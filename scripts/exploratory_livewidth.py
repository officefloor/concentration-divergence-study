#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. Live width against length: is a god method too much to hold at once?

Written after every oracle of the study had been read (PLAN.md, Amendments, 10), so nothing it
prints is confirmatory; it changes no verdict. The earlier exploration found length, gated by
"makes at least one internal call", the best method-level form, with nothing about complexity
beyond length adding to it. This reads whether what a reader must hold at once does: the live
width of scripts/livewidth.py (its facts in results/exploratory/livewidth/<set>/, measured by
that script first), in every variant, against length, tokens and length x [internal call >= 1];
and whether the plain count of the method's variables does, without regard to when each is live
(every form is also paired against that count, so a width that only counts variables shows);
and how data moves through the method (scripts/livewidth.py, FLOW): how many variables enter it
(parameters, fields, the results of internal calls), how many variables go into computing one,
whether what enters flows on into the method's fan-out (its internal calls, the measurer's
resolution call for call), and the state held across calls.

Each form is read two ways:

  outlier    the registered rule (modified z >= 3.5, fitted on every unit of the repository),
             pooled MCC with the paired bootstrap against the competitors (2000 resamples over
             repositories, seed 12345), as scripts/exploratory_ranking.py reads it;
  threshold  an absolute cutoff, the same for every repository: a width of k or more (k = 2..12,
             around the 4 +- 1 and 7 +- 2 spans), a count of k variables or more, and, for
             length, nloc of n or more. On MLCQ the
             cutoff is chosen on the explore half (the best pooled MCC) and read once on the
             confirm half, against length's cutoff chosen the same way.

Class level (Blob, Fontana, the seed-3 tool oracles) reads the largest live width of the class's
methods, the sum of their areas and the largest variable count, beside the ranking script's class competitors.

    .venv/bin/python scripts/exploratory_livewidth.py                 # every set
    .venv/bin/python scripts/exploratory_livewidth.py --sets mlcq

Writes results/exploratory/livewidth.<utc>.json (with its sha256) and prints the tables. A
repository without live-width facts is left out and counted, never scored as zeros.

Beside it, results/exploratory/livewidth-units.<utc>.csv.gz (with its sha256): one row per
method in a human oracle's universe (MLCQ's reviewed methods), with its set, repository key,
half, unit, label, whether the pass had facts for it, and every method form raw and as its
modified z within its repository (fitted on every unit there, as the registered rule fits it).
It is small enough to commit, so the reviewed units can be analysed further without the records.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concentration_divergence_study import boot, pins, records, rules, units  # noqa: E402
from complexity_concentration_study import study as p1  # noqa: E402
import exploratory_ranking as er  # noqa: E402
import livewidth as lw  # noqa: E402

H = lw.label(lw.HEADLINE)
WIDTH_K = tuple(range(2, 13))
NLOC_N = (10, 15, 20, 26, 30, 40, 50, 75, 100)
COUNT_K = (3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20)
COUNT = "vars count [all]"
SIZE_CALLS = "nloc x [internal call >= 1]"
# the competitors every method form is read against (exploratory_ranking's, and its best form)
METHOD_COMPETITORS = {"size_calls": SIZE_CALLS, "size": "nloc", "complexity": "tokens", "count": COUNT}
CLASS_COMPETITORS = er.COMPETITORS["class"]
# per level, the length a held-out cutoff is read against, and the form by the registered rule
HELD_OUT_REFS = {"method": ("nloc", SIZE_CALLS), "class": ("nloc_max", "nloc_max x nom")}


