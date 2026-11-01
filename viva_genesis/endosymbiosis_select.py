"""Processes for the proto_endosymbiosis_hybrid coupled model (M1).

Lives at top level (not under composites/) so register_workspace_processes scans it
and `local:ContactSelectionProcess` resolves in the detached run subprocess too.
"""
from __future__ import annotations

import math

from process_bigraph import Process


class ContactSelectionProcess(Process):
    """Frequency-dependent energetic replicator on a heritable contact propensity.

    State is the two phenotype abundances ``n_high`` / ``n_low`` (evolved additively by
    the replicator delta each tick = one generation). A contact-seeker realises exchange
    only in proportion to partner availability (the current frequency of the high-contact
    type), earning an energetic benefit; every phenotype always pays an energetic adhesion
    cost proportional to its contact propensity. Net fitness drives a normalised replicator
    step (population size ~ conserved). Derived quantities (frequency, selection coefficient)
    are computed by the observables from the abundance trajectory.
    """

    config_schema = {
        "benefit_coeff": {"_type": "float", "_default": 0.6},   # max energetic benefit / unit realised contact
        "cost_coeff": {"_type": "float", "_default": 0.3},      # energetic adhesion cost / unit contact propensity
        "exchange": {"_type": "string", "_default": "on"},     # "on" = exchange available; "off" = no-exchange control
        "selection_strength": {"_type": "float", "_default": 1.0},
        "cp_high": {"_type": "float", "_default": 1.0},         # contact propensity of the high phenotype
        "cp_low": {"_type": "float", "_default": 0.0},          # contact propensity of the low phenotype
    }

    def inputs(self):
        return {"n_high": "float", "n_low": "float"}

    def outputs(self):
        return {"n_high": "float", "n_low": "float"}

    def update(self, state, interval):
        c = self.config
        nh = max(float(state.get("n_high", 0.0) or 0.0), 0.0)
        nl = max(float(state.get("n_low", 0.0) or 0.0), 0.0)
        N = nh + nl
        if N <= 0.0:
            return {}
        fh = nh / N  # frequency of contact-seekers = partner availability
        cp_h, cp_l = float(c["cp_high"]), float(c["cp_low"])
        ex = 1.0 if str(c["exchange"]) == "on" else 0.0
        b, k = float(c["benefit_coeff"]), float(c["cost_coeff"])
        # frequency-dependent benefit: realised contact ∝ own propensity × partner availability
        fit_h = max(1.0 + ex * b * cp_h * fh - k * cp_h, 1e-9)
        fit_l = max(1.0 + ex * b * cp_l * fh - k * cp_l, 1e-9)
        mean_fit = (nh * fit_h + nl * fit_l) / N
        s = float(c["selection_strength"]) * float(interval)

        def step(n, fit):
            target = n * (fit / mean_fit)  # normalised replicator → N conserved
            return max(n + s * (target - n), 0.0)

        return {"n_high": step(nh, fit_h) - nh, "n_low": step(nl, fit_l) - nl}

