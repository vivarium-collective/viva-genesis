"""Geochemistry module family — serpentinization and limiting-resource chemistry.

Covers Campaign modules **A** (serpentinization and geochemical energy supply)
and **I** (nitrogen, phosphorus and other limiting resources), plus reactive
precipitation shared with `viva_genesis.transport`. See
``workspace/notes/modules.md`` for the full mechanism/evidence writeup.

Planned process contracts (not yet implemented):

- ``serpentinization(rock_state, water_flux, T, P)``
  → ``H2_flux, alkalinity_flux, heat_flux, mineral_transformations, dissolved_metals``.
  Treat H2 output as a distribution, not a fixed concentration.
  Recommended engine: PHREEQC or Reaktoro (equilibrium + kinetic rate laws
  ``dM/dt = k * A * f(T, pH, activities)``). Provenance: field refs
  ``kelley2001offaxis``, ``fruhgreen2003thirtythousand``, ``ludwig2006formation``,
  review ``schwander2023serpentinization``.
- resource modules: ``fes_n2_fixation`` (ref ``dorr2003prebiotic``),
  ``schreibersite_phosphorylation`` (ref ``pasek2017schreibersite``).

Contracts must declare units and conservation predicates (mass/elements for
C,H,O,N,P,S,Fe,Ni; charge; energy) per ``workspace/notes/architecture.md``.

Campaign 0 ships Module A as a **real PHREEQC bridge**
(``PhreeqcSerpentinizationProcess`` — genuine IPhreeqc speciation + mineral
equilibrium via ``phreeqpython`` + the vendored ``data/llnl.dat``) plus the
original ``SerpentinizationReproductionProcess`` (a tuned Gaussian source) kept
as a runs-anywhere fallback for environments without ``phreeqpython`` installed.
Both are re-exported here so ``build_core()``'s non-recursive package walk
registers them.
"""

from .phreeqc_serpentinization import PhreeqcSerpentinizationProcess  # noqa: E402,F401
from .serpentinization import SerpentinizationReproductionProcess  # noqa: E402,F401
from .nitrogen_assimilation import ReducedNitrogenProductionProcess  # noqa: E402,F401
from .phosphorus_speciation import PhosphorusSpeciationProcess  # noqa: E402,F401

__all__ = ["PhreeqcSerpentinizationProcess", "SerpentinizationReproductionProcess",
           "ReducedNitrogenProductionProcess", "PhosphorusSpeciationProcess"]
