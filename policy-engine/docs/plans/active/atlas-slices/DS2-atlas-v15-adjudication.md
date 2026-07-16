---
plan_id: atlas-ds2-atlas-v15-adjudication
title: "DS2 - Atlas v15 Adjudication"
type: slice-plan
status: complete-on-branch - architect review pending
created: 2026-07-16
revised: 2026-07-16
last_verified: 2026-07-16
stability: review-ready
closed_at: 2026-07-16
slice: DS2
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_record: ../../../brand/ATLAS_SOURCE_OF_TRUTH.md
ds1_report: ../../../reference/frontend/atlas-live-application-audit.md
adoption_schema: ../../../../architecture/atlas_surfaces/adoption-ledger.schema.json
archive_readme: ../../../../design/atlas-v15/README.md
adjudication_report: ../../../reference/frontend/atlas-v15-adjudication.md
adoption_instance: ../../../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
phase_a_synthesis: ../../../reference/frontend/atlas-phase-a-synthesis.md
journal: ../../../superpowers/journals/2026-07-16-atlas-ds2-v15-adjudication.md
audiences: [REVIEWER, EXPERT, MACHINE]
owner: team-design
runtime_co_owner: team-architecture  # evidence consumer only; DS2 changes no runtime code
depends_on:
  - ./DS0-source-of-truth-freeze-and-governing-decisions.md
  - ./DS1-live-application-audit.md
  - ../../../brand/ATLAS_SOURCE_OF_TRUTH.md
  - ../../../../architecture/atlas_surfaces/adoption-ledger.schema.json
  - ../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json
  - ../../../reference/policy-design-case-failure-patterns.md
---

