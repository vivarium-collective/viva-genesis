# Membrane-MD sub-program (M1–M5) — designs (Gate C / Gate D / integrative)

These are **designs, not runnable composites** — a connected set of *planned* studies
(narrative plus contracts, complete enough to scaffold directly), each to be converted to
a `design_status: drafted` study.yaml stub as its gate comes into reach. **The whole
membrane-MD program is PLANNED** (`simulation_status: not_run`): the fuller M-studies here
*and* their lightweight first-cut seeds (a vesicle-stability MD, a self-assembly MD, a PMF
MD — not yet built or named) are planned. Nothing in this doc is asserted as run.

**Core hypothesis (a feasible region, not an optimum).** The most stable membrane need not
be the most functional: a membrane that retains products may exclude substrates; a more
permeable one may raise throughput but lose intermediates. The objective is to map a
**feasible region** across assembly, stability, permeability, growth and metabolic demand —
not to optimize any one property. A negative result (no candidate composition meets the
joint constraints) is a **meaningful mechanistic boundary**, not a failure, and is reported
as such.

**Honest caveat (carried verbatim on every study).** *MD tests candidate prebiotic
compositions; it does NOT by itself demonstrate endogenous membrane formation.* MD assembles
and characterizes compositions that are *handed to it*; whether the campaign's own chemistry
produces those compositions is the separate chemistry→composition question (see the data
contract below). The studies keep that distinction explicit.

**Grounding.** Built on the real spine: og-31 (Martini-MD cohesion — the "makes a membrane"
half) and og-32 (the MD-informed permeability first cut, Option B: short Martini 3 CG-MD →
bilayer thickness → permeability → retention), with the PMF/membrane-closure gold standard
tracked as og-32a. The to-build engine is **viva-md-membrane** (an OpenMM/LAMMPS
coarse-grained composition→permeability closure, *to-build*). The MD property library this
program produces is stored as a **reusable resource** (the `structured_resources.yaml`
lipid-structure + a composition→property lookup), referenced by each node rather than
duplicated per study.

**Campaign gate standard.** Every claim is judged against a **matched null / ablation with
chemical input fluxes held equal**, across **multiple seeds**, with unbiased self-assembly
preferred over preassembled starts where feasible. Negatives are accepted and reported;
acceptance thresholds are never tuned to pass.

**Chemistry→composition data contract (the critical handoff — the ODE↔MD seam).** The
chemistry must emit explicit amphiphile identities / molecular classes / chain–headgroup
distributions / production rates — concretely, `AmphiphileChainExtensionProcess`
(`viva_genesis/membranes/amphiphile_chain_extension.py`, C10–C16 elongation) emits
`mean_chain_length`, `amphiphile_total`, `long_chain_fraction`, `aggregation_competent`
(long-chain pool / CAC), and `degradation_loss`. The MD side keys on these as its input
composition. This seam is what makes the program a coupled chemistry↔MD test rather than an
isolated MD study, and it is where the "MD tests compositions it is handed" caveat bites.

**Extends chain:** M1 → M2 · M1 → M3 · M1 → M4 · (M1,M2,M3,M4) → M5.
**Gate mapping:** M1 / M2 / M3 → Gate C (self-compartmentation); M4 → Gate D (reproduction —
division *propensity* only); M5 → integrative (ties og-32 and og-37).

---

## M1 — amphiphile assembly & composition (Gate C)

