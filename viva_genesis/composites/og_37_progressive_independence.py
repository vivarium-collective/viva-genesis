"""Study 37 (Gate E, optional, terminal) — Progressive Independence.

The final Gate E study: as each environmental support is withdrawn ONE AT A TIME,
which supports can the coupled protocell lineage internalize (persist via an
innovation) and which remain hard dependencies? This is the one-at-a-time rebuild
of og-08 (escape from the vent), which relaxed all supports JOINTLY — a confound
that cannot attribute which innovation rescues which support. By withdrawing each
support alone (holding the others full) and running a matched per-support ablation
(the rescuing innovation switched off → the lineage fails), study 37 resolves the
attribution: a per-support → rescuing-innovation map, with the all-at-once run shown
as the og-08 confound.

It REUSES the validated og-08 machinery verbatim — no parallel ledger, no invented
budget terms:
  * :class:`~viva_genesis.autonomy.off_gradient.EnvironmentalRelaxationProcess`
    relaxes the three support channels, now configured per-channel so only the
    chosen ``withdraw`` channel declines to zero while the others stay at full.
  * :class:`~viva_genesis.autonomy.off_gradient.OffGradientPersistenceProcess` is the
    co-limited (Liebig-minimum) free-energy + resource budget with three toggleable
    innovations — ``pump`` (internal energy conversion; the study-35 carrier),
    ``importer`` (active resource import), ``heredity`` (information maintenance that
    holds the machinery).

**Honest labelling.** The three channels are gradient (↔ the pH / pmf drive),
mineral_access (↔ mineral catalysis) and feed (= H2 + CO2 + organics LUMPED). The
first cut therefore does NOT resolve independence for H2 / CO2 / organics
individually — per-feedstock resolution, plus temperature as an Arrhenius rate
modifier, is the gold-standard follow-on og-37a. The innovations are coarse budget
abstractions, so the result is an affordability / attribution profile, NOT a
demonstrated real-cell escape; heredity is the irreducible substrate (no innovation
replaces it). Terminal study — consumes 34/35/36, extends nothing.

``withdraw`` ∈ {"gradient", "mineral", "feed", "all", "none"}. The sims sweep each
channel one-at-a-time × (full innovation set / rescuing innovation ablated), plus the
all-at-once (og-08) confound and the none baseline.
"""
from __future__ import annotations

from process_bigraph.composite_generator import composite_generator

from ..core import build_core

# Per-channel floors for each withdrawal mode: the withdrawn channel relaxes to 0,
# every other channel is pinned at 1 (floor = start = 1 -> stays full).
_WITHDRAW_FLOORS = {
    "none":     {"g_floor": 1.0, "m_floor": 1.0, "f_floor": 1.0},
    "gradient": {"g_floor": 0.0, "m_floor": 1.0, "f_floor": 1.0},
    "mineral":  {"g_floor": 1.0, "m_floor": 0.0, "f_floor": 1.0},
    "feed":     {"g_floor": 1.0, "m_floor": 1.0, "f_floor": 0.0},
    "all":      {"g_floor": 0.0, "m_floor": 0.0, "f_floor": 0.0},
}

_EMIT_PATHS = [
    "pop/survivors", "pop/lineage_fitness", "pop/machinery_integrity",
    "pop/external_power", "pop/internal_power",
    "env/gradient_support", "env/mineral_access", "env/feed", "global_time",
]


