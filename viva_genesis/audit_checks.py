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
import re
from typing import Callable, Dict, Iterable, List, Set, Tuple

_PASSED_TOKENS = {"passed", "complete", "completed", "ran", "evaluated", "done"}


def _primary_tests(spec: dict) -> List[dict]:
    return [t for t in (spec.get("behavior_tests") or [])
            if isinstance(t, dict) and t.get("classification") == "primary"]


def _study_claims_pass(spec: dict) -> bool:
    """A study asserting a positive result: gate passed / a supported verdict /
    confidence Accepted."""
    if str(spec.get("gate_status") or "").strip().lower() == "passed":
        return True
    if str(spec.get("confidence") or "").strip() == "Accepted":
        return True
    for v in (spec.get("conclusion_verdicts") or {}).values():
        token = v.get("result") if isinstance(v, dict) else v
        if str(token or "").strip().lower() in ("supported", "pass"):
            return True
    return False


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


# --------------------------------------------------------------------------- #
# Batch 2 — evidence-integrity checks.
# --------------------------------------------------------------------------- #
def check_dangling_refs(
    studies: Dict[str, dict],
    all_slugs: Set[str],
    bib_keys: Set[str],
) -> List[str]:
    """A — every cross-reference a study makes must resolve.

    - ``findings[].evidence.from_test`` -> a ``behavior_tests[].name``
    - ``findings[].provenance.run_ids[]`` -> a ``runs[].name``
    - every ``cites``/``expected.cites`` key -> a bibliography key (papers.bib)
    - ``pipeline_gate.prerequisites[].study`` -> a real study slug
    """
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        test_names = {t.get("name") for t in (spec.get("behavior_tests") or []) if isinstance(t, dict)}
        run_names = {r.get("name") for r in (spec.get("runs") or []) if isinstance(r, dict)}
        for bt in spec.get("behavior_tests") or []:
            for c in (bt.get("cites") or []):
                if bib_keys and c not in bib_keys:
                    errors.append(f"study {slug}: behavior_test '{bt.get('name')}' cites unknown bib key '{c}'")
        for fn in spec.get("findings") or []:
            ev = fn.get("evidence") or {}
            ft = ev.get("from_test")
            fts = ev.get("from_tests") or ([ft] if ft else [])
            for t in fts:
                if t and t not in test_names:
                    errors.append(f"study {slug}: finding '{fn.get('id')}' evidence.from_test '{t}' is not a behavior_tests[].name")
            for rid in (fn.get("provenance") or {}).get("run_ids", []) or []:
                if rid not in run_names:
                    errors.append(f"study {slug}: finding '{fn.get('id')}' provenance run_id '{rid}' is not a runs[].name")
            for c in (fn.get("expected") or {}).get("cites", []) or []:
                if bib_keys and c not in bib_keys:
                    errors.append(f"study {slug}: finding '{fn.get('id')}' cites unknown bib key '{c}'")
        for pr in (spec.get("pipeline_gate") or {}).get("prerequisites", []) or []:
            dep = pr.get("study") if isinstance(pr, dict) else pr
            if dep and dep not in all_slugs:
                errors.append(f"study {slug}: pipeline_gate prerequisite '{dep}' is not a real study")
    return errors


def check_artifacts_exist(
    studies: Dict[str, dict],
    resolve: Callable[[str, str], str],
) -> List[str]:
    """B — a ran/passed study's committed artifacts must exist on disk.

    ``resolve(slug, relpath) -> "ok" | "missing" | "ignored"``: the lint maps the
    path under the study dir and reports whether it exists, is absent, or is
    git-ignored (gitignored run DBs are expected absent in a fresh checkout, so
    they are skipped — only committed artifacts are required). Applies when
    ``simulation_status == ran`` or ``gate_status == passed``.
    """
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        ran = str(spec.get("simulation_status") or "").strip().lower() == "ran"
        passed = str(spec.get("gate_status") or "").strip().lower() == "passed"
        if not (ran or passed):
            continue
        paths: List[Tuple[str, str]] = []
        for bt in spec.get("behavior_tests") or []:
            if bt.get("artifact"):
                paths.append(("behavior_test '%s' artifact" % bt.get("name"), bt["artifact"]))
        for r in spec.get("runs") or []:
            if isinstance(r, dict) and r.get("store_path"):
                paths.append(("run '%s' store_path" % r.get("name"), r["store_path"]))
        for label, rel in paths:
            status = resolve(slug, rel)
            if status == "missing":
                errors.append(f"study {slug}: {label} path missing on disk: {rel} "
                              f"(ran/passed study — reproducibility gap)")
    return errors


