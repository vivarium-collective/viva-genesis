import pathlib, yaml

STUDIES = sorted((pathlib.Path(__file__).resolve().parents[1]
                  / "workspace/studies").glob("*/study.yaml"))
V = {"supported", "qualified", "honest-negative", "refuted", "mixed"}
T = {"conceptual_demonstration", "mechanistic_prediction", "calibrated"}


def test_every_study_has_valid_markers():
    missing = []
    for p in STUDIES:
        d = yaml.safe_load(p.read_text()) or {}
        if d.get("verdict") not in V or d.get("evidence_tier") not in T:
            missing.append(p.parent.name)
    assert not missing, f"studies missing/invalid markers: {missing}"
