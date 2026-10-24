"""Measure every usable repository of a sample (open-source-repository-sampler's run loop: each
one shallow-cloned at its pinned commit, measured, the clone deleted) into results/<set>/. Only
the files a measurement reads are downloaded (files.CLONE_ONLY).

Resumable: a re-run with the same --out-dir skips what the run log records as done and retries
what failed. It refuses to resume into a directory measured from a different sample, or whose
study.json is missing while its log says work was done; a resume by another harness commit is
recorded as a new session in run.json (every row names its own commit).
"""
from __future__ import annotations

import datetime
import json
import os
import platform

from complexity_concentration_study import study as p1

from . import __version__, files, javaparser, measure, pins, records


class PreflightFailed(RuntimeError):
    pass


def tool_versions(pmd: str | None, ck: str | None) -> dict:
    """Every tool that shapes a number, recorded in every row."""
    v = p1.tool_versions(pmd, ck)          # python, lizard, PMD, CK sha256 (paper one's pins)
    v.pop("harness_commit", None)          # paper one's own git commit is not visible when installed
    v.pop("complexity_concentration_study", None)
    info = pins.paper_one_installed()
    v.update({"paper_one_version": info.get("version"), "paper_one_commit": info.get("commit"),
              "javaparser": javaparser.version(), "harness_commit": pins.harness_commit(),
              "concentration_divergence_study": __version__, "platform": platform.platform()})
    return v


def preflight(pmd: str | None, ck: str | None, allow_dirty: bool = False) -> None:
    """Fail before any repository is cloned if anything that shapes a number is missing, broken
    or off its pin: paper one's package at its commit, Java, the measurer on its fixture, and a
    committed harness (a confirmatory measurement is never made from uncommitted code; PLAN.md,
    Procedure 3). Then paper one's own preflight: lizard not blind, every signal alive, PMD and
    CK at their pins and producing panels."""
    problems = pins.paper_one_problems() + javaparser.java_problems()
    if not problems:
        problems += javaparser.check()
    commit = pins.harness_commit()
    if commit is None or commit.endswith("-dirty"):
        msg = (f"the harness commit is {commit!r}: commit every change first, so each row names "
               f"the code that measured it")
        if allow_dirty:
            print(f"WARNING (--allow-dirty): {msg}. These rows are NOT confirmatory.", flush=True)
        else:
            problems.append(msg + " (or pass --allow-dirty for a non-confirmatory run)")
    if not pmd or not ck:
        problems.append("PMD and CK are required (the tool oracles and paper one's panels): run "
                        "./step1_setup.sh, which downloads both into ./lib")
    if problems:
        raise PreflightFailed("PREFLIGHT FAILED:\n  - " + "\n  - ".join(problems))
    p1.preflight(pmd, ck)
    print("preflight OK: paper one's package at its pinned commit, the measurer at JavaParser "
          f"{pins.JAVAPARSER_VERSION} measures its fixture exactly, harness {commit}.", flush=True)


def _meta(repo, set_name: str, sample_name: str, frame: dict) -> dict:
    row = repo.row
    return {"set": set_name, "key": records.key_of(repo.full_name, repo.commit),
            "repo": repo.url, "name": repo.full_name.split("/")[-1], "full_name": repo.full_name,
            "lang": repo.language, "commit": repo.commit,
            "date": (row.get("commit_date") or "")[:10], "stratum_lang": row.get("stratum_language"),
            "tier": row.get("tier"), "stars": row.get("stars"), "rank": row.get("rank"),
            "star_band": row.get("star_band"), "draw": row.get("draw"), "sample": sample_name,
            "half": (frame.get("halves") or {}).get(repo.url),
            "original_url": (frame.get("original_url") or {}).get(repo.url, repo.url)}


def _light(row: dict) -> dict:
    """The row as study.json keeps it (the record keeps everything)."""
    return {k: v for k, v in row.items() if k not in ("tools",)} | {
        "harness_commit": (row.get("tools") or {}).get("harness_commit")}


