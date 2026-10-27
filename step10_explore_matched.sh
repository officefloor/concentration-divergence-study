#!/usr/bin/env bash
#
# Step 10 — EXPLORATORY, POST HOC: ranking or flag rate (paper, Section 5.9).
#
#   ./step10_explore_matched.sh               ~7 minutes
#
# scripts/exploratory_matched.py: the threshold-free pooled AUC of the per-repository modified z
# and percentile over the reviewed units, and every form read at a matched flag rate. Post hoc
# (see step 9).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
[ -f results/analysis.json ] || { echo "ERROR: no results/analysis.json — the exploration follows the confirmatory analysis (./step8_analyse.sh)"; exit 1; }

echo "=== STEP 10 (exploratory): AUC and matched flag rate ==="
"$PY" scripts/exploratory_matched.py "$@"
./record_hashes.sh
echo
echo "=== STEP 10 complete. Next: ./step11_explore_log_matrix.sh ==="
