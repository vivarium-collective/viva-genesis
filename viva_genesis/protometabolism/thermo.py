"""Module D (thermodynamics) — imported from viva-equilibrator.

The real eQuilibrator feasibility gate that used to live here is now
``EquilibratorThermoStep``, shipped by the **viva-equilibrator** package (the
process-bigraph wrapper for the component-contribution engine). It is imported
and re-exported here so existing
``from viva_genesis.protometabolism.thermo import EquilibratorThermoStep``
call sites keep working; ``viva_genesis.core.build_core`` registers
``local:EquilibratorThermoStep`` from the imported class.

The default reaction set (H2-driven reductive CO2 fixation to
formate/acetate/pyruvate) and all ports are unchanged — the wrapper's default
``reactions`` config reproduces the original ports exactly. The build-time ΔG'°
helper is ``viva_equilibrator.standard_dg_primes`` (used by
``viva_genesis.protometabolism.universe``).
"""

from __future__ import annotations

from viva_equilibrator import EquilibratorThermoStep  # noqa: F401

__all__ = ["EquilibratorThermoStep"]
