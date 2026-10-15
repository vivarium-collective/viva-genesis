"""Information ledger mathematics for competing heredity (Model Upgrade plan, Phase 7).

Two things the Phase-7 verification needs, kept pure (numpy only) so the
ledger process, the study script and the tests share one implementation:

* :func:`mutual_information_bits` — a plug-in (binned) estimator of the
  mutual information I(X; Y) in bits between a parent trait and its
  offspring's trait, on equal-frequency bins (quantile edges pooled over both
  variables so the same partition is used on each side), with the
  Miller–Madow first-order bias correction (Miller 1955). The plug-in
  estimator is biased upward at small n, so the realised *heritable* bits are
  reported net of a permutation null (:func:`heritable_bits`): the MI that
  survives shuffling the parent↔offspring pairing is estimator bias, not
  inheritance.
* :func:`mi_with_convergence` — the convergence check the roadmap asks for
  ("mutual information estimator convergence"): the estimate is recomputed
  on a prefix ladder (n/4, n/2, 3n/4, n — time-ordered, so it is the running
  estimate the ledger publishes each tick) and on bootstrap resamples; the
  estimate is *converged* when the last two rungs of the ladder agree within
  ``tol_bits`` (or ``tol_rel`` of the value) and the bootstrap standard
  error is below ``tol_bits``. An unconverged estimate is still reported, but
  the ledger's ``information_ledger_ok`` flag stays 0 and the study gates
  that read heritable bits require convergence.

Realised heritable bits per generation are what a lineage actually transmits
in its *standing* variation: a population with no phenotypic variance
transmits zero bits by construction (there is nothing to predict), which is
the honest reading — the gate ``ancestry-predicts-phenotype`` asks whether
the parent's phenotype predicts the offspring's, not whether copying is
chemically accurate (that is ``fidelity``, reported separately).
"""

from __future__ import annotations

import math

import numpy as np


RESOLUTION = 0.05   # phenotype resolution: function differences below 5 % are one phenotype


def _edges(values: np.ndarray, n_bins: int, min_width: float = RESOLUTION) -> np.ndarray:
    """Equal-frequency bin edges over ``values`` (interior edges only).

    Repeated values collapse edges (a trait that takes few distinct values
    gets fewer, wider bins), so the partition never has empty bins; edges
    closer than ``min_width`` to the previous kept edge are dropped, so
    variation finer than the phenotype resolution is NOT counted as
    information (selection cannot see it either).
    """
    qs = np.linspace(0.0, 1.0, n_bins + 1)[1:-1]
    edges = np.unique(np.quantile(values, qs))
    kept = []
    last = float(values.min())
    for e in edges:
        if e - last >= min_width:
            kept.append(float(e))
            last = float(e)
    return np.asarray(kept, dtype=float)


def _digitize(x: np.ndarray, y: np.ndarray, n_bins: int, min_width: float = RESOLUTION) -> tuple[np.ndarray, np.ndarray, int]:
    pooled = np.concatenate([x, y])
    edges = _edges(pooled, n_bins, min_width)
    bx = np.searchsorted(edges, x, side="right")
    by = np.searchsorted(edges, y, side="right")
    return bx, by, len(edges) + 1


def mutual_information_bits(x, y, *, n_bins: int = 8, bias_correct: bool = True,
                            min_width: float = RESOLUTION) -> float:
    """Plug-in mutual information I(X;Y) in bits on equal-frequency bins.

    ``n_bins`` is capped so each cell of the joint table expects at least ~5
    samples (``n_bins <= sqrt(n / 5)``) and no bin is narrower than
    ``min_width`` (the phenotype resolution); with the Miller–Madow
    correction ``(K_xy - K_x - K_y + 1) / (2 n ln 2)`` where ``K`` counts the
    occupied cells. Returns ``nan`` for fewer than 8 pairs and 0 when the
    pooled trait spans less than one resolution unit (no transmissible
    phenotypic variation).
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = min(len(x), len(y))
    if n < 8:
        return float("nan")
    x, y = x[:n], y[:n]
    k = max(2, min(int(n_bins), int(math.floor(math.sqrt(n / 5.0)))))
    bx, by, k_eff = _digitize(x, y, k, min_width)
    if k_eff < 2:
        return 0.0
    joint = np.zeros((k_eff, k_eff), dtype=float)
    np.add.at(joint, (bx, by), 1.0)
    p_xy = joint / n
    p_x = p_xy.sum(axis=1, keepdims=True)
    p_y = p_xy.sum(axis=0, keepdims=True)
    mask = p_xy > 0
    mi = float(np.sum(p_xy[mask] * np.log2(p_xy[mask] / (p_x @ p_y)[mask])))
    if bias_correct:
        k_xy = int(mask.sum())
        k_x = int((p_x > 0).sum())
        k_y = int((p_y > 0).sum())
        mi += (k_xy - k_x - k_y + 1) / (2.0 * n * math.log(2.0))
    return max(mi, 0.0)


def permutation_null_bits(x, y, *, n_perm: int = 20, n_bins: int = 8, seed: int = 0) -> float:
    """Mean plug-in MI after shuffling the parent↔offspring pairing (estimator bias)."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = min(len(x), len(y))
    if n < 8:
        return float("nan")
    rng = np.random.default_rng(seed)
    vals = [mutual_information_bits(x[:n], rng.permutation(y[:n]), n_bins=n_bins) for _ in range(int(n_perm))]
    return float(np.mean(vals))


