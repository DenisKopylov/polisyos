# GY-CR4 Denominator Seam Decision and Conditional Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking. **Do not execute the conditional Phase 2 below until the
> governed-contract change is explicitly authorized.**

**Goal:** Replace an impossible equality between the Runtime epoch-input denominator and the
Scientist decision-impact denominator with an exact, content-bound reconciliation that preserves
both claims and refuses a false mapping.

**Architecture:** Keep both owner denominators because they answer different completeness
questions. Add an append-only cross-owner reconciliation receipt whose relation is verified from
exact Runtime transition bytes and an exact Scientist owner snapshot; do not coerce either digest
or repurpose the Claim Ledger's separate mapping receipt. Existing v1 receipts remain readable and
unchanged.

**Tech Stack:** Python 3.14, strict/frozen Pydantic DTOs, canonical JSON and SHA-256, FileSystemCAS,
pytest, Ruff, PolicyOS public-surface and artifact governance.

**Spec:** `docs/plans/active/layer3-slices/GY-engine-subordination.md` row `GY-CR4` and
`docs/plans/active/DEBT-REGISTER.md` finding
`epoch-dependency-denominator-defined-twice-incompatibly`.

## Global Constraints

- Phase 1 is decision-only. Do not change either owner, any schema, or any frozen receipt before
  this document is reviewed.
- Phase 2 is currently **NO-GO**: the selected close needs one new governed cross-owner receipt
  contract. The task's stop rule requires explicit review/authorization before that change.
- Never mutate or reinterpret the existing `polisyos.epoch.dependency-denominator.v1`,
  `polisyos.epoch.validity-transition.v1`, Decision-Validity pending/completion/batch v1, or frozen
  C4 Claim profiles.
- A valid reconciliation may relate differently shaped sets, including one Runtime target with
  zero or many affected decisions. It must refuse omissions, additions, substitutions, ambiguous
  target ownership, stale packet-lineage membership, or a Decision-Validity dependency whose
  artifact is outside the Runtime target denominator.
- The positive case must preserve
  `epoch_dependency_denominator_ref != decision_impact_denominator_ref`; equality is not success.
- Do not edit `docs/plans/active/`; the architect owns register transcription.
- Use absolute paths in every command, targeted tests only, one whole-file pass per completed
  implementation group, the bound debt checker once on the final quiescent tree, and Ruff on every
  changed Python file.

---

## Phase 1 Verdict

### Decision

Choose close **(a)**: an append-only, content-bound
`EpochTransitionDenominatorReconciliationReceipt` with a real producer and exact reader.

The two hashes are not aliases. They are projections over two different owners at two different
workflow boundaries:

1. Runtime asks which immutable epoch evidence, dependency edges, and graph targets make up the
   transition input.
2. Scientist asks which registered decision packets and lineage heads are affected by the
   transition's semantic-epoch dependency keys at the atomic intake boundary.

The correct cross-owner invariant is therefore an exact relation, not byte equality. Runtime
targets may have no affected decision packet, and one Runtime target may affect several
dependency-key/packet/lineage members. Those cardinality differences are valid only when they are
explicitly represented. A Decision-Validity member that cannot be joined to exactly one Runtime
target, or an omitted/extra member on either declared side, is a genuine disagreement and must be
refused.

### Rejected alternative

Reject close **(b)**, canonicalizing one current definition and migrating the other owner.

- Canonicalizing the Runtime definition would discard the Decision-Validity owner snapshot that
  proves the exact packet/key/lineage impact set. Comparing only target triples would also omit the
  dependency owner's `artifact_id`, the field needed to join a Scientist key to a Runtime target.
- Canonicalizing the Scientist definition would discard the certificate/graph/target input
  completeness used by Runtime staleness and certified recomputation.
- Reusing either existing v1 hash namespace for the other payload would change historical semantic
  replay without a version discriminator (`P07`).

Close (b) would become preferable only if a ratified invariant and an implemented owner source of
truth established that the two projections are the same property: one persisted artifact would
have to derive both complete sets, prove a total bijection for zero-, one-, and many-impact cases,
and supply legacy replay/migration evidence. No such artifact, bijection, or invariant exists in
the tracked tree.

## Source Readout: What Each Definition Proves

The line numbers below are from branch `codex/gy-cr4-denominator-seam` at
`0413953e25a9efbba1521022156be3138dd855f6`; they supersede the older line anchors in the register.

### Runtime owner: complete epoch-transition input

