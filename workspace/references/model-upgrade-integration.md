# viva-genesis — Model Upgrade and Implementation Plan: integration architecture

The campaign's **build target** from 2026-10-14. It encodes the expert's *Model
Upgrade and Implementation Plan* (source:
`workspace/references/expert/viva-genesis-model-upgrade-and-implementation-plan.pdf`,
registered in `workspace.yaml.expert_docs`) on top of the existing campaign and
on top of the earlier *Full Modeling Plan* integration design
(`full-modeling-plan-integration.md`, which this document **supersedes as the
build target** and keeps as the detailed design for structural rewrites, layer
composites and the spatial-transport face — sections referenced below as
"FMP §n"). Like that document it names real files, classes and tests, says what
exists versus what is planned, and is kept executable rather than aspirational.

Everything marked **built** below was implemented, tested and run on the
canonical stack (`process-bigraph 1.9.1`, `bigraph-schema 1.8.1`, FiPy 4,
phreeqpython) on 2026-10-14; everything marked **planned** is a proposal with
its decision recorded in `investigation.yaml`.

## 0. Where the campaign stands, and what the plan changes

**Current state (verified).** All fourteen member studies of
`origins-of-life-vent` (og-00..08, og-adv, og-res-nitrogen, og-res-phosphorus,
og-energy, og-growth) have `simulation_status: ran` and `gate_status: passed`.
The spatial-transport face carries two real solvers: FiPy (pure Python, the
live default behind every graded gate and sweep, uv `.venv`) and FEniCS/dolfinx
(merged high-fidelity cross-check run under viva-fenics's pixi env; the
head-to-head is recorded in `spatial-transport-solver-comparison.md`: og-00
outlet T agrees within 0.3 %, pH exactly; og-03's >10⁸ enrichment is a
reduced-model extrapolation above the resolvable Péclet).

**The plan's central objective.** Move from *"this mechanism can pass a gate"*
to: *given empirical constraints and competing mechanistic models, what is the
probability, parameter domain, causal mechanism and experimentally testable
prediction for each transition?* A stage is strong only when its conclusion is
not a direct consequence of how the model was encoded.

**What that changes in the codebase.** Three things, all additive:

| Plan element | Encoded as | Status |
|---|---|---|
| Three quantities per transition (Feasibility / Robustness / Discrimination) + evidence tiers | `viva_genesis/uq/report.py` — `TransitionReport`, `EvidenceTier` (+ permitted language), `decision_discipline()` | **built** |
| Canonical biological interfaces; model class as a categorical factor | `viva_genesis/schemas.py` (the `vg_*` types, registered by `build_core`), `viva_genesis/models.py` (faces, registry, `axis()`), `sweep_grid` string axes, `uq/ensemble.py` | **built** (two faces with real alternative classes; migration of the remaining interfaces planned per phase) |
| vg-data provenance layer | `viva_genesis/provenance.py` + `viva_genesis/data/vg_data/*.yaml` | **built** (first package: `vent_environment`) |
| Campaign UQ layer (calibration, Morris→Sobol, structural ensembles, propagation, verification, nulls, out-of-sample, pre-registered gates) | `viva_genesis/uq/` + `viva_genesis/ledger.py` | **built** as a working core (see §4 for what is thin) |
| Phase 1 — environmental calibration | `composites/geochemical_world.py`, `uq/environment_calibration.py`, study `og-cal-vent-environment` | **built and run** (§6) |
| Phases 2–9 | §7 roadmap, `investigation.yaml.guidelines.roadmap_phases` + `decisions_needed` | **planned** |

## 1. The scientific standard, as code

### 1.1 The three quantities

For every major transition a study reports (`viva_genesis.uq.report.TransitionReport`):

- **Feasibility** — `Feasibility(feasible, n_admissible, n_supporting, example,
  admissibility)`: is there at least one *physically admissible*
  parameterization (one inside the conditioning set, stated in `admissibility`)
  that supports the transition? The `example` is a concrete draw a reader can
  re-run.
