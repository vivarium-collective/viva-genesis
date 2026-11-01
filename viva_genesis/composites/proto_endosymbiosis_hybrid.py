"""proto_endosymbiosis_hybrid — the coupled bridge model (M1: selection for contact).

The reopened eukaryogenesis bridge studies need DISCRIMINATING observables that the
reused per-study composites cannot produce. M1 is the first coupled increment: it
MEASURES ``selection_coefficient_for_adhesion`` — whether metabolic exchange selects
FOR a heritable contact/adhesion propensity, once the adhesion cost is paid — which
discriminates H1-syntrophy-first (selected under exchange) from H4-no-integration
(not selected after costs).

Modeling choices (authored + reviewed, not silent defaults):
  * adhesion cost is energetic, in the SAME units as the exchange benefit (net fitness
    = benefit - cost), so the comparison is honest rather than assumed;
  * contact SCALES exchange access continuously (no binary gate);
  * selection is an ENERGETIC replicator — fitness grounded in the net energy budget.

Selection is EMERGENT, not analytic: the exchange benefit is FREQUENCY-DEPENDENT (a
contact-seeker only realises exchange when partners are available, proportional to the
current frequency of contact-seekers), so a contact type can fail to invade from rare
even when benefit>cost, and the realised selection coefficient comes out positive,
zero, or negative depending on regime. This is a reduced coupled model — its inferential
scope: it establishes whether exchange CAN select for contact given a benefit/cost
balance and partner availability, NOT the spatial exchange PDE or the membrane mechanics
(the higher-fidelity increments M2+).

Inherited trait: contact_propensity. Two phenotypes (high/low). The no-exchange control
(exchange_on=0) leaves only the adhesion cost, so contact is selected against.
"""
from __future__ import annotations

import math

from process_bigraph import Process
from process_bigraph.composite_generator import composite_generator

from ..core import build_core


def _last(rows, key):
    return float(rows[-1].get(key, float("nan"))) if rows else float("nan")


def _series(rows, key):
    return [float(r.get(key, float("nan"))) for r in rows]


from ..endosymbiosis_select import ContactSelectionProcess  # registered via build_core


@composite_generator(
    name="proto_endosymbiosis_hybrid",
    description="Coupled bridge model M1: measures selection for a heritable contact "
                "propensity under frequency-dependent exchange benefit vs adhesion cost.",
)
def proto_endosymbiosis_hybrid(core=None, *, exchange="on", benefit_coeff=0.6, cost_coeff=0.3,
                               selection_strength=1.0, cp_high=1.0, cp_low=0.0,
                               n_initial=100.0, init_freq_high=0.3, seed=1):
    if core is None:
        core = build_core()
    # This process lives beside its generator (composites/), which the workspace
    # process scan does not cover — register it explicitly so local: resolves.
    if "ContactSelectionProcess" not in core.link_registry:
        core.register_link("ContactSelectionProcess", ContactSelectionProcess)
    n0, f0 = float(n_initial), float(init_freq_high)
    return {
        "selection": {
            "_type": "process", "address": "local:ContactSelectionProcess", "interval": 1.0,
            "config": {"benefit_coeff": float(benefit_coeff), "cost_coeff": float(cost_coeff),
                       "exchange": str(exchange), "selection_strength": float(selection_strength),
                       "cp_high": float(cp_high), "cp_low": float(cp_low)},
            "inputs": {"n_high": ["n_high"], "n_low": ["n_low"]},
            "outputs": {"n_high": ["n_high"], "n_low": ["n_low"]},
        },
        "n_high": n0 * f0, "n_low": n0 * (1.0 - f0),
    }


# ── observables (computed from the emitted abundance trajectory `rows`) ───────────
def selection_coefficient_for_adhesion(rows) -> float:
    """Realised per-generation selection differential on contact propensity: the mean
    change in logit(freq_high) per generation while both phenotypes are present. >0 ⇒
    exchange selects FOR contact (H1); ≤0 ⇒ contact selected against after cost / under
    the no-exchange control (H4)."""
    nh, nl = _series(rows, "n_high"), _series(rows, "n_low")
    logits = []
    for h, l in zip(nh, nl):
        N = h + l
        if N > 0 and h > 0 and l > 0:
            p = h / N
            if 0.0 < p < 1.0:
                logits.append(math.log(p / (1.0 - p)))
    if len(logits) < 2:
        # fixed/extinct before we could measure a slope — sign from the net move
        ff = final_freq_high(rows)
        f0 = (nh[0] / (nh[0] + nl[0])) if (nh and (nh[0] + nl[0]) > 0) else float("nan")
        if ff == ff and f0 == f0:
            return math.copysign(1.0, ff - f0) if ff != f0 else 0.0
        return float("nan")
    return (logits[-1] - logits[0]) / (len(logits) - 1)


def final_freq_high(rows) -> float:
    """Final frequency of the contact-seeking phenotype (invasion outcome)."""
    nh, nl = _last(rows, "n_high"), _last(rows, "n_low")
    N = nh + nl
    return nh / N if N > 0 else float("nan")
