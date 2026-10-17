"""Write-time validator for the Prebiotic Reaction Atlas (Study 28 / upgrade plan).

The plan's decision test for Study 28 is "No unexplained precursor or unbalanced
reaction enters an accepted model." This validator ENFORCES that at write time —
it computes mass + charge balance from the species formulas and stoichiometry
(it does NOT trust a record's self-reported ``mass_balanced`` flag), and rejects
a record that claims balance it does not have. It closes the dataset-audit gap
(audit-build-capability-gaps.md gaps 1/3/4).
"""
from viva_genesis.reaction_atlas.validate import (
    parse_formula,
    reaction_balance,
    validate_record,
    is_acceptable,
)


def test_parse_formula_counts_elements():
    assert parse_formula("CO2") == {"C": 1, "O": 2}
    assert parse_formula("C2H4O2") == {"C": 2, "H": 4, "O": 2}
    assert parse_formula("H2O") == {"H": 2, "O": 1}


def test_reaction_balance_balanced():
    # CO2 + H2 -> CH2O2 (formic acid): C1 O2 H2 both sides, neutral.
    formulas = {"co2": ("CO2", 0), "h2": ("H2", 0), "formate": ("CH2O2", 0)}
    r = reaction_balance({"co2": 1, "h2": 1}, {"formate": 1}, formulas)
    assert r["mass_balanced"] is True
    assert r["charge_balanced"] is True


def test_reaction_balance_detects_mass_imbalance():
    # CO2 -> CH2O2 drops the H2: not mass balanced.
    formulas = {"co2": ("CO2", 0), "formate": ("CH2O2", 0)}
    r = reaction_balance({"co2": 1}, {"formate": 1}, formulas)
    assert r["mass_balanced"] is False
    assert r["element_diff"].get("H") != 0


def test_reaction_balance_detects_charge_imbalance():
    # CO2 + H2 -> formate(-1): charge not balanced (0 -> -1).
    formulas = {"co2": ("CO2", 0), "h2": ("H2", 0), "formate": ("CH2O2", -1)}
    r = reaction_balance({"co2": 1, "h2": 1}, {"formate": 1}, formulas)
    assert r["charge_balanced"] is False


def _good_record():
    return {
        "id": "pra-000001",
        "tier": "measured",
        "species": [
            {"chebi_id": "co2", "formula": "CO2", "charge": 0, "role": "reactant"},
            {"chebi_id": "h2", "formula": "H2", "charge": 0, "role": "reactant"},
            {"chebi_id": "formate", "formula": "CH2O2", "charge": 0, "role": "product"},
        ],
        "reaction": {
            "equation": "CO2 + H2 -> CH2O2",
            "reactants": {"co2": 1, "h2": 1},
            "products": {"formate": 1},
            "mass_balanced": True,
            "charge_balanced": True,
            "proton_convention": "pH 9, aqueous, 1 M standard state",
        },
        "conditions": {"temperature_c": 100.0, "pH": 9.0, "catalyst_mineral": "Fe(Ni)S"},
        "kinetics": {"rate_form": "mass-action", "parameters": {}, "is_range": False, "uncertainty": {}},
        "evidence": {
            "source_doi": "10.1038/s41586-019-1151-1",
            "source_key": "muchowska2019synthesis",
            "extracted_fields": ["conditions", "reaction"],
            "verified_against_source": True,
        },
        "provenance": {"acquisition": "extracted", "added_by": "test", "added_at": "2026-10-17"},
    }


def test_good_record_has_no_violations_and_is_acceptable():
    rec = _good_record()
    assert validate_record(rec) == []
    assert is_acceptable(rec) is True


def test_record_claiming_false_balance_is_rejected():
    # The record SAYS mass_balanced but drops H2 — the whole point of the gate.
    rec = _good_record()
    rec["reaction"]["reactants"] = {"co2": 1}  # removed h2
    violations = validate_record(rec)
    assert any("mass" in v.lower() for v in violations)
    assert is_acceptable(rec) is False


def test_missing_source_doi_is_a_violation():
    rec = _good_record()
    rec["evidence"]["source_doi"] = ""
    assert any("source_doi" in v for v in validate_record(rec))


def test_bad_tier_is_a_violation():
    rec = _good_record()
    rec["tier"] = "guessed"
    assert any("tier" in v.lower() for v in validate_record(rec))


def test_measured_tier_requires_source_verification():
    rec = _good_record()
    rec["evidence"]["verified_against_source"] = False
    assert any("verified_against_source" in v for v in validate_record(rec))


def test_reaction_ref_must_resolve_to_a_species():
    rec = _good_record()
    rec["reaction"]["products"] = {"unknown_species": 1}
    assert any("unknown_species" in v for v in validate_record(rec))
