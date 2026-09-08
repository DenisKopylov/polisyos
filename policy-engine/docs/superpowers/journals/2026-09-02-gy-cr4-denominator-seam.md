# GY-CR4 Phase-2 journal — denominator seam

Date: 2026-09-02
Branch: `codex/gy-cr4-denominator-seam`
Branch ref: `refs/heads/codex/gy-cr4-denominator-seam`
Phase-1 plan:
`docs/superpowers/plans/2026-09-02-gy-cr4-denominator-seam.md`
Slice base: `0413953e25a9efbba1521022156be3138dd855f6`
Source/tests freeze: `c442e5db93da9442f545b6aa9355e0167f7803ee`
Freeze tree: `d1909c4eb79fae44e475f9a675ab2cdf031da7a2`

The user ratified close (a): preserve Runtime's complete epoch-transition input population and
Scientist's current decision-impact population as two different claims, then relate them through
an additive, exact, content-bound reconciliation receipt. Canonicalization close (b) remains
rejected because it would erase one completeness claim. Phase 2 expressly authorized only the
additive governed sidecar and its write-once admission binding. Existing v1 receipt bytes and
meanings, the frozen C4 profiles, OpenAPI, generated clients, dashboards, all other schemas, and
all existing predicates remained untouchable.

## 1. Source/tests freeze and path receipt

The frozen commit was read back from the attached branch with a clean tree:

```bash
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine symbolic-ref -q HEAD
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine status -sb
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine rev-parse HEAD
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine rev-parse HEAD^{tree}
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine diff --name-status 0413953e25a9efbba1521022156be3138dd855f6..c442e5db93da9442f545b6aa9355e0167f7803ee
```

Observed: branch ref as above; clean `## codex/gy-cr4-denominator-seam`; commit and tree as above.
The complete changed-path set was:

Mechanism:

