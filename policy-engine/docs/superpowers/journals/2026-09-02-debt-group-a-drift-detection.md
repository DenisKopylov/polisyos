# Debt Group A — drift detection and actionable measurement

Date: 2026-09-02  
Branch: `codex/debt-group-a-drift-detection`  
Base: `fac07ffc6`

This journal is append-only. `docs/plans/active/` was read for the five binding
closure signals and is not edited by this task.

## Provisioning receipt

- The provisioned worktree had neither `.venv` nor `node_modules`. Offline `uv sync`
  could not resolve uncached `jaxlib==0.8.2`, so the empty environment was preserved
  under ignored `_build/.tmp/debt-a2-empty-venv` and `.venv` was linked to the main
  checkout's Python 3.14 lock environment. This is a tooling non-receipt, not a
  product verdict.
- `corepack pnpm install --frozen-lockfile --ignore-scripts` completed from the
  frozen lockfile. All comparisons in this task use that same Python environment,
  local `node_modules`, and the provisioned read-only `production_data` link.
- Runtime invocations pin `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
  `PYTHONHASHSEED=0`, `JAX_PLATFORMS=cpu`, and `PYTHONPATH=src:.`.

## Seam 2 — owner-validator timeout classification and measured ceiling

Pattern pass: P37/P38 apply to the failure classifier. The property is whether the
owner rejected the source; the old implementation tested whether the child returned
a receipt before a stopwatch expired. Those predicates diverge when a healthy child
crosses 120 seconds.

Positive control before RED:

- Exact node
  `tests/unit/runtime/http/test_confidence_ledger_risk_spend_projection.py::test_real_owner_artifact_reaches_available_domain_projection`
  passed unchanged. `/usr/bin/time -p` reported `real 216.91`, `user 180.49`,
  `sys 8.38`; the node returned an available owner-admitted packet. This whole-node
  time is context only, not substituted for the child measurement.
- The debt-register measurement at `docs/plans/active/DEBT-REGISTER.md:324` records
  the healthy serialized owner-validator child at 92 seconds. The committed timing
  catalog now admits that literal as `owner-validator:default`, labels its regime
  `serialized`, and derives the executable ceiling as `2 × 92 = 184` seconds.

Accepted RED:

- Two exact nodes failed: the timeout test because
  `OwnerValidationTimeoutError` did not exist, and the budget test because the
  `owner-validator:default` measurement lane did not exist.

Implementation and GREEN:

- `subprocess.TimeoutExpired` is no longer converted to
  `ProjectionSourceValidation(status="failed")`. It raises the typed operational
  `OwnerValidationTimeoutError`, carrying the projection id and the 184-second
  measured ceiling. `OSError` and completed owner-validator failures retain their
  existing fail-closed governance paths.
- The DS17 OpenAPI example propagates that typed timeout unchanged. Its exception
  says `timed out` and cannot say `owner-admitted`; no second resolution is needed
  to learn which clock failed.
- Three focused behavioral nodes passed. The two focused timing-catalog tests also
  passed, including the source-excerpt binding for the 92-second sample. Targeted
  Ruff and `git diff --check` passed.

## Seams 1 and 5 — one content-bound staleness discipline

**Shared rule:** Every persisted output carries a canonical content-bound generation
basis; its consumer recomputes that basis before interpreting bytes and treats a
missing or mismatched basis as stale/incompatible.

Pattern pass: P07 is the replay requirement; P31 forbids three artifact-specific
patches; P37 requires a recomputed predicate at the accepting consumer; and P38
requires the measured identity to be the generation property rather than a nearby
proxy. The existing OpenAPI consulted-path digest and trust-posture source-set digest
retain their byte formulas and epochs. The new generic basis helper is additive and
is first adopted by the Academic snapshot boundary.

### OpenAPI consulted-path receipt

Positive control before RED: the existing generated-family manifest enforcement
test proved that a family which removes its required default-freshness declaration is
already rejected. The new exact manifest node then failed because
`runtime-openapi-snapshot.default_freshness_check` was false and no isolated output
probe existed.

Identically provisioned generator probes at detached base `fac07ffc6` and this
worktree both completed without traceback. The base generator consulted 6,277 paths
while the committed snapshot recorded 6,276; the current generator also consulted
6,277 and emitted a different receipt after the timeout seam changed a consulted
source. The count is diagnostic only: the compared object was the generated OpenAPI
byte output, and both sides were real git worktrees with the same linked Python,
`node_modules`, and read-only data provisioning.

The generated-artifact family now names the owner-validator consulted dependency
basis in its source of truth and freshness rule, and the default freshness run invokes
the canonical exporter into an isolated output root. Any consulted-path change that
changes the embedded receipt is therefore a mandatory byte-drift failure. The
committed OpenAPI is deliberately not regenerated here: this task did not change a
frozen OpenAPI source, generated client, schema, or receipt epoch. The exact new
manifest node and the synchronized generated-artifact reference are green.

### Trust-claim posture receipt

Positive control: before this seam changed a contributing source, the exact
`check_trust_claim_posture.py --check` invocation passed. Accepted RED: after the
source changes it raised `DS11-GENERATED-DRIFT`, rather than silently treating the
old source-set digest as current. The existing producer was then invoked with
`--write --write-generated-reference`; the source-set digest moved from
`sha256:30658cbeedfe7d85acc168b15d3046c48e21c1d705b5f968020a2154442ab2b1`
to
`sha256:d6bd0a819d69dc599fe3ca3f3da5609610b9f4573238a0b42fa4b66130942b07`.
An independent exact `--check` replay completed with `write_set: []` and exit 0.
This is the third adoption of the same rule, not a new receipt design.

### Academic SKG snapshot schema generation

Positive controls established that the canonical basis is order-independent and
byte-reproducible, and that changing row content after graph load leaves the
table/column schema identity unchanged. Accepted REDs then proved that the old path
had no receipt, that publish could otherwise mint currentness without a graph-stage
producer, and that a consumer accepted a dropped required table when only the code
basis matched.

The repaired chain is:

- graph load materializes and checkpoints the SKG, then records both a canonical
  generation basis over the exact `SKG_DDL` and ordered compatibility alters and a
  read-only identity over the materialized `ac_skg_%` table/column structure;
- publish carries the graph receipt verbatim, recomputes the live structural identity
  at `config.db_path`, and sets `schema_generation_current=false` for a missing,
  malformed, unreadable, incompatible, or swapped schema;
- the shadow consumer independently recomputes both identities before accepting
  readiness, names recorded/current generation and rule version in its drift warning,
  and forces `consumer_ready=false` on non-currentness.

The table-removal counterfactual now refuses at both publish and shadow. The positive
row-content mutation stays current, pinning the intended boundary: ordinary downstream
data evolution is not schema-generation drift. An independent read-only review found
no remaining false-current path in this chain. Nineteen focused tests plus the row
mutation control passed; targeted Ruff passed.

The historical April Academic fixtures and read-only production snapshot are not
retroactively blessed. They now report `recorded_generation=unrecorded` and
`schema_generation_current=false`, so the data requirement moves from `absent` to
`present_stale`; reissuing through the repaired producer is the named action that
moves the snapshot itself to current.

## Seam 4 — live TypeScript identity emission for the DS4 waist

Positive control before RED: the existing identity-mode behavioral test passed and
proved the census consumes DS5 owner-qualified TypeScript identities while treating
numeric lines as navigation only. Accepted RED: the new emitter test failed because
the census exposed no identity-emission API.

The census now has a surgical `--emit-present-projection-anchor ARTIFACT --record-id
ID` mode. It reads the declared canonical path, types path, and symbol from the
selected JSON record; reads both live TypeScript files; asks the already-loaded DS5
engine to resolve and mint an `exported_declaration` and the corresponding
`type_property`; takes each navigation line from that same AST match; and replaces
only the selected anchor object after a parsed-document equality guard. It contains
no TypeScript parser and no identity encoder.

The writer moved `ds4-waist-decision-grade` from `missing_export` to
`present_projection`, with live navigation lines 532 and 6,406. No identity was
typed, pasted, edited, decoded, or reconstructed by hand. A second invocation on
unchanged source left the complete governed artifact byte-identical: SHA-256
`ff36f7891031174fb44667f4f0ecf93359cf8b4a155433bcef291f1b13de0905` before and
after. The behavioral sensitivity control changed both referenced declarations and
observed both engine-minted identities change. The live waist replay independently
resolved and validated the two stored identities and passed.

Identically provisioned repository censuses before and after the write both produced
valid JSON and neither contained a traceback. Set comparison, not count comparison,
showed no additions and exactly these removals:

```text
anchor_absence_unexpected_presence:architecture/atlas_surfaces/ds4-waist-debt-register.json:/entries/1/generated_client_anchor:canonical:DecisionGrade
anchor_absence_unexpected_presence:architecture/atlas_surfaces/ds4-waist-debt-register.json:/entries/1/generated_client_anchor:schema:DecisionGrade
```

The raw counts moved 2,288 to 2,286 only as a checksum on that set result. The
remaining errors are preserved for the status-retirement inventory seam; the emitter
did not narrow the census or suppress an inherited entry.

## Seam 3 — actionable status-retirement measurement

Pattern pass: P31 requires fixing the false-anchor class rather than suppressing
2,277 instances; P35 requires the complete root population; P38 distinguishes a
generated-client anchor from an unrelated object that happens to use the words
`identity` or `line`; P40 required widening the first label-only repair when the same
class appeared one level deeper in source coordinates; and P41 requires the
identically provisioned before/after set comparison below.

Positive controls before RED were the live DS17 builder test, which still derived six
roles and its governed source facts, and the generic semantic-exemption removal test,
which already proved that deleting a registered fact makes its live definition red.
The first migration test was then red because no bounded transformer existed. The
initial label-only candidate exposed seven more false anchors: six DS17 declaration
`line` fields plus the aggregate line population. That was the second finding in the
same P38 class, so the mechanism was widened once from a DS18 label patch to the
complete non-anchor source-field invariant. The DecisionGrade presentation test was
separately red while the live scanner fact had no exact semantic registration.

The repaired invariant is: scanner labels and source coordinates persist under
neutral names; the generated-client census's reserved `identity` and `line` field
vocabulary occurs only on actual generated-client anchors. Concretely:

- current DS18 roots persist scanner `component_identity` as `component_name` and
  scanner `line` as `source_row`; the validator maps those fields back to the live
  scanner fact and still compares every root field;
- current DS17 declaration receipts persist `source_row` rather than a false anchor
  `line`;
- frozen DS18 historical lineage retains its legacy `component_identity` selector,
  because that selector participates in an immutable composite lineage identity; the
  lineage index admits either generation and rejects an object carrying both;
- `--migrate-non-anchor-source-fields` rewrites only those two current-artifact spans,
  rejects missing, dual, empty, or invalid fields, proves parsed equality to the
  exact expected key substitutions, validates the resulting schema, and is
  byte-idempotent. It is deliberately a bounded field migration, not a claim that
  the independent DS18 freshness validator is green.

The live artifact proof is byte-exact against the committed predecessor: 759 DS18
component labels, 759 DS18 source coordinates, and six DS17 declaration coordinates
changed; no other byte changed, parsed historical lineage is equal, and the resulting
artifact SHA-256 is
`55f8266837f07c751bd2fb2a86dac06217e5032d29273ce23c3b30091bdf97eb`.
Re-running the migration reports all three rename counts as zero and leaves that hash
unchanged. The live census now derives zero bindings from those DS17/DS18 source
facts and returns an empty error set for the complete document.

`decisionGradePresentationByOwnerGrade` is now registered by its exact live path,
declaration span, kind, type expression, and four sorted owner-grade members as
`non_status_taxonomy`. Its rationale is bounded: it is a private exhaustive map over
the generated owner vocabulary, preserves owner labels, and sends novelty to
`unrecognized`; it neither mints nor promotes frontend authority. Removing the row or
changing its member set is red.

The normal architecture aggregate remains intentionally unchanged in scope. It now
prints this exact line on both success and failure, so a lane cannot mistake an
aggregate pass for execution of the standalone gate:

```text
Standalone Atlas gate: architecture/atlas_surfaces/check_status_retirement_inventory.py is not run by `uv run polisyos-tools architecture guardrails check`; run it explicitly or through architecture/atlas_surfaces/check_atlas_enforcement.py.
```

Eight focused behavioral tests passed: the four builder/migration cases, the
non-anchor census counterfactual, the full live census, the content-bound
DecisionGrade registration, and the aggregate disclosure. A repeat of the actual
migration was byte-identical. The schema/current-artifact semantic diff was exact.

### Exact status-checker before/after sets

Both runs used the same worktree provisioning and pinned environment from this
journal. Both completed without traceback. The checker emits one finding per stderr
line, so the saved outputs were lexically sorted and compared with `comm -23` and
`comm -13`; no total was used to infer movement.

Let `A` be the literal artifact path
`architecture/atlas_surfaces/frontend-disposition-register.json`. Let `P` be the
lexically sorted set of JSON pointers obtained by traversing every current
`A#/ds18_time_semantics_coverage/files/i/roots/j` member and writing one pointer plus
LF. `P` has 759 unique members and SHA-256
`49c42a3e6110fa776f1a05b1ae54392201c87994275910c7e78496cd61a3a2cf`.
Let `Q` be exactly these six pointers:

```text
/ds17_confidence_ledger_risk_spend_surface/roles/0/declaration
/ds17_confidence_ledger_risk_spend_surface/roles/1/declaration
/ds17_confidence_ledger_risk_spend_surface/roles/2/declaration
/ds17_confidence_ledger_risk_spend_surface/roles/3/declaration
/ds17_confidence_ledger_risk_spend_surface/roles/4/declaration
/ds17_confidence_ledger_risk_spend_surface/roles/5/declaration
```

The removed set `R` is exactly the union of these expansions:

```text
{ generated_client_receipt_census:anchor_identity_slot_set_drift:A:p | p in P }
{ generated_client_receipt_census:typescript_identity_validation:A:p:component_identity:typescript_reference_identity_invalid | p in P }
{ generated_client_receipt_census:anchor_population_mismatch:A:p:primary=absent:independent=present | p in P union Q }
```

where `A` is expanded to the literal path above, plus exactly these seven lines:

```text
generated_client_receipt_census:anchor_identity_mode_mixed:architecture/atlas_surfaces/frontend-disposition-register.json
generated_client_receipt_census:anchor_identity_population_mismatch:architecture/atlas_surfaces/frontend-disposition-register.json:primary=0:independent=759
generated_client_receipt_census:anchor_line_population_mismatch:architecture/atlas_surfaces/frontend-disposition-register.json:primary=0:independent=765
inventory_source_hash_drift:architecture/atlas_surfaces/frontend-disposition-register.json
inventory_source_hash_drift:packages/runtime-api-client/canonicalRuntimeApiClient.ts
inventory_source_hash_drift:packages/runtime-api-client/types.ts
unregistered_semantic_definition:decisionGradePresentationByOwnerGrade
```

