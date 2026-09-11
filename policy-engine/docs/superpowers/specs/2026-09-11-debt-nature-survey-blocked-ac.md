# Debt nature survey — blocked A/C workstream

Base: `fc823071a7b6f2c9a573172aec3499ad6d138c0f`. This is an assessment of claims, not a
standing, closure, allocation, appointment or repair decision. All 16 assigned rows are accounted
for below; unresolved questions remain explicit.

## Measurement contract and receipts

Membership is the root's reconciled **16 blocked rows: A15 + C1**, from
`docs/superpowers/journals/debt-survey/denominator/reconciliation.json`. The register supplies
identities and hypotheses only. It is never evidence about runtime behavior.

Source AST denominator: **2,653 `src/**/*.py` files**, independently reconciled against the
filesystem, with `ast.walk` versus `NodeVisitor` identity equality including async definitions,
and no parse ambiguities. The full shared universe is 5,686 Python files under
`src/`, `tests/`, `tools/`, `architecture/`; package distributions accompany every source query.
TypeScript denominator: **1,224 `.ts/.tsx` files under `apps/**` and `packages/**`**, including tests
and declarations: dashboard 1,156; atlas-ui 57; cli 7; runtime-api-client 4. The Git/filesystem
identity sets and the two AST traversals agree, with no parse failures. This does not establish
arbitrary dynamic reachability. Clerk's narrower denominator is **32 `.ts/.tsx` files**, plus its
non-TypeScript OWNER file outside that count.

Demand search walks **683 `.md/.json/.yaml/.yml` files** under all active plans, reference,
research and system-design-decisions, excluding DEBT-REGISTER and LEDGER. This includes
`withheld-propositions-register.md`, CORR withheld propositions and research finding registers.
Literal matches locate material for scope reading; they prove neither absence of an alias nor an
owner appointment. Source/set facts use scripts rather than inherited counts.

All commands run from `policy-engine/`. Every evidence source below is its tracked path at
`fc823071a`; `inspect_slots.py` reads those bytes through `git show`, and the shared AST scanner
checks current source equality with that base. Exact replay commands, actual exit codes, complete
output paths and SHA-256 values are in
`docs/superpowers/journals/debt-survey/blocked-ac/receipts.json`. Raw output remains ignored.
The command keys below each identify one exact replayable command in that index:

| Key | Exact replay command | Receipt label |
| --- | --- | --- |
| PUBLIC | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py public` | `slots-public` |
| CLAIM | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py claim` | `slots-claim` |
| EPOCH | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py epoch` | `slots-epoch` |
| PROMOTION | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py promotion` | `slots-promotion-v2` |
| MANDATE | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py mandate` | `slots-mandate-v2` |
| A11Y | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py a11y` | `slots-a11y` |
| C13 | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py c13` | `c13-current-bindings` |
| WAIST | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py ds5` | `ds5-table` |
| ATLAS | `python3 docs/superpowers/journals/debt-survey/blocked-ac/inspect_slots.py authority` | `atlas-scopes` |
| TS | `node docs/superpowers/journals/debt-survey/blocked-ac/inspect_frontend.mjs` | `frontend-ast` |
| DEMAND | Exact complete-corpus regex command in the named receipt | `demand-inventory` |
| HTTP | Exact three-selector pytest command in the named receipt | `public-and-case-http-data` |
| CLAIM-HTTP | Exact positive and default-negative pytest command in the named receipt | `claim-http` |
| C13-TEST | Exact C13 conjunction pytest command in the named receipt | `c13-conjunction` |

Pattern pass: P01/P02/P03 (chain and surface), P05/P15/P32 (purpose-bound authority),
P29/P35/P37/P38 (behavior, complete sets, predicate source and proxy divergence), P36 (warrant),
P39/P41 (proportional receipts and provenance of failure). The existing recurring survey hazard is
to call a implemented refusal a fillable positive appointment slot. The target is the whole
producer → artifact → bridge → consumer property with declared confidence and missing links.

