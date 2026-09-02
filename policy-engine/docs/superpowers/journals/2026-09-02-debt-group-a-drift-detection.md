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
