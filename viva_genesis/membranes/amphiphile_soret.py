"""Literature-grounded ionic-strength dependence of the amphiphile Soret coefficient.

The thermophoretic (Baaske) trap in ``self_maintaining_concentrated`` enriches the
fatty-acid pool by ``exp(beta * L)`` with ``beta`` LINEAR in the amphiphile Soret
coefficient ``S_T`` (``ThermophoreticTrapProcess``). A prior inline analysis made
closure salinity-gated with an *ad-hoc* ``S_T(I) = S_T0 + A*lambda_D(I)^2``
calibrated by hand to hit ``S_T = 0.10`` at ``I = 0.01 M``. This module replaces the
guessed calibration with the measured thermophoresis literature for charged
single-chain surfactants and small ions, and makes the ionic-strength scaling an
explicit, cited choice rather than an invented one.

WHAT THE LITERATURE ACTUALLY MEASURES
-------------------------------------
There is **no direct Soret measurement of single-chain fatty-acid (decanoate /
oleate) monomers or premicellar aggregates versus ionic strength** (searched Oct
2026). The relation below is therefore built from the three nearest *measured*
anchors, and the magnitude anchor is flagged as a surfactant-class estimate, not a
decanoate-specific datum.

1. MONOMERIC / SMALL-ION FLOOR  ``S_T0``  [MEASURED]
   Aqueous 1:1 electrolytes (NaCl, KCl) have Soret coefficients with a near-constant
   term of ~2.0-2.2e-3 K^-1 (Di Lecce & Bresme and refs therein, Phys. Chem. Chem.
   Phys. 2025, d4cp04477k: a = 2.04e-3 for NaCl, 2.20e-3 for KCl). A dispersed
   fatty-acid MONOMER is a small singly-charged solute of this class, so its Soret
   floor is ~2e-3 K^-1 (the "no self-association" limit). Taken as S_T0.

2. CHARGED SINGLE-CHAIN-SURFACTANT MAGNITUDE  ``S_T_ref``  [MEASURED CLASS / ESTIMATED SPECIES]
   SDS (sodium dodecyl sulfate) is a single C12 anionic surfactant -- the closest
   measured analog to deprotonated decanoate/oleate. Piazza & Guarino (Phys. Rev.
   Lett. 88, 208302, 2002) measured SDS-micelle thermophoresis (radius ~2.5 nm,
   structural charge Z~50-75); the Soret coefficient is positive and of order
   1e-2 - 1e-1 K^-1 at low ionic strength. Vigolo, Buzzaccaro & Piazza (Langmuir 26,
   7792, 2010) extend this to added-salt / thermoelectric (Seebeck) effects. We take
   the low-salt self-associating amphiphile value as S_T_ref ~ 0.08 K^-1 at
   I_ref = 0.01 M. **This magnitude is a surfactant-class estimate** (SDS-micelle
   order), not a measured decanoate number -- it is the one assumed scalar.

3. IONIC-STRENGTH SCALING  ``lambda_D(I)``  [MEASURED SCALING LAW -- TWO REGIMES]
   S_T of a charged species rises with the Debye screening length
   ``lambda_D(I) = 0.304 / sqrt(I) nm`` (1:1 electrolyte, 25 C; textbook). The
   literature gives TWO measured power laws, and they bracket the answer:

     * LINEAR  ``S_T^ionic ~ lambda_D``  (exponent 1, -> 1/sqrt(I)).
       Duhr & Braun (PNAS 103, 19678, 2006), Eq. 2, parameter-free fit to DNA and
       polystyrene beads:  S_T^ionic = A*beta*sigma_eff^2*lambda_D / (4*eps*eps0*k*T^2),
       i.e. LINEAR in lambda_D (sigma_eff = effective surface-charge DENSITY held
       fixed). Confirmed for 215 nm PS beads, S_T ~ 0.2 K^-1 linear in lambda_D
       (Eslahian et al., arXiv:1401.7242). This is the FLAT-double-layer regime
       (particle radius >> lambda_D).

     * QUADRATIC  ``S_T^ionic ~ lambda_D^2``  (exponent 2, -> 1/I).
       Piazza & Guarino (PRL 2002, abstract): for SDS micelles the Soret coefficient
       "strongly decreases with ionic strength, scaling as the square of the
       Debye-Huckel length." This is the SMALL-charged-object regime (radius
       <~ lambda_D), captured by the (1+kappa*a)^-2 factor in Ruckenstein/Dhont
       charged-colloid theory (arXiv:0708.0090).

   A single-chain amphiphile / premicellar aggregate is SMALL (a ~ 1-2 nm) and, at
   low I, lambda_D (3 nm at I=0.01 M) is comparable to or larger than it -- the
   Piazza-Guarino regime -> the steeper lambda_D^2 (1/I) law is the better-matched
   measured analog. The Duhr-Braun lambda_D (1/sqrt(I)) law is the gentler bound a
   flat-double-layer object would follow. So the honest grounded answer is a
   BRACKET, exponent in {1, 2}. (The prior ad-hoc lambda_D^2 happens to coincide with
   the Piazza-Guarino SDS measurement -- so its *scaling* was defensible even though
   its calibration was a guess.)

S_T scales with particle area A (Duhr-Braun): a monomer (small A) has a small Soret,
self-association (large effective A) raises it -- the physical basis for a low floor
and a raised aggregate anchor.

USAGE
-----
``soret_of_ionic_strength`` returns S_T (1/K) for an ionic strength I (mol/L). Pass
its value at each I as the scalar ``soret_coeff`` of ``og_self_maintaining_concentrated``
(the trap process takes a fixed float). Default ``exponent=2`` = the better-matched
single-chain-surfactant (Piazza-Guarino SDS) regime; ``exponent=1`` = the gentler
Duhr-Braun flat-double-layer bound.
"""
from __future__ import annotations

