# PA1 independent review — frozen initial bridge, 2026-09-08

## Findings first

**PA1-R01 — P1 / NEW class: post-generation signed evidence has no production path into the job's current disposition.** This is `bridge_missing` (P01/P02), an engineering gap owned by PA1, not an institutional appointment blocker. It prevents an `executed` claim for this frozen package even though the stated refusal controls are valid.

`src/polisyos/runtime/http/services/control/run_lifecycle.py:2828` reads normative evidence only from the queued request context, which was supplied before that job's compiled CAS source existed. `:1450` exposes a useful source-aware producer, but it only returns/persists a new composition; it does not admit that result to an existing job's current head. `:2092` and the shared current-reader path continue resolving the sidecar ref already stored in job progress. The source-bound v2 permission requires the exact compiled and leaf CAS identities. The positive worker test supplies those identities by building the fixture first and replacing the worker's compiler (`tests/unit/runtime/http/test_control_service_di.py:692`, `:717`); that is a valid mechanism control, but does not establish a reachable post-generation authority response in production.

Concrete case: run the actual worker with no schedule; obtain its persisted compiled source and request; create independently signed fixture permission **after** this source exists; call the real `resolve_generation_value_choices` owner; read the job through both actual outward readers. The new owner result is `authorized` with `candidate_cgf_shadow`, while both readers retain the old `blocked` sidecar. The original authority was correctly refused, but the requested evidence response cannot reach the current lifecycle.

[Independent execution, full streams and RC](independent-temporal-intake.json) decides the finding: RC **0**, 33.129 seconds; `new_sidecar_consumed_by_current_job=false`. The script asserts the actual mismatch instead of manufacturing a failing suite status. Its upstream compile input is the existing canonical fixture generation port, explicitly a mechanism witness and not a governed production design. [Witness source](review_temporal_intake.py).

The [complete source census](independent-intake-census.json) independently reconciles git-index and filesystem identity sets over **all 2,630 `src/**/*.py` files**, then AST and token-stream symbol identity sets; all identity differences and ambiguous sets are empty. The entire production call set for `resolve_generation_value_choices` is the initial worker and the missing/corrupt-sidecar refusal fallback. Neither supplies evidence after completion. There is no third hidden call that consumes the new authorized sidecar. This is a complete source-symbol census, not a claim to enumerate external deployment code.

**Smallest repair:** extend the existing authenticated control-job command owner, preferably a typed `POST /control/jobs/{job_id}/normative-evidence` intake adjacent to the existing job status/control routes. Derive the compiled ref from the tenant-owned completed job, not the submitted request. Pass only typed evidence refs through the existing S8 and compiled owners, persist a new event/sidecar with previous-head binding, and atomically advance that job's current disposition. Keep the original sidecar and event readable. Both current readers already share the correct egress boundary; reuse it. A concurrent response must not silently replace a head it did not observe: compare the expected prior head/revision or use the existing store's equivalent conditional operation. Empty deployment trust remains valid and refuses. This integrates an external signed statement; it does not implement appointment, notification, or an administrator workflow.

Falsifiers: generate source first, then sign the exact source, submit via the actual intake, and observe its new current sidecar through both readers; wrong job/source/role, stale or damaged signatures, untrusted candidate-supplied keys and stale concurrent head refuse without licensing a ranking. Remove the intake-to-current-head transition while preserving receipt fields and signed positive owner output: the lifecycle control must go red. The test must not precompute the compilation and feed its future identity into the initial request as the sole positive.

P40 bucket: **NEW temporal producer-to-lifecycle bridge class**, distinct from the already widened source-membership, signature-replay, current-egress, and source-preserving-refusal classes. This finding does not call for additional recursive verifiers or reopening S8's standalone mechanism. Root accepted it as the D3b append repair before closure.

No other blocking finding was established in the frozen review scope below. No production/test source was edited by this reviewer, and no commits or full suites were run.

## Stage A — specification compliance

Reviewed D3/D3a in `docs/superpowers/plans/2026-09-08-gy-phase5-execution.md`, the full PA1 `Done when`, and [stage3 handback](stage3.md). The following conclusions apply to the initial frozen package; they do not credit a later repair not yet reviewed.

