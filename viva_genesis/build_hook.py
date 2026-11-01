"""Workspace build hook for the discovery-cycle Build route (workbench #1540).

The engine never builds itself: when a capability_gap is Accepted and then Built in the Cycle
panel, ``discovery_engine.discover.load_workspace_build_hook`` imports this module and calls
``register_build_hook(registry)``; the engine then invokes ``registry['build_capability']`` as
``fn(gap, ws_root) -> {status, process, detail, gap_id}`` and verifies the named process
actually exists in the catalog and COVERS the mechanism before flipping the gap to ``built``
(see ``discovery_engine.capability_gaps.build_capability_gap``).

This hook is honest about what it can do:

  * **reuse** — if a composite already in the workspace covers the gap's mechanism (the M1–M7
    coupled bridge models are exactly this for the eukaryogenesis reopening), name it. The
    engine verifies coverage and closes the gap legitimately — no new code, no fake build.
  * **needs_implementation** — otherwise, scaffold a typed, runnable coupled-composite SKELETON
    (process module + ``@composite_generator`` with ``parameters=`` + a ``SQLiteEmitter`` whose
    ``paths`` carry the state, following the proven pipeline contract) and return
    needs_implementation with a pointer to it. The gap becomes ``needs_author`` — the dynamics
    are the science, authored by hand — never silently "built".
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"for", "the", "a", "an", "of", "and", "to", "in", "on", "with", "by", "is", "as",
         "model", "coupled", "bridge", "measures", "measure", "composite"}
_NAME_RE = re.compile(r"name\s*=\s*[\"']([^\"']+)[\"']")


def register_build_hook(registry: dict) -> None:
    registry["build_capability"] = build_capability


def _tokens(s: str) -> set[str]:
    return {t for t in _WORD.findall((s or "").lower()) if t not in _STOP}


def _slug(mechanism: str) -> str:
    toks = [t for t in _WORD.findall((mechanism or "mechanism").lower())]
    return "_".join(toks[:5]) or "mechanism"


def _find_covering_process(mechanism: str, ws_root: Path) -> str | None:
    """Return the dotted address of an existing composite that COVERS the mechanism
    (its name + module-docstring tokens superset the mechanism tokens), else None.
    Prefers the engine's own catalog + matcher when available; falls back to a file scan.
    The engine re-verifies coverage with process_present, so this only names a candidate."""
    want = _tokens(mechanism)
    if not want:
        return None
    # Preferred: the engine's catalog + coverage matcher (same bar the engine re-checks with).
    try:
        from discovery_engine import model_architect as _ma  # type: ignore
        from discovery_engine.capability_gaps import process_present  # type: ignore
        catalog = _ma.build_catalog({}, ws_root=str(ws_root))
        hit = process_present(catalog, mechanism)
        if hit:
            return hit if isinstance(hit, str) else (hit.get("address") or hit.get("process"))
    except Exception:  # noqa: BLE001 — fall back to a local scan
        pass
    # Fallback: scan composite files; match the mechanism tokens against each generator's
    # name + its module docstring (which describes the mechanism).
    comp_dir = ws_root / "viva_genesis" / "composites"
    if not comp_dir.is_dir():
        return None
    for f in sorted(comp_dir.glob("*.py")):
        if f.name == "__init__.py":
            continue
        try:
            text = f.read_text(encoding="utf-8")
            doc = ast.get_docstring(ast.parse(text)) or ""
        except Exception:  # noqa: BLE001
            continue
        m = _NAME_RE.search(text)
        if not m:
            continue
        gen = m.group(1)
        if want <= (_tokens(gen) | _tokens(doc)):
            return f"viva_genesis.composites.{f.stem}.{gen}"
    return None


_PROCESS_TMPL = '''"""Scaffold for mechanism: {mechanism}

Auto-scaffolded by viva_genesis.build_hook for an accepted capability_gap. The I/O and wiring
are runnable; the DYNAMICS in update() are a placeholder — author the real mechanism here.
"""
from __future__ import annotations

from process_bigraph import Process


class {cls}(Process):
    config_schema = {{"rate": {{"_type": "float", "_default": 0.1}}}}

    def inputs(self):
        return {{"level": "float"}}

    def outputs(self):
        return {{"level": "float"}}

    def update(self, state, interval):
        # TODO author the real dynamics for: {mechanism}
        level = float(state.get("level", 0.0) or 0.0)
        return {{"level": float(self.config["rate"]) * float(interval) * (1.0 - level)}}
'''

_COMPOSITE_TMPL = '''"""Scaffolded coupled composite for mechanism: {mechanism}

Auto-scaffolded by viva_genesis.build_hook. Runnable skeleton; author the dynamics in the
process and replace the placeholder observable with the gap's required discriminating observable.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..{proc_mod} import {cls}


@composite_generator(
    name="{slug}",
    emitters=[{{"address": "local:SQLiteEmitter", "paths": ["global_time", "level"]}}],
    parameters={{"rate": {{"type": "float", "default": 0.1, "description": "placeholder rate for {mechanism}"}}}},
    description="SCAFFOLD covering mechanism: {mechanism}. Author the dynamics + discriminating observable.",
)
def {slug}(core=None, *, rate=0.1, seed=1):
    if core is None:
        core = build_core()
    if "{cls}" not in core.link_registry:
        core.register_link("{cls}", {cls})
    return {{
        "proc": {{"_type": "process", "address": "local:{cls}", "interval": 1.0,
                 "config": {{"rate": float(rate)}},
                 "inputs": {{"level": ["level"]}}, "outputs": {{"level": ["level"]}}}},
        "level": 0.0,
    }}


def {slug}_observable(rows) -> float:
    """Placeholder — replace with the gap's required discriminating observable."""
    return float(rows[-1].get("level", float("nan"))) if rows else float("nan")
'''


def _scaffold(mechanism: str, ws_root: Path) -> str:
    slug = _slug(mechanism)
    cls = "".join(p.capitalize() for p in slug.split("_")) + "Process"
    proc_mod = f"{slug}_process"
    pkg = ws_root / "viva_genesis"
    (pkg / f"{proc_mod}.py").write_text(
        _PROCESS_TMPL.format(mechanism=mechanism, cls=cls), encoding="utf-8")
    (pkg / "composites" / f"{slug}.py").write_text(
        _COMPOSITE_TMPL.format(mechanism=mechanism, slug=slug, cls=cls, proc_mod=proc_mod),
        encoding="utf-8")
    return f"viva_genesis.composites.{slug}.{slug}"


def build_capability(gap: dict, ws_root: Any) -> dict:
    """Reuse a covering composite if one exists; else scaffold a skeleton (needs_author)."""
    ws_root = Path(ws_root)
    mechanism = str((gap or {}).get("mechanism", "")).strip()
    gap_id = (gap or {}).get("id")
    if not mechanism:
        return {"status": "failed", "detail": "gap has no mechanism", "gap_id": gap_id}
    existing = _find_covering_process(mechanism, ws_root)
    if existing:
        return {"status": "reuse", "process": existing, "gap_id": gap_id,
                "detail": f"existing composite {existing} covers {mechanism!r}"}
    addr = _scaffold(mechanism, ws_root)
    return {"status": "needs_implementation", "process": addr, "gap_id": gap_id,
            "detail": f"scaffolded runnable skeleton {addr} — author the dynamics + "
                      f"discriminating observable for {mechanism!r}, then re-run Build to reuse it"}
