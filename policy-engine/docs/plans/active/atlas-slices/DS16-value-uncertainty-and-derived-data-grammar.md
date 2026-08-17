---
title: DS16 — Value, Uncertainty & Derived-Data Grammar — slice task plan
status: ACTIVE — not started
slice: DS16
owner: team-design
branch: codex/atlas-ds16-value-grammar
worktree: .worktrees/atlas-ds16
base: 88210076e3e866635f9e4bf0b2344c15d51abe9b
created: 2026-08-17
master_plan: docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
laws: [1, 3, 4, 5]
authoritative_for: [ds16_cut_lines, ds16_cluster_sequence, ds16_negatives]
may_not_use_for: [capability_claim, closure_evidence, ledger_update]
---

# DS16 — task plan

## 1. Why this slice can run now, and what it is independent of

**Gate: `DS4` (closed, merged `7f450eb7b`) + value/uncertainty parts live at `GY-N10` merge
(`7e035a426`, activation satisfied).** Both are genuinely closed, not closed-by-label.

Verified independent of the three lanes in flight:

| lane | collision |
|---|---|
| `DS5` enforcement waist | 0 files — does not touch either DS16 panel |
| `DS6` evidence workflow | 0 files — owns `apps/runtime-dashboard/src/shared/i18n/**` exclusively |
| `GY-DEFC-8` (N11 closure) | different programme; touches no `apps/**` path |

**Not dependent on `GY-N11`.** Measured: the dashboard has **zero** imports of `confidence_ledger`.
DS16's value grammar consumes `ValueOuterSet` and advisor receipts, which are N10-era artifacts.
This matters because `DS17` and `DS18` *are* behind N11/N12 and DS16 is often grouped with them.

**Substrate measured present, both halves:**
- value: `src/polisyos/core/contracts/value_outer_set.py`; `ValueOuterSet` in
  `architecture/policy_design_case/layer3_gy_value_gate_contract.json`;
- derived: `src/polisyos/runtime/quality/derived_observations.py`;
  `derivation_certificate` / `provenance_class` already present in
  `schemas/runtime_api_v1.openapi.json` and `core/contracts/policy_design_case_projection.py`.
  `GY-N13a`/`GY-N13b` are recorded executed, so the derived half is not gate-blocked —
  **but confirm the certificate shape before consuming it; do not infer it from a name.**

## 2. The finding that shapes the whole slice — read before planning any cluster

The two DS16-owned panels are **11-line stubs**:

```tsx
export function PublicSectorReadinessPanel() {
  const { t } = useI18n();
  return <section data-testid="public-sector-readiness-panel">{t("common.unavailable")}</section>;
}
```

`DS4-C23` stripped them because they were **minting** authority the runtime never produced —
`PublicSectorReadinessPanel` composed readiness from local thresholds/regexes/dwell-state/disputes,
`ScientificDepthPanel` invented remedies, acquisition refs, E-values, claim extinction, cohort
timelines and stress rankings (`P15`/`P05`).

**`readinessScientificContainment.test.ts` (471 lines) does not merely check the stub — it proves
CONSTANT emission by AST.** For each panel it requires: the exact sanctioned unavailable return,
`unavailableCalls === 1`, `i18nBindings === 1`, and **`expressions === 0`, `text === 0`,
`components === 0`, `spreads === 0`, `calls === 0`**; the function declaration must take **zero
parameters** and every production mount must carry **zero props** (exactly 3 mounts: readiness ×2,
scientific ×1).

**Consequence, and it is the crux of this slice:** there is no way to wire a producer value into
these panels without changing that gate. `calls === 0` forbids a hook; `parameters === 0` forbids
props; `components === 0` forbids a child that would fetch. **The containment gate is not an
obstacle to route around — it is the specification of what its successor must preserve.**

`DS4-C23` proved *"this panel cannot emit anything."* DS16 must prove *"this panel cannot emit
anything it did not receive."* That is strictly harder, and it is the slice's real deliverable.
The master plan's closure signal — "the DS4 containment negatives stay green afterwards" — is
therefore read as **the property stays proven**, not as *the witness file stays byte-identical*.
Preserving the witness while the property weakens is `P33` (probe-as-spec); the successor gate is
written first, red-first, and the old witness retires through the disposition register in the same
change (`P28` — strangle, do not fork).

