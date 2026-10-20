"""What the explore step and the analysis share: the populations of repositories each definition
is read on, and the paired estimand.

A population is the usable repositories of one measured set (paper one's substance floor,
study.is_usable, on the measured row) whose score carries the definition at that level with a
non-empty universe: for a human definition, at least one reviewed unit (a repository whose
reviewed units hold no positive is KEPT: its reviewed units are negatives, as paper one's
human_readout reads them); for a tool definition, the tool's panel ran. Its cells are an array
C[repository, form, rule, 4] of paper one's lean counts.
"""
from __future__ import annotations

import math

import numpy as np

from . import boot, forms, pins, rules

MAD = rules.ORDER.index(pins.OUTLIER_RULE)


class Population:
    def __init__(self, scores: list[dict], set_name: str, level: str, oracle: str, label: str = ""):
        self.set_name, self.level, self.oracle = set_name, level, oracle
        self.label = label or f"{oracle} ({set_name})"
        self.meta, cells, self.extracts, self.lv = [], [], [], []
        for sc in scores:
            m = sc["meta"]
            if not m.get("usable") or m.get("error"):
                continue
            lv = (sc.get("sets") or {}).get(set_name, {}).get(level)
            if not lv or oracle not in lv["oracles"]:
                continue
            oi = lv["oracles"].index(oracle)
            c = lv["cells"][:, :, oi, :]
            if c[0, MAD, 0] == 0:
                continue                                  # no unit in the definition's universe
            self.meta.append(m)
            cells.append(c)
            self.extracts.append((lv.get("extracts") or {}).get(oracle))
            self.lv.append(lv)
        self.n = len(self.meta)
        nf = len(forms.SPECS[level])
        self.C = np.stack(cells) if cells else np.zeros((0, nf, len(rules.ORDER), 4), np.int32)
        self._m = None

    def subset(self, keep: np.ndarray) -> "Population":
        p = object.__new__(Population)
        p.set_name, p.level, p.oracle, p.label = self.set_name, self.level, self.oracle, self.label
        idx = np.flatnonzero(keep)
        p.meta = [self.meta[i] for i in idx]
        p.extracts = [self.extracts[i] for i in idx]
        p.lv = [self.lv[i] for i in idx]
        p.C = self.C[idx]
        p.n = len(idx)
        p._m = None
        return p

    @property
    def m(self) -> np.ndarray:
        """Paper one's bootstrap multiplicities for this population (its own generator)."""
        if self._m is None:
            self._m = boot.multiplicities(self.n)
        return self._m

    def f(self, form: str) -> int:
        return forms.INDEX[self.level][form]

    def counts(self, form: str, rule: int = MAD) -> np.ndarray:
        return self.C[:, self.f(form), rule, :]

    def pooled_mcc(self, form: str, rule: int = MAD) -> float | None:
        if self.n == 0:
            return None
        return float(boot.mcc_counts(self.counts(form, rule).sum(0)))

    def with_positive(self) -> np.ndarray:
        return self.C[:, 0, MAD, 3] > 0


REFINES = "the divergence factor refines complexity"
WORSENS = "it makes it worse"


def compare(pop: Population, x: str, y: str, rule: int = MAD, better: str = REFINES,
            worse: str = WORSENS, neither: str = "no difference resolved") -> dict:
    """The paired comparison of form y against form x on a population: the micro (pooled) MCC
    difference with its interval and reading (`better` when its lower bound is above 0, `worse`
    when its upper bound is below), and beside it, not deciding, each arm's pooled precision,
    recall and false-positive rate, and the macro MCC difference."""
    cx, cy = pop.counts(x, rule), pop.counts(y, rule)
    micro = boot.micro_diff(cx, cy, pop.m)
    return {"x": x, "y": y, "rule": rules.ORDER[rule], "population": pop.label, "n_repos": pop.n,
            "n_repos_with_positive": int(pop.with_positive().sum()),
            "micro": micro, "reading": boot.reading(micro, better, worse, neither),
            "arms": {x: {"mcc": pop.pooled_mcc(x, rule), **boot.rates(cx.sum(0))},
                     y: {"mcc": pop.pooled_mcc(y, rule), **boot.rates(cy.sum(0))}},
            "macro": boot.macro_diff(cx, cy, pop.m)}