`src/polisyos/runtime/quality/epoch_validity_cascade.py:319-340` defines an
`EpochDependencyGraph` as the complete owner-enumerated edge set. Its own `denominator_ref` hashes
only the graph edges.

`src/polisyos/runtime/quality/epoch_validity_cascade.py:722-756` defines the outer
`EpochDependencyDenominatorReceipt`. It verifies:

```python
expected = _semantic_hash(
    "polisyos.epoch.dependency-denominator.v1",
    {
        "certificate_bindings": self.certificate_bindings,
        "dependency_graph": self.dependency_graph,
        "target_refs": self.target_refs,
    },
)
```

The receipt also requires `target_refs` to equal the unique graph-target set and certificate
bindings to be canonical and unique. The transition producer copies that outer digest at
`epoch_validity_cascade.py:1143-1167`.

This answers: **what exact immutable evidence and graph population is the basis of this epoch
transition?** It does not enumerate Decision-Validity packets or lineage heads.

### Scientist owner: complete decision-impact snapshot

`src/polisyos/scientist/validation/decision_validity.py:823-849` walks the requested dependency
keys from the Decision-Validity owner index and builds rows containing:

```python
{
    "dependency_key": owner.dependency_key,
    "dependency_kind": owner.dependency_kind.value,
    "artifact_id": owner.artifact_id,
    "packet_refs": sorted(owner.packet_refs),
    "lineage_keys": sorted(owner.lineage_keys),
}
```

It hashes canonical `json.dumps(rows, sort_keys=True, separators=(",", ":"))` bytes with raw
SHA-256 and separately derives exact `(packet_ref, dependency_key, decision_lineage_key)` targets.
Decision Packet registration enters at `decision_validity.py:852-914`; its owner-index write is
implemented at `decision_validity.py:1615-1652`.

This answers: **for the supplied semantic-epoch keys, what exact current packet/key/lineage
population must the owner freeze and update atomically?** It does not enumerate certificate
bindings or epoch graph edges.

### The impossible gate

At `decision_validity.py:485-495`, strict intake derives the Scientist target set and digest, then
requires both:

```python
observed_targets == expected_targets
receipt.dependency_denominator_ref == expected_denominator
```

The verifier-to-intake receipt has only one digest field
(`src/polisyos/core/contracts/decision_validity.py:240-270`). Forwarding the Runtime digest into it
cannot meet the second comparison. Replacing it with the Scientist digest without a persisted
mapping would merely conceal the Runtime/Scientist disagreement.

Predicate classification (`P37`): the two owner populations are `recomputed`; the relation between
them is currently `not_established`. It may become `independently_reconciled` only after exact
resolve + content-bind + verifier-provenance checks.

Proxy divergence (`P38`): the gate intends to establish that the transition's complete Runtime
target population maps soundly and completely to the Scientist impact population, but it actually
tests equality of unrelated hashes. A single graph target affecting two registered packets is a
concrete case where the relationship is valid and the equality is necessarily false.

## Complete Consumer and Reference Enumeration

### Commands and denominators

The exploratory search used `rg`; the authoritative count used the immutable research base
`0413953e25a9efbba1521022156be3138dd855f6` so untracked environments, indexes, and this decision
document's own non-consumer references could not define the denominator (`P35`). Re-running a
worktree-wide grep after this deliverable is committed will add this plan as one documentation file;
that does not add a product consumer.

