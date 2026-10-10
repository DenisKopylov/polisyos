# DX6 independent delta review

Review target: `e89927b645469f1981750e7d13ae5cdfc590b7e` (tree `932078c9ad34a93b6bb36eb619e14ebb209967ff`), parent `314dc4100a1982cac1d2ddcdde230f2b9ba71a06`.

The tests and collection comparison ran at root-authored descendant `cf949d4a10869d0f992d111cbf1f35fa89a84b30` (tree `fda95489c4f777ef647ddc12e4b8c07d3e5c2627`); the assigned commit is its ancestor. Before receipt readback, the root advanced the branch to `8e69d23ee61a640621a487243a59107f0d1f232f` (tree `4ccdbe603115ab9a018f8c330f9608a7e21ac22b`). The assigned commit remains an ancestor, and all eight scoped paths plus `.pre-commit-config.yaml` remain byte-identical and clean. Peer changes outside those paths were left untouched.

## Independent code assessment

**Pass for the root-mode Ruff parity property in this delta; no new blocking code gap found.** The generator now takes product-root `cache-dir` and `src` from the manifest, renders the product-root config from those settings, and emits caller-root-adjusted settings for the Git-root config. The workspace config extends the same canonical Ruff base and per-file-ignore fragments. Effective settings, include/exclude behavior, per-file ignore matchers, collection, and real import-sort behavior are compared through Ruff itself.

The test excludes only the two caller-specific `project_root` settings from full settings equality; it separately asserts the expected root for each caller. It also compares all effective per-file ignore matcher/code records, including Ruff's negation bit, tests the full `--show-files` sets, and runs a real `I001` check plus a temporary test-file suppression probe. Existing ignore fragments are not changed by this delta. The base still declares `ignore = []`; no blanket ignore or expiry change was introduced.

The candidate's unchanged `.pre-commit-config.yaml` selects `policy-engine/architecture/tooling/ruff/workspace_root.toml` for both Ruff hooks, and the committed test reads that same hook argument rather than hard-coding a substitute.

The current product-root manifest declares `cache-dir` and `src`; it has no explicit root `include`, `exclude`, `extend-include`, or `extend-exclude` values, and the base has no explicit include/exclude. The test compares Ruff's complete effective include/exclude settings and collection under both roots. The unchanged per-file fragment census and its pattern classes are recorded in the prior receipt, [dx0-review.md](dx0-review.md); this delta does not edit those fragments.

The generated-artifacts companion is now present: `workspace_root.toml` appears in both the registry's generated-config family and the detailed outputs list in `generated-artifacts.md`.

## Distinguishing evidence

The complete `ruff check --show-files` comparison passed at worktree HEAD `cf949d4`: product-root discovery from `policy-engine` and Git-root explicit-config mode both returned 7,342 paths, with identical normalized absolute path sets. A complete suffix walk of that `policy-engine/` tree found 7,327 `.py`, 5 `.pyi`, and 10 `.toml` paths. This denominator includes peer work present at `cf949d4`; it is not claimed as the candidate commit's file count. The scoped config and test sources used for the comparison match the assigned commit bytes.

For exact candidate-commit source contents piped to Ruff, product-root discovery and the correct Git-root explicit config both returned no `I001` diff for:

- `src/polisyos/ddm/contracts/metric_budget.py`
- `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`
- `tests/unit/scientist/search/funnel/test_level4_full.py`

I then used a temporary config outside the repository that extended the correct workspace config and overrode only `src = ["."]`. This retained the base rules and all per-file ignores while corrupting the source-root setting. `--show-settings` reported the Git root alone as `linter.src`; Ruff then emitted an `I001` diff for each of the two production witnesses. The third file remained unchanged. The exact distinguishing output was:

```diff
--- policy-engine/src/polisyos/ddm/contracts/metric_budget.py
+++ policy-engine/src/polisyos/ddm/contracts/metric_budget.py
@@ -2,9 +2,8 @@
 
 from __future__ import annotations
 
-from pydantic import BaseModel, ConfigDict, Field, model_validator
-
 from polisyos.ddm.contracts.events import MetricDirection
+from pydantic import BaseModel, ConfigDict, Field, model_validator
 
 
 class MetricBudgetPolicy(BaseModel):
```

```diff
--- policy-engine/src/polisyos/runtime/http/services/governed_projection_validation_worker.py
+++ policy-engine/src/polisyos/runtime/http/services/governed_projection_validation_worker.py
@@ -657,12 +657,13 @@
 ) -> dict[str, Any]:
     """Run the real N11 validator and freeze source/request arithmetic facts."""
 
+    from tools.quality.validation.check_layer3_gy_confidence_ledger import (
+        validate_payload,
+    )
+
     from polisyos.runtime.quality.confidence_ledger import (
         ConfidenceLedgerSemanticReceiptProjection,
         load_confidence_ledger_registry,
-    )
-    from tools.quality.validation.check_layer3_gy_confidence_ledger import (
-        validate_payload,
     )
```

