# Independent Welfare admission/report review

## Scope and source identity

Read-only review of the Welfare admission/report delta in the shared candidate checkout at:

- Candidate path: /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
- Parent-supplied source context: own candidate HEAD 4699 / current WIP. Git was outside this review’s permitted operations, so this packet identifies the reviewed source by exact file SHA-256, not by a newly asserted commit/tree.
- Product source hashes are recorded in LOCAL/raw/welfare-current-review/source-hashes.txt @ ba51de97449ffd08d6f7d8351fe9393b3d22dfa2c71590ebf6ed5c0bc86b8e46. The five relevant implementation files are welfare_context.py @ e8abc741bce3ae06de269070b4b0577475b4ad4a1cd04e9ea575f94dbc5b500c; welfare_propagation.py @ b1a9570a2bac671c01824c7a5b723196195ca7754eceadb17c58ea9590a1b70b; welfare_draws.py @ 42749968e953eb879c73a817fae1250fbd0d772cc846720cb984cbc5f7241bac; welfare_reports.py @ 81b106a36385e5599a6ac9db9437939865cd64211a83d3809688ab038f6373e8; and foundry/uncertainty/evaluation_failures.py @ a371c4e8ad6ca37d3d94bb69fefad541c442fcec233c2a7305ea689fffca9050.
- The E11 release fragment is release-fragments/unreleased/2026-10-09-e02-e11-welfare-monte-carlo-truthfulness.toml @ 0ce07acaa2d33e351e910b4759a38bde9475a01d2505535f6c23f9231c2f5eea.

No product source or test files were changed by this reviewer. Only this review note and files in ignored LOCAL/raw/welfare-current-review/ were written.

During review, the two companion test files changed concurrently while the five implementation hashes stayed identical. Current test hashes are in the source-hashes manifest. The context test changed from f6f2d5e473d627ba24bf03d0d35ad5c790c40140dd41e11abdf2845dff3c7dc7 to eae01d14c70b1b210bc774adc77dc602574041fe51ab400437a2a028617ae4f2 and adds an empty-response test; the reports test changed from 518924c92de62d0278f4e10ca60cf0e1ecd5ec632aab58f765ed9a9acb3967b to 042bb414cafc9c6e662003552d023e1b9dce9b2f29a6f219ccec8a81b1617934 and adds failed/unattempted partition assertions. Those new assertions had not been run by the earlier 39-test receipt or my focused pytest runs; the unchanged implementation currently contradicts them. The earlier pass receipts therefore describe the previous test bytes, not the current test set.

## Findings

### SAME_CLASS_DEEPER — supplied malformed Welfare inputs can still be accepted as defaults or numbers

The intended absent-versus-present handling is substantially improved: _resolve_base_response distinguishes key presence and refuses null/non-mapping/non-sequence values; _resolve_weights defaults to unit weight only when the key is absent for a single label and refuses explicit null; _resolve_pe_sensitivity applies identity defaults only when absent and validates a present mapping; _resolve_requested_welfare_method rejects null/empty/unsupported explicit method strings before consumer dispatch.

The whole input boundary is not closed:

1. welfare_reports.py::_load_propagation_config (lines 66–83) catches validation failure for a supplied propagation_config dictionary and silently returns default PropagationConfig. With raw {mc_n_samples: -1, preferred_method: "monte_carlo"}, the actual resolver returns preferred_method="auto" and resolved method="auto"; with preferred_method=42 it also returns "auto". This bypasses the refusal for an explicit malformed configured method. The exact product-venv probe is LOCAL/raw/welfare-current-review/boundary-probes.stdout.txt @ 52ed767b634312dbc97e510295f11f8eee7092af1d330a71f877b740a66c8c68; full probe source is boundary-probes.py @ 507c1d4626535146f85f2117b249c020be6094085c36314acde7c428bbd7af05.
2. _resolve_base_response accepts explicit empty response containers as an empty label/vector pair. Full _resolve_welfare_context also accepts explicit pe_response=[] with weights=[] and pe_response={} with weights={}, returning labels=(), response_vector=[], weights_vector=[] while a fallback metric exists. This is not a missing-field default; the malformed supplied basis is admitted as an empty Welfare context.
3. The response and weight parsers use float(value) without rejecting bools. _resolve_welfare_context accepts pe_response=[True], weights=[True] and computes aggregate 1.0. The neighboring sensitivity parser explicitly rejects boolean coefficients, so the bool policy is inconsistent across the same numeric input surface.

