#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. Is a form's gain a better ranking, or only more flags?

Written after every oracle of the study had been read (PLAN.md, Amendments, 10); it changes no
verdict. A monotone transform of a signal (a power, a logarithm) keeps every unit's rank and
moves only where the rule's constant lands, so it is the same knob as the constant 3.5. A
coupling factor is not monotone in the complexity signal, but its product can still gain by
flagging more units rather than by ranking them better: X*.O_flow flags about two and a half
times as many classes as X* alone. Two reads separate the two effects, for the registered arms
and the exploratory forms of scripts/exploratory_ranking.py:

  1. the threshold-free pooled AUC of each form's per-repository modified z over the reviewed
     units (as the analysis computes it for the primary pair), and of its per-repository
     percentile rank, which no transform changes; with the paired bootstrap against X*;
  2. a matched flag rate: each form read at the constant that gives it exactly as many flags,
     over every unit of the population's repositories, as a reference form has at 3.5 (class:
     X*.O_flow; method: the best complexity-alone signal), with precision, recall and the pooled
     MCC and its paired difference against X* at that same rate.

    .venv/bin/python scripts/exploratory_matched.py                 # every set
    .venv/bin/python scripts/exploratory_matched.py --sets mlcq

Writes results/exploratory/matched.<utc>.json (with its sha256) and prints one table per
population.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concentration_divergence_study import boot, forms, pins, records, rules, units  # noqa: E402
from complexity_concentration_study import study as p1  # noqa: E402
import exploratory_ranking as er  # noqa: E402

POPULATIONS = er.POPULATIONS
CUT = 3.5

# the forms read, per level: (label, how to get the vector)
CLASS_ARMS = [
    ("X* = nloc_max", ("spec", ("X", "nloc_max"))),
    ("X*.D_flow (primary arm)", ("spec", ("XD_A", "nloc_max", "flow", "np"))),
    ("X*.E_flow (exemption only)", ("spec", ("XE_A", "nloc_max", "flow", "np"))),
    ("X*.A_flow (amplification only)", ("spec", ("XA_A", "nloc_max", "flow", "np"))),
    ("X*.N (size null)", ("spec", ("XN", "nloc_max"))),
    ("X*.O_flow (outgoing factor)", ("spec", ("XO_A", "nloc_max", "flow"))),
    ("hvol_sum (best complexity alone)", ("spec", ("X", "hvol_sum"))),
    ("nloc_sum", ("spec", ("X", "nloc_sum"))),
    ("nloc_sum x nom (size only)", ("er", "nloc_sum x nom")),
    ("nloc_sum x (1+leaving calls)", ("er", "nloc_sum x (1+calls_leave)")),
    ("nloc_sum x (1+fan-out)", ("er", "nloc_sum x (1+fan_leave)")),
    ("leaving calls alone", ("er", "calls_leave")),
]
METHOD_ARMS = [
    ("X*_m = cognitive", ("spec", ("X", "cognitive"))),
    ("X*_m.D_flow (all calls)", ("spec", ("XD", "cognitive", "flow", "all"))),
    ("X*_m.E_flow", ("spec", ("XE", "cognitive", "flow", "all"))),
    ("X*_m.O_flow", ("spec", ("XO", "cognitive", "flow", "all"))),
    ("tokens (best complexity alone)", ("spec", ("X", "tokens"))),
    ("nloc", ("spec", ("X", "nloc"))),
    ("nloc x [any call]", ("er", "nloc x [any call >= 1]")),
    ("nloc x [internal call]", ("er", "nloc x [internal call >= 1]")),
    ("nloc x (1+internal calls)", ("er", "nloc x (1+calls_all)  [weight, not gate]")),
]
REFERENCE = {"class": "X*.O_flow (outgoing factor)", "method": "tokens (best complexity alone)"}
BASE = {"class": "X* = nloc_max", "method": "X*_m = cognitive"}
# a second base, the best complexity-alone signal, so a gain over the registered signal can be
# told from a gain over length itself
ALT = {"class": "hvol_sum (best complexity alone)", "method": "tokens (best complexity alone)"}


