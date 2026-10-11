"""Electrochemistry module family — gradients and pH-driven carbon reduction.

Covers Campaign module **C** (natural electrochemistry and pH-gradient-driven
carbon reduction). See ``workspace/notes/modules.md``.

Planned process contract (not yet implemented):

- ``electrochemistry(pH, Eh, H2, CO2)``
  → ``electron_flux, current, products``.
  Compute H+ gradients, membrane/mineral interface potentials, ion transport and
  electron-transfer-limited CO2 reduction. **A pH difference is not itself proof
  of extractable work.** Reaction-current coupling must obey charge conservation:
  ``J_i = -D_i grad(c_i) - z_i u_i F c_i grad(phi) + v c_i`` (Nernst-Planck;
  electroneutral or Poisson closure).
  Recommended engine: Nernst-Planck-Poisson on FiPy/FEniCSx; PHREEQC for aqueous
  speciation; Cantera/custom heterogeneous kinetics.
  Provenance: ``hudson2020co2`` (pH-gradient reactor, isotope controls),
  ``altair2025carbon`` (macroscale currents ~nA-uA). Counter-voice:
  ``jackson2016natural``, ``tutolo2026rethinking``.

**Key discriminating variable:** encode ``pH(T, P, ionic_strength)``, never
laboratory pH as a constant environmental state.

Placeholder package: no Process/Step classes yet.
"""
