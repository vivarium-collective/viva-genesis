"""Butler-Volmer carbon fixation — the vent wall as a galvanic cell (Phase 2).

Model Upgrade plan, Phase 2 (*electrochemical carbon fixation*): replace og-01's
scalar ``gradient_efficiency`` with explicit electrochemistry, so that *which*
limitation stops carbon fixation — thermodynamic, electrical, catalytic or
transport — is a result rather than a parameter. This is the fast primary class
(the plan's decision: Butler-Volmer first; CatMAP/Cantera microkinetics as the
deferred conda class).

The chain, every tick, is **fluid redox → electrode potentials → overpotentials
→ current density → surface rates**:

1. **Fluid redox (Nernst).** The alkaline, H2-rich vent fluid is the anode
   (H2 → 2 H+ + 2 e−); the acidic, CO2-bearing ocean side is the cathode
   (CO2 + 2 H+ + 2 e− → HCOOH, E0 = −0.199 V vs SHE). Dissolved H2 / CO2 are
   converted to activities through temperature-dependent Henry constants and
   formic acid is speciated against its pKa (3.75), so product accumulation
   raises the cathode's equilibrium potential back toward the anode's — the
   thermodynamic shut-off is a Nernst statement, not a yield cap. A competing
   hydrogen-evolution branch (2 H+ + 2 e− → H2) runs at the same cathode.
2. **Electrode kinetics (Butler-Volmer).** Each branch carries
   ``j = j0 [exp(αa f η) − exp(−αc f η)]`` with ``f = F/RT``; the exchange
   current densities scale with the catalyst activity, the Ni fraction of the
   Fe/Ni phase (Preiner-2020 awaruite > magnetite > greigite hierarchy) and an
   Arrhenius factor. Mass transport to each electrode enters as a limiting
   current (``j_lim = n F D c / δ``) combined Koutecký-Levich style, so the
   kinetic and transport overpotentials are separable.
3. **The circuit.** The mineral layer (thickness ``L``, electronic conductivity
   ``σ``) is the external circuit (areal resistance ``L/σ``); the pore fluid is
   the ionic return path (Bruggeman ``σ_f φ^1.5``). The cell current is the root
   of ``E_cathode(j) − E_anode(j) − j (R_e + R_ion) = 0`` — a monotone scalar
   equation solved by Brent's method. No spontaneous current (mixed cathode
   potential below the anode's) is the thermodynamic limitation.
4. **Surface rates.** The CO2-reduction share of the current (the faradaic
   efficiency) is split over formate (2 e−), acetate (8 e−) and pyruvate
   (10 e−) with electron branch fractions calibrated to the Preiner-2020 yield
   hierarchy (Ni raises the C2/C3 share); product increments are additive
   deltas on the dissolved pool with the same open-flow washout as og-01.

Calibration. The exchange-current defaults put the nominal operating point
(pH 9.5 | 6.0, 5 mM H2, 2 mM CO2, 100 °C, σ = 1e-3 S/m, L = 1 mm, Ni3Fe)
inside the current window the campaign dossier records for the Altair-2025
reactor (~10 nA to 10 µA on a cm²-scale interface, i.e. 1e-5 .. 1e-2 A/m²;
``vg-data`` package ``electrochemical_interface``). They are classed
``calibrated``; the branch fractions ``inferred`` from Preiner; the Ni gain and
the ocean-side H2 ``hypothetical``.

Failure-mode attribution. The ideal driving force is the emf at trace product
(fresh fluid). Each tick the class partitions it: the part lost to product
back-pressure (thermodynamic), the ohmic drop (electrical), the kinetic
activation overpotentials (catalytic) and the concentration overpotentials
(transport) — four fractions that sum to one while current flows, published as
``loss_*`` with the dominant one as ``limitation_code`` (a cathode that sends
most electrons to H2 is catalytic — selectivity — limited). The ``empirical``
class publishes the same four ports from its gating factors, which is what
lets the Phase-2 gate ask whether the classes agree on the label.

Verification. ``iv_residual`` is the circuit equation's residual at the root;
``electron_flux``, ``carbon_electron_flux`` and ``her_electron_flux`` are the
anode-side and the two cathode-branch electron rates, which the
:class:`~viva_genesis.ledger.ChargeLedgerProcess` checks for Kirchhoff balance
and faradaic efficiency ≤ 1 every tick.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from process_bigraph import Process

F = 96485.33212        # C/mol
R = 8.314462618        # J/mol/K
LN10 = math.log(10.0)

# Henry constants (mol/L/bar at 298.15 K) and their van 't Hoff slopes (K);
# Sander 2015 compilation values.
KH_H2_298, DLNKH_H2 = 7.8e-4, 500.0
KH_CO2_298, DLNKH_CO2 = 3.4e-2, 2400.0
E0_CO2_HCOOH = -0.199   # V vs SHE at pH 0, 25 C (CO2 + 2H+ + 2e- -> HCOOH)
PKA_FORMIC = 3.75
T_REF = 373.15          # K — the og-01 / Preiner operating temperature

# Electrons per product molecule from CO2 (formate C+2, acetate C0, pyruvate C+2/3)
N_ELECTRONS = {"formate": 2.0, "acetate": 8.0, "pyruvate": 10.0}
CARBONS = {"formate": 1.0, "acetate": 2.0, "pyruvate": 3.0}

LIMITATION_CODES = {"thermodynamic": 0, "electrical": 1, "catalytic": 2, "transport": 3}
LIMITATION_NAMES = {v: k for k, v in LIMITATION_CODES.items()}

_MOLAR = {"_type": "float", "_units": "molar"}
_K = {"_type": "float", "_units": "kelvin"}
_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_SM = {"_type": "float", "_units": "siemens/meter"}
_M = {"_type": "float", "_units": "meter"}
_OVW = {"_type": "overwrite[float]", "_units": "dimensionless"}


def henry(T: float, kh298: float, dlnk: float) -> float:
    """Henry constant (mol/L/bar) at ``T`` from its 298 K value and van 't Hoff slope."""
    return kh298 * math.exp(dlnk * (1.0 / T - 1.0 / 298.15))


