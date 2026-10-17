"""Load study.yaml handoff blocks into records for :mod:`viva_genesis.handoff.validate`."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import yaml

_SLUG_RE = re.compile(r"^og-(\d+)-")


def plan_id_from_slug(slug: str) -> Optional[int]:
    """Return the plan id encoded in an ``og-<n>-...`` slug, or None."""
    m = _SLUG_RE.match(slug)
    return int(m.group(1)) if m else None


def load_investigation(studies_dir) -> List[dict]:
    """Read every ``<slug>/study.yaml`` under ``studies_dir`` into validator records.

    Each record has ``id``, ``plan_id`` (explicit field, else derived from the
    slug), ``builds_on`` and a ``handoff`` block normalised to
    ``{"emits": [...], "receives": [...]}`` (empty lists when absent).
    """
    studies_dir = Path(studies_dir)
    records: List[dict] = []
    for sub in sorted(studies_dir.iterdir()):
        yaml_path = sub / "study.yaml"
        if not yaml_path.is_file():
            continue
        data = yaml.safe_load(yaml_path.read_text()) or {}
        plan_id = data.get("plan_id")
        if plan_id is None:
            plan_id = plan_id_from_slug(sub.name)
        handoff = data.get("handoff") or {}
        records.append({
            "id": data.get("name", sub.name),
            "plan_id": plan_id,
            "builds_on": data.get("builds_on") or [],
            "handoff": {
                "emits": handoff.get("emits") or [],
                "receives": handoff.get("receives") or [],
            },
        })
    return records
