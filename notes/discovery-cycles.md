# Discovery-engine cycles — origins-of-life-vent

Running log of turning the `viva-discover crank` on this investigation. Each entry
records the crank state, the next-action it recommended, what was executed, the
result, and — the point of this log — **observations about the discovery engine and
concrete opportunities to improve it**. Engine-improvement items are candidates to
graduate into viva-superpowers (`viva_superpowers/discovery_engine.py`,
`discover.py`, `knowledge_store.py`).

How to run a crank (the engine modules are on superpowers `origin/main`, but the
genesis venv's *installed* superpowers is stale and lacks them, and the installed
`viva_workspace` has the `canonical_run` timestamp bug — so both must be shadowed):

```bash
cd ~/code/viva-genesis--harden
PYTHONPATH="$HOME/code/viva-superpowers--knowledge-store:$HOME/code/viva-workspace--ts-key" \
  ~/code/viva-genesis/.venv/bin/python -m viva_superpowers.discover \
  --workspace "$HOME/code/viva-genesis--harden" crank origins-of-life-vent
```

---

## Cycle 1 — 2026-10-25 (Phase 2: connect-and-close the self-maintenance refutation)

Summary (for continuity; recorded in the study YAMLs, not here): the crank pointed at
the refuted self-maintenance step; the cycle built the connected composite
`og_self_maintaining_concentrated` (reactor → chain-extension → FiPy thermophoretic
trap), grounded the amphiphile Soret coefficient `S_T(I)` to measured data
(`membranes/amphiphile_soret.py`), and produced `og-self-maintaining-concentrated`
(qualified: closes under favorable low-salinity trapping, marine vent excluded 6-7
orders). Follow-ups: grounded Soret, gas-bubble interface (magnitude-limited),
autocatalysis (refutation persists).

---

## Cycle 2 — 2026-10-25 (competing environments: is vent-specificity real?)

### Crank state (before)
`closure: OPEN` — unaddressed criteria 1, open gaps 9, open challenges 3, frontier 35.
**Next action:** `[branch] unaddressed_criterion on og-vent-specificity` (priority 90)
— "acceptance criterion not met (verdict: refuted)."

### Action taken (the branch)
`og-vent-specificity` refuted a *feature-ablated* generic null (its designed, positive
result — the five gates reject a drive stripped of H2 + Fe/Ni/S + pore concentration).
But its own claim admits the harder test — specificity against **positive, realistic
competing environments** — was *planned, not run* (`og-ev-competing-environments`). So
the branch = run that test.

Reusing the Cycle-1 grounded Soret model, I held the thermophoretic trap at the vent's
own favorable geometry (ΔT 45 K, 5 mm pore, base aggregation_competent 9.46e-8) and
varied **only ionic strength** across competing environments, driving the real
`ThermophoreticTrapProcess` enrichment law (`transport/fenics_reactor.py`, verified to
reproduce the canonical S_T 0.10/ΔT30 → 9.6e7) with `S_T(I) = soret_of_ionic_strength(I)`
under both the Piazza-Guarino (λ_D²) and Duhr-Braun (λ_D) laws.

### Result (compartmentation gate, matched geometry; aggregation_competent_concentrated vs CAC=1)

| environment | I (M) | ac (Piazza-Guarino) | ac (Duhr-Braun) | gate |
|---|---|---|---|---|
| Marine serpentinizing alkaline vent (Lost City) | 0.60 | 2.4e-7 | 2.6e-6 | fail (worst) |
| Marine black smoker | 0.60 | 2.4e-7 | 2.6e-6 | fail |
| Terrestrial hot spring | 0.08 | 2.4e-6 | 3.3e-4 | fail |
| Freshwater geothermal (Mulkidjanian pond) | 0.02 | 7.7e-3 | 6.6e-1 | fail |
| Low-salinity freshwater / condensate | 0.005 | 7.7e11 | 2.6e6 | **PASS** |
| Very dilute meltwater | 0.001 | 3.3e12 | 3.3e12 | **PASS** |

The compartmentation gate is **monotone in low salinity**: the marine vent is the
*worst* performer, not specifically favored; it closes only at freshwater I ≤ ~0.005 M.
The chemistry gates (sustained H2, Fe/Ni/S, alkaline pH gradient) remain vent-specific
serpentinization geochemistry that freshwater lacks. So competing environments **split**
the five gates — no single realistic environment passes all five at grounded parameters.

