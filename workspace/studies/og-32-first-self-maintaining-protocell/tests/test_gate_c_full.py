"""Behavior tests for og-32 full Gate C (Option B, MD-INFORMED self-maintenance).

Assertions against the committed artifact (``artifacts/gate_c_full.json`` from
``sims/compute_gate_c_full.py``), plus the real MD observables
(``artifacts/md_bilayer_observables.json``). Back the study's findings: MD-informed
permeability that moves with composition, the measurable ⚑1 self-maintenance
(integrity AND benefit over the matched ablation), the honest persistence-not-throughput
shape, and the located boundaries.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ART = Path(__file__).resolve().parents[1] / "artifacts"
GATE_C = ART / "gate_c_full.json"
MD = ART / "md_bilayer_observables.json"


@pytest.fixture(scope="module")
def art():
    if not GATE_C.exists():
        pytest.skip(f"{GATE_C.name} not found — run sims/compute_gate_c_full.py")
    return json.loads(GATE_C.read_text())


@pytest.fixture(scope="module")
def md():
    if not MD.exists():
        pytest.skip(f"{MD.name} not found — run sims/run_md_bilayer_observables.py on the mini")
    return json.loads(MD.read_text())


def test_md_thickness_responds_to_composition(md):
    """Real short Martini CG-MD: the longer-chain (di-C16) bilayer is thicker than the
    shorter-chain (di-C12) one — the composition-responsive structural observable."""
    r = md["results"]
    assert r["DPPC"]["bilayer_thickness_nm"] > r["DLPC"]["bilayer_thickness_nm"]
    assert r["DPPC"]["n_tail_beads_per_chain"] > r["DLPC"]["n_tail_beads_per_chain"]


def test_permeability_is_md_informed_not_fixed(art):
    """Membrane permeability/retention is derived from the MD thickness (composition),
    not a free parameter: thicker long-chain core -> lower permeability -> higher retention."""
    mi = art["membrane_integrity"]
    assert 0.0 < mi["retention"] < 1.0
    comp = {c["composition"]: c for c in art["boundary"]["composition"]}
    long_, short = comp["long_di-C16"], comp["short_di-C12"]
    # thicker (long) -> lower permeability -> higher retention than thinner (short)
    assert long_["thickness_nm"] > short["thickness_nm"]
    assert long_["permeability"] < short["permeability"]
    assert long_["retention"] > short["retention"]


def test_membrane_integrity_maintained(art):
    """Self-maintenance (i): net amphiphile production >= degradation (the metabolism
    rebuilds its membrane at least as fast as it degrades)."""
    mi = art["membrane_integrity"]
    assert mi["maintained"] is True
    assert mi["production"] >= mi["degradation"]
    assert mi["net_integrity"] >= 0.0


def test_beats_ablation_on_persistence(art):
    """Self-maintenance (ii): the membrane beats the matched no-endogenous-membrane
    ablation at equal feeds on persistence (standing pool)."""
    d = art["benefit_demo"]
    assert d["beats_ablation"] is True
    assert d["persistence_pays"] is True
    assert d["toc_benefit"] > 1.0
    assert d["membrane"]["total_organic_carbon"] > d["ablation"]["total_organic_carbon"]


def test_throughput_not_improved_expected(art):
    """Throughput is NOT improved — the physically-expected, feed-limited null
    (compartmentation buys retention, not faster chemistry; mirrors og-31)."""
    d = art["benefit_demo"]
    assert d["throughput_pays"] is False
    assert d["flux_benefit"] < 1.0


def test_self_maintaining_and_qualified(art):
    """⚑1 measurable self-maintenance holds (integrity AND benefit), and the verdict is
    qualified — a genuine positive with the persistence-only / MD-informed caveats."""
    assert art["self_maintaining"] is True
    assert art["verdict"] == "qualified"


def test_result_is_windowed_with_located_boundary(art):
    """The result is windowed, not a single favorable point: integrity holds only up to a
    located k_deg boundary, above which the membrane is not self-maintained."""
    kb = art["boundary"]["k_deg"]
    bound = art["boundary"]["k_deg_boundary_max"]
    assert bound is not None and bound > 0.0
    assert any(b["maintained"] for b in kb)
    assert any(not b["maintained"] for b in kb)     # a real upper boundary exists
    for b in kb:
        if b["maintained"]:
            assert b["k_deg"] <= bound


def test_scope_is_md_informed_not_pmf(art):
    """The coupling is labelled MD-informed (structural proxy), NOT PMF-resolved — Option
    A (study og-32a) is the budgeted follow-on."""
    coupling = art["meta"]["coupling"].lower()
    assert "md-informed" in coupling
    assert "not pmf-resolved" in coupling or "not pmf" in coupling