"""Multisolute localization model classes on the `localization` face (Phase 4).

Covers the pure-numpy surrogate's physics (runs anywhere in the uv .venv), the
face-conformance + registration of both classes, and that the dolfinx FEM
reference registers but raises a clear "run under pixi" error here (no backend).
The FEM reference's actual solve is validated in viva-fenics (test_pore3d_*).
"""
import numpy as np
import pytest

from viva_genesis.core import build_core
from viva_genesis import models
from viva_genesis.multisolute_localization import (
    COLOCALIZATION_SPECIES,
    FenicsMultisolutePoreProcess,
    MultisolutePoreSurrogateProcess,
    _default_species_params,
)


# --- registration + face conformance ---------------------------------------

def test_both_classes_registered_on_localization():
    build_core()  # package walk register_link()s the classes; import adds to INTERFACES
    names = models.model_names("localization")
    assert "multisolute_surrogate" in names
    assert "fenics_multisolute_3d" in names
    # the base classes are still there
    assert {"fipy", "fenics", "surrogate"} <= set(names)


def test_both_classes_satisfy_the_face():
    core = build_core()
    # resolve_checked runs assert_face; no raise == the ports honour the face
    addr_s = models.resolve_checked(core, "localization", "multisolute_surrogate")
    addr_f = models.resolve_checked(core, "localization", "fenics_multisolute_3d")
    assert addr_s == "local:MultisolutePoreSurrogateProcess"
    assert addr_f == "local:FenicsMultisolutePoreProcess"


def test_classes_resolve_in_core_registry():
    core = build_core()
    assert "MultisolutePoreSurrogateProcess" in core.link_registry
    assert "FenicsMultisolutePoreProcess" in core.link_registry


# --- surrogate physics (uv .venv, no dolfinx) ------------------------------

def _run_surrogate(species_params=None, **cfg):
    core = build_core()
    config = {"flow_velocity": 1e-3, "porosity": 0.3, "temperature": 363.0,
              "pore_length": 5e-3, "delta_T": 30.0, "species_params": species_params}
    config.update(cfg)
    proc = MultisolutePoreSurrogateProcess(config=config, core=core)
    return proc.update({}, 1.0)


def test_surrogate_returns_enrichment_for_all_eight_species():
    out = _run_surrogate()
    enr = out["enrichment"]
    assert set(enr) == set(COLOCALIZATION_SPECIES)
    assert all(np.isfinite(v) and v > 0 for v in enr.values())
    assert out["flux_divergence_residual"] == 0.0


def test_surrogate_higher_soret_enriches_more():
    """Two species identical but for Soret -> the higher-S_T one enriches more."""
    sp = {
        "lo": {"diffusivity": 1e-9, "soret": 3e-3, "k_ads": 0, "k_des": 0, "k_deg": 0},
        "hi": {"diffusivity": 1e-9, "soret": 9e-3, "k_ads": 0, "k_des": 0, "k_deg": 0},
    }
    enr = _run_surrogate(sp)["enrichment"]
    assert enr["hi"] > enr["lo"] > 1.0


def test_surrogate_adsorption_lowers_dissolved_enrichment():
    """A strongly-adsorbing species has a smaller mobile (dissolved) enrichment."""
    sp = {
        "mobile": {"diffusivity": 1e-9, "soret": 6e-3, "k_ads": 0.0, "k_des": 1e-3, "k_deg": 0},
        "sticky": {"diffusivity": 1e-9, "soret": 6e-3, "k_ads": 9e-3, "k_des": 1e-3, "k_deg": 0},
    }
    enr = _run_surrogate(sp)["enrichment"]
    assert enr["sticky"] < enr["mobile"]


def test_surrogate_degradation_lowers_enrichment():
    sp = {
        "stable": {"diffusivity": 1e-9, "soret": 6e-3, "k_ads": 0, "k_des": 0, "k_deg": 0.0},
        "labile": {"diffusivity": 1e-9, "soret": 6e-3, "k_ads": 0, "k_des": 0, "k_deg": 1e-2},
    }
    enr = _run_surrogate(sp)["enrichment"]
    assert enr["labile"] < enr["stable"]


def test_default_species_params_are_the_eight_solutes():
    sp = _default_species_params()
    assert set(sp) == set(COLOCALIZATION_SPECIES)
    for p in sp.values():
        assert p["diffusivity"] > 0 and "soret" in p
        for k in ("k_ads", "k_des", "k_deg"):
            assert k in p


# --- FEM reference registers but needs pixi here ---------------------------

def test_fenics_reference_raises_run_under_pixi_without_backend():
    core = build_core()
    proc = FenicsMultisolutePoreProcess(config={}, core=core)
    with pytest.raises(RuntimeError, match="pixi"):
        proc.update({}, 1.0)
