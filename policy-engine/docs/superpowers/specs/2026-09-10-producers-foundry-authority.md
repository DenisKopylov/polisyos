# Foundry runtime authority: measured absence and scheduling proposal

Date: 2026-09-10. Research base:
`a534024ee28dfd9ac4fd21be1ff769b253722d8e`. Requirement:
`foundry-runtime-authority-capabilities-absent`. Status: **research complete;
engineering task proposed, pending architect ratification and row linkage**.
No source/test changes or test executions were made for this research. Paths
are relative to `policy-engine/`; `path@sha` citations below identify Git blobs.
DEBT-REGISTER and LEDGER supply requirements, never evidence about the code.

## Decision

Take the user-permitted scheduling route. The production authority path really
does refuse before the required runtime authority capabilities, while existing
candidate observation, profile reduction and diagnostic machinery are substantial
and should be reused. Building a declaration shell or flipping the capability
registry to `implemented` would manufacture the very authority the boundary
currently withholds. The four capabilities require a coordinated engineering
task with an explicit writer model, admission source, persisted evidence and
consumer integration.

At the pinned base the task is **NOT REGISTERED** in the active planning corpus.
The root lane has now authored `docs/plans/active/foundry-runtime-authority.md`,
task **FR-AUTH-01**, under the user's scheduling authorization, with status
**proposed** and engineering execution **not started**. This research subtask
read that local artifact; root owns its commit and branch readback. Its scope
owner is the Foundry catalog/discovery boundary, with accountable engineering
allocation still outstanding and Runtime as consumer collaborator. The artifact
explicitly distinguishes the scheduling proposal from an architect verdict,
institutional appointment and capability implementation. It asks the architect
to place the task in the execution order; the GY §8.5 status mechanism must be
respected if that plan is selected for the accepted task's standing.

The target row's alternative closure
requires an architect scheduling act **and the row pointing to it**. Because
DEBT-REGISTER and LEDGER are outside the write scope, architect ratification and
the row-pointer update remain explicit outstanding actions even after an active
task artifact is committed. Do not claim row closure.

The separate GY-DEF22 owner-adjudication appointment is not this task. An
institutional signer remaining unappointed cannot justify withholding engineering
work on these four capabilities; it limits the authority claims the resulting
mechanism may admit. Conversely, writing this plan cannot appoint that signer.

## Source findings

**FA-F01 — the registry is corroborated by a refusing production implementation.**
`method_catalog_dependency_authority.toml` records the four requested capabilities
as `absent/unallocated`, with empty toolchain admissions, launcher profiles, root
keys and production-data trust-policy lists. This alone would be weak evidence.
The corroboration is `build_production_method_catalog_dependency_authority`, which
constructs `_ProductionMethodCatalogDependencyAuthority` with an exact
`_NoRuntimeSubtreeCutoffAuthority`. The resolver first verifies canonical source,
then invokes cutoff preflight and returns `build_runtime_cutoff_refusal`.
Its result union has source-rejected, source-not-established and
runtime-cutoff-not-established arms; the current public graph has no positive
authority arm. `_validate_authority_registry` also rejects populated authority
lists and a different capability denominator: adding registry rows alone cannot
activate an admission mechanism.

- `architecture/production_quality/method_catalog_dependency_authority.toml@9b7a02c9ca93f830074ccc181e93e091de88c6f7`.
- `src/polisyos/foundry/methods/catalog/dependency_authority.py@d42e2791ca22eb514bc0376170973fba07310995`,
  `_validate_authority_registry`, `_NoRuntimeSubtreeCutoffAuthority.preflight`,
  `_ProductionMethodCatalogDependencyAuthority.resolve`,
  `build_production_method_catalog_dependency_authority` and
  `validate_negative_only_dependency_authority_abi`.
- `architecture/production_quality/method_catalog_dependency_digest_domains.toml@caf4fa98a0669f6d81bd8b5db0014cb015b9492f`,
  the `owner_enforced_runtime_subtree_cutoff` predicate's
  `not_established_only` branch.

**FA-F02 — nearest implementations do not provide the missing authority.**