```bash
/Applications/ChatGPT.app/Contents/Resources/rg -n --hidden --glob '!.git' --glob '!.venv' --glob '!node_modules' 'dependency_denominator_ref|dependency-denominator|dependency_denominator' /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine ls-tree -r --name-only 0413953e25a9efbba1521022156be3138dd855f6 | /usr/bin/awk 'END {print NR}'
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine ls-tree -r --name-only 0413953e25a9efbba1521022156be3138dd855f6 | /usr/bin/awk 'BEGIN {src=0; tests=0} /^src\// && /\.py$/ {src++} /^tests\// && /\.py$/ {tests++} END {print src, tests, src+tests}'
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -I --fixed-strings -e 'dependency_denominator_ref' 0413953e25a9efbba1521022156be3138dd855f6
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -I --fixed-strings -e 'dependency_denominator_ref' 0413953e25a9efbba1521022156be3138dd855f6 | /usr/bin/awk -F: '{matches++; seen[$2]=1} END {for (path in seen) files++; print matches, files}'
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -I --fixed-strings -e 'dependency_denominator_ref' 0413953e25a9efbba1521022156be3138dd855f6 | /usr/bin/awk -F: '{path=$2; if (path ~ /^src\//) class="src"; else if (path ~ /^tests\//) class="tests"; else if (path ~ /^docs\//) class="docs"; else if (path ~ /^(schemas|packages|apps)\//) class="generated"; else if (path ~ /^tools\//) class="tools"; else class="other"; lines[class]++; seen[class SUBSEP path]=1} END {for (key in seen) {split(key, part, SUBSEP); files[part[1]]++} for (class in lines) print class, lines[class], files[class]}' | /usr/bin/sort
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -I --fixed-strings -e 'polisyos.epoch.dependency-denominator.v1' 0413953e25a9efbba1521022156be3138dd855f6
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -I --fixed-strings -e 'polisyos.claim-ledger.dependency-denominator.v1' 0413953e25a9efbba1521022156be3138dd855f6
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -E -- 'EpochDependencyDenominatorReceipt|EpochValidityTransitionArtifact|EpochTransitionVerificationReceipt|EpochValidityPendingBatch|EpochValidityBatchCompletionStatement|EpochValidityBatchReceipt|ClaimDependencyDenominatorReceipt|ClaimLifecycleBridgeResultStatement|EpochInheritanceRecomputeReceipt' 0413953e25a9efbba1521022156be3138dd855f6 -- src tests tools
/usr/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine grep -n -E -- 'DecisionValidityService\(|epoch_transition_verifier=' 0413953e25a9efbba1521022156be3138dd855f6 -- src
```

Measured denominator and result:

- 10,497 tracked paths.
- 5,107 tracked Python paths: 2,617 under `src/` plus 2,490 under `tests/`, including
  `tests/conftest.py` at the test root.
- `dependency_denominator_ref`: 88 matching lines in all 28 matching tracked files.
- Production source: 40 lines in 9 files.
- Tests: 30 lines in 9 files.
- Docs/register/history: 10 lines in 5 files.
- Generated/public client surfaces: 6 lines in 4 files.
- Quality validator: 2 lines in 1 file.
- Six production `DecisionValidityService(...)` constructions and zero
  `epoch_transition_verifier=` injections in the complete 2,617-source-Python denominator.

### Every direct-reference file, classified

| Class | Complete tracked file set | Semantic dependency |
| --- | --- | --- |
| Runtime producer and local carriers | `src/polisyos/runtime/quality/epoch_validity_cascade.py` | Defines graph and outer Runtime denominator; writes the outer digest into the transition. |
| Runtime semantic consumers | `src/polisyos/runtime/quality/epoch_staleness_projection.py`; `src/polisyos/runtime/quality/derived_observations.py` | Staleness correctly compares an exact outer receipt to the transition. Certified recomputation incorrectly compares the transition's outer field to the inner graph digest; see the consumer defect below. |
| Scientist intake and persisted batch lifecycle | `src/polisyos/scientist/validation/decision_validity.py`; `src/polisyos/core/contracts/decision_validity.py` | Recomputes the impact denominator, applies the impossible equality, then carries one digest through verification, pending, completion, batch, replay, and gate receipts. |
| Claim owner bridge | `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py`; `src/polisyos/scientist/evidence/claims/head_index.py`; `src/polisyos/core/contracts/c4_persisted_profiles.py` | Treats the completed batch digest as a foreign binding while independently constructing a Claim dependency-path mapping. The C4 bridge field is a ref to that mapping, not either disputed digest. |
| Runtime API examples | `src/polisyos/runtime/http/openapi_contract.py` | Serialized example/contract construction only; it does not validate denominator semantics. |
| Generated/public surfaces | `schemas/runtime_api_v1.openapi.json`; `packages/runtime-api-client/runtimeApiClient.ts`; `packages/runtime-api-client/types.ts`; `apps/runtime-dashboard/src/api/types.ts` | Shape-only projections of the existing batch response. |
| Quality validator | `tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py` | Test-like fixture obtains the Scientist denominator and injects it into a verification receipt. |
| Direct tests | `tests/unit/runtime/http/test_runs_api.py`; `tests/unit/runtime/quality/test_derived_observations.py`; `tests/unit/runtime/quality/test_epoch_staleness_projection.py`; `tests/unit/runtime/quality/test_epoch_validity_cascade.py`; `tests/unit/runtime/quality/test_generation_cycle.py`; `tests/unit/runtime/quality/test_open_world_risk.py`; `tests/unit/scientist/evidence/claims/test_head_index.py`; `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py`; `tests/unit/scientist/validation/test_decision_validity_service.py` | Local construction, carriage, rejection, replay, C4 mapping, and generated-profile coverage. The registered reconciliation test does not yet exist. |
| Planning and historical evidence | `docs/plans/active/DEBT-REGISTER.md`; `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`; `docs/plans/active/layer3-slices/GY-engine-subordination.md`; `docs/superpowers/journals/2026-08-30-debt-b-epoch-decision-validity.md`; `docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md` | Records the seam, closure signal, or earlier single-field design. These are not runtime consumers. |