def run(sample_csv: str, out_dir: str, set_name: str, pmd: str | None, ck: str | None,
        labels_path: str | None = None, frame_path: str | None = None,
        allow_dirty: bool = False) -> list[dict]:
    from open_source_repository_sampler import for_each, read_sample

    os.makedirs(out_dir, exist_ok=True)
    rows_path = os.path.join(out_dir, "study.json")
    log_path = os.path.join(out_dir, "run-log.jsonl")
    run_path = os.path.join(out_dir, "run.json")
    rows: dict = {}
    if os.path.exists(rows_path):
        rows = {r["key"]: r for r in records.load_rows(out_dir)}
    elif os.path.exists(log_path):
        raise RuntimeError(f"{out_dir} has a run log but no study.json: a resume would skip "
                           f"repositories without their rows. Use a fresh --out-dir.")
    preflight(pmd, ck, allow_dirty)
    tools = tool_versions(pmd, ck)
    frame = json.load(open(frame_path)) if frame_path else {}
    spec = {"set": set_name, "sample": os.path.relpath(sample_csv, pins.PROJECT_ROOT),
            "sample_sha256": records.sha256(sample_csv),
            "labels": os.path.relpath(labels_path, pins.PROJECT_ROOT) if labels_path else None,
            "labels_sha256": records.sha256(labels_path) if labels_path else None,
            "frame": os.path.relpath(frame_path, pins.PROJECT_ROOT) if frame_path else None,
            "frame_sha256": records.sha256(frame_path) if frame_path else None}
    session = {"started_utc": _now(), "harness_commit": tools["harness_commit"], "tools": tools}
    if os.path.exists(run_path):
        old = json.load(open(run_path))
        diff = [k for k in spec if old.get(k) != spec[k]]
        if diff:
            raise RuntimeError(f"{run_path} records a run with a different {diff}: one set is "
                               f"measured from one sample. Delete {out_dir} and measure afresh "
                               f"(and record why).")
        if old["sessions"][-1]["harness_commit"] != session["harness_commit"]:
            print(f"NOTE: resuming with harness {session['harness_commit']}, the last session ran "
                  f"{old['sessions'][-1]['harness_commit']}. Each row records its own commit; a "
                  f"repository measured by code since fixed is re-measured with `cds forget`.",
                  flush=True)
        old["sessions"].append(session)
        records.atomic_json(run_path, old)
    else:
        records.atomic_json(run_path, {**spec, "sessions": [session], "forgotten": []})
    labels = p1.load_labels(labels_path)
    n = len(read_sample(sample_csv))
    print(f"concentration-divergence-study: {n} usable repositories in {sample_csv} -> {out_dir}"
          + (f", labels {labels_path}" if labels_path else ""), flush=True)

    def experiment(repo):
        meta = _meta(repo, set_name, os.path.basename(sample_csv), frame)
        human, other = p1.labels_for(labels, repo.url, repo.full_name, repo.commit)
        rec = measure.measure_checkout(repo.path, meta, human, pmd, ck, tools)
        if other:
            rec["row"]["labels_commit_mismatch"] = other
        records.write_json_gz(records.record_path(out_dir, meta["key"]), rec)
        rows[meta["key"]] = _light(rec["row"])
        records.atomic_json(rows_path, list(rows.values()))
        r = rec["row"]
        js = r.get("javaparser_summary") or {}
        print(f"        {r.get('n_funcs', '?'):>6} fns | class universe "
              f"{(r.get('matrix') or {}).get('class', {}).get('n_univ')} | pruned "
              f"{r['pruned']['removed']} | measurer {js.get('methods')} methods, calls "
              f"{js.get('calls')}" + (f" | ERROR {r['error']}" if r.get("error") else "")
              + (f" | MEASURER ERROR {r['javaparser_error'][:200]}" if r.get("javaparser_error") else ""),
              flush=True)
        if r.get("javaparser_error") or (r.get("lang") == "java" and not r.get("error")
                                         and "pmd_gods" not in r):
            raise RuntimeError("the measurer or PMD produced no result; the record is kept, the "
                               "repository is logged failed and retried on the next run")

    # Clones go on disk beside the results, not in the system temp directory, which may be a
    # small RAM-backed tmpfs (paper one lost openjdk/jdk to "unable to write file" there).
    work = os.path.join(out_dir, ".work")
    os.makedirs(work, exist_ok=True)
    use_disk_temp(out_dir)
    for_each(sample_csv, experiment, deep=False, run_log=log_path, work_dir=work,
             only=files.CLONE_ONLY)
    out = list(rows.values())
    print(f"\n{len(out)} repositories recorded in {rows_path}", flush=True)
    return out


def use_disk_temp(out_dir: str) -> None:
    """Every temporary file of this process (paper one's PMD and CK runs, the measurer's list)
    under <out_dir>/.tmp, on disk, rather than in a possibly small RAM-backed /tmp."""
    import tempfile
    tmp = os.path.join(out_dir, ".tmp")
    os.makedirs(tmp, exist_ok=True)
    tempfile.tempdir = tmp


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def forget(out_dir: str, keys: list[str], reason: str) -> None:
    """Mark repositories for re-measurement after a measurement fault was fixed: each record is
    moved to repos/superseded/ (kept, never deleted), its row dropped from study.json, its lines
    dropped from the run log (so the run loop measures it again), and the action, with the
    reason and the harness commit, appended to run.json. Re-run the step afterwards."""
    if not reason.strip():
        raise ValueError("a reason is required: it is recorded in run.json")
    run_path = os.path.join(out_dir, "run.json")
    spec = json.load(open(run_path))
    rows = {r["key"]: r for r in records.load_rows(out_dir)}
    log_path = os.path.join(out_dir, "run-log.jsonl")
    log = [json.loads(line) for line in open(log_path) if line.strip()] if os.path.exists(log_path) else []
    stamp = _now().replace(":", "").replace("-", "")
    for key in keys:
        src = records.record_path(out_dir, key)
        if key not in rows and not os.path.exists(src):
            raise KeyError(f"no repository {key} in {out_dir}")
        row = rows.pop(key, None)
        if os.path.exists(src):
            dst = os.path.join(out_dir, "repos", "superseded", f"{key}.{stamp}.json.gz")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(src, dst)
        if row:
            log = [r for r in log if (r.get("full_name"), r.get("commit")) != (row["full_name"], row["commit"])]
    records.atomic_json(os.path.join(out_dir, "study.json"), list(rows.values()))
    tmp = log_path + ".tmp"
    with open(tmp, "w") as fh:
        for r in log:
            fh.write(json.dumps(r) + "\n")
    os.replace(tmp, log_path)
    spec.setdefault("forgotten", []).append({"keys": keys, "reason": reason, "utc": _now(),
                                             "harness_commit": pins.harness_commit()})
    records.atomic_json(run_path, spec)
    print(f"forgot {len(keys)} repositories in {out_dir}; re-run the step to measure them again")
