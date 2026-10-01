"""R14 catalogue-geometry propagation operators.

Two new operators, predeclared in ``knowledge/10_r14_hypotheses.md`` (H-R14-1)
and the control for it (§4 P2).  Both emit mass ONLY off-catalogue, because the
organiser masks known-fault pixels out of evaluation entirely (forum 11516
post 2), so mass on the catalogue is worth exactly zero.

Nothing in this module reads a feature band.  Both operators are pure functions
of the visible catalogue geometry, which is the point: they test whether
*geometry* carries information the repo's magnitude-ranked geophysical
detectors do not (measured in reports/r14_budget_curve.json -- they do not).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

S8 = ndi.generate_binary_structure(2, 2)


def trace_endpoints(visible: np.ndarray) -> np.ndarray:
    """Pixels of `visible` with at most one visible 8-neighbour."""
    k = np.asarray(visible, dtype=bool)
    n8 = ndi.convolve(k.astype(np.uint8), np.ones((3, 3), np.uint8),
                      mode="constant", cval=0) - k.astype(np.uint8)
    return k & (n8 <= 1)


def local_strike(visible: np.ndarray, endpoints: np.ndarray,
                 radius: int = 4) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-endpoint outward unit direction, from PCA of the local trace.

    Returns (rows, cols, dir) where `dir` is an (n, 2) array of [dy, dx] unit
    vectors pointing AWAY from the trace body (the sign is fixed by requiring
    the local visible centroid to lie on the opposite side, so the ribbon
    extends the trace rather than doubling back along it).

    Rows are in raster convention: +y is SOUTH (row index increases), +x is
    EAST.  That matches the grid's affine (100, 0, west, 0, -100, north).
    """
    vis = np.asarray(visible, dtype=bool)
    ys, xs = np.nonzero(endpoints)
    if ys.size == 0:
        return ys, xs, np.zeros((0, 2))
    H, W = vis.shape
    r = int(radius)
    dirs = np.zeros((ys.size, 2), np.float64)
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    win = (yy * yy + xx * xx) <= r * r
    for i in range(ys.size):
        y0, x0 = ys[i] - r, xs[i] - r
        y1, x1 = ys[i] + r + 1, xs[i] + r + 1
        sy0, sx0 = max(0, y0), max(0, x0)
        sy1, sx1 = min(H, y1), min(W, x1)
        sub = vis[sy0:sy1, sx0:sx1]
        w = win[sy0 - y0:sub.shape[0] + (sy0 - y0), sx0 - x0:sub.shape[1] + (sx0 - x0)]
        py, px = np.nonzero(sub & w)
        if py.size < 3:
            dirs[i] = (0.0, 1.0)      # degenerate: fall back to due east
            continue
        py = py.astype(np.float64) - (ys[i] - sy0)
        px = px.astype(np.float64) - (xs[i] - sx0)
        cov = np.array([[np.dot(px, px), np.dot(px, py)],
                        [np.dot(px, py), np.dot(py, py)]]) / py.size
        evals, evecs = np.linalg.eigh(cov)
        v = evecs[:, -1]                       # [x, y] principal direction
        centroid = np.array([px.mean(), py.mean()])
        if np.dot(v, centroid) > 0:            # point AWAY from the trace body
            v = -v
        n = np.hypot(v[0], v[1]) or 1.0
        dirs[i] = (v[1] / n, v[0] / n)         # -> [dy, dx]
    return ys, xs, dirs


