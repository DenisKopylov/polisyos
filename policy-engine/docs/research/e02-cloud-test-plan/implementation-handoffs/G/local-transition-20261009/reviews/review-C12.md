# C12 independent review: source admission and G composition

Date: 2026-10-09. Read-only review in G checkout.

Pins:
- G: dee58973f7673299070b7c7374f419b0adb8175c, tree 4caee698bd9a6c61277a1608bb38376b669f0372
- C12 source: a47ec396228d3a8be63cb6c2c5ad3a1f17ee20e7, tree 2e40b42e506b5dbae790f809368c308631cdaac4
- C12 published receipt: fcf164eb1c5bb54786462e67ba2537313b33b90d
- Final coordinator handoff: d9a4b671c99bf6a5435fde4fc873092e03b451b0, policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/orch02-r2-20261008/delivery/final-handoff.json

## Verdict

C12 mechanism is **GO_BOUNDED at its exact own-lane source a47ec396**, conditional on selecting the exact producer dependencies and public API companions.

Admission to current G is **HOLD**. The G tree lacks modules and symbols imported by C12, and the served request path does not supply the immutable profile or local encoder. Porting store.py/search.py alone would fail at import or leave the new vector property unserved. This is component code review, not G source acceptance, an integrated capability, production authority, or finding closure.

## What the exact source receipts establish

C12 source lineage is separate from G: a47 is a child of fd3898, based on C12 r2 9c46da and original Legal base c60e37. The published final packet pins exact a47 source/tree. The source-owned delta includes store.py, search.py, test_emb_03.py, README and two release fragments. Against current G, four existing file preimages differ and both release fragments are absent; the handoff marks these as pathwise port work.

The implementation has a real portable property: LegalQueryProfile freezes basis kind, generation ID, and canonical inventory bytes; the store resolves the selected generation afresh and compares the saved request profile before encoding. It checks current table membership/projected text, selected index/matrix correspondence, model/device/dimension/projection-rule fields, live encoder identity before and after encode, output shape/finite values, and normalization. Refusal is before query encoding and native knn. The selected persisted index may be loaded before refusal, an explicit limit.

The exact source-bound native receipts show 45 PASS plus a disjoint 13 PASS supplement = 58 unique affected PASS. The 24 numeric cases are included in that set and separately used in a removal probe; do not add them. A guard-only removal gives 9 expected failures when actual encode/knn is reached. Removing the numeric float branch gives 12 scientific-notation failures and 12 zero controls still passing. The independent final reviewer reports 39 deciding output streams reconciled to exact source. I inspected the source and committed receipts; I did not rerun checks in G.

Final a47 Ruff/format and strict scoped mypy are PASS; the mypy profile uses a separate pinned hnswlib stub, not a product lock change. The old 677 result is stale and is not the final-source verdict.

## Why G cannot merge this patch alone

Current G lacks policy-engine/src/polisyos/data_forge/domains/legal/embedding_projection.py. Its kernel/embeddings.py lacks the C12-required GenerationIdentity, derive_encoder_identity, generation_basis_matches_members, and hnsw_index_matches_vectors APIs; current G also lacks the Legal projection rule/text module. C12 store.py imports these in its own source tree. These are real missing dependencies, not merely absent authentic production inputs.

The exact C12 proposal selects existing public owners rather than a new facade:
1. First select the canonical DFI→CAT→Legal producer ancestry and provide its generation/member/index identity symbols. Do not copy the old c60 branch or supplier snapshots wholesale.
2. Extend policy-engine/src/polisyos/data_forge/read_api/legal.py with the typed lazy exports and rule-version wrapper in the committed C12 companion. Extend policy-engine/src/polisyos/lex/knowledge/__init__.py to export LegalQueryInput, LegalQueryProfile and LegalQueryProfileError, including TYPE_CHECKING declarations.
3. Port the exact C12-owned changes pathwise into current G store.py/search.py/test_emb_03.py, retaining G postimages and adding the existing README/release companions. Current-G preimages are different; own-base checks do not transfer.
4. Regenerate/review the existing public-surface inventory/reference and required generated families after the facade and request contract changes. C12's full architecture gate is FAIL: 154 deep-import diagnostics, one baseline drift, two generated drifts, all four required families measured, none UNRUN. Do not change baselines, exceptions or generated outputs merely to hide this result.

