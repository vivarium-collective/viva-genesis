import importlib.util, pathlib

spec = importlib.util.spec_from_file_location(
    "dv", pathlib.Path(__file__).resolve().parents[1] / "scripts/derive_study_verdict_tier.py")
dv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dv)


def test_passed_gate_is_supported():
    assert dv.derive({"name": "og-00", "gate_status": "passed"})[0] == "supported"


def test_known_honest_negatives():
    assert dv.derive({"name": "og-01-cal-electrochemistry", "gate_status": "failed"})[0] == "honest-negative"
    assert dv.derive({"name": "og-08-alt-robust-innovation-set", "gate_status": "failed"})[0] == "honest-negative"


def test_adversarial_is_refuted():
    s = {"name": "og-adv-generic-nonequilibrium", "gate_status": "passed",
         "parent_relations": [{"study": "og-00", "relation": "refutes"}]}
    assert dv.derive(s)[0] == "refuted"


def test_calibration_study_is_calibrated_tier():
    assert dv.derive({"name": "og-cal-vent-environment", "gate_status": "passed"})[1] == "calibrated"


def test_cal_in_name_is_not_calibrated_tier():
    # Phase-2's og-01-cal-electrochemistry is a sweep, not calibrated-to-data
    assert dv.derive({"name": "og-01-cal-electrochemistry", "gate_status": "failed"})[1] != "calibrated"


def test_existing_tier_is_preserved():
    assert dv.derive({"name": "og-x", "gate_status": "passed",
                      "evidence_tier": "mechanistic_prediction"})[1] == "mechanistic_prediction"


def test_default_is_supported_mechanistic():
    assert dv.derive({"name": "og-x", "gate_status": "passed"}) == ("supported", "mechanistic_prediction")
