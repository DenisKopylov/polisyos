---
title: DS16 — Value, Uncertainty & Derived-Data Grammar — slice task plan
status: CLOSED blocked_on_ds5 (2026-08-18) — authority repair delivered; grammar body deferred to a successor
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
- derived: `src/polisyos/runtime/quality/derived_observations.py` — **CORRECTED by C08/C09/C10
  (2026-08-17), the original claim here was wrong.** `derivation_certificate` has **0 occurrences**
  in `schemas/runtime_api_v1.openapi.json`; the type exists only in Python. The served
  `provenance_class` on `core/contracts/policy_design_case_projection.py` is
  `ParticipationProvenanceClass` (ADR-0167), a **different vocabulary with a different owner**, not
  the `ObservationProvenanceClass` DS16 needs — which is served nowhere. `GY-N13a`/`GY-N13b` being
  executed does not make the derived half *served*: the substrate is real and exercised, the bridge
  is absent. See the C08/C09/C10 outcome section.

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

#### C02 outcome (executed 2026-08-17)

Gate: `src/features/runs/components/ds16SuccessorContainment.test.ts`, over the **real** panel files.
C01's analyzer moved verbatim to `src/test/contracts/successorAuthorityAnalyzer.ts` so both C01's
negative and C02's gate consume one function (`P27`); C01's six expectations are unchanged and still
green, which is what proves the move was behaviour-preserving.

**The vacuity trap is answered, not commented on.** Both panels are stubs, so the property holds
trivially. The gate therefore *asserts* `panelEmissionMode === "contained"` for both, putting the
reason on the record where it cannot drift; C05 flipping a panel to `bound` must update that
assertion deliberately. Beyond that, the whole gate was verified by **corrupting the real
`PublicSectorReadinessPanel.tsx` and the real `RunDetailLayout.tsx` mount site on disk** — 4 of 9
tests went RED including the cross-file census, and both files were restored byte-identical.

**Gap 1 — mount graph: carried forward and strengthened.** Re-measured rather than inherited:
**3** production mounts — `RunDetailLayout.tsx` readiness ×1 + scientific ×1, `GovernanceTab.tsx`
readiness ×1 — all propless. The ancestor's "zero mount props" is generalized to **no *minted* mount
props**, since C05 may legitimately pass a producer value but may never compute one at the mount
site. **Reachability, not filename, is what excludes the test harness:**
`quantityDecisionProducerHarness.tsx` also mounts the readiness panel and is *not* a `*.test.tsx`
file, so a census filtering on filename alone reports four mounts and is wrong.

**Gap 2 — the label-channel ruling (`P38`).** The answer is **both halves, and they are not
symmetric**:

- **Key *selection* is structurally closed.** A key can only be chosen by a construct the gate
  already refuses — a conditional, a template literal, a non-literal argument, a threshold, or
  control flow. Verified with four violating shapes, each RED, rather than assumed.
- **Key *identity* is a bounded, declared limitation.** No AST analysis can separate
  `t("readiness.high")` (minting a verdict) from `t("readiness.sectionTitle")` (labelling a section):
  the difference is the key's *meaning*, which lives in the i18n catalog — DS6's exclusive territory,
  which DS16 may neither write nor treat as authority. Claiming this channel closed would be a proxy
  gate.
- **Mitigation, so the limitation is watched rather than merely declared:** the gate pins each
  panel's exact rendered-key inventory (`["common.unavailable"]` for both today). A value-bearing key
  cannot enter without editing the gate, which converts an invisible minting channel into a
  reviewable diff.
- **The one case where property and implementation diverge:** a reviewer who *approves*
  `readiness.high` in that diff. The structural gate then passes while the property is violated.
  **Carrier:** C05's behavioural assertion — a bound panel rendered with a producer supplying no
  readiness must render the typed refusal, which a panel hardcoding a verdict fails at runtime
  whatever its AST says.

**Typed refusal — structural reach and its limit.** The gate enforces that a `contained` panel
renders the sanctioned refusal `common.unavailable` (referenced from the ancestor, not coined) and
that no panel renders a blank, a `null`, an empty expression, or a `0` in a value slot. Whether a
**bound** panel refuses when a producer field is null *at runtime* is not a property of source text;
that half is behavioural and is C05's, recorded here rather than left implied.

**The ancestor stays.** `readinessScientificContainment.test.ts` is untouched and green. It asserts
`calls === 0`, so it goes RED the moment C05 wires a hook — it retires in that same change (C11),
not before. Until then the two gates coexist deliberately. The mount-graph walk is knowingly
duplicated because the ancestor exports none of its internals and may not be edited; that
duplication ends at the ancestor's retirement (`P28`).

