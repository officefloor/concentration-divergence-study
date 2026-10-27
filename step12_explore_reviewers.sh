#!/usr/bin/env bash
#
# Step 12 — EXPLORATORY, POST HOC: what MLCQ's reviewers judge (paper, Section 5.9).
#
#   ./step12_explore_reviewers.sh             ~3 minutes
#
# scripts/exploratory_reviewers.py: MLCQ's individual reviews joined to the measured units: the
# Long Method rate by length for leaves and the rest, per reviewer, their disagreement, each
# reviewer's own length cutoff, and Blob by class size. Post hoc (see step 9).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
[ -f results/analysis.json ] || { echo "ERROR: no results/analysis.json — the exploration follows the confirmatory analysis (./step8_analyse.sh)"; exit 1; }

echo "=== STEP 12 (exploratory): the individual reviews ==="
"$PY" scripts/exploratory_reviewers.py "$@"
./record_hashes.sh
echo
echo "=== STEP 12 complete. Next: ./step13_explore_livewidth.sh ==="
