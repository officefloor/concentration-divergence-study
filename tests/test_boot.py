"""The vectorised bootstrap reproduces paper one's stats.bootstrap_paired."""
import random

import numpy as np

from complexity_concentration_study import stats as p1stats

from concentration_divergence_study import boot


def _items(n, seed):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        u = rnd.randint(0, 30)
        g = rnd.randint(0, min(u, 4))
        ox = rnd.randint(0, u)
        oy = rnd.randint(0, ox)
        out.append(({"n_univ": u, "n_out": ox, "n_overlap": rnd.randint(0, min(ox, g)), "n_god_univ": g},
                    {"n_univ": u, "n_out": oy, "n_overlap": rnd.randint(0, min(oy, g)), "n_god_univ": g}))
    return out


def test_micro_diff_equals_paper_one():
    for n, seed in ((7, 1), (40, 2), (120, 3)):
        items = _items(n, seed)

        def stat(its):
            a = p1stats.pooled_confusion([x for x, _ in its])["mcc"]
            b = p1stats.pooled_confusion([y for _, y in its])["mcc"]
            return None if a is None or b is None else b - a
        want = p1stats.bootstrap_paired(items, stat, b=400, seed=12345)
        cx = np.array([[c["n_univ"], c["n_out"], c["n_overlap"], c["n_god_univ"]] for c, _ in items])
        cy = np.array([[c["n_univ"], c["n_out"], c["n_overlap"], c["n_god_univ"]] for _, c in items])
        got = boot.micro_diff(cx, cy, boot.multiplicities(n, b=400, seed=12345))
        for k in ("value", "lo", "hi"):
            assert abs(want[k] - got[k]) < 1e-12, (k, want, got)
        assert want["n_dropped"] == got["n_dropped"]


def test_auc_equals_paper_one():
    rnd = random.Random(5)
    pos = [float(rnd.randint(0, 9)) for _ in range(30)]
    neg = [float(rnd.randint(0, 9)) for _ in range(70)]
    assert abs(boot.auc(np.array(pos), np.array(neg)) - p1stats.auc(pos, neg)) < 1e-12
