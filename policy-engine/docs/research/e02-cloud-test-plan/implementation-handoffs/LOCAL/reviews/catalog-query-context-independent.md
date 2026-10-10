# Catalog query-context independent review

Review date: 2026-10-10 UTC. Review-only; no product/test source edits, Git commands, installs, or fit workloads. This review is tied to the current shared candidate by the SHA-256 values below, not to a claimed final or production freeze. It is not a production currentness attestation or G acceptance.

## Finding

The current selected Catalog path is structurally coherent for the tested contract: the producer records a basis over canonical projected dataset bytes plus encoder/profile intent; the read store recomputes the complete projection basis from current rows and re-resolves it before query-vector admission and again before loading a cached index; query output, the registered knowledge tool, measurement-root CAS payload, and semantic benchmark v2 preserve per-call status. The live encoder asset comparison happens before `encode`, and the graph serializes each query through a lock while returning a local atomic response. Empty query results distinguish absent/refused vector search from a compatible vector query filtered to zero hits.

This only establishes behavior in deterministic temporary fixtures with a controlled `_CatalogEncoder`; it does not establish production-corpus freshness, ownership of an encoder provider, executable `encode` behavior, ranking quality, or policy authority. `CatalogRunProfile` remains the Core batch-source-selection literal in `core/contracts/control.py`; query embedding model/device/generation intent is a separate Catalog knowledge contract. No query profile is inferred from a batch run profile.

## Property trace and evidence

- **Producer and selected artifact.** `data_forge/domains/catalog/batch/embedder.py::build_hnsw_index` projects the actual `id/title/description/keywords/variables` rows with `project_catalog_dataset_embedding` and passes those members plus the live encoder object to the shared generation builder. The selected generation basis records the projection rule, model/device/dimension and encoder asset identity. `resolve_embedding_generation` validates the selected artifact family and refuses a malformed present selector instead of falling back to the flat legacy pair.
- **Fresh consumer/currentness.** `DatasetCatalogStore._current_dataset_generation` rereads all current projected rows, compares exact IDs and recomputes the complete member basis with `generation_basis_matches_members`. `_query_generation_matches_encoder` re-resolves current selection, checks the generation ID did not change, then compares actual live encoder assets and full immutable generator rule. `search_by_vector(expected_generation_id=...)` reaches `_load_dataset_index`, which checks the current selection and expected generation before using the cached index. In the same-ID mutation control, the catalog title/description/keywords/variables change while selector bytes remain identical; a newly opened store refuses with `catalog_material_basis_mismatch`, and a fresh graph returns text fallback. In the encoder control, a same-dimension encoder with different weights is refused before any query `encode` call, with selector bytes unchanged.
- **Atomic query response and tool bridge.** `DatasetCatalogGraph.search_datasets_with_status` keeps response rows and status in invocation-local state; `explain=False` does not remove it. `DatasetSearchResponse.from_result_rows` maps legacy empty rows to `limitation_code=query_status_unavailable` and `state=unknown`, never to a success default. The registered `search_datasets` tool dispatches through `KnowledgeToolkit.search_datasets_with_status` and serializes the envelope as structured JSON. The real registered-tool test covers absent generation + zero hits, selected generation + encoder mismatch + zero hits, and compatible vector query + filter-to-zero hits; the last is `search_mode=vector` with selected matching context and no refusal. The overlapping-query test keeps a successful vector status and an encoder execution refusal attached to their own calls.
- **Persisted downstream consumers.** `MeasurementRootProducer` takes one status envelope and persists both the catalog result and query status into `FileSystemCAS`; its current test reads the CAS payload back and checks the absent/refusal context. `WorkspaceLoop._semantic_benchmark_run` passes the same envelope into the v2 semantic benchmark run; the workspace test checks query status and hit status together. The v1 serializer removes the new status fields and schema version to retain the old payload shape. Semantic score tests show query status does not change a materially adequate hit outcome. The control-plane transition serializes the whole exit contract to CAS (`workspace_loop_transition.py`), but this review's selected run did not execute that HTTP transition test; the directly tested CAS write/readback is the measurement-root artifact.
- **Surface and contract.** `read_api/catalog.py` lazy exports the response/context/profile and currentness helpers. The Catalog knowledge README and the C12 release fragment explicitly preserve the old list-returning Python signatures and explain that they cannot retain status for an empty result. The registered tool and typed workspace consumers are the status-bearing surfaces. `search_mode="vector"` means the vector-enabled hybrid path, not that every returned row originated in the vector index.

