"""og-04-alt — the endogenous boundary: a protocell boundary built from the
campaign's OWN chemistry (Phase 5).

Continuous carbon chemistry (acetate + formate, the carbon_fixation products)
feeds :class:`AmphiphileSynthesisProcess`; when the endogenous amphiphile clears
the critical aggregation concentration AND a viable boundary forms (the
``boundary`` face class), :class:`BoundaryFormationStep` performs an ``_add``
structural rewrite — a new individual appears in the ``agents`` map, its matter
seeded from the localized pool. With synthesis ablated (``k_synth = 0``) the
amphiphile never clears cac and NO individual forms: the discriminating control
for the ``boundary-forms-from-chemistry`` gate. A :class:`RewriteLedgerProcess`
audits that the ``_add`` conserves matter (``rewrite_ok``).
"""
from __future__ import annotations

from viva_superpowers.composite_generator import composite_generator

from ..core import build_core
from .. import models

_EMIT_PATHS = [
    "molecules/dissolved/amphiphile", "molecules/dissolved/acetate", "molecules/dissolved/formate",
    "diag/boundary_formed", "diag/viable_compartments",
    "ledger/n_agents", "ledger/agent_matter", "ledger/rewrite_residual_max",
    "ledger/partition_residual_max", "ledger/rewrite_ok",
    "global_time",
]
_EMIT_TYPES = {
    "amphiphile": "float", "acetate": "float", "formate": "float",
    "boundary_formed": "float", "viable_compartments": "float",
    "n_agents": "float", "agent_matter": "float", "rewrite_residual_max": "float",
    "partition_residual_max": "float", "rewrite_ok": "float", "global_time": "float",
}


