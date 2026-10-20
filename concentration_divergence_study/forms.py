"""The signal forms of the matrix (PLAN.md, The leaf exemption and the score; The matrix).

For a coupling definition k, with d_k = out_k - in_k:

    fD_k = max(d_k + 1, 0)      the divergence factor: a catchment (d < 0) is exempt (0), a
                                pipe (d = 0) counts once, a junction counts d + 1 times
    fO_k = out_k + 1            the outgoing factor (the petclinic observation)

Method level, for each of paper one's 10 method signals X, each definition k and each calls
variant v (`all`: every internal call; `nohelp`: calls to another file only):

    X            complexity alone                                   10
    X*D_k@v      X x fD_k                                           60
    X*O_k@v      X x fO_k                                           60
    D_k@v, O_k@v the factors alone                                  12
    X&d_k        AND: flagged by the rule on X and on d_k@all       (the candidates x 3)

Class level, for each of paper one's 31 class signals Xc, input variant i (`np`: non-private
methods; `pub`: public), and, for form B, each base method signal X and aggregation g:

    Xc                    complexity alone                                    31
    Xc*D_k[A,i]           A: the class's own coupling weights Xc              186
    Xc*O_k[A]                                                                 93
    D_k[A,i], O_k[A]                                                          9
    X*D_k[B,i]_g          B: each method's form, aggregated as paper one      180
    X*O_k[B]_g                                                                90
    D_k[B,i]_g, O_k[B]_g                                                      27
    Xc&d_k[A,np]          AND (the candidates x 3)

Each form is a spec tuple; `name` gives its label and `base` the complexity signal it is built
from (its family and its ingredient relation follow the base; None for the factors alone).
"""
from __future__ import annotations

import numpy as np

from complexity_concentration_study import metrics as p1_metrics

from .units import AGGS, CLASS_SIGNALS, DEFS, METHOD_FIELDS

VARIANTS = ("all", "nohelp")
INPUTS = ("np", "pub")

# The candidates for X* (PLAN.md, Primary estimand): class, paper one's primary families peak and
# density, never size, never params; method, structure and density, never params.
CLASS_CANDIDATES = tuple(s for fam in ("peak", "density") for s in p1_metrics.CLASS_FAMILIES[fam]
                         if not s.startswith("params_"))
METHOD_CANDIDATES = tuple(s for fam in ("structure", "density") for s in p1_metrics.METHOD_FAMILIES[fam]
                          if s != "params")


def method_forms() -> list[tuple]:
    out = [("X", x) for x in METHOD_FIELDS]
    out += [("XD", x, k, v) for x in METHOD_FIELDS for k in DEFS for v in VARIANTS]
    out += [("XO", x, k, v) for x in METHOD_FIELDS for k in DEFS for v in VARIANTS]
    out += [("D", k, v) for k in DEFS for v in VARIANTS]
    out += [("O", k, v) for k in DEFS for v in VARIANTS]
    out += [("AND", x, k) for x in METHOD_CANDIDATES for k in DEFS]
    return out


def class_forms() -> list[tuple]:
    out = [("X", x) for x in CLASS_SIGNALS]
    out += [("XD_A", x, k, i) for x in CLASS_SIGNALS for k in DEFS for i in INPUTS]
    out += [("XO_A", x, k) for x in CLASS_SIGNALS for k in DEFS]
    out += [("D_A", k, i) for k in DEFS for i in INPUTS]
    out += [("O_A", k) for k in DEFS]
    out += [("XD_B", x, g, k, i) for x in METHOD_FIELDS for g in AGGS for k in DEFS for i in INPUTS]
    out += [("XO_B", x, g, k) for x in METHOD_FIELDS for g in AGGS for k in DEFS]
    out += [("D_B", g, k, i) for g in AGGS for k in DEFS for i in INPUTS]
    out += [("O_B", g, k) for g in AGGS for k in DEFS]
    out += [("AND", x, k) for x in CLASS_CANDIDATES for k in DEFS]
    return out


def name(spec: tuple) -> str:
    t = spec[0]
    if t == "X":
        return spec[1]
    if t in ("XD", "XO"):
        return f"{spec[1]}*{t[1]}_{spec[2]}@{spec[3]}"
    if t in ("D", "O"):
        return f"{t}_{spec[1]}@{spec[2]}"
    if t == "XD_A":
        return f"{spec[1]}*D_{spec[2]}[A,{spec[3]}]"
    if t == "XO_A":
        return f"{spec[1]}*O_{spec[2]}[A]"
    if t == "D_A":
        return f"D_{spec[1]}[A,{spec[2]}]"
    if t == "O_A":
        return f"O_{spec[1]}[A]"
    if t == "XD_B":
        return f"{spec[1]}*D_{spec[3]}[B,{spec[4]}]_{spec[2]}"
    if t == "XO_B":
        return f"{spec[1]}*O_{spec[3]}[B]_{spec[2]}"
    if t == "D_B":
        return f"D_{spec[2]}[B,{spec[3]}]_{spec[1]}"
    if t == "O_B":
        return f"O_{spec[2]}[B]_{spec[1]}"
    if t == "AND":
        return f"{spec[1]}&d_{spec[2]}" + ("[A,np]" if spec[1] in CLASS_SIGNALS else "@all")
    raise ValueError(spec)


