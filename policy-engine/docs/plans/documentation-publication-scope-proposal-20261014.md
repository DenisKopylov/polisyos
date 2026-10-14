---
title: Approved handbook publication boundary
status: accepted
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: draft
---

# Approved handbook publication boundary

## Decision and approval

Use a narrower MkDocs publication scope while retaining every source file
and the existing documentation taxonomy. The explicit navigation and
`not_in_nav` manifest contains 493 unique Markdown pages at documentation
commit `ab899ef43d76b86c93089ad00a3722fc77248c3a`. MkDocs additionally collects
unlisted research, journals and historical pages. This proposal separates that
repository material from the handbook build; it does not close or archive E02.

The user approved this exact scope on 2026-10-14 with the response
“Согласовать границу handbook (рекомендую)”. The nine exclusions below are
therefore authorized. Approval covers the source-build boundary; no site
deployment or live URL inventory has been performed.

## Exact configuration delta

Add the following patterns to
`architecture/tooling/mkdocs/exclude_docs.yml`, then regenerate only the MkDocs
configuration with the existing canonical renderer:

```yaml
  research/**
  superpowers/**
  backlog/**
  brand/ATLAS_SOURCE_OF_TRUTH.md
  explanation/berl-method-identity.md
  reference/frontend/atlas-live-application-audit.md
  reference/frontend/atlas-phase-a-synthesis.md
  reference/frontend/atlas-v15-adjudication.md
  system-design-decisions/README.md
```

The current handbook retains its 493 declared pages, including the current
architecture, subsystem maps, ratified identity and custody documents. The
repository's research map, plans, historical frontend audit and decision index
remain available through repository paths and pinned source links. Research
and journal content, E02 receipts and their bindings remain byte-identical.
No directories move; warning severity, taxonomy and runtime code remain
unchanged.

The pre-application census uses MkDocs `load_config` and `get_files`, rather
than treating navigation as the complete build input. At `ab899ef` with the
recorded documentation-only working-tree delta, it collected 2,803 Markdown
paths, of which 2,383 were included. The projected exclusions remove 1,845
included Markdown paths: 1,537 under `research/`, 296 under `superpowers/`,
six under `backlog/`, and the six exact files below. The rules have no overlaps.
The projected included set has 538 Markdown paths: all 493 declared pages and
45 additional unlisted pages. This change is not a strict 493-page allowlist.
The complete census and reproduction script are local receipts:
`_build/docs-refresh/raw/publishing-scope-census.json` (SHA-256
`a61a77b7ea4e883090bfeb7b56a4a6585cdda705d9bd9ebdc8b010e78e95025e`)
and `publishing-scope-census.py` beside it. The path denominator is the actual
MkDocs docs-tree collection; the file-type denominator above is `.md` only.

## Evidence and publication risk

The strict build at `ab899ef` failed after 93.01 seconds with 698 warning lines.
A complete warning census identifies 685 Markdown link warnings and 13
autorefs warnings. None of the Markdown-warning source paths belongs to the
493-page declared set. The six exact file exclusions above cover the warning
paths outside the three proposed repository collections. Eleven autorefs
warnings arise in research pages; the other two arise from duplicate rendering
of one Foundry API module, corrected separately by linking its secondary
reference page to the canonical rendering.

Sources: the complete local build logs and census at
`_build/docs-refresh/raw/mkdocs-strict.{stdout,stderr,execution.json}` and
`_build/docs-refresh/raw/strict-build-warning-census.json`. These ignored
receipts are local evidence, not published pages. The recorded census SHA-256
is `946c6e77e1619afc47af255f759351d1f7f1bbcc45b8bdfee9988de594fd3ae6`.

Removing a file from the build can remove its website URL on a later
deployment. Keeping its Git source does not preserve bookmarks, external
citations or the previous website URL. Existing deployment coverage and
external inbound references are **not established**. Approval therefore
accepts this source-build boundary only; before any deployment, the publishing
owner must decide whether formerly deployed URLs need compatible redirects,
retained landing pages or explicit retirement. No redirects are asserted to
exist here.

## Pattern pass and acceptance

- **P03:** preserve repository indexes and source links so useful research and
  historical evidence remains discoverable.
- **P13/P27:** reuse MkDocs fragments and the existing taxonomy rather than
  creating another documentation system.
- **P35/P37:** reconcile actual MkDocs inputs and destinations; a directory
  name or a navigation subset is not a complete publication denominator.
- **P38:** rerun strict build and complete local link QA; retain the accuracy
  checker's parser omissions instead of extending a green verdict.
- **P41:** preserve exact output and baseline provenance; do not call a global
  gate's failure inherited without the required empty input intersection.

See the [failure/repair register](../reference/policy-design-case-failure-patterns.md).
Acceptance requires user approval, no loss from the 493 declared pages,
resolved handbook links to excluded content, unchanged E02/source bytes,
canonical configuration drift checks and a fresh strict build. A strict-build
pass would verify rendering and local links, not code behavior or prose truth.

The product-wide docs-lifecycle failure is a separate unresolved gate: its
895 findings reproduce exactly at the pinned base, but documentation changes
overlap its input denominator, so global P41 attribution remains
`not_established`. Fixing its source/input classification requires a separately
authorized code task; this publication proposal does not waive that failure.
