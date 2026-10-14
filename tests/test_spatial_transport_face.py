"""The swappable spatial_transport face (full modeling plan 4.1/4.2 + 4.5-4.6):
model registry, assert_face, the fipy/fenics swap, and the Ray-ready sweep.

The FiPy arm runs the real finite-volume solver (importorskip fipy). The FEniCS
arm's dolfinx solve is conda-only; here (the uv .venv) we assert it *builds*
(resolve + assert_face succeed -- the face is introspectable without dolfinx)
and that *running* it raises a clear "run under pixi" error. The real dolfinx
head-to-head runs under pixi via scripts/compare_spatial_transport.py.
"""

from __future__ import annotations

import pytest

from process_bigraph import Composite, gather_emitter_results
from viva_genesis.core import build_core
from viva_genesis import models


# --------------------------------------------------------------------------- #
# registry + face
# --------------------------------------------------------------------------- #

def test_new_processes_registered():
    reg = build_core().link_registry
    for n in ("FenicsReactiveTransportProcess", "FenicsThermophoreticTrapProcess",
              "SurrogateThermophoreticTrapProcess"):
        assert n in reg


def test_resolve_and_assert_face_fipy_and_fenics():
    core = build_core()
    # Both solvers satisfy the one face, on both interfaces.
    for iface, name in [("spatial_transport", "fipy"), ("spatial_transport", "fenics"),
                        ("localization", "fipy"), ("localization", "fenics"),
                        ("localization", "surrogate")]:
        addr = models.resolve(iface, name)
        models.assert_face(core, iface, addr)  # must not raise


def test_resolve_unknown_raises():
    with pytest.raises(KeyError):
        models.resolve("localization", "no_such_model")
    with pytest.raises(KeyError):
        models.resolve("no_such_interface", "fipy")


def test_assert_face_rejects_nonconforming_class():
    from process_bigraph import Process

    class WrongPorts(Process):
        def inputs(self):
            return {"temperature": "float"}            # missing porosity, flow_velocity

        def outputs(self):
            return {"made_up_output": "float"}          # missing flux_divergence_residual

        def update(self, state, interval):
            return {}

    core = build_core()
    core.register_link("WrongPorts", WrongPorts)
    with pytest.raises(models.FaceError):
        models.assert_face(core, "localization", "local:WrongPorts")


# --------------------------------------------------------------------------- #
# swappable composites
# --------------------------------------------------------------------------- #

def test_trap_composite_fipy_runs_real_solver():
    pytest.importorskip("fipy")
    from viva_genesis.composites.spatial_transport import spatial_transport_trap
    core = build_core()
    sim = Composite({"state": spatial_transport_trap(core=core, model_spatial_transport="fipy")},
                    core=core)
    for _ in range(10):
        sim.run(1)
    last = gather_emitter_results(sim)[("emitter",)][-1]
    assert last["enrichment_factor"] > 1.0e7       # Baaske-favorable default
    assert last["accumulation_peclet"] >= 18.0


def test_trap_composite_fenics_builds_but_needs_pixi():
    """The FEniCS arm BUILDS in the .venv (resolve + assert_face succeed), but
    running it without dolfinx raises a clear 'run under pixi' error."""
    from viva_genesis.composites.spatial_transport import spatial_transport_trap
    core = build_core()
    doc = spatial_transport_trap(core=core, model_spatial_transport="fenics")
    assert doc["pore"]["address"] == "local:FenicsThermophoreticTrapProcess"
    sim = Composite({"state": doc}, core=core)
    with pytest.raises(RuntimeError, match="pixi"):
        sim.run(1)


def test_vent_composite_fenics_builds_but_needs_pixi():
    from viva_genesis.composites.spatial_transport import spatial_transport_vent
    core = build_core()
    doc = spatial_transport_vent(core=core, model_spatial_transport="fenics")
    assert doc["reactor"]["address"] == "local:FenicsReactiveTransportProcess"
    sim = Composite({"state": doc}, core=core)
    with pytest.raises(RuntimeError, match="pixi"):
        sim.run(1)


# --------------------------------------------------------------------------- #
# sweep (plan 4.6, lever 1) -- Ray-ready; serial == process-pool
# --------------------------------------------------------------------------- #

def test_sweep_grid_serial_trap():
    """sweep_grid drives the swappable trap over a pore-length axis (model held
    fixed via `fixed`, since axes are numeric); longer pore -> larger Pe."""
    pytest.importorskip("fipy")
    from viva_genesis import sweep
    from viva_genesis.composites.spatial_transport import spatial_transport_trap
    res = sweep.sweep_grid(
        spatial_transport_trap,
        axes={"pore_length": [1.0e-3, 5.0e-3]},
        reduce={"peclet": sweep.last("accumulation_peclet")},
        fixed={"model_spatial_transport": "fipy"},
        n_steps=5,
    )
    surf = res.surfaces["peclet"]
    assert surf.shape == (2,)
    assert surf[1] > surf[0]            # exponential-in-length accumulation


def test_sweep_ray_matches_serial():
    """The Ray dispatch (plan 4.6) agrees with the serial path point-for-point.
    Ray is optional (the mini has it); skip where it is not installed."""
    pytest.importorskip("fipy")
    pytest.importorskip("ray")
    from viva_genesis import sweep
    from viva_genesis.composites.spatial_transport import spatial_transport_trap
    kw = dict(axes={"pore_length": [1.0e-3, 5.0e-3]},
              reduce={"peclet": sweep.last("accumulation_peclet")},
              fixed={"model_spatial_transport": "fipy"}, n_steps=5)
    serial = sweep.sweep_grid(spatial_transport_trap, n_jobs=1, **kw)
    ray_res = sweep.sweep_grid(spatial_transport_trap, n_jobs="ray", **kw)
    import numpy as np
    assert np.allclose(serial.surfaces["peclet"], ray_res.surfaces["peclet"], rtol=1e-9)
