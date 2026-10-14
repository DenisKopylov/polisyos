# Documentation Inventory

Census date: 2026-10-14 (not a content-freshness assertion)

Owner: `@docs-owners`
Baseline: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` (`policy-engine/docs` tracked tree)
Source of truth: pinned Git tree and `policy-engine/architecture/tooling/mkdocs/generated.yml`; D0-D6 ledger below is historical, not current evidence

Program owner: `@platform-owners`

This page opens with a read-only census of the complete pinned `policy-engine/docs`
tree. Its scope is 14,817 tracked Git blob paths of all file types, including
2,791 Markdown paths. It excludes paths outside that directory and all
post-baseline or uncommitted integration changes. The rest of this page preserves
older D0-D6 and slice notes; their status labels and recorded checks have not
been revalidated by this census and must not be read as current publication
readiness.

This is static tree/config inspection, not a docs acceptance run. No MkDocs
build, docs-accuracy or link check, runbook rehearsal, runtime command, or
semantic content review was run for this census. See the [documentation style
guide](../style-guide.md), [reference navigation](index.md), [measurement author
contract](../how-to/author-measurement-instruments.md), and [failure/repair
register](policy-design-case-failure-patterns.md) (P35-P38) for the governing
standards.

## Pinned baseline census (2026-10-14)

The counts in this section describe the source baseline, not the later
documentation branch. The Git-retained report
`docs/archive/reports/2026-10-14-documentation-maintenance-audit.md` records the
second slice's complete census, per-path review methods, preservation checks
and final publication scope. It is outside the published handbook. Its
verification status governs whether those later measurements are complete;
they do not replace this historical set.

### Reproduction and evidence

The complete-set walk ran:

```sh
git ls-tree -r -z bafca83bff9ff49eef1466bc491a8420b5cd1dbb -- policy-engine/docs
```

It returned
14,817 entries, all Git blobs; SHA-256 of the command's NUL-delimited stdout is
`4d6f13e3e2230a8b464f76887c9e43fe1793b625580fe9f949b96ff0b9886bf2`. The
2,791 Markdown blobs were fetched with `git cat-file --batch`; the marker scan
examined only their first 80 lines. The other 12,026 paths were counted by path,
suffix, and blob ID, but their content bytes were not read.

The static config source is `policy-engine/mkdocs.yml`, which inherits
`policy-engine/architecture/tooling/mkdocs/generated.yml` at the baseline. The
generated-config blob is `68f12ccdd0e447241c65d90aeb3134d1e4f75ec0`
(SHA-256 `788cedda8e55160056a4a6be042f152246ab2984398b773b937363a8538d22b9`).
The YAML nav was parsed with PyYAML 6.0.3 under Python 3.14.0. Reproduce the
measurement in the originating worktree with
`python3 policy-engine/_build/docs-refresh/raw/census.py`; that script and its
receipts are ignored local evidence, not tracked repository files. The script
SHA-256 is `22aedc24478965abfedffc81f2a51a0537753aae16977989ce88d196c7557777`.
The compact summary is `policy-engine/_build/docs-refresh/raw/census.json`
(`7c6bea63572877efe501a9d3b901914884dc7badae14288da731281f7098383e`); the
complete 14,817-path manifest with Git blob IDs is
`policy-engine/_build/docs-refresh/raw/tracked-files.jsonl.gz`
(`6d0a71145f64f8f916b471e8e41d874a56645b5ea7cbc3170fbc3825211446b1`).

The census follows P35: every count below names its complete path and file-type
denominator. The summary and manifest preserve the derived result and the full
path set rather than copying a large dump into this page.

### Tracked file types

All suffix categories below partition the 14,817 tracked blob paths; their counts
sum to that denominator. `[no extension]` is a path suffix category.

| Suffix               | Paths | Suffix           | Paths |
| -------------------- | ----: | ---------------- | ----: |
| `.bin`               | 2     | `.blob`          | 31    |
| `.candidate`         | 1     | `.css`           | 2     |
| `.diff`              | 15    | `.docx`          | 1     |
| `.exitcode`          | 8     | `.gz`            | 799   |
| `.html`              | 1     | `.in`            | 1     |
| `.initial-candidate` | 1     | `.json`          | 6,050 |
| `.jsonl`             | 13    | `.lock`          | 16    |
| `.log`               | 51    | `.md`            | 2,791 |
| `.mjs`               | 2     | `.ndjson`        | 2     |
| `.nul`               | 1     | `.patch`         | 30    |
| `.png`               | 9     | `.pt`            | 8     |
| `.py`                | 1,161 | `.receiver-only` | 1     |
| `.sh`                | 2     | `.sha256`        | 6     |
| `.sqlite`            | 2     | `.sqlite-wal`    | 2     |
| `.stderr`            | 606   | `.stdin`         | 1     |
| `.stdout`            | 537   | `.toml`          | 4     |
| `.tsv`               | 6     | `.txt`           | 2,329 |
| `.webm`              | 6     | `.xml`           | 199   |
| `.xz`                | 62    | `.yaml`          | 1     |
| `.yml`               | 2     | `.zip`           | 7     |
| `[no extension]`     | 48    | —                | —     |

### Markdown path taxonomy

This taxonomy is derived only from the first directory in each relative Markdown
path. It is a filing map, not a claim about the page's semantic type. The
categories partition all 2,791 Markdown paths.

| Path-derived bucket        | Markdown paths |
| -------------------------- | -------------: |
| `tutorials/`               | 5              |
| `how-to/`                  | 31             |
| `reference/`               | 202            |
| `explanation/`             | 13             |
| `adr/`                     | 197            |
| `plans/`                   | 339            |
| `archive/`                 | 53             |
| `system-design-decisions/` | 20             |
| `runbooks/`                | 27             |
| Docs root                  | 4              |
| Other top-level paths      | 1,900          |
| **Total**                  | **2,791**      |

The four Diataxis directories contain 251 Markdown paths. `Other top-level
paths` is deliberately broad; it is not a semantic category or a judgment that
those pages should be published.

### Static navigation and disposition coverage

At the pinned baseline, `mkdocs.yml` inherits the generated config above. Its
static `nav` has 358 Markdown scalar references and 358 unique paths; all 358
match tracked Markdown paths, with zero missing. The inventory itself is among
the listed paths. This is a string-to-tree join, not proof of a successful site
build or rendered navigation.

| Disjoint static path class      | Markdown paths | Basis                                                |
| ------------------------------- | -------------: | ---------------------------------------------------- |
| Explicit `nav` target           | 358            | Parsed YAML strings ending in `.md`, exact path join |
| Candidate `exclude_docs` match  | 417            | Python `fnmatchcase` against tracked Markdown paths  |
| Declared `not_in_nav` path      | 117            | Listed paths joined to tracked Markdown paths        |
| No match in those three classes | 1,899          | Residual of the complete Markdown set                |
| **Total**                       | **2,791**      | No class overlaps in this static partition           |

The generated config has 27 `exclude_docs` patterns; 19 match no path in the
complete 14,817-path tree under the census's `fnmatchcase` approximation.
`not_in_nav` has 117 declared Markdown paths, all matching the pinned tree. The
1,899 residual paths are not silently
assigned to a publication state: by top-level directory they are `research/`
1,536, `superpowers/` 296, `reference/` 35,
`system-design-decisions/` 20, `backlog/` 6, `how-to/` 3, and one each under
`brand/`, `explanation/`, and `runbooks/`. These are disposition candidates,
not proof of omissions: directory and pattern matching do not establish intent
or effective MkDocs behavior.

### Lifecycle marker scan

The following counts use the same denominator: all 2,791 Markdown blobs under
`policy-engine/docs/` at the pinned baseline. A marker means a recognized field
label appeared in the first 80 lines; it does not establish a valid value, a
current value, or whole-document coverage. Marker categories can overlap and
are not an additive lifecycle score.

| First-80-line marker           | Markdown paths with marker |
| ------------------------------ | -------------------------: |
| Front matter delimiters        | 422 / 2,791                |
| Status                         | 554 / 2,791                |
| Date-like field                | 379 / 2,791                |
| Freshness / last-updated field | 90 / 2,791                 |
| Owner                          | 496 / 2,791                |
| Last-tested field              | 23 / 2,791                 |

For the 27 paths under `runbooks/`, the same scan found owner markers in 26,
last-tested markers in 23, evidence markers in 26, and rollback markers in 25.
The first-80-line marker gaps are: `runbooks/lex-production-140k.md` (owner,
evidence, rollback), `runbooks/cloud-production-debugging.md`,
`runbooks/local-production-debugging.md`, and
`runbooks/production-quality-triage.md` (last-tested); the latter also lacks a
rollback marker in that window. This does not establish that the field is
absent later in any file. For 197 paths under `adr/`, a status marker appeared
in 20 and a date marker in 19. Compare the actual ADRs with the [Date and Status
template](../style-guide.md#adr-template); the bounded marker scan alone cannot
declare noncompliance. The [README freshness policy](../style-guide.md#readme-freshness-policy)
is scoped to package README files, not every Markdown page.

### Evidence limits and prioritized follow-up

| Priority | Gap to close                                                                                                                                                                            | Evidence boundary / acceptance signal                                                                                                                  |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| P1       | Reconcile the 1,899 residual Markdown paths with an explicit publish, exclude, or intentional-not-in-nav disposition. Start with `research/` and `superpowers/`; preserve owner intent. | Complete path manifest plus owner-reviewed classifications; no directory-name inference.                                                               |
| P1       | Reconcile the 19 unmatched `exclude_docs` patterns against their source fragments and actual MkDocs selection semantics.                                                                | Strict MkDocs build and config-owner review; do not delete patterns on the `fnmatchcase` result alone.                                                 |
| P1       | Recompute navigation and dispositions after the shared documentation refresh is frozen.                                                                                                 | Repeat the complete pinned-tree census against the delivered ref, then run the docs checks required by the style guide.                                |
| P2       | Review the runbook and ADR marker gaps against full page contents and their actual lifecycle requirements.                                                                              | Record owners, evidence/rollback posture, last-tested evidence, and ADR Date/Status only where required; verify rather than infer from marker absence. |
| P2       | Establish content accuracy and freshness for published pages.                                                                                                                           | Owner/source review and the documented docs-accuracy/link/build gates; the census does not assess prose or behavior.                                   |

Evidence predicate labels, following P37 (applied here to the census, not as a
publication gate): tree membership and path/type counts are `recomputed` from
the pinned Git tree; the static nav join and first-80-line marker counts are
`recomputed` from pinned inputs; candidate exclusion matches are `recomputed`
under the stated `fnmatchcase` approximation. Taxonomy meaning is
`not_established` beyond the path heuristic; equivalence to effective MkDocs
exclusion/publication, content accuracy, lifecycle validity, and freshness are
`not_established`.
Following P38, the property sought by the lifecycle scan is useful, current
metadata, while its implementation tests only recognized field labels in a
bounded prefix. A stale or invalid value beyond—or inside—a matching label is a
divergent case, so marker presence is not a freshness or compliance gate. This
census therefore reports no runtime-verified or content-verified result.

## 2026-09-11 instrument and custody impact note

Historical slice note: this records the state as described for that local slice;
it was not revalidated by the 2026-10-14 census.

Scope: the local `codex/instrument-honesty` slice from `cc74d6581`. This note
records the changed behavior and operational boundary; it is not a hosted CI
receipt, a historical source-impact repair, or an authority promotion.

- **Fabric connector configuration:** `ConnectionConfig.redacted()` in
  `src/polisyos/fabric/connectors/base.py` submits every credential value to the
  canonical secret scanner while preserving arbitrary credential keys and the
  immutable input mapping. Incomplete scanner output raises an explicit redaction
  UNRUN error instead of returning apparently empty credentials. Headers retain
  the scanner's existing handling. URL contents and credential key names are not
  a complete secret-redaction surface. The negative tests in
  `tests/unit/fabric/connectors/sources/test_http_connector_base.py` exercise
  arbitrary secret keys and malformed scanner output; the protocol consumer is
  separately exercised in `tests/unit/fabric/connectors/test_protocol_compliance.py`.
- **Runtime/Core custody:** runtime constructors compose the existing
  `build_artifact_store` factory and public `ArtifactStore` contract. The factory
  carries explicit filesystem tenant/cell ownership; unsupported backends refuse
  scoped construction before creating a remote store. Existing CAS roots,
  permissions, receipt kinds and ledger accounting remain governed by their
  owners. Acquisition accepts an injected store and registry providers and
  refuses a store whose artifact backing differs from its declared source;
  missing injected profiles do not fall back to a process-global registry.
  `tests/unit/core/artifacts/backends/test_config.py` exercises actual persistence,
  reopening and wrong-scope refusal; `test_live_acquisition_executor.py` exercises
  the real orchestrator/connector with transport intercepted.
- **Scientist/Common ownership:** the JSON extraction implementation moved into
  the existing `polisyos.common.serialization` owner, with all non-test importers
  redirected. This includes discovery workers, design generation, the adversary
  and translator. The extraction function AST bodies are unchanged, and real
  parser/importer negatives still reject malformed output. LLM text remains a
  candidate; the move grants no evidence or approval authority. Discovery workers'
  public interface and Foundry method semantics are not extended by this import
  consolidation. Package-boundary acceptance of the new import edges remains an
  architect decision, not an incidental baseline refresh.
- **Dashboard and schema consumers:** behavioral tests exercise shortcuts,
  reproduction navigation and real scenario-query admission. Statement coverage
  still uses the existing 85.57% floor and zero tolerance. The types comparison
  now invokes the locked workspace generator and its existing recursive-type
  normalizer; subprocess success alone cannot establish canonical byte agreement.
  Coverage, type bytes and static invocation each print their own unmeasured
  boundaries and do not establish deployed runtime behavior.

Operational response for these changed seams: treat an unavailable scanner,
registry, owner validator or comparison artifact as no complete verdict. Preserve
that reason and the existing receipt bytes; do not promote a previous success or
retry against another store/profile as if it were the requested custody scope.
For suspected CAS migration issues, first reconcile the configured root and
explicit tenant/cell against the actual store, then use the named persistence and
acquisition tests above. For schema drift, run the registered
`polisyos-tools runtime check-runtime-api-contract` and regenerate through
`polisyos-tools runtime export-runtime-openapi` only after source inputs are
frozen. A timeout is distinct from a completed byte diff. For import findings,
retain the exact edges for the architect; do not run guardrails sync to clear them.
These are local diagnosis instructions, not a completed production rehearsal.

The existing path-aware documentation planner measures changed-path coverage,
not the substance of this note or execution of its planned child gates. Original
C-CI F19/F20/F21/F22 findings retain their historical ranges; this note addresses
only the current slice. Deciding local evidence and explicit test selectors are
retained in the repository's instrument completion journal and runner.

## Historical D0 Exit Snapshot

| Exit criterion                            | Status | Evidence                                                                         |
| ----------------------------------------- | ------ | -------------------------------------------------------------------------------- |
| Inventory page exists                     | active | This page is the D0 inventory skeleton.                                          |
| Six source remediation plans are linked   | active | See [Historical D0 plan map](#historical-d0-canonical-source-plan-map).          |
| Every lane has owner and doc surfaces     | active | See [Ownership](ownership.md#documentation-sota-lane-owners).                    |
| D0 QA evidence was recorded               | active | See [Historical QA Ledger](#historical-qa-ledger-recorded-2026-05-03-not-rerun). |
| Shared coordination files were identified | active | See [Historical Conflict Map](#historical-conflict-map).                         |

## Historical D0 Canonical Source Plan Map

This is the D0 source-plan map, not a current list of active remediation plans.
Its plans were input evidence for the original refresh; current work should
verify claims against current code, generators, schemas, tests, and CI gates.

| Lane                   | Source plan                                                       | Primary docs impact                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| L1 Core/Common/Runtime | `docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md` | `README.md`, runtime API reference, operations reference, security model, runtime runbooks, `src/polisyos/{common,core,runtime}/README.md` |
| L2 Fabric              | `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`              | Fabric reference, connectors guide, data-plane docs, data source how-to, Fabric runbooks                                                   |
| L3 Foundry             | `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`                   | Foundry reference, methods catalog, causal-engine explanation, benchmark and reproducibility docs                                          |
| L4 IR                  | `docs/plans/active/IR_AUDIT_REMEDIATION_PLAN.md`                  | IR reference, schema catalog, contracts, ADR index, interoperability docs                                                                  |
| L5 Tools               | `docs/plans/active/TOOLS_AUDIT_REMEDIATION_PLAN.md`               | Tools reference, CI/CD how-to, contributor command map, validation docs                                                                    |
| L6 Scientist           | `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`           | Scientist reference, workflows/nodes/governance docs, reliability scorecard, Scientist how-to/tutorial surfaces                            |

## Historical D0-D6 Documentation Surface Inventory

This table preserves the publication-readiness claims recorded for D0-D6.
Status values such as `active` are historical labels and were not rechecked in
the pinned census; generated pages remain governed by their canonical
regeneration commands.

| Page or surface                                                                | Owner                                              | Status                                                                                                                                                      | Source of truth                                                                                                                                                                                                                                                                                                                                         | Validation method                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------ | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `policy-engine/README.md`                                                      | `@docs-owners`                                     | active gateway                                                                                                                                              | product root, public-surface inventory, command registry                                                                                                                                                                                                                                                                                                | docs accuracy check, quickstart command smoke tests                                                                                                                                                                                           |
| `docs/reference/index.md`                                                      | `@docs-owners`                                     | active shared nav                                                                                                                                           | `mkdocs.yml`, this inventory                                                                                                                                                                                                                                                                                                                            | MkDocs strict build                                                                                                                                                                                                                           |
| `docs/reference/documentation-inventory.md`                                    | `@docs-owners`                                     | active D0 baseline                                                                                                                                          | `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md` Phase D0                                                                                                                                                                                                                                                                                                 | linked from reference index and nav                                                                                                                                                                                                           |
| `docs/reference/repository-topology.md`                                        | `@platform-owners`                                 | active topology reference                                                                                                                                   | Repository SOTA accepted closeout and architecture contracts                                                                                                                                                                                                                                                                                            | public-polish gate, topology cleanup gate, closeout command                                                                                                                                                                                   |
| `docs/reference/ownership.md`                                                  | `@platform-owners`                                 | active D0 owner map                                                                                                                                         | logical owner groups documented in `docs/reference/ownership.md`                                                                                                                                                                                                                                                                                        | every L0-L9 lane has primary and backup owner                                                                                                                                                                                                 |
| `docs/reference/quality-gates.md`                                              | `@platform-owners`                                 | active D6 gate map                                                                                                                                          | validation tools, CI workflows, merge governance                                                                                                                                                                                                                                                                                                        | docs drift gate, docs accuracy, CI parity                                                                                                                                                                                                     |
| `docs/reference/api/**`                                                        | `@runtime-owners`                                  | active reference                                                                                                                                            | Runtime OpenAPI export, runtime tests                                                                                                                                                                                                                                                                                                                   | OpenAPI contract check, API tests                                                                                                                                                                                                             |
| `docs/reference/fabric/**`                                                     | `@fabric-owners`                                   | active reference                                                                                                                                            | Fabric plan, connector registry, data-plane tests                                                                                                                                                                                                                                                                                                       | connector registry tests, schema compatibility gates                                                                                                                                                                                          |
| `docs/reference/foundry/**`                                                    | `@foundry-owners`                                  | active reference                                                                                                                                            | Foundry plan, methods catalog, benchmarks                                                                                                                                                                                                                                                                                                               | Foundry tests, benchmark gates, reproducibility checks                                                                                                                                                                                        |
| `docs/reference/ir/**`                                                         | `@ir-owners`                                       | active/generated reference                                                                                                                                  | IR schemas, schema snapshots, IR tests                                                                                                                                                                                                                                                                                                                  | schema generation check, property/fuzz tests where available                                                                                                                                                                                  |
| `docs/reference/scientist/**`                                                  | `@scientist-owners`                                | active reference                                                                                                                                            | Scientist plan, workflow/node registries, phase gates                                                                                                                                                                                                                                                                                                   | Scientist phase gates, docs accuracy, MkDocs link checks                                                                                                                                                                                      |
| `docs/reference/tools.md`                                                      | `@tools-owners`                                    | regenerated in D0                                                                                                                                           | `tools.registry` command metadata                                                                                                                                                                                                                                                                                                                       | `uv run polisyos-tools docs --output docs/reference/tools.md`                                                                                                                                                                                 |
| `docs/reference/schemas.md`                                                    | `@ir-owners`                                       | active/generated reference                                                                                                                                  | generated schema inventory                                                                                                                                                                                                                                                                                                                              | schema generation check                                                                                                                                                                                                                       |
| `docs/reference/operations/**`                                                 | `@platform-owners`                                 | active operations reference                                                                                                                                 | runbooks, SLO docs, operational checks                                                                                                                                                                                                                                                                                                                  | CI parity, runbook rehearsal evidence                                                                                                                                                                                                         |
| `docs/reference/policy-design-case-failure-patterns.md`                        | `team-policyos-runtime`                            | active PDC pattern register                                                                                                                                 | P01-P15 failure and repair vocabulary, capability reality labels                                                                                                                                                                                                                                                                                        | pattern lifecycle use in plans, tests, and closeout notes                                                                                                                                                                                     |
| `docs/reference/policy-design-case-capability-ratchet.md`                      | `team-runtime-quality`                             | active W1.A capability ratchet                                                                                                                              | `architecture/policy_design_case/capability_reality_report.json`, capability ratchet checker                                                                                                                                                                                                                                                            | `uv run pytest tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q`                                                                                                                                                     |
| `docs/reference/policy-design-case-layer3-grounding-inventory.md`              | `team-runtime-quality` with `principal-governance` | active G0 v2 pre-adapter audit surface                                                                                                                      | `src/polisyos/runtime/quality/proving_ground/pre_adapter_grounding_inventory.py`, `architecture/policy_design_case/inventory.json`, ADR-0175 v2 amendment, persisted discovery/search artifacts                                                                                                                                                         | `uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g0_readiness.py -q`                                                                                                                                                    |
| `docs/reference/policy-design-case-layer3-substrate-grounding.md`              | `team-runtime-quality`                             | active G1 EXPERT/MACHINE substrate grounding audit surface                                                                                                  | `src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py`, `architecture/policy_design_case/inventory.json`, `architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml`, G0 v2 dependency artifacts                                                                                                                   | `uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py -q`                                                                                                                                                    |
| `docs/reference/policy-design-case-layer3-causal-forecast.md`                  | `team-runtime-quality`                             | active G2 PUBLIC/REVIEWER/EXPERT/MACHINE causal forecast tier audit surface                                                                                 | `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`, `architecture/policy_design_case/inventory.json`, `architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml`, G1 dependency artifacts                                                                                                                          | `uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness_cli.py -q`                                                                        |
| `docs/reference/policy-design-case-layer3-analytics-search.md`                 | `team-runtime-quality`                             | active G3 PUBLIC/REVIEWER/EXPERT/MACHINE analytics search audit surface                                                                                     | `src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py`, `architecture/policy_design_case/inventory.json`, `architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml`, G2 dependency artifacts                                                                                                                 | `uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness_cli.py -q`                                                                        |
| `docs/reference/policy-design-case-layer3-legal-mandate-search.md`             | `team-runtime-quality`                             | active GL EXPERT/MACHINE legal mandate search audit surface                                                                                                 | `src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py`, `architecture/policy_design_case/layer3_gl_legal_mandate_audit_surface.json`, `architecture/policy_design_case/layer3_gl_public_export_projection_refs.json`, L3 Legal KG dependency artifacts                                                                                   | `uv run pytest tests/unit/runtime/quality/test_layer3_gl_legal_mandate_search.py tests/repo_quality/tools/test_policy_design_case_layer3_gl_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_gl_readiness_cli.py -q`      |
| `docs/reference/policy-design-case-layer3-promotion-gate.md`                   | `team-runtime-quality`                             | active G4 PUBLIC/REVIEWER/EXPERT/MACHINE shadow-to-governed promotion audit surface                                                                         | `src/polisyos/runtime/quality/proving_ground/governed_promotion_gate.py`, `architecture/policy_design_case/layer3_g4_promotion_audit_surface.json`, `architecture/policy_design_case/layer3_g4_public_export_projection_refs.json`, G1/G2/G3/GL dependency artifacts                                                                                    | `uv run pytest tests/unit/runtime/quality/test_layer3_g4_promotion_gate.py tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g4_readiness_cli.py -q`            |
| `docs/reference/policy-design-case-layer3-proving-ground-conversion.md`        | `team-runtime-quality`                             | active G5 PUBLIC/REVIEWER/EXPERT/MACHINE first proving-ground conversion audit surface                                                                      | `src/polisyos/runtime/quality/proving_ground/proving_ground_conversion.py`, `architecture/policy_design_case/layer3_g5_conversion_audit_surface.json`, `architecture/policy_design_case/layer3_g5_public_export_projection_refs.json`, G4 handoff and W12.D pinned input artifacts                                                                      | `uv run pytest tests/unit/runtime/quality/test_layer3_g5_proving_ground_conversion.py tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g5_readiness_cli.py -q` |
| `docs/reference/policy-design-case-layer3-bounded-agent.md`                    | `team-runtime-quality`                             | active G6 PUBLIC/REVIEWER/EXPERT/MACHINE bounded arbitrary-request adapter audit surface                                                                    | `src/polisyos/runtime/quality/proving_ground/bounded_request_agent.py`, `architecture/policy_design_case/layer3_g6_agent_audit_surface.json`, `architecture/policy_design_case/layer3_g6_public_export_projection_refs.json`, policy-grammar projection, G5 bridge, replay/continuity, and search-ledger artifacts                                      | `uv run pytest tests/unit/runtime/quality/test_layer3_g6_bounded_agent.py tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g6_readiness_cli.py -q`             |
| `docs/reference/public-surface.md#policy-design-case-generated-audit-surfaces` | `team-runtime-quality`                             | active `layer3_g7_region_widening_surface` PUBLIC/REVIEWER/EXPERT/MACHINE region-widening audit surface                                                     | `src/polisyos/runtime/quality/proving_ground/region_widening.py`, `architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json`, `architecture/policy_design_case/layer3_g7_public_export_projection_refs.json`, region scorecard, S14 feed/consumer gate, replay/continuity, route registry, and readiness manifest artifacts         | `uv run pytest tests/unit/runtime/quality/test_layer3_g7_region_widening.py tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g7_readiness_cli.py -q`           |
| `docs/reference/public-surface.md#policy-design-case-generated-audit-surfaces` | `team-runtime-quality`                             | active `layer3_g8_health_metric_governance_surface` EXPERT/MACHINE health-metric governance audit surface with PUBLIC/REVIEWER projection refs out of scope | `src/polisyos/runtime/quality/proving_ground/health_metric_governance.py`, `architecture/policy_design_case/layer3_g8_metric_governance_audit_surface.json`, `architecture/policy_design_case/layer3_g8_closeout_signal_consumer_gate.json`, metric registry, D4.4 rebasing receipts, replay manifest, route registry, and readiness manifest artifacts | `uv run pytest tests/unit/runtime/quality/test_layer3_g8_health_metric_governance.py tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g8_readiness_cli.py -q`  |
| `docs/reference/policy-design-case-source-ownership.md`                        | `team-policyos-runtime`                            | active W0.G source ledger                                                                                                                                   | raw research ledger, normalized synthesis, research plan, implementation plan, ADR index                                                                                                                                                                                                                                                                | `uv run pytest tests/repo_quality/tools/test_policy_design_case_source_ownership.py -q`                                                                                                                                                       |
| `docs/reference/policy-design-case-evidence-paths.md`                          | `team-policyos-runtime`                            | active W1.E evidence path ledger                                                                                                                            | W0.G source ledger, W0.H structural ADR registry, implementation plan, operator runbook                                                                                                                                                                                                                                                                 | `uv run pytest tests/repo_quality/tools/test_policy_design_case_documentation_paths.py -q`                                                                                                                                                    |
| `docs/reference/policy-design-case-structural-adr-registry.md`                 | `team-policyos-runtime`                            | active W0.H structural ADR registry                                                                                                                         | C0-C41 research map, implementation plan, ADR index, W0 fast-track ADRs                                                                                                                                                                                                                                                                                 | `uv run pytest tests/repo_quality/tools/test_policy_design_case_structural_adr_registry.py -q`                                                                                                                                                |
| `docs/reference/policy-design-case-operator-guide.md`                          | `team-policyos-runtime`                            | active W5.E operator guide                                                                                                                                  | evidence paths, structural ADR registry, system-design decision index, tuned-parameter owner ledger, validation ladder, capability evidence, rollout runbook                                                                                                                                                                                            | `uv run pytest tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py -q`                                                                                                                                                      |
| `docs/runbooks/policy-design-case-rollout-rollback.md`                         | `@platform-owners` with `team-policyos-runtime`    | active W5.E rollout runbook                                                                                                                                 | operator guide, evidence paths, capability ratchet, structural ADR registry, W6 validation ladder                                                                                                                                                                                                                                                       | `uv run pytest tests/repo_quality/tools/test_policy_design_case_w5e_docs_runbooks.py -q`                                                                                                                                                      |
| `docs/runbooks/**`                                                             | `@platform-owners`                                 | active rehearsed runbooks                                                                                                                                   | incident procedures, release gates                                                                                                                                                                                                                                                                                                                      | last-tested evidence and rollback validation                                                                                                                                                                                                  |
| `docs/how-to/**`                                                               | `@docs-owners`                                     | active task guidance                                                                                                                                        | current CLI, API, code paths                                                                                                                                                                                                                                                                                                                            | walkthrough smoke tests                                                                                                                                                                                                                       |
| `docs/tutorials/**`                                                            | `@docs-owners`                                     | active tutorial path                                                                                                                                        | product quickstart and example fixtures                                                                                                                                                                                                                                                                                                                 | tutorial smoke tests                                                                                                                                                                                                                          |
| `docs/explanation/**`                                                          | `@docs-owners`                                     | active explanations                                                                                                                                         | ADRs, architecture boundaries, source plans                                                                                                                                                                                                                                                                                                             | docs accuracy and owner review                                                                                                                                                                                                                |
| `docs/contracts/**`                                                            | `@platform-owners`                                 | active contract reference                                                                                                                                   | contracts, schemas, ABI snapshots                                                                                                                                                                                                                                                                                                                       | schema/ABI contract gates                                                                                                                                                                                                                     |
| `docs/adr/**`                                                                  | `@platform-owners`                                 | active decision history                                                                                                                                     | accepted ADRs and supersession notes                                                                                                                                                                                                                                                                                                                    | MkDocs strict, ADR owner review                                                                                                                                                                                                               |

## Historical Root-Level Plan Status Ledger

This is the D0 classification snapshot for the root-level plan paths it listed.
Its status and publication claims were not revalidated in this census and are
not a current source of truth. Archived plan paths were outside that historical
ledger.

| Plan                                                                             | Status       | Owner lane | D0 classification note                                                                                                                                                                                                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------- | ------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/plans/active/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md`                | active       | L1         | Canonical source remediation plan for Core/Common/Runtime docs refresh.                                                                                                                                                                                                                                                                                                                                                       |
| `docs/plans/archive/DATA_FORGE_CONSOLIDATION_PLAN_ROOT_LEGACY.md`                | archived     | L2/L5      | Adjacent data-pipeline consolidation plan; use as historical context for Fabric/Tools docs only after owner review.                                                                                                                                                                                                                                                                                                           |
| `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`                                   | active       | L0         | Program plan for this docs refresh; excluded from published docs site by `mkdocs.yml`.                                                                                                                                                                                                                                                                                                                                        |
| `docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`                             | active       | L2         | Canonical source remediation plan for Fabric docs refresh.                                                                                                                                                                                                                                                                                                                                                                    |
| `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`                                  | active       | L3         | Canonical source remediation plan for Foundry docs refresh; file marks active implementation and release-gate hardening.                                                                                                                                                                                                                                                                                                      |
| `docs/plans/active/FRONTEND_SOTA_PLAN.md`                                        | active       | L7         | Frontend/API-consumer plan; planning-only surface excluded from the published site by `mkdocs.yml`.                                                                                                                                                                                                                                                                                                                           |
| `docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md`                                  | active       | L8/L9      | Infrastructure/platform plan; useful for ownership, gates, and release governance surfaces.                                                                                                                                                                                                                                                                                                                                   |
| `docs/plans/active/IR_AUDIT_REMEDIATION_PLAN.md`                                 | active       | L4         | Canonical source remediation plan for IR docs refresh.                                                                                                                                                                                                                                                                                                                                                                        |
| `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`       | active       | L6/L9      | Repo-owned research plan for universal Policy Design Case C0-C41 and E0-E24 handoff.                                                                                                                                                                                                                                                                                                                                          |
| `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md` | active-draft | L6/L9      | Engineering wave plan for universal Policy Design Case implementation; W0.G source chain is indexed in `docs/reference/policy-design-case-source-ownership.md`, W1.E command evidence paths are indexed in `docs/reference/policy-design-case-evidence-paths.md`, and W5.E operator guidance is indexed in `docs/reference/policy-design-case-operator-guide.md` plus `docs/runbooks/policy-design-case-rollout-rollback.md`. |
| `docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`                          | active       | L6         | Canonical source remediation plan for Scientist docs refresh.                                                                                                                                                                                                                                                                                                                                                                 |
| `docs/plans/active/TOOLS_AUDIT_REMEDIATION_PLAN.md`                              | active       | L5         | Canonical source remediation plan for Tools docs refresh.                                                                                                                                                                                                                                                                                                                                                                     |
| `docs/plans/active/UKRAINE_FUNDING_INTELLIGENCE_PLAN.md`                         | active       | L2/L6      | Domain/data plan; use as context for Ukraine funding surfaces and data-source docs.                                                                                                                                                                                                                                                                                                                                           |
| `docs/plans/accepted/REPOSITORY_SOTA_PLAN.md`                                    | accepted     | L0/L5/L8   | Final repository-topology closeout. Stable behavior is now published in `docs/reference/repository-topology.md`.                                                                                                                                                                                                                                                                                                              |

## Historical QA Ledger (recorded 2026-05-03; not rerun)

The commands and results below were recorded from `policy-engine/` on
2026-05-03 after Repository SOTA public-polish closeout. They are historical
receipts, not current status, and were not replayed for the 2026-10-14 census.

| Command                                                                                                                                                                                             | Status                        | Recorded output                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run polisyos-tools architecture guardrails sync`                                                                                                                                                | pass                          | Architecture guardrail inventories updated; generated reference inventories are in sync with the current repo state.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `uv run polisyos-tools docs --output docs/reference/tools.md`                                                                                                                                       | pass                          | Wrote `docs/reference/tools.md`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `uv run polisyos-tools validation check-docs-gate --repo-root .`                                                                                                                                    | pass                          | Full D6 docs gate remains the canonical docs-sensitive umbrella: generated tools reference, public-surface/README guardrails, ABI schema snapshots, Runtime API OpenAPI/client drift, docs accuracy, strict MkDocs, and semantic public-surface docstrings are validated through one path-aware command.                                                                                                                                                                                                                                                                                                                            |
| `PYTHONPATH=src:. uv run --extra ml python tools/quality/diagnostics/gen_schema.py`                                                                                                                 | pass                          | Generated ABI schema snapshots for 84 models (`0` file updates, `scan_mode=full`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `uv run polisyos-tools validation check-docs-accuracy --repo-root .`                                                                                                                                | pass                          | Docs accuracy reports published-doc drift without treating excluded plans as public navigation. Active GitHub workflow facts come from repository-root `.github/workflows/**`; reusable product workflow templates remain under `ops/ci/templates/workflows/**`.                                                                                                                                                                                                                                                                                                                                                                    |
| `uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q`                                                                                                                 | pass                          | Public-polish gate blocks Markdown links from published docs to excluded plan evidence, stale current-topology wording, Repository SOTA evidence left in active lifecycle, and missing repository-topology navigation.                                                                                                                                                                                                                                                                                                                                                                                                              |
| `uv run polisyos-tools workspace repository-sota-closeout`                                                                                                                                          | pass                          | Repository SOTA closeout validates the fail-closed topology, import, public-surface, generated-artifact, docs, shim, security, dependency, SBOM, commit-policy, and command-registry gates.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `uv run polisyos-tools architecture guardrails check`                                                                                                                                               | pass                          | Architecture guardrail check passed.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `PYTHONPATH=src:. uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check`                                                                                                         | pass                          | ABI schema snapshot check passed (84 models, `scan_mode=full`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `uv run --extra docs python -m mkdocs build --strict`                                                                                                                                               | pass                          | Documentation built successfully after plan-only docs were excluded from the published site and the D6 docs gate wiring was added. No project-content strict warnings or errors remained. The only extra terminal banner comes from the installed Material for MkDocs package and is suppressible with `NO_MKDOCS_2_WARNING=true`.                                                                                                                                                                                                                                                                                                  |
| `uv run polisyos-tools validation check-docstring-quality --repo-root . --allowlist tools/quality/validation/docstring_quality_allowlist.txt --coverage-scope public-surface --minimum-coverage 85` | pass                          | Inspected `6758` public symbols. Semantic coverage: `4774/6758` all subjects (`70.6%`), `3787/3823` public surface (`99.1%`), with `0` placeholder violations. Remaining second-pass packages are tracked as semantic-depth debt, not gate failures.                                                                                                                                                                                                                                                                                                                                                                                |
| `uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml --output-format json`                                 | pass                          | Import policy passed after adding `ukraine_data` to the known internal roots and recording newly surfaced boundary crossings as expiring import exceptions. Current result: `0` violations, `53` allowed exceptions, `1` non-enforced package-level cycle warning.                                                                                                                                                                                                                                                                                                                                                                  |
| `uv run python tools/quality/diagnostics/check_state_reads.py`                                                                                                                                      | pass                          | `state_reads contract check passed` after Scientist built-in nodes declared the broad `artifacts_index`/`reports_index` and exact `run_id` reads their `execute` paths already performed.                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `uv run polisyos-tools connectors check-contracts --check`                                                                                                                                          | pass                          | Connector contract snapshot passed after regenerating `schemas/snapshots/connectors/contracts.json`; the snapshot now includes the connector approval metadata shape emitted by the current registry contracts.                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `uv run pytest tests/performance/test_benchmark_runtime_pipeline.py`                                                                                                                                | pass                          | `3 passed`; the legacy `benchmarks.run_parallel` import path now exposes the canonical parallel benchmark scheduler for the runtime-pipeline tests.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `python3 -m tools.cli workspace ci-parity --skip-browser`                                                                                                                                           | blocked outside docs closeout | The run now passes doctor, import policy, Foundry ban list, `state_reads`, Scholar imports, connector contracts, ABI schema freshness, Runtime API contract, and frontend contract fixtures before reaching the broad backend pytest gate. Backend pytest then fails with `186 failed, 8895 passed, 54 skipped, 110 deselected` in `38:09`; dominant clusters are missing local data/catalog fixtures, legacy academic/dataset script exports, and pre-existing Foundry/IR/Scientist backend contract failures. This is no longer the D6 documentation-gate/import/docstring blocker; it is recorded as separate backend test debt. |

## Historical Conflict Map

This records shared coordination surfaces and review guidance from the earlier
refresh; assignments and conflict status were not revalidated by the census.

| Shared file or surface                                              | Coordination owner | Why it conflicts                                                                     | D0 rule                                                                           |
| ------------------------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `mkdocs.yml`                                                        | L0/L9              | Global nav, exclusions, plugin behavior, and strict-mode failures affect every lane. | One lane edits nav at a time; keep generated pages in nav or explicitly excluded. |
| `docs/index.md`                                                     | L0                 | Published home page frames product state and current entry points.                   | Update only after source-plan mapping confirms current claims.                    |
| `docs/reference/index.md`                                           | L0                 | Reference landing page links all subsystem docs.                                     | Add only canonical D0/D1 coordination links until lane pages are refreshed.       |
| `docs/reference/documentation-inventory.md`                         | L0                 | Shared ledger for plan status, QA blockers, and conflicts.                           | Add findings here before rewriting another lane's technical content.              |
| `docs/reference/ownership.md`                                       | L0/L8              | Owner routing drives reviews and escalation.                                         | Every new lane or shared surface needs primary and backup owner.                  |
| `docs/reference/quality-gates.md`                                   | L9/L8              | Gate language must match CI and local validation commands.                           | Update together with command evidence or CI workflow changes.                     |
| `docs/reference/tools.md`                                           | L5/L9              | Generated from command registry; manual edits drift quickly.                         | Regenerate through `polisyos-tools docs`.                                         |
| `docs/reference/schemas.md`, `docs/reference/ir/schema-catalog.md`  | L4/L9              | Generated/reference schema surfaces are currently out of date.                       | Regenerate or record drift; do not hand-edit generated schema truth.              |
| `schemas/**`, `docs/reference/api/**`, frontend runtime client docs | L1/L7/L9           | OpenAPI and generated client drift impacts runtime consumers.                        | Treat contract generation and docs update as one coordinated change.              |
| root-level `docs/*_PLAN.md`                                         | L0                 | Published-looking plans can conflict with current source-of-truth docs.              | Keep status in this ledger; archive/supersede through L0 when closed.             |
| `.github/workflows/**` and workflow references                      | L8/L9              | Docs accuracy checks validate workflow names.                                        | Update workflow docs and checks together.                                         |
| `README.md` and subsystem `README.md` files                         | owning lane + L0   | Entry points are read before reference docs and can contradict lane pages.           | Refresh after D1 source-of-truth mapping, not during D0.                          |

## Historical D1 Status Snapshot

Audit date: 2026-04-17

This snapshot checks the concrete D1 exit criteria from
`docs/plans/active/DOCUMENTATION_SOTA_PLAN.md` against the current repository state.

### Required Output Coverage

All required D1 output files currently exist.

| Lane                   | Required outputs present                                                  | Evidence anchor                                                                                                            | Status                    |
| ---------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| L1 Core/Common/Runtime | 19/19                                                                     | `docs/reference/api/**`, `docs/reference/operations/**`, security/runbooks, `src/polisyos/{common,core,runtime}/README.md` | complete on file coverage |
| L2 Fabric              | 15/15                                                                     | `docs/reference/fabric/**`, Fabric how-to/runbooks, `src/polisyos/fabric/**/README.md`                                     | complete on file coverage |
| L3 Foundry             | 16/16                                                                     | `docs/reference/foundry/**`, benchmark/how-to pages, `src/polisyos/foundry/**/README.md`                                   | complete on file coverage |
| L4 IR                  | 18/18 plus `docs/contracts/E1_*.md` and `docs/contracts/E2_*.md` families | `docs/reference/ir/**`, shared reference pages, IR package READMEs, contract set                                           | complete on file coverage |
| L5 Tools               | 12/12                                                                     | `docs/reference/tools.md`, tooling READMEs, CI/release/how-to pages                                                        | complete on file coverage |
| L6 Scientist           | 17/17                                                                     | `docs/reference/scientist/**`, Scientist how-to/tutorial pages, `src/polisyos/scientist/**/README.md`                      | complete on file coverage |

Total required file coverage: `97/97`.

### Lane Closure Readiness

| Lane                   | Source-of-truth map | Validation command/test linkage | Missing-page backlog discipline | Verdict                                                                                                                                            |
| ---------------------- | ------------------- | ------------------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| L1 Core/Common/Runtime | present             | present                         | present                         | `docs/reference/api/index.md` now provides the lane-level D1-L1 source map, exact outputs, validation anchors, and explicit no-gap backlog status. |
| L2 Fabric              | present             | present                         | present                         | `docs/reference/fabric/index.md` now carries exact-file impact coverage plus explicit D1/no-gap backlog tracking.                                  |
| L3 Foundry             | present             | present                         | present                         | `docs/reference/foundry/index.md` now combines phase mapping, exact outputs, validation commands, and explicit backlog status.                     |
| L4 IR                  | present             | present                         | present                         | `docs/reference/ir/index.md` now lists exact D1 outputs, source-of-truth surfaces, validation anchors, and backlog status.                         |
| L5 Tools               | present             | present                         | present                         | The generated tools reference and tooling READMEs now cover exact D1 outputs, validation contract, and explicit backlog/no-gap status.             |
| L6 Scientist           | present             | present                         | present                         | `docs/reference/scientist/index.md` already carried the strongest D1 closure structure and now includes the exact file set too.                    |

### Exit-Criteria Check

| D1 exit criterion                                                 | Status   | Evidence                                                                                                                                                                              |
| ----------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Each source remediation plan has a docs impact table              | complete | All six canonical remediation plans now carry a `## D1 Docs Impact Table` section with exact-file coverage, source-of-truth surfaces, validation commands, and backlog/no-gap status. |
| Each lane has exact files, source of truth and validation command | complete | L1-L6 lane reference pages list the exact D1 outputs, source-of-truth surfaces, and validation anchors.                                                                               |
| Missing pages are recorded as backlog with priority               | complete | Required D1 pages are all present. Lane pages and remediation plans now record explicit `none` status for required gaps and keep optional D2 follow-ups prioritized.                  |