def ni_activity_gain(ni_fraction: float, gain: float) -> float:
    """Relative CO2-reduction exchange current of an Fe/Ni phase with Ni mole fraction ``x``.

    ``(1 + gain x)``: a linear gain over the Fe-only phase, normalised by the
    caller to its reference composition (Ni3Fe, x = 0.75). Hypothetical shape;
    the ordering (awaruite > magnetite/greigite) is Preiner 2020's.
    """
    return 1.0 + max(gain, 0.0) * min(max(ni_fraction, 0.0), 1.0)


def limitation_label(losses: dict, faradaic_efficiency: float = 1.0) -> str:
    """The dominant limitation: the largest loss fraction, with the selectivity rule.

    A cathode that sends most of its electrons to hydrogen evolution
    (``faradaic_efficiency < 0.5``) is catalytically (selectivity) limited
    whatever the overpotential split says.
    """
    if faradaic_efficiency < 0.5 and losses.get("thermodynamic", 0.0) < 1.0:
        return "catalytic"
    best, best_v = "thermodynamic", -1.0
    for name in ("thermodynamic", "electrical", "catalytic", "transport"):
        v = float(losses.get(name, 0.0))
        if v > best_v:
            best, best_v = name, v
    return best


# --------------------------------------------------------------------------- #
# Pure electrochemistry (no process-bigraph state) — used by the process, the
# conductivity circuit, the tests and the polarization-curve visualization.
# --------------------------------------------------------------------------- #
@dataclass
class CellSolution:
    """One steady galvanic-cell solve."""

    emf: float                   # E_eq,cathode(CO2/HCOOH) - E_eq,anode(H2) at the current product level (V)
    emf_fresh: float             # the same at trace product: the ideal driving force (V)
    e_anode_eq: float
    e_cathode_eq: float
    e_her_eq: float
    j: float                     # cell current density (A/m^2), >= 0
    e_anode: float               # anode potential under load (V)
    e_cathode: float             # cathode (mixed) potential under load (V)
    eta_anode: float             # anode overpotential (V, >= 0)
    eta_cathode: float           # cathode overpotential vs the CO2/HCOOH couple (V, >= 0 when reducing)
    eta_anode_kinetic: float     # ... the kinetic (activation) part
    eta_cathode_kinetic: float
    ohmic_drop: float            # j (R_e + R_ion) (V)
    j_co2: float                 # CO2-reduction current density (A/m^2)
    j_her: float                 # hydrogen-evolution current density (A/m^2)
    j_her_reverse: float         # local oxidation of ocean-side trace H2 at the cathode (A/m^2)
    faradaic_efficiency: float   # j_co2 / (j + j_her_reverse)
    iv_residual: float           # |E_c - E_a - j R| / max(emf_fresh, eps)
    losses: dict                 # thermodynamic / electrical / catalytic / transport fractions of emf_fresh
    limitation: str
    j_lim_anode: float
    j_lim_co2: float
    j_lim_her: float

    def to_dict(self) -> dict:
        return asdict(self)


def equilibrium_potentials(T, pH_vent, pH_ocean, h2, co2, formate, h2_ocean):
    """Nernst potentials (V vs SHE): anode H2/H+, cathode CO2/HCOOH, cathode H+/H2."""
    rt_f = R * T / F
    a_h2 = max(h2, 1e-30) / henry(T, KH_H2_298, DLNKH_H2)
    a_co2 = max(co2, 1e-30) / henry(T, KH_CO2_298, DLNKH_CO2)
    a_h2_ocean = max(h2_ocean, 1e-30) / henry(T, KH_H2_298, DLNKH_H2)
    a_hcooh = max(formate, 1e-30) / (1.0 + 10.0 ** (pH_ocean - PKA_FORMIC))
    e_anode = -LN10 * rt_f * pH_vent - 0.5 * rt_f * math.log(a_h2)
    e_cathode = E0_CO2_HCOOH - LN10 * rt_f * pH_ocean + 0.5 * rt_f * math.log(a_co2 / a_hcooh)
    e_her = -LN10 * rt_f * pH_ocean - 0.5 * rt_f * math.log(a_h2_ocean)
    return e_anode, e_cathode, e_her


