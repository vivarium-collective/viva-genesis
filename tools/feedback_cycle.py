#!/usr/bin/env python3
"""feedback_cycle — drive the discovery engine from a reopening-feedback YAML.

RETIRED PROTOTYPE (kept as the offline fallback). The canonical implementation is now
``discovery_engine.feedback_compiler`` (schema-validated ``compile_feedback`` /
``reconcile_and_reopen`` / ``ingest_feedback``, merged in discovery-engine #19). The runner
(``discovery_runner.ensure_reopened``) prefers the engine compiler whenever it is importable
and only falls back to this local translator when it is not. This module stays as that fallback
and as the record of the prototype's mapping; new behaviour belongs in the engine compiler.

A *reopening-feedback* file (``feedback_version: 1.0`` with ``target`` /
``status_reconciliation`` / ``scientific_challenge`` / ``next_cycle`` / ...) is a
scientist's instruction to REOPEN and REDIRECT an investigation. The engine's
existing inline-feedback importer (viva_superpowers.feedback_import) is a passive
inbox; this translator instead maps the feedback into *engine-native authored
artifacts* so the ordinary discovery cycle (frontier / advance) drives progress:

  reopen         -> register the challenge's mandate as UNMET high-priority
                    acceptance_criteria + reopen executive.verdict_status
                    (an unmet blocking criterion makes closure() return open)
  challenge      -> investigation objective + central gap
  hypotheses     -> competing hypotheses with DISJOINT numeric predictions,
                    attached to the new discriminating studies so
                    discriminating_hypotheses() raises experiment-design items
  controls       -> required_mechanisms (controls the engine must honour)
  diagnostics    -> a reconciliation_log (+ per-study attention flags)
  next_cycle     -> seeded, run-ready-shaped study specs (reuse + extend_with
                    -> required_mechanisms; measurements -> observables +
                    behavior_tests whose pass_if encodes the decision_rule)
  composite      -> required_mechanisms for the bridge composite, so the
                    capability-gap loop raises a build_process (model-building)
  autonomy       -> cycle_flags.autonomy

Prior closure + rationale are preserved in a lifecycle_history audit entry
(never silently dropped). Content-addressed ids keep the ingest idempotent.

Usage:
  python tools/feedback_cycle.py <feedback.yaml> --workspace workspace [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _hash8(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:8]


def _load(p: Path) -> dict:
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise SystemExit(f"{p}: expected a top-level mapping")
    return d


# ── predicted-observable bands per competing hypothesis ──────────────────────
# A discriminating study needs >=2 hypotheses predicting the SAME observable with
# DISJOINT numeric bands (so experiment_design.design_discriminating_study fires).
# We derive those bands from each study's decision_rule + the hypothesis mechanism.
_DISCRIMINATING = {
    # study slug -> {observable, hypotheses: [(hyp_id, statement, op, value)]}
    "study-selection-for-proximity": {
        "observable": "selection_coefficient_for_adhesion",
        "rule": "Syntrophy-first is preferred only where contact phenotypes invade and "
                "persist with POSITIVE selection under exchange, but not in no-exchange controls.",
        "arms": [
            ("H1-syntrophy-first", "Exchange creates positive selection for contact "
             "(adhesion-seeking phenotypes invade and persist).", ">", 0.0),
            ("H4-no-integration", "After adhesion costs, contact is NOT selected — "
             "external syntrophy stays fitter (selection <= 0).", "<=", 0.0),
        ],
    },
    "study-enclosure-mechanics": {
        "observable": "probability_of_stable_enclosure",
        "rule": "Enclosure is supported only if mechanically valid, persistent outcomes occur "
                "without imposing the desired topology as a starting condition.",
        "arms": [
            ("H2-geometry-first", "Physically constrained remodelling reaches stable "
             "enclosure in a majority of the feasible regime.", ">=", 0.5),
            ("H3-parasitism-or-conflict", "Enclosure is reached but is unstable / "
             "exploitative — stable-enclosure probability stays low.", "<", 0.5),
        ],
    },
    "study-contact-to-enclosure-coupling": {
        "observable": "joint_feasibility_region",
        "rule": "Reject a continuous syntrophy-first bridge where the selected-contact regime "
                "and the feasible-enclosure regime do NOT overlap.",
        "arms": [
            ("H1-syntrophy-first", "The selected-contact regime and the feasible-enclosure "
             "regime overlap (continuous bridge exists).", ">", 0.0),
            ("H4-no-integration", "Selected-contact and feasible-enclosure regimes are "
             "disjoint — no continuous bridge.", "<=", 0.0),
        ],
    },
}

# bridge composite (following_cycle.new_composite_model) -> required mechanisms the
# catalog must provide; those it cannot provide become capability_gap build tasks.
_CONTROL_MECHANISMS = [
    "no_exchange", "no_adhesion", "no_enclosure",
    "low_vs_high_diffusion", "efficient_vs_inefficient_energy_coupling",
    "faithful_vs_failed_vertical_transmission",
]


def _parent_composite(studies: dict, reuse: list[str]) -> str | None:
    """First-fidelity arm: reuse a named parent study's baseline composite path."""
    for slug in reuse or []:
        spec = studies.get(slug)
        if not isinstance(spec, dict):
            continue
        base = spec.get("baseline")
        if isinstance(base, list) and base and isinstance(base[0], dict):
            return base[0].get("composite")
        if isinstance(base, dict):
            return base.get("composite")
    return None


