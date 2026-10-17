"""Couple a thermophoretic trap's enrichment to a reaction network's feed.

Study 30 asks whether the full chemical network can operate IN A PORE despite
fractionation and washout. The real FiPy thermophoretic trap
(``ThermophoreticTrapProcess``) concentrates a dilute feed by an
``enrichment_factor``; this adapter scales the base precursor feed by that factor
and writes the pore-local concentrations the open chemical network consumes. A
``concentrating`` flag off forces the factor to 1.0 — the matched well-mixed /
nonconcentrating control the decision test compares against (productive flux in
the pore must EXCEED the control).
"""
from __future__ import annotations

from process_bigraph import Process

_MOLAR = {"_type": "float", "_units": "molar"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}


class PoreEnrichedFeedProcess(Process):
    """Scale a base precursor feed by the pore enrichment -> pore-local feed."""

    config_schema = {
        # Base (ocean/bulk) precursor concentrations before pore concentration.
        "base_CO2": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},
        "base_H2": {"_type": "float", "_default": 1.0e-3, "_units": "molar"},
        # The nonconcentrating control: ignore the trap, feed stays at base.
        "concentrating": {"_type": "boolean", "_default": True},
        # Cap so a runaway enrichment can't produce unphysical feeds.
        "max_enrichment": {"_type": "float", "_default": 1.0e6, "_units": "dimensionless"},
    }

    def inputs(self):
        return {"enrichment_factor": _DIMLESS}

    def outputs(self):
        # Pore-local feed (sensors — the current concentrated concentrations the
        # network reads) + the effective enrichment actually applied.
        return {"CO2": _OW_MOLAR, "H2": _OW_MOLAR, "effective_enrichment": _OW_DIMLESS}

    def initial_state(self):
        return {"enrichment_factor": 1.0}

    def update(self, state, interval):
        raw = float(state.get("enrichment_factor", 1.0))
        if not self.config["concentrating"]:
            e = 1.0                      # matched nonconcentrating control
        else:
            # Enrichment concentrates (>=1); clamp to a physical ceiling.
            e = min(max(raw, 1.0), float(self.config["max_enrichment"]))
        return {
            "CO2": float(self.config["base_CO2"]) * e,
            "H2": float(self.config["base_H2"]) * e,
            "effective_enrichment": e,
        }
