"""Builder for the Prebiotic Reaction Atlas (Study 28 asset; reused by 29/31).

The builder turns raw candidate reactions into schema-shaped records the
write-time validator accepts, then routes balanced/valid records to ``accepted``
and the rest to ``proposed``. These tests are offline-safe: the pure pipeline
(extract from explicit formulas -> validate -> route) needs no deps; the RDKit
canonicalization and the eQuilibrator ΔG bridge are exercised real-where-present
(``importorskip``) and via an injected stub estimator (no network, ever).

Importing the module here also proves import-safety: RDKit / viva_equilibrator
are NOT installed in the CI venv, so a non-lazy import would fail collection.
"""
import pytest

from viva_genesis.reaction_atlas import build
from viva_genesis.reaction_atlas.build import (
    build_atlas,
    extract_record,
    feasibility,
)
from viva_genesis.reaction_atlas.validate import is_acceptable, validate_record


# --------------------------------------------------------------------------- #
# helpers — raw records keyed by explicit formula/charge (no RDKit needed)
# --------------------------------------------------------------------------- #
def _raw_formic(balanced: bool = True):
    """CO2 + H2 -> CH2O2 (formic acid). When ``balanced`` is False, drop H2."""
    reactants = {"co2": 1, "h2": 1} if balanced else {"co2": 1}
    return {
        "id": "pra-build-0001",
        "tier": "inferred",
        "species": [
            {"chebi_id": "co2", "formula": "CO2", "charge": 0, "role": "reactant"},
            {"chebi_id": "h2", "formula": "H2", "charge": 0, "role": "reactant"},
            {"chebi_id": "formate", "formula": "CH2O2", "charge": 0, "role": "product"},
        ],
        "reaction": {"reactants": reactants, "products": {"formate": 1},
                     "proton_convention": "pH 7, aqueous, 1 M"},
        "conditions": {"temperature_c": 100.0, "pH": 7.0, "catalyst_mineral": "Fe(Ni)S"},
        "evidence": {
            "source_doi": "10.1038/s41586-019-1151-1",
            "source_key": "muchowska2019synthesis",
            "extracted_fields": ["reaction"],
        },
        "provenance": {"acquisition": "extracted"},
    }


# --------------------------------------------------------------------------- #
# import-safety
# --------------------------------------------------------------------------- #
def test_module_imports_without_rdkit_or_equilibrator():
    # Reaching the public surface must not require either heavy dep.
    assert callable(build.extract_record)
    assert callable(build.build_atlas)
    assert callable(build.canonical_formula_charge)


# --------------------------------------------------------------------------- #
# extract_record — balance computed from the formulas
# --------------------------------------------------------------------------- #
def test_extract_computes_balance_from_formulas():
    rec = extract_record(_raw_formic(balanced=True))
    assert rec["reaction"]["mass_balanced"] is True
    assert rec["reaction"]["charge_balanced"] is True
    # schema-shaped: reaction carries reactants/products + an equation string
    assert rec["reaction"]["reactants"] == {"co2": 1, "h2": 1}
    assert "=" in rec["reaction"]["equation"]
    # the record the validator sees is well-formed and acceptable
    assert validate_record(rec) == []
    assert is_acceptable(rec) is True


def test_extract_overrides_self_reported_balance():
    # A raw record that LIES about balance (claims True while dropping H2) is
    # recomputed to False — the builder never trusts the raw flag.
    raw = _raw_formic(balanced=False)
    raw["reaction"]["mass_balanced"] = True
    rec = extract_record(raw)
    assert rec["reaction"]["mass_balanced"] is False
    assert is_acceptable(rec) is False


def test_extract_fills_required_scaffold_fields():
    rec = extract_record(_raw_formic(), added_at="2026-10-17")
    for key in ("id", "tier", "species", "reaction", "conditions",
                "kinetics", "evidence", "provenance"):
        assert key in rec
    assert rec["kinetics"]["rate_form"] == "n/a"          # default filled
    assert rec["provenance"]["added_at"] == "2026-10-17"  # tool-stamped


def test_extract_is_study_agnostic_via_params():
    # Same builder, Study-29-style candidate: rule-generated acquisition + tier.
    rec = extract_record(
        {**_raw_formic(), "id": "cand-1", "tier": None,
         "provenance": {}},  # let params supply acquisition/tier
        default_tier="hypothetical",
        acquisition="rule-generated",
    )
    assert rec["tier"] == "hypothetical"
    assert rec["provenance"]["acquisition"] == "rule-generated"


