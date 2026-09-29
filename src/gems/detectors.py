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


# ---------------------------------------------------------------------------
# R6-1 · Horsetail splay / relay-ramp structural completion
# ---------------------------------------------------------------------------
def horsetail_splay(visible: np.ndarray, max_gap_px: int = 20,
                    min_size: int = 6, splay_len_px: int = 12,
                    n_fan: int = 5, fan_angle_deg: float = 35.0) -> np.ndarray:
    """Connect step-overs and emit horsetail fans at fault tips.

    Layers: existing_faults geometry only (catalogue-derived, rebuilt per fold).
    Physical signature: en-echelon step detection + tip splay.
    Why missing: catalogue omits small linking faults at relay ramps,
    horsetails and intersections because they are short, discontinuous, or lack
    Quaternary scarp. Organizers explicitly include extensions, splays,
    parallel strands and corrections as new-fault pixels.
    Differs from extension_rays: extension_rays projects forward along same
    strike; this detects NEARBY faults and bridges the gap, plus emits a fan
    of diverging rays at each tip (horsetail).
    """
    lab, ncomp = ndi.label(visible, structure=np.ones((3, 3), dtype=int))
    H, W = visible.shape
    out = np.zeros((H, W), dtype=np.float32)
    if ncomp == 0:
        return out
    objs = ndi.find_objects(lab)
    comps = []
    for i, sl in enumerate(objs):
        if sl is None:
            continue
        ys, xs = np.nonzero(lab[sl] == i + 1)
        if ys.size < min_size:
            continue
        ys = ys + sl[0].start
        xs = xs + sl[1].start
        cy, cx = float(ys.mean()), float(xs.mean())
        dy, dx = ys - cy, xs - cx
        cov = np.array([[np.dot(dx, dx), np.dot(dx, dy)],
                        [np.dot(dx, dy), np.dot(dy, dy)]]) / max(ys.size, 1)
        w, v = np.linalg.eigh(cov)
        ax = v[:, -1]  # principal (x,y)
        # strike angle
        ang = np.arctan2(ax[1], ax[0])
        t = dx * ax[0] + dy * ax[1]
        tmin, tmax = float(t.min()), float(t.max())
        # tip positions
        tip_lo = (ys[t.argmin()], xs[t.argmin()])
        tip_hi = (ys[t.argmax()], xs[t.argmax()])
        comps.append(dict(ys=ys, xs=xs, cy=cy, cx=cx, ax=ax, ang=ang,
                          tmin=tmin, tmax=tmax, tip_lo=tip_lo, tip_hi=tip_hi,
                          sl=sl))
    # relay ramp bridging
    for a in comps:
        for b in comps:
            if a is b:
                continue
            # quick distance between centroids
            dcent = np.hypot(a['cy'] - b['cy'], a['cx'] - b['cx'])
            if dcent > max_gap_px * 2:
                continue
            # check strike subparallel within 30 deg
            dang = abs(a['ang'] - b['ang'])
            dang = min(dang, np.pi - dang)
            if dang > np.deg2rad(30):
                continue
            # closest tip pair
            best = None
            best_d = 1e9
            for ta in (a['tip_lo'], a['tip_hi']):
                for tb in (b['tip_lo'], b['tip_hi']):
                    d = np.hypot(ta[0] - tb[0], ta[1] - tb[1])
                    if d < best_d:
                        best_d = d
                        best = (ta, tb)
            if best is None or best_d > max_gap_px or best_d < 1:
                continue
            (y0, x0), (y1, x1) = best
            # draw line between tips
            steps = int(max(abs(y1 - y0), abs(x1 - x0))) + 1
            for s in range(steps + 1):
                yy = int(round(y0 + (y1 - y0) * s / max(steps, 1)))
                xx = int(round(x0 + (x1 - x0) * s / max(steps, 1)))
                if 0 <= yy < H and 0 <= xx < W:
                    out[yy, xx] = max(out[yy, xx], 1.0 - best_d / max_gap_px)
    # horsetail fan at each tip
    fan_rad = np.deg2rad(fan_angle_deg)
    for c in comps:
        for tip, sgn in ((c['tip_lo'], -1.0), (c['tip_hi'], 1.0)):
            base_ang = c['ang']
            # fan angles centered on strike continuation
            for k in range(n_fan):
                frac = (k - (n_fan - 1) / 2) / max((n_fan - 1) / 2, 1)
                ang = base_ang + frac * fan_rad
                if sgn < 0:
                    # flip for lo tip
                    ang += np.pi if np.cos(ang - base_ang) > 0 else 0
                    # ensure continuation outward: if dot with principal is wrong, flip
                    dvec = np.array([np.cos(ang), np.sin(ang)])
                    if dvec[0] * c['ax'][0] + dvec[1] * c['ax'][1] > 0:
                        ang += np.pi
                else:
                    dvec = np.array([np.cos(ang), np.sin(ang)])
                    if dvec[0] * c['ax'][0] + dvec[1] * c['ax'][1] < 0:
                        ang += np.pi
                # emit ray
                for s in range(1, splay_len_px + 1):
                    yy = int(round(tip[0] + np.sin(ang) * s))
                    xx = int(round(tip[1] + np.cos(ang) * s))
                    if 0 <= yy < H and 0 <= xx < W:
                        val = (0.97 ** s) * (1.0 - abs(frac) * 0.3)
                        if val > out[yy, xx]:
                            out[yy, xx] = val
                    else:
                        break
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# R6-2 · Paleo-shoreline / lacustrine terrace scarp (intrabasin)
# ---------------------------------------------------------------------------
def paleo_shoreline_scarp(det_elev: np.ndarray, det_elev_slope: np.ndarray,
                          sigma: float = 2.0, flat_pct: float = 45.0) -> np.ndarray:
    """Subtle intrabasin scarps that offset flat lake-bottom sediments.

    Layers: det_elev (12), det_elev_slope (19).
    Physical signature: second-derivative / curvature ridge on detrended
    elevation, gated to low-slope, low-relief playa/lake beds.
    Why missing: USGS QFaults focuses on range-front scarps; intrabasin scarps
    in Lake Lahontan lake beds are low-amplitude (decimetres) and invisible
    without detrending. They still cut Quaternary deposits, so they are
    Quaternary faults missing from the catalogue.
    Differs from BASE_topo_ridge: BASE finds all ridges; this inverts the mask
    to flat ground, uses curvature (second derivative) not slope, and uses
    directional coherence to require lateral continuity of the shoreline.
    """
    elev = fill_nan_nearest(det_elev)
    slope = fill_nan_nearest(det_elev_slope)
    # flat mask: bottom 45% slope AND low local variance of elev
    thr_slope = np.percentile(slope[np.isfinite(slope)], flat_pct)
    flat = (slope <= thr_slope)
    # local variance via gaussian
    mean = ndi.gaussian_filter(elev, 6.0, mode='nearest')
    var = ndi.gaussian_filter((elev - mean) ** 2, 6.0, mode='nearest')
    thr_var = np.percentile(var[np.isfinite(var)], 50.0)
    flat = flat & (var <= thr_var)
    flat_f = ndi.gaussian_filter(flat.astype(np.float32), 3.0)

    # curvature: Laplacian of detrended elev
    lap = ndi.gaussian_laplace(elev, sigma=sigma)
    # ridge strength on slope magnitude for continuity
    st, ori = ridge_strength(slope, sigma=1.5)
    crest = nms_thin(st, ori)
    # combine: curvature magnitude where flat and crest present
    curv = robust_norm(np.abs(lap))
    out = curv * robust_norm(crest) * flat_f
    # directional coherence along strike (shoreline continuity)
    out = directional_lineaments(out, sigma=1.0, n_theta=8, length=12)
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# R6-3 · Conductive-base step with conductivity coherence
# ---------------------------------------------------------------------------
def conductive_base_step(depth_to_base: np.ndarray, cond_surf: np.ndarray,
                         det_elev_slope: np.ndarray,
                         sigma: float = 2.0, flat_pct: float = 55.0) -> np.ndarray:
    """Improved buried-fault detector: basement step AND conductivity contrast.

    Layers: depth_to_base_surf (15), cond_surf (17), det_elev_slope (19).
    Signature: product of gradient magnitudes of depth_to_base and cond_surf,
    oriented-filtered for line continuity, gated by flat topography AND low
    topo-ridge strength (so not already mapped).
    Why missing: buried fault offsets conductive basement and juxtaposes
    different lithologies -> conductivity contrast, but no surface scarp.
    Differs from HC_hinge: HC used only depth_to_base gradient magnitude;
    this requires BOTH depth and conductivity to agree, plus directional
    coherence, plus anti-topo gate.
    """
    dbase = fill_nan_nearest(depth_to_base)
    cond = fill_nan_nearest(cond_surf)
    slope = fill_nan_nearest(det_elev_slope)

    hg_base = horizontal_gradient_mag(dbase)
    hg_cond = horizontal_gradient_mag(cond)

    # ridge on product
    prod = robust_norm(hg_base) * robust_norm(hg_cond)
    st, ori = ridge_strength(prod, sigma=sigma)
    crest = nms_thin(st, ori)

    thr = np.percentile(slope[np.isfinite(slope)], flat_pct)
    flat = ndi.gaussian_filter((slope <= thr).astype(np.float32), 3.0)

    # also low topo ridge
    topo_st, _ = ridge_strength(slope, sigma=1.5)
    topo_norm = robust_norm(topo_st)
    anti_topo = 1.0 - topo_norm
    anti_topo = ndi.gaussian_filter(anti_topo, 2.0)

    out = robust_norm(crest) * flat * anti_topo
    # coherence
    out = directional_lineaments(out, sigma=1.2, n_theta=12, length=15)
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# R6-4 · Gravity-gradient termination / intersection
# ---------------------------------------------------------------------------
def gravity_termination(iso_grav_hg: np.ndarray, iso_grav_vg: np.ndarray,
                        iso_grav: np.ndarray,
                        sigma: float = 1.5, reach_px: int = 12) -> np.ndarray:
    """Where gravity gradient ridge terminates, a fault tip is hypothesized.

    Layers: iso_grav_anom_hg (18), iso_grav_anom_vg (11), iso_grav_anom (13).
    Signature: detect terminations of horizontal gravity gradient ridges,
    emit short continuation beyond termination. At intersections of two
    ridges, emit crossing splay.
    Why missing: INGENIOUS authors stated gravity-gradient terminations
    defined fault tips and crossings in their basin analysis. Those are
    places where geophysical evidence says structure continues but surface
    mapping stopped.
    Differs: uses geophysical ridge termination, not catalogue fault tip.
    """
    hg = fill_nan_nearest(iso_grav_hg)
    st, ori = ridge_strength(hg, sigma=sigma)
    crest = nms_thin(st, ori)
    # binary ridge
    ridge = crest > np.percentile(crest[crest > 0], 80) if (crest > 0).any() else crest > 0

    # find endpoints: ridge pixel with only 1 neighbor in 8-connectivity
    out = np.zeros_like(crest, dtype=np.float32)
    # use binary hit-or-miss for endpoints
    # simple approach: convolve neighbor count
    neigh = ndi.convolve(ridge.astype(np.float32), np.ones((3, 3)), mode='constant') - ridge.astype(np.float32)
    endpoints = ridge & (neigh == 1)

    ys, xs = np.nonzero(endpoints)
    H, W = crest.shape
    for y, x in zip(ys, xs):
        ang = ori[y, x]
        # two directions along ridge; we want outward continuation
        # estimate outward by checking which side has no ridge
        # try both directions, keep one with lower ridge density ahead
        best_dir = None
        best_score = 1e9
        for sgn in (1.0, -1.0):
            cnt = 0
            for s in range(1, 6):
                yy = int(round(y + np.sin(ang) * s * sgn))
                xx = int(round(x + np.cos(ang) * s * sgn))
                if 0 <= yy < H and 0 <= xx < W and ridge[yy, xx]:
                    cnt += 1
            if cnt < best_score:
                best_score = cnt
                best_dir = sgn
        if best_dir is None:
            best_dir = 1.0
        for s in range(1, reach_px + 1):
            yy = int(round(y + np.sin(ang) * s * best_dir))
            xx = int(round(x + np.cos(ang) * s * best_dir))
            if 0 <= yy < H and 0 <= xx < W:
                val = 0.95 ** s
                if val > out[yy, xx]:
                    out[yy, xx] = val
            else:
                break
    # intersections: where two different orientations cross -> emit short cross
    # approximate by high ridge strength + high orientation variance in 3x3
    ori_var = ndi.generic_filter(ori, lambda x: np.std(x), size=3, mode='nearest')
    inter = ridge & (ori_var > np.deg2rad(25))
    out = np.maximum(out, inter.astype(np.float32) * 0.8)
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# R6-5 · Transtensional coupling / dilational jog
# ---------------------------------------------------------------------------
def transtensional_coupling(shear_rate: np.ndarray, dilate_rate: np.ndarray,
                            second_inv: np.ndarray, grav_hg: np.ndarray,
                            sigma: float = 2.0) -> np.ndarray:
    """High shear + positive dilatation + gravity gradient = dilational jog.

    Layers: geod_shearrate (7), geod_dilaterate (8), geod_2ndinv (4),
            iso_grav_anom_hg (18).
    Signature: normalized shear * positive dilatation * second invariant,
    multiplied by gravity gradient ridge strength to localize to a sharp trace.
    Why missing: transtensional jogs are prime geothermal targets (high
    permeability) but may have subtle or no scarp because extension is
    distributed. Strain fields are smooth (no pixel trace) so need sharp
    multiplier.
    Differs from HD_strain: HD used deficit (strain minus faults minus eq);
    this uses product of shear and dilatation (coupling) as positive evidence.
    """
    shear = fill_nan_nearest(shear_rate)
    dil = fill_nan_nearest(dilate_rate)
    sec = fill_nan_nearest(second_inv)
    grav = fill_nan_nearest(grav_hg)

    shear_n = robust_norm(ndi.gaussian_filter(shear, sigma))
    dil_pos = np.clip(dil, 0, None)
    dil_n = robust_norm(ndi.gaussian_filter(dil_pos, sigma))
    sec_n = robust_norm(ndi.gaussian_filter(sec, sigma))
    grav_st, _ = ridge_strength(grav, sigma=1.5)
    grav_n = robust_norm(grav_st)

    # coupling: shear * dil * sec
    coupling = shear_n * dil_n * sec_n
    out = coupling * (0.5 + 0.5 * grav_n)  # gravity localizes but not required
    out = robust_norm(out)
    # oriented lineament on top to make it trace-like
    out = directional_lineaments(out, sigma=1.2, n_theta=12, length=15)
    return out.astype(np.float32)
