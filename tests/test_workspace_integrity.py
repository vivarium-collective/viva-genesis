"""Workspace-integrity guards that pytest enforces independently of scripts/lint-workspace.py.

Both classes here were real holes the consolidation wave hit:

- an unparseable ``investigation.yaml`` (a multi-line plain ``role:``/prose scalar
  containing ``": "``, read by YAML as a mapping indicator) silently skipped the
  gate-member-in-roster audit for the whole wave — so the file MUST ``safe_load``;
- a consolidation fold ``git mv``s artifacts into the consolidated study dir, and a
  source reader (a dashboard viz default, an evaluator path) left at the pre-fold
  path then fails only at RUNTIME — neither the audit lint's study.yaml checks nor
  the rest of pytest covers it, so every ``workspace/studies/<slug>/artifacts|viz``
  path hardcoded in ``viva_genesis/`` source MUST resolve on disk.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WS_ROOT = Path(__file__).resolve().parents[1]
_INV_DIR = WS_ROOT / "workspace" / "investigations"
_PKG = WS_ROOT / "viva_genesis"


def test_every_investigation_yaml_parses():
    """Every investigations/*/investigation.yaml must be valid YAML (safe_load)."""
    inv_files = sorted(_INV_DIR.glob("*/investigation.yaml"))
    assert inv_files, "no investigation.yaml found — workspace layout changed?"
    for inv in inv_files:
        try:
            yaml.safe_load(inv.read_text())
        except Exception as exc:  # noqa: BLE001 — report which file + why
            raise AssertionError(
                f"{inv.relative_to(WS_ROOT)} is not valid YAML ({exc}) — quote any "
                f"multi-line role/prose scalar containing ': '"
            ) from exc


def test_source_hardcoded_artifact_paths_resolve():
    """Every workspace artifact/viz path hardcoded in viva_genesis/ source resolves.

    Matches full ``.../X.json|.html`` paths and split-literal ``.../artifacts/<slug>/``
    directory prefixes (the dir-prefix + filename-on-next-line idiom).
    """
    path_re = re.compile(r"workspace/studies/[A-Za-z0-9_./-]+")
    stale: list[str] = []
    for py in sorted(_PKG.rglob("*.py")):
        try:
            src = py.read_text()
        except Exception:
            continue
        rel = py.relative_to(WS_ROOT)
        for tok in path_re.findall(src):
            if tok.endswith((".json", ".html")):
                if not (WS_ROOT / tok).is_file():
                    stale.append(f"{rel}: '{tok}' is not a file")
            elif tok.endswith("/") and ("/artifacts/" in tok or "/viz/" in tok):
                if not (WS_ROOT / tok).is_dir():
                    stale.append(f"{rel}: directory '{tok}' does not exist")
    assert not stale, (
        "stale hardcoded artifact paths in viva_genesis/ source (a fold moved them? "
        "repoint the source path):\n  " + "\n  ".join(stale)
    )


def _load_studies():
    studies = {}
    for f in sorted((WS_ROOT / "workspace" / "studies").glob("*/study.yaml")):
        studies[f.parent.name] = yaml.safe_load(f.read_text()) or {}
    return studies


def test_dangling_edge_targets_fixture():
    """Unit: the pure check resolves slug + plan_id edges, flags danglers, honours
    the explicit allowlist, and skips self-edges."""
    from viva_genesis.audit_checks import check_dangling_edge_targets
    studies = {
        "og-a": {"plan_id": 2, "parent_studies": [{"study": "og-b"}],
                 "builds_on": [2, 9], "handoff": {"emits": [{"to": 3}], "receives": [{"from": 99}]}},
        "og-b": {"plan_id": 3, "parent_studies": ["og-a", "og-gone"],
                 "parent_relations": [{"study": "og-vanished", "relation": "tests"}]},
    }
    slugs, plans = {"og-a", "og-b"}, {2, 3}
    joined = " ".join(check_dangling_edge_targets(studies, slugs, plans))
    assert "og-gone" in joined          # dangling parent_studies slug flagged
    assert "og-vanished" in joined      # dangling parent_relations (typed-edge) slug flagged
    assert "plan_id 9" in joined        # dangling builds_on plan flagged
    assert "plan_id 99" in joined       # dangling handoff.receives.from flagged
    assert "plan_id 3" not in joined    # handoff.to 3 resolves (og-b's plan)
    assert check_dangling_edge_targets(
        studies, slugs, plans,
        allow={"slug:og-gone", "slug:og-vanished", "plan:9", "plan:99"}) == []


def test_workspace_has_no_dangling_edge_targets():
    """Every study-graph edge (builds_on / parent_studies / handoff) in the real
    workspace resolves to a current study (slug or plan_id) — guards a consolidation
    fold from leaving a stale pointer (cites resolved but edges did not)."""
    from viva_genesis.audit_checks import check_dangling_edge_targets
    studies = _load_studies()
    slugs = set(studies)
    plans = {s["plan_id"] for s in studies.values() if isinstance(s.get("plan_id"), int)}
    ALLOW: set = set()   # explicit documented exceptions; keep in sync with lint-workspace.py
    errs = check_dangling_edge_targets(studies, slugs, plans, ALLOW)
    assert not errs, "dangling study-graph edges:\n  " + "\n  ".join(errs)
