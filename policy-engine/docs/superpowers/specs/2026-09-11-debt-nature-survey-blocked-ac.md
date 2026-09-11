# Debt nature survey — blocked A/C workstream

Base: `fc823071a7b6f2c9a573172aec3499ad6d138c0f`. Read-only analysis; no standing,
closure, allocation, owner appointment or repair decision. This first checkpoint is partial.

## Denominator and method

The root's independent reconciliation selects exactly 16 blocked identities: 15 in A and one
in C. Membership comes from `../journals/debt-survey/denominator/reconciliation.json`; register
prose supplies hypotheses only. This workstream does not measure another worker's row.

The shared AST instrument compares the complete pinned Git set with an independent filesystem
walk and compares `ast.walk` with a separate `NodeVisitor`, including asynchronous definitions.
The source denominator is **2,653 `src/**/*.py` files**, with zero parse ambiguities; full
definition distributions by package are retained. These are static call occurrences, not dynamic
reachability. Demand search walks **683 files** under active plans, reference, research and
system-design-decisions, of types `.md/.json/.yaml/.yml`, excluding DEBT-REGISTER and LEDGER.
Its literal matches are an index for reading scopes, not proof that an equivalent owner is absent.

Replay commands and deciding-output hashes are in
`docs/superpowers/journals/debt-survey/blocked-ac/receipts.json`. Every source path below denotes
that tracked path at `fc823071a`; receipts retain the complete output under the adjacent ignored
`raw/` directory. Commands run from `policy-engine/`.

Pattern pass: P01/P02/P03 (complete chain), P05/P15/P32 (purpose-bound evidence), P29/P35/P37/P38
(behavior, complete denominator, predicates and proxies), P36 (scope authority), P39/P41
(proportional receipts, provenance of failure). The target is a property account with explicit
`measured`, `inferred` and `unestablished` claims, not register-status repair.

## First measured source corrections

### `ds10-global-case-index-producer-allocation`

**Measured, narrower.** The historical missing-producer/provider premise no longer describes
the source: `src/polisyos/runtime/quality/global_case_index.py` defines `GlobalCaseIndexProducer`;
`GlobalCaseIndexCapabilityDiscoveryProvider.search` in `capability_discovery.py` constructs it,
persists a snapshot and a content-bound `GlobalCaseIndexOwnerReceipt`; the default provider
is installed by `runtime/http/services/control_registry_providers.py`. The exact historical
closure test now exists in `tests/unit/runtime/http/test_capability_discovery_api.py`.

This index is explicitly candidate grade: `authority_owner_ref` is empty, and the provider
forbids `global_case_population_claim`. Engineering for candidate discovery is present;
an appointed universal case-population authority is a different property. Dynamic replay and
the boundary between this row's exact signal and that wider claim remain pending.

Deciding source command: `python3 docs/superpowers/journals/debt-survey/open/inspect_tree.py ast
'EpochValidityTransitionProducer|EpochTransitionVerifier|NoEpochTransitionVerifier|DecisionValidityService|EpochDependencyDenominatorProvider|EpochPerturbationAdjudicationProvider|EpochTransitionDenominatorReconciliationReader|append_verified_owner_event|PublicDecisionVerificationService|CaseProvider|GlobalCase|ValueGateReceipt|ValuePortObservation|CanonicalN9PromotionPort|_eval_safety_obligation|DelegationMandate|CurrentMandateOwner|PublicSignaturePopulation' --source-only`
(`source-definitions` receipt).

### `ds10-public-decision-rendering` and `ds8-public-case-publication`

**Measured, narrower.** The server report-signing and public verification mechanism exists in
`runtime/http/routes/public_decisions.py` and `runtime/http/services/public_decision_verification.py`.
The contracts in `public_decision_verification_contracts.py` constrain `promoted_record` to
`Literal[None]`. Report authentication cannot create a governed promoted design or its public
signature. The historical total endpoint absence is false; governed publication remains a
separate, unfilled positive contract.

The existing HTTP test `test_owned_run_packet_is_redacted_issued_and_publicly_verified` exercises
POST issuance, anonymous GET, persisted-signature tampering and refusal, with the promoted slot
empty. This survey's replay (`public-report-http`) stopped in fixture setup because this isolated
tree lacks the catalog DuckDB source. It did not reach the property. **Dynamic reachability is
unestablished by that replay**, and the failure is not classified as a product defect or inherited
red. The interpreter was borrowed from the main workspace; project source resolved inside this
worktree, as the retained traceback shows. Local lock-bound environment admission remains absent.

### `DS11-CLAIM-LIFECYCLE-ORCHESTRATION`

**Measured, narrower.** `scientist/evidence/claims/head_index.py` now implements the repository
owner's `append_verified_owner_event`: it resolves a signed event, binds the exact prior ledger,
persists an append-only successor, writes the discriminated `claim_owner_event_bridge` profile,
and advances through head CAS. This is no longer an unconditional nonreceipt stub. Its
`owner_event_authority: ClaimSupersessionAuthority | None` remains a real typed optional input;
missing authority returns `claim_owner_event_authority_unappointed`. Producer, profile and
runtime composition need separate checks before appointment alone can be called sufficient.

## Remaining survey work

The other A/C rows, institutional counterfactuals, scope readings, TS AST census, candidate
reductions and the complete machine-readable assessment are pending. No incomplete row is
silently classified by this checkpoint.
