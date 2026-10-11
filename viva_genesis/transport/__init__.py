"""Transport module family — flow, precipitation, pores, and concentration.

Covers Campaign modules **B** (hydrothermal flow, mixing, precipitation and
pores) and **F** (transport, concentration and retention). See
``workspace/notes/modules.md``.

Planned process contracts (not yet implemented):

- ``hydrothermal_circulation(pressure, permeability, heat)`` → ``flow_field``
  (Darcy/advection; reduced network first, OpenFOAM/FEniCSx only if needed).
- ``reactive_precipitation(ion_activities)``
  → ``mineral_phases, porosity, conductivity`` (kinetic mineral precipitation;
  couples porosity back to permeability). Implement BOTH the classical
  "abundant persistent Fe(Ni)S barrier" case and the sulfur-scarce Tutolo-2026
  case (ref ``tutolo2026rethinking``).
- ``spatial_transport(species_fields, T_field, flow)``
  → ``advection/diffusion/thermophoresis`` fluxes. Recommended engine: FiPy
  finite-volume; concentration from the balance of advection, diffusion,
  thermodiffusion (Soret), adsorption, precipitation and degradation.
  Provenance/validation: ``baaske2007extreme``, ``mast2010thermal``,
  reactor architecture ``herschy2014originreactor``.

Fluxes must be conservative across cell and compartment boundaries
(``workspace/notes/architecture.md``).

Placeholder package: no Process/Step classes yet.
"""
