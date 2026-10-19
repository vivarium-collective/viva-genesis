"""og-32b assertions against the committed multi-seed artifact (no MD re-run).

Reads artifacts/vesicle_stability.json (the deterministic result of the fatty-acid
vesicle stability sweep) and checks the Gate-C claims hold: protonated fatty-acid
vesicles are stable across C10-C16, the charged-only null micellises at the short
corner, and every arm is multi-seed with unanimous per-arm verdicts.
"""
import json
import pathlib

ART = pathlib.Path(__file__).resolve().parents[1] / "artifacts" / "vesicle_stability.json"


def _arms():
    d = json.loads(ART.read_text())
    return {a["label"]: a for a in d["arms"]}, d


def test_all_protonated_chains_stable():
    arms, d = _arms()
    prot = [a for a in arms.values() if a["protonated"]]
    assert {a["chain"] for a in prot} == {10, 12, 14, 16}
    for a in prot:
        assert a["verdict"] == "stable_vesicle", a["label"]
        assert a["inner_leaflet_fraction"] >= d["verdict_thresholds"]["inner_leaflet_min"]
        assert a["head_radial_cv"] <= d["verdict_thresholds"]["head_radial_cv_max"]
        assert a["n_stable_seeds"] == a["n_seeds"]          # unanimous


def test_charged_null_micellises_short_corner():
    arms, d = _arms()
    c10n = arms["C10_charged_null"]
    assert c10n["verdict"] == "micellised"
    assert c10n["head_radial_cv"] > d["verdict_thresholds"]["head_radial_cv_max"]
    assert c10n["n_stable_seeds"] == 0                      # unanimous failure


def test_multi_seed_and_real_amphiphile():
    arms, _ = _arms()
    for a in arms.values():
        assert a["n_seeds"] >= 3                            # >= 3 independent replicates
        assert a["n_lipids"] > 100                          # a real built vesicle
