# Catalog search_datasets envelope consumer rollout

This runbook covers the registered tool JSON boundary only. It does not assert that
any production deployment or consumer has been upgraded.

## Preflight

1. Inventory every registered-tool consumer and strict decoder that expects a
   top-level array from search_datasets.
2. Update consumers to accept a DatasetSearchResponse object and iterate
   response.results. Keep direct Python list callers on their existing method.
3. Verify consumers preserve query status for populated and empty results:
   search_mode, vector_refusal_code, limitation_code, and
   query_generation_context.state.
4. Exercise at least a selected vector result, a text-fallback/refusal result, and an
   empty result with unavailable or unknown context. Ensure status remains visible
   when results is empty.

## Cutover and rollback

The current registered-tool path emits the object envelope and no old-array response
mode is declared. If any strict client still expects an array, hold the cutover until
that client is updated or a separately reviewed compatibility route exists. Coordinate
reader and producer changes when they cannot be staged independently. On rollback,
use a reader and tool producer with matching response shapes; do not infer that the
current producer has switched back to arrays.

Query status is descriptive. It is not evidence of encoder execution, trusted provider
ownership, ranking adequacy, data currentness, or policy authority. Retain the selected
source artifacts and manifests under their normal owner controls; this runbook does not
authorize rewriting production manifests or hashes.
