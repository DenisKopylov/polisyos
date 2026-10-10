# Final authentic read-only closeout command readiness

Date: 2026-10-10. Source anchor supplied by the coordinating task: `f52809e8210714131f53c7b90bd53a9215c69d69`. I did not run Git, start a service, issue an HTTP request, open a catalog database, hash production files, run tests, or inspect payloads. This note prepares a bounded command for the existing selected local service after source freeze; it is not an execution receipt or a B13 closure.

## What the existing surface can establish

The runtime already exposes a fresh run-scoped GET at `/api/v1/runs/{run_id}/evidence-context` (`runs.py`, operation `get_run_evidence_context`). Its `RunEvidenceContextView` includes the run ID, `data_snapshot_ref`, `fabric_retrieval_trace_ref`, `production_data_evidence_context`, materialization refs, and related artifact refs. The debug projection builds the production-data context from the run’s persisted retrieval context. That is useful for checking which root and manifest hash the run recorded and which typed snapshot/trace refs the consumer currently resolves.

The API does not return the live process’s selected execution/catalog profile or the original `DataViewRequestRef` as direct fields. `/api/v1/health` reports service lifecycle/dependency status, not those selections. The evidence-context GET is consequently a fresh read of a run-bound persisted projection; by itself it does not prove the current serving process still uses that root/profile, prove source currentness, or bind the catalog selector. The owner of the already-running local service must independently supply its exact local base URL, run ID, selected profile, root, typed source/request tuple, and backend. Do not infer them from the `research` label in the old L01 receipt, from a working-directory default, or from this worktree.

The code-backed catalog read method is DuckDB’s `open_catalog_read_session(path, overlay_path=None)`, which opens the baseline with `read_only=True`. It supports a single parameterized dataset lookup and, only when the selected profile names one, one exact distribution lookup. The earlier readiness note shows that SQL. No selector was supplied in the named inputs, so the database remains unopened. Do not construct `DatasetCatalogStore` for the preflight: its constructor fingerprints the whole source twice.

## Named input boundary

The already-read `INPUTS.json` (`b000d61906fc0d732287f1a50cbb1ca902c23f4d08a292e4330734f5147431da`) names two private custody roots. I used the existing `L01::` and `L02::` aliases only; private absolute paths and production member bytes are not reproduced here.

The named L01 B13 packet (`b2ea97c8e1e9001e33e5c96a15208809d283117d429b0bc97d2a41c256c41ac5`) records `production_input_admission=not_established`, an unreplayed `catalog_fetch_source_unreadable`, and an authentic consumer join still `UNRUN`. The L01 A-L6 packet (`c6ab16fa192483dbfaccca6b634e79129709e6d2ba6f7b05d9e152090a3bf61f`), binding readback (`d3c8e15fa6a76e93703db0e38e837c7c1b5597674e0716943de04a29f7025e43`), and source receipt (`5092071cf08f36358a3eb00b77e3169ea5dbf47a02e4141fcca5bf75baf38d38`) identify the L6 substrate/observation-routing selection, not an admitted RES-03 catalog/acquisition source. Its selected profile is an owner default. In its declared member set, root-to-bundle binding and observation routes pass; the intervention-knobs and Lex-map members fail their declared size/checksum comparisons. This receipt cannot stand in for the currently selected serving input.

The L02 manifest (`c8b83ebe68bbd3568d9bceb7626863c3acb5616ab2c717bf2a3d13130b0cc769`) and late-input correction (`8f06c226e12132c91b836507d014cbc161f53f998054817edabdee20d941c347`) correct the earlier “packet absent” wording: the L01 factual packet exists, but the matching source/profile/owner/API/currentness tuple remains `not_established`. The previous local admission notes contain the exact selected L01/L02 receipt aliases and hashes; they do not name a matching current catalog selector or legitimate versioned replacement.

## Prepared bounded check

