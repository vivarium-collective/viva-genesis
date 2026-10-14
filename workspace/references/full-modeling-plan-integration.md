# viva-genesis — Full Modeling Plan: deep integration architecture

Working architecture for integrating the expert's *Full Modeling Plan* (source:
`workspace/references/expert/viva-genesis-full-modeling-plan.pdf`, registered in
`workspace.yaml.expert_docs`) into the existing viva-genesis campaign. This is the
builder's document: it names the real files, classes, composites and
bigraph-schema shapes, says what already exists versus what to add, and orders the
work by the plan's section 18 priority list. It is tracked here so the design is
reviewable and executable, not a restatement of the PDF.

Framework facts asserted below were verified against the pinned stack in
`.venv` on 2026-10-13: `process-bigraph 1.8.5`, `bigraph-schema 1.7.0`,
`viva-superpowers 0.23.0`, `vivarium-workbench 0.4.1`, `bigraph-viz` present.

## 0. The thesis, and where the codebase stands against it

**Plan thesis.** Do not start with a cell. Build a geological world in which
biological organization must *emerge*, and let the Process Bigraph itself change
shape as localization, boundaries, growth, heredity and ecology appear. The
endpoint is a definition, not a target: *cells arise when processes previously
distributed across the environment become composed inside a persistent,
reproducing, heritable boundary.*

**Where we are.** The campaign already has the right stage sequence (og-00..08,
og-adv, and the N / P / proto-energetics / growth-division modules), real
simulators behind each stage (PHREEQC, FiPy, eQuilibrator, libRoadRunner), typed
ports with `_units` on every process, conservation residuals as contract
invariants, phase maps as the Decision view, an adversarial control, and a
three-view (World / Mechanism / Decision) viz convention. What it does **not**
have is the architecture the plan asks for:

| Plan element | Status in `viva_genesis/` today | Gap |
|---|---|---|
| Canonical biological schemas (shared types) | Each process declares its own `{"_type":"float","_units":...}` ports; store names differ per composite (`vent/H2` in og-00, `env/H2` in og-01, `pools/NH4` in og-res-N) | No shared type names; models are not substitutable by construction |
| One persistent environmental world across stages | Each composite builds its own `env`/`vent` store from scalar params; og-01's `env.pH` is a number copied from og-00's output by hand | Stages are separate simulations with hand-carried parameters, not one world with agents added |
| Structural rewrites (boundary / growth / division / extinction / conditional heredity) | `OsmoticGrowthDivisionProcess` counts divisions as an integer; `LineageReplicatorProcess` and `CrossFeedingMetacommunityProcess` keep populations as numpy arrays *inside* one process | No composite ever gains or loses a node at runtime; "division" is a counter, not a bigraph rewrite |
| Model substitution as experiment | `heredity_lineage_comparison(module=...)` and `proto_energetics(carrier=...)` select a variant by string **inside one process class**; og-00 has the real vs reduced generator pair | Only two interfaces have swappable models, and the swap is a config branch, not a class behind a shared face |
| Cross-cutting C-N-P + energetics | og-res-nitrogen, og-res-phosphorus, og-energy-proto-energetics are **separate studies with separate composites**; `cn_supply_ratio` lives only in the N composite | No shared molecule pool or energy ledger that threads through stages |
| Free-energy / matter / charge accounting across model boundaries | Per-process residuals (`charge_imbalance`, `n_mass_residual`, `p_mass_residual`, `energy_ledger_residual`, `osmolyte_balance_residual`) | No composite-level ledger that sums across processes and across the environment/individual boundary |
| Autonomy continuum readout | `OffGradientPersistenceProcess` emits `external_power` / `internal_power`; `BioenergeticSelectionProcess` emits `internalization` | Exists for one stage; not a persistent per-individual quantity |

Everything below is designed to close those gaps **by composition on top of the
existing processes**, never by replacing them. The 24 process classes and 14
generators stay valid; new work adds a schema module, a world composite, a
protocell composite, rewrite steps, model-registry wiring and ledger steps.

## 1. Canonical biological schemas — `viva_genesis/schemas.py`

### 1.1 Mechanism

bigraph-schema 1.7.0 supports named types with units, bounds and defaults:
`core.register_type(key, data)` / `core.register_types({...})` (verified:
`core.access({"_type":"float","_units":"molar"})` realizes a `Float molar`).
`build_core()` in `viva_genesis/core.py` is the single place every composite and
test obtains its core, so registering canonical types there makes them available
everywhere under stable names (`local:` process addresses already go through the
same hook).

**Add** `viva_genesis/schemas.py` exporting one dict `CANONICAL_TYPES` and a
`register_canonical_types(core)` function; **change** `build_core()` to call it
after `register_workspace_processes`. The module must import nothing heavy (it is
walked by `_iter_own_process_classes`, which swallows import errors, but types
must never be missing).

### 1.2 Atom types (units-typed leaves)

Reusable leaf types that every schema below is built from. Names are prefixed
`vg_` so they cannot collide with framework types.

```python
ATOMS = {
    "vg_concentration": {"_type": "float", "_units": "molar", "_min": 0.0},
    "vg_amount":        {"_type": "float", "_units": "mole", "_min": 0.0},
    "vg_rate":          {"_type": "float", "_units": "mole/second"},
    "vg_flux_density":  {"_type": "float", "_units": "mole/meter**2/second"},
    "vg_temperature":   {"_type": "float", "_units": "kelvin", "_min": 273.0, "_max": 673.0},
    "vg_pressure":      {"_type": "float", "_units": "pascal", "_min": 1.0e5, "_max": 5.0e7},
    "vg_ph":            {"_type": "float", "_units": "dimensionless", "_min": 0.0, "_max": 14.0},
    "vg_fraction":      {"_type": "float", "_units": "dimensionless", "_min": 0.0, "_max": 1.0},
    "vg_potential":     {"_type": "float", "_units": "volt"},
    "vg_current_density": {"_type": "float", "_units": "ampere/meter**2"},
    "vg_free_energy":   {"_type": "float", "_units": "kilojoule/mole"},
    "vg_power":         {"_type": "float", "_units": "watt"},
    "vg_energy":        {"_type": "float", "_units": "joule"},
    "vg_length":        {"_type": "float", "_units": "meter", "_min": 0.0},
    "vg_area":          {"_type": "float", "_units": "meter**2", "_min": 0.0},
    "vg_volume":        {"_type": "float", "_units": "liter", "_min": 0.0},
    "vg_velocity":      {"_type": "float", "_units": "meter/second"},
    "vg_permeability":  {"_type": "float", "_units": "meter/second", "_min": 0.0},
    "vg_time":          {"_type": "float", "_units": "second", "_min": 0.0},
    "vg_count":         {"_type": "integer", "_min": 0},
    "vg_id":            "string",
}
```

Existing processes already use exactly these unit strings (`molar`,
`mole/second`, `kelvin`, `meter/second`, `watt`, `dimensionless`, `liter`,
`meter**2`), so adopting the atoms is a rename of port declarations, not a change
of physics. The `_min`/`_max` bounds mirror the `contract.face` bounds the studies
already declare (og-00: `temperature 273–673 K`, `pressure 1e5–5e7 Pa`).

