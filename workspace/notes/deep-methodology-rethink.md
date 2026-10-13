# Deep methodology rethink — viva-genesis simulation campaign

_Status: proposal for review (2026-10-13). Models-first. Derived from the current
campaign + `AI-Generated/Viva_Genesis_Visualization_Plan.pdf`._

## 0. The problem this fixes

The current stages work and pass their gates, but they are **too shallow to
explain**: each shows a single favorable run plus a couple of controls, emits flat
scalars, and renders a bespoke Plotly figure. Several models are reduced to the
point of being illustrative rather than investigative (og-03 is an analytic
`exp(Pe_acc)` column; og-05 a replicator with no energy accounting; og-06 an
error-threshold curve with no lineages). Measured against the visualization plan's
own acceptance checklist we have **World (partial) + Time**, but not **Mechanism**
or **Decision**, no parameter-space phase maps, no typed emit contract, and no
cross-campaign synthesis.

The plan's standard, restated as engineering requirements:

1. **Decision over demonstration.** Every stage runs a *parameter sweep* and shows
   the *region* where the hypothesis holds plus the neighboring regions where it
   fails — not a representative success. This is the single biggest change and the
   main lever on "deeply thought out."
2. **Typed emitted state, composable viewers.** Each process emits typed viz state
   (geometry, scalar/vector fields, pools, fluxes, entities, boundaries, lineage,
   provenance, gates); viewers compose it into one persistent vent world.
3. **Mechanistically deeper models, right tool per stage.** Reach past generic
   0-D/1-D ODE+FVM where the science demands fields, stochastic spatial dynamics,
   energy bookkeeping, or lineages.
4. **Three views per stage** (World / Mechanism / Decision) + **three
   cross-campaign figures** (Genesis Ladder, Viability Manifold, Provenance River).

Models-first means the per-stage **method deepening + its typed emit** lead; the
reusable SPA viewers are built on top once the models produce rich state.

---

## 1. The two foundational capabilities (build first)

These unblock most of the per-stage depth.

### 1a. Parameter-sweep harness (`viva_genesis.sweep`)
A runner that executes a composite over an N-D parameter grid, collects a decision
metric per point (via the existing evaluators), and emits a **phase-map grid**
(scalar/label field over parameter space) + the pass/fail region from the study's
acceptance band. Parallelizable; heavy sweeps go to the Mac mini via Ray
(`feedback_mini_ray_parallel_sweeps`). This is what turns every "representative
run" into a decision figure. Serves og-01, og-02, og-03, og-04, og-05, og-adv.

### 1b. Typed visualization-state contract (`viva_genesis.viz_state`)
bigraph-schema types for the plan's §8 emit categories, so processes emit typed
state and viewers consume it without per-stage glue:

| Category | Typed fields |
|---|---|
| Geometry | mesh / pore polygons / compartment boundaries / porosity field / topology |
| Scalar fields | T, pH, H2, CO2, concentration, potential, reaction rate (+ grid) |
| Vector fields | velocity, diffusive flux, electrochemical current (on faces) |
| Chemical pools | species id, amount/concentration, compartment id |
| Fluxes | source, target, species/energy carrier, signed rate |
| Entities | persistent id, position, geometry, parent id, phenotype |
| Boundaries | type, permeability-by-species, area, potential difference |
| Lineage | parent–child links, birth/death time, inherited state |
| Provenance | source process, evidence class, parameter/source id |
| Gates | metric, threshold, result, uncertainty, study id |

The deeper models (below) are what *produce* this state, so the contract and the
models co-develop.

---

## 2. Per-stage model deepening (the heart of this plan)

For each stage: current method → why it's too shallow → deeper method + tool →
new typed emit → the sweep/decision dimension.

### og-00 — Vent reactor
- **Now:** FiPy 2-D *lateral-gradient* reactor (prescribed hot-right wall) + PHREEQC
  serpentinization reduced to a 0-D source.
