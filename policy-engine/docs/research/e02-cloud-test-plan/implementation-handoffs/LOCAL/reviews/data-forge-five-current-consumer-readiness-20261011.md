# Data Forge five-path current consumer readiness — 2026-10-11

## Scope and disposition

This is a read-only current-source audit and a proposed focused validation receipt. No product imports, tests, lint commands, or production-data reads were run for this audit. The proposed checks remain unrun; this note does not claim runtime passage, capability closure, or production currentness.

The source slice is exactly five working-tree-modified Python files at the candidate checkout below. Their current worktree bytes equal the independent review's candidate bindings. The changes are local to provider/facade binding and equivalent expression layout, a type-only import move, catalog facade imports, and preserving an existing Ukraine stream error as the cause of its existing refusal. The five paths have 285 insertions and 146 deletions against the selected base, predominantly explicit import aliases and reflowed long prompt/regex literals. `git diff --check` on these five paths returned no diagnostics. No test companion in the proposed set is modified in the current worktree.

P40 classification: **SAME_CLASS_DEEPER**. The prior boundary review already treated facade/private-name compatibility and runtime reflection as the relevant class. This pass extends the review to all five current source paths and the consuming paths listed below; it found no new escape. The existing bounded caveat remains: `Callable` and `Iterator` are moved under `TYPE_CHECKING`, so external runtime annotation/reflection consumers could observe those names missing. No in-repository caller of those names was identified in the cited review. Do not convert this to a general production-currentness or complete-API claim.

## Source identity

Candidate checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, branch `codex/e02-unified-local-20261009`.

Selected base commit: `8c42e13b76e13c0d1f81ab3b2b3e974c9e2cdf71`; tree `e1e4833c523f65dc07a8a9f751e8b08ae34dd460`.

Current source HEAD: `785944776c39722923c3a34d4ab7a3594dc03287`; tree `cb0c7a5bbed0fbfe5910bfbe9d0cb21457e664db`.

The base blob equals HEAD preimage for each source path. The candidate column is the current worktree SHA-256:

| Source path | Base / HEAD-preimage SHA-256 | Candidate worktree SHA-256 |
|---|---|---|
| `policy-engine/src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py` | `8be7c78c9d084f6c16d69270f34e1fda759d2817a359df838ebd4981086f5dd4` | `292b45bf9c658b90f8e2132ed7e96117ab7cf91184a2ebc93c1b9b59ea0e76ec` |
| `policy-engine/src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py` | `b040590c41d51706181d82323ea96845193e2f680fca7b28b8d42426c7d2c142` | `7c371c9407e2fab6035e49f77ecd1ff1b3bb7304c41466cd67d45c1e3a77a222` |
| `policy-engine/src/polisyos/data_forge/domains/academic/batch/resolve_extract.py` | `abcc2891946682c684d84a52b8616d93886e2a35519dd9fbafec8c171b550026` | `ca9e1c1572c83b6d53027446d4e2c18a8177f8c0c4dbd38107d4ea33436280b4` |
| `policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | `ccc219c5c5ca2f83d75470bfa9dd0761871957edd54bb6b64ab20c3c4f159a16` | `55c700823a390c76f6d61cfa568dbd6a0d129a94eb72bf076ab0f56379fa6ff3` |
| `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/sources.py` | `d67a292c7e5d21a5355cbad451c3d24c08a2aa6436349dca9bf15867654108fd` | `1600e315fa1183126a83e8695ca5a1b4621163916d97642e7aafb4d8d558e9c1` |

## Current governed check inputs

Run commands from `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`. Root Ruff policy is `ruff.toml` SHA-256 `8887d0a15457d44ebb1a5b5aee8110dd5101dc9e952649cd0490b845af2d933e`; it extends generated `ruff.generated.toml` SHA-256 `3e9528c1d2c0ce1767f73e567feaeefb2e78f139b96b00f3a9b26270d31496b9`. Generator split policy is `architecture/tooling/tool_config_split.toml` SHA-256 `17d19ddf53af4e7489e1a93425cd5eff578e9c08644652f934bc4163462b41db`. `uv.lock` pins Ruff 0.14.10. `pyproject.toml` SHA-256 is `b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267`; `pytest.ini` SHA-256 is `61270205a9f573a090b3c051a4b78351e67308a49e21660dbf33e76186d799eb` (`--import-mode=importlib`, strict markers, asyncio auto). These configuration bytes were unchanged at source HEAD and worktree when read.

## Proposed focused checks

First run the behavioral consumer command below. It touches all five changed sources through their actual import routes; includes the academic private provider facade seam and publish gate; exercises the catalog facade and persisted registry/manifest outputs; runs a deterministic academic+catalog producer chain; and tests Ukraine stream resume/refusal plus verified persisted-artifact consumption and content-drift rejection.

```sh
cd /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine
PYTHONPATH=src:. .venv/bin/python -m pytest -o addopts= -q -ra \
  tests/unit/data_forge/domains/academic/batch/test__resolve_extract_providers.py \
  tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py \
  tests/unit/data_forge/domains/academic/batch/test__resolve_extract_api.py \
  tests/unit/data_forge/domains/academic/batch/test_article_extraction_golden.py::test_article_extraction_known_article_golden \
  tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py::test_core_sources_facade_does_not_broadcast_new_globals_to_leaf_group \
  tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py::test_core_sources_ingest_populates_registry_tables \
  tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py::test_core_sources_ingest_manifest_propagates_shard_counts \
  tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py::test_core_sources_api_module_keeps_facade_entrypoints \
  tests/unit/remediation/test_obs_02.py::test_failure_between_metric_frames_resumes_at_confirmed_metric_cursor \
  tests/unit/remediation/test_obs_02.py::test_partial_resume_aborts_when_unchanged_snapshot_lacks_pending_metric_cursor \
  tests/unit/remediation/test_obs_02.py::test_partial_resume_aborts_when_normalized_snapshot_changes \
  tests/unit/remediation/test_obs_02.py::test_build_d2_materializes_unique_observation_shards_and_counts \
  tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py::test_verified_stage_artifacts_recompute_and_bind_the_producer_outputs \
  tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py::test_verified_stage_artifacts_fail_closed_on_content_drift \
  tests/integration/test_phase0_quality_validation.py::test_phase0_quality_validation_deterministic_e2e