# --------------------------------------------------------------------------- #
# build_atlas — routing
# --------------------------------------------------------------------------- #
def test_build_atlas_routes_accepted_and_proposed():
    res = build_atlas([_raw_formic(balanced=True), _raw_formic(balanced=False)])
    assert len(res.accepted) == 1
    assert len(res.proposed) == 1
    assert res.accepted[0]["reaction"]["mass_balanced"] is True
    # proposed records are annotated with the reason they were rejected
    assert res.proposed[0]["_violations"]
    assert any("mass" in v.lower() for v in res.proposed[0]["_violations"])


def test_build_atlas_accepted_all_pass_validator():
    res = build_atlas([_raw_formic(balanced=True)])
    for rec in res.accepted:
        assert validate_record(rec) == []
        assert is_acceptable(rec) is True


def test_build_atlas_missing_provenance_routed_to_proposed():
    # No source_doi -> validator rejects -> proposed, not accepted (no fabrication).
    raw = _raw_formic(balanced=True)
    raw["evidence"] = {}
    res = build_atlas([raw])
    assert len(res.accepted) == 0
    assert any("source_doi" in v for v in res.proposed[0]["_violations"])


# --------------------------------------------------------------------------- #
# feasibility — injected stub (offline) + routing is independent of ΔG
# --------------------------------------------------------------------------- #
def test_feasibility_with_stub_estimator():
    calls = {}

    def stub(formulas, *, p_h, ionic_strength_M, temperature_K):
        calls["ph"] = p_h
        return {name: (-30.0, 2.0) for name in formulas}

    rec = feasibility(extract_record(_raw_formic()), estimator=stub)
    assert rec["thermodynamics"]["delta_g_kj_mol"] == -30.0
    assert rec["thermodynamics"]["feasible"] is True      # ΔG'° <= 0
    assert calls["ph"] == 7.0                              # pulled from conditions.pH


def test_feasibility_positive_dg_is_infeasible():
    def stub(formulas, *, p_h, ionic_strength_M, temperature_K):
        return {name: (+25.0, 3.0) for name in formulas}

    rec = feasibility(extract_record(_raw_formic()), estimator=stub)
    assert rec["thermodynamics"]["feasible"] is False


def test_build_atlas_feasibility_does_not_gate_acceptance():
    # An infeasible ΔG must NOT drop an otherwise-valid, balanced record.
    def infeasible(formulas, *, p_h, ionic_strength_M, temperature_K):
        return {name: (+50.0, 1.0) for name in formulas}

    res = build_atlas([_raw_formic(balanced=True)], estimator=infeasible)
    assert len(res.accepted) == 1
    assert res.accepted[0]["thermodynamics"]["feasible"] is False


# --------------------------------------------------------------------------- #
# RDKit bridge — real where present
# --------------------------------------------------------------------------- #
def test_canonical_formula_charge_real_rdkit():
    pytest.importorskip("rdkit")
    from viva_genesis.reaction_atlas.build import canonical_formula_charge
    assert canonical_formula_charge("O=C=O") == ("CO2", 0)      # carbon dioxide
    assert canonical_formula_charge("[H][H]") == ("H2", 0)      # dihydrogen
    assert canonical_formula_charge("OC=O") == ("CH2O2", 0)     # formic acid
    f, c = canonical_formula_charge("[OH-]")                    # hydroxide ion
    assert c == -1


def test_extract_canonicalizes_from_smiles_real_rdkit():
    pytest.importorskip("rdkit")
    raw = {
        "id": "pra-smiles-1",
        "tier": "inferred",
        "species": [
            {"chebi_id": "co2", "smiles": "O=C=O", "role": "reactant"},
            {"chebi_id": "h2", "smiles": "[H][H]", "role": "reactant"},
            {"chebi_id": "formate", "smiles": "OC=O", "role": "product"},
        ],
        "reaction": {"reactants": {"co2": 1, "h2": 1}, "products": {"formate": 1}},
        "evidence": {"source_doi": "10.1038/s41586-019-1151-1"},
        "provenance": {"acquisition": "extracted"},
    }
    rec = extract_record(raw)
    formulas = {s["chebi_id"]: s["formula"] for s in rec["species"]}
    assert formulas == {"co2": "CO2", "h2": "H2", "formate": "CH2O2"}
    assert rec["reaction"]["mass_balanced"] is True
    assert is_acceptable(rec) is True
