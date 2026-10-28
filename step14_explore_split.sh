#!/usr/bin/env bash
#
# Step 14 — EXPLORATORY, POST HOC: the split cost, what it takes to bring a method under the cap
# (SPLIT.md).
#
#   ./step14_explore_split.sh                    every set
#   ./step14_explore_split.sh --sets mlcq        one set
#
# Reads the live-width facts step 13 wrote (results/exploratory/livewidth/<set>/, schema 3: the
# variables' reference, definition and write lines, the loops, the calls and the statement tree)
# and, for every method at or over the 26-line trigger, finds the cheapest segmentation into
# pieces of at most 25 lines (scripts/split.py): its worst seam, its cost, its binding to the
# class, and the structural-only, no-input-limit and records variants. scripts/exploratory_split.py then
# reads every form against the oracles as step 13 did (the registered rule; absolute cutoffs
# chosen on the explore half and read on the confirm half; and, among the long methods only,
# the AUC against the label), and the locked share at class level. No fetching: a reader over
# the facts. Post hoc (see step 9).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
[ -f results/analysis.json ] || { echo "ERROR: no results/analysis.json — the exploration follows the confirmatory analysis (./step8_analyse.sh)"; exit 1; }
[ -d results/exploratory/livewidth ] || { echo "ERROR: no results/exploratory/livewidth — the split reads step 13's facts (./step13_explore_livewidth.sh)"; exit 1; }

echo "=== STEP 14 (exploratory): split cost ==="
"$PY" scripts/exploratory_split.py "$@"
./record_hashes.sh
echo
echo "=== STEP 14 complete. Commit analysis-hashes.txt. ==="
