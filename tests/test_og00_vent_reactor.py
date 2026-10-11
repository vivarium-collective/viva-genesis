"""og-00 Campaign-0 reduced vent-reactor model: processes, generator, run, viz."""
from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.campaign0.og_00_vent_reactor_baseline"


def test_processes_registered():
    reg = build_core().link_registry
    assert "SerpentinizationReproductionProcess" in reg
    assert "VentReactorReproductionProcess" in reg
    assert "VentReactorTimeseries" in reg


def test_serpentinization_update_positive_in_window():
    from viva_genesis.geochemistry import SerpentinizationReproductionProcess
    core = build_core()
    proc = SerpentinizationReproductionProcess(config={}, core=core)
    out = proc.update({"temperature": 340.0, "flow_velocity": 1.0e-3}, interval=1.0)
    assert set(out) >= {"H2", "alkalinity", "heat", "H2_flux", "alkalinity_flux", "heat_flux"}
    assert out["H2_flux"] > 0 and out["alkalinity_flux"] > 0  # producing at the optimum


def test_vent_reactor_relaxes_toward_target():
    from viva_genesis.transport import VentReactorReproductionProcess
    core = build_core()
    proc = VentReactorReproductionProcess(config={}, core=core)
    # Cold, acidic start → temperature + pH deltas must be positive (toward target).
    out = proc.update({"temperature": 300.0, "pH": 7.2, "porosity": 0.35,
                       "H2": 0.0, "alkalinity": 0.02, "heat": 10.0}, interval=1.0)
    assert out["temperature"] > 0  # warming toward the mixing target
    assert out["pH"] > 0           # alkalinizing toward the window


def test_generator_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} not registered; have {[i for i in _REGISTRY if 'genesis' in i]}"


def test_composite_settles_in_lost_city_window():
    from viva_genesis.composites.campaign0 import vent_reactor_baseline
    core = build_core()
    sim = Composite({"state": vent_reactor_baseline(core)}, core=core)
    sim.run(120.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    temp_c = last["temperature"] - 273.15
    assert 40.0 <= temp_c <= 91.0, f"T={temp_c:.1f}C outside Lost City window"
    assert 9.0 <= last["pH"] <= 10.8, f"pH={last['pH']:.2f} outside window"
    assert last["H2_flux"] > 0 and last["alkalinity_flux"] > 0  # sustained reducing supply


def test_viz_renders_html():
    from viva_genesis.viz import VentReactorTimeseries
    core = build_core()
    html = VentReactorTimeseries(config={"n_steps": 60}, core=core).update({})["html"]
    assert isinstance(html, str) and "plotly" in html.lower() and len(html) > 1000
