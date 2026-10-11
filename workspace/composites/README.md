# Composites

Composites wire the module processes (`../../viva_genesis/`) into runnable
process-bigraphs. **None are implemented yet** — this workspace is scaffolded as
a design + resource foundation (see `../notes/`), not a claim of a working
abiogenesis simulation.

## Campaign-0 target — the first integrated composite

The recommended first integrated composite (Campaign overview + architecture) is
a **1D/2D porous vent wall**:

- externally prescribed fluid boundary conditions
- thermodynamic speciation (Module A/B → PHREEQC/Reaktoro)
- reactive solute transport (Module B/F → FiPy)
- a minimal Fe/NiS-catalyzed CO2-reduction network (Module C/D → Cantera/SciPy)
- explicit **mass and charge accounting** (see the integration contracts in
  `../notes/architecture.md`)

Serpentinization (Module A) enters first as a **boundary flux**, later as a
coupled mineral-kinetics module.

## Building a composite

1. Wrap a simulator/engine as a Vivarium Process with `/viva-expert` (declare the
   port contract from `../notes/architecture.md` — types, units, conservation
   predicates).
2. Add the process class under the matching `viva_genesis/<family>/` subpackage;
   `build_core()` registers it.
3. Compose and smoke-test with `/viva-run`; drive studies with `/viva-study`.
4. Audit the wiring + completeness with the workbench **§ Contract** panel.
