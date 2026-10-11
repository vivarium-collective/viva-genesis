# viva-genesis — campaign overview

**Scope:** deep-sea serpentinization-driven alkaline hydrothermal vents, with
explicit comparison to shallow-vent, terrestrial-geothermal, and cyanosulfidic
alternatives. Literature verified through October 2026.

> **Core modeling idea.** Treat the origin of life as a sequence of coupled,
> independently falsifiable transitions:
> geochemical disequilibrium → carbon fixation → concentration and
> compartmentalization → protometabolic networks → protocells → hereditary
> chemistry → autonomous cells.

> **Primary scientific question.** Can a physically plausible early-Earth
> hydrothermal system generate and sustain localized, increasingly autonomous
> chemical organizations — *without* inserting metabolism, membranes, or heredity
> by assumption?

## Why this fits Vivarium

The strongest version of the alkaline-vent hypothesis is not "life began at a
vent" as a single claim. It is a chain of mechanistic propositions linking
water–rock reactions to biological organization. Each proposition can be a
**process** with explicit state variables, rate laws, spatial interfaces,
uncertainty distributions, and **alternative implementations**. The model must
*not* hard-code the alkaline-vent narrative as the answer: a major 2026 critique
(Tutolo, `papers.bib` ref 28; see also Jackson 2016, ref 35) argues in-situ pH
gradients, sulfide availability, vent longevity and hydrocarbon kinetics may be
substantially less favorable than classical models assume. Those objections are
represented as **parameterizations and competing process models**, so the
simulations adjudicate among scenarios rather than illustrate one story.

## Staged simulation campaign (Campaigns 0–VIII)

| # | Campaign | Transition |
|---|---|---|
| 0 | Reproduce the physical analog | Build a Lost City-like baseline; verify fluid mixing, heat transport, mineral precipitation and H2/alkalinity delivery against published field constraints. **No origin-of-life claim yet.** Output: a validated geochemical/spatial testbed. |
| I | geology → reduced carbon | Add H2-driven CO2 reduction on mineral surfaces and across gradients. Reproduce Hudson/Preiner/Altair regimes before extrapolating. Which T, pH, pressure, H2, CO2 and mineralogy combinations yield sustained net organic-carbon flux? |
| II | reduced carbon → protometabolism | Insert broad reaction graphs (Huber/Wächtershäuser, Muchowska/Moran). Search for persistent cycles, flux amplification, product reuse and autocatalytic motifs under continuous feed and washout. |
| III | dilution → localized chemical individuals | Add pore geometry, adsorption, convection, thermophoresis. When do retention time and concentration cross thresholds for network persistence? Let pore morphology evolve via precipitation/dissolution. |
| IV | mineral compartments → protocells | Introduce mixed amphiphiles and membrane assembly. Evolve permeability, adsorption, vesicle growth and fission. Do organic boundaries enhance persistence without cutting systems off from geochemical energy? |
| V | environmental → internal bioenergetics | Allow catalytic ion transport and later active pumping. Can selection move from externally imposed gradients toward internally maintained electrochemical states? |
| VI | chemistry → heredity | Compare RNA-like, peptide-assisted, compositional and hybrid heredity modules. Require inherited state to improve persistence/throughput, not merely template replication in isolation. |
| VII | ecology before LUCA | Heterogeneous populations in connected pore networks with cross-feeding, parasitism, cooperation, horizontal exchange. Compare emergent capabilities to ancestral reconstructions without assuming LUCA is primitive. |
| VIII | escape from the vent | Relax environmental support. Vary gradient strength, mineral access, feed chemistry. Identify the minimum innovations required for autonomous persistence away from the geological reactor. |

## First publication-sized milestone (recommended first target)

> Can a **dynamically precipitating, spatially resolved alkaline vent–ocean
> interface** generate and **retain a persistent protometabolic carbon flux**
> under parameter ranges consistent with field observations and laboratory
> experiments?

Intentionally **pre-genetic**: hard enough to be meaningful, admits direct
laboratory validation, and avoids hiding the weakest part of the origin story
(heredity) behind assumed replicators.

## Recommended implementation order (Campaign Appendix B)

1. Curate a provenance-first parameter registry and reproduce three benchmark
   experiments: **Preiner 2020, Hudson 2020, Baaske 2007**.
2. Build a reduced spatial vent interface: two fluids, T, pH/speciation,
   H2/CO2, dynamic precipitate, and a small carbon-reduction network.
3. Validate against Lost City ranges while separately parameterizing Hadean
   ocean chemistry; never calibrate ancient chemistry by silently reusing
   modern seawater.
4. Add Muchowska/Moran protometabolic edges; measure network persistence under
   continuous flow and washout.
5. Add pore remodeling and concentration mechanisms; run ensembles over
   geometry and geochemical uncertainty.
6. Only after the geochemistry→protometabolism model is predictive, add
   amphiphile compartments and selection.
7. Keep heredity modular; compare multiple origins-of-information hypotheses
   rather than picking RNA by default.
8. Run the full campaign as competing environmental scenarios: deep vent,
   shallow vent, terrestrial geothermal, and connected-niche models.

> **Bottom line.** The most defensible Vivarium program begins with a validated
> geochemical flow reactor and asks *when* chemical organization appears. The
> scientific payoff is identifying the parameter regimes and transition sequence
> in which geology can become an evolving chemical ecology — and determining
> where the vent hypothesis fails.

## Related documents

- `hypothesis-graph.md` — state-space stages, link evidence table, provenance crosswalk.
- `modules.md` — mechanistic modules A–J and the LUCA boundary condition.
- `architecture.md` — Vivarium process-bigraph architecture, shared stores, coupling.
- `provenance-schema.md` — provenance classes and model-card requirements.
- `experiments-and-falsification.md` — discriminating tests and acceptance gates.
- `risk-register.md` — evidence gaps and model risks.
- `data-acquisition.md` — field + laboratory datasets to acquire/digitize.
- `../references/computational-resources.md` — engines, databases, standards.
- `../references/papers.bib` — the 35-reference annotated library.
