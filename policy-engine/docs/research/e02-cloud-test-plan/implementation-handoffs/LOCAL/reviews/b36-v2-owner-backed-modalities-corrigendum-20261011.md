# B36 V2 owner-backed two-modality evidence corrigendum

Status: **append-only evidence correction; no source change and no formal closure.** Created 2026-10-11 for the E02 closeout handoff.

## Identity and correction

This note supplements, and does not edit, the B36 V2 candidate packet:

- V2 manifest: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b36-required-modalities-all-source-union-v2-20261011/manifest.json` @ SHA-256 `304b5c226b7416846709982927dce71a2da8b32a8744b1d03de75013ad66d3ce`.
- V2 candidate patch: the adjacent `candidate.patch` @ SHA-256 `30f05fbd7f2a56d3b8595ef2ec075c16e9de4ab40b0e63a27c3ee6d2c95f4581`.
- Candidate slice base: `827c709eb926d5bd3a4d7418630ffe56904bc130`; candidate advisor postimage SHA-256 `76b50899f75699671509e587d3be3f83ee370ce624e6e05bd42326cd1a198368`.

The first `limitations_and_next_checks` statement in the V2 manifest says no owner-backed registry method was demonstrated to satisfy simultaneous `panel` and `tabular` modalities, and characterizes the positive as synthetic-only. The no-method claim is **superseded and false** in light of the actual owner-backed catalog and consumer probe below. The narrower statement about V2's own newly-added unit positive remains accurate: that particular test uses a synthetic catalog entry. It is not the only evidence for this property.

## Source-bound evidence

The read-only probe called the real `build_method_catalog_snapshot` and `select_value_method_for_problem` APIs with the V2 candidate advisor loaded over the slice-base source. Its command record identifies base `827c709eb926d5bd3a4d7418630ffe56904bc130`, the exact candidate patch SHA above, exit code `0`, and elapsed time `15.729859875` seconds:

- Probe harness: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b36-independent-review-v2-20261011/actual-owner-all-sources-consumer-probe.py` @ SHA-256 `1e01b5d795c181313342ed5e868b3a5257898294c828cf2f197eadbf0e511476`.
- Command and exit record: adjacent `actual-owner-all-sources-consumer-probe-command.json` @ SHA-256 `1d1f150b700b8b4ece6dcf2c2e0857ea8c48596f90cc7cb9ce862c3087a9e867`.
- Complete deciding output: adjacent `actual-owner-all-sources-consumer-probe.stdout.txt` @ SHA-256 `b95a7344e73ab3de4dabc22e2cda6fe296b9d49898cfdac4871bc1e28b989d9d`.
- Candidate/source-origin check: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b36-required-modalities-all-source-union-v2-20261011/candidate-source-chain-origin-v2.stdout.txt` @ SHA-256 `a1c8b34c059de723dc9e373b74d0709d9227e36697a93df7a578b48830c3a74c`. It binds the candidate advisor bytes and reports the catalog snapshot and selection registry resolving from the source modules.
- The prior independent review note, which records this probe and its boundary: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/b36-required-modalities-all-source-union-v2-independent-review-20261011.md` @ SHA-256 `a19dca5866769df087d5ebacaf375b93eb25329086a6301cac84ad25352023d3`.

The complete generated catalog contained 389 rows; 55 were owner-backed value entries, and 9 of those had both `panel` and `tabular` modalities. Against that catalog, with candidate signal `panel`, runtime hint `tabular`, and projected manifest targets containing both, the explicit-FQN route selected `econometrics.panel.difference_gmm@1.0.0`; the ranked route selected `econometrics.panel.fixed_effects@1.0.0`. Both returned `status=selected` from their respective selection sources. The complete output lists all nine qualifying FQNs.

## Bounded interpretation and remaining checks

This evidence corrects the catalog-availability and actual-selection witness only. It does not claim modality transformation, method execution, successful model output, causal validity, production currentness, or publication authority. The V2 source remains a candidate patch, and this probe is not a full route/integration receipt. A source-bound regression test should retain a real owner-backed two-modality method on both the explicit and ranked routes when the source candidate is admitted; the broader runtime integration and canonical formatting gate remain separate checks.

`closure_ids` remains empty. `proposal_ids` remains `B36`. G retains independent code acceptance, integration publication, and formal finding adjudication.
