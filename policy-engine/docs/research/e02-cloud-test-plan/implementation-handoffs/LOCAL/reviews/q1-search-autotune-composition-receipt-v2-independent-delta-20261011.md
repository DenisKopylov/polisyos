# Independent delta review: Q1 composition receipt v2

**Delta verdict: PASS for the bounded receipt.** V2 corrects the v1 ambiguity by separating the 31-pass earlier snapshot from the candidate-bound outcomes. I independently checked that its new per-run source qualifications match the retained command input maps. This does not establish whole-candidate/native readiness or G acceptance.

## Artifact identities

- Original v1 is preserved unchanged: `LOCAL/q1-search-autotune-composition-verification-v1.json`, SHA-256 `645ae47b07a5b6555e9eba2eaa7e1a760eefe88191277dc556f96211b19c16a4`.
- Superseding v2: `LOCAL/q1-search-autotune-composition-verification-v2.json`, SHA-256 `0be563c22992f8dd62de0bb44ab02e62b92fe8c5db02a885193c15f13bcf08b8`, 48,625 bytes. Its `supersedes` entry points to the exact v1 path/hash.
- The initial independent review is `LOCAL/reviews/q1-search-autotune-composition-receipt-independent-20261011.md`, SHA-256 `4cfce6388fb4076311bc31625f5b24fd9e893d242a6b82f591a9722e3a080871`; the JSON companion is `...receipt-independent-20261011.json`, SHA-256 `2fa369dae397ec4010a53f68f864b7f21f38a9066d5e2eef39cd6ec53c5d52f1`.

## Qualification check

V2 changes only receipt interpretation/provenance fields and the displayed deciding outcomes. The source candidate, tree, footprint, run records, output hashes, full 6,169-input comparison, LA-021 proposal, closure list, and G status remain the same as v1.

I recomputed the Q1-footprint comparison against each retained run map:

- Run 1: 19 footprint inputs compared; one mismatch, `tests/unit/remediation/test_srv_01.py` (`7ac1c504…` captured versus `3ce51560…` candidate). V2 now marks this run `historical_iteration_only` and moves its 31 passes into `prior_iteration_outcomes`.
- Run 2: 20 footprint inputs compared, zero mismatches; 33-pass JUnit remains candidate-bound for the captured Q1 footprint.
- Run 3: 20 footprint inputs compared, zero mismatches; one-pass corruption-control JUnit remains candidate-bound.
- Ruff: 19 explicit Python targets compared, zero mismatches; retained stdout is `[]`.

The complete run outputs were already reconciled in the v1 review: raw command records and output hashes match; JUnit suites contain 31, 33, and 1 tests respectively with zero failures, errors, or skips; each command's before/after input map is stable. The 31-pass run's earlier test-file bytes remain unavailable from its hash-only command record, so preserving it as historical rather than candidate proof is the appropriate boundary.

The wider captured source comparison remains 6,083 exact matches and 86 differing `.py` inputs, with no overlap with the 21-path Q1 footprint. V2 retains the explicit common-freeze/native-readiness limit. I verified the local source/remote readback and current branch again: HEAD and remote branch remain `c3f3f7d3ff2970daa44356535511ef1e84a2c1cd`, tree `4f5a90ba5627615d80effc8e1a7e4c96e6b56bb7`, parent `7296a02065fbdac778dae241b137182179667625`.

## Disposition

The v2 qualification resolves the receipt-level finding. The remaining 86-input difference is the already-declared broader-worktree versus partial-commit boundary, not an unreported Q1-path mismatch. **P40: SAME_CLASS_DEEPER, now bounded by the per-run footprint comparison; no further instance-level repair is indicated.**

The v2 receipt keeps `closure_ids: []`, `formal_g_adjudication: not_adjudicated`, and the historical LA-021 status held pending its separate Core/IR and profile/history evidence. I ran no tests, imports, Ruff, or builds in this delta review; I parsed v2, compared it structurally to v1, rechecked retained records and source-path qualifications, and read back the local/remote identity.