def butler_volmer(eta: float, j0: float, alpha: float, T: float) -> float:
    """Signed Butler-Volmer current density for overpotential ``eta`` (anodic positive)."""
    f = F / (R * T)
    x1, x2 = alpha * f * eta, -(1.0 - alpha) * f * eta
    return j0 * (math.exp(min(x1, 700.0)) - math.exp(min(x2, 700.0)))


def _brentq(fn, a, b, xtol=1e-14, maxiter=200):
    from scipy.optimize import brentq
    return float(brentq(fn, a, b, xtol=xtol, maxiter=maxiter))


def anode_overpotential(j: float, j0: float, alpha: float, T: float, j_lim: float | None) -> float:
    """Invert the anode's Butler-Volmer (with a Koutecky-Levich transport limit) for ``j >= 0``."""
    if j <= 0.0:
        return 0.0
    j_kin = j if (j_lim is None or not math.isfinite(j_lim)) else j / max(1.0 - j / j_lim, 1e-15)
    hi = 0.5
    while butler_volmer(hi, j0, alpha, T) < j_kin and hi < 20.0:
        hi *= 2.0
    return _brentq(lambda e: butler_volmer(e, j0, alpha, T) - j_kin, 0.0, hi)


def _kl(j_kin: float, j_lim: float | None) -> float:
    """Koutecky-Levich series combination of a kinetic and a limiting current (both >= 0)."""
    if j_lim is None or not math.isfinite(j_lim):
        return j_kin
    return j_kin * j_lim / (j_kin + j_lim) if j_kin > 0.0 else 0.0


def cathode_current(e_c, *, e_co2, e_her, j0_co2, j0_her, alpha, T, j_lim_co2, j_lim_her,
                    j_lim_co2_rev=None, j_lim_her_rev=None):
    """Total cathodic current (positive = reducing) at cathode potential ``e_c``, per branch.

    Each branch is transport-limited in both directions: the reducing direction
    by the reactant supply (CO2, H+), the reverse direction by the product it
    would oxidise (formate, the ocean-side trace H2), so a branch whose
    equilibrium sits above the mixed potential cannot run away anodically on a
    reactant that is not there.
    """
    def branch(e_eq, j0, j_lim, j_lim_rev):
        jk = -butler_volmer(e_c - e_eq, j0, alpha, T)       # cathodic magnitude when e_c < e_eq
        if jk >= 0.0:
            return _kl(jk, j_lim)                            # reducing direction
        return -_kl(-jk, j_lim_rev)                          # reverse (anodic) direction
    jc = branch(e_co2, j0_co2, j_lim_co2, j_lim_co2_rev)
    jh = branch(e_her, j0_her, j_lim_her, j_lim_her_rev)
    return jc + jh, jc, jh


def cathode_potential(j, **kw) -> float:
    """Invert the two-branch cathode for the potential carrying total cathodic current ``j``."""
    e_top = max(kw["e_co2"], kw["e_her"]) + 1.0
    e_bot = min(kw["e_co2"], kw["e_her"]) - 1.0
    fn = lambda e: cathode_current(e, **kw)[0] - j  # noqa: E731
    while fn(e_bot) < 0.0 and e_bot > min(kw["e_co2"], kw["e_her"]) - 20.0:
        e_bot -= 1.0
    return _brentq(fn, e_bot, e_top)