def check_planned_not_passed(studies: Dict[str, dict]) -> List[str]:
    """C — a study whose CANONICAL baseline is ``planned: true`` must not claim a
    pass (gate_status passed / supported verdict / confidence Accepted). A planned
    (not-yet-built / rebuild-pending) baseline is not a result."""
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        baselines = spec.get("baseline") or []
        canon = [b for b in baselines if isinstance(b, dict) and b.get("canonical")]
        canon = canon or [b for b in baselines if isinstance(b, dict)][:1]  # fall back to first
        if any(b.get("planned") for b in canon) and _study_claims_pass(spec):
            errors.append(
                f"study {slug}: canonical baseline is planned:true but the study claims a pass "
                f"(gate_status={spec.get('gate_status')!r}, confidence={spec.get('confidence')!r}) "
                f"— a planned baseline cannot be a passed result")
    return errors


def check_verdict_evidence(studies: Dict[str, dict]) -> List[str]:
    """D — a supported verdict / passed gate requires the matching primary
    behavior_test's run outcome to be PASS (runs[].outcomes is a DICT with an
    UPPERCASE ``result``). Not FAIL, not missing."""
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        if not _study_claims_pass(spec):
            continue
        primaries = _primary_tests(spec)
        if not primaries:
            continue
        # Gather every outcome seen across runs: {test_name: set(results)}.
        seen: Dict[str, Set[str]] = {}
        for r in spec.get("runs") or []:
            for tname, oc in (r.get("outcomes") or {}).items():
                res = oc.get("result") if isinstance(oc, dict) else oc
                seen.setdefault(tname, set()).add(str(res).strip().upper())
        for t in primaries:
            name = t.get("name")
            results = seen.get(name)
            if not results:
                errors.append(f"study {slug}: claims a pass but primary test '{name}' has no run outcome")
            elif "PASS" not in results:
                errors.append(f"study {slug}: claims a pass but primary test '{name}' outcome is {sorted(results)} (not PASS)")
    return errors


def check_knife_edge_margins(studies: Dict[str, dict], eps: float = 1e-9) -> List[str]:
    """E (WARN) — a hard acceptance-criterion test that passes by a hair
    (|measured - threshold| <= eps) is fragile; suggest a sweep."""
    warnings: List[str] = []
    for slug, spec in sorted(studies.items()):
        for r in spec.get("runs") or []:
            for tname, oc in (r.get("outcomes") or {}).items():
                if not isinstance(oc, dict):
                    continue
                axis = oc.get("axis") or {}
                margin = axis.get("margin")
                expected = axis.get("expected") or {}
                op = str(expected.get("op") or "").strip()
                # Knife-edge only applies to a CONTINUOUS band. Skip invariant /
                # boolean gates: op "==" / none, or a threshold that is a boolean
                # or a 0/1 invariant (e.g. "logged >= 1.0", "residual <= 0.0") —
                # those have margin 0 by design, not a fragile pass.
                if op in ("", "==", "!="):
                    continue
                if isinstance(expected.get("value"), bool) or expected.get("value") in (0, 1, 0.0, 1.0):
                    continue
                if (axis.get("severity") == "hard"
                        and str(oc.get("result") or "").strip().upper() == "PASS"
                        and isinstance(margin, (int, float)) and abs(margin) <= eps):
                    warnings.append(f"study {slug}: hard gate '{tname}' passes knife-edge "
                                    f"(margin≈{margin}); run a seed/param sweep")
    return warnings


