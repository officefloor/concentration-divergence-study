#!/usr/bin/env bash
#
# Step 6 — Fontana's God Class on the Qualitas Corpus (PLAN.md, Oracles 4), then score it.
#
#   ./step6_run_fontana.sh [--allow-dirty]
#
# The data set and the corpus cannot be downloaded by a script (the MLCSD page links them
# through pages and drives; the Qualitas Corpus is distributed by its maintainers). Place them
# first, and record where they came from:
#   inputs/fontana/ACCESS.md        source, date and access terms of each file (required)
#   inputs/fontana/god-class.arff   the God Class data set
#   inputs/fontana/corpus/          the Qualitas Corpus source archives of its systems
# Then this step converts the labels (labels/fontana-labels.csv, labels/fontana-systems.csv with
# each archive's sha256), measures each system's archive into results/fontana/, and scores it.
# The attribute names of the ARFF default to project / package / complextype / is_god_class;
# run `cds fontana-prepare --help` to change them.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
OUT="results/fontana"
for f in inputs/fontana/ACCESS.md inputs/fontana/god-class.arff; do
  [ -f "$f" ] || { echo "ERROR: $f is missing (see the head of this script)" >&2; exit 1; }
done
[ -d inputs/fontana/corpus ] || { echo "ERROR: inputs/fontana/corpus/ is missing" >&2; exit 1; }

echo "=== STEP 6: convert Fontana's labels and locate the archives ==="
"$PY" -m concentration_divergence_study.cli fontana-prepare
echo
echo "=== STEP 6: measure every system -> $OUT ==="
"$PY" -m concentration_divergence_study.cli study-fontana --out-dir "$OUT" "$@"
echo
echo "=== STEP 6: score ==="
"$PY" -m concentration_divergence_study.cli score --results "$OUT"

cat <<'NEXT'

=== STEP 6 complete. ===
Next — the explore-half choices:

    ./step7_explore.sh

NEXT
