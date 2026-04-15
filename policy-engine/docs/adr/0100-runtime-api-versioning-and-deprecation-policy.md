# ADR-0100: Runtime API Versioning and Deprecation Policy

## Status
Accepted

## Date
2026-04-12

## Context

External dashboards, operator tools, and generated clients consume the runtime
HTTP surface. Without an explicit contract, additive improvements and breaking
changes are hard to distinguish, and operators cannot tell from responses alone
when migration work is required.

WS-2D introduced version/deprecation headers and supporting documentation. This
ADR defines that behavior as the stable policy.

## Decision

1. Public runtime HTTP compatibility lines are defined by path major, for
   example `/api/v1`.
2. Every `/api/v1/*` response emits:
   - `X-API-Version`;
   - `X-API-Compatibility-Window`.
3. Deprecating a supported surface requires:
   - `Deprecation: true`;
   - `Sunset` when a removal date is known;
   - a `Link` relation pointing to migration documentation.
4. Breaking changes require a new path major. Additive changes remain within the
   current path major.
5. A documented migration guide is mandatory for:
   - path-major changes;
   - removal or renaming of supported fields/endpoints;
   - changes that require client rollout coordination.
6. Immutable artifact resources must expose cache validators (`ETag`,
   `Last-Modified`, `Cache-Control`) as part of the client contract.

## Consequences

### Positive

- Clients can reason about compatibility from headers and docs rather than from
  source archaeology.
- Deprecation becomes operationally visible instead of being only a release-note
  footnote.
- Generated clients and dashboards have a clear review surface for contract
  drift.

### Negative

- Version/deprecation metadata must now be maintained consistently across docs,
  responses, and release notes.
- Temporary compatibility shims may live longer to honor the migration window.
