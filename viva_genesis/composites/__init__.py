"""viva_genesis composite generators (dashboard-visible entry points).

Each submodule is imported for its side effect so the ``@composite_generator``
decorators fire on package import.
"""

from . import vent_reactor  # noqa: F401
from . import carbon_fixation  # noqa: F401
from . import protometabolism  # noqa: F401

from .vent_reactor import serpentinizing_vent_reactor, serpentinizing_vent_reactor_reduced
from .carbon_fixation import hydrothermal_carbon_fixation
from .protometabolism import protometabolic_network

__all__ = [
    "serpentinizing_vent_reactor", "serpentinizing_vent_reactor_reduced",
    "hydrothermal_carbon_fixation",
    "protometabolic_network",
]
