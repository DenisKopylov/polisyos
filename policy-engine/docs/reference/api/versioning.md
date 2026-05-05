# Runtime API Versioning and Deprecation Policy

Related reference: [REST API Reference](index.md), [Runtime API Migration Guide](migration-guide.md).

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/response_policies.py`, `src/polisyos/runtime/http/routes/{runs.py,artifacts.py}`, and [ADR-0100](../../adr/0100-runtime-api-versioning-and-deprecation-policy.md)
Validation: `uv run pytest -q tests/unit/runtime/http/test_api_maturity.py tests/unit/runtime/http/test_runtime_api_contract_hardening.py`

`/api/v1/*` is the current stable runtime HTTP surface.
ADR reference: [ADR-0100](../../adr/0100-runtime-api-versioning-and-deprecation-policy.md).

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
- Do not generate SDK assumptions from schema-hidden routes such as
  `/api/v1/runs/live`; use them only as operator streaming endpoints.

## Validation

The versioning contract is checked together with OpenAPI drift and generated
clients:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py
```

Relevant test and workflow anchors:

- `tests/unit/runtime/http/test_api_maturity.py`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py`
- Architecture Import Gate workflow
- `ops/ci/templates/workflows/arch.yml`
