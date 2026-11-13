"""Cross-run checks for specialization-improves-group-performance, read from runs.db.
Net biomass = viable_biomass(last) - viable_biomass(first emitted update). Held-out env B = o2_source 0.025."""
import json, sqlite3, statistics as st
from pathlib import Path
import pytest

DB = Path(__file__).resolve().parents[1] / "runs.db"
ENV_B = 0.025


def _net_by_arm():
    db = sqlite3.connect(DB)
    out = {}
    for rid, pj, n in db.execute("select run_id, params_json, n_steps from runs_meta where status='completed'"):
        p = json.loads(pj)
        first = db.execute("select min(step) from history where simulation_id=? and step>=1", (rid,)).fetchone()[0]
        v = lambda s: float(json.loads(db.execute("select state from history where simulation_id=? and step=?", (rid, s)).fetchone()[0])["viable_biomass"])
        out.setdefault((p["fate_mode"], float(p["o2_source"])), []).append(v(n) - v(first))
    return {k: st.mean(x) for k, x in out.items()}


@pytest.fixture(scope="module")
def mean():
    if not DB.exists():
        pytest.skip("no runs.db")
    return _net_by_arm()


@pytest.mark.parametrize("control", ["none", "random", "clamped"])
def test_oxygen_beats_controls_on_B(mean, control):
    assert mean[("oxygen", ENV_B)] > mean[(control, ENV_B)]


def test_oxygen_beats_random(mean):
    """Decisive: isolates the spatial pattern of fate from the amount of differentiation."""
    assert mean[("oxygen", ENV_B)] > mean[("random", ENV_B)]