- `src/polisyos/core/contracts/__init__.py`
- `src/polisyos/core/contracts/decision_validity.py`
- `src/polisyos/runtime/quality/derived_observations.py`
- `src/polisyos/runtime/quality/epoch_denominator_reconciliation.py` (added)
- `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- `src/polisyos/scientist/validation/decision_validity.py`

Tests:

- `tests/unit/runtime/quality/test_derived_observations.py`
- `tests/unit/runtime/quality/test_epoch_validity_cascade.py`
- `tests/unit/scientist/evidence/claims/test_head_index.py`
- `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py`
- `tests/unit/scientist/validation/test_decision_validity_service.py`

Mandatory record companions, excluded from the mechanism count under P39:

- `docs/superpowers/plans/2026-09-02-gy-cr4-denominator-seam.md`
- `architecture/public_surface/inventory.json`
- `docs/reference/public-surface.md`
- `release-fragments/unreleased/2026-09-02-gy-cr4-denominator-reconciliation.toml`
- `src/polisyos/core/contracts/README.md`
- `src/polisyos/runtime/quality/README.md`
- `src/polisyos/scientist/validation/README.md`
- this append-only journal companion, written only after the source/tests freeze

Unexpected paths: none. No `docs/plans/active/**` path changed.

## 2. Capability-chain receipt

The implemented, injected seam is:

```text
authentic exact Runtime transition bytes
  -> exact Scientist owner snapshot
  -> Runtime reconciliation producer persists an additive sidecar
  -> exact reader re-resolves transition, snapshot, Runtime target members, receipt bytes,
     manifest inputs, and appointed verifier provenance
  -> write-once Scientist admission binding freezes the exact sidecar handle before pending state
  -> Decision-Validity first admission consumes the frozen relation
  -> restart/replay resolves the bound handle and ignores a later valid live candidate
```

The additive public Core contracts are
`DecisionValidityEpochImpactOwnerRow`, `DecisionValidityEpochImpactTarget`,
`DecisionValidityEpochImpactSnapshot`, `DecisionValidityEpochImpactSnapshotHandle`,
`PersistedDecisionValidityEpochImpactSnapshot`, `EpochTransitionDenominatorMappingRow`,
`EpochTransitionDenominatorReconciliationReceipt`,
`EpochTransitionDenominatorReconciliationHandle`,
`PersistedEpochTransitionDenominatorReconciliation`,
`EpochDenominatorReconciliationAdmissionBinding`, and
`EpochTransitionDenominatorReconciliationReader`. Runtime adds the concrete producer and reader
plus `EpochDenominatorReconciliationNonReceipt`.

The Scientist snapshot uses schema `polisyos.decision-validity.epoch-impact-snapshot.v1`, artifact
kind `scientist.decision_validity_epoch_impact_snapshot`, media `application/json`, manifest schema
version `1.0`, and canonicalization `polisyos.canon.json/0.2.0`. The reconciliation receipt uses
schema and rule `polisyos.epoch-transition-denominator-reconciliation.v1`, kind
`polisyos.epoch.transition_denominator_reconciliation_receipt`, media
`application/vnd.polisyos.chronology+json`, manifest schema version `1.0`, canonicalization
`polisyos.canon.json/0.2.0`, and predicate `independently_reconciled`. The local write-once binding
uses schema `polisyos.decision-validity.epoch-reconciliation-admission-binding.v1`, the same rule
and canonicalization, and freezes transition, snapshot, denominator, provenance, and receipt
coordinates before pending state.

Observed failure/non-receipt codes include `epoch_denominator_membership_mismatch`,
`epoch_denominator_reconciliation_unavailable`, `epoch_denominator_reconciliation_unresolved`,
`epoch_denominator_reconciliation_ambiguous`, and
`epoch_denominator_reconciliation_admission_conflict`. No existing v1 field was reinterpreted.

Production boundaries remain explicit: no production `EpochValidityTransitionProducer`
construction or `produce_and_persist` call exists; no concrete complete dependency/adjudication
provider exists; and none of the six production `DecisionValidityService` constructions injects
the verifier or reconciliation reader. This is an implemented seam under real injection, not DS18
production orchestration or institutional appointment.

## 3. Red-first and semantic evidence

### 3.1 Coercion negative

Exact node:

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_refuses_distinct_member_sets
```

Before implementation, the plugin-controlled replay exited `1` after the authentic Runtime and
Scientist source assertions, at the intended delayed import:

```text
ModuleNotFoundError: No module named 'polisyos.runtime.quality.epoch_denominator_reconciliation'
```

The final strengthened node exited `0`, one passed. It enters the configured
`DecisionValidityService` and proves:

```text
runtime_denominator_ref: sha256:7e1c4f8d5965e6c638e6fe067ed88860b9af00f14294e153f2aa8a2813488e48
scientist_denominator_ref: sha256:7be44799992462278d4b5b2e48d82954c0515c63b9fe83532e65871ec5d28801
digests_unequal: true
runtime_graph_source_artifact_ids:
  {sha256:2880048f2877cdcce4354f106673f1907ed60580ad49c067814a170b2848bfd4}
runtime_target_artifact_ids:
  {sha256:78603a1e2703ec8c8de2dc28dfe4eb0f83425db8eeebe425288723d1adb56b5f}
scientist_owner_artifact_ids:
  {sha256:ceedf30aadcaea7ca0c60caabe1c38882a06b02a3480b9194d2d1aadd7c65d62}
scientist_impact_member:
  (sha256:b5595883523b951e0de6d695e3ba7b3e9a47e2203b3f2315c0b1baf694e2c50f,
   epoch::distinct-member-set, epoch_lineage_distinct_member_set)
memberships_distinct: true
typed_nonreceipt_status: rejected
typed_nonreceipt_code: epoch_denominator_membership_mismatch
typed_nonreceipt_predicate_class: recomputed
typed_nonreceipt_handle: null
reconciliation_receipt_artifact_count: 0
pending_batches_after: 0
completed_batches_after: 0
packet_state_equal_before_after: true
```

Both sources are authentic. The false `artifact_id` join is the deciding mismatch. This proves
non-coercion: the sidecar cannot declare genuinely different owner memberships equal and writes no
positive artifact or Decision-Validity state.

### 3.2 Registered unequal-hash positive

Exact node:

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions
```

The pre-implementation node exited `1` after the canonical builder-produced transition, exact
two-member Scientist projection, and unequal-digest assertions, at the same intended missing-module
import. The final node exited `0`, one passed. Exact diagnostic readback from the same test path
recorded:

```text
runtime_denominator_ref: sha256:7e1c4f8d5965e6c638e6fe067ed88860b9af00f14294e153f2aa8a2813488e48
scientist_denominator_ref: sha256:381862983ab8af57c1324ca9bd13e69d27b96d42724cc8f2ca87dd179b6f05f5
digests_unequal: true
runtime_graph_source_artifact_ids:
  {sha256:2880048f2877cdcce4354f106673f1907ed60580ad49c067814a170b2848bfd4}
runtime_target_artifact_ids:
  {sha256:78603a1e2703ec8c8de2dc28dfe4eb0f83425db8eeebe425288723d1adb56b5f}
scientist_owner_artifact_ids:
  {sha256:78603a1e2703ec8c8de2dc28dfe4eb0f83425db8eeebe425288723d1adb56b5f}
scientist_impact_members:
  (sha256:4292672f7affaab9e68ba2edefb1c06b7cf2833dcfb2bf28d91c025b998fa9ec,
   epoch::reconciliation-owner, epoch_lineage_reconciliation_0)
  (sha256:a9cb6a75e1c2f6cc863d830408090e60fc76c9595dc8d01daf9d62097e5caafd,
   epoch::reconciliation-owner, epoch_lineage_reconciliation_1)
runtime_target_count: 1
scientist_owner_row_count: 1
scientist_impact_member_count: 2
mapping_row_count: 2
distinct_mapped_runtime_target_count: 1
mapping_cardinality: 1-to-2
snapshot_ref:
  sha256:b77952a34b5867506c325977d0793b5c1ac8218f46fed130c4011046cbec5d89
  scientist.decision_validity_epoch_impact_snapshot; application/json
snapshot_raw_sha256: sha256:b77952a34b5867506c325977d0793b5c1ac8218f46fed130c4011046cbec5d89
snapshot_content_hash: sha256:c760a073acc117309935e334b79cc2f4d866e549d436181538fec6a9e3b6dfee
receipt_ref:
  sha256:8d474c7385b11608dbfc64f259d0277f722f00d4a023cd268398a864f487980a
  polisyos.epoch.transition_denominator_reconciliation_receipt;
  application/vnd.polisyos.chronology+json
receipt_raw_sha256: sha256:8d474c7385b11608dbfc64f259d0277f722f00d4a023cd268398a864f487980a
receipt_content_hash: sha256:617117ae3a0b683eb95670ed2d66372689e9ebb9789637a9900bc6797a2d969e
completed_batch_count: 1
decision_validity_mutation_count: 2
```

The write-once binding identity was:

```text
batch_id: epoch_batch_86c302a858eacd7a4ee9eaa1602411696d4aa8570edf9e560bdff6a3e0bbfa74
binding_content_hash: sha256:4cf4e0e023911af6b63db1b8cfb87c1b6abd26ce8aa6859025598fd216bc73d0
transition_ref/content_hash:
  sha256:665df4dbdddffb4b84ac704d5baa96df5bbbd750321a304cc85806f805e94b30
verifier_provenance_ref:
  sha256:65ff9962a8f8b73012ad71661955401373fd11c9c2347398d20b969f38a44602
snapshot_ref/content_hash: sha256:b77952a34b5867506c325977d0793b5c1ac8218f46fed130c4011046cbec5d89 / sha256:c760a073acc117309935e334b79cc2f4d866e549d436181538fec6a9e3b6dfee
receipt_ref/content_hash: sha256:8d474c7385b11608dbfc64f259d0277f722f00d4a023cd268398a864f487980a / sha256:617117ae3a0b683eb95670ed2d66372689e9ebb9789637a9900bc6797a2d969e
schema: polisyos.decision-validity.epoch-reconciliation-admission-binding.v1
rule: polisyos.epoch-transition-denominator-reconciliation.v1
canon: polisyos.canon.json/0.2.0
```

A later valid candidate used receipt ref
`sha256:8281f1d29e0adff4e7e94bc1aad420ce28f356834a6fc96014f54bd308e5cd2f`
and content hash
`sha256:13de1189aef3f2ac8e6a37cb038ff50874b986fadc9eab61762efc4c500be983`.
Restart replayed the original handle, did not select the later candidate, made no replay mutation,
and left the late packet `ACTIVE`.

### 3.3 Task-4 exact-source post-review repair

Review of `191ffcd8c6845718672ab02c9a4ce2cae5f17ff3` found the same P37 exact-source
class one level deeper: `_read_transition_exact` recomputed the outer hash but did not reconstruct
the authoritative `EpochDependencyDenominatorReceipt` canonical/unique certificate-membership
predicate. This was the first post-commit finding in that bucket.

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_reconciliation_exact_transition_rejects_noncanonical_certificates
```

Against `191ffcd8c`, exit `1`, two failed: both duplicate and out-of-order certificate variants were
rejected by the authoritative receipt with `epoch_dependency_certificate_denominator_mismatch`,
but the reconciliation producer returned a positive persisted receipt. After the structural repair,
the same parametrized node exited `0`, two passed and proved exact unresolved plus zero positive
receipt persistence. The repair reconstructs `EpochDependencyDenominatorReceipt` from the exact
transition with graph-derived target refs and `predicate_class="independently_reconciled"`; it does
not strengthen the legacy v1 transition DTO. Repair commit:
`e0f21e091eb8d9a4d677c66149a92288ee91cf78`.

### 3.4 Real pre-change v1 literal bytes

The compatibility witness is a real `EpochValidityBatchReceipt` emitted before Phase 2 from base
`0413953e25a9efbba1521022156be3138dd855f6`, not a post-change reserialization. The committed
literal batch bytes are 1,532 bytes, raw SHA-256
`sha256:2317b29e75fc35a7fd093e04b03e9675f4f0344fc22682bc8fe7e29ddc1e4c01`, and
schema version `polisyos.decision-validity.epoch-batch-receipt.v1`. Base64 of the literal bytes:

```text
eyJhZGp1ZGljYXRpb25fZGVub21pbmF0b3JfcmVmIjoic2hhMjU2OjQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQiLCJhZmZlY3RlZF9wYWNrZXRfcmVmcyI6WyJzaGEyNTY6ZWQxMzU5ZmM0ZDYyYmVjZTZjMmFhMWU2MjA2NWMwOWUzMDJjNDI2NDY3NDkxNzQ3OTQ1NzI4NTVmOGQzOWI3ZCJdLCJiYXRjaF9pZCI6ImVwb2NoX2JhdGNoXzk4NjRlMTQ5OGJhNmFmMDBkN2JhN2QxZmNkZDFkM2U5ZGZjNTA2ZWM1MWFlYmMyYTcxZTQwOTMwNTQ1MWVhN2YiLCJjbGFpbV9icmlkZ2VfcmVzdWx0X3JlZnMiOltdLCJjb21wbGV0aW9uX3JlY2VpcHRfcmVmIjp7ImFydGlmYWN0X2lkIjoic2hhMjU2OmM4ZWQyMmI2ZGM4OTIxYmYxNjUzMDE4ZWRjZGNmNmU4NGZkOTI0MTZiODk5NWU1ZGFlYWRlM2ViODNmNDAwOTEiLCJraW5kIjoic2NpZW50aXN0LmRlY2lzaW9uX3ZhbGlkaXR5X2Vwb2NoX2JhdGNoX2NvbXBsZXRpb24iLCJtZWRpYV90eXBlIjoiYXBwbGljYXRpb24vanNvbiJ9LCJkZXBlbmRlbmN5X2Rlbm9taW5hdG9yX3JlZiI6InNoYTI1NjoyYWQ4OTNlY2EzOGMxZTJiNDdkNjYzOWQzY2Y4ODAzZjNhMTE3ZDNiNDEzMmFiODA3ZWIxYmJjMjQ3ZjRjYjVmIiwicmVxdWVzdGVkX3F1ZXJ5X2NvbnRleHRfcmVmIjoic2hhMjU2OjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIiLCJzY2hlbWFfdmVyc2lvbiI6InBvbGlzeW9zLmRlY2lzaW9uLXZhbGlkaXR5LmVwb2NoLWJhdGNoLXJlY2VpcHQudjEiLCJzdGF0ZSI6ImNvbXBsZXRlZCIsInRhcmdldHMiOlt7ImRlY2lzaW9uX2xpbmVhZ2Vfa2V5IjoiZXBvY2hfbGluZWFnZV8wIiwiZGVwZW5kZW5jeV9rZXkiOiJlcG9jaDo6b3duZXItZml4dHVyZSIsInBhY2tldF9yZWYiOiJzaGEyNTY6ZWQxMzU5ZmM0ZDYyYmVjZTZjMmFhMWU2MjA2NWMwOWUzMDJjNDI2NDY3NDkxNzQ3OTQ1NzI4NTVmOGQzOWI3ZCIsInJlYXNvbiI6ImVwb2NoX2FkdmFuY2VkIiwic3RhdHVzIjoic3RhbGUifV0sInRyYW5zaXRpb25fYXJ0aWZhY3RfcmVmIjp7ImFydGlmYWN0X2lkIjoic2hhMjU2OmE3YjJmZGZkMjlmNjA3MTQ4OTUwNmJlYzcxNTQxODRjMThhYjE0NTEyODgyNTcxNmVjMDFkMjJjOWZmYTgxY2YiLCJraW5kIjoiY2hyb25vbG9neS5lcG9jaF90cmFuc2l0aW9uIiwibWVkaWFfdHlwZSI6ImFwcGxpY2F0aW9uL2pzb24ifSwidHJhbnNpdGlvbl9jb250ZW50X2hhc2giOiJzaGEyNTY6YTdiMmZkZmQyOWY2MDcxNDg5NTA2YmVjNzE1NDE4NGMxOGFiMTQ1MTI4ODI1NzE2ZWMwMWQyMmM5ZmZhODFjZiIsInZlcmlmaWVyX3Byb3ZlbmFuY2VfcmVmIjp7ImFydGlmYWN0X2lkIjoic2hhMjU2OjY1ZmY5OTYyYThmOGI3MzAxMmFkNzE2NjE5NTU0MDEzNzNmZDExYzljMjM0NzM5OGQyMGI5NjlmMzhhNDQ2MDIiLCJraW5kIjoiY2hyb25vbG9neS5lcG9jaF90cmFuc2l0aW9uX3ZlcmlmaWVyIiwibWVkaWFfdHlwZSI6ImFwcGxpY2F0aW9uL2pzb24ifX0=
```

The companion historical blobs are a 36-byte transition at
`sha256:a7b2fdfd29f6071489506bec7154184c18ab145128825716ec01d22c9ffa81cf` and a
1,343-byte completion at
`sha256:c8ed22b6dc8921bf1653018edcdcf6e84fd92416b8995e5daeade3eb83f40091`.

Manifest profiles are exact: transition kind `chronology.epoch_transition`, media
`application/json`, schema `chronology.epoch_transition`/`1.0`, legacy canon with floats allowed,
and no inputs; completion kind `scientist.decision_validity_epoch_batch_completion`, media
`application/json`, schema `polisyos.decision-validity.epoch-batch-completion.v1`/`1.0`, default
canon, and the transition input; batch kind `scientist.decision_validity_epoch_batch_receipt`,
media `application/json`, schema `polisyos.decision-validity.epoch-batch-receipt.v1`/`1.0`, default
canon, and transition plus completion inputs.

```bash
/usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_pre_reconciliation_epoch_batch_v1_replays_exact_bytes_without_sidecar_binding
```

Final focused run: exit `0`, one passed in 24.33 seconds. The current model loads schema v1,
canonical reserialization equals the literal, and post-change SHA-256 equals the literal. The
Scientist `dependency_denominator_ref` remains
`sha256:2ad893eca38c1e2b47d6639d3cf8803f3a117d3b4132ab807eb1bbc247f4cb5f`; targets,
transition ref/hash, verifier provenance, completion ref, state, and Claim bridge refs keep their
v1 meanings. Reader configuration is literal `None`; no sidecar binding or lazy directory appears
before or after replay.

### 3.5 `derived_observations` sibling-consumer verdict

Verdict: same-class P31/P38 sibling consumer repaired; not a third owner definition. The property
is the full outer Runtime denominator over certificate bindings, dependency graph, and graph-derived
target refs. The old consumer tested the inner graph digest.

Shared helper:
`polisyos.runtime.quality.epoch_validity_cascade.epoch_dependency_outer_denominator_ref`.
Its exact consumers are `EpochDependencyDenominatorReceipt._bind_complete_denominator`, the
Task-4 exact transition reader, and certified epoch-inheritance recomputation in
`derived_observations`; the transition builder receives the same independently reconciled outer
digest without changing its v1 DTO validator.

The graph-only substitution negative was red first:

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_derived_observations.py::test_epoch_inheritance_recompute_rejects_graph_digest_substituted_for_outer_denominator
```

Before repair: exit `1` in 29.76 seconds, `Failed: DID NOT RAISE
DerivationRefusalError` after proving the graph-only transition was content-valid and exact-readable.
After repair: exit `0`; the consumer refuses with `EPOCH_RECOMPUTE_DRIFT` before persisting a
recompute receipt.

Producer-shaped positive witnesses:

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_dependency_and_adjudication_receipts_bind_complete_denominators /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_signed_transition_preimage_binds_owner_purpose_and_both_denominators /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_derived_observations.py::test_epoch_inheritance_recompute_receipt_round_trips_exact_owner_graph
```

Exit `0`, three passed. Group-end whole files: `test_derived_observations.py`, exit `0`, 51 passed;
`test_epoch_validity_cascade.py`, exit `0`, 30 passed. The importing Temporal route exact node also
passed one test. The v1 transition constructor and content hash remain unchanged.

### 3.6 C4 remains a separate frozen chain

The unchanged field chain is:

```text
EpochValidityBatchReceipt.dependency_denominator_ref
  = Scientist decision-impact Digest
ClaimDependencyDenominatorReceipt.batch_dependency_denominator_ref
  = that same Scientist Digest
ClaimLifecycleBridgeResultStatement.dependency_denominator_ref
  = ArtifactRef to the separate Claim mapping artifact
```

```bash
/usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_completed_epoch_batch_is_only_authority_input_to_claim_bridge
```

Exit `0`, one passed in 28.46 seconds. The test exact-reads the Claim mapping, proves the two Digest
fields above, and proves the pending Claim statement references the separate mapping artifact.

```bash
/usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/evidence/claims/test_head_index.py::test_verified_epoch_batch_advances_one_closed_head_with_stale_event
```

The changed C4 node passed twice; final focused result: exit `0`, one passed in 24.44 seconds. It
pins both full C4 profiles and their raw/semantic exact readers, proves the bridge-result field
remains the Claim mapping `ArtifactRef`, and rejects the Runtime reconciliation artifact profile
with `claim_profiled_statement_profile_mismatch`.

Tree proof on the freeze:

```bash
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine diff --exit-code 0413953e25a9efbba1521022156be3138dd855f6..c442e5db93da9442f545b6aa9355e0167f7803ee -- /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/core/contracts/c4_persisted_profiles.py
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine diff --exit-code 0413953e25a9efbba1521022156be3138dd855f6..c442e5db93da9442f545b6aa9355e0167f7803ee -- /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/schemas /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/packages/runtime-api-client /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/apps/runtime-dashboard/src/api/types.ts /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/runtime/http/openapi_contract.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/docs/plans/active
```

Both exited `0` with no output. The C4 profile, OpenAPI source, schemas, generated clients,
dashboard types, and active plans are byte-untouched.

## 4. Complete command ledger

Every entry below records a single semantic predicate, execution point, and result. No full
repository suite was claimed.

1. Positive control, before any red, base/Phase-1 state:

   ```bash
   /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_one_packet_with_two_epoch_keys_is_applied_once_without_losing_relation
   ```

   Exit `0`, one passed in 2.29 seconds. The refusal regression
   `test_epoch_batch_reconciles_complete_dependency_denominator` also passed one test; its bogus
   digest refusal was not cited as the positive control.

2. Coercion negative: exact argv and initial/final outcomes are in §3.1. Initial owned red:
   missing module after valid fixtures. Final: exit `0`, one passed in the refusing direction.

3. Registered positive: exact argv and initial/final outcomes are in §3.2. Initial owned red:
   missing module after valid fixtures. Final: exit `0`, one passed.

4. Task-3 snapshot/binding focused group:

   ```bash
   /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin -k 'epoch_impact_snapshot or strict_snapshot_refuses_nullable_owner_but_legacy_digest_is_unchanged or epoch_reconciliation or no_reconciliation_reader_preserves_legacy_admission_and_lazy_state or owner_denominator_is_stable_across_operational_timestamp_updates' /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py
   ```

   After the snapshot-backend normalization and real two-writer binding repair, exit `0`, 38
   passed. This includes the exact owner-denominator operational-timestamp stability node.

5. Task-4 post-review certificate-membership node: exact argv and two-fail/two-pass evidence are
   in §3.3. The two closure anchors were rerun together after the fix: exit `0`, two passed.

6. Task-5 proxy negative and three positives: exact argv and results are in §3.5.

7. Runtime group ends:

   ```bash
   /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_derived_observations.py
   /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py
   /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/http/test_temporal_routes.py::test_temporal_service_exact_reads_completed_recompute_at_requested_coordinate
   ```

   Results: exit `0`, 51 passed; exit `0`, 30 passed; exit `0`, one passed, respectively.

8. Historical v1, C4 lifecycle, fabricated DTO, and exact head-index nodes:

   ```bash
   /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_pre_reconciliation_epoch_batch_v1_replays_exact_bytes_without_sidecar_binding
   /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_completed_epoch_batch_is_only_authority_input_to_claim_bridge
   /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_fabricated_completed_batch_dto_and_matching_ref_cannot_bridge
   /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/evidence/claims/test_head_index.py::test_verified_epoch_batch_advances_one_closed_head_with_stale_event
   ```

   Final outcomes: all exit `0`, one passed each; 24.33 s, 28.46 s, 25.52 s, and 24.44 s.

9. Lifecycle whole-file group end:

   ```bash
   /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py
   ```

   Exit `0`, 14 passed in 22.91 seconds.

10. Scientist final group at freeze `c442e5db9`:

    ```bash
    /usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py
    ```

    Exit `0`. Exact terminal progress was 57 dots, then `............... [ 77%]`, then
    `..................... [100%]`: 93 cases by dots; no summary line was emitted.

### P41 head-index harness red

The Task-6 whole head-index file exited `1` only at two unchanged multiprocessing nodes. In each,
a child remained alive after fixed `process.join(20)`, so `exitcode is None`; Python 3.14 warned
that forking a multithreaded process may deadlock. The changed C4 node had passed twice, and every
non-multiprocessing case displayed a passing dot. Cleanup waited at multiprocessing atexit and was
interrupted only after failure output was captured, so no aggregate whole-file count exists.

This was classified by a true-slice-base replay, not by assertion. Base extraction:

```bash
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine archive 0413953e25a9efbba1521022156be3138dd855f6 | /usr/bin/tar -xf - -C /tmp/gy-cr4-base-replay.nhQYkr
```

Exact base commands, workdir `/tmp/gy-cr4-base-replay.nhQYkr`:

```bash
/usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/tmp/gy-cr4-base-replay.nhQYkr/src:/tmp/gy-cr4-base-replay.nhQYkr /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /tmp/gy-cr4-base-replay.nhQYkr/tests/unit/scientist/evidence/claims/test_head_index.py::test_concurrent_initial_head_creation_accepts_only_identical_bytes
/usr/bin/env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=/tmp/gy-cr4-base-replay.nhQYkr/src:/tmp/gy-cr4-base-replay.nhQYkr /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q -p pytest_benchmark.plugin -p pytest_asyncio.plugin /tmp/gy-cr4-base-replay.nhQYkr/tests/unit/scientist/evidence/claims/test_head_index.py::test_two_distinct_process_advances_from_one_predecessor_yield_one_conflict
```

Both exited `1` at the same `exitcode is None` assertions with the same Python 3.14 warning. The
first used parent PID 33815 / child 33857; the second parent 34011 / child 34115. Atexit waits were
interrupted only after failure output. `/bin/ps -o pid=,ppid=,stat=,etime=,command= -p
33857,33858,34115,34116` exited `1` with no output. This is a P41 base-reproduced harness red, not
an owned C4 semantic failure and not a waiver for the changed exact node.

## 5. Counts, lint, diffs, architecture, and bound checker

### Complete tracked-source counts and production boundary

The complete Git-tree enumerators were:

```bash
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine ls-tree -r --name-only 0413953e25a9efbba1521022156be3138dd855f6 | /usr/bin/awk 'BEGIN {n=0} /^src\/.*\.py$/ {n++} END {print n}'
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine ls-tree -r --name-only c442e5db93da9442f545b6aa9355e0167f7803ee | /usr/bin/awk 'BEGIN {n=0} /^src\/.*\.py$/ {n++} END {print n}'
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine ls-tree -r --name-only c442e5db93da9442f545b6aa9355e0167f7803ee | /usr/bin/awk 'BEGIN {n=0} /^src\/polisyos\/scientist\/.*\.py$/ {n++} END {print n}'
```

Outputs: 2,617 base source-Python files; 2,618 frozen source-Python files; 586 frozen Scientist
source-Python files. Git name-status proves one added source Python file and zero removed:

```text
2617 + 1 - 0 = 2618
```

An AST walk parsed every one of the 2,618 tracked source-Python files. It found:

- zero `EpochValidityTransitionProducer(...)` call nodes;
- zero `.produce_and_persist(...)` call nodes;
- only the two Protocol method declarations
  `EpochDependencyDenominatorProvider.resolve_complete_epoch_dependencies` and
  `EpochPerturbationAdjudicationProvider.resolve_complete_owner_adjudications`, and zero concrete
  complete provider classes;
- six `DecisionValidityService(...)` call nodes, at
  `runtime/http/services/control/run_lifecycle.py:1198,1326`,
  `runtime/http/services/debug.py:122`, `runtime/http/services/run_index.py:78`,
  `scientist/feedback/core.py:165`, and
  `scientist/nodes/builtins/decide/decision_packet/builder.py:859`; each has no verifier or
  reconciliation-reader keyword;
- across all 586 Scientist source files, zero occurrences of each exact required N12 field
  `subject_ref`, `gate_evidence_ref`, `epoch_validity_projection`, and
  `decision_packet_lineage_key_ref`, and zero AST calls, dictionaries, or function signatures
  containing all four.

This complete census decides the carried-row boundaries: DS18 production remains absent and N12
remains independently absent/unallocated.

### Ruff and frozen diffs

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m ruff check /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/core/contracts/__init__.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/core/contracts/decision_validity.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/runtime/quality/derived_observations.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/runtime/quality/epoch_denominator_reconciliation.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/runtime/quality/epoch_validity_cascade.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src/polisyos/scientist/validation/decision_validity.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_derived_observations.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/evidence/claims/test_head_index.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py
```

Exit `0`: `All checks passed!`.

```bash
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine diff --check 0413953e25a9efbba1521022156be3138dd855f6..c442e5db93da9442f545b6aa9355e0167f7803ee
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine diff --exit-code 0413953e25a9efbba1521022156be3138dd855f6..28bd0225b9fc098a3b53350b118f7dbdc160463e -- /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src
```

Both exited `0`, no output. The first proves frozen diff hygiene; the second proves Phase 1 changed
no source. Release TOML parsing exited `0` with `release_toml=ok`.

### Architecture P41 replay

Current command:

```bash
/usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tools/devx/architecture/guardrails.py check --skip-generated-checks
```

Exit `1`, solely the three existing
`runtime/http/services/acquisition_admission_bundle.py` deep imports of Core manifest, signing, and
write-contract modules. Exact base-archive replay used the same argv with
`PYTHONPATH=/tmp/gy-cr4-base-replay.nhQYkr/src:/tmp/gy-cr4-base-replay.nhQYkr` and the script at
`/tmp/gy-cr4-base-replay.nhQYkr/tools/devx/architecture/guardrails.py`; it exited `1` reproducing
the same three acquisition findings. Archive-only notices about missing `../.github` workflows are
extraction-harness notices, not current-tree findings. The acquisition red is therefore
base-reproduced P41 debt and no GY-CR4 architecture finding remains.

### Baselines and exactly-once checker

The carried docs-lifecycle baseline is exit `1` with exactly six findings. It was not rerun in this
slice and is recorded as carried, not normalized into a product failure.

The bound checker command, invoked exactly once on the clean quiescent freeze, is:

```bash
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tools/quality/validation/check_debt_ledger.py --check
```

Exit `0`, no blocking findings. Summary:
`register_ids=178`, `gy_ids=38`, `closure_signal_selects_nothing=0`,
`collection_failed=0`, `collection_host_unknown=0`, and
`ast_collection_disagreements=0`. Eight identity-unresolvable/count-exit disagreements and one
unsupported runner were informational, not blocking findings. Invocation count: exactly one.

## 6. Pattern closeout

- P01/P02: the injected seam is not contract-only. It has typed contracts, snapshot and receipt
  producers, exact CAS artifacts/readers, write-once admission binding, Scientist consumer,
  public/audit registration, positive, mismatch negative, and restart replay. DS18 production
  bridge absence remains explicit.
- P03: the public/audit inventory and reference expose the new Core capability; C4 is deliberately
  separate.
- P05/P10/P32: both sources are resolved and content-bound; appointed verifier provenance is
  checked; missing, substituted, ambiguous, malformed, or false membership fails before pending.
- P07: a base-provenanced literal v1 receipt remains byte-identical at 1,532 bytes and replays with
  no sidecar binding under the literal `None` reader branch.
- P13: the sidecar and write-once binding avoid versioning unrelated v1/C4/OpenAPI clients.
- P29: the producer persists real CAS bytes and exact-reads them; the proof is not constructor-only.
- P31: the graph-only `derived_observations` proxy now routes through the shared full-outer helper.
- P35: complete tracked-source denominators are 2,617 base and 2,618 freeze, with exact arithmetic;
  DS18 and N12 censuses enumerate their complete tracked source sets.
- P37/P38: the relation is frozen only as `independently_reconciled`; valid unequal 1-to-2
  membership passes, while a false join, noncanonical certificates, and graph-only substitution
  fail.
- P40: the Task-4 post-review certificate escape was classified as the same P37 exact-source class
  one level deeper and repaired structurally through the authoritative receipt predicate.
- P41: the head-index multiprocessing and acquisition deep-import reds were reproduced from the
  exact slice base and remain harness/architecture debt outside this slice.

## 7. Per-row disposition

| Row | Final effect of this slice | Active status to report | Deciding rule | Evidence anchors |
| --- | --- | --- | --- | --- |
| `epoch-dependency-denominator-defined-twice-incompatibly` | **Closes** | propose `open -> closed` to architect | Both exact definitions are persisted and exact-read through one non-coercive relation; valid unequal hashes pass; false membership typed-refuses without state; base v1 bytes remain identical. | registered positive; coercion negative; literal v1 bytes/hash/pass; exact read/restart; P37/P38 |
| `ds18-positive-transition-verification-producer-missing` | **Unblocked, not closed** | remains `blocked`, `producer_missing, candidate` | The contradiction is removed, but closure still needs a real verifier as production default at all six roots, appointed provenance, and positive production E2E verification. | six-root census; `NoEpochTransitionVerifier` default; no production injection |
| `ds18-positive-transition-production-unorchestrated` (engineering half) | **Unblocked, not closed** | remains `blocked`, `implemented_but_not_orchestrated, candidate` | Closure still requires a real pre-N9 trigger, complete dependency/adjudication providers, production transition `produce_and_persist`, and signer/producer appointment. | zero constructor/call/provider census |
| `GY-DEF23` engineering remainder | **Unblocked, not closed** | remains `blocked` | Strict intake has an honest injected seam, but no real signed transition enters through production generation control; institutional appointment remains separate. | seam positive plus DS18 boundary |
| `gy-n12-epoch-current-decision-lineage-carrier-unallocated` | **Neither closes nor directly unblocks** | remains `blocked`, `absent/unallocated` | Its content-bound lineage-head reader, four-field Scientist handoff, all-root routing, and authentic-old/head-advance/missing/substituted/denominator-drift falsifiers remain independent work. | 586-file Scientist census; zero four-field handoffs |

Only `epoch-dependency-denominator-defined-twice-incompatibly` closes in this slice.

## 8. Exact append-only row prose

### `epoch-dependency-denominator-defined-twice-incompatibly`

> **GY-CR4 PHASE-2 CLOSEOUT 2026-09-02 — `closed`; ratified close (a), non-coercive reconciliation.** Source/tests freeze `c442e5db93da9442f545b6aa9355e0167f7803ee` persists and exact-reads both owner projections through the additive `EpochTransitionDenominatorReconciliationReceipt` and a write-once Scientist admission binding; it does not assign either owner's digest to the other. The registered positive exits `0` with Runtime `sha256:7e1c4f8d5965e6c638e6fe067ed88860b9af00f14294e153f2aa8a2813488e48` and Scientist `sha256:381862983ab8af57c1324ca9bd13e69d27b96d42724cc8f2ca87dd179b6f05f5` unequal and an exact `1-to-2` mapping that survives restart/replay from the originally admitted handle. The coercion negative exits `0` in the refusing direction: authentic but disjoint owner memberships produce `epoch_denominator_membership_mismatch`, zero pending/completed batch, and unchanged packet state. A real pre-change `EpochValidityBatchReceipt` from `0413953e25a9efbba1521022156be3138dd855f6` remains literal-byte identical at `1532` bytes / `sha256:2317b29e75fc35a7fd093e04b03e9675f4f0344fc22682bc8fe7e29ddc1e4c01` and passes post-change readback with its v1 meaning unchanged. Canonicalization close (b) remains rejected; existing v1 DTOs, frozen C4 profiles, OpenAPI, generated clients and schemas are byte-untouched. The final tracked source-Python denominator reconciles `2617 + 1 - 0 = 2618`, and the bound debt checker ran exactly once on the clean quiescent freeze at exit `0` with no blocking findings.

### `ds18-positive-transition-verification-producer-missing`

> **GY-CR4 PHASE-2 DISPOSITION 2026-09-02 — denominator contradiction removed; `unblocked`, not `closed`; active row remains `blocked` / `producer_missing, candidate`.** The new receipt producer and exact reader establish the cross-owner relation under explicit test injection, so a future verifier no longer has to forward one owner's digest as the other. This slice deliberately does not install a positive verifier or reconciliation reader in `run_lifecycle.py`, does not replace the production `NoEpochTransitionVerifier` default, and does not appoint verifier provenance. Closure still requires a real verifier as the production default, injection at all six production `DecisionValidityService` construction roots, appointed verifier provenance, and a positive end-to-end production verification. The green GY-CR4 closure node is therefore evidence for the seam only and must not be cited as crossing DS18.

### `ds18-positive-transition-production-unorchestrated`

> **GY-CR4 PHASE-2 DISPOSITION 2026-09-02 — engineering prerequisite clarified; `unblocked`, not `closed`; active row remains `blocked` / `implemented_but_not_orchestrated, candidate`.** Exact reconciliation now gives downstream strict intake an honest relation between the Runtime epoch-input population and Scientist decision-impact population, but it neither drives nor signs a transition. Closure still requires a real pre-N9 trigger, complete `EpochDependencyDenominatorProvider` and `EpochPerturbationAdjudicationProvider` implementations, a production `EpochValidityTransitionProducer.produce_and_persist` call, and the separately appointed signer/owner-held producer identity. The final source census records `0` production producer constructions, `0` production calls, and `0` concrete complete owner-provider implementations; no production-orchestration closure is claimed here.

### `GY-DEF23` engineering remainder

> **GY-CR4 PHASE-2 DISPOSITION 2026-09-02 — honest intake seam delivered; engineering remainder `unblocked`, not `closed`; `GY-DEF23` remains `blocked`.** The injected real reconciliation path proves that strict Decision Validity can admit a content-bound transition without coercing the two owner denominators, but this slice does not make a signed transition enter through the production generation-control route. Closure still requires that production derive the signed transition before strict intake and satisfy the row's full no-state falsifiers; the transition-signing and owner-held producer-identity appointments remain a separate institutional conjunct and no appointment was made or proposed. The GY-CR4 positive is not a substitute for that production call.

### `gy-n12-epoch-current-decision-lineage-carrier-unallocated`

> **GY-CR4 PHASE-2 DISPOSITION 2026-09-02 — neither closed nor directly unblocked; active row remains `blocked` / `absent/unallocated`.** Denominator reconciliation binds a transition to the current Scientist impact snapshot; it does not allocate the independent current-packet lineage carrier. The row still requires a content-bound lineage-head reader keyed by `decision_packet_lineage_key_ref`, the four-field Scientist packet handoff (`subject_ref`, `gate_evidence_ref`, `epoch_validity_projection`, `decision_packet_lineage_key_ref`), identical direct/recursive/HTTP/offline routing, and authentic-old, head-advance, missing, substituted and denominator-drift falsifiers. The final complete Scientist-source census is `586` files with `0` qualifying four-field handoffs, and this slice claims no lineage work from the denominator sidecar.
