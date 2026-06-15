# Honest Diagnostics Operator Triage

Related runbooks: [Production Quality Triage](production-quality-triage.md),
[Production Quality Canary](production-quality-canary.md), and
[Runtime API Outage](runtime-api-outage.md).

Related reference: [Runtime quality scorecard](../reference/runtime/quality-scorecard.md),
[Production quality approval](../reference/runtime/production-quality-approval.md),
and `docs/system-design-decisions/honest-diagnostics-substrate.md`.

Owner: `@platform-owners` with `@runtime-owners`,
`@scientist-owners`, `@fabric-owners`, `@foundry-owners`, `@lex-owners`,
`@security-owners`, and compliance reviewers.
Last tested: `2026-05-15` against the Phase 6.5 documentation lifecycle
checks. Runtime commands below are diagnostic anchors for the owning failure
mode, not a full rehearsal.
Evidence path: runtime diagnostic event log, runtime CAS authority refs,
`quality_evidence/quality_scorecard.json`,
`quality_evidence/evidence_provenance_manifest.json`,
`quality_evidence/semantic_binding_ledger.json`,
`quality_evidence/source_truth_conflicts.json`,
`quality_evidence/attestation_records.json`, and the affected control job or
run payload.
Rollback path: stop promotion, preserve the original runtime refs and bundle,
quarantine lower-authority projections, and rerun only the owning runtime
producer or reader after the authority gap is understood.

Use this runbook when a serious `research`, `governed`, or `production` run
cannot close because the honest diagnostics substrate found missing,
contradictory, stale, projected, or downgraded authority evidence.

## Authority Rules

- Runtime diagnostic events and runtime CAS artifacts are the highest evidence
  authority for closeout.
- Scorecards, readiness, approval packets, dashboards, public exports, and
  canary bundles are readers or projections. They cannot mint missing runtime
  truth.
- A missing or invalid authority record must become a typed blocker. Do not
  patch JSON, mark refs optional, or promote a bundle-local file to a runtime
  ref.
- Preserve the first failing bundle, event log rows, CAS manifests, scorecard,
  and control job payload before retries.
- If tenant, cell, public-export, secret, or hidden-answer boundaries are in
  doubt, treat the incident as security-sensitive until proven otherwise.

## First 15 Minutes

1. Stop promotion and freeze publication for the affected run or lane.
2. Capture identifiers: `RUN_ID`, `JOB_ID`, tenant, cell, execution profile,
   bundle path, scorecard ref, readiness output, and dashboard URL.
3. Extract scorecard blockers:

   ```bash
   uv run python - "$SCORECARD_JSON" <<'PY'
   import json
   import sys
   from pathlib import Path

   scorecard = json.loads(Path(sys.argv[1]).read_text())
   for item in scorecard.get("blocking_quality_failures") or []:
       print(
           item.get("code"),
           "| gate=", item.get("gate"),
           "| layer=", item.get("layer"),
           "| phase=", item.get("phase"),
           "| ref=", item.get("evidence_ref"),
           "| next=", item.get("next_action"),
       )
   PY
   ```

4. Compare runtime refs, diagnostic events, and source-truth conflicts:

   ```bash
   uv run python - "$BUNDLE" <<'PY'
   import json
   import sys
   from pathlib import Path

   root = Path(sys.argv[1]) / "quality_evidence"
   for name in (
       "quality_scorecard.json",
       "evidence_provenance_manifest.json",
       "source_truth_conflicts.json",
       "semantic_binding_ledger.json",
       "attestation_records.json",
   ):
       path = root / name
       print(name, "present" if path.exists() else "missing")
       if path.exists() and name == "quality_scorecard.json":
           payload = json.loads(path.read_text())
           print(json.dumps(payload.get("evidence_refs", {}), indent=2, sort_keys=True))
   PY
   ```

5. Route by failure code and owner. If the failure has no owner or next action,
   route to `@runtime-owners` first and record that the diagnostic itself was
   under-specified.

## Failure Routing

