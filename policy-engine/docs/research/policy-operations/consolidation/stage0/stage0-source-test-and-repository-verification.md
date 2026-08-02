---
title: Stage-0 Source, Test, and Repository Verification
status: draft_consolidation
kind: research-synthesis
research_scope:
  - PAO-R0
  - PAO-R1
  - OPS-R15
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
ops_r15_audit_commit: 42a79a655974b37e28a89d31b5f72ffea83927f4
consolidation_date: 2026-07-28
consolidation_branch: research/stage0-anchor-consolidation
authoritative_for:
  - cross-audit synthesis at recorded commits
  - proposed Stage-0 research amendments
  - candidate additional-research sequencing
may_not_use_for:
  - production capability claim
  - final code contract
  - canonical owner assignment
  - authority grant
  - legal compliance conclusion
  - implementation authorization
  - production benchmark passage
  - production RPO or RTO commitment
  - automatic amendment of authoritative backlogs or decisions
research_only: true
---

# Stage-0 Source, Test, and Repository Verification

## Exact refs and source inventory

| Item | Verification | Result |
|---|---|---|
| Current remote `main` | `git rev-parse origin/main` plus remote commit lookup | `4813b49f6ce14e8debf3aaea096f0967d38d9768` |
| Historical baseline | `git show -s --format=%H 4813b49...` | Same full SHA |
| Baseline delta | `git diff --quiet 4813b49... origin/main` | No changed files |
| PAO-R0 audit ref | fetched exact branch, `git show -s --format=%H` | `258aa740efcfb9e6771bfe52d4fdabc6b74f93a7` |
| PAO-R1 audit ref | same | `566840c330e867a15313923c87c20b6863cb053f` |
| OPS-R15 audit ref | same | `42a79a655974b37e28a89d31b5f72ffea83927f4` |
| Audit artifacts | `git show <audit-sha>:<path>` | 17/17 expected files read |
| Audit normalization | Temporary parser over exact files | 5,962 lines, 143 Markdown tables, 1,706 table rows |
| Original PAO-R0 | Repository/branch census | Unavailable; no source hash |
| Original PAO-R1 | Repository/branch census | Unavailable; no source hash |
| Original OPS-R15 | Audit normalization record | 2,672 lines; SHA-256 `0c3baf41df8ae02bd9f9ae88cc9f1a350d7f4e33021a94327c3e578044690d15` |

## Audit artifact hashes

These hashes identify the exact source material read by the synthesis:

