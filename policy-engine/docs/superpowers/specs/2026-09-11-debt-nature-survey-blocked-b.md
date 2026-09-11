# Debt nature survey — blocked section B

Pinned source: `fc823071a7b6f2c9a573172aec3499ad6d138c0f`. This is a survey of the 19 B/blocked subjects reconciled in the master, not a change to standing, allocation or implementation. The register supplies membership and hypotheses only.

## Method and evidence

Every source claim below names a deciding receipt in `docs/superpowers/journals/debt-survey/blocked-b/receipts.json`. Each receipt contains exactly one replayable command, its actual exit, complete-output path and SHA-256. Source paths in this document are relative to `policy-engine/` and pinned to `@fc823071a`; measurement scripts are survey artifacts. Oversized complete outputs remain in the already-ignored `blocked-b/raw/` directory.

`measure.py GROUP` reuses the master AST instrument: all 5,686 tracked Python files under `src/`, `tests/`, `tools/`, `architecture/`, including all 2,653 source Python files; independent filesystem enumeration reconciles exact identities with the pinned Git tree. `ast.walk` and a separate `NodeVisitor` reconcile class/function/async-function/call identities. Results contain complete package definition distributions and matched module distributions, including parse ambiguities (none in these receipts). AST occurrence is static evidence, never proof of runtime reachability. The complete demand scan covers 683 tracked `.md/.json/.yaml/.yml` files in active plans, reference, research and system decisions, excludes DEBT-REGISTER/LEDGER, and includes the withheld-propositions and research finding registers. A missing guessed filename is recorded, then replaced by the discovered owner in the `*-current` receipt; it is never counted as an absent capability.

The pattern pass applies P01/P02/P03/P05/P29/P32/P35/P36/P37/P38: separate source slot from candidate artifact, institutional act from our intake, refusal from a missing positive consumer, and matching names from shared deciding properties. For each row, *unblocks* means a prerequisite changes; *discharges* means the row's full stated property is demonstrated. A typed `None` placeholder is not automatically a fillable admission port. Dynamic checks use the existing main-worktree interpreter read-only, explicitly bind imported modules to this worktree's `src`, and run only existing tests. No appointment or new test is made.

## B-PUBLIC — two DS8 rows

### `ds8-global-case-index`

**Measured, narrower than the subject.** The no-producer/no-provider premise is false. `runtime/quality/global_case_index.py@fc823071a` defines `GlobalCaseIndexProducer.produce`: it enumerates the complete tenant-visible CAS, selects canonical PDC S2 binding manifests, verifies content/schema/producer and referenced design/search records, persists `GlobalCaseIndexSnapshot`, and reads it back. `GlobalCaseIndexCapabilityDiscoveryProvider.search` in `runtime/quality/capability_discovery.py@fc823071a` invokes it, persists the content-bound `GlobalCaseIndexOwnerReceipt`, and emits the case rows. `runtime/http/services/control_registry_providers.py@fc823071a` installs that provider in default composition. Receipts `public-current` and `public-existing-tests` (exit 0) establish the source chain and existing integration-style behavior.

**Wider boundary.** The denominator is the tenant-visible *canonical S2 binding* set, not all possible policy cases. `limitation_codes=(s2_bindings_only, terminality_not_established)` and the provider's `may_not_use_for` includes `global_case_population_claim`, `policy_authority`, and `terminal_run_completion`. This bounded inventory cannot establish global recall or public authority. `GlobalCaseIndexSnapshot.authority_owner_ref: None` is a real empty source field but candidate indexing neither waits for nor consumes an appointment; a human appointed today changes no code path. The engineering chain for the bounded inventory is complete; broader population authority remains unestablished, not implied.

**Reduction/class.** Candidate reduction with `ds10-global-case-index-producer-allocation` only for the shared deciding property: canonical S2 snapshot + verified owner receipt + installed case discovery provider. Holder is the runtime case-index owner, repair is the same producer/bridge chain. A/C owns that comparison. No reduction to signed public decisions: a case inventory is not a public promotion. *Unblocks:* the source chain already exists. *Discharges:* an accepted demand scope and its exact complete-denominator behavior, not a string hit. No institutional prerequisite for this bounded capability; no new allocation is established by this survey.

### `ds8-signed-public-decision-surface`

**Measured, partly narrower.** The old zero-route/unwired-export premise is false. `runtime/http/routes/public_decisions.py@fc823071a` mounts issuance from a persisted run decision packet through `build_public_export_bundle` and `PublicDecisionVerificationService.issue`, and a public verification reader returns authenticated retained bytes. `public-existing-tests` exits 0 across the real issue/verify/refusal route tests and index tests. The implemented object is explicitly `verification_report_only`.

