"""The on-disk layout of a measured set (results/<set>/), written by run.py and read by the
analysis. Generated data is never edited (PLAN.md, Fixed in advance): a fault is fixed in the
code, the affected output deleted and the step re-run.

    results/<set>/
      study.json         one light row per measured repository (paper one's row, reduced),
                         rewritten atomically after each repository
      repos/<key>.json.gz  the full record of each repository (measure.py)
      run-log.jsonl      the sampler's run log (resume: repositories recorded done are skipped)
      run.json           how the set was measured: the sample(s), their sha256, the tools
      scores/            the per-repository scores of the analysis (score.py), derived data
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os


def key_of(full_name: str, commit: str) -> str:
    return f"{full_name.replace('/', '__')}@{commit[:12]}"


def record_path(out_dir: str, key: str) -> str:
    return os.path.join(out_dir, "repos", key + ".json.gz")


def write_json_gz(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        # dumps, not dump: dump streams through the pure-Python encoder, which recurses once per
        # nested container and fails at the interpreter's limit on a deeply nested value (a
        # live-width statement tree of a long else-if chain); dumps uses the C encoder
        fh.write(json.dumps(data, separators=(",", ":")))
    os.replace(tmp, path)


def read_json_gz(path: str):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def atomic_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, path)


def load_rows(out_dir: str) -> list[dict]:
    path = os.path.join(out_dir, "study.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no {path}: measure the set first")
    with open(path) as fh:
        return json.load(fh)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
