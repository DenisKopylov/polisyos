# Global case index: verify the delivered producer and preserve its scope

Date: 2026-09-10. Stage: research and decision proposal; no test execution or
mechanism changes in this document's preparation. Source base:
`a534024ee28dfd9ac4fd21be1ff769b253722d8e`. Target requirement:
`global-case-index-producer-missing` only. Paths below are relative to
`policy-engine/`; `path@<40-character SHA>` denotes a Git blob unless a commit is
explicitly named. The debt row and its dependent rows were read as requirements,
never used as evidence of source state. No register or LEDGER edit is proposed here.

## Decision

Reuse and verify the September 7 producer. `GlobalCaseIndexProducer.produce` is
already called by the default HTTP capability provider, persists and reads back a
snapshot, and resolves the canonical PDC binding, design record and search ledger
before emitting an entry. Building another producer would duplicate that chain.
The delivered product is **candidate discovery over tenant/cell-visible persisted
S2 bindings across runs**. It does not establish a universal case population,
terminal-run completion, a single current record per logical case, or policy
authority. The broader row cannot close merely because its named HTTP test passes.

The engineering allocation premise also needs reconciliation before closeout.
The active Atlas plan's **DS12, “Debt rows this slice must close”,
`global-case-index-producer-missing` bullet** expressly allocates the producer to
DS12 on September 1; **DS13, “Debt rows this slice must close”** assigns browse,
contest and history consumption to DS13 and says that producer delivery alone
does not close `ds8-global-case-index`. These are identified planning obligations,
not code measurements. The target row's remaining “engineering unallocated”
wording therefore must not be recast as a missing institutional signing mandate.
Source: `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@d956553af570f5f2d2040241aad58f374001da0c`,
DS12 lines 1785–1790 and DS13 lines 1945–1951 at the pinned base.

Recommended disposition after verification: report the limited producer chain as
implemented within its declared coverage, then return the exact broader coverage
and row-status decision to the architect under the existing DS12 allocation.
DS13 remains the already-active consumption task; do not invent a new deferral,
close its dependent row, or build its surfaces in this task. If the architect
requires a different universal case denominator, that requirement needs explicit
registration or amendment under DS12 before it can become a source contract.
Nothing here appoints a signer or fills `authority_owner_ref`.

## Findings from the tree and history

**GI-F01 — the absent-producer diagnosis is superseded by source.** Commit
`d207b82f5f231fc0ea8653027b2576b33d6a71b2` added
`runtime/quality/global_case_index.py`, installed the default case provider,
added `GlobalCaseIndexOwnerReceipt` to result admission, and removed the
composer's unconditional rejection of a `case` provider. Reading that commit's
parent and diff establishes the old blocker and its repair directly. The current
producer blob is `src/polisyos/runtime/quality/global_case_index.py@59e6c3a8759a603fd03a563ddcd647fc673e7186`;
the provider and consumer blob is
`src/polisyos/runtime/quality/capability_discovery.py@a6ccf3f9afc148cec1dcf0e4e068306c83951557`.
Historical journal statements are not fresh execution receipts for this base.

**GI-F02 — independent AST evidence finds an explicit production call.** A
separate Python `ast` walk parsed the complete `git ls-files
'policy-engine/src/**/*.py'` set: **2,654 tracked source Python files; zero parse
errors**. It visits `ClassDef`, `FunctionDef`, `AsyncFunctionDef`, `Import`,
`ImportFrom` and `Call`; it does not derive call counts from regex matches. The
same complete denominator contains one import of the index module, the local
import in `GlobalCaseIndexCapabilityDiscoveryProvider.search`, with no aliases,
and one explicit index-producer construction, used immediately by
`GlobalCaseIndexProducer(store).produce()` at line 569. The default provider
constructor appears at line 130 of `resolve_control_registry_providers`.
These are static findings, not an execution receipt or a proof about arbitrary
dynamic loading. The root task's existing `production_invocation.py` census
completed at exit 0 over **2,654 source / 5,669 total tracked Python files**,
with identical base/current sets and no source delta or regression. Its
`raw/base-invocation.json` marks `GlobalCaseIndexProducer.produce` and provider
`search` as uninvoked: its receiver/callback model does not resolve this immediate
constructed receiver and injected provider path. This is a tool limitation,
not evidence of `bridge_missing`. The explicit AST call above, the manual HTTP
trace below, and fresh runtime witnesses must reconcile that diagnostic; do not
describe the scanner as proving a runnable path it did not resolve.

