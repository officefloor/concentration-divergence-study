"""Paper one's seven outlier rules (complexity_concentration_study.metrics.ALGORITHMS), each at its
default constant, on numpy arrays.

The study scores about 800 signal forms per repository with every rule, so paper one's
pure-Python rules (its skew-adjusted boxplot computes a 1500 x 1500 medcouple kernel in Python)
would take days. These are the same rules, operation for operation: the same order statistics,
the same arithmetic in the same order, and every sum over many values taken with Python's own
`sum` (which since Python 3.12 is compensated, so numpy's pairwise sum could differ in the last
bit and flip a unit on a boundary). tests/test_rules.py checks that each flags exactly the units
paper one's rule flags, on random, tied, zero-heavy and constant populations.

Each function takes the values of one population (every unit of the repository at the level,
zeros included, as paper one fits) and returns a boolean mask of the flagged units.
"""
from __future__ import annotations

import math

import numpy as np

from complexity_concentration_study import extract as p1_extract
from complexity_concentration_study import metrics as p1_metrics

CUT = p1_extract.OUTLIER_Z                 # 3.5, the modified z's constant
ORDER = tuple(p1_metrics.ALGORITHMS)       # mad_z, double_mad, iqr, adj_boxplot, evt_pot, pct_top1, zscore


