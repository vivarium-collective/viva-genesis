# viva-genesis

<!-- BEGIN dashboard -->
> ## 📊 [**Live dashboard →**](https://vivarium-collective.github.io/viva-genesis/dashboard/)
> Browse every investigation & study interactively, or read the [published investigation reports](https://vivarium-collective.github.io/viva-genesis/). Auto-published from `main` on every merge.
<!-- END dashboard -->

**An origins-of-life hydrothermal-vent simulation campaign, built on [Vivarium](https://github.com/vivarium-collective) / process-bigraph.**

It treats the origin of cells not as one event but as a chain of coupled,
independently falsifiable transitions — geochemical disequilibrium → carbon
fixation → concentration and compartmentalization → protometabolism → protocells
→ heredity → autonomy — grounded in deep-sea serpentinization-driven alkaline
vents, with competing scenarios (shallow-vent, terrestrial-geothermal,
cyanosulfidic) kept as explicit alternatives rather than assumptions.

Every stage is a composite of **real simulators** wrapped as process-bigraph
processes — PHREEQC geochemistry, FiPy and FEniCS/dolfinx transport, eQuilibrator
thermodynamics, libRoadRunner reaction networks — run against pre-registered,
falsifiable acceptance gates with mass, charge, and free-energy ledgers held to
machine precision.

## What it shows

The full geochemistry-to-heredity arc runs end to end and passes its pre-stated
gates. The campaign is deliberately honest about what that means: it maps
*where* the proposed alkaline-vent trajectory is internally compatible, where it
has bounded operating regions, and where resources or innovations become
bottlenecks — including the honest negatives (e.g. the limitation on carbon
fixation is structure-sensitive, and the integrated {pump, importer, heredity}
set is not jointly sufficient off-gradient).

It does **not** claim that life historically originated at alkaline vents.
Several stages begin from specified reaction networks or coarse-grained models;
the value is that those assumptions are explicit, executable, sweepable, and
increasingly vulnerable to ablation, adversarial controls, and replacement by
higher-fidelity models.

The genuine simulators are **imported** from dedicated wrapper repositories
rather than reimplemented here:
[viva-equilibrator](https://github.com/vivarium-collective/viva-equilibrator) ·
[viva-tellurium](https://github.com/vivarium-collective/viva-tellurium) ·
[viva-fenics](https://github.com/vivarium-collective/viva-fenics).

## Design and framing

| Document | What |
|---|---|
| [`campaign-overview.md`](workspace/notes/campaign-overview.md) | Core idea, primary question, stage order, milestones. |
| [`hypothesis-graph.md`](workspace/notes/hypothesis-graph.md) | Stages and mechanistic links with evidence status and a provenance crosswalk. |
| [`modules.md`](workspace/notes/modules.md) | Mechanistic modules → Vivarium process signatures. |
| [`architecture.md`](workspace/notes/architecture.md) | Process-bigraph design: process table, shared stores, coupling, conservation contracts. |
| [`provenance-schema.md`](workspace/notes/provenance-schema.md) | Evidence classes (FIELD / LAB / MODEL / RECONSTRUCTION / HYPOTHESIS) and model-card requirements. |
| [`experiments-and-falsification.md`](workspace/notes/experiments-and-falsification.md) | Discriminating tests, acceptance gates, reproduction targets, competing environments. |
| [`risk-register.md`](workspace/notes/risk-register.md) · [`data-acquisition.md`](workspace/notes/data-acquisition.md) | Evidence gaps and model risks; datasets to acquire. |

**Resources:**
[`computational-resources.md`](workspace/references/computational-resources.md)
(engines, databases, standards) ·
[`papers.bib`](workspace/references/papers.bib) (annotated references) ·
[`parameter-registry.yaml`](workspace/datasets/parameter-registry.yaml)
(provenance-classed parameters).

## Getting started

```bash
uv venv .venv && source .venv/bin/activate && uv pip install -e ".[dev]"
python scripts/lint-workspace.py        # workspace lint: OK
pytest -q                               # package + registration guards
bash scripts/serve.sh                   # open the interactive workbench locally
```

Build processes and composites by wrapping a simulator with `/viva-expert`, run
them with `/viva-run`, drive studies with `/viva-study`, and group them with
`/viva-investigation`. See [`AGENTS.md`](AGENTS.md) for the PR conventions.

## Layout

Code lives at the repo root; research state is grouped under `workspace/`
(paths come from the `layout:` map in `workspace.yaml`).

- `viva_genesis/` — the Python package; `core.py` exposes `build_core()`, with module families (`geochemistry`, `transport`, `electrochemistry`, `protometabolism`, `bioenergetics`, `heredity`, `ecology`, `membranes`, …) in subpackages.
- `workspace/investigations/`, `workspace/studies/` — the investigation and its per-study design, runs, and visualizations.
- `workspace/notes/` — campaign design documents.
- `workspace/references/` — `papers.bib` and the computational-resources catalog.
- `workspace/datasets/` — the provenance-classed parameter registry.
- `.pbg/schemas/` — the JSON schemas the lint and workbench validate against.

<!-- the two tables below are generated by `vivarium-workbench gen-readme` and kept fresh by CI. -->

### Composites

<!-- BEGIN:composites -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Composite | What it is |
|---|---|
<!-- END:composites -->

### Investigations

<!-- BEGIN:investigations -->
<!-- generated by `vivarium-workbench gen-readme` — edit the source, not this table -->

| Investigation | Research question |
|---|---|
| [Origins-of-life vent campaign _(running)_](https://vivarium-collective.github.io/viva-genesis/investigations/origins-of-life-vent.html) | Could the first cells have originated at alkaline hydrothermal vents? |
<!-- END:investigations -->