def collect(set_name: str, wanted: list) -> dict:
    """Per population: per form, the per-repository modified z and percentile of every unit, with
    the oracle's masks; kept as lists per repository for the bootstrap."""
    results = os.path.join(pins.RESULTS, set_name)
    rows = records.load_rows(results)
    out: dict = {}
    for k, r in enumerate(rows):
        if r.get("error") or r.get("javaparser_error") or not p1.is_usable(r):
            continue
        rec = records.read_json_gz(records.record_path(results, r["key"]))
        built = units.joined(rec)
        ml, cl = built["method"], built["class"]
        S = {"method": ml, "class": cl}
        mc = er.method_calls(rec, ml)
        ex = {"class": er.class_forms(cl, ml, mc), "method": er.method_forms(ml, mc)}
        grouper = forms.Grouper(ml.c["file"], cl.ids)
        for halves, lvl, oracle in wanted:
            if halves is not None and r.get("half") not in halves:
                continue
            L = S[lvl]
            if oracle not in L.oracles or L.n == 0:
                continue
            pos, univ = L.oracles[oracle]
            if univ.sum() == 0:
                continue
            arms = CLASS_ARMS if lvl == "class" else METHOD_ARMS
            slot = out.setdefault((halves, lvl, oracle), {"keys": [], "z": {a[0]: [] for a in arms},
                                                            "pct": {a[0]: [] for a in arms}, "pos": [], "univ": []})
            for label, (how, what) in arms:
                v = (forms.vector(lvl, what, S, grouper) if how == "spec" else ex[lvl][what]).astype(float)
                z = rules.mad_z_scale(v)[1].astype(np.float32)
                order = np.argsort(np.argsort(v, kind="stable"))
                pct = ((order + 1) / L.n).astype(np.float32)
                slot["z"][label].append(z)
                slot["pct"][label].append(pct)
            slot["keys"].append(r["key"])
            slot["pos"].append(pos)
            slot["univ"].append(univ)
        if (k + 1) % 50 == 0:
            print(f"  {set_name}: {k + 1}/{len(rows)} records", file=sys.stderr)
    return out


def counts_at(zs: list, t: float, pos: list, univ: list) -> np.ndarray:
    return np.array([[int(u.sum()), int((z >= t)[u].sum()), int(((z >= t) & p)[u].sum()), int((p & u).sum())]
                     for z, p, u in zip(zs, pos, univ)], dtype=np.int64)


def pooled_auc(vals: list, pos: list, univ: list, m: np.ndarray | None):
    """AUC over the reviewed units pooled; the paired bootstrap repeats each repository's units."""
    v = [x[u] for x, u in zip(vals, univ)]
    l = [p[u] for p, u in zip(pos, univ)]
    V, Lb = np.concatenate(v), np.concatenate(l)
    full = boot.auc(V[Lb], V[~Lb])
    if m is None:
        return full, None
    reps = []
    for row in m:
        w = np.concatenate([np.repeat(np.full(len(x), 1), int(c)) if False else np.repeat(x, int(c)) for x, c in zip(v, row)])
        lab = np.concatenate([np.repeat(x, int(c)) for x, c in zip(l, row)])
        reps.append(boot.auc(w[lab], w[~lab]) if lab.any() and (~lab).any() else np.nan)
    return full, np.array(reps, float)


def est(iv):
    return "n/a" if not iv else f"{iv['value']:+.3f} [{iv['lo']:+.3f}, {iv['hi']:+.3f}]"


