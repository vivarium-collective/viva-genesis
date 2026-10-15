"""Model class as a categorical sweep axis (Model Upgrade plan, Process Bigraph
principle): the serpentinization face has two real classes; sweep_grid takes a
string-valued axis; the UQ ensemble reducers separate parameter from
model-structure uncertainty on the result."""

from __future__ import annotations

import numpy as np
import pytest

from viva_genesis import models
from viva_genesis.core import build_core


def test_serpentinization_face_has_two_registered_classes():
    core = build_core()
    assert models.model_names("serpentinization") == ["phreeqc", "reduced"]
    for n in models.model_names("serpentinization"):
        models.assert_face(core, "serpentinization", models.resolve("serpentinization", n))


def test_uniform_upflow_class_on_spatial_transport_face():
    core = build_core()
    assert "fipy_uniform_upflow" in models.model_names("spatial_transport")
    models.assert_face(core, "spatial_transport", models.resolve("spatial_transport", "fipy_uniform_upflow"))
    from viva_genesis.transport.fipy_reactor import FipyUniformUpflowTransportProcess
    assert FipyUniformUpflowTransportProcess.config_schema["buoyancy"]["_default"] == 0.0


def test_axis_and_model_parameters_and_split():
    ax = models.axis("spatial_transport", ["fipy", "fenics"])
    assert ax == {"model_spatial_transport": ["fipy", "fenics"]}
    with pytest.raises(KeyError):
        models.axis("spatial_transport", ["no_such"])
    params = models.model_parameters("serpentinization", "spatial_transport",
                                     defaults={"serpentinization": "phreeqc"})
    assert params["model_serpentinization"]["default"] == "phreeqc"
    assert "fipy_uniform_upflow" in params["model_spatial_transport"]["description"]
    m, rest = models.split_model_kwargs({"model_serpentinization": "reduced", "flow_velocity": 1e-3,
                                         "model_unknown": "x"})
    assert m == {"serpentinization": "reduced"} and set(rest) == {"flow_velocity", "model_unknown"}


def test_register_model_on_new_interface_requires_face():
    with pytest.raises(KeyError):
        models.register_model("brand_new", "a", "local:X")
    models.register_model("brand_new", "a", "local:X",
                          face_spec={"required_inputs": set(), "optional_inputs": set(),
                                     "required_outputs": set(), "optional_outputs": set()})
    assert models.resolve("brand_new", "a") == "local:X"
    del models.INTERFACES["brand_new"]; del models.FACES["brand_new"]


def test_sweep_grid_categorical_axis_and_structure_agreement():
    """Sweep the geochemical world over (model_serpentinization x flow_velocity) with a
    fast reduced-size world, then reduce to per-class pass fractions + agreement."""
    pytest.importorskip("fipy")
    pytest.importorskip("phreeqpython")
    from viva_genesis import sweep
    from viva_genesis.composites.geochemical_world import geochemical_world, settled_H2_flux
    from viva_genesis.uq.ensemble import pass_fraction, structure_agreement, decision_envelope

    res = sweep.sweep_grid(
        geochemical_world,
        axes={**models.axis("serpentinization"), "flow_velocity": [5.0e-4, 2.0e-3]},
        reduce={"h2_flux": settled_H2_flux},
        fixed={"nx": 8},
        n_steps=4,
    )
    assert res.categorical_axes() == ["model_serpentinization"]
    assert res.shape == (2, 2)
    assert res.meta["categorical_axes"] == ["model_serpentinization"]
    assert np.all(np.isfinite(res.surfaces["h2_flux"]))
    pf = pass_fraction(res, "model_serpentinization", "h2_flux", threshold=1e-9)
    assert set(pf) == {"phreeqc", "reduced"} and all(v == 1.0 for v in pf.values())
    sa = structure_agreement(res, "model_serpentinization", "h2_flux", threshold=1e-9)
    assert sa["agreement"] == 1.0 and sa["structure_uncertainty"] == 0.0
    env = decision_envelope(res, "model_serpentinization", "h2_flux", threshold=1e-9)
    assert env["intersection"].shape == (2,) and not env["structure_sensitive"].any()
    sub = res.slice_along("model_serpentinization", "reduced")
    assert sub.axis_order == ["flow_velocity"] and sub.surfaces["h2_flux"].shape == (2,)


def test_structure_agreement_on_masks_disagreement():
    from viva_genesis.uq.ensemble import structure_agreement, pass_fraction
    masks = {"a": np.array([True, True, False, False]), "b": np.array([True, False, False, True])}
    sa = structure_agreement(masks)
    assert sa["agreement"] == 0.5 and sa["structure_uncertainty"] == 0.5
    assert pass_fraction(masks) == {"a": 0.5, "b": 0.5}
