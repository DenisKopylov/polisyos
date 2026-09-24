# Governed public record — Stage 1 R3/R4

Read-only source investigation at `034f30c64a79eb2020c04c6f0b0f07c90a74a1ee` on
`codex/governed-public-record`. This note is requirements analysis, **not an admitted schema or
authority appointment**. Source/test/register/ledger files were not edited. Tests were not run.

## Decision

Build the bounded exact-snapshot profile selected in GPR-A03 of the companion decision.
An early proposed stop for an unspecified semantic model was **refuted before commitment**:
`consolidation/int-r7-r8/int-r7-r8-open-questions-and-next-research.md`, findings
**ENG-02, ENG-05 and ENG-06**, explicitly allocate proof/evaluator/receipt construction to
engineering. Its “Engineering non-decisions” includes schema, API and solver choices.
No new active research or institutional appointment is required to build a candidate mechanism.

The profile records exactly the selected admitted owner snapshot and its statuses at publication
time. It does not infer firstness, complete history, current policy authority or performance.
Source resolution and extraction must use the existing Claim owner, rather than infer authority
from a packet's `claims_ref` or `prepared_not_current` projection. Candidate ledger material
cannot enter admitted public content. Resolve the complete raw typed owner ledger as the semantic denominator, and use the
PUBLIC export for eligibility. That export omits raw metadata, comparisons and lifecycle; equality
to the export alone is insufficient. Require all source claims to be PUBLIC-visible; unsupported
arbitrary metadata or material redaction is a refusal, not an invented condensation theorem.

`PV-K03` forbids proof from minting content authority. `PV-K04/05` require exact material
preservation for this profile; `PV-K06/09` require an explicit bounded reconstruction/metadata
model. `PV-K07` controlled-prefix evidence is required only for that stronger claim, which this
profile does not make. `PV-K08` supplies no numerical guarantee. `S0-K06` and the principal's
boundary ruling §9 item 5 require a complete mechanism with institutional signing typed and empty.

## Existing owners and concrete limits

Paths below are relative to `policy-engine/` at the pinned revision.

| Owner | What the code establishes | Why it does not settle the positive PUBLIC contract |
| --- | --- | --- |
| `src/polisyos/runtime/http/services/public_decision_verification_contracts.py:69` | All declared PV-K01 dimensions have type `Literal["not_established"]`; signed report and response carry `promoted_record: Literal[None]` | This is deliberately a report-authentication owner. Filling the slot changes its contract; a signature alone cannot change dimension truth. |
| `src/polisyos/runtime/http/services/public_decision_verification.py:117` | Persists document bytes, signed report, index; readback verifies digest, exact issuer/key/purpose/rule/schema bindings | This proves the issuer authenticated those bytes. No source material or semantic/channel model enters `issue`. |
| `src/polisyos/runtime/http/routes/public_decisions.py:103` | Tenant-bound run selection; client body rejected; persisted packet passed through public export; export refusal stops issuance | Builder receives `artifacts={"decision_packet": packet}` only. This path does not extract a governed semantic denominator or invoke PA3. |
| `src/polisyos/runtime/quality/public_export.py:274` and `:2163` | Canonical redaction, candidate firewall, authority surface refusal, projection/use limits | Result is `projection_only`, `redacted_derived`, `public_audit_only`. Preserve this owner and its consumer prohibitions; do not reclassify its bundle as authority. |
| `src/polisyos/runtime/quality/promotion_sequence.py:1796` | Canonical N9 candidate promotion receipt, including obligations, risk, owner projection and authority derivation | Candidate promotion does not independently prove this PUBLIC projection's semantics, protected channel or history. |
| `src/polisyos/runtime/quality/prompt_tool_ledger.py:667` and `:866` | PA3 recomputes exact material-item fingerprint partitions, categorical declared omissions, denied uses, limitations and evidence-independence basis | Material-set completeness/classification is an input. `summary_reconstruction="proved_conservative"` derives from a permitted item drop; no secret/channel/observation model is evaluated. Do not equate this field with PV-K06 non-reconstruction. |
| `src/polisyos/runtime/quality/design_axes/projection_lowering.py:434` | S9 reference-set checks, denied authority and declared limitations | Tradeoff inversion/approval checks depend on keywords in claim refs; `hidden_blocker_refs=[]`. The rendered-record type has no actual rendered proposition body to compare. It cannot establish unrestricted PV-K04 parity. |
| `src/polisyos/runtime/quality/projection_semantics.py:825`, `:1011` | PDC closeout/omission/contested preservation against caller-supplied expected sets; S9 status/detail inspection | Useful checks, not an independent derivation of total protected-query semantics. A caller-declared expectation is not the quantity P37 requires. |
| `src/polisyos/core/contracts/chronology.py:1` | Integrity of a supplied native prefix | Module explicitly leaves membership, completeness, authority heads, acceptance and custody to native owners. Reusing it does not conjure a controlled release-family owner. |
| `src/polisyos/scientist/governance/continuous/published_signature_custody.py:120` | Local report inventory inspection, report reverification, persisted nonreceipt | `resolve()` rejects nonempty promoted records as `promoted_record_not_admitted`; it cannot be converted by a mere non-null check. |