**GI-F03 — the input is an existing persisted producer vocabulary.**
`persist_s2_design_search_run` creates `DesignRecordV0`, PDC `SearchLedger` and
`RunBoundDesignRecordBinding` CAS artifacts with the PDC producer identity, exact
schema, content digests and run/tenant/cell binding. Its explicit source caller
is `execute_s2_design_search_operation`. That operation is reached through
`WorkspaceLoop.execute_registered_s2_design_search_operation` and
`ControlPlaneWorkspaceLoopTransitionMixin._execute_s2_design_search_operation`;
the mixin dispatches the exact `phase2.refine.layer2_s2_design_search` operation
from workflow state. The source producer is not a test-local case store.

- `src/polisyos/pdc/_impl/layer2_design_search.py@9c308a94c582c05efb429b3665530beab7e4819c`,
  `RunBoundDesignRecordBinding` and `persist_s2_design_search_run`.
- `src/polisyos/runtime/quality/workspace/s2_design_search_operation.py@0bf01c217a2562aa62ef75cbc3b415df69ae39eb`,
  `execute_s2_design_search_operation`.
- `src/polisyos/runtime/quality/workspace/loop.py@a7d4911a8c8708150e85ce560dc9f2bb78f0a1f6`,
  `build_workspace_operation_registry` and
  `WorkspaceLoop.execute_registered_s2_design_search_operation`.
- `src/polisyos/runtime/http/services/control/workspace_loop_transition.py@212fbbac18cb6f6bdf3efc0ec103cea6eae42e29`,
  `ControlPlaneWorkspaceLoopTransitionMixin` dispatch and execution methods.

**GI-F04 — the index derives a scoped artifact denominator, not a global-case
truth predicate.** `produce` requires ambient tenant context, obtains a native
`FileSystemCAS.for_tenant` view, enumerates its artifact IDs, selects the exact
`policyos.pdc.run_bound_design_record_binding` kind, and calls `_resolve_entry`
for each selected artifact. `_verified_payload` resolves schema, producer and
content integrity; `_resolve_entry` compares the resolved record and ledger to
the binding and rejects empty/blank instrument-family coverage. It does not
substitute a `case_id` or field name for vocabulary values. One entry is emitted
per binding: no claim of one entry per logical case is warranted.

`FileSystemCAS.for_tenant` enables ownership enforcement and requires scope;
`iter_artifact_ids` filters sidecars through the native ownership index before
returning IDs. Thus “complete” refers to that returned visible CAS set at
enumeration, not all tenant stores, all institutions, all possible case
vocabularies, or a transactional world snapshot. Sources: GI-F01 producer blob;
`src/polisyos/core/artifacts/store.py@76cc3574f2bbbb102f47111872ac31f131c253fe`,
`for_tenant`, `_require_artifact_owner`, and `iter_artifact_ids`.

**GI-F05 — both persistence and the HTTP bridge exist.** `produce` persists
`GlobalCaseIndexSnapshot`, checks its content hash and CAS verification, and
validates readback equality. The provider consumes that readback, constructs
candidate rows and a search ledger, and persists a `GlobalCaseIndexOwnerReceipt`
whose result digest binds the selected rows, ledger, scope of search and
incompleteness. `CapabilityProviderSearchResult` recomputes that digest and
enforces the exact case receipt type. The receipt is a candidate-search receipt,
not an independent institutional signature. Provider persistence is a write;
the consumer uses the validated result returned in-process, so do not describe
the receipt as separately loaded and cryptographically verified by HTTP.

