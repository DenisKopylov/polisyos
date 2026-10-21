# DS17 source-binding correction and conditional import-purity clarification

**Status:** unaccepted proposal for G review. This document is not an adopted architecture decision, code acceptance, release gate, or finding closure. No decision owner is assigned. The existing source-identity repair proceeds as ordinary owner engineering while this conditional question is unresolved.

## Conditional question and current finding

Does a cited, ratified DS17 owner contract require every import-time expression in the selected route to be effect-free, beyond binding selected runtime values to their exact source and declared import routes?

The evidence reviewed for this proposal supports repository-local source-bound import closure plus declared finite PEP 562 routes. The owner binds source module/symbol, bytes, build inputs, and runtime profile. No reviewed DS17 source ratifies whole-module purity. If no source citation establishes that stronger requirement, there is no additional G decision to wait for: continue the existing source-identity repair.

The retained official owner writer refused at `READ_API_SURFACES` because the direct-binding resolver accepts literal-only assignment values and undecorated local definitions, then rejects the actual tuple constructor and frozen/slotted dataclass. The refusal diagnostic says “side-effecting,” but the checker only demonstrated that `ast.literal_eval` does not support that expression. It did not observe an import side effect. Official output: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/q2-current-runtime-contract-render-20261021/owner-recompute/ds17-official-owner-write-20261021T000000Z/validator.stdout.json`, SHA-256 `b199accaca2b6be1eed3a91d8e21c73d3b548bd600f0e5a8f2138d9ce62bb575`. Result: zero stable passes, second derivation not started, no corruption controls, no candidate artifact.

This makes the immediate false negative an engineering repair if the existing source-identity contract is retained. A broader G clarification is relevant only if a cited requirement makes whole-module purity part of the intended authority property. It must not hold the source-identity repair absent such evidence.

## Recommended default: source-identity reconciliation

Reuse the existing owner source-byte, route, import-closure, loaded-code, and runtime-profile machinery. Independently parse the exact admitted source bytes for the two literal maps `READ_API_SURFACE_MODULES` and `READ_API_SURFACE_SUMMARIES`. Accept only unique literal dictionary assignments with string keys and values, no duplicate keys, and the exact expected member set. Preserve their source order. Never compute the expected value from the live mutable maps.

At the real owner boundary, compare both loaded route maps and the actual `READ_API_SURFACES` tuple to those source-derived values; require exact row order and values, no missing/extra/duplicate rows, the exact loaded `ReadApiSurface` class, expected frozen/slotted field shape, and identical public re-export objects. Resolve selected lazy modules and the catalog/academic symbol routes to their exact source-selected module/symbol origins. Capture the result at import time and compare source hashes, loaded code, selected closure, lock inputs, and Python profile at rederivation. Do not evaluate arbitrary AST calls or decorators.

Required distinguishing probe: after import, jointly mutate both live maps and the tuple so they agree with a wrong route and summary while all public markers/names remain. The owner must refuse because its expected routes and summaries come from the exact source bytes, not those changed maps. A source change after import, stale profile, tuple/class rebind, wrong tuple order, duplicate/missing/extra row, changed module origin, or duplicate literal key must also refuse. A positive must run the actual official writer and projection consumer on the current constructor-based route, including cold and cache-hit reads, and must fail on a corrupted source member. Tests that only assert marker presence are insufficient.

This contract does not claim unrelated import-time code is effect-free. If that residual is outside the required property, current evidence does not establish it.

## Alternatives and material impact

**A. Source-bound identity reconciliation — recommended engineering correction.** Keeps current public tuple/class behavior and current source-closure property. Smallest change to the owner checker and its real consumer tests. No public API migration. Residual is explicit: effects unrelated to selected binding identity remain outside this claim.

**B. Whole selected-module import-purity grammar — conditional clarification only if a ratified requirement is cited.** A generic grammar must cover the complete recomputed selected binding set: aliases, constructors, decorators, iterable protocols, defaults, descriptors, metaclasses, rebinding, and hidden imports. Unknown calls/effects refuse. The earlier 1,479-Python-file census is not a selected-source denominator for this mechanism. This adds a static interpreter, adversarial tests, maintenance burden, and a stronger authority predicate. Do not start a syntax allowlist or expression ladder without evidence that this stronger property is required.

**C. Versioned literal public API.** Replace or deprecate the constructed tuple/class route for literal route data; update consumer code and the public-surface contract/reference with a compatibility path. This is a source-compatibility migration, larger than needed if A is the intended property.

**D. Keep bounded refusal.** Honest current state is `verification_missing` / unavailable. It does not repair the false negative, and a manual hash refresh, marker, lazy-export bypass, or neighboring accepted decision cannot change it.

## Boundary and status

The source-bound identity requirement already explains why source bytes, selected bindings, and loaded runtime are compared. Accepting exact output of the current pinned source while rejecting mutated live state is a proxy correction within that requirement. No law, external institution, or cited DS17 ratification was found that requires unrelated import effects to be excluded. Requiring whole purity would create that new boundary and authority predicate; the code diagnostic is not such a decision.

If an owner supplies a citation showing whole-module purity is required, G may clarify that contract and name an appropriate decision owner. Otherwise this conditional clarification is not required and the narrower source-identity correction proceeds without a G stop. No owner is inferred by this proposal.

Do not conflate the six-path census/receipt at `6e7460c33c363c4b53f677dfd160643b62d68001` with R1's source base `185a0f327199d75d06410f9bc841131e0bf33b1e` or the independent review frame `566d194402dec721d162cff83b4bf2d16442d52e`. The earlier receipt records 1,511 dependency paths and 1,479 Python files but expressly does not compute recursive route reachability or PEP 562 selection. At the review frame, the six owner-source hashes matched; the listed changes since R1 were three metadata/document paths only.

## Source anchors and evidence limits

All line numbers are under `policy-engine/` and refer to the reviewed source frame.

| Fact | Path and lines |
|---|---|
| Owner entry modules | `tools/quality/validation/layer3_gy_confidence_ledger_contract.py:51-54` |
| Actual catalog facade call | `tools/quality/validation/layer3_gy_confidence_ledger_contract.py:712-716` |
| Runtime-selected producer refs | `tools/quality/validation/layer3_gy_confidence_ledger_contract.py:1087-1097`; source declaration in `src/polisyos/runtime/quality/design_generation.py:141` |
| Import-time/loaded-runtime comparison | `src/polisyos/runtime/quality/confidence_ledger.py:5671-5712` |
| Repository-local closure traversal | `src/polisyos/runtime/quality/confidence_ledger.py:5864-6021` |
| Literal-only direct binding and decorated-definition checks | `src/polisyos/runtime/quality/confidence_ledger.py:10274-10425` |
| Two literal route maps | `src/polisyos/data_forge/read_api/surface_routes.py:5-17` |
| Tuple construction and dataclass | `src/polisyos/data_forge/read_api/surfaces.py:15-29` |
| Eager facade exports and lazy module routing | `src/polisyos/data_forge/read_api/__init__.py:8-17, 67-79` |

The actual selected route is two owner entries, four runtime-declared producer refs, the catalog callsite, eager facade bindings, the two literal maps, and four mapped surface modules. It is not the entire older ten-path read_api receipt and not the 1,479-file syntax census.

Reviewed source hashes: `confidence_ledger.py` `95fcbe2bd84165a6e405e3e7439d842a44623f4c1283c91cde0de966d5dca2ac`; `design_generation.py` `e8b7a1709ea7431f1026e152857b1b359c76a9cfc8fcff5316be2a7e815e8a8a`; `layer3_gy_confidence_ledger_contract.py` `4157235f0a4cf086f468fed80c8b58cc03f1801c5407cf6b6041e7a323faed82`; `read_api/__init__.py` `663b16941e870aaf1b2d2756fe227c580b65b7da10a64d4b60d824fdcec3bc27`; `surface_routes.py` `ab55d4df959fda4273c4cd13e5da4764bdf0930bb3a209b8e0ad6e4d1c931b06`; `surfaces.py` `d1e1824563de3811ac617def946ae569e95451bb94e75986f04f24fefaf46588`.

R1 packet SHA-256 is `3709326643b1c3551be869a3ae08cbd396369bb03ee9fb3580619bca3d290f4e`. Independent review SHA-256 is `c5898857e342d27dcf41f0b14d6ae2817f27c2d8001117a1f54beb15666cfa79`; its verdict was `HOLD_FOR_G_HANDOFF_CORRECTIONS`. This proposal incorporates the technical corrections but remains unaccepted.

## Status and pattern pass

- G acceptance false; source acceptance false; closure IDs empty.
- The actual owner result remains a refusal with no candidate projection. Keep `verification_missing` / unavailable until the real writer and consumer pass.
- Source identity does not establish scientific adequacy, law, custody, permission, currentness, or publication authority.
- P29/P32: behavioral owner writer/consumer and corrupted-control refusal.
- P37/P38: bind all deciding inputs and name the concrete source-identity versus syntax-proxy divergence.
- P40: treat assignment, decorator/class, facade re-export, and runtime comparison as one class boundary.
- P41: preserve the provenance of the 6e receipt and the separate 185a/566d frames.

The source-identity capability remains `verification_missing` until the real owner writer and consumer recompute successfully. This proposal claims no closure.
