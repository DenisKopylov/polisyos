# Q2 filesystem output-control independent review

Date: 2026-10-10. Review anchor supplied by root: `HEAD 7fe2ceca103582a8c2d3d6345effbd79af7e8f8f`, tree `f2f6b9dff3ddcac843b6ffa912e256836591fd3c`. I did not run Git commands to independently resolve that anchor. I read the exact oracle, helper, and complete retained control receipt by path and hash; I did not execute the helper/oracle or run tests.

## Verdict

**Narrow GO for the static Q2 output-path guard behavior covered here; no concrete escape found in the retained controls.** This is not a general filesystem-safety or Linux-runtime closure. The evidence is a host `/bin/bash` execution against controlled static paths, and the receipt itself states that privileged concurrent replacement is not established.

## Direct evidence

The pinned files match the requested hashes:

- Oracle: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/q2_output_path_behavior_controls.py@c76cf2608cde1dbee07c851508621d00bb03c03df5b0d57fcc6d880252f71729`
- Actual helper source: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/final-source-linux-wave.sh@545a503585c98145c314df9c81ab42af4012e3ef11550a593d1172096f08116d`
- Full actual-control receipt: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/q2-path-guard-real-filesystem-controls-20261010-r2/stdout.txt@5a0c04d1bfe8386571a15369095e914036b8a2f405fd8debb7cb6bc185b1e3d4`

The receipt’s `source_sha256` equals the helper hash. Its 14 records all have the expected exit status: 4 allowed/reusable-or-create paths succeed, and 8 unsafe/retained paths are refused with exit 17, followed by two deliberate guard removals that succeed. Specifically, the ordinary cases cover an existing root, an existing parent, a missing parent, dangling root and parent links, a parent symlink-to-directory, a parent file, an absent target, and existing target directory/file/symlink/dangling-symlink.

The oracle does not merely call a separately reimplemented classifier. It extracts `q2_output_action()` and `q2_output_directory()` directly from the pinned helper (`final-source-linux-wave.sh` lines 143–158 and 617–631), then extracts the actual target existence/classification/create block at lines 635–643. It runs those extracted bodies through `/bin/bash` against real temporary directories, files, symlinks, and dangling symlinks.

Both removal controls keep the actual `q2_output_action()` classifier function and its decision labels present, but bypass the behavior under test. Replacing `q2_output_directory()` with `mkdir -p` makes the parent-symlink control return success; bypassing target admission and using `mkdir -p` makes the symlink-target control return success. The corresponding guarded controls refuse those same symlink paths. These paired results distinguish the filesystem property from the classifier labels and satisfy the remove-the-property-keep-the-markers probe for the exercised paths.

The oracle confines its fixture to a previously absent, non-symlink path under `policy-engine/_build/.tmp`, creates an external-directory sentinel, and checks its hash after every control. The receipt records the same before/after sentinel hash, `b9d8bb2f65c8ff26480ecaca22a8541eb36e225a48b27ae10210d733b2dec51d`; it also reports that `external/orchestration` was not created. The full streams remain in the retained receipt; I did not copy the large per-case shell payloads into this note.

## Property and limits

The property exercised is: Q2 may reuse only the permitted real directory components, create only absent parent/attempt directories, and must refuse symlinked or non-directory components and retained target paths before continuing to later output work. The inspected implementation classifies links with `[[ -L ... ]]`, admits the relevant real/missing cases, and rechecks created/reused directories with `[[ -d ... && ! -L ... ]]`. The target path uses an exclusive `mkdir -m 700` after the target guard.

This receipt runs the extracted shell under the host `/bin/bash`; it is not an execution of the Q2 flow in its intended Linux worker/container. It tests static fixtures only. It does not prove safety against a concurrent privileged replacement between classification and `mkdir`/later writes, and no such stronger claim is made here. There is no separate root-symlink-to-directory case; the common symlink-rejection branch is exercised with parent and target symlinks, while root is covered with real and dangling-directory cases.

P40 bucket: this is the first review of the filesystem-output guard class, distinct from the earlier V5 score-admission class. The two marker-preserving controls are useful falsifiers within this first review; I found no second same-class escape requiring a mechanism change. This review supports only the bounded static output-path behavior above, not a generic closure claim.

## Review actions

I inspected the oracle source, the actual helper source, and the complete retained JSON receipt; I verified their hashes and the oracle/helper source-hash join, parsed the 14 result records, and compared each actual exit status with its expected status. I did not run the shell helper or oracle, run tests, alter Git state, or modify source. The only write is this review note.
