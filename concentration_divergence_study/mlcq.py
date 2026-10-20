"""Prepare the MLCQ material: the labels, the repositories at their labelled commits, the frozen
explore/confirm split, and the moved repositories.

    cds mlcq-prepare [--labels-dir labels]

1. Download MLCQCodeSmellSamples.csv (Madeyski and Lewowski 2020, Zenodo 3666840; sha256
   verified) and convert it with paper one's converter, its strict-majority rule (PLAN.md,
   Oracles 1): labels/mlcq-labels.csv, labels/mlcq-repos.csv, labels/mlcq-summary.json. These are
   byte-for-byte paper one's files.
2. Check the split: paper one's frozen results/mlcq/halves.json, committed here as
   inputs/paper-one/mlcq-halves.json, must name the sha256 of the mlcq-repos.csv just written,
   and stats.assign_halves over it must give exactly that split. Either mismatch stops.
3. Apply mlcq-moved-repositories.csv (PLAN.md, Moved repositories): each listed repository whose
   labelled commit is the one paper one's file names is pointed at its new URL, in a copy of the
   sample and of the labels (labels/mlcq-repos.mapped.csv, labels/mlcq-labels.mapped.csv). A
   mapped repository keeps the half paper one assigned to its old URL. labels/mlcq-frame.json
   records, per URL measured, the half and the original URL, and the mapping's counts.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from complexity_concentration_study import mlcq as p1mlcq
from complexity_concentration_study import stats as p1stats

from . import pins, records

HALVES = os.path.join(pins.INPUTS, "paper-one", "mlcq-halves.json")


def check_halves(repos_csv: str, halves_path: str = HALVES) -> dict:
    from open_source_repository_sampler import read_sample
    ref = json.load(open(halves_path))
    sha = records.sha256(repos_csv)
    if ref["samples"].get("mlcq-repos.csv") != sha:
        raise RuntimeError(f"{repos_csv} (sha256 {sha}) is not the file paper one's split was "
                           f"frozen on ({ref['samples']}); the converter or the download differs")
    items = {}
    for r in read_sample(repos_csv):
        items.setdefault(r["url"], (r.get("language"), r.get("tier")))
    halves = p1stats.assign_halves(list(items.items()), stratum_of=lambda it: it[1],
                                   key_of=lambda it: it[0])
    if halves != ref["halves"]:
        raise RuntimeError("stats.assign_halves no longer reproduces paper one's frozen split")
    return ref["halves"]


def apply_moved(repos_csv: str, labels_csv: str, halves: dict, moved_csv: str, out_dir: str) -> dict:
    from open_source_repository_sampler import files as sfiles
    moved = {}
    with open(moved_csv, newline="") as fh:
        for m in csv.DictReader(fh):
            moved[m["old_url"].rstrip("/").lower()] = m
    with open(repos_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    new_of, frame_halves, original = {}, {}, {}
    applied, unmapped, commit_mismatch = [], [], []
    for r in rows:
        old = r["url"]
        m = moved.get(old.rstrip("/").lower())
        url = old
        if m is not None:
            if m["commit"].lower() != r["commit"].lower():
                commit_mismatch.append(old)
            elif m["new_url"]:
                url = m["new_url"].rstrip("/")
                r["url"] = url
                r["full_name"] = p1mlcq.full_name_of(url)
                new_of[old] = url
                applied.append({"old_url": old, "new_url": url, "commit": r["commit"]})
            else:
                unmapped.append(old)
        frame_halves[url] = halves[old]
        original[url] = old
    if commit_mismatch:
        raise RuntimeError(f"mlcq-moved-repositories.csv names another commit for {commit_mismatch}")
    sample_out = os.path.join(out_dir, "mlcq-repos.mapped.csv")
    sfiles.write_csv(sample_out, rows)
    labels_out = os.path.join(out_dir, "mlcq-labels.mapped.csv")
    carried: dict = {}
    with open(labels_csv, newline="") as fh, open(labels_out, "w", newline="") as out:
        rd = csv.DictReader(fh)
        w = csv.DictWriter(out, fieldnames=rd.fieldnames, lineterminator="\n")
        w.writeheader()
        for lab in rd:
            if lab["repo"] in new_of:
                lab["repo"] = new_of[lab["repo"]]
                carried[lab["label"]] = carried.get(lab["label"], 0) + 1
            w.writerow(lab)
    frame = {"halves": frame_halves, "original_url": original,
             "moved": {"listed": len(moved), "mapped": len(applied), "unmapped": unmapped,
                       "labels_carried": dict(sorted(carried.items())), "repositories": applied},
             "sources": {os.path.basename(p): records.sha256(p)
                         for p in (repos_csv, labels_csv, moved_csv, HALVES)}}
    frame_path = os.path.join(out_dir, "mlcq-frame.json")
    with open(frame_path, "w") as fh:
        json.dump(frame, fh, indent=1)
    return {"sample": sample_out, "labels": labels_out, "frame": frame_path, **frame["moved"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds mlcq-prepare", description=__doc__.splitlines()[0])
    ap.add_argument("--labels-dir", default=pins.LABELS)
    args = ap.parse_args(argv)
    src = p1mlcq.fetch(args.labels_dir)
    sha = records.sha256(src)
    if sha != p1mlcq.MLCQ_SHA256:
        raise RuntimeError(f"{src} sha256 {sha} is not MLCQ 1.1's")
    agg = p1mlcq.aggregate(p1mlcq.read_reviews(src), "majority")
    summary = p1mlcq.write_outputs(agg, args.labels_dir, "majority", sha)
    print(f"MLCQ converted with paper one's converter (strict majority): {summary['labels']}")
    repos = os.path.join(args.labels_dir, "mlcq-repos.csv")
    halves = check_halves(repos)
    n_ex = sum(1 for h in halves.values() if h == "explore")
    print(f"split verified: paper one's frozen halves, {n_ex} explore / {len(halves) - n_ex} confirm")
    out = apply_moved(repos, os.path.join(args.labels_dir, "mlcq-labels.csv"), halves,
                      pins.MOVED_REPOSITORIES, args.labels_dir)
    print(f"moved repositories: {out['mapped']} of {out['listed']} listed mapped; labels carried "
          f"{out['labels_carried']}; unmapped {out['unmapped']}")
    print(f"wrote {out['sample']}, {out['labels']}, {out['frame']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
