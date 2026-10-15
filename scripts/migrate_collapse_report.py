#!/usr/bin/env python3
"""Tier-C narrative collapse: drop the per-study `report.*` prose block and the
top-level `result`, which the vivarium-workbench renderers now fall back to the
canonical fields for (PR #1347: SSR + study-detail).

The whole `report.*` block is removed: SSR + study-detail fall back to the canonical
fields (#1347), the SPA study-card verdict already derives from `gate_status`, and
informational detection now uses `study_type`/`kind` (#1349) — so `report.verdict`
is optional too. Lossless: before dropping, any report.* field whose canonical home
is empty is promoted into it (title/confidence/conclusion/caveat).

Kept untouched: `conclusion`, `discovery_implications`, `limitations`, `findings`,
`claim`, etc. (no renderer fallback, or they ARE the canonical source).

Usage: python scripts/migrate_collapse_report.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
STUDIES = sorted((ROOT / "workspace" / "studies").glob("*/study.yaml"))

yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096  # don't re-wrap long plain scalars (keeps the diff to real changes)


def migrate(data) -> list[str]:
    """Mutate one study mapping in place; return a list of change notes."""
    notes: list[str] = []
    rep = data.get("report") or {}

    # Promote report.* into the canonical field ONLY when that field is empty,
    # so nothing a renderer would show goes blank after the drop.
    if rep.get("title") and not data.get("title"):
        data["title"] = rep["title"]; notes.append("promoted report.title -> title")
    if rep.get("confidence") and not data.get("confidence"):
        data["confidence"] = rep["confidence"]; notes.append("promoted report.confidence -> confidence")
    if rep.get("conclusion") and not data.get("conclusion"):
        data["conclusion"] = rep["conclusion"]; notes.append("promoted report.conclusion -> conclusion")
    if rep.get("caveat") and not data.get("limitations"):
        data["limitations"] = [rep["caveat"]]; notes.append("promoted report.caveat -> limitations[0]")

    # Decide what (if anything) of report survives.
    has_findings = bool(data.get("findings"))
    has_outcomes = any(
        isinstance(r, dict) and r.get("outcomes") for r in (data.get("runs") or [])
    )
    keep = {}
    # report.verdict is now optional everywhere (SSR -> computed; SPA card -> gate_status;
    # informational detection -> study_type/kind, workbench #1349), so it is dropped too.
    if rep.get("main_insight") and not has_findings:
        keep["main_insight"] = rep["main_insight"]  # fallback is the first finding
    if rep.get("key_metrics") and not has_outcomes:
        keep["key_metrics"] = rep["key_metrics"]  # fallback derives from run outcomes

    if "report" in data:
        if keep:
            data["report"] = keep
            notes.append(f"report.* -> {{{', '.join(keep)}}} (rest dropped)")
        else:
            del data["report"]; notes.append("dropped report block")
    if "result" in data:
        del data["result"]; notes.append("dropped top-level result")
    return notes


def main() -> int:
    check = "--check" in sys.argv
    changed = 0
    for p in STUDIES:
        data = yaml.load(p)
        notes = migrate(data)
        if not notes:
            continue
        changed += 1
        print(f"{p.parent.name}: {'; '.join(notes)}")
        if not check:
            yaml.dump(data, p)
    print(f"\n{changed}/{len(STUDIES)} studies {'would change' if check else 'migrated'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
