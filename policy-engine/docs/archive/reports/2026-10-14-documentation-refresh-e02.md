---
title: Documentation refresh against the E02 source snapshot — closeout
status: completed
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: closed
---

# Documentation refresh against the E02 source snapshot

## Delivered scope

The bounded documentation refresh is delivered on
`codex/docs-refresh-e02-20261014`, branched from
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on
`codex/e02-unified-local-20261009`. The final published-content verification
freeze is `ec888ee30d58928735c2a28eb38af8cde3198983`. Later closeout companions
are repository-only records; this report does not certify later E02 changes,
deployment, code behavior or every scientific claim in the handbook.

Twenty direct lanes covered the inventory, archival decisions, architecture,
data flows, subsystem references, runtime/API, governance, frontend,
operations, developer guides, verification, research navigation, documentation
practice research and independent link/source review. Review findings were
reconciled before the final publication-content freeze. No production code,
tests, schemas, dependencies or CI workflows changed.

Those change and companion statements describe this first slice, ending at
`c35222b3dcf103338175cf300c5fe9487e6416f3`; they are not assertions about all
later commits on the branch. The separately authorized
[maintenance audit](2026-10-14-documentation-maintenance-audit.md) records the
subsequent documentation-validator and mirrored-test changes.

Reader entrypoints:

- [Handbook](../../index.md), [repository guide](../../README.md),
  [reference map](../../reference/index.md) and
  [contributor task map](../../reference/contributor-start-here.md).
- [Architecture](../../explanation/architecture.md) and
  [bounded end-to-end data flow](../../explanation/end-to-end-data-flow.md).
- Current runtime, Scientist, Data Forge and frontend source maps, plus revised
  IR/Core, Foundry, Fabric, Lex, governance, API and operating guidance linked
  from the reference map.
- [E02 documentation snapshot](../../reference/e02-documentation-snapshot.md),
  [inventory](../../reference/documentation-inventory.md),
  [verification contract](../../reference/documentation-verification.md) and
  [archive disposition](../../plans/documentation-refresh-disposition-20261014.md).

The maps separate proposed targets, ratified decisions, observed code paths,
typed authority/status/time constraints and incomplete capability chains.
Tests cited in those maps were inspected, not executed. The documentation work
did not run runtime, provider, browser, cloud or production-data procedures.

## Archive and publication decisions

Three pre-existing plans moved to `docs/plans/archive/` with byte-identical
originals and old-path compatibility pointers: Documentation SOTA, Data Forge
Phase 0 cutover readiness and G5 proving-ground conversion. Their primary
closure evidence and remaining blockers are in the disposition. G2, current
production-quality obligations, E02-driving plans and pinned research receipts
remain with their existing owners. The refresh's own execution plan has a
separate completed archive and closeout; it is not one of those three historical
byte-preserved moves.

The user approved the exact [publication boundary](../../plans/documentation-publication-scope-proposal-20261014.md)
on 2026-10-14. Nine exclusions remove research/journal/backlog collections and
six named unlisted historical pages from the MkDocs build while preserving
their repository sources. All 493 declared handbook pages remain: 371 nav
entries and 122 `not_in_nav` entries. Actual MkDocs inclusion has 538 Markdown
pages and 14 non-Markdown resources; the 45 additional unlisted pages are
explicitly included in the final link denominator.

The applied all-files census at `38958b228f88fa47f6a78a8293ddf0cb5fb5ae7b`
removes 13,748 build inputs: 1,845 Markdown and
11,903 non-Markdown files. This is a build-selection count, not a repository
deletion count. The complete census uses MkDocs `load_config` and `get_files`,
not a directory-name or navigation-only approximation. Between that census
and `ec888ee`, only existing Markdown content changed; the publication
configuration and included path membership stayed equal.

One Foundry module now renders at its canonical API reference, with the
secondary reference linking there. Complete included-set QA also exposed an
INFO-level local link to an excluded VC1 decision; the crosswalk now uses the
full-SHA source link. The verification contract records why strict-build
success and the declared accuracy set have narrower properties than complete
local reachability (P35/P38).

No merge, push, dispatch or deployment occurred. The existing Docs Pages
workflow can deploy after a successful main-push `PR Fast` run or dispatch.
The publishing owner must decide redirects, retained pages or retirement for
old URLs **before merge or dispatch**. Deployment coverage and external inbound
references remain `not_established`; this documentation change adds no
technical deployment hold.

