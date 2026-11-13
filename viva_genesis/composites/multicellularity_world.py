"""Shared CPM "world" blueprint for the multicellularity campaign (S04-S06).

``build_world_spec`` returns the viva-cpm ``spec`` for a growing clonal cluster of
one cell type; the ``adhesion`` knob in [0, 1] sets the homotypic contact energy.
``s04_morphomechanics`` wires it into a single ``CPMProcess`` whose
``n_propagules`` / ``largest_cluster_fraction`` outputs land in top-level stores
(so a study's ``readouts[].store_path`` can address them).

No heavy import here: the process is addressed by string, so the generator
registers even when viva_cpm is not installed.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from viva_basic_processes.intervention import register_intervention as _register_intervention

from ..core import build_core

CPM_ADDR = "local:!viva_cpm.processes.cpm_process.CPMProcess"

# adhesion -> homotypic contact energy J(1,1), monotonic decreasing:
#     J_hom = J_MIN + (J_MAX - J_MIN) * (1 - adhesion)
# adhesion=1 -> J_MIN (cells much prefer each other: cohesive); adhesion=0 -> J_MAX.
# Medium-cell J(0,1) is fixed. A cluster stays condensed while J_hom < 2*J_MEDIUM
# (cell-cell contact cheaper than exposing two medium faces), so J_MAX > 2*J_MEDIUM
# makes adhesion=0 a true non-adhesive control.
J_MIN = 2.0
J_MAX = 60.0
J_MEDIUM = 12.0

_EMIT_PATHS = [
    "n_propagules", "largest_cluster_fraction", "volumes", "types", "positions",
    "global_time", "fate_counts", "viable_biomass",
]

def register_intervention(core):
    """Register Intervention, then return the core: the library helper returns a bool, which
    apply_core_extensions would otherwise adopt as the core."""
    _register_intervention(core)
    return core


# S05 has no aggregate-cluster reporting, so n_propagules / largest_cluster_fraction do not exist
# there; declaring them makes the workbench runner refuse to build the composite.
_S05_EMIT_PATHS = [p for p in _EMIT_PATHS if p not in ("n_propagules", "largest_cluster_fraction")]


def homotypic_j(adhesion: float) -> float:
    a = min(1.0, max(0.0, float(adhesion)))
    return J_MIN + (J_MAX - J_MIN) * (1.0 - a)


def build_world_spec(*, adhesion, seed_volume=30.0, grow_rate=2.0, divide_threshold=55.0,
                     dims=(80, 40, 1), report_types=(1,), seed=1) -> dict:
    """Shared CPM world spec: one clonal 2x2 cluster of type 1 at the lattice centre and a
    full contact matrix (pure ``load_world`` vocabulary). The ``mitosis`` and
    ``report_aggregate_types`` knobs are CPMProcess config keys, not spec keys; build them
    with :func:`world_process_config`.

    NOTE (transient window): growth-driven fracture is a TRANSIENT, quasi-static readout.
    Measure at ~40 updates (``default_n_steps=40``); beyond ~80 updates crowding re-merges
    clusters and the strong-vs-weak adhesion contrast disappears. Downstream studies must
    pin the readout to this window.
    """
    nx, ny, nz = (int(d) for d in dims)
    side = max(2, int(round(float(seed_volume) ** 0.5)))      # square patch of ~seed_volume sites
    gap = 1
    n = 2
    total = n * side + (n - 1) * gap
    x_start, y_start = (nx - total) // 2, (ny - total) // 2
    cells = []
    for i in range(n):
        for j in range(n):
            x0 = x_start + i * (side + gap)
            y0 = y_start + j * (side + gap)
            cells.append({
                "type": 1, "target_volume": float(seed_volume), "lambda_volume": 2.0,
                "target_surface": 4.0 * side, "lambda_surface": 0.2,
                "seed_block": [x0, y0, 0, x0 + side, y0 + side, nz],
            })
    return {
        "potts": {"dims": [nx, ny, nz], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 8.0, "seed": int(seed)},
        "cells": cells,
        "contact": [
            {"a": 0, "b": 1, "j": J_MEDIUM},                  # medium-cell
            {"a": 1, "b": 1, "j": homotypic_j(adhesion)},     # homotypic (adhesion-controlled)
        ],
    }


def world_process_config(*, adhesion, seed_volume=30.0, grow_rate=2.0, divide_threshold=55.0,
                         dims=(80, 40, 1), report_types=(1,), mcs_per_update=16, seed=1) -> dict:
    """CPMProcess config: the world spec plus the mitosis and aggregate-report knobs."""
    return {
        "spec": build_world_spec(adhesion=adhesion, seed_volume=seed_volume, grow_rate=grow_rate,
                                 divide_threshold=divide_threshold, dims=dims,
                                 report_types=report_types, seed=seed),
        "mcs_per_update": int(mcs_per_update),
        "mitosis": [{"type": 1, "grow_rate": float(grow_rate),
                     "divide_threshold": float(divide_threshold),
                     "reset_target": float(seed_volume)}],
        "report_aggregate_types": [int(t) for t in report_types],
    }


# TRANSIENT WINDOW: the growth-driven fracture this composite shows is a transient,
# quasi-static readout. Measure at ~40 updates (default_n_steps=40); beyond ~80 updates
# crowding re-merges clusters and the contrast disappears. Studies must pin to this window.
@composite_generator(
    name="s04_morphomechanics",
    methods=["Cellular Potts (Glazier-Graner-Hogeweg) clonal growth with differential adhesion"],
    fidelity="spatial_dynamics",
    description=(
        "Multicellularity S04 (morphomechanics). A clonal cell cluster grows and divides on the "
        "Rust CPM engine; the adhesion knob sets homotypic contact energy. Strong adhesion keeps "
        "the cluster one cohesive body; weak adhesion lets growth fracture it into propagules. "
        "Emits n_propagules and largest_cluster_fraction."
    ),
    parameters={
        "adhesion": {"type": "number", "default": 0.8,
                     "description": "cell-cell adhesion in [0,1]; higher = lower homotypic J = cohesive"},
        "grow_rate": {"type": "number", "default": 2.0,
                      "description": "target-volume growth per update per cell"},
        "divide_threshold": {"type": "number", "default": 55.0,
                             "description": "volume at which a cell divides"},
        "seed": {"type": "integer", "default": 1,
                 "description": "Potts RNG seed (vary for replicate runs)"},
    },
    default_n_steps=40,
    core_extensions=[build_core, register_intervention],
    emitters=[{"address": "local:SQLiteEmitter", "paths": _EMIT_PATHS}],
)
def s04_morphomechanics(core=None, *, adhesion=0.8, grow_rate=2.0, divide_threshold=55.0, seed=1):
    config = world_process_config(adhesion=adhesion, grow_rate=grow_rate,
                                  divide_threshold=divide_threshold, seed=seed)
    return {
        "cpm": {
            "_type": "process",
            "address": CPM_ADDR,
            "config": config,
            "interval": 1.0,
            "inputs": {},
            "outputs": {"volumes": ["volumes"], "types": ["types"], "positions": ["positions"],
                        "n_propagules": ["n_propagules"],
                        "largest_cluster_fraction": ["largest_cluster_fraction"]},
        },
    }


# ---------------------------------------------------------------------------
# S05 differentiation: an O2 gradient drives interior cells germ (1) -> soma (2).
# ---------------------------------------------------------------------------
S05_CPM_ADDR = "local:!viva_genesis.s05_process.PreEquilibratedCPMProcess"
SBML_ADDR = "local:!viva_cpm.subcellular.sbml.SBMLSubcell"
BOOL_ADDR = "local:!viva_cpm.subcellular.boolean.BooleanSubcell"

GERM, SOMA = 1, 2

# Stemness S relaxes to S* = k_on*O2/(k_on*O2 + k_off): high O2 -> S~1 (stay germ),
# hypoxia -> S~0 (differentiate).
STEMNESS_O2_MODEL = """
J1: -> S; k_on*O2*(1 - S);
J2: S -> ; k_off*S;
species S, O2;
S = 1.0; O2 = 0.0;
k_on = 1.0; k_off = 1.0;
"""

S05_GRID = 5            # 5x5 = 25 fixed cells
S05_CELL_SIDE = 5
S05_DIMS = (64, 64, 1)
# O2 field (medium source, per-type consumption). d*2*ndim*dt = 0.2*4*1 = 0.8 < 1.
PRE_EQUILIBRATE = 3000
O2_MEDIUM_LEVEL = 2.0   # empirical far-medium O2 equilibrium for the default source/decay
O2_D = 0.2
O2_DECAY = 0.002
O2_SOURCE = 0.02          # medium (type 0) replenishment
O2_CONSUME_GERM = 0.01    # germ draw (R_hi)
O2_CONSUME_SOMA = 0.002   # soma draw (R_lo < R_hi): differentiation frees O2
O2_DYNAMICS = {"dt": 1.0, "substeps": 5}
LIGAND_SCALE = 1.0
STEMNESS_THRESHOLD = 0.4
GROW_RATE = 0.5
GROWTH_O2_THRESHOLD = 0.7
RANDOM_FRACTION = 0.4   # ~ soma fraction the oxygen arm produces at the 40-update window


def s05_world_spec(*, dims=S05_DIMS, grid=S05_GRID, side=S05_CELL_SIDE, seed=1,
                   o2_source=O2_SOURCE, consume_germ=O2_CONSUME_GERM,
                   consume_soma=O2_CONSUME_SOMA) -> dict:
    """Fixed packed grid x grid patch of germ (type 1) cells, centred, plus the O2 field."""
    nx, ny, nz = (int(d) for d in dims)
    total = grid * side + (grid - 1)
    x_start, y_start = (nx - total) // 2, (ny - total) // 2
    vol = float(side * side)
    cells = []
    for i in range(grid):          # cell id = i*grid + j + 1 (seed order)
        for j in range(grid):
            x0 = x_start + i * (side + 1)
            y0 = y_start + j * (side + 1)
            cells.append({
                "type": GERM, "target_volume": vol, "lambda_volume": 2.0,
                "target_surface": 4.0 * side, "lambda_surface": 0.2,
                "seed_block": [x0, y0, 0, x0 + side, y0 + side, nz],
            })
    return {
        "potts": {"dims": [nx, ny, nz], "boundary": "noflux", "neighbor_order": 2,
                  "temperature": 8.0, "seed": int(seed)},
        "cells": cells,
        "contact": [
            {"a": 0, "b": GERM, "j": J_MEDIUM}, {"a": 0, "b": SOMA, "j": J_MEDIUM},
            {"a": GERM, "b": GERM, "j": 4.0}, {"a": GERM, "b": SOMA, "j": 4.0},
            {"a": SOMA, "b": SOMA, "j": 4.0},
        ],
        "fields": [{
            "name": "O2", "d": O2_D, "decay": O2_DECAY,
            "secretion": [{"type": 0, "rate": float(o2_source)},
                          {"type": GERM, "rate": -float(consume_germ)},
                          {"type": SOMA, "rate": -float(consume_soma)}],
            "chemotaxis": [], "dynamics": dict(O2_DYNAMICS),
        }],
    }


def _o2_fate_wiring(state: dict, cell_ids, *, ligand_scale, threshold, **_kw) -> None:
    """Per-cell SBML stemness + Boolean fate subcells (forked from viva-cpm crypt)."""
    for cid in cell_ids:
        state[f"sbml_{cid}"] = {
            "_type": "process", "address": SBML_ADDR,
            "config": {"model": STEMNESS_O2_MODEL, "ligand_species": "O2",
                       "state_species": "S", "ligand_scale": float(ligand_scale)},
            "interval": 1.0,
            "inputs": {"ligand": ["field_at_cell", str(cid)]},
            "outputs": {"state": ["cell_state", str(cid)]},
        }
        state[f"bool_{cid}"] = {
            "_type": "process", "address": BOOL_ADDR,
            # both fate types = soma: any sub-threshold (hypoxic) cell -> type 2
            "config": {"stemness_threshold": float(threshold),
                       "goblet_type": SOMA, "absorptive_type": SOMA},
            "interval": 1.0,
            "inputs": {"state": ["cell_state", str(cid)],
                       "neighbor_secretory": ["neighbor_secretory", str(cid)]},
            "outputs": {"fate": ["fates", str(cid)]},
        }


def _none_fate_wiring(state: dict, cell_ids, **_kw) -> None:
    """Null: no subcells; every cell stays germ (no division of labor)."""


def _random_fate_wiring(state: dict, cell_ids, *, seed=1, random_fraction=RANDOM_FRACTION,
                        **_kw) -> None:
    """Null: no O2-keyed subcells; a random subset is seeded as soma at build time."""
    import random
    cells = state["cpm"]["config"]["spec"]["cells"]
    n = int(round(float(random_fraction) * len(cells)))
    for idx in random.Random(int(seed)).sample(range(len(cells)), n):
        cells[idx]["type"] = SOMA


def _clamped_fate_wiring(state: dict, cell_ids, *, ligand_scale, threshold, **_kw) -> None:
    """Control: full oxygen machinery, but stemness S is clamped to 1.0 so no cell differentiates."""
    from viva_basic_processes.intervention import intervention_node
    _o2_fate_wiring(state, cell_ids, ligand_scale=ligand_scale, threshold=threshold)
    for cid in cell_ids:
        # The SBML step *overwrites* cell_state while the Intervention emits an additive delta, so
        # both writing one store gives a 0/1 flip-flop. Divert the free ODE trajectory to its own
        # store; the Boolean gate then reads only the clamped cell_state (held at 1.0).
        state[f"sbml_{cid}"]["outputs"]["state"] = ["cell_state_free", str(cid)]
        state[f"clamp_{cid}"] = intervention_node(["cell_state", str(cid)], mode="set", value=1.0)


_FATE_MODES = {"oxygen": _o2_fate_wiring, "none": _none_fate_wiring,
               "random": _random_fate_wiring, "clamped": _clamped_fate_wiring}


@composite_generator(
    name="s05_differentiation",
    methods=["Cellular Potts patch with O2 diffusion/consumption; SBML stemness ODE + Boolean fate gate"],
    fidelity="spatial_dynamics",
    description=(
        "Multicellularity S05 (differentiation). A fixed 5x5 patch of germ cells consumes O2 that "
        "diffuses in from the medium; interior cells go hypoxic, their stemness ODE decays and they "
        "differentiate to soma (type 2), which draws less O2. Germ cells grow only where local O2 is "
        "above a threshold. Emits fate_counts and viable_biomass. TRANSIENT/quasi-stable gradient: "
        "the O2 profile relaxes during the first updates; readouts are taken at the pinned window."
    ),
    parameters={
        "fate_mode": {"type": "string", "default": "oxygen",
                      "description": "oxygen | none | random | clamped"},
        "random_fraction": {"type": "number", "default": RANDOM_FRACTION,
                            "description": "random arm: fraction of cells seeded as soma"},
        "o2_source": {"type": "number", "default": O2_SOURCE, "description": "medium O2 source rate"},
        "consume_germ": {"type": "number", "default": O2_CONSUME_GERM, "description": "germ O2 draw"},
        "consume_soma": {"type": "number", "default": O2_CONSUME_SOMA, "description": "soma O2 draw"},
        "grow_rate": {"type": "number", "default": GROW_RATE,
                      "description": "germ target-volume growth per update where O2 >= threshold"},
        "seed": {"type": "integer", "default": 1, "description": "Potts RNG seed"},
    },
    default_n_steps=40,
    core_extensions=[build_core, register_intervention],
    emitters=[{"address": "local:SQLiteEmitter", "paths": _S05_EMIT_PATHS}],
)
def s05_differentiation(core=None, *, fate_mode="oxygen", o2_source=O2_SOURCE,
                        consume_germ=O2_CONSUME_GERM, consume_soma=O2_CONSUME_SOMA,
                        grow_rate=GROW_RATE, seed=1, random_fraction=RANDOM_FRACTION):
    if fate_mode not in _FATE_MODES:
        raise ValueError(f"fate_mode {fate_mode!r} not implemented; have {sorted(_FATE_MODES)}")
    spec = s05_world_spec(seed=seed, o2_source=o2_source, consume_germ=consume_germ,
                          consume_soma=consume_soma)
    cell_ids = list(range(1, len(spec["cells"]) + 1))
    state = {
        "fates": {str(cid): 0 for cid in cell_ids},
        # Seed the field readout at the medium O2 level: the subcells step before the CPM has
        # published anything, and a 0 ligand on that first step would crash S below threshold
        # and differentiate every cell regardless of the gradient.
        # likewise the Boolean gate reads cell_state before the ODE has written it (default 0.0)
        "cell_state": {str(cid): 1.0 for cid in cell_ids},
        "field_at_cell": {str(cid): float(O2_MEDIUM_LEVEL) for cid in cell_ids},
        "cpm": {
            "_type": "process", "address": S05_CPM_ADDR,
            "config": {
                "pre_equilibrate": PRE_EQUILIBRATE,
                "spec": spec, "mcs_per_update": 8, "n_fields": 1,
                "report_fate_growth": True,
                # no divide_threshold / reset_target -> no division, ids stay fixed
                "mitosis": [{"type": GERM, "grow_rate": float(grow_rate),
                             "o2_gate": {"field": 0, "threshold": GROWTH_O2_THRESHOLD}}],
            },
            "interval": 1.0,
            "inputs": {"fates": ["fates"]},
            "outputs": {"volumes": ["volumes"], "types": ["types"], "positions": ["positions"],
                        "field_at_cell": ["field_at_cell"],
                        "neighbor_secretory": ["neighbor_secretory"],
                        "fate_counts": ["fate_counts"], "viable_biomass": ["viable_biomass"]},
        },
    }
    _FATE_MODES[fate_mode](state, cell_ids, ligand_scale=LIGAND_SCALE, threshold=STEMNESS_THRESHOLD,
                           seed=seed, random_fraction=random_fraction)
    return state


def group_partition(world, founder_types):
    """Pure read-out of per-founder group traits for the S06 Price partition.

    Founder identity is the CELL TYPE (division preserves it). Returns
    ``{f: {toughness, n_cells, volume}}`` per founder plus ``"by_cell_type"``
    over every live non-medium type (exposes cheater sub-lineages).
    """
    from viva_cpm import metrics

    by_type: dict = {}
    for t, v in zip(world.cell_types()[1:], world.cell_volumes()[1:]):
        if v <= 0:
            continue
        e = by_type.setdefault(t, {"n_cells": 0, "volume": 0.0})
        e["n_cells"] += 1
        e["volume"] += float(v)
    out: dict = {}
    for f in founder_types:
        e = by_type.get(f, {"n_cells": 0, "volume": 0.0})
        out[f] = {"toughness": metrics.largest_cluster_fraction(world, [f]),
                  "n_cells": e["n_cells"], "volume": e["volume"]}
    out["by_cell_type"] = by_type
    return out