| Audit file | SHA-256 |
|---|---|
| PAO-R0 `pao-r0-independent-audit.md` | `231656dcef46efca64fdf1d18a79e44201bb77744850f74638aafaf630966557` |
| PAO-R0 `pao-r0-claim-evidence-ledger.md` | `9d395157bf7eab96b1a6f67f93ab1ca07d3180c0c4fad1ca3f4aac4e9a052b26` |
| PAO-R0 `pao-r0-recommended-revision.md` | `e76af0bfeeef43bda72f2d6f1291c892dbb096be7f8e14b84ff08a9b230c6390` |
| PAO-R0 `pao-r0-test-and-fixture-verification.md` | `a270341adb50ebc3b4774c10af28d95c2fde8d7500a7aa4d7597bc0aff008c67` |
| PAO-R1 `pao-r1-independent-audit.md` | `2ae1b38d8d764bb0bc130e3bdf82304b4e8ee4b596697a7c8af4d63f3bcc15af` |
| PAO-R1 `pao-r1-register-row-audit-ledger.md` | `7be50648b1324958910125a48515d72c3c804b31cbafad31d2fa8456c7f8b708` |
| PAO-R1 `pao-r1-evidence-contract-audit.md` | `1b924647d7a0d1088213da3cf6807fdfeaaf6d9236c5c31d8cd7f17518fdd4a2` |
| PAO-R1 `pao-r1-contradiction-and-consistency-ledger.md` | `1e5e29ca2511c00e04ca7c875818b2f62f3e2114daea7925eb4641aee660a0c0` |
| PAO-R1 `pao-r1-recommended-revision.md` | `a5a0806ff857211fd1a7f097dfb2660b7abd3e6cc676fe1e6286709b89dcf5a0` |
| PAO-R1 `pao-r1-test-and-fixture-verification.md` | `63bd34b93502a677c940e798fe85d53042795ed56055d3f4a9e0bb6b50418aff` |
| OPS-R15 `ops-r15-independent-audit.md` | `7abd085262468ba973ca612edda6def06e613fc9c97edf9657949b13c0777aff` |
| OPS-R15 `ops-r15-calendar-event-audit-ledger.md` | `18b5bbdc1ae51219a5e29a984226c060f06199d5faa0e6337409812d511f9929` |
| OPS-R15 `ops-r15-metric-and-oracle-audit.md` | `bd4a16cee95f2765de9d9cbc3945ab010aeac4fa3935d0be77ea8b636632194b` |
| OPS-R15 `ops-r15-state-contract-and-owner-audit.md` | `6785b69e76bad1206810da608de6bd3fb855cf60f7b783b10be24698a776153e` |
| OPS-R15 `ops-r15-stage0-kernel-and-extension-packs.md` | `e12c301d11b1635268bc20e5d05bb5bb84c50373545f348c2befa731a7ae0f3a` |
| OPS-R15 `ops-r15-recommended-revision.md` | `0d18449bdfd57a145f644546fc213d63cd036531e82bfeabe999fc2f0ae3fa75` |
| OPS-R15 `ops-r15-test-and-probe-verification.md` | `d25f2286ff462756938513cda5873a77a8d19e2043cffa2dbc1dac09c37c0bcf` |

## Audit-of-audits critical/high ledger

Thirty-one critical/high audit findings were reviewed. “Duplicate” means the
finding is correct but shares a root already evidenced elsewhere; it does not
mean unimportant.

