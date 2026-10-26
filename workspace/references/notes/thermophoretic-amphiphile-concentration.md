# Can spatial concentration close the self-maintenance gap? — literature grounding

Research step for `og-self-maintaining-concentrated` (Phase-2 discovery cycle). The
connected composite shows reciprocal chemistry↔boundary maintenance *can* close if
the vent pore's thermophoretic trap reaches ~10⁴–10⁸-fold enrichment, which in the
model needs an amphiphile Soret coefficient S_T ≳ 0.07 K⁻¹ and cross-pore ΔT ≳ 45 K
(or S_T ≳ 0.10 at ΔT 30 K). The load-bearing question: **is that S_T defensible for
sub-CAC fatty-acid amphiphiles at vent conditions?** Three findings:

## 1. The mechanism has direct experimental precedent (supports closure)
A thermal-diffusion (thermogravitational) column has been shown to **accumulate
lipid precursors above the critical vesicle concentration**, aiding vesicle
formation — i.e. thermophoretic + convective accumulation can concentrate
amphiphiles past the aggregation threshold, exactly the step the model needs. Vent
thermal gradients (≈5–50 °C across structures) are in the operative range.
- Budin, Bruckner & Szostak, *Formation of Protocell-like Vesicles in a Thermal
  Diffusion Column*, JACS 2009. https://www.researchgate.net/publication/26670316
- Baaske/Braun thermal-trap lineage (DNA/precursor accumulation, exponential in
  pore length): https://www.researchgate.net/publication/44611066

## 2. The Soret coefficient is likely SUPPRESSED at vent conditions (against closure)
For charged micelles the Soret coefficient **decreases strongly with ionic
strength** (scales ∝ Debye length², i.e. ∝ 1/ionic strength) via an interfacial-
tension mechanism. Vents are high-salt (I ~0.1–0.7 M), and above its pKa decanoate
is anionic — so the S_T ≈ 0.07–0.10 the closure needs is **optimistic** for a
charged single-chain amphiphile in seawater; the effective trapping may be well
below the closing regime. S_T can even change sign (thermophilic) at high
concentration / low T.
- Vigolo, Buzzaccaro & Piazza, *Thermophoresis and Thermoelectricity in Surfactant
  Solutions*, Langmuir 2010 (surfactant S_T, ionic-strength dependence).
- *Soret Effect in Interacting Micellar Solutions*:
  https://www.researchgate.net/publication/11364687
- *Why molecules move along a temperature gradient* (Duhr & Braun), PNAS 2006:
  https://www.pnas.org/doi/10.1073/pnas.0603873103

## 3. Premicellar aggregation is real but modest; a stronger alternative exists
C8–C12 fatty-acid soaps show **premicellar aggregation well below the CMC**
(apparent pKa rises below CMC → submicellar aggregates; premicelles range from
dimers to nonamers). Pre-association raises the *effective* particle size and thus
S_T somewhat — but dimers are not ~10× larger, so this alone likely does not reach
S_T 0.10. However, **heated gas–water interfaces concentrate lipids faster than
thermophoresis** (minutes vs. the slower trap) and continuously encapsulate solutes
when oleic acid / DOPC is present — a distinct, possibly stronger concentrating
process to add to the composite.
- Kanicky & Shah, *Effect of Premicellar Aggregation on the pKa of Fatty Acid Soap
  Solutions*, Langmuir 2003. https://pubs.acs.org/doi/10.1021/la020672y
- Matreux et al., *Heated gas bubbles enrich, crystallize, dry, phosphorylate…*,
  Nat. Chem. 2021. https://arxiv.org/pdf/2104.05537
- Caveat (independent, against vent location): single-chain decanoate membranes are
  less stable than dialkyl lipids — often used to argue against ocean/vent origins.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5745557/

## Verdict + next model
Closure is **physically real but contested at vent conditions** → `qualified`, not
`supported`. Two concrete follow-up models: (a) an **ionic-strength-dependent Soret**
for the amphiphile so the trap's enrichment is judged at vent salinity (does salt
suppress it below closure?); (b) a **gas-bubble / interface accumulation** process as
the stronger concentrating mechanism. Build (a) first — it directly tests whether the
closing S_T regime survives seawater.
