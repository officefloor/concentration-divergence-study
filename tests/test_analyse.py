"""The analysis code paths on synthetic scores: the hand-built record of test_units scored as a
few repositories, so every estimand runs end to end before any real score exists."""
import copy

import numpy as np

from concentration_divergence_study import analyse, core, forms, score, units

from test_units import record


def fake_scores(n: int = 8, half: str = "explore") -> list[dict]:
    out = []
    for i in range(n):
        rec = copy.deepcopy(record())
        # vary the complexity so the rules have something to flag, and the labels
        mv = rec["units"]["method"]["values"]
        mv["cc"] = [float(v) * (1 + i % 3) for v in mv["cc"]]
        cv = rec["units"]["class"]["values"]
        cv["cognitive_max"] = [10.0 + 5 * i, 1.0]
        cv["nom"] = [4.0, 1.0]
        rec["units"]["class"]["god_idx"]["human_blob"] = [0] if i % 2 == 0 else []
        rec["units"]["method"]["god_idx"]["human_method_long_method"] = [0] if i % 2 else []
        rec["units"]["method"]["god_idx"]["human_method_long_method_reviewed"] = [0, 4]
        sc = score.score_record(rec)
        sc["meta"] = {"key": f"r{i}", "usable": True, "error": None, "half": half, "di": [],
                      "javaparser": {"budget_exhausted": False}, "full_name": f"o{i % 2}/r{i}"}
        out.append(sc)
    return out


def test_decomposition_and_mechanism_run_end_to_end():
    scores = fake_scores()
    pop = core.Population(scores, "joined", "class", "human_blob", "fake Blob")
    assert pop.n == 8
    x = "cognitive_max"
    primary = core.compare(pop, x, core.primary_arm("class", x))
    dc = analyse.decomposition(pop, x, "class")
    assert set(dc) == {"exemption_only", "amplification_only", "D_vs_exemption_only", "D_vs_amplification_only"}
    assert dc["exemption_only"]["y"] == f"{x}*E_flow[A,np]"
    assert dc["amplification_only"]["y"] == f"{x}*A_flow[A,np]"
    lf = analyse.leaf(pop, x, "flow", "np")
    mech = analyse.mechanism(primary, dc["exemption_only"], lf)
    assert mech["reading"]
    if primary["reading"] != core.REFINES:
        assert mech["reading"].startswith("not read")
    # the mechanism reading itself, on made-up readings
    refine = {"reading": core.REFINES}
    assert analyse.mechanism(refine, refine, {"reading": "unresolved"})["reading"] == analyse.BY_EXEMPTION
    assert analyse.mechanism(refine, refine, {"reading": "contradicted (x)"})["reading"] == analyse.BY_AMPLIFICATION
    assert analyse.mechanism(refine, {"reading": "no difference resolved"}, {"reading": "unresolved"})["reading"] == analyse.BY_AMPLIFICATION
    assert analyse.mechanism({"reading": "no difference resolved"}, refine, {"reading": "unresolved"})["reading"].startswith("not read")
    # method level
    mp = core.Population(scores, "joined", "method", "human_method_long_method", "fake Long Method")
    assert mp.n == 8
    dm = analyse.decomposition(mp, "cc", "method")
    assert dm["exemption_only"]["y"] == "cc*E_flow@all"
    sn = analyse.size_null(pop, x)
    assert sn["size_null"] == f"{x}*N" and sn["D_vs_N"]["x"] == f"{x}*N"
    assert analyse.matrix_by_family(pop)["rows"]
    assert analyse.intersection(pop, x)["cells"]