### Historical Audit Notes

- 2026-05-15: Honest Diagnostics Phase 6.5 added the operator-facing triage
  runbook for runtime ref, diagnostic event, source-truth, adapter, mode,
  fallback, phase-barrier, projection, semantic binding, tenant, stale evidence,
  attestation, and partial-state failures. The design decision and accepted ADR
  set were reviewed for this documentation pass; no decision supersession was
  required.
- 2026-05-23: Universal Policy Design Case W5.E added
  `docs/reference/policy-design-case-operator-guide.md` and
  `docs/runbooks/policy-design-case-rollout-rollback.md` as the durable
  operator routes for ADR lookup, system-design decision indexes, public
  evidence paths, tuned-parameter owners, validation ladders, capability
  evidence, and rollout/rollback procedures.
- 2026-05-13: Production-quality Phase 6.2 documents the cross-lane impact of
  runtime quality, Fabric source-selection audit, compliance, frontend
  operator dashboard, provider-quality, replay, resilience, approval, reissue,
  and withdrawal changes. Operator evidence now lives in
  `docs/runbooks/production-quality-canary.md`,
  `docs/runbooks/production-quality-triage.md`, and
  `docs/reference/runtime/production-quality-approval.md`; generated command
  coverage is refreshed in `docs/reference/tools.md`.