## Per-row accounts

### 1. `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`

**Measured narrower; engineering incomplete in default deployment.** CLAIM reads a real signed
owner-event producer, resolver, append-only ledger operation and a distinct frozen
`claim_owner_event_bridge` profile in `scientist/evidence/claims/{owner_events,head_index}.py`.
The earlier stub and incompatible-profile premises are false. `lifecycle_bridge.py` creates a
candidate, then calls `append_verified_owner_event`; the runtime monitor route consumes it.
CLAIM-HTTP passes the exact historical positive signal and the default-negative control using
real HTTP, persisted readback, signature refusal, supersession and idempotent replay.

**Typed empty:** `_RepositoryClaimLedgerOwner.owner_event_authority:
ClaimSupersessionAuthority | None`; absence returns `claim_owner_event_authority_unappointed`.
However, `build_default_claim_ledger_owner` unconditionally returns `UnappointedClaimLedgerOwner`.
The positive test injects the repository owner through a development override; default HTTP
preserves `claim_head_absent` and `review_required`. An appointment arriving today is not a
configured production intake. Remaining link: sanctioned positive owner/appointment composition,
then real independently signed event admission (`implemented_but_not_orchestrated`,
`bridge_missing` for that positive deployment path). **Unblocks:** the default composition can
resolve the appointed owner. **Discharges:** the row's supersession property holds under that
composition, not solely a test override. No reduction to scope adjudication: legal/context
supersession and a four-way scope ruling decide different propositions. Dynamic positive
production configuration remains `unestablished`; the dev HTTP chain is `measured`.

### 2. `DS11-EXTERNAL-A11Y-COUNTERSIGN`

**Measured engineering gap behind an institutional input.** A11Y reads
`scientist/evidence/claims/posture.py`: `AccessibilityDocumentBinding` binds an internal historical
document and explicitly requires its statement that it does not replace the third-party
countersign. The external-certification arm of `_validate_fixed_semantic_bindings` is fixed to
`SourceClaimState.BLOCKED`, `evidence=None`, and a denied
`external_accessibility_certification` purpose. The available current-page receipt likewise
asserts `external_countersign_status == not_established` in its existing verifier.

**Typed empty:** the external-certification claim's semantic evidence is `None`; this is a
mechanized absence, not an admitted external-evidence slot. The static posture producer and
public/MACHINE posture consumers expose the absence; no non-test positive countersign admission
caller is established. An actual assessor's artifact today cannot change the fixed arm without
engineering. Missing: external document/identity/currentness/scope admission and its producer to
posture bridge (`producer_missing`, `bridge_missing`, `verification_missing`). **Unblocks:** an
external artifact plus a reachable admission mechanism. **Discharges:** an independent current
scope-exact countersign is admitted and tested. The row's institutional origin is real, but
engineering completeness is not. No shared deciding property with print receipts or performance.

### 3. `DS11-FULL-TRUST-CENTER-AND-DOCS-IA`

**Measured scope mismatch; allocation is inferred.** The retained marketing master explicitly
has `status: superseded`, `execution_authority: superseded`, and directs DS11–DS13 through the
Atlas master. Its Phase 2.11 and 2.15 prose is an inventory, not a fourth execution authority.
DS11's explicit non-closure preserves certifications, procurement, status, forms, sandbox,
calculators and general docs as `surface_out_of_scope`. ATLAS/DEMAND establish a successor scope
context, not an executing allocation for each retained route.

**Typed empty:** no institutional field is the blocker; this row concerns unallocated surfaces.
Non-test reachability of a complete retained-route population with approved owners/evidence
contracts is `unestablished`. Existing `/trust` posture does not establish that population.
Appointment has no role in building these surfaces. Engineering is incomplete at producer,
route/evidence-contract and verification links; exact residual population is unmeasured here.
**Unblocks:** an operational scope/allocation for the retained surfaces. **Discharges:** each
retained route meets its own owner/evidence contract. It does not reduce to publication or the
other DS11 rows; its population and repair differ.

