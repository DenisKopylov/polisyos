---
plan_id: atlas-ds0-source-of-truth-freeze-and-governing-decisions
title: "DS0 - Source-Of-Truth Freeze & Governing Decisions"
type: slice-plan
status: ready - executable pre-activation (Phase A, Layer-3-independent)
created: 2026-06-11
revised: 2026-06-11
last_verified: 2026-06-11
stability: draft
slice: DS0
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
audiences: [MACHINE, EXPERT]          # ledgers + decision records with docs projections; no user-facing surface
backend_co_owner: none                # decision slice - no runtime producers
feature_flags: none
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ../../../reference/frontend/workspace-contract.md
  - ../../../../design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip  # sha256 28d3e51d…
  - ../../../brand/ATLAS_DESIGN_SYSTEM.md
  - ../../../brand/ATLAS_V4_ADOPTION.md
  - ../FRONTEND_SOTA_PLAN.md
  - ../DESIGN_BEST_IN_CLASS_PLAN.md
  - ../POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md
---

# DS0 - Source-Of-Truth Freeze & Governing Decisions

## For agentic workers

This is an executable slice spec, not a strategy note. Follow it red-first:
validator tests are written and failing before the schemas and records they
validate exist.

DS0 **is**: the Atlas analogue of G0 — six governing decisions recorded as
machine artifacts, two ledger schemas with a fail-closed validator, and the
supersession of the drifting v4/v7 design documents. It is Layer-3-independent
and may execute before the master plan's activation gate.

DS0 **is not**: an audit (DS1), an adjudication of v15 content (DS2), a
component or token migration (DS4), or anything user-facing. DS0 decides and
defines; it ships no surface, admits nothing to production, and changes no app
code. A decision without rejected alternatives and a revisit condition is not a
decision — it is an opinion, and the validator rejects it.

Decision D4 (locale scope) is value-laden and **requires a named human owner's
explicit sign-off** recorded in the decision artifact; an agent must not
default it.

## Closure Contract

DS0 is closed when every box below is checked and the validation commands pass:

- [ ] `architecture/atlas_surfaces/` exists with the four artifacts in the
      File Map, each passing `check_atlas_surface_ledgers.py`.
- [ ] All six governing decisions (D1–D6) are recorded with decision, rejected
      alternatives, owner, decided_at, and revisit condition; D4 carries a
      human sign-off marker.
- [ ] `adoption_ledger.json` is seeded with the v15 archive (sha256-pinned)
      and the in-repo v4 system as `pending` entries — no verdicts issued.
- [ ] `surface_readiness_ledger.json` is seeded with all 15 master-plan slices
      at `defined`; vocabulary is capability-reality labels only.
- [ ] `FRONTEND_SOTA_PLAN.md` and `DESIGN_BEST_IN_CLASS_PLAN.md` are moved to
      `docs/plans/archive/` with supersession frontmatter; the docs lifecycle
      gate passes.
- [ ] `ATLAS_DESIGN_SYSTEM.md`, `ATLAS_V4_ADOPTION.md`, and the v7 surfaces
      master plan carry their D1 disposition in frontmatter (superseded-as-
      canonical / retained-as-material), per the recorded decision.
- [ ] The docs projection `docs/reference/atlas-surface-ledgers.md` exists and
      the projection-parity test proves it matches the machine records.
- [ ] `atlas_ds0_readiness_manifest.json` reports `status: pass` and blocks
      (fail-closed) if any decision or ledger is missing or invalid.
- [ ] The `atlas-surfaces-ds0` family is registered in
      `architecture/generated_artifacts.toml`, the guardrails sync is clean,
      and the new test file is registered in `ci_tiers.toml`.
- [ ] All red-first tests from the tasks are green; the closeout pattern check
      is recorded.

Validation commands (expected output in parentheses):

```bash
uv run pytest tests/repo_quality/tools/test_check_atlas_surface_ledgers.py -q   # (all pass)
uv run python tools/quality/validation/check_atlas_surface_ledgers.py --repo-root .  # ("Atlas surface ledgers gate passed.")
uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .   # ("Docs lifecycle gate passed.")
uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline  # (clean, no unexpected diff)
```

