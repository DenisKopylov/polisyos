# Independent check: ninth-wave B local numeric evidence

**Decision: GO for this narrow local evidence artifact.** This does not accept B source into G, admit the broader B carrier, or close any finding.

Reviewed the exact candidate at `e7c5182bf9d37f62a87e1effd003ee9732c20c32`, tree `bd3d76242c3c222b0bee7dd2c81bc73c2ecb374f`; `git rev-parse <candidate>^{tree}` agrees. The positive archive's loaded `gateway_client.py` bytes equal `git show <candidate>:policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py` (Git blob `0dc65ee8cbe6477c50deb965d4d7cc12b3f6c5a2`, SHA-256 `4161bc6dfa38838c107228672fab9e1468087c19ae7ddb4f510247577fac29c3`). The receipt also binds `response.py` blob `33c7b310aef734b31c2ed2e61fe28d6525524b97` and `prompt_cache.py` blob `e4aece7bace8cc969a0c896727c09cd80cef25bf`.

All nine file assets in `integration/checks/2026-10-07-ninth-wave/B-gateway/receipt.json` match their declared byte counts and SHA-256 values. The complete copied stdout/JUnit/Ruff evidence is:

| Output | Bytes | SHA-256 | Readback |
|---|---:|---|---|
| `candidate.stdout.txt` | 6,831 | `12a722f3db95c3578b81b8a6c76fc2e127de9fe71eb607ce1c20a2dd11955631` | 30 passed |
| `candidate.junit.xml` | 5,817 | `fe11afca936fb934199217d4365dd99553d1770f192c26725c3c11a35e7d2a47` | 30 cases; 0 failures/errors/skips |
| `control.stdout.txt` | 48,763 | `0216479e1899386a09ce42251aeed0f8c44d076622d44656404c611206068b5a` | 20 failed, 10 passed |
| `control.junit.xml` | 40,767 | `881a6b0c90caf2c1d8547d147025afe5aa512d594c1e597315a05ee56e361ffb` | 30 cases; 20 failures, 0 errors/skips |
| `ruff.stdout.txt` | 19 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | `All checks passed!` |

The three stderr files are each empty and match the receipt's SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Candidate and control XML parse counts agree with the full stdout summaries. The control archive differs from candidate at only `gateway_client.py`, one line: it removes `parse_float=Decimal` from `json.loads`; the receipt's before/after file hashes agree with that single mutation. The 20 negative-control failures include the tiny nonzero cost/token evidence cases; the 10 unaffected cases remain green.

`g_origin_plugin.py` is observational: its only pytest hooks capture the exit status and inspect/hash already-loaded modules at teardown to write a report; it has no collection, fixture, monkeypatch, or test-execution hooks. The local ignored origin reports at `policy-engine/_build/e02-g-continuation-20261006/R/incoming-20261007-0837/B-local-numeric/results/{candidate.module-origins.json,control.module-origins.json}` record the exact candidate/tree, 81 product modules and 7 test modules, with zero origin errors. Both identify the three selected modules above. These are local G receipts, not cloud inputs; the published check folder includes the observer plugin and selected-module summary, while the full origin census remains in ignored `_build` storage.

The `B.md` relative link resolves to `integration/checks/2026-10-07-ninth-wave/B-gateway/README.md`, whose receipt link resolves locally. The run context is the local isolated archive under `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/R/incoming-20261007-0837/B-local-numeric/`; it used the existing read-only G environment, no install and no production data. This is local test evidence, not a cloud run.

Scope stays narrow: this supports the HTTP numeric decoder and its cost/status consumer. `B.md` correctly keeps the original B120 controller-spend bridge open, states `new_source_accepted: []` and `new_findings_closed: []`, and holds the broader merge carrier for the inherited `ArtifactRef` write-scope issue. It does not label a failure inherited under P41. No broader source or carrier admission follows from these receipts.

## Publication delta: observer snapshot classification

## Publication delta: observer snapshot classification

The updated check bundle now retains the executed observer as `g_origin_plugin.executed.py.txt`, explicitly labeled verbatim non-executable evidence, rather than as a maintained `.py` module. Its 5,891 bytes match the previously recorded executed-plugin SHA-256 `cd9356c4ed7ea8adb953edbb5f9371b254123b18a735f9520061d904f9f1c22b`. The preserved full lint output `executed-observer-ruff.txt` is 2,315 bytes, SHA-256 `3b0a506384c35757ac2bf2eafeca4597b13f0e3487ba4804db5833778737d0e3`: exit 1, exactly four style diagnostics (ANN401 twice, E501 twice).

`receipt.json` (SHA-256 `761b122afdf946931fa32f6f4cc974024aa48de5d2f2f3d259d71c19389ae4b0`) and the updated README classify this as snapshot-only Ruff failure, separate from the successful two-path product/test Ruff run. They state no observer source was changed or rerun and no candidate/control result changed. The distinction is accurate; the bounded numeric evidence GO above remains unchanged, with no claim that the observer snapshot itself passes Ruff.

## Final artifact representation delta

## Final artifact representation delta

The four historical raw-output names above are now represented in the check folder by lossless UTF-8 JSON containers; their decoded streams are byte-identical to the original raw outputs. Receipt-bound `decoded_bytes` and `decoded_sha256` match the earlier values: candidate stdout 6,831 bytes (30 passed); candidate JUnit 5,817 bytes (30 cases, 0 failures); control stdout 48,763 bytes (20 failed / 10 passed); control JUnit 40,767 bytes (30 cases, 20 failures). The full current paths end in `.stdout.txt.lossless.json` / `.junit.xml.lossless.json`; physical container hashes are separately bound in `receipt.json`. This preserves native trailing whitespace without editing the output. Root reports `git diff --check` passes for the wrapper representation; no tests or reruns were performed for this delta.
