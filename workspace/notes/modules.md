# Mechanistic modules A–J (+ LUCA boundary)

From the Campaign dossier §2. Each module is a candidate Vivarium process (or
family of processes). The `viva_genesis/` package groups these into subpackages
(`geochemistry/`, `transport/`, `electrochemistry/`, `protometabolism/`,
`compartments/`, `polymers/`, `ecology/`) — see each subpackage's README for the
intended process contract. Reference numbers index `../references/papers.bib`.

## Module A — serpentinization and geochemical energy supply
**Mechanism.** Water circulating through Fe(II)-bearing ultramafic rock hydrates
olivine to serpentine/brucite, oxidizing iron toward Fe(III) phases (magnetite);
the electron transfer reduces water to H2, which drives subsequent carbon
reduction. The 2023 Schwander synthesis (ref 9) is the best current gateway.
**Provenance.** Lost City field observations (refs 5, 7, 8) constrain fluid T,
pH, mineralogy, carbon species and system longevity (>=30,000 y).
**Vivarium process.** `serpentinization(rock_state, water_flux, T, P) -> H2_flux,
alkalinity_flux, heat_flux, mineral_transformations, dissolved_metals`. Treat the
output as a **distribution**, not a fixed H2 concentration.
→ `viva_genesis/geochemistry/`

## Module B — hydrothermal flow, mixing, precipitation and pores
**Mechanism.** The vent–ocean interface is a coupled reactive-transport problem:
alkaline fluid mixes with carbon-bearing ocean water; carbonate/silicate/sulfide/
oxide phases precipitate; permeability evolves; pore geometry feeds back on flow.
Herschy et al. (ref 10) built a bench-top reactor for this regime.
**Key modeling choice.** Whether thin Fe(Ni)S-rich barriers are abundant and
persistent under Hadean conditions. Classical models assume yes; Tutolo 2026
(ref 28) argues early-ocean sulfur scarcity and serpentinizing-system geology
may make that far less plausible. **Implement both versions.**
→ `viva_genesis/transport/`

## Module C — natural electrochemistry and pH-gradient-driven carbon reduction
**Mechanism.** Hudson et al. (ref 11) reduced CO2 with H2 at room T and 1.5 bar
when acidic and alkaline streams were separated across freshly precipitated
Fe(Ni)S; isotope + deuterium experiments favored a spatially separated
half-reaction (electrochemical-cell) interpretation. Altair et al. 2025 (ref 12)
extended this to a macroscale reactor (currents ~nA to uA).
**Key discriminating variable.** Do gradients persist at in-situ T and P, or are
large pH differences primarily a cooling/measurement artifact? Encode
`pH(T, P, ionic_strength)`, not laboratory pH as a constant environmental state.
→ `viva_genesis/electrochemistry/`

## Module D — mineral-catalyzed carbon fixation
**Mechanism.** Huber & Wächtershäuser (ref 13) formed activated acetate/thioester
chemistry on coprecipitated FeS/NiS; Varma et al. (ref 14) showed native Fe
reduces CO2 toward acetyl-CoA-pathway products; Preiner et al. (ref 15) showed
greigite/magnetite/awaruite catalyze H2-dependent CO2 fixation at 100 C,
producing formate (up to ~200 mM), acetate (up to ~100 uM), pyruvate (up to
~10 uM) and methanol/methane. **These are laboratory outcomes, not environmental
concentrations** — treat as yield/rate calibration targets under specific mineral,
T and P regimes.
→ `viva_genesis/protometabolism/`

## Module E — protometabolic network formation
**Mechanism.** Begin with an experimentally motivated reaction graph and ask
whether metabolism-like subnetworks emerge under sustained flow. Muchowska et al.
(refs 16, 17) showed metals promote rTCA sequences and Fe2+ generates nine of
eleven TCA intermediates plus all five universal metabolic precursors from
pyruvate and glyoxylate. Elementary/lumped reactions carry rate laws; mineral
dependencies and environmental windows constrain them; persistent flux cycles,
autocatalytic motifs, cross-catalysis and product retention become **emergent
observables rather than assumptions**.
→ `viva_genesis/protometabolism/`