def _median_sorted(xs: np.ndarray) -> float:
    n = len(xs)
    return float(xs[n // 2]) if n % 2 else (float(xs[n // 2 - 1]) + float(xs[n // 2])) / 2


def _median_unsorted(a: np.ndarray) -> float:
    """The median as metrics.median takes it (the middle order statistic, or the mean of the two
    middle ones), by selection instead of a full sort: the same order statistics, so the same value."""
    n = len(a)
    if n % 2:
        return float(np.partition(a, n // 2)[n // 2])
    p = np.partition(a, [n // 2 - 1, n // 2])
    return (float(p[n // 2 - 1]) + float(p[n // 2])) / 2


def mad_z_scale(v: np.ndarray) -> tuple[str, np.ndarray]:
    """(scale kind, modified z of every value): extract.modified_z_scale, vectorised."""
    n = len(v)
    if n == 0:
        return "constant", np.zeros(0)
    xs = np.sort(v)
    med = _median_sorted(xs)
    dev = np.sort(np.abs(xs - med))
    mad = _median_sorted(dev)
    if mad > 0:
        return "mad", 0.6745 * (v - med) / mad
    mad2 = sum(np.abs(xs - med).tolist()) / n
    if mad2 > 0:
        return "mean_ad", (v - med) / (1.2533 * mad2)
    return "constant", np.zeros(n)


def mad_z(v: np.ndarray, cut: float = CUT) -> np.ndarray:
    if len(v) == 0:
        return np.zeros(0, bool)
    return mad_z_scale(v)[1] >= cut


def double_mad(v: np.ndarray, cut: float = CUT) -> np.ndarray:
    n = len(v)
    if n < 3:
        return np.zeros(n, bool)
    xs = np.sort(v)
    med = _median_sorted(xs)
    upper = np.sort(xs[xs >= med] - med)
    mad_u = _median_sorted(upper) if len(upper) else 0
    if not mad_u or mad_u <= 0:
        return mad_z(v, cut)
    return (v > med) & (0.6745 * (v - med) / mad_u >= cut)


def _quantile(xs: np.ndarray, q: float) -> float:
    n = len(xs)
    if n == 1:
        return float(xs[0])
    pos = q * (n - 1)
    lo = int(pos)
    frac = pos - lo
    return float(xs[lo]) * (1 - frac) + float(xs[lo + 1]) * frac if lo + 1 < n else float(xs[lo])


def iqr(v: np.ndarray, k: float = 1.5) -> np.ndarray:
    xs = np.sort(v)
    if len(xs) < 4:
        return np.zeros(len(v), bool)
    q1, q3 = _quantile(xs, 0.25), _quantile(xs, 0.75)
    return v > q3 + k * (q3 - q1)


def medcouple(sorted_xs: np.ndarray) -> float:
    """metrics._medcouple: the same subsample of order statistics, the same kernel, its median."""
    xs = sorted_xs
    n = len(xs)
    if n < 3:
        return 0.0
    if n > 1500:
        step = n / 1500.0
        xs = np.array([xs[min(n - 1, int(i * step))] for i in range(1500)])
        n = len(xs)
    med = _median_sorted(xs)
    U = xs[xs >= med]
    L = xs[xs <= med]
    nu, nl = len(U), len(L)
    a = U[:, None]
    b = L[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        h = ((a - med) - (med - b)) / (a - b)
    tie = (a == med) & (b == med)
    if tie.any():
        i = np.arange(nu)[:, None]
        j = np.arange(nl)[None, :]
        k = (nu - 1 - i) - j
        h = np.where(tie, np.sign(k).astype(float), h)
    return _median_unsorted(h.ravel()) or 0.0


def adj_boxplot(v: np.ndarray, k: float = 1.5) -> np.ndarray:
    xs = np.sort(v)
    if len(xs) < 5:
        return np.zeros(len(v), bool)
    q1, q3 = _quantile(xs, 0.25), _quantile(xs, 0.75)
    mc = medcouple(xs)
    coef = math.exp(3 * mc) if mc >= 0 else math.exp(4 * mc)
    return v > q3 + k * coef * (q3 - q1)


def evt_pot(v: np.ndarray, q: float = 0.90) -> np.ndarray:
    xs = np.sort(v)
    n = len(xs)
    out = np.zeros(n, bool)
    if n < 20:
        return out
    p = 1.0 / n
    u = float(xs[int(q * n)])
    ex = (xs[xs > u] - u).tolist()
    if len(ex) < 10:
        return out
    m = sum(ex) / len(ex)
    var = sum((e - m) ** 2 for e in ex) / len(ex)
    if var <= 0:
        return out
    xi = 0.5 * (1 - m * m / var)
    sigma = 0.5 * m * (1 + m * m / var)
    pu = len(ex) / n
    if sigma <= 0:
        return out
    if pu < p:                                   # every value at or below u has survival pu
        out[v <= u] = True
    for i in np.nonzero(v > u)[0]:               # the exceedances, in paper one's arithmetic
        y = float(v[i]) - u
        if abs(xi) < 1e-6:
            s = pu * math.exp(-y / sigma)
        else:
            base = 1 + xi * y / sigma
            s = pu * base ** (-1.0 / xi) if base > 0 else 0.0
        out[i] = s < p
    return out


def pct_top1(v: np.ndarray, q: float = 0.99) -> np.ndarray:
    xs = np.sort(v)
    n = len(xs)
    if n < 2:
        return np.zeros(n, bool)
    thr = xs[min(n - 1, int(q * n))]
    return (v >= thr) & (v > xs[0])


def zscore(v: np.ndarray, k: float = 3.0) -> np.ndarray:
    n = len(v)
    if n < 3:
        return np.zeros(n, bool)
    xs = v.tolist()
    mean = sum(xs) / n
    sd = (sum((x - mean) ** 2 for x in xs) / (n - 1)) ** 0.5
    if sd <= 0:
        return np.zeros(n, bool)
    return (v - mean) / sd >= k


RULES = {"mad_z": mad_z, "double_mad": double_mad, "iqr": iqr, "adj_boxplot": adj_boxplot,
         "evt_pot": evt_pot, "pct_top1": pct_top1, "zscore": zscore}
assert tuple(RULES) == ORDER, "the rules must be paper one's, in its reporting order"


def all_rules(v: np.ndarray) -> list[np.ndarray]:
    """The masks of every rule, in ORDER."""
    return [RULES[name](v) for name in ORDER]