**Measured:** typecheck `14.675` s · blast radius 9 files / 47 tests / `5.089` s · lint, quantity
coverage clean.

### C03 — The producer contract

Define the typed contract for readiness composition and scientific-depth values. Each named value
resolves to a producer field or a **registered typed refusal**. No value exists in the contract that
the runtime cannot supply — an unsupplied value is a refusal in the contract, not an optional field
the client fills in.

Enumerate the `DS4-C23` inventory completely (readiness composition; remedies, acquisition refs,
E-values, claim extinction, cohort timelines, stress rankings) and give each one disposition:
producer-supplied, typed refusal, or **out of scope with its reason**. A value silently dropped is
the failure this slice exists to close.

#### C03/C04 outcome (executed 2026-08-17)

**MERGE HOLD — this branch does not merge until the GY cold closeout is banked.** Any `.py` added
under the source root moves the `E12` deployment identity (`_deployment_relative_paths` globs
`source_root.rglob("*.py")`), re-pricing the three deployment-bound GY artifacts, and
`codex/gy-defc-3-retry` is spending its single authorized cold `N11` right now. Nothing here touches
a GY artifact and no GY validator runs on this branch — the *merge* is sequenced, not the work.

**The inventory is ELEVEN value families, not seven.** Re-derived from the deleted modules at
`bc1d01001` rather than from the record's prose. The summary sentence "readiness composition"
collapses **six** distinct readiness builders into one phrase; the scientific side matches.

| # | member | disposition | reason (a property of the value) |
|---|---|---|---|
| 1 | `readiness.composite_verdict` | typed refusal · `no_runtime_composition_rule` | No governed artifact defines how a verdict is composed. Inputs are served by their own owners; the composition rule does not exist, and composing one on the surface is the C23 sin. |
| 2 | `readiness.lens_projection` | typed refusal · `owned_by_another_surface` | Stakeholder lens is audience mapping, owned by DS0/DS3; DS16 references and may not re-derive it. |
| 3 | `readiness.fairness_audit` | typed refusal · `analysis_not_runtime_resident` | Resident in offline `scientist`/`foundry` (29 files); **0** in `runtime/http`. |
| 4 | `readiness.harm_assessment` | typed refusal · `analysis_not_runtime_resident` | Resident in offline `scientist`/`foundry` (23 files); **0** in `runtime/http`. |
| 5 | `readiness.embargo_overlay` | typed refusal · `no_runtime_producer` | **0** occurrences repo-wide under any name. |
| 6 | `readiness.slow_review` | typed refusal · `no_runtime_producer` | Derived from browser dwell state in local storage; interaction state never became a runtime value. |
| 7 | `readiness.revocation_ledger` | typed refusal · `no_runtime_producer` | The one `revocation` token in the served schema is a **step-up auth class** on a reissue endpoint — an unrelated concept. |
| 8 | `scientific.identifiability_remedy` | typed refusal · `no_runtime_estimator` | Identifiability *state* is served; the **remedy** and its acquisition ref need an acquisition planner that does not exist. |
| 9 | `scientific.sensitivity_e_value` | typed refusal · `no_runtime_estimator` | **0** E-value estimator anywhere in `src/`; claim extinction derives from it. |
| 10 | `scientific.cohort_timeline` | typed refusal · `analysis_not_runtime_resident` | Cohort transition analysis is offline and not served per run. |
| 11 | `scientific.stress_ranking` | typed refusal · `no_runtime_producer` | **0** stress-scene producer; the retired ranking ordered scenes the surface invented. |

**Not a member, recorded for completeness:** `identifiability` itself. DS4-C23's own wording is that
`ScientificDepth` "binds generated identifiability correctly", and it is served today on
`QuantityUncertainty` and `DecisionPacketEffectSize` (17 schema hits). It was consumed honestly and
was never minted.

**Why every disposition is a refusal, and why that is the honest answer.** No member has a runtime
producer. The contract therefore defines **no** value field the runtime would populate with `null` —
that shape is `contract_only` by construction. Each member is a served `RefusedAuthorityValue`
carrying its reason and, where one exists, the owning surface. Completeness is **enforced** by
`RunAuthorityProjection`'s validator, not documented: dropping or duplicating a member raises, and
the test proves it by dropping one. A `SuppliedAuthorityValue` variant exists so a value can graduate
without a contract change.

**What C05 gets.** A discriminated `state` — a distinguishable "no value" that is not an absent key.
An optional field is how "unavailable" silently becomes "zero" one slice later.

**Bridge:** `GET /api/v1/runs/{run_id}/authority-values` → `schemas/runtime_api_v1.openapi.json` →
`packages/runtime-api-client`. Schema and client diffs are **purely additive** (one path, one
operation, five component schemas, 0 deletions), so replaying the regeneration after another lane
lands the schema is cheap and conflict-free. The contract check first failed with *missing success
response example*; fixed **upstream** in the operation example registry, never patched downstream.

