# Multisolute pore physics: per-species transport, Soret, adsorption & degradation

Parameter reference for the **Phase 4 / Priority-Upgrade-D** multisolute
localization model (full modeling plan §4.5, Stage III). The decisive test is
not whether *one* tracer concentrates in a thermophoretic pore, but whether the
chemically-necessary **mixture** co-localizes or fractionates. That requires,
per solute, four physical parameters — molecular diffusivity `D`, Soret
(thermophoretic) coefficient `S_T`, mineral-surface adsorption, and degradation
— fed to the FEM reference (`viva-fenics`'s `multisolute_pore`) and the reduced
pore-network surrogate.

This file sources those parameters and, critically, **states their provenance
honestly**: which are measured, which are estimated by analogy, and which are
only bracketed. The single most important honesty point is that **Soret
coefficients for most prebiotic solutes have not been individually measured**;
they are estimated from the solvation-entropy theory and bracketed by ranges.
That uncertainty is not a defect to paper over — it is a **first-class input to
the model-structure-uncertainty analysis** (`uq.structure_agreement` /
`decision_envelope`): the co-localization verdict's robustness to the `S_T`
ranges is itself a reportable result.

Reference condition for the tabulated values: dilute aqueous solution, alkaline
hydrothermal pore (**pH ≈ 9–10, T ≈ 90 °C**), unless noted. Diffusivities are
quoted at 25 °C (the temperature at which standard tables report them) and scale
roughly with `T/η(T)` (≈ 2–3× higher at 90 °C — apply the Stokes–Einstein
correction in the model, do not hard-code the 25 °C value as the vent value).

## Provenance classes

| class | meaning |
|---|---|
| **M** | measured value for this exact species (standard tables / cited study) |
| **A** | estimated by analogy to a measured homolog (named) |
| **E** | estimated from theory (Stokes–Einstein for `D`; solvation-entropy for `S_T`) |
| **B** | only bracketed by an order-of-magnitude range; the structure-uncertainty sweep spans it |

## The eight solutes

`D` in 10⁻⁹ m²·s⁻¹ (25 °C, infinite dilution). `S_T` in 10⁻³ K⁻¹, positive =
thermophobic (accumulates on the **cold** side — the Baaske trap sign).
Adsorption and degradation are given as the regime + a representative rate class
at the reference condition; exact `k_ads`/`k_des`/`k_deg` are set per run from
these brackets.

| species (dissolved key) | `D` (prov) | `S_T` (prov) | adsorption @ pH≈9 (prov) | degradation @ ~90 °C (prov) |
|---|---|---|---|---|
| `phosphate` (H₂PO₄⁻/HPO₄²⁻) | 0.76–0.88 (M) | 3–10 (B) | **strong** inner-sphere on Fe-(oxyhydr)oxide (~45 % uptake at pH 9) (M) | stable — inorganic (M) |
| `ammonium` (NH₄⁺) | 1.96 (M) | 1–4 (B); cation → weaker cold-side than anions (E) | weak–moderate cation exchange on silicates (A) | stable — inorganic (M) |
| `formate` (HCOO⁻) | 1.45 (M) | 2–7 (B) | weak, outer-sphere carboxylate (A) | relatively stable; slow decarboxylation (M, Bockisch/Palmer acetic-acid-derivative series) |
| `acetate` (CH₃COO⁻) | 1.09 (M) | 2–7 (B) | weak, outer-sphere carboxylate (A) | **very stable**; high-Eₐ decarboxylation (M) |
| `pyruvate` (CH₃COCOO⁻) | ~1.0 (A, vs lactate) | 2–8 (B) | weak–moderate (A) | **labile** — decarboxylates to acetate + CO₂ (M, first-order) |
| `amino_precursor` (glycine proxy) | 1.06 (M) | 3–8 (B) | moderate on clays / Fe-S (A) | moderate — decarboxylation, Eₐ 88–137 kJ·mol⁻¹ (M) |
| `amphiphile` (C₈–C₁₀ fatty-acid monomer) | ~0.6 monomer; ≪ as micelle (E) | 5–20 (B); aggregation raises effective `S_T` (E) | **strong** partition to surfaces / self-aggregates (A) | stable — slow carboxylic-acid hydrolysis (E) |
| `nucleotide_precursor` (ribose / AMP) | ribose ~0.7 (M); AMP ~0.4–0.5 (M) | 5–15 (B); larger, charged → higher (A, vs DNA/nucleotide thermophoresis) | moderate–strong via phosphate moiety → Fe-(oxyhydr)oxide (A) | **labile** — glycosidic / phosphoester hydrolysis (A) |

### Notes per parameter family

**Diffusivity `D`.** Small-ion aqueous diffusivities span ≈ 0.6–2 ×10⁻⁹ m²·s⁻¹;
biomolecules 0.1–1 ×10⁻⁹. Values above are standard infinite-dilution tabulations
(Vanýsek / CRC for the ions; the measured glycine value is 1.055–1.064 ×10⁻⁹);
AMP/ribose from biomolecule diffusivity tables. These are the best-constrained
inputs. **Do apply a Stokes–Einstein `T/η` correction to the pore temperature** —
at 90 °C `D` is ≈ 2–3× the 25 °C value.

**Soret coefficient `S_T`.** The dominant uncertainty. Measured aqueous `S_T`
for small organics/ions is of order 10⁻³–10⁻² K⁻¹, positive (thermophobic) at
room-to-warm temperature, with **anions accumulating cold-side more strongly
than cations**, and a sign change toward thermophilic at low T. There is **no
direct `S_T` measurement for most of these exact prebiotic solutes** — the
brackets above follow the measured small-solute range and the Duhr–Braun
solvation-entropy scaling (larger, more-charged species → larger `S_T`; nucleotides
and aggregating amphiphiles at the high end). **These brackets define the
structure-uncertainty sweep**: the model reports the co-localization verdict
across the `S_T` range, and `1 − structure_agreement` is the share of the range
where the answer flips.

**Adsorption.** Phosphate's strong inner-sphere complexation on ferrous/ferric
(oxyhydr)oxide (measured ~45 % uptake at pH 9, maximal for ferrous oxyhydroxide)
is the firmest adsorption datum and the most consequential: a strongly-adsorbing
phosphate is pulled out of the mobile pool differently from the carboxylates,
a candidate fractionation channel. Carboxylates adsorb weakly (outer-sphere);
amino acids and nucleotides moderately (clays, Fe-S, and — for nucleotides — the
phosphate moiety); amphiphiles partition strongly to surfaces and aggregates.

**Degradation.** First-order at vent temperature. The hierarchy matters more
than the absolute rates: **pyruvate and nucleotide precursors are labile**
(pyruvate decarboxylates to acetate; nucleosides/nucleotides hydrolyze),
**amino-acid precursors intermediate** (decarboxylation, Eₐ 88–137 kJ·mol⁻¹),
**acetate and the inorganics essentially stable** on the residence timescale.
A species that concentrates but degrades in place does not co-localize in the
steady state — degradation and enrichment compete, which the FEM solve resolves
directly.

## How these feed the model

1. **FEM reference** (`viva-fenics` `multisolute_pore` / `fem_multisolute`):
   each species carries its own `D`, `S_T`, `k_ads`/`k_des`, `k_deg` from the
   per-run parameterization; the solve returns per-species enrichment + the
   pairwise co-localization correlation on the real 3-D pore.
2. **Reduced surrogate** (`multisolute_surrogate`, uv `.venv`): a cheap
   pore-network model fit to the FEM reference over (`Pe`, `S_T`, `D`,
   geometry), used to fill Decision-map cells with the FEM run reserved for
   World-view points + a random audit subset.
3. **Structure-uncertainty** (`uq`): the `S_T` brackets (and the adsorption /
   degradation ranges) are swept; the co-localization verdict is reported with
   `structure_agreement` / `decision_envelope`, so the claim is honest about the
   parameter region where the mixture co-localizes vs. fractionates.

## Sources

- Soret / thermophoresis magnitudes, ion-specific cold-side accumulation:
  *Solution-composition-dependent Soret coefficient (MicroScale Thermophoresis)*,
  RSC Adv. 2023 — https://pubs.rsc.org/ra/article/13/23/15901/823109 ;
  *Thermodiffusion of aqueous potassium salts*, J. Chem. Phys. 154, 084506 (2021) —
  https://pubs.aip.org/aip/jcp/article/154/8/084506 ;
  *Thermodiffusion in aqueous alkali-halide solutions* — https://arxiv.org/html/2604.18084
- Solvation-entropy theory + DNA/nucleotide thermophoresis (size/charge scaling):
  Duhr & Braun, *Why molecules move along a temperature gradient*, PNAS 2006 —
  https://www.biosystems.physik.lmu.de/paperpdfs/thermophoresis_pnas.pdf ;
  *Thermophoresis of DNA determined by microfluidic fluorescence* —
  https://www.biosystems.physik.uni-muenchen.de/paperpdfs/microfl_thermoph.pdf
- Phosphate adsorption on iron (oxyhydr)oxides under early-Earth conditions:
  *Effects of Amino Acids on Phosphate Adsorption onto Iron (Oxy)hydroxide
  Minerals under Early Earth Conditions*, Caltech —
  https://resolver.caltech.edu/CaltechAUTHORS:20210503-115704077
- Hydrothermal decarboxylation kinetics (acetate derivatives, amino acids,
  pyruvate): *Spectroscopy of Hydrothermal Reactions 13: Decarboxylation of
  Acetic Acid Derivatives at 100–260 °C*, J. Phys. Chem. A —
  https://pubs.acs.org/doi/10.1021/jp984122d ;
  *Thermal degradation of amino acids* (Eₐ 88.5–137 kJ·mol⁻¹), Sci. Rep. 2024 —
  https://www.nature.com/articles/s41598-024-79032-8
- Glycine aqueous diffusivity (1.055–1.064 ×10⁻⁹ m²·s⁻¹):
  *Diffusion of Zwitterion Glycine, Diglycine, and Triglycine in Water* —
  https://arxiv.org/pdf/1706.05491
