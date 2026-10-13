"""Module L — cross-feeding metacommunity (og-07, ecology before LUCA).

Campaign-VII transition: once individuals inherit a chemical phenotype (og-06),
they live in **connected pore networks**, not in isolation. This module asks what
capabilities emerge in a *metacommunity* — N connected compartments, each carrying
a coarse-grained vector over a small set of protometabolic functions — once
cross-feeding, horizontal transfer, cooperation and parasitism are allowed, versus
the same compartments run in isolation.

This is a **coarse-grained, deterministic (seeded) reproduction**, honestly labeled
— NOT a wrapped ALife/agent engine. Each compartment conceptually reuses the og-02
protometabolic capability set (H2/CO2 fixation, FeS catalysis, acetyl-CoA, …) as a
capability *vector*, rather than instantiating N heavy libRoadRunner networks; the
exchange/transfer dynamics are explicit and reproducible.

Mechanisms (all per-tick, deterministic given ``seed``):

  * **Cross-feeding** — a compartment expressing a capability its neighbour lacks
    supplies the byproduct (deficit-driven community sharing), at a rate
    ``exchange_rate / connectivity``. A metabolic chain spreads across the network
    that no single compartment runs end-to-end.
  * **Horizontal transfer (HGT)** — a capability itself spreads to connected
    compartments at ``hgt_rate`` (copied "uphill" from a neighbour that has it to one
    that does not).
  * **Parasitism / cooperation** — a seeded fraction ``parasite_load`` of
    compartments are parasites that DRAIN their neighbours' expressed capabilities;
    the remainder cooperate (their cross-feeding/HGT contribution is the sharing).
  * **Maintenance decay** — acquired (non-intrinsic) capability relaxes back toward
    the intrinsic set each tick, so a cross-fed capability persists only while it is
    continuously supplied (it is not a free permanent upgrade).

Emergent observables (not assumptions):
  * ``metacommunity_robustness`` — functional *redundancy*: each capability covered
    by >= R compartments is robust to a single compartment loss. Connected networks
    spread capabilities across compartments → higher redundancy.
  * ``isolated_robustness`` — the SAME seeded assignment scored with no exchange /
    HGT / parasitism (the within-run isolated counterfactual).
  * ``robustness_gain`` = connected − isolated (the connected-vs-isolated signal).
  * ``capability_diversity`` — mean per-compartment functional breadth (how many
    capabilities each compartment effectively expresses, intrinsic + cross-fed).
  * ``luca_capability_overlap`` — overlap of the metacommunity's collective
    capability set with the anaerobic H2/CO2/FeS LUCA reconstruction
    (``weiss2016physiology``, ``moody2024nature``), reported as a far-end **boundary**
    the emergent set approaches — NOT a target the model is tuned to hit.
"""
from __future__ import annotations

from process_bigraph import Process

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_OW_DIMLESS = {"_type": "overwrite[float]", "_units": "dimensionless"}

# Coarse-grained protometabolic capability set (conceptually the og-02 functions).
# A sparse space (12 functions, only a few intrinsic per compartment) so that an
# isolated compartment is functionally fragile and redundancy must be BUILT by the
# metacommunity rather than present by construction.
CAPABILITIES = (
    "h2_oxidation",        # 0  H2 uptake / electron bifurcation
    "co2_fixation",        # 1  carbon fixation (rTCA / Wood-Ljungdahl)
    "fes_catalysis",       # 2  FeS-cluster redox catalysis
    "acetyl_coa",          # 3  acetyl-CoA / acetogenesis
    "ion_pumping",         # 4  chemiosmotic coupling
    "amino_acid_synth",    # 5  amino-acid synthesis
    "nucleotide_synth",    # 6  nucleotide synthesis
    "cofactor_synth",      # 7  cofactor (flavin / pterin) synthesis
    "methyl_transfer",     # 8  Wood-Ljungdahl methyl branch
    "lipid_synth",         # 9  isoprenoid / fatty-acid lipid synthesis
    "electron_bifurc",     # 10 flavin-based electron bifurcation
    "formate_metab",       # 11 formate dehydrogenase / formate metabolism
)
# The Weiss-2016 anaerobic autotrophic LUCA core (H2/CO2/FeS physiology). The
# overlap of the emergent repertoire with THIS set is the reported boundary — it is
# a reconstruction constraint on capabilities eventually acquired, not evidence the
# first compartments were LUCA-like, and NOT an optimisation target.
LUCA_CORE = ("h2_oxidation", "co2_fixation", "fes_catalysis", "acetyl_coa", "ion_pumping")
_LUCA_IDX = tuple(CAPABILITIES.index(c) for c in LUCA_CORE)


