# F original criteria: current source-delta assessment

**State:** read-only; current semantics unrun; no closure proposal. Denominator is 35 IDs / 36 criterion occurrences / 35 source blocks. LA-016’s two bindings are preserved separately (`CAU-01`, `coverage.json#/findings/240/criterion_refs/0`; `CAU-05`, `coverage.json#/findings/240/criterion_refs/1`).

## Source binding and candidate boundary

The original blocks are bound to B_r19 and LA_r09 at commit `198076863e143dea9f89f02734b13d50dae3eed5`; the complete-file SHA-256s recompute to `9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5` and `2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727`. Every occurrence row carries its source span/block hash, exact coverage and ledger pointers, source-author property, producer/artifact/bridge/consumer/surface, F receipt extent, decision boundary, selector files and next discriminator. See [the compact occurrence matrix](full-id-F-current-source-delta.json).

The comparison receipt pins b2 `b2cd1fbb0c9aaa21a05cbf999330a2e07fe81f23` / tree `65c44e4872c0efb0772ee955c2b92351c2486892`. The parent supplied `HEAD4699+WIP` as a label; I did not query Git, so that label is not independently verified here. `source-composition.json` is a changed-path/hash footprint rather than a whole-tree snapshot: 627 b2-pinned entries, with 73 current-byte mismatches and zero missing files. The matrix includes exact hashes where the changed-path receipt supports comparison and makes no equality claim for omitted paths. This local readback is not a frozen-candidate behavioral result.

`full-id-F-assessment.json` records candidate b2 semantics as UNRUN for every F occurrence. F’s historic PASS/closed labels remain bound only to the old source/profile/input/consumer receipts. Formal G finding acceptance is not issued and G code acceptance is not inferred.

## Delta and executable boundaries

Current test selector groups and exact owner/dependency deltas are joined in the JSON rather than copied into each occurrence. The prior F assessment says the shared Core ArtifactStore/dispatch boundary is applicable to exactly 29 rows with a CAS/MethodJob/FileSystemCAS chain; selectors are `test_async_store.py`, `test_manifest_lineage_input_normalization.py`, `test_transfer_import_fresh_process.py`, `test_manifest_serialization_schema.py`, and `test_dispatch_output_contract.py`. They were not executed here. A current shared bridge delta requires fresh producer→artifact→reader replay; the unchanged analytical owner alone is insufficient.

Each `next_check` is a property discriminator, not a test result: e.g. ATT=3 with zero-pre refusal, actual unit-cluster covariance, requested DiD/RDD levels, selected-cohort unit draws, centered-null p/interval inversion, fixed-profile sharp RBC, genuine DoWhy worker point-only behavior, endpoint-aware graph queries and surgery, fitted empirical root-law through fresh CAS, keyed parallel edge persistence, actual result/report lineage, named economic baseline preservation, and supported symbolic/archive consumers.

S1 intersects this F queue only at B214. B31 subject, B161 refinement, and LA-023/032/036 remain separate. S2’s B157/B190/B194/B197/B200/LA-036 are separate; their Monte Carlo or empirical-law evidence does not transfer to B207/B208 inference or B221 fitted root-law custody. V5 B108/B157 are independent Search/funnel criteria. R4’s B56 needs the actual configured shared-cap study/fold workload. R3 B10/B66/B67/B68 remain separate monetary criteria.

For LA-019/020/037, the discriminator retains exact named sibling files, real filename loader/source inventory, explicit supported exports, FQN/object identity and source/wheel/sdist consumers. Lexical imports and archive markers do not establish external clients. LA-017’s norm diff/report consumer remains separate from current law, jurisdiction, issuer and effective-time inputs. LA-003/004/035 retain existing model/baseline semantics; no fiscal norm, calibrated superiority or new welfare objective is inferred.

## Pattern and capability status

P01/P02/P03 require an actual producer→persisted artifact→bridge→fresh consumer chain; P04/P05/P10/P15 preserve unknowns and authority boundaries; P07/P08 preserve version/time; P14 separates synthetic agreement from real support; P29/P32/P33 require behavioral negatives; P35/P37/P38 keep the denominator and measured gate predicate visible; P40 is the recorded `SAME_CLASS_DEEPER` shared candidate-source-freeze/provenance gap, not 35 product defects. Widen once to all 35 IDs/36 occurrences and their source/test/config/lock/consumer evidence; if evidence cannot be admitted, keep the full set `target_not_evaluated` and run the removal/falsifier check. The existing LOCAL proposal machinery is present but was not run here, so output-only status is not evidence that the capability is absent. Retain B56 `UNRUN` and B214 `limited` absent their own results. P41 prohibits inherited labels without slice-base replay. The current state for all 36 occurrences is `verification_missing`; this review makes no instance-level repair or scientific/legal claim.

No tests, native fits, Git commands, source writes or test writes were performed.
