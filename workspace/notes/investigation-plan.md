# Investigation plan — origins-of-life vent campaign

The campaign (`campaign-overview.md`) rendered as a Vivarium **investigation**: a
DAG of member **studies**, each a knowledge-producing operation with a question,
proposed mechanisms, proposed models/methods, a **contract** (the ports +
conservation invariants its composite must satisfy), and **success criteria**
(behavior tests derived from the acceptance gates + discriminating experiments).

This is the design; it scaffolds to `investigations/origins-of-life-vent/` with
one `study.yaml` per node (canonical shapes in `.pbg/schemas/`). Nothing here is
a claim that any stage already runs — every study opens at **Design** phase.

---

## Investigation: `origins-of-life-vent`

- **Overarching question.** Can a physically plausible early-Earth hydrothermal
  system generate and sustain localized, increasingly autonomous chemical
  organizations — without inserting metabolism, membranes, or heredity by
  assumption?
- **Hypothesis (across the whole sequence).** Under parameter ranges consistent
  with field observations + laboratory experiments, a serpentinization-fed,
  spatially resolved vent–ocean interface crosses, in order, thresholds for
  sustained carbon fixation → network persistence → concentration/individuality
  → compartmentation → internalized energy → heritable organization — and each
  threshold is *falsifiable*, with identifiable parameter regions where it fails.
- **Verdict framing (`executive.verdict_status`).** `planning` → advances to
  `in-progress` as `og-00`/`og-01` run; the headline verdict a reviewer lands on
  rolls up member-study confidence.
- **Competing frameworks** (`competing_frameworks`, for rigor): classical
  alkaline-vent (Russell/Martin/Lane/Sojo) vs. the 2026 unfavorable
  reassessment (Tutolo; Jackson) vs. shallow-vent / terrestrial-geothermal /
  cyanosulfidic alternatives. The campaign adjudicates; it does not assume.
- **Adversarial coverage** (rigor requirement): `og-adv-generic-nonequilibrium`
  — a generic nonequilibrium / non-vent control that SHOULD fail the
  vent-specific gates. If it passes them, the gates aren't vent-specific.

### The investigation graph (DAG)

```
og-00  vent reactor baseline  (Campaign 0 — reproduce the physical analog)
  │
  ▼
og-01  geology → reduced carbon  (Campaign I)              ── first publication
  │                                                            milestone target
  ├──────────────► og-adv-generic-nonequilibrium (adversarial; refutes)
  ▼
og-02  reduced carbon → protometabolism  (Campaign II)
  │
  ▼
og-03  dilution → localized individuals  (Campaign III)   ◄── milestone ends here
  │                                                           (pre-genetic)
  ▼
og-04  mineral compartments → protocells  (Campaign IV)
  │
  ▼
og-05  environmental → internal bioenergetics  (Campaign V)
  │
  ▼
og-06  chemistry → heredity  (Campaign VI)   [branch point — not RNA by default]
  │
  ▼
og-07  ecology before LUCA  (Campaign VII)
  │
  ▼
og-08  escape from the vent  (Campaign VIII)
```

Edges are `parent_studies` with `condition: tests-passed`; `relation: leads-to`
(solid) except the adversarial edge (`refutes`, dashed). The **first
publication milestone** is `og-00 → og-03`: a dynamically precipitating, spatially
resolved interface that generates and *retains* a persistent protometabolic
carbon flux — intentionally pre-genetic.

### Shared contract vocabulary (every study inherits)

From `architecture.md` integration contracts — each study's composite must carry
these ports (typed, united) and satisfy these predicate invariants:

- **Ports / stores:** `environment{T,P,flow,potential}`, `aqueous{species amount
  by voxel}`, `minerals{phase abundance, surface area, porosity}`,
  `interfaces{area, permeability, surface charge}`, plus stage-specific stores.
- **Conservation predicates (contract conditions):**
  `mass/elements` (residuals for C,H,O,N,P,S,Fe,Ni ≈ 0),
  `charge/electrons` (electroneutrality or Poisson closure),
  `energy` (thermodynamic directionality; log work/heat/free-energy),
  `spatial transfer` (fluxes conservative across cell + compartment boundaries),
  `reproducibility` (solver/db/param-source/seed/scenario recorded).

