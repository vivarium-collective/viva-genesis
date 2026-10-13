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

__all__ = ["BioenergeticSelectionProcess", "EnvironmentalDeclineProcess"]
