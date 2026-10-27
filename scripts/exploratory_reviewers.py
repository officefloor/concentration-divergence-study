#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. How MLCQ's reviewers judge: the leaf exemption and length, review by review.

Written after every oracle of the study had been read (PLAN.md, Amendments, 10); it changes no
verdict. The study scores the strict-majority label per sample. MLCQ also keeps every individual
review (reviewer, severity), so the reading "a reviewer first asks whether the method is a
self-contained algorithm, then whether it is long" can be put to the reviews themselves:

  1. the positive rate (severity other than none) by length bin, for methods that make no call
     (leaves) against the rest, over every Long Method review on a measured unit, both halves;
  2. the same per reviewer, for reviewers with enough reviews of long methods of both kinds;
  3. disagreement: among samples with two or more reviews, the share that are not unanimous, for
     long leaves against long non-leaves;
  4. severity: the distribution of minor/major/critical among long leaves and long non-leaves;
  5. each reviewer's own sense of "long": the length cutoff that best separates their positive
     and negative reviews, and the median length of each;
  6. Blob: the positive rate and disagreement by class size bin, and within the largest bin by
     the class's leaving calls.

Each review is joined to the measured unit the study's label landed on (the same file and the
first method starting at or after the sample's first line, as paper one's rule), so reviews on
units the harness did not measure are left out and counted.

    .venv/bin/python scripts/exploratory_reviewers.py

Writes results/exploratory/reviewers.<utc>.json (with its sha256) and prints the tables.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concentration_divergence_study import boot, pins, records, rules, units  # noqa: E402
from complexity_concentration_study import study as p1  # noqa: E402
import exploratory_ranking as er  # noqa: E402

BINS = [(1, 10), (11, 25), (26, 50), (51, 100), (101, 10 ** 9)]
LONG = 26                       # "long": the bin the tuned MI cutoff of paper one lands near
SEV = {"none": 0, "minor": 1, "major": 2, "critical": 3}


def owner_name(url: str) -> str:
    m = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?/?$", url.strip())
    return m.group(1).lower() if m else url.strip().lower()


