"""The analysis of PLAN.md, in its reporting order (Procedure 6): the diagnostics, the primary,
the leaf diagnostic, the consistency analysis and its verdict on the construct, the secondaries,
the sensitivities, and then the exploratory intersection (PLAN.md, Amendments, 3), which decides
nothing.

    cds analyse                  the confirmatory analysis: results/analysis.json, written once,
                                 with its sha256 beside it
    cds analyse --exploratory    any later analysis: results/analysis.exploratory.<utc>.json
    cds analyse --check          a dry run on the MLCQ EXPLORE half only (no confirm score, no
                                 seed-3 or Fontana score is opened), to find faults in this code
                                 before the confirmatory run: results/analysis.check.<utc>.json

Every analysis reads the decisions of the explore step (decisions/explore-choices.json), and
refuses to run unless that file is committed and unchanged, so the order "choose on explore,
then read confirm" is in the git history. The verdicts are read from the joined set; the
JavaParser-only set is read the same way and each verdict is marked `agrees` or `differs`.

Operational choices the plan leaves to the harness, stated here so they are fixed before any
confirm number exists:
  * populations: the usable repositories with at least one unit in the definition's universe
    (core.Population); MLCQ cells are read on the confirm half.
  * P1 holds when the lower bound of dD is above 0 in BOTH the peak and the density family
    (human Blob, non-ingredient cells, flow); P3 reads outgoing-only when some counted family's
    dDO has its upper bound below 0 and none its lower bound above 0, the balance when the
    reverse, unresolved otherwise.
  * Secondary 2 "track closely": the median within-repository |Spearman| of X* with d_flow is
    at least 0.7. The tertile re-reading is reported whatever it is.
  * The mechanism of a refinement (PLAN.md, Amendments, 4) is read from the exemption-only arm
    in the primary's own variant (flow, non-private) and the leaf diagnostic under flow,
    non-private; "contradicted" is the leaf diagnostic's reading of that name.
  * The consistency bootstrap: one generator (seed 12345) draws, for each replicate, the MLCQ
    confirm, the seed-3 and the Fontana repositories in that order (boot.joint_multiplicities).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter

import numpy as np

from complexity_concentration_study import metrics as p1_metrics
from complexity_concentration_study import stats as p1stats
from complexity_concentration_study import study as p1

from . import boot, core, forms, pins, rules, score, units
from .explore import CHOICES

SETS = ("joined", "javaparser")
CLASS_ORACLES_SEED3 = ("pmd_GodClass", "decor_blob", "wmc47")
METHOD_ORACLES_SEED3 = ("pmd_method_NPath200", "brain_method")
# The class input variant with constructors counted, reported beside the primary (PLAN.md, Amendments, 2).
CTOR = "np+ctor"


# ---------------------------------------------------------------------------------------------
# the decisions
# ---------------------------------------------------------------------------------------------
def committed(path: str) -> str:
    """The commit that last changed `path`; refuses unless it is tracked and unchanged."""
    rel = os.path.relpath(path, pins.PROJECT_ROOT)
    git = ["git", "-C", pins.PROJECT_ROOT]
    if subprocess.run(git + ["ls-files", "--error-unmatch", rel], capture_output=True).returncode:
        raise SystemExit(f"{rel} is not committed: commit the explore choices before the analysis")
    if subprocess.run(git + ["diff", "--quiet", "HEAD", "--", rel]).returncode:
        raise SystemExit(f"{rel} has uncommitted changes")
    return subprocess.run(git + ["log", "-1", "--format=%H %cI", "--", rel], capture_output=True,
                          text=True).stdout.strip()


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def pooled_auc(pop: core.Population, xs: str, ys: str) -> dict:
    """The threshold-free comparison: the pooled AUC of the per-repository modified z of ys
    against xs over the reviewed units, and the paired difference with its interval."""
    zx, zy, lab, rep = [], [], [], []
    for i, e in enumerate(pop.extracts):
        if not e or xs not in e["z"] or ys not in e["z"]:
            continue
        zx.append(np.array(e["z"][xs]))
        zy.append(np.array(e["z"][ys]))
        lab.append(np.array(e["label"], bool))
        rep.append(i)
    if not rep:
        return {"x": None, "y": None, "diff": None}

    def aucs(weights):
        X = np.concatenate([np.repeat(a, w) for a, w in zip(zx, weights)])
        Y = np.concatenate([np.repeat(a, w) for a, w in zip(zy, weights)])
        L = np.concatenate([np.repeat(a, w) for a, w in zip(lab, weights)])
        ax, ay = boot.auc(X[L], X[~L]), boot.auc(Y[L], Y[~L])
        return ax, ay
    ax, ay = aucs([1] * len(rep))
    m = pop.m[:, rep]
    reps = []
    for row in m:
        a, b = aucs(row)
        reps.append(np.nan if a is None or b is None else b - a)
    full = None if ax is None or ay is None else ay - ax
    return {"x": ax, "y": ay, "diff": boot.interval(full, np.array(reps), len(rep), len(m)),
            "reading": None}


def leaf(pop: core.Population, x: str, k: str, inp: str) -> dict:
    """Secondary 1: among the reviewed units X* flags, the positive rate of catchments minus the
    rest's, pooled, with its paired interval over repositories."""
    key = f"{x}|{k}|{inp}"
    c = np.array([e["leaf"][key] if e and key in e["leaf"] else [0, 0, 0, 0] for e in pop.extracts], float)
    if len(c) == 0:
        return {"key": key, "diff": None, "reading": "not estimable"}

    def stat(s):
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where((s[..., 0] > 0) & (s[..., 2] > 0), s[..., 1] / s[..., 0] - s[..., 3] / s[..., 2], np.nan)
    tot = c.sum(0)
    full = float(stat(tot)) if tot[0] > 0 and tot[2] > 0 else None
    iv = boot.interval(full, stat(pop.m @ c), len(c), len(pop.m))
    r = boot.reading(iv, "contradicted (catchments are called positive MORE often)",
                     "supported (catchments are called positive less often)", "unresolved")
    return {"key": key, "catchment": {"flagged": tot[0], "positive": tot[1]},
            "rest": {"flagged": tot[2], "positive": tot[3]}, "diff": iv, "reading": r}