- 2026-04-28: Fabric Phase 7 touched public package facades under
  `src/polisyos/fabric/{security,world}` and regenerated the runtime client for
  temporal capability fields. The impact is covered by
  `docs/reference/fabric/time-travel.md`,
  `docs/reference/fabric/best-in-class-inventory.md`, and
  `docs/reference/generated-artifacts.md`.
- 2026-04-28: Fabric Phase 8 added processing guarantee contracts under
  `src/polisyos/fabric/processing_guarantees.py`, surfaced them in
  SourceContract v2 snapshots, and documented runtime semantics in
  `docs/reference/fabric/processing-guarantees.md`.
- `python3 tools/quality/validation/check_docs_accuracy.py --repo-root .` was rerun on
  2026-04-17 during this audit after fixing Scientist workflow path references.

- D1 formal closure is now recorded directly in lane reference pages and in the
  six canonical remediation plans.

## Historical D5 Status Snapshot

Audit date: 2026-04-17

At the time recorded, this snapshot checked the D5 acceptance criteria from
`docs/plans/active/DOCUMENTATION_SOTA_PLAN.md` against the then-current published
documentation surface.

### Architecture Explanation Coverage

| Package                     | Required docs                                                             | Status   | Evidence                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| System context              | `docs/explanation/architecture.md`, `docs/index.md` diagram               | complete | Both pages link operations diagrams, ADRs, contracts, generated artifacts, and platform acceptance evidence.             |
| Contract architecture       | `docs/explanation/trinity.md`, `docs/explanation/ir-design.md`, contracts | complete | Trinity and IR pages link TRINITY, merge semantics, E1/E2 contracts, IR references, and ADR-0104 through ADR-0109.       |
| Runtime platform            | `docs/explanation/security-model.md`, API reference, operations docs      | complete | Security model links auth/tenant, error semantics, security compliance, runtime runbooks, and ADR-0097 through ADR-0102. |
| Data architecture           | `docs/explanation/data-fabric.md`, Fabric reference                       | complete | Data Fabric links Fabric references, contracts, schema/lineage evidence, and Fabric runbooks.                            |
| Scientific architecture     | `docs/explanation/causal-engine.md`, Scientist/Foundry references         | complete | Causal engine links Foundry, Scientist, contracts, ADRs, benchmark triage, and non-default frontier acceptance pages.    |
| Legal/NormPack architecture | `docs/explanation/lex-pipeline.md`, Lex references                        | complete | Lex pipeline links Lex references, E2.8/E2.9/E2.10 contracts, ADRs, and Lex test evidence.                               |
| Governance architecture     | `docs/explanation/governance-model.md`, governance pass refs              | complete | Governance model links Scientist governance references, ADRs, workflow/governance tests, and non-default rollout pages.  |
| Observation contracts       | `docs/explanation/observation-contracts.md`, IR observation refs          | complete | Observation contracts link IR observation, Fabric quality, Scientist causal validity, ADRs, and observation tests.       |
| Freeze/ratchet model        | `docs/explanation/freeze-policy.md`, ratchet/merge governance             | complete | Freeze policy links quality gates, ratchet policy, ADRs, import policy, and docs/architecture gate commands.             |