### 1.3 The eight canonical schemas (plan section 15)

Each is a `tree`-shaped named type. Representative fields come from the plan; the
`<-` annotations say which existing process port already produces that field.

```python
SCHEMAS = {
  # ---- Layer 1: physical world -------------------------------------------
  "vg_environment": {
      "temperature": "vg_temperature",        # <- Fipy/VentReactor outputs temperature
      "pressure": "vg_pressure",
      "pH": "vg_ph",                          # <- FipyReactiveTransport.pH
      "pH_ocean": "vg_ph",                    # <- hydrothermal_carbon_fixation env.pH_ocean
      "ionic_strength": "vg_concentration",   # <- carbon_fixation env.ionic_strength
      "flow_velocity": "vg_velocity",         # <- boundary.flow_velocity (og-00)
      "porosity": "vg_fraction",              # <- FipyReactiveTransport.porosity
      "pore_length": "vg_length",             # <- thermophoretic_concentration param
      "residence_time": "vg_time",            # <- ThermophoreticTrap.residence_time
      "heat": "vg_power",                     # <- Phreeqc.heat
  },
  "vg_minerals": {
      "phase_abundance": "map[vg_amount]",    # olivine, serpentine, brucite, magnetite, FeS, carbonate
      "surface_area": "vg_area",
      "catalytic_sites": "vg_amount",         # <- carbon_fixation catalyst.active (today a 0/1 scalar)
      "fes_activity": "vg_fraction",          # <- reduced_nitrogen_reactor catalyst.fes_activity
      "conductivity": {"_type": "float", "_units": "siemens/meter"},
      "passivation": "vg_fraction",
      "porosity_feedback": "vg_fraction",     # mineral growth -> porosity change (Stage 0 add)
  },
  "vg_molecules": {
      # single pool keyed by species; every stage reads/writes THIS map.
      "dissolved": "map[vg_concentration]",   # CO2, H2, DIC, formate, acetate, pyruvate, OAA,
                                              # malate, succinate, NO3, NO2, NH4, N2, amino_precursor,
                                              # phosphate, polyphosphate, reactive_P,
                                              # amphiphile, thioester, acyl_phosphate, polyP, ...
      "adsorbed": "map[vg_concentration]",    # mineral-surface retained pool (Stage III add)
      "polymers": "map[vg_concentration]",    # peptide / RNA-like pools (Stage VI)
      "catalysts": "map[vg_fraction]",        # effective activity per catalyst class
  },
  "vg_energy": {
      "redox_potential": "vg_potential",      # <- Phreeqc.pe (convert pe -> Eh)
      "electric_potential": "vg_potential",   # <- PhGradientNernstPlanck.electric_potential
      "pmf": "vg_potential",                  # <- ProtonBudget.pmf (loaded)
      "pmf_open": "vg_potential",             # <- PhGradientNernstPlanck.pmf
      "current_density": "vg_current_density",
      "ion_gradients": "map[vg_concentration]",  # H+, Na+ inside/outside deltas (Stage V)
      "stored_work": "vg_energy",             # <- ProtoEnergyCurrency.energy_stored
      "dissipated": "vg_energy",              # <- ProtoEnergyCurrency.energy_dissipated
      "energy_charge": "vg_fraction",         # <- ProtoEnergyCurrency.energy_charge_fraction
      "drive_free_energy": "vg_free_energy",  # <- GeochemicalDrive.drive_free_energy
  },
  # ---- Layer 2: boundary ---------------------------------------------------
  "vg_boundary": {
      "area": "vg_area",                      # <- ProtocellAssembly.membrane_area
      "composition": "map[vg_fraction]",      # <- mix_fraction (today one scalar)
      "permeability": "map[vg_permeability]", # per-species; <- ProtocellAssembly.permeability
      "charge": "vg_potential",               # membrane potential (Stage V)
      "integrity": "vg_fraction",             # 1 = intact; lysis when -> 0  <- Osmotic.lysed
      "tension": {"_type": "float", "_units": "newton/meter"},
  },
  # ---- Layer 3: individual -------------------------------------------------
  "vg_individual": {
      "id": "vg_id",
      "volume": "vg_volume",                  # <- OsmoticGrowthDivision.volume
      "internal": "vg_molecules",             # the individual's OWN molecule pool
      "boundary": "vg_boundary",
      "energy": "vg_energy",                  # the individual's OWN energy state
      "maintenance_flux": "vg_power",         # <- BioenergeticSelection.maintenance_power
      "growth_rate": {"_type": "float", "_units": "1/second"},  # <- Osmotic.net_growth
      "division_state": "vg_fraction",        # volume / division_threshold
      "persistence": "vg_time",               # age since boundary formation
      "autonomy": "vg_fraction",              # internal_power / (internal+external)  <- OffGradient
      "heredity": "maybe[vg_heredity]",       # ATTACHED CONDITIONALLY (section 2.5)
  },
  # ---- Layer 4: heredity + lineage/ecology ---------------------------------
  "vg_heredity": {
      "mode": "string",                       # compositional | network | peptide | rna_like | hybrid | mineral
      "inherited_state": "map[vg_fraction]",  # composition vector (GARD) or network occupancy
      "sequence": "maybe[string]",            # template modes only
      "fidelity": "vg_fraction",              # <- heredity_lineage per_site_fidelity
      "mutation_rate": {"_type": "float", "_units": "1/second"},
      "information_content": {"_type": "float", "_units": "bit"},
      "heritability": "vg_fraction",          # <- LineageReplicator.heritability
  },
  "vg_lineage": {
      "parent_id": "vg_id",
      "lineage_id": "vg_id",
      "generation": "vg_count",               # <- LineageReplicator.lineage_depth
      "position": "tuple[vg_length,vg_length]",
      "uptake": "map[vg_rate]",               # per-species exchange with the shared field
      "secretion": "map[vg_rate]",
      "interaction": "map[vg_fraction]",      # cross-feeding / parasitism weights per neighbour
  },
}
```

Register as `core.register_types({**ATOMS, **SCHEMAS})`. Composite stores are
then declared as e.g. `"world": {"_type": "vg_environment", ...}` and a process
port as `"environment": "vg_environment"` or a sub-field `"vg_concentration"`.

### 1.4 Port mapping of existing processes (what makes models substitutable)

The point of the schemas is that two different model classes expose **the same
face**, so a composite can swap the `address` and nothing else changes. Today
the faces differ in trivial ways that block that. The migration is per-interface
(section 4 gives the interface list); here is the mapping for the processes that
exist:

