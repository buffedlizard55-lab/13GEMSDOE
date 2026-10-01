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


# ---------------------------------------------------------------------------
# R14/R15 `tip` rule -- predeclared in knowledge/10_r14_hypotheses.md §1
# ---------------------------------------------------------------------------
def trace_endpoints(known: np.ndarray) -> np.ndarray:
    """8-connected pixels of `known` with at most one known neighbour.

    The catalogue raster is one pixel wide almost everywhere, so this is the
    set of trace terminations -- the places where *mapping* stopped.
    """
    k = np.asarray(known, dtype=bool)
    n8 = ndi.convolve(k.astype(np.uint8), np.ones((3, 3), np.uint8),
                      mode="constant", cval=0) - k.astype(np.uint8)
    return k & (n8 <= 1)


def tip_fold(known: np.ndarray, valid: np.ndarray, tip_len: int,
             name: str, min_len: int = 20,
             seed_segments: np.ndarray | None = None) -> Fold:
    """Withhold the outermost `tip_len` px of every long trace as hidden truth.

    No `link_px` grouping is applied, so hidden truth lies IMMEDIATELY adjacent
    to visible catalogue. That is deliberate: `group_systems(link_px=8)` merges
    traces within ~1.6 km, which makes the pre-existing rules structurally
    blind to any near-catalogue strategy (knowledge/10 §0 F7, measured in
    reports/r14_budget_curve.json). The hidden pixels are chosen ONLY from
    catalogue geometry -- never from a feature value -- so no detector can be
    tuned on them.

    The growth is a geodesic ball inside `known`: because segments are
    8-connected components, dilating within `known` can never leave the
    component the seed belonged to.

    `seed_segments` restricts WHICH segment ids contribute tips. Everything
    else in the catalogue stays visible -- and therefore masked out of
    evaluation exactly as the organiser masks the known catalogue (F1) -- so
    the fold never leaves catalogue pixels unaccounted for.
    """
    known = np.asarray(known, dtype=bool)
    seg, n_seg = label_segments(known)
    sizes = np.asarray(ndi.sum_labels(known.astype(np.float32), seg,
                                      np.arange(1, n_seg + 1)))
    ok = sizes >= min_len if min_len > 0 else sizes >= 0
    eligible = np.flatnonzero(ok) + 1
    if seed_segments is not None:
        eligible = np.intersect1d(eligible, np.asarray(seed_segments))
    seeds = trace_endpoints(known) & np.isin(seg, eligible)

    st = ndi.generate_binary_structure(2, 2)
    hidden = seeds.copy()
    for _ in range(int(tip_len)):
        nxt = ndi.binary_dilation(hidden, structure=st) & known & ~hidden
        if not nxt.any():
            break
        hidden |= nxt

    visible = known & ~hidden
    return Fold(name=name, rule=f"tip{tip_len}", hidden=hidden, visible=visible,
                eval_mask=valid & ~visible,
                n_hidden=int(hidden.sum()), n_visible=int(visible.sum()),
                meta={"tip_len_px": int(tip_len), "min_segment_len_px": int(min_len),
                      "n_endpoints": int(seeds.sum()),
                      "n_segments_eligible": int(eligible.size),
                      "known_px_accounted": int((hidden | visible).sum()),
                      "hidden_adjacent_to_visible": True})


def tip_folds(known: np.ndarray, valid: np.ndarray,
              tip_lens=(8, 16, 32), seeds=(1, 2, 3),
              min_len: int = 20) -> list[Fold]:
    """Deterministic `tip` folds.

    The rule has no randomness in it (it is pure catalogue geometry), so the
    `seeds` argument only varies WHICH long segments contribute tips: seed 1
    uses every eligible segment, seed 2 every second segment id, seed 3 every
    third. Three distinct folds per tip length, no hidden tuning knob, and the
    non-selected catalogue stays visible (hence masked) in every fold.
    """
    out: list[Fold] = []
    known = np.asarray(known, dtype=bool)
    seg, n_seg = label_segments(known)
    sizes = np.asarray(ndi.sum_labels(known.astype(np.float32), seg,
                                      np.arange(1, n_seg + 1)))
    eligible = np.flatnonzero(sizes >= min_len) + 1 if min_len > 0 \
        else np.arange(1, n_seg + 1)
    for tl in tip_lens:
        for s in seeds:
            sel = eligible[(np.arange(eligible.size) % int(s)) == 0] if s > 1 else eligible
            f = tip_fold(known, valid, tl, f"tip{tl}_seed{s}",
                         min_len=min_len, seed_segments=sel)
            f.meta["segment_subsample"] = int(s)
            out.append(f)
    return out
