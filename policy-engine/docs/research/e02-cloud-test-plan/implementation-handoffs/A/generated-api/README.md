# Generated API contract handoff

This receipt preserves six owner waves, with the original two unchanged. Wave 1 at `8a2cecc` found 2/5 stale generated files; commit `905820c` refreshed the OpenAPI snapshot and dashboard types, and wave 2 at `905820c` matched 5/5. Wave 3 at `65ea907`, after source commit `9794b716a7` and its public-surface inventory refresh, found one schema-only drift (nine hash-line replacements; the other four files matched). Commit `00fa6d83` copied the exact fresh owner schema, and wave 4 at `00fa6d83` matched all five registered outputs.

Wave 5 at `766f8b4` found one schema drift after the consumer fixes. Its four owner commands passed and the 220-file source inventory stayed immutable; the wrapper aggregate remains UNRUN because authorized parallel document/test writes changed porcelain status. Commit `b3de1ec` copied the exact owner schema, and wave 6 at that commit matched all five outputs with stable source and porcelain state.

The final candidate is `b3de1ec3158e5c257edb548e7ef43ac82078531f` (tree `d6092e27161185a882ca7179187dfd6e3b0cc83a`). The 220-file source inventory is represented by its count and SHA only; the complete file listing remains in each ignored raw receipt, cited by path and SHA. No raw environment snapshot is copied into the tracked handoff.

Each of the six waves records the complete five-path denominator derived from `architecture/generated_artifacts.toml`. The handoff includes all 60 per-command stdout/stderr copies byte-for-byte (five command groups per wave), full per-wave comparisons, and manifest/source inventory hashes. The raw receipts and generated temporary outputs remain under ignored `_build` for manual Trash cleanup.

The negative validator probe passes by removing the actual `examples` field from `POST /api/v1/analysis/attractors` response `200 application/json` and observing the expected missing 2xx response example violation. This validates that hardening rule only. It does not execute endpoints, prove authorization, exercise client runtime behavior, or establish production serving. B04 and B26 remain limited; this receipt adds generated-surface freshness evidence only.

`ConditionalSimulation` response types and their route predate these generated companion commits. No new DTO, route, runtime bridge, or semantic consumer is claimed.
