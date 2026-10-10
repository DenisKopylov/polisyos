# Independent packaging review

Target: `314dc4100a1982cac1d2ddcdde230f2b9ba71a06` (parent `a76bbfaef5be8362c2393802c497866b79df4d9e`, tree `5444f50a26499a2cf62cbc1e894fc6ed5684bd21`). The commit changes exactly three paths: `ops/cloud/gcp/package_repo.sh`, `tests/repo_quality/tools/test_gcp_package_assets.py`, and `tests/repo_quality/tools/test_hatch_packaging.py`. At review time those paths matched the target commit (`git diff --quiet <target> -- <three paths>` exited 0); other candidate work was present in the shared checkout and was not part of this review.

## Finding

**Medium, high confidence — a symlinked parent component bypasses the source-path symlink refusal.** P40 bucket: **NEW class in this review**; this is the first demonstrated escape for this package change.

At `ops/cloud/gcp/package_repo.sh:45-50`, the guard recomputes absolute/traversal status, resolved containment, regular-file status, and `source_path.is_symlink()`. The last predicate checks only the leaf. The intended property is that a configured Hatch source is a regular, in-root path with no symlink component. A divergent case is `assets -> internal` inside `policy-engine`, with a regular `internal/item.yaml` and configured source `assets/item.yaml`: `source_path.is_symlink()` is false and the resolved path remains inside the product root, so the guard accepts it and archives the redirected bytes under `policy-engine/assets/item.yaml`.

I reproduced this by invoking the committed `package_repo.sh` against an isolated fixture with that path shape. It exited 0 and the archive member contained `redirected in-root bytes`. The adjacent controls exited 1 with `Invalid Hatch wheel force-include source: assets/item.yaml` for a missing source and for a symlink at the leaf. Thus the current guard catches those cases but does not establish the whole-path no-symlink predicate. The smallest class-level repair is to reject symlinks in every path component between `product_root` and the source leaf, with a regression case for a parent symlink that resolves back inside the root.

## Evidence and limits

- `policy-engine/.venv/bin/python -m pytest -q tests/repo_quality/tools/test_gcp_package_assets.py` — **PASS** (`.`; exit 0). This executes the actual archive script. The fixture reads every source key from `policy-engine/hatch.toml` at the reviewed commit (`ab91c577cc1fc7beed00b78d29efd9c84ba7c9f7`): a complete walk returned 11 configured source paths out of 11 `force-include` mapping entries. It verifies exact source bytes in the archive and excludes an undeclared YAML sibling in the same resource directory.
- Fresh isolated path probes against the same script: present regular source **accepted**; missing source **refused**; leaf symlink **refused**; parent symlink to an in-root directory **accepted with redirected bytes**. These are direct behavior observations, not marker checks.
- The commit updates `test_hatch_packaging.py` with native wheel/sdist comparisons and a GCP archive-to-wheel rebuild comparison. I inspected those assertions but did not run the Hatch build suite because the composed heavy packaging wave is reserved for the frozen candidate. Therefore archive-to-wheel/sdist behavior remains **UNRUN in this review**; the focused archive test alone does not establish that end-to-end chain.

## Gate classification

For the direct archive test, byte equality for each configured source and absence of the undeclared sibling are recomputed from the archive members. For the source-path guard, absolute/traversal checks and resolved containment are recomputed, but “no symlink anywhere in the source path” is **not established** by the leaf-only predicate. P38 divergence is the in-root parent-symlink case above. The review verdict is **partial, with one blocking source-path finding**; independent G acceptance and formal finding adjudication remain outside this review.