def check_units_present(studies: Dict[str, dict]) -> List[str]:
    """F (WARN) — a contract input/output field with no ``_units`` (explicit
    ``dimensionless`` is fine; a bare field is ambiguous)."""
    warnings: List[str] = []
    for slug, spec in sorted(studies.items()):
        face = ((spec.get("contract") or {}).get("face") or {})
        for side in ("inputs", "outputs"):
            for fname, fdef in (face.get(side) or {}).items():
                if isinstance(fdef, dict) and "_units" not in fdef:
                    warnings.append(f"study {slug}: contract.face.{side}.{fname} has no _units")
    return warnings


def check_gate_matched_null(gate_rows: Iterable[dict], authored_gates: Iterable[dict]) -> List[str]:
    """G — a gate authored ``status: passed`` must be DERIVED passed too (its
    matched-null/ablation criterion confirmed on a member study). ``gate_rows`` is
    the output of ``build_plan_progress``; ``authored_gates`` is the raw plan_gates.
    """
    errors: List[str] = []
    # build_plan_progress emits "met" for a fully-satisfied gate; "passed" is the
    # legacy synonym. Either derived value supports an authored passed/met.
    _ok = ("passed", "met")
    derived = {r.get("id"): r.get("status") for r in gate_rows}
    for g in authored_gates:
        if str(g.get("status") or "").strip().lower() in _ok:
            if derived.get(g.get("id")) not in _ok:
                errors.append(f"plan gate {g.get('id')}: authored status 'passed' but the "
                              f"matched-null/criterion evidence does not support it "
                              f"(derived: {derived.get(g.get('id'))})")
    return errors


def check_used_imports_declared(
    used_packages: Dict[str, str],
    declared_packages: Set[str],
) -> List[str]:
    """Every external simulator-wrapper package the workspace actually uses must
    be declared in ``workspace.yaml`` ``imports:`` — otherwise the dashboard
    Repositories tab silently omits the repo and affected-study attribution is
    wrong. (The viva-openmm gap: used by ``viva_genesis/core.py`` and og-31's
    ``local:OpenMMMartiniProcess``, but never declared.)

    Pure set comparison so it is unit-testable; the lint script resolves the
    inputs by source-scanning the package (``import viva_X`` + ``local:<Process>``
    addresses) and reading the ``imports[].package`` values.

    ``used_packages`` maps a used import-name (e.g. ``viva_openmm``) to a short
    human note of where it was detected. ``declared_packages`` is the set of
    declared ``imports[].package`` values. Framework/toolchain packages (e.g.
    ``viva_superpowers``) and the workspace's own package are excluded upstream,
    so everything here is a reference-imported wrapper that belongs in imports.
    """
    errors: List[str] = []
    for pkg in sorted(used_packages):
        if pkg not in declared_packages:
            where = used_packages.get(pkg) or ""
            errors.append(
                f"package '{pkg}' is used ({where}) but is not declared in "
                f"workspace.yaml imports: — the dashboard Repositories tab will "
                f"silently omit it and mis-attribute affected studies")
    return errors


def check_gate_members_in_roster(
    inv_name: str,
    plan_gates: Iterable[dict],
    roster: Set[str],
) -> List[str]:
    """Every ``plan_gates[].member_studies`` slug must be in the investigation's
    top-level ``studies:`` roster — otherwise the gate references a study the
    investigation graph/DAG never iterates (it builds from the roster), so the
    study is silently missing from the graph. (Caught by the plan-board build:
    og-27..31 were gate members but absent from the roster.)"""
    errors: List[str] = []
    for g in plan_gates or []:
        for slug in g.get("member_studies") or []:
            if slug not in roster:
                errors.append(
                    f"investigation {inv_name}: plan_gates gate {g.get('id')} member "
                    f"'{slug}' is not in the studies: roster — it won't appear in the graph/DAG")
    return errors


