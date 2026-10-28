# G27-02: admission of a registered SQL materialization

This records the user-forwarded G architecture decision dated 28 October 2026. Its
source basis is commit `cb3e81aa6998cb6d0ecda91c68c9e1789d4f35b6`, tree
`f848b376a36e272770baed965123327ca00f34fc`, the earlier `OWNER-CHOICE.md`,
disposition G27-02, two independent analyses, and G's subsequent source reading.
The original answer is preserved locally at
`LOCAL/raw/e02-execution-20261027/decisions/G27-02-20261028-r1/original.txt`
with SHA-256 `06592ba45317dc2343a94da736672fc9f49b93a5772d840b49f2089411ac1d14`.
This English record is a translation of that answer; the local RAW path is not a
claim that the original bytes have been committed or published.

This is an architecture decision, not code acceptance or finding closure. The
answer reported no runtime checks. The selected current-use chain is not claimed
implemented or verified here: `code_acceptance=false`, `closure_ids=[]`, and
runtime verification is `UNRUN`. The earlier bounded B13 witness and the historical
B198 disposition remain unchanged. G's original response said it had changed no
code, index, refs, or files; it supplied the full text to the coordinator.

## 1. Chosen path and authority boundary

Extend the existing Fabric producer of materialized SQL snapshots and consolidate
durable source state and admission within the existing `DecisionValidityService`.
Do not create a second simulation-specific ledger.

The first source family is a PolicyOS-registered SQL materialization with explicit
admission and withdrawal for a specified use. PolicyOS attests which verified
snapshot it admitted, for what use, and when that admission was withdrawn. This
is not an attestation of the external SQL database's currentness, the completeness
of its contents, or the detection of all its changes. A new materialization alone
does not withdraw the old one or render the earlier calculation scientifically
incorrect.

This is the bounded first mechanism for the remaining G27-02 property: the real
owner withdraws the shared basis admission, after which a fresh consumer stops
authorizing dependent use of the result. Its check must not be described as proof
of arbitrary external SQL change detection.

DataForge is not selected for this path: the examined path has no specific
DataForge issuer/commit contract owning the RES-03 source actually consumed. This
is a finding about the examined source and route, not a repository-wide absence
claim.

## 2. Existing owners and the missing part

These source paths and observations refer to the immutable source identified
above; paths below are relative to `policy-engine/src/polisyos/`.

| Existing owner | Reuse | Do not attribute to it |
| --- | --- | --- |
| `scientist/adapters/fabric_bridge.py:114–241`, `DefaultFabricPort.snapshot` | Read the request, obtain data, persist payload, schema and quality, and produce DataSnapshot 0.3. | Durable source registration, withdrawal, or external currentness. |
| `fabric/connectors/sources/sql_query.py:209–268` | Real SQL read, observed bytes, content hash and acquisition time. | Authority over external database commits; `completeness=1.0` does not prove source completeness. |
| `scientist/validation/decision_validity.py` | Existing validity owner, dependencies, reaction rules, serialization and file-persistence helpers. | An already available crash-atomic transaction across several files. |
| `foundry/execute/api.py`, `FoundryExecutionInputBasis` | Admission of the selected single-step execution basis. | A complete dynamic readset of every plugin or backend. |
| `scientist/methods/research_dag/invalidation.py` | Applicable existing propagation logic. | Production of the source event or proof that scheduling prerequisites were actually consumed. |
| `runtime/http/services/debug.py:392–585` | Verified selected-result/final-state binding and the fresh served consumer. | An already implemented source-currentness check. |

The new scope extends and consolidates these owners. The missing registration,
issuer, committed head, and reader bridge must not be claimed to exist already.

## 3. Stable identity

Keep source/view identity, a materialization revision, and admission for use
distinct. The proposed keys are:

```text
source_view_scope = tenant_id + cell_id + owner-issued source_incarnation_id
                  + versioned effective_view_contract_ref
admission_scope   = source_view_scope + versioned use_contract_ref
```

- The internal owner that registered the source issues `source_incarnation_id`.
  It survives rereads and credential rotation. Replacing the logical source
  requires explicit new registration or migration.
- `effective_view_contract_ref` binds the view actually executed: the selected
  provider, SQL/table/query and parameters, applied restrictions, projection,
  paging/limit and relevant profile semantics. A requested filter ignored by the
  connector must not be recorded as applied.