- **extends:** the chemistry→composition contract (the C10–C16 amphiphile pool); seeds M2/M3/M4.
- **scientific_question:** Which amphiphile structures and mixtures — fatty acids C8–C14, fatty alcohols, monoacylglycerols, and their mixtures — form micelles, bilayers or vesicles under vent-relevant conditions?
- **hypothesis:** Assembly state is set by chain length, headgroup and mixture composition (and the protonation fraction of fatty-acid carboxylates); a feasible bilayer/vesicle window exists for long-enough chains and favorable mixtures, bounded below by the CAC and above by insolubility.
- **primary_output:** per-composition assembly state (micelle / bilayer / vesicle / none), bilayer thickness, area per molecule, acyl-chain order parameter, and vesicle survival over the run.
- **claim (either/or, incl. the negative):** Either a defined set of prebiotically-plausible compositions self-assembles into surviving bilayers/vesicles under vent conditions, or they do not — in which case the accessible assembly window is reported as a bound (which chains/mixtures fail, and why), not tuned to pass.
- **matched-null / ablation:** matched counts / concentration / ionic strength across compositions; multiple seeds; **pure vs mixed** compositions compared head-to-head; **unbiased self-assembly vs a preassembled bilayer** start (to show assembly is spontaneous, not imposed) — all at identical input conditions.
- **proposed_methods / models:** Martini 3 CG-MD (*to-build* viva-md-membrane) for self-assembly + bilayer observables; `first_cut_forthcoming`: a lightweight fatty-acid vesicle-stability MD and a spontaneous self-assembly MD (planned, not yet scaffolded or named). Real anchors on main: og-31 (Martini cohesion), og-32 (bilayer thickness). Refs: souza2021martini3, marrink2003vesicle, janke2014oleic, jordan2019promotion.

## M2 — permeability & selective retention (Gate C; also feeds the A1 network)

- **extends:** M1 (the assembled compositions).
- **scientific_question:** Which membranes admit substrates while retaining products — i.e. which compositions are *selectively* permeable in the direction the metabolism needs?
- **hypothesis:** Permeability is graded by solute class and set by composition; a window exists where small substrates (water, neutral organics) cross while larger / charged products (organic acids, charged metabolites) are retained — but stability and selective retention may trade off (the core feasibility tension).
- **primary_output:** potential-of-mean-force (PMF) profiles, diffusivities, and permeabilities with uncertainty, per solute class (water, neutral organics, organic acids, charged metabolites); a composition→transport lookup table.
- **claim (either/or):** Either a composition window admits substrates while retaining products (selective permeability in the useful direction), or no accessible composition does — reported as a transport bound, not tuned.
- **matched-null / ablation:** per-solute PMFs computed with matched enhanced-sampling protocol and windows; a no-membrane (free-diffusion) reference; equal-condition comparison across compositions.
- **proposed_methods / models:** CG-MD + enhanced sampling (umbrella / US-WHAM or equivalent) for PMFs (*to-build* viva-md-membrane); `first_cut_forthcoming`: **og-32a** (the already-tracked PMF/membrane-closure gold-standard follow-up) is the natural first cut for this study. Real anchors: og-32 (MD-informed permeability proxy), og-32a (proposed PMF closure). Refs: souza2021martini3, grunewald2020titratable, marrink2007martini.

## M3 — stability across environmental gradients (Gate C)

- **extends:** M1 (the assembled compositions).
- **scientific_question:** How do ionic strength, mono- and divalent ions, temperature, and carboxylate protonation fraction change membrane integrity?
- **hypothesis:** Vent-relevant ionic strength, divalent cations (Mg²⁺/Ca²⁺), temperature and pH-set protonation define a stability envelope; integrity degrades (defects, desorption, rupture) outside it, and the envelope may not coincide with the functional (selective-permeability) window.
- **primary_output:** stability envelopes over the gradients, defect statistics, desorption/exchange rates, and rupture / pore-formation thresholds.
- **claim (either/or):** Either candidate compositions stay intact across the vent-relevant gradient ranges, or they rupture/desorb within them — the stability envelope is reported either way.
- **matched-null / ablation:** one-factor-at-a-time sweeps → a small factorial; matched counts/seeds; a reference composition held across all conditions as the internal control.
- **proposed_methods / models:** CG-MD stability runs across ionic strength / ion identity / temperature / protonation (*to-build* viva-md-membrane); `first_cut_forthcoming`: a lightweight pH × chain-length stability-window MD (planned). Real anchors: og-31/og-32. Refs: janke2014oleic (protonation/phase), grunewald2020titratable, souza2021martini3.

## M4 — growth, shape change & division propensity (Gate D)