Transitive Runtime consumers were also followed by class/function identity, not only by the field
token. `EpochInheritanceRecomputeReceipt` is read by
`src/polisyos/runtime/quality/epoch_staleness_projection.py`, which is called by
`src/polisyos/runtime/http/services/temporal.py`; their tests include
`tests/unit/runtime/http/test_temporal_routes.py`.

### Claim Ledger constraint

The complete Claim chain is:

```text
EpochValidityBatchReceipt.dependency_denominator_ref (Digest)
  -> EpochClaimLifecycleBridgeService as batch_dependency_denominator_ref
  -> ClaimDependencyDenominatorReceipt (new Claim-path mapping artifact)
  -> ClaimLifecycleBridgeResultStatement.dependency_denominator_ref
     (ArtifactRef to the Claim mapping, not a Digest)
  -> frozen claim_bridge_result C4 profile
  -> ClaimLedgerHeadStatement.bridge_result_refs
  -> exact head replay
```

Evidence: `lifecycle_bridge.py:152-220`, `head_index.py:873-921`,
`head_index.py:1026-1049`, `head_index.py:2867-2959`, and
`c4_persisted_profiles.py:402-470`.

Neither admissible close requires changing this chain. The new reconciliation receipt must not
replace `ClaimLifecycleBridgeResultStatement.dependency_denominator_ref`; doing so would break the
typed read at `head_index.py:2882-2887` and the exact pending/result comparison at
`head_index.py:2928-2932`. The Claim mapping should continue to carry the Scientist batch digest as
`batch_dependency_denominator_ref`, with the batch/transition pair linking it to the separately
reconciled Runtime digest.

No enumerated dependent contract is unable to survive close (a). Stop rule 3 is therefore not
triggered.

### Additional consumer defect found

`src/polisyos/runtime/quality/derived_observations.py:2000-2008` rejects unless
`transition.dependency_denominator_ref == transition.dependency_graph.denominator_ref`. Those are
the outer Runtime denominator and inner graph denominator respectively, so a transition emitted by
`EpochValidityTransitionProducer` would fail this consumer. Existing fixtures at
`tests/unit/runtime/quality/test_epoch_validity_cascade.py:1224-1247` and
`tests/unit/runtime/quality/test_derived_observations.py:1463-1485` encode the graph-only proxy.

This is not a third owner definition: the consumer does not mint a new denominator. It is an
existing P38 proxy and P31 sibling-consumer escape. It survives close (a) by using one shared
Runtime helper that recomputes the full
`{certificate_bindings, dependency_graph, target_refs}` denominator from transition content. The
same helper must be used by `EpochDependencyDenominatorReceipt`,
`EpochValidityTransitionArtifact`, and certified recomputation; the two graph-only fixtures must be
migrated. A one-site equality deletion would not close this class.

## Selected Receipt Contract

The authorized implementation should add one additive sidecar artifact rather than mutate any
existing v1 receipt. Its strict contract must carry:

- schema/rule version and canonicalization profile;
- reconciliation artifact ref and raw content hash in its persisted handle;
- exact transition artifact ref and raw content hash;
- Runtime `epoch_dependency_denominator_ref` and the complete canonical Runtime target refs derived
  from the transition's certificate/graph/target members;
- exact persisted Scientist owner-snapshot ref and raw content hash;
- Scientist `decision_impact_denominator_ref`, requested dependency keys, exact owner rows, and
  exact packet/key/lineage target triples;
- canonical mapping rows from each Scientist dependency/impact member to exactly one Runtime target
  by owner `artifact_id`, while explicitly retaining zero-impact Runtime targets;
- requested query context, authority purpose, verifier provenance, and frozen
  `predicate_class="independently_reconciled"`;