## Missing actual request and serving bridge

C12's handoff identifies the existing route as POST /api/v1/control/lex/search → LexPipelineMixin.search_lex_graph → Graph.text_search. The current strict LexSearchRequest only carries query, top_k and output_dir. The caller passes neither query_encoder nor query_profile and does not perform a vector positive. Broad ValueError handling maps errors to an empty response.

The executable integration task is therefore:
- In existing policy-engine/src/polisyos/core/contracts/control.py, locate an existing saved request-intent record first. If none exists, choose the smallest versioned immutable intent reference on the existing LexSearchRequest; bind it to the actual request and selected basis, and never manufacture the expected intent from the reader's live selector. Do not add a parallel DTO or trust a self-asserted hash.
- With an explicit A/G lease, wire policy-engine/src/polisyos/runtime/http/services/control/lex_pipeline.py to resolve the saved intent and trusted canonical local encoder, pass both to the reopened LegalKnowledgeGraph, and call existing search_facts while preserving request filters and LegalFactResult projection. The prior C10 lease did not cover lex_pipeline.py.
- In existing lex_search_projection.py/route handling, preserve LegalQueryProfileError.code through the owner's current error contract. Do not turn unsupported/stale vector intent into successful empty results; do not invent a status or response DTO.
- Add the existing request schema/client/validator/generated companions and API tests that exercise matching intent, missing/stale/mixed generation, encoder mismatch and refusal propagation. Prove property removal at the served consumer. The C12 direct-call excerpt is only a proposal, not a served positive.

## Limits and undecided inputs

- The unchanged-asset arbitrary encode-callable substitution remains unproven. The route must supply the trusted canonical local encoder; do not expose an arbitrary user callable as an authority path.
- Pairing is for the queried table, not a global three-table lockstep.
- hybrid_search may return text-only results on vector refusal; that mode must be surfaced. Text fallback is not a vector positive.
- Portable fixtures establish the mechanism only: not production corpus provenance, current-law completeness, model quality or Legal authority.
- Latest L01/L02 evidence does not close authentic pairing: L01 reports I3 against another snapshot root and L6/Legal content/currentness unresolved; L02's three-control loader plus forged-hash negatives establish loader behavior, while live serving root/currentness and authentic POST/N5/CAS/GET remain not_established/UNRUN. Continue portable work independently; do not relabel it authentic.
- Production invocation on a47 against c60 is partial UNRESOLVED and capture ERROR_INCOMPLETE_AUTHOR_PROCESS_CAPTURE. The 170,878,513-byte raw JSON is complete/parseable but gitignored and unpublished; no wait4 exit/wall/RSS exists. HTTP dispatch, DI, events, callbacks/coroutines, reflection/dynamic dispatch, and runtime execution are unmeasured. A preflight cgroup snapshot shows oom_kill=1, but the capture says it was unchanged; no OOM attribution or exit 3 is established. Do not rerun the unchanged large diagnostic just to recover wait4.
- P41 is explicitly not_established: exact slice-base/full-denominator/zero-overlap replay is absent. Do not call these reds inherited or assign the capture error to product code.

## Pattern pass and review scope

P01/P02: internal persisted reader is demonstrated; producer→saved intent→route→visible response bridge is missing.
P04/P05/P37/P38: refusal status must survive serving; expected intent must resolve/content-bind, not self-attest. The G0 request after G1 publish is the discriminator.
P27/P30: extend the existing Data Forge/Legal public owners, no parallel DTO/facade.
P29/P32/P33: actual reader tests and matched removal controls support the bounded mechanism, not production authority.
P14: same-lineage source/test/review evidence is not multiple independent production sources.
P41: red provenance remains unknown.

No tests, installs, production reads, source/ref changes or tracked writes were performed. This report is in ignored _build scratch only.
