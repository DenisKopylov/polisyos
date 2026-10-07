# C3 current ING cleanup handoff evidence

This receipt is a documentation-only handoff for the frozen C source slice 07bbb61ffa6d53709942bcda87c37daef1a04651 (tree 4bb3d7ef227f7745ab22a23f41f4618766e8b350). Its parent/source slice base is C158 c158689d692d47b6300609ac2ba5e7dac28650dc (tree 573063f560533e73518ef87d29acc1a46959cf33). The criterion/document base remains fresh main 198076863e143dea9f89f02734b13d50dae3eed5; C2 root anchor 1ddcd7b3905e52c0d19db091823a64830139fa64 is an ancestor.

The candidate diff from C158 is exactly policy-engine/src/polisyos/fabric/data_plane/streaming.py plus policy-engine/tests/unit/fabric/data_plane/test_stream_cleanup_recovery.py. The implementation commit is separate from this handoff commit. No source, environment, G, production data, or finding ledger was changed to create this receipt.

## Property and evidence

The bounded property is cleanup-owner transfer: after stream-close failure or cancellation, the exact pool and pending physical handle remain reachable under the existing registry retry owner; retry uses that same handle; the primary error is preserved; capacity is released once; successful close clears the owner. The source tests exercise actual EventStream JSONL, pool and registry lifecycle, and FileSystemCAS checkpoint/chunk/window readback. The installed probe ran the same runtime from the exact wheel, with isolated Python and no PYTHONPATH, and observed same-handle retry, primary-error identity, cleared retry owner, and persisted readback.

The strongest negative controls remove only the cleanup-owner retention call. The focused source test then returns four failures at the retained-owner assertion. The installed mutant leaves the cleanup marker present but forces registry owner count to zero while the physical handle remains pending; the behavioral assertion rejects it. This is the named P38 divergence and the P29 remove-property-keep-markers witness.

## Deciding outcomes and limits

- Two targeted existing streaming suites: 128 passed with one unknown cache_dir pytest-config warning. The run used the frozen candidate source bytes while recorded HEAD metadata still named C158; its command/result/source hashes are preserved.
- Six focused cleanup cases: passed against the exact candidate source/test hashes. The available raw receipt does not preserve the original argv; a reproducible command is supplied in the machine handoff as a suggested replay, not represented as the historical argv.
- C158 baseline witness: two failing cleanup-owner cases are preserved. The original command and source/test hashes were not retained, so P41 inherited-red attribution is not_established.
- Ruff check and format check: pass.
- Architecture guardrails: exit 1; generated/freshness checks were explicitly skipped. No slice-base replay or complete input-denominator disjointness is recorded, so attribution is not_established.
- Production-invocation diagnostic: command exits 0 but reports coverage=partial, static direct-call reachability only, and runtime_invocation_established=false.
- Exact candidate archive wheel/sdist: offline build first failed because hatchling was not cached; one online fallback built both successfully. A fresh frozen base-only environment installed the wheel with normal dependency resolution. Atlas positive and nine corruption cases passed; the actual installed stream consumer and owner-removal mutant passed their respective property assertions.
- The independent source reviewer gave GO for this bounded C cleanup-owner transfer; that reviewer did not rerun tests or removal controls.

The installed receipt is scoped to a fresh Python 3.14 base-only profile, no dev/test/vector extras, no pytest or hnswlib, no PYTHONPATH, no production data/services/model weights, and no numerical workload. Atlas validation is a source-tree script outside the wheel; the probe independently checked package origins and imported jsonschema from the installed environment before adding the extracted archive root for the validator subordinate workspace import.

Boundaries: direct StreamingSourceSession construction without a registry stays caller-owned; a failure in synchronous in-memory registry insertion has no alternate owner; BaseException injection at a frontier seam is not OS process death. This does not prove spill-to-disk, RSS or full memory ceilings, pre-return connector allocations, full production behavior, B87, or unrelated B findings. B+C composition remains a separate branch/run and is not part of this C source admission. No C54 finding closure or status promotion is asserted.

Full source archive, wheel/sdist binaries, isolated environment, and generated source/artifact census maps remain in ignored scratch and are cited by SHA in the installed machine receipt. They were intentionally not copied into Git. The G refresh from a0ac10f to ebae80e added exactly 12 storage documents; the five immutable C inputs named in intake-refresh-ebae.json are byte-identical. The pinned G storage notes, referenced by exact commit and blob in evidence-index.json, state that old source archives were moved reversibly to Trash while current C root/CAN and sibling evidence were protected; this handoff did not perform G writes or cleanup.

Raw evidence copies are byte-for-byte from their ignored source paths. G's already-tracked storage notes are cited by commit, blob, and content hash rather than duplicated. evidence-index.json records each copied path, byte count, SHA-256, source, and role.

A receipt-local `.gitattributes` disables line-ending normalization for the three captured JSONL fixtures; this preserves the CRLF bytes of the frontier-resume input and its indexed SHA through Git checkout.