Each study below names the **binding** ports + invariants it adds on top.

---

## og-00 · Vent reactor baseline  — Campaign 0

- **Phase:** Design → (near-term build target). **Parents:** none. **Rigor role:** baseline / negative-control host.
- **Question.** Can a Lost City–like, serpentinization-fed vent–ocean interface
  reproduce observed fluid mixing, heat transport, mineral precipitation and
  H2/alkalinity delivery under field-constrained conditions — with no
  origin-of-life claim? 
- **Hypothesis.** A 1D/2D porous-wall reactor with prescribed boundary fluxes
  reproduces published Lost City ranges (T, pH, H2, DIC) and qualitative
  precipitation trends while conserving mass + charge.
- **Proposed mechanisms (modules).** A (serpentinization as boundary flux),
  B (flow, mixing, FeS/carbonate precipitation, evolving porosity).
- **Proposed models/methods.** PHREEQC/Reaktoro (speciation + mineral kinetics);
  FiPy finite-volume advection–diffusion–reaction; prescribed vent source.
- **Contract.** ports: `environment{T,P,flow}`, `aqueous{H2,DIC,major ions}`,
  `minerals{serpentine,brucite,magnetite,FeS,carbonate; porosity}`. Binding
  invariants: **mass/elements, charge, spatial-flux conservation**; energy
  logged (heat).
- **Success criteria (behavior_tests).**
  - `vent-T-pH-in-lostcity-range` — measure outlet T, pH; pass_if T∈[40,91]°C and pH∈[9.0,10.8] (anchor: `kelley2001offaxis`,`ludwig2006formation`).
  - `h2-alkalinity-sustained` — measure steady H2 + alkalinity flux; pass_if > 0 and stable over residence time (`schwander2023serpentinization`).
  - `mass-charge-conserved` — residuals for C,H,O,Fe,S and net charge; pass_if |residual| < tolerance (negative control: perturb a flux → residual must break).
- **Literature anchors.** Lost City T/pH/longevity (`kelley2001offaxis`,`fruhgreen2003thirtythousand`,`ludwig2006formation`).

## og-01 · Geology → reduced carbon  — Campaign I

- **Phase:** Design. **Parents:** og-00. **Rigor role:** primary; reproduction gate.
- **Question.** Which combinations of T, pH, pressure, H2, CO2 and mineralogy
  generate *sustained net organic-carbon flux* across the interface — reproducing
  Hudson/Preiner/Altair regimes before any extrapolation?
- **Hypothesis.** Over Fe/Ni/S surfaces and across the pH gradient, H2-driven CO2
  reduction yields formate/acetate/pyruvate at rates matching lab calibration
  within a bounded (T,pH,H2,pressure) region; outside it, net flux → 0.
- **Proposed mechanisms.** C (pH-gradient electrochemistry), D (mineral-catalyzed
  fixation). Encode `pH(T,P,ionic_strength)`, not lab pH as a constant.
- **Proposed models/methods.** Nernst–Planck–Poisson (electroneutral) on
  FiPy/FEniCSx; Cantera/custom heterogeneous kinetics; eQuilibrator feasibility;
  Bayesian calibration (PyMC) to Preiner/Hudson/Altair.
- **Contract.** adds ports `electrical{potential, current density}`,
  `aqueous{formate,acetate,pyruvate,methanol}`. Binding invariants:
  **charge/electron bookkeeping** (reaction-current coupling obeys charge
  conservation), **energy** (affinity vs. kinetically accessible electron
  transfer kept separate), mass.
- **Success criteria.**
  - `co2-reduction-reproduces-preiner` — measure product distribution at 100 °C over greigite/magnetite/awaruite; pass_if within lab ranges (formate≲200 mM, acetate≲100 µM, pyruvate≲10 µM) as *rates/yields*, not env. conc. (anchor `preiner2020hydrogen`).
  - `ph-gradient-drives-formate` — measure formate vs Δ-pH across Fe(Ni)S with controls (remove gradient / H2 / precipitate → product must vanish) (`hudson2020co2`).
  - `net-carbon-flux-region-mapped` — measure sustained net organic-C flux over (T,pH,H2,P); pass_if a nonzero region exists AND a zero region is identified.
