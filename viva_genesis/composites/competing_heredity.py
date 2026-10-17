"""Competing heredity — og-06's lineage behind the heredity face (Phase 7).

One layer generator, six model classes selected through the typed face
``viva_genesis.models.INTERFACES["heredity"]`` (``model_heredity``:
compositional | network | peptide | rna_like | hybrid | mineral_state), all
simulated by the same exact Gillespie lineage at low copy number
(``viva_genesis.heredity.competing``) under **matched budgets**: one shared
dissolved pool of precursors (nucleotide / amino / amphiphile / mineral
growth units, each chemostat-fed by ``BudgetFeedProcess``) and one shared
energy store (``stored_work``, fed at a fixed power), from which every class
draws integer molecules and quanta per copy.

Heredity is **attached conditionally** (FMP §2.5) by ``HeredityAttachmentStep``:
until the class's precursor budget, energy budget and expected copy fidelity
(Eigen's ``Q >= 1/sigma``) cross their thresholds, daughters re-form their
heritable material de novo — og-06's non-heritable control is the unattached
state of every class. ``attachment`` can force the flag ``on`` / ``off`` for
the frontier and control arms.

``InformationLedgerProcess`` prices what each class transmits: parent→offspring
mutual information (net of its permutation null, with the estimator's
convergence flag) per joule and per precursor molecule spent per offspring,
and audits the energy store exactly.
"""

from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .. import models
from ..heredity.competing import DEFAULTS, POOLS

_SENSORS = ("mean_function", "functional_fraction", "population", "lineage_depth", "heritability", "fidelity",
            "mutation_rate", "mean_molecules", "n_attached")
_INFO = ("information_content", "information_capacity", "mi_converged", "mi_standard_error")
_COSTS = ("replication_energy", "quanta_used", "precursors_consumed", "precursor_energy", "copies", "births")
_LEDGER = ("heritable_bits", "energy_per_offspring", "precursors_per_offspring", "bits_per_joule",
           "bits_per_precursor", "energy_in", "energy_used", "energy_residual", "information_ledger_ok")
_ATTACH = ("attached", "attachment_margin", "fidelity_floor")

_WIRES = {
    **{p: ["pool", p] for p in POOLS},
    "stored_work": ["energy", "stored_work"], "work_flux": ["energy", "work_flux"],
    **{k: ["heredity", k] for k in _ATTACH},
    **{k: ["lineage", k] for k in _SENSORS},
    **{k: ["info", k] for k in _INFO},
    **{k: ["cost", k] for k in _COSTS},
    **{k: ["ledger", k] for k in _LEDGER},
    "global_time": ["global_time"],
}
_EMIT_PATHS = ["/".join(v) for v in _WIRES.values()]