| Existing process (file) | Port today | Canonical port (schema field) |
|---|---|---|
| `PhreeqcSerpentinizationProcess`, `SerpentinizationReproductionProcess` (`geochemistry/`) | `H2`, `alkalinity`, `heat`, `H2_flux`, `pe` | `molecules.dissolved.H2`, `molecules.dissolved.alkalinity`, `environment.heat`, `rates.H2` (`vg_rate`), `energy.redox_potential` |
| `FipyReactiveTransportProcess`, `VentReactorReproductionProcess` (`transport/`) | `temperature`, `pH`, `porosity` | `environment.temperature/pH/porosity` |
| `PhGradientNernstPlanckProcess`, `ProtonBudgetProcess` (`electrochemistry/`) | `pH_vent`, `pH_ocean`, `pmf`, `pmf_open`, `electric_potential`, `current_density` | `environment.pH`, `environment.pH_ocean`, `energy.pmf`, `energy.pmf_open`, `energy.electric_potential`, `energy.current_density` |
| `EquilibratorThermoStep` (`protometabolism/thermo.py`) | `dg_*`, `feasible_*` | `energy.reaction_dg` (`map[vg_free_energy]`), `energy.feasible` (`map[vg_fraction]`) — new map-valued fields so new species need no new ports |
| `CarbonFixationProcess` | `H2`, `CO2`, `formate`, `acetate`, `pyruvate`, `catalyst_activity`, `net_carbon_flux` | `molecules.dissolved.{H2,CO2,formate,acetate,pyruvate}`, `minerals.catalytic_sites`, `rates.carbon` |
| `RoadRunnerNetworkProcess` | `feed_pyruvate`, `feed_CO2`, `OAA`, `malate`, `succinate`, `acetate`, `autocatalytic_gain`, `network_connected` | `molecules.dissolved.*` (same map), `diagnostics.autocatalytic_gain`, `diagnostics.network_connected` |
| `ThermophoreticTrapProcess` | `enrichment_factor`, `residence_time`, `accumulation_peclet` | `localization.enrichment` (`map[vg_fraction]`, per species — plan asks for species-specific thermophoresis), `environment.residence_time` |
| `ProtocellAssemblyProcess` (`membranes/`) | `membrane_area`, `permeability`, `compartment_volume`, `viable_compartments`, `retention`, `access` | `boundary.area`, `boundary.permeability` (map), `individual.volume`, `diagnostics.viable_compartments`; **plus a new `assembly_event` boolean that the boundary-formation rewrite step consumes (section 2.2)** |
| `OsmoticGrowthDivisionProcess` (`compartments/`) | `volume`, `osmotic_pressure`, `division_event`, `lysed` | `individual.volume`, `individual.division_state`, `boundary.integrity`; the integer `division_count` is replaced by the **count of daughters in the `agents` map** |
| `GeochemicalDriveProcess`, `ProtoEnergyCurrencyProcess` (`bioenergetics/proto_energetics.py`) | `drive_free_energy`, `energy_charge*`, `energy_stored`, `energy_dissipated`, `energy_ledger_residual` | `energy.drive_free_energy`, `energy.energy_charge`, `energy.stored_work`, `energy.dissipated`, `ledger.residual` |
| `BioenergeticSelectionProcess`, `EnvironmentalDeclineProcess` | `electric_potential`, `internalization`, `external_power`, `internal_power` | `energy.electric_potential`, `individual.autonomy`, `ledger.external_power`, `ledger.internal_power` |
| `HeredityReplicatorProcess`, `LineageReplicatorProcess` (`heredity/`) | `information_retention`, `functional_fraction`, `heritability`, `lineage_depth` | `heredity.information_content`, `heredity.heritability`, `lineage.generation` — and the per-agent population arrays become **per-individual `vg_heredity` state** (section 2.5) |
| `CrossFeedingMetacommunityProcess` (`ecology/`) | `metacommunity_robustness`, `capability_diversity` | `lineage.uptake/secretion/interaction` per individual; the summary scalars become a `proto_ecology` Step reducer |
| `OffGradientPersistenceProcess`, `EnvironmentalRelaxationProcess` (`autonomy/`) | `gradient_support`, `mineral_access`, `feed`, `survivors`, `external_power`, `internal_power` | `environment` fields scaled by an **ablation Step** (section 6, Stage VIII), `individual.autonomy` |
| `ReducedNitrogenProductionProcess`, `PhosphorusSpeciationProcess` (`geochemistry/`) | `NO3/NO2/NH4/N2/amino_precursor`, `phosphate/polyphosphate/reactive_P/mineral_P`, `cn_supply_ratio` | all into `molecules.dissolved.*`; `mineral_P` into `minerals.phase_abundance.apatite`; `cn_supply_ratio` into the resource-budget Step (section 5) |

Migration policy: **do not rewrite the 24 processes in one PR.** Give each
process a canonical face via a thin wrapper in the same module (e.g.
`CarbonFixationProcess` keeps its ports; a new `CarbonFixationCanonical(Process)`
subclass overrides `inputs()/outputs()` with the canonical names and maps in
`update()`), register both, and let the new world composite address the
canonical one. When an interface has two canonical models the old port names can
be retired. This keeps og-00..08 and their canonical runs reproducible while the
architecture lands.

### 1.5 Contract audit

bigraph-schema's `contract_audit` already parses `_units` with pint and flags
`bad_units`. **Add** `tests/test_schemas.py`: every `SCHEMAS` leaf resolves via
`core.access`, every unit string parses, and every canonical-face process's
`inputs()/outputs()` keys are a subset of the schema fields (the substitutability
test — it is what makes "swap a model" a safe operation).

## 2. The dynamic / structural-rewrite architecture

### 2.1 What process-bigraph can actually do (verified)

process-bigraph 1.8.5 supports **true runtime rewrites** of the composite tree;
no fallback is needed. Three mechanisms, in increasing generality:

1. **Structural update sentinels on `map[...]` stores.** A Process or Step
   whose output port is typed `map[<schema>]` may return
   `{"_add": {key: subtree, ...}}`, `{"_remove": [key, ...]}` (or `"all"`), or
   `{"_divide": {"mother": key, "daughters": {k1: override, k2: override}}}`.
   `bigraph_schema.methods.apply.apply(Map, ...)` applies them, emits
   `NodeAdded` / `NodeRemoved` / `Divided` events, and the Composite's
   `apply_updates` detects the sentinel and re-realizes the tree, instantiating
   any **new processes declared inside the added subtree** (`_add` of a dict
   containing `{"_type": "process", "address": ..., "config": ..., "inputs":
   ..., "outputs": ...}` creates a running process). `_divide` is two-phase:
   a type-driven split of the mother's state (bulk fields binomially, `_set`
   fields copied, etc. — `bigraph_schema.methods.divide`) followed by the
   caller's per-daughter overrides (fresh process links so daughters do not
   share the mother's instances).
2. **Nested `local:Composite` as a process.** A whole composite document can be
   a node of the outer composite (`{"_type": "process", "address":
   "local:Composite", "config": {"state": <inner doc>, "bridge": {"inputs":
   wires, "outputs": wires}}}`), with `bridge.conduits` for outputs that must
   reach the outer tree *only* (this is exactly how an inner protocell
   composite emits its own `_divide` into the outer `agents` map without also
   creating nested daughters inside itself — see the `CompositeDivision`
   comments in `process_bigraph/composite.py`).
