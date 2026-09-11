# Debt nature survey — base fc823071a

Survey of claims; no standing, closure, allocation, task registration or implementation decision.

## 1. Reconciled live set

**Measured.** Both independent derivations agree on every `(id, section)` in the complete 258-ID register denominator, and on every `(id, section, status)` in the live 62-ID set: **27 open + 35 blocked**. There are no identity omissions or section disagreements. The one status discrepancy below remains ambiguous and is retained outside that 62-ID set.

Replay from `policy-engine/` (all commands in this survey use that working directory unless stated otherwise):

```sh
python3 docs/superpowers/journals/debt-survey/denominator/reconcile.py
```

Full output: `docs/superpowers/journals/debt-survey/denominator/reconciliation.json`. The subject is `docs/plans/active/DEBT-REGISTER.md`; it supplies membership and hypotheses only. No register or ledger assertion is used as evidence about source behavior.

Derivation A imports `_parse_register` from `tools/quality/validation/check_debt_ledger.py@fc823071a`. It follows the production checker’s section, strikethrough and column-offset grammar. Derivation B is an independent table-block lexer in the replay command: it recognizes whole status cells, carries table context across interrupted blocks, and does not call any checker cell/status helper. The comparison asserts identity equality and then live identity/section/status equality, not just matching totals.

Live set digest (sorted triples, JSON compact encoding): `ff43f6e2ecb6b1391279b1be0b75afa5740f0d7273da3bd24541716195e0fc7c`.

**The 207/258 gap.** Within the 258 debt-ID denominator, 207 rows in A/B/C/D/F have explicit recognized whole status cells; the remaining 49 are in G (closed by section) and 2 are in E (folded by section). `207 + 49 + 2 = 258`. Two additional E entries are branch records, excluded explicitly by both derivations. Statuses over the full 258-ID denominator are 186 closed, 35 blocked, 27 open, 6 foreign, 3 folded, 1 ambiguous. A literal scan of every table in the document would also count non-debt vocabulary tables; that is a different denominator.

**Ground-truth check.** `w5-institutional-authority-slots` is B / blocked in both derivations. A regex route extractor and an independent backtick-token extractor agree on these 18 unique route identifiers in that subject row:

`W5-O5-Q04`, `W5-O5-Q05`, `W5-O5-Q10`, `W5-R2-Q04`, `W5-R2-Q05`, `W5-R2-Q06`, `W5-R2-Q13`, `W5-R3-Q06`, `W5-R3-Q08`, `W5-R4-Q08`, `W5-R4-Q09`, `W5-R5-Q02`, `W5-R5-Q04`, `W5-R5-Q08`, `W5-R5-Q09`, `W5-R5-Q10`, `W5-R6-Q04`, `W5-R6-Q05`.

**Unclassifiable status.** `extraction-ask-offers-six-of-ten-evidence-classes` is A / ambiguous to the checker and A / folded to the whole-cell lexer. Its subject contains code with pipe-delimited enum values before the status column; `_cells()` splits those pipes and `_parse_register()` reads the shifted column. The survey retains this discrepancy as **ambiguous**, makes no status edit, and does not silently add it to either open or blocked. The initial parser-development receipt also records three C rows missed before interrupted table blocks were handled; the final identity assertions include them.

Exact live membership (membership is a measurement of the survey subject, not proof of the debts’ factual premises):

### Blocked A and C

| ID | Section | Standing read |
| --- | --- | --- |
| `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` | A | blocked |
| `DS11-EXTERNAL-A11Y-COUNTERSIGN` | A | blocked |
| `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` | A | blocked |
| `DS11-GROUNDED-PERFORMANCE` | A | blocked |
| `DS11-INHERITED-C13-PRINT-RECEIPT` | A | blocked |
| `ds10-c13-print-receipt-reissue` | C | blocked |
| `ds10-global-case-index-producer-allocation` | A | blocked |
| `ds10-public-decision-rendering` | A | blocked |
| `ds15-mandate-intake-has-no-registered-task` | A | blocked |
| `ds18-positive-transition-production-unorchestrated` | A | blocked |
| `ds18-positive-transition-verification-producer-missing` | A | blocked |
| `ds5-waist-successors-routed-to-unscoped-slices` | A | blocked |
| `ds8-lex-clerk-authority-repair` | A | blocked |
| `ds8-public-case-publication` | A | blocked |
| `eval-safety-promotion-authority-producer-missing` | A | blocked |
| `first-promotion-candidate-with-complete-evidence` | A | blocked |

### Blocked B

| ID | Section | Standing read |
| --- | --- | --- |
| `GY-DEF23` | B | blocked |
| `GY-GAP2` | B | blocked |
| `GY-GAP3` | B | blocked |
| `GY-GAP5` | B | blocked |
| `GY-GAP6` | B | blocked |
| `GY-O0-NC-01` | B | blocked |
| `ds15-deterministic-admission-bundle-producer` | B | blocked |
| `ds15-fresh-positive-production-route` | B | blocked |
| `ds15-gy-gap6-evidence-register-closure` | B | blocked |
| `ds15-int-r2-gap-acquisition-case-union` | B | blocked |
| `ds15-numeric-voi-metric-residual-granularity` | B | blocked |
| `ds8-global-case-index` | B | blocked |
| `ds8-signed-public-decision-surface` | B | blocked |
| `gy-n12-epoch-current-decision-lineage-carrier-unallocated` | B | blocked |
| `gy-n12-epoch-predicate-policy-authority-unappointed` | B | blocked |
| `gy-n12-epoch-transition-signing-authority-unappointed` | B | blocked |
| `gy-n12-lex-amendment-valid-effect-carrier` | B | blocked |
| `gy-promotion-obligations-scope-insufficient` | B | blocked |
| `w5-institutional-authority-slots` | B | blocked |

### Open, all sections

| ID | Section | Standing read |
| --- | --- | --- |
| `DS11-PUBLIC-SIGNATURE-POPULATION` | A | open |
| `DS11-SCOPE-ADJUDICATION-RECORD` | A | open |
| `GY-DEF22` | B | open |
| `GY-PA1` | B | open |
| `calibration-report-fixture-blanket-fields` | F | open |
| `cg2-production-relation-gold-acceptance-unspecified` | B | open |
| `corr-wave-unowned-destinations` | A | open |
| `ds15-production-n13b-execution-handshake` | B | open |
| `ds15-semantic-epoch-qualification-authority` | A | open |
| `ds15-signed-v2-delegation-mandate-owner-authority` | A | open |
| `ds18-epoch-history-independent-holder-unappointed` | A | open |
| `ds18-epoch-predicate-policy-signer-unappointed` | A | open |
| `ds18-epoch-transition-signer-unappointed` | A | open |
| `education-importer-provenance-neither-inherited-nor-excluded` | A | open |
| `estimand-binding-strength-terms-unregistered` | A | open |
| `foundry-requirements-flat-manifest-consumer-unmeasured` | A | open |
| `foundry-ukraine-method-contract-consumer-residual` | A | open |
| `gy-builder-mechanisms-have-no-production-caller` | A | open |
| `gy-j-positive-evidence-admission-producer-has-no-owner` | A | open |
| `int-r2-ceiling-vocabulary-owners` | A | open |
| `merged-lanes-need-a-reissue-path-neither-lane-declared` | A | open |
| `pyproject-exceeds-its-declared-line-budget` | B | open |
| `s3-law-to-lever-correspondence-is-unverified` | A | open |
| `s3-r12-legal-knowledge-store-selects-an-unavailable-version` | A | open |
| `stale-worktree-registrations-collide-with-new-lane-names` | A | open |
| `transitive-runner-closure-unbound` | B | open |
| `udf-retained-source-schema-is-malformed-and-stays-ambiguous` | A | open |