The DTO validates mode/refusal/limitation consistency and context shape, but a `DatasetSearchResponse` is still a caller-constructible record; its type is not an issuer attestation. Currentness claims must be sourced from the canonical graph producer. In this code, status is diagnostic and is not a policy-authority or adequacy predicate.

## P40 class and bounded residual

This is the **same projection-loss class** as the empty-result status gap, one level deeper, not a new class. The structural closure is the atomic query envelope used by the registered tool and status-bearing workspace/measurement-root consumers. The remaining compatibility edge is the direct legacy list API: `DatasetCatalogGraph.search_datasets` projects `.results`, `KnowledgeToolkit.search_datasets` keeps the list signature, and `suggest_related` uses that list path. A zero-row legacy list still cannot distinguish “no hit” from a refused query. The README/release explicitly declare this limitation; the new `from_result_rows` path marks empty legacy responses unavailable/unknown. The full AST walk below found the additional batch CLI callsite, but `_cmd_search` is currently a silent stub (it emits no output for either nonempty or empty results), so it is not evidence of a status-bearing surface. The batch benchmark and runtime/workspace paths use the atomic method.

Smallest capability to close the bounded compatibility residual: migrate an in-scope direct-list consumer to the atomic response (or add a typed status sibling for `suggest_related`); do not reinterpret an empty list. Falsifier used: with the same selected generation, the controlled encoder mismatch and a compatible query filtered to zero hits produce different structured tool envelopes, while a legacy empty adapter yields explicit `query_status_unavailable/unknown`. The residual remains only for callers that deliberately choose the legacy list API; no broader caller-by-caller patch is recommended under the P40 rule.

The remaining asset-vs-executable issue is a documented bounded limitation in the **same identity/currentness class**: `derive_encoder_identity` fingerprints loaded assets, not mutable executable behavior. The existing removal-style test replaces `encode` while retaining the same identity and proves the boundary. The canonical graph checks and then uses the same loaded object, but external mutation/provider ownership is not attested. The knowledge README and release fragment state this precisely; no introspection ladder is implied.

## Independent checks

The scoped Catalog/consumer command completed with 12 passing selected tests and two Python 3.14 `torch.jit.script` deprecation warnings (the quiet pytest config emitted twelve dots and no failure summary):

```text
.venv/bin/python -m pytest -q \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_vector_index_rejects_same_id_with_changed_projected_content \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_graph_rejects_query_encoder_assets_mismatched_with_selected_generation \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_toolkit_reports_selected_generation_refusal_without_explanation \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_registered_search_tool_keeps_refusal_for_empty_query_results \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_legacy_empty_search_remains_limited_with_unknown_generation_context \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_overlapping_queries_keep_their_own_encoder_status \
  tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_graph_names_model_device_and_dimension_generation_refusals \
  tests/unit/runtime/quality/test_semantic_binding.py::test_semantic_benchmark_retains_empty_query_refusal_in_versioned_run \
  tests/unit/runtime/quality/test_semantic_binding.py::test_query_status_does_not_change_adequate_semantic_benchmark_outcome \
  tests/unit/runtime/quality/test_workspace_loop.py::test_slice0_semantic_benchmark_feeds_incompleteness_record \
  tests/unit/runtime/quality/test_workspace_loop.py::test_measurement_root_producer_resolves_catalog_and_persists_cas \
  tests/unit/scientist/agent/tools/test_knowledge_tools_adapter.py::TestBuildKnowledgeToolRegistry::test_search_tool_uses_atomic_status_bridge_when_available
```

Separate existing controls also passed: `tests/unit/data_forge/kernel/io/test_generation_basis.py::test_generation_basis_comparison_rejects_a_forged_digest` (malformed basis digest), `tests/unit/data_forge/domains/catalog/knowledge/test_store.py::test_graph_exposes_legacy_flat_generation_text_fallback` (legacy refusal), and `tests/unit/data_forge/kernel/test_encoder_identity.py::test_encoder_identity_does_not_bind_replaced_encode_behavior` (executable-behavior residual).

For the production source callsite denominator, an AST walk parsed all **2,748 `.py` files under `src/polisyos`** and enumerated attribute calls to `search_datasets`, `search_datasets_with_status`, or `suggest_related`. It found these source callsites: `batch/benchmark.py:987` uses the atomic method; `batch/cli.py:151` uses the legacy list in the silent stub; `knowledge/search.py:745` exposes the atomic method and `:946` has `suggest_related` call the list wrapper; `runtime/quality/data_forge_binding.py:236` is the legacy fallback; `scientist/agent/knowledge_tools.py:100` is the legacy wrapper and `:125` the status bridge. No AST parse failures were reported. The command was an explicit AST traversal, not a partial `rg` result:

```text
.venv/bin/python - <<'PY'
import ast
from pathlib import Path
root = Path('src/polisyos')
files = sorted(root.rglob('*.py'))
print(f'python_file_denominator={len(files)}')
for path in files:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'search_datasets', 'search_datasets_with_status', 'suggest_related'}:
            print(f'{path}:{node.lineno}:{node.func.attr}')
PY
```

## Current snapshot identity

SHA-256 values bind the reviewed 11-path slice (source, its two principal consumer tests, and required release/readme companions):

```text
90bd4901c233e37c3136f8c094eacebfb0116378d43518719c542d4ff2f3a09e  src/polisyos/data_forge/domains/catalog/knowledge/types.py
b401bad5753db7aad3bb11382fc230091eca489f47fabdb56990399acd37bcc4  src/polisyos/data_forge/domains/catalog/knowledge/search.py
241945f6132ffaa41822d28bf994714009582387c321619354718297be87b255  src/polisyos/data_forge/read_api/catalog.py
50ea2433702d58e269bfb697e6d4b44d4c36fd5c7eb309c1a56a7a26d7cb275c  src/polisyos/scientist/agent/knowledge_tools.py
2449fc922ac4875ccb3b596d4bc09ebbc1c8396b9023fdca8051c7f24ce302cc  src/polisyos/runtime/quality/data_forge_binding.py
ab82ade126f6ca49ed9183da7f3b35258e0ec37acae9b6b6aa212917d9e511c1  src/polisyos/runtime/quality/semantic_binding.py
68228238d47f05d5b138defbe1fc13c2758d09c1896b51b3bf315484dcbe4614  src/polisyos/runtime/quality/workspace/loop.py
e4f7766b30de2047d329539b6c7227e46f569f142e1d60cd9c83c08c541d8ecd  tests/unit/data_forge/domains/catalog/knowledge/test_store.py
3a09826ee2c0c19b7bf1922983c22c0f25752afa6b9d62c840629467f6cf67ab  tests/unit/runtime/quality/test_workspace_loop.py
82801358fd40f6cab9e20ea43d1148f0d5d8a9b764b1f974bdc5b29a2546e6f0  src/polisyos/data_forge/domains/catalog/knowledge/README.md
69046b61f5ebb894e59086fee254ddc8175d97ff82f739b9998f898aa1b387ea  release-fragments/unreleased/2026-10-09-e02-c12-catalog-search-status.toml
```

Additional load-bearing dependency hashes (reviewed implementation/helper/bridge files and the separate malformed-basis/executable-residual tests):

```text
d683ec0033f08b99ad7173e73b472c3b39c241e682ef98e731800e28d6e4a207  src/polisyos/data_forge/domains/catalog/batch/embedder.py
a28c9fbdf2b70c6fd1818adff9ca0df29fe4bef6a550db58d89c686e4e99446d  src/polisyos/data_forge/kernel/embeddings.py
5036e343aa67a6b2989bb003c3513f36d0b20e6ce59f86f91144c2daca79f343  src/polisyos/data_forge/kernel/io/generation_basis.py
5a3b7f62744c1fc5c3d6ca214cc67a99cd50f827dc9013f51532d3d664e4c8f2  src/polisyos/data_forge/domains/catalog/knowledge/store.py
48d941c3bfb3b9ecabb8b34d5ce50749217644f3fe64eefa6ca1dc6ee5abfddf  src/polisyos/scientist/agent/tools/knowledge_tools_adapter.py
b1fef07372cb522b593fc2a68ef57a4790fc2ebbd7f401817e9691e643e4afb8  src/polisyos/runtime/http/services/control/workspace_loop_transition.py
b775160bf1717c119512e80036a54c35c6e8fdaa1c75790218edb21801404805  tests/unit/runtime/quality/test_semantic_binding.py
c38298482af4e68d797ad3800bd53825b23b02f3015edfc8b929f2b2a7a173bc  tests/unit/scientist/agent/tools/test_knowledge_tools_adapter.py
99d608cdba909f5ef47bfe679838fb76d79fd6fb864a1c48ca5c6ec0a7e0a12d  tests/unit/data_forge/kernel/io/test_generation_basis.py
d520a112768b12e40692b5f155ddb67b1ea4db600e64c527dd935270f0fbee44  tests/unit/data_forge/kernel/test_encoder_identity.py
```

Dependency test files were also exercised: `tests/unit/runtime/quality/test_semantic_binding.py` and `tests/unit/scientist/agent/tools/test_knowledge_tools_adapter.py`. No Git state or production data was consulted for this review.