def check_dangling_edge_targets(
    studies: Dict[str, dict],
    all_slugs: Set[str],
    all_plan_ids: Set[int],
    allow: Set[str] = frozenset(),
) -> List[str]:
    """Every graph-EDGE target must resolve to a CURRENT study.

    The audit previously resolved citations + finding/run cross-refs but NOT the
    study-graph edges, so a consolidation fold that removed a study left stale
    ``builds_on`` / ``parent_studies`` / ``handoff`` pointers (e.g. og-02, og-28,
    og-30 after they folded into their consolidated studies) sailing through
    "0 dangling". This closes that class, fail-loud like ``check_dangling_refs``.

    Resolution rule: a SLUG edge (``parent_studies[].study`` and the typed
    ``parent_relations[].study``) must be a current study slug; a NUMERIC edge
    (``builds_on[]`` and ``handoff`` ``emits[].to`` /
    ``receives[].from``) must be a ``plan_id`` claimed by a current study (studies
    adopt their canonical arm's ``plan_id``). A self-edge is skipped.
    ``pipeline_gate.prerequisites`` is intentionally NOT re-checked here — it is
    already covered by :func:`check_dangling_refs` (avoid double-reporting).

    ``allow`` is an EXPLICIT, documented exception set of ``"slug:<slug>"`` /
    ``"plan:<n>"`` tokens — a last resort for a legitimate planned-but-unscaffolded
    concept, never a silent skip.
    """
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        own_plan = spec.get("plan_id")
        # SLUG edges: parent_studies[].study + parent_relations[].study (the latter a
        # TYPED edge {study, relation} the baker reads to type the graph).
        for field in ("parent_studies", "parent_relations"):
            for e in spec.get(field) or []:
                t = e.get("study") if isinstance(e, dict) else e
                if t and t != slug and t not in all_slugs and f"slug:{t}" not in allow:
                    errors.append(f"study {slug}: {field} target '{t}' is not a current study slug "
                                  f"(folded? repoint to the consolidated study)")
        numeric = [("builds_on", n) for n in (spec.get("builds_on") or [])]
        hp = spec.get("handoff") or {}
        numeric += [("handoff.emits.to", (e.get("to") if isinstance(e, dict) else e))
                    for e in (hp.get("emits") or [])]
        numeric += [("handoff.receives.from", (e.get("from") if isinstance(e, dict) else e))
                    for e in (hp.get("receives") or [])]
        for kind, n in numeric:
            if isinstance(n, bool) or not isinstance(n, int):
                continue
            if n != own_plan and n not in all_plan_ids and f"plan:{n}" not in allow:
                errors.append(f"study {slug}: {kind} target plan_id {n} is not claimed by any current "
                              f"study (folded/never-scaffolded? repoint, remove, scaffold, or allowlist)")
    return errors


# --------------------------------------------------------------------------- #
# Batch 3 — §6 audit-contract hardening (calibration-vs-prediction tagging).
# --------------------------------------------------------------------------- #
# A verdict-feeding fitted number (a yield / rate law / parameter) carries an
# `evidence_basis` tag saying whether it was fit to the reference data
# (``calibrated``), validated against held-out / independent data (``predicted``),
# or applied outside the fitted regime (``extrapolated``). Field shape locked with
# genesis-writer: a BARE STRING enum on a ``findings[]`` entry (primary home) or a
# ``behavior_tests[]`` entry; optional free-text sibling ``evidence_basis_note``
# (ignored here). This is a DIFFERENT axis from ``band_basis`` (the provenance of
# an acceptance *threshold*) — the two coexist; neither reads the other.
EVIDENCE_BASIS_VALUES = frozenset({"calibrated", "predicted", "extrapolated"})


def check_evidence_basis_enum(studies: Dict[str, dict]) -> List[str]:
    """§6.2 (hard-fail) — any ``evidence_basis`` *value present* on a finding or
    behavior_test must be one of :data:`EVIDENCE_BASIS_VALUES`.

    An out-of-enum value (a typo, an invented tag) is an authoring error, never a
    valid incremental-rollout state, so it fails loud — distinct from the coverage
    WARN below, which tolerates *absence* while tagging lands study by study.
    """
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        for coll in ("findings", "behavior_tests"):
            for e in spec.get(coll) or []:
                if not isinstance(e, dict) or "evidence_basis" not in e:
                    continue
                v = e.get("evidence_basis")
                if v not in EVIDENCE_BASIS_VALUES:
                    ident = e.get("id") or e.get("name") or "?"
                    errors.append(
                        f"study {slug}: {coll} '{ident}' evidence_basis={v!r} is not one of "
                        f"{sorted(EVIDENCE_BASIS_VALUES)} (calibrated|predicted|extrapolated)")
    return errors