## Scope Boundaries

In scope: decision records D1–D6; ledger schemas, seeds, validator, docs
projection; supersession/lifecycle execution for the four documents named in
D1; the DS0 readiness manifest.

Out of scope (**Not yet**): route/feature/authz/cache audit (DS1); v15
conformance battery and any adoption verdict beyond `pending` (DS2); creating
`packages/atlas-ui` or moving any code (DS4+); changing flags, locales, tokens,
or `docs/brand/` content beyond frontmatter dispositions; touching
`apps/runtime-dashboard`; emitting any HTTP producer.

## Pattern Pass

| Pattern | DS0 exposure | Negative control (red-first) |
| --- | --- | --- |
| P06 canonical ownership ambiguity | the slice's whole purpose; supersession must be recorded, not implied | `test_atlas_ds0_superseded_docs_carry_lifecycle_frontmatter` |
| P10 structural-only validation | archive "PASS" reports must not satisfy evidence requirements | `test_atlas_ds0_archive_report_alone_cannot_support_stable` |
| P04 status enum proliferation | ledgers must reuse controlled vocabulary, never mint statuses | `test_atlas_ds0_readiness_ledger_rejects_ui_only_status_labels` |
| P05 authority dilution | docs projection must not upgrade or soften machine-record content | `test_atlas_ds0_ledger_docs_projection_matches_machine_record` |
| P13 contract gravity well | six decisions, two schemas, one validator — nothing more; every artifact traces to a master-plan deliverable | scope-boundary review at closeout |
| P26 responsibility integrity | D4 is value-laden; an agent defaulting it is laundering | `test_atlas_ds0_locale_decision_requires_human_owner_signoff` |

## Code-Grounded Reality

The master plan's "Code-Grounded Technical State" table is the substrate
inventory; DS0 consumes these rows without re-deriving them:

- **Sources in conflict (D1):** living coded v4 (`shared/ui/tokens/designTokens.ts`,
  ~40 components), `docs/brand/ATLAS_DESIGN_SYSTEM.md` + `ATLAS_V4_ADOPTION.md`
  (v4 docs), v7 surfaces master plan, v15 archive
  (`design/atlas-v15/…zip`, sha256 `28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969`).
- **Tokens (D2):** `designTokens.ts` is hand-coded TS; v15 carries a DTCG
  pipeline with generated CSS/TS/Tailwind/Figma outputs. Two formats, no
  declared winner (master-plan tension T6).
- **Package home (D3):** `packages/` holds `runtime-api-client` (generated)
  and `cli` (styleguide exports); `apps/runtime-dashboard/src/shared/ui` is
  the de-facto component home. Workspace contract governs placement.
- **Locales (D4):** `en`/`uk`/`ru` with parity tests, ICU messages,
  formatters. `ru` retention is a value-laden product/policy question.
- **Flags (D5):** 12 manifest-driven flags (`shared/lib/featureFlags.ts`,
  remote manifest via `VITE_FEATURE_FLAGS_URL`, zod, TTL) **plus** a second
  source: `feature_overrides` from `/api/v1/auth/me`. No owner/intent/sunset
  anywhere.
- **Non-web (D6):** `packages/cli` styleguide; `docs/brand/EMAIL_TEMPLATES.md`,
  `PRINT_AND_EXPORT.md`, `CLI_STYLEGUIDE.md`, `GLYPH_SPECIFICATION.md`,
  `MOTION.md`, `BUREAUCRATIC_RENDERING.md`, `A11Y_CONTRAST.md` — specs without
  a plan home.
- **Validator conventions to reuse:** `tools/quality/validation/check_docs_lifecycle.py`
  (gate style, `--repo-root`, exit codes); repo-quality tests under
  `tests/repo_quality/tools/`.

Verified registration and convention facts (2026-06-11 pass) — these are the
load-bearing details a naive execution would miss:

- **`architecture/generated_artifacts.toml` is a governed registry** (233
  layer3 references): every committed artifact family carries `owner`,
  `approval_owner`, `lifecycle`, `generator`, `verifier`,
  `stale_output_behavior`, `outputs[]`. The new `architecture/atlas_surfaces/`
  outputs **must be registered as a family**, and
  `docs/reference/generated-artifacts.md` is **generated** from the registry by
  `uv run python tools/devx/architecture/guardrails.py sync
  --skip-deep-import-baseline` — never hand-edit it.