def _seed_study(design: dict, inv: str, studies: dict) -> dict:
    slug = design["id"]
    disc = _DISCRIMINATING.get(slug, {})
    measurements = design.get("measurements") or []
    extend = design.get("extend_with") or []
    reuse = design.get("reuse") or []
    parent_comp = _parent_composite(studies, reuse)
    # behavior tests: the discriminating observable (pass_if from the hypothesis band)
    # + one preregistered test per measurement (directional, author-to-sharpen).
    btests = []
    if disc:
        obs = disc["observable"]
        # the gate test = the positive arm's band (what "supported" requires)
        pos = disc["arms"][0]
        btests.append({
            "name": f"{slug}-discriminates",
            "classification": "primary",
            "description": disc["rule"],
            "measure": obs,
            "pass_if": {"op": pos[2], "value": pos[3]},
        })
    for m in measurements:
        if disc and m == disc.get("observable"):
            continue
        btests.append({
            "name": f"{slug}-{_slug(m)}",
            "classification": "secondary",
            "description": f"Preregistered measurement: {m} (bands to be sharpened before run).",
            "measure": m,
        })
    spec = {
        "schema_version": "0.4",
        "name": slug,
        "title": design.get("question") or slug,
        "investigation": inv,
        "question": design.get("question"),
        "claim": None,  # hypothesis-neutral until evidence decides
        "hypothesis": (disc["arms"][0][1] if disc else None),
        "concept": "endosymbiosis transition bridge",
        "topic": "eukaryogenesis",
        "status": "planned",
        "design_status": "designed",
        "simulation_status": "not_started",
        "evaluation_status": "not_started",
        "gate_status": "not_started",
        "created": _now(),
        "parent_studies": [{"study": s, "relation": "builds-on"} for s in reuse],
        "required_mechanisms": list(extend) + _CONTROL_MECHANISMS,
        "baseline": ([{
            "name": "baseline",
            "composite": parent_comp,
            "params": {},
            "note": "First-fidelity arm: reuses the parent composite named in the feedback's "
                    "`reuse`. The coupled proto_endosymbiosis_hybrid composite (with the "
                    "extend_with mechanisms) is the next-fidelity arm — a capability gap to build.",
        }] if parent_comp else []),
        "variants": [],
        "observables": list(measurements),
        "behavior_tests": btests,
        "visualizations": [],
        "findings": [],
        "runs": [],
        "tags": ["bridge", "discriminating", "reopened-by-feedback"],
    }
    return spec


