"""The live-width facts on the pass's fixture, and the widths computed from them (post hoc)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import livewidth as lw  # noqa: E402

from concentration_divergence_study import pins  # noqa: E402


def _method(vars_, lines, name_line=1):
    return {"name": "m", "name_line": name_line, "lines": lines, "vars": vars_}


def _v(name, kind, first, last, loop_first=None, loop_last=None, defs=1, steps=0, muts=0):
    return [name, kind, first, last, first if loop_first is None else loop_first,
            last if loop_last is None else loop_last, defs, steps, muts]


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


def test_fields_count_only_in_the_all_scope():
    m = _method([_v("f", lw.FIELD, 1, 3), _v("x", lw.LOCAL, 2, 3)], [1, 2, 3])
    assert lw.summary(m, ("text", "unit", "locals", "use"))["max"] == 1
    assert lw.summary(m, ("text", "unit", "all", "use"))["max"] == 2


def test_an_empty_method_is_zero():
    s = lw.summary(_method([], []), lw.HEADLINE)
    assert s["max"] == 0 and s["peak_line"] is None


def test_every_variant_is_labelled_once():
    labels = [lw.label(v) for v in lw.variants()]
    assert len(labels) == len(set(labels)) == 13
    assert lw.label(lw.HEADLINE) == "[loop,role,all]"


@pytest.mark.skipif(not os.path.isfile(pins.MEASURER_JAR), reason="the measurer is not built")
def test_livewidth_fixture():
    assert lw.check() == []