### 4. `DS11-GROUNDED-PERFORMANCE`

**Measured remains a wider capability than signing a report.** PROMOTION shows protected
promotion still lacks its promotion-purpose EvalSafety input, while the default N8 value route
ends in `treatment_assignment_not_owner_derived`. PUBLIC constrains the public verification
record's `promoted_record` to `Literal[None]`; HTTP authenticates reports with that slot empty.
Neither observation asserts a census of historical promotion artifacts.

**Typed empty:** `PublicDecisionVerificationIssued/Response.promoted_record: Literal[None]`.
Non-test callers reach report verification and the N9 gate; a caller producing and consuming
content-bound **public performance evidence from a governed promotion** is not established.
Appointment alone cannot fill a `Literal[None]` or produce missing value evidence. Missing:
positive promotion evidence → public performance admission/projection (`producer_missing`,
`bridge_missing`, `surface_missing`). **Unblocks:** a real evidence-complete governed design and
its public-purpose evidence bridge. **Discharges:** content-bound performance evidence passes
its specific test and DS12's publication admission. Shared prerequisites with the publication
pair and first-candidate row are not whole-row reductions: performance meaning is an additional
property.

### 5. `DS11-INHERITED-C13-PRINT-RECEIPT`

**Measured same deciding object as row 6; evidence is stale again.** C13 re-hashes the complete
admitted denominator: **11 source bindings = 6 current + 5 stale**, and **3 producer bindings =
3 current**. C13-TEST fails at the actual current-byte conjunction on
`AmbientTelemetryHud.tsx`; it is not a missing capture or collection failure. The reader first
checks retained raw executions and then exact current bytes. The schema still limits DS18
`source_reconciliations` to `maxItems: 1`.

**Typed empty:** no institutional slot; the missing object is current independent execution
receipt/reconciliation evidence. The non-test caller is
`architecture/atlas_surfaces/check_frontend_disposition_register.py`, which actually parses the
journal's marked JSON receipt and checks the current bytes. Engineering/verification is
incomplete (`verification_missing`; reconciliation schema restriction persists). **Unblocks:**
current two-run evidence and schema-admissible reconciliation. **Discharges:** its named
conjunction and the full disposition check succeed. An appointment changes nothing. Candidate
reduction to row 6 is exact at the deciding conjunction/current-receipt property; separate row
standing is untouched. Full disposition replay and current browser captures remain unrun here.

### 6. `ds10-c13-print-receipt-reissue` (C)

**Measured narrower and wider.** Earlier missing captures were supplied, but the assertion that
only schema work remains is false at this base. The five current-byte mismatches over the same
11-source-binding denominator are `AmbientTelemetryHud.tsx`, `OperatorCraftPanel.tsx`,
`RunDetailLayout.tsx`, `RunReportPage.parity.test.tsx`, and
`runtime-dashboard.visual.spec.ts`. C13 retains the full identities and hashes; a fail-fast test
would expose only the first. Producer-chain bindings remain 3/3 current. No future browser
behavior is inferred from byte mismatches.

Slot, non-test checker, missing links, appointment effect, unblocking and discharge property are
exactly those in row 5. This is the strongest A/C reduction candidate: **same receipt, parser,
current-byte conjunction, schema restriction and DS6 independent evidence holder**. It is not
merely a shared DS10/DS11 prefix. Capability remains `verification_missing`; the global gate's
full error set was not measured and no source was changed to make the receipt fit.

### 7. `ds10-global-case-index-producer-allocation`

**Measured premise false for the stated candidate-discovery chain.** PUBLIC shows
`GlobalCaseIndexProducer` in `runtime/quality/global_case_index.py` persists and re-reads a
scope-bound S2 candidate snapshot. `GlobalCaseIndexCapabilityDiscoveryProvider.search` persists
a content-bound owner receipt, and `control_registry_providers.py` installs the provider.
HTTP passes the row's exact named test plus the false-persisted-binding negative: real S2
production → snapshot → owner receipt → default provider → authenticated HTTP.