def method_widths(facts: dict, ml: units.Level) -> tuple[dict, int]:
    """{form name: values over ml.ids} of every live-width variant and variable count, and how
    many joined units have no facts (zeros)."""
    by = lw.by_unit(facts)
    vs = lw.variants()
    n = ml.n
    out = {f"lw max {lw.label(v)}": np.zeros(n) for v in vs}
    out["MaxLive [text,unit,locals]  (Crichton)"] = np.zeros(n)
    out["LV mean [text,unit,locals]  (Dunsmore & Gannon)"] = np.zeros(n)
    for name in ("mean", "area") + tuple(f"over{k}" for k in (4, 7)):
        out[f"lw {name} {H}"] = np.zeros(n)
    for c in lw.COUNTS:
        out[f"vars count [{c}]"] = np.zeros(n)
    missing = 0
    for i, uid in enumerate(ml.ids):
        m = by.get(units._uid_parts(uid))
        if m is None:
            missing += 1
            continue
        for v in vs:
            s = lw.summary(m, v)
            out[f"lw max {lw.label(v)}"][i] = s["max"]
            if v == ("text", "unit", "locals", "use"):
                out["MaxLive [text,unit,locals]  (Crichton)"][i] = s["max"]
                out["LV mean [text,unit,locals]  (Dunsmore & Gannon)"][i] = s["mean"]
            if v == lw.HEADLINE:
                for name in ("mean", "area", "over4", "over7"):
                    out[f"lw {name} {H}"][i] = s[name]
        for c, x in lw.counts(m).items():
            out[f"vars count [{c}]"][i] = x
    return out, missing


def method_flows(facts: dict, rec: dict, ml: units.Level) -> tuple[dict, int]:
    """{form name: values over ml.ids} of every FLOW measure, and how many units were left at
    zero because their calls did not align with the measurer record's (the same count of calls,
    in the same order, is required to take each call's resolution)."""
    by = lw.by_unit(facts)
    jp = {}
    for path, ms in units._measurer_files(rec["javaparser"]).items():
        for m, _ in ms:
            jp.setdefault((path, m["name"], m["name_line"]), m)
    out = {f"flow {k}": np.zeros(ml.n) for k in lw.FLOW}
    misaligned = 0
    for i, uid in enumerate(ml.ids):
        key = units._uid_parts(uid)
        m, r = by.get(key), jp.get(key)
        if m is None or r is None:
            continue
        if len(r["calls"]) != len(m.get("calls", [])):
            misaligned += 1
            continue
        for k, x in lw.flow(m, [c[2] == er.I for c in r["calls"]]).items():
            out[f"flow {k}"][i] = x
    return out, misaligned


def method_forms(ml: units.Level, mc: dict, w: dict) -> dict:
    base = er.method_forms(ml, mc)
    gate = (mc["calls_all"] >= 1).astype(float)
    top = w[f"lw max {H}"]
    f = {k: base[k] for k in ("tokens", "cc", "cognitive", "nloc", SIZE_CALLS)}
    f.update(w)
    f[f"lw max {H} x [internal call >= 1]"] = top * gate
    f[f"lw area {H} x [internal call >= 1]"] = w[f"lw area {H}"] * gate
    f[f"{COUNT} x [internal call >= 1]"] = w[COUNT] * gate
    for k in (4, 5, 7):
        f[f"nloc x [lw max {H} >= {k}]  (length beyond the span)"] = ml.values["nloc"] * (top >= k)
    return f


def thresholds(name: str) -> list[tuple[str, float]]:
    """The absolute cutoffs a form is read at: widths for a maximum width, variables for a count,
    lines for length."""
    if " x " in name:
        return []
    if name.startswith(("lw max", "MaxLive", "max_m lw max")):
        return [(f">={k}", float(k)) for k in WIDTH_K]
    if name in ("flow lw_at_calls",):
        return [(f">={k}", float(k)) for k in WIDTH_K]
    if name.startswith(("vars count", "max_m vars count", "flow ", "max_m flow ")):
        return [(f">={k}", float(k)) for k in COUNT_K]
    if name in ("nloc", "nloc_max"):
        return [(f">={n}", float(n)) for n in NLOC_N]
    return []


