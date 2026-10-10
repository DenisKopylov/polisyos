# B194 Foundry failure-scope repair

Status: implementation and focused behavioral verification are ready for review. This is not a
formal finding closure or a claim that every B194 boundary is established.

## Source-bound criterion

The owner criterion is B194 at
`docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md:4792-4801`.
The exact source-span SHA-256 is
`47058d366d7ff7e11ed2348e96b2f56659a999f1f0839a02edc92804b295711e`; the current full source-file
SHA-256 is `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`. The binding is
`closure-decisions/coverage.json#/findings/113/criterion_refs/0`.

The criterion's executable witness is a fixed symmetric 100-point input with `y=x`, followed by a
solver refusal for `x<0`. The complete run has mean 0. The remaining 50 outputs have conditional
mean `50/99 ≈ 0.50505`, above `mc_min_valid_samples=10`. The failure register therefore requires
preserving the incomplete basis and forbids treating global access or contract errors as noisy
draws.

P40 classification: **SAME_CLASS_DEEPER**. This is the same conditional-distribution / lost-failure
scope class already exercised by Welfare, deeper in the generic Foundry Monte Carlo evaluator and
its nominal and versioned-posterior call paths. The repair consolidates exception-graph traversal and
scope classification once; it does not add a per-exception-site allowlist. The current retry
  task is a same-class deeper repair of the original bounded typed-transient retry clause.

## Mechanism and observed behavior

`src/polisyos/foundry/uncertainty/evaluation_failures.py` adds a private shared classifier for
cause, context, and exception-group graphs. It distinguishes shared descendants from active cycles,
caps traversal at 64 distinct nodes and 256 edges, classifies visible `OSError`, Pydantic validation,
fatal/validation `PolicyOSError`, and caller-declared global error types, and accepts typed
transient/sample-domain scope only at the root of a complete acyclic graph.

`monte_carlo.py` uses that classifier in the generic `propagate()` draw path, the
`propagate_posterior_summary()` row path, and nominal preflight. Only an unchained built-in
`RuntimeError` retains the old draw-local candidate behavior. Other typed or unknown failures,
including cause-wrapped globals and cyclic/truncated graphs, propagate. A root typed transient
gets at most one retry with the same input mapping across nominal, sampled, and versioned-posterior
evaluator calls. The retry does not add a logical draw; the persisted ledger separately records
`simulation_attempt_count` and `retry_attempt_count`. A second transient escapes. Sampling errors,
global failures, and unknown failures are not retried. The existing direct
`RuntimeError` case remains non-authoritative: partial output stays candidate-only with no confidence
interval or normative admission.

The exact 100/50 test passes through the public propagator and through `PropagateUncertaintyNode`,
FileSystemCAS persistence, fresh uncertainty-envelope/report reads, and a fresh
`RunNormativeArbitrationNode`. The downstream result remains partial and excludes the incomplete
metric. A separate global-permission node test proves the exception escapes before a partial
SimulationResult is written; the original CAS bytes remain unchanged. Classifier and public
propagator controls cover direct and wrapped OSError, Pydantic validation, an ExceptionGroup with a
global member, direct fatal/validation/transient PolicyOSError, and cyclic/truncated unknown graphs.

## Deciding commands and retained outputs

The current-boundary focused run used:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -o addopts= -q -ra \
  --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-exact-original-reproducer/failure-scope-final3.xml \
  tests/unit/foundry/uncertainty/test_evaluation_failures.py \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_exact_symmetric_partial_draws_stay_candidate_and_retain_control \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_exact_symmetric_partial_draws_reach_fresh_normative_consumer \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_global_access_error_is_not_recorded_as_a_draw_failure \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_global_permission_error_after_nominal_preflight_escapes \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_global_and_unknown_causes_fail_closed_at_sampled_call_boundary \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_b194_global_permission_error_does_not_persist_partial_node_result \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_posterior_pushforward_does_not_record_global_failure_as_failed_row \
  tests/unit/foundry/uncertainty/test_monte_carlo_b194.py::test_versioned_posterior_consumer_retains_failed_rows_and_limits_summary_basis \
  tests/unit/foundry/uncertainty/test_monte_carlo.py::TestMonteCarloPropagator::test_mc_heuristic_fallback_on_sim_failures \
  tests/unit/foundry/uncertainty/test_monte_carlo.py::TestMonteCarloPropagator::test_mc_qmc_failure_path_counts_failures_and_avoids_input_metric_fallback
```

Result: **14 passed in 4.19s**, exit 0. Full stdout, stderr, exit code, and JUnit are retained at
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-exact-original-reproducer/failure-scope-final3.*`.

