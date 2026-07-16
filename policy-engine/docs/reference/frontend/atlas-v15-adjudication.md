---
title: Atlas v15 Adjudication
status: in-progress - conformance battery complete
owner: team-design
created: 2026-07-16
last_reviewed: 2026-07-16
slice_plan: ../../plans/active/atlas-slices/DS2-atlas-v15-adjudication.md
master_plan: ../../plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
ds0_record: ../../brand/ATLAS_SOURCE_OF_TRUTH.md
ds1_report: ./atlas-live-application-audit.md
adoption_schema: ../../../architecture/atlas_surfaces/adoption-ledger.schema.json
archive: ../../../design/atlas-v15/PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip
archive_sha256: 28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969
audiences: [REVIEWER, EXPERT, MACHINE]
---

# Atlas v15 Adjudication

## Scope And Authority Boundary

This report adjudicates the sha256-frozen Atlas v15 archive against the
[living v4 baseline](./atlas-live-application-audit.md#sharedui-families-audited-12-of-12-owning-89-of-89-components)
and the [DS0 source decisions](../../brand/ATLAS_SOURCE_OF_TRUTH.md#d1---canonical-source-supersession-and-docs-lifecycle).
It is authoritative for DS2 adoption decisions and Phase-A planning input. It
may not be used as evidence that a component is integrated, browser-tested,
manually AT-tested, authority-compatible, publicly safe, package-publishable,
or production `stable`.

The archive itself makes the same essential limitation: its readiness overlay
is “ZIP/archive-level hardening only,” with product integration, runtime
browser checks, and manual assistive-technology validation deferred
(`BEST_IN_CLASS_READINESS.md:1-5`). DS2 preserves that limit even where an
archive report says `PASS` or a component manifest says `stable`.

## Archive Identity And Extraction Proof

| Measure | Result | Method |
| --- | ---: | --- |
| SHA-256 | `28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969` | `shasum -a 256` before extraction |
| ZIP entries | 1,612 | Python `zipfile.ZipFile.infolist()` |
| Directory entries | 136 | `ZipInfo.is_dir()` |
| Non-directory members | 1,476 | entries minus directory entries |
| Uncompressed bytes | 13,371,433 | sum of non-directory `file_size` |
| Compressed member bytes | 4,489,042 | sum of non-directory `compress_size` |
| Extracted files / bytes | 1,476 / 13,371,433 | scratch-only recursive filesystem count |
| Unique content blobs | 983 | SHA-256 of every extracted file |
| Duplicate-content groups / members | 432 / 925 | grouped file SHA-256 values |

Extraction used `/private/tmp/atlas-ds2-v15.DafNaR`; the path is execution
scratch, not a repository artifact. ZIP and extracted file/byte counts match,
and repository status remained clean immediately after extraction. The
archive zip is the evidence source; no extracted file will be committed.

## Conformance Battery

### Result

**Archive verification is internally useful but constitutionally
insufficient.** The 44 physical verification artifacts collapse by exact
content and generated-projection identity to 31 logical reports. DS2
classified **44 of 44 physical reports and 31 of 31 logical reports** before
assigning any token, component, or pattern verdict.

The archive's primary `scripts/verify.py` gate does not execute the product
package or a browser. It checks 33 artifacts for presence and ten report files
for pinned regular-expression markers, including a hard-coded expected
component count of 56 (`scripts/verify.py:7-25,36-52`). The full verifier does
execute 17 archive-local Python generators and linters and records exit codes
(`scripts/run_full_verify.py:9-31,42-67`), so it is stronger than presence
alone, but its outputs still prove only archive-local generator/linter
behavior. Neither path supplies PolicyOS repository integration, runtime
authority semantics, deployed performance, browser behavior, or manual AT.

The best-in-class report is even narrower: it marks 51 named documentation and
metadata paths `PASS` when present, then checks that the self-scored area list
is complete and the component-health count equals the same manifest
(`dist/verification/best-in-class-readiness-report.md:1-61`). Its `PASS`
cannot establish the truth, adoption, or effectiveness of those policies.

### Evidence-class ceiling

| Claim class | What it proves | What remains missing | Owning slice |
| --- | --- | --- | --- |
| Artifact-presence / marker report | Named archive paths and expected marker strings existed in this snapshot | semantic property, current repo compatibility, adversarial drift | DS4 / DS6 |
| Archive generator/build evidence | An archive-local script emitted internally related source/projection artifacts at the recorded revision | reproducible repo toolchain, supply-chain review, generated-diff gate, consumer integration | DS4 / DS6 |
| Manifest/schema/static lint | Parsed archive files satisfy the archived enumerated rules | complete-by-construction repo rules, authority/status compatibility, consumer behavior | DS4 / DS6 |
| Component/state coverage | The manifest and state matrix have matching named rows and archived source/docs/story paths | browser state behavior, keyboard/APG interaction, visual modes, manual AT, live consumer | DS4 / DS6 |
| Contrast calculation | The 15 recorded foreground/background pairs meet or are restricted under the recorded WCAG thresholds | all component states, images/gradients/overlays, forced-colors, browser rendering, human review | DS6 |
| Responsive/data-viz/theme audit | Enumerated contracts, modes, chart types, and generated mirrors are internally present/consistent | viewport/browser behavior, data fallback, uncertainty semantics, set-valued/incomparable value, screenshots | DS4 / DS6 / DS16 |
| Readiness/health/VPAT score | The archive authors recorded a rubric, gap list, or heuristic score | independent owner ratification, product evidence, adoption telemetry, conformance statement | DS6 |
| Run log | Named archive commands returned success at the recorded time | reproducibility in this repo, adequacy of each check, absence of untested behavior | DS4 / DS6 |

No evidence class above can assign PolicyOS maturity `stable`. Static methods
with coherent, bounded claims may be retained as `beta` evidence candidates;
all other report artifacts remain `experimental`. A report's own maturity or
health label is never inherited.

### Exhaustive report classification

Exact duplicate paths share one row below. `component-health.json` and its
Markdown projection also share one logical row because they are two formats
of the same generated health result. Every listed path remains separately
accounted for in the 44-member physical denominator.

| ID | Archive report path(s) | Actual method and maximum proof | Missing evidence / disposition | Revisit condition |
| --- | --- | --- | --- | --- |
| `evidence-best-in-class-summary` | `BEST_IN_CLASS_READINESS.md` | Author-written inventory and explicit non-runtime scope; proves the intended archive overlay and its own limitation | No independent execution; `defer`, experimental, DS4/DS6 | Revisit when an adopted item cites the summary to a resolved underlying report rather than its headline |
| `evidence-a11y-static` | `accessibility/audit-results.md` | Archive heuristic scan reports 0 blockers and 0 warnings | No browser, focus, keyboard, state, or AT evidence; `defer`, experimental, DS6 | Revisit when the scanner is bound to admitted source and cross-checked against axe/browser/manual-AT evidence |
| `evidence-contrast-audit` | `accessibility/contrast-audit.md` | Recomputable ratios for 15 named pairs: 12 pass and 3 restricted | Not whole-component/state coverage; `admit_after_refactor`, beta method, DS6 | Revisit maturity when DS6 runs admitted tokens across every rendered state/mode and retains the three restrictions |
| `evidence-vpat-readiness` | `accessibility/vpat-acr-readiness.md` | Readiness/gap planning for a future VPAT/ACR | No conformance testing or signed accessibility statement; `defer`, experimental, DS6 | Revisit after product-scope conformance evidence and accountable sign-off exist |
| `evidence-readiness-matrix` | `best-in-class/readiness-matrix.md` | Author inventory of archive coverage and named gaps | No independent scoring or repo consumer evidence; `defer`, experimental, DS6 | Revisit if DS6 binds rows to current, resolved evidence artifacts and owners |
| `evidence-readiness-scorecard` | `best-in-class/readiness-scorecard.json` | Self-reported numeric scores and targets for ten areas; explicitly says runtime evidence is absent | Scores have no measured denominator or independent verifier; `reject` as maturity evidence, experimental, DS6 | Revisit only with published scoring rules, recomputed inputs, and non-producer acceptance |
| `evidence-component-build` | `component-library/build-evidence.md` | Recorded manifest/build projection counts at the archive revision | No current repo build, dependency, or consumer proof; `defer`, experimental, DS4 | Revisit when DS4 reproduces admitted sources in the repo toolchain with a generated-diff check |
| `evidence-component-audit` | `component-library/component-library-audit.md` | Static agreement among a pinned 56-entry manifest, docs/source paths, story requirement, and archived outputs | Count is hard-coded in the verifier; no behavioral evidence; `admit_after_refactor`, experimental method, DS4/DS6 | Revisit when the gate derives the set generically from admitted exports and fails a missing-state/source/story corruption |
| `evidence-viz-build-summary` | `component-library/data-visualization/build-summary.md` | Recorded generation of component-library data-viz artifacts | No DS16 semantic compatibility or repo build; `defer`, experimental, DS4/DS16 | Revisit after admitted chart contracts generate in-repo and cover value/uncertainty requirements |
| `evidence-viz-component-audit` | `component-library/data-visualization/data-visualization-audit.md`; exact duplicate `dist/verification/data-visualization-audit.md` | Static component-library data-viz checks at one archive revision | No browser/data fallback/semantic tests; `defer`, experimental, DS4/DS6/DS16 | Revisit when DS16 negatives exercise set-valued, incomparable, provenance, and missing-data cases |
| `evidence-state-matrix-audit` | `component-library/state-matrix-audit.md` | Manifest/matrix parity for 56 components, 491 supported states, 92 rejected states, and 2 backlog states | Does not render or interact with any state and can coexist with an unsafe authority lattice; `admit_after_refactor`, experimental method, DS4/DS6 | Revisit when state identities bind to governed exports and browser/keyboard/negative evidence is derived from the matrix |
| `evidence-state-matrix-coverage` | `component-library/state-matrix/coverage.md` | Author-readable coverage projection of the canonical matrix | Same missing runtime evidence as the matrix; `defer`, experimental, DS4/DS6 | Revisit when generated from the admitted matrix and linked to per-state evidence |
| `evidence-responsive-audit` | `dashboard-responsive/audit-results.md`; exact duplicates `dashboard-responsive/responsive-audit.md`, `component-library/dashboard-responsive/dashboard-responsive-audit.md`, `dist/verification/dashboard-responsive-audit.md`, `dist/verification/responsive-audit.md` | Static contract lint for five named window classes and required files/mirrors | No viewport render, touch, zoom, print, or live data evidence; `admit_after_refactor`, experimental method, DS4/DS6/DS8 | Revisit after DS6 executes admitted shell states at the declared viewports and print mode |
| `evidence-responsive-build` | `dashboard-responsive/build-evidence.md` | Recorded manifest/TypeScript projection generation | No repo generator or consumer parity; `defer`, experimental, DS4 | Revisit when DS4 reproduces the projection and a drift check rejects a corrupted mirror |
| `evidence-responsive-screen-coverage` | `dashboard-responsive/screen-coverage.md` | Declared screen/viewport coverage matrix | It is a plan, not screenshots or assertions; `defer`, experimental, DS6/DS8 | Revisit when every declared cell resolves to a current browser artifact and owner |
| `evidence-viz-audit` | `data-visualization/audit-results.md`; exact duplicate `dist/data-visualization/audit-results.md` | Static lint for 16 chart types, 14 components, required docs/tokens, and mirrors | No DS16 basis-chip/set-valued/incomparability semantics or live fallback; `admit_after_refactor`, experimental method, DS4/DS6/DS16 | Revisit when the check imports admitted grammar and exercises DS16 semantic negatives |
| `evidence-viz-build` | `data-visualization/build-evidence.md`; exact duplicate `dist/verification/data-viz-build.md` | Recorded manifest/grammar/TS projection generation | No repo build or consumer; `defer`, experimental, DS4/DS16 | Revisit when DS4/DS16 reproduce admitted projections and verify semantic parity |
| `evidence-best-in-class-lint` | `dist/verification/best-in-class-readiness-report.md` | Presence of 51 expected docs/metadata paths plus manifest-count equality | Form-based presence is not policy truth or maturity; `reject` as a repo readiness gate, experimental, DS6 | Revisit after each claimed property is recomputed from its effective source and fails when the property—not merely its marker—is removed |
| `evidence-full-verify-current-log` | `dist/verification/full-verify-current.log` | Historical partial archive command/exit witness | Incomplete gate set and no environment binding; `defer`, experimental, DS4/DS6 | Revisit only as provenance attached to a reproducible admitted build |
| `evidence-full-verify-summary` | `dist/verification/full-verify-summary.md` | Human summary that archive gates passed and runtime evidence remains planned | Summary does not independently prove its inputs; `defer`, experimental, DS6 | Revisit when generated from resolved current gate results with environment/provenance |
| `evidence-full-verify-log` | `dist/verification/full-verify.log` | Historical archive command/exit witness for the full static chain | Exit success does not establish check adequacy or repo reproducibility; `defer`, experimental, DS4/DS6 | Revisit after DS4/DS6 rerun admitted gates in a pinned repo environment |
| `evidence-release-consistency` | `dist/verification/release-consistency-report.md` | Versions and selected release strings agree on `15.0.0-accessibility-modes` | PolicyOS package name/version intentionally differs and archive consistency is not release approval; `admit_after_refactor`, experimental method, DS4/DS6 | Revisit when generalized to `@polisyos/atlas-ui`, repo versioning, and single-source generated metadata |
| `evidence-verification-report` | `dist/verification/verification-report.md` | Presence of 33 artifacts and pinned markers in ten reports | P29 form-based gate; can stay green when runtime semantics are absent; `reject` as a repo gate, experimental, DS6 | Revisit only when checks derive from and exercise admitted sources/properties, including corrupt-property probes |
| `evidence-verify-log` | `dist/verification/verify.log` | Historical text says generated evidence checks passed | No command, environment, inputs, or resolved results; `reject` as evidence, experimental, DS6 | Revisit if a signed/reproducible run record binds commands, inputs, outputs, and verifier provenance |
| `evidence-component-health` | `governance/component-health.json`; Markdown projection `governance/component-health.md` | Heuristic projection labels 39 components ready and 17 watch from manifest status/state counts | Reuses archive maturity and quantity thresholds; no usage, browser, AT, or owner-freshness evidence; `reject` as PolicyOS maturity evidence, experimental, DS6 | Revisit when health is recomputed from constitutional evidence classes and accountable owner reviews |
| `evidence-theming-audit` | `theming/audit-results.md`; exact duplicate `dist/theming/audit-results.md` | Static agreement for 16 named modes, three theming components, nine tokens, docs, and mirrors | No mode-resolution browser matrix, forced-colors, visual, or AT evidence; `admit_after_refactor`, experimental method, DS4/DS6 | Revisit after admitted modes run across components and system/manual conflicts in browsers |
| `evidence-theming-build` | `theming/build-evidence.md` | Recorded theme manifest/mode/TS projection generation | No repo pipeline or v4 semantic parity; `defer`, experimental, DS4 | Revisit after D2-admitted modes generate through the repo pipeline and pass parity/drift gates |
| `evidence-token-audit` | `tokens/generated/token-audit.md`; exact duplicate `dist/tokens/token-audit.md` | Generated counts, alias totals, source list, and output summary for the archive token graph | Does not compare live v4 semantics or prove repo integration; `defer`, experimental, DS4 | Revisit after the D2 parity map selects admitted values/modes and DS4 reproduces outputs |
| `evidence-token-aggregate-lint` | `tokens/generated/token-lint-results.md`; exact duplicate `dist/tokens/token-lint-results.md` | Aggregate report parses PASS markers from schema/static reports | Form-based aggregation adds no semantic evidence; `reject` as a repo gate, experimental, DS6 | Revisit when aggregation consumes structured recomputed results and corrupt-property probes fail |
| `evidence-token-schema-lint` | `tokens/generated/token-schema-lint.md`; exact duplicate `dist/tokens/token-schema-lint.md` | Static DTCG source/mode structure, alias, and required-output checks for the archive set | No admitted semantic parity or runtime/toolchain proof; `admit_after_refactor`, experimental method, DS4/DS6 | Revisit after the check derives from admitted DTCG files and validates generated repo projections |
| `evidence-token-static-lint` | `tokens/generated/token-static-lint.md`; exact duplicate `dist/tokens/token-static-lint.md` | Static hard-coded-value/baseline scan against the archive's enumerated path set | Baseline and scan roots are archive-specific; no v4 meaning or browser proof; `admit_after_refactor`, experimental method, DS4/DS6 | Revisit when the scan covers the canonical repo consumer graph and intentional value deltas are governed |

### Battery verdict distribution

| Preliminary evidence-artifact verdict | Logical reports |
| --- | ---: |
| `admit_after_refactor` | 9 |
| `defer` | 16 |
| `reject` | 6 |
| `admit_as_is` | 0 |
| `wrap_then_strangle` | 0 |
| **Total** | **31** |

All 31 are `experimental` except the bounded contrast-calculation method,
which is `beta`; none is `stable`. These are evidence-artifact decisions, not
the final distribution across archive components, tokens, and patterns.

## Conformance Negative Controls

- Removing a runtime semantic while retaining the expected report marker can
  leave `scripts/verify.py` green; therefore its report is rejected as a repo
  gate under P29.
- Deleting a best-in-class policy's effectiveness while retaining its file can
  leave the readiness lint green; therefore presence is not adoption or
  maturity evidence.
- A manifest row and state-matrix row can agree while the component fails in a
  browser or launders a UI-local authority status; therefore matrix parity is
  retained only as an input to DS4/DS6.
- Numeric self-scores and component-health labels have producer provenance,
  not independent verifier provenance; they cannot raise maturity.
- Exact duplicate projections add zero independent evidence. They are retained
  in physical coverage but share one logical decision.

## Scope Of This Checkpoint

The conformance battery is complete. Per-item component, token, pattern,
package, and prototype decisions; D2 semantic parity; the full 12-family
v4-vs-v15 outcome; the canonical adoption ledger; and the Phase-A synthesis
belong to the following committed checkpoints. Nothing in this section admits
an archive item into a production surface.