`GY-GAP3` remains explicitly open in `docs/plans/active/layer3-slices/GY-engine-subordination.md:5198`;
the binding correction is `PV-K07` and ratification §6.2, `RFR-06`. Its required shape is assigned
to the existing epoch/currentness owner, with PA3 as consumer; a generic hash chain is insufficient.
This history evidence matters if the selected proposition includes a controlled-prefix claim.

## Field requirements: existing versus to be selected

The following are field-level requirements and reader rationales. Proposed concepts are not new
chosen Python field names or a ratified DTO. Internal evidence must not automatically be emitted
as public CAS addresses: existing public export redacts tenant-private references, and `PV-K09`
requires proof-address/channel analysis.

| Field or concept | Requirement and reader |
| --- | --- |
| `schema_version` | Existing report field; exact signed schema validation and replay reader. Positive schema identity must be distinct from verification-report-only semantics. |
| `record_id` | Existing opaque server-issued locator; public API/viewer request binding and inventory. Never a browser-authored document token. |
| `decision_id` | Existing report field, currently run ID; issuance index and public verifier compare it. Internal packet/claim linkage must resolve rather than infer from naming. |
| `issuer_id` | Existing authenticated report issuer; report verifier checks exact configured key binding. A governed publication issuer is a distinct purpose-scoped assertion. |
| `signing_key_id` | Existing signed report field, compared to actual signature key. Governs report authentication only. Public key identifiers are part of the PV-K09 channel. |
| `purpose` | Existing literal `public_decision_verification_record`; cannot be borrowed as policy publication mandate. Positive publication purpose requires explicit selection and trusted evidence. |
| `rule_version` | Existing exact report/index/service comparison. Admission/semantic/channel rules also need content-bound versions, chosen by their real owners. |
| `issued_at` | Existing aware report issuance time; cannot stand for mandate interval, publication time, query cutoff or status observation. |
| `public_document_digest` | Existing exact retained document identity; used by signed report, durable index and read verifier. Not a proof of semantics, redaction safety or institutional approval. |
| `publication_class` | Existing literal `verification_report_only`. A positive class must name the actual public proposition, rather than change the existing value's meaning. |
| `promoted_record` | Existing typed-empty slot in signed report/response/route and observation protocol. A future admitted envelope needs owner-produced verification; untrusted non-null input must continue to fail. |
| `signature_ref` | Existing custody-member requirement; exact persisted governed-signature subject needed by watcher and audit, not merely the verifier report signature. |
| `decision_packet_ref` | Existing custody-member requirement; exact packet needed by claim-lifecycle bridge and decision-validity service. |
| `affected_claim_ids` | Existing nonempty custody-member requirement; must be derived/reconciled against the exact packet claim ledger, because lifecycle applies effects to those claims. |
| `published_at` | Existing custody-member field; identifies start of published signature custody, separate from report issuance. |
| `staleness_after_seconds` | Existing custody-member field; watcher computes due time from this interval. The selected custody policy must supply its binding authority; arbitrary caller intervals are not currentness proof. |
| Source semantic identity and revision | Required by PV-K03/PV-K04; source resolver and parity verifier must bind source and projection, not trust source ref syntax. |
| Claim kind, basis, scope, assumptions, material conditions and limitations | Required by PV-K04, with delta obligation set/relative-basis rider under PV-K05. Actual selected typed source/extractor must establish the complete basis. |
| Retained items, typed omission reason/effect, declared/denied uses | Required by PV-K03/PV-K04/PV-K05; semantic verifier and public viewer must preserve negative terminals, dissent, contest and recourse. PA3 provides reusable partition logic once its input completeness is established. |
| Admission evidence and verifier provenance | Required for any positive producer/consumer gate. Bound to exact packet, public bytes, claim/use scope, rules and evidence; cannot be an opaque signed `safe=true` bundle. |
| Institutional signature slot and authority basis | Required but legitimately empty in production. Exact issuer/mandate/purpose/scope/time evidence is an integrate input; verification of that evidence is owned computation. It cannot supply mathematical parity/non-reconstruction facts by assertion. |
| Verification cutoff and authenticated currentness/status evidence | PV-K02/PV-K01; current authority and snapshot selection must resolve from existing validity/epoch owners. Staleness detection is advisory, not a current-authority certificate. |
| History/durability/obtainability evidence | Each PV-K01 dimension needs its own bounded evidence and time. Local file presence/index enumeration cannot claim globally complete public history or future archival durability. |
| Disclosure/channel model and controlled history | Required for the chosen PV-K06/PV-K07/PV-K09 claim, including proof metadata, not a numerical disclosure budget. These semantics are not derived by current export/report owners. |

