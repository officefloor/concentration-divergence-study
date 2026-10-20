"""The measurer's validation report (PLAN.md, Units and measures; Diagnostics, read first).

    cds validate --results results/<set> [--half explore] [--out FILE]

Read from the measured records alone (no score, no label outcome):

  join          the share of paper one's (lizard's) Java methods joined to a measurer method, the
                ambiguous joins, and the methods the measurer finds that lizard does not
  agreement     per complexity field, over the joined methods: the share of exact matches and
                the rank correlation of the measurer's value with lizard's (pooled over units,
                and the median within repositories): the JavaParser-only set's validity
  calls         per repository, the share of calls resolved internal, to the JDK, to an
                unanalysed repository file, unresolved, "should have resolved", or left by the
                time budget; summarised by median and quartiles
  pmd           cognitive complexity against PMD's own CognitiveComplexity (rank correlation
                within repositories), for paper one's lexical estimator and for the measurer's
  files         parse failures, the Java 8 fallback, files deleted by the extra rule (by
                segment), DI frameworks declared, labels on deleted files and labels that land
                on a measured unit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

from . import javaparser, records, units
from .score import spearman

FIELDS = units.METHOD_FIELDS


def _q(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and np.isnan(x))]
    if not xs:
        return None
    a = np.array(xs, float)
    return {"median": float(np.median(a)), "q1": float(np.quantile(a, 0.25)),
            "q3": float(np.quantile(a, 0.75)), "n": len(xs)}


def report(results: str, halves: tuple | None = None) -> dict:
    rows = records.load_rows(results)
    pairs = {f: ([], []) for f in FIELDS}
    within = defaultdict(list)
    res_share = defaultdict(list)
    res_total = Counter()
    pmd_p1, pmd_jp = [], []
    join_tot = Counter()
    files = Counter()
    pruned = Counter()
    di = Counter()
    labels = defaultdict(Counter)
    n = 0
    for row in rows:
        if halves is not None and row.get("half") not in halves:
            continue
        path = records.record_path(results, row["key"])
        if not os.path.exists(path):
            continue
        rec = records.read_json_gz(path)
        r = rec["row"]
        for seg, k in ((r.get("pruned") or {}).get("by_segment") or {}).items():
            pruned[seg] += k
        for fw in (r.get("di") or {}).get("frameworks", []):
            di[fw] += 1
        di["(repositories)"] += 1
        for lab, d in (r.get("human_labels") or {}).items():
            labels[lab]["labelled"] += d.get("labelled", 0)
            labels[lab]["measured"] += d.get("measured", 0)
        for lab, k in (r.get("labels_out_of_scope") or {}).items():
            labels[lab]["on_deleted_files"] += k
        if r.get("error") or rec.get("javaparser") is None or rec.get("units") is None:
            files["repositories_without_measurement"] += 1
            continue
        n += 1
        doc = rec["javaparser"]
        files["files"] += len(doc["files"])
        files["failed"] += sum(1 for f in doc["files"] if f["level"] == "failed")
        files["java8_fallback"] += sum(1 for f in doc["files"] if f["level"] == "JAVA_8")
        files["budget_exhausted_repositories"] += int(bool(doc.get("budget_exhausted")))
        tot = Counter()
        for f in doc["files"]:
            for m in f["methods"]:
                for c in m["calls"]:
                    tot[javaparser.RESOLUTIONS[c[2]]] += 1
        s = sum(tot.values())
        res_total.update(tot)
        if s:
            for name in javaparser.RESOLUTIONS:
                res_share[name].append(tot[name] / s)
        J = units.joined(rec)
        P = units.javaparser_set(rec)
        for k, v in J["join"].items():
            join_tot[k] += v
        jm, pm = J["method"], P["method"]
        pos = {u: i for i, u in enumerate(pm.ids)}
        li, pi = [], []
        for i, uid in enumerate(jm.ids):
            j = pos.get(uid)
            if j is not None and jm.coupled[i]:
                li.append(i)
                pi.append(j)
        li, pi = np.array(li, int), np.array(pi, int)
        for f in FIELDS:
            a, b = jm.values[f][li], pm.values[f][pi]
            pairs[f][0].extend(a.tolist())
            pairs[f][1].extend(b.tolist())
            within[f].append(spearman(a, b))
        # cognitive against PMD's value, on paper one's Java units PMD reported (> 0)
        mu = rec["units"]["method"]
        pv = (mu.get("pmd_values") or {}).get("cognitive")
        if pv:
            idx = [i for i, u in enumerate(mu["units"]) if u.split("::", 1)[0].endswith(".java")
                   and pv[i] not in (None, 0)]
            if len(idx) >= 3:
                pmd = np.array([pv[i] for i in idx], float)
                p1v = np.array([mu["values"]["cognitive"][i] for i in idx], float)
                pmd_p1.append(spearman(p1v, pmd))
                both = [(pos[mu["units"][i]], k) for k, i in enumerate(idx) if mu["units"][i] in pos]
                if len(both) >= 3:
                    pmd_jp.append(spearman(np.array([pm.values["cognitive"][b] for b, _ in both]),
                                           np.array([pmd[k] for _, k in both])))
    agree = {}
    for f in FIELDS:
        a, b = np.array(pairs[f][0]), np.array(pairs[f][1])
        agree[f] = {"n": len(a), "exact": float((np.abs(a - b) < 1e-9).mean()) if len(a) else None,
                    "spearman_pooled": spearman(a, b) if len(a) >= 3 else None,
                    "spearman_within": _q(within[f])}
    jt = dict(join_tot)
    if jt.get("lizard_units"):
        jt["joined_share"] = jt["joined"] / jt["lizard_units"]
    if jt.get("measurer_units"):
        jt["measurer_not_joined_share"] = jt["measurer_not_joined"] / jt["measurer_units"]
    ctot = sum(res_total.values())
    return {"results": results, "halves": list(halves) if halves else None, "repositories": n,
            "join": jt, "agreement": agree,
            "calls": {"total": dict(res_total),
                      "share_total": {k: v / ctot for k, v in res_total.items()} if ctot else {},
                      "share_per_repository": {k: _q(v) for k, v in res_share.items()}},
            "pmd_cognitive_spearman": {"paper_one": _q(pmd_p1), "measurer": _q(pmd_jp)},
            "files": dict(files), "pruned_by_segment": dict(pruned), "di": dict(di),
            "labels": {k: dict(v) for k, v in labels.items()}}


def print_report(rep: dict) -> None:
    print(f"\n=== measurer validation: {rep['results']} ({rep['halves'] or 'all halves'}), "
          f"{rep['repositories']} repositories ===")
    j = rep["join"]
    print(f"join: {j.get('joined')} of {j.get('lizard_units')} lizard methods joined "
          f"({100 * j.get('joined_share', 0):.2f}%), {j.get('ambiguous')} ambiguous; the measurer "
          f"finds {j.get('measurer_not_joined')} methods lizard does not "
          f"({100 * j.get('measurer_not_joined_share', 0):.2f}% of its {j.get('measurer_units')})")
    print("field agreement over the joined methods (measurer vs lizard):")
    for f, a in rep["agreement"].items():
        w = a["spearman_within"] or {}
        print(f"  {f:12} exact {a['exact'] if a['exact'] is None else round(a['exact'], 3)!s:>6}  "
              f"rho pooled {a['spearman_pooled'] if a['spearman_pooled'] is None else round(a['spearman_pooled'], 3)!s:>6}  "
              f"rho within median {round(w['median'], 3) if w else None}")
    print("calls by resolution (share of all calls):",
          {k: round(v, 3) for k, v in rep["calls"]["share_total"].items()})
    print("per repository (median share):",
          {k: round(v["median"], 3) for k, v in rep["calls"]["share_per_repository"].items() if v})
    pc = rep["pmd_cognitive_spearman"]
    print(f"cognitive vs PMD (median within-repository rho): paper one "
          f"{(pc['paper_one'] or {}).get('median')}, measurer {(pc['measurer'] or {}).get('median')}")
    print(f"files: {rep['files']}; deleted by the extra rule: {rep['pruned_by_segment']}")
    print(f"DI frameworks declared: {rep['di']}")
    if rep["labels"]:
        print(f"labels: {rep['labels']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds validate", description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True)
    ap.add_argument("--half", action="append", default=None, help="explore and/or confirm")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    rep = report(a.results, tuple(a.half) if a.half else None)
    print_report(rep)
    out = a.out or os.path.join(a.results, "validation" + (f".{'-'.join(a.half)}" if a.half else "") + ".json")
    with open(out, "w") as fh:
        json.dump(rep, fh, indent=1)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
