import pytest

pytest.importorskip("viva_cpm")

from process_bigraph import Composite, composite_spec

import viva_genesis  # noqa: F401
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.multicellularity_world.s06_individuality"


def _run(**kw):
    core = build_core()
    from viva_genesis.composites.multicellularity_world import s06_individuality
    comp = Composite({"state": s06_individuality(core, **kw)}, core=core)
    traj = []
    for _ in range(kw.get("generations", 6)):
        comp.run(1)
        traj.append(comp.state["mean_adhesion"])
    return comp, traj


def test_registers_and_default_steps():
    spec = composite_spec.get(GEN_ID)
    assert spec is not None
    n = getattr(spec, "default_n_steps", None)
    if n is None and isinstance(spec, dict):
        n = spec.get("default_n_steps")
    assert n == 6
    from viva_genesis.composites.multicellularity_world import s06_individuality  # noqa: F401


def test_response_with_selection():
    _, traj = _run(clonality="clonal", selection=True, generations=6)
    assert traj[-1] > traj[0] + 0.03, traj


def test_drift_null_without_selection():
    _, traj = _run(clonality="clonal", selection=False, generations=6)
    assert abs(traj[-1] - traj[0]) < 0.08, traj


def test_fitness_variance_guard():
    from viva_genesis.s06_process import GroupSelectionProcess
    out = {}
    for a in (0.0, 0.5):
        p = GroupSelectionProcess(
            config={"n_founders": 2, "window": 40, "region": 60, "mcs_per_update": 16,
                    "init_adhesion_lo": a, "init_adhesion_hi": a, "seed": 1},
            core=build_core())
        out[a] = p.update({}, 1)["mean_toughness"]
    assert out[0.0] < 0.4, out
    assert out[0.5] == 1.0, out