This expansion was generated independently from the current artifact and compared to
the literal `comm -23` output: the sets are equal. Its cardinality is
`759 + 759 + (759 + 6) + 7 = 2,290`, and its sorted LF-delimited SHA-256 is
`583e9be4689ef0aef847b1a8c6205db64966c6a3933be7b2674602f7aad2733d`.

The after set `F` is exactly these 49 lines:

```text
live_status_denominator_drift
registered_semantic_definition_missing:semantic-composer-mode-sections-tone
registered_semantic_definition_missing:semantic-explainability-card-explainability-level
registered_semantic_definition_missing:semantic-launch-run-page-tone
registered_semantic_definition_missing:semantic-rendered-value-state
registered_semantic_definition_missing:semantic-share-fixture-state
registered_status_definition_missing:status-inline-authz-provider
registered_status_definition_missing:status-inline-bureaucratic-block
registered_status_definition_missing:status-inline-bureaucratic-section
registered_status_definition_missing:status-share-trust-fixture
status_consumers_drift:status-inline-review-surface
unregistered_semantic_definition:ATLAS_AUTOMATED_RUNNER_PROFILES
unregistered_semantic_definition:ATLAS_CITED_SURFACE_READINESS_REPORT_SCHEMA
unregistered_semantic_definition:ATLAS_EVIDENCE_DENIED_USES
unregistered_semantic_definition:ATLAS_EVIDENCE_PAYLOAD_SCHEMA
unregistered_semantic_definition:ATLAS_EVIDENCE_RECEIPT_SCHEMA
unregistered_semantic_definition:ATLAS_EVIDENCE_STORAGE_CONVENTION
unregistered_semantic_definition:ATLAS_SURFACE_READINESS_PROJECTION_SCHEMA
unregistered_semantic_definition:ATLAS_SURFACE_READINESS_REPORT_SCHEMA
unregistered_semantic_definition:AuthorityPresentationRecognition
unregistered_semantic_definition:CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA
unregistered_semantic_definition:ConfidenceLedgerOwnerPacketSchema
unregistered_semantic_definition:ConfidenceLedgerProtectedAnswer
unregistered_semantic_definition:ConfidenceLedgerSafetyBlockedReason
unregistered_semantic_definition:EXECUTABLE_CLOSURE_PREFIXES
unregistered_semantic_definition:ExplainabilityLevel
unregistered_semantic_definition:REQUIRED_SUPPORT_PREDICATES
unregistered_semantic_definition:RUN_PAPER_AUTHORITY_NONRECEIPT_REQUIREMENTS
unregistered_semantic_definition:RenderedValueState
unregistered_semantic_definition:TRUST_AUDIENCE_KEYS
unregistered_semantic_definition:TRUST_COPY_KEYS
unregistered_semantic_definition:authorityPurpose
unregistered_semantic_definition:dispute
unregistered_semantic_definition:humanDecisionCoveragePresentationTones
unregistered_semantic_definition:humanDecisionGatePresentationTones
unregistered_semantic_definition:legalReviewPresentationTones
unregistered_semantic_definition:state
unregistered_semantic_definition:tone
unregistered_status_definition:AuthzProvider.tsx:status
unregistered_status_definition:acquisitionRoutePresentation.ts:status
unregistered_status_definition:atlasHonestyComprehensionProtocol.ts:observation_status
unregistered_status_definition:atlasManualAtMaturity.ts:evidence_status
unregistered_status_definition:atlasSurfaceReadinessReconciliation.ts:RouteAssertionStatus
unregistered_status_definition:bureaucratic-document-ast.ts:legal_review_status
unregistered_status_definition:bureaucratic-document-ast.ts:status
unregistered_status_definition:email-fixtures.ts:ShareTrustStatus
unregistered_status_definition:epochSemantics.ts:EpochProjectionStatus
unregistered_status_definition:opaqueBackgroundContrast.ts:status
unregistered_status_definition:trust-glyphs.ts:status
```

