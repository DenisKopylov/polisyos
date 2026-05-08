---
title: Business GPT Agents Knowledge Base Plan
status: active
owner: denis-kopylov
created: 2026-05-07
last_verified: 2026-05-07
stability: draft
related:
  - docs/plans/README.md
  - docs/plans/TEMPLATE.md
  - docs/reference/scientist/claim-ledger.md
  - docs/reference/lex/knowledge.md
  - docs/adr/0129-scientist-claim-ledger.md
  - docs/adr/0015-knowledge-bundle-freshness-protocol.md
---

# Business GPT Agents Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** build a governed, artifact-first knowledge base for the new business
GPT agents so they can produce customer-safe, procurement-safe, internally
useful answers without mixing canonical company truth with temporary working
memory.

**Architecture:** use `policy-engine/knowledge/business_agents/**` as the
git-backed canonical artifact source, with Markdown bodies and YAML
frontmatter following the ADR documentation pattern. Treat registries as views
over atomic artifacts, task packs as just-in-time assembly recipes, access as
agent policy configuration, indexes and embeddings as derived artifacts, and
interaction memory as a separate runtime store with distinct retention and
access rules.

**Tech Stack:** Markdown with YAML frontmatter, JSON Schema, TOML policy
contracts, Python/Pydantic loaders, DuckDB or runtime storage for interaction
memory, hybrid retrieval using the existing trust/domain/jurisdiction/as-of
filtering ideas, pytest repo gates, MkDocs reference pages.

---

## 1. Context

This plan is for the business GPT agent set listed by Denis on 2026-05-07:

| User-facing name | Canonical agent id for this plan | Primary category |
| --- | --- | --- |
| Ассистент руководителя | `executive_assistant` | executive operations |
| Составитель ответов клиентам | `customer_reply_drafter` | customer communication |
| Анализ данных | `data_analysis_assistant` | analytics |
| Ассистент по продажам | `sales_assistant` | GTM |
| Конструктор SQL-запросов | `sql_query_builder` | analytics engineering |
| Анализ условий договора | `contract_terms_analyzer` | legal/procurement |
| Ассистент по анализу причин инцидентов | `incident_rca_assistant` | operations |
| Генератор описаний вакансий | `job_description_generator` | people |
| Генератор рекламных текстов для кампаний | `campaign_copy_generator` | marketing |
| Карта стейкхолдеров | `stakeholder_map_assistant` | GTM/account planning |
| Координатор IT Change Advisory Board | `it_cab_coordinator` | IT governance |
| Маркетинговая стратегия | `marketing_strategy_assistant` | marketing |
| Менеджер ответов на RFP | `rfp_response_manager` | procurement/GTM |
| Отраслевой обзор | `industry_brief_assistant` | market intelligence |
| Планирование продукта | `product_planning_assistant` | product |
| Подготовка ответов для анкет по безопасности | `security_questionnaire_assistant` | trust/procurement |
| Поддержка клиентов | `customer_support_assistant` | support |
| Поиск знаний | `knowledge_search_assistant` | internal discovery |
| Помощник по дизайну | `design_assistant` | design/product marketing |
| Проверка заявок на ПО | `software_request_reviewer` | IT governance |
| Синтезатор отзывов о продукте | `product_feedback_synthesizer` | product research |
| Управление задачами | `task_management_assistant` | operations |
| Финансовая отчетность по закрытию месяца | `month_close_reporting_assistant` | finance |
| Эксперт по оценке готов | `readiness_assessment_expert` | readiness/risk |

The last user-facing label is truncated in the input. The stable internal id is
therefore `readiness_assessment_expert`, and UI copy can later rename it without
changing the policy surface.

### Official Product Context Verified On 2026-05-07

OpenAI Help currently describes ChatGPT Business standard seats as including
ChatGPT features such as GPTs, Projects, Apps, Company Knowledge, ChatGPT
Agent, Deep Research, and Codex. Company Knowledge is described as using
enabled apps to return organization-specific answers with citations while
respecting existing source permissions.

Sources checked:

- OpenAI Help, "What is ChatGPT Business?":
  <https://help.openai.com/en/articles/8792828>
- OpenAI Help, "Company knowledge in ChatGPT (Business, Enterprise, and Edu)":
  <https://help.openai.com/en/articles/12628342-company-knowledge-in-chatgpt-business-enterprise-and-edu>
- OpenAI product announcement, "Work smarter with your company knowledge in
  ChatGPT": <https://openai.com/index/introducing-company-knowledge/>

This plan does not assume the user-facing names above are permanent OpenAI
product identifiers. It treats them as the current PolicyOS workspace agent
catalog input.

## 2. Scope

In scope:

- canonical business-agent knowledge architecture;
- artifact type catalog;
- minimal and expanded metadata taxonomy;
- lifecycle, publishability, redaction, freshness, approval, and reissue
  policies;
- source-of-truth, evidence, artifact, runtime memory, and output boundaries;
- agent registry and access policy model;
- retrieval and task-pack assembly contract;
- response contracts per agent category;
- folder, schema, config, docs, tests, and rollout plan;
- migration path from scattered docs or ad hoc prompts into governed artifacts;
- MVP sequencing that starts small but does not paint the system into a
  document-first corner.

Out of scope:

- filling the knowledge base with full product/legal/security content;
- implementing final user-facing ChatGPT workspace configuration;
- committing real customer account notes into git;
- making unverified claims about PolicyOS capabilities, pricing, compliance,
  roadmap, or security;
- treating this plan as permanent source of truth after implementation. Stable
  rules must move into `docs/reference/**`, machine contracts into
  `schemas/**` and `architecture/**`, and procedures into `docs/runbooks/**` or
  `docs/how-to/**`.

## 3. Non-Negotiable Design Principles

1. **Artifact-first, not document-first.** The base unit is a typed artifact
   such as `capability_card`, `approved_claim`, `objection_response`,
   `security_answer_module`, `contract_clause_playbook`, `support_known_issue`,
   `pricing_rule`, `glossary_term`, `stakeholder_persona`,
   `implementation_pattern`, `rfp_answer_module`, or `escalation_policy`.

2. **Canonical artifacts, not duplicated source layers.** The proposed
   "Canonical Source Layer" and "Knowledge Object Layer" collapse into one
   source layer: canonical atomic artifacts. Registries are generated views over
   those artifacts, not separate truth stores.

3. **Truth, evidence, memory, and outputs stay separate.** Canonical artifacts
   are stable approved knowledge. Evidence refs point to sources. Interaction
   memory contains call notes, account notes, feedback, drafts, and temporary
   observations. Output recipes assemble task context. These four classes must
   never be indexed as one customer-facing corpus.

4. **Task packs are recipes, not stored copies.** A sales discovery pack, RFP
   pack, security questionnaire pack, or support first-response pack is built
   at request time from current approved artifacts. Stored copies of the same
   fact are not allowed to become a silent divergence source.

5. **Access is computed, not enumerated on every artifact.** Do not put
   `agents_allowed` on artifacts. Agent policies declare which properties they
   may read and quote. Artifacts carry properties such as lifecycle,
   publishability, recipients, observer modes, risk, domain, source refs, and
   freshness.

6. **Lifecycle and publishability are separate axes.** `lifecycle_state` says
   whether the object is draft, approved, blocked, superseded, or withdrawn.
   `publishability` says where it may be used: internal, customer-safe, or
   restricted.

7. **Reuse Claim Ledger vocabulary.** Do not create a second lifecycle language
   when PolicyOS already has claim-ledger semantics. Business knowledge should
   use `approved`, `blocked`, `superseded`, `reissued`, and `withdrawn` as
   operating concepts, while remaining separate from Scientist claim records.

8. **Owner plus review date is a production gate.** An artifact without
   `owner` and `review_due_at` is not production-ready, even if its text looks
   correct.

9. **Customer-facing retrieval is fail-closed.** If an artifact is not approved,
   is blocked, is stale beyond policy, has restricted publishability, or lacks
   required source refs, the agent must not quote it to customers.

10. **Disallowed claims are first-class.** The reject list is often shorter and
    more stable than the approved list. Agents must retrieve disallowed claims
    before drafting customer-facing text.

11. **Response contracts matter as much as retrieval.** High-value agents must
    answer in fixed shapes that expose confirmed facts, caveats, assumptions,
    missing information, escalation need, and source artifact ids.

12. **MVP starts with friction, not with ontology pride.** Begin with two or
    three high-signal artifact types, run real agent tasks, then add metadata
    and artifact types only when retrieval, policy, or review needs prove the
    need.

13. **Specification eviction is part of the plan.** Once ADR, schema, TOML, and
    reference docs exist, long explanatory sections in this plan must be treated
    as historical guidance. Durable behavior belongs in contracts and reference
    docs, not in this active plan.

## 4. Source Of Truth Map

| Concern | Source after this plan is implemented | Current anchor |
| --- | --- | --- |
| Irreversible architecture decision | New ADR under `policy-engine/docs/adr/NNNN-business-agent-kb-boundary.md` | `docs/adr/0129-scientist-claim-ledger.md`, `docs/adr/0015-knowledge-bundle-freshness-protocol.md` |
| Canonical business knowledge artifacts | `policy-engine/knowledge/business_agents/canonical/**` | No dedicated source yet |
| Artifact schema | `policy-engine/schemas/knowledge/business_agent_artifact.schema.json` | Plan only |
| Agent access policy | `policy-engine/architecture/business_agent_access.toml` | Existing knowledge-search filtering ideas |
| Artifact type registry | `policy-engine/architecture/business_agent_artifact_types.toml` | Plan only |
| Agent registry | `policy-engine/architecture/business_agent_registry.toml` | User-provided agent list on 2026-05-07 |
| Task pack recipes | `policy-engine/src/polisyos/business_agents/task_packs/**` or `policy-engine/architecture/business_agent_task_packs.toml` | Plan only |
| Approval policy | `policy-engine/architecture/business_agent_approval.toml` | Plan only |
| Source registry | `policy-engine/knowledge/business_agents/source_registry.toml` | Plan only |
| Runtime interaction memory | Production runtime store configured by `polisyos.business_agents.memory`; local dev may use DuckDB | Must not live under `knowledge/**` |
| Reference docs | `policy-engine/docs/reference/knowledge/business-agents.md` | `docs/reference/lex/knowledge.md` as documentation pattern |
| Procedures | `policy-engine/docs/runbooks/business-agent-kb-governance.md` and `docs/how-to/business-agent-kb-authoring.md` | Plan only |
| Generated indexes | `policy-engine/knowledge/business_agents/index.toml` and search index artifacts | ADR `index.toml` convention as pattern |

