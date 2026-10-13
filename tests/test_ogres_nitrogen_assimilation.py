"""og-res Campaign-I (Module I) real model: FeS-mediated reduced-nitrogen production.

Pure-numpy process (no heavy optional deps), so these run everywhere in CI.
"""
from __future__ import annotations

from process_bigraph import Composite, allocate_core, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.nitrogen_assimilation.reduced_nitrogen_reactor"


def test_processes_and_viz_registered():
    reg = build_core().link_registry
    for name in ("ReducedNitrogenProductionProcess", "NitrogenAssimilationViz",
                 "NitrogenCarbonBalanceViz", "NitrogenAssimilationPhaseMap"):
        assert name in reg, name


def test_generator_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


# --- process-level reduction chain + ablation controls --------------------

def _n_run(fes=1.0, h2=5e-3, no3_supply=2e-5, c_demand=1e-4, loss=1e-2, steps=120):
    from viva_genesis.geochemistry.nitrogen_assimilation import ReducedNitrogenProductionProcess
    p = ReducedNitrogenProductionProcess(
        config={"no3_supply": no3_supply, "loss_rate": loss}, core=allocate_core())
    st = {"NO3": 1e-3, "NO2": 0.0, "NH4": 0.0, "amino_precursor": 0.0, "N2": 5e-4,
          "H2": h2, "temperature": 353.15, "fes_activity": fes, "c_demand": c_demand}
    last = None
    for _ in range(steps):
        u = p.update(st, 1.0)
        for k in ("NO3", "NO2", "NH4", "amino_precursor", "N2"):
            st[k] += u[k]
            st[k] = max(st[k], 0.0)
        last = u
    return st, last


def test_ammonium_produced_and_controls_kill_it():
    st, _ = _n_run()
    assert st["NH4"] > 1e-4                      # sustained standing ammonium (> 100 uM)
    assert st["amino_precursor"] > 0.0           # drawn into amino-acid precursors
    # Each feature is necessary: no FeS or no H2 => essentially no ammonium.
    assert _n_run(fes=0.0)[0]["NH4"] < 1e-6
    assert _n_run(h2=0.0)[0]["NH4"] < 1e-6


def test_cn_supply_ratio_keeps_pace_vs_limiting():
    _, fav = _n_run(no3_supply=2e-5)
    _, lim = _n_run(no3_supply=2e-6)
    assert fav["cn_supply_ratio"] <= 8.0         # reduced N keeps pace with carbon
    assert lim["cn_supply_ratio"] > 8.0          # scarce nitrate => nitrogen limiting


def test_nitrogen_mass_conserved():
    from viva_genesis.geochemistry.nitrogen_assimilation import ReducedNitrogenProductionProcess
    p = ReducedNitrogenProductionProcess(
        config={"no3_supply": 2e-5, "loss_rate": 1e-2}, core=allocate_core())
    st = {"NO3": 1e-3, "NO2": 0.0, "NH4": 0.0, "amino_precursor": 0.0, "N2": 5e-4,
          "H2": 5e-3, "temperature": 353.15, "fes_activity": 1.0, "c_demand": 1e-4}
    worst = 0.0
    for _ in range(120):
        u = p.update(st, 1.0)
        worst = max(worst, abs(u["n_mass_residual"]))
        for k in ("NO3", "NO2", "NH4", "amino_precursor", "N2"):
            st[k] = max(st[k] + u[k], 0.0)
    assert worst <= 1e-9                          # N mass conserved to machine precision


# --- full coupled composite -----------------------------------------------

def test_favourable_composite_sustains_reduced_nitrogen():
    from viva_genesis.composites.nitrogen_assimilation import reduced_nitrogen_reactor
    core = build_core()
    sim = Composite({"state": reduced_nitrogen_reactor(core)}, core=core)
    sim.run(120.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["NH4"] > 1e-4                     # standing ammonium pool
    assert last["nh4_production_rate"] > 1e-6     # a viable reduced-N source
    assert 1.0 <= last["cn_supply_ratio"] <= 8.0  # keeps pace with carbon


def test_phase_map_decision_gradient():
    from viva_genesis.phase_maps import nitrogen_assimilation_phase_map
    res = nitrogen_assimilation_phase_map(no3_supply=(2e-6, 1e-4, 5),
                                          fes_activity=(0.05, 1.0, 5), n_steps=120)
    cn = res.surfaces["cn_ratio"]
    # C:N falls as nitrate supply rises (nitrogen stops being limiting).
    assert cn[-1, -1] < cn[0, -1]
    # the keeps-pace region is non-empty but not the whole grid (a real boundary).
    kp = res.surfaces["keeps_pace"]
    assert 0.0 < kp.mean() < 1.0
