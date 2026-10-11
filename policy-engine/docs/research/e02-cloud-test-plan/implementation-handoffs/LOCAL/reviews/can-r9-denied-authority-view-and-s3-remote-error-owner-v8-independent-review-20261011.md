# Independent review: CAN R9 authority read boundary V8

**Verdict: bounded GO for root to compose this candidate on the three exact preimages.** This is an independent code review only; `closure_ids` is empty, this does not accept the patch for G, and it does not close the wider CAN source/profile/history properties.

## Candidate and reviewed repository state

- Candidate patch: `LOCAL/raw/can-r9-denied-authority-view-and-s3-remote-error-owner-v8-20261011/patch.diff` @ SHA-256 `f28a82fd882b5b9c2801ba7106af6281efb6b1feb26ddfbae2f65b4702ac7d9d`.
- Manifest: same raw directory, `manifest.json` @ SHA-256 `1ae5a33bf75e67ed6e1cdcf25dce6b750e0d401b50714d77b9679063e857bd23`.
- Candidate source base: branch `codex/e02-unified-local-20261009`, HEAD `e6a8390c76607c2dbdc545697c616ceec6e891a1`, tree `c53b96360d4335a76fe8caf829f2c6b702b249b0`, parent `e2681fd7ac10eabb8acf06d0470abeadce31a146`.
- At review readback, the shared checkout had advanced to HEAD `827c709eb926d5bd3a4d7418630ffe56904bc130`, tree `05c9db6cefb11604d7d0019de5f87730e6953fd7`; the candidate base is its ancestor. The checkout is root-owned and dirty. I did not move HEAD or alter the product/index. The three target worktree bytes exactly match the candidate preimages below; `git apply --check --verbose` passed against the current tree.

| Path | Exact preimage SHA-256 | Candidate postimage SHA-256 |
| --- | --- | --- |
| `policy-engine/src/polisyos/runtime/quality/authority_reconciliation.py` | `966e56c71fac3ca30d4fe288009f1ff2ec17b7051b41daff9fd34aaa512b4155` | `ad2ca089964718a49ac70ef65b6e3f3dd333f177aae5c6f719555b61f830a49d` |
| `policy-engine/tests/unit/runtime/quality/test_authority_reconciliation.py` | `1d04fe63a77d9224eb725ecf092fc54b0475b6ff4b20617cd46b20c1fbee3661` | `b914ba2d197211a79a7760518d60467a0c872034a0d48bdef26cdc721f2d2dbe` |
| `policy-engine/tests/unit/core/artifacts/backends/test_s3_store.py` | `51cabed07b9d214eae3f0d960fec2efd22c8957fba81bdce7793d150d431e722` | `f7c7a7055f949353f5ce2673b45b6a7884dca316bafe0998203c4e37b9994410` |

## Property review

P40 bucket: **SAME_CLASS_DEEPER_SECOND**. V7 had exposed an `OSError(EIO)` escaping its exception-class allowlist at the real `FileSystemCAS.get_manifest → ManifestLifecycle.read → Path.read_text` boundary. V8 widens that same untrusted-read/refusal class across the whole read set with one `Exception` capture helper; it does not add another exception-specific patch. It intentionally leaves `BaseException` signals uncaught.

The candidate turns read failures into a fixed error category and drops the original exception object/text before callers construct their typed refusal. The complete source census covers five direct operations—default/profile manifest resolution, byte reads, verification, and event-row materialization—and all are inside the shared capture path. The linked-event decode and DTO validation also execute inside that boundary. The public resolver uses the same safe resolution path and emits a fixed `ValueError`-compatible refusal. Failed verification details retain only a validated artifact ID, valid SHA-256 values, nonnegative integer byte size, and a fixed failure category. The profile selector remains explicit; the code never switches to a default view after selected-view failure.

The marker-preserving removal control substitutes the prior bounded exception allowlist while keeping markers and expects two failures: the injected fault matrix and the real local filesystem EIO. The preserved `KeyboardInterrupt` control confirms that the catch does not absorb `BaseException`. S3 coverage seeds and reads a selected remote artifact, exercises provider errors through direct and cached GET/HEAD, checks exception identity, and asserts the post-setup `head_bucket_calls` counter did not change.

## Independent evidence

- Patch admission: `git apply --check --verbose .../v8-20261011/patch.diff` exited 0 for all three files. Current worktree target hashes match all three exact preimages.
- Focused candidate-overlay command recorded by the author: `policy-engine/.venv/bin/python .../can-r9-denied-authority-view-and-s3-remote-error-owner-v8-20261011/checks/run-focused-v8.py`; exit 0, **11 passed / 32 deselected**. Full output: `checks/final-focused-v2.stdout.txt` SHA-256 `40abc13761404eaf8a8ab87fa06f44290512357ec9243fc87b5838f45889d17c`.
- Canonical Ruff and format check used `policy-engine/architecture/tooling/ruff/workspace_root.toml`; all three postimages passed. Report: `checks/static-checks-v2.json` SHA-256 `7ac1e930e17d53b1749a5e0e9ff6d9f1215cae1c7a26f6114511516c7eae4d13`.
- Complete operation census: all five source callsites are captured; report `checks/operation-census-v2.json` SHA-256 `c008bbbeee693df12f8dbd15225fb3daf11784c935dbd72d5813ab071cf6b029`.
- Removal probe output: `checks/final-removal-v2.stdout.txt` SHA-256 `0ff0038b8467da2eace23e2a98626c0e43995b06df5a2ea6f37faec09d749b02`.
- I independently ran the focused overlay earlier in this review; the same deciding output is preserved by the candidate. I also exercised the public resolver against an actual local authority artifact with injected `OSError` on default and selected-profile reads. Both yielded `_AuthorityManifestReadError`, `error_kind=read_error`, `context_is_none=True`, and no private marker in string or traceback. Script `LOCAL/raw/can-r9-v8-public-resolver-probe-20261011/reproduce.py` SHA-256 `d24d1b5350da2e010079a993f4228a794c99182f0120a979901fd60cf54b2ce5`; output SHA-256 `80fe149466e47e5a087f674303d364996efe7d7e753fcfc77f407313ff6f56f4`.
- I also probed selected-profile behavior on a tenant-scoped store. Both an existing foreign blob and a nonexistent blob with an unowned profile were denied by the owner index before presence or payload reads, with `authority_payload_mismatch` / `permission_denied` and no fallback. This correctly does **not** establish physical absence. Script `LOCAL/raw/can-r9-v8-profile-absence-probe-20261011/reproduce.py` SHA-256 `1e159edd0ef5a198b1ee43dd309bcf580b7bdbd4fbfbcd89bc42d393d2df5419`; output SHA-256 `d4c9793f295131b21880b22a7522ffa2dc14962a4560462bca7c234bbe8f44dc`. The unchanged unscoped missing-object test establishes true `FileNotFoundError → authority_cas_missing`; the unchanged absent-selected-profile control on an existing artifact establishes refusal rather than default-profile fallback.

## Limits and next check

This is controlled local CAS plus a fake S3 client. It does not establish live provider behavior, production custody/currentness, the composed HTTP/API/browser surface, or the full E02 queue. The V8 source change does not resolve the separate CAN questions about typed mapping options, raw content/profile conformance, Core-only tags versus IR law, producer-attested versus reader-materialized profile, or profileless-history rollout. Root should apply it only to the exact three preimages, then run it in the composed source freeze with the planned HTTP/quarantine companion and actual focused/full consumer checks. G retains independent acceptance and formal adjudication.

`closure_ids: []`
