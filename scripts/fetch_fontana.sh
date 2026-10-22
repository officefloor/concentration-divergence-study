#!/usr/bin/env bash
#
# Fetch Fontana's God Class data set and the Qualitas Corpus into inputs/fontana/, with curl,
# and record where every file came from (PLAN.md, Oracles 4: the access terms are checked and
# recorded before measurement).
#
#   ./scripts/fetch_fontana.sh
#
# 1. The data set: the MLCSD "binary class datasets" (Arcelli Fontana et al.), the Google Drive
#    file the MLCSD page links (essere.disco.unimib.it/?p=109), sha256-verified;
#    binary_class/god-class.csv -> inputs/fontana/god-class.csv (420 instances, 74 systems).
# 2. The pages that state the terms, saved as fetched into inputs/fontana/provenance/: the
#    MLCSD page, the Qualitas Corpus download and acquisition pages.
# 3. The Qualitas Corpus web distribution, release 20130901 (the only release on the web; the
#    20120401 one Fontana used is "available on request"). Its "r" part (3.3 GiB, the latest
#    version of each system) first; then, only while a system version the data set names is
#    still missing, its "f" part (0.84 GiB) and its "e" parts (16.75 GiB), which together with
#    "r" hold every version. Each tar is unpacked into inputs/fontana/corpus/.
# 4. inputs/fontana/SHA256SUMS (every file fetched) and inputs/fontana/ACCESS.md (where, when,
#    and the terms quoted from the saved pages). Commit both. A second run verifies every file
#    against SHA256SUMS and refuses on a mismatch, and keeps the section of ACCESS.md recorded
#    by hand ("## The maintainer's reply" to the end of the file) as it is.
#
# Resumable: curl continues a partial download (-C -). Needs curl, tar, unzip, sha256sum and
# the project's venv (step 1).
set -euo pipefail
cd "$(dirname "$0")/.."

D="inputs/fontana"
DL="$D/download"
PROV="$D/provenance"
CORPUS="$D/corpus"
SUMS="$D/SHA256SUMS"
PY=".venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: $PY not found — run ./step1_setup.sh first"; exit 1; }
mkdir -p "$DL" "$PROV" "$CORPUS"

DATASET_URL="https://drive.usercontent.google.com/download?id=15aXc_el-nx4tQwU3khunQ-I5ObSA1-Zb&export=download&confirm=t"
DATASET_SHA256="7752a681d58b4c7239a591cf0425b2cc4c7d29d1b6cce50f875e6bae6270d8ef"
QC="http://www.cs.auckland.ac.nz/~ewan/download/corpus"
R_PARTS="QualitasCorpus-20130901r-pt1.tar QualitasCorpus-20130901r-pt2.tar"
F_PARTS="QualitasCorpus-20130901f.tar"
E_PARTS="$(for i in 1 2 3 4 5 6 7 8 9; do printf 'QualitasCorpus-20130901e-pt%s.tar ' "$i"; done)"

# fetch URL FILE: download (resuming) unless present, then check it against SHA256SUMS if
# that file names it, else record its sha256 there.
fetch() {
  local url="$1" out="$2" name
  name="$(basename "$out")"
  if [ ! -f "$out" ]; then
    echo "  downloading $name"
    # The corpus server (New Zealand) drops long transfers; retry on any error and resume the
    # partial file, up to 50 times.
    local tries=0
    until curl -sS -fL --retry 5 --retry-all-errors --retry-delay 10 -C - -o "$out.part" "$url"; do
      tries=$((tries + 1))
      [ "$tries" -lt 50 ] || { echo "ERROR: $name did not download after $tries attempts" >&2; exit 1; }
      echo "  resuming $name (attempt $((tries + 1)))"
      sleep 15
    done
    mv "$out.part" "$out"
  fi
  local got
  got="$(sha256sum "$out" | cut -d' ' -f1)"
  if [ -f "$SUMS" ] && grep -q "  $name\$" "$SUMS"; then
    grep -q "^$got  $name\$" "$SUMS" || { echo "ERROR: $out does not match its sha256 in $SUMS" >&2; exit 1; }
  else
    echo "$got  $name" >> "$SUMS"
  fi
}

# missing: the system versions the data set names that are not yet in the corpus
missing() {
  "$PY" - "$D/god-class.csv" "$CORPUS" <<'EOF'
import sys
from concentration_divergence_study import fontana
inst = fontana.instances(sys.argv[1], "project", "package", "complextype", "is_god_class")
need = sorted({i["system"] for i in inst})
print(" ".join(s for s in need if fontana.find_archive(sys.argv[2], s) is None))
EOF
}

unpack() {
  local tar="$1" mark="$CORPUS/.unpacked-$(basename "$1")"
  [ -f "$mark" ] && return 0
  echo "  unpacking $(basename "$tar")"
  tar -xf "$tar" -C "$CORPUS"
  touch "$mark"
}

