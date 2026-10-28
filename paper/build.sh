#!/usr/bin/env bash
#
# Build the paper and pack the arXiv bundle.
#
#   ./build.sh
#
# The build needs only main.tex, generated/ and figures/, all tracked, so a fresh clone builds
# without the harness, its results or any Python. Regenerating generated/ from the results is
# `../.venv/bin/python scripts/tables.py`, not part of the build.
#
# report.tex is the full registered report (every secondary, sensitivity and table the paper leaves
# out), built to report.pdf from the same generated/ and packed under anc/full-report/.
#
# Writes: main.pdf, report.pdf, abstract.txt (the abstract as plain text, for the arXiv and Zenodo forms, with
# a warning past arXiv's 1920 characters) and arxiv.tar.gz, the submission bundle: main.tex and
# generated/ at the root and, under anc/, the data the paper rests on (see pack() and
# anc-README.md). The harness's scripts are not packed; they are in the public repository.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"

abstract() {
  local out=abstract.txt
  sed -n '/^\\begin{abstract}$/,/^\\end{abstract}$/p' main.tex \
    | sed -e '1d' -e '$d' \
    | sed -E -e 's/\\noindent//g' \
             -e 's/\\(emph|textbf|textit|texttt|textsc)\{([^}]*)\}/\2/g' \
             -e 's/\\([A-Za-z]+)\{\}/\\\1/g' \
    > "$out.tmp"
  python3 - "$out.tmp" "$out" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
macros = dict(re.findall(r'\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}', open('generated/numbers.tex').read()))
text = open(src).read()
text = re.sub(r'\\([A-Za-z]+)', lambda m: macros.get(m.group(1), m.group(0)), text)
text = text.replace('{,}', ',').replace('``', '"').replace("''", '"').replace('~', ' ')
text = text.replace('$-$', '-').replace('\\%', '%')
text = re.sub(r'\\([%$&_#])', r'\1', text)
text = text.replace('\\', '')
paras, cur = [], []
for line in text.splitlines():
    if line.strip():
        cur.append(line.strip())
    elif cur:
        paras.append(' '.join(cur)); cur = []
if cur:
    paras.append(' '.join(cur))
open(dst, 'w').write('\n\n'.join(paras) + '\n')
PY
  rm -f "$out.tmp"
  local chars; chars=$(wc -c < "$out" | tr -d ' ')
  echo "Wrote $out ($(wc -w < "$out" | tr -d ' ') words, $chars characters, arXiv limit 1920)"
  [ "$chars" -le 1920 ] || echo "WARNING: the abstract is $((chars - 1920)) characters over arXiv's 1920 limit." >&2
}

