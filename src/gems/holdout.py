"""Construct local proxy folds by hiding parts of the known fault catalogue.

The competition target is expert-labelled new-fault truth, which is not
available for local validation. Withholding known catalogue traces therefore
tests one useful but incomplete question:

    "If a known fault system or raster segment were hidden, how well would the
     detector recover it using only the remaining visible catalogue?"

This is not a recreation of the undisclosed test distribution. Build folds by
withholding whole segments/systems with a buffer, rebuild catalogue-derived
features from the visible catalogue only, apply the pixel-exact visible-fault
mask, and score only the withheld truth. Report results across several rules and
keep all transfer-to-test claims explicitly tentative.

Withholding rules implemented (a candidate that wins under only one is fragile):
  random     - uniformly sampled systems
  short      - preferentially withhold short segments
  isolated   - preferentially withhold segments far from other faults
  oriented   - withhold one strike class (proxy for age/slip-rate strata,
               which need the INGENIOUS Quaternary Faults v2 attributes --
               see limitation L-2)
  dense      - preferentially withhold segments in high fault-density areas
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

PIXEL_M = 100.0


# ---------------------------------------------------------------------------
# Segmentation of the catalogue into segments and systems
# ---------------------------------------------------------------------------
def label_segments(known: np.ndarray) -> tuple[np.ndarray, int]:
    """8-connected components of the rasterised fault catalogue."""
    lab, n = ndi.label(known, structure=np.ones((3, 3), dtype=int))
    return lab.astype(np.int32), int(n)


def group_systems(known: np.ndarray, link_px: int = 8) -> tuple[np.ndarray, int]:
    """Group segments into 'systems' by dilating and re-labelling.

    Two segments whose traces come within `2*link_px` pixels (1.6 km by
    default) are treated as one system. Withholding by system prevents the
    detector from trivially interpolating across a gap it has already seen.
    """
    st = ndi.generate_binary_structure(2, 2)
    grown = ndi.binary_dilation(known, structure=st, iterations=link_px)
    lab, n = ndi.label(grown, structure=np.ones((3, 3), dtype=int))
    return np.where(known, lab, 0).astype(np.int32), int(n)


def segment_table(known: np.ndarray, seg: np.ndarray, n_seg: int) -> dict:
    """Per-segment morphology used by the stratified withholding rules."""
    idx = np.arange(1, n_seg + 1)
    sizes = np.asarray(ndi.sum_labels(known.astype(np.float32), seg, idx))
    objs = ndi.find_objects(seg)

    strike = np.zeros(n_seg)
    extent = np.zeros(n_seg)
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        ys, xs = np.nonzero(seg[sl] == i + 1)
        if ys.size < 2:
            strike[i] = np.nan
            extent[i] = 1.0
            continue
        ys = ys.astype(np.float64); xs = xs.astype(np.float64)
        ys -= ys.mean(); xs -= xs.mean()
        cov = np.array([[np.dot(xs, xs), np.dot(xs, ys)],
                        [np.dot(xs, ys), np.dot(ys, ys)]]) / ys.size
        w, v = np.linalg.eigh(cov)
        major = v[:, -1]
        # map to compass azimuth: x=east, y=south (raster rows increase south)
        strike[i] = np.degrees(np.arctan2(major[0], -major[1])) % 180.0
        extent[i] = 2.0 * np.sqrt(max(w[-1], 0.0))

    # isolation: distance from each segment to the nearest *other* fault pixel
    dist_all = ndi.distance_transform_edt(~known)
    isolation = np.zeros(n_seg)
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        m = seg[sl] == i + 1
        sub = np.ones_like(m)
        # distance to nearest fault pixel that is NOT this segment
        other = known.copy()
        ys0, xs0 = sl[0].start, sl[1].start
        other[sl][m] = False
        # cheap proxy: expand a window around the segment
        pad = 120
        y0 = max(0, ys0 - pad); y1 = min(known.shape[0], sl[0].stop + pad)
        x0 = max(0, xs0 - pad); x1 = min(known.shape[1], sl[1].stop + pad)
        win = other[y0:y1, x0:x1]
        if win.any():
            d = ndi.distance_transform_edt(~win)
            mm = np.zeros_like(win)
            mm[ys0 - y0:sl[0].stop - y0, xs0 - x0:sl[1].stop - x0] = m
            isolation[i] = float(d[mm].min()) if mm.any() else pad
        else:
            isolation[i] = float(pad)
        del other

    del dist_all
    return {"id": idx, "size_px": sizes, "strike_deg": strike,
            "extent_px": extent, "isolation_px": isolation}


# ---------------------------------------------------------------------------
@dataclass
class Fold:
    name: str
    rule: str
    hidden: np.ndarray          # bool, the withheld "new fault" ground truth
    visible: np.ndarray         # bool, catalogue the model may use / is masked
    eval_mask: np.ndarray       # bool, pixels that may contribute FP_w
    n_hidden: int = 0
    n_visible: int = 0
    meta: dict = field(default_factory=dict)


def make_fold(known: np.ndarray, valid: np.ndarray, hide_ids: np.ndarray,
              seg: np.ndarray, name: str, rule: str,
              buffer_px: int = 5) -> Fold:
    """Build one hide-and-recover fold.

    buffer_px : visible catalogue pixels within this distance of a withheld
        segment are ALSO removed from the visible set. Without this the model
        sees the withheld structure's immediate continuation and the holdout
        becomes optimistic.
    """
    hidden = np.isin(seg, hide_ids) & known
    st = ndi.generate_binary_structure(2, 2)
    halo = ndi.binary_dilation(hidden, structure=st, iterations=buffer_px)
    visible = known & ~hidden & ~halo

    # Scoring mirrors the organizers exactly: the *visible* catalogue is the
    # "known fault" set, so it is masked pixel-exactly (forum 11516 post 4).
    # Everything else inside the footprint can accrue FP_w -- including the
    # 1-3 px halo around visible traces, which the organizers confirmed is
    # fully penalized.
    eval_mask = valid & ~visible

    return Fold(name=name, rule=rule, hidden=hidden, visible=visible,
                eval_mask=eval_mask, n_hidden=int(hidden.sum()),
                n_visible=int(visible.sum()),
                meta={"buffer_px": buffer_px,
                      "n_hidden_segments": int(len(hide_ids))})


def build_folds(known: np.ndarray, valid: np.ndarray, *, n_folds: int = 3,
                hide_frac: float = 0.25, seed: int = 20260928,
                link_px: int = 8, buffer_px: int = 5) -> list[Fold]:
    """All withholding rules x n_folds."""
    seg, n_seg = group_systems(known, link_px=link_px)
    tab = segment_table(known, seg, n_seg)
    rng = np.random.default_rng(seed)

    ids = tab["id"]
    size = tab["size_px"]
    total = size.sum()
    target = hide_frac * total

    def pick(order: np.ndarray) -> np.ndarray:
        """Take systems in the given order until `target` pixels are hidden."""
        cum = np.cumsum(size[order])
        k = int(np.searchsorted(cum, target)) + 1
        return ids[order[:k]]

    folds: list[Fold] = []
    for f in range(n_folds):
        perm = rng.permutation(n_seg)
        folds.append(make_fold(known, valid, pick(perm), seg,
                               f"random_{f}", "random", buffer_px))

    # short: smallest segments first (jittered so folds differ)
    for f in range(n_folds):
        key = size + rng.normal(0, 0.15 * size.std(), n_seg)
        folds.append(make_fold(known, valid, pick(np.argsort(key)), seg,
                               f"short_{f}", "short", buffer_px))

    # isolated: most isolated first
    iso = tab["isolation_px"]
    for f in range(n_folds):
        key = -(iso + rng.normal(0, 0.15 * (iso.std() + 1e-6), n_seg))
        folds.append(make_fold(known, valid, pick(np.argsort(key)), seg,
                               f"isolated_{f}", "isolated", buffer_px))

    # oriented: withhold by strike class (proxy stratum for age/slip-rate)
    strike = np.nan_to_num(tab["strike_deg"], nan=0.0)
    for f, (lo, hi) in enumerate([(0, 60), (60, 120), (120, 180)][:n_folds]):
        sel = ids[(strike >= lo) & (strike < hi)]
        if sel.size == 0:
            continue
        folds.append(make_fold(known, valid, sel, seg,
                               f"strike_{lo}_{hi}", "oriented", buffer_px))

    # dense: segments in the highest local fault density
    dens = ndi.uniform_filter(known.astype(np.float32), size=101)
    seg_dens = np.asarray(ndi.mean(dens, seg, ids))
    for f in range(n_folds):
        key = -(seg_dens + rng.normal(0, 0.15 * (seg_dens.std() + 1e-9), n_seg))
        folds.append(make_fold(known, valid, pick(np.argsort(key)), seg,
                               f"dense_{f}", "dense", buffer_px))

    return folds