def check_evidence_basis_coverage(studies: Dict[str, dict]) -> List[str]:
    """§6.2 (WARN) — a study with a decided verdict carries ZERO ``evidence_basis``
    tags, so its verdict-feeding fitted numbers are untagged.

    Study-level coverage, not per-finding: there is no reliable per-entry marker
    for "this number is a fitted quantity feeding the verdict", and inferring it
    from prose false-fires — so the check warns once per study only when the study
    has a decided verdict (truthy top-level ``verdict`` and ``status`` not
    ``planned`` — the planned scaffolds have no numbers to tag yet) AND not a
    single finding or behavior_test carries ``evidence_basis``. That stays
    false-alarm-free and lets the tagging land incrementally.
    """
    warnings: List[str] = []
    for slug, spec in sorted(studies.items()):
        verdict = str(spec.get("verdict") or "").strip()
        status = str(spec.get("status") or "").strip().lower()
        if not verdict or status == "planned":
            continue
        tagged = any(
            isinstance(e, dict) and e.get("evidence_basis")
            for coll in ("findings", "behavior_tests")
            for e in (spec.get(coll) or [])
        )
        if not tagged:
            warnings.append(
                f"study {slug}: verdict {verdict!r} is decided but no finding/behavior_test carries an "
                f"`evidence_basis` tag (calibrated|predicted|extrapolated) — verdict-feeding fitted "
                f"numbers are untagged (fit-vs-held-out invisible)")
    return warnings


# --------------------------------------------------------------------------- #
# Batch 3 — §6.6 avoid vacuous gates (inferred-tier coverage honesty).
# --------------------------------------------------------------------------- #
# "Zero inferred reactions cannot count as substantive inferred-tier coverage;
# balance-by-construction tests are bookkeeping witnesses, not chemistry
# validation." The vacuous-gate signature (og-network-persistence / the reaction
# atlas): a gate PASSES with a ZERO count — `inferred-tier-has-thermo-and-rate-
# basis` is "vacuously satisfied" because there are 0 inferred reactions, and the
# `atlas-write-gate-zero-leakage` gate passes because unbalanced records are held
# out *by construction*. Neither is substantive coverage.
#
# The honest escape valve — which current main already uses — is to keep the
# derived finding ``status: planned`` (a bookkeeping gate's finding ``kind:
# methodological``) while the tier is empty. This check is therefore a FORWARD
# GUARD: it is inert while the study is honest, and fails loud the moment a
# *delivered* finding credits a zero-count gate as real coverage. A gate earns
# inferred-tier coverage only from real inferred reactions.
_INFERRED_TIER_RE = re.compile(r"inferred[-_ ]?tier", re.I)
# Atlas write-gate / provenance-leakage bookkeeping language — deliberately NOT
# the bare word "balance" (which would catch legitimate energy/mass-balance
# physics residuals that close to a real 0); only the "atlas write gate that
# admits/rejects records" vocabulary that marks a construction witness.
_BOOKKEEPING_GATE_RE = re.compile(
    r"zero[-_ ]?leakage|unsourced|write[-_ ]?gate|records? admitted", re.I)
# Finding statuses that mean "not yet delivered" — honestly pending, so a
# zero-count backing gate is fine (nothing is being credited yet).
_NOT_DELIVERED_STATUSES = frozenset({"planned", "proposed", "pending", "deferred", ""})


def _zero_count_pass_tests(spec: dict) -> Set[str]:
    """Behavior_test names that PASSED with a numeric ``measured_value`` of 0 in
    some run (a vacuous / by-construction zero-count pass). Booleans excluded."""
    out: Set[str] = set()
    for r in spec.get("runs") or []:
        for tname, oc in (r.get("outcomes") or {}).items():
            if not isinstance(oc, dict):
                continue
            mv = oc.get("measured_value")
            if (str(oc.get("result") or "").strip().upper() == "PASS"
                    and isinstance(mv, (int, float)) and not isinstance(mv, bool) and mv == 0):
                out.add(tname)
    return out


