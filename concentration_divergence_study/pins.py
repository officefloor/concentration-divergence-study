"""Every pinned constant of the study, in one place, and where the project keeps its files.

A change to any value here changes numbers; make it as its own commit, so a difference between
two runs can be traced to it (PLAN.md, Fixed in advance).
"""
from __future__ import annotations

import json
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- paper one: the complexity extractor, the rules, the statistics, the PMD/CK panels -------
PAPER_ONE_URL = "https://github.com/officefloor/complexity-concentration-study"
PAPER_ONE_COMMIT = "393da766e5630ab05478a9b1ce896e3626741b09"

# --- the coupling measurer ---------------------------------------------------------------------
JAVAPARSER_VERSION = "3.28.2"              # measurer/pom.xml, javaparser.version
MEASURER_JAR = os.path.join(PROJECT_ROOT, "measurer", "target", "divergence-measurer.jar")
# The JVM heap the measurer runs with, and its per-repository time budget for resolving calls:
# a call met after the budget is spent is recorded as unresolved by budget (resolution 5), so a
# pathological repository is bounded and the loss is counted, never silent. 8 hours (PLAN.md,
# Amendments, 2): openjdk/jdk, the largest Java repository, spent a 1-hour budget with 22% of
# its calls left; a repository that still spends it is kept, and the primary is also read
# without it (analyse.py, sensitivity).
MEASURER_HEAP = os.environ.get("CDS_MEASURER_HEAP", "6g")
MEASURER_BUDGET_SECONDS = 8 * 3600

# --- the plan's constants (PLAN.md) ------------------------------------------------------------
SEED3 = 3                                   # the tool-oracle sample's seed
SEED3_USABLE = 500                          # usable repositories measured from it
SEED3_DRAW_TARGET = 540                     # drawn with a margin for the exclusions (step 3)
BOOTSTRAP_B = 2000
BOOTSTRAP_SEED = 12345
HALF_WIDTH = 0.10                           # the effective-sample gate's target half-width
GATE_FLOOR = 20
OUTLIER_RULE = "mad_z"                      # the rule every estimand reads (its constant 3.5)

# Path segments that drop a .java file before any rule is fitted, on top of paper one's file
# rule (PLAN.md, Analysed sources). Matched against every DIRECTORY segment, at any depth.
EXTRA_TEST_SEGMENTS = ("androidTest", "testFixtures", "integrationTest")
EXTRA_BUILD_SEGMENTS = ("build", "target", "generated", "generated-sources", "out", "bin")

# --- where things live -------------------------------------------------------------------------
LIB = os.environ.get("CDS_LIB") or os.path.join(PROJECT_ROOT, "lib")
RESULTS = os.environ.get("CDS_RESULTS") or os.path.join(PROJECT_ROOT, "results")
LABELS = os.path.join(PROJECT_ROOT, "labels")
SAMPLE = os.path.join(PROJECT_ROOT, "sample")
INPUTS = os.path.join(PROJECT_ROOT, "inputs")
DECISIONS = os.environ.get("CDS_DECISIONS") or os.path.join(PROJECT_ROOT, "decisions")
MOVED_REPOSITORIES = os.path.join(PROJECT_ROOT, "mlcq-moved-repositories.csv")


# The files scripts/fetch_fontana.sh writes while it runs (a day-long download that appends a
# hash line after each corpus part). They record where data came from; no number depends on
# them, so an append in progress does not make the harness dirty.
FETCH_RECORDS = ("inputs/fontana/SHA256SUMS", "inputs/fontana/ACCESS.md")


def harness_commit() -> str | None:
    """This harness's git commit, plus '-dirty' when tracked files have uncommitted changes
    (the fetch script's own records, FETCH_RECORDS, excepted)."""
    try:
        sha = subprocess.run(["git", "-C", PROJECT_ROOT, "rev-parse", "HEAD"], capture_output=True,
                             text=True, timeout=30)
        if sha.returncode != 0:
            return None
        dirty = subprocess.run(["git", "-C", PROJECT_ROOT, "status", "--porcelain",
                                "--untracked-files=no", "--", "."]
                               + [f":!{f}" for f in FETCH_RECORDS], capture_output=True, text=True, timeout=30)
        return sha.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return None


def paper_one_installed() -> dict:
    """What pip recorded about the installed paper-one package: its version and, for a VCS
    install, the commit it was installed from (PEP 610 direct_url.json)."""
    from importlib import metadata
    try:
        dist = metadata.distribution("complexity-concentration-study")
    except metadata.PackageNotFoundError:
        return {"installed": False}
    out = {"installed": True, "version": dist.version, "commit": None, "url": None}
    raw = dist.read_text("direct_url.json")
    if raw:
        d = json.loads(raw)
        out["url"] = d.get("url")
        out["commit"] = (d.get("vcs_info") or {}).get("commit_id")
    return out


def paper_one_problems() -> list[str]:
    info = paper_one_installed()
    if not info["installed"]:
        return ["paper one's package (complexity-concentration-study) is not installed: run "
                "./step1_setup.sh"]
    if info["commit"] != PAPER_ONE_COMMIT:
        return [f"paper one's package is installed from {info['url']} @ {info['commit']}, not the "
                f"pinned {PAPER_ONE_COMMIT}: the baseline would not be paper one's numbers. "
                f"Re-run ./step1_setup.sh"]
    return []
