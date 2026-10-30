# G decision request: loaded deployment identity proof boundary

Architecture question only; no code acceptance, E02 closure, integration, or test execution is requested.

## Source and exact observed failure
Author checkout: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
Source: 8e501aa0f24c02e5e2866e3ce13b0467f7fc0736
Tree: 66b80e279e3f4895b6bac1e705e0a0ae2d20d1fd
Branch: codex/e02-unified-local-20261009. These commits are local author work; the latest published author receipt remains R125 at e151479e. Read the exact local checkout or git show; do not switch/reset any checkout.

A fresh, one-shot, read-only source import on predecessor 4ccfa564 / 5f44a9ec reproduced N7's sticky failure:
canonical_loaded_runtime_mismatch
decorated direct source binding is unresolved: polisyos.core.artifacts.protocol.ArtifactReader
The detail is 94 characters, SHA256 17159e0d906df9b6c0251643adaf41192d313e04f38a0590ac5e58d42a5839f4.
Receipt: LOCAL/raw/e02-execution-20261027/runtime-prep/N7-identity-import-r152/result.json
SHA256 ee680f6f31954c4e6cfdf584100f5bd6986cc3e5d49e65b125d6f7ca86fa8197.
All 1559 finite first-party Python origins matched actual bytes and pinned Git; Python 3.14.3 SourceFileLoader, private empty pycache, no pytest tracing, no DB/network/product writes. This is a diagnostic, not semantic PASS.
confidence_ledger.py is unchanged f7e770b6d170dafcaaa9fe566355ff9b64dc138b38b29848726cda3dbf0206c8.

The exact rejecting route is confidence_ledger.py near 13122. ArtifactReader at core/artifacts/protocol.py:223 is a legitimate @runtime_checkable Protocol. The import-time authority closure is assigned only after successful capture, so its retained empty tuple is not evidence of an empty actual source dependency set. This blocks the original N7 controller/custody test before its target admission proof. R157 on current source is 9 PASS / 2 FAIL of the same 11 N7 consumers; the other failure is a separate historical private-helper test interface.

## Existing property and reuse candidates
The canonical confidence_ledger owner already reconciles source/lock/runtime identity, module source origins and code bindings, selected providers, import closure, dataclass/read-API binding forms and final fences. Keep its actual authority boundary; do not make a second identity issuer or weaken status to established by a pathname, symbol, declaration or CodeType marker.
Existing canonical import/loader and source/provider reconciliation are reuse candidates. A verified startup/import appointment plus held real bindings might be an alternative to reconstructing arbitrary initialization later; that is a proposal, not an existing mechanism or accepted proof.
Dynamic decomposition preflight is a separate source-tool property, not a substitute loaded-runtime attestor. Its R13 is now composed with bounded unit proof; it is not this N7 identity.

## P40 investigation and falsifiers
The source-only worker widened beyond the first instance before proposing a repair. Discovery with rejection gates explicitly bypassed solely for a census (never a proof) found further unsupported same-class source forms:
- simple callable alias require_return_selected_profile_writer;
- parameterized Protocol base and property in CoreJSONArtifactBoundedMemberAttempt;
- conditional optional-provider source binding such as core.observability.get_metrics;
- lazy-child/provider routes.
17 top-level decorated Protocol declarations were enumerated in the exact core protocol source. R152 has no successful admitted closure, so no complete admitted-closure count is claimed.

The scratch prototype remains HOLD. Two concrete source/stdlib probes show why shape-only repair is unsafe:
1. functools.cache(hostile) with forged __wrapped__ can mimic the verified wrapper while retaining and invoking hostile. gc.get_referents can expose the actual held callable for this CPython object, but that single fact is not a generic provider/state proof.
2. A forged typing._lazy_annotationlib module, also inserted in sys.modules under the expected name, passes a name/provider proxy. Refusing every initialized provider instead rejects authentic CPython 3.14.3 after legitimate annotationlib.Format access; legitimate isinstance also changes Protocol ABC cache state.
These are same provider-binding/precision class. No unsafe prototype is applied, no runtime identity PASS is claimed.
Worker material: LOCAL/raw/e02-execution-20261027/repairs/N7-protocol-identity-r1/ (mutable research; inspect exact current files, not invented immutable evidence). No production payload required.

## Decision requested
Please define the exact authority predicate and choose the bounded implementation route:
A. Extend the current retrospective resolver only for source forms with complete existing proof. Unsupported legitimate states stay explicitly not_established; this cannot yet satisfy N7's positive identity.
B. Extend the existing owner coherently to the complete actual source/provider/code graph of the supported profile, including genuine generic bases, aliases, conditional and lazy providers, with an explicit proof boundary for trusted stdlib and runtime state. Do not incrementally whitelist names/classes or pretend arbitrary Python evaluation is solved.
C. Reuse the actual canonical loader/startup boundary to attest canonical source execution and hold the actual resulting code/provider bindings, then reconcile those at admission, instead of reconstructing all initializer semantics retrospectively. This mechanism is not established today; name its trusted bootstrap, migration and falsifiers if selected.

My conditional recommendation is B only if the existing owner can establish the actual source/code/provider predicate with a finite, declared semantic domain; otherwise C is the concrete reuse-first alternative. We need your ruling on the property, not permission to make a test green:
- Is loaded deployment identity claiming canonical code/provider binding under an explicit trusted local CPython profile, or a stronger claim about all mutable globals, caches and transitive behavior? Which runtime state is actually load-bearing for N9 admission, and what remains not_established rather than being silently treated as proved?
- May a source-derived finite set of legitimate conditional provider routes be reconciled to the actual held provider/code without claiming a replay of the historical branch choice?
- Which existing custody rule/finding governs that boundary, and what smallest independent spoof/removal and legitimate-warm-state controls distinguish it?

Preserve historical closures including B198/B59, current selected-profile/lineage/source guards, and scientific/authority separation. Unknown code identity does not become authority; do not weaken protected N9 admission or fabricate an issuer. Please return an English decision document in a NEW path under LOCAL/raw/e02-execution-20261027/analysis/G-loaded-deployment-decision-20261030/ with exact source pointers, limitations and migration. Only that new document may be written; no source/index/refs changes, heavy tests, cleanup, or resumption of acceptance. Other local E02 work continues independently.