For the P29 removal-of-property control, an ignored pytest plugin kept the production source and
test assertions intact while forcing the shared classifier to return `unknown` and the
legacy-draw-local predicate to allow every error. The corrected direct nominal and sampled-call
PermissionError tests then both failed with the intended `DID NOT RAISE PermissionError` result
(2 failed in 3.46s, exit 1). The plugin and complete stdout, stderr, exit code, and JUnit are retained
at `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-exact-original-reproducer/remove_global_boundary_plugin.py`
and `global-boundary-remove-property-control-final2.*`. This is an isolated mutation control; shared
source was not edited for the probe.

The earlier 14-pass focused run predates the bounded retry and is scope-only, not the final
receipt.

The older `global-access.*` baseline file is **fixture-invalid**, not a deciding red: that test used
`inaccessible_source(_x)` while the runtime passed keyword `x`, so it failed through `TypeError` and
did not establish the PermissionError behavior. The corrected current-boundary tests and isolated
removal control above replace that evidence. The intermediate
`failure-scope-focused.*` output is also non-deciding; it exposed that fixture mismatch and a
`None`-versus-empty assertion, both corrected before the final run.

Ruff check and format check passed on the four Python implementation/test files; `py_compile` passed
on the two production files; the release TOML fragment parsed with its required fields. Complete
outputs are retained under the same `LOCAL/raw/b194-exact-original-reproducer/` directory.

## Bounded limitation

The legacy direct built-in `RuntimeError` is not independently proven to be caused by an input
domain; it remains a candidate-only per-draw failure for compatibility. Typed transient retry is
limited to one repeated evaluator call on the unchanged mapping; there is no backoff or new sample
draw. Exhaustion propagates. No native HMC/fit run was performed, and no formal G acceptance or
closure is claimed.

## Changed source and companion paths

- `src/polisyos/foundry/uncertainty/evaluation_failures.py`
- `src/polisyos/foundry/uncertainty/monte_carlo.py`
- `src/polisyos/foundry/uncertainty/README.md`
- `tests/unit/foundry/uncertainty/test_evaluation_failures.py`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py`
- `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml`

The helper is internal and is not added to the Foundry uncertainty public facade. Current source
and companion hashes:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/foundry/uncertainty/evaluation_failures.py` | `a371c4e8ad6ca37d3d94bb69fefad541c442fcec233c2a7305ea689fffca9050` |
| `src/polisyos/foundry/uncertainty/monte_carlo.py` | `55cb10307797795392e17ae68f76c754672d85dbe341d301043ba20507152d80` |
| `src/polisyos/foundry/uncertainty/README.md` | `1eb6ecd9a2532e0111b7820e39aab5535fd72ce870e177354afbe8f7fb3f0343` |
| `tests/unit/foundry/uncertainty/test_evaluation_failures.py` | `265badd84d4ad7488cc6380a511b3abfee9cbc9870fe1d4b3b906814f241288c` |
| `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` | `28a36d300bd54642a016b28cee7e955bddbc8e39e3925bbb00232f6519e68e97` |
| `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml` | `85c34f3757ad9a0affb6a69c0da6a538d3f8f3fe8c39269c4031d74d0b7107fa` |

The final focused receipt hashes are `failure-scope-final3.stdout` `fabc351fd86479e030a5a5f70069b92e51ecf4f0bf52d7c0b93085dfb060ce40`, `failure-scope-final3.stderr` `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, `failure-scope-final3.exit` `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`, and `failure-scope-final3.xml` `0ea017ea6ab30d594c8f6c9e85826c4d62abef1f268d76bcfbc08f2f4747983a`. The isolated removal-control hashes are `global-boundary-remove-property-control-final2.stdout` `1e5f0c0ae27202c4242bd49f110f5cc3a51f8cd2c14402696d64dfd989377408`, `.stderr` `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, `.exit` `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`, and `.xml` `2b91a871aa80d5d66db21a0fa70e81aec582d5fba5824d7e6ce8f1ebdf064476`. The plugin SHA-256 is `c366df729e4003a6ba8e7d8372a95d47c21ce80006338410b65ee54a86b16611`.

The current Ruff, formatting, compile, and release-parse outputs and exit companions are also retained
as `final3-ruff-check.*`, `final3-ruff-format.*`, `final3-pycompile.*`, and `final3-release-parse.*`
under the same raw directory. One read-only `git status --short` was run during inspection; no Git
mutation was performed.

## Same-draw retry addendum

