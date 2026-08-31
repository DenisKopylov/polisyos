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
