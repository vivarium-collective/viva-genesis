"""og-res-phosphorus Campaign model: libRoadRunner P-speciation + precipitation sink.

Guarded with importorskip so CI without tellurium skips (not fails).
"""
from __future__ import annotations

import numpy as np
import pytest

from process_bigraph import Composite, allocate_core, gather_emitter_results
from viva_genesis.core import build_core

GEN_ID = "viva_genesis.composites.phosphorus_availability.phosphorus_availability"


def test_process_and_viz_registered():
    reg = build_core().link_registry
    assert "PhosphorusSpeciationProcess" in reg
    assert "PhosphorusSpeciationViz" in reg
    assert "PhosphorusMechanismViz" in reg
    assert "PhosphorusAvailabilityMap" in reg


def test_generator_registered():
    from process_bigraph.composite_generator import _REGISTRY
    assert GEN_ID in _REGISTRY, f"{GEN_ID} missing; have {[i for i in _REGISTRY if 'genesis' in i]}"


def _run(core, n=120, **kw):
    sim = Composite({"state": _gen(core, **kw)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


def _gen(core, **kw):
    from viva_genesis.composites.phosphorus_availability import phosphorus_availability
    return phosphorus_availability(core, **kw)


def _settled_net(rows):
    tail = rows[-max(1, len(rows) // 5):]
    return float(np.mean([r["net_reactive_P"] for r in tail]))


def test_favorable_pore_makes_reactive_p_available():
    """In the enriched pore reactive-P production outpaces precipitation — net
    availability > 0 and reactive P accumulates while little precipitates."""
    pytest.importorskip("tellurium")
    core = build_core()
    rows = _run(core)
    last = rows[-1]
    assert _settled_net(rows) > 0.0               # reactive P produced faster than lost
    assert last["reactive_P"] > last["mineral_P"]  # reactive route wins over the sink
    assert last["precipitated_fraction"] < 0.25    # little precipitated


def test_open_pore_ablation_collapses_availability():
    """Open pore / no thermal gradient (enrichment = 1): precipitation wins, reactive-P
    availability collapses and most phosphorus precipitates (the feature ablation)."""
    pytest.importorskip("tellurium")
    core = build_core()
    rows = _run(core, pore_enrichment=1.0)
    assert _settled_net(rows) <= 0.0               # no enrichment -> availability collapses
    assert rows[-1]["precipitated_fraction"] > 0.5  # phosphate precipitates before it is useful


def test_phosphorus_mass_conserved():
    """The closed P-atom network conserves total phosphorus to ~machine epsilon."""
    pytest.importorskip("tellurium")
    core = build_core()
    rows = _run(core)
    assert max(abs(r["p_mass_residual"]) for r in rows) <= 1e-6


def test_enrichment_tips_fate_toward_reactive():
    """Higher pore enrichment moves phosphorus from the precipitation sink toward the
    reactive route — precipitated fraction falls as enrichment rises."""
    pytest.importorskip("tellurium")
    core = build_core()
    low = _run(core, pore_enrichment=1.0)[-1]["precipitated_fraction"]
    high = _run(core, pore_enrichment=30.0)[-1]["precipitated_fraction"]
    assert high < low
