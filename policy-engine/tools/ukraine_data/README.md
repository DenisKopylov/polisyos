# tools/ukraine_data

Ukraine public-data ingestion and corpus-preparation helpers.

Use the unified entry point:

```bash
polisyos-tools ukraine_data --help
polisyos-tools ukraine_data pre-shard-lex-corpus --help
```

Operational rules:

- Preserve source null/missing semantics in generated manifests and contract
  payloads.
- Stream large inputs and use atomic publication for summary files.
- New harvesters must make timeout, response-size, and retry policies explicit.
