"""Phase 7 — the heredity face: six registered classes, loud face rejection
(og-06's own process is a real non-conformer), exact Gillespie budgets, the
Eigen threshold at the agent level, the information ledger + MI convergence,
conditional attachment, the vg-data package and the gate evaluators."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from viva_genesis import models
from viva_genesis.core import build_core
from viva_genesis.heredity import information as I
from viva_genesis.heredity.competing import (HEREDITY_CLASSES, HEREDITY_PROCESSES, POOLS, BudgetFeedProcess,
                                             CompetingLineage, HeredityAttachmentStep, make_kinetics,
                                             simulate_competing)

WS_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# the face
# --------------------------------------------------------------------------- #
def test_face_registers_all_six_classes():
    core = build_core()
    assert models.model_names("heredity") == sorted(HEREDITY_CLASSES)
    for n in models.model_names("heredity"):
        models.assert_face(core, "heredity", models.resolve("heredity", n))
    assert models.canonical_coverage("heredity")["uncovered"] == []
    assert set(models.axis("heredity")["model_heredity"]) == set(HEREDITY_CLASSES)


def test_assert_face_rejects_nonconformers():
    from process_bigraph import Process
    core = build_core()
    # og-06's one-class process predates the face: no budgets, no attachment -> rejected loudly
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "heredity", "local:LineageReplicatorProcess")
    assert "missing required input" in str(exc.value) and "attached" in str(exc.value)

    class WrongHeredity(Process):
        def inputs(self):
            return {"attached": "float", "stored_work": "float"}        # missing the pools

        def outputs(self):
            return {"heritability": "float", "made_up": "float"}        # foreign port, missing information

        def update(self, state, interval):
            return {}

    core.register_link("WrongHeredity", WrongHeredity)
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "heredity", "local:WrongHeredity")
    assert "made_up" in str(exc.value)
    from viva_genesis.composites.competing_heredity import competing_heredity
    with pytest.raises(KeyError):
        competing_heredity(core, model_heredity="no_such_class")


def test_every_new_class_declares_provenance_on_its_config():
    from viva_genesis.provenance import audit_config_schema
    from viva_genesis.ledger import InformationLedgerProcess
    for cls in (*HEREDITY_PROCESSES.values(), HeredityAttachmentStep, BudgetFeedProcess, InformationLedgerProcess):
        audit = audit_config_schema(cls.config_schema)
        assert not audit["undeclared"], (cls.__name__, audit["undeclared"])


# --------------------------------------------------------------------------- #
# the information estimator + its convergence check
# --------------------------------------------------------------------------- #
def test_mutual_information_estimator_and_convergence():
    rng = np.random.default_rng(0)
    x = rng.random(2000)
    assert I.heritable_bits(x, rng.random(2000)) < 0.05                 # independent -> ~0 net of null
    dep = I.mi_with_convergence(x, x + 0.02 * rng.standard_normal(2000))
    assert dep["heritable_bits"] > 1.0 and dep["converged"]            # y ~ x -> bits, converged
    assert len(dep["ladder"]) >= 3 and dep["ladder"][-1][0] == 2000
    # variation finer than the phenotype resolution is NOT information
    tiny = I.mutual_information_bits(1e-4 * x, 1e-4 * x)
    assert tiny == 0.0
    small = I.mi_with_convergence(x[:20], x[:20])
    assert not small["converged"]                                      # too few pairs is never converged
    assert I.pareto_front({"a": (1.0, 1.0), "b": (2.0, 2.0), "c": (0.5, 0.5), "d": (1.0, 2.0)}) == ["a", "b", "c"]
    ipc = I.information_per_cost(1.0, 0.0, 2.0)
    assert ipc["bits_per_joule"] == math.inf and ipc["bits_per_precursor"] == 0.5


# --------------------------------------------------------------------------- #
# the Gillespie lineage: exact budgets, inheritance vs control, Eigen threshold
# --------------------------------------------------------------------------- #
def test_lineage_budget_accounting_is_exact_and_inheritance_beats_control():
    lin = CompetingLineage("rna_like", seed=3)
    lin.pools = {p: 20000 for p in POOLS}
    lin.pool_nominal = {p: 20000 for p in POOLS}
    lin.quanta = 20000
    lin.attached = True
    for i in range(len(lin.ids)):
        lin._refresh(i)
    for _ in range(8):
        lin.advance(1.0)
    assert lin.consumed["nucleotide_precursor"] > 0 and lin.quanta_used > 0
    assert lin.pools["nucleotide_precursor"] + lin.consumed["nucleotide_precursor"] == 20000   # integer-exact
    assert lin.quanta + lin.quanta_used == 20000
    assert lin.consumed["amphiphile"] == 0 and lin.consumed["amino_precursor"] == 0            # draws only its pool
    assert lin.births >= 2 and len(lin.pairs) == lin.births and len(lin.nodes) == len(lin.ids) + lin.births

    for cls in ("rna_like", "compositional", "mineral_state"):
        on = simulate_competing(cls, n_ticks=30, attached=True, seed=1)
        off = simulate_competing(cls, n_ticks=30, attached=False, seed=1)
        assert on["info"]["heritable_bits"] > off["info"]["heritable_bits"] + 0.2, cls
        assert on["heritability"] > 0.5 > abs(off["heritability"]), cls
        assert off["consumed"][make_kinetics(cls).primary_pool] > 0        # the control PAYS for its material


def test_eigen_threshold_at_the_agent_level():
    """Function is kept above the error threshold (Q sigma > 1) and lost below it."""
    hi = simulate_competing("rna_like", n_ticks=40, attached=True, seed=2, cfg={"per_site_fidelity": 0.99})
    lo = simulate_competing("rna_like", n_ticks=40, attached=True, seed=2, cfg={"per_site_fidelity": 0.90})
    assert hi["series"][-1]["mean_function"] > 0.2 > lo["series"][-1]["mean_function"]
    assert make_kinetics("rna_like", {"per_site_fidelity": 0.99}).expected_fidelity() > 1 / 3
    assert make_kinetics("rna_like", {"per_site_fidelity": 0.90}).expected_fidelity() < 1 / 3


def test_capacity_and_costs_differ_by_class():
    caps = {c: make_kinetics(c).capacity_bits() for c in HEREDITY_CLASSES}
    assert caps["rna_like"] == 60.0 and caps["network"] == 4.0 and caps["mineral_state"] == 16.0
    assert caps["rna_like"] > caps["hybrid"] > caps["compositional"] > caps["network"]
    core = build_core()
    costs = {c: HeredityAttachmentStep(config={"heredity_class": c}, core=core).costs() for c in HEREDITY_CLASSES}
    assert costs["rna_like"] == {"pool": "nucleotide_precursor", "precursor_per_copy": 30, "quanta_per_copy": 30}
    assert costs["compositional"] == {"pool": "amphiphile", "precursor_per_copy": 1, "quanta_per_copy": 0}
    assert costs["mineral_state"]["pool"] == "mineral_precursor" and costs["mineral_state"]["quanta_per_copy"] == 0
    assert costs["network"] == {"pool": "amino_precursor", "precursor_per_copy": 1, "quanta_per_copy": 1}


# --------------------------------------------------------------------------- #
# conditional attachment
# --------------------------------------------------------------------------- #
def test_attachment_step_conditions_on_budget_and_the_eigen_floor():
    core = build_core()
    full = {**{p: 1.0e-4 for p in POOLS}, "stored_work": 8.0e-16}
    rna = HeredityAttachmentStep(config={"heredity_class": "rna_like"}, core=core)
    d = rna.decide(full)
    assert d["fidelity_ratio"] > 1 and d["precursor_ratio"] > 1 and d["energy_ratio"] > 1 and d["margin"] >= 1
    assert rna.update(full)["attached"] == 1.0
    assert rna.update({**full, "stored_work": 0.0})["attached"] == 1.0      # latched
    unlatched = HeredityAttachmentStep(config={"heredity_class": "rna_like", "latch": False}, core=core)
    assert unlatched.update({**full, "nucleotide_precursor": 0.0})["attached"] == 0.0
    assert unlatched.decide({**full, "stored_work": 0.0})["energy_ratio"] == 0.0
    # peptide at its nominal fidelity sits below the Eigen floor: refused whatever the budget
    pep = HeredityAttachmentStep(config={"heredity_class": "peptide"}, core=core)
    assert pep.decide(full)["fidelity_ratio"] < 1 and pep.update(full)["attached"] == 0.0
    pep_hi = HeredityAttachmentStep(config={"heredity_class": "peptide", "peptide_fidelity": 0.95}, core=core)
    assert pep_hi.update(full)["attached"] == 1.0
    # compositional needs no quanta: the energy condition is vacuous
    comp = HeredityAttachmentStep(config={"heredity_class": "compositional"}, core=core)
    assert comp.decide({**full, "stored_work": 0.0})["energy_ratio"] == math.inf


# --------------------------------------------------------------------------- #
# the composite + the information ledger
# --------------------------------------------------------------------------- #
def test_composite_runs_classes_with_closed_information_ledger():
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.competing_heredity import competing_heredity, PHASE7_REDUCERS
    core = build_core()
    for cls, arm in (("rna_like", "step"), ("compositional", "on"), ("network", "off")):
        sim = Composite({"state": competing_heredity(core, model_heredity=cls, attachment=arm)}, core=core)
        sim.run(12.0)
        rows = gather_emitter_results(sim)[("emitter",)]
        out = {k: fn(rows) for k, fn in PHASE7_REDUCERS.items()}
        assert max(float(r["energy_residual"]) for r in rows) <= 1e-9
        assert out["attached_fraction"] == (0.0 if arm == "off" else 1.0)
        assert rows[-1]["population"] == 32 and rows[-1]["lineage_depth"] >= 3
        if cls == "rna_like":
            assert rows[-1]["nucleotide_precursor"] < 1.0e-4 and rows[-1]["energy_used"] > 0      # budgets drawn
            assert rows[-1]["stored_work"] <= 8.0e-16 + 1e-30
        if cls == "compositional":
            assert rows[-1]["energy_used"] == 0.0 and rows[-1]["amphiphile"] < 1.0e-4           # no quanta, amphiphiles
    # the ledger certifies bits only once the estimator has converged
    from viva_genesis.ledger import InformationLedgerProcess
    led = InformationLedgerProcess(config={}, core=core)
    s = {**led.initial_state(), "stored_work": 1.0, "information_content": 0.7, "mi_converged": 0.0, "births": 2.0,
         "replication_energy": 0.1, "work_flux": 0.1}
    o = led.update(s, 1.0)
    assert o["heritable_bits"] == 0.0 and o["information_ledger_ok"] == 0.0
    o2 = led.update({**s, "mi_converged": 1.0, "stored_work": 1.0}, 1.0)
    assert o2["heritable_bits"] == 0.7 and o2["energy_residual"] <= 1e-12 and o2["bits_per_joule"] == pytest.approx(0.7 / (0.2 / 4))


# --------------------------------------------------------------------------- #
# the vg-data package and the gate evaluators
# --------------------------------------------------------------------------- #
def test_inheritance_budgets_package_loads_and_cites_real_bibkeys():
    from viva_genesis import provenance as P
    pkg = P.load_package("inheritance_budgets")
    assert {"per_site_fidelity", "template_length", "energy_quantum", "attach_min_copies", "nucleotide_feed",
            "defect_copy_error"} <= set(pkg.parameters)
    assert pkg["per_site_fidelity"].provenance is P.ProvenanceClass.MEASURED
    assert pkg["per_site_fidelity"].nominal() == pytest.approx(0.967)
    audit = pkg.audit()
    assert "attach_min_copies" in audit["hypothetical"] and "attach_energy_margin" in audit["hypothetical"]
    assert audit["unsourced"] == []
    assert pkg.observations["ribozyme_polymerase_fidelity"]["low"] == 0.96
    missing = P.check_bib(pkg, WS_ROOT / "workspace" / "references" / "papers.bib")
    assert not missing, f"inheritance_budgets cites bibkeys not in papers.bib: {missing}"


def test_information_gates_evaluate(tmp_path):
    from viva_genesis import evaluators as EV
    reg = {}
    EV.register_derived_scalars(reg)
    assert {"n_classes_ancestry_predicts", "frontier_pareto_size", "nonrna_bits_fraction", "attachment_budget_span",
            "class_heritable_bits", "heritable_bits_final", "information_ledger_ok_final"} <= set(reg)
    art = {"gates": {"n_classes_ancestry_predicts": 5, "frontier_pareto_size": 2, "frontier_span_decades": 3.1,
                     "nonrna_bits_fraction": 1.6, "attachment_budget_span": 0.8, "templated_takeover_fidelity": None},
           "classes": {"mineral_state": {"attached": {"heritable_bits": 2.3}}}, "ledger": {"energy_residual_max": 1e-16}}
    (tmp_path / "f.json").write_text(json.dumps(art))
    test = {"artifact": "f.json", "params": {"heredity_class": "mineral_state"}}
    assert reg["n_classes_ancestry_predicts"](None, test, tmp_path) == 5.0
    assert reg["frontier_pareto_size"](None, test, tmp_path) == 2.0
    assert reg["nonrna_bits_fraction"](None, test, tmp_path) == pytest.approx(1.6)
    assert reg["class_heritable_bits"](None, test, tmp_path) == pytest.approx(2.3)
    assert reg["frontier_ledger_residual_max"](None, test, tmp_path) == 1e-16
    with pytest.raises(ValueError):
        reg["templated_takeover_fidelity"](None, test, tmp_path)