#: perpendicular Gaussian splat, sigma = 1 px, normalised to peak 1.0
def _perp_kernel(sigma: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    o = np.arange(-2, 3)
    g = np.exp(-0.5 * (o / sigma) ** 2)
    return o, g


def along_strike_tips(visible: np.ndarray, length_px: int = 10,
                      sigma: float = 1.0, taper: str = "linear",
                      radius: int = 4) -> np.ndarray:
    """H-R14-1: extend every visible trace tip along its own local strike.

    For each endpoint, walk `length_px` pixels along the outward principal
    direction of the local trace and splat a perpendicular Gaussian of width
    `sigma`.  Amplitude tapers to zero at the end of the walk.

    The output is a float32 *intensity* field, un-normalised; callers rank it
    and take a budget.  It is exactly zero on the visible catalogue and on
    every pixel not reached by some tip ribbon.
    """
    vis = np.asarray(visible, dtype=bool)
    eps = trace_endpoints(vis)
    ys, xs, dirs = local_strike(vis, eps, radius=radius)
    out = np.zeros(vis.shape, np.float32)
    if ys.size == 0:
        return out
    o, g = _perp_kernel(sigma)
    L = int(length_px)
    H, W = vis.shape
    for t in range(1, L + 1):
        amp = (1.0 - t / (L + 1.0)) if taper == "linear" else np.exp(-t / (L / 2.0))
        cy = np.round(ys + t * dirs[:, 0]).astype(np.int64)
        cx = np.round(xs + t * dirs[:, 1]).astype(np.int64)
        # perpendicular unit vector
        px_, py_ = -dirs[:, 1], dirs[:, 0]
        for k, gw in zip(o, g):
            ry = np.round(cy + k * py_).astype(np.int64)
            rx = np.round(cx + k * px_).astype(np.int64)
            good = (ry >= 0) & (ry < H) & (rx >= 0) & (rx < W)
            np.add.at(out, (ry[good], rx[good]),
                      np.float32(amp * gw))
    # never emit onto the visible catalogue: those pixels are masked anyway
    out[vis] = 0.0
    return out


def isotropic_halo(visible: np.ndarray) -> np.ndarray:
    """Control for H-R14-1 (register §4 P2): proximity WITHOUT direction.

    Intensity = 1 / (1 + Euclidean distance to the visible catalogue), zero on
    the catalogue itself.  Ranking this and taking a budget gives the same
    pixel budget as `along_strike_tips` but with no directional information, so
    comparing the two isolates the contribution of the strike vector.
    """
    vis = np.asarray(visible, dtype=bool)
    d = ndi.distance_transform_edt(~vis).astype(np.float32)
    out = 1.0 / (1.0 + d)
    out[vis] = 0.0
    return out.astype(np.float32)


def square_lattice(shape: tuple[int, int], stride: int) -> np.ndarray:
    """The shipped reference: a fault-blind lattice of points."""
    m = np.zeros(shape, bool)
    m[::int(stride), ::int(stride)] = True
    return m


def budget_from_intensity(intensity: np.ndarray, allowed: np.ndarray,
                          n_pixels: int,
                          jitter: np.ndarray | None = None) -> np.ndarray:
    """Top-`n_pixels` of `intensity` restricted to `allowed`, as a float32 map.

    TIE-BREAKING IS THE WHOLE POINT OF THE `jitter` ARGUMENT.  Intensity fields
    built from a distance transform or from a small set of ribbon amplitudes are
    massively tied: the 1-px ring around a 60,988-px catalogue holds roughly
    200,000 pixels that all have the SAME score.  A bare `argpartition` breaks
    those ties by flat index, i.e. **row-major position**, so the selected set
    is the northernmost slice of the region rather than a spatially uniform
    sample of the ring.  That is irregularity I-14, and it silently destroyed
    the first run of this experiment (the isotropic-halo control measured
    DTI 0.039 when a position-unbiased version of the same map is much better).

    With `jitter` supplied (a fixed, seeded, spatially uniform [0, 1) field),
    ties are broken uniformly at random while genuinely different intensities
    keep their order: the jitter is scaled to 1e-7 of the field's own range.
    Without it, ties fall back to flat index and the result is reported as
    position-dependent.

    The result is 1.0 on the selected pixels, 0.0 elsewhere.
    """
    a = np.asarray(intensity, dtype=np.float64).ravel()
    mask = np.asarray(allowed, dtype=bool).ravel()
    key = np.where(mask, a, -np.inf)
    finite = key[np.isfinite(key)]
    n = int(min(max(n_pixels, 0), int(mask.sum())))
    out = np.zeros(a.size, np.float32)
    if n == 0:
        return out.reshape(np.asarray(allowed).shape)
    if n >= int(mask.sum()):
        out[mask] = 1.0
        return out.reshape(np.asarray(allowed).shape)
    if jitter is not None:
        span = float(finite.max() - finite.min()) if finite.size else 1.0
        scale = (span if span > 0 else 1.0) * 1e-7
        key = key + np.where(mask, np.asarray(jitter, dtype=np.float64).ravel() * scale, 0.0)
    part = np.argpartition(-key, n - 1)[:n]
    out[part] = 1.0
    return out.reshape(np.asarray(allowed).shape)


def tie_fraction(intensity: np.ndarray, allowed: np.ndarray) -> float:
    """Fraction of `allowed` pixels sitting on the field's single largest tie.

    Reported alongside every budget selection so the I-14 pathology can never
    hide again: a value near 1 means the ranking carries almost no information
    beyond "in the mask or not".
    """
    a = np.asarray(intensity, dtype=np.float64).ravel()[np.asarray(allowed, bool).ravel()]
    if a.size == 0:
        return 0.0
    vals, counts = np.unique(a, return_counts=True)
    return float(counts.max() / a.size)


def make_jitter(shape: tuple[int, int], seed: int = 20261001) -> np.ndarray:
    """The fixed, seeded, spatially uniform tie-break field."""
    return np.random.default_rng(seed).random(shape, dtype=np.float64)



def prioritised_union(primary_sel: np.ndarray, filler: np.ndarray,
                      allowed: np.ndarray, total_budget: int,
                      jitter: np.ndarray | None = None) -> np.ndarray:
    """`primary_sel` first, then as much of `filler` as the budget allows.

    A coverage floor under a geological prior: the total predicted area is fixed
    (so the FP term is controlled), the geologically motivated pixels are never
    displaced by coverage pixels, and whatever budget is left buys the
    recall that beta = 0.8 pays four times what it charges for a false alarm.

    Filler pixels are chosen with the same uniform tie-break as
    `budget_from_intensity`, never by row-major position (I-14).
    """
    allowed = np.asarray(allowed, dtype=bool)
    sel = np.asarray(primary_sel, dtype=bool) & allowed
    out = sel.astype(np.float32)
    need = int(total_budget) - int(sel.sum())
    if need <= 0:
        return out
    pool = np.asarray(filler, dtype=bool) & allowed & ~sel
    n_pool = int(pool.sum())
    if n_pool == 0:
        return out
    if need >= n_pool:
        out[pool] = 1.0
        return out
    key = pool.astype(np.float64)
    if jitter is not None:
        key = key + np.asarray(jitter, dtype=np.float64) * 1e-7
    flat_pool = np.flatnonzero(pool.ravel())
    k = flat_pool[np.argpartition(-key.ravel()[flat_pool], need - 1)[:need]]
    o = np.zeros(key.size, np.float32).ravel()
    o[k] = 1.0
    out += o.reshape(out.shape)
    return np.clip(out, 0.0, 1.0).astype(np.float32)