The existing one-row catalog-read recipe cannot verify physical member bytes or bind a fresh served read to one manifest/member pair. I prepared the ignored, unexecuted helper [`final_authentic_read_only_check.py`](../raw/final_authentic_read_only_check.py) for that narrow measurement. It reads one `RunEvidenceContextResponse` from stdin, one manifest under the owner-selected root, and exactly two distinct member descriptors chosen by JSON Pointer inside that manifest. It verifies the member paths remain under that root and compares each physical digest and any declared size. It performs no directory walk, catalog/DB connection, scan, write, or service startup. Its current SHA-256 is `d8f44b0f2ff8983839f72345865e77d82479a84eb5dc7c46e03161f32d4082ec`; `docs/research/**/raw/` is ignored by the repository root ignore rule.

After freeze, the service owner can bind the following already-existing inputs in their private shell or protected local config: `RES03_RUNTIME_BASE_URL`, `RES03_EXISTING_CURL_CONFIG`, `RES03_RUN_ID`, `RES03_SELECTED_ROOT`, `RES03_MANIFEST_RELATIVE`, `RES03_EXPECTED_DATA_SNAPSHOT_REF`, `RES03_EXPECTED_FABRIC_TRACE_REF`, `RES03_MEMBER_A_DESCRIPTOR_POINTER`, `RES03_MEMBER_B_DESCRIPTOR_POINTER`, and a unique ignored `RES03_RAW_RECEIPT` path. The two expected refs must come from the independent source/request binding or existing run owner record, not be copied from the GET response being checked. Descriptor pointers and field names must be read from the one selected manifest. Keep credentials and absolute roots out of the tracked note and terminal transcript.

The command below calls only the already-running service and stores the helper’s redacted hash/status output under ignored `LOCAL/raw`. An exit code of `3` means the bounded physical and persisted-context comparisons matched but the helper deliberately marks closeout incomplete; `2` means refused or a mismatch. Neither is a positive currentness/profile assertion.

```sh
PRODUCT=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
LOCAL="$PRODUCT/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL"
CHECK="$LOCAL/raw/final_authentic_read_only_check.py"

# Use the owner-selected existing local endpoint and its existing auth config.
# A successful health response establishes service availability only.
curl --fail --silent --show-error \
  --config "${RES03_EXISTING_CURL_CONFIG:?}" \
  "${RES03_RUNTIME_BASE_URL:?}/api/v1/health" \
  | "$PRODUCT/.venv/bin/python" -c 'import json,sys; p=json.load(sys.stdin); print({"status":p.get("status"),"service":p.get("service")})'

# One fresh run-context GET, one named manifest, and exactly two manifest-declared files.
# The owner supplies the exported RES03_* bindings described above before this command.
set -o pipefail
curl --fail --silent --show-error \
  --config "${RES03_EXISTING_CURL_CONFIG:?}" \
  "${RES03_RUNTIME_BASE_URL:?}/api/v1/runs/${RES03_RUN_ID:?}/evidence-context" \
  | PYTHONPATH="$PRODUCT/src" "$PRODUCT/.venv/bin/python" "$CHECK" \
  | tee "${RES03_RAW_RECEIPT:?Use a unique path under LOCAL/raw}"
```

The helper emits the manifest digest, the two member digests/sizes and declared-member pointers, run/root/manifest comparisons, typed-ref identity/profile statuses, and hashes of the compared request/context tuples. It omits root paths, run/ref values, and credentials from its output. A relative root reported by the persisted context is treated as incomparable rather than resolved against the helper’s working directory. Its `serving_profile` and `source_request_ref` fields remain explicitly unresolved because the existing evidence-context DTO does not expose them. A root/process-profile binding and the currentness/version evidence must be retained separately from the actual selected local service owner; do not treat the persisted manifest hash or `generated_at` as currentness.