- **Discriminating test.** `in-situ-ph-correction`: does a usable gradient persist at in-situ T/P, or collapse (Tutolo/Jackson)? observable: Δ-pH, proton-motive contribution, fixation rate.

## og-02 · Reduced carbon → protometabolism  — Campaign II

- **Phase:** Design. **Parents:** og-01. **Rigor role:** primary.
- **Question.** Under continuous feed + washout, do reaction subnetworks become
  self-reinforcing — persistent cycles, flux amplification, product reuse,
  autocatalytic motifs — without imposed product accumulation?
- **Hypothesis.** A curated graph (formate/acetate/pyruvate/glyoxylate + rTCA
  fragments) seeded with Muchowska/Moran edges sustains nonzero throughput and
  at least one autocatalytic motif within a feasible resource budget.
- **Proposed mechanisms.** E (network formation), D (surface chemistry).
- **Proposed models/methods.** SBML + libRoadRunner/Tellurium or COPASI;
  SciPy solve_ivp; element-balance + thermodynamic-consistency checks before
  kinetic fitting; GillesPy2 for low-copy stochastic regimes.
- **Contract.** adds ports `aqueous{organic network state}`,
  `organic{reaction-network state}`. Binding invariants: **mass/elements** (every
  edge element-balanced), **energy** (thermodynamic directionality per edge),
  reproducibility. No steady-state FBA substituting for kinetics.
- **Success criteria.**
  - `sustained-carbon-throughput` — measure net throughput under feed+washout; pass_if > 0 without imposed accumulation (Gate II).
  - `autocatalytic-gain-present` — measure cycle flux + autocatalytic gain; pass_if ≥ 1 reinforcing motif (`muchowska2017metals`,`muchowska2019synthesis`).
  - `network-closure-vs-oneoff` — pass_if products connect into a network, not disconnected one-offs.

## og-03 · Dilution → localized individuals  — Campaign III  *(milestone end)*

- **Phase:** Design. **Parents:** og-02. **Rigor role:** primary; milestone gate.
- **Question.** When do retention time + concentration cross the thresholds for
  network persistence, as pore morphology evolves via precipitation/dissolution?
- **Hypothesis.** Thermophoresis + convection + adsorption in evolving pores
  raise local concentration enough that synthesis outruns hydrolysis/leakage in a
  bounded geometry region; elsewhere washout dominates.
- **Proposed mechanisms.** F (transport/concentration/retention), B (evolving pores).
- **Proposed models/methods.** FiPy finite-volume with Soret term; OpenPNM/PoreSpy
  pore geometry; reproduce Baaske enrichment; Damköhler/Péclet/Soret scaling.
- **Contract.** adds ports `geometry{pore network, surfaces, interface areas}`,
  `environment{T-field, flow}`. Binding invariants: **spatial-flux conservation**
  (advection/diffusion/thermodiffusion fluxes conservative), mass.
- **Success criteria.**
  - `thermophoretic-enrichment-reproduces-baaske` — measure enrichment vs pore geometry; pass_if trend matches (>10⁸-fold in favorable geometry) (`baaske2007extreme`).
  - `retention-beats-destruction` — measure residence time vs synthesis timescale; pass_if a region with net accumulation exists (Gate III), AND map where hydrolysis/leakage defeat synthesis.
  - `network-persists-in-pore` — couple og-02 network into the pore; pass_if persistence improves vs well-mixed.

## og-04 · Mineral compartments → protocells  — Campaign IV

- **Phase:** Design. **Parents:** og-03. **Rigor role:** supporting.
- **Question.** Do mixed-amphiphile organic boundaries enhance persistence without
  cutting the system off from geochemical energy?
- **Hypothesis.** Over a salt/pH/divalent-cation/T window, vesicles form and
  selectively retain while remaining permeable enough to exploit the external
  gradient — a non-empty "individuality vs. access" region exists.
