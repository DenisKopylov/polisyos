# B194 bounded-retry independent acceptance review

## Verdict

The current implementation passes the bounded retry property: one root typed transient can repeat the identical evaluator input once, while logical draw counts stay separate from physical calls. The exact original B194 partial-output witness also remains candidate-only and is refused by the fresh normative consumer. This is not full B194 closure or G acceptance.

There is one release/API decision still open: the strict public posterior DTO intentionally accepts historical payloads without attempt counters, but a current retry result can be stripped and relabeled into that accepted historical shape. This does not enable authority (`gate_eligible` remains `False`), but it can erase audit provenance. The release fragment still says `public_surface_inventory_reviewed = false`; do not claim lossless attempt-history compatibility or release readiness until that surface choice is reviewed.

## Original criterion and boundary

The source criterion is B194 at `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md:4792-4801`, occurrence `closure-decisions/coverage.json#/findings/113/criterion_refs/0`, source-span SHA-256 `47058d366d7ff7e11ed2348e96b2f56659a999f1f0839a02edc92804b295711e`. It specifies the fixed 100-point symmetric `x∈[-1,1]`, `y=x` witness, a refusal for `x<0`, and `mc_min_valid_samples=10`. The complete mean is 0; retaining only the 50 successful rows yields the conditional mean `50/99 ≈ 0.50505`, which exceeds the minimum-valid threshold. The criterion asks to preserve draw identity, failure types, and missing mass; a temporary error may repeat the same authorized draw, while global access/contract errors must not become noisy samples. It does not authorize treating the 50-row conditional result as an unconditional confidence claim.

The current exact witness still returns 50 successes and 50 failed rows over the same 100 draws. Its reported mean is the conditional `50/99`; the envelope is `HEURISTIC_RANGE`, has no confidence level, and is marked `candidate_only`/`gate_eligible=False`. The fresh CAS and normative-reader test leaves model completeness partial, excludes the incomplete metric from proposal binding, and leaves rights audit unevaluated.

## Mechanism review

`evaluation_failures.py` traverses cause, context, and exception-group edges with 64-node/256-edge limits. A visible `OSError`, Pydantic `ValidationError`, or fatal/validation `PolicyOSError` anywhere in the graph wins over transient classification. Only a root `PolicyOSError(category=TRANSIENT)` with a complete acyclic graph is classified transient. There is no error-message matching. The classifier is shared by nominal preflight, sampled evaluation, and the versioned-posterior selected-point/source-row path; random and QMC sampling both enter the same `_eval_and_record` wrapper.

`_evaluate_with_transient_retry` allows two physical calls total, and retries only after the first typed transient. It reuses the same numeric parameter mapping and does not request another random or QMC sample. Exhaustion propagates. Sampling failures do not enter the evaluator retry. Global, validation, wrapped/global, cycle, truncation, and other unknown failures are not retried. The retained compatibility carveout is an unchained built-in `RuntimeError`: it can still represent a failed candidate draw, but it is never retried. That remains a bounded limitation because an arbitrary untyped `RuntimeError` does not prove a sample-domain cause.

For the original random witness, the recovery case records 102 physical evaluator calls—one nominal preflight, 100 logical sample rows, and one retry—while `attempted_draw_count=100`, `successful_draw_count=100`, and `retry_attempt_count=1`. An independent real Sobol control generated one 100-row chunk and made 102 evaluator calls; the first QMC vector and sampled-input digest were identical across the transient and retry. A separate mutable-kwargs control reassigned `kwargs["x"]` inside the first callback, then raised a transient; both callback entries still observed the retained scalar input `1.0`.

The posterior path returns a strict frozen `PosteriorPushforwardResult` with `simulation_attempt_count`, `retry_attempt_count`, and an additive `row_evaluation_semantics` literal. Its validator rejects contradictory counts/literals. The physical count includes the selected-point evaluation plus source rows and retries; the test's call order `[2, 1, 1, 2, 3]` demonstrates one selected point, three source rows, and one same-row retry. Historical records without the new counters still parse as the old no-retry literal. The README and release fragment accurately say that older strict `extra=forbid` consumers need an update; `profile_version=1.1` continues to identify the source-summary profile, not the result DTO schema.

## Independent probes and P40 disposition

