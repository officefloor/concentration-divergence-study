#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. Split cost against length: what does it cost to bring a long method under the cap?

Written after step 13 was read (PLAN.md, Amendments, 10), so nothing it prints is confirmatory;
it changes no verdict. Step 13 settled the reviewers' Long Method as an absolute length (26 lines
or more, MCC 0.777 on the confirm half) that no width, count or flow form beats. This reads
what follows (SPLIT.md): for every method at or over that trigger, the cheapest segmentation
into pieces of at most the target length (scripts/split.py over the live-width facts of
scripts/livewidth.py, schema 3), and whether its worst seam, its cost, its binding to the
class, or the structural-only variant separates the long methods the reviewers passed from the
ones they flagged. A method under the trigger has no split, so every split form is zero there:
"split width >= k" is length's cutoff with the seam added to it, and the question is whether k
raises precision without losing more recall than it is worth.

Each method form is read three ways:

  outlier    the registered rule (modified z >= 3.5 per repository), pooled MCC with the paired
             bootstrap against the competitors, as scripts/exploratory_livewidth.py reads it;
  threshold  an absolute cutoff, the same for every repository (a seam of k or more, a cost of k
             or more, k pieces or more, length of n or more); on MLCQ the cutoff is chosen on the
             explore half and read once on the confirm half, against length's cutoff chosen the
             same way, and against length x [internal call >= 1] by the registered rule;
  within     among the methods at or over the trigger only, the rank of each form against the
             reviewers' label (Mann-Whitney AUC, bootstrapped over repositories): the ceiling
             for any split form is what it can do among the long methods, since it cannot reach
             a short positive.

Class level reads the binding: the locked share of a class (the pieces its long methods' best
segmentations leave bound to the class, and the remainders, over all pieces and remainders),
with the sum of its methods' split costs and interface, the largest seam, and the counts of
long and of infeasible methods, against the ranking script's class competitors.

    .venv/bin/python scripts/exploratory_split.py                 # every set
    .venv/bin/python scripts/exploratory_split.py --sets mlcq

Writes results/exploratory/split.<utc>.json (with its sha256) and prints the tables, and
results/exploratory/split-units.<utc>.csv.gz: one row per method in a human oracle's universe
with its label, its length, every split reading, and the cuts of its best segmentation. The
parameters (scripts/split.py, Params) are recorded in the output; the defaults are the headline,
the structural-only and no-input-limit variants are read beside them, and nothing else of the
grid in SPLIT.md is tried here.
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
from dataclasses import asdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concentration_divergence_study import boot, pins, records, rules, units  # noqa: E402
from complexity_concentration_study import study as p1  # noqa: E402
import exploratory_ranking as er  # noqa: E402
import exploratory_livewidth as el  # noqa: E402
import livewidth as lw  # noqa: E402
import split as sp  # noqa: E402

SIZE_CALLS = el.SIZE_CALLS
METHOD_COMPETITORS = {"size_calls": SIZE_CALLS, "size": "nloc", "complexity": "tokens"}
CLASS_COMPETITORS = er.COMPETITORS["class"]
NLOC_N = el.NLOC_N
SEAM_K = (1, 2, 3, 4, 5, 6, 8)
COST_K = (2, 3, 4, 6, 8, 10, 15, 20)
COUNT_K = (1, 2, 3, 4, 6)
SHARE_K = (0.5, 0.75, 0.9, 1.0)
VARIANTS = {"": sp.DEFAULT, " [structural]": sp.STRUCTURAL, " [no input limit]": sp.UNLIMITED}
# the forms read within the long methods, by AUC against the label
WITHIN = ("split width", "split cost", "split interface", "split pieces", "split locked share",
          "split width [structural]", "split width [no input limit]", "nloc", "tokens", "cc", "cognitive")


def own_call_lines(fm: dict, rm: dict | None, fidx: int) -> tuple[list, bool]:
    """The lines of the calls that resolve to the method's own file with no receiver variable:
    calls to the class's own methods, as far as the record tells (SPLIT.md). Misaligned when the
    facts' calls and the record's differ in number."""
    if rm is None or len(rm["calls"]) != len(fm.get("calls", [])):
        return [], True
    lines = [c[lw.C_LINE] for c, r in zip(fm["calls"], rm["calls"])
             if r[2] == er.I and r[3] == fidx and not c[lw.C_RECEIVER]]
    return lines, False


