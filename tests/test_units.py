"""The coupling definitions, the join and the forms, on a hand-built record."""
import os

import numpy as np
import pytest

from concentration_divergence_study import files, forms, javaparser, pins, units

I, J, U = javaparser.RES_INTERNAL, javaparser.RES_JDK, javaparser.RES_UNRESOLVED


def _m(name, line, params, vis, calls, local=False, cc=1, kind="method"):
    return {"name": name, "kind": kind, "owner": "A", "vis": vis, "local": local,
            "decl_line": line, "name_line": line, "end_line": line + 2, "params": params,
            "cc": cc, "cognitive": 0, "nesting": 0, "exit_points": 0, "tokens": 5, "nloc": 3,
            "hvol": 10.0, "calls": calls}


def record():
    a = "src/a/A.java"
    b = "src/a/B.java"
    doc = {"files": [
        {"path": a, "package": "a", "level": "JAVA_21", "problem": None, "types": 1, "methods": [
            # p=2; calls: 1 arg to B (leaves), 0 args to A (helper), 3 args to the JDK
            _m("run", 3, 2, "public", [[1, 0, I, 1], [0, 0, I, 0], [3, 0, J, -1]], cc=5),
            _m("help", 9, 0, "private", []),
            _m("anon", 12, 1, "public", [[2, 0, I, 1]], local=True),
            # a public constructor, p=3, calling B's constructor with 1 argument
            _m("A", 15, 3, "public", [[1, 1, I, 1]], kind="ctor")]},
        {"path": b, "package": "a", "level": "JAVA_21", "problem": None, "types": 1, "methods": [
            _m("leaf", 2, 4, "package", [[0, 0, U, -1]], cc=9)]}]}
    munits = [f"{a}::run@3", f"{a}::help@9", f"{a}::anon@12", f"{a}::A@15", f"{b}::leaf@2",
              f"{b}::ghost@40"]
    sig = list(units.METHOD_FIELDS)
    mvals = {s: [1.0] * len(munits) for s in sig}
    mvals["cc"] = [5.0, 1.0, 1.0, 1.0, 9.0, 2.0]
    csig = list(units.CLASS_SIGNALS)
    cvals = {s: [1.0, 1.0] for s in csig}
    return {"units": {"method": {"units": munits, "signals": sig, "values": mvals,
                                 "god_idx": {"brain_method": [4]}},
                      "class": {"units": [a, b], "signals": csig, "values": cvals,
                                "god_idx": {"wmc47": [], "human_blob": [0],
                                            "human_blob_reviewed": [0, 1]}}},
            "javaparser": doc, "jp_oracles": {}}


def test_method_coupling_definitions():
    J_ = units.joined(record())
    m = J_["method"]
    i = m.ids.index("src/a/A.java::run@3")
    assert m.c["in_flow"][i] == 3 and m.c["in_data"][i] == 2 and m.c["in_message"][i] == 1
    # flow: (1+1) + (1+0) all; (1+1) leaving.  data: 1 + 0; 1.  message: max(0,1) + max(-1,1); 1
    assert m.c["out_all_flow"][i] == 3 and m.c["out_leave_flow"][i] == 2
    assert m.c["out_all_data"][i] == 1 and m.c["out_leave_data"][i] == 1
    assert m.c["out_all_message"][i] == 2 and m.c["out_leave_message"][i] == 1


def test_join_and_unjoined_unit_is_unweighted():
    J_ = units.joined(record())
    m = J_["method"]
    assert J_["join"]["joined"] == 5 and J_["join"]["lizard_units"] == 6
    g = m.ids.index("src/a/B.java::ghost@40")
    assert not m.coupled[g]
    d = forms.method_d(m, "flow", "all")
    assert d[g] == 0 and forms.fD(d)[g] == 1          # no coupling: complexity unweighted


def test_catchment_is_exempt():
    J_ = units.joined(record())
    m = J_["method"]
    leaf = m.ids.index("src/a/B.java::leaf@2")       # in 5 (flow), out 0 -> d = -5
    v = forms.vector("method", ("XD", "cc", "flow", "all"), J_)
    assert v[leaf] == 0
    run = m.ids.index("src/a/A.java::run@3")         # d = 3 - 3 = 0, a pipe: counted once
    assert v[run] == 5


def test_exemption_and_amplification_arms():
    """PLAN.md, Amendments, 4: fE exempts only, fA amplifies only, and fD = fE * fA."""
    J_ = units.joined(record())
    m = J_["method"]
    d = forms.method_d(m, "flow", "all")
    assert forms.fE(d).tolist() == [1, 0, 1, 0, 0, 1]           # run (pipe), anon (junction), ghost (uncoupled)
    assert forms.fA(d).tolist() == [1, 1, 2, 1, 1, 1]           # anon: d = 1 -> 2; catchments not exempt
    assert np.array_equal(forms.fD(d), forms.fE(d) * forms.fA(d))
    leaf = m.ids.index("src/a/B.java::leaf@2")
    assert forms.vector("method", ("XE", "cc", "flow", "all"), J_)[leaf] == 0
    assert forms.vector("method", ("XA", "cc", "flow", "all"), J_)[leaf] == 9
    c = J_["class"]
    a = c.ids.index("src/a/A.java")                          # d(A) = 7 - 3 = 4 under flow, np
    assert forms.vector("class", ("XE_A", "cc_sum", "flow", "np"), J_)[a] == 1
    assert forms.vector("class", ("XA_A", "cc_sum", "flow", "np"), J_)[a] == 5
    assert forms.vector("class", ("XD_A", "cc_sum", "flow", "np"), J_)[a] == 5


