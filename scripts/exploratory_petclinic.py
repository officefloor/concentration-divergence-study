#!/usr/bin/env python3
"""EXPLORATORY, DESCRIPTIVE. The sinew costs on AI-written code: Spring against OfficeFloor.

Written after step 14 was read; nothing here is confirmatory and no reviewer labels the code.
It reads the PetClinic-Evolve harness's branches (~/spring-petclinic-rest-long-degradation-test:
a fixed coding agent extends one application over 60 checkpoints, ten independent chains per
architecture) with the study's own instruments: the measurer (length, complexity, calls), the
live-width pass (scripts/livewidth.py, schema 3) and the split (scripts/split.py), on every
method of every snapshot. SPLIT.md sets the question out: at the same length, does AI-written
code carry wider seams, and does the architecture change that?

Per method: length (nloc), the live width [loop,role,all], the whole method's binding to its
class, and for a method at or over the cap its split (default and records variants, and the
framework variant, split.FRAMEWORK: the pieces as functions the framework calls in sequence,
a pass-through parameter injected for nothing and each value handed on a declared variable,
the reading an OfficeFloor function gets); for every
method with two or more statements the narrowest waist (split.waist): the cheapest seam of any
head or tail run of any sequence whose extraction leaves both sides at least a third of the
lines. Each method is new (its file and name are not in
the arm's base), modified (an old name in a file the chains changed) or untouched.

Per snapshot (a chain's tip, or every checkpoint with --trajectory): the counts and the
distributions, over all methods and over the AI-written ones (new and modified). Per arm: the
median over chains and the bootstrap interval of the mean (2000 resamples of chains, seed
12345), and the difference Spring minus OfficeFloor the same way, chains resampled
independently since the chains are not paired.

    .venv/bin/python scripts/exploratory_petclinic.py                      # the control run's tips
    .venv/bin/python scripts/exploratory_petclinic.py --strategy impact_gated --run blind-202609010045
    .venv/bin/python scripts/exploratory_petclinic.py --trajectory           # every checkpoint (~1,200 snapshots)
    .venv/bin/python scripts/exploratory_petclinic.py \\
        --arm angular-spring=~/officehq-angular-spring:base-empty \\
        --arm tanstack-officefloor=~/officehq-tanstack-officefloor:base-empty \\
        --branch '202610241-*/just-solve/*' --branch '2026101[789]*/just-solve/*' --at 40
                                                                            # OfficeHQ: two repositories, one per arm,
                                                                            # the chains of one checkpoint ladder, read at checkpoint 40

Writes results/exploratory/petclinic.<utc>.json (with its sha256) and
results/exploratory/petclinic-units.<utc>.csv.gz: one row per method per snapshot.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import asdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from concentration_divergence_study import javaparser, pins, units  # noqa: E402
import livewidth as lw  # noqa: E402
import split as sp  # noqa: E402
import exploratory_split as es  # noqa: E402

# an arm: name -> (repository, base ref, hotspot). The hotspot is ("method", "File.java", "name")
# for a named entry handler, ("dir", "/path/fragment/") for the longest method under a directory,
# or None for the longest AI-written method. The defaults are the PetClinic-Evolve arms; any
# other pair of repositories built by the same harness is given with --arm.
DEFAULT_ARMS = {"spring": (os.path.expanduser("~/compare/spring"), "spring-compare-no-tests",
                           ("method", "OwnerRestControllerV1.java", "addOwner")),
                "officefloor": (os.path.expanduser("~/compare/officefloor"), "officefloor-compare-no-tests",
                                ("dir", "/rest/function/"))}
ARMS: dict = dict(DEFAULT_ARMS)
FUNCTION_DIR = "/rest/function/"
WIDTH = ("loop", "role", "all", "use")
REPS, SEED = 2000, 12345
CAP = sp.DEFAULT.target


def git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout


def branches(repo: str, patterns: list[str], arm: str) -> list[str]:
    """The evolve branches matching any pattern (a glob on 'run/strategy/chainN', or on
    'run/strategy/arm/chainN' as the PetClinic harness names them, where the arm component must
    be this arm's), local heads and the remote-tracking ones, each once."""
    import fnmatch
    seen, out = set(), []
    for prefix in ("refs/heads/evolve/", "refs/remotes/origin/evolve/"):
        for ref in git(repo, "for-each-ref", "--format=%(refname)", prefix).split():
            short = ref[len(prefix):]
            parts = short.split("/")
            if short in seen or not any(fnmatch.fnmatch(short, p) for p in patterns):
                continue
            if len(parts) == 4 and parts[2] != arm:
                continue                    # the other arm's chain in a clone that holds both
            seen.add(short)
            out.append(ref)
    return sorted(out, key=lambda r: (r.rsplit("/", 1)[0], int(re.search(r"chain(\d+)$", r).group(1))))


def snapshots(repo: str, base: str, patterns: list[str], trajectory: bool, at: int | None, arm: str) -> list[dict]:
    """[{run, chain, checkpoint, commit}] for the base (chain None), then per matching branch its
    tip, or its agent commit at checkpoint `at` (skipped when the chain never reached it), or
    every agent commit in order with --trajectory."""
    out = [{"run": None, "chain": None, "checkpoint": 0, "commit": git(repo, "rev-parse", base).strip()}]
    for ref in branches(repo, patterns, arm):
        short = ref.split("/evolve/", 1)[1]
        chain = int(re.search(r"chain(\d+)$", short).group(1))
        run = short.rsplit("/chain", 1)[0]
        log = git(repo, "log", "--reverse", "--format=%H %s", f"{base}..{ref}")
        agent = []
        for line in log.splitlines():
            h, _, subject = line.partition(" ")
            m = re.match(r"cp(\d+) agent ", subject)
            if m:
                agent.append((int(m.group(1)), h))
        if trajectory:
            out += [{"run": run, "chain": chain, "checkpoint": cp, "commit": h} for cp, h in agent]
        elif at is not None:
            hit = [h for cp, h in agent if cp == at]
            if hit:
                out.append({"run": run, "chain": chain, "checkpoint": at, "commit": hit[-1]})
            else:
                print(f"  {short}: no checkpoint {at} (reached {max(cp for cp, _ in agent) if agent else 0}); skipped", file=sys.stderr)
        else:
            out.append({"run": run, "chain": chain, "checkpoint": max((cp for cp, _ in agent), default=0),
                        "commit": git(repo, "rev-parse", ref).strip()})
    return out


def checkout(repo: str, commit: str, dest: str) -> list[str]:
    tar = subprocess.run(["git", "-C", repo, "archive", commit, "src/main/java"], capture_output=True, check=True).stdout
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest)
    return sorted(os.path.relpath(os.path.join(d, f), dest) for d, _, fs in os.walk(dest) for f in fs if f.endswith(".java"))


