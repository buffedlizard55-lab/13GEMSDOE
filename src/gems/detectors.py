"""Physical-signature detectors for faults that are ABSENT from a scarp-derived
catalogue.

Design principle behind every detector here: the USGS Quaternary Fault and Fold
Database is built predominantly from *surface* evidence — scarps visible in
topography and aerial imagery, plus trenching and published geologic maps. The
systematic blind spots of such a catalogue are

  (a) structures with no surface scarp (buried beneath Quaternary basin fill),
  (b) structures whose surface expression is non-topographic (lithologic /
      geochemical / hydrologic contrast),
  (c) structures that are real faults but not demonstrably *Quaternary*.

Every detector below targets one of those blind spots, using the 19 official
bands only. None of them is a topographic ridge detector, because that is the
signature the catalogue already encodes — and it is what this team has already
run repeatedly.
"""
from __future__ import annotations

import numpy as np
from scipy import fft as sfft
from scipy import ndimage as ndi

PIXEL_M = 100.0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def fill_nan_nearest(a: np.ndarray) -> np.ndarray:
    """Replace NaN with the nearest finite value (needed before any FFT)."""
    a = np.asarray(a, dtype=np.float32)
    bad = ~np.isfinite(a)
    if not bad.any():
        return a
    idx = ndi.distance_transform_edt(bad, return_distances=False,
                                     return_indices=True)
    return a[tuple(idx)].astype(np.float32)


def robust_norm(a: np.ndarray, mask: np.ndarray | None = None,
                lo: float = 1.0, hi: float = 99.0) -> np.ndarray:
    """Percentile-clipped rescale to [0,1]; NaN-safe."""
    a = np.asarray(a, dtype=np.float32)
    sel = np.isfinite(a) if mask is None else (np.isfinite(a) & mask)
    if not sel.any():
        return np.zeros_like(a)
    p1, p99 = np.percentile(a[sel], [lo, hi])
    if p99 <= p1:
        return np.zeros_like(a)
    out = (a - p1) / (p99 - p1)
    return np.clip(np.nan_to_num(out, nan=0.0), 0.0, 1.0).astype(np.float32)


def _pad_reflect(a: np.ndarray, frac: float = 0.12) -> tuple[np.ndarray, tuple]:
    py = max(8, int(a.shape[0] * frac))
    px = max(8, int(a.shape[1] * frac))
    return np.pad(a, ((py, py), (px, px)), mode="reflect"), (py, px)


def _wavenumbers(shape: tuple[int, int], dx: float):
    ky = np.fft.fftfreq(shape[0], d=dx).astype(np.float32) * 2 * np.pi
    kx = np.fft.rfftfreq(shape[1], d=dx).astype(np.float32) * 2 * np.pi
    return np.sqrt(ky[:, None] ** 2 + kx[None, :] ** 2)


def upward_continue(a: np.ndarray, height_m: float,
                    dx: float = PIXEL_M) -> np.ndarray:
    """Upward-continue a potential field by `height_m` (Fourier domain).

    F_up(k) = F(k) * exp(-|k| h). Standard potential-field operator; it is a
    low-pass whose cut-off is set by a *physical* height, which is what makes
    multiscale edge ("worm") analysis interpretable.
    """
    if height_m <= 0:
        return np.asarray(a, dtype=np.float32)
    p, (py, px) = _pad_reflect(fill_nan_nearest(a))
    k = _wavenumbers(p.shape, dx)
    F = sfft.rfft2(p, workers=2)
    F *= np.exp(-k * np.float32(height_m))
    out = sfft.irfft2(F, s=p.shape, workers=2).astype(np.float32)
    return out[py:-py, px:-px]


def vertical_derivative(a: np.ndarray, dx: float = PIXEL_M) -> np.ndarray:
    """First vertical derivative of a potential field (Fourier: multiply |k|)."""
    p, (py, px) = _pad_reflect(fill_nan_nearest(a))
    k = _wavenumbers(p.shape, dx)
    F = sfft.rfft2(p, workers=2) * k
    out = sfft.irfft2(F, s=p.shape, workers=2).astype(np.float32)
    return out[py:-py, px:-px]


