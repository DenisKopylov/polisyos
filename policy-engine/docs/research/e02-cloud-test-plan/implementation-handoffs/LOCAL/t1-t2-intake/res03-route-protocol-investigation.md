# RES-03 route and read-protocol investigation

Date: 2026-10-10  
Companion to [`res03-authentic-intake-readiness.md`](res03-authentic-intake-readiness.md); its input boundaries and earlier receipts remain unchanged.

This investigation resolves the application route, the minimum catalog read, and the reason no authentic database read was attempted. It made no source/test changes, did not open the named DuckDB file, and did not start a server.

## What the configured code can do

The current B13 integration test at `tests/integration/scientist/test_res_03_real_simulation_route.py::test_res_03_real_simulation_later_failure_reaches_user_route` exercises an actual Foundry simulation and the persisted-CAS/debug-reader route. It does not exercise Fabric acquisition or the nominated Catalog input:

- `_build_real_trinity` builds `GlobalState.empty(...)`, persists a state snapshot, and wraps that ref in a `DataSnapshot`. The test puts this `data_snapshot_ref` into `ExperimentState.inputs` before executing the workflow.
- `BuildDataSnapshotNode.execute` returns immediately when `INPUT_DATA_SNAPSHOT_REF` is already present. Thus the workflow’s `build_data_snapshot` node does not call the Fabric port in this test.
- The execution context uses `DefaultFoundryPort()`. The test app is then a `TestClient` over the test CAS; the reader checks artifacts produced by that fixture run.

The actual Fabric producer is a distinct route. `DefaultFabricPort.snapshot` consumes a `DataViewRequestRef`, resolves its dataset selector (`metrics[0]`, otherwise `request_id`), calls `_enforce_execution_tier` through an injected `catalog_store.get_dataset(dataset_id)`, then calls `fabric_get_data` and writes the payload/schema/quality/snapshot artifacts. That route needs an exact request selector and a selected connector/profile; neither is supplied by the B13 test or the current L01/L02 packet.

The HTTP runtime does expose an injection seam: `create_runtime_api_app` accepts `catalog_run_profile` and `container_overrides`; `RuntimeContainerOverrides` accepts `control_registry_providers`; and `resolve_control_registry_providers` accepts both `gy_catalog_graph` and `catalog_run_profile`. The default provider instead calls `build_slice0_fixture_catalog_graph`. Therefore a future controlled served test can inject an admitted provider bundle, but setting `POLISYOS_PRODUCTION_DATA_ROOT` or passing a profile label alone would not select the source graph or create the missing `DataViewRequest`/source-backed snapshot.

## Read method and bounded query

`DatasetCatalogGraph(db_path, index_dir)` wraps `DatasetCatalogStore`, whose direct `get_dataset(dataset_id)` query is `ds_datasets WHERE id = ? LIMIT 1`. The store opens its baseline via `open_catalog_read_session`; with no overlay that helper calls DuckDB with `read_only=True`.

The public graph constructor is not a minimal-I/O option for this 1,320,693,760-byte file: `DatasetCatalogStore.__init__` calls `_fetch_source_identities()` before opening the session and again after it opens. `_fetch_source_identities()` streams every file byte in 1 MiB chunks into SHA-256. Instantiating the graph against this database would read the full file twice (and a present overlay as well). No such scan was authorized or performed; the heavy-slot receipt remains `not_established`.

After C05 supplies the exact selected profile and L01 supplies the exact source selector/ref, the smallest direct read-only discriminator is one exact dataset row and, only if the selected profile names one, its exact distribution row. The query must bind supplied IDs; no wildcard search, table census, vector/index query, count, or payload selection:

```sql
SELECT id, title, source, dataset_id, source_dataset_id,
       execution_tier, last_updated
FROM ds_datasets
WHERE id = ?
LIMIT 1;

SELECT id, dataset_id, connector_type, profile_id, source_locator,
       parser_supported, machine_readable, checksum
FROM ds_distributions
WHERE id = ? AND dataset_id = ?
LIMIT 1;
```

Use `open_catalog_read_session(Path(exact_admitted_catalog), overlay_path=None)`, pass only the source/profile-provided values to the parameter placeholders, and close the connection in `finally`. The first query is the dataset identity/eligibility check; the second is omitted unless a selected distribution ID exists. A raw row read is not by itself an admission: the profile, source/version, authority purpose, relevant time role, and consumer binding still need their owner packet and an independently observed serving context.

## Why the read is still unqualified

The pinned L01 B packet (SHA-256 `b2ea97c8e1e9001e33e5c96a15208809d283117d429b0bc97d2a41c256c41ac5`) says B13 is `limited`; `catalog_fetch_source_unreadable` is a prior, unreplayed error; its terminal join is UNRUN; and A must provide the exact local input packet and refs. It does not supply a query selector.