@composite_generator(
    name="og_37_progressive_independence",
    methods=["coarse-grained co-limited free-energy budget (reused from og-08)",
             "per-support one-at-a-time withdrawal (vs og-08's joint relaxation)",
             "matched per-support innovation ablation (causal attribution)"],
    fidelity="reproduction",
    description=(
        "Gate E progressive independence: withdraw each environmental support ONE AT A TIME and ask which "
        "the lineage can internalize (persist via an innovation) vs which are hard dependencies. Reuses the "
        "validated og-08 off-gradient budget (OffGradientPersistenceProcess + EnvironmentalRelaxationProcess) "
        "verbatim — no invented terms — but relaxes a single channel at a time (others held full) instead of "
        "og-08's joint all-at-once relaxation, so a matched per-support ablation (rescuing innovation off -> "
        "fail) attributes each support to its internalizing innovation (gradient->pump, mineral/feed->importer, "
        "all gated by heredity). Channels: gradient (pH/pmf drive), mineral_access (mineral catalysis), feed "
        "(H2+CO2+organics LUMPED — per-feedstock split + temperature-Arrhenius = og-37a). Coarse budget "
        "abstraction = an affordability/attribution profile, NOT a demonstrated escape; heredity = irreducible "
        "substrate. Terminal (consumes 34/35/36, extends nothing)."
    ),
    parameters={
        "withdraw": {"type": "string", "default": "all",
                     "description": "Which support to withdraw one-at-a-time: gradient | mineral | feed | all (og-08 confound) | none (baseline)"},
        "has_pump": {"type": "float", "default": 1.0, "description": "Internal energy-conversion innovation (study-35 carrier); 1 present, 0 knockout"},
        "has_importer": {"type": "float", "default": 1.0, "description": "Active resource-import innovation; 1 present, 0 knockout"},
        "has_heredity": {"type": "float", "default": 1.0, "description": "Information-maintenance innovation (holds machinery); 1 present, 0 knockout"},
        "catalyst_efficiency": {"type": "float", "default": 1.0, "description": "Internal-pump catalytic efficiency (dimensionless) — the pump-affordability knob"},
        "decline_rate": {"type": "float", "default": 0.02, "description": "Support relaxation per step (1/s); the withdrawn channel reaches 0 partway through the run"},
    },
    default_n_steps=60,
    preferred_time="1000 years",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter", "paths": _EMIT_PATHS}],
)
def og_37_progressive_independence(core=None, *, withdraw="all", has_pump=1.0,
                                   has_importer=1.0, has_heredity=1.0,
                                   catalyst_efficiency=1.0, decline_rate=0.02):
    if core is None:
        core = build_core()

    def _tog(v):
        # numeric 0/1 -> "on"/"off": a config schema replaces a falsy 0.0 with its
        # default, so numeric knockouts would read back as present. Strings are preserved.
        return "on" if float(v) >= 0.5 else "off"

    floors = _WITHDRAW_FLOORS.get(str(withdraw), _WITHDRAW_FLOORS["all"])
    return {
        "relax": {
            "_type": "process",
            "address": "local:EnvironmentalRelaxationProcess",
            "config": {"g_start": 1.0, "m_start": 1.0, "f_start": 1.0,
                       "g_floor": floors["g_floor"], "m_floor": floors["m_floor"],
                       "f_floor": floors["f_floor"], "decline_rate": float(decline_rate)},
            "interval": 1.0,
            "inputs": {},
            "outputs": {"gradient_support": ["env", "gradient_support"],
                        "mineral_access": ["env", "mineral_access"],
                        "feed": ["env", "feed"]},
        },
        "lineage": {
            "_type": "process",
            "address": "local:OffGradientPersistenceProcess",
            "config": {"pump": _tog(has_pump), "importer": _tog(has_importer),
                       "heredity": _tog(has_heredity),
                       "catalyst_efficiency": float(catalyst_efficiency)},
            "interval": 1.0,
            "inputs": {"gradient_support": ["env", "gradient_support"],
                       "mineral_access": ["env", "mineral_access"],
                       "feed": ["env", "feed"]},
            "outputs": {"survivors": ["pop", "survivors"],
                        "lineage_fitness": ["pop", "lineage_fitness"],
                        "free_energy_flux": ["pop", "free_energy_flux"],
                        "machinery_integrity": ["pop", "machinery_integrity"],
                        "external_power": ["pop", "external_power"],
                        "internal_power": ["pop", "internal_power"]},
        },
        "env": {"gradient_support": 1.0, "mineral_access": 1.0, "feed": 1.0},
        "pop": {"survivors": 1.0, "lineage_fitness": 0.0, "free_energy_flux": 0.0,
                "machinery_integrity": 1.0, "external_power": 0.0, "internal_power": 0.0},
    }
