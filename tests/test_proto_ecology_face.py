"""Phase 8 — the proto_ecology face: two registered classes (the Phase-3
universe and its matched null inside a protocell), loud face rejection (og-07's
capability-vector process is a real non-conformer), the exchange-rule reactive
system (conserving, counted), lineage rule masks, the composite with the
cross-system C/N/P ledger closed, the og-07 readouts recomputed from agents,
the vg-data package and the community-function gate evaluators."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from viva_genesis import models
from viva_genesis.core import build_core
from viva_genesis.ecology import proto_ecology as PE
from viva_genesis.ecology.reactive_system import BigraphicalReactiveSystem, RuleContext
from viva_genesis.protometabolism import universe as U

WS_ROOT = Path(__file__).resolve().parents[1]
SIMS = WS_ROOT / "workspace" / "studies" / "og-ecology" / "sims" / "og-07-alt-real-metabolite-exchange"


@pytest.fixture(autouse=True)
def _quiet_roadrunner():
    import roadrunner
    roadrunner.Logger.setLevel(roadrunner.Logger.LOG_ERROR)


# --------------------------------------------------------------------------- #
# the face
# --------------------------------------------------------------------------- #
def test_face_registers_both_classes():
    core = build_core()
    assert models.model_names("proto_ecology") == ["null_network", "reaction_universe"]
    for n in models.model_names("proto_ecology"):
        models.assert_face(core, "proto_ecology", models.resolve("proto_ecology", n))
    assert models.canonical_coverage("proto_ecology")["uncovered"] == []
    assert set(models.axis("proto_ecology")["model_proto_ecology"]) == {"null_network", "reaction_universe"}


def test_assert_face_rejects_nonconformers():
    from process_bigraph import Process
    core = build_core()
    # og-07's capability-vector metacommunity predates the face: no agent pool, symbolic outputs -> rejected loudly
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "proto_ecology", "local:CrossFeedingMetacommunityProcess")
    assert "missing required input" in str(exc.value) and "internal" in str(exc.value)

    class WrongEcology(Process):
        def inputs(self):
            return {"internal": "map[float]"}

        def outputs(self):
            return {"internal": "map[float]", "capability_vector": "tree"}     # foreign port, missing witnesses

        def update(self, state, interval):
            return {}

    core.register_link("WrongEcology", WrongEcology)
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "proto_ecology", "local:WrongEcology")
    assert "capability_vector" in str(exc.value) and "functions_produced" in str(exc.value)
    from viva_genesis.composites.metabolite_exchange_community import metabolite_exchange_community
    with pytest.raises(KeyError):
        metabolite_exchange_community(core, model_proto_ecology="capability_vector")


def test_every_new_class_declares_provenance_on_its_config():
    from viva_genesis.provenance import audit_config_schema
    from viva_genesis.ledger import EcologyElementLedgerProcess
    for cls in (PE.ProtocellNetworkProcess, PE.ProtocellNullNetworkProcess, PE.SpatialCouplingStep,
                PE.EcologyReducerStep, EcologyElementLedgerProcess):
        audit = audit_config_schema(cls.config_schema)
        assert not audit["undeclared"], (cls.__name__, audit["undeclared"])


# --------------------------------------------------------------------------- #
# the function vocabulary and the repertoires
# --------------------------------------------------------------------------- #
def test_function_vocabulary_and_repertoires():
    assert PE.function_of("X_ACKA") == "c4_diacid_oxo"          # oxaloacetate
    assert PE.function_of("X_ACOA") == "c4_diacid_hydroxy"      # malate
    assert PE.function_of("X_ACCA") == "c4_diacid_reduced"      # succinate
    assert PE.function_of("X_AKM") == "c3_monoacid_oxo"         # pyruvate
    assert PE.function_of("X_A") == "c1_formate" and PE.function_of(U.CO2) is None
    assert len(PE.FUNCTIONS) >= 20 and "c4_diacid_hydroxy" in PE.FUNCTIONS
    # the lineages partition the catalysed rules; the thermal decarboxylations belong to all
    assert PE.FREE_RULES <= PE.REPERTOIRES["fixer"] and PE.FREE_RULES <= PE.REPERTOIRES["reducer"]
    assert not (PE.REPERTOIRES["fixer"] - PE.FREE_RULES) & (PE.REPERTOIRES["reducer"] - PE.FREE_RULES)
    assert PE.REPERTOIRES["generalist"] == frozenset(U.RULES)
    assert PE.permeability_class("X_ACKA") == "p_diacid" and PE.permeability_class("X_AKM") == "p_monoacid"
    assert PE.permeability_class("X_DM") == "p_small_neutral" and PE.permeability_class(U.H2) == "p_gas"


# --------------------------------------------------------------------------- #
# the reactive system: conserving transfers, counted firings, the private arm
# --------------------------------------------------------------------------- #
def _ctx(private=False):
    el = {"A": {"C": 2, "N": 0, "P": 0}, "N1": {"C": 0, "N": 1, "P": 0}}
    agents = {"a": {"volume": 1e-18, "cell": "c0", "internal": {"A": 1e-6, "N1": 0.0}, "k": {"A": 0.5, "N1": 0.1}, "lineage": "x"},
              "b": {"volume": 1e-18, "cell": "c1", "internal": {"A": 0.0, "N1": 0.0}, "k": {"A": 0.5, "N1": 0.1}, "lineage": "y"}}
    cells = {"c0": {"A": 0.0, "N1": 1e-5}, "c1": {"A": 0.0, "N1": 1e-5}}
    bg = {"c0": {"A": 0.0, "N1": 1e-5}, "c1": {"A": 0.0, "N1": 1e-5}}
    return RuleContext(agents=agents, cells=cells, cell_volume=1e-17, background=bg, elements=el, dt=1.0,
                       k_diffusion=0.2, k_wash=0.05, private=private, neighbours={"c0": ["c1"], "c1": ["c0"]})


def _moles(ctx):
    tot = {"C": 0.0, "N": 0.0}
    for a in ctx.agents.values():
        for s, c in a["internal"].items():
            for el in tot:
                tot[el] += c * a["volume"] * ctx.elements[s][el]
    for cell in ctx.cells.values():
        for s, c in cell.items():
            for el in tot:
                tot[el] += c * ctx.cell_volume * ctx.elements[s][el]
    return tot


def test_reactive_system_conserves_matter_and_counts_firings():
    ctx = _ctx()
    before = _moles(ctx)
    sys_ = BigraphicalReactiveSystem()
    out = sys_.fire(ctx)
    after = _moles(ctx)
    for el in ("C", "N"):
        assert after[el] == pytest.approx(before[el] + ctx.inflow[el] - ctx.outflow[el], rel=1e-12, abs=1e-40)
    assert out["counts"]["secretion"] >= 1 and out["counts"]["uptake"] >= 1 and out["counts"]["pore_exchange"] >= 1
    assert out["counts"]["diffusion"] >= 1
    assert sys_.counts == out["counts"] and sys_.rule_names() == ["uptake", "secretion", "diffusion", "pore_exchange"]
    assert ctx.agents["a"]["internal"]["A"] < 1e-6 and ctx.cells["c0"]["A"] > 0        # secreted into the cell
    assert ctx.agents["b"]["internal"]["N1"] > 0                                          # taken up from the cell
    # a second firing keeps counting
    sys_.fire(ctx)
    assert sys_.counts["uptake"] > out["counts"]["uptake"]
    # private: nothing an agent secretes reaches a cell; pore rules are silent
    ctxp = _ctx(private=True)
    outp = BigraphicalReactiveSystem().fire(ctxp)
    assert outp["counts"]["pore_exchange"] == 0 and outp["counts"]["diffusion"] == 0
    assert ctxp.cells["c0"]["A"] == 0.0 and ctxp.outflow["C"] > 0 and ctxp.inflow["N"] > 0


# --------------------------------------------------------------------------- #
# the protocell network: real engine, rule masks, witnesses
# --------------------------------------------------------------------------- #
def test_protocell_network_masks_rules_and_balances_elements():
    core = build_core()
    feed = {U.CO2: 1.4e-3, U.H2: 1.08e-2, "X_AKM": 1.0e-4}
    outs = {}
    for lineage in ("fixer", "reducer"):
        proc = PE.ProtocellNetworkProcess(config={"lineage": lineage}, core=core)
        internal = dict(feed)
        for _ in range(5):
            o = proc.update({"internal": internal}, 1.0)
            for s, d in o["internal"].items():
                internal[s] = internal.get(s, 0.0) + d
        outs[lineage] = (o, internal)
    fo, fi = outs["fixer"]
    ro, ri = outs["reducer"]
    assert fo["element_residual"] == 0.0 and ro["element_residual"] == 0.0        # exact stoichiometry
    assert fo["dissipation"] >= 0.0 and ro["dissipation"] >= 0.0                  # second law
    assert fo["rule_flux"]["carboxylate_alpha"] > 0 and fo["rule_flux"]["reduce_carbonyl"] == 0.0
    assert ro["rule_flux"]["reduce_carbonyl"] > 0 and ro["rule_flux"]["carboxylate_alpha"] == 0.0
    assert fo["functions_produced"]["c4_diacid_oxo"] == 1.0                      # the fixer makes OAA ...
    assert ro["functions_produced"]["c4_diacid_oxo"] == 0.0                      # ... the reducer cannot
    assert ro["functions_produced"]["c3_monoacid_hydroxy"] == 1.0                # ... but makes lactate
    assert fi["X_ACKA"] > 1e-8 and ri["X_ACKA"] < 1e-20 and ri["X_AOM"] > fi["X_AOM"]   # OAA only via carboxylation
    assert fo["co2_fixation"] > 0 and ro["h2_consumption"] > 0
    # the null class shares the engine and masks but rewires the chemistry
    null = PE.ProtocellNullNetworkProcess(config={"lineage": "fixer", "null_seed": 0}, core=core)
    o = null.update({"internal": dict(feed)}, 1.0)
    assert null.universe().label == "null_network" and set(o["rule_flux"]) == set(U.RULES)


# --------------------------------------------------------------------------- #
# the composite + the cross-system ledger + og-07's readouts from agents
# --------------------------------------------------------------------------- #
def test_composite_runs_with_closed_cross_system_ledger():
    from process_bigraph import Composite, gather_emitter_results
    from viva_genesis.composites.metabolite_exchange_community import (metabolite_exchange_community, PHASE8_REDUCERS,
                                                                       parse_lineages, place_agents)
    assert parse_lineages("fixer:2,reducer:1") == ["fixer", "fixer", "reducer"]
    assert place_agents(["fixer", "fixer", "reducer", "reducer"], 2, "mixed", 1) == [0.125, 0.625, 0.375, 0.875]
    core = build_core()
    sim = Composite({"state": metabolite_exchange_community(core, lineages="fixer:2,reducer:2", n_cells=2,
                                                            p_diacid=1e-8, p_monoacid=1e-7, k_wash=0.01)}, core=core)
    sim.run(25.0)
    rows = gather_emitter_results(sim)[("emitter",)]
    out = {k: fn(rows) for k, fn in PHASE8_REDUCERS.items()}
    last = rows[-1]
    assert last["element_ledger_ok"] == 1.0
    assert last["C_residual_max"] <= 1e-6 and last["N_residual_max"] <= 1e-9 and last["P_residual_max"] <= 1e-9
    assert last["N_total"] > 0 and last["P_total"] > 0 and last["C_total"] > 0
    assert out["exchange_firings_total"] > 0 and all(last["firings"][r] > 0 for r in ("uptake", "secretion", "diffusion", "pore_exchange"))
    assert out["cross_lineage_flux_total"] > 0                                   # something crossed between lineages
    assert all(float(r["robustness_gain"]) >= -1e-12 for r in rows)              # held includes produced
    assert 0.0 < last["max_cell_completeness"] <= 1.0 and last["n_functions_union"] >= 3
    assert last["luca_capability_overlap"] <= 0.8                                # ion pumping unreachable
    fu = last["functions_union"]
    assert "fixer" in fu["c4_diacid_oxo"]["produced_by"] and "reducer" not in fu["c4_diacid_oxo"]["produced_by"]
    # private: the same assignment, nothing crosses between lineages
    simp = Composite({"state": metabolite_exchange_community(core, lineages="fixer:2,reducer:2", n_cells=2, coupling="private",
                                                             p_diacid=1e-8, p_monoacid=1e-7, k_wash=0.01)}, core=core)
    simp.run(10.0)
    rp = gather_emitter_results(simp)[("emitter",)][-1]
    assert rp["cross_lineage_flux_total"] == 0.0 and rp["firings"]["pore_exchange"] == 0.0 and rp["element_ledger_ok"] == 1.0


# --------------------------------------------------------------------------- #
# the vg-data package and the gate evaluators
# --------------------------------------------------------------------------- #
def test_cnp_resources_package_loads_and_cites_real_bibkeys():
    from viva_genesis import provenance as P
    pkg = P.load_package("cnp_resources")
    assert {"feed_CO2", "feed_ammonium", "feed_phosphate", "p_diacid", "p_monoacid", "k_wash", "agent_volume",
            "function_floor", "redundancy_target"} <= set(pkg.parameters)
    assert pkg["feed_CO2"].provenance is P.ProvenanceClass.CALIBRATED
    assert pkg["p_diacid"].provenance is P.ProvenanceClass.HYPOTHETICAL and not pkg["p_diacid"].is_fixed
    audit = pkg.audit()
    assert "p_diacid" in audit["hypothetical"] and audit["unsourced"] == []
    assert audit["counts"]["measured"] == 0
    missing = P.check_bib(pkg, WS_ROOT / "workspace" / "references" / "papers.bib")
    assert not missing, f"cnp_resources cites bibkeys not in papers.bib: {missing}"


def _load_sims_module():
    spec = importlib.util.spec_from_file_location("og07alt_map", SIMS / "compute_community_function_map.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_community_function_gate_evaluates(tmp_path):
    mod = _load_sims_module()
    floor = 1e-9

    def arm(functions, produced, cross=None, completeness=0.8):
        return {"functions": functions, "produced_any_settled": produced, "cross_lineage_flux": cross or {},
                "cross_lineage_flux_total": sum(v["moles_per_tick"] for v in (cross or {}).values()),
                "max_cell_completeness": completeness, "mean_cell_completeness": completeness * 0.9,
                "n_functions_union": float(len(functions)),
                "functions_final": {f: {"max_conc": c, "held_by": ["fixer", "reducer"], "produced_by": ["reducer"]} for f, c in functions.items()}}

    arms = {
        "community": arm({"c4_diacid_oxo": 5e-8, "c4_diacid_hydroxy": 1e-8, "c3_monoacid_hydroxy": 1e-6}, ["c4_diacid_oxo", "c4_diacid_hydroxy"],
                         {"X_ACKA": {"name": "oxaloacetate", "moles_per_tick": 3e-27}}),
        "mono_fixer": arm({"c4_diacid_oxo": 5e-8}, ["c4_diacid_oxo"]),
        "mono_reducer": arm({"c3_monoacid_hydroxy": 1e-6}, ["c3_monoacid_hydroxy"]),
        "private": arm({"c4_diacid_oxo": 5e-8, "c3_monoacid_hydroxy": 1e-6, "c4_diacid_hydroxy": 1e-12}, ["c4_diacid_oxo"]),
        "generalist": arm({"c4_diacid_hydroxy": 1e-7}, ["c4_diacid_hydroxy"], completeness=1.0),
    }
    g = mod.evaluate_gate(arms, floor)
    assert g["community_only_functions"] == ["c4_diacid_hydroxy"] and g["vanish_without_exchange"] == ["c4_diacid_hydroxy"]
    assert g["flux_sustained"] and g["exchanged_intermediates"][0]["name"] == "oxaloacetate"
    assert g["community_over_generalist"] == pytest.approx(0.1) and g["max_cell_completeness"] == 0.8
    # a function the private arm keeps is NOT flux-sustained
    arms["private"]["functions"]["c4_diacid_hydroxy"] = 2e-9
    g2 = mod.evaluate_gate(arms, floor)
    assert g2["community_only_functions"] == ["c4_diacid_hydroxy"] and not g2["flux_sustained"]

    from viva_genesis import evaluators as EV
    reg = {}
    EV.register_derived_scalars(reg)
    assert {"n_community_only_functions", "community_flux_sustained", "emergence_p_diacid_nominal", "element_ledger_ok_final",
            "cross_lineage_flux_total_final", "max_cell_completeness_final", "connected_minus_isolated_robustness"} <= set(reg)
    art = {"gates": {"n_community_only_functions": 2, "n_vanish_without_exchange": 2, "flux_sustained": 1.0,
                     "community_cross_lineage_flux_total": 1e-24, "community_max_cell_completeness": 0.85,
                     "community_over_generalist": 0.1, "null_community_only_max": 0, "segregated_n_community_only": 1,
                     "emergence_p_diacid_at_nominal_residence": None, "all_ledgers_ok": True,
                     "connected_minus_isolated_robustness": 0.07},
           "ledger": {"C_residual_max": 3e-12}}
    (tmp_path / "f.json").write_text(json.dumps(art))
    test = {"artifact": "f.json"}
    assert reg["n_community_only_functions"](None, test, tmp_path) == 2.0
    assert reg["community_flux_sustained"](None, test, tmp_path) == 1.0
    assert reg["map_ledgers_all_ok"](None, test, tmp_path) == 1.0
    assert reg["map_carbon_residual_max"](None, test, tmp_path) == 3e-12
    with pytest.raises(ValueError):
        reg["emergence_p_diacid_nominal"](None, test, tmp_path)
