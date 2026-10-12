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

``core.build_core()`` registers this package's own Process/Step classes.
Campaign 0 is implemented (reduced reproductions in ``geochemistry``/``transport``
+ the ``composites.vent_reactor`` generator); the later campaigns are documented
placeholders. Importing this package registers the campaign's composite
generators (so the workbench discovers them even under an editable install that
``discover_generators`` can't see).
"""

# Side-effect imports: fire the @composite_generator decorators + make the
# Process/Step classes importable so the workspace package alone registers the
# campaign (the hatchling editable install is invisible to packages_distributions).
from . import geochemistry      # noqa: E402,F401
from . import transport         # noqa: E402,F401
from . import electrochemistry  # noqa: E402,F401
from . import protometabolism   # noqa: E402,F401
from . import viz               # noqa: E402,F401
from . import composites        # noqa: E402,F401