def measure(repo: str, commit: str) -> tuple[dict, dict, list[str]]:
    work = tempfile.mkdtemp(prefix="cds-pc-")
    try:
        files = checkout(repo, commit, work)
        return javaparser.measure(work, files), lw.run_pass(work, files), files
    finally:
        shutil.rmtree(work, ignore_errors=True)


def method_rows(arm: str, snap: dict, doc: dict, facts: dict, base_names: set, touched: set) -> list[dict]:
    rec = {"javaparser": doc, "jp_oracles": None, "units": {"class": {"god_idx": {}, "units": []}}}
    ml = units.javaparser_set(rec)["method"]
    by = lw.by_unit(facts)
    jp = {}
    for path, ms in units._measurer_files(doc).items():
        for m, fidx in ms:
            jp.setdefault((path, m["name"], m["name_line"]), (m, fidx))
    rows = []
    for i, uid in enumerate(ml.ids):
        key = units._uid_parts(uid)
        path, name, line = key
        nloc = int(ml.values["nloc"][i])
        origin = "new" if (path, name) not in base_names else ("modified" if path in touched else "untouched")
        row = {"arm": arm, "run": snap["run"], "chain": snap["chain"], "checkpoint": snap["checkpoint"], "commit": snap["commit"][:12],
               "file": path, "name": name, "line": line, "origin": origin, "function": FUNCTION_DIR in path,
               "nloc": nloc, "cc": int(ml.values["cc"][i]), "facts": 0, "lw_max": None, "binding": "",
               "long": int(nloc >= sp.DEFAULT.trigger)}
        m = by.get(key)
        if m is not None:
            row["facts"] = 1
            rm, fidx = jp.get(key, (None, -1))
            own, _ = es.own_call_lines(m, rm, fidx)
            row["lw_max"] = float(lw.summary(m, WIDTH)["max"])
            row["binding"] = sp.binding(m, own)
            w = sp.waist(m, own)
            row.update({"waist_defined": int(w.defined), "waist_width": w.width if w.defined else None,
                        "waist_cost": w.cost if w.defined else None, "waist_side": w.side, "waist_binding": w.binding,
                        "waist_inputs": w.inputs if w.defined else None, "waist_outputs": w.outputs if w.defined else None,
                        "waist_depth": w.depth if w.defined else None})
            if nloc >= sp.DEFAULT.trigger:
                r = sp.split(m, own, sp.DEFAULT, nloc)
                v = sp.split(m, own, sp.RECORDS, nloc)
                fw = sp.split(m, own, sp.FRAMEWORK, nloc)
                row.update({"split_width_fw": fw.width, "split_cost_fw": fw.cost, "split_pieces_fw": fw.pieces,
                            "split_infeasible_fw": int(not fw.feasible), "split_locked_fw": fw.locked + int(fw.remainder_locked),
                            "split_units_fw": fw.pieces + 1})
                row.update({"split_width": r.width, "split_cost": r.cost, "split_pieces": r.pieces,
                            "split_infeasible": int(not r.feasible),
                            "split_locked": r.locked + int(r.remainder_locked), "split_units": r.pieces + 1,
                            "split_width_records": v.width, "split_cost_records": v.cost,
                            "split_infeasible_records": int(not v.feasible)})
        rows.append(row)
    return rows