def solve_cell(*, T, pH_vent, pH_ocean, h2, co2, formate, h2_ocean, catalyst_activity, ni_fraction,
               conductivity, layer_thickness, porosity, ionic_strength,
               j0_h2_ref, j0_co2_ref, j0_her_ref, alpha, activation_energy, ni_gain, ni_reference,
               boundary_layer, d_h2, d_co2, d_proton, fluid_conductivity_per_molar,
               bruggeman_exponent, trace_product=1.0e-9) -> CellSolution:
    """Solve the vent-wall galvanic cell once (steady state at the given fluid state)."""
    # The product level never reads below the trace level that defines the
    # fresh-fluid (ideal) emf, so emf <= emf_fresh and the loss fractions partition it.
    formate_eff = max(formate, trace_product)
    e_a, e_c_eq, e_her = equilibrium_potentials(T, pH_vent, pH_ocean, h2, co2, formate_eff, h2_ocean)
    _, e_c_fresh, _ = equilibrium_potentials(T, pH_vent, pH_ocean, h2, co2, trace_product, h2_ocean)
    emf, emf_fresh = e_c_eq - e_a, e_c_fresh - e_a

    arrh = math.exp(-activation_energy / R * (1.0 / T - 1.0 / T_REF))
    cat = max(catalyst_activity, 0.0)
    gain = ni_activity_gain(ni_fraction, ni_gain) / ni_activity_gain(ni_reference, ni_gain)
    j0_a = max(j0_h2_ref * cat * gain * arrh, 1e-30)
    j0_c = max(j0_co2_ref * cat * gain * arrh, 1e-30)
    j0_h = max(j0_her_ref * cat * arrh, 1e-30)

    # limiting currents (mol/L -> mol/m^3 x 1000)
    delta = max(boundary_layer, 1e-9)
    j_lim_a = 2.0 * F * d_h2 * max(h2, 0.0) * 1e3 / delta
    j_lim_c = 2.0 * F * d_co2 * max(co2, 0.0) * 1e3 / delta
    j_lim_h = F * d_proton * (10.0 ** (-pH_ocean)) * 1e3 / delta
    # reverse-direction supply limits: formate oxidation, ocean-side H2 oxidation
    j_lim_c_rev = 2.0 * F * d_co2 * formate_eff * 1e3 / delta
    j_lim_h_rev = 2.0 * F * d_h2 * max(h2_ocean, 0.0) * 1e3 / delta

    # circuit resistances (ohm m^2)
    r_e = layer_thickness / max(conductivity, 1e-30)
    sigma_ion = fluid_conductivity_per_molar * max(ionic_strength, 1e-6) * (1.0 + 0.02 * (T - 298.15)) \
        * max(porosity, 1e-6) ** bruggeman_exponent
    r_ion = layer_thickness / max(sigma_ion, 1e-30)
    r_tot = r_e + r_ion

    cath = dict(e_co2=e_c_eq, e_her=e_her, j0_co2=j0_c, j0_her=j0_h, alpha=alpha, T=T,
                j_lim_co2=j_lim_c, j_lim_her=j_lim_h, j_lim_co2_rev=j_lim_c_rev, j_lim_her_rev=j_lim_h_rev)
    # kinetic-only reference: no transport limit on the reducing direction (the
    # reverse-direction caps stay, they are what keeps the HER branch honest)
    cath_kin = dict(cath, j_lim_co2=None, j_lim_her=None)

    def cell_fn(j):
        return cathode_potential(j, **cath) - (e_a + anode_overpotential(j, j0_a, alpha, T, j_lim_a)) - j * r_tot

    j_max = min(j_lim_a, j_lim_c + j_lim_h) * (1.0 - 1e-9)
    losses = {"thermodynamic": 0.0, "electrical": 0.0, "catalytic": 0.0, "transport": 0.0}
    no_current = emf_fresh <= 0.0 or j_lim_a <= 0.0 or (j_lim_c + j_lim_h) <= 0.0 or cell_fn(1e-300) <= 0.0
    if no_current:
        e_c0 = cathode_potential(0.0, **cath) if (j_lim_c + j_lim_h) > 0.0 else e_c_eq
        losses["thermodynamic"] = 1.0
        return CellSolution(
            emf=emf, emf_fresh=emf_fresh, e_anode_eq=e_a, e_cathode_eq=e_c_eq, e_her_eq=e_her,
            j=0.0, e_anode=e_a, e_cathode=e_c0, eta_anode=0.0, eta_cathode=max(e_c_eq - e_c0, 0.0),
            eta_anode_kinetic=0.0, eta_cathode_kinetic=0.0, ohmic_drop=0.0, j_co2=0.0, j_her=0.0,
            j_her_reverse=0.0, faradaic_efficiency=0.0, iv_residual=0.0, losses=losses, limitation="thermodynamic",
            j_lim_anode=j_lim_a, j_lim_co2=j_lim_c, j_lim_her=j_lim_h)

    j = _brentq(cell_fn, 1e-300, j_max)
    e_c = cathode_potential(j, **cath)
    eta_a = anode_overpotential(j, j0_a, alpha, T, j_lim_a)
    e_an = e_a + eta_a
    eta_c = e_c_eq - e_c
    eta_a_kin = anode_overpotential(j, j0_a, alpha, T, None)
    eta_c_kin = e_c_eq - cathode_potential(j, **cath_kin)
    ohmic = j * r_tot
    _, jc, jh = cathode_current(e_c, **cath)
    jh_rev = max(-jh, 0.0)                               # local ocean-side H2 oxidation feeding the cathode
    supply = j + jh_rev
    fe = min(max(jc, 0.0) / supply, 1.0) if supply > 0 else 0.0
    residual = abs(e_c - e_an - ohmic) / max(emf_fresh, 1e-30)

    ideal = max(emf_fresh, 1e-30)
    losses = {
        "thermodynamic": max(emf_fresh - emf, 0.0) / ideal,
        "electrical": ohmic / ideal,
        "catalytic": max(eta_a_kin + eta_c_kin, 0.0) / ideal,
        "transport": max((eta_a - eta_a_kin) + (eta_c - eta_c_kin), 0.0) / ideal,
    }
    return CellSolution(
        emf=emf, emf_fresh=emf_fresh, e_anode_eq=e_a, e_cathode_eq=e_c_eq, e_her_eq=e_her,
        j=j, e_anode=e_an, e_cathode=e_c, eta_anode=eta_a, eta_cathode=eta_c,
        eta_anode_kinetic=eta_a_kin, eta_cathode_kinetic=eta_c_kin, ohmic_drop=ohmic,
        j_co2=max(jc, 0.0), j_her=max(jh, 0.0), j_her_reverse=jh_rev, faradaic_efficiency=fe,
        iv_residual=residual,
        losses=losses, limitation=limitation_label(losses, fe),
        j_lim_anode=j_lim_a, j_lim_co2=j_lim_c, j_lim_her=j_lim_h)


