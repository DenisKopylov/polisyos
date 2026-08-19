---
plan_id: atlas-ds0-source-of-truth-freeze-and-governing-decisions
title: "DS0 - Source-Of-Truth Freeze & Governing Decisions"
type: slice-plan
status: complete-on-branch; D4 ratified 2026-07-16 and amended by D4-A1 2026-08-19
created: 2026-06-11
revised: 2026-08-19
last_verified: 2026-08-19
stability: review-ready
closed_at: 2026-07-16
slice: DS0
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
gy_execution_plan: ../layer3-slices/GY-engine-subordination.md
audiences: [MACHINE, EXPERT]
backend_co_owner: none
feature_flags: none
depends_on:
  - ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
  - ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
  - ../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - ../../../reference/policy-design-case-failure-patterns.md
  - ../../../reference/frontend/workspace-contract.md
  - ../../../../design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
  - ../../../brand/ATLAS_DESIGN_SYSTEM.md
  - ../../../brand/ATLAS_V4_ADOPTION.md
  - ../FRONTEND_SOTA_PLAN.md
  - ../DESIGN_BEST_IN_CLASS_PLAN.md
  - ../POLICYOS_ATLAS_PRODUCT_MARKETING_CLIENT_SURFACES_MASTER_PLAN.md
  - ../POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
---

# DS0 - Source-Of-Truth Freeze & Governing Decisions

## Revision 2 Reconciliation

This executable spec is reconciled to Revision 2 of the
[Atlas Surface Implementation Master Plan](../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md)
as of 2026-07-16. Revision 2 explicitly clears Phase A (`DS0`-`DS2`) to run
now and replaces the old G-naming dependency story with the GY input contract
and start-now ladder. DS0 remains GY-independent: it may cite the active
[GY execution plan](../layer3-slices/GY-engine-subordination.md), but it does
not read from, write to, or wait on the GY worktree.

The prior 2026-06-11 version over-scoped DS0 into a repo-quality validator,
tests, generated-reference plumbing, and a readiness manifest. Revision 2's
closure is narrower: **governing decisions plus two strict ledger schemas,
one valid example instance for each, and a trivial in-fence self-validation**.
Nothing is silently dropped; the reassignment table below names the later
slice that owns every moved-out deliverable.

The prior locale choice is not treated as a ratified product decision. It
predates the surface constitution's jurisdictional-surface posture and was
never owner-ratified under the current decision contract. DS0 therefore
records an evidence package, recommendation, alternatives, and
`pending_owner_ratification`; an agent does not finalize `ru` retention.

## Mission And Boundary

DS0 is the surface analogue of a discipline freeze. It decides which sources
govern Atlas work, where future artifacts belong, and which controlled
vocabularies later slices must reuse. It does not audit the live application
(`DS1`), adjudicate v15 contents (`DS2`), migrate tokens or components
(`DS4`), implement flag enforcement (`DS5`), or ship a route, component,
package, runtime producer, or public claim.

The current roadmap contains **19 slices, `DS0` through `DS18`**. The DAG and
GY gates in the master plan govern ordering; numeric order alone does not.
References to the former G0-G8 campaign are historical. The active upstream
vocabulary is GY (`GY-N10`, `GY-N13a`, `GY-N13b`, `GY-N11`, `GY-N12`, and the
Phase-6 O-block).

## Closure Contract

DS0 closes only when all of the following are true:

- [x] One short, dated, owned Atlas source-of-truth decision record contains
      D1-D6. Every decision includes evidence, the strongest rejected
      alternative, and a concrete revisit condition.
- [x] D1 resolves the living coded v4, v4 brand documents, the v7 surfaces
      plan, and the sha256-pinned v15 archive. It records what is superseded,
      what is retained, and what DS2 still must adjudicate.
- [x] The active GY plan is recorded as the Layer-3 owner; the historical
      G-naming Layer-3 plan is retained but explicitly superseded in practice,
      without deletion or edits under `layer3-slices/**`.
