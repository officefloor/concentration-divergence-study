#!/usr/bin/env python3
"""EXPLORATORY, POST HOC. Split cost: what it takes to bring a method under the cap (SPLIT.md).

Written after step 13 was read (PLAN.md, Amendments, 10): nothing here is confirmatory. It
reads one method's live-width facts (scripts/livewidth.py, schema 3: the variables' reference,
definition and write lines, the loops, the calls, and the statement tree with each node's kind)
and finds the cheapest way to cut the method into pieces that each end at or under the cap.

A piece is a contiguous run of one sequence's statements (a block, a switch entry, a lambda's
block body); whole statements move. Its seam is what crosses its boundary: the locals and
parameters used inside and defined before (inputs: parameters of the new method) and those
written inside and read after, or read earlier in a loop the run sits in (outputs: the return
value, and Java allows one). A declaration with no value or a literal one, before the run and
used only inside it, crosses nothing: the tool moves it. Fields are not interface; they bind
the piece to the class instead (free / bound by reads / locked by a write or a call to the
class's own methods).

The search is a dynamic program over each sequence's statements, bottom up: keep a statement
(with any of the reductions its inner sequences allow) or close an extracted run ending at it.
A single statement longer than the cap is reduced from inside first, and may then be extracted
whole. Among the segmentations whose remainder and every piece end at or under the target, the
one with the smallest worst seam wins, then the fewest pieces, then the smallest total cost.
Every number is a Params field, with SPLIT.md's defaults.

    width(S) = max over pieces of (inputs + outputs)
    cost(S)  = sum over pieces of (inputs + output_weight * outputs + piece_cost)

Known approximations (SPLIT.md, Facts needed): a reference after the run is taken as a read,
so a variable merely overwritten later still counts as an output; calls to the class's own
methods are those resolving to the method's own file (the measurer record's resolution), so a
static method of the same class reads as binding when it is not.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, asdict, field

import livewidth as lw

# the width and cost a method gets when no segmentation reaches the cap: larger than any seam
# the limits allow, so an absolute cutoff on width flags it, and a ranking puts it last
INFEASIBLE_WIDTH = 50.0


@dataclass(frozen=True)
class Params:
    trigger: int = 26          # a method of this many code lines or more is split
    target: int = 25           # every piece, and the remainder, must end at this many or fewer
    min_piece: int = 5         # the smallest run worth extracting, in code lines
    min_saving: int = 3        # lines a cut must remove: the run's length less its call line
    max_inputs: int = 3        # parameters a piece may need; -1 for no limit
    max_outputs: int = 1       # values a piece may return (Java: one)
    output_weight: int = 2     # a return value against a parameter, in the cost
    piece_cost: int = 1        # a name and a call site, per piece
    trailing_return: bool = True   # a run may end in a return; any other return leaves it
    structural_only: bool = False  # pieces are whole if, loop, try and switch statements only
    lock_on_any_field: bool = False  # a field read locks a piece too (default: a write, or an own call)


DEFAULT = Params()
STRUCTURAL = Params(structural_only=True)
UNLIMITED = Params(max_inputs=-1)      # whether an infeasible method fails on inputs or on outputs


@dataclass(frozen=True)
class Seam:
    lo: int
    hi: int
    inputs: tuple
    outputs: tuple
    moved: tuple
    fields_read: tuple
    fields_written: tuple
    own_calls: int

    @property
    def width(self) -> int:
        return len(self.inputs) + len(self.outputs)

    def cost(self, p: Params) -> int:
        return len(self.inputs) + p.output_weight * len(self.outputs) + p.piece_cost

    def feasible(self, p: Params) -> bool:
        return len(self.outputs) <= p.max_outputs and (p.max_inputs < 0 or len(self.inputs) <= p.max_inputs)

    def binding(self, p: Params) -> str:
        if self.fields_written or self.own_calls or (p.lock_on_any_field and self.fields_read):
            return "locked"
        return "bound" if self.fields_read else "free"


@dataclass(frozen=True)
class Option:
    """One way of handling a stretch of statements: lines left in place (extracted pieces
    replaced by one call line each), the worst seam, the total cost, the pieces, the cuts."""
    rem: int
    width: int = 0
    cost: int = 0
    pieces: int = 0
    cuts: tuple = ()

    def key(self):
        return (self.width, self.pieces, self.cost)


@dataclass
class Result:
    applicable: bool           # the method is at or over the trigger
    feasible: bool             # some segmentation reaches the target
    width: float               # the worst seam of the best segmentation (INFEASIBLE_WIDTH if none)
    cost: float
    pieces: int
    interface: int             # the sum of the seams: the sinews the split creates
    remainder: int             # code lines left in the method
    cuts: list                 # [(lo, hi, inputs, outputs, binding)]
    locked: int = 0            # pieces an instance method must keep
    bound: int = 0             # pieces free if their field reads are passed in
    free: int = 0
    remainder_locked: bool = False
    params: dict = field(default_factory=dict)


# ------------------------------------------------------------------------------------------------
# the method's facts, indexed for the many seams a search asks for
# ------------------------------------------------------------------------------------------------

def tree_lines(node: list) -> set:
    """The code lines a statement tree covers: a leaf statement's whole span, a compound
    statement's span less its blocks (its header and closing lines), a block's first and last
    lines (its braces) and its statements. Blank and comment lines between statements fall
    outside every span, so this tracks the measurer's nloc, which the facts' node lines (one per
    node's first line) do not."""
    out = set()
    if node[lw.S_SEQ]:
        out.update((node[lw.S_START], node[lw.S_END]))
        for k in node[lw.S_KIDS]:
            out |= tree_lines(k)
        return out
    out.update(range(node[lw.S_START], node[lw.S_END] + 1))
    for k in node[lw.S_KIDS]:
        if k[lw.S_SEQ]:
            out.difference_update(range(k[lw.S_START], k[lw.S_END] + 1))
    for k in node[lw.S_KIDS]:
        out |= tree_lines(k)
    return out


class Method:
    def __init__(self, m: dict, own_call_lines=()):
        self.tree = m["tree"]
        code = tree_lines(self.tree)
        first = m.get("decl_line", m.get("name_line", self.tree[lw.S_START]))
        code.update(range(first, self.tree[lw.S_START] + 1))                                 # the signature
        self.code = sorted(code)
        self.loops = [tuple(x) for x in m.get("loops", [])]
        self.own_calls = sorted(own_call_lines)
        self.vars = []
        for v in m["vars"]:
            refs = sorted(v[lw.REFS])
            defs = sorted(v[lw.DEF_LINES])
            muts = sorted(v[lw.MUT_LINES])
            decl = None
            if v[lw.LIT] and v[lw.FIRST] in defs and v[lw.FIRST] not in refs:
                decl = v[lw.FIRST]       # a literal initializer: a definition, not a use
            touches = sorted(set(refs) | set(defs) | set(muts))
            self.vars.append((v[lw.NAME], v[lw.KIND], refs, defs, muts, touches, decl))
        self._seams: dict = {}

    def lines(self, lo: int, hi: int) -> int:
        return bisect_right(self.code, hi) - bisect_left(self.code, lo)

    def seam(self, lo: int, hi: int) -> Seam:
        s = self._seams.get((lo, hi))
        if s is None:
            s = self._seams[(lo, hi)] = self._seam(lo, hi)
        return s

    def _seam(self, lo: int, hi: int) -> Seam:
        inputs, outputs, moved, fread, fwrit = [], [], [], [], []
        enclosing = [(a, b) for a, b in self.loops if a < lo and hi <= b]
        for name, kind, refs, defs, muts, touches, decl in self.vars:
            if kind == lw.FIELD:
                if _any(refs, lo, hi) or _any(defs, lo, hi) or _any(muts, lo, hi):
                    if _any(defs, lo, hi) or _any(muts, lo, hi):
                        fwrit.append(name)
                    else:
                        fread.append(name)
                continue
            if not _any_but(touches, lo, hi, decl):
                continue
            before = _any_below(refs, lo) or _any_below(muts, lo) or _any_below_but(defs, lo, decl)
            after = _any_above(touches, hi)
            written = _any(defs, lo, hi)
            if kind == lw.PARAM or before:
                inputs.append(name)
            back_edge = written and any(_any(refs, a, lo - 1) for a, _ in enclosing)
            if written and (after or back_edge):
                outputs.append(name)
            elif decl is not None and decl < lo and not before and not after:
                moved.append(name)
        own = bisect_right(self.own_calls, hi) - bisect_left(self.own_calls, lo)
        return Seam(lo, hi, tuple(inputs), tuple(outputs), tuple(moved), tuple(fread), tuple(fwrit), own)


def _any(xs: list, lo: int, hi: int) -> bool:
    i = bisect_left(xs, lo)
    return i < len(xs) and xs[i] <= hi


def _any_but(xs: list, lo: int, hi: int, skip) -> bool:
    i = bisect_left(xs, lo)
    while i < len(xs) and xs[i] <= hi:
        if xs[i] != skip:
            return True
        i += 1
    return False


def _any_below(xs: list, lo: int) -> bool:
    return bool(xs) and xs[0] < lo


def _any_below_but(xs: list, lo: int, skip) -> bool:
    for x in xs:
        if x >= lo:
            return False
        if x != skip:
            return True
    return False


def _any_above(xs: list, hi: int) -> bool:
    return bool(xs) and xs[-1] > hi


# ------------------------------------------------------------------------------------------------
# the jump rule
# ------------------------------------------------------------------------------------------------

def _jumps(node: list, in_loop: bool, in_switch: bool, in_lambda: bool, acc: list) -> None:
    """acc[0]: returns that leave the run; acc[1]: True if a break, continue or yield leaves it.
    A block directly under an expression or declaration is a lambda's body: nothing in it leaves."""
    k = node[lw.S_KIND]
    if in_lambda:
        return
    if k == lw.K_RETURN:
        acc[0] += 1
    elif k == lw.K_BREAK and not (in_loop or in_switch):
        acc[1] = True
    elif k == lw.K_CONTINUE and not in_loop:
        acc[1] = True
    elif k == lw.K_YIELD and not in_switch:
        acc[1] = True
    loop = in_loop or k == lw.K_LOOP
    switch = in_switch or k == lw.K_SWITCH
    for c in node[lw.S_KIDS]:
        _jumps(c, loop, switch, k == lw.K_OTHER and c[lw.S_KIND] == lw.K_BLOCK, acc)


def jumps_ok(run: list, p: Params) -> bool:
    acc = [0, False]
    for node in run:
        _jumps(node, False, False, False, acc)
    if acc[1]:
        return False
    if acc[0] == 0:
        return True
    return p.trailing_return and acc[0] == 1 and run[-1][lw.S_KIND] == lw.K_RETURN


# ------------------------------------------------------------------------------------------------
# the search
# ------------------------------------------------------------------------------------------------

def _push(states: dict, o: Option) -> None:
    cur = states.get(o.rem)
    if cur is None or o.key() < cur.key():
        states[o.rem] = o


def _pareto(options) -> list:
    """Drop every option another beats on all of rem, width, pieces and cost."""
    opts = sorted(options, key=lambda o: (o.rem, o.width, o.pieces, o.cost))
    keep = []
    for o in opts:
        if not any(k.rem <= o.rem and k.width <= o.width and k.pieces <= o.pieces and k.cost <= o.cost
                   for k in keep):
            keep.append(o)
    return keep


def _combine(a: Option, b: Option, extra_rem: int = 0) -> Option:
    return Option(a.rem + b.rem + extra_rem, max(a.width, b.width), a.cost + b.cost, a.pieces + b.pieces,
                  a.cuts + b.cuts)


def solve_stmt(node: list, M: Method, p: Params) -> list:
    """The options for one statement: as it is, or reduced by extractions inside it."""
    total = M.lines(node[lw.S_START], node[lw.S_END])
    fronts = []
    for c in node[lw.S_KIDS]:
        f = solve_seq(c, M, p) if c[lw.S_SEQ] else solve_stmt(c, M, p)
        # a child's saving is read against what its own search covered: its statements' lines
        # for a sequence (its braces stay), its whole span for a statement
        base = covered(c, M)
        fronts.append([Option(o.rem - base, o.width, o.cost, o.pieces, o.cuts) for o in f])
    opts = [Option(total)]
    for f in fronts:
        opts = _pareto(_combine(o, d) for o in opts for d in f)
    return opts


def covered(node: list, M: Method) -> int:
    """The lines a node's own search accounts for: a sequence's statements, a statement's span."""
    if node[lw.S_SEQ]:
        return sum(M.lines(k[lw.S_START], k[lw.S_END]) for k in node[lw.S_KIDS])
    return M.lines(node[lw.S_START], node[lw.S_END])


def solve_seq(node: list, M: Method, p: Params) -> list:
    """The Pareto front of ways to handle a sequence: lines left, worst seam, cost, pieces."""
    kids = node[lw.S_KIDS]
    n = len(kids)
    opts = [solve_stmt(k, M, p) for k in kids]
    at = [dict() for _ in range(n + 1)]
    at[0][0] = Option(0)
    for i in range(n):
        new = at[i + 1]
        for st in at[i].values():
            for o in opts[i]:
                _push(new, _combine(st, o))
        kid = kids[i]
        structural = kid[lw.S_KIND] in lw.STRUCTURAL
        if not p.structural_only or structural:
            # a single statement, as it is or reduced from inside, then extracted whole
            if jumps_ok([kid], p):
                sm = M.seam(kid[lw.S_START], kid[lw.S_END])
                if sm.feasible(p):
                    for o in opts[i]:
                        if p.min_piece <= o.rem <= p.target and o.rem - 1 >= p.min_saving:
                            cut = (sm.lo, sm.hi, len(sm.inputs), len(sm.outputs), sm.binding(p))
                            for st in at[i].values():
                                _push(new, Option(st.rem + 1, max(st.width, o.width, sm.width),
                                                  st.cost + o.cost + sm.cost(p), st.pieces + o.pieces + 1,
                                                  st.cuts + o.cuts + (cut,)))
        if p.structural_only:
            continue
        # a run of several statements, as they are
        for j in range(i - 1, -1, -1):
            L = M.lines(kids[j][lw.S_START], kid[lw.S_END])
            if L > p.target:
                break
            if L < p.min_piece or L - 1 < p.min_saving:
                continue
            run = kids[j:i + 1]
            if not jumps_ok(run, p):
                continue
            sm = M.seam(kids[j][lw.S_START], kid[lw.S_END])
            if not sm.feasible(p):
                continue
            cut = (sm.lo, sm.hi, len(sm.inputs), len(sm.outputs), sm.binding(p))
            for st in at[j].values():
                _push(new, Option(st.rem + 1, max(st.width, sm.width), st.cost + sm.cost(p), st.pieces + 1,
                                  st.cuts + (cut,)))
    return _pareto(at[n].values())


def split(m: dict, own_call_lines=(), p: Params = DEFAULT, nloc: int | None = None) -> Result:
    """The best segmentation of one method's facts (scripts/livewidth.py, by_unit), or why none.
    `nloc`, when given, is the method's length as the oracle counts it (the measurer record):
    the trigger and the target are read on it, with the lines a cut saves taken from the facts."""
    M = Method(m, own_call_lines)
    total = len(M.code) if nloc is None else int(nloc)
    if total < p.trigger:
        return Result(False, True, 0.0, 0.0, 0, 0, total, [], params=asdict(p))
    root = M.tree
    # what the search removes is read against the statements it sees; the lines no statement
    # covers (the signature, a closing brace) stay whatever is cut
    kids_total = covered(root, M)
    front = solve_seq(root, M, p)
    ok = [o for o in front if total - (kids_total - o.rem) <= p.target]
    if not ok:
        return Result(True, False, INFEASIBLE_WIDTH, INFEASIBLE_WIDTH, 0, int(INFEASIBLE_WIDTH), total, [],
                      params=asdict(p))
    best = min(ok, key=lambda o: o.key())
    cuts = sorted(best.cuts)
    r = Result(True, True, float(best.width), float(best.cost), best.pieces,
               sum(c[2] + c[3] for c in cuts), total - (kids_total - best.rem), [list(c) for c in cuts],
               params=asdict(p))
    for c in cuts:
        if c[4] == "locked":
            r.locked += 1
        elif c[4] == "bound":
            r.bound += 1
        else:
            r.free += 1
    r.remainder_locked = _remainder_locked(M, cuts, p)
    return r


def _remainder_locked(M: Method, cuts: list, p: Params) -> bool:
    """Whether what stays behind writes a field or calls the class's own methods outside the cuts."""
    def outside(line: int) -> bool:
        return not any(lo <= line <= hi for lo, hi, *_ in cuts)
    if any(outside(x) for x in M.own_calls):
        return True
    for name, kind, refs, defs, muts, touches, decl in M.vars:
        if kind != lw.FIELD:
            continue
        if any(outside(x) for x in defs) or any(outside(x) for x in muts):
            return True
        if p.lock_on_any_field and any(outside(x) for x in refs):
            return True
    return False
