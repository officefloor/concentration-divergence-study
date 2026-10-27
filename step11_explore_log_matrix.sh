#!/usr/bin/env bash
#
# Step 11 — EXPLORATORY, POST HOC: the registered matrix on a log scale (paper, Section 5.9).
#
#   ./step11_explore_log_matrix.sh            ~3 minutes with 6 workers (CDS_WORKERS or --workers)
#
# scripts/exploratory_log_matrix.py: ln(1 + X) in place of every complexity signal X, scored by
# the registered rule against every oracle and paired with the raw form. Post hoc (see step 9).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
[ -f results/analysis.json ] || { echo "ERROR: no results/analysis.json — the exploration follows the confirmatory analysis (./step8_analyse.sh)"; exit 1; }

echo "=== STEP 11 (exploratory): log-scale matrix ==="
"$PY" scripts/exploratory_log_matrix.py "$@"
./record_hashes.sh
echo
echo "=== STEP 11 complete. Next: ./step12_explore_reviewers.sh ==="
