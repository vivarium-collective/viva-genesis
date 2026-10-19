"""Protometabolism module family — carbon fixation and reaction networks.

Covers Campaign modules **D** (mineral-catalyzed carbon fixation) and **E**
(protometabolic network formation). See ``workspace/notes/modules.md``.

Planned process contracts (not yet implemented):

- ``surface_chemistry(adsorbed_species, minerals)`` → ``organics``
  (reaction-network kinetics on Fe/Ni/S surfaces).
- ``protometabolism(organic_network)`` → ``fluxes, cycles``.
  Build a curated reaction graph from formate, acetate, pyruvate, glyoxylate and
  organic acids; include measured nonenzymatic routes, reversible reactions and
  competing sinks. ``dC/dt = S v(C, T, pH, catalyst) + transport``; check
  thermodynamic consistency and element balance BEFORE fitting kinetics.
  Persistent flux cycles, autocatalytic motifs, cross-catalysis and product
  retention are **emergent observables, not assumptions**.
  Recommended engine: SBML + libRoadRunner/Tellurium or COPASI; SciPy solve_ivp;
  Cantera for suitable reaction kinetics; eQuilibrator for thermodynamic checks.
  Provenance/calibration: ``huber1997activated``, ``varma2018native``,
  ``preiner2020hydrogen`` (yields are LAB outcomes, not environmental conc.),
  ``muchowska2017metals``, ``muchowska2019synthesis``.

Outputs: carbon conversion, yields, network persistence, energy dissipation,
selectivity. Do NOT substitute steady-state FBA for origins-stage chemistry.

Phase 3 adds the proto_metabolism face classes: ``universe`` (rule-generated
network + eQuilibrator potentials + matched nulls), ``motifs`` (post-hoc
autocatalysis detection, enrichment, flux control, stiffness) and
``universe_process`` (``ReactionUniverseProcess`` / ``NullNetworkProcess``).
"""

from .thermo import EquilibratorThermoStep  # noqa: E402,F401
from .carbon_fixation import CarbonFixationProcess  # noqa: E402,F401
from .network import RoadRunnerNetworkProcess  # noqa: E402,F401
from .universe_process import ReactionUniverseProcess, NullNetworkProcess  # noqa: E402,F401
from .rtca import RTCANetworkProcess, RTCANullProcess  # noqa: E402,F401
from .precursor_pool import PrecursorPoolProcess  # noqa: E402,F401

__all__ = ["EquilibratorThermoStep", "CarbonFixationProcess", "RoadRunnerNetworkProcess",
           "ReactionUniverseProcess", "NullNetworkProcess",
           "RTCANetworkProcess", "RTCANullProcess", "PrecursorPoolProcess"]
