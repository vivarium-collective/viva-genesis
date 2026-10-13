"""og-adv — adversarial control: run the real og-01/og-02/og-03 composites with
every vent feature removed (generic non-vent chemistry) and show the SAME gates
reject it where the vent passes.

This is the falsifiability test for the whole investigation: if the gates passed a
generic nonequilibrium system with no sustained H2, no Fe/Ni/S catalytic interface
and no pore concentration, they would be measuring generic chemistry, not the vent
mechanism. The vent features are already parameters on the real composites, so the
control is a parameterization of the SAME models — not a separate hand-tuned mock.
"""
from __future__ import annotations

import math

# Vent (favorable) vs generic (all vent features off) parameterizations of the three
# real composites. "generic" = no sustained H2 (reductant), no Fe/Ni/S catalyst, no
# pore concentration — a generic abiotic nonequilibrium mixture.
VENT_PARAMS = {
    "carbon": dict(gradient_efficiency=1.0, catalyst_active=1.0, h2=5.0e-3),
    "protometabolism": dict(feed_pyruvate=1.0e-4, feed_CO2=2.0e-3, k_rtca=800.0, k_wash=0.05),
    "thermophoretic": dict(flow_velocity=1.0e-4, porosity=0.3, pore_length=5.0e-3, delta_T=30.0),
}
GENERIC_PARAMS = {
    "carbon": dict(gradient_efficiency=0.0, catalyst_active=0.0, h2=1.0e-9),
    "protometabolism": dict(feed_pyruvate=1.0e-12, feed_CO2=1.0e-9, k_rtca=800.0, k_wash=0.05),
    "thermophoretic": dict(flow_velocity=1.0e-4, porosity=0.99, pore_length=5.0e-3, delta_T=30.0),
}

N_STEPS = 50


def _run(core, which, **params):
    from process_bigraph import Composite, gather_emitter_results
    if which == "carbon":
        from .composites.carbon_fixation import hydrothermal_carbon_fixation as gen
    elif which == "protometabolism":
        from .composites.protometabolism import protometabolic_network as gen
    elif which == "thermophoretic":
        from .composites.thermophoretic_concentration import thermophoretic_concentration as gen
    else:  # pragma: no cover
        raise ValueError(which)
    sim = Composite({"state": gen(core, **params)}, core=core)
    sim.run(float(N_STEPS))
    return gather_emitter_results(sim)[("emitter",)]


def _settled(vals, frac):
    if not vals:
        return 0.0
    k = max(1, int(len(vals) * frac))
    return sum(vals[-k:]) / k


# Each gate: (label, composite, native threshold, pass if value >= threshold, measure).
# Thresholds mirror the og-01/og-02/og-03 behavior-test bands (lower bounds that a
# productive vent clears). native units noted in the label.
def _gate_specs():
    return [
        ("og-01 formate (mM)", "carbon", 50.0,
         lambda rows: _settled([r.get("formate", 0.0) for r in rows], 0.1) * 1e3),
        ("og-01 net C-flux (mol/s)", "carbon", 1.0e-6,
         lambda rows: max((r.get("net_carbon_flux", 0.0) for r in rows), default=0.0)),
        ("og-02 throughput (mol/s)", "protometabolism", 1.0e-6,
         lambda rows: _settled([r.get("net_carbon_flux", 0.0) for r in rows], 0.2)),
        ("og-03 accumulation Péclet", "thermophoretic", 18.0,
         lambda rows: _settled([r.get("accumulation_peclet", 0.0) for r in rows], 0.2)),
        ("og-03 enrichment (fold)", "thermophoretic", 1.0e6,
         lambda rows: (rows[-1].get("enrichment_factor", 0.0) if rows else 0.0)),
    ]


def evaluate_gates(core):
    """Run every gate in VENT and GENERIC mode; return one row per gate with the
    measured value for each and the (shared) threshold. Each composite is run once
    per mode and reused across its gates."""
    specs = _gate_specs()
    cache = {}
    for mode, params in (("vent", VENT_PARAMS), ("generic", GENERIC_PARAMS)):
        for which in ("carbon", "protometabolism", "thermophoretic"):
            cache[(mode, which)] = _run(core, which, **params[which])
    rows = []
    for label, which, thr, measure in specs:
        rows.append({
            "label": label,
            "threshold": float(thr),
            "vent": float(measure(cache[("vent", which)])),
            "generic": float(measure(cache[("generic", which)])),
        })
    return rows


def adversarial_verdict(core):
    """Grade the control: PASS when EVERY gate REJECTS the generic system (value <
    threshold) AND PASSES the vent (value >= threshold). Returns the gate rows plus
    boolean summaries."""
    rows = evaluate_gates(core)
    generic_rejected = all(g["generic"] < g["threshold"] for g in rows)
    vent_passes = all(g["vent"] >= g["threshold"] for g in rows)
    # worst-case margin (decades) by which the control is rejected across gates.
    min_reject_decades = min(
        math.log10(g["threshold"] / max(g["generic"], 1e-300)) for g in rows)
    return {
        "gate_rows": rows,
        "generic_rejected": generic_rejected,
        "vent_passes": vent_passes,
        "n_gates": len(rows),
        "min_reject_decades": float(min_reject_decades),
    }