The L02 input packet (SHA-256 `a6104430660f645c96d0308a5ab5dbae21695cf78400e5bec4fbd607d859907f`) separates the required waves:

- **V1** needs matching L6/local Catalog-acquisition-history inputs, the artifact pair and matching manifest or legitimate versioned replacement, and source/context/tenant/run refs. It assigns the factual input to L01, accepted Catalog/profile to C05, and the served lifecycle consumer to C10. Its status says the L01 packet, actual host input identity, and configured profile are not established.
- **V6** is conditional on V1 plus Q1/R1 and needs an actual served simulation producer, a later independent failure, persisted success/history/CAS ref, and the exact sibling error. The task packet says Q1/R1 and V1 are absent.

The separate `l02_serving.json` (SHA-256 `899d03373a461ae1763162b5b626b0b5d95f76e874fc01427a97603705b9528b`) is the I4 Catalog/Legal profile task for LA-028/LA-040, not the V1 RES-03 profile. It cannot supply this selector. L01 A (SHA-256 `09be5b5b98e9daeb61f0704e7f50f247f1e17db924c535ee8a0ec4a564597b38`) covers B01–B03 L6 loader/context facts; it says the matching custodian-bound pair and authentic served route are not established. It is not a V1-selected Catalog/acquisition packet.

The current shell’s production-root/execution-profile variables are unset and the listener check found no Python/Uvicorn PolicyOS listener. The already-recorded file metadata proves only that the named path exists and is readable. There is no live root/profile/request context or owner-selected dataset/distribution key with which to bind the SQL. Consequently I did not open the file for schema discovery or run even the parameterized query with a guessed key.

## Concrete next protocol

1. **L01/A packet:** identify the logical catalog locator and exact source/version/ref, allowed non-secret content identity (if the custodian supplies one), selected matching L6/artifact pair and manifest/replacement, time-role and purpose, plus tenant/run/context refs. Keep rows/text/vectors out of the packet.
2. **C05/V1 packet:** identify the exact current Catalog/acquisition profile and selected dataset ID plus any selected distribution ID/profile. Preserve source/profile version and selection semantics; do not infer a `prod_full` or Legal profile.
3. **C10 + B/R1:** identify the current served simulation/history route and the admitted producer/collector refs. Pin the actual serving root/profile/context from the existing process or the controlled test’s exact injection seam.
4. **G read slot:** once those selectors exist, authorize one read-only query pair above. If the intended consumer requires `DatasetCatalogGraph`, first decide whether its two whole-file identity scans are warranted; do not hide them behind a TestClient or describe a direct query as consumer verification.
5. **B13 falsifier:** run the admitted producer through CAS and the fresh served reader; assert the exact partial result and later sibling error survive. Then remove/corrupt/mismatch the result ref and assert refusal and zero unintended CAS/history effects. The current fixture test remains a bounded positive for its synthetic-state route, not proof of the selected source context.

If the owner packets cannot be obtained, the accurate outcome remains `limited` for authentic B13: the runtime fixture path is implemented and exercised in source, while the authentic source/profile bridge and its semantic test remain missing. This is a missing-input boundary, not a conclusion that the source is unavailable or that no legitimate versioned replacement exists.

## Pattern check

P05/P32: a readable pathname or profile string is not custody/permission. P10: record/route shape does not prove the source-backed effect. P37: the actual selector, version, and profile-to-consumer binding are `not_established`; they must be supplied/reconciled before the authentic run. P38: the existing synthetic `DataSnapshot` is the proxy; the divergent case is a production source/profile mismatch while the TestClient fixture still passes. P40: do not repair repeated variants of this same source-to-consumer bridge one selector at a time; either widen the admitted binding to the complete selected input tuple or retain the bounded limitation and its falsifier.

## Controlled route rerun addendum

The C05 controls and B13 route selector were then run with `POLISYOS_CACHE_HOME=/tmp/e02-res03-c05.ljBoGO/cache`, `-n 1`, `--capture=tee-sys`, a retained JUnit file, and a dedicated `--basetemp`. The selector is a controlled fixture route; it did not open the production catalog or establish a live serving profile. The three C05 profile absent/conflict/malformed controls passed in the earlier combined run. The first B13 run stopped at `tests/integration/scientist/test_res_03_real_simulation_route.py:482` because direct Pydantic equality compared the dynamic branch-journal class names even though both references printed the same four typed values: canonical artifact ID `sha256:78ec2c226fcfcf112c3ebac23ccf96e15a9657b944538ea63dda259d5b3b6114`, kind `foundry.simulation_result`, media type `application/json`, and manifest profile `None`.

