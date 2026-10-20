"""The seed-3 tool-oracle sample: from the sampler's draw to the repositories measured.

    cds seed3-select [--source sample/open-source-repository-sample.seed3.csv]

PLAN.md, Oracles 3: Java repositories drawn by open-source-repository-sampler with seed 3, 500
usable, stratified by tier as the sampler does, with every repository that appears in paper
one's pilot (seed 1), its seed-2 sample or MLCQ excluded BEFORE measurement. The sampler has no
flag for a list of repositories, so ./step3_sample.sh draws a margin above 500
(pins.SEED3_DRAW_TARGET) and this step takes, in the sampler's draw order, the first 500 usable
repositories that are not excluded. The selection is a pure function of the draw and the
exclusion lists, so step 5 re-derives it and refuses to measure if the file differs.

Writes sample/seed3-measured.csv (sampler columns, the 500 rows) and sample/seed3-measured.json
(each excluded repository with the list it appears in, the sha256 of every input).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from . import pins, records

SOURCE = os.path.join(pins.SAMPLE, "open-source-repository-sample.seed3.csv")
MEASURED = os.path.join(pins.SAMPLE, "seed3-measured.csv")
PAPER_ONE = os.path.join(pins.INPUTS, "paper-one")
EXCLUSION_LISTS = {
    "paper one pilot (seed 1)": os.path.join(PAPER_ONE, "pilot-run-v1-repos.txt"),
    "paper one main sample (seed 2)": os.path.join(PAPER_ONE, "sample", "open-source-repository-sample.csv"),
    "paper one Java supplement (seed 2)": os.path.join(PAPER_ONE, "sample",
                                                      "open-source-repository-sample.java-supplement.csv"),
    "MLCQ": os.path.join(pins.LABELS, "mlcq-repos.mapped.csv"),
    "MLCQ (labelled URL)": os.path.join(pins.LABELS, "mlcq-repos.csv"),
}


def _name(s: str) -> str:
    s = s.strip().lower().rstrip("/")
    s = s[:-4] if s.endswith(".git") else s
    if "github.com" in s:
        s = s.split("github.com", 1)[1].lstrip("/:")
    return s


def excluded_names() -> dict:
    """{owner/name (lower case): [lists it appears in]}, from every exclusion list."""
    out: dict = {}
    for label, path in EXCLUSION_LISTS.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} is missing ({label}); for MLCQ run ./step4_run_mlcq.sh's "
                                    f"preparation first (cds mlcq-prepare)")
        if path.endswith(".txt"):
            names = [ln.split()[0] for ln in open(path) if ln.strip() and not ln.startswith("#")]
        else:
            with open(path, newline="") as fh:
                names = [r["full_name"] for r in csv.DictReader(fh)]   # every row drawn, any status
        for n in names:
            out.setdefault(_name(n), []).append(label)
    return out


def select(source: str = SOURCE, n: int = pins.SEED3_USABLE) -> tuple[list[dict], dict]:
    from open_source_repository_sampler import read_sample
    excl = excluded_names()
    usable = read_sample(source)
    chosen, dropped = [], []
    for r in usable:
        lists = excl.get(_name(r["full_name"])) or excl.get(_name(r["url"]))
        if lists:
            dropped.append({"full_name": r["full_name"], "draw": r["draw"], "in": lists})
            continue
        if len(chosen) < n:
            chosen.append(r)
    if len(chosen) < n:
        raise RuntimeError(f"{source} holds {len(usable)} usable repositories, {len(dropped)} "
                           f"excluded: only {len(chosen)} of the {n} needed. Draw a larger target "
                           f"(pins.SEED3_DRAW_TARGET) into a fresh --out-dir and record why.")
    last = chosen[-1]["draw"]
    report = {"source": os.path.relpath(source, pins.PROJECT_ROOT), "source_sha256": records.sha256(source),
              "exclusion_lists": {k: {"path": os.path.relpath(p, pins.PROJECT_ROOT), "sha256": records.sha256(p)}
                                  for k, p in EXCLUSION_LISTS.items()},
              "usable_in_draw": len(usable), "measured": len(chosen), "last_draw_measured": last,
              "excluded": dropped, "excluded_before_last": sum(1 for d in dropped if d["draw"] <= last),
              "rule": "the first n usable repositories in the sampler's draw order that appear in "
                      "no exclusion list"}
    return chosen, report


def write(chosen: list[dict], report: dict, out_csv: str = MEASURED) -> None:
    from open_source_repository_sampler import files as sfiles
    sfiles.write_csv(out_csv, chosen)
    report = {**report, "measured_sha256": records.sha256(out_csv)}
    with open(out_csv[:-len(".csv")] + ".json", "w") as fh:
        json.dump(report, fh, indent=1)


def check(out_csv: str = MEASURED) -> None:
    """Refuse unless out_csv is exactly what select() gives now."""
    import tempfile
    chosen, report = select()
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "x.csv")
        from open_source_repository_sampler import files as sfiles
        sfiles.write_csv(tmp, chosen)
        if records.sha256(tmp) != records.sha256(out_csv):
            raise RuntimeError(f"{out_csv} is not the selection its draw and exclusion lists give; "
                               f"re-run `cds seed3-select`")


def head(source: str, n: int, out_csv: str) -> int:
    """The first n usable rows of a sample, in draw order, as a sample CSV (the validation step
    measures a prefix of paper one's seed-2 Java draw when asked to)."""
    from open_source_repository_sampler import files as sfiles, read_sample
    rows = read_sample(source)[:n]
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    sfiles.write_csv(out_csv, rows)
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds seed3-select", description=__doc__.splitlines()[0])
    ap.add_argument("--source", default=SOURCE)
    ap.add_argument("--out", default=MEASURED)
    ap.add_argument("--head", type=int, default=None,
                    help="instead: write the first N usable rows of --source to --out")
    args = ap.parse_args(argv)
    if args.head is not None:
        print(f"{head(args.source, args.head, args.out)} rows -> {args.out}")
        return 0
    chosen, report = select(args.source)
    write(chosen, report, args.out)
    print(f"{report['measured']} repositories selected (draws 1..{report['last_draw_measured']}); "
          f"{report['excluded_before_last']} excluded before the last one measured, "
          f"{len(report['excluded'])} in the whole draw -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
