"""Phase 9 — the integrated autonomy world: it assembles from the merged faces,
the ablation withdraws the drivers, every ledger holds over the integrated world,
the structural-event log records the rewrites, the ensemble runs across
structures, the minimum-sufficient-innovation-set gate evaluates, the vg-data
package carries the Phase-1 posterior, and the additive foundation ports keep
the earlier phases' behaviour."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from viva_genesis import models
from viva_genesis.core import build_core
from viva_genesis.autonomy import integrated as IA
from viva_genesis.uq import robust_innovation as RI

WS_ROOT = Path(__file__).resolve().parents[1]
SIMS = WS_ROOT / "workspace" / "studies" / "og-08-alt-robust-innovation-set" / "sims"


@pytest.fixture(autouse=True)
def _quiet_roadrunner():
    import roadrunner
    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)


def _run(core, n_ticks=40, tick=60.0, **kw):
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.integrated_autonomy import integrated_autonomy_world
    sim = Composite({"state": integrated_autonomy_world(core, tick_seconds=tick, **kw)}, core=core)
    sim.run(float(n_ticks) * tick)
    return gather_emitter_results(sim)[("emitter",)]


# --------------------------------------------------------------------------- #
# the world assembles from the merged faces; the knockouts are validated
# --------------------------------------------------------------------------- #
def test_world_assembles_from_every_face_and_rejects_bad_classes():
    from viva_genesis.composites.integrated_autonomy import integrated_autonomy_world, relative_leak
    core = build_core()
    doc = integrated_autonomy_world(core)
    nodes = {k for k, v in doc.items() if isinstance(v, dict) and v.get("_type") in ("process", "step")}
    assert {"ablation", "drivers", "serpentinization", "conservation_ledger", "fixation", "charge_ledger", "localization",
            "network_cell-0", "coupling", "active_import", "element_ledger", "network_ledger", "boundary_class", "energy",
            "free_energy_ledger", "maintenance_demand", "heredity_class", "heredity_attachment", "lineage_supply",
            "information_ledger", "lineage_state", "autonomy_budget", "population_budget", "division", "rewrite_ledger",
            "lineage_stats", "event_log", "emitter"} <= nodes
    assert doc["ablation"]["_type"] == "step" and doc["ablation"]["address"] == "local:AblationStep"
    assert doc["energy"]["address"] == models.resolve("energy_coupling", "thioester_acyl_phosphate")
    assert doc["heredity_class"]["address"] == models.resolve("heredity", "rna_like")
    assert doc["energy"]["config"]["coupling_activity"] == 1.0
    assert "coupling_activity" not in integrated_autonomy_world(core, pump="off")["energy"]["config"]   # the knockout
    assert "heredity_attachment" not in integrated_autonomy_world(core, heredity="off")
    assert integrated_autonomy_world(core, importer="off")["active_import"]["config"]["importer"] == "off"
    assert "enrichment_adapter" in integrated_autonomy_world(core, model_localization="surrogate")
    with pytest.raises(ValueError):
        integrated_autonomy_world(core, model_energy_coupling="passive_gradient")     # the pump knockout, not a storage model
    with pytest.raises(ValueError):
        integrated_autonomy_world(core, maintenance_law="free_lunch")
    with pytest.raises(KeyError):
        integrated_autonomy_world(core, model_heredity="lamarckian")
    # the permeability assumption: boundary class x anchor
    leak = relative_leak(core, "thioester_aminothiol", temperature=322.15)
    assert leak["relative_leak"] == 100.0 and relative_leak(core, "single_chain", temperature=322.15)["relative_leak"] == 1.0
    mixed = relative_leak(core, "mixed", temperature=322.15)["relative_leak"]
    assert 1.0 < mixed < 2.0
    perm = integrated_autonomy_world(core, permeability_anchor="measured")["coupling"]["config"]
    perm0 = doc["coupling"]["config"]
    assert perm["p_monoacid"] == pytest.approx(1.0e-3 * perm0["p_monoacid"]) and perm["p_gas"] == perm0["p_gas"]


def test_every_new_class_declares_provenance_on_its_config():
    from viva_genesis.provenance import audit_config_schema
    for cls in (IA.AblationStep, IA.GeologicalDriverStep, IA.EnrichmentAdapterStep, IA.LineageStateProcess,
                IA.ActiveImportProcess, IA.MaintenanceDemandProcess, IA.LineageSupplyProcess, IA.AutonomyBudgetStep,
                IA.PopulationBudgetProcess, IA.StructuralEventLogStep):
        audit = audit_config_schema(cls.config_schema)
        assert not audit["undeclared"], (cls.__name__, audit["undeclared"])


def test_foundation_ports_are_additive():
    """The optional ports keep the Phase-6 / Phase-8 behaviour when unwired."""
    from viva_genesis.bioenergetics.energy_coupling import ThioesterCouplingProcess
    from viva_genesis.ecology.proto_ecology import ProtocellNetworkProcess
    from viva_genesis.ledger import RewriteLedgerProcess
    core = build_core()
    for face in ("energy_coupling", "proto_ecology"):
        for name in models.model_names(face):
            models.assert_face(core, face, models.resolve(face, name))
        assert models.canonical_coverage(face)["uncovered"] == []
    p = ThioesterCouplingProcess(config={"coupling_activity": 1.0, "seconds_per_tick": 10.0}, core=core)
    st = {"electric_potential": 0.2, "drive_free_energy": 50.0, "permeability": 1e-6, "membrane_area": 3e-12,
          "compartment_volume": 5e-16, "temperature": 322.15, "catalyst_activity": 1.0}
    full = p.update(dict(st), 1.0)
    p2 = ThioesterCouplingProcess(config={"coupling_activity": 1.0, "seconds_per_tick": 10.0}, core=core)
    half = p2.update({**st, "drive_availability": 0.5}, 1.0)
    assert half["free_energy_in"] < full["free_energy_in"] and half["external_power"] == full["external_power"]
    net = ProtocellNetworkProcess(config={"lineage": "generalist"}, core=core)
    feed = {"CO2": 1.4e-3, "H2": 1.08e-2, "X_AKM": 1.0e-4}
    o1 = net.update({"internal": dict(feed)}, 1.0)
    net2 = ProtocellNetworkProcess(config={"lineage": "generalist"}, core=core)
    o2 = net2.update({"internal": dict(feed), "catalyst_activity": 0.01}, 1.0)
    assert o2["rule_flux"]["co2_reduction"] < o1["rule_flux"]["co2_reduction"]     # the mineral rules slow without catalysis
    assert o2["rule_flux"]["aldol"] == pytest.approx(o1["rule_flux"]["aldol"], rel=0.5)   # the base-catalysed ones do not
    led = RewriteLedgerProcess(config={}, core=core)
    agents = {"a": {"internal_amounts": {"c": 1.0}}}
    led.update({"agents": agents, "localized": {}, "partition_residual": 0.0, "removed_matter": 0.0}, 1.0)
    out = led.update({"agents": {"a": {"internal_amounts": {"c": 1.5}}}, "localized": {}, "partition_residual": 0.0,
                      "removed_matter": 0.0, "external_flux": 0.5}, 1.0)
    assert out["rewrite_residual"] == 0.0 and out["rewrite_ok"] == 1.0


# --------------------------------------------------------------------------- #
# the active-uptake rule: conserving, regulated, budgeted, costed
# --------------------------------------------------------------------------- #
def test_active_uptake_rule_conserves_regulates_and_charges():
    from viva_genesis.ecology.reactive_system import ActiveUptakeRule, BigraphicalReactiveSystem, RuleContext
    el = {"A": {"C": 3, "N": 0, "P": 0}}
    def ctx(c_in, budget=None, target=None):
        agents = {"a": {"volume": 5e-16, "cell": "c0", "internal": {"A": c_in}, "k": {}, "lineage": "x",
                        "importer": {"A": 1e-19}}}
        cells = {"c0": {"A": 1e-6}}
        c = RuleContext(agents=agents, cells=cells, cell_volume=5e-15, background={"c0": {"A": 1e-6}}, elements=el, dt=60.0)
        if budget is not None:
            c.import_budget = budget
        return c, agents, cells
    sys_ = BigraphicalReactiveSystem(rules=[ActiveUptakeRule(k_m=1e-6, efficiency=0.5, rt_j=2.68e3, max_ratio=100.0)])
    c, agents, cells = ctx(0.0)
    before = agents["a"]["internal"]["A"] * 5e-16 + cells["c0"]["A"] * 5e-15
    out = sys_.fire(c)
    after = agents["a"]["internal"]["A"] * 5e-16 + cells["c0"]["A"] * 5e-15
    assert out["counts"]["active_uptake"] == 1 and after == pytest.approx(before, rel=1e-12)
    assert agents["a"]["internal"]["A"] > 0 and c.import_energy == 0.0            # downhill: free
    c2, agents2, _ = ctx(1e-5)                                                     # uphill 10x: costs RT ln 10 / 0.5
    sys_.fire(c2)
    assert c2.import_energy > 0.0
    c3, agents3, _ = ctx(1e-5, budget=0.0)                                         # no budget: nothing moves
    assert sys_.fire(c3)["counts"]["active_uptake"] == 0 and agents3["a"]["internal"]["A"] == 1e-5
    c5, agents5, cells5 = ctx(1e-5, budget=1e-24)                                  # a small budget: a partial, conserving move
    sys_.fire(c5)
    assert 0.0 < c5.import_energy <= 1e-24 + 1e-36
    assert agents5["a"]["internal"]["A"] * 5e-16 + cells5["c0"]["A"] * 5e-15 == pytest.approx(1e-5 * 5e-16 + 1e-6 * 5e-15, rel=1e-12)
    sys_t = BigraphicalReactiveSystem(rules=[ActiveUptakeRule(targets={"A": 1e-7})])
    c4, _, _ = ctx(2e-7)                                                           # above its set-point: idle
    assert sys_t.fire(c4)["counts"]["active_uptake"] == 0
    c6, agents6, _ = ctx(0.0)                                                      # below it: fills to the set-point, no further
    sys_t.fire(c6)
    assert agents6["a"]["internal"]["A"] == pytest.approx(1e-7)


# --------------------------------------------------------------------------- #
# the ablation and the lineage state, in isolation
# --------------------------------------------------------------------------- #
def test_ablation_schedule_and_generic_control():
    core = build_core()
    ab = IA.AblationStep(config={"start": 100.0, "duration": 200.0, "feed_floor": 0.01, "mineral_floor": 0.01}, core=core)
    o0 = ab.update({"global_time": 0.0})
    assert o0["gradient_support"] == 1.0 and o0["ablation_phase"] == 0.0 and "events" in o0
    o1 = ab.update({"global_time": 200.0})
    assert o1["ablation_phase"] == 1.0 and 0.0 < o1["feed_support"] < 1.0
    o2 = ab.update({"global_time": 400.0})
    assert o2["ablation_phase"] == 2.0 and o2["gradient_support"] == 0.0 and o2["feed_support"] == pytest.approx(0.01)
    assert sorted(v["kind"] for v in {**o0.get("events", {}), **o1.get("events", {}), **o2.get("events", {})}.values()) \
        == ["ablation_complete", "ablation_started", "world_assembled"]
    gen = IA.AblationStep(config={"environment": "generic", "feed_floor": 0.01, "mineral_floor": 0.01}, core=core)
    g = gen.update({"global_time": 0.0})
    assert g["gradient_support"] == 0.0 and g["feed_support"] == pytest.approx(0.01) and g["ablation_phase"] == 2.0
    ls = IA.LineageStateProcess(config={"function_reference": 0.25, "k_h2": 1e-5, "k_org": 1e-5}, core=core)
    on_mineral = ls.update({"mean_function": 0.5, "mineral_access": 1.0, "internal": {"H2": 1e-2}}, 60.0)
    off = ls.update({"mean_function": 0.1, "mineral_access": 0.0, "internal": {"H2": 1e-5}}, 60.0)
    assert on_mineral["machinery"] == 1.0 and on_mineral["catalysis_total"] == 1.0 and on_mineral["autonomy_information"] == 0.0
    assert off["machinery"] == pytest.approx(0.4) and off["catalysis_total"] == pytest.approx(0.4)
    assert off["autonomy_information"] == 1.0 and off["drive_availability"] == pytest.approx(0.5 * 0.4)
    m = IA.MaintenanceDemandProcess(config={"law": "leak_repair", "coupling_activity": 1.0}, core=core)
    assert m.update({"machinery": 0.5, "relative_leak": 10.0}, 60.0)["maintenance_power"] == pytest.approx(1e-19 + 5e-18 * 10.0)
    t = IA.MaintenanceDemandProcess(config={"law": "turnover", "coupling_activity": 1.0}, core=core)
    assert t.update({"machinery": 0.5, "relative_leak": 10.0}, 60.0)["maintenance_power"] == pytest.approx(1e-19 + 2.5e-18)


# --------------------------------------------------------------------------- #
# the world runs: every ledger holds, the rewrites are logged, the knockout differs
# --------------------------------------------------------------------------- #
def test_world_runs_with_every_ledger_closed_and_events_logged():
    from viva_genesis.composites.integrated_autonomy import LEDGER_FLAGS, PHASE9_REDUCERS, worst_residuals
    core = build_core()
    rows = _run(core, n_ticks=60, ablation_start=600.0, ablation_duration=1200.0, feed_floor=0.1)
    last = rows[-1]
    assert last["ablation_phase"] == 2.0 and last["gradient_support"] == 0.0 and last["feed_support"] == pytest.approx(0.1)
    for k in LEDGER_FLAGS:
        if k != "information_ledger_ok":
            assert last[k] == 1.0, k
    res = worst_residuals(rows)
    assert res["geology_mass"] == 0.0 and res["element"] == 0.0 and res["rewrite"] <= 1e-30 and res["partition"] == 0.0
    assert res["C"] <= 1e-4 and res["free_energy"] <= 1e-9 and res["information_energy"] <= 1e-9 and res["charge"] <= 1e-9
    out = {k: fn(rows) for k, fn in PHASE9_REDUCERS.items()}
    assert out["every_ledger_ok"] == 1.0 and out["ablation_complete"] == 1.0
    kinds = [v["kind"] for v in (last.get("events") or {}).values()]
    assert "world_assembled" in kinds and "ablation_started" in kinds and "ablation_complete" in kinds
    assert last["event_count"] >= 2
    # the budget is what the processes deliver: an external tap in the vent, none off-gradient
    assert rows[5]["external_power"] > 0 and last["external_power"] == 0.0
    assert 0.0 <= last["autonomy"] <= 1.0 and 0.0 <= last["autonomy_work"] <= 1.0
    assert last["n_alive"] >= 1 and last["survivors"] <= 1.0
    # the pump knockout never charges its store
    rows_ko = _run(core, n_ticks=20, pump="off", feed_floor=0.1)
    assert max(float(r["internal_power"]) for r in rows_ko) == 0.0
    assert max(float(r["energy_charge_fraction"]) for r in rows_ko) < 0.05


def test_population_rewrites_divide_and_remove_under_the_rewrite_ledger():
    core = build_core()
    pb = IA.PopulationBudgetProcess(config={"division_mass": 1.0, "uptake_cap": 0.6, "min_matter": 0.1, "n_initial": 2}, core=core)
    pop = {"founder-0": {"internal_amounts": {"carbon": 0.5}, "division_state": 0.5},
           "founder-1": {"internal_amounts": {"carbon": 0.12}, "division_state": 0.12}}
    out = pb.update({"population": pop, "localized": {"carbon": 0.0}, "net_power": 1e-17, "material_net": 1.0e-2}, 60.0)
    gain = min(1.0e-2, 1e-17 / 4e4) * 60.0
    assert out["external_flux"] == pytest.approx(gain) and out["n_alive"] == 2 and "_remove" not in out.get("population", {})
    starving = pb.update({"population": pop, "localized": {"carbon": 0.0}, "net_power": -1e-15, "material_net": 0.0}, 60.0)
    assert "_remove" in starving["population"] and starving["population"]["_remove"] == ["founder-1"]
    assert starving["removed_matter"] == pytest.approx(0.12) and starving["extinct"] == 1.0 and starving["n_alive"] == 1


# --------------------------------------------------------------------------- #
# the ensemble and the gate
# --------------------------------------------------------------------------- #
def test_structure_design_and_posterior():
    from viva_genesis.uq.phase1_posterior import posterior_draws, posterior_summary
    draws = posterior_draws()
    assert len(draws) == 6 and all(1e-3 <= d["endmember"]["h2_vent"] <= 1.5e-2 for d in draws)
    summ = posterior_summary(draws)
    assert summ["n"] == 6 and summ["delta_ph"]["min"] > 3.0
    structs = RI.sample_structures(12, seed=1, n_draws=len(draws))
    assert len(structs) == 12 and {s["model_heredity"] for s in structs} == set(RI.STRUCTURE_AXES["model_heredity"])
    assert {s["model_energy_coupling"] for s in structs} == set(RI.STRUCTURE_AXES["model_energy_coupling"])
    kw = RI.structure_kwargs(structs[0], draws)
    assert "h2_vent" in kw and kw["model_boundary"] in RI.STRUCTURE_AXES["model_boundary"]
    assert len(RI.INNOVATION_SETS) == 8 and () in RI.INNOVATION_SETS and ("pump", "importer", "heredity") in RI.INNOVATION_SETS


def test_lattice_gate_evaluates():
    structs = [{"id": "s00", **{a: l[0] for a, l in RI.STRUCTURE_AXES.items()}, "draw": 0},
               {"id": "s01", **{a: l[-1] for a, l in RI.STRUCTURE_AXES.items()}, "draw": 1},
               {"id": "s02", **{a: l[0] for a, l in RI.STRUCTURE_AXES.items()}, "draw": 2}]

    def point(ok, net=1e-18):
        return {"ablation_complete": 1.0, "settled": {"net_power": (net if ok else -1e-18), "material_net": 1e-22, "survivors": 1.0,
                                                      "autonomy": 0.9, "autonomy_work": 1.0, "autonomy_material": 0.8,
                                                      "autonomy_information": 0.7},
                "in_vent": {"autonomy": 0.2, "autonomy_work": 0.1, "autonomy_material": 0.5, "autonomy_information": 0.0}}
    results = {}
    for s in structs:
        for subset in RI.INNOVATION_SETS:
            if s["id"] == "s00":
                ok = {"pump", "heredity"} <= set(subset)             # importer unnecessary here
            elif s["id"] == "s01":
                ok = set(subset) == set(RI.INNOVATIONS)             # og-08's set, irreducible
            else:
                ok = False                                           # nothing persists
            results[(s["id"], RI.set_label(subset))] = point(ok)
    lat = RI.evaluate_lattice(structs, results)
    assert lat["n_viable"] == 2 and lat["full_set_persistence_fraction"] == pytest.approx(2 / 3)
    assert lat["required_intersection"] == ["pump", "heredity"] and lat["required_union"] == ["pump", "importer", "heredity"]
    assert lat["per_structure"]["s00"]["minimal_sufficient"] == ["pump+heredity"]
    assert lat["per_structure"]["s01"]["required"] == ["pump", "importer", "heredity"] and lat["per_structure"]["s02"]["required"] is None
    assert lat["required_fraction"]["importer"] == 0.5 and lat["og08_hypothesis"]["intersection_matches"] is False
    assert lat["nodes"]["pump+heredity"]["n_persist"] == 1 and lat["nodes"]["none"]["n_persist"] == 0
    au = RI.autonomy_summary(structs, results, lat)
    assert au["persisting_full_set"]["autonomy"]["n"] == 2 and au["persisting_full_set"]["autonomy"]["mean"] == pytest.approx(0.9)
    gen = RI.generic_control(structs, {("s00", "generic"): point(False), ("s01", "generic"): point(False)})
    assert gen["persistence_fraction"] == 0.0
    rep = RI.innovation_report(lat, au, gen, RI.paired_knockouts(structs, results), {"all_ok": True, "n_ok": 24, "n_runs": 24},
                               {"n": 1, "counts": {}})
    assert rep.feasibility.feasible and rep.robustness.fraction == pytest.approx(2 / 3) and "pump" in rep.robustness.note

    from viva_genesis import evaluators as EV
    reg = {}
    EV.register_derived_scalars(reg)
    assert {"every_ledger_ok_final", "settled_autonomy", "lattice_minimum_sufficient_set_resolved", "lattice_generic_rejected",
            "lattice_robust_required_count"} <= set(reg)


def test_vg_data_package_carries_the_posterior_and_cites_real_bibkeys():
    from viva_genesis import provenance as P
    pkg = P.load_package("integrated_autonomy")
    assert {"h2_vent", "delta_ph", "feed_floor", "v_max_import", "k_h2", "function_reference", "heredity_allocation",
            "heredity_clock_ratio", "m_active", "carbon_energy_equivalent"} <= set(pkg.parameters)
    assert pkg["h2_vent"].provenance is P.ProvenanceClass.CALIBRATED and not pkg["h2_vent"].is_fixed
    assert pkg["feed_floor"].provenance is P.ProvenanceClass.HYPOTHETICAL and not pkg["feed_floor"].is_fixed
    audit = pkg.audit()
    assert "feed_floor" in audit["hypothetical"] and audit["unsourced"] == []
    missing = P.check_bib(pkg, WS_ROOT / "workspace" / "references" / "papers.bib")
    assert not missing, f"integrated_autonomy cites bibkeys not in papers.bib: {missing}"


def test_committed_artifact_is_consistent_with_the_study():
    art = WS_ROOT / "workspace" / "studies" / "og-08-alt-robust-innovation-set" / "artifacts" / "robust_innovation_set.json"
    if not art.exists():
        pytest.skip("artifact not computed")
    rep = json.loads(art.read_text())
    g = rep["gates"]
    lat = rep["lattice"]
    assert lat["n_structures"] >= 8 and len(lat["nodes"]) == 8
    assert set(lat["required_intersection"]) <= set(RI.INNOVATIONS)
    assert set(lat["required_intersection"]) <= set(lat["required_union"])
    assert g["all_ledgers_ok"] == 1.0 and rep["ledger"]["n_ok"] == rep["ledger"]["n_runs"]
    assert g["generic_persistence_fraction"] <= 0.25
    assert 0.0 <= (g["autonomy_persisting_full_set_rich"] or 0.0) <= 1.0
    assert rep["report"]["tier"] == "conceptual_demonstration" and rep["decision_discipline"] == []
    spec = importlib.util.spec_from_file_location("og08alt_set", SIMS / "compute_robust_innovation_set.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.NOMINAL_FLOOR == rep["meta"]["nominal_floor"]
