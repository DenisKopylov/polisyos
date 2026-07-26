---
title: PAO-R1 Test and Fixture Verification
status: draft_audit
kind: research-audit
research_task: PAO-R1
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
audit_date: 2026-07-26
audit_branch: research/pao-r1-independent-audit
authoritative_for:
  - repository audit findings at the recorded commits
  - recommended corrections to the PAO-R1 research artifact
may_not_use_for:
  - production capability claim
  - legal or institutional authority allocation
  - final code contract
  - production implementation authorization
  - automatic boundary adjudication
  - direct modification of authoritative plans
  - proof that an external institution performed a function
research_only: true
---

# PAO-R1 Test and Fixture Verification

## Checkout

Every command ran on branch `research/pao-r1-independent-audit` at
`4813b49f6ce14e8debf3aaea096f0967d38d9768`. Baseline A and B are the same
checkout.

## Commands executed

| Command | Result | Count/failure | Audit implication |
| --- | --- | --- | --- |
| `python3 -m tools.cli workspace bootstrap` | Failed | `ModuleNotFoundError: click` | System Python lacks project dependencies; no bootstrap pass claimed |
| `python3 -m tools.cli workspace doctor` | Failed | `ModuleNotFoundError: click` | Same limitation |
| `PYTHONPATH=src /tmp/pao-r0-testenv/bin/python -m tools.cli workspace bootstrap` | Failed | Bootstrap attempted `pip install --user uv==0.9.21` inside a venv | Environmental bootstrap incompatibility |
| `PYTHONPATH=src /tmp/pao-r0-testenv/bin/python -m tools.cli workspace doctor` | Failed | 8 issues: Node 24 vs 22; uv 0.11.29 vs 0.9.21; Chromium missing; uv/pnpm lock, schema, OpenAPI and frontend checks blocked | No workspace-health claim |
| `PYTHONPATH=src:. /tmp/pao-r0-testenv/bin/pytest -o addopts='' -q tests/unit/pdc/test_gy_waist_contracts.py` | Passed | **11 passed** | Verifier-only Ring-2 fields, bypass checks and PDC boundary primitives work in this scope |
| `... tests/unit/fabric/connectors/test_source_contract_v2.py` | Passed | **12 passed** | Fabric data-source contract validation works; not proof for institutional evidence families |
| `... tests/unit/lex/test_legal_authority_adapter.py tests/unit/lex/test_legal_authority_requirement_adapter.py tests/unit/lex/test_normative_applicability_report.py tests/unit/lex/legal_evaluation/test_transport_constraints.py` | Passed | **29 passed** | Legal authority/applicability/transport constraints have reusable primitives |
| `... tests/unit/ddm/mirror_contracts/test_events.py tests/unit/ddm/test_readiness_mapping.py tests/unit/ddm/test_delayed_label_replay.py` | Passed | **6 passed** | DDM event/replay/readiness semantics exist for narrow local scopes |
| `... tests/unit/core/phase0/test_audit_export_verify.py tests/unit/core/phase0/test_provenance_contract_shims.py tests/unit/core/audit/test_safe_tar.py` | Passed | **10 passed** | Portable audit/provenance/safe archive primitives work; not an independent audit opinion |
| `... tests/unit/runtime/mirror_contracts/test_access_audit.py tests/unit/core/security/test_audit_chain.py tests/unit/core/security/test_audit_log_adapter.py` | Passed | **15 passed** | Append-only access/security audit behavior works; authorization is not execution proof |
| `... tests/repo_quality/tools/test_policy_design_case_w0c_contestability.py tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py` | Passed | **22 passed** | Contestability/owner-map structural rules exist; partner adjudication remains external |
| `... tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py` | Passed | **3 passed** | Partial reissue preserves scoped unaffected material |
| `... test_policy_design_case_cluster_ownership_map.py test_policy_design_case_documentation_paths.py test_fabric_source_contracts.py test_policy_design_case_w0c_contestability.py` | Failed | **33 passed, 2 failed**; generated Fabric source-platform Markdown is stale and fail-closed main returns 1 | Existing baseline repository defect; not caused by audit |
| Runtime-quality, runtime HTTP, full lifecycle/reissue and external-audit selections | Collection blocked | Missing `jaxlib==0.8.2` for CPython 3.14; some first attempts also lacked `tests` on `PYTHONPATH` | Static evidence inspected; no pass claimed |
| `NPM_CONFIG_CACHE=/tmp/pao-r1-npm-cache npx --yes markdownlint-cli2 --no-globs "docs/research/policy-operations/audits/pao-r1/*.md"` | Passed | **6 files, 0 issues** | The committed Markdown conforms to the repository lint configuration |
| `NPM_CONFIG_CACHE=/tmp/pao-r1-npm-cache npx --yes markdownlint-cli2 "docs/research/policy-operations/audits/pao-r1/*.md"` | Failed outside audit scope | The repository config expanded to **1,042 files and 4,556 pre-existing issues in 196 files** | Not an audit-file failure; `--no-globs` isolates the six changed files |
| Frontmatter, table-column, permalink-object and line-anchor validation scripts recorded in the audit work log | Passed | **6 valid frontmatters; 213 unique Appendix-C IDs; 49 permalink uses/20 unique objects; 42 valid line anchors; 0 malformed tables** | Confirms artifact structure and commit-pinned link targets; it does not prove the semantic conclusions |

