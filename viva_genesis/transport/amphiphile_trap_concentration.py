"""Concentrate the amphiphile pool at the thermophoretic trap.

The reciprocal-maintenance refutation (og-self-maintaining-individual) found the
chemistry's amphiphile pool sits 4-7 orders below its critical aggregation
concentration, so no membrane forms endogenously and the chemistry<->boundary loop
cannot close. But that loop was solved WITHOUT the one supported mechanism that
could supply those orders: the vent pore's thermophoretic (Baaske) trap that
og-spatial-concentration establishes. The long-chain fatty acids the chemistry
makes are among the most strongly trapped species — large Soret coefficient, and
self-associating, which Baaske et al. (2007) showed sharply enhances accumulation —
so a serpentinite pore concentrates them at its base, exactly where a membrane
would assemble.

This adapter applies a ``ThermophoreticTrapProcess`` ``enrichment_factor`` to the
amphiphile pool the chemistry produces, so aggregation competence is re-judged on
the pore-concentrated pool — the direct test of whether spatial concentration
closes the self-maintenance gap. It is CONSERVATIVE: the factor is applied once, to
the synthesised pool, not compounded through the (nonlinear) synthesis. A
``concentrating`` flag off forces the factor to 1.0 — the matched non-concentrating
control (the no-built-in-gain witness: the loop may use the pore's concentration,
never an assumed membrane).
"""
from __future__ import annotations

from process_bigraph import Process

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOLAR = {"_type": "float", "_units": "molar"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}


class AmphiphileTrapConcentrationProcess(Process):
    """Apply a thermophoretic trap's enrichment to the amphiphile pool -> the
    pore-local aggregation competence (the pool re-evaluated at the trap base)."""

    config_schema = {
        # The matched non-concentrating control: ignore the trap, pool stays at
        # its well-mixed value (enrichment forced to 1).
        "concentrating": {"_type": "boolean", "_default": True},
        # Physical ceiling so a runaway solved enrichment can't produce an
        # unphysical pool (Baaske's optical maximum is ~10^8-10^9).
        "max_enrichment": {"_type": "float", "_default": 1.0e9, "_units": "dimensionless"},
    }

    def inputs(self):
        return {
            "aggregation_competent": _DIMLESS,   # base (well-mixed) long-chain / CAC
            "amphiphile_total": _MOLAR,          # base amphiphile pool
            "enrichment_factor": _DIMLESS,       # from the thermophoretic trap
        }

    def outputs(self):
        return {
            "aggregation_competent_concentrated": _OW_DIMLESS,  # base * enrichment
            "amphiphile_total_concentrated": _OW_MOLAR,
            "effective_enrichment": _OW_DIMLESS,
        }

    def initial_state(self):
        return {"aggregation_competent": 0.0, "amphiphile_total": 0.0, "enrichment_factor": 1.0}

    def update(self, state, interval):
        base_ac = max(0.0, float(state.get("aggregation_competent", 0.0)))
        base_tot = max(0.0, float(state.get("amphiphile_total", 0.0)))
        raw = float(state.get("enrichment_factor", 1.0))
        if not self.config["concentrating"]:
            e = 1.0
        else:
            e = min(max(raw, 1.0), float(self.config["max_enrichment"]))
        return {
            "aggregation_competent_concentrated": base_ac * e,
            "amphiphile_total_concentrated": base_tot * e,
            "effective_enrichment": e,
        }
