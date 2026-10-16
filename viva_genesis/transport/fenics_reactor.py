"""Reduced thermophoretic-trap surrogate for the ``spatial_transport`` face.

The two **real dolfinx FEM** classes that used to live here —
``FenicsReactiveTransportProcess`` and ``FenicsThermophoreticTrapProcess`` —
now ship from the imported ``viva-fenics`` package
(``viva_fenics.FenicsReactiveTransportProcess`` /
``...FenicsThermophoreticTrapProcess``, backed by
``viva_fenics.fem.advection_diffusion_step``). ``viva_genesis.core.build_core``
registers them under their ``local:`` addresses, so composites and
``models.resolve`` / ``assert_face`` are unchanged; only *running* the FEM arm
needs viva-fenics's conda-only pixi env.

What remains here is the pure-Python reduced surrogate
(``SurrogateThermophoreticTrapProcess``, plan 4.6): the closed-form
``enrichment = exp(beta * pore_length)`` that fills the Decision-map grid
cheaply while the full PDE runs only at the World-view points and an audit
subset. It needs no dolfinx and sits on the same ``spatial_transport`` face, so
its use stays *declared*, not hidden.
"""

from __future__ import annotations

import math

from process_bigraph import Process

_K = {"_type": "float", "_units": "kelvin"}
_MPS = {"_type": "float", "_units": "meter/second"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}


class SurrogateThermophoreticTrapProcess(Process):
    """Reduced surrogate for the thermophoretic trap (plan 4.6): the closed-form
    ``enrichment = exp(beta * pore_length)`` the FiPy trap documents, with no PDE
    solve -- for filling the Decision-map grid cheaply while the full PDE runs
    only at the World-view points and an audit subset. Same ports and physics
    constants as the trap classes, so it sits on the ``spatial_transport`` face
    and its use is *declared*, not hidden.
    """

    config_schema = {
        "pore_length": {"_type": "float", "_default": 5.0e-3, "_units": "meter"},
        "pore_width": {"_type": "float", "_default": 1.0e-4, "_units": "meter"},
        "delta_T": {"_type": "float", "_default": 30.0, "_units": "kelvin"},
        "soret_coeff": {"_type": "float", "_default": 0.10, "_units": "1/kelvin"},
        "solute_diffusivity": {"_type": "float", "_default": 1.0e-10, "_units": "meter**2/second"},
        "geom_constant": {"_type": "float", "_default": 1.75e-3, "_units": "dimensionless"},
    }

    def inputs(self):
        return {"temperature": _K, "flow_velocity": _MPS, "porosity": _DIMLESS}

    def outputs(self):
        return {
            "enrichment_factor": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "residence_time": {"_type": "overwrite[float]", "_units": "second"},
            "accumulation_peclet": {"_type": "overwrite[float]", "_units": "dimensionless"},
            "flux_divergence_residual": {"_type": "overwrite[float]", "_units": "dimensionless"},
        }

    def initial_state(self):
        return {"temperature": 333.15, "flow_velocity": 1.0e-4, "porosity": 0.3}

    def update(self, state, interval):
        flow = max(float(state.get("flow_velocity", 0.0)), 0.0)
        porosity = min(max(float(state.get("porosity", 0.3)), 0.0), 1.0)
        D = float(self.config["solute_diffusivity"])
        w = max(float(self.config["pore_width"]), 1e-12)
        L = float(self.config["pore_length"])
        dT = max(float(self.config["delta_T"]), 0.0)
        soret = max(float(self.config["soret_coeff"]), 0.0)
        geom = max(float(self.config["geom_constant"]), 0.0)
        pe_conv = flow * w / D
        beta = geom * soret * dT * pe_conv / w * (1.0 - porosity)
        pe_acc = beta * L
        residence = L / flow if flow > 1e-12 else 1.0e12
        return {
            "enrichment_factor": math.exp(min(pe_acc, 45.0)),
            "residence_time": min(residence, 1.0e12),
            "accumulation_peclet": pe_acc,
            "flux_divergence_residual": 0.0,  # closed form: no discrete residual
        }
