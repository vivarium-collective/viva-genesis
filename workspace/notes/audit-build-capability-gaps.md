# Audit & build capability gaps — origins-of-life upgrade

Started 2026-10-17 while adding the upgrade plan's resources + build registry
using viva-superpowers. Records **where the viva-superpowers / workbench build
and audit capabilities are missing** for what the plan requires, and — the user's
core concern — **what should be getting audited but currently isn't.**

Roster: viva-genesis (coordinator), genesis-helper, genesis-writer, genesis-viz.

---

## A. Build-capability gaps (found while doing deliverable 2)

1. **No registry slot for "tools/datasets to be built."** `/viva-catalog` only
   installs pbg-* packages that already exist; `/api/workspace-manifest` reports
   only already-importable processes/steps/emitters/viz/types. A plan that says
   "build these 7 methods + 1 dataset" has nowhere to live. → Worked around with
   `references/build-registry.yaml` (build_status per tool). *Streamlining:*
   viva-superpowers should have a first-class **planned-build / roadmap registry**
   the dashboard renders with status, so planned tools are visible, not prose.

2. **No "external database source" dataset kind.** `workspace.yaml datasets:` +
   the Inputs tab expect a local file + DOI; there is no way to register an
   external API/DB (Rhea, ChEBI, ORD, PubChem, KIDA) as a tracked upstream with
   an acquisition mode. → Worked around with `datasets/source-databases.yaml`.

3. **No scaffold for a shared, versioned, schema-validated derived dataset.**
   The Prebiotic Reaction Atlas is consumed by 5 studies and needs a record
   schema + raw/proposed/accepted separation. Datasets today are per-study file
   attachments. → Worked around with `datasets/prebiotic-reaction-atlas/`
   (README + schema.yaml). *Streamlining:* `/viva-expert` builds a Process
   wrapper but there is no "build a shared data asset + its validator" path.

---

## B. Audit-capability gaps (the "what should be audited but isn't" list)

These map directly to plan requirements that have **no enforcing gate today**:

4. **Dataset artifacts are not audited.** The report-card/gate pipeline audits
   STUDY runs (conservation ledgers, behavior_tests). Nothing validates a
   *dataset* at write time. Study 28's decision test — "No unexplained precursor
   or unbalanced reaction enters an accepted model" — has no gate. *Needed:* a
   write-time validator for the reaction atlas (mass balance, charge balance,
   ChEBI identity resolution, thermodynamic-domain check) that blocks a bad
   record, same way a study gate blocks a bad run.

5. **No cross-study / investigation-level gate.** The plan's **four cumulative
   integration gates (A/B/C/D)** each span several studies AND require a
   comparison against a *matched ablation/null with all chemical input fluxes
   held equal.* The current `pipeline_gate` is per-study; there is no construct
   for a gate that (a) spans members and (b) requires a matched-null arm.
   → **Biggest audit gap for this upgrade.**

