"""Cumulative integration-gate board for the origins-of-life-vent plan.

Pure ``(investigation, studies) -> rows`` derivation: it reads the investigation's
``plan_gates`` block (gate A-D/E definitions + member_studies + criterion, authored
by hand) and computes each gate's **status** from its member studies' lifecycle
gates, honoring the cumulative ``extends`` chain. The dashboard renders the board
from this structure; nothing here writes.

Two pieces:

- :func:`study_stage` — the per-study six-axis "you are here" ladder, mirroring
  vivarium-workbench ``study_page.py`` §13 exactly so the board agrees with the
  per-study page: ``Plan←design_status``, ``Execution←simulation_status``,
  ``Evidence←evaluation_status``, ``Quality←evaluation_status`` (same axis),
  ``Decision←gate_status``, ``Release←expert_review_status``. Each axis token is
  classified into the gate-state vocabulary; the current stage is the first one
  not yet passed/waived.
- :func:`build_plan_progress` — rolls member studies' Decision gates up into each
  plan gate:

  * ``passed``      — every own member's Decision gate passed AND the gate's
    matched-null criterion is met AND it has no unscaffolded (pending) members
    AND the prior gate in the ``extends`` chain is passed (cumulative).
  * ``blocked``     — the gate has scaffolded members but its prior gate isn't
    passed (it can't pass before what it builds on).
  * ``in_progress`` — scaffolded members exist and the prior gate is passed (or
    there is none), but the gate isn't fully passed yet.
  * ``pending``     — the gate has no scaffolded member studies yet (its members
    are still plan numbers, e.g. 32-37).
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

# Finding-id markers that signal a gate's matched-null / ablation arm.
_NULL_MARKERS = ("beats-matched-null", "matched-null", "matched_null",
                 "null-control", "null_control", "ablation")

_DONE_STATES = ("passed", "waived")


def _axis_state(token) -> str:
    if not token:
        return "not-assessed"
    return _STATE_TOKENS.get(str(token).strip().lower(), "not-assessed")


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


def _is_passed(token) -> bool:
    return _axis_state(token) == "passed"


def _finding_confirmed(f: dict) -> bool:
    return str(f.get("status", "")).strip().lower() in ("confirms", "confirmed", "passed")


def _criterion_met(gate: dict, member_specs: List[dict]) -> bool:
    """Whether the gate's matched-null / ablation criterion is satisfied.

    If the gate declares ``criterion_findings`` (member finding ids), every one
    must be confirmed. Otherwise fall back to a heuristic: any member finding
    whose id marks a matched-null / ablation arm must be confirmed; if a gate's
    members declare no such arm, the criterion is not blocked on a signal that
    isn't there (the member Decision gates carry it).
    """
    explicit = gate.get("criterion_findings")
    if explicit:
        confirmed = {
            f.get("id")
            for spec in member_specs
            for f in (spec.get("findings") or [])
            if _finding_confirmed(f)
        }
        return all(fid in confirmed for fid in explicit)
    null_findings = [
        f
        for spec in member_specs
        for f in (spec.get("findings") or [])
        if any(mk in str(f.get("id", "")).lower() for mk in _NULL_MARKERS)
    ]
    if not null_findings:
        return True
    return any(_finding_confirmed(f) for f in null_findings)


def build_plan_progress(investigation: dict, studies: Dict[str, dict]) -> List[dict]:
    """Derive the gate board from ``investigation['plan_gates']`` + ``studies``.

    ``studies`` maps a study slug to its parsed ``study.yaml``; a gate member
    slug absent from it is treated as unscaffolded (pending).
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

    # plan_gates are authored prior-before-dependent (A, B, C, ...); compute in
    # order so a gate's ``extends`` status is already known.
    for gate in gates:
        gid = gate.get("id")
        own = list(gate.get("member_studies") or [])
        pending = list(gate.get("pending_studies") or [])
        scaffolded = [s for s in own if s in studies]
        member_specs = [studies[s] for s in scaffolded]

        prior_id = gate.get("extends")
        prior_passed = (prior_id is None) or (status_by_id.get(prior_id) == "passed")

        if not scaffolded:
            status = "pending"
        elif not prior_passed:
            status = "blocked"
        else:
            all_decided = all(_is_passed(s.get("gate_status")) for s in member_specs)
            complete = all_decided and not pending and len(scaffolded) == len(own)
            if complete and _criterion_met(gate, member_specs):
                status = "passed"
            else:
                status = "in_progress"
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
        if gate.get("optional"):
            row["optional"] = True
        rows.append(row)

    return rows