def load_reviews() -> list[dict]:
    with open(os.path.join(pins.LABELS, "MLCQCodeSmellSamples.csv"), encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def repo_keys() -> dict:
    """(owner/name, commit[:12]) -> record key, by the measured URL and the original one."""
    rows = records.load_rows(os.path.join(pins.RESULTS, "mlcq"))
    out = {}
    for r in rows:
        for u in (r.get("repo"), r.get("original_url")):
            if u:
                out[(owner_name(u), r["commit"][:12])] = r
    return out


def bin_of(n: float) -> str:
    for lo, hi in BINS:
        if lo <= n <= hi:
            return f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"
    return "0"


def rate(iv):
    return "n/a" if not iv else f"{iv['value']:+.3f} [{iv['lo']:+.3f}, {iv['hi']:+.3f}]"


def main(argv=None) -> int:
    reviews = load_reviews()
    keys = repo_keys()
    by_key_m = defaultdict(list)      # record key -> list of (review, rel path, line)
    by_key_c = defaultdict(list)
    unmapped = Counter()
    for rv in reviews:
        if rv["smell"] not in ("long method", "blob"):
            continue
        row = keys.get((owner_name(rv["repository"]), rv["commit_hash"][:12]))
        if row is None:
            unmapped["repository not measured"] += 1
            continue
        if row.get("error") or row.get("javaparser_error") or not p1.is_usable(row):
            unmapped["repository not usable"] += 1
            continue
        rel = rv["path"].lstrip("/")
        (by_key_m if rv["smell"] == "long method" else by_key_c)[row["key"]].append((rv, rel, int(rv["start_line"]), row.get("half")))
    # per review, the measured unit's features
    mrev, crev = [], []
    for k in sorted(set(by_key_m) | set(by_key_c)):
        rec = records.read_json_gz(records.record_path(os.path.join(pins.RESULTS, "mlcq"), k))
        built = units.joined(rec)
        ml, cl = built["method"], built["class"]
        mc = er.method_calls(rec, ml)
        gate = (mc["calls_any"] >= 1).astype(float)
        z_nloc = rules.mad_z_scale(ml.values["nloc"])[1]
        z_gate = rules.mad_z_scale(ml.values["nloc"] * gate)[1]
        z_tokens = rules.mad_z_scale(ml.values["tokens"])[1]
        z_cog = rules.mad_z_scale(ml.values["cognitive"])[1]
        # the reviewed units the study matched, by file: (start line, index)
        matched = rec["units"]["method"]["god_idx"].get("human_method_long_method_reviewed", [])
        full_ids = rec["units"]["method"]["units"]
        pos_of = {u: j for j, u in enumerate(ml.ids)}
        by_file = defaultdict(list)
        for i in matched:
            j = pos_of.get(full_ids[i])
            if j is None:
                continue
            path, name, line = units._uid_parts(ml.ids[j])
            by_file[path].append((line, j))
        for f in by_file:
            by_file[f].sort()
        for rv, rel, line, half in by_key_m.get(k, []):
            cands = [(l, i) for l, i in by_file.get(rel, []) if l >= line]
            if not cands:
                unmapped["long method review on no measured unit"] += 1
                continue
            l, i = cands[0]
            if l - line > 40:                            # a label that stepped too far is suspect
                unmapped["long method review on no measured unit"] += 1
                continue
            mrev.append({"key": k, "half": half, "reviewer": rv["reviewer_id"], "sample": (k, rel, line),
                         "sev": SEV.get(rv["severity"], 0), "nloc": float(ml.values["nloc"][i]),
                         "tokens": float(ml.values["tokens"][i]), "cc": float(ml.values["cc"][i]),
                         "leaf": bool(mc["calls_all"][i] == 0), "leaf_any": bool(mc["calls_any"][i] == 0),
                         "calls_any": int(mc["calls_any"][i]),
                         "calls_internal": int(mc["calls_all"][i]), "z_nloc": float(z_nloc[i]),
                         "flag_gate": bool(z_gate[i] >= 3.5), "flag_tokens": bool(z_tokens[i] >= 3.5),
                         "flag_cog": bool(z_cog[i] >= 3.5)})
        cidx = {f: j for j, f in enumerate(cl.ids)}
        cf = er.class_forms(cl, ml, mc)
        z_sum = rules.mad_z_scale(cl.values["nloc_sum"])[1]
        for rv, rel, line, half in by_key_c.get(k, []):
            j = cidx.get(rel)
            if j is None:
                unmapped["blob review on no measured class"] += 1
                continue
            crev.append({"key": k, "half": half, "reviewer": rv["reviewer_id"], "sample": (k, rel),
                         "sev": SEV.get(rv["severity"], 0), "nloc_sum": float(cl.values["nloc_sum"][j]),
                         "nom": float(cl.values["nom"][j]), "calls_leave": float(cf["calls_leave"][j]),
                         "nloc_max": float(cl.values["nloc_max"][j]), "z_sum": float(z_sum[j])})
    out = {"kind": "exploratory", "made_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
           "harness_commit": pins.harness_commit(), "note": __doc__.splitlines()[0],
           "reviews": {"long_method": len(mrev), "blob": len(crev), "unmapped": dict(unmapped)}}
    print(f"Long Method reviews on measured units: {len(mrev)} by {len(set(r['reviewer'] for r in mrev))} reviewers "
          f"({len(set(r['sample'] for r in mrev))} samples); Blob reviews: {len(crev)}; left out: {dict(unmapped)}")
    print(f"  leaf = no internal call (the registered catchment under flow); methods with no call of any kind: "
          f"{sum(1 for r in mrev if r['leaf_any'])} reviews, of which {LONG}+ lines: {sum(1 for r in mrev if r['leaf_any'] and r['nloc'] >= LONG)}")
    out["no_call_at_all"] = {"reviews": sum(1 for r in mrev if r["leaf_any"]), "long": sum(1 for r in mrev if r["leaf_any"] and r["nloc"] >= LONG)}

    # 1. positive rate by length bin, leaves against the rest ---------------------------------
    def table(rows, keyfn, groups):
        t = defaultdict(lambda: [0, 0])
        for r in rows:
            g = keyfn(r)
            t[g][0] += 1
            t[g][1] += r["sev"] > 0
        return {g: {"reviews": t[g][0], "positive": t[g][1], "rate": (t[g][1] / t[g][0] if t[g][0] else None)} for g in groups if g in t}
    bins = [bin_of(lo) for lo, _ in BINS]
    t1 = {"leaf": table([r for r in mrev if r["leaf"]], lambda r: bin_of(r["nloc"]), bins),
          "non-leaf": table([r for r in mrev if not r["leaf"]], lambda r: bin_of(r["nloc"]), bins)}
    print("\n1. Long Method: share of reviews calling the method a Long Method (any severity), by length and leaf status")
    print(f"   {'lines':8s} {'leaf: n':>8s} {'rate':>6s}   {'non-leaf: n':>12s} {'rate':>6s}")
    for b in bins:
        a, c = t1["leaf"].get(b), t1["non-leaf"].get(b)
        print(f"   {b:8s} {a['reviews'] if a else 0:8d} {a['rate'] if a else 0:6.2f}   {c['reviews'] if c else 0:12d} {c['rate'] if c else 0:6.2f}")
    # the paired difference over repositories, long methods only (per-repository rates pooled)
    def pooled_diff(rows, cond_a, cond_b):
        ks = sorted(set(r["key"] for r in rows))
        A = np.array([[sum(1 for r in rows if r["key"] == k and cond_a(r)), sum(r["sev"] > 0 for r in rows if r["key"] == k and cond_a(r))] for k in ks], float)
        B = np.array([[sum(1 for r in rows if r["key"] == k and cond_b(r)), sum(r["sev"] > 0 for r in rows if r["key"] == k and cond_b(r))] for k in ks], float)
        m = boot.multiplicities(len(ks))
        def rate_of(M, w):
            n, p = (w @ M[:, 0]), (w @ M[:, 1])
            return np.where(n > 0, p / np.maximum(n, 1), np.nan)
        full = (B[:, 1].sum() / max(B[:, 0].sum(), 1)) - (A[:, 1].sum() / max(A[:, 0].sum(), 1))
        reps = rate_of(B, m) - rate_of(A, m)
        return boot.interval(float(full), reps, len(ks), len(m))
    long_rows = [r for r in mrev if r["nloc"] >= LONG]
    d1 = pooled_diff(long_rows, lambda r: not r["leaf"], lambda r: r["leaf"])
    print(f"   long methods ({LONG}+ lines): positive rate, leaves minus non-leaves, bootstrap over repositories: {rate(d1)}")
    out["by_length_and_leaf"] = t1
    out["long_leaf_minus_nonleaf"] = d1
    # the registered leaf diagnostic's population: the reviewed methods X*_m (cognitive) flags
    fl = [r for r in mrev if r["flag_cog"]]
    fl_leaf = [r for r in fl if r["leaf"]]; fl_rest = [r for r in fl if not r["leaf"]]
    out["flagged_by_cognitive"] = {"leaf": {"reviews": len(fl_leaf), "median_lines": float(np.median([r["nloc"] for r in fl_leaf])) if fl_leaf else None,
                                            "rate": float(np.mean([r["sev"] > 0 for r in fl_leaf])) if fl_leaf else None},
                                   "rest": {"reviews": len(fl_rest), "median_lines": float(np.median([r["nloc"] for r in fl_rest])) if fl_rest else None,
                                            "rate": float(np.mean([r["sev"] > 0 for r in fl_rest])) if fl_rest else None}}
    print(f"   among reviews of methods X*_m (cognitive) flags at 3.5: leaves n {len(fl_leaf)}, median {out['flagged_by_cognitive']['leaf']['median_lines']} lines, "
          f"positive rate {out['flagged_by_cognitive']['leaf']['rate']}; rest n {len(fl_rest)}, median {out['flagged_by_cognitive']['rest']['median_lines']} lines, rate {out['flagged_by_cognitive']['rest']['rate']}")

    # 2. per reviewer ----------------------------------------------------------------------------
    print(f"\n2. Per reviewer, long methods ({LONG}+ lines): positive rate for leaves and non-leaves (reviewers with 5+ of each)")
    per = {}
    for rv in sorted(set(r["reviewer"] for r in mrev), key=int):
        rr = [r for r in long_rows if r["reviewer"] == rv]
        leaf = [r for r in rr if r["leaf"]]
        non = [r for r in rr if not r["leaf"]]
        allr = [r for r in mrev if r["reviewer"] == rv]
        per[rv] = {"reviews": len(allr), "long_leaf": len(leaf), "long_leaf_rate": (np.mean([r["sev"] > 0 for r in leaf]) if leaf else None),
                   "long_nonleaf": len(non), "long_nonleaf_rate": (np.mean([r["sev"] > 0 for r in non]) if non else None)}
    shown = {rv: p for rv, p in per.items() if p["long_leaf"] >= 5 and p["long_nonleaf"] >= 5}
    lower = sum(1 for p in shown.values() if p["long_leaf_rate"] < p["long_nonleaf_rate"])
    print(f"   {'reviewer':9s} {'reviews':>8s} {'long leaves':>12s} {'rate':>6s} {'long non-leaves':>16s} {'rate':>6s}")
    for rv, p in shown.items():
        print(f"   {rv:9s} {p['reviews']:8d} {p['long_leaf']:12d} {p['long_leaf_rate']:6.2f} {p['long_nonleaf']:16d} {p['long_nonleaf_rate']:6.2f}")
    print(f"   leaf rate below non-leaf rate for {lower} of {len(shown)} reviewers shown")
    out["per_reviewer"] = per
    out["per_reviewer_leaf_lower"] = [lower, len(shown)]

    # 3. disagreement --------------------------------------------------------------------------
    print("\n3. Disagreement: samples with 2+ reviews that are not unanimous (some none, some positive)")
    samples = defaultdict(list)
    for r in mrev:
        samples[r["sample"]].append(r)
    def disagree(cond):
        ss = [v for v in samples.values() if len(v) >= 2 and cond(v[0])]
        mixed = sum(1 for v in ss if 0 < sum(r["sev"] > 0 for r in v) < len(v))
        return len(ss), mixed, (mixed / len(ss) if ss else None)
    d3 = {"long leaf": disagree(lambda r: r["leaf"] and r["nloc"] >= LONG),
          "long non-leaf": disagree(lambda r: (not r["leaf"]) and r["nloc"] >= LONG),
          "short leaf": disagree(lambda r: r["leaf"] and r["nloc"] < LONG),
          "short non-leaf": disagree(lambda r: (not r["leaf"]) and r["nloc"] < LONG)}
    for g, (n, mixed, share) in d3.items():
        print(f"   {g:16s} samples {n:4d}  not unanimous {mixed:4d}  share {share if share is not None else 0:5.2f}")
    out["disagreement"] = d3

    # 4. severity ------------------------------------------------------------------------------
    print(f"\n4. Severity among long methods ({LONG}+ lines): share of reviews at each level")
    d4 = {}
    for g, cond in (("long leaf", lambda r: r["leaf"]), ("long non-leaf", lambda r: not r["leaf"])):
        rr = [r for r in long_rows if cond(r)]
        c = Counter(r["sev"] for r in rr)
        d4[g] = {lvl: (c[i] / len(rr) if rr else None) for lvl, i in SEV.items()}
        print(f"   {g:16s} n {len(rr):4d}  " + "  ".join(f"{lvl} {(d4[g][lvl] or 0):.2f}" for lvl in SEV))
    out["severity"] = d4

    # 5. each reviewer's sense of long ---------------------------------------------------------
    print("\n5. Each reviewer's own cutoff: the length that best separates their positive from their negative reviews (MCC), reviewers with 10+ positives")
    d5 = {}
    for rv, p in per.items():
        rr = [r for r in mrev if r["reviewer"] == rv and not r["leaf"]]
        pos = [r for r in rr if r["sev"] > 0]
        neg = [r for r in rr if r["sev"] == 0]
        if len(pos) < 10 or len(neg) < 10:
            continue
        lens = np.array([r["nloc"] for r in rr]); lab = np.array([r["sev"] > 0 for r in rr])
        best = None
        for t in np.unique(lens):
            f = lens >= t
            tp, fp, fn, tn = (f & lab).sum(), (f & ~lab).sum(), (~f & lab).sum(), (~f & ~lab).sum()
            den = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
            mcc = (tp * tn - fp * fn) / np.sqrt(den) if den else 0
            if best is None or mcc > best[1]:
                best = (float(t), float(mcc))
        d5[rv] = {"non_leaf_reviews": len(rr), "positives": len(pos), "median_len_positive": float(np.median([r["nloc"] for r in pos])),
                  "median_len_negative": float(np.median([r["nloc"] for r in neg])), "best_cutoff": best[0], "best_mcc": best[1]}
        print(f"   reviewer {rv:4s} non-leaf reviews {len(rr):4d}  positives {len(pos):3d}  median lines: positive {d5[rv]['median_len_positive']:5.0f} negative {d5[rv]['median_len_negative']:5.0f}  best cutoff >= {best[0]:4.0f} lines (MCC {best[1]:.2f})")
    out["reviewer_cutoffs"] = d5

    # 6. Blob -------------------------------------------------------------------------------
    print("\n6. Blob: share of reviews calling the class a Blob, by total lines of the class")
    cbins = [(1, 100), (101, 250), (251, 500), (501, 1000), (1001, 10 ** 9)]
    def cbin(n):
        for lo, hi in cbins:
            if lo <= n <= hi:
                return f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"
        return "0"
    d6 = {}
    csamples = defaultdict(list)
    for r in crev:
        csamples[r["sample"]].append(r)
    for lo, hi in cbins:
        b = f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"
        rr = [r for r in crev if cbin(r["nloc_sum"]) == b]
        ss = [v for v in csamples.values() if len(v) >= 2 and cbin(v[0]["nloc_sum"]) == b]
        mixed = sum(1 for v in ss if 0 < sum(r["sev"] > 0 for r in v) < len(v))
        d6[b] = {"reviews": len(rr), "rate": (np.mean([r["sev"] > 0 for r in rr]) if rr else None),
                 "samples_2plus": len(ss), "not_unanimous": mixed}
        print(f"   {b:10s} reviews {len(rr):5d}  Blob rate {d6[b]['rate'] if rr else 0:5.2f}  samples with 2+ reviews {len(ss):4d}  not unanimous {mixed / len(ss) if ss else 0:5.2f}")
    big = [r for r in crev if r["nloc_sum"] >= 501]
    if big:
        q = np.quantile([r["calls_leave"] for r in big], [1 / 3, 2 / 3])
        ter = {"low": [r for r in big if r["calls_leave"] <= q[0]], "mid": [r for r in big if q[0] < r["calls_leave"] <= q[1]],
               "high": [r for r in big if r["calls_leave"] > q[1]]}
        d6["large_by_calls"] = {t: {"reviews": len(v), "rate": float(np.mean([r["sev"] > 0 for r in v])) if v else None,
                                    "median_lines": float(np.median([r["nloc_sum"] for r in v])) if v else None} for t, v in ter.items()}
        print("   classes of 501+ lines, by tertile of leaving calls: " + "; ".join(
            f"{t}: n {len(v)}, Blob rate {np.mean([r['sev'] > 0 for r in v]):.2f}, median lines {np.median([r['nloc_sum'] for r in v]):.0f}" for t, v in ter.items()))
    out["blob"] = d6

    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = os.path.join(pins.RESULTS, "exploratory", f"reviewers.{out['made_utc']}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else (str(o) if not isinstance(o, float) else o))
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with open(path + ".sha256", "w") as fh:
        fh.write(f"{digest}  {os.path.basename(path)}\n")
    print(f"\nwrote {path}  (exploratory; not part of the plan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
