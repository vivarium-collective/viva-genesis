"""Study-31 composite: real Martini CG MD membrane cohesion (needs the membrane extra)."""
import pytest
from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core

pytest.importorskip("openmm")
pytest.importorskip("martini_openmm")

from viva_genesis.composites.og_31_protometabolism_to_amphiphiles import (  # noqa: E402
    og_31_protometabolism_to_amphiphiles as og31,
)


def test_generator_and_process_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert any(eid.endswith(".og_31_protometabolism_to_amphiphiles") for eid in _REGISTRY)
    assert "OpenMMMartiniProcess" in build_core().link_registry


def test_real_md_run_shows_membrane_cohesion():
    core = build_core()
    # Tiny bilayer, CPU, few steps — keeps the real MD fast + deterministic.
    sim = Composite({"state": og31(core, nx=3, ny=3, steps_per_update=200,
                                   platform="CPU", minimize=True)}, core=core)
    sim.run(2.0)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    # Minimize+NVT relaxes the clashy placement into a bound bilayer: PE settles
    # negative (cohesion) and is finite; the membrane geometry is reported.
    assert last["potential_energy"] < 0.0
    assert last["potential_energy"] == last["potential_energy"]  # not NaN
    assert last["area_per_lipid"] > 0.0
    assert last["n_lipids"] == 18.0
