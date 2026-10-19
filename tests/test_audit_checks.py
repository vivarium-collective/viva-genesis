"""Audit checks wired into lint-workspace: baseline-param + optional-import guards."""
from viva_genesis.audit_checks import (
    check_baseline_params,
    check_unguarded_optional_imports,
    check_used_imports_declared,
)


# --------------------------------------------------------------------------- #
# check_baseline_params
# --------------------------------------------------------------------------- #
def _study(baseline):
    return {"baseline": baseline}


def test_baseline_param_declared_is_clean():
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.g",
                             "params": {"flow_velocity": 1.0}}])}
    gen = {"pkg.m.g": {"flow_velocity", "nx"}}
    assert check_baseline_params(studies, gen) == []


def test_baseline_param_orphan_is_flagged():
    # The og-12 break: a param left after a repoint that the composite no longer declares.
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.g",
                             "params": {"model_proto_metabolism": "curated_rtca"}}])}
    gen = {"pkg.m.g": {"flow_velocity", "nx"}}
    errs = check_baseline_params(studies, gen)
    assert len(errs) == 1
    assert "model_proto_metabolism" in errs[0] and "pkg.m.g" in errs[0]


def test_baseline_unresolved_composite_is_skipped():
    # A planned / unresolved composite ref isn't in gen_parameters -> not our check.
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.planned",
                             "params": {"anything": 1}}])}
    assert check_baseline_params(studies, {"pkg.m.g": {"x"}}) == []


def test_baseline_empty_params_clean():
    studies = {"s": _study([{"name": "b", "composite": "pkg.m.g", "params": {}}])}
    assert check_baseline_params(studies, {"pkg.m.g": {"x"}}) == []


# --------------------------------------------------------------------------- #
# check_unguarded_optional_imports
# --------------------------------------------------------------------------- #
_OPT = {"viva_openmm", "openmm", "rdkit", "fipy"}


def test_module_level_optional_import_flagged():
    src = "import pytest\nimport viva_openmm\n\ndef test_x():\n    assert True\n"
    errs = check_unguarded_optional_imports([("test_martini.py", src)], _OPT)
    assert len(errs) == 1 and "viva_openmm" in errs[0]


def test_from_import_of_optional_flagged():
    src = "from openmm import unit\n"
    errs = check_unguarded_optional_imports([("test_md.py", src)], _OPT)
    assert len(errs) == 1 and "openmm" in errs[0]


def test_importorskip_guarded_is_clean():
    # The correct pattern — no bare module-level import of the dep.
    src = ('import pytest\n'
           'viva_openmm = pytest.importorskip("viva_openmm")\n'
           'def test_x():\n    assert viva_openmm\n')
    assert check_unguarded_optional_imports([("test_ok.py", src)], _OPT) == []


def test_import_inside_function_is_clean():
    # Nested (lazy) import runs only when the test runs — fine.
    src = "def test_x():\n    import rdkit\n    assert rdkit\n"
    assert check_unguarded_optional_imports([("test_lazy.py", src)], _OPT) == []


def test_non_optional_import_ignored():
    src = "import numpy\nimport pytest\n"
    assert check_unguarded_optional_imports([("test_n.py", src)], _OPT) == []


# --------------------------------------------------------------------------- #
# Batch 2 — evidence-integrity checks
# --------------------------------------------------------------------------- #
from viva_genesis.audit_checks import (  # noqa: E402
    check_dangling_refs,
    check_artifacts_exist,
    check_planned_not_passed,
    check_verdict_evidence,
    check_knife_edge_margins,
    check_units_present,
    check_gate_matched_null,
)


def test_dangling_from_test_and_runid_and_cite_and_prereq():
    spec = {
        "behavior_tests": [{"name": "t1"}],
        "runs": [{"name": "r1"}],
        "findings": [
            {"id": "F1", "evidence": {"from_test": "t1", "provenance": {}}},
            {"id": "F2", "evidence": {"from_test": "nope", "run_ids": ["r1", "rbad"]},
             "expected": {"cites": ["good", "bad"]}},
        ],
        "pipeline_gate": {"prerequisites": [{"study": "og-01"}, {"study": "ghost"}]},
    }
    # provenance.run_ids lives under evidence here; move for the checker's shape:
    spec["findings"][1]["provenance"] = {"run_ids": ["r1", "rbad"]}
    errs = check_dangling_refs({"s": spec}, {"og-01", "s"}, {"good"})
    joined = " ".join(errs)
    assert "nope" in joined and "rbad" in joined and "bad" in joined and "ghost" in joined
    assert "t1" not in joined.replace("from_test", "")  # t1 resolved