The original B194 contract also requires a bounded retry of a typed temporary failure on the same
authorized draw. The current implementation uses one shared Foundry evaluator wrapper for nominal
preflight, random/QMC sampled draws, and the versioned posterior selected point/source rows. Only a
root transient classification from the shared exception classifier is retried, at most once. It
reuses the same parameter mapping and does not advance the sampler or add a denominator row. A second
typed transient escapes instead of becoming a partial result. The report keeps `attempted_draw_count`
as logical sample rows and adds separate `simulation_attempt_count` and `retry_attempt_count` values.

Behavioral regressions exercise a transient recovered on the first symmetric draw, a transient during
nominal preflight, posterior row recovery, exhausted retry, unchanged vector hashes, a fresh CAS report
read and normative consumer, and the existing global/unknown failure controls. The recovered 100-draw
case produces 102 evaluator calls (one nominal, 100 sample rows, one retry), with a 100-row denominator,
100 successes, zero failures, and one retry. The exhausted case makes two evaluator calls for the same
first sampled value and propagates the same typed error.

The focused RED controls before the source change are retained at
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-same-draw-transient-retry-red.txt`
and
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-same-draw-transient-retry-controls-red.txt`. The first selector failed at the typed
transient call; the latter three selectors failed at posterior evaluation, retry exhaustion (only one
call), and the real node path. An earlier command typo that could not find `python` or the selector is
not deciding evidence. The post-change focused retry/global/classifier run before the DTO contract update was 13 passed
in 3.73s and is retained at `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/`
(`b194-same-draw-transient-retry-focused-final.txt` and `.xml`). It is superseded by the current
21-test run below.

The pre-compatibility focused command was `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python
-m pytest -o addopts= -q -ra [18 explicit selectors: evaluation_failures.py; retry, nominal, posterior,
sampler, exhaustion, fresh CAS, global/unknown controls; posterior historical/strict-schema controls;
and the existing Monte Carlo random/QMC failure controls] --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-final.xml`.
It completed **21 passed in 4.46s**, exit 0. Complete stdout, stderr, exit status, and JUnit are
retained as `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-final.*`.
This is a focused regression run, not the complete Foundry suite.

## Posterior output DTO compatibility decision packet (implementation selected; G pending)

`PosteriorPushforwardResult` is an exported strict Pydantic DTO (`extra="forbid"`) in the public
stable Foundry uncertainty facade. Repository search finds no persisted consumer, registered schema
snapshot, or reader of `row_evaluation_semantics`; the DTO is returned in memory. The source
`PosteriorSummaryV11.profile_version` remains 1.1 and names the input profile. The result DTO is not
registered as an artifact schema, but its runtime `model_json_schema()` is part of the exported
Python contract and includes required attempt-count fields and two semantics literals. The public
surface inventory lists the exported type name only and remains for root canonical review. A review
found that an actual retry result could have both counters stripped and its literal reset to the old
value, after which the parser accepted it as a historical no-retry result. This is a NEW_CLASS public
result-history/versioning issue, not an authority promotion; the result remains candidate-only.

Options considered:

- **Require counters on the current DTO (selected implementation; G acceptance pending):** keep the
  old semantics literal only for a counted zero-retry result; emit
  `one_logical_result_per_source_draw_with_one_bounded_typed_transient_retry` only when a retry
  occurs; require `simulation_attempt_count` and `retry_attempt_count` for every current result; and
  recompute the physical-count relation against one selected-point evaluation plus one per source
  row. Current parsing rejects payloads without these fields rather than synthesizing zero attempts.
  Older strict clients must migrate, and old serialized payloads without counters require explicit
  migration or recomputation. The source `profile_version` remains 1.1; this is a result-schema
  compatibility change, not a source-profile change.
- **Add an explicitly named legacy reader (researched alternative, not implemented):** validate the
  old shape into a separate strict limited result that exposes the recorded old literal as
  `recorded_row_evaluation_semantics` and physical-attempt provenance as `not_established`. It must
  not synthesize zero retries, claim an exact one-call history, or return the current
  `PosteriorPushforwardResult`. No such persisted reader or stored result exists in this repository,
  so this would add a public surface solely for hypothetical external payloads. If a real legacy
  consumer appears, this is the bounded compatibility option to reconsider.
- **Preserve the literal by refusing retries in the posterior path:** this keeps old clients parsing
  but violates the original B194 same-draw retry criterion at a real consumer boundary.
- **Add a versioned result DTO/API:** this would let a separate result profile preserve the old
  contract, but no second result DTO or persisted output-schema registry exists. It adds parallel
  routing and type surface solely to preserve compatibility; retain as a G alternative if the
  additive public-schema change is not accepted.