def polarization_curve(n: int = 40, j_max: float | None = None, **kw) -> dict:
    """Cell voltage decomposition vs current density for the viz (same physics as ``solve_cell``)."""
    sol = solve_cell(**kw)
    jm = j_max or max(sol.j * 5.0, 1e-6)
    jm = min(jm, min(sol.j_lim_anode, sol.j_lim_co2 + sol.j_lim_her) * 0.999)
    T, alpha = kw["T"], kw["alpha"]
    arrh = math.exp(-kw["activation_energy"] / R * (1.0 / T - 1.0 / T_REF))
    gain = ni_activity_gain(kw["ni_fraction"], kw["ni_gain"]) / ni_activity_gain(kw["ni_reference"], kw["ni_gain"])
    cat = max(kw["catalyst_activity"], 0.0)
    j0_a = max(kw["j0_h2_ref"] * cat * gain * arrh, 1e-30)
    j0_c = max(kw["j0_co2_ref"] * cat * gain * arrh, 1e-30)
    j0_h = max(kw["j0_her_ref"] * cat * arrh, 1e-30)
    r_tot = sol.ohmic_drop / sol.j if sol.j > 0 else kw["layer_thickness"] / max(kw["conductivity"], 1e-30)
    delta = max(kw["boundary_layer"], 1e-9)
    cath = dict(e_co2=sol.e_cathode_eq, e_her=sol.e_her_eq, j0_co2=j0_c, j0_her=j0_h, alpha=alpha, T=T,
                j_lim_co2=sol.j_lim_co2, j_lim_her=sol.j_lim_her,
                j_lim_co2_rev=2.0 * F * kw["d_co2"] * max(kw["formate"], 1e-9) * 1e3 / delta,
                j_lim_her_rev=2.0 * F * kw["d_h2"] * max(kw["h2_ocean"], 0.0) * 1e3 / delta)
    out = {"j": [], "cell_voltage": [], "eta_anode": [], "eta_cathode": [], "ohmic": [],
           "faradaic_efficiency": [], "operating_point": sol.to_dict()}
    for i in range(n):
        j = jm * (i + 1) / n
        e_c = cathode_potential(j, **cath)
        eta_a = anode_overpotential(j, j0_a, alpha, T, sol.j_lim_anode)
        _, jc, jh_ = cathode_current(e_c, **cath)
        out["j"].append(j)
        out["cell_voltage"].append(e_c - (sol.e_anode_eq + eta_a))
        out["eta_anode"].append(eta_a)
        out["eta_cathode"].append(sol.e_cathode_eq - e_c)
        out["ohmic"].append(j * r_tot)
        out["faradaic_efficiency"].append(min(max(jc, 0.0) / (j + max(-jh_, 0.0)), 1.0))
    return out


