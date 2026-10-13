"""Autonomy mechanisms — escape from the geological reactor (og-08).

Processes here model a lineage's free-energy + resource budget and its
persistence as external geological support (gradient / mineral access / feed) is
relaxed, with the candidate innovations that could buy autonomy away from the vent
(internal energy conversion, resource import, information maintenance) as
toggleable capabilities. Imported for its auto-registration side effect.
"""

from .off_gradient import (  # noqa: E402,F401
    EnvironmentalRelaxationProcess,
    OffGradientPersistenceProcess,
)

__all__ = ["OffGradientPersistenceProcess", "EnvironmentalRelaxationProcess"]