@composite_generator(
    name="endogenous_boundary",
    methods=["amphiphile synthesis from acetate+formate", "boundary face (vesicle self-assembly)",
             "_add structural rewrite on agents map", "rewrite conservation ledger"],
    fidelity="reproduction",
    description=(
        "og-04-alt: a protocell boundary formed from the campaign's OWN chemistry. "
        "Acetate + formate condense to an amphiphile (AmphiphileSynthesisProcess); when "
        "it clears the critical aggregation concentration and the boundary face class "
        "(model_boundary: single_chain | mixed | thioester_aminothiol) reports a viable "
        "vesicle, a BoundaryFormationStep does an _add structural rewrite and a new "
        "individual appears in the agents map, matter seeded from the localized pool. "
        "Synthesis-ablated (k_synth=0) is the control: no amphiphile, no individual. A "
        "RewriteLedgerProcess audits that the _add conserves matter (rewrite_ok)."
    ),
    parameters={
        **models.model_parameters("boundary", defaults={"boundary": "mixed"}),
        "k_synth": {"type": "number", "default": 5.0e-2,
                    "description": "Amphiphile condensation rate (0 = synthesis-ablated control) [vg-data: hypothetical]"},
        "acetate0": {"type": "number", "default": 5.0e-2, "description": "Initial dissolved acetate (M)"},
        "formate0": {"type": "number", "default": 5.0e-2, "description": "Initial dissolved formate (M)"},
        "pH": {"type": "number", "default": 9.0, "description": "Vent-fluid pH (alkaline, vesicle-favourable)"},
        "ionic_strength": {"type": "number", "default": 0.35, "description": "Ionic strength (M, seawater)"},
        "temperature": {"type": "number", "default": 333.15, "description": "Temperature (K)"},
        "cac": {"type": "number", "default": 1.0e-3, "description": "Critical aggregation concentration (M) [vg-data: measured]"},
        "localized_formate": {"type": "number", "default": 4.0, "description": "Localized formate parcel seeding the individual (mol)"},
        "localized_acetate": {"type": "number", "default": 2.0, "description": "Localized acetate parcel (mol)"},
    },
    default_n_steps=40,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def endogenous_boundary(core=None, *, model_boundary="mixed", k_synth=5.0e-2,
                        acetate0=5.0e-2, formate0=5.0e-2, pH=9.0, ionic_strength=0.35,
                        temperature=333.15, cac=1.0e-3,
                        localized_formate=4.0, localized_acetate=2.0):
    if core is None:
        core = build_core()
    boundary_addr = models.resolve_checked(core, "boundary", model_boundary)
    mix_fraction = 0.0 if model_boundary == "single_chain" else 0.4

    return {
        "molecules": {"dissolved": {"amphiphile": 0.0, "acetate": float(acetate0),
                                    "formate": float(formate0)}},
        "env": {"pH": float(pH), "ionic_strength": float(ionic_strength),
                "temperature": float(temperature), "mix_fraction": float(mix_fraction)},
        "localized": {"formate": float(localized_formate), "acetate": float(localized_acetate)},
        "agents": {},
        "diag": {"boundary_formed": 0.0, "viable_compartments": 0, "pr": 0.0, "rm": 0.0},
        # acetate + formate -> amphiphile (endogenous; k_synth=0 ablates it)
        "synth": {
            "_type": "process", "address": "local:AmphiphileSynthesisProcess",
            "config": {"k_synth": float(k_synth)},
            "inputs": {"acetate": ["molecules", "dissolved", "acetate"],
                       "formate": ["molecules", "dissolved", "formate"]},
            "outputs": {"amphiphile": ["molecules", "dissolved", "amphiphile"],
                        "acetate": ["molecules", "dissolved", "acetate"],
                        "formate": ["molecules", "dissolved", "formate"]},
        },
        # the boundary face class -> viable_compartments
        "boundary": {
            "_type": "process", "address": boundary_addr,
            "config": {"mix_fraction": float(mix_fraction)},
            "inputs": {"pH": ["env", "pH"], "ionic_strength": ["env", "ionic_strength"],
                       "temperature": ["env", "temperature"], "mix_fraction": ["env", "mix_fraction"],
                       "amphiphile": ["molecules", "dissolved", "amphiphile"]},
            "outputs": {"viable_compartments": ["diag", "viable_compartments"]},
        },
        # amphiphile over cac + viable boundary -> _add an individual
        "form": {
            "_type": "step", "address": "local:BoundaryFormationStep",
            "config": {"cac": float(cac)},
            "inputs": {"amphiphile": ["molecules", "dissolved", "amphiphile"],
                       "viable_compartments": ["diag", "viable_compartments"],
                       "localized": ["localized"], "agents": ["agents"]},
            "outputs": {"agents": ["agents"], "boundary_formed": ["diag", "boundary_formed"],
                        "localized": ["localized"]},
        },
        # conservation audit of the structural rewrite
        "rewrite_ledger": {
            "_type": "process", "address": "local:RewriteLedgerProcess", "config": {},
            "inputs": {"agents": ["agents"], "localized": ["localized"],
                       "partition_residual": ["diag", "pr"], "removed_matter": ["diag", "rm"]},
            "outputs": {"rewrite_residual": ["ledger", "rewrite_residual"],
                        "rewrite_residual_max": ["ledger", "rewrite_residual_max"],
                        "partition_residual_max": ["ledger", "partition_residual_max"],
                        "agent_matter": ["ledger", "agent_matter"],
                        "n_agents": ["ledger", "n_agents"],
                        "rewrite_ok": ["ledger", "rewrite_ok"]},
        },
        "ledger": {"rewrite_residual": 0.0, "rewrite_residual_max": 0.0,
                   "partition_residual_max": 0.0, "agent_matter": 0.0, "n_agents": 0.0,
                   "rewrite_ok": 1.0},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": dict(_EMIT_TYPES)},
            "inputs": {
                "amphiphile": ["molecules", "dissolved", "amphiphile"],
                "acetate": ["molecules", "dissolved", "acetate"],
                "formate": ["molecules", "dissolved", "formate"],
                "boundary_formed": ["diag", "boundary_formed"],
                "viable_compartments": ["diag", "viable_compartments"],
                "n_agents": ["ledger", "n_agents"], "agent_matter": ["ledger", "agent_matter"],
                "rewrite_residual_max": ["ledger", "rewrite_residual_max"],
                "partition_residual_max": ["ledger", "partition_residual_max"],
                "rewrite_ok": ["ledger", "rewrite_ok"],
                "global_time": ["global_time"],
            },
        },
    }
