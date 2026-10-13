"""viva_genesis composite generators (dashboard-visible entry points).

Each submodule is imported for its side effect so the ``@composite_generator``
decorators fire on package import.
"""

from . import vent_reactor  # noqa: F401
from . import carbon_fixation  # noqa: F401
from . import protometabolism  # noqa: F401
from . import thermophoretic_concentration  # noqa: F401
from . import mixed_amphiphile_protocell  # noqa: F401
from . import bioenergetic_internalization  # noqa: F401
from . import heredity_module_comparison  # noqa: F401
from . import heredity_lineage  # noqa: F401
from . import off_gradient_persistence  # noqa: F401
from . import cross_feeding_metacommunity  # noqa: F401
from . import nitrogen_assimilation  # noqa: F401

from .vent_reactor import serpentinizing_vent_reactor, serpentinizing_vent_reactor_reduced
from .carbon_fixation import hydrothermal_carbon_fixation
from .protometabolism import protometabolic_network
from .thermophoretic_concentration import thermophoretic_concentration
from .mixed_amphiphile_protocell import mixed_amphiphile_protocell
from .bioenergetic_internalization import bioenergetic_internalization
from .heredity_module_comparison import heredity_module_comparison
from .heredity_lineage import heredity_lineage_comparison
from .off_gradient_persistence import off_gradient_persistence
from .cross_feeding_metacommunity import cross_feeding_metacommunity
from .nitrogen_assimilation import reduced_nitrogen_reactor

__all__ = [
    "serpentinizing_vent_reactor", "serpentinizing_vent_reactor_reduced",
    "hydrothermal_carbon_fixation",
    "protometabolic_network",
    "thermophoretic_concentration",
    "mixed_amphiphile_protocell",
    "bioenergetic_internalization",
    "heredity_module_comparison",
    "heredity_lineage_comparison",
    "off_gradient_persistence",
    "cross_feeding_metacommunity",
    "reduced_nitrogen_reactor",
]