pack() {
  local stage; stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' RETURN
  mkdir -p "$stage/anc"
  cp anc-README.md "$stage/anc/README.md"
  cp regeneration.txt "$stage/anc/REGENERATION.txt"
  cp generated/DEVIATIONS.md "$stage/anc/DEVIATIONS.md" || echo "   ! generated/DEVIATIONS.md missing: run scripts/tables.py" >&2
  local d="$stage/anc/analysis"; mkdir -p "$d"
  for f in analysis.json analysis.json.sha256; do
    cp "$ROOT/results/$f" "$d/" 2>/dev/null || echo "   ! results/$f missing" >&2; done
  cp "$ROOT"/results/analysis.v*.json "$ROOT"/results/analysis.v*.json.sha256 "$d/" 2>/dev/null || true
  cp "$ROOT"/results/exploratory/*.json "$ROOT"/results/exploratory/*.json.sha256 "$d/" 2>/dev/null || echo "   ! results/exploratory/*.json missing: run scripts/exploratory_ranking.py, exploratory_matched.py, exploratory_log_matrix.py" >&2
  cp "$ROOT"/results/analysis.exploratory.*.json "$ROOT"/results/analysis.exploratory.*.json.sha256 "$d/" 2>/dev/null || true
  cp "$ROOT/analysis-hashes.txt" "$d/"
  d="$stage/anc/decisions"; mkdir -p "$d"
  cp "$ROOT"/decisions/*.json "$d/"            # the choices, and those set aside as *.v1.json
  for s in mlcq seed3 fontana validation; do
    d="$stage/anc/$s"; mkdir -p "$d"
    for f in run.json validation.json study.json run-log.jsonl; do cp "$ROOT/results/$s/$f" "$d/" 2>/dev/null || true; done
  done
  d="$stage/anc/sample"; mkdir -p "$d"
  cp "$ROOT"/sample/*.csv "$ROOT"/sample/*.json "$d/" 2>/dev/null || true
  cp -r "$ROOT"/sample/attempt-1 "$d/" 2>/dev/null || true
  cp "$ROOT"/inputs/paper-one/mlcq-halves.json "$ROOT"/inputs/paper-one/pilot-run-v1-repos.txt "$d/" 2>/dev/null || true
  cp "$ROOT"/mlcq-moved-repositories.csv "$d/"
  d="$stage/anc/labels"; mkdir -p "$d"
  cp "$ROOT"/labels/mlcq-labels.csv "$ROOT"/labels/mlcq-labels.mapped.csv "$ROOT"/labels/mlcq-repos.csv "$ROOT"/labels/mlcq-repos.mapped.csv "$ROOT"/labels/mlcq-summary.json "$ROOT"/labels/mlcq-frame.json "$d/" 2>/dev/null || echo "   ! labels/ missing: run ./step3_sample.sh" >&2
  cp "$ROOT"/labels/fontana-labels.csv "$ROOT"/labels/fontana-systems.csv "$d/" 2>/dev/null || echo "   ! Fontana labels missing: run scripts/fetch_fontana.sh and ./step6_run_fontana.sh" >&2
  cp "$ROOT"/inputs/fontana/ACCESS.md "$ROOT"/inputs/fontana/SHA256SUMS "$d/" 2>/dev/null || true
  cp "$ROOT/PLAN.md" "$ROOT/SINEW.md" "$stage/anc/"
  mkdir -p "$stage/anc/full-report"
  cp report.tex report.pdf "$stage/anc/full-report/" 2>/dev/null || echo "   ! report.pdf missing" >&2
  tar czf arxiv.tar.gz main.tex generated -C "$stage" anc
  echo "Packed arxiv.tar.gz ($(tar tzf arxiv.tar.gz | grep -c .) entries, $(du -h arxiv.tar.gz | cut -f1))"
}

abstract
if ! command -v pdflatex >/dev/null 2>&1; then
  echo "pdflatex not found: install TeX Live. main.tex targets pdflatex, which arXiv runs." >&2
  exit 1
fi
pdflatex -interaction=nonstopmode -halt-on-error main.tex > build.log 2>&1 || { grep -n "^!" -A 3 build.log | head -40; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error main.tex > build.log 2>&1 || { grep -n "^!" -A 3 build.log | head -40; exit 1; }
echo "Built main.pdf ($(pdfinfo main.pdf 2>/dev/null | awk '/Pages/{print $2}') pages); $(grep -c Overfull build.log || true) overfull boxes, $(grep -c 'LaTeX Warning' build.log || true) LaTeX warnings (see build.log)"
grep -n "undefined\|Undefined\|multiply" build.log | head -20 || true
pdflatex -interaction=nonstopmode -halt-on-error report.tex > build-report.log 2>&1 || { grep -n "^!" -A 3 build-report.log | head -40; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error report.tex > build-report.log 2>&1 || { grep -n "^!" -A 3 build-report.log | head -40; exit 1; }
echo "Built report.pdf, the full registered report ($(pdfinfo report.pdf 2>/dev/null | awk '/Pages/{print $2}') pages)"
grep -n "undefined\|Undefined\|multiply" build-report.log | head -20 || true
pack
