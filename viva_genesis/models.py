"""Model registry and typed faces for model-substitution-as-experiment.

Full modeling plan sections 4.1/4.2 (the model registry + the typed "face"
concept) and 4.5-4.6 (the spatial-transport interface: FiPy and FEniCS/dolfinx
behind one face), generalised per the Model Upgrade plan's Process Bigraph
principle: *every upgraded mechanism implements a canonical biological
interface, and a model class becomes a categorical experimental factor.*

Three things live here:

1. **Faces** (``FACES``): per interface, the REQUIRED and OPTIONAL input/output
   port names a model class must honour. Every face port must also map onto a
   canonical ``vg_*`` schema field (``viva_genesis.schemas.PORT_TO_CANONICAL``)
   or a declared diagnostic — ``canonical_coverage`` audits that, so a face is
   expressible in the shared biological vocabulary, not just a port list.
2. **Interfaces** (``INTERFACES``): ``{interface -> {face, models}}`` where
   ``models`` maps a model-class NAME to a ``local:`` process address.
   ``resolve()`` turns ``(interface, name)`` into the address and
   ``assert_face()`` fails loudly at composite-build time if the class does not
   honour the face.
3. **Model class as a sweep axis**: a composite generator takes one keyword
   ``model_<interface>`` per interface it exposes (``model_parameters()``
   declares them uniformly); ``viva_genesis.sweep.sweep_grid`` accepts the
   string-valued axis ``{"model_<interface>": axis(interface)}`` and the UQ
   layer (``viva_genesis.uq.ensemble``) reduces the result to per-class
   ``pass_fraction`` and cross-class ``structure_agreement``.

Spatial transport (plan 4.5). Both solvers implement one ``spatial_transport``
face over the ``world`` block: FiPy (pure-Python finite volume, runs in the uv
``.venv``) and the real dolfinx FEM wrapper in ``viva-fenics`` (conda-only,
runs under pixi). The FEniCS classes register unconditionally (their dolfinx
import is lazy, inside ``update()``), so ``resolve`` / ``assert_face`` work in
the ``.venv`` too; only *running* a FEniCS model without dolfinx raises a clear
"run under pixi" error (see ``viva_genesis.transport.fenics_reactor``).

Serpentinization (Model Upgrade plan, priority upgrade A). The real PHREEQC
class and the reduced Gaussian-source reproduction honour one
``serpentinization`` face, so the og-00 world can sweep the geochemistry
engine as a class axis; the planned Reaktoro / PFLOTRAN classes register on
the same face when they land.

Carbon fixation (Model Upgrade plan, Phase 2). Three classes honour one
``carbon_fixation`` face: ``empirical`` (og-01's lab-calibrated gated kinetics,
adapted to publish its failure-mode attribution), ``butler_volmer`` (Nernst
half-cell potentials + Butler-Volmer electrode kinetics + the ohmic mineral
circuit, solved as a galvanic cell each tick) and ``microkinetic``
(CatMAP/Cantera adsorbate microkinetics; the backend is conda-only, so the
class registers here and raises a clear "run under pixi" error in ``update``).
"""

from __future__ import annotations

from .schemas import PORT_TO_CANONICAL

MODEL_PARAM_PREFIX = "model_"


# --------------------------------------------------------------------------- #
# Faces
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

# The serpentinization source: (T, flow[, DIC]) -> H2 / alkalinity / heat
# source deltas + instantaneous flux sensors. The real PHREEQC class adds the
# speciation sensors (pe, pH_eq, charge_imbalance) as optional outputs.
SERPENTINIZATION_FACE = {
    "required_inputs": {"temperature", "flow_velocity"},
    "optional_inputs": {"DIC", "pressure"},
    "required_outputs": {"H2", "alkalinity", "heat", "H2_flux"},
    "optional_outputs": {"alkalinity_flux", "heat_flux", "pe", "pH_eq", "charge_imbalance"},
}

