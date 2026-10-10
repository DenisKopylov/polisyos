# DX6 independent code review

Review ref: `a76bbfaef5be8362c2393802c497866b79df4d9e` (`e90e650e53ca112529c6d1ce8a2f2a1c554e304c`), against `9e89dddfbcc3d8c44a421cc1fc143ec84f3753ae`.

## Independent code assessment

**Fail on root-mode lint parity.** The generated Git-root config preserves the current per-file ignore matchers and the discovered Python file set, but Ruff infers a different `src` setting from the changed project root. This changes real `I001` fix output for two committed source files.

With product-root discovery, Ruff reports no `I001` change in either `src/polisyos/ddm/contracts/metric_budget.py` or `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`. With `--config policy-engine/architecture/tooling/ruff/workspace_root.toml` from the Git root, Ruff proposes fixes in both: it moves `polisyos` imports ahead of `pydantic`, and moves the `tools` import ahead of `polisyos`. The repo hook uses Ruff with `--fix`, so the mismatch can rewrite files during pre-commit even when product-root Ruff considers them clean. Both witness files are clean at the reviewed commit.

`--show-settings` reports product-root `linter.src` as the product root and its `src` directory; the workspace config reports the Git root and its `src` directory. The product's `policy-engine/src` is therefore not represented as a source root in the explicit workspace config. The smallest structural correction is to render the workspace-root `src` mapping with the product prefix, then test import classification and fix output on a real local-versus-third-party import boundary.

## Requirements and evidence

| Requirement | Result | Evidence |
| --- | --- | --- |
| Same lint rules and existing ignores | Pass for selected rules and per-file policies | Both effective configs select the same rules, retain global `ignore = []`, and have equal per-file-ignore maps keyed by resolved absolute matcher and code list (240 entries). The authored ANN001/S101 behavior test passes for both roots. No blanket ignore or expiry change appears in the DX6 diff. |
| Same collection | Pass | `ruff --show-files` from product-root discovery and Git-root explicit-config mode each returned 7,341 files; normalized absolute path sets are equal. |
| Same actual lint behavior | Fail | Read-only `I001` comparison over `src/polisyos` returned 119 diagnostics under product-root discovery and 121 under the workspace config. The two workspace-only results are reproduced with `ruff check --diff` on committed files; no files were changed. |
| Existing glob inputs | Current set covered | A script walked `architecture/tooling/ruff/per-file-ignores/*.toml` (path denominator: all nine manifest-declared files; file-type denominator: those nine `.toml` fragments): 240 unique patterns, comprising 206 literals, 4 `*` patterns, and 30 `**` patterns. The effective matcher/code maps are equal. The base fragment has no explicit `include` or `exclude`; the current patterns contain no negation, `?`, brace, slash-anchored, or dot-relative forms. Their absence is not treated as a future-mechanism finding. |
| Generated artifact reference | Pending | `architecture/generated_artifacts.toml` adds `architecture/tooling/ruff/workspace_root.toml`, but `docs/reference/generated-artifacts.md` still omits it from the generated-config family. `CONTRIBUTING.md` requires this companion reference to be regenerated. This review left it for root closeout. |

The two root modes also resolve `cache_dir` under different roots, as their respective project roots differ. This is operational path context; the observed lint-output mismatch is the `src` classification above.

## P40 classification and disposition

- **Root-mode lint mismatch:** same root-relative configuration class one level deeper than per-file pattern anchoring. The generator adapts ignore keys but leaves the Ruff source-root default bound to the caller's project root. Treat the two files as witnesses to one structural class, not as per-file repair requests; widen the workspace config's source-root mapping and use the `I001` comparison as its falsifier.
- **Generated reference omission:** new, independent artifact-documentation surface class. The reference update is pending root closeout.

No formal finding closure is claimed. No source, test, or configuration file was changed, and no build, install, commit, or push was performed.

## Command log

- `git status -sb && git rev-parse HEAD && git rev-parse HEAD^{tree} && git branch --show-current` — exact requested branch, commit, and tree confirmed; unrelated peer edits were present and left untouched.
- `git diff --stat <base> <candidate> -- && git diff --name-status <base> <candidate> --` — six DX6 paths; 944 insertions and 22 deletions.
- `git status --short -- <six DX6 paths>` — empty; the reviewed paths matched the candidate commit.
- `python3 -m pytest -q tests/repo_quality/tools/test_tool_config_split.py::test_ruff_pre_commit_settings_and_collection_match_product_root` — **passed** (`1 passed`). Exact output: `. [100%]`. The test's temporary probe was cleaned up; no tracked path changed.
- Product-root `python3 -m ruff check --show-files .` and Git-root `python3 -m ruff check --config policy-engine/architecture/tooling/ruff/workspace_root.toml --show-files policy-engine` — both exited 0; each emitted 7,341 paths and their normalized absolute-path sets compared equal. `--show-settings` commands exited 0. A full settings comparison found equal selected rules and equal per-file-ignore maps (240 resolved matchers with identical code lists); the non-location setting difference was `linter.src`. Root-specific `project_root` and `cache_dir` also differed.
- Pattern census at `architecture/tooling/ruff/per-file-ignores/*.toml` (all nine manifest-declared `.toml` fragments) — 240 unique keys: 206 literals, 4 `*`, 30 `**`; zero negations, `?`, braces, slash-anchored or dot-relative patterns. `base.toml` declares neither `include` nor `exclude`.
- `python3 - <<'PY' ... tool_configs.render_files(...) ... PY` — generated output comparison printed `workspace_config_generated_exactly True` for `architecture/tooling/ruff/workspace_root.toml` (27,987 bytes).
- Product-root `python3 -m ruff check --no-cache --select I001 --output-format=json src/polisyos` and Git-root `python3 -m ruff check --no-cache --select I001 --output-format=json --config policy-engine/architecture/tooling/ruff/workspace_root.toml policy-engine/src/polisyos` — both exited 1 because findings are reported; diagnostic counts were 119 and 121. The workspace-only set was exactly:
  - `src/polisyos/ddm/contracts/metric_budget.py:3:1` (`I001`)
  - `src/polisyos/runtime/http/services/governed_projection_validation_worker.py:660:5` (`I001`)
- Product-root `python3 -m ruff check --no-cache --diff --select I001 <path>` returned 0 for each witness. Git-root `python3 -m ruff check --no-cache --diff --select I001 --config policy-engine/architecture/tooling/ruff/workspace_root.toml policy-engine/<path>` returned 1 for each and emitted these complete proposed import changes:

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

- `rg -n -C 2 'tool-config-split-generated-configs|workspace_root\.toml' docs/reference/generated-artifacts.md` — family exists, but its outputs list ends at `architecture/tooling/ruff/generated.toml`; `workspace_root.toml` is absent.

## G acceptance

This is an independent code assessment only. G acceptance remains pending the root decision on the source-root parity defect and the generated-artifact reference companion; this receipt grants neither acceptance nor a formal closure.
