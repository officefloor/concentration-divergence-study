"""The two result sets of one repository, built from its record (PLAN.md, Two result sets):

  joined      paper one's units and complexity (lizard), with the measurer's coupling joined to
              each method by file, name and start line (lizard's start line is the line of the
              method's name, which the measurer records as `name_line`). Decides every verdict.
  javaparser  the measurer's own units and its re-implemented complexity fields. Robustness.

Both are restricted to units in `.java` files (the study is Java only). Per level each set holds
the unit ids, the complexity values of every paper-one signal, the coupling of each unit under
the three definitions, and the definitions (oracles) as boolean masks, with the universe each is
scored on (the reviewed units for a human definition, every unit otherwise).

Coupling (PLAN.md, Units and measures; SINEW.md), per method m with p parameters and, for each
INTERNAL call c (resolved to an analysed file), a(c) arguments:

    flow     in = 1 + p           out = sum(1 + a(c))
    data     in = p               out = sum(a(c))
    message  in = max(p - 1, 1)   out = sum(max(a(c) - 1, 1))

`out` is counted over all internal calls (the method's all-calls variant) and over the calls to
another file only (its no-helpers variant, which is also what leaves the class at class level).
A class's `in` sums the `in` of its methods callable from outside the file: non-private (the
primary input variant) or public; the methods of anonymous and local classes are not members
callable from outside. A unit of paper one's that the join cannot match carries no coupling
(in = out = 0, so d = 0 and both factors are 1: its complexity is unweighted), and so does a file
the measurer could not parse; both are counted in the diagnostics.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from complexity_concentration_study import extract as p1_extract
from complexity_concentration_study import metrics as p1_metrics
from complexity_concentration_study import study as p1

from . import javaparser, measure

DEFS = ("flow", "data", "message")
METHOD_FIELDS = tuple(p1_extract.COMPLEXITY_FIELDS)
CLASS_SIGNALS = tuple(p1_metrics.CLASS_SIGNALS)
AGGS = tuple(p1_metrics.AGGREGATIONS)

# The definitions each set scores, by level: (name, universe) where universe names the
# definition listing the units it is scored on (None: every unit).
CLASS_ORACLES = (("human_blob", "human_blob_reviewed"),
                 ("human_fontana_god_class", "human_fontana_god_class_reviewed"),
                 ("pmd_GodClass", None), ("decor_blob", None), ("wmc47", None))
METHOD_ORACLES = (("human_method_long_method", "human_method_long_method_reviewed"),
                  ("pmd_method_NPath200", None), ("brain_method", None))


def coupling_in(p: np.ndarray, k: str) -> np.ndarray:
    if k == "flow":
        return 1 + p
    if k == "data":
        return p.copy()
    return np.maximum(p - 1, 1)


def call_out(a: int, k: str) -> int:
    if k == "flow":
        return 1 + a
    if k == "data":
        return a
    return max(a - 1, 1)


class Level:
    """One level of one result set: ids, values {signal: array}, coupling arrays, oracles."""

    def __init__(self, ids):
        self.ids = list(ids)
        self.n = len(self.ids)
        self.values: dict = {}
        self.oracles: dict = {}          # name -> (positives mask, universe mask)
        self.coupled = np.zeros(self.n, bool)
        # method level: p, in_k, out_all_k, out_leave_k, callable masks, file index
        # class level: in_k (np / pub), out_k
        self.c: dict = {}

    def add_oracle(self, name, pos_mask, univ_mask=None):
        self.oracles[name] = (pos_mask, univ_mask if univ_mask is not None else np.ones(self.n, bool))


def _method_coupling(m: dict, file_idx: int) -> dict:
    out = {"p": m["params"], "callable_np": (m["vis"] != "private") and not m["local"],
           "callable_pub": (m["vis"] == "public") and not m["local"]}
    for k in DEFS:
        all_, leave = 0, 0
        for a, _kind, res, tidx in m["calls"]:
            if res != javaparser.RES_INTERNAL:
                continue
            v = call_out(a, k)
            all_ += v
            if tidx != file_idx:
                leave += v
        out[f"out_all_{k}"] = all_
        out[f"out_leave_{k}"] = leave
    return out


def _method_arrays(level: Level, coup: list) -> None:
    """Fill the method-level coupling arrays from per-unit dicts (None = not coupled)."""
    n = level.n
    p = np.array([c["p"] if c else 0 for c in coup], dtype=float)
    level.coupled = np.array([c is not None for c in coup], bool)
    level.c["p"] = p
    level.c["callable_np"] = np.array([bool(c and c["callable_np"]) for c in coup])
    level.c["callable_pub"] = np.array([bool(c and c["callable_pub"]) for c in coup])
    for k in DEFS:
        inn = coupling_in(p, k)
        inn[~level.coupled] = 0
        level.c[f"in_{k}"] = inn
        for v in ("all", "leave"):
            level.c[f"out_{v}_{k}"] = np.array([c[f"out_{v}_{k}"] if c else 0 for c in coup], float)
    assert all(len(a) == n for a in level.c.values())


def _class_coupling(level: Level, methods_by_file: dict) -> None:
    """Form A coupling of each file from all the measurer's methods in it."""
    for k in DEFS:
        for key in ("in_np", "in_pub", "out"):
            level.c[f"{key}_{k}"] = np.zeros(level.n)
    coupled = np.zeros(level.n, bool)
    for i, f in enumerate(level.ids):
        ms = methods_by_file.get(f)
        if ms is None:
            continue
        coupled[i] = True
        for m, fidx in ms:
            mc = _method_coupling(m, fidx)
            for k in DEFS:
                ink = float(coupling_in(np.array([mc["p"]], float), k)[0])
                if mc["callable_np"]:
                    level.c[f"in_np_{k}"][i] += ink
                if mc["callable_pub"]:
                    level.c[f"in_pub_{k}"][i] += ink
                level.c[f"out_{k}"][i] += mc[f"out_leave_{k}"]
    level.coupled = coupled


