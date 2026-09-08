# Independent PA1 OpenAPI example delta review — 2026-09-08

No additional findings in the frozen D3f delta. **Approve the captured transport example and its existing-owner registration for final canonical export.** This approval does not turn the retained full scoped Ruff failure into a pass or establish the final generated-artifact checks, which the coordinator owns.

## Specification review

`src/polisyos/runtime/http/openapi_contract.py` extends the existing success-example-set map for `submit_run_normative_evidence`. The lazy helper validates the captured JSON against the actual `NormativeEvidenceSubmissionResponse` DTO with `strict=True`, then supplies the original values. The existing augmentation owner invokes callable example sets and deep-copies the result, matching its existing singleton-example behavior. There is no alternative schema owner, evidence producer, admission path or receipt epoch in this change.

The response is the actual transport emitted by the previously reviewed worker → later fixture signature → owned HTTP intake path. The retained observer calls the original `TestClient.post`, copies `response.content` after the real response, and returns that same response to the unchanged positive test. It does not replace the producer or edit the result. Capture command RC 0 and provenance identify the fixture source, signer and trust as fixture-only. The captured byte SHA-256 is `becbcde583102a388069266d50e0dbee946b7c642223a958f8234652b8e4ed65`.

The inline literal preserves the complete emitted response, including nulls, authority limitations, `compiled_membership_status: not_established`, existing projection warnings, fixture trust epoch, references and times. The actual scoped authorization remains `value_schedule_for_ranking`; its excluded authority purposes remain present. Qualification appears in the OpenAPI example description, without modifying the response contract or inventing a receipt field. The sample is explicitly not production authority, a canonical denominator or reusable evidence. No runtime evidence admission consumes this documentation value.

## Correctness and falsifier review

The focused test starts from the complete tracked OpenAPI schema, removes only this operation's existing examples, and calls the actual augmentation owner and full contract validator. It then compares the entire emitted value with the preserved capture, strictly validates the DTO and compares its complete JSON dump again. The positive therefore establishes transport shape and unchanged values, while its earlier worker/intake capture supplies the separate execution provenance.

The semantic probe derives the complete get/post operation identity set from the existing owner iterator and reconciles it against an independent traversal of the full JSON. I read both retained packets and recomputed their symmetric identity differences from those complete lists; both differences are empty. The gate's denominator is not narrowed to the new operation.

The registration-removal probe deletes only `submit_run_normative_evidence` from the existing map in memory. The captured payload, helper and fixture-description markers remain. The unchanged positive fails at the real full-validator assertion, before checking description or payload markers, with exactly `POST /api/v1/control/runs/{run_id}/normative-evidence: missing 2xx success response example`. The companion negative asserts that exact finding identity. This is a decisive registration/removal check, not a static registration-name test.

Evidence read: `pa1/openapi-response-capture-command.json` RC 0, 99.909 seconds; `openapi-example-final-green.json` RC 0, 65.208 seconds; `openapi-registration-removal.json` expected RC 1, 77.001 seconds. Their full command, environment, stdout and stderr remain in the evidence records. No test, generator or report producer was rerun by this reviewer.

## Preserved incidental finding and boundary

`openapi-example-ruff-final-v2.json` remains **RC 1**, reporting the duplicate `admit_epoch_validity_batch` key at `openapi_contract.py:4231`. The earlier definition at line 1643 evaluates `_epoch_validity_batch_example()`; the later literal wins. The preserved audit and handoff route this competing-example definition to **DS18 C03 and DS15 C03**, both executed rows that this lane may not repair. No suppression, removal or choice between those example values was introduced. Because this gate consumes the OpenAPI owner changed by PA1, this review makes no inherited/disjoint P41 claim.

P40 classification: D3f closes the already identified PA1 external-surface gap through its existing owner; no new class or deeper escape was found in this bounded delta. Prior authority-chain reviews remain in their own reports. Final canonical generation, API/client checks and common guardrails remain the coordinator's responsibility. After writing and reading back this review, this reviewer freezes all file writes for that verification boundary.