| Required capability | Nearest existing implementation | Why it does not discharge the property |
| --- | --- | --- |
| `owner_enforced_runtime_subtree_cutoff` | `observe_candidate_python_runtime`, `_walk_candidate_python_runtime`, `build_candidate_python_runtime_installation`; descriptor-bound POSIX observations and two manifest walks | The observer expressly produces a candidate without a common cutoff. A writer can change a file after its second observation while the retained manifests remain equal. The production preflight is `_NoRuntimeSubtreeCutoffAuthority`, so observation cannot promote itself. |
| `owner_resolved_resolution_receipt_store` | `ArtifactStoreFoundryDependencyAuthorityRepository`, `FileSystemCASSignedRecordRepository`, content-bound receipt DTOs | The evidence repository reads blobs/capsules. `persist_binding_index` raises an absent-capability error; `_open_production_dependency_authority_repository` raises rather than supplying an owner-resolved writer. Existing CAS storage is not an admitted receipt custody service. |
| `platform_toolchain_admission` | `PythonRuntimeAdmission`, runtime installation/observation statements and candidate installation builders | `_ProductionPythonRuntimeInstallationAuthority.attest_after_install` and `resolve_installed_root` call the absent cutoff and return a not-established predicate. The selected production composition cannot accept an ambient installation report as an admission. |
| `production_data_trust_policy` | `ProductionDataTrustPolicyStatement`, trust/appointment/custody DTOs, `resolve_candidate_production_data_root_access`, candidate manifest reader | `_ProductionFoundryTrustResolver.resolve` always returns trust-not-established; mount/root-access production owners also refuse. Candidate access to a path or a content-bound manifest does not establish whose production data may be trusted for this purpose and time. |

The authority source for this table is the FA-F01 code blob, by the named symbols,
plus `src/polisyos/foundry/methods/catalog/dependency_evidence.py@0ab4c2fe4fea437a5c76904859abb83e94c369d3`
for the types and
`src/polisyos/foundry/methods/catalog/dependency_profile.py@33e250d5e977708bd57a3c9e1ac3de66b447cbdb`
for `DependencyProfileEnvironmentReceipt`, `read_candidate_production_data_manifest`
and `diagnose_dependency_environment`. The environment receipt's predicate is
constrained to `recomputed`; its docstring explicitly excludes writer-independent
custody. The diagnostic may reconcile observed coordinates and still produces
only a diagnostic. Calling these complete capabilities because the types exist
would be P01/P37.

**FA-F03 — the complete source census and explicit calls agree with the refusal
graph.** The root's existing `production_invocation.py` audit is retained at
`docs/superpowers/journals/producers/verification/raw/base-invocation.json`:
2,654 source Python files / 5,669 total tracked Python files, base/current sets
equal, exit 0 and no source delta. It is a static diagnostic, not a proof that
an authority-producing runtime path executed.

An independent `ast` walk parsed the complete 2,654 tracked
`policy-engine/src/**/*.py` files with zero parse errors, visiting classes,
regular and async definitions, and calls. Querying the delivered vocabulary
found the production factory's `_NoRuntimeSubtreeCutoffAuthority` construction;
the public runtime-identity and provenance builders each call that factory in
`catalog/snapshot.py`. The two explicit calls to `observe_candidate_python_runtime`
are inside `build_candidate_python_runtime_installation` and
`_observe_and_verify_candidate_python_runtime`, not the production resolver.
`PythonRuntimeAdmission`, `ProductionDataTrustPolicyStatement` and
`PersistedTrustResolutionReceipt` have definitions but no constructor calls in
that source denominator. This syntactic result is bounded: it is not a
claim about arbitrary dynamic Python loading. The production constructor,
public-result union and backward consumer trace establish the relevant behavior.

**FA-F04 — two backward traces distinguish diagnostics from authority.** The
public `build_method_catalog_runtime_identity` discards its snapshot input and
delegates to the production authority factory. The public
`build_method_catalog_provenance_manifest` likewise discards snapshot, registry
report and ambient manifest before delegating. Candidate builders remain separate
private functions. Source:
`src/polisyos/foundry/methods/catalog/snapshot.py@39afd41e5b87c407f0e740b39aa4fcd8d4eee906`.

The N8 consumer independently resolves the public builder path in
`_build_catalog_denominator_evidence_transport` and requires runtime-identity and
provenance results to agree. Its diagnostic companion path instead invokes
`validate_foundry_dependency_discriminant` →
`_validate_foundry_dependency_discriminant` →
`_dependency_environment_ambient_findings` →
`diagnose_dependency_environment`. The returned `ValueGateValidationResult`
retains `legacy.governing_issues` in both success and invalid-companion branches;
diagnostic findings are added only to `ambient_findings`.
`_value_dependency_diagnostic` in the governed HTTP worker calls that same N8
validator and projects `decision_role="ambient_non_decisive"`. A failed or absent
ambient probe becomes a diagnostic non-receipt rather than a governing verdict.

