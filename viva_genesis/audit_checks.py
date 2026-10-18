"""Pure workspace-audit checks (wired into ``scripts/lint-workspace.py``).

Each function is a pure ``inputs -> list[str]`` (human-readable violations, empty
== clean) so it is unit-testable without the dashboard or a live registry. The
lint script resolves the real inputs (registry parameters, the optional-dep set,
the test files) and hard-fails on any returned violation.

Checks here map to real failures hit in the origins-of-life-vent build:

- :func:`check_baseline_params` — a study ``baseline[].params`` key that is not a
  declared parameter of its composite generator (the og-12 orphaned-param break
  after a baseline repoint).
- :func:`check_unguarded_optional_imports` — a ``tests/`` module-level import of
  an optional dependency with no ``pytest.importorskip`` guard (the red-main
  ``test_martini_bilayer`` importing ``viva_openmm`` on a dep-less runner).
"""
from __future__ import annotations

import ast
from typing import Dict, Iterable, List, Set, Tuple


def check_baseline_params(
    studies: Dict[str, dict],
    gen_parameters: Dict[str, Set[str]],
) -> List[str]:
    """Every ``baseline[].params`` key must be a declared parameter of its composite.

    ``studies`` maps slug -> parsed ``study.yaml``; ``gen_parameters`` maps a full
    composite ref (``viva_genesis.composites.<mod>.<gen>``) -> the set of declared
    parameter names (from the ``@composite_generator`` ``parameters`` dict). A
    baseline whose composite ref is absent from ``gen_parameters`` (unresolved /
    planned) is skipped here — resolution is a separate check — so this never
    double-reports and never fails on a not-yet-built composite.
    """
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        for b in spec.get("baseline", []) or []:
            ref = b.get("composite")
            params = b.get("params") or {}
            if not ref or ref not in gen_parameters or not isinstance(params, dict):
                continue
            declared = gen_parameters[ref]
            for key in params:
                if key not in declared:
                    errors.append(
                        f"study {slug}: baseline '{b.get('name', ref)}' sets param "
                        f"'{key}' which is not a declared parameter of {ref} "
                        f"(declared: {sorted(declared)})"
                    )
    return errors


def check_unguarded_optional_imports(
    test_files: Iterable[Tuple[str, str]],
    optional_deps: Set[str],
) -> List[str]:
    """Flag a ``tests/`` MODULE-LEVEL import of an optional dependency.

    ``test_files`` is an iterable of ``(name, source)``. A top-level ``import X`` /
    ``from X import ...`` whose root package is in ``optional_deps`` executes at
    collection time and crashes the whole run on a runner without the extra — it
    must be guarded with ``pytest.importorskip("X")`` instead. Imports nested
    inside a function / fixture (not module-level) run lazily and are fine, so
    only ``tree.body`` is inspected.
    """
    errors: List[str] = []
    for name, source in test_files:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:  # module level only
            roots: List[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots = [node.module.split(".")[0]]
            for root in roots:
                if root in optional_deps:
                    errors.append(
                        f"test {name}: module-level `import {root}` of optional dep "
                        f"'{root}' is not guarded — use "
                        f"`{root.replace('-', '_')} = pytest.importorskip(\"{root}\")` "
                        f"so collection doesn't fail where the extra isn't installed"
                    )
    return errors
