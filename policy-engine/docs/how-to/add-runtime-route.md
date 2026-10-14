# Add Runtime Route

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/app.py`, `src/polisyos/runtime/http/routes/`, `src/polisyos/runtime/http/services/`, `schemas/runtime_api_v1.openapi.json`, and `tests/unit/runtime/http/`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Procedure and source-reference inspection only for this documentation update; the scaffold, tests, and contract check were not run.

> Add a runtime endpoint while keeping the HTTP layer thin, preserving the
> contract chain, and respecting container and service boundaries.

## Inputs

- a route name in `snake_case`;
- a decision about whether the route is part of the public OpenAPI surface or
  is route-only;
- an understanding of which service or container dependency the route should
  use.

## Output

- a new route module under `src/polisyos/runtime/http/routes/`;
- the route wired into `create_runtime_api_app(...)`;
- if the route is public, an updated OpenAPI snapshot and downstream generated
  clients.

## Commands

Dry run scaffold:

```bash
cd policy-engine
python3 -m tools.cli architecture scaffold runtime-route \
  --name policy_review \
  --output src/polisyos/runtime/http/routes/policy_review.py \
  --dry-run
```

Verification:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
uv run pytest -q \
  tests/unit/runtime/http/test_runtime_api_contract_hardening.py \
  tests/unit/runtime/http/test_architecture_boundaries.py \
  tests/unit/runtime/http/test_api_maturity.py
```

## 1. Decide whether the route is public or route-only

Public route:

- appears in `schemas/runtime_api_v1.openapi.json`;
- affects generated runtime client and dashboard types;
- must have stable request/response DTOs and examples.

Route-only surface:

- stays out of committed OpenAPI and generated clients;
- is documented manually, like the live SSE routes in
  [REST API Reference](../reference/api/index.md).

## 2. Scaffold the route skeleton

Generate the initial file, then rerun without `--dry-run` when the template
looks right:

```bash
python3 -m tools.cli architecture scaffold runtime-route \
  --name policy_review \
  --output src/polisyos/runtime/http/routes/policy_review.py
```

The template creates:

- an `APIRouter` with `/api/v1/<route_name>` prefix;
- a minimal response model;
- one thin handler function.

## 3. Keep business logic out of the route layer

Route modules should translate HTTP requests to service calls, not reimplement
runtime logic.

Use:

- request/response DTOs in route or contract modules;
- service-layer helpers from `src/polisyos/runtime/http/services/**`;
- container/dependency resolvers instead of direct `app.state` plumbing.

Do not:

- reach into legacy container state directly from routes;
- instantiate concrete CAS/store implementations in route handlers;
- hide large business logic blocks inside FastAPI handlers.

`tests/unit/runtime/http/test_architecture_boundaries.py` is the practical guardrail
for these mistakes.

## 4. Wire the route into the app

Add the router import and `include_router(...)` call in
`src/polisyos/runtime/http/app.py`.

Also decide whether the route belongs in:

- `src/polisyos/runtime/http/routes/__init__.py` for package-level route exports;
- `src/polisyos/runtime/http/openapi_contract.py` for examples, links and
  problem payload semantics.

If the route is public, update the committed contract chain:

1. export OpenAPI snapshot;
2. regenerate runtime API client;
3. regenerate dashboard API types.

That flow is documented in
[Update Runtime Dashboard API Client](update-runtime-dashboard-api-client.md).

## 5. Verify the change

Minimum route-level checks:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
uv run pytest -q tests/unit/runtime/http/test_architecture_boundaries.py
```

If the route changes visible API behavior, also add or update focused tests under
`tests/unit/runtime/http/`.

## Rollback

- if the endpoint should not be public, remove it from OpenAPI-facing flow and
  revert generated client/type artifacts;

- if the handler became too stateful, move logic down into services before
  landing the route;

- if the route was exploratory only, remove the `include_router(...)` wiring and
  keep the draft outside the public contract.

## Troubleshooting

- `check-runtime-api-contract.py` fails: you wired the route into FastAPI but did
  not update the committed OpenAPI/client chain;

- architecture-boundary tests fail: the handler is reaching directly into
  `app.state` or other forbidden internals;

- route should be stream-only or experimental: keep it route-only and document
  it manually instead of forcing it into generated clients.

## Capability and authority boundary

Router wiring, an OpenAPI operation, and generated client types establish an
HTTP surface only. Before describing a route as a complete capability, account
for its producer, typed artifact/event, orchestration bridge, consumer,
verification, audit/API/dashboard surface (or explicit `out_of_scope`), and a
negative or semantic integration test. Record missing links with the repository
capability labels instead of implying that the route is complete.

LLM-produced and simulated results remain candidates. Candidate-band work may
carry unknown scope only when its owner preserves that unknown as a typed
limitation; protected actions, custody facts, and published claims fail closed.
A successful status or response DTO does not establish a causal policy chain,
admissibility, or publication authority.