| Audit finding | Severity | Atomic claim | Exact independent evidence | Inference/recommendation check | Overlap | Classification | Consolidated disposition |
|---|---|---|---|---|---|---|---|
| R0-F01 | Critical | “Immediately binding” exceeds research standing | Source standing quoted in audit; W2 calls freeze a research guard | Acceptance principal is a governance decision | R1-H05 | `independently_confirmed` | Replace binding language |
| R0-F02 | Critical | `support_status` creates parallel lattice/envelope | One-lattice decision; existing authority/lifecycle/support owners | Exact mapping remains owner work | R1-H02/H03, O15-H08 | `confirmed_but_duplicate` | Reject common state/envelope |
| R0-F03 | High | PDC canonical owner not established | PDC README limits authority to graph structure; no matter type | Which owner wins requires decision | R1-H06 | `requires_team_architecture_decision` | S0-GAP-01 |
| R0-F04 | High | Nine clocks pre-empt OPS-R4 | W2 OPS-R4 remit; distributed current clock names | Minimum role split survives | R1-H04, O15 temporal | `confirmed_but_duplicate` | Defer algebra to OPS-R4 |
| R0-F05 | High | Failure-pattern IDs shifted | Exact pattern register read at both identical baselines | None | R1-H09/O15 detected status | `independently_confirmed` | Correct all mappings |
| R0-F06 | High | Named fixtures are literals/tests, not corpus | Exact test symbols and tracked-tree search | Tests remain useful patterns | O15 corpus standing | `independently_confirmed` | Relabel |
| R0-F07 | High | Tenant/namespace assumptions unproven; lineage store tenant-blind | `_lineage_path` hashes raw key; current contract fields | Exploitability not claimed | O15-H03 | `independently_confirmed` | Separate defect; keep identity question open |
| R0-F08 | High | Public export redaction is not green | Exact failing test and builder path recorded; static path re-read | Owner-supported rerun still desirable | O15 public profile | `independently_confirmed` | Repository fix separate |
| R0-F09 | High | Atlas doctrine is not complete current-state description | Active plan debt; `publicSectorReadiness.ts` computes `approvalReady` | “Minting” is semantic interpretation backed by plan | R1 capability/public findings | `independently_confirmed` | Renderer role plus defect |
| R0-F10 | High | Lex-only owner wording is wrong | Public/package policy and code: Data Forge batch vs Lex runtime | None | R1/O15 legal chains | `independently_confirmed` | Correct chain |
| R0-F11 | High | Sidecar correction sufficiency unproven | Signing binds bytes; no matter-aware public correction chain | Sidecar may still be valid future design | R1/O15 correction | `confirmed_with_narrower_scope` | Preserve non-rewrite only |
| R1-H01 | Critical | External acts are labelled I with their evidence | ID §5 and ADR-0170; row audit contains mixed acts | Linked planes need not be stored as two rows | O15-H05 | `independently_confirmed` | Ratify plane separation |
| R1-H02 | Critical | Multiple unmapped state systems contradict one lattice | One-lattice decision and current family owners | Report-local labels may remain | R0-F02/O15-H08 | `confirmed_but_duplicate` | Remove runtime implication |
| R1-H03 | High | Institutional envelope duplicates/mixes owners | Fabric/RQ/PDC/provenance/audit/lifecycle contract census | “Compose by reference” is architecture guidance | R0-F02/O15 envelope | `confirmed_with_narrower_scope` | Reject freeze; retain composition guidance |
| R1-H04 | High | Ten/five clocks pre-empt OPS-R4 | W2 OPS-R4 and current naming conflicts | None | R0-F04/O15 temporal | `confirmed_but_duplicate` | Defer |
| R1-H05 | High | Stage-0/cadence/freeze/challenge/task decisions overclaim authority | Frontmatter/W2 standing | Exact governance process needs decision | R0-F01 | `confirmed_but_duplicate` | Recast as proposals |
| R1-H06 | High | PDC/RQ owners unproven | PDC/RQ READMEs; absence of generic bridge | Future owner selection open | R0-F03 | `confirmed_but_duplicate` | Conservative owner map |
| R1-H07 | High | “Most owners exist” overstates capability | Complete chain census; ADR-0170 and Atlas plan limitations | None | R0 capability/O15 fragments | `independently_confirmed` | Normalize chain states |
| R1-H08 | High | Undefined owner/capability aliases and future tasks used as owners | Exact symbol search and Appendix-C legend | Analytical role model is useful | R0 owner/O15 H2 | `confirmed_but_duplicate` | Separate roles/capability |
| R1-H09 | High | Pattern IDs wrong; M31 is not pattern | Failure register and distillation | None | R0-F05 | `confirmed_but_duplicate` | Correct |
| R1-H10 | High | Claimed Rev-1 source unavailable | `git log --all --follow`; parent lacks backlog | Finding is reproducible even though source is not | None | `independently_confirmed` | Remove historical claim |
| O15-H01 | Critical | Semantic oracle is self-authored/visible | Source normalization: expectations co-located; no oracle files | Independence design still needed | R0/R1 fixture standing | `independently_confirmed` | S0-GAP-02 |
| O15-H02 | Critical | Same-code rebuild is circular | Temporary injected-fault reducer; no independent-code requirement | Independent evaluator shape is future research | None | `independently_confirmed` | S0-GAP-02 |
| O15-H03 | Critical | Current checkpoint/control composition lacks custody binding | `CheckpointMetadata`, control-job SQL, diagnostics fields | Not proof of exploitable production flow | R0-F07 | `independently_confirmed` | Defect/prerequisite |
| O15-H04 | Critical | Unknown jurisdiction falls back to Ukraine | Registry `_REGISTRY.get(..., UkrainianJurisdiction)` | Applicability consequence depends on consumer | R1 jurisdiction | `independently_confirmed` | Repository fix/OPS-R11 |
| O15-H05 | Critical | External acts/evidence mixed in calendar | 16 ledger rows; ID §5 | Same root as R1-H01 | R1-H01 | `confirmed_but_duplicate` | Split fixtures |
| O15-H06 | High | Calendar vocabulary does not normalize | 117 calendar names, 92 dictionary names, 87/62 mismatch | Literal mismatch may overstate semantic family count | None | `independently_confirmed` | Rebuild machine corpus |
| O15-H07 | High | Twenty universal gates are overbroad chokepoint | Gate audit: public/budget/impact checks have different phases/conditions | Correct phase design requires OPS-R1/3 | None | `reasonable_architecture_inference` | Equivalent protection |
| O15-H08 | High | State/envelope gravity duplicates owners | One-lattice/OPS-R4/R8/PAO-R36 ownership | Same root as PAO findings | R0-F02/R1-H02/H03 | `confirmed_but_duplicate` | Predicates/extensions |
| O15-H09 | High | Numerical thresholds lack basis | Metric ledger; no closed denominators or repository/pilot source | Metrics may gain justified thresholds later | None | `confirmed_with_narrower_scope` | Demote/remove Stage-0 values |
| O15-H10 | High | “Detected” overclaims unexecuted fixtures | No runner/fixture symbols; source labels proposed cases | Pattern concepts mostly remain useful | R0/R1 fixture claims | `independently_confirmed` | Say proposed/untested |

