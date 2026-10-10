# Q2 packaging final delta review

## Scope and pin

Read-only review of `4326679438f97c92be08773a33927463b0a67633` (tree `584113c73d3a6290ccf659b44c20171eca6d6cd9`, parent `672f5514e2733a782b49a56425b67294928de78a`). It changes exactly `policy-engine/ops/cloud/gcp/package_repo.sh` and `policy-engine/tests/repo_quality/tools/test_gcp_package_assets.py`. Those two paths and `test_hatch_packaging.py` were byte-identical to the pinned commit in the active candidate worktree (`git diff --quiet <commit> -- <paths>` exited 0); the shared HEAD was `22ca5401692d41f30c37eca060d132c6353dfa87`, and I did not move it.

## Whole archive-member preflight

The prior two packaging reviews classified uncovered symlink admission as the same P40 class at successively deeper routes. This delta widens that mechanism across the actual archive plan. `include_paths` consists of the fixed metadata and directory roots plus every source named by the current Hatch wheel force-include table (`package_repo.sh:30–58`). `iter_paths` uses `lstat`/`scandir` without following symlinks and builds one deduplicated `archive_members` plan (`:80–111`, `:160–169`). Before opening the archive, the same generic `validate_archive_member` checks every planned path (`:127–157`, `:171–176`): lexical product-root membership; `lstat` of each component; no symlinks; directory intermediate components; only a regular file or directory at the leaf; and strict resolved containment. No separate enumerated root gate is used. The archive writer emits only this validated plan.

The root's retained `LOCAL/q2-packaging/root-whole-archive-checks.txt` records `bash -n`, 11 focused tests, Ruff check/format, and `git diff --check` as passing. I independently reran the focused suite against byte-identical source and test paths: `11 passed in 0.68s`.

I also exercised selected-root/member variants in temporary fixtures. Symlinked `src`, `tools`, and `schemas` roots were each refused before an archive was created; symlink members under `tools`, `schemas`, and `ops` were refused; symlinked `README.md`, `pyproject.toml`, `uv.lock`, and a valid external `hatch.toml` were each refused. The suite additionally verifies configured asset bytes and absence of an undeclared sibling, missing/leaf/parent/nested asset symlinks, accepted clean directory assets, refusal of a recursive asset symlink, refusal of a FIFO in a fixed root, and excluded `.pyc`/`__pycache__` symlinks not entering the archive. These are member/byte observations, not marker checks.

The declared source-freeze boundary is explicit in `LOCAL/q2-packaging/archive-preflight/admitted-graph-census.txt:13`: the filesystem graph must remain frozen between census/preflight and tar emission; this mechanism does not defend concurrent mutation. I treat that as the bounded operational input for this candidate, not as another instance of the already-widened symlink class. Native Hatch wheel/sdist and GCP wheel rebuild checks remain **UNRUN** in this review, as requested for the post-freeze wave.

## Separate exclusion-path residual: conventional `.egg-info` name

**Bucket: NEW class (excluded-member selection), not a P40 symlink re-open.** `should_skip` checks the exact path component `".egg-info"` (`package_repo.sh:64–73`). A temporary fixture with both `src/.egg-info/PKG-INFO` and the conventional distribution metadata path `src/polisyos.egg-info/PKG-INFO` showed:

```text
packager_exit=0
stderr=''
literal_dot_egg_info_in_archive=False
conventional_distribution_egg_info_in_archive=True
```

Thus the declared `.egg-info` exclusion does not match the conventional `<distribution>.egg-info` directory spelling. A targeted scan of the current candidate's `policy-engine/src` found no such directory, so this does not show that the current frozen tree contains generated egg metadata. It is a concrete behavior gap if that selected tree contains it; the smallest structural correction is to express the exclusion as a directory-name suffix rule and add the conventional-name fixture. G should decide whether this declared skip applies to distribution-suffixed metadata for the accepted source freeze. No source changes or formal closure are asserted by this review.

## Disposition

The second same-class symlink finding is structurally addressed by one preflight over the complete member plan; no additional fixed-root symlink escape was found under the declared source-freeze condition. The suffix-specific `.egg-info` behavior is recorded separately as a bounded NEW finding, with no current-tree occurrence observed. Independent G review and finding adjudication remain required.
