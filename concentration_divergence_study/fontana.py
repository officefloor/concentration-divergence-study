"""Fontana's God Class (Arcelli Fontana et al., Empirical Software Engineering 21(3), 2016): the
human replication oracle on the Qualitas Corpus (PLAN.md, Oracles 4).

The material, fetched by ./scripts/fetch_fontana.sh (the MLCSD binary-class datasets from the
Google Drive file the MLCSD page links; the Qualitas Corpus web distribution, release 20130901,
whose r, e and f parts together hold every version, the 20120401 ones Fontana used among them):

    inputs/fontana/ACCESS.md        where each file came from, when, and its access terms (the
                                    plan requires them checked and recorded before measurement;
                                    prepare refuses without this file)
    inputs/fontana/god-class.csv    Fontana's God Class data set (binary_class/god-class.csv of
                                    the MLCSD binary-class datasets): each instance names a
                                    system (`project`, a path ending in the Qualitas system
                                    version), a `package`, a class (`complextype`) and the label
                                    (`is_god_class`)
    inputs/fontana/corpus/          the Qualitas Corpus, unpacked

The fetch script also writes ACCESS.md and SHA256SUMS, from the pages as they read when fetched.

    cds fontana-prepare [--dataset ...] [--corpus ...]
        labels/fontana-labels.csv   system, class (qualified), label: `fontana_god_class` for a
                                    positive, `fontana_god_class_reviewed` for every instance
        labels/fontana-systems.csv  system, archive (relative to the project; `outer!inner` for
                                    an archive nested in another, `;` between several), its
                                    sha256
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
import io
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
DATASET = os.path.join(DIR, "god-class.csv")
CORPUS = os.path.join(DIR, "corpus")
ACCESS = os.path.join(DIR, "ACCESS.md")
LABELS_CSV = os.path.join(pins.LABELS, "fontana-labels.csv")
SYSTEMS_CSV = os.path.join(pins.LABELS, "fontana-systems.csv")
LABEL = "fontana_god_class"
ARCHIVE_EXT = (".zip", ".jar", ".tar.gz", ".tgz", ".tar", ".tar.bz2")


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


def read_table(path: str) -> tuple[list[str], list[list[str]]]:
    """The data set's attribute names and rows, from its CSV (or an ARFF export of it)."""
    if path.lower().endswith(".arff"):
        return read_arff(path)
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def instances(path: str, system_col: str, package_col: str, class_col: str, label_col: str) -> list[dict]:
    attrs, data = read_table(path)
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
        system = row[idx["system"]].strip().rstrip("/").rsplit("/", 1)[-1]   # a path: its last part
        out.append({"system": system, "class": qn,
                    "positive": row[idx["label"]].strip().lower() in ("true", "1", "yes", "t")})
    return out


def _entries(src, name: str) -> list:
    """[(entry name, loader of its bytes)] of the files in a zip, jar or tar archive; `src` is a
    path or a file object."""
    if name.lower().endswith((".zip", ".jar")):
        z = zipfile.ZipFile(src)
        return [(i.filename, lambda z=z, i=i: z.read(i)) for i in z.infolist() if not i.is_dir()]
    t = tarfile.open(src) if isinstance(src, str) else tarfile.open(fileobj=src)
    return [(m.name, lambda t=t, m=m: t.extractfile(m).read()) for m in t.getmembers() if m.isfile()]


def _java_count(src, name: str) -> int:
    return sum(e.endswith(".java") for e, _ in _entries(src, name))


