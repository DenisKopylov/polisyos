# RES-03 authentic closeout admission (current source)

Date: 2026-10-10. Read-only review anchor: candidate `codex/e02-unified-local-20261009`, HEAD `c9d0941864a801e3f143b5cc2e94ec1c26f72e22`. This is an admission check, not a source freeze or a formal B13 closure. I did not start a server, run pytest, open/query the catalog database, inspect production payloads, or change production bytes, manifests, or descriptors.

## Finding

The authentic RES-03 run remains held because the current admitted inputs do not join a specific catalog source and acquisition profile to a `DataViewRequestRef`, the actual serving root/profile/context, and the persisted simulation readback. The available L01 receipts do prove a bounded local custody fact, and the current code has a supported Fabric producer and injection seam. Neither fact supplies that missing join. This is `input_missing` for the criterion-specific selector/profile, `verification_missing` for a current serving-root/context binding, and `bridge_missing` for the authentic source-to-producer path. It is **not** evidence that the catalog or its owner is absent.

The original B13 criterion is that a real simulation result remains available, with its scoped later-stage failure, through the served consumer; the earlier failure must not erase independently completed work (`B_r19_original.md`, §B13, lines 349–359). The RES-03 acceptance note adds the specific prerequisite to admit the local read-only catalog before the TestClient run (`closure-decisions/B.md`, RES-03/B13, lines 276–284). Neither criterion requires inventing a general external issuer contract.

## Named L01/L02 custody evidence

Unified-local `INPUTS.json` (`@b000d61906fc0d732287f1a50cbb1ca902c23f4d08a292e4330734f5147431da`) declares two private local custody roots. `LOCAL/t1-t2-intake/README.md` defines the paired relative aliases: `L01::` is under `implementation-handoffs/L01/`, and `L02::` is under `implementation-handoffs/L02/parallel-20261008-l02/`. I followed only those named roots and selected receipt files; I did not enumerate either root or expose its absolute path.

The first named root contains these exact L01 custody receipts:

- `L01/restart-20261008-bindings/packets/A-l6.json` — receipt SHA-256 `c6ab16fa192483dbfaccca6b634e79129709e6d2ba6f7b05d9e152090a3bf61f`.
- `L01/restart-20261008-bindings/evidence/binding-readback.json` — `d3c8e15fa6a76e93703db0e38e837c7c1b5597674e0716943de04a29f7025e43`.
- `L01/restart-20261008-bindings/source.json` — `5092071cf08f36358a3eb00b77e3169ea5dbf47a02e4141fcca5bf75baf38d38`.
- The selected root metadata also names `root-manifest.json` (`b893eb0590cf151afd89ed0cb0c288fddf09a93f3e36305679e33aaeb55dd6c3`), `l6-selected-bindings.json` (`551c1b66cd0644d6e7a29492d51952d7e18b3406c3fb5921ae9b6c6e3a1bc491`), and `public-alias-index.json` (`db427943dfd71c99ad1bf405f24a145b8769eb04f91a0de0f2bc0ddf40bd49b2`).

That is an L6 intervention-substrate/observation-routing bundle, not the RES-03 catalog/acquisition selector. Its declared profile is `research` and the receipt calls it an owner default, not an admitted served profile. Within its exact three-member comparison, root-to-bundle checksum binding passes and the observation-routes member matches; the knobs and Lex-map members do not match their declared descriptors. This is a real local custody observation, but it is neither a versioned replacement nor evidence for RES-03’s selected dataset. The active custodian, replacement legitimacy, relocation/currentness, admitted purpose, and served path remain `not_established` in the receipt.

The L02 source-pinned manifest (`L02::manifest.json`, SHA-256 `c8b83ebe68bbd3568d9bceb7626863c3acb5616ab2c717bf2a3d13130b0cc769`) and independent correction (`L02::prepared/l02_late_input_independent_review.json`, `8f06c226e12132c91b836507d014cbc161f53f998054817edabdee20d941c347`) establish that the published L01 packet exists. The correction explicitly limits that packet to factual navigation and bounded observations: it does not provide a source-matching profile or an authentic consumer. Therefore earlier wording that the L01 packet was absent is stale; the remaining RES-03 join is still `not_established`. The L02 review names the missing V1 pair as matching catalog/acquisition/history inputs or an accepted existing versioned replacement, plus source/context/tenant/run refs; it leaves the ordinary owned-context POST → N5 → persisted CAS → fresh GET witness `UNRUN` in that packet.

The L01 root-manifest profile and member comparisons are `owner_supplied` and `recomputed` only within that named L6 bundle. They do not establish the serving root, RES-03 request profile, catalog content identity, or currentness. No private absolute path or production-payload digest is reproduced here.