@composite_generator(
    name="competing_heredity",
    methods=["exact Gillespie SSA at low copy number", "conditional heredity attachment (FMP 2.5)",
             "parent-offspring mutual information with convergence check", "information-per-cost ledger"],
    fidelity="real",
    description=(
        "og-06's heredity lineage rebuilt as the Phase-7 competing-heredity composite: the inheritance "
        "mechanism is a model CLASS on the heredity face (model_heredity: compositional | network | peptide | "
        "rna_like | hybrid | mineral_state), every class an exact Gillespie lineage of protocell-scale "
        "individuals (tens of heritable molecules each) drawing integer precursors and energy quanta from the "
        "SAME chemostat-fed pools and energy store. HeredityAttachmentStep attaches heredity only when the "
        "precursor budget, the energy budget and the class's expected copy fidelity (Eigen Q >= 1/sigma) allow "
        "it — before that, daughters re-form their heritable material de novo (the non-heritable control). "
        "InformationLedgerProcess prices the realised parent-offspring mutual information per joule and per "
        "precursor and audits the energy store exactly."
    ),
    parameters={
        **models.model_parameters("heredity", defaults={"heredity": "rna_like"}),
        "attachment": {"type": "string", "default": "step",
                       "description": "step = HeredityAttachmentStep decides; on = heredity forced attached; off = non-heritable control"},
        "nucleotide_feed": {"type": "float", "default": DEFAULTS["nominal_feed"],
                            "description": "Activated-nucleotide feed set-point (M) [vg-data: hypothetical]"},
        "amino_feed": {"type": "float", "default": DEFAULTS["nominal_feed"],
                       "description": "Activated amino-acid feed set-point (M) [vg-data: extrapolated]"},
        "amphiphile_feed": {"type": "float", "default": DEFAULTS["nominal_feed"],
                            "description": "Amphiphile feed set-point (M) [vg-data: inferred]"},
        "mineral_feed": {"type": "float", "default": DEFAULTS["nominal_feed"],
                         "description": "Mineral growth-unit feed set-point (M) [vg-data: hypothetical]"},
        "power": {"type": "float", "default": 8.0e-16, "description": "Energy supply to the shared store (J per tick) [vg-data: hypothetical]"},
        "per_site_fidelity": {"type": "float", "default": DEFAULTS["per_site_fidelity"],
                              "description": "Template per-site copy fidelity q (rna_like / hybrid) [vg-data: measured, Johnston 2001]"},
        "peptide_fidelity": {"type": "float", "default": DEFAULTS["peptide_fidelity"],
                             "description": "Peptide per-site templating fidelity q_p [vg-data: hypothetical]"},
        "defect_copy_error": {"type": "float", "default": DEFAULTS["defect_copy_error"],
                              "description": "Mineral per-bit defect copy error per layer p_m [vg-data: hypothetical]"},
        "attach_min_copies": {"type": "float", "default": DEFAULTS["attach_min_copies"],
                              "description": "Attachment threshold: copies per individual the budget must cover [vg-data: hypothetical, swept]"},
        "attach_energy_margin": {"type": "float", "default": DEFAULTS["attach_energy_margin"],
                                 "description": "Attachment threshold: energy-budget margin [vg-data: hypothetical, swept]"},
        "n_individuals": {"type": "integer", "default": DEFAULTS["n_individuals"], "description": "Lineage capacity (individuals)"},
        "seed": {"type": "integer", "default": 1, "description": "RNG seed (reproducible SSA)"},
    },
    default_n_steps=60,
    preferred_time="60 generations",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def competing_heredity(core=None, *, model_heredity="rna_like", attachment="step",
                       nucleotide_feed=DEFAULTS["nominal_feed"], amino_feed=DEFAULTS["nominal_feed"],
                       amphiphile_feed=DEFAULTS["nominal_feed"], mineral_feed=DEFAULTS["nominal_feed"],
                       power=8.0e-16, per_site_fidelity=DEFAULTS["per_site_fidelity"],
                       peptide_fidelity=DEFAULTS["peptide_fidelity"], defect_copy_error=DEFAULTS["defect_copy_error"],
                       attach_min_copies=DEFAULTS["attach_min_copies"], attach_energy_margin=DEFAULTS["attach_energy_margin"],
                       n_individuals=DEFAULTS["n_individuals"], seed=1):
    if core is None:
        core = build_core()
    address = models.resolve_checked(core, "heredity", model_heredity)
    if attachment not in ("step", "on", "off"):
        raise ValueError(f"attachment must be step | on | off, got {attachment!r}")

    feeds = {"nucleotide_precursor": float(nucleotide_feed), "amino_precursor": float(amino_feed),
             "amphiphile": float(amphiphile_feed), "mineral_precursor": float(mineral_feed)}
    class_cfg = {"seed": int(seed), "n_individuals": int(n_individuals), "per_site_fidelity": float(per_site_fidelity),
                 "peptide_fidelity": float(peptide_fidelity), "defect_copy_error": float(defect_copy_error),
                 "nominal_feed": float(DEFAULTS["nominal_feed"])}
    w0 = float(power)
    doc = {
        "heredity_class": {
            "_type": "process", "address": address, "config": class_cfg, "interval": 1.0,
            "inputs": {"temperature": ["env", "temperature"], "attached": ["heredity", "attached"],
                       "stored_work": ["energy", "stored_work"], **{p: ["pool", p] for p in POOLS}},
            "outputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["energy", "stored_work"],
                        **{k: ["lineage", k] for k in _SENSORS}, **{k: ["info", k] for k in _INFO},
                        **{k: ["cost", k] for k in _COSTS}},
        },
        "budget_feed": {
            "_type": "process", "address": "local:BudgetFeedProcess",
            "config": {**{f"{p}_feed": feeds[p] for p in POOLS}, "power": w0, "max_stored_work": w0},
            "interval": 1.0,
            "inputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["energy", "stored_work"]},
            "outputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["energy", "stored_work"],
                        "work_flux": ["energy", "work_flux"]},
        },
        "information_ledger": {
            "_type": "process", "address": "local:InformationLedgerProcess", "config": {}, "interval": 1.0,
            "inputs": {"information_content": ["info", "information_content"], "mi_converged": ["info", "mi_converged"],
                       "replication_energy": ["cost", "replication_energy"], "precursor_energy": ["cost", "precursor_energy"],
                       "precursors_consumed": ["cost", "precursors_consumed"], "births": ["cost", "births"],
                       "stored_work": ["energy", "stored_work"], "work_flux": ["energy", "work_flux"]},
            "outputs": {k: ["ledger", k] for k in _LEDGER},
        },
        "env": {"temperature": 353.15},
        "pool": dict(feeds),
        "energy": {"stored_work": w0, "work_flux": 0.0},
        "heredity": {"attached": 1.0 if attachment == "on" else 0.0, "attachment_margin": 0.0, "fidelity_floor": 0.0},
        "lineage": {k: 0.0 for k in _SENSORS},
        "info": {k: 0.0 for k in _INFO},
        "cost": {k: 0.0 for k in _COSTS},
        "ledger": {k: 0.0 for k in _LEDGER},
        "emitter": {
            "_type": "step", "address": "local:RAMEmitter",
            "config": {"emit": {k: "float" for k in _WIRES}},
            "inputs": {k: list(v) for k, v in _WIRES.items()},
        },
    }
    if attachment == "step":
        doc["heredity_attachment"] = {
            "_type": "step", "address": "local:HeredityAttachmentStep",
            "config": {"heredity_class": model_heredity, "attach_min_copies": float(attach_min_copies),
                       "attach_energy_margin": float(attach_energy_margin), "n_individuals": int(n_individuals),
                       "per_site_fidelity": float(per_site_fidelity), "peptide_fidelity": float(peptide_fidelity),
                       "defect_copy_error": float(defect_copy_error)},
            "inputs": {**{p: ["pool", p] for p in POOLS}, "stored_work": ["energy", "stored_work"]},
            "outputs": {k: ["heredity", k] for k in _ATTACH},
        }
    return doc