BY_EXEMPTION = "by the exemption: the claim in the question is supported"
BY_AMPLIFICATION = ("by amplification: the gain comes from multiplying junctions, and the claim that "
                    "setting complex leaves aside refines complexity is not supported")


def mechanism(primary: dict, exemption_only: dict, leaf_flow: dict) -> dict:
    """PLAN.md, Amendments, 4: when the primary reads refinement, whether the exemption carries
    it (the exemption-only arm also refines and the leaf diagnostic is not contradicted) or the
    amplification does."""
    if primary["reading"] != core.REFINES:
        return {"reading": "not read: the primary does not read refinement",
                "exemption_only": exemption_only["reading"], "leaf": leaf_flow["reading"]}
    by_exemption = (exemption_only["reading"] == core.REFINES
                    and not leaf_flow["reading"].startswith("contradicted"))
    return {"reading": BY_EXEMPTION if by_exemption else BY_AMPLIFICATION,
            "exemption_only": exemption_only["reading"], "leaf": leaf_flow["reading"]}


def decomposition(pop: core.Population, x: str, level: str, k: str = "flow",
                  variant: str | None = None) -> dict:
    """Secondary 8 (PLAN.md, Amendments, 4): the two halves of the divergence factor on their
    own against X*, and the primary arm against each."""
    D, E, A = (core.factor_arm(f, level, x, k, variant) for f in "DEA")
    return {"exemption_only": core.compare(pop, x, E, better="the exemption refines complexity",
                                           worse="the exemption makes it worse"),
            "amplification_only": core.compare(pop, x, A, better="the amplification refines complexity",
                                               worse="the amplification makes it worse"),
            "D_vs_exemption_only": core.compare(pop, E, D, better="the whole factor beats exemption only",
                                                worse="exemption only beats the whole factor"),
            "D_vs_amplification_only": core.compare(pop, A, D, better="the whole factor beats amplification only",
                                                    worse="amplification only beats the whole factor")}


BEYOND_SIZE = "beyond size: the coupling factor beats the size factor"
SIZE_BETTER = "the size factor beats the coupling factor"
NOT_DISTINGUISHED = "not distinguished from a size weighting"


def size_null(pop: core.Population, x: str) -> dict:
    """Secondary 9 (PLAN.md, Amendments, 5): the primary arm against the size null X*·N (X*
    times the class's number of methods, no coupling), and the size null against X*."""
    N = forms.name(("XN", x))
    D = core.primary_arm("class", x)
    return {"size_null": N,
            "N_vs_X": core.compare(pop, x, N, better="the size factor refines complexity",
                                   worse="the size factor makes it worse"),
            "D_vs_N": core.compare(pop, N, D, better=BEYOND_SIZE, worse=SIZE_BETTER,
                                   neither=NOT_DISTINGUISHED)}


def tertiles(pop: core.Population, x: str, k: str = "flow") -> list:
    key = f"{x}|{k}"
    out = []
    for t in range(3):
        cx = np.array([e["tertile"][key][t][0] if e and key in e["tertile"] else [0, 0, 0, 0]
                       for e in pop.extracts])
        cy = np.array([e["tertile"][key][t][1] if e and key in e["tertile"] else [0, 0, 0, 0]
                       for e in pop.extracts])
        iv = boot.micro_diff(cx, cy, pop.m) if len(cx) else None
        out.append({"tertile": t + 1, "micro": iv, "reading": boot.reading(
            iv, "the divergence factor refines complexity", "it makes it worse")})
    return out


def independence(pops: dict, level: str, x: str) -> dict:
    out = {}
    for label, pop in pops.items():
        d = {}
        for k in units.DEFS:
            for what in ("d", "out"):
                for sig in (units.CLASS_SIGNALS if level == "class" else units.METHOD_FIELDS):
                    vals = [lv["spearman"].get(f"{sig}|{what}_{k}") for lv in pop.lv]
                    vals = [v for v in vals if v is not None]
                    if vals:
                        d[f"{sig}|{what}_{k}"] = {"median": float(np.median(vals)), "n": len(vals)}
        out[label] = d
    return out


