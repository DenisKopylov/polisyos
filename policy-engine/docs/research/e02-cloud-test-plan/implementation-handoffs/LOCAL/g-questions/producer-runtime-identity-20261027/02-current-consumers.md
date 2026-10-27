# R23 clarification: actual MethodJob source admission and proposed runtime join

**Disposition:** immutable RAW clarification only. This corrects R21's overstatement that an existing consumer already requires both producer identity and execution state. The two predicates are a proposed new joined MethodJob law; the current code does not join them. No canonical edits, tests, or status changes were made.

## Frame and source readback

Repo: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
Product: policy-engine
HEAD/tree: 1fd513e8b2a7e3405d61023c2dffa22ce9a88447 / c3c614e7d34d33abcc9a11a2ce0b847615e24cbc

| File and SHA256 | Actual consumer behavior |
|---|---|
| src/polisyos/scientist/methods/autotune/registry.py @ 99ce5e98e88e524f19a4dd1f166aa46b2fa06edce21170280415bb8b1015e33a | _methodjob_source_admission_failure recomputes request, input-slot/source-data, dispatch binding, CAS lineage, result/evidence, and metric consistency. It does not consume R19's RAW producer-code fingerprint and does not validate a nuisance-cache run witness. _methodjob_execution_provenance_failure returns methodjob_execution_provenance_not_established for a marked MethodJob. ChampionRegistry._promotion_binding_failure calls the same checks again. |
| src/polisyos/scientist/methods/autotune/runtime.py @ 5a91c4c8bfc5de8eb5ec5666f81c364ef5c31f852fa8d9f03e7a23036a83e4ed | _evaluate_candidate calls MethodJob source admission for MethodJobBenchmarkEvaluator at lines 2172 onward. On failure it strips the primary metric and sets methodjob_source_rejected. If those checks pass, execution provenance remains not_established; the evaluation is non-promotable while retaining measured_candidate status and a note. |
| src/polisyos/scientist/methods/autotune/execution_work.py @ 96832083c087c9300865eab0fef69b2836c6fb6acd296231c05b27a039647e40 | MethodJobExecutionWorkPacket schema 1.2/1.3 is authority_purpose engineering_execution_observation and candidate_status diagnostic_only. It records observed bootstrap work and artifact/request refs; it is not the current source-code/cache admission gate. |
| src/polisyos/scientist/methods/autotune/models.py @ a83f8ee607349126395658143040510f4a5c4245155f8e1481f47f532e79a2ae | BenchmarkEvaluation's execution_work_packet_ref and available/unavailable/rejected status are separate optional diagnostic fields. |
| src/polisyos/scientist/methods/autotune/source_profile_verification.py @ 270afff675c424a30fe080708c0d0103c0be58be0ef09daf450a16e781bb4348; src/polisyos/scientist/methods/autotune/bayesian_generator.py @ 060a92bea9849686976a991c185641469f773d8b0ef2f5f21ffb7985d0dd2a75 | _apply_warm_start uses _verify_search_source_profile_receipt. This is a distinct Search source-profile consumer, not evidence that the new MethodJob source/cache pair is already enforced for GP or warm-start. |

## Do not conflate the generic diagnostic packet with MethodJob admission

The actual MethodJob path is runtime._evaluate_candidate -> registry._methodjob_source_admission_failure -> the separate execution-provenance check, then a later ChampionRegistry._promotion_binding_failure recheck. The current source admission concerns request/data/dispatch/result lineage; its name does not mean producer-code identity is admitted. The R19 producer dependency fingerprint is unadopted RAW work. MethodJob execution provenance still cannot establish who executed the result.

runtime._search_work_packet_admission_failure is used on the non-MethodJobBenchmarkEvaluator branch. It validates the separate Search work packet and can set source_work_packet_rejected. The MethodJob path does not use that as its source/cache law. The optional diagnostic packet is not an automatic home for a new authority claim; exact artifact placement is deferred to the existing owner after the semantic decision.

