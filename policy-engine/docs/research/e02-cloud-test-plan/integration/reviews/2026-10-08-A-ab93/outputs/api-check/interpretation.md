# Python Runtime API check interpretation

Candidate: `ab93e222381372c54056b9f05e6c8cd7aedf2f2c`, tree `ee92f0719be5b02e212947dcd35f90a1276e875f`.

The single authorized command was `python -B tools/ops_runners/runtime/check_runtime_api_contract.py --skip-client-drift`, from the exact candidate `policy-engine` directory, with the generic origin guard. It completed in 44.511 seconds under the 180-second cap and returned 1. The CLI reported `Runtime API contract check FAILED` because generated OpenAPI bytes drift from committed `schemas/runtime_api_v1.openapi.json`. The stdout contains the complete CLI output; its built-in 120-line unified-diff limit states that 49 additional diff lines were omitted. Generated-client freshness was explicitly skipped.

The raw receipt says `ERROR_SOURCE_AFTER` because the harness initially required the entire nonmanifest inventory to remain unchanged. That status describes a checker-policy mismatch, not a changed selected source input. The task's source-immutability predicate passed: all 7,499 selected manifest rows (165,980,819 bytes) matched their candidate Git blob and mode before and after; the complete source subtree and candidate tree identity matched; 1,674 loaded project-module file origins matched candidate blobs and modes with zero audit errors. The G branch remained `codex/e02-integration` at `c7adfde6d039e47b1f304eff79340e31a9426270`.

The nine preexisting nonmanifest `root.lock` files were all regular mode `100644`, zero bytes, and retained the same empty-file SHA-256 before and after. The API command generated six additional nonmanifest CAS outputs inside the candidate export: three zero-byte transaction locks and a 37-byte blob plus two 358-byte manifests. The receipt records every path, mode, size, and digest before/after; these generated runtime artifacts are separate from the selected Git inputs. No cleanup was performed.

Interpret the check as **API contract FAIL (OpenAPI drift)** with **selected-source immutability PASS**. It does not measure generated TypeScript client freshness, endpoint execution, authorization behavior, production deployment, or hosted CI. No source was repaired and no second API run or pytest wave was performed.

Receipts: `receipt.json` SHA-256 `bf25c0a843cfa6c4378ecefbb7b9424b80217c7c19d8bb53752140a915b16563`; `stdout.txt` `b9398f23839c4b9f9e195b3417ef5e41399368eb495e9d0a4ea418d08af49b29`; `stderr.txt` `6b763fc09d57fa6d5be4d4f86e3b3bff99922a45dc3dc24a8854cff851196da1`; `origin-audit.json` `1057063f38cb3888a098a6c9c3407626fab0953ba584a30be097c97c3133a3cb`.
