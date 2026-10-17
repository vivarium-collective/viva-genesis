import json, pathlib, jsonschema, pytest

SCHEMA = json.loads((pathlib.Path(__file__).resolve().parents[1]
                     / ".pbg/schemas/study.schema.json").read_text())


def _valid_study(**extra):
    base = {
        "schema_version": 4, "name": "og-x",
        "baseline": [{"name": "b", "composite": "a.b"}],
    }
    base.update(extra)
    return base


def test_verdict_and_tier_accept_valid_enums():
    # Two-axis ontology: the four canonical verdicts (honest-negative folds to
    # refuted, mixed to inconclusive — they are no longer valid enum values).
    for v in ["supported", "qualified", "inconclusive", "refuted"]:
        jsonschema.validate(_valid_study(verdict=v), SCHEMA)
    for t in ["conceptual_demonstration", "mechanistic_prediction", "calibrated"]:
        jsonschema.validate(_valid_study(evidence_tier=t), SCHEMA)


def test_verdict_rejects_out_of_enum():
    # Retired values and bare invalids both rejected.
    for v in ["accepted", "honest-negative", "mixed"]:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_valid_study(verdict=v), SCHEMA)


def test_evidence_tier_rejects_out_of_enum():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_valid_study(evidence_tier="mechanistic"), SCHEMA)


def test_fields_are_optional():
    jsonschema.validate(_valid_study(), SCHEMA)
