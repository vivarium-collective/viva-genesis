# Provenance schema and model-card requirements

From the Campaign dossier §3 and the Methods Atlas §9. The campaign will combine
dozens of heterogeneous papers; **keeping measured, literature-derived, estimated
and hypothetical parameters distinct is essential**, so model comparisons can
tell interpolation from extrapolation.

## Provenance classes

Every quantitative object carries exactly one provenance class:

| Class | Meaning | Preserve |
|---|---|---|
| **FIELD** | Measured in a natural hydrothermal/serpentinizing system. | site, depth, T/P convention, sample handling, analytical method |
| **LAB-DIRECT** | Measured in an experiment designed to reproduce a proposed mechanism. | reactor geometry, feed chemistry, catalyst prep, P, T, duration, detection limit |
| **LAB-ANALOG** | Demonstrates a physical principle relevant to vents but uses biological or otherwise non-prebiotic components (e.g. PCR in a thermal trap). | same as LAB-DIRECT + why it is an analog |
| **MODEL** | Derived from transport/thermodynamic/kinetic/phylogenetic/evolutionary modeling. | equations, assumptions, priors |
| **RECONSTRUCTION** | Inferred ancestral physiology/genome state. | treat as a probabilistic boundary condition |
| **HYPOTHESIS** | Mechanistic proposition not yet independently constrained. | **must never silently become a fixed parameter** |

## Data object design (machine-readable record)

Each quantitative object is accompanied by a record with at least:

- source DOI
- evidence class (one of the six above)
- system / site
- measurement conditions
- variable definition and units
- central value; uncertainty or range
- transformation applied
- original table/figure
- model module consuming the value
- whether the value is calibration, validation or prior information

See the machine-readable registry at
`../datasets/parameter-registry.yaml`.

## Model-card requirements (per module, Atlas §9)

Each module ships with a machine-readable **model card**: source paper/DOI;
extracted figure/table; raw dataset URL; experimental system; units;
temperature/pressure/pH range; fitted formula; parameter uncertainty;
applicability bounds; solver/version; validation tests; alternative
parameterizations. **Avoid transferring a rate constant between pH, pressure or
mineral regimes without an explicit extrapolation flag.**

## Run-export requirements (per simulation run, Atlas §9)

Each run exports: scenario YAML; parameter posterior/sample; code commit;
solver/database versions; composite graph; random seeds; provenance manifest;
and conservation/validation diagnostics. Prefer **SBML** for kinetic networks,
**COMBINE/OMEX** for packaging, **SED-ML** for standardized simulation tasks, and
a **separate spatial schema** for meshes and compartment topology.

## Calibration, uncertainty, inference, validation (Atlas §7)

- Hierarchical priors across mineral types and experimental setups.
- Global sensitivity screening (Morris/Sobol) before fitting.
- Bayesian calibration (PyMC/NumPyro); posterior predictive checks against
  *independent* experimental conditions.
- Prefer profile likelihood / identifiability tests before fitting large kinetic
  networks.
- **Experimental failure cases are mandatory validation targets.**
- Recommended metrics: H2 consumption, DIC fixation, product selectivity, carbon
  mass balance, charge balance, energy dissipation, pore residence-time
  distribution, enrichment ratio, membrane retention, network persistence,
  division rate, lineage survival. Record raw time series plus aggregated
  observables.
