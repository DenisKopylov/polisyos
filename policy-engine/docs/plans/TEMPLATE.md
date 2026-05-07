---
title: Plan title
status: active
owner: team-name
created: YYYY-MM-DD
last_verified: YYYY-MM-DD
stability: draft
---

# Plan Title

## Scope

State the bounded workstream and what is explicitly out of scope.

## Source of Truth

| Concern           | Source                                 |
| ----------------- | -------------------------------------- |
| Decisions         | ADR links                              |
| Machine contracts | `architecture/*.toml` / `schemas/**`   |
| Stable behavior   | `docs/reference/**`                    |
| Procedures        | `docs/how-to/**` or `docs/runbooks/**` |

## Phases

| Phase | Deliverable | Acceptance                        |
| ----- | ----------- | --------------------------------- |
| 0     | Contracts   | Gates can run in report-only mode |

## Acceptance Criteria

1. Every irreversible decision has an ADR.
2. Every topology/import/schema/generated-artifact rule has a machine-readable
   contract.
3. The plan has an exit path to `accepted/` or `docs/plans/archive/`.
