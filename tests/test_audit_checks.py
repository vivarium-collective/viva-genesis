"""Audit checks wired into lint-workspace: baseline-param + optional-import guards."""
from viva_genesis.audit_checks import (
    check_baseline_params,
    check_unguarded_optional_imports,
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
