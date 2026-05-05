# Scientist Claim Ledger

Related references: [Claims](claims.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [Research DAG](research-dag.md), [Human oversight](human-oversight.md), [Benchmark authority](benchmark-authority.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/claims/lifecycle.py`, `src/polisyos/scientist/claims/audit.py`, `src/polisyos/scientist/claims/diff.py`, `src/polisyos/scientist/claims/export.py`, `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`, `src/polisyos/scientist/policy_design/output.py`, `tests/unit/scientist/claims/test_lifecycle.py`, `tests/unit/scientist/claims/test_audit.py`, `tests/unit/scientist/claims/test_diff.py`, `tests/unit/scientist/claims/test_export.py`, and `tools/ci/check_scientist_best_in_class_phase2_1.py`.

The Claim Ledger is the Wave 2 object that links research, governance,
provenance, human review, UI export and audit at claim level. It extends the
Phase 1.1 `ClaimLedger` sidecar; it does not replace `ClaimRecord`,
`ClaimLedger`, `claims_ref` or the public `DecisionReadinessContract` ladder.

## Runtime Contracts

| Contract | Module | Role |
| --- | --- | --- |
| `ClaimLifecycleEvent` | `claims/lifecycle.py` | Append-only event for created, updated, merged, split, superseded, blocked, unblocked, reviewed and invalidated claims. |
| `AppendOnlyClaimLedger` | `claims/lifecycle.py` | Claim Ledger v2 sidecar with `schema_version = "2.0"`, current claims and ordered lifecycle events. |
| Audit persistence | `claims/audit.py` | CAS persistence, loading, actor attribution, event ordering and bounded-retention export windows. |
| Claim diff | `claims/diff.py` | Added, removed, changed support, changed readiness, blocked, superseded, counterevidence and reviewer-attribution diffs. |
| Claim export | `claims/export.py` | Public, reviewer and machine exports plus packet-level ledger and blocked-claim summaries. |

## Lifecycle Rules

- Every lifecycle transition requires an `actor_id` and non-empty `reason`.
- Events are append-only ordered by `occurred_at`; duplicate `event_id` values
  are invalid.
- Merge and split events preserve source claim ids in metadata.
- Supersede events preserve the superseding claim id or next claim ref.
- Publishable claims cannot be silently downgraded or deleted. They must remain
  visible as blocked, superseded, invalidated or reviewed with a reason.
- Blocked claims remain visible in reviewer and machine exports.
- Counterevidence, reviewer refs and source refs remain part of claim-level
  diff and export metadata.

## Packet Projection

Decision packets now include:

```text
claim_ledger_summary
blocked_claim_summary
```

When `scientist.best_in_class.wave2.phase2_1.claim_ledger_v2` is enabled, the
packet also includes:

```text
claim_ledger_v2_ref
artifacts.claim_ledger_v2_ref
```

Old packets without v2 events remain readable. Legacy `ClaimLedger` artifacts
render `lifecycle_status = "legacy_no_events"`.

Policy output bundles keep `claims_ref` and add `claim_ledger_summary` and
`blocked_claim_summary` to metadata when a claim ledger can be loaded.

Human-review packets prefer `claim_ledger_summary` and `blocked_claim_summary`
from the decision payload, with legacy `claim_readiness_summary` as fallback.

## Exports

| Audience | Visibility |
| --- | --- |
| `public` | Publishable claims only; blocked/internal/draft claims are listed as omitted. |
| `reviewer` | All claims, including blocked and superseded claims. |
| `machine` | All claims, including blocked and superseded claims, with counts, omission metadata and bounded-retention window metadata. |

## Migration

1. Keep Phase 1.1 `ClaimLedger` readable as `schema_version = "1.0"`.
2. Persist v2 lifecycle events as a sidecar; do not mutate v1 ledgers in place.
3. Keep `claims_ref`, `claim_ledger_status` and `claim_readiness_summary`.
4. Add `claim_ledger_v2_ref` only behind the Wave 2 feature flag.
5. Render old ledgers with `lifecycle_status = "legacy_no_events"`.

## Rollback

Disable `scientist.best_in_class.wave2.phase2_1.claim_ledger_v2`. Decision
packets continue to include v1 `claims_ref`, `claim_ledger_summary` and
`blocked_claim_summary`; v2 refs remain optional sidecars ignored by legacy
consumers.

## Feature Flags

```text
scientist.best_in_class.wave2.phase2_1.claim_ledger_v2
scientist.best_in_class.wave2.phase2_1.require_lifecycle_events
```

Production default remains off until later Wave 2 gates require lifecycle
events for selected high-risk publication paths.

## Validation

```bash
uv run pytest tests/unit/scientist/claims/test_lifecycle.py tests/unit/scientist/claims/test_audit.py tests/unit/scientist/claims/test_diff.py tests/unit/scientist/claims/test_export.py -q
uv run pytest tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_build_decision_packet_node_emits_v3_payload_and_manifest_inputs -q
uv run python tools/ci/check_scientist_best_in_class_phase2_1.py --repo-root . --output-format json --require-passing
```
