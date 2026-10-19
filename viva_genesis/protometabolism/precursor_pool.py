"""NEW A — Geochemical carbon to a functional precursor pool (og-precursor-pool).

The bridge node between bulk reduced-carbon flux (og-carbon-fixation, supported)
and the *functional precursor set* the downstream reaction-network and amphiphile
studies consume. It REUSES the real C1-C3 reaction engine
(:class:`ReactionUniverseProcess` — the genuine libRoadRunner CSTR over the
rule-generated, atom-resolved, eQuilibrator-dG' reaction universe) and adds three
things the bridge needs:

1. **Precursor yield vectors.** The steady-state concentration of each functional
   (C>=2) organic precursor, with the C1 feedstock reported alongside. This is the
   state B/C/D consume.

2. **Carbon-source attribution** (NOT isotope / KIE ``13C`` tracing — no
   fractionation-rate data was provided, and inventing it would be a fabricated
   input). A steady-state linear apportionment over the atom-mapped stoichiometry
   and the solved reaction fluxes: what fraction of each precursor's carbon was
   fixed *de novo* from the CO2 feed versus passed through from fed upstream
   organics. It distinguishes a genuinely *delivered* pool (assembled de novo)
   from mere upstream carry-over. Honest label: "carbon-source attribution."

3. **Electron budget closure.** A degree-of-reduction balance (gamma = 4C + H - 2O;
   CO2 -> 0, H2 -> 2): the electrons supplied by H2 oxidation accounted for in the
   reduced organic products. Because every generated reaction is atom-balanced
   (``element_residual == 0``), gamma balances identically per reaction, so the net
   budget closes to integrator tolerance — reported as a witness, not claimed as
   evidence independent of the atom balance.

The three ablation controls (no-H2, no-catalyst, no-gradient) and the
withheld-calibration product prediction live in the study's composites + runner
(``workspace/studies/og-precursor-pool/``), not here.

Feed activities are the upstream-calibrated values (og-vent-interface bounded DIC
window 2-20 mM; og-carbon-fixation H2-driven Preiner hierarchy), never new
literature numbers introduced here.
"""
from __future__ import annotations

import numpy as np

from . import universe as U
from .universe_process import ReactionUniverseProcess, SPECIES_PORTS

__all__ = [
    "degree_of_reduction",
    "carbon_source_attribution",
    "electron_budget",
    "functional_precursors",
    "PrecursorPoolProcess",
]

