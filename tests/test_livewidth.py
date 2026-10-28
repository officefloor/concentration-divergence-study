"""The live-width facts on the pass's fixture, and the widths computed from them (post hoc)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import livewidth as lw  # noqa: E402

from concentration_divergence_study import pins  # noqa: E402


def _method(vars_, lines, name_line=1):
    return {"name": "m", "name_line": name_line, "lines": lines, "vars": vars_}


def _v(name, kind, first, last, loop_first=None, loop_last=None, defs=1, steps=0, muts=0, frm=(),
       lit=0, use_first=None, use_loop_first=None, refs=(), def_lines=(), mut_lines=()):
    """A variable's facts as LiveWidth.java writes them; by default not a literal declaration, so
    the use range is the range."""
    loop_first = first if loop_first is None else loop_first
    use_first = first if use_first is None else use_first
    return [name, kind, first, last, loop_first, last if loop_last is None else loop_last,
            defs, steps, muts, list(frm), lit, use_first,
            loop_first if use_loop_first is None else use_loop_first, list(refs),
            list(def_lines), list(mut_lines)]


def test_a_sequence_of_short_lived_variables_stays_narrow_however_long():
    # x1 = ..; x2 = f(x1); ... each live two lines: width 2 at most, at any length
    vars_ = [_v(f"x{i}", lw.LOCAL, i, i + 1) for i in range(2, 60)]
    s = lw.summary(_method(vars_, list(range(1, 62))), ("text", "unit", "locals", "use"))
    assert s["max"] == 2
    assert s["over4"] == 0


def test_overlapping_variables_add_and_the_peak_is_the_widest_line():
    vars_ = [_v("a", lw.PARAM, 2, 9), _v("b", lw.LOCAL, 3, 5), _v("c", lw.LOCAL, 4, 4)]
    m = _method(vars_, [1, 2, 3, 4, 5, 9])
    s = lw.summary(m, ("text", "unit", "locals", "use"))
    assert s["max"] == 3 and s["peak_line"] == 4
    assert list(lw.widths(m, ("text", "unit", "locals", "use"))) == [0, 1, 2, 3, 2, 1]


def test_weights_set_once_is_one_a_stepper_is_one_a_gatherer_is_more():
    once = _v("x", lw.LOCAL, 1, 1)
    stepper = _v("i", lw.LOCAL, 1, 1, defs=2, steps=1)
    gatherer = _v("sum", lw.LOCAL, 1, 1, defs=4)
    filled = _v("arr", lw.LOCAL, 1, 1, muts=2)
    assert [lw.weight(v, "unit") for v in (once, stepper, gatherer, filled)] == [1, 1, 1, 1]
    assert [lw.weight(v, "assign") for v in (once, stepper, gatherer, filled)] == [1, 2, 4, 3]
    assert [lw.weight(v, "role") for v in (once, stepper, gatherer, filled)] == [1, 1, 4, 3]


def test_loop_flow_and_signature_start_widen_the_range():
    p = _v("p", lw.PARAM, 8, 8, loop_first=5, loop_last=10)
    m = _method([p, _v("q", lw.LOCAL, 6, 6)], [1, 5, 6, 8, 10], name_line=1)
    assert lw.summary(m, ("text", "unit", "locals", "use"))["max"] == 1
    assert lw.summary(m, ("loop", "unit", "locals", "use"))["max"] == 2       # p live at line 6
    assert list(lw.widths(m, ("text", "unit", "locals", "sig"))) == [1, 1, 2, 1, 0]


def test_a_literal_declaration_starts_at_its_first_use_unless_read_from_the_declaration():
    # int k = 0 at line 2, first used at 10 (in no loop); x live 3..5 in between
    k = _v("k", lw.LOCAL, 2, 11, lit=1, use_first=10, refs=[10, 11])
    m = _method([k, _v("x", lw.LOCAL, 3, 5)], [1, 2, 3, 4, 5, 10, 11])
    assert list(lw.widths(m, ("text", "unit", "locals", "use"))) == [0, 0, 1, 1, 1, 1, 1]
    assert list(lw.widths(m, ("text", "unit", "locals", "decl"))) == [0, 1, 2, 2, 2, 1, 1]
    # declared at 2, first used at 8 inside a loop over lines 6..9: live over the loop from 6
    k = _v("k", lw.LOCAL, 2, 9, loop_first=2, loop_last=9, lit=1, use_first=8, use_loop_first=6,
           refs=[8])
    m = _method([k], [1, 2, 6, 7, 8, 9])
    assert list(lw.widths(m, ("loop", "unit", "locals", "use"))) == [0, 0, 1, 1, 1, 1]
    assert list(lw.widths(m, ("text", "unit", "locals", "use"))) == [0, 0, 0, 0, 1, 1]
    assert list(lw.widths(m, ("loop", "unit", "locals", "decl"))) == [0, 1, 1, 1, 1, 1]


def test_fields_count_only_in_the_all_scope():
    m = _method([_v("f", lw.FIELD, 1, 3), _v("x", lw.LOCAL, 2, 3)], [1, 2, 3])
    assert lw.summary(m, ("text", "unit", "locals", "use"))["max"] == 1
    assert lw.summary(m, ("text", "unit", "all", "use"))["max"] == 2


def test_counts_ignore_when_each_variable_is_live():
    # the long sequence: 58 variables, never more than 2 at once
    seq = _method([_v(f"x{i}", lw.LOCAL, i, i + 1) for i in range(2, 60)], list(range(1, 62)))
    assert lw.counts(seq)["all"] == 58
    m = _method([_v("p", lw.PARAM, 1, 1), _v("i", lw.LOCAL, 1, 1, defs=2, steps=1),
                 _v("sum", lw.LOCAL, 1, 1, defs=3), _v("f", lw.FIELD, 1, 1, defs=2)], [1])
    assert lw.counts(m) == {"all": 4, "locals": 3, "params": 1, "fields": 1, "reassigned": 2,
                            "weighted": 7.0}


def _f(name, kind, first, last, frm=(), defs=1):
    return _v(name, kind, first, last, defs=defs, frm=frm)


def test_flow_traces_what_enters_to_the_internal_calls_it_reaches():
    # 0 p (param) -> 2 x = p + 1 -> call g(x) at line 3, internal
    # 1 q (param), used only locally: caught
    # 3 f (field) passed as it came to h(f) at line 4, internal: a pipe strand
    # 4 r = g(x) holds an internal call's result; k(r) at line 5 resolves to the JDK
    vars_ = [_f("p", lw.PARAM, 2, 2), _f("q", lw.PARAM, 2, 2), _f("x", lw.LOCAL, 2, 3, [0]),
             _f("f", lw.FIELD, 4, 4), _f("r", lw.LOCAL, 3, 5, [2])]
    calls = [[3, [2], [], 4], [4, [3], [], -1], [5, [4], [], -1]]
    m = _method(vars_, [1, 2, 3, 4, 5]) | {"calls": calls}
    fl = lw.flow(m, [True, True, False])
    assert fl["in_params"] == 2 and fl["in_fields"] == 1 and fl["in_results"] == 1
    assert fl["in_all"] == 4
    assert fl["in_out"] == 2                 # p (through x) and f; q and r reach no internal call
    assert fl["in_caught"] == 2
    assert fl["in_through"] == 1             # f
    assert fl["out_vars"] == 2 and fl["max_fanout"] == 1
    assert fl["max_from"] == 1 and fl["derived"] == 2
    assert fl["bridging"] == 1               # r is live at lines 3 and 4, both internal calls
    # with every call internal, r reaches k(r) too
    assert lw.flow(m, [True, True, True])["in_out"] == 3


def test_sequences_lists_each_block_as_the_ranges_of_its_statements():
    # body { a; if (..) { b; c; } d; } with the if's arm a nested block
    tree = [1, 9, 1, lw.K_BLOCK, [[2, 2, 0, lw.K_OTHER, []],
                                  [3, 6, 0, lw.K_IF, [[3, 6, 1, lw.K_BLOCK, [[4, 4, 0, lw.K_OTHER, []],
                                                                            [5, 5, 0, lw.K_RETURN, []]]]]],
                                  [7, 7, 0, lw.K_OTHER, []]]]
    assert lw.sequences(tree) == [[(2, 2), (3, 6), (7, 7)], [(4, 4), (5, 5)]]
    assert lw.sequences([1, 2, 1, lw.K_BLOCK, []]) == [[]]
    assert lw.K_RETURN in lw.JUMPS and lw.K_IF in lw.STRUCTURAL and lw.K_OTHER not in lw.JUMPS


def test_an_empty_method_is_zero():
    s = lw.summary(_method([], []), lw.HEADLINE)
    assert s["max"] == 0 and s["peak_line"] is None


def test_every_variant_is_labelled_once():
    labels = [lw.label(v) for v in lw.variants()]
    assert len(labels) == len(set(labels)) == 14
    assert lw.label(lw.HEADLINE) == "[loop,role,all]"
    assert "[loop,role,all,decl]" in labels and "[loop,role,all,sig]" in labels


@pytest.mark.skipif(not os.path.isfile(pins.MEASURER_JAR), reason="the measurer is not built")
def test_livewidth_fixture():
    assert lw.check() == []