- **Robustness** — `Robustness(fraction, by_class, structure_agreement,
  structure_uncertainty, n_posterior, n_prior, binding_observation)`: what
  fraction of the *empirically supported* parameter distribution (the posterior
  after conditioning, not the swept grid) supports it, per model class; and the
  fraction of that distribution on which all model classes agree. `1 -
  structure_agreement` is model-form uncertainty, reported separately from
  parameter uncertainty — the plan's "sweep bounds can strongly determine
  apparent robustness" is answered by conditioning first.
- **Discrimination** — `Discrimination(alternatives, discriminating,
  non_discriminating, proposed_perturbations)`: which readouts separate the
  favored class from its alternatives on *identical* parameter draws
  (`uq.ensemble.paired_class_difference`, standardised paired difference `d`),
  and which perturbations would.

### 1.2 Evidence tiers and permitted language

`EvidenceTier` fixes the sentence stem a finding may use:

| Tier | Meaning | Language (`tier.language`) |
|---|---|---|
| `reproduction` | reproduces an external measured / established result | "reproduces / validates" |
| `mechanistic_prediction` | a parameterized model makes a new quantitative prediction | "predicts under stated assumptions" |
| `conceptual_demonstration` | a reduced model shows an organizational principle is possible | "demonstrates in a coarse-grained model" |

Re-reading the fourteen studies against the tiers (recorded here, not yet
written into their YAML — the text owner should do that): og-00 is
*reproduction* (Lost City window, now with a conditioned posterior, §6); og-01
is *reproduction* for the Preiner/Hudson yields and *mechanistic prediction* for
the Tutolo collapse; og-02, og-03, og-04, og-res-N, og-res-P, og-energy,
og-growth are *mechanistic predictions* whose networks / windows were curated
in; og-05, og-06, og-07, og-08 are *conceptual demonstrations* (capability
vectors, agent-based lineages, a reduced budget model); og-adv is the null
control the plan asks every stage to have.

### 1.3 Decision discipline, as an audit

`uq.report.decision_discipline(report)` returns the plan's section-14 rules as
violations: a headline that depends on a numerically unvalidated regime (ledger
not OK), a conservation residual above tolerance, a claim of necessity when the
model classes disagree on most of the posterior, a *reproduction* tier without a
stated conditioning set. The Phase-1 runner writes its result beside the report
(`artifacts/vent_environment_report.json: decision_discipline`); the intended
workflow is that a study's `report.verdict` may not move forward while that list
is non-empty.

### 1.4 Pre-registered gates

Already the campaign's practice (`study.yaml.preregistered`); the UQ layer adds
the rule that the *posterior* gate of a phase (e.g. `posterior-viable-vent-
fraction`) is declared with its threshold **before** the ensemble is run —
og-cal-vent-environment's gates were written while its ensemble was computing.

## 2. Canonical interfaces and the model class as an experimental factor

### 2.1 `viva_genesis/schemas.py` — built

- `ATOMS`: units-typed leaves (`vg_concentration` molar, `vg_temperature` kelvin
  273–673, `vg_ph`, `vg_fraction`, `vg_potential` volt, `vg_current_density`,
  `vg_conductivity` siemens/meter, `vg_free_energy` kJ/mol, `vg_power`,
  `vg_energy_amount` joule, `vg_length`, `vg_area`, `vg_volume`, `vg_velocity`,
  `vg_permeability`, `vg_time`, `vg_per_second`, `vg_tension`,
  `vg_information` bit, `vg_count`, `vg_id`). The unit strings are exactly the
  ones the 24 existing processes declare (tested), so migration is a rename.
  bigraph-schema 1.8.1 keeps `_units` but drops `_min/_max` on realised
  `Float`s; the bounds therefore live as contract metadata (`schemas.bounds`)
  and mirror the studies' `contract.face` bounds.
- `SCHEMAS`: the eight canonical types of the plan — `vg_environment`,
  `vg_minerals`, `vg_molecules` (**one** dissolved pool keyed by species),
  `vg_energy`, `vg_boundary`, `vg_individual` (with `heredity:
  maybe[vg_heredity]`, absent until attached), `vg_heredity`, `vg_lineage`.
  Registered by `build_core()` (`register_canonical_types`, idempotent).