import math

# --- Measured / estimated anchors (see module docstring for provenance) ---------
S_T0_MONOMER = 2.0e-3            # K^-1  [MEASURED] small-ion / monomer floor (NaCl,KCl ~2e-3)
S_T_REF_AGGREGATE = 0.08         # K^-1  [ESTIMATED, SDS-micelle class] self-assoc. amphiphile at I_ref
I_REF = 0.01                     # mol/L  reference ionic strength for the aggregate anchor
S_T_MAX = 0.30                   # K^-1  physical cap (largest measured biomolecule/colloid Soret)
DEBYE_PREFACTOR_NM = 0.304       # nm    lambda_D = 0.304/sqrt(I) for a 1:1 electrolyte at 25 C [textbook]


def debye_length_nm(ionic_strength: float, temperature_K: float = 298.15) -> float:
    """Debye screening length (nm) for a 1:1 electrolyte.

    ``lambda_D = 0.304 / sqrt(I)`` nm at 25 C (I in mol/L); scaled by
    ``sqrt(T/298.15)`` for a warmer vent pore (lambda_D ~ sqrt(eps*T), eps(T) roughly
    cancels the explicit T so the sqrt(T) factor is the dominant correction and is
    small: +6% at 60 C). [MEASURED/textbook constant.]
    """
    I = max(float(ionic_strength), 1e-9)
    t_factor = math.sqrt(max(temperature_K, 1.0) / 298.15)
    return DEBYE_PREFACTOR_NM * t_factor / math.sqrt(I)


def soret_of_ionic_strength(
    ionic_strength: float,
    *,
    exponent: int = 2,
    s_t0: float = S_T0_MONOMER,
    s_t_ref: float = S_T_REF_AGGREGATE,
    i_ref: float = I_REF,
    s_t_max: float = S_T_MAX,
    temperature_K: float = 298.15,
) -> float:
    """Grounded amphiphile Soret coefficient S_T (1/K) at ionic strength ``I`` (mol/L).

    ``S_T(I) = S_T0 + (S_T_ref - S_T0) * (lambda_D(I) / lambda_D(I_ref)) ** exponent``

    With ``lambda_D ~ 1/sqrt(I)`` this is ``S_T0 + (S_T_ref-S_T0)*(i_ref/I)**(exponent/2)``:
    ``exponent=1`` -> 1/sqrt(I) (Duhr-Braun linear-lambda_D bound);
    ``exponent=2`` -> 1/I (Piazza-Guarino SDS-micelle law, default -- the better-matched
    single-chain-surfactant analog). Clamped to [S_T0, s_t_max].
    """
    if exponent not in (1, 2):
        raise ValueError("exponent must be 1 (Duhr-Braun linear) or 2 (Piazza-Guarino quadratic)")
    lam = debye_length_nm(ionic_strength, temperature_K)
    lam_ref = debye_length_nm(i_ref, temperature_K)
    scale = (lam / lam_ref) ** exponent
    s_t = s_t0 + (s_t_ref - s_t0) * scale
    return float(min(max(s_t, s_t0), s_t_max))


# Convenience: the two measured-regime callables used in the salinity sweep.
def soret_piazza_guarino(ionic_strength: float, temperature_K: float = 298.15) -> float:
    """S_T(I) under the MEASURED SDS-micelle law (lambda_D^2 ~ 1/I). Best analog."""
    return soret_of_ionic_strength(ionic_strength, exponent=2, temperature_K=temperature_K)


def soret_duhr_braun(ionic_strength: float, temperature_K: float = 298.15) -> float:
    """S_T(I) under the MEASURED Duhr-Braun law (lambda_D ~ 1/sqrt(I)). Gentler bound."""
    return soret_of_ionic_strength(ionic_strength, exponent=1, temperature_K=temperature_K)