The six foreign IDs (outside the 62-row remit) are `DS20-B B3 promotion CAS`, `DS20-B B5 PostgreSQL linearizability proofs`, `DS20-B Helm policy mirror`, `DS20-B-scorecard-provenance-producer-trust`, `aiohttp Fabric connector cleanup`, `worktree-tooling-gap`.

### Measurement boundaries

Pattern pass: P01/P02/P03 (slot, producer, bridge, consumer, surface); P05/P15/P32 (authority and admissibility); P29/P35/P37/P38 (behavior, complete denominators, predicate provenance, proxy failure); P36 (operational authority boundary); P39/P41 (proportional receipts and provenance of red). The discovered instrument anti-pattern is a column proxy that loses an explicit status when a code cell embeds `|`. The target pattern for this survey is a complete per-row, replayable property account with `measured`, `inferred`, or `unestablished` confidence. Missing links retain precise capability labels; there is no repair or status decision.

After this solitary reconciliation, ownership is disjoint: workstream A/C owns its 16 blocked rows; workstream B owns its 19 blocked rows; root owns all 27 open rows and integration. At most three workstreams. Root serializes git. Shared governed artifacts, browser/fixed-port and data-engine resources are not mutated or run concurrently. Read-only censuses can run concurrently.

The generated-ledger check was run alone, without `--write`:

```sh
env PYTHONPATH=. python3 tools/quality/validation/check_debt_ledger.py --check
```

**Exit 0.** This is ledger reconciliation, not a behavioral verdict on debts: all 45 selected pytest commands were `collection_host_unknown` because this interpreter is not bound to the project lockfile. No selector was executed by that check. Complete output is retained at `docs/superpowers/journals/debt-survey/denominator/raw/ledger-check.txt`, SHA-256 `e65a3e5843824c1fc9c32c8e8480ae2bfd2eb8c1282b20f1d59ebd6b8a288c6e`. Oversized/raw output is gitignored from the first commit.

## 2. Rows whose stated premise is false at this base

A false conjunct does not discharge a row. Some rows retain an initial assertion followed by a later correction; the table identifies the disproved assertion, without claiming its correction is newly discovered. The full accounts also report premises that hold and questions that remain unestablished. All source citations below resolve at `fc823071a7b6f2c9a573172aec3499ad6d138c0f`.

Replay keys use the exact command tables in [blocked A/C](2026-09-11-debt-nature-survey-blocked-ac.md), [blocked B](2026-09-11-debt-nature-survey-blocked-b.md), and [open](2026-09-11-debt-nature-survey-open.md). `AC:PUBLIC`, for example, is one named command, not an instruction to repeat an exploratory search. Each key has complete retained output and a hash in its workstream receipt index.

