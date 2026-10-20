"""concentration-divergence-study command line (also `cds`). The numbered step scripts call these;
each is also usable on its own.

  cds deps                                   PMD 7.27.0 and CK 0.7.0 into ./lib (paper one's pins)
  cds mlcq-prepare                           MLCQ labels, the frozen split, the moved repositories
  cds seed3-select                           the 500 seed-3 repositories measured, after exclusions
  cds fontana-prepare                        Fontana's God Class labels and the Qualitas archives
  cds study --set S --sample CSV --out-dir D [--labels CSV] [--frame JSON]
                                             measure every usable repository of a sample
  cds study-fontana --out-dir D              measure the Qualitas systems
  cds forget --results D --key K --reason R  re-measure repositories after a measurement fix
  cds score --results D                      score every measured repository (derived, cached)
  cds validate --results D [--half explore]  the measurer's validation report
  cds explore                                the explore-half choices, written to decisions/
  cds analyse [--exploratory]                the confirmatory analysis (once), or a labelled re-run
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys

from . import pins

DELEGATED = {"mlcq-prepare": "mlcq", "seed3-select": "sample", "fontana-prepare": "fontana",
             "score": "score", "validate": "validate", "explore": "explore", "analyse": "analyse"}


def _tools(lib: str | None):
    from complexity_concentration_study import deps as p1deps
    lib = lib or pins.LIB
    return p1deps.default_pmd(lib), p1deps.default_ck(lib)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in DELEGATED:
        mod = importlib.import_module(f".{DELEGATED[argv[0]]}", __package__)
        return mod.main(argv[1:])
    ap = argparse.ArgumentParser(prog="cds", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("deps", help="download PMD and CK into ./lib (sha256-verified)")
    dp.add_argument("--lib", default=None)
    st = sub.add_parser("study", help="measure every usable repository of a sample")
    st.add_argument("--set", required=True, help="the set's name (mlcq, seed3, validation, ...)")
    st.add_argument("--sample", required=True)
    st.add_argument("--out-dir", required=True)
    st.add_argument("--labels", default=None)
    st.add_argument("--frame", default=None, help="JSON with halves / original_url per URL")
    st.add_argument("--lib", default=None)
    st.add_argument("--allow-dirty", action="store_true",
                    help="measure from uncommitted code (never for a confirmatory set)")
    sf = sub.add_parser("study-fontana", help="measure the Qualitas systems of Fontana's data set")
    sf.add_argument("--out-dir", required=True)
    sf.add_argument("--lib", default=None)
    sf.add_argument("--allow-dirty", action="store_true")
    fg = sub.add_parser("forget", help="mark repositories for re-measurement (recorded)")
    fg.add_argument("--results", required=True)
    fg.add_argument("--key", action="append", required=True)
    fg.add_argument("--reason", required=True)
    for name in DELEGATED:
        sub.add_parser(name, add_help=False, help=f"see `cds {name} --help`")
    args = ap.parse_args(argv)
    if args.cmd == "deps":
        from complexity_concentration_study import deps as p1deps
        p1deps.fetch(args.lib or pins.LIB)
        return 0
    if args.cmd == "study":
        from . import run
        pmd, ck = _tools(args.lib)
        run.run(args.sample, args.out_dir, args.set, pmd, ck, labels_path=args.labels,
                frame_path=args.frame, allow_dirty=args.allow_dirty)
        return 0
    if args.cmd == "study-fontana":
        from . import fontana
        pmd, ck = _tools(args.lib)
        fontana.run(args.out_dir, pmd, ck, args.allow_dirty)
        return 0
    if args.cmd == "forget":
        from . import run
        run.forget(args.results, args.key, args.reason)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
