"""Measure one checkout: paper one's complexity and oracles, unchanged, and the coupling measurer,
on the same file set. Writes one record per repository; nothing here derives a score.

The record (records.write) holds everything the analysis needs, raw, so a fault in the analysis
is fixed and re-run without measuring again (README, Run and analyse are separate):

  row          paper one's row for the checkout (study.analyse, the matrix reduced to its
               universe sizes), plus this study's fields: the sample metadata, the half, the
               tools, the files the extra rule deleted (`pruned`), the DI frameworks the build
               files name (`di`), labels on deleted files (`labels_out_of_scope`)
  units        paper one's per-unit payload (study._unit_payload): per level the units, every
               signal's value per unit, the positions of every definition's positives, and PMD's
               own method values
  pmd          PMD's raw findings as paper one's run produced them (captured from its own call,
               not a second PMD run): method findings (path, line, rule) and class findings
  javaparser   the measurer's document (javaparser.py)
  jp_oracles   method-level definitions mapped onto the measurer's units: PMD's NPath findings
               and the human method labels, each to the innermost method containing its line
               (a label on an annotation, comment or blank lead-in line steps forward to the
               method that starts after it, as paper one's _labelled_unit_at does)
  human_items  the expert labels applied to this checkout, as given
"""
from __future__ import annotations

import contextlib
import os
import re
from collections import defaultdict

from complexity_concentration_study import extract as p1_extract
from complexity_concentration_study import study as p1

from . import files, javaparser


@contextlib.contextmanager
def capture_pmd(into: dict):
    """Record the report paper one's own PMD call returns, by wrapping study._pmd_report for the
    duration (study.analyse looks it up at call time). PMD runs once, exactly as paper one runs it."""
    orig = p1._pmd_report

    def wrapped(*a, **k):
        rep = orig(*a, **k)
        into["report"] = rep
        return rep
    p1._pmd_report = wrapped
    try:
        yield into
    finally:
        p1._pmd_report = orig


def jp_unit_ids(doc: dict) -> list[tuple[str, dict, str]]:
    """(unit id, method record, file) for every measurer method, ids as `file::name@name_line`
    (a second unit on the same line gets a prime, as paper one's ids do)."""
    out = []
    seen = set()
    for f in doc.get("files", []):
        for m in f["methods"]:
            uid = f"{f['path']}::{m['name']}@{m['name_line']}"
            while uid in seen:
                uid += "'"
            seen.add(uid)
            out.append((uid, m, f["path"]))
    return out


_LEAD_IN = re.compile(r"^\s*(?:@|//|/\*|\*|$)")


def _jp_by_file(doc: dict) -> dict:
    by: dict = defaultdict(list)
    for uid, m, path in jp_unit_ids(doc):
        by[path].append((m["decl_line"], m["end_line"], uid))
    return by


def _innermost(by_file: dict, rel: str, line: int):
    best = None
    for st, en, uid in by_file.get(rel, ()):
        if st <= line <= en and (best is None or (en - st) < (best[1] - best[0])):
            best = (st, en, uid)
    return best[2] if best else None


def jp_labelled_unit(by_file: dict, root: str, rel: str, line: int):
    """The measurer unit a method label names: the innermost method containing the line (the
    measurer's range starts at the first annotation), else the method that starts on the first
    line after the label's annotation, comment and blank lead-in lines (paper one's rule)."""
    uid = _innermost(by_file, rel, line)
    if uid is not None:
        return uid
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            src = fh.read().splitlines()
    except OSError:
        return None
    if not (0 < line <= len(src)) or not src[line - 1].strip():
        return None
    depth = 0
    for n in range(line, len(src) + 1):
        text = src[n - 1]
        if depth > 0 or text.lstrip().startswith("@"):
            depth = max(0, depth + text.count("(") + text.count("{")
                        - text.count(")") - text.count("}"))
            continue
        if _LEAD_IN.match(text):
            continue
        for st, _, uid in by_file.get(rel, ()):
            if st == n:
                return uid
        return None
    return None