**Disposition register state, measured:** 4 rows, `disposition: rebind_pending`, owner `team-design`,
successor `c23-readiness-scientific-containment`, `consumer_refs` = the two panels + the containment
test. Closing DS16 means moving those rows, not adding new ones beside them.

**The producer does not exist.** Zero files in `src/` or `schemas/` match
`public_sector_readiness|scientific_depth|readiness_composition`. Per the Execution Doctrine, *"if
the missing link is a producer or bridge, building it is this slice's work"* — so the full chain
(producer → artifact → OpenAPI → client regen → consumer → verification → MACHINE twin) is in scope.

## 3. Cut-lines and ownership (anti-`P13`, constitution Rule 10)

**This slice writes:**
- `apps/runtime-dashboard/src/features/runs/components/{PublicSectorReadinessPanel,ScientificDepthPanel}.tsx`
  and their tests;
- the successor gate replacing `readinessScientificContainment.test.ts`;
- the value/uncertainty viz family and basis-chip components it introduces;
- the runtime producer for readiness composition and scientific-depth values;
- `schemas/runtime_api_v1.openapi.json` regeneration and `packages/runtime-api-client`;
- its own rows in the disposition register and the surface readiness ledger.

**This slice does NOT write:** `apps/runtime-dashboard/src/shared/i18n/**` (DS6's exclusive
territory); the DS5 register/baseline-manifest/status-inventory/checker set; any GY artifact under
`architecture/policy_design_case/**`; grammar, registries, ledgers or mappings owned by DS0/DS3/DS4/DS5
— those are **referenced**, never re-derived.

**Vocabulary is referenced, not invented.** `unknown`, `incomparable`, provenance classes
(`observed`/`derived`/`deployment_update`) and the status grammar come from DS0/DS4. If a needed term
does not exist, that is a finding routed to its owner, not a local definition.

## 4. Cluster sequence

Clusters are separately landable. `C01`–`C06` are the authority repair and are the priority;
`C07`–`C10` are the grammar body; `C11`–`C12` close.

### C01 — Negatives first, red-first, before any producer byte

Per the doctrine, positive work may not start with negatives unwritten. Write and prove RED:

1. a set-valued value rendered as a point estimate fails visual regression;
2. a derived series rendered without its provenance class fails the semantic test;
3. a class-(iv) model output styled as observed data fails (data-plane `P15`);
4. **the successor authority negative** — a panel that emits a value the producer did not supply
   fails, *by construction and not by inspection*;
5. `unknown` rendered as zero, or as a gap, fails;
6. `incomparable` rendered as a ranking fails.

Each carries its register ID. Each must be observed RED before its fix exists.

#### C01 outcome (executed 2026-08-17)

All six written and **all six proven non-vacuous** — each observed RED against a deliberately
violating fixture and green when the fixture is corrected. Files:
`src/test/contracts/quantityDecisionProducerHarness.tsx` (fixtures, extending the existing harness
rather than forking a registry), `src/shared/ui/quantity/ds16ValueGrammarNegatives.test.tsx`
(negatives 1/2/3/5/6), `src/features/runs/components/ds16SuccessorAuthority.test.ts` (negative 4).
`readinessScientificContainment.test.ts` is untouched and still green.

**`class-(iv)` is RESOLVED to an existing defined term — no local coining, no stop.** It is the
**fourth** member of `ObservationProvenanceClass` in
`src/polisyos/data_forge/domains/catalog/knowledge/overlay.py:84-90`, whose full denominator is
exactly four: (i) `observed`, (ii) `proxy`, (iii) `derived`, (iv) `model_output`. Corroborated by
`acquisition_executor.py:1719` returning `("model_output_not_observation",)` and by
`layer3_gy_n13b_acquisition_contract.py:1051-1052` asserting that code under the message
*"class-(iv) output must fail observation admission closed"*.