**Findings.**
- `apps/runtime-dashboard/src/api/types.ts` is **stale on `main`** — regenerating it from `main`'s own
  schema changes 1504 lines, before any DS16 edit. It has 25 importers (the package client has 74).
  Repairing it is not this slice's scope and would bury an additive change under someone else's
  drift, so it was reverted and is registered here instead.
- `openapi_contract.py` was already not `ruff format` clean on `main`; running the repo's formatter on
  the file this cluster edits normalized 3 incidental pre-existing lines.
- `defusedxml` is imported directly by `fabric/connectors/sources/eurostat.py` but declared by no
  extra; the runtime-http test barrel needs `--extra test` to import at all.

**Verification.** Guardrail deep-import set **byte-identical** to the pre-edit baseline (5 before, 5
after, none in the new module). Runtime contract check passes. 8 new Python tests green (`7.836` s).
Four `runs_api`/`architecture_boundaries` failures were confirmed **inherited** by running them in a
throwaway worktree at `88210076e`, where they fail identically. Frontend: typecheck `12.434` s,
lint, quantity coverage clean; full suite 910 passed / 3 failed, the failing set identical to the C02
baseline. C02's gate still reports both panels `contained`; panels, mount sites and the ancestor are
byte-identical to `main`.

### C04 — Persisted artifact + bridge

Producer → persisted artifact → OpenAPI schema → `packages/runtime-api-client` regeneration.
Generated typed client only; no hand-written types. Regeneration is part of this cluster, not a
follow-up.

### C05 — Consumers rewired

Both panels render a producer value or an honest typed refusal. The three production mounts are
updated together; the `RunDetailLayout` and `GovernanceTab` call sites are the complete consumer set
(measured — verify it has not changed).

#### C05/C06 outcome (executed 2026-08-17)

**MERGE HOLD STANDS — unchanged by this cluster.** `codex/gy-defc-3-retry` is still spending its
single authorized cold `N11`; any `.py` under the source root moves the `E12` deployment identity.
Do not merge this branch until that closeout is banked.

**The rendering decision: each refusal individually, never a statement over them.** A single summary
would have to *compose* eleven refusals — and a count is a composite, so even "11 values unavailable"
is the `DS4-C23` sin rebuilt one layer up. Each member renders its own `value_id`, `refusal_code`,
`reason` and `owner_surface`, and nothing is aggregated. A test asserts the glass carries no count,
share or percentage, and the twin asserts the same for machines.

**What a reader now learns that `common.unavailable` could not tell them:** *which* eleven values are
absent; *why each* is absent, by kind — `no_runtime_estimator` (no such computation exists anywhere)
is a different world from `analysis_not_runtime_resident` (it exists, offline) and from
`owned_by_another_surface` (real data exists, elsewhere); and *where to go instead* for the one
member that has an owner. The stub's "Unavailable" is indistinguishable from broken, loading, or
permission-denied. That distinction is the cluster's product.

**The flip.** C02's gate asserted `panelEmissionMode === "contained"`, recording that it passed for
the vacuous reason. Both panels are now **`bound`**. The gate *refused the rewire* until
`useRunAuthorityValues` was added to the sanctioned producer set — a panel cannot reach for a new
producer without someone widening that set on purpose.

**Two analyzer refinements C05 forced, both principled rather than relaxations.** Iteration over a
producer collection is not computation, so `producerCollection.map(...)` is permitted with the
callback parameter becoming a producer root — refusing it would have pushed the loop into a helper
the gate cannot see, which is the ancestor's direct-helper corruption in a new hat. And a prop handed
to a producer read is not a computed argument. Every other rule still applies inside the callback.

**The two behavioural properties, with the REDs observed before they passed:**

| property | exact RED |
|---|---|
| typed refusal reaches the glass with its reason | `Unable to find an element with the text: No governed artifact defines how a readiness verdict is composed.` — panel rendered only `Unavailable` with an empty list |
| label-channel carrier (output follows the producer) | `Unable to find an element with the text: first producer answer` |
| surface partition | `AssertionError: expected null not to be null` |
| no summary composed | `Unable to find an element with the text: reason for readiness.composite_verdict` |

Root cause of all four: the generated client calls `fetch(url, init)` with a path-relative URL while
`authAwareRuntimeFetch` takes a `Request`, and `new Request()` cannot parse a relative URL —
`TypeError: Failed to parse URL from /api/v1/runs/r/authority-values`, isolated with a throwaway probe.

