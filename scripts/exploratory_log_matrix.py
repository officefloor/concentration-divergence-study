#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. The registered matrix with the complexity signal on a logarithmic scale.

Written after every oracle of the study had been read (PLAN.md, Amendments, 10). Nothing it
prints is confirmatory; it changes no verdict.

Every registered form of the matrix (forms.py) multiplies a complexity signal X by a coupling
factor F: X*D (divergence), X*O (outgoing), X*E (exemption), X*A (amplification), X*N (the size
null), in every definition, input variant and class form. This script recomputes each of them
with ln(1 + X) in place of X, so that the factor has more of the say in the product and the
complexity tail is compressed, and scores every form by the registered rule (modified z >= 3.5,
fitted on every unit of the repository; the |ne forms on the non-exempt units) against every
oracle. The raw forms' counts are read from the study's score files, so each log form is paired
with its raw counterpart on the same repositories, and the forms whose values a logarithm does
not change (the factors alone, the divergence alone, the AND forms) are left out.

Reported per population, with the plan's bootstrap (2000 resamples over repositories, seed
12345): for every form, the pooled MCC raw and log, the paired difference log minus raw, and the
paired difference of the log form against ln(1 + X) alone (does the factor help once X is on a
log scale); the registered primary arms in particular; and the best log forms.

    .venv/bin/python scripts/exploratory_log_matrix.py                # every set
    .venv/bin/python scripts/exploratory_log_matrix.py --sets fontana  # one set
    .venv/bin/python scripts/exploratory_log_matrix.py --workers 6

Writes results/exploratory/log-matrix.<utc>.json (with its sha256) and prints a summary.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from concentration_divergence_study import boot, forms, pins, records, rules, score, units  # noqa: E402

MAD = rules.ORDER.index("mad_z")
LOGGABLE = {"X", "XD", "XO", "XE", "XA", "XDne", "XD_A", "XO_A", "XE_A", "XA_A", "XN", "XDne_A", "XD_B", "XO_B"}

POPULATIONS = [
    ("mlcq", ("explore",), "class", "human_blob"), ("mlcq", ("confirm",), "class", "human_blob"),
    ("mlcq", ("explore",), "method", "human_method_long_method"),
    ("mlcq", ("confirm",), "method", "human_method_long_method"),
    ("fontana", None, "class", "human_fontana_god_class"),
    ("seed3", None, "class", "pmd_GodClass"), ("seed3", None, "class", "decor_blob"), ("seed3", None, "class", "wmc47"),
    ("seed3", None, "method", "pmd_method_NPath200"), ("seed3", None, "method", "brain_method"),
]
PRIMARY = {"class": ["nloc_max", "nloc_max*D_flow[A,np]", "nloc_max*E_flow[A,np]", "nloc_max*A_flow[A,np]",
                     "nloc_max*N", "nloc_max*O_flow[A]", "hvol_sum", "nloc_sum", "nloc_sum*O_flow[A]",
                     "nloc_sum*D_flow[A,np]", "cognitive_max", "cognitive_max*O_flow[A]"],
           "method": ["cognitive", "cognitive*D_flow@all", "cognitive*E_flow@all", "cognitive*A_flow@all",
                      "cognitive*O_flow@all", "nloc", "nloc*E_flow@all", "nloc*E_message@all", "nloc*O_flow@all",
                      "tokens", "tokens*E_flow@all", "cc", "cc*E_flow@all"]}


def log_level(level: units.Level) -> units.Level:
    """A copy of a level with every signal on the ln(1 + X) scale; coupling arrays shared."""
    L = copy.copy(level)
    L.values = {k: np.log1p(np.maximum(np.asarray(v, float), 0.0)) for k, v in level.values.items()}
    return L


def log_cells(args) -> tuple:
    """One repository: the mad_z cells of every loggable form on the log scale, per level."""
    results, key = args
    rec = records.read_json_gz(records.record_path(results, key))
    built = units.joined(rec)
    S = {"method": log_level(built["method"]), "class": log_level(built["class"])}
    out = {}
    for level in ("method", "class"):
        L = S[level]
        specs = forms.SPECS[level]
        oracles = list(L.oracles)
        grouper = forms.Grouper(S["method"].c["file"], L.ids) if level == "class" else None
        cells = np.zeros((len(specs), len(oracles), 4), np.int32)
        if L.n:
            for fi, spec in enumerate(specs):
                if spec[0] not in LOGGABLE:
                    continue
                v = forms.vector(level, spec, S, grouper).astype(float)
                sel = forms.fit_on(level, spec, S)
                if sel is None:
                    mask = rules.mad_z(v)
                else:
                    mask = np.zeros(L.n, bool)
                    mask[sel] = rules.mad_z(v[sel])
                for oi, o in enumerate(oracles):
                    pos, univ = L.oracles[o]
                    f = mask & univ
                    cells[fi, oi] = (int(univ.sum()), int(f.sum()), int((f & pos).sum()), int((pos & univ).sum()))
        out[level] = {"oracles": oracles, "cells": cells}
    return key, out


