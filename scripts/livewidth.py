#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. Live width: how many variables a reader holds at once in a method.

Written after every oracle of the study had been read (PLAN.md, Amendments, 10): nothing it
measures is confirmatory, and it changes no verdict. It measures what the stored records cannot
give, because they keep no source: per method, every variable's live range (first reference to
last, in line order), the lines it is used at, and how often it is assigned. A variable declared
with no value or a literal one starts at its first use, since the declaration could move there
without changing the method (the declaration-start reading is kept as a variant). The method's
statement tree is recorded too, so a reader can tell where a cut may fall. A method's
width at a line is the sum of the
weights of the variables live there, and its live width is the largest such width: what has to
be held in mind at the hardest point of reading it, against the 4 +- 1 (Cowan) or 7 +- 2
(Miller) a reader can hold. The prior measures it builds on, and the gaps it closes, are in
LIVEWIDTH.md.

    .venv/bin/python scripts/livewidth.py --sets mlcq seed3 fontana     # facts, per repository
    .venv/bin/python scripts/livewidth.py --check                       # the fixture only

Each measured repository is fetched again (a repository at its recorded commit, partial and
sparse: only the .java files the measurer read; a Fontana system unpacked from its archive,
checked against its recorded sha256) and parsed by the measurer jar's LiveWidth pass (no symbol
solver, so seconds to minutes per repository). The file list is the record's own (the measurer's
files), so the units are the measurer's; every repository's facts are checked against the
record's units, and a mismatch is counted, never dropped. Writes
results/exploratory/livewidth/<set>/<key>.json.gz; resumable (a repository written by this
schema is skipped; one written by an older schema is measured again).
The widths are read by scripts/exploratory_livewidth.py with the functions below.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from concentration_divergence_study import pins, records  # noqa: E402

MAIN = "net.officefloor.divergence.LiveWidth"
SCHEMA = 3                                  # LiveWidth.SCHEMA
OUT = os.path.join(pins.RESULTS, "exploratory", "livewidth")

# a variable's facts, and a call's, as LiveWidth.java writes them: the range from the first
# reference (a literal declaration included) to the last, as text and widened over loops; the
# definitions, steps and writes into it; the variables it is computed from; whether it is a
# literal declaration (LIT); the range start from the first use instead (USE_FIRST, as text;
# USE_LOOP_FIRST, over loops); the distinct lines it is used at (REFS); the distinct lines of
# its definitions that have a line (DEF_LINES: an initializer, a binding, an assignment, an
# increment; not a parameter's argument or a field's prior state); and the lines of the writes
# into its object (MUT_LINES)
(NAME, KIND, FIRST, LAST, LOOP_FIRST, LOOP_LAST, DEFS, STEPS, MUTS, FROM,
 LIT, USE_FIRST, USE_LOOP_FIRST, REFS, DEF_LINES, MUT_LINES) = range(16)
C_LINE, C_ARGS, C_RECEIVER, C_RESULT = range(4)
# a node of the method's statement tree (m["tree"], the body): its first and last line, whether
# it is a sequence (a block, a switch entry: its children are statements in order, and any
# contiguous run of them is what Extract Method can move) or a statement (its children are the
# sequences and statements directly inside it), its kind, and its children
S_START, S_END, S_SEQ, S_KIND, S_KIDS = range(5)
# the kinds: the jumps say whether a run can be moved, 6 to 9 are where developers cut
(K_OTHER, K_RETURN, K_BREAK, K_CONTINUE, K_THROW, K_YIELD, K_IF, K_LOOP, K_TRY, K_SWITCH,
 K_SYNCHRONIZED, K_LABELED, K_BLOCK, K_ENTRY) = range(14)
JUMPS = (K_RETURN, K_BREAK, K_CONTINUE, K_THROW, K_YIELD)
STRUCTURAL = (K_IF, K_LOOP, K_TRY, K_SWITCH)
PARAM, LOCAL, FIELD = 0, 1, 2