def class_forms(cl: units.Level, ml: units.Level, mc: dict, w: dict) -> dict:
    f = er.class_forms(cl, ml, mc)
    keep = {k: f[k] for k in CLASS_COMPETITORS.values()} | {k: f[k] for k in ("nloc_max", "nloc_sum")}
    fidx = {p: i for i, p in enumerate(cl.ids)}
    top = np.zeros(cl.n)
    area = np.zeros(cl.n)
    most = np.zeros(cl.n)
    bridging = np.zeros(cl.n)
    entering = np.zeros(cl.n)
    for j, p in enumerate(ml.c["file"]):
        if p in fidx:
            c = fidx[p]
            top[c] = max(top[c], w[f"lw max {H}"][j])
            area[c] += w[f"lw area {H}"][j]
            most[c] = max(most[c], w[COUNT][j])
            bridging[c] = max(bridging[c], w["flow bridging"][j])
            entering[c] = max(entering[c], w["flow in_all"][j])
    keep[f"max_m lw max {H}"] = top
    keep[f"sum_m lw area {H}"] = area
    keep[f"max_m {COUNT}"] = most
    keep["max_m flow bridging"] = bridging
    keep["max_m flow in_all"] = entering
    keep[f"nloc_sum x [max_m lw max {H} >= 7]"] = f["nloc_sum"] * (top >= 7)
    return keep


def score_set(set_name: str) -> tuple[dict, dict, list]:
    """{(halves, level, oracle): {'keys', 'forms', 'rules': {form: [rule]}, 'counts': {form:
    [repo][rule][4]}, 'pairs': [(nloc, width)] over the universe}}, the coverage counts, and the
    extract's rows (method level, human oracles)."""
    results = os.path.join(pins.RESULTS, set_name)
    rows = records.load_rows(results)
    out: dict = {}
    cover = {"records": 0, "no_facts": 0, "units": 0, "units_without_facts": 0, "unit_mismatch": 0,
             "flow_misaligned": 0}
    wanted = [(h, lvl, o) for s, h, lvl, o in er.POPULATIONS if s == set_name]
    extract: list = []
    for k, r in enumerate(rows):
        if r.get("error") or r.get("javaparser_error") or not p1.is_usable(r):
            continue
        cover["records"] += 1
        fpath = os.path.join(lw.OUT, set_name, r["key"] + ".json.gz")
        if not os.path.exists(fpath):
            cover["no_facts"] += 1
            continue
        lwrec = records.read_json_gz(fpath)
        if lwrec["facts"].get("livewidth") != lw.SCHEMA:
            cover["no_facts"] += 1      # an older schema's facts: measure again (scripts/livewidth.py)
            continue
        cover["unit_mismatch"] += lwrec["check"]["missing"] + lwrec["check"]["extra"]
        rec = records.read_json_gz(records.record_path(results, r["key"]))
        built = units.joined(rec)
        ml, cl = built["method"], built["class"]
        mc = er.method_calls(rec, ml)
        w, missing = method_widths(lwrec["facts"], ml)
        fl, misaligned = method_flows(lwrec["facts"], rec, ml)
        w.update(fl)
        cover["flow_misaligned"] += misaligned
        cover["units"] += ml.n
        cover["units_without_facts"] += missing
        forms = {"method": method_forms(ml, mc, w), "class": class_forms(cl, ml, mc, w)}
        levels = {"method": ml, "class": cl}
        by = lw.by_unit(lwrec["facts"])
        has = [units._uid_parts(u) in by for u in ml.ids]
        z = None
        for halves, lvl, oracle in wanted:
            if halves is not None and r.get("half") not in halves:
                continue
            level = levels[lvl]
            if oracle not in level.oracles or level.n == 0:
                continue
            pos, univ = level.oracles[oracle]
            if univ.sum() == 0:
                continue
            slot = out.setdefault((halves, lvl, oracle), {
                "keys": [], "forms": list(forms[lvl]),
                "rules": {n: ["mad_z"] + [t for t, _ in thresholds(n)] for n in forms[lvl]},
                "counts": defaultdict(list), "pairs": []})
            for name, vals in forms[lvl].items():
                vals = np.asarray(vals, float)
                masks = [rules.mad_z(vals)] + [vals >= c for _, c in thresholds(name)]
                slot["counts"][name].append([er.cells(m, pos, univ) for m in masks])
            slot["keys"].append(r["key"])
            if lvl == "method" and oracle.startswith("human_"):
                if z is None:
                    z = {n: rules.mad_z_scale(np.asarray(v, float))[1] for n, v in forms["method"].items()}
                for i in np.flatnonzero(univ):
                    extract.append([set_name, r["key"], r.get("half"), oracle, ml.ids[i], int(pos[i]),
                                    int(has[i])]
                                   + [x for n, v in forms["method"].items()
                                      for x in (float(v[i]), round(float(z[n][i]), 4))])
            size = ml.values["nloc"] if lvl == "method" else cl.values["nloc_max"]
            width = forms[lvl][f"lw max {H}" if lvl == "method" else f"max_m lw max {H}"]
            slot["pairs"].extend(zip(size[univ].tolist(), width[univ].tolist()))
        if (k + 1) % 50 == 0:
            print(f"  {set_name}: {k + 1}/{len(rows)} records", file=sys.stderr)
    for slot in out.values():
        slot["counts"] = {n: np.array(c, dtype=np.int64) for n, c in slot["counts"].items()}
    return out, cover, extract


