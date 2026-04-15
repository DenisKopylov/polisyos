# Runtime API Versioning and Deprecation Policy

Related reference: [REST API Reference](index.md), [Runtime API Migration Guide](migration-guide.md).

`/api/v1/*` is the current stable runtime HTTP surface.

## Compatibility window

- Backward-compatible changes may land within `v1` without changing the base path.
- Breaking changes require a documented migration guide and a compatibility window of at least 12 months.
- Runtime responses emit `X-API-Version` and `X-API-Compatibility-Window` so clients can pin policy expectations without reading source code.

## Deprecation contract

- Deprecating a `v1` surface requires `Deprecation: true`.
- When a hard removal date is known, responses also emit `Sunset: <HTTP-date>`.
- Runtime responses attach a `Link` header with `rel="describedby"` that points clients to migration documentation.

## Client guidance

- Treat `ETag` and `Last-Modified` on immutable artifact resources as canonical cache validators.
- Prefer bulk endpoints such as `POST /api/v1/runs/batch` and `POST /api/v1/artifacts/batch` for dashboard and operator workflows.
- For artifact payloads, request JSON preview by default and ask for raw bytes explicitly with `Accept: application/octet-stream` or the concrete artifact media type.