```

Then check all five changed production files and all listed test files against the same governed Ruff configuration:

```sh
.venv/bin/python -m ruff check \
  src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py \
  src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py \
  src/polisyos/data_forge/domains/academic/batch/resolve_extract.py \
  src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py \
  src/polisyos/data_forge/domains/ukraine/builders/sources.py \
  tests/unit/data_forge/domains/academic/batch/test__resolve_extract_providers.py \
  tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py \
  tests/unit/data_forge/domains/academic/batch/test__resolve_extract_api.py \
  tests/unit/data_forge/domains/academic/batch/test_article_extraction_golden.py \
  tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py \
  tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py \
  tests/unit/remediation/test_obs_02.py \
  tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py
.venv/bin/python -m ruff format --check \
  src/polisyos/data_forge/domains/academic/batch/_resolve_extract_providers.py \
  src/polisyos/data_forge/domains/academic/batch/_resolve_extract_transformers.py \
  src/polisyos/data_forge/domains/academic/batch/resolve_extract.py \
  src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py \
  src/polisyos/data_forge/domains/ukraine/builders/sources.py \
  tests/unit/data_forge/domains/academic/batch/test__resolve_extract_providers.py \
  tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py \
  tests/unit/data_forge/domains/academic/batch/test__resolve_extract_api.py \
  tests/unit/data_forge/domains/academic/batch/test_article_extraction_golden.py \
  tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py \
  tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py \
  tests/unit/remediation/test_obs_02.py \
  tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py
```

The proposed witness tests are not runtime evidence yet. `test_phase0_quality_validation_deterministic_e2e` executes the in-repo academic and catalog producer paths and reads persisted DuckDB outputs, but substitutes a deterministic LLM and connector fetches. The golden article test also uses a fake pool that ignores the prompt. Therefore these tests do not establish live-provider behavior or, by themselves, prove exact prompt-literal equivalence. The existing provider helper test proves `_empty_provider_response` is reachable through both the provider module and `resolve_extract` facade; the facade `__all__` declarations remain unchanged, but the selected tests do not exhaustively compare every dynamically exposed name or private runtime type annotation. The catalog test guards against broadcasting newly-added globals to leaf groups; Ukraine stage-reader tests cover persisted artifact verification and content drift. No suite wall-time budget is claimed; record it from the first captured run before setting a timeout.

## Companion test identities

All paths below were unchanged at HEAD and worktree when read. SHA-256 values bind the proposed test input bytes:

| Test path | SHA-256 |
|---|---|
| `policy-engine/tests/integration/test_phase0_quality_validation.py` | `83831d5821cd0a8003a7547e14987cf0eb847f0a8a0f27ce48cb40e05c6f5b2c` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test__resolve_extract_providers.py` | `ff82110f1c198edde4898ab1bd7751a2229e3e6e5457c1de3df04934639c3b7a` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_claim_adjudicator.py` | `2996a53a4b81283a01a5c93401c15f74d5bfadb1f00e60a7928cfe24cedbd6a5` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test__resolve_extract_api.py` | `d9624efb31a0007b265015528b88d48f252422fd53c637b2e5a5f8928f3622e7` |
| `policy-engine/tests/unit/data_forge/domains/academic/batch/test_article_extraction_golden.py` | `f0456d263299a7fc8cade523d1155bdc7de7fed5c9de731778b55a1305b9e45e` |
| `policy-engine/tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py` | `fb78646044a7d7a17969ffa6e801fc8b4c964dbdc88de614fbccebda53d930d1` |
| `policy-engine/tests/unit/data_forge/domains/catalog/batch/core_sources/test_api.py` | `ddf2d7ac01ad8abf0dccb943c1f8edccd40486fcf11d387e4142773c14b8c64b` |
| `policy-engine/tests/unit/remediation/test_obs_02.py` | `8a31f37b7d5f9bac140733eb17b5f20a733380ce048886402460452a2c1fa7a4` |
| `policy-engine/tests/unit/data_forge/read_api/test_ukraine_stage_artifacts.py` | `1c912200cc4d6de02e37e9cbb8e642ec433a94d5747e7b04855b83048eb36a7f` |

Prior independent static review: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/dataforge-five-final-boundary-independent-20261011.md`, SHA-256 `574e0ebc93c152d468ede05c9926056c5a0c9da710a390db0aa4c2abad149f8a`; structured companion JSON SHA-256 `f740cf4eb2b2122d5e43cc90bdee6a50991e78d28f90bc01a137ed7ce4068acc`. That review verdict was LIMIT with runtime checks unrun. This receipt updates its source identity to the current base/HEAD and records a focused validation proposal; it does not upgrade the verdict.
