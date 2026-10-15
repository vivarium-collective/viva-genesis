"""The geochemical_world layer generator: real PHREEQC + FiPy behind two faces,
with the conservation ledger exact; and the Phase-1 environmental-calibration
pipeline end to end on a tiny ensemble."""

from __future__ import annotations

import numpy as np
import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core


def _run(core, **kw):
    from viva_genesis.composites.geochemical_world import geochemical_world
    sim = Composite({"state": geochemical_world(core, nx=8, **kw)}, core=core)
    sim.run(6.0)
    return gather_emitter_results(sim)[("emitter",)]


def test_generator_registered_with_model_parameters():
    from process_bigraph.composite_generator import _REGISTRY
    entry = _REGISTRY["viva_genesis.composites.geochemical_world.geochemical_world"]
    assert "model_serpentinization" in entry.parameters and "model_spatial_transport" in entry.parameters


@pytest.mark.parametrize("serp,transport", [("phreeqc", "fipy"), ("phreeqc", "fipy_uniform_upflow"),
                                            ("reduced", "fipy")])
def test_world_runs_and_ledger_is_exact(serp, transport):
    pytest.importorskip("fipy")
    if serp == "phreeqc":
        pytest.importorskip("phreeqpython")
    rows = _run(build_core(), model_serpentinization=serp, model_spatial_transport=transport)
    assert len(rows) >= 6
    last = rows[-1]
    assert last["ledger_ok"] == 1.0 and last["energy_directionality"] == 1.0
    assert last["H2_residual"] == 0.0 and last["energy_residual"] == 0.0
    # the ledger audits the snapshot it reads: its integral after tick i equals the
    # pool the emitter recorded at tick i-1 — bit for bit (same floats, same order)
    for i in range(1, len(rows)):
        assert rows[i]["H2_in"] == rows[i - 1]["H2"]
        assert rows[i]["energy_in"] == rows[i - 1]["heat"]
    assert last["H2"] > 0 and last["H2_flux"] > 0
    if serp == "phreeqc":
        assert last["charge_residual_max"] <= 1e-6 and last["pH_eq"] > 8.5


def test_fenics_class_builds_but_needs_pixi():
    from viva_genesis.composites.geochemical_world import geochemical_world
    core = build_core()
    doc = geochemical_world(core, model_spatial_transport="fenics", nx=8)
    assert doc["transport"]["address"] == "local:FenicsReactiveTransportProcess"
    sim = Composite({"state": doc}, core=core)
    with pytest.raises(RuntimeError, match="pixi"):
        sim.run(1)


def test_environment_calibration_pipeline_tiny():
    """Two prior draws x two transport classes through the real world, conditioned and reported."""
    pytest.importorskip("fipy")
    pytest.importorskip("phreeqpython")
    from viva_genesis.uq import environment_calibration as EC
    ens = EC.vent_environment_ensemble(n_draws=2, seed=1, n_steps=4, nx=8)
    assert set(ens.outcomes) == {"serpentinization=phreeqc+spatial_transport=fipy",
                                 "serpentinization=phreeqc+spatial_transport=fipy_uniform_upflow"}
    for rows in ens.outcomes.values():
        assert len(rows) == 2 and all(r["ok"] for r in rows)
        assert all(np.isfinite(r["dissolved_H2_mmol_kg"]) for r in rows)
    cond = EC.condition_ensemble(ens)
    names = {o["name"] for o in cond["observations"]}
    assert names == {"outlet_temperature_C", "outlet_pH", "dissolved_H2_mmol_kg"}   # MARHYS pending is skipped
    assert {r["name"] for r in cond["requirements"]} == {"h2_for_fixation_mM", "ph_gradient_units",
                                                         "below_phreeqc_validity_C"}
    pc = next(iter(cond["per_class"].values()))
    assert pc["n_runs"] == 2 and pc["ledger"]["all_ok"] and pc["ledger"]["max_mass_residual"] == 0.0
    assert "settled_temperature_C" in cond["discrimination"]
    rep = EC.vent_calibration_report(ens, cond)
    d = rep.to_dict()
    assert d["tier"] == "mechanistic_prediction" and d["numerical_verification"]["ok"]
    assert 0.0 <= d["robustness"]["structure_agreement"] <= 1.0
    assert d["provenance_audit"]["counts"]["hypothetical"] >= 1
    # round-trip the artifact
    again = EC.EnvironmentEnsemble.from_dict(ens.to_dict())
    assert again.draws == ens.draws and again.labels() == ens.labels()