- **`architecture/production_quality/ci_tiers.toml` registers every test
  file** (`[[tests]]` with `path`/`tier`/`owner`/`purpose`). The new test file
  gets a `fast-pr` entry.
- **Archive convention:** `docs/plans/archive/` uses date-prefixed kebab-case
  names (`2026-05-19-…-implementation-plan.md`) and YAML frontmatter
  (`status`, `last_verified`, `stability`, `owner`, `supersedes`). The two
  moved plans are renamed accordingly, not just moved.
- **The brand docs have no YAML frontmatter** — they use bold text lines
  (`**Status:** Canonical production design system`). Disposition = add YAML
  frontmatter on top *and* update the bold status line; both currently claim
  canonical status.
- **ADR-047 (Atlas v4 dark-theme canonicalization) exists** and is referenced
  from `ATLAS_V4_ADOPTION.md`, alongside the reference token file
  `docs/brand/atlas-v4/colors_and_type.css`. **D1 leaves ADR-047 in force** —
  superseding an accepted ADR is an ADR-process act that belongs after DS2
  verdicts, not in DS0. `ATLAS_V4_ADOPTION.md` also records a
  `/Users/…/Downloads/` source path (the same non-replayable-source defect the
  v15 ingestion fixed) — note it in the disposition, fix belongs to DS2.
- **Inbound references to the two moved plans exist in ~12 files**, including
  `docs/README.md`, `docs/reference/documentation-inventory.md`,
  `docs/brand/A11Y_CONTRAST.md`, the v7 surfaces master plan, and
  `SCIENTIST_BEST_IN_CLASS_PLAN.md` / `FABRIC_BEST_IN_CLASS_PLAN.md`. Task 3
  updates references in **active/living** docs; references inside
  `docs/archive/` and `docs/plans/archive/` stay as historical record.
- **`docs/reference/documentation-inventory.md` is a docs control ledger** —
  the new reference page gets an entry there; mkdocs nav does not require
  individual reference pages (only the ADR nav tokens are enforced).
- **The i18n parity test enforces full key parity across en/ru/uk today**
  (imports all three JSON files, compares key paths) — this is what makes the
  D4 enforcement mechanism above necessary.
- **No feature-flag manifest file exists in the repo** — `VITE_FEATURE_FLAGS_URL`
  is env-only and defaults to empty (compiled-in defaults win). D5's registry
  is therefore a records-only act in DS0; creating and serving the actual
  manifest is DS5 greenfield, larger than it looks.

## Governing Decisions — Menu And Defaults

Task 2 records each decision in `atlas_ds0_governing_decisions.json`. Defaults
below are recommendations; the recorded decision may override them, but must
record what it rejected and when to revisit.

### D1 — Canonical source of truth & supersession

- **Decision:** what is canonical for design-system truth from DS0 onward.
- **Default:** the **adoption ledger + surface constitution** become canonical.
  `ATLAS_DESIGN_SYSTEM.md`/`ATLAS_V4_ADOPTION.md` → superseded-as-canonical,
  retained as v4 reference; `FRONTEND_SOTA_PLAN.md`/`DESIGN_BEST_IN_CLASS_PLAN.md`
  → archived; v7 surfaces master plan → superseded-as-execution-master,
  retained as DS11–DS13 material. The v15 archive remains an evidence source,
  never canonical (`implemented_but_not_orchestrated` until DS2 verdicts).
- **Revisit:** when DS2 closes (ledger becomes content-bearing).

### D2 — Token pipeline

- **Decision:** one token source format and generation path; sunset for the
  loser (closes master-plan T6).
- **Default:** **DTCG JSON as canonical format** with one generation pipeline
  emitting CSS variables/Tailwind/TS; `designTokens.ts` becomes a generated
  output (or carries a sunset date); v15 token *content* still passes DS2
  adjudication before adoption. Rationale: hand-coded TS tokens cannot feed
  Figma/theming/a11y-mode generation; DTCG is the industry contract format.
