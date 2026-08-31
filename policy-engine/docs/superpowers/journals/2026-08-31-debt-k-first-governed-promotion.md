# Task K — First Governed Promotion Execution Journal

## Standing

- Worktree: `.worktrees/debt-k-first-governed-promotion`
- Attached branch: `refs/heads/codex/debt-k-first-governed-promotion`
- Slice base: `83f69c3c00cba451a52a71f03c3a35ee94b40552`
- CG1 implementation commit: `5a5fa5716`
- N9 comparison reissue commit: `cbee85fea`
- Scope denominator: the four rows named by Task K. Protected architect
  registers and plans remained read-only.
- Terminal arithmetic: **4 = 2 closed + 2 blocked + 0 open**.

## Pattern pass

- Relevant patterns: `P05`, `P07`, `P29`, `P31`, `P32`, `P33`, `P35`,
  `P37`, and `P38`.
- Existing anti-patterns found: the generated N9 comparison companion was
  pinned to a v3 receipt manifest after the live receipt reached v6; the four
  manifest readers separately enumerated only a subset of readable receipt
  epochs; CG1 atom identity included insertion order that its public reference
  identity and equality excluded.
- Target correct pattern: one producer-owned registry for every readable
  promotion epoch, a one-transition v3-to-v6 reissue predicate over exactly
  three canonical receipt pointers, and CG1 atom identity canonicalized from
  reference content.
- Capability labels before repair: the two closure-signal rows were
  `producer_missing` at the required real-receipt instance; the comparison row
  was `verification_missing`; the CG1 row was `semantic_test_missing` plus an
  order-sensitive identity defect.
- Acceptance signal: the exact four-cell census decides whether promotion may
  be attempted; the governed N9 checker exits 0; its corruption probe reaches
  the healthy red terminal; retained v3 and v5 receipts remain readable but
  cannot regain current authority; sorting a persisted CG1 edge mapping leaves
  atom and certificate identities unchanged.

## Four-cell refusal table

The deciding command, run before source edits and again after both
implementation commits, was:

```bash
uv run --extra test pytest -q -s --tb=short \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9
```

Both runs exited `0`. Counts are separated as `full refusals` and
`scope-only refusals`; no number below is inferred from a sampled receipt.

| Request class | Lane | Before full | Before scope-only | After full | After scope-only | Refusal reasons after |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| data-only | production | 3 | 0 | 3 | 0 | `effect:unknown`, `calibration:single_obligation_fail`, `data:single_obligation_fail` |
| data-only | contract testing | 3 | 0 | 3 | 0 | `effect:unknown`, `calibration:single_obligation_fail`, `data:single_obligation_fail` |
| field-pilot | production | 4 | 1 | 4 | 1 | the data-only three plus `eval_safety:scope_insufficient` |
| field-pilot | contract testing | 3 | 0 | 3 | 0 | `effect:unknown`, `calibration:single_obligation_fail`, `data:single_obligation_fail` |

The data-only production full-refusal set is non-empty. Task K stop rule 3
therefore fired before any promotion attempt. No receipt was constructed or
injected, and no reconciled counter was exercised.

## Command ledger