## Module F — transport, concentration and retention
**Mechanism.** Any oceanic origin must defeat dilution. Baaske et al. (ref 18)
modeled thermally driven convection + thermophoresis in elongated pores,
predicting >10^8-fold nucleotide accumulation in favorable geometries; Mast &
Braun (ref 19) demonstrated a thermal trap supporting DNA replication cycling and
thermophoretic accumulation. Concentration should arise from the balance of
advection, molecular diffusion, thermodiffusion, adsorption/desorption,
precipitation, degradation and pore geometry.
→ `viva_genesis/transport/`

## Module G — mineral compartments to organic protocells
**Mechanism.** Mineral pores provide initial spatial individuality without
requiring lipid membranes first. Jordan et al. (ref 20) found single-chain
amphiphile mixtures form vesicles across a broader range of alkaline pH,
salinity, divalent cations and elevated temperature than simple single-fatty-acid
models imply. Model amphiphile production/import, partitioning, adsorption to
minerals, vesicle nucleation, permeability, growth, division and leakage. Central
tension: membranes must retain enough to support selection while remaining
permeable enough to exploit external gradients.
→ `viva_genesis/compartments/`

## Module H — bioenergetic internalization
**Mechanism.** Lane & Martin (ref 3) proposed natural proton gradients across
inorganic barriers could precede membrane bioenergetics, with initially leaky
protocell membranes later forcing the evolution of active ion pumping. Sojo et al.
(ref 21) modeled LUCA-like cells using proton gradients only if membranes remain
sufficiently leaky. In Vivarium this is an **evolutionary control problem**: vary
membrane permeability, Na+/H+ coupling, gradient magnitude and catalyst
efficiency; reward carbon/energy throughput and compartment persistence; test
whether selection favors increasingly internalized gradient generation.
→ `viva_genesis/compartments/`

## Module I — nitrogen, phosphorus and other limiting resources
**Mechanism.** Origins may be controlled by less-abundant resources. Dörr et al.
(ref 22) reported NH3 from N2 on freshly precipitated FeS + H2S at ~70-80 C
(~0.1% yield relative to FeS — flux-limiting). Phosphorus: schreibersite
((Fe,Ni)3P) is a reduced, reactive P source; basic conditions favor
organophosphates (Pasek, ref 23) — an example of environmental incompatibility
that may require transport between niches.
→ `viva_genesis/geochemistry/` (resource modules)

## Module J — polymers, information and heredity
**Mechanism.** The least complete link in a strict deep-sea alkaline scenario.
Pores can concentrate nucleotides/polymers; Fe/Ni/S chemistry can promote peptide
formation (Huber & Wächtershäuser, ref 24: amino-acid activation with CO on
(Ni,Fe)S at 100 C, pH 7-10) — but no single validated vent pathway spans
feedstock synthesis, nucleotide activation, template copying, functional polymers,
compartment coupling and open-ended heredity. **Treat informational chemistry as
a branch point, not a scripted milestone:** candidate modules include RNA-world,
peptide-first catalysis, compositional heredity, mineral-surface templating, and
exchange with shallow/terrestrial environments.
→ `viva_genesis/polymers/`

## LUCA as a far-end boundary condition
LUCA is not the first life, but phylogenomic reconstructions give a distant
target state. Weiss et al. (ref 25) reconstructed 355 protein families consistent
with an anaerobic, H2-dependent, CO2-fixing, FeS-rich physiology associated with
hydrothermal settings; Moody et al. 2024 (ref 26) inferred a larger, earlier LUCA
(~4.2 Ga) embedded in an ecosystem. Use LUCA reconstructions as **constraints on
which capabilities must eventually be acquired**, not evidence that the first
replicators had LUCA-like complexity.
→ `viva_genesis/ecology/`