def base(spec: tuple) -> str | None:
    """The complexity signal a form is built from (at the form's own level)."""
    t = spec[0]
    if t in ("X", "XD", "XO", "XD_A", "XO_A", "AND"):
        return spec[1]
    if t in ("XD_B", "XO_B"):
        return f"{spec[1]}_{spec[2]}"
    return None


METHOD_FORMS = method_forms()
CLASS_FORMS = class_forms()
METHOD_NAMES = [name(f) for f in METHOD_FORMS]
CLASS_NAMES = [name(f) for f in CLASS_FORMS]
INDEX = {"method": {n: i for i, n in enumerate(METHOD_NAMES)},
         "class": {n: i for i, n in enumerate(CLASS_NAMES)}}
SPECS = {"method": METHOD_FORMS, "class": CLASS_FORMS}


# ---------------------------------------------------------------------------------------------
# divergence and the factors
# ---------------------------------------------------------------------------------------------
def method_d(m, k: str, v: str) -> np.ndarray:
    out = m.c[f"out_{'all' if v == 'all' else 'leave'}_{k}"]
    return out - m.c[f"in_{k}"]


def method_out(m, k: str, v: str) -> np.ndarray:
    return m.c[f"out_{'all' if v == 'all' else 'leave'}_{k}"]


def class_d(c, k: str, i: str) -> np.ndarray:
    return c.c[f"out_{k}"] - c.c[f"in_{i}_{k}"]


def fD(d: np.ndarray) -> np.ndarray:
    return np.maximum(d + 1, 0)


def fO(out: np.ndarray) -> np.ndarray:
    return out + 1


def _method_B(m, k: str, i: str | None) -> tuple[np.ndarray, np.ndarray]:
    """Form B's per-method factors: in counted only if callable from outside, out leaving only."""
    out = m.c[f"out_leave_{k}"]
    if i is None:
        return fO(out), None
    inn = np.where(m.c[f"callable_{i}"], m.c[f"in_{k}"], 0)
    return fD(out - inn), None


class Grouper:
    """Aggregates per-method values to the class units (files), as paper one aggregates."""

    def __init__(self, method_files, class_ids):
        pos = {f: j for j, f in enumerate(class_ids)}
        self.idx = np.array([pos.get(f, -1) for f in method_files])
        self.n = len(class_ids)
        self.count = np.bincount(self.idx[self.idx >= 0], minlength=self.n).astype(float)

    def agg(self, v: np.ndarray, g: str) -> np.ndarray:
        ok = self.idx >= 0
        if g == "sum" or g == "mean":
            s = np.bincount(self.idx[ok], weights=v[ok], minlength=self.n)
            if g == "sum":
                return s
            with np.errstate(invalid="ignore", divide="ignore"):
                return np.where(self.count > 0, s / np.maximum(self.count, 1), 0.0)
        mx = np.full(self.n, -np.inf)
        np.maximum.at(mx, self.idx[ok], v[ok])
        return np.where(np.isfinite(mx), mx, 0.0)


def vector(level: str, spec: tuple, S: dict, grouper: Grouper | None = None) -> np.ndarray:
    """The values of one form over the level's units, for the result set S."""
    t = spec[0]
    if level == "method":
        m = S["method"]
        if t == "X":
            return m.values[spec[1]]
        if t == "XD":
            return m.values[spec[1]] * fD(method_d(m, spec[2], spec[3]))
        if t == "XO":
            return m.values[spec[1]] * fO(method_out(m, spec[2], spec[3]))
        if t == "D":
            return fD(method_d(m, spec[1], spec[2]))
        if t == "O":
            return fO(method_out(m, spec[1], spec[2]))
        raise ValueError(spec)
    c = S["class"]
    if t == "X":
        return c.values[spec[1]]
    if t == "XD_A":
        return c.values[spec[1]] * fD(class_d(c, spec[2], spec[3]))
    if t == "XO_A":
        return c.values[spec[1]] * fO(c.c[f"out_{spec[2]}"])
    if t == "D_A":
        return fD(class_d(c, spec[1], spec[2]))
    if t == "O_A":
        return fO(c.c[f"out_{spec[1]}"])
    m = S["method"]
    if t == "XD_B":
        f, _ = _method_B(m, spec[3], spec[4])
        return grouper.agg(m.values[spec[1]] * f, spec[2])
    if t == "XO_B":
        f, _ = _method_B(m, spec[3], None)
        return grouper.agg(m.values[spec[1]] * f, spec[2])
    if t == "D_B":
        f, _ = _method_B(m, spec[2], spec[3])
        return grouper.agg(f.astype(float), spec[1])
    if t == "O_B":
        f, _ = _method_B(m, spec[2], None)
        return grouper.agg(f.astype(float), spec[1])
    raise ValueError(spec)


def and_d(level: str, spec: tuple, S: dict) -> np.ndarray:
    """The divergence an AND form's second rule is fitted on."""
    if level == "method":
        return method_d(S["method"], spec[2], "all")
    return class_d(S["class"], spec[2], "np")
