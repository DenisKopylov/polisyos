# Independent review — L01 DDM witnesses

**Disposition: GO for the bounded synthetic runtime mechanics; no LA-054/LA-055 closure.** I found no proxy-only proof or source mutation in the reviewed slice. The evidence reaches the library registry gate, while actual live-feed completeness, deployment persistence/consumer, and institutional signoff remain outside it.

## Frozen source and execution identity

The reviewed checkout is `codex/e02-L01-custody-20261008` at `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b`, tree `d9a4e73a0e85fa11f865bf643c1b63fbe66c2767`. The captured pytest warning points to the reusable venv under `e02-integration-6971`; its editable `.pth` targets that sibling checkout. The sibling checkout is also at the exact `f00dd…` commit/tree. All 12 paths in `checks/environment/declared-check-inputs.json` match the frozen target blobs (12/12).

Because the removal folder retained output but no injection driver, I ran the four tamper cases once with `_IMMUTABLE_VALIDITY_PROJECTION_FIELDS = ()` patched in memory and `policy-engine/src` explicitly on `PYTHONPATH`. The imported `audit.py` path was the frozen L01 source. All four cases failed at the gate assertion because promotion became `True` (`R4_promotion_allowed`), as expected. The production file was not edited. This is a genuine remove-the-property/keep-the-DTO-and-verifier-fields probe. The current worktree also shows an untracked `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/L01/` path; it appeared during this review and was not created or touched here.

## What the witnesses establish

`test_full_acceptance.py::_registry_context` builds a synthetic report and audit, then calls the real `DriftAndDegradationMonitor.evaluate_window`; the monitor runs `_check_bound_calibration_validity` and builds the real registry record. The test JSON-serializes and reloads that public DTO, rebinds it against the exact report/audit/time/trigger inputs, and calls `evaluate_registry_gate`.

The captured six passes are one successful public DTO round-trip/rebind, four tampered immutable-projection cases (digest, calibration ID, detector ID, regime ID), and the distinction between unavailable triggers and an observed empty list. The fresh-process probe separately confirms: exact synthetic context permits R4 after rebind; a tampered digest blocks with `calibration_report_binding_not_established`; missing trigger observations block with `calibration_validity_not_established`. Before rebind, the reloaded record fails closed because the private checker evidence is not serialized.

This tests behavior in the actual producer-to-registry-to-library-gate path. The saved JSON file and child-process reload exercise public DTO serialization; they do not exercise a durable registry service or deployment-facing consumer. For that external route, the actual durable artifact is `artifact_missing` and the deployment surface is `surface_missing` in these receipts. The source schema is titled `DDM-15.7 ModelRegistryReadinessRecord` and has no explicit schema-version field, so these receipts also do not establish the distinct-v2 migration requested in the current E decision.

## Property versus predicate

The property exercised is that a stored validity projection cannot regain current checker authority unless its immutable report/calibration/detector/regime identity binds to the supplied source report and audit. The implementation compares those four values, issues private checker evidence only from the canonical validity checker, and the gate consumes that evidence. The test mutates each value and checks the resulting gate decision; the removal probe demonstrates that preserving DTO shape and verifier labels is insufficient. Within this bounded property, the implementation measures the behavior rather than a marker or field name (P29/P38).

A separate predicate remains supplied rather than established: `observed_invalidation_triggers is not None` is treated as an observed feed, so `[]` becomes `observation_status="observed"`. In the fixture, the list is `institutionally_supplied`; actual feed completeness/freshness is `not_established`. A caller with a missing, stale, or incomplete feed could still supply `[]` and obtain the synthetic valid branch. The code does not independently establish feed completeness or freshness. This is the declared LA-054/055 owner-input boundary, not evidence against the bounded rebind mechanic (P37/P38).

## Original criteria and remaining boundary

The original LA-054 criterion asks for current source/report/model/detector/regime/metric/window/rule/expiry references, a complete fresh invalidation feed, and a fresh public deployment consumer. It also calls for wrong-subject, expiry, trigger, metric, and missing-source refusal coverage. The six-test receipt establishes only synthetic report binding, projection tamper refusal, and unavailable-versus-empty input semantics; the three-process probe reuses the same synthetic fixture. It does not establish the live producer inputs, source-feed completeness, deployment route, or full acceptance matrix.

The original LA-055 criterion requires persisted veto precedence and an identity-bound institutional R2 exception. These six passes and three fresh cases do not exercise the R2 signoff matrix or prove an institutional issuer. A boolean `owner_signoff` is only a library branch input. The current E decision records both findings as partial/limited and names the outstanding live-feed, deployment-purpose, target-consumer, and identity-bound R2 owner inputs; the closeout `findings.json` says `G_closure: not_adjudicated` and `next_decision: resolve_named_residual_then_G_adjudication`. The E execution receipt for profile diagnostics is for a different candidate/slice and adds no DDM authority.

**P40 bucket:** the feed-completeness/purpose/consumer gap is the same declared external-input class one level deeper, not a new finding class. No code repair follows from this review. The minimum closure input remains the named owners’ current source and complete freshness-qualified invalidation feed bound to a target deployment consumer; LA-055 additionally needs versioned purpose/precedence and identity-bound R2 evidence. These inputs are not established by the reviewed receipts.

## Evidence references

- Original criteria: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md:4053` and `:4108`.
- Current E disposition: `policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/2026-10-07-thirteenth-wave/E54-current-decisions.md:97-98` and `integration/connected-closeout-plan-2026-10-08/findings.json`.
- Runtime source: `policy-engine/src/polisyos/ddm/calibration/audit.py`, `integration/monitor.py`, `integration/model_registry.py`, and `contracts/events.py`.
- Fixture tests: `policy-engine/tests/unit/ddm/test_full_acceptance.py`.
- Outputs: `_build/e02-L01-20261008/checks/ddm/{stdout.txt,junit.xml}`, `ddm-fresh/{probe.py,stdout.txt,synthetic-persisted-context.json}`, `ddm-removal/{stdout.txt,junit.xml}`, and `checks/environment/{identity.json,declared-check-inputs.json}`.
