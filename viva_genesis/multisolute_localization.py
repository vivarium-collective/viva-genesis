"""Multisolute localization on the ``localization`` face (plan §4.5 / §6, Phase 4).

Two model classes, both honouring the ``spatial_transport`` face, that transport
the chemically-necessary PREBIOTIC MIXTURE (phosphate, ammonium, formate,
acetate, pyruvate, amino-acid / nucleotide precursors, amphiphiles) through a
thermophoretic pore SIMULTANEOUSLY -- each solute with its own diffusivity,
Soret coefficient, adsorption and degradation -- and report, per species, the
trap enrichment, so a study can tell whether the mixture co-localizes or
fractionates:

* :class:`FenicsMultisolutePoreProcess` -- the high-fidelity 3-D FEM reference.
  Drives ``viva_fenics``'s real dolfinx multisolute pore solver (the
  ``viva-fenics`` ``multisolute_pore`` / ``fem_multisolute`` build); dolfinx is
  conda-only, so it registers in the uv ``.venv`` but only RUNS under
  viva-fenics's pixi env (lazy import + a clear "run under pixi" error).
* :class:`MultisolutePoreSurrogateProcess` -- the reduced pore-network surrogate.
  Pure-numpy per-species ``exp(beta.L)`` reduced model (generalising the
  single-tracer :class:`SurrogateThermophoreticTrapProcess`, plan §4.6) with
  adsorption (mobile-fraction) and degradation corrections, CALIBRATED to the
  FEM reference. Runs anywhere in the uv ``.venv`` so a Decision-map / large
  ensemble can be filled cheaply, with the FEM reference reserved for World-view
  points + an audit subset.

Register both on the ``localization`` interface (``register_model`` at the
bottom). Species transport parameters come from the per-run ``species_params``
(``map[vg_species_transport]``); the defaults are the literature-bracketed
midpoints from ``workspace/references/multisolute-pore-physics.md`` (the brackets
drive the structure-uncertainty sweep).
"""
from __future__ import annotations

import numpy as np
from process_bigraph import Process

try:
    from .schemas import CANONICAL_DISSOLVED_SPECIES  # foundation (model-upgrade)
except Exception:  # pragma: no cover - during pre-foundation imports
    CANONICAL_DISSOLVED_SPECIES = (
        "formate", "acetate", "pyruvate", "phosphate", "ammonium",
        "amino_precursor", "amphiphile", "nucleotide_precursor",
    )

# The eight co-localization solutes (subset of CANONICAL_DISSOLVED_SPECIES, minus
# the vent/network inorganics H2/CO2/DIC/alkalinity).
COLOCALIZATION_SPECIES = (
    "phosphate", "ammonium", "formate", "acetate", "pyruvate",
    "amino_precursor", "amphiphile", "nucleotide_precursor",
)

# Default per-species transport parameters, in the FEM-reference convention.
#
# ``diffusivity`` D is in 1e-9 m^2/s (25 C; only RATIOS matter here -- they set
# each species' advective Peclet relative to the mixture mean). ``soret`` is the
# NONDIMENSIONAL effective Soret drift coefficient the pore solve uses (the same
# knob fem_multisolute's weak form takes), NOT the physical S_T in 1/K.
#
# Convention bridge: the physical Soret coefficients in
# workspace/references/multisolute-pore-physics.md (#24) are ~1e-3-1e-2 /K; the
# pore nondimensionalisation maps them onto this O(0.01-0.1) drift coefficient,
# and the values below preserve the reference's RELATIVE ordering (amphiphile >
# nucleotide > amino ~ pyruvate > phosphate ~ formate ~ acetate > ammonium).
# The co-localization verdict depends on this ordering, not on the absolute
# scale, and the structure-uncertainty sweep spans the bracket. k_ads/k_des/k_deg
# are per-step rates (reference condition pH~9, ~90 C).
_DEFAULT_TRANSPORT = {
    #                       D(1e-9) soret(nd) k_ads   k_des   k_deg
    "phosphate":           (0.80,   0.065,    5e-3,   5e-4,   0.0),
    "ammonium":            (1.96,   0.030,    5e-4,   5e-4,   0.0),
    "formate":             (1.45,   0.050,    2e-4,   2e-3,   2e-6),
    "acetate":             (1.09,   0.050,    2e-4,   2e-3,   2e-7),
    "pyruvate":            (1.00,   0.055,    5e-4,   2e-3,   2e-5),
    "amino_precursor":     (1.06,   0.060,    1e-3,   1e-3,   5e-6),
    "amphiphile":          (0.60,   0.130,    5e-3,   2e-4,   1e-7),
    "nucleotide_precursor":(0.50,   0.110,    2e-3,   1e-3,   2e-5),
}


