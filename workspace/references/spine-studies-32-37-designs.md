# Spine studies 32–37 — designs (Gates C / D / E)

Designs for the six spine studies that extend the built 27–31 spine and complete
the origins-of-life-vent campaign arc. These are **designs, not runnable
composites** — narrative plus contracts, complete enough to scaffold directly.
Each is converted to a `design_status: drafted` `study.yaml` stub as its gate
comes into reach (not before: Gate C is gated on Gates A/B, which are still in
progress). They live here as references in the meantime.

Grounding: the 27–31 spine, the tool/method map in
[`build-registry.yaml`](build-registry.yaml) and
[`computational-resources.md`](computational-resources.md), the integration gates
in the investigation's `plan_gates`, and the og-06 / og-12 / og-22 rescopes these
studies instantiate.

**Campaign gate standard.** Every gate criterion is judged against a **matched
null / ablation with chemical input fluxes held equal** — the ablation removes the
mechanism under test (membrane, inheritance, carrier, …) while feeding the system
exactly the same, so any benefit is a margin over the control, not an artifact of
more input. A negative result is an accepted scientific outcome; thresholds are
never tuned to force a pass.

**Extends chain:** 32 ← 31 · 33 ← 32 · 34 ← 32 (uses 33) · 35 ← 34 · 36 ← 34 · 37 ← 34.

**Gate mapping:** 32 → Gate C (self-compartmentation) · 33 + 34 → Gate D
(reproduction & heredity) · 35 + 36 + 37 → Gate E (optional extension).

---

## 32 — First Self-Maintaining Protocell (Gate C)

- **extends:** 31 (consumes the 31 membrane + 30 spatial metabolism + 29 network)
- **question:** Can a vent-fed metabolism and an endogenous membrane be coupled so the membrane encloses and is maintained by the metabolism — and does the enclosed system persist and function better than the same metabolism with no membrane?
- **hypothesis:** Coupling the 29/30 reaction network to the 31 amphiphile/membrane closure yields a compartment that retains metabolites against leakage, is replenished by metabolism-supplied amphiphiles faster than it degrades, and sustains higher productive flux/persistence than a membrane-less control at equal feeds.
- **claim:** A composite coupling endogenous metabolism to an endogenous membrane either self-maintains — the membrane retains metabolites and is rebuilt by the metabolism against degradation, and the enclosed system beats a matched no-membrane control at equal feeds — or the membrane is a net cost, which is reported.
- **decision_test:** At identical input fluxes the compartmented system must (i) maintain membrane integrity (net amphiphile production ≥ degradation) **and** (ii) exceed the ablation on productive flux or persistence. Failing either is a reported negative (not self-maintaining, or not beneficial), not tuned.
- **matched-null / ablation:** membrane-less / permeability-fixed-open control at identical chemical input fluxes — removes the endogenous boundary while holding feeds equal; the Gate C benefit is the margin over this.
- **proposed_methods / models:** viva-md-membrane (OpenMM/LAMMPS coarse-grained composition→permeability closure, *to-build*); 30 reactive transport + 29 kinetics; a Vivarium coupling composite joining metabolism↔membrane via amphiphile-precursor + energy flows with permeability-gated exchange; PyMC/SALib robustness.

## 33 — Chemically Coupled Growth & Division (Gate D)

- **extends:** 32
- **question:** Can a self-maintaining protocell grow and divide as a consequence of its own chemistry — membrane area and content increasing from metabolism until a physical instability splits it — rather than by an imposed division rule?
- **hypothesis:** Metabolism-supplied amphiphiles grow the membrane; as area outpaces volume the compartment reaches a shape instability and divides, partitioning contents; division rate scales with metabolic flux and daughters re-enter self-maintenance.
- **claim:** A protocell either grows from its own metabolic amphiphile production and divides at a physically-grounded threshold — yielding viable daughters that resume self-maintenance — or growth/division needs an imposed rule, which is reported rather than asserted as emergent.
- **decision_test:** Growth and division must follow from metabolic flux + membrane physics (a measured critical-geometry threshold) with no imposed division event, and daughters must be viable (resume self-maintenance) — vs a control with growth decoupled from metabolism at equal feeds.
- **matched-null / ablation:** growth decoupled from metabolism (fixed external amphiphile supply) **or** imposed-division-rule control, at identical input fluxes.
- **proposed_methods / models:** membrane growth from the 31/32 amphiphile pool; division via a **measured critical-geometry threshold** first (coarse-grained membrane mechanics via viva-md-membrane as the richer follow-up — see Design decisions); multi-compartment Vivarium composite. Real anchors on main: `hanczyc2003experimental`, `budin2012concentration`, `zhu2012photochemically`, `natchem2023osmoticgrowth`.

## 34 — Chemical Heredity & Selection (Gate D)

- **extends:** 32 (uses 33 division)
- **question:** Does a chemical difference inherited by a daughter protocell cause reproducible differences in survival or reproduction — is there heritable variation selection can act on?
- **hypothesis:** Compartments carrying different inherited network compositions show reproducible, heritable fitness differences under the vent feed, so a population shifts composition under selection rather than drifting.
- **claim:** A daughter-inherited chemical difference either produces a reproducible fitness difference that selection acts on — shown against a matched no-inheritance control — or inheritance confers no selectable difference, which is reported.
- **decision_test:** An inherited chemical difference must cause reproducible survival/reproduction differences (parent–offspring fitness correlation above a no-inheritance control) at equal feeds, and a population under selection must shift measurably.
- **matched-null / ablation:** no-inheritance control (daughters reset to a common composition) at identical input fluxes.
- **proposed_methods / models:** multi-compartment Vivarium population over shared vent fields; inheritance via **network composition** partitioned at division (see Design decisions); selection = differential persistence/division; PyMC for significance. Instantiates the og-06 rescope's four mechanisms. Real anchors on main: `segre2000compositional`, `vasas2010lack`, `eigen1971selforganization`, `blokhuis2020universal`, `adamala2013nonenzymatic`.

