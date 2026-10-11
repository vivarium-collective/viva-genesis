# Computational resources — engines, databases, standards

Curated from the **Origins-of-Life Computational Methods Atlas** (11 Oct 2026),
§§1, 3, 10. This is a **design and resource-selection** catalog, not a claim
that any of these tools already simulates abiogenesis end-to-end. The campaign
keeps geology, aqueous chemistry, transport, mineral surfaces, protometabolism,
compartment dynamics, polymers and population evolution as **replaceable models
coupled by explicit conserved quantities** (see `../notes/architecture.md`).

## Executive architecture — scale → recommended initial engine → coupling output

| Scale / state | Recommended initial engine | Coupling output |
|---|---|---|
| Rock–fluid thermodynamics | PHREEQC or Reaktoro | aqueous species, pH, saturation indices, mineral extents |
| Flow, temperature, solute transport | FiPy / custom spatial-transport; OpenFOAM if needed | velocity, T, concentration fields |
| Aqueous / surface reactions | Cantera, SciPy ODEs, custom kinetic laws | species fluxes, heat, charge |
| Thermodynamic screening | eQuilibrator + curated reaction thermochemistry | reaction Gibbs energies, feasibility bounds |
| Chemical networks | Tellurium/RoadRunner, COPASI, GillesPy2 | reaction-network state and event histories |
| Membranes / pores / polymers | custom mesoscopic models; OpenMM/LAMMPS for calibration | permeability, assembly and adsorption laws |
| Protocell agents / selection | Vivarium process-bigraph + agent-based processes | birth, division, exchange, lineage and fitness |

**Recommended first integrated composite:** a 1D/2D porous vent wall with
externally prescribed fluid boundary conditions, thermodynamic speciation,
reactive solute transport, a minimal Fe/NiS-catalyzed CO2-reduction network, and
explicit mass/charge accounting. Serpentinization enters first as a boundary
flux, later as a coupled mineral-kinetics module.

## Software selection — best role and caution

| Resource | Best role | Caution / implementation note | Primary link |
|---|---|---|---|
| **PHREEQC** | Aqueous speciation, saturation, mineral reactions | Thermodynamic database choice + activity model matter strongly at high ionic strength; cite the exact database used. | https://www.usgs.gov/software/phreeqc-version-3 |
| **Reaktoro** | Python-accessible equilibrium and reactive chemistry | Check supported thermodynamic datasets and kinetic formulations before committing. | https://reaktoro.org/ |
| **FiPy** | Rapid 1D/2D finite-volume transport | Coupling electrostatics, flow and evolving pore geometry requires development. | https://pages.nist.gov/fipy/ |
| **OpenFOAM / FEniCSx** | Resolved flow / multiphysics FEM | Higher implementation and compute cost; defer until reduced models fail. | https://www.openfoam.com/ · https://fenicsproject.org/ |
| **Cantera** | Well-specified chemical kinetics and reactor networks | No prebuilt validated prebiotic vent reaction mechanism is supplied. | https://cantera.org/ |
| **Tellurium / RoadRunner** | SBML kinetic protometabolic networks | Kinetic constants for abiotic networks must be curated or inferred. | https://tellurium.analogmachine.org/ |
| **COPASI** | COmplex PAthway SImulator (kinetics, analysis) | Same curation caveat as Tellurium. | https://copasi.org/ |
| **eQuilibrator** | Reaction thermodynamics, screening | Biochemical standard-state assumptions may not suit hydrothermal brines. | https://equilibrator.weizmann.ac.il/ |
| **Smoldyn / ReaDDy** | Particle-based reaction-diffusion (mesoscopic) | Mesoscopic spatial models are not mineral-surface quantum chemistry. | https://www.smoldyn.org/ · https://readdy.github.io/ |
| **OpenMM / LAMMPS** | Focused atomistic / coarse-grained studies | Force-field validity and accessible timescales are major constraints; use only to calibrate transport/binding laws. | https://openmm.org/ · https://www.lammps.org/ |
| **GillesPy2 (StochSS)** | Stochastic simulation (SSA) for low copy numbers | Project documentation; pair with rule-based chemistry for combinatorics. | https://github.com/StochSS/GillesPy2 |
| **BioNetGen / NFsim** | Rule-based chemistry for combinatorial networks | Useful for sequence-level / polymer combinatorics (Module J). | https://bionetgen.org/ |
| **COBRApy** | Metabolic network analysis, late-stage benchmarks | Steady-state FBA should NOT replace prebiotic reaction kinetics. | https://opencobra.github.io/cobrapy |
| **PyMC / NumPyro** | Bayesian calibration, uncertainty, inference | Prefer profile likelihood / identifiability tests before fitting large kinetic networks. | https://www.pymc.io/ |
| **OpenPNM / PoreSpy** | Pore-network modeling / porous-media image analysis | For pore-scale geometry feeding continuum transport. | https://openpnm.org/ · https://porespy.org/ |

