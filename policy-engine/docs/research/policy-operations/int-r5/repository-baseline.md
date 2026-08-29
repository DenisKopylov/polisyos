# INT-R5 Repository Baseline — Shipped Authority Model At `dc7bdf79a`

## 1. Purpose and measurement posture

This file records what the pinned repository can and cannot represent before the external surveys
are used to design the target model. It supports section 2 of the main deliverable and is not an
implementation contract.

The measurement holder is the INT-R5 research pass. Exact files were read at
`dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` through the authenticated GitHub connector. The
canonical executable denominator is **10 files: nine Python owners plus one Rego mirror**. Historical
counts from closure documents are labelled historical receipts. Search-index results orient the
inspection but do not settle a zero.

## 2. Governing repository findings

| ID | Classification | Finding | Consequence |
| --- | --- | --- | --- |
| `INT-R5-RF-01` | repository/process | The INT-R5 ordering constraint was violated: GY-PA2, DS9 and DS20 closed before their named research input. | Audit the shipped model; do not retrofit it into the target. |
| `INT-R5-RF-02` | repository/model | GY-PA2's five predicates are internally coherent and fail closed for their declared operational facts. | No architect stop; consume them as a bounded subset. |
| `INT-R5-RF-03` | repository/model | DS9 re-resolves signed inputs, separates human actor from custody signer, checks currentness and guards persistence. | Natural pre-effect certificate consumer, not a complete authority producer. |
| `INT-R5-RF-04` | repository/model | DS20 binds principal, permission, operation, resource and step-up and does not claim institutional competence. | Keep DS20 narrow; a future certificate feeds it rather than collapsing into it. |
| `INT-R5-RF-05` | repository/model | Acquisition composes DS20 acquisition step-up with the PA2/DS9 gateway and currentness checks. | Closest landing seam, still not a certificate. |
| `INT-R5-RF-06` | repository/absence | No canonical owner field represents jurisdictional legal power or amount/valuation scope. | Full authority proof cannot be issued. |
| `INT-R5-RF-07` | repository/absence | No canonical owner field represents collegial forum, roster, quorum, voting or co-signature. | A board-role token cannot prove a body acted. |
| `INT-R5-RF-08` | repository/absence | DS9 has narrow reviewer separation but no general transaction-level SoD or COI/recusal model. | Self-approval and recusal cannot be certified. |
| `INT-R5-RF-09` | repository/absence | No parent-grant/subdelegation, acting/succession, emergency or recognition chain exists. | Current role and envelope currentness are insufficient provenance. |
| `INT-R5-RF-10` | repository/absence | Action/source-kind vocabularies do not distinguish legal effect among consultation, recommendation, approval and decision. | Authority and responsibility can be overstated downstream. |
| `INT-R5-RF-11` | documentation drift | DS20 closure prose reports 33 permissions; pinned Python and Rego owners each contain 34 after DS9 added `runs.human_decisions.create`. | Historical receipt remains useful; 33 is not current vocabulary size. |
| `INT-R5-RF-12` | capability classification | The full graph/certificate chain has no typed artifact, appointed producer, bridge, complete consumer or semantic e2e test. | `absent/unallocated`; research prose is not `contract_only`. |

## 3. Canonical owner coordinates

### 3.1 Delegation and GY-PA2

`policy-engine/src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`

- `DecisionRole`
- `HumanDecisionRecordPredicate`
- `DelegatedActionEnvelope`
- `DelegationContract`
- `HumanDecisionRequest`
- `HumanDecisionRecord`

`policy-engine/src/polisyos/runtime/quality/agent_action_authority.py`

- `AgentActionAuthorityDecision`
- `evaluate_agent_action_authority`
- `_live_accountability_check`
- `resolve_gateway_adapter`

Represented and enforced:

- exact operation, invocation, intent and resource binding;
- exact permission proof;
- subject, tenant and authorized runtime roles;
- time interval and `active|revoked` envelope state;
- typed refusal for ambiguity, mismatch, not-yet-valid, expiry and revocation.

Not represented:

- source law and jurisdiction profile;
- office appointment provenance;
- amount, currency, aggregation and valuation;
- parent grant and right to subdelegate;
- collegial validity;
- COI and recusal;
- cross-agency recognition;
- legal effect.

### 3.2 DS9 human decisions

`policy-engine/src/polisyos/runtime/http/services/human_decision_contracts.py`

- `HumanDecisionPrincipalBinding`
- `ReviewerSeparationCredential`
- `HumanDecisionPresentationContract`
- `ProductionHumanDecisionBasis`
- `HumanDecisionPA2GatewayAdapterInput`

`policy-engine/src/polisyos/runtime/http/services/human_decisions.py`

- `HumanDecisionService`
- `_ResolvedPA2OperationalAuthority`
- source resolution and currentness methods
- guarded record reservation, write and readback

Represented and enforced:

- issuer-qualified actor identity and key;
- current role and permission binding;
- exact request, evidence-exposure and presentation binding;
- narrow reviewer independence against named reviewed actors;
- producer trust, CAS identity, append-only event evidence and idempotency;
- currentness re-resolution before protected consumption.

Not represented:

- proposer, material contributor, executor and reviewer as a complete transaction lineage;
- forum, roster, quorum, vote and co-signature;
- conflict declarations, recusal, waiver or management measures;
- amount, jurisdiction, appointment, succession or subdelegation;
- external recognition and act-effect classification.