The source profile remains 1.1; no source summary version or authority semantics changed. The result
continues `gate_eligible=false` and `unit_binding_status="not_established"`; that unit status is not
reused to describe attempt history. The current parser schema requires both attempt counters. Tests
exercise an actual retry result with the counters removed and old literal restored, a genuine
zero-retry result with observed physical calls, and the required-field schema. The named legacy reader
and separate-version API remain unselected alternatives. This packet is a proposal and implementation
record, not G acceptance; independent root review and generated-surface review remain pending.

## Initial retry implementation footprint and hashes (pre-compatibility delta)

This retry addendum changed the following product/companion files; the classifier and Welfare adapter
interfaces are unchanged:

- `src/polisyos/foundry/uncertainty/monte_carlo.py`
- `src/polisyos/foundry/uncertainty/README.md`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py`
- `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml`

The exact pytest argv, working directory, thread environment, and complete outputs are retained in
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-final.command.txt`,
`b194-retry-final.stdout`, `b194-retry-final.stderr`, `b194-retry-final.exit`, and
`b194-retry-final.xml`. The deciding stdout SHA-256 is
`85fd2315b66891c5fe6ab1154dd536ee283aa841a19862db3377f6cccee7d388`; stderr is empty; exit-file
SHA-256 is `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`; JUnit SHA-256 is
`f8796a77e2dcd74ab807259f4ad88ef384192e5c41165d8defbdc6338cf88ca5`.

At that pre-compatibility checkpoint, source/companion hashes were:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/foundry/uncertainty/monte_carlo.py` | `f34de0be4d49f9d500f546e4471ae85918d0aebc7291fadb53093de2a0666199` |
| `src/polisyos/foundry/uncertainty/README.md` | `136249e7d9c81788dfeb8c30f3ff51770333fd20df5fae285b2c983f682cae46` |
| `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` | `c36a47ccedcde952de93c4385259ee46337a3f24e4fa722aac256f08016e3c16` |
| `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml` | `ccb2d22e8894fa5d1ca06229d9e9b621987cd5bf9205c41f1dec54e1764e7f26` |
| `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-final.command.txt` | `dac1fff91da796d98960ec12f51810f0e056029b2f3c52dc2506f2cbc6153a71` |

`ruff check` and `ruff format --check` passed for the changed Python source/test. The output DTO schema
is a live `model_json_schema()` surface and has no checked-in schema snapshot. The model/schema
regression asserts both semantics literals and requires both count properties; root's canonical
public-surface review is pending.

## Required-counter compatibility delta

After the independent downgrade finding, the focused test first failed as intended in three places:
the generated DTO schema did not require counts, an omitted-count zero-retry payload parsed, and an
actual retry result with both counts removed and the old literal restored parsed. The complete red
output is retained at
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-compatibility/red.*`.
The corrected current DTO requires both counters and validates physical attempts against observed
producer counts. The exact focused cohort was rerun once after the delta: **21 passed in 5.41s**, exit
0. Its command, stdout, stderr, exit, and JUnit are retained under
`docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-compatibility/final.*`.
Ruff check and format check also passed; complete outputs are retained beside that run. These checks
verify the selected parser/migration behavior; G acceptance, public-surface review, and the final
composed source freeze remain pending.

The current product/companion bytes are:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/foundry/uncertainty/monte_carlo.py` | `a2aacf8e01d0e71bd9707ced3c0d71577f16ed2cdea1a586a777f2a9b92eccc9` |
| `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` | `c25eb001bcb4af04bdec3828c360b50c54b46acd04c88f8da53f6ba6e2c6610a` |
| `src/polisyos/foundry/uncertainty/README.md` | `2b18b72bdbabf5c76643d8c973ba7dc44b135f6000e3c4cc534d6e1f22995386` |
| `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml` | `965348d27217929e83b89726b7e215c3554ffca03551b8bad4e3c713d1bd0777` |

The required-counter RED output SHA-256 is `fc7f87030e648ef917b65fb3e79fe75c4451bb288b02bcb61aae0923bd4cf09b`; its exit is 1 and stderr is empty. The post-delta focused stdout SHA-256 is `72c854eda02f54e4373c12157d85c94d901d496bc6851e37cf28d43aa25e5cb7`; stderr is empty; exit is 0; JUnit SHA-256 is `a07f0799a04c603f7e98bbb133ec1fda4096bbc3c354c3fa7090262ffa19b8ed`. Ruff-check and format stdout hashes are `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` and `3bc53bf3e981a98a34a852e175bf9b77af841edea74fca595d9aedcbaf9a4938`. These receipts are under the ignored `LOCAL/raw/b194-retry-compatibility/` directory; no hash of this decision packet is asserted.