### Diagram Coverage

| Required diagram                             | Current location                                                                                                                                             | Status   |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| System context                               | `docs/index.md#system-context`                                                                                                                               | complete |
| Container view                               | `docs/explanation/architecture.md#container-view`; `docs/reference/operations/platform-architecture-diagrams.md#c4-container-view`                           | complete |
| Runtime HTTP request flow                    | `docs/reference/operations/platform-architecture-diagrams.md#runtime-http-request-flow`; `docs/explanation/security-model.md#auth-and-request-flow`          | complete |
| Auth/tenant isolation flow                   | `docs/reference/operations/platform-architecture-diagrams.md#auth-and-tenant-isolation-flow`; `docs/explanation/security-model.md#auth-and-tenant-isolation` | complete |
| CAS/artifact lifecycle                       | `docs/reference/operations/platform-architecture-diagrams.md#cas-signing-and-integrity-flow`                                                                 | complete |
| Generated artifact lifecycle                 | `docs/explanation/architecture.md#generated-artifact-lifecycle`                                                                                              | complete |
| Fabric connector ingestion flow              | `docs/explanation/data-fabric.md#connector-ingestion-flow`                                                                                                   | complete |
| Fabric lineage and schema compatibility flow | `docs/explanation/data-fabric.md#lineage-and-schema-compatibility-flow`                                                                                      | complete |
| Foundry compile/execute flow                 | `docs/explanation/causal-engine.md#foundry-compile-and-execute-flow`                                                                                         | complete |
| IR schema evolution flow                     | `docs/explanation/ir-design.md#schema-evolution-flow`                                                                                                        | complete |
| Scientist workflow execution flow            | `docs/explanation/governance-model.md#scientist-workflow-execution-flow`                                                                                     | complete |
| Scientist governance artifact flow           | `docs/explanation/governance-model.md#governance-artifact-flow`                                                                                              | complete |
| CI/docs quality gate flow                    | `docs/explanation/freeze-policy.md#ci-and-docs-quality-gate-flow`                                                                                            | complete |

