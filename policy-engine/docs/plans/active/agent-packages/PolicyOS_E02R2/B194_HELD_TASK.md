# B194 held residual — served simulation support

**Status:** held. The independent review permits keeping B194 held with one named missing capability. It is **NO-GO** for closure and for an implementation-ready handoff. Source, test, removal-probe, control, and four-base outcomes are `UNRUN`.

## Property and exact residual

A result computed only from successful draws must remain a useful candidate estimate explicitly conditional on those draws. It cannot be presented to a protected consumer as the unconditional downstream distribution unless the producer records and a consumer verifies the complete requested-draw denominator, typed per-draw outcomes, source basis, and support.

The one residual is a **production simulation-evaluation contract that supplies typed outcomes for each requested draw and carries source-bound support through the existing Monte Carlo result, persisted propagation report, derived envelope support, and one verified intake consumed by ConfidencePass, normative arbitration, and `decision_packet.enrichment`**. This is an engineering capability blocker, not a missing data record or external institution. Keep successful values available in the candidate band with a typed conditional/unknown limitation; authority, promotion, and publication may not treat the successful-only moments as complete evidence.

The source review found one production `PropagationDispatcher` caller: `PropagateUncertaintyNode.execute`. Its callback is a frozen metric plus an affine sensitivity map, not the model/simulation solver, and it has no input-domain refusal boundary. A monkeypatched callback or direct `MonteCarloPropagator` test cannot establish the served positive witness. The actual producer bridge is therefore still missing/not established.

## Consumer boundary and discrepancy

The first design named ConfidencePass and normative arbitration. The independent review found a third current consumer: `decision_packet.enrichment` emits point, bounds, and optional CI without support/conditionality. The shared verification boundary must reconcile the source-bound report and per-metric outcomes before all three consumers use the estimate. A typed marker alone is not proof.

- ConfidencePass counts `gate_eligible` without reconciling it to the draw denominator.
- Normative arbitration extracts point and interval width; a syntactically valid conditional envelope can become a numeric ranking input without a missing-binding warning.
- `decision_packet.enrichment` exposes point/lower/upper/CI without a support field or limitation.

These are source-level divergences, not test outcomes. No consumer or producer behavior was run.

## Required evidence before implementation handoff

The broker must admit whole-file four-base replays before any product edit. The minimum set from the reviewed design is:

- `tests/unit/foundry/uncertainty/test_monte_carlo.py`
- `tests/unit/remediation/test_uqp_03.py`
- `tests/unit/foundry/uncertainty/test_uncertainty_propagation.py`
- `tests/unit/scientist/nodes/test_propagate_uncertainty_node.py`
- `tests/unit/scientist/nodes/builtins/simulate/test_propagate_uncertainty.py`
- `tests/unit/ir/test_uncertainty.py`
- `tests/unit/scientist/governance/test_confidence_pass.py`
- `tests/unit/scientist/nodes/test_normative_arbitration_node.py`
- `tests/unit/scientist/nodes/test_decision_packet_node_v3.py`
- `tests/unit/scientist/nodes/builtins/decide/test__decision_packet_contracts.py` if its payload/schema changes.

Freeze the eventual source write set first; add every newly touched importer and historical artifact validator to the same four-base queue. Presence at each base and all outcomes are `UNRUN` until the broker records them. This task does not edit the broker-owned queue.

The served positive must use the actual simulation evaluator, persist and reload the result/report/envelope, account for 100 requested ordinals (including 50 typed failures in a distinguishing case), and pass verified support through all three consumers. The candidate-preserving control must show all-success computation and a useful conditional result for a partially evaluable input without blanket refusal. The protected consumer must carry a typed limitation or withhold the conditional bounds.

The marker-retaining removal probe removes per-draw rows while preserving `mc_n_failed`, `n_samples`, `gate_eligible`, and report-status markers; verified intake must fail because it cannot reconcile the ordinal outcomes. A stale `gate_eligible=True` marker with typed failures must also be refused. Distinguish transient retry of the same draw from input-domain inapplicability and fatal/unknown failures; do not infer retryability from exception text.

Version the persisted report and any envelope schema that gains fields, with historical serializers/readers that preserve prior bytes and semantics. Do not add a second posterior owner or claim sequential-stopping/QMC closure; those remain outside B194's bounded residual. No exact live register row is established for this owner seam, so this note proposes no debt-register row or closure.

## Evidence

- Source/design: `/Users/deniskopylov/.codex/scratch/e02-r2-b194-held-design-20260925.md@sha256:4c0fb0d5a50e7b7d871c97600bfcf8266eb9c836692098b0b9850d0b9a530272`.
- Independent review: `/Users/deniskopylov/.codex/scratch/e02-r2-b194-independent-review-20260925.md@sha256:e3dff0e527e1d6fc65407e63b8db234d360b9f2a81d8391fcc5f41371d08898b` (conditional GO to retain held; NO-GO closure/handoff).
- Finding record: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/finding_record_probe.json#rows/B194` (record inspection only; behavior `UNRUN`).
