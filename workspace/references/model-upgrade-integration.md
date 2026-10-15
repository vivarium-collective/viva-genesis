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
| Phase 2 — electrochemical carbon fixation | `electrochemistry/{butler_volmer,empirical,microkinetic,mineral_conductivity}.py`, `ledger.ChargeLedgerProcess`, `composites/electrochemical_interface.py`, `uq/electrochemistry_calibration.py`, vg-data `electrochemical_interface`, study `og-01-cal-electrochemistry` | **built and run** (§6b; the `microkinetic` class is registered but its CatMAP/Cantera backend is pixi-only) |
| Phase 3 — open chemical network | `protometabolism/{universe,motifs,universe_process}.py`, `ledger.NetworkLedgerProcess`, `composites/open_chemical_network.py`, vg-data `reaction_universe`, study `og-02-alt-reaction-universe` | **built and run** (§6c) |
| Phase 6 — proto-energetics | `bioenergetics/energy_coupling.py` (five classes on the `energy_coupling` face), `ledger.FreeEnergyLedgerProcess`, `composites/protocell_energetics.py`, `uq/energetics_threshold.py`, vg-data `energy_currencies`, study `og-energy-alt-internalization-threshold` | **built and run** (§6d) |
| Phase 7 — competing heredity | `heredity/{competing,information}.py`, `ledger.InformationLedgerProcess`, `composites/competing_heredity.py`, vg-data `inheritance_budgets`, study `og-06-alt-information-per-cost` | **built and run** (§6e) |
| Phase 8 — biochemical ecology | `ecology/{proto_ecology,reactive_system}.py`, `ledger.EcologyElementLedgerProcess`, `composites/metabolite_exchange_community.py`, vg-data `cnp_resources`, study `og-07-alt-real-metabolite-exchange` | **built and run** (§6f) |
| Phases 4, 5, 9 | §7 roadmap, `investigation.yaml.guidelines.roadmap_phases` + `decisions_needed` | **planned** (4 and 5 have their classes and studies; 9 planned) |

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
| `carbon_fixation` (Phase 2) | `empirical` (og-01's lab-calibrated gated kinetics, adapted to publish its failure-mode attribution), `butler_volmer` (Nernst half-cell potentials + Butler-Volmer kinetics + the ohmic mineral/ionic circuit, solved as a galvanic cell each tick), `microkinetic` (CatMAP/Cantera adsorbate microkinetics; registers and face-checks here, runs under pixi — raises a clear error in the uv venv, never a mock) | whether carbon fixation is *driven* by a lumped proton-motive term or by explicit electrode kinetics is a structural assumption; the limitation label (thermodynamic / electrical / catalytic / transport) is the readout the classes are compared on |

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
`electrochemical_interface` (built, §6b: the Altair-2025 current window as the
calibration observation, exchange currents `calibrated` to it, Preiner-2020
electron branching `inferred`, the Ni gain and the ocean-side H2
`hypothetical` — the latter unsourced on purpose so the audit flags it; the
roadmap's "Panico 2026" is cited through the workspace's existing bibkey for
the Communications Chemistry 2026 current-producing-interfaces paper);
`reaction_universe` (Phase 3: Wołos 2020
rule set, eQuilibrator ΔG′, catalyst constraints); `pore_physics` (Phase 4:
Baaske / Mast geometry, species Soret coefficients); `amphiphile_assembly`
(Phase 5: Jordan 2019 phase data, Lu 2024 osmotic growth); `energy_currencies`
(built, §6d: the external pmf `calibrated` to the Phase-1 posterior ΔpH, the
H+ permeability `extrapolated` from vesicle literature with the Na+/H+ ratio's
*order* `inferred` from Sojo 2014, carrier bonds `inferred` from Buckel &
Thauer, the Fe(II)-disproportionation drive `hypothetical` pending the
reference's acceptance, and every per-cell number — turnover, maintenance,
pool, load — `hypothetical`; 24 parameters, `unsourced = []`);
`inheritance_budgets` (Phase 7, built — §6e: per-copy template costs,
precursor feeds, copy error rates, the energy quantum, the low-copy scale and
the attachment thresholds; 39 parameters, the ribozyme fidelity the one
measured entry, `unsourced = []`); `cnp_resources` (Phase 8, built — §6f: the
Phase-1 carbon feed `calibrated`, the og-res N / P pools `extrapolated`, the
membrane permeability classes `extrapolated` from fatty-acid vesicle work with
the dicarboxylate value `hypothetical` — the swept Decision axis and the
weakest number — the pore residence `inferred` from the og-02 convention over
the Phase-4 window, the C:N:P demand `hypothetical`; 23 parameters, `unsourced
= []`; the measured charged-solute permeability and a Redfield-type anchor are
in `proposed_inputs`, pending).

## 4. The campaign UQ layer

`viva_genesis/uq/` — built. Mapping of the plan's section-11 methods:

| Method | Module / function | State |
|---|---|---|
| Bayesian calibration | `calibration.py`: `Observation` windows, `abc_rejection` (uniform likelihood on windows — the worked example), `gaussian_weights` (importance), `posterior_summary`, `Calibrator` protocol for a PyMC/NumPyro backend | ABC + importance built; MCMC backend planned when a stage has a likelihood model rather than population windows |
| Global sensitivity | `sensitivity.py`: `morris` (elementary effects, `r` trajectories), `sobol` (Saltelli + Jansen, bootstrap CIs); both on NumPy only (SALib not required), tested against Ishigami analytic indices | built |
| Structural model ensembles | `ensemble.py`: `pass_fraction`, `structure_agreement`, `decision_envelope`, `paired_class_difference` on a `SweepResult` with a class axis or on `{class: mask}` | built |
| Uncertainty propagation | `sampling.py`: `lhs_unit`, `sample_package` (LHS over the package's free parameters), `draws_to_configs` | built |
| Numerical verification | `viva_genesis/ledger.py` (`ConservationLedgerProcess`), `spatial-transport-solver-comparison.md` (cross-solver), `compare_spatial_transport.py` (manufactured solution, convergence orders) | ledger + cross-solver built; mesh/time-step convergence gate per stage planned (§7, Phase 4) |
| Null and adversarial models | og-adv (environment ablation); `null_network` class on the `proto_metabolism` face (degree-preserving, (C,O)-matched rewiring of the generated universe, 24 draws per arm in og-02-alt-reaction-universe) | built |
| Out-of-sample prediction | `calibration.py` conditions on named observations, so holding one out is `package_observations(...)` minus one | mechanism built; first held-out test planned in Phase 1 follow-up (hold out H2, predict it) |
| Pre-registered gates | `study.yaml.preregistered` + §1.4 rule | practice |

**What is thin and says so.** The Bayesian interface stops at ABC/importance;
Sobol is implemented but has not been run on the real world (Morris has —
§6); the ledger covers the vent world's H2 / alkalinity / heat / charge / flux
balance and (Phase 3) the network's exact element residual, integrated carbon
balance and dissipation, not yet N/P totals or rewrite residuals (FMP §5.3).

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

## 6b. Phase 2 — electrochemical carbon fixation, worked concretely

### 6b.1 What was built

- `viva_genesis/models.py` — the `carbon_fixation` face (required: H2, CO2,
  temperature, catalyst_activity, the three product pools → the three product
  deltas + net_carbon_flux; optional: the og-01 pmf / feasibility drive *or*
  the electrochemical drive pH_vent, pH_ocean, ni_fraction, conductivity,
  layer_thickness, porosity, ionic_strength; optional outputs: the circuit
  readouts, the electron-balance witnesses and the four `loss_*` fractions +
  `limitation_code`). Every port maps to a canonical `vg_*` field (new atoms
  `vg_areal_resistance`, `vg_charge`; new fields on `vg_minerals` /
  `vg_energy`). Three registered classes, all face-checked; og-01's original
  `CarbonFixationProcess` also satisfies the face.
- `electrochemistry/butler_volmer.py` — `ButlerVolmerCarbonFixationProcess`
  (tier A, the primary class): Nernst half-cell potentials from the fluid
  redox state (Henry-corrected H2 / CO2 activities, formic-acid speciation,
  the CO2/HCOOH couple at E0 = −0.199 V, a competing H2-evolution branch);
  Butler-Volmer kinetics with exchange currents scaled by catalyst activity,
  Ni fraction (Preiner hierarchy) and an Arrhenius factor; Koutecký-Levich
  transport limits in both directions; the ohmic mineral (L/σ) + Bruggeman
  ionic path; the cell current as the Brent root of
  `E_c(j) − E_a(j) − j R = 0`; the faradaic split over formate (2 e−),
  acetate (8 e−), pyruvate (10 e−). The fresh-fluid emf is partitioned each
  tick into thermodynamic / electrical / catalytic / transport loss fractions
  (sum to 1 while current flows). Pure functions `solve_cell` /
  `polarization_curve` back the tests and the viz.
- `electrochemistry/empirical.py` — `EmpiricalCarbonFixationProcess` (tier
  E): og-01's rate law unchanged (`update` delegates), Ni-scaled catalyst,
  the headroom of each gate published as the four losses, faradaic
  efficiency 1 by construction (stated).
- `electrochemistry/microkinetic.py` — `MicrokineticCarbonFixationProcess`
  (tier A, deferred): CatMAP/Cantera adsorbate microkinetics; registers and
  face-checks everywhere, raises `MicrokineticBackendMissing` ("run under
  pixi") in `update`. Never a mock. Build items in `NEXT_STEPS.md`.
- `electrochemistry/mineral_conductivity.py` — `MineralConductivityProcess`:
  `gradient_efficiency = R_ct / (R_ct + L/σ_e + L/(σ_f φ^1.5)) · (1 − shunt)`
  with `R_ct = (RT/F)(1/j0_a + 1/j0_c)`. The Phase-2 composite runs og-01's
  Nernst-Planck gradient at *this* efficiency instead of the knob.
- `ledger.ChargeLedgerProcess` — per tick: Kirchhoff residual
  `|e_anode − (e_carbon + e_her)| / e_anode`, faradaic efficiency recomputed
  and bounded by 1, worst-case current-voltage residual, integrated charge
  and electrons-to-carbon, `charge_ledger_ok`. During the build it caught a
  real gap (on insulating walls the trace ocean-side H2 oxidising at the
  cathode co-supplies electrons), now counted explicitly.
- vg-data `electrochemical_interface` (13 parameters: 1 measured, 3
  calibrated, 6 inferred, 1 extrapolated, 2 hypothetical; `unsourced = []`
  — the ocean-side H2 is hypothetical and flagged by design).
- `composites/electrochemical_interface.py` — the layer generator with
  `model_carbon_fixation` as a categorical axis; `uq/electrochemistry_calibration.py`
  — the sweep, attribution, agreement and report; `viz_uq.ElectrochemistryMechanismMap`
  / `ElectrochemistryPolarization`; study `og-01-cal-electrochemistry`.

### 6b.2 Results (5 × 5 × 5 × 3 = 375 points × 2 runnable classes, 40 ticks, nx = 20, open flow)

| Quantity | Value | Reading |
|---|---|---|
| Coverage | 375/375 points labelled in both classes; 0/750 failed | every point carries a limitation label |
| **Gate `failure-mode-attributed`** | label agreement **0.47** on the 78 points both classes call favorable (0.45 overall) — **FAIL** vs the pre-registered ≥ 0.8 | the limitation label is structure-sensitive; `decision_discipline` flags it |
| Butler-Volmer map | catalytic 226, electrical 149, transport 0, thermodynamic 0; favorable region 93/93 catalytic | at Altair-level exchange currents the conducting wall is activation-limited; electrical only below ~1e-6 S/m; thermodynamics never binds in open flow |
| Empirical map | transport 147, catalytic 117, electrical 108, thermodynamic 3 | the pmf-Michaelis drive lumps electrical + catalytic; Km(H2) = 1e-4 M invents a transport limit |
| Where they agree | 0.81 at 1e-9 S/m (both electrical); 0.67–0.68 at H2 ≥ 1.4e-4 M; 0.01 at 1 µM H2 | agreement only where the physics is unambiguous |
| Calibration | nominal j = 1.06e-3 A/m², FE 0.92, emf 0.49 V; 79.7 % of the grid inside the Altair window (1e-5..1e-2 A/m²); FE 0.76–1.00 | reproduction-tier check against the window, not a per-condition fit |
| Derived gradient efficiency | 0.01 / 0.42 / 0.98 / 1.00 at 1e-9 / 1e-7 / 1e-5 / ≥ 1e-3 S/m | the Tutolo collapse is a conductivity regime, not a knob |
| Verification | charge residual ≤ 1.7e-13; FE max 1 + 1e-13; circuit residual ≤ 8.5e-9; all 750 ledgers OK | clean |
| Discrimination | d(log10 throughput) = 11 (scale), d(loss_transport) = 1.77, d(loss_thermodynamic) = 0.68; loss_electrical / loss_catalytic / gradient_efficiency \|d\| < 0.5 | the classes separate on the transport attribution |
| Tier | `mechanistic_prediction` ("predicts under stated assumptions"); the current-window check is `reproduction` | language the study may use |

Wall time 117 s for the sweep on 6 workers. The honest reading: Phase 2
delivers its component, package, ledger and mechanism map, and the gate
fails because *attributing* a limitation is a property of the model class —
the empirical rate law cannot separate electrical from catalytic limitation.
Decisions recorded in `investigation.yaml`.

### 6b.3 What Phase 2 does *not* yet do

1. Run the **microkinetic** class (CatMAP / Cantera under pixi) — the third
   class the roadmap row names; `NEXT_STEPS.md` lists the build items.
2. Attach the **Altair-2025 per-condition** current / product time courses so
   the exchange currents become a fit rather than a window calibration.
3. Decide whether og-01's default class becomes `butler_volmer` (then the
   Tutolo arm is `conductivity`, not `gradient_efficiency`).
## 6c. Phase 3 — the open chemical network, worked concretely

Built (PR "feat(phase3)"): `viva_genesis/protometabolism/universe.py` (linear
C/H/O skeletons up to C4, eleven Wołos-style rules → 413 reversible reactions,
exact element balance, eQuilibrator component-contribution potentials for the
50 formula-verified KEGG skeletons and a group-additivity fit — LOO RMSE
7.2 kJ/mol — for the other 71, catalyst classes with a saturating site pool,
degradation, washout, Antimony emission with carbon-ledger integrators, and
the (C,O)-matched degree-preserving null); `motifs.py` (SBML network
extraction, exact element residual, bounded-DFS enumeration of flux-carrying
simple cycles with stoichiometric gain > 1 — Blokhuis 2020 type-I cores —
og-02-compatible dynamic gain, empirical enrichment, finite-difference
elasticities → flux-control coefficients + summation theorem, CVODE
tolerance sweep + Jacobian stiffness); `universe_process.py`
(`ReactionUniverseProcess`, `NullNetworkProcess`); `ledger.NetworkLedgerProcess`;
`composites/open_chemical_network.py` (`model_proto_metabolism` axis; feed =
the Phase-1 posterior example point from `vg-data/reaction_universe.yaml`); the
`proto_metabolism` face in `models.py` with `curated_rtca` =
`RoadRunnerNetworkProcess`. Kinetic convention: the exergonic direction of
every reaction runs at its rule's k0, the uphill one at k0·exp(−|ΔG′°|/RT), so
detailed balance is exact, no rate exceeds a catalyst turnover, and the
dissipation −Σ v ΔG is a real second-law witness.

Results (`og-02-alt-reaction-universe`, 200 ticks, 24 nulls per arm):

| Arm | Universe | Nulls (24) | Curated rTCA |
|---|---|---|---|
| Phase-1 feed (CO2 1.4 mM, H2 10.8 mM, pyruvate 0.1 mM) | 14 persistent species, 0 motifs; the reductive branch OAA/malate/succinate at 5e-8 / 9e-8 / 8e-9 M (equilibrium-limited carboxylation) | 0 motifs (p = 1.0) | 1 motif (self-loop, dynamic gain 2.99 = declared k_rtca[CO2]/k_wash); element residual C 4 / H 8 / O 3 per turn |
| + 10 mM formaldehyde | 49 species, **1 motif** = the formose cycle (gain 2, dynamic 3.1), recovered post hoc | 0 motifs, **p = 0.040** | same |
| Ignition map (CH2O × washout) | motif only at CH2O ≥ 9.6 mM & washout ≥ 0.024/s (30 mM: ≥ 0.008/s) | 0 everywhere | — |

Verification: universe element residual 0 (exact), carbon balance 2.8e-6,
dissipation ≥ 0 every tick, summation theorem 3.3e-3 on the dominant fluxes
(1.3e-4 on the curated model), stiffness ratio 9.4e2, tolerance sensitivity
7e-6 (tightened) / 2.8e-3 (loosened). The nulls match compound / reaction /
arity / catalyst density / C,O balance but not the energetic span (714 vs
166 kJ/mol) because their ΔG′ stay potential-consistent — recorded as a
limitation. Provenance audit of the package: 0 measured, 2 calibrated, 4
inferred, 7 extrapolated, 8 hypothetical.

Reading: with real thermodynamics and conservation the curated motif is
*imposed* (and its stoichiometry creates carbon); the generated universe makes
no autocatalysis at vent activities because every C–C route is uphill, and the
one cycle the C ≤ 4 chemistry can close (formose) needs a C1 supply and a
residence time the reducing vent does not provide — which hands Phase 4
(co-localization) its question.

## 6d. Phase 6 — proto-energetics inside the individual, worked concretely

Built (PR "feat(phase6)"): `viva_genesis/bioenergetics/energy_coupling.py` —
one per-individual power-budget engine (SI watt per cell) behind the
`energy_coupling` face in `models.py`, with five structurally different
classes: `passive_gradient` (the external pmf tapped through the membrane
leak, `G_flux = F P_H A Δc pmf`, no store), `h_na_gradient_leaky_membrane`
(a pumped Na+/H+ gradient store with capacitor potential `n F pmf_max q`
leaking *through the membrane* at `ratio × P_H` — the Sojo tradeoff),
`thioester_acyl_phosphate` and `polyphosphate` (og-energy's carriers as the
store, ideal-mixing potential `bond + RT ln(q/(1−q))` relative to the resting
charge, leaking by hydrolysis plus carrier permeation) and `fe_redox` (a
reduced-metal store charged by the Fe(II)-disproportionation drive). Charging
is gated by the drive clearing the store potential (capped exactly), work by
the store potential clearing the load (30 kJ/mol), leaks relax toward the
resting charge; every flow is an exact difference of the store's free-energy
function, so `ledger.FreeEnergyLedgerProcess` closes
`in_cum + E0 − work_cum − diss_cum = E(t)` to rounding and witnesses the
roadmap's `free_energy_in ≥ work + dissipated` as a non-negative margin, a
non-negative dissipation rate and a capture efficiency ≤ 1. Autonomy =
internal / (internal + external) power is one readout across classes and is
now also published per individual by og-05's `BioenergeticSelectionProcess`
beside its population-mean `internalization` (the switch-over is a recorded
decision). `composites/protocell_energetics.py` carries the
`model_energy_coupling` axis, the og-energy drive processes for both drives
and og-05's decline process for the collapsing-gradient scenario;
`uq/energetics_threshold.py` is the sweep / attribution / report;
`viz_energetics.py` the two figures; `schemas.py` gains the power-budget
fields on `vg_energy`.

Results (`og-energy-alt-internalization-threshold`: 5 classes × 11
activities × 9 permeabilities × 2 gradient states = 990 runs, 300 ticks of
10 s, 7 s on 6 workers):

| Class | Threshold activity a* at P_H 1e-6 m/s, 0.216 V | Autonomy at a* / at a = 1 | Pays on the grid | Permeability ceiling | Collapsed gradient (0.02 V), a = 1 |
|---|---|---|---|---|---|
| passive_gradient (baseline, net 1.95e-17 W) | — | 0 / 0 | 0 % | — | 1.7e-18 W |
| thioester_acyl_phosphate | **0.10** (potential 29.6 → 34.3 kJ/mol; best +2.1e-18 W at 0.8) | 0.03 / 0.26 | 54 % | 3.2e-6 m/s | +3.7e-18 W, autonomy 0.79 |
| fe_redox | **0.80** (potential pinned 29.3–29.9 at the load) | 0.17 / 0.21 | 18 % | 1e-6 m/s | +1.9e-18 W, 0.74 |
| h_na_gradient_leaky_membrane | none (potential 6.5 kJ/mol; Na+ leak 6e-3/s) — pays at P_H 1e-8 from 0.5 | 0 / 0 (0.97 at 1e-8) | 4 % | 1e-8 m/s | −3.3e-18 W |
| polyphosphate | none (potential 22.1 kJ/mol at q 0.69; needs q > 0.98) | 0 / 0 | 0 % | — | −3.3e-18 W |

Verification: ledger residual ≤ 1.3e-14 on every run, second-law margin ≥
−1e-26 J (rounding against ~1e-13 J of intake), dissipation ≥ 0,
capture efficiency ≤ 0.30 (0.26–0.28 at the thresholds); `decision_discipline`
= []. Cross-class agreement on "pays" 0.46 (pairwise 0.46–0.96); most
discriminating readouts store potential (d = 1.9), internal power (1.0),
capture efficiency (0.9), autonomy (0.8). Provenance audit 0 measured / 1
calibrated / 8 inferred / 3 extrapolated / 12 hypothetical. Tier:
`conceptual_demonstration` ("demonstrates in a coarse-grained model") — every
per-cell number is hypothetical and the priors were not propagated.

Reading: inside one individual the internalization threshold is
thermodynamic — a store pays only once its potential clears the load faster
than it leaks — so the leak law and the bond energy, i.e. the model *class*,
decide: a thioester-class carrier internalizes from a tenth of the drive at
fatty-acid-like leak, Fe-redox only near full activity, a pumped ion gradient
only in a membrane ~100× tighter to Na+ (Sojo's constraint, per individual),
polyphosphate never against a 30 kJ/mol step. What Phase 6 does *not* yet do:
propagate the `energy_currencies` priors; put the classes inside each og-05
strategy and re-run selection on per-individual autonomy; take P_H from the
og-04 membrane process; transcribe the Fe(II)-disproportionation numbers.
## 6e. Phase 7 — competing heredity, worked concretely

Built (PR "feat(phase7)"): `viva_genesis/heredity/competing.py` — the six
heredity classes carved out of og-06's one `LineageReplicatorProcess`
(`module=` string) into separate Process classes on one `heredity` face
(`models.py`): `rna_like` (L-site template, template-directed copy at per-site
fidelity q with back-mutation, L nucleotides + L quanta per copy), `peptide`
(8-site peptide, weak sequence-templated ligation at q_p over a 20-letter
alphabet), `compositional` (GARD composition over K = 8 amphiphile types with a
lognormal mutual-catalysis matrix carrying two composomes, inherited by random
fission; 1 amphiphile, 0 quanta per incorporation), `network` (M = 4
autocatalytic cores growing in their own niches, lost by dilution at fission,
re-seeded only by rare spontaneous formation; capacity M bits), `hybrid` (an
8-site template whose function focuses the composition) and `mineral_state`
(a 16-bit crystal-face defect pattern copied into every new layer at per-bit
error p_m; cleavage hands both daughters the face). Every class is simulated
by **one exact Gillespie direct-method lineage at low copy number**
(`CompetingLineage`): 32 protocell-scale individuals (1 fL) carrying ~10–40
heritable molecules each, a bulk mass growing at `k_grow (1 + σ φ)` (φ = the
function the heritable state confers through a common sigmoid landscape, σ =
Eigen's superiority, which also multiplies each template's own copy rate),
division at 2 m₀ with random partition of the heritable state, uniform dilution
at capacity; every copy draws **integer** precursor molecules from one shared
pool and integer energy quanta (30 kJ/mol each) from one shared store — the
budgets are matched across classes by construction and the ledgers are exact.

`HeredityAttachmentStep` (FMP §2.5) attaches heredity only when the class's
precursor budget (`attach_min_copies × cost per copy × n` molecules), energy
budget (`attach_energy_margin ×` the same in quanta) and expected copy fidelity
(**Eigen's threshold Q ≥ 1/σ**) all hold; before attachment daughters re-form
their heritable material de novo *from the same pool at the same price* —
og-06's non-heritable control is the unattached state of every class, not a
seventh module. The budget thresholds are `hypothetical` (expert decision
recorded in `investigation.yaml`) and swept.

Verification: `viva_genesis/heredity/information.py` — a plug-in
parent→offspring mutual-information estimator on equal-frequency bins with a
phenotype-resolution floor (differences in function below 5 % are one
phenotype), Miller–Madow bias correction and a **permutation null** (realised
heritable bits = MI − null), plus the **convergence check** the roadmap asks
for: a time-ordered prefix ladder (n/4, n/2, 3n/4, n) and a bootstrap standard
error, converged only when the last two rungs agree within 0.05 bit (or 15 %)
and SE ≤ 0.05 bit. `ledger.InformationLedgerProcess` integrates the energy a
class spends (quanta + precursor free-energy equivalents) and its births,
audits the shared store exactly (`stored_work = W₀ + ∫flux − ∫spent`,
residual ≤ 3e-14 on every run) and prices the converged bits per joule and
per precursor; it certifies nothing while the estimator is unconverged.
vg-data `inheritance_budgets`: 39 parameters — 1 measured (the R18 ribozyme's
96.7 % per-site fidelity, Johnston 2001), 6 inferred, 8 extrapolated, 24
hypothetical; `unsourced = []`; the defect-copy error of the mineral class is
the declared weakest number.

Results (`og-06-alt-information-per-cost`, 6 seeds × 100 ticks per class and
arm, 3 seeds per map point; 252 composite runs, 75 s on 6 workers):

| Class | Heritable bits (attached / control) | MI converged on all 6 seeds | Energy per offspring | Bits / J | Precursors per offspring | Capacity | Attaches (step) from |
|---|---|---|---|---|---|---|---|
| mineral_state | 2.24 ± 0.14 / 0.00 | no (function decays through layer-copy errors at the nominal budget; the lineage is non-stationary) | 4.1e-20 J | 5.4e19 | 8 | 16 bits | 3 % of the nominal budget; p_m ≤ 0.005 |
| rna_like | 1.46 ± 0.10 / 0.00 | yes | 3.0e-17 J | 4.9e16 | 150 | 60 bits | the full budget only; q ≥ 0.967 |
| network | 0.53 ± 0.06 / 0.00 | yes | 4.2e-19 J | 1.3e18 | 4 | 4 bits | 3 % |
| hybrid | 0.49 ± 0.03 / 0.00 | yes | 1.9e-17 J | 2.5e16 | 103 | 34 bits | 30 %; q ≥ 0.90 |
| compositional | 0.47 ± 0.03 / 0.00 | yes | 1.1e-18 J | 4.3e17 | 11 | 18 bits | 3 % |
| peptide | 0.14 ± 0.22 / 0.00 | no | 1.5e-17 J | 9.0e15 | 154 | 35 bits | never at q_p = 0.7; q_p ≥ 0.90 |

Every control (heredity unattached, daughters re-formed de novo from the same
budget) transmits 0.00 bit with heritability ≈ 0; every attached class
transmits bits with heritability 0.45–1.0; the energy-store residual is
≤ 3e-14 on all 252 runs.

Gates (declared after the exploratory scans were visible; the committed
artifact is the deterministic 6-seed run): `ancestry-predicts-phenotype` —
**4/6** classes pass the strict rule (MI converged on every seed, ≥ 0.1 bit,
≥ 0.05 bit above the class's own control); peptide fails on fidelity (refused
by the step at q_p = 0.7) and mineral_state on convergence. The
information-per-cost frontier spans **3.8 decades** in bits/J; the certified
Pareto front is {network, rna_like}; mineral_state would dominate both axes
(cheapest and richest) if its estimate were certified — on a defect-copy
error nobody has measured. Class substitution splits by currency: among
certified classes the best non-RNA class (network) carries **0.36×** the
RNA-like bits per offspring but **26×** its bits per joule — og-06's "need not
presume RNA" survives as an efficiency statement, not as a capacity one.
The attachment map's span low→high budget is 1.0 over attachable classes
(compositional / network / mineral attach from 3 % of the nominal budget,
hybrid from 30 %, rna_like only at the full budget); the transition to
templated heredity against the organic attractor classes happens the moment
the Eigen floor admits the template (rna_like at q ≥ 0.967 carries 3× the
bits of compositional / network), not against the mineral class within the
swept range. Reading: at low copy number the expensive, high-capacity template
transmits the most certified phenotype bits but needs 30× the budget of the
attractor classes and ribozyme-level fidelity to be attached at all, while
the cheap classes win per joule by one to three decades.

What Phase 7 does not yet do: attach the classes to Phase-5 agents as a
bigraph rewrite (the step publishes a lineage-level flag, the class holds its
individuals); sequence-level information (the MI is on phenotype, bounded by
the resolution bins, so capacity and realised bits are reported side by side);
propagate the package priors (nominal + two swept axes only).
## 6f. Phase 8 — biochemical ecology, worked concretely

Built (PR "feat(phase8)"): `viva_genesis/ecology/proto_ecology.py` — the
`proto_ecology` face in `models.py` with two real classes,
`reaction_universe` = `ProtocellNetworkProcess` and `null_network` =
`ProtocellNullNetworkProcess`: **the Phase-3 rule-generated universe inside
every agent** (413 reversible reactions, eQuilibrator ΔG′, catalyst-site
saturation, degradation to tar, integrated by the agent's own libRoadRunner
instance from one JIT-cached SBML), **masked to the agent's lineage
repertoire** — the subset of the twelve reaction rules its catalysts carry,
applied as 0/1 rate multipliers (`REPERTOIRES`: `fixer` = CO2 reduction +
the two carboxylations, `reducer` = the three hydrogenations, `condenser` =
aldol / formose / isomerisation / Cannizzaro, `generalist` = all; the
uncatalysed decarboxylations belong to every lineage). The class reads the
agent's dissolved pool from the agents map, advances the chemistry over the
tick with **no exchange term**, writes the pool deltas back and publishes the
product classes it **produced itself** (gross internal production above the
flux floor — at steady state an intermediate's net production is zero
although the agent makes it continuously), the per-rule flux, the H2 / CO2
rates and the Phase-3 witnesses (exact element residual, dissipation ≥ 0,
carbon degraded). og-07's `CrossFeedingMetacommunityProcess` is the face's
declared non-conformer (no pool; its outputs are capability symbols).

`viva_genesis/ecology/reactive_system.py` — `BigraphicalReactiveSystem`: an
ordered set of **matter-conserving exchange rules** matched against the
bigraph each tick and counted when they fire — `UptakeRule` / `SecretionRule`
(membrane permeation between an agent and its field cell as the exact
two-compartment relaxation of each species, `k = P A / V` from six
size-and-charge permeability classes), `PoreDiffusionRule` (neighbouring
cells), `PoreExchangeRule` (every cell relaxes toward its Phase-4 background
at the pore residence rate; the element moles crossing the pore boundary are
integrated). No rule moves a capability. `SpatialCouplingStep` points each
agent at a fixed cell (positions in the `lineages` map — **no motion this
phase**, the recorded decision), shapes the cells' background from the feed
and the `localization` class's per-species `enrichment` raised to the cell's
fractional position (the Soret profile), fires the system and publishes the
firing counts and the **cross-lineage flux** of every species (moles secreted
by one lineage and taken up by another in the same tick). `EcologyReducerStep`
keeps og-07's gate names and recomputes them from the agents: capabilities
are product classes (chain length × carboxylation × oxidation state, derived
from the skeletons), *held* above a 1 nM floor or produced, *intrinsic* when
produced; it also publishes the community union and each agent's completeness
relative to it. `ledger.EcologyElementLedgerProcess` sums C, N and P over
every agent's interior and every field cell and closes them against the pore
inflow, washout and tar. `composites/metabolite_exchange_community.py`
carries `model_proto_ecology` and `model_localization` as class axes;
`viz_ecology.py` the two figures; vg-data `cnp_resources` the feed, pore,
protocell, permeability and floor parameters (23; 0 measured, 2 calibrated, 7
inferred, 7 extrapolated, 7 hypothetical, `unsourced = []`).

Results (`og-07-alt-real-metabolite-exchange`: 98 composite runs — the arms
at the canonical point plus four arms over 7 diacid permeabilities × 3
residences, 250 ticks, 8 agents each; ~110 s on 6 workers):

| Arm (canonical point: P_diacid 1e-8 m/s, residence 100 s) | Classes held | Malate (c4_diacid_hydroxy) | Robustness | Max completeness |
|---|---|---|---|---|
| **community** fixer:4 + reducer:4, interleaved | 15 | **6.4e-9 M** in the reducer lineage (3.9e-3 molecules per 1-fL agent; 3.9 per 1-pL compartment) | 0.54 | **0.93** (14/15) |
| mono fixer:8 | 7 | 0 (never produced) | 0.25 | 1.0 |
| mono reducer:8 | 9 | 0 (never produced) | 0.32 | 1.0 |
| private (same assignment, no sharing) | 13 | 0 | 0.46 | 0.69 |
| generalist:8 (complete cells) | 19 | 1.36e-7 M (0.08 molecules per fL) | 0.68 | 1.0 |
| segregated placement | 15 | present (1 community-only class) | 0.54 | 0.93 |
| rewired null (seeds 0 / 1) | 7 / 11 | — (0 / 1 community-only classes: methanol in seed 1) | — | — |

**Gate `community-function-precedes-cell-completeness`: PASS.** One product
class — the reductive C4 branch, malate — is held by the community and by
neither lineage in monoculture, vanishes in the private arm, and its
precursor oxaloacetate (made only by the fixer, gross carboxylation 5e-6 M/s;
the reducer cannot make it) crosses between the lineages at 1.8e-27 mol per
tick (1.1e-3 molecules per tick over the eight agents; formate 1.7e-24 and
lactate 3.6e-25 mol/tick carry the largest cross-lineage fluxes). The
community reaches 4.7 % of a complete cell's level while its best agent holds
14 of the 15 classes. Decision map: the function emerges from **P_diacid =
3e-9 m/s** at 20 s and 100 s residence and only at 1e-7 m/s at 500 s (the
shared feed depletes); below the boundary oxaloacetate decarboxylates back to
pyruvate (0.02/s) inside the fixer before it can cross. The measured passage
of charged solutes through fatty-acid vesicles (~1e-11–1e-10 m/s; Mansy
2008, proposed, pending) sits one to two decades below the boundary — the
study's main constraint and a recorded decision. og-07's readouts from real
agents: shared robustness 0.54 vs private 0.46 (connected-beats-isolated
0.07); the within-run isolated counterfactual equals the held robustness,
because what an agent acquires by flux is a precursor and the function it
then performs is its own — og-07's "acquired capability" has no counterpart
in real chemistry. LUCA-core overlap 0.8 wherever a fixer is present (ceiling
0.8: ion pumping is unreachable in a C/H/O network).

Verification: C residual ≤ 6.5e-9 (CVODE tolerance), N ≤ 1.1e-15, P ≤ 1.4e-15
over agents + field on all 98 runs; 468,331 exchange-rule firings on the
canonical run (secretion 135,316, uptake 115,466, pore diffusion 93,009,
feed / washout 124,540); element residual 0 and dissipation ≥ 0 in every
agent. Tier: `conceptual_demonstration` ("demonstrates in a coarse-grained
model") — the chemistry and thermodynamics are real, every permeability is
extrapolated or hypothetical, and the function lives at copy numbers (four
thousandths of a molecule per femtolitre agent — four per picolitre pore
compartment — a thousandth of a precursor per tick) where the ODE description
is a mean-field expectation of occupancy, not a count.

Reading: with real chemistry, division of labour is a property of the
membrane as much as of the network — two incomplete protocells run a
carbon-fixation branch together only where the intermediate crosses faster
than it decarboxylates and washes out, and the rewired null shows a rule
partition can split *some* pathway in rewired chemistry too (what the real
universe fixes is *which*). What Phase 8 does *not* yet do: exact
low-copy-number stochastics per agent (the Phase-7 machinery); permeabilities
from the Phase-5 boundary classes; growth, division or motion of agents
(motion deferred — `decisions_needed`); N/P-bearing rules so the C:N:P demand
becomes a gate; a second lineage partition.

## 7. Roadmap — Phases 2–9 mapped onto the existing studies

Each phase leaves behind, per the plan: a reusable PBG component (a class on a
face), a calibrated vg-data package, a numerical-verification notebook (a
`sims/verify_*.py` + its artifact), and one or more *discriminating* studies.
The existing study keeps its passing result; the phase adds a `-cal` / `-alt`
study beside it and a class axis to its gates. Proposed study ids are
recorded in `investigation.yaml.guidelines.roadmap_phases`.

| Phase | Builds on | PBG component (face: classes) | vg-data package | Verification | Discriminating study (proposed id) | Exit criterion (plan) | Decision needed |
|---|---|---|---|---|---|---|---|
| **2 Electrochemical carbon fixation** — **built and run (§6b)**; gate result: agreement 0.47 < 0.8, attribution structure-sensitive | og-01 (`PhGradientNernstPlanckProcess`, `ProtonBudgetProcess`, `CarbonFixationProcess`), open decision "explicit electrochemistry vs gradient-efficiency scalar" | `carbon_fixation`: `empirical` (E), `butler_volmer` (A: fluid redox → electrode potential → overpotential → current density → surface rate, calibrated to Altair 2025 current/product yields), `microkinetic` (A: CatMAP/Cantera-style adsorbates, site coverage, passivation); `MineralConductivityProcess` derives `gradient_efficiency` from circuit physics | `electrochemical_interface` (Altair 2025, Panico 2026, Ni/Fe ratio, thickness, conductivity) | charge + electron-count ledger (`ledger.charge_residual` per tick, faradaic efficiency ≤ 1), current–voltage residual | `og-01-cal-electrochemistry`: (pH × H2 × conductivity × Ni/Fe) with the three classes; gate `failure-mode-attributed` — each point labelled thermodynamic / electrical / catalytic / transport-limited and the classes agree on the label in the favorable region | mechanism map | Adopt Butler–Volmer as the fast class first; CatMAP/Cantera is a conda/compiled dependency (pixi, like FEniCS) |
| **3 Open chemical network** (built — §6c) | og-02 (`RoadRunnerNetworkProcess`, curated rTCA SBML) | `proto_metabolism`: `curated_rtca` (E), `reaction_universe` (A: generated SBML from a Wołos-2020-style rule set with reversible kinetics, side reactions, degradation, catalyst limits), `null_network` (A: randomized networks matched for compounds / reactions / energetic span / catalyst density) | `reaction_universe` (rules, ΔG′ via eQuilibrator, catalyst requirements) | flux-control analysis, element + free-energy ledger over the network, stiffness check vs libRoadRunner tolerances | `og-02-alt-reaction-universe`: gate `motifs-emerge-not-imposed` — persistent autocatalytic subnetworks detected post hoc; motif enrichment vs the matched nulls; the curated rTCA result becomes one class among three | distribution of persistent / autocatalytic subnetworks; enrichment vs null | Rule-set scope (C1–C3 only, or N/P-bearing from the start, folding og-res-N/P into the universe) |
| **4 3-D multisolute localization** | og-03 (`ThermophoreticTrapProcess`), the FEniCS cross-check (Pe ≳ 13 solver-sensitive), og-res-P's species-agnostic multiplier | `localization`: `fipy` (E), `fenics` (E, now with species Soret term), `pore_network` (A: reduced pore-network surrogate for ensembles, OpenPNM-style) | `pore_physics` (Baaske / Mast geometry, per-species D and S_T for phosphate, NH4, formate, acetate, pyruvate, amino acids, amphiphiles, nucleotide precursors) | mesh- and time-step convergence gate; head-to-head inside a declared trustworthy Péclet range; analytic bound `exp(Pe)` | `og-03-alt-colocalization`: gate `mixture-colocalizes` — co-localization / fractionation phase map for the simultaneous mixture, **no acceptance gate outside demonstrated convergence** (removes the >10⁸ headline from any gate) | co-localization envelope with convergence envelope | Whether og-03's current enrichment gate is re-stated at the resolvable Péclet (recommended) |
| **5 Endogenous boundary + growth/division** | og-04 (`ProtocellAssemblyProcess`), og-growth (`OsmoticGrowthDivisionProcess`), FMP §2.3–2.4 rewrites | `boundary`: `single_chain` (E), `mixed` (E), `thioester_aminothiol` (A); `AmphiphileSynthesisProcess` (A, from `molecules.dissolved.{acetate,formate}`); `BoundaryFormationStep` / `DivisionStep` / `LysisStep` / `ExtinctionStep` as `_add` / `_divide` / `_remove` rewrites on `agents: map[vg_individual]` | `amphiphile_assembly` (Jordan 2019 phase data under alkaline / saline / divalent conditions; Lu 2024 osmotic growth) | `ledger.rewrite_residual == 0` across every structural rewrite; partition residual on `_divide` | `og-04-alt-endogenous-boundary`: gate `boundary-forms-from-chemistry` (agents 0 → ≥1 with endogenous amphiphile; not with synthesis ablated); `og-growth-alt-physical-reproduction`: a ≥3-generation lineage in the agents map with daughter volumes summing to the mother's | first continuous chemistry → growing, dividing individual | Partition semantics for concentration maps (store `internal` as amounts + volume; FMP §9.1) |
| **6 Proto-energetics** (built — §6d; thioester pays from activity 0.10, Fe-redox from 0.80, the ion gradient only below P_H 1e-8 m/s, polyphosphate never; agreement 0.46) | og-energy (`GeochemicalDriveProcess`, `ProtoEnergyCurrencyProcess`), og-05 (`BioenergeticSelectionProcess`) | `energy_coupling`: `passive_gradient` (A), `h_na_gradient_leaky_membrane` (A), `thioester_acyl_phosphate` (E as carrier), `polyphosphate` (E), `fe_redox` (A) — all inside each protocell composite, autonomy = internal / (internal + external) power per individual | `energy_currencies` (Fe disproportionation drive already proposed; H+/Na+ permeabilities) | free-energy ledger: `free_energy_in ≥ work + dissipated` as an invariant | `og-energy-alt-internalization-threshold`: gate `internalization-pays` — passive vs increasingly active coupling, the point where energetic benefit exceeds leakage + maintenance, per class | energy-capture efficiency and internalization threshold | Replace og-05's population-mean `internalization` with per-individual autonomy (reads the same field) |
| **7 Competing heredity** | og-06 (`LineageReplicatorProcess` modes), FMP §2.5 | `heredity`: `compositional`, `network`, `peptide`, `rna_like`, `hybrid`, `mineral_state` (carved out of the one class), attached conditionally by `HeredityAttachmentStep` under matched resource + energy budgets, Gillespie at low copy number | `inheritance_budgets` (precursor availability, error rates, template costs) | information ledger: heritable bits per unit energy; mutual information estimator convergence | `og-06-alt-information-per-cost`: gates `ancestry-predicts-phenotype` (parent–offspring mutual information per class) and the information-per-cost frontier; og-06's "need not presume RNA" becomes a class-substitution result | information-per-cost frontier; transition to templated heredity | Defensible attachment thresholds (expert input; `hypothetical` and swept until then) |
| **6 Proto-energetics** | og-energy (`GeochemicalDriveProcess`, `ProtoEnergyCurrencyProcess`), og-05 (`BioenergeticSelectionProcess`) | `energy_coupling`: `passive_gradient` (A), `h_na_gradient_leaky_membrane` (A), `thioester_acyl_phosphate` (E as carrier), `polyphosphate` (E), `fe_redox` (A) — all inside each protocell composite, autonomy = internal / (internal + external) power per individual | `energy_currencies` (Fe disproportionation drive already proposed; H+/Na+ permeabilities) | free-energy ledger: `free_energy_in ≥ work + dissipated` as an invariant | `og-energy-alt-internalization-threshold`: gate `internalization-pays` — passive vs increasingly active coupling, the point where energetic benefit exceeds leakage + maintenance, per class | energy-capture efficiency and internalization threshold | Replace og-05's population-mean `internalization` with per-individual autonomy (reads the same field) |
| **7 Competing heredity** (built — §6e) | og-06 (`LineageReplicatorProcess` modes), FMP §2.5 | `heredity`: `compositional`, `network`, `peptide`, `rna_like`, `hybrid`, `mineral_state` (carved out of the one class), attached conditionally by `HeredityAttachmentStep` under matched resource + energy budgets, Gillespie at low copy number | `inheritance_budgets` (precursor availability, error rates, template costs) | information ledger: heritable bits per unit energy; mutual information estimator convergence | `og-06-alt-information-per-cost`: gates `ancestry-predicts-phenotype` (parent–offspring mutual information per class) and the information-per-cost frontier; og-06's "need not presume RNA" becomes a class-substitution result | information-per-cost frontier; transition to templated heredity | Defensible attachment thresholds (expert input; `hypothetical` and swept until then) |
| **8 Biochemical ecology** (built — §6f; malate held by the community of a carboxylating and a hydrogenating lineage and by neither alone, vanishing without sharing, sustained by oxaloacetate crossing between them, no cell complete; emerges above P_diacid 3e-9 m/s) | og-07 (`CrossFeedingMetacommunityProcess` capability vectors) | `proto_ecology`: real reaction networks per protocell (Phase-3 classes inside each agent), `SpatialCouplingStep` onto the Phase-4 fields, `BigraphicalReactiveSystem` exchange rules; `EcologyReducerStep` keeps og-07's gate names | `cnp_resources` + the Phase-3 universe | element ledger across agents + fields; exchange-rule firing counts | `og-07-alt-real-metabolite-exchange`: gate `community-function-precedes-cell-completeness` — a function present in the community union but in no lineage, sustained by real metabolite flux, not symbolic capability transfer | emergent cross-feeding / division of labor / robustness | Agent motion model (defer; point agents on fields first) |
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
   "fourteen" studies; adding `og-cal-vent-environment` and
   `og-02-alt-reaction-universe` makes sixteen. Left for the narrative owner
   (another session edits that text).
6. **Rule-set scope (Phase 3).** The universe is C/H/O only, linear skeletons,
   C ≤ 4 (so rTCA cannot close; formose can). Whether N/P-bearing rules
   (folding og-res-N / og-res-P in) and branched C5/C6 skeletons come next is
   the expert's call (`og-02-alt-reaction-universe.decisions_needed`).
