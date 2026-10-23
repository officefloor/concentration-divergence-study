#!/usr/bin/env bash
#
# Step 2 — validate the coupling measurer on the exploration material (PLAN.md, Procedure 2;
# Exploration).
#
#   ./step2_validate.sh [--first N] [--allow-dirty]
#
# Measures paper one's seed-2 Java supplement (inputs/paper-one/sample, committed copies of paper
# one's sample/; already read in paper one, so it is exploration material) exactly as the study
# measures its own sets, into results/validation/, then writes the validation report
# (results/validation/validation.json): the join of the measurer's methods to paper one's units,
# the methods lizard misses, call resolution rates per repository, the JavaParser-only fields
# against lizard's, cognitive complexity against PMD's, the files the extra rule deleted, the DI
# frameworks declared. Measure design may be developed and checked on this material only.
#
# --first N measures the first N usable repositories in the draw order (a quicker check, written
# to results/validation-first-N/). Resumable: re-run the same command to continue.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
FIRST=""
PASS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --first) FIRST="$2"; shift 2 ;;
    --first=*) FIRST="${1#*=}"; shift ;;
    *) PASS+=("$1"); shift ;;
  esac
done
SRC="inputs/paper-one/sample/open-source-repository-sample.java-supplement.csv"
.venv/bin/open-source-repository-sampler verify "$SRC"
SAMPLE="$SRC"
OUT="results/validation"
if [ -n "$FIRST" ]; then
  OUT="results/validation-first-$FIRST"
  SAMPLE="$OUT/sample-first-$FIRST.csv"
  mkdir -p "$OUT"
  "$PY" -m concentration_divergence_study.cli seed3-select --source "$SRC" --head "$FIRST" --out "$SAMPLE"
fi

echo "=== STEP 2: measure the exploration material ($SAMPLE) -> $OUT ==="
"$PY" -m concentration_divergence_study.cli study --set validation --sample "$SAMPLE" --out-dir "$OUT" \
    ${PASS[@]+"${PASS[@]}"}
echo
echo "--- the validation report"
"$PY" -m concentration_divergence_study.cli validate --results "$OUT"

cat <<NEXT

=== STEP 2 complete: $OUT/validation.json ===
Read the report. A fault in the measurer is fixed in measurer/ or the harness, committed, and the
affected repositories re-measured (cds forget --results $OUT --key K --reason R, then re-run).
Next — draw the seed-3 sample (needs \`gh auth login\`):

    ./step3_sample.sh

NEXT