### 4.1 Source Registry Contract

`source_refs` are a hard gate, so they need a real registry before any artifact
can be approved. The registry lives at
`policy-engine/knowledge/business_agents/source_registry.toml`, and its schema
lives at `policy-engine/schemas/knowledge/business_agent_source_registry.schema.json`.

Registry entry shape:

```toml
[[sources]]
id = "src.product.capability_registry"
kind = "reference_doc"
owner = "product"
backup_owner = "founder"
path = "docs/reference/product/capability-registry.md"
visibility = "internal"
publishability = "customer_safe"
freshness_tier = "high"
review_due_at = "2026-06-30"
proof_grade = "canonical_internal"
```

Required fields:

| Field | Meaning |
| --- | --- |
| `id` | Stable source id referenced by artifacts |
| `kind` | `reference_doc`, `adr`, `schema`, `source_code`, `security_matrix`, `contract_template`, `external_url`, `runtime_record`, or `manual_attestation` |
| `owner` | Accountable source owner |
| `path` or `url` | Resolvable location |
| `visibility` | Internal visibility of the source |
| `publishability` | Whether source details can be exposed externally |
| `freshness_tier` | Review interval class |
| `review_due_at` | Source freshness gate |
| `proof_grade` | How strong the source is as evidence |

Allowed `proof_grade` values:

- `canonical_internal`;
- `auditable_internal`;
- `third_party_public`;
- `runtime_observation`;
- `manual_attestation`;
- `unverified_context`.

Artifacts may reference `unverified_context` only while `draft` or
`in_review`.

### 4.2 Integration With Existing Knowledge Infrastructure

This work must not create a second unrelated retrieval platform.

Reuse:

- the ADR/index convention from `docs/adr/**` for Markdown+frontmatter,
  generated indexes, and supersession visibility;
- the Claim Ledger lifecycle vocabulary and append-only event discipline from
  `docs/reference/scientist/claim-ledger.md`;
- the existing knowledge-search policy-filter ideas: trust tier, domain,
  jurisdiction, `as_of`, and quality/freshness bands;
- existing Python validation and repo-quality gate patterns under
  `tools/quality/validation/**` and `tests/repo_quality/**`.

Do not reuse blindly:

- `polisyos.lex.knowledge` as the business artifact store. Lex Knowledge is a
  legal DuckDB/vector surface with legal fact/provision contracts; business
  artifacts need different schemas and governance.
- Scientist Claim Ledger records as business-agent artifacts. Business KB
  lifecycle should be compatible with claim-ledger events, not stored inside
  Scientist claim ledgers.

Build new:

- a thin `business_agents.knowledge` policy/loader/assembler layer;
- adapters that can call existing hybrid/vector search infrastructure when the
  index backend is shared;
- tests proving business KB filters run before semantic ranking.

### 4.3 Workspace And Tenancy Model

Initial scope is one PolicyOS-owned internal workspace knowledge base:
`workspace_id = "ws.policyos"`. Canonical artifacts are global to this internal
workspace unless later architecture explicitly enables customer-specific
canonical stores.

Memory is always scoped:

- `tenant_id` identifies the deployment or workspace boundary;
- `workspace_id` identifies the ChatGPT/PolicyOS workspace;
- `account_id` identifies customer/account context when applicable;
- `subject_ids` identify people or entities covered by erasure requests.

Customer-specific memory must never be co-indexed with global canonical
artifacts. If PolicyOS later supports multiple tenants, each tenant gets a
separate memory store and, if needed, a separate canonical namespace rather
than a shared corpus filtered only at query time.

## 5. Target Repository Layout

The final implementation should create these paths:

```text
policy-engine/
  knowledge/
    business_agents/
      README.md
      index.toml
      source_registry.toml
      canonical/
        product/
          capability_cards/
          product_facts/
          use_cases/
          glossary/
          approved_claims/
          disallowed_claims/
          roadmap_safe_wording/
        commercial/
          icp/
          segment_briefs/
          stakeholder_personas/
          message_house/
          objection_responses/
          pricing_rules/
          competitive_notes/
        trust/
          security_answer_modules/
          data_handling/
          architecture_positions/
          compliance_positions/
          rfp_answer_modules/
          contract_clause_playbooks/
        customer_ops/
          faq_cards/
          support_policies/
          known_issues/
          onboarding_patterns/
          implementation_patterns/
          escalation_policies/
          incident_comms/
        internal_enablement/
          design_guidelines/
          job_description_templates/
          campaign_copy_modules/
          sql_patterns/
          data_metric_definitions/
          change_policies/
          software_request_policies/
          readiness_rubrics/
      fixtures/
        prompts/
        expected_bundles/

  schemas/
    knowledge/
      business_agent_artifact.schema.json
      business_agent_answer_bundle.schema.json
      business_agent_memory.schema.json
      business_agent_source_registry.schema.json
      business_agent_search_result_bundle.schema.json
      business_agent_observability_event.schema.json

  architecture/
    business_agent_registry.toml
    business_agent_access.toml
    business_agent_approval.toml
    business_agent_artifact_types.toml
    business_agent_task_packs.toml
    business_agent_freshness.toml
    business_agent_conflict_policy.toml

  src/
    polisyos/
      business_agents/
        __init__.py
        knowledge/
          __init__.py
          artifacts.py
          loader.py
          policy.py
          retrieval.py
          source_registry.py
          scoring.py
          indexer.py
          answer_bundle.py
        task_packs/
          __init__.py
          recipes.py
          assembler.py
          response_contracts.py
        memory/
          __init__.py
          models.py
          store.py
          retention.py
        governance/
          __init__.py
          lifecycle.py
          approval.py
          validation.py
          redaction.py
          observability.py

  tests/
    unit/
      business_agents/
        knowledge/
          test_artifact_schema.py
          test_access_policy.py
          test_retrieval_policy_filter.py
          test_task_pack_assembly.py
          test_response_contracts.py
          test_memory_separation.py
    repo_quality/
      architecture/
        test_business_agent_kb_contracts.py

  docs/
    reference/
      knowledge/
        business-agents.md
    how-to/
      business-agent-kb-authoring.md
    runbooks/
      business-agent-kb-governance.md
```

Layout rules:

- `knowledge/business_agents/canonical/**` stores only canonical artifacts.
- `knowledge/business_agents/index.toml` is generated or refreshed from
  canonical artifacts and may be checked in if repo convention chooses checked
  indexes.
- `fixtures/**` exists only for validation prompts and expected retrieval
  bundles, not for real customer data.
- `src/polisyos/business_agents/memory/**` defines the runtime memory contract,
  but memory records themselves do not live in git.
- `architecture/*.toml` is the machine-readable policy surface for the agent
  registry, access, approval, task pack recipes, artifact type constraints,
  conflict resolution, and freshness.
- `knowledge/business_agents/source_registry.toml` is the resolvable source
  registry for every `source_refs` and `evidence_refs` id.
- `docs/reference/**` explains stable behavior after implementation; this plan
  remains an execution artifact only.

## 6. Canonical Artifact Contract

### 6.1 Minimal Required Frontmatter

Start with a small schema that directly supports policy filtering. These fields
are mandatory for every production artifact:

```yaml
id: kb.capability.sso
title: Single Sign-On support
artifact_type: capability_card
lifecycle_state: approved
publishability: customer_safe
recipients:
  - prospect
  - customer
owner: product
review_due_at: 2026-06-30
domains:
  - product
  - security
source_refs:
  - src.product.capability_registry
```

Required fields and why they exist:

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | string | Stable object id; never reused for a different meaning |
| `title` | string | Human-readable review label |
| `artifact_type` | enum | Drives validation, retrieval boosting, and response assembly |
| `lifecycle_state` | enum | Draft/review/approved/blocked/superseded/withdrawn policy |
| `publishability` | enum | Internal/customer-safe/restricted usage axis |
| `recipients` | list enum | Recipient classes the artifact may answer |
| `owner` | string | Accountable owner for correctness |
| `review_due_at` | date | Freshness gate |
| `domains` | list enum | Product, security, legal, commercial, ops, finance, people, design, analytics |
| `source_refs` | list string | Registered origins used to author or approve the artifact |

### 6.2 Recommended Optional Frontmatter

Add these fields only when they are used by retrieval, governance, or review:

```yaml
backup_owner: security
reviewers:
  - product
  - security
version: 1.0
effective_from: 2026-05-07
freshness_tier: high
confidence: high
journey_stages:
  - evaluation
  - procurement
risk_level: medium
observers:
  - auditor
jurisdictions:
  - global
plan_tiers:
  - business
deployment_models:
  - cloud
human_review_required_if:
  - asks_for_contractual_commitment
  - asks_for_roadmap_date
related_artifacts:
  - kb.security.access_control
supersedes: []
superseded_by: []
evidence_refs:
  - evidence.security.control_matrix.v1
quality_band: gold
notes_internal: >
  Internal reviewer notes that are not eligible for customer-facing output.
```

Optional fields are not status symbols. They are accepted only if at least one
of these is true:

- an agent policy filters on the field;
- a task-pack recipe needs the field;
- a reviewer workflow routes on the field;
- a freshness or risk gate uses the field;
- an external audit or export needs the field.

Signal semantics:

| Field | Orthogonal meaning | Example |
| --- | --- | --- |
| `risk_level` | harm if misused or over-quoted | legal fallback language is high risk even when fresh |
| `freshness_tier` | how quickly the artifact can rot | pricing and roadmap wording rot faster than glossary terms |
| `confidence` | owner confidence in the statement | a new capability card can be low confidence until implementation review |
| `quality_band` | source/evidence structure quality | a cited security matrix is higher quality than a sales note |

Do not collapse these into one permanent `trust_score` in the artifact. The
retrieval layer may compute a request-specific ranking score, but policy gates
use the individual signals so reviewers can see exactly why an artifact was
allowed, blocked, stale, or escalated.

### 6.3 Body Contract

Every artifact file has two parts:

1. YAML frontmatter as the machine-readable contract.
2. Markdown body as the human-readable canonical content.

Body sections:

```markdown
## Canonical Answer

PolicyOS supports SSO in the current approved deployment scope.

## Approved Claims

- Supports SSO in approved deployment patterns.

## Disallowed Claim Refs

- kb.disallowed.sso_every_plan
- kb.disallowed.guaranteed_customer_rollout_date

## Safe Wording

Short:
PolicyOS supports SSO under approved deployment patterns.

Procurement:
PolicyOS supports SSO under approved deployment patterns. Final configuration
details should be confirmed during security and implementation review.

## Escalation

Escalate to product and security if the user asks for contractual commitment,
custom rollout timing, or unsupported deployment variants.
```

The loader must parse both frontmatter and headings. Customer-facing agents may
use only approved sections. Internal agents may see `notes_internal`, but it
must not appear in customer-facing output.

Disallowed claims are referenced by id, not duplicated inline. The source of
truth for banned wording is always a `disallowed_claim` artifact. This slightly
expands the MVP, but avoids a guaranteed migration trap where the same banned
claim exists both inside a capability card and as a typed object.

## 7. Lifecycle Model

### 7.1 State Axis

Use one lifecycle vocabulary:

| `lifecycle_state` | Meaning | Customer-facing use |
| --- | --- | --- |
| `draft` | Created but not review-ready | Never |
| `in_review` | Submitted for owner/reviewer review | Never unless explicit reviewer mode |
| `approved` | Current production artifact | Allowed if publishability permits |
| `blocked` | Known risk or conflict; still visible to reviewers and machines | Never |
| `superseded` | Replaced by a newer artifact | Never, except to explain history internally |
| `withdrawn` | No longer valid and not replaced | Never |

Do not add `approved_internal` or `approved_customer_safe` as lifecycle states.
Those belong to `publishability`.

### 7.2 Event Vocabulary

The event log should support these transitions:

| Event | Required metadata |
| --- | --- |
| `created` | actor, reason, timestamp |
| `submitted_for_review` | actor, reviewers, reason, timestamp |
| `approved` | actor, owner, reviewer refs, timestamp |
| `blocked` | actor, reason, customer impact, timestamp |
| `unblocked` | actor, reason, reviewer refs, timestamp |
| `superseded` | actor, superseding artifact id, reason, timestamp |
| `reissued` | actor, source artifact id, reason, timestamp |
| `withdrawn` | actor, reason, timestamp |
| `reviewed_no_change` | actor, reviewer refs, next review due, timestamp |

Every event requires a non-empty `actor_id` and `reason`, matching the Claim
Ledger discipline in `docs/reference/scientist/claim-ledger.md`.

### 7.3 Replacement Rules

- Never delete a production artifact to hide old wording.
- If wording changes but meaning remains compatible, create a new version and
  event.
- If meaning changes materially, create a new artifact id or reissue event and
  mark the old artifact `superseded`.
- If a claim becomes unsafe, mark it `blocked` immediately, then resolve through
  `reissued`, `superseded`, or `withdrawn`.
- Retrieval must include blocked and superseded artifacts in reviewer/machine
  exports, but never in customer-facing bundles.

## 8. Publishability And Visibility

Use `publishability` as a separate axis:

| `publishability` | Meaning | Typical examples |
| --- | --- | --- |
| `internal` | Safe for internal agents, not approved for customers | strategy notes, internal process, implementation notes |
| `customer_safe` | Can be used in customer replies, RFPs, support, sales | approved claims, FAQ cards, support answers |
| `restricted` | High-risk content requiring policy and often human review | legal positions, security details, pricing exceptions, roadmap boundaries |

Use `recipients` for intended recipients:

```yaml
recipients:
  - internal
  - prospect
  - customer
  - vendor
  - candidate
```

Use `observers` for review or oversight modes. Observers are not the same as
recipients: an auditor may inspect a customer-facing answer with extra
provenance, but that does not mean auditor-facing prose follows customer-copy
rules.

```yaml
observers:
  - auditor
  - regulator
```

Access is granted only if all are true:

- lifecycle state is allowed by the agent policy;
- publishability is allowed by the agent policy;
- recipient intersects with the task recipient;
- observer mode is allowed when the task is an audit, regulatory, reviewer, or
  machine export;
- domain is allowed by the agent policy;
- risk is at or below the policy threshold, unless escalation mode is active;
- artifact is fresh enough;
- source refs are present and valid;
- no disallowed-claim conflict is detected.

## 9. Artifact Type Catalog

### 9.1 MVP Types

Start with three task-facing types plus one guardrail type:

| Artifact type | Why first | Used by |
| --- | --- | --- |
| `capability_card` | Product truth is the most common source of sales/support/RFP drift | sales, RFP, support, customer replies, security questionnaire |
| `objection_response` | Gives immediate feedback from sales and customer-facing agents | sales, stakeholder map, RFP, customer replies |
| `faq_card` | Stabilizes repeat customer/support answers quickly | support, customer replies, knowledge search |
| `disallowed_claim` | Prevents unsafe wording from being duplicated inline in other artifacts | every customer-facing recipe |

Expansion to more types is allowed only after these pass retrieval and review
tests with real prompts.

### 9.2 First Expansion Types

| Artifact type | Purpose | Primary owner |
| --- | --- | --- |
| `approved_claim` | Reusable allowed wording | founder/product |
| `pricing_rule` | What can be said about pricing and packaging | founder/growth |
| `security_answer_module` | Atomic answer for security questionnaires | security |
| `contract_clause_playbook` | Position, risk, fallback language for contract clauses | legal |
| `rfp_answer_module` | Reusable RFP response block with citations | sales/procurement |
| `glossary_term` | Canonical definitions | product/docs |
| `implementation_pattern` | Safe deployment/onboarding pattern | product/ops |
| `roadmap_safe_wording` | Approved ways to discuss future product direction without commitments | founder/product |

### 9.3 Full Catalog

| Domain | Artifact types |
| --- | --- |
| Company/product truth | `product_fact`, `capability_card`, `use_case_card`, `glossary_term`, `approved_claim`, `disallowed_claim`, `roadmap_safe_wording` |
| Commercial/GTM | `icp_profile`, `segment_brief`, `stakeholder_persona`, `message_house_module`, `objection_response`, `competitive_position`, `pricing_rule` |
| Trust/procurement | `security_answer_module`, `security_control_summary`, `data_handling_position`, `architecture_position`, `compliance_position`, `rfp_answer_module`, `contract_clause_playbook` |
| Customer operations | `faq_card`, `support_policy`, `known_issue_card`, `onboarding_checklist`, `implementation_pattern`, `escalation_policy`, `incident_comms_template` |
| Internal enablement | `sql_pattern`, `data_metric_definition`, `incident_rca_pattern`, `change_policy`, `software_request_policy`, `job_description_template`, `campaign_copy_module`, `design_guideline`, `product_feedback_theme`, `task_management_policy`, `month_close_reporting_rule`, `readiness_assessment_rubric` |

## 10. Agent Access Policy Contract

The full access matrix belongs in
`policy-engine/architecture/business_agent_access.toml`. This plan defines the
principle and a small example only.

Access policy inputs:

| Input | Source |
| --- | --- |
| agent identity and category | `business_agent_registry.toml` |
| artifact lifecycle, publishability, recipients, observers, domain, risk, freshness | artifact frontmatter |
| owner/reviewer requirements | `business_agent_approval.toml` |
| task intent and recipient | retrieval request context |
| source/evidence validity | `source_registry.toml` |

Example policy summary:

| Agent id | Customer-facing allowed | Memory mode | Restricted handling |
| --- | --- | --- | --- |
| `sales_assistant` | yes | account context only | human review for roadmap, pricing, security, legal |
| `contract_terms_analyzer` | no final external output | deal context only | legal owner required |

Rules:

- adding a new agent changes `business_agent_registry.toml` and
  `business_agent_access.toml`, not artifact frontmatter;
- access is computed from properties, never from `agents_allowed`;
- policy denial reason codes must be emitted for observability;
- customer-facing access requires both an allowed agent policy and allowed
  artifact properties.

## 11. Agent Response Contracts

### 11.1 Customer-Facing Answer

Used by `customer_reply_drafter`, `customer_support_assistant`,
`sales_assistant`, `rfp_response_manager`, and parts of
`security_questionnaire_assistant`.

```yaml
answer_type: customer_facing_answer
confirmed_answer: string
caveats:
  - string
missing_information:
  - string
escalation_needed: true
escalation_route:
  owner_team: product
  required_reviewers:
    - security
source_artifact_ids:
  - kb.capability.sso
disallowed_claims_checked:
  - kb.disallowed.sso_every_plan
```

Rules:

- Include caveats when the artifact includes limits or safe wording.
- Include `missing_information` when the user asks for plan tier, legal term,
  roadmap date, data residency, security certification, or custom integration
  not covered by approved artifacts.
- Set `escalation_needed` when any artifact trigger matches.

### 11.2 Security Answer

```yaml
answer_type: security_answer
direct_response: string
control_statement: string
limitations:
  - string
evidence_refs:
  - evidence.security.control_matrix.v1
source_artifact_ids:
  - kb.security.access_control
manual_review_required: true
review_reason: high_risk_procurement_or_contractual_commitment
```

### 11.3 Contract Analysis

