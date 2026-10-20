#!/usr/bin/env bash
#
# Step 7 — the choices the plan delegates to the MLCQ explore half (PLAN.md, Procedure 4).
#
#   ./step7_explore.sh
#
# Makes sure every MLCQ record is scored, then `cds explore` reads the EXPLORE half only: the
# measurer's validation on it, X* (class) and X*_m (method) chosen by complexity alone, and the
# effective-sample gate. Writes decisions/explore-choices.json and
# decisions/measurer-validation.mlcq-explore.json, once. Commit them before step 8: the
# analysis refuses to run until they are committed, so the order is in the git history.
#
# Before committing, `./step8_analyse.sh --check` runs the whole analysis on the explore half
# (no confirm, seed-3 or Fontana score is opened), to find faults in the analysis code first.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
"$PY" -m concentration_divergence_study.cli score --results results/mlcq
echo
echo "=== STEP 7: explore-half choices ==="
"$PY" -m concentration_divergence_study.cli explore

cat <<'NEXT'

=== STEP 7 complete. Commit decisions/ now:

    git add decisions && git commit -m "Record the explore-half choices"

Then the confirmatory analysis:

    ./step8_analyse.sh

NEXT