def matrix_by_family(pop: core.Population) -> dict:
    """Secondary 4: every form against its base signal, under every rule, with paired intervals
    (exploratory), and Friedman tests over repositories across the forms X, X*D_k, X*O_k within
    each family."""
    level = pop.level
    specs = forms.SPECS[level]
    names = [forms.name(s) for s in specs]
    base_idx = []
    for s in specs:
        b = forms.base(s)
        base_idx.append(forms.INDEX[level].get(b) if (b is not None and s[0] != "X") else None)
    out = {"population": pop.label, "n_repos": pop.n, "rows": []}
    if pop.n == 0:
        return out
    m = pop.m.astype(float)
    has = (pop.C[:, 0, core.MAD, 0] > 0).astype(float)
    ok = (m @ has) > 0
    for r, rule in enumerate(rules.ORDER):
        C = pop.C[:, :, r, :].astype(float)                       # [R, F, 4]
        full = boot.mcc_counts(C.sum(0))                           # [F]
        S = (m @ C.reshape(pop.n, -1)).reshape(len(m), len(specs), 4)
        reps = boot.mcc_counts(S)                                  # [B, F]
        for f, bi in enumerate(base_idx):
            row = {"form": names[f], "rule": rule, "mcc": float(full[f])}
            if bi is not None:
                d = np.where(ok, reps[:, f] - reps[:, bi], np.nan)
                row["diff_vs_base"] = boot.interval(float(full[f] - full[bi]), d, pop.n, len(m))
            out["rows"].append(row)
    # Friedman across forms within each family (mad_z; per repository, the family's mean MCC)
    fams = p1_metrics.FAMILIES[level]
    per = boot.per_item_mcc(pop.C[:, :, core.MAD, :])            # [R, F]
    fr = {}
    for fam, sigs in fams.items():
        for k in units.DEFS:
            arms = {"X": [forms.INDEX[level][s] for s in sigs]}
            if level == "class":
                arms["X*D"] = [forms.INDEX[level][forms.name(("XD_A", s, k, "np"))] for s in sigs]
                arms["X*O"] = [forms.INDEX[level][forms.name(("XO_A", s, k))] for s in sigs]
            else:
                arms["X*D"] = [forms.INDEX[level][forms.name(("XD", s, k, "all"))] for s in sigs]
                arms["X*O"] = [forms.INDEX[level][forms.name(("XO", s, k, "all"))] for s in sigs]
            rows_ = [{a: float(per[i, idx].mean()) for a, idx in arms.items()} for i in range(pop.n)]
            res = p1stats.friedman(rows_)
            fr[f"{fam}|{k}"] = res
    out["friedman"] = fr
    return out


# ---------------------------------------------------------------------------------------------
# the exploratory intersection
# ---------------------------------------------------------------------------------------------
def _regions(cx: np.ndarray, cd: np.ndarray, ca: np.ndarray) -> dict:
    """[..., 4] counts (n_univ, n_flagged, n_flagged_positive, n_positive) of the two flag sets X
    and d and of their intersection, to the counts of every region by inclusion-exclusion."""
    def mk(f, tp):
        out = cx.copy()
        out[..., 1], out[..., 2] = f, tp
        return out
    return {"X": cx, "d": cd, "both": ca,
            "X_only": mk(cx[..., 1] - ca[..., 1], cx[..., 2] - ca[..., 2]),
            "d_only": mk(cd[..., 1] - ca[..., 1], cd[..., 2] - ca[..., 2]),
            "either": mk(cx[..., 1] + cd[..., 1] - ca[..., 1], cx[..., 2] + cd[..., 2] - ca[..., 2])}


def intersection(pop: core.Population, x: str) -> dict:
    """PLAN.md, Amendments, 3 (exploratory): the units the rule (mad_z) flags on complexity X and
    on the coupling divergence d_k, each on its own, and where the definition's positives fall:
    X only, d only, both (the AND form), either. The same with the outgoing factor O_k in place of
    d_k. Per definition k and variant (method: all calls, no helpers; class: the four input
    variants), pooled counts with precision, recall and MCC per region, and paired micro MCC
    differences against X of `both`, `either` and the second set alone."""
    level = pop.level
    out = {"population": pop.label, "n_repos": pop.n, "x": x, "rule": "mad_z", "cells": {}}
    if pop.n == 0:
        return out
    variants = forms.VARIANTS if level == "method" else forms.INPUTS
    for k in units.DEFS:
        for v in variants:
            for second in ("d", "o"):
                if second == "d":
                    sv = ("d", k, v) if level == "method" else ("d_A", k, v)
                    andf = ("AND", x, k, v)
                elif level == "method":
                    sv, andf = ("O", k, v), ("ANDO", x, k, v)
                elif v == "np":                       # O_k[A] has no input variants
                    sv, andf = ("O_A", k), ("ANDO", x, k)
                else:
                    continue
                cx, cd, ca = (pop.counts(n) for n in (x, forms.name(sv), forms.name(andf)))
                per = _regions(cx, cd, ca)              # per repository
                pooled = {r: {"mcc": float(boot.mcc_counts(c.sum(0))), **boot.rates(c.sum(0))}
                          for r, c in per.items()}
                cell = {"second": forms.name(sv), "and": forms.name(andf), "pooled": pooled,
                        "vs_X": {r: boot.micro_diff(cx, per[r], pop.m) for r in ("both", "either", "d")}}
                for r, iv in cell["vs_X"].items():
                    cell[f"vs_X_{r}_reading"] = boot.reading(iv, "the second is better", "X is better")
                key = f"{k}|{v}" + ("" if second == "d" else "|O")
                out["cells"][key] = cell
    return out


# ---------------------------------------------------------------------------------------------
# the consistency analysis
# ---------------------------------------------------------------------------------------------
def _ingredients(oracle: str) -> set:
    return p1.ingredients(oracle) if oracle in p1.ORACLES else set()


