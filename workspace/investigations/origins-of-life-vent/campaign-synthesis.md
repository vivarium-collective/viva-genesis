# Origins of life in an alkaline vent — campaign synthesis

This is the whole campaign in one place, told honestly. The required spine (Gates
A–D) is complete: a vent-fed chemistry that **persists, concentrates, compartments,
reproduces and inherits — but does not self-amplify by the routes we could
represent.** Each gate below carries its own verdict, the number it turns on, and
the matched control it was judged against. Where a result is qualified, it says so;
where a route was refuted, it says that too.

## The arc in one line

Geology makes a reducing, alkaline vent; a carbon-fixing reaction network emerges
and persists once a mineral pore concentrates it; an endogenous membrane then pays
for its own upkeep; and the enclosed protocell grows, divides and passes on a
selectable chemical difference. Along the way the one thing the vent theory most
wants — a self-amplifying (autocatalytic) core — was tested and **refuted** for both
routes we could represent, each with a mechanism. The result is a mechanism map and
an honestly-advanced spine, not a declaration of success.

## The spine, gate by gate

Every gate is judged against a **matched null with chemical input fluxes held
equal**, so a benefit is a margin over the control, not an artifact of more feed.

### Gate A1 — network persistence (qualified)

*Members: og-27 (coupled geochemical interface), og-28 (prebiotic reaction atlas);
pore-persistence confirmed via Gate B (og-30).*

A rule-generated C/H/O reaction network emerges on bounded geochemical feeds and
fixes carbon. In a well-mixed system the six-carbon network ignites only at about
**20× the vent-posterior feed** — above defensible vent concentrations — but a
concentrating mineral pore closes that gap (Gate B). So a connected carbon-fixing
network **persists at vent-realistic feeds inside a pore**, within a bounded,
somewhat brittle porosity window (~0.80–0.90). Qualified: it holds in a pore, not
in free solution.

### Gate A2 — endogenous autocatalysis (refuted, off-spine)

*Members: og-29 (endogenous autocatalysis), og-rtca-autocatalysis; off-spine — a
tested-and-refuted branch, not a spine prerequisite.*

Self-amplification beyond a degree-preserving matched null is **refuted under vent
conditions for both representable routes**, each with a distinct mechanism:

- **Formose (linear).** The canonical doubling step (two glycolaldehyde → threose)
  is thermodynamically condensation-favored (standard free energy **−16.4 kJ/mol**),
  so its splitting direction carries no net flux; and on a coefficient-free
  functional discriminator the network fixes carbon but production is
  **seed-independent** — feed-driven, not self-amplified.
- **rTCA (branched).** Under vent H₂ a seeded reductive-TCA cycle washes out,
  because the reductive carboxylations run uphill (succinate → α-ketoglutarate
  **+18 kJ/mol**; acetyl → pyruvate **+31 kJ/mol**) and too slow against washout —
  the same reason real rTCA uses ferredoxin, not H₂, as its reductant. A labelled
  counterfactual shows the rTCA topology *is* autocatalysis-capable under a stronger
  reductant (lowering the carboxylation barrier switches it on), so the vent
  negative is a redox-environment limitation, not a flaw in the cycle's wiring — a
  possible beyond-vent follow-up, outside the current vent scope.

This is the campaign's sharpest honest negative: no autocatalysis without a
one-carbon feed, and none at all by the routes a vent can represent.

### Gate B — spatial organization (met)

*Member: og-30 (spatially integrated protometabolism).*

At the same vent-posterior base feed held equal, a concentrating mineral pore at a
modest, physical porosity (**0.88**, pore-local ~0.023 M, enrichment ~23×) ignites
the reaction network — net carbon flux **+4.5e-4**, a connected network — while a
matched well-mixed, nonconcentrating control stays dead (flux ~0, not connected).
Spatial concentration is the only difference, so the pore itself causes the
productive flux. Confirmed directly on the six-carbon network og-29 found needs ~20×
well-mixed feed (flux +4.49e-4, connected). The rescue holds in a bounded window
(~0.80–0.90): below it enrichment is sub-threshold; above it the pore-local feeds
become physically implausible. Gate B also resolves A1's feed-plausibility question.

### Gate C — self-compartmentation (qualified)

*Members: og-31 (protometabolism to amphiphiles), og-32 (first self-maintaining
protocell). Matched null: a no-endogenous-membrane ablation at equal feeds.*

An endogenous membrane **pays for itself on persistence, but not on throughput.** On
the Gate-B pore-concentrated A1 network, a membrane raises the standing metabolite
pool above the no-membrane ablation (og-31, reduced-coupling: **~2.9×**; og-32,
MD-informed: **~1.98×**) while net fixation flux is *lower* (~0.6× and ~0.79×) —
throughput is feed-limited, so compartmentalization buys retention and
concentration, not faster chemistry. og-32 takes full Gate C on an **MD-informed
first cut** (Option B): short Martini CG-MD gives a thicker long-chain bilayer
(di-C16 2.870 nm vs di-C12 2.325 nm) → lower permeability (0.256) → higher retention
(0.661), so composition sets permeability sets retention — a resolved coupling, not a
free knob. The benefit is windowed (membrane access ≳ 0.45; integrity to a
degradation rate k_deg ≤ ~0.01/s) and the metabolism is the sustained A1
carbon-fixing network, not autocatalysis. Qualified: persistence not throughput,
windowed, and MD-informed rather than PMF-resolved (the gold standard is tracked as
og-32a).