| Stage | Deciding command | Exit | Decisive output |
| --- | --- | ---: | --- |
| branch preflight | `git status -sb && git symbolic-ref -q HEAD && git rev-parse HEAD` | 0 | clean attached task branch at the declared slice base |
| governed checker before | `JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers --extra test python tools/quality/validation/check_layer3_gy_promotion_contract.py --check --output-format json` | 1 | `promotion_comparison_admission_manifest_drift` |
| CG1 red falsifier | `uv run --extra test pytest -q --tb=short tests/unit/runtime/quality/test_grounding_relation.py::test_certificate_identity_is_invariant_to_persisted_edge_mapping_order` | 1 | equal references produced different candidate atom IDs |
| CG1 focused green | the same exact node after canonicalizing `edge_scope` | 0 | one passed; sorted persisted mapping preserved atom and certificate identities |
| CG1 owned file | `uv run --extra test pytest -q --tb=short tests/unit/runtime/quality/test_grounding_relation.py` | 0 | `13 passed` |
| controlled reissue | `JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers --extra test python tools/quality/validation/check_layer3_gy_promotion_contract.py --write --output-format json` | 0 | only `architecture/policy_design_case/layer3_gy_promotion_contract.json` reissued |
| governed checker after | the governed checker command above | 0 | `status=pass`, zero issues |
| corrupt-field drift | the checker with `--corrupt-field-drift-check --output-format json` | 1, healthy | `corrupt_field_drift_detected` after deleting the conditionality clause |
| v5 history | exact v5 round-trip and comparison-refusal nodes in `test_promotion_sequence.py` | 0 | two passed; 48,568 bytes and pinned SHA-256 retained; current authority and historical comparison both refused |
| N11 row denominator | `uv run ... pytest -q tests/repo_quality/tools/test_layer3_gy_promotion_contract.py::test_rederived_n9_contract_accounts_fixed_time_refusal_through_n11` | 0 | one passed; exactly calibration and data rows, both preflight refusals |
| four-cell replay after | exact census command above | 0 | the four rows are byte-for-byte count-equivalent to the before table |
| safety source integrity | current and base SHA-256 over `evaluation_safety.py` | 0 | both `22edd5916472bbe5e186c2a0091ab2e65c40d3b06d94c72cbefaaafdb4d6537c` |
| lint | `uv run --extra lint python -m ruff check` over the seven changed Python files | 0 | all checks passed |
| format | `uv run --extra lint python -m ruff format --check` over the seven changed Python files | 0 | all seven files already formatted |

## Historical registry and artifact readback

The complete registry-file denominator is these four files:

1. `tools/quality/validation/check_layer3_gy_promotion_contract.py`
2. `tools/quality/validation/check_layer3_gy_generation_cycle_contract.py`
3. `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
4. `tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py`

The exact census was:

```bash
rg -n "canonical_promotion_verification_comparison_owner_rule_registry\(\)" \
  tools/quality/validation/check_layer3_gy_promotion_contract.py \
  tools/quality/validation/check_layer3_gy_generation_cycle_contract.py \
  tools/quality/validation/check_layer3_gy_second_domain_pack.py \
  tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py
