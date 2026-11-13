import importlib.util
from pathlib import Path
import pytest
from ruamel.yaml import YAML

SD = Path(__file__).resolve().parents[1] / "workspace/studies/s06-individuality"


def _study():
    return YAML().load(open(SD / "study.yaml"))


def test_study_declares_four_arms_and_seeds():
    d = _study()
    vs = [d["baseline"][0]] + list(d["variants"])
    arms = {}
    for v in vs:
        p = v["params"]
        arms.setdefault((p["clonality"], p["selection"]), set()).add(p["seed"])
    assert set(arms) == {("clonal", True), ("clonal", False), ("mixed", True), ("mixed", False)}
    assert all(len(s) >= 3 and {4, 5, 6} <= s for s in arms.values())
    assert "tests" not in d
    for k in ("controls", "alternative_hypotheses", "falsifiability", "limitations", "followup_study_proposals"):
        assert d[k]


def test_grader_returns_per_arm_metrics():
    if not (SD / "runs.db").exists():
        pytest.skip("no runs.db")
    spec = importlib.util.spec_from_file_location("grade_individuality", SD / "analysis/grade_individuality.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    r = m.grade()
    assert len(r["arms"]) == 8 and isinstance(r["verdict"], bool)
    assert all(a["n"] >= 3 for a in r["arms"].values())
