# viva-genesis — Scientific Enrichment Plan (expert-provided 2026-10-13)

Digest of the expert's *Scientific Enrichment Plan: Concrete Mechanisms, Unknowns,
and Testable Questions for an Exploratory Simulation Campaign on the Origin of
Cells* (source: `Viva_Genesis_Scientific_Enrichment_Plan.pdf`). Captured here so the
reframing and the roadmap are tracked in the repo. The references it cites are added
to `references/papers.bib`; the per-stage integration map is recorded on the
investigation (`guidelines.enrichment_roadmap`) and on each study's future-work.

## Core thesis (reframing)

**viva-genesis should become a quantitative MAP OF THE BOTTLENECKS between geology
and cells — not a computational retelling of the alkaline-vent hypothesis.** The
scientific value is strongest when it exposes *dependencies, failure regimes, and
discriminating experiments*, and weakest when it produces a single successful origin
narrative. A passing gate means the implemented model satisfies a prespecified
criterion under its assumptions; it does NOT establish that the historical transition
occurred.

## Stage-by-stage enrichment (add to the model → key unknown to test)

- **0 Rock→vent** — mineral-resolved serpentinization (Fe²⁺/Fe³⁺ balance), H₂
  production + precipitation + pore evolution. *Do H₂, alkalinity and precipitation
  co-vary, or trade off?*
- **I Vent→reduced carbon** — explicit electrode potentials, conductivity, current
  density (treat the vent as an electrical circuit). *Is the conductive Fe/Ni/S
  architecture the real limiting variable?*
- **I–II Carbon→network** — broader C1/C2/C3 chemistry (CO, methanol, glyoxylate,
  succinate, amino-acid precursors); let dominant subnetworks EMERGE, don't impose a
  modern pathway. *Do WL/rTCA motifs emerge from vent chemistry itself?*
- **III Localization** — dynamic pore morphology, adsorption, species-specific
  thermophoresis. *Does the pore concentrate chemically different solutes
  differently (co-concentration vs separation)?*
- **IV Protocells** — endogenous amphiphile production + critical aggregation
  concentration. *Can vent chemistry produce membrane precursors faster than they are
  lost, and concentrate them enough to assemble?*
- **V Bioenergetics** — H⁺/Na⁺ permeability, membrane potential, primitive ion
  transport. *Can primitive chemistry replace environmental energy with internal
  energy at real cost?*
- **VI Heredity** — competing inheritance modes under one resource/error budget.
  *When does high-fidelity template heredity outperform cheaper compositional/network
  inheritance?*
- **VII Ecology** — spatial cross-feeding, resource competition, parasitism. *Can
  cooperation/division of labor achieve functions no single protocell can sustain?*
- **VIII Autonomy** — ablate mineral catalysis / H₂ / confinement / external feed.
  *Which geological functions must be biologically internalized before a lineage can
  leave?*

## New modules / adjacent studies the plan adds

1. **Electrochemical vent interface** (§2) — fluid composition → redox potential →
   mineral conductivity → current density → electron-transfer rate → carbon
   reduction. *Enriches og-01* (replace the abstract gradient-efficiency scalar).
2. **Dynamic, co-evolving mineral wall** (§3) — precipitation/dissolution alter pore
   size, permeability, catalyst; feedback onto transport + chemistry. *Enriches
   og-00/og-03.*
3. **Carbon chemical landscape** (§4) — emergent networks from thermo+kinetic
   constraints. *Enriches og-02.*
4. **Nitrogen as a limiting resource** (§5) — N₂/NO₃⁻/NO₂⁻ → NH₃/NH₄⁺, reductive
   amination; track C:N. **NEW study.**
5. **Phosphorus bottleneck** (§6) — dissolved phosphate, mineral-bound P,
   polyphosphates, reactive P; co-concentration with C,N. **NEW study.**
6. **Proto-energetics before modern pumping** (§7) — couple exergonic→endergonic
   chemistry via thioesters, acyl phosphates, polyphosphates, reduced-metal centers;
   explicit energetic bookkeeping into a transferable currency. **NEW study** (before
   og-05).
7. **Endogenous membrane production** (§8) — routes to fatty acids/alkanols/
   thioesters/diacyl-lipids; production vs loss + assembly thresholds. *Enriches
   og-04.*
8. **Metabolism → growth & division** (§9) — product accumulation → osmotic pressure
   → compartment expansion → division; a physical selection mechanism without an
   abstract fitness score. **NEW study** (after og-04).
9. **Heredity vs simpler memory** (§10) — mineral-state / compositional / network /
   peptide / RNA / hybrid under one budget. *Partly done in og-06; extend.*
10. **LUCA far downstream, as a constraint only** (§11). *Shapes og-07.*

## Recommended near-term simulation arc (§13)

serpentinization → dynamic mineral/electrical interface → carbon fixation → nitrogen
fixation/assimilation → phosphorus availability → coupled C-N-P protometabolism →
species-specific thermophoretic concentration → endogenous amphiphile synthesis →
compartment formation → autocatalysis-driven growth/division. Reframed objective:
**Can a physically plausible hydrothermal pore transform inorganic geological
feedstocks into a growing, dividing chemical individual without presupposing cellular
machinery?**

## Experimental design principles (§14)

1. Phase maps, not representative trajectories — every major claim identifies PASS
   AND FAILURE regions.
2. Carry measured vs calibrated vs extrapolated parameter provenance explicitly.
3. Maintain matter, charge and free-energy accounting across composed processes.
4. Use feature ablations to find NECESSARY (not merely correlated) mechanisms.
5. Build negative controls that fail the same gates (vent-specificity).
6. Let multiple origin scenarios share modules (deep/shallow vents, terrestrial
   geothermal, photochemical) comparable via the same gates.
7. Treat negative results as scientific output: a broken transition identifies an
   experimentally targetable bottleneck.

## High-value questions viva-genesis can adjudicate (§12)

Molecular-or-spatial first transition? Was early metabolism inherited from geology?
Which vent feature matters most (ablation — see og-adv)? Is thermodynamic favorability
enough (separate ΔG from kinetics + electron-transfer)? What was the first limiting
resource (C vs N vs P vs metals vs amphiphiles vs energy)? Can ONE environment do
everything (overlap of favorable windows)? When does a compartment become an organism?
Is autonomy gradual (fraction of essential functions no longer supplied by geology)?
Could ecology precede complete cells?