- `PORT_TO_CANONICAL`: every existing port name → `schema.field`;
  `models.canonical_coverage(face)` asserts a face has no port outside the
  canonical vocabulary (test `test_every_face_port_is_canonical`). Diagnostics
  (`charge_imbalance`, `flux_divergence_residual`) map to the `ledger.*`
  namespace, which is not biology but is required by the numerical-verification
  method.

### 2.2 `viva_genesis/models.py` — built

Faces are port contracts (required / optional inputs and outputs); interfaces
map model-class *names* to `local:` addresses; `resolve_checked` fails loudly
at build time. Interfaces with real alternative classes today:

| Interface | Classes (all registered, face-checked) | What the class axis means |
|---|---|---|
| `serpentinization` | `phreeqc` (real IPhreeqc peridotite speciation), `reduced` (tuned Gaussian source; no speciation — its endmember pH is a declared hypothetical) | geochemistry engine; Reaktoro / PFLOTRAN register here when added (Phase 1 follow-up) |
| `spatial_transport` | `fipy` (Darcy–Boussinesq convecting wall), `fipy_uniform_upflow` (same FVM solve, buoyancy = 0: prescribed upflow), `fenics` (dolfinx FEM, pixi) | whether the vent wall convects is a *structural* assumption, so it is a class, not a parameter |
| `localization` | `fipy`, `fenics`, `surrogate` | FMP §4.5–4.6 |

`models.axis("spatial_transport")` returns `{"model_spatial_transport":
[...]}`; `sweep_grid` accepts string-valued axes and `SweepResult.slice_along`
returns the per-class sub-surface; `models.model_parameters(...)` declares the
`model_<interface>` knobs uniformly on a generator so the workbench renders
them as string parameters. Study YAML selects a class the same way it selects
a parameter (`baseline[].params.model_spatial_transport`).

### 2.3 Migration rule for the remaining interfaces (planned, per phase)

The FMP §1.4 port table stays the migration map. Each phase below adds its
interface to `INTERFACES` **with at least two real classes** (the existing
process + the upgraded one) before any study sweeps it; a stage's gates are
then re-run per class with `uq.ensemble.pass_fraction` /
`structure_agreement`, and the finding reports the intersection region
(parameter-robust) and the union-minus-intersection (structure-sensitive)
separately. Never one class alone: a face with one class is a port list, not an
experiment.

## 3. vg-data — the provenance layer

`viva_genesis/provenance.py` — built.

- `Parameter`: `id, units, provenance ∈ {measured, calibrated, inferred,
  extrapolated, hypothetical}, value and/or distribution (fixed | uniform |
  loguniform | normal | lognormal | triangular), context, sources (bibkeys),
  consumed_by (process config key), how_to_use`. `sample()` / `nominal()` /
  `bounds()`.
- `ParameterPackage`: a named, versioned YAML file (`viva_genesis/data/vg_data/
  <name>.yaml`) with `parameters`, `observations` (conditioning windows) and
  `downstream_requirements` (what the next stage needs). `load / sample /
  to_config / audit / check_bib`.
- `audit()` is the plan's one-glance honesty indicator: counts per class, the
  hypothetical and extrapolated ids, the weakest three, and the *unsourced*
  non-hypothetical ones. The first package deliberately leaves the Hadean DIC
  proxy flagged (extrapolated, unsourced) rather than hiding it.
- `audit_config_schema()` checks a process `config_schema` for `_provenance`
  annotations; `ConservationLedgerProcess` declares them, the legacy processes
  do not yet (advisory; required for every new canonical class).
- The older `workspace/datasets/parameter-registry.yaml` vocabulary (FIELD,
  LAB-DIRECT, LAB-ANALOG, MODEL, RECONSTRUCTION, HYPOTHESIS) maps onto the five
  plan classes (`LEGACY_CLASS_MAP`), so the dossier's §3 table can be imported
  as a package without re-typing its provenance.

