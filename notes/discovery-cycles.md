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

---

## Cycle 3 — 2026-10-25 (adjudicate the persistence↔autocatalysis challenge)

Run on the **engine fixed in Cycle 2's follow-up** (viva-superpowers PR #360:
*acceptance criteria track the named behavior, not the verdict sign*). That fix moved
the frontier: the false `og-vent-specificity` item is gone (`unaddressed criteria
1 → 0`), and the crank advanced to the real next priority.

### Crank state (before)
`closure: OPEN` — unaddressed criteria **0**, open gaps 9, open challenges 3, frontier 34.
**Next action:** `[synthesize] open_challenge on claim:og-autocatalysis-a2` (priority 80)
— edge `claim:og-network-persistence --refutes--> claim:og-autocatalysis-a2` unadjudicated.

### Action taken (the synthesize)
Adjudicated the challenge. The two claims are **concordant, not conflicting**:
`og-network-persistence` (supported) — the carbon-fixing network persists under
*external drive* (vent feed + washout), explicitly "driven, not autocatalytic
self-amplification"; `og-autocatalysis-a2` (refuted) — endogenous self-amplifying
autocatalysis fails on both representable routes. Together they state one coherent
claim: **the prebiotic network is a driven dissipative system, not a self-amplifying
one.** Refuting autocatalysis does not threaten persistence; persistence does not
require autocatalysis. The challenge resolves as a *joint justification*, not a defeat.
Recorded as a finding `ogaa2-adjudicate-persistence-challenge` on og-autocatalysis-a2.

### Crank state (after)
**Unchanged** — still `[synthesize] open_challenge on claim:og-autocatalysis-a2`,
frontier 34. The adjudication did not close the item.

### Observation (the systemic pattern, now confirmed)
`frontier()` raises an `open_challenge` for **every** argument edge of `type ==
"challenge"` and checks **no adjudication state** — so the `synthesize` op it
recommends has no way to discharge the item, exactly as `branch` could not discharge
an acceptance criterion before PR #360. This is the **same loop-not-closed defect,
systemic across op kinds**: the knowledge-clock transition I_{n+1}=T(aₙ,Iₙ,δₙ) ignores
the action aₙ for `synthesize` and `narrative_gap` just as it did for `branch`. PR #360
closed it for one kind (acceptance ← behavior outcome); the others remain.

### Opportunity to improve discovery (next PR candidate)
**A uniform "resolution" representation, generalizing PR #360 to every op kind.** Each
frontier item kind needs a discharged-state the frontier checks:
- `open_challenge` → **adjudicated**: an authored justification/synthesis edge (or a
  `resolved: true` flag on the challenge edge, or re-typing `refutes`→`qualifies`/
  `concordant` once adjudicated) that `frontier()` consults before raising the item.
- `narrative_gap` → **bridged**: a completed bridging study (a `tests`/`builds-on`
  child closing the gap) marks the gap addressed — the child→parent *discharge* edge
  this log first flagged in Cycle 2.
The crank already recommends `branch`/`synthesize`; it must recognize the artifact each
op produces. Until then, a human re-reads the frontier each cycle and the closure count
understates real progress.

### Scientific state after Cycle 3
- og-autocatalysis-a2 carries the adjudication: persistence (driven) and the autocatalysis
  refutation are concordant — one coherent "driven dissipative network" claim.
- The three `open_challenge`s (og-autocatalysis-a2, og-self-maintaining-concentrated,
  og-vent-specificity) are all real adjudication work the engine can't yet close; the
  next engine PR (uniform resolution) is the highest-leverage discovery improvement.

---

## Cycle 4 — 2026-10-25 (adjudicate the individual→concentrated self-maintenance test)

Run on **both engine fixes now merged to viva-superpowers main**: #360
(acceptance ← behavior) and #361 (uniform resolution + the `discover resolve` verb).
The Cycle-3 resolution persists, so the crank opened at open challenges **2**.

### Crank state (before)
`closure: OPEN` — unaddressed 0, open gaps 9, open challenges **2**, frontier 33.
**Next:** `[synthesize] open_challenge on claim:og-self-maintaining-concentrated`
— edge `og-self-maintaining-individual --tests--> og-self-maintaining-concentrated`.

### Action (synthesize + resolve)
Adjudicated: **concordant, not a defeat.** og-self-maintaining-individual (refuted) —
the loop stays 4–7 orders below CAC at defensible vent conditions; og-self-maintaining-
concentrated (qualified) **reproduces** that base shortfall (9.46e-8) and maps *where*
it closes (near-maximal trap, low salinity). The concentrated study inherits and
**quantifies** the refutation into a conditional bound, it does not overturn it — the
`tests` edge is satisfied. Recorded as finding `ogsmc-adjudicate-individual-test` and
discharged with `discover resolve open_challenge claim:og-self-maintaining-concentrated`.

### Crank state (after) — the loop now closes
**open challenges 2 → 1, frontier 33 → 32.** The item dropped and the crank advanced to
the last challenge (`og-vent-specificity`, `og-vent-environment --alternative-to-->`).
First cycle where the recommended `synthesize` op actually moved the frontier — the
uniform-resolution mechanism (#361) closed the loop that Cycles 2–3 proved was open.

### Observation
The engine now advances monotonically: each adjudication/resolution drops its item and
surfaces the next. Progress that Cycles 2–3 made but the engine couldn't *see* is now
visible in the closure count. Remaining: 1 open challenge + 9 narrative gaps (the
`narrative_gap → bridged` discharge is the next natural use of the same `resolve`
mechanism, with a bridging study as the `by` artifact).

---

## Cycle 5 — 2026-10-25 (adjudicate the last challenge; all challenges now closed)

### Crank (before): open challenges **1**, frontier 32. Next: `[synthesize]` the
`og-vent-environment --alternative-to--> og-vent-specificity` edge.

### Action: adjudicated **complementary, not competing** — og-vent-environment (viable
feed, supported) + og-vent-specificity (gates discriminate the vent, behavior passed)
are jointly bounded by og-ev-competing-environments (Cycle 2: the gates *split* —
chemistry favors the vent, compartmentation favors low-salinity freshwater). The vent is
a viable, chemically-discriminating feed environment but not the unique environment
across all gates → specificity is **feature-specific, not environment-specific**.
Recorded as finding `ogvs-adjudicate-environment-alternative`; discharged via `resolve`.

