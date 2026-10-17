"""Bioenergetics module family — selection toward internalized gradient generation.

Covers the final pre-LUCA transition (Module H): whether selection moves lineages
from externally imposed geochemical gradients toward internally maintained
electrochemical states (catalytic ion transport, then active pumping), under the
Sojo leaky-membrane constraint. See ``workspace/notes/modules.md``.
"""

from .selection import (  # noqa: E402,F401
    BioenergeticSelectionProcess,
    EnvironmentalDeclineProcess,
)
from .proto_energetics import (  # noqa: E402,F401
    GeochemicalDriveProcess,
    ProtoEnergyCurrencyProcess,
)
from .thioester_cycle import ThioesterCarrierCycleProcess  # noqa: E402,F401
from .energy_coupling import (  # noqa: E402,F401
    PassiveGradientCouplingProcess,
    IonGradientCouplingProcess,
    ThioesterCouplingProcess,
    PolyphosphateCouplingProcess,
    FeRedoxCouplingProcess,
)

__all__ = [
    "BioenergeticSelectionProcess",
    "EnvironmentalDeclineProcess",
    "GeochemicalDriveProcess",
    "ProtoEnergyCurrencyProcess",
    "ThioesterCarrierCycleProcess",
    "PassiveGradientCouplingProcess",
    "IonGradientCouplingProcess",
    "ThioesterCouplingProcess",
    "PolyphosphateCouplingProcess",
    "FeRedoxCouplingProcess",
]