| Row(s) | Disproved or narrowed assertion; deciding measurement | Confidence / replay |
| --- | --- | --- |
| `ds10-global-case-index-producer-allocation`; `ds8-global-case-index` | The producer/provider are present and installed. `GlobalCaseIndexProducer.produce` persists/readbacks a canonical S2 inventory; default discovery consumes it. Its explicit S2/tenant/cell boundary does not establish unrestricted global recall. `src/polisyos/runtime/quality/global_case_index.py@fc823071a`. | Measured; AC:PUBLIC, AC:HTTP; B:`public-current`, `public-existing-tests`. |
| `ds10-public-decision-rendering`; `ds8-signed-public-decision-surface`; `ds8-public-case-publication` | Issue/verify/export routes and report rendering exist. `promoted_record: Literal[None]` prevents treating their signed verification report as a governed promoted decision. DS12 already owns the record half in an explicit scope act. `src/polisyos/runtime/http/routes/public_decisions.py@fc823071a`. | Measured; AC:PUBLIC, AC:ATLAS; B:`public-current`. |
| `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` | The signed owner-event producer, distinct bridge profile, append/readback and runtime monitor consumer exist; the old stub/profile mismatch is gone. Default positive deployment intake remains a separate question. `src/polisyos/scientist/evidence/claims/head_index.py@fc823071a`. | Measured; AC:CLAIM, AC:CLAIM-HTTP. |
| `DS11-EXTERNAL-A11Y-COUNTERSIGN` | The absence is not just an auditor: the external-certification posture arm fixes `evidence=None` and `SourceClaimState.BLOCKED` and no positive admission path is demonstrated. The local WCAG slice evidence does not fill it. | Measured source boundary; AC:A11Y, AC:PUBLIC. |
| `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` | Trust/documentation surfaces and an explicit DS12 ownership act exist. A complete retained-route scope/evidence census remains unestablished. | Measured partial delivery; AC:TS, AC:ATLAS. |
| `DS11-INHERITED-C13-PRINT-RECEIPT`; `ds10-c13-print-receipt-reissue` | Currentness alone is too narrow: the shared receipt/source-byte conjunction fails, and the richer reconciliation disposition meets a stricter schema than the old prose suggests. No fresh browser receipt was created. | Measured; AC:C13, AC:C13-TEST. |
| `ds18-positive-transition-production-unorchestrated`; `ds18-positive-transition-verification-producer-missing`; `GY-DEF23` | A real typed transition producer and exact history adapter exist. Unconditional nonreceipts, missing production composition and absent positive readers still prevent the admitted positive chain. | Measured; AC:EPOCH; B:`epoch-current`, `epoch-existing-tests`. |
| `ds5-waist-successors-routed-to-unscoped-slices`; `ds8-lex-clerk-authority-repair` | Several successor scopes are explicitly owned, and the Clerk/G6 mechanisms exist in part. The historical candidate-only assignment premise is false for the DS12/DS14 portions. Whole DS5 equivalence is still unestablished. | Measured scope acts; whole-DS5 inference bounded. AC:WAIST, AC:ATLAS, AC:TS. |
| `w5-institutional-authority-slots` | The four builders exist under delivered vocabulary, but their candidate-only results do not demonstrate engineering completion for the 18 distinct authority purposes. The B account enumerates every purpose, including unknown slots/callers. | Measured source; purpose counterfactuals separately inferred/unestablished. B:`w5`, `source-details`; open:`invocation-selection`. |
| `ds15-deterministic-admission-bundle-producer` | The signed bundle producer, readback and gateway mechanism exist. A fillable signing slot without a real production invocation is not an appointment-only capability. | Measured implementation; bridge inference bounded by AST/dispatch limits. B:`ds15`, `ds15-existing-tests`. |
| `ds15-fresh-positive-production-route` | Appointment-only framing misses a concrete positive receipt mismatch: the real admission CLI rejects the activated type with `acquisition_epoch_activation_consumer_not_established`. | Measured; B:`source-details`; open:`semantic-production-body`, `semantic-admission-tests`. |
| `ds15-int-r2-gap-acquisition-case-union` | Missing `GapAcquisitionCase` does not mean missing mechanism: delivered `GapShapeAssessment`, `AcquisitionType`, `NonDataRequest` and `NonDataReceipt` implement a candidate union. The crosswalk explicitly declines full equivalence. | Measured; B:`w5`, `ds15`, `w5-existing-tests`. |
| `gy-n12-epoch-predicate-policy-authority-unappointed`; `gy-n12-epoch-transition-signing-authority-unappointed` | The default missing-policy/signer refusal is real; a change in institutional standing alone does not compose the missing positive factory/reader paths. | Measured source predicates, inferred appointment counterfactual; B:`epoch-current`. |
| `first-promotion-candidate-with-complete-evidence`; `gy-promotion-obligations-scope-insufficient`; `GY-O0-NC-01` | Effect and measurement evaluators and writers now exist. The real value path still refuses, and the pilot promotion-safety evaluator remains mode-only. A candidate and a pilot safety/counter witness are different remaining quantities. | Measured; AC:PROMOTION; B:`promotion`. |
| `ds15-production-n13b-execution-handshake` | A tenant-bound `WorldBankWDIAcquisitionExecutionPort`, factory and service/job binding exist; the complete selected integration file passes. This refutes the old test-port-only production absence. | Measured; open:`ds15-authority-source`, `n13-binding-tests`. |
| `DS11-SCOPE-ADJUDICATION-RECORD` | The candidate artifact exists and its complete selected test file passes. It is explicitly forbidden from claiming authority; the positive resolver/lifecycle path is a separate residual. | Measured; open:`scope-source`, `scope-candidate-tests`. |
| `DS11-PUBLIC-SIGNATURE-POPULATION` | A real population inspection/refusal adapter exists. It still cannot emit a governed positive population, so “no adapter” and “no governed producer” are different claims. | Measured; open:`scope-source`, `population-tests`. |
| `ds18-epoch-history-independent-holder-unappointed`; `ds15-semantic-epoch-qualification-authority` | Their non-test CLI consumers now persist and reopen the negative receipt. The earlier missing negative bridge is discharged; positive custody/activation intake is not established by those tests. | Measured; open:`epoch-custody-tests`, `semantic-admission-tests`, `epoch-factory-body`. |
| `GY-DEF22` | The standing five-green acceptance premise fails in this replay: three of the exact five cases fail, two pass. The failed paths stop at `DigestPredicateMismatch`; no test or pin was repaired. | Measured host receipt; source/data provenance of failure not attributed. Open:`def22-tests`. |
| `s3-law-to-lever-correspondence-is-unverified` | The source-relative comparator/consumer and unrelated-law refusal are built and the selected behavioral cases pass. This does not provide independent legal gold or an authority-grade subject binding. | Measured; open:`correspondence-source`, `correspondence-tests`. |
| `cg2-production-relation-gold-acceptance-unspecified`; `GY-PA1` | Source discovery/replay and S8 value authorization are built. Current CG2 replay also exposes a structural-refusal assertion failure and missing proof-world CAS inputs, so “only a scientific appointment remains” does not establish engineering green. | Measured; open:`cg2-source-body`, `correspondence-source`, `cg2-refusal-tests`. |
| `gy-builder-mechanisms-have-no-production-caller` | Some builders have real non-test assurance/CLI roots under aliases; CB/ML authority operations have no resolved roots within the invocation checker's declared coverage. The blanket no-caller claim is false, and a blanket production-ready claim would also be unsupported. | Measured static paths; runtime unresolved. Open:`production-invocation`, `invocation-selection`, `builder-demand`. |
| `int-r2-ceiling-vocabulary-owners` | Eight software relations have named owners and implementations; five semantic vocabularies remain a different denominator. Estimand is concentrated around an owner; normative mechanisms span distinct packages. | Measured inventories/distribution; semantic equivalence inferred. Open:`vocabulary-distribution`, `vocabulary-semantic-source`, `demand-independent`. |
| `calibration-report-fixture-blanket-fields` | The located generic helper adds three fields outside the strict 15-field producer model. The producer rejects them; “ignored” describes neither strict admission nor the generic writer bypass. | Measured; open:`calibration.json`. |
| `pyproject-exceeds-its-declared-line-budget` | The pinned file is 307 physical lines, not the historical 305; the unchanged declared ceiling is 300. This is a size predicate, not a complexity measurement. | Measured; open:`pyproject-gate.json`. |

Two corrections use mutable local substrate and are deliberately **not** backdated to the source commit. The provision API selects an absent **column** `version_id`, not merely an unavailable version identity, against the actual 31-column local store (open:`lex-schema`). The complete current worktree set is 78 registrations including this survey, with 53 absent paths, not the row's 72 (open:`worktrees.json`). The full denominators and independent identity derivations are in those receipts. External UDF unreadability and missing Lex effect coordinates were reproduced; neither became a zero or an exclusion.

## 3. Blocked rows where appointment alone changes nothing

**19/35 blocked rows** have a measured implementation obstacle on the examined capability path that an appointment alone does not remove. This is an **inference about that path from measured source/behavior**, not a census of all possible deployed institutions or dynamically supplied implementations. **15/35** concern a different deciding variable; **1/35**, W5, has a mixed purpose-level result. These disjoint sets sum to the exact 35-row denominator and are independently aggregated from the two workstream assessments by:

```sh
python3 docs/superpowers/journals/debt-survey/final/verify_survey.py
```

The roughly fourteen-row hypothesis was not used to select or classify rows. The 19-row set below is neither a repair authorization nor a claim that every missing evidence artifact is buildable software. It establishes why an appointment is insufficient for the measured path; the full acceptance conditions remain in each row account.

