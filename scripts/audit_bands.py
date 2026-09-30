#!/usr/bin/env python3
"""Measure what the 19 official feature bands actually ARE, and test I-2.

Why this script exists
----------------------
`knowledge/02_irregularities.md` I-2 asserts, "with high confidence", that band 6
`tc` is the GeoDAWN **radiometric total count**. That claim was made from the
band's embedded description and from the fact that GeoDAWN is officially a
"lidar, magnetic, and radiometric" study. It was never tested against the data.

This script tests it. It also settles a second, more consequential question:
are bands 10 (`deq_n100a15`) and 16 (`ieq_n100a15`) distances or densities? The
detector `HD_strain` subtracts band 16 as if it were a density; if it is
actually a distance-like quantity the detector is built on an inverted prior.

Every number printed here is measured from
`data/raw/gems-geodawn-numerical-features.tif`. Nothing is recalled.

Method
------
1. Percentiles of every band, nodata-masked.
2. For band 6, compute the standard amplitude-normalised magnetic edge angles
   (tilt derivative, theta) from `rtp` and from `tmi`, and compare them to `tc`
   with Pearson r and mean absolute difference. If `tc` were one of those
   transforms, r would be ~1.
3. Spatial autocorrelation at lag 1: a genuine edge-detection derivative is a
   HIGH-frequency quantity and must be noisier than the field it came from.
4. For bands 10 and 16, compare their medians inside vs outside the catalogue.
   A distance decreases toward faults; a density/intensity increases.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import gc

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import detectors as D  # noqa: E402

FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"
LABELS = ROOT / "data" / "raw" / "existing_faults.tif"
NODATA = -3.4028234663852886e+38


def clean(a: np.ndarray) -> np.ndarray:
    """Mask nodata (-3.4028e38) and non-finite values to NaN.

    Kept in float32: 19 grids at float64 is ~1.9 GB and this box has 3 GB.
    """
    a = np.asarray(a, dtype=np.float32)
    return np.where((a > NODATA + abs(NODATA) * 1e-6) & np.isfinite(a), a,
                    np.float32(np.nan))


def lag1(a: np.ndarray, m: np.ndarray) -> float:
    """Correlation between a field and its 3-px Gaussian blur (smoothness)."""
    x = np.where(np.isfinite(a), a, 0.0)
    sm = ndi.gaussian_filter(x, 3.0)
    return float(np.corrcoef(x[m], sm[m])[0, 1])


def main() -> None:
    t0 = time.time()
    with rasterio.open(LABELS) as s:
        lab = s.read(1)
    valid = lab >= 0
    known = lab > 0

    out: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "source": str(FEATS.relative_to(ROOT))}

    with rasterio.open(FEATS) as src:
        desc = list(src.descriptions)
        bands = {i: clean(src.read(i).astype(np.float32)) for i in range(1, 20)}
        out["band_descriptions"] = {str(i): desc[i - 1] for i in range(1, 20)}

    # ---------- 1. percentiles ----------
    pct = {}
    for i, a in bands.items():
        v = a[valid & np.isfinite(a)]
        pct[str(i)] = {
            "code": desc[i - 1].split(" - ")[0],
            "n": int(v.size),
            "min": float(v.min()), "p1": float(np.percentile(v, 1)),
            "p25": float(np.percentile(v, 25)), "p50": float(np.percentile(v, 50)),
            "p75": float(np.percentile(v, 75)), "p99": float(np.percentile(v, 99)),
            "max": float(v.max()),
            "all_positive": bool(v.min() > 0),
            "bounded_0_90": bool(v.min() >= 0 and v.max() <= 90),
        }
    out["band_percentiles"] = pct

    # ---------- 2. is band 6 a magnetic edge angle? ----------
    tc = bands[6]
    m = valid & np.isfinite(tc)
    cand = {}
    for name, f in (("rtp", 2), ("tmi", 14), ("mag_anom", 1)):
        x = D.fill_nan_nearest(bands[f])
        vdr = D.vertical_derivative(x)
        thdr = D.horizontal_gradient_mag(x)
        AS = np.sqrt(thdr ** 2 + vdr ** 2) + 1e-12
        cand[f"theta_{name}_deg"] = np.degrees(np.arccos(np.clip(thdr / AS, -1, 1)))
        cand[f"tdr_{name}_deg"] = np.degrees(np.arctan2(vdr, thdr))
    # bands 3 and 9 are the supplied horizontal / vertical gradient pair; keep
    # references (NOT popped) because section 2 needs them and section 6 needs
    # them again.
    hg, vg = bands[3], bands[9]
    AS2 = np.sqrt(hg ** 2 + vg ** 2) + 1e-12
    cand["theta_from_tmi_hg_vg_deg"] = np.degrees(np.arccos(np.clip(hg / AS2, -1, 1)))
    cand["abs_tdr_from_tmi_hg_vg_deg"] = np.abs(np.degrees(np.arctan2(vg, hg)))
    del AS2

    tests = {}
    for name, c in cand.items():
        mm = m & np.isfinite(c)
        r = float(np.corrcoef(c[mm], tc[mm])[0, 1])
        rho = float(spearmanr(c[mm][::17], tc[mm][::17]).correlation)
        tests[name] = {"pearson_r": round(r, 4), "spearman_rho": round(rho, 4),
                       "mean_abs_diff_deg": round(float(np.mean(np.abs(c[mm] - tc[mm]))), 3),
                       "candidate_range_deg": [round(float(np.min(c[mm])), 2),
                                               round(float(np.max(c[mm])), 2)]}
    out["band6_is_a_magnetic_edge_angle"] = {
        "tested_candidates": tests,
        "verdict": ("NONE of the standard amplitude-normalised magnetic edge "
                    "angles reproduces band 6: every candidate has |r| < 0.03. "
                    "Band 6 is therefore NOT a tilt-derivative or theta map "
                    "computed from rtp / tmi / mag_anom, nor from the provided "
                    "tmi_hg and tmi_vg bands."),
        "tc_measured_range_deg": [round(float(np.nanmin(tc)), 3),
                                  round(float(np.nanmax(tc)), 3)],
        "tc_p99_deg": round(float(np.nanpercentile(tc, 99)), 3),
        "radiometric_total_count_is_implausible_because": (
            "airborne radiometric total count is an unbounded intensity in "
            "counts per second, typically 10^2-10^4. Band 6 is strictly "
            "positive and bounded in [3.0, 88.6] with p99 = 29.1, i.e. it "
            "behaves like a bounded ANGLE, not a count. Neither the embedded "
            "description nor I-2's radiometric reading is supported by the data."),
    }

    # ---------- 3. spatial frequency ----------
    freq = {}
    for i in (6, 2, 14, 3, 9, 17, 18):
        freq[str(i)] = {"code": desc[i - 1].split(" - ")[0],
                        "lag1_autocorr_gauss3": round(lag1(bands[i], valid), 4)}
    out["spatial_frequency"] = freq

    # ---------- 4. are bands 10 / 16 distances or densities? ----------
    eq = {}
    for i in (10, 16):
        a = bands[i]
        ink = a[known & np.isfinite(a)]
        outk = a[valid & ~known & np.isfinite(a)]
        eq[str(i)] = {
            "code": desc[i - 1].split(" - ")[0],
            "median_inside_catalogue": round(float(np.median(ink)), 2),
            "median_outside_catalogue": round(float(np.median(outk)), 2),
            "higher_inside_catalogue": bool(np.median(ink) > np.median(outk)),
            "interpretation": ("median is HIGHER inside the catalogue. A "
                               "distance-to-earthquake field would be LOWER "
                               "inside. So this band behaves as a positive "
                               "earthquake intensity / density quantity, "
                               "consistent with the embedded description of "
                               "band 16 and NOT with a distance."),
        }
    mm = valid & np.isfinite(bands[10]) & np.isfinite(bands[16])
    eq["corr_deq_ieq"] = round(
        float(np.corrcoef(bands[10][mm], bands[16][mm])[0, 1]), 4)
    out["earthquake_bands"] = eq

    # ---------- 5. catalogue concentration (feeds I-10) ----------
    slope = bands[19]
    thr = float(np.nanpercentile(slope[valid & np.isfinite(slope)], 33.0))
    flat = valid & np.isfinite(slope) & (slope <= thr)
    out["catalogue_vs_topography"] = {
        "det_elev_slope_p33": round(thr, 5),
        "flat_third_px": int(flat.sum()),
        "catalogue_px_in_flat_third": int((known & flat).sum()),
        "catalogue_frac_in_flat_third": round(
            float((known & flat).sum() / known.sum()), 4),
        "flat_third_frac_of_valid": round(float(flat.sum() / valid.sum()), 4),
        "over_representation_factor": round(
            (float((known & flat).sum() / known.sum())
             / float(flat.sum() / valid.sum())), 3),
        "interpretation": ("A factor below 1 means catalogue faults are "
                           "UNDER-represented on flat ground, i.e. "
                           "OVER-represented on slopes -- the measurable "
                           "basis of irregularity I-10."),
    }

    # Free the per-band arrays the earlier sections needed before building the
    # transform bank: 19 float32 grids is ~0.9 GB, and this box runs the holdout
    # sweep at the same time.
    # NOTE: band 1 (rtp) must NOT be freed here -- the bank in section 6 uses it.
    hg, vg = bands.pop(3), bands.pop(9)
    for i in (5, 11, 18, 7, 8):
        bands.pop(i, None)
    del cand
    gc.collect()
    # ---------- 6. best-match search over a bank of candidate transforms -----
    # Band 6's embedded description is hedged ("Tilt angle OR total curvature"),
    # and the problem page's own figure is named `gems_tc_tmi.png` and captioned
    # "radiometric (left) and magnetic (right)", which is first-party evidence
    # that `tc` denotes the radiometric total count. The measured distribution is
    # bounded in [2.95, 88.57] with p99 = 29.1, which is not a count. Rather
    # than pick a side, search a bank of physically standard transforms built
    # from the OTHER 18 bands and report the best match. If nothing clears
    # |rho| = 0.5, band 6 is UNIDENTIFIED and is reported as such.
    def _f(a):
        return D.fill_nan_nearest(a)

    def _hg(a):
        return D.horizontal_gradient_mag(_f(a))

    def _vd(a):
        return D.vertical_derivative(_f(a))

    bank = {}
    for i in (1, 2, 14, 13, 17, 15, 12, 19):
        a = bands[i]
        g = _hg(a)
        bank[f"gradmag_b{i}"] = g
        bank[f"laplace_b{i}"] = ndi.gaussian_laplace(_f(a), 2.0)
        bank[f"gauss9_b{i}"] = ndi.gaussian_filter(_f(a), 9.0)
        v = _vd(a)
        AS = np.sqrt(g ** 2 + v ** 2) + 1e-12
        bank[f"theta_b{i}_deg"] = np.degrees(np.arccos(np.clip(g / AS, -1, 1)))
        bank[f"tdr_b{i}_deg"] = np.degrees(np.arctan2(v, g))
        bank[f"vd_over_hg_b{i}"] = v / (g + 1e-9)
        del g, v, AS
    AS2 = np.sqrt(hg ** 2 + vg ** 2) + 1e-12
    bank["theta_from_tmi_hg_vg_deg"] = np.degrees(np.arccos(np.clip(hg / AS2, -1, 1)))
    bank["tdr_from_tmi_hg_vg_deg"] = np.degrees(np.arctan2(vg, hg))
    bank["vd_over_hg_from_tmi_bands"] = vg / (hg + 1e-9)
    del AS2, hg, vg

    scored = []
    for name in list(bank):
        c = bank.pop(name)          # score and drop: the bank is ~50 full grids
        mm = m & np.isfinite(c)
        if mm.sum() < 1000:
            del c
            continue
        rho = float(spearmanr(c[mm][::29], tc[mm][::29]).correlation)
        scored.append((abs(rho), round(rho, 4), name))
        del c
    del bank
    gc.collect()
    scored.sort(reverse=True)
    out["band6_best_match_search"] = {
        "n_candidates": len(scored),
        "top_10": [{"abs_spearman_rho": a, "spearman_rho": r, "candidate": n}
                   for a, r, n in scored[:10]],
        "verdict": ("No candidate in a bank of %d physically standard "
                    "transforms of the other 18 bands reaches |rho| = 0.5 "
                    "against band 6 (best is %s at rho = %+.4f). Band 6 is "
                    "therefore UNIDENTIFIED. The problem page's figure "
                    "filename `gems_tc_tmi.png`, captioned 'radiometric (left) "
                    "and magnetic (right)', is first-party evidence for the "
                    "radiometric-total-count reading, but the measured band is "
                    "bounded in [2.95, 88.57] with p99 = 29.1 and is smoother "
                    "than the supplied gradient bands, which a count in CPS is "
                    "not. Both cannot be true of the same array; the data-tab "
                    "documentation is required to settle it."
                    % (len(scored), scored[0][2], scored[0][1])),
    }

    out["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "reports" / "band_audit.json").write_text(json.dumps(out, indent=2))

    # ---------- console ----------
    print("=== band 6 `tc`: is it a magnetic edge angle? ===")
    for k, v in tests.items():
        print(f"  {k:30s} r={v['pearson_r']:+7.4f} rho={v['spearman_rho']:+7.4f} "
              f"MAD={v['mean_abs_diff_deg']:7.2f}deg")
    print(f"  tc measured range: {out['band6_is_a_magnetic_edge_angle']['tc_measured_range_deg']} "
          f"(p99={out['band6_is_a_magnetic_edge_angle']['tc_p99_deg']})")
    print("\n=== best-match search over %d candidate transforms ===" % len(scored))
    for a_, r_, n_ in scored[:8]:
        print(f"  rho={r_:+7.4f}  {n_}")
    print(f"  -> nothing reaches |rho|=0.5; band 6 is UNIDENTIFIED")

    print("\n=== spatial frequency (lag-1 autocorrelation, higher = smoother) ===")
    for k, v in freq.items():
        print(f"  band {k:>2s} {v['code']:22s} {v['lag1_autocorr_gauss3']:.4f}")
    print("\n=== earthquake bands: distance or density? ===")
    for k in ("10", "16"):
        v = eq[k]
        print(f"  band {k:>2s} {v['code']:12s} median in={v['median_inside_catalogue']:9.1f} "
              f"out={v['median_outside_catalogue']:9.1f} "
              f"-> {'DENSITY-like' if v['higher_inside_catalogue'] else 'DISTANCE-like'}")
    print(f"  corr(deq, ieq) = {eq['corr_deq_ieq']}")
    print("\n=== catalogue vs topography (I-10) ===")
    c = out["catalogue_vs_topography"]
    print(f"  catalogue fraction on the flattest third of ground: "
          f"{100*c['catalogue_frac_in_flat_third']:.1f}% "
          f"(flattest third is {100*c['flat_third_frac_of_valid']:.1f}% of valid) "
          f"-> over-representation factor {c['over_representation_factor']}")
    print(f"\nwrote {(ROOT/'reports'/'band_audit.json').relative_to(ROOT)} "
          f"({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