def _q(xs: list, q: float) -> float | None:
    return float(np.percentile(xs, q)) if xs else None


def summarise(rows: list[dict]) -> dict:
    """The snapshot's numbers, over all methods and over the AI-written ones (suffix _ai)."""
    out: dict = {"methods": len(rows), "new": sum(r["origin"] == "new" for r in rows),
                 "modified": sum(r["origin"] == "modified" for r in rows)}
    for suffix, sel in (("", rows), ("_ai", [r for r in rows if r["origin"] != "untouched"])):
        nloc = [r["nloc"] for r in sel]
        longs = [r for r in sel if r["long"]]
        out[f"n{suffix}"] = len(sel)
        out[f"long{suffix}"] = len(longs)
        out[f"long_share{suffix}"] = len(longs) / len(sel) if sel else None
        out[f"nloc_max{suffix}"] = max(nloc) if nloc else None
        out[f"nloc_p90{suffix}"] = _q(nloc, 90)
        out[f"excess{suffix}"] = sum(max(0, n - CAP) for n in nloc)
        lwm = [r["lw_max"] for r in sel if r["lw_max"] is not None]
        out[f"lw_max_median{suffix}"] = _q(lwm, 50)
        out[f"lw_max_p90{suffix}"] = _q(lwm, 90)
        ws = [r["waist_width"] for r in sel if r.get("waist_defined")]
        out[f"waist_n{suffix}"] = len(ws)
        out[f"waist_median{suffix}"] = _q(ws, 50)
        out[f"waist_p90{suffix}"] = _q(ws, 90)
        out[f"waist_ge3_share{suffix}"] = (sum(w >= 3 for w in ws) / len(ws)) if ws else None
        wc = [r["waist_cost"] for r in sel if r.get("waist_defined")]
        out[f"waist_cost_mean{suffix}"] = float(np.mean(wc)) if wc else None
        bound = [r["binding"] for r in sel if r["binding"]]
        for b in ("free", "bound", "locked"):
            out[f"{b}_share{suffix}"] = (sum(x == b for x in bound) / len(bound)) if bound else None
        out[f"split_cost_sum{suffix}"] = sum(r.get("split_cost", 0) for r in longs if not r.get("split_infeasible"))
        out[f"split_width_max{suffix}"] = max([r.get("split_width", 0) for r in longs if not r.get("split_infeasible")] or [0])
        out[f"split_infeasible{suffix}"] = sum(r.get("split_infeasible", 0) for r in longs)
        out[f"split_infeasible_records{suffix}"] = sum(r.get("split_infeasible_records", 0) for r in longs)
        out[f"split_infeasible_fw{suffix}"] = sum(r.get("split_infeasible_fw", 0) for r in longs)
        out[f"split_cost_sum_fw{suffix}"] = sum(r.get("split_cost_fw", 0) for r in longs if not r.get("split_infeasible_fw"))
        out[f"split_width_max_fw{suffix}"] = max([r.get("split_width_fw", 0) for r in longs if not r.get("split_infeasible_fw")] or [0])
        lu = sum(r.get("split_units", 0) for r in longs if not r.get("split_infeasible"))
        out[f"split_locked_share{suffix}"] = (sum(r.get("split_locked", 0) for r in longs if not r.get("split_infeasible")) / lu) if lu else None
    return out


