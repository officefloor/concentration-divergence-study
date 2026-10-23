#!/usr/bin/env bash
#
# Step 8 — the analysis (PLAN.md, Procedure 5 and 6).
#
#   ./step8_analyse.sh                 the confirmatory analysis: results/analysis.json, once
#   ./step8_analyse.sh --exploratory   a later re-analysis: results/analysis.exploratory.<utc>.json
#   ./step8_analyse.sh --check         a dry run on the MLCQ explore half only (before step 7's
#                                      commit is fine): results/analysis.check.<utc>.json
#
# Re-scores anything stale (a scoring fix since), writes the validation report of every measured
# set (diagnostics, read first), runs `cds analyse`, then ./record_hashes.sh (not for --check).
# Commit analysis-hashes.txt afterwards: the confirmatory analysis's sha256 is committed once.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
MODE="${1:-}"
case "$MODE" in ""|--exploratory|--check) ;; *) echo "ERROR: unknown flag $MODE" >&2; exit 1 ;; esac

if [ "$MODE" = "--check" ]; then
  "$PY" -m concentration_divergence_study.cli score --results results/mlcq
else
  for s in mlcq seed3 fontana; do
    [ -f "results/$s/study.json" ] || { echo "NOTE: results/$s not measured; its secondaries read as not estimable"; continue; }
    "$PY" -m concentration_divergence_study.cli score --results "results/$s"
    "$PY" -m concentration_divergence_study.cli validate --results "results/$s"
  done
fi
echo
echo "=== STEP 8: analyse ${MODE:-(confirmatory)} ==="
"$PY" -m concentration_divergence_study.cli analyse $MODE
if [ "$MODE" != "--check" ]; then
  ./record_hashes.sh
  echo
  echo "=== STEP 8 complete. Commit analysis-hashes.txt. ==="
fi