### Runbook And Compliance Coverage

| Package                       | Required scope                                                                                 | Status   | Evidence                                                                                                                                        |
| ----------------------------- | ---------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime incidents             | runtime outage, stuck worker, idempotency, CAS/OPA runbooks                                    | complete | `docs/runbooks/runtime-api-outage.md`, `runtime-graceful-shutdown-and-stuck-worker.md`, `idempotency-incident.md`, `cas-opa-outage.md`.         |
| Artifact and schema incidents | artifact corruption, signing/SBOM, broken contract generation, retained artifact recovery      | complete | `artifact-corruption-recovery.md`, `artifact-signing-sbom-failure.md`, `broken-contract-generation.md`, `retained-artifact-recovery.md`.        |
| Fabric incidents              | cache rebuild storm, connector quarantine/DLQ, data-plane recovery                             | complete | `cache-rebuild-storm.md` plus `fabric-quarantine-dlq-and-data-plane-recovery.md`.                                                               |
| Release and CI                | dependency upgrade regression, docs publication failure, canary rollback, benchmark regression | complete | `dependency-upgrade-regression.md`, `docs-publication-failure.md`, `canary-rollback-or-promotion-failure.md`, `benchmark-regression-triage.md`. |
| Security/compliance           | key rotation, security compliance ref, FedRAMP gap, evidence map                               | complete | `key-rotation.md`, `docs/reference/security-compliance.md`, `docs/fedramp/gap-analysis.md`, `docs/reference/compliance-evidence-map.md`.        |

