#!/usr/bin/env bash
#
# Step 13 — EXPLORATORY, POST HOC: live width, what a reader must hold at once (LIVEWIDTH.md).
#
#   ./step13_explore_livewidth.sh                     every set: measure (resumable), then score
#   ./step13_explore_livewidth.sh --sets mlcq         one set
#
# The records keep no source, so this step fetches every measured repository again: at its
# recorded commit, partial and sparse (only the .java files the measurer read), or a Fontana
# system from its archive (checked against its recorded sha256), and runs the measurer jar's
# LiveWidth pass on it (no symbol solver: seconds to minutes per repository, so hours per set,
# bound by the network). The pass is checked on its fixture first. Facts go to
# results/exploratory/livewidth/<set>/<key>.json.gz; a re-run skips what is written and retries
# what failed. Then scripts/exploratory_livewidth.py scores every variant, and the plain
# counts of the method's variables, and how data flows from what enters the method to its
# internal calls (each call's resolution from the measurer record), against length, tokens, length x [internal call >= 1] and
# the count of all variables, by the registered rule and by absolute cutoffs (the
# MLCQ cutoff chosen on the explore half, read on the confirm half), and writes
# results/exploratory/livewidth.<utc>.json and, small enough to commit, the reviewed methods'
# values as results/exploratory/livewidth-units.<utc>.csv.gz. Needs network access, git 2.27+ and Java 17+ (or
# CDS_JAVA naming one). Post hoc (see step 9).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
[ -f results/analysis.json ] || { echo "ERROR: no results/analysis.json — the exploration follows the confirmatory analysis (./step8_analyse.sh)"; exit 1; }

echo "=== STEP 13 (exploratory): live width ==="
"$PY" scripts/livewidth.py "$@"
"$PY" scripts/exploratory_livewidth.py "$@"
./record_hashes.sh
echo
echo "=== STEP 13 complete. Commit analysis-hashes.txt. ==="
