# proto_endosymbiosis_hybrid — coupled-model build plan

**Goal:** a process-bigraph composite that measures the *discriminating* observables
the reopened eukaryogenesis bridge studies need (selection coefficient, stable-enclosure
probability, joint feasibility) — which the existing per-study composites cannot produce.

**Key finding (reuse-first):** the 7 feedback modules are already built in `viva_genesis`.
This is a **composition** task — build the typed, conserved *couplings* between existing
mechanisms, not the mechanisms themselves.

## Module → existing-component map

| Feedback module | Reuse |
|---|---|
| spatial_metabolite_exchange | `composites/metabolite_exchange_community.py` (S1/S2) |
| host_and_partner_metabolism | `composites/protometabolism.py`, `cross_feeding_metacommunity.py` |
| adhesion_and_membrane_mechanics | `membrane_wrapping.py`, `membrane_enclosure.py`, `composites/protrusion_enclosure*.py` (S3) |
| compartment_transport_and_energy_accounting | `bioenergetics/energy_coupling.py`, `composites/bioenergetic_internalization.py`, `proto_energetics.py` (S4) |
| host_symbiont_growth_division_and_death | `composites/og_33_chemically_coupled_growth_and_division.py`, `osmotic_growth_division.py`, `growth_rewrites.py` |
| symbiont_partition_and_vertical_transmission | `composites/competing_heredity.py`, `heredity_lineage.py`, `og_34_chemical_heredity_and_selection.py` (S5) |
| host_partner_conflict_and_partner_loss | partial — `og_36_stochastic_protocell_ecology.py`; **the main new coupling** |

**Composition template:** `composites/integrated_autonomy.py::integrated_autonomy_world` —
merges mechanisms into ONE persistent-lineage world via modular `model_*` slots +
a `ConservationLedgerProcess`. Follow this `@composite_generator` idiom.

**Selection engine (for the coefficient):** `og_34_chemical_heredity_and_selection`
(replicator dynamics on an inherited trait, fitness grounded in real coupling) and
`bioenergetic_internalization::BioenergeticSelectionProcess` (replicator w/ leaky-membrane
fitness). Adapt: the **inherited trait = contact/adhesion propensity**; fitness =
(exchange benefit enabled by contact) − (adhesion/membrane cost).

## Incremental sequence (each ends with a runnable, validated increment)

1. **M1 — selection_coefficient_for_adhesion** (unblocks study-selection-for-proximity,
   discriminates H1-syntrophy-first vs H4-no-integration). Compose:
   `metabolite_exchange` (benefit) + `growth_division` (og_33) + an **adhesion-cost**
   coupling + a **contact-propensity selection** process (og_34 style). Measure the
   invasion-fitness differential of contact-seeking vs non-contact-seeking phenotypes,
   under exchange vs the no-exchange control.
   *Acceptance:* runs reproducibly; selection coefficient > 0 only under exchange (not
   controls) in some parameter regime, ≤ 0 in another — i.e. it can go either way,
   proving it *measures* rather than imposes the answer.
2. **M2 — probability_of_stable_enclosure** (study-enclosure-mechanics): couple M1 to the
   membrane/enclosure mechanics (protrusion_enclosure + membrane_wrapping) with explicit
   bending/adhesion energy; topology-changing enclosure event.
3. **M3 — joint_feasibility_region** (study-contact-to-enclosure-coupling): feed M1's
   selected-contact regime into M2's enclosure initial conditions; measure overlap.
4. **M4 — full integration** (following_cycle): + energy accounting (S4) + vertical
   transmission (S5) + conflict/partner-loss → net lineage fitness, transition outcomes.

## Coupling contract (feedback, non-negotiable)

Typed shared stores with explicit **units** and **mass/energy conservation** (reuse the
`ConservationLedgerProcess`); pass **actual output states** between modules; support
**topology-changing enclosure events**; **no narrative handoff** substituting for coupling.
Every model records its **inferential scope** (what it does/does not establish).

## Scientific decision points (where expert steering matters most)

1. **Adhesion-cost grounding** — how is the membrane/adhesion cost quantified against the
   exchange benefit? (Determines whether H1 vs H4 is discriminated honestly vs by assumption.)
2. **Contact→exchange coupling** — does contact *gate* exchange access (binary), or scale
   flux continuously with contact duration/area?
3. **Selection grounding** — reuse og_34's compositional-inheritance fitness, or
   bioenergetic_internalization's energetic replicator? (The first is membrane-retention
   grounded; the second is gradient/energetics grounded.)

These are modeling choices that change the result, so they are authored, reviewed inputs —
not defaults the engine silently picks.