```yaml
answer_type: contract_analysis
clause: string
risk_level: high
why_it_matters: string
suggested_fallback: string
business_position: string
legal_review_required: true
source_artifact_ids:
  - kb.contract.limitation_of_liability
```

### 11.4 Sales Brief

```yaml
answer_type: sales_brief
account_hypothesis: string
stakeholder_map:
  - role: security_reviewer
    likely_concern: data_access
likely_pain:
  - string
allowed_proof_points:
  - string
open_questions:
  - string
next_step_recommendation: string
source_artifact_ids:
  - kb.icp.public_sector
  - kb.objection.security_review
```

### 11.5 Internal Analysis

Used by data, SQL, incident, product, feedback, finance, task management, and
readiness agents.

```yaml
answer_type: internal_analysis
summary: string
assumptions:
  - string
findings:
  - statement: string
    support: string
    source_artifact_ids:
      - kb.metric.arr
risks:
  - string
actions:
  - owner: string
    action: string
    due: 2026-05-15
escalation_needed: false
```

### 11.6 Search Result Bundle

Used by `knowledge_search_assistant`. It returns labeled retrieval results and
policy decisions, not a synthesized customer-facing answer.

```yaml
answer_type: search_result_bundle
query: "SSO security review"
mode: reviewer
results:
  - artifact_id: kb.capability.sso
    title: Single Sign-On support
    artifact_type: capability_card
    lifecycle_state: approved
    publishability: customer_safe
    policy_decision: allowed
    policy_reasons:
      - lifecycle_allowed
      - recipient_allowed
    source_refs:
      - src.product.capability_registry
    freshness_status: fresh
    snippet: PolicyOS supports SSO under approved deployment patterns.
omitted_results:
  - artifact_id: kb.security.sso_draft
    policy_decision: denied
    policy_reasons:
      - draft_lifecycle_state
```

The schema belongs in
`policy-engine/schemas/knowledge/business_agent_search_result_bundle.schema.json`.

## 12. Retrieval Design

### 12.1 Request Context

Every retrieval call receives a typed request context:

```yaml
agent_id: sales_assistant
task_type: sales_discovery
tenant_id: tenant.policyos_internal
workspace_id: ws.policyos
recipient: prospect
observer_mode: none
workspace_role: internal_user
customer_facing: true
jurisdiction: global
as_of: 2026-05-07
query: "How should we answer SSO and security review objections?"
provided_context_refs:
  - memory.account.acme.2026_05_07
```

### 12.2 Pipeline

Step 1 - policy filter:

- apply agent access policy;
- remove disallowed lifecycle states for the mode;
- remove publishability outside the task;
- remove stale artifacts beyond freshness policy;
- remove restricted artifacts unless task mode and role allow them;
- mark human review triggers.

Step 2 - canonical retrieval:

- retrieve atomic approved artifacts, not long documents;
- boost artifact types needed by the task;
- retrieve disallowed claims in parallel;
- retrieve source/evidence refs for provenance;
- preserve lifecycle and publishability in the result.

Step 2.5 - conflict resolution:

- detect approved-vs-approved conflicts before assembly;
- prefer the more domain-specific authority over generic FAQ content;
- prefer restricted/high-risk specialized artifacts for escalation decisions,
  but do not quote them into customer-facing output unless policy allows;
- prefer fresher approved artifacts only when authority and risk are equal;
- if conflict remains unresolved, return `requires_human_review` instead of
  letting the model blend both answers.

Step 3 - task assembly:

- apply task-pack recipe;
- group facts, approved wording, caveats, disallowed claims, missing sources,
  and escalation triggers;
- produce a curated answer bundle;
- do not materialize the task pack as a source artifact.

Step 4 - response contract:

- agent drafts only within its response contract;
- include source artifact ids;
- include missing information and escalation when required;
- reject or ask for review if the answer would need unsupported claims.

### 12.3 Retrieval Scoring Inputs

Policy filtering is binary and always happens first. Scoring happens only among
allowed candidates.

Minimum ranking inputs:

| Signal | Direction |
| --- | --- |
| semantic similarity | higher is better |
| artifact type weight from task-pack recipe | task-required types rank higher |
| source ref proof grade | `canonical_internal` and `auditable_internal` rank above `manual_attestation` |
| source freshness | stale sources are penalized or denied by policy |
| artifact freshness | fresher is better after authority ties are resolved |
| quality band | higher quality band ranks higher |
| risk level | higher risk does not rank higher; it increases review/escalation pressure |
| exact title/id match | exact match boosts search-result bundles |

Ranking must not override policy denial. A highly similar restricted artifact
still stays denied in customer-facing mode.

### 12.4 Answer Bundle Contract

```yaml
bundle_id: bundle.sales_discovery.2026_05_07.acme
request_context_hash: sha256:3f1c6b7e9d9b2a51f4d0e42a6bb8d0b77fb80744f4b9c2f3d3a2f1f47d8b6a10
policy_decision: allowed
policy_reasons:
  - customer_safe_artifacts_only
facts:
  - artifact_id: kb.capability.sso
    claim: Supports SSO in approved deployment patterns.
caveats:
  - artifact_id: kb.capability.sso
    text: Final configuration details require implementation review.
disallowed_claims:
  - artifact_id: kb.disallowed.saml_every_plan
    text: Do not claim SAML is available in every plan.
missing_information:
  - exact plan tier requested by prospect
escalation_triggers:
  - asks_for_contractual_commitment
source_refs:
  - src.product.capability_registry
expires_at: 2026-05-21
```

## 13. Task Pack Recipes

Task packs are recipes in code/config, not knowledge folders. The
machine-readable recipe should declare artifact types, filters, required
sections, response contract, and fallback behavior.

Example TOML shape:

```toml
[[task_pack]]
id = "sales_discovery_pack"
agent_ids = ["sales_assistant", "stakeholder_map_assistant"]
response_contract = "sales_brief"
artifact_types = [
  "icp_profile",
  "segment_brief",
  "stakeholder_persona",
  "message_house_module",
  "objection_response",
  "capability_card",
  "pricing_rule",
  "roadmap_safe_wording",
  "disallowed_claim"
]
required_publishability = ["customer_safe", "internal"]
customer_facing_sections = ["Canonical Answer", "Approved Claims", "Safe Wording"]
always_check_disallowed_claims = true
fail_closed_if_missing_source_refs = true
```

Initial recipes:

| Recipe id | Primary agents | Required artifact types | Output contract |
| --- | --- | --- | --- |
| `sales_discovery_pack` | sales, stakeholder map | ICP, segments, personas, objections, capabilities, pricing, roadmap safe wording | sales brief |
| `customer_reply_pack` | customer replies, support | FAQ, known issues, support policy, capabilities, implementation patterns, disallowed claims | customer-facing answer |
| `security_questionnaire_pack` | security questionnaire, RFP | security modules, data handling, architecture positions, compliance positions, disallowed claims | security answer |
| `rfp_response_pack` | RFP, sales | RFP modules, approved claims, capabilities, pricing, security modules, legal summaries | customer-facing answer |
| `contract_review_pack` | contract analyzer | contract clause playbooks, fallback positions, risk glossary, pricing/legal rules | contract analysis |
| `executive_briefing_pack` | executive assistant | account summaries, active risks, tasks, allowed claims, recent decisions | internal analysis |
| `incident_rca_pack` | incident RCA, support | incident patterns, known issues, support policy, escalation, incident comms | internal analysis |
| `month_close_pack` | finance reporting | reporting rules, metric definitions, glossary, close calendar | internal analysis |
| `readiness_assessment_pack` | readiness expert | readiness rubrics, governance policies, risk rules, evidence refs | internal analysis |

## 14. Interaction Memory Boundary

Interaction memory is not canonical truth.

Examples:

- account briefs;
- call summaries;
- discovery notes;
- objection logs;
- product feedback snippets;
- win/loss notes;
- draft answers;
- incident working notes;
- task/project notes;
- month-close working papers.

Rules:

- Interaction memory must not live under `knowledge/business_agents/canonical`.
- Customer-facing retrieval may use interaction memory only as task-specific
  context, never as proof of company position.
- Memory results must be labeled `memory`, not `canonical`.
- Memory must have retention policy, account/workspace scope, source system,
  timestamp, and actor.
- Memory must support subject erasure workflows when it contains personal data.
- Memory can create candidate artifacts only through a review pipeline.
- A feedback synthesis can recommend a new canonical artifact, but cannot
  become one automatically.

Minimum memory record:

```yaml
id: memory.account.acme.2026_05_07
memory_type: call_summary
tenant_id: tenant.policyos_internal
workspace_id: ws.policyos
account_id: acct.acme
subject_ids:
  - person.customer_contact_123
created_at: 2026-05-07T12:00:00Z
created_by: user.sales
retention_until: 2026-11-07
subject_erasure_supported: true
visibility: internal
source_system: google_meet_notes
summary: Customer asked about SSO, data residency, and procurement timeline.
candidate_artifact_refs:
  - candidate.objection.data_residency
```

## 15. Source And Evidence Boundary

`source_refs` and `evidence_refs` intentionally answer different questions.

| Field | Meaning | Used for |
| --- | --- | --- |
| `source_refs` | Where the artifact author got the statement and what owner approved it | provenance, freshness, owner routing, typo-proof source resolution |
| `evidence_refs` | What can prove the statement to a reviewer, auditor, customer, or procurement process | security answers, legal/procurement review, trust exports |

For many security and legal artifacts, the same registry entry can appear in
both fields. That is allowed. The distinction still matters because some
sources are legitimate origins but not externally shareable evidence.

Evidence rules:

- `source_refs` are required for all production artifacts.
- `evidence_refs` are required for high-risk trust, legal, security, finance,
  and compliance artifacts.
- Every ref must resolve through `source_registry.toml`.
- If evidence is restricted, customer-facing answers may cite the canonical
  artifact id while withholding restricted evidence details.
- If source or evidence freshness changes, affected artifacts get a freshness
  event or review event.
- `source_refs` with `proof_grade = "unverified_context"` cannot support an
  approved artifact.

