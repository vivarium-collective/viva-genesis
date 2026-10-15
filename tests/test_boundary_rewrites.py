"""Phase 5 framework — the boundary face, amphiphile synthesis, the structural
rewrites on the agents map, and their conservation (rewrite + partition residuals).
"""
import pytest
from process_bigraph import Composite

from viva_genesis.core import build_core
from viva_genesis import models, schemas
from viva_genesis.provenance import load_package


# --- boundary face ----------------------------------------------------------

def test_boundary_face_registers_all_classes():
    build_core()
    assert set(models.model_names("boundary")) == {"single_chain", "mixed",
                                                   "thioester_aminothiol"}


def test_boundary_classes_satisfy_the_face():
    core = build_core()
    for m in ("single_chain", "mixed", "thioester_aminothiol"):
        addr = models.resolve_checked(core, "boundary", m)  # runs assert_face
        assert addr.startswith("local:")


def test_boundary_face_canonical_coverage_complete():
    assert models.canonical_coverage("boundary")["uncovered"] == []


def test_assert_face_rejects_a_non_conformer():
    core = build_core()
    # AmphiphileSynthesisProcess has none of the boundary face's required ports
    with pytest.raises(models.FaceError):
        models.assert_face(core, "boundary", "local:AmphiphileSynthesisProcess")


def test_vg_individual_has_internal_amounts():
    assert schemas.SCHEMAS["vg_individual"]["internal_amounts"] == "map[vg_amount]"


# --- amphiphile synthesis ---------------------------------------------------

def test_amphiphile_synthesis_makes_amphiphile_from_carbon():
    core = build_core()
    from viva_genesis.boundary_rewrites import AmphiphileSynthesisProcess
    proc = AmphiphileSynthesisProcess(config={"k_synth": 1.0}, core=core)
    out = proc.update({"acetate": 0.1, "formate": 0.1}, 1.0)
    assert out["amphiphile"] > 0
    # the produced amphiphile is drawn from the consumed substrates (mass link)
    assert out["acetate"] < 0 and out["formate"] < 0
    assert out["amphiphile"] == pytest.approx(-out["acetate"], rel=1e-9)


# --- structural rewrites + conservation ------------------------------------

def _run(doc, t=1.0):
    core = build_core()
    sim = Composite({"state": doc}, core=core)
    sim.run(t)
    return sim


def _inds(agents):
    return {k: v for k, v in agents.items()
            if isinstance(v, dict) and "internal_amounts" in v}


def test_divide_conserves_matter_partition_residual_zero():
    mother = {"id": "m0", "volume": 2e-12, "internal_amounts": {"formate": 4.0, "acetate": 2.0},
              "boundary": {"area": 1.0, "integrity": 1.0}, "division_state": 1.0, "persistence": 0.0}
    sim = _run({
        "agents": {"m0": mother},
        "div": {"_type": "step", "address": "local:DivisionStep", "config": {},
                "inputs": {"agents": ["agents"]},
                "outputs": {"agents": ["agents"], "division_count": ["d", "dc"],
                            "partition_residual": ["d", "pr"]}},
        "d": {"dc": 0.0, "pr": 0.0},
    })
    inds = _inds(sim.state["agents"])
    assert len(inds) == 2
    tot = {}
    for a in inds.values():
        for sp, amt in a["internal_amounts"].items():
            tot[sp] = tot.get(sp, 0.0) + amt
    assert tot["formate"] == pytest.approx(4.0, abs=1e-12)
    assert tot["acetate"] == pytest.approx(2.0, abs=1e-12)
    assert sim.state["d"]["pr"] == pytest.approx(0.0, abs=1e-12)


