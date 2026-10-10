# Independent review: product-relative inputs in Git object paths

## Result and P40 bucket

**P40: SAME_CLASS_DEEPER — frozen source identity / Git-object path binding.** The prior validation failure was a real product-root mapping defect: from the repository root, `HEAD:pyproject.toml` does not exist, while the product file is stored at `HEAD:policy-engine/pyproject.toml`. The reviewed wrapper now derives the product prefix from the resolved product and Git roots, cross-checks it against `git rev-parse --show-prefix`, and uses one product-relative path mapper for both Git blob reads and blob-existence checks. The mapper rejects absolute, parent-traversal, and backslash paths before constructing a repository-relative object path.

The fix is generic rather than a one-file rewrite. `git_blob_bytes()` maps its product-relative argument with `product_git_path()`, and the sole `git cat-file -e` caller maps the same inputs through that helper. The `verify_input_manifest()` path therefore uses repository-root-relative Git object names consistently for every planned product input.

## Exact candidate and direct evidence

Candidate: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, branch `codex/e02-unified-local-20261009`, HEAD `7574c864a605c50efc033b966807790cbd8d1781`, tree `9561394a619e21b92680d79a1aa812da6892967c`.

Reviewed wrapper: `LOCAL/raw/composed_mac_capture.py`, SHA-256 `6f40ef9fa037655285d516153283c50591039e314105c6ed50550527856dadb2`.

I independently enumerated the canonical plan's complete input set from its source paths, selected test paths, source note, and plan file: 71 source inputs + 62 test paths + 2 note/plan files = 135 unique inputs. I obtained the frozen repository tree using Git, derived the product prefix independently as `policy-engine/` from both the resolved roots and `git rev-parse --show-prefix`, then fetched every tracked planned input with `git show <commit>:policy-engine/<product-relative-path>`. All 135 were tracked blobs and every blob's bytes matched its current worktree file. No planned input needed the external local-source-manifest fallback.

The specific positive mapping also passed: product-relative `pyproject.toml` maps to `policy-engine/pyproject.toml`; its actual commit blob SHA-256 matches the worktree file. The resolver refused all three outside-prefix controls: `../README.md`, `/tmp/outside.py`, and `..\\outside.py`. Direct baseline confirmation showed `HEAD:pyproject.toml` is absent and `HEAD:policy-engine/pyproject.toml` exists.

The complete per-input path, source kind, size, and digest record is `LOCAL/raw/composed-mac-git-prefix-freeze-v2-independent-20261010.json`, SHA-256 `045982ff57fa5b5ca7035faf621b22295a4a83713abebdefafacb1c292a6f80d`.

## Actual CLI validation evidence

I re-read and verified the author's fresh `main --validate-only --allow-heavy` receipt against the exact wrapper and current HEAD/tree. The command returned 0 with status `VALIDATED_NOT_RUN`, all 19 planned command IDs selected, all 135 input paths checked, and `product_commands_run=0`. Captured stdout SHA-256 is `2f639ecaa69799e1b1f4575f673fe665397a9cfbb768dc33ccd438f13ab68d30`; stderr is empty and has SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The receipt itself is `LOCAL/raw/composed-mac-git-prefix-freeze-v2-60dc858bcc404b3b9df2f3d54166e921/validate-allow-heavy-receipt.json`, SHA-256 `e44dfe6f016708c8334dd8febef9b33dca14808cc9066e015cb2ea1b516d580f`.

**Review result: READY for this Git-path mapping delta and the root's final manifest preparation.** This proves the frozen Git inputs for the 19-command preflight, not execution of those commands or their product behaviors. I ran only read-only Git blob comparisons and the wrapper path mapper; I did not run pytest, the capture queue, build/install, a native fit, or production-data reads. The source manifest must be regenerated if later source/config inputs change. This independent review gives no formal finding closure or G acceptance.
