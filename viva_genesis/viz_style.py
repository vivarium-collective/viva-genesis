"""Back-compat shim — real home: viva_genesis/visualizations/viz_style.py.

Viz classes moved under viva_genesis/visualizations/ so the dashboard resolver
and readiness linter discover them (address: local:<ClassName>). This shim keeps
existing `from viva_genesis.viz_style import ...` imports working.
"""
from .visualizations import viz_style as _m  # noqa: F401
globals().update({k: getattr(_m, k) for k in dir(_m) if not k.startswith("__")})
del _m
