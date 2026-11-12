# Design — S04–S06 multiscale build on viva-cpm (From Cells to Organisms)

**Investigation:** `viva-genesis` / `multicellularity` (VG-MULTI-001, "From Cells to Organisms")
**Branch:** `multicellularity`
**Date:** 2026-11-12
**Status:** DRAFT — awaiting approval. Nothing is built until this is approved.

---

## 1. Intent and why

S01–S03 run today, but they read "simple and boring": the simulator is a mean-field
cell-collective model and the results are scalar persistence/fitness numbers. The
science of the multicellular transition is *spatial and multiscale* — cells adhere,
clusters grow and fracture, interiors go hypoxic and differentiate, and lineages
compete as groups. None of that is visible in a scalar.

This design takes the three frontier studies already declared in the investigation —
S04 morphomechanics, S05 differentiation, S06 evolutionary individuality — off the
mean-field and onto a **real spatial Cellular Potts substrate (viva-cpm)**, so each
study produces something you can *watch* (cells snapping apart, a germ/soma pattern
emerging in an O₂ gradient, lineages fixing or being invaded) and grade on a spatial
readout tied to its existing acceptance criterion.

The "why now": the engine loop (`discover gap → refine-study → advance → viz`) and the
viva-cpm substrate are both in place; the missing piece is composing them into the
three studies. The payoff is the investigation's stated final deliverable — a phase
atlas and quantitative boundaries separating physical aggregation from physiological
integration from evolutionary individuality — rendered from spatial simulations
instead of asserted.

## 2. Goals

- Each of S04, S05, S06 runs a **real registered viva-cpm composite** (not the
  mean-field model), persists runs via an emitter, and passes a behavior test keyed to
  its existing acceptance criterion:
  - S04 → `propagule-toughness-predicted`
  - S05 → `specialization-improves-group-performance`
  - S06 → `between-group-heritable-fitness-stable`
- One **shared world blueprint** parameterizes all three (one lattice + optional PDE
  field + optional per-cell network), so the studies are three lenses on the same
  substrate, not three disconnected toys.
- Each scale coupling (field↔CPM, CPM↔subcellular, CPM↔population) is expressed as a
  **ProcessContract**, so the seam is typed and checkable, not implicit.
- Every study yields at least one **spatial, watchable visualization** (viva-cpm 3D
  viewer and/or a `/viva-viz` figure) that makes the mechanism legible.
- Each study is **promoted off the mean-field through the engine** — `discover gap`
  surfaces the mean-field limitation, `refine-study --composite` swaps in the spatial
  composite, `advance` runs it — so the upgrade is recorded as discovery, not a manual
  rewrite.

## 3. Non-goals

- Not re-running or re-deriving S01–S03; they stay as the mean-field first cycle.
- Not GPU/performance work. 2D lattices at demo scale are fine; 3D only where it buys a
  readout.
- Not adding any external CPM engine (Morpheus/Artistoo/CompuCell3D). viva-cpm is the
  single CPM backend; where it lacks a method we extend viva-cpm. (Standing user rule.)
- Not a new visualization framework; use viva-cpm's viewer + `/viva-viz`.
- Not publishing or deploying a read-only workbench as part of this build (separate ask).

## 4. Anti-goals (these would make it a failure even if it "worked")