class CrossFeedingMetacommunityProcess(Process):
    """Deterministic cross-feeding metacommunity over N connected compartments.

    Each compartment holds a coarse-grained capability vector over ``CAPABILITIES``.
    ``diversity`` sets how heterogeneous the intrinsic assignments are across
    compartments (0 = every compartment identical; 1 = each a different random
    subset). The process evolves the *expressed* capability matrix each tick under
    cross-feeding, horizontal transfer and parasite drain on a ring network, and
    emits metacommunity robustness (redundancy), the isolated counterfactual, their
    difference, the mean per-compartment functional breadth, and the overlap with the
    anaerobic LUCA reconstruction (a reported boundary). All outputs are overwrite
    sensors; the capability matrix is integrated internally."""

    contract = {
        "summary": "Coarse-grained deterministic cross-feeding metacommunity: do connected, heterogeneous compartments develop capability redundancy (robustness) and a collective repertoire that single compartments do not — with the anaerobic LUCA reconstruction as a far-end boundary?",
        "description": (
            "N compartments on a ring network, each carrying a capability vector over a "
            "small coarse-grained protometabolic set (conceptually the og-02 functions; "
            "NOT N heavy libRoadRunner networks). diversity sets inter-compartment "
            "heterogeneity. Per tick: cross-feeding (a compartment expressing a capability "
            "a neighbour lacks supplies the byproduct at exchange_rate/connectivity), "
            "horizontal transfer (a capability spreads to connected compartments at "
            "hgt_rate), parasite drain (a seeded parasite_load fraction drain their "
            "neighbours; the rest cooperate), and maintenance decay of acquired capability "
            "toward the intrinsic set. Emits the metacommunity robustness (functional "
            "redundancy), the no-exchange isolated counterfactual on the same seeded "
            "assignment, their difference, the mean per-compartment functional breadth, and "
            "the collective overlap with the Weiss-2016 anaerobic H2/CO2/FeS LUCA core "
            "reported as a boundary (not a target). Deterministic given seed; a coarse-"
            "grained reproduction, not a wrapped ALife engine."
        ),
        "inputs": {},
        "outputs": {
            "metacommunity_robustness": "functional redundancy of the connected metacommunity (dimensionless, 0-1)",
            "isolated_robustness": "redundancy of the same seeded assignment with no exchange/HGT/parasitism (dimensionless, 0-1)",
            "robustness_gain": "connected minus isolated robustness — the connected-vs-isolated signal (dimensionless)",
            "capability_diversity": "mean per-compartment effective functional breadth (dimensionless, 0-1)",
            "luca_capability_overlap": "fraction of the anaerobic LUCA core covered by the collective repertoire — a reported boundary (dimensionless, 0-1)",
            "mean_capability": "mean expressed capability level across all compartments and functions (dimensionless, 0-1)",
        },
        "assumptions": [
            "Coarse-grained deterministic metacommunity (reproducible given seed); honestly a reproduction, not a wrapped ALife/agent engine.",
            "Each compartment is a capability VECTOR over a small protometabolic set, not an instantiated metabolic network — cross-feeding/transfer are explicit couplings.",
            "Cross-feeding rate scales as exchange_rate/connectivity; acquired (non-intrinsic) capability decays toward the intrinsic set so it needs continuous supply.",
            "The LUCA overlap is a far-end BOUNDARY (phylogenomic constraint on capabilities eventually acquired), never a fitting target.",
        ],
        "math": [
            "intrinsic[i,k]: top-m capabilities of (1-diversity)*common[k] + diversity*personal[i,k]",
            "cross_feed[i,k] = (exchange_rate/connectivity) * sum_{j~i} max(eff[j,k]-eff[i,k], 0)  (community sharing of a byproduct you lack)",
            "hgt[i,k] = hgt_rate * max_{j~i}(eff[j,k] - eff[i,k], 0)  (capability copied from a donor)",
            "drain[i,k] = drain_coeff * (#parasite neighbours of i) * eff[i,k]",
            "acquired <- (1-decay)*acquired + cross_feed + hgt - drain ;  eff = clip(intrinsic+acquired,0,1)",
            "robustness = mean_k 1[coverage_k >= R]   (coverage_k = #{i: eff[i,k] > thr}); a capability is robust only if >= R compartments hold it",
        ],
        "symbols": {
            "eff": "expressed capability matrix (N x K)", "m": "intrinsic capabilities per compartment",
            "R": "redundancy target", "thr": "coverage threshold", "j~i": "ring neighbours of i",
        },
        "references": ["weiss2016physiology", "moody2024nature"],
    }

    config_schema = {
        "n_compartments": {"_type": "integer", "_default": 8},
        "exchange_rate": {"_type": "float", "_default": 0.3, "_units": "dimensionless"},   # cross-feeding strength
        "diversity": {"_type": "float", "_default": 0.6, "_units": "dimensionless"},       # inter-compartment heterogeneity (0-1)
        "parasite_load": {"_type": "float", "_default": 0.0, "_units": "dimensionless"},   # fraction of compartments that drain
        "hgt_rate": {"_type": "float", "_default": 0.1, "_units": "dimensionless"},        # horizontal-transfer rate
        "connectivity": {"_type": "integer", "_default": 2},                               # ring degree (neighbours per node)
        # The isolated counterfactual arm. Use this flag (NOT exchange_rate=0.0) to
        # disable exchange: process-bigraph's config merge treats a falsy 0.0 as
        # "unset" and would fall back to the non-zero default. Default False.
        "isolated": {"_type": "boolean", "_default": False},
        "seed": {"_type": "integer", "_default": 1},
        "intrinsic_per_comp": {"_type": "integer", "_default": 2},                         # m: intrinsic capabilities/compartment
        "redundancy_target": {"_type": "integer", "_default": 2},                          # R: coverage for "robust"
        "coverage_threshold": {"_type": "float", "_default": 0.35, "_units": "dimensionless"},  # thr: expressed if eff>thr
        "decay": {"_type": "float", "_default": 0.35, "_units": "dimensionless"},          # maintenance relaxation of acquired
        "drain_coeff": {"_type": "float", "_default": 0.5, "_units": "dimensionless"},     # per-parasite-neighbour drain
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        import numpy as np

        n = max(int(self.config["n_compartments"]), 2)
        k = len(CAPABILITIES)
        rng = np.random.default_rng(int(self.config["seed"]))
        div = float(np.clip(self.config["diversity"], 0.0, 1.0))
        m = int(np.clip(self.config["intrinsic_per_comp"], 1, k))

        # Intrinsic assignment: mix a SHARED common propensity with a per-compartment
        # personal one. diversity=0 -> every compartment keeps the same common top-m
        # (identical, nothing to cross-feed); diversity=1 -> each keeps its own random
        # top-m (heterogeneous — the raw material cross-feeding/HGT act on). Density
        # fixed at m per compartment regardless of diversity.
        common = rng.random(k)
        personal = rng.random((n, k))
        propensity = (1.0 - div) * common[None, :] + div * personal
        intrinsic = np.zeros((n, k))
        for i in range(n):
            top = np.argsort(propensity[i])[::-1][:m]
            intrinsic[i, top] = 1.0
        self._intrinsic = intrinsic
        self._eff = intrinsic.copy()
        self._acquired = np.zeros((n, k))

        # Ring neighbours (connectivity neighbours, split either side).
        deg = max(int(self.config["connectivity"]), 1)
        half = max(deg // 2, 1)
        neighbours = []
        for i in range(n):
            nb = set()
            for d in range(1, half + 1):
                nb.add((i - d) % n)
                nb.add((i + d) % n)
            nb.discard(i)
            neighbours.append(sorted(nb))
        self._neighbours = neighbours
        self._deg = max(float(np.mean([len(nb) for nb in neighbours])), 1.0)

        # Seeded parasites: a fraction parasite_load of compartments drain neighbours.
        pl = float(np.clip(self.config["parasite_load"], 0.0, 1.0))
        n_par = int(round(pl * n))
        order = rng.permutation(n)
        self._is_parasite = np.zeros(n, dtype=bool)
        self._is_parasite[order[:n_par]] = True
        # Per-compartment count of parasite neighbours (drain they receive).
        self._par_nbr_count = np.array(
            [sum(1 for j in neighbours[i] if self._is_parasite[j]) for i in range(n)], dtype=float)

        self._n, self._k = n, k

    def inputs(self):
        return {}

    def outputs(self):
        return {
            "metacommunity_robustness": _OW_DIMLESS,
            "isolated_robustness": _OW_DIMLESS,
            "robustness_gain": _OW_DIMLESS,
            "capability_diversity": _OW_DIMLESS,
            "luca_capability_overlap": _OW_DIMLESS,
            "mean_capability": _OW_DIMLESS,
        }

    def _robustness(self, cap) -> float:
        import numpy as np
        thr = float(self.config["coverage_threshold"])
        r = max(int(self.config["redundancy_target"]), 1)
        coverage = (cap > thr).sum(axis=0)                 # per-capability coverage count
        # A capability is robust only if at least R compartments hold it (survives a
        # single-compartment loss). Singly-covered capabilities are fragile → not robust.
        return float(np.mean((coverage >= r).astype(float)))

    def _diversity(self, cap) -> float:
        import numpy as np
        thr = float(self.config["coverage_threshold"])
        return float(np.mean((cap > thr).sum(axis=1) / self._k))

    def _luca_overlap(self, cap) -> float:
        import numpy as np
        thr = float(self.config["coverage_threshold"])
        covered = (cap > thr).sum(axis=0) > 0              # per-capability union coverage
        idx = list(_LUCA_IDX)
        return float(covered[idx].sum() / len(idx))

    def update(self, state, interval):
        import numpy as np

        eff = self._eff
        # The isolated counterfactual: no cross-feeding, no HGT, no parasite drain —
        # each compartment keeps only its intrinsic capabilities. (Use the flag, not
        # a 0.0 rate, because the config merge ignores a falsy override.)
        isolated = bool(self.config["isolated"])
        ex = 0.0 if isolated else float(self.config["exchange_rate"]) / self._deg
        hgt = 0.0 if isolated else float(self.config["hgt_rate"])
        decay = float(np.clip(self.config["decay"], 0.0, 1.0))
        drain_coeff = 0.0 if isolated else float(self.config["drain_coeff"])

        cross = np.zeros_like(eff)
        transfer = np.zeros_like(eff)
        for i, nb in enumerate(self._neighbours):
            if not nb:
                continue
            deficit = np.maximum(eff[nb, :] - eff[i][None, :], 0.0)   # (deg, K): what each neighbour can supply
            # Cross-feeding: a neighbour expressing a capability YOU lack supplies its
            # byproduct — additive community sharing (needs heterogeneity: no deficit
            # between identical compartments → nothing to share).
            cross[i] = ex * deficit.sum(axis=0)
            # HGT: the capability itself is copied from the best donor (needs a donor
            # that has it and you do not).
            transfer[i] = hgt * deficit.max(axis=0)

        drain = drain_coeff * self._par_nbr_count[:, None] * eff
        self._acquired = (1.0 - decay) * self._acquired + cross + transfer - drain
        self._eff = np.clip(self._intrinsic + self._acquired, 0.0, 1.0)

        robustness = self._robustness(self._eff)
        isolated_rob = self._robustness(self._intrinsic)
        return {
            "metacommunity_robustness": robustness,
            "isolated_robustness": isolated_rob,
            "robustness_gain": robustness - isolated_rob,
            "capability_diversity": self._diversity(self._eff),
            "luca_capability_overlap": self._luca_overlap(self._eff),
            "mean_capability": float(np.mean(self._eff)),
        }


def metacommunity_state(proc: "CrossFeedingMetacommunityProcess") -> dict:
    """The current expressed capability matrix + layout for the viz — every value a
    real metacommunity state. Returns ``{capabilities, luca_core, eff, intrinsic,
    is_parasite}``."""
    if getattr(proc, "_eff", None) is None:
        return {"capabilities": list(CAPABILITIES), "luca_core": list(LUCA_CORE),
                "eff": [], "intrinsic": [], "is_parasite": []}
    return {
        "capabilities": list(CAPABILITIES),
        "luca_core": list(LUCA_CORE),
        "eff": proc._eff.tolist(),
        "intrinsic": proc._intrinsic.tolist(),
        "is_parasite": proc._is_parasite.tolist(),
    }