6. **No "builds-on handoff" audit.** The plan's composition contract gives a
   required-transferred-state table (27→29: H2/inorganic-C flux, pH, T, ionic
   activities, catalyst state, time-dependent feeds; 28→29: canonical species,
   balanced stoichiometry, rate forms, bounds, confidence tags; etc.). The
   investigation-graph `builds-on` edge is currently **topical, not verified** —
   nothing checks that the downstream study actually receives the listed state,
   or flags a silent external substitution for missing upstream synthesis
   ("An external feed must have explicit provenance and should never silently
   substitute for missing upstream synthesis"). *Needed:* a handoff contract on
   each builds-on edge + an audit that the transferred state is real.

7. **No upstream-input manifest / untracked-feed audit.** Plan import step 6:
   "Produce mass/charge/energy ledgers and an upstream-input manifest for each
   cumulative gate." Evidence standard 2: "no untracked energy, biomass or
   amphiphile feeds." There is no audit that enumerates every input flux of a
   composite and flags one that isn't sourced from an upstream study or a cited
   dataset.

8. **Cross-simulator species-identity consistency is unchecked.** "Shared species
   must use the same formulas, charge states, units and identifiers across all
   simulators." No audit compares species identity/units across composites.

9. **Citation audit can't classify band type** (from genesis-writer). The linter
   fires "missing cite" without distinguishing an *internal threshold*
   (conservation/physics/model-internal — correctly uncitable, cite run_ids)
   from an *external claim without a source* (a real defect). Only the latter
   should fire. 79/79 genesis bands audited last round were internal.

10. **Viz artifacts drift silently** (from genesis-viz). Baked
    `studies/*/viz/*.html` keep stale axes/units after a viz-affecting dependency
    change (e.g. PR #68 real-time axes) until a manual canonical re-run. No gate
    ties a viz-affecting change to a required re-run.

---

## C. Streamlining ideas (how the upgrade could tighten the pipeline)

- Promote the **evidence standard** (plan §, 8 points) into a reusable
  acceptance-band template every new study (27-37) inherits, so the standard is
  gated, not aspirational.
- Make **negative results first-class**: "never tune success thresholds to force
  a pass" should be an audit (threshold-vs-result provenance), not a convention.
- A single **reaction-atlas validator** satisfies gaps 4, 6, 8 at once if it owns
  canonical species identity + balance + provenance for the whole investigation.

Owner: this session drives the gate/validator design with the workbench; writer
handles evidence/citation discipline; viz handles the re-run-on-change loop.

---

## D. Schema & scaffolding gaps (found scaffolding studies 27-31, from genesis-helper)

11. **No native `builds_on` or `tools[]`/`build_status` field in study.schema.json.**
    Both had to be added as custom fields (persist via `additionalProperties`,
    but no dashboard tooling reads them). The dependency structure the whole
    upgrade is organized around (and the composition-contract handoff) has no
    first-class schema home — the handoff validator must read custom fields.
    *Needed:* promote `builds_on` + a per-tool `build_status` into the schema.

12. **`parent_studies[].relation` enum disagrees between the /viva-study skill doc
    and the schema.** Schema (and the new two-axis ontology) uses
    `[builds-on, tests, motivates, alternative-to]`; the skill doc still lists
    `[leads-to, regulatory, supports, refutes]`. Existing og-07/og-08 use
    `leads-to` and lint-WARN. *Needed:* reconcile the viva-superpowers skill doc
    + viva-template schema to the ontology enum (small framework fix).

13. **`/viva-study new` cannot scaffold a design-phase study without a live
    dashboard + a real composite source.** Helper had to author `study.yaml`
    directly (og-08 `planned:true` pattern); `check-observables`/`preview-viz`
    are no-ops until composites exist. *Needed:* a design-phase scaffold path
    that doesn't require a built composite — the plan is explicitly "design
    first, build later," which the tooling doesn't support.

14. **Dependencies to studies not yet scaffolded can't be expressed in
    `parent_studies`** (parent-not-found) — the plan numbers 14,15,16,11,21,17
    are kept numeric-only in `builds_on` until those studies land. The
    dependency graph is only partially machine-represented until every referenced
    study exists; a forward-reference/placeholder dep has no home.

Shells: branch `wip/scaffold-studies-27-31` (off origin/main @493b5c7), 5
lint-clean design shells (og-27…og-31); handoff findings land in native
`findings[]` so the handoff validator has a target there.

15. **No design-phase findings vocabulary** (from genesis-helper, content pass).
    `study.schema.json` `findings.status` enum is `[confirms, partial,
    contradicts, novel]` (no `planned`) and `findings.kind` is `[biological,
    computational, methodological]` (no `dataset`). The findings vocab assumes
    POST-RUN outcomes; a design-phase study can't express a *planned* finding or
    a *dataset-coverage* finding (Study 28) without a WARN on every finding.
    *Needed:* add `planned` to status and `dataset` to kind (or a design-phase
    findings mode). Worked around by placing writer's content verbatim and
    accepting the non-blocking WARNs.

16. **Cross-branch cite dependency is invisible to tooling** (merge-ordering).
    4 cite keys (bonfio2017uvlight, budin2012concentration, hanczyc2003experimental,
    naturecomms2024ironsulfide) exist only on PR #69's papers.bib, not on main, so
    the spine content on `wip/scaffold-studies-27-31` cites dangling keys until #69
    (or its papers.bib) lands first. Nothing checks that a study's cite keys
    resolve against the bib on its *merge target*. *Needed:* a cite-resolution
    check in CI; meanwhile **merge order is enforced by hand: #69 before the spine
    branch.**

### Enforcement status (what these validators now gate)
- Gaps **1/3/4** → `viva_genesis/reaction_atlas/validate.py` (write-time atlas gate). CLOSED (tool built; wiring into the write path is the remaining step).
- Gap **6** → `viva_genesis/handoff/validate.py` (builds-on handoff contract). CLOSED (tool built; run against the live spine once the structured `handoff:` blocks are added).
- Gaps **2, 5, 7-16** remain open (framework/schema/CI changes or not-yet-built).
