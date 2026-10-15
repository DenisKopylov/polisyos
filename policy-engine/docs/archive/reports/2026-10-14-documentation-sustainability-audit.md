---
title: Documentation clarity and sustainable verification closeout
status: completed
owner: team-docs
created: 2026-10-14
last_verified: 2026-10-14
stability: closed
---

# Documentation sustainability closeout

This third pass completes the bounded documentation work below. It does not
close E02, establish functional policy E2E, waive the lifecycle gate or authorize
publication. The system remains documented as incomplete end to end.

## Scope and source

The slice starts at `47e1e59b569a5b922611f71a7f53fb6320abea4c` on
`codex/docs-refresh-e02-20261014`. Twenty direct lanes performed disjoint edits,
source inspection, reader-path walkthroughs and independent reviews in the
existing checkout. No new project checkout, worktree, environment, dependency
installation, production-code change, CI change or tutorial update was made.
The previous [maintenance audit](2026-10-14-documentation-maintenance-audit.md)
has a separate scope and verification wave.

Implementation and tests were saved at
`6fd47dc693b8f79993876bc28a55421cc0196027`; the tool-verification contract
was pinned at `85d1a5756ae5aca7b2713c2bdf8349dca8f159ee`.
The final publication-content freeze is
`5080989dec5f8e56e74e8d99d807d7d392462789`. Later closeout companions are
repository-only; the closeout receipt checks all 548 bound input bytes and
the seven companions separately for input disjointness.

## Changes that matter to readers

- Architecture, IR, Runtime, Scientist, Foundry, Fabric, Data Forge, frontend
  and Lex routes distinguish inspected implementation from ratified targets,
  source declarations, candidate artifacts and missing producer/consumer
  bridges. Local metadata selection does not establish current law; passing
  supplied quality-gate fields does not prove gate substance or authority.
- Fabric's dedicated ID-conformance check is distinguished from its aggregate
  inventory's partial mapping. Downstream lineage remains `bridge_missing`;
  manual all-node fixtures do not establish automatic source-to-query lineage.
- The predictive trace is explicitly a candidate-run-attached diagnostic over
  selected observations using a service-selected ETS method. It does not
  calibrate the policy's causal effect. Request scope, CAS/SQL ordering, missing
  dependency errors and distinct association/S10 statuses are source-qualified.
- Existing indexes now reach the migration records, Cloud Wave 11 diagnostic
  queue and research synthesis draft. The migration records retain their
  historical status and publication exclusion. The hidden quality page routes
  to the canonical published reference; primary records were not rewritten.
- The style, ownership and contributor guides describe change-triggered claim
  review, owner labels versus human routing, and proportionate evidence. The
  inventory includes an ordinary-clone census recipe, exercised against its
  original pin. Reader walkthroughs were desk-based, not human usability tests.
- Evidence guidance distinguishes ignored local logs from available workflow
  artifacts and describes exact reproduction inputs. Pages publishing remains
  governed by its existing workflow; no deployment hold or uploaded artifact
  was invented. External environment protections and URL availability were not
  queried.

## Repeatable instruments

`check_docs_source_bindings` compares explicit source declarations at immutable
Git commits. It reads each selected Markdown page once for both metadata and
hash, expands complete component-glob sets at both refs, and compares stored
bytes and modes. Explicit `repo:` and `product:` namespaces avoid shadow-path
ambiguity. Missing inputs, LFS/gitlinks and unsupported declarations remain
UNRUN; lazy fetch and replacement refs are disabled. Equality proves only the
declared comparison, not prose truth, dependency completeness or test execution.

`check_docs_rendered_links` checks the complete specified site output and its
supported HTML/CSS URI forms. It verifies local files and HTML IDs, uses an
unambiguous path-set digest, and reports parser/read/origin uncertainty as UNRUN.
It admits bounded ASCII/canonical-IP origins; browser-equivalent WHATWG/UTS46
normalization, non-HTML fragments, JavaScript navigation, external liveness and
atomic snapshot semantics are named limits. Actual missing targets are retained
even when another input is unresolved.

Both are available through the existing CLI registry's automatic discovery and
as direct modules. They are not dispatched by the docs gate or CI. The existing
gate now plans its existing accuracy and strict-build checks for the complete
MkDocs publication-config family. Early failure still leaves later children
unrun; a planned command is not an execution receipt.

The canonical crosswalk generator repaired one stale source digest without
changing terms, IDs, rulings or authority. The refreshed artifact SHA-256 is
`b20d06785141249cf842d2c3eb066997172b8bcba2bc4402d98d725476b2246c`.
All 14 bound source entries match its UTF-8/newline-normalized hashing method.
The writer and independent check passed; an alternate corrupted term was
rejected. This is crosswalk consistency, not lifecycle authority or E02 closure.

## Actual checks