- **extends:** M1 (vesicles), M2/M3 (their transport + stability).
- **scientific_question:** Can supplied amphiphiles insert into, reshape, and expand a vesicle — and what is its *propensity* to divide?
- **hypothesis:** Supplied amphiphiles insert and expand membrane area; area growth drives curvature/shape change and lowers the budding barrier — a *propensity* to divide, set by composition and osmotic conditions.
- **primary_output:** insertion/exchange rates, area-growth trajectories, curvature change, and budding/division-barrier estimates.
- **claim (either/or):** Either supplied amphiphiles insert and reshape toward a division-competent geometry, or they do not (insertion too slow, no curvature response) — reported as a propensity bound. **Division propensity is kept SEPARATE from heritable division — this is NOT a demonstration of heredity** (that is Gate D's og-34 / template-copying line).
- **matched-null / ablation:** **no-supply** control vs **composition-matched supply**; multiple vesicle sizes; matched osmotic conditions — at identical feeds.
- **proposed_methods / models:** CG-MD insertion/growth + curvature/barrier estimation (*to-build* viva-md-membrane); builders (insane / CHARMM-GUI Martini Maker / TS2CG) for the vesicle starts. Real anchors: og-33 (metabolism-driven division at a measured geometry — the propensity here feeds that, it does not replace it). Refs: hanczyc2003experimental, budin2012concentration, marrink2003vesicle.

## M5 — functional membrane window (integrative; ties og-32 / og-37)

- **extends:** M1 (assembly), M2 (permeability), M3 (stability), M4 (growth) — all property outputs feed M5.
- **scientific_question:** Which *measured* compositions sustain a modeled internal reaction network — i.e. where do assembly, stability, selective permeability and growth-requirement constraints jointly hold?
- **hypothesis:** The feasible region is an *intersection*, likely narrow: the most stable composition is not the most functional, so the compositions that sustain the internal network are a bounded compromise — and the region may be empty (a meaningful boundary).
- **primary_output:** a ranked, uncertainty-aware **membrane feasibility map** — compositions scored on substrate access, product retention, network persistence and growth requirement, with the joint-feasible region (or its emptiness) identified.
- **claim (either/or):** Either a non-empty composition region jointly satisfies the assembly/stability/permeability/growth constraints and sustains the internal network, or the region is empty — the feasibility map reports which, with uncertainty.
- **matched-null / ablation:** an **equal-feed unbounded** (no-membrane) baseline; a **prescribed-parameter** baseline (membrane properties fixed, not measured); **alternative compositions** compared; input fluxes held equal.
- **proposed_methods / models:** insert the M2–M4 measured properties into a coupled compartment–reaction model (reusing og-32's compartment coupling and the A1 network), scan compositions; this is the integrative tie to og-32 (self-maintaining protocell) and og-37 (the budget-feasibility / independence framing). Refs: souza2021martini3, sojo2014bioenergetic, jordan2019promotion.

---

## Design decisions

Resolved choices for the v1 scaffold, with alternatives noted as possible later refinements
(all overridable).

- **⚑1 — Whole program is PLANNED (chosen):** the M-studies and their S first-cut seeds are
  all `simulation_status: not_run`; nothing is asserted as run or in-flight. *Possible later
  tightening:* scaffold the lightweight S first cuts (vesicle-stability / self-assembly / PMF)
  before the fuller M-studies, and harden the `first_cut_forthcoming` soft-refs to real slugs.
- **⚑2 — Feasibility region, not optimum (chosen):** success is a joint-constraint region (or
  its honest emptiness), never a single optimized property. *Possible later tightening:* a
  formal multi-objective Pareto front once the M2–M4 property library has uncertainty bands.
- **⚑3 — Engine viva-md-membrane, to-build (chosen):** the composition→permeability closure is
  a planned OpenMM/LAMMPS CG tool; M2's PMF first cut reuses the tracked og-32a proposal.
  *Richer follow-up:* atomistic cross-checks on a few keystone compositions.
- **⚑4 — Division propensity ≠ heredity (chosen, honest-bar):** M4 measures a *propensity* to
  divide (geometry/curvature/barrier), explicitly NOT heritable division (og-34's line). The
  distinction is marked on M4 so a division-competent geometry is never read as proof of
  heredity.
- **⚑5 — MD property library as a reusable resource (chosen):** compositions and their measured
  properties live once in the structured-resources manifest (lipid-structure + a
  composition→property lookup), referenced by each node, not duplicated per study.
- **⚑6 — Gate placement (chosen; open to the board):** M1/M2/M3 → Gate C, M4 → Gate D, M5
  integrative. *Open:* whether this membrane-MD set is better recorded as a planned *extension*
  of the (already qualified) Gates C/D or as its own named sub-gate — a board/renderer call.