**Typed empty:** `GlobalCaseIndexSnapshot.authority_owner_ref` is constrained empty. This is
candidate discovery, with `global_case_population_claim` explicitly denied. Appointment is not
needed for the measured chain and cannot broaden its purpose by filling that field. Engineering
is **complete for this bounded property**, including persisted output, bridge, consumer, surface
and semantic negative. There is no still-missing candidate producer to allocate. **Unblocks:**
the old producer absence has already been discharged in source. **Discharges:** its stated
candidate-index signal is exercised; changing register standing is outside this survey.
The wider global public case/contest/history population is not established. B's
`ds8-global-case-index` therefore shares a narrower chain, not automatically the whole property.

### 8. `ds10-public-decision-rendering`

**Measured narrower.** The old absence of endpoints is false: server issuance, anonymous
verification and a real viewer exist; HTTP passes issuance, readback and signature-tamper
refusal. TS follows `PublicDecisionViewerPage` to `fetchPublicDecisionVerification`.
But the delivered vocabulary is **report authentication**, not governed promoted-decision
admission; it denies that substitution explicitly.

**Typed empty:** the public response and record use `promoted_record: Literal[None]` (PUBLIC).
The non-test route/service/viewer is reachable for reports. A governed decision-rendering
consumer cannot receive a positive record through that contract. Engineering is incomplete for
the debt's governed property (`producer_missing`, `bridge_missing`, `surface_missing`), even if
an institution is appointed today. **Unblocks:** a real promoted record and its positive typed
public contract. **Discharges:** the governed decision is custody-bound and rendered through
its own gate. It is a reduction candidate with row 13 only for **governed public-record
admission**; rendering and citizen publication acceptance must not disappear in that reduction.

### 9. `ds15-mandate-intake-has-no-registered-task`

**Measured mixed engineering/institutional boundary; equivalent allocation unestablished.**
MANDATE reads the real `CurrentMandateOwnerEvidence` and CAS/signature/currentness resolver in
`runtime/quality/agent_action_authority.py`. `AcquisitionActionService` has a typed
`AcquisitionAuthorityGatewayProvider | None` and refuses when absent. Container composition
passes only `config.overrides.acquisition_authority_provider`; non-development app creation
rejects direct `container_overrides` and demands a factory-attested deployment-security bundle.
This is a real downstream authority consumer but not a demonstrated sanctioned deployment intake.

**Typed empty:** `authority_provider=None`; external signed v2 delegation and current
mandate-owner evidence are separate inputs. Non-test acquisition request/worker paths call the
provider; a configured positive deployment provider is unestablished. Appointment alone leaves
the composition gap (`bridge_missing`, `implemented_but_not_orchestrated`). **Unblocks:** the
sanctioned composition can admit the signed external inputs. **Discharges:** actual deployment
admission and action binding use them. DEMAND spans every active plan and the wider research
corpus. DS15 C02/explicit non-closures, GY-PA2 and adjacent re-entry scopes show related work;
exact-name absence is not an exhaustive alias adjudication. Allocation stays **unestablished**,
not a new owner decision. B's admission-bundle/production-route rows share stages, not this
signed-mandate predicate or its full signal.

### 10. `ds18-positive-transition-production-unorchestrated`

**Measured wider than wiring alone.** EPOCH's complete source AST finds no direct construction
of `EpochValidityTransitionProducer`; provider method definitions occur only on their protocols
and are called from that producer. That is static evidence, not a universal dynamic-call proof.
More decisively, its entire `produce_and_persist` body ends, even after exact signed evidence
resolves, with `del record` and `epoch_transition_exact_evidence_unavailable`: it has no positive
owner-held producer-identity admission/issuance terminus.