The 108 passing count used in the main report is the sum of the non-overlapping
successful command rows above. The later 33-pass/2-fail aggregate reran some of
the same tests and is not added to that count.

## Exact existing fixture and test inventory

| Repository test/symbol | Exact property proved | Does not prove |
| --- | --- | --- |
| [`test_non_verifier_writer_cannot_set_ring2_field`](https://github.com/DenisKopylov/polisyos/blob/4813b49f6ce14e8debf3aaea096f0967d38d9768/policy-engine/tests/unit/pdc/test_gy_waist_contracts.py#L88-L117) | Agent/non-verifier cannot set a verifier-only PDC authority field through validation context | External producer competence or every write path |
| `test_ring2_consumption_boundary_rejects_constructed_bypass_fields` in the same file | Constructed objects cannot bypass the Ring-2 provenance assertion | Full runtime egress or institutional event admission |
| `tests/unit/fabric/connectors/test_source_contract_v2.py` | Source-contract v2 validates active schema, quality, replay, lineage and related data-source rules | Legal finality, proof of service, audit independence, payment settlement |
| `tests/unit/lex/test_legal_authority_adapter.py` | Legal authority adapter produces/limits authority evidence | Actual legislature/court act or universal applicability |
| `tests/unit/lex/test_normative_applicability_report.py` | Applicability reports retain typed limitations | Binding legal conclusion in a real jurisdiction |
| `tests/unit/ddm/mirror_contracts/test_events.py` | DDM event contract semantics | Generic public incident classification |
| `tests/unit/ddm/test_delayed_label_replay.py` | Delayed-label replay is deterministic for its fixture | OPS-R4 multi-clock semantics |
| `tests/unit/core/phase0/test_audit_export_verify.py` | Exported core audit package verifies | Independent auditor opinion |
| `tests/unit/runtime/mirror_contracts/test_access_audit.py` | Runtime access audit event contract and append semantics | Handler success or external execution |
| `tests/repo_quality/tools/test_policy_design_case_w0c_contestability.py` | ADR-0170 structural and documentation commitments | Live appeal intake/adjudication/outcome partner |
| `tests/unit/scientist/governance/continuous/test_reissue_partial_scope.py` | Partial reissue scope behavior | Generic external-event correction/fan-out |
| `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py` | Source contains explicit projection-mint negative tests | Not executed here because collection required missing `jaxlib` |
| `tests/unit/runtime/quality/test_external_audit.py` | Source contains package/projection validation fixtures | Not executed here; no independent auditor integration |
| `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py` | Source contains unscoped-event blocker and append-only lifecycle tests | Not executed here; no generic institutional bridge |

## Proposed BND fixture mapping

No `BND-001`–`BND-040` symbol or fixture exists at either baseline. “Seed”
means an existing test or contract can be reused; “gap” means the central
semantic case is absent.

| Fixture | Existing seed | What remains missing | Pattern correction | Disposition |
| --- | --- | --- | --- | --- |
| BND-001 | ADR-0170 contestability | Competent real outcome producer and scoped cascade | P05 valid; P13 only if workflow becomes gravity well | Preserve/split act and admission |
| BND-002 | ADR-0170 pointer fail-closed tests | Real forum/standing verification | P10/P26 valid | Preserve |
| BND-003 | None exact | Notice dispatch vs legal service | P10 valid; add P32 | Preserve; pilot/jurisdiction |
| BND-004 | No proof-of-service fixture | Qualified/jurisdictional service verifier | P05 valid | Preserve; pilot |
| BND-005 | Authorization admission semantics is analogous | Payment-stage and settlement producer | Replace P14 with P05/P10 | Preserve |
| BND-006 | Lifecycle supersession/reissue seed | Payment reversal semantics | P08 partial; add lifecycle rule | Preserve |
| BND-007 | Projection-only tests | Delivery source binding | P05 primary; P03 for absent surface detail | Preserve |
| BND-008 | Fabric provenance | Real service-owner report and denominator checks | P13 is not the primary risk; use P05/P10 | Preserve |
| BND-009 | Source-contract freshness/fail closed | External institution outage effect on claims | P10 valid; add P32 | Preserve |
| BND-010 | Lex validity intervals | Institution succession/competence bridge | P08 valid | Preserve; PAO-R0/INT-R5 |
| BND-011 | No boundary-register validator | Linked-plane normalization | P31 partial; P04 is wrong unless statuses proliferate | Preserve with correction |
| BND-012 | Identity anti-role and import rules | H2/custody queue schema lint | Call anti-role directly; P13 only as gravity well | Preserve |
| BND-013 | Lex/Data Forge source/version tests | Official publisher partner | P05 valid | Preserve |
| BND-014 | DDM signal separation/candidate firewall | Generic observation admission transition | P05/P10; P15 only for LLM signal | Preserve |
| BND-015 | PDC prohibited uses / aggregation checks | External case return adapter | P19 valid; anti-role direct | Preserve |
| BND-016 | Cluster ownership-map tests | PAO-R1-specific owner search | P27 exact | Preserve |
| BND-017 | Projection-mint source tests | Executed frontend semantic fixture | P05 primary; P03 secondary | Preserve |
| BND-018 | Lex scope/transport constraints | Generic signed wrong-jurisdiction institutional event | P32 exact | Preserve |
| BND-019 | Core audit export/verify | Explicit independent-opinion absence assertion | P05 valid | Preserve |
| BND-020 | Core audit + external audit source tests | Real external auditor producer/mandate | P13 wrong as primary; use P05/P27 | Preserve |
| BND-021 | DDM event/readiness tests | Threshold-to-policy firewall | Replace P24 unless strategic response is present; use P05/P10 | Preserve |
| BND-022 | DDM delayed replay; metric versions | OPS-R4 epoch integration | P08 valid | Preserve |
| BND-023 | DDM incident candidate concepts | Media-signal observation/admission transition | P10 valid | Preserve |
| BND-024 | DDM + lifecycle bridge | Regulator competence and scoped revalidation | P13 wrong as primary; use P05/P10 | Preserve |
| BND-025 | `scientist/orchestration/engine/compensation.py` inspection | Public/UI vocabulary lint | P05 valid | Preserve unchanged |
| BND-026 | Fabric supplier/source and audit contracts | Independence verification | Replace P14 with P05/P29/P32 | Preserve |
| BND-027 | Source-contract expiry/deprecation fragments | Watched dependency orchestration | P09 valid | Preserve; OPS-R14 |
| BND-028 | Retention policy | Legal-hold adapter and deletion gate | P08/P32 weak; use records rule + P10 | Preserve; jurisdiction |
| BND-029 | No exact fixture | Formal-act promotion from political context | P10 valid | Preserve |
| BND-030 | Lex change + lifecycle/reissue | Court outcome bridge and historical replay | P07/P08 related | Preserve |
| BND-031 | Access/audit idempotency seeds | External-event dedupe + irreversible reaction test | Replace P29 with P31/idempotency | Preserve |
| BND-032 | Weakest-boundary composition | Competent precedence/adjudication | M31 is not a pattern; use P04/P05/P10 | Preserve/correct |
| BND-033 | Authority purpose/scope tests | External identity purpose binding | P32 exact | Preserve |
| BND-034 | Public revision/projection source tests | Cache invalidation end-to-end | P03 valid | Preserve; PAO-R36 |
| BND-035 | Identity anti-role | H2/payment API hard-block and metric | Call anti-role; P13 only if workflow gravity | Preserve |
| BND-036 | Authorization admission ≠ success analogy | Payment settlement adapter | P05 valid | Preserve |
| BND-037 | No exact institutional transition fixture | Competence-impact classifier | P13 wrong; use overblocking/materiality test | Preserve/qualify |
| BND-038 | Lex/authority validity intervals | Succession mandate bridge | P05 valid | Preserve |
| BND-039 | Source-contract fail-closed patterns | Boundary-register validator | P01/P10 valid; add P32 | Preserve |
| BND-040 | Lifecycle/reissue append-only source tests | Boundary-decision owner/workflow | P07/P08 related; governance owner unresolved | Preserve as research fixture |

## Concrete adversarial probes

| Probe | Method/outcome | Classification |
| --- | --- | --- |
| Non-verifier writes authority fields | Executed PDC test; rejected; 11-test file passed | Existing narrow gate confirmed |
| Runtime wrapper mistaken for external-act owner | Read `institutional_provenance` wrappers and ADR-0170; wrapper ownership is technical, act owner remains external | Terminology risk confirmed |
| Observation directly changes claim status | DDM events/replay inspected; DDM signal is not a generic admitted authority transition | No generic path proved; transition gap remains |
| Projection mints authority | Static negative tests and external-audit validator found; Atlas plan documents two historical/current implementation violations | Doctrine enforced in some paths, not universally |
| Authorization allow mistaken for successful execution | `access_audit.py:93–99` explicitly denies this interpretation; access-audit tests passed | Strong positive finding |
| Signed event wrong jurisdiction | Lex transport tests passed; no generic cross-family institutional envelope test exists | Family-local protection, generic gap |
| Signed event wrong subject | PDC/Ring-2 purpose binding tests exist; no all-family institutional test | Partial |
| Missing external evidence becomes pass | Fabric fail-closed contracts/tests exist; generic claim dependency absent | Partial; row-specific route missing |
| Stale evidence remains current | Source-contract and decision-validity code inspected; full runtime suite blocked | Static partial |
| Corrected event overwrites history | Lifecycle/reissue source is append-only; partial reissue tests passed | Narrow case path confirmed |
| Appeal triggers scoped revalidation | ADR-0170 permits append-only outcome effects; real producer/bridge absent | `bridge_missing` |
| Unscoped appeal/incident blocked | Lifecycle bridge source emits blocker; full test collection blocked | Static evidence, runtime not rerun |
| Technical compensation leaks as financial remedy | Exact source semantics inspected; no public lint/test found | Naming collision confirmed; protection missing |
| Payment authorization displayed as settlement | No payment surface/runtime exists; authorization contract says admission ≠ success | Proposed fixture only |
| Send status displayed as legal service | No proof-of-service contract/surface found | Proposed fixture only |
| Audit package displayed as independent conclusion | Core audit tests passed; external-audit projection validator inspected | Package/opinion boundary confirmed; UI coverage partial |
| Duplicate external event duplicates reaction | Access audit is idempotent; no generic external-event reaction bridge | Generic gap |
| Tenant/jurisdiction dropped | Fields common in RQ/Fabric/Lex; no cross-family federation test | Presence is not proof; gap |
| Broad API `status` without evidence state | Many local status fields found in runtime/generated clients | Parallel-lattice risk confirmed |
| Common fields already exist | RQ envelope, Fabric contract, PROV, audit and temporal types inspected | Duplicate-envelope risk confirmed |
| PDC references boundary-decision version | Exact searches found no field/symbol | Absent at both baselines |
| Provenance distinguishes all five owner roles | PROV has entity/activity/agent/role edges, not explicit operator/issuer/adapter/consumer owner fields | Partial |
| Boundary change fans out | Decision-validity/lifecycle support scoped events; no boundary-decision dependency type | Missing |
| Boundary correction without rewriting | Generic lifecycle pattern exists; no boundary-decision artifact | Research-only proposal |
| H2/control plane executes external acts | No H2 production owner or payment/notice/service/procurement execution path found | Bounded negative; hidden partner code remains blind spot |

## Dynamic composition probe

The following direct probe ran successfully:

```text
AuthorityBoundary A:
  authoritative_for = [claim:a, claim:b]
  may_not_use_for = [pay]
AuthorityBoundary B:
  authoritative_for = [claim:b, claim:c]
  may_not_use_for = [serve]
meet(A, B):
  authoritative_for = [claim:b]
  may_not_use_for = [pay, serve]
  posture = advisory
  evidence_kind = simulation
  decision_grade = descriptive_only
```

This confirms the report's exact intersection/union/weakening claim for the PDC
class. It does not prove that every legal, audit, security, identity, service or
payment family can be represented without additional semantics.

## Search record for negative findings

The census used case-insensitive `rg` over:

```text
src tests docs schemas architecture apps
```

Queries included every name required by the audit specification, plus exact
`OperationalBoundaryDecision`, `InstitutionalEvidenceEnvelope`,
`BoundaryDecisionChallengeReceipt`, `AbsenceBehavior`, `boundary_decision_id`,
`supersedes_boundary_decision`, `proof_of_service`, `audit_opinion`,
`records_disposition`, `policy_matter_ref`, `owner_state`, `real_operator`,
`external_producer`, `claim_reaction_owner` and `admitted_at`.

Exact findings:

- `OperationalBoundaryDecision`: one documentation hit in the Wave-2 backlog,
  no implementation;
- `InstitutionalEvidenceEnvelope`: zero;
- `policy_matter_ref`: zero;
- `proof_of_service`: zero;
- `audit_opinion`: zero;
- `owner_state`, `real_operator`, `external_producer`,
  `claim_reaction_owner`, `boundary_verdict`: zero;
- `admitted_at`: one unrelated documentation/spec occurrence, no canonical
  cross-family clock.

No paths were deliberately excluded. Generated architecture baselines were
searched. Confidence is high for symbol absence in the checkout and medium for
operational absence. Blind spots: untracked files, inaccessible services,
partner deployments, secrets, packages fetched at runtime, and unreachable Git
history.

## Runtime blockers

- Missing CPython 3.14 `jaxlib` prevented collection of several runtime-quality,
  HTTP and lifecycle suites.
- Browser and frontend contract checks could not run because Chromium is absent,
  Node/uv versions differ from repository pins, and corepack attempted to use an
  unwritable cache.
- No partner systems or jurisdiction packs were available, so external
  competence, legal service, settlement, institutional audit, records
  disposition and service delivery cannot be runtime-verified.
- The supplied PAO-R1 report is not committed, so no repository validator can
  parse it directly.