def hotspot(arm: str, rows: list[dict]) -> dict | None:
    spec = ARMS[arm][2]
    if spec and spec[0] == "method":
        hs = [r for r in rows if r["file"].endswith(spec[1]) and r["name"] == spec[2]]
    elif spec and spec[0] == "dir":
        hs = [r for r in rows if spec[1] in r["file"]]
    else:
        hs = [r for r in rows if r["origin"] != "untouched"]
    if not hs:
        return None
    r = max(hs, key=lambda r: r["nloc"])
    keep = ("file", "name", "nloc", "cc", "lw_max", "binding", "waist_width", "waist_cost", "split_width", "split_cost",
            "split_pieces", "split_infeasible", "split_locked", "split_units", "split_cost_records",
            "split_width_fw", "split_cost_fw", "split_pieces_fw", "split_infeasible_fw")
    return {k: r.get(k) for k in keep}


def boot_mean(xs: list, rng: np.random.Generator) -> dict:
    a = np.array([x for x in xs if x is not None], float)
    if len(a) == 0:
        return {"n": 0}
    idx = rng.integers(0, len(a), size=(REPS, len(a)))
    means = a[idx].mean(axis=1)
    return {"n": int(len(a)), "median": float(np.median(a)), "mean": float(a.mean()),
            "lo": float(np.percentile(means, 2.5)), "hi": float(np.percentile(means, 97.5))}


def boot_diff(xs: list, ys: list, rng: np.random.Generator) -> dict:
    a = np.array([x for x in xs if x is not None], float)
    b = np.array([y for y in ys if y is not None], float)
    if len(a) == 0 or len(b) == 0:
        return {}
    d = a[rng.integers(0, len(a), size=(REPS, len(a)))].mean(axis=1) - b[rng.integers(0, len(b), size=(REPS, len(b)))].mean(axis=1)
    return {"value": float(a.mean() - b.mean()), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5))}


KEYS = ["methods", "n_ai", "long", "long_ai", "nloc_max", "nloc_max_ai", "excess", "excess_ai",
        "lw_max_median_ai", "lw_max_p90_ai", "waist_median_ai", "waist_p90_ai", "waist_ge3_share_ai", "waist_cost_mean_ai",
        "free_share_ai", "bound_share_ai", "locked_share_ai",
        "split_cost_sum", "split_width_max", "split_infeasible", "split_infeasible_records", "split_locked_share",
        "split_infeasible_fw", "split_cost_sum_fw", "split_width_max_fw",
        "waist_median", "waist_p90", "lw_max_p90", "locked_share"]