def consistency(pops: list[core.Population], set_index: dict, M: dict, set_name: str,
                inp: str = "np") -> dict:
    """PLAN.md, Does the construct hold up. pops: the (oracle) populations, each tagged with the
    measured set it comes from (set_index[label] = (set, positions of its repos in that set)).
    inp: the class input variant of the class cells (np: non-private methods, the primary)."""
    cells = []
    B = pins.BOOTSTRAP_B
    for pop in pops:
        if pop.n == 0:
            continue
        sname, pos = set_index[pop.label]
        m = M[sname][:, pos].astype(float)
        ok = (m @ (pop.C[:, 0, core.MAD, 0] > 0).astype(float)) > 0
        level = pop.level
        ing = _ingredients(pop.oracle)
        C = pop.C[:, :, core.MAD, :].astype(float)
        full = boot.mcc_counts(C.sum(0))
        reps = boot.mcc_counts((m @ C.reshape(pop.n, -1)).reshape(B, C.shape[1], 4))
        reps[~ok] = np.nan
        for fam, sigs in p1_metrics.FAMILIES[level].items():
            for rel in ("ingredient", "non-ingredient"):
                ss = [s for s in sigs if (s in ing) == (rel == "ingredient")]
                if not ss:
                    continue
                for k in units.DEFS:
                    ix = [forms.INDEX[level][s] for s in ss]
                    if level == "class":
                        iD = [forms.INDEX[level][forms.name(("XD_A", s, k, inp))] for s in ss]
                        iO = [forms.INDEX[level][forms.name(("XO_A", s, k))] for s in ss]
                    else:
                        iD = [forms.INDEX[level][forms.name(("XD", s, k, "all"))] for s in ss]
                        iO = [forms.INDEX[level][forms.name(("XO", s, k, "all"))] for s in ss]
                    est = {"dD": (full[iD] - full[ix]).mean(), "dO": (full[iO] - full[ix]).mean(),
                           "dDO": (full[iD] - full[iO]).mean()}
                    rep = {"dD": (reps[:, iD] - reps[:, ix]).mean(1), "dO": (reps[:, iO] - reps[:, ix]).mean(1),
                           "dDO": (reps[:, iD] - reps[:, iO]).mean(1)}
                    counted = rel == "non-ingredient" and pop.oracle != "pmd_GodClass"
                    cells.append({"oracle": pop.oracle, "population": pop.label, "level": level,
                                  "family": fam, "relation": rel, "k": k, "signals": ss,
                                  "counted": counted, "n_repos": pop.n, "_rep": rep,
                                  **{d: boot.interval(float(est[d]), rep[d], pop.n, B) for d in est}})
    # between definitions, same oracle/family/relation
    by = {(c["oracle"], c["family"], c["relation"], c["k"]): c for c in cells}
    between = []
    for (o, fam, rel, k), c in by.items():
        if k != "flow":
            continue
        for a, b_ in (("flow", "data"), ("message", "flow")):
            ca, cb = by.get((o, fam, rel, a)), by.get((o, fam, rel, b_))
            if not ca or not cb or not ca["dD"] or not cb["dD"]:
                continue
            between.append({"oracle": o, "family": fam, "relation": rel, "compare": f"dD({a}) - dD({b_})",
                            "diff": boot.interval(ca["dD"]["value"] - cb["dD"]["value"],
                                                  ca["_rep"]["dD"] - cb["_rep"]["dD"], ca["n_repos"], B)})
    preds = {k: predictions(by, k) for k in units.DEFS}
    for c in cells:
        c.pop("_rep")
        for d in ("dD", "dO", "dDO"):
            c[f"{d}_reading"] = boot.reading(c[d], "the first is better", "the second is better")
    return {"set": set_name, "class_inputs": inp, "cells": cells, "between_definitions": between, "predictions": preds,
            "verdict": preds["flow"]["verdict"]}


def predictions(by: dict, k: str) -> dict:
    B = pins.BOOTSTRAP_B

    def cell(o, fam, rel="non-ingredient"):
        return by.get((o, fam, rel, k))

    def lo_pos(iv):
        return iv is not None and iv["lo"] > 0

    def hi_neg(iv):
        return iv is not None and iv["hi"] < 0
    blob = "human_blob"
    p1d = {fam: (cell(blob, fam) or {}).get("dD") for fam in ("peak", "density")}
    p1o = {fam: (cell(blob, fam) or {}).get("dO") for fam in ("peak", "density")}
    P1 = all(lo_pos(v) for v in p1d.values())
    P1_O = all(lo_pos(v) for v in p1o.values())
    # P2: peak (class) / structure (method) minus size, for every counted oracle
    p2 = []
    for (o, fam, rel, kk), c in by.items():
        if kk != k or rel != "non-ingredient" or fam not in ("peak", "structure"):
            continue
        size = by.get((o, "size", "non-ingredient", k))
        if not size or c["dD"] is None or size["dD"] is None:
            continue
        p2.append({"oracle": o, "compare": f"dD({fam}) - dD(size)",
                   "diff": boot.interval(c["dD"]["value"] - size["dD"]["value"],
                                         c["_rep"]["dD"] - size["_rep"]["dD"], c["n_repos"], B)})
    p2_blob = [p for p in p2 if p["oracle"] == blob]
    P2 = bool(p2_blob) and lo_pos(p2_blob[0]["diff"])
    # P3: dDO for human Blob in the counted families
    p3 = {fam: (cell(blob, fam) or {}).get("dDO") for fam in ("size", "peak", "density")}
    any_bal = any(lo_pos(v) for v in p3.values())
    any_out = any(hi_neg(v) for v in p3.values())
    P3 = "the balance" if any_bal and not any_out else ("outgoing-only" if any_out and not any_bal else "unresolved")
    # P4: counted cells of the tool oracles
    tools = [c for (o, fam, rel, kk), c in by.items()
             if kk == k and c["counted"] and o in ("decor_blob", "wmc47", "pmd_method_NPath200", "brain_method")]
    pos = [c for c in tools if c["dD"] is not None and c["dD"]["value"] > 0]
    P4 = {"counted_tool_cells": len(tools), "dD_positive": len(pos),
          "majority": len(tools) > 0 and len(pos) * 2 > len(tools),
          "cells": [{"oracle": c["oracle"], "family": c["family"], "dD": c["dD"]} for c in tools]}
    nonsize = [cell(blob, fam) for fam in ("peak", "density")]
    any_lo = any(c and (lo_pos(c["dD"]) or lo_pos(c["dO"])) for c in nonsize)
    if any(v is None for v in p1d.values()):
        verdict = "not estimable"            # no interval for human Blob in peak or density
    elif P1 and P3 != "outgoing-only":
        verdict = "supported"
    elif P1_O and P3 == "outgoing-only":
        verdict = "outgoing data only"
    elif not any_lo:
        verdict = "not supported"
    else:
        verdict = "unresolved"
    return {"P1": {"holds": P1, "dD": p1d, "dO_holds": P1_O, "dO": p1o}, "P2": {"holds_human_blob": P2, "cells": p2},
            "P3": {"reads": P3, "dDO": p3}, "P4": P4, "verdict": verdict}


