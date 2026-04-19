# ADR-0126: Docs Lifecycle via Diataxis and Plan Buckets

## Status
Proposed

## Date
2026-04-18

## Context

The repository had active plans, historical research notes, reference material,
and runbooks mixed in the same docs directories. That makes plans become a
second source of truth after implementation and makes review difficult.

## Decision

Use a docs lifecycle:

1. Diataxis buckets hold durable docs: `tutorials/`, `how-to/`, `reference/`,
   and `explanation/`.
2. `docs/plans/active/` holds work under review or implementation.
3. `docs/plans/accepted/` holds approved plans while implementation is in
   progress.
4. `docs/archive/plans/` holds superseded or completed historical plans.
5. Irreversible decisions move into ADRs; machine-checkable behavior moves into
   `architecture/*.toml` and `schemas/**`.

## Consequences

- Plans stop competing with reference docs after implementation.
- ADR review becomes the mandatory path for irreversible architectural choices.
- Docs freshness gates can reason about front matter and plan lifecycle.

## Related Decisions

- Extends: ADR-0096 (canonical product root and workspace boundary).
- Related: ADR-0111 (workspace root SOTA contract), ADR-0115 (layered
  architecture enforcement).