The exact source witnesses for (2) and (3) are in the same boundary-probe output. The review’s own product-local module-origin receipt confirms tests and probes import implementation from the candidate’s policy-engine/src tree: module-origins.stdout.txt @ c78bb150c3cb21357658b169d98b712ee81062fc55681f5b3841c363c7bef0b2.

P40 bucket: SAME_CLASS_DEEPER, present malformed input is still being collapsed into an omission/default or coerced into a plausible number on sibling input paths. This is a class-level gap, not a request for more individual-value patches. Proposed next check: one typed supplied-input admission boundary must preserve defaults only for absent optional fields, reject invalid supplied propagation_config before method selection, require a nonempty response basis, and reject boolean numeric values for response/weights. Preserve existing typed welfare refusal codes. Re-run the removal-property control after the repair, and run the current newly added empty-response test plus config/bool adversarial siblings. The current empty-response test checks only _resolve_base_response; it does not yet assert the complete _resolve_welfare_context behavior with empty weights.

### SAME_CLASS_DEEPER — failed and unattempted draw counts are not a disjoint requested-denominator partition

welfare_draws.py::_draw_outcome_provenance (lines 889–912) calculates failed_draw_count as requested_draw_count minus successful samples, then also publishes unattempted_draw_count as requested_draw_count minus attempted_draw_count. An independent product-venv probe supplied a coherent internal ledger with three requested draws, two attempted successful terminal rows, and zero failure rows. The emitted counts were successful=2, failed=1, unattempted=1, so the three categories sum to four while the terminal ledger contains zero failures.

This violates the report’s separate failed/unattempted fields and the release fragment’s reconciled requested denominator claim. The source should derive failed count from non-success terminal outcomes (or explicitly define a different non-partitioning field name/semantics) and preserve the invariant successful + failed + unattempted = requested. The raw witness is boundary-probes.stdout.txt above. Current test_welfare_reports.py now asserts the expected partition in test_unattempted_draws_remain_partial_in_fresh_report_reader, but the current welfare_draws.py hash still uses requested-minus-successes; that test has not been run against the current test bytes and should fail until implementation catches up.

P40 bucket: SAME_CLASS_DEEPER within the report’s draw-ledger reconciliation property. The original checks now validate most identity/counter/value relationships; the remaining error is the mutually exclusive category calculation for incomplete denominators. Do not treat the new assertion alone as code acceptance.

## Verified behavior and consumer boundary

The author’s previous-source focused output final-focused.txt @ 995124eb63e1dfa9035b05ad234af6fe95911dc94ce0d913144d4d36d7531550 reports 39 passed across the Welfare helper, node, and facade tests. The counted helper subset reports 31 passed (semantic-focused-counted.txt @ 760d751b568b8820c01684ef6d79ee4a3aba6be81b6216ebc375a9c0be1b4372); the draw subset reports 2 passed (draws-focused.txt @ 396d08627f001d33cf4d79c689f0d6999b85cd5f822955e62ac960b84dd59df4). These are pre-concurrent-test-edit receipts. The release fragment claims internal-only behavior and no HTTP/OpenAPI/client changes; this review makes no claim about those external surfaces.

I independently ran the candidate-local fresh-CAS producer/consumer case:
PYTHONPATH=src:. .venv/bin/python -m pytest -q tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py::test_partial_welfare_draws_retain_terminal_outcomes_after_fresh_cas_readback

It exited 0. Full stdout is fresh-cas.stdout.txt @ ff7302cd30f5584f99f3c484fb2eb2493668d64974a47e551af41fcc1eab3ed5; status is fresh-cas.status.txt @ 418a5c17f33c70e99b0cc0a07fce69191489cfedc94164bfa903785777c5bd4b. This actual producer runs a requested 100 draws with explicit sample-domain failures, persists sample/report/bundle artifacts, opens a fresh FileSystemCAS, loads the partial bundle/report, and calls the Welfare summary consumer. It checks no credible interval, a nominal point estimate, the partial status/warning, terminal rows and sample indices, and manifest links. This covers the all-attempted partial path; it does not validate the unattempted denominator partition, API/browser surfaces, production currentness, or scientific authority of a consumer-asserted sample-domain declaration.

