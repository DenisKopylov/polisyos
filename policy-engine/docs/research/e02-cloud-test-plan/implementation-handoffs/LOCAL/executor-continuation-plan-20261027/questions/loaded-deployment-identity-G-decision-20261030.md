# G decision: canonical loaded execution and retained bindings

Date: 2026-10-30. Decision key: `G-LOADED-EXECUTION-20261030`.

**Disposition: select C, with bounded B mechanisms retained for discovery and reconciliation.** Extend the existing confidence-ledger owner with evidence of trusted source execution established before authority imports, retained actual bindings, and role-specific currentness checks. Do not continue the retrospective initializer-grammar repair ladder. A remains the fail-closed outcome until this producer and all required consumers are implemented and independently verified.

This is a source-bound architecture decision for implementation, not source acceptance, an implementation receipt, a claim that trusted bootstrap exists today, or a new E02 closure. `code_acceptance=false`; `closure_ids=[]`. Historical decisions, including B198 and B59, remain unchanged. General G acceptance remains paused. No product import, test, probe execution, environment change, cleanup, Git mutation, cloud task, or integration was performed for this decision. Only this document was written.

## 1. Source frame and evidence qualification

The assessed immutable author input is:

- Commit: `8e501aa0f24c02e5e2866e3ce13b0467f7fc0736`.
- Tree: `66b80e279e3f4895b6bac1e705e0a0ae2d20d1fd`.
- Checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`.
- Author branch: `codex/e02-unified-local-20261009`.
- `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py`: SHA-256 `f7e770b6d170dafcaaa9fe566355ff9b64dc138b38b29848726cda3dbf0206c8`.

All source line anchors below refer to that commit, not the moving working tree. The author continued independently during this review; a later observed HEAD was `80e2bd118c40d97db1601fe58d8dd8ec165a5f67`. It was not substituted for the assessed input. Publication of the assessed local commits was not verified here; the request identifies R125 at `e151479e...` as its latest published receipt.

The R152 receipt is `LOCAL/raw/e02-execution-20261027/runtime-prep/N7-identity-import-r152/result.json`, SHA-256 `ee680f6f31954c4e6cfdf584100f5bd6986cc3e5d49e65b125d6f7ca86fa8197`. Its own source is predecessor `4ccfa564f925d048f3c46dc0069ffcbfe028a13a`, tree `5f44a9eca496ff46472ee426daf457cfdcef9beb`. It reports a completed source import on CPython 3.14.3, reconciliation of 1,559 loaded first-party origin files against that frame, and an unavailable loaded identity. This is an author diagnostic, not an independent full-graph census at the newer input and not semantic PASS.

The exact refusal is `canonical_loaded_runtime_mismatch`, with detail `decorated direct source binding is unresolved: polisyos.core.artifacts.protocol.ArtifactReader`. The detail has 94 characters and SHA-256 `17159e0d906df9b6c0251643adaf41192d313e04f38a0590ac5e58d42a5839f4`. The ledger file hash agrees across the diagnostic and assessed input; this alone does not establish equivalence of their entire dependencies. The empty retained authority closure is the failure sentinel after capture failed, not evidence of an empty dependency graph.

The later reported N7 result, 9 PASS / 2 FAIL, was not replayed by G. The separate private-helper interface failure is not decided by this ruling.

### Research witnesses, not product receipts

The following local files were read and hashed, not executed. Paths are relative to `LOCAL/raw/e02-execution-20261027/repairs/N7-protocol-identity-r1/`. They are mutable research transport; the hashes identify the bytes inspected.

| File | SHA-256 | Meaning and boundary |
| --- | --- | --- |
| `actual_loader_execution_probe.py` | `4be2e58a80c42630178cf41ff0ec91b41641cd52360336a81f1381d8b627c573` | Extracted source helpers; a substituted loader and an exact `SourceFileLoader` with temporarily replaced `get_code`. |
| `actual_loader_execution_probe.py.stdout` | `ebddcafdde68bd4c998dfa0e6092e0b771c0c0782b43f4ee8f0f5ef55761ad15` | Reports changed module constant with a consistent retrospective source/code manifest. |
| `loader_facade_combined_probe.py` | `7bd6019c43dcb85e2eb6dfd6b9c8a5b2a346b111567610df2a5fb0046c43bb95` | Synthetic package, provider and importer; exact loader restored before reconciliation. |
| `loader_facade_combined_probe.py.stdout` | `f95ae9034e0a688b1dbcb124cec2f03f91bbd7524975627807d74a2b83e9aa60` | Reports source-closure discovery, two held bindings, facade reconciliation and code-manifest consistency despite changed consumer-visible constant. |
| `provider-removal.stdout` | `a46135ae6d8281d95a3e2424c00a68196c18be2a371fd4163010321a50e93a05` | Reports admitted altered-provider, spoofed-cache-wrapper and spoofed-annotation-provider controls in the scratch prototype. |
| `warmed_provider_boundary_probe.py.stdout` | `24c60ab49bf8209a43b53a14397ab9e6b2d9abe04bac2cae211f00ef0a193e19` | Reports rejection of an authentic warmed annotation provider. That rejection is an availability defect, despite its printed `PASS REJECT` label. |

The loader witnesses do **not** execute the complete N9 path or the full import-time capture. They establish a distinguishing counterexample to the proposed retrospective proof argument, not an independently reproduced N9 exploit and not the cause of R152. Their synthetic helper namespace and stripped decorators further limit extrapolation. The unsafe scratch prototype remains HOLD.

## 2. Answer to the three questions

**What is claimed?** Canonical source-bound loaded code/provider identity, with explicitly qualified decision state and currentness for the protected operation, under an admitted local runtime profile. It is not whole-heap immutability, arbitrary Python initialization purity, equivalence of every future behavior, a complete scientific execution readset, or resistance to an attacker with arbitrary code/native-memory execution in the authority process.

**May finite conditional routes qualify the actual provider without replaying historical branch selection?** Yes. The source-derived allowed route, the authenticated actual provider, the held importer binding, and the scope of the claim must all agree. This establishes the selected binding. It does not establish which historical condition evaluated true or why it was justified. If that condition affects N9 authority—tenant, permissions, selected profile, backend semantics, rule choice or comparable meaning—its owner must independently bind or recompute that condition. A second legitimate provider cannot replace the first silently merely because both are in the allowed set.

**Which rules govern?** GY-DI1 defines a derived relevant authority closure, inside-closure refusal, outside-closure noninterference, and its explicit dormant-dynamic residual. S0-K06 limits fail-closed to affected authority claims, preserving candidate work under declared unknowns. P31/P32/P37/P38/P40 require a structural, content-bound proof of the actual predicate. C95-CANON-HASH-01 and C101-I1/I2 distinguish code/origin witnesses from semantic equivalence and complete readsets. None of these rules establishes arbitrary module purity or makes a copied runtime declaration authoritative.

| Alternative | Decision |
| --- | --- |
| A: retain retrospective supported forms | Safe unavailable fallback, not a solution to the genuine N7 positive. Do not weaken the refusal to make it pass. |
| B: reconstruct source/provider semantics retrospectively | Retain finite source discovery, passive binding checks and completeness obligations. Reject B as the sole proof of actual initialization: restored loader behavior and mutable state are not recovered from matching files and function code. |
| C: trusted execution before imports, then retained bindings | Selected. It handles Python's real class/decorator/alias construction without implementing another Python interpreter. Its trust root, execution evidence and state-through-use conditions must actually exist. |
| Universal sandbox or whole-program purity verifier | Not selected. It would create a different subsystem and a stronger claim than this identity boundary requires. Untrusted executable plugins require an isolation boundary, not a permissive identity exception. |

## 3. The authority predicate

Let `g` be a process-local capture generation, `D` its stable deployment identity, and `op` an existing protected ledger/N9 operation. The loaded-runtime part of admission is:

`appointed_profile(g) AND executed_bound_source(g) AND complete_relevant_bindings(g, op) AND valid_decision_state(g, op) AND current_deployment(g) AND protected_through_use(g, op)`.

This conjunction is **necessary, not sufficient**, for N9 promotion. Existing ledger, risk-scope, selected-profile, lineage, census, authority-issuer, input and scientific guards still decide their own predicates. In particular, a loaded identity does not appoint the separately required N6 census or deployment-authority issuer.

- `appointed_profile`: the canonical deployment/launch owner establishes the interpreter, bootstrap, import configuration and applicable dependency profile before authority-capable imports. A request field, environment flag, file path or self-authored certificate is not appointment.
- `executed_bound_source`: the evidence producer consumed and executed the exact content-bound source/code under that profile. Observing the loader class or re-reading the source after initialization is insufficient.
- `complete_relevant_bindings`: derive the relevant graph, authenticate its actual providers and retain the actual objects used by consumers. A caller's manifest or a whole-process `sys.modules` dump cannot supply this premise.
- `valid_decision_state`: independently reconcile all state roles material to the protected decision, not every byte of every module dictionary. A missing material-state obligation is `not_established`, not an ignored field.
- `current_deployment`: preserve source/lock/runtime/profile drift checks against the admitted generation. Import-time success is not permanent currentness.
- `protected_through_use`: the admitted relation remains valid from admission through the decision and its authority-bearing commit/publication. Endpoint equality alone does not exclude an A→B→A mutation during use.

The implementation must classify the proof of each premise, not just the status of the final record. Use `recomputed` or `independently_reconciled` where established; consumer assertion, missing observation or an unverified supplier declaration cannot turn this gate green. The explicitly trusted host/interpreter is the **scope's root of trust**, not a claim that the product has proved the operating system trustworthy. Under that root, launch identity, executed inputs and admitted bindings still need concrete independent measurement and controlled use; calling the whole process “trusted” is not an exemption.

Unknown loaded identity blocks the affected protected operation. Candidate computations and diagnostics may continue with declared limitations; they may not borrow a trusted sibling process's identity for their own execution.

## 4. One owner, one evidence producer, explicit versions

`confidence_ledger` remains the sole identity admission owner and the source of `LoadedDeploymentIdentityObservation`. The early launcher/recorder is an evidence producer owned by the existing runtime/tooling launch boundary. It does not sign policy, mint N9 authority, or introduce a second deployment-identity service.

Use a typed owner-private capture contract with these selected version identifiers:

- Proof schema: `policyos.runtime.confidence_ledger.loaded_execution_capture.v1`.
- Identity rule: `canonical-source-execution/1`.
- Runtime profile: an explicitly selected, content-bound profile; initially the actual source-checkout CPython 3.14.3 configuration, not “any Python 3.14” or a default-by-name profile.

These are **new implementation contracts selected here**, not existing artifacts. They may be private module types; this decision does not require a new public artifact subsystem or a new universal envelope.

The stable capture body binds the proof/rule versions, bootstrap identity, runtime/dependency profile, canonical source and lock inputs, derived relevant module/provider graph, construction/binding evidence, and role-specific semantic-state projections. A separate in-process portion holds strong references to the actual modules, classes, functions, wrappers, providers and importer bindings, plus generation validity and mutation ownership. Serializing `id(obj)`, a repr, a qualname or an object-address hash cannot replace those references.

Deployment identity is a deterministic digest of the stable owner-verified body. Process IDs, object addresses, capture timestamps, memo-cache occupancy and event ordering that has no semantic significance stay outside it. Process/generation provenance remains bound to the live capture and diagnostics. Two genuinely equivalent admitted fresh processes can have the same deployment identity without sharing object identity or live authority; each must establish its own capture. A different effective provider or material configuration changes the stable identity or the existing narrower operation binding, according to its actual owner.

The identity preimage must include the new proof/rule version. Do not relabel an old digest as satisfying this rule. Keep current public status semantics and refusal categories; retain detailed phase/reason information in the existing owner diagnostic surface. If a persisted/public shape changes, give it the normal explicit schema migration and all generated consumers. A compact exported capture description is audit evidence; deserializing it never creates a live authority session.

The compact diagnostic must expose the proof/rule and runtime-profile identities, capture phase, established/unavailable result, failed premise and unresolved scope, relevant source/provider digests, and capture-versus-currentness time roles. Reuse the existing owner observation/diagnostic route; the public projection must not hide that an import succeeded while authority capture failed. Full object graphs and source copies are not diagnostic output.

## 5. Concrete bootstrap route

### 5.1 Entry and trust root

Introduce only the thin missing early entry in the repository tooling launch layer, outside the product package import path. It uses admitted stdlib primitives and dispatches the existing target after installing the recorder. Reuse existing tool/HTTP/test targets and argument handling; do not build a second runtime.

Starting inside `polisyos.runtime.quality` is too late: its `__init__.py:3–25` already imports PDC and quality owners. `tools/ops_runners/runtime_cli.py:16–26` imports Core at module scope; `runtime/http/profiled_server.py:10–15` imports the app and container at module scope. `tools/lib/runner.py:365–382` is a useful downstream dispatch seam, but bootstrap must precede `tools/lib/preflight.py:57–62` too: dotted `find_spec` can import parent packages. A pytest fixture/conftest is likewise too late if plugin collection imported the authority graph first.

The canonical host launcher establishes a fresh interpreter, expected executable/runtime profile, selected source snapshot and source roots, import path, flags, and permitted startup behavior before that entry. Disable or explicitly admit environment injection, user site, `.pth`/site customization, import hooks, plugin autoload and similar pre-import execution. Use the existing environment; do not solve appointment by creating another full environment or checking every unrelated file on the host.

The first profile is a narrowly configured trusted-code authority process, including a bootstrapped CLI/server/test process where its code and mutation owners meet this condition. If an application embeds arbitrary plugins or permits ambient mutation that cannot be excluded, put the protected operation behind a fresh authority worker boundary or leave that authority claim unavailable. A new service topology is not mandatory when the existing process can meet the profile.

Trust in the bootstrap/interpreter starts at the appointed host deployment boundary; the code being attested cannot certify that boundary retrospectively. No new external institutional signer or hardware attestation is required for this bounded local profile. The launcher must nevertheless resolve the selected expected artifacts independently, control actual startup, and expose its unresolved premises. Installed-package authority remains unavailable until its existing issuer/build mapping is genuinely supplied.

### 5.2 Execute the bytes that were admitted

Extend the existing import lifecycle rather than simulating Python initialization in AST code. For first-party source modules, read and bind the selected source bytes, compile those same bytes with the admitted compiler/flags, retain the resulting code object as execution evidence, and execute that exact object in the loader-owned module. A later `get_code()` lookup must not be allowed to substitute another initializer.

Preserve standard module locks, package semantics, import-cycle behavior, origin/spec information and failure handling. Do not manually replay decorators, bases or metaclass logic. Actual canonical initialization constructs Protocols, generic bases, aliases and descriptors. The bootstrap compiler/builtins/loader path is part of the admitted root; a Python audit hook alone is not that root.

Bind actual stdlib/third-party/native providers to the selected runtime/dependency profile. `uv.lock` is required input, not proof that the installed or loaded dependency matches it. Builtin/frozen/native components use the profile's independently verified build/origin mapping, with an explicit TCB boundary; do not pretend their machine code was reconstructed from Python source. Unsupported mappings remain unavailable for the affected authority route. A pinned `typing.py` alone does not authenticate its `_abc`, `annotationlib`, compiler or native dependencies.

A bytecode cache may be used only when the admitted rule binds it to the exact selected source/code and compiler profile. The smallest first implementation may avoid first-party pyc reuse. Do not trust timestamp/size cache validation as execution provenance. Source-read/compile/load races, alternate loader hooks and mismatched optimization flags must be distinguished.

### 5.3 Finalization and recursive imports

Record observed imports, selected provider edges and module completion while imports execute. A provisional `sys.modules` object in a cycle is not a finalized module. Failure of any required initializer leaves the generation unavailable; successfully imported siblings are not a partial authority certificate.

The current ledger cannot complete a new capture of its own final module state while its initializer is still running. Move final sealing to the early recorder's post-import handoff: the ledger registers its admission/finalization endpoint, required modules finish, the owner reconciles the graph, and the complete snapshot is published atomically. A minimal private lifecycle is collecting → sealed or failed. While collecting, authority requests refuse; this is not success and not a hidden completed capture. Once an actual capture attempt fails, preserve the sticky failure for that process. Do not clear its globals and try to bless the same compromised initialization later.

If reconciliation needs additional imports, collect and reconcile them before sealing. Do not recursively perform N9 during capture. Publish the established predicate last, preserving the protection presently expressed at `confidence_ledger.py:16176–16178`.

## 6. Closure, conditional routes and deferred providers

Reuse `_resolve_authority_import_closure`, source/provider indexes and route candidates for finite discovery and consistency obligations. Reuse the facade/importer reconciliation and retained-reference machinery. Their source-derived candidate graph is not a certificate that execution occurred or that every runtime edge was observed.

The admitted relevant graph combines source-derived obligations with authenticated execution/binding evidence rooted in the actual authority owner. Include imported helpers, selected facade/provider/importer edges and relevant runtime loads. Avoid both a hand-maintained list of today's symbols and the whole unrelated `sys.modules` population. The existing “live maps never contribute closure edges” rule must be refined explicitly: arbitrary live maps remain inadmissible; events produced under the trusted execution boundary can supply independently bound edges. Matching mutually forged maps cannot.

Mediation must cover the actual supported paths, including `importlib`/cached-module reuse and provider lookup; installing only a meta-path finder does not observe every use of an already cached object. Reconcile actual consumer-held references against independently retained producer objects. Do not rely only on the current `sys.modules` entry. Explicit dynamic loading or generated code outside the admitted mechanism is not retroactively accepted because it later acquires a familiar origin/name.

For a conditional source binding, qualify the finite candidate routes without executing the condition during verification. Admit the actual selected object only when its producer execution and consumer binding are established. If selection depends on a material environment/configuration/input condition, that condition has a separate owner-bound obligation. If it only chooses between semantically permitted instrumentation providers, the identity may truthfully bind the selected provider without claiming branch-history replay or adding a policy-authority assertion.

Deferred providers have two cases:

1. **Admitted transition within the same semantic deployment.** For example, a selected stdlib profile describes a lazy proxy becoming its already authenticated module; independently held provenance proves the destination and state rule. The owner may normalize cold/warm representations without changing `D`.
2. **New authority-relevant code, provider choice or semantic state.** It cannot execute as an authority dependency under a sealed old graph. The minimal initial implementation refuses and requires a fresh boot/admission generation. Later controlled graph extension may be added with a new generation and proper dependent invalidation; it must not silently mutate a published capture.

The runtime-profile graph must include the authenticated future destination for case 1; otherwise it is case 2. Preloading a required lazy destination before sealing is a valid implementation simplification if it preserves the real provider contract. Do not invoke arbitrary annotation evaluators merely to force a convenient state.

Dormant routes need not all be executed or included speculatively. Preserve GY-DI1's dormant-dynamic limitation, its real-path no-invocation discriminator, and refusal before an unadmitted route acquires authority. Candidate-only discovery of new providers remains available.

## 7. State that N9 actually needs

Canonical initialization provenance is not proof that every resulting global is correct, immutable or derived from legitimate data. Retaining an object proves continuity of that object, not continuity of its contents. Preserve existing effective contract/model/CanonSpec and selected-profile checks, then derive the remaining state obligations from the actual protected read/use paths.

| State role | Required treatment |
| --- | --- |
| Function code, defaults, keyword defaults, closure cells and material global bindings | Bind the actual callable and effective dependency roles. Reject relevant rebinding/mutation; matching code alone is insufficient. |
| Provider/facade/importer relation, class/metaclass, bases/MRO, descriptors/accessors and registry selectors | Retain actual objects and reconcile role-specific structural/semantic state. No name-only or source-marker replacement. |
| Ledger contract tables, models, CanonSpec, selected schema/profile, rules and authority configuration | Preserve existing independent source/owner recomputation. A bootstrap snapshot of arbitrary current values is not a substitute. |
| Module constant or initialization result consumed by a protected decision | Bind its derivation/configuration where material and its protected effective value. A constant changed during or after initialization is not excused because methods retain the same code. |
| Protocol membership and ABC state | Genuine memo warming may be allowed under the selected runtime's invariant; registrations, subclass hooks, relevant class mutation and provider changes are semantic inputs, not ignorable cache occupancy. |
| Memo/lazy cache | Establish producer, key/basis, allowed mutation and consumer behavior. Exclude occupancy/statistics from identity only after showing that equivalent admitted inputs produce equivalent protected decisions. Stale or poisoned semantic results still refuse. |
| Request data, clocks, randomness, external I/O and scientific inputs | Keep their own operation/input contracts. Initialization may not turn unbound ambient input into fixed authoritative configuration. Identity does not certify the empirical truth of these inputs. |
| Unused unrelated module, diagnostic counter or non-decisive instrumentation state | Do not widen deployment identity merely because the object exists. Establish its non-decisive scope rather than excluding it by a suggestive name. |

This inventory is role-derived and extensible, not a closed roster of today's Python identifiers. Each new opaque execution/state primitive requires an owner adapter or a declared limitation; each ordinary new module using existing supported primitives should require no new identity exception. Do not replace the grammar whitelist with a module-name whitelist, an “all stdlib is safe” shortcut, or whole-module dictionary equality.

### Wrappers and passive inspection

At the assessed input, `_loader_owned_slot_binding` reads a cache wrapper's parameters and `__wrapped__` (`confidence_ledger.py:15025–15053`). CPython's C wrapper calls its retained `func`; rewriting `__wrapped__` does not establish that target. The scratch counterexample is therefore a material acceptance control.

For the admitted cache primitive, bind the real construction inputs/target and retain the resulting wrapper, using trusted construction evidence or an independently verified exact-runtime adapter. Also protect the target's code/defaults/closures and cache basis. Do not accept `__wrapped__`, `cache_parameters()` output or matching wrapper type as sufficient proof. Generic `gc.get_referents` inspection is not a universal target/state verifier; a bounded CPython adapter requires its own exact invariant and discriminator.

Passive verification must not execute a candidate callback, descriptor, annotation evaluator, `__getattr__`, or replaced introspection method to find out whether it is safe. Use non-invoking inspection of admitted object representations and independently retained construction information. Normal canonical initialization may execute legitimate descriptors/decorators as product code under its admitted execution/input profile; it is not an excuse to execute untrusted inspection during admission.

### State through the protected operation

Use the existing session/currentness boundary together with explicit ownership/exclusion of material code/provider/configuration mutation. Hold the protection through the protected decision and durable publication. A lock is effective only against all permitted mutation owners; it does not stop arbitrary Python writes by itself. Exclude or separately admit reentrant callbacks, background mutations and reloads in this interval. A mutable-state change cannot be legitimized by clearing a dirty bit after use.

The minimal supported profile uses trusted code with no uncontrolled execution in the authority process and no concurrent unowned mutation of the protected roles. A general plugin host does not qualify by assertion. If those conditions cannot be established, isolate the authority operation or retain `not_established`; do not promise a hostile-Python sandbox. Existing mutable ledger data still uses its normal transactional owner; this rule does not freeze the whole application or serialize unrelated computations.

## 8. Integration and compatibility contract

Preserve these existing seams and obligations:

| Existing source at the assessed input | Required change or preservation |
| --- | --- |
| `confidence_ledger.py:890–924, 5521–5545` | Keep the typed established/unavailable observation and coherent reason semantics. Consume the newly sealed owner capture, never a caller-supplied proof object. |
| `:111–130, 10024–10045` retained-binding machinery | Reuse actual strong-reference comparisons; extend roles for trusted construction/provider evidence. |
| `:163–249`, `:5750–5822` source analysis/baseline/fence | Reuse source-byte custody and drift checks; bind source, pyproject, lock, runtime and selected proof profile. Metadata fences remain optimizations, not byte authority. |
| `:5475–5489, 16050–16104` contract-currentness | Preserve effective ledger/model/canonical projections and repeated currentness checks. No cache-warm exemption for material contracts. |
| `:5660–5745` identity/admission | Bind the versioned stable capture body; require valid process-local holdings and current deployment before authority. |
| `:5866–6046`, provider and facade indexes | Retain discovery and passive reconciliation; remove the unsupported-initializer grammar's role as a universal authority gate only after its obligations have actual replacement evidence. |
| `:15136–15293` loaded-code manifest | Keep independent compiled-code/source reconciliation as a witness, augmented by actual execution provenance; it is not the sole initializer attestor. |
| `:16110–16184` capture publication | Replace too-late self-capture with early-recorder/post-import sealing; preserve atomic readiness, terminal failed capture and installed-issuer unavailability. |
| `promotion_sequence.py:4112–4123, 4170–4189, 5051–5095` | Preserve N6 supplied/current identity equality and canonical N9 authority-session checks. No alternate “bootstrapped therefore promote” path. |
| `promotion_sequence.py:5259–5269, 5713–5753` | Public receipt recomputation uses the same canonical owner/currentness checks. Historical display and present authority are distinct. |
| Core selected artifact/profile readers | Preserve exact selected-profile, manifest/payload, lineage and raw-view guards. Difficult Protocol syntax does not authorize bypassing these modules. |

Minimum companion footprint includes the launch entry and its configuration, canonical tool preflight/dispatch, ordinary HTTP startup, test invocation/plugin admission, N6/N9 producer and public replay consumers, relevant process-spawn/reload paths, owner diagnostic/public schemas if changed, and current tests and generated inventories that bind those surfaces. Enumerate the actual caller set on the implementation source; the table is not a claim of complete caller census.

Each spawned authority process needs its own early execution evidence. A parent token, copied environment marker or serialized capture cannot certify child initialization. A pre-import worker/reloader hook must run before importing the target; a post-fork inherited object graph is not a fresh capture. The initial route may use spawn/exec. A future fork profile requires explicit inheritance/currentness semantics rather than silently borrowing the parent's claim.

### Migration steps

1. Introduce the typed capture and early evidence producer with a fail-closed default. Preserve current authoritative guards while the new path is incomplete. Do not ship a Protocol-only bypass as migration.
2. Wire early launch for the actual N7/N9 test and ordinary runtime/replay entry paths; derive the affected caller and process denominator. Importing directly remains possible for candidate work, with authority unavailable.
3. Finalize the first complete source-checkout profile, real provider/state adapters and operation-through-use protection. Produce independently reviewed source-only adversarial evidence before the expensive integrated wave.
4. Switch both canonical production and public replay admission to the same new owner predicate. Remove superseded grammar-based admission branches where the new mechanism covers the obligation; do not keep competing issuers or permissive fallbacks.
5. Start a fresh bootstrapped authority process. A new capture/deployment identity does **not** authorize a fresh risk budget. For an existing incompatible scope, continuation requires an explicitly supported owner-authorized transition preserving prior spend, lineage and invalidation/poison state; no such transition is assumed here. Until supplied, that continuation remains unavailable. Preserve prior events and historical receipt bytes. Do not clear a scope, invent an epoch, change the problem identity, or derive a new scope from the new deployment identity to bypass prior spend or poison. An independently valid new problem/scope or isolated verification fixture is a different case; it cannot stand in for continuation of the old problem.
6. Run the affected real N7/N9 and fresh-consumer checks at the composed source and actual profile. A successful import is only the first readiness check, not N7 controller/custody success or E02 closure.

Old identity/receipt versions remain readable for their original historical claim. They do not satisfy `canonical-source-execution/1` merely because their files still match. Fresh authoritative replay needs fresh current-process admission and existing rule/version compatibility; a historical-only reader must not silently project current authority. Capture time, currentness-check time and historical run time remain distinct. Do not invalidate all historical evidence solely because the implementation gained this stronger explicit proof version.

This migration boundary is concrete: `promotion_sequence.py:3826–3839` derives the scope from the problem with `epoch_ref=None`; `confidence_ledger.py:2141–2157` requires the persisted root and new session deployment identities to agree. `N12EpochReferenceProjection` and `project_n12_epoch_reference` (`:1388–1408`, `:4328–4356`) explicitly report `epoch_not_implemented`. Thus neither same-scope reopen nor new-epoch budget reset is an existing escape hatch. Implementing and verifying C can proceed without solving a general epoch subsystem; delivery must identify any existing-scope continuation that remains blocked. Extending budget continuity would be a separate confidence-ledger contract change, not a bootstrap convenience.

## 9. Acceptance and falsification matrix

These are required future checks, **not executed results**. Derive concrete selectors from the implementation and original N7/N9 obligations. An independent reviewer must distinguish a new failure class from the same class at a deeper consumer (P40).

| Boundary | Positive / compatibility signal | Adversarial or removal signal |
| --- | --- | --- |
| Genuine declarations | Actual runtime-checkable/parameterized Protocol, property contract, callable alias and supported conditional/lazy provider load through the canonical owner. | Same name/type/source marker but substituted class, accessor, provider or importer refuses. Do not limit the cases to ArtifactReader. |
| Actual initialization | Canonical bytes initialize the real consumer-visible value. | Temporarily patched `get_code`, restored before reconciliation, cannot change the initializer while capture establishes canonical execution. Exercise the actual bootstrap, not only extracted helpers. |
| Source/code custody | Captured executed code corresponds to exact selected bytes/compiler flags. | Equal-metadata byte replacement, source-read/load race, alternate bytecode and loader/compile/builtins substitution refuse or are prevented before execution. |
| Bootstrap appointment | Ordinary admitted launch establishes the owner snapshot. | Preloaded forged module, plugin/site-hook import before capture, forged launcher file/env marker or copied sealed description does not appoint authority. |
| Actual wrapper target | Genuine cache wrapper constructed by the admitted producer remains valid. | `cache(hostile)` plus forged `__wrapped__`, parameters or qualname cannot qualify the hostile target. |
| Conditional binding | Each supported selected provider has its own qualified actual binding. | Coherently substitute provider, facade, importer and `sys.modules`; retained independent producer anchors still reject. A selection predicate that matters to authority cannot remain caller-asserted. |
| Legitimate warming | Authentic `annotationlib.Format` access and `isinstance`/ABC memo warming preserve the claim where semantically invariant. | Forged lazy destination, altered registration/hook/class or stale semantic cache refuses. Cold-only success is insufficient. |
| Relevant state | Unchanged code/provider/contract state supports a protected decision. | Mutate a material global, default, closure, descriptor, model, CanonSpec or selected profile without changing function code; admission/use refuses. |
| Through-use protection | Allowed ordinary data operations complete under their existing transaction owner. | A→B→A mutation or reentrant callback during protected decision cannot publish under the old admission. Before/after equality alone must not make this test pass. |
| Import finalization | Valid cycles complete and seal only after required initialization. | Partial circular module, initializer failure, early authority request or incomplete capture cannot expose a ready snapshot. Failed capture cannot be upgraded in place. |
| Relevant closure | Actual authority imports and selected runtime providers are included generically. | Remove/relabel an edge or rehash a forged manifest while preserving declarations; actual consumer refuses. Unadmitted deferred execution cannot use the old graph. |
| Noninterference | A derived unrelated-module change and nonsemantic cache warming leave the stable identity and decision unchanged. | A material inside-closure/source/profile change invalidates the relevant claim. Do not hard-code today's outside witness. |
| Process boundary | Fresh bootstrapped worker/server restart establishes its own holdings; equal stable inputs may yield equal D. | Parent token reuse, unbootstrapped spawned/reloaded child or borrowed clean-worker identity cannot certify another process's operation. |
| Runtime/dependencies | Actual selected interpreter/stdlib/native/dependency mapping qualifies the profile. | Same version/name with mismatched loaded installation refuses; lockfile equality alone cannot repair it. Installed no-issuer stays unavailable. |
| N9 producer and fresh public consumer | Existing guarded N9 and fresh receipt recomputation both use the real owner capture and original protected predicates. | Remove the execution-evidence check, binding check or state guard while keeping schema/markers; the applicable semantic test becomes red. No verification-only injected authority substitute. |
| History and statuses | Historical receipts retain their old claim and parse according to their own versions. | Old capture, missing proof, current source mismatch, setup error or unrun path cannot be relabeled as new authority or PASS. |
| Risk continuity | A new valid process capture does not change previously consumed risk allowance or historical events. | Warm an existing spent/poisoned scope, then change proof/deployment version: reopen, fabricated epoch, alternate root or renamed problem must not obtain a fresh allowance for that same obligation. Unsupported continuation refuses explicitly. |

Minimum decisive first vertical slice: genuine Protocol through real owner → canonical bootstrap initialization positive → patched-and-restored loader negative → fake provider/wrapper negative → legitimate warm-state positive → original guarded N7/N9 consumer and fresh replay. The broader table closes affected siblings and compatibility; it is not permission to stop after the first green import.

## 10. Resource and extensibility constraints

Reuse the existing analysis context and hash/source caches within their admitted lifetime. Capture module execution once per generation, retain existing objects by reference, and store compact events/projections. Do not duplicate entire source trees, environments, module dictionaries or heap snapshots. Avoid all-call tracing and arbitrary recursive heap traversal as the production proof mechanism.

Cache repeated verification only with a complete semantic dependency key and an independent invalidation boundary. Continue existing source quick-fence plus content reconciliation; a timestamp-only cache cannot supply byte identity. Safe memo warming must not reprice N9/N11/generation evidence merely because a new object address or counter appeared. Relevant provider/state/source changes still require affected revalidation.

Support growth through generic load/binding records and explicit execution/state primitive adapters. New normal modules, aliases and decorators executing through an already supported profile should not require per-symbol whitelist edits. New interpreter builds, opaque wrappers, loaders or native providers need a new qualified profile/adapter, not a default exemption. This is a bounded extensibility contract, not a claim to support every future Python execution mechanism now.

## 11. Remaining limitations and genuine inputs

- Trusted early launch, source-execution capture and its integration are not present in the inspected seams. Their current capability labels are `producer_missing`, `bridge_missing` and `verification_missing`; the decision does not fill them by prose.
- The exact runtime/build/dependency mapping and enforceable mutation-owner profile must be supplied and checked by the implementation. If unavailable, the affected loaded identity remains `not_established`. The code may implement this local profile; no production dataset, law, calibration record or new institutional permission is required merely to build and test it.
- Installed-package identity remains `packaged_deployment_identity_issuer_unavailable` until its actual build issuer and source/origin mapping are wired. A source-launch wrapper is not that issuer.
- Existing-scope continuation across an incompatible deployment identity has a conditional `bridge_missing`: the cited source supplies no budget-preserving deployment/epoch transition. This does not block construction or isolated verification of C, but it prevents a blanket migration-ready claim for prior live scopes. No risk allowance is reset by this decision.
- No universal whole-heap proof, arbitrary dynamic-code completeness, hostile-native-code defense, deterministic replay of arbitrary initializer side effects, scientific truth or institutional authority is asserted.
- Unknown material initializers, state transitions or providers cannot enter protected operation under a bounded label pretending they are proved. Establish the specific role, isolate it, or keep that claim unavailable while other candidate work proceeds.
- The diagnostic origin count is not the final admitted graph denominator. No accepted closure count, total source correctness claim or N7/N9 runtime PASS is issued here.

## 12. Source and research references

Repository sources are pinned to the commit in section 1. In addition to the implementation anchors above:

- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:3104–3154`, **GY-DI1**: derived relevant authority import closure, inside/outside drift controls, forged-manifest refusal, declared dormant-dynamic residual. Historical counts in that record are not current counts.
- `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:46–88, 164–176`, **S0-K06** application: authority-band fail-closed and candidate work with declared unknowns.
- `policy-engine/docs/reference/policy-design-case-failure-patterns.md:627–647`, **C95-CANON-HASH-01 / C101-I1 / C101-I2**: actual code/origin qualification, installed-origin mapping and the limits of structural fingerprints.
- `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/ds17-source-binding-vs-import-purity-proposal-20261021.md` is an unaccepted proposal, not independent authority for this ruling.

