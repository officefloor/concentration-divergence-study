#!/usr/bin/env bash
#
# Step 5 — measure the seed-3 sample for the tool oracles (PLAN.md, Procedure 3), then score it.
#
#   ./step5_run_seed3.sh [--allow-dirty]
#
# Verifies the draw against its derivation and the selection against the draw and the exclusion
# lists (it must be exactly what `cds seed3-select` gives), then measures every selected
# repository at its pinned commit into results/seed3/ and scores it. Resumable.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
OUT="results/seed3"
.venv/bin/open-source-repository-sampler verify sample/open-source-repository-sample.seed3.csv
"$PY" -c 'from concentration_divergence_study import sample; sample.check(); print("selection verified: sample/seed3-measured.csv")'

echo "=== STEP 5: measure the seed-3 sample -> $OUT ==="
"$PY" -m concentration_divergence_study.cli study --set seed3 --sample sample/seed3-measured.csv \
    --out-dir "$OUT" "$@"
echo
echo "=== STEP 5: score ==="
"$PY" -m concentration_divergence_study.cli score --results "$OUT"

cat <<'NEXT'

=== STEP 5 complete. ===
Next — Fontana's God Class (needs the files placed by hand; see the script):

    ./step6_run_fontana.sh

NEXT
