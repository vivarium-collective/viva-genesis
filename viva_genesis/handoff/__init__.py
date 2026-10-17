"""Builds-on handoff-contract enforcement (upgrade plan §"Explicit interfaces").

See ``validate`` for the audit that a ``builds on`` edge actually transfers the
required state the plan's handoff table specifies — the composition contract,
not topical similarity.
"""
from .validate import HANDOFF_TABLE, required_state, covers, validate_investigation

__all__ = ["HANDOFF_TABLE", "required_state", "covers", "validate_investigation"]