echo "=== 1. the God Class data set ==="
fetch "$DATASET_URL" "$DL/mlcsd-binary-class-datasets.zip"
got="$(sha256sum "$DL/mlcsd-binary-class-datasets.zip" | cut -d' ' -f1)"
[ "$got" = "$DATASET_SHA256" ] || { echo "ERROR: the data set's sha256 $got is not the pinned $DATASET_SHA256" >&2; exit 1; }
unzip -o -q -j "$DL/mlcsd-binary-class-datasets.zip" binary_class/god-class.csv -d "$D"
echo "  $D/god-class.csv: $(($(wc -l < "$D/god-class.csv") - 1)) instances"

echo "=== 2. the pages stating the terms ==="
TODAY="$(date -u +%Y-%m-%d)"
curl -fsSL -k -m 120 -o "$PROV/mlcsd.$TODAY.html" "https://essere.disco.unimib.it/?p=109" || echo "  WARNING: the MLCSD page could not be fetched"
curl -fsSL -m 120 -o "$PROV/qualitas-download.$TODAY.html" "http://qualitascorpus.com/download/"
curl -fsSL -m 120 -o "$PROV/qualitas-acquisition.$TODAY.html" "http://qualitascorpus.com/docs/acquisition.html"

echo "=== 3. the Qualitas Corpus (20130901) ==="
for p in $R_PARTS; do fetch "$QC/$p" "$DL/$p"; unpack "$DL/$p"; done
M="$(missing)"
if [ -n "$M" ]; then
  echo "  not in the r distribution: $M"
  for p in $F_PARTS; do fetch "$QC/$p" "$DL/$p"; unpack "$DL/$p"; done
  M="$(missing)"
fi
if [ -n "$M" ]; then
  echo "  not in r or f: $M"
  for p in $E_PARTS; do fetch "$QC/$p" "$DL/$p"; unpack "$DL/$p"; done
  M="$(missing)"
fi
[ -z "$M" ] && echo "  every system version the data set names is in the corpus" \
            || echo "  WARNING: still missing (recorded in ACCESS.md; their labels are reported unmatched): $M"

echo "=== 4. ACCESS.md ==="
text() { sed -e 's/<[^>]*>/ /g' "$1" | tr -s ' \n' ' ' | sed -e 's/&nbsp;/ /g'; }
# The maintainer's reply is recorded by hand after the first run; a later run keeps it.
REPLY=""
[ -f "$D/ACCESS.md" ] && REPLY="$(sed -n "/^## The maintainer's reply\$/,\$p" "$D/ACCESS.md")"
{
  echo "# Fontana's God Class and the Qualitas Corpus: where they came from"
  echo
  echo "Written by \`./scripts/fetch_fontana.sh\` on $TODAY (UTC); do not edit by hand, except the"
  echo "maintainer's reply at the end, which a later run keeps. The sha256 of every file fetched is"
  echo "in \`SHA256SUMS\`; the pages quoted are saved in \`provenance/\`."
  echo
  echo "## The data set"
  echo
  echo "- MLCSD binary-class datasets (Arcelli Fontana, Mäntylä, Zanoni and Marino, Empirical"
  echo "  Software Engineering 21(3), 2016), the file the MLCSD page links:"
  echo "  $DATASET_URL"
  echo "- \`god-class.csv\` is \`binary_class/god-class.csv\` of that archive (sha256 pinned in the script)."
  echo "- The MLCSD page (provenance/mlcsd.$TODAY.html) states no licence for the files it links."
  echo
  echo "## The corpus"
  echo
  echo "- Qualitas Corpus (Tempero et al., APSEC 2010), web distribution of release 20130901, from"
  echo "  $QC/ ; parts fetched: $(ls "$DL" | grep -c '^QualitasCorpus' || true)."
  echo "- Fontana's data set names versions of the 20120401 release, which is no longer on the web"
  echo "  (\"can be provided if required\"); the 20130901 r, e and f distributions together hold the"
  echo "  complete corpus, every version. System versions the data set names that are not in what was"
  echo "  fetched: ${M:-none}."
  echo "- Terms, as the acquisition page reads (provenance/qualitas-acquisition.$TODAY.html):"
  echo
  echo "  > $(text "$PROV/qualitas-acquisition.$TODAY.html" | grep -oE 'The Qualitas Corpus is available[^.]*\.[^.]*\.' | head -1)"
  echo
  echo "- The download page (provenance/qualitas-download.$TODAY.html) offers the parts openly over the web."
  echo
  echo "Check these terms before measuring, and record any reply from the corpus's maintainer here"
  echo "in a commit of its own (PLAN.md, Oracles 4)."
  if [ -n "$REPLY" ]; then
    echo
    printf '%s\n' "$REPLY"
  fi
} > "$D/ACCESS.md.new"
mv "$D/ACCESS.md.new" "$D/ACCESS.md"
sha256sum "$PROV"/*.html | sed -e "s|  $PROV/|  provenance/|" >> "$SUMS"
sort -u -k2 "$SUMS" -o "$SUMS"

cat <<'NEXT'

=== Fontana material fetched. Read inputs/fontana/ACCESS.md, then commit it with SHA256SUMS:

    git add inputs/fontana/ACCESS.md inputs/fontana/SHA256SUMS && git commit -m "Record where Fontana's material came from"

Then measure it:

    ./step6_run_fontana.sh

NEXT
