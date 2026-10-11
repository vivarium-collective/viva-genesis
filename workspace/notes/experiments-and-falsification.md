# Discriminating experiments, falsification tests, acceptance gates

From the Campaign dossier §§5–7 and the Methods Atlas §6. The campaign is built
to **adjudicate among scenarios**, not illustrate one. Competing outcomes are
first-class.

## Discriminating experiments (Campaign §6)

| Test | Vent-model prediction | Competing outcome | Model observable |
|---|---|---|---|
| In-situ pH correction | Large usable gradient persists across reaction interface | Gradient collapses substantially at hydrothermal T/P | delta pH, proton motive contribution, carbon-fixation rate |
| Sulfur availability | Enough sulfide precipitates catalytic Fe(Ni)S interfaces | Sulfide-poor system dominated by carbonates/oxides | mineral area fractions; conductivity; catalytic yield |
| Pressure/H2 dependence | CO2 reduction remains effective across plausible subseafloor regimes | Products require laboratory-favorable H2 pressures | rate surface over H2 fugacity and pressure |
| Pore lifetime | Reactive compartments persist long enough for enrichment/network growth | Precipitation/dissolution/flow resets pores too fast | residence-time distribution; lineage persistence |
| Dilution | Transport creates concentration hotspots | Washout dominates chemistry | Damköhler/Péclet/Soret-dependent enrichment |
| Reaction-network closure | Sustained feed yields self-reinforcing network motifs | Products remain disconnected one-off syntheses | cycle flux, autocatalytic gain, network persistence |
| Membrane transition | Mixed amphiphiles increase individuality and selection | Salts/T/pH destroy or over-seal membranes | vesicle survival, permeability, resource flux |
| Fixed N/P supply | N/P production/import supports increasing complexity | N or P becomes a hard bottleneck | limiting-resource shadow price / growth sensitivity |
| Autonomy | Evolution internalizes energy conversion | Systems remain obligately tied to exact vent interface | survival as external gradient is reduced |

## Acceptance gates (Methods Atlas §6 — six campaigns)

| Campaign | Couples | Gate |
|---|---|---|
| I. Vent reactor | geochemical source, transport, mineral precipitation, pH/redox gradients, CO2 reduction | Reproduce qualitative trends and published experimental regimes, **including negative controls**; conserve mass and charge. |
| II. Sustained protometabolism | acetate/pyruvate and TCA-like fragments, thermodynamic + kinetic constraints | Identify parameter domains supporting nonzero sustained carbon throughput **without imposed product accumulation**. |
| III. Concentration and protocells | adsorption, thermophoresis, amphiphiles, permeability | Show measurable enrichment and retention, and map **when hydrolysis/leakage defeat synthesis**. |
| IV. Energy autonomy | catalytic ion selectivity, active transport (hypothetical) | Quantify reduced dependence on environmental gradients; compare energetic cost of membrane maintenance. |
| V. Heredity and evolution | copying fidelity, catalytic polymers, lineage selection | Demonstrate inheritance and adaptation under **chemically feasible resource budgets**. |
| VI. Ecological emergence | cross-feeding, fluctuating vents, alternative shallow/terrestrial settings | Test robustness and **distinguish vent-specific predictions from generic nonequilibrium chemistry**. |

## Reproduction / benchmark targets (start here)

Reproduce three benchmark experiments before extrapolating (Campaign Appendix B):

- **Preiner et al. 2020** (ref 15) — H2-dependent CO2 fixation product distributions.
- **Hudson et al. 2020** (ref 11) — pH-gradient-driven CO2 reduction, with controls.
- **Baaske et al. 2007** (ref 18) — thermophoretic accumulation in pore geometries.

These belong in `../experiments/` with provenance-linked expected outputs.

## What would seriously weaken the deep-sea vent program (Campaign §6.1)

- If realistic in-situ T/P/ionic corrections eliminate the electrochemical
  gradients needed for proposed carbon reduction across most plausible geometries.
- If Hadean sulfur inventories make Fe(Ni)S catalytic barriers rare while
  alternative carbonate/oxide mineralogies fail to support comparable chemistry.
- If experimentally constrained reaction rates are too slow relative to pore
  turnover, dilution and degradation to produce meaningful local accumulation.
- If N or P bottlenecks cannot be overcome by flux from the vent or connected
  environments.
- If no plausible pathway couples protometabolic chemistry to heritable
  compartments without importing chemistry that requires a fundamentally
  different environment.

## Competing and hybrid origin environments (Campaign §7)

The right campaign is **not "vent versus everything else."** Vivarium represents
connected environments and material exchange.

| Scenario | Strengths | Weaknesses / tests | Reference anchors |
|---|---|---|---|
| Deep alkaline vent | Continuous H2; gradients; minerals; pores; long-lived forcing | Dilution; P/N; nucleotide chemistry; sulfur/pH critique | refs 1, 2, 4, 28 |
| Shallow alkaline vent | Vent chemistry plus light, tidal/wet-dry and salinity variability | Geological prevalence on Hadean Earth uncertain | ref 27 |
| Terrestrial geothermal field | K-rich/low-Na pools; evaporation and wet-dry cycling | Requires subaerial land and transport; different energy regime | ref 29 |
| Cyanosulfidic / photochemical chemistry | Powerful routes to building blocks under UV-driven chemistry | Requires compatible feedstocks and environmental sequence | ref 30 |
| Network of environments | Can combine incompatible chemistries by transport/cycling | Adds geological/logistical constraints; easy to overfit | simulation should penalize transport complexity |