**Typed empty:** `NoEpochTransitionSigningAuthority` returns a typed nonreceipt; the producer
accepts a signing authority, but successful signing still reaches the terminal nonreceipt.
No non-test positive producer caller is established. DecisionValidity default construction also
leaves the reconciliation reader unfilled; the reader itself requires verifier provenance.
Missing: complete dependency/adjudication providers, a real trigger, producer-identity carrier,
positive persistence and reconciliation wiring (`implemented_but_not_orchestrated`,
`producer_missing`, `bridge_missing`). Appointment today changes none of those missing links.
**Unblocks:** a reachable producer with complete owner inputs and an actual positive artifact
terminus. **Discharges:** a real trigger persists the exact positive transition for downstream
intake. This is not reduced to the verifier row: producer emission and independent verification
have different deciding properties and holders.

### 11. `ds18-positive-transition-verification-producer-missing`

**Measured remains engineering work; the historical contradiction is narrower.** EPOCH reads
`DecisionValidityService` with `epoch_transition_verifier: EpochTransitionVerifier | None` and
`epoch_denominator_reconciliation_reader: ... | None`. Its default verifier deletes all inputs
and raises `verifier_not_configured`. The complete source census has six service constructor
occurrences, with no positive verifier/reconciliation injection. The reconciliation reader now
exists and separates the two denominator meanings; the legacy equality branch still runs when
that reader is absent. Thus absence of the reconciliation mechanism is not the remaining fact.

**Typed empty:** `NoEpochTransitionVerifier.verifier_provenance_ref=None`; optional service
injections also default empty. Non-test DecisionValidity callers exist; a positive verification
provider/caller is unestablished. Missing: positive verifier, admitted verifier provenance,
reconciliation injection and real transition consumption (`producer_missing`, `bridge_missing`).
Appointment alone cannot make the default verifier inspect bytes. **Unblocks:** the positive
verification and reconciliation chain can consume an exact transition. **Discharges:** positive
end-to-end verification with wrong/missing/substituted evidence refused. Same dependency chain
as row 10, but different repair and holder; prefix grouping is refuted.

### 12. `ds5-waist-successors-routed-to-unscoped-slices`

**Measured premise narrowed; exact residual adequacy unestablished.** WAIST's two independent
parsers agree on **27 groups / 58 sites** in the complete direct-Badge table. The historical
handoff subset is **6 groups / 11 sites**: DS12 3/7; DS14 1/1; DS15 1/1; DS18 1/2. ATLAS now
explicitly takes DS12 and DS14 inherited obligations into scope; DS15/DS18 have slice scopes.
A missing standalone DS12 filename cannot be the scope predicate.

**Typed empty:** no one institutional input represents this heterogeneous row. Its obligations
are generated owner fields, private issuers, mixed-veto and novelty handling at six consumer
families. TS finds delivered `ProjectionFreshness` and public-verification DTO vocabulary;
absence of the old group label therefore does not prove the promised contract is absent. The
full semantic adequacy of every current issuer at those historic sites was not established.
Engineering remains **unestablished at exact residual granularity**, with `bridge_missing` /
`semantic_test_missing` as hypotheses rather than reasserted census facts. **Unblocks:** executing
allocation of the as-yet-undischarged issuer obligations; **discharges:** each actual table
property, not a plan filename. Allocation is **inferred yes for unresolved execution**, not an
owner appointment. The six groups do not share one repair and holder; they cannot be collapsed
into a single class solely because all use branded owner presentations.

### 13. `ds8-public-case-publication`

**Measured scope premise false and endpoint premise narrowed.** ATLAS's DS12 Inherited
obligations explicitly includes this exact ID, alongside the real public record/certificate and
citizen-verification scope. DS12 is no longer only a one-line candidate. PUBLIC/HTTP show the
server signing/report chain delivered; `promoted_record: Literal[None]` means even a new real
promotion receipt cannot become a governed public record through the delivered response alone.

