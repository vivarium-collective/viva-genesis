# Multicellularity S04 + Shared World + Engine Seam — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take S04 (morphomechanics) off the mean-field onto a real spatial Cellular Potts substrate (viva-cpm): build the shared world blueprint, prove the cross-repo discovery-engine seam, and land S04 end-to-end (growth-driven cluster fracture → propagule-toughness readout) with its acceptance criterion satisfied by a real run.

**Architecture:** A `multicellularity_world(**knobs)` generator in `viva_genesis` wires viva-cpm's `CPMProcess` (via a `local:!…` address string, heavy `import cpm` kept out of the registration file — the existing `protrusion_enclosure_cpm` two-file pattern). Two small viva-cpm extensions make the science runnable: an aggregate-cluster fragmentation metric, and optional mitosis + aggregate-metric emission on `CPMProcess`. The study is graded by a cross-run behavior test and promoted through `discover refine-study --composite` + `advance --autonomous`.

**Tech Stack:** Python 3.12, process-bigraph (`@composite_generator`), viva-cpm (Rust `cpm_core` via pyo3; packages `cpm` + `viva_cpm` + `viva_cpm_studies`), discovery-engine `discover` CLI, vivarium-workbench runner + `run` test fixture, pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-multicellularity-multiscale-design.md` (this plan implements §6, §7.1, §7.2, §7.5–§7.8, §11; S05/S06 are separate plans written after this lands).

## Global Constraints

- **No AI attribution** in any commit message or PR body/title (no `Co-Authored-By: Claude`, no "Generated with Claude Code"). Verbatim from the user's standing rule.
- **viva-cpm is the only CPM backend.** Extend viva-cpm for missing methods; never add Morpheus/Artistoo/CompuCell3D.
- **Worktree discipline.** viva-genesis work stays in this worktree (`/Users/eranagmon/code/viva-genesis--multicellularity`, branch `multicellularity`). viva-cpm work goes in a **new dedicated worktree** off `origin/main` (canonical `~/code/viva-cpm` is read-only). Verify `git branch --show-current` + `git rev-parse --short HEAD` before every commit/push. Squash-merge. Never bare `git stash`.
- **Real registered composites only.** `baseline[].composite` must resolve to a registered generator id (`<module>.<name>`); runs must persist via an emitter.
- **A composite depending on `viva_cpm` keeps `import cpm` OUT of the generator file** — reference the process by `local:!viva_cpm.processes.cpm_process.CPMProcess`. Registration must work even when `viva_cpm` is absent; only a *run* needs it.
- **Compute budget:** 2D demo-scale lattices (~80×40 order), bounded steps, single runs on the laptop; the adhesion × seed calibration sweep on the Mac mini via Ray.
- **Provided-mechanisms-only honesty:** if the toughness behavior does not emerge from the provided physics, record an HONEST OPEN QUESTION — never add an un-provided constant/cap/sink to force a PASS.
- **Rigor bar per study:** ≥3 seeds, a negative control (no-adhesion system that should fail to form a cohesive propagule), alternative hypotheses, tiered findings, falsifiability, limitations.
- **Verdict honesty (§11):** S04's current `passing-with-caveats` is asserted with zero runs — reset it to unproven before the real run earns it.

## Review Focus

- **Cross-repo engine seam may not carry a viva_cpm composite.** `advance --autonomous` shells to `vivarium-workbench run study`; if the workbench runner can't resolve `local:!viva_cpm…` or persist its outcomes, the seam goal breaks. → Task 1 is a hard gate that proves it on the existing `protrusion_enclosure_cpm` before any S04 work; documented manual-swap fallback if it fails.
- **`per_generation_mean` does not exist** on the `Run` fixture (SKILL.md is stale). → Task 5's test averages in-line over `run.observable(...)`; no call to `per_generation_mean`.
- **Degenerate lattice** (cluster dissolves to medium, single-pixel cell, all-medium frame). → Task 2's metric test includes an empty-mask case (returns 0) and a single-blob case (returns 1); no crash.
- **Contact matrix with a missing type pair silently yields J=0.** → Task 4 populates every type pair and its test asserts the intended adhesion actually took effect (cohesion differs between strong/weak J).
- **Per-key map outputs dropped when the store isn't pre-seeded** (the `fates`/map contract). → Task 3/Task 4 pre-seed any map store they write and the test asserts the emitted aggregate observable is present and non-null.

---

## File Structure

**viva-cpm (new worktree, PRs to `vivarium-collective/viva-cpm`):**
- Modify `viva_cpm/metrics.py` — add `aggregate_components`, `largest_cluster_fraction` (Task 2).
- Modify `viva_cpm/processes/cpm_process.py` — optional mitosis + aggregate-metric emission (Task 3).
- Test `viva-cpm/tests/test_aggregate_metrics.py` (Task 2), `tests/test_cpm_mitosis_and_aggregate.py` (Task 3).

**viva-genesis (this worktree, branch `multicellularity`):**
- Create `viva_genesis/composites/multicellularity_world.py` — `build_world_spec(**knobs)` factory + `s04_morphomechanics` generator (address-string only; no `import cpm`) (Task 4).
- Test `tests/test_multicellularity_world.py` (Task 4).
- Modify `workspace/studies/s04-morphomechanics/study.yaml` — composite swap + verdict reset (Task 5).
- Create `workspace/studies/s04-morphomechanics/tests/conftest.py`, `tests/test_propagule_toughness.py` (Task 5).
- Create the S04 visualization via `/viva-viz` into `viva_genesis/viz/` (Task 6).

---

### Task 1: Prove the cross-repo engine seam (hard gate — spike)

Verification task, no TDD code. If it fails, STOP and fall back to the documented manual path; do not start Task 4+ assuming the seam works.

**Files:** none created. Touches the genesis `.venv` and a throwaway sandbox study (reverted after).

- [ ] **Step 1: Install the spatial extra into the genesis venv.**
  Run: `cd /Users/eranagmon/code/viva-genesis--multicellularity && uv pip install -e .[spatial]` (or add a `.pth` to `~/code/viva-cpm`).
  Then: `.venv/bin/python -c "from cpm import cpm_core; import viva_cpm; print('ok', viva_cpm.__file__)"`
  Expected: prints `ok <path>` — no `ModuleNotFoundError`.

- [ ] **Step 2: Confirm the existing CPM composite runs under the workbench runner and emits into runs.db.**
  Use the already-registered generator `viva_genesis.composites.protrusion_enclosure_cpm.protrusion_enclosure_cpm`. Run it through `/viva-run` (or `vivarium-workbench run study` against a sandbox study whose `baseline[].composite` is that id).
  Expected: a run completes and `runs.db` gains a `runs_meta` row + `history` rows (non-empty emitted `state`).

- [ ] **Step 3: Exercise the discovery seam end-to-end on a sandbox study.**
  Create a throwaway study (`/viva-study new`) or copy s04's seed; then:
  `discover --workspace . refine-study multicellularity <sandbox> --composite viva_genesis.composites.protrusion_enclosure_cpm.protrusion_enclosure_cpm --autonomy human_in_the_loop --write`
  Confirm `baseline[].composite` was rewritten. Then:
  `discover --workspace . advance multicellularity --autonomous`
  Expected: a run executes via the `vivarium-workbench run study` subprocess and the sandbox study gains `runs[].outcomes`.

- [ ] **Step 4: Record the result and decide the path.**
  If Steps 2–3 pass: note in the plan that the seam carries a cross-repo CPM composite; proceed. If they fail: capture the exact error, file a gap against discovery-engine/workbench, and switch Task 5 to the **manual fallback** (`vivarium-workbench run study` directly + `discovery_engine.study.outcomes.sync`), not `advance`.

- [ ] **Step 5: Revert the sandbox.** Remove the throwaway study / restore any edited seed so the workspace is clean. Commit nothing from this task except (optionally) a short note in the plan.

---

### Task 2: viva-cpm — aggregate-cluster fragmentation metric

**Files:**
- Modify: `viva_cpm/metrics.py`
- Test: `tests/test_aggregate_metrics.py`
- (In a new viva-cpm worktree off `origin/main`.)

**Interfaces:**
- Consumes: `viva_cpm.metrics._neighbors_moore` (existing flood-fill adjacency, `metrics.py:29`); `world.snapshot()` + `world.cell_types()` (as `connected_components` uses).
- Produces:
  - `aggregate_components(world, types: list[int]) -> int` — number of connected components of the merged mask `{sites whose cell's type ∈ types}` (medium excluded), using the same Moore adjacency as `connected_components`.
  - `largest_cluster_fraction(world, types: list[int]) -> float` — largest component's site count ÷ total masked site count; `0.0` when the mask is empty.

- [ ] **Step 1: Set up the viva-cpm worktree.**
  `git -C ~/code/viva-cpm fetch origin main && git -C ~/code/viva-cpm worktree add ~/code/viva-cpm--multicell-metrics -b multicell-metrics origin/main`

- [ ] **Step 2: Write the failing tests** in `tests/test_aggregate_metrics.py`:

```python
def test_two_detached_blobs_same_type_counts_two():
    world = _world_with_two_separated_blobs(type_=1)   # helper builds a spec with two non-adjacent type-1 clusters
    assert aggregate_components(world, [1]) == 2

def test_one_cohesive_blob_counts_one():
    world = _world_with_single_blob(type_=1)
    assert aggregate_components(world, [1]) == 1

def test_empty_mask_is_zero_not_crash():
    world = _world_with_single_blob(type_=1)
    assert aggregate_components(world, [9]) == 0          # no cells of type 9
    assert largest_cluster_fraction(world, [9]) == 0.0

def test_largest_fraction_on_70_30_split():
    world = _world_with_two_blobs(type_=1, sizes=(70, 30))
    assert abs(largest_cluster_fraction(world, [1]) - 0.7) < 0.05
```

- [ ] **Step 3: Run tests to verify they fail.**
  Run: `pytest tests/test_aggregate_metrics.py -v` — Expected: FAIL (`aggregate_components` not defined).

- [ ] **Step 4: Implement `aggregate_components` and `largest_cluster_fraction` in `viva_cpm/metrics.py`.**
  Build the masked site set over all cells whose type ∈ `types`, then flood-fill with `_neighbors_moore` (mirroring `connected_components`, `metrics.py:47-69`) to count/size components. Guard the empty mask.

- [ ] **Step 5: Run tests to verify they pass.** Run: `pytest tests/test_aggregate_metrics.py -v` — Expected: PASS.

- [ ] **Step 6: Commit.**
  `git add viva_cpm/metrics.py tests/test_aggregate_metrics.py && git commit -m "feat(metrics): aggregate multi-cell cluster fragmentation metric"`

---

### Task 3: viva-cpm — CPMProcess optional mitosis + aggregate-metric emission

**Files:**
- Modify: `viva_cpm/processes/cpm_process.py`
- Test: `tests/test_cpm_mitosis_and_aggregate.py`
- (Same viva-cpm worktree as Task 2.)

**Interfaces:**
- Consumes: Task 2's `aggregate_components`, `largest_cluster_fraction`; `world.grow(type, rate)`, `world.divide_cells(threshold, reset_target) -> list[int]`, `world.n_cells()` (pyo3 binding, verified present).
- Produces: `CPMProcess` gains two optional config keys and two optional outputs:
  - config `mitosis: list[{type:int, grow_rate:float, divide_threshold:float, reset_target:float}]` (default `[]`) — after each `world.step`, for each entry call `world.grow(type, grow_rate)` then `world.divide_cells(divide_threshold, reset_target)`.
  - config `report_aggregate_types: list[int]` (default `[]`) — when non-empty, emit outputs `n_propagules: int` (= `aggregate_components(world, report_aggregate_types)`) and `largest_cluster_fraction: float`, both `overwrite`.

- [ ] **Step 1: Write the failing tests** in `tests/test_cpm_mitosis_and_aggregate.py`:

```python
def test_mitosis_grows_cell_count():
    comp = _run_spec(_spec_with_mitosis(type_=1, grow_rate=2.0, divide_threshold=50.0,
                                         reset_target=25.0), updates=20)
    assert comp.state["n_cells_final"] > comp.state["n_cells_initial"]   # via a tiny probe, or assert world.n_cells grew

def test_aggregate_output_present_and_nonnull():
    comp = _run_spec(_spec_reporting_aggregate(types=[1]), updates=5)
    assert comp.state["n_propagules"] is not None
    assert comp.state["n_propagules"] >= 1

def test_strong_adhesion_stays_cohesive_weak_fractures_under_growth():
    strong = _run_spec(_growth_spec(homotypic_j=2.0, report=[1]), updates=40)   # low J == strong adhesion
    weak   = _run_spec(_growth_spec(homotypic_j=14.0, report=[1]), updates=40)  # high J == weak adhesion
    assert strong.state["n_propagules"] <= weak.state["n_propagules"]
```

- [ ] **Step 2: Run tests to verify they fail.** Run: `pytest tests/test_cpm_mitosis_and_aggregate.py -v` — Expected: FAIL (config keys/outputs unknown).

- [ ] **Step 3: Implement the extension in `viva_cpm/processes/cpm_process.py`.**
  Add `mitosis` and `report_aggregate_types` to `config_schema` (after the existing `secretory_types`, `cpm_process.py:147-152`). In `update()` after `self.world.step(self.mcs)` (`cpm_process.py:216`): run the mitosis grow/divide loop, then if `report_aggregate_types` compute and attach the two aggregate outputs. Declare the two outputs in `outputs()` (`cpm_process.py:161-180`). Keep both paths no-ops when their config is empty (preserves current behavior).

- [ ] **Step 4: Run tests to verify they pass.** Run: `pytest tests/test_cpm_mitosis_and_aggregate.py -v` — Expected: PASS. Also run the existing CPM process/field/crypt tests to confirm no regression: `pytest tests/ -k "cpm or crypt or field or mitosis" -q`.

- [ ] **Step 5: Commit.**
  `git add viva_cpm/processes/cpm_process.py tests/test_cpm_mitosis_and_aggregate.py && git commit -m "feat(cpm): optional mitosis + aggregate-cluster reporting on CPMProcess"`

- [ ] **Step 6: Push + open the viva-cpm PR** (verify branch/HEAD + `git log --oneline origin/main..HEAD` shows only your two commits first). Hold for the user's merge approval (never auto-merge). The genesis venv already points at the viva-cpm checkout (Task 1), so Task 4 can build against the worktree via `PYTHONPATH`/editable install even before merge.

---

### Task 4: viva-genesis — shared `multicellularity_world` blueprint + S04 composite generator

**Files:**
- Create: `viva_genesis/composites/multicellularity_world.py`
- Test: `tests/test_multicellularity_world.py`

**Interfaces:**
- Consumes: viva-cpm Tasks 2–3 (mitosis + `report_aggregate_types` emitting `n_propagules`); `CPMProcess` via `local:!viva_cpm.processes.cpm_process.CPMProcess`; the `@composite_generator` convention and `core_extensions=[build_core]` (mirror `viva_genesis/composites/protrusion_enclosure_cpm.py`).
- Produces:
  - `build_world_spec(*, adhesion: float, seed_volume: float = 30.0, grow_rate: float = 2.0, divide_threshold: float = 55.0, dims=(80,40,1), report_types=(1,)) -> dict` — the shared CPM `spec` (potts + one seeded clonal cluster of type 1 + full contact matrix where homotypic J is derived from `adhesion` + mitosis entry + `report_aggregate_types`). **Factory reused by S05/S06 later.**
  - generator `s04_morphomechanics(core=None, *, adhesion=<default>, grow_rate=<default>, divide_threshold=<default>) -> dict` registered as id `viva_genesis.composites.multicellularity_world.s04_morphomechanics`, wiring `CPMProcess` with `config={"spec": build_world_spec(...), "mcs_per_update": 16, "report_aggregate_types": list(report_types)}` and an emitter (copy the emitter node + `core_extensions` from `protrusion_enclosure_cpm`). **No `import cpm` in this file.**

- [ ] **Step 1: Write the failing tests** in `tests/test_multicellularity_world.py` (require `.[spatial]`; skip if `cpm` unimportable, mirroring existing spatial tests):

```python
def test_generator_registers_with_expected_id():
    from process_bigraph.composite_spec import get_registry   # or the project's lookup
    assert "viva_genesis.composites.multicellularity_world.s04_morphomechanics" in _registered_ids()

def test_contact_matrix_populates_every_type_pair():
    spec = build_world_spec(adhesion=0.8)
    pairs = {(e["a"], e["b"]) for e in spec["contact"]}
    assert (0, 1) in pairs and (1, 1) in pairs            # medium-cell AND homotypic present (no silent J=0)

def test_strong_adhesion_cluster_stays_cohesive():
    comp = _run_generator(adhesion=0.95, updates=40)
    assert comp.state["n_propagules"] == 1

def test_weak_adhesion_cluster_fractures_under_growth():
    comp = _run_generator(adhesion=0.15, updates=40)
    assert comp.state["n_propagules"] > 1

def test_zero_differential_adhesion_forms_no_cohesive_propagule():   # negative control
    comp = _run_generator(adhesion=0.0, updates=40)
    assert comp.state["largest_cluster_fraction"] < 0.5
```

- [ ] **Step 2: Run tests to verify they fail.** Run: `pytest tests/test_multicellularity_world.py -v` — Expected: FAIL (module absent).

- [ ] **Step 3: Implement `build_world_spec` + the `s04_morphomechanics` generator** in `viva_genesis/composites/multicellularity_world.py`, copying the generator scaffold (decorator args, emitter node, `core_extensions=[build_core]`, `local:!…` address) from `viva_genesis/composites/protrusion_enclosure_cpm.py`. Map `adhesion∈[0,1]` to the homotypic contact `j` (higher adhesion → lower J), populate `(0,1)` and `(1,1)` contact entries, add the mitosis entry and `report_aggregate_types`. Pre-seed any map store the process writes.

- [ ] **Step 4: Run tests to verify they pass.** Run: `pytest tests/test_multicellularity_world.py -v` — Expected: PASS. Confirm registration also survives WITHOUT the heavy import: `.venv/bin/python -c "import viva_genesis; print('registered' )"` must not error even if `cpm` were absent (import of the generator file must not import `cpm`).

- [ ] **Step 5: Commit.**
  `git add viva_genesis/composites/multicellularity_world.py tests/test_multicellularity_world.py && git commit -m "feat(multicellularity): shared CPM world blueprint + S04 morphomechanics composite"`

---

### Task 5: viva-genesis — wire S04 study, behavior test, run, grade, reset verdict

**Files:**
- Modify: `workspace/studies/s04-morphomechanics/study.yaml`
- Create: `workspace/studies/s04-morphomechanics/tests/conftest.py`, `workspace/studies/s04-morphomechanics/tests/test_propagule_toughness.py`

**Interfaces:**
- Consumes: Task 4's generator id; the `run`/`runs` fixtures from `vivarium_workbench.testing` (`Run.observable/.final/.params/.label`; **no `per_generation_mean`**); the acceptance behavior `propagule-toughness-predicted` (already in `investigation.yaml` `acceptance_criteria`); the cross-run grading pattern from the sibling study `workspace/studies/s03-transport-limits/study.yaml` (its `size-viability-tracks-transport` outcome uses `operator: cross_run, evaluated_by: code` — copy that authoring shape).
- Produces: s04 with a real run and `runs[].outcomes["propagule-toughness-predicted"].result == PASS`, and `investigation.yaml` `executive.computed_acceptance` marking the s04 criterion satisfied.

- [ ] **Step 1: Reset the asserted verdict (§11).** In `study.yaml` set `status: investigating`, clear/neutralize the un-run `passing-with-caveats` verdict (set `verdict:` to unproven/`investigating`, `confidence: provisional`), so no claim stands without a run. Do NOT hand-edit the composite/runs outside the skills where `/viva-study` applies.

- [ ] **Step 2: Point the study at the spatial composite.** Prefer the seam: `discover --workspace . refine-study multicellularity s04-morphomechanics --composite viva_genesis.composites.multicellularity_world.s04_morphomechanics --write` (plus `params:` for the adhesion sweep points). If Task 1 flagged the seam as unavailable, set `baseline[].composite` + sweep `variants[]` via `/viva-study` instead.

- [ ] **Step 3: Write the failing behavior test** `tests/test_propagule_toughness.py` with `tests/conftest.py` doing `from vivarium_workbench.testing import run, runs  # noqa: F401`. Set `study.yaml tests.data_source: all_runs` and use the parametrized `runs` fixture. Per-run assertions (the cross-run monotonic roll-up is authored as the study outcome, copying s03):

```python
def test_cohesive_at_strong_adhesion(runs):            # one invocation per run
    r = runs
    if float(r.params["adhesion"]) >= 0.9:
        assert r.final("n_propagules") == 1            # strong adhesion → single propagule
    if float(r.params["adhesion"]) <= 0.1:             # negative control arm
        assert r.final("largest_cluster_fraction") < 0.5
```

- [ ] **Step 4: Run the test to verify it fails** (no runs yet). Run: `pytest workspace/studies/s04-morphomechanics/tests/ -v` — Expected: FAIL / errors (no `runs.db` rows).

- [ ] **Step 5: Run the adhesion × seed sweep.** Calibrate with a grid (e.g. adhesion ∈ {0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95}) × ≥3 seeds in one pass on the **Mac mini via Ray** (not single values). Execute via `discover --workspace . advance multicellularity --autonomous` (seam) or the manual `vivarium-workbench run study s04-morphomechanics --workspace .` fallback per Task 1.

- [ ] **Step 6: Author the cross-run outcome + grade.** Following s03's `size-viability-tracks-transport` shape, author `propagule-toughness-predicted` as a `cross_run` outcome: the largest cohesive cluster size is non-decreasing in adhesion AND the no-adhesion control fails to form a cohesive propagule. Let the evaluator compute it from run data. Run `pytest workspace/studies/s04-morphomechanics/tests/ -v` — Expected: PASS. **If the monotonic toughness relation does NOT emerge, record it as an HONEST OPEN QUESTION in the study — do not patch the physics to force PASS.**

- [ ] **Step 7: Confirm acceptance roll-up.** Verify `runs[].outcomes["propagule-toughness-predicted"].result == PASS` and that `investigation.yaml` `executive.computed_acceptance` lists the s04 criterion as satisfied (via `/viva-report` or the `write_investigation_acceptance` path).

- [ ] **Step 8: Commit.**
  `git add workspace/studies/s04-morphomechanics/ && git commit -m "feat(s04): spatial morphomechanics — propagule-toughness from CPM cluster fracture"`

---

### Task 6: viva-genesis — S04 spatial visualization (watchable fracture)

**Files:**
- Create: an S04 visualization via `/viva-viz` (into `viva_genesis/viz/`), registered so the study report renders it.

**Interfaces:**
- Consumes: the emitted `types`/`positions`/`n_propagules`/`largest_cluster_fraction` timeseries from the S04 runs (Task 5).
- Produces: a registered visualization showing the clonal cluster growing and snapping into propagules over time (lattice snapshots colored by cluster, plus the `n_propagules` trace), and the toughness curve (critical cohesive size vs adhesion) across the sweep.

- [ ] **Step 1: Build the visualization** with `/viva-viz` — push for an interactive/animated spatial view, not a default line chart (per the viz skill). Two panels: (a) time-lapse lattice snapshots colored by connected cluster; (b) propagule-toughness curve over the adhesion sweep with seed spread.
- [ ] **Step 2: Verify it renders** against a real S04 run (no fabricated preview) via `/viva-report` or the workbench study page.
- [ ] **Step 3: Commit.** `git add viva_genesis/viz/ workspace/studies/s04-morphomechanics/ && git commit -m "viz(s04): animated cluster-fracture + propagule-toughness curve"`

---

## Self-Review

- **Spec coverage:** §6 (verified substrate) → Tasks 2–4 build on it; §7.1 shared blueprint → Task 4 `build_world_spec`; §7.2 S04 → Tasks 3–6; §7.5 coupling contracts → implicit in the CPMProcess port wiring (field/subcellular couplings arrive in S05's plan, flagged); §7.6 engine seam → Tasks 1, 5; §7.7 sequencing → this plan IS the S04-first stage; §7.8 packaging + seam spike → Tasks 1, 4; §11 verdict reset → Task 5 Step 1. **Deferred to later plans (noted):** §7.3 (S05 O₂ field + germ/soma network), §7.4 (S06 lineage + Price partition + reseed loop). The `cell ↔ subcellular` and `field ↔ cell` couplings are not exercised here because S04 is pure morphomechanics (adhesion + growth) — correct for this stage.
- **Step scan:** each code step gives a signature or exact assertions; no "handle edge cases" placeholders.
- **Type consistency:** `n_propagules` (int) and `largest_cluster_fraction` (float) are named identically in Tasks 3, 4, 5; `aggregate_components(world, types)` / `largest_cluster_fraction(world, types)` signatures match between Task 2 (def) and Task 3 (use); generator id string identical in Tasks 4 and 5.
- **Review Focus:** all five lines have an owning test (seam gate T1; no `per_generation_mean` T5 S3; degenerate mask T2; silent-J=0 T4; unseeded map T3/T4).
- **Proportion:** plan is longer than the eventual diff only in test-assertion text; no full function bodies are transcribed.