def test_boundary_formation_add_conserves_and_gates_on_amphiphile():
    base = {
        "agents": {}, "localized": {"formate": 10.0, "acetate": 6.0},
        "env": {"amph": 5e-3, "viable": 3},
        "form": {"_type": "step", "address": "local:BoundaryFormationStep",
                 "config": {"cac": 1e-3},
                 "inputs": {"amphiphile": ["env", "amph"], "viable_compartments": ["env", "viable"],
                            "localized": ["localized"], "agents": ["agents"]},
                 "outputs": {"agents": ["agents"], "boundary_formed": ["d", "bf"],
                             "localized": ["localized"]}},
        "d": {"bf": 0.0},
    }
    sim = _run(base)
    inds = _inds(sim.state["agents"])
    assert len(inds) == 1 and sim.state["d"]["bf"] == 1.0
    total = (sum(sum(i["internal_amounts"].values()) for i in inds.values())
             + sum(float(v) for v in sim.state["localized"].values()))
    assert total == pytest.approx(16.0, abs=1e-9)  # conserved

    # synthesis ablated: amphiphile below cac -> no boundary forms
    base2 = dict(base); base2["env"] = {"amph": 1e-6, "viable": 3}
    base2["agents"] = {}; base2["localized"] = {"formate": 10.0, "acetate": 6.0}
    base2["d"] = {"bf": 0.0}
    sim2 = _run(base2)
    assert len(_inds(sim2.state["agents"])) == 0 and sim2.state["d"]["bf"] == 0.0


def test_lysis_remove_accounts_removed_matter():
    sim = _run({
        "agents": {"a0": {"id": "a0", "volume": 1e-12, "internal_amounts": {"formate": 3.0},
                          "boundary": {"area": 1, "integrity": 0.05}, "division_state": 0.0, "persistence": 0.0},
                   "a1": {"id": "a1", "volume": 1e-12, "internal_amounts": {"formate": 5.0},
                          "boundary": {"area": 1, "integrity": 0.9}, "division_state": 0.0, "persistence": 0.0}},
        "lys": {"_type": "step", "address": "local:LysisStep", "config": {"lysis_integrity": 0.1},
                "inputs": {"agents": ["agents"]},
                "outputs": {"agents": ["agents"], "lysed": ["d", "l"], "removed_matter": ["d", "rm"]}},
        "d": {"l": 0.0, "rm": 0.0},
    })
    assert list(_inds(sim.state["agents"])) == ["a1"]
    assert sim.state["d"]["rm"] == pytest.approx(3.0, abs=1e-12)


def test_rewrite_ledger_reports_conservation():
    sim = _run({
        "agents": {}, "localized": {"formate": 10.0, "acetate": 6.0},
        "env": {"amph": 5e-3, "viable": 3},
        "form": {"_type": "step", "address": "local:BoundaryFormationStep", "config": {"cac": 1e-3},
                 "inputs": {"amphiphile": ["env", "amph"], "viable_compartments": ["env", "viable"],
                            "localized": ["localized"], "agents": ["agents"]},
                 "outputs": {"agents": ["agents"], "boundary_formed": ["d", "bf"], "localized": ["localized"]}},
        "ledger": {"_type": "process", "address": "local:RewriteLedgerProcess", "config": {},
                   "inputs": {"agents": ["agents"], "localized": ["localized"],
                              "partition_residual": ["d", "pr"], "removed_matter": ["d", "rm"]},
                   "outputs": {"rewrite_residual": ["d", "rr"], "rewrite_residual_max": ["d", "rrm"],
                               "partition_residual_max": ["d", "prm"], "agent_matter": ["d", "am"],
                               "n_agents": ["d", "na"], "rewrite_ok": ["d", "ok"]}},
        "d": {"bf": 0.0, "pr": 0.0, "rm": 0.0, "rr": 0.0, "rrm": 0.0, "prm": 0.0, "am": 0.0, "na": 0.0, "ok": 1.0},
    }, t=3.0)
    assert sim.state["d"]["rrm"] == pytest.approx(0.0, abs=1e-9)
    assert sim.state["d"]["ok"] == 1.0


# --- data package -----------------------------------------------------------

def test_amphiphile_assembly_package_loads_and_audits():
    pkg = load_package("amphiphile_assembly")
    pkg.audit()
    nom = pkg.nominal()
    assert nom["cac"] == pytest.approx(1e-3)
    assert "mix_fraction" in nom
