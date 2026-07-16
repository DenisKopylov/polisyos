---
title: Atlas DS0 Source-Of-Truth Freeze Journal
status: active
owner: team-design
created: 2026-07-16
branch: codex/atlas-ds0-source-of-truth
worktree: .worktrees/atlas-ds0
---

# Atlas DS0 Source-Of-Truth Freeze Journal

This is the only journal created or edited by DS0. It records checkpoints on
the isolated Atlas branch and deliberately does not share a filename with the
parallel GY audit.

## 2026-07-16 - Revision 2 reconciliation

- Created the mandatory isolated worktree from `main` at commit `6be25b872`.
- Read, in order, the Revision 2 master plan, the surface constitution, and the
  prior DS0 executable spec before editing.
- Read `CONTRIBUTING.md`, ADR-0126, and the failure/repair register.
- Reconciled DS0 to the Revision 2 start-now ladder, GY vocabulary, and the
  19-slice (`DS0`-`DS18`) DAG.
- Removed no obligation silently: out-of-fence validator, test, generated
  reference, runtime, and app-code work is reassigned explicitly to DS3,
  DS4, DS5, DS6, or DS12.
- Restored the `ru` retention question to an evidence-backed recommendation
  with `pending_owner_ratification`; the earlier choice predates the current
  jurisdictional posture and was not ratified under this contract.
- Recorded the two narrow fence exceptions granted by the owner:
  `docs/plans/archive/**` for lifecycle moves and this one unique journal.

Next checkpoint: gather read-only evidence and record the six governing
decisions without touching application or GY-owned paths.

## 2026-07-16 - Governing decisions D1-D6

- Completed three parallel read-only evidence passes inside the DS0 worktree:
  design/token/package sources, locale/flags, and lifecycle/non-web surfaces.
- Recorded one canonical decision register at
  `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`; it carries evidence, the strongest
  rejected alternative, and revisit conditions for every decision.
- Kept live v4 as the transitional production baseline; v7 is DS11-DS13
  material only; v15 remains sha-pinned `implemented_but_not_orchestrated`
  evidence pending DS2 item-level adjudication.
- Chose future one-way DTCG generation without admitting v15 values; reserved
  private `@polisyos/atlas-ui` at `packages/atlas-ui`; made Figma a projection.
- Restored D4 to `pending_owner_ratification`. Snapshot evidence found 2,449
  string leaves per locale, but 80.16% of `ru` values equal English and the
  runtime advertises only `en`/`uk`.
- Governed all 12 declared flags; recorded four as `consumer_missing` and
  separated rollout from `/auth/me` authorization.
- Assigned each non-web artifact to DS2/DS3/DS4/DS6/DS8 or explicit
  `surface_out_of_scope` with an owner and revisit trigger.

Next checkpoint: execute the docs-lifecycle moves and update the retained
source documents to point at the new canonical decision record.

## 2026-07-16 - Docs lifecycle and source dispositions

- Followed ADR-0126 plus the active/archive bucket READMEs. Moved the complete
  legacy plans under their original filenames to `docs/plans/archive/` and
  marked them superseded/archived.
- Left narrow active-path stubs because inbound references exist outside the
  DS0 fence. The design stub preserves exact `#f3` and `#f4` anchors used by
  publication-packet provenance in app code.
- Reclassified the v4 design-system and adoption docs as retained live-baseline
  evidence, not governing sources. ADR-047 remains in force; the historical
  local-download path is explicitly non-replayable DS2 debt.
- Marked the v7 surfaces plan superseded for execution and retained only for
  DS11-DS13. Recorded the historical G plan centrally as retained context with
  no execution authority; its protected file was not edited.
- Updated the v15 wrapper: DS0 freezes its evidence-source role, DS2 owns
  item-level adjudication, and DS4 owns any migration.
- Rebound the Revision 2 master plan and brand index to the canonical DS0
  record without editing the read-only surface constitution.

Next checkpoint: define the two strict ledger schemas and their valid example
instances under `architecture/atlas_surfaces/`.

## 2026-07-16 - Ledger schemas and examples

- Added two strict Draft 2020-12 schemas: adoption ledger and surface
  readiness ledger. Shared audience, maturity, authority, and slice
  vocabularies are defined in the readiness schema and referenced by the
  adoption schema.
- Added one valid instance per schema. The adoption instance carries four
  source dispositions and pins the v15 hash; the readiness instance contains
  exactly `DS0`-`DS18`, all honestly `contract_only` and `fixture_only`.
- `check-jsonschema` metaschema and instance validation pass for both files.
- Negative probes reject an unknown adoption verdict, a UI-only readiness
  state, and `stable` maturity backed only by archive/document evidence.
- Recomputed the archive sha256 from the worktree and matched
  `28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969`.

Next checkpoint: reconcile final cross-links, close the pattern pass, and prove
the branch path fence against `main`.