def primary_arm(level: str, x: str, k: str = "flow", variant: str | None = None) -> str:
    """The name of X*D_k in the primary form: class form A with non-private methods as inputs
    (constructors not counted); method, all calls (or the variant given)."""
    return factor_arm("D", level, x, k, variant)


def factor_arm(factor: str, level: str, x: str, k: str = "flow", variant: str | None = None) -> str:
    """The name of X*F_k for a factor F (D: divergence; E: exemption only; A: amplification
    only; O: outgoing) in the primary variant, or the variant given (PLAN.md, Amendments, 4)."""
    if level == "class":
        if factor == "O":
            return forms.name(("XO_A", x, k))
        return forms.name((f"X{factor}_A", x, k, variant or "np"))
    return forms.name((f"X{factor}", x, k, variant or "all"))


def gate(pop: Population, x: str) -> dict:
    """PLAN.md, Effective-sample gate (as amended, Amendments, 6): the 95% percentile bootstrap
    interval of the pooled paired difference (X*D_flow minus X*) over the explore population has
    half-width h over n_e explore repositories with at least one reviewed positive; a pooled
    interval narrows with the square root of the number of repositories, so the confirm
    repositories with a reviewed positive needed for a half-width of 0.10 are
    n = ceil(n_e (h / 0.10)^2), never below 20. The gate as first registered (s, the standard
    deviation of the per-repository paired MCC difference; n = ceil((1.96 s / 0.10)^2)) is
    computed beside it, under `v1`, for the record; it does not decide."""
    keep = pop.with_positive()
    n_e = int(keep.sum())
    y = primary_arm(pop.level, x)
    micro = boot.micro_diff(pop.counts(x), pop.counts(y), pop.m) if pop.n else None
    h = (micro["hi"] - micro["lo"]) / 2 if micro else float("nan")
    n = (max(pins.GATE_FLOOR, math.ceil(n_e * (h / pins.HALF_WIDTH) ** 2))
         if not math.isnan(h) and n_e > 0 else None)
    d = (boot.per_item_mcc(pop.counts(y)[keep]) - boot.per_item_mcc(pop.counts(x)[keep]))
    s = float(np.std(d, ddof=1)) if len(d) > 1 else float("nan")
    n1 = max(pins.GATE_FLOOR, math.ceil((1.96 * s / pins.HALF_WIDTH) ** 2)) if not math.isnan(s) else None
    return {"n_required": n, "half_width_explore": h, "interval_explore": micro,
            "n_repos_with_positive_explore": n_e, "n_repos_explore": pop.n,
            "rule": "n = ceil(n_e (h / 0.10)^2), at least 20; h the half-width of the explore "
                    "bootstrap interval of the pooled paired difference, n_e the explore "
                    "repositories with at least one reviewed positive (PLAN.md, Amendments, 6)",
            "v1": {"s": s, "n_required": n1, "n_repos_used": n_e,
                   "rule": "as first registered: n = ceil((1.96 s / 0.10)^2), at least 20; s over "
                           "the explore repositories with at least one reviewed positive; "
                           "reported, not deciding"}}


def choose(pop: Population, candidates) -> dict:
    """X*: the candidate whose mad_z flags maximise the pooled MCC (ties: the first in paper one's
    family order). The multiplied form is not consulted."""
    crit = {x: pop.pooled_mcc(x) for x in candidates}
    best = max(candidates, key=lambda x: (crit[x] if crit[x] is not None else -2, -candidates.index(x)))
    return {"chosen": best, "criterion": crit, "candidates": list(candidates),
            "population": pop.label, "n_repos": pop.n}