This is the marker-preserving falsifier for the measured property: the config still carries the same rule and ignore markers, but the wrong `src` root changes actual import classification. The committed test also asserts the exact two product source roots, so this corruption violates the tested property rather than merely changing a marker.

## P40 classification

The original root-mode `I001` mismatch and the `src` divergence are the **same caller-root configuration class, one level deeper** than the earlier per-file-pattern anchoring issue. The two source files are witnesses to that one class, not separate findings. This delta addresses the class through manifest-declared path and pattern setting families and tests complete effective settings, collection, and behavior. The deliberate wrong-`src` mutation is the falsifier, not another implementation escape. No additional actual escape was established. No formal finding closure is claimed.

## Validation and command log

- `git merge-base --is-ancestor e89927b645469f1981750e7d13ae5cdfc590b7e HEAD` — exit 0.
- `git diff --quiet e89927b645469f1981750e7d13ae5cdfc590b7e -- <eight scoped paths>` — exit 0; all eight current path bytes match the candidate.
- `git diff --quiet e89927b645469f1981750e7d13ae5cdfc590b7e -- policy-engine/.pre-commit-config.yaml` — exit 0; the tested hook configuration also matches the candidate.
- `python -m pytest tests/repo_quality/tools/test_tool_config_split.py -q` — **5 passed**.
- `python -m tools.cli workspace tool-configs --check` — exit 0.
- `python -m ruff check tools/devx/workspace/tool_configs.py tests/repo_quality/tools/test_tool_config_split.py` — `All checks passed!`.
- `python -m ruff format --check tools/devx/workspace/tool_configs.py tests/repo_quality/tools/test_tool_config_split.py` — `2 files already formatted`.
- `git diff --check <candidate-parent> <candidate> -- <eight scoped paths>` — exit 0.
- Exact candidate-source I001 probe with the correct product-root and explicit Git-root configs — exit 0 for all three inputs; the temporary wrong-`src` config — exit 1 with the two diffs above and no diff for the test witness.
- Exact candidate-source `ruff format --check --diff` from both roots — exit 0 for all three inputs.
- Full `--show-files` commands from both roots — exit 0; 7,342 paths in each current-tree result and equal normalized sets, with the denominator described above.

The root readback log at `LOCAL/dx0-native/root-readback-checks.txt` independently records the five tests, generator check, Ruff check, format check, and diff check passing. This receipt is an independent code assessment only; G acceptance remains a separate root decision.

## Independent DX0 subprocess-output receipt reread

This is a separate property from Ruff root-selection parity. P40 class: **NEW** tool-evidence
retention class relative to Ruff config-root parity; the full-stream witness is one shared child
runner helper, not per-gate patches.

Property: when `repository-sota-closeout --subprocess-receipt-dir <path>` is supplied, retain each
executed child’s complete stdout/stderr, command, repository cwd, exit status, and hashes; without
the option keep the ordinary compact failure path. Source inspection of
`tools/devx/workspace/repository_sota_closeout.py` confirms all listed closeout child gates and the
docs-freshness child use `_run_subprocess_with_receipt`. With a receipt directory, it invokes the
child with raw bytes, writes `stdout.bin` and `stderr.bin`, and hashes those bytes before converting
output for existing gate summaries using UTF-8 `backslashreplace` plus universal newline
normalization. Without a receipt directory, it keeps the pre-existing text-mode path. Thus summary
normalization does not alter the retained bytes.

The focused helper test now emits more than 5 KB on both streams with CRLF and invalid UTF-8, exits
23, and compares exact `.bin` contents, raw byte lengths/hashes, receipt fields, and readable
normalized summary text. It also checks the flag parser and that omitting receipts keeps the
existing 4,000-character compact/truncated failure string. The test exercises the real subprocess
helper; the `main`/all-gates option wiring is source-inspected, not end-to-end invoked in this
reread. I did not execute tests, the full gate, or a native SOTA wave. This is not a formal finding
closure.

Reviewed source fingerprints at this mutable snapshot:

- `tools/devx/workspace/repository_sota_closeout.py` —
  `99019d11fd73cedb9c749fb21ec006a551268cbefa1e445c75cce1c77776b06d`
- `tests/repo_quality/architecture/test_repository_sota_phase5_closeout.py` —
  `4707af7381158a8e1f7f8910d3fcc34f67b6db9e4d31b736419d5cacdfb2f866`

The earlier text-mode-only implementation was superseded before this reread. Raw byte capture and
the invalid-byte/CRLF control close that observed byte-fidelity gap; no further actual escape was
established in the current helper/test shape.
