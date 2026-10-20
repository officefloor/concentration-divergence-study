"""The fast rules flag exactly the units paper one's rules flag (rules.py's claim)."""
import random

import numpy as np

from complexity_concentration_study import extract as p1_extract
from complexity_concentration_study import metrics as p1_metrics

from concentration_divergence_study import rules


def populations():
    rnd = random.Random(7)
    yield [0.0] * 30                                             # constant
    yield [0.0] * 40 + [1.0, 2.0, 50.0]                          # zero-heavy: MAD 0, mean-AD
    yield [1.0, 1.0, 1.0, 2.0]                                   # tiny
    yield [3.0]
    yield []
    for n in (5, 19, 20, 21, 60, 400, 1499, 1500, 1501, 4000):
        yield [float(int(rnd.paretovariate(1.3))) for _ in range(n)]          # heavy-tailed, tied
        yield [round(rnd.lognormvariate(1, 1), 4) for _ in range(n)]          # continuous
        yield [float(rnd.choice([0, 0, 0, 1, 2, 3, 5, 8, 40])) for _ in range(n)]  # few levels
        yield [rnd.choice([0.0, 2.0]) * rnd.randint(0, 9) for _ in range(n)]       # products (x * fD)


def test_every_rule_matches_paper_one():
    for vals in populations():
        vmap = {i: v for i, v in enumerate(vals)}
        arr = np.array(vals, dtype=float)
        for name in rules.ORDER:
            want = p1_metrics.ALGORITHMS[name](vmap)
            got = set(np.flatnonzero(rules.RULES[name](arr)).tolist())
            assert got == want, (name, len(vals), sorted(want ^ got)[:5])


def test_scale_kind_matches_paper_one():
    for vals in populations():
        kind, z = rules.mad_z_scale(np.array(vals, dtype=float))
        want_kind, fn = p1_extract.modified_z_scale(vals)
        assert kind == want_kind
        assert np.allclose(z, [fn(v) for v in vals])


def test_medcouple_matches_paper_one():
    rnd = random.Random(3)
    for n in (3, 10, 101, 1600):
        xs = sorted(float(rnd.randint(0, 20)) for _ in range(n))
        assert rules.medcouple(np.array(xs)) == p1_metrics._medcouple(xs)