**Packages (built / planned):** `vent_environment` (built, §6);
`electrochemical_interface` (Phase 2: Altair 2025 / Panico 2026 currents,
Ni/Fe ratios, mineral conductivity); `reaction_universe` (Phase 3: Wołos 2020
rule set, eQuilibrator ΔG′, catalyst constraints); `pore_physics` (Phase 4:
Baaske / Mast geometry, species Soret coefficients); `amphiphile_assembly`
(Phase 5: Jordan 2019 phase data, Lu 2024 osmotic growth); `energy_currencies`
(Phase 6); `inheritance_budgets` (Phase 7); `cnp_resources` (cross-cutting:
the N / P hydrothermal datasets already proposed in `proposed_inputs`).

## 4. The campaign UQ layer

`viva_genesis/uq/` — built. Mapping of the plan's section-11 methods:

| Method | Module / function | State |
|---|---|---|
| Bayesian calibration | `calibration.py`: `Observation` windows, `abc_rejection` (uniform likelihood on windows — the worked example), `gaussian_weights` (importance), `posterior_summary`, `Calibrator` protocol for a PyMC/NumPyro backend | ABC + importance built; MCMC backend planned when a stage has a likelihood model rather than population windows |
| Global sensitivity | `sensitivity.py`: `morris` (elementary effects, `r` trajectories), `sobol` (Saltelli + Jansen, bootstrap CIs); both on NumPy only (SALib not required), tested against Ishigami analytic indices | built |
| Structural model ensembles | `ensemble.py`: `pass_fraction`, `structure_agreement`, `decision_envelope`, `paired_class_difference` on a `SweepResult` with a class axis or on `{class: mask}` | built |
| Uncertainty propagation | `sampling.py`: `lhs_unit`, `sample_package` (LHS over the package's free parameters), `draws_to_configs` | built |
| Numerical verification | `viva_genesis/ledger.py` (`ConservationLedgerProcess`), `spatial-transport-solver-comparison.md` (cross-solver), `compare_spatial_transport.py` (manufactured solution, convergence orders) | ledger + cross-solver built; mesh/time-step convergence gate per stage planned (§7, Phase 4) |
| Null and adversarial models | og-adv (environment ablation) exists; `reaction_universe` null networks planned (Phase 3) | partial |
| Out-of-sample prediction | `calibration.py` conditions on named observations, so holding one out is `package_observations(...)` minus one | mechanism built; first held-out test planned in Phase 1 follow-up (hold out H2, predict it) |
| Pre-registered gates | `study.yaml.preregistered` + §1.4 rule | practice |

**What is thin and says so.** The Bayesian interface stops at ABC/importance;
Sobol is implemented but has not been run on the real world (Morris has —
§6); null networks are not yet generated; the ledger covers the vent world's
H2 / alkalinity / heat / charge / flux balance, not yet C/N/P element totals or
rewrite residuals (FMP §5.3).

## 5. Numerical verification: the ledger

`ConservationLedgerProcess` (built) runs beside the world processes and, each
tick, integrates the published source *rates* and compares them with the
accumulated *pools*. Because every process returns additive deltas to the same
store, the two must agree bit-for-bit — and they do (`H2_residual == 0.0`,
`energy_residual == 0.0` on every tick, all classes; test
`test_world_runs_and_ledger_is_exact` also checks `H2_in[i] == H2[i-1]`
exactly). It also tracks worst-case PHREEQC charge imbalance (0 throughout),
the FVM flux-divergence residual, a heat-directionality witness
(serpentinization never absorbs heat) and publishes `ledger_ok`. The og-00
contract's four invariants (`mass_balance`, `charge_neutrality`,
`spatial_flux_conservation`, `energy_directionality`) are now all
machine-witnessed; previously `energy_directionality` was declared but not
computed.

## 6. Phase 1 — environmental calibration, worked concretely

### 6.1 What was built