| Exact row | Unbuilt or unconnected half on the measured path | Deciding replay |
| --- | --- | --- |
| `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` | The signed bridge works under explicit injection; sanctioned deployment owner-intake/configuration for the default positive path is not established. | AC:CLAIM, CLAIM-HTTP. |
| `DS11-EXTERNAL-A11Y-COUNTERSIGN` | External document/identity/currentness/scope admission and producer-to-posture bridge; the existing external-certification arm is fixed blocked/empty. | AC:A11Y. |
| `DS11-GROUNDED-PERFORMANCE` | Content-bound governed performance evidence and its public admission/projection; signed reports keep the promoted slot permanently empty. | AC:PUBLIC, PROMOTION. |
| `ds10-public-decision-rendering` | Governed promoted-record admission and its positive projection; report rendering already exists. | AC:PUBLIC, HTTP. |
| `ds8-public-case-publication` | DS12's governed record half and positive admission; documentary scope ownership is already present. | AC:PUBLIC, ATLAS. |
| `ds15-mandate-intake-has-no-registered-task` | Sanctioned production provider/intake of signed delegation and current mandate evidence; default route service has only the absent-provider refusal. | AC:MANDATE. |
| `ds18-positive-transition-production-unorchestrated` | Purpose-bound producer identity, positive emission/persistence and a real producer trigger; the delivered producer still returns its unconditional nonreceipt. | AC:EPOCH. |
| `ds18-positive-transition-verification-producer-missing` | Independently retained exact signed evidence, positive verifier and reconciliation into the consumer; nonreceipt verification alone does not supply them. | AC:EPOCH. |
| `eval-safety-promotion-authority-producer-missing` | Promotion-purpose safety producer/admission/consumer; the current evaluator branches on mode without consuming such authority evidence. | AC:PROMOTION; B:`promotion`. |
| `first-promotion-candidate-with-complete-evidence` | Authentic positive value/evidence production and persistence; the real default N8 path reaches `treatment_assignment_not_owner_derived`. | AC:PROMOTION. |
| `GY-DEF23` | Real positive transition composition before strict intake, followed by positive readback/consumption. | B:`epoch-current`, `epoch-existing-tests`. |
| `ds8-signed-public-decision-surface` | Promoted PUBLIC record producer/admission/lifecycle/projection; `Literal[None]` report slots cannot admit it. | B:`public-current`, `public-existing-tests`. |
| `ds15-deterministic-admission-bundle-producer` | Production construction/configuration and route-to-producer bridge. Its **fillable** signing slot and substantive producer exist; a source caller that consumes them is not established. | B:`ds15`, `ds15-existing-tests`; AST dispatch limit retained. |
| `ds15-fresh-positive-production-route` | Positive epoch admission/consumer adapters and same-instance re-entry; the CLI rejects the activated receipt type. | B:`source-details`; open:`semantic-admission-tests`. |
| `ds15-int-r2-gap-acquisition-case-union` | Full admitted union meanings and purpose-qualified demanding-gate admission/bridge. Existing persisted candidate receipts fix signer empty and authority false. | B:`w5`, `ds15`. |
| `gy-n12-epoch-predicate-policy-authority-unappointed` | Positive factory/reader composition and exact admitted policy/provenance/relation evidence; the factory always builds the unallocated policy path. | B:`epoch-current`. |
| `gy-n12-epoch-transition-signing-authority-unappointed` | Positive producer caller and projection readers around exact signature admission; current HTTP/Temporal paths refuse positive results. | B:`epoch-current`. |
| `gy-promotion-obligations-scope-insufficient` | Admitted promotion-safety predicate/consumer and full real candidate evidence; effect/measurement implementations already exist. | B:`promotion`. |
| `GY-O0-NC-01` | The real candidate and pilot-safety chains plus the retained counter/hash witness; no appointment manufactures that empirical conjunction. | B:`promotion`; AC:PROMOTION. |

The **15/35** other-variable rows are fully enumerated here so they cannot disappear from the count:

| Exact row | What actually decides the row; source/claim boundary |
| --- | --- |
| `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` | Complete retained-route scope and evidence contracts; no institutional slot is the blocker. AC:ATLAS, TS. |
| `DS11-INHERITED-C13-PRINT-RECEIPT` | Current C13 bytes/receipt and admissible reconciliation. AC:C13. |
| `ds10-c13-print-receipt-reissue` | The same C13 conjunction. AC:C13. |
| `ds10-global-case-index-producer-allocation` | Bounded S2 inventory chain already exists; wider demanded scope remains distinct. AC:PUBLIC. |
| `ds5-waist-successors-routed-to-unscoped-slices` | Scope assignment and semantic adequacy across heterogeneous presentation issuers. AC:WAIST, ATLAS. |
| `ds8-lex-clerk-authority-repair` | G6-to-Clerk session/audit/loss semantics and the real consuming path. AC:TS, ATLAS. |
| `GY-GAP2` | Admissible family risk-composition scope and its evidence chain. B:`gaps`. |
| `GY-GAP3` | Exact controlled-release family custody; an equivalent built chain remains unestablished. B:`gaps`, `source-details`. |
| `GY-GAP5` | Canonical complete production-run enumeration and Board bridge. B:`gaps`, `source-details`. |
| `GY-GAP6` | Owner-admitted per-row acquisition movement and chronology. B:`gaps`, `source-details`. |
| `ds15-gy-gap6-evidence-register-closure` | The same movement admission, distinct from receipt supply or a register action. B:`ds15`, `gaps`. |
| `ds15-numeric-voi-metric-residual-granularity` | Content-bound metric-level value/cost and owner-to-residual relation; interim ranking is not VOI. B:`growth`. |
| `ds8-global-case-index` | The same already-built bounded S2 inventory, not unrestricted global recall. B:`public-current`. |
| `gy-n12-epoch-current-decision-lineage-carrier-unallocated` | Post-N9 packet handoff/currentness lookup and exact lineage consumer. B:`epoch-current`, `lineage`. |
| `gy-n12-lex-amendment-valid-effect-carrier` | Complete owner-established effect coordinates or explicit member-level adjudication. The source refusal reader is built; missing external evidence is **not itself proof of missing engineering**. B:`lex`, `lex-current-rows-v2`. |

The remaining **1/35** is `w5-institutional-authority-slots`. Its 18-purpose B table distinguishes fixed candidate ceilings and missing callers from purpose-specific chains that could not be established. At least some positive authority intake/consumer work is missing, but no single whole-row appointment counterfactual is established. Unknown INT-R5, operational-outcome and diagnosis-authority paths remain named. This mixed row cannot be promoted into either a universal institutional-only or universal engineering-only conclusion.

## 4. Genuinely institutional blocked rows

**0 established / 35 examined** meet the full conjunction **named source slot + reachable non-test refusal + complete engineering for the demanded capability + an appointment/admitted institutional evidence that can affect that existing path**. This is an evidence result, **not a measurement that there are zero genuinely institutional debts**. Unknown complete paths remain in §8; fixed negative types, test-only injection and a missing positive caller cannot prove the conjunction.

The closest positive controls are reported explicitly rather than treating every refusal as a defect:

| Row/control | What is genuinely built | What prevents the full institutional-only finding |
| --- | --- | --- |
| `ds15-deterministic-admission-bundle-producer` | A fillable signing slot, signed bundle producer, exact verification/persist/readback and gateway contract. | Production caller/configuration bridge not established; this is stronger than contract-only but weaker than reachable institutional intake. B:`ds15`, `ds15-existing-tests`. |
| `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` | Real signed bridge, persisted lifecycle effect, HTTP consumption and negative refusal. | Sanctioned deployment intake of positive owner evidence is not established by the injected test; default absence and the test's positive are kept distinct. AC:CLAIM, CLAIM-HTTP. |
| `gy-n12-epoch-predicate-policy-authority-unappointed`; `gy-n12-epoch-transition-signing-authority-unappointed` | Named purpose-specific refusals, exact policy/history adapters and signature verification interface. | Fixed production factories and missing positive reader composition remain. B:`epoch-current`. |
| `gy-n12-lex-amendment-valid-effect-carrier` | Canonical reader refuses unknown effect coordinates without substituting transaction time. | It is an external evidence/adjudication problem; no whole-chain institutional appointment-only conclusion follows from reading the database. B:`lex`, `lex-current-rows-v2`. |
| `ds10-global-case-index-producer-allocation`; `ds8-global-case-index` | Complete bounded S2 producer → persisted snapshot/owner receipt → installed provider → tested consumer. | These are **2/35 complete bounded engineering accounts**, and neither requires an institutional appointment for that purpose. They are not counted as institutional positives. AC:PUBLIC, HTTP; B:`public-current`. |