# --------------------------------------------------------------------------- #
# Reducers (module-level, picklable)
# --------------------------------------------------------------------------- #
def _last(rows, key):
    return float(rows[-1].get(key, float("nan"))) if rows else float("nan")


def final_heritable_bits(rows) -> float:
    return _last(rows, "information_content")


def final_mi_converged(rows) -> float:
    return _last(rows, "mi_converged")


def final_bits_per_joule(rows) -> float:
    return _last(rows, "bits_per_joule")


def final_energy_per_offspring(rows) -> float:
    return _last(rows, "energy_per_offspring")


def attached_fraction(rows) -> float:
    """Fraction of ticks on which heredity was attached."""
    if not rows:
        return float("nan")
    return sum(float(r.get("attached", 0.0)) >= 0.5 for r in rows) / len(rows)


def settled_mean_function(rows, frac=0.25) -> float:
    n = max(1, int(round(len(rows) * frac)))
    t = [float(r.get("mean_function", float("nan"))) for r in rows[-n:]]
    return sum(t) / len(t) if t else float("nan")


def final_heritability(rows) -> float:
    return _last(rows, "heritability")


def information_ledger_ok_final(rows) -> float:
    return _last(rows, "information_ledger_ok")


PHASE7_REDUCERS = {
    "heritable_bits": final_heritable_bits, "mi_converged": final_mi_converged,
    "bits_per_joule": final_bits_per_joule, "energy_per_offspring": final_energy_per_offspring,
    "attached_fraction": attached_fraction, "settled_mean_function": settled_mean_function,
    "heritability": final_heritability, "information_ledger_ok": information_ledger_ok_final,
}

__all__ = ["competing_heredity", "PHASE7_REDUCERS"]