### Crank (after): **open challenges 1 → 0, frontier 32 → 31.** All three argument-level
challenges (Cycles 3–5) are adjudicated and closed. closure now: unaddressed 0,
challenges 0, **open gaps 9** — the frontier is entirely `narrative_gap`s.

### Milestone + what's left
The criterion/verdict axis and the challenge axis are fully discharged. The remaining 9
`narrative_gap`s are "unsupported transition" items in the reading (op: `branch`). Unlike
an adjudication (a finding + a resolution), a narrative gap is discharged by *supplying
the missing link* — either authoring an epistemic edge between existing studies
(`discover connect`/`relate`, cheap) or a genuine bridging study (`branch`, heavy, like
Cycle 2). Cycle 6+ should triage each gap into those two classes before acting.

---

## Cycle 6 — 2026-10-25 (triage the narrative gaps → they are detector artifacts)

### Crank (before): open challenges 0, **open gaps 9**, frontier 31. Next:
`[branch] narrative_gap on claim:mem-m4-growth-division-propensity`.

### Action: triage, not branch.
Listed all 9 gaps and read `narrate`/`audit` (`viva_superpowers/narrative.py`). The gaps
are "Unsupported transition: A → B" between **adjacent units in a topological
linearization** of the claim DAG (`narrate` toposorts over *supporting* edges, ties by
id; `audit` flags every consecutive pair `zip(units, units[1:])` with no supporting
path). Two defects make these mostly **false positives**, not missing science:

1. **Topo-adjacency ≠ asserted inference.** A total order places unrelated claims next
   to each other (e.g. `og-ecology → og-energetics`, `og-heredity → og-operating-window`,
   `og-operating-window → og-reproduction`). Flagging each consecutive step as a claimed
   transition treats the linearization as a chain of inferences, which it is not.
2. **Support set excludes challenge/test edges.** `audit`'s `_SUPPORTING` set omits
   `challenge`/`tests` edges, so a genuinely-related, *already-adjudicated* pair is still
   flagged — e.g. `og-self-maintaining-concentrated → og-self-maintaining-individual`
   (Cycle 4's adjudicated test edge) and `og-precursor-pool → og-spatial-concentration`.

Branching 9 bridging studies to "close" these would **fabricate links that do not
belong**. The honest action is an engine fix, not new studies.

### Crank (after): unchanged by design — I did not fabricate. closure stays open gaps 9.

### Observation + next engine PR (the third loop-closing fix)
A third false-frontier class (after the null-control criterion in Cycle 2 and the
loop-not-closed in Cycles 2–3): **the narrative-gap detector over-reports.** `audit`
should flag a gap only where a transition is genuinely *asserted* and unsupported —
restrict to pairs where `u2` declares a prerequisite on `u1` (any relation) that lacks
support, and count an adjudicated `challenge`/`tests` edge as narrative continuity — not
every topo-consecutive pair. That turns 9 artifacts into the (few) real gaps, which then
discharge via `branch` + `resolve` like Cycles 2–5. This is the highest-leverage next
discovery improvement; until it lands, the 9 `narrative_gap`s are known artifacts, not
pending work.

---

## Cycle 7 — 2026-10-25 (fix the gap detector → investigation reaches CLOSED)

Implemented the Cycle-6 fix as viva-superpowers **PR #362**: `narrative.audit()` now
flags a gap only when a **declared edge** asserts the transition and it is neither a
supporting path nor a challenge — independent-adjacency artifacts and challenge
double-counts no longer raise gaps.

### Crank (after the fix): **closure CLOSED.**
`unaddressed criteria 0 · open gaps 9 → 0 · open challenges 0.` The investigation's
argument is settled: every acceptance criterion met (by behavior), all three challenges
adjudicated (Cycles 3–5), and no unsupported transitions remain.

### What's left is the `steer` class, not gaps
The frontier (22) is now entirely forward-looking, expert-input items the crank hands
back to a human — **8 `open_decision`s** (steer), 13 `divergence`s, 1 `open_question`:
- Publication scope (close the first paper at the pre-genetic arc?)
- Reaction-universe rule-set scope (C1–C3 C/H/O-only, or fold in N/P?)
- Unified-world architecture (single persistent-world composite?)
- MARHYS 4.0 + Hadean-ocean prior (og-vent-environment)
- Ocean-floor H2 / organic prior (og-independence)
- Agent motion model + dicarboxylate membrane permeability (og-ecology)
- Heredity attachment thresholds (og-heredity)

These require the investigator's decision (the `steer` op is "the expert decides"), not
an adjudication or a bridging study — so this is the natural hand-back point of the
crank. Discovery engine after 6 cycles: 3 false-frontier classes found and fixed
(#360 null-control criterion, #361 loop-not-closed, #362 narrative-gap over-reporting);
the crank now advances monotonically to a true CLOSED and surfaces only real steer work.
