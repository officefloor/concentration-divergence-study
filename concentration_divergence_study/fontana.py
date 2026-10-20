"""Fontana's God Class (Arcelli Fontana et al., Empirical Software Engineering 21(3), 2016): the
human replication oracle on the Qualitas Corpus (PLAN.md, Oracles 4).

The files cannot be fetched by a script: the MLCSD page (essere.disco.unimib.it) links its
datasets through pages and drives, and the Qualitas Corpus is distributed by its maintainers.
So the material is placed by hand, its access terms written down, and everything after that is
code:

    inputs/fontana/ACCESS.md        where each file came from, when, and its access terms (the
                                    plan requires them checked and recorded before measurement;
                                    prepare refuses without this file)
    inputs/fontana/god-class.arff   Fontana's God Class data set (its instances name a system,
                                    a package and a class, and the label)
    inputs/fontana/corpus/          the Qualitas Corpus source archives of the systems it names

    cds fontana-prepare [--arff ...] [--corpus ...]
        labels/fontana-labels.csv   system, class (qualified), label: `fontana_god_class` for a
                                    positive, `fontana_god_class_reviewed` for every instance
        labels/fontana-systems.csv  system, archive (relative to the project), its sha256
    cds study --set fontana         measure each system's archive (unpacked to a temporary
                                    directory) in place of a pinned commit, its sha256 recorded
                                    as the commit (`archive:<sha256>`)

A label names a class; the unit is the file that declares its top-level type (package path and
type name, from the source), so a nested class's label lands on its outer file. Labels that
land on no measured file are counted. Every rule is fitted on the whole system and scored on the
labelled classes only (the `_reviewed` universe), class level only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile

from . import measure, pins, records, run as run_mod

DIR = os.path.join(pins.INPUTS, "fontana")
ARFF = os.path.join(DIR, "god-class.arff")
CORPUS = os.path.join(DIR, "corpus")
ACCESS = os.path.join(DIR, "ACCESS.md")
LABELS_CSV = os.path.join(pins.LABELS, "fontana-labels.csv")
SYSTEMS_CSV = os.path.join(pins.LABELS, "fontana-systems.csv")
LABEL = "fontana_god_class"
ARCHIVE_EXT = (".zip", ".tar.gz", ".tgz", ".tar", ".tar.bz2")


def read_arff(path: str) -> tuple[list[str], list[list[str]]]:
    attrs, data, in_data = [], [], False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("%"):
                continue
            if not in_data:
                low = s.lower()
                if low.startswith("@attribute"):
                    m = re.match(r"@attribute\s+('[^']*'|\"[^\"]*\"|\S+)", s, re.I)
                    attrs.append(m.group(1).strip("'\""))
                elif low.startswith("@data"):
                    in_data = True
                continue
            data.extend(csv.reader([s], quotechar="'", skipinitialspace=True))
    return attrs, data


def instances(path: str, system_col: str, package_col: str, class_col: str, label_col: str) -> list[dict]:
    attrs, data = read_arff(path)
    low = [a.lower() for a in attrs]
    idx = {}
    for name, col in (("system", system_col), ("package", package_col), ("class", class_col),
                      ("label", label_col)):
        if col.lower() not in low:
            raise RuntimeError(f"{path} has no attribute {col!r} (attributes: {attrs[:12]}...); "
                               f"pass --{name}-attribute")
        idx[name] = low.index(col.lower())
    out = []
    for row in data:
        pkg = row[idx["package"]].strip()
        cls = row[idx["class"]].strip()
        qn = cls if (pkg and cls.startswith(pkg + ".")) or not pkg else f"{pkg}.{cls}"
        out.append({"system": row[idx["system"]].strip(), "class": qn,
                    "positive": row[idx["label"]].strip().lower() in ("true", "1", "yes", "t")})
    return out


def find_archive(corpus: str, system: str) -> str | None:
    """The source archive (or source directory) of one system in the corpus: a file whose name
    starts with the system's name and names its sources (`...src...`), else a directory named
    after the system. The shortest such path wins, so a system's own archive beats a nested one."""
    hits = []
    for dirpath, dirnames, filenames in os.walk(corpus):
        for fn in filenames:
            if fn.startswith(system) and "src" in fn.lower() and fn.lower().endswith(ARCHIVE_EXT):
                hits.append(os.path.join(dirpath, fn))
        for d in dirnames:
            if d == system:
                hits.append(os.path.join(dirpath, d))
    return min(hits, key=lambda p: (os.path.isdir(p), len(p))) if hits else None


def tree_sha256(path: str) -> str:
    if os.path.isfile(path):
        return records.sha256(path)
    import hashlib
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            h.update(os.path.relpath(p, path).encode() + b"\0" + records.sha256(p).encode())
    return h.hexdigest()


def prepare(arff: str, corpus: str, cols: dict) -> dict:
    if not os.path.isfile(ACCESS):
        raise RuntimeError(f"no {ACCESS}: record where the God Class data set and the Qualitas "
                           f"Corpus came from, when, and their access terms before measuring "
                           f"(PLAN.md, Oracles 4)")
    inst = instances(arff, **cols)
    systems = sorted({i["system"] for i in inst})
    os.makedirs(pins.LABELS, exist_ok=True)
    with open(LABELS_CSV, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["system", "class", "label"])
        for i in sorted(inst, key=lambda i: (i["system"], i["class"])):
            w.writerow([i["system"], i["class"], LABEL + "_reviewed"])
            if i["positive"]:
                w.writerow([i["system"], i["class"], LABEL])
    missing = []
    with open(SYSTEMS_CSV, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["system", "archive", "sha256"])
        for s in systems:
            a = find_archive(corpus, s)
            if a is None:
                missing.append(s)
                continue
            w.writerow([s, os.path.relpath(a, pins.PROJECT_ROOT), tree_sha256(a)])
    return {"instances": len(inst), "positives": sum(i["positive"] for i in inst),
            "systems": len(systems), "systems_without_archive": missing,
            "arff_sha256": records.sha256(arff)}


