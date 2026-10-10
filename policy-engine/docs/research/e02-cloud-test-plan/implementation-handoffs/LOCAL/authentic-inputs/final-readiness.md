# RES-03 final authentic-input readiness

Read-only intake at the coordinator-declared freeze anchor `9de48febba1ef18c8e1252dc027cb0d89b88abc3` (tree `d524ed13bdbcf6b7e65b838ca2a42f70df15d5c9`). I did not run Git, tests, the helper, an HTTP request, a server, a database query, or a production-file read. Private absolute locator values and member digests are intentionally omitted.

## Decision

No exact authentic RES-03 invocation can be populated from the named inputs. The current shell has none of the required `RES03_*` bindings, and the named L01/L02 records do not select a live serving instance or an admitted catalog/acquisition request. Keep the authentic positive `not_established`; do not substitute the L01 L6 bundle, a fixture run, a working-directory default, or a guessed endpoint.

The current process reports these required fields as unset: `RES03_RUNTIME_BASE_URL`, `RES03_EXISTING_CURL_CONFIG`, `RES03_RUN_ID`, `RES03_SELECTED_ROOT`, `RES03_MANIFEST_RELATIVE`, `RES03_EXPECTED_DATA_SNAPSHOT_REF`, `RES03_EXPECTED_FABRIC_TRACE_REF`, `RES03_MEMBER_A_DESCRIPTOR_POINTER`, and `RES03_MEMBER_B_DESCRIPTOR_POINTER`. `POLISYOS_PRODUCTION_DATA_ROOT`, `POLISYOS_EXECUTION_PROFILE`, and `POLISYOS_CATALOG_RUN_PROFILE` are also unset here. This is only this process’s environment; it does not establish whether a service exists elsewhere.

## Named receipt boundary

The unified task `INPUTS.json` is `b000d61906fc0d732287f1a50cbb1ca902c23f4d08a292e4330734f5147431da`; it names two private custody roots. I followed the paired aliases from `LOCAL/t1-t2-intake/README.md` and read only these named metadata receipts:

- L01 B packet `L01::parallel-20261008-l01/packets/B.json` (`b2ea97c8e1e9001e33e5c96a15208809d283117d429b0bc97d2a41c256c41ac5`) reports B13 `limited`, `production_input_admission=not_established`, and `input_bytes_digest=withheld_no_disclosure_admission`. Its prior `catalog_fetch_source_unreadable` is historical and unreplayed; its authentic consumer join is not established.
- L01 A-L6 packet `L01::restart-20261008-bindings/packets/A-l6.json` (`c6ab16fa192483dbfaccca6b634e79129709e6d2ba6f7b05d9e152090a3bf61f`) is an owner-default L6 substrate/observation-routing bundle, not the B13 catalog/acquisition selector or served profile. Its three selected members include two whose recorded size and checksum comparisons fail and one that matches. The member records give logical aliases and comparison outcomes, not the JSON Pointers or relative file paths required by the helper.
- L01 binding readback (`d3c8e15fa6a76e93703db0e38e837c7c1b5597674e0716943de04a29f7025e43`) and source receipt (`5092071cf08f36358a3eb00b77e3169ea5dbf47a02e4141fcca5bf75baf38d38`) do not supply the missing B13 selector/profile/run join.
- L02 manifest (`L02::manifest.json`, `c8b83ebe68bbd3568d9bceb7626863c3acb5616ab2c717bf2a3d13130b0cc769`), late-input correction (`8f06c226e12132c91b836507d014cbc161f53f998054817edabdee20d941c347`), and input-packet matrix (`a6104430660f645c96d0308a5ab5dbae21695cf78400e5bec4fbd607d859907f`) establish that the L01 packet exists. They leave the criterion-matched source/profile/owner/API/currentness tuple and authentic served readback unestablished.

The prior controlled RES-03 route is a fixture witness: it supplies synthetic state and refs to a temporary CAS and reads them back through a fixture client. It does not identify or consume the selected local catalog/acquisition input, nor does it identify a current local service. Its result cannot fill the live `RES03_*` environment.

## Bounded invocation for the owner-selected instance

Once the existing local service owner supplies the tuple below, this is the one permitted read-only request. It pipes the fresh response directly into the helper; the helper reads one selected manifest and exactly two distinct members. It does not open DuckDB, enumerate a root, or save the response body. A unique ignored output file is created with restrictive permissions. Do not run this block with guessed or fixture values.

Required owner-bound environment before the request:

- `RES03_RUNTIME_BASE_URL` and `RES03_EXISTING_CURL_CONFIG` for the already-running selected local service; do not start a new service or expose the config contents.
- `RES03_RUN_ID` for the real run whose fresh read is intended.
- `RES03_SELECTED_ROOT` and `RES03_MANIFEST_RELATIVE` from that run’s selected source/root binding, not from a default or the L01 L6 alias.
- `RES03_MEMBER_A_DESCRIPTOR_POINTER` and `RES03_MEMBER_B_DESCRIPTOR_POINTER` as two distinct strict JSON Pointers into that one source-owned manifest, selecting the genuine previously named pair. Do not infer them from logical aliases; they are not present in the L01 receipt.
- `RES03_EXPECTED_DATA_SNAPSHOT_REF` and `RES03_EXPECTED_FABRIC_TRACE_REF` as JSON objects issued by the independent source/request binding. Each requires canonical `artifact_id`, `kind`, and `media_type`; a profileless legacy ref remains explicitly unverified and cannot satisfy protected binding. Do not copy expected refs from the GET response.
- `RES03_RAW_RECEIPT` as a new unique path beneath `LOCAL/raw`.

```sh
PRODUCT=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
LOCAL="$PRODUCT/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL"
CHECK="$LOCAL/raw/final_authentic_read_only_check.py"

: "${RES03_RUNTIME_BASE_URL:?owner must select an existing local service}"
: "${RES03_EXISTING_CURL_CONFIG:?owner must provide its existing private curl config}"
: "${RES03_RUN_ID:?owner must bind the actual run}"
: "${RES03_SELECTED_ROOT:?owner must bind the run-selected root}"
: "${RES03_MANIFEST_RELATIVE:?owner must select a manifest under that root}"
: "${RES03_EXPECTED_DATA_SNAPSHOT_REF:?owner must supply independent expected ref JSON}"
: "${RES03_EXPECTED_FABRIC_TRACE_REF:?owner must supply independent expected ref JSON}"
: "${RES03_MEMBER_A_DESCRIPTOR_POINTER:?owner must supply first manifest pointer}"
: "${RES03_MEMBER_B_DESCRIPTOR_POINTER:?owner must supply distinct second manifest pointer}"
: "${RES03_RAW_RECEIPT:?choose a new unique ignored LOCAL/raw output path}"

set +x
set -o pipefail
umask 077
curl --fail --silent --show-error \
  --config "$RES03_EXISTING_CURL_CONFIG" \
  "$RES03_RUNTIME_BASE_URL/api/v1/runs/$RES03_RUN_ID/evidence-context" \
  | PYTHONPATH="$PRODUCT/src" "$PRODUCT/.venv/bin/python" "$CHECK" \
  | tee "$RES03_RAW_RECEIPT"
```

No values above are set by this note. The helper SHA-256 is `d8f44b0f2ff8983839f72345865e77d82479a84eb5dc7c46e03161f32d4082ec`. Its output compares canonical typed-ref identity and profile fields, but explicitly does not verify artifact-body custody, the live serving profile, the original request selector, or source currentness. Exit 3 means the bounded physical and persisted-context comparisons match while full closeout remains incomplete; exit 2 means refusal or mismatch. A profileless legacy ref is unverified, not a protected positive.

## Smallest missing input and falsifier

The smallest missing input is one source-owner-supplied tuple joining (a) the exact catalog/acquisition/history source and its matching or already-versioned manifest/member pair, (b) the selected `DataViewRequestRef` or equivalent independent expected snapshot/trace refs with profile and time/currentness basis, and (c) the currently selected local service root/profile/context and actual run ID. The source owner must supply the two member pointers from that exact manifest. No alternate manifest, profile, member pair, or run may be chosen by this helper author.

The bounded falsifier is a fresh GET for that run in which the owner-bound manifest and both named member comparisons match and both expected typed refs have the same canonical identity and selected profile; changing the owner-bound root, manifest, or refs must refuse or remain unverified. A serving-process profile change is not detectable through this API and remains unresolved. This proves only the bounded selected bytes and persisted tuple. The API does not expose the serving process profile or original request ref, so independent owner/currentness evidence remains necessary even if the helper returns 3.

P40: **same custody/currentness class, one level deeper**. The helper now measures the exact manifest/member and typed-ref comparisons, but the second layer still lacks the source-owner and live-serving tuple. The smallest closure is one admitted owner-bound selection plus currentness binding consumed by the existing producer and fresh reader. Without that tuple, retain `input_missing`, `bridge_missing`, `verification_missing`, and `semantic_test_missing` for the authentic path, while preserving the controlled fixture witness separately. Do not open a sequence of per-alias or guessed-service repairs; the falsifier above distinguishes a genuinely selected current input from the existing fixture route.

No private raw receipt was created because the named inputs contain no executable selected tuple to protect. No production files, private member contents, service endpoints, or credentials are recorded here.