- `composites/geochemical_world.py` — og-00's real PHREEQC + FiPy vent as a
  layer generator behind the two faces, with the ledger, and with its free
  parameters bound to the `vent_environment` package (`flow_velocity`,
  `olivine_rate`, `pyroxene_fraction`, `fe_fraction`,
  `heat_to_fluid_fraction`, `fluid_dic`; `nx`). Registered as a composite
  (`viva_genesis.composites.geochemical_world.geochemical_world`).
- `uq/environment_calibration.py` — the pipeline: LHS prior → ensemble per
  model class (serial; the PHREEQC extension does not survive a process pool) →
  ABC conditioning on the Lost City windows (outlet T 40–91 °C, pH 9.0–10.8,
  dissolved H2 1–15 mmol/kg; MARHYS 4.0 **pending**) → posterior-predictive
  fraction meeting og-01's requirements (H2 ≥ 1 mM at the interface, pH
  gradient ≥ 3 units against pH 6.0, T ≤ 100 °C) → `TransitionReport` with
  the provenance audit, the ledger verification and a Morris screening.
- Study `og-cal-vent-environment` (new, alongside og-00 — og-00's passing
  study.yaml is untouched): canonical run of `geochemical_world` graded on the
  ledger readouts and the dissolved-H2 window, plus the ensemble artifacts
  (`artifacts/vent_environment_ensemble.json`, `vent_environment_report.json`)
  rendered by `VentEnvironmentPosterior` (`viva_genesis/viz_uq.py`).

### 6.2 Results (48 LHS draws × 2 transport classes, 30 steps, nx = 20, seed 0)

See §6.2 of `og-cal-vent-environment/study.yaml` for the graded numbers; the
summary recorded here is copied from `artifacts/vent_environment_report.json`
after the run:

| Quantity | Value | Reading |
|---|---|---|
| **Feasibility** | 6 / 48 prior draws consistent with all three Lost City windows; 6 / 6 of those meet og-01's requirements | at least one physically admissible, observation-consistent vent state feeds carbon fixation (example: flow 3.2e-4 m/s, olivine_rate 0.38, pyroxene 0.54, fe 0.26, heat partition 6.2e-4, DIC 1.4 mM → 49.2 °C, pH 9.38, H2 10.8 mmol/kg, ΔpH 3.38) |
| **Robustness** | posterior-viable fraction **1.00** (both classes); P(consistent \| prior) 0.125; structure agreement on viability **1.00** | 100 % of the empirically supported distribution supports the transition; no model-form uncertainty across the two transport classes |
| **Discrimination** | binding observation: dissolved H2 (6/48 pass; pH 48/48, T 47/48); between classes d(T) = 0.89, d(pH) = −0.54 (on a 0.02-unit scale), d(H2) = 0.00 | pH is mineral-buffered (9.38–9.91 on every run) and uninformative; the classes differ only in outlet T (~2 °C) |
| Posterior | DIC 1.2–2.9 mM (prior 1.2–17 mM); olivine_rate 0.09–0.38 (prior 0.02–0.35); fe_fraction 0.14–0.26; heat partition 6e-4–1.9e-3 | the H2 window pins the Fe-budget-to-DIC ratio: at full redox equilibrium (llnl.dat) DIC is reduced before free H2 appears — a threshold, and an equilibrium-model statement to test with a kinetic carbon-redox class |
| Sensitivity (Morris, r = 4) | H2: olivine_rate 23.0, DIC 20.8, flow 16.9, fe 3.1; T: heat partition 2.16, flow 1.47, olivine 0.84; pH ≤ 0.11 everywhere | T and H2 are controlled by disjoint parameters; the posterior factorises |
| Verification | ledger residuals 0.0 (mass, energy), charge 0, flux ≤ 1.1e-14; 0 / 96 points rejected; `decision_discipline` = [] | clean |
| Tier | `mechanistic_prediction` ("predicts under stated assumptions"); the conditioning step is `reproduction` | language the study may use |

Wall time 368 s for the ensemble + ~160 s for Morris, serial, on the laptop.

### 6.3 What Phase 1 does *not* yet do (follow-ups, in order)

