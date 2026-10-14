"""Model registry and typed faces for model-substitution-as-experiment.

Full modeling plan sections 4.1/4.2 (the model registry + the typed "face"
concept) and 4.5-4.6 (the spatial-transport interface: FiPy and FEniCS/dolfinx
behind one face). This is the minimal registry the plan describes: an
``INTERFACES`` map of {interface -> {face, models}}, ``resolve()`` turning a
``(interface, model_name)`` into a ``local:`` process address, and
``assert_face()`` which fails loudly at composite-build time if the chosen
class does not honour the interface's canonical face.

The point (plan 4.1): two different model classes expose the **same face**, so
a composite swaps the ``address`` selected by a study param
(``model_spatial_transport ∈ {"fipy", "fenics", ...}``) and nothing else
changes. ``assert_face`` is what makes that swap a *safe* operation.

Spatial transport (plan 4.5). Both solvers implement one ``spatial_transport``
face over the ``world`` block: FiPy (pure-Python finite volume, runs in the uv
``.venv``) and the real dolfinx FEM wrapper in ``viva-fenics`` (conda-only,
runs under pixi). The FEniCS classes register unconditionally (their dolfinx
import is lazy, inside ``update()``), so ``resolve`` / ``assert_face`` work in
the ``.venv`` too; only *running* a FEniCS model without dolfinx raises a clear
"run under pixi" error (see ``viva_genesis.transport.fenics_reactor``).
"""

from __future__ import annotations


# --------------------------------------------------------------------------- #
# The spatial_transport face (plan 4.5)
# --------------------------------------------------------------------------- #
# One face spans both the vent reactor (og-00: advection-diffusion-reaction,
# outlet T/pH/porosity deltas) and the pore trap (og-03: thermophoretic drift,
# per-species enrichment). Ports common to every spatial-transport model are
# REQUIRED; the reactor- and trap-specific ports are ALLOWED (optional). A
# class with a port outside the allowed set, or missing a required port, fails
# the face -- that is the loud failure the plan asks for.
SPATIAL_TRANSPORT_FACE = {
    "required_inputs": {"temperature", "porosity", "flow_velocity"},
    "optional_inputs": {
        # reactor drivers (serpentinization source + chem)
        "pH", "H2", "alkalinity", "heat", "pH_eq",
        # canonical/aggregate forms the plan names
        "sources", "species_params", "geometry",
        # resolved-field inputs (FEM)
        "velocity", "temperature_field",
    },
    "required_outputs": {"flux_divergence_residual"},
    "optional_outputs": {
        # reactor outlet deltas
        "temperature", "pH", "porosity",
        # trap readouts
        "enrichment", "enrichment_factor", "residence_time", "accumulation_peclet",
        # resolved fields (World view)
        "fields",
    },
}

FACES = {
    "spatial_transport": SPATIAL_TRANSPORT_FACE,
}


# --------------------------------------------------------------------------- #
# Interfaces and their swappable model classes (plan 4.1)
# --------------------------------------------------------------------------- #
# E = exists today, A = added by this work. Both FiPy classes already satisfy
# the face; the FEniCS classes are the viva-fenics advection + Soret extension
# adapted to the same ports; the surrogate classes are the reduced Decision-map
# fillers (plan 4.6), registered so their use is declared, not hidden.
INTERFACES = {
    # The vent reactor: advection-diffusion-reaction over the vent cross-section.
    "spatial_transport": {
        "face": "spatial_transport",
        "models": {
            "fipy": "local:FipyReactiveTransportProcess",            # E
            "fenics": "local:FenicsReactiveTransportProcess",        # A (dolfinx FEM)
            # NOTE (plan 4.6): the reduced vent reactor
            # (VentReactorReproductionProcess) is the natural og-00 Decision-map
            # surrogate, but it is a first-order relaxation box without the
            # spatial-transport ports (no flow_velocity in, no
            # flux_divergence_residual out), so it does NOT satisfy this face as
            # written. Adding a thin face-conforming wrapper for it is left as
            # follow-up; the localization surrogate below IS face-conforming.
        },
    },
    # Pore localization: the thermophoretic (Soret) trap.
    "localization": {
        "face": "spatial_transport",
        "models": {
            "fipy": "local:ThermophoreticTrapProcess",               # E
            "fenics": "local:FenicsThermophoreticTrapProcess",       # A (dolfinx FEM + Soret)
            "surrogate": "local:SurrogateThermophoreticTrapProcess",  # A (exp(beta*L), plan 4.6)
        },
    },
}


class FaceError(AssertionError):
    """Raised when a model class does not honour an interface's face."""


def resolve(interface: str, name: str) -> str:
    """Return the ``local:`` process address for ``(interface, model_name)``.

    Pure registry lookup; raises ``KeyError`` for an unknown interface or model
    (never for a missing backend library -- that surfaces at *run* time with a
    clear "run under pixi" message, so ``resolve`` / ``assert_face`` stay usable
    in the uv ``.venv``).
    """
    if interface not in INTERFACES:
        raise KeyError(
            f"unknown interface {interface!r}; have {sorted(INTERFACES)}"
        )
    models = INTERFACES[interface]["models"]
    if name not in models:
        raise KeyError(
            f"unknown model {name!r} for interface {interface!r}; "
            f"have {sorted(models)}"
        )
    return models[name]


def _class_for_address(core, address: str):
    name = address.split(":", 1)[1] if ":" in address else address
    try:
        return core.link_registry[name]
    except Exception as exc:  # pragma: no cover - surfaced as a clear message
        raise FaceError(
            f"no process registered at address {address!r} "
            f"(name {name!r}); is the workspace core built?"
        ) from exc


def model_ports(core, address: str) -> tuple[set, set]:
    """Return (input_port_names, output_port_names) for the class at ``address``.

    Introspects the class's ``inputs()``/``outputs()`` -- static dicts for the
    transport processes, so this needs neither dolfinx nor fipy installed.
    """
    cls = _class_for_address(core, address)
    inst = cls(config={}, core=core)
    return set(inst.inputs().keys()), set(inst.outputs().keys())


def assert_face(core, interface: str, address: str) -> None:
    """Assert the class at ``address`` honours ``interface``'s face, else raise.

    Called at composite-build time (plan 4.2): a model that does not honour the
    face fails loudly here rather than silently producing wrong wiring. Checks
    that the class declares every REQUIRED port and declares no port outside the
    required ∪ optional set.
    """
    face_name = INTERFACES[interface]["face"]
    face = FACES[face_name]
    ins, outs = model_ports(core, address)

    allowed_in = face["required_inputs"] | face["optional_inputs"]
    allowed_out = face["required_outputs"] | face["optional_outputs"]

    missing_in = face["required_inputs"] - ins
    missing_out = face["required_outputs"] - outs
    foreign_in = ins - allowed_in
    foreign_out = outs - allowed_out

    problems = []
    if missing_in:
        problems.append(f"missing required input ports {sorted(missing_in)}")
    if missing_out:
        problems.append(f"missing required output ports {sorted(missing_out)}")
    if foreign_in:
        problems.append(f"input ports outside the face {sorted(foreign_in)}")
    if foreign_out:
        problems.append(f"output ports outside the face {sorted(foreign_out)}")

    if problems:
        raise FaceError(
            f"{address!r} does not satisfy the {interface!r} face "
            f"({face_name!r}): " + "; ".join(problems)
        )


def resolve_checked(core, interface: str, name: str) -> str:
    """resolve() + assert_face(): the one call a composite generator makes."""
    address = resolve(interface, name)
    assert_face(core, interface, address)
    return address