- a domain-separated reconciliation content hash over every field except itself.

The reader must resolve and verify both source artifacts, recompute both independent denominators,
recompute the mapping, verify the receipt's fixed kind/media/schema/canonical bytes and verifier
provenance, and reject missing, duplicated, extra, stale, ambiguous, or substituted members. It
must never assign one owner's digest to the other.

The existing `EpochTransitionVerificationReceipt.dependency_denominator_ref` remains explicitly
the Scientist impact digest expected by intake. The Runtime digest remains in the transition and
the new sidecar.

Because the v1 pending/completed DTOs do not carry the new sidecar's identity, coordinate lookup
alone is insufficient for replay: a later rule or provenance reissue could create a second valid
receipt for the same transition/query/Scientist digest. First admission must therefore persist a
separate, write-once `EpochDenominatorReconciliationAdmissionBinding` inside the Scientist owner
transaction *before* `EpochValidityPendingBatch`. Its key binds the batch id, transition ref/hash,
query context, Scientist impact digest, and verifier provenance; its value binds the exact sidecar
ref/hash plus reconciliation rule/profile version. A conflicting second binding fails closed.
Pending or completed replay loads this admitted handle and exact-reads that receipt; it never scans
for a current match or reconciles historical work against a later live owner index. This additive
binding is the durable carrier that permits every existing v1 DTO byte to remain unchanged.

## Frozen and Governed Artifact Verdict

### Existing artifacts

- `EpochValidityPendingBatch`, `EpochValidityBatchCompletionStatement`, and
  `EpochValidityBatchReceipt` are strict/frozen and carry v1 schema literals at
  `src/polisyos/core/contracts/decision_validity.py:273-363`.
- `EpochTransitionVerificationReceipt` and those batch contracts are exported on the
  `polisyos.core` `public_stable` surface; see
  `architecture/public_surface/inventory.json:191-206,662-676`.
- Schema policy requires additive changes to be versioned and committed snapshots to be reviewed
  as contract changes (`docs/how-to/release-policy.md:170-184`).
- The C4 `claim_dependency_denominator` and `claim_bridge_result` profiles are explicitly frozen;
  neither needs modification.
- `polisyos.epoch.validity-transition.v1` content-binds the overloaded field, and the public
  `EpochInheritanceRecomputeReceipt` carries it under its own v1 schema. Reinterpreting either
  existing field in place would violate rule-versioned replay.

### Stop ruling

An ungoverned private sidecar would be a hidden cross-owner authority artifact (`P01`, `P03`,
`P32`). An honest close therefore needs a new typed, persisted, versioned cross-owner contract and
profile, plus public/audit registration or an explicit `surface_out_of_scope` ruling. That is a
governed schema change even though it can be additive and leave every existing v1 byte unchanged.

**Stop rule 1 is triggered. Phase 2 must not begin under the current authorization.**

The smallest authorization that would release the stop is permission to add the new additive
reconciliation sidecar contract/profile, its write-once admission-binding contract/index, and
their public/audit registration while preserving every existing v1 DTO, OpenAPI response,
generated client, and frozen C4 profile. Authorization to reinterpret a current v1 field is neither
requested nor acceptable.

## Pattern Pass

| Pattern | Existing issue | Target correct pattern | Acceptance signal |
| --- | --- | --- | --- |
| `P01` / `P02` | Two contracts and local producers coexist without a real cross-owner artifact/bridge. | Persisted receipt + producer + exact reader + intake consumer. | Registered positive node crosses both owners and replays exact bytes. |
| `P03` | A private sidecar could hide the basis of authority. | Public/audit registration, or an explicit scoped ruling. | Artifact can be resolved from durable batch coordinates. |
| `P05` / `P10` / `P32` | Copying the Scientist hash into a verifier receipt could launder an unproved relation. | Resolve both sources, content-bind both, verify independent provenance, fail closed. | Substituted source/ref/hash/provenance cases leave zero batch state. |
| `P07` | Reinterpreting an existing v1 hash or receipt would change replay semantics. | Additive versioned sidecar; legacy v1 bytes retain their meaning. | Historical receipt replay remains byte-identical. |
| `P13` | Versioning every downstream DTO would add unnecessary governance gravity. | One sidecar keyed by existing durable coordinates; no C4/OpenAPI mutation. | No existing serialized DTO field changes. |
| `P29` | A constructor-only receipt would be authorial proof. | Real producer writes CAS; exact reader verifies source bytes and manifest profile. | Remove/corrupt receipt or source and admission refuses. |
| `P31` | `derived_observations` is a sibling graph-only proxy. | One Runtime denominator helper used by receipt, transition validator, and every semantic consumer. | Actual producer-shaped transition passes; graph-only substituted digest fails. |
| `P35` | Sampled searches could miss a consumer. | Complete tracked-path census with file-type denominators. | 88 references / 28 files reconcile to 10,497 tracked paths. |
| `P37` / `P38` | The relation is `not_established`; the gate tests hash equality instead. | Freeze `independently_reconciled` only after exact relational proof. | Valid one-to-many mapping passes with unequal hashes; a false join refuses. |