# ---------------------------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------------------------
def diagnostics(scores: list[dict], label: str, xc: str | None, xm: str | None) -> dict:
    metas = [s["meta"] for s in scores]
    usable = [m for m in metas if m.get("usable") and not m.get("error")]
    res = Counter()
    pruned = Counter()
    di = Counter()
    owners = Counter(m["full_name"].split("/")[0].lower() for m in usable)
    join = Counter()
    labels = Counter()
    for s in scores:
        m = s["meta"]
        for k, v in ((m.get("javaparser") or {}).get("calls") or {}).items():
            res[k] += v
        for seg, v in ((m.get("pruned") or {}).get("by_segment") or {}).items():
            pruned[seg] += v
        for fw in m.get("di") or []:
            di[fw] += 1
        for k, v in (s.get("join") or {}).items():
            join[k] += v
        for lab, d in (m.get("human_labels") or {}).items():
            labels[f"{lab}|labelled"] += d.get("labelled", 0)
            labels[f"{lab}|measured"] += d.get("measured", 0)
        for lab, v in (m.get("labels_out_of_scope") or {}).items():
            labels[f"{lab}|on_deleted_files"] += v
    tot = sum(res.values())
    out = {"set": label, "measured": len(metas), "usable": len(usable),
           "errors": [m["key"] for m in metas if m.get("error")],
           "harness_commits": sorted({str(m.get("harness_commit")) for m in metas}),
           "calls": {k: v / tot for k, v in res.items()} if tot else {},
           "join": dict(join), "pruned_by_segment": dict(pruned),
           "di": {"repositories_declaring": sum(1 for m in usable if m.get("di")), "by_framework": dict(di)},
           "owners_top": owners.most_common(10),
           "owner_top_share": (owners.most_common(1)[0][1] / len(usable)) if usable else None,
           "labels": dict(labels), "scale_kinds": {}, "roles": {}}
    for sname in SETS:
        for level, x in (("class", xc), ("method", xm)):
            if x is None:
                continue
            arms = [x, core.primary_arm(level, x)]
            kinds = {}
            for a in arms:
                fi = forms.INDEX[level][a]
                ks = Counter()
                zs = []
                for s in scores:
                    lv = (s.get("sets") or {}).get(sname, {}).get(level)
                    if not lv:
                        continue
                    ks[{0: "mad", 1: "mean_ad", 2: "constant"}.get(int(lv["scale"][fi]), "?")] += 1
                    zs.append(float(lv["zero"][fi]))
                kinds[a] = {"scale": dict(ks), "zero_share_median": float(np.median(zs)) if zs else None}
            out["scale_kinds"][f"{sname}|{level}"] = kinds
            roles = Counter()
            for s in scores:
                lv = (s.get("sets") or {}).get(sname, {}).get(level)
                for key, (nu, area) in ((lv or {}).get("roles") or {}).items():
                    roles[f"{key}|units"] += nu
                    roles[f"{key}|cc"] += area
            out["roles"][f"{sname}|{level}"] = dict(roles)
    return out


# ---------------------------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------------------------
def _load(results: str, halves=None) -> list[dict]:
    if not os.path.exists(os.path.join(results, "study.json")):
        return []
    return score.load_all(results, halves)


