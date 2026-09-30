#!/usr/bin/env python3
"""Build the R10 external-data detector maps and cache them to data/derived/.

Inputs are the OFFICIAL external products staged by
``scripts/fetch_external_data.py`` (USGS 3DEP 1-m LiDAR morphometrics, USGS
GeoDAWN airborne radiometrics) plus two PROVIDED bands for the vent conjunction
(`cond_surf` 17, `depth_to_base_surf` 15). None of the R10 detectors reads the
fault catalogue, so these maps are fold-independent and cannot leak withheld
traces into the hide-and-recover holdout.

Memory: the box has ~3.9 GB RAM, so channels are loaded one at a time and freed;
every map is written to disk as float32 before the next is computed.

Outputs
  data/derived/R10_*.npy                     the detector maps
  reports/external_detectors_manifest.json   what was built, with full-domain
                                             univariate AUC against the provided
                                             catalogue and top-5 % recall
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import detectors as D          # noqa: E402
from gems import external as X           # noqa: E402

RAW = ROOT / "data" / "raw"
FEATS = RAW / "gems-geodawn-numerical-features.tif"
LABELS = RAW / "existing_faults.tif"
OUT = ROOT / "data" / "derived"
OUT.mkdir(parents=True, exist_ok=True)
REPORTS = ROOT / "reports"
FEATURE_NODATA = -3.4028234663852886e38


def provided_band(code: str) -> np.ndarray:
    with rasterio.open(FEATS) as src:
        idx = None
        for i, d in enumerate(src.descriptions, start=1):
            if (d or "").split(" - ")[0].strip() == code:
                idx = i
                break
        if idx is None:
            raise KeyError(f"band {code!r} not found in the feature stack")
        a = src.read(idx).astype(np.float32)
    a = np.where(a <= FEATURE_NODATA + abs(FEATURE_NODATA) * 1e-6, np.nan, a)
    return np.where(np.isfinite(a), a, np.nan).astype(np.float32)


def auc_top5(score: np.ndarray, known: np.ndarray, valid: np.ndarray,
              top_frac: float = 0.05) -> dict:
    """Full-domain univariate AUC and top-k catalogue recall.

    Restricted to the valid footprint: `score` outside it is irrelevant because
    the submission format requires null/NaN there and the scoring mask is the
    label raster's own valid mask.
    """
    v = valid.ravel()
    s = np.where(np.isfinite(score.ravel()), score.ravel(), np.nan)
    pos = (known & valid).ravel()
    sv = s[v]
    pv = pos[v]
    finite = np.isfinite(sv)
    if finite.sum() == 0:
        return {"auc": None, "catalogue_recall_in_top5pct": None,
                "catalogue_precision_in_top5pct": None,
                "nonzero_px_inside_footprint": int(((score > 0) & valid).sum())}
    lo = float(sv[finite].min())
    sv = np.where(finite, sv, lo)          # undefined channels rank last
    n_pos = int(pv.sum())
    n_neg = int((~pv).sum())
    r = rankdata(sv)
    auc = float((r[pv].mean() - (n_pos + 1) / 2.0) / n_neg) if n_neg else float("nan")
    k = int(top_frac * v.sum())
    top_idx = np.argpartition(-sv, k)[:k]
    topmask = np.zeros(sv.size, dtype=bool)
    topmask[top_idx] = True
    return {"auc": round(auc, 5),
            "domain_px": int(v.sum()),
            "catalogue_recall_in_top5pct": round(float((topmask & pv).sum()) / max(n_pos, 1), 5),
            "catalogue_precision_in_top5pct": round(float((topmask & pv).sum()) / max(k, 1), 5),
            "nonzero_px_inside_footprint": int(((score > 0) & valid).sum())}


def main() -> int:
    t0 = time.time()
    X.require(X.LIDAR, X.TOPO, X.RAD)
    with rasterio.open(LABELS) as src:
        lab = src.read(1)
    valid = lab >= 0
    known = lab > 0
    del lab
    print(f"footprint {int(valid.sum()):,} px, catalogue {int(known.sum()):,} px")

    manifest: dict = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {
            "lidar": {"file": X.LIDAR,
                      "source": "USGS 3DEP 1 m DEM, 716 tiles; morphometrics computed "
                                "at 2 m working resolution and aggregated to 100 m",
                      "official": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/"},
            "topo": {"file": X.TOPO, "source": "USGS 3DEP DEM -> 9 channels at 100 m"},
            "radiometric": {"file": X.RAD,
                            "source": "USGS GeoDAWN airborne radiometric survey",
                            "official": "https://doi.org/10.5066/P93LGLVQ"},
            "provided_bands": ["cond_surf (17)", "depth_to_base_surf (15)"],
        },
        "catalogue_input": False,
        "maps": {},
    }

    def finish(name: str, arr: np.ndarray, desc: str, layers: list[str]) -> np.ndarray:
        arr = np.where(valid, np.nan_to_num(arr, nan=0.0), 0.0).astype(np.float32)
        np.save(OUT / f"{name}.npy", arr)
        stats = auc_top5(arr, known, valid)
        stats.update({"description": desc, "layers": layers,
                      "min": float(arr.min()), "max": float(arr.max())})
        manifest["maps"][name] = stats
        print(f"[{time.time()-t0:6.1f}s] {name}: AUC={stats['auc']:.4f} "
              f"top5%recall={stats['catalogue_recall_in_top5pct']:.4f} "
              f"nz={stats['nonzero_px_inside_footprint']:,}  {desc[:70]}")
        return arr

    # ---- R10-3 damage-zone texture -----------------------------------------
    slope_std = X.read_channel(X.TOPO, "slope_std")
    curv = X.read_channel(X.TOPO, "curv_prof_absmax")
    relief = X.read_channel(X.TOPO, "relief_local")
    finish("R10_dzt", D.damage_zone_texture(slope_std, curv),
           "R10-3 damage-zone texture: persistent ridge crests of slope_std x "
           "profile curvature (3DEP DEM)", ["topo::slope_std", "topo::curv_prof_absmax"])
    dzt_field = finish("R10_dzt_field",
                       D.damage_zone_texture(slope_std, curv, thin=False),
                       "R10-3 un-thinned damage-zone texture field (for fusion)",
                       ["topo::slope_std", "topo::curv_prof_absmax"])
    del slope_std, curv

    # ---- R10-1 LiDAR morphometric scarp composite ---------------------------
    lidar_ch = {c: X.read_channel(X.LIDAR, c) for c in
                ("step_max", "ex_max", "ex_mean", "lapneg_max", "lappos_max",
                 "upface_max")}
    finish("R10_scarp", D.lidar_scarp_composite(lidar_ch),
           "R10-1 LiDAR scarp composite: band-passed step x slope-excess x "
           "(crest convexity x toe concavity) x antislope, persistent crests",
           [f"lidar::{c}" for c in lidar_ch])
    scarp_field = finish("R10_scarp_field",
                         D.lidar_scarp_composite(lidar_ch, thin=False),
                         "R10-1 un-thinned LiDAR scarp field (for fusion)",
                         [f"lidar::{c}" for c in lidar_ch])
    del lidar_ch

    # ---- R10-2 radiometric alteration-ratio lineaments ----------------------
    uk = X.read_channel(X.RAD, "rad_uk")
    uth = X.read_channel(X.RAD, "rad_uth")
    finish("R10_alter", D.alteration_ratio_lineaments(uk, uth, relief),
           "R10-2 alteration lineaments: relief-residual U/K x U/Th local "
           "anomalies, persistent crests", ["radiometric::rad_uk",
                                            "radiometric::rad_uth",
                                            "topo::relief_local"])
    alter_field = finish("R10_alter_field",
                         D.alteration_ratio_lineaments(uk, uth, relief, thin=False),
                         "R10-2 un-thinned alteration-residual field (for fusion)",
                         ["radiometric::rad_uk", "radiometric::rad_uth",
                          "topo::relief_local"])
    del uk, uth, relief

    # ---- R10-4 vent conjunction --------------------------------------------
    cond = provided_band("cond_surf")
    base = provided_band("depth_to_base_surf")
    cond_hp = D.highpass_residual(cond, None, sigma_px=12.0)
    base_hp = D.highpass_residual(-base, None, sigma_px=12.0)
    del cond, base
    vent = D.vent_conjunction(scarp_field, alter_field, cond_hp, base_hp,
                              require_all=True)
    finish("R10_vent", vent,
           "R10-4 vent conjunction: LiDAR scarp x alteration chemistry x "
           "surface-conductivity anomaly x shallow conductive base",
           ["R10_scarp_field", "R10_alter_field", "cond_surf (17)",
            "depth_to_base_surf (15)"])
    # a morphology+chemistry-only variant, for the 38% of the footprint with no
    # LiDAR directional channels and for ablation
    vent2 = D.vent_conjunction(dzt_field, alter_field, cond_hp, base_hp,
                               require_all=True)
    finish("R10_vent_dzt", vent2,
           "R10-4b vent conjunction with damage-zone texture instead of the "
           "LiDAR scarp composite (100 % footprint coverage)",
           ["R10_dzt_field", "R10_alter_field", "cond_surf (17)",
            "depth_to_base_surf (15)"])

    manifest["total_seconds"] = round(time.time() - t0, 1)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "external_detectors_manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(f"\nwrote reports/external_detectors_manifest.json ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
