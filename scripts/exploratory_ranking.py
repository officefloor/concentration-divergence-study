#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. Rank candidate god-unit forms built from size and outgoing calls.

Written after every oracle of the study had been read (PLAN.md, Amendments, 10), so nothing it
prints is confirmatory: it is the exploratory step of a next registration, on material that is
all exploration material now. It is not part of the plan and changes no verdict.

It reads the raw records (results/<set>/repos/*.json.gz) and computes, from the measurer's
per-call data, forms the registered matrix does not hold: the plain count of internal calls
(each call one unit, arguments ignored), fan-out as distinct callee files, and products of a size
measure with them, in class form A (the class's total) and form B (per-method products
aggregated), plus the method-level gate "makes at least one internal call". Every form is
scored by the registered rule (modified z >= 3.5, fitted on every unit of the repository) and,
with --all-rules, by every rule of paper one, against every oracle, and read as the pooled MCC
with the paired bootstrap difference (2000 resamples over repositories, seed 12345) against two
competitors: the best complexity-alone signal and the size-only counterpart.

    .venv/bin/python scripts/exploratory_ranking.py                 # every set, mad_z
    .venv/bin/python scripts/exploratory_ranking.py --sets mlcq     # one set
    .venv/bin/python scripts/exploratory_ranking.py --all-rules     # slower

Writes results/exploratory/ranking.<utc>.json and prints one table per population. Complexity
is paper one's (the record's units), coupling the measurer's; units are the joined set's.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from concentration_divergence_study import boot, javaparser, pins, records, rules, units  # noqa: E402
from complexity_concentration_study import study as p1  # noqa: E402  (paper one's substance floor)

I = javaparser.RES_INTERNAL
MAD = rules.ORDER.index("mad_z")

# the populations: (set, halves, level, oracle)
POPULATIONS = [
    ("mlcq", ("explore",), "class", "human_blob"), ("mlcq", ("confirm",), "class", "human_blob"),
    ("mlcq", ("explore",), "method", "human_method_long_method"),
    ("mlcq", ("confirm",), "method", "human_method_long_method"),
    ("fontana", None, "class", "human_fontana_god_class"),
    ("seed3", None, "class", "pmd_GodClass"), ("seed3", None, "class", "decor_blob"), ("seed3", None, "class", "wmc47"),
    ("seed3", None, "method", "pmd_method_NPath200"), ("seed3", None, "method", "brain_method"),
]

# the competitors each candidate is read against, per level: the best complexity-alone signal,
# and the size-only counterparts (the registered size null X*.N is nloc_max x nom)
COMPETITORS = {"class": {"complexity": "hvol_sum", "size": "nloc_sum x nom", "size_max": "nloc_max x nom"},
               "method": {"complexity": "tokens", "size": "nloc", "size_max": "nloc"}}


def method_calls(rec: dict, ml: units.Level) -> dict:
    """Per joined method: internal calls (all / leaving the file), distinct callee files left to,
    and calls of any resolution; zeros for an unjoined unit."""
    jp_files = units._measurer_files(rec["javaparser"])
    by_key = defaultdict(list)
    for path, ms in jp_files.items():
        for m, fidx in ms:
            by_key[(path, m["name"], m["name_line"])].append((m, fidx))
    n = ml.n
    out = {k: np.zeros(n) for k in ("calls_all", "calls_leave", "fan_leave", "calls_any")}
    for i, uid in enumerate(ml.ids):
        path, name, line = units._uid_parts(uid)
        hits = by_key.get((path, name, line))
        if not hits:
            continue
        m, fidx = hits[0]
        out["calls_any"][i] = len(m["calls"])
        callees = set()
        for a, kind, res, tidx in m["calls"]:
            if res != I:
                continue
            out["calls_all"][i] += 1
            if tidx != fidx:
                out["calls_leave"][i] += 1
                callees.add(tidx)
        out["fan_leave"][i] = len(callees)
    return out


def class_forms(cl: units.Level, ml: units.Level, mc: dict) -> dict:
    """Every class-level candidate, as {name: values over cl.ids}."""
    fidx = {f: i for i, f in enumerate(cl.ids)}
    groups = defaultdict(list)
    for j, p in enumerate(ml.c["file"]):
        if p in fidx:
            groups[fidx[p]].append(j)
    n = cl.n
    v = cl.values
    calls_leave = np.zeros(n); calls_all = np.zeros(n); fan = np.zeros(n)
    b_sum = np.zeros(n); b_max = np.zeros(n)
    for ci, js in groups.items():
        js = np.array(js)
        calls_leave[ci] = mc["calls_leave"][js].sum()
        calls_all[ci] = mc["calls_all"][js].sum()
        # fan-out of the class: distinct callee files over its methods is not recoverable from
        # per-method distinct counts; the sum over methods is an upper bound and is what is used
        fan[ci] = mc["fan_leave"][js].sum()
        prod = ml.values["nloc"][js] * (1 + mc["calls_leave"][js])
        b_sum[ci] = prod.sum(); b_max[ci] = prod.max()
    nom = v["nom"]
    out_flow = cl.c.get("out_flow", np.zeros(n))          # the registered, argument-weighted outgoing data
    f = {
        # complexity alone and size alone
        "hvol_sum": v["hvol_sum"], "nloc_sum": v["nloc_sum"], "nloc_max": v["nloc_max"],
        "cognitive_max": v["cognitive_max"], "cc_sum": v["cc_sum"], "nom": nom,
        "cyc_density_max": v["cyc_density_max"],
        # size only competitors
        "nloc_sum x nom": v["nloc_sum"] * nom, "nloc_max x nom": v["nloc_max"] * nom,
        # the candidates: size x calls, form A
        "nloc_sum x (1+calls_leave)": v["nloc_sum"] * (1 + calls_leave),
        "nloc_sum x (1+calls_all)": v["nloc_sum"] * (1 + calls_all),
        "nloc_sum x (1+fan_leave)": v["nloc_sum"] * (1 + fan),
        "nloc_max x (1+calls_leave)": v["nloc_max"] * (1 + calls_leave),
        "hvol_sum x (1+calls_leave)": v["hvol_sum"] * (1 + calls_leave),
        "cc_sum x (1+calls_leave)": v["cc_sum"] * (1 + calls_leave),
        "nloc_sum x (1+out_flow)  [registered O_flow]": v["nloc_sum"] * (1 + out_flow),
        "nloc_max x (1+out_flow)  [registered X*.O_flow]": v["nloc_max"] * (1 + out_flow),
        # is it the calls, the size, or the complexity beyond length?
        "nom x (1+calls_leave)": nom * (1 + calls_leave),
        "cyc_density_max x (1+calls_leave)": v["cyc_density_max"] * (1 + calls_leave),
        "nloc_max x (1+calls_leave/nom)  [per-method rate]": v["nloc_max"] * (1 + np.where(nom > 0, calls_leave / np.maximum(nom, 1), 0)),
        "calls_leave": calls_leave, "fan_leave": fan,
        # form B: per-method products aggregated
        "sum_m nloc(m) x (1+calls_leave(m))  [form B]": b_sum,
        "max_m nloc(m) x (1+calls_leave(m))  [form B]": b_max,
    }
    return f


def method_forms(ml: units.Level, mc: dict) -> dict:
    v = ml.values
    gate_int = (mc["calls_all"] >= 1).astype(float)
    gate_leave = (mc["calls_leave"] >= 1).astype(float)
    gate_any = (mc["calls_any"] >= 1).astype(float)
    return {
        "tokens": v["tokens"], "cc": v["cc"], "cognitive": v["cognitive"], "nloc": v["nloc"],
        "hvol": v["hvol"], "cyc_density": v["cyc_density"],
        "nloc x [internal call >= 1]": v["nloc"] * gate_int,
        "nloc x [leaving call >= 1]": v["nloc"] * gate_leave,
        "nloc x [any call >= 1]": v["nloc"] * gate_any,
        "tokens x [internal call >= 1]": v["tokens"] * gate_int,
        "cc x [internal call >= 1]": v["cc"] * gate_int,
        "cognitive x [internal call >= 1]": v["cognitive"] * gate_int,
        "hvol x [internal call >= 1]": v["hvol"] * gate_int,
        "cyc_density x [internal call >= 1]": v["cyc_density"] * gate_int,
        "nloc x (1+calls_all)  [weight, not gate]": v["nloc"] * (1 + mc["calls_all"]),
        "nloc x (1+calls_leave)": v["nloc"] * (1 + mc["calls_leave"]),
        "calls_all": mc["calls_all"],
    }


def cells(flags: np.ndarray, pos: np.ndarray, univ: np.ndarray) -> list:
    """Paper one's lean counts over the oracle's universe: n_univ, n_out, n_overlap, n_god."""
    f = flags & univ
    return [int(univ.sum()), int(f.sum()), int((f & pos).sum()), int((pos & univ).sum())]


def score_set(set_name: str, all_rules: bool) -> dict:
    """{(halves-key, level, oracle): {'keys': [...], 'forms': [...], 'counts': [repo][form][rule][4]}}"""
    results = os.path.join(pins.RESULTS, set_name)
    rows = records.load_rows(results)
    out: dict = {}
    wanted = [(h, lvl, o) for s, h, lvl, o in POPULATIONS if s == set_name]
    for k, r in enumerate(rows):
        if r.get("error") or r.get("javaparser_error") or not p1.is_usable(r):
            continue
        rec = records.read_json_gz(records.record_path(results, r["key"]))
        built = units.joined(rec)
        ml, cl = built["method"], built["class"]
        mc = method_calls(rec, ml)
        forms = {"class": class_forms(cl, ml, mc), "method": method_forms(ml, mc)}
        levels = {"class": cl, "method": ml}
        for halves, lvl, oracle in wanted:
            if halves is not None and r.get("half") not in halves:
                continue
            level = levels[lvl]
            if oracle not in level.oracles or level.n == 0:
                continue
            pos, univ = level.oracles[oracle]
            if univ.sum() == 0:
                continue
            key = (halves, lvl, oracle)
            slot = out.setdefault(key, {"keys": [], "forms": list(forms[lvl]), "counts": []})
            per_form = []
            for name, vals in forms[lvl].items():
                vals = np.asarray(vals, float)
                masks = rules.all_rules(vals) if all_rules else [rules.mad_z(vals)]
                per_form.append([cells(m, pos, univ) for m in masks])
            slot["keys"].append(r["key"])
            slot["counts"].append(per_form)
        if (k + 1) % 50 == 0:
            print(f"  {set_name}: {k + 1}/{len(rows)} records", file=sys.stderr)
    for slot in out.values():
        slot["counts"] = np.array(slot["counts"], dtype=np.int64)
    return out


def f(iv):
    return "n/a" if not iv else f"{iv['value']:+.3f} [{iv['lo']:+.3f}, {iv['hi']:+.3f}]"


def report(key, slot, rule_idx: int, rule_name: str) -> dict:
    halves, lvl, oracle = key
    C = slot["counts"][:, :, rule_idx, :]             # [repo, form, 4]
    names = slot["forms"]
    n = C.shape[0]
    m = boot.multiplicities(n)
    comp = COMPETITORS[lvl]
    comp_x, comp_s = comp["complexity"], comp["size"]
    idx = {k: names.index(v) for k, v in comp.items()}
    rows = []
    for j, name in enumerate(names):
        pooled = C[:, j, :].sum(0)
        rates = boot.rates(pooled)
        rows.append({"form": name, "mcc": float(boot.mcc_counts(pooled)), "precision": rates["precision"],
                     "recall": rates["recall"], "flagged": int(pooled[1]), "hits": int(pooled[2]),
                     "vs_complexity": boot.micro_diff(C[:, idx["complexity"], :], C[:, j, :], m),
                     "vs_size": boot.micro_diff(C[:, idx["size"], :], C[:, j, :], m),
                     "vs_size_max": boot.micro_diff(C[:, idx["size_max"], :], C[:, j, :], m),
                     "macro_vs_complexity": boot.macro_diff(C[:, idx["complexity"], :], C[:, j, :], m),
                     "macro_vs_size": boot.macro_diff(C[:, idx["size"], :], C[:, j, :], m)})
    rows.sort(key=lambda r: -r["mcc"])
    label = f"{oracle} [{'+'.join(halves) if halves else 'all'}] {lvl}, {rule_name}: {n} repositories, " \
            f"{int(C[:, 0, 0].sum())} units in the universe, {int(C[:, 0, 3].sum())} positives"
    print(f"\n=== {label}")
    print(f"  {'form':52s} {'MCC':>6s} {'P':>5s} {'R':>5s} {'flag':>6s}  vs {comp_x:<10s}           vs {comp_s}")
    for r in rows:
        p = "  n/a" if r["precision"] is None else f"{r['precision']:5.2f}"
        q = "  n/a" if r["recall"] is None else f"{r['recall']:5.2f}"
        print(f"  {r['form']:52s} {r['mcc']:6.3f} {p} {q} {r['flagged']:6d}  {f(r['vs_complexity']):26s} {f(r['vs_size'])}")
    return {"population": label, "set_halves": halves, "level": lvl, "oracle": oracle, "rule": rule_name,
            "n_repos": n, "n_units": int(C[:, 0, 0].sum()), "n_positives": int(C[:, 0, 3].sum()),
            "competitors": comp, "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", nargs="+", default=["mlcq", "fontana", "seed3"])
    ap.add_argument("--all-rules", action="store_true", help="every rule of paper one, not only mad_z")
    ap.add_argument("--out", default=None, help="output path (default results/exploratory/ranking.<utc>.json)")
    a = ap.parse_args(argv)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"kind": "exploratory", "made_utc": stamp, "harness_commit": pins.harness_commit(),
           "note": __doc__.splitlines()[0], "populations": []}
    for s in a.sets:
        print(f"scoring {s} ...", file=sys.stderr)
        scored = score_set(s, a.all_rules)
        for key, slot in scored.items():
            rule_names = list(rules.ORDER) if a.all_rules else ["mad_z"]
            for ri, rn in enumerate(rule_names):
                out["populations"].append(report(key, slot, ri, rn))
    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = a.out or os.path.join(pins.RESULTS, "exploratory", f"ranking.{stamp}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    import hashlib
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with open(path + ".sha256", "w") as fh:
        fh.write(f"{digest}  {os.path.basename(path)}\n")
    print(f"\nwrote {path}  (exploratory; not part of the plan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
