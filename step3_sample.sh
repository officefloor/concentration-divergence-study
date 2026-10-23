#!/usr/bin/env bash
#
# Step 3 — draw the seed-3 Java sample for the tool oracles, and select the 500 measured
# (PLAN.md, Oracles 3; Fixed in advance).
#
#   ./step3_sample.sh [any other `open-source-repository-sampler sample` flag]
#
# 1. prepares the MLCQ material (cds mlcq-prepare: download, paper one's conversion, the frozen
#    split checked, the moved repositories applied), because MLCQ's repositories are excluded
#    from this sample;
# 2. draws Java with seed 3 across the sampler's three tiers, with paper one's substance floor
#    (>= 50 functions in >= 15 files) and the author's ecosystem excluded, to a target of
#    pins.SEED3_DRAW_TARGET usable repositories: a margin over 500 for the exclusions, since the
#    sampler cannot exclude a list of repositories itself;
# 3. selects, in the draw order, the first 500 usable repositories that appear in no exclusion
#    list (paper one's pilot, its seed-2 samples, MLCQ): sample/seed3-measured.csv, with every
#    exclusion recorded in sample/seed3-measured.json.
# Commit sample/ after this step. Interrupted? Re-run the same command to resume the draw.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
# Temporary files (clones, checkouts) on disk in the project, not in a small RAM-backed /tmp.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

PY=".venv/bin/python"
SAMPLER=".venv/bin/open-source-repository-sampler"
[ -x "$SAMPLER" ] || { echo "ERROR: $SAMPLER not found — run ./step1_setup.sh first"; exit 1; }
SEED="$("$PY" -c 'from concentration_divergence_study import pins; print(pins.SEED3)')"
TARGET="$("$PY" -c 'from concentration_divergence_study import pins; print(pins.SEED3_DRAW_TARGET)')"
for a in "$@"; do
  case "$a" in --seed|--seed=*) echo "ERROR: the seed is fixed by the plan ($SEED); seeds 1 and 2 are seen" >&2; exit 1 ;; esac
done

echo "=== STEP 3: prepare MLCQ (its repositories are excluded from this sample) ==="
"$PY" -m concentration_divergence_study.cli mlcq-prepare

echo
echo "=== STEP 3: draw Java, seed $SEED, target $TARGET usable -> sample/ ==="
"$SAMPLER" sample --langs java --tiers high,mid,low --target "$TARGET" --seed "$SEED" \
    --min-functions 50 --min-files-with-functions 15 --exclude-owners officefloor,sagenschneider \
    --label seed3 --out-dir sample "$@"
"$SAMPLER" verify sample/open-source-repository-sample.seed3.csv

echo
echo "=== STEP 3: select the 500 measured ==="
"$PY" -m concentration_divergence_study.cli seed3-select

cat <<'NEXT'

=== STEP 3 complete. Commit sample/ (the draw, its derivation and the selection). ===
Next — measure the MLCQ repositories at their labelled commits:

    ./step4_run_mlcq.sh

NEXT