def method_splits(facts: dict, rec: dict, ml: units.Level) -> tuple[dict, dict, int, int]:
    """{form: values over ml.ids}, {unit index: Result (default params)}, units without facts,
    units whose calls did not align (split without own-call binding)."""
    by = lw.by_unit(facts)
    jp = {}
    for path, ms in units._measurer_files(rec["javaparser"]).items():
        for m, fidx in ms:
            jp.setdefault((path, m["name"], m["name_line"]), (m, fidx))
    names = ["split width", "split cost", "split interface", "split pieces", "split infeasible",
             "split locked pieces", "split locked share", "split remainder locked",
             "split width [structural]", "split infeasible [structural]",
             "split width [no input limit]", "split infeasible [no input limit]"]
    out = {n: np.zeros(ml.n) for n in names}
    results, missing, misaligned = {}, 0, 0
    for i, uid in enumerate(ml.ids):
        key = units._uid_parts(uid)
        m = by.get(key)
        if m is None:
            missing += 1
            continue
        rm, fidx = jp.get(key, (None, -1))
        own, mis = own_call_lines(m, rm, fidx)
        nloc = int(ml.values["nloc"][i])
        if nloc < sp.DEFAULT.trigger:
            continue                    # every split form is zero under the trigger
        misaligned += mis
        r = sp.split(m, own, sp.DEFAULT, nloc)
        results[i] = r
        out["split width"][i] = r.width
        out["split cost"][i] = r.cost
        out["split interface"][i] = r.interface
        out["split pieces"][i] = r.pieces
        out["split infeasible"][i] = 0.0 if r.feasible else 1.0
        out["split locked pieces"][i] = r.locked + (1 if r.remainder_locked else 0)
        out["split locked share"][i] = (r.locked + (1 if r.remainder_locked else 0)) / (r.pieces + 1)
        out["split remainder locked"][i] = 1.0 if r.remainder_locked else 0.0
        for suffix, p in list(VARIANTS.items())[1:]:
            v = sp.split(m, own, p, nloc)
            out[f"split width{suffix}"][i] = v.width
            out[f"split infeasible{suffix}"][i] = 0.0 if v.feasible else 1.0
    return out, results, missing, misaligned


def method_forms(ml: units.Level, mc: dict, w: dict) -> dict:
    base = er.method_forms(ml, mc)
    f = {k: base[k] for k in ("tokens", "cc", "cognitive", "nloc", SIZE_CALLS)}
    f.update(w)
    for k in (1, 2, 3):
        f[f"nloc x [split width >= {k}]"] = ml.values["nloc"] * (w["split width"] >= k)
    return f


def thresholds(name: str) -> list[tuple[str, float]]:
    if " x " in name:
        return []
    if name.startswith(("split width", "max_m split width")):
        return [(f">={k}", float(k)) for k in SEAM_K]
    if name.startswith(("split cost", "split interface", "sum_m split")):
        return [(f">={k}", float(k)) for k in COST_K]
    if name.startswith(("split pieces", "split locked pieces", "count_m")):
        return [(f">={k}", float(k)) for k in COUNT_K]
    if name.startswith(("split locked share", "locked share")):
        return [(f">={k}", float(k)) for k in SHARE_K]
    if name in ("split infeasible", "split remainder locked") or name.startswith("split infeasible"):
        return [(">=1", 1.0)]
    if name in ("nloc", "nloc_max"):
        return [(f">={n}", float(n)) for n in NLOC_N]
    return []


def class_forms(cl: units.Level, ml: units.Level, mc: dict, w: dict, results: dict) -> dict:
    f = er.class_forms(cl, ml, mc)
    keep = {k: f[k] for k in CLASS_COMPETITORS.values()} | {k: f[k] for k in ("nloc_max", "nloc_sum")}
    fidx = {p: i for i, p in enumerate(cl.ids)}
    cost = np.zeros(cl.n)
    interface = np.zeros(cl.n)
    top = np.zeros(cl.n)
    longs = np.zeros(cl.n)
    infeasible = np.zeros(cl.n)
    locked = np.zeros(cl.n)
    parts = np.zeros(cl.n)
    for j, p in enumerate(ml.c["file"]):
        if p not in fidx or j not in results:
            continue
        c = fidx[p]
        r = results[j]
        longs[c] += 1
        cost[c] += r.cost if r.feasible else 0.0
        interface[c] += r.interface
        top[c] = max(top[c], r.width)
        infeasible[c] += 0.0 if r.feasible else 1.0
        locked[c] += r.locked + (1 if r.remainder_locked else 0)
        parts[c] += r.pieces + 1
    keep["count_m long methods"] = longs
    keep["count_m split infeasible"] = infeasible
    keep["sum_m split cost"] = cost
    keep["sum_m split interface"] = interface
    keep["max_m split width"] = top
    keep["locked share"] = np.where(parts > 0, locked / np.maximum(parts, 1), 0.0)
    keep["count_m split locked pieces"] = locked
    return keep