**Deciding boundary.** `PublicDecisionVerificationIssued`, `PublicDecisionVerificationRecord` and `PublicDecisionVerificationResponse` contain `promoted_record: Literal[None]`. The seven dimensions in `PublicDecisionVerificationDimensions` are each `Literal["not_established"]`. This is PV-K01's vector boundary (`docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md@fc823071a`, PV-K01), not a public-decision authority signature. The report signer can authenticate the report today; appointment alone cannot turn its forbidden promoted-record branch positive. Promoted PUBLIC record producer/admission/lifecycle/projection are outside this implemented report chain (`producer_missing` / `bridge_missing` for that authority purpose). The current typed-empty surface is real but is not the institution-admission mechanism.

**Reduction/class.** Candidate reduction with `ds10-public-decision-rendering` and `ds8-public-case-publication` is limited to *admitting and rendering a promoted PUBLIC record with custody-bound authority*, not generic signing. Their A/C owner evaluates their own signals. *Unblocks:* a genuine admitted promoted record chain and successor scope. *Discharges:* its public projection, current custody and verification semantics with negative tests; issuing a report alone does not. Allocation for that authority chain remains unestablished here.

## B-W5 — `w5-institutional-authority-slots`

**Measured correction to both old hypotheses.** The complete subject has 18 unique W5 route IDs, independently reconciled by the master. The four delivered builders exist under their current vocabulary; the original guessed-name census is not the instrument. `w5` derives definitions/calls and the full demand set; `w5-existing-tests` exits 0 for the existing AQ/CR/CB/ML tests. `tools/quality/validation/check_canonical_vocabulary_crosswalk.py@fc823071a`, `_families`, maps names with `equivalence_claimed=False` throughout. Its validator parses the declared classes and validates vocabulary/projection behavior; it does **not** establish all 18 purpose-specific authority admission paths. The explicit `CoAuthentic` mapping refuses equivalence to a source pack.

**Measured source counterfactual.** AQ's `NonDataReceipt` fixes `institutional_signer: None`, `authority_granted: Literal[False]`, purpose `candidate_process_only`. CR's `_CandidateRecord` fixes signer/substitute to `None`, execution to `False`; `AdaptationDecisionRecord.status` is `Literal["failed_safe"]`, naming `missing_role`. CR has a real `main` CLI using `submit/process/snapshot`. CB's `ComprehensionResult.human_comprehension_established` always returns `False`; `CandidateDesign.authority_source` is `None` and the projection names `W5-R3-Q06_item_adjudicator_absent`. ML's `CandidateAssuranceResult.signer` always returns `None`, `qualified_holders` is empty, equivalence is false, and `read_assurance_result` rejects a supplied nonempty qualified holder. These candidate refusals are intentional and real. Appointment alone cannot change their authority outcomes; they need a distinct admitted institution-evidence path before the blocked authority property can change. `may_not_use_for` excludes protected action/authority, comprehension, legal equivalence and source authority respectively. WP-08 and WP-13 distinguish activation from this constructible engineering half; WP-09/11/12 preserve additional numerical and language boundaries.

The individual 18-purpose account and wider source-owner comparison are being completed below. No aggregate claim that all 18 engineering halves are complete is made at this checkpoint.

## Remaining owned rows — unresolved at this checkpoint

The following rows remain under measurement; no debt premise is accepted from the register and no status is inferred from a prefix.

### `GY-DEF23`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `GY-GAP2`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `GY-GAP3`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `GY-GAP5`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `GY-GAP6`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `GY-O0-NC-01`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `ds15-deterministic-admission-bundle-producer`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `ds15-fresh-positive-production-route`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `ds15-gy-gap6-evidence-register-closure`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `ds15-int-r2-gap-acquisition-case-union`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `ds15-numeric-voi-metric-residual-granularity`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `gy-n12-epoch-current-decision-lineage-carrier-unallocated`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `gy-n12-epoch-predicate-policy-authority-unappointed`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `gy-n12-epoch-transition-signing-authority-unappointed`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `gy-n12-lex-amendment-valid-effect-carrier`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.

### `gy-promotion-obligations-scope-insufficient`

Unestablished at this checkpoint: narrower/wider scope, source slot and non-test caller, appointment counterfactual, exact missing chain, unblocking versus discharge, and shared deciding-property reduction. No classification is issued pending its receipt.
