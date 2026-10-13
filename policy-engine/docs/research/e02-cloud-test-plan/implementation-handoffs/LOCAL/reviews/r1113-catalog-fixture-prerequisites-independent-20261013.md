# R1113 independent review: catalog fixture directory precondition

Verdict: **GO for Root's actual native replay only.** This review does not establish runtime success or close a finding. closure_ids=[].

The proposal fixes the directly demonstrated fixture failure. In R1106's retained JUnit output (5 cases: 2 pass, 3 fail), all three new HTTP cases fail before the producer starts: _actual_scope_catalog attempts to write catalog/registry.yaml under a nested path that the caller has not created. The patch creates that shared root with parents=True, exist_ok=True before either profile branch. Both producer paths and snapshot_root then use the same root. The snapshot path is unchanged in meaning, and the patch leaves the real producer, API app, HTTP route, fresh reader, and all existing assertions intact.

I inspected the complete _actual_scope_catalog helper and every test call site. Existing callers pass pytest's already-created tmp_path; the HTTP helper alone passes the nested tmp_path / catalog in both branches. DatasetBatchConfig creates its own publisher output directories after construction, while the registry write happens before that constructor, matching the observed failure boundary.

P40 bucket: **NEW**, a fixture filesystem-precondition class, distinct from the prior format-only issue. The bounded quantity is one helper, its two producer branches, and the three HTTP cases that use it.

Exact source binding: HEAD 808225e86db87a557e39afdf38f22c40a364cf77, tree 047ea0dff5b33068ffa7c6eea92581002bc3c684, R1105 frame root-author-source-frame-r1105-20261013.json@d7e9ead894477fd5a679e3d7acb68422ece36c361e13a7d2e7dd1afe00e4e884. All 11 current files in the submitted direct fixture/producer/API footprint matched their declared hashes. The single changed test file preimage hash matched; applying the patch in memory reproduced candidate hash da373550c49fa9e084b15f7c3fd277fe2ddc4d5e0c1d1b2f40824900c3dfdd3e (9,810 bytes).

Checks on the exact candidate: git apply --check passed; stdlib AST parsing passed; configured Ruff check and format check passed. I did not run pytest, product imports, or native tests under this review lease. Root should run the actual three cases in the composed source freeze before treating the companion as verified.