The backward consumer trace is:

```text
POST /api/v1/control/capabilities/search
  routes/control.search_capabilities
  ControlPlaneService.search_capabilities
  CapabilityDiscoveryService.search
  CapabilityDiscoveryComposer.search
  _ValidatedProvider.search
  GlobalCaseIndexCapabilityDiscoveryProvider.search
  GlobalCaseIndexProducer.produce
  _resolve_entry -> _verified_payload -> PDC CAS artifacts
```

The return path composes independent discovery, execution and authority postures,
then `ControlPlaneService.search_capabilities` persists the exact response packet.
Bootstrap installs the default provider in `resolve_control_registry_providers`
and `RuntimeServiceContainer.startup` binds the service; the control service calls each
provider's `bind_artifact_store` before serving requests. Registry-factory
overrides deliberately suppress defaults, and an explicitly injected case
provider replaces the default; the real closure witness must exercise ordinary
default construction. Sources:

- `src/polisyos/runtime/http/services/control_registry_providers.py@961f46b7999ab2c4b15c2a5ae3fcf0b0028265c4`.
- `src/polisyos/runtime/http/container.py@d6638eb8e85420d1e528a025895d792da76cd4d7`.
- `src/polisyos/runtime/http/services/control/run_lifecycle.py@9f8f81f227c43207d745b2cf0af6ba883b14bcc2`.
- `src/polisyos/runtime/http/services/control/capability_discovery.py@6cf10f86deebc20c92bc498fa7e8de0da3b1f42a`.
- `src/polisyos/runtime/http/routes/control.py@f1331c7da27c1d65688d484539063bda66b9357b`.
- GI-F01 provider/consumer blob, `CapabilityDiscoveryComposer` and
  `GlobalCaseIndexCapabilityDiscoveryProvider`.

**GI-F06 — scope remains explicit at the consumer.** The snapshot and case-owner
receipt constrain `authority_owner_ref` to `None`. The producer records
`s2_bindings_only` and `terminality_not_established`; the provider yields
`recall_unmeasured` or `budget_cutoff`, and excludes use for policy authority,
terminal completion and `global_case_population_claim`. It searches actual
family values alongside case labels and descriptions. Lack of matches does not
become a complete-global-population claim. Sources: GI-F01 blobs.

## Requirements, boundaries and alternatives

The exact target row requires a canonical global index, an appointed producer,
a provider bridge and its named HTTP test against the producer. Its September 7
coverage limit remains a requirement to disposition, not permission to silently
rename tenant-visible S2 inventory as universal coverage. The dependent DS8 and
DS10 rows do not close automatically. The active DS12/DS13 obligation split above
supplies real task routing; a field fixed to `None` is an authority limitation,
not evidence that the engineering task cannot run.

The import policy allows Runtime to consume PDC and Core, while PDC may consume
Core/IR/Common. The existing producer uses the public `polisyos.pdc` vocabulary
and native Core CAS, so the correct direction is already present. HTTP packages
are internal; `polisyos.runtime.quality` is a public-experimental facade, and a
facade change would require its usual surface review. No new export, module,
contract, enum or backend is proposed. Sources:
`architecture/imports/policy.toml@3ba18adb3a7d69dafe7c87ee5686968de0994ad4`,
`architecture/public_surface/contract.toml@11bf31254e4bb5a83b7eddec586a6dfd946b33a9`.