The existing snapshot adds `population_id`, `population_provenance`, `members`, `captured_at`
and schema identity; its persisted handle adds the exact artifact/hash. A controlled local population
must not silently claim all public signatures or erase revoked historical signatures (`PV-K02`).

Prohibited authority-bearing content includes raw LLM candidate assertions, unresolved claim or
basis references, browser-provided promotion/verifier verdicts, contract-testing or shadow promotion
treated as production, narrowed denied uses, omitted active negative terminals, bare delta claims,
and unsupported blanket `Verified`, current-authority, completeness or non-reconstruction claims.
Candidates may remain inspectable under an explicit candidate band and declared limitation; they
cannot fill admitted PUBLIC authority slots. Numerical disclosure claims remain refused under
`PV-K08`. Credentials, private tenant/CAS identifiers and proof linkage cannot bypass the canonical
disclosure boundary (`PV-K09`).

## R4 deployment seam

The current exact seam is
`src/polisyos/runtime/http/services/public_decision_verification_configuration.py:35`:
`POLISYOS_PUBLIC_VERIFICATION_CONFIG` selects strict JSON with issuer, optional private key and
trusted public-key/issuer/purpose rows; malformed trust fails startup; missing configuration disables
report issuance. It does **not** contain a public-decision mandate or a semantic verifier.

Reusable patterns, not reusable authority purposes:

- `src/polisyos/runtime/http/services/acquisition_admission_bundle.py:91` defines a typed empty
  `AcquisitionAdmissionSigningSlot` and refuses before writes when incomplete. The governed PUBLIC
  slot should preserve that fail-closed distinction without borrowing acquisition authority.
- `src/polisyos/runtime/http/services/human_decision_contracts.py:119` binds trusted producers by
  exact manifest kind/schema/version and signer identity; `HumanDecisionTrustPolicy` freezes the
  verifier epoch. `src/polisyos/runtime/http/deployment_security.py:92` adds exact public keys and
  revocation policy. Use this infrastructure pattern for scoped external evidence; do not reuse its
  human-decision semantics as public-publication authorization.

