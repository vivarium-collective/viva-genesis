"""MineralSurfaceDynamicsProcess — the evolving mineral-water interface (studies 27, 30).

A general, composable Process: precipitation/dissolution change porosity (a delta
that composes with FiPy's transport-driven porosity), and precipitation passivates
the catalytic surface over time (catalytic_accessibility decays monotonically).
Ports are unit-typed to match the existing geochemistry/transport processes so it
drops into the geochemical_world coupling.
"""
import pytest

from process_bigraph import allocate_core
from viva_genesis.geochemistry.mineral_surface_dynamics import MineralSurfaceDynamicsProcess


def _proc(**cfg):
    return MineralSurfaceDynamicsProcess(config=cfg, core=allocate_core())


def test_ports_declared():
    p = _proc()
    ins, outs = p.inputs(), p.outputs()
    assert {"saturation_index", "temperature", "porosity", "catalytic_accessibility"} <= set(ins)
    assert {"porosity", "catalytic_accessibility", "reactive_surface_area",
            "mineral_mass_residual"} <= set(outs)


def test_update_returns_declared_outputs():
    p = _proc()
    out = p.update({"saturation_index": 0.0, "temperature": 350.0,
                    "flow_velocity": 1e-3, "porosity": 0.3,
                    "catalytic_accessibility": 1.0}, 1.0)
    for k in ("porosity", "catalytic_accessibility", "reactive_surface_area", "mineral_mass_residual"):
        assert k in out


def test_supersaturation_precipitates_and_reduces_porosity():
    p = _proc()
    out = p.update({"saturation_index": 1.0, "temperature": 350.0,
                    "flow_velocity": 1e-3, "porosity": 0.3,
                    "catalytic_accessibility": 1.0}, 1.0)
    assert out["porosity"] < 0.0  # precipitation clogs pores -> porosity delta negative


def test_undersaturation_dissolves_and_opens_porosity():
    p = _proc()
    out = p.update({"saturation_index": -1.0, "temperature": 350.0,
                    "flow_velocity": 1e-3, "porosity": 0.3,
                    "catalytic_accessibility": 1.0}, 1.0)
    assert out["porosity"] > 0.0  # dissolution opens pores


def test_precipitation_passivates_catalyst_monotonically():
    p = _proc()
    # Under precipitation the catalytic surface only degrades (delta <= 0).
    out = p.update({"saturation_index": 1.0, "temperature": 350.0,
                    "flow_velocity": 1e-3, "porosity": 0.3,
                    "catalytic_accessibility": 1.0}, 1.0)
    assert out["catalytic_accessibility"] <= 0.0


def test_catalyst_decay_scales_with_remaining_accessibility():
    p = _proc()
    hi = p.update({"saturation_index": 1.0, "temperature": 350.0, "flow_velocity": 1e-3,
                   "porosity": 0.3, "catalytic_accessibility": 1.0}, 1.0)
    lo = p.update({"saturation_index": 1.0, "temperature": 350.0, "flow_velocity": 1e-3,
                   "porosity": 0.3, "catalytic_accessibility": 0.2}, 1.0)
    # First-order decay: less remaining accessibility -> smaller absolute decay.
    assert abs(lo["catalytic_accessibility"]) < abs(hi["catalytic_accessibility"])


def test_mineral_mass_conserved():
    p = _proc()
    out = p.update({"saturation_index": 1.0, "temperature": 350.0,
                    "flow_velocity": 1e-3, "porosity": 0.3,
                    "catalytic_accessibility": 1.0}, 1.0)
    assert abs(out["mineral_mass_residual"]) < 1e-9  # precipitated == porosity loss * density


def test_composes_in_a_minimal_bigraph():
    from process_bigraph import Composite
    core = allocate_core()
    core.register_link("MineralSurfaceDynamicsProcess", MineralSurfaceDynamicsProcess)
    doc = {
        "mineral": {
            "_type": "process",
            "address": "local:MineralSurfaceDynamicsProcess",
            "config": {},
            "interval": 1.0,
            "inputs": {"saturation_index": ["s", "si"], "temperature": ["s", "T"],
                       "flow_velocity": ["s", "v"], "porosity": ["s", "phi"],
                       "catalytic_accessibility": ["s", "acc"]},
            "outputs": {"porosity": ["s", "phi"], "catalytic_accessibility": ["s", "acc"],
                        "reactive_surface_area": ["s", "area"],
                        "mineral_mass_residual": ["s", "resid"]},
        },
        "s": {"si": 1.0, "T": 350.0, "v": 1e-3, "phi": 0.3, "acc": 1.0,
              "area": 0.0, "resid": 0.0},
    }
    sim = Composite({"state": doc}, core=core)
    sim.run(3.0)  # must not raise; porosity accumulates the deltas
