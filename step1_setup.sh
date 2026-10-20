#!/usr/bin/env bash
#
# Step 1 — set up for replication (PLAN.md, Procedure 2 needs it).
#
#   ./step1_setup.sh
#
# A thin alias for ./setup.sh: .venv with paper one's package installed from its pinned commit
# (complexity, rules, statistics, PMD/CK panels, MLCQ converter), the pinned sampler and numpy;
# PMD 7.27.0 and CK 0.7.0 into ./lib (sha256-verified); the coupling measurer built with Maven
# (JavaParser pinned in measurer/pom.xml); then the test suite.
#
# Needs on the machine: python3, git, Java 17+ and Maven 3. Step 3 (sampling) also needs the
# GitHub CLI authenticated (`gh auth login`).
set -euo pipefail
cd "$(dirname "$0")"

echo "=== STEP 1: setup ==="
./setup.sh "$@"

cat <<'NEXT'

=== STEP 1 complete. ===
Next — validate the measurer on the exploration material (paper one's seed-2 Java sample):

    ./step2_validate.sh            # or --first 30 for a quicker check

NEXT
