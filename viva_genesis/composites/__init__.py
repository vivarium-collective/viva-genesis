"""viva_genesis composite generators (dashboard-visible entry points).

Each submodule is imported for its side effect so the ``@composite_generator``
decorators fire on package import.
"""

from . import campaign0  # noqa: F401

from .campaign0 import og_00_vent_reactor_baseline, og_00_vent_reactor_reduced

__all__ = ["og_00_vent_reactor_baseline", "og_00_vent_reactor_reduced"]
