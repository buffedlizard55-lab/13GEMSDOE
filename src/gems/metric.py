"""
Exact implementation of the GEMS Prize scoring metric: the distance-weighted
Tversky index (DTI).

Transcribed verbatim from the official problem description:
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
  section "Performance metric" -> "Mathematical representation".

Official definitions (R = 300 m = 3 pixels at 100 m resolution):

    k(d) = max(1 - d/R, 0)                                   triangular kernel

    TP_w = sum_{g in G}  max_{x : d(x,g) <= R}  p(x) * k(d(x,g))
    FP_w = sum_{x : p(x) > 0}  p(x) * [ 1 - max_{g in G} k(d(x,g)) ]
    FN_w = sum_{g in G} [ 1 - max_{x : d(x,g) <= R} p(x) * k(d(x,g)) ]

    DTI(alpha, beta) = TP_w / (TP_w + alpha*FP_w + beta*FN_w + eps)

Competition setting: alpha = 0.2, beta = 0.8.

Official worked example (same page, "Scoring example"):
    TP_w = 3.00, FP_w = 1.89, FN_w = 2.00  ->  DTI = 0.60

--------------------------------------------------------------------------
ALGEBRAIC AUDIT (proved in `audit.py`, all three results are exact identities)
--------------------------------------------------------------------------
Because the TP_w and FN_w summands are complementary over the SAME index set
G with the SAME inner max, FN_w == |G| - TP_w identically. Therefore

    DTI = TP_w / (0.2*TP_w + 0.2*FP_w + 0.8*|G|)                        (R1)
        = 1 / (0.2/P_w + 0.8/R_w)                                       (R2)

with weighted precision P_w = TP_w/(TP_w+FP_w) and weighted recall
R_w = TP_w/|G|.  (R2) is exactly the weighted harmonic mean of precision
(weight 0.2) and recall (weight 0.8) -- i.e. DTI is a distance-weighted
F-beta score with beta^2 = 0.8/0.2 = 4, so beta = 2:  DTI is a
distance-weighted **F2 score**.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

# ----------------------------------------------------------------------------
# Official competition constants
# ----------------------------------------------------------------------------
ALPHA = 0.2            # false-positive weight (official)
BETA = 0.8             # false-negative weight (official)
PIXEL_SIZE_M = 100.0   # training/submission grid resolution (official)
RANGE_M = 300.0        # triangular kernel support R (official)
R_PIX = RANGE_M / PIXEL_SIZE_M  # == 3.0 pixels
EPS = 1e-9


def kernel_offsets(r_pix: float = R_PIX) -> list[tuple[int, int, float]]:
    """All integer pixel offsets (dy, dx) with Euclidean distance <= r_pix,
    paired with their triangular-kernel weight k(d) = max(1 - d/r, 0).

    Offsets whose weight is exactly 0 (d == r) are dropped: they can never
    change a max() and dropping them is exact, not an approximation.
    """
    out: list[tuple[int, int, float]] = []
    lim = int(np.floor(r_pix))
    for dy in range(-lim, lim + 1):
        for dx in range(-lim, lim + 1):
            d = float(np.hypot(dy, dx))
            if d <= r_pix:
                k = 1.0 - d / r_pix
                if k > 0.0:
                    out.append((dy, dx, k))
    return out


def _shift(a: np.ndarray, dy: int, dx: int, fill: float = 0.0) -> np.ndarray:
    """Shift array contents by (dy, dx); vacated cells filled with `fill`.

    Result[y, x] == a[y + dy, x + dx] when in-bounds.
    """
    out = np.full_like(a, fill)
    ys_dst = slice(max(0, -dy), a.shape[0] - max(0, dy))
    ys_src = slice(max(0, dy), a.shape[0] - max(0, -dy))
    xs_dst = slice(max(0, -dx), a.shape[1] - max(0, dx))
    xs_src = slice(max(0, dx), a.shape[1] - max(0, -dx))
    out[ys_dst, xs_dst] = a[ys_src, xs_src]
    return out


def kernel_dilate_prob(p: np.ndarray, r_pix: float = R_PIX) -> np.ndarray:
    """D[y,x] = max_{|o| <= R} p[(y,x)+o] * k(|o|).

    Evaluated at a ground-truth pixel g this is exactly the inner
    `max_{x : d(x,g) <= R} p(x) k(d(x,g))` of the official TP_w / FN_w sums.
    """
    p = np.asarray(p, dtype=np.float64)
    out = np.zeros_like(p)
    for dy, dx, k in kernel_offsets(r_pix):
        np.maximum(out, _shift(p, dy, dx) * k, out=out)
    return out


def kernel_field_of_truth(g: np.ndarray, r_pix: float = R_PIX) -> np.ndarray:
    """K[y,x] = max_{g in G} k(d(x,g)); 0 where no truth pixel is within R.

    This is the `max_{g in G} k(d(x,g))` factor of the official FP_w sum.
    Computed by exact morphological dilation of the binary truth mask, which
    equals k(EDT) because k is monotonically non-increasing in d.
    """
    gb = (np.asarray(g) > 0).astype(np.float64)
    out = np.zeros_like(gb)
    for dy, dx, k in kernel_offsets(r_pix):
        np.maximum(out, _shift(gb, dy, dx) * k, out=out)
    return out


@dataclass(frozen=True)
class DTIResult:
    tp_w: float
    fp_w: float
    fn_w: float
    n_truth: int
    dti: float
    precision_w: float
    recall_w: float

    def as_dict(self) -> dict:
        return asdict(self)


def dti(
    pred: np.ndarray,
    truth: np.ndarray,
    alpha: float = ALPHA,
    beta: float = BETA,
    r_pix: float = R_PIX,
    eval_mask: np.ndarray | None = None,
    eps: float = EPS,
) -> DTIResult:
    """Distance-weighted Tversky index; the base formula matches the official metric.

    Parameters
    ----------
    pred : float array in [0, 1]. NaN is treated as 0 (no prediction).
    truth : array; > 0 marks a ground-truth fault pixel.
    eval_mask : local optional evaluation-mask extension. Where False, truth
        pixels are excluded and FP_w is zeroed. In this function, prediction
        mass outside the mask can still contribute through the TP dilation for
        in-mask truth. The organizer confirms pixel-exact masking of known
        pixels and that new-fault truth may lie within 300 m of known traces,
        but public wording does not resolve whether predictions on masked known
        pixels can supply that TP credit. See knowledge/02_irregularities.md Q-1.
        `FoldScorer` defaults to conservatively dropping predictions outside its
        eval mask, so its default is not equivalent to this function on arbitrary
        unmasked prediction arrays; holdout candidate maps are clipped to the
        eval mask before either scorer is used. This is a local proxy policy,
        not a claim about the private evaluator.
    """
    p = np.nan_to_num(np.asarray(pred, dtype=np.float64), nan=0.0)
    if p.size and (p.min() < -1e-9 or p.max() > 1 + 1e-9):
        raise ValueError(
            f"predictions must lie in [0,1]; got [{p.min()}, {p.max()}]"
        )
    p = np.clip(p, 0.0, 1.0)

    g = (np.asarray(truth) > 0)
    if eval_mask is not None:
        g = g & eval_mask

    n_truth = int(g.sum())

    # TP_w / FN_w : one term per ground-truth pixel.
    dil = kernel_dilate_prob(p, r_pix)
    per_truth = dil[g]
    tp_w = float(per_truth.sum())
    fn_w = float((1.0 - per_truth).sum())  # identically n_truth - tp_w

    # FP_w : one term per predicted pixel.
    kfield = kernel_field_of_truth(g, r_pix)
    fp_map = p * (1.0 - kfield)
    if eval_mask is not None:
        fp_map = np.where(eval_mask, fp_map, 0.0)
    fp_w = float(fp_map.sum())

    score = tp_w / (tp_w + alpha * fp_w + beta * fn_w + eps)
    prec = tp_w / (tp_w + fp_w) if (tp_w + fp_w) > 0 else 0.0
    rec = tp_w / n_truth if n_truth > 0 else 0.0
    return DTIResult(tp_w, fp_w, fn_w, n_truth, score, prec, rec)


# ----------------------------------------------------------------------------
# Closed forms implied by the FN_w == |G| - TP_w identity
# ----------------------------------------------------------------------------
def dti_reduced(tp_w: float, fp_w: float, n_truth: float,
                alpha: float = ALPHA, beta: float = BETA,
                eps: float = EPS) -> float:
    """DTI = TP_w / ((1-beta)*TP_w + alpha*FP_w + beta*|G|).

    At the official alpha=0.2, beta=0.8 this is
        TP_w / (0.2*TP_w + 0.2*FP_w + 0.8*|G|).
    """
    return tp_w / ((1.0 - beta) * tp_w + alpha * fp_w + beta * n_truth + eps)


def dti_from_pr(precision_w: float, recall_w: float,
                alpha: float = ALPHA, beta: float = BETA) -> float:
    """DTI as the weighted harmonic mean 1 / (alpha/P + beta/R)."""
    if precision_w <= 0 or recall_w <= 0:
        return 0.0
    return 1.0 / (alpha / precision_w + beta / recall_w)


def marginal_precision_threshold(current_dti: float,
                                 alpha: float = ALPHA) -> float:
    """Smallest marginal weighted precision d(TP)/(d(TP)+d(FP)) that a block of
    added predictions must exceed to RAISE the score.

    Exact result (derivation in audit.py): the threshold is alpha * DTI.
    At alpha = 0.2 a block only needs marginal precision above 0.2 * DTI.
    """
    return alpha * current_dti


def recall_dominates_precision(precision_w: float, recall_w: float,
                               alpha: float = ALPHA,
                               beta: float = BETA) -> bool:
    """True when a relative gain in recall moves DTI more than the same
    relative gain in precision.

    d log DTI / d log R  >  d log DTI / d log P
        <=>  beta/R > alpha/P  <=>  P > (alpha/beta) * R.
    At alpha=0.2, beta=0.8 the crossover is P > 0.25 * R.
    """
    if precision_w <= 0 or recall_w <= 0:
        return False
    return (beta / recall_w) > (alpha / precision_w)


def elasticities(precision_w: float, recall_w: float,
                 alpha: float = ALPHA, beta: float = BETA
                 ) -> tuple[float, float]:
    """(d log DTI / d log P, d log DTI / d log R); the two sum to 1."""
    if precision_w <= 0 or recall_w <= 0:
        return (0.0, 0.0)
    a, b = alpha / precision_w, beta / recall_w
    return (a / (a + b), b / (a + b))