I also executed the current semantic tests with their properties disabled while leaving their assertion code intact. Three expected red controls were observed: malformed response fell back to the metrics result; unknown configured-at-entry method reached Monte Carlo instead of refusing; and a partial draw record accepted the claimed complete flag. The exact temporary monkeypatch probe is removal-control-probe.py @ 7e46c59c392617fdcfbe6fa7a12d228b65e194a3d4631de991ef52859169c5fc; full output is removal-control.stdout.txt @ 44985562fc0991e746f203ad34ccf742cf093598aeef3f79ec2eeb4486582a66; status is removal-control.status.txt @ 418a5c17f33c70e99b0cc0a07fce69191489cfedc94164bfa903785777c5bd4b. These controls exercise the then-current test bytes; the later test additions are not covered by that receipt.

## Shared failure-classifier interface

The Welfare adapter in welfare_draws.py calls the shared classifier with sample_domain_error_type and additional_global_error_types=(_WelfareNodeFailure,). The latter argument has a default, so the existing generic Foundry callers continue to use the one-argument interface. The adapter consumes the classification scope, bounded chain, completeness, and cycle state without an interface mismatch.

A complete Python-file census over 7,470 files found classifier references in the shared implementation, four generic Foundry Monte Carlo call sites, the Welfare adapter, tests, and ignored historical raw evidence; it found no runtime_v1_v2 service caller. Census output: classifier-caller-census.txt @ 7526a6b43abdd87cbb77f81c3966de8dc161ec66acc2f30f8179e50d55b5c83b. Product modules imported from the candidate .venv and src tree, as recorded above.

The shared classifier’s four unit tests plus Welfare’s same-draw transient retry/fresh-CAS test passed in one focused command; output classifier-retry.stdout.txt @ 08ee742cddf2b87546c3a2a55ee1d92ad4195aa5dfab1d46d080b5a963b8fb9d, status classifier-retry.status.txt @ 418a5c17f33c70e99b0cc0a07fce69191489cfedc94164bfa903785777c5bd4b. The generic Foundry same-draw transient retry test also exited 0; output foundry-retry.stdout.txt @ 423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d, status foundry-retry.status.txt @ 418a5c17f33c70e99b0cc0a07fce69191489cfedc94164bfa903785777c5bd4b. These establish compatibility for the current Python call graph, not runtime_v1_v2 capability acceptance.

## Closeout proposal boundary

For B194/E11, this review supports only candidate-level proposals: limited/held on supplied-input admission because malformed sibling paths still fall back or coerce; held on truthful denominator partition because failed and unattempted counts overlap. The current fresh-CAS all-attempted partial path and shared typed transient retry are positively evidenced at the hashes above. No formal G closure is proposed or adjudicated here; G retains source acceptance and finding closure.

## Delta review — widened malformed-input and draw-denominator repair

This append-only delta supersedes the earlier WIP conclusions above for invalid present propagation configuration, empty response/weights, and overlapping failed/unattempted counts. It does not convert those observations into G closures.

### Reviewed source and test identity

The parent supplied own-candidate WIP source (HEAD context `4699`); Git inspection was outside this review's permitted operations, so this is a byte-identified source review, not an asserted commit or source freeze. Current source hashes:

- `src/polisyos/scientist/nodes/builtins/simulate/welfare_context.py` @ `683711d97cae99b019cf96a055b2d108628f39cdacb5a510aa271046a84c4254`
- `src/polisyos/scientist/nodes/builtins/simulate/welfare_reports.py` @ `1912854649e06f5c55e6680ca9a1bb6f8b6d70a42dd01878270a1393e0fe1bc1`
- `src/polisyos/scientist/nodes/builtins/simulate/welfare_draws.py` @ `43554e3df35b400091d7d1d8c5ddea3af1cf7c3489f7110d4503efbac42edd9f`
- `test_welfare_context.py` @ `509fbbd0a5661c7ecc0e09ccb7337723ce164ffb1bf8d352fbbd6e78207cafef`; `test_welfare_reports.py` @ `c80870eaaf44b37c72a1be148c8dcc310615fe6f82fd0b82117c2172c9fb2697`; `test_welfare_node.py` @ `3a000ce251bdf3fff5d1bc8e2fc7a7ac39dc4fd2f45039a83e9da3eb1636aa22`.

The author’s latest product-venv focused receipt is `LOCAL/raw/welfare-current/final-focused.txt` @ `9e67bbe94a3516eb9f513f453d0f5c50f6a26b467bf25d6c1296538e2b147800` (49 passed, 2 warnings, 6.61s). It matches the three implementation hashes above. I independently ran the narrower listed tests and controls below, so this receipt is corroboration rather than the only basis for these findings.