- **Fabricated or forced results.** No un-provided literature constant, cap, or sink
  added solely to hit a target. If a study's acceptance behavior does not emerge from
  the provided mechanism, it is recorded as an HONEST OPEN QUESTION, not patched to a
  pass. (viva-study house rule #2.)
- **A scalar dressed up as spatial.** If a study ends up reading a single aggregate
  number with no spatial structure in the readout or the figure, it has not met the
  intent.
- **A disconnected composite per study.** Three composites that don't share the world
  blueprint defeat the multiscale point.
- **Differentiation/fracture/individuality that is hard-coded rather than emergent.**
  The interesting claim in each study is that the behavior *emerges* from the physics +
  the coupled network; a scripted fate assignment or a scripted split is engineered, not
  emergent, and must be labeled as such (`mechanism_origin: engineered`) — which for
  these studies means the study has not shown what it set out to.

## 5. Constraints

- **Substrate is viva-cpm** (`~/code/viva-cpm`, packages `cpm` + `viva_cpm`; process
  `local:!viva_cpm.processes.cpm_process.CPMProcess`). Extend viva-cpm where a method is
  missing rather than reaching for another engine.
- **Worktree discipline.** All work in the `multicellularity` worktree of viva-genesis
  and a dedicated worktree of viva-cpm; squash-merge; one task per worktree. Canonical
  checkouts are read-only.
- **Study authoring goes through `/viva-study`** (canonical `study.yaml`, provenance,
  AI-free split), not hand-edited YAML. Composites are real/registered or they lint as
  errors.
- **No AI attribution** in any commit/PR.
- **Rigor bar.** Each study carries model + replication (≥3 seeds stochastic) + a
  negative control (a system that should fail) + alternative hypotheses + tiered findings
  + falsifiability + limitations, so the rigor scorecard goes green.
- **Compute budget (my call).** Demo-scale **2D lattices** (~100×100 order), bounded step
  counts, single runs on the **laptop**; calibration **sweeps × multiseed on the Mac mini
  via Ray** (the established sweep path). 3D only where a readout demands it. The plan
  sizes each sweep to this budget rather than open-ended grids; if a study's rigor can't
  be met within it, that is reported, not papered over.

## 6. What viva-cpm already provides (verified 2026-11-12)

Confirmed by reading the repo, so the build composes rather than reinvents:

- **CPM energy terms** (Rust core `crates/cpm-core`): Volume, Surface, **Contact
  (ContactMatrix = differential adhesion)**, Length/elongation, External potential.
- **PDE reaction–diffusion fields** (`field.rs`, `test_fields`) with `field_at_cell`
  coupling into per-cell subcellular processes.
- **Mitosis** (`mitosis.rs`) — grow/divide.
- **Subcellular plugins**: `SBMLSubcell` (ODE), `BooleanSubcell`, receptor /
  adaptive-receptor — each wired to local field/neighbor context.
- **The `crypt` composite** (`viva_cpm/composites/crypt.py`) is a *working template for
  S05*: a niche secretes a field (Wnt), each progenitor cell runs a stemness ODE
  (`field_at_cell → ligand → S`) plus a Boolean fate gate (`S` + secretory-neighbor
  count → fate), and the CPM relabels cells by fate so differentiation feeds back into
  the tissue.
- **Spatial metrics** (`viva_cpm/metrics.py`): `connected_components(world, cell_id)`
  (the fracture/propagule primitive), `interior_medium_pockets` (lumen/cavity),
  `radial_cell_counts` / `radial_thickness`, `heterotypic_boundary` (a spatial
  differentiation metric).

**Implication:** S05 is largely a re-parameterization of an existing, tested pattern; S04
needs a **small multi-cell aggregation metric** built *on* `connected_components` (the
primitive counts components of a single cell's pixels — a grown clonal cluster is many
cell ids, so a cluster is the spatially-adhered aggregate of same-type neighbouring cells,
and fracture is that aggregate splitting into ≥2 components); only S06 needs genuinely new
substrate work (lineage identity through division + a group-selection partition).

**Sequencing note (from builder review).** S04's cluster detection is deliberately
*spatial* (adjacency of adhered same-type cells), **not** founder-tag based, so S04 does
**not** depend on S06's lineage machinery and the S04 → S05 → S06 order holds. S06 later
adds founder identity on top for *heritable* group tracking across generations; S04 only
needs "what is physically stuck together right now."

## 7. The decided "how" (these are my calls unless marked)

### 7.1 One shared world blueprint

A single composite factory, `multicellularity_world(**knobs)`, builds the shared
substrate: a CPM lattice with Volume/Surface/Contact(adhesion) terms, an optional PDE
field, optional per-cell subcellular networks, and mitosis. Each study instantiates it
with different knobs and attaches its own readout metrics. The three study composites are
therefore three configurations of one blueprint, satisfying the "shared world" goal.
*(My call. Alternative — three independent composites — rejected as an anti-goal.)*

### 7.2 S04 — morphomechanics ("how big before it breaks")

- **Physics:** adhesion (ContactMatrix) vs an external shear/detachment potential and
  growth (mitosis) inflating a clonal cluster.
- **Watch:** cluster grows, then **fractures into propagules** — detected by
  `connected_components` rising above 1 for a founding lineage's pixels.
- **Readout (ties to `propagule-toughness-predicted`):** the **critical cluster size /
  shear at fracture** as a function of adhesion strength, i.e. a predicted
  propagule-toughness curve. Negative control: zero differential adhesion → no cohesive
  propagule (fractures immediately / never coheres).
- **viva-cpm extension (small):** a **group-level fragmentation + propagule-accounting
  metric** (cluster = a founder lineage's adhered pixels; record split events, daughter
  sizes, and the stress/size at which they occur). `connected_components` is the
  primitive; the group accounting on top is new. May also need a tunable external shear
  potential if the current External term is insufficient to apply a controlled load.

### 7.3 S05 — differentiation ("who becomes what")

- **Mechanism:** fork the `crypt` pattern. An **O₂ PDE field** (consumed by cells,
  replenished at the boundary) sets up an interior-hypoxic gradient; each cell runs a
  stemness/fate network (SBMLSubcell ODE + BooleanSubcell gate) keyed to **local O₂**
  instead of Wnt; interior (hypoxic) cells cross the threshold and differentiate
  (germ/soma-like division of labor). The CPM relabels by fate; differentiation feeds
  back into adhesion/behavior.
- **Field choice = O₂ (primary).** *My call*, and it matches the investigation's own
  composite C ("model B + oxygen-limited growth"). The field plugin stays generic so a
  morphogen can be swapped in later. **← flagged for you (§10).**
- **Watch:** a **spatial germ/soma pattern** emerging along the O₂ gradient
  (`heterotypic_boundary`, `radial_cell_counts` by fate).
- **Readout (ties to `specialization-improves-group-performance`):** a group-performance
  metric (e.g. net viable growth or resource yield) for the **differentiated** group vs a
  **clamped-undifferentiated control** (negative control via the Intervention process).
  Specialization "improves performance" iff differentiated > undifferentiated under
  matched conditions.
- **viva-cpm extension (small):** mostly composition (new O₂ field + germ/soma network
  params); possibly a fate-**latching** option so a committed cell stays committed
  (crypt fate is currently responsive, not necessarily irreversible).

### 7.4 S06 — evolutionary individuality ("when is a group an individual")

- **Mechanism:** many clonal groups (each founded from a tagged founder) grow, fracture
  into offspring groups (reusing S04 propagule machinery), and are selected at the
  **group** level under an ecological regime; a heritable group-level trait (e.g. adhesion
  set-point or differentiation propensity) varies across founders.
- **Group life cycle = discrete generational reseed loop** *(my call, settling builder
  question #1).* A "generation" is an **outer population-genetic process** (the layer the
  investigation already anticipates): grow founders on the lattice → fracture into
  propagules (S04 machinery) → score each group → **select propagules and reseed a fresh
  lattice** of the next generation's founders, carrying each propagule's heritable
  group trait. This (not differential removal within one continuous run) is what makes
  "between-group *heritable* fitness across generations" operationalizable — heritability
  needs a parent→offspring group boundary. It is the larger of the two readings and sets
  S06's scope: a real `cell ↔ population` feedback process, not just an emitter.
- **Watch:** among-group vs within-group variance over generations of groups; lineages
  fixing or being invaded by cheaters.
- **Readout (ties to `between-group-heritable-fitness-stable`):** a **Price-equation
  partition** of selection into among-group and within-group components, and the
  **heritability** of the group trait across the group life cycle. Stable individuality =
  persistent, heritable among-group fitness variance that is not collapsed by
  within-group (cheater) selection. Negative control: mixed (non-clonal) founders →
  within-group conflict dominates, among-group heritability collapses. *(This is the
  `kind: adversarial` member the rigor bar wants.)*
- **S06 frame = ecological scaffolding (primary) + intrinsic conflict-mediation
  (secondary).** *My call.* Ecological scaffolding (group-level selection under an
  ecological regime) is the primary driver, matching H1/H4 and the curated Black 2020 /
  Hammerschmidt references; clonality-vs-cheater conflict (C2 "clonality limits conflict")
  is read as the secondary axis via the mixed-founder control. **← flagged for you (§10).**
- **viva-cpm extension (the real new work):** **lineage/founder identity carried through
  mitosis** (a founder id that propagates to daughters across division), a
  **group-tagging + Price-partition emitter**, and a **multi-founder clonality control**
  (clonal vs mixed seeding). The lineage id through division likely touches the Rust
  mitosis path or a Python bookkeeping layer over it.

### 7.5 Coupling contracts

Three couplings, each a ProcessContract so the seam is typed:
`field → cell` (local concentration in), `cell → field` (consumption/secretion out);
`cell ↔ subcellular` (`field_at_cell`/neighbor context in, fate/state out);
`cell ↔ population` (birth/death/fracture events up, selection/seeding down).

### 7.6 Engine seam

Each study is promoted via the discovery loop, not a manual swap: `discover gap --propose`
names the mean-field limitation; `refine-study --composite <spatial composite>` swaps the
substrate; `advance` runs it; viz via the viva-cpm viewer + `/viva-viz`. This keeps the
upgrade on the investigation record as discovery.

### 7.7 Sequencing (my call)

Full-stack but sequenced so something is watchable at every step:
1. **Shared world blueprint + S04 end-to-end** (proves the seam; earliest watchable
   result — fracture).
2. **S05** (adds the O₂ field + germ/soma network; reuses the world).
3. **S06** (adds lineage identity + group partition; reuses S04 fracture + S05 groups).

Each stage: compose → run (≥3 seeds) → record outcomes → behavior test → viz → report,
before starting the next (viva-study house rule #1, BIAS TO EXECUTE).

### 7.8 Packaging and the cross-repo engine seam (my call + one planning-time check)

- **Where the code lives.** The world blueprint and the three study composites live in
  **`viva_genesis`** (the investigation's package), importing **`viva_cpm` as a library
  dependency**. Substrate *extensions* (S04 group-fracture metric, S06 lineage id +
  group-partition + multi-founder seeding, any new shear term) ship as **feature PRs to
  viva-cpm**; the *composition* ships as content on the `multicellularity` branch. This
  keeps "extend viva-cpm, compose in genesis" clean and keeps the substrate reusable.
  Requires adding `viva_cpm` to the genesis environment (it is **not** installed there
  today) and confirming `viva_genesis.build_core`'s `@composite_generator` scan registers
  a composite that imports viva-cpm.
- **Engine-seam feasibility is a planning-time spike, not an assumption.** Goal #5 / §7.6
  assume `refine-study --composite <cpm composite>` + `advance` can target this composite
  and persist CPM `runs[].outcomes`. Before committing the "promoted as discovery" path,
  the plan's **first task verifies this end-to-end on a trivial CPM composite**; if the
  discovery tooling can't carry a cross-repo CPM composite or persist its outcomes, the
  fallback is a manual `refine-study` swap + direct run, with the gap filed against the
  engine. Either way the study still lands; only the "discovery-recorded" framing is at
  risk.

## 8. What's left to the builder

- Exact knob names/defaults on `multicellularity_world` and per-study params (adhesion
  strengths, field diffusion/consumption rates, thresholds), calibrated by a
  sweep × multiseed (house rule #5), not single values.
- Whether S04's controlled load reuses the existing External potential or needs a new
  shear term in viva-cpm — decide when wiring S04.
- 2D vs 3D per study (default 2D; use 3D only where a readout needs it).
- Precise form of the group-performance metric (S05) and the Price-partition emitter
  (S06), consistent with existing `runs[].outcomes` shapes.
- Where the lineage-id-through-mitosis extension lives (Rust core vs Python bookkeeping).
- Test band forms (generation-average vs strict), defaulting to generation-average per
  the viva-study band rule.

## 9. Open calls settled as defaults (my calls, listed so you can veto)

- Shared single world blueprint (vs three composites).
- S04 readout = critical size/shear-at-fracture vs adhesion curve.
- S05 group-performance = differentiated vs clamped-undifferentiated control.
- S06 readout = Price partition + group-trait heritability; adversarial mixed-founder
  control.
- Sequencing S04 → S05 → S06, full-stack.
- 2D default.

## 10. Owner calls — decided 2026-11-12

1. **S05 field identity → O₂.** Oxygen is the diffusible driver (interiors go hypoxic →
   differentiate), matching composite C's oxygen-limited growth. The field plugin stays
   generic so a morphogen can be added later as a variant.
2. **S06 primary frame → ecological scaffolding.** Group-level selection under an
   ecological regime is the lead mechanism (discriminating H1/H4); clonality-vs-cheater
   conflict (C2/H3) is the secondary control via the mixed-founder arm.
3. **Existing S04–S06 verdicts → reset to unproven** (§11): the spatial run earns the
   verdict; no asserted claim is carried forward.
4. **Still open — readout acceptability.** The three operational readouts in §7
   (critical size/shear-at-fracture for "toughness"; differentiated-vs-undifferentiated
   performance for "specialization improves performance"; Price partition + group-trait
   heritability for "heritable among-group fitness") are my proposed grading definitions.
   Owner to flag any they'd define differently before the plan locks them.

## 11. Existing S04–S06 results are asserted, not run (builder review finding)

`investigation.yaml` currently reports S04/S05/S06 as `passing-with-caveats` with
`executed_actions` dated 2026-11-10, **but** each `study.yaml` has `status: planned`,
`simulation_status: not_run`, `runs: []` — the verdicts are **asserted, not backed by any
simulation**. Because there are no mean-field runs to preserve, there is **no baseline arm
to keep**: the spatial composite becomes each study's first real result.

**Decided (confirmed 2026-11-12):** when the spatial build lands each study, **reset its
asserted verdict to unproven** (`planned`/`investigating`)
and let the actual spatial run earn the verdict and update the investigation's
`computed_acceptance`. The spatial run is the study's first evidence; the prior
`passing-with-caveats` is not carried forward as if it were established. This keeps the
record honest (no claim without a run) and is the main reason to confirm with you rather
than silently overwrite.
