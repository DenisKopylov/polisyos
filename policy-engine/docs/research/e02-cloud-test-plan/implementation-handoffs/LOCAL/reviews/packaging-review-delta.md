# Q2 packaging delta review

## Scope and pin

Read-only review of `8e69d23ee61a640621a487243a59107f0d1f232f` (tree `4ccdbe603115ab9a018f8c330f9608a7e21ac22b`, parent `cf949d4a10869d0f992d111cbf1f35fa89a84b30`). The commit changes exactly two paths: `policy-engine/ops/cloud/gcp/package_repo.sh` and `policy-engine/tests/repo_quality/tools/test_gcp_package_assets.py`. Both paths in the shared candidate worktree were byte-identical to the pinned commit (`git diff --quiet <commit> -- <two paths>` exited 0); other dirty paths belonged to the active author and were not read or modified for this review.

The delta closes the prior review's force-include component escape: it rejects symlinks in every source path component and in recursively visited members of a force-included directory. It also rejects missing/special entries and keeps the clean-directory positive. The focused suite has 8 passing tests; the author's retained `LOCAL/q2-packaging/root-symlink-delta-checks.txt` records `bash -n`, Ruff check/format, and `git diff --check` as passing. The same pytest command was run against the identical source paths and passed (`........ [100%]`). Full Hatch archive-to-wheel/sdist builds were not run in this delta review; they remain reserved for the frozen composed replay.

## Finding: fixed archive roots still admit symlink members

**Bucket: SAME class, one level deeper (P40), following `packaging-review.md`.** The source-path guard is invoked only for Hatch `force-include` entries (lines 43–77). The ordinary roots at lines 29–38 are appended directly. `iter_paths` recursively yields every non-skipped entry from those roots without checking symlink type (lines 96–108), and the archive loop passes each path to `tar.add` (lines 111–115). The property is “every path admitted to the archive obeys the package's source-boundary and symlink policy”; this implementation only checks the force-include subset.

I reproduced the counterexample in an isolated temporary workspace using this exact script: put `src/leaked.yaml` as a symlink to `../outside/payload.yaml`, leave the force-include table empty, and run `bash ops/cloud/gcp/package_repo.sh`. Deciding output:

```text
packager_exit=0
stdout='Created .../policy-engine-20261009-095501-local.tar.gz'
stderr=''
archive_count=1
member_type=b'2' is_symlink=True linkname='.../outside/payload.yaml'
```

The archive therefore accepts an externally redirected member under a fixed include root (`policy-engine/src`). This is not a force-include regression test; it is the adjacent fixed-root route through the same archive admission mechanism. The new nested-directory test at `test_gcp_package_assets.py:150–167` exercises only a force-included directory, so it does not falsify this case. The minimum capability that closes this class is one preflight over every archive input root and recursively admitted member, before `tar.add`; that whole-root preflight is absent at the reviewed commit. Under P40 this is the same class one level deeper, so the review does not prescribe a sequence of path-specific patches: either widen admission to the whole archive input set and falsify fixed-root plus force-include cases, or record this precise residual with its falsifier and owner.

## Gate classification and disposition

For declared force-includes, path containment and symlink-free traversal are recomputed by the script, and tests inspect archive members/bytes. The archive-wide no-symlink/source-boundary predicate is **not established**: the fixed-root counterexample exits successfully. P38 divergence is direct: the package is intended to admit only approved repository content, while the archive writer tests neither symlink status nor resolved containment for fixed roots; an absolute-target symlink in `src` is admitted as a tar symlink. Review result: **partial; one blocking package-admission residual**. No formal G finding closure or source change is asserted here.