3. **Milner reaction rules.** `bigraph_schema.assembly.ReactionRule(redex,
   reactum, instantiation, rate, label)` with `run_reactions` and two ready
   processes: `local:ReactionStep` (fires to quiescence when its
   `state: tree[node]` input changes) and `local:BigraphicalReactiveSystem`
   (a Process with `deterministic | stochastic | gillespie` modes). Nodes match by
   `_control`; the target store **must** be typed `tree[node]` / `map[node]` or
   `_control` tags are dropped and rules silently no-op.

Design choice: **mechanism 1 (sentinels) is the workhorse for the five
biological rewrites, mechanism 2 is how a protocell is represented, mechanism 3
is reserved for the ecology stage** (horizontal exchange and engulf/merge are
naturally rules over neighbours; the individual-level rewrites are better
expressed as a Step that reads canonical state and emits a sentinel, because the
assembly / division / lysis criteria are physical thresholds, not graph
patterns).

### 2.2 The world document shape

The top-level composite (`geochemical_world`, section 3) has this skeleton — the
part that never changes shape is `world`; the part that changes is `agents`:

```python
{
  "world": {                      # layer 1 — persists through all stages
      "environment": {"_type": "vg_environment", ...},
      "minerals":    {"_type": "vg_minerals", ...},
      "molecules":   {"_type": "vg_molecules", ...},
      "energy":      {"_type": "vg_energy", ...},
      "fields":      {...},       # FiPy spatial fields (Stage III): map[array]
  },
  "localized": {"_type": "map[vg_molecules]"},   # persistent chemical regions (Stage III)
  "agents":    {"_type": "map[vg_individual]"},  # EMPTY until boundary formation
  "ledger":    {...},             # section 5.3
  "serpentinization": {process ...}, "transport": {process ...}, ...   # world processes
  "boundary_formation": {"_type": "step", "address": "local:BoundaryFormationStep", ...},
  "extinction":         {"_type": "step", "address": "local:ExtinctionStep", ...},
  "heredity_attachment":{"_type": "step", "address": "local:HeredityAttachmentStep", ...},
}
```

Early in a run `agents == {}` — there is no cell object, which is the plan's
"early in the simulation there is no cell object" realized literally. Every
rewrite below is a Step with `outputs: {"agents": "map[vg_individual]"}` (or
`localized`) returning a sentinel.

### 2.3 Boundary formation (localized region -> protocell composite)

**Add** `viva_genesis/compartments/rewrites.py` with `BoundaryFormationStep`:

- inputs: `localized: map[vg_molecules]`, `world_env: vg_environment`,
  `assembly: {viable_compartments, membrane_area, permeability}` (from
  `ProtocellAssemblyProcess`, which already computes the Jordan-2019 viability
  window and `cac`), `persistence: map[vg_time]` (age of each localized region,
  from the Stage III retention Step).
- criterion (plan: "amphiphile concentration and local persistence cross
  assembly criteria"): `localized[r].dissolved.amphiphile >= cac` **and**
  `persistence[r] >= tau_min` **and** `assembly.viable_compartments > 0`.
- output: `{"agents": {"_add": {new_id: protocell_composite(region_state, ...)}},
  "localized": {"_remove": [r]}}` — the region's molecule pool *becomes* the
  individual's `internal` pool (matter conserved by construction: the ledger
  Step checks that `sum(localized) + sum(agents.internal)` is unchanged by the
  rewrite).

`protocell_composite(...)` is a plain function (in
`viva_genesis/composites/proto_individual.py`, section 3) returning a
`local:Composite` node whose inner document holds the individual's own
processes: `OsmoticGrowthDivisionProcess` (growth), a `ProtoEnergyCurrencyProcess`
(internal energetics), a `MembraneExchangeProcess` (new; per-species
permeability x gradient, writing both `internal` and, through the bridge,
`world.molecules`), and a `DivisionStep` / `LysisStep` whose sentinel outputs are
declared as **conduits** so they land in the outer `agents` map.

### 2.4 Growth, division, extinction

- **Growth** is not a rewrite: `OsmoticGrowthDivisionProcess` already grows
  `volume` from osmotic influx and raises `division_state`; `boundary.area`
  follows from `membrane_area` production (amphiphile synthesis, Stage IV).
- **Division** (`DivisionStep`, inner): input `individual` (whole
  `vg_individual`), config `division_threshold`, `partition_seed`. When
  `division_state >= 1.0` it returns, via the conduit,
  `{"agents": {"_divide": {"mother": my_id, "daughters": {f"{my_id}.0": override0,
  f"{my_id}.1": override1}}}}`. The type-driven phase halves `volume`, binomially
  partitions every `internal.dissolved` / `polymers` / `catalysts` entry and
  `boundary.area`; the overrides supply fresh process links (new `config.id`,
  new RNG seeds) and the **stochastic partition of `heredity.inherited_state`**
  — this is where "stochastic partitioning of molecules, catalysts, membrane
  components and hereditary material" (plan) lives. One individual composite
  becomes two. `lineage.parent_id` / `generation` are set in the overrides.