## Current producer, route, and divergent case

Current source identities at the review anchor:

| Source | SHA-256 |
|---|---|
| `tests/integration/scientist/test_res_03_real_simulation_route.py` | `9a572f253f82d3899895c8f9a9739e88314c73cf392115de6fb395ce5cce0d34` |
| `src/polisyos/core/contracts/fabric.py` | `390415a884778be3f78415c6610db9ea51e26484466d246859a912076a557bf7` |
| `src/polisyos/scientist/adapters/fabric_bridge.py` | `729648c0d5a46bce9799ba647530da02f9ad9e6a909fd7971303b53075e2a240` |
| `src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py` | `b2a37ad9d4bcafecc3f6185b01c6ec6fd179aa9dc0d256310ef2009b8485e658` |
| `src/polisyos/scientist/orchestration/workflows/builder.py` | `39b0a80bf4e336e42f60a32f44011869309b74f1d1297cab6705298320b26c95` |
| `src/polisyos/runtime/http/app.py` | `b726343afe9b1a57fed71c78b733bfd5e606d0ffebbb2d7fa84b67ed8b6a9ba0` |
| `src/polisyos/runtime/http/container.py` | `c9fb1621a7dce2b6889858145220f8e10679d40bfd5838141fa4704bc3ec814b` |
| `src/polisyos/runtime/http/services/control_registry_providers.py` | `cd7cb561b727fa91bfd96499aca13b122e36dbee49ecd4930425a63512a8a2a0` |
| `src/polisyos/data_forge/domains/catalog/knowledge/store.py` | `5a3b7f62744c1fc5c3d6ca214cc67a99cd50f827dc9013f51532d3d664e4c8f2` |
| `src/polisyos/data_forge/domains/catalog/knowledge/overlay.py` | `1d9f6fa8721a467dd214c751a26c81fb685b880975a16819914dd7bddd04297b` |

`DataViewRequestRef` is a typed `ArtifactRef` for `ir.data_view_request`. `DefaultFabricPort.snapshot` resolves the request’s dataset ID, checks its execution tier through the injected catalog store, calls the configured fetcher, and persists the retrieved artifacts. `BuildDataSnapshotNode.execute` calls that Fabric port only when the state has no `data_snapshot_ref`, a `data_view_request_ref` is present, and the execution context has Fabric configured. `build_execution_context` accepts `fabric` as an optional port and leaves it unset by default.

The current RES-03 test instead builds a `GlobalState.empty(...)` fixture, persists a synthetic `DataSnapshot`, supplies that snapshot and a generated default registry bundle in `ExperimentState.inputs`, and runs with `DefaultFoundryPort()`. Consequently `build_data_snapshot` returns early and no catalog/Fabric acquisition is selected. The test does exercise a real Foundry simulation, a later failure, an independent sibling, persisted temporary CAS artifacts, a TestClient debug read, and missing/corrupt/mismatch controls. Its app and CAS are temporary fixture resources. The concrete divergent case is a source/profile mismatch (including the old unreplayed `catalog_fetch_source_unreadable` report) while this route test still passes, because its path never asks that catalog for input. This is the P38 distinction: it tests the served partial-result property for synthetic inputs, not authentic source admission.

The prior 4-pass controlled receipt (`res03-final-controls-witness-20261010.txt`, SHA-256 `b73e958996a7e7e71ebd8d821350c235636962690046aea9fb52a2b1f1eb28b2`) used an earlier test source hash `7f1456fc14d2f15b88926e7d77388a3802d99b2e53311931db98a47e7d5f722c`, not the current test hash above. I therefore do not carry that pass as a replay receipt for this exact source. No current-source test was run in this admission task.

The HTTP injection path exists (`create_runtime_api_app` accepts `catalog_run_profile` and `container_overrides`; the container can receive control-registry providers). The default provider path can build a fixture catalog graph. The current RES-03 test does not pass a catalog profile or graph and does not use the production catalog. A profile label alone would not create a `DataViewRequestRef` or bind an external source to the run.

The current shell has no `POLISYOS_PRODUCTION_DATA_ROOT`, execution profile, runner backend, catalog profile, or cache override set; a process-name snapshot found no Uvicorn/PolicyOS runtime. This is a local observation, not evidence that a service or source is absent elsewhere. Source code defaults an unconfigured test-created app to the development execution profile; that default is not live serving context.

## Smallest safe next check

