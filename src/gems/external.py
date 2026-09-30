"""Loader for the OFFICIAL external products staged in ``data/external/``.

Every product here comes from a U.S. Geological Survey public-domain release and
was re-gridded onto the competition grid (EPSG:32611, 100 m, 3730x3292, transform
``(100, 0, 243350; 0, -100, 4508550)``) by this group's sibling repositories in
open-egress runners. ``scripts/fetch_external_data.py`` re-stages them and
verifies each file twice (sha256 pinned in the sibling provenance record + git
blob SHA-1 pinned from the sibling git tree).

Sources (official, free, public domain):

  GeoDAWN airborne magnetic and radiometric surveys, northwestern Great Basin
      Glen, J.M.G., and Earney, T.E., 2024, U.S. Geological Survey data release,
      https://doi.org/10.5066/P93LGLVQ
      https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7
  USGS 3DEP elevation (1 m / 10 m)
      https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/
      acknowledgement: "Map services and data available from U.S. Geological
      Survey, National Geospatial Program."
  USGS Quaternary fault and fold database (QFFDB)
      https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip
      https://doi.org/10.5066/P9BCVRCK

Dequantisation is **not** transcribed by hand: the lo/hi percentile limits and
the sqrt/linear quantisation rules are read at run time from the sibling
provenance records that ``scripts/fetch_external_data.py`` copies into
``reports/external_provenance/``. If a record is missing, the loader raises
rather than guessing.

All products are ``uint8`` with **0 == nodata**; loaders return ``float32`` with
``NaN`` where the product is undefined, so callers can mask honestly (LiDAR
covers 75.3 % of the footprint, its directional channels 62.1 %).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
EXT_DIR = ROOT / "data" / "external"
PROV_DIR = ROOT / "reports" / "external_provenance"

LIDAR = "lidar_scarp_features_u8.tif"
TOPO = "topo_u8.tif"
RAD = "radiometric_u8.tif"
GEODAWN_RAD = "geodawn_rad_u8.tif"
GEODAWN_EXT = "geodawn_extensions_u8.tif"
QFAULTS = "qfaults_prior_u8.tif"

# provenance record staged by scripts/fetch_external_data.py
_PROV_FILES = {
    LIDAR: "7GEMSDOE__external_dem_lidar_scarp_features.json",
    TOPO: "5GEMSDOE__data_aux_bridge_topo_manifest.json",
    RAD: "5GEMSDOE__data_aux_bridge_radiometric_manifest.json",
    GEODAWN_RAD: "7GEMSDOE__external_geodawn_rad_geodawn_rad.json",
    GEODAWN_EXT: "7GEMSDOE__external_geodawn_extensions_geodawn_extensions.json",
    QFAULTS: "7GEMSDOE__external_qfaults_qfaults_prior.json",
}

FETCH_HINT = ("data/external/ is not staged. Run: "
              ".venv/bin/python scripts/fetch_external_data.py")


def _prov(fname: str) -> dict:
    p = PROV_DIR / _PROV_FILES[fname]
    if not p.exists():
        raise FileNotFoundError(f"missing provenance record {p}. {FETCH_HINT}")
    return json.loads(p.read_text())


def available() -> dict[str, bool]:
    """Which external products are present on disk."""
    return {f: (EXT_DIR / f).exists() for f in _PROV_FILES}


def require(*files: str) -> None:
    missing = [f for f in files if not (EXT_DIR / f).exists()]
    if missing:
        raise FileNotFoundError(f"missing external product(s): {missing}. {FETCH_HINT}")


def _open(fname: str):
    require(fname)
    return rasterio.open(EXT_DIR / fname)


def channel_names(fname: str) -> list[str]:
    with _open(fname) as ds:
        return [d for d in ds.descriptions]


def read_raw(fname: str, channel: str) -> np.ndarray:
    """Raw uint8 channel (0 == nodata), no dequantisation."""
    with _open(fname) as ds:
        names = list(ds.descriptions)
        if channel not in names:
            raise KeyError(f"{channel!r} not in {fname}: {names}")
        return ds.read(names.index(channel) + 1)


def _linear_from_limits(q: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Inverse of q = 1 + round(254*clip((v-lo)/(hi-lo),0,1)); 0 -> NaN."""
    v = lo + (q.astype(np.float32) - 1.0) / 254.0 * (hi - lo)
    return np.where(q > 0, v, np.nan).astype(np.float32)


def _sqrt_from_xmax(q: np.ndarray, xmax: float) -> np.ndarray:
    """Inverse of q = 1 + round(254*sqrt(clip(x/xmax,0,1))); 0 -> NaN."""
    t = (q.astype(np.float32) - 1.0) / 254.0
    return np.where(q > 0, xmax * t * t, np.nan).astype(np.float32)


def _rank_from_percentile(q: np.ndarray) -> np.ndarray:
    """Percentile-rank quantisation (GeoDAWN products): bytes are ranks, not
    physical units (stated in the provenance record). 0 -> NaN, else [0,1]."""
    return np.where(q > 0, (q.astype(np.float32) - 1.0) / 254.0, np.nan).astype(np.float32)


def read_channel(fname: str, channel: str) -> np.ndarray:
    """Dequantised float32 channel, NaN where the product is undefined."""
    q = read_raw(fname, channel)
    if fname in (TOPO, RAD):
        prov = _prov(fname)
        for b in prov["bands"]:
            if b["band_name"] == channel:
                return _linear_from_limits(q, float(b["lo"]), float(b["hi"]))
        raise KeyError(f"no quantisation record for {channel} in {_PROV_FILES[fname]}")
    if fname == LIDAR:
        prov = _prov(fname)
        if channel not in prov["quantisation"]:
            raise KeyError(f"no quantisation record for {channel} in lidar manifest")
        xmax, kind = prov["quantisation"][channel]
        if kind == "sqrt":
            return _sqrt_from_xmax(q, float(xmax))
        if kind == "linear":
            return np.where(q > 0, float(xmax) * (q.astype(np.float32) - 1.0) / 254.0,
                            np.nan).astype(np.float32)
        raise ValueError(f"unknown quantisation kind {kind!r}")
    if fname in (GEODAWN_RAD, GEODAWN_EXT):
        return _rank_from_percentile(q)
    if fname == QFAULTS:
        return np.where(q > 0, 1.0, 0.0).astype(np.float32)
    raise KeyError(f"no dequantisation rule for {fname}")


def read_stack(fname: str, channels: list[str] | None = None) -> dict[str, np.ndarray]:
    names = channels or channel_names(fname)
    return {c: read_channel(fname, c) for c in names}


def lidar_coverage(fname: str = LIDAR) -> np.ndarray:
    """Boolean mask of grid cells with LiDAR-derived values (channel `valid`)."""
    return read_raw(fname, "valid") > 0


def grid_matches_competition(fname: str) -> bool:
    with _open(fname) as ds:
        return (ds.height == 3730 and ds.width == 3292
                and ds.crs is not None and ds.crs.to_epsg() == 32611
                and tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0,
                                                0.0, -100.0, 4508550.0))