## 35 — Chemical Energy Coupling (Gate E, optional)

- **extends:** 34 (ties to the og-12 energy-carrier rebuild)
- **question:** Does coupling a specified chemical energy carrier (thioester/acyl-phosphate cycle) to the protocell's metabolism improve net useful work and persistence over using the environmental gradient alone?
- **hypothesis:** A carrier cycle that stores and transfers free energy lets the protocell do endergonic work when the gradient dips, raising persistence/robustness vs gradient-only operation — provided synthesis/hydrolysis costs are outweighed.
- **claim:** Coupling a specified energy-carrier cycle either confers net positive useful work and improved persistence over a gradient-only control — with a full energy ledger and no hidden inflow — or its costs exceed its benefit, which is reported.
- **decision_test:** Full energy accounting (synthesis/activation/use/hydrolysis/leak) shows net positive useful work **and** improved persistence vs a matched gradient-only control at equal feeds, with no hidden energy inflow.
- **matched-null / ablation:** gradient-only (no carrier) control at identical input fluxes.
- **proposed_methods / models:** eQuilibrator ΔG + the og-12 carrier chemistry; libRoadRunner/COPASI kinetics; coupled to the 32/34 protocell. Real anchors on main: `huber1997activated`, `natcomm2025phosphateactivation`, `buckel2013energy`, `sojo2014bioenergetic`.

## 36 — Stochastic Protocell Ecology (Gate E, optional)

- **extends:** 34 (ties to og-07)
- **question:** In a heterogeneous pore network, do populations of protocells develop cross-feeding, competition and community-level functions that single lineages do not — under honest stochastic low-count dynamics?
- **hypothesis:** Heterogeneous protocell populations over shared spatial fields develop metabolic division of labour / cross-feeding and greater robustness than any single lineage, with stochastic dynamics materially changing outcomes at low counts.
- **claim:** Protocell populations either develop cross-feeding/community functions and robustness beyond single lineages — shown against a matched single-lineage/well-mixed control — or heterogeneity confers no community benefit, which is reported.
- **decision_test:** Population-level function/robustness must exceed a matched single-lineage (or well-mixed, no-cross-feeding) control at equal feeds; stochastic vs deterministic must be compared where molecule counts are low. *(The concrete community-function metric is an open design item — see Design decisions ⚑4.)*
- **matched-null / ablation:** single-lineage / no-cross-feeding / well-mixed control at identical input fluxes.
- **proposed_methods / models:** Vivarium multi-agent composites over FiPy shared fields; continuum-stochastic-exchange (GillesPy2/SSA, *to-build*) for low counts; optional COBRApy genome-scale benchmark.

## 37 — Progressive Independence (Gate E, optional)

- **extends:** 34 (consumes 35/36; ties to og-08 / og-22)
- **question:** As each environmental support is withdrawn one at a time, how independent can a protocell lineage become — which supports can it internalize or replace, and where does it still fail?
- **hypothesis:** The coupled protocell (32/34 + 35 energy) can internalize a subset of supports (e.g. energy via carrier, some resources) but remains dependent on others (specific minerals, fixed carbon), giving a measurable independence profile rather than all-or-nothing escape.
- **claim:** A lineage achieves graded independence — a measurable profile of which supports it can replace and which it cannot, against an explicit budget and matched per-support ablations — rather than a single escape event; remaining dependencies are reported, not smoothed.
- **decision_test:** For each withdrawn support (pH gradient, H2, CO2, mineral catalysis, temperature, organics) determine whether the lineage persists via internalization or fails, against an explicit budget and a matched ablation at equal feeds; report the independence profile and remaining dependencies.
- **matched-null / ablation:** per-support matched ablation (one support removed, inputs otherwise equal) — mirrors the og-22 rebuild.
- **proposed_methods / models:** the og-22 per-support variation applied to the protocell composite; explicit budget accounting; PyMC/SALib.

---

## Design decisions

Resolved choices for the v1 scaffold, with alternatives noted as possible later
refinements (all overridable).

- **⚑1 — 32 self-maintenance criterion (chosen):** the weaker, measurable form —
  net amphiphile production ≥ degradation **and** the compartment beats the
  no-membrane control at equal feeds. It is falsifiable and matches the campaign's
  measurable-gate standard. *Possible later tightening:* strict autopoietic closure
  (all membrane components produced endogenously). Not the v1 bar.
- **⚑2 — 33 division mechanism (chosen):** a **measured critical-geometry
  threshold** first (grounded in the hanczyc/budin growth–division geometries).
  *Richer follow-up:* full coarse-grained membrane mechanics via viva-md-membrane —
  deferred so the to-build membrane tool is not over-committed to mechanics upfront.
- **⚑3 — 34 inheritance mechanism (chosen):** **inherited network composition**
  first — tractable and tied to compositional/GARD inheritance plus its
  `vasas2010lack` evolvability caveat. *Follow-up:* template copying.
- **⚑4 — 36 community-function metric (open):** what counts as an emergent
  community capability is **deliberately left open**; define the concrete metric
  when 36 is actually scaffolded (it is a distant, optional Gate E study), not now.
- **⚑5 — Gate E scope:** all three designs (35 / 36 / 37) are **kept** — they are
  complete and cost nothing as references. The *execution* scope of Gate E is
  decided when the campaign reaches it; nothing is cut now.