# --------------------------------------------------------------------------- #
# The process
# --------------------------------------------------------------------------- #
class ButlerVolmerCarbonFixationProcess(Process):
    """Carbon fixation as a galvanic cell across the Fe/Ni-sulfide wall: Nernst
    half-cell potentials from the fluid redox state, Butler-Volmer electrode
    kinetics with Koutecky-Levich transport limits, the ohmic mineral + ionic
    circuit, and the faradaic split of the current over formate / acetate /
    pyruvate (additive deltas on the dissolved pool) with open-flow washout.
    Publishes the circuit readouts, the four failure-mode loss fractions and the
    electron-balance witnesses the charge ledger audits."""

    contract = {
        "summary": "Butler-Volmer galvanic cell: fluid redox -> Nernst potentials -> overpotentials -> current -> surface rates.",
        "description": (
            "Each tick solves the vent-wall cell at steady state: H2 oxidation on the alkaline "
            "side and CO2 reduction (plus competing H2 evolution) on the acidic side, with "
            "Butler-Volmer kinetics scaled by catalyst activity, Ni fraction and temperature, "
            "Koutecky-Levich transport limits, and the ohmic drop through the mineral layer "
            "(thickness / conductivity) and the pore-fluid return path. The CO2-reduction "
            "current is split over formate (2e), acetate (8e) and pyruvate (10e) by electron "
            "branch fractions calibrated to the Preiner-2020 yield hierarchy; product "
            "increments are additive deltas with exponential open-flow washout. Publishes "
            "emf, overpotential, current density, faradaic efficiency, the anode / cathode-"
            "branch electron fluxes, the circuit residual and the thermodynamic / electrical "
            "/ catalytic / transport loss fractions with the dominant limitation code."
        ),
        "inputs": {
            "H2": "dissolved H2 on the vent side (molar)", "CO2": "dissolved CO2 on the ocean side (molar)",
            "temperature": "interface temperature (K)", "pH_vent": "alkaline vent-side pH",
            "pH_ocean": "acidic ocean-side pH", "catalyst_activity": "active-catalyst fraction (0 = no mineral)",
            "ni_fraction": "Ni mole fraction of the Fe/Ni catalytic phase",
            "conductivity": "electronic conductivity of the mineral layer (S/m)",
            "layer_thickness": "mineral layer thickness (m)", "porosity": "pore fraction (ionic return path)",
            "ionic_strength": "pore-fluid ionic strength (molar)",
            "formate": "formate pool (molar)", "acetate": "acetate pool (molar)", "pyruvate": "pyruvate pool (molar)",
        },
        "outputs": {
            "formate": "formate delta (molar)", "acetate": "acetate delta (molar)", "pyruvate": "pyruvate delta (molar)",
            "net_carbon_flux": "carbon fixed per second (mole/second)",
            "current_density": "cell current density (ampere/meter**2)", "emf": "open-circuit emf at the current product level (volt)",
            "overpotential": "total overpotential + ohmic drop under load (volt)",
            "faradaic_efficiency": "fraction of the electrons reaching the cathode that reduce CO2",
            "electron_flux": "electrons supplied to the cathode: cell current + local ocean-side H2 oxidation (mole/second)",
            "carbon_electron_flux": "electrons into carbon products (mole/second)",
            "her_electron_flux": "electrons into H2 evolution (mole/second)",
            "iv_residual": "circuit-equation residual at the solved current (dimensionless)",
            "loss_thermodynamic": "fraction of the fresh-fluid emf lost to product back-pressure",
            "loss_electrical": "fraction lost to the ohmic drop", "loss_catalytic": "fraction lost to activation overpotential",
            "loss_transport": "fraction lost to concentration overpotential", "limitation_code": "0 thermodynamic, 1 electrical, 2 catalytic, 3 transport",
        },
        "assumptions": [
            "Steady cell each tick (electrode double layers equilibrate faster than the pools change).",
            "The CO2/HCOOH couple sets the cathode emf; acetate and pyruvate are side branches of the same current (their couples are more positive, so this is conservative).",
            "H2 and CO2 are boundary feeds (not depleted by the current); products accumulate and wash out.",
            "Standard potentials taken at 25 C (dE0/dT neglected); Henry constants van 't Hoff-corrected.",
        ],
        "math": [
            "E_a = -(RT/F) ln10 pH_vent - (RT/2F) ln a_H2;  E_c = E0 - (RT/F) ln10 pH_ocean + (RT/2F) ln(a_CO2 / a_HCOOH)",
            "j = j0 [exp(alpha F eta / RT) - exp(-(1-alpha) F eta / RT)];  1/j_eff = 1/j_kin + 1/j_lim",
            "E_c(j) - E_a(j) = j (L/sigma_e + L/(sigma_f phi^1.5))",
            "rate_i = f_i FE j A / (n_i F)",
        ],
        "symbols": {"j0": "exchange current density", "eta": "overpotential", "FE": "faradaic efficiency",
                    "f_i": "electron branch fraction", "n_i": "electrons per product"},
        "references": ["altair2025carbon", "altair2025electrochemical", "commchem2026currentproducing",
                       "commchem2026energeticconstraints", "preiner2020hydrogen", "hudson2020co2"],
    }

    config_schema = {
        # exchange current densities at T_REF, Ni3Fe, full catalyst activity (A/m^2)
        "j0_h2_ref": {"_type": "float", "_default": 5.0e-5, "_units": "ampere/meter**2", "_provenance": "calibrated"},
        "j0_co2_ref": {"_type": "float", "_default": 1.0e-5, "_units": "ampere/meter**2", "_provenance": "calibrated"},
        "j0_her_ref": {"_type": "float", "_default": 2.5e-6, "_units": "ampere/meter**2", "_provenance": "calibrated"},
        "alpha": {"_type": "float", "_default": 0.5, "_units": "dimensionless", "_provenance": "inferred"},
        "activation_energy": {"_type": "float", "_default": 4.0e4, "_units": "joule/mole", "_provenance": "hypothetical"},
        # Ni dependence of the CO2-reduction exchange current (Preiner hierarchy)
        "ni_gain": {"_type": "float", "_default": 3.0, "_units": "dimensionless", "_provenance": "hypothetical"},
        "ni_reference": {"_type": "float", "_default": 0.75, "_units": "dimensionless", "_provenance": "inferred"},
        # electron branch fractions at the reference Ni composition (formate = remainder)
        "acetate_branch_ref": {"_type": "float", "_default": 2.0e-3, "_units": "dimensionless", "_provenance": "inferred"},
        "pyruvate_branch_ref": {"_type": "float", "_default": 2.5e-4, "_units": "dimensionless", "_provenance": "inferred"},
        # transport
        "boundary_layer": {"_type": "float", "_default": 1.0e-3, "_units": "meter", "_provenance": "inferred"},
        "d_h2": {"_type": "float", "_default": 4.5e-9, "_units": "meter**2/second", "_provenance": "measured"},
        "d_co2": {"_type": "float", "_default": 1.9e-9, "_units": "meter**2/second", "_provenance": "measured"},
        "d_proton": {"_type": "float", "_default": 9.3e-9, "_units": "meter**2/second", "_provenance": "measured"},
        # ionic return path
        "fluid_conductivity_per_molar": {"_type": "float", "_default": 8.0, "_units": "siemens/meter", "_provenance": "inferred"},
        "bruggeman_exponent": {"_type": "float", "_default": 1.5, "_units": "dimensionless", "_provenance": "inferred"},
        # ocean-side dissolved H2 (sets the HER equilibrium potential)
        "h2_ocean": {"_type": "float", "_default": 1.0e-7, "_units": "molar", "_provenance": "hypothetical"},
        # geometry: interface area and the fluid volume the products dilute into
        "interface_area": {"_type": "float", "_default": 1.0e-3, "_units": "meter**2", "_provenance": "inferred"},
        "reactor_volume": {"_type": "float", "_default": 0.1, "_units": "liter", "_provenance": "inferred"},
        "dilution_rate": {"_type": "float", "_default": 0.0, "_units": "1/second", "_provenance": "hypothetical"},
    }

    def inputs(self):
        return {
            "H2": _MOLAR, "CO2": _MOLAR, "temperature": _K, "pH_vent": _DIMLESS, "pH_ocean": _DIMLESS,
            "catalyst_activity": _DIMLESS, "ni_fraction": _DIMLESS, "conductivity": _SM,
            "layer_thickness": _M, "porosity": _DIMLESS, "ionic_strength": _MOLAR,
            "formate": _MOLAR, "acetate": _MOLAR, "pyruvate": _MOLAR,
        }

    def outputs(self):
        return {
            "formate": _MOLAR, "acetate": _MOLAR, "pyruvate": _MOLAR,
            "net_carbon_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
            "current_density": {"_type": "overwrite[float]", "_units": "ampere/meter**2"},
            "emf": {"_type": "overwrite[float]", "_units": "volt"},
            "overpotential": {"_type": "overwrite[float]", "_units": "volt"},
            "faradaic_efficiency": _OVW,
            "electron_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
            "carbon_electron_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
            "her_electron_flux": {"_type": "overwrite[float]", "_units": "mole/second"},
            "iv_residual": _OVW,
            "loss_thermodynamic": _OVW, "loss_electrical": _OVW, "loss_catalytic": _OVW, "loss_transport": _OVW,
            "limitation_code": _OVW,
        }

    def initial_state(self):
        return {"H2": 5.0e-3, "CO2": 2.0e-3, "temperature": T_REF, "pH_vent": 9.5, "pH_ocean": 6.0,
                "catalyst_activity": 1.0, "ni_fraction": 0.75, "conductivity": 1.0e-3,
                "layer_thickness": 1.0e-3, "porosity": 0.35, "ionic_strength": 0.25,
                "formate": 0.0, "acetate": 0.0, "pyruvate": 0.0}

    def solve(self, state) -> CellSolution:
        c = self.config
        return solve_cell(
            T=max(float(state.get("temperature", T_REF)), 250.0),
            pH_vent=float(state.get("pH_vent", 9.5)), pH_ocean=float(state.get("pH_ocean", 6.0)),
            h2=max(float(state.get("H2", 0.0)), 0.0), co2=max(float(state.get("CO2", 0.0)), 0.0),
            formate=max(float(state.get("formate", 0.0)), 0.0), h2_ocean=float(c["h2_ocean"]),
            catalyst_activity=max(float(state.get("catalyst_activity", 0.0)), 0.0),
            ni_fraction=float(state.get("ni_fraction", 0.75)),
            conductivity=max(float(state.get("conductivity", 1e-3)), 0.0),
            layer_thickness=max(float(state.get("layer_thickness", 1e-3)), 1e-9),
            porosity=float(state.get("porosity", 0.35)), ionic_strength=float(state.get("ionic_strength", 0.25)),
            j0_h2_ref=float(c["j0_h2_ref"]), j0_co2_ref=float(c["j0_co2_ref"]), j0_her_ref=float(c["j0_her_ref"]),
            alpha=float(c["alpha"]), activation_energy=float(c["activation_energy"]),
            ni_gain=float(c["ni_gain"]), ni_reference=float(c["ni_reference"]),
            boundary_layer=float(c["boundary_layer"]), d_h2=float(c["d_h2"]), d_co2=float(c["d_co2"]),
            d_proton=float(c["d_proton"]), fluid_conductivity_per_molar=float(c["fluid_conductivity_per_molar"]),
            bruggeman_exponent=float(c["bruggeman_exponent"]))

    def branch_fractions(self, ni_fraction: float) -> dict:
        """Electron branch fractions over the products at Ni mole fraction ``x`` (sum to 1)."""
        scale = max(ni_fraction, 0.0) / max(float(self.config["ni_reference"]), 1e-9)
        fa = min(float(self.config["acetate_branch_ref"]) * scale, 0.45)
        fp = min(float(self.config["pyruvate_branch_ref"]) * scale, 0.45)
        return {"formate": 1.0 - fa - fp, "acetate": fa, "pyruvate": fp}

    def update(self, state, interval):
        sol = self.solve(state)
        area = max(float(self.config["interface_area"]), 1e-12)
        vol = max(float(self.config["reactor_volume"]), 1e-12)
        dilution = max(float(self.config["dilution_rate"]), 0.0)
        branches = self.branch_fractions(float(state.get("ni_fraction", 0.75)))

        # Electron bookkeeping (Kirchhoff at the cathode): electrons reach the
        # cathode through the mineral (the cell current j) and, when the cell
        # current is tiny, also locally from oxidation of the trace ocean-side H2
        # (the HER branch running in reverse — a mixed-potential couple that the
        # charge ledger would otherwise flag). They leave into carbon products
        # or into H2 evolution.
        e_total = (sol.j + sol.j_her_reverse) * area / F   # mol e-/s supplied to the cathode
        e_carbon = sol.j_co2 * area / F                    # ... into CO2 reduction
        e_her = sol.j_her * area / F                       # ... into H2 evolution
        out, carbon_rate = {}, 0.0
        for name, n_e in N_ELECTRONS.items():
            rate = branches[name] * e_carbon / n_e      # mol/s
            pool = max(float(state.get(name, 0.0)), 0.0)
            washout = pool * (1.0 - math.exp(-dilution * interval))
            out[name] = rate * interval / vol - washout
            carbon_rate += CARBONS[name] * rate
        out.update({
            "net_carbon_flux": carbon_rate,
            "current_density": sol.j,
            "emf": sol.emf,
            "overpotential": sol.eta_anode + sol.eta_cathode + sol.ohmic_drop,
            "faradaic_efficiency": sol.faradaic_efficiency,
            "electron_flux": e_total,
            "carbon_electron_flux": e_carbon,
            "her_electron_flux": e_her,
            "iv_residual": sol.iv_residual,
            "loss_thermodynamic": sol.losses["thermodynamic"],
            "loss_electrical": sol.losses["electrical"],
            "loss_catalytic": sol.losses["catalytic"],
            "loss_transport": sol.losses["transport"],
            "limitation_code": float(LIMITATION_CODES[sol.limitation]),
        })
        return out


