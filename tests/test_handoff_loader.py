"""Loader: read study.yaml handoff blocks into validator records.

Bridges the on-disk studies to viva_genesis.handoff.validate. Reads each
study.yaml's ``plan_id`` (or derives it from the ``og-<n>-...`` slug), its
``builds_on``, and its structured ``handoff`` block. A study with no handoff
block loads with an empty one, so the validator reports the undeclared handoff
rather than crashing.
"""
import textwrap
from viva_genesis.handoff.load import plan_id_from_slug, load_investigation


def test_plan_id_from_slug():
    assert plan_id_from_slug("og-27-coupled-geochemical-reaction-interface") == 27
    assert plan_id_from_slug("og-7-ecology-before-luca") == 7
    assert plan_id_from_slug("not-a-study") is None


def _write_study(root, slug, body):
    d = root / "studies" / slug
    d.mkdir(parents=True)
    (d / "study.yaml").write_text(textwrap.dedent(body))


def test_load_investigation_reads_handoff_blocks(tmp_path):
    _write_study(tmp_path, "og-27-coupled-geochemical-reaction-interface", """
        name: og-27-coupled-geochemical-reaction-interface
        builds_on: [0, 1, 14, 15]
        handoff:
          emits:
            - to: 29
              provides: [H2 flux, inorganic carbon flux, pH, T, ionic activities, catalyst state, time-dependent feeds]
    """)
    _write_study(tmp_path, "og-29-endogenous-autocatalysis", """
        name: og-29-endogenous-autocatalysis
        builds_on: [2, 16, 27, 28]
        handoff:
          receives:
            - from: 27
              requires: [H2 flux, inorganic carbon flux, pH, T, ionic activities, catalyst state, time-dependent feeds]
    """)
    studies = load_investigation(tmp_path / "studies")
    by_id = {s["plan_id"]: s for s in studies}
    assert set(by_id) == {27, 29}
    assert by_id[27]["handoff"]["emits"][0]["to"] == 29
    assert by_id[29]["handoff"]["receives"][0]["from"] == 27
    assert by_id[27]["builds_on"] == [0, 1, 14, 15]


def test_study_without_handoff_block_loads_empty(tmp_path):
    _write_study(tmp_path, "og-30-spatially-integrated-protometabolism", """
        name: og-30-spatially-integrated-protometabolism
        builds_on: [3, 11, 21, 27, 29]
    """)
    studies = load_investigation(tmp_path / "studies")
    assert studies[0]["handoff"] == {"emits": [], "receives": []}
