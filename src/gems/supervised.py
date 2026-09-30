"""H-S -- the first SUPERVISED detector in this repository.

Why this exists
---------------
Every detector built so far (`gems.detectors`, H-A..H-E, R6-1..R6-5,
R7-1..R7-5) is analytic and unsupervised: a hand-written physical transform
whose ranking is then thresholded. None of them learns from the catalogue at
all. The competition's own reference solution
(<https://github.com/drivendataorg/gems-prize-reference-solution>) trains a
U-Net, i.e. the intended approach is supervised.

This module is the cheap, CPU-only version of that: L2-regularised logistic
regression on multi-scale context features built from the 19 official bands.
It is deliberately *not* a deep network -- 3 GB of RAM and 2 cores rule that
out here -- but it is supervised, it uses all 19 bands at once, and it can be
trained per holdout fold on the VISIBLE catalogue only, which is the only way
to score it honestly.

Memory
------
The naive feature cube is (3730, 3292, 57) float32 = 2.8 GB, which does not fit.
Everything here is therefore computed in row blocks with a 4-row pad, so only
~150 MB of features is alive at any moment. The block boundaries are exact: the
9x9 mean needs 4 rows of context and each block carries 4, so only the raster's
own outer 4 rows touch the array boundary, exactly as a full-grid
`uniform_filter(mode="nearest")` would.

Leakage control
---------------
`fit_labelled` takes an explicit `allowed_mask` of pixels that may be used for
training. The holdout calls it with `visible & ~hidden_halo` and nothing else,
so the withheld segments are never used as training labels. The context
features are pixel-local (3x3 and 9x9 means), so a training pixel's 9x9
neighbourhood can overlap the withheld halo; the buffer is 5 px, so the overlap
is bounded and is disclosed here rather than hidden.

Features (57 total, all from the 19 official bands)
---------------------------------------------------
    f_0  .. f_18   the band value at the pixel
    f_19 .. f_37   3x3 mean  (150 m context)
    f_38 .. f_56   9x9 mean  (450 m context)

Standardised with training-set statistics only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

BAND_COUNT = 19
N_FEATURES = 3 * BAND_COUNT
_PAD = 4          # rows of context a block needs for the 9x9 mean
BLOCK_ROWS = 200  # ~150 MB of features per block


def features_block(bands: list[np.ndarray], y0: int, y1: int) -> np.ndarray:
    """(y1-y0, W, 57) float32 features for raster rows [y0, y1)."""
    H, W = bands[0].shape
    s0 = max(0, y0 - _PAD)
    s1 = min(H, y1 + _PAD)
    out = np.zeros((y1 - y0, W, N_FEATURES), dtype=np.float32)
    off = y0 - s0
    n = y1 - y0
    for i, a in enumerate(bands):
        x = np.where(np.isfinite(a[s0:s1]), a[s0:s1], 0.0).astype(np.float32)
        out[..., i] = x[off:off + n]
        out[..., BAND_COUNT + i] = ndi.uniform_filter(x, 3, mode="nearest")[off:off + n]
        out[..., 2 * BAND_COUNT + i] = ndi.uniform_filter(x, 9, mode="nearest")[off:off + n]
    return out


@dataclass
class LogisticModel:
    w: np.ndarray                 # (57,)
    b: float
    mu: np.ndarray                # (57,) training means
    sd: np.ndarray                # (57,) training stds
    n_train_pos: int
    n_train_neg: int

    def predict(self, bands: list[np.ndarray]) -> np.ndarray:
        """P(fault | features) as an (H, W) float32 map in [0, 1]."""
        H, W = bands[0].shape
        out = np.zeros((H, W), dtype=np.float32)
        for y0 in range(0, H, BLOCK_ROWS):
            y1 = min(H, y0 + BLOCK_ROWS)
            f = features_block(bands, y0, y1)
            z = (f.reshape(-1, N_FEATURES) - self.mu) / self.sd
            p = 1.0 / (1.0 + np.exp(-np.clip(z @ self.w + self.b, -30, 30)))
            out[y0:y1] = p.reshape(y1 - y0, W)
        return out


def fit_labelled(bands: list[np.ndarray], pos_mask: np.ndarray,
                 allowed_mask: np.ndarray, *, l2: float = 1e-3,
                 lr: float = 0.5, epochs: int = 40, batch: int = 65536,
                 pos_weight: float | None = None, seed: int = 0,
                 max_neg: int = 400_000) -> LogisticModel:
    """Train logistic regression on `pos_mask` pixels inside `allowed_mask`.

    Negatives are subsampled to `max_neg` so the design matrix stays ~210 MB
    (float64) on a 3 GB box. Optimiser is Adam on mini-batches, deterministic
    given `seed`.
    """
    rng = np.random.default_rng(seed)
    H, W = bands[0].shape
    pos_flat = (pos_mask & allowed_mask).ravel()
    neg_flat = (~pos_mask & allowed_mask).ravel()
    pos_idx = np.nonzero(pos_flat)[0]
    neg_idx = np.nonzero(neg_flat)[0]
    if neg_idx.size > max_neg:
        neg_idx = np.sort(rng.choice(neg_idx, max_neg, replace=False))
    idx = np.concatenate([pos_idx, neg_idx])
    order = np.argsort(idx, kind="stable")
    idx_sorted = idx[order]
    y = np.concatenate([np.ones(pos_idx.size, np.float64),
                        np.zeros(neg_idx.size, np.float64)])[order]

    X = np.zeros((idx_sorted.size, N_FEATURES), dtype=np.float64)
    filled = 0
    for y0 in range(0, H, BLOCK_ROWS):
        y1 = min(H, y0 + BLOCK_ROWS)
        lo = y0 * W
        hi = y1 * W
        a = np.searchsorted(idx_sorted, lo, "left")
        b = np.searchsorted(idx_sorted, hi, "right")
        if b <= a:
            continue
        f = features_block(bands, y0, y1).reshape(-1, N_FEATURES)
        X[a:b] = f[idx_sorted[a:b] - lo]
        filled += b - a
        del f
    assert filled == idx_sorted.size, (filled, idx_sorted.size)

    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-8] = 1.0
    X = (X - mu) / sd

    if pos_weight is None:
        pos_weight = float(neg_idx.size) / max(pos_idx.size, 1)
    sw = np.where(y > 0.5, pos_weight, 1.0)
    sw /= sw.mean()

    w = np.zeros(N_FEATURES)
    b = 0.0
    n = X.shape[0]
    mw = np.zeros_like(w); vw = np.zeros_like(w)
    mb = 0.0; vb = 0.0
    b1, b2, eps = 0.9, 0.999, 1e-8
    t = 0
    for _ in range(epochs):
        perm = rng.permutation(n)
        for s in range(0, n, batch):
            sel = perm[s:s + batch]
            xb = X[sel]; yb = y[sel]; wb = sw[sel]
            p = 1.0 / (1.0 + np.exp(-np.clip(xb @ w + b, -30, 30)))
            g = (p - yb) * wb
            gw = xb.T @ g / len(sel) + l2 * w
            gb = float(g.mean())
            t += 1
            mw = b1 * mw + (1 - b1) * gw
            vw = b2 * vw + (1 - b2) * (gw * gw)
            mb = b1 * mb + (1 - b1) * gb
            vb = b2 * vb + (1 - b2) * gb * gb
            w -= lr * (mw / (1 - b1 ** t)) / (np.sqrt(vw / (1 - b2 ** t)) + eps)
            b -= lr * (mb / (1 - b1 ** t)) / (np.sqrt(vb / (1 - b2 ** t)) + eps)
    return LogisticModel(w=w, b=float(b), mu=mu.astype(np.float32),
                         sd=sd.astype(np.float32),
                         n_train_pos=int(pos_idx.size),
                         n_train_neg=int(neg_idx.size))
