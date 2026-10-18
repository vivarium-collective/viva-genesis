"""Behavior tests for og-rtca-autocatalysis.

Two offline structural tests (curated-network balance + topological-autocatalysis
shape, via stub potentials so no eQuilibrator / libRoadRunner is needed) and
three assertions against the committed discriminator artifact
(``artifacts/rtca_discriminator.json``, produced by
``sims/compute_rtca_discriminator.py``). They back the study's behavior_tests:
rtca-vent-h2-washout, rtca-topology-net-turn, rtca-permissive-limit-topology-
specific, gate-a-a2-branched-resolved.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "rtca_discriminator.json"


def _stub_potentials():
    from viva_genesis.protometabolism import rtca as R
    return {s: 0.0 for s in R.ORGANICS}


# --- offline structural tests ------------------------------------------------ #
def test_rtca_topology_net_turn():
    """Element-balanced, carrier = OAA, and NO coefficient-2 reaction: the
    autocatalysis is topological, so the coefficient detector reads 0 by
    construction (rtca-topology-net-turn)."""
    from viva_genesis.protometabolism import rtca as R
    from viva_genesis.protometabolism import universe as U
    u = R.build_rtca_universe(potentials=_stub_potentials())
    assert u.element_residual()["max_abs"] == 0.0, "curated rTCA must be element-balanced"
    assert u.doubling_reactions() == [], "rTCA autocatalysis is topological — no coefficient-2 reaction"
    assert R.CARRIER == R.OAA
    # net turn over the 9 reactions: 1 OAA + 4 CO2 + 5 H2 -> 2 OAA + 3 H2O
    from collections import Counter
    net = Counter()
    for r in u.reactions:
        for s, n in r.products.items():
            net[s] += n
        for s, n in r.reactants.items():
            net[s] -= n
    assert net[U.CO2] == -4, "one turn fixes 4 CO2"
    assert net[U.H2] == -5, "one turn consumes 5 H2"
    assert net[R.OAA] == 1, "one turn nets +1 OAA (1 -> 2, carrier doubled)"
    assert net[U.H2O] == 3, "one turn produces 3 H2O"


def test_rtca_branched_specials_registered():
    """The branched C6 specials carry the right carbon count + formula."""
    from viva_genesis.protometabolism import rtca as R
    from viva_genesis.protometabolism import universe as U
    R.build_rtca_universe(potentials=_stub_potentials())
    for sid in (R.CITRATE, R.ISOCITRATE, R.ACONITATE):
        assert U.n_carbons(sid) == 6, f"{sid} is a branched C6 intermediate"
    assert U.n_carbons(R.OAA) == 4 and U.n_carbons(R.AKG) == 5 and U.n_carbons(R.ACETATE) == 2


# --- committed-artifact assertions ------------------------------------------- #
@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.exists():
        pytest.skip(f"{ARTIFACT.name} not found — run sims/compute_rtca_discriminator.py")
    return json.loads(ARTIFACT.read_text())


def test_rtca_vent_h2_washout(artifact):
    """Under real vent H2 the cycle does not self-amplify across the feed sweep
    (rtca-vent-h2-washout)."""
    assert artifact["vent_feasible"] is False
    for lbl, res in artifact["vent"].items():
        assert res["verdict"] == "refuted", f"vent {lbl} should be refuted"
        assert res["favorable"]["functional_autocatalysis"] is False
        assert res["favorable"]["seed_dependence"]["self_maintained"] is False


def test_rtca_permissive_limit_topology_specific(artifact):
    """The topology IS autocatalysis-capable + topology-specific in the labelled
    permissive counterfactual (rtca-permissive-limit-topology-specific)."""
    perm = artifact["counterfactual"]["permissive_limit"]
    assert perm["verdict"] == "MET"
    assert perm["topology_specific"] is True
    assert perm["favorable"]["functional_autocatalysis"] is True
    assert perm["matched_null"]["functional_autocatalysis"] is False


def test_gate_a_a2_branched_resolved(artifact):
    """Formose cross-check on the same discriminator is functionally refuted
    (seed-independent = feed-driven), so A2 is resolved for both routes
    (gate-a-a2-branched-resolved)."""
    f = artifact["formose_crosscheck"]
    assert f["verdict"] == "refuted"
    assert f["favorable"]["functional_autocatalysis"] is False
    sd = f["favorable"]["seed_dependence"]
    # seed-INDEPENDENT: seeded and unseeded fixation flux agree (feed-driven, not self-amplified)
    assert sd["seeded_flux"] == pytest.approx(sd["unseeded_flux"], rel=0.1)
    assert artifact["verdict"] == "honest-negative"