- **Revisit:** at DS2 closure, when content verdicts exist.

### D3 — Package home, versioning, Figma status

- **Decision:** where admitted design-system code lives, how it versions, what
  Figma is.
- **Default:** `packages/atlas-ui`, private, semver with changelog, releases
  cut per DS-slice closure; **Figma is a projection, never a source** —
  parity owned by `team-design` with a per-release parity check. Placement
  conforms to the workspace contract.
- **Revisit:** if a second consuming app appears.

### D4 — Locale scope (value-laden; human owner required)

- **Decision:** locale set going forward (en/uk/ru exist), `ru` retention,
  RTL posture, copy-register owner.
- **Owner decision taken (2026-06-11, Denis Kopylov): option (b)** — `en`/`uk`
  are product locales; `ru` is **frozen-but-served**: existing `ru` keys remain
  and are served, no new translation obligations accrue. Rejected: (a) keep
  all three as product locales (ongoing ru translation cost without product
  commitment); (c) remove `ru` (breaks existing users without need). RTL:
  not-in-envelope until a target locale exists (untested = out-of-envelope).
- **Enforcement mechanism (record in the decision; implement in the first
  slice that adds a locale key, not in DS0):** the parity test today imports
  all three locales and enforces **full key parity** — it will fail on the
  first post-freeze key. The recorded mechanism: freeze date + `ru` falls back
  to `en` for keys added after the freeze; `parity.test.ts` changes from
  "ru = en" to "ru ⊇ frozen key set, fallback allowed beyond it". Task 2
  records this with an `enforcement_change_owner` so the change is not
  orphaned.
- **Sign-off:** record `human_signoff: {name: "Denis Kopylov", date: "2026-06-11"}`
  per the schema; the red-first sign-off test then passes against a real
  record, not a placeholder.
- **Revisit:** at DS12 gate (public surfaces make locale scope citizen-facing).

### D5 — Feature-flag governance

- **Decision:** single governed flag path + registry discipline.
- **Default:** the repo-served manifest becomes the one source;
  `/auth/me.feature_overrides` becomes a server projection of the same
  registry (no second vocabulary); every flag gets `owner`, `intent`
  (`launch-gate` / `experiment` / `kill-switch` / `mode`), and `sunset_or_review`
  date in a registry section of the decisions artifact. Flags are this plan's
  dark-shipping mechanism (master-plan doctrine), so ungoverned flags are a
  defect from DS4 onward.
- **Revisit:** DS5 (lint can then enforce registry membership).

### D6 — Non-web surface disposition

- **Decision:** plan home for email/print/CLI/glyph/motion surface specs.
- **Default:** **explicitly out-of-scope for this plan generation**, recorded
  per artifact with a revisit condition: email → revisit when notification
  surfaces are proposed; print/export → revisit at DS12–DS13 (public records
  print path); CLI styleguide → stays owned by `team-frontend`, out of Atlas
  scope; glyph/motion/contrast specs → inputs to DS2 adjudication, not
  standalone surfaces.
- **Revisit:** as recorded per artifact above.

## Persisted Artifacts & Schemas

Home: `architecture/atlas_surfaces/` (this slice ratifies the master plan's
proposed location — record as part of D1).

**`atlas_ds0_governing_decisions.json`** — header: `schema_version`,
`generated_at`; entries: `decision_id` (D1–D6), `title`, `decision`,
`rejected_alternatives[]` (non-empty), `owner`, `decided_at`,
`revisit_condition` (non-empty), `links[]`; D4 additionally:
`human_signoff: {name, date}`.