# The variants: which variables (locals: parameters and locals; all: fields too), the range
# (text: first to last reference; loop: widened over every loop the variable is referenced in
# and declared outside of), the weight (unit: 1, the unweighted count; assign: every definition
# and write into it; role: 1 plus the definitions that are not steps, plus writes into it, so a
# value set once and a loop counter are 1, Sajaniemi's fixed value and stepper), and where a
# range starts (use: the first use, so a parameter from its first reference and a local declared
# with no value or a literal one from its first use, not its declaration; decl: such a local from
# its declaration; sig: a parameter from the signature).
SCOPES = {"locals": (PARAM, LOCAL), "all": (PARAM, LOCAL, FIELD)}
FLOWS = ("text", "loop")
WEIGHTS = ("unit", "assign", "role")
STARTS = ("use", "decl", "sig")
HEADLINE = ("loop", "role", "all", "use")
# the widths an absolute threshold is read at: below, at and above the working-memory span
OVER = (3, 4, 5, 6, 7, 8, 9)


def variants() -> list[tuple]:
    out = [(f, w, s, "use") for f in FLOWS for w in WEIGHTS for s in SCOPES]
    out.append(("loop", "role", "all", "decl"))
    out.append(("loop", "role", "all", "sig"))
    return out


def label(v: tuple) -> str:
    return "[" + ",".join(v[:3] if v[3] == "use" else v) + "]"


def weight(var: list, how: str) -> float:
    if how == "unit":
        return 1.0
    if how == "assign":
        return float(max(1, var[DEFS] + var[MUTS]))
    return float(1 + max(0, var[DEFS] - 1 - var[STEPS]) + var[MUTS])


def widths(m: dict, variant: tuple) -> np.ndarray:
    """The width at each of the method's code lines (m["lines"], in order)."""
    flow, how, scope, start = variant
    kinds = SCOPES[scope]
    vs = [v for v in m["vars"] if v[KIND] in kinds]
    lines = np.asarray(m["lines"], float)
    if not vs or not len(lines):
        return np.zeros(len(lines))
    if start == "decl":
        lo = np.array([v[LOOP_FIRST] if flow == "loop" else v[FIRST] for v in vs], float)
    else:
        lo = np.array([v[USE_LOOP_FIRST] if flow == "loop" else v[USE_FIRST] for v in vs], float)
    hi = np.array([v[LOOP_LAST] if flow == "loop" else v[LAST] for v in vs], float)
    if start == "sig":
        lo = np.where([v[KIND] == PARAM for v in vs], m["name_line"], lo)
    w = np.array([weight(v, how) for v in vs])
    live = (lo[:, None] <= lines[None, :]) & (lines[None, :] <= hi[:, None])
    return (live * w[:, None]).sum(0)


def summary(m: dict, variant: tuple) -> dict:
    """max, mean (over the code lines), area (their sum), the code lines wider than each k of
    OVER, and the first line of the peak."""
    w = widths(m, variant)
    if not len(w):
        return {"max": 0.0, "mean": 0.0, "area": 0.0, "peak_line": None,
                **{f"over{k}": 0 for k in OVER}}
    return {"max": float(w.max()), "mean": float(w.mean()), "area": float(w.sum()),
            "peak_line": int(m["lines"][int(w.argmax())]),
            **{f"over{k}": int((w > k).sum()) for k in OVER}}


# The plain counts beside the widths: how many variables the method references, with no regard
# to when they are live (all: parameters, locals and fields; locals: parameters and locals), by
# kind, how many are reassigned beyond a step (role weight above 1), and the sum of the role
# weights (the width the method would have if every variable were live at once).
COUNTS = ("all", "locals", "params", "fields", "reassigned", "weighted")


def counts(m: dict) -> dict:
    vs = m["vars"]
    return {"all": len(vs),
            "locals": sum(v[KIND] in SCOPES["locals"] for v in vs),
            "params": sum(v[KIND] == PARAM for v in vs),
            "fields": sum(v[KIND] == FIELD for v in vs),
            "reassigned": sum(weight(v, "role") > 1 for v in vs),
            "weighted": float(sum(weight(v, "role") for v in vs))}