- The provider must be explicitly selected and bound. Discovery by `dataset_id`
  alone is insufficient for this authority-bearing chain.
- A URL, credentials, `request_id`, dataset name, timestamp, or content hash is
  not individually that key. Credentials and secret parameters are not published;
  necessary protected bindings stay in protected owner storage.
- Each revision separately binds the full identities of request, snapshot and
  required inputs, including `(id, kind, media_type, selected_profile)`, as well
  as registration and the producer/admission rule version.

Identical bytes can have distinct acquisition occurrences. CAS content
deduplication must not erase the history of those occurrences or their admission.

## 4. Commit and withdrawal boundary

For the first family, the authoritative commit is the internal owner's commit of
the verified materialization's admission. It is neither the SQL `SELECT` nor the
appearance of a new CAS object:

1. Fabric obtains the data through the specifically bound provider and persists
   the necessary immutable artifacts.
2. The admission owner resolves and checks the references, content, and match to
   the registered scope.
3. An authorized internal service capability commits genesis or a transition in
   the existing validity owner.
4. Only a successfully committed transition can ground the current-use
   projection.

Issuer identity comes from trusted runtime/provider configuration and the
calling service's verifiable authority. An issuer string, a caller-provided
`source_ref`, or a supplied dependency list does not create authority. An external
issuer may supply typed evidence; its assertion must not automatically become an
internally verified fact.

The operations have separate semantics:

- **Genesis:** explicitly create the registered scope and first state. An absent
  journal does not mean admission is valid.
- **Publish/admit:** register a new verified revision.
- **Supersede:** explicitly change the selected revision in a named use contract;
  this does not automatically withdraw every historical use.
- **Withdraw:** withdraw the exact revision in the exact admission scope.
- **Readmit/restore:** commit a new transition with a new generation; an old token
  does not become valid again.

In the minimum first profile, a transition takes effect at commit. Observation
time, upstream-asserted time, and committed time remain distinct. Committed
sequence determines order; timestamps are not sorted to infer it. A withdrawal
of revision A arriving after B must affect A, not accidentally withdraw B. An
exact retry is idempotent; the same event ID with different content is a conflict.
A missing predecessor must not silently advance the head.

## 5. One crash-consistent commit in the validity owner

The existing `owner_transaction()` uses `RLock` plus `flock` to serialize
operations. Several successive atomic file replacements are not thereby a single
transaction. In the source basis, `record_dependency_event` persists dedupe before
applying the event; a crash after that write can leave the event marked processed
without its full effect.

Use an immutable committed generation with one atomically published root pointer
in the existing store. Its minimum invariants are:

- A generation binds source facts and heads, event identity, registrations, and
  the required admission states. Referenced objects are made durable first.
- Under the existing owner fence, check the expected predecessor, then publish one
  root pointer with a monotonic generation by atomic replacement and `fsync`.
  Readers use only the committed root.
- A crash before publication leaves the old state; after a successful durable
  commit, it leaves the new state. Resolve an uncertain operation outcome by
  reading the root and retrying idempotently.
- Dedupe belongs to the committed event; it is not a separate advance permission
  to skip work.
- Fan-out and dependency indexes are recoverable projections. Their incomplete
  update must not leave a false current-positive.
- Persist an event even when no consumers are registered. Late registration and
  a fresh read reconcile against already committed source facts.

Do not copy the whole journal and every packet on each transition: the immutable
root may reference reusable index parts. Do not scan the whole journal on each
GET. One admission/read interface serves the relevant existing packet dependencies
and simulation consumers. A migrating scope must not have two simultaneous
authority-bearing stores.

The first profile is bounded to a verified local storage backend and its
particular durability and locking semantics. This decision does not claim
distributed consistency.

## 6. Fresh reader and consistency point

In the existing served reader:

1. Select the result through owner-traced terminal finalization.
2. Perform canonical exact-reference and bounded Foundry source admission.
3. Bind the actually verified basis to registered admission scopes.
4. Obtain one consistent committed validity state.
5. Produce a current-use outcome carrying generation, rule version, and the
   boundary of what was checked.

For the preferred first mechanism, read immutable CAS objects outside the short
critical section; check source heads and admission and select the generation
under the common owner fence. The guarantee is that the result is admitted for
the specified use according to committed state `G` at the **decisive read's
linearization point**. A withdrawal committed before that point must be observed;
a withdrawal after it may validly follow the read. Neither a token nor this fence
promises that the answer remains current until network delivery.