def report(key, slot, with_boot: bool) -> dict:
    halves, lvl, oracle = key
    n = len(slot["keys"])
    m = boot.multiplicities(n) if with_boot else None
    pos, univ = slot["pos"], slot["univ"]
    arms = [a[0] for a in (CLASS_ARMS if lvl == "class" else METHOD_ARMS)]
    ref, base = REFERENCE[lvl], BASE[lvl]
    # the reference's flags at 3.5 over every unit
    K = int(sum(int((z >= CUT).sum()) for z in slot["z"][ref]))
    allz = {a: np.concatenate(slot["z"][a]) for a in arms}
    n_all = len(allz[base])
    out_rows = []
    # AUCs and the base's counts first
    auc_z, auc_pct = {}, {}
    for a in arms:
        auc_z[a] = pooled_auc(slot["z"][a], pos, univ, m)
        auc_pct[a] = pooled_auc(slot["pct"][a], pos, univ, m)
    alt = ALT[lvl]
    t_alt = np.sort(allz[alt])[::-1][min(K, n_all) - 1] if K > 0 else np.inf
    alt_matched = counts_at(slot["z"][alt], t_alt, pos, univ)
    base_own = counts_at(slot["z"][base], CUT, pos, univ)
    t_base = np.sort(allz[base])[::-1][min(K, n_all) - 1] if K > 0 else np.inf
    base_matched = counts_at(slot["z"][base], t_base, pos, univ)
    label = f"{oracle} [{'+'.join(halves) if halves else 'all'}] {lvl}: {n} repositories, " \
            f"{int(sum(u.sum() for u in univ))} reviewed units, {int(sum((p & u).sum() for p, u in zip(pos, univ)))} positives; " \
            f"matched rate: {K} flags of {n_all} units, as {ref} at 3.5"
    print(f"\n=== {label}")
    print(f"  {'form':34s} {'AUC z':>6s} {'AUC pct':>8s}  AUC z vs X* (95% CI)      | own 3.5: {'flag':>5s} {'MCC':>6s} {'P':>5s} {'R':>5s} | matched: {'MCC':>6s} {'P':>5s} {'R':>5s}  MCC vs X* at matched rate")
    for a in arms:
        own = counts_at(slot["z"][a], CUT, pos, univ)
        t = np.sort(allz[a])[::-1][min(K, n_all) - 1] if K > 0 else np.inf
        mt = counts_at(slot["z"][a], t, pos, univ)
        po, pm = boot.rates(own.sum(0)), boot.rates(mt.sum(0))
        az, az_reps = auc_z[a]
        bz, bz_reps = auc_z[base]
        auc_diff = None
        if m is not None and az is not None and bz is not None:
            auc_diff = boot.interval(az - bz, az_reps - bz_reps, n, len(m))
        mcc_diff = boot.micro_diff(base_matched, mt, m) if m is not None else None
        alt_auc_diff = alt_pct_diff = alt_mcc_diff = None
        if m is not None:
            cz, cz_reps = auc_z[alt]
            if az is not None and cz is not None:
                alt_auc_diff = boot.interval(az - cz, az_reps - cz_reps, n, len(m))
            ap_, ap_reps = auc_pct[a]; cp_, cp_reps = auc_pct[alt]
            if ap_ is not None and cp_ is not None:
                alt_pct_diff = boot.interval(ap_ - cp_, ap_reps - cp_reps, n, len(m))
            alt_mcc_diff = boot.micro_diff(alt_matched, mt, m)
        r = {"form": a, "auc_z": az, "auc_pct": auc_pct[a][0], "auc_z_vs_base": auc_diff,
             "auc_z_vs_alt": alt_auc_diff, "auc_pct_vs_alt": alt_pct_diff, "matched_mcc_vs_alt": alt_mcc_diff,
             "own": {"flagged": int(own.sum(0)[1]), "mcc": float(boot.mcc_counts(own.sum(0))), **po},
             "matched": {"threshold_z": float(t), "flagged": int(mt.sum(0)[1]), "mcc": float(boot.mcc_counts(mt.sum(0))), **pm,
                         "mcc_vs_base": mcc_diff}}
        out_rows.append(r)
        f = lambda x: "  n/a" if x is None else f"{x:5.2f}"
        print(f"  {a:34s} {az if az else 0:6.3f} {auc_pct[a][0] if auc_pct[a][0] else 0:8.3f}  {est(auc_diff):26s}| "
              f"{r['own']['flagged']:5d} {r['own']['mcc']:6.3f} {f(po['precision'])} {f(po['recall'])} | "
              f"{r['matched']['mcc']:6.3f} {f(pm['precision'])} {f(pm['recall'])}  {est(mcc_diff)}")
    print(f"  -- against {alt}: AUC z, percentile-rank AUC, and MCC at the matched rate")
    for r in out_rows:
        print(f"  {r['form']:34s} {est(r['auc_z_vs_alt']):26s} {est(r['auc_pct_vs_alt']):26s} {est(r['matched_mcc_vs_alt'])}")
    return {"population": label, "set_halves": halves, "level": lvl, "oracle": oracle, "n_repos": n,
            "reference": ref, "base": base, "alt": alt, "matched_flags": K, "n_units": n_all, "rows": out_rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", nargs="+", default=["mlcq", "fontana", "seed3"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rep = {"kind": "exploratory", "made_utc": stamp, "harness_commit": pins.harness_commit(),
           "note": __doc__.splitlines()[0], "cut": CUT, "populations": []}
    for s in a.sets:
        wanted = [(h, lvl, o) for st, h, lvl, o in POPULATIONS if st == s]
        print(f"collecting {s} ...", file=sys.stderr)
        got = collect(s, wanted)
        for key, slot in got.items():
            rep["populations"].append(report(key, slot, with_boot=(s != "seed3")))
    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = a.out or os.path.join(pins.RESULTS, "exploratory", f"matched.{stamp}.json")
    with open(path, "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with open(path + ".sha256", "w") as fh:
        fh.write(f"{digest}  {os.path.basename(path)}\n")
    print(f"\nwrote {path}  (exploratory; not part of the plan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