def _measurer_files(doc: dict) -> dict:
    """{path: [(method record, file index)]} over the files the measurer parsed."""
    out = {}
    for fidx, f in enumerate(doc.get("files", [])):
        if f["level"] != "failed":
            out[f["path"]] = [(m, fidx) for m in f["methods"]]
    return out


def _uid_parts(uid: str) -> tuple[str, str, int]:
    path, rest = uid.split("::", 1)
    name, line = rest.rsplit("@", 1)
    return path, name, int(line.rstrip("'"))


def joined(rec: dict) -> dict:
    """{'method': Level, 'class': Level, 'join': stats} for the joined set."""
    units = rec["units"]
    doc = rec["javaparser"]
    jp_files = _measurer_files(doc)
    by_key: dict = defaultdict(list)
    for path, ms in jp_files.items():
        for m, fidx in ms:
            by_key[(path, m["name"], m["name_line"])].append((m, fidx))
    # method level
    mu = units["method"]
    keep = [i for i, u in enumerate(mu["units"]) if u.split("::", 1)[0].endswith(".java")]
    ml = Level([mu["units"][i] for i in keep])
    for s in mu["signals"]:
        ml.values[s] = np.array([mu["values"][s][i] for i in keep], float)
    coup, ambiguous, used = [], 0, set()
    files_of = []
    for i in keep:
        path, name, line = _uid_parts(mu["units"][i])
        files_of.append(path)
        hits = by_key.get((path, name, line), [])
        if len(hits) > 1:
            ambiguous += 1
        if hits:
            m, fidx = hits[0]
            used.add(id(m))
            coup.append(_method_coupling(m, fidx))
        else:
            coup.append(None)
    _method_arrays(ml, coup)
    ml.c["file"] = np.array(files_of, dtype=object)
    pos = {u: j for j, u in enumerate(keep)}
    _oracles_from_idx(ml, mu["god_idx"], pos, METHOD_ORACLES)
    # class level
    cu = units["class"]
    ckeep = [i for i, u in enumerate(cu["units"]) if u.endswith(".java")]
    cl = Level([cu["units"][i] for i in ckeep])
    for s in cu["signals"]:
        cl.values[s] = np.array([cu["values"][s][i] for i in ckeep], float)
    _class_coupling(cl, jp_files)
    cpos = {u: j for j, u in enumerate(ckeep)}
    _oracles_from_idx(cl, cu["god_idx"], cpos, CLASS_ORACLES)
    n_jp = sum(len(ms) for ms in jp_files.values())
    join = {"lizard_units": ml.n, "joined": int(ml.coupled.sum()), "ambiguous": ambiguous,
            "measurer_units": n_jp, "measurer_not_joined": n_jp - len(used),
            "class_units": cl.n, "class_coupled": int(cl.coupled.sum())}
    return {"method": ml, "class": cl, "join": join}