def test_dangling_all_resolve_is_clean():
    spec = {"behavior_tests": [{"name": "t1"}], "runs": [{"name": "r1"}],
            "findings": [{"id": "F", "evidence": {"from_test": "t1"},
                          "provenance": {"run_ids": ["r1"]}, "expected": {"cites": ["k"]}}],
            "pipeline_gate": {"prerequisites": [{"study": "og-01"}]}}
    assert check_dangling_refs({"s": spec}, {"og-01"}, {"k"}) == []


def test_artifacts_missing_for_ran_study_flagged():
    spec = {"simulation_status": "ran",
            "behavior_tests": [{"name": "t", "artifact": "workspace/studies/s/a.json"}]}
    res = lambda slug, rel: "missing"  # noqa: E731
    errs = check_artifacts_exist({"s": spec}, res)
    assert len(errs) == 1 and "a.json" in errs[0]


def test_artifacts_gitignored_run_db_skipped():
    spec = {"gate_status": "passed", "runs": [{"name": "r", "store_path": "runs.db"}]}
    res = lambda slug, rel: "ignored"  # noqa: E731
    assert check_artifacts_exist({"s": spec}, res) == []


def test_artifacts_not_checked_for_unran_study():
    spec = {"status": "planned",
            "behavior_tests": [{"name": "t", "artifact": "x.json"}]}
    res = lambda slug, rel: "missing"  # noqa: E731
    assert check_artifacts_exist({"s": spec}, res) == []


def test_planned_canonical_but_passed_flagged():
    spec = {"gate_status": "passed", "confidence": "Accepted",
            "baseline": [{"name": "b", "canonical": True, "planned": True}]}
    errs = check_planned_not_passed({"s": spec})
    assert len(errs) == 1 and "planned" in errs[0]


def test_planned_canonical_honestly_unpassed_is_clean():
    spec = {"status": "planned", "confidence": "Planned",
            "baseline": [{"name": "b", "canonical": True, "planned": True}]}
    assert check_planned_not_passed({"s": spec}) == []


def test_non_planned_passed_is_clean():
    spec = {"gate_status": "passed", "confidence": "Accepted",
            "baseline": [{"name": "b", "canonical": True, "planned": False}]}
    assert check_planned_not_passed({"s": spec}) == []


def test_verdict_evidence_missing_outcome_flagged():
    spec = {"gate_status": "passed",
            "behavior_tests": [{"name": "t", "classification": "primary"}],
            "runs": [{"name": "r", "outcomes": {}}]}
    errs = check_verdict_evidence({"s": spec})
    assert len(errs) == 1 and "no run outcome" in errs[0]


def test_verdict_evidence_fail_outcome_flagged():
    spec = {"gate_status": "passed",
            "behavior_tests": [{"name": "t", "classification": "primary"}],
            "runs": [{"name": "r", "outcomes": {"t": {"result": "FAIL"}}}]}
    errs = check_verdict_evidence({"s": spec})
    assert len(errs) == 1 and "not PASS" in errs[0]


def test_verdict_evidence_pass_is_clean():
    spec = {"gate_status": "passed",
            "behavior_tests": [{"name": "t", "classification": "primary"}],
            "runs": [{"name": "r", "outcomes": {"t": {"result": "PASS"}}}]}
    assert check_verdict_evidence({"s": spec}) == []


def test_knife_edge_continuous_flagged_invariant_skipped():
    spec = {"runs": [{"name": "r", "outcomes": {
        "cont": {"result": "PASS", "axis": {"severity": "hard", "margin": 0.0,
                                             "expected": {"op": ">="}}},
        "invariant": {"result": "PASS", "axis": {"severity": "hard", "margin": 0.0,
                                                 "expected": {"op": "=="}}},
    }}]}
    warns = check_knife_edge_margins({"s": spec})
    assert len(warns) == 1 and "cont" in warns[0]


def test_units_present_warn():
    spec = {"contract": {"face": {"outputs": {"flux": {"_type": "float"}},
                                  "inputs": {"T": {"_type": "float", "_units": "kelvin"}}}}}
    warns = check_units_present({"s": spec})
    assert len(warns) == 1 and "flux" in warns[0]


def test_gate_matched_null_authored_pass_unsupported():
    rows = [{"id": "A", "status": "in_progress"}]
    authored = [{"id": "A", "status": "passed"}]
    errs = check_gate_matched_null(rows, authored)
    assert len(errs) == 1 and "A" in errs[0]


