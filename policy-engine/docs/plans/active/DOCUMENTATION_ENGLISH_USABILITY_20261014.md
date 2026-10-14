---
title: English documentation and simpler reader and author workflows
status: active
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: evolving
---

# English documentation and simpler reader and author workflows

## Authorization and boundaries

The principal approved the seven documentation improvements and English as
the sole official documentation language on 2026-10-14. The subsequent scope
clarification prioritizes code documentation and other documents outside
currently executing plans; active plans and working E02 material are deferred.
The human usability study is deferred: prepare its method without claiming
that agents represent human participants. Conversation language is unaffected.

This slice starts at `af387828fbf27dce6dec8665286180df0dd10d1c` on the attached
`codex/docs-refresh-e02-20261014` branch in the existing checkout. No new project
worktree, checkout, environment, dependency installation or source/data export
is allowed. Production behavior, CI, schemas, locks and deployments remain
outside scope. Root serializes Git, generated references, publication config
and the one final in-place site build after review.

English authoring rules do not establish source-language legal authority or
translation equivalence. Preserve exact external quotations, code literals,
identifiers, source pins, historical statuses and evidence bytes. Existing
accepted ADRs and primary historical receipts remain records of their original
decision/run; separately labeled reader translations cannot ratify or revise
them. Do not reinterpret mathematical symbols or proper names as foreign prose.

Tutorial functionality remains deferred until E02 completion. Language-only
edits may translate existing explanations without inventing working examples,
expected results or completed E2E demonstrations. Any source-embedded production
docstring translation needs a separate reviewable scope decision.

The principal subsequently approved the prepared patch translating exactly
14 class docstrings in `src/polisyos/ir/analytics/calibration.py` and
`src/polisyos/ir/model_layer/types.py`, plus their generated IR reference.
Non-docstring AST equality was checked; `__doc__` and derived descriptions
change, while runtime logic, fields and schema snapshots remain unchanged.

## Design and acceptance

- One intent-based handbook entrypoint; detailed catalogs stay at their owners.
- Short purpose, observed capability, limitation and next-route introductions
  where they help the reader; no competing implementation-status registry.
- One common author path through existing canonical checks, with an optional
  review orchestrator retaining actual child outcomes and compressed logs.
- A source-impact queue derived from existing declarations and immutable Git
  trees, with unmapped/unsupported/read-unrun pages and bounded absence verdicts.
- One package README template and one command authority per generated family.
- A non-normative reader vocabulary and reproducible search expectations;
  search ranking remains distinct from human findability evidence.
- A prepared human usability protocol with explicit NOT RUN status.
- English authored prose across the admitted first-stage documentation set,
  with preserved literals, recorded primary-source exceptions and deferred work.

The source-impact CLI is `validation check-docs-impact`, taking explicit
`--base-ref`, `--head-ref`, `--repo-root`, `--format` and optional `--output`.
It reads the complete tracked Markdown set at the resolved head, expands
supported declared source patterns against both trees and queues actual changed
members for human review. Equality does not prove prose truth. Missing binding
coverage, unsupported grammar or unreadable inputs must stay visible as UNRUN.

The review CLI is `validation check-docs-review`. Git determines the real changed
set; explicit paired refs provide a committed window, while default worktree
mode cannot establish immutable source impact. Reuse the existing docs gate's
plan and early stop. With `--run-independent`, run applicable independent style,
impact, build and emitted-link checks without relabeling blocked gate children.
Reuse configured `_build/site`; never create a second site copy. A successful
matching strict build is a prerequisite for a fresh rendered-link receipt.
Review-required, failed, blocked and unrun outcomes remain distinct.

## Direct lanes and ownership

Twenty direct agents work in the same checkout, without delegation below them.
Each writer owns disjoint paths; shared inventories have exactly one writer.

| Lane | Owned work |
| --- | --- |
| closeout_census | Complete pinned documentation inventory and final census |
| research_e02 | Read-only source-bound/E02 and authority reconciliation |
| quality_contract | Author verification path and generated-artifact procedure |
| closeout_plan | Main, Explanation, Reference and contributor reader routes |
| english_policy | AGENTS/contributor/style rules and the language policy |
| docs_review_cli | Review orchestrator and mirrored behavioral tests |
| docs_impact | Source-impact discovery and mirrored behavioral tests |
| docs_search | Non-normative vocabulary and search expectations |
| reader_pilot | Human protocol and explicitly non-human desk preview |
| translate_explanation | Explanation prose; structured-content read-only audit |
| translate_reference_core | Core/API/runtime/frontend/operations references |
| translate_reference_science | Scientist/Foundry/Fabric/Data Forge references |
| translate_howto | How-to prose and its reader index |
| translate_runbooks | Runbooks and key-rotation prose |
| translate_decisions | Preserved ADR sources and English reader editions |
| translate_plans | Plan routing and named active-plan/E02 deferrals |
| translate_research | Unbound research proposal prose and source classification |
| translate_archive | Historical-source preservation and English reading routes |
| translate_packages | Source-package Markdown/RST documentation only |
| translate_misc | Other README/ops/schema/tool/contract authored documentation |

Root owns this plan, repository-level integration, publication fragments and
the final report. Initial source census walked 5,665 tracked documentation-like
blobs at the entry commit. Its script signals are triage, not an English-language
classifier; binary and structured data require separate actual-input accounts.
The sole canonical inventory is ignored
`_build/docs-maintenance/raw/pass4-translation-inventory.json`; its sole writer
is `closeout_census`. A scoped writer overwrote it once; its output was retained
under a distinct name and the original complete census was recomputed from the
same immutable entry tree. No tracked source was lost.

## Execution

- [ ] Establish complete scope, canonical English policy and named deferrals.
- [ ] Simplify reader/author routes and canonical templates/command guidance.
- [ ] Translate admitted prose with independent semantic and literal checks.
- [ ] Implement and test real Git impact and review orchestration behavior.
- [ ] Integrate vocabulary, language policy, human protocol and search routes.
- [ ] Reconcile primary-source translations without authority or URL retirement.
- [ ] Freeze all sources, complete independent reviews, then run one final wave.
- [ ] Run focused tool tests/Ruff, authored Markdown style, relevant owner drift,
  complete included-page accuracy and strict build plus rendered local links.
- [ ] Retain failed/UNRUN gates without waiving or assigning inherited ownership.
- [ ] Commit clean boundaries, re-read branch blobs, verify protected E02/source
  preservation and allocated storage, then record the actual first-stage result.

## Resource and pattern pass

New ignored mechanism outputs target at most 32 MiB: one source census, small
fixtures, compressed deciding logs and compact receipts. Mandatory plan/report/
index companions are outside that output budget (P39). Remove only task-owned
reproducible fixture scratch after preserving deciding logs. Do not attribute
global filesystem free-space changes to this task.

P01/P02/P05/P15 preserve incomplete capabilities and scoped authority.
P07/P08 retain source, time and translation roles. P13/P27 avoid duplicate
registries, competing command authorities and shared-inventory writers.
P29/P31/P32/P35/P37/P38 require real Git/read/build behavior and complete named
denominators; language signals, markers and byte equality cannot prove English
meaning, human usability or semantic currentness. P40 buckets repeated escapes
before widening or declaring bounded residuals. P41 prohibits inherited-failure
claims without an exact-entry replay and complete empty-intersection proof.
