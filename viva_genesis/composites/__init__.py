"""viva_genesis composite generators (dashboard-visible entry points).

Every submodule here is imported for its side effect — the
``@composite_generator`` decorators fire on package import, registering each
generator in the process-bigraph registry. Discovery is by a package glob (not a
hand-maintained ``from . import X`` list): dropping a new ``*.py`` composite in
this directory registers it automatically, with no manual append. (That manual
append block used to be a merge-conflict magnet — every spine/rescope PR edited
the same anchor.)

``__all__`` is the submodule list, built the same way. Composite references
resolve by their full ``viva_genesis.composites.<module>.<generator>`` id via the
registry / import path, so no package-level function re-exports are needed.
"""
import importlib as _importlib
import pkgutil as _pkgutil

__all__ = []
for _m in _pkgutil.iter_modules(__path__):
    _importlib.import_module(f"{__name__}.{_m.name}")
    __all__.append(_m.name)
__all__ = sorted(__all__)