| Requirement | Evidence and conclusion |
| --- | --- |
| No schedule: zero ranks, actual frontier, persisted typed request | Actual worker `[missing]` and source-preserving missing-sidecar controls exercise this correctly. The source front mapping is retained and dominance stays `not_established`. |
| Authority-lane mismatch | Actual worker `[wrong_role]` checks `p20_normative_authority_scope_mismatch`, not the superseded resolver-absent reason. |
| Silent equal-weight / historical-prior / proxy default injection goes red | The common generic coherent leaf+composition mutation is refused by owner recomputation. The three labels are adversarial cases of the same structural unauthorized-ranking invariant, not separate ad hoc parsers. Leaf-replay removal makes the forbidden recommendation escape. |
| Ranked consumer exists with a nonvacuous positive | Independent signatures, role, mandate, scope and source binding reach existing S8 recommendation. Initial worker positive is a valid fixture mechanism control. Production post-source evidence intake remains PA1-R01. |
| P27 owner-first | Existing compiled DTO owner derives/replays complete parent/leaf membership; existing S8 owner handles signed permission and exact leaf source. The S8 leaf explicitly disclaims compiled-membership authority. |
| P28 default changed with run-emitted strangle | The real worker unconditionally runs the bridge; its strangle source/disposition identity sets are recomputed. The default-call removal retains markers/completion and fails on the omitted disposition. |
| P29 substantive proof | Historical and current recomputation run the real source and signature owners. Existing removal records falsify actual authority and worker behavior. |
| Full denominator / fake / novel source | Complete leaf and candidate identities are checked against owner-derived sources; foreign compiled/leaf/frontier sources and coherent altered composition refuse. The source census has independently equal identity sets. |
| Data-only growth | New graph leaf identities flow through generic source enumeration with the same code. This is accurately labeled a structural fixture witness, not the canonical policy denominator. |
| Receipt epochs | Generation binding uses additive authorization/admission v2 and new disposition/composition v1; old standalone S8 v1 handling remains present. No promotion epoch edit in this PA1 diff. |
| Existing signatures stay honest when consumed | Both service readers share current replay; expiry and signature corruption revoke current recommendation. Audit refs remain historical. |
| Full capability: external input → current lifecycle/surface | **Not complete in the frozen package: PA1-R01.** A newly answered request remains a detached producer result rather than the job's current disposition. |

## Stage B — correctness, security and quality

The implementation resolves exact CAS bytes and typed source DTOs before projecting. Parent membership is checked by the compiled owner over the real leaves, rather than by a flag from S8. Source-bound v2 authorization checks the compiled ref, leaf ref and node; the signed frontier must name the same leaf source and its proposed selections must belong to that source. This admits scoped selection permission only: the new disposition disclaims Pareto, empirical, legal and publication authority.

Deployment trust enters through the typed app/container/service constructor path. Candidate context is parsed only as evidence refs; malformed `trust` input is a typed refusal. The S8 owner checks independent signatures, configured roles/case/scope/mandate, status, effective time and expiry. Current disposition reconstruction compares the persisted historical object with recomputed content and then computes the current response; stored green fields do not authorize emission. Historical v1 admission still resolves via its own typed schema.

Both outward job readers delegate to `_current_normative_job_record`. Missing or corrupted sidecars with a readable compiled source produce a fresh typed refusal preserving the source fronts; unreadable source becomes `not_established`, not empty. This is an honest fallback, and the return does not mint source or institutional authority. PA1-R01 concerns advancing to **new evidence**, not replaying the current evidence incorrectly.

The CAS adapter unwraps only the exact runtime `GuardedDependencyProxy` to its existing `FileSystemCAS`; it does not open a second store or accept arbitrary `_target` objects. The existing CAS itself continues enforcing ownership on bytes/manifests/signatures. This bypasses the proxy's timeout/circuit-breaker wrapper for S8 calls because the existing S8 owner accepts concrete CAS only; ownership is not implemented by that wrapper. No authority leak was established from this adapter. Supporting other backends remains the explicitly stated adapter boundary.

`NormativeRunStrangleReceipt` contains literal markers, but acceptance does not turn merely on their presence: complete membership is recomputed and the actual worker-removal probe goes red. That meets the declared bounded strangle property; no hypothetical recursive verifier is requested.

## Reviewed package and verification bounds

Source comparison was against slice base `3d572c146` / docs-only HEAD `55b0329`, including the untracked new test and release fragment:

- `src/polisyos/runtime/http/app.py`, `container.py`, `services/control/generation_cycle.py`, `services/control/run_lifecycle.py`;
- `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`;
- `tests/unit/runtime/http/test_control_service_di.py`, `test_normative_generation_bridge.py`;
- the PA1 portions of the HTTP/quality README companions and `release-fragments/unreleased/2026-09-08-gy-pa1-generation-disposition.toml`.

Read the complete final targeted JUnit identity list and `stage3-final-targeted.json` (RC0), and the separate collection/reconciliation record; did not repeat that suite. Read the complete ordinary and removal control implementations and preserved removal results (each actual forbidden ranking or omitted worker output, not a harness crash). The independent additional execution was the concrete PA1-R01 witness and the complete source census above. The final lane guardrails/public surface checks remain root-owned; their result was `not_established` at this review boundary. No canonical fully evidenced promotion or actual institutional appointment is claimed by this review.

## Review command index

Commands were each the sole child gate invocation; the capture wrapper preserved real return codes and complete stdout/stderr in the linked JSON.

| Exact child command (cwd `policy-engine`) | RC | Wall seconds | Complete record |
| --- | --- | --- | --- |
| `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.review_temporal_intake` | 0 | 33.129 | [record](independent-temporal-intake.json) |
| `.venv/bin/python -m docs.superpowers.journals.gy-phase5-evidence.pa1.stage3_census` | 0 | 19.805 | [record](independent-intake-census.json) |

The lane `.venv/bin` is first in each child PATH, and lane `src` is first in PYTHONPATH. Full records include exact cwd and child command. Research-only witness scratch was under `.tmp/gyphase5-pa1-independent-review`; it did not use the reserved composed-WMR scratch or any other lane/worktree.
