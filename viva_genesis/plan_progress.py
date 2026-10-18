"""Cumulative integration-gate board for the origins-of-life-vent plan.

Pure ``(investigation, studies) -> rows`` derivation: it reads the investigation's
``plan_gates`` block (gate definitions + member_studies + criterion, authored by
hand) and computes each gate's **status** from its member studies' own evaluated
verdicts, honoring the ``extends`` spine. The dashboard renders the board from this
structure; nothing here writes.

Two pieces:

- :func:`study_stage` — the per-study six-axis "you are here" ladder, mirroring
  vivarium-workbench ``study_page.py`` §13 exactly so the board agrees with the
  per-study page: ``Plan←design_status``, ``Execution←simulation_status``,
  ``Evidence←evaluation_status``, ``Quality←evaluation_status`` (same axis),
  ``Decision←gate_status``, ``Release←expert_review_status``. Each axis token is
  classified into the gate-state vocabulary; the current stage is the first one
  not yet passed/waived.

- :func:`build_plan_progress` — rolls member studies' own verdicts up into each
  plan gate. The central rule: **an evaluated gate shows its OWN verdict**, never
  "blocked" just because an upstream gate is only qualified or a sibling branch
  was refuted. Board status vocabulary (what the render consumes):

  * ``met``         — the gate's members ran + evaluated, its matched-null /
    ablation criterion is confirmed, every own member passed cleanly, and it has
    no unscaffolded (pending) members. (``passed`` is accepted as a synonym on
    input; ``met`` is what this emits.)
  * ``qualified``   — the criterion holds but with caveats: a member's own verdict
    is qualified (e.g. og-27 two-regime, og-31 partial Gate C), and/or the gate
    still has pending/unscaffolded members. A genuine positive, with conditions.
  * ``refuted``     — the gate's criterion is refuted (a ``criterion_findings``
    entry is contradicted) and/or every evaluated member's own verdict is refuted.
    An ``off_spine: true`` branch (A2) can be refuted without ever gating the
    spine, because nothing downstream ``extends`` it.
  * ``in_progress`` — scaffolded members exist and the prior **spine** gate is met
    or qualified (or there is none), but the gate's members aren't all evaluated
    yet, so no verdict can be derived.
  * ``blocked``     — scaffolded members exist but aren't evaluated AND the prior
    spine gate is not yet met/qualified — the gate genuinely can't start.
  * ``pending``     — the gate has no scaffolded member studies yet (its members
    are still plan numbers, e.g. 32-37).

  Spine advancement keys off the prior spine gate being **met OR qualified** (its
  spine-critical criterion holds), not a clean ``met`` — a qualified spine gate
  still carries what the next gate builds on. Off-spine branches never gate
  downstream (nothing ``extends`` them).
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Axis-token -> gate-state vocabulary. Mirrors vivarium-workbench
# study_page.py's _GATE_STATE_TOKENS (§13.2) so the board and the per-study
# ladder classify a status the same way.
_STATE_TOKENS = {
    # passed — assessed and clean
    "complete": "passed", "completed": "passed", "ran": "passed",
    "evaluated": "passed", "done": "passed", "designed": "passed",
    "approved": "passed", "implemented": "passed", "signed_off": "passed",
    "passed": "passed",
    # passed-with-conditions — assessed, partial credit
    "needs_calibration": "passed-with-conditions", "partial": "passed-with-conditions",
    "mixed": "passed-with-conditions", "drift": "passed-with-conditions",
    # blocked — assessed and failing
    "blocked": "blocked", "failed": "blocked", "fail": "blocked",
    "mismatch": "blocked", "stale": "blocked", "failed_evaluation": "blocked",
    # waived — explicitly accepted residual risk
    "waived": "waived",
    # not-assessed — nothing decided yet (incl. in progress / pending / planned)
    "not_started": "not-assessed", "not_run": "not-assessed",
    "not_evaluated": "not-assessed", "planning": "not-assessed",
    "planned": "not-assessed", "pending": "not-assessed",
    "in_progress": "not-assessed", "running": "not-assessed",
}

# (key, label, source axis). Quality intentionally shares evaluation_status with
# Evidence — that is study_page.py §13's table, not a bug.
_LADDER = (
    ("plan", "Plan", "design_status"),
    ("execution", "Execution", "simulation_status"),
    ("evidence", "Evidence", "evaluation_status"),
    ("quality", "Quality", "evaluation_status"),
    ("decision", "Decision", "gate_status"),
    ("release", "Release", "expert_review_status"),
)

_DONE_STATES = ("passed", "waived")

# A gate status that lets the spine advance to what builds on it: a met gate, or a
# qualified gate (its spine-critical criterion holds, with caveats). "passed" is
# accepted as a synonym of "met".
_ADVANCES = ("met", "qualified", "passed")

# --- member own-verdict vocabulary ----------------------------------------- #
# A study's Decision verdict, read from its gate_status + report verdict. These are
# the authored enums: gate_status ∈ {not_started, blocked, needs_calibration,
# passed, failed, stale}; verdict ∈ {supported, qualified, inconclusive, refuted}
# (+ the workspace's authored "honest-negative", treated as refuted).
_GATE_REFUTED = ("failed", "fail")
_GATE_QUALIFIED = ("needs_calibration", "partial", "mixed")
_GATE_MET = ("passed", "waived")
_VERDICT_REFUTED = ("refuted", "refutes", "honest-negative", "honest_negative")
_VERDICT_QUALIFIED = ("qualified",)
_VERDICT_MET = ("supported", "confirms", "confirmed")

# finding-status -> criterion signal
_FINDING_CONFIRMED = ("confirms", "confirmed", "passed")
_FINDING_REFUTED = ("contradicts", "contradicted", "refuted", "refutes", "failed")


def _norm(token) -> str:
    return str(token or "").strip().lower()


def _axis_state(token) -> str:
    if not token:
        return "not-assessed"
    return _STATE_TOKENS.get(_norm(token), "not-assessed")


def study_stage(spec: dict) -> dict:
    """The per-study lifecycle ladder + the current ("you are here") stage.

    Returns ``{"stage": <label>, "state": <gate-state>, "ladder": [{gate, label,
    status}, ...]}``. The current stage is the first ladder rung not yet
    passed/waived; when every rung is passed/waived the study is at ``Release``.
    """
    ladder = [
        {"gate": key, "label": label, "status": _axis_state(spec.get(axis))}
        for key, label, axis in _LADDER
    ]
    current = next((g for g in ladder if g["status"] not in _DONE_STATES), ladder[-1])
    return {"stage": current["label"], "state": current["status"], "ladder": ladder}


# --------------------------------------------------------------------------- #
# member verdict + gate criterion
# --------------------------------------------------------------------------- #
def _member_evaluated(spec: dict) -> bool:
    """The study has run and been evaluated (a Decision verdict can be read)."""
    evaluated = _axis_state(spec.get("evaluation_status")) in ("passed", "blocked", "waived")
    decided = _norm(spec.get("gate_status")) in (
        *_GATE_REFUTED, *_GATE_QUALIFIED, *_GATE_MET,
    )
    has_verdict = _norm(spec.get("verdict")) in (
        *_VERDICT_REFUTED, *_VERDICT_QUALIFIED, *_VERDICT_MET, "inconclusive",
    )
    return evaluated or decided or has_verdict


def _member_verdict(spec: dict) -> str:
    """A study's own Decision verdict → {met, qualified, refuted, in_progress}.

    Refuted dominates (a failed Decision gate or a refuted/honest-negative verdict
    is a refutation regardless of other axes); then qualified; then met.
    """
    gs = _norm(spec.get("gate_status"))
    vd = _norm(spec.get("verdict"))
    if gs in _GATE_REFUTED or vd in _VERDICT_REFUTED:
        return "refuted"
    if vd in _VERDICT_QUALIFIED or gs in _GATE_QUALIFIED:
        return "qualified"
    if gs in _GATE_MET or vd in _VERDICT_MET:
        return "met"
    return "in_progress"


def _criterion_status(gate: dict, member_specs: List[dict]) -> str:
    """The gate's matched-null / ablation criterion → {met, refuted, pending}.

    A gate may declare ``criterion_findings`` (member finding ids that carry the
    matched-null/ablation arm). If so: every listed finding confirmed → ``met``;
    any listed finding contradicted → ``refuted`` (the positive claim is actively
    disproven); otherwise (planned/missing/partial) → ``pending``. With no declared
    findings the criterion is not audited here — the member verdicts carry it — so
    it returns ``met`` (non-blocking).
    """
    listed = gate.get("criterion_findings")
    if not listed:
        return "met"
    by_id = {
        f.get("id"): f
        for spec in member_specs
        for f in (spec.get("findings") or [])
    }
    states: List[str] = []
    for fid in listed:
        f = by_id.get(fid)
        st = _norm(f.get("status")) if isinstance(f, dict) else ""
        if st in _FINDING_CONFIRMED:
            states.append("confirmed")
        elif st in _FINDING_REFUTED:
            states.append("refuted")
        else:
            states.append("pending")  # planned / partial / novel / missing
    if any(s == "refuted" for s in states):
        return "refuted"
    if states and all(s == "confirmed" for s in states):
        return "met"
    return "pending"


def _gate_verdict(gate: dict, member_specs: List[dict], *, incomplete: bool) -> str:
    """Derive an evaluated gate's own verdict from members + criterion.

    ``incomplete`` is True when the gate still has pending (unscaffolded) members
    or not all of its own members are scaffolded — a genuine positive then reads
    as ``qualified`` (satisfied so far, more to come), never a clean ``met``.
    """
    member_verdicts = [_member_verdict(s) for s in member_specs]
    crit = _criterion_status(gate, member_specs)

    # Refuted: the criterion is disproven, or every evaluated member is refuted.
    if crit == "refuted":
        return "refuted"
    if member_verdicts and all(v == "refuted" for v in member_verdicts):
        return "refuted"
    # A refuted member on an otherwise-live gate means its criterion arm failed.
    if "refuted" in member_verdicts:
        return "refuted"
    # Criterion evidence declared but not yet confirmed → still in progress.
    if crit == "pending":
        return "in_progress"
    # Criterion met, no refuted members → met, or qualified if caveated.
    if "qualified" in member_verdicts or incomplete:
        return "qualified"
    if member_verdicts and all(v == "met" for v in member_verdicts):
        return "met"
    return "in_progress"


def build_plan_progress(investigation: dict, studies: Dict[str, dict]) -> List[dict]:
    """Derive the gate board from ``investigation['plan_gates']`` + ``studies``.

    ``studies`` maps a study slug to its parsed ``study.yaml``; a gate member slug
    absent from it is treated as unscaffolded (pending). Each evaluated gate shows
    its own verdict (met/qualified/refuted); a not-yet-evaluated gate is in_progress
    or blocked by whether its prior spine gate has advanced; a gate with no
    scaffolded members is pending. Off-spine branches (``off_spine: true``) never
    gate downstream — nothing ``extends`` them.
    """
    gates = investigation.get("plan_gates") or []
    by_id = {g.get("id"): g for g in gates}

    # Cumulative own-member slugs via the extends chain (for display + criterion).
    def _chain_members(gate: dict) -> List[str]:
        seen: List[str] = []
        cur: Optional[dict] = gate
        guard = 0
        while cur is not None and guard < len(gates) + 1:
            for slug in cur.get("member_studies") or []:
                if slug not in seen:
                    seen.append(slug)
            parent = cur.get("extends")
            cur = by_id.get(parent) if parent else None
            guard += 1
        return seen

    status_by_id: Dict[str, str] = {}
    rows: List[dict] = []

    # plan_gates are authored prior-before-dependent (A1, A2, B, ...); compute in
    # order so a gate's ``extends`` status is already known.
    for gate in gates:
        gid = gate.get("id")
        own = list(gate.get("member_studies") or [])
        pending = list(gate.get("pending_studies") or [])
        scaffolded = [s for s in own if s in studies]
        member_specs = [studies[s] for s in scaffolded]

        prior_id = gate.get("extends")
        prior_advanced = (prior_id is None) or (status_by_id.get(prior_id) in _ADVANCES)

        if not scaffolded:
            status = "pending"
        elif not all(_member_evaluated(s) for s in member_specs):
            # members scaffolded but not all evaluated yet
            status = "in_progress" if prior_advanced else "blocked"
        else:
            incomplete = bool(pending) or (len(scaffolded) < len(own))
            status = _gate_verdict(gate, member_specs, incomplete=incomplete)
        status_by_id[gid] = status

        member_stages = [
            {"study": slug, **study_stage(studies[slug])} for slug in scaffolded
        ]
        row = {
            "id": gid,
            "name": gate.get("name"),
            "extends": prior_id,
            "member_studies": own,
            "pending_studies": pending,
            "criterion": gate.get("criterion"),
            "status": status,
            "member_stages": member_stages,
            "cumulative_members": _chain_members(gate),
        }
        if gate.get("criterion_findings"):
            row["criterion_findings"] = list(gate.get("criterion_findings"))
        if gate.get("off_spine"):
            row["off_spine"] = True
        if gate.get("optional"):
            row["optional"] = True
        rows.append(row)

    return rows
