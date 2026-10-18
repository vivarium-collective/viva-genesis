"""Study 31 (partial Gate C) — does an endogenous membrane PAY FOR ITSELF?

og-31's Martini-MD composite shows the metabolism's amphiphiles COHERE into a
bilayer (the "makes a membrane" half). This composite tests the other half — does
compartmenting the network BENEFIT it? — against a no-endogenous-membrane
ablation, the Gate C criterion.

**Honest framing (baked in):** the "metabolism" here is the sustained,
carbon-fixing A1 network — it is NOT autocatalytic (Gate A's A2 was refuted for
both routes). So this asks whether a *persisting* (not self-amplifying) network
can make a membrane that pays for itself, never implying autocatalysis.

**REDUCED coupling (labelled — NOT the real MD-resolved permeability).** The real
membrane<->metabolite-pool coupling (MD-resolved PMF for charged intermediates)
is the study-32 / viva-md-membrane follow-on = full Gate C. Here the membrane is
a reduced retention/access model on the Gate-B pore-concentrated network: it
- RETAINS metabolites -> reduces effective washout, k_wash_eff = k_wash*(1-retention)
- has finite ACCESS (permeability) -> reduces effective feed crossing, feed_eff = feed*access
The retention/access defaults are the Jordan-2019-calibrated
``ProtocellAssemblyProcess`` values at vent conditions (retention ~0.905, access
~0.997) — grounded, not tuned. ``membrane=False`` is the matched ABLATION
(retention 0, access 1: full washout, full feed crossing), at the same external
feed. Membrane benefit = net carbon flux / persistence(membrane) > (ablation):
the retention gain exceeds the access cost. Sweeping ``access`` down locates the
failure boundary where a too-tight membrane starves the network (benefit
inverts) — so the result is a WINDOW, not a single favorable point.

Reuses :func:`og_30_spatially_integrated_protometabolism` for the pore + real
libRoadRunner reaction universe; the membrane enters as effective-feed x access
and effective-washout x (1 - retention).
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .og_30_spatially_integrated_protometabolism import og_30_spatially_integrated_protometabolism

# Jordan-2019-calibrated ProtocellAssemblyProcess values at vent conditions
# (pH 9, ionic 0.35 M, T 318 K, mix 0.4): retention 0.905, access 0.997.
_VENT_RETENTION, _VENT_ACCESS = 0.905, 0.997


@composite_generator(
    name="og_31_membrane_benefit",
    methods=["reduced membrane retention/access coupling", "Gate-B pore-concentrated reaction universe",
             "matched no-endogenous-membrane ablation"],
    fidelity="real",
    description=(
        "Partial Gate C: does an endogenous membrane pay for itself? Puts the sustained (A1, NOT "
        "autocatalytic) carbon-fixing network in the Gate-B concentrating pore and adds a REDUCED "
        "membrane coupling - retention reduces effective washout (k_wash*(1-retention)), finite access "
        "reduces effective feed crossing (feed*access) - with Jordan-2019-calibrated vent retention/access "
        "(0.905/0.997, grounded not tuned). membrane=False is the matched ablation (retention 0, access 1). "
        "Benefit = net carbon flux / persistence(membrane) > (ablation). NOT the MD-resolved PMF coupling "
        "(that is study 32 / viva-md-membrane = full Gate C)."
    ),
    parameters={
        "membrane": {"type": "boolean", "default": True,
                     "description": "Endogenous membrane (True) vs matched no-membrane ablation (False)"},
        "retention": {"type": "float", "default": _VENT_RETENTION,
                      "description": "Fraction of metabolites the membrane retains [Jordan-2019 vent value]"},
        "access": {"type": "float", "default": _VENT_ACCESS,
                   "description": "Membrane feed access/permeability in [0,1]; lower = tighter = starves feed"},
        "base_CO2": {"type": "float", "default": 1.0e-3, "description": "Bulk precursor CO2 (molar)"},
        "base_H2": {"type": "float", "default": 1.0e-3, "description": "Bulk precursor H2 (molar)"},
        "porosity": {"type": "float", "default": 0.88, "description": "Gate-B pore porosity (0.88 = demo pore)"},
        "k_wash": {"type": "float", "default": 0.05, "description": "Base CSTR washout (1/s) before retention"},
        "max_carbons": {"type": "integer", "default": 4, "description": "Carbon cap of the reaction universe"},
    },
    default_n_steps=90,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["flux/net_carbon_flux", "net/total_organic_carbon",
                         "stats/n_persistent_species", "flux/network_connected"]}],
)
def og_31_membrane_benefit(core=None, *, membrane=True, retention=_VENT_RETENTION, access=_VENT_ACCESS,
                           base_CO2=1.0e-3, base_H2=1.0e-3, porosity=0.88, k_wash=0.05, max_carbons=4):
    if core is None:
        core = build_core()
    # Ablation: no endogenous membrane -> full feed crossing, full washout.
    r = float(retention) if membrane else 0.0
    a = float(access) if membrane else 1.0
    # Membrane as reduced modifiers on the Gate-B pore-concentrated network:
    #   effective feed crossing  = feed * access   (applied to the bulk base feed;
    #     the pore enrichment is multiplicative, so base*access*enrichment = enriched*access)
    #   effective washout        = k_wash * (1 - retention)
    eff_base_CO2 = float(base_CO2) * a
    eff_base_H2 = float(base_H2) * a
    eff_k_wash = float(k_wash) * (1.0 - r)
    return og_30_spatially_integrated_protometabolism(
        core, concentrating=True, base_CO2=eff_base_CO2, base_H2=eff_base_H2,
        porosity=float(porosity), k_wash=eff_k_wash, max_carbons=int(max_carbons))
