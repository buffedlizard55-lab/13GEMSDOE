"""R15 shallow-thermal line hypotheses, not confirmed faults or geothermal vents.

Frozen criteria: knowledge/11_r15_predeclared.md. The intensity builder never
receives fault labels. Only same-area, measured warm-station spans are drawn.
GDR1391 source README defines F2mDAB as temperature minus area background;
zero is a valid value. Primary dates can be seasonal-correction dates.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import shapefile
from rasterio.features import rasterize
from rasterio.transform import rowcol
from rasterio.warp import transform as project
from scipy.spatial import cKDTree

DAB_MIN_C = 3.0
NEIGHBOUR_M = 1500.0
MIN_STATIONS = 3
AXIS_RATIO = 4.0
MAX_PERP_RMS_M = 300.0


def load_probes(path: Path, affine, footprint: np.ndarray) -> tuple[list[dict], dict]:
    """Read NAD83 coordinates and exclude invalid/out-of-footprint stations.

    The paired .prj must say NAD83 geographic, not merely be assumed from a
    filename. Array-safe rowcol is used (Dataset.index accepts scalars).
    """
    prj = path.with_suffix('.prj').read_text().upper()
    if not (prj.startswith('GEOGCS') and ('NAD_1983' in prj or 'NORTH_AMERICAN' in prj)):
        raise ValueError('Expected source NAD83 geographic CRS; inspect .prj before use')
    reader = shapefile.Reader(str(path))
    if reader.shapeType != shapefile.POINT:
        raise ValueError('Expected point probes')
    required = {'Area', 'F2mDAB', 'T2m', 'Date'}
    if not required.issubset({f[0] for f in reader.fields[1:]}):
        raise ValueError('Probe schema differs from the inspected GDR1391 release')
    raw = []
    invalid_coordinates = 0
    for sr in reader.iterShapeRecords():
        rec = sr.record.as_dict()
        if not sr.shape.points:
            invalid_coordinates += 1
            continue
        lon, lat = sr.shape.points[0]
        if not (np.isfinite(lon) and np.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            invalid_coordinates += 1
            continue
        raw.append((lon, lat, rec))
    if not raw:
        return [], {'source_records': len(reader), 'inside_footprint': 0,
                    'invalid_coordinates': invalid_coordinates}
    xx, yy = project('EPSG:4269', 'EPSG:32611',
                     [t[0] for t in raw], [t[1] for t in raw])
    rows, cols = rowcol(affine, xx, yy)
    rows, cols = np.asarray(rows), np.asarray(cols)
    in_grid = (rows >= 0) & (rows < footprint.shape[0]) & (cols >= 0) & (cols < footprint.shape[1])
    in_fp = np.zeros(len(raw), bool)
    in_fp[in_grid] = footprint[rows[in_grid], cols[in_grid]]
    probes, repeats = [], Counter()
    rejected_values = 0
    for i in np.flatnonzero(in_fp):
        rec = raw[i][2]
        dated = sum(rec.get('Date' + s) is not None
                    and rec.get('T2m' + s) is not None
                    and np.isfinite(rec['T2m' + s]) and rec['T2m' + s] > 0
                    for s in ('', '_2', '_3', '_4', '_5', '_6', '_7'))
        repeats[dated] += 1
        t, dab = rec['T2m'], rec['F2mDAB']
        if t is None or dab is None or not np.isfinite([t, dab]).all() or not -50 <= t <= 150 or not -100 <= dab <= 100:
            rejected_values += 1
            continue
        probes.append({'x': float(xx[i]), 'y': float(yy[i]),
                       'area': str(rec['Area']).strip(), 'dab_c': float(dab),
                       't2m_c': float(t), 'date': str(rec['Date']),
                       'station': str(rec.get('Station', '')), 'dated_measurements': dated})
    stats = {'source_records': len(reader), 'in_bounding_rectangle': int(in_grid.sum()),
             'inside_footprint': int(in_fp.sum()), 'usable_probes': len(probes),
             'invalid_coordinates': invalid_coordinates, 'rejected_temperature_values': rejected_values,
             'areas': dict(sorted(Counter(t['area'] for t in probes).items())),
             'dated_measurements_histogram': {str(k): v for k, v in sorted(repeats.items())},
             'repeat_warning': 'Primary dates may be correction dates; repeats are an availability diagnostic, not independent seasonal validation.'}
    return probes, stats


def corridor_segments(probes: list[dict]) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], dict]:
    """Weighted local PCA, no labels, no score-based parameter selection.

    Exact duplicate locations cannot satisfy the minimum independent-station
    count. The larger DAB is retained at duplicates; they are not averaged into
    falsely independent corroborating evidence. Segments never cross Area.
    """
    areas = sorted({p['area'] for p in probes if p['area']})
    segments, warm_total, groups_checked, duplicate_locations = [], 0, 0, 0
    seen = set()
    for area in areas:
        unique = {}
        for p in probes:
            if p['area'] != area or not np.isfinite(p['dab_c']) or p['dab_c'] < DAB_MIN_C:
                continue
            xy = (p['x'], p['y'])
            if not np.isfinite(xy).all():
                continue
            if xy in unique:
                duplicate_locations += 1
            unique[xy] = max(unique.get(xy, DAB_MIN_C), min(p['dab_c'], 30.0))
        xy = np.asarray(list(unique), dtype=np.float64).reshape(-1, 2)
        warm_total += len(xy)
        if len(xy) < MIN_STATIONS:
            continue
        weights = np.asarray(list(unique.values()), dtype=np.float64)
        tree = cKDTree(xy)
        for centre in xy:
            ix = tree.query_ball_point(centre, NEIGHBOUR_M)
            key = (area, tuple(sorted(ix)))
            if len(ix) < MIN_STATIONS or key in seen:
                continue
            seen.add(key)
            groups_checked += 1
            points, w = xy[ix], weights[ix]
            mean = np.average(points, axis=0, weights=w)
            z = points - mean
            cov = (z * w[:, None]).T @ z / w.sum()
            ev, axes = np.linalg.eigh(cov)
            if ev[1] <= 0 or ev[1] / max(ev[0], 1.0) < AXIS_RATIO or np.sqrt(max(ev[0], 0)) > MAX_PERP_RMS_M:
                continue
            along = z @ axes[:, 1]
            endpoints = mean + np.outer([along.min(), along.max()], axes[:, 1])
            segments.append((tuple(endpoints[0]), tuple(endpoints[1])))
    return segments, {'warm_unique_probes': warm_total, 'neighbourhoods_checked': groups_checked,
                      'segments_emitted': len(segments), 'warm_duplicate_locations': duplicate_locations,
                      'criteria': {'dab_min_c': DAB_MIN_C, 'neighbour_m': NEIGHBOUR_M,
                                   'min_stations': MIN_STATIONS, 'axis_ratio_min': AXIS_RATIO,
                                   'perpendicular_rms_max_m': MAX_PERP_RMS_M}}


def build_corridors(probes: list[dict], affine, footprint: np.ndarray) -> tuple[np.ndarray, dict]:
    segments, stats = corridor_segments(probes)
    if segments:
        shapes = [({'type': 'LineString', 'coordinates': [a, b]}, 1) for a, b in segments]
        field = rasterize(shapes, out_shape=footprint.shape, transform=affine,
                          fill=0, all_touched=False, dtype='uint8').astype(bool)
    else:
        field = np.zeros(footprint.shape, bool)
    field &= footprint
    return field, {**stats, 'positive_pixels': int(field.sum()),
                   'coverage_pct': 100.0 * int(field.sum()) / max(int(footprint.sum()), 1),
                   'interpretation': 'Thermal line hypotheses only; heat/outflow is not proof of fault displacement.'}
