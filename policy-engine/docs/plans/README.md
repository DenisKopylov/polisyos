# Plans Lifecycle

This directory contains active, accepted, and archived implementation plans.
Plans are not the final source of truth for irreversible architecture
decisions; every accepted plan must leave behind ADRs, reference docs, runbooks, and
machine-checkable contracts.

## Buckets

| Path                  | Meaning                                     | Exit rule                                   |
| --------------------- | ------------------------------------------- | ------------------------------------------- |
| `active/`             | Under review or currently being implemented | Move to `accepted/` when approved           |
| `accepted/`           | Approved and implementation is in progress  | Move to `docs/plans/archive/` when complete |
| `docs/plans/archive/` | Historical plans and superseded drafts      | Keep only curated history                   |

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
5. Repository-wide topology or governance plans need a closeout report before
   they move out of `active/`; for Repository SOTA this is
   `accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md` plus the
   `workspace repository-sota-closeout` gate.
6. Historical plans do not live under `docs/archive/**`; that subtree is for
   reviewed evidence, reports, frozen specs, incidents, and postmortems.