### D5 Acceptance Check

| Acceptance criterion                                                        | Status   | Notes                                                                                                                                                                                                                                                                          |
| --------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| All explanation pages link back to ADRs, contracts, or reference docs       | complete | Every file under `docs/explanation/*.md` has an ADR, contract, reference, or evidence backlink.                                                                                                                                                                                |
| Every runbook has owner, last-tested date, evidence path, and rollback path | complete | All published runbook pages, including the runbook index, declare the required metadata.                                                                                                                                                                                       |
| SOTA claims are evidence-backed or clearly marked as future work            | complete | Published explanation and runbook surfaces use evidence lines, ADR/contract links, generated-reference commands, or explicit non-default/future-state notes. ADRs are treated as evidence records; generated references are governed by their canonical regeneration commands. |

## Historical D6 Status Snapshot

Audit date: 2026-04-17

| D6 criterion                                    | Status                        | Evidence                                                                                                                                                                                                     |
| ----------------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Local docs gate has one documented command      | complete                      | `uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main` is documented in [Quality Gates](quality-gates.md).                                                                  |
| CI fails on docs drift with actionable messages | complete                      | Repository-root `.github/workflows/abi.yml` runs `check-docs-gate` in the `Fast PR / Docs quality` job for pull requests and pushes.                                                                         |
| Published nav excludes closed/planning docs     | complete                      | `mkdocs.yml` excludes active planning/remediation docs and `check-docs-accuracy` blocks planning docs in published nav.                                                                                      |
| Generated references are current                | complete                      | Tools, public-surface/generated-artifacts, schema, Runtime API, and frontend contract checks are part of `check-docs-gate`.                                                                                  |
| Semantic public-surface docstrings pass         | complete                      | Global public-surface docstring check passes with `0` placeholder violations.                                                                                                                                |
| Import-policy baseline is known                 | complete                      | `ukraine_data` is now in `architecture/imports/policy.toml`; newly exposed crossings are recorded in `architecture/imports/exceptions.toml` and `architecture/imports/exceptions.md` with 2026-07-01 expiry. |
| Broader local CI parity status is explicit      | blocked outside docs closeout | `ci-parity --skip-browser` reaches backend pytest after all docs/contract/import/state-read layers pass, then fails on the existing broad backend test suite (`186 failed`, `8895 passed`).                  |

