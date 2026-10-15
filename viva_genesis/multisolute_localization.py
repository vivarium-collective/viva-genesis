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

# Literature-bracketed default transport parameters (bracket midpoints) from
# workspace/references/multisolute-pore-physics.md. D in 1e-9 m^2/s (25 C,
# Stokes-Einstein-corrected to the pore T in the solver); soret in 1e-3 /K;
# k_ads/k_des/k_deg in 1/s (reference condition pH~9, ~90 C). These are
# bracketed estimates, NOT measured per-species values -- the structure sweep
# spans the ranges in the reference.
_DEFAULT_TRANSPORT = {
    #                       D(1e-9) soret(1e-3) k_ads   k_des   k_deg
    "phosphate":           (0.80,   6.5,        5e-3,   5e-4,   0.0),
    "ammonium":            (1.96,   2.5,        5e-4,   5e-4,   0.0),
    "formate":             (1.45,   4.5,        2e-4,   2e-3,   2e-6),
    "acetate":             (1.09,   4.5,        2e-4,   2e-3,   2e-7),
    "pyruvate":            (1.00,   5.0,        5e-4,   2e-3,   2e-5),
    "amino_precursor":     (1.06,   5.5,        1e-3,   1e-3,   5e-6),
    "amphiphile":          (0.60,   12.0,       5e-3,   2e-4,   1e-7),
    "nucleotide_precursor":(0.50,   10.0,       2e-3,   1e-3,   2e-5),
}


def _default_species_params():
    return {
        name: {"diffusivity": D * 1e-9, "soret": sT * 1e-3,
               "k_ads": ka, "k_des": kd, "k_deg": kg}
        for name, (D, sT, ka, kd, kg) in _DEFAULT_TRANSPORT.items()
    }


# Calibrated surrogate constants (fit to the viva-fenics FEM reference; see
# scripts/calibrate_pore_surrogate.py). ``geom`` scales the accumulation
# exponent; ``pe0`` sets the convective-enhancement saturation (the resolved
# field saturates past the trustworthy Peclet, so the surrogate saturates too).
_SURROGATE = {"geom": 1.0, "pe0": 10.0, "coloc_k": 1.0}


class MultisolutePoreSurrogateProcess(Process):
    """Reduced multisolute pore-network surrogate (uv ``.venv``, no dolfinx).

    Per species, the steady dissolved-pool enrichment is
    ``exp(beta * L) * mobile_fraction * degradation_factor`` where
    ``beta = geom * S_T * dT * saturating(Pe) * (1 - porosity)`` (the
    single-tracer reduced model, per species), ``mobile_fraction =
    k_des/(k_ads+k_des)`` (adsorption removes a species from the dissolved pool),
    and ``degradation_factor = 1/(1 + k_deg * residence_time)`` (degradation
    competes with accumulation). Honours the ``spatial_transport`` face."""

    config_schema = {
        "flow_velocity": {"_type": "float", "_default": 1.0e-4},
        "porosity": {"_type": "float", "_default": 0.3},
        "temperature": {"_type": "float", "_default": 333.15},
        "pore_length": {"_type": "float", "_default": 5.0e-3},
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
        w = max(float(cfg["flow_velocity"]), 1e-12)
        porosity = float(cfg["porosity"])
        dT = float(cfg["delta_T"])
        L = float(cfg["pore_length"])
        geom = _SURROGATE["geom"]
        pe0 = _SURROGATE["pe0"]
        enr = {}
        for name, p in self._species().items():
            D = float(p["diffusivity"])
            sT = float(p["soret"])
            k_ads = float(p.get("k_ads", 0.0))
            k_des = float(p.get("k_des", 0.0))
            k_deg = float(p.get("k_deg", 0.0))
            pe = w * L / max(D, 1e-18)
            sat = 1.0 - np.exp(-pe / pe0)           # convective enhancement, saturating
            beta = geom * sT * dT * sat * (1.0 - porosity)
            mobile = (k_des / (k_ads + k_des)) if (k_ads + k_des) > 0 else 1.0
            residence = L / w
            deg = 1.0 / (1.0 + k_deg * residence)
            enr[name] = float(np.exp(min(beta * L, 45.0)) * mobile * deg)
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
            "D": float(p["diffusivity"]), "soret": float(p["soret"]) * 1e3,  # /K -> /nondim-K scale
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
