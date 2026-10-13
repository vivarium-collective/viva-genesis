"""Compartments module family — amphiphiles, protocells, bioenergetics.

Covers Campaign modules **G** (mineral compartments to organic protocells) and
**H** (bioenergetic internalization). See ``workspace/notes/modules.md``.

Planned process contracts (not yet implemented):

- ``amphiphile_dynamics(lipids, surfaces)`` → ``vesicles, permeability``.
  Model amphiphile supply/import, aggregation, mixed-membrane stability,
  permeability, osmotic balance and division; compare mineral-confined vs free
  vesicles. Compartment agents exchange species through flux laws; include
  leakage, ion partitioning, membrane area, tension and energy constraints.
  Recommended engine: custom coarse-grained membrane kinetics; Smoldyn/ReaDDy for
  spatial stochastic reactions; OpenMM/LAMMPS for targeted parameter studies.
  Provenance: ``jordan2019promotion`` (vesicle feasibility map).
- bioenergetic internalization (evolutionary control problem): vary membrane
  permeability, Na+/H+ coupling, gradient magnitude and catalyst efficiency;
  reward carbon/energy throughput and compartment persistence; test whether
  selection favors internalized gradient generation. Provenance: ``lane2012origin``,
  ``sojo2014bioenergetic``.

Central tension: retain enough for selection while staying permeable enough to
exploit external gradients. Outputs: viable compartment count, chemical retention,
membrane growth and stability.

Implemented: ``OsmoticGrowthDivisionProcess`` (metabolism → growth & division) —
an internal autocatalytic osmolyte source coupled to compartment osmotic physics
(product → osmotic pressure → solvent influx → volume growth → division / lysis /
starvation set by membrane permeability).
"""

from .osmotic_growth_division import OsmoticGrowthDivisionProcess  # noqa: E402,F401

__all__ = ["OsmoticGrowthDivisionProcess"]
