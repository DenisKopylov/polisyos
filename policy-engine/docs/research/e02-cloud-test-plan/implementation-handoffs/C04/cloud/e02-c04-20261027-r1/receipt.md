# C04 / I3 cloud receipt (`e02-c04-20261027-r1`)

## Identity and admission

- Environment: `polisyos` (`6965429cdb308191a0e6eb63cb118ea3`); checkout `/workspace/polisyos`; observed branch `work`.
- Base commit/tree: `8db01b1076e425b7998b05a658776c991b7bd594` / `1706923ebe943f1a332dca4860cd145ddd366e36`.
- Admission resources: overlay disk 32 GiB total, 28 GiB free; RAM 17 GiB total, 16 GiB available; no swap.
- Inputs: product proposal SHA-256 `2018c9554ff2da0e1be4fcfca6b4b67e4351058c0947c0bdebf9940f830977a9`; test proposal SHA-256 `87588f51b8b8f9b10763f9681ccb748db4edddb4f6d3fa498965dc629c92b5ee`.
- Backend/profile: repository `.venv`, pytest defaults/plugin autoload, `OMP_NUM_THREADS=1`.

## Delivered source and bounded results

The source-local promotion route resolves the aggregate evidence bundle and provenance graph, content-binds each source's persisted result and boundary, and promotes each independently confirmed cursor. Typed source-local fetch failures continue without granting promotion. EventStream no longer manufactures positional provider identity.

- PASS: `env OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q -ra tests/unit/fabric/data_plane/test_e02_c_streaming_oracle.py -k 'b80_two_source or b83_event_stream_preserves or b83_missing_owner_identity'` — 3 passed.
- FAIL: full four-module command — 113 passed, 6 failed in the final pre-adjustment replay. Four EventStream-dependent regression fixtures lacked explicit provider keys and were corrected afterward; the two B79 cases expose an existing case-sensitive REST response-header lookup (`dict(resp.headers)` followed by `get("ETag")`) that converts the local server's `Etag` response to a content-hash version, so the sound ETAG boundary refuses promotion. The defining B80/B83 failures were corrected and replayed by the focused PASS above. A final four-module replay after the regression-fixture correction is required.
- WARNING: `/usr/bin/time -v ...` was unavailable (`/usr/bin/time: No such file or directory`), so suite wall/RSS was not measured.
- UNRUN: independent two-OS-process 86,399/86,400-second B83 proof; the inherited test recreates runtime objects in one pytest process and is not sufficient.
- UNRUN: property-removal test that destroys an admitted owner-contract/runtime binding; no such binding is delivered here.

## Admission labels and remaining state

| Predicate / capability | Frozen label or state | Result |
|---|---|---|
| persisted CAS bytes and artifact identity | `recomputed` | resolved and content-bound |
| per-source result/provenance/run join | `recomputed` | promotion fails closed on mismatch |
| finite fixture source records | `independently_reconciled` | B80 positive and binding-negative pass |
| provider completeness and live-source currentness | `not_established` | no production claim |
| key/version/scope owner semantics | `not_established` | positional identity removed; missing identity refuses, but typed owner contract is `bridge_missing` |
| durable two-process horizon | `semantic_test_missing` | exact proof remains UNRUN |
| public/generated/schema companions | `surface_out_of_scope` | no common generated family mutated |

## Unapplied companion proposal

A separate, versioned owner extension is required rather than changing SourceContract v2 serialization: bind connector ID, dataset pattern, concrete schema ID/version/content hash, event-id role, source-version role, partition/scope roles, key policy and compatible retention horizon. The existing source-contract conformance owner must resolve that extension and hand the bound identity to the streaming runtime; missing, duplicate, ambiguous, mismatched or unresolvable roles must raise `StreamDedupeUnsupported` before writes. The later shared-family writer must update `schemas/fabric/source_contract.schema.json`, affected snapshots, OpenAPI/client/dashboard/public inventories, and run their documented recomputing validators plus corrupt-field expected failure. No compatible genuine resolver exists in this slice, so this work does not trust field names or self-attestation.
