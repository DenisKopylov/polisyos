# PAG static-profile source-lineage handoff

**Disposition:** committed, remotely read-back-verified 17-path checkpoint with a bounded tested source-lineage path. This is not a full E02 freeze, formal closure, producer-attestation claim, or broad PAG authority claim.

## Candidate and current evidence

The selected commit is `524caa44fd3b4172c3fd327ab0cddb8435b10512` (tree `46c633446eff2092635112334f4118d7d8d172ca`, parent `af1f92c82be5ee8e268945b0ce6c77dac9086b8c`), and `origin/codex/e02-unified-local-20261009` has the same SHA/tree and the same 17 selected file hashes. The local readback is `LOCAL/raw/pag17-implementation-checkpoint-20261011/readback.json` at `923cd62a784d730208193013e9760efa96b2adc3874abbfa5db96f2b73cf438f`; the remote readback is at `6a3af4da660388bd8aad4891e4a30db1675cfb56d847ac1df0a145ef0fb7ff42`. The selected precommit footprint is at `8db443c4b7bce74f8a3fd0d1672b7f2855ba62154dbb3078385aff5ed2f75b69`. All 17 candidate hashes match the current selected files and remote manifest.

The full focused run before the final style-only delta reports **620 passed, 0 failed/errors/skipped** in 12.091 seconds; its command/JUnit/stdout hashes are `c7eaee02c37524baa509e48e087a6d6bfe15490f8deb0fee06c84ecc8837d45e`, `9de69c12b954a34a0e596cddeab69cb0dd5fc755e5c98724e43db32ceecad918`, and `214eb2aceff7e31dfba6401616499a876fd708b5af7462c70efbf7569c0fef9f`. The receipt records 6,160 unchanged input paths.

After the style delta, the two PAG producer-to-fresh-CAS/compiler/strict-gate selectors report **2 passed** in 11.777 seconds; command/JUnit/stdout hashes are `acefaeb682de090a3a5dfa29b4ffd25b7918d623cf6d01ab977d63f1fbfc6c8a`, `b72e823249f5c03222e4dd013a24f6875846231c6c0dd2981972f6efeb84d7fb`, and `78a6f17583a53a93b819dbeca9979de222bbc392defd60ca2a14513ad020dd60`. The post-style Ruff command exits 0 with empty diagnostics (`3cc5899edc87fd4b3a8f8e5a0ec2faab0d21779e2926dd70f92bba8fe972831f`; output `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`). Its snapshot records 20 input paths and matches all 17 selected candidate hashes; it passes 15 explicit Python file targets. The post-style pytest snapshot covers 15 selected code/test files; the README and release fragment are not in that command’s file hash map.

Historical failures remain part of the evidence. The earlier V3 full selector run is **590 passed, 13 failed, 1 error, 0 skipped** (6,158 stable input paths; command/JUnit/stdout `597e252bd450bf2bf90e47d37cdf277bfdf7ec712140a19b136aeed8dfc65ef4`, `221378020ef4b008a646fa62c6c0e62fa84bea400d4478da9f2b3b06a155cb22`, `55357f37753fffb2f9f897a385d11471e65f609c5bd97c717fd8442b00dbae9f`). The V4 run is **604 passed, 1 failed** among 605 cases, with a 6,160-path denominator; the separate denominator erratum is `LOCAL/decisions/pag-v5-v4-run-denominator-erratum-20261011.md@22a5e55b23ce4cacb1a39817fbd44014554d89d17f4a1d3ab24139cfa03f02ff`.

## What the source chain establishes

The static ADMG guard produces the typed `unsupported_static_admg_profile` limitation. The controlled discovery path carries `oracle_needed` through the real utility judge, aggregator, and `GraphPriorBuilder`; `DiscoveryArtifactBuilder` persists the selected source chain with profile-bound refs; a fresh CAS consumer recompiles cross-graph evidence and the strict pass retains `INSUFFICIENT`, expert review, and blocker outcomes. The test-only whole-chain witness verifies exact selected manifest edges, not just role presence.

The profile ref has a narrow meaning: it is a **reader-materialized exact view after successful immutable CAS write or reuse**. The helper derives the stored manifest profile, resolves that selected view, and verifies integrity. It does not prove that this invocation uniquely created the object, attest producer intent, or establish external causal truth.

The current consumer recomputes the selected matrix, GraphPrior projection, and identification status from the loaded source views. It does **not** independently recreate every utility score channel or all production inputs used to form the utility report/bootstrap scores. The V3/V4 source-binding reviews keep that residual explicit. Broader PAG/CPDAG completion, temporal-PAG inference, and institutional/live-world facts remain unestablished.

## Original IDs, review boundaries, and open state

B214 remains the query-specific partial-graph boundary in the unified decision record. B216, B217, and B220 are carried as historical IDs from the earlier static-profile slice and are not newly closed here; its bundle references are GRF-01/GRF-02. The committed readback has `closure_ids: []` and `full_composed_freeze: pending`. The selected 17-path readback does not freeze the broader shared worktree or certify whole-candidate source/input/backend completeness.

Independent review receipts are bound by exact file hashes in the companion JSON. Key outcomes: the V3 source-binding review was partial/static only; V4 approved exact-view selection with the explicit no-attestation boundary; V5 was NO-GO for role-presence identity; V6 was approved for execution and has the later passing receipts above; the canonical style review is followed by the post-style two-test and Ruff receipts. The original V5 hashes `9fccecb6…` / `8702e30b…` and the reported `b7bd4492…` note bytes were not recovered. Available refinement bytes are recorded as patch `41445571…` and note `88d995a4…`; no claim is made that the missing V5 artifacts were restored or reviewed.

Pattern pass: P32/P37/P38/P40. The repair widens exact source binding and recomputation through the whole selected edge set rather than trusting labels or adding role-by-role patches. The remaining full-composition gap is `verification_missing`; broader PAG/temporal capability is `absent/unallocated`; an external institutional-authority surface is `surface_out_of_scope`. This handoff adds no closure ID.

The companion `LOCAL/pag-static-profile-source-lineage.json` contains the complete 17-file SHA list, exact run/review receipt identities, typed predicate classifications, and bounded residuals.
