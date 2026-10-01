"""Buffered geographic stress folds. Public covariates remain visible.

This is NOT private-test ground truth and not the system-withholding protocol.
Tile assignment is independent of labels; truth only comes from withheld labels.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from .holdout import Fold


def spatially_blocked_folds(known: np.ndarray, valid: np.ndarray, *,
                           tile_px: int = 256, buffer_px: int = 5,
                           guard_px: int = 3) -> list[Fold]:
    known, valid = np.asarray(known, bool), np.asarray(valid, bool)
    if known.ndim != 2 or valid.shape != known.shape:
        raise ValueError('Known/valid masks must be matching 2D arrays')
    if tile_px <= 2 * guard_px or buffer_px < guard_px or guard_px < 0:
        raise ValueError('Tile must exceed guards; buffer must be >= guard >= 0')
    if np.any(known & ~valid):
        raise ValueError('Catalogue outside footprint')
    row = np.arange(known.shape[0])[:, None] // tile_px
    col = np.arange(known.shape[1])[None, :] // tile_px
    partition = (row % 2) * 2 + col % 2
    st = np.ones((3, 3), bool)
    folds = []
    for i in range(4):
        region = partition == i
        core = (ndi.binary_erosion(region, st, iterations=guard_px)
                if guard_px else region.copy())
        held_guard = (ndi.binary_dilation(region, st, iterations=buffer_px)
                      if buffer_px else region.copy())
        visible = known & ~held_guard
        em = valid & core
        hidden = known & em
        folds.append(Fold(f'geo256_{i}' if tile_px == 256 else f'geo{tile_px}_{i}',
                          'geographic_block', hidden, visible, em,
                          int(hidden.sum()), int(visible.sum()),
                          {'tile_px': tile_px, 'tile_m': tile_px * 100,
                           'partition': i, 'n_partitions': 4,
                           'buffer_px': buffer_px, 'metric_boundary_guard_px': guard_px,
                           'held_out_catalogue_pixels': int((known & region).sum()),
                           'withheld_truth_pixels_in_guard_not_scored': int((known & region & ~core).sum()),
                           'public_covariates_available': True,
                           'label_dependent_tile_selection': False}))
    return folds
