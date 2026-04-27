# PolicyOS Scientist - Best-in-Class Plan

> Дата: 2026-04-26  
> Статус: active proposal  
> Владелец: Denis Kopylov  
> Область: `policy-engine/src/polisyos/scientist/**`  
> Companion docs:  
> - `docs/reference/scientist/index.md` - factual reference surface  
> - `docs/reference/scientist/remediation-status.md` - current Phase 0-4 closure  
> - `docs/SCIENTIST_AUDIT_REMEDIATION_PLAN.md` - historical audit remediation plan  
> - `docs/reference/scientist/best-in-class-readiness.md` - Phase 1.0 readiness index  
> - `docs/reference/scientist/scientist-capability-inventory.md` - Phase 1.0 inventory and reconciliation map  
> - `docs/archive/plans/SCIENTIST_SOTA_ROADMAP.md` - historical SOTA roadmap  
> - `docs/archive/plans/SCIENTIST_AGENT_SOTA_ROADMAP.md` - historical agent roadmap  
> - `docs/archive/plans/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md` - historical autoresearch blueprint  
> - `docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md` - sibling frontend/design best-in-class plan  
> - `docs/archive/plans/FOUNDRY_METHODS_RESEARCH_AGENDA.md` - sibling methods research agenda  
> - `docs/archive/plans/CAUSAL_ENGINE_RESEARCH_AGENDA.md` - sibling causal research agenda

---

## Оглавление