**Ancestor retirement — coverage argument, re-verified not inherited.** The successor now covers
**10 of 11** ancestor corruptions, not C02's 9: the cross-file sibling-wrapper mount is carried by
`mountGraphCensus`, which C02 built and proves. The single uncovered case remains the arbitrary
i18n key, **intentionally** permitted because a label is not a value. No third gap appeared, so the
retirement proceeded. The witness was deleted in the same commit that rewired the panels (`P28`), and
a strangle proof asserts nothing still *loads* it — testing for reaching, not for mentioning, since
the successor's prose names its ancestor deliberately.

**Contract addition.** C05 added a server-supplied `surface` partition (`readiness` | `scientific`)
so no consumer parses a value id to decide what belongs to it; deriving that client-side would be a
local routing decision over authority data. Bridge replayed: schema, client and contract check green.

**Twin.** `policyos.atlas.ds16.authority_values.twin.v1` — member-for-member, no aggregate, parity
read off the **rendered DOM** rather than off the shared model, with a failing mutation for each
property (dropped member, invented member, reordering into a ranking, softened code, softened reason).

**Finding — the DS3 governed-projections machinery was NOT used, deliberately.** It requires an
`owner_validator_id` and an isolated owner-validation worker, and is built for governed artifact
files under `architecture/policy_design_case/**`. This contract is runtime-computed, so registering
it there would have meant inventing an owner validator to satisfy a shape. The twin instead meets the
master plan's stated requirement directly — typed JSON export, replayable packet, stable URL
(`GET /api/v1/runs/{run_id}/authority-values`) — with the parity test in-slice.

**Verification.** typecheck green · lint exit 0 · quantity coverage exit 0 · a11y 84 files / 85 tests
`28.086` s · full component suite **919 passed / 3 failed**, failing set byte-identical to the C04
baseline (DS6's inherited ICU-plural rows) · guardrails **byte-identical to the pre-C03 baseline**
(5 before, 5 after) · runtime contract check green · ruff clean · 8 Python contract tests green.
`testing-library/no-container` was satisfied by moving to Testing Library queries, not suppressed.

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

#### C07 outcome (executed 2026-08-17)

**MERGE HOLD STANDS.** `codex/gy-defc-3-retry` is still spending its single authorized cold `N11`.
Do not merge this branch until that closeout is banked.

**Decision: render against what is served. Do NOT bridge `ValueOuterSet`.** This diverges from the
cluster brief, which framed the choice as a work-size tradeoff. Measured, bridging is not *larger* —
it is **unfoundable**:

- the only `ValueOuterSet` construction in the entire source tree is
  `_empty_household_value_outer_set()` (`src/polisyos/foundry/contracts/state.py:295`), an **empty
  placeholder** with `representation="unknown"`, `identification_status="blocked"` and empty
  coordinate/lower/upper tuples;
- `.compare()` — the sole producer of `incomparable` anywhere — has **zero callers**;
- `ValueOuterSet` appears in **0** served schemas, and **0 of 356** served schemas express an order
  verdict at all (`incomparable`, `dominates`, or any equivalent).

An endpoint over that would serve a placeholder: `contract_only` by construction, which is precisely
what C03 refused. So the served types genuinely cannot express `incomparable`, and the honest response
is to register the producer rather than manufacture one.

**Registered dependencies (three, all with zero occurrences, none invented here):**

| dependency | measured | owner | consumer |
|---|---|---|---|
| `NormativeAuthorizationRecord` | 0 files in `src`/`schemas`/`architecture` | `GY-PA1` | any ranked recommendation |
| `NormativeDecisionRequest` | 0 files | `GY-PA1` | the absent-authorization surface |
| run-scoped `ValueOuterSetComparison` producer | contract exists, 0 callers, 0 served | GY value-gate / foundry | `OuterSetValue` order statement |

Because the first two do not exist, **no ranking may render at all**, and the family has no ordering
code path — asserted by scanning its own source for `<ol`, `aria-posinset`, `aria-setsize`,
`data-rank`, `.sort(` and `localeCompare`.

**Two order statements, deliberately not conflated.** `incomparable` is a claim about the **values**
("no admissible ranking exists") and only a producer may make it. Order-not-authorized is a claim
about the **surface** ("nothing licenses this glass to rank"), true today for every set, and it is
DS16's own to make. `null` is the *absence* of a verdict, not a fourth member of
`ValueOuterSetComparison` — the vocabulary is referenced verbatim and never extended.

**C01's negatives now bind real components.** The compliant fixtures render `OuterSetValue` and
`OuterSetValueStateCell`; the guards are unchanged. The neutering experiment was re-run against the
real family and negatives 1, 5 and 6 all went RED on demand (`expected [] to deeply equal [ …(2) ]`,
`[ Array(1) ]`, `[ 'ordered-list-semantics', …(2) ]`), then green on restore.

**Honest limit: the family has zero production importers.** It is built, proven and a11y-clean, but no
rendered surface consumes it yet — the panels render refusals, not set-valued quantities, and mounting
the family where no set-valued decision value is served would be fabrication. Its consumers are
C08–C10.

**Snapshot decision: do NOT update any snapshot.** `run detail A4 print` still fails, and it fails on
unmodified `main` as well. Updating it would make the lane green by absorbing an inherited failure
whose cause has not been diagnosed — so a green could not mean "the new image is correct", only "I
took someone else's failure with mine". C07 itself changes **no** rendered surface (zero production
importers), so nothing in this cluster requires an update. The A4 print snapshot needs a deliberate
update *after* the inherited failure is diagnosed, by whoever owns it.