def f(x, nd=2) -> str:
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", action="append", default=None, metavar="NAME=REPO:BASE[:method=File.java::name | :dir=/fragment/]",
                    help="an arm (repeatable; default: the two PetClinic-Evolve arms). The first named is reported first and the difference is first minus second.")
    ap.add_argument("--branch", action="append", default=None, metavar="GLOB",
                    help="evolve branches to read, a glob on run/strategy/chainN or run/strategy/arm/chainN (repeatable; default: the PetClinic control run)")
    ap.add_argument("--run", default="blind-202608100006")
    ap.add_argument("--strategy", default="just-solve")
    ap.add_argument("--at", type=int, default=None, help="read every chain at this checkpoint instead of its tip")
    ap.add_argument("--trajectory", action="store_true", help="every checkpoint's agent commit, not only the tips")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.arm:
        ARMS.clear()
        for spec in a.arm:
            name, rest = spec.split("=", 1)
            repo, base, *hot = rest.split(":", 2)
            h = None
            if hot:
                kind, val = hot[0].split("=", 1)
                h = ("method", *val.split("::", 1)) if kind == "method" else ("dir", val)
            ARMS[name] = (os.path.expanduser(repo), base, h)
    arms = list(ARMS)
    assert len(arms) == 2, "two arms"
    patterns = a.branch or [f"{a.run}/{a.strategy}/*"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {"kind": "exploratory", "made_utc": stamp, "harness_commit": pins.harness_commit(),
           "note": __doc__.splitlines()[0], "branches": patterns, "at": a.at, "trajectory": a.trajectory,
           "params": {"default": asdict(sp.DEFAULT), "records": asdict(sp.RECORDS), "framework": asdict(sp.FRAMEWORK)}, "width_variant": lw.label(WIDTH),
           "arms": {}, "snapshots": [], "hotspots": [], "by_arm": {}, "difference": {}}
    all_rows: list[dict] = []
    summaries: dict = {arm: [] for arm in ARMS}
    for arm, (repo, base, _) in ARMS.items():
        snaps = snapshots(repo, base, patterns, a.trajectory, a.at, arm)
        out["arms"][arm] = {"repo": repo, "base": base, "snapshots": len(snaps), "chains": len({(s["run"], s["chain"]) for s in snaps if s["chain"] is not None})}
        base_names: set = set()
        for k, snap in enumerate(snaps):
            doc, facts, files = measure(repo, snap["commit"])
            if snap["chain"] is None:
                base_names = {(p, m["name"]) for p, ms in units._measurer_files(doc).items() for m, _ in ms}
                touched: set = set()
            else:
                touched = set(git(repo, "diff", "--name-only", base, snap["commit"], "--", "src/main/java").split())
            rows = method_rows(arm, snap, doc, facts, base_names, touched)
            all_rows += rows
            s = summarise(rows)
            s.update({"arm": arm, "run": snap["run"], "chain": snap["chain"], "checkpoint": snap["checkpoint"], "commit": snap["commit"][:12], "files": len(files)})
            out["snapshots"].append(s)
            h = hotspot(arm, rows)
            if h:
                out["hotspots"].append({"arm": arm, "run": snap["run"], "chain": snap["chain"], "checkpoint": snap["checkpoint"], **h})
            if snap["chain"] is not None and (not a.trajectory or snap["checkpoint"] == max(x["checkpoint"] for x in snaps if (x["run"], x["chain"]) == (snap["run"], snap["chain"]))):
                summaries[arm].append(s)
            print(f"  {arm}: {k + 1}/{len(snaps)} snapshots ({snap['run']} chain {snap['chain']}, cp {snap['checkpoint']}: "
                  f"{s['methods']} methods, {s['long']} long, nloc max {s['nloc_max']})", file=sys.stderr)
    rng = np.random.default_rng(SEED)
    A, B = arms
    for key in KEYS:
        out["by_arm"][key] = {arm: boot_mean([s.get(key) for s in summaries[arm]], rng) for arm in ARMS}
        out["difference"][key] = boot_diff([s.get(key) for s in summaries[A]], [s.get(key) for s in summaries[B]], rng)
    # the report
    where = f"checkpoint {a.at}" if a.at is not None else "chain tips"
    print(f"\n=== {', '.join(patterns)}: {len(summaries[A])} {A} chains, {len(summaries[B])} {B} chains, {where} ===")
    print(f"  {'per chain':30s} {A:>22s}   {B:>22s}   {A + ' - ' + B:>28s}")
    for key in KEYS:
        s, o, d = out["by_arm"][key][A], out["by_arm"][key][B], out["difference"][key]
        if s.get("n") and o.get("n"):
            print(f"  {key:30s} {f(s['median']):>7s} [{f(s['lo'])}, {f(s['hi'])}]   {f(o['median']):>7s} [{f(o['lo'])}, {f(o['hi'])}]   "
                  f"{d['value']:+.2f} [{d['lo']:+.2f}, {d['hi']:+.2f}]")
    base = {s["arm"]: s for s in out["snapshots"] if s["chain"] is None}
    print("\n  the base (before any checkpoint):")
    for arm in ARMS:
        b = base[arm]
        print(f"    {arm:12s} methods {b['methods']}, long {b['long']}, nloc max {b['nloc_max']}, waist median {f(b['waist_median'])} p90 {f(b['waist_p90'])}, "
              f"lw max p90 {f(b['lw_max_p90'])}, locked share {f(b['locked_share'])}")
    print("\n  the hotspot per chain (a named entry handler, the longest method under a directory, or the longest AI-written method):")
    tips = {}
    for h in out["hotspots"]:
        if h["chain"] is not None:
            tips[(h["arm"], h["run"], h["chain"])] = h       # the last one per chain wins: the tip
    for (arm, run, chain), h in sorted(tips.items(), key=lambda kv: (arms.index(kv[0][0]), kv[0][1], kv[0][2])):
        print(f"    {arm:12s} {run} chain {chain}: {h['name']:28s} nloc {h['nloc']:3d} cc {h['cc']:2d} lw {f(h['lw_max'],0):>3s} {h['binding']:7s} "
              f"waist {f(h['waist_width'],0):>3s} split width {f(h.get('split_width'),0):>3s} cost {f(h.get('split_cost'),0):>3s} "
              f"pieces {f(h.get('split_pieces'))} infeasible {f(h.get('split_infeasible'))} locked {f(h.get('split_locked'))}/{f(h.get('split_units'))}"
              f" | framework: width {f(h.get('split_width_fw'),0):>3s} cost {f(h.get('split_cost_fw'),0):>3s} pieces {f(h.get('split_pieces_fw'))} infeasible {f(h.get('split_infeasible_fw'))}")
    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = a.out or os.path.join(pins.RESULTS, "exploratory", f"petclinic.{stamp}.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    upath = os.path.join(os.path.dirname(path), f"petclinic-units.{stamp}.csv.gz")
    header = sorted({k for r in all_rows for k in r}, key=lambda k: (k not in ("arm", "run", "chain", "checkpoint", "commit", "file", "name", "line", "origin"), k))
    with gzip.open(upath, "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(all_rows)
    for p in (path, upath):
        digest = hashlib.sha256(open(p, "rb").read()).hexdigest()
        with open(p + ".sha256", "w") as fh:
            fh.write(f"{digest}  {os.path.basename(p)}\n")
    print(f"\nwrote {path} and {upath}  (exploratory, descriptive; not part of the plan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