- **Extinction / lysis** (`ExtinctionStep`, outer — it needs the world pool):
  inputs `agents`, `world_molecules`. Criterion: `boundary.integrity <= 0`
  (osmotic lysis, from `lysed`) **or** sustained `ledger.energy_balance < 0`
  over `maintenance_window` ticks (plan: "sustained negative energy/maintenance
  balance"). Output: `{"agents": {"_remove": [id]}, "world_molecules":
  {"dissolved": {species: +amount, ...}}}` — internal material dissolves back
  into the environment (again conserved: the ledger checks it).

### 2.5 Conditional heredity attachment

`vg_individual.heredity` is `maybe[vg_heredity]`, i.e. absent by default.
`HeredityAttachmentStep` (outer) reads each agent's `internal.polymers`,
`internal.dissolved.{nucleotide_precursor, amino_precursor, reactive_P}` and the
fidelity the chosen heredity model class reports (`vg_heredity.fidelity`), and
only when precursor availability, copying chemistry and fidelity cross their
thresholds does it return `{"agents": {id: {"heredity": {<vg_heredity initial>},
"heredity_process": {"_type": "process", "address": "local:<HeredityModel>",
...}}}}` — an `_add`-style insertion of **both state and a new process** into
that individual. Which `<HeredityModel>` is attached is the model-substitution
knob for the heredity interface (section 4). Heredity therefore appears as a
change in the bigraph (a new node under one individual), which is the plan's
"heredity adds inherited state".

### 2.6 Ecology by composition, rules for exchange

Many individuals sharing `world.fields` is already the shape above (`agents` is a
map). Stage VII adds (a) `lineage.position` and a `SpatialCouplingStep` that maps
each agent's `uptake`/`secretion` onto the FiPy field cells, and (b) a
`BigraphicalReactiveSystem` with rules over `agents` typed `map[node]`:
`horizontal_exchange` (redex: two agents within `r_contact`; reactum: catalyst /
polymer transferred with `rate`), `engulf` (optional). This is where mechanism 3
earns its keep — those are graph-pattern events.

### 2.7 Emission and provenance of rewrites

Every rewrite emits a `NodeAdded`/`NodeRemoved`/`Divided` event from
bigraph-schema's event system. **Add** `StructuralEventLogStep` (in
`rewrites.py`) that subscribes to those events and writes an append-only table
`events/{time, kind, path, mother, daughters, cause}` through the existing
`ParquetEmitter` path list — the raw data for the "bigraph restructuring" figure
(section 7) and for the `rewrite_count` family of behavior-test readouts.

### 2.8 What to prove first (spike)

Before any stage uses this, **add** `tests/test_structural_rewrites.py` with a
toy world: one `localized` region, `BoundaryFormationStep` promotes it to an
`agents` entry containing a `local:Composite` with `Grow`-like dynamics and a
`DivisionStep` conduit; assert `len(agents)` goes 0 -> 1 -> 2, that total
`internal + localized + world` amount is conserved to 1e-12 across both rewrites,
that `ExtinctionStep` returns the mass to `world`, and that the Parquet event log
has three rows. This spike de-risks the entire architecture in ~200 lines.

## 3. Reusable composite layers — mapping the plan's nine onto the fourteen

Principle: **one world, agents added by composition.** The nine plan composites
become *generator functions that return document fragments* which a stage
composite merges (process-bigraph's `deep_merge`), not fourteen independent
simulations. Existing generators stay registered for their studies' canonical
runs; the new ones are added under `viva_genesis/composites/layers/`.

| Plan composite | Builds from (existing) | Add / refactor |
|---|---|---|
| `geochemical_world` | `serpentinizing_vent_reactor` (`PhreeqcSerpentinizationProcess` + `FipyReactiveTransportProcess`) and its reduced twin | New `layers/geochemical_world.py::geochemical_world(core, *, engine="phreeqc" \| "reduced", ...)` returning the `world` block of section 2.2 with canonical stores. Add `MineralEvolutionProcess` (precipitation/dissolution updating `minerals.phase_abundance`, `surface_area`, `porosity_feedback`) — the plan's Stage 0 "porosity/permeability feedback" that og-00 lacks; feed `porosity_feedback` into `FipyReactiveTransportProcess.porosity`. |
| `electrochemical_interface` | `PhGradientNernstPlanckProcess` + `ProtonBudgetProcess` (og-01) | Wrap as `layers/electrochemical_interface.py`. Add `MineralConductivityProcess` (fluid `energy.redox_potential` + `minerals.conductivity/passivation` -> `energy.current_density`) so `gradient_efficiency` is **derived** from circuit physics instead of a free scalar (the open og-01 decision in `investigation.yaml`). |
| `prebiotic_chemistry` | `CarbonFixationProcess` + `EquilibratorThermoStep` (C), `RoadRunnerNetworkProcess` (network), `ReducedNitrogenProductionProcess` (N), `PhosphorusSpeciationProcess` (P), `GeochemicalDriveProcess` + `ProtoEnergyCurrencyProcess` (currency) | `layers/prebiotic_chemistry.py` merges all six onto the **single** `world.molecules.dissolved` map (section 5). The four currently separate composites' stores (`products/`, `net/`, `pools/`, `pool/`) collapse into that map. |
| `pore_localization` | `ThermophoreticTrapProcess` (og-03) + FiPy fields | `layers/pore_localization.py`: species-specific thermophoresis (Soret coefficient per species, plan Stage III), `AdsorptionProcess` (`dissolved` <-> `adsorbed`), `DegradationProcess`, and `LocalizationStep` that **creates `localized[r]` entries** (an `_add` sentinel) when enrichment x retention beats destruction in a cell — the first rewrite in the sequence. |
| `proto_boundary` | `ProtocellAssemblyProcess` (og-04) | `layers/proto_boundary.py`: add `AmphiphileSynthesisProcess` (endogenous fatty-acid/alkanol from `molecules.dissolved.{acetate, formate}` — plan's "endogenous amphiphile production") feeding `dissolved.amphiphile`; `ProtocellAssemblyProcess` reads it instead of its `amphiphile_conc` config; `BoundaryFormationStep` from section 2.3. |
| `proto_individual` | `OsmoticGrowthDivisionProcess` (og-growth-division) | `composites/proto_individual.py::protocell_composite(...)` — the nested `local:Composite` document of section 2.3 with `MembraneExchangeProcess` (new), `DivisionStep`, `LysisStep`. |
| `proto_bioenergetics` | `BioenergeticSelectionProcess` + `EnvironmentalDeclineProcess` (og-05), `ProtoEnergyCurrencyProcess` | `layers/proto_bioenergetics.py`: `MembraneElectrochemistryProcess` (delta-pH, membrane potential, H+/Na+ leak from `boundary.permeability`) + `IonTransportProcess` (primitive pumping at energetic cost) + the currency process **inside** each protocell composite; `BioenergeticSelectionProcess`'s population-mean `internalization` is replaced by the per-individual `autonomy` field. |
| `proto_heredity` | `LineageReplicatorProcess` (`module=template\|compositional\|hybrid\|none`), `HeredityReplicatorProcess` | Split the `module` branches into **separate Process classes behind one face** (section 4): `CompositionalHeredity`, `NetworkHeredity`, `PeptideHeredity`, `RnaLikeHeredity`, `HybridHeredity`, `MineralStateHeredity`. `HeredityAttachmentStep` attaches the configured one. |
| `proto_ecology` | `CrossFeedingMetacommunityProcess` (og-07) | `layers/proto_ecology.py`: `SpatialCouplingStep`, the exchange `BigraphicalReactiveSystem`, and `EcologyReducerStep` recomputing og-07's `metacommunity_robustness`, `capability_diversity`, `luca_capability_overlap` **from the agents map** so og-07's gates keep their names. |

Stage composites are then compositions:
`og-00 = geochemical_world`; `og-01 = + electrochemical_interface + prebiotic_chemistry(C)`;
`og-02 = + prebiotic_chemistry(network)`; `og-03 = + pore_localization`;
`og-04 = + proto_boundary (+ proto_individual on formation)`; ... `og-08 =
everything + ablation Step`. The same `world` state dict is what each stage
starts from — **add** `viva_genesis/composites/layers/stage.py::stage_composite(stage,
**model_choices)` as the one generator the studies call, with the stage index
selecting which layers merge in.

## 4. Model substitution as experiment

### 4.1 Interfaces and swappable model classes (plan section 16)

Each interface is a canonical face (section 1) plus a registry of classes that
implement it. `E` = exists, `A` = add.

| Interface (face) | Model classes | Note |
|---|---|---|
| `environment` (`vg_environment` + `vg_minerals` producers) | `PhreeqcSerpentinizationProcess` + `FipyReactiveTransportProcess` (E, deep alkaline vent); `SerpentinizationReproductionProcess` + `VentReactorReproductionProcess` (E, reduced); `ShallowVentEnvironment` (A, Barge & Price: lower T, higher O2, Fe-oxyhydroxide); `TerrestrialGeothermalEnvironment` (A, Mulkidjanian: K+/Zn, drying cycles); `GenericNonequilibriumEnvironment` (A — promote `viva_genesis/adversarial.py` into a class) | og-adv already shows the gates reject the generic control; this makes it a first-class swap |
| `carbon_fixation` | `CarbonFixationProcess` (E, empirical Preiner/Hudson kinetics); `MineralSurfaceMicrokineticModel` (A, adsorption + elementary steps on Ni/Fe/S sites from `minerals.catalytic_sites`); `CurrentLimitedFixationModel` (A, rate = `energy.current_density` / nF x faradaic efficiency); `AlternativeCatalystModel` (A, awaruite/greigite parameter sets of the microkinetic model) | Distinguishes "failure is thermodynamic vs kinetic vs electrical" (plan Stage I) |
| `proto_metabolism` | `RoadRunnerNetworkProcess` (E, curated rTCA fragment, SBML) ; `BroadC123Network` (A, larger SBML from the enrichment plan's C1/C2/C3 landscape, same class, different SBML); `AutocatalyticSetModel` (A, RAF detection over realized fluxes); `ConstraintBasedModel` (A, cobra-style FBA on the same stoichiometry, optional) | All write `molecules.dissolved`; `diagnostics.autocatalytic_gain` / `network_connected` are the shared readouts |
| `localization` | `ThermophoreticTrapProcess` (E, idealized trap); `IrregularPoreFipyModel` (A, FiPy ADR on an irregular pore geometry from `minerals`); `AdsorptionDominatedRetention` (A); `MixedLocalization` (A = composition of the three) | Phase maps re-run per class |
| `boundary` | `ProtocellAssemblyProcess` with `mix_fraction=0` (E, single-chain), `>0` (E, mixed); `ThioesterAminothiolMembrane` (A, different viability window and permeability law) | Already a parameter-selected pair; becomes class-selected |
| `heredity` | `CompositionalHeredity`, `NetworkHeredity`, `PeptideHeredity`, `RnaLikeHeredity`, `HybridHeredity`, `MineralStateHeredity` (all A, carved out of `LineageReplicatorProcess` / `HeredityReplicatorProcess`) | og-06's result ("heredity need not presume RNA") becomes a model-substitution result by construction |

### 4.2 Wiring: a model registry and a config that selects the class

**Add** `viva_genesis/models.py`:

```python
INTERFACES = {
  "environment":    {"face": ("vg_environment", "vg_minerals"), "models": {...}},
  "carbon_fixation": {"face": "carbon_fixation_face", "models": {
       "empirical": "local:CarbonFixationProcess",
       "microkinetic": "local:MineralSurfaceMicrokineticModel",
       "current_limited": "local:CurrentLimitedFixationModel"}},
  ...
}
def resolve(interface, name) -> address
def assert_face(core, interface, address)   # inputs/outputs ⊆ canonical face
```

`stage_composite(stage, models={"carbon_fixation": "microkinetic", ...})`
resolves addresses through `resolve()`; `assert_face` runs at build time so a
model that does not honour the face fails loudly. Studies select models the
same way they select parameters today — in `study.yaml.baseline[].params` the
new keys are `model_<interface>` (strings), which the workbench already renders
as string parameters (cf. `heredity_lineage_comparison.module`).

### 4.3 How a study runs the same gates against alternative structures

`sweep_grid` (`viva_genesis/sweep.py`) already takes any generator kwargs as grid
axes. Model choice is just **a categorical axis**: `sweep_grid(stage_composite,
axes={"model_carbon_fixation": ["empirical","microkinetic","current_limited"],
"h2": logspace, "ph_vent": linspace}, reducers=...)`. The existing phase-map
builders in `phase_maps.py` then produce one Decision surface per model class
with identical axes and identical reducers (`carbon_sustained_throughput`, ...),
and the study's `behavior_tests` (`net-carbon-flux-nonzero-region`, etc.) are
evaluated per class by the existing `evaluators.py` hook — no new grading code.

**Reporting model-structure vs parameter uncertainty.** Add one reducer family
to `phase_maps.py` (spec only here; implementation after the viz agents finish):

- `pass_fraction[m]` — fraction of the parameter grid where model `m` passes
  the gate (parameter uncertainty, per model).
- `structure_agreement` — fraction of grid points where **all** models agree
  (pass/pass or fail/fail). `1 - structure_agreement` is the share of the
  parameter space where the *answer depends on which model you believe* —
  the model-structure uncertainty the plan wants separated.
- `decision_envelope` — the union and intersection pass regions across models;
  reported as two contours on one phase map (section 7).

Each study's `findings[]` then carries, per gate: `parameter_region` (the
intersection), `structure_sensitive_region` (union minus intersection), and
the list of model classes compared — so a finding can say "sustained carbon
fixation is robust to kinetic model choice above 1 mM H2 but depends on the
current-limited assumption below it", which is a stronger and more honest claim
than the current single-model band.

## 5. Cross-cutting layers: C-N-P, proto-energetics, free-energy accounting

### 5.1 One molecule pool, resource budget as a Step

The separate N / P / energy studies prove each module alone. To make them
cross-cutting: all six chemistry processes write **the same**
`world.molecules.dissolved` map (section 3, `prebiotic_chemistry`). **Add**
`ResourceBudgetStep` (`viva_genesis/protometabolism/budget.py`): reads
`dissolved.{formate,acetate,pyruvate,NH4,amino_precursor,reactive_P}` and the
elemental stoichiometry table in `viva_genesis/data/`, computes `C:N`, `C:P`,
`N:P` supply ratios and `limiting_resource ∈ {C,N,P,energy}` = argmin of
supply/demand, and writes `diagnostics.limiting_resource` (+ one `vg_fraction`
per element). This is the plan's "which resource first limits
persistence/growth?" readout and it becomes a **gate on every stage from II
onward**, not a side study.

Inside each protocell composite, the same Step runs on `individual.internal`,
and `MembraneExchangeProcess` is the only thing moving C/N/P across the
boundary — so the boundary's selective permeability (og-04's "retention
without isolation") is literally the C-N-P coupling of the individual.

### 5.2 Proto-energetics threaded through the individual

`GeochemicalDriveProcess` + `ProtoEnergyCurrencyProcess` run **twice**: once in
the world (environmental drive -> `world.energy.stored_work`, the geological
energy pool) and once inside each protocell (internal redox / membrane coupling
-> `individual.energy.stored_work`). `individual.autonomy` =
`internal_power / (internal_power + external_power)` is computed per individual
by the currency process (the fields already exist on
`OffGradientPersistenceProcess` and `BioenergeticSelectionProcess`; move the
formula into the currency process so it is one definition). Stage V's
"autonomy metric" and Stage VIII's "autonomy is continuous" are then the same
state field read at different times.

### 5.3 The ledger: matter, charge, free energy across model boundaries

**Add** `viva_genesis/ledger.py` with `ConservationLedgerStep`:

- inputs: `world.molecules`, `localized`, `agents` (whole map), `rates.*`,
  boundary fluxes from every exchange process, and the per-process residuals
  that already exist (`charge_imbalance`, `n_mass_residual`, `p_mass_residual`,
  `osmolyte_balance_residual`, `energy_ledger_residual`,
  `flux_divergence_residual`).
- outputs `ledger.{C,N,P,charge}_total`, `ledger.{C,N,P}_residual` (world +
  localized + all individuals - inflow + outflow), `ledger.free_energy_in`
  (vent drive x time), `ledger.free_energy_work` (sum of `energy_work`),
  `ledger.free_energy_dissipated`, `ledger.energy_balance` per individual, and
  `ledger.rewrite_residual` (the amount moved by the most recent structural
  event, which must be zero).
- `contract.conditions` on every stage gain `ledger_C_residual < tol`,
  `ledger_charge_residual < tol`, `free_energy_in >= work + dissipated`
  (second law as an invariant) — this is the plan's "maintain matter, charge
  and free-energy accounting across model boundaries", and it is what makes a
  rewrite trustworthy: a boundary forming, a cell dividing or dying must not
  create or destroy atoms or free energy.

### 5.4 Parameter provenance tier as a type annotation

Every config parameter already has `_units`; **add** a `_provenance` key
(`measured | calibrated | inferred | extrapolated | hypothetical`) to the
canonical process `config_schema`s and a `ProvenanceAuditStep`-free check in
`tests/test_schemas.py` that every parameter of a canonical model declares one.
The study report can then colour the parameter table by tier (section 7) —
the plan's "carry parameter provenance explicitly".

## 6. Per-stage implementation roadmap (plan section 18 order)

Priority numbers are the plan's. Each item: built today / add / new gate /
World-Mechanism-Decision viz it needs. Viz items are **specified only** here
(section 7) — `phase_maps.py`, `viz_phase.py`, `viz.py` and per-study
`study.yaml` viz blocks are being edited by the three-view agents.

**P1 — Canonical schemas + `geochemical_world` (Stage 0).**
Built: `serpentinizing_vent_reactor` (PHREEQC + FiPy), reduced twin, og-00
gates (`vent-pH-in-lostcity-range`, conservation). Add: `schemas.py` +
`build_core` registration; `layers/geochemical_world.py`; `MineralEvolutionProcess`
(FeS/carbonate/brucite precipitation updating `minerals` and `porosity_feedback`);
`ConservationLedgerStep`; the rewrite spike test (section 2.8). New gate:
`reactor-stays-open` — H2 flux, pH >= 9, catalytic phase abundance and porosity
above a floor **co-persist** for the settled window (plan Stage 0 key test:
"does the reactor poison or seal itself?"). Viz: World = existing vent
cross-section + a mineral-phase panel; Mechanism = porosity-feedback loop
(precipitation -> porosity -> flow -> H2); Decision = (olivine_rate x
flow_velocity) phase map with "sealed / poisoned / open" regions.

**P2 — `electrochemical_interface` (Stage I).**
Built: `PhGradientNernstPlanckProcess`, `ProtonBudgetProcess`,
`EquilibratorThermoStep`, `CarbonFixationProcess`, og-01 gates and phase map.
Add: `MineralConductivityProcess`; `CurrentLimitedFixationModel` and
`MineralSurfaceMicrokineticModel` behind the `carbon_fixation` face;
`models.py` registry + `assert_face`. New gate: `failure-mode-attributed` —
for each point in the (pH x H2 x conductivity) grid the composite reports
whether fixation is limited by delta-G (`energy.reaction_dg > 0`), kinetics
(`microkinetic` rate-limiting step) or current (`current_density` ceiling),
and the three model classes agree on the sign of the answer within the
favourable region. Resolves the open og-01 decision ("explicit
electrochemistry or keep the gradient-efficiency scalar") by deriving the
scalar. Viz: Mechanism = the circuit diagram with live potentials/current;
Decision = the model-substitution comparison figure (section 7.2).

**P3 — Expanded `prebiotic_chemistry` (C-N-P + proto-energetics; Stage II +
cross-cutting).** Built: `RoadRunnerNetworkProcess`, N / P / energy processes
and their studies. Add: single `molecules.dissolved` map; `ResourceBudgetStep`;
the world-side energy pair; `BroadC123Network` SBML + `AutocatalyticSetModel`
(RAF over realized fluxes); `AmphiphileSynthesisProcess` (needed by P5 but it is
chemistry). New gate: `coupled-cnp-with-captured-work` — under one flow
environment, `limiting_resource` is reported, C:N and C:P stay inside the
demand band, and `world.energy.stored_work` is positive (plan section 6 gate).
Second gate: `motifs-emerge-not-imposed` — the dominant persistent subnetwork
in the broad network is identified post hoc and compared with WL / rTCA
motifs. Viz: World = stacked C/N/P pools over time with limiting-resource
band; Mechanism = resource-budget Sankey; Decision = free-energy-ledger figure
(section 7.3).

**P4 — `pore_localization` on shared spatial fields (Stage III).**
Built: `ThermophoreticTrapProcess`, og-03 gate `retention-beats-destruction`.
Add: species-specific Soret coefficients; `AdsorptionProcess`,
`DegradationProcess`; `LocalizationStep` creating `localized[r]` entries
(first `_add` rewrite); `IrregularPoreFipyModel`. New gate:
`persistent-local-history` — at least one `localized` region survives
`tau_min` with regeneration > destruction + exchange (plan's "individuality
begins when local chemical states have persistent histories"), **and** the
coupled localization -> ignition run (the open og-03 decision) shows rTCA
`autocatalytic_gain > 1` inside a region but not in the bulk. Viz: World = 2-D
field with localized regions outlined as they appear; Mechanism =
retention/regeneration/destruction budget per region; Decision =
(porosity x k_wash) map with the `localized`-count surface.

**P5 — `proto_boundary` + endogenous amphiphile production (Stage IV).**
Built: `ProtocellAssemblyProcess`, og-04 gates. Add: `AmphiphileSynthesisProcess`
reading `dissolved.{acetate,...}`; `BoundaryFormationStep`;
`composites/proto_individual.py::protocell_composite`;
`MembraneExchangeProcess`; `ThioesterAminothiolMembrane` model. New gate:
`boundary-forms-from-chemistry` — `agents` goes from 0 to >= 1 **with the
amphiphile produced endogenously** (synthesis arm) and does not with synthesis
ablated; `ledger.rewrite_residual == 0`. Viz: the bigraph-restructuring figure
(section 7.1), first use.

**P6 — Growth / division structural rewrites (Stage IV, og-growth-division).**
Built: `OsmoticGrowthDivisionProcess` (volume, pressure, lysis, division
counter). Add: `DivisionStep`, `LysisStep` as conduits; `ExtinctionStep`;
`StructuralEventLogStep`. New gate: `physical-reproduction` — a lineage of >= 3
generations in the `agents` map with daughter volumes summing to the mother's,
partition residual zero, and the starvation / lysis arms producing `_remove`
events instead. Viz: restructuring figure with the lineage tree; Decision =
existing growth-division band re-read as rewrite counts.

**P7 — Competing heredity modules (Stage VI).**
Built: `LineageReplicatorProcess` (template / compositional / hybrid / none),
`HeredityReplicatorProcess`, og-06 gates (`inheritance-beats-noninheritance`,
Eigen threshold). Add: the six heredity classes behind one face;
`HeredityAttachmentStep`; `vg_heredity` partition in `DivisionStep`. New gate:
`ancestry-predicts-phenotype` — regress daughter `growth_rate` /
`energy_charge` on parent's, per heredity model, under one resource + energy
budget; report the fidelity x information-capacity region where the
regression slope exceeds the non-heritable control (plan: "when does the
benefit of fidelity exceed the cost of replication"). Viz: Decision =
model-substitution figure over (fidelity x length), six models, same gate.

**P8 — `proto_ecology` (Stage VII).**
Built: `CrossFeedingMetacommunityProcess`, og-07 gate `cross-feeding-robustness`.
Add: `SpatialCouplingStep`, `BigraphicalReactiveSystem` with exchange rules,
`EcologyReducerStep`. New gate: `community-function-precedes-cell-completeness`
— a capability (e.g. N assimilation) present in the community's union but in
no single lineage, sustained by cross-feeding; HGT spreads a catalyst between
lineages (an exchange-rule firing count > 0 and a measurable fitness change).
Viz: World = agents on the field coloured by lineage; Mechanism = interaction
graph from `lineage.interaction`; Decision = robustness vs exchange_rate with
the isolated counterfactual.

**P9 — Autonomy / ablation campaign (Stage VIII).**
Built: `OffGradientPersistenceProcess`, `EnvironmentalRelaxationProcess`,
og-08 `survival-off-gradient`. Add: `AblationStep` that scales
`world.environment` / `minerals` / feed fields (gradient, H2, mineral,
confinement, feed, innovation-by-innovation) on a schedule; per-individual
`autonomy` from the currency process. New gate: `minimum-sufficient-innovation-
set` — the smallest set of internal processes (pump, importer, heredity,
internal catalysis) whose presence keeps >= 1 lineage alive under full
ablation; reported as a lattice with the autonomy value at each node. Viz: the
autonomy-continuum readout (section 7.4).

**Adversarial control throughout.** `GenericNonequilibriumEnvironment` becomes
a model-substitution arm on the `environment` interface so every stage's gate
is re-run against it automatically — og-adv's five gates generalise to every
stage without a separate composite.

## 7. Visualization implications (specification only)

To be implemented as `@visualization` entries once the three-view agents land
their PRs. Each is listed with the data it reads so the emit paths can be
planned now.

### 7.1 The Process Bigraph restructuring figure
A time-indexed sequence of the composite tree (render via `bigraph_viz` from the
saved composite document at each `StructuralEventLogStep` row): frame 0 shows
`world` processes only, `agents` empty; frame k shows `localized[r]` appearing;
frame k+1 shows it replaced by `agents[p]` containing its own sub-processes;
later frames show `_divide` (one node -> two with a lineage edge) and
`_remove` (node dissolving, with an arrow of matter back to `world.molecules`).
Reads: the Parquet `events/*` table + per-event document snapshots. This is the
single figure that shows "the emergence of a cell is a change in the Process
Bigraph itself".

### 7.2 Model-substitution comparison
One phase map per interface: identical axes, one coloured contour per model
class (pass boundary), with the intersection region filled and the
union-minus-intersection hatched and labelled "structure-sensitive". A side
bar reports `pass_fraction[m]` and `structure_agreement`. Reads: a
`SweepResult` with a categorical `model_<interface>` axis.

### 7.3 Free-energy / matter ledger
Stacked flows over time: `free_energy_in` -> {`work` (by stage / by individual),
`dissipated`, `stored_work` (world vs inside individuals)}; a second panel of
C/N/P residuals at machine precision with the structural events marked as
vertical lines (they must not move the residual). Reads: `ledger/*`.

### 7.4 Autonomy continuum
Per individual over time: `autonomy` (0 = fully vent-supplied, 1 = fully
internal) as a line, with ablation events as steps in the background and
extinctions as line ends; a summary panel of the innovation lattice from P9
coloured by autonomy. Reads: `agents/*/autonomy`, `events/*`, ablation
schedule.

### 7.5 Resource-limitation band
C:N / C:P supply vs demand bands with the `limiting_resource` strip beneath;
world and (after P5) each individual. Reads: `diagnostics/limiting_resource`,
budget fractions.

### 7.6 Provenance-tiered parameter table
The study's parameter table coloured by `_provenance` tier, with a count of
hypothetical parameters per stage — a one-glance honesty indicator.

## 8. Testing, acceptance and migration rules

- Every new Process/Step gets a test in `tests/` in the existing style
  (`build_core()`, `Composite({"state": gen(core=core, ...)}, core=core)`,
  `gather_emitter_results`). Rewrite steps are tested on toy worlds first
  (section 2.8).
- Conservation after a rewrite is a hard invariant: `ledger.rewrite_residual`
  must be exactly 0.0 for `_add`/`_remove`, and `<= 1e-12` relative for
  `_divide`.
- Canonical-face conformance is a test, not a convention (`assert_face` in
  `tests/test_schemas.py`).
- The 14 existing generators and their canonical runs remain untouched until
  a stage's new composite passes the old gates **and** the new one; only then
  does the study's `baseline[].composite` move to `stage_composite`.
- Negative results stay first-class: a stage whose new gate fails across the
  whole grid is reported as a bottleneck finding, not retuned.
- `scripts/lint-workspace.py` must stay OK on every PR.

## 9. Risks and open questions for the expert

1. **Partition semantics for maps of concentrations.** `_divide`'s type-driven
   walk binomially splits *amounts*; concentrations in a halved volume stay
   equal. `vg_molecules.dissolved` is a concentration map, so `DivisionStep`
   must convert amount <-> concentration around the split (or the internal
   pool should be stored as `vg_amount` with volume alongside — recommended).
2. **Nested composite time-stepping.** Inner protocell composites run at their
   own `interval`; FiPy fields in the world run at theirs. Exchange through
   the bridge is per outer tick; the spike test should check that stiff
   membrane exchange does not need sub-stepping.
3. **Spatial agents on FiPy fields.** `SpatialCouplingStep` maps point agents
   to cells; agent motion (plan Stage VII) is the first place viva-munk-style
   mechanics might be needed — defer until P8.
4. **Scope of `ConstraintBasedModel`.** Optional in the plan; include only if
   the broad network is too stiff for libRoadRunner.
5. **Which heredity attachment thresholds** are defensible (precursor
   availability, fidelity floor) — expert input needed; until then they are
   `_provenance: hypothetical` and swept.
