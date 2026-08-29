# INT-R5 Repository Baseline — Bounded Shipped-Model Inspection At `dc7bdf79a`

## 1. Purpose, pin and measurement posture

This file records what the pinned repository inspection actually established before the external
surveys were used to derive the target authority model. It is evidence for the research package, not
an implementation contract and not a repository-wide census.

```yaml
repository: DenisKopylov/polisyos
pin: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
measurement_holder: INT-R5 stage-1 research pass, corrected by stage-3 amendment
inspection_channel: authenticated GitHub reads
selected_slice_id: int-r5-authority-slice-v1
selected_slice_size: 10 files
selected_slice_file_types:
  python: 9
  rego: 1
complete_executable_closure_claimed: false
complete_repository_absence_claimed: false
```

The original package called these ten files a “canonical executable owner closure.” That label is
withdrawn. They are a **selected authority slice** chosen to inspect the named GY-PA2, DS9, DS20 and
acquisition coordinates. Direct imports and call paths reach owners outside the slice. Therefore:

```text
absence in the selected ten-file slice: may be established by reading all ten files
absence in the complete executable/authority closure: not established by this pass
```

GitHub code-search results remain orientation only. They settle neither a zero nor a positive.

## 2. Corrected dependency and ordering ledger

The task row states that INT-R5 must land before GY-PA2 or Atlas DS9/DS14 consumers close, and
separately states that it feeds DS20 vocabulary and acquisition approvals. These are different
relationships and are not summed as one count.

```yaml
closure_order_violations:
  - GY-PA2
  - DS9
unclosed_named_consumer:
  - DS14
missed_feed_dependencies:
  - DS20 action-permission vocabulary
missing_integrations:
  - acquisition -> PA2/DS9 institutional-authority bridge
```

Consequently, there were **two closure-order violations**, one unclosed named consumer, one missed
vocabulary feed, and one missing integration. The prior statement “three consumers closed” is
withdrawn.

## 3. Selected authority slice

The ten inspected files are:

1. `policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`
2. `policy-engine/src/polisyos/runtime/quality/agent_action_authority.py`
3. `policy-engine/src/polisyos/runtime/http/services/human_decision_contracts.py`
4. `policy-engine/src/polisyos/runtime/http/services/human_decisions.py`
5. `policy-engine/src/polisyos/runtime/http/permissions.py`
6. `policy-engine/src/polisyos/runtime/http/authorization.py`
7. `policy-engine/src/polisyos/runtime/http/resource_binding.py`
8. `policy-engine/src/polisyos/runtime/http/step_up.py`
9. `policy-engine/src/polisyos/runtime/http/routes/control.py`
10. `policy-engine/ops/policy/policies/action_permission.rego`

The slice deliberately includes the named strict contracts, policy mirror and acquisition route. It
does **not** include every transitive producer, route, store, event writer, artifact writer or effect
service. Known positive controls outside the slice include:

- `policy-engine/src/polisyos/runtime/quality/approval.py`;
- `policy-engine/src/polisyos/runtime/http/routes/human_decisions.py`;
- `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`;
- security, identity, reconciliation, event, CAS and idempotency owners reached by imports/calls.

Those positive controls are why the ten-file set cannot be called complete.

## 4. Component verdicts

### 4.1 GY-PA2 — sound inside its declared predicate set, incomplete for INT-R5

Coordinates:

- `runtime/quality/design_axes/mandate_bounded_delegation.py`
- `runtime/quality/agent_action_authority.py`

The inspected path enforces verified identity, explicit permission, mandate-bounded delegation,
operation/envelope match and live accountability. It binds operation, invocation, intent, subject,
tenant, resource, time interval and `active|revoked` status and refuses ambiguity, mismatch,
not-yet-valid, expiry and revocation.

It does not establish source-law competence, office provenance, amount/valuation, parent grant,
succession, collegial validity, conflict posture, recognition or legal effect. Verdict:

```yaml
component: GY-PA2
verdict: sound_within_declared_predicates_but_incomplete
```

### 4.2 DS9 — sound on run-bound human-decision routes, incomplete for INT-R5

Coordinates:

- `runtime/http/services/human_decision_contracts.py`
- `runtime/http/services/human_decisions.py`
- positive control outside the selected slice: `runtime/http/routes/human_decisions.py`

DS9 separates the human actor from the PolicyOS custody signer, uses a strict PA2/production source
union, re-resolves raw source evidence, checks currentness and protects persistence with reservation,
idempotency, CAS/event evidence and guarded readback. Its `ReviewerSeparationCredential` is a narrow
separation predicate against named reviewed actors.

It does not establish complete transaction lineage, forum, quorum, recusal, amount, succession,
recognition or act effect. Verdict:

```yaml
component: DS9
verdict: sound_on_declared_run_bound_path_but_incomplete
```

### 4.3 DS20 — sound within runtime authorization boundary

Coordinates:

- `runtime/http/permissions.py`
- `runtime/http/authorization.py`
- `runtime/http/resource_binding.py`
- `runtime/http/step_up.py`
- `ops/policy/policies/action_permission.rego`

DS20 binds a verified runtime principal to one exact permission, operation, resource and signed,
request-bound step-up assertion with replay protection. It answers **who may perform which runtime
operation over which resource now**. It does not claim institutional competence.

At the pin, Python and Rego each contain **34** equal permission values. The historical DS20 closure
text reporting 33 predates `runs.human_decisions.create`; that is documentation drift, not parity
failure.

```yaml
component: DS20
verdict: sound_within_runtime_authorization_boundary
permission_parity:
  python: 34
  rego: 34
```

### 4.4 Acquisition — DS20-only protected route; institutional bridge missing

Actual path:

```text
POST /api/v1/control/data/ingest
  -> _INGEST_DATA_AUTHZ
     RuntimePermission.EVIDENCE_ACQUIRE
     request-bound runtime.evidence.acquisition resource
  -> _INGEST_DATA_STEP_UP
     StepUpClass.ACQUISITION_APPROVAL
  -> ControlPlaneService.run_data_ingestion
  -> Fabric/connector ingestion
```

The route and `run_data_ingestion` path contain no PA2 resolver, no `HumanDecisionService` call, no
human-decision record, no reviewer-separation receipt and no guarded DS9 authority/currentness write.
The DS9 PA2 arm exists on separate run-bound human-decision routes; architectural adjacency does not
create a production call edge.

```yaml
component: acquisition
DS20_operation_floor: implemented
PA2_producer_for_own_contract: implemented
DS9_PA2_currentness_custody_seam: implemented_elsewhere
acquisition_to_PA2_DS9_bridge: missing
acquisition_institutional_authority_consumer: missing
verdict: prior_composition_claim_wrong_and_withdrawn
```

## 5. Ten-attribute observation table

Vocabulary:

- `observed_fragment` — a narrower enforced predicate was read in the selected slice;
- `not_observed_in_selected_slice` — no field, producer and consumer for the full semantic was found
  in all ten files; this is **not** a repository-wide zero;
- `full_INT_R5_representation` — requires the complete institutional proposition and a real consumer.

