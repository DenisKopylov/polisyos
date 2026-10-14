---
title: English documentation and reader workflow closeout
status: completed
owner: team-docs
created: 2026-10-15
last_verified: 2026-10-15
stability: closed
---

# English documentation and reader workflow closeout

This fourth pass completes the admitted first stage of English migration and
reader/author workflow improvements. English is the sole official authoring
language. The system remains incomplete end to end; this report does not close
E02, establish translation equivalence, or establish human usability.

## Scope and saved state

The slice starts at `af387828fbf27dce6dec8665286180df0dd10d1c` on the attached
`codex/docs-refresh-e02-20261014` branch. Twenty direct agents performed disjoint
edits, source inspection and independent reviews in the existing checkout.
No new project checkout, worktree, environment, dependency installation, source
export or data copy was created. Existing environments and `_build/site` were
reused. No push, merge, deployment or recurring automation was performed.

The initial implementation was committed at
`4b1204481fdeff627e360b2f66ae554899c8333a`. The documentation verification page
binds its 19 declared tool/test inputs to
`9eaa2b7f3c88bceda9eb7e6cb587da353a8e516e`. The final publication-content freeze
is `7e6fb6b1ab976db9652d7109297ffcb227b3fcf8`.
The whole-window review was executed at the earlier
`4cb073a847eb183b8943ce5a16f459ef1d9f5cce` freeze. Later guide, homepage and
lineage-heading changes received scoped review/style checks and a fresh strict
build, search and rendered-link check. The whole-window review was not rerun
over those changes or the five repository-only closeout companions.

The complete delivery set contains 182 repository-relative paths: 168 Markdown,
ten Python, three YAML and one HTML file. This is the union of the complete Git
slice diff and the five companions, with the already-present plan path counted
once; it is not a count of production changes or translated pages.

Production source changes have one explicitly approved exception: exactly
14 class docstrings in `src/polisyos/ir/analytics/calibration.py` and
`src/polisyos/ir/model_layer/types.py`, followed by their generated IR reference.
Non-docstring ASTs match the slice entry. Runtime logic, fields, enum values and
schema snapshots are unchanged. `__doc__` and derived descriptions do change.
Other Python changes are documentation-maintenance tools, their mirrored tests,
and two tool module-docstring translations.

## What readers and authors now receive

- The handbook homepage offers exactly five task routes: understand the system,
  change a component, check a change, find a contract, and investigate a failure.
  Detailed catalogs remain on their thematic pages. Its end-to-end status is
  explicit; an inspected implementation snapshot is not an E02 closure claim.
- Complex architecture, IR, Runtime, Scientist, Foundry, Fabric, Data Forge and
  frontend pages begin with purpose, observed implementation, limits and the
  next reading route. IR validation is bounded to its structural checks;
  recorded lineage still names missing orchestration bridges.