# DS2 - Atlas v15 Adjudication

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` for independent archive-research
> clusters and keep all repository edits with the controlling agent.

## Goal

Fully adjudicate the sha256-frozen Atlas v15 archive into the DS0 adoption
ledger against DS1's living coded v4 baseline, then close Phase A with one
architect-facing synthesis that re-scopes DS3-DS18 from measured evidence.

## Architecture

DS2 treats the zip as immutable subordinate evidence. It extracts only to a
scratch directory, builds one canonical logical-item index whose rows cover
every non-directory archive member, and projects the same stable item IDs into
the human report and strict DS0 adoption-ledger instance. Components and
patterns are migration decisions against DS1's 89 implementations in 12
families; archive reports are evidence about archive-internal consistency, not
runtime or maturity authority.

## Tech Stack

Markdown, JSON Schema Draft 2020-12, JSON, `shasum`, `zipinfo`/`unzip`, `jq`,
`rg`, and an ephemeral standard-library script for deterministic inventory,
projection, and parity checks. No application dependency, build, browser, or
test tooling is installed or changed.

## Global Constraints

- Work only in `.worktrees/atlas-ds0` on
  `codex/atlas-ds0-source-of-truth`, stacked on DS0+DS1 HEAD `b0f66adc0`.
- The archive hash must equal
  `28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969`
  before extraction. A mismatch stops DS2.
- The zip is immutable. Extraction lives under `/private/tmp` and is never
  committed.
- Writable repository paths are this DS2 plan, the DS2 report and Phase-A
  synthesis under `docs/reference/frontend/**`,
  `architecture/atlas_surfaces/**`, exactly one new DS2 journal, and
  disposition-only edits to `design/atlas-v15/README.md`.
- `apps/**`, `packages/**`, `frontend/**`, `e2e/**`, and runtime HTTP code are
  read-only evidence. No application code, tests, generated client, token
  output, component, route, dependency, or flag changes are allowed.
- The GY worktree `.worktrees/gy-n13a`, its branch,
  `docs/plans/active/layer3-slices/**`,
  `architecture/policy_design_case/**`, `tools/quality/**`, and
  `production_data/**` are forbidden.
- Reuse the DS0 schema and Revision-2 controlled vocabulary. Do not add a
  local verdict, maturity, audience, source, or artifact-kind enum.
- No archive `PASS`, `stable`, release, coverage, or Figma label can assign
  PolicyOS maturity `stable`; the archive cannot contain repo browser,
  manual-AT, runtime-integration, authority-compatibility, or repo-gate
  evidence by construction.
- Every verdict records the strongest rejected alternative and a concrete
  revisit condition. Every losing v4/v15 path gets a sunset condition.
- `defer` is the default when no DS3-DS18 consuming surface justifies
  admission. Admission to the ledger is not production admission.
- Commit per checkpoint: task plan, conformance battery, adjudication,
  ledger+synthesis, closeout. Do not merge or push.

---

## Governing Sources And Reused Vocabulary

DS2 derives, in order, from:

1. the [Revision 2 master plan](../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md),
   especially the corrected Code-Grounded Technical State and DS2 closure
   contract;
2. the [surface constitution](../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md),
   especially laws 1-12, the component maturity bar, and Atlas v15 Admission
   Posture;
3. the [DS0 governing record](../../../brand/ATLAS_SOURCE_OF_TRUTH.md),
   especially D1's source hierarchy, D2's token-source decision and revisit
   condition, and D3's unaudited Figma mappings;
4. the [DS1 audit](../../../reference/frontend/atlas-live-application-audit.md)
   and its [machine ledger](../../../../architecture/atlas_surfaces/live-application-readiness-ledger.json),
   especially the 89-implementation/12-family v4 counterpart census;
5. the [failure/repair register](../../../reference/policy-design-case-failure-patterns.md).

The unchanged [adoption-ledger schema](../../../../architecture/atlas_surfaces/adoption-ledger.schema.json)
owns:

- verdicts: `admit_as_is`, `admit_after_refactor`,
  `wrap_then_strangle`, `reject`, `defer`;
- maturity: `experimental`, `beta`, `stable`, `deprecated`;
- audiences: `PUBLIC`, `REVIEWER`, `EXPERT`, `MACHINE`;
- artifact kinds: `token_set`, `component`, `pattern`, `package`, `doc`,
  `archive`;
- source: `v15_archive` and disposition
  `evidence_source_pending_adjudication`.

DS2 does not amend the schema merely to restate v4-counterpart prose. The
canonical ledger row carries the counterpart outcome through its reason,
sunset condition, rejected alternative, consuming surfaces, and next
adjudication; the human projection exposes those fields as a dedicated
counterpart column.

## Binding Boundary And Artifact Locations

| Artifact | Responsibility |
| --- | --- |
| `docs/plans/active/atlas-slices/DS2-atlas-v15-adjudication.md` | This executable spec and closure contract |
| `docs/reference/frontend/atlas-v15-adjudication.md` | Human conformance battery, coverage proof, per-item verdict projection, D2 parity result, and v4-vs-v15 outcomes |
| `architecture/atlas_surfaces/atlas-v15-adoption-ledger.json` | Canonical logical-item index and strict DS0-schema machine twin |
| `docs/reference/frontend/atlas-phase-a-synthesis.md` | DS0+DS1+DS2 input package for master-plan Revision 3, one row per DS3-DS18 slice |
| `docs/superpowers/journals/2026-07-16-atlas-ds2-v15-adjudication.md` | Unique checkpoint and reproducibility log |
| `design/atlas-v15/README.md` | Hash-preserving final disposition pointer only; the zip is unchanged |

Scratch inventory files and generation scripts are disposable execution
tools. They are not new governance artifacts and are not committed.

## Archive Identity Gate

The first archive operation is:

```bash
shasum -a 256 \
  design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
```

Expected hash:

```text
28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969
```

Only after the task-plan commit may the verified zip be extracted:

```bash
SCRATCH="$(mktemp -d /private/tmp/atlas-ds2-v15.XXXXXX)"
unzip -q \
  design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip \
  -d "$SCRATCH"
```

The journal records the resolved scratch path, member count, directory count,
uncompressed byte count, and a post-extraction repo `git status --porcelain`.

## Full-Denominator Inventory

### Physical-member coverage

`zipinfo -1` supplies the authoritative path denominator. Directories are
separated from non-directory members. Each non-directory member maps to
exactly one logical adjudication unit; no member may be unowned and no member
may map to two units. Generated outputs, examples, styles, stories, fixtures,
and reports remain physical members but may be subordinate evidence for the
logical item that owns them.

Closure requires:

```text
zip_non_directory_members - mapped_archive_members = empty
mapped_archive_members - zip_non_directory_members = empty
duplicate(mapped_archive_members) = empty
logical_unit_ids - report_verdict_ids = empty
report_verdict_ids - logical_unit_ids = empty
logical_unit_ids - ledger_entry_ids = empty
ledger_entry_ids - logical_unit_ids = empty
duplicate(logical_unit_ids) = empty
duplicate(ledger_entry_ids) = empty
```

The report publishes counts and deterministic grouping rules. The scratch
mapping retains every path during verification; repository outputs retain
exact archive path evidence on each logical row without committing an
unpacked archive or a redundant filesystem manifest.

### Logical units

The following rules prevent both file-level ceremony and semantic omission:

| Dimension | Logical unit rule | Required coverage statement |
| --- | --- | --- |
| DTCG token sets | One row per authored DTCG source or mode JSON file; generated CSS/TS/Tailwind/Figma outputs map to the source row that produced them, while an independently authored generated-only family becomes its own row | `adjudicated N of N authored token files`; all token-related archive members mapped |
| Components and state matrices | One row per canonical component identity in the archive map/manifest; its implementation, styles, tests, stories, examples, docs, and state-matrix cells map to that row. A named component absent from the canonical map is an additional row and finding | recomputed canonical count, archive-claimed count, and `adjudicated N of N` |
| Forms/data entry | One row per named form, validation, field, upload, selection, or data-entry pattern that has independent semantics | `adjudicated N of N` named patterns |
| Dashboard responsive model | One row per independently named responsive/layout/navigation model or breakpoint behavior, not per screenshot | `adjudicated N of N` models |
| Data-visualization grammar | One row per chart/encoding/legend/uncertainty/provenance/data-fallback grammar item; DS16 set-valued, basis-chip, and incomparability requirements are explicit comparison axes | `adjudicated N of N` grammar items |
| Themes and accessibility modes | One row per independently selectable or generated mode, including light/dark/high-contrast/density/reduced-motion semantics | `adjudicated N of N` modes |
| Governance and product patterns | One row per independently named governance, i18n, Figma, content-design, security/privacy-UX, or product-flow contract/pattern | category-by-category `adjudicated N of N` |
| Archive verification | One row per distinct verification report or scorecard; duplicated rendered formats map to the underlying report row and remain in physical-member coverage | `classified N of N` reports |
| Package/archive metadata | One row per package contract, generator/pipeline contract, or archive-level migration/release manifest that changes adoption behavior | `adjudicated N of N` contracts |

If two files disagree about the same identity, they remain one logical row
with an inconsistency finding. If a file contains multiple independently
adoptable named patterns, it produces multiple logical rows. This makes the
denominator a semantic adoption denominator while still proving all physical
members are accounted for.

## Conformance Battery Before Admission

Every archive verification report is classified before any component,
token, or pattern verdict is assigned. The report table carries:

| Claim class | Maximum fact it can establish | Evidence still missing | Owner |
| --- | --- | --- | --- |
| Schema/lint/static consistency | Parsed files satisfy the archive's own rules at the archived revision | repo schema/toolchain compatibility, runtime use, browser/AT behavior | DS4 / DS6 |
| Unit/component tests | Archived implementation satisfies its archived test harness | repo dependency integration, current-browser matrix, PolicyOS semantic negatives | DS4 / DS6 |
| Story/snapshot/visual report | A named archive state had a renderable or captured projection | live repo rendering, interaction, keyboard, responsive regression, human review | DS4 / DS6 |
| Automated accessibility report | The archived automated rule set found no reported violation in its exercised states | full state coverage, keyboard semantics, manual screen-reader/AT evidence | DS6 |
| Token parity/generation report | Archived source/output relations matched the archive's own compared sets | v4 semantic parity, repo drift gates, secure/reproducible generation | DS4 / DS6 |
| Governance/Figma/content checklist | Archive metadata or mapping fields are present and internally classified | owner ratification, code parity, runtime authority compatibility, public evidence | DS4 / DS6 |
| Performance/security/privacy score | The archive's static or self-reported target/check passed | deployed public-route measurement, threat/privacy review, telemetry and data-flow evidence | DS6 / DS12 |

For each actual report, DS2 records its archive path, claim text, method,
inputs, self-report status, what it proves, what it cannot prove, and the
DS4/DS6 evidence class required next. Missing raw inputs or an author-only
score are findings. No battery outcome raises a row above `beta`; most
unintegrated items remain `experimental`.

## Per-Item Adjudication Procedure

The controller applies the following steps to every logical item in stable-ID
order:

1. identify the authored source and every subordinate archive member;
2. classify the battery evidence without promoting self-attestation;
3. map the item to zero or more DS1 v4 families:
   `ui-primitives-root`, `ui-compounds-root`,
   `ui-operator-diagnostics`, `ui-authored-text`, `ui-compounds`,
   `ui-counterfactual`, `ui-patterns`, `ui-quantity`, `ui-responsive`,
   `ui-temporal`, `ui-trust-view`, `ui-tokens`;
4. name the consuming Revision-2 slice or apply `defer` when none exists;
5. assign one DS0 verdict and constitutional maturity;
6. name which v4/v15 side wins, the compatibility wrapper if any, and the
   evidence-based sunset condition for the loser;
7. record the strongest rejected alternative and the concrete condition that
   would reopen the verdict;
8. record `not_yet` limits and the purpose-scoped authority boundary;
9. project the canonical ledger row into the human verdict table.

### Verdict rules

- `admit_as_is`: semantics are useful unchanged as a future substrate, but
  production use still waits for the consuming slice and evidence bar.
- `admit_after_refactor`: semantics are admitted while package shape,
  naming, token binding, authority slots, accessibility, or repo integration
  must change before consumption.
- `wrap_then_strangle`: a live v4 consumer must remain behind a compatibility
  boundary while an admitted v15 semantic owner replaces it; the row states
  the measurable removal condition.
- `reject`: the item conflicts with constitutional authority/status rules,
  duplicates a stronger living owner without useful delta, is unsafe, or is
  internally incapable of the claimed role. The reason and revisit trigger
  are mandatory.
- `defer`: no current DAG consumer or sufficient evidence justifies adoption.
  Mere polish, completeness, novelty, or archive release status is not a
  consumer.

`stable` is prohibited in DS2. `beta` requires coherent archived behavior and
a real v4/Revision-2 consumer case but still carries missing repo evidence.
`experimental` is the default. `deprecated` is reserved for a consciously
retained item whose use is being strangled, not as a synonym for `reject`.

### Consuming-slice tests

The natural mappings are hypotheses to test, not automatic admissions:

- DS4: governed component/token package, state matrix, themes/modes;
- DS6: evidence infrastructure and continuous accessibility/performance
  verification;
- DS7: Cycle Board components and status-bearing board interactions;
- DS8: workspace, responsive dashboard, drill-down, print/export;
- DS9/DS12: reviewer/public security, privacy, content, and publication
  patterns;
- DS15: acquisition forms and refusal-with-a-path surfaces;
- DS16: data visualization for set-valued/incomparable value, uncertainty,
  provenance, and basis chips;
- DS18: epoch, freshness, revalidation, and stale-state chrome.

Items mapping only to an imagined surface outside DS3-DS18 are `defer`, not a
new slice request.

## D2 Token Decision Verification

D2 selected DTCG as the future authoring format unless DS2/DS4 proves it
cannot reproduce admitted live semantics or pass repo gates. DS2 performs the
static half of that test; it does not build the pipeline.

The parity inventory uses:

- every semantic token/key/alias and CSS-variable registry entry in the live
  `apps/runtime-dashboard/src/shared/ui/tokens/designTokens.ts`;
- live values and mode semantics in `styles.css`, `theme-light.css`,
  `theme-dark.css`, theme preferences, density preferences, and the frozen v4
  check/reference;
- every authored v15 DTCG root/mode file and its alias/output manifests.

Every v4 semantic token receives exactly one classification:

- exact semantic counterpart;
- representable rename/alias;
- representable value delta requiring an explicit migration decision;
- missing v15 counterpart;
- conflicting semantics;
- v4-only runtime preference/control rather than a token.

The report separately reconciles light, ADR-047 warm dark, system preference,
density, responsive, data-viz, high-contrast, contrast, and reduced-motion
semantics. It publishes both directions: v4-without-v15 and v15-without-v4.

The single D2 outcome is:

- `parity_achievable` when every admitted v4 semantic is exact or a lossless
  alias/rename;
- `parity_achievable_with_named_gaps` when DTCG can represent the semantics
  but explicit missing/conflicting values, modes, or repo-gate work remain;
- `parity_not_achievable` only when the format/pipeline model cannot represent
  an admitted live semantic or cannot plausibly satisfy a required gate.

Only `parity_not_achievable` fires D2's source-format revisit condition from
static evidence. Named content and integration gaps keep D2 but become exact
DS4 obligations. No token values migrate in DS2.

## Canonical Index, Machine Twin, And Human Projection

`architecture/atlas_surfaces/atlas-v15-adoption-ledger.json` is the canonical
logical-item index. Every entry satisfies the unchanged DS0 schema and carries
the archive path evidence, v4 disposition in its decision fields, consuming
slice, negative control, and authority boundary.

The per-item report table is generated from those ledger entries in stable-ID
order. Narrative sections may add analysis but may not create a verdict ID.
Closure compares IDs, verdicts, maturity, consuming slices, and source evidence
in both directions; empty set and value differences are required. A transient
generator is permitted only in scratch and its command/hash is journaled.

Schema validation uses:

```bash
uv run --with check-jsonschema check-jsonschema \
  --schemafile architecture/atlas_surfaces/adoption-ledger.schema.json \
  architecture/atlas_surfaces/atlas-v15-adoption-ledger.json
```

Negative probes copy the instance to scratch and must fail after each of:

- replacing one verdict with an unknown value;
- adding an unexpected property;
- changing the frozen archive hash;
- assigning `stable` without both browser and manual-AT evidence.

The unmodified instance must return `ok -- validation done`. These probes
prove contract strictness only; DS6 still owns behavioral CI validation.

## Phase-A Synthesis

`docs/reference/frontend/atlas-phase-a-synthesis.md` is a compact input
package for master-plan Revision 3. It does not duplicate the three source
artifacts. It links to:

- DS0 D1-D6 decisions and the pending-owner-ratification list;
- DS1 denominators, hotspot findings, ledger, and Plan-Impact Appendix;
- DS2 coverage, battery, verdict distribution, D2 outcome, family outcomes,
  and adoption ledger.

For each DS3-DS18 slice the synthesis records:

1. what Phase A confirmed;
2. what measured/adjudicated evidence re-scopes;
3. what Revision-2 assumption Phase A invalidated, or `none`;
4. the exact source links and denominator/verdict IDs;
5. the recommended Revision-3 action and relative effort direction.

The synthesis may recommend a re-cut but cannot renumber or rewrite the master
plan in DS2. The architect owns Revision 3.

## Pattern Pass

| Pattern | DS2 risk | Smallest correct control / acceptance signal |
| --- | --- | --- |
| P05 | an archive projection or polished state matrix occupies an authority slot | every row states `may_not_use_for`; status-bearing components require DS4 semantic binding |
| P06 | v4 and v15 become co-authoritative | every overlapping item names one target owner and one measurable loser sunset |
| P10 | archive PASS becomes runtime, browser, AT, or maturity proof | conformance battery limits each report's claim; no `stable` row |
| P13 | 1,612 files create 1,612 ceremonial decisions or attractive unused components create slices | physical-member map proves coverage; logical rows follow independent adoption semantics; no DAG consumer defaults to `defer` |
| P29 | hand-authored report counts self-attest to completeness | zip/member/unit/report/ledger sets are recomputed with empty differences; schema corruption probes fail |
| P31 | only the advertised 56 components or one report family is checked | inventory derives identities from all archive sources and adds unmapped named items as findings |
| P32 | presence of a PASS field grants admission | evidence must resolve to an archive member and its method/input; self-stamp remains archive-internal evidence |
| P33 | the frozen claims dictate the inventory | adversarial checks search for unlisted components, duplicate aliases, conflicting counts, generated-only items, and reports without raw inputs |
| P34 | an extraction/tool side effect is dismissed | pre/post repo status and scratch-only proof precede any exclusion |

DS2 produces decisions, not runtime capability. Every admitted item remains
`implemented_but_not_orchestrated` relative to production until its owning
slice supplies the missing bridge, consumer, verification, and negative test.

## Execution Checkpoints And Scoped Commits

1. **Task plan** — create this plan and unique journal; record clean branch,
   linked-worktree identity, exact archive hash, governing-source read, and
   scope; verify plan links and commit before extraction.
2. **Conformance battery** — extract to scratch, recompute physical/logical
   denominators, classify every verification report, create the report's
   coverage/battery sections, update the journal, and commit.
3. **Adjudication** — decide every token/component/pattern/package/doc row,
   map v4 counterparts and consuming slices, complete D2 static parity and
   family outcomes, update the report/journal, and commit.
4. **Ledger and synthesis** — populate the canonical adoption-ledger instance,
   mechanically project/check the report table, write DS3-DS18 Phase-A
   synthesis, update the archive README disposition pointer and journal, then
   commit.
5. **Closeout** — validate schema and negative probes, recompute coverage and
   report/ledger parity, resolve links, check the zip hash/immutability,
   re-run the pattern pass, prove the combined DS0-DS2 path fence and clean
   tree, mark artifacts review-ready, update the journal, and commit.

## Closure Contract

DS2 closes only when all conditions are true:

- [x] The committed plan and unique journal predate archive extraction and
      the task-plan checkpoint is committed.
- [x] The immutable zip still has the frozen sha256 and no extracted member is
      committed.
- [x] Every non-directory zip member maps exactly once to a logical unit;
      missing, duplicate, and extra physical-member sets are empty.
- [x] Every required dimension publishes a recomputed denominator,
      enumeration method, and `adjudicated N of N` or `classified N of N`
      statement.
- [x] The claimed component/Figma denominator is independently recomputed;
      discrepancies are findings rather than silently normalized.
- [x] Every archive verification report has a conformance-battery row stating
      what it proves, what remains missing, and DS4/DS6 ownership.
- [x] No archive PASS assigns `stable`; every maturity follows the
      constitution's evidence bar.
- [x] Every logical item has exactly one DS0 verdict, maturity, evidence,
      v4-counterpart outcome, consuming slice, loser sunset, strongest
      rejected alternative, revisit condition, `not_yet`, and authority
      boundary.
- [x] Every no-consumer item is `defer` unless the report cites a specific
      constitutional rejection reason.
- [x] The D2 parity map covers every live v4 token semantic and every authored
      v15 DTCG source/mode in both directions, including themes, density,
      responsive, data-viz, contrast/high-contrast, and reduced motion.
- [x] The D2 verdict is one of the three specified outcomes and either
      confirms D2 with named DS4 gaps or explicitly fires its revisit
      condition.
- [x] v4-vs-v15 outcomes cover all 12 DS1 families and name the winning owner,
      compatibility path, and loser sunset.
- [x] `atlas-v15-adoption-ledger.json` validates against the unchanged DS0
      schema; all four corrupt-instance probes fail validation.
- [x] Report and ledger IDs/decision fields have empty bidirectional
      differences and no duplicates.
- [x] The Phase-A synthesis covers DS3-DS18 with confirmed, re-scoped,
      invalidated, evidence, action, and effort fields.
- [x] All touched Markdown links and ledger evidence paths resolve; archive
      member paths resolve inside the verified zip/scratch extraction.
- [x] `git diff --check main...HEAD` is clean, every changed path is inside the
      combined DS0+DS1+DS2 fence, and `git status --porcelain` is empty.

Closure does not mean a component/token is copied, a package is created, a
pipeline is built, a v4 import is rebound, a browser/AT result exists, or any
production maturity claim is raised. Those remain with DS4/DS6 and the named
consuming slices.

## Targeted Verification

Closeout records exact commands and results for:

- frozen sha256 and zip member counts;
- scratch physical-member/logical-unit mapping set differences;
- JSON parseability, unique IDs, strict schema validation, and four negative
  probes;
- report↔ledger ID and decision-field parity;
- v4 token and v15 DTCG bidirectional parity denominators;
- all local Markdown links and ledger/archive evidence references;
- `git diff --check main...HEAD`;
- `git diff --name-only main...HEAD` against the explicit combined fence;
- `git status --porcelain`.

No pytest, application build, browser run, dependency install, generated
client, or token generation is part of DS2 verification.
