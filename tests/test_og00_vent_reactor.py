"""og-00 Campaign-0 vent reactor: processes, generators, runs, viz.

Covers both baselines: the REAL coupled model
(``og_00_vent_reactor_baseline`` — PHREEQC + FiPy) and the reduced
tuned-relaxation reproduction (``og_00_vent_reactor_reduced``).
"""
from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

REAL_ID = "viva_genesis.composites.campaign0.og_00_vent_reactor_baseline"
REDUCED_ID = "viva_genesis.composites.campaign0.og_00_vent_reactor_reduced"


def test_processes_registered():
    reg = build_core().link_registry
    # Real Module A/B bridges + reduced fallbacks + the native viz.
    for name in ("PhreeqcSerpentinizationProcess", "FipyReactiveTransportProcess",
                 "SerpentinizationReproductionProcess", "VentReactorReproductionProcess",
                 "VentReactorTimeseries"):
        assert name in reg, name


def test_generators_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert REAL_ID in _REGISTRY, f"{REAL_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"
    assert REDUCED_ID in _REGISTRY


# --- reduced reproduction (runs anywhere) ---------------------------------

def test_serpentinization_update_positive_in_window():
    from viva_genesis.geochemistry import SerpentinizationReproductionProcess
    proc = SerpentinizationReproductionProcess(config={}, core=build_core())
    out = proc.update({"temperature": 340.0, "flow_velocity": 1.0e-3}, interval=1.0)
    assert set(out) >= {"H2", "alkalinity", "heat", "H2_flux", "alkalinity_flux", "heat_flux"}
    assert out["H2_flux"] > 0 and out["alkalinity_flux"] > 0


def test_reduced_composite_settles_in_lost_city_window():
    from viva_genesis.composites.campaign0 import og_00_vent_reactor_reduced
    core = build_core()
    sim = Composite({"state": og_00_vent_reactor_reduced(core)}, core=core)
    sim.run(120.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    temp_c = last["temperature"] - 273.15
    assert 40.0 <= temp_c <= 91.0, f"T={temp_c:.1f}C outside Lost City window"
    assert 9.0 <= last["pH"] <= 10.8, f"pH={last['pH']:.2f} outside window"
    assert last["H2_flux"] > 0 and last["alkalinity_flux"] > 0


# --- real coupled model (PHREEQC + FiPy) ----------------------------------

def test_real_composite_conserves_reduces_and_warms():
    pytest.importorskip("phreeqpython")
    pytest.importorskip("fipy")
    from viva_genesis.composites.campaign0 import og_00_vent_reactor_baseline
    core = build_core()
    sim = Composite({"state": og_00_vent_reactor_baseline(core)}, core=core)
    sim.run(120.0)
    rows = gather_emitter_results(sim)[("emitter",)]
    n = len(rows)
    tail = rows[-max(1, n // 4):]

    def settled(k):
        return sum(r[k] for r in tail) / len(tail)

    # Real PHREEQC reducing power: sustained positive H2 source flux, reducing pe.
    assert min(r["H2_flux"] for r in rows[n // 2:]) > 0.0
    assert settled("pe") < 0.0
    # PHREEQC conserves charge; FiPy's FVM conserves flux (machine-eps witnesses).
    assert max(abs(r["charge_imbalance"]) for r in rows) < 1e-6
    assert max(abs(r["flux_divergence_residual"]) for r in rows) < 1e-3
    # Heat-calibrated outlet temperature lands in the Lost City window.
    assert 40.0 <= settled("temperature") - 273.15 <= 91.0
    # pH lands in the Lost City window via the real peridotite (olivine+pyroxene)
    # Ca-OH endmember — the serpentinized-fluid equilibrium pH transported to the
    # outlet, not a tuned value.
    assert 9.0 <= settled("pH") <= 10.8


def test_viz_renders_html():
    pytest.importorskip("phreeqpython")
    pytest.importorskip("fipy")
    from viva_genesis.viz import VentReactorTimeseries
    html = VentReactorTimeseries(config={"n_steps": 40}, core=build_core()).update({})["html"]
    assert isinstance(html, str) and "plotly" in html.lower() and len(html) > 1000
