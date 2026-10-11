"""viva_genesis — origins-of-life hydrothermal-vent campaign package.

Process/Step classes live in module-family subpackages that mirror the Campaign
modules (see ``workspace/notes/modules.md`` and ``workspace/notes/architecture.md``):

- ``geochemistry``   — serpentinization + limiting resources (modules A, I)
- ``transport``      — flow, precipitation, pores, concentration (modules B, F)
- ``electrochemistry`` — pH-gradient-driven carbon reduction (module C)
- ``protometabolism`` — carbon fixation + reaction networks (modules D, E)
- ``compartments``   — amphiphiles, protocells, bioenergetics (modules G, H)
- ``polymers``       — catalytic polymers, information, heredity (module J)
- ``ecology``        — populations, evolution, pre-LUCA transition (stages 7-8)

``core.build_core()`` registers this package's own Process/Step classes. The
subpackages are documented placeholders today (no processes yet); add real
wrapped processes with ``/viva-expert``.
"""