The user's two worked examples remain useful controls outside this blocked denominator: open `ds18-epoch-history-independent-holder-unappointed` and `ds15-semantic-epoch-qualification-authority` now have real non-test negative bridges with persisted readback. Their row accounts explicitly affirm that delivery. They also distinguish the narrower negative-observation proof from positive custody/activation intake; no status or appointment is decided here.

## 5. Rows blocked on allocation

The class is **no assigned execution owner for the demanded capability**. It is not “engineering remains”, “a standalone plan filename is absent”, “the task is not currently dispatched”, or “an institution is unappointed”. With that property, the three supplied candidate-owner examples do not reproduce as three established unallocated debts:

| Supplied member | Current measured scope result | Confidence / replay |
| --- | --- | --- |
| `ds8-public-case-publication` | The Atlas master explicitly lists the exact debt under DS12's **Debt rows this slice must close** act and makes DS12 the owner without a separate slice plan. Positive record engineering remains. | Measured; AC:ATLAS. |
| `ds8-lex-clerk-authority-repair` | DS14's inherited-obligation act places the named Clerk producer/bridge/strangle work in executable scope and adjudicates its Lex halves. The old candidate-only scope premise is false. | Measured documentary scope; positive consuming path remains unestablished. AC:ATLAS, TS. |
| `ds5-waist-successors-routed-to-unscoped-slices` | DS12/DS14 explicitly own their presentation groups and DS18 covers freshness; equivalent assignment of DS15's generated promotion-union/private-issuer property was not established. | Mixed: measured partial assignment, **unestablished whole-row allocation**. AC:WAIST, ATLAS. |

Across the full **35 blocked rows**, the measured assessment partition is **9 no longer shown as awaiting engineering allocation**, **3 inferred allocation candidates**, **23 unestablished**. The **confirmed unallocated count is 0/35**, meaning no complete current-owner-absence proof was established; it is not a claim that no row is unallocated. The actual class size therefore remains **unestablished**, rather than being reported as either three or twenty-six. The exact partition is enumerated by `final/verify_survey.py`; each unknown is named again in §8.

The **3/35 inferred candidates** are `ds18-positive-transition-production-unorchestrated`, `ds18-positive-transition-verification-producer-missing`, and `eval-safety-promotion-authority-producer-missing`. Their current missing positive producers/bridges are established; an equivalent assigned purpose-specific build owner remains unestablished. That is why their allocation finding is an inference, not a measurement of all current appointments or scopes.

The **9/35 measured counterexamples** are `DS11-FULL-TRUST-CENTER-AND-DOCS-IA`, `DS11-GROUNDED-PERFORMANCE`, `DS11-INHERITED-C13-PRINT-RECEIPT`, `ds10-c13-print-receipt-reissue`, `ds10-global-case-index-producer-allocation`, `ds10-public-decision-rendering`, `ds8-public-case-publication`, `ds8-lex-clerk-authority-repair`, and `ds8-global-case-index`. Existing scoped ownership or already-built bounded capability defeats the allocation-only premise. Their independent surface/evidence obligations survive.

Documentary allocation and parser recognition remain separate facts. The Atlas body act exists; the current slice-plan checker does not consume that act. This survey makes neither the parser nor the register an authority over the act and appoints nobody.

## 6. Candidate reductions

These are comparisons of deciding properties. No pair is merged and no owner is appointed. A shared upstream absence is explicitly weaker than an identical debt.

| Candidate members | Shared deciding property | Distinguishing obligation / confidence / replay |
| --- | --- | --- |
| `DS11-INHERITED-C13-PRINT-RECEIPT` + `ds10-c13-print-receipt-reissue` | The same C13 evidence/current-source-byte and schema-admissible reconciliation conjunction; same DS6 receipt holder. | Exact reduction candidate, measured shared inputs/predicate. Consumer placement differs, not the currentness test. AC:C13, C13-TEST. |
| `ds10-global-case-index-producer-allocation` + `ds8-global-case-index` | Canonical S2 snapshot, verified owner receipt and installed case-discovery provider. | Measured same built chain. Full reduction depends on whether the demanded “global” scope is the bounded S2 inventory; unrestricted population authority is unestablished. AC:PUBLIC; B:`public-current`. |
| `GY-GAP6` + `ds15-gy-gap6-evidence-register-closure` | GY admits the exact per-row acquisition movement and its chronology; Cycle Board consumes it for the same case/cycle. | Candidate identity for movement-admission work. DS15 supply and a procedural register action are not this deciding property. B:`gaps`, `source-details`, `ds15`. |
| `gy-promotion-obligations-scope-insufficient` + `GY-O0-NC-01` | The same real field-pilot conjunction: promotable receipt, protected-pilot refusal, near miss, both exactly-once counters, unchanged safety core/hash. | Exact candidate on the recorded full signal. Repairing effect/measurement evaluators alone cannot discharge it. B:`promotion`; AC:PROMOTION. |
| `gy-n12-epoch-predicate-policy-authority-unappointed` + `ds18-epoch-predicate-policy-signer-unappointed` | Admitted purpose-specific policy/provenance/relation evidence for the same production query. | Inferred institution-purpose identity; exact appointment/selection-key equivalence not established. `ds15-semantic-epoch-qualification-authority` adds acquisition activation and is only a prerequisite overlap. B:`epoch-current`; open:`signer-body`, `semantic-production-body`. |
| `gy-n12-epoch-transition-signing-authority-unappointed` + `ds18-epoch-transition-signer-unappointed` | Distinct transition-purpose signature admitted for exact bytes, with independent producer identity evidence. | Inferred same institutional purpose; production emission/positive reader proofs remain separate. B:`epoch-current`; open:`signer-body`. |
| `ds8-public-case-publication` + `ds8-signed-public-decision-surface` + `ds10-public-decision-rendering` | Admitted governed PUBLIC record with custody-bound authority. | Partial reduction only. Publication admission, surface rendering and public verification retain their own consumer signals. DS11 population/performance cannot be merged into this property. AC:PUBLIC, ATLAS; B:`public-current`. |
| `ds18-positive-transition-production-unorchestrated` + `GY-DEF23` | Owner-derived positive transition production before strict intake. | Shared chain, not established full identity: DEF23 additionally decides strict admission; independent verification has another proof. AC:EPOCH; B:`epoch-current`. |
| `estimand-binding-strength-terms-unregistered` within `int-r2-ceiling-vocabulary-owners` | Registered strength ordering with versioned identity, justified edges and declared incomparability. | Constituent reduction, not equality with five semantic vocabularies or eight software relations. Open:`vocabulary-distribution`, `vocabulary-semantic-source`. |
| `cg2-production-relation-gold-acceptance-unspecified` within `GY-PA1` | Independently accepted proposal/reference relation evidence at the declared stratum. | Upstream conjunct only: PA1 adds S8 authorization/persistence/ranking and N8 consumption. Legal correspondence needs different gold and competent authority. Open:`cg2-source-body`, `correspondence-source`. |

A negative control is the requirements/Ukraine pair: one question is whether a flat manifest manufactures validity-looking evidence; the other is whether each actual method contract is executed by a workflow. Similar Foundry vocabulary does not give them the same predicate, holder or repair (open:`requirements.json`, `ukraine-key-reconciliation`). Likewise unreadable UDF bytes, missing Lex effect coordinates and the Lex provision API's absent column are three different data obligations.

