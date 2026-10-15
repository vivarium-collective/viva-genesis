"""Phase 6 — the energy_coupling face: five registered classes, loud face
rejection, the per-individual power budget, the free-energy ledger invariant
(free_energy_in >= work + dissipated with the store), the vg-data package, the
og-05 per-individual autonomy readout and the internalization-pays gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from viva_genesis import models
from viva_genesis.core import build_core

WS_ROOT = Path(__file__).resolve().parents[1]
CLASSES = ["fe_redox", "h_na_gradient_leaky_membrane", "passive_gradient", "polyphosphate", "thioester_acyl_phosphate"]


# --------------------------------------------------------------------------- #
# the face
# --------------------------------------------------------------------------- #
def test_face_registers_all_five_classes():
    core = build_core()
    assert models.model_names("energy_coupling") == CLASSES
    for n in CLASSES:
        models.assert_face(core, "energy_coupling", models.resolve("energy_coupling", n))
    assert models.canonical_coverage("energy_coupling")["uncovered"] == []
    assert "FreeEnergyLedgerProcess" in core.link_registry


def test_assert_face_rejects_nonconforming_class_at_build():
    from process_bigraph import Process

    class WrongCoupling(Process):
        def inputs(self):
            return {"electric_potential": "float", "permeability": "float"}   # missing drive, area, volume

        def outputs(self):
            return {"work": "float", "made_up": "float"}                      # foreign port, missing budget

        def update(self, state, interval):
            return {}

    core = build_core()
    core.register_link("WrongCoupling", WrongCoupling)
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "energy_coupling", "local:WrongCoupling")
    assert "missing required" in str(exc.value) and "made_up" in str(exc.value)
    from viva_genesis.composites.protocell_energetics import protocell_energetics
    with pytest.raises(KeyError):
        protocell_energetics(core, model_energy_coupling="no_such_class")


def test_every_class_declares_provenance_on_its_config():
    from viva_genesis.provenance import audit_config_schema
    from viva_genesis.bioenergetics.energy_coupling import ENERGY_COUPLING_CLASSES
    from viva_genesis.ledger import FreeEnergyLedgerProcess
    for cls in list(ENERGY_COUPLING_CLASSES.values()) + [FreeEnergyLedgerProcess]:
        audit = audit_config_schema(cls.config_schema)
        assert not audit["undeclared"], (cls.__name__, audit["undeclared"])


# --------------------------------------------------------------------------- #
# the power budget and the ledger invariant
# --------------------------------------------------------------------------- #
def _run(core, n=150, **kw):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.protocell_energetics import protocell_energetics
    sim = Composite({"state": protocell_energetics(core, **kw)}, core=core)
    sim.run(float(n))
    return gather_emitter_results(sim)[("emitter",)]


def test_free_energy_ledger_invariant_holds_on_every_class():
    core = build_core()
    for cls in CLASSES:
        for a in (0.0, 1.0):
            rows = _run(core, model_energy_coupling=cls, coupling_activity=a)
            last = rows[-1]
            assert last["free_energy_ledger_ok"] == 1.0, (cls, a, last)
            assert last["free_energy_residual_max"] <= 1e-9
            assert last["second_law_margin_min"] >= -1e-9 * max(last["free_energy_in_total"], 1e-30)
            assert last["dissipation_min"] >= 0.0 and 0.0 <= last["capture_efficiency"] <= 1.0
            # the per-tick identity in = work + dissipated + dE
            for r in rows[2:]:
                assert r["free_energy_in"] >= 0.0 and r["dissipated"] >= 0.0 and r["work"] >= 0.0
                assert r["energy_stored"] >= -1e-30
            assert 0.0 <= last["autonomy"] <= 1.0


def test_ledger_catches_a_violation():
    from viva_genesis.ledger import FreeEnergyLedgerProcess
    core = build_core()
    led = FreeEnergyLedgerProcess(config={}, core=core)
    led.update(led.initial_state(), 1.0)
    # a class claiming more work + dissipation than it drew (and a store that does not shrink)
    out = led.update({"free_energy_in": 1.0, "work": 2.0, "dissipated": 0.5, "energy_stored": 0.0}, 1.0)
    assert out["free_energy_ledger_ok"] == 0.0 and out["second_law_margin"] < 0.0 and out["capture_efficiency"] > 1.0
    neg = FreeEnergyLedgerProcess(config={}, core=core)
    neg.update(neg.initial_state(), 1.0)
    out = neg.update({"free_energy_in": 1.0, "work": 0.5, "dissipated": -0.5, "energy_stored": 1.0}, 1.0)
    assert out["free_energy_ledger_ok"] == 0.0 and out["dissipation_min"] < 0.0


def test_classes_differ_structurally_at_the_nominal_membrane():
    """The store physics discriminates: the thioester carrier clears the 30 kJ/mol
    load and pays; the passive baseline has no internal power; the ion-gradient
    store drains through the Na+ leak at P_H = 1e-6 m/s; polyphosphate's 20 kJ/mol
    bond sits below the load."""
    core = build_core()
    passive = _run(core, model_energy_coupling="passive_gradient", coupling_activity=1.0)[-1]
    thio = _run(core, model_energy_coupling="thioester_acyl_phosphate", coupling_activity=1.0)[-1]
    ion = _run(core, model_energy_coupling="h_na_gradient_leaky_membrane", coupling_activity=1.0)[-1]
    poly = _run(core, model_energy_coupling="polyphosphate", coupling_activity=1.0)[-1]
    assert passive["internal_power"] == 0.0 and passive["autonomy"] == 0.0 and passive["maintenance_power"] == pytest.approx(1e-19)
    assert thio["internal_power"] > 0.0 and thio["autonomy"] > 0.1 and thio["net_power"] > passive["net_power"]
    assert thio["store_potential"] > 30.0
    assert ion["store_potential"] < 30.0 and ion["internal_power"] == 0.0 and ion["net_power"] < passive["net_power"]
    assert poly["store_potential"] < 30.0 and poly["internal_power"] == 0.0
    # tighten the membrane: the ion store holds and the ion class starts to pay
    tight = _run(core, model_energy_coupling="h_na_gradient_leaky_membrane", coupling_activity=1.0, permeability=1e-8)[-1]
    assert tight["store_potential"] > ion["store_potential"] and tight["internal_power"] > 0.0


def test_chemical_store_rests_at_equilibrium_and_leaks_toward_it():
    from viva_genesis.bioenergetics.energy_coupling import ThioesterCouplingProcess, PolyphosphateCouplingProcess
    core = build_core()
    for cls in (ThioesterCouplingProcess, PolyphosphateCouplingProcess):
        p = cls(config={}, core=core)
        T = 322.15
        q_eq = p._q_rest(T)
        assert abs(p._store_mu(q_eq, T)) < 1e-9                     # mu(q_eq) = 0
        assert p._store_G(q_eq, 1e-18, T) == 0.0
        for q in (0.0, 1e-4, 0.1, 0.5, 0.99):
            assert p._store_G(q, 1e-18, T) >= 0.0                   # never below the minimum
        st = {"electric_potential": 0.0, "drive_free_energy": 0.0, "permeability": 1e-6,
              "membrane_area": 3e-12, "compartment_volume": 5e-16}
        p._q = 0.5
        out = p.update(st, 10.0)
        assert out["dissipated"] > 0.0 and out["internal_power"] >= 0.0 and p._q < 0.5    # leak dissipates, charge falls


# --------------------------------------------------------------------------- #
# the vg-data package
# --------------------------------------------------------------------------- #
def test_energy_currencies_package_loads_and_cites_real_bibkeys():
    from viva_genesis import provenance as P
    pkg = P.load_package("energy_currencies")
    assert {"external_pmf", "h_permeability", "na_h_permeability_ratio", "fe_disproportionation_drive",
            "thioester_bond", "polyphosphate_bond", "load_free_energy", "maintenance_active"} <= set(pkg.parameters)
    for p in pkg:
        assert p.units and p.provenance in P.ProvenanceClass
    audit = pkg.audit()
    assert "fe_disproportionation_drive" in audit["hypothetical"]
    assert "h_permeability" in audit["extrapolated"]
    assert audit["counts"]["calibrated"] >= 1 and audit["unsourced"] == []
    assert pkg.observations["vent_ocean_ph_gradient"]["low"] == 3.0
    missing = P.check_bib(pkg, WS_ROOT / "workspace" / "references" / "papers.bib")
    assert not missing, f"energy_currencies cites bibkeys not in papers.bib: {missing}"


# --------------------------------------------------------------------------- #
# og-05: the per-individual autonomy readout beside the population-mean internalization
# --------------------------------------------------------------------------- #
def test_og05_publishes_per_individual_autonomy():
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.bioenergetic_internalization import bioenergetic_internalization
    core = build_core()
    sim = Composite({"state": bioenergetic_internalization(core=core)}, core=core)
    sim.run(40)
    rows = gather_emitter_results(sim)[("emitter",)]
    assert rows[-1]["autonomy"] > 0.6 and rows[-1]["internalization"] > 0.6        # both read the same field
    assert all(0.0 <= r["autonomy"] <= 1.0 for r in rows)
    weak = Composite({"state": bioenergetic_internalization(core=core, catalyst_efficiency=0.3)}, core=core)
    weak.run(40)
    assert gather_emitter_results(weak)[("emitter",)][-1]["autonomy"] < rows[-1]["autonomy"]


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #
def test_internalization_pays_gate_evaluates(tmp_path):
    from viva_genesis.uq import energetics_threshold as ET
    from viva_genesis.uq.report import decision_discipline
    from viva_genesis import evaluators
    res = ET.internalization_map(axes={"coupling_activity": [0.0, 0.3, 1.0], "permeability": [1e-8, 1e-6],
                                       "electric_potential": [0.216, 0.02]}, n_steps=120)
    assert res.categorical_axes() == [ET.CLASS_AXIS] and res.shape == (5, 3, 2, 2)
    att = ET.attribute_thresholds(res)
    for c in att["classes"]:
        assert att["per_class"][c]["ledger"]["all_ok"] and att["per_class"][c]["n_failed"] == 0
    assert att["per_class"]["passive_gradient"]["pays_fraction"] == 0.0
    thio = att["per_class"]["thioester_acyl_phosphate"]["nominal"]
    assert thio["threshold_activity"] is not None and thio["autonomy_at_threshold"] > 0.0
    sa = att["cross_class"]["structure_agreement_pays"]
    assert 0.0 <= sa["agreement"] <= 1.0
    rep = ET.energetics_report(res, att)
    assert rep.gate == "internalization-pays" and rep.feasibility.feasible
    assert isinstance(decision_discipline(rep), list)
    traj = ET.budget_trajectories(classes=("passive_gradient", "thioester_acyl_phosphate"), activities=(1.0,), n_steps=20, every=5)
    paths = ET.save_artifacts(res, att, rep, tmp_path, trajectories=traj)
    art = json.loads(paths["report"].read_text())
    assert art["attribution"]["cross_class"]["n_classes_paying_at_nominal"] >= 1
    reg = {}
    evaluators.register_derived_scalars(reg)
    test = {"artifact": str(paths["report"]), "params": {"class": "thioester_acyl_phosphate"}}
    assert reg["n_classes_paying_at_nominal"](None, test, None) >= 1.0
    assert 0.0 < reg["internalization_threshold_activity"](None, test, None) <= 1.0
    assert reg["autonomy_at_threshold"](None, test, None) > 0.0
    assert reg["threshold_map_ledger_all_ok"](None, test, None) == 1.0
    assert 0.0 <= reg["internalization_structure_agreement"](None, test, None) <= 1.0
    # the figures render from the artifacts
    from viva_genesis.viz_energetics import energy_budget_figure, threshold_map_figure
    mmap = json.loads(paths["threshold_map"].read_text())
    assert "plotly" in threshold_map_figure(mmap, art) and "plotly" in energy_budget_figure(art)
