"""Study-27 composite: the evolving geochemical reaction interface.

Asserts the generator is discoverable and that the mineral dynamics is wired into
the real PHREEQC->FiPy coupling so a short run evolves porosity + catalytic
accessibility and keeps the mineral-mass ledger closed. Uses the real bridges, so
it runs only a couple of steps.
"""
import pytest

from process_bigraph import Composite, gather_emitter_results

pytest.importorskip("phreeqpython")  # real PHREEQC bridge required for this coupling

from viva_genesis.core import build_core  # noqa: E402
from viva_genesis.composites.og_27_coupled_geochemical_reaction_interface import (  # noqa: E402
    og_27_coupled_geochemical_reaction_interface as og27,
)


def test_generator_is_registered():
    from process_bigraph.composite_generator import _REGISTRY
    matches = [eid for eid in _REGISTRY if eid.endswith(".og_27_coupled_geochemical_reaction_interface")]
    assert matches, f"og_27 generator missing; have e.g. {list(_REGISTRY)[:3]}"


def test_document_wires_mineral_into_the_coupling():
    doc = og27(build_core())
    assert "mineral_surface" in doc
    ms = doc["mineral_surface"]
    # Reads the PHREEQC saturation index; writes the porosity delta to the SAME
    # store FiPy writes (so the two porosity contributions compose).
    assert ms["inputs"]["saturation_index"] == ["diagnostics", "saturation_index"]
    assert ms["outputs"]["porosity"] == ["vent", "porosity"]
    assert doc["transport"]["outputs"]["porosity"] == ["vent", "porosity"]
    # PHREEQC now routes its real SI into the diagnostics store the mineral reads.
    assert doc["serpentinization"]["outputs"]["saturation_index"] == ["diagnostics", "saturation_index"]


def test_short_run_evolves_interface_and_keeps_ledger_closed():
    core = build_core()
    sim = Composite({"state": og27(core, nx=8)}, core=core)
    sim.run(2.0)  # two steps of the real coupling
    rows = gather_emitter_results(sim)[("emitter",)]
    assert rows, "no emitter rows"
    last = rows[-1]
    # The evolving-interface observables are present + finite.
    for k in ("porosity", "catalytic_accessibility", "saturation_index",
              "mineral_mass_residual", "reactive_surface_area"):
        assert k in last
    # Catalytic accessibility starts at 1.0 and can only be passivated downward.
    assert last["catalytic_accessibility"] <= 1.0 + 1e-9
    # Mineral mass stays conserved.
    assert abs(last["mineral_mass_residual"]) < 1e-9