**Finding that refines the inherited-visual baseline:** `evidence promotion focus` is **flaky**, not
deterministically inherited. It failed at C06 and on `main`, and passes here (1 failed / 17 passed,
`83.6` s, versus 2 failed / 16 passed at C06).

**Measured:** typecheck green · lint 0 · quantity coverage 0 · a11y 85 files / 87 tests `72.23` s
(up from `28.086` s with the new component and its two suites) · components **925 passed / 3 failed**,
failing set identical to the C06 baseline · visual `83.6` s.

### C08 — Basis chips

Every monetary or unit-bearing chart carries its basis (`real, base-2020, deflator=CPI`) as a
visible, clickable element resolving to its certificate — not a caption.

### C09 — Derivation-recipe popover (derived half)

Recipe = inputs × method+params × auxiliaries. **Confirm the certificate shape against
`derived_observations.py` and the OpenAPI schema before consuming it.** Single-transform provenance
only; no transform-planner UI — the GY plan defers transform chains.

### C10 — Provenance-class marking

`observed` / `derived` / `deployment_update` wherever data is decision-bearing.

#### C08/C09/C10 outcome — MEASURED, NOT BUILT (2026-08-17): a terminal for the grammar body

**MERGE HOLD STANDS.** `codex/gy-defc-3-retry` is still spending its single authorized cold `N11`.

**This cluster stopped deliberately.** Two of its stop-rule conditions are met, and the overriding
question it was given — whether the grammar body is implementable in its planned scope — resolves to
**no, but not for the reason C03 and C07 resolved that way.**

**§1 of this plan contains an architect error, corrected here.** It states `derivation_certificate` is
"already present in `schemas/runtime_api_v1.openapi.json`". Measured: **0 occurrences in the entire
schema document.** The file-level grep that produced that claim matched `provenance_class` and was
attributed to the wrong token.

| cluster | gap kind | measurement |
|---|---|---|
| C08 basis chips | **bridge** (buildable) | `BasisSignature`, `BasisAttribute`, `BasisParameterBinding` live in `src/polisyos/runtime/quality/derived_observations.py` — the **runtime** tree — and the module has real callers. Served: **0**. |
| C09 derivation recipe | **bridge** (buildable) | `DerivationRecipe` (:592) and `DerivationCertificate` (:695) exist; `build_derivation_recipe` has **32 call sites**, `persist_source_series` 8, `persist_transform_family_registry` 6. Served: **0**. |
| C10 provenance marking | **name collision + absent producer** | See below. Not a type gap. |

**C08/C09 are decisively unlike C07.** `ValueOuterSet` was unfoundable — its only construction was an
empty placeholder and `.compare()` had zero callers. The derivation machinery is genuinely exercised
by five `tools/quality/validation/**` GY validators. The substrate is real; only the bridge is missing.

**C10's premise was wrong, and this is the cluster's sharpest finding.** The single served
`provenance_class` (`PolicyDesignCaseParticipationRequirementProjection`, typed bare `string`,
`minLength: 1`) does **not** carry DS16's concept. It carries `ParticipationProvenanceClass` — ADR-0167
participation grades `A_representative_population` / `B_structured_deliberative_or_process` /
`C_attributable_nonrepresentative` / `D_unverifiable_or_speculative` — owned by
`src/polisyos/participation_requirement/`. DS16's concept is `ObservationProvenanceClass`
(`observed` / `proxy` / `derived` / `model_output`), which is served **nowhere**: `observation_class`
**0**, `model_output` **0**, `proxy` **0**, `derived` **0**.

Same token, two unrelated vocabularies, two owners. **Narrowing the served field would (a) move a
producer DS16 does not own and (b) narrow the wrong concept entirely** — the C10 stop-rule condition,
met exactly. Not narrowed; registered instead.