def test_gate_matched_null_consistent_is_clean():
    rows = [{"id": "A", "status": "passed"}]
    authored = [{"id": "A", "status": "passed"}]
    assert check_gate_matched_null(rows, authored) == []


from viva_genesis.audit_checks import check_gate_members_in_roster  # noqa: E402


def test_gate_member_missing_from_roster_flagged():
    gates = [{"id": "A", "member_studies": ["og-27", "og-28"]}]
    errs = check_gate_members_in_roster("inv", gates, {"og-27"})
    assert len(errs) == 1 and "og-28" in errs[0]


def test_gate_members_all_in_roster_clean():
    gates = [{"id": "A", "member_studies": ["og-27", "og-28"]}]
    assert check_gate_members_in_roster("inv", gates, {"og-27", "og-28"}) == []


# --------------------------------------------------------------------------- #
# check_used_imports_declared — used wrapper must be declared in imports:
# --------------------------------------------------------------------------- #
def test_used_import_declared_is_clean():
    used = {"viva_equilibrator": "imported in viva_genesis/thermo.py",
            "viva_fenics": "imported in viva_genesis/core.py"}
    declared = {"viva_equilibrator", "viva_tellurium", "viva_fenics"}
    assert check_used_imports_declared(used, declared) == []


def test_used_but_undeclared_is_flagged():
    # The viva-openmm gap: used by core.py + og-31's local:OpenMMMartiniProcess,
    # never declared in imports: -> dashboard Repositories tab omits it.
    used = {"viva_openmm": "local:OpenMMMartiniProcess in viva_genesis/core.py",
            "viva_fenics": "imported in viva_genesis/core.py"}
    declared = {"viva_equilibrator", "viva_tellurium", "viva_fenics"}
    errs = check_used_imports_declared(used, declared)
    assert len(errs) == 1
    assert "viva_openmm" in errs[0]
    assert "OpenMMMartiniProcess" in errs[0]          # where-detected note surfaces
    assert "imports:" in errs[0]


def test_multiple_undeclared_are_each_flagged_sorted():
    used = {"viva_zeta": "imported in a.py", "viva_alpha": "imported in b.py"}
    errs = check_used_imports_declared(used, declared_packages=set())
    assert len(errs) == 2
    assert "viva_alpha" in errs[0] and "viva_zeta" in errs[1]   # sorted


# --------------------------------------------------------------------------- #
# Batch 3 — §6.2 calibration-vs-prediction tagging (evidence_basis)
# --------------------------------------------------------------------------- #
from viva_genesis.audit_checks import (  # noqa: E402
    check_evidence_basis_enum,
    check_evidence_basis_coverage,
    EVIDENCE_BASIS_VALUES,
)


def test_evidence_basis_enum_accepts_the_three_values():
    for v in EVIDENCE_BASIS_VALUES:
        spec = {"findings": [{"id": "F", "evidence_basis": v}]}
        assert check_evidence_basis_enum({"s": spec}) == []


def test_evidence_basis_enum_bad_value_on_finding_hard_fails():
    spec = {"findings": [{"id": "F1", "evidence_basis": "calibratd"}]}  # typo
    errs = check_evidence_basis_enum({"s": spec})
    assert len(errs) == 1
    assert "F1" in errs[0] and "calibratd" in errs[0] and "findings" in errs[0]


def test_evidence_basis_enum_bad_value_on_behavior_test_hard_fails():
    spec = {"behavior_tests": [{"name": "t1", "evidence_basis": "measured"}]}
    errs = check_evidence_basis_enum({"s": spec})
    assert len(errs) == 1 and "t1" in errs[0] and "behavior_tests" in errs[0]


def test_evidence_basis_enum_absent_is_clean():
    # Absence is NOT an enum error — coverage (WARN) handles absence separately.
    spec = {"findings": [{"id": "F", "evidence": {"observed": "x"}}]}
    assert check_evidence_basis_enum({"s": spec}) == []


def test_evidence_basis_coverage_decided_verdict_untagged_warns():
    spec = {"verdict": "supported", "status": "complete",
            "findings": [{"id": "F", "statement": "x"}],
            "behavior_tests": [{"name": "t"}]}
    warns = check_evidence_basis_coverage({"s": spec})
    assert len(warns) == 1 and "supported" in warns[0] and "evidence_basis" in warns[0]


