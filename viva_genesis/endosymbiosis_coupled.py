"""Coupled contact<->enclosure process for the proto_endosymbiosis bridge (M3).

Measures ``joint_feasibility_region`` — whether selection-for-contact (M1) and stable
enclosure (M2) can co-succeed in the SAME regime, which is the heart of the reopening
question ("which combinations of mechanisms actually work"). The two mechanisms are
COUPLED, not run side by side:

  * contact provides the adhesion that enclosure needs: only high-contact lineages have
    enough adhesion to seal (low-contact lineages cannot enclose);
  * enclosure reinforces contact: a sealed lineage locks in a stable internalised exchange
    benefit, so it stays high-contact (does not revert) and raises the frequency-dependent
    benefit for the rest.

So the jointly-feasible fraction is EMERGENT from the coupling, not imposed: it is positive
only where contact is selected AND that contact seals AND the seal persists. It can be ~0
in three distinct ways — contact never invades (benefit<cost / sub-threshold), contact
invades but cannot seal (adhesion<bending barrier), or seals but unwraps (perturbation
dominates) — each a real failure mode of the transition.

Inferential scope: reduced three-compartment coupled model (low-contact ⇄ high-contact-
unsealed ⇄ high-contact-sealed). Establishes whether a self-reinforcing contact+enclosure
regime EXISTS; does not resolve the spatial membrane PDE or full energetics (M4).
"""
from __future__ import annotations

import math

from process_bigraph import Process


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 50.0), -50.0)))


class CoupledTransitionProcess(Process):
    """Three-compartment coupled transition: lc <-> hc_un <-> hc_se.

    lc = low-contact (cannot seal); hc_un = high-contact, not yet sealed; hc_se =
    high-contact AND stably sealed (= jointly feasible). Contact selection (lc<->hc_un) is
    a frequency-dependent replicator on net benefit minus adhesion cost; enclosure
    (hc_un<->hc_se) is adhesion vs bending barrier vs perturbation; sealed lineages are
    locked high-contact (the reinforcing feedback).
    """

    config_schema = {
        "benefit_coeff": {"_type": "float", "_default": 1.2},   # max freq-dependent exchange benefit
        "cost_coeff": {"_type": "float", "_default": 0.3},      # adhesion cost
        "base_adhesion": {"_type": "float", "_default": 0.8},   # adhesion of a high-contact lineage
        "bending_modulus": {"_type": "float", "_default": 0.2}, # enclosure neck-closure barrier
        "perturbation": {"_type": "float", "_default": 0.1},    # unwrapping stress
        "seal_rate": {"_type": "float", "_default": 0.3},
        "unwrap_rate": {"_type": "float", "_default": 0.3},
        "retry_rate": {"_type": "float", "_default": 0.05},     # stalled -> unsealed (slow)
        "selection_strength": {"_type": "float", "_default": 1.0},
        "sharpness": {"_type": "float", "_default": 10.0},      # steep barrier: sub-barrier adhesion ⇒ sealing is rare
    }

    def inputs(self):
        return {"n_lc": "float", "n_hc_un": "float", "n_hc_se": "float", "n_hc_st": "float"}

    def outputs(self):
        return {"n_lc": "float", "n_hc_un": "float", "n_hc_se": "float", "n_hc_st": "float"}

    def update(self, state, interval):
        c = self.config
        lc = max(float(state.get("n_lc", 0.0) or 0.0), 0.0)
        hc_un = max(float(state.get("n_hc_un", 0.0) or 0.0), 0.0)
        hc_se = max(float(state.get("n_hc_se", 0.0) or 0.0), 0.0)
        hc_st = max(float(state.get("n_hc_st", 0.0) or 0.0), 0.0)
        N = lc + hc_un + hc_se + hc_st
        if N <= 0:
            return {"n_lc": 0.0, "n_hc_un": 0.0, "n_hc_se": 0.0, "n_hc_st": 0.0}
        dt = float(interval)
        k = float(c["sharpness"])
        hc = hc_un + hc_se + hc_st
        freq_high = hc / N
        realized_benefit = float(c["benefit_coeff"]) * freq_high        # frequency-dependent
        s = float(c["selection_strength"]) * (realized_benefit - float(c["cost_coeff"]))
        # contact selection among unsealed (sealed hc are locked in by the exchange bonus)
        sel_gain = max(s, 0.0) * lc * (hc / N) * dt                     # lc -> hc_un (needs partners)
        sel_lose = max(-s, 0.0) * hc_un * dt                           # hc_un -> lc
        # enclosure: only high-contact lineages have the adhesion to seal; unwrapped
        # attempts fall into a stalled state and only slowly retry (persistence barrier)
        p_seal = _sigmoid(k * (float(c["base_adhesion"]) - float(c["bending_modulus"])))
        p_unwrap = _sigmoid(k * (float(c["perturbation"]) - float(c["base_adhesion"])))
        seal = float(c["seal_rate"]) * p_seal * hc_un * dt             # hc_un -> hc_se
        unwrap = float(c["unwrap_rate"]) * p_unwrap * hc_se * dt        # hc_se -> hc_st (stalled)
        retry = float(c["retry_rate"]) * hc_st * dt                     # hc_st -> hc_un
        return {
            "n_lc": -sel_gain + sel_lose,
            "n_hc_un": sel_gain - sel_lose - seal + retry,
            "n_hc_se": seal - unwrap,
            "n_hc_st": unwrap - retry,
        }