def unpack(src: str, dest: str) -> None:
    if os.path.isdir(src):
        shutil.copytree(src, dest, symlinks=False, dirs_exist_ok=True)
    elif src.lower().endswith(".zip"):
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
    else:
        with tarfile.open(src) as t:
            t.extractall(dest, filter="data")


_PKG = re.compile(r"(?m)^\s*package\s+([\w.]+)\s*;")
_TYPE = re.compile(r"(?m)^(?:[\w@\s]*\s)?(?:class|interface|enum|record)\s+(\w+)")


def class_files(root: str) -> dict:
    """{qualified top-level type name: repo-relative file} over the tree's .java files."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            if not fn.endswith(".java"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                text = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            m = _PKG.search(text)
            pkg = m.group(1) if m else ""
            for t in [fn[:-5]] + _TYPE.findall(text):
                out.setdefault(f"{pkg}.{t}" if pkg else t, rel)
    return out


def labels_for_system(root: str, rows: list[dict]) -> tuple[dict, dict]:
    files = class_files(root)
    human: dict = {}
    unmatched: dict = {}
    for r in rows:
        qn = r["class"].replace("$", ".")
        parts = qn.split(".")
        path = None
        for k in range(len(parts), 0, -1):            # Outer.Inner -> the file of Outer
            path = files.get(".".join(parts[:k]))
            if path:
                break
        if path is None:
            unmatched[r["label"]] = unmatched.get(r["label"], 0) + 1
            continue
        human.setdefault(r["label"], set()).add(path)
    return human, unmatched


def run(out_dir: str, pmd: str, ck: str, allow_dirty: bool = False) -> None:
    os.makedirs(out_dir, exist_ok=True)
    run_mod.use_disk_temp(out_dir)
    run_mod.preflight(pmd, ck, allow_dirty)
    tools = run_mod.tool_versions(pmd, ck)
    with open(LABELS_CSV, newline="") as fh:
        labels = list(csv.DictReader(fh))
    with open(SYSTEMS_CSV, newline="") as fh:
        systems = list(csv.DictReader(fh))
    rows_path = os.path.join(out_dir, "study.json")
    rows = {r["key"]: r for r in records.load_rows(out_dir)} if os.path.exists(rows_path) else {}
    spec_path = os.path.join(out_dir, "run.json")
    if not os.path.exists(spec_path):
        records.atomic_json(spec_path, {"set": "fontana", "labels_sha256": records.sha256(LABELS_CSV),
                                        "systems_sha256": records.sha256(SYSTEMS_CSV),
                                        "access_sha256": records.sha256(ACCESS),
                                        "sessions": [{"harness_commit": tools["harness_commit"],
                                                      "tools": tools}], "forgotten": []})
    for i, s in enumerate(systems, 1):
        key = records.key_of("qualitas/" + s["system"], s["sha256"])
        if key in rows:
            print(f"[{i}/{len(systems)}] {s['system']}: done, skipped", flush=True)
            continue
        src = os.path.join(pins.PROJECT_ROOT, s["archive"])
        if tree_sha256(src) != s["sha256"]:
            raise RuntimeError(f"{src} does not match its recorded sha256; re-run fontana-prepare")
        os.makedirs(os.path.join(out_dir, ".work"), exist_ok=True)
        work = tempfile.mkdtemp(prefix="cds-fontana-", dir=os.path.join(out_dir, ".work"))
        try:
            print(f"[{i}/{len(systems)}] {s['system']}: unpacking and measuring ...", flush=True)
            unpack(src, work)
            human, unmatched = labels_for_system(work, [r for r in labels if r["system"] == s["system"]])
            meta = {"set": "fontana", "key": key, "repo": "qualitas:" + s["system"],
                    "name": s["system"], "full_name": "qualitas/" + s["system"], "lang": "java",
                    "commit": "archive:" + s["sha256"], "archive": s["archive"], "half": None,
                    "sample": "fontana-systems.csv", "original_url": "qualitas:" + s["system"],
                    "labels_unmatched": unmatched}
            rec = measure.measure_checkout(work, meta, human, pmd, ck, tools)
            records.write_json_gz(records.record_path(out_dir, key), rec)
            rows[key] = run_mod._light(rec["row"])
            records.atomic_json(rows_path, list(rows.values()))
        finally:
            shutil.rmtree(work, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds fontana-prepare", description=__doc__.splitlines()[0])
    ap.add_argument("--arff", default=ARFF)
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--system-attribute", default="project")
    ap.add_argument("--package-attribute", default="package")
    ap.add_argument("--class-attribute", default="complextype")
    ap.add_argument("--label-attribute", default="is_god_class")
    a = ap.parse_args(argv)
    out = prepare(a.arff, a.corpus, {"system_col": a.system_attribute, "package_col": a.package_attribute,
                                     "class_col": a.class_attribute, "label_col": a.label_attribute})
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