- **Shortfall:** the "cross-section" is a prescribed gradient, not a real buoyant
  plume — the animation barely moves; precipitation doesn't change geometry.
- **Deeper:** buoyancy-driven convection (Boussinesq; stream-function/vorticity or
  FiPy convection with a buoyancy-coupled velocity) so hot vent fluid genuinely
  rises and mixes; per-cell speciation (Reaktoro/PHREEQC) so mineral precipitation
  reduces porosity → feeds back on the velocity field (dynamic geometry).
- **Tool:** FiPy + proper convection closure, or step to FEniCSx/Firedrake for
  coupled flow–reaction; Reaktoro for per-cell speciation.
- **Emit:** geometry (porosity, precipitation front), scalars (T/pH/H2/CO2), vector
  (velocity → streamlines), fluxes (H2/alkalinity source–sink), provenance.
- **Decision:** settled T/pH/H2 vs (vent flux × ocean mixing) → the Lost-City
  viability region.

### og-01 — Geology → reduced carbon
- **Now:** FiPy Nernst–Planck pH gradient + eQuilibrator ΔG' + lab-calibrated
  kinetics + proton-budget back-pressure; one favorable run + Tutolo arm.
- **Shortfall:** **no phase map** — the plan's #1 ask for Campaign I. We show a run,
  not the carbon-production landscape.
- **Deeper:** sweep (vent pH × H2 flux) [+ T, pressure, CO2 as facets] → net
  carbon-flux field → phase map with contours (no-reaction / transient / sustained),
  favorable + Tutolo/Jackson parameterizations **on the same axes**, and
  experimentally-constrained vs Hadean-extrapolated regions annotated separately.
- **Tool:** the existing composite + the sweep harness (1a).
- **Emit:** phase-map grid (scalar over param space) + the gate region.
- **Decision:** IS the carbon-fixation landscape; bounded favorable region.

### og-02 — Reduced carbon → protometabolism
- **Now:** libRoadRunner rTCA CSTR; a static-ish node graph.
- **Shortfall:** not a *living* flux map; no carbon-fate flow; no persistence/gain
  phase map.
- **Deeper:** living flux map (edge thickness ∝ instantaneous `rr` reaction rate,
  node area ∝ pool, node persistence over time, geological carbon feeding in) +
  carbon-fate Sankey (inorganic C → C1/C2/C3) + persistence/autocatalytic-gain
  phase map over (feed rate × dilution rate × kinetic uncertainty).
- **Tool:** libRoadRunner (per-step `getReactionRates`) + sweep harness.
- **Emit:** fluxes (per-reaction signed rate), pools, network topology, phase grid.
- **Decision:** the gain/persistence region under feed+washout.

### og-03 — Dilution → localized individuals  **(strongest investment)**
- **Now:** analytic accumulation column `enrichment = exp(Pe_acc)` (reduced).
- **Shortfall:** this is the pre-genetic milestone's key claim (does chemistry pass
  through, or does a *localized individual* appear?) and our model is the thinnest.
- **Deeper (four products the plan names):** (i) a real 2-D reaction–transport–
  thermophoresis field in a pore (FiPy/FEniCSx Soret + buoyant convection — resolve
  the actual accumulation; fixes the 2-D convection tuning I earlier punted on), or
  a spatial-stochastic tracer sim (Smoldyn/ReaDDy) for the concentration **movie**
  (washout vs focusing vs persistent hotspots); (ii) a **retention phase diagram**
  (pore geometry × flow/thermal gradient; enrichment + the retention>destruction
  boundary); (iii) a **chemical-individuality plot** — trajectories of *multiple
  pores* through chemical-state space; persistent separation under a shared
  environment = evidence for individuality; (iv) a **coupled comparison** — the
  og-02 network *inside a pore* vs the same network well-mixed, identical feed.
- **Tool:** FiPy/FEniCSx for the field (or Smoldyn for tracers) + libRoadRunner for
  the in-pore network.