| Failure | Primary signals | First checks | Mitigation and owner | Verification |
| --- | --- | --- | --- | --- |
| Missing runtime ref | `hds_runtime_ref_missing`, `hds_runtime_refs_missing`, empty required `*_ref`, or a bundle path where a CAS ref is required | Check `quality_scorecard.evidence_refs`, runtime progress refs, CAS manifests, and HDS-MCG row `required_ref_keys` | Keep the scorecard blocked. Route to the producer owner for the missing ref. Reemit the authority artifact or emit a runtime blocker. | `uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py tests/unit/runtime/quality/test_authority_envelope_contract.py -q` |
| Missing diagnostic event | `serious_diagnostic_event_missing`, `authority_orphan_cas`, or an envelope with CAS but no durable event | Check the runtime diagnostic event log for `run_id`, `job_id`, `payload_ref`, `artifact_refs`, `event_type`, and `sampling_decision` | Treat as a runtime diagnostics failure. Do not synthesize an event after the fact unless an idempotent replay can prove the same payload and dedupe key. Owner: `@runtime-owners`. | `uv run pytest tests/unit/runtime/quality/test_diagnostic_event_contract.py tests/unit/runtime/quality/test_authority_reconciliation.py -q` |
| Ref identity mismatch | `hds_ref_identity_mismatch`, `authority_runtime_ref_mismatch`, `diagnostic_event_ref_mismatch`, or different refs across progress, scorecard, bundle, and report payload | Compare CAS ref, event `payload_ref`, event `artifact_refs`, envelope `artifact_ref`, and scorecard evidence ref | Keep runtime CAS as authority. Emit or inspect a losing-authority record for the lower surface. Owner follows the source-truth field family. | `uv run pytest tests/unit/runtime/quality/test_authority.py tests/unit/runtime/quality/test_source_truth_lattice.py -q` |
| Event/CAS reconciliation failure | `authority_cas_missing`, `authority_orphan_cas`, `authority_payload_mismatch`, `authority_ref_not_cas`, `authority_event_collision`, `authority_replay_drift_unexplained`, or `authority_tenant_conflict` | Run event-to-CAS and CAS-to-event reconciliation. Check payload hash, manifest authority link, duplicate event id, tenant, cell, run, and job | Quarantine the affected authority record and rerun the owning producer only after idempotency is understood. Owner: `@runtime-owners` plus the producer owner. | `uv run pytest tests/unit/runtime/quality/test_authority_reconciliation.py tests/unit/runtime/quality/test_crash_retry_partial_state.py -q` |
| Schema incompatibility | `hds_schema_incompatible`, `unknown_schema_blocked`, `incompatible_blocked`, `stale_schema_blocked`, or `legacy_quarantined` | Check `schema_name`, `schema_version`, `reader_contract`, `reader_contract_version`, and `architecture/production_quality/schema_compatibility.toml` | Migrate with a declared compatibility decision or keep the evidence quarantined. Do not let legacy-readable evidence satisfy serious closeout. Owner: `@runtime-owners` with `@platform-owners`. | `uv run pytest tests/unit/runtime/quality/test_schema_compat.py tests/repo_quality/tools/test_runtime_quality_schema_compatibility.py -q` |
| Source-of-truth conflict | `hds_source_truth_conflict` or field-family-specific conflict codes such as `hds_runtime_ref_authority_conflict` | Compare authoritative producer and allowed projection/package surfaces in `source_truth_lattice.toml` | Preserve the losing surface and record lost fields. The authoritative producer reruns or the lower surface is corrected. | `uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q` |
| Adapter semantic loss | `hds_adapter_semantic_loss` or a source-truth adapter report with missing required semantic fields | Check adapter path, source surface, target surface, field family, and lost fields | Block the adapter output from closeout. Owner is the adapter or projection surface owner. Preserve the pre-adapter authority payload. | `uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q` |
| Mode leakage | `mode_profile_mismatch`, `mode_simulated_provider_not_allowed`, `mode_fixture_identity_not_allowed`, `mode_non_production_data`, `mode_evidence_overlay_not_allowed`, or `mode_requested_effective_mismatch` | Inspect effective mode ledger: requested/effective profile, provider mode, fixture identity, simulation mode, data mode, warning policy, quarantine, and overlay mode | Keep the run blocked for serious closeout. Rerun with a serious-compatible effective mode or record an explicit non-production scope. Owner: `@runtime-owners` and `@scientist-owners` for provider mode. | `uv run pytest tests/unit/runtime/quality/test_effective_mode.py -q` |
| Unallowed fallback | `hds_unallowed_fallback`, `degradation_fallback_not_allowed`, or fallback-derived evidence without a degradation ledger | Inspect fallback/degradation ledger: component, phase, trigger, allowed profiles, affected claims, produced artifacts, and override policy | Block authority-bearing evidence from fallback output unless the registry allows it and a signed non-production-lowering exception exists. Owner: `@runtime-owners`. | `uv run pytest tests/unit/runtime/quality/test_degradation.py -q` |
| Phase-barrier violation | `hds_phase_barrier_not_closed`, `phase_barrier_missing`, `phase_barrier_skipped`, `phase_barrier_blocker_missing`, `phase_barrier_blocked`, or `phase_barrier_not_passed` | Inspect phase-barrier ledger for policy intent, legal, data, method, grounding, privacy, security, conflict, tenant, provenance, and scorecard barriers | Stop final artifact, scorecard, approval, and public export publication. Rerun missing phases or keep typed blockers. Owner: `@runtime-owners` plus affected subsystem owner. | `uv run pytest tests/unit/runtime/quality/test_run_state.py -q` |
| Projection used as authority | `hds_projection_used_as_authority`, `projection_quality_status_not_authority`, `scorecard_projection_not_authority`, or `hds_bundle_ref_used_as_runtime_ref` | Check `authority_role`, `provenance_kind`, projection source, dashboard/readiness status, and bundle-local paths | Demote the surface to projection-only and require the corresponding runtime CAS/event authority. Owner: projection owner and `@runtime-owners`. | `uv run pytest tests/unit/runtime/quality/test_authority.py tests/unit/runtime/quality/test_authority_spoofing.py -q` |
| Semantic binding missing | `hds_semantic_binding_missing`, `semantic_binding_ref_mismatch`, `semantic_binding_ledger_invalid`, `semantic_no_relevant_evidence_blocker`, or `semantic_retrieval_failure_blocker` | Inspect semantic binding ledger for policy intent, canonical concepts, legal norms, data sources, method plan, final claims, claim refs, and authority envelope refs | Keep final claims blocked. Regenerate or repair the ledger through Lex, Fabric, Foundry, Scientist, and final compiler owners. | `uv run pytest tests/unit/runtime/quality/test_semantic_binding.py tests/unit/scientist/validation/test_claim_support.py -q` |
| Cross-tenant evidence mismatch | `authority_tenant_conflict`, tenant/cell mismatch in CAS manifest, event, envelope, scorecard, or public export | Compare tenant and cell across run payload, same-input closure, CAS manifest, diagnostic event, authority envelope, and export metadata | Treat as security-sensitive. Freeze public export and approval, preserve evidence, and route to `@runtime-owners` plus security. | `uv run pytest tests/unit/runtime/quality/test_multi_tenant_shared_cas.py tests/unit/runtime/quality/test_authority_reconciliation.py -q` |
| Stale evidence | `stale_diagnostic_event`, `diagnostic_slo_evidence_stale`, `stale_schema_blocked`, stale provider/default evidence, or stale governance lifecycle report | Check event time, observed time, freshness TTL, schema registry version, provider/model ledger age, data/legal snapshot age, and continuous governance lifecycle refs | Rerun the owning producer or emit stale/reissue/withdraw lifecycle evidence. Do not extend TTL silently. | `uv run pytest tests/unit/runtime/quality/test_diagnostic_event_contract.py tests/unit/runtime/quality/test_diagnostic_slos.py tests/unit/scientist/governance/continuous -q` |
| Unattested producer step | `attestation_missing`, `*_attestation_missing`, `attestation_evidence_ref_missing`, `attestation_signature_ref_missing`, `attestation_synthetic_material_ref`, or producer identity mismatch | Check `trust_boundary_id`, materials/products, producer identity, environment identity, isolation, service generation, consumer verification, tamper check, signature, and evidence ref | Keep evidence diagnostic-readable only. Reemit a verified service-generated attestation for the trust boundary. Owner follows `trust_boundaries.toml`. | `uv run pytest tests/unit/runtime/quality/test_attestation.py tests/unit/runtime/quality/test_scorecard.py::test_production_scorecard_blocks_required_trust_boundary_without_attestation -q` |
| Partial-state contradiction | Phase-specific blockers such as `lex_partial_state_blocker`, `fabric_partial_state_blocker`, `foundry_partial_state_blocker`, a completed job with missing progress refs, or pass scorecard with blocking evidence | Compare control job state, progress details, CAS writes, event log, outbox/retry state, scorecard gates, and readiness output | Freeze closeout and preserve both states. Reconcile idempotent retry before cleanup. Owner: `@runtime-owners` plus the phase owner. | `uv run pytest tests/unit/runtime/quality/test_crash_retry_partial_state.py tests/unit/runtime/quality/test_authority_reconciliation.py -q` |