## 16. Freshness Policy

Freshness tiers:

| Tier | Default review interval | Examples |
| --- | --- | --- |
| `critical` | 14 days | pricing exceptions, security certifications, legal fallback language |
| `high` | 30 days | capabilities, roadmap safe wording, security answers |
| `medium` | 90 days | ICP, segment briefs, support policies, implementation patterns |
| `low` | 180 days | glossary, stable design principles, evergreen templates |

Rules:

- `review_due_at` is mandatory for approved artifacts.
- Artifacts past `review_due_at` are stale.
- Customer-facing agents must fail closed on stale `critical` and `high`
  artifacts.
- Internal agents may use stale artifacts only with a visible stale warning.
- `reviewed_no_change` updates `review_due_at` and adds an event.
- Freshness gates should align with the existing freshness protocol spirit from
  `docs/adr/0015-knowledge-bundle-freshness-protocol.md`.

## 17. Approval Policy Contract

Approval is a machine-readable contract, not a markdown-only matrix. The source
of truth after implementation is
`policy-engine/architecture/business_agent_approval.toml`; this section only
describes the intended shape.

Example:

```toml
[domains.product]
default_owner = "product"
backup_owner = "founder"
required_reviewers_customer_safe = ["product"]
restricted_requires_owner_approval = true
draft_author_can_self_approve = false

[domains.security]
default_owner = "security"
backup_owner = "founder"
required_reviewers_customer_safe = ["security"]
restricted_requires_owner_approval = true
draft_author_can_self_approve = false
high_risk_requires_second_reviewer = true

[domains.legal]
default_owner = "legal"
backup_owner = "founder"
required_reviewers_customer_safe = ["legal"]
restricted_requires_owner_approval = true
draft_author_can_self_approve = false
high_risk_requires_second_reviewer = true
```

Enforced approval rules:

- draft author cannot be the only approver for high-risk artifacts;
- restricted artifacts need explicit owner approval even for internal use by
  high-autonomy agents;
- customer-safe security, legal, pricing, finance, and roadmap artifacts require
  named reviewer refs;
- owner changes are lifecycle events;
- reviewers must block rather than silently edit if they cannot verify source
  refs;
- approval policy tests fail if an approved artifact's domain has no policy
  entry.

## 18. Redaction Policy

Customer-safe output must remove:

- internal notes;
- raw customer/account memory unless explicitly supplied for that customer;
- reviewer comments;
- internal risk labels unless response contract requires caveats;
- private source URLs;
- security implementation details beyond approved safe wording;
- legal fallback language marked restricted;
- roadmap candidates and unapproved dates;
- pricing exceptions not approved for the recipient.

Reviewer and machine exports may include restricted context, but must label
restricted fields and intended recipient or observer mode.

## 19. Agent Registry Principle

The complete per-agent specification belongs in
`policy-engine/architecture/business_agent_registry.toml`, not in this plan.
The registry is the canonical source for:

- stable `agent_id`;
- user-facing names and aliases;
- primary task categories;
- default task pack recipes;
- response contracts;
- memory access mode;
- customer-facing permission;
- restricted artifact handling;
- escalation routes.

Plan text may show examples, but it must not duplicate the full registry after
Phase 1.5 lands.

Example registry entries:

```toml
[[agents]]
id = "sales_assistant"
display_name_ru = "Ассистент по продажам"
category = "gtm"
default_task_packs = ["sales_discovery_pack"]
default_response_contract = "sales_brief"
memory_access = "account_context_only"
customer_facing_allowed = true
restricted_handling = "requires_human_review"
escalation_routes = ["product", "growth", "security"]

[[agents]]
id = "contract_terms_analyzer"
display_name_ru = "Анализ условий договора"
category = "legal_procurement"
default_task_packs = ["contract_review_pack"]
default_response_contract = "contract_analysis"
memory_access = "deal_context_only"
customer_facing_allowed = false
restricted_handling = "legal_owner_required"
escalation_routes = ["legal", "founder"]
```

Registry rules:

- every agent listed in Section 1 must have exactly one registry entry;
- every registry entry must point to an access policy entry;
- every customer-facing registry entry must point to a response contract;
- every high-risk category must define an escalation route;
- removing or renaming an agent id requires a compatibility note or migration
  event;
- this markdown plan should not be edited to update agent behavior after the
  registry exists.

## 20. MVP Content Seed

The first seed should be intentionally small:

### 20.1 Capability Cards

Seed 10 capability cards:

| id | title | domain |
| --- | --- | --- |
| `kb.capability.company_knowledge` | Company knowledge grounding | product/trust |
| `kb.capability.sso` | Single Sign-On support | product/security |
| `kb.capability.audit_trail` | Audit trail | product/trust |
| `kb.capability.role_based_access` | Role-based access | security |
| `kb.capability.decision_packets` | Decision packets | product |
| `kb.capability.evidence_fabric` | Evidence Fabric | product |
| `kb.capability.lex_knowledge` | Lex Knowledge | product/legal |
| `kb.capability.public_decision_viewer` | Public decision viewer | product |
| `kb.capability.export_pdf` | PDF/procurement export | product |
| `kb.capability.runtime_dashboard` | Runtime dashboard | product |

These are seed ids, not assertions that each feature is fully customer-safe.
Each must be backed by current source refs before approval.

### 20.2 Objection Responses

Seed 8 objections:

| id | title |
| --- | --- |
| `kb.objection.security_review_required` | "We need security review before evaluation" |
| `kb.objection.legal_procurement_slow` | "Legal/procurement will slow this down" |
| `kb.objection.need_data_residency` | "We need data residency clarity" |
| `kb.objection.no_budget_now` | "We do not have budget this quarter" |
| `kb.objection.build_internally` | "We can build this internally" |
| `kb.objection.ai_trust_concerns` | "We do not trust AI-generated recommendations" |
| `kb.objection.integration_effort` | "Integration sounds expensive" |
| `kb.objection.roadmap_uncertainty` | "We need a committed roadmap date" |

### 20.3 FAQ Cards

Seed 8 FAQ cards:

| id | title |
| --- | --- |
| `kb.faq.what_is_policyos` | What is PolicyOS? |
| `kb.faq.who_is_policyos_for` | Who is PolicyOS for? |
| `kb.faq.what_data_needed` | What data is needed to start? |
| `kb.faq.how_security_review_works` | How does security review work? |
| `kb.faq.how_support_escalates` | How support escalation works |
| `kb.faq.what_outputs_exist` | What outputs can PolicyOS produce? |
| `kb.faq.how_to_handle_rfp` | How to handle RFP requests |
| `kb.faq.how_to_discuss_roadmap` | How to discuss roadmap safely |

### 20.4 Disallowed Claims

Seed at least 8 typed guardrail artifacts:

| id | title |
| --- | --- |
| `kb.disallowed.saml_every_plan` | Do not claim SAML is available in every plan |
| `kb.disallowed.guaranteed_customer_rollout_date` | Do not guarantee customer-specific rollout dates |
| `kb.disallowed.compliance_certification_without_evidence` | Do not claim certifications without evidence |
| `kb.disallowed.security_control_absolute` | Do not make absolute security-control claims |
| `kb.disallowed.unapproved_data_residency` | Do not promise data residency without approved position |
| `kb.disallowed.fixed_support_sla_without_policy` | Do not promise support SLA outside support policy |
| `kb.disallowed.custom_pricing_commitment` | Do not quote custom pricing without approval |
| `kb.disallowed.competitor_superiority_without_evidence` | Do not claim competitor superiority without evidence |

## 21. Implementation Phases

### Phase 0 - Boundary ADR And Plan Acceptance

**Goal:** prevent the KB from becoming a second uncontrolled docs tree.

**Files:**

- Create: `policy-engine/docs/adr/NNNN-business-agent-kb-boundary.md`
- Modify: `policy-engine/docs/adr/index.toml` through existing ADR tooling if
  required
- Modify: `policy-engine/docs/adr/by-topic.md` through existing ADR tooling if
  required

- [ ] Step 0.1: Write ADR establishing that canonical business-agent knowledge
  lives under `policy-engine/knowledge/business_agents/canonical/**`, memory is
  separate runtime state, task packs are recipes, and access policies are
  computed from artifact properties.

- [ ] Step 0.2: Include compatibility with Claim Ledger vocabulary:
  `approved`, `blocked`, `superseded`, `reissued`, `withdrawn`.

- [ ] Step 0.3: Include the rule that no customer-facing retrieval may use
  stale, blocked, superseded, withdrawn, restricted, or source-less artifacts.

- [ ] Step 0.4: Include integration boundaries for Lex Knowledge,
  knowledge-search infrastructure, and Scientist Claim Ledger so business-agent
  KB does not fork or misuse existing systems.

- [ ] Step 0.5: Include the specification-eviction rule: durable behavior moves
  to ADR, schema, TOML, reference docs, and runbooks.

- [ ] Step 0.6: Run ADR/documentation checks used by the repo.

Expected output:

- ADR accepted or marked proposed with owner.
- This plan remains active until ADR and contracts are in place.

### Phase 1 - Minimal Contracts And Loader

**Goal:** create the smallest production-shaped artifact contract.

**Files:**

- Create: `policy-engine/schemas/knowledge/business_agent_artifact.schema.json`
- Create: `policy-engine/schemas/knowledge/business_agent_source_registry.schema.json`
- Create: `policy-engine/architecture/business_agent_artifact_types.toml`
- Create: `policy-engine/src/polisyos/business_agents/__init__.py`
- Create: `policy-engine/src/polisyos/business_agents/knowledge/artifacts.py`
- Create: `policy-engine/src/polisyos/business_agents/knowledge/loader.py`
- Create: `policy-engine/src/polisyos/business_agents/knowledge/source_registry.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_artifact_schema.py`

- [ ] Step 1.1: Define JSON Schema with required fields:
  `id`, `title`, `artifact_type`, `lifecycle_state`, `publishability`,
  `recipients`, `owner`, `review_due_at`, `domains`, `source_refs`.

