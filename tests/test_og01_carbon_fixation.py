"""og-01 Campaign-I real model: eQuilibrator thermo + FiPy NPP + lab kinetics.

Guarded with importorskip so CI without equilibrator_api / fipy skips (not fails).
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, allocate_core, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.carbon_fixation.hydrothermal_carbon_fixation"


def test_processes_and_viz_registered():
    reg = build_core().link_registry
    for name in ("PhGradientNernstPlanckProcess", "EquilibratorThermoStep",
                 "CarbonFixationProcess", "CarbonFixationViz"):
        assert name in reg, name


def test_generator_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


# --- real eQuilibrator thermodynamics -------------------------------------

def test_equilibrator_feasibility_and_product_inhibition():
    pytest.importorskip("equilibrator_api")
    from viva_genesis.protometabolism.thermo import EquilibratorThermoStep
    s = EquilibratorThermoStep(config={}, core=allocate_core())
    base = {"pH": 8.0, "ionic_strength": 0.25, "temperature": 373.15, "H2": 5e-3, "CO2": 2e-3}
    fresh = s.update({**base, "formate": 1e-6, "acetate": 1e-7, "pyruvate": 1e-8})
    assert fresh["free_energy_logged"] is True
    assert fresh["dg_formate"] < 0.0                 # real negative ΔG' (favorable)
    assert fresh["feasible_formate"] > 0.9
    # Product inhibition: a saturated fluid shuts formate down (real thermodynamics).
    sat = s.update({**base, "H2": 1e-4, "CO2": 1e-4, "formate": 0.2, "acetate": 1e-4, "pyruvate": 1e-5})
    assert sat["feasible_formate"] < fresh["feasible_formate"]


# --- real FiPy Nernst-Planck electrochemistry -----------------------------

def test_ph_gradient_favorable_vs_tutolo():
    pytest.importorskip("fipy")
    from viva_genesis.electrochemistry.ph_gradient import PhGradientNernstPlanckProcess
    st = {"pH_vent": 9.5, "pH_ocean": 6.0, "temperature": 333.15}
    fav = PhGradientNernstPlanckProcess(config={"gradient_efficiency": 1.0}, core=allocate_core())
    tut = PhGradientNernstPlanckProcess(config={"gradient_efficiency": 0.1}, core=allocate_core())
    of = ot = None
    for _ in range(5):
        of = fav.update(st, 1.0); ot = tut.update(st, 1.0)
    assert of["pmf"] > 0.2                      # strong proton-motive force (favorable)
    assert ot["pmf"] < 0.3 * of["pmf"]          # Tutolo-2026 collapse
    assert of["flux_divergence_residual"] <= 1e-2


# --- lab-calibrated kinetics + controls -----------------------------------

def _fix_run(cat=1.0, pmf=0.2, h2=5e-3, steps=120):
    from viva_genesis.protometabolism.carbon_fixation import CarbonFixationProcess
    p = CarbonFixationProcess(config={}, core=allocate_core())
    st = {"H2": h2, "CO2": 2e-3, "temperature": 373.15, "pmf": pmf, "catalyst_activity": cat,
          "feasible_formate": 1.0, "feasible_acetate": 1.0, "feasible_pyruvate": 1.0,
          "formate": 0.0, "acetate": 0.0, "pyruvate": 0.0}
    for _ in range(steps):
        u = p.update(st, 1.0)
        for k in ("formate", "acetate", "pyruvate"):
            st[k] += u[k]
    return st


def test_fixation_hits_preiner_yields_and_controls_kill_it():
    fav = _fix_run()
    assert 0.05 <= fav["formate"] <= 0.22        # ~200 mM ceiling
    assert fav["formate"] > fav["acetate"] > fav["pyruvate"]   # Preiner hierarchy
    # Controls (no gradient / no H2 / no catalyst) each zero out formate.
    assert _fix_run(pmf=0.0)["formate"] < 1e-3
    assert _fix_run(h2=0.0)["formate"] < 1e-3
    assert _fix_run(cat=0.0)["formate"] < 1e-3


# --- full coupled composite -----------------------------------------------

def test_favorable_composite_reproduces_benchmarks():
    pytest.importorskip("equilibrator_api")
    pytest.importorskip("fipy")
    from viva_genesis.composites.carbon_fixation import hydrothermal_carbon_fixation
    core = build_core()
    sim = Composite({"state": hydrothermal_carbon_fixation(core)}, core=core)
    sim.run(120.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert 0.05 <= last["formate"] <= 0.22           # Preiner formate
    assert last["net_carbon_flux"] >= 0.0            # a carbon-flux region
    assert last["pmf"] > 0.2                          # usable proton-motive force
    # real ΔG' logged (energy_directionality) + FVM conservation.
    assert last["dg_formate"] < 0.0
    assert abs(last["flux_divergence_residual"]) <= 1e-2