**`adoption_ledger.json`** — header: `schema_version`, `generated_at`,
`source_hashes` (v15 sha256 pinned); entries: `id`, `kind`
(`token_set|component|pattern|package|doc|archive`), `source`
(`v4_code|v4_doc|v7_doc|v15_archive`), `verdict`
(`pending|admit_as_is|admit_after_refactor|wrap_then_strangle|reject|defer`),
`maturity` (`experimental|beta|stable|deprecated|na`), `evidence_refs[]`
(typed: `kind` ∈ `archive_report|browser|at_manual|visual_snapshot|contract_test|storybook`,
`ref`), `consuming_surface`, `rejected_deltas[]`, `reason`,
`revisit_condition`, `sunset_date`, `owner`, `decided_at`, `as_of`.
Schema rules (validator-enforced): `reject`/`defer` ⇒ `reason` +
`revisit_condition` non-empty; `maturity=stable` ⇒ `evidence_refs` contains at
least one `browser` **and** one `at_manual` entry — `archive_report` entries
alone never qualify; verdict/maturity vocabularies are closed (extra values
fail).

**`surface_readiness_ledger.json`** — header: `schema_version`, `as_of`;
entries: `surface_id`, `route_or_component`, `audiences[]`
(`PUBLIC|REVIEWER|EXPERT|MACHINE`), `chain` — nine links
(`contract|producer|persisted|bridge|consumer|verification|surface|negative_test|semantic_test`),
each `{status: implemented|missing|out_of_scope, ref}`; `readiness_label`
(capability-reality labels only: `contract_only|producer_missing|bridge_missing|consumer_missing|verification_missing|surface_missing|semantic_test_missing|implemented`),
`provenance_posture` (`live|replay|fixture_only`), `owning_slice`, `not_yet[]`,
`updated_at`. Schema rule: any label outside the closed vocabularies fails
(no UI-local statuses — P04).

**`atlas_ds0_readiness_manifest.json`** — `status: pass|blocked`,
`blockers[]` (issue codes), `decisions: {D1..D6: recorded|missing}`,
`ledgers: {adoption: valid|invalid, readiness: valid|invalid}`,
`docs_lifecycle: pass|fail`, `generated_at`. Fail-closed: any missing piece ⇒
`blocked` with issue codes, never a partial pass.

## File Map

| Path | Action |
| --- | --- |
| `architecture/atlas_surfaces/atlas_ds0_governing_decisions.json` | create (Task 2) |
| `architecture/atlas_surfaces/adoption_ledger.json` | create + seed (Task 1) |
| `architecture/atlas_surfaces/surface_readiness_ledger.json` | create + seed (Task 1) |
| `architecture/atlas_surfaces/atlas_ds0_readiness_manifest.json` | create (Task 4) |
| `tools/quality/validation/check_atlas_surface_ledgers.py` | create (Task 1) |
| `tests/repo_quality/tools/test_check_atlas_surface_ledgers.py` | create red-first (Task 0) |
| `docs/reference/atlas-surface-ledgers.md` | create docs projection (Task 4) |
| `docs/plans/active/FRONTEND_SOTA_PLAN.md` | move + rename → `docs/plans/archive/2026-06-11-policyos-frontend-sota-improvement-plan.md` (Task 3) |
| `docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md` | move + rename → `docs/plans/archive/2026-06-11-policyos-atlas-best-in-class-design-roadmap.md` (Task 3) |
| `docs/brand/ATLAS_DESIGN_SYSTEM.md`, `docs/brand/ATLAS_V4_ADOPTION.md` | add YAML frontmatter + update bold status lines per D1 (Task 3) |
| `docs/plans/active/POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md` | frontmatter disposition per D1 (Task 3) |
| `architecture/generated_artifacts.toml` | register `atlas-surfaces-ds0` family (Task 1) |
| `architecture/production_quality/ci_tiers.toml` | register new test file, `fast-pr` (Task 1) |
| `docs/reference/documentation-inventory.md` | ledger entry for the new reference page + reference updates (Tasks 3–4) |
| `docs/README.md`, `docs/brand/A11Y_CONTRAST.md`, `SCIENTIST_BEST_IN_CLASS_PLAN.md`, `FABRIC_BEST_IN_CLASS_PLAN.md` | inbound-reference updates (Task 3) |

Paths follow existing repo conventions (`check_docs_lifecycle.py`,
`tests/repo_quality/tools/`); if a convention differs on contact, follow the
repo and record the delta in the readiness manifest, do not fork a new
convention.

## Implementation Tasks

### Task 0 — Red Baseline

Implement: nothing. Write the failing tests and confirm the world before
changes.

Tests (all red at this point except the baseline check):

