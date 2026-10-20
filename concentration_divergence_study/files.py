"""The analysed sources: paper one's file rule, plus the plan's extra exclusions, applied to the
checkout itself before anything is measured.

PLAN.md, Analysed sources (as amended, see its Amendments): on top of paper one's rule (which
already leaves out test directories, vendored trees, root build directories, generated-by-name
and oversize files), both result sets drop every `.java` file whose SOURCE ROOT (its directory
less the path of its `package` declaration) has a segment named `androidTest`, `testFixtures` or
`integrationTest`, or `build`, `target`, `generated`, `generated-sources`, `out` or `bin`, at
any depth. A segment inside the package path is a package name (`org.springframework.restdocs
.build`), not a build directory, and does not exclude. A file whose directory does not end in
its package path (or that declares none) has its whole directory checked. The files are
deleted from the (temporary) clone before paper one's extractor, PMD, CK and the coupling
measurer run, so every tool sees the same file set and paper one's code runs
unchanged. What was deleted is counted per segment and listed, and labels on deleted files are
counted as out of scope (measure.py).

Also here: which dependency-injection frameworks a repository declares in its build files, for
the plan's sensitivity (Diagnostics, Calls static parsing cannot see).
"""
from __future__ import annotations

import os
import re

from . import pins


_PACKAGE = re.compile(r"(?m)^\s*package\s+([\w.]+)\s*;")


def package_of(path: str) -> str:
    """The package a Java file declares ("" for none or an unreadable file)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            m = _PACKAGE.search(fh.read())
    except OSError:
        return ""
    return m.group(1) if m else ""


def source_root_segments(rel: str, package: str) -> list[str]:
    """The directory segments of a repo-relative file above its package path."""
    dirs = rel.replace(os.sep, "/").split("/")[:-1]
    pkg = package.split(".") if package else []
    if pkg and len(dirs) >= len(pkg) and dirs[len(dirs) - len(pkg):] == pkg:
        return dirs[:len(dirs) - len(pkg)]
    return dirs


def extra_exclusion(rel: str, package: str = "") -> str | None:
    """The segment that excludes a repo-relative `.java` path under the plan's extra rule, or
    None. Only the source root's segments are checked (see the module docstring)."""
    if not rel.endswith(".java"):
        return None
    for seg in source_root_segments(rel, package):
        if seg in pins.EXTRA_TEST_SEGMENTS or seg in pins.EXTRA_BUILD_SEGMENTS:
            return seg
    return None


def prune(root: str) -> dict:
    """Delete every `.java` file the extra rule excludes. Returns {"removed": n, "by_segment":
    {segment: n}, "paths": [...]} (paths repo-relative, sorted)."""
    removed = []
    by_seg: dict = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for fn in filenames:
            if not fn.endswith(".java"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            seg = extra_exclusion(rel, package_of(os.path.join(dirpath, fn)))
            if seg is None:
                continue
            os.remove(os.path.join(dirpath, fn))
            removed.append(rel)
            by_seg[seg] = by_seg.get(seg, 0) + 1
    return {"removed": len(removed), "by_segment": dict(sorted(by_seg.items())),
            "paths": sorted(removed)}


# Build-file coordinates of each framework. `javax.inject`/`jakarta.inject` alone are the JSR-330
# annotations every one of them uses, so they mark CDI only together with an enterprise artifact.
DI_PATTERNS = {
    "spring": re.compile(r"org\.springframework"),
    "guice": re.compile(r"com\.google\.inject"),
    "cdi": re.compile(r"(?:javax|jakarta)\.enterprise|cdi-api|org\.jboss\.weld"),
    "dagger": re.compile(r"com\.google\.dagger"),
    "micronaut": re.compile(r"io\.micronaut"),
    "quarkus": re.compile(r"io\.quarkus"),
}
BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")


def di_frameworks(root: str) -> dict:
    """{"frameworks": [names], "build_files": n}: the DI frameworks any Maven or Gradle build file
    of the checkout names (read as text; no build is run)."""
    found: set = set()
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        for fn in filenames:
            if fn not in BUILD_FILES:
                continue
            n += 1
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for name, rx in DI_PATTERNS.items():
                if rx.search(text):
                    found.add(name)
    return {"frameworks": sorted(found), "build_files": n}