## Fresh verification and its limits

Commands ran from `policy-engine/`. The final concurrent wave used
`UV_NO_SYNC=1` to keep the already provisioned dependency environment stable;
complete execution receipts record that override, commands, source refs,
timeouts, exit codes and wall times.

- **PASS:** docs accuracy at `ec888ee`, zero violations over 493 declared
  Markdown pages. This checker omits reference-style links, assets, external
  liveness and prose/runtime truth, as recorded in the verification contract.
- **PASS:** freshness baseline and canonical `workspace tool-configs --check`
  at `f86fa6c`; their owning configuration/source inputs are unchanged at the
  final publication-content freeze.
- **PASS:** authored Markdown style across the writing/correction waves and
  final publication-content delta. The three byte-preserved historical archive
  originals were excluded from reformatting. Closeout companions receive a
  separate style/link pass; the configured style scope excludes `docs/archive/`,
  so this report receives manual layout and independent link/receipt review.
- **PASS:** strict MkDocs build at `ec888ee`, exit 0 in 37.9 seconds, with no
  MkDocs content `WARNING` diagnostics or excluded-page link diagnostics.
  Its stderr retains unlisted-page INFO and the theme's compatibility advisory.
  The build is local and
  does not establish live hosting or application readiness.
- **PASS:** complete source-side link/anchor/asset QA over all 538 included
  Markdown pages and all 14 resource destinations: 2,309 Markdown/HTML link
  occurrences plus nine outgoing references parsed from the three HTML/CSS
  resource files, with no broken local targets and no local
  links into excluded pages. Three historical-source links use full-SHA GitHub
  targets verified as Git blobs. External URL availability was not checked.
- **PASS:** emitted-site crawl over 601 output files, including 540 HTML and
  five CSS files. All 552 input destinations exist. Of 291,973 HTML/CSS
  reference occurrences, 289,016 internal references resolve; their 82,035
  fragment checks have no broken anchors. The remaining occurrences are
  2,956 external references without a liveness check and one unchecked CSS
  same-document fragment. These classes sum to the reference denominator;
  fragment checks are a subset of the internal references.
- **PASS:** the canonical drift checker at `ab899ef43d76b86c93089ad00a3722fc77248c3a`
  accepted a clean scratch rendering
  and rejected both a corrupted field and removal of a navigation entry while
  generated markers remained. No tracked file was corrupted by the probes.
- **PASS:** branch readback at `ec888ee` over the complete repository diff:
  92 changed paths, all 87 Markdown under `docs/` or five MkDocs YAML inputs.
  Every changed branch blob matched the checkout. The complete named code
  trees contain 8,671 blobs at both refs with no diff; the four named E02 corpus
  trees contain 11,266 blobs at both refs with no diff.
- **FAIL:** path-aware docs gate at `f86fa6c`, exit 1 at its lifecycle child.
  Its sequential dispatcher stopped there; later planned checks are not
  represented by that wrapper result. The standalone passes above remain
  separate evidence, not a green whole-gate claim.

### Lifecycle failure and P41 attribution

The exact lifecycle child was replayed from an independent, non-shallow local
clone at the original `bafca83` base. Import provenance confirms the checker
and CLI resolved from that clone. Baseline and `f86fa6c` emit exactly the same
895 finding tuples: 886 `reference_scan_ambiguous` and nine
`removed_stub_reference`, with no new tuples and none on refreshed paths.

The complete product-root tracked denominator is 25,017 paths at base and
25,033 at that verification freeze; the actual byte-scan denominator is 24,695
and 24,711. The changed-path intersections are 75 at base and 91 at that
freeze. P41 therefore remains **`not_established` for the whole gate**;
reproduced findings do not satisfy the required zero-input-intersection test
for an inherited/disjoint verdict.

The scanner attempts UTF-8 decoding on compressed and binary receipt inputs,
including `.gz`, `.xz`, `.docx`, `.pt`, `.sqlite*` and `.whl`. Its measured
decode success is a proxy for appropriate textual-reference input selection.
The smallest code follow-up is the lifecycle checker and its mirrored test
module, owned logically by `@tools-owners` with `@platform-owners` backup.
That task must explicitly classify/read its input types and exercise the real
property. No validator or E02 evidence bytes were repaired in this docs lane.

