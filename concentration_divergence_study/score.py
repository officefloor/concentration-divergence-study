"""Score every measured repository: every form, every rule, every definition, both result sets.

    cds score --results results/<set> [--workers N]

Derived data only, written to results/<set>/scores/<key>.npz, one per repository, and
recomputed whenever the record or the scoring code changes (the file names the record's sha256,
a hash of the scoring modules, and the harness commit that scored it). The analysis reads only these files, so a fault in the
analysis is fixed and re-run in minutes, and one in the scoring is fixed and re-scored without
measuring anything again.

Per repository, result set and level:
  cells        int32 [form, rule, definition, 4]: n_univ, n_out, n_overlap, n_god_univ, the
               lean confusion counts of paper one (study._cell), each definition over its own
               universe (the reviewed units for a human definition). Every rule is fitted on
               every unit of the level, zeros included.
  scale, zero  per form, the scale the modified z used (0 mad, 1 mean_ad, 2 constant) and the
               share of zeros, the diagnostics PLAN.md reads first
  extracts     for a human definition (scored on reviewed units), per candidate X* and
               definition k: the modified z of X and X*D_k over the reviewed units with their
               labels (for the pooled AUC), the leaf diagnostic's counts, and the cells within the
               tertiles of X (secondary 2)
  spearman     within-repository rank correlation of every complexity signal with d_k and out_k
  roles        units (and complexity, by cc) in each role: catchment, pipe, junction
Nothing is read or printed about any result here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

from complexity_concentration_study import study as p1

from . import forms, pins, records, rules, units

SCALE_CODE = {"mad": 0, "mean_ad": 1, "constant": 2}
# The modules a score depends on. A score is recomputed when any of them changes (or its record
# does), and not otherwise, so an unrelated commit does not force a re-score.
SCORING_MODULES = ("score.py", "units.py", "forms.py", "rules.py", "javaparser.py", "measure.py")


def scoring_code() -> str:
    """sha256 over the source of the scoring modules and the installed paper-one commit."""
    import hashlib
    h = hashlib.sha256(str(pins.paper_one_installed().get("commit")).encode())
    here = os.path.dirname(os.path.abspath(__file__))
    for m in SCORING_MODULES:
        with open(os.path.join(here, m), "rb") as fh:
            h.update(m.encode() + b"\0" + fh.read())
    return h.hexdigest()


def _counts(flag: np.ndarray, pos: np.ndarray, univ: np.ndarray) -> list[int]:
    f = flag & univ
    return [int(univ.sum()), int(f.sum()), int((f & pos).sum()), int((pos & univ).sum())]


def _ranks(a: np.ndarray) -> np.ndarray:
    """Average ranks (1-based), ties sharing the mean rank."""
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    return (np.cumsum(counts) - (counts - 1) / 2)[inv]


def spearman(x: np.ndarray, y: np.ndarray):
    if len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    dx, dy = rx - rx.mean(), ry - ry.mean()
    den = float(np.sqrt((dx * dx).sum() * (dy * dy).sum()))
    return float((dx * dy).sum() / den) if den > 0 else None


def _tertile(v: np.ndarray) -> np.ndarray:
    q1, q2 = np.quantile(v, [1 / 3, 2 / 3]) if len(v) else (0, 0)
    return np.where(v <= q1, 0, np.where(v <= q2, 1, 2))


def score_level(level: str, S: dict) -> dict:
    L = S[level]
    specs = forms.SPECS[level]
    oracles = [o for o in L.oracles]
    nf, nr, no = len(specs), len(rules.ORDER), len(oracles)
    cells = np.zeros((nf, nr, no, 4), np.int32)
    scale = np.zeros(nf, np.int8)
    zero = np.zeros(nf, np.float32)
    grouper = forms.Grouper(S["method"].c["file"], L.ids) if level == "class" else None
    x_masks: dict = {}
    form_masks: dict = {}                    # the d and O forms' masks, for the AND forms
    vectors_kept: dict = {}
    keep = set(forms.CLASS_CANDIDATES if level == "class" else forms.METHOD_CANDIDATES)
    for fi, spec in enumerate(specs):
        if L.n == 0:
            break
        if spec[0] in ("AND", "ANDO"):
            masks = [a & b for a, b in zip(x_masks[spec[1]], form_masks[forms.and_partner(level, spec)])]
            scale[fi], zero[fi] = -1, np.nan
        else:
            v = forms.vector(level, spec, S, grouper).astype(float)
            masks = rules.all_rules(v)
            kind, _ = rules.mad_z_scale(v)
            scale[fi] = SCALE_CODE[kind]
            zero[fi] = float((v == 0).mean())
            if spec[0] in ("d", "d_A", "O", "O_A"):
                form_masks[spec] = masks
            if spec[0] == "X":
                x_masks[spec[1]] = masks
                if spec[1] in keep:
                    vectors_kept[spec[1]] = v
        for ri, mask in enumerate(masks):
            for oi, o in enumerate(oracles):
                pos, univ = L.oracles[o]
                cells[fi, ri, oi] = _counts(mask, pos, univ)
    out = {"oracles": oracles, "cells": cells, "scale": scale, "zero": zero, "n": L.n,
           "n_coupled": int(L.coupled.sum())}
    out["extracts"] = _extracts(level, S, oracles, vectors_kept, x_masks)
    out["spearman"] = _spearman(level, S)
    out["roles"] = _roles(level, S)
    return out


def _primary_d(level: str, S: dict, k: str, i: str = "np") -> np.ndarray:
    return (forms.method_d(S["method"], k, "all") if level == "method"
            else forms.class_d(S["class"], k, i))


def _extracts(level: str, S: dict, oracles: list, vectors: dict, x_masks: dict) -> dict:
    """Per human definition (one with a reviewed universe): what the per-unit secondaries need."""
    L = S[level]
    out = {}
    mad = rules.ORDER.index("mad_z")
    inputs = forms.INPUTS if level == "class" else ("all",)
    for o in oracles:
        pos, univ = L.oracles[o]
        if univ.all():
            continue                                   # a tool definition: no reviewed universe
        rev = np.flatnonzero(univ)
        rec = {"label": pos[rev].astype(int).tolist(), "coupled": L.coupled[rev].astype(int).tolist(),
               "z": {}, "leaf": {}, "tertile": {}}
        for x, v in vectors.items():
            _, zx = rules.mad_z_scale(v)
            rec["z"][x] = np.round(zx[rev], 4).tolist()
            flagged = x_masks[x][mad]
            ter = _tertile(v)
            for k in units.DEFS:
                d = _primary_d(level, S, k)
                vd = v * forms.fD(d)
                _, zd = rules.mad_z_scale(vd)
                rec["z"][f"{x}|D_{k}"] = np.round(zd[rev], 4).tolist()
                flag_d = rules.mad_z(vd)
                # tertiles of X: cells of X and X*D_k (mad_z) over the reviewed units in each
                rec["tertile"][f"{x}|{k}"] = [
                    [_counts(flagged, pos, univ & (ter == t)), _counts(flag_d, pos, univ & (ter == t))]
                    for t in range(3)]
                for i in inputs:
                    di = _primary_d(level, S, k, i) if level == "class" else d
                    sel = flagged & univ & L.coupled
                    catch = di < 0
                    rec["leaf"][f"{x}|{k}|{i}"] = [int((sel & catch).sum()), int((sel & catch & pos).sum()),
                                                  int((sel & ~catch).sum()), int((sel & ~catch & pos).sum())]
        out[o] = rec
    return out


def _spearman(level: str, S: dict) -> dict:
    L = S[level]
    sel = L.coupled
    out = {}
    if sel.sum() < 3:
        return out
    for k in units.DEFS:
        d = _primary_d(level, S, k)
        o = (forms.method_out(L, k, "all") if level == "method" else L.c[f"out_{k}"])
        for x, v in L.values.items():
            out[f"{x}|d_{k}"] = spearman(v[sel], d[sel])
            out[f"{x}|out_{k}"] = spearman(v[sel], o[sel])
    return out


def _roles(level: str, S: dict) -> dict:
    L = S[level]
    sel = L.coupled
    cc = L.values["cc" if level == "method" else "cc_sum"]
    out = {}
    for k in units.DEFS:
        d = _primary_d(level, S, k)
        for role, m in (("catchment", d < 0), ("pipe", d == 0), ("junction", d > 0)):
            out[f"{k}|{role}"] = [int((sel & m).sum()), float(cc[sel & m].sum())]
    return out


def score_record(rec: dict) -> dict:
    sets = units.build(rec)
    out = {"sets": {}}
    for set_name, S in sets.items():
        out["sets"][set_name] = {lvl: score_level(lvl, S) for lvl in ("class", "method")}
    out["join"] = sets["joined"]["join"]
    return out


def _meta(rec: dict, path: str) -> dict:
    row = rec["row"]
    jp = row.get("javaparser_summary") or {}
    return {"key": row["key"], "repo": row["repo"], "original_url": row.get("original_url"),
            "full_name": row["full_name"], "set": row.get("set"), "half": row.get("half"),
            "usable": bool(p1.is_usable(row)), "error": row.get("error") or row.get("javaparser_error"),
            "di": (row.get("di") or {}).get("frameworks", []), "pruned": row.get("pruned"),
            "files_skipped": row.get("files_skipped"), "human_labels": row.get("human_labels"),
            "labels_out_of_scope": row.get("labels_out_of_scope"), "pmd": "pmd_gods" in row,
            "ck": "ck_def_gods" in row, "javaparser": jp, "harness_commit": (row.get("tools") or {}).get("harness_commit"),
            "record_sha256": records.sha256(path)}


def _write(path: str, meta: dict, sc: dict) -> None:
    arrays = {}
    js = {"meta": meta, "join": sc.get("join"), "sets": {}}
    for s, levels in sc.get("sets", {}).items():
        js["sets"][s] = {}
        for lvl, d in levels.items():
            arrays[f"{s}.{lvl}.cells"] = d["cells"]
            arrays[f"{s}.{lvl}.scale"] = d["scale"]
            arrays[f"{s}.{lvl}.zero"] = d["zero"]
            js["sets"][s][lvl] = {k: v for k, v in d.items() if k not in ("cells", "scale", "zero")}
    arrays["json"] = np.frombuffer(json.dumps(js).encode(), dtype=np.uint8)
    tmp = path + ".part.npz"
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)


def read(path: str) -> dict:
    with np.load(path) as z:
        js = json.loads(bytes(z["json"]).decode())
        for s in js["sets"]:
            for lvl in js["sets"][s]:
                for a in ("cells", "scale", "zero"):
                    js["sets"][s][lvl][a] = z[f"{s}.{lvl}.{a}"]
    return js


def _one(rec_path: str, out_path: str, commit: str, code: str) -> str:
    rec = records.read_json_gz(rec_path)
    meta = _meta(rec, rec_path)
    meta["scored_by"] = commit
    meta["scoring_code"] = code
    meta["forms"] = {"class": len(forms.CLASS_FORMS), "method": len(forms.METHOD_FORMS)}
    if meta["error"] or rec.get("javaparser") is None or rec.get("units") is None:
        _write(out_path, meta, {"sets": {}})
        return rec_path
    _write(out_path, meta, score_record(rec))
    return rec_path


def _stale(rec_path: str, out_path: str, code: str) -> bool:
    if not os.path.exists(out_path):
        return True
    try:
        with np.load(out_path) as z:
            meta = json.loads(bytes(z["json"]).decode())["meta"]
    except Exception:
        return True
    return meta.get("scoring_code") != code or meta.get("record_sha256") != records.sha256(rec_path)


def run(results: str, workers: int = 6) -> None:
    commit = pins.harness_commit() or "unknown"
    code = scoring_code()
    rec_dir = os.path.join(results, "repos")
    out_dir = os.path.join(results, "scores")
    os.makedirs(out_dir, exist_ok=True)
    recs = sorted(f for f in os.listdir(rec_dir) if f.endswith(".json.gz"))
    todo = []
    for f in recs:
        rp = os.path.join(rec_dir, f)
        op = os.path.join(out_dir, f[:-len(".json.gz")] + ".npz")
        if _stale(rp, op, code):
            todo.append((rp, op))
    live = {f[:-len(".json.gz")] + ".npz" for f in recs}
    for f in os.listdir(out_dir):                     # a record forgotten since: its score goes
        if f.endswith(".npz") and f not in live:
            os.remove(os.path.join(out_dir, f))
    print(f"scoring {len(todo)} of {len(recs)} repositories in {results} (harness {commit}, "
          f"scoring code {code[:12]}, {workers} workers)", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, rp, op, commit, code): rp for rp, op in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            fut.result()
            if i % 10 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)} scored ({time.time() - t0:.0f}s)", flush=True)


def load_all(results: str, halves: tuple | None = None) -> list[dict]:
    """Every score of a set, optionally only the repositories of the given halves. A score file
    is read only if its half is wanted, so the explore step never opens a confirm score."""
    out_dir = os.path.join(results, "scores")
    rows = {r["key"]: r for r in records.load_rows(results)}
    out = []
    for key in sorted(rows):
        if halves is not None and rows[key].get("half") not in halves:
            continue
        p = os.path.join(out_dir, key + ".npz")
        if not os.path.exists(p):
            raise FileNotFoundError(f"no score for {key}: run `cds score --results {results}`")
        out.append(read(p))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cds score", description=__doc__.splitlines()[0])
    ap.add_argument("--results", required=True)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("CDS_WORKERS", "6")))
    a = ap.parse_args(argv)
    run(a.results, a.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