- **Emit:** geometry (pore), scalar field (concentration movie), retention phase
  grid, multiple-pore trajectories (entities in chemical-state space).
- **Decision:** the retention phase diagram + the individuality separation.

### og-04 — Mineral compartments → protocells
- **Now:** coarse-grained vesicle-window physico-chemistry; one arm.
- **Shortfall:** no retention–access phase *plane* with 3 regimes; feasibility is
  one arm, not swept; no boundary viewer.
- **Deeper:** sweep the 5-axis feasibility (amphiphile mix × pH × salinity ×
  divalent × T); render the retention–access plane (y=retention, x=access) with
  **three regimes** (too open=washout / viable=individuality+access / too
  closed=starvation); boundary viewer with per-species permeability flux arrows;
  optionally ground the permeability law with a few OpenMM MD points.
- **Tool:** coarse model + sweep harness; OpenMM for a few calibration points.
- **Emit:** boundaries (permeability by species, area), phase-plane grid,
  feasibility hypercube slices.
- **Decision:** the retention–access plane + the viable region.

### og-05 — Environmental → internal bioenergetics
- **Now:** replicator dynamics over (permeability × pump) with a Sojo fitness.
- **Shortfall:** no **energy provenance** — the plan's core ask: what fraction of
  useful disequilibrium is external gradient vs metabolic conversion vs internally
  maintained; no free-energy budget.
- **Deeper:** explicit per-lineage free-energy bookkeeping (J harvested from the
  external pmf, J pump-generated, maintenance+transport costs, net usable work) →
  stacked **provenance trajectory** + free-energy budget bars + gradient-dependence
  curve (persistence as external pmf → 0, comparing internalization strategies).
- **Tool:** the replicator model + an energy-accounting layer.
- **Emit:** provenance (energy carriers, source process, signed), free-energy
  budget, gradient-dependence sweep.
- **Decision:** gradient-dependence curve across strategies.

### og-06 — Chemistry → heredity
- **Now:** libRoadRunner quasispecies error-threshold curve.
- **Shortfall:** no **lineage tree**; nodes carry no chemical phenotype; no
  parent–offspring phenotype distance; replication cost not visualized.
- **Deeper:** an agent-based / stochastic lineage sim — templates replicate with
  fidelity + cost, carry a *phenotype vector* (catalyst composition, permeability,
  network state, resource budget), mutate → a real lineage tree with
  phenotype-colored nodes + parent–offspring phenotype distance + module comparison
  (non-heritable / compositional / peptide-assisted / template / hybrid) on the same
  tree, cost kept visible.
- **Tool:** agent-based substrate (custom Gillespie-with-lineage-tracking, or cells
  in a spatial sim) — libRoadRunner alone can't track trees.
- **Emit:** lineage (parent–child, birth/death, inherited phenotype), entities
  (phenotype vectors), module comparison.
- **Decision:** does ancestry predict functional organization (phenotype distance
  vs persistence/throughput benefit).

### og-07 — Ecology before LUCA  *(not yet built)*
- **Plan:** many compartments; animated metabolite-exchange network;
  cross-feeding / parasitism / cooperation / extinction; persistent phenotype count
  / diversity / coverage / robustness over time; connected-vs-isolated controls.
- **Tool:** agent-based / spatial multi-compartment (extend the og-03 pore-world to
  many cells + exchange) — genuinely agent-based.
- **Emit:** entities (cells, phenotype, position), fluxes (exchange arrows),
  lineage, ecology metrics.

### og-08 — Escape from the vent  *(not yet built)*
- **Plan:** an **ablation movie** — from the mature vent system, progressively
  remove geological support (external pH, H2, mineral interfaces, distance, pore
  confinement); most lineages fail; any that persists = the payoff. Autonomy
  trajectory (persistence vs a "vent-support" scalar, full→zero); minimum-innovation
  matrix (ablate membrane / transport / internal-fixation / heredity one at a time).
- **Tool:** the integrated agent-based system + a systematic ablation sweep.
- **Emit:** ablation grid, autonomy trajectory, surviving lineages in the world.

