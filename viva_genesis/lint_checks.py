"""viva-genesis workspace-local lint checks — the ``<pkg>.lint_checks`` hook.

Reference implementation of the workspace-local check hook consumed by
``discovery_engine.workspace_lint`` (the composed workspace-lint entrypoint). The
shared engine checks (the report linter) live upstream and run for every workspace;
this module holds only the checks that are **specific to viva-genesis's own data
model** and therefore do not belong in the shared linter.

``CHECKS`` is a list of callables ``fn(ws_root: Path) -> Iterable[LintFinding | str]``
(a plain string is coerced to a workspace-level warning by the composer). Each entry
here wraps an existing pure check in :mod:`viva_genesis.audit_checks` — resolving its
inputs from ``ws_root`` — so there is no logic duplication.

Scope note: the *generic* audit checks (verdict-evidence, baseline-params, units, …)
are being lifted into ``discovery_engine.report_linter`` (one check, every workspace)
and are deliberately NOT listed here. Only genuinely viva-genesis-specific checks
(e.g. vg_data resource references) stay local. See the workspace-lint consolidation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .audit_checks import check_arm_resource_refs

_VG_DATA_RESOURCES = Path("viva_genesis") / "data" / "vg_data" / "structured_resources.yaml"


def _load_studies(ws_root: Path) -> dict[str, dict]:
    """``{study_dir_name: study_spec}`` — keyed the same way the workspace lint keys it.

    Resolves the studies directory through the shared workspace-paths helper (honoring
    ``workspace.yaml`` ``layout:``), falling back to the conventional nested/flat paths.
    """
    studies_dir: Path | None = None
    try:
        from viva_superpowers.paths import workspace_dir  # type: ignore
        resolved = Path(workspace_dir("studies", root=Path(ws_root)))
        if resolved.is_dir():
            studies_dir = resolved
    except Exception:
        studies_dir = None
    if studies_dir is None:  # resolver unavailable or pointed at a non-existent dir
        for cand in (Path(ws_root) / "workspace" / "studies", Path(ws_root) / "studies"):
            if cand.is_dir():
                studies_dir = cand
                break
    if studies_dir is None:
        return {}
    out: dict[str, dict] = {}
    for p in sorted(studies_dir.glob("*/study.yaml")):
        try:
            out[p.parent.name] = yaml.safe_load(p.read_text()) or {}
        except Exception:
            continue
    return out


def _load_resource_ids(ws_root: Path) -> set[str]:
    """Registered vg_data Resource ids (``resources[].id``). Empty set if the registry
    is absent/unreadable — callers skip rather than false-fail on an empty registry."""
    path = Path(ws_root) / _VG_DATA_RESOURCES
    if not path.is_file():
        return set()
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return set()
    return {r.get("id") for r in (data.get("resources") or [])
            if isinstance(r, dict) and r.get("id")}


def check_arm_resources(ws_root: Path) -> Iterable[str]:
    """Workspace-local: every study-arm ``resource:`` ref resolves to a registered
    vg_data Resource id. Skips when the resource registry is empty/unreadable."""
    resource_ids = _load_resource_ids(ws_root)
    if not resource_ids:
        return []
    studies = _load_studies(ws_root)
    return [f"arm-resource-ref: {e}" for e in check_arm_resource_refs(studies, resource_ids)]


#: Workspace-local checks discovered by ``discovery_engine.workspace_lint``.
CHECKS = [check_arm_resources]