### 3.3 DS20 action-permission floor

`policy-engine/src/polisyos/runtime/http/permissions.py`

- `RuntimePermission`: 34 exact values at the pin.

`policy-engine/src/polisyos/runtime/http/authorization.py`

- `ActionPermissionDependency`
- `BoundActionPermissionVerification`
- `RouteAuthorizationRequirement`

`policy-engine/src/polisyos/runtime/http/resource_binding.py`

- `BindingAuthority`
- `BoundAuthorizationResource`
- exact request/resource digest binding

`policy-engine/src/polisyos/runtime/http/step_up.py`

- `StepUpClass`: promotion, production approval, publication, revocation,
  acquisition approval and human decision
- signed request-bound assertion verification
- single-use replay store

`policy-engine/ops/policy/policies/action_permission.rego`

- 34-value `permission_vocabulary`, equal to Python
- five `binding_authority_vocabulary` values
- two `authorization_source_vocabulary` values
- exact permission/resource/authority combinations

DS20 answers whether a verified runtime principal may perform an exact operation over an exact
resource under current permission and step-up policy. It does not answer whether that principal or
body possesses the institutional power to decide the underlying matter.

### 3.4 Acquisition approval

`policy-engine/src/polisyos/runtime/http/routes/control.py::ingest_data`

- permission: `RuntimePermission.EVIDENCE_ACQUIRE`
- resource: request-bound `runtime.evidence.acquisition`
- step-up: `StepUpClass.ACQUISITION_APPROVAL`

The route proves that acquisition approval is a first-class high-stakes runtime operation. Its
institutional authority still arrives only through the bounded PA2/DS9 arm; no acquisition-specific
authority graph or certificate exists.

## 4. Attribute census over the strict owner closure

| Attribute | Standing | Positive coordinate | Missing semantic |
| --- | --- | --- | --- |
| Temporal and subject delegation | partial | `DelegatedActionEnvelope`, GY-PA2 | source law, jurisdiction, amount, reserved matters |
| Quorum and co-signature | not representable | none beyond a `governance_board` role label | forum, roster, timeline, threshold, vote branches, countersignature |
| Separation of duties | partial | `ReviewerSeparationCredential` | full transaction lineage and controlling subject |
| Recusal and COI | not representable | none | disclosure, detection, recusal, waiver, management, detectability boundary |
| Acting and succession | not representable | none | office, vacancy, acting basis, succession rule and qualifications |
| Subdelegation | not representable | none | parent grant, delegation bit/depth, creation-time power and attenuation |
| Expiry and emergency | partial | envelope time and status | emergency source, trigger, scope and expiry profile |
| Mid-operation revocation | partial | pre-consumption currentness re-resolution | checkpoint/cancel/irreversible-effect and consequence semantics |
| Cross-agency acceptance | not representable | producer authentication only | legal gateway, accepted assertion type, negative perimeter and residual duties |
| Act-type distinction | not representable | workflow verbs only | legal effect, condition precedent, departure freedom and operative actor |

## 5. Absence-search record

The orientation searches were run against the runtime authority surface for:

- `quorum`
- `recusal`
- `conflict_of_interest`
- `subdelegation`
- `succession`
- `acting_appointment`
- `cross_agency`
- `co_signature`
- `amount_limit`
- `forum`

Those searches returned no executable owner matches in the inspected runtime authority surface.
Under P35, the zero claim is not based on the index. It is based on the explicit 10-file canonical
owner closure above: each strict contract, predicate, resource-binding projection, permission owner,
step-up owner, acquisition route and Rego mirror was read, and none carries those semantics.

## 6. Reusable tests and fixtures

The later implementation can reuse:

- GY-PA2 agent-action authority negatives for identity, permission, envelope and currentness;
- DS9 human-decision service tests for strict source unions, re-resolution, stale evidence,
  guarded persistence, idempotency and actor/custodian separation;
- DS20 structural route coverage, Python/Rego parity and step-up replay tests;
- acquisition route tests for exact permission/resource/step-up binding;
- PAO-R4 as an independent downstream boundary test.

None of those tests proves quorum, recusal, amount authority, succession, subdelegation,
recognition or legal effect today.

## 7. Research blockers versus engineering blockers

Research blockers retained:

- jurisdiction-specific consequences of defects cannot be normalized to one universal validity
  result;
- disputed forum, recusal and evaluative emergency predicates require a competent adjudicator, and
  none is appointed;
- hidden personal conflicts cannot be disproved from system records;
- snapshot versus lease versus revalidation is partly a legal-policy choice, not a technical fact.

Engineering blockers visible after this result:

- no canonical graph and certificate contract;
- no adapters for appointments, meeting events, conflict records, recognition or legal-effect rules;
- no graph reducer or certificate producer;
- no persisted dependency index and revocation checkpoint bridge;
- no DS9 certificate-consumer arm;
- no Atlas/DS14 projection;
- no adversarial semantic e2e suite.

## 8. Placement conclusion

The target is not a new permission system. The reuse-first placement is an extension of the current
mandate/delegation authority owner, with DS9 as pre-effect resolver and guarded consumer and DS20 as
the operation/resource enforcement floor. External institutional facts enter through typed
INTEGRATE adapters. Atlas projects; it does not decide. `PAO-R4` remains separate.

No canonical owner is appointed by this research, so the full capability remains
`absent/unallocated`.