# Carbon fixation at the Fe/Ni-sulfide interface (Model Upgrade plan, Phase 2).
# Every class turns the fluid state (H2, CO2, T, the catalyst) into product
# increments on the ONE dissolved pool plus the net organic-carbon flux. The
# empirical class reads the proton-motive drive the og-01 gradient + budget
# supply; the electrochemical classes read the two pH's and the mineral layer
# (conductivity, thickness, Ni fraction) and derive the drive themselves, so
# both sets are OPTIONAL inputs. The optional outputs are the circuit readouts
# (emf, overpotential, current, faradaic efficiency, electron fluxes) and the
# failure-mode attribution every class must be able to publish.
CARBON_FIXATION_FACE = {
    "required_inputs": {"H2", "CO2", "temperature", "catalyst_activity",
                        "formate", "acetate", "pyruvate"},
    "optional_inputs": {
        # og-01 empirical drive (proton-motive force + eQuilibrator gate)
        "pmf", "feasible_formate", "feasible_acetate", "feasible_pyruvate",
        # electrochemical drive (fluid redox + the mineral circuit)
        "pH_vent", "pH_ocean", "ni_fraction", "conductivity", "layer_thickness",
        "porosity", "ionic_strength",
    },
    "required_outputs": {"formate", "acetate", "pyruvate", "net_carbon_flux"},
    "optional_outputs": {
        # circuit readouts
        "current_density", "emf", "overpotential", "electric_potential",
        "faradaic_efficiency", "electron_flux", "carbon_electron_flux",
        "her_electron_flux", "iv_residual", "gradient_efficiency",
        # failure-mode attribution
        "loss_thermodynamic", "loss_electrical", "loss_catalytic", "loss_transport",
        "limitation_code",
    },
}

# The open chemical network (Model Upgrade plan, Phase 3): a reaction network
# fed reduced carbon under flow. Every class must publish og-02's three
# emergent observables; the species pools, the post-hoc motif statistics and
# the numerical-verification witnesses (element / carbon / free-energy
# ledger) are optional so the curated SBML class and the generated classes
# share one face.
PROTO_METABOLISM_FACE = {
    "required_inputs": {"feed_CO2"},
    "optional_inputs": {"feed_pyruvate", "feed_H2", "feed_formaldehyde", "feed_formate", "feed_acetate",
                        "temperature", "pH"},
    "required_outputs": {"net_carbon_flux", "autocatalytic_gain", "network_connected"},
    "optional_outputs": {
        # species pools (canonical dissolved names)
        "OAA", "malate", "succinate", "acetate", "formate", "pyruvate", "formaldehyde", "glycolaldehyde",
        "total_organic_carbon",
        # post-hoc network statistics
        "n_persistent_species", "n_autocatalytic_motifs", "autocatalytic_core_size", "catalyst_saturation",
        # ledger witnesses
        "dissipation", "element_residual", "carbon_residual",
    },
}

# The endogenous boundary (Model Upgrade plan, Phase 5). Every class turns the
# fluid conditions (T, ionic strength, pH) + the available amphiphile into a
# self-assembled vesicle boundary and its individuality readouts (retention vs
# access). `single_chain`/`mixed` are the Jordan-2019 fatty-acid ± co-surfactant
# vesicle (one ProtocellAssemblyProcess, mix_fraction 0 vs >0); the alternative
# membrane chemistry (thioester/aminothiol) has a different viability window.
# amphiphile is an OPTIONAL input: the endogenous arm feeds it from
# AmphiphileSynthesisProcess, the exogenous arm takes it as a fixed pool.
BOUNDARY_FACE = {
    "required_inputs": {"temperature", "ionic_strength", "pH"},
    "optional_inputs": {"mix_fraction", "amphiphile"},
    "required_outputs": {"membrane_area", "viable_compartments"},
    "optional_outputs": {"permeability", "compartment_volume", "retention",
                         "access", "individuality_access", "boundary_formed"},
}

FACES = {
    "spatial_transport": SPATIAL_TRANSPORT_FACE,
    "serpentinization": SERPENTINIZATION_FACE,
    "carbon_fixation": CARBON_FIXATION_FACE,
    "proto_metabolism": PROTO_METABOLISM_FACE,
    "boundary": BOUNDARY_FACE,
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
            "fipy": "local:FipyReactiveTransportProcess",            # E (Darcy-Boussinesq convection)
            "fipy_uniform_upflow": "local:FipyUniformUpflowTransportProcess",  # A (prescribed upflow, no convection)
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
    # The serpentinization source (Model Upgrade plan, priority upgrade A).
    "serpentinization": {
        "face": "serpentinization",
        "models": {
            "phreeqc": "local:PhreeqcSerpentinizationProcess",       # E (real IPhreeqc speciation)
            "reduced": "local:SerpentinizationReproductionProcess",  # E (tuned Gaussian source)
            # planned (same face): "reaktoro", "pflotran" — see the model-upgrade
            # integration doc, Phase 1.
        },
    },
    # Carbon fixation at the mineral interface (Model Upgrade plan, Phase 2).
    "carbon_fixation": {
        "face": "carbon_fixation",
        "models": {
            "empirical": "local:EmpiricalCarbonFixationProcess",          # E (og-01 lab-calibrated kinetics)
            "butler_volmer": "local:ButlerVolmerCarbonFixationProcess",  # A (Nernst + Butler-Volmer circuit)
            "microkinetic": "local:MicrokineticCarbonFixationProcess",   # A (CatMAP/Cantera; runs under pixi)
        },
    },
    # The open chemical network (Model Upgrade plan, Phase 3).
    "proto_metabolism": {
        "face": "proto_metabolism",
        "models": {
            "curated_rtca": "local:RoadRunnerNetworkProcess",        # E (og-02 curated rTCA-fragment SBML)
            "reaction_universe": "local:ReactionUniverseProcess",    # A (rule-generated C/H/O universe, eQuilibrator dG')
            "null_network": "local:NullNetworkProcess",              # A (matched degree-preserving null)
        },
    },
    # The endogenous boundary (Model Upgrade plan, Phase 5). single_chain/mixed
    # are one ProtocellAssemblyProcess selected by mix_fraction (0 vs >0).
    "boundary": {
        "face": "boundary",
        "models": {
            "single_chain": "local:ProtocellAssemblyProcess",            # E (Jordan 2019 fatty-acid vesicle, mix_fraction=0)
            "mixed": "local:ProtocellAssemblyProcess",                   # E (+ co-surfactant, mix_fraction>0)
            "thioester_aminothiol": "local:ThioesterAminothiolMembraneProcess",  # A (different viability window)
        },
    },
}