## Escalation Map

| Evidence family | First owner | Supporting owners |
| --- | --- | --- |
| Runtime refs, CAS, events, idempotency, phase barriers | `@runtime-owners` | `@platform-owners` |
| Scorecard, readiness, approval, proof harness | `@platform-owners` | `@runtime-owners` |
| Lex norms, legal conflict, jurisdiction, legal time context | `@lex-owners` | compliance reviewers |
| Fabric source selection, source quality, data freshness | `@fabric-owners` | `@runtime-owners` |
| Foundry method validity, causal/statistical assumptions | `@foundry-owners` | `@scientist-owners` |
| Scientist claims, semantic binding, grounding, citations | `@scientist-owners` | `@lex-owners`, `@fabric-owners`, `@foundry-owners` |
| Mode, fallback, degradation, provider defaults | `@runtime-owners` | `@scientist-owners`, ops |
| Attestation, tenant isolation, public export, security evidence | `@security-owners` | `@platform-owners`, compliance reviewers |
| Dashboard or API projection | `@frontend-owners` | `@runtime-owners` |

## Closeout Record

Every honest-diagnostics incident record must include:

- UTC detection, mitigation, rerun, and restoration timestamps;
- `RUN_ID`, `JOB_ID`, tenant, cell, execution profile, and bundle path;
- scorecard ref, readiness output, and approval packet ref when present;
- every blocking failure code, gate, layer, phase, evidence ref, and next
  action;
- runtime CAS refs, diagnostic event ids, payload hashes, and any reconciliation
  report;
- source-truth conflict or adapter semantic-loss record when one exists;
- mode ledger, degradation ledger, phase-barrier ledger, semantic binding
  ledger, and attestation refs touched by the incident;
- owner and due date for remediation;
- verification commands rerun after the fix;
- explicit note when the incident remains blocked, quarantined, or outside
  production closeout scope.