- **Proposed mechanisms.** G (amphiphiles/protocells).
- **Proposed models/methods.** custom coarse-grained membrane kinetics;
  Smoldyn/ReaDDy spatial stochastic; OpenMM/LAMMPS to calibrate permeability laws.
- **Contract.** adds ports `interfaces{area, permeability, surface charge}`,
  `compartments{volume, membrane, internal species}`. Binding invariants: mass,
  **spatial-flux** across compartment boundaries, energy (membrane maintenance cost).
- **Success criteria.**
  - `vesicles-form-in-window` — measure vesicle formation vs amphiphile mix/pH/salts/T; pass_if matches Jordan feasibility map (`jordan2019promotion`).
  - `retention-without-isolation` — measure chemical retention AND external-gradient access; pass_if both nonzero (Gate III/IV).
  - `membrane-transition-robust` — discriminating: do salts/T/pH destroy or over-seal membranes? observable: vesicle survival, permeability, resource flux.

## og-05 · Environmental → internal bioenergetics  — Campaign V

- **Phase:** Design. **Parents:** og-04. **Rigor role:** supporting.
- **Question.** Can selection move from externally imposed gradients toward
  internally maintained electrochemical states (catalytic ion transport → pumping)?
- **Hypothesis.** When membrane permeability + Na+/H+ coupling + catalyst
  efficiency vary under selection, systems with increasing internal gradient
  generation win on carbon/energy throughput + persistence — but only if membranes
  stay sufficiently leaky (Sojo constraint).
- **Proposed mechanisms.** H (bioenergetic internalization).
- **Proposed models/methods.** evolutionary control loop over membrane params;
  reward = throughput + persistence; Sojo leaky-membrane model as baseline.
- **Contract.** adds ports `electrical{internal potentials}`, `lineage{fitness
  observables}`. Binding invariants: energy (quantify reduced env-dependence +
  membrane-maintenance cost), charge, reproducibility (seeds/scenarios).
- **Success criteria.**
  - `reduced-gradient-dependence` — measure survival as external gradient is lowered; pass_if internalizing lineages persist longer (Gate IV).
  - `energy-cost-accounted` — measure membrane-maintenance energy vs benefit; pass_if net-positive region exists.

## og-06 · Chemistry → heredity  — Campaign VI  *(branch point)*

- **Phase:** Design. **Parents:** og-05. **Rigor role:** primary (weakest link — hypothesis-comparative).
- **Question.** Does inherited state improve persistence/throughput — comparing
  RNA-like, peptide-assisted, compositional and hybrid heredity — rather than
  template replication in isolation? (Do NOT presume RNA.)
- **Hypothesis.** At least one heredity module raises lineage persistence +
  information retention above its non-heritable control under a feasible resource
  budget; the winner is not assumed a priori.
- **Proposed mechanisms.** J (polymers/information/heredity) — as competing modules.
- **Proposed models/methods.** GillesPy2/StochPy SSA; rule-based chemistry
  (BioNetGen/NFsim) for sequence combinatorics; separate catalyst discovery from
  inheritance; explicit fidelity/cost/competition.
- **Contract.** adds ports `lineage{catalysts, sequences, ancestry}`,
  `organic{polymer length distributions}`. Binding invariants: mass (monomer
  budget), **reproducibility**, energy (chemical cost of copying).
- **Success criteria.**
  - `inheritance-beats-noninheritance` — measure persistence/throughput with vs without inherited state; pass_if heritable > control (Gate V).
  - `heredity-modules-compared` — ≥2 heredity modules evaluated head-to-head; pass_if ranking is evidence-based, not assumed.
  - `replication-feasible-budget` — pass_if demonstrated under chemically feasible resource budgets, not idealized.

## og-07 · Ecology before LUCA  — Campaign VII

- **Phase:** Design. **Parents:** og-06. **Rigor role:** supporting.
- **Question.** In connected pore networks with cross-feeding, parasitism,
  cooperation and horizontal exchange, what emergent capabilities arise — compared
  to ancestral reconstructions, without assuming LUCA is primitive?
