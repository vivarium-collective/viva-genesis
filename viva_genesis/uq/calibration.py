"""Bayesian-calibration interface: observations, ABC-rejection posterior, weights.

Plan section 11: *infer parameter distributions from experiments / field data
rather than selecting plausible point values; posterior predictive distributions
for model observables.* Plan section 3 (priority upgrade A): *posterior
predictive analysis — ask what fraction of vent states consistent with observed
systems also satisfy downstream chemical requirements.*

The worked example is **ABC rejection** on observation windows: a prior draw is
*consistent* when every observed readout falls inside its window (a uniform
likelihood on the window), and the posterior is the set of consistent draws.
That is exactly the question the Phase-1 calibration asks, it needs no
likelihood model for noisy field compilations, and it is what MARHYS-style
population windows support. :func:`gaussian_weights` gives the importance-
sampling alternative when a central value + sd is available, and
:class:`Calibrator` is the protocol a PyMC / NumPyro MCMC backend implements
when a stage needs a full posterior over a likelihood.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

import numpy as np


@dataclass
class Observation:
    """One conditioning window on a model readout.

    ``low``/``high`` are the admissible window (either may be ``None`` for a
    one-sided constraint); ``mean``/``sd`` optionally give a Gaussian likelihood
    for :func:`gaussian_weights`. ``readout`` names the key in each outcome
    dict; ``sources`` are bibkeys; ``provenance`` the evidence class.
    """

    name: str
    readout: str
    low: float | None = None
    high: float | None = None
    mean: float | None = None
    sd: float | None = None
    units: str = ""
    sources: list[str] = field(default_factory=list)
    provenance: str = "measured"

    def inside(self, value: float) -> bool:
        if value is None or not np.isfinite(value):
            return False
        if self.low is not None and value < self.low:
            return False
        if self.high is not None and value > self.high:
            return False
        return True

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], "")}

    @classmethod
    def from_package_entry(cls, name: str, entry: Mapping) -> "Observation":
        return cls(name=name, readout=str(entry.get("readout", name)),
                   low=entry.get("low"), high=entry.get("high"),
                   mean=entry.get("mean"), sd=entry.get("sd"),
                   units=str(entry.get("units", "")),
                   sources=list(entry.get("sources") or []),
                   provenance=str(entry.get("provenance", "measured")))


def consistency_mask(outcomes: Sequence[Mapping[str, float]],
                     observations: Sequence[Observation]) -> np.ndarray:
    """Boolean mask: outcome ``i`` lies inside EVERY observation window."""
    mask = np.ones(len(outcomes), dtype=bool)
    for i, out in enumerate(outcomes):
        for obs in observations:
            if not obs.inside(out.get(obs.readout, float("nan"))):
                mask[i] = False
                break
    return mask


def per_observation_masks(outcomes: Sequence[Mapping[str, float]],
                          observations: Sequence[Observation]) -> dict[str, np.ndarray]:
    """Which draws satisfy each observation separately (diagnoses the binding constraint)."""
    return {obs.name: np.array([obs.inside(o.get(obs.readout, float("nan"))) for o in outcomes],
                               dtype=bool) for obs in observations}


@dataclass
class ABCResult:
    n_prior: int
    n_posterior: int
    mask: np.ndarray
    per_observation: dict[str, int]
    acceptance: float

    def to_dict(self) -> dict:
        return {"method": "abc_rejection", "n_prior": self.n_prior, "n_posterior": self.n_posterior,
                "acceptance": self.acceptance, "per_observation": self.per_observation,
                "accepted_indices": [int(i) for i in np.flatnonzero(self.mask)]}


def abc_rejection(outcomes: Sequence[Mapping[str, float]],
                  observations: Sequence[Observation]) -> ABCResult:
    """ABC rejection on windows: the posterior is the prior draws consistent with every observation."""
    mask = consistency_mask(outcomes, observations)
    per = {k: int(v.sum()) for k, v in per_observation_masks(outcomes, observations).items()}
    n = len(outcomes)
    return ABCResult(n, int(mask.sum()), mask, per, float(mask.mean()) if n else float("nan"))


def gaussian_weights(outcomes: Sequence[Mapping[str, float]],
                     observations: Sequence[Observation]) -> np.ndarray:
    """Importance weights ∝ Π_obs N(readout | mean, sd) (observations without mean/sd are windows)."""
    logw = np.zeros(len(outcomes))
    for i, out in enumerate(outcomes):
        for obs in observations:
            v = out.get(obs.readout, float("nan"))
            if not obs.inside(v):          # the window is always hard support
                logw[i] = -np.inf
                break
            if obs.mean is not None and obs.sd:   # the Gaussian shapes the inside
                logw[i] += -0.5 * ((v - obs.mean) / obs.sd) ** 2
    if not np.any(np.isfinite(logw)):
        return np.zeros(len(outcomes))
    w = np.exp(logw - np.nanmax(logw[np.isfinite(logw)]))
    w[~np.isfinite(w)] = 0.0
    s = w.sum()
    return w / s if s > 0 else w


def posterior_summary(draws: Sequence[Mapping[str, float]], weights: np.ndarray,
                      names: Sequence[str] | None = None) -> dict[str, dict]:
    """Weighted mean / sd / 5-95 % range per parameter (prior vs posterior comparison)."""
    weights = np.asarray(weights, dtype=float)
    if weights.sum() <= 0:
        return {}
    w = weights / weights.sum()
    names = list(names or (draws[0].keys() if draws else []))
    out = {}
    for nm in names:
        x = np.array([float(d.get(nm, np.nan)) for d in draws])
        ok = np.isfinite(x) & (w > 0)
        if not ok.any():
            continue
        xs, ws = x[ok], w[ok] / w[ok].sum()
        mean = float(np.sum(ws * xs))
        sd = float(np.sqrt(np.sum(ws * (xs - mean) ** 2)))
        order = np.argsort(xs)
        cdf = np.cumsum(ws[order])
        q05 = float(xs[order][np.searchsorted(cdf, 0.05)])
        q95 = float(xs[order][min(np.searchsorted(cdf, 0.95), len(xs) - 1)])
        out[nm] = {"mean": mean, "sd": sd, "q05": q05, "q95": q95, "n_eff": float(1.0 / np.sum(ws ** 2))}
    return out


class Calibrator(Protocol):
    """The interface a full Bayesian backend (PyMC / NumPyro) implements.

    ``fit`` returns posterior weights over the supplied prior draws (importance
    form) or a fresh set of posterior draws; either way the Phase reports consume
    ``(draws, weights)``. ABC rejection and Gaussian importance weighting above
    are the two built-in implementations.
    """

    def fit(self, draws: Sequence[Mapping[str, float]], outcomes: Sequence[Mapping[str, float]],
            observations: Sequence[Observation]) -> np.ndarray: ...


class ABCRejectionCalibrator:
    def fit(self, draws, outcomes, observations) -> np.ndarray:
        return abc_rejection(outcomes, observations).mask.astype(float)


class GaussianImportanceCalibrator:
    def fit(self, draws, outcomes, observations) -> np.ndarray:
        return gaussian_weights(outcomes, observations)


__all__ = ["Observation", "consistency_mask", "per_observation_masks", "ABCResult",
           "abc_rejection", "gaussian_weights", "posterior_summary", "Calibrator",
           "ABCRejectionCalibrator", "GaussianImportanceCalibrator"]
