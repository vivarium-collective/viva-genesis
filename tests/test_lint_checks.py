"""Tests for the workspace-local lint-check hook (viva_genesis.lint_checks).

The hook is the reference ``<pkg>.lint_checks`` consumed by
``discovery_engine.workspace_lint``; these cover the vg_data arm-resource check
wired through ``ws_root`` plus the empty-registry skip.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

from viva_genesis.lint_checks import CHECKS, check_arm_resources


def _make_ws(tmp_path: Path, *, arm_resource: str, resource_ids: list[str]) -> Path:
    ws = tmp_path / "ws"
    (ws / "workspace" / "studies" / "s01").mkdir(parents=True)
    (ws / "workspace.yaml").write_text("package_path: viva_genesis\n")
    (ws / "workspace" / "studies" / "s01" / "study.yaml").write_text(
        yaml.safe_dump({"name": "s01", "arms": [{"id": "a1", "resource": arm_resource}]})
    )
    vg = ws / "viva_genesis" / "data" / "vg_data"
    vg.mkdir(parents=True)
    (vg / "structured_resources.yaml").write_text(
        yaml.safe_dump({"resources": [{"id": rid} for rid in resource_ids]})
    )
    return ws


def test_checks_is_list_of_callables():
    assert isinstance(CHECKS, list) and CHECKS
    assert all(callable(c) for c in CHECKS)


def test_dangling_arm_resource_is_flagged(tmp_path):
    ws = _make_ws(tmp_path, arm_resource="ghost-resource", resource_ids=["prebiotic-reaction-atlas"])
    out = list(check_arm_resources(ws))
    assert len(out) == 1
    assert "ghost-resource" in out[0]
    assert out[0].startswith("arm-resource-ref:")


def test_resolved_arm_resource_is_clean(tmp_path):
    ws = _make_ws(tmp_path, arm_resource="prebiotic-reaction-atlas",
                  resource_ids=["prebiotic-reaction-atlas"])
    assert list(check_arm_resources(ws)) == []


def test_empty_registry_skips_rather_than_false_fails(tmp_path):
    # registry present but empty -> skip (don't flag every ref)
    ws = _make_ws(tmp_path, arm_resource="anything", resource_ids=[])
    assert list(check_arm_resources(ws)) == []


def test_missing_registry_file_skips(tmp_path):
    ws = tmp_path / "ws"
    (ws / "workspace" / "studies").mkdir(parents=True)
    (ws / "workspace.yaml").write_text("package_path: viva_genesis\n")
    assert list(check_arm_resources(ws)) == []
