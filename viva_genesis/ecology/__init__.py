"""Ecology module family — populations, evolution, and the pre-LUCA transition.

Covers Campaign Stage 7/8 (ecosystems, autonomy and pre-LUCA transitions) and the
LUCA far-end boundary condition. See ``workspace/notes/modules.md``.

Planned process contracts (not yet implemented):

- ``compartment_ecology(pores, protocells)`` → ``growth, fission, extinction``
  (agent-based population process over shared spatial fields).
- ``evolution(heritable_traits)`` → ``selection, innovation``
  (population genetics / adaptive search). Couple heterogeneous compartments,
  cross-feeding, migration, environmental fluctuations and active transport;
  select for independence from vent gradients. Evaluate environmental energy
  dependence, ecological stability and population-level selection.
  Recommended engine: Vivarium multi-agent composites; COBRApy for later
  genome-scale metabolic benchmarks; evolutionary algorithms / Bayesian
  calibration.

**LUCA boundary condition:** use phylogenomic reconstructions as constraints on
which capabilities must eventually be acquired, NOT as evidence the first
replicators had LUCA-like complexity. Provenance: ``weiss2016physiology`` (355
protein families, anaerobic H2/CO2/FeS physiology), ``moody2024nature`` (~4.2 Ga
LUCA embedded in an ecosystem).

Outputs: autonomous lineages, metabolic diversity, cross-feeding and robustness.

Implemented (og-07): ``CrossFeedingMetacommunityProcess`` — a coarse-grained,
deterministic cross-feeding metacommunity over N connected compartments.

Implemented (Phase 8, og-07-alt-real-metabolite-exchange): ``proto_ecology`` —
real reaction networks per protocell (``ProtocellNetworkProcess`` /
``ProtocellNullNetworkProcess`` on the ``proto_ecology`` face), the
``SpatialCouplingStep`` onto the Phase-4 fields with the exchange rules of a
``BigraphicalReactiveSystem`` (``reactive_system``), and the
``EcologyReducerStep`` that keeps og-07's gate names.
"""

from .metacommunity import CrossFeedingMetacommunityProcess  # noqa: E402,F401
from .proto_ecology import (EcologyReducerStep, ProtocellNetworkProcess,  # noqa: E402,F401
                            ProtocellNullNetworkProcess, SpatialCouplingStep)
from .reactive_system import BigraphicalReactiveSystem  # noqa: E402,F401
from .stochastic_ecology import StochasticProtocellEcologyProcess  # noqa: E402,F401

__all__ = ["CrossFeedingMetacommunityProcess", "ProtocellNetworkProcess", "ProtocellNullNetworkProcess",
           "SpatialCouplingStep", "EcologyReducerStep", "BigraphicalReactiveSystem",
           "StochasticProtocellEcologyProcess"]