def find_archive(corpus: str, system: str) -> list[str] | None:
    """The source of one system in the corpus, as archive members: `path` for an archive, or
    `path!inner` for an archive nested in it. The corpus keeps each system version in a
    directory named after it (the shortest such path), its sources only in `compressed/`, under
    names that follow no one pattern (`aoisrc281.zip`, `junit-4.10-src.jar`, `src.jar`) and
    sometimes one archive inside another (weka's `weka-src.jar` in `weka-3-7-5.zip`). So the
    source is the archive in `compressed/`, or nested one level in one there, holding the most
    `.java` files, a top-level archive winning a tie. A system shipped as several `*-sources.jar`
    modules named after it in one archive (jung's `jung-api-2.0.1-sources.jar`, ...) is all of
    them; a dependency's sources beside them (jena's `iri-0.8-sources.jar`) are not. None if no
    archive there holds a `.java` file."""
    prefix = system.split("-")[0].lower()
    dirs = [os.path.join(dp, d) for dp, dn, _ in os.walk(corpus) for d in dn if d == system]
    if not dirs:
        return None
    comp = os.path.join(min(dirs, key=len), "compressed")
    if not os.path.isdir(comp):
        return None
    cands = []                                         # (java files, nested, members)
    for fn in sorted(os.listdir(comp)):
        path = os.path.join(comp, fn)
        if not fn.lower().endswith(ARCHIVE_EXT):
            continue
        try:
            es = _entries(path, fn)
        except (OSError, zipfile.BadZipFile, tarfile.TarError):
            continue
        cands.append((sum(e.endswith(".java") for e, _ in es), 0, [path]))
        modules = []
        for e, load in es:
            if not e.lower().endswith(ARCHIVE_EXT):
                continue
            try:
                n = _java_count(io.BytesIO(load()), e)
            except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError):
                continue
            cands.append((n, 1, [f"{path}!{e}"]))
            base = os.path.basename(e).lower()
            if base.endswith("-sources.jar") and base.startswith(prefix) and n:
                modules.append((n, e))
        if len(modules) > 1:
            cands.append((sum(n for n, _ in modules), 1, [f"{path}!{e}" for _, e in modules]))
    if not cands:
        return None
    n, _, members = max(cands, key=lambda c: (c[0], -c[1]))
    return members if n else None


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


def source_sha256(members: list[str]) -> str:
    """The sha256 of a system's source: of its archive, when that is one top-level archive (as
    recorded before nested members were read), else over every member's archive and name."""
    if len(members) == 1 and "!" not in members[0]:
        return tree_sha256(members[0])
    import hashlib
    h = hashlib.sha256()
    for m in members:
        path, _, inner = m.partition("!")
        h.update(f"{os.path.relpath(path, pins.PROJECT_ROOT)}!{inner}".encode() + b"\0"
                 + tree_sha256(path).encode() + b"\n")
    return h.hexdigest()


def prepare(dataset: str, corpus: str, cols: dict) -> dict:
    if not os.path.isfile(ACCESS):
        raise RuntimeError(f"no {ACCESS}: record where the God Class data set and the Qualitas "
                           f"Corpus came from, when, and their access terms before measuring "
                           f"(PLAN.md, Oracles 4)")
    inst = instances(dataset, **cols)
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
            w.writerow([s, ";".join(os.path.relpath(m, pins.PROJECT_ROOT) for m in a),
                        source_sha256(a)])
    return {"instances": len(inst), "positives": sum(i["positive"] for i in inst),
            "systems": len(systems), "systems_without_archive": missing,
            "dataset_sha256": records.sha256(dataset)}


def _extract(src, name: str, dest: str) -> None:
    if name.lower().endswith((".zip", ".jar")):
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
    else:
        with (tarfile.open(src) if isinstance(src, str) else tarfile.open(fileobj=src)) as t:
            t.extractall(dest, filter="data")


def unpack(members: list[str], dest: str) -> None:
    """Unpack a system's source members (see find_archive) into dest; several members each into
    their own directory, so files of the same name do not collide."""
    for m in members:
        path, _, inner = m.partition("!")
        d = dest if len(members) == 1 else os.path.join(dest, os.path.basename(inner or path))
        if os.path.isdir(path):
            shutil.copytree(path, d, symlinks=False, dirs_exist_ok=True)
        elif not inner:
            _extract(path, path, d)
        else:
            load = dict(_entries(path, path))[inner]
            _extract(io.BytesIO(load()), inner, d)


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
        src = [os.path.join(pins.PROJECT_ROOT, m) for m in s["archive"].split(";")]
        if source_sha256(src) != s["sha256"]:
            raise RuntimeError(f"{s['archive']} does not match its recorded sha256; re-run "
                               f"fontana-prepare")
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
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--system-attribute", default="project")
    ap.add_argument("--package-attribute", default="package")
    ap.add_argument("--class-attribute", default="complextype")
    ap.add_argument("--label-attribute", default="is_god_class")
    a = ap.parse_args(argv)
    out = prepare(a.dataset, a.corpus, {"system_col": a.system_attribute, "package_col": a.package_attribute,
                                     "class_col": a.class_attribute, "label_col": a.label_attribute})
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
