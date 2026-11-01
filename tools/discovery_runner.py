#!/usr/bin/env python3
"""discovery_runner — continuously drive the discovery cycle from a discovery_request.

Implements the "feedback-triggered discovery cycle" control loop:

  envelope (discovery_request.yaml)  ->  execution policy (budgets, approvals, stop_when)
  feedback (scientific reopening YAML) -> engine-native artifacts (via feedback_cycle)
  then loop:  assess -> advance (dry/supervised) -> classify -> log -> should_stop

The loop never fabricates progress: in supervised mode it only auto-runs actions
that are NOT in require_approval_for AND are run-ready; everything else (simulations
when expensive_compute is gated, steers, model revisions, model builds) is surfaced
for approval, and the loop stops / waits on the stop_when conditions. This is the
governance layer (should_stop + budgets) around the feedback->engine translator.

Usage:
  PYTHONPATH=<engine-main-worktree> python tools/discovery_runner.py \
      --workspace workspace --once
  ... --watch --interval 300   # keep assessing; auto-resume when state changes
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feedback_cycle  # noqa: E402  (sibling module)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# which frontier ops each require_approval_for token gates
_APPROVAL_OPS = {
    "steer": {"steer"},
    "synthesize": {"synthesize"},
    "model_revision": {"revise_model"},
    "expensive_compute": {"test", "branch"},   # simulations
}
_SIM_OPS = {"test", "branch"}
_BUILD_OPS = {"build_process"}


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _gated_ops(require_approval_for: list[str]) -> set[str]:
    out: set[str] = set()
    for tok in require_approval_for or []:
        out |= _APPROVAL_OPS.get(tok, set())
    return out


def ensure_reopened(ws: Path, inv: str, feedback_path: Path, request_path: Path | None = None) -> dict:
    """Idempotent: reopen the investigation from the feedback.

    PROTOTYPE RETIRED into the engine: prefer ``discovery_engine.feedback_compiler``
    (the canonical, schema-validated compiler — ``ingest_feedback`` loads the
    discovery_request + its feedback, compiles to typed actions, reconciles, and writes)
    whenever the engine is importable. The local ``feedback_cycle`` translator remains ONLY
    as the offline fallback for when the engine isn't on the path.
    """
    inv_yaml = ws / "investigations" / inv / "investigation.yaml"
    inv_spec = _load(inv_yaml)
    if (inv_spec.get("cycle_flags") or {}).get("reopened"):
        return {"already": True, "status": inv_spec.get("status")}
    # Canonical path: the engine's feedback_compiler.
    if request_path and Path(request_path).is_file():
        try:
            from discovery_engine import feedback_compiler as _fc  # noqa: PLC0415
            res = _fc.ingest_feedback(str(request_path), str(ws), write=True) or {}
            return {"already": False, "via": "engine.feedback_compiler",
                    **(res.get("summary") or {k: v for k, v in res.items() if k != "compiled"})}
        except Exception as e:  # noqa: BLE001 — fall back to the local prototype translator
            _fallback_note = f"engine compiler unavailable ({type(e).__name__}); using local prototype"
        else:
            _fallback_note = None
    # Fallback: the retired local prototype translator.
    fb = _load(feedback_path)
    studies = {}
    for slug in inv_spec.get("studies") or []:
        sp = ws / "studies" / slug / "study.yaml"
        if sp.is_file():
            studies[slug] = _load(sp)
    out = feedback_cycle.ingest(fb, inv_spec, studies)
    inv_yaml.write_text(yaml.safe_dump(out["inv_spec"], sort_keys=False), encoding="utf-8")
    for slug, spec in out["new_studies"].items():
        sdir = ws / "studies" / slug
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "study.yaml").write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    return {"already": False, "via": "local-prototype-fallback", **out["summary"]}


def assess(ws: Path, inv: str, gated: set[str]) -> dict:
    """One engine assessment: run the cycle, classify the frontier, dry-advance."""
    from discovery_engine import discover, discovery_engine as de, model_architect
    try:
        from discovery_engine import capability_gaps
    except Exception:
        capability_gaps = None

    inv_path, inv_spec, studies = discover.load_cycle_inputs(str(ws), inv)
    catalog = model_architect.build_catalog(studies, ws_root=str(ws))
    cyc = discover.run_cycle(inv_spec, studies, catalog=catalog)
    if capability_gaps is not None:
        gaps = capability_gaps.propose_capability_gaps(inv_spec, studies, catalog) or []
        if gaps:
            cyc = dict(cyc)
            cyc["capability_gaps"] = gaps
    clo = de.closure(cyc, inv_spec)
    fr = de.frontier(cyc, inv_spec)
    na = de.next_action(cyc, inv_spec)

    runnable, human_gated, model_build, other = [], [], [], []
    for f in fr:
        op = f.get("op")
        item = {"kind": f["kind"], "op": op, "target": str(f.get("target"))[:60],
                "priority": f.get("priority")}
        if op in _BUILD_OPS or f["kind"] == "capability_gap":
            model_build.append(item)
        elif op in gated or f["kind"] in ("open_decision",):
            human_gated.append(item)
        elif op in _SIM_OPS:
            # a simulation that is NOT gated and run-ready would be auto-runnable
            runnable.append(item)
        else:
            other.append(item)

    # dry advance (supervised): what WOULD run / what needs building
    adv = {}
    try:
        adv = discover.advance_cycle(str(ws), inv, autonomous=False) or {}
    except Exception as e:
        adv = {"error": str(e)}

    return {
        "at": _now(),
        "closed": clo.get("closed"),
        "open_items": clo.get("open_items"),
        "next_action": {"kind": (na or {}).get("kind"), "op": (na or {}).get("op"),
                        "target": str((na or {}).get("target"))[:60]},
        "runnable": runnable, "human_gated": human_gated,
        "model_build": model_build, "other": other,
        "advance_needs_build": adv.get("needs_build"),
        "advance_would_run": adv.get("runs") or adv.get("would_run"),
    }


def should_stop(a: dict, cycle_n: int, policy: dict) -> str | None:
    ex = policy.get("execution", {})
    stop_when = set(policy.get("continuation", {}).get("stop_when") or [])
    if "scientific_objectives_satisfied" in stop_when and a.get("closed"):
        return "scientific_objectives_satisfied"
    if "budget_exhausted" in stop_when and cycle_n >= int(ex.get("max_cycles", 5)):
        return "budget_exhausted"
    if not a["runnable"]:
        if a["human_gated"] and "human_decision_required" in stop_when:
            return "human_decision_required"
        if "no_executable_actions" in stop_when:
            return "no_executable_actions"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="workspace")
    ap.add_argument("--inv", default=None)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=300)
    args = ap.parse_args()

    ws = Path(args.workspace)
    # locate the envelope
    inv = args.inv
    if inv is None:
        for env in ws.glob("investigations/*/discovery_request.yaml"):
            inv = env.parent.name
            break
    env_path = ws / "investigations" / inv / "discovery_request.yaml"
    req = _load(env_path).get("discovery_request", {})
    policy = req
    gated = _gated_ops(req.get("execution", {}).get("require_approval_for", []))
    feedback_path = ws / "investigations" / inv / req.get("feedback_file", "")

    log_dir = ws / ".discovery" / inv
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / "cycle-log.jsonl"

    reopen = ensure_reopened(ws, inv, feedback_path, request_path=env_path)
    print(json.dumps({"reopen": reopen}, indent=2))

    cycle_n = 0
    backoff = args.interval
    while True:
        cycle_n += 1
        a = assess(ws, inv, gated)
        stop = should_stop(a, cycle_n, policy)
        rec = {"cycle": cycle_n, "stop_reason": stop, **a}
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"\n── cycle {cycle_n} @ {a['at']} ──")
        print(f"  open={a['open_items']} closed={a['closed']}  next={a['next_action']['kind']}/{a['next_action']['op']}")
        print(f"  runnable(auto)={len(a['runnable'])}  human_gated={len(a['human_gated'])}  model_build={len(a['model_build'])}")
        if a["human_gated"]:
            print("  awaiting approval/decision:")
            for h in a["human_gated"][:4]:
                print(f"    - {h['kind']}/{h['op']} :: {h['target']}")
        if a["model_build"] or a.get("advance_needs_build"):
            print("  blocked on model build (P2):", a.get("advance_needs_build") or [m['target'] for m in a['model_build'][:3]])
        if stop:
            print(f"  STOP: {stop}")
            if args.once or stop in ("scientific_objectives_satisfied", "budget_exhausted"):
                break
            if args.watch:
                print(f"  watching for state change; re-assess in {backoff}s …")
                time.sleep(backoff)
                backoff = min(backoff * 2, 3600)  # back off while blocked
                cycle_n -= 1  # a blocked re-check is not a consumed cycle
                continue
            break
        # (supervised) auto-run only non-gated run-ready work — none yet; re-assess
        if args.once:
            break
        time.sleep(min(args.interval, 60))
    print(f"\nlog -> {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