- `tools/quality/validation/check_layer3_gy_value_gate_contract.py@c23d1a1e0946fa38a8d79090c169195cb121aaaf`,
  the named transport and validation functions.
- `src/polisyos/runtime/http/services/governed_projection_validation_worker.py@552129d3b5010bdf8198282907495164c03efe73`,
  `_value_dependency_diagnostic`, `_dependency_diagnostic_nonreceipt` and
  `_validate_request`.

## Active-plan census and real scheduling requirement

**FA-F05 — no matching task is registered at the base.** A script enumerated the
entire pinned `docs/plans/active/` tree: **123 tracked paths = 92 Markdown + 22
JSON + 3 PNG + 3 ZIP + 3 WebM**. It read every Markdown and JSON artifact and
parsed all 22 JSON files without errors. The four exact capability IDs and the
target row ID occur only in DEBT-REGISTER and LEDGER. Excluding those two
requirements/status files leaves **90 Markdown and 22 JSON artifacts** with no
exact matching scheduling declaration. Media files were excluded from text
task matching and are identified in the denominator, not silently omitted.

To avoid treating vocabulary search as a task oracle, the active GY task-standing
table and build-task sections, and the Foundry remediation workstreams, were also
read. GY §8.5's closing note mentions an “owner-enforced runtime cutoff” without
a named build task; its GY-N12 row records the already-delivered negative and
non-decisive route, which is not a schedule to build the positive authority
subsystem. The older Foundry remediation plan has general reproducibility and
catalog workstreams, not a task with these four outputs and their writer model.
The GY note's adjacency to institutional signers is not authority to classify
this engineering subsystem as an appointment-only task.

- `docs/plans/active/layer3-slices/GY-engine-subordination.md@9527c8b9c193ab215c0c8b9257317b3df9b62c8c`,
  §8.5 standing rules, GY-N12 row and closing note; §9 build tasks.
- `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md@5be10b44a068dba88995809ab8e7cd7747698a5b`,
  Phase 4 and WS-7/WS-10.

The proposed task must include these obligations before “scheduled” can be a
meaningful claim:

1. **Scope and ownership:** Foundry catalog/discovery owns correctness; Runtime
   consumes the result. Resolve engineering ownership separately from external
   institutional evidence. Preserve the current refusal while prerequisites are
   absent. Do not reopen GY-DEF22's adjudication appointment in this task.
2. **Writer-independent cutoff:** define the actual protected interval, allowed
   writers, executable/root/descendant-byte closure and enforcement primitive.
   Demonstrate a mutation after the second candidate walk is denied or changes
   the admitted result. More repeated walks or a self-declared timestamp do not
   satisfy this obligation.
3. **Owner-resolved receipt persistence:** reuse Core CAS and existing Foundry
   evidence contracts, but supply the real authoritative writer/resolver, content
   and scope binding, persisted readback, lineage/time/revocation rules and
   consumer. Present-but-forged, stale, cross-environment and replacement receipts
   must fail. A path string or a receipt-shaped JSON file is insufficient.
4. **Platform/toolchain admission:** wire admitted Python/uv/platform evidence to
   the exact executable/root/installation and retained cutoff receipt. Source
   identity, runtime-instance identity and observed package coordinates remain
   distinct. Test copied runtimes, redirected executables and swapped installs.
5. **Production-data trust:** establish purpose/role/root/content bindings and
   trust-policy verification through the existing owner interfaces, with
   revocation/time and tenant scope. Missing external evidence remains typed-empty
   and cannot be replaced with a local test signer in production.
6. **Composition and consumer:** evolve the currently negative-only result
   contract deliberately, with versioned rules and source-derived negative
   coverage. The non-test caller remains the public snapshot builders →
   `build_production_method_catalog_dependency_authority().resolve`; N8's existing
   transport is the consumer. Any positive artifact must be persisted, read back,
   resolved and consumed there. Diagnostic success never supplies a missing
   predicate. Name the runnable owner boundary before implementation; do not add
   a shell merely to print an authority-looking result.
7. **Acceptance:** one real producer → persisted receipt → default consumer →
   machine/audit projection run, plus each above refusal and an unchanged-test
   removal falsifier. Only verified authority evidence may change an authority
   verdict. Test that mixed outcomes compose fail-closed. Preserve the existing
   non-decisive diagnostic path as the default until the entire chain qualifies.

