"""Derivation of the cumulative integration-gate board (A1/A2 + B-D/E) from member
studies' own evaluated verdicts — pure ``(investigation, studies) -> rows`` logic.

Mirrors the per-study six-axis ladder (vivarium-workbench study_page.py §13:
Plan←design_status, Execution←simulation_status, Evidence/Quality←evaluation_status,
Decision←gate_status, Release←expert_review_status) and rolls each gate's member
verdicts up into its OWN status (met/qualified/refuted), so an evaluated gate is
never "blocked" just because an upstream gate is only qualified or a sibling branch
was refuted. A1 is the spine root; A2 is an off-spine refuted branch that never
gates the spine; B/C/D build on A1.
"""
from viva_genesis.plan_progress import build_plan_progress, study_stage


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def _study(slug, *, design=None, simulation=None, evaluation=None, gate=None,
           release=None, verdict=None, findings=None):
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
    if verdict is not None:
        spec["verdict"] = verdict
    if findings is not None:
        spec["findings"] = findings
    return spec


def _planned(slug):
    # scaffolded but NOT yet run/evaluated
    return _study(slug, design="drafted", simulation="planned")


def _met(slug, *, findings=None):
    return _study(slug, design="approved", simulation="ran", evaluation="evaluated",
                  gate="passed", release="signed_off", verdict="supported", findings=findings)


def _qualified(slug, *, gate="needs_calibration", findings=None):
    return _study(slug, design="approved", simulation="ran", evaluation="evaluated",
                  gate=gate, verdict="qualified", findings=findings)


def _refuted(slug, *, findings=None):
    return _study(slug, design="approved", simulation="ran", evaluation="evaluated",
                  gate="failed", verdict="honest-negative", findings=findings)


# real matched-null / refutation findings carried by the member studies
_F_OG29_NULL_PLANNED = [{"id": "og29-beats-matched-null", "kind": "computational", "status": "planned"}]
_F_RTCA_CONTRADICTS = [{"id": "og-rtca-vent-h2-washout", "kind": "computational", "status": "contradicts"}]
_F_OG30_CONFIRMS = [{"id": "og30-pore-ignites-vs-control", "kind": "computational", "status": "confirms"}]


