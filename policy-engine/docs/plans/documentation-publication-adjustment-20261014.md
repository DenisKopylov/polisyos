---
title: Curated handbook adjustment after complete input inspection
status: proposed
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: draft
---

# Curated handbook adjustment

## Decision requested

Preserve the ten source records below byte for byte in Git, and exclude their
exact paths from the MkDocs handbook. Re-admit the revised
`explanation/berl-method-identity.md` and add it to the explanation navigation.
This changes local publication configuration only. No deployment, merge,
push or E02 closure is authorized by this proposal.

## Exact retained source records

| Path under `docs/` | Documentary role |
| --- | --- |
| `reference/foundry/causal-installed-source-reconciliation.md` | Source reconciliation and bound primary evidence. |
| `reference/foundry/causal-source-quality.md` | Source-quality comparison and primary evidence. |
| `reference/frontend/atlas-evidence-artifact.md` | Historical Atlas artifact/source record. |
| `reference/frontend/atlas-frontend-disposition-register.md` | Historical Atlas disposition/source record. |
| `reference/frontend/atlas-health-metrics.md` | Atlas metric/source record. |
| `reference/frontend/atlas-honesty-comprehension-protocol.md` | Atlas research protocol/source record. |
| `reference/frontend/atlas-manual-at-maturity.md` | Atlas target manual/source record. |
| `reference/frontend/atlas-surface-readiness-reconciliation.md` | Atlas surface reconciliation/source record. |
| `reference/policy-design-causal-grounding-firewall-CGF-spec.md` | Verbatim external specification, interpreted by separate decision records. |
| `reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md` | Verbatim external specification, interpreted by separate decision records. |

All ten are included by MkDocs but are outside the 493 existing declared
`nav`/`not_in_nav` handbook pages. Their current metadata fails 17 plain-line
Owner/Source predicates newly exposed by the complete inclusion-set checker.
Adding metadata to primary or verbatim records is not the chosen repair.

The complete current source scan found no incoming links to these ten from
539 included Markdown pages, the HTML/CSS assets, or exact-path candidates in
the other included assets. This is a source-reachability result, not evidence
about external backlinks or deployed URLs. The ignored receipt is
`_build/docs-maintenance/raw/accuracy-held-page-inbound.json`; it binds the
553 included-file hashes and names parser/asset/network limits. These counts
belong to that mutable-tree inspection at documentation HEAD `8dd9336`.

BERL's revised authored explanation identifies the inspected source pin,
diagnostic conditional route, empirical TreeSHAP fallback, per-call reuse and
the absence of policy/publication authority. Two source reviews support its
readmission; its cited tests were inspected, not freshly executed.

## Consequences and validation

The existing 493 declared pages remain. BERL gains a curated navigation entry;
the ten retained records cease to be emitted by a future build. Previous
deployed URLs and external backlinks are unmeasured. The publishing owner must
resolve redirects/retirement before any later merge or deployment; the current
workflow can publish after a successful main-branch PR Fast run as well as
manual dispatch. This local approval installs no technical deployment hold.

After approval, regenerate configuration through its canonical owner, compare
the actual MkDocs inclusion set, run complete source and emitted-site link QA,
and run a strict build. Metadata, link, build and lifecycle verdicts remain
separate; no gate is weakened and no runtime capability is promoted.

## Pattern pass

P01/P05/P15: neither a raw spec nor a historical receipt proves a functional
capability. P35/P38: actual inclusion and resolved destinations replace a nav
or filename proxy. P07/P08/P36: preserve primary bytes, pins and dated findings.
P40: disposition of the source-record class replaces repeated metadata edits.
Acceptance is an owner-approved exact-path decision, preserved source bytes,
unchanged existing declared membership and fresh publication checks.