def analyse(check: bool = False) -> dict:
    choices = json.load(open(CHOICES))
    choices_commit = committed(CHOICES)
    xc, xm = choices["class"]["chosen"], choices["method"]["chosen"]
    gate_n = choices["gate"]["n_required"]
    half = "explore" if check else "confirm"
    mlcq = _load(os.path.join(pins.RESULTS, "mlcq"), (half,))
    seed3 = [] if check else _load(os.path.join(pins.RESULTS, "seed3"))
    fontana = [] if check else _load(os.path.join(pins.RESULTS, "fontana"))
    code = score.scoring_code()
    stale = [s["meta"]["key"] for s in mlcq + seed3 + fontana if s["meta"].get("scoring_code") != code]
    if stale:
        raise SystemExit(f"{len(stale)} scores were made by other scoring code (e.g. {stale[:3]}): "
                         f"re-run `cds score` on each set first")
    out = {"made_utc": _now(), "harness_commit": pins.harness_commit(), "check_on_explore": check,
           "scoring_code": code,
           "decisions": {"file": os.path.relpath(CHOICES, pins.PROJECT_ROOT), "commit": choices_commit,
                         "X*_class": xc, "X*_method": xm, "gate": choices["gate"]},
           "constants": {"rule": pins.OUTLIER_RULE, "bootstrap": [pins.BOOTSTRAP_B, pins.BOOTSTRAP_SEED],
                         "mlcq_half": half}}
    # 0. diagnostics
    out["diagnostics"] = {"mlcq": diagnostics(mlcq, f"MLCQ {half}", xc, xm),
                          "seed3": diagnostics(seed3, "seed 3", xc, xm) if seed3 else None,
                          "fontana": diagnostics(fontana, "Fontana", xc, None) if fontana else None,
                          "validation": {n: _maybe(os.path.join(pins.RESULTS, n, "validation.json"))
                                         for n in ("validation", "mlcq", "seed3", "fontana")}}
    out["diagnostics"]["validation"]["mlcq_explore"] = _maybe(os.path.join(pins.DECISIONS, "measurer-validation.mlcq-explore.json"))
    pops = {}
    for sname in SETS:
        pops[sname] = {
            "blob": core.Population(mlcq, sname, "class", "human_blob", f"MLCQ {half}, human Blob [{sname}]"),
            "long": core.Population(mlcq, sname, "method", "human_method_long_method",
                                    f"MLCQ {half}, human Long Method [{sname}]"),
            "fontana": core.Population(fontana, sname, "class", "human_fontana_god_class", f"Fontana God Class [{sname}]"),
            **{o: core.Population(seed3, sname, "class", o, f"seed 3, {o} [{sname}]") for o in CLASS_ORACLES_SEED3},
            **{o: core.Population(seed3, sname, "method", o, f"seed 3, {o} [{sname}]") for o in METHOD_ORACLES_SEED3}}
    # 1. the primary
    out["primary"] = {}
    for sname in SETS:
        pop = pops[sname]["blob"]
        y = core.primary_arm("class", xc)
        c = core.compare(pop, xc, y)
        n_pos = int(pop.with_positive().sum())
        c["gate"] = {"required": gate_n, "repos_with_reviewed_blob": n_pos, "underpowered": n_pos < (gate_n or 0)}
        c["verdict"] = c["reading"] + (" (underpowered)" if c["gate"]["underpowered"] else "")
        c["pooled_auc"] = pooled_auc(pop, xc, f"{xc}|D_flow")
        c["pooled_auc"]["reading"] = boot.reading((c["pooled_auc"] or {}).get("diff"))
        c["decomposition"] = decomposition(pop, xc, "class")
        c["size_null"] = size_null(pop, xc)
        out["primary"][sname] = c
    out["primary"]["javaparser"]["robustness"] = (
        "agrees" if out["primary"]["javaparser"]["reading"] == out["primary"]["joined"]["reading"] else "differs")
    # 1b. constructors counted in the class's inputs (PLAN.md, Amendments, 2): the same estimand,
    # marked agrees or differs, and the two arms against each other
    for sname in SETS:
        pop = pops[sname]["blob"]
        w = core.compare(pop, xc, core.primary_arm("class", xc, variant=CTOR))
        w["constructors"] = "agrees" if w["reading"] == out["primary"][sname]["reading"] else "differs"
        out["primary"][sname]["with_constructors"] = w
        out["primary"][sname]["methods_vs_with_constructors"] = core.compare(
            pop, core.primary_arm("class", xc, variant=CTOR), core.primary_arm("class", xc),
            better="methods only is better", worse="with constructors is better")
    # 2. the leaf diagnostic
    out["leaf"] = {sname: {f"{k}|{i}": leaf(pops[sname]["blob"], xc, k, i) for k in units.DEFS for i in forms.INPUTS}
                   for sname in SETS}
    _agree(out["leaf"])
    # 2b. the mechanism of a refinement (PLAN.md, Amendments, 4), read from the primary, the
    # exemption-only arm and the leaf diagnostic in the primary's variant
    for sname in SETS:
        p = out["primary"][sname]
        p["mechanism"] = mechanism(p, p["decomposition"]["exemption_only"], out["leaf"][sname]["flow|np"])
    out["primary"]["javaparser"]["mechanism"]["robustness"] = (
        "agrees" if out["primary"]["javaparser"]["mechanism"]["reading"]
        == out["primary"]["joined"]["mechanism"]["reading"] else "differs")
    # 3. the consistency analysis
    sets_rows = {"mlcq": [s for s in mlcq if s["meta"].get("usable") and not s["meta"].get("error")],
                 "seed3": [s for s in seed3 if s["meta"].get("usable") and not s["meta"].get("error")],
                 "fontana": [s for s in fontana if s["meta"].get("usable") and not s["meta"].get("error")]}
    M = boot.joint_multiplicities({k: len(v) for k, v in sets_rows.items()})
    key_pos = {k: {s["meta"]["key"]: i for i, s in enumerate(v)} for k, v in sets_rows.items()}
    out["consistency"] = {}
    for sname in SETS:
        plist, index = [], {}
        for name, pop in pops[sname].items():
            src = "mlcq" if name in ("blob", "long") else ("fontana" if name == "fontana" else "seed3")
            index[pop.label] = (src, [key_pos[src][m["key"]] for m in pop.meta])
            plist.append(pop)
        out["consistency"][sname] = consistency(plist, index, M, sname)
        w = consistency(plist, index, M, sname, inp=CTOR)
        w["constructors"] = "agrees" if w["verdict"] == out["consistency"][sname]["verdict"] else "differs"
        out["consistency"][sname]["with_constructors"] = w
    out["consistency"]["javaparser"]["robustness"] = (
        "agrees" if out["consistency"]["javaparser"]["verdict"] == out["consistency"]["joined"]["verdict"] else "differs")
    # 4. the secondaries
    sec = {}
    for sname in SETS:
        P = pops[sname]
        s = {}
        s["independence"] = independence({"MLCQ": P["blob"], **({"seed 3": P["pmd_GodClass"]} if seed3 else {})}, "class", xc)
        s["independence_method"] = independence({"MLCQ": P["long"]}, "method", xm)
        med = ((s["independence"].get("MLCQ") or {}).get(f"{xc}|d_flow") or {}).get("median")
        s["track_closely"] = None if med is None else abs(med) >= 0.7
        s["tertiles"] = tertiles(P["blob"], xc)
        arms = [forms.name(("XD_A", xc, k, "np")) for k in ("data", "message")]
        arms += [forms.name(("XO_A", xc, k)) for k in units.DEFS]
        arms += [forms.name(("D_A", k, "np")) for k in units.DEFS] + [forms.name(("O_A", k)) for k in units.DEFS]
        arms += [forms.name(("AND", xc, k, "np")) for k in units.DEFS]
        arms += [forms.name(("XD_A", xc, k, i)) for i in forms.INPUTS if i != "np" for k in units.DEFS]
        arms += [forms.name(("D_A", k, CTOR)) for k in units.DEFS]
        base, agg = xc.rsplit("_", 1)
        if base in units.METHOD_FIELDS and agg in units.AGGS:
            arms += [forms.name(("XD_B", base, agg, k, i)) for k in units.DEFS for i in forms.INPUTS]
            arms += [forms.name(("XO_B", base, agg, k)) for k in units.DEFS]
        s["other_arms"] = [core.compare(P["blob"], xc, a) for a in arms]
        s["matrix"] = {name: matrix_by_family(P[name]) for name in P if P[name].n}
        ym = core.primary_arm("method", xm)
        s["method"] = {"all_calls": core.compare(P["long"], xm, ym),
                       "no_helpers": core.compare(P["long"], xm, core.primary_arm("method", xm, variant="nohelp")),
                       "no_helpers_vs_all": core.compare(P["long"], ym, core.primary_arm("method", xm, variant="nohelp"),
                                                         better="no helpers is better", worse="all calls is better"),
                       "leaf": {k: leaf(P["long"], xm, k, "all") for k in units.DEFS},
                       "decomposition": decomposition(P["long"], xm, "method")}
        s["method"]["mechanism"] = mechanism(s["method"]["all_calls"], s["method"]["decomposition"]["exemption_only"],
                                             s["method"]["leaf"]["flow"])
        s["tool_oracles"] = {o: core.compare(P[o], xc, core.primary_arm("class", xc)) for o in CLASS_ORACLES_SEED3}
        s["tool_oracles_with_constructors"] = {
            o: core.compare(P[o], xc, core.primary_arm("class", xc, variant=CTOR)) for o in CLASS_ORACLES_SEED3}
        s["tool_oracles"].update({o: core.compare(P[o], xm, ym) for o in METHOD_ORACLES_SEED3})
        s["tool_oracles_caveat"] = ("PMD GodClass contains a coupling measure (ATFD), so agreement is "
                                    "partly circular; tool oracles are never the headline")
        s["fontana"] = {"paired": core.compare(P["fontana"], xc, core.primary_arm("class", xc)),
                        "paired_with_constructors": core.compare(
                            P["fontana"], xc, core.primary_arm("class", xc, variant=CTOR)),
                        "leaf": {f"{k}|{i}": leaf(P["fontana"], xc, k, i) for k in units.DEFS for i in forms.INPUTS},
                        "note": "read only as the paired difference, never as an absolute level"}
        sec[sname] = s
    out["secondary"] = sec
    # 5. the sensitivities
    sens = {}
    for sname in SETS:
        pop = pops[sname]["blob"]
        no_di = pop.subset(np.array([not m.get("di") for m in pop.meta], bool))
        no_di.label = pop.label + ", without repositories declaring a DI framework"
        no_budget = pop.subset(np.array([not (m.get("javaparser") or {}).get("budget_exhausted")
                                         for m in pop.meta], bool))
        no_budget.label = pop.label + ", without repositories whose call resolution ran out of time"
        sens[sname] = {"without_di": core.compare(no_di, xc, core.primary_arm("class", xc)),
                       "without_budget_exhausted": core.compare(no_budget, xc, core.primary_arm("class", xc)),
                       "budget_exhausted_repos": [m["key"] for m in pop.meta
                                                  if (m.get("javaparser") or {}).get("budget_exhausted")]}
    out["sensitivity"] = sens
    # 6. exploratory, deciding nothing: the intersection of the complexity and divergence outliers
    out["exploratory_intersection"] = {
        sname: {name: intersection(pop, xm if pop.level == "method" else xc)
                for name, pop in pops[sname].items() if pop.n}
        for sname in SETS}
    return out