**Typed empty:** that literal-empty record field. Non-test report issuance/verification is
reachable; positive governed public-case admission remains `producer_missing`/`bridge_missing`.
Appointment alone cannot alter a Literal or supply the promotion/design evidence. Scope
allocation to DS12 is explicit; whether a remaining executing task owns every positive record
link is `unestablished`, so the old candidate-not-owner label is not simply repeated.
**Unblocks:** positive promotion-to-public-record engineering and genuine evidence.
**Discharges:** one custody-bound governed case is actually published and citizen-verifiable.
Partial reduction candidate with row 8 and B's signed-public-decision surface: shared governed
public-record admission, with each distinct surface/acceptance conjunct retained.

### 14. `ds8-lex-clerk-authority-repair`

**Measured scope premise false; Clerk implementation remains incomplete.** ATLAS's DS14 scope
and inherited-obligation act name the Clerk strangle; Lex route/discovery is DS10/team-design,
while Lex pipeline mutation is team-lex. The old DS10-description conflict and lack-of-scope
claim therefore no longer decide anything. These are scope findings, not permission to implement.

**Typed empty:** no institutional slot is needed for the missing surface bridge. The actual
Clerk path (`useClerkNlRun` → `useLaunchNlRun` → run SSE; `StructuredResponseData` rendering) is
present. TS walks all **32 Clerk `.ts/.tsx` files** and finds no literals of the promised
`PromptToolParserAuthorityLedger`, `CompressionLossReceipt`, `agent_session`,
`orchestration_audit`; this is exact vocabulary evidence only. The delivered run-based vocabulary
was read before comparison. Positive G6 authority-delta/session/audit projection through Clerk
is not established. Missing: typed endpoint/client/consumer bridge and its P15 semantic negatives
(`bridge_missing`, `consumer_missing`, `semantic_test_missing`, inferred execution allocation).
**Unblocks:** the scoped G6→Clerk surface composition. **Discharges:** candidate-clothed choices,
loss and denied uses survive real rendering. No reduction to public signature semantics or DS5's
single blocker-issuer property: their consumers, repair and holder obligations differ.

### 15. `eval-safety-promotion-authority-producer-missing`

**Measured engineering gap, not a fillable appointment.** PROMOTION's
`_eval_safety_obligation` accepts only `ValueGateReceipt | None`; the protected modes
`sandbox_pilot`, `field_pilot`, `deployment` return unconditional `scope_insufficient` with
`owner_ref='absent/unallocated'`. There is no promotion-authority evidence input in that
function. The implemented `EvalSafetyCertificate` is fixed to attempted-evaluation admission
and denies promotion use. Its existing production caller cannot supply the missing purpose.

**Typed empty:** a fail-closed obligation result, **no established typed positive promotion
slot**. The non-test N9 obligation compiler reaches this result. Engineering is incomplete:
promotion-purpose contract/artifact, producer, verifier, persistence and consumer admission
(`absent/unallocated`, `producer_missing`, `bridge_missing`). Appointment alone changes no
reachable evidence input. **Unblocks:** a purpose-correct positive/refusal mechanism with an
admissible authority source. **Discharges:** a real protected request yields a decisive result,
while the required pilot protection/near-miss and unchanged safety-core conditions also hold.
B's scope-insufficiency row shares this remaining arm; GY-O0-NC-01 has additional whole-signal
conditions. Neither is wholly reduced to it.

### 16. `first-promotion-candidate-with-complete-evidence`

**Measured historic wiring premise false; remaining chain is still incomplete.** PROMOTION
finds the N9 context provider now wired by the generation-cycle constructor; the production
bridge persists effect, measurement and independence evidence. The source AST has one
`ValueGateReceipt` class, zero direct constructor occurrences, and two `model_validate` readers
in `promotion_sequence.py` over the complete 2,653-file source denominator. Those counts do not
prove a global receipt-population zero. The decisive called-path fact is stronger: the default
`FoundryValuePort.__call__`, after successful method selection, unconditionally returns
`treatment_assignment_not_owner_derived`; it cannot emit `value_ready`.