def score_set(set_name: str, facts_dir: str) -> tuple[dict, dict, list]:
    results_dir = os.path.join(pins.RESULTS, set_name)
    rows = records.load_rows(results_dir)
    out: dict = {}
    cover = {"records": 0, "no_facts": 0, "units": 0, "units_without_facts": 0, "long_units": 0,
             "long_without_facts": 0, "calls_misaligned": 0}
    wanted = [(h, lvl, o) for s, h, lvl, o in er.POPULATIONS if s == set_name]
    extract: list = []
    for k, r in enumerate(rows):
        if r.get("error") or r.get("javaparser_error") or not p1.is_usable(r):
            continue
        cover["records"] += 1
        fpath = os.path.join(facts_dir, set_name, r["key"] + ".json.gz")
        if not os.path.exists(fpath):
            cover["no_facts"] += 1
            continue
        lwrec = records.read_json_gz(fpath)
        if lwrec["facts"].get("livewidth") != lw.SCHEMA:
            cover["no_facts"] += 1
            continue
        rec = records.read_json_gz(records.record_path(results_dir, r["key"]))
        built = units.joined(rec)
        ml, cl = built["method"], built["class"]
        mc = er.method_calls(rec, ml)
        w, res, missing, misaligned = method_splits(lwrec["facts"], rec, ml)
        cover["units"] += ml.n
        cover["units_without_facts"] += missing
        cover["calls_misaligned"] += misaligned
        long_mask = ml.values["nloc"] >= sp.DEFAULT.trigger
        cover["long_units"] += int(long_mask.sum())
        by = lw.by_unit(lwrec["facts"])
        has = np.array([units._uid_parts(u) in by for u in ml.ids], dtype=bool)
        cover["long_without_facts"] += int((long_mask & ~has).sum())
        forms = {"method": method_forms(ml, mc, w), "class": class_forms(cl, ml, mc, w, res)}
        levels = {"method": ml, "class": cl}
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
                "counts": defaultdict(list), "within": defaultdict(list)})
            for name, vals in forms[lvl].items():
                vals = np.asarray(vals, float)
                masks = [rules.mad_z(vals)] + [vals >= c for _, c in thresholds(name)]
                slot["counts"][name].append([er.cells(m, pos, univ) for m in masks])
            slot["keys"].append(r["key"])
            if lvl == "method":
                sel = univ & long_mask & has
                for name in WITHIN:
                    vals = np.asarray(forms["method"][name], float)
                    slot["within"][name].append((vals[sel & pos].tolist(), vals[sel & ~pos].tolist()))
                if oracle.startswith("human_"):
                    for i in np.flatnonzero(univ):
                        rr = res.get(i)
                        cuts = "" if rr is None else ";".join(f"{lo}-{hi}:{a}/{b}/{bd[0]}" for lo, hi, a, b, bd in rr.cuts)
                        extract.append([set_name, r["key"], r.get("half"), oracle, ml.ids[i], int(pos[i]),
                                        int(has[i]), int(ml.values["nloc"][i])]
                                       + [float(forms["method"][n][i]) for n in w] + [cuts])
        if (k + 1) % 50 == 0:
            print(f"  {set_name}: {k + 1}/{len(rows)} records", file=sys.stderr)
    for slot in out.values():
        slot["counts"] = {n: np.array(c, dtype=np.int64) for n, c in slot["counts"].items()}
    return out, cover, extract