- `test_atlas_ds0_adoption_ledger_schema_is_strict`
- `test_atlas_ds0_adoption_ledger_rejects_unknown_verdict`
- `test_atlas_ds0_reject_and_defer_require_reason_and_revisit`
- `test_atlas_ds0_archive_report_alone_cannot_support_stable`
- `test_atlas_ds0_readiness_ledger_uses_capability_reality_labels_only`
- `test_atlas_ds0_readiness_ledger_rejects_ui_only_status_labels`
- `test_atlas_ds0_governing_decisions_require_rejected_alternatives`
- `test_atlas_ds0_locale_decision_requires_human_owner_signoff`
- `test_atlas_ds0_seed_entries_reference_v15_archive_hash`
- `test_atlas_ds0_readiness_manifest_blocks_until_all_decisions_recorded`

Validation: `uv run python tools/quality/validation/check_docs_lifecycle.py
--repo-root .` is green **before** any move (baseline), and the new test file
collects and fails (`uv run pytest tests/repo_quality/tools/test_check_atlas_surface_ledgers.py -q`).

### Task 1 — Ledger Schemas, Validator, Seeds

Implement:

- Strict schemas for both ledgers exactly as specified above (closed
  vocabularies, conditional requirements).
- `check_atlas_surface_ledgers.py`: validates both ledgers + decisions +
  manifest; gate-style output and exit codes mirroring
  `check_docs_lifecycle.py`; fail-closed on missing files.
- Seed `adoption_ledger.json`: two entries, both `verdict: pending` — the v15
  archive (kind `archive`, sha256 in `source_hashes`) and the in-repo v4
  system (kind `package`, source `v4_code`).
- Seed `surface_readiness_ledger.json`: 15 entries (DS0–DS14), each
  `readiness_label` per master-plan reality (DS0 in progress, others
  `contract_only`), `owning_slice` set, `not_yet` from the master plan.
- **Register the artifact family** in `architecture/generated_artifacts.toml`
  (family `atlas-surfaces-ds0-governance-artifacts`: owner `team-design`,
  lifecycle `generated_committed`, generator "DS0 validator write mode",
  verifier `check_atlas_surface_ledgers.py`, `stale_output_behavior = "fail"`,
  the four outputs) and run the guardrails sync so
  `docs/reference/generated-artifacts.md` regenerates.
- **Register the test file** in `architecture/production_quality/ci_tiers.toml`
  (`tier = "fast-pr"`, owner `team-design`).

Tests turning green: schema/vocabulary/seed tests from Task 0.

Validation: `check_atlas_surface_ledgers.py` passes on the seeds; mutating a
seed verdict to an unknown value makes it fail (run both directions);
`uv run python tools/devx/architecture/guardrails.py sync
--skip-deep-import-baseline` exits clean with no unexpected diff.

### Task 2 — Governing Decision Records (D1–D6)

Implement:

- `atlas_ds0_governing_decisions.json` with all six decisions from the menu;
  every entry carries rejected alternatives + revisit condition + owner.
- D4 is recorded per the owner decision already taken (option b, 2026-06-11,
  Denis Kopylov) including the parity-test enforcement mechanism and its
  `enforcement_change_owner`; the `human_signoff` field carries the real
  owner and date.
- D5 includes the flag registry section: all 12 flags with owner/intent/
  sunset_or_review.

Tests turning green: decision-requirement tests, locale-signoff test.

Validation: validator passes; removing `rejected_alternatives` from any entry
makes it fail.

### Task 3 — Supersession Execution & Lifecycle Moves

Implement (exactly as recorded in D1 — if D1 overrode the default, follow D1):

- Move and **rename per archive convention**:
  `FRONTEND_SOTA_PLAN.md` → `docs/plans/archive/2026-06-11-policyos-frontend-sota-improvement-plan.md`,
  `DESIGN_BEST_IN_CLASS_PLAN.md` → `docs/plans/archive/2026-06-11-policyos-atlas-best-in-class-design-roadmap.md`;
  frontmatter per archive convention (`status: superseded`, `stability`,
  `owner`, `last_verified`, `superseded_by` → surface constitution + Atlas
  master plan).