If either descriptor uses keys other than `path`, `sha256`, and `size`, supply the exact key names through `RES03_DESCRIPTOR_PATH_KEY`, `RES03_DESCRIPTOR_SHA256_KEY`, and `RES03_DESCRIPTOR_SIZE_KEY` after reading that selected manifest. If either member has no declared size, the helper can compare its declared digest, but the size predicate stays absent; do not manufacture a size assertion. If a manifest’s member descriptor is not represented as a JSON object with an explicit relative path and SHA-256, stop and preserve the read-only raw receipt as `not_established`; do not infer a field or choose another pair.

Once the file/context check matches, the only catalog-backend discriminator remains the owner-supplied exact dataset ID and, if the selected profile names one, exact distribution ID. The existing `open_catalog_read_session(..., overlay_path=None)` recipe from `authentic-closeout-admission-current.md` can then run one parameterized row read against the exact selected catalog, with DuckDB baseline `read_only=True`. Omit the distribution query when no distribution is selected. Do not search for IDs or inspect payloads. A metadata row is still not source admission: the same accepted profile/request must reach the configured Fabric producer and the simulation output must resolve through the fresh consumer.

## Evidence limits and closeout decision

| Predicate | Current status | What a matching prepared command would establish |
|---|---|---|
| L01/L02 receipt identity | `recomputed` in the named receipts | Identity of those cited receipts, not that they are the currently selected RES-03 source. |
| Current selected root / manifest bytes | `not_established` now | A bounded run-context-to-manifest digest comparison for one later observed GET. |
| Two selected member bytes | `not_established` now | Physical SHA-256/size equality for exactly two descriptors from that same manifest. |
| Active serving profile/backend | `not_established` | `/health` and `evidence-context` do not expose the runtime’s selected profile/backend; source owner must bind the already-running process configuration. |
| Original request selector and currentness | `not_established` | The evidence-context DTO does not directly expose the original `DataViewRequestRef` or a currentness/expiry decision. The selected source/profile owner must supply the exact selector and a legitimate current/version binding. |
| Authentic simulation → persisted result → fresh consumer | `not_established` for the selected production input | The existing controlled RES-03 test proves a synthetic fixture route only; it skips Fabric/catalog acquisition when a `DataSnapshotRef` is already supplied. |

Keep capability labels for the authentic input path at `input_missing`, `bridge_missing`, `verification_missing`, and `semantic_test_missing` until the source/profile/request is selected, the actual producer consumes it, and the fresh consumer resolves the persisted output. The controlled synthetic route remains a separate fixture-level witness. Do not infer global source absence from an unset local environment or an unavailable local URL.

P40 bucket: **same custody/currentness class, widened to the complete selected pair**. The earlier notes already locate L01/L02 evidence and the one-row catalog read, but no selected root/profile/request tuple exists in the admitted inputs. The helper widens the bounded file check from a path-exists proxy to one manifest plus exactly two declared members; it does not close the same class’s missing owner/currentness binding. The class falsifier is an owner-selected current root/profile/request tuple whose manifest and two declared member digests match at the time of the actual GET, followed by the same request reaching Fabric and its persisted result being read through the fresh consumer. If no owner-bound tuple is available, preserve the bounded `not_established` result rather than add per-instance source guesses.

Pattern check: P05/P32 rule out treating a readable path, profile label, or matching digest as authority; P10 requires the actual source-backed simulation property; P37 classifies the gate’s own root/profile/currentness predicates; P38 names the divergence where a synthetic pre-populated snapshot passes while the selected production source differs; P40 keeps this within one custody/currentness mechanism. The failure/repair register was read at `docs/reference/policy-design-case-failure-patterns.md` (P05, P10, P32, P37, P38, P40).

## Source/input denominator observed

The following source files were read for this recipe and hashed at the local observation point; the candidate was still subject to the parent’s source freeze:

| Path | SHA-256 |
|---|---|
| `src/polisyos/runtime/http/routes/runs.py` | `5660b1ef01c76fb1dc5129b7fa1e76a3b9e0471b9b44d91764b2c8eac34fa4b8` |
| `src/polisyos/runtime/http/services/debug.py` | `66bcffb3645186f9bc886ce97963b049b8bd8f1573db7fed9758241e752e9180` |
| `src/polisyos/core/contracts/runtime.py` | `11659fd0ddde5d675699bcca77338a7bc1fd9c7ae359d1aac36ffb2a348f311d` |
| `src/polisyos/core/artifacts/manifest.py` | `a84690d4f683a107a51afffd655e7a8b9e2550aceb0ca0ce406cf56b1393bc3c` |
| `src/polisyos/runtime/http/services/control/production_data.py` | `af9fc09b0436cc22254efaecb747974e8d10961862edf8c61a14127e908ec4ac` |
| `src/polisyos/runtime/http/routes/health.py` | `65fb90134c54c203bab11c739dc7b9bc62b32f0041842550ebab0ac24cebd9e8` |
| `src/polisyos/runtime/http/container.py` | `9b96fa1cd315b5ebe715352232ddeddb3a0ce874798e36f75344ed714a31a29a` |
| `src/polisyos/runtime/http/routes/artifacts.py` | `f0a5dd379b991055074935299ed822eff7ad9ba598ab294bdf2bc210c75c8843` |
| `src/polisyos/data_forge/domains/catalog/knowledge/overlay.py` | `1d9f6fa8721a467dd214c751a26c81fb685b880975a16819914dd7bddd04297b` |

The pre-existing named decision inputs read as context were `authentic-closeout-admission-current.md@ced95ecf16172b983b1e990739c76dd47ece8574ec154442ab933d90854d21aa`, `authentic-closeout-final-local-attempt.md@38b44fcd1522964df523447ba19850e94c167fae4771bf60029e3787c4dfbbff`, and `t1-t2-intake/res03-route-protocol-investigation.md@8c6b435d1808afcea363383ad41290ca04f1f346d20d8f9f7b968c2d4600de2e`. No production input content or private absolute locator was read or copied during this final command-readiness pass.

Supporting local instructions/boundaries read: `docs/reference/policy-design-case-failure-patterns.md@a64956e284b411276a16a612afffb1fb42daf03ffef8f7ef1c3f3f9bc25d0349` and `.gitignore@77274a4c3534450075f1a95890b59cbacb17ee2a914de3d24916ca308626723c`.

## Helper static-boundary review

The helper was revised after a static review found three whole-boundary gaps. `_ref_matches` previously returned true for two empty mappings; it now requires the canonical `ArtifactRef` fields and validates both actual and expected values with the existing strict model (`extra="forbid"`, `model_validate(..., strict=True)`). Missing or malformed required fields refuse with a stable code. A profileless legacy ref can still be identity-compared, but reports `unverified_profileless_legacy`, cannot satisfy the protected-ref binding check, and cannot raise the helper’s exit status from 2 to 3. A matching ref identity does not establish custody of the artifact body; output says `artifact_body_custody=not_verified_by_reference_identity`.

JSON Pointer token decoding now rejects dangling/invalid `~` escapes and array positions except canonical nonnegative decimal indexes (`0` or a nonzero digit followed by digits). Thus `01`, `+1`, whitespace, and `~2` are refused rather than normalized. Resolve/open/read errors use fixed reason codes and exception type only; exception messages and absolute private paths are never emitted. Scope remains one explicitly selected manifest plus exactly two distinct named members, with no database access, directory census, or payload dump. Exit 3 still means only the bounded selected checks matched while independent profile/currentness binding remains incomplete.

This update was AST-parsed only; the helper was not executed, and no HTTP, tests, database, production payloads, or Git operations were performed. Helper path/hash: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/final_authentic_read_only_check.py@d8f44b0f2ff8983839f72345865e77d82479a84eb5dc7c46e03161f32d4082ec`.