Its sorted LF-delimited SHA-256 is
`7e8fd4f5adc433fa0ee826ef539acbe0a54337941d600c9550146ffbe52fbc9f`.
The before set is exactly the disjoint union `F union R`: 2,339 lines, SHA-256
`c21f58118eed96cf0d0994e6abcec71a6daa09dad27c352a19636bcf982692c4`.
The after set is exactly `F`; `comm -13` is empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Thus the movement is 2,290 exact removals and no additions, not merely a smaller
total.

The independent DS18 freshness command is not claimed green by this repair. Its
current 17-line set (SHA-256
`b67629ec0b8b52caa4270350939fe76922c7de4d6889990e32648e7dddf60018`)
names the `Task-D-dashboard-freeze` landing slice, current RunReport/posture/
DecisionGrade source receipts, five RunReport behavioral receipts, and three count
receipts. It contains no diagnostic naming `component_name`, `source_row`,
`component_identity`, or a false `line` anchor. Under the existing lineage admission
rule, `Task-D-dashboard-freeze` owns that separate landing refresh. The governed
lineage schema has no typed non-closure-owner slot, so this task did not invent one or
use that residual to waive any member of `R`.

## Shared-rule precision

The earlier shared-rule sentence described the Academic consumer shape too
specifically for all three mechanisms. The exact one-line rule, superseding that
wording, is: **Recompute canonical generation inputs and reject a persisted output as
stale when either its content-bound receipt or its complete generated bytes differ.**
OpenAPI enforces this with an isolated output comparison, trust posture with its
source-set receipt replay, and Academic SKG with producer/publish/consumer generation
and materialized-schema comparison. This is one staleness policy with three existing
boundary-appropriate mechanisms, not a claim that all three import one helper.