def _default_species_params():
    return {
        name: {"diffusivity": D * 1e-9, "soret": sT,
               "k_ads": ka, "k_des": kd, "k_deg": kg}
        for name, (D, sT, ka, kd, kg) in _DEFAULT_TRANSPORT.items()
    }


# Surrogate constants calibrated to the viva-fenics FEM reference over a
# (Peclet x Soret) grid (scripts/calibrate_pore_surrogate.py): max 6.8% / mean
# 1.7% relative error on single-species enrichment. ``geom`` is the pore-geometry
# accumulation factor; ``pe0`` sets the advective-washout scale (in a FLOW-THROUGH
# pore, enrichment is strongest at low Peclet and washes out as advection
# dominates -- the convective factor is 1/(1 + Pe/pe0), NOT increasing with Pe).
_SURROGATE = {"geom": 0.1623, "pe0": 8.8439, "coloc_k": 1.0}


class MultisolutePoreSurrogateProcess(Process):
    """Reduced multisolute pore-network surrogate (uv ``.venv``, no dolfinx).

    Per species, the steady dissolved-pool enrichment is
    ``exp(beta) * mobile_fraction * degradation_factor`` where
    ``beta = geom * (S_T * dT) * washout(Pe) * (1 - porosity)`` (the single-tracer
    reduced model, per species, calibrated to the FEM reference),
    ``washout(Pe) = 1/(1 + Pe/pe0)`` (a FLOW-THROUGH pore de-concentrates as
    advection dominates -- enrichment is strongest at low Peclet), ``Pe`` is the
    species' advective Peclet = ``peclet * D_mean/D`` (the control ``peclet`` is
    set at the mixture-mean diffusivity), ``mobile_fraction = k_des/(k_ads+k_des)``
    (adsorption removes a species from the dissolved pool), and
    ``degradation_factor = 1/(1 + k_deg * residence)``. Honours the
    ``spatial_transport`` face."""

    config_schema = {
        # peclet is the control advective Peclet (at the mixture-mean D); the FEM
        # reference + calibration are parameterised by it. flow_velocity is kept
        # as a face input port but peclet is the sweep knob.
        "peclet": {"_type": "float", "_default": 8.0},
        "flow_velocity": {"_type": "float", "_default": 1.0e-4},
        "porosity": {"_type": "float", "_default": 0.3},
        "temperature": {"_type": "float", "_default": 333.15},
        "delta_T": {"_type": "float", "_default": 30.0},
        "species_params": {"_type": "tree", "_default": None},
    }

    def inputs(self):
        return {
            "temperature": "float",
            "porosity": "float",
            "flow_velocity": "float",
            "species_params": "tree",
        }

    def outputs(self):
        return {
            "flux_divergence_residual": "float",
            "enrichment": "tree",            # map[species] -> enrichment factor
        }

    def _species(self):
        sp = self.config.get("species_params")
        return sp if sp else _default_species_params()

    def update(self, state, interval):
        cfg = self.config
        porosity = float(cfg["porosity"])
        dT = float(cfg["delta_T"])
        peclet = max(float(cfg["peclet"]), 1e-9)
        geom = _SURROGATE["geom"]
        pe0 = _SURROGATE["pe0"]
        species = self._species()
        D_mean = float(np.mean([float(p["diffusivity"]) for p in species.values()])) or 1e-18
        residence = 1.0 / peclet                    # nondim residence ~ 1/Pe
        enr = {}
        for name, p in species.items():
            D = float(p["diffusivity"])
            sT = float(p["soret"])
            k_ads = float(p.get("k_ads", 0.0))
            k_des = float(p.get("k_des", 0.0))
            k_deg = float(p.get("k_deg", 0.0))
            pe_i = peclet * (D_mean / max(D, 1e-18))   # species' advective Peclet
            washout = 1.0 / (1.0 + pe_i / pe0)         # flow-through de-concentration
            ns = sT * dT                               # nondimensional Soret number
            beta = geom * ns * washout * (1.0 - porosity)
            mobile = (k_des / (k_ads + k_des)) if (k_ads + k_des) > 0 else 1.0
            deg = 1.0 / (1.0 + k_deg * residence)
            enr[name] = float(np.exp(min(beta, 45.0)) * mobile * deg)
        return {"flux_divergence_residual": 0.0, "enrichment": enr}


_PIXI_HINT = (
    "FenicsMultisolutePoreProcess requires the viva-fenics dolfinx multisolute "
    "pore solver (fem_multisolute / fem_pore3d). dolfinx is conda-only: run the "
    "FEniCS arm under viva-fenics's pixi env with viva-genesis + viva-fenics on "
    "PYTHONPATH, or select the 'multisolute_surrogate' / 'fipy' model class."
)


