"""Builds-on handoff-contract validator.

Encodes the upgrade plan's "Explicit interfaces and composition contracts"
handoff table and checks that every scaffolded handoff edge actually transfers
the required state: the upstream study must EMIT it to the downstream study, and
the downstream must declare it RECEIVES it, covering every required item. It
reads a structured ``handoff`` block on each study record (not prose), so the
audit is deterministic.

A ``builds on`` edge with no handoff-table entry is not checked for coverage
here (the plan specifies required state only for the integration edges); an edge
whose downstream study is not yet scaffolded is skipped, not failed.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

# The plan's handoff table (§"Explicit interfaces and composition contracts").
# Each entry: the upstream source study id(s), the downstream study id, and the
# required transferred state. Ids use the plan's study numbering. Required items
# are written in a canonical, lower-case phrasing; matching is token-subset +
# synonym aware (see ``covers``), so a study may phrase them more richly.
HANDOFF_TABLE = [
    {"sources": [27], "to": 29, "requires": [
        "h2 flux", "inorganic carbon flux", "ph", "temperature",
        "ionic activities", "catalyst state", "time-dependent feeds"]},
    {"sources": [28], "to": 29, "requires": [
        "canonical species", "balanced stoichiometry", "rate forms",
        "parameter bounds", "confidence tags"]},
    {"sources": [29], "to": 30, "requires": [
        "active reactions", "molecular species", "concentrations",
        "competing degradation routes"]},
    {"sources": [30], "to": 31, "requires": [
        "precursor concentrations", "temperature", "ph",
        "residence time", "competing sinks"]},
    {"sources": [31], "to": 32, "requires": [
        "amphiphile pools", "composition-dependent assembly", "permeability"]},
    {"sources": [32], "to": 33, "requires": [
        "molecular inventories", "membrane inventories", "energy state",
        "osmotic pressure", "volume"]},
    {"sources": [33], "to": 34, "requires": [
        "daughter inventories", "stochastic segregation",
        "reproductive outcomes", "pedigree"]},
    {"sources": [32, 35], "to": 37, "requires": [
        "chemical coupling cycles", "budget for replacing vent gradients"]},
    {"sources": [33, 34, 36], "to": 37, "requires": [
        "lineage survival", "fitness", "community dependencies", "dispersal state"]},
]

# Synonyms normalised at the token level so a study's own wording matches the
# canonical required item (e.g. the plan writes "T" for temperature).
_SYNONYMS = {"t": "temperature", "temp": "temperature", "h₂": "h2"}
_STOP = {"and", "the", "of", "a", "an", "with", "to"}


def _tokens(text: str) -> set:
    text = text.lower().replace("-", " ").replace("/", " ")
    text = re.sub(r"[(),.;:]", " ", text)
    out = set()
    for tok in text.split():
        tok = _SYNONYMS.get(tok, tok)
        if tok and tok not in _STOP:
            out.add(tok)
    return out


def covers(required_item: str, provided: Sequence[str]) -> bool:
    """True if some provided phrase covers ``required_item`` (token-subset match)."""
    req = _tokens(required_item)
    if not req:
        return False
    return any(req <= _tokens(p) for p in provided)


def required_state(frm: int, to: int) -> Optional[List[str]]:
    """Required transferred state for a single-source edge ``frm -> to``."""
    for entry in HANDOFF_TABLE:
        if entry["to"] == to and frm in entry["sources"]:
            return list(entry["requires"])
    return None


def _index(studies: Sequence[dict]) -> Dict[int, dict]:
    idx = {}
    for s in studies:
        pid = s.get("plan_id")
        if pid is not None:
            idx[pid] = s
    return idx


def validate_investigation(studies: Sequence[dict]) -> List[str]:
    """Return handoff-contract violations across all scaffolded contract edges.

    ``studies`` is a list of records, each with ``plan_id`` and a ``handoff``
    block: ``{"emits": [{"to", "provides"}], "receives": [{"from", "requires"}]}``.
    An edge is checked only when its downstream study is present (upstream may be
    unscaffolded — that is reported as an un-emittable source, not skipped).
    """
    idx = _index(studies)
    violations: List[str] = []

    for entry in HANDOFF_TABLE:
        to = entry["to"]
        sources = entry["sources"]
        req = entry["requires"]
        downstream = idx.get(to)
        if downstream is None:
            continue  # not scaffolded yet — nothing to audit for this edge

        provided: List[str] = []
        declared_received: List[str] = []
        d_handoff = downstream.get("handoff") or {}
        receives = d_handoff.get("receives") or []

        for src in sources:
            up = idx.get(src)
            if up is None:
                violations.append(
                    f"handoff {src}->{to}: upstream study {src} not scaffolded, cannot emit")
            else:
                emits_to = [e for e in (up.get("handoff") or {}).get("emits", [])
                            if e.get("to") == to]
                if not emits_to:
                    violations.append(
                        f"handoff {src}->{to}: study {src} does not emit a handoff to {to}")
                for e in emits_to:
                    provided.extend(e.get("provides") or [])

            recs = [r for r in receives if r.get("from") == src]
            if not recs:
                violations.append(
                    f"handoff {src}->{to}: study {to} does not receive a handoff from {src}")
            for r in recs:
                declared_received.extend(r.get("requires") or [])

        label = "+".join(str(s) for s in sources)
        for item in req:
            if not covers(item, provided):
                violations.append(
                    f"handoff {label}->{to}: emitted state missing required item '{item}'")
            if not covers(item, declared_received):
                violations.append(
                    f"handoff {label}->{to}: study {to} does not declare receiving '{item}'")

    return violations