- [ ] Step 1.2: Define `artifact_type` enum with MVP values:
  `capability_card`, `objection_response`, `faq_card`, and
  `disallowed_claim`.

- [ ] Step 1.3: Define Pydantic model in `artifacts.py` that mirrors the
  schema and forbids unknown required-shape fields only where safe.

- [ ] Step 1.4: Implement Markdown frontmatter loader in `loader.py`.

- [ ] Step 1.5: Add tests for valid artifact, missing owner, missing
  `review_due_at`, invalid lifecycle state, invalid publishability, and
  duplicated ids.

- [ ] Step 1.6: Define source registry schema and loader for
  `knowledge/business_agents/source_registry.toml`.

- [ ] Step 1.7: Add tests that approved artifacts cannot reference unknown
  source ids or `proof_grade = "unverified_context"`.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_artifact_schema.py -q
```

### Phase 1.5 - Registry, Approval, And Integration Contracts

**Goal:** move stable policy surfaces out of markdown before content seeding.

**Files:**

- Create: `policy-engine/architecture/business_agent_registry.toml`
- Create: `policy-engine/architecture/business_agent_approval.toml`
- Create: `policy-engine/architecture/business_agent_conflict_policy.toml`
- Create: `policy-engine/knowledge/business_agents/source_registry.toml`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_source_registry.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_approval_policy.py`

- [ ] Step 1.5.1: Add registry entries for the 24 agent ids from Section 1.

- [ ] Step 1.5.2: Add approval policy entries for product, commercial, pricing,
  security, legal, support, incident/change, people, marketing/design,
  analytics, and finance domains.

- [ ] Step 1.5.3: Add source registry entries for every source id used by the
  first seed artifacts.

- [ ] Step 1.5.4: Add conflict policy ordering: specialized domain artifacts
  outrank generic FAQ, high-risk conflicts escalate, freshness breaks ties only
  after domain authority and risk.

- [ ] Step 1.5.5: Document integration boundaries: reuse ADR/index conventions,
  claim-ledger lifecycle vocabulary, and common policy-filter ideas; do not
  store business artifacts inside Lex Knowledge or Scientist Claim Ledger.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_source_registry.py tests/unit/business_agents/knowledge/test_approval_policy.py -q
