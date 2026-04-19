# Plans Lifecycle

This directory contains active and accepted implementation plans. Plans are not
the final source of truth for irreversible architecture decisions; every
accepted plan must leave behind ADRs, reference docs, runbooks, and
machine-checkable contracts.

## Buckets

| Path | Meaning | Exit rule |
|------|---------|-----------|
| `active/` | Under review or currently being implemented | Move to `accepted/` when approved |
| `accepted/` | Approved and implementation is in progress | Move to `docs/archive/plans/` when complete |
| `docs/archive/plans/` | Historical plans and superseded drafts | Keep only curated history |

## Required Front Matter

Every plan should declare:

```yaml
---
title: Plan title
status: active
owner: team-name
created: YYYY-MM-DD
last_verified: YYYY-MM-DD
stability: draft
---
```

## Rules

1. Active plans must link to required ADRs.
2. Accepted plans must link to machine-readable contracts when the plan changes
   repository topology, imports, schemas, generated artifacts, release policy,
   secrets, observability, or public API.
3. Plans must not become permanent second sources of truth. Stable behavior
   belongs in `docs/reference/`, procedures in `docs/how-to/` or
   `docs/runbooks/`, and decisions in `docs/adr/`.
4. Machine-checkable contracts belong in `architecture/*.toml` and
   `schemas/**`; a plan may link them but must not duplicate their contents.