def spearman(pairs: list) -> float | None:
    if len(pairs) < 3:
        return None
    a = np.array(pairs, float)

    def ranks(x):
        order = np.argsort(x, kind="mergesort")
        r = np.empty(len(x))
        r[order] = np.arange(len(x))
        _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
        sums = np.bincount(inv, r)
        return (sums / cnt)[inv]
    ra, rb = ranks(a[:, 0]), ranks(a[:, 1])
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def pooled(C: np.ndarray) -> dict:
    s = C.sum(0)
    r = boot.rates(s)
    return {"mcc": float(boot.mcc_counts(s)), "precision": r["precision"], "recall": r["recall"],
            "flagged": int(s[1]), "hits": int(s[2])}


def report(key, slot) -> dict:
    halves, lvl, oracle = key
    comp = METHOD_COMPETITORS if lvl == "method" else CLASS_COMPETITORS
    names = slot["forms"]
    C = slot["counts"]
    n = len(slot["keys"])
    m = boot.multiplicities(n)
    first = C[names[0]][:, 0, :]
    label = f"{oracle} [{'+'.join(halves) if halves else 'all'}] {lvl}: {n} repositories, " \
            f"{int(first[:, 0].sum())} units in the universe, {int(first[:, 3].sum())} positives"
    print(f"\n=== {label}")
    rho = spearman(slot["pairs"])
    print(f"  Spearman rho(length, {'lw max' if lvl == 'method' else 'max_m lw max'} {H}) over the universe: "
          + ("n/a" if rho is None else f"{rho:.3f}"))
    cols = list(comp)
    print(f"  outlier (mad_z): {'form':58s} {'MCC':>6s} {'P':>5s} {'R':>5s} {'flag':>6s}  "
          + "  ".join(f"vs {comp[c]:<24s}" for c in cols))
    rows = []
    for name in names:
        x = C[name][:, 0, :]
        row = {"form": name, **pooled(x)}
        for c in cols:
            row[f"vs_{c}"] = boot.micro_diff(C[comp[c]][:, 0, :], x, m)
        rows.append(row)
    rows.sort(key=lambda r: -r["mcc"])
    for r in rows:
        p = "  n/a" if r["precision"] is None else f"{r['precision']:5.2f}"
        q = "  n/a" if r["recall"] is None else f"{r['recall']:5.2f}"
        print(f"  {'':17s}{r['form']:58s} {r['mcc']:6.3f} {p} {q} {r['flagged']:6d}  "
              + "  ".join(f"{er.f(r[f'vs_{c}']):27s}" for c in cols))
    thr = {}
    for name in names:
        if len(slot["rules"][name]) == 1:
            continue
        thr[name] = [{"rule": rn, **pooled(C[name][:, j, :])} for j, rn in enumerate(slot["rules"][name]) if j]
    if thr:
        print("  threshold (pooled MCC at each absolute cutoff):")
        for name, cells in thr.items():
            print(f"    {name:58s} " + " ".join(f"{c['rule']}:{c['mcc']:.3f}" for c in cells))
    return {"population": label, "set_halves": halves, "level": lvl, "oracle": oracle, "n_repos": n,
            "n_units": int(first[:, 0].sum()), "n_positives": int(first[:, 3].sum()),
            "spearman_size_width": rho, "competitors": comp, "outlier": rows, "threshold": thr,
            "keys": slot["keys"]}


