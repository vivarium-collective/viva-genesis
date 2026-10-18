"""Study 32 — First Self-Maintaining Protocell (full Gate C, Option B: MD-INFORMED).

Couples the sustained A1 carbon-fixing network (the Gate-B pore-concentrated og-30
reaction universe) to an endogenous membrane whose permeability is INFORMED BY SHORT
MARTINI CG-MD of the amphiphile composition — a tighter coupling than og-31's reduced
retention/access proxy, but explicitly **MD-INFORMED (structural-proxy), NOT a
PMF-resolved permeability**. The full PMF+diffusion closure (the real viva-md-membrane
wrapper) is Option A, a compute-budgeted follow-on (study og-32a).

**The MD (real).** ``sims/run_md_bilayer_observables.py`` ran short Martini 3 CG-MD
(viva-openmm / martini_openmm, on the mini) of two saturated-lipid bilayers that stand
in for og-17's fatty-acid C2-elongation axis (chain length; CAC falls as chains grow,
so only the long-enough-chain pool is aggregation-competent):

    DLPC (di-C12, 3 tail beads/chain, SHORT): bilayer thickness 2.325 nm
    DPPC (di-C16, 4 tail beads/chain, LONG):  bilayer thickness 2.870 nm

Bilayer thickness is the composition-responsive structural observable (longer tail ->
thicker, more-ordered core); area-per-lipid was held by the NVT box and is not used.

**Composition -> permeability -> retention (the MD-informed coupling).** A published
solubility-diffusion picture makes permeability fall as the hydrophobic core thickens
(a higher permeation barrier): ``P_eff = P0 * exp(-(d - d0)/lambda)``. The retained
fraction rises as permeability falls: ``retention = 1 / (1 + P_eff/P_half)``. The
relation CONSTANTS (P0, d0, lambda, P_half) are a labelled model proxy — recorded as a
``proposed_input`` on the investigation, pending calibration to a measured
composition-resolved permeability dataset at vent conditions (an open expert question),
**not asserted as validated**. Only the SHAPE (monotone-decreasing, solubility-diffusion)
is claimed. The metabolism's aggregation-competent product is the LONG chain pool, so the
``membrane`` arm uses the long (DPPC) thickness; the short (DLPC) point is the sensitivity
boundary.

retention sets effective washout: ``k_wash_eff = k_wash * (1 - retention)`` — lower
permeability -> higher retention -> lower washout -> larger standing pool. External feeds
are held EQUAL across arms (the matched-null standard); only the membrane differs.

``membrane=False`` is the matched ablation: permeability fixed OPEN (retention 0, full
washout), equal external feeds — the no-endogenous-membrane control.

Guardrail: the enclosed metabolism is the sustained A1 carbon-fixing network, NOT
autocatalytic (A2 is refuted under vent conditions). The claim under test is that a
persisting network can build and keep a membrane that pays its way — never that the
chemistry self-amplifies. Membrane integrity (net amphiphile production vs degradation)
and the Gate-C benefit-vs-ablation verdict are computed in
``sims/compute_gate_c_full.py`` from this composite's outputs.
"""
from __future__ import annotations

import math

from process_bigraph.composite_generator import composite_generator

from ..core import build_core
from .og_30_spatially_integrated_protometabolism import og_30_spatially_integrated_protometabolism

# --- MD observables (REAL short Martini CG-MD, mini; sims/run_md_bilayer_observables.py) --- #
# bilayer thickness [nm] per composition; the long pool is aggregation-competent (og-17 CAC).
MD_THICKNESS_NM = {"short_di-C12": 2.325, "long_di-C16": 2.870}
_DEFAULT_COMPOSITION = "long_di-C16"

# --- Published solubility-diffusion structure->permeability relation (PROPOSED_INPUT). ---- #
# P_eff = P0 * exp(-(d - d0)/lambda); thicker core -> higher barrier -> lower permeability.
# Constants are a labelled proxy pending calibration to a measured permeability dataset
# (investigation proposed_input og32-md-permeability-relation); only the monotone SHAPE is claimed.
_PERM_P0 = 1.0          # reference permeability (relative units) at d0
_PERM_D0_NM = 2.325     # reference thickness = the short (DLPC) composition
_PERM_LAMBDA_NM = 0.40  # barrier decay length [nm]
_RET_P_HALF = 0.5       # permeability at which retention = 0.5 (relative units)