def _oracles_from_idx(level: Level, god_idx: dict, pos: dict, wanted) -> None:
    for name, univ in wanted:
        if name not in god_idx:
            continue
        if univ is not None and univ not in god_idx:
            continue
        p = np.zeros(level.n, bool)
        for g in god_idx[name]:
            if g in pos:
                p[pos[g]] = True
        u = None
        if univ is not None:
            u = np.zeros(level.n, bool)
            for g in god_idx[univ]:
                if g in pos:
                    u[pos[g]] = True
        level.add_oracle(name, p, u)


def javaparser_set(rec: dict) -> dict:
    """{'method': Level, 'class': Level} for the JavaParser-only set."""
    doc = rec["javaparser"]
    jp_files = _measurer_files(doc)
    path_idx = {f["path"]: i for i, f in enumerate(doc.get("files", []))}
    ids, recs, files_of = [], [], []
    for uid, m, path in measure.jp_unit_ids(doc):
        if path in jp_files:
            ids.append(uid)
            recs.append((m, path_idx[path]))
            files_of.append(path)
    ml = Level(ids)
    vals = {f: [] for f in METHOD_FIELDS}
    for m, _ in recs:
        cc, nloc, hvol = m["cc"], m["nloc"], m["hvol"]
        row = {"cc": cc, "cognitive": m["cognitive"], "nloc": nloc, "tokens": m["tokens"],
               "params": m["params"], "nesting": m["nesting"],
               "cyc_density": round(cc / nloc, 4) if nloc > 0 else 0.0,
               "exit_points": m["exit_points"], "hvol": hvol,
               "mi": p1_extract.maintainability_burden(hvol, cc, nloc)}
        for f in METHOD_FIELDS:
            vals[f].append(row[f])
    for f in METHOD_FIELDS:
        ml.values[f] = np.array(vals[f], float)
    _method_arrays(ml, [_method_coupling(m, fi) for m, fi in recs])
    ml.c["file"] = np.array(files_of, dtype=object)
    # method definitions on the measurer's units
    jo = rec.get("jp_oracles") or {}
    pos = {u: i for i, u in enumerate(ids)}

    def mask(uids):
        a = np.zeros(ml.n, bool)
        for u in uids:
            if u in pos:
                a[pos[u]] = True
        return a
    if "human_method_long_method" in jo and "human_method_long_method_reviewed" in jo:
        ml.add_oracle("human_method_long_method", mask(jo["human_method_long_method"]),
                      mask(jo["human_method_long_method_reviewed"]))
    if "pmd_method_NPath200" in jo:
        ml.add_oracle("pmd_method_NPath200", mask(jo["pmd_method_NPath200"]))
    ml.add_oracle("brain_method", (ml.values["nloc"] >= 50) & (ml.values["cc"] >= p1.CC_GOD)
                  & (ml.values["nesting"] >= 5))
    # class level: the files with a measured method, aggregated as paper one aggregates
    files = sorted({p for p in files_of})
    cl = Level(files)
    fidx = {f: i for i, f in enumerate(files)}
    groups = defaultdict(list)
    for j, p in enumerate(files_of):
        groups[fidx[p]].append(j)
    for base in METHOD_FIELDS:
        v = ml.values[base]
        for agg in AGGS:
            cl.values[f"{base}_{agg}"] = np.array(
                [p1_metrics._aggregate(v[groups[i]].tolist(), agg) for i in range(cl.n)], float)
    cl.values["nom"] = np.array([len(groups[i]) for i in range(cl.n)], float)
    _class_coupling(cl, jp_files)
    # class definitions: paper one's file-level positives, wmc47 from the measurer's own cc
    god_idx = rec["units"]["class"]["god_idx"]
    cunits = rec["units"]["class"]["units"]
    named = {name: {cunits[i] for i in idx} for name, idx in god_idx.items()}
    for name, univ in CLASS_ORACLES:
        if name == "wmc47":
            cl.add_oracle(name, cl.values["cc_sum"] >= p1_extract.WMC_GOD)
            continue
        if name not in named or (univ is not None and univ not in named):
            continue
        p = np.array([f in named[name] for f in files])
        u = np.array([f in named[univ] for f in files]) if univ else None
        cl.add_oracle(name, p, u)
    return {"method": ml, "class": cl}


def build(rec: dict) -> dict:
    """Both result sets of one record: {'joined': {...}, 'javaparser': {...}}."""
    return {"joined": joined(rec), "javaparser": javaparser_set(rec)}