### Gate D — reproduction and heredity (qualified — a real positive)

*Members: og-33 (chemically coupled growth and division), og-34 (chemical heredity
and selection).*

**Growth and division (og-33).** The protocell grows from its own metabolic
amphiphile production and divides at a **measured area-doubling geometry** (ratio
2.0, grounded in the hanczyc/budin growth–division data) with no imposed event.
Division rate scales with metabolic flux (**0.0125 → 0.0500** as net carbon flux
rises) where a growth-decoupled control is flux-independent and an imposed-division
control fires on a timer; daughters resume self-maintenance (viable). It beats both
matched nulls at equal feeds. Qualified on the measured-geometry first cut (resolved
membrane mechanics tracked as og-33a).

**Heredity and selection (og-34).** A daughter-inherited chemical difference produces
a **reproducible, selectable fitness difference** — parent-offspring fitness
correlation **+0.949** versus a no-inheritance control's −0.018 (permutation
p=0.0001), and the inheriting population shifts composition toward higher retention
(**+0.551**) while the control drifts (−0.004, p=0.0002), across 8 seeds × 40
generations at equal feeds. Fitness is grounded in the real study-32/33 coupling
(composition → membrane retention → standing pool → division rate), not a toy
function, and the vasas-2010 evolvability caveat was *tested* (a declared, not tuned,
heritable variance) rather than assumed. This is the campaign's clearest positive:
compositional inheritance carried enough selectable variance here. Qualified on
compositional inheritance (template copying tracked as og-34a).

## What the campaign shows — and what it does not

The required spine is complete and the story is consistent: a vent-fed chemistry
**persists** (A1, in a pore), **concentrates** (B), **compartments and is
maintained** (C), and **reproduces and inherits a selectable trait** (D). Those are
real, matched-null-anchored results — Gate D in particular is a genuine positive.

A second through-line runs across the campaign's independent mechanisms: each buys
**robustness and persistence, not productivity.** The concentrating pore (B) lets the
network ignite and persist at vent-realistic feeds rather than raising the throughput
of an already-running network; the endogenous membrane (C) buys metabolite retention
(~2–3×) while net fixation flux stays flat or lower (feed-limited); and the Gate E
energy carrier (study 35, qualified) buys persistence through a gradient dip — useful
work through the dip (0.030) where a gradient-only system starves (0.006), with the
free-energy ledger closing to machine precision (~9e-19, no hidden inflow) — while
total useful work is not improved (0.256 vs 0.282, even at zero hydrolysis), because
it banks and time-shifts energy rather than netting more. Three independent mechanisms
— spatial, compartment and energetic — thus buy the protocell time, retention and
dip-resilience, not faster chemistry. The campaign-level finding is that
**concentration, compartmentation and energy coupling alike buy persistence and
robustness, not productivity.**

What the campaign does **not** show is self-amplification: endogenous autocatalysis
is refuted under vent conditions for both routes we could represent (A2), on
thermodynamics and on a seed-independence discriminator. The honest summary is a
chemistry that gets a long way toward a cell by persistence, concentration,
compartmentation and heredity — without ever needing, or achieving, a self-amplifying
core by a vent-representable route.

## Tracked follow-ups (the gold-standard versions)

None of these is a hidden caveat; each is a named, budgeted follow-up study:

- **og-32a** — full PMF-resolved membrane permeability (gold-standard viva-md-membrane),
  to re-test Gate C under a structurally-resolved permeability rather than the
  MD-informed structural proxy.
- **og-33a** — coarse-grained membrane-mechanics division, to re-test growth/division
  under resolved membrane physics rather than a measured critical-geometry threshold.
- **og-34a** — template-copying inheritance, to re-test selectable heredity under a
  higher-fidelity copying mechanism rather than compositional inheritance.

**Gate E (optional extension)** is designed and contracted beyond the required spine.
og-35 chemical energy coupling has **run (qualified)** — the third
robustness-not-throughput instance noted above (follow-up og-35a: alternative-carrier
/ microkinetic); og-36 stochastic protocell ecology (og-36a: full GillesPy2/SSA +
COBRApy benchmark) and og-37 progressive independence (og-37a: combinatorial /
staged-order withdrawal) remain designed. Its execution scope is decided if and when
the campaign reaches it.

## How to read these verdicts

Every verdict above is anchored to a matched null with input fluxes held equal, so a
benefit is a true margin. "Qualified" means a real result inside a stated scope
(persistence not throughput; in a pore not free solution; MD-informed not
PMF-resolved; compositional not template heredity) — not a hedge. "Refuted" means a
tested negative with a mechanism, reported and never tuned away. The campaign's value
is the map it draws: where a cellular origin is reachable by vent chemistry, where it
is only reachable inside a concentrating pore, and where — for self-amplification — it
is not reachable by the routes a vent can represent at all.