### Prior defects now fixed on these source bytes

- Supplied `propagation_config` now goes through `_validated_propagation_config`; only an absent config uses default `PropagationConfig()`. The actual node test for malformed present config passed all four cases (negative sample count, invalid preferred method, null, non-mapping). Command and complete captured output: `LOCAL/raw/config-refusal-focused.txt` @ `613925a2f724ea9f04f19e5da95aa8a00bfa766b440028b87d82a43b3583a1f4`, exit 0.
- Empty supplied response and empty weights are rejected by the boundary helpers. Four cases passed: `LOCAL/raw/welfare-current-review-delta/empty-basis-focused.txt` @ `7863ff4d209fc277ac9f6264a0de9fec13734cc308e4290b23c38441888113b4`, exit 0.
- Draw outcomes now require terminal-row count to equal attempted count; `failed_draw_count` is the number of terminal rows whose code is not `success`; `unattempted_draw_count` is requested minus attempted. Thus `success + failed = attempted` and the reported categories partition requested. The report consumer recomputes this expectation before persisting, and the fresh `FileSystemCAS` read returns it unchanged. The no-failure/unattempted case passed: `LOCAL/raw/welfare-current-review-delta/fresh-cas-partition.txt` @ `db996c267fd0de6a945f0154a3019d03939ecb8bf5c9e96b4a0da2213dba0f14`, exit 0. The one-non-success-terminal/no-unattempted case passed, including `failed == count(outcome_code != "success")` and the same partition assertion after fresh CAS read: `LOCAL/raw/welfare-current-review-delta/non-success-terminal-partition.txt` @ `cd199b2de6af4ec6310457d280829b2a003022f82603ec344210da6445317442`, exit 0.

### Same-class residual: boolean coercion remains in supplied numeric response/weights

The prior malformed-present-input finding is improved but not fully closed. `_response_from_sequence` and `_response_from_mapping` use `float(value)`, and `_resolve_weights` does likewise. A direct candidate-local probe supplied `pe_response=[True]` and `weights=[True]`; both were admitted as `[1.0]`, producing aggregate `1.0`. The exact probe is in `LOCAL/raw/welfare-current-review-delta/removal-controls.txt` @ `fa978f640bdf5732ffac14acc66d9c2470cf988b37661c72281ae33c9adec06b`, produced by `delta_controls.py` @ `94682745a4eb96d7d29fb77dd8d0e939b305dfc9dbf407174864975d1fd07daa`. These helper paths are called by `_resolve_welfare_context`. The neighboring `pe_sensitivity` numeric parser explicitly refuses booleans, so current admission is inconsistent across the same Welfare context.

P40 classification: **SAME_CLASS_DEEPER residual** in malformed supplied numeric admission, not a new issue category and not a request for another per-field/per-value patch. Confidence is high for the coercion behavior; severity is medium because a supplied boolean can silently become a plausible Welfare response/weight and change the resulting aggregate. The whole class remains open at this boundary. A bounded closure would use one strict finite-numeric admission rule across raw response and weight shapes, then show `True`/`False` refusal for mapping and sequence forms while preserving valid integer/float inputs; otherwise keep this explicit residual for G. Do not infer that the author’s 49-test pass covers booleans: the current named tests do not exercise them.

### Property-removal controls and independent output

I ran unchanged test assertions after disabling each runtime property in memory (no source/test edits): (1) replace present-config validation with default fallback; (2) replace both empty-response parsers with empty-vector acceptance; (3) restore `requested - successful` as failed count while retaining the current unattempted count. The first two controls made all four invalid-config cases and both empty-response cases fail respectively. The denominator control made the fresh-report test fail because the supplied partition no longer reconciled with the helper’s recomputed provenance. The complete outputs include the individual failures and control labels; the wrapper exits 0 only when each expected-red control is observed. Command was `PYTHONPATH=src:. .venv/bin/python docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/welfare-current-review-delta/delta_controls.py`; output/status are in the receipt above. Pytest emitted only the already-imported jaxtyping assertion-rewrite warning during this in-process control run.

These probes establish that current tests detect removal of the three repaired properties while their test markers/assertions remain. They do not close the boolean residual, prove installed-wheel behavior, or certify a broader Welfare surface. No formal G closure is proposed or adjudicated; G retains independent acceptance and finding closure.
