#!/usr/bin/env bash
#
# Set up for replication: .venv with the pinned Python dependencies (paper one's package at its
# pinned commit, the sampler, numpy), PMD 7.27.0 and CK 0.7.0 into ./lib (paper one's pins,
# sha256-verified), and the coupling measurer built with Maven (JavaParser pinned in
# measurer/pom.xml). Then the test suite.
#
# Needs on the machine: python3 (3.10+), git, Java 17+ and Maven 3. Override the interpreter
# with PYTHON=..., the dependency dir with CDS_LIB=... .
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "[1/5] creating .venv"
"$PYTHON" -m venv .venv
echo "[2/5] installing pinned Python dependencies (paper one's package from its pinned commit)"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e '.[test]'
echo "[3/5] downloading PMD + CK into ./lib (verified by sha256)"
.venv/bin/python -m concentration_divergence_study.cli deps
echo "[4/5] building the coupling measurer (measurer/target/divergence-measurer.jar)"
(cd measurer && mvn -B -q package)
echo "[5/5] running the tests"
.venv/bin/python -m pytest -q tests
echo "setup complete."