def within_long(slot: dict) -> list[dict]:
    """Each WITHIN form's AUC against the label among the long methods, pooled over repositories
    with the bootstrap interval, and the paired difference against length's AUC."""
    per = slot["within"]
    if not per:
        return []
    n = len(slot["keys"])
    m = boot.multiplicities(n)
    rows = []
    aucs = {}
    for name, lists in per.items():
        pos_all = np.concatenate([np.asarray(p, float) for p, _ in lists]) if lists else np.zeros(0)
        neg_all = np.concatenate([np.asarray(q, float) for _, q in lists]) if lists else np.zeros(0)
        full = boot.auc(pos_all, neg_all)
        reps = np.full(len(m), np.nan)
        for b in range(len(m)):
            w = m[b]
            ps = [np.asarray(p, float) for (p, _), c in zip(lists, w) for _ in range(int(c))]
            qs = [np.asarray(q, float) for (_, q), c in zip(lists, w) for _ in range(int(c))]
            if ps and qs:
                a = boot.auc(np.concatenate(ps), np.concatenate(qs))
                reps[b] = np.nan if a is None else a
        aucs[name] = (full, reps)
        rows.append({"form": name, "n_long": int(len(pos_all) + len(neg_all)), "n_positives": int(len(pos_all)),
                     "auc": full, "auc_interval": boot.interval(full, reps, n)})
    lf, lr = aucs.get("nloc", (None, None))
    for row in rows:
        f_, r_ = aucs[row["form"]]
        row["vs_nloc_auc"] = None if lf is None or f_ is None else boot.interval(f_ - lf, r_ - lr, n)
    rows.sort(key=lambda r: -(r["auc"] or 0))
    return rows


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
    cols = list(comp)
    print(f"  outlier (mad_z): {'form':44s} {'MCC':>6s} {'P':>5s} {'R':>5s} {'flag':>6s}  "
          + "  ".join(f"vs {comp[c]:<24s}" for c in cols))
    rows = []
    for name in names:
        x = C[name][:, 0, :]
        row = {"form": name, **el.pooled(x)}
        for c in cols:
            row[f"vs_{c}"] = boot.micro_diff(C[comp[c]][:, 0, :], x, m)
        rows.append(row)
    rows.sort(key=lambda r: -r["mcc"])
    for r in rows:
        p = "  n/a" if r["precision"] is None else f"{r['precision']:5.2f}"
        q = "  n/a" if r["recall"] is None else f"{r['recall']:5.2f}"
        print(f"  {'':17s}{r['form']:44s} {r['mcc']:6.3f} {p} {q} {r['flagged']:6d}  "
              + "  ".join(f"{er.f(r[f'vs_{c}']):27s}" for c in cols))
    thr = {}
    for name in names:
        if len(slot["rules"][name]) == 1:
            continue
        thr[name] = [{"rule": rn, **el.pooled(C[name][:, j, :])} for j, rn in enumerate(slot["rules"][name]) if j]
    if thr:
        print("  threshold (pooled MCC at each absolute cutoff):")
        for name, cells in thr.items():
            print(f"    {name:44s} " + " ".join(f"{c['rule']}:{c['mcc']:.3f}" for c in cells))
    within = within_long(slot) if lvl == "method" else []
    if within:
        print(f"  within the long methods (nloc >= {sp.DEFAULT.trigger}), AUC against the label:")
        for r in within:
            iv = r["auc_interval"]
            s = ("n/a" if r["auc"] is None else f"{r['auc']:.3f} (no interval)") if iv is None \
                else f"{iv['value']:.3f} [{iv['lo']:.3f}, {iv['hi']:.3f}]"
            print(f"    {r['form']:36s} n={r['n_long']:5d} positives={r['n_positives']:4d}  AUC {s:28s} vs nloc {er.f(r['vs_nloc_auc'])}")
    return {"population": label, "set_halves": halves, "level": lvl, "oracle": oracle, "n_repos": n,
            "n_units": int(first[:, 0].sum()), "n_positives": int(first[:, 3].sum()),
            "competitors": comp, "outlier": rows, "threshold": thr, "within_long": within,
            "keys": slot["keys"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", nargs="+", default=["mlcq", "fontana", "seed3"])
    ap.add_argument("--facts", default=lw.OUT, help="the live-width facts directory (default: step 13's)")
    ap.add_argument("--out", default=None, help="output path (default results/exploratory/split.<utc>.json)")
    a = ap.parse_args(argv)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"kind": "exploratory", "made_utc": stamp, "harness_commit": pins.harness_commit(),
           "note": __doc__.splitlines()[0],
           "params": {name.strip(" []") or "default": asdict(p) for name, p in VARIANTS.items()},
           "infeasible_width": sp.INFEASIBLE_WIDTH, "coverage": {}, "populations": [], "held_out": {}}
    extract, header = [], None
    for s in a.sets:
        print(f"scoring {s} ...", file=sys.stderr)
        scored, cover, rows = score_set(s, a.facts)
        extract += rows
        for (h, lvl, o), slot in scored.items():
            if lvl == "method" and header is None:
                split_names = [n for n in slot["forms"] if n.startswith("split ")]
                header = ["set", "key", "half", "oracle", "unit", "label", "facts", "nloc"] + split_names + ["cuts"]
        out["coverage"][s] = cover
        print(f"\n{s}: {cover}")
        for key, slot in scored.items():
            out["populations"].append(report(key, slot))
        for lvl, oracle in {(lvl, o) for (h, lvl, o) in scored if h == ("explore",)}:
            ho = el.held_out(scored.get((("explore",), lvl, oracle)), scored.get((("confirm",), lvl, oracle)), lvl)
            if ho:
                out["held_out"][f"{oracle}|{lvl}"] = ho
    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = a.out or os.path.join(pins.RESULTS, "exploratory", f"split.{stamp}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    paths = [path]
    if extract and header:
        upath = os.path.join(os.path.dirname(path), f"split-units.{stamp}.csv.gz")
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