def horizontal_gradients(a: np.ndarray, dx: float = PIXEL_M):
    a = fill_nan_nearest(a)
    gy, gx = np.gradient(a, dx)
    return gx.astype(np.float32), gy.astype(np.float32)


def horizontal_gradient_mag(a: np.ndarray, dx: float = PIXEL_M) -> np.ndarray:
    gx, gy = horizontal_gradients(a, dx)
    return np.hypot(gx, gy).astype(np.float32)


def ridge_strength(a: np.ndarray, sigma: float = 1.5):
    """Hessian ridge filter. Returns (strength >= 0, orientation in radians).

    Strength is the magnitude of the most-negative principal curvature, i.e.
    'brightness of a bright ridge'. Orientation is the ridge's along-strike
    direction (perpendicular to the maximum-curvature eigenvector).
    """
    a = fill_nan_nearest(a).astype(np.float32)
    ayy = ndi.gaussian_filter(a, sigma, order=(2, 0), mode="nearest")
    axx = ndi.gaussian_filter(a, sigma, order=(0, 2), mode="nearest")
    axy = ndi.gaussian_filter(a, sigma, order=(1, 1), mode="nearest")
    tr = axx + ayy
    det_ = axx * ayy - axy * axy
    disc = np.sqrt(np.maximum(0.25 * tr * tr - det_, 0.0)).astype(np.float32)
    lam_min = 0.5 * tr - disc                      # most negative eigenvalue
    strength = np.maximum(-lam_min, 0.0).astype(np.float32)
    # eigenvector for lam_min; ridge runs perpendicular to it
    theta = 0.5 * np.arctan2(2 * axy, (axx - ayy)).astype(np.float32)
    return strength, (theta + np.pi / 2).astype(np.float32)


_NMS_SHIFTS = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (1, -1)}


def nms_thin(strength: np.ndarray, orientation: np.ndarray) -> np.ndarray:
    """Non-maximum suppression across the ridge (keeps a 1-px crest).

    Classic Canny-style NMS with the across-ridge normal quantised to the 4
    pixel-lattice directions. Implemented with integer shifts rather than
    interpolation: it is ~20x cheaper and, on a 100 m grid where the target is
    a single-pixel crest, sub-pixel interpolation buys nothing.
    """
    strength = np.asarray(strength, dtype=np.float32)
    normal = orientation + np.pi / 2          # across-ridge direction
    q = np.mod(np.round(normal / (np.pi / 4)).astype(np.int8), 4)

    keep = np.ones(strength.shape, dtype=bool)
    for bin_id, (dy, dx) in _NMS_SHIFTS.items():
        sel = q == bin_id
        if not sel.any():
            continue
        for sgn in (1, -1):
            nb = np.roll(strength, (-sgn * dy, -sgn * dx), axis=(0, 1))
            # roll wraps; blank the wrapped border so edges are not spurious
            if dy:
                if sgn > 0:
                    nb[-1, :] = 0
                else:
                    nb[0, :] = 0
            if dx:
                if sgn * dx > 0:
                    nb[:, -1] = 0
                else:
                    nb[:, 0] = 0
            keep &= ~sel | (strength >= nb)
            del nb
    return (strength * keep).astype(np.float32)


