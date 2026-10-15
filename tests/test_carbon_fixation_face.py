"""Phase 2 — the carbon_fixation face: three registered classes, loud face
rejection, real Butler-Volmer cell physics, the charge + electron ledger
invariant, the circuit-derived gradient efficiency, the vg-data package and the
failure-mode-attributed gate evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from viva_genesis import models
from viva_genesis.core import build_core

WS_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# the face
# --------------------------------------------------------------------------- #
def test_face_registers_all_three_classes():
    core = build_core()
    assert models.model_names("carbon_fixation") == ["butler_volmer", "empirical", "microkinetic"]
    for n in models.model_names("carbon_fixation"):
        models.assert_face(core, "carbon_fixation", models.resolve("carbon_fixation", n))
    # og-01's original process also honours the face (the empirical class wraps it)
    models.assert_face(core, "carbon_fixation", "local:CarbonFixationProcess")
    assert models.canonical_coverage("carbon_fixation")["uncovered"] == []


def test_assert_face_rejects_nonconforming_class_at_build():
    from process_bigraph import Process

    class WrongFixation(Process):
        def inputs(self):
            return {"H2": "float", "CO2": "float"}            # missing temperature, catalyst, pools

        def outputs(self):
            return {"formate": "float", "made_up": "float"}   # foreign port, missing acetate/pyruvate/flux

        def update(self, state, interval):
            return {}

    core = build_core()
    core.register_link("WrongFixation", WrongFixation)
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "carbon_fixation", "local:WrongFixation")
    assert "missing required" in str(exc.value) and "made_up" in str(exc.value)
    # and through the composite path: an unregistered class name fails loudly at resolve time
    from viva_genesis.composites.electrochemical_interface import electrochemical_carbon_fixation
    with pytest.raises(KeyError):
        electrochemical_carbon_fixation(core, model_carbon_fixation="no_such_class")


def test_every_new_class_declares_provenance_on_its_config():
    from viva_genesis.provenance import audit_config_schema
    from viva_genesis.electrochemistry import (ButlerVolmerCarbonFixationProcess, EmpiricalCarbonFixationProcess,
                                               MicrokineticCarbonFixationProcess, MineralConductivityProcess)
    from viva_genesis.ledger import ChargeLedgerProcess
    for cls in (ButlerVolmerCarbonFixationProcess, EmpiricalCarbonFixationProcess,
                MicrokineticCarbonFixationProcess, MineralConductivityProcess, ChargeLedgerProcess):
        audit = audit_config_schema(cls.config_schema)
        assert not audit["undeclared"], (cls.__name__, audit["undeclared"])


# --------------------------------------------------------------------------- #
# Butler-Volmer cell physics
# --------------------------------------------------------------------------- #
def test_cell_partitions_its_driving_force_and_respects_faradaic_bound():
    from viva_genesis.electrochemistry.butler_volmer import default_cell_kwargs, solve_cell
    s = solve_cell(**default_cell_kwargs())
    assert s.j > 0.0 and s.iv_residual < 1.0e-10
    assert 0.0 <= s.faradaic_efficiency <= 1.0
    assert abs(sum(s.losses.values()) - 1.0) < 1.0e-9           # the four fractions partition emf_fresh
    assert abs(s.eta_anode + s.eta_cathode + s.ohmic_drop - s.emf) < 1.0e-9   # Kirchhoff voltage law
    assert 1.0e-5 <= s.j <= 1.0e-2                               # inside the Altair-2025 window


def test_cell_limitations_move_with_the_physics():
    from viva_genesis.electrochemistry.butler_volmer import default_cell_kwargs, solve_cell
    nominal = solve_cell(**default_cell_kwargs())
    insulating = solve_cell(**default_cell_kwargs(conductivity=1.0e-9))
    starved = solve_cell(**default_cell_kwargs(h2=1.0e-8))
    loaded = solve_cell(**default_cell_kwargs(formate=1.0e-3))
    reversed_gradient = solve_cell(**default_cell_kwargs(pH_vent=2.0, h2=1.0e-6, formate=1.0))
    assert insulating.limitation == "electrical" and insulating.j < nominal.j
    assert starved.limitation == "transport" and starved.j < nominal.j
    assert loaded.losses["thermodynamic"] > nominal.losses["thermodynamic"] and loaded.emf < nominal.emf
    assert reversed_gradient.j == 0.0 and reversed_gradient.limitation == "thermodynamic"
    # Ni raises the CO2-reduction exchange current (Preiner hierarchy), hence the current
    assert solve_cell(**default_cell_kwargs(ni_fraction=0.0)).j < nominal.j


def test_nernst_potentials_shift_with_ph_and_h2():
    from viva_genesis.electrochemistry.butler_volmer import R, F, T_REF, equilibrium_potentials
    ea1, ec1, _ = equilibrium_potentials(T_REF, 9.5, 6.0, 5e-3, 2e-3, 1e-9, 1e-7)
    ea2, _, _ = equilibrium_potentials(T_REF, 10.5, 6.0, 5e-3, 2e-3, 1e-9, 1e-7)
    ea3, _, _ = equilibrium_potentials(T_REF, 9.5, 6.0, 5e-2, 2e-3, 1e-9, 1e-7)
    rt_f = R * T_REF / F
    assert abs((ea1 - ea2) - np.log(10) * rt_f) < 1e-9          # 1 pH unit = (RT/F) ln10
    assert abs((ea1 - ea3) - 0.5 * rt_f * np.log(10.0)) < 1e-9  # 10x H2 = (RT/2F) ln10
    assert ec1 > ea1                                             # the fresh cell is spontaneous


# --------------------------------------------------------------------------- #
# the circuit-derived gradient efficiency
# --------------------------------------------------------------------------- #
def test_mineral_conductivity_derives_gradient_efficiency():
    from viva_genesis.electrochemistry.mineral_conductivity import MineralConductivityProcess, circuit_efficiency
    effs = [circuit_efficiency(conductivity=s, layer_thickness=1e-3)["gradient_efficiency"]
            for s in (1e-9, 1e-7, 1e-5, 1e-3)]
    assert all(b >= a for a, b in zip(effs, effs[1:]))          # monotone in conductivity
    assert effs[0] < 0.05 and effs[-1] > 0.99                    # insulator collapses it, conductor delivers it
    p = MineralConductivityProcess(config={}, core=build_core())
    out = p.update({**p.initial_state(), "conductivity": 1e-7}, 1.0)
    assert 0.0 < out["gradient_efficiency"] < 1.0 and out["areal_resistance"] > 0.0


# --------------------------------------------------------------------------- #
# the charge + electron ledger
# --------------------------------------------------------------------------- #
def test_charge_ledger_invariant_holds_on_the_cell_and_catches_violations():
    from viva_genesis.electrochemistry.butler_volmer import ButlerVolmerCarbonFixationProcess
    from viva_genesis.ledger import ChargeLedgerProcess
    core = build_core()
    bv = ButlerVolmerCarbonFixationProcess(config={"dilution_rate": 2.0}, core=core)
    led = ChargeLedgerProcess(config={}, core=core)
    st = bv.initial_state()
    for conductivity in (1e-3, 1e-9):                           # including the local-H2-oxidation corner
        st["conductivity"] = conductivity
        for _ in range(5):
            o = bv.update(st, 1.0)
            st["formate"] += o["formate"]
            lo = led.update({k: o[k] for k in ("electron_flux", "carbon_electron_flux", "her_electron_flux", "iv_residual")}, 1.0)
            assert lo["charge_residual"] <= 1e-9 and lo["faradaic_efficiency"] <= 1.0 + 1e-12
            assert lo["charge_ledger_ok"] == 1.0
    # a class that claims more carbon electrons than it supplies is caught
    bad = ChargeLedgerProcess(config={}, core=core)
    lo = bad.update({"electron_flux": 1.0, "carbon_electron_flux": 2.0, "her_electron_flux": 0.0, "iv_residual": 0.0}, 1.0)
    assert lo["faradaic_efficiency"] == 2.0 and lo["charge_residual"] == 1.0 and lo["charge_ledger_ok"] == 0.0


def test_empirical_class_is_og01_kinetics_with_attribution():
    from process_bigraph import allocate_core
    from viva_genesis.electrochemistry.empirical import EmpiricalCarbonFixationProcess
    from viva_genesis.protometabolism.carbon_fixation import CarbonFixationProcess
    core = allocate_core()
    emp = EmpiricalCarbonFixationProcess(config={}, core=core)
    og = CarbonFixationProcess(config={}, core=core)
    st = og.initial_state()
    a, b = emp.update({**st, "ni_fraction": 0.75}, 1.0), og.update(st, 1.0)
    for k in ("formate", "acetate", "pyruvate", "net_carbon_flux"):
        assert a[k] == pytest.approx(b[k])                      # at the reference Ni it IS og-01
    assert a["faradaic_efficiency"] == 1.0 and a["her_electron_flux"] == 0.0
    assert a["electron_flux"] == pytest.approx(a["carbon_electron_flux"])
    assert {a["limitation_code"]} <= {0.0, 1.0, 2.0, 3.0}
    fe_only = emp.update({**st, "ni_fraction": 0.0}, 1.0)
    assert fe_only["formate"] < a["formate"] and fe_only["loss_catalytic"] > a["loss_catalytic"]


def test_microkinetic_builds_and_face_checks_but_needs_pixi():
    from viva_genesis.electrochemistry.microkinetic import (MicrokineticBackendMissing,
                                                           MicrokineticCarbonFixationProcess, backend_available)
    core = build_core()
    models.resolve_checked(core, "carbon_fixation", "microkinetic")
    p = MicrokineticCarbonFixationProcess(config={}, core=core)
    if backend_available() is not None:
        pytest.skip("a microkinetic backend is installed; the bridge is a NEXT_STEPS item")
    with pytest.raises(MicrokineticBackendMissing) as exc:
        p.update(p.initial_state(), 1.0)
    assert "pixi" in str(exc.value) and "mock" in str(exc.value)


# --------------------------------------------------------------------------- #
# the vg-data package
# --------------------------------------------------------------------------- #
def test_electrochemical_interface_package_loads_and_cites_real_bibkeys():
    from viva_genesis import provenance as P
    pkg = P.load_package("electrochemical_interface")
    assert {"j0_co2", "ni_fraction", "layer_thickness", "conductivity", "boundary_layer"} <= set(pkg.parameters)
    for p in pkg:
        assert p.units and p.provenance in P.ProvenanceClass
    audit = pkg.audit()
    assert "h2_ocean" in audit["hypothetical"] and "h2_ocean" not in audit["unsourced"]
    assert audit["counts"]["calibrated"] >= 3
    assert pkg.observations["cell_current_density"]["low"] == 1.0e-5
    missing = P.check_bib(pkg, WS_ROOT / "workspace" / "references" / "papers.bib")
    assert not missing, f"electrochemical_interface cites bibkeys not in papers.bib: {missing}"


# --------------------------------------------------------------------------- #
# the composite and the gate
# --------------------------------------------------------------------------- #
def test_composite_runs_both_classes_with_closed_ledger():
    pytest.importorskip("fipy")
    pytest.importorskip("equilibrator_api")
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.electrochemical_interface import (PHASE2_REDUCERS, electrochemical_carbon_fixation,
                                                                   limitation_name)
    core = build_core()
    for cls in ("butler_volmer", "empirical"):
        doc = electrochemical_carbon_fixation(core, model_carbon_fixation=cls, dilution_rate=2.0, nx=8)
        sim = Composite({"state": doc}, core=core)
        sim.run(6.0)
        rows = gather_emitter_results(sim)[("emitter",)]
        out = {k: fn(rows) for k, fn in PHASE2_REDUCERS.items()}
        assert out["charge_ledger_ok"] == 1.0 and out["charge_residual_max"] <= 1e-9
        assert out["faradaic_efficiency_max"] <= 1.0 + 1e-12
        assert out["sustained_throughput"] > 0.0
        assert limitation_name(out["limitation_code"]) in ("thermodynamic", "electrical", "catalytic", "transport")
    # the knob is gone: gradient_efficiency is derived from the circuit
    ins = electrochemical_carbon_fixation(core, model_carbon_fixation="empirical", conductivity=1e-9)
    assert ins["gradient"]["config"]["gradient_efficiency"] < 0.05
    assert electrochemical_carbon_fixation(core, model_carbon_fixation="empirical")["gradient"]["config"]["gradient_efficiency"] > 0.99


def test_failure_mode_attributed_gate_evaluates(tmp_path):
    pytest.importorskip("fipy")
    pytest.importorskip("equilibrator_api")
    from viva_genesis.uq import electrochemistry_calibration as EC
    from viva_genesis.uq.report import decision_discipline
    from viva_genesis import evaluators
    res = EC.mechanism_map(axes={"ph_vent": [7.0, 9.5], "h2": [1e-8, 5e-3], "conductivity": [1e-9, 1e-3],
                                 "ni_fraction": [0.75]}, n_steps=4, nx=8)
    assert res.categorical_axes() == [EC.CLASS_AXIS] and res.shape == (2, 2, 2, 2, 1)
    att = EC.attribute_mechanisms(res)
    for c in ("empirical", "butler_volmer"):
        assert att["per_class"][c]["label_coverage"] == 1.0
        assert att["per_class"][c]["ledger"]["all_ok"]
        assert sum(att["per_class"][c]["label_counts"].values()) == 8
    cross = att["cross_class"]
    assert 0.0 <= cross["label_agreement_all"] <= 1.0
    fav = cross["label_agreement_favorable"]
    assert fav is None or np.isnan(fav) or 0.0 <= fav <= 1.0
    rep = EC.electrochemistry_report(res, att)
    assert rep.gate == "failure-mode-attributed" and "microkinetic (deferred)" in rep.model_classes
    assert isinstance(decision_discipline(rep), list)
    paths = EC.save_artifacts(res, att, rep, tmp_path)
    art = json.loads(paths["report"].read_text())
    assert art["nominal_cell"]["limitation"] in EC.LABELS and len(art["polarization"]["j"]) == 40
    # the derived evaluators the study's gates use read that artifact
    reg = {}
    evaluators.register_derived_scalars(reg)
    test = {"artifact": str(paths["report"])}
    assert reg["failure_mode_label_coverage"](None, test, None) == 1.0
    assert reg["mechanism_map_ledger_all_ok"](None, test, None) == 1.0
    assert 0.0 <= reg["failure_mode_agreement_all"](None, test, None) <= 1.0