def _gates():
    """The restructured origins-of-life-vent plan_gates shape (A1 spine root,
    A2 off-spine branch, B/C/D extends A1->B->C)."""
    return [
        {"id": "A1", "name": "Network persistence", "extends": None,
         "member_studies": ["og-27", "og-28"], "pending_studies": [],
         "criterion": "network persists on bounded feeds", "status": "pending"},
        {"id": "A2", "name": "Endogenous autocatalysis", "extends": "A1", "off_spine": True,
         "member_studies": ["og-29", "og-rtca"], "pending_studies": [],
         "criterion_findings": ["og29-beats-matched-null", "og-rtca-vent-h2-washout"],
         "criterion": "autocatalysis must beat a matched null", "status": "pending"},
        {"id": "B", "name": "Spatial organization", "extends": "A1",
         "member_studies": ["og-30"], "pending_studies": [],
         "criterion_findings": ["og30-pore-ignites-vs-control"],
         "criterion": "pore beats well-mixed control", "status": "pending"},
        {"id": "C", "name": "Self-compartmentation", "extends": "B",
         "member_studies": ["og-31"],
         "pending_studies": [{"plan_no": 32, "title": "First Self-Maintaining Protocell",
                              "scaffolded": False}],
         "criterion": "membrane beats a matched ablation", "status": "pending"},
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


def _real_board_studies():
    """The real evaluated verdicts on main after #94: A1 qualified (og-27),
    A2 refuted (both), B met (og-30), C qualified (og-31 + pending 32)."""
    return {
        "og-27": _qualified("og-27"),                       # two-regime qualified
        "og-28": _met("og-28"),
        "og-29": _refuted("og-29", findings=_F_OG29_NULL_PLANNED),
        "og-rtca": _refuted("og-rtca", findings=_F_RTCA_CONTRADICTS),
        "og-30": _met("og-30", findings=_F_OG30_CONFIRMS),
        "og-31": _qualified("og-31", gate="passed"),
    }


def _by_id(rows):
    return {r["id"]: r for r in rows}


# --------------------------------------------------------------------------- #
# study_stage — the per-study "you are here" ladder (unchanged logic)
# --------------------------------------------------------------------------- #
def test_study_stage_planned_is_at_plan():
    st = study_stage(_study("s", design="drafted", simulation="planned"))
    assert st["stage"] == "Plan"
    assert st["state"] in ("not-assessed", "in_progress")
    assert [g["label"] for g in st["ladder"]] == \
        ["Plan", "Execution", "Evidence", "Quality", "Decision", "Release"]


def test_study_stage_approved_design_advances_to_execution():
    st = study_stage(_study("s", design="approved", simulation="planned"))
    assert st["ladder"][0]["status"] == "passed"
    assert st["stage"] == "Execution"


def test_study_stage_fully_passed_is_release():
    st = study_stage(_met("s"))
    assert st["stage"] == "Release"
    assert all(g["status"] == "passed" for g in st["ladder"][:5])


def test_study_stage_blocked_axis_surfaces():
    st = study_stage(_study("s", design="approved", simulation="ran", evaluation="failed"))
    evidence = next(g for g in st["ladder"] if g["label"] == "Evidence")
    assert evidence["status"] == "blocked"


# --------------------------------------------------------------------------- #
# build_plan_progress — the honest board
# --------------------------------------------------------------------------- #
def test_honest_board_matches_real_investigation():
    """The headline: A1 qualified · A2 refuted (branch) · B met · C qualified
    (partial) · D pending · E pending — each evaluated gate's OWN verdict."""
    rows = _by_id(build_plan_progress(_investigation(), _real_board_studies()))
    assert rows["A1"]["status"] == "qualified"
    assert rows["A2"]["status"] == "refuted"
    assert rows["B"]["status"] == "met"
    assert rows["C"]["status"] == "qualified"
    assert rows["D"]["status"] == "pending"
    assert rows["E"]["status"] == "pending"


def test_refuted_branch_never_blocks_spine():
    """A2 is refuted, but because it is off-spine (nothing extends it) and B
    extends A1 (not A2), B still derives its own met verdict — no false cascade."""
    rows = _by_id(build_plan_progress(_investigation(), _real_board_studies()))
    assert rows["A2"]["status"] == "refuted"
    assert rows["A2"].get("off_spine") is True
    assert rows["B"]["status"] == "met"          # the fix: not "blocked"


def test_qualified_spine_gate_lets_downstream_advance():
    """A spine gate that is only *qualified* (A1) still advances the spine: B's
    own evaluated verdict shows, it is not held blocked."""
    rows = _by_id(build_plan_progress(_investigation(), _real_board_studies()))
    assert rows["A1"]["status"] == "qualified"
    assert rows["B"]["status"] == "met"
    assert rows["C"]["status"] == "qualified"    # C extends B (met); og-31 qualified + pending 32


def test_evaluated_gate_shows_own_verdict_not_blocked():
    """Anti-cascade: even if the spine root is not clean-met, an evaluated gate
    reports its own verdict rather than inheriting a blocked state."""
    studies = _real_board_studies()
    # degrade A1 member og-27 so A1 is qualified (already is) — B must still be met
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["B"]["status"] == "met"


# --------------------------------------------------------------------------- #
# build_plan_progress — verdict derivation rules
# --------------------------------------------------------------------------- #
def test_met_requires_all_members_met_and_criterion_confirmed():
    studies = _real_board_studies()
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["B"]["status"] == "met"          # og-30 met + og30-pore-ignites confirms


def test_criterion_pending_holds_gate_in_progress():
    """og-30 met but its matched-control finding is still planned -> criterion
    not confirmed -> the gate cannot read met yet."""
    studies = _real_board_studies()
    studies["og-30"] = _met("og-30", findings=[
        {"id": "og30-pore-ignites-vs-control", "status": "planned"}])
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["B"]["status"] == "in_progress"


def test_criterion_contradicted_marks_gate_refuted():
    """A gate whose criterion_findings carry a contradiction is refuted (the
    positive claim is actively disproven) — this is A2's path."""
    rows = _by_id(build_plan_progress(_investigation(), _real_board_studies()))
    assert rows["A2"]["status"] == "refuted"


def test_all_refuted_members_mark_gate_refuted_without_findings():
    """Even with no criterion_findings, a gate whose every evaluated member is
    refuted reads refuted (member verdicts carry it)."""
    inv = {"name": "t", "plan_gates": [
        {"id": "A2", "name": "autocat", "extends": None, "off_spine": True,
         "member_studies": ["og-29", "og-rtca"], "pending_studies": [],
         "criterion": "beat null", "status": "pending"},
    ]}
    rows = _by_id(build_plan_progress(inv, {"og-29": _refuted("og-29"),
                                            "og-rtca": _refuted("og-rtca")}))
    assert rows["A2"]["status"] == "refuted"


def test_qualified_member_downgrades_gate_to_qualified():
    """A1: og-27 qualified + og-28 met, no pending members -> qualified (a genuine
    positive, with caveats), never a clean met."""
    rows = _by_id(build_plan_progress(_investigation(), _real_board_studies()))
    assert rows["A1"]["status"] == "qualified"


def test_pending_members_downgrade_met_to_qualified():
    """C: even if og-31 were a clean met, the open pending_study (32) keeps C at
    qualified (partial), not met."""
    studies = _real_board_studies()
    studies["og-31"] = _met("og-31")             # clean met member...
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["C"]["status"] == "qualified"    # ...but pending 32 -> qualified


# --------------------------------------------------------------------------- #
# build_plan_progress — pre-run states (blocked vs in_progress vs pending)
# --------------------------------------------------------------------------- #
def test_design_phase_unevaluated_members_block_or_progress():
    """Before anything runs: A1 in_progress (no prior), A2/B blocked (prior A1 not
    advanced + unevaluated members), C blocked, D/E pending."""
    studies = {s: _planned(s) for s in ["og-27", "og-28", "og-29", "og-rtca", "og-30", "og-31"]}
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A1"]["status"] == "in_progress"
    assert rows["A2"]["status"] == "blocked"
    assert rows["B"]["status"] == "blocked"
    assert rows["C"]["status"] == "blocked"
    assert rows["D"]["status"] == "pending"
    assert rows["E"]["status"] == "pending"


def test_blocked_flips_to_in_progress_once_prior_spine_advances():
    """B's members are still unevaluated, but once A1 is met/qualified the spine
    has advanced, so B is in_progress (can start), not blocked."""
    studies = {
        "og-27": _qualified("og-27"), "og-28": _met("og-28"),   # A1 -> qualified
        "og-29": _refuted("og-29"), "og-rtca": _refuted("og-rtca", findings=_F_RTCA_CONTRADICTS),
        "og-30": _planned("og-30"),                             # B member not yet run
        "og-31": _planned("og-31"),
    }
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["A1"]["status"] == "qualified"
    assert rows["B"]["status"] == "in_progress"                 # prior advanced, members unrun


def test_no_scaffolded_members_is_pending():
    studies = _real_board_studies()
    rows = _by_id(build_plan_progress(_investigation(), studies))
    assert rows["D"]["status"] == "pending"
    assert rows["D"]["member_stages"] == []
    assert rows["D"]["pending_studies"]                         # preserved passthrough
    assert rows["E"].get("optional") is True


# --------------------------------------------------------------------------- #
# build_plan_progress — row shape
# --------------------------------------------------------------------------- #
def test_row_shape_and_passthroughs():
    rows = build_plan_progress(_investigation(), _real_board_studies())
    by = _by_id(rows)
    a1 = by["A1"]
    assert a1["id"] == "A1" and a1["name"] == "Network persistence"
    assert a1["extends"] is None and a1["member_studies"] == ["og-27", "og-28"]
    assert "criterion" in a1 and a1.get("off_spine") is None
    # A2 carries off_spine + criterion_findings passthrough
    a2 = by["A2"]
    assert a2.get("off_spine") is True
    assert a2["criterion_findings"] == ["og29-beats-matched-null", "og-rtca-vent-h2-washout"]
    assert a2["extends"] == "A1"
    # member_stages: one entry per scaffolded own member
    stages = {m["study"]: m for m in a1["member_stages"]}
    assert set(stages) == {"og-27", "og-28"}
    # cumulative_members: B sees A1's members through the extends chain
    assert set(by["B"]["cumulative_members"]) == {"og-27", "og-28", "og-30"}


def test_unscaffolded_members_are_not_invented():
    rows = _by_id(build_plan_progress(_investigation(), _real_board_studies()))
    assert rows["D"]["member_stages"] == []
    assert rows["E"]["member_stages"] == []
    assert rows["E"].get("optional") is True
