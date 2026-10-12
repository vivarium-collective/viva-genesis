"""Tests for the real FiPy reactive-transport Process (Module B, og-00).

Guarded with ``importorskip`` so CI without fipy stays green while a machine
with fipy exercises the genuine FVM solve.
"""
import pytest

fipy = pytest.importorskip("fipy")

from process_bigraph import allocate_core

from viva_genesis.transport.fipy_reactor import (
    FipyReactiveTransportProcess, spatial_profile,
)

_IN_KEYS = {"temperature", "pH", "porosity", "H2", "alkalinity", "heat", "flow_velocity", "pH_eq"}
_OUT_KEYS = {"temperature", "pH", "porosity", "flux_divergence_residual"}


def _make():
    core = allocate_core()
    return FipyReactiveTransportProcess(config={"nx": 40}, core=core)


def test_ports_shape():
    proc = _make()
    ins, outs = proc.inputs(), proc.outputs()
    assert isinstance(ins, dict) and isinstance(outs, dict)
    assert set(ins) == _IN_KEYS
    assert set(outs) == _OUT_KEYS
    # the conservation witness is a sensor (overwrite), the rest compose as deltas
    assert outs["flux_divergence_residual"]["_type"] == "overwrite[float]"
    for k in ("temperature", "pH", "porosity"):
        assert outs[k]["_type"] == "float"


def test_real_fvm_run_conserves_and_drives_state():
    proc = _make()
    # Running interface state we advance ourselves by applying the emitted deltas.
    st = {"temperature": 300.0, "pH": 7.2, "porosity": 0.30,
          "H2": 5.0e-3, "alkalinity": 2.0e-3, "heat": 20.0, "flow_velocity": 5.0e-3,
          "pH_eq": 9.5}
    temps = []
    for _ in range(20):
        upd = proc.update(st, interval=1.0)
        assert set(upd) == _OUT_KEYS, f"missing output ports: {set(upd)}"
        # FVM conservation witness stays tiny every step
        assert upd["flux_divergence_residual"] <= 1e-3, upd["flux_divergence_residual"]
        # porosity only clogs (never opens) under a positive alkalinity source
        assert upd["porosity"] <= 1e-12
        st["temperature"] += upd["temperature"]
        st["pH"] += upd["pH"]
        st["porosity"] += upd["porosity"]
        temps.append(st["temperature"])

    # Heat forces a warm inlet field (275 + 3.5*20 = 345 K); the outlet-driven
    # delta should pull the interface temperature UP, roughly monotonically.
    assert temps[-1] > temps[0] + 5.0, (temps[0], temps[-1])
    rises = sum(1 for i in range(1, len(temps)) if temps[i] >= temps[i - 1] - 1e-9)
    assert rises >= len(temps) - 2, "temperature should climb near-monotonically"
    # pH driven toward the transported equilibrium pH_eq (> starting 7.2, <= pH_eq)
    assert 7.2 < st["pH"] <= 9.5 + 1e-6
    # porosity clogged below its start
    assert st["porosity"] < 0.30


def test_spatial_profile_available_after_run():
    proc = _make()
    assert spatial_profile(proc)["x"] == []     # unbuilt before first step
    proc.update({"temperature": 300.0, "pH": 7.2, "porosity": 0.3,
                 "H2": 5e-3, "alkalinity": 2e-3, "heat": 20.0, "flow_velocity": 1e-3,
                 "pH_eq": 9.5},
                interval=1.0)
    prof = spatial_profile(proc)
    assert len(prof["x"]) == 40
    assert len(prof["temperature"]) == 40 and len(prof["solute"]) == 40
    # inlet (left) warmer than the far field initially cold column near outlet? just
    # assert the transported heat field is non-trivial.
    assert max(prof["temperature"]) > min(prof["temperature"])