```

It found **7 calls across all 4 files**: 2, 2, 2, and 1 respectively. The
single owner registry contains the legacy plus v3, v4, v5, and current v6
comparison projectors. A behavioral replay applied a real retained v3
verification receipt through all four registries. The promotion, generation,
second-domain, and depth registries all accepted it. Actual persisted
promotion-pointer counts were 3 current pointers in N9, 2 historical pointers
in N6, 4 historical pointers in the second-domain trace, and 0 in the depth
manifest; the depth registry was therefore exercised with that real receipt at
a synthetic comparison pointer without writing an artifact or changing
authority.

Generated N9 readback after the owner writer:

- bytes: `187735`
- receipt epochs: v6, v6, v6 at the three canonical pointers
- comparison projection schema: `policyos.gy.comparison_projection.v2`
- comparison rule: `policyos.gy.non_authority_verification.v3`
- owner projection rule: `canonical_promotion_receipt_verification_projection.v5`
- contract hash: `sha256:fb6f68900447d62c06ad9ad87017e25c5cbfa7fac5d69093ba909880630589ab`
- comparison hash: `sha256:9841ae3f3c32e97a6d0b4aeed947a977a2f563ab15ae950b80affbe61e0f1fed`

The authentic v5 fixture remains exactly 48,568 bytes with SHA-256
`dba4a1ab7f374ea04044b171b0e163c6b0b1390089197fc64f96c2f0e86983c9`.
It parses under v5/v2 and is rejected as current authority with
`legacy_obligation_scope_v2_authority_not_admitted`; because its ledger
provenance is authoritative rather than verification-only, the historical
comparison projector also refuses it.

## Register closure dossier

### `GY-O0-NC-01`

- verdict: `blocked`
- blocked_by: a producer-issued and persisted canonical production N9 receipt
  for a field-pilot request, with EFFECT established and CALIBRATION and DATA
  passing, while the required pilot protection remains absent and EvalSafety
  therefore blocks. The measured production run did not issue that receipt.
- deciding command: the exact four-cell refusal command above
- exit code: `0`
- decisive output: data-only production is `3 full / 0 scope-only`, so stop
  rule 3 terminated the row before promotion. No constructed or forged receipt
  can satisfy this blocker.
- architect question: which canonical persisted artifact/file owns the real
  field-pilot promotion receipt required by this row? That producer-issued
  artifact must land before the row can be replayed; a test fixture or caller
  injection is not an answer.
- exact append-only prose for the register:

  > **BLOCKED 2026-08-31 (`5a5fa5716`, `cbee85fea`).** The complete four-cell
  > refusal census remains non-promotable before and after Task K. Data-only
  > production has three full refusals and zero scope-only refusals:
  > `effect:unknown`, `calibration:single_obligation_fail`, and
  > `data:single_obligation_fail`; field-pilot production adds the one
  > scope-only `eval_safety:scope_insufficient` refusal. Task K stop rule 3
  > therefore terminated the row before any promotion attempt. No receipt was
  > constructed or injected, no reconciled counter was exercised, and the
  > EvalSafety source SHA-256 remains
  > `22edd5916472bbe5e186c2a0091ab2e65c40d3b06d94c72cbefaaafdb4d6537c`,
  > identical to the slice base. `blocked_by:` a producer-issued, persisted
  > canonical production N9 field-pilot receipt with EFFECT established and
  > CALIBRATION and DATA passing, while the absent required protection causes
  > `EvalSafety=blocked`; the architect must name the canonical persisted
  > artifact/file that owns this receipt. Deciding command: `uv run --extra
  > test pytest -q -s --tb=short
  > tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9`
  > (exit 0; decisive production data-only count `3/0`).

### `gy-promotion-obligations-scope-insufficient`

- verdict: `blocked`
- blocked_by: the same producer-issued real canonical field-pilot receipt
  required by `GY-O0-NC-01`; this row carries that closure signal verbatim.
- deciding command: the exact four-cell refusal command above
- exit code: `0`
- decisive output: the data-only production refusal set is non-empty, so the
  shared signal cannot close.
- exact append-only prose for the register:

  > **BLOCKED 2026-08-31 (`cbee85fea`).** The unconditional
  > `scope_insufficient` defect is repaired, but this row carries
  > `GY-O0-NC-01`'s real-receipt closure signal verbatim. The complete
  > four-cell census still reports data-only production as `3 full / 0
  > scope-only` and field-pilot production as `4 full / 1 scope-only`.
  > Task K stop rule 3 terminated before promotion; no constructed or forged
  > receipt was admitted. `blocked_by:` the same producer-issued, persisted
  > canonical production N9 field-pilot receipt with EFFECT, CALIBRATION, and
  > DATA non-refusing and the missing required protection producing blocked
  > EvalSafety. Deciding command: `uv run --extra test pytest -q -s
  > --tb=short
  > tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9`
  > (exit 0; the shared closure predicate remains false).

### `promotion-comparison-admission-manifest-drift`

- verdict: `closed`
- deciding command: the governed N9 checker after the owner reissue
- exit code: `0`
- decisive output: `status=pass`, zero issues; the corruption probe detects a
  removed decisive field at its healthy exit-1 terminal.
- exact append-only prose for the register:

  > **CLOSED 2026-08-31 (`cbee85fea`).** The generated N9 comparison companion
  > was reissued once through its owner writer after the final EFFECT epoch.
  > Its three canonical receipts are `n9_promotion.v6`, and its three manifest
  > entries use
  > `canonical_promotion_receipt_verification_projection.v5`. The reissue
  > predicate admits only a self-validating, exactly-three-pointer v3-to-v6
  > transition; mixed epochs and sibling pointers refuse. One producer-owned
  > registry now supplies legacy, v3, v4, v5, and current v6 projection rules
  > to the complete four-file consumer denominator (7 calls). Historical v3
  > verification receipts remain comparison-readable. The authentic
  > 48,568-byte v5/v2 receipt remains byte-identical and readable under its own
  > epoch, but is rejected as current authority by
  > `legacy_obligation_scope_v2_authority_not_admitted` and cannot enter
  > historical comparison because it is not verification provenance. Deciding
  > command: `JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers
  > --extra test python
  > tools/quality/validation/check_layer3_gy_promotion_contract.py --check
  > --output-format json` (exit 0, zero issues); the corrupt-field drift probe
  > exits 1 with `corrupt_field_drift_detected`.

### `cg1-certificate-identity-order-sensitive`

- verdict: `closed`
- deciding command: the complete owned grounding-relation test file
- exit code: `0`
- decisive output: `13 passed`; the red-first falsifier had changed candidate
  atom IDs for a sorted persisted edge mapping, and now the atom IDs,
  certificate ID, and certificate content hash are unchanged.
- exact append-only prose for the register:

  > **CLOSED 2026-08-31 (`5a5fa5716`).** CG1 now derives reference atoms from
  > a sorted unique `edge_scope`, so certificate identity is a function of the
  > `CredalReference` content identity rather than mapping insertion order. The
  > falsifier constructs two dataclass-equal references with identical public
  > reference hashes, sorts the persisted edge mapping, and requires identical
  > candidate atom IDs, certificate ID, and certificate content hash. The full
  > owned test file passes 13 cases. The `shadow_only`,
  > `no_bind_admit_promote`, and `cg1_bind_transition_forbidden` boundaries were
  > not weakened. Deciding command: `uv run --extra test pytest -q --tb=short
  > tests/unit/runtime/quality/test_grounding_relation.py` (exit 0, 13 passed).

## Closeout state before repository baselines

No promotion occurred. Therefore there is no receipt, near-miss event, or pair
of reconciled counters to report. The required safety source stayed byte
identical, and the four-cell refusal evidence stayed unchanged. Repository
baseline replay results are appended below after this dossier is present, so
the lifecycle checker measures the journal that will actually be delivered.

## Repository baseline replay

### Architecture guardrails

After `corepack pnpm install --frozen-lockfile`, the exact command

```bash
uv run polisyos-tools architecture guardrails check
```

exited `1`. The runtime API client and dashboard API-type generated freshness
checks were clean. The sole reported failing surface was the carried
trust-claim-posture generator, which stopped because
`DS11-CLAIM-LIFECYCLE-ORCHESTRATION` was not exactly appointed and open. This
lane did not regenerate or silence that receipt.

### Bound debt ledger

The exact post-dossier command

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check
```

