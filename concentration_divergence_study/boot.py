"""The percentile bootstrap over repositories, vectorised.

stats.bootstrap_paired (paper one) draws, for each of B replicates, n repository indices with
random.Random(seed).randrange(n), recomputes the statistic on the resampled list, drops the
replicates where it is undefined, and reads the 2.5% and 97.5% order statistics. Pooled (micro)
statistics are sums of per-repository counts, so a replicate is the multiplicity of each
repository times its counts: `multiplicities` draws exactly paper one's indices, in its order,
and every interval here is read with paper one's order-statistic rule. tests/test_boot.py checks
that the paired micro-MCC interval equals stats.bootstrap_paired's on the same counts.

For the consistency analysis, one set of replicates must resample every population at once
(PLAN.md: one bootstrap that resamples repositories once per replicate and recomputes every
cell), so `joint_multiplicities` draws, per replicate, each population's indices in a fixed
order from one generator.
"""
from __future__ import annotations

import math
import random

import numpy as np

from . import pins


def multiplicities(n: int, b: int = pins.BOOTSTRAP_B, seed: int = pins.BOOTSTRAP_SEED) -> np.ndarray:
    """[b, n]: how often each item is drawn in each replicate, paper one's draws."""
    rnd = random.Random(seed)
    m = np.zeros((b, n), np.int32)
    for r in range(b):
        row = m[r]
        for _ in range(n):
            row[rnd.randrange(n)] += 1
    return m


def joint_multiplicities(sizes: dict, b: int = pins.BOOTSTRAP_B,
                         seed: int = pins.BOOTSTRAP_SEED) -> dict:
    """{population: [b, n]} from one generator, per replicate each population in `sizes` order."""
    rnd = random.Random(seed)
    out = {p: np.zeros((b, n), np.int32) for p, n in sizes.items()}
    for r in range(b):
        for p, n in sizes.items():
            row = out[p][r]
            for _ in range(n):
                row[rnd.randrange(n)] += 1
    return out


def mcc_counts(s: np.ndarray) -> np.ndarray:
    """MCC from [..., 4] counts (n_univ, n_out, n_overlap, n_god_univ), as stats.pooled_confusion
    derives it: 0 when a marginal is empty."""
    n, pp, tp, ap = (s[..., i].astype(float) for i in range(4))
    fp, fn = pp - tp, ap - tp
    tn = n - pp - ap + tp
    den = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (tp * tn - fp * fn) / np.sqrt(np.where(den > 0, den, 1)), 0.0)


def rates(s: np.ndarray) -> dict:
    n, pp, tp, ap = (float(s[i]) for i in range(4))
    fp = pp - tp
    tn = n - pp - ap + tp
    return {"tp": tp, "fp": fp, "fn": ap - tp, "tn": tn, "n_god": ap, "n_univ": n,
            "precision": tp / pp if pp else None, "recall": tp / ap if ap else None,
            "fpr": fp / (fp + tn) if (fp + tn) else None}


def interval(full: float | None, reps: np.ndarray, n: int, b: int = pins.BOOTSTRAP_B,
             min_n: int = 5) -> dict | None:
    """Paper one's reading of a bootstrap: None for fewer than min_n items or an undefined full
    value; replicates that are NaN are dropped, and fewer than b // 2 left is None."""
    if n < min_n or full is None or (isinstance(full, float) and math.isnan(full)):
        return None
    vals = np.sort(reps[~np.isnan(reps)])
    k = len(vals)
    if k < max(2, b // 2):
        return None
    return {"value": float(full), "lo": float(vals[int(0.025 * k)]),
            "hi": float(vals[min(k - 1, int(0.975 * k))]), "n": n, "n_dropped": b - k}


def reading(iv: dict | None, better: str = "the first is better", worse: str = "the second is better",
            neither: str = "no difference resolved") -> str:
    if iv is None:
        return "not estimable"
    if iv["lo"] > 0:
        return better
    if iv["hi"] < 0:
        return worse
    return neither


def micro_diff(counts_x: np.ndarray, counts_y: np.ndarray, m: np.ndarray) -> dict | None:
    """The paired difference of pooled MCCs, Y minus X, over items with [n, 4] counts each, with
    its interval from multiplicities m [b, n]. A replicate is undefined (dropped) when no
    resampled item has a universe, as stats.pooled_confusion is."""
    n = len(counts_x)
    if n == 0:
        return None
    has = (counts_x[:, 0] > 0).astype(float)
    full = float(mcc_counts(counts_y.sum(0)) - mcc_counts(counts_x.sum(0))) if has.sum() else None
    sx = m @ counts_x.astype(float)
    sy = m @ counts_y.astype(float)
    reps = mcc_counts(sy) - mcc_counts(sx)
    reps = np.where(m @ has > 0, reps, np.nan)
    return interval(full, reps, n, len(m))


def per_item_mcc(counts: np.ndarray) -> np.ndarray:
    return mcc_counts(counts)


def macro_diff(counts_x: np.ndarray, counts_y: np.ndarray, m: np.ndarray) -> dict | None:
    """The paired difference of macro (per-repository mean) MCCs, Y minus X."""
    n = len(counts_x)
    if n == 0:
        return None
    d = per_item_mcc(counts_y) - per_item_mcc(counts_x)
    full = float(d.mean())
    reps = (m @ d) / n
    return interval(full, reps, n, len(m))


def auc(pos: np.ndarray, neg: np.ndarray) -> float | None:
    """Mann-Whitney AUC with average ranks for ties (stats.auc)."""
    ng, nn = len(pos), len(neg)
    if ng == 0 or nn == 0:
        return None
    allv = np.concatenate([pos, neg])
    _, inv, counts = np.unique(allv, return_inverse=True, return_counts=True)
    r = (np.cumsum(counts) - (counts - 1) / 2)[inv]
    return float((r[:ng].sum() - ng * (ng + 1) / 2) / (ng * nn))