| Check | Outcome and complete declared scope |
| --- | --- |
| Three changed tool/test modules | 66 tests passed at 85d1; all six Python input files remain identical at the final content freeze. |
| Python style | Ruff check and format passed for all six changed Python files. AST equivalence was checked for the four formatter-modified files; initial format failures remain in local evidence. |
| Authored Markdown | Canonical `workspace docs-style` passed the 38 changed authored paths at the final content freeze. The generated tools reference receives its owner's drift check. |
| Accuracy and freshness | Passed: zero violations over the actual 530 included Markdown files; zero-baseline wrapper passed separately. |
| Generated owners | Canonical tools-reference and tool-config drift checks passed. The crosswalk negative probe returned exit 1 as required. |
| Strict MkDocs | Passed at 5080989; 36.92 seconds wall time. The preceding build and initial failing generated-reference gate are retained separately. |
| Emitted-site CLI | Passed over all 593 regular outputs: 532 HTML, five CSS and 56 other files; 289,319 extracted references; zero missing local files, HTML fragments or parser-unresolved inputs. |
| Declared source bindings | All seven explicitly selected pages match their declared source pins against this docs branch's frozen HEAD; this does not measure a different branch. |
| E02 source comparison | Exit 1, as required for drift: five of six selected map declarations differ from commit 4dffb9f. The handbook's E02 snapshot records the exact overlapping counts and review needs. |
| Repository-only closeout | Five in-scope Markdown companions pass docs-style; the two report/archive-index paths are excluded by its existing policy. All seven companions have zero intersection with the 548 bound build inputs, whose bytes remain unchanged. |
| Changed-path docs gate at content freeze | Failed at 5080989, exit 1, over 46 discovered slice paths. Tools reference passes; lifecycle child returns UNRUN/exit 2 and stops subsequent children. Independent checks above are not relabeled as gate children. |

The gate was not repeated for the later seven repository-only companions;
its frozen result is not a fresh gate over the final 51-path delivery.
The lifecycle reference receipt covers 25,047 tracked product paths, 24,829
selected and 218 excluded; 23,885 were scanned as text, 941 recognized opaque
inputs were byte-read, and three were ambiguous. It retains 1,159 unresolved
reference inputs and ten direct-reference findings. Other lifecycle input
families and historical-role verification remain unmeasured. This result is
not waived or called inherited: this slice changes paths inside its denominator.

The emitted reference partition is 286,380 existing local targets, 2,894
external-unverified, 44 nonlocal-scheme-unmeasured and one non-HTML fragment.
Those categories sum to 289,319; they do not establish browser behavior or
external availability. The build binding reads all 544 included sources plus
four named config/lock files and verifies all 548 against committed bytes.
Its row-set digest is
`59622be9e85571da82bc90f32f7f7cf7e7c574bf65d443e73b5d3322e16253bf`.
Mkdocstrings' 170 directives, transitive Python imports, theme/plugin inputs and
full environment closure are not promoted to a complete dependency receipt.

Full backend verification, CI parity, architecture environment reconstruction,
live providers, browser usability, policy E2E and deployment were not run. The
earlier architecture/public-surface failure attribution remains confined to
the second report; it is not a fresh result or P41 attribution for this slice.

## Retained evidence and disk use

Complete command output and execution records are ignored under
`_build/docs-maintenance/raw/`. The following bindings retain the deciding
evidence; an ignored path plus hash does not make its bytes remotely available:

- `pass3-frozen-tests.stdout` @
  `f7fd07e6833e81ced4590bc0069a28c52b6e3451c98d59aaa8a240573f620067`.
- `pass3-final-strict-build.stderr` @
  `c1c33b3b0b27c73c75acaf953c8b49f9120dd8616afd7d6e692bf6f347fd4186`.
- `pass3-final-docs-gate.stdout` @
  `68b0ab5ece3401c9841296c72a3f08f5ead13d177596d1d36fd45016d789ff3c`.
- `pass3-final-rendered.json` @
  `babf50e828b46013aca2fa4e8c6fb7ac721960c4c9f8324055e8dd49f611129a`.
- `pass3-final-build-inputs.json` @
  `acbd000de3fe1f2a7a3fae1009278b48f9b0b129730a87f479ceafff3479f50f`.
- `pass3-closeout-companions-receipt.json` @
  `ea069db6222241db5843db1a5907e0964a2d720beb77321fb4286c6880f7dc48`.
- `pass3-frozen-source-e02.stdout` @
  `58b247aa162fe4dcb30194ded16cfe8cffc96f27dd8076def2e24cceb743e9e6`.

Other passing/probe commands retain their `pass3-*.execution.json` and complete
stdout/stderr. Eight task-owned pytest fixture directories were removed after
their deciding logs were retained, releasing 23,379,968 allocated file bytes;
the exact cleanup receipt names each directory. Existing environments were
reused and the existing site directory rebuilt in place. No large source or
data copies were created. At the precommit closeout census, 106 retained
`pass3*` files contained
10,394,193 logical bytes and occupied 10,616,832 allocated file bytes. Final
small preservation/style/readback receipts are added to this local scope;
filesystem free-space changes are not attributed to this task.

The complete third-slice delivered set is 51 paths: 44 Markdown, six Python
and one JSON. The only changed `src/` path is a documentation README. E02
research, active agent packages and tutorials retain all 11,254 paths and
275,691,139 source bytes from the slice entry, including 1,378 Markdown files;
all ten held primary pages remain identical by mode and blob OID. Publication
navigation/configuration, production implementation, schemas, locks and CI
are unchanged. The final delivery re-reads committed branch blobs and checks
that the checkout matches them; a staging-area view alone is insufficient.

## Remaining owner work

Re-review the five flagged maps against the canonical integration freeze before
moving their pins. The zero-drift Scientist declaration does not certify its
unlisted dependencies or current behavior. E02 acceptance and tutorials belong
to the later completed integration work. Lifecycle's opaque/excluded inputs,
fixture and historical-role semantics, and other input families need their own
bounded instrumentation work; no blanket exclusion was added. Current external
URL retirement, accessibility and live deployment facts still require their
owners. Human reader/search/mobile usability remains unmeasured.

P01/P02/P05/P15 preserve capability and authority truthfulness. P07/P08 retain
source and time roles. P13/P27 avoid a new taxonomy, registry or dependency.
P29/P31/P32/P35/P37/P38 bind actual inputs and distinguish measured properties
from cheap stand-ins. P40 widened path/origin handling and declared the genuine
browser/snapshot limits; P41 keeps failure attribution separate from closure.