exited `1` with `closure_signal_identity_unresolvable=15`. Its complete blocker
ID set was identical to the pre-edit replay:

1. `DS11-EXTERNAL-A11Y-COUNTERSIGN`
2. `DS11-FULL-TRUST-CENTER-AND-DOCS-IA`
3. `DS11-GROUNDED-PERFORMANCE`
4. `DS11-PUBLIC-SIGNATURE-POPULATION`
5. `DS11-SCOPE-ADJUDICATION-RECORD`
6. `decision-validity-fixed-temp-concurrency`
7. `ds10-adapter-admission-capability-discovery-bridge`
8. `ds10-adapter-registry-data-only-free-growth`
9. `ds10-causal-method-index-provider-bridge`
10. `ds10-connector-acquisition-content`
11. `ds10-global-case-index-producer-allocation`
12. `ds10-layer3-owner-ledger-rejection-richness`
13. `ds10-owner-signed-capability-purpose-binding`
14. `ds10-public-decision-rendering`
15. `ds10-world-agent-capability-discovery-boundary`

The blocker set did not grow. The checker also retained one informational
unsupported-runner row; it is not part of the 15 blocking identities.

### Docs lifecycle

The exact command

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py
```

exited `1` with exactly six findings: two existing metadata findings in the
protected active-plan ledger and four existing removed-stub references. This
journal authored no seventh finding.

## Continuation — corrected instrument and production-producer census

This section is append-only and supersedes only the first-round interpretation
of the four-cell table. It does not rewrite the commands or results above.

### Continuation standing

- The task branch was clean and attached before both ordinary merges. The first
  merge fast-forwarded to `e31e72ccbb06641d3ca3461a33d31527dfc686ac` before
  investigation. While the investigation was running, `main` gained the
  completed G/L deliveries; a second ordinary merge fast-forwarded to the
  current continuation base `ef0e24ad7a8d2bd0dd05383529fcfdb0af8ef1f5`.
- The second merge changed no file under `src/**/*.py`. The complete source and
  test censuses below were nevertheless rerun after it, against the actual
  continuation base.
- No source, test, generated manifest, comparison registry, safety-core, or
  safety-hash input was changed by this continuation. The only Task K change is
  this append-only journal section.
- Terminal arithmetic for the four continuation rows: **4 = 0 closed + 4
  blocked + 0 open**.
- Task K stop rule 4 fired: the complete candidate cannot be produced from a
  repository production path. Constructing the missing receipt in a new test
  would invent the evidence whose absence is decisive.

### Continuation pattern pass

- Relevant patterns are `P01`/`P02` (a contract and consumer without the
  producer/orchestration chain), `P05`/`P32` (the existing attempted-evaluation
  certificate expressly cannot be laundered into promotion authority), `P29`
  (a fixture green would not exercise the production property), `P33` (do not
  teach a new witness the requested answer), `P35` (complete AST denominators),
  `P37` (promotion authority cannot rest on a caller-supplied predicate), `P38`
  (a constructed receipt is a proxy for a produced one), and `P41` (baseline
  state measured at the continuation base).
- The existing anti-pattern is not a gate evaluator that cannot pass. It is a
  missing production N7/N8 value-receipt chain and a missing production N9
  context bridge. The round-3 fixture obscured that distinction by supplying
  neither the later EFFECT evidence nor a passing value receipt.
- The smallest correct pattern is the already-assigned chain: N7 admits either
  an institution-signed owner rollout assignment or a certified SKG identity
  bridge; N8 produces and persists the bound `ValueGateReceipt` and emits the
  corresponding `value_ready` observation; the production N9 port carries the
  producer inputs into its existing measurement, independence, and EFFECT
  writers. A test helper cannot substitute for any link.
- Capability state is `producer_missing + bridge_missing`, not a candidate that
  merely happens to fail a complete gate.

### Complete candidate-producer census

The deciding command was one AST walk over every `*.py` file under `src` and
then every `*.py` file under `tests`. It counted class definitions, constructor
and `model_validate` calls, `ValuePortObservation(status="value_ready")` calls,
`CanonicalN9PromotionPort(context_provider=...)` calls, and exact string-literal
uses of the three production writer-input keys. The search was structural, not
textual; its positive controls were the real class definition, two persisted
receipt readers, and all three production writer-input consumers.

Source denominator and result:

```text
path_denominator=policy-engine/src
file_type_denominator=*.py
python_files=2616
value_gate_class_defs=1
value_gate_constructor_calls=0
value_gate_model_factory_calls=2
value_ready_observation_calls=0
value_receipt_observation_calls=0
canonical_port_context_provider_calls=0
promotion_evidence_context_literal_sites=3
```

The one class definition is
`src/polisyos/runtime/quality/generation_cycle.py:445`. The two factory calls
are `ValueGateReceipt.model_validate` at
`src/polisyos/runtime/quality/promotion_sequence.py:1530` and `:1590`; both
parse persisted owner/history projections and do not mint a receipt. The three
literal sites are the existing consumers
`effective_independence_writer_input` (`:1435`),
`measurement_root_writer_input` (`:1455`), and
`effect_obligation_writer_input` (`:1467`). Their presence proves the census
could find the bridge vocabulary; the zero production context-provider calls
proves no source caller supplies it.

Test denominator and result:

```text
path_denominator=policy-engine/tests
file_type_denominator=*.py
python_files=2484
value_gate_constructor_calls=2
value_ready_observation_calls=1
value_receipt_observation_calls=1
canonical_port_context_provider_calls=5
```

Both receipt constructors are test helpers
(`test_promotion_sequence.py:3779`, `test_value_gate.py:2362`). All five N9
context-provider constructions are in `test_promotion_sequence.py`. The sole
`value_ready` observation is itself a negative test: it constructs a test
receipt without an owner selection receipt and requires
`value_ready_requires_owner_receipts`. Thus the test tree is a positive control
for exactly the mechanisms absent from production, not a hidden producer.

This reproduces the GY plan's existing `GY-PA1` finding on the current base:
production constructs no `ValueGateReceipt`; N8's furthest owner-resolved path
ends at `treatment_assignment_not_owner_derived`; N7 must first admit either an
institution-signed rollout assignment or a certified SKG identity bridge; N8,
not Task K or PA1, owns the persisted receipt producer.

### Four-cell refusal table, corrected instrument

The round-3 figures are retained exactly. The requested EFFECT-bearing
continuation column is deliberately `not run`: producing its required passing
value receipt is impossible through source and would require one of the two
test-only constructors plus a test-only N9 context provider. That would violate
stop rules 1 and 4 and would turn an absent producer into a manufactured
candidate.

| Request class | Lane | Round-3 full | Round-3 scope-only | EFFECT-bearing complete-candidate full | EFFECT-bearing complete-candidate scope-only |
| --- | --- | ---: | ---: | --- | --- |
| data-only | production | 3 | 0 | not run — production receipt producer absent | not run — production receipt producer absent |
| data-only | contract testing | 3 | 0 | not run — would construct a receipt | not run — would construct a receipt |
| field-pilot | production | 4 | 1 | not run — receipt producer and EvalSafety authority absent | not run — receipt producer and EvalSafety authority absent |
| field-pilot | contract testing | 3 | 0 | not run — would construct a receipt | not run — would construct a receipt |

Therefore there is no honest numeric “after” table. The absence is itself the
deciding measurement. A declared fixture was not created. Such a fixture could
show only that already-constructed DTOs compose through the evaluators; it
could not establish that a governed design produced its evidence, that N8
emitted it, or that production N9 consumed it.

### EvalSafety appointment ruling and complete census

The same current-base AST walk enumerated the EvalSafety certificate type,
constructor and builder calls, every symbol whose name combines promotion with
EvalSafety, and every literal promotion use in `authoritative_for` and
`may_not_use_for` fields:

```text
path_denominator=policy-engine/src
file_type_denominator=*.py
python_files=2616
eval_safety_certificate_class_defs=1
eval_safety_certificate_constructor_calls=1
eval_safety_certificate_builder_calls=2
promotion_eval_safety_symbol_defs=0
promotion_eval_safety_symbol_calls=0
authoritative_for_promotion_fields=0
may_not_use_for_promotion_fields=5
```

The positive certificate is `EvalSafetyCertificate` at
`runtime/quality/evaluation_safety.py:688`; its single owner constructor is at
`:1828`, reached by the HTTP owner service and the Runtime replay path. The
type fixes `authoritative_for` to `attempted_evaluation_admission` and requires
`promotion` and `attempted_evaluation_occurred` in its deny set. There is no
promotion-authoritative EvalSafety artifact, producer symbol, or minting call
in the complete source denominator.

The answer is therefore split at the ratified boundary:

- the neutral artifact vocabulary, typed empty signer slot, content-binding
  verifier, resolver interface, persistence bridge, and fail-closed N9
  consumer are **producible engineering**;
- the act of minting a receipt that says the field-pilot/deployment safety
  predicate has promotion authority needs an **appointment**. The existing
  GY-O0 owner is appointed only to attempted-evaluation admission and is
  statically forbidden from minting the promotion claim.

This is identity decision §9 items 5 and 6 exactly: build the full mechanism
and leave the signature slot typed and empty, but do not treat a verifier as a
signer or reuse the GY-O0 certificate. Task K did not take that build after the
first-row stop fired, and the user explicitly allowed this row to be handed
back untouched. The architect must name (1) the canonical promotion-authority
artifact, (2) the institution/component appointed to mint it, and (3) the
owner file for its neutral contract and typed empty slot. No Task K-owned file
can be chosen honestly until that authority decision lands.

### Safety-core integrity

An AST source-segment hash compared the exact
`decide_evaluation_safety_core` function at the merged GY-O0 commit, the prior
Task K head, and the continuation head:

```text
313132b6b core_bytes=4711 core_sha256=ac0620093ed69e8c219f9bce1936900ec99ef1eaca7821a31a948418f73d0e2d
aaf60c71b core_bytes=4711 core_sha256=ac0620093ed69e8c219f9bce1936900ec99ef1eaca7821a31a948418f73d0e2d
HEAD        core_bytes=4711 core_sha256=ac0620093ed69e8c219f9bce1936900ec99ef1eaca7821a31a948418f73d0e2d
```

The entire current `evaluation_safety.py` file also remains byte-identical to
the prior Task K head at SHA-256
`22edd5916472bbe5e186c2a0091ab2e65c40d3b06d94c72cbefaaafdb4d6537c`.
No promotion occurred, so no near-miss event or reconciled counter was emitted.

## Continuation register closure dossier

### `first-promotion-candidate-with-complete-evidence`

- verdict: `blocked`
- blocked_by: the N7/N8 production value-authority chain and production N9
  evidence-context bridge must land. Concretely: an institution-signed owner
  rollout assignment or certified SKG identity bridge admitted by N7; an N8
  owner-produced, persisted `ValueGateReceipt` plus a valid `value_ready`
  observation; and a production `CanonicalN9PromotionPort` context supplier
  carrying the existing measurement, independence, and EFFECT writer inputs.
- deciding command: the complete current-base source/test AST census above
- exit code: `0`
- decisive output: over 2,616 source Python files, receipt constructors `0`,
  `value_ready` emissions `0`, and production context-provider calls `0`; over
  2,484 test Python files the corresponding counts are 2, 1, and 5.
- exact append-only prose for the register:

  > **BLOCKED 2026-08-31 — COMPLETE PRODUCER CENSUS, STOP RULE 4.** The corrected
  > round-3 interpretation does not make a complete candidate executable.
  > Across all 2,616 `src/**/*.py` files, `ValueGateReceipt` has one class
  > definition, zero constructors, zero `ValuePortObservation(status="value_ready")`
  > emissions, and zero `CanonicalN9PromotionPort(context_provider=...)` callers.
  > The two `ValueGateReceipt.model_validate` calls are persisted-history readers.
  > The same AST search finds two receipt constructors, one deliberately-invalid
  > `value_ready` observation, and five context-provider calls under all 2,484
  > `tests/**/*.py` files. Creating the requested witness would therefore invent
  > the missing evidence and violate Task K stop rule 4. `blocked_by:` N7 admission
  > of an institution-signed owner rollout assignment or certified SKG identity
  > bridge; N8 production and persistence of the bound `ValueGateReceipt` and
  > valid `value_ready` observation; and production N9 wiring of the three existing
  > writer-input keys. No fixture was created and no promotion was attempted.
  > Deciding command: the complete AST census recorded in the Task K journal
  > (exit 0; source zeroes 0/0/0 with positive test controls 2/1/5).

### `eval-safety-promotion-authority-producer-missing`

- verdict: `blocked`
- blocked_by: an architect appointment of the authority allowed to mint the
  promotion-grade field-pilot/deployment safety predicate, followed by its
  neutral contract, typed empty signer slot, producer/persistence bridge, and
  N9 consumer in the architect-selected owner file. The row was handed back
  untouched because the first-row stop fired.
- deciding command: the complete current-base EvalSafety AST census above
- exit code: `0`
- decisive output: one real EvalSafety certificate type and owner constructor,
  zero promotion-EvalSafety producer symbols, zero promotion-authoritative
  fields, and five explicit promotion denials.
- exact append-only prose for the register:

  > **BLOCKED 2026-08-31 — APPOINTMENT REQUIRED; ROW UNTOUCHED.** The complete
  > 2,616-file source census finds one real `EvalSafetyCertificate` type, one
  > owner constructor, and two builder call sites, but zero symbols or calls that
  > combine promotion with EvalSafety and zero `authoritative_for` fields
  > containing `promotion`. The existing certificate is fixed to
  > `attempted_evaluation_admission` and must deny both `promotion` and
  > `attempted_evaluation_occurred`; reusing it would launder GY-O0 authority.
  > The contract, typed empty slot, verifier, persistence bridge, and fail-closed
  > N9 consumer are producible engineering. Minting the promotion-authority
  > predicate is an appointed act under identity decision §9 item 6. Task K
  > handed this row back untouched after its first-row stop fired. `blocked_by:`
  > the architect must appoint the minting institution/component and name the
  > canonical artifact and owner file; then the full mechanism must land with
  > that signer slot typed and empty until appointment evidence is present.
  > Deciding command: the complete EvalSafety AST census in the Task K journal
  > (exit 0; promotion-authoritative fields exactly zero).

### `GY-O0-NC-01`

- verdict: `blocked`
- blocked_by: both concrete predecessor builds above must land: the real N7/N8
  candidate-evidence producer chain and the appointed EvalSafety
  promotion-authority artifact/mechanism. Only then can the unchanged
  field-pilot signal be measured.
- deciding command: the combined current-base candidate and EvalSafety AST
  census
- exit code: `0`
- decisive output: production cannot issue the prerequisite promotable receipt,
  and the field-pilot obligation has no promotion-authority artifact. A test
  construction would satisfy neither absence.
- exact append-only prose for the register:

  > **BLOCKED 2026-08-31 — TWO PRODUCTION CHAINS MUST LAND.** The corrected
  > measurement terminates before a four-cell replay because the purported
  > complete candidate can currently be assembled only in tests. The complete
  > source census has zero `ValueGateReceipt` constructors, zero valid
  > `value_ready` emissions, and zero production N9 context-provider calls; the
  > complete EvalSafety census has zero promotion-authoritative fields or
  > producer symbols, while the real GY-O0 certificate statically denies
  > promotion use. `blocked_by:` (1) the N7/N8 owner-backed receipt production
  > chain and production N9 evidence bridge, and (2) the appointed
  > promotion-authority EvalSafety artifact with its full typed-empty mechanism.
  > No receipt was constructed or injected, no promotion or near miss occurred,
  > and no reconciled counter moved. The 4,711-byte safety core remains SHA-256
  > `ac0620093ed69e8c219f9bce1936900ec99ef1eaca7821a31a948418f73d0e2d`,
  > identical to `313132b6b`. Deciding command: the combined current-base AST
  > census (exit 0; decisive production zeroes documented in the Task K journal).

### `gy-promotion-obligations-scope-insufficient`

- verdict: `blocked`
- blocked_by: the same two production chains as `GY-O0-NC-01`, whose strict
  closure signal this row carries verbatim.
- deciding command: the combined current-base candidate and EvalSafety AST
  census
- exit code: `0`
- decisive output: the three former unconditional scope failures are repaired,
  but the one field-pilot EvalSafety scope absence is real and no production
  candidate exists with which to reach its replacement predicate.
- exact append-only prose for the register:

  > **BLOCKED 2026-08-31 — SHARED SIGNAL, SAME TWO PRODUCER CHAINS.** The three
  > formerly unconditional `scope_insufficient` obligations remain repaired.
  > The remaining field-pilot EvalSafety absence is not a gate evaluator defect:
  > it names a promotion-authority producer that the complete source census
  > proves absent. The same census also proves that production cannot yet create
  > the prerequisite complete `ValueGateReceipt` candidate. `blocked_by:` the
  > N7/N8 owner-backed value-receipt chain plus production N9 evidence wiring,
  > and the appointed EvalSafety promotion-authority artifact/mechanism. This row
  > closes or remains blocked with `GY-O0-NC-01`; no constructed fixture can
  > change that verdict. Deciding command: the combined current-base AST census
  > (exit 0).

## Continuation baseline pre-edit receipt

At continuation base `ef0e24ad7`, before this journal append, the exact bound
debt command exited `1` with 16 unresolvable closure-signal identities. The
sixteen are the previous fifteen plus the newly registered
`global-case-index-producer-missing` row merged from `main`; Task K did not
author that change. This **16-row base set**, not the earlier 15-row set, is the
comparison denominator for the post-journal replay. Post-journal debt and docs
lifecycle results are appended below after the delivered journal itself is in
their filesystem view.

## Continuation exact-search addendum

The exact census invocation was `uv run python - <<'PY'` from `policy-engine/`.
For each of `Path("src").rglob("*.py")` and
`Path("tests").rglob("*.py")`, sorted, it parsed the file with `ast.parse` and
applied these exact zero predicates:

1. receipt constructor: an `ast.Call` whose dotted callee's leaf is
   `ValueGateReceipt`;
2. successful value emission: an `ast.Call` whose leaf is
   `ValuePortObservation` and whose `status` keyword contains the exact string
   literal `value_ready`;
3. receipt-bearing value emission: the same call with a `value_receipt`
   keyword;
4. production N9 evidence bridge: an `ast.Call` whose leaf is
   `CanonicalN9PromotionPort` and which has a `context_provider` keyword;
5. promotion EvalSafety producer surface: any class/function/call name that
   contains `promotion` and either both `eval` and `safety` or
   `evaluationsafety` after lowercase normalization;
6. promotion authority: an `authoritative_for` call keyword, annotated
   assignment, or dictionary field whose AST subtree contains the exact string
   literal `promotion`.

Positive-control predicates in the same walk counted the `ValueGateReceipt`
and `EvalSafetyCertificate` class definitions, `ValueGateReceipt.model_validate`
calls, the exact three writer-input string literals, EvalSafety certificate
constructor/builder calls, and `may_not_use_for` fields containing the exact
`promotion` literal. This is the exact search behind every zero in the dossier.

## Continuation post-journal baseline receipt

The exact bound command

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check
```

exited `1` after the dossier append. Its complete 16-identity blocker set is
identical to the pre-edit continuation-base set. Task K's set did not grow.
The unsupported Vitest runner remains informational and is not in the blocking
set.

The exact docs command

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py
```

exited `1` with exactly the same six findings as the continuation base: two
active-plan metadata findings and four removed-stub references. This appended
journal authored no seventh finding.
