#!/usr/bin/env python3
"""Compute every candidate detector map once and cache it to data/derived/.

All detectors here use ONLY the 19 official feature bands. None of them reads
the fault catalogue, so caching them globally does not leak holdout
information: the catalogue-dependent part (H-D's fault-density term) is rebuilt
per fold from the VISIBLE catalogue inside scripts/run_holdout.py.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import detectors as D  # noqa: E402

FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"
LABELS = ROOT / "data" / "raw" / "existing_faults.tif"
OUTDIR = ROOT / "data" / "derived"
OUTDIR.mkdir(parents=True, exist_ok=True)

BAND = {}  # code -> 1-based index


def band(code: str) -> np.ndarray:
    with rasterio.open(FEATS) as src:
        a = src.read(BAND[code]).astype(np.float32)
        nd = src.nodatavals[BAND[code] - 1]
    if nd is not None:
        a = np.where(a <= nd + abs(nd) * 1e-6, np.nan, a)
    a = np.where(np.isfinite(a), a, np.nan)
    return a


def save(name: str, arr: np.ndarray) -> None:
    np.save(OUTDIR / f"{name}.npy", arr.astype(np.float32))
    print(f"    saved {name}.npy  "
          f"[{float(np.nanmin(arr)):.3f}, {float(np.nanmax(arr)):.3f}]  "
          f"nz={int((arr > 0).sum()):,}")


def main() -> None:
    with rasterio.open(FEATS) as src:
        for i, d in enumerate(src.descriptions, 1):
            BAND[(d or f"b{i}").split(" - ")[0].strip()] = i
    with rasterio.open(LABELS) as src:
        lab = src.read(1)
    valid = lab >= 0
    np.save(OUTDIR / "_valid.npy", valid)
    np.save(OUTDIR / "_known.npy", lab > 0)

    manifest = {}
    t0 = time.time()

    def step(name, fn, desc, bands_used):
        t = time.time()
        print(f"[{time.time()-t0:7.1f}s] {name}: {desc}")
        arr = fn()
        arr = np.where(valid, np.nan_to_num(arr, nan=0.0), 0.0).astype(np.float32)
        save(name, arr)
        manifest[name] = {"description": desc, "bands": bands_used,
                          "seconds": round(time.time() - t, 1)}
        del arr

    # ---- H-A  multiscale potential-field worms -----------------------------
    step("HA_worms_rtp", lambda: D.worms(band("rtp")),
         "cross-scale persistence of horizontal-gradient maxima of the "
         "reduced-to-pole magnetic field, upward-continued 0-8 km",
         ["rtp"])
    step("HA_worms_grav", lambda: D.worms(band("iso_grav_anom")),
         "same worming operator on the isostatic gravity anomaly",
         ["iso_grav_anom"])

    # ---- H-B  amplitude-normalised source-edge detection -------------------
    step("HB_tdr_rtp", lambda: D.tdr_edge(band("rtp")),
         "tilt-derivative zero-contour steepness on RTP magnetics",
         ["rtp"])
    step("HB_tdr_grav", lambda: D.tdr_edge(band("iso_grav_anom")),
         "tilt-derivative zero-contour steepness on isostatic gravity",
         ["iso_grav_anom"])
    step("HB_theta_rtp", lambda: D.robust_norm(D.theta_map(band("rtp"))),
         "theta map (acos(THDR/AS)) on RTP magnetics", ["rtp"])

    # ---- H-C  concealed basement hinge under flat cover --------------------
    step("HC_hinge", lambda: D.basement_hinge(band("depth_to_base_surf"),
                                              band("det_elev_slope")),
         "linear steps in depth-to-conductive-base restricted to "
         "topographically flat ground (buried structures only)",
         ["depth_to_base_surf", "det_elev_slope"])

    # ---- H-D  strain budget (catalogue term added per fold) ----------------
    step("HD_strain_raw",
         lambda: D.strain_residual(band("geod_2ndinv"), band("ieq_n100a15"),
                                   np.zeros_like(valid, dtype=np.float32)),
         "geodetic 2nd invariant minus earthquake density (fault-density term "
         "is added per holdout fold from the VISIBLE catalogue only)",
         ["geod_2ndinv", "ieq_n100a15"])

    # ---- H-E  directional-coherence lineaments -----------------------------
    step("HE_lin_tc", lambda: D.directional_lineaments(band("tc")),
         "oriented matched-filter lineaments in band `tc` "
         "(GeoDAWN radiometric total count - see irregularity I-2)", ["tc"])
    step("HE_lin_cond", lambda: D.directional_lineaments(band("cond_surf")),
         "oriented matched-filter lineaments in surface conductivity",
         ["cond_surf"])

    # ---- R6-2 paleo shoreline / intrabasin scarp -------------------------
    step("R6_shore",
         lambda: D.paleo_shoreline_scarp(band("det_elev"), band("det_elev_slope")),
         "R6-2 paleo-shoreline / lacustrine terrace scarp: curvature ridge on detrended elev gated to flat playa/lake beds",
         ["det_elev", "det_elev_slope"])

    # ---- R6-3 conductive base step improved --------------------------------
    step("R6_condbase",
         lambda: D.conductive_base_step(band("depth_to_base_surf"), band("cond_surf"), band("det_elev_slope")),
         "R6-3 conductive-base step: product of depth-to-base and cond gradients, oriented-filtered, anti-topo gated",
         ["depth_to_base_surf", "cond_surf", "det_elev_slope"])

    # ---- R6-4 gravity termination ------------------------------------------
    step("R6_gravterm",
         lambda: D.gravity_termination(band("iso_grav_anom_hg"), band("iso_grav_anom_vg"), band("iso_grav_anom")),
         "R6-4 gravity-gradient termination/intersection: where hg ridge terminates, emit continuation",
         ["iso_grav_anom_hg", "iso_grav_anom_vg", "iso_grav_anom"])

    # ---- R6-5 transtensional coupling --------------------------------------
    step("R6_transt",
         lambda: D.transtensional_coupling(band("geod_shearrate"), band("geod_dilaterate"), band("geod_2ndinv"), band("iso_grav_anom_hg")),
         "R6-5 transtensional coupling: shear * positive dilatation * 2nd invariant localized by gravity gradient",
         ["geod_shearrate", "geod_dilaterate", "geod_2ndinv", "iso_grav_anom_hg"])

    # ---- R6-1 horsetail splay (catalogue-dependent, cached for full catalogue)
    def _horse_full():
        known = np.load(OUTDIR / "_known.npy")
        return D.horsetail_splay(known, max_gap_px=20, splay_len_px=12)
    step("R6_horse_full",
         _horse_full,
         "R6-1 horsetail splay / relay-ramp (full catalogue version for submission): connects step-overs and fans at tips",
         ["existing_faults (catalogue geometry)"])

    # ---- baseline the team has already relied on ---------------------------
    step("BASE_topo_ridge",
         lambda: D.robust_norm(D.nms_thin(
             *D.ridge_strength(D.robust_norm(band("det_elev_slope")), 1.5))),
         "BASELINE: topographic scarp/ridge detector on detrended-elevation "
         "slope - the family this team has already submitted repeatedly",
         ["det_elev_slope"])
    step("BASE_tmi_hg",
         lambda: D.robust_norm(D.nms_thin(
             *D.ridge_strength(D.robust_norm(band("tmi_hg")), 1.5))),
         "BASELINE: single-scale horizontal-gradient ridge on the provided "
         "TMI horizontal gradient band", ["tmi_hg"])

    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "detectors_manifest.json").write_text(
        json.dumps({"bands_in_file": BAND, "detectors": manifest,
                    "total_seconds": round(time.time() - t0, 1)}, indent=2))
    print(f"\ndone in {time.time()-t0:.1f}s -> {OUTDIR}")


if __name__ == "__main__":
    main()