## Historical Publication Readiness Notes

- D1-D6 documentation closeout is complete on the published docs surface and
  the dedicated docs/contract/import/state-read gates listed above pass.

- Any new stale claims or cross-lane conflicts should be added to this page
  before rewriting another lane's technical content without owner review.

- Import exceptions added during this closeout expire on 2026-07-01 and should
  be retired through facade extraction or boundary cleanup, not renewed by
  default.

- The broad `ci-parity --skip-browser` backend pytest failures remain outside
  the documentation closeout and need a separate backend stabilization pass
  before the full local CI parity command can be marked green.

## Delivered documentation delta at d015c0f (2026-10-14)

This source-only comparison preserves the pinned-baseline census above and adds
the delivered documentation tree at `d015c0f06dbc32671b000f7f61e92badbcb9859f`.
It compares that frozen commit with baseline
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; it does not recast historical D0-D6
notes as current evidence.

The complete `policy-engine/docs/` Git tree increased from 14,817 to 14,832
tracked blob paths, with Markdown increasing from 2,791 to 2,806. The pinned
diff has 68 modified and 15 added Markdown files, with no deletions; all other
suffix counts are unchanged. The complete tree-listing SHA-256 values are
`4d6f13e3e2230a8b464f76887c9e43fe1793b625580fe9f949b96ff0b9886bf2` at the
baseline and `2dd276bf3a65b19d8cfd45c096207616e77dd09ec86ba67adae839a3618bd420`
at the freeze.