class FaceError(AssertionError):
    """Raised when a model class does not honour an interface's face."""


# --------------------------------------------------------------------------- #
# Registry queries
# --------------------------------------------------------------------------- #
def interfaces() -> list[str]:
    return sorted(INTERFACES)


def model_names(interface: str) -> list[str]:
    """The registered model-class names on ``interface`` (sorted)."""
    if interface not in INTERFACES:
        raise KeyError(f"unknown interface {interface!r}; have {sorted(INTERFACES)}")
    return sorted(INTERFACES[interface]["models"])


def axis(interface: str, names=None) -> dict[str, list[str]]:
    """A categorical sweep axis for ``interface``: ``{"model_<interface>": [names]}``.

    Pass straight into ``sweep_grid(axes={**axis("spatial_transport"), ...})``.
    """
    names = list(names) if names is not None else model_names(interface)
    for n in names:
        resolve(interface, n)  # validate
    return {MODEL_PARAM_PREFIX + interface: names}


def model_parameters(*interfaces_, defaults=None) -> dict:
    """``@composite_generator(parameters=...)`` entries for the model knobs.

    One string parameter ``model_<interface>`` per interface, listing the
    registered classes in its description, so every generator declares the
    model axis the same way and the workbench renders it as a string param.
    """
    defaults = dict(defaults or {})
    out = {}
    for iface in interfaces_:
        names = model_names(iface)
        default = defaults.get(iface, names[0])
        out[MODEL_PARAM_PREFIX + iface] = {
            "type": "string", "default": default,
            "description": f"Model class behind the {iface!r} face: " + " | ".join(names),
        }
    return out


def split_model_kwargs(kwargs: dict) -> tuple[dict[str, str], dict]:
    """Split generator kwargs into ``({interface: model_name}, other_kwargs)``."""
    models, rest = {}, {}
    for k, v in kwargs.items():
        if k.startswith(MODEL_PARAM_PREFIX) and k[len(MODEL_PARAM_PREFIX):] in INTERFACES:
            models[k[len(MODEL_PARAM_PREFIX):]] = str(v)
        else:
            rest[k] = v
    return models, rest


def register_model(interface: str, name: str, address: str, *, face: str | None = None,
                   face_spec: dict | None = None) -> None:
    """Register a model class on an interface (creating the interface if needed).

    New interfaces need either an existing ``face`` name or a ``face_spec``
    dict in the ``FACES`` shape.
    """
    if interface not in INTERFACES:
        if face_spec is not None:
            FACES[interface if face is None else face] = face_spec
            face = interface if face is None else face
        if face is None or face not in FACES:
            raise KeyError(f"new interface {interface!r} needs a face; have {sorted(FACES)}")
        INTERFACES[interface] = {"face": face, "models": {}}
    INTERFACES[interface]["models"][name] = address


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


def face_ports(face_name: str) -> set[str]:
    face = FACES[face_name]
    return (face["required_inputs"] | face["optional_inputs"]
            | face["required_outputs"] | face["optional_outputs"])


def canonical_coverage(face_name: str) -> dict:
    """Which ports of a face map onto canonical ``vg_*`` fields / declared diagnostics.

    Returns ``{"covered": {port: field}, "uncovered": [ports]}``. The Model
    Upgrade principle requires ``uncovered`` to be empty for every face.
    """
    covered, uncovered = {}, []
    for port in sorted(face_ports(face_name)):
        field = PORT_TO_CANONICAL.get(port)
        if field is None:
            uncovered.append(port)
        else:
            covered[port] = field
    return {"covered": covered, "uncovered": uncovered}


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