Once the proposition is selected, the institutional input must be a strict, separately persisted
statement binding the exact publication subject/public digest, affected scope, intended purpose,
issuer and authority basis, validity interval and trust-policy version. Its exact manifest and
signature are checked against deployment-owned trust. This is a **requirement**, not a claim that
such a PUBLIC evidence type already exists. Institutional text or keys cannot decide whether
omissions are safe or a controlled history is complete.

An opaque `Verifier` Protocol would put the absent semantic computation behind an interface
(`P01`/`P02`). Admitting an institution-authored `parity=true` or `safe=true` without recomputation
would put an `institutionally_supplied` predicate inside an authority gate (`P37`), even with a valid
signature (`PV-K03`, `P32`).

## Existing runnable chain and acceptance boundary

Production report path: authenticated `POST /api/v1/runs/{run_id}/public-verification-record`
→ exact persisted packet → canonical public export → report CAS/signature/index/readback
→ anonymous `GET /api/v1/public-decisions/verification` →
`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts` and
`PublicDecisionViewerPage.tsx`. The client requires `promoted_record: null` and literal
`not_established` dimensions; widening server semantics without a strict new client branch breaks
the contract. The page currently displays title/digest and unresolved dimensions, not retained
claim/limitation/negative-terminal content. A positive public reader must carry those semantics.

Production advisory path: `RuntimeContainer.startup` at `container.py:327` supplies the report
population provider to `ControlPlaneService`; embedded `ControlWorker` maintenance at
`services/control/run_lifecycle.py:1404` invokes the watcher. `scan_once` at
`published_signature_custody.py:510` persists a nonreceipt today. With an independently admitted
population, it verifies members, emits a staleness monitor event, calls
`publish_published_signature_custody_event` at `run_lifecycle.py:3579`, and persists claim-lifecycle,
decision-validity and `control.decision_validity.published_signature_custody` outbox effects.
External-worker scheduling is not proved by this embedded-worker call site.

Suggested existing regression replay commands (not executed in this read-only pass):

```sh
cd policy-engine
uv run pytest tests/unit/runtime/http/test_public_decision_verification_routes.py tests/unit/runtime/http/test_public_decision_verification.py tests/unit/runtime/http/test_public_decision_verification_configuration.py -q
uv run pytest tests/unit/scientist/governance/continuous/test_published_signature_custody.py tests/integration/runtime_quality/test_published_signature_custody.py -q
```

The custody integration test supplies a synthetic signature artifact and `synthetic_test`
population. It proves advisory lifecycle/outbox mechanics, not institutional admission or a PUBLIC
positive. Future acceptance must use the actual chosen public producer, persisted reread, all
consumers and an unchanged-negative call-removal probe; no test-only admitted producer.

## Measured denominator and pattern pass

The named operational denominator is the complete input signatures and function bodies of
`PublicDecisionVerificationService.issue/_verify_entry`, `build_public_export_bundle`,
`PublicVerificationRecordPopulationProvider.resolve`, `verify_projection_faithfulness` and
`build_compression_loss_receipt`. Re-read these exact tracked owners at the pinned base
with `git show 034f30c64:policy-engine/<path>`. The complete tracked-source type census
and independent cross-check are in `governed-public-record/census.md`.
The conclusions concern these actual call paths, not a lexical absence of all possible
implementations. Dynamic/external providers remain `unresolved_by_construction`.

Relevant patterns: `P01`/`P02` missing positive producer/bridge; `P03` incomplete positive reader;
`P04`/`P05`/`P09` report, promotion, currentness and advisory status separation; `P07`/`P08` rule/time
binding; `P10`/`P15` candidate semantic adequacy; `P27` owner reuse; `P29`/`P32` behavioral evidence;
`P35`/`P36` denominator/finding precision; `P37`/`P38` declared predicates/proxies. Smallest correct
pattern: select the public proposition, then build its total typed-source admission and single
emission path with per-dimension evidence; leave only institutional signing empty. Do not claim
that a report plus custody helper has completed this capability.
