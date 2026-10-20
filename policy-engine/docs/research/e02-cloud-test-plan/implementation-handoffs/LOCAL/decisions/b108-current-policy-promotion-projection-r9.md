# B108 current policy-promotion projection — R9 proposal

Status: author proposal for independent G review; no formal closure. `closure_ids=[]`, `proposal_ids=["B108"]`.

## Property and evidence

The selected objective score is source-recomputed under the configured rule and current simulation result. That score is necessary for score-driven completion; it is not a permission to publish a promoted policy. A current promotion projection also needs a protected owner receipt that binds the owner-issued action to the current candidate, score admission, and permitted scope.

The current default runtime has no such receipt producer or verifier. The L6 promotion runner is withheld as `bridge_missing`; `RunPolicyPromotionNode` reports that direct runtime promotion is unsupported. `PolicyPromotionResult`, nested judge/readiness results, and params markers carry no issuer-owned receipt. A non-null typed value or a status marker therefore cannot establish a current promotion.

The R8 independent review (HOLD, `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b108-no-score-candidate-r8-independent-review-20261020/review.json@751aca8e1f61a1530143ca9003a28742feafe77b89adfe68cac12331f6e97def`) demonstrated two paths in the default workflow:
- caller feedback could remain positive after L6 changed the final funnel action to reject/defer, then be written to current params;
- old promotion params survived the runtime branch and were consumed by translation, compliance, and output-bundle nodes, with no promotion node between them.

The inspected default chain is blueprint runtime → policy translation → translator compliance → output bundle → decision packet. Run GET DTOs do not return `params.policy_promotion_result`; the issue is an internal workflow current-state emission/consumer path. The candidate-only bundle and raw stage feedback remain report data, not promotion authority.

## Options

1. **Keep promotion report-only until a protected owner bridge exists (implemented candidate; recommended).** Recompute and retain the final selected-score admission, archive prior current fields and new caller feedback, clear current promotion and derived output pointers, and make translation/compliance/current-bundle consumers use one fail-closed resolver. Direct bundle construction rejects `promoted=true` because its input type has no receipt. This preserves raw evidence and candidate evaluation while withholding current promotion. No owner or law is inferred.
2. **Add an issuer-owned receipt/bridge.** This needs a named authority owner, a strict receipt schema, source verification and currentness semantics, the candidate/score/action binding, persistence, revocation/reissue behavior, and downstream consumers. No current source contract or issuer is available in this slice. G must appoint/confirm the owner and accept the contract before implementation can assert a receipt.
3. **Treat a typed PromotionResult, verdict, or status flag as sufficient.** Rejected: these are self-carried report facts, and the reproduced caller/stale-state paths remain green if the actual owner receipt is absent. This would repeat P05/P32/P37.

## Candidate behavior and migration

The R9 candidate uses source-recomputed score status only to explain why a current promotion projection is unavailable. Even an AVAILABLE zero and completed funnel yield `reported_only / not_established` because no protected owner receipt exists. INVALID, UNAVAILABLE, and NOT_ESTABLISHED are retained as distinct score admission reasons. Existing promotion params, judge/readiness payloads, associated output refs, and new final feedback are retained in `reported_policy_promotion_history`; the immutable artifacts remain in CAS. Current fields and derived brief/compliance/output pointers are removed before downstream workflow nodes run.

Translation and compliance skip without a current owner result, including when a stale brief is already present. The bundle node strips self-asserted promotion results and rebuilds a prior promoted bundle as candidate-only. When no current owner result exists, the direct builder excludes caller-supplied judge/readiness/brief/compliance fields and prior bundle-output refs from its current candidate bundle snapshot; the caller's input state remains unchanged. Runtime projection archives prior current fields and all output refs declared by the bundle node (including the frontier report) before downstream nodes run. The direct builder rejects a positive promotion result. Future migration must not upgrade legacy history; it must add a real receipt producer/verifier and a source-bound consumer before allowing current promotion again.

This changes the internal contract: current promotion output is withheld on these paths until the receipt bridge exists. It does not revoke or erase any external/historical institutional act. Existing raw feedback remains an audit report. It does not claim HTTP exposure or bypass of Phase 5/publication controls.

## Falsifiers and next checks

The candidate's behavioral controls cover unavailable score, recomputed INVALID from changed source, valid numeric zero, a complete positive typed caller payload plus fake “verified” marker, cached stale brief/compliance, and a direct builder call with `promoted=true`. Removal controls must fail if the reporting projector stops clearing stale state, if either consumer parses the raw param again, or if the builder accepts the positive payload.

After independent review, run the composed reporting→translation→compliance→bundle workflow and persistence/restart controls on one frozen source. Verify exact state writes, current/history round-trip, candidate-only bundle contents, output cache reissue, and native repository gates. Runtime replay, persistence/restart, full workflow, installed consumers, and formal G adjudication remain UNRUN/open. Any future authority-positive route remains held on an owner decision and genuine receipt input.
