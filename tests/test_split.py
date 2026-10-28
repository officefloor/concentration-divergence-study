"""The split cost (scripts/split.py) on small synthetic facts: the seam's roles, the jump rule,
the binding, and the search (post hoc, SPLIT.md)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import livewidth as lw  # noqa: E402
import split as sp  # noqa: E402


def V(name, kind, refs, defs=(), muts=(), lit=0, decl=None):
    """A variable's facts as LiveWidth.java writes them (schema 3); only the fields the split
    reads are meaningful here. `decl` is the line of a literal declaration (then lit must be 1)."""
    refs, defs, muts = sorted(refs), sorted(defs), sorted(muts)
    first = decl if decl is not None else (min(refs + defs) if refs or defs else 0)
    last = max(refs + defs + muts) if refs or defs or muts else first
    use_first = min(refs) if refs else first
    return [name, kind, first, last, first, last, max(1, len(defs)), 0, len(muts), [], lit, use_first,
            use_first, refs, defs, muts]


def seq(start, end, *kids, kind=lw.K_BLOCK):
    return [start, end, 1, kind, list(kids)]


def stmt(start, end=None, kind=lw.K_OTHER, *kids):
    return [start, start if end is None else end, 0, kind, list(kids)]


def method(tree, vars_, loops=()):
    lines = sorted(set(range(tree[lw.S_START], tree[lw.S_END] + 1)))
    return {"name": "m", "name_line": tree[lw.S_START], "lines": lines, "vars": vars_, "tree": tree,
            "loops": [list(x) for x in loops]}


def chain(n, start=2):
    """x_i = f(x_{i-1}) on each line: every variable live two lines, so any run's seam is one in
    and one out."""
    vars_ = []
    for i in range(start, start + n):
        vars_.append(V(f"x{i}", lw.LOCAL, refs=[i, i + 1], defs=[i]))
    return vars_


def test_a_sequential_method_splits_with_a_narrow_seam():
    body = seq(1, 62, *[stmt(i) for i in range(2, 62)])
    r = sp.split(method(body, chain(60)))
    assert r.applicable and r.feasible
    assert r.width == 2 and r.pieces == 2 and r.remainder <= 25
    assert all(hi - lo + 1 <= 25 for lo, hi, *_ in r.cuts)
    # each piece hands one value on; the first piece starts the chain, so it takes nothing in
    assert [(ins, outs) for _, _, ins, outs, _ in r.cuts] == [(0, 1), (1, 1)]
    assert r.cost == (0 + 2 + 1) + (1 + 2 + 1)


def test_an_interwoven_method_has_a_wide_seam_everywhere_and_fails_the_input_limit():
    body = seq(1, 62, *[stmt(i) for i in range(2, 62)])
    # five values set at line 2 and read on every later line: any run needs all five
    vars_ = [V(f"v{k}", lw.LOCAL, refs=list(range(2, 62)), defs=[2]) for k in range(5)]
    r = sp.split(method(body, vars_))
    assert r.applicable and not r.feasible and r.width == sp.INFEASIBLE_WIDTH
    r = sp.split(method(body, vars_), p=sp.Params(max_inputs=-1))
    assert r.feasible and r.width == 5


def test_two_results_cannot_be_returned():
    body = seq(1, 73, *[stmt(i) for i in range(2, 73)])
    # lines 2-40 keep setting a and b, both read at 70: any run over the writes has two outputs,
    # and the runs that avoid them cannot bring 72 lines under the cap
    vars_ = [V("a", lw.LOCAL, refs=list(range(2, 41)) + [70], defs=list(range(2, 41))),
             V("b", lw.LOCAL, refs=list(range(2, 41)) + [70], defs=list(range(2, 41)))]
    r = sp.split(method(body, vars_))
    assert r.applicable and not r.feasible
    M = sp.Method(method(body, vars_))
    assert M.seam(10, 30).outputs == ("a", "b")


def test_the_seam_roles_input_output_internal_and_the_loop_back_edge():
    M = sp.Method({"lines": list(range(1, 50)), "tree": seq(1, 49), "loops": [[10, 40]], "vars": [
        V("p", lw.PARAM, refs=[20]),                       # a parameter read inside: input
        V("x", lw.LOCAL, refs=[5, 20], defs=[5]),           # set before, read inside: input
        V("y", lw.LOCAL, refs=[20, 45], defs=[20]),         # set inside, read after: output
        V("z", lw.LOCAL, refs=[18, 22], defs=[18]),         # inside only: internal
        V("acc", lw.LOCAL, refs=[12, 25], defs=[8, 25]),    # written inside, read earlier in the loop
    ]})
    s = M.seam(15, 30)
    assert s.inputs == ("p", "x", "acc")        # acc was set at 8, before the run
    assert s.outputs == ("y", "acc")            # y read after; acc read at 12, the back edge
    assert s.moved == ()
    assert s.width == 5
    assert s.cost(sp.DEFAULT) == 3 + 2 * 2 + 1


def test_a_literal_declaration_before_the_run_is_moved_not_passed():
    M = sp.Method({"lines": list(range(1, 50)), "tree": seq(1, 49), "loops": [], "vars": [
        V("count", lw.LOCAL, refs=[20, 21], defs=[3, 20], lit=1, decl=3),     # int count = 0 at 3
        V("name", lw.LOCAL, refs=[20, 40], defs=[3, 20], lit=1, decl=3),      # ... but read after
        V("seen", lw.LOCAL, refs=[20, 21], defs=[20], lit=1),                 # int seen; no value
    ]})
    s = M.seam(15, 30)
    assert s.inputs == ()
    assert s.moved == ("count",)
    assert s.outputs == ("name",)


def test_the_jump_rule():
    loop_with_break = stmt(10, 20, lw.K_LOOP, seq(10, 20, stmt(12, kind=lw.K_BREAK)))
    assert sp.jumps_ok([loop_with_break], sp.DEFAULT)
    assert not sp.jumps_ok([stmt(12, kind=lw.K_BREAK)], sp.DEFAULT)
    assert not sp.jumps_ok([stmt(12, kind=lw.K_CONTINUE)], sp.DEFAULT)
    assert sp.jumps_ok([stmt(12, kind=lw.K_THROW)], sp.DEFAULT)
    assert sp.jumps_ok([stmt(12), stmt(13, kind=lw.K_RETURN)], sp.DEFAULT)         # trailing
    assert not sp.jumps_ok([stmt(12, kind=lw.K_RETURN), stmt(13)], sp.DEFAULT)     # not trailing
    assert not sp.jumps_ok([stmt(12), stmt(13, kind=lw.K_RETURN)], sp.Params(trailing_return=False))
    if_with_return = stmt(12, 14, lw.K_IF, seq(12, 14, stmt(13, kind=lw.K_RETURN)))
    assert not sp.jumps_ok([if_with_return], sp.DEFAULT)                            # leaves from inside
    lambda_body = stmt(12, 14, lw.K_OTHER, seq(12, 14, stmt(13, kind=lw.K_RETURN)))
    assert sp.jumps_ok([lambda_body], sp.DEFAULT)                                   # a lambda's return


def test_the_binding_free_bound_and_locked():
    vars_ = [V("f", lw.FIELD, refs=[20]), V("g", lw.FIELD, refs=[40], defs=[40]),
             V("h", lw.FIELD, refs=[45], muts=[45])]
    M = sp.Method({"lines": list(range(1, 60)), "tree": seq(1, 59), "loops": [], "vars": vars_},
                  own_call_lines=[50])
    assert M.seam(15, 25).binding(sp.DEFAULT) == "bound"        # reads f
    assert M.seam(15, 25).binding(sp.Params(lock_on_any_field=True)) == "locked"
    assert M.seam(35, 42).binding(sp.DEFAULT) == "locked"       # writes g
    assert M.seam(43, 47).binding(sp.DEFAULT) == "locked"       # writes into h
    assert M.seam(48, 55).binding(sp.DEFAULT) == "locked"       # calls the class's own method
    assert M.seam(2, 10).binding(sp.DEFAULT) == "free"


def test_a_method_under_the_trigger_is_not_split():
    body = seq(1, 20, *[stmt(i) for i in range(2, 20)])
    r = sp.split(method(body, chain(18)))
    assert not r.applicable and r.width == 0 and r.pieces == 0


def test_a_loop_longer_than_the_cap_is_cut_from_inside():
    inner = [stmt(i) for i in range(6, 50)]
    loop = stmt(5, 50, lw.K_LOOP, seq(5, 50, *inner))
    body = seq(1, 55, stmt(2), stmt(3), stmt(4), loop, stmt(51), stmt(52), stmt(53))
    r = sp.split(method(body, chain(44, start=6), loops=[(5, 50)]))
    assert r.feasible and r.remainder <= 25
    # a piece is cut from inside the loop, and the shortened loop is then extracted whole: the
    # outer cut spans 46 lines but keeps 46 - 25 + 1 = 22
    assert [(lo, hi) for lo, hi, *_ in r.cuts] == [(5, 50), (6, 30)]
    assert r.pieces == 2 and r.width == 1


def test_the_structural_variant_moves_whole_statements_only():
    arm = [stmt(i) for i in range(11, 31)]
    cond = stmt(10, 31, lw.K_IF, seq(10, 31, *arm))
    body = seq(1, 45, *[stmt(i) for i in range(2, 10)], cond, *[stmt(i) for i in range(32, 45)])
    vars_ = chain(8) + chain(20, start=11) + chain(13, start=32)
    r = sp.split(method(body, vars_), p=sp.STRUCTURAL)
    # only the if can move, and moving it whole (22 lines) leaves 24
    assert r.feasible and [(lo, hi) for lo, hi, *_ in r.cuts] == [(10, 31)]
    free = sp.split(method(body, vars_))
    assert free.feasible and free.width <= r.width
    # an if whose arm is over the cap cannot be cut inside under the structural variant
    arm = [stmt(i) for i in range(11, 40)]
    cond = stmt(10, 40, lw.K_IF, seq(10, 40, *arm))
    body = seq(1, 45, *[stmt(i) for i in range(2, 10)], cond, *[stmt(i) for i in range(41, 45)])
    vars_ = chain(8) + chain(29, start=11) + chain(4, start=41)
    assert not sp.split(method(body, vars_), p=sp.STRUCTURAL).feasible
    assert sp.split(method(body, vars_)).feasible


def test_the_remainder_binding_reads_what_stays():
    body = seq(1, 62, *[stmt(i) for i in range(2, 62)])
    vars_ = chain(60) + [V("state", lw.FIELD, refs=[2], defs=[2])]
    r = sp.split(method(body, vars_))
    assert r.feasible
    inside = any(lo <= 2 <= hi for lo, hi, *_ in r.cuts)
    assert r.remainder_locked == (not inside)
    assert r.locked + r.bound + r.free == r.pieces
