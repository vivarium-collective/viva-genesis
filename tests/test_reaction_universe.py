"""Phase 3 — the proto_metabolism face and the rule-generated reaction universe.

Face registration (three classes, face-checked); a non-conforming class is
rejected; the universe is element-balanced by construction and the ledger
invariant (element residual 0, carbon balance at integrator tolerance,
dissipation >= 0) holds on a real libRoadRunner run; the null is matched; the
post-hoc detector finds og-02's lumped rTCA turn and the formose cycle; the
motif-enrichment gate evaluates from an artifact-shaped dict.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from viva_genesis import models
from viva_genesis.core import build_core
from viva_genesis.protometabolism import universe as U
from viva_genesis.protometabolism import motifs as M


# --------------------------------------------------------------------------- #
# Face
# --------------------------------------------------------------------------- #
def test_proto_metabolism_face_registers_three_classes():
    core = build_core()
    assert models.model_names("proto_metabolism") == ["curated_rtca", "null_network", "reaction_universe"]
    for n in models.model_names("proto_metabolism"):
        models.assert_face(core, "proto_metabolism", models.resolve("proto_metabolism", n))
    assert models.resolve("proto_metabolism", "curated_rtca") == "local:RoadRunnerNetworkProcess"
    assert not models.canonical_coverage("proto_metabolism")["uncovered"]


def test_assert_face_rejects_non_conforming_class():
    """A process lacking the required outputs (and declaring a foreign input)
    fails loudly at resolve_checked time."""
    core = build_core()
    # the serpentinization class has none of the proto_metabolism required ports
    with pytest.raises(models.FaceError) as exc:
        models.assert_face(core, "proto_metabolism", "local:SerpentinizationReproductionProcess")
    assert "missing required" in str(exc.value)


# --------------------------------------------------------------------------- #
# Universe generation: chemistry by construction
# --------------------------------------------------------------------------- #
def test_skeleton_formulas_match_known_compounds():
    assert U.formula(("A", "K", "M")) == {"C": 3, "H": 4, "O": 3}          # pyruvate
    assert U.formula(("A", "C", "K", "A")) == {"C": 4, "H": 4, "O": 5}     # oxaloacetate
    assert U.formula(("D", "O", "O", "H")) == {"C": 4, "H": 8, "O": 4}     # erythrose
    assert U.formula(("A",)) == {"C": 1, "H": 2, "O": 2}                   # formate (HCOOH)
    assert U.formula(("D",)) == {"C": 1, "H": 2, "O": 1}                   # formaldehyde
    assert U.canon(("M", "K", "A")) == ("A", "K", "M")
    assert U.common_name(("M", "K", "A")) == "pyruvate"


def test_universe_is_element_balanced_and_sized():
    u = U.build_universe(4)
    assert len(u.organics()) == 121 and 350 < len(u.reactions) < 500
    res = u.element_residual()
    assert res["max_abs"] == 0.0 and res["n_unbalanced"] == 0
    # every rule fired; formose initiation + aldol + retro-aldol are present
    rc = u.rule_counts()
    assert {"aldol", "isomerize", "co2_reduction", "formose_initiation", "carboxylate_alpha"} <= set(rc)
    # thermodynamic consistency: dG0 is a potential difference, so every cycle sums to 0
    pots = u.potentials
    for r in u.reactions[:50]:
        assert abs(r.dg0 - U.reaction_dg0(r, pots)) < 1e-12
    assert len(u.doubling_reactions()) > 10        # doubling edges (Cannizzaro, retro-aldol) exist


def test_package_thermo_matches_live_equilibrator():
    """The committed dG' table reproduces the real eQuilibrator reaction estimate
    (pyruvate + CO2 -> OAA) to 1e-6 kJ/mol."""
    pytest.importorskip("equilibrator_api")
    from equilibrator_api import ComponentContribution, Q_
    u = U.build_universe(4)
    cond = u.conditions
    cc = ComponentContribution()
    cc.p_h = Q_(cond.p_h); cc.ionic_strength = Q_(f"{cond.ionic_strength_M} M"); cc.temperature = Q_(f"{cond.temperature_K} K")
    live = float(cc.standard_dg_prime(cc.parse_reaction_formula("kegg:C00022 + kegg:C00011 = kegg:C00036")).value.to("kJ/mol").magnitude)
    pyr, oaa = U.species_id(("A", "K", "M")), U.species_id(("A", "C", "K", "A"))
    r = next(r for r in u.reactions if r.reactants == {pyr: 1, "CO2": 1} and r.products == {oaa: 1})
    assert abs(r.dg0 - live) < 1e-6


def test_package_provenance_and_bib():
    from pathlib import Path
    from viva_genesis import provenance as P
    pkg = P.load_package("reaction_universe")
    audit = pkg.audit()
    assert audit["n"] >= 18 and audit["counts"]["measured"] == 0           # honest: nothing here is measured
    assert set(U.DEFAULT_KINETICS) <= set(pkg.parameters)
    assert all(pkg[k].nominal() == v for k, v in U.DEFAULT_KINETICS.items())
    missing = P.check_bib(pkg, Path(__file__).resolve().parents[1] / "workspace" / "references" / "papers.bib")
    assert missing == [], missing
    thermo = U.load_thermo_table()
    assert thermo["fit"]["n_resolved"] >= 45 and all("provenance" in c for c in thermo["compounds"].values())


def test_null_network_is_matched():
    u = U.build_universe(4)
    n = U.null_network(u, seed=3)
    assert n.organics() == u.organics()
    assert abs(len(n.reactions) - len(u.reactions)) <= 10
    assert n.catalyst_density().keys() == u.catalyst_density().keys()
    # carbon AND oxygen balance kept, hydrogen balance lost
    res = n.element_residual()
    assert res["per_element"]["C"] == 0.0 and res["per_element"]["O"] == 0.0 and res["per_element"]["H"] > 0
    # topology actually changed
    assert sum(1 for a, b in zip(u.reactions, n.reactions) if a.key() != b.key()) > 100


# --------------------------------------------------------------------------- #
# Ledger invariant on a real run
# --------------------------------------------------------------------------- #
def test_universe_ledger_invariant_on_real_run():
    pytest.importorskip("tellurium")
    from process_bigraph import allocate_core
    from viva_genesis.protometabolism.universe_process import ReactionUniverseProcess
    p = ReactionUniverseProcess(config={"motif_every": 30}, core=allocate_core())
    feed = p.initial_state()
    o = None
    for _ in range(60):
        o = p.update(feed, 1.0)
        assert o["element_residual"] == 0.0
        assert o["dissipation"] >= -1e-12            # second law, every tick
        assert o["carbon_residual"] < 1e-4           # integrator-tolerance carbon balance
    assert o["n_persistent_species"] >= 5 and o["total_organic_carbon"] > 1e-5
    assert o["malate"] > 1e-9                        # the rTCA reductive branch emerges from the rules


def test_network_ledger_process_flags_violations():
    from viva_genesis.ledger import NetworkLedgerProcess
    from process_bigraph import allocate_core
    led = NetworkLedgerProcess(config={}, core=allocate_core())
    ok = led.update({"element_residual": 0.0, "carbon_residual": 1e-8, "dissipation": 1e-3, "total_organic_carbon": 1e-4}, 1.0)
    assert ok["ledger_ok"] == 1.0 and ok["free_energy_directionality"] == 1.0
    bad = led.update({"element_residual": 4.0, "carbon_residual": 1e-8, "dissipation": -1e-3, "total_organic_carbon": 1e-4}, 1.0)
    assert bad["ledger_ok"] == 0.0 and bad["free_energy_directionality"] == 0.0 and bad["element_residual_max"] == 4.0


# --------------------------------------------------------------------------- #
# Post-hoc detector
# --------------------------------------------------------------------------- #
def _toy_net(reactions):
    species = sorted({s for r in reactions for s in list(r[1]) + list(r[2])})
    return M.Network(species=species, reactions=[M.Rxn(id=i, reactants=a, products=b) for i, a, b in reactions])


def test_detector_finds_lumped_rtca_turn_and_formose_cycle():
    # og-02's lumped turn: OAA + 2 CO2 -> 2 OAA + acetate is a self-loop with gain 2
    net = _toy_net([("R_rtca", {"OAA": 1, "CO2": 2}, {"OAA": 2, "acetate": 1}),
                    ("R_mal", {"OAA": 1}, {"malate": 1})])
    cyc = M.autocatalytic_cycles(net, {"R_rtca": 1e-3, "R_mal": 1e-4}, {"OAA": 1e-3, "malate": 1e-4, "acetate": 1e-3},
                                 exclude={"CO2"})
    assert len(cyc) == 1 and cyc[0].gain == 2.0 and cyc[0].species == ["OAA"]
    g = M.motif_gain(cyc[0], {"OAA": 1e-3}, loss_rate=0.05)
    assert abs(g - (1e-3 * 1.0) / (0.05 * 1e-3)) < 1e-12        # = k_rtca [CO2] / k_wash for v = k [OAA][CO2]
    # formose: GA + CH2O -> GLY -> DHA ; DHA + CH2O -> ERU -> ERY -> 2 GA
    net = _toy_net([("aldol1", {"GA": 1, "CH2O": 1}, {"GLY": 1}), ("iso1", {"GLY": 1}, {"DHA": 1}),
                    ("aldol2", {"DHA": 1, "CH2O": 1}, {"ERU": 1}), ("iso2", {"ERU": 1}, {"ERY": 1}),
                    ("retro", {"ERY": 1}, {"GA": 2})])
    rates = {k: 1e-6 for k in ("aldol1", "iso1", "aldol2", "iso2", "retro")}
    conc = {s: 1e-6 for s in ("GA", "GLY", "DHA", "ERU", "ERY", "CH2O")}
    cyc = M.autocatalytic_cycles(net, rates, conc, exclude={"CH2O"})
    assert len(cyc) == 1 and cyc[0].gain == 2.0 and set(cyc[0].species) == {"GA", "GLY", "DHA", "ERU", "ERY"}
    # a reaction running backwards breaks the cycle
    rates["retro"] = -1e-6
    assert M.autocatalytic_cycles(net, rates, conc, exclude={"CH2O"}) == []


def test_curated_rtca_is_not_element_balanced_but_universe_is():
    pytest.importorskip("tellurium")
    import tellurium as te
    from viva_genesis.protometabolism.network import _MODEL
    net = M.network_from_roadrunner(te.loada(_MODEL))
    formulas = {"CO2": {"C": 1, "O": 2}, "pyruvate": {"C": 3, "H": 4, "O": 3}, "OAA": {"C": 4, "H": 4, "O": 5},
                "malate": {"C": 4, "H": 6, "O": 5}, "succinate": {"C": 4, "H": 6, "O": 4}, "acetate": {"C": 2, "H": 4, "O": 2}}
    res = M.element_residual(net, formulas)
    assert res["per_element"]["C"] == 4.0 and res["offenders"][0]["reaction"] == "R_rtca"   # 6 C in, 10 C out
    u = U.build_universe(4)
    ant = U.to_antimony(u, U.DEFAULT_KINETICS, {"feed_CO2": 1e-3, "feed_H2": 1e-2})
    net_u = M.network_from_roadrunner(te.loada(ant))
    assert M.element_residual(net_u, u.formulas, skip={"tar"})["max_abs"] == 0.0


def test_motif_enrichment_gate_evaluates():
    """The gate's evaluator reads an artifact-shaped dict: universe above every
    null -> p = 1/(n+1); universe at the null level -> p ~ 1."""
    e = M.enrichment(1.0, [0.0] * 24)
    assert e["p_empirical"] == pytest.approx(1 / 25) and e["null_max"] == 0.0 and e["z"] == math.inf
    e2 = M.enrichment(0.0, [0.0] * 24)
    assert e2["p_empirical"] == 1.0
    e3 = M.enrichment(3.0, [1.0, 2.0, 3.0, 0.0])
    assert e3["p_empirical"] == pytest.approx(2 / 5) and e3["null_mean"] == 1.5
    # the registered derived scalar reads the same shape from a file
    import json
    from viva_genesis import evaluators as EV
    reg = {}
    EV.register_derived_scalars(reg)
    assert {"motif_enrichment_p", "universe_motif_count", "curated_element_residual", "max_element_residual"} <= set(reg)
    art = {"arms": {"formose_feed": {"enrichment": {"n_motifs": e}, "universe": {"n_motifs": 1}},
                    "phase1_feed": {"curated_rtca": {"element_residual": 4.0}}}}
    tmp = pytest.importorskip("tempfile").TemporaryDirectory()
    import pathlib
    root = pathlib.Path(tmp.name); (root / "a").mkdir()
    (root / "a" / "m.json").write_text(json.dumps(art))
    test = {"artifact": "a/m.json", "params": {"arm": "formose_feed"}}
    assert reg["motif_enrichment_p"](None, test, root) == pytest.approx(1 / 25)
    assert reg["universe_motif_count"](None, test, root) == 1.0
    assert reg["curated_element_residual"](None, test, root) == 4.0


def test_flux_control_and_stiffness_on_curated_model():
    pytest.importorskip("tellurium")
    import tellurium as te
    from viva_genesis.protometabolism.network import _MODEL
    rr = te.loada(_MODEL)
    rr.simulate(0, 400, 50)
    fca = M.flux_control_analysis(rr)
    assert fca["ok"] and fca["max_summation_residual"] < 1e-2          # MCA summation theorem
    st = M.stiffness_check(lambda: te.loada(_MODEL), t_end=60.0, n_points=61)
    assert math.isfinite(st["jacobian"]["stiffness_ratio"]) and st["jacobian"]["stiffness_ratio"] > 1
    assert all(v["max_rel_dev"] < 1e-2 for v in st["deviations"].values())