def _agree(by_set: dict) -> None:
    for key, v in by_set["javaparser"].items():
        v["robustness"] = "agrees" if v["reading"] == by_set["joined"][key]["reading"] else "differs"


def _maybe(path: str):
    return json.load(open(path)) if os.path.exists(path) else None


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(iv) -> str:
    return "n/a" if not iv else f"{iv['value']:+.3f} [{iv['lo']:+.3f}, {iv['hi']:+.3f}] (n={iv['n']})"


def print_report(a: dict) -> None:
    d = a["decisions"]
    print(f"\n=== {'CHECK on the explore half' if a['check_on_explore'] else 'analysis'} "
          f"(harness {a['harness_commit']}); decisions {d['commit']} ===")
    for name, dg in a["diagnostics"].items():
        if not dg or name == "validation":
            continue
        print(f"\n-- diagnostics: {dg['set']}: {dg['usable']} usable of {dg['measured']}, errors "
              f"{len(dg['errors'])}; calls {({k: round(v, 3) for k, v in dg['calls'].items()})}; "
              f"DI declared in {dg['di']['repositories_declaring']}; top owner share {dg['owner_top_share']}")
    for sname in SETS:
        p = a["primary"][sname]
        print(f"\n-- PRIMARY [{sname}] {p['y']} minus {p['x']}, mad_z, {p['population']}: "
              f"{_fmt(p['micro'])} -> {p['verdict']}" + (f"  [{p.get('robustness')}]" if sname != "joined" else ""))
        for arm, v in p["arms"].items():
            print(f"     {arm}: MCC {v['mcc']}, precision {v['precision']}, recall {v['recall']}, FPR {v['fpr']}")
        print(f"     macro {_fmt(p['macro'])}; pooled AUC {p['pooled_auc'].get('x')} -> "
              f"{p['pooled_auc'].get('y')}, diff {_fmt(p['pooled_auc'].get('diff'))}; gate {p['gate']}")
        w = p["with_constructors"]
        print(f"     with constructors in the inputs: {_fmt(w['micro'])} -> {w['reading']} "
              f"[{w['constructors']}]; methods only minus with: {_fmt(p['methods_vs_with_constructors']['micro'])}")
        dc = p["decomposition"]
        print(f"     exemption only {_fmt(dc['exemption_only']['micro'])} -> {dc['exemption_only']['reading']}; "
              f"amplification only {_fmt(dc['amplification_only']['micro'])} -> {dc['amplification_only']['reading']}")
        print(f"     mechanism: {p['mechanism']['reading']}" + (f"  [{p['mechanism'].get('robustness')}]" if sname != "joined" else ""))
        sn = p["size_null"]
        print(f"     size null {sn['size_null']}: vs X* {_fmt(sn['N_vs_X']['micro'])}; X*D minus it "
              f"{_fmt(sn['D_vs_N']['micro'])} -> {sn['D_vs_N']['reading']}")
    for sname in SETS:
        print(f"\n-- leaf diagnostic [{sname}]")
        for key, v in a["leaf"][sname].items():
            print(f"     {key}: {_fmt(v['diff'])} -> {v['reading']}" + (f" [{v.get('robustness')}]" if sname != "joined" else ""))
    for sname in SETS:
        c = a["consistency"][sname]
        pr = c["predictions"]["flow"]
        print(f"\n-- consistency [{sname}]: verdict on the construct: {c['verdict'].upper()}"
              + (f" [{c.get('robustness')}]" if sname != "joined" else ""))
        print(f"     P1 {pr['P1']['holds']} (dD peak {_fmt(pr['P1']['dD'].get('peak'))}, density "
              f"{_fmt(pr['P1']['dD'].get('density'))}); P2 {pr['P2']['holds_human_blob']}; P3 {pr['P3']['reads']}; "
              f"P4 {pr['P4']['dD_positive']}/{pr['P4']['counted_tool_cells']} positive")
        print(f"     with constructors in the inputs: {c['with_constructors']['verdict'].upper()} "
              f"[{c['with_constructors']['constructors']}]")
    s = a["secondary"]["joined"]
    print(f"\n-- secondaries [joined]: method {_fmt(s['method']['all_calls']['micro'])} "
          f"(no helpers {_fmt(s['method']['no_helpers']['micro'])}; mechanism: {s['method']['mechanism']['reading']}); tool oracles "
          + "; ".join(f"{o} {_fmt(v['micro'])}" for o, v in s["tool_oracles"].items())
          + f"; Fontana {_fmt(s['fontana']['paired']['micro'])}")
    sj = a["sensitivity"]["joined"]
    print(f"-- sensitivity [joined]: without DI {_fmt(sj['without_di']['micro'])}; without the "
          f"{len(sj['budget_exhausted_repos'])} repositories out of resolution time "
          f"{_fmt(sj['without_budget_exhausted']['micro'])}")
    print("\n-- EXPLORATORY intersection [joined], mad_z, flow (decides nothing): positives / flagged per region")
    for name, it in a["exploratory_intersection"]["joined"].items():
        c = it["cells"].get("flow|np") or it["cells"].get("flow|all")
        if not c:
            continue
        p = c["pooled"]
        reg = "  ".join(f"{r} {int(p[r]['tp'])}/{int(p[r]['tp'] + p[r]['fp'])}"
                        for r in ("X_only", "both", "d_only"))
        print(f"     {it['population']}: {reg}; of {int(p['X']['n_god'])} positives; MCC X {p['X']['mcc']:.3f}, "
              f"both {p['both']['mcc']:.3f}, either {p['either']['mcc']:.3f}; both vs X {_fmt(c['vs_X']['both'])}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds analyse", description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--exploratory", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    commit = pins.harness_commit() or ""
    if commit.endswith("-dirty") and not a.check:
        raise SystemExit("the harness has uncommitted changes; commit them first")
    target = os.path.join(pins.RESULTS, "analysis.json")
    stamp = _now().replace(":", "").replace("-", "")
    if a.check:
        target = os.path.join(pins.RESULTS, f"analysis.check.{stamp}.json")
    elif a.exploratory:
        target = os.path.join(pins.RESULTS, f"analysis.exploratory.{stamp}.json")
    elif os.path.exists(target):
        raise SystemExit(f"{target} exists: the confirmatory analysis is written once. Re-analyse "
                         f"with --exploratory.")
    res = analyse(check=a.check)
    res["kind"] = "check" if a.check else ("exploratory" if a.exploratory else "confirmatory")
    os.makedirs(pins.RESULTS, exist_ok=True)
    with open(target, "w") as fh:
        json.dump(res, fh, indent=1, default=_json_default)
    digest = hashlib.sha256(open(target, "rb").read()).hexdigest()
    with open(target + ".sha256", "w") as fh:
        fh.write(f"{digest}  {os.path.basename(target)}\n")
    print_report(res)
    print(f"\nwrote {target} (sha256 {digest[:16]}...)")
    return 0


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o))


if __name__ == "__main__":
    sys.exit(main())
