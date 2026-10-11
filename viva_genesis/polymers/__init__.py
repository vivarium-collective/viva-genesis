"""Polymers module family — catalytic polymers, information and heredity.

Covers Campaign module **J** (polymers, information and heredity) and Stage 5
polymer chemistry (oligomerization/hydrolysis). The **least complete link** in a
strict deep-sea alkaline scenario. See ``workspace/notes/modules.md``.

Planned process contracts (not yet implemented):

- ``polymer_chemistry(monomers, size_distributions)``
  → ``polymer_length_distributions, enrichment_factors, survival_of_precursors``
  (size-dependent diffusion, adsorption/desorption, temperature-dependent
  polymerization and degradation; compare residence time vs synthesis timescale).
- ``heredity(polymers)`` → ``copying, catalysis, variation``.
  Introduce polymer sequence- or class-based catalysis, template copying, error
  rates, degradation and genotype-phenotype coupling. **Do not presume a viable
  RNA replication mechanism.** Separate catalyst discovery from inheritance; make
  explicit replication fidelity, substrate activation, chemical costs and
  competition.
  Recommended engine: GillesPy2/StochPy for SSA; rule-based chemistry
  (BioNetGen/NFsim) for combinatorics; custom sequence-level agent dynamics.
  Provenance: ``huber1998peptides`` (mineral/CO peptide formation).

**Treat informational chemistry as a branch point, not a scripted milestone:**
compare RNA-world, peptide-first, compositional heredity, mineral-surface
templating, and exchange with shallow/terrestrial environments. Outputs: lineage
persistence, information retention, evolvability, replication thresholds.

Placeholder package: no Process/Step classes yet.
"""