| Alternative | Decision and reason |
| --- | --- |
| Verify the delivered canonical binding index and retain its limitations | Selected. It exercises the existing producer, source reader, default bridge and persisted/API result. |
| Add a second “global” producer or derive an index from run lists and arbitrary `case_id` fields | Rejected. Duplicates ownership, weakens the input denominator and recreates P01/P27/P38. |
| Require an institutional appointment to run candidate discovery | Rejected. Engineering allocation and policy-signing authority are different acts; the emitted authority slot remains empty. |
| Close every dependent row because the named HTTP test passes | Rejected. It would erase the declared S2 coverage limit and DS13's separately assigned consumption obligation. |
| Expand to a universal case/current-head model during verification | Outside this task. DS12 owns the requirement decision; any new denominator must be explicit and source-backed before implementation. |

The production terminus is the authenticated HTTP route above. A new
`polisyos-tools` command is inappropriate for this work: tenant and cell scope
come from the authenticated request, and bypassing that context would change
the property being verified. The provider's `replay_command` value
`capability-discovery:global-case-index` is a ledger label, not evidence of a
registered runnable CLI. Do not count it as one or claim that fresh rebuilding
is byte-identical replay; `observed_at` intentionally changes. Snapshot readback
and a real HTTP invocation are the relevant receipts for this row.

## Verification design for the next stage

No tests have been run by this research subtask. Existing tests were inspected
at `tests/unit/runtime/quality/test_global_case_index.py@a9c874c35fcb54b345b38994ba59317bf9cb5248`
and `tests/unit/runtime/http/test_capability_discovery_api.py@9bfc22997767bd05479541a08613d165710cad78`.
Do not import September 7 pass counts as results for the present branch.

The exact row closure witness is:

```text
tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index
```

It uses the real S2 production writer, authenticated tenant/cell request and
default provider; checks actual family-value search against a field-name miss;
reads the resulting snapshot from CAS; and asserts candidate, non-executable,
non-authoritative, `recall_unmeasured` output. It begins by calling the production
S2 operation directly, so it proves discovery of real operation outputs, not
the earlier HTTP workflow dispatch itself.

Use these exact existing owner-test nodes as the narrow semantic wave, with the
common prefix `tests/unit/runtime/quality/test_global_case_index.py::`:

- `test_real_s2_producer_emits_persisted_content_bound_case_index`
- `test_case_field_names_do_not_identify_the_canonical_vocabulary`
- `test_linked_content_identity_must_match_binding`
- `test_canonical_kind_with_unverified_provenance_refuses_the_inventory`
- `test_missing_family_vocabulary_cannot_be_replaced_with_case_identity`
- `test_mutated_linked_bytes_refuse_even_after_a_successful_read`
- `test_new_bindings_join_the_next_complete_snapshot`
- `test_tenant_and_cell_views_never_reuse_another_scopes_cases`
- `test_missing_scope_cannot_emit_an_unscoped_inventory`

The real negative is `test_linked_content_identity_must_match_binding`: a real
persisted S2 run is followed by a shape-valid binding with a mismatched case,
ledger identity or record identity; resolution must raise `GlobalCaseIndexError`.
The source exists, its ref resolves and its schema is valid, so this cannot pass
merely by checking field presence. The missing-family node independently changes
and rebinds real ledger bytes, retaining valid hashes, and requires refusal.

**Source-reader removal probe:** in an isolated interpreter, compile an AST copy
of the existing `GlobalCaseIndexProducer.produce` method in which only the
`entries = tuple(_resolve_entry(...))` assignment becomes `entries = ()`.
Leave all source files and all test text unchanged, retain the `_resolve_entry`
definition and all schema/producer/snapshot markers, and run the unchanged
`test_linked_content_identity_must_match_binding` node. The required result is
an assertion failure because the malformed canonical source no longer raises;
an import/collection failure is not a successful falsifier. This probes removal
of the actual production source-reader call, not a hand-built surrogate producer.
Run the unchanged original node normally in a fresh process afterward. An
alternative narrower binding probe can remove only the case-ID comparison and
run the mismatched-case instance, but the source-reader probe covers the omitted
intake class without coupling its selector to pytest-generated parameter IDs.