# Overwrite (sensor) port specs — the pool process reports solved operating-point
# quantities, not accumulating pools.
_OW_MOLAR = {"_type": "overwrite[float]", "_units": "molar"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OW_MOLS = {"_type": "overwrite[float]", "_units": "molar/second"}

# Canonical calibrated inorganic feed defaults (molar): og-vent-interface DIC
# window lower bound (2 mM CO2) and og-carbon-fixation dissolved-H2 (~10.8 mM).
_CO2_DEFAULT = 2.0e-3
_H2_DEFAULT = 1.08e-2


def degree_of_reduction(form: dict[str, int]) -> float:
    """Available-electron / degree-of-reduction gamma = 4C + H - 2O.

    Referenced so CO2 -> 0 and H2 -> 2 (two available electrons per H2). This is
    the standard electron-equivalent accounting for a C/H/O balance; because the
    generated reactions are atom-balanced, gamma is conserved per reaction.
    """
    return 4.0 * form.get("C", 0) + form.get("H", 0) - 2.0 * form.get("O", 0)


def functional_precursors(u: U.Universe) -> list[str]:
    """Organic species with >= 2 carbons — the functional precursors downstream
    chemistry (reaction-network + amphiphile) actually needs, as opposed to the
    C1 feedstock (formate, formaldehyde)."""
    return [s for s in u.organics() if U.n_carbons(s) >= 2]


def carbon_source_attribution(
    u: U.Universe,
    fluxes: dict[str, float],
    fed_organics: set[str],
    *,
    flux_floor: float = 1.0e-12,
) -> dict[str, dict[str, float]]:
    """Steady-state carbon-source apportionment over the solved reaction fluxes.

    For every organic species, returns the fraction of its carbon traceable to
    ``"co2_fixed"`` (reduced de novo from the CO2 feed) versus ``"fed"`` (supplied
    as a fed upstream organic). This is source attribution over the atom-mapped
    stoichiometry — NOT isotope-fractionation 13C tracing.

    Carbon conservation at steady state makes this a linear fixed point. For each
    species i, the carbon arriving per second (from CO2-consuming reactions, from
    organic reactants carrying their own provenance, and from the organic feed)
    sums to the carbon leaving; the provenance fractions solve (I - M) f = b where
    M routes a reactant's provenance to the product and b injects the CO2-fixed and
    fed sources. Reactions are evaluated in their net (flux-signed) direction.
    """
    organics = u.organics()
    idx = {s: i for i, s in enumerate(organics)}
    n = len(organics)
    sources = ("co2_fixed", "fed")
    if n == 0:
        return {}

    # Carbon inflow bookkeeping per organic species i:
    #   Cin[i]           total carbon arriving per second
    #   from_co2[i]      carbon arriving that was a CO2 carbon newly fixed
    #   from_fed[i]      carbon arriving via the organic feed J_i
    #   M[i, j]          carbon arriving at i that came from organic reactant j
    Cin = np.zeros(n)
    from_co2 = np.zeros(n)
    from_fed = np.zeros(n)
    M = np.zeros((n, n))

    rid_to_r = {r.id: r for r in u.reactions}
    for rid, v in fluxes.items():
        r = rid_to_r.get(rid)
        if r is None or abs(v) <= flux_floor:
            continue
        # Net forward direction: reactants -> products if v > 0, else swap.
        reac, prod = (r.reactants, r.products) if v > 0 else (r.products, r.reactants)
        rate = abs(v)
        # Organic carbon atoms produced this reaction delivers, and the carbon
        # the reaction draws from CO2 (newly fixed) vs organic reactants.
        co2_in = rate * float(reac.get(U.CO2, 0))  # CO2 carbons consumed (each = 1 C)
        organic_reactant_c = {
            s: rate * nn * U.n_carbons(s)
            for s, nn in reac.items() if s.startswith("X_") and U.n_carbons(s) > 0
        }
        total_source_c = co2_in + sum(organic_reactant_c.values())
        if total_source_c <= 0.0:
            continue
        # Distribute the produced organic carbon over product species proportional
        # to each product's carbon, carrying the blended source provenance.
        produced = {s: nn * U.n_carbons(s) for s, nn in prod.items()
                    if s.startswith("X_") and U.n_carbons(s) > 0}
        produced_total = sum(produced.values())
        if produced_total <= 0.0:
            continue
        for s, c_s in produced.items():
            i = idx[s]
            share = rate * c_s  # carbon/sec delivered to species s by this reaction
            Cin[i] += share
            # provenance split of this reaction's source carbon
            from_co2[i] += share * (co2_in / total_source_c)
            for j_s, c_j in organic_reactant_c.items():
                M[i, idx[j_s]] += share * (c_j / total_source_c)

    # Organic feed injects "fed" carbon directly: the exchange reaction J_<sid>
    # (:-> sid; k_wash*feed) brings carbon of source "fed" into the species. Its
    # flux is in the full fluxes dict (getReactionRates includes the exchanges),
    # though J_<sid> is not among the internal u.reactions above.
    for s in fed_organics:
        if s not in idx or U.n_carbons(s) <= 0:
            continue
        feed_rate = abs(float(fluxes.get(f"J_{s}", 0.0)))
        if feed_rate <= 0.0:
            continue
        share = feed_rate * U.n_carbons(s)
        Cin[idx[s]] += share
        from_fed[idx[s]] += share

    # Normalise rows to provenance fractions: f = (I - Mhat) \ bhat where Mhat and
    # bhat are the per-carbon-normalised routing and injection.
    f = {s: {"co2_fixed": 0.0, "fed": 0.0} for s in organics}
    with np.errstate(divide="ignore", invalid="ignore"):
        norm = np.where(Cin > 0, 1.0 / Cin, 0.0)
    Mhat = M * norm[:, None]
    b_co2 = from_co2 * norm
    b_fed = from_fed * norm
    # species with no modelled inflow but that ARE fed are 100% fed.
    for s in fed_organics:
        if s in idx and Cin[idx[s]] <= 0.0:
            b_fed[idx[s]] = 1.0
    A = np.eye(n) - Mhat
    try:
        sol_co2 = np.linalg.solve(A, b_co2)
        sol_fed = np.linalg.solve(A, b_fed)
    except np.linalg.LinAlgError:
        sol_co2, *_ = np.linalg.lstsq(A, b_co2, rcond=None)
        sol_fed, *_ = np.linalg.lstsq(A, b_fed, rcond=None)
    for s, i in idx.items():
        c = float(np.clip(sol_co2[i], 0.0, 1.0))
        fv = float(np.clip(sol_fed[i], 0.0, 1.0))
        tot = c + fv
        if tot > 0:
            f[s] = {"co2_fixed": c / tot, "fed": fv / tot}
        else:
            f[s] = {"co2_fixed": 0.0, "fed": 0.0}
    return f


def electron_budget(u: U.Universe, fluxes: dict[str, float]) -> dict[str, float]:
    """Degree-of-reduction (electron) budget over the internal reactions.

    Electrons supplied by net H2 oxidation vs electrons carried into the reduced
    organic products. Returns rates (electron-equiv/second) and the normalised
    residual. Closes to integrator tolerance because every generated reaction is
    atom-balanced (gamma is linear in atom counts), so this is a *witness* of
    electron accounting, not evidence independent of the atom balance.
    """
    rid_to_r = {r.id: r for r in u.reactions}
    gamma = {s: degree_of_reduction(u.formulas[s]) for s in u.species}
    h2_consumed = 0.0          # electron-equiv/s liberated by H2 oxidation
    organic_e_gain = 0.0       # electron-equiv/s fixed into organics
    for rid, v in fluxes.items():
        r = rid_to_r.get(rid)
        if r is None or v == 0.0:
            continue
        reac, prod = (r.reactants, r.products) if v > 0 else (r.products, r.reactants)
        rate = abs(v)
        # H2 net consumed by this reaction (reactant side minus product side)
        h2_net = reac.get(U.H2, 0) - prod.get(U.H2, 0)
        h2_consumed += rate * h2_net * gamma[U.H2]
        for s, nn in prod.items():
            if s.startswith("X_"):
                organic_e_gain += rate * nn * gamma[s]
        for s, nn in reac.items():
            if s.startswith("X_"):
                organic_e_gain -= rate * nn * gamma[s]
    supplied = float(h2_consumed)
    fixed = float(organic_e_gain)
    residual = abs(supplied - fixed) / max(abs(supplied), 1e-30)
    return {"electrons_supplied_rate": supplied, "electrons_fixed_rate": fixed,
            "electron_budget_residual": float(residual)}


class PrecursorPoolProcess(ReactionUniverseProcess):
    """og-precursor-pool: the real C1-C3 reaction-universe CSTR, read out as a
    functional precursor pool with carbon-source attribution and an electron
    budget. Inherits the genuine libRoadRunner engine and all its witnesses
    (element_residual, carbon_residual, dissipation); adds the bridge outputs the
    downstream network + amphiphile studies consume.
    """

    contract = {
        **ReactionUniverseProcess.contract,
        "summary": (
            "Functional precursor pool from the real C1-C3 reaction-universe CSTR: "
            "precursor yield vectors, carbon-source attribution (de-novo CO2-fixed vs "
            "fed upstream organics; NOT isotope 13C), and a degree-of-reduction "
            "electron budget. Reuses ReactionUniverseProcess (libRoadRunner)."
        ),
    }

    config_schema = {
        **ReactionUniverseProcess.config_schema,
        # Reduced-nitrogen availability feeding the C:N readout, from
        # og-nutrient-bottlenecks (ammonium). Provenance: calibrated upstream.
        "ammonium_availability": {"_type": "float", "_default": 0.0, "_units": "molar",
                                  "_provenance": "calibrated"},
    }

    def initial_state(self):
        # Canonical de-novo pool: inorganic feed only (CO2 in the DIC window + H2),
        # NO organic feed. The base class seeds feed_pyruvate=1e-4; here it must be
        # 0 so the pool is assembled from CO2, not a seeded organic. (process-bigraph
        # treats a Float store value of 0.0 as empty and backfills it from this
        # default, so the default itself has to be 0.0 for the organics.)
        return {"feed_CO2": _CO2_DEFAULT, "feed_H2": _H2_DEFAULT, "feed_pyruvate": 0.0,
                "feed_formaldehyde": 0.0, "feed_formate": 0.0, "feed_acetate": 0.0}

    def outputs(self):
        out = super().outputs()
        out.update({
            "functional_pool_carbon": _OW_MOLAR,
            "pool_cofixed_fraction": _OW_DIMLESS,
            "functional_pool_cofixed_fraction": _OW_DIMLESS,
            "electrons_supplied_rate": _OW_MOLS,
            "electrons_fixed_rate": _OW_MOLS,
            "electron_budget_residual": _OW_DIMLESS,
            "cn_ratio": _OW_DIMLESS,
        })
        return out

    # -- analysis on the solved operating point ----------------------------------
    def _fed_organics(self, feeds: dict[str, float]) -> set[str]:
        fed = set()
        for sid, pid in U.FEED_SPECIES.items():
            if sid.startswith("X_") and float(feeds.get(pid, 0.0)) > 0.0:
                fed.add(sid)
        return fed

    def precursor_report(self, feeds: dict[str, float]) -> dict:
        """Full per-precursor report from the current solved state — used by the
        study runner to write the committed yield-vector artifact."""
        u = self.universe()
        conc, fluxes = self._conc, self._fluxes
        # Attribution counts every flux-carrying reaction (a much smaller floor
        # than the motif detector's), so carbon conservation is respected: with
        # CO2 the sole carbon feed, every organic resolves to ~100% CO2-fixed.
        attr = carbon_source_attribution(u, fluxes, self._fed_organics(feeds),
                                         flux_floor=1.0e-30)
        funcs = functional_precursors(u)
        sid_to_name = {v: k for k, v in SPECIES_PORTS.items()}
        vectors = {}
        for s in u.organics():
            vectors[sid_to_name.get(s, s)] = {
                "sid": s,
                "n_carbons": U.n_carbons(s),
                "concentration_M": float(conc.get(s, 0.0)),
                "co2_fixed_fraction": attr.get(s, {}).get("co2_fixed", 0.0),
                "fed_fraction": attr.get(s, {}).get("fed", 0.0),
                "functional": s in funcs,
            }
        eb = electron_budget(u, fluxes)
        return {"yield_vectors": vectors, "electron_budget": eb,
                "functional_species": [sid_to_name.get(s, s) for s in funcs]}

    def _functional_metrics(self, feeds: dict[str, float]) -> dict[str, float]:
        u = self.universe()
        conc, fluxes = self._conc, self._fluxes
        funcs = functional_precursors(u)
        pool_c = float(sum(U.n_carbons(s) * max(conc.get(s, 0.0), 0.0) for s in funcs))
        toc = float(sum(U.n_carbons(s) * max(conc.get(s, 0.0), 0.0) for s in u.organics()))
        attr = carbon_source_attribution(u, fluxes, self._fed_organics(feeds),
                                         flux_floor=1.0e-30)
        # carbon-weighted de-novo CO2-fixed fraction of the functional pool
        num = 0.0
        for s in funcs:
            c = U.n_carbons(s) * max(conc.get(s, 0.0), 0.0)
            num += c * attr.get(s, {}).get("co2_fixed", 0.0)
        cofixed = (num / pool_c) if pool_c > 0 else 0.0
        eb = electron_budget(u, fluxes)
        nh4 = float(self.config.get("ammonium_availability", 0.0))
        # C:N of the fixed organic carbon against upstream reduced-nitrogen
        # (ammonium) availability — the og-nutrient-bottlenecks readout; inf-safe.
        cn = (toc / nh4) if nh4 > 0 else 0.0
        return {
            "functional_pool_carbon": pool_c,
            "pool_cofixed_fraction": cofixed,
            "functional_pool_cofixed_fraction": cofixed,
            "electrons_supplied_rate": eb["electrons_supplied_rate"],
            "electrons_fixed_rate": eb["electrons_fixed_rate"],
            "electron_budget_residual": eb["electron_budget_residual"],
            "cn_ratio": cn,
        }

    def update(self, state, interval):
        out = super().update(state, interval)
        feeds = {k: max(float(state.get(k, 0.0)), 0.0) for k in self.inputs()}
        out.update(self._functional_metrics(feeds))
        return out