def est(iv):
    return "n/a" if not iv else f"{iv['value']:+.3f} [{iv['lo']:+.3f}, {iv['hi']:+.3f}]"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", nargs="+", default=["mlcq", "fontana", "seed3"])
    ap.add_argument("--workers", type=int, default=int(os.environ.get("CDS_WORKERS", "6")))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {"kind": "exploratory", "made_utc": stamp, "harness_commit": pins.harness_commit(),
              "note": __doc__.splitlines()[0], "populations": []}
    for s in a.sets:
        results = os.path.join(pins.RESULTS, s)
        scored = {sc["meta"]["key"]: sc for sc in score.load_all(results)
                  if sc["meta"].get("usable") and not sc["meta"].get("error")}
        print(f"{s}: {len(scored)} usable repositories; computing the log forms ...", file=sys.stderr)
        with Pool(a.workers) as pool:
            logs = dict(pool.imap_unordered(log_cells, [(results, k) for k in scored], chunksize=4))
        for set_name, halves, level, oracle in POPULATIONS:
            if set_name != s:
                continue
            keys = [k for k, sc in scored.items()
                    if (halves is None or sc["meta"].get("half") in halves)
                    and oracle in sc["sets"]["joined"][level]["oracles"]
                    and sc["sets"]["joined"][level]["cells"][0, MAD, sc["sets"]["joined"][level]["oracles"].index(oracle), 0] > 0]
            if not keys:
                continue
            names = forms.SPECS[level]
            raw = np.stack([scored[k]["sets"]["joined"][level]["cells"][:, MAD, scored[k]["sets"]["joined"][level]["oracles"].index(oracle), :]
                            for k in keys])                                 # [repo, form, 4]
            lg = np.stack([logs[k][level]["cells"][:, logs[k][level]["oracles"].index(oracle), :] for k in keys])
            n = len(keys)
            m = boot.multiplicities(n)
            rows = []
            for fi, spec in enumerate(names):
                if spec[0] not in LOGGABLE:
                    continue
                nm = forms.name(spec)
                b = forms.base(spec)
                bi = forms.INDEX[level][b] if b in forms.INDEX[level] else None
                r = {"form": nm, "base": b, "mcc_raw": float(boot.mcc_counts(raw[:, fi].sum(0))),
                     "mcc_log": float(boot.mcc_counts(lg[:, fi].sum(0))),
                     "log_minus_raw": boot.micro_diff(raw[:, fi], lg[:, fi], m)}
                if bi is not None and bi != fi:
                    r["log_form_minus_log_base"] = boot.micro_diff(lg[:, bi], lg[:, fi], m)
                    r["raw_form_minus_raw_base"] = boot.micro_diff(raw[:, bi], raw[:, fi], m)
                rates = boot.rates(lg[:, fi].sum(0))
                r["precision_log"], r["recall_log"] = rates["precision"], rates["recall"]
                r["flagged_raw"], r["flagged_log"] = int(raw[:, fi, 1].sum()), int(lg[:, fi, 1].sum())
                rows.append(r)
            label = f"{oracle} [{'+'.join(halves) if halves else 'all'}] {level}: {n} repositories, " \
                    f"{int(raw[:, 0, 0].sum())} units, {int(raw[:, 0, 3].sum())} positives"
            print(f"\n=== {label}")
            print(f"  {'registered arm':34s} {'raw':>6s} {'log':>6s} {'flag raw':>9s} {'flag log':>9s}  log - raw                 log form - log base        raw form - raw base")
            byname = {r["form"]: r for r in rows}
            for nm in PRIMARY[level]:
                r = byname.get(nm)
                if r:
                    print(f"  {nm:34s} {r['mcc_raw']:6.3f} {r['mcc_log']:6.3f} {r['flagged_raw']:9d} {r['flagged_log']:9d}  {est(r['log_minus_raw']):26s} "
                          f"{est(r.get('log_form_minus_log_base')):26s} {est(r.get('raw_form_minus_raw_base'))}")
            top = sorted(rows, key=lambda r: -r["mcc_log"])[:12]
            print(f"  -- best log forms (raw MCC of the same form beside):")
            for r in top:
                print(f"  {r['form']:44s} log {r['mcc_log']:6.3f}  raw {r['mcc_raw']:6.3f}  {est(r['log_minus_raw'])}")
            better = sum(1 for r in rows if r["log_minus_raw"] and r["log_minus_raw"]["lo"] > 0)
            worse = sum(1 for r in rows if r["log_minus_raw"] and r["log_minus_raw"]["hi"] < 0)
            print(f"  -- of {len(rows)} forms, log resolved better than raw in {better}, worse in {worse}")
            report["populations"].append({"population": label, "set_halves": halves, "level": level, "oracle": oracle,
                                          "n_repos": n, "rows": rows, "log_better": better, "log_worse": worse})
    os.makedirs(os.path.join(pins.RESULTS, "exploratory"), exist_ok=True)
    path = a.out or os.path.join(pins.RESULTS, "exploratory", f"log-matrix.{stamp}.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with open(path + ".sha256", "w") as fh:
        fh.write(f"{digest}  {os.path.basename(path)}\n")
    print(f"\nwrote {path}  (exploratory; not part of the plan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
