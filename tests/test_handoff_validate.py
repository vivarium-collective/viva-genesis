"""Builds-on handoff-contract validator (upgrade plan §"Explicit interfaces").

The plan says a ``builds on`` edge must be "a real mechanistic or material
dependency, not mere topical similarity," with an explicit required-transferred-
state per edge (the handoff table). This validator enforces that: for every
handoff edge in the table, the upstream study must EMIT the required state to the
downstream study, and the downstream must declare it RECEIVES it — covering every
required item. It reads a structured ``handoff`` block, not prose, so the check is
deterministic. Closes capability gap 6 in audit-build-capability-gaps.md.
"""
from viva_genesis.handoff.validate import (
    required_state,
    covers,
    validate_investigation,
)


def test_required_state_lookup():
    rs = required_state(27, 29)
    assert rs is not None
    assert "catalyst state" in rs
    assert "h2 flux" in rs
    assert required_state(1, 2) is None  # not a contract edge


def test_covers_is_token_subset_and_synonym_aware():
    provided = ["H2 and inorganic-carbon flux", "catalyst (mineral-surface) state"]
    assert covers("h2 flux", provided)
    assert covers("inorganic carbon flux", provided)
    assert covers("catalyst state", provided)
    assert not covers("permeability", provided)
    # 'T' is a synonym of temperature
    assert covers("temperature", ["pH, T and ionic activities"])


def _study(plan_id, builds_on=(), emits=(), receives=()):
    return {
        "id": f"og-{plan_id}",
        "plan_id": plan_id,
        "builds_on": list(builds_on),
        "handoff": {
            "emits": [{"to": t, "provides": list(p)} for (t, p) in emits],
            "receives": [{"from": f, "requires": list(r)} for (f, r) in receives],
        },
    }


def _good_27_28_29():
    s27 = _study(27, builds_on=[0, 1, 14, 15], emits=[
        (29, ["H2 flux", "inorganic carbon flux", "pH", "temperature",
              "ionic activities", "catalyst state", "time-dependent feeds"])])
    s28 = _study(28, builds_on=[1, 2, 16], emits=[
        (29, ["canonical species", "balanced stoichiometry", "rate forms",
              "parameter bounds", "confidence tags"])])
    s29 = _study(29, builds_on=[2, 16, 27, 28], receives=[
        (27, ["H2 flux", "inorganic carbon flux", "pH", "temperature",
              "ionic activities", "catalyst state", "time-dependent feeds"]),
        (28, ["canonical species", "balanced stoichiometry", "rate forms",
              "parameter bounds", "confidence tags"])])
    return [s27, s28, s29]


def test_complete_edges_have_no_violations():
    assert validate_investigation(_good_27_28_29()) == []


def test_missing_emit_is_a_violation():
    studies = _good_27_28_29()
    studies[0]["handoff"]["emits"] = []  # 27 emits nothing
    viol = validate_investigation(studies)
    assert any("27" in v and "emit" in v.lower() and "29" in v for v in viol)


def test_missing_receive_is_a_violation():
    studies = _good_27_28_29()
    studies[2]["handoff"]["receives"] = [r for r in studies[2]["handoff"]["receives"]
                                         if r["from"] != 28]  # 29 drops receive-from-28
    viol = validate_investigation(studies)
    assert any("29" in v and "receive" in v.lower() and "28" in v for v in viol)


def test_incomplete_coverage_names_missing_item():
    studies = _good_27_28_29()
    # 27 emits everything except catalyst state
    studies[0]["handoff"]["emits"][0]["provides"] = [
        "H2 flux", "inorganic carbon flux", "pH", "temperature",
        "ionic activities", "time-dependent feeds"]
    viol = validate_investigation(studies)
    assert any("catalyst state" in v for v in viol)


def test_edge_with_unscaffolded_downstream_is_skipped():
    # Only 27 + 28 present; 29 not scaffolded yet -> no handoff violations for 27/28->29.
    studies = [_good_27_28_29()[0], _good_27_28_29()[1]]
    assert validate_investigation(studies) == []