1. Attach **MARHYS 4.0** as a workspace dataset and condition on the
   ultramafic-vent population (decision recorded in `investigation.yaml`).
2. Add **Reaktoro** (conda) and **PFLOTRAN** on the `serpentinization` face
   under a pixi env, mirroring the FEniCS pattern, so database / activity-model
   dependence of the pH endmember becomes a class axis (plan upgrade A,
   "cross-check database dependence").
3. **Dynamic mineral feedback** (`MineralEvolutionProcess`, FMP §3): precipitation
   updating porosity / permeability / surface area, feeding
   `FipyReactiveTransportProcess.porosity` — the plan's "does the reactor
   poison or seal itself?" gate (`reactor-stays-open`).
4. **Out-of-sample**: hold out the H2 window, condition on T + pH only, and
   report whether the posterior predicts the measured H2 range.
5. Run **Sobol** on the posterior (not the prior) once the ensemble is large
   enough (Ray on the mini is not an option for PHREEQC; use a serial overnight
   run or a per-draw subprocess pool).

## 7. Roadmap — Phases 2–9 mapped onto the existing studies

Each phase leaves behind, per the plan: a reusable PBG component (a class on a
face), a calibrated vg-data package, a numerical-verification notebook (a
`sims/verify_*.py` + its artifact), and one or more *discriminating* studies.
The existing study keeps its passing result; the phase adds a `-cal` / `-alt`
study beside it and a class axis to its gates. Proposed study ids are
recorded in `investigation.yaml.guidelines.roadmap_phases`.