## Evidence custody

Complete deciding logs and negative-probe outputs remain ignored under
`policy-engine/_build/docs-refresh/raw/`. Paths below are relative to that
directory; SHA-256 binds the complete indicated receipt. Execution JSON binds
the command and its stdout/stderr paths; the complete logs are retained beside
it. Bulky source copies are not committed.

Retention: keep this report and its source bindings while any plan, decision
or follow-up cites them; review retention when those consumers retire. Keep
the ignored deciding logs/probes locally for follow-up reproducibility rather
than replacing them with summaries alone. Redaction: this tracked report
contains source refs, aggregate check results and checksums, with no runtime
payloads or credentials; no redactions were required. Raw logs remain local
and are not promoted into the public repository by this report.

```text
final-ec888-mkdocs-strict.stderr@796fab59d63740986b8c557ca0c503400dc0a8d276452fc224802c1e828d226b
final-ec888-mkdocs-strict.execution.json@82fcc6d656a49fe5028a2e22343c0c6c01edb13e1f79f3959b5dee8d19122e86
final-ec888-accuracy.stdout@e84cbabb5efce01c372738924d6055bb71ae86881ffe9bcca2ebd87cb8319503
final-ec888-accuracy.execution.json@9a5b13496f48378bc738bd435bc289852198cc1a3b9bae1458fe8b4d61d97e53
final-f86-freshness.execution.json@8ff769b49aa039b4f2d3d33ead07db85f8fda21bf973bdefdbef3e374b3f1dce
final-f86-tool-configs.execution.json@e0b33eee7ed75a845fcb759d80de7e62b1dac5f0269f2a73b63f2db6f2f2db25
final-f86-docs-gate.stdout@884cb9d05871d9a45ebd7720fba1d05879b92aa46980131f51df10d6b91fa01e
docs-lifecycle-baseline-bafca83.stdout@934c68ac6df20a24662874341fb8e7fc089d999ea4ca6b737e61d90c301637f1
final-f86-docs-lifecycle-p41-comparison.json@197c3b464be3f5cf48dddaf9d72b73d21422835f85924d440a8e2ebbab4b2fdc
applied-publishing-census.json@a267c4fb070ef1146ff3d6108a50b108d7a89224373b6b129806dff1ec188a50
final-source-scope-ec888.json@4adc1c57fbdb780f91f46597e21f92d560d471805ab1910e8cc03d15cac61915
mkdocs-drift-probe.json@f653e583e6ecf4ba79d070b4cd0bf4c1351508b31924e8c24a187183e6039fad
actual-surface-link-audit-ec888-summary.json@ece25004b4de24e73b91fc59535d77052cb7cdb48d633cd61db4d6614b98007f
emitted-site-link-audit-ec888.json@a171b83f75b34b39672f0d5d10d37d5df598ac31fe6c1e91ed056f1dc6e7ad47
```

The source-side link receipt is `actual-surface-link-audit-ec888.json` and its
reproduction script is beside it. Archive hashes and pinned full link QA are
in `final-f86fa6c-link-delta.json`; they are not copied into this report.
Disposable baseline checkouts and the obsolete broad rendered site were
removed after retaining their deciding output. The current local built site
remains at `policy-engine/_build/site/`.

## Remaining ownership

E02 stays active and its snapshot stays candidate-qualified. G2 and other held
archive candidates need their primary owners' current reconciliation. The
Fabric package README outside `docs/` still has broader unified-path wording
than the source-qualified reference map; it remains outside this folder-only
refresh. Runtime verification, live runbook rehearsal, external-link liveness
and publication/URL decisions are unrun or unresolved, not silently passed.

The [failure/repair register](../../reference/policy-design-case-failure-patterns.md)
was revisited at closeout: P04/P05/P15 constrain authority claims; P01/P02/P03
constrain capability reality; P07/P08 preserve source/time boundaries;
P13/P27 preserve reuse; P35/P37/P38 constrain the denominators and gate claims;
P40 widens publication-link QA to actual inputs; P41 prevents false inherited
red attribution. This report closes the bounded documentation branch work,
not those separately owned obligations.