The exact dataset selector and optional distribution selector are not supplied by the named L01/L02 receipts, so I did not connect to the catalog or guess an ID. The smallest metadata discriminator, after L01 and C05/V1 supply the exact selected source/profile and opaque row IDs, is one parameterized dataset-row read and (only if that profile selects one) one exact distribution-row read using the existing baseline-only read session with `read_only=True`. Do not construct `DatasetCatalogStore` for this preflight: its constructor computes source identities by streaming the entire catalog twice. Do not scan tables, count rows, inspect payloads, or use a wildcard query.

Prepared post-freeze recipe (not executed; placeholders must be replaced by the source/profile owner, never by guesses):

```sh
cd /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
PYTHONPATH=src .venv/bin/python - <<'PY'
import os
from pathlib import Path

from polisyos.data_forge.domains.catalog.knowledge.overlay import open_catalog_read_session

catalog = Path(os.environ["RES03_ADMITTED_CATALOG_PATH"])
dataset_id = os.environ["RES03_ADMITTED_DATASET_ID"]
distribution_id = os.environ.get("RES03_ADMITTED_DISTRIBUTION_ID")
connection = open_catalog_read_session(catalog, overlay_path=None)
try:
    dataset = connection.execute(
        """SELECT id, execution_tier, last_updated
           FROM ds_datasets WHERE id = ? LIMIT 1""",
        [dataset_id],
    ).fetchone()
    print({"dataset_selected": dataset is not None,
           "execution_tier": dataset[1] if dataset is not None else None})
    if distribution_id:
        distribution = connection.execute(
            """SELECT id, connector_type, parser_supported, machine_readable
               FROM ds_distributions
               WHERE id = ? AND dataset_id = ? LIMIT 1""",
            [distribution_id, dataset_id],
        ).fetchone()
        print({"distribution_selected": distribution is not None,
               "connector_type": distribution[1] if distribution is not None else None})
finally:
    connection.close()
PY
```

That read is only the exact selector/eligibility check; it is not a complete source admission or served positive. After it, the owning profile must bind the same request and source into the existing Fabric producer, with an explicit configured catalog/profile context; the resulting snapshot and simulation refs must then be persisted and resolved through a fresh HTTP consumer. The normal B13 selector may be used for the controlled partial-result behavior, but its fixture must consume that admitted request/ref before it can serve as the authentic witness. A post-freeze verification plan is therefore:

1. Re-read only the exact owner-supplied manifest/profile and requested catalog rows through the admitted read-only alias; preserve the supplied currentness/version evidence.
2. Run the current B13 TestClient selector only after the actual request ref, Fabric port, selected catalog/profile, and context are wired; isolate any fixture cache if the route creates one.
3. Assert simulation success, a distinct sibling failure and independent success, persisted history/ref lineage, fresh HTTP resolution of the exact producer ref, and missing/corrupt/foreign-profile refusal. The authentic positive is established only if the served root/profile/context matches the admitted tuple.

## Required owner input, labels, and bounded residual

Smallest discriminating input from L01/A and C05/V1:

- An existing exact matching catalog bytes/manifest pair, or a legitimate already-versioned replacement for the changed bytes; the source owner and the profile’s purpose/time/currentness binding. Do not create a replacement manifest to make the check pass.
- The selected catalog/acquisition profile and exact dataset ID, plus an exact distribution ID only if that profile names one; the corresponding `DataViewRequestRef` or its owner-supplied selection inputs.
- The selected local serving root, profile, and request context for this run, with tenant/cell/run binding, and the existing consumer/API that will resolve the persisted ref. This is the minimum needed to distinguish an offline local receipt from the current served instance.

The external fact is not “the file exists.” The missing fact is which owner-selected catalog/profile and request are meant to ground this run, and whether the serving context used them. The code route and artifact types exist, so the remaining gap is not a request for a new issuer or an invented permission rule. If those exact owner inputs are unavailable, keep the authentic positive `not_established` and preserve the synthetic route as a controlled fixture witness. Do not infer global source absence.

P37 basis labels for this check: named receipt identity and its selected L6 file comparisons are `recomputed`; the L01 declared profile/version is `owner_supplied`; RES-03 dataset/profile selection, content binding, runtime root/profile/context, and currentness are `not_established`. For the authentic B13 path, the selected source/request is `input_missing`, source-to-Fabric/run binding is `bridge_missing`, the live consumer tuple is `verification_missing`, and the source-backed semantic positive is `semantic_test_missing`; the controlled synthetic route has its own fixture-level positive.

P40 bucket: **same custody/currentness class, one level deeper**. The new evidence resolves an authentic named L01 custody receipt but still does not join it to the RES-03 selector and live consumer. Stop at the class boundary; widen only through the owner-supplied matching source/profile/context tuple or record this bounded residual with the falsifier above. No site-specific code patch or protected positive is justified by the current evidence.