Current capability state for the proposed sidecar is `absent/unallocated`. If authorization permits
only the typed contract, it becomes `contract_only`; it remains
`producer_missing + bridge_missing + verification_missing` until the conditional tasks below land.
The existing cross-owner seam remains
`epoch-dependency-denominator-defined-twice-incompatibly` and is not closed by this decision alone.

---

## Conditional Phase 2 Build Sequence

The sequence below is binding only after the stop is explicitly released. It preserves the
registered closure signal because close (a), not close (b), was selected.

### Task 0: Reconfirm the genuine positive baseline before any red

**Files:** none.

- [ ] Run the existing exact successful-admission control:

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_one_packet_with_two_epoch_keys_is_applied_once_without_losing_relation
```

Expected: exit 0, one passed with a completed batch and one lifecycle mutation. Phase 1 ran this
command before any red and observed that result. The separately run
`test_epoch_batch_reconciles_complete_dependency_denominator` is a green refusal-path regression
control: despite its name, it substitutes a bogus digest and expects
`dependency_denominator_unresolved`; it must not be cited as a positive admission control.

### Task 1: Write the non-coercion negative first

**Files:**

- Modify: `tests/unit/scientist/validation/test_decision_validity_service.py`

**Behavior:** Build an authentic Runtime transition whose full outer denominator verifies, then a
Scientist snapshot containing one semantic-epoch dependency whose `artifact_id` does not name any
Runtime target. Ask the real reconciliation seam to admit it. Require
`epoch_denominator_membership_mismatch`, no pending/completed batch, and unchanged packet state.

- [ ] Add
  `test_epoch_denominator_reconciliation_receipt_refuses_distinct_member_sets` before the positive
  closure test.
- [ ] Run only that node and record the initial failure. It must fail because the real receipt
  producer/reader is absent, not because the fixture is malformed.

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_refuses_distinct_member_sets
```

Expected before implementation: fail. Expected after Task 4: pass with both owner digests still
unequal and zero Decision-Validity mutation.

### Task 2: Write the registered positive red

**Files:**

- Modify: `tests/unit/scientist/validation/test_decision_validity_service.py`

**Behavior:** Use an authentic producer-shaped Runtime transition and a Scientist impact snapshot
with a valid one-to-many packet mapping. Persist and exact-read the reconciliation receipt, assert
the two independent digests are unequal, admit the batch, restart the service, and replay the same
receipt without consulting a later live index.

- [ ] Add the registered signal unchanged:
  `test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions`.
- [ ] Run only that node and record the red caused by the missing producer/reader.

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions
```

Expected before implementation: fail. Expected after Task 4: pass.

### Task 3: Add the governed sidecar contract and exact owner snapshot

**Files:**

- Modify: `src/polisyos/core/contracts/decision_validity.py`
- Modify: `src/polisyos/core/contracts/__init__.py`
- Modify: `src/polisyos/core/contracts/README.md`
- Modify: `src/polisyos/scientist/validation/decision_validity.py`
- Modify: `src/polisyos/scientist/validation/README.md`
- Modify/regenerate: `architecture/public_surface/inventory.json`
- Modify/regenerate: `docs/reference/public-surface.md`
- Create: `release-fragments/unreleased/2026-09-02-gy-cr4-denominator-reconciliation.toml`

**Interfaces:**

- Scientist produces an exact persisted `DecisionValidityEpochImpactSnapshot` under the existing
  owner transaction from the same rows and target triples used by `_resolve_epoch_target_denominator`.
- Core defines the strict/frozen snapshot handle, mapping member,
  `EpochTransitionDenominatorReconciliationReceipt`, persisted handle,
  `EpochDenominatorReconciliationAdmissionBinding`, and a separate reader Protocol that Scientist
  can consume without importing Runtime.
- Existing v1 verification/pending/completion/batch/gate DTOs are not changed.

- [ ] Refactor `_resolve_epoch_target_denominator` through one snapshot builder so its digest and
  target set cannot drift from the persisted snapshot.
- [ ] Persist and exact-read the snapshot with fixed kind/media/schema/canonical profile; content
  bind dependency rows, packet/key/lineage triples, query context, and owner projection generation.
- [ ] Add a write-once Scientist owner index for the exact admitted sidecar handle. Bind batch id,
  transition ref/hash, query, Scientist digest, verifier provenance, sidecar ref/hash, and rule/profile;
  reject a conflicting rewrite and resolve by the frozen handle on pending/completed replay.
- [ ] Add contract negatives for duplicate members, non-canonical order, wrong semantic-epoch kind,
  and self-hash substitution in the same service test file.
- [ ] Run the new snapshot negatives and the existing denominator-stability node.

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/scientist/validation/test_decision_validity_service.py::test_owner_denominator_is_stable_across_operational_timestamp_updates
```

