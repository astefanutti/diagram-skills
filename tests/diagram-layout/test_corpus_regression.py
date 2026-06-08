"""Baseline guard over the historical layout-plan corpus.

`eval/runs/` is gitignored (present only on a machine that has run the eval), so
this test SKIPS when the corpus is absent — it protects local iteration without
breaking a fresh clone / CI. When present, it asserts that running fix_layout
over every plan stays at or better than the established baseline:

    improved >= 8, regressed <= 1

The single accepted regression is a known pre-existing ungrouped eval-mlflow
case; see the edge-routing-robustness / regression-suite notes.
"""
import copy
import glob
import json
import os

import pytest

import fix_layout as F
from validate_layout import validate

# <repo>/tests/diagram-layout/test_corpus_regression.py -> <repo>
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = sorted(glob.glob(os.path.join(ROOT, "eval", "runs", "**",
                                       "layout-plan.json"), recursive=True))


def _issues(p, spec):
    r = validate(p, spec)
    return len(r["errors"]) + len(r["warnings"])


@pytest.mark.skipif(len(CORPUS) < 50,
                    reason="layout-plan corpus (eval/runs) not present")
def test_fix_layout_holds_baseline_over_corpus():
    improved = unchanged = regressed = 0
    regressions = []
    for path in CORPUS:
        with open(path) as f:
            base = json.load(f)
        spec = None
        sp = os.path.join(os.path.dirname(path), "graph-spec.json")
        if os.path.exists(sp):
            with open(sp) as f:
                spec = json.load(f)
        before = _issues(base, spec)
        work = copy.deepcopy(base)
        F.fix(work, spec)
        after = _issues(work, spec)
        if after < before:
            improved += 1
        elif after > before:
            regressed += 1
            regressions.append((path.replace(ROOT + "/", ""), before, after))
        else:
            unchanged += 1

    assert regressed <= 1, f"new regressions: {regressions}"
    assert improved >= 8, f"only {improved} plans improved (expected >= 8)"