| Required attribute | Selected-slice observation | Positive coordinate | Unsettled or missing semantic |
|---|---|---|---|
| temporal and subject-matter delegation | `observed_fragment` | `DelegatedActionEnvelope`; PA2 currentness | source law, jurisdiction, amount, reserved matters, legal-purpose scope |
| quorum and co-signature | `not_observed_in_selected_slice` | role labels only | competent body/forum, roster, event timeline, threshold, vote branches, signature purpose |
| separation of duties | `observed_fragment` | DS9 `ReviewerSeparationCredential` | proposer/contributor/executor/reviewer lineage and controlling-subject closure |
| recusal and conflict of interest | `not_observed_in_selected_slice` | none in slice | disclosure, detected conflict, recusal, waiver/management and bounded claim producer |
| acting appointments and succession | `not_observed_in_selected_slice` | principal/role only | office, vacancy, acting basis, succession rule, qualifications and predecessor path |
| subdelegation limits | `not_observed_in_selected_slice` | none in slice | parent grant, permission/depth, delegee class, attenuation and creation-time power |
| expiry and emergency authority | `observed_fragment` | envelope validity/status | emergency source, trigger, necessity/urgency, exceptional scope and expiry profile |
| revocation mid-operation | `observed_fragment` | DS9 pre-use source currentness | checkpoint/cancel/irreversible-effect and post-effect consequence; absent on acquisition route |
| cross-agency acceptance | `not_observed_in_selected_slice` | source authentication fragments | legal gateway, accepted assertion, negative perimeter, refusal grounds, retained duties |
| consultation/recommendation/approval/binding decision | `not_observed_in_selected_slice` | workflow/action labels | legal effect, condition precedent, freedom to depart, operative act, ultimate maker |

Summary of the selected slice:

```yaml
observed_fragment: 4
not_observed_in_selected_slice: 6
full_INT_R5_representation: 0
repository_wide_zero_claims_from_this_table: 0
```

The word `partial` in the main report maps to `observed_fragment` here. It is not a midpoint guess:
each row names the implemented fragment and the missing proposition.

## 6. Capability standing

The full graph/certificate capability remains:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

This standing is not inferred from the six selected-slice zeroes. It follows from the absence of an
admitted `DecisionAuthorityGraph`/`DelegationValidityCertificate` contract in production, no
allocated complete owner, no institutional producer chain, no acquisition or other protected effect
that consumes the certificate, and no semantic end-to-end test through a real effect.

Existing PA2, DS9 and DS20 capabilities remain real and narrower. Markdown does not promote the full
capability to `contract_only`.

## 7. Reuse-first placement after correction

The smallest plausible future chain is:

```text
institutional source adapters
  -> DecisionAuthorityGraph reducer
  -> DelegationValidityCertificate or typed negative
  -> DS9-like source re-resolution/currentness/guarded custody
  -> conditional PAO-R4 receipt for individual-case or pointwise-recoverable use
  -> DS20 exact operation/resource/step-up floor
  -> protected effect
```

For acquisition, the missing production edge is named:

```text
acquisition_authority_bridge:
  consumes: certificate/refusal + currentness receipt
  binds: exact ingest decision and effect commitment
  invokes: PAO-R4 only when the target crosses its boundary
  precedes: ControlPlaneService.run_data_ingestion
  current_standing: missing
```

DS14 remains a future projection/consumer candidate, never an authority producer. External
appointments, meeting facts, conflict adjudication, recognition and legal-effect rules remain typed
INTEGRATE dependencies. No owner or institutional holder is appointed by this research.

## 8. Measurement limitations and positive controls

What this baseline establishes:

- exact narrow behavior of the inspected PA2, DS9 and DS20 coordinates;
- exact DS20-only acquisition route topology;
- 34/34 current Python/Rego permission parity;
- four observed fragments and six non-observations in the named ten-file slice;
- absence of the complete admitted INT-R5 capability chain.

What it does not establish:

- a complete import/call/route closure of the repository;
- a repository-wide zero for any institutional semantic;
- global soundness of PA2, DS9 or DS20 beyond the inspected contracts;
- legal sufficiency in any jurisdiction;
- that architectural reuse has already been wired.

Positive controls proving the selected slice is not a complete closure are the real human-decision
route, production-approval resolver, acquisition effect service and transitive security/event/store
owners named in §3. A future repository-wide zero requires a reproducible AST/import plus route/call
closure with path and file-type denominators and positive controls; this amendment deliberately does
not pretend to have executed that larger census.