**Typed empty:** `ValuePortObservation` defaults pending; the called default value producer has
no positive terminus. This is not a single institutional field: the engineering SKG alternative
and institution-signed rollout route differ, while `_ValueInputWorldKnowledgeAlternative` is a
strict **gap declaration** (`Literal['unsatisfied']`), not proof that no other admission contract
exists. Non-test generation→N8→N9 callers exist; complete authentic value receipt production does
not. Missing links are positive value production/persistence and authentic upstream relation,
calibration/adjudication evidence (`producer_missing`, `artifact_missing`); receipt population
and current external data adequacy were not re-censused here. **Unblocks:** the real positive
value/evidence path. **Discharges:** one authentic candidate jointly reaches canonical production
`consumer_promotable=True`. It shares prerequisites with promotion/performance/publication but
cannot discharge the protected-pilot EvalSafety, near-miss or counters conditions.

## Classes, reductions and institutional counterfactual

The **five DS11 rows are not one class**: signed supersession composition, external accessibility
admission, retained-surface allocation, performance evidence and print currentness have different
mechanisms, missing links and holders. The **three ds10 rows are not one class**: candidate-index
production is demonstrated, public promoted-record admission is unavailable, and print evidence
is stale. The **two ds18 positive-transition rows share a dependency chain but not the deciding
property**: emission versus independent verification. A future repair of one need not fix the other.

The C13 pair is an exact reduction candidate on its common receipt/currentness conjunction and
DS6 holder. The public pair is only a partial reduction candidate at governed-record admission;
the surface-specific acceptance remains. Promotion rows are prerequisite relationships, not
full equivalences. Cross-workstream comparisons were communicated to root and B; no other
worker's row was independently adopted or adjudicated.

No row in this A/C remit has been established as **genuinely institutional with complete
engineering and a fillable production slot**. That statement is over the 16 explicit assessments
below, not a claim about all repository institutional inputs. A typed refusal, literal-empty
field, or development injection is insufficient. Where executing allocation is not demonstrated,
`unestablished` is kept rather than inferred from a name search.

## Machine-readable assessment

`premise_false=yes` means at least one material asserted premise is false/narrowed at the base;
it never means the whole row is closed. Engineering is assessed against the debt's positive
capability; the candidate-index row explicitly has the narrower denominator above. Allocation
means unresolved engineering execution allocation, not institution appointment. Unknowns are part
of the result.