**Selected single HTTP negative:** the inspected owner and API tests cover the
source rejection and HTTP positive separately. To establish a fresh end-to-end corrupt-source API refusal, add only
`tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_refuses_invalid_persisted_binding`.
Reuse the real S2 setup, create a canonical-kind binding whose case ID disagrees
with the resolved ledger, then request `case` through the default HTTP provider.
Require status 200 with empty results, `producer_unavailable` and the exact
`case:case_index_binding_content_mismatch` reason; never `producer_missing` or
an ordinary complete empty result. Read the persisted response back. Repeat the
same source-reader removal probe against this unchanged negative: a normal
`recall_unmeasured` response must make it red. Existing tests suffice for the
narrow delivered claim; this test is warranted only to strengthen that precise
end-to-end refusal claim, not to mirror implementation.

Retain full deciding output and removal-probe output in root-owned gitignored
raw receipts; report actual exits and wall times. Freeze the selected source and
tests before the verification wave. There is no shared database or fixed port:
CAS fixtures are per-test temporary roots. Root owns any edits and commits.

## Pattern pass and acceptance

Relevant rules were read before design and again at closeout preparation:
`docs/reference/policy-design-case-failure-patterns.md@efe428b76ac61ff5d22a4a52258496c6010b90b2`,
P01/P02/P03, P05/P10, P27/P29/P32/P35/P37/P38/P40/P41.

| Pattern | Observation and correct closure |
| --- | --- |
| P01/P02/P27 | A producer and bridge were delivered September 7. Verify their real caller and persisted readback; do not rebuild from the older missing-producer description. |
| P03/P05 | Candidate information reaches HTTP. Preserve empty authority and explicit denied uses; API existence does not establish a public, authoritative case population. |
| P29/P32/P37 | Content identity, schema, producer manifest and family values are recomputed from CAS, not taken from a caller's binding declaration alone. This proves local content admission, not an independent external institutional fact. |
| P35 | Source census covers all 2,654 tracked source Python files, includes async definitions, and has zero parse errors. The CAS scan denominator is separately tenant/cell-visible artifact IDs; never conflate these sets. |
| P38 | The property is valid candidate entries over visible persisted canonical S2 bindings. An HTTP 200, named test, `case` field, or `global` symbol would be a proxy for a broader universal-case claim. Concrete divergent case: an otherwise real case persisted under another vocabulary is outside this producer's binding selection. Its existence would not make the S2 scan fail, so the broader claim stays limited. |
| P40 | A finding about other case vocabularies, cross-store coverage, terminality or logical-case consolidation is the same declared coverage class at another level. Do not patch each variant. DS12 must choose the required denominator; subsequent variants are worked examples of the limitation. A failure to reject corrupted admitted S2 content or a default-provider bypass is a new class and gets its own bounded diagnosis. |
| P41 | A failed fresh gate is not inherited merely because source was unchanged in this document. Replay from the slice base and reconcile its complete input denominator before assigning ownership. |

For the scoped candidate chain, source inspection establishes contract, producer,
snapshot persistence/readback, bridge, consumer, HTTP surface and existing
semantic tests. Fresh execution evidence is pending in this stage; that fact
does not establish a new `verification_missing` capability defect and certainly
does not imply `producer_missing`. A broader universal-case or
DS13-history capability is outside the demonstrated claim and retains its
existing task obligations. Do not mislabel the entire chain `absent/unallocated`
when the canonical producer is visibly present.

Acceptance for the authorized verification work is: current-base static results
are reconciled with the explicit AST call and manually traced production path;
the named HTTP witness and selected
owner negatives pass; persisted snapshot/response readback is observed; the
unchanged negative becomes red when its real source-reader call is removed;
normal behavior passes again without a source mutation; the final disposition
states the S2/tenant/cell limits, separates engineering allocation from signing
authority, and leaves DS12/DS13 row decisions to their existing owners. No claim
of broader closure is earned by this document alone.