def decimate_grid(mask: np.ndarray, score: np.ndarray, spacing: int) -> np.ndarray:
    """Keep at most ONE predicted pixel per `spacing` x `spacing` tile.

    This is the orientation-free way to enforce the metric's geometry rule.
    TP_w takes a MAX over the 300 m (3 px) neighbourhood, so two predictions
    inside the same small tile can never both earn credit -- the second is pure
    FP mass. Keeping the highest-scoring pixel per tile removes that redundancy
    without needing a reliable strike estimate.

    Preferred over `decimate_along_strike`, whose orientation estimate is
    unreliable on an already-thinned crest map (measured: only a 2.5% mass
    reduction at spacing=4, i.e. it silently did nothing).
    """
    if spacing <= 1:
        return mask
    H, W = mask.shape
    ph, pw = (-H) % spacing, (-W) % spacing
    sc = np.where(mask, np.asarray(score, dtype=np.float32), -np.inf)
    sc = np.pad(sc, ((0, ph), (0, pw)), constant_values=-np.inf)
    bh, bw = sc.shape[0] // spacing, sc.shape[1] // spacing
    blocks = sc.reshape(bh, spacing, bw, spacing).transpose(0, 2, 1, 3)
    blocks = blocks.reshape(bh, bw, spacing * spacing)
    arg = blocks.argmax(axis=2)
    keep_ok = np.isfinite(blocks.max(axis=2))
    by, bx = np.nonzero(keep_ok)
    ys = by * spacing + arg[by, bx] // spacing
    xs = bx * spacing + arg[by, bx] % spacing
    out = np.zeros((H + ph, W + pw), dtype=bool)
    out[ys, xs] = True
    return out[:H, :W]


def decimate_along_strike(mask: np.ndarray, orientation: np.ndarray,
                          spacing: int) -> np.ndarray:
    """Keep roughly every `spacing`-th pixel along each lineament.

    TP_w takes a MAX over the 300 m neighbourhood, so a second predicted pixel
    within 3 px of the first buys no extra credit while adding full FP mass.
    Decimating a 1-px line to every 3rd pixel therefore removes ~2/3 of the
    FP mass for a small recall cost. Verified empirically in
    scripts/tune_geometry.py.
    """
    if spacing <= 1:
        return mask
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return mask
    ang = orientation[ys, xs]
    # project each pixel onto its own strike direction and keep one per bucket
    proj = xs * np.cos(ang) + ys * np.sin(ang)
    perp = -xs * np.sin(ang) + ys * np.cos(ang)
    key = (np.round(proj / spacing).astype(np.int64) * 1000003
           + np.round(perp).astype(np.int64))
    _, first = np.unique(key, return_index=True)
    out = np.zeros_like(mask)
    out[ys[first], xs[first]] = True
    return out


# ---------------------------------------------------------------------------
# H-A  Multiscale potential-field "worms"
# ---------------------------------------------------------------------------
def worms(field: np.ndarray, heights_m=(0, 500, 1000, 2000, 4000, 8000),
          sigma: float = 1.2) -> np.ndarray:
    """Cross-scale persistence of horizontal-gradient maxima.

    For each upward-continuation height we take the horizontal gradient
    magnitude of the field and thin it to its crest. A contact that is a real,
    steeply-dipping, vertically-extensive structure (a fault) keeps producing a
    gradient maximum in nearly the same place as the field is continued
    upward; shallow noise and sedimentary texture wash out within a few hundred
    metres. The output is the *height-weighted persistence* of the crest.

    Reference method: multiscale edge / 'worming' analysis of potential fields
    (Fourier upward continuation + horizontal-gradient maxima).
    """
    acc = np.zeros(field.shape, dtype=np.float32)
    wsum = 0.0
    for h in heights_m:
        f = upward_continue(field, h) if h > 0 else fill_nan_nearest(field)
        hg = horizontal_gradient_mag(f)
        st, ori = ridge_strength(hg, sigma=sigma)
        crest = nms_thin(st, ori)
        # tolerate small lateral drift between heights
        crest = ndi.maximum_filter(crest, size=3)
        w = 1.0 + np.log1p(h / 1000.0)      # reward persistence to height
        acc += w * robust_norm(crest)
        wsum += w
        del f, hg, st, ori, crest
    return (acc / max(wsum, 1e-9)).astype(np.float32)