## Narrow verification for this task

No new tests are necessary to verify the current refusal and diagnostic boundary.
Run exact existing nodes, never whole test files:

| Property | Exact selector |
| --- | --- |
| Production stops before candidate machinery | `tests/unit/foundry/methods/test_dependency_profile.py::test_no_runtime_cutoff_preflight_blocks_before_sync_or_candidate_generation` |
| Equal candidate walks do not prove a writer cutoff | `tests/unit/foundry/methods/test_dependency_profile.py::test_barriered_write_after_second_post_fstat_preserves_equal_candidate_manifests` |
| Candidate positive input cannot be injected into the public builder | `tests/unit/foundry/methods/test_dependency_profile.py::test_public_builders_reject_caller_constructed_positive_profile` |
| Reconciled diagnostic failure has no governing effect | `tests/unit/runtime/quality/test_value_gate.py::test_n8_dependency_discriminant_matching_supplied_fail_is_ambient_only` |
| Claimed pass must reconcile to current observation | `tests/unit/runtime/quality/test_value_gate.py::test_n8_dependency_discriminant_supplied_pass_requires_current_recomputation` |
| HTTP-worker diagnostic failures preserve the governing result | `tests/unit/runtime/http/test_governed_projection_validation_worker.py::test_value_gate_worker_diagnostic_exception_cannot_change_governing_status` |

Test sources are pinned as
`tests/unit/foundry/methods/test_dependency_profile.py@1f0881efd4dd12dd1d9b0dce9ce5bbaa421e3a99`,
`tests/unit/runtime/quality/test_value_gate.py@0a456de37782a7f6c89014a8cb9550334e1767e2`,
and `tests/unit/runtime/http/test_governed_projection_validation_worker.py@e21a71650c4db69000cb8b3ad7d5f0d0f72f16b0`.
The barriered-write witness already mutates real runtime fixture bytes after the
second post-fstat observation, demonstrates equal retained candidate manifests
despite the mutation, and separately requires the production cutoff refusal.
That is a substantive falsifier of “two equal walks establish runtime authority.”

For an **unchanged-negative removal probe**, use an isolated interpreter to
replace only `_validate_foundry_dependency_discriminant`'s returned governing
result with `governing_issues + ambient_findings` after running its original
implementation. Retain the actual producer, companion, diagnostic payload,
`ambient_non_decisive` markers and all test text. `dataclasses.replace` can make
that one consumer mutation because `ValueGateValidationResult` is frozen.
Run `test_n8_dependency_discriminant_matching_supplied_fail_is_ambient_only`
unchanged: it must fail at equality to `_legacy_n8_governing_issues`, showing
that the test guards the separation property, not a marker. An import failure,
source-pin failure or a test that never reaches that equality is not the needed
receipt. Run the normal node again in a fresh process afterward. Root retains
complete gate and probe output under the existing gitignored raw directory.

## Pattern pass and final claim boundary

P01/P02/P27: extend the existing owner ports and consumers; do not count DTOs or
candidate builders as a complete authority chain. P29/P32: real bound evidence
and removal probes, not self-attested status or registry shape. P35: the source
and plan denominators are separate and complete, with explicit media exclusions.
P37/P38: candidate runtime walks and dependency profiles are `recomputed`; the
absence of a writer-independent cutoff, authoritative receipt custody,
toolchain admission and production-data trust is `not_established` for authority.
The divergent case is the real post-observation writer mutation that equal
candidate manifests miss. No consumer may promote that observation.

P40 bucket rule: another candidate filesystem race, copied tree or receipt-shaped
artifact that lacks the declared writer-independent boundary is the same bounded
absence class, not a request for another per-instance repair. The task must widen
to an enforceable writer model or retain the limitation. A present consumer that
actually uses ambient diagnostics to decide authority is a new class and requires
its own traced repair. Do not turn a hypothetical future positive path into an
infinite verification ladder. P41 applies to every fresh gate failure; ownership
cannot be assigned from historical pass counts or a nearer base.

The four authority capabilities remain `absent/unallocated` as admitted
production capabilities, despite existing types, candidate producers and refusing
ports. The current fail-closed boundary and non-decisive diagnostic chain are
implemented mechanisms whose fresh verification is still pending. A committed
pending-ratification task is scheduling progress only. Neither it nor this spec
discharges the architect's act, the protected debt-row link, an institutional
appointment, or a positive runtime-authority claim.