- The contributor route points to one
  [Quick author path](../../reference/documentation-verification.md#quick-author-path).
  There is one package README template with required and conditional sections.
  Regeneration guidance points to the existing generated-artifact registry
  rather than maintaining another command list.
- `validation check-docs-impact` turns immutable Git changes and supported source
  declarations into an editorial review queue. `validation check-docs-review`
  records actual gate and independent-check outcomes. Partial binding coverage,
  failures, early-stop children and unrun checks remain visible.
- The [reader vocabulary](../../reference/reader-vocabulary.md) expands acronyms
  and offers plain English task phrases linked to canonical destinations.
  Only the existing machine crosswalk owns canonical term rulings. Three entry
  pages have a measured search boost; no new competing terminology registry was
  introduced.
- The [language policy](../../reference/documentation-language.md), root/scoped
  agent instructions, contributor guidance and style guide require English for
  new and updated authored documentation. Optional localized editions remain
  informational derivatives bound to an original revision; English does not
  grant legal, decision or runtime authority.
- A [human usability method](../../how-to/evaluate-documentation-usability.md)
  supplies four tasks, separate outcome codes and a result form. Human sessions
  are **NOT RUN**. Agent desk previews are not blind or timed human studies.

## Translation and preservation

The admitted migration covers current handbook prose, source-package documents,
operations and runbooks, annotation/testing/architecture guidance, and selected
unbound research proposals. Ten English ADR reader editions retain source pins,
hashes and original statuses; their original decision records remain intact.
Existing tutorials received language edits only. All 29 tutorial fenced blocks
match the entry commit; no working examples or successful E2E output were added.

Working E02 material and other executing plans are deferred. Held primary
specifications, historical receipts, raw research, native legal quotations,
source-status values and identifiers retain their source roles. Translation
does not silently replace primary evidence or revise a ratified decision.
Post-E02 Markdown reader prose is distinguished from unchanged JSON and transfer
receipts. The generated ADR source-title values retain their original language.

The entry inventory walks all 5,665 tracked documentation-like blobs at the
slice base: 95,439,921 bytes and 1,118,540 decoded text lines. Its Cyrillic signals
are triage, not a language classifier or proof of semantic equivalence. A later
editorial pass inspected all 110 residual records in its declared selection
and closed seven current-guide gaps. The selection excluded working E02, active
agent packages/plans, original ADRs and held archive sources; it is not a claim
that every remaining repository page has been translated or semantically audited.

The protected set is checked by complete Git mode/blob comparison against the
slice base: E02 research, active agent packages, original ADRs, held primary
documents and six research JSON records. Crosswalk-bound sources and transfer
receipts have separate checks. Preservation proves those bytes stayed intact;
it does not prove that their claims are current or that translations are exact.

The protected denominator is 11,275 files: 11,010 E02 research files, 239 active
agent-package files, ten original ADRs, ten held primary documents and six JSON
records. All remain unchanged. At the publication freeze the complete matching
documentation-like scope contains 5,680 files, 95,315,988 bytes and 1,119,870
decoded text lines. Its 451 Cyrillic-prose signals include declared primary and
deferred sources; they are not a count of untranslated current guides. One DOCX
is retained as bytes and is not decoded by this UTF-8 census.

## Actual verification

| Check | Result and actual scope |
| --- | --- |
| Focused documentation tools | The original five-module wave passed 106 cases at the first implementation freeze. The subsequent gate/wrapper delta passed 53 cases, including nine new lexical-classification cases. These are overlapping waves, not 159 unique tests. |
| Python style | Ruff check and format passed all ten changed Python files through the initial and delta checks; those code inputs remain unchanged at the publication freeze. |
| Markdown style | At the publication freeze, direct lint passed 161 of 163 selected product Markdown paths; the two `tools/research/` READMEs are configured exclusions. The root `AGENTS.md` passed separately. Scoped checks also cover the final homepage and lineage edits. A skipped hook is not counted as linting its path. |
| Generated owners | Tool-config, tools-reference and IR documentation owner drift checks passed on their respective frozen inputs. This is not the full schema/runtime API check. |
| Accuracy/freshness | Both passed at `1a47d2b8`: 544 included Markdown files, zero accuracy violations, and a zero-baseline freshness result. The only later included input change is the lineage heading, without a claim or metadata change. |
| Strict MkDocs | Passed at `7e6fb6b1`; 33.889 seconds wall time. Existing included-but-unlisted pages remain informational build notices. |
| Emitted local links | Passed at `7e6fb6b1`: 607 regular output files, including 546 HTML and five CSS files; 296,518 extracted references; zero missing files, HTML fragments or parser-unresolved inputs. |
| Short search phrases | All ten expected canonical pages appear in the first five results in the actual emitted Material/Lunr worker over 9,863 indexed sections. |
| Full search questions | **LIMITED: 5/10** expected canonical pages in the first five. The original questions were retained; the separate short-phrase set was curated after observing the weaker baseline and is not a held-out test. |
| Whole-window review | **FAIL** at `4cb073a8`. Independent style, strict build and rendered links passed; source impact is partial/UNRUN. The D6 gate's failure and blocked children are not relabeled by independent results. |
| Repository-only closeout | All five companions exist and are excluded by the actual installed MkDocs loader. All 558 selected sources and four config/lock inputs retain their frozen hashes and modes. Four companion Markdown files pass style; the report is excluded by the configured archive policy. |
| Human usability, policy E2E, deployment | **NOT RUN**. Full backend verification, CI parity and live-provider/browser behavior were not measured by this slice. |

The final emitted-reference partition is 293,513 existing local targets,
2,960 external-unverified links, 44 nonlocal-scheme-unmeasured references and
one non-HTML fragment. These sum to 296,518. The receipt does not establish
external availability, JavaScript navigation or browser-equivalent URI behavior.

The actual MkDocs loader selects 558 documentation/assets inputs: 544 Markdown
and 14 assets, from 14,856 enumerated files. Four named config/lock files are
bound separately. This accounts for the selected sources, not the complete
Python interpreter, theme/plugin implementation, mkdocstrings target modules or
their transitive imports. Publication-input equality for later excluded closeout
companions is checked separately; it is not a fresh whole-tree gate execution.
The post-companion loader sees 14,858 enumerated files and the same 558 selected
inputs; its two additional files are excluded repository records.

## Failures and unmeasured boundaries

The final whole-window impact receipt reads 3,340 tracked Markdown pages,
78,674,749 bytes: 134 supported declarations, 3,144 unmapped pages and 62
unsupported declarations, with zero read failures. It emits 16 editorial review
items over 56 changed source paths. Unsupported/unmapped pages remain explicit
coverage gaps. The queue requests claim review; source equality cannot certify
the truth of a page or complete dependency coverage.

The D6 security classifier now uses lexical token starts, correcting substring
matches such as `design`. Its property remains narrower than semantic security
scope. The final `AUTH` prefix match in
`src/polisyos/foundry/methods/catalog/AUTHORING.md` is a worked example of the
declared residual, not a new repair class (P38/P40). A falsifier also shows that
`check_significance.py` matches a security prefix without establishing security
semantics. Closing this residual needs an owner-admitted surface classification
or equivalent distinguishing context; this lexical matcher has neither.
The gate retains the resulting security-doc finding and its **FAIL** verdict.

The lifecycle child returns **UNRUN / exit 2**. Its removed-stub reference scan
accounts for 25,068 tracked paths: 24,850 selected and 218 excluded. Within the
selected set, 23,906 text inputs were decoded, 941 opaque inputs were recognized
and three were ambiguous. It retains 1,159 unresolved-reference findings, ten
direct removed-stub findings and three ambiguous-input findings. Other lifecycle
input families are not measured by this receipt. Tool-config/schema/runtime/
freshness/strict-build D6 children after the stop are **BLOCKED**; the independent
checks above keep their own narrower results.

No exact command replay from the slice base with a complete empty-intersection
proof was performed. These failures are not waived or called inherited (P41).
The documentation tools do not establish policy authority, E02 closure,
translation equivalence or human comprehension (P01/P05/P15/P29/P35/P37).

## Retained evidence and storage

Complete deciding output and execution metadata remain ignored under
`_build/docs-maintenance/`. An ignored path and hash identify local evidence;
they do not make its bytes available in a fresh clone. The search harness is a
local diagnostic, not a tracked reusable test or browser usability result.
The durable query table and canonical contributor path remain in Git.

Selected local evidence bindings are:

| Receipt under `_build/docs-maintenance/` | SHA-256 |
| --- | --- |
| `raw/pass4-translation-inventory.json` | `93a047f559811780223bc50e143da8e0a9e70ec04a89b82ac9c72b2af65fa7a4` |
| `raw/pass4-residual-editorial-review.json` | `3a890e981d4b266526e04a2c31ee2fab43d8493562e3495c5af434373107b78c` |
| `raw/pass4-final-focused-tests.stdout` | `42f91387fc61022ff6b5a7d2c343068cd9b2e4e9e4c8ed88a28e63532dff8639` |
| `raw/pass4-gate-lexical-delta-tests.stdout` | `3bf5ea7c2adce2a8def4d6995c21f699dd10c4eed53d65d3beca9cf0b2731e93` |
| `docs-review/run-731118e2817a4d95b960254622b66f13/review.json` | `ced19a60baeb818373257192d29655c02b0250c761e8cee5f60f8f3e98badfb0` |
| `raw/pass4-build-keyword-freeze.stderr` | `d339d45f7db2e405e01762a5515bee817753fbd80b9ed60a2a2d5c6524680822` |
| `raw/pass4-rendered-links-keyword-freeze.stdout` | `128b4a6057a32157c17ebddb1f98abade4f693a4ecfcf0ff0cdb7ed4ae8dd1a5` |
| `raw/pass4-search-keyword-freeze-20261015.stdout.json` | `7a8bd3b99077ee2e1a9e182f0674ab08aa6536fafd02fa8ed50dd54bd503fcc5` |
| `raw/pass4-publication-input-manifest-7e6fb6b1.json` | `cd3ed62d7bef94466bf96e429887fa9795ec659a999f01f820c563353c95bc1b` |
| `raw/pass4-post-companion-publication-proof.json` | `6b37e1aaf6b3678cfbfc4c76d8afaf168fd0ec04a8ebd55b96f0f3bd1007b61a` |

The storage census includes all task-owned raw artifacts, all three review UUID
directories, parser/smoke receipts, the local search harness and owned bytecode.
Earlier figures restricted to `raw/` omitted review directories and are not the
task's storage total. Mandatory tracked plan/report/index companions are outside
the 32 MiB ignored-output target (P39). Only designated task-owned reproducible
fixture scratch was removed; deciding logs and previous passes' artifacts were
retained. Global free-space changes are not attributed to this task.

At the post-companion census, 192 owned files contain 15,058,727 logical bytes
and occupy 15,527,936 allocated file bytes (`st_blocks * 512`), below the
33,554,432-byte target. Directory metadata is excluded. Final small style and
branch-readback receipts are added after this measurement; no environment or
second site copy is included in that output total because neither was created.

## Remaining work and routing

The next code owner can use the impact queue and canonical update path when E02
changes settle. Reconcile current implementation claims against that completed
code, then commission real tutorial runs with retained inputs and results.
The working E02 corpus and executing-plan language migration stay with their
owners; primary evidence needs an explicit derivative/revision treatment.

Run the prepared human study later and use its outcomes to revise navigation
and prose. Improve full-question search from observed misses without replacing
the original question set. Expand source declarations through owner review;
do not turn unmapped pages into an automatic claim of staleness or correctness.
The declared security-classification residual and lifecycle findings require
their own scoped work, rather than being silently cleared by this report.

The [archived execution plan](../../plans/archive/2026-10-14-documentation-english-usability.md)
records this completed first stage and the deferred work. The previous
[sustainability closeout](2026-10-14-documentation-sustainability-audit.md) has
its own source window and evidence; its outcomes are not fresh checks here.