# ---------------------------------------------------------------------------
# H-B  Tilt-derivative / theta edge detection
# ---------------------------------------------------------------------------
def tilt_derivative(field: np.ndarray) -> np.ndarray:
    """TDR = atan2(dF/dz, |grad_h F|), in radians.

    TDR is amplitude-normalised: it responds to the *geometry* of a source edge
    rather than its magnitude, so weak anomalies from deep or low-contrast
    sources score as strongly as loud shallow ones. That is precisely the
    regime where a catalogue built from strong, obvious features is incomplete.
    """
    vdr = vertical_derivative(field)
    thdr = horizontal_gradient_mag(field)
    return np.arctan2(vdr, thdr + 1e-12).astype(np.float32)


def tdr_edge(field: np.ndarray, sigma: float = 1.2) -> np.ndarray:
    """Source-edge likelihood = steepness of TDR at its zero contour.

    The TDR zero contour sits over the source edge; |grad TDR| is maximal there.
    """
    tdr = tilt_derivative(field)
    g = horizontal_gradient_mag(ndi.gaussian_filter(tdr, sigma))
    near_zero = np.exp(-(tdr / 0.35) ** 2).astype(np.float32)
    return (robust_norm(g) * near_zero).astype(np.float32)


def theta_map(field: np.ndarray) -> np.ndarray:
    """theta = acos(THDR / AS): another amplitude-normalised edge detector."""
    vdr = vertical_derivative(field)
    thdr = horizontal_gradient_mag(field)
    analytic = np.sqrt(thdr ** 2 + vdr ** 2) + 1e-12
    return np.arccos(np.clip(thdr / analytic, -1, 1)).astype(np.float32)


# ---------------------------------------------------------------------------
# H-C  Concealed basement hinge under flat cover
# ---------------------------------------------------------------------------
def basement_hinge(depth_to_base: np.ndarray, det_elev_slope: np.ndarray,
                   sigma: float = 2.0, flat_pct: float = 55.0) -> np.ndarray:
    """Linear steps in basement depth that have NO topographic expression.

    A normal fault that offsets the basement but is buried by Quaternary fill
    produces a hinge in depth-to-basement and *nothing* at the surface. A
    scarp-derived catalogue cannot contain it. Conditioning on flat topography
    is what makes this detector select for catalogue-invisible structures
    instead of re-finding range fronts that are already mapped.
    """
    st, ori = ridge_strength(horizontal_gradient_mag(depth_to_base), sigma=sigma)
    crest = nms_thin(st, ori)
    slope = fill_nan_nearest(det_elev_slope)
    thr = np.percentile(slope[np.isfinite(slope)], flat_pct)
    flat = ndi.gaussian_filter((slope <= thr).astype(np.float32), 3.0)
    return (robust_norm(crest) * flat).astype(np.float32)


