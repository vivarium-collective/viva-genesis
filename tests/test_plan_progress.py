"""Derivation of the cumulative integration-gate board (Gate A-D/E) from member
studies' lifecycle gates — pure ``(investigation, studies) -> rows`` logic.

Mirrors the per-study six-axis ladder (vivarium-workbench study_page.py §13:
Plan←design_status, Execution←simulation_status, Evidence/Quality←evaluation_status,
Decision←gate_status, Release←expert_review_status) and rolls the Decision gates
up into each gate's status, honoring the cumulative ``extends`` chain.
"""
from viva_genesis.plan_progress import build_plan_progress, study_stage


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _study(slug, *, design=None, simulation=None, evaluation=None, gate=None,
           release=None, findings=None):
    spec = {"name": slug}
    if design is not None:
        spec["design_status"] = design
    if simulation is not None:
        spec["simulation_status"] = simulation
    if evaluation is not None:
        spec["evaluation_status"] = evaluation
    if gate is not None:
        spec["gate_status"] = gate
    if release is not None:
        spec["expert_review_status"] = release
    if findings is not None:
        spec["findings"] = findings
    return spec


def _planned(slug):
    return _study(slug, design="drafted", simulation="planned")


def _passed(slug, *, findings=None):
    return _study(slug, design="approved", simulation="ran", evaluation="evaluated",
                  gate="passed", release="signed_off", findings=findings)


_NULL_OK = [{"id": "x-beats-matched-null", "kind": "computational", "status": "confirms"}]
_NULL_PENDING = [{"id": "x-beats-matched-null", "kind": "computational", "status": "planned"}]


def _gates():
    """The origins-of-life-vent plan_gates shape (writer's block, condensed)."""
    return [
        {"id": "A", "name": "Chemical emergence", "extends": None,
         "member_studies": ["og-27", "og-28", "og-29"], "pending_studies": [],
         "criterion": "beat a matched null", "status": "pending"},
        {"id": "B", "name": "Spatial organization", "extends": "A",
         "member_studies": ["og-30"], "pending_studies": [],
         "criterion": "beat well-mixed control", "status": "pending"},
        {"id": "C", "name": "Self-compartmentation", "extends": "B",
         "member_studies": ["og-31"],
         "pending_studies": [{"plan_no": 32, "title": "First Self-Maintaining Protocell",
                              "scaffolded": False}],
         "criterion": "beat a matched ablation", "status": "pending"},
        {"id": "D", "name": "Reproduction & heredity", "extends": "C",
         "member_studies": [],
         "pending_studies": [{"plan_no": 33, "title": "Growth & Division", "scaffolded": False}],
         "criterion": "inherited fitness difference", "status": "pending"},
        {"id": "E", "name": "Optional extension", "extends": "D", "optional": True,
         "member_studies": [],
         "pending_studies": [{"plan_no": 35, "title": "Chemical Energy Coupling", "scaffolded": False}],
         "criterion": "matched ablation", "status": "pending"},
    ]


def _investigation():
    return {"name": "origins-of-life-vent", "plan_gates": _gates()}


def _by_id(rows):
    return {r["id"]: r for r in rows}


# --------------------------------------------------------------------------- #
# study_stage — the per-study "you are here" ladder
# --------------------------------------------------------------------------- #
def test_study_stage_planned_is_at_plan():
    st = study_stage(_study("s", design="drafted", simulation="planned"))
    # drafted is not a "passed" design token -> Plan is the current (in-progress) stage
    assert st["stage"] == "Plan"
    assert st["state"] in ("not-assessed", "in_progress")
    assert [g["label"] for g in st["ladder"]] == \
        ["Plan", "Execution", "Evidence", "Quality", "Decision", "Release"]


def test_study_stage_approved_design_advances_to_execution():
    st = study_stage(_study("s", design="approved", simulation="planned"))
    assert st["ladder"][0]["status"] == "passed"      # Plan passed
    assert st["stage"] == "Execution"                 # you-are-here


def test_study_stage_fully_passed_is_release():
    st = study_stage(_passed("s"))
    assert st["stage"] == "Release"
    assert all(g["status"] == "passed" for g in st["ladder"][:5])