**Deliverable:** `workspace/studies/og-ev-competing-environments/study.yaml`, verdict
**qualified** — og-vent-specificity is re-cast from *environment*-specific to
*feature*-specific; chemistry favors the vent, compartmentation favors freshwater,
pointing to a transitional/coupled scenario (vent chemistry feeding a low-salinity
compartmentation stage — a mixing zone, a freshening excursion, or the gas-bubble
interface from Cycle 1).

### Crank state (after)
**Unchanged** — still `[branch] unaddressed_criterion on og-vent-specificity` at
priority 90, frontier 35. The new study did not move closure. This is the cycle's
most important finding about the engine (below).

### Observations (engine behavior)

1. **The crank's top recommendation was a false frontier item.** `og-vent-specificity`
   is an adversarial *null control*: `refuted` is its designed, successful outcome, and
   its acceptance behavior `gates-reject-generic` actually **passed** (`gate_status:
   passed`). But `frontier()` reads the study's roll-up **verdict**, and
   `_MET = ("supported","qualified")`, so `refuted ∉ _MET` ⇒ it is flagged
   `unaddressed_criterion` at the *highest* priority (90). The engine conflates the
   epistemic verdict-sign with acceptance — violating the framework's own
   "progress ⊥ verdict" two-axis principle. A refuted null is a *met* criterion.

2. **The engine does not close its own loop.** `next_action` recommended `branch`;
   I executed the branch (created `og-ev-competing-environments`, completed, qualified,
   with a `tests` prerequisite edge back to `og-vent-specificity`). The frontier did
   not change, because closure is computed from `investigation.acceptance_criteria[].study`
   → that parent study's verdict. There is no notion of a child study *discharging* a
   parent's criterion. The knowledge-clock transition I_{n+1}=T(aₙ,Iₙ,δₙ) is not
   reflecting the action aₙ. A branch result is "dangling" w.r.t. closure until a human
   re-points the criterion or edits the parent.

3. **Acceptance tracks the study verdict, not the named behavior.** Each criterion is
   `{study, behavior}` (e.g. `gates-reject-generic`), but `frontier()` never looks at
   whether *that behavior's* test passed — only the study's overall verdict. A study can
   pass the exact named behavior and still be flagged unmet.

4. **Crank is unrunnable from a clean install (two stale-dependency blockers).**
   (a) the genesis venv's installed `viva_superpowers` predates the discover modules
   (they're on superpowers `origin/main` but not pip-installed here); (b) the installed
   `viva_workspace.canonical_run` throws `TypeError: '>' not supported between 'str' and
   'float'` on mixed-type run timestamps. Both must be shadowed via PYTHONPATH
   (`viva-superpowers--knowledge-store` + `viva-workspace--ts-key`) or the crank dies.

5. **Lint vs engine disagree on run/status accounting.** `lint-workspace.py` reports
   "0 completed runs" and "23 studies (status: 23 unknown)" for studies that carry
   `execution_status: completed` + `runs[].status: completed` in YAML — the lint counts
   `runs.db` artifacts, the engine reads YAML fields. The two readers should agree.

### Opportunities to improve discovery (candidates → viva-superpowers)

- **Acceptance = behavior outcome, not verdict sign.** In `frontier()` (line ~81),
  evaluate the criterion's named `behavior`'s test result; count a criterion *met* when
  its behavior passes, independently of the study's roll-up verdict. This alone fixes
  the null-control false-positive (#1, #3). Minimal alt: treat `refuted` as met when the
  study is flagged `study_type: null-control`/`adversarial`.
- **Add a `discharge`/`addresses` edge so the loop closes (#2).** When a completed child
  study with a `tests`/`addresses` relation to a parent carries a met verdict, mark the
  parent's corresponding criterion addressed (or drop the frontier item's priority). The
  crank recommends `branch`; it must then *recognize the branch it recommended*.
- **Land the `viva-workspace` `canonical_run` timestamp-coercion fix to main (#4)** —
  coerce run timestamps to a common type before `max(...)`; it is a hard crash for any
  crank from a clean install.
- **Version/declare the `viva-superpowers` crank dependency (#4)** so a workspace venv
  resolves the discover modules without a manual PYTHONPATH shadow.
- **Reconcile lint and engine run/status readers (#5).**

### Scientific state after Cycle 2
- `og-ev-competing-environments` (new, qualified): competing environments split the
  gates; vent-specificity is feature-specific, not environment-specific.
- Open synthesis this surfaced (a *good* new frontier item the engine should raise, but
  doesn't yet): the chemistry↔compartmentation environment tension → model a
  transitional/coupled scenario (vent-freshwater mixing zone or freshening excursion).