- [x] `FRONTEND_SOTA_PLAN.md` and `DESIGN_BEST_IN_CLASS_PLAN.md` are archived
      through ADR-0126's `docs/plans/archive/` lifecycle, with narrow active
      disposition stubs retained where needed for link continuity.
- [x] The v7 surfaces plan is retained as a DS11-DS13 material source but is
      no longer an execution master.
- [x] D2 chooses one token source of truth and gives the losing path an owner,
      sunset condition, and compatibility posture.
- [x] D3 chooses the package home, release/versioning policy, and Figma
      source-vs-projection status with parity ownership.
- [x] D4 records the `en`/`uk`/`ru` evidence, alternatives, recommendation,
      RTL posture, and owner, with status `pending_owner_ratification`.
- [x] D5 inventories all 12 manifest-driven flags with owner, intent,
      sunset/review condition, shadow-shipping role, and one governed source
      path; implementation remains DS5.
- [x] D6 gives every named non-web artifact a named slice or an explicit
      `surface_out_of_scope` disposition with owner and revisit condition.
- [x] `architecture/atlas_surfaces/` contains two Draft 2020-12 JSON Schemas
      and one valid example instance for each: adoption ledger and surface
      readiness ledger.
- [x] The adoption example carries the v4/v7/v15 source-disposition entry set
      and pins the v15 sha256
      `28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969`.
- [x] The readiness example represents all 19 Revision 2 slices and uses only
      the master plan's controlled vocabularies.
- [x] The two examples validate against their schemas with the in-fence
      self-validation commands; no DS6 CI-validator claim is made.
- [x] All links in touched Markdown resolve, `git diff --check` is clean, and
      `git diff --name-only main...HEAD` proves the path fence.

Closure is review-ready rather than merged. The one unresolved product choice
is intentionally not a DS0 blocker: D4's evidence package is complete and its
policy result remains `pending_owner_ratification`, exactly as required.

## Binding Path Fence

Work occurs only in the isolated worktree on
`codex/atlas-ds0-source-of-truth`. Writable paths are:

- `docs/brand/**`;
- `docs/plans/active/atlas-slices/**`;
- the frontend-family plans named `POLICYOS_ATLAS_*`,
  `FRONTEND_SOTA_PLAN.md`, and `DESIGN_BEST_IN_CLASS_PLAN.md`;
- `docs/archive/**` for lifecycle notes;
- `design/**` for disposition notes only;
- new `architecture/atlas_surfaces/**`;
- exception: `docs/plans/archive/**`, for the two lifecycle moves and their
  disposition notes only;
- exception: exactly one new journal,
  `docs/superpowers/journals/2026-07-16-atlas-ds0-source-of-truth.md`.

`apps/**`, `packages/**`, and `src/**` are read-only evidence. The GY blast
zone remains forbidden: `docs/plans/active/layer3-slices/**`,
`architecture/policy_design_case/**`, `tools/quality/**`, and
`production_data/**`. If a necessary change falls outside this fence, DS0
stops and reports it.

## Governing Decisions

All six decisions live together in one canonical Atlas decision record. A
decision is incomplete without rejected alternatives and a revisit condition.

### D1 - Canonical source, supersession, and docs lifecycle

Decide the canonical relationship among:

- the living coded v4 in `apps/runtime-dashboard/src/shared/ui/**` and
  `designTokens.ts`;
- v4 brand documents `ATLAS_DESIGN_SYSTEM.md` and `ATLAS_V4_ADOPTION.md`;
- the v7-based Atlas product/marketing/client surfaces plan;
- the v15 archive, sha256-pinned and currently
  `implemented_but_not_orchestrated`;
- the surface constitution and Revision 2 master plan.

The decision must preserve a working live baseline while preventing competing
canonical owners. It must say exactly which v15 content DS2 will adjudicate
and must leave ADR-047 in force unless a later ADR process supersedes it.

The same cluster records these lifecycle dispositions:

- archive the two vision-superseded frontend plans;
- retain the v7 plan only as DS11-DS13 material;
- identify `layer3-slices/GY-engine-subordination.md` Rev 17 as the active
  Layer-3 plan;
- retain the historical G-naming plan as historical context, explicitly
  superseded in practice by the GY plan, and never delete it.

### D2 - Token pipeline

Choose one token source format and generation direction. The evidence decision
must distinguish **format/pipeline authority** from **token-content
adjudication**: DS0 may choose the pipeline, while DS2 still decides which v15
token values are admitted. Record the losing path's sunset condition and
compatibility owner to close master-plan tension T6.

### D3 - Package home, versioning, and Figma

Choose the future package home (expected candidate: `packages/atlas-ui`),
whether it is private or published, the version and release policy, and whether
Figma is a source or a projection. Name the owner and acceptance signal for
code/Figma parity. DS0 creates no package.

### D4 - Locale and i18n posture (`ratified`, later amended)

**Supersession notice:** this section is the 2026-07-16 decision-preparation
contract. The owner subsequently ratified D4 and Atlas Revision 3.19 amended
it as D4-A1 on 2026-08-19: `en` is the authored primary, `uk` is its
translation, and `ru` remains `legacy_continuity_frozen`. The historical
preparation requirements below are retained as evidence, not current posture.

Prepare, but do not ratify, the product decision for existing `en`, `uk`, and
`ru` locales. Evidence must cover current key parity, fallback behavior,
Ukraine-facing jurisdictional posture, user continuity, ongoing translation
obligation, and public-surface consequences. Include at least:

- recommended option;
- retain-all-three alternative;
- frozen-but-served alternative;
- remove-or-depublish alternative;
- RTL posture and trigger;
- named product owner and explicit ratification field.

The owner acted; no D4 owner-ratification gate remains open.

### D5 - Feature-flag governance

Record the 12 manifest-driven flags with owner, intent, and sunset/review
condition. Choose one governed registry path and define `/auth/me` overrides
as a projection or authorized evaluation result of that registry, never a
second flag vocabulary. State how flags carry DS4/DS5 shadow shipping.
Implementation, linting, and source collapse remain DS5.

### D6 - Non-web surface dispositions

Dispose every named artifact without turning brand specs into claimed
capabilities:

- `packages/cli` styleguide exports;
- `EMAIL_TEMPLATES.md`;
- `PRINT_AND_EXPORT.md`;
- `CLI_STYLEGUIDE.md`;
- `BUREAUCRATIC_RENDERING.md`;
- `GLYPH_SPECIFICATION.md`;
- `MOTION.md`;
- `A11Y_CONTRAST.md`.

Each row names a consuming slice or uses `surface_out_of_scope` with an owner
and revisit condition.

## Ledger Schemas And Examples

The canonical schema home is `architecture/atlas_surfaces/`. DS0 creates only:

| File | Purpose |
| --- | --- |
| `adoption-ledger.schema.json` | Strict adoption-entry contract; closed adoption verdict, maturity, source-disposition, evidence-kind, and audience vocabularies. |
| `adoption-ledger.example.json` | Valid D1 source-disposition set for living v4, v4 docs, v7 material, and v15 evidence source. It is not DS2 component adjudication. |
| `surface-readiness-ledger.schema.json` | Strict readiness-entry contract using Revision 2 readiness, maturity, provenance, audience, and capability-link vocabularies. |
| `surface-readiness-ledger.example.json` | Valid 19-slice roadmap example, honest about DS0 and every `not_yet` claim. |

Both schemas use Draft 2020-12, set `additionalProperties: false` at every
object boundary, require ownership, dates, evidence/reason, rejected
alternatives where a decision is embedded, and keep controlled vocabularies in
`$defs` so later consumers reference rather than re-derive them.

The examples are self-validated without adding a validator to the repo:

```bash
uv run --with check-jsonschema check-jsonschema --schemafile architecture/atlas_surfaces/adoption-ledger.schema.json architecture/atlas_surfaces/adoption-ledger.example.json
uv run --with check-jsonschema check-jsonschema --schemafile architecture/atlas_surfaces/surface-readiness-ledger.schema.json architecture/atlas_surfaces/surface-readiness-ledger.example.json
```