| Phase | Builds on | PBG component (face: classes) | vg-data package | Verification | Discriminating study (proposed id) | Exit criterion (plan) | Decision needed |
|---|---|---|---|---|---|---|---|
| **2 Electrochemical carbon fixation** | og-01 (`PhGradientNernstPlanckProcess`, `ProtonBudgetProcess`, `CarbonFixationProcess`), open decision "explicit electrochemistry vs gradient-efficiency scalar" | `carbon_fixation`: `empirical` (E), `butler_volmer` (A: fluid redox → electrode potential → overpotential → current density → surface rate, calibrated to Altair 2025 current/product yields), `microkinetic` (A: CatMAP/Cantera-style adsorbates, site coverage, passivation); `MineralConductivityProcess` derives `gradient_efficiency` from circuit physics | `electrochemical_interface` (Altair 2025, Panico 2026, Ni/Fe ratio, thickness, conductivity) | charge + electron-count ledger (`ledger.charge_residual` per tick, faradaic efficiency ≤ 1), current–voltage residual | `og-01-cal-electrochemistry`: (pH × H2 × conductivity × Ni/Fe) with the three classes; gate `failure-mode-attributed` — each point labelled thermodynamic / electrical / catalytic / transport-limited and the classes agree on the label in the favorable region | mechanism map | Adopt Butler–Volmer as the fast class first; CatMAP/Cantera is a conda/compiled dependency (pixi, like FEniCS) |
| **3 Open chemical network** | og-02 (`RoadRunnerNetworkProcess`, curated rTCA SBML) | `proto_metabolism`: `curated_rtca` (E), `reaction_universe` (A: generated SBML from a Wołos-2020-style rule set with reversible kinetics, side reactions, degradation, catalyst limits), `null_network` (A: randomized networks matched for compounds / reactions / energetic span / catalyst density) | `reaction_universe` (rules, ΔG′ via eQuilibrator, catalyst requirements) | flux-control analysis, element + free-energy ledger over the network, stiffness check vs libRoadRunner tolerances | `og-02-alt-reaction-universe`: gate `motifs-emerge-not-imposed` — persistent autocatalytic subnetworks detected post hoc; motif enrichment vs the matched nulls; the curated rTCA result becomes one class among three | distribution of persistent / autocatalytic subnetworks; enrichment vs null | Rule-set scope (C1–C3 only, or N/P-bearing from the start, folding og-res-N/P into the universe) |
| **4 3-D multisolute localization** | og-03 (`ThermophoreticTrapProcess`), the FEniCS cross-check (Pe ≳ 13 solver-sensitive), og-res-P's species-agnostic multiplier | `localization`: `fipy` (E), `fenics` (E, now with species Soret term), `pore_network` (A: reduced pore-network surrogate for ensembles, OpenPNM-style) | `pore_physics` (Baaske / Mast geometry, per-species D and S_T for phosphate, NH4, formate, acetate, pyruvate, amino acids, amphiphiles, nucleotide precursors) | mesh- and time-step convergence gate; head-to-head inside a declared trustworthy Péclet range; analytic bound `exp(Pe)` | `og-03-alt-colocalization`: gate `mixture-colocalizes` — co-localization / fractionation phase map for the simultaneous mixture, **no acceptance gate outside demonstrated convergence** (removes the >10⁸ headline from any gate) | co-localization envelope with convergence envelope | Whether og-03's current enrichment gate is re-stated at the resolvable Péclet (recommended) |
| **5 Endogenous boundary + growth/division** | og-04 (`ProtocellAssemblyProcess`), og-growth (`OsmoticGrowthDivisionProcess`), FMP §2.3–2.4 rewrites | `boundary`: `single_chain` (E), `mixed` (E), `thioester_aminothiol` (A); `AmphiphileSynthesisProcess` (A, from `molecules.dissolved.{acetate,formate}`); `BoundaryFormationStep` / `DivisionStep` / `LysisStep` / `ExtinctionStep` as `_add` / `_divide` / `_remove` rewrites on `agents: map[vg_individual]` | `amphiphile_assembly` (Jordan 2019 phase data under alkaline / saline / divalent conditions; Lu 2024 osmotic growth) | `ledger.rewrite_residual == 0` across every structural rewrite; partition residual on `_divide` | `og-04-alt-endogenous-boundary`: gate `boundary-forms-from-chemistry` (agents 0 → ≥1 with endogenous amphiphile; not with synthesis ablated); `og-growth-alt-physical-reproduction`: a ≥3-generation lineage in the agents map with daughter volumes summing to the mother's | first continuous chemistry → growing, dividing individual | Partition semantics for concentration maps (store `internal` as amounts + volume; FMP §9.1) |
| **6 Proto-energetics** | og-energy (`GeochemicalDriveProcess`, `ProtoEnergyCurrencyProcess`), og-05 (`BioenergeticSelectionProcess`) | `energy_coupling`: `passive_gradient` (A), `h_na_gradient_leaky_membrane` (A), `thioester_acyl_phosphate` (E as carrier), `polyphosphate` (E), `fe_redox` (A) — all inside each protocell composite, autonomy = internal / (internal + external) power per individual | `energy_currencies` (Fe disproportionation drive already proposed; H+/Na+ permeabilities) | free-energy ledger: `free_energy_in ≥ work + dissipated` as an invariant | `og-energy-alt-internalization-threshold`: gate `internalization-pays` — passive vs increasingly active coupling, the point where energetic benefit exceeds leakage + maintenance, per class | energy-capture efficiency and internalization threshold | Replace og-05's population-mean `internalization` with per-individual autonomy (reads the same field) |
| **7 Competing heredity** | og-06 (`LineageReplicatorProcess` modes), FMP §2.5 | `heredity`: `compositional`, `network`, `peptide`, `rna_like`, `hybrid`, `mineral_state` (carved out of the one class), attached conditionally by `HeredityAttachmentStep` under matched resource + energy budgets, Gillespie at low copy number | `inheritance_budgets` (precursor availability, error rates, template costs) | information ledger: heritable bits per unit energy; mutual information estimator convergence | `og-06-alt-information-per-cost`: gates `ancestry-predicts-phenotype` (parent–offspring mutual information per class) and the information-per-cost frontier; og-06's "need not presume RNA" becomes a class-substitution result | information-per-cost frontier; transition to templated heredity | Defensible attachment thresholds (expert input; `hypothetical` and swept until then) |
| **8 Biochemical ecology** | og-07 (`CrossFeedingMetacommunityProcess` capability vectors) | `proto_ecology`: real reaction networks per protocell (Phase-3 classes inside each agent), `SpatialCouplingStep` onto the Phase-4 fields, `BigraphicalReactiveSystem` exchange rules; `EcologyReducerStep` keeps og-07's gate names | `cnp_resources` + the Phase-3 universe | element ledger across agents + fields; exchange-rule firing counts | `og-07-alt-real-metabolite-exchange`: gate `community-function-precedes-cell-completeness` — a function present in the community union but in no lineage, sustained by real metabolite flux, not symbolic capability transfer | emergent cross-feeding / division of labor / robustness | Agent motion model (defer; point agents on fields first) |
| **9 Integrated autonomy** | og-08 (`OffGradientPersistenceProcess`, {pump, importer, heredity}), og-adv | one persistent world (FMP §2.2 skeleton) with an `AblationStep` scheduling geology withdrawal; the {pump, importer, heredity} result re-run under an **ensemble** of maintenance functions, transport laws, storage models, permeability assumptions and inheritance classes | all packages, posterior-propagated from Phase 1 | every ledger; structural-event log | `og-08-alt-robust-innovation-set`: gate `minimum-sufficient-innovation-set` across model structures — the *intersection* of required innovations, reported as a lattice with the continuous autonomy value (fraction of essential work and material supplied internally, decomposed by function) | functions robustly required across model structures | Treat the current {pump, importer, heredity} as a hypothesis generator (plan §10), not a result |

