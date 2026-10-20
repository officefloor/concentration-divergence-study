"""Run the coupling measurer (measurer/, JavaParser with its symbol solver) on one checkout, and
check it before any repository is measured.

The measurer is the Java program in measurer/src (built by ./setup.sh into MEASURER_JAR). Its
output, per analysed file, is every method and constructor with its parameters, visibility, line
range, the complexity fields re-implemented on the syntax tree, and every call with its argument
count and how the symbol solver resolved it (Measurer.java states the rules). Nothing here
interprets it; units.py does.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import tempfile

from . import pins

# Call kinds and resolutions, as Measurer.java writes them. CALL_THROW_NEW is a `new` that is the
# expression of a `throw` (counted as a constructor call; kept apart for the diagnostics).
CALL_METHOD, CALL_NEW, CALL_EXPLICIT_CTOR, CALL_THROW_NEW = 0, 1, 2, 3
RES_INTERNAL, RES_JDK, RES_REPO_NOT_ANALYSED, RES_UNRESOLVED, RES_SHOULD_HAVE, RES_BUDGET = range(6)
RESOLUTIONS = ("internal", "jdk", "repo_not_analysed", "unresolved", "should_have_resolved",
               "budget")


class MeasurerFailed(RuntimeError):
    pass


def version(jar: str = pins.MEASURER_JAR) -> str:
    out = subprocess.run(["java", "-jar", jar, "--version"], capture_output=True, text=True,
                         timeout=120)
    return out.stdout.strip()


def measure(root: str, files: list[str], jar: str = pins.MEASURER_JAR,
            budget_seconds: int = pins.MEASURER_BUDGET_SECONDS) -> dict:
    """The measurer's document for `files` (repo-relative .java paths) of the checkout `root`."""
    work = tempfile.mkdtemp(prefix="cds-jp-")
    try:
        lst = os.path.join(work, "files.txt")
        out = os.path.join(work, "out.json.gz")
        with open(lst, "w", encoding="utf-8") as fh:
            fh.write("\n".join(files) + "\n")
        cmd = ["java", f"-Xmx{pins.MEASURER_HEAP}", "-Xss16m", "-jar", jar, "--root", root,
               "--files", lst, "--out", out, "--budget-seconds", str(budget_seconds)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=budget_seconds + 3600)
        if p.returncode != 0 or not os.path.exists(out):
            raise MeasurerFailed(f"measurer exited {p.returncode}: {(p.stderr or '')[-2000:]}")
        with gzip.open(out, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except subprocess.TimeoutExpired as e:
        raise MeasurerFailed(f"measurer timed out after {e.timeout}s") from e
    finally:
        shutil.rmtree(work, ignore_errors=True)


# A fixture with one call of every resolution the study distinguishes. The measurer must
# report exactly these, or no repository is measured.
_FIXTURE = {
    "src/main/java/a/T.java": """package a;
public class T {
    public T() { this(1); }
    T(int x) { }
    public int foo(int a, int b) {
        Runnable r = () -> { if (a > 1) { System.out.println(); } };
        Object o = new Object() {
            @Override public String toString() { return a > 0 ? "x" : "y"; }
        };
        return a;
    }
}
""",
    "src/main/java/b/U.java": """package b;
import a.T;
import org.external.Lib;
public class U extends T {
    private int helper(int x) { return x + 1; }
    public int run(String s, int y) {
        int v = helper(y);
        String t = s.trim();
        Lib.call(s, y);
        new T(3);
        if (v > 1 && y > 0) { for (int i = 0; i < y; i++) { if (i % 2 == 0) { v++; } else if (i > 5) { v--; } else { v += 2; } } }
        return run2(v, v, v);
    }
    int run2(int a, int b, int... c) { if (a < 0) { throw new IllegalStateException("x"); } return a; }
    public U() { super(1); }
}
""",
}
# (file, method name, name line) -> (params, vis, cc, cognitive, nesting, calls)
_EXPECTED = {
    ("src/main/java/a/T.java", "T", 3): (0, "public", 1, 0, 0, [[1, 2, 0, 0]]),
    ("src/main/java/a/T.java", "T", 4): (1, "package", 1, 0, 0, []),
    ("src/main/java/a/T.java", "foo", 5): (2, "public", 2, 2, 2, [[0, 0, 1, -1], [0, 1, 1, -1]]),
    ("src/main/java/a/T.java", "toString", 8): (0, "public", 2, 1, 1, []),
    ("src/main/java/b/U.java", "helper", 5): (1, "private", 1, 0, 0, []),
    ("src/main/java/b/U.java", "run", 6): (2, "public", 6, 9, 3,
                                           [[1, 0, 0, 1], [0, 0, 1, -1], [2, 0, 3, -1],
                                            [1, 1, 0, 0], [3, 0, 0, 1]]),
    ("src/main/java/b/U.java", "run2", 14): (3, "package", 2, 1, 1, [[1, 3, 1, -1]]),
    ("src/main/java/b/U.java", "U", 15): (0, "public", 1, 0, 0, [[1, 2, 0, 0]]),
}


def check(jar: str = pins.MEASURER_JAR) -> list[str]:
    """Problems with the measurer: missing, the wrong JavaParser, or not measuring the fixture
    exactly as expected. Empty when it is fit to measure."""
    if not os.path.isfile(jar):
        return [f"no measurer jar at {jar}: run ./step1_setup.sh (it builds measurer/ with Maven)"]
    problems = []
    v = version(jar)
    if v != pins.JAVAPARSER_VERSION:
        problems.append(f"the measurer reports JavaParser {v!r}, not the pinned "
                        f"{pins.JAVAPARSER_VERSION}: rebuild it (./setup.sh)")
    root = tempfile.mkdtemp(prefix="cds-jp-fixture-")
    try:
        for rel, body in _FIXTURE.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write(body)
        doc = measure(root, sorted(_FIXTURE), jar, budget_seconds=600)
    except MeasurerFailed as e:
        return problems + [f"the measurer failed on its fixture: {e}"]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    got = {}
    for f in doc["files"]:
        for m in f["methods"]:
            got[(f["path"], m["name"], m["name_line"])] = (
                m["params"], m["vis"], m["cc"], m["cognitive"], m["nesting"], m["calls"])
    for key, want in _EXPECTED.items():
        if got.get(key) != want:
            problems.append(f"measurer fixture {key}: got {got.get(key)}, expected {want}")
    extra = set(got) - set(_EXPECTED)
    if extra:
        problems.append(f"measurer fixture: unexpected units {sorted(extra)}")
    return problems


def java_problems() -> list[str]:
    return [] if shutil.which("java") else ["no `java` on PATH: the measurer, PMD and CK need a JRE 17+"]
