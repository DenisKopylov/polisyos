# Registered Catalog search response migration

The registered search_datasets tool has a breaking JSON result shape change. Its old
result was a top-level array of dataset rows. It now returns one object envelope:

    {
      "results": [],
      "search_mode": null,
      "vector_refusal_code": null,
      "limitation_code": null,
      "query_generation_context": {"state": "unknown"}
    }

The object is DatasetSearchResponse. The registered adapter selects the status-aware
query method so empty results can retain query-local refusal or limitation information.
Direct Python calls to DatasetCatalogGraph.search_datasets and
KnowledgeToolkit.search_datasets keep their legacy list return; this JSON migration
applies to the registered tool response.

Update registered-tool decoders from array indexing/iteration to reading the
results array. Handle search_mode, vector_refusal_code, limitation_code, and
query_generation_context.state as query status, including selected, absent, refused,
and unknown. Do not collapse a refusal or limitation into an unqualified empty search
result. The metadata describes retrieval and selected/live profile compatibility; it
does not establish executable encoder behavior, ranking quality, data custody, or
policy authority.

No old-array output mode is declared for the current registered tool. Upgrade strict
registered-tool consumers before they use the new response. See the consumer rollout
runbook at ../runbooks/catalog-search-datasets-envelope-rollout.md.
