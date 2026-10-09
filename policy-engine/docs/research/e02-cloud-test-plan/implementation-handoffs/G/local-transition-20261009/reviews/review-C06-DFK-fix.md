# Independent delta review: C06-DFK serializer fix proposal

Date: 2026-10-09
Disposition: **GO to apply this exact narrow fix on the integration lineage, subject to source-base reconciliation and ordinary focused verification.** This is not acceptance of the original `3a0d5549…` unchanged, not a commit or merge, and not formal finding closure.

## Immutable inputs and patch identity

- Patch: `policy-engine/_build/e02-g-continuation-20261006/R/local-transition-20261009/DFK-fix-proposal.patch`.
- SHA-256: `a87013d72f3f11e50a968001935256e02628361252f828fe21e4ba5ab3ef71c2`.
- Pinned source base: `3a0d5549606087c1d4e8d344ed474c0dfb4cbe5d`, tree `1e2e7c6ca7948f3c2b771af431bd0d73510fec3a`.
- Source preimage SHA-256: `schema_fqn_census.py` `a2ee2b6d21a1b5d5cf5e2484539ca5ca365f82a8d1b941344730e58f13625d42`; test preimage `test_dfk_01.py` `27dacceb4bde9ceaa1b594175b8fb3f439a76dc118214fb9d9ed3787894b1be8`.
- Proposed postimages, independently re-hashed from the ignored exact candidate, match `patch-validation-final.json`: source 31,622 bytes / SHA-256 `33c80a668228b159526c45f3101e259a54fd74a6dd4d5c8f80cc2dfef6a02e12`; test 44,270 bytes / SHA-256 `9058c7ecab448336f2d025cae3b5eedc0c7bc0966ad316cb0ead63be735d47e8`.
- The patch changes only the JSON serializer argument and adds one focused test. The recorded standalone `patch -p1 --dry-run` and apply succeeded against a copy of exact `3a0` source, and both resulting files byte-match these proposed postimages.

At the initial delta-review snapshot, integration was `e92487c58d77481f05450085e2b78f6e2478b512` (`ahead 28`) and clean. During review it advanced to `b776bcb7049dacb45daeafc0dba40e88bc25f331` (`ahead 31`); the latter is not a descendant of `3a0d5549…`, and the DFK source/test files are absent at that current tip. I did not move or repair the branch. This review is bound to the immutable `3a0` preimages and postimage hashes above. The GO applies to a repaired immutable DFK candidate built from the exact `3a0` source delta; it does not authorize applying this patch alone to current G or admitting raw `3a0` unchanged. G must reconcile ancestry and source selection, then preserve ordinary append-only history.

## Defect and repair assessment

The source change is exactly `json.dumps(receipt, ensure_ascii=False, sort_keys=True)` → `ensure_ascii=True`. The previously recorded real-`main` serializer falsifier passes a receipt containing `bad_\udcff.json`, receives exit 0, but captures raw byte `ff` in stdout; decoding captured stdout as UTF-8 and parsing it as JSON fails. The byte-name filesystem reproduction on this Mac is explicitly unavailable (`APFS`, errno 92), so it is not represented as a real Git filename test.

The patch’s new test invokes the actual `main()` serializer boundary with that surrogate-containing receipt, then requires ASCII stdout and `json.loads` to recover the exact original Python path string. The existing real-Git parser suite remains unchanged: the fix touches neither `os.fsdecode`, the XY/rename/copy parser, input selection, the partial/missing-input rule, nor any census semantics. The recorded focused regression contains the new test plus both original public-CLI text/JSON cases: **3 PASS**. The previously source-qualified DFK suite remains **45 PASS**; those historical receipts are not falsely relabeled as execution on the patched postimage.

`ensure_ascii=True` is generic for the entire receipt: ordinary non-ASCII strings are escaped as JSON Unicode escapes without changing their parsed values, and surrogate escapes no longer put non-UTF-8 bytes on stdout. The fix closes the discovered output-boundary failure without hiding or dropping the path. The proposed regression is appropriately narrow for the serializer itself; it does not claim to test invalid-byte filename creation or Git enumeration on this host.

## Remaining limitation and decision boundary

A Linux real-filesystem/Git test using a filename containing raw `0xff` remains **UNRUN**. The supplied receipt explains why it could not run on APFS. This does not block applying the serializer fix: the failing boundary was independently reproduced through the real `main()`, and the postimage test exercises that same serializer boundary while preserving the path value. Keep the real-byte Git case listed as unverified; do not claim end-to-end invalid-byte path enumeration passed.

There is one explicit interoperability limit: Python’s surrogate-escape representation of a non-UTF-8 OS path is emitted as an escaped lone surrogate (for example `\\udcff`). That is ASCII JSON text and Python round-trips it, but a consumer that requires Unicode-scalar-only strings or reconstructs original filesystem bytes across languages may need a separately specified byte-path representation or a partial-result policy. No such cross-language raw-path contract was established in these receipts, so I record this as a boundary to retain in the tool contract, not a demonstrated blocker to this bounded local census fix.

## Review actions and recommendation

Read-only review of the patch, exact `3a0` preimage blobs, candidate postimage hashes, source-falsifier receipt, focused JUnit/run receipts, and patch-validation receipt. I did not run tests, install dependencies, access production data, edit source, stage/commit, or publish refs. A non-mutating `git apply --check --directory=policy-engine` attempt used the wrong path root and failed to locate the root-prefixed patch paths; it is not evidence either way. The correctly rooted standalone validation receipt is the applyability evidence used here.

**GO** for a history-preserving repaired-source sequence: reconcile and select the exact `3a0` DFK candidate, apply this two-file forward fix to that candidate, and admit/replay only the fixed final source as the bounded source candidate. The current G tip lacks these DFK files, so this patch cannot be applied directly there by itself; G must choose and verify the source lineage first. Rerun the focused DFK CLI text/JSON and serializer cases against the resulting exact local source and retain their full outputs. Keep the Linux real-byte Git check `UNRUN`, preserve prior finding/release limitations, and do not report the original source alone as accepted or any product finding as closed.
