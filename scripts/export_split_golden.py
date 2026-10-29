#!/usr/bin/env python3
"""EXPLORATORY. The parity data for SinewSlim (~/SinewSlim, DESIGN.md, Testing): split.py's
answers, per variant, for every method at or over the trigger, with the facts they were read on.

SinewSlim ports the search to Java and is accepted when it reproduces split.py exactly on the
study's facts. This writes, per method, the live-width facts (scripts/livewidth.py, schema 3),
the own-call lines and the measurer's nloc as scripts/exploratory_split.py takes them, and the
Result of split.split under each named Params (DEFAULT, STRUCTURAL, UNLIMITED, RECORDS,
FRAMEWORK), as one JSON object per line.

    .venv/bin/python scripts/export_split_golden.py --out FILE.jsonl.gz [--sets mlcq] [--every N]

`--every N` keeps every N-th long method of each set (all by default), for a subset small enough
to commit as a test resource.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from dataclasses import asdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concentration_divergence_study import pins, records  # noqa: E402
import exploratory_split as es  # noqa: E402
import livewidth as lw  # noqa: E402
import split as sp  # noqa: E402

VARIANTS = {"default": sp.DEFAULT, "structural": sp.STRUCTURAL, "unlimited": sp.UNLIMITED,
            "records": sp.RECORDS, "framework": sp.FRAMEWORK}
FACTS = ("decl_line", "name_line", "end_line", "loops", "vars", "tree")


def result(r: sp.Result) -> dict:
    d = asdict(r)
    d.pop("params")
    return d


def export(set_name: str, out, every: int, counts: dict) -> None:
    results_dir = os.path.join(pins.RESULTS, set_name)
    facts_dir = os.path.join(lw.OUT, set_name)
    seen = 0
    for r in records.load_rows(results_dir):
        if r.get("error") or r.get("javaparser_error"):
            continue
        fpath = os.path.join(facts_dir, r["key"] + ".json.gz")
        if not os.path.exists(fpath):
            continue
        lwrec = records.read_json_gz(fpath)
        if lwrec["facts"].get("livewidth") != lw.SCHEMA:
            continue
        rec = records.read_json_gz(records.record_path(results_dir, r["key"]))
        by = lw.by_unit(lwrec["facts"])
        done = set()
        for fidx, f in enumerate(rec["javaparser"].get("files", [])):
            if f["level"] == "failed":
                continue
            for rm in f["methods"]:
                key = (f["path"], rm["name"], rm["name_line"])
                if key in done or rm.get("nloc", 0) < sp.DEFAULT.trigger:
                    continue
                done.add(key)
                m = by.get(key)
                if m is None or "tree" not in m:
                    continue
                own, mis = es.own_call_lines(m, rm, fidx)
                if mis:
                    counts["misaligned"] += 1
                    continue
                seen += 1
                if (seen - 1) % every:
                    continue
                nloc = int(rm["nloc"])
                row = {"set": set_name, "key": r["key"], "path": f["path"], "name": rm["name"], "nloc": nloc,
                       "own": own, "facts": {k: m[k] for k in FACTS if k in m},
                       "expect": {name: result(sp.split(m, own, p, nloc)) for name, p in VARIANTS.items()}}
                out.write(json.dumps(row, separators=(",", ":")) + "\n")
                counts["methods"] += 1
    print(f"  {set_name}: {seen} long methods, {counts['methods']} written so far", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sets", nargs="+", default=["mlcq", "seed3", "fontana"])
    ap.add_argument("--every", type=int, default=1)
    a = ap.parse_args(argv)
    counts = {"methods": 0, "misaligned": 0}
    with gzip.open(a.out, "wt", encoding="utf-8") as out:
        out.write(json.dumps({"params": {n: asdict(p) for n, p in VARIANTS.items()}}, separators=(",", ":")) + "\n")
        for s in a.sets:
            export(s, out, a.every, counts)
    print(f"wrote {counts['methods']} methods to {a.out} ({counts['misaligned']} skipped: calls misaligned)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
