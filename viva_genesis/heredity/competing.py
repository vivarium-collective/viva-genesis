"""Competing heredity — six model classes behind one ``heredity`` face (Phase 7).

og-06's ``LineageReplicatorProcess`` chose its inheritance mechanism with a
``module`` string *inside* one class (template / compositional / hybrid /
non-heritable) and advanced a mean-field "generation" per tick. The Model
Upgrade plan (Phase 7, FMP §2.5) asks for the opposite structure: **each
mechanism is its own Process class on a typed face**, attached to a lineage
*conditionally* under matched resource + energy budgets, and simulated
**exactly at low copy number** — so the classes are compared on what they
actually transmit per joule and per precursor molecule, not on a mean-field
score.

What is here
------------
* :class:`CompetingLineage` — an exact Gillespie (direct-method) simulation of a
  population of protocell-scale individuals. Every individual carries a few
  tens of heritable molecules (``N0``..``N_max``), a bulk mass that grows at
  ``k_grow (1 + sigma * phi)`` (``phi`` = the function its heritable state
  confers, in [0, 1]; ``sigma`` = Eigen's selective superiority) and divides
  at ``2 m0``. Every molecular event (template copy, de-novo synthesis,
  incorporation, layer growth, decay) is one reaction channel with a
  propensity; copies draw **integer** precursor molecules from one shared
  pool and integer energy quanta from one shared store, so the budgets are
  matched across classes by construction and the ledgers are exact.
* Six :class:`HeredityKinetics` — the state space, channels, costs and
  phenotype of each class:

  ========================  =================================================================  ====================  ==========
  class                     heritable state / copy mechanism                                    precursor pool        quanta/copy
  ========================  =================================================================  ====================  ==========
  ``rna_like``              L-site template, template-directed copy, per-site fidelity q        nucleotide_precursor  L
  ``peptide``               L_p-site peptide, weak sequence-templated ligation (q_p)            amino_precursor       L_p
  ``compositional``         GARD composition over K amphiphile types, mutual catalysis (beta)   amphiphile            0
  ``network``               M autocatalytic cores, growth by autocatalysis, loss by dilution    amino_precursor       1
  ``mineral_state``         B-bit surface pattern copied layer-by-layer (defect error p_m)      mineral_precursor     0
  ``hybrid``                short template (L_h) that focuses a GARD composition                nucleotide + amphiphile  L_h
  ========================  =================================================================  ====================  ==========

* Six thin ``Process`` wrappers (``RnaLikeHeredityProcess`` ...) that honour
  the ``heredity`` face (``viva_genesis.models``), read the shared pools and
  the energy store, write their *consumption* back as additive deltas, and
  publish the lineage sensors, the running mutual-information estimate with
  its convergence flag (``viva_genesis.heredity.information``) and the
  per-copy costs the information ledger integrates.
* :class:`HeredityAttachmentStep` — FMP §2.5: heredity is *absent* until the
  precursor budget, the energy budget and the class's expected copy fidelity
  cross their thresholds. Before attachment a lineage's heritable material
  re-forms **de novo** at every division (daughters are not copies of their
  parent): that is og-06's non-heritable control, obtained here as the
  unattached state of every class rather than as a seventh module. The
  precursor / energy thresholds are ``hypothetical`` (expert input needed;
  swept); the fidelity floor is Eigen's error threshold ``Q >= 1/sigma``.
"""

from __future__ import annotations

import math

import numpy as np
from process_bigraph import Process, Step

from .information import heritability_slope, mi_with_convergence

HEREDITY_CLASSES = ("compositional", "network", "peptide", "rna_like", "hybrid", "mineral_state")
POOLS = ("nucleotide_precursor", "amino_precursor", "amphiphile", "mineral_precursor")

AVOGADRO = 6.02214076e23
_KJ_PER_MOL_TO_J = 1.0e3 / AVOGADRO

_DIMLESS = {"_type": "float", "_units": "dimensionless"}
_MOLAR = {"_type": "float", "_units": "molar"}
_J = {"_type": "float", "_units": "joule"}
_K = {"_type": "float", "_units": "kelvin"}
_OVW = {"_type": "overwrite[float]", "_units": "dimensionless"}
_OVW_BIT = {"_type": "overwrite[float]", "_units": "bit"}
_OVW_J = {"_type": "overwrite[float]", "_units": "joule"}


# --------------------------------------------------------------------------- #
# Shared configuration (every parameter is a vg-data ``inheritance_budgets`` entry)
# --------------------------------------------------------------------------- #
DEFAULTS = {
    # lineage / individual
    "n_individuals": 32, "n0_molecules": 16, "n_max_molecules": 48, "division_mass": 20,
    "base_growth_rate": 0.35, "selective_superiority": 3.0,
    "individual_volume": 1.0e-18, "pool_volume_multiplier": 10.0,
    # budgets
    "energy_quantum_kj": 30.0, "nominal_feed": 1.0e-4,
    "precursor_energy_equivalent": {"nucleotide_precursor": 3.0, "amino_precursor": 1.0,
                                    "amphiphile": 2.0, "mineral_precursor": 0.1},
    # rna_like / hybrid template
    "template_length": 30, "per_site_fidelity": 0.967, "k_replicate": 1.0, "k_degrade": 0.05,
    "k_denovo": 0.05, "hybrid_template_length": 8, "hybrid_focus": 2.0,
    # peptide
    "peptide_length": 8, "peptide_fidelity": 0.7, "peptide_alphabet": 20,
    # compositional
    "composition_types": 8, "catalysis_sd": 1.0, "k_incorporate": 2.0, "k_release": 0.05,
    # network
    "network_cores": 4, "k_autocatalysis": 0.6, "k_spontaneous": 0.02,
    # mineral_state
    "mineral_bits": 16, "defect_copy_error": 0.005, "k_layer": 6.0, "k_dissolve": 0.05,
    # attachment thresholds (hypothetical; swept)
    "attach_min_copies": 10.0, "attach_energy_margin": 1.0,
}


FUNCTION_HALF, FUNCTION_WIDTH = 0.8, 0.04


def function_from_match(match, half: float = FUNCTION_HALF, width: float = FUNCTION_WIDTH):
    """The common genotype->function landscape of every class: a sigmoid in the
    match fraction (fraction of correct sites / composome similarity / pattern
    match), half-maximal at ``half`` with width ``width`` — function needs most
    of the state right (a single-peak-with-plateau landscape: the Eigen master
    and its near-neutral neighbours are functional, the error tail is not).
    A random 4-letter sequence (match 0.25) scores ~0; a perfect one ~1."""
    return 1.0 / (1.0 + np.exp(-(np.asarray(match, dtype=float) - half) / width))


def _phi_from_fraction(frac: float) -> float:
    return float(function_from_match(frac))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# --------------------------------------------------------------------------- #