Expected: pass; the snapshot digest excludes operational timestamps exactly as the existing owner
digest does.

### Task 4: Produce, exact-read, and consume the reconciliation

**Files:**

- Create: `src/polisyos/runtime/quality/epoch_denominator_reconciliation.py`
- Modify: `src/polisyos/runtime/quality/README.md`
- Modify: `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- Modify: `src/polisyos/scientist/validation/decision_validity.py`
- Modify: `tests/unit/scientist/validation/test_decision_validity_service.py`

**Interfaces:**

- Runtime's producer resolves exact transition and Scientist snapshot bytes, recomputes both
  denominators, derives the complete mapping, persists the sidecar, and returns only its ref/hash.
- Runtime's exact reader re-resolves both inputs and verifier provenance and recomputes the receipt.
- Scientist receives that reader through a new constructor port separate from
  `EpochTransitionVerifier`; its fail-closed default produces no positive receipt. On first
  admission it compares the sidecar's Scientist digest/targets with the live snapshot and freezes
  the exact sidecar handle before pending state. On pending/completed replay it resolves only the
  write-once admitted handle and does not consult the live owner index.
- Failure code `epoch_denominator_membership_mismatch` joins the existing intake failure-code set.

- [ ] Implement one domain-named producer and one exact reader; do not duplicate either owner's
  hash algorithm.
- [ ] Route the first-admission equality seam through the reader result. Keep the direct Scientist
  equality only as a local snapshot-integrity check, never as a Runtime/Scientist equality.
- [ ] Make zero/multiple receipt lookup, wrong artifact profile, bad source hash, wrong query/purpose,
  unappointed provenance, omitted/extra/duplicate mapping, and false `artifact_id` join fail before
  pending state is written.
- [ ] Make a second sidecar for the same admission coordinates but a different ref/hash, rule, or
  provenance fail as an admission-binding conflict; prove replay still reads the originally bound
  handle after a later candidate is published.
- [ ] Do not wire a positive verifier or reader into `run_lifecycle.py` in this task. That requires
  the still-unmet DS18 production verifier, owner-provider, and appointment work; tests inject the
  real reconciliation reader directly while the production default remains fail closed.
- [ ] Run the negative from Task 1 first, then the registered positive from Task 2.

Expected: both pass; the positive explicitly proves unequal digests can reconcile, and the negative
proves unequal memberships cannot be coerced.

### Task 5: Repair the discovered Runtime sibling consumer

**Files:**

- Modify: `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- Modify: `src/polisyos/runtime/quality/derived_observations.py`
- Modify: `tests/unit/runtime/quality/test_epoch_validity_cascade.py`
- Modify: `tests/unit/runtime/quality/test_derived_observations.py`

- [ ] Extract one Runtime helper for the full outer epoch denominator and call it from
  `EpochDependencyDenominatorReceipt`, transition validation, and certified recomputation.
- [ ] Change the two graph-only fixtures to build the full producer denominator.
- [ ] Add a negative that preserves a valid graph digest but substitutes the outer denominator; the
  transition or recompute producer must reject it.
- [ ] Run the exact producer/recompute nodes, then each changed whole test file once.

```bash
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py::test_signed_transition_preimage_binds_owner_purpose_and_both_denominators
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_derived_observations.py
/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python -m pytest -q /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tests/unit/runtime/quality/test_epoch_validity_cascade.py
```

