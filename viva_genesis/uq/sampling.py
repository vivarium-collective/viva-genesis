"""Uncertainty propagation: draw ensembles from a provenance-carrying parameter package.

Plan section 11, "uncertainty propagation: pass distributions and correlated
states forward, not best-fit scalars". The free parameters of a
:class:`~viva_genesis.provenance.ParameterPackage` define the prior; this module
turns it into an ensemble of parameter dicts a composite generator can consume.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

from ..provenance import ParameterPackage


def lhs_unit(n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` Latin-hypercube points in the unit ``k``-cube (scipy's optimised LHS).

    Falls back to a plain stratified LHS if ``scipy.stats.qmc`` is unavailable.
    """
    try:
        from scipy.stats import qmc
        sampler = qmc.LatinHypercube(d=k, seed=int(rng.integers(0, 2**31 - 1)))
        return sampler.random(n)
    except Exception:  # pragma: no cover - scipy is a hard dep of the workspace
        u = np.empty((n, k))
        for j in range(k):
            perm = rng.permutation(n)
            u[:, j] = (perm + rng.random(n)) / n
        return u


def sample_package(package: ParameterPackage, n: int, rng: np.random.Generator,
                   method: str = "lhs", only: Iterable[str] | None = None) -> list[dict[str, float]]:
    """``n`` prior draws ``{parameter_id: value}`` over the package's free parameters.

    Fixed parameters repeat their nominal value. ``method`` is ``"lhs"`` (default,
    stratified over every free parameter) or ``"mc"`` (independent Monte Carlo).
    ``only`` restricts the free set (the others take their nominal value).
    """
    free = [p for p in package.free() if only is None or p.id in set(only)]
    nominal = package.nominal()
    if not free:
        return [dict(nominal) for _ in range(n)]
    if method == "lhs":
        u = lhs_unit(n, len(free), rng)
    elif method == "mc":
        u = rng.random((n, len(free)))
    else:
        raise ValueError(f"unknown sampling method {method!r}; use 'lhs' or 'mc'")
    cols = {p.id: p.distribution.ppf(u[:, j]) for j, p in enumerate(free)}
    draws = []
    for i in range(n):
        d = dict(nominal)
        for pid, col in cols.items():
            d[pid] = float(col[i])
        draws.append(d)
    return draws


def draws_to_configs(package: ParameterPackage, draws: list[dict[str, float]],
                     mapping: dict[str, str] | None = None) -> list[dict[str, float]]:
    """Map each draw onto generator / process config kwargs via ``package.to_config``."""
    return [package.to_config(mapping=mapping, values=d) for d in draws]


__all__ = ["lhs_unit", "sample_package", "draws_to_configs"]
