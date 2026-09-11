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

Pending the indexed row measurements; no judgement is recorded yet.

## 3. Blocked rows where appointment alone changes nothing

Pending the indexed row measurements; no judgement is recorded yet.

## 4. Genuinely institutional blocked rows

Pending the indexed row measurements; no judgement is recorded yet.

## 5. Rows blocked on allocation

Pending the indexed row measurements; no judgement is recorded yet.

## 6. Candidate reductions

Pending the indexed row measurements; no judgement is recorded yet.

## 7. Candidate classes and refuted prefix groupings

Pending the indexed row measurements; no judgement is recorded yet.

## 8. What could not be established

Pending the indexed row measurements; no judgement is recorded yet.
