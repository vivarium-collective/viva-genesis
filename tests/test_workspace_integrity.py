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