def test_evidence_basis_coverage_one_tag_anywhere_is_enough():
    # A single tagged entry (on a finding OR a behavior_test) clears the study.
    spec = {"verdict": "qualified", "status": "complete",
            "findings": [{"id": "F", "evidence_basis": "calibrated"}],
            "behavior_tests": [{"name": "t"}]}
    assert check_evidence_basis_coverage({"s": spec}) == []
    spec2 = {"verdict": "qualified",
             "findings": [{"id": "F"}],
             "behavior_tests": [{"name": "t", "evidence_basis": "predicted"}]}
    assert check_evidence_basis_coverage({"s": spec2}) == []


def test_evidence_basis_coverage_planned_study_excluded():
    # A planned scaffold has no numbers to tag yet — never warned.
    spec = {"verdict": "supported", "status": "planned",
            "findings": [{"id": "F"}]}
    assert check_evidence_basis_coverage({"s": spec}) == []


def test_evidence_basis_coverage_no_verdict_excluded():
    # No decided verdict -> nothing feeds a verdict -> no coverage expectation.
    spec = {"status": "complete", "findings": [{"id": "F"}]}
    assert check_evidence_basis_coverage({"s": spec}) == []


# --------------------------------------------------------------------------- #
# Batch 3 — §6.6 avoid vacuous gates (inferred-tier coverage honesty)
# --------------------------------------------------------------------------- #
from viva_genesis.audit_checks import check_vacuous_inferred_coverage  # noqa: E402


def _atlas_study(finding_status, finding_kind="methodological",
                 test_name="inferred-tier-has-thermo-and-rate-basis",
                 description="the inferred tier extends connectivity ...",
                 measure_detail="fraction of inferred-tier reactions carrying a basis"):
    """og-network-persistence-shaped: an inferred-tier gate PASSING at 0, with a
    finding derived from it whose status/kind we vary."""
    return {
        "behavior_tests": [
            {"name": test_name, "classification": "primary",
             "description": description,
             "measure": {"kind": "observable", "detail": measure_detail}},
        ],
        "runs": [{"name": "r", "outcomes": {
            test_name: {"result": "PASS", "measured_value": 0,
                        "detail": "0 inferred-tier reactions; vacuously satisfied"}}}],
        "findings": [
            {"id": "f-inferred", "kind": finding_kind, "status": finding_status,
             "evidence": {"from_test": test_name}},
        ],
    }


def test_vacuous_honest_planned_finding_is_clean():
    # The current-main honest state: the zero-count gate's finding is planned.
    assert check_vacuous_inferred_coverage({"s": _atlas_study("planned")}) == []


def test_vacuous_delivered_inferred_finding_hard_fails():
    # Flip the finding to a delivered status with the tier still empty -> vacuous.
    errs = check_vacuous_inferred_coverage({"s": _atlas_study("novel")})
    assert len(errs) == 1
    assert "f-inferred" in errs[0] and "inferred-tier coverage" in errs[0] and "vacuous" in errs[0]


def test_vacuous_nonzero_measured_value_is_clean():
    # A real inferred tier (measured_value > 0) earns coverage — delivered is fine.
    spec = _atlas_study("novel")
    spec["runs"][0]["outcomes"]["inferred-tier-has-thermo-and-rate-basis"]["measured_value"] = 1.0
    assert check_vacuous_inferred_coverage({"s": spec}) == []


def test_vacuous_non_inferred_zero_pass_is_clean():
    # A zero-count pass on a test that is NOT an inferred-tier coverage gate is
    # not this check's concern (e.g. a legitimate "0 division failures").
    spec = _atlas_study("novel", test_name="no-division-failures",
                        description="division succeeds every cycle",
                        measure_detail="count of division failures")
    assert check_vacuous_inferred_coverage({"s": spec}) == []


# A write-gate-backed computational finding + the artifact/report plumbing rule
# (b) now requires. The by-construction signal is balance_violations_held > 0.
_WG_ART = "workspace/datasets/prebiotic-reaction-atlas/atlas_coverage_report.json"


def _writegate_study():
    return {
        "behavior_tests": [
            {"name": "atlas-write-gate-zero-leakage", "classification": "primary",
             "artifact": _WG_ART,
             "measure": {"kind": "observable",
                         "detail": "count of unbalanced / unsourced records admitted (target 0)"}},
        ],
        "runs": [{"name": "r", "outcomes": {
            "atlas-write-gate-zero-leakage": {"result": "PASS", "measured_value": 0}}}],
        "findings": [
            {"id": "f-chem", "kind": "computational", "status": "novel",
             "evidence": {"from_test": "atlas-write-gate-zero-leakage"}},
        ],
    }