def default_cell_kwargs(**overrides) -> dict:
    """The process's nominal cell (config defaults + initial state) as ``solve_cell`` kwargs."""
    cfg = {k: v["_default"] for k, v in ButlerVolmerCarbonFixationProcess.config_schema.items()}
    kw = dict(T=T_REF, pH_vent=9.5, pH_ocean=6.0, h2=5.0e-3, co2=2.0e-3, formate=0.0,
              h2_ocean=cfg["h2_ocean"], catalyst_activity=1.0, ni_fraction=0.75,
              conductivity=1.0e-3, layer_thickness=1.0e-3, porosity=0.35, ionic_strength=0.25,
              j0_h2_ref=cfg["j0_h2_ref"], j0_co2_ref=cfg["j0_co2_ref"], j0_her_ref=cfg["j0_her_ref"],
              alpha=cfg["alpha"], activation_energy=cfg["activation_energy"], ni_gain=cfg["ni_gain"],
              ni_reference=cfg["ni_reference"], boundary_layer=cfg["boundary_layer"], d_h2=cfg["d_h2"],
              d_co2=cfg["d_co2"], d_proton=cfg["d_proton"],
              fluid_conductivity_per_molar=cfg["fluid_conductivity_per_molar"],
              bruggeman_exponent=cfg["bruggeman_exponent"])
    kw.update(overrides)
    return kw


__all__ = ["ButlerVolmerCarbonFixationProcess", "CellSolution", "solve_cell", "polarization_curve",
           "equilibrium_potentials", "butler_volmer", "limitation_label", "ni_activity_gain",
           "default_cell_kwargs", "LIMITATION_CODES", "LIMITATION_NAMES", "N_ELECTRONS", "CARBONS",
           "F", "R", "T_REF"]
