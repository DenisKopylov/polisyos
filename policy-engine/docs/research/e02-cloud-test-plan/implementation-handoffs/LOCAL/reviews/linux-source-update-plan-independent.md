# Independent review: append-only Linux source update plan

Review target: `LOCAL/linux-profile/append-only-source-update-plan.md` at SHA-256 `a863510239899bac63c393b65a47d8c4791d19f8559c8499f3b1956b7adcea49`.

The source freeze currently read back is `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, tree `8d8c4082febf1676dd86084106f3266d8b2131a3`, parent `25219d0692c1c54b99f9d40b5c53a6956e2f4e2e`. A read-only `merge-base --is-ancestor 7574c864a605c50efc033b966807790cbd8d1781 13e411da7d9e505856fc336b3d25fd0aabdb1f66` succeeded. The actual commit headers read back for the freeze and base agree with those identities; the base header names parent `5e312037e180938aa643abccfd727a2a12b9a691`. No Docker or Git mutation was run for this review.

**Assessment: SAME_CLASS_DEEPER (P40), conditionally ready for root's corrected stdin recipe; do not execute the plan verbatim.** The intended append-only path is sound in outline: incrementally bundle the frozen attached branch, fetch into the existing shallow bare store, compare-and-swap its branch ref from the exact base, fetch into the existing attached checkout, and fast-forward. The plan's two command-context errors can make that recipe fail, while missing fail-fast and loose absence checks weaken its stop conditions. These are deeper command/state-boundary failures in the same transport class, not separate transport mechanisms.

## Required command corrections

Run each outer host block in one fail-fast Bash session (or prefix each independently executed block with this line); the inner worker scripts already set these options:

```sh
set -euo pipefail
```

Add explicit nonempty-advance and symlink-safe bundle guards before creating the host bundle:

```sh
test "$new_sha" != "$base"
test -n "$(git -C "$source_checkout" rev-list --reverse --topo-order "$base..$new_sha")"
test ! -e "$bundle" && test ! -L "$bundle"
```

Use an explicit repository context for host bundle verification and listing; the plan's bare `git bundle verify/list-heads` depends on a prior `cd` and is unsafe if snippets are run separately:

```sh
git -C "$source_checkout" bundle create "$bundle" "refs/heads/$branch" "^$base"
git -C "$source_checkout" bundle verify "$bundle"
git -C "$source_checkout" bundle list-heads "$bundle"
```

`docker_e02` is a host-side Docker wrapper, not an in-container command. Replace the plan's invalid `docker_e02 test ! -e "$worker_bundle"` with:

```sh
docker_e02 exec "$container" /bin/bash -lc 'test ! -e "$1" && test ! -L "$1"' _ "$worker_bundle"
```

Likewise, the worker bundle verification must run through `exec`:

```sh
docker_e02 exec "$container" git --git-dir="$worker_bare" bundle verify "$worker_bundle"
```

For exact one-line shallow-boundary checks, replace each `test "$(cat PATH)" = "$base"` in both worker scripts with a byte-exact comparison. The existing worker commands explicitly use Bash, so process substitution is available:

```sh
cmp -s "$bare/shallow" <(printf '%s\n' "$base")
cmp -s "$repo/.git/shallow" <(printf '%s\n' "$base")
```

Do the corresponding check for the bare store after update. Also make the alternates checks symlink-safe, so a dangling symlink cannot pass as absence:

```sh
test ! -e "$bare/objects/info/alternates" && test ! -L "$bare/objects/info/alternates"
test ! -e "$repo/.git/objects/info/alternates" && test ! -L "$repo/.git/objects/info/alternates"
```

Keep the existing Docker `exec` preflight and post-update checks, frozen SHA/tree/lock/manifest pins, `FETCH_HEAD` comparison, compare-and-swap, fast-forward, and connectivity checks. Do not unshallow, replace the checkout, or overwrite a bundle. The plan's introductory sentence saying that no new freeze has been supplied is now stale relative to the source freeze above; it is documentation context, not a reason to infer or alter any pin.

## Boundary and limitation

This is static review only. No container inspection, bundle creation/verification, worker copy, ref update, checkout update, or product test was performed. Root should retain the complete actual stdin command and its output as the transport receipt. The review establishes the host source ancestry and identifies the command corrections; it does not establish Linux-side execution or successful transport.
