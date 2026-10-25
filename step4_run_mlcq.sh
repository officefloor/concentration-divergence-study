#!/usr/bin/env bash
#
# Step 4 — measure the MLCQ repositories at their labelled commits, both halves (PLAN.md,
# Procedure 3), then score them.
#
#   ./step4_run_mlcq.sh [--allow-dirty]
#
# 1. cds mlcq-prepare (idempotent): labels/mlcq-labels.mapped.csv, labels/mlcq-repos.mapped.csv
#    and labels/mlcq-frame.json (the frozen half and the original URL of every repository);
# 2. measures every repository (the sampler's run loop: shallow clone at the labelled commit,
#    paper one's extractor, PMD and CK, the coupling measurer, then the clone deleted) into
#    results/mlcq/repos/, one record per repository. Resumable: re-run to continue; failures
#    are retried;
# 3. scores every record (results/mlcq/scores/; derived, recomputed when the scoring code changes).
# Nothing is analysed or printed about any result. The confirm half is first read by step 8.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
# PMD with a 16 MB thread stack, as the measurer runs: on deeply nested code its default 1 MB
# overflows, PMD stops part-way through its report, and the repository is logged failed.
export PMD_JAVA_OPTS="${PMD_JAVA_OPTS:--Xss16m}"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
OUT="results/mlcq"

echo "=== STEP 4: prepare MLCQ ==="
"$PY" -m concentration_divergence_study.cli mlcq-prepare
echo
echo "=== STEP 4: measure every MLCQ repository -> $OUT ==="
"$PY" -m concentration_divergence_study.cli study --set mlcq --sample labels/mlcq-repos.mapped.csv \
    --labels labels/mlcq-labels.mapped.csv --frame labels/mlcq-frame.json --out-dir "$OUT" "$@"
echo
echo "=== STEP 4: score ==="
"$PY" -m concentration_divergence_study.cli score --results "$OUT"

cat <<'NEXT'

=== STEP 4 complete. ===
Next — measure the seed-3 sample:

    ./step5_run_seed3.sh

NEXT
