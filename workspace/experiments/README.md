# Experiments

Reproduction targets, discriminating experiments, and falsification tests. Full
design in `../notes/experiments-and-falsification.md`.

## Reproduce before extrapolating (benchmark targets)

Each should become a reproducible experiment spec with provenance-linked expected
outputs (`papers.bib` keys + `../datasets/parameter-registry.yaml` ids):

| Target | Reference | What to reproduce |
|---|---|---|
| CO2 fixation product distributions | `preiner2020hydrogen` (ref 15) | H2-dependent CO2 fixation over greigite/magnetite/awaruite at 100 C |
| pH-gradient CO2 reduction | `hudson2020co2` (ref 11) | formate from H2/CO2 across Fe(Ni)S, **with negative controls** |
| Thermophoretic accumulation | `baaske2007extreme` (ref 18) | enrichment vs pore geometry (convection + thermophoresis) |

## Discriminating + falsification tests

See `../notes/experiments-and-falsification.md` for the full discriminating-test
table (in-situ pH correction, sulfur availability, pressure/H2 dependence, pore
lifetime, dilution, network closure, membrane transition, N/P supply, autonomy)
and the "what would seriously weaken the program" list. **Negative controls and
negative regions of parameter space are mandatory validation targets.**

## Acceptance gates

Campaigns I–VI each have an explicit acceptance gate (same note). A campaign
stage is not "done" until its gate is met with conservation diagnostics
(mass/charge/energy) passing.
