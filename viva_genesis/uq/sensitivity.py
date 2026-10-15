"""Global sensitivity analysis: Morris screening, then Sobol indices.

Plan section 11: *use Morris screening followed by Sobol indices on influential
parameters — rank controlling mechanisms and experimental priorities.* Both are
implemented directly on NumPy (no SALib dependency) so they run anywhere the
workspace runs, and both take any ``model(x: dict[str, float]) -> float``.

* :func:`morris` — Campolongo-style elementary effects over ``r`` random
  trajectories on a ``levels``-level grid; returns ``mu``, ``mu_star`` (mean
  absolute effect, the screening rank) and ``sigma`` (interaction / nonlinearity)
  per parameter.
* :func:`sobol` — Saltelli A/B/AB sampling with Sobol' quasi-random points and
  the Jansen estimators for first-order ``S1`` and total-order ``ST`` indices,
  plus bootstrap confidence intervals.

``bounds`` is ``{name: (low, high)}``; names in ``log_params`` are sampled
uniformly in log10 space (the right scale for rates and fluxes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

import numpy as np


def _to_physical(u: np.ndarray, names: list[str], bounds: Mapping[str, tuple[float, float]],
                 log_params: set[str]) -> list[dict[str, float]]:
    out = []
    for row in np.atleast_2d(u):
        x = {}
        for j, name in enumerate(names):
            lo, hi = bounds[name]
            if name in log_params:
                x[name] = float(10 ** (np.log10(lo) + row[j] * (np.log10(hi) - np.log10(lo))))
            else:
                x[name] = float(lo + row[j] * (hi - lo))
        out.append(x)
    return out


def _evaluate(model: Callable, points: list[dict[str, float]], tolerant: bool) -> np.ndarray:
    ys = []
    for x in points:
        try:
            ys.append(float(model(x)))
        except Exception:
            if not tolerant:
                raise
            ys.append(float("nan"))
    return np.asarray(ys, dtype=float)


@dataclass
class MorrisResult:
    names: list[str]
    mu: dict[str, float]
    mu_star: dict[str, float]
    sigma: dict[str, float]
    n_evaluations: int
    ranking: list[str]          # by mu_star, descending

    def to_dict(self) -> dict:
        return {"method": "morris", "names": self.names, "mu": self.mu, "mu_star": self.mu_star,
                "sigma": self.sigma, "n_evaluations": self.n_evaluations, "ranking": self.ranking}


def morris(model: Callable[[dict], float], bounds: Mapping[str, tuple[float, float]], *,
           r: int = 4, levels: int = 4, rng: np.random.Generator | None = None,
           log_params: Iterable[str] = (), tolerant: bool = True) -> MorrisResult:
    """Morris elementary-effects screening (``r`` trajectories, ``(k+1)·r`` model calls)."""
    rng = rng or np.random.default_rng(0)
    names = list(bounds)
    k = len(names)
    log_params = set(log_params)
    delta = levels / (2.0 * (levels - 1))
    effects = {n: [] for n in names}
    n_eval = 0
    for _ in range(r):
        # random base point on the grid (only levels that keep x+delta inside [0,1])
        grid = np.arange(0, levels - 1) / (levels - 1)       # 0 .. (levels-2)/(levels-1)
        base = rng.choice(grid, size=k)
        order = rng.permutation(k)
        x = base.copy()
        y_prev = _evaluate(model, _to_physical(x, names, bounds, log_params), tolerant)[0]
        n_eval += 1
        for j in order:
            x_new = x.copy()
            x_new[j] = x[j] + delta if x[j] + delta <= 1.0 else x[j] - delta
            y_new = _evaluate(model, _to_physical(x_new, names, bounds, log_params), tolerant)[0]
            n_eval += 1
            sign = 1.0 if x_new[j] > x[j] else -1.0
            if np.isfinite(y_new) and np.isfinite(y_prev):
                effects[names[j]].append(sign * (y_new - y_prev) / delta)
            x, y_prev = x_new, y_new
    mu = {n: (float(np.mean(v)) if v else float("nan")) for n, v in effects.items()}
    mu_star = {n: (float(np.mean(np.abs(v))) if v else float("nan")) for n, v in effects.items()}
    sigma = {n: (float(np.std(v, ddof=1)) if len(v) > 1 else float("nan")) for n, v in effects.items()}
    ranking = sorted(names, key=lambda n: -(mu_star[n] if np.isfinite(mu_star[n]) else -1.0))
    return MorrisResult(names, mu, mu_star, sigma, n_eval, ranking)


@dataclass
class SobolResult:
    names: list[str]
    S1: dict[str, float]
    ST: dict[str, float]
    S1_conf: dict[str, float]
    ST_conf: dict[str, float]
    n_evaluations: int
    variance: float

    def to_dict(self) -> dict:
        return {"method": "sobol", "names": self.names, "S1": self.S1, "ST": self.ST,
                "S1_conf": self.S1_conf, "ST_conf": self.ST_conf,
                "n_evaluations": self.n_evaluations, "variance": self.variance}


def sobol(model: Callable[[dict], float], bounds: Mapping[str, tuple[float, float]], *,
          n: int = 256, rng: np.random.Generator | None = None, log_params: Iterable[str] = (),
          n_boot: int = 200, tolerant: bool = True) -> SobolResult:
    """Sobol' first- and total-order indices by Saltelli sampling + Jansen estimators.

    ``n`` base points (a power of two is best) → ``n·(k+2)`` model calls.
    """
    rng = rng or np.random.default_rng(0)
    names = list(bounds)
    k = len(names)
    log_params = set(log_params)
    try:
        from scipy.stats import qmc
        sampler = qmc.Sobol(d=2 * k, scramble=True, seed=int(rng.integers(0, 2**31 - 1)))
        m = int(2 ** np.ceil(np.log2(max(n, 2))))
        ab = sampler.random(m)[:n]
    except Exception:  # pragma: no cover
        ab = rng.random((n, 2 * k))
    A, B = ab[:, :k], ab[:, k:]
    yA = _evaluate(model, _to_physical(A, names, bounds, log_params), tolerant)
    yB = _evaluate(model, _to_physical(B, names, bounds, log_params), tolerant)
    yAB = []
    for j in range(k):
        ABj = A.copy()
        ABj[:, j] = B[:, j]
        yAB.append(_evaluate(model, _to_physical(ABj, names, bounds, log_params), tolerant))
    yAB = np.asarray(yAB)
    n_eval = n * (k + 2)

    def _indices(idx):
        a, b, abm = yA[idx], yB[idx], yAB[:, idx]
        ok = np.isfinite(a) & np.isfinite(b) & np.all(np.isfinite(abm), axis=0)
        a, b, abm = a[ok], b[ok], abm[:, ok]
        var = float(np.var(np.concatenate([a, b]), ddof=1)) if a.size > 1 else float("nan")
        if not (var > 0):
            return np.full(k, np.nan), np.full(k, np.nan), var
        s1 = np.array([1.0 - np.mean((b - abm[j]) ** 2) / (2.0 * var) for j in range(k)])
        st = np.array([np.mean((a - abm[j]) ** 2) / (2.0 * var) for j in range(k)])
        return s1, st, var

    s1, st, var = _indices(np.arange(n))
    boots1, bootst = [], []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, n)
        b1, bt, _ = _indices(idx)
        boots1.append(b1)
        bootst.append(bt)
    s1_conf = 1.96 * np.nanstd(np.asarray(boots1), axis=0) if n_boot else np.full(k, np.nan)
    st_conf = 1.96 * np.nanstd(np.asarray(bootst), axis=0) if n_boot else np.full(k, np.nan)
    return SobolResult(
        names,
        {nm: float(s1[j]) for j, nm in enumerate(names)},
        {nm: float(st[j]) for j, nm in enumerate(names)},
        {nm: float(s1_conf[j]) for j, nm in enumerate(names)},
        {nm: float(st_conf[j]) for j, nm in enumerate(names)},
        n_eval, var,
    )


__all__ = ["morris", "sobol", "MorrisResult", "SobolResult"]
