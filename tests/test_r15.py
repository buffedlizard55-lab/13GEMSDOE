"""Synthetic evidence-boundary and geographic leakage regression tests."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import shapefile
from rasterio.transform import from_origin
from rasterio.warp import transform

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems import thermal  # noqa: E402
from gems.spatial import spatially_blocked_folds  # noqa: E402


def probes(xy, areas=None, dab=6.0):
    return [{'x': x, 'y': y, 'area': areas[i] if areas else 'same survey', 'dab_c': dab}
            for i, (x, y) in enumerate(xy)]


def test_three_warm_aligned_stations_emit_only_observed_span():
    seg, stats = thermal.corridor_segments(probes([(0, 0), (400, 0), (800, 0)]))
    assert stats['segments_emitted'] == 1
    assert sorted(seg[0]) == [(0.0, 0.0), (800.0, 0.0)]


def test_background_or_missing_signal_emits_nothing():
    for dab in (0.0, -5.0, float('nan')):
        assert thermal.corridor_segments(probes([(0, 0), (100, 0), (200, 0)], dab=dab))[0] == []


def test_duplicate_locations_are_not_independent_corroboration():
    seg, stats = thermal.corridor_segments(probes([(0, 0)] * 3))
    assert seg == [] and stats['warm_duplicate_locations'] == 2


def test_distinct_survey_areas_cannot_make_a_corridor():
    assert thermal.corridor_segments(probes([(0, 0), (100, 0), (200, 0)], ['A', 'A', 'B']))[0] == []


def test_round_hot_spot_is_not_a_linear_corridor():
    assert thermal.corridor_segments(probes([(-100, -100), (-100, 100), (100, -100), (100, 100)]))[0] == []


def test_sparse_distant_points_do_not_extrapolate():
    assert thermal.corridor_segments(probes([(0, 0), (5000, 0), (10000, 0)]))[0] == []


def test_empty_builder_returns_zero_even_with_valid_footprint():
    fp = np.ones((10, 10), bool)
    a, stats = thermal.build_corridors([], from_origin(0, 1000, 100, 100), fp)
    assert a.dtype == bool and not a.any() and stats['segments_emitted'] == 0


def test_dab_zero_is_retained_by_loader(tmp_path):
    p = tmp_path / 'test.shp'
    with shapefile.Writer(str(p)) as w:
        w.field('Area', 'C'); w.field('F2mDAB', 'F', 19, 3)
        w.field('T2m', 'F', 19, 3); w.field('Date', 'D')
        w.point(-118.0, 39.0); w.record('test', 0.0, 20.0, None)
    p.with_suffix('.prj').write_text('GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983"]]')
    x, y = transform('EPSG:4269', 'EPSG:32611', [-118.0], [39.0])
    affine = from_origin(x[0]-500, y[0]+500, 100, 100)
    points, stats = thermal.load_probes(p, affine, np.ones((10, 10), bool))
    assert len(points) == 1 and points[0]['dab_c'] == 0.0 and stats['inside_footprint'] == 1
    p.with_suffix('.prj').write_text('PROJCS["NAD_1983_UTM_Zone_11N"]')
    with pytest.raises(ValueError, match='geographic'):
        thermal.load_probes(p, affine, np.ones((10, 10), bool))


def test_geographic_fold_labels_and_boundaries_are_separated():
    valid = np.ones((80, 80), bool)
    known = np.zeros_like(valid); known[15:65, 15:65] = True
    folds = spatially_blocked_folds(known, valid, tile_px=20, buffer_px=5, guard_px=3)
    seen = np.zeros_like(known, np.int8)
    for f in folds:
        assert not (f.hidden & f.visible).any()
        assert not (f.hidden & ~f.eval_mask).any()
        assert not (f.visible & f.eval_mask).any()
        assert f.meta['label_dependent_tile_selection'] is False
        seen += f.eval_mask
    assert seen.max() == 1  # disjoint scoring domains, no duplicated truth
    assert seen.min() == 0  # boundary guards deliberately not scored
    other = spatially_blocked_folds(np.zeros_like(known), valid, tile_px=20, buffer_px=5, guard_px=3)
    for a, b in zip(folds, other):
        np.testing.assert_array_equal(a.eval_mask, b.eval_mask)  # partition cannot depend on label selection


@pytest.mark.parametrize('tile,buffer,guard', [(6, 5, 3), (20, 2, 3), (20, 5, -1)])
def test_bad_geographic_parameters_rejected(tile, buffer, guard):
    with pytest.raises(ValueError):
        spatially_blocked_folds(np.zeros((40, 40), bool), np.ones((40, 40), bool),
                               tile_px=tile, buffer_px=buffer, guard_px=guard)