**Finding routed to the master-plan owner — the C10 provenance triple is wrong.** The master plan
(and §3 above) name the provenance classes as `observed` / `derived` / `deployment_update`. Measured
against both full enums, that sentence **conflates two different vocabularies**: `observed` and
`derived` are `ObservationProvenanceClass` members, but `deployment_update` is not a provenance class
at all — it is a `BranchMode` member (`world_model_record.py:66-71`; `observed` | `scenario` |
`deployment_update`), i.e. world-*branch* semantics. The shared `observed` member is the likely seam
of the conflation. The triple also silently **drops `proxy` and `model_output`**, and `model_output`
is precisely the class negative 3 exists to police. **C10 must mark against the four-member
`ObservationProvenanceClass`, not the stated triple**; whether a branch mode is *also* surfaced is a
separate question with a separate owner.

**Two lane divergences from this plan's §5, reported on re-measured numbers:**

- Negative 1 was assigned to the visual-regression lane. It runs in the **Vitest component lane**
  instead, because a screenshot diff carries no semantics — a PNG cannot assert that a set was
  collapsed to a point, only that pixels changed. The property is observable exactly where the seam
  lives: `chartQuantityScalarPoint` and `data-chart-quantity-cardinality`. Note also that
  `visualRegressionHarness.test.ts` is itself a **Vitest** AST/asset auditor, not a Playwright spec.
- `test:contracts` runs **only** `src/test/contracts/contractFixtures.test.ts`, not the contracts
  directory; the harness and its consumers run under `test:components`.