## Exact append-only prose for architect transcription

No seam remains blocked. The following paragraphs are transcriber-ready additions to
the five existing rows; they do not ask the architect to infer a status from this
journal.

### `owner-validator-120s-child-timeout-is-load-variable`

**TASK A 2026-09-02 — `open` -> `closed`.** The stopwatch and governance verdict are
now different typed outcomes. A child that crosses its budget raises
`OwnerValidationTimeoutError`, names the projection and ceiling, and propagates
through the DS17 OpenAPI example without saying `owner-admitted`; completed owner
refusals and `OSError` retain their existing fail-closed admission paths. The checked-in
serialized measurement record contains one admitted 92-second sample and is
test-bound to an executable ceiling of `2 × 92 = 184` seconds; the runtime derives the
ceiling from that admitted sample rather than retaining the marginal 120-second
literal. Focused timeout, propagation, budget-binding, and real-owner positive
controls pass. Closure signal discharged: the failure says timeout without a second
resolution, and the ceiling is bound to the recorded healthy measurement.

### `openapi-example-receipt-stale-on-any-consulted-path`

**TASK A 2026-09-02 — `open` -> `closed`.** The class rule is: recompute canonical
generation inputs and reject a persisted output as stale when either its content-bound
receipt or its complete generated bytes differ. `runtime-openapi-snapshot` now has a
mandatory default freshness check that runs the canonical exporter into an isolated
output root; any consulted-path movement that changes the embedded owner-validator
receipt changes the generated bytes and blocks freshness acceptance until
regeneration. The pre-existing trust-posture source-set replay and the new Academic
producer/consumer generation-basis comparison enforce the same policy at their
respective boundaries. The probe was proven on identically provisioned real git
worktrees and no
receipt epoch, OpenAPI source, generated client, or schema was changed. Closure signal
discharged: consulted-set movement now forces regeneration, and the class was decided
once rather than patched per artifact.