def test_class_form_A_inputs():
    J_ = units.joined(record())
    c = J_["class"]
    a = c.ids.index("src/a/A.java")
    # callable from outside: run (public); help is private, anon is in an anonymous class; the
    # constructor counts only in the +ctor variants (PLAN.md, Amendments, 2)
    assert c.c["in_np_flow"][a] == 3 and c.c["in_pub_flow"][a] == 3
    assert c.c["in_np+ctor_flow"][a] == 3 + 4 and c.c["in_pub+ctor_flow"][a] == 3 + 4
    # out leaving A: run's call to B (1+1), anon's call to B (1+2), the constructor's `new B(x)` (1+1)
    assert c.c["out_flow"][a] == 7
    b = c.ids.index("src/a/B.java")
    assert c.c["in_np_flow"][b] == 5 and c.c["in_pub_flow"][b] == 0   # package-private leaf
    # form B: the constructor's own in is counted only with constructors
    m = J_["method"]
    k = m.ids.index("src/a/A.java::A@15")
    assert not m.c["callable_np"][k] and m.c["callable_np+ctor"][k]
    assert forms.method_d(m, "flow", "all")[k] == 2 - 4          # the method level is unchanged


def test_human_oracle_universe():
    J_ = units.joined(record())
    pos, univ = J_["class"].oracles["human_blob"]
    assert pos.tolist() == [True, False] and univ.tolist() == [True, True]


def test_form_registry_counts_match_the_plan():
    t = [s[0] for s in forms.METHOD_FORMS]
    assert t.count("X") == 10 and t.count("XD") == 60 and t.count("XO") == 60
    assert t.count("XE") == 60 and t.count("XA") == 60                       # Amendments, 4
    assert t.count("D") + t.count("O") == 12
    c = [s[0] for s in forms.CLASS_FORMS]
    assert c.count("X") == 31 and c.count("XD_A") == 372 and c.count("XO_A") == 93
    assert c.count("XE_A") == 372 and c.count("XA_A") == 372                 # Amendments, 4
    assert c.count("D_A") + c.count("O_A") == 15
    assert c.count("XD_B") == 360 and c.count("XO_B") == 90 and c.count("D_B") + c.count("O_B") == 45
    # the exploratory intersection (PLAN.md, Amendments, 3)
    assert t.count("d") == 6 and t.count("AND") == 60 and t.count("ANDO") == 60 and len(t) == 388
    assert c.count("d_A") == 12 and c.count("AND") == 372 and c.count("ANDO") == 93 and len(c) == 2227
    assert "cognitive_max&d_flow[A,np]" in forms.INDEX["class"] and "cc&d_flow@all" in forms.INDEX["method"]
    assert len(set(forms.CLASS_NAMES)) == len(forms.CLASS_NAMES)
    assert len(set(forms.METHOD_NAMES)) == len(forms.METHOD_NAMES)
    assert "params_max" not in forms.CLASS_CANDIDATES and "nloc_max" in forms.CLASS_CANDIDATES
    assert "cc_sum" not in forms.CLASS_CANDIDATES and "params" not in forms.METHOD_CANDIDATES


def test_extra_exclusion_rule():
    assert files.extra_exclusion("app/src/androidTest/java/a/B.java", "a") == "androidTest"
    assert files.extra_exclusion("x/build/generated/a/A.java", "a") == "build"       # any depth
    assert files.extra_exclusion("core/build/gen/mindustry/A.java", "mindustry") == "build"
    # a package named build or target is a package, not a build directory (PLAN.md, Amendments)
    assert files.extra_exclusion("gradle/plugins/antora/src/main/java/org/x/build/antora/A.java",
                                 "org.x.build.antora") is None
    assert files.extra_exclusion("src/main/java/org/x/target/A.java", "org.x.target") is None
    # no package, or one that does not match the directory: the whole directory is checked
    assert files.extra_exclusion("src/main/java/org/x/target/A.java", "") == "target"
    assert files.extra_exclusion("src/main/java/org/x/target/A.java", "other.pkg") == "target"
    assert files.extra_exclusion("src/main/java/a/build.java", "a") is None           # a file name
    assert files.extra_exclusion("src/main/java/a/A.java", "a") is None


@pytest.mark.skipif(not os.path.isfile(pins.MEASURER_JAR), reason="the measurer is not built")
def test_measurer_fixture():
    assert javaparser.check() == []


def test_and_form_is_the_intersection_of_the_two_flag_sets():
    from concentration_divergence_study import analyse, rules, score
    J_ = units.joined(record())
    out = score.score_level("method", J_)
    names = forms.METHOD_NAMES
    m = J_["method"]
    for x in ("cc", "nloc"):
        for k in units.DEFS:
            fx = rules.all_rules(m.values[x])
            fd = rules.all_rules(forms.method_d(m, k, "all"))
            both = out["cells"][names.index(f"{x}&d_{k}@all")]
            for r, (a, b) in enumerate(zip(fx, fd)):
                assert both[r, 0, 1] == int((a & b).sum())
    # the regions add up: X only + both = X; either = X + d - both
    cx, cd, ca = (np.array([10, f, t, 3]) for f, t in ((4, 2), (3, 1), (2, 1)))
    rg = analyse._regions(cx, cd, ca)
    assert rg["X_only"][1:3].tolist() == [2, 1] and rg["d_only"][1:3].tolist() == [1, 0]
    assert rg["either"][1:3].tolist() == [5, 2] and rg["either"][3] == 3