def test_study_stage_blocked_axis_surfaces():
    st = study_stage(_study("s", design="approved", simulation="ran",
                            evaluation="failed"))
    evidence = next(g for g in st["ladder"] if g["label"] == "Evidence")
    assert evidence["status"] == "blocked"


# --------------------------------------------------------------------------- #
# build_plan_progress — gate roll-up
# --------------------------------------------------------------------------- #
def test_design_phase_A_in_progress_B_blocked_rest_pending():
    studies = {s: _planned(s) for s in ["og-27", "og-28", "og-29", "og-30", "og-31"]}
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A"]["status"] == "in_progress"   # members exist, none passed
    assert rows["B"]["status"] == "blocked"       # prior A not passed
    assert rows["C"]["status"] == "blocked"       # prior B not passed
    assert rows["D"]["status"] == "pending"       # no scaffolded members
    assert rows["E"]["status"] == "pending"


def test_gateA_passed_unblocks_B_to_in_progress():
    studies = {
        "og-27": _passed("og-27"),
        "og-28": _passed("og-28"),
        "og-29": _passed("og-29", findings=_NULL_OK),
        "og-30": _planned("og-30"),
        "og-31": _planned("og-31"),
    }
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A"]["status"] == "passed"        # all members passed + null confirmed
    assert rows["B"]["status"] == "in_progress"   # prior A passed, member 30 not passed
    assert rows["C"]["status"] == "blocked"       # prior B not passed


def test_matched_null_not_confirmed_holds_A_in_progress():
    # Every member's Decision gate passed, BUT the matched-null finding is still
    # planned -> the gate criterion isn't met -> not passed.
    studies = {
        "og-27": _passed("og-27"),
        "og-28": _passed("og-28"),
        "og-29": _passed("og-29", findings=_NULL_PENDING),
        "og-30": _planned("og-30"),
        "og-31": _planned("og-31"),
    }
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A"]["status"] == "in_progress"


def test_cumulative_B_not_passed_while_A_unpassed_even_if_member_passed():
    # Gate B's own member (30) is fully passed, but Gate A is NOT -> B is blocked,
    # never passed (cumulative rule).
    studies = {
        "og-27": _planned("og-27"), "og-28": _planned("og-28"), "og-29": _planned("og-29"),
        "og-30": _passed("og-30", findings=_NULL_OK),
        "og-31": _planned("og-31"),
    }
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A"]["status"] == "in_progress"
    assert rows["B"]["status"] == "blocked"


def test_gate_with_pending_member_cannot_pass():
    # Gate C has a scaffolded member (31) AND a pending study (32). Even with B
    # passed and 31 passed, C stays in_progress (not all members scaffolded).
    studies = {
        "og-27": _passed("og-27"), "og-28": _passed("og-28"),
        "og-29": _passed("og-29", findings=_NULL_OK),
        "og-30": _passed("og-30", findings=_NULL_OK),
        "og-31": _passed("og-31", findings=_NULL_OK),
    }
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A"]["status"] == "passed"
    assert rows["B"]["status"] == "passed"
    assert rows["C"]["status"] == "in_progress"   # pending_studies (32) still open


def test_row_shape_and_member_stages():
    studies = {s: _planned(s) for s in ["og-27", "og-28", "og-29", "og-30", "og-31"]}
    rows = build_plan_progress(_investigation(), studies)
    a = rows[0]
    assert a["id"] == "A" and a["name"] == "Chemical emergence"
    assert a["extends"] is None and a["member_studies"] == ["og-27", "og-28", "og-29"]
    assert "criterion" in a
    # member_stages: one entry per scaffolded own member, each with a current stage
    stages = {m["study"]: m for m in a["member_stages"]}
    assert set(stages) == {"og-27", "og-28", "og-29"}
    assert stages["og-27"]["stage"] == "Plan"
    # cumulative_members includes the extends-chain (B sees A's members too)
    b = _by_id(rows)["B"]
    assert set(b["cumulative_members"]) == {"og-27", "og-28", "og-29", "og-30"}


def test_unscaffolded_members_are_not_invented():
    # D/E reference only pending (unscaffolded) studies -> no member_stages rows.
    studies = {s: _planned(s) for s in ["og-27", "og-28", "og-29", "og-30", "og-31"]}
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["D"]["member_stages"] == []
    assert rows["D"]["pending_studies"]  # preserved passthrough
    assert rows["E"].get("optional") is True