Primary technical sources inform the mechanism choices below; the PolicyOS decisions are architectural inferences, not claims that upstream Python implements this attestor:

- [CPython 3.14.3 typing source](https://github.com/python/cpython/blob/v3.14.3/Lib/typing.py): `_LazyAnnotationLib` legitimately replaces its proxy with the imported provider; Protocol creation and runtime membership have materialized state. This motivates a qualified warm transition rather than a cold-state requirement.
- [CPython 3.14.3 functools source](https://github.com/python/cpython/blob/v3.14.3/Lib/functools.py) and [C cache wrapper implementation](https://github.com/python/cpython/blob/v3.14.3/Modules/_functoolsmodule.c): wrapper metadata and the retained target called by the C implementation are distinct. Construction evidence must bind the latter.
- [Python import system](https://docs.python.org/3.14/reference/import.html): import mechanisms, mutable module caches and the distinction between loading and name binding explain why a finder log or a module-path comparison is incomplete. The selected runtime profile remains pinned to 3.14.3, not the moving documentation patch version.
- [Annotation introspection](https://docs.python.org/3.14/library/annotationlib.html): annotation access can execute code. An identity verifier must not treat it as inherently passive.
- [Runtime-checkable Protocols](https://docs.python.org/3.14/library/typing.html#typing.runtime_checkable): structural runtime membership is limited; it is not semantic verification of a provider's behavior.
- [Python audit hooks](https://docs.python.org/3.14/library/sys.html#sys.addaudithook): Python-level hooks are observability tools and are not a hostile-code sandbox. The proposed recorder must have an independently admitted launch boundary.

## 13. Review disposition and implementation handoff

Three direct read-only reviews covered existing owner/consumer seams, CPython mechanisms, and adversarial boundaries. The second red-team pass incorporated the restored-loader/changed-constant witness, premature import entry, provisional-cycle publication, retained-object versus mutable-content distinction, and through-use mutation race. G then read the cited owner/consumer and launcher seams and the new probes/outputs, and selected the concrete route in this document. None of those reviews executed product tests.

Final builder review found that a draft migration step incorrectly assumed an existing deployment-to-risk-scope transition. G checked the problem-scope derivation, root binding and unimplemented epoch projection at the pinned source, removed that assumption, and added the explicit no-budget-reset boundary and falsifier above. Final adversarial review found no further material contradiction in the selected bounded architecture; that is a document review outcome, not implementation acceptance.

Pattern pass: **P01/P02** require the new early producer and bridge to real N9/public consumers; **P05/P37** prevent a copied declaration or clean sibling from appointing authority; **P07/P08** preserve proof version and capture/current/history time roles; **P13/GY-DI1** prevent whole-process overbinding; **P29/P32/P38** require actual executed bytes and real held targets; **P31/P40** end per-syntax repairs; **P14/P35** keep diagnostic counts and extracted probes within their denominators.

The executor may implement compatible details autonomously within this decision: exact module placement inside the canonical launch owner, private type decomposition and efficient cache structures are engineering choices. A proposed weaker bootstrap, retroactive adoption of preloaded modules, whole-heap/sandbox claim, permissive unknown state, second issuer or narrowed original N7/N9 predicate is a contract change, not an implementation convenience.

Deliver the implementation with exact source/profile, full mechanism and companion footprint, independent reviews, complete deciding outputs and explicit limitations. G source acceptance, integrated-source verification and finding adjudication remain separate later actions.