Expected: all pass with actual producer semantics; graph-only substitution is red in the refusing
direction.

### Task 6: Prove Claim/C4 compatibility without modifying its frozen profile

**Files:**

- Test only: `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py`
- Test only if an existing assertion needs clarification:
  `tests/unit/scientist/evidence/claims/test_head_index.py`

- [ ] Extend the existing completed-batch bridge test to assert that
  `ClaimDependencyDenominatorReceipt.batch_dependency_denominator_ref` is the Scientist batch
  digest and that `ClaimLifecycleBridgeResultStatement.dependency_denominator_ref` still resolves
  to the Claim mapping artifact.
- [ ] Assert the cross-owner reconciliation receipt cannot be supplied in that C4 field.
- [ ] Run exact nodes while editing, then each changed whole file once.

Expected: Claim lifecycle advances only from the exact completed batch and exact Claim mapping;
the frozen `claim_bridge_result` field list and semantic prefix remain byte-identical.

### Task 7: Close only the row whose full signal is met

**Files:**

- Create append-only after source/tests freeze:
  `docs/superpowers/journals/2026-09-02-gy-cr4-denominator-seam.md`
- Do not modify: `docs/plans/active/DEBT-REGISTER.md`

- [ ] Run `tests/unit/scientist/validation/test_decision_validity_service.py` once as the final
  Scientist group file.
- [ ] Run Ruff over every changed Python file and `git diff --check`.
- [ ] On the quiescent tree, run the bound checker exactly once:

```bash
/usr/bin/env PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/tools/quality/validation/check_debt_ledger.py --check
```

Expected carried baseline: exit 0 with zero blocking. Do not normalize the carried
`check_docs_lifecycle` exit 1 / exactly 6 findings, and re-read the complete tracked
`src/**/*.py` denominator if any source file is added (Phase-1 baseline: 2,617).

- [ ] Append exact red-first output, the unequal-hash positive, the false-membership refusal, all
  exact/whole-file commands, and exact append-only row prose to the journal.
- [ ] Verify branch attachment immediately before each commit. Commit source/tests separately from
  the append-only journal.

## Carried Row Disposition

| Row | Phase-1 effect | Effect after an authorized, fully verified Phase 2 | Deciding rule |
| --- | --- | --- | --- |
| `epoch-dependency-denominator-defined-twice-incompatibly` | Remains `open`; decision recorded, capability still absent. | **Closes.** | Both exact definitions are persisted and read through one non-coercive reconciliation; registered positive and mismatch negative pass. |
| `ds18-positive-transition-verification-producer-missing` | Seam decision removes the design ambiguity only. | **Unblocked, not closed.** | Closure still requires a real verifier as production default, all six construction roots injected, appointed verifier provenance, and positive end-to-end verification. |
| `ds18-positive-transition-production-unorchestrated` (engineering half) | Relation to downstream intake is decided. | **Unblocked, not closed.** | Closure still requires a real pre-N9 trigger, both complete owner providers, production `produce_and_persist`, and separately appointed signer/producer identity. |
| `GY-DEF23` engineering remainder | The honest intake bridge is specified. | **Unblocked, not closed.** | Closure still requires a real signed transition to enter strict intake through the production generation-control route; institutional appointment remains separate. |
| `gy-n12-epoch-current-decision-lineage-carrier-unallocated` | Constrained but not unblocked. | **Does not close and is not directly unblocked.** | Its own content-bound lineage-head reader, four-field Scientist packet handoff, all-root routing, and authentic-old/head-advance/missing/substituted/denominator-drift falsifiers remain independent work. |

Phase 2 must not claim any of the last four rows closed merely because the denominator seam is
repaired.

## Phase 1 Verification Receipt

- Bound interpreter confirmed once:
  `/Users/deniskopylov/polisyos/.worktrees/gy-cr4-denominator-seam/policy-engine/.venv`.
- Branch attachment confirmed as `refs/heads/codex/gy-cr4-denominator-seam` at
  `0413953e25a9efbba1521022156be3138dd855f6` before research.
- Existing refusal-path regression control passed: one test, exit 0.
- Existing successful-admission positive control passed before any red: one test, exit 0.
- No source, test, schema, generated surface, C4 profile, active plan, or journal was changed in
  Phase 1.
- The failure/repair register was read before the decision and must be re-read before any authorized
  Phase-2 closeout.