def test_bookkeeping_gate_with_held_violations_hard_fails():
    # Report shows a violation held out -> the clean pass is by construction.
    spec = _writegate_study()
    reports = {_WG_ART: {"balance_violations_held": 1, "accepted_balance_violations": 0}}
    errs = check_vacuous_inferred_coverage({"s": spec}, reports)
    assert len(errs) == 1
    assert "f-chem" in errs[0] and "by-construction" in errs[0] and "methodological" in errs[0]


def test_bookkeeping_gate_no_held_violations_is_clean():
    # Nothing held out -> the atlas is balanced on the full set -> genuine, clean.
    spec = _writegate_study()
    reports = {_WG_ART: {"balance_violations_held": 0}}
    assert check_vacuous_inferred_coverage({"s": spec}, reports) == []


def test_bookkeeping_gate_no_report_is_clean():
    # No coverage report for the gate (e.g. a real ledger-closes residual == 0)
    # -> rule (b) has no by-construction signal -> never fires. This is the
    # og-vent-environment `ledger-closes` false-positive the re-key eliminated.
    spec = {
        "behavior_tests": [
            {"name": "ledger-closes",
             "measure": {"detail": "mass-balance residual of the closed ledger"}},
        ],
        "runs": [{"name": "r", "outcomes": {
            "ledger-closes": {"result": "PASS", "measured_value": 0}}}],
        "findings": [
            {"id": "ogcal-ledger-exact", "kind": "computational", "status": "novel",
             "evidence": {"from_test": "ledger-closes"}},
        ],
    }
    assert check_vacuous_inferred_coverage({"s": spec}, {}) == []


def test_bookkeeping_gate_as_methodological_is_clean():
    # The honest framing: the zero-leakage gate's finding is methodological (a
    # bookkeeping deliverable), not a chemistry result -> clean even with held-out.
    spec = _writegate_study()
    spec["findings"][0]["kind"] = "methodological"
    reports = {_WG_ART: {"balance_violations_held": 1}}
    assert check_vacuous_inferred_coverage({"s": spec}, reports) == []


def test_vacuous_no_runs_no_zero_pass_is_clean():
    # No run outcomes -> no zero-count pass to credit -> inert.
    spec = {"behavior_tests": [{"name": "inferred-tier-x"}],
            "findings": [{"id": "f", "kind": "computational", "status": "novel",
                          "evidence": {"from_test": "inferred-tier-x"}}]}
    assert check_vacuous_inferred_coverage({"s": spec}) == []


# --------------------------------------------------------------------------- #
# check_arm_resource_refs — study-arm resource: must resolve to a registered id
# --------------------------------------------------------------------------- #
from viva_genesis.audit_checks import check_arm_resource_refs  # noqa: E402


def test_arm_resource_ref_resolved_is_clean():
    # The #153 shape: an arm points at a registered Resource id.
    studies = {"og-network-persistence": {"arms": [
        {"id": "28_prebiotic_reaction_atlas", "resource": "prebiotic-reaction-atlas"}]}}
    assert check_arm_resource_refs(studies, {"prebiotic-reaction-atlas", "pathway-formose"}) == []


def test_arm_resource_ref_dangling_is_flagged():
    studies = {"s": {"arms": [{"id": "a1", "resource": "renamed-or-typod-atlas"}]}}
    errs = check_arm_resource_refs(studies, {"prebiotic-reaction-atlas"})
    assert len(errs) == 1
    assert "renamed-or-typod-atlas" in errs[0] and "a1" in errs[0] and "structured_resources" in errs[0]


def test_arm_resource_ref_list_each_checked():
    studies = {"s": {"arms": [{"id": "a1", "resource": ["prebiotic-reaction-atlas", "ghost-resource"]}]}}
    errs = check_arm_resource_refs(studies, {"prebiotic-reaction-atlas"})
    assert len(errs) == 1 and "ghost-resource" in errs[0]


def test_arm_without_resource_is_clean():
    studies = {"s": {"arms": [{"id": "a1", "source_study": "og-28"}]}}
    assert check_arm_resource_refs(studies, {"prebiotic-reaction-atlas"}) == []


def test_arm_resource_ref_empty_registry_skips():
    # Registry unreadable/empty -> skip rather than false-fail every ref.
    studies = {"s": {"arms": [{"id": "a1", "resource": "anything"}]}}
    assert check_arm_resource_refs(studies, set()) == []