def sequences(tree: list) -> list[list[tuple[int, int]]]:
    """Every sequence of the tree, outermost first, as the line ranges of its statements in
    order: the places a cut may fall are between two statements of one sequence."""
    out = []
    todo = [tree]
    while todo:
        n = todo.pop(0)
        if n[S_SEQ]:
            out.append([(k[S_START], k[S_END]) for k in n[S_KIDS]])
        todo.extend(n[S_KIDS])
    return out


# How data moves through a method, from what enters it to the calls it fans out to (only the
# calls that resolve to an analysed file: the measurer's internal calls, its sinew).
#   in_params, in_fields, in_results  what enters: parameters and fields referenced, and the
#                                     variables an internal call's result is held in
#   in_all                            all three, each variable once
#   max_from                          the most variables any one variable is computed from
#   derived                           the variables computed from at least one other
#   out_vars                          the variables passed to an internal call (argument or
#                                     receiver)
#   max_fanout                        the most internal calls one variable is passed to
#   in_out                            entering variables that reach an internal call, directly or
#                                     through what is computed from them
#   in_through                        parameters and fields passed to an internal call as they
#                                     came (never reassigned): a pipe strand
#   in_caught                         entering variables that reach no internal call
#   bridging                          variables live (the headline range: loops, first use) at
#                                     two or more lines with an internal call: state held
#                                     across calls
#   lw_at_calls                       the headline width at the lines with an internal call
FLOW = ("in_params", "in_fields", "in_results", "in_all", "max_from", "derived", "out_vars",
        "max_fanout", "in_out", "in_through", "in_caught", "bridging", "lw_at_calls")


def flow(m: dict, internal: list) -> dict:
    """The FLOW measures of one method; `internal` holds, per call of m["calls"], whether it
    resolved to an analysed file (the measurer record's resolution, call for call)."""
    vs = m["vars"]
    calls = [c for c, keep in zip(m.get("calls", []), internal) if keep]
    params = {i for i, v in enumerate(vs) if v[KIND] == PARAM}
    fields = {i for i, v in enumerate(vs) if v[KIND] == FIELD}
    results = {c[C_RESULT] for c in calls if c[C_RESULT] >= 0}
    incoming = params | fields | results
    fanout = [0] * len(vs)
    for c in calls:
        for i in set(c[C_ARGS]) | set(c[C_RECEIVER]):
            fanout[i] += 1
    feeds = [[] for _ in vs]                       # u -> the variables computed from u
    for j, v in enumerate(vs):
        for u in v[FROM]:
            feeds[u].append(j)

    def reaches_out(u: int) -> bool:
        seen, todo = {u}, [u]
        while todo:
            x = todo.pop()
            if fanout[x]:
                return True
            for y in feeds[x]:
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return False
    in_out = sum(reaches_out(u) for u in incoming)
    call_lines = sorted({c[C_LINE] for c in calls})
    bridging = sum(sum(v[USE_LOOP_FIRST] <= ln <= v[LOOP_LAST] for ln in call_lines) >= 2
                   for v in vs)
    at_calls = 0.0
    if call_lines and m["lines"]:
        w = dict(zip(m["lines"], widths(m, HEADLINE)))
        at_calls = float(max(w.get(ln, 0.0) for ln in call_lines))
    return {"in_params": len(params), "in_fields": len(fields), "in_results": len(results),
            "in_all": len(incoming), "max_from": max((len(v[FROM]) for v in vs), default=0),
            "derived": sum(bool(v[FROM]) for v in vs),
            "out_vars": sum(bool(f) for f in fanout), "max_fanout": max(fanout, default=0),
            "in_out": in_out,
            "in_through": sum(1 for i in params | fields if fanout[i] and vs[i][DEFS] <= 1),
            "in_caught": len(incoming) - in_out, "bridging": bridging, "lw_at_calls": at_calls}


def by_unit(doc: dict) -> dict:
    """{(path, name, name_line): method facts}, the first of a repeated key (as the join takes it)."""
    out = {}
    for f in doc.get("files", []):
        if f["level"] == "failed":
            continue
        for m in f["methods"]:
            out.setdefault((f["path"], m["name"], m["name_line"]), m)
    return out