## Chemical and biological databases

| Resource | Role | Link |
|---|---|---|
| **InterRidge / PANGAEA** (Beaulieu & Szafranski 2020, v3.4) | Global database of active submarine hydrothermal vent fields — environmental **prior** on vent setting, depth, T, tectonic context. | https://doi.pangaea.de/10.1594/PANGAEA.917894 |
| **EarthChem** | Geochemical data infrastructure and portals. | https://www.earthchem.org/ |
| **Lost City field chemistry** (published) | Modern analog constraints on T, pH, mineralogy, carbon species, longevity. | see `papers.bib` refs 5–8, 34 |
| **PHREEQC thermodynamic databases** | Select and cite the exact database used; avoid treating all databases as interchangeable. | https://www.usgs.gov/software/phreeqc-version-3 |

## Interoperability / packaging standards

| Standard | Use |
|---|---|
| **SBML** (Keating et al. 2020, Level 3) | Preferred format for kinetic reaction networks. https://sbml.org/ |
| **SED-ML** (Waltemath et al. 2011) | Standardized, reproducible simulation tasks. https://sed-ml.org/ |
| **COMBINE / OMEX** (Bergmann et al. 2014) | Model packaging archive. https://combinearchive.org/ |
| *(separate spatial schema)* | Use a distinct schema for meshes and compartment topology — do not fold spatial geometry into SBML. |

## Model hierarchy and computational cost (tiers)

- **Tier A — reduced screening:** 0D/1D compartments, fixed geometry, prescribed vent source, 10–50 species, simple kinetics. Thousands of parameter sweeps.
- **Tier B — mechanistic spatial:** 2D finite-volume fields, dynamic mineral surfaces, adsorption, electrochemical transport, explicit pore populations. Hundreds of runs.
- **Tier C — focused calibration:** pore-scale CFD, molecular dynamics or reactive mineral modeling to derive **closure laws** for Tiers A/B.
- **Tier D — evolution:** thousands of compartment agents coupled to coarse spatial fields; use emulators for expensive chemistry where validated.

## Stage → engine map (Atlas §2, condensed)

| Stage | Scientific model | Engines / methods |
|---|---|---|
| 0 Environmental priors | Hadean scenario ensembles | PANGAEA/InterRidge, EarthChem, Lost City chemistry, PHREEQC thermo DBs |
| 1 Serpentinization | water–rock reaction, Fe redox, H2, alkalinity, heat | PHREEQC, Reaktoro; CrunchFlow/TOUGHREACT for larger reactive transport |
| 2 Chimney growth / pore flow | mixing, FeS/carbonate precipitation, evolving porosity | FiPy; OpenFOAM (resolved CFD); FEniCSx; PoreSpy/OpenPNM |
| 3 Electrochemical gradients | H+ gradients, interface potentials, electron-transfer-limited CO2 reduction | Nernst–Planck–Poisson (electroneutral approx) on FiPy/FEniCSx; PHREEQC; Cantera/custom heterogeneous kinetics |
| 4 Carbon fixation / protometabolism | curated reaction graph (formate, acetate, pyruvate, glyoxylate) | SBML + libRoadRunner/Tellurium or COPASI; SciPy solve_ivp; Cantera; eQuilibrator |
| 5 Concentration / polymers | thermophoresis, diffusion, convection, adsorption, oligomerization/hydrolysis | FiPy; custom finite-volume; GillesPy2/SSA; OpenMM/LAMMPS for calibration only |
| 6 Amphiphiles / protocells | amphiphile supply, aggregation, membrane stability, permeability, division | custom coarse-grained membrane kinetics; Smoldyn/ReaDDy; OpenMM/LAMMPS for targeted studies |
| 7 Catalytic polymers / heredity | sequence/class-based catalysis, template copying, error rates | GillesPy2/StochPy; rule-based chemistry (BioNetGen/NFsim); custom sequence-level agents |
| 8 Ecosystems / pre-LUCA | heterogeneous compartments, cross-feeding, migration, selection | Vivarium multi-agent composites; COBRApy for genome-scale benchmarks; evolutionary algorithms / Bayesian calibration |

## Implementation roadmap (first 12 months, Atlas §8)

| Window | Deliverables |
|---|---|
| Months 1–2 | Data registry; species + units schema; 0D vent/ocean mixer; PHREEQC/Reaktoro proof-of-concept; benchmark notebooks. |
| Months 3–4 | 1D FiPy transport + geochemical speciation + simple mineral precipitation; regression tests and parameter sweeps. |
| Months 5–6 | CO2-to-formate/acetate kinetic process; experimental comparison; provenance-rich model cards; first integrated demonstration. |
| Months 7–9 | Dynamic pore/adsorption/concentration models; compare alternative physical closures and gradient mechanisms. |
| Months 10–12 | Compartment agents, amphiphile exchange, scenario comparisons; reproducible Workbench demonstration and manuscript-ready figures. |