```

### Phase 2 - Canonical Artifact Store Skeleton

**Goal:** create the artifact repository without filling it with speculative
content.

**Files:**

- Create: `policy-engine/knowledge/business_agents/README.md`
- Create: `policy-engine/knowledge/business_agents/canonical/product/capability_cards/.gitkeep`
- Create: `policy-engine/knowledge/business_agents/canonical/commercial/objection_responses/.gitkeep`
- Create: `policy-engine/knowledge/business_agents/canonical/customer_ops/faq_cards/.gitkeep`
- Create: `policy-engine/knowledge/business_agents/fixtures/prompts/.gitkeep`
- Create: `policy-engine/knowledge/business_agents/fixtures/expected_bundles/.gitkeep`

- [ ] Step 2.1: Document authoring rules in `knowledge/business_agents/README.md`.

- [ ] Step 2.2: State that `canonical/**` accepts only artifacts that pass
  schema and source-ref checks.

- [ ] Step 2.3: State that interaction memory is prohibited in this tree.

- [ ] Step 2.4: State that generated indexes are derived and can be rebuilt.

Validation:

```bash
cd policy-engine
rg -n "call summary|account note|draft answer|working memory" knowledge/business_agents/canonical
```

Expected: no matches except explicit negative examples in README.

### Phase 3 - Access Policy Engine

**Goal:** compute access from artifact properties and agent policies.

**Files:**

- Create: `policy-engine/architecture/business_agent_access.toml`
- Create: `policy-engine/src/polisyos/business_agents/knowledge/policy.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_access_policy.py`

- [ ] Step 3.1: Add agent policy entries for all 24 agent ids.

- [ ] Step 3.2: For each policy, define allowed lifecycle states,
  publishability, domains, recipients, observer modes, max risk, and
  customer-facing mode.

- [ ] Step 3.3: Implement `evaluate_artifact_access(request_context, artifact)`.

- [ ] Step 3.4: Return structured decisions:
  `allowed`, `denied`, `requires_human_review`, with reason codes.

- [ ] Step 3.5: Test that no artifact needs an `agents_allowed` field.

Example denial reasons:

```text
blocked_lifecycle_state
publishability_not_allowed
recipient_not_allowed
observer_mode_not_allowed
risk_exceeds_agent_policy
artifact_stale
missing_source_refs
restricted_without_review_mode
```

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_access_policy.py -q
```

### Phase 4 - Retrieval Policy Filter

**Goal:** make fail-closed filtering the first retrieval step.

**Files:**

- Create: `policy-engine/src/polisyos/business_agents/knowledge/retrieval.py`
- Create: `policy-engine/src/polisyos/business_agents/knowledge/answer_bundle.py`
- Create: `policy-engine/src/polisyos/business_agents/knowledge/scoring.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_retrieval_policy_filter.py`

- [ ] Step 4.1: Define `BusinessAgentRetrievalRequest`.

- [ ] Step 4.2: Define `BusinessAgentRetrievalResult`.

- [ ] Step 4.3: Filter artifacts before text similarity ranking.

- [ ] Step 4.4: Always retrieve disallowed claims for customer-facing requests
  using typed `disallowed_claim` artifacts.

- [ ] Step 4.5: Add stale/fresh logic based on `review_due_at` and
  `freshness_tier`.

- [ ] Step 4.6: Test that customer-facing retrieval excludes draft, in-review,
  blocked, superseded, withdrawn, restricted, stale critical, and source-less
  artifacts.

- [ ] Step 4.7: Implement approved-vs-approved conflict detection and
  escalation when domain authority, risk, and freshness cannot resolve the
  conflict.

- [ ] Step 4.8: Implement scoring inputs in `scoring.py` without allowing
  scoring to override policy denial.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_retrieval_policy_filter.py -q
```

### Phase 5 - Task Pack Recipes And Assembly

**Goal:** assemble task context just in time without duplicating truth.

**Files:**

- Create: `policy-engine/architecture/business_agent_task_packs.toml`
- Create: `policy-engine/src/polisyos/business_agents/task_packs/__init__.py`
- Create: `policy-engine/src/polisyos/business_agents/task_packs/recipes.py`
- Create: `policy-engine/src/polisyos/business_agents/task_packs/assembler.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_task_pack_assembly.py`

- [ ] Step 5.1: Define recipes for `sales_discovery_pack`,
  `customer_reply_pack`, `security_questionnaire_pack`, and `rfp_response_pack`.

- [ ] Step 5.2: Implement recipe loading from TOML.

- [ ] Step 5.3: Implement assembly into answer bundle shape.

- [ ] Step 5.4: Add validation that task pack outputs contain artifact ids,
  caveats, missing info, disallowed claim checks, and escalation triggers.

- [ ] Step 5.5: Add validation that task pack outputs are not written back as
  canonical artifacts.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_task_pack_assembly.py -q
```

### Phase 6 - Response Contracts

**Goal:** prevent agents from emitting unstructured high-risk answers.

**Files:**

- Create: `policy-engine/schemas/knowledge/business_agent_answer_bundle.schema.json`
- Create: `policy-engine/schemas/knowledge/business_agent_search_result_bundle.schema.json`
- Create: `policy-engine/src/polisyos/business_agents/task_packs/response_contracts.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_response_contracts.py`

- [ ] Step 6.1: Define schemas for `customer_facing_answer`,
  `security_answer`, `contract_analysis`, `sales_brief`, and
  `internal_analysis`.

- [ ] Step 6.1a: Define `search_result_bundle` schema for
  `knowledge_search_assistant`.

- [ ] Step 6.2: Implement response contract validators.

- [ ] Step 6.3: Test that security answers require evidence refs.

- [ ] Step 6.4: Test that contract analysis requires legal review when risk is
  high or restricted artifacts are used.

- [ ] Step 6.5: Test that customer-facing answers include source artifact ids
  and disallowed-claim check results.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_response_contracts.py -q
```

### Phase 7 - Interaction Memory Separation

**Goal:** keep call notes, account notes, drafts, feedback, and working papers
out of canonical truth.

**Files:**

- Create: `policy-engine/schemas/knowledge/business_agent_memory.schema.json`
- Create: `policy-engine/src/polisyos/business_agents/memory/__init__.py`
- Create: `policy-engine/src/polisyos/business_agents/memory/models.py`
- Create: `policy-engine/src/polisyos/business_agents/memory/store.py`
- Create: `policy-engine/src/polisyos/business_agents/memory/retention.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_memory_separation.py`

- [ ] Step 7.1: Define memory record schema with workspace/account scope,
  source system, actor, timestamp, retention, subject ids, erasure support, and
  memory type.

- [ ] Step 7.2: Implement memory labels that distinguish `memory` from
  `canonical_artifact`.

- [ ] Step 7.3: Implement retention policy stubs with deterministic behavior.

- [ ] Step 7.4: Test that memory cannot satisfy a customer-facing source-ref
  requirement.

- [ ] Step 7.5: Test that memory can create candidate artifact proposals only
  through review workflow metadata.

- [ ] Step 7.6: Test subject erasure: memory records with matching
  `subject_ids` can be purged or tombstoned without touching canonical
  artifacts.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge/test_memory_separation.py -q
```

### Phase 8 - Seed MVP Artifacts

**Goal:** prove the system with a small set of real artifacts.

**Files:**

- Create: 10 Markdown files under
  `policy-engine/knowledge/business_agents/canonical/product/capability_cards/`
- Create: 8 Markdown files under
  `policy-engine/knowledge/business_agents/canonical/commercial/objection_responses/`
- Create: 8 Markdown files under
  `policy-engine/knowledge/business_agents/canonical/customer_ops/faq_cards/`
- Create: 8 Markdown files under
  `policy-engine/knowledge/business_agents/canonical/product/disallowed_claims/`
- Create: retrieval fixtures under
  `policy-engine/knowledge/business_agents/fixtures/prompts/`
- Create: expected bundles under
  `policy-engine/knowledge/business_agents/fixtures/expected_bundles/`

- [ ] Step 8.1: Create only artifacts backed by existing source refs.

- [ ] Step 8.2: Mark uncertain artifacts `draft` or `in_review`, not
  `approved`.

- [ ] Step 8.3: Create typed `disallowed_claim` artifacts and reference them
  from capability, objection, FAQ, and roadmap artifacts by id. Do not duplicate
  banned wording inline inside other artifact bodies.

- [ ] Step 8.4: Add three golden prompts:
  sales objection, customer support question, and security questionnaire item.

- [ ] Step 8.5: Validate expected bundles by policy filter before semantic
  quality tuning.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge -q
```

### Phase 9 - Expanded Artifact Types

**Goal:** add the 8-type MVP only after the first real tasks show the schema is
not fighting the work.

**Files:**

- Modify: `policy-engine/schemas/knowledge/business_agent_artifact.schema.json`
- Modify: `policy-engine/architecture/business_agent_artifact_types.toml`
- Add canonical directories for approved claims, pricing, security modules, RFP
  modules, contract playbooks, and roadmap safe wording.

- [ ] Step 9.1: Add `approved_claim`.

- [ ] Step 9.2: Add `pricing_rule`.

- [ ] Step 9.3: Add `security_answer_module`.

- [ ] Step 9.4: Add `contract_clause_playbook`.

- [ ] Step 9.5: Add `rfp_answer_module`.

- [ ] Step 9.6: Add `roadmap_safe_wording` with required sections:
  `Current Position`, `Allowed Future-Looking Language`, `Disallowed
  Commitments`, `Escalation`.

- [ ] Step 9.7: Add artifact-specific validation rules only where needed.

- [ ] Step 9.8: Add retrieval tests for disallowed claim conflict detection and
  approved-vs-approved conflict escalation.

Validation:

```bash
cd policy-engine
uv run pytest tests/unit/business_agents/knowledge -q
```

### Phase 10 - Governance Docs And Authoring Workflow

**Goal:** make the system usable by humans, not only validators.

**Files:**

- Create: `policy-engine/docs/reference/knowledge/business-agents.md`
- Create: `policy-engine/docs/how-to/business-agent-kb-authoring.md`
- Create: `policy-engine/docs/runbooks/business-agent-kb-governance.md`
- Modify: `policy-engine/mkdocs.yml` if this repo publishes the new pages

- [ ] Step 10.1: Document artifact anatomy.

- [ ] Step 10.2: Document lifecycle and publishability axes.

- [ ] Step 10.3: Document owner/reviewer process.

- [ ] Step 10.4: Document redaction and customer-safe authoring.

- [ ] Step 10.5: Document how memory becomes a candidate artifact.

- [ ] Step 10.6: Document source vs evidence refs, recipient vs observer modes,
  and approved-vs-approved conflict handling.

- [ ] Step 10.7: Document emergency block and reissue workflow.

- [ ] Step 10.8: Document specification eviction: which sections of this plan
  have moved into ADR, schema, TOML, reference docs, and runbooks.

Validation:

```bash
cd policy-engine
uv run --extra docs python -m mkdocs build --strict
```

### Phase 11 - Repo Quality Gates

**Goal:** prevent silent KB rot.

**Files:**

- Create: `policy-engine/tools/quality/validation/check_business_agent_kb.py`
- Create: `policy-engine/tests/repo_quality/architecture/test_business_agent_kb_contracts.py`
- Modify: tool registry only if repo convention requires exposing the checker

- [ ] Step 11.1: Check every artifact has required fields.

- [ ] Step 11.2: Check unique ids.

- [ ] Step 11.3: Check `source_refs` and `evidence_refs` resolve to source
  registry entries.

- [ ] Step 11.4: Check `owner` and `review_due_at` for approved artifacts.

- [ ] Step 11.5: Check approved artifacts satisfy
  `business_agent_approval.toml`, including reviewer count and self-approval
  restrictions.

- [ ] Step 11.6: Check every agent registry entry has access policy, task-pack
  recipe, response contract, and escalation route when required.

- [ ] Step 11.7: Check blocked/superseded/withdrawn artifacts are not selected
  by customer-facing fixtures.

- [ ] Step 11.8: Check no artifact frontmatter contains `agents_allowed`.

- [ ] Step 11.9: Check task packs are recipes, not duplicated answer bodies.

- [ ] Step 11.10: Check memory files are not committed under canonical paths.

- [ ] Step 11.11: Check typed `disallowed_claim` artifacts are used instead of
  inline banned wording in other artifact bodies.

Validation:

```bash
cd policy-engine
uv run python tools/quality/validation/check_business_agent_kb.py --repo-root . --output-format json
uv run pytest tests/repo_quality/architecture/test_business_agent_kb_contracts.py -q
```

### Phase 12 - Agent Pilot

**Goal:** validate with real high-frequency work before expanding ontology.

Pilot agents:

- `sales_assistant`;
- `customer_reply_drafter`;
- `security_questionnaire_assistant`;
- `rfp_response_manager`;
- `knowledge_search_assistant`.

- [ ] Step 12.1: Create 5 representative prompts per pilot agent.

- [ ] Step 12.1a: Store labeled policy-decision eval cases in
  `policy-engine/knowledge/business_agents/fixtures/evals/pilot_policy_decisions.v1.jsonl`.
  Each case must include prompt, agent id, recipient, expected policy decision,
  expected required artifacts, expected denied artifacts, expected escalation,
  labeler, and reviewed date.

- [ ] Step 12.2: Run retrieval and task pack assembly.

- [ ] Step 12.3: Review whether missing fields are real filtering needs or
  just nice-to-have metadata.

- [ ] Step 12.4: Record false positives, false negatives, blocked answers,
  stale artifacts, and escalation decisions.

- [ ] Step 12.5: Promote only fields and artifact types that solve observed
  retrieval/review problems.

Acceptance:

- at least 80 percent of versioned pilot eval cases produce the labeled policy
  decision and expected escalation behavior;
- 100 percent of customer-facing pilot outputs include source artifact ids;
- 100 percent of unsafe prompts fail closed or escalate;
- no output cites interaction memory as canonical truth.

### Phase 13 - Full Agent Coverage

**Goal:** extend coverage to the remaining agents without weakening policy.

- [ ] Step 13.1: Add task-pack recipes for executive, incident RCA, CAB,
  marketing strategy, product planning, design, software request, feedback,
  task management, finance close, and readiness assessment.

- [ ] Step 13.2: Add internal enablement artifact types only when recipe tests
  require them.

- [ ] Step 13.3: Add memory adapters for account, support, project, incident,
  and finance contexts with retention policies.

- [ ] Step 13.4: Add registry-linked golden prompts and eval cases for each
  enabled agent.

- [ ] Step 13.5: Run full KB gate before enabling customer-facing usage for any
  new agent.

Acceptance:

- every agent id has a policy entry;
- every customer-facing agent has a response contract;
- every high-risk agent has escalation triggers;
- every task-pack recipe has fixtures;
- memory separation tests pass.

### Phase 14 - Operational Rollout And Continuous Governance

**Goal:** make the KB an operating system, not a one-time documentation push.

- **Files:**

- Create: `policy-engine/schemas/knowledge/business_agent_observability_event.schema.json`
- Create: `policy-engine/src/polisyos/business_agents/governance/observability.py`
- Create: `policy-engine/tests/unit/business_agents/knowledge/test_observability_events.py`

- [ ] Step 14.1: Establish weekly review for critical/high freshness artifacts.

- [ ] Step 14.2: Establish monthly review for medium freshness artifacts.

- [ ] Step 14.3: Establish emergency block workflow with owner SLA.

- [ ] Step 14.4: Add KB drift report to docs/governance cadence.

- [ ] Step 14.5: Add review packets for proposed artifacts generated from
  feedback, support, sales calls, and RFP gaps.

- [ ] Step 14.6: Emit structured events for retrieval policy decisions, source
  ref resolution, conflicts, answer bundle assembly, response validation,
  memory use, subject erasure, human review, block, and reissue.

- [ ] Step 14.7: Add closeout report before moving this plan out of
  `docs/plans/active`.

Acceptance:

- there is a runbook for blocking/reissuing an artifact;
- stale critical/high artifacts are visible in a report;
- agent output logs include source artifact ids and policy decision reasons;
- plan exits to `accepted/` or archive with reference docs and contracts in
  place.

## 22. Machine-Readable Policy Examples

### 22.1 Agent Access TOML

```toml
[agents.sales_assistant]
allowed_lifecycle_states = ["approved"]
allowed_publishability = ["internal", "customer_safe"]
allowed_domains = ["product", "commercial", "trust"]
allowed_recipients = ["internal", "prospect", "customer"]
allowed_observer_modes = ["none", "reviewer"]
max_risk_level = "medium"
customer_facing_allowed = true
restricted_requires_review = true
stale_policy = "fail_closed_for_high_and_critical"

[agents.contract_terms_analyzer]
allowed_lifecycle_states = ["approved"]
allowed_publishability = ["internal", "restricted"]
allowed_domains = ["legal", "commercial", "trust"]
allowed_recipients = ["internal"]
allowed_observer_modes = ["none", "reviewer"]
max_risk_level = "critical"
customer_facing_allowed = false
restricted_requires_review = true
stale_policy = "warn_internal_fail_closed_external"
```

### 22.2 Source Registry TOML

```toml
[[sources]]
id = "src.product.capability_registry"
kind = "reference_doc"
owner = "product"
backup_owner = "founder"
path = "docs/reference/product/capability-registry.md"
visibility = "internal"
publishability = "customer_safe"
freshness_tier = "high"
review_due_at = "2026-06-30"
proof_grade = "canonical_internal"
```

### 22.3 Approval TOML

```toml
[domains.product]
default_owner = "product"
backup_owner = "founder"
required_reviewers_customer_safe = ["product"]
restricted_requires_owner_approval = true
draft_author_can_self_approve = false

[domains.legal]
default_owner = "legal"
backup_owner = "founder"
required_reviewers_customer_safe = ["legal"]
restricted_requires_owner_approval = true
draft_author_can_self_approve = false
high_risk_requires_second_reviewer = true
```

### 22.4 Conflict Policy TOML

```toml
[priority]
domain_specific_over_generic = true
freshness_breaks_ties_only_after_authority = true
high_risk_conflict_action = "requires_human_review"

[[domain_authority]]
task_domain = "security"
artifact_type_order = ["security_answer_module", "capability_card", "faq_card"]

[[domain_authority]]
task_domain = "legal"
artifact_type_order = ["contract_clause_playbook", "pricing_rule", "faq_card"]
```

### 22.5 Artifact Types TOML

```toml
[artifact_types.capability_card]
required_sections = ["Canonical Answer", "Approved Claims", "Disallowed Claim Refs", "Safe Wording", "Escalation"]
required_domains = ["product"]
customer_safe_allowed = true
default_freshness_tier = "high"

[artifact_types.disallowed_claim]
required_sections = ["Disallowed Claim", "Reason", "Safe Alternative", "Escalation"]
customer_safe_allowed = false
default_publishability = "internal"
default_freshness_tier = "high"

[artifact_types.roadmap_safe_wording]
required_sections = ["Current Position", "Allowed Future-Looking Language", "Disallowed Commitments", "Escalation"]
required_domains = ["product"]
customer_safe_allowed = true
default_freshness_tier = "critical"

[artifact_types.contract_clause_playbook]
required_sections = ["Position", "Risk", "Fallback Language", "Escalation"]
required_domains = ["legal"]
customer_safe_allowed = false
default_publishability = "restricted"
default_freshness_tier = "critical"
```

### 22.6 Freshness TOML

```toml
[freshness_tiers.critical]
review_interval_days = 14
customer_facing_on_stale = "deny"

[freshness_tiers.high]
review_interval_days = 30
customer_facing_on_stale = "deny"

[freshness_tiers.medium]
review_interval_days = 90
customer_facing_on_stale = "warn_and_escalate"

[freshness_tiers.low]
review_interval_days = 180
customer_facing_on_stale = "warn"
```

## 23. Observability Events

Continuous governance needs structured events, not only prose logs. The event
schema belongs in
`policy-engine/schemas/knowledge/business_agent_observability_event.schema.json`.

Minimum event shape:

```yaml
event_id: evt.business_kb.2026_05_07_000001
event_type: retrieval_policy_evaluated
occurred_at: 2026-05-07T12:00:00Z
tenant_id: tenant.policyos_internal
workspace_id: ws.policyos
agent_id: sales_assistant
request_id: req.123
artifact_ids:
  - kb.capability.sso
policy_decision: allowed
policy_reasons:
  - lifecycle_allowed
  - source_refs_resolved
source_refs:
  - src.product.capability_registry
human_review_required: false
```

Required event types:

| Event type | When emitted |
| --- | --- |
| `artifact_loaded` | loader parses canonical artifact |
| `source_ref_resolved` | source/evidence ref resolves or fails |
| `retrieval_policy_evaluated` | policy filter allows, denies, or escalates |
| `retrieval_candidates_ranked` | scoring ranks allowed candidates |
| `artifact_conflict_detected` | approved-vs-approved or approved-vs-disallowed conflict is found |
| `answer_bundle_assembled` | task pack recipe produces an answer bundle |
| `response_contract_validated` | output validates or fails validation |
| `human_review_requested` | restricted, stale, conflict, or high-risk path escalates |
| `memory_used_as_context` | memory participates as labeled context |
| `memory_erasure_requested` | subject erasure starts for memory records |
| `artifact_blocked` | owner blocks an artifact |
| `artifact_reissued` | blocked/superseded artifact is replaced |

Observability rules:

- customer-facing logs must include source artifact ids and policy reason codes;
- logs must not store full restricted evidence text unless the log sink is
  approved for restricted data;
- every denied candidate should record reason codes for drift analysis;
- answer bundle ids must link to retrieval request ids for audit.

## 24. Validation Matrix

| Gate | What it catches | Command |
| --- | --- | --- |
| Schema validation | malformed frontmatter and missing required fields | `uv run python tools/quality/validation/check_business_agent_kb.py --repo-root .` |
| Unit tests | policy/retrieval/task-pack logic | `uv run pytest tests/unit/business_agents/knowledge -q` |
| Repo quality | contracts, source registry, approval policy, no `agents_allowed`, no memory in canonical tree | `uv run pytest tests/repo_quality/architecture/test_business_agent_kb_contracts.py -q` |
| Docs build | reference/how-to/runbook publication | `uv run --extra docs python -m mkdocs build --strict` |
| Golden prompts | end-to-end bundles for representative tasks | `uv run pytest tests/unit/business_agents/knowledge/test_task_pack_assembly.py -q` |
| Manual review | content correctness and safe wording | owner review packet |

## 25. Migration Strategy

### 25.1 Inventory

- inventory current product docs, security docs, sales notes, RFP snippets,
  FAQ/support notes, contract positions, pricing notes, and design/marketing
  copy;
- classify each source as canonical candidate, evidence, memory, or output;
- reject sources that cannot be owned or dated.

### 25.2 Normalize

- convert high-frequency facts into atomic artifacts;
- keep original docs as source refs or evidence refs;
- create disallowed claims for unsafe old wording;
- mark uncertain content draft or in review.

### 25.3 Review

- route product/security/legal/pricing/support artifacts to owners;
- require source refs and review_due_at before approval;
- block risky claims first, then reissue safe replacements.

### 25.4 Pilot

- run pilot prompts for five agents;
- measure retrieval misses and unsafe answers;
- add fields/types only when misses prove the need.

### 25.5 Promote

- enable customer-facing agents only after gates pass;
- export reference docs and runbooks;
- move plan to accepted when implementation is in progress and stable contracts
  exist.

## 26. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Ontology grows before use cases prove it | slow authoring, low adoption | start with 3 artifact types and add only after pilot misses |
| Task packs become copied facts | silent drift | recipes only, generated bundles not stored as truth |
| Memory leaks into customer answers | unsafe false authority | separate store, labels, tests, no memory under canonical tree |
| Artifact access enumerates agents | migration pain for every new agent | compute access from properties and policies |
| Lifecycle mixes with visibility | impossible states | separate `lifecycle_state` and `publishability` |
| Owners do not review artifacts | stale facts | owner and `review_due_at` hard gate |
| Security/legal facts overexposed | procurement or legal risk | restricted publishability and escalation triggers |
| Disallowed claims omitted | agents overpromise | retrieve disallowed claims for customer-facing tasks |
| Disallowed claims duplicated inline | two banned-wording sources diverge | require typed `disallowed_claim` artifacts and refs |
| Source refs become typo-tolerant strings | false provenance confidence | source registry schema and source-ref resolution gate |
| Approval remains ceremonial | unsafe artifacts get approved without reviewers | machine-readable approval TOML and repo-quality tests |
| Approved artifacts conflict | agents blend contradictory answers | domain authority, risk, freshness conflict policy and escalation |
| Memory subject erasure missing | privacy/compliance exposure | subject ids, erasure workflow, retention tests |
| Pilot metrics become subjective | false launch confidence | versioned labeled eval set with reviewer/date metadata |
| Observability is incomplete | drift cannot be debugged | structured governance events with policy reason codes |
| Index becomes source of truth | stale generated data | index is derived and rebuildable |
| Plan becomes permanent docs | second source of truth | closeout requires reference docs, schemas, ADR, and runbook |

## 27. Exit Criteria

This plan can move out of `active/` only when:

1. Boundary ADR exists and references this plan.
2. Artifact schema exists under `schemas/knowledge/**`.
3. Source registry exists and source-ref resolution is enforced.
4. Agent registry, access policy, approval policy, conflict policy, and
   freshness policy exist under `architecture/**`.
5. Task-pack recipe contract exists under `architecture/**` or
   `src/polisyos/business_agents/task_packs/**`.
6. Canonical artifact store exists under `knowledge/business_agents/**`.
7. Interaction memory has a separate runtime contract, subject-erasure support,
   and no canonical indexing.
8. The MVP artifact types have seed artifacts and owner review, including typed
   `disallowed_claim` artifacts.
9. At least four task-pack recipes produce answer bundles from current
   artifacts.
10. Customer-facing retrieval fails closed for blocked, superseded, withdrawn,
   stale high-risk, restricted, and source-less artifacts.
11. Approved-vs-approved conflicts are detected and escalated when unresolved.
12. Reference docs, authoring how-to, and governance runbook exist.
13. Repo quality gates pass.
14. Pilot eval set is versioned and labeled.
15. Observability event schema and reason-code logging exist.
16. Closeout report states what became source of truth and where.

## 28. Immediate Next Actions

Recommended first work package:

- [ ] Create the boundary ADR.
- [ ] Create minimal schema for the three task-facing MVP artifact types plus
  typed `disallowed_claim`.
- [ ] Create source registry schema and initial
  `knowledge/business_agents/source_registry.toml`.
- [ ] Create `business_agent_registry.toml` for the 24 agent ids.
- [ ] Create access policy TOML for the five pilot agents.
- [ ] Create approval policy TOML before seeding any approved artifacts.
- [ ] Add the Lex Knowledge / Claim Ledger / knowledge-search integration
  boundary to the ADR.
- [ ] Create loader and schema tests.
- [ ] Create four seed artifacts: one capability card, one objection response,
  one FAQ card, and one typed disallowed claim.
- [ ] Run the sales/customer/security pilot prompts.
- [ ] Decide whether the next expansion should be `approved_claim` plus
  `security_answer_module`, since `disallowed_claim` is already in the MVP
  guardrail set.

This keeps the architecture aligned with the larger vision while forcing early
feedback from real agent work.