With the approved test-only change to compare all four fields, plus local kind/profile mutation falsifiers, the route test advanced past both reference assertions and failed later while constructing its foreign-tenant negative fixture at line 765. It tried to write a manifest bound to tenant `bbbb…/cell-b` while the ambient CAS owner remained `aaaaaaaa…/cell-a`; `FileSystemCAS._require_bound_context_for_owner` correctly refused with `ArtifactOwnershipError("Manifest is bound to a different tenant")`. This is a fixture-construction error before the foreign-route refusal assertion, not an application-route pass/failure. The original CAS ownership protection remains intact. The full failed output and JUnit are retained at `LOCAL/t1-t2-intake/receipts/res03-route-witness-20261010.txt` (SHA-256 `51c07c0e7c52f323b14385b17438f8bf99d23ae73a8734e0a576088c20a50a07`) and `.xml` (SHA-256 `84e5d8a176e5095ff66c51714c4fb948b2b0b5399d563aff13d06f43474aae31`). The prior unmodified-wrapper fail remains separately retained; neither is overwritten.

The test-only helper now uses the canonical public `str(ref.artifact_id)` and compares `kind`, `media_type`, and `manifest_profile_sha256` as well. Its in-test controls show changed `kind` and changed valid selected profile compare unequal; this is not an ID-only equivalence. The test still contains subsequent body/manifest input-role and CAS-read integrity/consumer assertions, but the rerun has not reached the later assertions after the foreign fixture failure, so those remain source-level expectations rather than this run's receipts. Source/test-input hash manifests before and after this run match (`b08f2eeedbfc74d4614393e54407a397605950ca622037f79adb94c154119988` each); exact source list is retained in `LOCAL/t1-t2-intake/receipts/res03-source-input-hashes-{pre,post}-20261010.txt`. The test inputs are generated in that named test and its temporary CAS; there is no external fixture file to hash.

The production-input disposition remains `limited`: no exact L01 selector/profile/source-version/consumer tuple was received, so the read-only SQL remains intentionally unexecuted against the 1.32 GB catalog. A `prod_full` profile in a controlled test is only a configured witness, not evidence of a deployed/current serving context.

## Final controlled verification

After the parent-approved ownership-aware test fixture correction, the three C05 profile-boundary tests and the B13 integration selector passed together: **4 passed, 4 dependency deprecation warnings, 36.46s**, under one pytest worker and an isolated cache (`/tmp/e02-res03-final.l8yD9I/cache`). Full output SHA-256 `b73e958996a7e7e71ebd8d821350c235636962690046aea9fb52a2b1f1eb28b2`; JUnit SHA-256 `aa16335ceda3c0c4e8afefb48acbb2a0ab5a15a4aae7b3d56bead812ec7f9846`. The full stream and JUnit remain in `LOCAL/t1-t2-intake/receipts/res03-final-controls-witness-20261010.{txt,xml}`.

The successful B13 selector exercises the test-authored Foundry simulation producer, temporary CAS persistence, later failure plus independent sibling and dependent skip, the fresh in-process TestClient candidate reader, returned scoped error, body/manifest assertions, CAS integrity verification, and wrong-node/ref/run/tenant/schema/tamper refusals. The `SimulationResultRef` handoff assertions compare the complete four-field ref identity; the valid kind and selected-profile perturbations are rejected. B and wrong-cell fixtures are verified through their actual owner views before the A/cell-A reader attempts access; cross-owner refusal remains generic `unavailable` at the CAS boundary. This is a positive for the controlled fixture implementation only. It does not establish any production catalog/source selection or live currentness.

Pre/post source and in-test-input manifest hashes match (`cf4c1efefb3fa113ba822f42cdfeb5cf4896673b150bb44c0cb3ef8c076c457e` each). The source list is retained in `LOCAL/t1-t2-intake/receipts/res03-source-input-hashes-{pre5,post5}-20261010.txt`; the test has no external fixture file, because its input data and temporary CAS are generated inside that integration test. `ruff check --ignore B009` on the test file passes. Full Ruff still reports two existing B009 violations at the unchanged `_coerce_put_options` lines 104–105; they are outside this narrow test repair.

The earlier fail receipts were preserved as deciding diagnostics: wrapper-class comparison (`res03-wrapper-assertion-diagnostic-20261010.txt`), fixture owner mismatch (`res03-route-witness-20261010.{txt,xml}`), and the now-correct CAS refusal expectation (`res03-route-witness2-20261010.txt` and `res03-route-witness3-20261010.txt`). They explain why the test-only repair and expected refusal codes changed; none is represented as a product source failure.