# Class kinetics
# --------------------------------------------------------------------------- #
class HeredityKinetics:
    """State space + reaction channels + costs + phenotype of one heredity class.

    ``channels`` lists ``(name, pool_or_None, precursor_cost, quanta_cost, is_copy)``;
    :meth:`propensities` returns the per-individual *base* propensity of each
    channel (the shared pool / energy availability multiplies it in the SSA).
    """

    name = "abstract"
    channels: list[tuple[str, str | None, int, int, bool]] = []
    primary_pool: str = "nucleotide_precursor"

    def __init__(self, cfg: dict, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.n0 = int(cfg["n0_molecules"])
        self.n_max = int(cfg["n_max_molecules"])

    # state --------------------------------------------------------------
    def denovo(self, n: int | None = None) -> np.ndarray:
        """A fresh heritable state of ``n`` (default n0) molecules formed from the environment."""
        raise NotImplementedError

    def founder(self) -> np.ndarray:
        """A functional founder state (og-06's convention: founders carry the function;
        the question is whether the lineage KEEPS it)."""
        raise NotImplementedError

    def count(self, row: np.ndarray) -> int:
        return int(row.sum())

    def phenotype(self, row: np.ndarray) -> float:
        raise NotImplementedError

    def split(self, row: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Random binomial partition of every molecule type (fission)."""
        a = self.rng.binomial(row.astype(int), 0.5)
        return a.astype(float), (row - a).astype(float)

    def overlap(self, parent: np.ndarray, daughter: np.ndarray) -> float:
        return _cosine(parent, daughter)

    def capacity_bits(self) -> float:
        raise NotImplementedError

    def expected_fidelity(self) -> float:
        """The whole-state copy fidelity the attachment step compares with 1/sigma."""
        raise NotImplementedError

    # kinetics -----------------------------------------------------------
    def propensities(self, row: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def apply(self, row: np.ndarray, channel: int) -> np.ndarray:
        raise NotImplementedError


class _TemplateKinetics(HeredityKinetics):
    """Shared by rna_like / peptide / the hybrid's template: a histogram over the
    number of correct sites c in [0, L] of each template molecule."""

    alphabet = 4

    def __init__(self, cfg, rng, *, length: int, q: float, pool: str, k_rep: float,
                 weight_functional: bool = False):
        super().__init__(cfg, rng)
        self.L = int(length)
        self.q = float(q)
        self.k_rep = float(k_rep)
        self.k_deg = float(cfg["k_degrade"])
        self.k_syn = float(cfg["k_denovo"])
        self.weight_functional = weight_functional
        self.sigma = float(cfg["selective_superiority"])
        self.primary_pool = pool
        self.channels = [("replicate", pool, self.L, self.L, True),
                         ("degrade", None, 0, 0, False),
                         ("denovo", pool, self.L, self.L, False)]
        self._frac = np.arange(self.L + 1) / self.L
        self._g = function_from_match(self._frac)

    def denovo(self, n: int | None = None) -> np.ndarray:
        n = self.n0 if n is None else int(n)
        row = np.zeros(self.L + 1)
        if n > 0:
            cs = self.rng.binomial(self.L, 1.0 / self.alphabet, size=n)
            np.add.at(row, cs, 1.0)
        return row

    def founder(self) -> np.ndarray:
        row = np.zeros(self.L + 1)
        row[int(round(0.95 * self.L))] = float(self.n0)
        return row

    def phenotype(self, row):
        n = row.sum()
        if n <= 0:
            return 0.0
        return float(np.dot(row, self._g) / n)

    def capacity_bits(self) -> float:
        return float(self.L * math.log2(self.alphabet))

    def expected_fidelity(self) -> float:
        return float(self.q ** self.L)

    def _weights(self, row):
        # Eigen: a template's own copy rate rises with its function (the master sequence
        # replicates sigma-fold faster than the error tail) — molecular-level selection
        return row * (1.0 + self.sigma * self._g)

    def _rep_weight(self, row):
        return float(self._weights(row).sum())

    def propensities(self, row):
        n = row.sum()
        rep = self.k_rep * self._rep_weight(row) if n < self.n_max else 0.0
        return np.array([rep, self.k_deg * n, self.k_syn if n < self.n_max else 0.0])

    def _pick(self, row, weights):
        w = weights / weights.sum()
        return int(self.rng.choice(len(row), p=w))

    def apply(self, row, channel):
        row = row.copy()
        if channel == 0:   # template-directed copy
            c = self._pick(row, self._weights(row))
            keep = self.rng.binomial(c, self.q)
            back = self.rng.binomial(self.L - c, (1.0 - self.q) / (self.alphabet - 1))
            row[keep + back] += 1.0
        elif channel == 1:
            c = self._pick(row, row)
            row[c] -= 1.0
        else:              # de-novo (non-templated) polymerisation
            c = self.rng.binomial(self.L, 1.0 / self.alphabet)
            row[c] += 1.0
        return row


class RnaLikeKinetics(_TemplateKinetics):
    name = "rna_like"

    def __init__(self, cfg, rng):
        super().__init__(cfg, rng, length=cfg["template_length"], q=cfg["per_site_fidelity"],
                         pool="nucleotide_precursor", k_rep=cfg["k_replicate"])


class PeptideKinetics(_TemplateKinetics):
    name = "peptide"

    def __init__(self, cfg, rng):
        self.alphabet = int(cfg["peptide_alphabet"])
        super().__init__(cfg, rng, length=cfg["peptide_length"], q=cfg["peptide_fidelity"],
                         pool="amino_precursor", k_rep=cfg["k_replicate"], weight_functional=True)


class CompositionalKinetics(HeredityKinetics):
    """GARD (Segré 2000): an assembly's composition over K types grows by
    mutually-catalysed incorporation (lognormal beta) and is inherited by
    fission; two competing composomes (A functional, B not) are the
    self-sustaining attractors the beta matrix carries."""

    name = "compositional"
    primary_pool = "amphiphile"

    def __init__(self, cfg, rng, *, focus_from=None):
        super().__init__(cfg, rng)
        self.K = int(cfg["composition_types"])
        self.k_in = float(cfg["k_incorporate"])
        self.k_out = float(cfg["k_release"])
        self.channels = [("incorporate", "amphiphile", 1, 0, False), ("release", None, 0, 0, False)]
        mrng = np.random.default_rng(12345)       # the beta matrix is a fixed chemistry, not a seed
        self.beta = np.exp(mrng.normal(0.0, float(cfg["catalysis_sd"]), size=(self.K, self.K)))
        self.A = np.zeros(self.K); self.A[: max(self.K // 3, 1)] = 1.0
        self.B = np.zeros(self.K); self.B[max(self.K // 3, 1): 2 * max(self.K // 3, 1)] = 1.0
        # composome blocks: mutual catalysis within A and within B strong enough to hold
        # an attractor against the K-type background (strength = K, the GARD regime)
        self.beta += float(self.K) * (np.outer(self.A, self.A) + np.outer(self.B, self.B))
        self.focus = 0.0

    def denovo(self, n: int | None = None) -> np.ndarray:
        n = self.n0 if n is None else int(n)
        return self.rng.multinomial(n, np.full(self.K, 1.0 / self.K)).astype(float)

    def founder(self) -> np.ndarray:
        w = 0.2 / self.K + 0.8 * self.A / self.A.sum()
        return self.rng.multinomial(self.n0, w / w.sum()).astype(float)

    def phenotype(self, row):
        return float(function_from_match(_cosine(row, self.A)))

    def capacity_bits(self) -> float:
        # log2 of the number of compositions of n0 molecules over K types
        return float(math.log2(math.comb(self.n0 + self.K - 1, self.K - 1)))

    def expected_fidelity(self) -> float:
        return float(1.0 - 1.0 / math.sqrt(max(self.n0, 1)))

    def _rates(self, row):
        n = row.sum()
        frac = row / n if n > 0 else np.full(self.K, 1.0 / self.K)
        beta = self.beta + self.focus * np.outer(self.A, self.A)
        return self.k_in * (1.0 + beta @ frac) / self.K

    def propensities(self, row):
        n = row.sum()
        inc = float(self._rates(row).sum()) if n < self.n_max else 0.0
        return np.array([inc, self.k_out * n])

    def apply(self, row, channel):
        row = row.copy()
        if channel == 0:
            r = self._rates(row)
            k = int(self.rng.choice(self.K, p=r / r.sum()))
            row[k] += 1.0
        else:
            k = int(self.rng.choice(self.K, p=row / row.sum()))
            row[k] -= 1.0
        return row


class NetworkKinetics(HeredityKinetics):
    """Attractor heredity in an autocatalytic network (Vasas 2010): M cores
    grow autocatalytically from a precursor, are lost by dilution at fission,
    and re-seed only by rare spontaneous formation; what is inherited is which
    cores are occupied (M bits at most)."""

    name = "network"
    primary_pool = "amino_precursor"

    def __init__(self, cfg, rng):
        super().__init__(cfg, rng)
        self.M = int(cfg["network_cores"])
        self.k_cat = float(cfg["k_autocatalysis"])
        self.k_spont = float(cfg["k_spontaneous"])
        self.k_deg = float(cfg["k_degrade"])
        self.channels = [("autocatalysis", "amino_precursor", 1, 1, True),
                         ("spontaneous", "amino_precursor", 1, 1, False),
                         ("decay", None, 0, 0, False)]
        self.F = np.zeros(self.M); self.F[: max(self.M // 2, 1)] = 1.0   # the functional cores
        self.K_half = 1.0

    def denovo(self, n: int | None = None) -> np.ndarray:
        n = self.n0 if n is None else int(n)
        return self.rng.multinomial(n, np.full(self.M, 1.0 / self.M)).astype(float)

    def founder(self) -> np.ndarray:
        w = 0.2 / self.M + 0.8 * self.F / self.F.sum()
        return self.rng.multinomial(self.n0, w / w.sum()).astype(float)

    def phenotype(self, row):
        f = row[self.F > 0]
        return float(function_from_match(np.mean(f / (f + self.K_half))))

    def capacity_bits(self) -> float:
        return float(self.M)

    def expected_fidelity(self) -> float:
        per_core = self.n0 / self.M
        p_keep = 1.0 - 0.5 ** per_core
        return float(p_keep ** float(self.F.sum()))

    def _auto(self, row):
        # each core grows autocatalytically in its own niche (carrying capacity n_max / M),
        # so cores coexist and what is inherited is WHICH cores are occupied
        niche = self.n_max / self.M
        return self.k_cat * row * np.clip(1.0 - row / niche, 0.0, None)

    def propensities(self, row):
        n = row.sum()
        room = 1.0 if n < self.n_max else 0.0
        return np.array([float(self._auto(row).sum()) * room, self.k_spont * self.M * room, self.k_deg * n])

    def apply(self, row, channel):
        row = row.copy()
        if channel == 0:
            a = self._auto(row)
            m = int(self.rng.choice(self.M, p=a / a.sum()))
            row[m] += 1.0
        elif channel == 1:
            row[int(self.rng.integers(self.M))] += 1.0
        else:
            m = int(self.rng.choice(self.M, p=row / row.sum()))
            row[m] -= 1.0
        return row


class MineralStateKinetics(HeredityKinetics):
    """Cairns-Smith mineral heredity: a B-bit defect pattern on a growing
    crystal face is copied into each new layer with per-bit error p_m; the
    'molecules' are layers; cleavage hands both daughters the face pattern."""

    name = "mineral_state"
    primary_pool = "mineral_precursor"

    def __init__(self, cfg, rng):
        super().__init__(cfg, rng)
        self.B = int(cfg["mineral_bits"])
        self.p_err = float(cfg["defect_copy_error"])
        self.k_lay = float(cfg["k_layer"])
        self.k_dis = float(cfg["k_dissolve"])
        self.channels = [("grow_layer", "mineral_precursor", 1, 0, True), ("dissolve", None, 0, 0, False)]
        self.target = (np.arange(self.B) % 2).astype(float)

    def denovo(self, n: int | None = None) -> np.ndarray:
        n = self.n0 if n is None else int(n)
        bits = self.rng.integers(0, 2, size=self.B).astype(float)
        return np.concatenate([bits, [float(n)]])

    def founder(self) -> np.ndarray:
        flips = self.rng.random(self.B) < 0.05
        bits = np.where(flips, 1.0 - self.target, self.target)
        return np.concatenate([bits, [float(self.n0)]])

    def count(self, row):
        return int(row[-1])

    def phenotype(self, row):
        frac = float(np.mean(row[: self.B] == self.target))
        return _phi_from_fraction(frac)

    def capacity_bits(self) -> float:
        return float(self.B)

    def expected_fidelity(self) -> float:
        # the layers regrown per generation (n0/2 after cleavage halves them), each copying B bits
        return float((1.0 - self.p_err) ** (self.B * max(self.n0 // 2, 1)))

    def split(self, row):
        layers = int(row[-1])
        a = self.rng.binomial(layers, 0.5)
        ra, rb = row.copy(), row.copy()
        ra[-1], rb[-1] = float(a), float(layers - a)
        return ra, rb

    def overlap(self, parent, daughter):
        return float(np.mean(parent[: self.B] == daughter[: self.B]))

    def propensities(self, row):
        n = row[-1]
        return np.array([self.k_lay if n < self.n_max else 0.0, self.k_dis * n])

    def apply(self, row, channel):
        row = row.copy()
        if channel == 0:
            flips = self.rng.random(self.B) < self.p_err
            row[: self.B] = np.where(flips, 1.0 - row[: self.B], row[: self.B])
            row[-1] += 1.0
        else:
            row[-1] = max(row[-1] - 1.0, 0.0)
        return row


class HybridKinetics(HeredityKinetics):
    """A short template (L_h sites) whose function focuses a GARD composition
    on the functional composome: cheap like composition, heritable like a
    template. State = template histogram ++ composition counts."""

    name = "hybrid"
    primary_pool = "nucleotide_precursor"

    def __init__(self, cfg, rng):
        super().__init__(cfg, rng)
        tcfg = dict(cfg, n0_molecules=max(int(cfg["n0_molecules"]) // 2, 4),
                    n_max_molecules=max(int(cfg["n_max_molecules"]) // 2, 8))
        self.t = _TemplateKinetics(tcfg, rng, length=cfg["hybrid_template_length"], q=cfg["per_site_fidelity"],
                                   pool="nucleotide_precursor", k_rep=cfg["k_replicate"])
        self.c = CompositionalKinetics(cfg, rng)
        self.focus_gain = float(cfg["hybrid_focus"])
        self.nt = self.t.L + 1
        self.channels = list(self.t.channels) + list(self.c.channels)

    def _parts(self, row):
        return row[: self.nt], row[self.nt:]

    def denovo(self, n: int | None = None):
        if n is None:
            return np.concatenate([self.t.denovo(), self.c.denovo()])
        nt = int(round(n * self.t.n0 / max(self.t.n0 + self.c.n0, 1)))
        return np.concatenate([self.t.denovo(nt), self.c.denovo(int(n) - nt)])

    def founder(self):
        return np.concatenate([self.t.founder(), self.c.founder()])

    def count(self, row):
        return int(row.sum())

    def phenotype(self, row):
        _, comp = self._parts(row)
        return self.c.phenotype(comp)

    def capacity_bits(self):
        return self.t.capacity_bits() + self.c.capacity_bits()

    def expected_fidelity(self):
        return self.t.expected_fidelity()

    def propensities(self, row):
        tpl, comp = self._parts(row)
        self.c.focus = self.focus_gain * self.t.phenotype(tpl)
        return np.concatenate([self.t.propensities(tpl), self.c.propensities(comp)])

    def apply(self, row, channel):
        tpl, comp = self._parts(row)
        nt_ch = len(self.t.channels)
        if channel < nt_ch:
            tpl = self.t.apply(tpl, channel)
        else:
            self.c.focus = self.focus_gain * self.t.phenotype(tpl)
            comp = self.c.apply(comp, channel - nt_ch)
        return np.concatenate([tpl, comp])


KINETICS = {
    "rna_like": RnaLikeKinetics, "peptide": PeptideKinetics, "compositional": CompositionalKinetics,
    "network": NetworkKinetics, "mineral_state": MineralStateKinetics, "hybrid": HybridKinetics,
}


def make_kinetics(name: str, cfg: dict | None = None, seed: int = 0) -> HeredityKinetics:
    if name not in KINETICS:
        raise KeyError(f"unknown heredity class {name!r}; have {sorted(KINETICS)}")
    full = {**DEFAULTS, **(cfg or {})}
    return KINETICS[name](full, np.random.default_rng(int(seed)))


# --------------------------------------------------------------------------- #
# The exact Gillespie lineage
# --------------------------------------------------------------------------- #
class CompetingLineage:
    """A population of individuals, one heredity class, exact SSA at low copy number.

    ``pools`` / ``quanta`` are the shared integer budgets the SSA draws from
    (set them before each :meth:`advance`); consumption is accumulated in
    ``consumed`` / ``quanta_used`` so the caller can write exact deltas back.
    ``attached`` switches inheritance on: when False, daughters re-form their
    heritable state de novo at fission (the non-heritable control) and no
    copy channel runs.
    """

    def __init__(self, heredity_class: str, cfg: dict | None = None, *, seed: int = 0):
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.rng = np.random.default_rng(int(seed))
        self.kin = KINETICS[heredity_class](self.cfg, self.rng)
        self.name = heredity_class
        self.cap = int(self.cfg["n_individuals"])
        self.m0 = int(self.cfg["division_mass"])
        self.k_grow = float(self.cfg["base_growth_rate"])
        self.sigma = float(self.cfg["selective_superiority"])
        self.attached = False
        self.time = 0.0
        self.generation = 0
        # shared budgets (integers) + exact consumption counters
        self.pools: dict[str, int] = {p: 0 for p in POOLS}
        self.pool_nominal: dict[str, int] = {p: 1 for p in POOLS}
        self.quanta = 0
        self.consumed: dict[str, int] = {p: 0 for p in POOLS}
        self.quanta_used = 0
        self.copies = 0
        self.births = 0
        self.events = 0
        # lineage records
        self.pairs: list[tuple[float, float]] = []
        self.overlaps: list[float] = []
        self.nodes: list[dict] = []
        self._nid = 0
        # population arrays
        n = self.cap
        self.H = np.stack([self.kin.founder() for _ in range(n)])
        self.bulk = np.full(n, float(self.m0))
        self.phi = np.array([self.kin.phenotype(r) for r in self.H])
        self.ids = np.arange(n)
        self._nid = n
        self.gen_of = np.zeros(n, dtype=int)
        for i in range(n):
            self.nodes.append({"id": int(i), "parent": -1, "gen": 0, "phi": round(float(self.phi[i]), 4)})
        self.n_ch = len(self.kin.channels)
        self.P = np.zeros((n, self.n_ch + 1))
        for i in range(n):
            self._refresh(i)

    # --- propensities -------------------------------------------------------
    def _refresh(self, i: int) -> None:
        base = self.kin.propensities(self.H[i])
        # the heritable material grows with the SAME function-driven metabolism that
        # grows the bulk (1 + sigma phi): a cell whose heredity confers function both
        # divides faster and makes its heritable molecules faster (matched coupling
        # across classes); pure decay channels are not coupled
        metab = 1.0 + self.sigma * float(self.phi[i])
        for c, ch in enumerate(self.kin.channels):
            if ch[1] is not None:
                base[c] *= metab
            if not self.attached and ch[4]:
                base[c] = 0.0
        self.P[i, : self.n_ch] = base
        self.P[i, self.n_ch] = self.k_grow * self.bulk[i] * (1.0 + self.sigma * self.phi[i])

    def _factors(self) -> np.ndarray:
        g = np.ones(self.n_ch + 1)
        for c, (_, pool, cost_p, cost_q, _) in enumerate(self.kin.channels):
            if pool is not None:
                if self.pools[pool] < cost_p or self.quanta < cost_q:
                    g[c] = 0.0
                else:
                    g[c] = self.pools[pool] / max(self.pool_nominal[pool], 1)
            elif cost_q > 0 and self.quanta < cost_q:
                g[c] = 0.0
        return g

    # --- the SSA ------------------------------------------------------------
    def advance(self, tau: float) -> None:
        t = 0.0
        while True:
            g = self._factors()
            col = self.P.sum(axis=0) * g
            a0 = float(col.sum())
            if a0 <= 0.0:
                break
            dt = self.rng.exponential(1.0 / a0)
            if t + dt > tau:
                break
            t += dt
            c = int(np.searchsorted(np.cumsum(col), self.rng.random() * a0))
            c = min(c, self.n_ch)
            w = self.P[:, c]
            i = int(np.searchsorted(np.cumsum(w), self.rng.random() * w.sum()))
            i = min(i, len(w) - 1)
            self.events += 1
            if c == self.n_ch:
                self.bulk[i] += 1.0
                if self.bulk[i] >= 2 * self.m0:
                    self._divide(i)
                else:
                    self.P[i, self.n_ch] = self.k_grow * self.bulk[i] * (1.0 + self.sigma * self.phi[i])
                continue
            _, pool, cost_p, cost_q, is_copy = self.kin.channels[c]
            if pool is not None:
                self.pools[pool] -= cost_p
                self.consumed[pool] += cost_p
            self.quanta -= cost_q
            self.quanta_used += cost_q
            if is_copy:
                self.copies += 1
            self.H[i] = self.kin.apply(self.H[i], c)
            self.phi[i] = self.kin.phenotype(self.H[i])
            self._refresh(i)
        self.time += tau
        self.generation += 1

    def _divide(self, i: int) -> None:
        parent_phi = float(self.phi[i])
        parent_state = self.H[i].copy()
        parent_id = int(self.ids[i])
        if self.attached:
            ha, hb = self.kin.split(parent_state)
        else:
            ha, hb = self._paid_denovo(), self._paid_denovo()
        gen = int(self.gen_of[i]) + 1
        # daughter A takes the parent's slot
        self._place(i, ha, parent_id, gen, parent_phi, parent_state)
        # daughter B: a new slot, or dilution of a random individual at capacity
        if len(self.ids) < self.cap:
            self.H = np.vstack([self.H, hb[None, :]])
            self.bulk = np.append(self.bulk, float(self.m0))
            self.phi = np.append(self.phi, 0.0)
            self.ids = np.append(self.ids, 0)
            self.gen_of = np.append(self.gen_of, 0)
            self.P = np.vstack([self.P, np.zeros((1, self.n_ch + 1))])
            j = len(self.ids) - 1
        else:
            others = [k for k in range(len(self.ids)) if k != i]
            j = int(self.rng.choice(others))
        self._place(j, hb, parent_id, gen, parent_phi, parent_state)
        self.births += 2

    def _paid_denovo(self) -> np.ndarray:
        """Unattached control: a daughter's heritable material is synthesised afresh
        from the SAME pool at the class's per-molecule cost (matched budgets), so
        it gets only as many molecules as the pool and the store can pay for."""
        ch = [c for c in self.kin.channels if c[1] is not None]
        pool, cost_p, cost_q = (ch[0][1], ch[0][2], ch[0][3]) if ch else (None, 0, 0)
        n = self.kin.n0
        if pool is not None:
            if cost_p > 0:
                n = min(n, self.pools[pool] // cost_p)
            if cost_q > 0:
                n = min(n, self.quanta // cost_q)
            n = max(int(n), 0)
            self.pools[pool] -= n * cost_p
            self.consumed[pool] += n * cost_p
            self.quanta -= n * cost_q
            self.quanta_used += n * cost_q
        return self.kin.denovo(n)

    def _place(self, slot: int, h: np.ndarray, parent_id: int, gen: int,
               parent_phi: float, parent_state: np.ndarray) -> None:
        self.H[slot] = h
        self.bulk[slot] = float(self.m0)
        self.phi[slot] = self.kin.phenotype(h)
        self.ids[slot] = self._nid
        self.gen_of[slot] = gen
        self.nodes.append({"id": int(self._nid), "parent": int(parent_id), "gen": int(gen),
                           "phi": round(float(self.phi[slot]), 4)})
        self._nid += 1
        self.pairs.append((parent_phi, float(self.phi[slot])))
        self.overlaps.append(self.kin.overlap(parent_state, h))
        self._refresh(slot)

    # --- readouts -------------------------------------------------------------
    def mean_molecules(self) -> float:
        return float(np.mean([self.kin.count(r) for r in self.H])) if len(self.H) else 0.0

    def summary(self) -> dict:
        phis = self.phi
        return {"population": int(len(self.ids)), "mean_function": float(phis.mean()) if len(phis) else 0.0,
                "functional_fraction": float((phis > 0.5).mean()) if len(phis) else 0.0,
                "lineage_depth": int(self.gen_of.max()) if len(self.gen_of) else 0,
                "mean_molecules": self.mean_molecules(),
                "n_pairs": len(self.pairs), "births": self.births, "copies": self.copies, "events": self.events}

    def fidelity(self) -> float:
        if not self.overlaps:
            return float("nan")
        return float(np.mean(self.overlaps[-200:]))

    def heritability(self) -> float:
        if not self.pairs:
            return float("nan")
        pp = np.asarray(self.pairs)
        return heritability_slope(pp[:, 0], pp[:, 1])

    def information(self, **kw) -> dict:
        if not self.pairs:
            return mi_with_convergence([], [])
        pp = np.asarray(self.pairs)
        return mi_with_convergence(pp[:, 0], pp[:, 1], **kw)


def simulate_competing(heredity_class: str, *, n_ticks: int = 40, attached: bool = True, seed: int = 0,
                       cfg: dict | None = None, feeds: dict | None = None, energy_feed_quanta: float | None = None,
                       feed_rate: float = 0.5) -> dict:
    """Headless run of one class under chemostat-fed matched budgets (for sweeps and tests).

    Returns the lineage sensors, the MI/convergence dict, costs per offspring
    and the lineage tree. ``feeds`` overrides the nominal molar feed of each
    pool; ``energy_feed_quanta`` is the quanta supplied per tick (default
    ``500 * n_individuals``).
    """
    lin = CompetingLineage(heredity_class, cfg, seed=seed)
    cfgf = lin.cfg
    v_pool = float(cfgf["individual_volume"]) * float(cfgf["pool_volume_multiplier"]) * int(cfgf["n_individuals"])
    feeds = {**{p: float(cfgf["nominal_feed"]) for p in POOLS}, **(feeds or {})}
    nominal = {p: int(round(feeds[p] * v_pool * AVOGADRO)) for p in POOLS}
    lin.pool_nominal = {p: max(nominal[p], 1) for p in POOLS}
    lin.pools = dict(nominal)
    q_feed = int(energy_feed_quanta if energy_feed_quanta is not None else 500 * int(cfgf["n_individuals"]))
    lin.quanta = q_feed
    lin.attached = bool(attached)
    for i in range(len(lin.ids)):
        lin._refresh(i)
    series = []
    for _ in range(int(n_ticks)):
        lin.advance(1.0)
        for p in POOLS:
            lin.pools[p] += int(round(feed_rate * (nominal[p] - lin.pools[p])))
        lin.quanta += int(round(feed_rate * max(q_feed - lin.quanta, 0)))
        series.append(lin.summary())
    info = lin.information()
    quantum_j = float(cfgf["energy_quantum_kj"]) * _KJ_PER_MOL_TO_J
    equiv = cfgf["precursor_energy_equivalent"]
    births = max(lin.births, 1)
    e_direct = lin.quanta_used * quantum_j
    e_prec = sum(lin.consumed[p] * float(equiv[p]) for p in POOLS) * quantum_j
    return {"class": heredity_class, "attached": bool(attached), "series": series, "info": info,
            "heritability": lin.heritability(), "fidelity": lin.fidelity(),
            "capacity_bits": lin.kin.capacity_bits(), "expected_fidelity": lin.kin.expected_fidelity(),
            "births": lin.births, "copies": lin.copies, "events": lin.events,
            "quanta_used": lin.quanta_used, "consumed": dict(lin.consumed),
            "energy_per_offspring_j": (e_direct + e_prec) / births,
            "direct_energy_per_offspring_j": e_direct / births,
            "precursors_per_offspring": sum(lin.consumed.values()) / births,
            "nodes": lin.nodes, "pairs": lin.pairs}


# --------------------------------------------------------------------------- #
# Process wrappers (one per class) honouring the heredity face
# --------------------------------------------------------------------------- #
def _p(default, units="dimensionless", prov="hypothetical", typ="float"):
    return {"_type": typ, "_default": default, "_units": units, "_provenance": prov}


_CONFIG = {
    "seed": _p(1, prov="inferred", typ="integer"),
    "n_individuals": _p(DEFAULTS["n_individuals"], prov="inferred", typ="integer"),
    "n0_molecules": _p(DEFAULTS["n0_molecules"], prov="inferred", typ="integer"),
    "n_max_molecules": _p(DEFAULTS["n_max_molecules"], prov="inferred", typ="integer"),
    "division_mass": _p(DEFAULTS["division_mass"], typ="integer"),
    "base_growth_rate": _p(DEFAULTS["base_growth_rate"], "1/second"),
    "selective_superiority": _p(DEFAULTS["selective_superiority"], prov="extrapolated"),
    "individual_volume": _p(DEFAULTS["individual_volume"], "liter", prov="inferred"),
    "pool_volume_multiplier": _p(DEFAULTS["pool_volume_multiplier"]),
    "energy_quantum_kj": _p(DEFAULTS["energy_quantum_kj"], "kilojoule/mole", prov="inferred"),
    "nominal_feed": _p(DEFAULTS["nominal_feed"], "molar"),
    "template_length": _p(DEFAULTS["template_length"], prov="extrapolated", typ="integer"),
    "per_site_fidelity": _p(DEFAULTS["per_site_fidelity"], prov="measured"),
    "k_replicate": _p(DEFAULTS["k_replicate"], "1/second"),
    "k_degrade": _p(DEFAULTS["k_degrade"], "1/second"),
    "k_denovo": _p(DEFAULTS["k_denovo"], "1/second"),
    "hybrid_template_length": _p(DEFAULTS["hybrid_template_length"], typ="integer"),
    "hybrid_focus": _p(DEFAULTS["hybrid_focus"]),
    "peptide_length": _p(DEFAULTS["peptide_length"], prov="extrapolated", typ="integer"),
    "peptide_fidelity": _p(DEFAULTS["peptide_fidelity"]),
    "peptide_alphabet": _p(DEFAULTS["peptide_alphabet"], prov="measured", typ="integer"),
    "composition_types": _p(DEFAULTS["composition_types"], prov="extrapolated", typ="integer"),
    "catalysis_sd": _p(DEFAULTS["catalysis_sd"], prov="extrapolated"),
    "k_incorporate": _p(DEFAULTS["k_incorporate"], "1/second"),
    "k_release": _p(DEFAULTS["k_release"], "1/second"),
    "network_cores": _p(DEFAULTS["network_cores"], prov="extrapolated", typ="integer"),
    "k_autocatalysis": _p(DEFAULTS["k_autocatalysis"], "1/second"),
    "k_spontaneous": _p(DEFAULTS["k_spontaneous"], "1/second"),
    "mineral_bits": _p(DEFAULTS["mineral_bits"], prov="extrapolated", typ="integer"),
    "defect_copy_error": _p(DEFAULTS["defect_copy_error"]),
    "k_layer": _p(DEFAULTS["k_layer"], "1/second"),
    "k_dissolve": _p(DEFAULTS["k_dissolve"], "1/second"),
    "equiv_nucleotide": _p(DEFAULTS["precursor_energy_equivalent"]["nucleotide_precursor"]),
    "equiv_amino": _p(DEFAULTS["precursor_energy_equivalent"]["amino_precursor"]),
    "equiv_amphiphile": _p(DEFAULTS["precursor_energy_equivalent"]["amphiphile"]),
    "equiv_mineral": _p(DEFAULTS["precursor_energy_equivalent"]["mineral_precursor"]),
}


def _lineage_cfg(config: dict) -> dict:
    cfg = {k: config[k] for k in DEFAULTS if k in config and k != "precursor_energy_equivalent"}
    cfg["precursor_energy_equivalent"] = {
        "nucleotide_precursor": float(config["equiv_nucleotide"]), "amino_precursor": float(config["equiv_amino"]),
        "amphiphile": float(config["equiv_amphiphile"]), "mineral_precursor": float(config["equiv_mineral"])}
    return cfg


class _HeredityProcessBase(Process):
    """One heredity class on the face: shared pools in (molar) + energy store (J) +
    the attachment flag -> lineage sensors, information + cost readouts, and the
    consumption written back as additive deltas on the pools / store."""

    HEREDITY_CLASS = "abstract"
    config_schema = _CONFIG

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._lin: CompetingLineage | None = None
        self._v_pool = None
        self._quantum_j = float(self.config["energy_quantum_kj"]) * _KJ_PER_MOL_TO_J

    def inputs(self):
        return {"temperature": _K, "attached": _DIMLESS, "stored_work": _J, **{p: _MOLAR for p in POOLS}}

    def outputs(self):
        return {
            # pool / store consumption (additive deltas)
            **{p: _MOLAR for p in POOLS}, "stored_work": _J,
            # lineage sensors
            "mean_function": _OVW, "functional_fraction": _OVW, "population": _OVW, "lineage_depth": _OVW,
            "heritability": _OVW, "fidelity": _OVW, "mutation_rate": {"_type": "overwrite[float]", "_units": "1/second"},
            "mean_molecules": _OVW, "n_attached": _OVW,
            # information
            "information_content": _OVW_BIT, "information_capacity": _OVW_BIT, "mi_converged": _OVW,
            "mi_standard_error": _OVW_BIT,
            # costs this tick (the ledger integrates them)
            "replication_energy": _OVW_J, "quanta_used": _OVW, "precursors_consumed": _OVW,
            "precursor_energy": _OVW_J, "copies": _OVW, "births": _OVW,
        }

    def initial_state(self):
        return {"temperature": 353.15, "attached": 0.0, "stored_work": 0.0, **{p: 0.0 for p in POOLS}}

    def _ensure(self):
        if self._lin is None:
            c = self.config
            self._lin = CompetingLineage(self.HEREDITY_CLASS, _lineage_cfg(c), seed=int(c["seed"]))
            self._v_pool = (float(c["individual_volume"]) * float(c["pool_volume_multiplier"])
                            * int(c["n_individuals"]))
            nominal = int(round(float(c["nominal_feed"]) * self._v_pool * AVOGADRO))
            self._lin.pool_nominal = {p: max(nominal, 1) for p in POOLS}

    def update(self, state, interval):
        self._ensure()
        lin = self._lin
        lin.attached = float(state.get("attached", 0.0)) >= 0.5
        for p in POOLS:
            lin.pools[p] = int(math.floor(max(float(state.get(p, 0.0)), 0.0) * self._v_pool * AVOGADRO))
        lin.quanta = int(math.floor(max(float(state.get("stored_work", 0.0)), 0.0) / self._quantum_j))
        before = dict(lin.consumed); q_before = lin.quanta_used; c_before = lin.copies; b_before = lin.births
        for i in range(len(lin.ids)):
            lin._refresh(i)
        lin.advance(float(interval))
        used = {p: lin.consumed[p] - before[p] for p in POOLS}
        q_used = lin.quanta_used - q_before
        equiv = _lineage_cfg(self.config)["precursor_energy_equivalent"]
        s = lin.summary()
        info = lin.information()
        fid = lin.fidelity()
        fid_out = 0.0 if not math.isfinite(fid) else fid
        her = lin.heritability()
        return {
            **{p: -used[p] / (self._v_pool * AVOGADRO) for p in POOLS},
            "stored_work": -q_used * self._quantum_j,
            "mean_function": s["mean_function"], "functional_fraction": s["functional_fraction"],
            "population": float(s["population"]), "lineage_depth": float(s["lineage_depth"]),
            "heritability": 0.0 if not math.isfinite(her) else her,
            "fidelity": fid_out, "mutation_rate": (1.0 - fid_out) / float(interval),
            "mean_molecules": s["mean_molecules"], "n_attached": float(s["population"]) if lin.attached else 0.0,
            "information_content": 0.0 if not math.isfinite(info["heritable_bits"]) else info["heritable_bits"],
            "information_capacity": lin.kin.capacity_bits(),
            "mi_converged": 1.0 if info["converged"] else 0.0,
            "mi_standard_error": 0.0 if not math.isfinite(info["se"]) else info["se"],
            "replication_energy": q_used * self._quantum_j, "quanta_used": float(q_used),
            "precursors_consumed": float(sum(used.values())),
            "precursor_energy": sum(used[p] * float(equiv[p]) for p in POOLS) * self._quantum_j,
            "copies": float(lin.copies - c_before), "births": float(lin.births - b_before),
        }

    def lineage_state(self) -> dict:
        self._ensure()
        return {"class": self.HEREDITY_CLASS, "nodes": self._lin.nodes,
                "po_pairs": [[round(p, 4), round(o, 4)] for p, o in self._lin.pairs],
                "heritability": self._lin.heritability(), "information": self._lin.information()}


def _contract(name: str, mechanism: str, refs: list[str]) -> dict:
    return {
        "summary": f"Heredity class '{name}' on the heredity face: {mechanism}",
        "description": (
            f"The '{name}' heredity class, simulated as an exact Gillespie lineage at low copy number: "
            f"{mechanism}. Draws integer precursor molecules from the shared dissolved pools and integer "
            "energy quanta from the shared stored-work store (matched budgets across classes), publishes the "
            "lineage sensors, the running parent-offspring mutual information with its convergence flag and "
            "the per-tick costs the information ledger integrates. Before attachment (attached = 0) daughters "
            "re-form their heritable state de novo at fission: og-06's non-heritable control."
        ),
        "inputs": {"temperature": "temperature (K)", "attached": "heredity attached (0/1, HeredityAttachmentStep)",
                   "stored_work": "shared energy store (J)",
                   **{p: f"shared dissolved {p} pool (molar)" for p in POOLS}},
        "outputs": {"information_content": "realised heritable bits (parent-offspring MI net of the permutation null)",
                    "mi_converged": "1 when the MI ladder + bootstrap SE converged",
                    "replication_energy": "energy quanta spent by heredity this tick, in joules",
                    "fidelity": "mean parent->daughter heritable-state overlap at fission"},
        "assumptions": ["Exact SSA (direct method) within each tick; pools and store refreshed at tick boundaries.",
                        "Selection acts through growth: bulk grows at k_grow (1 + sigma phi); dilution is uniform at capacity."],
        "references": refs,
    }


class RnaLikeHeredityProcess(_HeredityProcessBase):
    HEREDITY_CLASS = "rna_like"
    contract = _contract("rna_like", "an L-site template copied template-directed with per-site fidelity q (Eigen ratchet with back-mutation), L nucleotides + L quanta per copy",
                         ["eigen1971selforganization", "johnston2001rna", "rajamani2010effect"])


class PeptideHeredityProcess(_HeredityProcessBase):
    HEREDITY_CLASS = "peptide"
    contract = _contract("peptide", "a short peptide whose functional copies weakly template their own ligation (per-site fidelity q_p over a 20-letter alphabet), L_p amino acids + L_p quanta per copy",
                         ["huber1998peptides", "lee1996selfreplicating"])


class CompositionalHeredityProcess(_HeredityProcessBase):
    HEREDITY_CLASS = "compositional"
    contract = _contract("compositional", "a GARD assembly whose composition over K amphiphile types grows by mutually-catalysed incorporation (lognormal beta with two composomes) and is inherited by random fission; 1 amphiphile and 0 quanta per incorporation",
                         ["segre2000compositional", "vasas2010lack"])


class NetworkHeredityProcess(_HeredityProcessBase):
    HEREDITY_CLASS = "network"
    contract = _contract("network", "M autocatalytic cores growing from a precursor (1 amino acid + 1 quantum per molecule), lost by dilution at fission and re-seeded only by rare spontaneous formation: attractor heredity of at most M bits",
                         ["vasas2010lack", "szathmary2006origin"])


class MineralStateHeredityProcess(_HeredityProcessBase):
    HEREDITY_CLASS = "mineral_state"
    contract = _contract("mineral_state", "a B-bit defect pattern on a crystal face copied into every new layer with per-bit error p_m (1 mineral growth unit, 0 quanta per layer); cleavage hands both daughters the face",
                         ["cairnssmith1982genetic"])


class HybridHeredityProcess(_HeredityProcessBase):
    HEREDITY_CLASS = "hybrid"
    contract = _contract("hybrid", "a short template (L_h sites, nucleotides + quanta) whose function focuses a GARD composition on the functional composome (amphiphiles, no quanta)",
                         ["segre2000compositional", "eigen1971selforganization", "szathmary2006origin"])


HEREDITY_PROCESSES = {
    "compositional": CompositionalHeredityProcess, "network": NetworkHeredityProcess,
    "peptide": PeptideHeredityProcess, "rna_like": RnaLikeHeredityProcess,
    "hybrid": HybridHeredityProcess, "mineral_state": MineralStateHeredityProcess,
}


# --------------------------------------------------------------------------- #
# The matched budgets: chemostat precursor feed + fixed-power energy supply
# --------------------------------------------------------------------------- #
class BudgetFeedProcess(Process):
    """Chemostat feed of the shared precursor pools and a fixed-power energy supply.

    Each tick adds ``feed_rate * (feed - pool)`` to every precursor pool
    (additive delta) and ``min(power * interval, max_stored_work - stored_work)``
    to the energy store, publishing that inflow as ``work_flux`` so the
    information ledger can audit the store exactly.
    """

    contract = {
        "summary": "Chemostat precursor feed + fixed-power energy supply for the matched heredity budgets.",
        "description": ("Adds feed_rate * (feed - pool) to each shared precursor pool and a fixed power "
                        "(capped at max_stored_work) to the shared energy store each tick; publishes the "
                        "energy inflow as work_flux for the information ledger."),
        "inputs": {**{p: f"shared dissolved {p} (molar)" for p in POOLS}, "stored_work": "energy store (joule)"},
        "outputs": {**{p: f"inflow delta on {p} (molar)" for p in POOLS}, "stored_work": "energy inflow (joule)",
                    "work_flux": "energy inflow this tick (joule, sensor)"},
        "assumptions": ["Matched budgets: every class sees the same feed set-points and the same power."],
    }

    config_schema = {
        **{f"{p}_feed": _p(DEFAULTS["nominal_feed"], "molar") for p in POOLS},
        "feed_rate": _p(0.5, "1/second"),
        "power": _p(8.0e-16, "watt"),
        "max_stored_work": _p(8.0e-16, "joule"),
    }

    def inputs(self):
        return {**{p: _MOLAR for p in POOLS}, "stored_work": _J}

    def outputs(self):
        return {**{p: _MOLAR for p in POOLS}, "stored_work": _J,
                "work_flux": {"_type": "overwrite[float]", "_units": "joule"}}

    def initial_state(self):
        return {**{p: 0.0 for p in POOLS}, "stored_work": 0.0}

    def update(self, state, interval):
        r = float(self.config["feed_rate"])
        out = {p: r * (float(self.config[f"{p}_feed"]) - float(state.get(p, 0.0))) for p in POOLS}
        room = max(float(self.config["max_stored_work"]) - float(state.get("stored_work", 0.0)), 0.0)
        flux = min(float(self.config["power"]) * float(interval), room)
        out["stored_work"] = flux
        out["work_flux"] = flux
        return out


# --------------------------------------------------------------------------- #
# Conditional attachment (FMP section 2.5)
# --------------------------------------------------------------------------- #
class HeredityAttachmentStep(Step):
    """Attach heredity only when the matched budgets and the class's copy fidelity allow it.

    Reads the shared precursor pools (molar) and the energy store (J) and
    publishes ``attached`` = 1 when all three hold for the configured class:

    * precursor budget: molecules of the class's primary pool >=
      ``attach_min_copies * cost_per_copy * n_individuals``;
    * energy budget: quanta in the store >= ``attach_energy_margin *
      attach_min_copies * quanta_per_copy * n_individuals``;
    * fidelity floor (Eigen 1971): the class's expected whole-state copy
      fidelity ``Q >= 1 / selective_superiority``.

    ``attachment_margin`` is the smallest of the three ratios (>= 1 means
    attached). Once attached a lineage stays attached (``latch``), so a
    transient budget dip does not sever inheritance; replication simply
    stalls while a budget is exhausted. The precursor / energy thresholds are
    ``hypothetical`` until the expert supplies defensible ones; the study
    sweeps them.
    """

    contract = {
        "summary": "Conditional heredity attachment: precursor budget, energy budget and the Eigen fidelity floor must all be met.",
        "description": (
            "FMP section 2.5: heredity is absent until it can be paid for and copied. Each tick the step reads "
            "the shared precursor pools and the energy store, converts them to molecules / quanta per individual "
            "and compares them with the configured class's cost per copy; attached = 1 when the precursor ratio, "
            "the energy ratio and Q / (1/sigma) are all >= 1. Thresholds attach_min_copies and attach_energy_margin "
            "are hypothetical (expert decision pending) and swept; the fidelity floor is Eigen's error threshold."
        ),
        "inputs": {**{p: f"shared dissolved {p} (molar)" for p in POOLS}, "stored_work": "shared energy store (J)"},
        "outputs": {"attached": "1 once heredity is attached", "attachment_margin": "min(precursor, energy, fidelity ratios)",
                    "fidelity_floor": "1/sigma — the Eigen threshold the class's Q must exceed"},
        "math": ["attach iff N_pool >= m c_p N and quanta >= k m c_q N and Q >= 1/sigma"],
        "references": ["eigen1971selforganization"],
    }

    config_schema = {
        "heredity_class": {"_type": "string", "_default": "rna_like", "_provenance": "hypothetical"},
        "attach_min_copies": _p(DEFAULTS["attach_min_copies"]),
        "attach_energy_margin": _p(DEFAULTS["attach_energy_margin"]),
        "latch": {"_type": "boolean", "_default": True, "_provenance": "inferred"},
        **{k: _CONFIG[k] for k in ("n_individuals", "n0_molecules", "n_max_molecules", "selective_superiority",
                                   "individual_volume", "pool_volume_multiplier", "energy_quantum_kj",
                                   "template_length", "per_site_fidelity", "hybrid_template_length",
                                   "peptide_length", "peptide_fidelity", "peptide_alphabet", "composition_types",
                                   "catalysis_sd", "network_cores", "mineral_bits", "defect_copy_error",
                                   "k_replicate", "k_degrade", "k_denovo", "hybrid_focus", "k_incorporate",
                                   "k_release", "k_autocatalysis", "k_spontaneous", "k_layer", "k_dissolve")},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        self._attached = False
        cfg = {**DEFAULTS, **{k: self.config[k] for k in DEFAULTS if k in self.config}}
        self._kin = KINETICS[str(self.config["heredity_class"])](cfg, np.random.default_rng(0))
        self._v_pool = (float(cfg["individual_volume"]) * float(cfg["pool_volume_multiplier"])
                        * int(cfg["n_individuals"]))
        self._quantum_j = float(cfg["energy_quantum_kj"]) * _KJ_PER_MOL_TO_J
        self._n = int(cfg["n_individuals"])
        self._sigma = float(cfg["selective_superiority"])

    def inputs(self):
        return {**{p: _MOLAR for p in POOLS}, "stored_work": _J}

    def outputs(self):
        return {"attached": _OVW, "attachment_margin": _OVW, "fidelity_floor": _OVW}

    def costs(self) -> dict:
        """Per-copy precursor / quanta cost of the configured class (its copy channel)."""
        copy_ch = [ch for ch in self._kin.channels if ch[4]] or [ch for ch in self._kin.channels if ch[1]]
        pool, c_p, c_q = copy_ch[0][1], copy_ch[0][2], copy_ch[0][3]
        return {"pool": pool, "precursor_per_copy": int(c_p), "quanta_per_copy": int(c_q)}

    def decide(self, state: dict) -> dict:
        c = self.costs()
        m = float(self.config["attach_min_copies"])
        k = float(self.config["attach_energy_margin"])
        n_pool = max(float(state.get(c["pool"], 0.0)), 0.0) * self._v_pool * AVOGADRO
        quanta = max(float(state.get("stored_work", 0.0)), 0.0) / self._quantum_j
        need_p = m * c["precursor_per_copy"] * self._n
        need_q = k * m * c["quanta_per_copy"] * self._n
        r_p = n_pool / need_p if need_p > 0 else float("inf")
        r_q = quanta / need_q if need_q > 0 else float("inf")
        floor = 1.0 / self._sigma
        r_f = self._kin.expected_fidelity() / floor
        margin = min(r_p, r_q, r_f)
        return {"precursor_ratio": r_p, "energy_ratio": r_q, "fidelity_ratio": r_f, "margin": margin,
                "fidelity_floor": floor, "expected_fidelity": self._kin.expected_fidelity(), **c}

    def update(self, state):
        d = self.decide(state)
        now = d["margin"] >= 1.0
        if bool(self.config.get("latch", True)):
            self._attached = self._attached or now
        else:
            self._attached = now
        return {"attached": 1.0 if self._attached else 0.0,
                "attachment_margin": float(min(d["margin"], 1.0e6)),
                "fidelity_floor": d["fidelity_floor"]}


__all__ = ["HEREDITY_CLASSES", "POOLS", "DEFAULTS", "KINETICS", "HEREDITY_PROCESSES", "make_kinetics", "BudgetFeedProcess",
           "CompetingLineage", "simulate_competing", "HeredityAttachmentStep",
           "RnaLikeHeredityProcess", "PeptideHeredityProcess", "CompositionalHeredityProcess",
           "NetworkHeredityProcess", "MineralStateHeredityProcess", "HybridHeredityProcess"]