### og-adv — Generic nonequilibrium control  *(not yet built)*
- **Plan:** a **gate-comparison dashboard** — the vent-specific acceptance gates
  should REJECT a plausible feature-ablated control (a generic nonequilibrium
  chemical system with no vent-specific features).
- **Tool:** run the same gates on a control composite via the sweep harness.
- **Emit:** gate comparison (metric, threshold, result per gate; vent vs control).

---

## 3. Cross-campaign figures (after the per-stage emits exist)

- **Genesis Ladder** — geology→cell progression with each transition's gate state
  (not started / parameter-dependent / passed / failed / challenged). Partly exists.
- **Viability Manifold** — aggregate all sweep grids into a shared parameter-space
  view; the target is the *intersection* of feasible regions that permits the whole
  path from geological disequilibrium to cellular autonomy. Pairwise phase diagrams
  first, then a dimensionality-reduced / classifier-backed boundary.
- **Provenance River** — trace conserved matter + free energy from rock/environment
  reservoirs through H2, reduced carbon, network intermediates, compartments,
  internal gradients, replication. Answers "where did this carbon come from?" and
  "what supplied the free energy?" at any point.

---

## 4. The reusable viewers (Phase D — after models emit rich state)

- Persistent **spatial-field viewer** (one vent world; time scrubber; layer toggles
  for fields/geometry/vectors/entities). Plan P0.
- **Phase-map / parameter-sweep viewer** (the decision view). Plan P0.
- **Flux / lineage network viewer** (mechanism view). Plan P1.
- Migrate the current self-running `Visualization` classes → typed-emit + these
  composing viewers.

---

## 5. Phasing (models-first)

- **Phase A — foundations + hardest model.** (1a) sweep harness; (1b) typed emit
  contract; deepen **og-03** (real pore field + individuality + og-02 coupling);
  retrofit **og-01** as the first phase map.
- **Phase B — deepen built stages.** og-00 real convection; og-02 living flux +
  carbon-fate + gain phase map; og-04 retention-access plane; og-05 energy
  provenance; og-06 lineage tree (agent-based).
- **Phase C — build unbuilt stages.** og-07 ecology (agent-based); og-08 ablation;
  og-adv control.
- **Phase D — viewers + cross-campaign figures.** Spatial-field / phase-map / flux
  viewers; Genesis Ladder, Viability Manifold, Provenance River.

Each phase keeps the stage quality bar (`viva-campaign-stage`): real-tool models,
units-typed ports, filled contracts, pre-registered graded tests, green + clean.

---

## 6. Open decisions (need your call)

1. **Tool stack.** How far up the stack do we go? Options per concern:
   - Coupled flow–reaction (og-00, og-03): stay on FiPy + a convection closure, or
     adopt FEniCSx/Firedrake? (More capable, heavier dependency/build.)
   - Spatial-stochastic (og-03 tracers, og-07 ecology): Smoldyn / ReaDDy, or an
     agent-based framework (Mesa-style)?
   - Lineages (og-06/07/08): custom Gillespie+tree, or cells-in-a-spatial-sim?
   - Permeability (og-04): ground with a few OpenMM MD points, or keep calibrated?
2. **Compute budget for sweeps.** Phase maps multiply run cost (N×M per stage).
   Mac-mini Ray parallel sweeps are the natural home — OK to lean on that, and what
   grid resolution is "enough" for a decision figure?
3. **Reduced-model boundaries.** Where is a labeled coarse model acceptable vs
   where must we go full mechanistic? (og-04/05/06 especially.)
4. **Framework placement.** The sweep harness + typed emit contract: in
   viva-genesis (workspace-local) first, or designed for the workbench/pbg so other
   campaigns inherit them?
5. **Scope of this pass.** All of Phases A–D, or Phase A + B (finish the pre-genetic
   milestone og-00→03 to the full standard) as the first deliverable, then reassess?