- [0. TL;DR и тезис](#0-tldr-и-тезис)
- [1. Почему нужен новый план](#1-почему-нужен-новый-план)
- [2. Внешние источники и что берем из них](#2-внешние-источники-и-что-берем-из-них)
- [3. Диагноз текущего состояния](#3-диагноз-текущего-состояния)
- [4. Сквозные законы Scientist](#4-сквозные-законы-scientist)
- [5. Архитектура двух волн](#5-архитектура-двух-волн)
- [6. Волна 1 - Claim-Safe SOTA Closure](#6-волна-1---claim-safe-sota-closure)
  - [Фаза 1.0 - Status reconciliation](#фаза-10---status-reconciliation)
  - [Фаза 1.1 - Claim/Evidence/Readiness spine](#фаза-11---claimevidencereadiness-spine)
  - [Фаза 1.2 - Research DAG as first-class runtime object](#фаза-12---research-dag-as-first-class-runtime-object)
  - [Фаза 1.3 - Deep research evidence stack](#фаза-13---deep-research-evidence-stack)
  - [Фаза 1.4 - Agent and tool runtime promotion gates](#фаза-14---agent-and-tool-runtime-promotion-gates)
  - [Фаза 1.5 - Benchmark authority and hidden eval packs](#фаза-15---benchmark-authority-and-hidden-eval-packs)
  - [Фаза 1.6 - Human oversight and accountable release packets](#фаза-16---human-oversight-and-accountable-release-packets)
  - [Фаза 1.7 - Wave 1 closeout](#фаза-17---wave-1-closeout)
- [7. Волна 2 - Best-in-Class Primitives](#7-волна-2---best-in-class-primitives)
  - [Фаза 2.0 - Scientist OS foundation](#фаза-20---scientist-os-foundation)
  - [Фаза 2.1 - Claim Ledger](#фаза-21---claim-ledger)
  - [Фаза 2.2 - Research DAG replay and comparison](#фаза-22---research-dag-replay-and-comparison)
  - [Фаза 2.3 - VOI scheduler](#фаза-23---voi-scheduler)
  - [Фаза 2.4 - Reflexive memory and failure intelligence](#фаза-24---reflexive-memory-and-failure-intelligence)
  - [Фаза 2.5 - Adversarial challenge factory](#фаза-25---adversarial-challenge-factory)
  - [Фаза 2.6 - Continuous governance and reissue loop](#фаза-26---continuous-governance-and-reissue-loop)
  - [Фаза 2.7 - Decision-grade research compiler](#фаза-27---decision-grade-research-compiler)
  - [Фаза 2.8 - System closeout](#фаза-28---system-closeout)
- [8. Research-first companion agenda](#8-research-first-companion-agenda)
- [9. Success metrics](#9-success-metrics)
- [10. Risks and mitigations](#10-risks-and-mitigations)
- [11. Source bibliography](#11-source-bibliography)

---

## 0. TL;DR и тезис

`polisyos.scientist` не должен становиться "самым автономным агентом".
Best-in-class версия Scientist должна стать **governed research operating
system**: системой, которая производит проверяемые policy research artifacts,
умеет доказывать, сомневаться, блокировать себя, учиться на провалах и
объяснять границы каждого вывода.

Главный системный закон:

> **No naked claims.**
> Любое утверждение, рекомендация, policy option, causal statement,
> legal/compliance claim или research conclusion обязаны иметь typed support:
> evidence refs, provenance, uncertainty, counterevidence, freshness,
> decision-readiness status, actor/source attribution и publishability gate.

В текущем коде уже есть сильный капитал:

- workflow runtime, async DAG, checkpoint/resume, distributed runner contracts;
- 44 builtin nodes и пять routed workflows;
- governance passes, calibration/accountability artifacts, frontier runtime gates;
- search/autotune/funnel/pareto primitives;
- agent roles, tool loop, supervisor, reflexion, eval harness;
- CAS/provenance/replay/reliability scorecard;
- Phase 0-4 closure уже отражена в `docs/reference/scientist/remediation-status.md`.

Но это пока **claim-safe SOTA substrate**, а не category-defining product
primitive. Разрыв до best-in-class лежит не в количестве методов, а в пяти вещах:

1. Claims пока не являются единым первичным объектом runtime.
2. Research process пока не является полностью replayable DAG с typed
   evidence/counterevidence ledger.
3. Frontier capabilities остаются gated, но promotion не объединен в один
   decision-readiness authority для всех подсистем.
4. Agent/deep-research слой еще не является production-grade evidence factory.
5. У системы нет сильного reflexive loop: failures, hidden evals, human review,
   post-deployment drift и reissue должны замыкаться в обучение платформы.

План строится как две волны:

- **Волна 1 - Claim-Safe SOTA Closure**: привести Scientist к единому claim,
  evidence, readiness, research DAG и benchmark authority контракту.
- **Волна 2 - Best-in-Class Primitives**: сделать Claim Ledger, Research DAG,
  VOI Scheduler, Reflexive Memory, Adversarial Challenge Factory и Continuous
  Governance теми примитивами, по которым категорию потом будут сравнивать.

Общая оценка: **24-32 недели** для одного сильного backend/platform инженера с
точечным подключением research, security/compliance и product/design review.

---

## 1. Почему нужен новый план

Исторические Scientist планы уже сделали важную работу:

- `SCIENTIST_SOTA_ROADMAP.md` был remediation/SOTA планом для engine,
  governance, observability, testing, distributed execution, LLM, DOE, search.
- `SCIENTIST_AGENT_SOTA_ROADMAP.md` был отдельным агентным gap analysis:
  tool calling, web research, supervisor-worker, Reflexion, provider semantics.
- `SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md` сформулировал три слоя:
  Core Platform, Policy Design App, Discovery App.

Текущая reference-документация говорит, что Phase 0-4 workstreams закрыты:
`WS-0A` - `WS-4B` имеют статус `done`, reliability scorecard и frontier runtime
уже machine-readable. Поэтому новый план не должен повторять старые tickets.

Новая цель:

- не "довести reliability до 9/10";
- не "включить больше LLM tricks";
- не "добавить еще один агентный framework";
- а **сделать Scientist платформой, где policy research можно продвигать от
  черновика до decision-grade вывода через прозрачную, воспроизводимую и
  юридически объяснимую цепочку evidence, tests, governance и human oversight**.

---

## 2. Внешние источники и что берем из них

Документ опирается на публичные primary sources, official docs и research papers,
проверенные 2026-04-26.

| Источник | Что берем в Scientist |
| --- | --- |
| Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Простые composable workflows важнее тяжелых frameworks; parallelization, routing, evaluator-optimizer и orchestrator-workers включаются только когда evals показывают пользу. |
| Anthropic, [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Search как compression problem; subagents работают в отдельных context windows; lead agent синтезирует; качество держится на evals, tool design и operational discipline. |
| Anthropic, [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | Tool interface - это product/API design: маленький набор high-impact tools, strict schemas, response caps, helpful errors, eval-driven iteration. |
| Anthropic, [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Context state - это runtime object: tools, memory, external data, message history и subagent isolation нужно управлять как ресурсом. |
| OpenAI, [Deep research API guide](https://developers.openai.com/api/docs/guides/deep-research) | Deep research должен иметь staged workflow, logging/review of tool calls, prompt-injection controls, separation public web/private data, citations. |
| OpenAI, [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) и [Agent evals](https://developers.openai.com/api/docs/guides/agent-evals) | Agent rollout должен измерять instruction following, tool selection, argument precision, handoff accuracy, functional correctness, traces и graders. |
| Google, [Gemini Deep Research Agent](https://ai.google.dev/gemini-api/docs/deep-research) | Long-running research должен быть background job с polling/streaming, planning, search/read/reason loop, citations, explicit unknown handling и cost model. |
| OpenAI, [BrowseComp](https://openai.com/index/browsecomp/) | Web agents нужно оценивать не только на простых facts, а на hard-to-find multi-hop retrieval; benchmark leakage нужно защищать. |
| OpenAI, [SimpleQA](https://openai.com/index/introducing-simpleqa/) | Для factuality нужны simple, low-variance, easy-to-grade evals, но они покрывают только узкий класс factual claims. |
| Deep Research Bench, [arXiv:2506.06287](https://arxiv.org/abs/2506.06287) | Для web research полезен frozen/offline web environment, чтобы сравнивать agents во времени и измерять hallucinations, tool use, forgetting. |
| SWE-bench Verified, [official benchmark](https://www.swebench.com/verified.html) | Human-validated subsets и фиксированные harness версии важны для честной оценки agent scaffolds. |
| NIST, [AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) | Risk management должен быть lifecycle practice: govern, map, measure, manage; evaluation, provenance, incident handling и monitoring должны быть встроены. |
| OECD, [AI Principles](https://www.oecd.org/en/topics/ai-principles.html) | Trustworthy AI требует transparency, robustness, safety, accountability и ongoing risk management. |
| EU AI Act guidance, [European Commission FAQ](https://digital-strategy.ec.europa.eu/en/faqs/navigating-ai-act) и [Article 14 human oversight](https://artificialintelligenceact.eu/article/14/) | Для high-risk use cases нужны traceability, documentation, human oversight, ability to override/interrupt, monitoring, representative input data и right-to-explanation posture. |

Практический вывод:

- best-in-class Scientist должен быть **eval-first**, **evidence-first**,
  **claim-bound**, **human-overridable**, **replayable**, **cost-aware** и
  **safe under adversarial/untrusted inputs**.

---

## 3. Диагноз текущего состояния

### 3.1. Капитал, который не ломаем

| Слой | Текущий капитал | Почему это ценно |
| --- | --- | --- |
| Public facade | `run_experiment(...)`, `ExperimentState`, routed workflows | Один понятный entrypoint для orchestration. |
| Workflow runtime | `WorkflowSpec`, `NodeInvocation`, async executor, runner backends | Можно строить research DAG без нового framework. |
| Builtin nodes | 44 nodes across data/planning/compile/causal/simulate/governance/decide | Уже есть production-shaped policy pipeline. |
| Governance | pass registry, profiles, accountability, calibration, stress scenarios | Отличный фундамент для claim gates. |
| Search/autotune | funnel, pareto, benchmark registry, VOI scheduler, lessons | Уже почти есть platform layer для promotion. |
| Agent layer | PI/Drafter/Formalizer/Critic, supervisor, tool loop, Reflexion, eval harness | Есть агентный капитал, который надо дисциплинировать. |
| Frontier runtime | `disabled/offline_gated/available_offline/experimental_not_wired` statuses | Хорошая claim discipline для advanced methods. |
| Reliability gates | scorecard, Phase 0/1/2 gates, operational evidence | Machine-checked closure уже стала культурой. |
| Provenance/replay | CAS refs, run DAG, replay/diff, checkpoint/resume | Основа для audit-grade research process. |

### 3.2. Главные пробелы до best-in-class

| # | Пробел | Последствие | Фазы |
| --- | --- | --- | --- |
| G1 | Claims не являются единым runtime object | Decision packet может агрегировать выводы, но не все выводы имеют одинаковый support contract | 1.1, 2.1 |
| G2 | Research DAG не является first-class artifact | Нельзя полноценно сравнить, переиграть и объяснить исследовательскую траекторию | 1.2, 2.2 |
| G3 | Deep research source pipeline недостаточно первичен | Web/scholar evidence не становится snippet-level claim support ledger по умолчанию | 1.3 |
| G4 | Agent/tool rollout разбросан между несколькими отчетами | Сложно понять, какая agent capability реально default-eligible | 1.4 |
| G5 | Benchmark authority еще не единый для всех claim families | Frontier, agent, policy-design, governance и causal use different gates | 1.5 |
| G6 | Human oversight есть как governance surface, но не как release primitive | Для public-sector/high-risk use cases нужен review packet, override, interrupt и right-to-explanation posture | 1.6 |
| G7 | VOI scheduler не стал главным compute law | Expensive eval/search/human escalation не всегда выбираются по expected value of information | 2.3 |
| G8 | Reflexive memory не замыкает failures в future runs | Система может оставаться reliable, но не становиться умнее от failure cards | 2.4 |
| G9 | Adversarial challenge generation не является постоянной фабрикой | Hidden holdouts и challenge packs требуют ручного lifecycle | 2.5 |
| G10 | Continuous governance и reissue не замкнуты в один loop | Post-deployment drift не становится автоматическим decision-validity lifecycle | 2.6 |

### 3.3. Что означает "best-in-class" для Scientist

Scientist best-in-class - это не model leaderboard. Это способность системы:

1. Выпускать policy research artifacts с machine-checkable границами claims.
2. Показывать, какие evidence и counterevidence поддерживают каждое утверждение.
3. Воспроизводить research trajectory: search, tools, sources, decisions, failures.
4. Дешево отбрасывать слабые candidates и дорого проверять только то, что имеет VOI.
5. Продвигать frontier capabilities только после hidden evals, shadow runs и explicit approval.
6. Держать human oversight как активный control plane, а не документальную приписку.
7. Обновлять, отзывать или переиздавать decisions при drift, source invalidation или policy-context change.

---

## 4. Сквозные законы Scientist

Эти инварианты применяются ко всем фазам.

### 4.1. No naked claims

Запрещено публиковать или повышать readiness любого claim без:

- `claim_id`;
- `claim_type`;
- `supporting_evidence_refs`;
- `counterevidence_refs`;
- `uncertainty_profile`;
- `freshness_profile`;
- `source_attribution`;
- `provenance_ref`;
- `decision_readiness`;
- `publishability_status`;
- `human_review_status` для high-impact/high-risk claims.

### 4.2. Research is a DAG, not a transcript

LLM messages, tool calls, web searches, source reads, extraction, verifier
passes, synthesis, critique, human review и decision publication должны
сохраняться как typed DAG nodes/edges, а не как loose chat log.

### 4.3. Frontier is non-default until proven

Любая advanced capability остается non-default, пока нет:

- offline validation ref;
- benchmark pack ref;
- hidden holdout evidence;
- rotating challenge evidence;
- baseline comparison;
- governance approval;
- explicit baseline replacement approval.

### 4.4. Evals drive architecture

Multi-agent, tree search, LATS, learned routing, deep research fan-out и VOI
policy включаются только после comparative evals. Нельзя добавлять agentic
complexity как стиль.

### 4.5. Context is governed state

Каждый context injection должен иметь source, scope, TTL, sensitivity, trust
tier и reason for inclusion. Retrieved web text is untrusted data, not
instructions.

### 4.6. Human oversight must be operational

Для high-risk policy decisions система должна поддерживать:

- stop/interrupt;
- override/disregard;
- human review assignment;
- explanation packet;
- two-person verification option;
- post-deployment monitoring and reissue.

### 4.7. Fail closed on publication, degrade open on exploration

Exploration может деградировать и продолжать run с explicit degraded envelopes.
Publication и readiness promotion должны fail closed.

---

## 5. Архитектура двух волн

### 5.0. Execution detail policy

Этот план является единственным активным source of truth для Scientist
best-in-class work. Детализация фаз живет прямо здесь, без отдельных папок и
дополнительных phase-файлов.

Фазы, которые уже можно исполнять без дополнительного research result,
детализируются по единому встроенному шаблону:

- goal;
- preconditions;
- non-goals;
- existing code and test surfaces;
- new or extended contracts;
- work packages;
- migration plan;
- feature flags;
- acceptance and negative tests;
- CI gate;
- rollout;
- kill rules.

Правило обновления: если у фазы появляется новая execution-level информация, ее
нужно добавлять в соответствующую фазу этого документа. Отдельные execution
bundle папки не создаем, пока явно не появится потребность в машинно
исполняемых спецификациях.

### 5.1. Wave 1 gate

Wave 1 закрыта только если:

- есть единый `ClaimRecord`/`EvidenceRecord`/`DecisionReadiness` контракт;
- все decision-bearing Scientist outputs мапятся на claim ledger или explicitly
  marked non-claiming;
- research DAG artifact создается для at least `scientist_policy_design`,
  `scientist_policy_verified`, `scientist_causal_full`;
- deep research evidence bundle хранит query trace, source list, snippets,
  claim-to-source support и fetch safety metadata;
- agent/tool capabilities имеют unified promotion report;
- benchmark authority умеет проверять hidden holdout, rotating challenges,
  sentinel candidates и leakage guard;
- human review packet включен в high-risk/public-sector release path;
- docs/reference обновлены и есть CI gate.

### 5.2. Wave 2 gate

Wave 2 закрыта только если:

- Claim Ledger стал primary decision artifact;
- Research DAG replay/diff работает между runs;
- VOI scheduler управляет expensive eval, search, source verification и human escalation;
- Reflexive Memory measurable улучшает recovery/retry behavior;
- Adversarial Challenge Factory регулярно производит новые challenge packs;
- Continuous Governance loop умеет trigger reissue/withdrawal;
- success metrics показывают lift над Wave 1 baseline без роста unsafe publication rate.

### 5.3. Feature flags

Каждая фаза вводит feature flags в формате:

```text
scientist.best_in_class.wave{N}.phase{M}.{slug}
```

Правила:

- production default: off;
- development/staging: on после acceptance;
- shadow mode обязателен для фаз, влияющих на publication, search selection,
  governance, human review или baseline replacement;
- flag удаляется только после двух релизов stable behavior и documented migration.

---

## 6. Волна 1 - Claim-Safe SOTA Closure

## Фаза 1.0 - Status reconciliation

**Длительность:** 1-2 недели.  
**Тезис:** перед новой архитектурой нужно зафиксировать, что старые Scientist
планы уже закрыты, что реально живет в коде, а что остается gated/backlog.
**Implementation status:** `closed` by
`docs/reference/scientist/best-in-class-readiness.md`,
`docs/reference/scientist/scientist-capability-inventory.md`, and
`tools/ci/check_scientist_best_in_class_phase1_0.py`.

### Scope

- Инвентаризация `src/polisyos/scientist/**`, `tests/scientist/**`,
  `docs/reference/scientist/**`.
- Маппинг старых roadmap workstreams в current reference/gate status.
- Новый canonical active plan index.

### Deliverables

```text
policy-engine/docs/reference/scientist/best-in-class-readiness.md
policy-engine/docs/reference/scientist/scientist-capability-inventory.md
policy-engine/tools/ci/check_scientist_best_in_class_phase1_0.py
policy-engine/tests/tools/test_scientist_best_in_class_phase1_0.py
```

### Acceptance criteria

- `best-in-class-readiness.md` перечисляет все active Scientist capability
  families и их current readiness.
- Каждый historically planned item из historical Scientist plan docs имеет статус:
  `closed`, `superseded`, `still_gated`, `research_first`, `not_in_scope`.
- Нет новой реализации, только source-of-truth reconciliation.

---

## Фаза 1.1 - Claim/Evidence/Readiness spine

**Длительность:** 3-4 недели.  
**Тезис:** claims становятся typed runtime objects, а не prose inside reports.
**Implementation status:** `closed` by
`src/polisyos/scientist/claims/**`,
`docs/reference/scientist/claims.md`,
`tools/ci/check_scientist_best_in_class_phase1_1.py`, and the
`claims_ref` integrations in decision packet, policy output, governance,
causal validity and frontier runtime surfaces.

### Scope

- Единый claim model.
- Evidence/counterevidence model.
- Decision readiness ladder.
- Projection into decision packets, governance reports, causal validity bundles,
  policy output bundles.

### Proposed contracts

Important compatibility rule: this phase extends the existing
`polisyos.scientist.search.readiness.DecisionReadinessContract`; it does not
replace it. Current readiness levels in
`src/polisyos/scientist/search/readiness.py` remain the public readiness ladder
for promoted policy artifacts. The new claim spine adds claim-level support,
counterevidence, provenance and publishability.

```python
class ClaimType(str, Enum):
    FACTUAL = "factual"
    CAUSAL = "causal"
    LEGAL = "legal"
    NORMATIVE = "normative"
    FORECAST = "forecast"
    DISTRIBUTIONAL = "distributional"
    WELFARE = "welfare"
    IMPLEMENTATION = "implementation"
    SOURCE_QUALITY = "source_quality"


class ClaimSupportStatus(str, Enum):
    UNSUPPORTED = "unsupported"
    WEAKLY_SUPPORTED = "weakly_supported"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"
    NOT_EVALUABLE = "not_evaluable"


class ClaimPublishability(str, Enum):
    DRAFT = "draft"
    INTERNAL_ONLY = "internal_only"
    REVIEW_REQUIRED = "review_required"
    PUBLISHABLE = "publishable"
    BLOCKED = "blocked"


class ClaimRecord(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    claim_id: str
    run_id: str
    claim_type: ClaimType
    text: str
    normalized_subject: str | None = None
    support_status: ClaimSupportStatus
    publishability: ClaimPublishability
    readiness_level: DecisionReadiness
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    counterevidence_refs: list[ArtifactRef] = Field(default_factory=list)
    uncertainty_profile_ref: ArtifactRef | None = None
    provenance_ref: ArtifactRef | None = None
    source_attribution: list[str] = Field(default_factory=list)
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ClaimLedger(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    claims: list[ClaimRecord] = Field(default_factory=list)
    decision_readiness_ref: ArtifactRef | None = None
    source_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_by_node_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
```

### Deliverables

```text
policy-engine/src/polisyos/scientist/claims/
├── __init__.py
├── models.py
├── ledger.py
├── readiness.py
├── projections.py
└── validators.py

policy-engine/docs/reference/scientist/claims.md
policy-engine/tests/scientist/claims/
├── test_models.py
├── test_readiness.py
├── test_ledger.py
└── test_projections.py

policy-engine/tools/ci/check_scientist_best_in_class_phase1_1.py
policy-engine/tests/tools/test_scientist_best_in_class_phase1_1.py
```

### Integration targets

- `nodes/builtins/decide/build_decision_packet.py`
- `nodes/builtins/decide/build_policy_output_bundle.py`
- `nodes/builtins/simulate/run_causal_evaluation.py`
- `governance/report.py`
- `governance/accountability.py`
- `causal/validity.py`
- `frontier_runtime.py`

### Acceptance criteria

- Every decision packet contains `claims_ref`.
- Governance blocks publication if decision-bearing fields exist without
  claim projection.
- Existing tests stay green.
- New gate rejects naked decision claims in selected hot paths.

### Execution details

#### Preconditions

- `docs/reference/scientist/remediation-status.md` still reports Phase 0-4 done.
- Current Scientist workflow, governance and decision packet tests are green.
- Existing readiness code is treated as source of truth:
  `src/polisyos/scientist/search/readiness.py`.
- Existing legal and policy claims are inventoried from
  `policy_verified/models.py`, `policy_design/output.py`, decision packet
  builders and governance reports.

Minimum baseline:

```bash
uv run pytest tests/scientist/test_decision_packet_node_v3.py tests/scientist/nodes/test_build_policy_output_bundle.py -q
uv run pytest tests/scientist/search/test_phase_b_policy_runtime.py tests/scientist/search/test_benchmark_registry.py -q
```

#### Non-goals

- Do not redesign every policy output artifact in this phase.
- Do not remove or rename existing `DecisionReadiness` levels.
- Do not require every sentence in a public summary to be a claim.
- Do not solve citation faithfulness scoring; Phase 1.3 and Phase 1.5 own that.
- Do not make hidden benchmark evidence visible in public artifacts.

#### Existing surfaces

```text
src/polisyos/scientist/search/readiness.py
src/polisyos/scientist/policy_verified/models.py
src/polisyos/scientist/policy_verified/service.py
src/polisyos/scientist/policy_design/output.py
src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py
src/polisyos/scientist/nodes/builtins/decide/build_policy_output_bundle.py
src/polisyos/scientist/nodes/builtins/decide/build_verified_policy_report.py
src/polisyos/scientist/governance/report.py
src/polisyos/scientist/governance/accountability.py
src/polisyos/scientist/causal/validity.py
src/polisyos/scientist/frontier_runtime.py
```

Existing tests to preserve and extend:

```text
tests/scientist/test_decision_packet_node_v3.py
tests/scientist/nodes/test_build_policy_output_bundle.py
tests/scientist/nodes/builtins/decide/test_build_verified_policy_report.py
tests/scientist/policy_design/test_phase_b_output.py
tests/scientist/policy_design/test_phase_b_hierarchical_search.py
tests/scientist/search/test_phase_b_policy_runtime.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 1.1A | Claim-bearing inventory | `docs/reference/scientist/claims.md` | Table of decision-bearing surfaces and first projection owner | Docs/CI text check |
| 1.1B | Core claim contracts | `claims/models.py`, `claims/readiness.py` | Pydantic claim and ledger models | `tests/scientist/claims/test_models.py` |
| 1.1C | Ledger persistence | `claims/ledger.py` | Persist/load `ClaimLedger` via ArtifactStore/CAS | `test_ledger.py` |
| 1.1D | Projection helpers | `claims/projections.py` | Convert existing legal/causal/policy/governance outputs into claims | `test_projections.py` |
| 1.1E | Naked-claim validator | `claims/validators.py`, governance pass hook | Detect required outputs without claim refs | negative tests |
| 1.1F | Decision packet integration | decision packet and output bundle builders | `claims_ref` in artifacts index / packet payload | decision packet regressions |
| 1.1G | CI phase gate | `tools/ci/check_scientist_best_in_class_phase1_1.py` | Machine-readable pass/fail report | `tests/tools/test_scientist_best_in_class_phase1_1.py` |

#### Migration plan

1. Add claim artifacts without changing existing packet fields.
2. Project from existing outputs into a `ClaimLedger` sidecar.
3. Add `claims_ref` to decision packet payload and `artifacts_index`.
4. Add warnings for missing claim refs in staging.
5. Turn warnings into fail-closed publication gate only for selected workflows:
   `scientist_policy_design`, `scientist_policy_verified`,
   `scientist_causal_full`.
6. Keep old packets readable. If `claims_ref` is missing, render
   `claim_ledger_status = "legacy_missing"`.

#### Feature flags

```text
scientist.best_in_class.wave1.phase1_1.claim_spine
scientist.best_in_class.wave1.phase1_1.fail_on_naked_claims
```

Defaults:

- development: claim spine on, fail-on-naked-claims off until tests pass;
- staging: claim spine on, fail-on-naked-claims on after projection coverage;
- production: claim spine off initially, then shadow, then on for new runs only.

#### Required negative tests

- Decision packet with recommendation text but no `claims_ref` fails publication
  when flag is on.
- Legal claim without evidence refs becomes `review_required` or `blocked`.
- Claim with counterevidence but no support status cannot be `publishable`.
- Legacy packet remains loadable and marked `legacy_missing`.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase1_1.py
```

Gate checks:

- claim package import works;
- claim ledger model validates fixtures;
- selected decision packet fixtures include `claims_ref`;
- reference doc exists;
- expected tests are present by path.

#### Rollout

- Phase 1: sidecar only.
- Phase 2: packet projection in staging.
- Phase 3: fail closed for new high-risk/publication paths.
- Rollback: disable `fail_on_naked_claims`; keep sidecar generation.

#### Kill rules

Do not promote this phase if:

- existing readiness artifacts break compatibility;
- claim refs are generated but not persisted in CAS;
- hidden benchmark refs leak into public claim exports;
- claim validation produces high false-block rates on current decision packet
  tests;
- projections silently drop blocked or contested claims.

---

## Фаза 1.2 - Research DAG as first-class runtime object

**Длительность:** 3-4 недели.  
**Тезис:** research process должен быть replayable DAG, не transcript.

**Implementation status:** `closed` by
`src/polisyos/scientist/research_dag/**`, [research-dag.md](../../reference/scientist/research-dag.md),
selected-workflow `research_dag_ref` sidecar persistence, workflow/provenance/tool-loop
projections, replay/diff tests, and
`tools/ci/check_scientist_best_in_class_phase1_2.py`.

### Scope

- Typed nodes for research actions.
- Edges for dependency/support/refutation/synthesis.
- CAS-persisted `ResearchDAGArtifact`.
- Bridge from workflow/node traces and agent/tool loops.

### Proposed node families

| Node family | Examples |
| --- | --- |
| `question` | user request, normalized research question, subquestion |
| `plan` | research brief, search plan, eval plan |
| `source_acquisition` | web search, scholar search, file read, database query |
| `source_read` | URL fetch, PDF extraction, table extraction |
| `extraction` | snippet, metric, quote, legal provision, causal assumption |
| `verification` | citation check, freshness check, contradiction check |
| `synthesis` | answer section, policy option, causal conclusion |
| `critique` | critic pass, refutation pass, adversarial review |
| `governance` | pass result, human review, publication decision |

### Detailed contracts

```python
class ResearchNodeType(str, Enum):
    QUESTION = "question"
    PLAN = "plan"
    SOURCE_ACQUISITION = "source_acquisition"
    SOURCE_READ = "source_read"
    EXTRACTION = "extraction"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"
    CRITIQUE = "critique"
    GOVERNANCE = "governance"
    PUBLICATION = "publication"


class ResearchDAGNode(BaseModel):
    node_id: str
    node_type: ResearchNodeType
    run_id: str
    workflow_id: str | None = None
    producer: str
    summary: str
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    input_fingerprint: str | None = None
    output_fingerprint: str | None = None
    safety_labels: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ResearchEdgeType(str, Enum):
    DEPENDS_ON = "depends_on"
    SUPPORTS = "supports"
    REFUTES = "refutes"
    SUMMARIZES = "summarizes"
    DERIVES = "derives"
    GATES = "gates"
    SUPERSEDES = "supersedes"


class ResearchDAGEdge(BaseModel):
    source_node_id: str
    target_node_id: str
    edge_type: ResearchEdgeType
    claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ResearchDAGArtifact(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    workflow_id: str
    nodes: list[ResearchDAGNode]
    edges: list[ResearchDAGEdge]
    claim_ledger_ref: ArtifactRef | None = None
    hidden_content_redacted: bool = True
    created_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)
```

### Deliverables

```text
policy-engine/src/polisyos/scientist/research_dag/
├── __init__.py
├── models.py
├── builder.py
├── persistence.py
├── replay.py
├── diff.py
└── projections.py

policy-engine/docs/reference/scientist/research-dag.md
policy-engine/tests/scientist/research_dag/
```

### Integration targets

- `engine/trace_attributes.py`
- `engine/checkpoint.py`
- `provenance/run_dag.py`
- `agent/tools/tool_loop.py`
- `workflows/builder.py`
- `nodes/builtins/planning/*`
- `nodes/builtins/decide/*`

### Acceptance criteria

- `scientist_policy_design`, `scientist_policy_verified`, `scientist_causal_full`
  can persist a minimal `research_dag_ref`.
- DAG replay reconstructs high-level research path without LLM raw transcript.
- DAG diff shows changed sources, changed claims, changed governance outcomes.
- Raw untrusted web/page text is never stored as instruction-bearing context.

### Execution details

#### Goal

Persist a high-signal research DAG that explains how a decision artifact was
produced: question, plan, sources, extraction, verification, synthesis,
critique, governance and publication. The v1 target is not deterministic replay
of every LLM token.

#### Preconditions

- Phase 1.1 defines `ClaimLedger` or a stable placeholder ref.
- Current workflow and provenance tests are green.
- Existing provenance surfaces are understood:
  `src/polisyos/scientist/provenance/run_dag.py`,
  `engine/trace_attributes.py`, checkpoint and resume tests.

Baseline:

```bash
uv run pytest tests/scientist/workflows/test_workflow_specs.py tests/scientist/workflows/test_builder_pinning.py -q
uv run pytest tests/scientist/test_checkpoint.py tests/scientist/integration/test_checkpoint_resume.py -q
```

#### Non-goals

- Do not store full raw LLM transcripts as the research DAG.
- Do not require live web replay.
- Do not make LLM sampling deterministic.
- Do not replace existing engine DAG or workflow specs.
- Do not expose hidden benchmark internals in DAG exports.

#### Existing surfaces

```text
src/polisyos/scientist/engine/workflow_spec.py
src/polisyos/scientist/engine/trace_attributes.py
src/polisyos/scientist/engine/checkpoint.py
src/polisyos/scientist/provenance/run_dag.py
src/polisyos/scientist/replay/
src/polisyos/scientist/agent/tools/tool_loop.py
src/polisyos/scientist/workflows/builder.py
src/polisyos/scientist/nodes/builtins/planning/
src/polisyos/scientist/nodes/builtins/decide/
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 1.2A | Minimal models | `research_dag/models.py` | Node, edge, artifact models | `test_models.py` |
| 1.2B | Builder API | `research_dag/builder.py` | Append node/edge helpers | `test_builder.py` |
| 1.2C | Persistence | `research_dag/persistence.py` | CAS persist/load helpers | `test_persistence.py` |
| 1.2D | Workflow projection | `research_dag/projections.py`, workflow builder | Workflow and node outcomes become DAG nodes | workflow integration test |
| 1.2E | Tool-loop projection | `agent/tools/tool_loop.py` adapter only | Tool calls summarized as acquisition/read/extract nodes | agent/tool test |
| 1.2F | Minimal replay/diff | `research_dag/replay.py`, `diff.py` | Compare two DAGs by sources/claims/governance | `test_diff.py` |
| 1.2G | CI gate | `tools/ci/check_scientist_best_in_class_phase1_2.py` | Required files/tests/docs check | tools test |

#### Migration plan

1. Add DAG sidecar generation only.
2. Persist `research_dag_ref` into `artifacts_index`.
3. Add projections for three workflows:
   `scientist_policy_design`, `scientist_policy_verified`,
   `scientist_causal_full`.
4. Render `research_dag_status = "legacy_missing"` for old runs.
5. Only after Phase 1.7, require DAG refs for new high-risk/publication runs.

#### Feature flags

```text
scientist.best_in_class.wave1.phase1_2.research_dag
scientist.best_in_class.wave1.phase1_2.require_research_dag_for_publication
```

Production starts with sidecar off. Staging runs sidecar on in shadow mode.

#### Required negative tests

- DAG export redacts hidden benchmark metadata.
- Tool result containing prompt-injection text is stored as untrusted data.
- A DAG with orphaned `SUPPORTS` edge fails validation.
- Old runs without DAG refs still load.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase1_2.py
```

Gate checks:

- models import;
- required tests exist;
- reference page exists;
- selected fixture DAG validates;
- no hidden eval fields in public DAG fixture.

#### Rollout

- Shadow DAG sidecar.
- Compare storage/cost overhead for 20 representative runs.
- Enable DAG refs in staging packets.
- Require DAG refs only after naked-claim gate and benchmark authority are
  stable.

#### Kill rules

Do not promote if:

- DAG sidecar changes workflow behavior;
- DAG persistence materially increases hot-path latency without budget approval;
- raw private data or hidden benchmark content appears in export fixtures;
- DAG diff cannot identify changed sources and changed claim ids.

---

## Фаза 1.3 - Deep research evidence stack

**Статус:** closed - implemented as an additive Scholar contract extension plus
Scientist evidence adapters, safe Scholar tool wrappers, evidence verifier,
research-DAG projection, reference docs and Phase 1.3 CI gate. Production
fail-closed rollout remains feature-flag controlled.

**Длительность:** 4-5 недель.  
**Тезис:** Scientist needs first-party deep research, not provider-dependent
search. External web is untrusted evidence, not prompt context.

### Scope

- Query graph planner.
- Safe fetch/open/find tools.
- Source quality and recency scoring.
- Snippet ledger.
- Claim-to-source support mapping.
- Prompt-injection isolation.
- CAS-backed URL/content cache with freshness TTL.

### Current-code correction

`WebEvidenceBundle`, `QueryGraph`, `SourceMetadata`, `SourceSnippet` and
`ClaimSupportLink` already exist in `src/polisyos/scholar/search/models.py`.
This phase reuses and extends that canonical Scholar contract instead of
creating a duplicate Scientist-only evidence bundle.

### Deliverables

```text
policy-engine/src/polisyos/scholar/search/models.py

policy-engine/src/polisyos/scientist/evidence/
├── __init__.py
├── source_quality.py
├── snippet_ledger.py
├── claim_support.py
├── safe_fetch.py
├── cache.py
└── verifier.py

policy-engine/src/polisyos/scientist/agent/tools/scholar_search_tools.py
policy-engine/src/polisyos/scientist/agent/tools/knowledge_tools_adapter.py
policy-engine/docs/reference/scientist/deep-research-evidence.md
policy-engine/tests/scientist/evidence/
```

### Existing useful evidence models

- `ResearchBrief`
- `QueryGraph`
- `SearchConstraints`
- `SearchBudgetControls`
- `WebSearchHit`
- `FetchResult`
- `SourceMetadata`
- `SourceSnippet`
- `SearchQueryTrace`
- `ClaimSupportLink`
- `WebEvidenceBundle`
- `ResearchJobCheckpoint`

### Additive evidence contract extensions

```python
class FetchSafetyEvent(BaseModel):
    event_id: str
    url: str
    event_type: Literal[
        "blocked_private_network",
        "blocked_domain",
        "blocked_content_type",
        "max_bytes_exceeded",
        "prompt_injection_suspected",
        "malformed_url",
        "robots_or_policy_block",
    ]
    severity: Literal["info", "warning", "block"]
    message: str
    metadata: dict[str, object] = Field(default_factory=dict)


class SourceQualitySignal(BaseModel):
    source_id: str
    authority_score: float = Field(ge=0.0, le=1.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    primary_source_score: float = Field(ge=0.0, le=1.0)
    anti_seo_score: float = Field(ge=0.0, le=1.0)
    duplicate_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


# Add optional fields to the canonical Scholar WebEvidenceBundle:
fetch_safety_events: list[FetchSafetyEvent] = Field(default_factory=list)
source_quality_signals: list[SourceQualitySignal] = Field(default_factory=list)
```

`ClaimSupportLink.claim_id` maps to Phase 1.1 claim ids when available. Legacy
bundles may continue to use local ids, but projection must record
`claim_id_namespace = "legacy_local"` in metadata.

### Safety requirements

- SSRF guards.
- Domain allow/block lists.
- MIME/content-type policy.
- Max bytes and max extracted chars.
- HTML script/style/hidden instruction stripping.
- Prompt-injection detector emits warning but does not self-certify safety.
- Public-web and private-data research stages separated by default.

### Acceptance criteria

- Every web-supported claim has snippet-level support or is marked unsupported.
- Evidence bundle can be rendered in decision packet and exported.
- Search/fetch/extract tools validate arguments and cap responses.
- Tests cover malicious page text attempting instruction injection.

### Execution details

#### Preconditions

- Phase 1.1 provides stable claim ids or a temporary claim id strategy.
- Existing Scholar web evidence formatting tests are green:
  `tests/scientist/agent/test_knowledge_tools_web_evidence.py`.
- Existing tool schema/runtime validation remains green.

Baseline:

```bash
uv run pytest tests/scientist/agent/test_knowledge_tools_web_evidence.py tests/scientist/agent/test_workers.py -q
uv run pytest tests/scientist/agent/test_eval_harness.py tests/scientist/agent/test_reasoning.py -q
```

#### Non-goals

- Do not depend on a provider-native deep research product for production.
- Do not promise legal citation verification beyond available source text.
- Do not OCR every PDF in v1.
- Do not fetch private/internal URLs in the same stage as public web.
- Do not let retrieved text become system/developer instructions.

#### Existing surfaces

```text
src/polisyos/scholar/search/models.py
src/polisyos/scientist/agent/knowledge_tools.py
src/polisyos/scientist/agent/tools/scholar_search_tools.py
src/polisyos/scientist/agent/tools/knowledge_tools_adapter.py
src/polisyos/scientist/agent/fabric.py
src/polisyos/scientist/agent/eval_harness.py
tests/scientist/agent/test_knowledge_tools_web_evidence.py
tests/scientist/agent/test_workers.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 1.3A | Contract reconciliation | `scholar/search/models.py`, docs | Additive safety/quality fields | model tests |
| 1.3B | Safe fetch policy | `scientist/evidence/safe_fetch.py` or Scholar equivalent | URL/domain/MIME/private-network guard helpers | malicious URL tests |
| 1.3C | Source quality scoring | `scientist/evidence/source_quality.py` | deterministic scoring v1 | unit tests |
| 1.3D | Snippet ledger helpers | `scientist/evidence/snippet_ledger.py` | stable snippet ids and span checks | span tests |
| 1.3E | Claim support mapping | `scientist/evidence/claim_support.py` | claim-to-snippet projection | projection tests |
| 1.3F | Agent tool wrappers | existing tool files | strict schemas, caps, allow/block lists | tool contract tests |
| 1.3G | Research DAG projection | Phase 1.2 adapter | query/fetch/extract/verify nodes | DAG integration tests |
| 1.3H | Reference docs | `docs/reference/scientist/deep-research-evidence.md` | operational contract | docs gate |

#### Migration plan

1. Keep `polisyos.scholar.search.models.WebEvidenceBundle` as canonical.
2. Add optional fields only.
3. Update `KnowledgeToolkit.format_web_evidence_context(...)` to render safety
   warnings and quality signals when present.
4. Add Scientist evidence helpers as adapters around Scholar models.
5. Project `WebEvidenceBundle` into claim ledger and research DAG only when
   Phase 1.1/1.2 refs exist.

#### Feature flags

```text
scientist.best_in_class.wave1.phase1_3.deep_research_evidence
scientist.best_in_class.wave1.phase1_3.safe_fetch_fail_closed
scientist.best_in_class.wave1.phase1_3.claim_support_required
```

Default:

- safe fetch helpers can be used immediately in tests;
- fail-closed fetch policy off in production until existing consumers are
  audited;
- claim-support-required on only for new deep-research workflows.

#### Required negative tests

- `http://169.254.169.254/...` and localhost/private-network URLs block unless
  explicitly allowed.
- Blocked domain does not fetch.
- Unsupported MIME type blocks or degrades as configured.
- Page text containing instruction-injection phrases is stored only as
  untrusted snippet text and emits a safety event.
- Claim support link with missing snippet id fails validation.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase1_3.py
```

Gate checks:

- canonical `WebEvidenceBundle` remains in Scholar namespace;
- safety/quality optional fields validate;
- malicious URL fixture blocks;
- reference docs exist;
- selected agent tests are present.

#### Rollout

- Start as library/helpers plus tests.
- Enable in agent eval harness and shadow deep-research runs.
- Integrate with claim ledger only after Phase 1.1 sidecar is stable.
- Public/private data separation remains default-on before production use.

#### Kill rules

Do not promote if:

- fetched page text can override system/developer instructions;
- private network fetches are possible without explicit allow flag;
- citation snippets lose stable source ids or character spans;
- source quality scoring is presented as truth rather than heuristic signal;
- claim-support-required blocks existing non-web workflows.

---

## Фаза 1.4 - Agent and tool runtime promotion gates

**Длительность:** 3-4 недели.  
**Статус:** closed - реализован read-only promotion surface, CI gate и reference
страница; runtime defaults не изменены.  
**Тезис:** agentic features должны иметь один promotion surface, а не разрозненные
reports.

### Scope

- Unified agent capability registry.
- Tool runtime contract hardening.
- Supervisor-worker promotion criteria.
- Comparative evals against baseline.
- Rollout status projection into `frontier_runtime`.

### Deliverables

```text
policy-engine/src/polisyos/scientist/agent/runtime_capabilities.py
policy-engine/src/polisyos/scientist/agent/promotion.py
policy-engine/src/polisyos/scientist/agent/tool_contracts.py
policy-engine/src/polisyos/scientist/agent/supervisor_eval.py
policy-engine/docs/reference/scientist/agent-capability-promotion.md
```

### Capability families

| Capability | Default rule |
| --- | --- |
| tool loop | default only with transcript/order/schema tests |
| supervisor-worker | shadow first, then offline validated |
| deep research subgraph | non-default until citation/faithfulness evals pass |
| tree-of-thought / LATS | offline-gated until lift beats baseline |
| learned routing / learned VOI | shadow only until calibration and regret tests pass |
| same-model fan-out/voting | allowed only with budget + citation + consistency checks |

### Promotion contract

```python
class AgentCapabilityId(str, Enum):
    TOOL_LOOP = "tool_loop"
    SUPERVISOR_WORKER = "supervisor_worker"
    DEEP_RESEARCH_SUBGRAPH = "deep_research_subgraph"
    TREE_OF_THOUGHT = "tree_of_thought"
    LATS_MCTS = "lats_mcts"
    LEARNED_ROUTING = "learned_routing"
    LEARNED_VOI = "learned_voi"
    SAME_MODEL_FANOUT = "same_model_fanout"


class AgentCapabilityPromotionReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str | None = None
    capabilities: list[AgentCapabilityStatusRecord]
    offline_validation_ref: ArtifactRef | None = None
    benchmark_pack_ref: ArtifactRef | None = None
    default_enable_eligible: bool
    blockers: list[str] = Field(default_factory=list)
```

### Acceptance criteria

- One `AgentCapabilityPromotionReport` covers tool loop, supervisor, search,
  reflexion, context/memory and provider behavior.
- Report status values align with `FrontierCapabilityStatus` or an explicit
  successor enum.
- Default-enable is impossible without offline eval ref and benchmark pack ref.
- Tool args/output validation, response caps and structured error taxonomy are
  covered by tests.

### Execution details

#### Goal

Unify the rollout story for agentic Scientist capabilities. The codebase already
has tool loops, supervisor, reasoning gates, eval harness and advanced search
policy reports; this phase turns them into one promotion surface so future
features cannot become default merely because a class exists.

#### Preconditions

- Existing `agent-search-reasoning.md` reference remains accurate.
- Current tests for reasoning, eval harness, supervisor and advanced search pass.
- `FrontierCapabilityStatus` or a successor status enum is selected as the
  shared rollout vocabulary.

Baseline:

```bash
uv run pytest tests/scientist/agent/test_reasoning.py tests/scientist/agent/test_eval_harness.py -q
uv run pytest tests/scientist/agent/test_supervisor.py tests/scientist/search/strategies/test_advanced_policy.py -q
```

#### Non-goals

- Do not turn tree-of-thought, LATS, learned VOI or learned routing default-on.
- Do not add a new agent framework.
- Do not make provider-native web search mandatory.
- Do not bypass benchmark authority or hidden eval packs.

#### Existing surfaces

```text
src/polisyos/scientist/agent/reasoning.py
src/polisyos/scientist/agent/eval_harness.py
src/polisyos/scientist/agent/supervisor.py
src/polisyos/scientist/agent/tools/tool_loop.py
src/polisyos/scientist/agent/tools/registry.py
src/polisyos/scientist/search/strategies/advanced_policy.py
src/polisyos/scientist/frontier_runtime.py
docs/reference/scientist/agent-search-reasoning.md
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 1.4A | Capability registry | `runtime_capabilities.py` | Static inventory of agent capabilities | unit tests |
| 1.4B | Promotion report builder | `promotion.py` | One report over existing eval reports | report tests |
| 1.4C | Tool contract summary | `tool_contracts.py` | Schema/timeout/cap/error readiness summary | tool tests |
| 1.4D | Supervisor eval adapter | `supervisor_eval.py` | Handoff/delegation/quorum metrics | supervisor tests |
| 1.4E | Frontier projection | `frontier_runtime.py` adapter or docs | Agent status maps to frontier status | integration tests |
| 1.4F | Reference docs | `agent-capability-promotion.md` | rollout rules | docs gate |

#### Migration plan

1. Build report from existing `AgentPolicyComparisonReport`,
   `AdvancedSearchPolicyReport` and `ReasoningPolicyGate`.
2. Do not change default runtime behavior.
3. Add report to reference docs and optional workflow artifacts.
4. Later, require report before enabling any new agent capability by default.

#### Feature flags

```text
scientist.best_in_class.wave1.phase1_4.agent_promotion_report
scientist.best_in_class.wave1.phase1_4.require_agent_promotion_for_default
```

#### Required negative tests

- Default enable requested without benchmark pack returns blocker.
- Capability with invalid tool schema cannot become default-eligible.
- Supervisor-worker capability cannot become eligible without handoff eval.
- Deep research capability cannot become eligible without citation/faithfulness
  eval.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase1_4.py
```

Gate checks:

- promotion report imports;
- all known capability ids appear exactly once;
- docs list the same capability ids;
- default-enable fixture without evidence fails.

#### Rollout

Start read-only. Use it to explain capability readiness in staging. Only after
Phase 1.5 should any default-enable gate consume this report.

#### Kill rules

Do not promote if:

- report duplicates or contradicts existing rollout statuses;
- any advanced capability can become eligible with only a feature flag;
- tool safety regressions are hidden behind aggregate pass/fail;
- evaluation refs are free-form strings instead of artifact refs or validated
  ids.

---

## Фаза 1.5 - Benchmark authority and hidden eval packs

**Длительность:** 4-5 недель.  
**Статус:** closed - реализован read-only `BenchmarkAuthority` facade поверх
`BenchmarkRegistry`, staleness/leakage controls, eval-pack contracts, docs и CI
gate; large real hidden datasets остаются non-goal этой фазы.  
**Тезис:** promotion must cite one benchmark authority across Scientist.

### Scope

- Extend `BenchmarkRegistry`.
- Separate public, private, hidden, rotating, sentinel, adversarial splits.
- Add leakage and contamination controls.
- Add frozen-web/RetroSearch-like harness for deep research where feasible.
- Add policy-domain eval packs.

### Current-code correction

Scientist already has `BenchmarkRegistry`, `FrontierBenchmarkBundle` and tests
for selection, hidden holdout, rotating challenge and sentinel refs. This phase
keeps `BenchmarkRegistry` as the persistence authority and adds a policy facade
that answers: what evidence is required before this claim, capability or
artifact can advance readiness or replace a baseline?

### Deliverables

```text
policy-engine/src/polisyos/scientist/evals/
├── __init__.py
├── authority.py
├── datasets.py
├── graders.py
├── leakage.py
├── frozen_web.py
├── policy_cases.py
├── challenge_packs.py
└── reports.py

policy-engine/docs/reference/scientist/benchmark-authority.md
policy-engine/tools/ci/check_scientist_benchmark_authority.py
```

### Authority contracts

```python
class PromotionEvidenceRequest(BaseModel):
    family: str
    claim_mode: Literal["proof_only", "bounds", "estimation"]
    readiness_target: str | None = None
    query_type: str | None = None
    estimator_name: str | None = None
    capability_id: str | None = None
    workflow_id: str | None = None
    risk_tier: Literal["low", "medium", "high"] = "medium"


class BenchmarkAuthorityVerdict(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    request: PromotionEvidenceRequest
    bundle: FrontierBenchmarkBundle
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    leakage_warnings: list[str] = Field(default_factory=list)
    default_enable_allowed: bool
    rationale: str
```

### Required eval families

| Family | Purpose |
| --- | --- |
| factuality | SimpleQA-like short facts, but domain-local and source-grounded |
| browsing/deep research | BrowseComp/Deep Research Bench inspired multi-hop tasks |
| citation faithfulness | claim-to-snippet and quote accuracy |
| causal readiness | supported causal query classes vs blockers |
| policy design | Pareto, constraints, welfare, equity, legal feasibility |
| governance | false-pass, false-block, escalation quality |
| tool use | tool selection, argument precision, error recovery |
| human review | reviewer burden, override correctness, explanation quality |

### Acceptance criteria

- `BenchmarkRegistry` can answer: "what evidence is required for this claim
  family to advance readiness?"
- Hidden holdout refs are never serialized into public decision artifacts.
- Rotating challenge packs expire and refresh on schedule.
- Promotion fails closed when eval evidence is missing or stale.

### Execution details

#### Preconditions

- Existing benchmark registry tests pass.
- Existing frontier runtime gate remains non-default by design.
- Phase 1.1 can identify claim family or artifact family for the thing being
  promoted.

Baseline:

```bash
uv run pytest tests/scientist/search/test_benchmark_registry.py tests/scientist/test_frontier_runtime.py -q
uv run pytest tests/scientist/search/test_phase_d4_runtime_integration.py -q
```

#### Non-goals

- Do not create large real hidden datasets in this phase.
- Do not expose hidden holdout refs in public outputs.
- Do not claim benchmark validity for every public policy domain.
- Do not replace causal/foundry method validation manifests.

#### Existing surfaces

```text
src/polisyos/scientist/search/benchmark_registry.py
src/polisyos/scientist/search/registry_contracts.py
src/polisyos/scientist/frontier_runtime.py
src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py
src/polisyos/scientist/search/compliance_audit.py
tests/scientist/search/test_benchmark_registry.py
tests/scientist/search/test_phase_d4_runtime_integration.py
tests/scientist/test_frontier_runtime.py
```

Current useful concepts:

- split types: `selection`, `hidden_holdout`, `rotating_challenge`, `sentinel`;
- scoped metadata: `family`, `query_type`, `estimator_name`,
  `readiness_target`, `validation_contour`, `visibility`,
  `holdout_family`, `benchmark_revision`, `comparator_profile`;
- `FrontierBenchmarkBundle.missing_for_promotion()`;
- Phase D4 rotating challenge suite dedupe.

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 1.5A | Authority facade | `evals/authority.py` | Request/verdict API over `BenchmarkRegistry` | unit tests |
| 1.5B | Split taxonomy docs | `benchmark-authority.md` | Public/private/hidden/rotating/sentinel/adversarial semantics | docs gate |
| 1.5C | Staleness policy | `evals/datasets.py` | expiry by split/revision/visibility | tests |
| 1.5D | Leakage checks | `evals/leakage.py` | hidden refs/public export guard | negative tests |
| 1.5E | Grader registry v1 | `evals/graders.py` | named grader metadata, not full grader implementation | tests |
| 1.5F | Frozen web stub | `evals/frozen_web.py` | interface for RetroSearch-like packs | contract tests |
| 1.5G | Policy case packs | `evals/policy_cases.py` | fixtures for policy-domain eval packs | fixture tests |
| 1.5H | CI gate | `check_scientist_benchmark_authority.py` | machine-readable acceptance | tools test |

#### Migration plan

1. Keep `BenchmarkRegistry` as persistence authority.
2. Add `BenchmarkAuthority` as policy facade, not replacement.
3. Existing calls to `require_promotion_evidence(...)` continue working.
4. New agent/frontier/default-enable code calls authority verdict.
5. Public artifacts receive only verdict summaries, never hidden refs.

#### Feature flags

```text
scientist.best_in_class.wave1.phase1_5.benchmark_authority
scientist.best_in_class.wave1.phase1_5.require_authority_for_default_enable
scientist.best_in_class.wave1.phase1_5.hide_hidden_eval_refs_in_exports
```

#### Required negative tests

- Missing hidden holdout blocks estimation promotion.
- Non-core family without rotating challenge blocks promotion.
- Stale benchmark revision blocks default enable.
- Hidden refs are redacted from public verdict export.
- Free-form benchmark refs are rejected when registry lookup is required.

#### CI gate

Create or extend:

```text
tools/ci/check_scientist_benchmark_authority.py
```

Gate checks:

- authority facade imports;
- required split names are documented;
- fixture verdicts match expected missing/stale behavior;
- public export fixture contains no hidden artifact ids;
- current benchmark registry regression tests are included.

#### Rollout

- Start as read-only authority used by docs and tests.
- Wire into agent promotion report.
- Wire into frontier default-enable gate.
- Only after shadow period, fail closed for default-enable requests.

#### Kill rules

Do not promote if:

- authority and `BenchmarkRegistry` disagree on missing evidence;
- hidden holdout refs leak into public reports;
- stale eval packs can still approve baseline replacement;
- benchmark authority is used to claim scientific validity outside documented
  benchmark scope;
- frozen web harness is treated as production web search instead of eval
  infrastructure.

---

## Фаза 1.6 - Human oversight and accountable release packets

**Длительность:** 3-4 недели.  
**Статус:** closed - реализованы typed review packets, queue assignments,
CAS-persisted review decisions, oversight policy gate, audit helpers,
governance report links, decision-packet validation and reference docs.  
**Тезис:** human oversight must be an operational control plane, not prose.

### Scope

- Review packet model.
- Review assignment and decision persistence.
- Override/interrupt/reject semantics.
- Two-person verification option.
- Right-to-explanation posture.
- Fundamental-rights/public-sector risk checklist.

### Deliverables

```text
policy-engine/src/polisyos/scientist/human_review/
├── __init__.py
├── models.py
├── queue.py
├── decisions.py
├── packets.py
├── oversight_policy.py
└── audit.py

policy-engine/docs/reference/scientist/human-oversight.md
policy-engine/tests/scientist/human_review/
```

### Review packet contents

- decision summary;
- claim ledger summary;
- top evidence and counterevidence;
- uncertainty and calibration;
- source freshness;
- legal/fairness/privacy/escalation issues;
- blocked claims;
- unresolved assumptions;
- recommended reviewer actions;
- stop/override/reissue controls;
- audit trail and reviewer signatures.

### Acceptance criteria

- High-risk/public-sector publication path can require human review.
- Human reviewer can approve, reject, request re-run, override, or mark
  explanation insufficient.
- Review decisions are CAS-persisted and included in governance report.
- Decision packet cannot claim `human_reviewed` readiness without a review ref.

---

## Фаза 1.7 - Wave 1 closeout

**Длительность:** 1-2 недели.  
**Статус:** closed - `docs/reference/scientist/best-in-class-wave1-acceptance.md`
and `tools/ci/check_scientist_best_in_class_wave1.py` verify the Wave 1
cross-phase acceptance surface.  
**Тезис:** Wave 1 is accepted only when claims, evidence, readiness, research DAG,
agent promotion, benchmark authority and human review agree.

### Deliverables

```text
policy-engine/docs/reference/scientist/best-in-class-wave1-acceptance.md
policy-engine/tools/ci/check_scientist_best_in_class_wave1.py
policy-engine/tests/tools/test_scientist_best_in_class_wave1.py
```

### Acceptance criteria

- All phase gates green.
- No decision-bearing number/text in selected workflows lacks claim projection.
- Research DAG and claim ledger refs appear in decision packets.
- Agent/frontier default-enable cannot bypass benchmark authority.
- Human review status is explicit for high-risk claims.

---

## 7. Волна 2 - Best-in-Class Primitives

## Фаза 2.0 - Scientist OS foundation

**Длительность:** 2 недели.  
**Тезис:** Wave 2 begins only after Scientist has a shared runtime vocabulary:
claim, research DAG, benchmark, review, VOI, reissue.

### Scope

- Cross-module package boundaries.
- Reference docs.
- API migration notes.
- Feature flag consolidation.
- Artifact versioning.

### Deliverables

```text
policy-engine/docs/adr/ADR-0XX-scientist-claim-ledger.md
policy-engine/docs/adr/ADR-0XX-scientist-research-dag.md
policy-engine/docs/adr/ADR-0XX-scientist-readiness-ladder.md
policy-engine/docs/adr/ADR-0XX-scientist-voi-compute-law.md
```

### Acceptance criteria

- ADRs accepted.
- Existing workflow APIs remain backward compatible.
- Old decision packet fields are additive/deprecated, not removed abruptly.

---

## Фаза 2.1 - Claim Ledger

**Длительность:** 4-5 недель.  
**Тезис:** Claim Ledger становится главным объектом, который связывает research,
governance, provenance, UI, export и audit.

### Scope

- Append-only claim ledger.
- Claim lifecycle transitions.
- Claim merge/split/supersede.
- Claim-level provenance and reviewer attribution.
- Claim export to decision packet and future frontend Trust View.

### Deliverables

```text
policy-engine/src/polisyos/scientist/claims/lifecycle.py
policy-engine/src/polisyos/scientist/claims/audit.py
policy-engine/src/polisyos/scientist/claims/export.py
policy-engine/src/polisyos/scientist/claims/diff.py
policy-engine/docs/reference/scientist/claim-ledger.md
```

### Best-in-class behavior

- A decision can be diffed by claims, not just files/artifacts.
- A reviewer can ask: "what changed since last run and why?"
- A blocked claim remains visible as blocked, not deleted.
- Counterevidence is first-class.
- Claim readiness cannot move backward/forward without transition reason.

### Acceptance criteria

- Claim lifecycle is state-machine checked.
- Claim diffs work between two runs.
- Ledger supports append-only audit and bounded retention.
- Decision packets include ledger summary and blocked claim summary.

---

## Фаза 2.2 - Research DAG replay and comparison

**Длительность:** 4-5 недель.  
**Тезис:** Research DAG is not only stored; it can be replayed, compared and
used to diagnose why decisions changed.

### Scope

- DAG replay planner.
- Deterministic replay where inputs are pinned.
- Non-deterministic replay envelope for LLM/web variance.
- Research trajectory diff.
- Source invalidation propagation.

### Deliverables

```text
policy-engine/src/polisyos/scientist/research_dag/replay.py
policy-engine/src/polisyos/scientist/research_dag/invalidation.py
policy-engine/src/polisyos/scientist/research_dag/comparison.py
policy-engine/docs/reference/scientist/research-dag-replay.md
```

### Acceptance criteria

- Replay can use CAS-pinned inputs without live web.
- Diff reports changed queries, changed sources, changed snippets, changed
  claims, changed governance outcomes.
- Source invalidation can mark dependent claims stale.
- Replay output is safe for audit without exposing hidden benchmark answers.

---

## Фаза 2.3 - VOI scheduler

**Длительность:** 4-6 недель.  
**Тезис:** Scientist compute should be allocated by expected value of
information, not static pipeline habit.

### Scope

- VOI model for candidate evaluation.
- VOI model for source verification.
- VOI model for human escalation.
- Budget-aware scheduling.
- Regret and calibration monitoring.

### Deliverables

```text
policy-engine/src/polisyos/scientist/search/voi_scheduler.py
policy-engine/src/polisyos/scientist/search/voi_models.py
policy-engine/src/polisyos/scientist/search/voi_calibration.py
policy-engine/src/polisyos/scientist/human_review/voi_escalation.py
policy-engine/docs/reference/scientist/voi-scheduler.md
```

### Scheduling decisions

| Decision | VOI question |
| --- | --- |
| Run expensive causal eval? | Will this change frontier/promotion/readiness? |
| Fetch more sources? | Will this reduce contested/unsupported claim risk? |
| Ask human reviewer? | Is expected harm/reversal risk high enough? |
| Run adversarial challenge? | Is candidate near promotion or high-impact? |
| Stop search? | Is expected improvement lower than compute + review cost? |

### Acceptance criteria

- VOI report is persisted per major run.
- Scheduler can explain why it spent or did not spend compute.
- Shadow comparison shows non-worse safety and lower or better-targeted cost.
- Human escalation decisions remain auditable and overrideable.

---

## Фаза 2.4 - Reflexive memory and failure intelligence

**Длительность:** 4-5 недель.  
**Тезис:** Best-in-class Scientist learns from failures without contaminating
future evaluations.

### Scope

- Failure cards as structured retrieval objects.
- Lesson cards with applicability scope.
- Cross-run transfer isolation.
- Memory contamination guards.
- Reflexion recovery evals.

### Deliverables

```text
policy-engine/src/polisyos/scientist/memory/
├── __init__.py
├── failure_lessons.py
├── applicability.py
├── contamination.py
├── retrieval.py
└── consolidation.py

policy-engine/docs/reference/scientist/reflexive-memory.md
```

### Rules

- Hidden benchmark answers never enter reusable memory.
- Lessons have scope: tenant, domain, workflow, method family, expiry.
- Failed trajectories can be retrieved, but only as warnings/anti-patterns.
- Memory influence must be visible in research DAG.

### Acceptance criteria

- Reflexion recovery rate improves on held-out failure scenarios.
- Memory retrieval emits source lesson ids and applicability reasons.
- Contamination tests prove hidden eval content is not reused.
- Lessons can be revoked when invalidated.

---

## Фаза 2.5 - Adversarial challenge factory

**Длительность:** 4-6 недель.  
**Тезис:** Scientist should continuously generate and rotate adversarial
challenges, not wait for hand-written evals.

### Scope

- Challenge generation from failures, near-misses and policy-domain risks.
- Challenge mutation.
- Sentinel candidates.
- Red-team scenarios.
- Rotating pack lifecycle.

### Deliverables

```text
policy-engine/src/polisyos/scientist/evals/challenge_factory.py
policy-engine/src/polisyos/scientist/evals/sentinels.py
policy-engine/src/polisyos/scientist/evals/red_team.py
policy-engine/src/polisyos/scientist/evals/rotation.py
policy-engine/docs/reference/scientist/adversarial-challenge-factory.md
```

### Challenge classes

- source contradiction;
- stale source;
- forged citation;
- missing transportability assumption;
- hidden confounding/proxy assumption trap;
- fairness threshold reversal;
- legal exception;
- policy gaming/strategic response;
- budget infeasibility;
- ambiguous human-review instruction.

### Acceptance criteria

- Challenge packs can be generated from failure cards.
- Generated challenges must be reviewed/promoted before becoming hidden evals.
- Benchmark authority tracks challenge pack lineage.
- Promotion near frontier requires fresh rotating challenge evidence.

---

## Фаза 2.6 - Continuous governance and reissue loop

**Длительность:** 4-5 недель.  
**Тезис:** A decision artifact is not final forever; it can become stale,
invalidated, superseded, reissued or withdrawn.

### Scope

- Continuous decision validity monitoring.
- Source freshness and invalidation.
- Calibration/fairness drift.
- Policy-context drift.
- Reissue/withdrawal workflow.
- Incident/post-market monitoring posture.

### Deliverables

```text
policy-engine/src/polisyos/scientist/continuous_governance/
├── __init__.py
├── monitors.py
├── invalidation.py
├── reissue.py
├── incident.py
└── reports.py

policy-engine/docs/reference/scientist/continuous-governance.md
```

### Acceptance criteria

- A source invalidation can mark dependent claims stale.
- Drift monitor can trigger review/reissue.
- Reissue packet links old and new claim ledgers.
- Withdrawal status is explicit and auditable.

---

## Фаза 2.7 - Decision-grade research compiler

**Длительность:** 3-4 недели.  
**Тезис:** Scientist output should compile from research artifacts into
audience-specific packets without losing provenance.

### Scope

- Decision packet compiler.
- Expert appendix.
- Public summary.
- Reviewer packet.
- Machine export.
- Frontend trust/provenance hooks.

### Deliverables

```text
policy-engine/src/polisyos/scientist/publisher.py
policy-engine/src/polisyos/scientist/orchestrator/decision_card.py
policy-engine/src/polisyos/scientist/claims/export.py
policy-engine/docs/reference/scientist/decision-grade-compiler.md
```

### Output tiers

| Tier | Audience | Contents |
| --- | --- | --- |
| public summary | citizen/operator | approved claims, plain explanation, limits |
| reviewer packet | human reviewer | claims, evidence, blockers, override controls |
| expert appendix | analyst/legal/scientist | methods, uncertainty, evals, assumptions |
| machine export | UI/API/audit | claim ledger, DAG, refs, statuses |

### Acceptance criteria

- All output tiers derive from the same claim ledger and research DAG.
- No tier can silently omit blockers unless marked intentionally hidden from
  that audience with a reason.
- Frontend can render trust/provenance views from exported fields.

---

## Фаза 2.8 - System closeout

**Длительность:** 1-2 недели.  
**Тезис:** Wave 2 is closed only with metrics, docs, CI gates, shadow evidence
and migration notes.

### Deliverables

```text
policy-engine/docs/reference/scientist/best-in-class-wave2-acceptance.md
policy-engine/tools/ci/check_scientist_best_in_class_wave2.py
policy-engine/docs/reference/scientist/best-in-class-maturity.md
```

### Acceptance criteria

- Wave 2 gate green.
- No unresolved migration docs.
- All new primitives have tests and source-of-truth reference pages.
- Shadow run shows measurable quality lift or cost/safety improvement.

---

## 8. Research-first companion agenda

Некоторые части нельзя честно поставить как engineering ticket без отдельного
research result. Для них нужен companion:

```text
policy-engine/docs/archive/plans/SCIENTIST_RESEARCH_AGENDA.md
```

### Candidate research tracks

| Track | Open question | Unlocks |
| --- | --- | --- |
| R1 - Claim support semantics | What is a sufficient computable support relation between evidence snippets and policy claims? | Claim Ledger promotion |
| R2 - Citation faithfulness under paraphrase | How to detect when a cited source supports a paraphrased policy claim? | Deep research evidence |
| R3 - VOI for governed policy research | How to estimate value of additional evidence/eval/human review under multi-objective risk? | VOI scheduler |
| R4 - Benchmark leakage and contamination | How to detect and prevent benchmark leakage through memory, web, and previous traces? | Benchmark authority |
| R5 - Human oversight thresholds | When should human review be required, and how to calibrate automation-bias mitigations? | Human oversight |
| R6 - Adversarial challenge generation | Which generated challenges are valid, non-leaky, and predictive of real failures? | Challenge factory |
| R7 - Decision reissue semantics | When does source or context drift invalidate a previous policy decision? | Continuous governance |
| R8 - Multi-agent compression quality | When does subagent fan-out improve evidence coverage rather than amplify noise? | Supervisor-worker runtime |

Research deliverables follow the same rule as causal/foundry agendas:

- theorem with machine-checkable conditions;
- calibrated benchmark;
- impossibility/counterexample class;
- or reduction to known solvable problem.

Heuristics alone do not unlock default production readiness.

---

## 9. Success metrics

### 9.1. Claim safety

| Metric | Target |
| --- | --- |
| Naked decision claims | 0 in gated workflows |
| Claims with evidence refs | >= 98% for factual/legal/causal claims |
| Claims with counterevidence status | 100% explicitly evaluated or marked unavailable |
| Blocked claims visible in packet | 100% |
| Stale claim invalidation latency | <= 1 run cycle after source invalidation |

### 9.2. Research quality

| Metric | Target |
| --- | --- |
| Citation faithfulness | >= 0.95 on held-out eval pack |
| Source freshness correctness | >= 0.98 |
| Unsupported claim false-pass rate | <= 0.02 |
| Deep research multi-hop success | measurable lift over baseline |
| Research DAG replay success | >= 0.95 on CAS-pinned runs |

### 9.3. Agent/tool quality

| Metric | Target |
| --- | --- |
| Invalid tool argument pass-through | 0 |
| Tool selection accuracy | >= phase-specific baseline + lift |
| Handoff accuracy | >= 0.95 for approved supervisor paths |
| Reflexion recovery rate | >= 0.60 on held-out failure pack |
| Prompt-injection unsafe action rate | 0 in malicious web tests |

### 9.4. Governance and oversight

| Metric | Target |
| --- | --- |
| High-risk publication without review | 0 |
| Reviewer packet completeness | 100% required fields |
| Override/reject auditability | 100% |
| Reissue/withdrawal traceability | 100% |
| Governance false-pass rate | decreasing vs Wave 1 baseline |

### 9.5. Compute economics

| Metric | Target |
| --- | --- |
| VOI report coverage | 100% for expensive eval/search/human escalation |
| Cost per promoted decision | decreases or justified by quality lift |
| Wasted expensive evals | decreasing vs baseline |
| Shadow regret | non-worse than baseline before default enablement |

---

## 10. Risks and mitigations

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Over-agentization | More agents can add nondeterminism, cost and debugging burden | Evals gate every multi-agent capability; keep workflows simple where fixed DAG is enough. |
| Claim ledger bloat | Every output could become too heavy | Only decision-bearing claims are mandatory; summaries and derived display text can be non-claiming. |
| Citation theater | Sources can be cited without actually supporting claims | Snippet-level support links, faithfulness graders, counterevidence checks. |
| Hidden benchmark leakage | Memory/replay/web can contaminate evals | Split visibility, memory contamination guards, canary strings, no hidden answers in reusable memory. |
| Human review becomes rubber stamp | Automation bias risk in public-sector/high-risk workflows | Reviewer packet includes blockers, uncertainty, override controls, and explicit "do not use" option. |
| VOI model gaming | Scheduler could avoid hard checks to save cost | Promotion gates require minimum evidence regardless of VOI; VOI can prioritize, not waive mandatory gates. |
| Continuous governance false alarms | Too many reissue triggers can create review fatigue | Severity tiers, debounce windows, calibrated drift thresholds, human override. |
| Provider-specific lock-in | Deep research via one provider can break or hide evidence | First-party evidence stack; provider tools optional and wrapped as evidence inputs. |
| Legal/compliance overreach | Plan may imply regulatory compliance without certification | Docs use "posture" and "readiness"; compliance claims require legal review and jurisdiction-specific gates. |

---

## 11. Source bibliography

### Agent architecture and tools

- Anthropic - [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Anthropic - [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic - [Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- Anthropic - [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- ReAct - [Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- Toolformer - [Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761)
- Reflexion - [Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- Self-Refine - [Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- Self-RAG - [Learning to Retrieve, Generate, and Critique through Self-Reflection](https://arxiv.org/abs/2310.11511)

### Deep research and browsing

- OpenAI - [Deep research API guide](https://developers.openai.com/api/docs/guides/deep-research)
- Google - [Gemini Deep Research Agent](https://ai.google.dev/gemini-api/docs/deep-research)
- STORM - [Assisting in Writing Wikipedia-like Articles From Scratch](https://arxiv.org/abs/2402.14207)
- MindSearch - [Mimicking Human Minds Elicits Deep AI Searcher](https://arxiv.org/abs/2407.20183)
- Deep Research Bench - [Evaluating AI Web Research Agents](https://arxiv.org/abs/2506.06287)

### Evals and benchmarks

- OpenAI - [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- OpenAI - [Agent evals](https://developers.openai.com/api/docs/guides/agent-evals)
- OpenAI - [BrowseComp](https://openai.com/index/browsecomp/)
- OpenAI - [SimpleQA](https://openai.com/index/introducing-simpleqa/)
- SWE-bench - [SWE-bench Verified](https://www.swebench.com/verified.html)

### Governance and public-sector risk

- NIST - [AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- OECD - [AI Principles](https://www.oecd.org/en/topics/ai-principles.html)
- European Commission - [Navigating the AI Act](https://digital-strategy.ec.europa.eu/en/faqs/navigating-ai-act)
- EU AI Act - [Article 14: Human Oversight](https://artificialintelligenceact.eu/article/14/)