## Proposed law, not current invariant

If selected, the actual MethodJob admission consumer would join two separately recomputed predicates to the same result and evaluation:

1. Static producer implementation identity: loaded producer source/code, runtime profile, and exact selected dependency-artifact identity. This identifies what implementation was loaded. The R17 audit found that nearest-ancestor uv.lock cannot identify a wheel outside a checkout; a loaded-source origin and installed dependency-artifact basis remain required. Editable source and RECORD-backed wheel origin must be typed separately. RECORD is not publisher authenticity.
2. Per-attempt fit/cache witness: actual attempt identity; recomputed X/T/Y and nuisance-contract fit identity; cache miss/hit/produce outcome; exact selected _ATENuisanceFitCore identity and content proof; and linkage to the result that used it. Capture the selected entry, not unrelated process cache contents.

Both are required by this proposed join; neither substitutes for the other. Missing or malformed state remains unavailable/rejected under current status semantics. This adds no execution provenance, scientific correctness, issuer authority, unit law, or promotion authority. Downstream GP/warm-start consumers need the same join only if G explicitly selects that eligibility rule; their current distinct receipt checks do not establish it by implication.

## Deciding runtime and installed-source evidence

R20 actual cold -> first-fit -> same-study warm -> second-study output is at dynamic-author/r20-cache-state-diagnostic-r1/execution-r3/lifecycle.json (SHA256 9e73808b57f7506e0948fae379073167848c9e51a91216e207ee4894d149ed47), stdout (SHA256 9ff4031ada1bb8595fa8ddd8ede11831235e89c26e164b3fe8ec4b287bd96d22), and supervisor result (SHA256 f9467b0e7fd9af442d5bf167dc776a46b478f780f4ece466a6dd360bbcc31d0d). The cache filled from zero to one to one to two entries. The diagnostic fingerprint was present cold and unavailable after the first actual fit, including on the same-study warm read. Only an in-memory exact builtin RLock classifier was enabled; it did not alter source or clear cache. That experiment proves an RLock exception alone does not recover the fingerprint.

R17 N3 source-identity report SHA256 d450b8d9eaf509ed675c4e675ea2942b1522b35d7ac52b36f16ce3720268b725 and addendum SHA256 dae64bbad2095da7c5707ed7874bbeb73af1fcd6f5f3445674709e3b156110e8 show the inspected venv is editable source, not wheel evidence. A normal wheel outside the checkout has no project ancestor uv.lock. CWD or neighboring locks are not installed-source evidence. Keep source identity unavailable until an admitted owner binds actual loaded source origin and selected dependency artifacts.

## G choice requested

Ratify or reject the new MethodJob join: static producer implementation identity plus a per-attempt fit/cache witness, recomputed and bound to the same MethodJob result/evaluation at the actual MethodJob source-admission consumer. Decide separately whether a MethodJob result entering GP/warm-start requires that same joined state at eligibility. Keep the generic Search diagnostic work-packet route separate. Select semantics before the existing owner chooses the narrow artifact/field; do not upgrade MethodJobExecutionWorkPacket by adjacency.

The current SourceUnit law and status remain fail-closed. Historical records must not be retroactively upgraded. If a versioned representation is selected, reader support comes before new writes; unsupported readers refuse new forms; rollback stops writes and preserves readable history. Old rows remain inspectable but do not gain a missing source identity or cache proof.

Required falsifiers: real cold/warm/second-study flow; key-preserving core-content mutation; removal, wrong key, or conflicting cache identity; altered X/T/Y/contract; unrelated-cache reorder; editable source and wheel outside checkout; CWD/neighbor-lock drift; and old/new reader plus rollback replay. Test through the actual MethodJob consumer/status path, not packet markers.

**Not established:** a normal wheel's installed-source/dependency identity, complete core-content verifier, selected G decision, current joined MethodJob law, GP/warm-start eligibility, execution provenance, or promotion.