def heritable_bits(x, y, *, n_bins: int = 8, n_perm: int = 20, seed: int = 0) -> float:
    """Realised heritable bits: MI net of the permutation null, floored at 0."""
    mi = mutual_information_bits(x, y, n_bins=n_bins)
    null = permutation_null_bits(x, y, n_bins=n_bins, n_perm=n_perm, seed=seed)
    if not (math.isfinite(mi) and math.isfinite(null)):
        return float("nan")
    return max(mi - null, 0.0)


def mi_with_convergence(x, y, *, n_bins: int = 8, n_boot: int = 40, n_perm: int = 20,
                        tol_bits: float = 0.05, tol_rel: float = 0.15, seed: int = 0) -> dict:
    """The MI estimate with its convergence diagnostics.

    Returns ``{"n", "mi", "null", "heritable_bits", "se", "ladder": [(n_k, mi_k)],
    "ladder_delta", "converged"}``. ``converged`` requires (i) the prefix
    ladder's last two rungs to agree within ``max(tol_bits, tol_rel * mi)``
    and (ii) the bootstrap standard error of the net estimate to be below
    ``tol_bits``; with fewer than 32 pairs the estimate is never converged.
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = min(len(x), len(y))
    out = {"n": int(n), "mi": float("nan"), "null": float("nan"), "heritable_bits": float("nan"),
           "se": float("nan"), "ladder": [], "ladder_delta": float("nan"), "converged": False}
    if n < 8:
        return out
    x, y = x[:n], y[:n]
    mi = mutual_information_bits(x, y, n_bins=n_bins)
    null = permutation_null_bits(x, y, n_bins=n_bins, n_perm=n_perm, seed=seed)
    net = max(mi - null, 0.0)
    rungs = sorted({max(8, n // 4), max(8, n // 2), max(8, (3 * n) // 4), n})
    ladder = []
    for m in rungs:
        v = mutual_information_bits(x[:m], y[:m], n_bins=n_bins)
        v0 = permutation_null_bits(x[:m], y[:m], n_bins=n_bins, n_perm=max(5, n_perm // 2), seed=seed + m)
        ladder.append((int(m), float(max(v - v0, 0.0))))
    rng = np.random.default_rng(seed + 1)
    boots = []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, n, n)
        boots.append(mutual_information_bits(x[idx], y[idx], n_bins=n_bins))
    se = float(np.std(boots, ddof=1)) if len(boots) > 1 else float("nan")
    delta = abs(ladder[-1][1] - ladder[-2][1]) if len(ladder) >= 2 else float("nan")
    converged = bool(n >= 32 and math.isfinite(delta) and math.isfinite(se)
                     and delta <= max(tol_bits, tol_rel * net) and se <= tol_bits)
    out.update({"mi": float(mi), "null": float(null), "heritable_bits": float(net), "se": se,
                "ladder": ladder, "ladder_delta": float(delta), "converged": converged})
    return out


def heritability_slope(x, y) -> float:
    """Realised heritability: slope of offspring trait on parent trait (og-06's measure)."""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = min(len(x), len(y))
    if n <= 10:
        return float("nan")
    x, y = x[:n], y[:n]
    if x.std() <= 1e-9:
        return float("nan")
    return float(np.polyfit(x, y, 1)[0])


def information_per_cost(heritable_bits_value: float, energy_per_offspring_j: float,
                         precursors_per_offspring: float) -> dict:
    """Bits per joule and bits per precursor molecule (``inf`` when the cost is zero)."""
    def _ratio(num, den):
        if not math.isfinite(num):
            return float("nan")
        if den <= 0.0:
            return float("inf") if num > 0 else 0.0
        return num / den
    return {"bits_per_joule": _ratio(heritable_bits_value, energy_per_offspring_j),
            "bits_per_precursor": _ratio(heritable_bits_value, precursors_per_offspring)}


def pareto_front(points: dict[str, tuple[float, float]]) -> list[str]:
    """Classes on the (maximise bits, minimise energy) Pareto front.

    ``points = {class: (heritable_bits, energy_per_offspring_j)}``; a class is
    dominated when another has at least as many bits at no more energy, with
    one strictly better. Non-finite points are excluded.
    """
    keep = []
    items = {k: v for k, v in points.items() if all(math.isfinite(float(c)) for c in v)}
    for k, (b, e) in items.items():
        dominated = False
        for k2, (b2, e2) in items.items():
            if k2 == k:
                continue
            if b2 >= b and e2 <= e and (b2 > b or e2 < e):
                dominated = True
                break
        if not dominated:
            keep.append(k)
    return sorted(keep)


__all__ = ["mutual_information_bits", "permutation_null_bits", "heritable_bits", "mi_with_convergence",
           "heritability_slope", "information_per_cost", "pareto_front"]