- **SAME_CLASS_DEEPER — classifier scope.** The retry finding is the same error-scope class one level deeper, across the nominal, random/QMC, and posterior evaluator boundaries. The shared type/category graph classifier widens the mechanism; it is not a message heuristic or per-exception-site patch. The removal-of-property probe replaced the helper with one physical call while retaining its counter update. The positive same-draw test then failed on the first sampled `PolicyOSError`, as required.
- **NEW_CLASS — public result history/versioning.** A current retried posterior result (`5` physical attempts, `1` retry) was copied in memory, both attempt fields removed, and the semantics literal reset to `one_evaluator_call_per_source_draw`. The current DTO accepted it as historical (`simulation_attempt_count=None`, `retry_attempt_count=0`). A dedicated result-schema discriminator, or an explicit decision that attempt history is optional/unverifiable for legacy-shaped records, is the smallest required follow-up. Keep it candidate-only; this is not an authority change. No such compatibility decision is accepted by this review.
- **P29/P33 removal control.** The retry property removal makes the real test red; the result-shape control establishes the separate historical-compatibility limitation rather than treating marker presence as proof.

## Verification

The retained focused suite was rerun against the current source with `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1`: **21 passed in 4.08s**. It covers classifier global precedence, shared exception DAGs, cycles/truncation, nominal and sampled retries, posterior row retry and physical-count validation, exhaustion, sampler non-retry, global failure persistence refusal, and legacy result parsing. Two exact original-B194 consumer tests also passed (**2 passed in 4.66s**). The additional in-process controls passed: real Sobol same-vector/no-redraw; mutable scalar kwargs; a transient root with a `PermissionError` cause classified global and attempted once; and the retry-result historical-shape downgrade described above. The no-retry removal probe failed the positive same-draw test as expected. No HMC or fitting run was performed.

## Source and companion footprint

These are the complete implementation/test/documentation paths reviewed, with current SHA-256 values:

| Path | SHA-256 |
| --- | --- |
| `src/polisyos/foundry/uncertainty/evaluation_failures.py` | `a371c4e8ad6ca37d3d94bb69fefad541c442fcec233c2a7305ea689fffca9050` |
| `src/polisyos/foundry/uncertainty/monte_carlo.py` | `f34de0be4d49f9d500f546e4471ae85918d0aebc7291fadb53093de2a0666199` |
| `tests/unit/foundry/uncertainty/test_evaluation_failures.py` | `265badd84d4ad7488cc6380a511b3abfee9cbc9870fe1d4b3b906814f241288c` |
| `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` | `c36a47ccedcde952de93c4385259ee46337a3f24e4fa722aac256f08016e3c16` |
| `src/polisyos/foundry/uncertainty/README.md` | `136249e7d9c81788dfeb8c30f3ff51770333fd20df5fae285b2c983f682cae46` |
| `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml` | `ccb2d22e8894fa5d1ca06229d9e9b621987cd5bf9205c41f1dec54e1764e7f26` |

The existing `tests/unit/foundry/uncertainty/test_monte_carlo.py` selector was also executed (SHA-256 `0fa296ed8499dcccc6a28ce971dfe2c7b3823a2db398c3147048afdf43ad8045`); it is not part of the six-path implementation/documentation footprint. The exact B194 decision input is `LOCAL/decisions/b194-exact-original-reproducer.md` (SHA-256 `552197e293c9ae5e57571678013d7db20f9f9c5c6bf048455d31b5ef08430119`). The register pass used P04/P05/P10/P29/P31/P32/P33/P38/P40; the relevant existing anti-pattern is conditional successful-subset output or transient retries being mistaken for unconditional authority. The target pattern is one shared typed failure classifier plus retained denominators and candidate-only partial status.

## Retained outputs

All fresh streams are in ignored `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b194-retry-independent/` (`.gitignore` rule at `policy-engine/.gitignore:151`). Full command, stdout, stderr, exit, and JUnit files are retained where applicable. Deciding output hashes:

| Probe | Output SHA-256 | Exit/XML |
| --- | --- | --- |
| `retry-focused.stdout` | `24d96cf4fe7ee60b083f66cd996444c4e6e7d37427d18301a29273d819c893fd` | exit `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`; XML `a950c826d00e3a56635e3c5996e4245211f1f3b711424f7da151996bcbe50b24` |
| `original-criterion.stdout` | `2fe563f3488a57f28342fe1201c1f68cc2914ac209bf8fb4adad52cbc0935a92` | exit `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`; XML `0e10bb6311b84818872005a0db09b40197307506bf1078df251a456fa24e8f89` |
| `behavioral-controls.stdout` | `1f3713c821cfae0b4a6b3facb07196c7cd63e0ca7686399be5ddcbf4655b242f` | exit `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `historical-shape-removal.stdout` | `2fac4544bc4b2591396c7ab3408e44902007e15c125b11f635d903f646c38e81` | exit `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `remove-retry-property.stdout` | `c9aa2e4979d9899e1a5906dc626111dd0f77695c5d7ee1812a4935d45b810ced` | expected test exit `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |

No source or test files were edited; the review and ignored raw receipts are the only outputs of this assessment.

## Counter-erasure delta review (2026-10-10)

This delta supersedes the earlier “historical result shape accepted” finding above. The current
`PosteriorPushforwardResult` now requires both physical-attempt counters, and the same parser rejects
a current result after both counters are removed and the old `one_evaluator_call_per_source_draw`
literal is restored. The prior concern is closed at this DTO boundary; this is not a claim of B194
closure or G acceptance.

The current model in `src/polisyos/foundry/uncertainty/monte_carlo.py` declares
`simulation_attempt_count: int = Field(ge=1)` and `retry_attempt_count: int = Field(ge=0)` without
defaults under `extra='forbid'`. The exported facade’s JSON schema lists both as required integer
properties (minimums 1 and 0). Its after-validator recomputes that the physical count equals one
selected-point evaluation plus source rows plus retries; zero retries require the original one-call
semantics, and positive retries require the bounded-retry semantics. `profile_version` remains
`Literal['1.1']`, and `gate_eligible` remains `Literal[False]`.

The focused current-tree rerun passed all three discriminating selectors (3 passed in 4.09s):
facade/schema export and required fields, actual zero-retry source-row production and stripped
payload rejection, and same-source-row transient retry with count/semantics mismatch rejection.
The zero-retry result was also generated from a real three-row posterior summary and serialized
through the public facade: the producer made four calls (selected point plus three rows), emitted
`simulation_attempt_count=4` and `retry_attempt_count=0`, and the exported DTO accepted the JSON
round trip. Removing both fields made that same payload fail with both required-field errors. The
focused retry test separately produces 5 physical calls for 3 rows plus selected point plus one
retry, then removes both counters and restores the old literal; validation rejects it. The existing
test also checks the valid 100-row zero-retry result reports 101 physical calls. All results remain
candidate-only and gate-ineligible.

The author’s retained compatibility red is the same three-selector command and failed all three
assertions: counters were not schema-required and both zero/retried results survived counter
erasure. The author’s following focused suite passed 21 tests. My 3-selector rerun and direct
public-facade probes pass on the current source. Full red/green streams remain in
`LOCAL/raw/b194-retry-compatibility/`; the independent focused/public-schema/public-facade streams
are in `LOCAL/raw/b194-retry-compatibility-independent/`.

Compatibility remains a release/migration impact, not a parser escape: `README.md` says there is no
in-repository persisted reader for this DTO and that uncounted legacy payloads are rejected by the
current DTO; if historical payload support is required, it needs an explicitly named limited reader
with attempt provenance `not_established`, not normalization into this current result. The release
fragment says old payloads require migration or recomputation and older strict clients must migrate;
it also leaves `public_surface_inventory_reviewed = false`. `profile_version=1.1` is the source
posterior-summary profile and does not version the output DTO. No compatibility adapter was found
in the uncertainty package. The G packet must retain the external-client/recompute choice as open;
this review does not accept that choice or clear the release inventory flag.

P40 disposition: the counter-erasure escape belongs to the same public-result-history class already
identified; the required schema plus recomputing validator now cover both zero-retry and retried
current outputs. The smallest relevant falsifier—delete the counters while retaining the old literal—
fails as required. The separate historical-client question is bounded and documented, with no
legacy reader in this package; it does not justify restoring permissive current parsing. P29/P32/P33
are addressed by exercising real producer output and the exported parser rather than schema-marker
inspection alone. No authority, confidence, or external-custody claim follows from this result.

Current source/companion hashes:
- `src/polisyos/foundry/uncertainty/monte_carlo.py` — `a2aacf8e01d0e71bd9707ced3c0d71577f16ed2cdea1a586a777f2a9b92eccc9`
- `src/polisyos/foundry/uncertainty/__init__.py` — `45ace7c8759d468214ceab42dc3a5cfe2c09bba85c5c5a5b9da7079aa76bbf1c`
- `tests/unit/foundry/uncertainty/test_monte_carlo_b194.py` — `c25eb001bcb4af04bdec3828c360b50c54b46acd04c88f8da53f6ba6e2c6610a`
- `src/polisyos/foundry/uncertainty/README.md` — `2b18b72bdbabf5c76643d8c973ba7dc44b135f6000e3c4cc534d6e1f22995386`
- `release-fragments/unreleased/2026-10-10-monte-carlo-global-failure-scope.toml` — `965348d27217929e83b89726b7e215c3554ffca03551b8bad4e3c713d1bd0777`

Independent decision-stream hashes:
- `focused.stdout` — `cef6f1e4c4a07db3fda069949f8787a36d970e69759fa8fcec321b6ce86a6723` (3 passed)
- `public-api.stdout` — `cf668863d0ebd7922b996a21e5f30443eb45a85fe658ca8a1c4c5386ca4fe012` (producer → exported DTO round-trip; erased counters rejected)
- `schema.stdout` — `cf45ab99d387e68b3db04b122b3d15c3bf45ff0f6f36034dbf1f3efcbce0de86` (required integer properties)