These commands establish schema/example consistency only. They do not claim
the behavioral CI validation owned by DS6.

## Reassigned Deliverables From The 2026-06-11 Spec

| Prior DS0 deliverable | New owner | Why / closure signal |
| --- | --- | --- |
| `check_atlas_surface_ledgers.py`, corruption cases, repo-quality tests, and CI-tier registration | **DS6** | DS6 owns the evidence workflow and the readiness-ledger CI validator. Its negative proves an unsupported `implemented` claim fails. |
| Computed DS0 readiness manifest and fail-closed issue-code machinery | **DS6** | Fold into the generic readiness validator; do not create a DS0-only governance island (P13/P30). |
| Generated human projection, projection-parity test, generated-artifact registry entry, and generated reference refresh | **DS6** | Land when the generic validator/producer exists; generated references must follow the real source, not a hand-authored DS0 packet (P29). |
| HTTP producer/export for the readiness ledger | **DS3** | DS3 owns runtime producers and export infrastructure; it projects this schema without re-deriving authority. |
| Token/component migration and creation of the package home | **DS4** | DS4 rebinds and migrates the design-system substrate after DS2 verdicts. DS0 records direction only. |
| Feature-flag manifest implementation, dual-source collapse, registry lint, and client enforcement | **DS5** | DS5 owns the enforcement waist and app-code changes. |
| Locale parity/fallback code changes | **DS5** | DS5 owns mechanical enforcement after owner ratification; DS12 implements the ratified public-locale posture at its constitutional gate. |
| Any `apps/**`, `packages/**`, or runtime source edit implied by the old defaults | **DS4/DS5** | App-code work is explicitly outside DS0 and lands in the relevant migration or enforcement slice. |

## Pattern Pass

| Pattern | Existing risk | Smallest correct pattern / acceptance signal |
| --- | --- | --- |
| P04 | a UI-local readiness or maturity vocabulary forks runtime truth | schemas close over the master plan's values; an unknown value fails JSON Schema validation |
| P05 | archive polish or Figma state is presented as authority | v15 stays `implemented_but_not_orchestrated`; examples declare purpose and `not_yet` limits |
| P06 | v4/v7/v15 and G/GY documents compete as canonical owners | one D1 record names canonical, retained, superseded, and pending-adjudication roles |
| P10 | archive reports are mistaken for runtime/accessibility evidence | archive evidence cannot by itself support `stable` in the adoption schema |
| P13 | DS0 grows a bespoke validator/governance subsystem | only two schemas, two examples, one decision record, and lifecycle dispositions ship |
| P26 | an agent silently settles a politically sensitive locale question | D4/D4-A1 remain explicit owner decisions with alternatives and a named owner; agents implement but do not choose them |
| P29 | examples self-attest to readiness | self-validation proves shape only; DS6 owns behavioral recomputation and claim checking |

Missing capability labels at DS0 close are intentional and precise: schemas
are `contract_only`; DS3 owns their producer/bridge, DS6 owns verification,
and later slices own consumers and surfaces. DS0 must not round them up to
`implemented`.

## Execution Checkpoints

1. **Spec reconciliation** - amend this plan against Revision 2 and commit it
   with the unique DS0 journal before executing any decision.
2. **Evidence and decisions** - inspect allowed/read-only sources; record D1-D6
   and the adoption source set; commit the cluster.
3. **Docs lifecycle** - archive the two legacy plans, leave narrow disposition
   stubs as needed, and record v7 plus historical G-plan dispositions; commit.
4. **Schemas and examples** - add the two strict schemas and valid examples;
   self-validate and commit.
5. **Closeout** - resolve touched-doc links, rerun the pattern pass, prove the
   fence and clean diff, update the same unique journal, and commit.

No checkpoint runs pytest, an application build, or browser tests. Nothing is
merged; the branch remains for architect review.