The publishing-input denominator is 20 tracked blobs at both refs: root
`mkdocs.yml`, all files under `architecture/tooling/mkdocs/`,
`architecture/tooling/tool_config_split.toml`, the Markdown lint config and
Python docs dependency declaration, and the docs publication/verification
workflow files. Four files changed: `architecture/tooling/mkdocs/generated.yml`,
`architecture/tooling/mkdocs/nav/30-reference.yml`,
`architecture/tooling/mkdocs/nav/40-explanation.yml`, and
`architecture/tooling/mkdocs/not_in_nav.yml`.

Static parsing of the frozen generated MkDocs config joined against all 2,806
tracked Markdown paths finds 371 unique navigation targets, all present; 27
`exclude_docs` patterns match 422 paths; 122 declared `not_in_nav` patterns
match 122 paths; and 1,891 paths remain outside those three classes. There are
no overlaps, and the four classes sum to 2,806. This is YAML and path matching
under the documented `fnmatchcase` approximation, not effective MkDocs
selection or rendered navigation verification.

For the named code-tree scope (`policy-engine/src/`, `policy-engine/tests/`,
`policy-engine/tools/`, `policy-engine/apps/`, `policy-engine/ops/`,
`policy-engine/scripts/`, and repository-root `src/`, `tests/`, `tools/`,
`apps/`, `packages/`, `services/`, and `scripts/`), both refs contain 8,671
tracked blobs and the diff is empty. The named E02 source corpus
(`docs/research/e02-cloud-test-plan/`, the E02 agent-package tree, and
`docs/research/development-programs/2026-09-30-post-e02/`) contains 11,212 blobs
at both refs, also with an empty diff. The new
[`e02-documentation-snapshot.md`](e02-documentation-snapshot.md) is a handbook
page outside those source-corpus paths. Across the full repository, the 87
changed paths are exactly 83 Markdown changes plus the four publishing-input
changes above; no product-code or E02-corpus path changed.

Three archived plan copies are byte-identical to their baseline source blobs;
each active source now mentions its archive destination. SHA-256 was computed
from each complete blob at the two refs:

- Active Data Forge cutover pointer: `policy-engine/docs/plans/active/DATA_FORGE_CUTOVER_READINESS.md`;
  archived copy: `policy-engine/docs/plans/archive/DATA_FORGE_CUTOVER_READINESS.md`,
  `ee575769c2b1cd62eafe7a062cbdf560cc0e956ac7072b8a6bbfa7e1837d7ed6`.
- Active documentation SOTA pointer: `policy-engine/docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`;
  archived copy: `policy-engine/docs/plans/archive/DOCUMENTATION_SOTA_PLAN.md`,
  `f4bc50595101d2490f498429eb92d25a7425c22997b6e702fc34882f65cd1d1c`.
- Active G5 slice pointer: `policy-engine/docs/plans/active/layer3-slices/G5-first-proving-ground-conversion.md`;
  archived copy: `policy-engine/docs/plans/archive/G5-first-proving-ground-conversion.md`,
  `7b0ed5e4cf517809b5f1a948e13e32eddce6fc2fe8cb4d7d113aefcf500a51cf`.

Reproduction script: `policy-engine/_build/docs-refresh/raw/delivered-delta.py`
(SHA-256 `e1f11ba62601f9b9a13962b99941bdeb03106188e66fc8ee5e6d01314e7ec997`).
Its compact local JSON receipt is
`policy-engine/_build/docs-refresh/raw/delivered-delta.json` (SHA-256
`1d9e19b120c78cbf18aace2e34c885eca388edbbab5dbfdda92760658628ca90`). Both
are ignored local evidence; the complete tracked path sets remain reproducible
from the two Git refs.

These counts and archive comparisons are source-only. No MkDocs build, link or
accuracy check, documentation publication, runbook rehearsal, runtime command,
or semantic content review was run against the freeze. The current docs
pipeline, page freshness, and documented runtime behavior therefore remain
unverified by this comparison. The measurement remains pinned to the two refs
above; companion or correction commits after `d015c0f06dbc32671b000f7f61e92badbcb9859f`
are not included.
