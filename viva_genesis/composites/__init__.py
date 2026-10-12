"""viva_genesis composite generators (dashboard-visible entry points).

Each submodule is imported for its side effect so the ``@composite_generator``
decorators fire on package import.
"""

from . import campaign0  # noqa: F401
from . import campaign1  # noqa: F401
from . import campaign2  # noqa: F401

from .campaign0 import og_00_vent_reactor_baseline, og_00_vent_reactor_reduced
from .campaign1 import og_01_geology_to_reduced_carbon
from .campaign2 import og_02_reduced_carbon_to_protometabolism

__all__ = [
    "og_00_vent_reactor_baseline", "og_00_vent_reactor_reduced",
    "og_01_geology_to_reduced_carbon",
    "og_02_reduced_carbon_to_protometabolism",
]