def ingest(feedback: dict, inv_spec: dict, studies: dict) -> dict:
    """Return {inv_spec, new_studies:{slug:spec}, audit, summary}."""
    inv = feedback.get("target", {}).get("investigation") or inv_spec.get("name")
    challenge = feedback.get("scientific_challenge", {}) or {}
    next_cycle = feedback.get("next_cycle", {}) or {}
    following = feedback.get("following_cycle", {}) or {}
    instr = feedback.get("cycle_instructions", {}) or {}

    inv_spec = json.loads(json.dumps(inv_spec, default=str))  # deep copy
    audit = {"at": _now(), "event": "reopened_by_feedback",
             "feedback_intent": feedback.get("target", {}).get("intent"),
             "prior_status": inv_spec.get("status"),
             "prior_verdict_status": (inv_spec.get("executive") or {}).get("verdict_status"),
             "rationale": feedback.get("human_feedback_to_engine", "").strip()[:400]}

    # 1. seed the discriminating studies
    new_studies = {}
    for design in next_cycle.get("design", []) or []:
        spec = _seed_study(design, inv, studies)
        new_studies[spec["name"]] = spec
    merged = dict(studies)
    merged.update(new_studies)

    # 2. competing hypotheses with disjoint predictions, attached to the new studies
    hyps = list(inv_spec.get("hypotheses") or [])
    seen = {h.get("id") for h in hyps if isinstance(h, dict)}
    for slug, disc in _DISCRIMINATING.items():
        if slug not in new_studies:
            continue
        ids = [a[0] for a in disc["arms"]]
        for (hid, stmt, op, val) in disc["arms"]:
            uid = f"{hid}@{slug}"
            if uid in seen:
                continue
            seen.add(uid)
            hyps.append({
                "id": uid,
                "study": slug,
                "statement": stmt,
                "competing_with": [f"{o}@{slug}" for o in ids if o != hid],
                "predictions": [{
                    "observable": disc["observable"],
                    "when": {"regime": "under_exchange_vs_control"},
                    "expected": {"op": op, "value": val},
                }],
                "status": "open",
            })
    inv_spec["hypotheses"] = hyps

    # 3. acceptance criteria: the discriminating behavior tests are the new gates
    acs = list(inv_spec.get("acceptance_criteria") or [])
    ac_keys = {(a.get("study"), a.get("behavior")) for a in acs if isinstance(a, dict)}
    for slug in new_studies:
        beh = f"{slug}-discriminates"
        if (slug, beh) not in ac_keys:
            acs.append({"study": slug, "behavior": beh})
    inv_spec["acceptance_criteria"] = acs

    # 4. studies list
    sl = list(inv_spec.get("studies") or [])
    for slug in new_studies:
        if slug not in sl:
            sl.append(slug)
    inv_spec["studies"] = sl

    # 5. required_mechanisms (bridge composite modules + the coupling contract)
    comp = (following.get("new_composite_model") or {})
    mechs = list(inv_spec.get("required_mechanisms") or [])
    for m in (comp.get("modules") or []):
        if m not in mechs:
            mechs.append(m)
    inv_spec["required_mechanisms"] = mechs
    inv_spec["bridge_composite"] = {
        "name": comp.get("name"), "architecture": comp.get("architecture"),
        "modules": comp.get("modules"), "coupling_contract": comp.get("coupling_contract"),
        "status": "proposed",
    }

    # 6. reopen: executive verdict back to open + objective + central gap
    ex = dict(inv_spec.get("executive") or {})
    ex["verdict_status"] = "open"
    ex["objective"] = challenge.get("question")
    ex["central_gap"] = challenge.get("central_gap")
    ex["mandate"] = challenge.get("mandate")
    inv_spec["executive"] = ex
    inv_spec["status"] = feedback.get("status_reconciliation", {}).get("requested_state", "active")

    # 7. cycle flags + lifecycle audit + reconciliation log
    cf = dict(inv_spec.get("cycle_flags") or {})
    cf["autonomy"] = instr.get("autonomy", "supervised")
    cf["reopened"] = True
    inv_spec["cycle_flags"] = cf
    inv_spec.setdefault("lifecycle_history", []).append(audit)
    inv_spec["reconciliation_log"] = [
        {"id": d.get("id"), "severity": d.get("severity"),
         "observation": d.get("observation"), "request": d.get("request"), "status": "open"}
        for d in (feedback.get("report_diagnostics") or [])
    ]

    summary = {
        "investigation": inv,
        "reopened": True,
        "new_studies": list(new_studies),
        "new_hypotheses": sum(len(d["arms"]) for s, d in _DISCRIMINATING.items() if s in new_studies),
        "new_acceptance_criteria": len(new_studies),
        "bridge_composite": comp.get("name"),
        "required_mechanisms": len(mechs),
        "reconciliation_items": len(inv_spec["reconciliation_log"]),
    }
    return {"inv_spec": inv_spec, "new_studies": new_studies, "audit": audit, "summary": summary}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("feedback")
    ap.add_argument("--workspace", default="workspace")
    ap.add_argument("--write", action="store_true", help="write the mutations (default: dry-run)")
    args = ap.parse_args()

    fb = _load(Path(args.feedback))
    inv = fb.get("target", {}).get("investigation")
    ws = Path(args.workspace)
    inv_dir = ws / "investigations" / inv
    inv_yaml = inv_dir / "investigation.yaml"
    inv_spec = _load(inv_yaml)
    studies = {}
    for slug in inv_spec.get("studies") or []:
        sp = ws / "studies" / slug / "study.yaml"
        if sp.is_file():
            studies[slug] = _load(sp)

    out = ingest(fb, inv_spec, studies)
    print(json.dumps(out["summary"], indent=2))

    if not args.write:
        print("\n(dry-run; pass --write to apply)")
        return 0

    inv_yaml.write_text(yaml.safe_dump(out["inv_spec"], sort_keys=False, default_flow_style=False), encoding="utf-8")
    for slug, spec in out["new_studies"].items():
        sdir = ws / "studies" / slug
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "study.yaml").write_text(
            yaml.safe_dump(spec, sort_keys=False, default_flow_style=False), encoding="utf-8")
    print(f"\nwrote {inv_yaml} + {len(out['new_studies'])} seeded studies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