- **Hypothesis.** Heterogeneous populations develop metabolic diversity +
  cross-feeding + robustness that single compartments do not; emergent capability
  set overlaps the anaerobic H2/CO2/FeS LUCA reconstruction as a boundary.
- **Proposed mechanisms.** ecology (populations, evolution), LUCA boundary.
- **Proposed models/methods.** Vivarium multi-agent composites over shared spatial
  fields; COBRApy for late-stage genome-scale benchmarks; evolutionary algorithms.
- **Contract.** adds ports `lineage{ancestry, metabolic diversity}`,
  `geometry{connected pore network}`. Binding invariants: mass/energy across
  agents, spatial-flux, reproducibility.
- **Success criteria.**
  - `cross-feeding-robustness` — measure diversity + robustness vs single-compartment; pass_if higher (Gate VI).
  - `luca-capability-overlap` — compare emergent capabilities to `weiss2016physiology`/`moody2024nature` as a *constraint*, not a target.

## og-08 · Escape from the vent  — Campaign VIII

- **Phase:** Design. **Parents:** og-07. **Rigor role:** supporting; autonomy gate.
- **Question.** What is the minimum set of innovations required for autonomous
  persistence away from the geological reactor, as environmental support is relaxed?
- **Hypothesis.** A bounded innovation set (internal energy conversion + resource
  import + heredity) allows persistence as gradient strength/mineral access/feed
  are reduced; below it, systems stay obligately vent-tied.
- **Proposed mechanisms.** all (integrated); autonomy readout.
- **Proposed models/methods.** multi-agent composites with relaxed boundaries;
  ablation sweeps over gradient/mineral/feed; population genetics.
- **Contract.** integrates all prior ports. Binding invariants: energy (autonomy =
  internalized conversion), mass, reproducibility.
- **Success criteria.**
  - `survival-off-gradient` — measure survival as external gradient → 0; pass_if ≥1 lineage persists (Gate "Autonomy").
  - `minimum-innovation-set` — identify the smallest ablation-robust innovation set.

## og-adv-generic-nonequilibrium · Adversarial control

- **Phase:** Design. **Parents:** og-02 (`relation: refutes`). **Rigor role:** `kind: adversarial`.
- **Question.** Does a *generic* nonequilibrium chemical system with no
  vent-specific features (no sustained H2, no Fe/Ni/S catalytic interface, no pore
  concentration) pass the vent-specific gates? It SHOULD NOT.
- **Hypothesis (adversarial).** The og-01/og-02/og-03 gates REJECT this control;
  if they pass it, the gates are measuring generic nonequilibrium chemistry, not
  the vent mechanism (Campaign VI falsification; `sutherland2017opinion` framing).
- **Proposed models/methods.** same composites as og-01…03 with vent features
  disabled (flat gradient, inert surface, well-mixed); run the same behavior_tests.
- **Success criteria (pass by REJECTING).**
  - `gates-reject-generic` — run og-01..03 behavior_tests on the control; pass_if they FAIL (no sustained net flux / no persistence / no enrichment).
  - `vent-specificity-demonstrated` — pass_if the vent arm passes the same tests the control fails.

---

## Scaffolding map (next step)

Each node above → `investigations/origins-of-life-vent/studies/<slug>/study.yaml`
(`schema_version: 4`, `phase: Design`, `investigation: origins-of-life-vent`
back-ref) carrying: `question`, `hypothesis`, `objective`, `description`,
`proposed_mechanisms`, `proposed_models_methods`, `contract`, `behavior_tests`
(the success criteria above), `literature_anchors`, `parent_studies` (the DAG),
`key_assumptions`. The investigation `investigation.yaml` carries `executive`,
`question`, `hypothesis`, `scientific_argument`, `competing_frameworks`,
`at_a_glance` (one line per study), `studies[]` (declared order above), and
`acceptance_criteria[]` (the gate test per study). Studies reference real
registered composites once the module processes are built (`/viva-expert`);
until then they stay at Design with `requires_simulation: true` tests.