A missing head, wrong scope/profile, unverified lineage, or incomplete required
basis cannot produce a current-positive. A historical candidate remains
available with an explicit limitation. In particular:

- Preserve `FoundryExecutionInputBasis.authority_purpose="execution_input_identity_only"`.
- A direct manifest edge does not verify unsupported nested, plugin, or external
  reads. A scheduling prerequisite does not become a consumed dependency.
- A shared root generation may change because of an independent source; that
  alone must not invalidate an independent result.
- The current-use projection is not a general scientific or legal admissibility
  claim. Apply the check to both default selection and explicit artifact
  selection; caching must not bypass it.

Do not rewrite the original `SimulationResult`, workflow success markers, or
history. Current fitness is a separate projection of the existing owner, and its
substantive outcome must be machine-readable, not merely a textual warning.

## 7. Migration and companions

- Preserve the historical interpretation of old artifacts. Do not reconstruct
  genesis or currentness from an empty journal, a timestamp, or one existing
  snapshot.
- Mark current-use as explicitly unverified for legacy or uncovered modes; where
  necessary require a new, real admission.
- Version the extensions to existing lineage, dependency and admission contracts
  and the committed-root representation.
- Include provider/issuer binding, the Fabric producer, the validity persistence
  and read path, the selected-basis bridge, the fresh API projection, and affected
  DTO, generated, and client consumers. Do not expose protected references through
  the public Research DAG.
- Reuse the existing terminal-finalization correction. At the decision source it
  is already in `runtime/http/services/adapters/core_run.py:487–520`: commit
  `d6ec80604dd044bafb649e11ca3360aaaeee674a` is an ancestor of the source cut.
  The older `OWNER-CHOICE.md` description is historical, not a current unfixed
  source defect. Runtime qualification of that correction remains separate and
  `UNRUN` at this decision.

## 8. Minimum falsifier and mandatory controls

The primary scenario must exercise the actual chain:

1. The real Fabric producer creates registered materialization A.
2. A real selected-basis run persists a positive dependent result D; separately,
   result I is persisted on another basis.
3. A fresh reader confirms bounded current-use for both.
4. An authorized owner actually commits withdrawal of A for the applicable use
   contract.
5. Without changing result bytes, success markers, or original references, a
   new reader/process reads the results.
6. D no longer receives current-use validity; I retains it, and both histories
   remain readable.
7. Removing the owner-currentness gate while retaining all markers makes the test
   fail.

The required bounded controls are:

- Event before registration; restart and retry.
- Failpoints around commit and during fan-out.
- Duplicate and conflicting duplicate; reordering and a predecessor gap.
- Wrong tenant, cell, view, or profile.
- Withdrawal of A after B; a new materialization without withdrawal.
- Both GET/withdrawal orderings using barriers.
- Restore with a new generation, without ABA revival of the old token.
- Absent genesis and legacy history.
- A hidden unsupported source read and an unused scheduling prerequisite.
- Removal of the retained result reference with success markers preserved,
  separately from a corrupt or wrong reference.

Assert the real outcome and generation, not merely HTTP status, field presence,
or receipt markers.

## Pattern pass and acceptance boundary

The existing gap is an incomplete producer-to-admission-to-fresh-consumer chain
(P01/P02), with authority and time boundaries that must remain explicit (P05/P08).
A caller's string or dependency list is not authority (P32/P37), and an HTTP status
or marker is not the property (P29/P38). The target is a single owner-backed,
content-bound committed admission, a bounded selected-basis bridge and a fenced
fresh consumer; the adversarial controls above test that property rather than a
proxy (P31/P33). Classify the decisive predicate's provenance under P37, freeze it
at admission, and fail closed when it is merely consumer-asserted,
institutionally supplied, or not established. This decision identifies missing
registration, issuer, head, reader bridge, and verification; it does not establish
a completed capability. The relevant state remains `verification_missing` until
an actual source-bound chain and its semantic controls are demonstrated.

For this internal scope an external production issuer is not required. A claim
about currentness of the external SQL database would require a separate
verifiable source revision/transaction contract; this mechanism does not replace
one. Architecture selection, source implementation, executed evidence, G code
acceptance, and formal closure remain separate acts.