### `snapshot-records-no-schema-generation`

**TASK A 2026-09-02 — `open` -> `closed`.** Academic graph production now records a
canonical `policyos.academic.skg_schema_generation.v1` basis over the exact SKG DDL
and ordered compatibility alters plus the read-only identity of the materialized
`ac_skg_%` table/column structure. Publish carries the producer receipt verbatim and
compares both the live code basis and live materialized schema; shadow independently
recomputes both before setting `consumer_ready`. Missing, malformed, unreadable,
swapped, or table-dropped snapshots fail closed with
`recorded_generation` and `current_generation` named, while a row-content-only change
stays current. Historical snapshots remain honestly `unrecorded`/`present_stale` until
the repaired producer reissues them. Closure signal discharged: schema drift is now
reported as drift with both generations named, rather than surfacing as an absent
table.

### `ds4-waist-anchor-declares-absence-of-a-present-symbol`

**TASK A 2026-09-02 — `open` -> `closed`.** The census now exposes
`--emit-present-projection-anchor`; it reads the declared symbol and both live
TypeScript sources, delegates both matches to the existing DS5 v1 identity engine,
and writes `canonical_line`, `canonical_identity`, `schema_line`, and
`schema_identity` together in the same surgical artifact update. The writer contains
no TypeScript parser or identity encoder. It moved `ds4-waist-decision-grade` to
`present_projection` at live lines 532 and 6,406; a repeat on unchanged sources was
byte-identical, fixture declaration changes changed both engine-minted identities,
and the committed identities independently validate against the live declarations.
No identity was typed, pasted, decoded, edited, or reconstructed by hand.
`decisionGradePresentationByOwnerGrade` is separately content-bound as the exact
four-member, generated-owner-derived `non_status_taxonomy`; deleting or drifting that
registration is red. Closure signal discharged: the status checker has neither
DecisionGrade absence finding nor that unregistered semantic finding, and the waist
entry carries the emitter-produced present projection.