def jp_oracles(doc: dict, root: str, pmd_methods: list, human: dict) -> dict:
    """Method-level definitions on the measurer's units: {name: sorted unit ids}."""
    by_file = _jp_by_file(doc)
    out: dict = {}
    npath = set()
    for rel, line, rule in pmd_methods:
        if rule == "NPathComplexity":
            uid = _innermost(by_file, rel, line)
            if uid is not None:
                npath.add(uid)
    if pmd_methods is not None:
        out["pmd_method_NPath200"] = sorted(npath)
    for label, items in sorted((human or {}).items()):
        lines = [i for i in items if isinstance(i, tuple)]
        if not lines:
            continue
        hit = set()
        for rel, ln in lines:
            uid = jp_labelled_unit(by_file, root, rel, ln)
            if uid is not None:
                hit.add(uid)
        out[f"human_method_{label}"] = sorted(hit)
    return out


def _json_items(items) -> list:
    return sorted([list(i) if isinstance(i, tuple) else i for i in items], key=str)


def measure_checkout(root: str, meta: dict, human: dict | None, pmd: str | None, ck: str | None,
                     tools: dict) -> dict:
    """The record of one checkout at `root` (a temporary copy: the extra rule deletes files)."""
    di = files.di_frameworks(root)
    pruned = files.prune(root)
    captured: dict = {}
    try:
        with capture_pmd(captured):
            a = p1.analyse(root, pmd, ck, human or None)
    except Exception as e:                                   # paper one's own failure mode
        a = {"error": f"{type(e).__name__}: {e}"}
    units = a.pop("_units", None)
    matrix = a.pop("matrix", None)
    row = {**meta, "tools": tools, **a, "di": di,
           "pruned": {"removed": pruned["removed"], "by_segment": pruned["by_segment"]}}
    if matrix:
        row["matrix"] = {lvl: {"n_univ": matrix[lvl]["n_univ"],
                               "oracle_gods": matrix[lvl].get("oracle_gods"),
                               "god_outside_univ": matrix[lvl].get("god_outside_univ")}
                         for lvl in ("class", "method")}
    gone = set(pruned["paths"])
    if human:
        row["labels_out_of_scope"] = {
            label: sum(1 for i in items if (i if isinstance(i, str) else i[0]) in gone)
            for label, items in sorted(human.items())}
    rep = captured.get("report")
    pmd_raw = None
    if rep is not None:
        pmd_raw = {"method": sorted([r, ln, rule] for r, ln, rule, _ in rep["method"]),
                   "class": {rule: sorted(paths) for rule, paths in rep["class"].items()}}
    record = {"row": row, "units": units, "pmd": pmd_raw, "pruned_paths": pruned["paths"],
              "human_items": {k: _json_items(v) for k, v in sorted((human or {}).items())},
              "javaparser": None, "jp_oracles": None}
    if row.get("error"):
        return record
    java = sorted(f for f in p1_extract.scan_files(root)["source"] if f.endswith(".java"))
    try:
        doc = javaparser.measure(root, java)
    except javaparser.MeasurerFailed as e:
        row["javaparser_error"] = str(e)
        return record
    record["javaparser"] = doc
    record["jp_oracles"] = jp_oracles(doc, root, [tuple(x) for x in (pmd_raw or {}).get("method", [])],
                                      human)
    if pmd_raw is None:
        record["jp_oracles"].pop("pmd_method_NPath200", None)
    row["javaparser_summary"] = summarise(doc)
    return record


def summarise(doc: dict) -> dict:
    """Counts for the run's progress line and the diagnostics: files, failures, methods, and
    calls by resolution."""
    res = [0] * len(javaparser.RESOLUTIONS)
    n_methods = 0
    for f in doc["files"]:
        for m in f["methods"]:
            n_methods += 1
            for c in m["calls"]:
                res[c[2]] += 1
    return {"files": len(doc["files"]),
            "files_failed": sum(1 for f in doc["files"] if f["level"] == "failed"),
            "files_java8": sum(1 for f in doc["files"] if f["level"] == "JAVA_8"),
            "methods": n_methods, "calls": dict(zip(javaparser.RESOLUTIONS, res)),
            "seconds": doc.get("seconds"), "budget_exhausted": doc.get("budget_exhausted")}
