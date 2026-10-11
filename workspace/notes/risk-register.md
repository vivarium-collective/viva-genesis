# Evidence gaps and model risk register

From the Campaign dossier §9. Priorities are the dossier's; "treatment in
campaign" is how each risk is handled by design rather than ignored.

| Risk | Why it matters | Treatment in campaign | Priority |
|---|---|---|---|
| Ancient ocean composition poorly constrained | Controls pH, carbon speciation, minerals and nutrients | Ensemble priors + sensitivity analysis | **Very high** |
| Lost City is not Hadean Earth | Modern biology/oxidation and geology differ | Separate field calibration from ancient extrapolation | **Very high** |
| In-situ pH / gradient controversy | Directly affects the proposed chemiosmotic driving force | Implement competing thermodynamic models (classical vs Tutolo 2026 / Jackson 2016) | **Very high** |
| Catalyst preparation dependence | Fresh FeS/NiS can behave unlike aged natural minerals | Surface-state variable + aging kinetics | High |
| Sparse kinetic data | Many studies report endpoint yields, not rates | Bayesian ranges; target new experiments | High |
| Product detection near limits | False positives / contamination possible in origins chemistry | Use controls and isotope-label evidence weighting | High |
| No complete path to heredity | Prevents a claim of full abiogenesis | Keep late stages modular and hypothesis-comparative (Module J branch point) | **Very high** |
| Scale gap from reactor to geology | Lab geometry may exaggerate gradients and contact | Dimensionless scaling and multiple geometries | High |
| Narrative bias | Easy to select only favorable papers | Encode critiques / negative outcomes as validation targets | **Very high** |

## Standing design guards (Methods Atlas §11)

- **Geochemical consistency:** PHREEQC/Reaktoro may predict different results
  depending on database and activity model; establish a fixed reference suite.
- **Redox accounting:** separate chemical affinity from kinetically accessible
  electron transfer.
- **Surface chemistry:** do not equate mineral presence with catalytic activity;
  curate catalyst identity, area, oxidation state and passivation.
- **Scale bridging:** use MD only to calibrate transport or binding laws that
  influence mesoscopic behavior.
- **Evolution:** do not substitute steady-state FBA for origins-stage chemistry.
- **Model falsification:** compare alternatives (weak gradient, high dilution,
  absent sulfur, phosphorus limitation) and **report negative regions of
  parameter space**.
