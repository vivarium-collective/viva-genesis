#!/usr/bin/env python
"""Seed study-level ``verdict`` + ``evidence_tier`` from existing signals.

A heuristic *seed*, not an exact algorithm — a human corrects wrong calls in
the yaml afterwards. Idempotent: never overwrites a value that differs from the
heuristic unless ``--force``.

Usage: python scripts/derive_study_verdict_tier.py [--check] [--force]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
STUDIES = sorted((ROOT / "workspace" / "studies").glob("*/study.yaml"))

# gate_status: failed studies that are legitimate negatives by design, not disproofs
HONEST_NEGATIVES = {"og-01-cal-electrochemistry", "og-08-alt-robust-innovation-set"}

VERDICTS = {"supported", "qualified", "honest-negative", "refuted", "mixed"}
TIERS = {"conceptual_demonstration", "mechanistic_prediction", "calibrated"}


def _relations(s):
    return [str(r.get("relation", "")) for r in (s.get("parent_relations") or []) if isinstance(r, dict)]


def derive(study: dict) -> tuple[str, str]:
    name = str(study.get("name", ""))
    gate = str(study.get("gate_status", "")).strip().lower()
    rels = _relations(study)

    # verdict
    if name in HONEST_NEGATIVES:
        verdict = "honest-negative"
    elif "refutes" in rels:
        verdict = "refuted"
    elif gate in ("failed", "failed_evaluation", "refuted"):
        verdict = "honest-negative"  # an unclassified fail is a finding, not a disproof
    elif gate in ("partial", "needs_calibration"):
        verdict = "qualified"
    else:
        verdict = "supported"

    # tier: existing value wins; og-cal-* calibration studies -> calibrated; else mechanistic
    tier = str(study.get("evidence_tier", "")).strip()
    if tier not in TIERS:
        tier = "calibrated" if name.startswith("og-cal") else "mechanistic_prediction"

    return verdict, tier


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="dry-run; non-zero exit if any change")
    ap.add_argument("--force", action="store_true", help="overwrite human-set values that differ")
    args = ap.parse_args()

    changed = 0
    for path in STUDIES:
        data = yaml.safe_load(path.read_text()) or {}
        v, t = derive(data)
        updates = {}
        for key, val in (("verdict", v), ("evidence_tier", t)):
            cur = data.get(key)
            if cur == val:
                continue
            if cur and not args.force:  # respect a human correction
                continue
            updates[key] = val
        if not updates:
            continue
        changed += 1
        print(f"{path.parent.name}: " + ", ".join(f"{k}={w}" for k, w in updates.items()))
        if not args.check:
            data.update(updates)
            tmp = str(path) + ".tmp"
            with open(tmp, "w") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            os.replace(tmp, path)

    print(f"{changed} study.yaml file(s) {'would change' if args.check else 'changed'}")
    return 1 if (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