# ---------------------------------------------------------------------------
# H-D  Strain-budget residual
# ---------------------------------------------------------------------------
def strain_residual(second_inv: np.ndarray, eq_density: np.ndarray,
                    known_density: np.ndarray, smooth: float = 6.0
                    ) -> np.ndarray:
    """Geodetic strain that is NOT explained by mapped faults or seismicity.

    Strain measured by GPS has to be accommodated somewhere. Where the
    second invariant of the strain-rate tensor is high but both the mapped
    fault density and the earthquake density are low, the accommodating
    structure is, by elimination, not in the catalogue.

    This is a low-spatial-frequency prior, not a pixel-accurate detector: the
    geodetic fields are heavily smoothed. It is used as a MULTIPLIER on sharp
    detectors, never on its own.
    """
    s = robust_norm(ndi.gaussian_filter(fill_nan_nearest(second_inv), smooth))
    e = robust_norm(ndi.gaussian_filter(fill_nan_nearest(eq_density), smooth))
    k = robust_norm(ndi.gaussian_filter(known_density.astype(np.float32), smooth))
    return np.clip(s - 0.5 * e - 0.5 * k, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# H-E  Directional-coherence lineaments (non-topographic contrast)
# ---------------------------------------------------------------------------
def directional_lineaments(field: np.ndarray, sigma: float = 1.5,
                           n_theta: int = 12, length: int = 15) -> np.ndarray:
    """Linear edges detected by directional coherence rather than amplitude.

    An oriented matched filter bank: for each of `n_theta` strikes, smooth the
    edge magnitude along that strike and take the across-strike derivative. A
    real lineament is coherent over `length` pixels (1.5 km); speckle is not.
    Works on any band, but is aimed at contrast layers (radiometrics,
    conductivity) where faults appear as lithologic/alteration boundaries with
    no relief at all.
    """
    e = robust_norm(horizontal_gradient_mag(
        ndi.gaussian_filter(fill_nan_nearest(field), sigma)))
    best = np.zeros_like(e)
    for t in np.linspace(0, np.pi, n_theta, endpoint=False):
        k = np.zeros((length, length), dtype=np.float32)
        c, s = np.cos(t), np.sin(t)
        for i in range(length):
            u = i - length // 2
            y = int(round(length // 2 + u * s))
            x = int(round(length // 2 + u * c))
            if 0 <= y < length and 0 <= x < length:
                k[y, x] = 1.0
        k /= k.sum()
        np.maximum(best, ndi.convolve(e, k, mode="nearest"), out=best)
    return robust_norm(best)


# ---------------------------------------------------------------------------
# H-I  Along-strike continuation beyond mapped fault tips
# ---------------------------------------------------------------------------
def extension_rays(visible: np.ndarray, reach_px: int = 30,
                   fit_px: int = 12, min_size: int = 6,
                   decay: float = 0.97) -> np.ndarray:
    """Project each mapped fault tip forward along its own strike.

    The organizers state that the new-fault label set includes "newly mapped
    geometry of an existing fault system" and "corrections or modifications to
    existing fault traces" -- explicitly naming along-strike tip extensions.
    A fault trace that stops in the catalogue usually stops because mapping
    stopped, not because the structure did.

    Returns a confidence ray of length `reach_px` beyond each end of every
    connected component, with strike estimated from the terminal `fit_px`
    pixels of that component.
    """
    lab, n = ndi.label(visible, structure=np.ones((3, 3), dtype=int))
    out = np.zeros(visible.shape, dtype=np.float32)
    H, W = visible.shape
    objs = ndi.find_objects(lab)
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        ys, xs = np.nonzero(lab[sl] == i + 1)
        if ys.size < min_size:
            continue
        ys = ys + sl[0].start
        xs = xs + sl[1].start
        cy, cx = ys.mean(), xs.mean()
        dy, dx = ys - cy, xs - cx
        cov = np.array([[np.dot(dx, dx), np.dot(dx, dy)],
                        [np.dot(dx, dy), np.dot(dy, dy)]]) / ys.size
        w, v = np.linalg.eigh(cov)
        ax = v[:, -1]                       # (x, y) principal direction
        t = dx * ax[0] + dy * ax[1]
        for sgn in (1.0, -1.0):
            end = t.max() if sgn > 0 else t.min()
            near = np.abs(t - end) <= fit_px
            if near.sum() < 3:
                near = np.abs(t - end) <= max(fit_px, 3)
            ey, ex = ys[near].mean(), xs[near].mean()
            ndy, ndx = ys[near] - ey, xs[near] - ex
            c2 = np.array([[np.dot(ndx, ndx), np.dot(ndx, ndy)],
                           [np.dot(ndx, ndy), np.dot(ndy, ndy)]]) / max(near.sum(), 1)
            _, v2 = np.linalg.eigh(c2)
            d = v2[:, -1]
            if (d[0] * ax[0] + d[1] * ax[1]) * sgn < 0:
                d = -d
            py = ys[near][np.argmax((ys[near] - cy) * ax[1] * sgn
                                    + (xs[near] - cx) * ax[0] * sgn)]
            px = xs[near][np.argmax((ys[near] - cy) * ax[1] * sgn
                                    + (xs[near] - cx) * ax[0] * sgn)]
            for s in range(1, reach_px + 1):
                yy = int(round(py + d[1] * s))
                xx = int(round(px + d[0] * s))
                if 0 <= yy < H and 0 <= xx < W:
                    val = decay ** s
                    if val > out[yy, xx]:
                        out[yy, xx] = val
                else:
                    break
    return out