### Audit-of-audits counts

| Classification | Count |
|---|---:|
| `independently_confirmed` | 19 |
| `confirmed_but_duplicate` | 7 |
| `confirmed_with_narrower_scope` | 3 |
| `reasonable_architecture_inference` | 1 |
| `requires_team_architecture_decision` | 1 |

No critical/high finding became stale or was contradicted by current `main`.

## Repository evidence rechecked

| Claim | Exact path/symbol | Historical verdict | Current verdict | What it proves | What it does not prove |
|---|---|---|---|---|---|
| Four-way test and anti-roles | `docs/system-design-decisions/policyos-identity-and-custody-boundary.md` §§5–6 | Confirmed | Confirmed | Governing semantic boundary | Runtime implementation |
| One authority/status grammar | universal vision and target architecture D3.7 | Confirmed | Confirmed | No parallel canonical lattice | Every family uses identical enum |
| PDC graph authority is narrow | `src/polisyos/pdc/README.md`; graph contracts | Confirmed | Confirmed | Graph structure owner | Matter/claim/public owner |
| RQ cannot mint producer authority | `src/polisyos/runtime/quality/README.md` | Confirmed | Confirmed | Admission/validation boundary | Generic institutional bridge |
| Authority meet behavior | `pdc/_impl/layer2_readiness.py::AuthorityBoundary.meet` | Confirmed | Confirmed | Allowed intersection, denied union, weakening | Legal/family payload completeness |
| PolicyMatter/register/world/H2 absent | Exact tracked `src`/`tests` name and semantic-owner census | Confirmed | Confirmed | No named typed capability | External/untracked services |
| Checkpoint binding incomplete | `scientist/orchestration/engine/checkpoint.py::CheckpointMetadata` | Confirmed | Confirmed | No tenant/cell/authority field | All surrounding invocation context |
| Control-job binding incomplete | `runtime/http/services/control_plane_store.py` schema | Confirmed | Confirmed | No tenant/cell column | Future migrations/external stores |
| Lineage persistence tenant-blind | `scientist/validation/decision_validity.py::_lineage_path` | Confirmed | Confirmed | Raw key determines local path | Remote deployment isolation |
| Unknown jurisdiction defaults UA | `data_forge/.../jurisdictions/__init__.py::get_jurisdiction` | Confirmed | Confirmed | Current fallback behavior | Every downstream authorization path |
| Public export redaction gap | `runtime/quality/public_export.py::build_public_export_bundle`; named test | Red at audit | Same code | Intended property not implemented in path | Cross-tenant read exploit |
| Atlas local readiness | `apps/runtime-dashboard/.../publicSectorReadiness.ts` | Confirmed | Confirmed | Renderer computes `approvalReady` | Every Atlas surface mints authority |
| Data Forge→Lex split | package READMEs/public-surface policy and code | Confirmed | Confirmed | Producer/runtime roles | Continuous legal capability completeness |
| Audit package≠opinion | `core/audit/README.md` and external-audit contracts | Confirmed | Confirmed | Package/integrity scope | Independent institutional audit |
| Authorization allow≠success | access-audit contract/docstring | Confirmed | Confirmed | Admission semantics | Handler/external execution |

