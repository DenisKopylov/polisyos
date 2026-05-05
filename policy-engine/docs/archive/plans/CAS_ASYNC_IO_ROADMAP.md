# CAS Async I/O Status

The runtime closeout now treats async CAS as an implemented storage boundary,
not only a roadmap:

1. Sync callers still use the stable `ArtifactStore` contract.
2. Async callers now use the sibling `AsyncArtifactStore` protocol with async
   `has/get_bytes/get_manifest/put_bytes/put_json/verify/iter_artifact_ids`.
3. `build_async_artifact_store(...)` rebuilds an async CAS boundary from the
   same declarative `ArtifactStoreConfig` used for sync bootstrapping.
4. Filesystem-backed CAS uses `AsyncFileSystemArtifactStore` as the first-class
   async facade.
5. Non-filesystem backends remain supported through the guarded
   `AsyncArtifactStoreAdapter` bridge rather than ad-hoc executors.
6. Runtime control, scholar jobs, scientist checkpoint/executor paths, and
   fabric data-plane streaming/orchestration now consume the async contract on
   their hot paths.

## Evidence

- Code:
  `src/polisyos/core/artifacts/protocol.py`,
  `src/polisyos/core/artifacts/async_store.py`,
  `src/polisyos/core/artifacts/backends/config.py`,
  `src/polisyos/runtime/http/dependencies.py`,
  `src/polisyos/runtime/http/services/control.py`,
  `src/polisyos/scientist/engine/checkpoint.py`,
  `src/polisyos/scientist/engine/async_executor.py`,
  `src/polisyos/fabric/data_plane/streaming.py`,
  `src/polisyos/fabric/data_plane/orchestrator.py`,
  `src/polisyos/fabric/data_plane/modes.py`,
  `src/polisyos/scholar/search/jobs.py`
- Tests:
  `tests/unit/core/artifacts/test_async_store.py`,
  `tests/unit/core/artifacts/backends/test_config.py`,
  `tests/unit/runtime/http/test_control_service_di.py`,
  `tests/performance/test_runtime_hot_paths.py`,
  `tests/performance/test_scientist_runtime_paths.py`
- Long-soak:
  `docs/archive/reports/core-runtime-long-soak.md`,
  `docs/archive/reports/core-runtime-long-soak.json`,
  `.github/workflows/core-runtime-long-soak.yml`

## Remaining Follow-Ups

The remaining work is non-blocking for closeout:

- async-native cloud backends can be added selectively where benchmarks justify
  them;
- the adapter remains the explicit compatibility bridge for non-filesystem
  stores;
- threshold tuning for long-soak evidence can evolve without changing the
  public sync/async storage contracts.