def md_informed_permeability(thickness_nm: float) -> float:
    """Effective permeability (relative units) from MD bilayer thickness (Option B proxy)."""
    return _PERM_P0 * math.exp(-(float(thickness_nm) - _PERM_D0_NM) / _PERM_LAMBDA_NM)


def permeability_to_retention(p_eff: float) -> float:
    """Retained metabolite fraction from permeability — monotone-decreasing, bounded [0,1)."""
    return 1.0 / (1.0 + float(p_eff) / _RET_P_HALF)


def composition_retention(composition: str = _DEFAULT_COMPOSITION) -> tuple[float, float, float]:
    """(thickness_nm, permeability, retention) for a named MD composition."""
    d = MD_THICKNESS_NM[composition]
    p = md_informed_permeability(d)
    return d, p, permeability_to_retention(p)


@composite_generator(
    name="og_32_first_self_maintaining_protocell",
    methods=["MD-informed membrane permeability (short Martini CG-MD structural proxy)",
             "Gate-B pore-concentrated A1 reaction universe", "permeability-gated metabolite retention",
             "matched no-endogenous-membrane ablation (permeability open, equal feeds)"],
    fidelity="real",
    description=(
        "Full Gate C (Option B, MD-INFORMED not PMF-resolved): couples the sustained A1 carbon-fixing "
        "network (Gate-B pore) to an endogenous membrane whose permeability is INFORMED BY short Martini "
        "CG-MD of the amphiphile composition (bilayer thickness: DLPC/di-C12 2.325 nm vs DPPC/di-C16 "
        "2.870 nm). A solubility-diffusion relation (proposed_input) maps thickness->permeability->retention "
        "(thicker long-chain membrane retains more); retention lowers effective washout (k_wash*(1-retention)) "
        "at feeds held EQUAL to the ablation. membrane=False is the matched no-endogenous-membrane control "
        "(permeability open, retention 0). Metabolism = sustained A1 network, NOT autocatalytic (A2 refuted). "
        "Full PMF-resolved permeability is Option A (study og-32a, budgeted follow-on)."
    ),
    parameters={
        "membrane": {"type": "boolean", "default": True,
                     "description": "Endogenous membrane (True) vs matched no-membrane ablation (False)"},
        "composition": {"type": "string", "default": _DEFAULT_COMPOSITION,
                        "description": "MD amphiphile composition (long_di-C16 = aggregation-competent pool)"},
        "base_CO2": {"type": "float", "default": 1.0e-3, "description": "Bulk precursor CO2 (molar) — equal across arms"},
        "base_H2": {"type": "float", "default": 1.0e-3, "description": "Bulk precursor H2 (molar) — equal across arms"},
        "porosity": {"type": "float", "default": 0.88, "description": "Gate-B pore porosity (0.88 = demo pore)"},
        "k_wash": {"type": "float", "default": 0.05, "description": "Base CSTR washout (1/s) before retention"},
        "max_carbons": {"type": "integer", "default": 4, "description": "Carbon cap of the reaction universe"},
    },
    default_n_steps=90,
    preferred_time="6 hours",
    core_extensions=[build_core],
    emitters=[{"address": "local:ParquetEmitter",
               "paths": ["flux/net_carbon_flux", "net/total_organic_carbon",
                         "stats/n_persistent_species", "flux/network_connected"]}],
)
def og_32_first_self_maintaining_protocell(
        core=None, *, membrane=True, composition=_DEFAULT_COMPOSITION,
        base_CO2=1.0e-3, base_H2=1.0e-3, porosity=0.88, k_wash=0.05, max_carbons=4):
    if core is None:
        core = build_core()
    # MD-informed retention from the amphiphile composition; ablation = permeability open (retention 0).
    if membrane:
        _d, _p, retention = composition_retention(composition)
    else:
        retention = 0.0
    eff_k_wash = float(k_wash) * (1.0 - float(retention))
    # Feeds held EQUAL across arms (matched-null standard); only washout differs via retention.
    return og_30_spatially_integrated_protometabolism(
        core, concentrating=True, base_CO2=float(base_CO2), base_H2=float(base_H2),
        porosity=float(porosity), k_wash=eff_k_wash, max_carbons=int(max_carbons))