def check_vacuous_inferred_coverage(
    studies: Dict[str, dict],
    coverage_reports: Dict[str, dict] | None = None,
) -> List[str]:
    """§6.6 (hard-fail) — a DELIVERED finding must not credit a vacuous gate as
    substantive coverage. Two vacuous-credit shapes:

    (a) inferred-tier coverage from zero inferred reactions — a delivered finding
        backed by an *inferred-tier* gate that PASSED with ``measured_value == 0``.
        A coverage *count* of 0 is unambiguously vacuous (unlike a residual that
        closes to a real 0), so this is keyed study-locally.
    (b) a balance-by-construction write-gate counted as chemistry validation — a
        delivered ``kind: computational`` (quantitative chemistry) finding backed
        by an atlas write-gate whose clean pass is achieved *by holding records
        out at write time*. The authoritative "by construction" signal is the
        gate's own coverage report: ``balance_violations_held > 0`` (violations
        exist but were excluded). ``coverage_reports`` maps a behavior_test
        ``artifact`` path -> the report's ``headline`` dict. Without that
        held-out signal (b) never fires — so a ledger/residual that genuinely
        closes to 0 (no held-out violations, no such report) is NOT flagged.

    Keyed on ``study.yaml`` (+ the optional coverage reports the lint resolves),
    unit-testable like the other checks. The honest fixes: keep the finding
    ``status: planned`` until the tier has real reactions, or (for (b)) frame the
    write-gate's finding as ``kind: methodological`` rather than a chemistry result.
    """
    coverage_reports = coverage_reports or {}
    errors: List[str] = []
    for slug, spec in sorted(studies.items()):
        tests = {t.get("name"): t for t in (spec.get("behavior_tests") or [])
                 if isinstance(t, dict) and t.get("name")}
        zero_pass = _zero_count_pass_tests(spec)
        if not zero_pass:
            continue
        for fn in spec.get("findings") or []:
            if not isinstance(fn, dict):
                continue
            if str(fn.get("status") or "").strip().lower() in _NOT_DELIVERED_STATUSES:
                continue  # honestly not-yet-delivered — nothing credited
            ev = fn.get("evidence") or {}
            ft = ev.get("from_test")
            fts = ev.get("from_tests") or ([ft] if ft else [])
            kind = str(fn.get("kind") or "").strip().lower()
            for tname in fts:
                if tname not in zero_pass:
                    continue
                t = tests.get(tname) or {}
                hay = " ".join(str(x) for x in (
                    tname, t.get("description"), (t.get("measure") or {}).get("detail"),
                    (t.get("pass_if") or {}).get("detail")) if x)
                if _INFERRED_TIER_RE.search(hay):
                    errors.append(
                        f"study {slug}: delivered finding '{fn.get('id')}' (status "
                        f"{fn.get('status')!r}) credits inferred-tier coverage to gate '{tname}', "
                        f"which PASSED with 0 (zero inferred reactions) — inferred-tier coverage must "
                        f"come from real inferred reactions, not a vacuous zero-count pass (keep the "
                        f"finding status: planned until the inferred tier is populated)")
                elif kind == "computational" and _BOOKKEEPING_GATE_RE.search(hay):
                    head = coverage_reports.get(t.get("artifact")) or {}
                    held = head.get("balance_violations_held")
                    if isinstance(held, (int, float)) and not isinstance(held, bool) and held > 0:
                        errors.append(
                            f"study {slug}: delivered computational finding '{fn.get('id')}' rests on "
                            f"balance-by-construction gate '{tname}' — its clean pass holds "
                            f"{held:g} balance violation(s) out of the accepted set at write time, so it "
                            f"is a bookkeeping witness, not chemistry validation (frame this finding as "
                            f"kind: methodological, or back the chemistry claim with a substantive "
                            f"measurement)")
    return errors
