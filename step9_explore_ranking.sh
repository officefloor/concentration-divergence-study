#!/usr/bin/env bash
#
# Step 9 — EXPLORATORY, POST HOC: size times calls and the leaf gate (paper, Section 5.9).
#
#   ./step9_explore_ranking.sh                every set, the registered rule (mad_z), ~5 minutes
#   ./step9_explore_ranking.sh --all-rules    every rule of paper one
#
# Steps 9 to 13 are the exploration made after every oracle had been read (PLAN.md, Amendments,
# 10): none of it is confirmatory, and each writes its own results/exploratory/<name>.<utc>.json
# (kind: exploratory, with its sha256 beside it), never analysis.json. Run them in order; each
# ends with ./record_hashes.sh, so commit analysis-hashes.txt after each (or after step 13).
#
# This one: scripts/exploratory_ranking.py, every candidate form built from size and outgoing
# calls, from the raw records, against every oracle.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
[ -f results/analysis.json ] || { echo "ERROR: no results/analysis.json — the exploration follows the confirmatory analysis (./step8_analyse.sh)"; exit 1; }

echo "=== STEP 9 (exploratory): size x calls ranking ==="
"$PY" scripts/exploratory_ranking.py "$@"
./record_hashes.sh
echo
echo "=== STEP 9 complete. Next: ./step10_explore_matched.sh ==="
