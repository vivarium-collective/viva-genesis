"""Membrane / protocell module family — mixed-amphiphile vesicles (Campaign G).

Covers the organic-boundary transition: mixed single-chain amphiphiles assembling
into vesicles that retain chemistry while staying permeable to the external
geochemical gradient (Jordan 2019). See ``workspace/notes/modules.md``.
"""

from .protocell_assembly import ProtocellAssemblyProcess  # noqa: E402,F401
from .amphiphile_chain_extension import AmphiphileChainExtensionProcess  # noqa: E402,F401

__all__ = ["ProtocellAssemblyProcess", "AmphiphileChainExtensionProcess"]