- The two `docs/brand` Atlas docs **have no YAML frontmatter** — add it
  (disposition per D1) **and** update the bold `**Status:**` lines that
  currently claim canonical status; leave **ADR-047 untouched and in force**,
  noting in the disposition that its supersession is a post-DS2 ADR-process
  act; note the `Downloads/` source-path defect in `ATLAS_V4_ADOPTION.md`
  (fix belongs to DS2).
- v7 surfaces master plan: frontmatter disposition
  (superseded-as-execution-master, retained-as-material, `superseded_by`).
- Update inbound references in **active/living** docs (`docs/README.md`,
  `docs/reference/documentation-inventory.md`, `docs/brand/A11Y_CONTRAST.md`,
  v7 master plan, `SCIENTIST_BEST_IN_CLASS_PLAN.md`,
  `FABRIC_BEST_IN_CLASS_PLAN.md`, both Atlas plan documents); leave
  references inside `docs/archive/` and `docs/plans/archive/` as historical
  record.

Tests: `test_atlas_ds0_superseded_docs_carry_lifecycle_frontmatter`.

Validation: `check_docs_lifecycle.py` passes after the moves.

### Task 4 — Readiness Manifest, Docs Projection, Closeout

Implement:

- `atlas_ds0_readiness_manifest.json` computed by the validator (not
  hand-written): decisions recorded, ledgers valid, lifecycle pass ⇒
  `status: pass`; anything missing ⇒ `blocked` + issue codes.
- `docs/reference/atlas-surface-ledgers.md`: human projection of both ledgers
  and the six decisions; generated or parity-tested against the machine
  records — it must not say more or less than they do (P05); register the
  page in `docs/reference/documentation-inventory.md` (control ledger).
  `docs/reference/generated-artifacts.md` is **not** hand-edited — it
  regenerates via the guardrails sync from Task 1.
- Update the readiness ledger: DS0 entry → its true closing state.
- Closeout pattern check: re-run the Pattern Pass table against what was
  actually built; record deviations in the manifest.

Tests turning green: manifest fail-closed test, projection parity test
(`test_atlas_ds0_ledger_docs_projection_matches_machine_record`).

Validation: all three closure commands pass in sequence.

## Issue Codes

| Code | Meaning |
| --- | --- |
| `ATLAS-DS0-001 decision_missing:<id>` | a governing decision is not recorded |
| `ATLAS-DS0-002 decision_incomplete:<id>` | missing rejected alternatives, owner, or revisit condition |
| `ATLAS-DS0-003 locale_signoff_missing` | D4 recorded without human sign-off |
| `ATLAS-DS0-004 ledger_schema_violation:<path>` | ledger entry violates schema or closed vocabulary |
| `ATLAS-DS0-005 stable_without_evidence` | maturity `stable` lacking browser + AT evidence refs |
| `ATLAS-DS0-006 archive_hash_mismatch` | seeded v15 entry does not match the pinned sha256 |
| `ATLAS-DS0-007 lifecycle_gate_failure` | docs lifecycle gate fails after moves |
| `ATLAS-DS0-008 projection_drift` | docs projection diverges from machine records |

## Commit Sequence

One commit per task, red visible before green:

1. `atlas-ds0: red baseline - ledger validator tests (failing)`
2. `atlas-ds0: ledger schemas, validator, seeds`
3. `atlas-ds0: governing decisions D1-D6`
4. `atlas-ds0: supersession execution and lifecycle moves`
5. `atlas-ds0: readiness manifest, docs projection, closeout`

## Non-Negotiables

- DS0 ships no user-facing surface and admits nothing into production use.
- Both ledger vocabularies are closed; a new status value is a defect, not an
  extension (P04 / constitution Rule 8).
- `reject` and `defer` without reason + revisit condition are invalid.
- Archive-level reports never satisfy `stable` evidence (P10).
- D4 without a named human sign-off blocks the slice honestly (P26); agents do
  not default value-laden decisions.
- The docs projection never says more, less, or softer than the machine
  records (P05).
- If execution reveals that a deliverable here is disproportionate or
  misplaced, amend the master plan (T9 discipline) — do not silently grow this
  slice.
