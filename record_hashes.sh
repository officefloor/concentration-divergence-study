#!/usr/bin/env bash
#
# Write analysis-hashes.txt: the sha256 of every analysis and of what it rests on, so the files
# a paper quotes are auditable against what was committed when. Regenerated in full, never
# edited; the order of events is shown by this file's git history, not by its content.
#
#   ./record_hashes.sh
#
# Listed: results/analysis.json (checked first against the .sha256 written beside it), every
# results/analysis.v*.json (a confirmatory analysis set aside by an amendment, PLAN.md
# Amendments, 9 and 10), every results/analysis.exploratory.*.json, the decisions (those set
# aside by Amendment 10 as *.v1.json beside them), every results/exploratory/ranking.*.json
# (scripts/exploratory_ranking.py, post hoc), the labels and samples measured, and each set's
# run.json and validation.json.
set -euo pipefail
cd "$(dirname "$0")"
shopt -s nullglob

A="results/analysis.json"
if [ -f "$A" ]; then
  RECORDED="$(cut -d' ' -f1 "$A.sha256")"
  ACTUAL="$(sha256sum "$A" | cut -d' ' -f1)"
  [ "$RECORDED" = "$ACTUAL" ] || { echo "ERROR: $A does not match $A.sha256" >&2; exit 1; }
fi
OUT="analysis-hashes.txt"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
{
  echo "# sha256 of the analyses and of what they rest on. Written by ./record_hashes.sh; never"
  echo "# edited by hand. results/analysis.json is the confirmatory analysis (PLAN.md, Fixed in"
  echo "# advance); analysis.v*.json and decisions/*.v1.json were set aside by an amendment (PLAN.md,"
  echo "# Amendments, 9 and 10);"
  echo "# analysis.exploratory.*.json are later re-analyses."
  for f in results/analysis.json results/analysis.v*.json results/analysis.exploratory.*.json \
           results/exploratory/ranking.*.json decisions/*.json \
           labels/MLCQCodeSmellSamples.csv labels/mlcq-*.csv labels/mlcq-*.json labels/fontana-*.csv \
           sample/* results/*/run.json results/*/validation.json; do
    [ -f "$f" ] && sha256sum "$f"
  done
} > "$TMP"
mv "$TMP" "$OUT"
trap - EXIT
echo "Wrote $OUT ($(grep -vc '^#' "$OUT") files hashed). Commit it."