```json
[
 {"id":"DS11-CLAIM-LIFECYCLE-ORCHESTRATION","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":[],"property":"signed legal/context supersession via default Claim owner","unknowns":["sanctioned positive deployment owner intake"],"confidence":"measured"},
 {"id":"DS11-EXTERNAL-A11Y-COUNTERSIGN","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":[],"property":"admit current independently countersigned accessibility evidence","unknowns":["positive external evidence admission implementation"],"confidence":"measured"},
 {"id":"DS11-FULL-TRUST-CENTER-AND-DOCS-IA","premise_false":"yes","appointment_effect":"not_institutional","engineering":"incomplete","allocation":"yes","reduction_peers":[],"property":"retained routes have scoped owners and evidence contracts","unknowns":["complete retained-route residual population","equivalent executing allocations"],"confidence":"inferred"},
 {"id":"DS11-GROUNDED-PERFORMANCE","premise_false":"unestablished","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":[],"property":"content-bound public performance evidence from governed design","unknowns":["governed receipt population","positive public-performance bridge"],"confidence":"measured"},
 {"id":"DS11-INHERITED-C13-PRINT-RECEIPT","premise_false":"yes","appointment_effect":"not_institutional","engineering":"incomplete","allocation":"no","reduction_peers":["ds10-c13-print-receipt-reissue"],"property":"same C13 receipt/current-byte conjunction and schema-admissible reconciliation","unknowns":["current browser captures","full disposition error set"],"confidence":"measured"},
 {"id":"ds10-c13-print-receipt-reissue","premise_false":"yes","appointment_effect":"not_institutional","engineering":"incomplete","allocation":"no","reduction_peers":["DS11-INHERITED-C13-PRINT-RECEIPT"],"property":"same C13 receipt/current-byte conjunction and schema-admissible reconciliation","unknowns":["current browser captures","full disposition error set"],"confidence":"measured"},
 {"id":"ds10-global-case-index-producer-allocation","premise_false":"yes","appointment_effect":"not_institutional","engineering":"complete","allocation":"no","reduction_peers":[],"property":"tenant/cell-scoped canonical S2 candidate index through default discovery","unknowns":["wider public global-case population is outside demonstrated purpose"],"confidence":"measured"},
 {"id":"ds10-public-decision-rendering","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":["ds8-public-case-publication"],"property":"partial only: governed public-record admission; rendering retained","unknowns":["positive promoted-record contract and public admission"],"confidence":"measured"},
 {"id":"ds15-mandate-intake-has-no-registered-task","premise_false":"unestablished","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":[],"property":"sanctioned deployment intake of signed delegation and current owner evidence","unknowns":["equivalent active successor allocation","positive deployment provider"],"confidence":"measured"},
 {"id":"ds18-positive-transition-production-unorchestrated","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"yes","reduction_peers":[],"property":"complete owner-bound positive transition emission and persistence","unknowns":["non-test dynamic producer trigger","sanctioned identity-carrier admission"],"confidence":"measured"},
 {"id":"ds18-positive-transition-verification-producer-missing","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"yes","reduction_peers":[],"property":"independent exact positive transition verification and reconciliation","unknowns":["configured positive verifier"],"confidence":"measured"},
 {"id":"ds5-waist-successors-routed-to-unscoped-slices","premise_false":"yes","appointment_effect":"not_institutional","engineering":"unestablished","allocation":"yes","reduction_peers":[],"property":"six heterogeneous owner-issued presentation contracts","unknowns":["semantic adequacy of each delivered issuer at historical sites","executing allocation for exact remaining obligations"],"confidence":"inferred"},
 {"id":"ds8-public-case-publication","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":["ds10-public-decision-rendering"],"property":"partial only: governed public-record admission; publication retained","unknowns":["executing positive record-half allocation","governed published receipt population"],"confidence":"measured"},
 {"id":"ds8-lex-clerk-authority-repair","premise_false":"yes","appointment_effect":"not_institutional","engineering":"incomplete","allocation":"yes","reduction_peers":[],"property":"G6 session/audit/loss semantics consumed by Clerk","unknowns":["executing lane allocation","positive end-to-end G6 Clerk projection"],"confidence":"inferred"},
 {"id":"eval-safety-promotion-authority-producer-missing","premise_false":"no","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"yes","reduction_peers":[],"property":"protected promotion-purpose safety evidence admission","unknowns":["appointed purpose-specific authority","positive promotion contract"],"confidence":"measured"},
 {"id":"first-promotion-candidate-with-complete-evidence","premise_false":"yes","appointment_effect":"none_on_blocked_capability","engineering":"incomplete","allocation":"unestablished","reduction_peers":[],"property":"authentic complete value/effect/measurement/independence candidate","unknowns":["current real receipt population","authentic upstream data adequacy"],"confidence":"measured"}
]
```

## Verification limits

HTTP's three named tests pass; CLAIM-HTTP's two named tests pass. C13-TEST reaches and fails
current source-byte validation. The initial public-report replay stopped before the property on
missing catalog data; the later replay used a read-only-use link to the canonical data. Both
receipts are retained. All these tests used the existing main-workspace Python environment with
`PYTHONPATH=src:.`; tracebacks and source binding use this worktree. This is a borrowed-host
receipt, not a claim that an isolation-local lock-bound environment was provisioned.

No source, test, governed artifact, active plan, debt row or owner was changed. No browser
capture, full backend suite, disposition rewrite, publication or appointment was performed.
The per-row unknowns limit the findings rather than becoming zeros. The failure/repair register
is re-read at closeout; no new anti-pattern class or repair decision is asserted by this survey.