def held_out(explore: dict, confirm: dict, lvl: str) -> dict | None:
    """Each thresholded form's cutoff chosen on the explore half (best pooled MCC) and read once
    on the confirm half, paired against length's cutoff chosen the same way and against the
    level's reference form by the registered rule (at method level the best earlier form,
    length x [internal call >= 1])."""
    if explore is None or confirm is None:
        return None
    length, ref = HELD_OUT_REFS[lvl]
    names = [n for n in confirm["forms"] if len(confirm["rules"][n]) > 1]
    choice = {}
    for n in names:
        cells = [(float(boot.mcc_counts(explore["counts"][n][:, j, :].sum(0))), j)
                 for j in range(1, len(explore["rules"][n]))]
        choice[n] = max(cells)[1]
    Cc = confirm["counts"]
    m = boot.multiplicities(len(confirm["keys"]))
    ref_len = Cc[length][:, choice[length], :]
    ref_rule = Cc[ref][:, 0, :]
    len_cut = confirm["rules"][length][choice[length]]
    out = []
    print(f"\n=== held out ({lvl}): cutoff chosen on the MLCQ explore half, read on the confirm half")
    for n in names:
        x = Cc[n][:, choice[n], :]
        row = {"form": n, "cutoff": confirm["rules"][n][choice[n]], **pooled(x),
               "vs_length_cutoff": boot.micro_diff(ref_len, x, m),
               "vs_reference_mad_z": boot.micro_diff(ref_rule, x, m)}
        out.append(row)
        print(f"  {n:58s} {row['cutoff']:>5s} MCC {row['mcc']:.3f}  vs {length} {len_cut}: "
              f"{er.f(row['vs_length_cutoff']):27s} vs {ref} (mad_z): {er.f(row['vs_reference_mad_z'])}")
    return {"length": length, "length_cutoff": len_cut, "reference": ref, "rows": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", nargs="+", default=["mlcq", "fontana", "seed3"])
    ap.add_argument("--out", default=None, help="output path (default results/exploratory/livewidth.<utc>.json)")
    a = ap.parse_args(argv)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"kind": "exploratory", "made_utc": stamp, "harness_commit": pins.harness_commit(),
           "note": __doc__.splitlines()[0], "headline_variant": H, "coverage": {},
           "populations": [], "held_out": {}}
    extract, header = [], None
    for s in a.sets:
        print(f"scoring {s} ...", file=sys.stderr)
        scored, cover, rows = score_set(s)
        extract += rows
        for (h, lvl, o), slot in scored.items():
            if lvl == "method" and header is None:
                header = ["set", "key", "half", "oracle", "unit", "label", "facts"] + [
                    x for n in slot["forms"] for x in (n, f"z:{n}")]
        out["coverage"][s] = cover
        print(f"\n{s}: {cover}")
        for key, slot in scored.items():
            out["populations"].append(report(key, slot))
        for lvl, oracle in {(lvl, o) for (h, lvl, o) in scored if h == ("explore",)}:
            ho = held_out(scored.get((("explore",), lvl, oracle)), scored.get((("confirm",), lvl, oracle)), lvl)
            if ho:
                out["held_out"][f"{oracle}|{lvl}"] = ho
    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = a.out or os.path.join(pins.RESULTS, "exploratory", f"livewidth.{stamp}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    paths = [path]
    if extract and header:
        upath = os.path.join(os.path.dirname(path), f"livewidth-units.{stamp}.csv.gz")
        with gzip.open(upath, "wt", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(header)
            w.writerows(extract)
        paths.append(upath)
    for p in paths:
        digest = hashlib.sha256(open(p, "rb").read()).hexdigest()
        with open(p + ".sha256", "w") as fh:
            fh.write(f"{digest}  {os.path.basename(p)}\n")
        print(f"\nwrote {p}  (exploratory; not part of the plan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