## 7. Candidate classes and refuted prefix groupings

Class requires a shared mechanism, repair **and** holder. The matrix distinguishes an enabling prerequisite from the full discharge proof. Membership comes from the reconciled 62-row set; class judgments come from source/authority measurements above. Prefix totals are not accepted without enumerating the members.

| Proposed group and complete membership | Class result; mechanism and holder | What unblocks | What discharges |
| --- | --- | --- | --- |
| `ds15-*`: **9/62 live**, **6/35 blocked**: mandate-intake, deterministic-admission-bundle, fresh-positive-route, gy-gap6-evidence-register, numeric-voi, int-r2-union; **3/27 open**: production-n13b-handshake, semantic-epoch-qualification, signed-v2-delegation-mandate. IDs are expanded in §1. | **Refuted as one class.** The supplied seven is not the complete prefix set. Runtime execution, mandate authority, bundle signing, epoch activation, GY movement admission, metric VOI and candidate union semantics have distinct owners/objects. B:`ds15`, `growth`; AC:MANDATE; open:`ds15-authority-source`, `epoch-source`. | Each missing source of authority/data and its own bridge. A real execution port already exists; it does not supply a mandate or a movement record. | Separate same-instance execution, mandate/currentness, signed bundle, activation, per-row movement, numeric granularity and demanding-gate union proofs. |
| `gy-n12-*`: **4/35 blocked**: predicate-policy-authority, transition-signing-authority, current-decision-lineage-carrier, lex-amendment-valid-effect-carrier. | **Refuted.** Policy evidence, transition signature, packet lineage and legal effect coordinates are different mechanisms and holders. Generic chronology is reusable infrastructure. B:`epoch-current`, `lineage`, `lex-current-rows-v2`. | Policy/role evidence; positive readers; Scientist handoff; complete Lex effect evidence, respectively. | Exact policy query; exact signed bytes; current packet lineage; every legal amendment's evidence/adjudication. No single signer discharges four predicates. |
| `ds8-*`: **4/35 blocked**: public-case-publication, lex-clerk-authority-repair, signed-public-decision-surface, global-case-index. | **Refuted.** Public authority admission is shared by two members, while Clerk consumes G6 semantics and the index consumes canonical S2 bindings. AC:PUBLIC, TS, ATLAS; B:`public-current`. | Governed PUBLIC record; Clerk G6 bridge; bounded index is already installed. | Separate publication/verification, Clerk session/audit/loss, and complete bounded inventory proofs. |
| `GY-GAP2/3/5/6`: **4/35 blocked**, exactly those four IDs. | **Refuted.** Family risk composition, controlled release custody, complete production enumeration and per-row acquisition movement are different quantities. They may reuse chronology but have distinct consumers and ownership boundaries. B:`gaps`, `source-details`. | Admissible composition scope; release-family allocation; run owner enumeration; admitted movement family. | Respective family validity, non-narrowable release prefix, exhaustive run identities/heads, exact movement-to-deeper-terminal provenance. |
| `DS11-*` proposed blocked subset: **5/35** — claim-lifecycle, external-a11y, grounded-performance, inherited-C13, full-trust/docs. Two other DS11 rows are open and separately indexed in §1. | **Refuted.** Signed lifecycle custody, external a11y evidence, performance provenance, print currentness and retained-route scope have different mechanisms/holders. AC:CLAIM, A11Y, C13, TS, ATLAS. | Their own owner/evidence intake or missing bridge; renewed current bytes for C13. | Independent end-to-end lifecycle, countersign, performance, print/readiness and route-scope proofs. |
| `ds10-*`: **3/35 blocked** — public-decision-rendering, global-case-index-producer-allocation, c13-print-receipt-reissue. | **Refuted.** Promoted-record projection, bounded inventory and receipt currentness are unrelated mechanisms despite a shared lane name. AC:PUBLIC, C13. | Admitted record; existing index; current C13 receipt/disposition. | Each actual surface or inventory predicate independently. |
| `ds18-positive-transition-*`: **2/35 blocked** — production-unorchestrated and verification-producer-missing. | **Not one repair class established.** Shared transition chain, separate emitter and independent verifier roles. AC:EPOCH. | Purpose-qualified signer/identity and production composition can enable both. | One proof of owner-derived emission/persistence; another proof of independent exact verification/reconciliation. One green test cannot substitute for the other. |
| Promotion proposal: **3/35 blocked** — first-promotion-candidate-with-complete-evidence, eval-safety-promotion-authority-producer-missing, gy-promotion-obligations-scope-insufficient. | **Refuted as whole-row identity/class.** Complete candidate production, purpose-authoritative safety predicate, and full field-pilot cross-gate witness have different holders/proofs. GY-O0-NC-01 is an additional exact-signal reduction candidate in §6, not a silently added group member. AC:PROMOTION; B:`promotion`. | Authentic value/effect/measurement/independence inputs and separately admitted pilot-safety semantics. | Data-only candidate readiness; promotion-purpose safety admission; full pilot refusal/near-miss/counter/hash witness, respectively. |

There are narrower candidate classes with measured mechanisms. The C13 pair shares one receipt-currentness mechanism and holder, but still owes schema-admissible reconciliation and the consumer's actual print/readiness check. The S2 index pair shares one installed producer/provider chain; full reduction depends on agreed population scope. The movement pair shares the exact owner-admitted per-row artifact, but supply, chronology and Board consumption each remain proof obligations. The W5 builders share a **candidate ceiling**, which explains their honest refusals; their 18 authority purposes do not share a repair and holder (B's complete purpose table).

Distribution changes the interpretation of the vocabulary rows. Across the complete **2,653 source-Python files**, literal `estimand` appears in **176 files**, distributed Foundry 105, IR 36, Runtime 19, Scientist 12, Data Forge 2, Fabric 2; canonical AST definitions corroborate the definitional concentration. Literal `normative` appears in **141 files**, distributed Runtime 38, Data Forge 36, Scientist 35, Lex 9, Core 6, IR 6, Evidence/Fabric/Foundry/PDC 2 each, DataRequirement/LegalRequirement/PolicyGrammar 1 each. These are matching-file distributions over the enumerated source denominator, not token totals or distinct capability counts. Real normative AST types and callers refute a prose-only reading, while several purposes prevent assuming one universal authority object. Zero literal `write_operation` or `assurance_level` hits in that same source denominator do not establish absent demand: the complete **683-document** active-plan/reference/research/withheld corpus contains relevant demand and delivered crosswalk vocabulary. Replay: open:`vocabulary-distribution`, `vocabulary-semantic-source`, `demand-independent`.

An instrument boundary is itself measured. `validate_slice_scope_obligations` reads slice-plan YAML frontmatter and `atlas_residual_inputs`, and skips absent target plans. It does not read the master plan's DS12/DS14 body ownership acts. The manifest's `candidate_only` / `closure_effect: none` prevents treating checker visibility as allocation authority. AC:ATLAS reads the parser's operational body and the scope act. Likewise the promotion reissue parser recomputes an admitted comparison plan from payload/receipts; prose proposing a fifth transition is not an input that authorizes it (open:`reissue-source`, `promotion-reissue-check`).