# ------------------------------------------------------------------------------------------------
# the pass
# ------------------------------------------------------------------------------------------------

def java() -> str:
    return os.environ.get("CDS_JAVA") or "java"


def run_pass(root: str, files: list[str], jar: str = pins.MEASURER_JAR) -> dict:
    work = tempfile.mkdtemp(prefix="cds-lw-")
    try:
        lst = os.path.join(work, "files.txt")
        out = os.path.join(work, "out.json.gz")
        with open(lst, "w", encoding="utf-8") as fh:
            fh.write("\n".join(files) + "\n")
        p = subprocess.run([java(), f"-Xmx{pins.MEASURER_HEAP}", "-Xss16m", "-cp", jar, MAIN,
                            "--root", root, "--files", lst, "--out", out],
                           capture_output=True, text=True, timeout=6 * 3600)
        if p.returncode != 0 or not os.path.exists(out):
            raise RuntimeError(f"LiveWidth exited {p.returncode}: {(p.stderr or '')[-2000:]}")
        with gzip.open(out, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _git(cwd: str, *args: str, stdin: str | None = None) -> str:
    p = subprocess.run(["git", "-c", "advice.detachedHead=false", *args], cwd=cwd, input=stdin,
                       capture_output=True, text=True, timeout=3 * 3600)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {p.stderr[-1000:]}")
    return p.stdout


def fetch(url: str, commit: str, files: list[str], dest: str) -> None:
    """The repository at `commit` into dest, only `files` checked out (blobs fetched on demand)."""
    _git(dest, "init", "--quiet")
    _git(dest, "remote", "add", "origin", url)
    _git(dest, "fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", commit)
    _git(dest, "sparse-checkout", "set", "--no-cone", "--stdin",
         stdin="".join("/" + f.replace("\\", "/") + "\n" for f in files))
    _git(dest, "checkout", "--quiet", "FETCH_HEAD")
    head = _git(dest, "rev-parse", "HEAD").strip()
    if not head.startswith(commit) and not commit.startswith(head):
        raise RuntimeError(f"fetched {head}, the record names {commit}")


def source(row: dict, files: list[str], dest: str) -> None:
    if row["set"] == "fontana":
        from concentration_divergence_study import fontana
        members = [os.path.join(pins.PROJECT_ROOT, m) for m in row["archive"].split(";")]
        if "archive:" + fontana.source_sha256(members) != row["commit"]:
            raise RuntimeError(f"{row['archive']} does not match the record's sha256")
        fontana.unpack(members, dest)
    else:
        fetch(row["repo"], row["commit"], files, dest)


def check_units(doc: dict, measurer: dict) -> dict:
    """The pass's units against the record's measurer units: both must be the same set."""
    ours = {(f["path"], m["name"], m["name_line"]) for f in doc["files"] for m in f["methods"]}
    theirs = {(f["path"], m["name"], m["name_line"]) for f in measurer["files"] for m in f["methods"]}
    missing = sorted(map(list, theirs - ours))
    return {"units": len(ours), "measurer_units": len(theirs), "missing": len(missing),
            "extra": len(ours - theirs), "missing_first": missing[:20],
            "failed_methods": sum(m["name"].startswith("(failed)") for f in doc["files"]
                                  for m in f["methods"]),
            "files_failed": sum(f["level"] == "failed" for f in doc["files"])}


def measure_set(set_name: str, limit: int | None = None) -> None:
    results = os.path.join(pins.RESULTS, set_name)
    rows = records.load_rows(results)
    out_dir = os.path.join(OUT, set_name)
    os.makedirs(out_dir, exist_ok=True)
    work_root = os.path.join(out_dir, ".work")
    os.makedirs(work_root, exist_ok=True)
    todo = [r for r in rows if not r.get("error") and not r.get("javaparser_error")]
    done = 0
    for i, r in enumerate(todo, 1):
        path = os.path.join(out_dir, r["key"] + ".json.gz")
        if os.path.exists(path) and records.read_json_gz(path)["facts"].get("livewidth") == SCHEMA:
            continue                    # written by this schema (an older one is measured again)
        rec = records.read_json_gz(records.record_path(results, r["key"]))
        jp = rec.get("javaparser")
        if not jp:
            continue
        files = [f["path"] for f in jp["files"]]
        work = tempfile.mkdtemp(prefix="lw-", dir=work_root)
        try:
            print(f"[{i}/{len(todo)}] {set_name} {r['key']}: {len(files)} files ...", flush=True)
            try:
                source({**r, "set": set_name}, files, work)
                doc = run_pass(work, files)
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                print(f"        FAILED: {e}", flush=True)
                continue
            chk = check_units(doc, jp)
            records.write_json_gz(path, {"kind": "exploratory", "set": set_name, "key": r["key"],
                                         "repo": r.get("repo"), "commit": r.get("commit"),
                                         "harness_commit": pins.harness_commit(),
                                         "check": chk, "facts": doc})
            print(f"        {chk['units']} units, {chk['missing']} of the record's missing, "
                  f"{chk['extra']} extra, {doc['seconds']:.0f}s", flush=True)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        done += 1
        if limit and done >= limit:
            break


# ------------------------------------------------------------------------------------------------
# the fixture: the pass must report exactly these facts, or nothing is measured
# ------------------------------------------------------------------------------------------------

FIXTURE = {"src/a/F.java": """package a;
import java.util.List;
public class F {
    private int count;
    int seq(int a, int b) {
        int x = a + 1;
        int y = x * 2;
        int z = y - b;
        return z;
    }
    int loop(List<String> items, int limit) {
        int sum = 0;
        for (int i = 0; i < limit; i++) {
            String s = items.get(i);
            sum += s.length();
        }
        for (String t : items) { this.count++; }
        int[] arr = new int[3];
        arr[0] = sum;
        Runnable r = () -> { int q = 1; System.out.println(q + count); };
        Object o = new Object() { public String toString() { int inner = 2; return "" + inner; } };
        try { return Math.max(sum, 0); } catch (RuntimeException e) { return e.hashCode(); }
    }
    int pat(Object o, int n) {
        if (o instanceof String str) { n = str.length(); }
        n = n + 1;
        switch (n) { case 1: return count; default: return n; }
    }
    int lit(int n) {
        int k = 0;
        String s = null;
        int unused = -1;
        int w;
        if (n > 0) { k = n; }
        w = k + 1;
        return w + (s == null ? 0 : s.length());
    }
}
"""}
# (method, name line) -> {variable: [kind, first, last, loop_first, loop_last, defs, steps, muts,
# [the variables it is computed from], lit, use_first, use_loop_first, [the lines it is used at],
# [the lines it is defined at], [the lines its object is written into at]]}
EXPECTED = {
    ("seq", 5): {"a": [0, 6, 6, 6, 6, 1, 0, 0, [], 0, 6, 6, [6], [], []],
                 "b": [0, 8, 8, 8, 8, 1, 0, 0, [], 0, 8, 8, [8], [], []],
                 "x": [1, 6, 7, 6, 7, 1, 0, 0, ["a"], 0, 6, 6, [6, 7], [6], []],
                 "y": [1, 7, 8, 7, 8, 1, 0, 0, ["x"], 0, 7, 7, [7, 8], [7], []],
                 "z": [1, 8, 9, 8, 9, 1, 0, 0, ["b", "y"], 0, 8, 8, [8, 9], [8], []]},
    ("loop", 11): {"items": [0, 14, 17, 13, 17, 1, 0, 0, [], 0, 14, 13, [14, 17], [], []],
                   "limit": [0, 13, 13, 13, 16, 1, 0, 0, [], 0, 13, 13, [13], [], []],
                   # sum = 0 at line 12 is a literal declaration: first use at 15, in the loop;
                   # defined at 12 (the initializer) and 15 (+=)
                   "sum": [1, 12, 22, 12, 22, 2, 0, 0, ["s"], 1, 15, 13, [15, 19, 22], [12, 15], []],
                   "i": [1, 13, 14, 13, 14, 2, 1, 0, [], 1, 13, 13, [13, 14], [13], []],
                   "s": [1, 14, 15, 14, 15, 1, 0, 0, ["i", "items"], 0, 14, 14, [14, 15], [14], []],
                   "t": [1, 17, 17, 17, 17, 1, 0, 0, ["items"], 0, 17, 17, [17], [17], []],
                   # arr[0] = sum at 19 is a write into arr, not a definition of it
                   "arr": [1, 18, 19, 18, 19, 1, 0, 1, ["sum"], 0, 18, 18, [18, 19], [18], [19]],
                   "r": [1, 20, 20, 20, 20, 1, 0, 0, ["count", "q"], 0, 20, 20, [20], [20], []],
                   "q": [1, 20, 20, 20, 20, 1, 0, 0, [], 1, 20, 20, [20], [20], []],
                   "o": [1, 21, 21, 21, 21, 1, 0, 0, [], 0, 21, 21, [21], [21], []],
                   "e": [1, 22, 22, 22, 22, 1, 0, 0, [], 0, 22, 22, [22], [22], []],
                   # a field: its prior state has no line; this.count++ at 17 does
                   "count": [2, 17, 20, 17, 20, 2, 1, 0, [], 0, 17, 17, [17, 20], [17], []]},
    ("toString", 21): {"inner": [1, 21, 21, 21, 21, 1, 0, 0, [], 1, 21, 21, [21], [21], []]},
    ("pat", 24): {"o": [0, 25, 25, 25, 25, 1, 0, 0, [], 0, 25, 25, [25], [], []],
                  "n": [0, 25, 27, 25, 27, 3, 0, 0, ["str"], 0, 25, 25, [25, 26, 27], [25, 26], []],
                  "str": [1, 25, 25, 25, 25, 1, 0, 0, ["o"], 0, 25, 25, [25], [25], []],
                  "count": [2, 27, 27, 27, 27, 1, 0, 0, [], 0, 27, 27, [27], [], []]},
    # the literal rule: k = 0, s = null and unused = -1 are declared at 30-32; k is first used
    # at 34 and s at 36, so their use ranges start there, while first keeps the declaration;
    # unused has no use, so its range is its declaration; the initializer still counts as a
    # definition (k: 2 defs, at 30 and 34). w is declared with no value at 33: never a
    # reference, so both starts are its first use at 35, and its one definition is that
    # assignment
    ("lit", 29): {"n": [0, 34, 34, 34, 34, 1, 0, 0, [], 0, 34, 34, [34], [], []],
                  "k": [1, 30, 35, 30, 35, 2, 0, 0, ["n"], 1, 34, 34, [34, 35], [30, 34], []],
                  "s": [1, 31, 36, 31, 36, 1, 0, 0, [], 1, 36, 36, [36], [31], []],
                  "unused": [1, 32, 32, 32, 32, 1, 0, 0, [], 1, 32, 32, [], [32], []],
                  "w": [1, 35, 36, 35, 36, 1, 0, 0, ["k"], 1, 35, 35, [35, 36], [35], []]},
}
# (method, name line) -> [[line, [arguments], [receiver], result]], in the measurer's call order
EXPECTED_CALLS = {
    ("seq", 5): [],
    ("loop", 11): [[14, ["i"], ["items"], "s"], [15, [], ["s"], "sum"], [20, ["count", "q"], [], None],
                   [21, [], [], "o"], [22, ["sum"], [], None], [22, [], ["e"], None]],
    ("toString", 21): [],
    ("pat", 24): [[25, [], ["str"], "n"]],
    ("lit", 29): [[36, [], ["s"], None]],
}
# (method, name line) -> the statement tree [first, last, seq, kind, children]; the loop method
# shows a for body, a for-each body, a lambda's block body and a try with its catch, each a
# sequence inside its statement, and the anonymous class at line 21 left out; the kinds mark
# the loops (7), the try (8), the if (6), the switch (9) and its entries (13), and the returns (1)
EXPECTED_TREE = {
    ("loop", 11): [11, 23, 1, 12, [[12, 12, 0, 0, []],
                                   [13, 16, 0, 7, [[13, 16, 1, 12, [[14, 14, 0, 0, []], [15, 15, 0, 0, []]]]]],
                                   [17, 17, 0, 7, [[17, 17, 1, 12, [[17, 17, 0, 0, []]]]]],
                                   [18, 18, 0, 0, []], [19, 19, 0, 0, []],
                                   [20, 20, 0, 0, [[20, 20, 1, 12, [[20, 20, 0, 0, []], [20, 20, 0, 0, []]]]]],
                                   [21, 21, 0, 0, []],
                                   [22, 22, 0, 8, [[22, 22, 1, 12, [[22, 22, 0, 1, []]]],
                                                   [22, 22, 1, 12, [[22, 22, 0, 1, []]]]]]]],
    ("pat", 24): [24, 28, 1, 12, [[25, 25, 0, 6, [[25, 25, 1, 12, [[25, 25, 0, 0, []]]]]],
                                  [26, 26, 0, 0, []],
                                  [27, 27, 0, 9, [[27, 27, 1, 13, [[27, 27, 0, 1, []]]],
                                                  [27, 27, 1, 13, [[27, 27, 0, 1, []]]]]]]],
    ("lit", 29): [29, 37, 1, 12, [[30, 30, 0, 0, []], [31, 31, 0, 0, []], [32, 32, 0, 0, []],
                                  [33, 33, 0, 0, []],
                                  [34, 34, 0, 6, [[34, 34, 1, 12, [[34, 34, 0, 0, []]]]]],
                                  [35, 35, 0, 0, []], [36, 36, 0, 1, []]]],
}


def fixture_doc(jar: str = pins.MEASURER_JAR) -> dict:
    root = tempfile.mkdtemp(prefix="cds-lw-fixture-")
    try:
        for rel, body in FIXTURE.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write(body)
        return run_pass(root, sorted(FIXTURE), jar)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check(jar: str = pins.MEASURER_JAR) -> list[str]:
    if not os.path.isfile(jar):
        return [f"no measurer jar at {jar}: run ./step1_setup.sh"]
    doc = fixture_doc(jar)
    if doc.get("livewidth") != SCHEMA:
        return [f"the jar writes live-width schema {doc.get('livewidth')}, not {SCHEMA}: rebuild it"]
    got, got_calls = {}, {}
    for f in doc["files"]:
        for m in f["methods"]:
            names = [v[NAME] for v in m["vars"]]
            key = (m["name"], m["name_line"])
            got[key] = {v[NAME]: v[KIND:FROM] + [sorted(names[i] for i in v[FROM])] + v[LIT:]
                        for v in m["vars"]}
            got_calls[key] = [[c[C_LINE], sorted(names[i] for i in c[C_ARGS]),
                               sorted(names[i] for i in c[C_RECEIVER]),
                               names[c[C_RESULT]] if c[C_RESULT] >= 0 else None] for c in m["calls"]]
    problems = [f"live-width fixture {k}: got {got.get(k)}, expected {want}"
                for k, want in EXPECTED.items() if got.get(k) != want]
    problems += [f"live-width fixture calls {k}: got {got_calls.get(k)}, expected {want}"
                 for k, want in EXPECTED_CALLS.items() if got_calls.get(k) != want]
    got_tree = {(m["name"], m["name_line"]): m.get("tree") for f in doc["files"] for m in f["methods"]}
    problems += [f"live-width fixture tree {k}: got {got_tree.get(k)}, expected {want}"
                 for k, want in EXPECTED_TREE.items() if got_tree.get(k) != want]
    extra = set(got) - set(EXPECTED)
    if extra:
        problems.append(f"live-width fixture: unexpected units {sorted(extra)}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sets", nargs="+", default=["mlcq", "seed3", "fontana"])
    ap.add_argument("--limit", type=int, default=None, help="stop after this many repositories per set")
    ap.add_argument("--check", action="store_true", help="check the pass on its fixture and stop")
    a = ap.parse_args(argv)
    problems = check()
    if problems:
        print("LIVE-WIDTH FIXTURE FAILED:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 1
    print("live-width pass measures its fixture exactly.", flush=True)
    if a.check:
        return 0
    for s in a.sets:
        measure_set(s, a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