## Commands executed during consolidation

All commands below ran in the isolated consolidation worktree at
`4813b49f6ce14e8debf3aaea096f0967d38d9768`.

| Command | Result | Audit implication |
|---|---|---|
| `git rev-parse origin/main; git diff --quiet 4813b49... origin/main` | Same SHA; no delta | Historical/current facts identical |
| Exact `git show <audit-sha>:<file>` for 17 files | Completed | Audit inputs pinned, not branch-tip drift |
| Temporary Markdown/YAML/table normalizer | 17 files, 5,962 lines, 143 tables, 1,706 rows | Mechanical synthesis corpus; no semantic proof |
| `python3 -m tools.cli workspace bootstrap` | Failed: `ModuleNotFoundError: click` | System environment not bootstrapped |
| `python3 -m tools.cli workspace doctor` | Failed for same reason | No system-doctor pass |
| `/tmp/stage0-consolidation-testenv/bin/python -m tools.cli workspace doctor` | 9 failures: Python 3.12 vs 3.14, Node 24 vs 22, uv 0.11 vs 0.9, browser absent, read-only caches, lock/generated checks blocked | Environmental limitation; not semantic anchor failure |
| Targeted PDC/reissue/core-audit tests | **20 passed** | Narrow verifier-only, partial-reissue, and audit-package behaviors; no end-to-end anchors |
| Fabric `SourceContract` v2 tests | **12 passed** | Data-source contract validation; not universal institutional evidence |
| Docs gate/lifecycle tests | **31 passed, 2 failed** | Baseline Atlas path and expired freshness debt; new directory not identified as cause |
| Same docs tests in a temporary clean detached worktree at `4813b49...` | **31 passed, same 2 failed with identical findings** | Completed isolation proves the failures pre-exist the consolidation |
| `git diff --check` | Passed | No whitespace errors |

The targeted commands were:

```text
PYTHONPATH=src:. /tmp/stage0-consolidation-testenv/bin/pytest \
  -o addopts='' -q \
  tests/unit/pdc/test_gy_waist_contracts.py \
  tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py \
  tests/unit/core/phase0/test_audit_export_verify.py
```

```text
PYTHONPATH=src:. /tmp/stage0-consolidation-testenv/bin/pytest \
  -o addopts='' -q \
  tests/unit/fabric/connectors/test_source_contract_v2.py
```

```text
PYTHONPATH=src:. /tmp/stage0-consolidation-testenv/bin/pytest \
  -o addopts='' -q \
  tests/repo_quality/tools/test_docs_gate.py \
  tests/repo_quality/tools/test_docs_lifecycle.py
```

The temporary Python 3.12 environment and downloaded dependencies are not
committed. Passing tests are local contract evidence only.

## Inherited audit test evidence

Because all audits and current main inspect the same tree, their exact dynamic
results remain relevant but were not all rerun:

| Audit | Selected results relied upon | Limitation |
|---|---|---|
| PAO-R0 | PDC compiler 4 pass; projection 37 pass; targeted batch 54 pass/1 redaction failure; PDC 122 pass/1 shim failure; DDM 4 pass; signing/audit 3 pass | Temporary Python 3.14 environment with import shim; runtime HTTP blocked |
| PAO-R1 | PDC waist 11 pass; Fabric 12; Lex 29; DDM 6; audit 10; security/access 15; contestability 22; reissue 3; broader docs/fabric 33 pass/2 baseline failures | Missing full repository toolchain and partner systems |
| OPS-R15 | Control store 16; checkpoint 40/1 unsupported; Fabric temporal 34; legal 15; lifecycle/CAS/signing/audit 41; docs 17/2 baseline; broad 36/51 environment/pre-existing | Python 3.12 vs required 3.14; no browser/topology/oracle |