Authority readings preserve their boundary. The identity-and-custody ratification, `docs/system-design-decisions/policyos-identity-and-custody-boundary.md@fc823071a`, §9 item 6 keeps legal-subject minting with GY-O0 inside PolicyOS; its prohibited uses prevent deriving a jurisdiction-specific legal conclusion or a capability claim from the document (open:`identity-authority-boundary`). INT-R2 handoff §1.1/§1.2 forbids appointment/implementation authorization and production-gate opening; W5-K01 governs non-substitution. These are scope warrants, not runtime receipts.

## 8. What could not be established

The complete 62-row unknowns denominator is below. “Unestablished” does not reverse a source measurement and is never used as zero, absence, closure or an excluded member. The workstream beside each ID contains its exact commands, retained outputs, source citations and per-finding confidence.

| Exact row | Workstream | Unestablished quantity |
| --- | --- | --- |
| `DS11-CLAIM-LIFECYCLE-ORCHESTRATION` | blocked-ac | sanctioned positive deployment owner intake |
| `DS11-EXTERNAL-A11Y-COUNTERSIGN` | blocked-ac | positive external evidence admission implementation |
| `DS11-FULL-TRUST-CENTER-AND-DOCS-IA` | blocked-ac | complete retained-route residual population |
| `DS11-GROUNDED-PERFORMANCE` | blocked-ac | governed receipt population; positive public-performance bridge |
| `DS11-INHERITED-C13-PRINT-RECEIPT` | blocked-ac | current browser captures; full disposition error set |
| `DS11-PUBLIC-SIGNATURE-POPULATION` | open | any actual governed member and full deployed worker execution. These report tests cannot supply either. |
| `DS11-SCOPE-ADJUDICATION-RECORD` | open | that authority-grade source producer, its production caller and a scope decision advancing the actual claim head. The candidate tests provide no such receipt. |
| `GY-DEF22` | open | complete P41 input disjointness and exact slice-base replay, hence no inherited-red attribution; no claim that the mismatch was introduced by this survey or by a named earlier lane. |
| `GY-DEF23` | blocked-b | formal signing/identity appointments; production positive transition population |
| `GY-GAP2` | blocked-b | research result and admissible numerical claim; full family owner allocation |
| `GY-GAP3` | blocked-b | equivalent implementation under other vocabulary; external-copy denominator; executing owner allocation |
| `GY-GAP5` | blocked-b | complete production run population; canonical production-enumeration allocation |
| `GY-GAP6` | blocked-b | production movement population; executing successor allocation |
| `GY-O0-NC-01` | blocked-b | complete production receipt population; actual counter/hash witness; formal promotion-safety institution |
| `GY-PA1` | open | actual production value-ready receipt population, independent relation acceptance and complete positive S8→N8→promotion behavior. The current negative source-discovery type cannot be counted as a positive producer. |
| `calibration-report-fixture-blanket-fields` | open | full HTTP fixture persistence/replay and every other kind's validity. |
| `cg2-production-relation-gold-acceptance-unspecified` | open | any real admitted positive relation population, independent gold or correctness bound. |
| `corr-wave-unowned-destinations` | open | specific §5 classifications of B1/B2, valid appointer identities and whether any external source can meet the required semantic evidence contract. |
| `ds10-c13-print-receipt-reissue` | blocked-ac | current browser captures; full disposition error set |
| `ds10-global-case-index-producer-allocation` | blocked-ac | wider public global-case population is outside demonstrated purpose |
| `ds10-public-decision-rendering` | blocked-ac | positive promoted-record contract and public admission |
| `ds15-deterministic-admission-bundle-producer` | blocked-b | formal signer appointment; production invocation population |
| `ds15-fresh-positive-production-route` | blocked-b | complete current production route population; actual live positive instance; formal epoch institution |
| `ds15-gy-gap6-evidence-register-closure` | blocked-b | full production receipt population; register action is outside this survey |
| `ds15-int-r2-gap-acquisition-case-union` | blocked-b | full union ratification scope; real demanding authority caller; institutional availability across eight types |
| `ds15-mandate-intake-has-no-registered-task` | blocked-ac | equivalent active successor allocation; positive deployment provider |
| `ds15-numeric-voi-metric-residual-granularity` | blocked-b | future numerical scope ruling; current owner allocation for all input families |
| `ds15-production-n13b-execution-handshake` | open | a positive production request using real external mandate evidence and an actual external fetch. Test-port results are not reclassified as that production instance. |
| `ds15-semantic-epoch-qualification-authority` | open | a production appointment loader and a positive CLI activation consumer; no repair is made. |
| `ds15-signed-v2-delegation-mandate-owner-authority` | open | real signed external delegation, its production provider and a live current-mandate positive run. No name census is promoted to a repository-wide semantic absence claim. |
| `ds18-epoch-history-independent-holder-unappointed` | open | a live positive appointment-to-factory path and external holder independence. The green negative tests do not establish either. |
| `ds18-epoch-predicate-policy-signer-unappointed` | open | appointment validity, policy adequacy and a production positive route. No status inference follows. |
| `ds18-epoch-transition-signer-unappointed` | open | a live positive appointed signer and exact equivalence of the two appointment scopes. A typed negative alone does not establish engineering completion. |
| `ds18-positive-transition-production-unorchestrated` | blocked-ac | non-test dynamic producer trigger; sanctioned identity-carrier admission; equivalent assigned purpose-specific positive build owner |
| `ds18-positive-transition-verification-producer-missing` | blocked-ac | configured positive verifier; equivalent assigned purpose-specific positive build owner |
| `ds5-waist-successors-routed-to-unscoped-slices` | blocked-ac | semantic adequacy of each delivered issuer at historical sites; equivalent assignment of DS15 generated promotion-union/private-issuer property |
| `ds8-global-case-index` | blocked-b | global population recall beyond S2; final demanded scope equivalence |
| `ds8-lex-clerk-authority-repair` | blocked-ac | positive end-to-end G6 Clerk projection |
| `ds8-public-case-publication` | blocked-ac | governed published receipt population; positive record-half engineering |
| `ds8-signed-public-decision-surface` | blocked-b | promoted authority chain scope/allocation; complete public record population |
| `education-importer-provenance-neither-inherited-nor-excluded` | open | that historical full input set, exact fresh replay at `3d572c146`, and whether its external data match those now mounted. Therefore no inherited attribution or test exclusion is made. The explicit unknown is retained instead of manufactured as zero. |
| `estimand-binding-strength-terms-unregistered` | open | equivalence of an existing delivered ordering under another vocabulary; no universal absence is inferred merely from the crosswalk's empty entry. |
| `eval-safety-promotion-authority-producer-missing` | blocked-ac | appointed purpose-specific authority; positive promotion contract; equivalent assigned purpose-specific positive build owner |
| `first-promotion-candidate-with-complete-evidence` | blocked-ac | current real receipt population; authentic upstream data adequacy |
| `foundry-requirements-flat-manifest-consumer-unmeasured` | open | full production input arrival, downstream authority effect and equivalence to an existing canonical owner. No helper result is promoted to that claim. |
| `foundry-ukraine-method-contract-consumer-residual` | open | actual production requests for the twelve non-panel keys and their full independent consumer enumeration. This survey does not convert one panel witness into thirteen execution receipts. |
| `gy-builder-mechanisms-have-no-production-caller` | open | dynamic callback and receiver routes outside the static model, and real operator/rendition production runs. No `uninvoked` string alone establishes universal source absence. |
| `gy-j-positive-evidence-admission-producer-has-no-owner` | open | such an allocated positive scientific owner, current source adequacy, and a fresh canonical production run. The fixed negative path is measured, not used to claim that all possible evidence elsewhere is inadequate. |
| `gy-n12-epoch-current-decision-lineage-carrier-unallocated` | blocked-b | equivalent handoff under other fields; executing successor allocation |
| `gy-n12-epoch-predicate-policy-authority-unappointed` | blocked-b | formal appointment/competence; current complete admission population |
| `gy-n12-epoch-transition-signing-authority-unappointed` | blocked-b | formal signing/identity appointments; positive transition population |
| `gy-n12-lex-amendment-valid-effect-carrier` | blocked-b | complete owner adjudication; source-commit-time database population; formal adjudication authority |
| `gy-promotion-obligations-scope-insufficient` | blocked-b | complete production receipt population; actual field-pilot counter/hash witness; formal promotion-safety institution |
| `int-r2-ceiling-vocabulary-owners` | open | whether any existing normative owner supplies the exact requested ceiling relation and who can authorize/register each value. |
| `merged-lanes-need-a-reissue-path-neither-lane-declared` | open | admissibility of any fifth transition, proof that any particular pair composes, and full P41 introducing-lane attribution. No transition is decided. |
| `pyproject-exceeds-its-declared-line-budget` | open | the maintainability effect of any particular extraction and historical attribution of the excess; no historical replay is claimed. |
| `s3-law-to-lever-correspondence-is-unverified` | open | independent positive legal subject membership and adjudication, current production correctness or any calibration bound. Synthetic positives and constructed negatives do not supply those quantities. |
| `s3-r12-legal-knowledge-store-selects-an-unavailable-version` | open | the complete call-site population's dynamic exposure, other deployed database schemas, and these untracked database bytes at the historical Git base. |
| `stale-worktree-registrations-collide-with-new-lane-names` | open | the row's historical 43 merged-branch count and universal compliance by future prompts. No registration was pruned. |
| `transitive-runner-closure-unbound` | open | repository-wide absence of every possible out-of-band attestation, current full runner closure and an executed mutation witness. No stale whole-tree file total is carried as proof. This bounded source account does not close the row. |
| `udf-retained-source-schema-is-malformed-and-stays-ambiguous` | open | the entire retained portfolio extraction, and whether these untracked bytes equal the historical bytes at the Git base. No historical 6,417-file total is adopted as current. |
| `w5-institutional-authority-slots` | blocked-b | INT-R5 exact source slots/callers; R3-Q08 operational outcome chain; R4-Q08 diagnosis authority chain; formal appointments; dynamic runtime invocation beyond checker coverage |