**Why the grammar body has no mount point, which is the real terminal.** C03 established that all
eleven DS16 authority families are refusals. So both DS16-owned panels render **refusal strings and no
quantities at all** — measured, zero `Quantity` references in either panel. There is therefore
nothing unit-bearing to attach a basis chip to, nothing derived to open a recipe for, and no
decision-bearing value to mark with a provenance class. The blocker is not an absent substrate; it is
that **this slice's surfaces carry no values to decorate.**

**The C07 family found no honest mount point, for the same reason.** `OuterSetValue` remains built,
proven against C01's negatives and a11y-clean, with zero production importers. Mounting it over a
refusal string to give it a home would be the fabrication C07 explicitly refused.

**A further subtlety for whoever builds C08.** `BasisSignature.attributes` is
`tuple[BasisAttribute, ...]` of free `{name, value}` strings, and `attribute()` is documented as
returning a declared attribute *"without assigning vocabulary meaning"*. The substrate is
**deliberately vocabulary-neutral**. The plan's chip design — `real, base-2020, deflator=CPI` —
presumes a vocabulary the substrate declines to define, so an honest chip renders the owner-declared
attributes verbatim and must not interpret them.

**Registered dependencies (three, added to C07's three):**

| dependency | measured | owner | consumer |
|---|---|---|---|
| basis bridge (`BasisSignature` → schema) | substrate real, 0 served | DS16 (bridge) / GY-N13b (substrate) | C08 basis chip |
| derivation bridge (`DerivationRecipe`/`DerivationCertificate` → schema) | substrate real, 32 call sites, 0 served | DS16 (bridge) / GY-N13b | C09 recipe popover |
| run-scoped `ObservationProvenanceClass` producer + served field | 0 served under any name | `data_forge` catalog / GY-N13b | C10 marking, C01 negative 3 |

**C01's negative 3 stays fixture-bound, and that is the honest outcome.** It was to be rebound to the
real marking; no real observation-provenance marking exists to bind to, because the concept is served
nowhere. The negative remains proven non-vacuous against its fixture and is registered as blocked on
the third dependency above.

**Nothing was built and nothing was narrowed**, so no gate moved: guardrails, schema, generated client
and the served contract are untouched by this cluster.

### C11 — Disposition register closure

Move the 4 `rebind_pending` rows. A successor closes only when a **real consumer exists** AND the old
owner path is **proven strangled**. Retire the old containment witness in the same change.

#### C11/C12 outcome — STOPPED at register closure (2026-08-17)

**MERGE HOLD STANDS.** `codex/gy-defc-3-retry` is still spending its single authorized cold `N11`.

**A governed gate was RED on this branch and no cluster before C11 ran it** — an architect omission,
recorded so the next slice inherits the habit rather than the debt. Baseline taken first: `main`
exit **0**, branch exit **1** with **7** findings, all caused by this slice.

**Closed: 2 of 7 (7 → 5).** `PublicSectorReadinessPanel.tsx` and `RunDetailLayout.tsx` legitimately
changed when C05 bound the panels, so their `sha256` content bindings in the baseline debt manifest
were stale. Recomputed from the live files, two lines, no reformat. Correct rather than convenient:
the new hash *is* the hash of the file this slice deliberately changed.

**Not closed: 5 of 7, and both reasons are stops rather than remaining work.**

**(a) The four `rebound_consumer_missing` rows.** Re-pointing `consumer_refs` at what exists is the
right repair and was applied — and it immediately produced **four new**
`c23_containment_root_drift` findings, because `_validate_c23_containment_roots` pins the expected
list in the constant `C23_SUCCESSOR_REFS` (`check_frontend_disposition_register.py:1484`). The
register and the checker must move together. That checker is named in this plan's §3 exclusion list
(*the DS5 register/baseline-manifest/status-inventory/**checker** set*), and the in-flight
`codex/atlas-ds5-enforcement-waist` lane has it open, rewritten from ~1,832 to ~8,000 lines, with
the register itself at **2,374** changed lines. The re-point was therefore reverted rather than
landed against a file this slice does not own and another lane is rewriting.

Measured and worth stating: DS5's branch still carries `readinessScientificContainment.test.ts` in
both `C23_SUCCESSOR_REFS` and its register, so **DS5 is not closing these rows either** — it carries
them forward. Whoever lands second must reconcile.

**(b) The census drift, diagnosed and deliberately not patched.** A single ref moved:
`quantityDecisionProducerHarness.tsx:139` → `:148`. Same file, same symbol, byte-identical line
content (`  return buildSignedPublicDecisionPacket({`), nine lines lower because C01 inserted its
import block above it. Count unchanged, **28 → 28** — the checker reported `observation_drift` and
*not* `expected_count_drift`, which is what identified it as a coordinate move rather than a
membership change. Nothing in DS16 touches browser signing.

Bumping the number would have been correct today and **wrong after DS5 lands**: DS5 replaces
line-numbered census refs with content-addressed TypeScript identity tokens
(`...tsx#ts-identity=<base64>`), which eliminates this drift class structurally. Patching a line
number into an artifact whose owner is removing line numbers is the "update a number to make a gate
green" this slice refused three times. Reverted; registered for DS5's landing.

#### What DS16 delivered, and what it did not

**Delivered — the authority repair, end to end.** Eleven value families measured with positive
controls, every one a refusal because no runtime producer exists; a typed contract defining **no**
field the runtime would populate with `null`; producer → persisted content-addressed artifact →
OpenAPI → generated client; both panels bound with behavioural proof the refusal reaches the glass;
the containment ancestor retired in the same commit that rewired the panels, with a strangle proof;
a MACHINE twin whose parity is read from the rendered DOM.

**Not delivered — the grammar body.** `OuterSetValue` is built, proven against C01's negatives and
a11y-clean, with **zero production importers**. Recorded as *a finished component awaiting a
surface*, not as debt.

**Six registered dependencies** — three from C07 (`NormativeAuthorizationRecord`,
`NormativeDecisionRequest`, run-scoped `ValueOuterSetComparison` producer) and three from C08/C09/C10
(basis bridge, derivation bridge, run-scoped `ObservationProvenanceClass` producer + served field),
each carried with its measurement, owner and consumer in its own outcome section.

**Successor slice for the grammar body**, with a property-shaped re-entry condition:
**a surface exists that renders values rather than refusals.** By the master plan's DAG that arrives
with **DS7 Cycle Board on real capstone data**; DS7 gates on DS5, which is in flight.

**Sequencing correction — a finding about the plan, not this slice.** The slice table and the DS16
section gate DS16 on `DS4`, while the Start-Now ladder grouped its value grammar under "DS5 closed".
**Both were partly right:** `DS4` is the correct gate for *defining* the grammar, and it is not
sufficient for *landing* it, because DS16's own surfaces carry no values to decorate. C08 and C09
could be bridged tomorrow and still have no consumer here.

**The two bridges were not built,** as instructed: `BasisSignature`/`BasisAttribute`/
`BasisParameterBinding` and `DerivationRecipe`/`DerivationCertificate` are real and exercised (32
call sites on `build_derivation_recipe` alone) and served nowhere. Buildable — but a bridge with no
consumer is `contract_only` by construction.

### C12 — Ledger + "Not yet"

Update the surface readiness ledger; state explicitly what the slice does not claim.

#### C11 / C12 outcome (executed 2026-08-18) — the slice closes here, as `blocked_on_ds5`

**Everything still outstanding is blocked on another lane, and nothing remains that DS16 can do.**
That is why this closes rather than staying open: not because the work ran out, but because the
work that remains is not this slice's to perform.

**Delivered and permanent — the authority repair, end to end.** Eleven inventory families measured
with positive controls and every one a refusal, because no runtime producer exists for any of them; a
typed contract that defines **no field the runtime would populate with `null`**, with completeness
enforced by a validator that raises on a dropped or duplicated member and proven by dropping one; the
bridge (producer → artifact → OpenAPI → generated client), purely additive at `+411/−0`; both panels
bound and rendering typed refusals with behavioural proof; the ancestor retired in the same commit as
the rewire with a strangle proof; the MACHINE twin with parity read from the **rendered DOM** rather
than the shared model.

**`OuterSetValue` is finished and unconsumed.** Built, proven against `C01`'s negatives, a11y-clean,
**zero production importers**. Recorded as a component awaiting a surface — not as debt, and not to be
mounted over a refusal string to give it a home.

**Two of the seven register findings closed; five are stops, not remaining work.**

The two `baseline_lint_resolution_content_hash_drift:C06` entries were closed by recomputing the
`sha256` bindings from the live files — `PublicSectorReadinessPanel.tsx` and `RunDetailLayout.tsx`
genuinely changed when `C05` bound the panels, so the new hash is the hash of a file this slice
deliberately changed. Correct rather than convenient.

The remaining five do not close inside DS16's cut-lines:

- **Four `rebound_consumer_missing`.** The re-point was performed exactly as briefed and produced
  four *new* `c23_containment_root_drift` findings, because `_validate_c23_containment_roots` pins the
  expected list in `C23_SUCCESSOR_REFS` (checker `:1484`) and compares `consumer_refs` against it for
  exact equality (`:3410`). **The register and the checker are coupled and have different owners** —
  the register is DS16's under §3, the checker is explicitly excluded by that same §3. The re-point
  was reverted rather than landed against a file this slice does not own.
- **One `census_observation_drift`.** Diagnosed, deliberately not patched: a single reference moved
  `quantityDecisionProducerHarness.tsx:139 → :148`, **byte-identical line content**
  (`return buildSignedPublicDecisionPacket({`), nine lines lower because `C01` inserted an import
  block above; membership unchanged at `28 → 28`, which is why the checker reported
  `observation_drift` and not `expected_count_drift`. `DS5` is replacing line-numbered census
  references with content-addressed TypeScript identity tokens, so bumping a line number into an
  artifact whose owner is removing line numbers would be correct today and discarded on `DS5`'s
  landing. This is the "update a number to make a gate green" the slice refused three times, wearing
  the mask of a legitimate edit.

**The bind is an architect defect in §3 of this plan, recorded so it is not repeated.** §3 made the
disposition register DS16's to write while excluding the checker that pins the register's contents.
Two coupled files, two owners, and the coupling was not visible when the cut-lines were drawn.

**The two-condition proof holds; only landing it does not.** A successor closes when a real consumer
exists **and** the old owner path is proven strangled. Both are established: the panels are bound to
`useRunAuthorityValues` and render typed refusals with behavioural assertions; the minting modules
were deleted at `bc1d01001` and the witness retired in the rewire commit, with the successor covering
**10 of 11** ancestor corruptions and the single gap (arbitrary i18n key) declared. The blocker is
ownership and contention, not evidence.

##### Handoff to DS5 — the exact end state DS5 must pin

`DS5` owns `check_frontend_disposition_register.py`, so **`DS5` reconciles**. It has both files open —
the checker at `+5,312/−517` and the register at `+2,315/−57` — and **still carries the retired
`readinessScientificContainment.test.ts`** in `C23_SUCCESSOR_REFS`, so `DS5` is not closing these rows
on its own either. The required end state, stated here so it does not have to be re-derived:

```python
C23_SUCCESSOR_REFS = [
    "apps/runtime-dashboard/src/features/runs/components/PublicSectorReadinessPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/ScientificDepthPanel.tsx",
    "apps/runtime-dashboard/src/features/runs/components/ds16SuccessorContainment.test.ts",
]
```

Only the third entry changes; the first two are unchanged. The register's successor `consumer_refs`
must equal this list exactly, and the four rows then move out of `rebind_pending`.

**`C23_RATIONALE` is also stale and its own condition is now satisfied.** It reads *"the retained
panels emit unavailable until DS16 provides producer-signed fields or registered typed refusal"* —
DS16 has provided the registered typed refusal, so the rationale should be rewritten to describe the
delivered state rather than the awaited one.

##### Merge ordering — now two conditions, not one

1. the `GY-DEFC-8` cold `N11` closeout is banked (`E12`: any `.py` under the source root re-prices the
   three deployment-bound GY artifacts);
2. **`DS5` lands first**, then this branch takes `main` and reconciles.

The second is not a preference. `DS5` carries `+2,315` lines of the same register this branch edited;
the later DS16 merges, the more that costs. The branch is currently **RED on a governed gate**
(register checker exit `1`, five findings) — closing the task and merging the branch are different
acts, and only the first is done here.

##### Six registered dependencies

Three from `C07`: `NormativeAuthorizationRecord` (0 files), `NormativeDecisionRequest` (0 files),
run-scoped `ValueOuterSetComparison` producer (contract exists, 0 callers, 0 served).
Three from `C08`/`C09`/`C10`: the basis bridge (`BasisSignature` real and exercised, 0 served), the
derivation bridge (`DerivationRecipe`/`DerivationCertificate`, 32 call sites on
`build_derivation_recipe`, 0 served), and a run-scoped `ObservationProvenanceClass` producer and served
field (0 served under any name).

##### Successor slice — re-entry condition as a property

The grammar body (`C07`–`C10`) becomes a registered successor. **Re-entry condition: a surface exists
that renders values rather than refusals.** By the master plan's DAG that arrives with **`DS7` Cycle
Board on real capstone data**; `DS7` gates on `DS5`, in flight. The two bridges are buildable today by
whoever needs them, but **not by this slice** — a bridge with no consumer is `contract_only` by
construction.

##### Sequencing correction, recorded as a finding about the plan

The slice table and the `DS16` section both gate this slice on `DS4`; the Start-Now ladder grouped its
value grammar under "DS5 closed". **Both were partly right.** `DS4` is the correct gate for *defining*
the grammar and is insufficient for *landing* it, because DS16's own surfaces carry no values to
decorate — measured: both panels contain **zero** quantity references. `C08` and `C09` could be
bridged tomorrow and still have no consumer here.

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