**Measured durations (this slice's own samples, replacing the supplied `DS-INFRA-2` ceilings):**
production build `18.504` s against the supplied `47.29` s; blast-radius suite (8 files, 38 tests)
`5.032` s; typecheck `16.781` s; a11y components (84 files, 85 tests) green; full component suite as
recorded in the C01 commit trail.

### C02 — The successor containment gate (the crux; do this before touching the panels)

Replace "proves constant unavailable emission" with a gate that proves **no locally minted value**.
State the property, state what the implementation tests, and **name one case where they diverge**
(`P38`). Minimum strength, and it must be argued rather than assumed:

- every value the panel renders is traceable to a producer field or a typed refusal;
- the panel cannot compute a value from thresholds, regexes, dwell state, or any local arithmetic —
  the exact classes `DS4-C23` found;
- absence of a producer field renders a **typed refusal**, never a blank, a zero, or an inference;
- the gate fails when the property is removed but its markers remain (`P29`
  remove-the-property-keep-the-markers probe).

**Forbidden:** relaxing the AST gate to "allow hooks" and calling the class closed — that trades a
proof for a convention. If a purely structural successor cannot express the property, say so and
state what behavioural gate carries it instead.

### C03 — The producer contract

Define the typed contract for readiness composition and scientific-depth values. Each named value
resolves to a producer field or a **registered typed refusal**. No value exists in the contract that
the runtime cannot supply — an unsupplied value is a refusal in the contract, not an optional field
the client fills in.

Enumerate the `DS4-C23` inventory completely (readiness composition; remedies, acquisition refs,
E-values, claim extinction, cohort timelines, stress rankings) and give each one disposition:
producer-supplied, typed refusal, or **out of scope with its reason**. A value silently dropped is
the failure this slice exists to close.

### C04 — Persisted artifact + bridge

Producer → persisted artifact → OpenAPI schema → `packages/runtime-api-client` regeneration.
Generated typed client only; no hand-written types. Regeneration is part of this cluster, not a
follow-up.

### C05 — Consumers rewired

Both panels render a producer value or an honest typed refusal. The three production mounts are
updated together; the `RunDetailLayout` and `GovernanceTab` call sites are the complete consumer set
(measured — verify it has not changed).

### C06 — MACHINE twin + parity test

Ships in-slice, using DS3 export machinery, with a surface↔twin parity test. A surface without its
twin does not close.

### C07 — Set-valued value viz family

Never collapses to a point. `unknown` (missing) and `incomparable` ("no admissible ranking exists")
render as first-class designed states, distinct from each other and from zero. A tail /
worst-case-over-process value may not be shown as a cancelling average.

**Binding:** a single ranked recommendation renders **only** when a `GY-PA1`
`NormativeAuthorizationRecord` authorizes the aggregation; absent it, show the frontier plus a
`NormativeDecisionRequest`, never a silent scalarization. Confirm whether that record type exists
before designing against it; if it does not, the honest surface is the frontier and the dependency
is registered.

### C08 — Basis chips

Every monetary or unit-bearing chart carries its basis (`real, base-2020, deflator=CPI`) as a
visible, clickable element resolving to its certificate — not a caption.

### C09 — Derivation-recipe popover (derived half)

Recipe = inputs × method+params × auxiliaries. **Confirm the certificate shape against
`derived_observations.py` and the OpenAPI schema before consuming it.** Single-transform provenance
only; no transform-planner UI — the GY plan defers transform chains.

### C10 — Provenance-class marking

`observed` / `derived` / `deployment_update` wherever data is decision-bearing.

### C11 — Disposition register closure

Move the 4 `rebind_pending` rows. A successor closes only when a **real consumer exists** AND the old
owner path is **proven strangled**. Retire the old containment witness in the same change.

### C12 — Ledger + "Not yet"

Update the surface readiness ledger; state explicitly what the slice does not claim.

## 5. Verification protocol

**Contended set — serialize these, run everything else in parallel:** the Playwright
browser/visual-snapshot lane, the Storybook runner, a dev server on a fixed port, and any writer
touching the same governed `architecture/atlas_surfaces/**` artifact. ESLint, typecheck, Vitest logic
files, the production build, dependency-cruiser and read-only censuses run in parallel.

**Declared ceilings** (supplied from `DS-INFRA-2`, labelled as supplied because this slice has no
samples of its own; a killed run is a **non-receipt, never a duration sample**):

| lane | declared ceiling |
|---|---|
| full Atlas enforcement module | `754.20` s |
| status-retirement module | `135.663` s |
| disposition corruption battery | `119.66` s |
| production build | `47.29` s |
| focused dashboard behavior | `14.417` s |

Measure this slice's own suites once and record them; a ceiling is enlarged **before** a run and
never mid-run to make a run fit.

**Gating:** absolute green for typecheck, production build, and every test this slice owns or
touches; **zero-NEW-diagnostics** against the hashed baseline manifests for inherited debt classes.
Weakening or suppressing an authority-relevant rule to make a gate pass is forbidden outright.

**Economics:** freeze the source, review, then run the expensive wave **once**. After the freeze a
cosmetic finding is recorded as debt; a blocking one is batched. Re-reviews read the **fix delta
only**, with the original findings as the checklist — use
`tools/quality/testing/build_review_package.py`, which now states its own exclusions.

**Two-fix breaker (repaired predicate):** a round consumes the breaker when triggered by evidence
that the mechanism is wrong — a failing behavioural test, an independent review finding, or a
governed RED. A round triggered solely by a non-behavioural static diagnostic does not consume it,
provided it changes no test outcome and no governed artifact byte **and that is proven**.

## 6. Work preservation

Commit at every clean boundary — uncommitted work is not storage, and a stash is a transient for
minutes. History is append-only: no rebase, reset onto an ancestor, force-push, or stash drop.
**Verify branch attachment with `git status -sb` before every commit** — a detached worktree looks
normal to `git log -1` and `git status --short`, and a commit made there is orphaned. Unexpected
history is an architect stop, never a self-repair.

## 7. Not yet (mandatory; restate at closure)

- No transform-planner UI; single-transform provenance only.
- No claim that readiness or scientific-depth **capability** exists — this slice binds a producer to
  a surface; it does not establish the underlying analysis.
- No `DS17` δ-surfaces and no `DS18` epoch chrome — both sit behind `GY-N11`/`GY-N12`, and `N11`'s
  cold closeout is **not** established.
- No re-derivation of status grammar, audience mapping, or the disposition register's own rules.

## 8. Done when

Every named `DS4-C23` value resolves to a generated field or a registered typed refusal; the
successor gate proves no locally minted value **and fails when that property is removed with its
markers intact**; the three mounts render producer values or typed refusals; the MACHINE twin ships
with its parity test; the 4 disposition rows are closed with the old witness retired; the readiness
ledger is updated; and the "Not yet" list above is restated in the ledger.
