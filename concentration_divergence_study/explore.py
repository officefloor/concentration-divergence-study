"""The choices the plan delegates to the MLCQ explore half, made before the confirm half is read
(PLAN.md, Primary estimand and decision; Procedure 4).

    cds explore [--results results/mlcq]

Reads ONLY the explore half: score.load_all opens a score file only when the study.json row
names its half `explore`, so no confirm number is computed, loaded or printed here.

  1. X* (class): among paper one's primary families (peak and density; never size, never
     params), the signal whose mad_z flags maximise the pooled MCC against human Blob over the
     reviewed class units. The multiplied form is not consulted.
  2. X*_m (method, secondary 5): the same among structure and density (never params), against
     human Long Method.
  3. The effective-sample gate (PLAN.md, as amended, Amendments, 6): h, the half-width of the
     explore bootstrap interval of the pooled paired difference (X*·D_flow minus X*), over n_e
     explore repositories with at least one reviewed Blob, gives n = ceil(n_e (h / 0.10)^2), at
     least 20; the gate as first registered (from s, the per-repository standard deviation) is
     written beside it, for the record.
  4. The measurer's validation on the explore half (reported before any result).

Writes decisions/explore-choices.json and decisions/measurer-validation.mlcq-explore.json, once:
an existing file is never overwritten. Commit both before ./step8_analyse.sh, which refuses to
run until they are committed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from . import core, forms, pins, score, validate

CHOICES = os.path.join(pins.DECISIONS, "explore-choices.json")
VALIDATION = os.path.join(pins.DECISIONS, "measurer-validation.mlcq-explore.json")


def decide(results: str) -> dict:
    scores = score.load_all(results, halves=("explore",))
    if any(s["meta"].get("half") != "explore" for s in scores):
        raise RuntimeError("a score outside the explore half was loaded")
    cls = core.Population(scores, "joined", "class", "human_blob", "MLCQ explore, human Blob")
    met = core.Population(scores, "joined", "method", "human_method_long_method",
                          "MLCQ explore, human Long Method")
    c = core.choose(cls, forms.CLASS_CANDIDATES)
    m = core.choose(met, forms.METHOD_CANDIDATES)
    g = core.gate(cls, c["chosen"])
    commits = sorted({s["meta"].get("scored_by") for s in scores})
    return {"made_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "harness_commit": pins.harness_commit(), "scored_by": commits,
            "results": os.path.relpath(results, pins.PROJECT_ROOT),
            "explore_repositories": sorted(s["meta"]["key"] for s in scores),
            "class": c, "method": m, "gate": g,
            "note": "made on the MLCQ explore half only, before the confirm half was read"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds explore", description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=os.path.join(pins.RESULTS, "mlcq"))
    a = ap.parse_args(argv)
    for p in (CHOICES, VALIDATION):
        if os.path.exists(p):
            raise SystemExit(f"{p} exists: the explore choices are made once. If they must be "
                             f"remade (a fault found before confirm was read), delete it in its "
                             f"own commit saying why, then re-run.")
    commit = pins.harness_commit() or ""
    if commit.endswith("-dirty"):
        raise SystemExit("the harness has uncommitted changes; commit them first")
    os.makedirs(pins.DECISIONS, exist_ok=True)
    rep = validate.report(a.results, ("explore",))
    validate.print_report(rep)
    with open(VALIDATION, "w") as fh:
        json.dump(rep, fh, indent=1)
    d = decide(a.results)
    with open(CHOICES, "w") as fh:
        json.dump(d, fh, indent=1)
    print(f"\n=== explore choices ({d['class']['n_repos']} explore repositories with reviewed classes) ===")
    for lvl in ("class", "method"):
        ch = d[lvl]
        print(f"{lvl}: X* = {ch['chosen']}  (pooled mad_z MCC on explore: "
              + ", ".join(f"{x} {v:.3f}" if v is not None else f"{x} -" for x, v in ch["criterion"].items()) + ")")
    g = d["gate"]
    print(f"gate: explore half-width h = {g['half_width_explore']:.4f} over {g['n_repos_with_positive_explore']} "
          f"explore repositories with a reviewed Blob -> {g['n_required']} confirm repositories with a "
          f"reviewed Blob needed (as first registered: s = {g['v1']['s']:.4f} -> {g['v1']['n_required']}, "
          f"reported only)")
    print(f"\nwrote {CHOICES} and {VALIDATION}. Commit both now, before the confirm half is read:\n"
          f"    git add decisions && git commit -m 'Record the explore-half choices'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
