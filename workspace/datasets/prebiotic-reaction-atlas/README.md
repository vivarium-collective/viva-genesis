# Prebiotic Reaction Atlas — new shared data asset

**Status: to be built (Study 28).** Declared here as part of the Scientific
Investigation Upgrade & Resource Plan (17 Oct 2026). This directory is the
canonical home for the atlas; the records themselves land here once Study 28's
extraction + validation tool (`viva-reaction-atlas`, see
[`../../references/build-registry.yaml`](../../references/build-registry.yaml))
produces them.

## What it is

A **versioned chemical network** of candidate prebiotic reactions connecting
C1–C3 products to functional chemistry, with per-reaction source provenance and
confidence tiers. It is the shared chemistry/provenance layer that studies
27-37 draw on, so that "shared species use the same formulas, charge states,
units and identifiers across all simulators" (plan §"Explicit interfaces").

The atlas is the handoff `28 -> 29`: *canonical species, balanced stoichiometry,
rate forms, parameter bounds and confidence tags.* A reaction that is not
balanced, or whose chemistry is uncertain, must be **flagged**, not silently
admitted — "No unexplained precursor or unbalanced reaction enters an accepted
model" (Study 28 decision test).

## Record schema (plan §"New shared data asset")

Each candidate record requires the fields in [`schema.yaml`](schema.yaml):

- chemical identifiers (ChEBI/canonical)
- balanced reaction + charge/proton conventions
- reaction evidence + source DOI
- measured temperature / pH / pressure / ionic strength
- catalyst mineral + preparation
- kinetic data or justified ranges
- uncertainties
- thermodynamic model (used for the ΔG screen)
- competing reactions
- a **measured / inferred / hypothetical** tier

**Raw observations are stored separately from agent-proposed mechanisms.**
Raw extracted records → `raw/`; agent-proposed or rule-generated candidates →
`proposed/`; the accepted, validated network → `atlas.vN.jsonl` at this level.

## Build + audit dependencies (not yet in place)

See [`../../notes/audit-build-capability-gaps.md`](../../notes/audit-build-capability-gaps.md).
The atlas needs a validator that enforces mass/charge balance, ChEBI identity
resolution and thermodynamic-domain checks at write time — the workspace does
not yet have a dataset-schema audit hook that runs on a non-study artifact like
this one.