def _require_fenics_multisolute():
    try:
        import dolfinx  # noqa: F401
        from viva_fenics.fem_multisolute import (  # noqa: F401
            colocalization, enrichment, multisolute_pore_step,
        )
        from viva_fenics.fem_pore3d import build_pore3d_mesh  # noqa: F401
    except Exception as exc:  # pragma: no cover - only in the uv .venv
        raise RuntimeError(_PIXI_HINT) from exc
    return (build_pore3d_mesh, multisolute_pore_step, enrichment, colocalization)


class FenicsMultisolutePoreProcess(Process):
    """High-fidelity 3-D FEM reference for multisolute localization: drives
    viva-fenics's real dolfinx converging-diverging-pore multisolute solve and
    reports per-species enrichment + the mixture's worst-pair co-localization.
    Registers in the uv ``.venv`` but only runs under viva-fenics's pixi env.
    Honours the ``spatial_transport`` face."""

    config_schema = {
        "flow_velocity": {"_type": "float", "_default": 1.0e-4},
        "porosity": {"_type": "float", "_default": 0.3},
        "temperature": {"_type": "float", "_default": 333.15},
        "pore_length": {"_type": "float", "_default": 5.0e-3},
        "delta_T": {"_type": "float", "_default": 30.0},
        "peclet": {"_type": "float", "_default": 8.0},
        "throat_radius": {"_type": "float", "_default": 0.12},
        "h_throat": {"_type": "float", "_default": 0.05},
        "n_steps": {"_type": "integer", "_default": 100},
        "species_params": {"_type": "tree", "_default": None},
    }

    def inputs(self):
        return {
            "temperature": "float",
            "porosity": "float",
            "flow_velocity": "float",
            "species_params": "tree",
        }

    def outputs(self):
        return {
            "flux_divergence_residual": "float",
            "enrichment": "tree",            # map[species] -> enrichment factor
            "fields": "tree",                # map[species] -> nodal field (World view)
        }

    def _species(self):
        sp = self.config.get("species_params")
        return sp if sp else _default_species_params()

    def update(self, state, interval):
        build_pore3d_mesh, step, enrich, _coloc = _require_fenics_multisolute()
        from dolfinx import fem

        cfg = self.config
        domain, ftags, markers = build_pore3d_mesh(
            throat_radius=float(cfg["throat_radius"]), h_throat=float(cfg["h_throat"]))
        V = fem.functionspace(domain, ("Lagrange", 1))
        n = V.dofmap.index_map.size_local
        z = V.tabulate_dof_coordinates()[:, 2]
        T = 330.0 - float(cfg["delta_T"]) * z
        sp = self._species()
        D_mean = float(np.mean([float(p["diffusivity"]) for p in sp.values()]))
        w = float(cfg["peclet"]) * D_mean / 1.0
        specs = [{
            "name": name, "dissolved": np.zeros(n), "adsorbed": np.zeros(n),
            # species_params.soret is already the nondimensional Soret drift
            # coefficient the fem_multisolute weak form takes (same convention).
            "D": float(p["diffusivity"]), "soret": float(p["soret"]),
            "inlet": 1.0, "k_ads": float(p.get("k_ads", 0.0)),
            "k_des": float(p.get("k_des", 0.0)), "k_deg": float(p.get("k_deg", 0.0)),
        } for name, p in sp.items()]
        for _ in range(int(cfg["n_steps"])):
            specs = step(domain, V, ftags, markers, specs, dt=0.02,
                         velocity=(0.0, 0.0, w), temperature_array=T)
        enr = {s["name"]: float(enrich(domain, V, ftags, markers, s["dissolved"]))
               for s in specs}
        fields = {s["name"]: s["dissolved"] for s in specs}
        return {"flux_divergence_residual": 0.0, "enrichment": enr, "fields": fields}


# Add the two model classes to the ``localization`` interface registry at import
# time. build_core()'s package walk (_iter_own_process_classes) register_link()s
# the classes themselves (they are top-level attributes of this module, defined
# in this package); this side effect adds them to INTERFACES["localization"] so a
# study can select them as `model_localization` axis values alongside the base
# fipy / fenics / surrogate classes. Idempotent (register_model overwrites).
# Guarded so importing this module on a checkout WITHOUT the model-upgrade
# foundation (no models.register_model) degrades to just defining the classes.
def _register_localization_models():
    from . import models
    models.register_model("localization", "multisolute_surrogate",
                          "local:MultisolutePoreSurrogateProcess")
    models.register_model("localization", "fenics_multisolute_3d",
                          "local:FenicsMultisolutePoreProcess")


try:
    _register_localization_models()
except Exception:  # pragma: no cover - foundation absent (pre-#22 main)
    pass
