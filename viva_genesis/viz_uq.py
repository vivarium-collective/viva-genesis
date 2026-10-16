"""Back-compat shim — real home: viva_genesis/visualizations/viz_uq.py.

Viz classes moved under viva_genesis/visualizations/ so the dashboard resolver
and readiness linter discover them (address: local:<ClassName>). This shim keeps
existing `from viva_genesis.viz_uq import ...` imports working.
"""
from .visualizations import viz_uq as _m  # noqa: F401
globals().update({k: getattr(_m, k) for k in dir(_m) if not k.startswith("__")})
del _m