No green unit suite proves PolicyMatter, a boundary register, H2, an independent
oracle, production recovery, external competence, or public cross-surface
parity.

## Failure-pattern reconciliation

Historical and current definitions are identical. This table is the one
verified mapping; reports must cite the exact concept rather than a convenient
number.

| ID | Exact register concept | Correct Stage-0 use | Common incorrect use to remove | Existing proof status |
|---|---|---|---|---|
| P01 | Contract-only capability | Incomplete type→surface chain | Any missing field or absence rule by itself | Architecture doctrine; family tests only |
| P03 | Internal richness with poor external surface | Missing/incorrect controlled projection | UI authority minting generally (P05 is closer) | Existing projection tests, incomplete surfaces |
| P04 | Status enum proliferation | Parallel/cross-status lattice risk | Broad-function decomposition | Architectural protection; no anchor runtime |
| P05 | Authority dilution | Projection/package/receipt confused with authority | All administrative scope inflation | Existing boundary/projection tests |
| P07 | Schema versioning without rule evolution | Historical rule-version replay | Generic append-only correction | Partial replay patterns |
| P08 | Time semantics fragmentation | Clock-role/correction/replay confusion | Every supersession problem | Partial temporal/lifecycle tests |
| P09 | Implicit soft gates | Expiry/warning owner and escalation | Generic dependency expiry without warning lifecycle | Partial existing controls |
| P10 | Structural-only validation | Shape/pass without semantic adequacy | Missing evidence/non-occurrence alone | Existing semantic tests in narrower scopes |
| P12 | Producer fragmentation | Pre-emission concept/scope handshake | Solely Lex/Data Forge role split | Architecture concern |
| P13 | Contract gravity well | Disproportionate mandatory artifact/gate cost | “Administrative scope inflation” as a synonym | Architecture review only |
| P14 | Raw evidence count inflation | Independence/source-count collapse | Vendor self-evaluation generally | Foundry/Scholar patterns |
| P15 | LLM speculation laundering | Candidate output becomes authority | Any observation-to-admission transition | Existing candidate firewalls |
| P19 | Aggregation laundering | Subject/granularity scope drift | Any individual-use firewall issue without aggregation | Partial concept/IR tests |
| P24 | Strategic-response laundering | Goodhart/Lucas/performativity | Any automatic policy action | Research task INT-R4/OPS-R5 |
| P26 | Responsibility-integrity laundering | Mandate-bounded informed human decision | Missing appeal link generally | Partial human-review contracts |
| P27 | Parallel implementation/canonical-owner bypass | Duplicate owner/envelope/status/contract | Any missing owner | Architecture owner maps/tests |
| P28 | Additive migration/un-strangled legacy | Old path remains default/callable | General version migration | Existing strangle guardrails |
| P29 | Authorial proof/self-attested artifact | Hand-authored oracle/proof instead of live recomputation | Duplicate event handling | Directly relevant to OPS-R15; no runner |
| P31 | Instance-patching over structural invariant | One named site fixed while sibling path remains | Broad row needs decomposition | Architectural test strategy |
| P32 | Trust-by-form | Presence/signature/shape grants authority without bind/verify | Every jurisdiction mismatch | Existing reference evidence guards in parts |
| P33 | Witness-as-spec | Exact probe passed, adjacent variants fail | Generic fixture absence | Core OPS-R15 anti-overfit concern |
| P34 | Premature green via uncompleted exclusion | Failure excluded without isolation proof | Any environmental limitation | Requires explicit isolation |
| M31 | **Not a failure pattern** | Distillation move only | Citation as `P*` pattern | Remove from failure-pattern tables |

