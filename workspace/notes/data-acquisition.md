# Data acquisition priorities

From the Campaign dossier §8. Every digitized dataset is stored **separately from
model code**, linked to a DOI plus a condition vector, so a parameter fitted from
one experiment retains a pointer to the exact source experiment (interpolation vs
extrapolation stays distinguishable). Register each as a workspace dataset
(`../datasets/`).

## Field datasets (FIELD provenance)

- **Lost City:** vent-fluid T, pH with measurement convention, H2, CH4, DIC,
  major ions, trace metals, mineralogy, chimney structure/porosity, and time
  series where available.
- **Other serpentinizing systems:** Rainbow, Von Damm, Prony, Strytan and
  continental serpentinite springs — to quantify how variable "alkaline vent"
  chemistry actually is.
- **InterRidge global active vent database:** distributions of vent setting,
  depth, temperature and tectonic context — use as an environmental **prior**
  rather than a Lost City-only world.
- **Ancient-ocean geochemical reconstructions:** CO2/DIC, sulfate/sulfide,
  phosphate, Fe and ionic strength. Critical — modern seawater cannot simply be
  substituted for Hadean ocean chemistry.

## Laboratory datasets worth digitizing (LAB-DIRECT / LAB-ANALOG)

- **Hudson et al. 2020** (ref 11): product vs pH gradient, catalyst composition,
  H2, pressure and controls.
- **Altair et al. 2025** (ref 12): time courses, currents, Ni content, mineral
  characterization, temperature effects and passive/induced potentials.
- **Preiner et al. 2020** (ref 15): product distributions by mineral, temperature,
  pressure and reaction time.
- **Muchowska et al. 2017/2019** (refs 16, 17): reaction yields and condition
  windows for each network edge; include off-pathway products.
- **Jordan et al. 2019** (ref 20): vesicle formation/stability across amphiphile
  mixtures, pH, salts, divalent ions and temperature.
- **Baaske 2007 / Mast & Braun 2010** (refs 18, 19): transport equations, Soret
  coefficients/geometry assumptions and observed trapping kinetics.
- **Dörr et al. 2003** and phosphorus studies (refs 22, 23): yields, surface-age
  effects, pH dependence and detection limits.

## Provenance-first implementation

Store every digitized dataset separately from model code; link to a DOI + a
condition vector. A parameter fitted from one experiment must retain a pointer to
its exact source experiment, so later model comparisons can distinguish
interpolation from extrapolation. This is essential for a campaign likely to
combine dozens of heterogeneous papers.
