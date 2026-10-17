"""Explicit amphiphile chain-extension chemistry (study 17 REBUILD chemistry).

Replaces the lumped ``acetate + formate -> one generic amphiphile`` condensation with
explicit 2-carbon fatty-acid ELONGATION across multiple chain lengths, degradation,
and a length-dependent critical aggregation concentration (CAC falls as chains grow,
so only a long-enough-chain pool is aggregation-competent). The amphiphiles form only
from the vent-carbon feed (no exogenous amphiphile pool), and all degradation losses
are tracked — the study-17 decision test: reach an experimentally-grounded
aggregation-competent composition WITHOUT an exogenous amphiphile feed.

Chemistry (named, iterative):
  seed:       2 acetate (C2)  -> C4 fatty acid
  elongation: C_L + acetate(C2) -> C_{L+2}      (fatty-acid synthesis motif)
  degradation: C_L + H2O -> C_{L-2} + acetate   (hydrolysis / reverse, a tracked loss)

Assembly ties to og-31's real Martini membrane engine: a composition that clears the
CAC is the input a viva-openmm bilayer run would assemble.
"""
from __future__ import annotations

from process_bigraph import Process

_MOLAR_IN = {"_type": "float", "_units": "molar"}
_K_IN = {"_type": "float", "_units": "kelvin"}
_OW = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}


class AmphiphileChainExtensionProcess(Process):
    """Explicit fatty-acid chain elongation -> chain-length distribution + CAC clearance."""

    config_schema = {
        "k_seed": {"_type": "float", "_default": 0.3, "_units": "1/second"},      # 2 C2 -> C4
        "k_extend": {"_type": "float", "_default": 0.4, "_units": "1/second"},    # C_L + C2 -> C_{L+2}
        "k_degrade": {"_type": "float", "_default": 0.02, "_units": "1/second"},  # hydrolysis loss
        "max_length": {"_type": "integer", "_default": 16},
        "long_chain_min": {"_type": "integer", "_default": 10},   # vesicle-competent threshold
        "cac_molar": {"_type": "float", "_default": 5.0e-3, "_units": "molar"},   # long-chain CAC
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._pool = {}          # {chain_length(int, even): molar}
        self._cum_degrade = 0.0  # cumulative carbon lost to degradation

    def inputs(self):
        return {"acetate": _MOLAR_IN, "temperature": _K_IN}

    def outputs(self):
        return {
            "mean_chain_length": _OW,
            "amphiphile_total": _OW_MOLAR,
            "long_chain_fraction": _OW,       # fraction of the pool at/above long_chain_min
            "aggregation_competent": _OW,     # long-chain pool / CAC (>=1 = clears, competent)
            "degradation_loss": _OW_MOLAR,    # cumulative carbon lost to hydrolysis
        }

    def initial_state(self):
        return {"acetate": 0.0, "temperature": 330.0}

    def update(self, state, interval):
        acetate = max(0.0, float(state.get("acetate", 0.0)))
        max_len = int(self.config["max_length"])
        k_seed = self.config["k_seed"]
        k_ext = self.config["k_extend"]
        k_deg = self.config["k_degrade"]
        has_feed = acetate > 0.0

        delta = {}  # length -> molar change this step

        def _add(L, amt):
            delta[L] = delta.get(L, 0.0) + amt

        # SEED: 2 acetate -> C4 (first condensation), rate limited by the feed.
        if has_feed:
            _add(4, k_seed * acetate * interval)

        # ELONGATION: C_L + acetate -> C_{L+2}, first-order in the pool, gated by feed.
        if has_feed:
            for L, amt in list(self._pool.items()):
                if L + 2 <= max_len and amt > 0.0:
                    ext = k_ext * amt * interval
                    _add(L, -ext)
                    _add(L + 2, ext)

        # DEGRADATION: C_L -> C_{L-2} + acetate (loss); C4 -> back to acetate (full loss).
        for L, amt in list(self._pool.items()):
            if amt <= 0.0:
                continue
            deg = k_deg * amt * interval
            _add(L, -deg)
            if L - 2 >= 4:
                _add(L - 2, deg)
            self._cum_degrade += deg  # carbon leaving the amphiphile pool

        # Apply deltas (clamp >= 0).
        for L, d in delta.items():
            self._pool[L] = max(0.0, self._pool.get(L, 0.0) + d)

        total = sum(self._pool.values())
        if total > 0.0:
            mean_len = sum(L * a for L, a in self._pool.items()) / total
            long_pool = sum(a for L, a in self._pool.items() if L >= self.config["long_chain_min"])
            long_frac = long_pool / total
        else:
            mean_len = 0.0
            long_pool = 0.0
            long_frac = 0.0

        cac = max(self.config["cac_molar"], 1e-12)
        # Clear-margin: long-chain concentration in units of its CAC. >= 1 means the
        # composition clears the critical aggregation concentration (competent to
        # assemble); < 1 means it stays sub-CAC (no membrane). Unclamped so the
        # margin is comparable across feeds.
        aggregation_competent = long_pool / cac

        return {
            "mean_chain_length": mean_len,
            "amphiphile_total": total,
            "long_chain_fraction": long_frac,
            "aggregation_competent": aggregation_competent,
            "degradation_loss": self._cum_degrade,
        }
