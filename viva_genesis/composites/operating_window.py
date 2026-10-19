"""NEW B — og-operating-window: the honest rescue test for A's thin precursor pool.

A (og-precursor-pool, QUALIFIED) showed the functional C2-C3 precursor pool is
thermodynamically bounded to ~nM within the defensible DIC window. B asks whether
the downstream concentration/retention machinery can RESCUE that: propagate A's
real pool through the REAL pore (thermophoretic Soret trap, genuine FiPy) and the
REAL membrane (ProtocellAssembly retention/access), and find whether any
defensible operating window lifts the functional pool to a consumable (~uM)
concentration.

This composite couples the two real levers onto A's genuine reactor:
- **Membrane retention** reduces the effective washout (``k_wash*(1-retention)``,
  the og_31 convention) using retention from the real ``ProtocellAssemblyProcess``
  (Jordan-2019 calibrated) — raising the steady-state pool.
- **Pore enrichment** is the real FiPy ``ThermophoreticTrapProcess`` enrichment
  factor at the cell's thermal gradient and Soret coefficient. The downstream
  analysis multiplies the (retained) functional pool by this factor
  (product-pool enrichment) and asks if it reaches ~uM.

The pivotal honest input is the Soret coefficient of the SMALL C2-C3 precursors:
the trap's 0.10/K default is the LARGE-biomolecule value (Baaske's 10^8). Small
precursors thermophorese far more weakly, so ``soret_coeff`` is SWEPT as the
pivotal uncertain parameter (see the og-operating-window study + sims/run.py),
never pinned at the large-molecule default that would falsely rescue the pool.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from ..membranes.protocell_assembly import ProtocellAssemblyProcess

# Base CSTR washout before membrane retention (1/s), A's convention.
_K_WASH = 0.05
# Jordan-2019-calibrated vent membrane knobs (the real, grounded operating point).
_VENT_MIX = 0.4
_VENT_PERM0 = 5.0e-4


def membrane_retention(core, *, mix_fraction=_VENT_MIX, perm_prefactor=_VENT_PERM0):
    """Retention / access / viability from the REAL ProtocellAssembly model (not an
    invented factor). Returns (retention, access, viable)."""
    mp = ProtocellAssemblyProcess(
        config={"mix_fraction": float(mix_fraction), "perm_prefactor": float(perm_prefactor)},
        core=core)
    st = mp.initial_state() if hasattr(mp, "initial_state") else {}
    last = {}
    for _ in range(3):
        last = mp.update(st, 1.0)
    return (float(last.get("retention", 0.0)), float(last.get("access", 0.0)),
            float(last.get("individuality_access", 0.0)))


_OBS = ("functional_pool_carbon", "pool_cofixed_fraction", "total_organic_carbon")
_EMIT = {"functional_pool_carbon": "float", "enrichment_factor": "float",
         "retention": "float", "access": "float", "individuality_access": "float",
         "global_time": "float"}


@composite_generator(
    name="og_operating_window",
    methods=["libRoadRunner precursor-pool reactor", "FiPy thermophoretic Soret trap",
             "ProtocellAssembly membrane retention/access"],
    fidelity="real",
    description=(
        "NEW B: A's real precursor-pool reactor (membrane-reduced washout from the "
        "real ProtocellAssembly retention) coupled to the real FiPy thermophoretic "
        "trap (enrichment at the cell's thermal gradient + Soret coefficient). The "
        "sweep asks whether product-pool enrichment x membrane retention lifts the "
        "nM functional pool to a consumable ~uM concentration. soret_coeff is the "
        "pivotal swept parameter (small-molecule, NOT the large-biomolecule default)."
    ),
    parameters={
        "feed_CO2": {"type": "float", "default": 2.0e-3,
                     "description": "Inorganic-carbon feed (M), og-vent-interface DIC window 2-20 mM"},
        "delta_T": {"type": "float", "default": 30.0,
                    "description": "Thermal gradient across the pore (K) driving the Soret trap"},
        "soret_coeff": {"type": "float", "default": 5.0e-3,
                        "description": "Small-molecule Soret coeff (1/K) — SWEPT; default is a mid small-molecule value, NOT the 0.10 large-biomolecule value"},
        "membrane": {"type": "boolean", "default": True,
                     "description": "Real membrane retention on (True) vs transport-decoupled null (False, retention 0)"},
        "mix_fraction": {"type": "float", "default": _VENT_MIX,
                         "description": "Co-surfactant fraction for the ProtocellAssembly membrane"},
        "flow_velocity": {"type": "float", "default": 1.0e-4,
                          "description": "Convective flow through the pore (m/s); 0 = no-trap control"},
        "porosity": {"type": "float", "default": 0.3,
                     "description": "Pore openness (0-1)"},
    },
    default_n_steps=240,
    preferred_time="24 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["obs/functional_pool_carbon", "trap/enrichment_factor",
                         "mem/retention", "mem/access", "global_time"]}],
)
def og_operating_window(core=None, *, feed_CO2=2.0e-3, delta_T=30.0, soret_coeff=5.0e-3,
                        membrane=True, mix_fraction=_VENT_MIX, flow_velocity=1.0e-4,
                        porosity=0.3):
    if core is None:
        core = build_core()

    # Real membrane retention/access -> effective washout on A's reactor.
    if membrane:
        retention, access, indiv = membrane_retention(core, mix_fraction=mix_fraction)
    else:
        retention, access, indiv = 0.0, 1.0, 0.0  # transport-decoupled null
    k_wash_eff = _K_WASH * (1.0 - retention)

    doc = {
        "reactor": {
            "_type": "process",
            "address": "local:PrecursorPoolProcess",
            "config": {"max_carbons": 3, "thermo_source": "package",
                       "ammonium_availability": 1.3e-4, "k_wash": k_wash_eff},
            "interval": 1.0,
            "inputs": {k: ["feed", k] for k in
                       ("feed_CO2", "feed_H2", "feed_pyruvate", "feed_formaldehyde",
                        "feed_formate", "feed_acetate")},
            "outputs": {p: ["obs", p] for p in _OBS},
        },
        "trap_process": {
            "_type": "process",
            "address": "local:ThermophoreticTrapProcess",
            "config": {"delta_T": float(delta_T), "soret_coeff": float(soret_coeff)},
            "interval": 1.0,
            "inputs": {"temperature": ["env", "temperature"],
                       "flow_velocity": ["env", "flow_velocity"],
                       "porosity": ["env", "porosity"]},
            "outputs": {"enrichment_factor": ["trap", "enrichment_factor"],
                        "residence_time": ["trap", "residence_time"],
                        "accumulation_peclet": ["trap", "accumulation_peclet"]},
        },
        "feed": {"feed_CO2": float(feed_CO2), "feed_H2": 1.08e-2, "feed_pyruvate": 0.0,
                 "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0},
        "obs": {p: 0.0 for p in _OBS},
        "trap": {"enrichment_factor": 1.0, "residence_time": 0.0, "accumulation_peclet": 0.0},
        "env": {"temperature": 333.15, "flow_velocity": float(flow_velocity),
                "porosity": float(porosity)},
        "mem": {"retention": retention, "access": access, "individuality_access": indiv},
        "emitter": {
            "_type": "step",
            "address": "local:RAMEmitter",
            "config": {"emit": _EMIT},
            "inputs": {
                "functional_pool_carbon": ["obs", "functional_pool_carbon"],
                "enrichment_factor": ["trap", "enrichment_factor"],
                "retention": ["mem", "retention"],
                "access": ["mem", "access"],
                "individuality_access": ["mem", "individuality_access"],
                "global_time": ["global_time"],
            },
        },
    }
    return doc