### `status-retirement-inventory-red-beyond-acting-and-outside-the-lane-guardrail`

**TASK A 2026-09-02 — `open` -> `closed`.** The 2,277 false DS18 findings were repaired
as one P38 class, not suppressed: all 759 current roots now persist scanner labels and
coordinates under neutral `component_name`/`source_row` fields while the validator
still reconciles every value to live scanner `component_identity`/`line`; frozen
lineage selectors remain byte-preserved. The same invariant removed six DS17 false
line anchors. Identically provisioned, traceback-free set comparison is exact:
before = 2,339 findings at
`c21f58118eed96cf0d0994e6abcec71a6daa09dad27c352a19636bcf982692c4`;
after = the 49-line set printed in this journal at
`7e8fd4f5adc433fa0ee826ef539acbe0a54337941d600c9550146ffbe52fbc9f`;
removed = 2,290 at
`583e9be4689ef0aef847b1a8c6205db64966c6a3933be7b2674602f7aad2733d`;
added = empty. The exact removed-set expansion and complete after set are recorded
above. The lane aggregate now states in one line that it does not run the standalone
checker and gives both actionable invocations. A separate 17-line DS18 landing-refresh
set remains explicitly attributed to `Task-D-dashboard-freeze` and was not used as a
waiver. Closure signal discharged: the inherited 2,277 are repaired, the remaining
status set is small and explicit, and the normal lane guardrail can no longer imply
that this checker ran.

## Pre-commit verification receipt

- The final targeted wave selected 33 exact nodes spanning the timeout classifier,
  OpenAPI output probe, Academic generation basis and producer/consumer chain, live
  identity emission/replay, neutral source-field migration, complete live census,
  DecisionGrade semantic registration, and aggregate disclosure. All 33 passed.
- Diff-scoped Ruff over the six row-3 Python files reported zero findings on added or
  modified hunks. The raw whole-file scan still reports 780 pre-existing findings, so
  no whole-file lint green is claimed. `git diff --check` passed.
- Independent review confirmed that the live scanner denominator is unchanged, every
  current stored DS18 field is reconciled back to its live scanner field, all 759
  current roots are migrated, and the frozen lineage selector population remains
  compatible. The review's certification caution is recorded above: the migration
  transforms and schema-checks its bounded fields; the separate DS18 freshness gate
  remains separately visible and owned.
