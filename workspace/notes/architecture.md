# Vivarium process-bigraph architecture

From the Campaign dossier §4 and the Methods Atlas §4. A process-bigraph
implementation fits because the relevant objects are **nested compartments and
interfaces** with processes operating on **incompatible timescales**. The
architecture must let models be exchanged without rewriting the whole campaign.

## Process table (state / ports → implementation → natural timescale)

| Process | State / ports | Possible implementation | Natural timescale |
|---|---|---|---|
| Geochemical rock reactor | rock minerals, water, T, P → H2, alkalinity, ions, heat | serpentinization model | days–years+ |
| Hydrothermal circulation | pressure, permeability, heat → flow field | Darcy/advection model; reduced network initially | s–days |
| Reactive precipitation | ion activities → mineral phases, porosity, conductivity | kinetic mineral precipitation | s–days |
| Electrochemistry | pH/Eh, H2, CO2 → electron/current + products | Nernst + empirical kinetics from reactor data | ms–hours |
| Spatial transport | species fields, T field, flow → advection/diffusion/thermophoresis | finite-volume spatial transport | ms–hours |
| Surface chemistry | adsorbed species + minerals → organics | reaction-network kinetics | s–days |
| Protometabolism | organic network → fluxes/cycles | ODE/stochastic reaction network | s–days |
| Amphiphile dynamics | lipids + surfaces → vesicles/permeability | coarse-grained state model | s–hours |
| Compartment ecology | pores/protocells → growth, fission, extinction | agent-based population process | min–generations |
| Polymer/heredity | monomers/polymers → copying/catalysis/variation | stochastic polymer model | s–generations |
| Evolution | heritable traits → selection and innovation | population genetics / adaptive search | generations+ |

## Core shared stores

- **geometry:** pore network, surfaces, membrane compartments, interface areas
- **fluid fields:** velocity, pressure, temperature, pH, ionic strength, redox potential
- **chemical species:** dissolved inorganic carbon, H2, sulfur species, nitrogen species, phosphorus species, metals, organics
- **solid phases:** olivine/serpentine/brucite/magnetite, Fe/Ni sulfides, carbonates, phosphides
- **electrical state:** potentials, conductivity, current density
- **organic organization:** amphiphiles, polymers, catalysts, reaction-network state
- **lineage state:** compartment ancestry, inherited catalysts/polymers, fitness observables
- **provenance:** parameter/source IDs and uncertainty-ensemble membership

Suggested shared schema (Atlas §4): environment (T, P, flow, potential); aqueous
(species amount by voxel); minerals (phase abundance, surface area, porosity);
interfaces (area, permeability, surface charge); compartments (volume, membrane,
internal species); lineages (catalysts, sequences, ancestry).

## Multiscale coupling principle

Do **not** force every process onto one timestep. Fast chemical/electrochemical
processes can be stepped locally or solved to quasi-steady state inside slower
transport updates; mineral evolution and geological forcing run on much slower
clocks; evolutionary experiments coarse-grain many chemical episodes into one
reproductive event. **Vivarium makes the coupling explicit** rather than burying
it in one monolithic simulator.

Illustrative (proposed, not empirically universal) update schedule: slow
rock/mineral changes (minutes–days); transport and chemistry (ms–hours,
adaptively); membrane and agent changes (seconds–hours); evolution (many
generations).

## Integration contracts and invariants (Atlas §4)

Represent each model as a process with declared input/output stores, units,
spatial support, step size, solver state and provenance.

| Contract | Invariant / test |
|---|---|
| Chemical species | Canonical IDs (formula + charge + phase + protonation); use mol amounts internally, derive concentrations from volumes. |
| Mass / elements | Elemental inventory residuals tracked for C, H, O, N, P, S, Fe, Ni and others. |
| Charge / electrons | Explicit electroneutrality or Poisson closure; track redox and electron bookkeeping. |
| Energy | Thermodynamic directionality; log external work, heat and chemical free-energy flow. |
| Spatial transfer | Fluxes conservative across neighboring cells and compartment boundaries. |
| Time integration | Operator splitting with convergence studies; avoid hidden double-updates to shared state. |
| Reproducibility | Version solver, database, parameter source, random seed and scenario identifier. |

These invariants are the natural place to attach **process contracts** (the
`§ Contract` audit in the Vivarium workbench): declare port types/units/bounds
and predicate conditions (mass/charge/energy conservation) so composites can be
audited for wiring and completeness.

## First integrated composite (Campaign 0 / Atlas §1)

A 1D/2D porous vent wall with externally prescribed fluid boundary conditions,
thermodynamic speciation, reactive solute transport, a minimal Fe/NiS-catalyzed
CO2-reduction network, and explicit mass/charge accounting. Serpentinization
enters first as a boundary flux, later as a coupled mineral-kinetics module.
See `../composites/README.md`.