“Detected” must mean an existing test or executed runner actually detected the
fault. Otherwise use “represented by proposed fixture,” “architecturally
constrained,” or “prose-only.”

## External-source corrections

| Source issue | Correction | Consolidated standing |
|---|---|---|
| PAO-R0 DOI row links ARK material | Use the official [DOI Handbook](https://www.doi.org/doi-handbook/html/) or relabel the [ARK overview](https://arks.org/about/ark-overview/) | Identifier governance analogy only |
| PAO-R0 bitemporal citation uses ResearchGate | Cite underlying primary publication/author record | Supports time distinction, not PolicyMatter schema |
| PAO-R1 W3C PROV link is 2012 working draft | Use final [W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/) | Provenance does not establish competence |
| PAO-R1 GAO display label corrupted and press release used | Use the final [GAO 2025 Green Book](https://www.gao.gov/assets/890/882014.pdf) | US internal-control example, not universal owner rule |
| PAO-R1 OECD AI link is press release | Use the final [*Governing with Artificial Intelligence* report](https://www.oecd.org/en/publications/governing-with-artificial-intelligence_795de142-en/full-report.html) | Comparative governance evidence |
| OPS-R15 engineering sources | Cite exact current official Temporal/Beam/NIST/RFC/OASIS documents | Engineering patterns do not grant authority or prove repository capability |
| EU/UK/US legal sources | Keep exact jurisdiction/version and operative scope | Scenario input, not universal law |
| PREMIS/Memento/RFC transparency/preservation sources | Use final standards and exact claims | Preservation/replay analogy, not production RPO/RTO |

The canonical W3C, GAO, OECD, DOI, ARK, and PREMIS destinations were
independently reopened on 2026-07-28. Other primary-source checks performed by
the audits are retained with their stated access dates. This consolidation did
not infer new legal conclusions from them.

## Documentation-artifact validation

The consolidation validator checks:

- exactly nine required Markdown files;
- parseable YAML frontmatter;
- exact baseline/audit commits, date, branch, standing lists, and
  `research_only`;
- 42 unique `S0-*` matrix IDs and disposition-summary parity;
- 16 unique consensus-kernel statements;
- exactly two unique candidate `S0-GAP-*` inquiries;
- all 20 mandatory gap-review rows;
- task coverage for 24 active, 7 merged, and 36 deferred Wave-2 tasks;
- no files outside the required directory;
- no unresolved placeholder tokens;
- Markdown table column consistency and `git diff --check`.

Result:

```text
VALIDATION PASSED
files=9 matrix_rows=42 kernel=16 gaps=2
tasks=67 active=24 merged=7 deferred=36
matrix_dispositions=
  defer_to_existing_task:7
  ratify_now:7
  reject:2
  repository_fix_separate:4
  requires_additional_research:6
  requires_cross_anchor_consolidation:2
  requires_external_or_pilot_evidence:1
  retain_as_research_guidance:4
  revise_before_acceptance:9
```

## Unverified claims and limitations

- Original PAO-R0/PAO-R1 exact wording and every section reference remain
  unavailable.
- OPS-R15 source bytes were not independently rehashed here.
- External institutional operators, competence, legal effect, service,
  settlement, records authority, and audit opinions cannot be verified from the
  repository.
- No production-like distributed topology, KMS, browser inventory, partner API,
  sealed oracle store, or benchmark runner was available.
- Current checkpoint/control/lineage findings establish missing fields/local
  keying, not an exploited cross-tenant path.
- The public-export redaction failure should be reproduced by its owner under
  the supported Python 3.14 toolchain before remediation, although it was
  reproducible in the PAO-R0 audit and the code path is unchanged.
- Same-code rebuild circularity was demonstrated on a temporary reducer, not a
  production H2 implementation that does not exist.
- Passing repository unit tests remain structural/local evidence, not proof of
  Stage-0 semantic correctness or benchmark executability.