The additional status-ambiguous ID, `extraction-ask-offers-six-of-ten-evidence-classes`, remains explicitly retained outside the 62-row live set. The survey does not silently resolve its checker/whole-cell status disagreement.

### Gate and environment boundaries

The borrowed Python environment is explicitly named in every behavioral command. Source imports bind to this worktree; an isolation-local lock-bound environment could not be provisioned offline because `jaxlib==0.8.2` was not cached. The canonical external data were accessed for read-only use; their current content is not presumed to equal data at the source commit. TypeScript AST tools ran only after `corepack pnpm install --frozen-lockfile` established workspace links.

No failed behavioral receipt is labelled inherited. GY-DEF22, education importer, CG2, C13 and promotion reissue retain their actual failures and stated scope. The exact earlier slice-base/input-disjointness proof required by P41 was not established. Positive tests do not waive failing selectors or substitute for positive institutions.

CG2's complete 31-case identity denominator is independently collected in `final/raw/cg2-case-denominator.txt` (SHA-256 `3a9b10d4dc8324dcf8942e270f54665392d04a85d22aec5f482e0aa02e4e680b`) by:

```sh
env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/runtime/quality/test_production_grounding_calibration.py tests/unit/runtime/quality/test_grounding_calibration.py --collect-only -o addopts= -q
```

The execution receipt is exit 1, 20 passed and 11 failed against that complete set. One failure reaches a structural-refusal assertion; ten fail before their assertions on missing local proof-world CAS input. Neither class is declared inherited or excluded.

The first architecture guardrail invocation returned **1 / FAILED**, not UNRUN. Its complete output is `docs/superpowers/journals/debt-survey/final/raw/architecture-guardrails.txt@sha256:9688845c41ca5a74b116ff46bb00f2b70e87ab2efe6b1e05224ef9a5bcd798f3`. It reported deep-import drift and generated-output mismatches; two output probes also observed concurrent survey writes outside their assigned scratch. That run is a measured contaminated attempt, not the final frozen-tree verdict. Its suggestion of `guardrails sync` is recorded as a finding; sync was not run.

The frozen-tree replay at survey commit `d34c5eab6` returned **1 / FAILED** in **469.424 seconds**, within the explicit **900-second** timeout selected after the 458.780-second first measurement. It did **not** return 2 / UNRUN. Exact gate command:

```sh
env PYTHONPATH=src:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m tools.cli architecture guardrails check
```

Complete output: `docs/superpowers/journals/debt-survey/final/raw/architecture-guardrails-frozen.txt@sha256:71bb66c5c46c7d22ee1da84bb97743604c729f506ae5c7022c7120a988b31275`. The output-probe concurrent-write findings disappear. The remaining findings are deep-import baseline drift/creep, the runtime OpenAPI snapshot mismatch, and the trust-claim-posture generated-output mismatch. They are reported exactly as observed, without an inherited attribution or baseline acceptance. No `guardrails sync` or generated-artifact rewrite was performed. The command explicitly excludes the standalone Atlas status-retirement inventory check; no verdict for that separate check is implied.

The final survey audit command above checks exact row/headings/assessment/unknown identities, two independent blocked-assessment aggregations, source citation existence at the cited SHA, complete retained-output hashes, ignored raw output, and the complete allowed change set. It also reconciles CG2's collected case definitions against both AST traversals, including async definitions. The initial audit parser missed a section suffix and W5's group heading; those failed development receipts are retained and were corrected before accepting the complete identity result.

The failure/repair register was re-read at closeout. The final product source remains `fc823071a`; only these four survey specs and their journal instruments/receipts differ. The register, ledger, plans, source, tests and governed artifacts are unchanged. Work is preserved through ordinary commits on `codex/debt-nature-survey`; no push or other branch operation was performed.

Delivery audit: **exit 0**; complete output `docs/superpowers/journals/debt-survey/final/raw/delivery-audit.txt@sha256:b0ac8ca2fd2583acedde0ce07cd85913b6c33f4272584cf9fe8cc5a240183cde`. Final denominator replay: **exit 0**, unchanged identity digest; complete output `docs/superpowers/journals/debt-survey/final/raw/denominator-replay.txt@sha256:87759f3ef32d3840f67ec64d3a4d569661c716610f30190fd38398d406a16c58`. Both exact commands are printed above and indexed with their working directory in `docs/superpowers/journals/debt-survey/final/receipts.json`. “Current” external data and Git-registration measurements mean the state at their recorded replay, not immutable data at the source commit.