**Cross-cutting, every phase:** the adversarial `GenericNonequilibriumEnvironment`
becomes a class on an `environment` interface so og-adv's rejection re-runs
automatically per stage; every new class ships `_provenance` on its
`config_schema`; every gate is evaluated per class with the ensemble reducers;
every phase's `TransitionReport` is written into its study's `study_card` with
the tier language.

**Near-term flagship milestone (plan §13), as a study chain:** Phase 1
posterior → Phase 3 universe under that posterior's feed → Phase 4
co-localization of its persistent subnetwork's species → Phase 5 endogenous
boundary and division — *with uncertainty propagated from the geochemistry* via
`uq.sampling` draws carried as `vg-data` posterior packages, not best-fit
scalars.

## 8. Scientific endpoint and what the campaign may now say

The plan's defensible high-level conclusion — *across experimentally
constrained parameter distributions and multiple mechanistic model classes,
viva-genesis identifies where geological disequilibrium can support each
transition, and the specific bottlenecks, incompatibilities and environmental
features that break the path* — requires every stage to carry a
`TransitionReport`. Until then the campaign's investigation-level verdict should
be read with the tiers of §1.2: the arc *runs and passes its gates*
(reproduction at og-00/og-01, mechanistic predictions through og-04 and the
bottleneck modules, conceptual demonstrations beyond), and the three-quantity
standard is met so far for Phase 1 only (§6).

## 9. Open questions / blocked items

1. **MARHYS 4.0 access.** The PANGAEA export is not in the workspace; the
   conditioning set is Lost City only. Needs the expert to attach the dataset
   (`proposed_inputs: marhys4_hydrothermal_fluids`).
2. **Reaktoro / PFLOTRAN / CatMAP / Cantera** are conda or compiled; adopt the
   viva-fenics pixi pattern (one env per heavy backend; classes register
   unconditionally, run under pixi).
3. **Parallel PHREEQC.** The IPhreeqc extension does not survive a process pool;
   ensembles are serial (~4 s/point). A per-point subprocess runner or Ray with
   one PHREEQC instance per worker process is the fix for larger posteriors.
4. **Hadean ocean prior** (`fluid_dic`, ocean pH 6.0, 275 K) is extrapolated /
   hypothetical and unsourced by design; the audit flags it until the expert
   supplies a prior.
5. **Study narrative counts.** `investigation.yaml` executive text says
   "fourteen" studies; adding `og-cal-vent-environment` makes fifteen. Left for
   the narrative owner (another session edits that text).
