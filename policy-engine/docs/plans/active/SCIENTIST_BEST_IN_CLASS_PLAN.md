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
- [8. Wave R - Research-first companion agenda](#8-wave-r---research-first-companion-agenda)
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

**Статус:** closed - ADRs, Wave 2 runtime contracts, compatibility fixtures and
Phase 2.0 gate accepted.

### Scope

- Cross-module package boundaries.
- Reference docs.
- API migration notes.
- Feature flag consolidation.
- Artifact versioning.

### Deliverables

```text
policy-engine/docs/adr/0129-scientist-claim-ledger.md
policy-engine/docs/adr/0130-scientist-research-dag.md
policy-engine/docs/adr/0131-scientist-readiness-ladder.md
policy-engine/docs/adr/0132-scientist-voi-compute-law.md
policy-engine/docs/reference/scientist/wave2-runtime-contracts.md
policy-engine/tools/ci/check_scientist_best_in_class_phase2_0.py
policy-engine/tests/scientist/wave2/test_compatibility_contracts.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_0.py
```

### Acceptance criteria

- ADRs accepted.
- Existing workflow APIs remain backward compatible.
- Old decision packet fields are additive/deprecated, not removed abruptly.

### Execution details

#### Goal

Create the Wave 2 operating contract before adding new primitives. This phase
does not build Claim Ledger, replay, VOI or reissue logic. It freezes the
package boundaries, naming, artifact versioning and migration rules that later
phases must follow.

#### Preconditions

- Wave 1 closeout gate is green:
  `tools/ci/check_scientist_best_in_class_wave1.py`.
- `claims_ref`, `research_dag_ref`, benchmark authority and human-review refs
  remain additive and backward compatible.
- Current routed workflows still load old decision packets and legacy sidecar
  states.

Baseline:

```bash
uv run python tools/ci/check_scientist_best_in_class_wave1.py --repo-root . --output-format json --require-passing
uv run pytest tests/tools/test_scientist_best_in_class_wave1.py -q
```

#### Non-goals

- Do not implement append-only Claim Ledger transitions in Phase 2.0.
- Do not require research DAG replay for publication yet.
- Do not turn VOI, memory, challenge generation or continuous governance
  default-on.
- Do not remove legacy decision-packet fields.

#### Existing surfaces

```text
src/polisyos/scientist/claims/**
src/polisyos/scientist/research_dag/**
src/polisyos/scientist/evals/**
src/polisyos/scientist/human_review/**
src/polisyos/scientist/search/voi_scheduler.py
src/polisyos/scientist/search/failure_cards.py
src/polisyos/scientist/search/lessons.py
src/polisyos/scientist/publisher.py
src/polisyos/scientist/orchestrator/decision_card.py
docs/reference/scientist/best-in-class-wave1-acceptance.md
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.0A | Boundary ADRs | `docs/adr/0129-scientist-*.md` through `docs/adr/0132-scientist-*.md` | Accepted package, artifact and migration decisions | ADR lint/docs gate |
| 2.0B | Versioning map | `docs/reference/scientist/wave2-runtime-contracts.md` | Artifact schemas, deprecation posture, feature-flag map | docs token gate |
| 2.0C | Compatibility fixtures | `tests/scientist/wave2/test_compatibility_contracts.py` | Legacy packet/sidecar fixture loading | pytest |
| 2.0D | Phase gate | `tools/ci/check_scientist_best_in_class_phase2_0.py` | Machine-readable readiness report | tools test |

#### Required negative tests

- Old decision packet without Wave 2 fields still loads as `legacy_missing`.
- A proposed ADR that removes an old public field fails the compatibility check.
- A new Wave 2 feature flag cannot default to production-on.
- Artifact schema version regression is rejected.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_0.py
tests/tools/test_scientist_best_in_class_phase2_0.py
```

Gate checks:

- Wave 1 gate passes;
- required ADRs exist and include compatibility, rollout and rollback sections;
- Wave 2 reference contract page exists;
- public packet compatibility fixtures load;
- readiness index lists the current Wave 2 phase names and numbers.

#### Rollout

Documentation and gate only. Once this phase is green, implementation phases
can add code behind Wave 2 feature flags without renegotiating naming or schema
semantics.

#### Kill rules

Do not promote Phase 2.0 if:

- any workflow API or decision-packet consumer breaks on legacy artifacts;
- ADRs conflict with Phase 1 public contracts;
- Wave 2 phase numbering is inconsistent across active plan and readiness
  reference;
- feature flags are ambiguous about default values.

---

## Фаза 2.1 - Claim Ledger

**Длительность:** 4-5 недель.  
**Тезис:** Claim Ledger становится главным объектом, который связывает research,
governance, provenance, UI, export и audit.

**Статус:** closed - lifecycle, audit, diff, export, packet summaries,
reference docs and Phase 2.1 gate accepted.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_1.py
policy-engine/tests/scientist/claims/test_lifecycle.py
policy-engine/tests/scientist/claims/test_audit.py
policy-engine/tests/scientist/claims/test_diff.py
policy-engine/tests/scientist/claims/test_export.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_1.py
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

### Execution details

#### Goal

Promote the Phase 1.1 `ClaimLedger` sidecar into the primary decision
artifact for claim lifecycle, audit, diff and export. Phase 2.1 extends the
existing `src/polisyos/scientist/claims/**` package; it does not replace the
Phase 1.1 models or `DecisionReadiness` ladder.

#### Current-code correction

`ClaimRecord`, `ClaimLedger`, ledger persistence, readiness checks,
projections and naked-claim validators already exist. This phase adds lifecycle
events and append-only audit on top of those contracts.

#### Proposed contracts

```python
class ClaimLifecycleAction(str, Enum):
    CREATED = "created"
    UPDATED_SUPPORT = "updated_support"
    UPDATED_READINESS = "updated_readiness"
    MERGED = "merged"
    SPLIT = "split"
    SUPERSEDED = "superseded"
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"
    REVIEWED = "reviewed"
    INVALIDATED = "invalidated"


class ClaimLifecycleEvent(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    claim_id: str
    run_id: str
    action: ClaimLifecycleAction
    occurred_at: datetime
    actor_id: str
    reason: str
    previous_claim_ref: ArtifactRef | None = None
    next_claim_ref: ArtifactRef | None = None
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class AppendOnlyClaimLedger(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    run_id: str
    base_ledger_ref: ArtifactRef | None = None
    current_claims: list[ClaimRecord] = Field(default_factory=list)
    events: list[ClaimLifecycleEvent] = Field(default_factory=list)
    retention_policy: dict[str, object] = Field(default_factory=dict)
```

#### Preconditions

- Phase 2.0 compatibility ADRs accepted.
- Phase 1.1 claim package and Wave 1 closeout gate are green.
- Existing decision packet and policy output bundle tests remain green.

Baseline:

```bash
uv run pytest tests/scientist/claims tests/scientist/test_decision_packet_node_v3.py -q
uv run pytest tests/scientist/nodes/test_build_policy_output_bundle.py -q
```

#### Non-goals

- Do not require every prose sentence to become a claim.
- Do not mutate persisted Phase 1.1 ledgers in place.
- Do not make frontend Trust View UI in this phase.
- Do not solve citation faithfulness scoring beyond Phase 1.3 support links.

#### Existing surfaces

```text
src/polisyos/scientist/claims/models.py
src/polisyos/scientist/claims/ledger.py
src/polisyos/scientist/claims/readiness.py
src/polisyos/scientist/claims/projections.py
src/polisyos/scientist/claims/validators.py
src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py
src/polisyos/scientist/human_review/**
src/polisyos/scientist/research_dag/**
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.1A | Lifecycle model | `claims/lifecycle.py` | Typed lifecycle events and transition matrix | `test_lifecycle.py` |
| 2.1B | Append-only audit | `claims/audit.py` | CAS persistence, event ordering, actor attribution | `test_audit.py` |
| 2.1C | Claim diff | `claims/diff.py` | Added/removed/changed/blocked/superseded claim diff | `test_diff.py` |
| 2.1D | Export model | `claims/export.py` | Public/reviewer/machine summaries with omission reasons | `test_export.py` |
| 2.1E | Packet projection | decision packet/output bundle builders | Ledger summary and blocked claim summary | packet regressions |
| 2.1F | Reference docs | `claim-ledger.md` | Operational contract and migration notes | docs gate |
| 2.1G | CI gate | `check_scientist_best_in_class_phase2_1.py` | Phase readiness report | tools test |

#### Migration plan

1. Keep Phase 1.1 `ClaimLedger` readable as `schema_version="1.0"`.
2. Persist append-only lifecycle events as a sidecar, not in-place mutation.
3. Add `claim_ledger_v2_ref` only after packet consumers handle both versions.
4. Render old ledgers with `lifecycle_status = "legacy_no_events"`.
5. Make blocked and superseded claims visible in exports before enabling any
   frontend Trust View dependency.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_1.claim_ledger_v2
scientist.best_in_class.wave2.phase2_1.require_lifecycle_events
```

#### Required negative tests

- A claim readiness transition without `reason` fails.
- A publishable claim cannot be silently downgraded or deleted.
- Merge/split events must preserve source claim ids.
- Superseded and blocked claims remain visible in reviewer/machine exports.
- Legacy `ClaimLedger` loads and renders `legacy_no_events`.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_1.py
tests/tools/test_scientist_best_in_class_phase2_1.py
```

Gate checks:

- lifecycle package imports;
- transition fixture validates;
- diff fixture reports changed support/readiness/blockers;
- packet fixture includes ledger and blocked-claim summaries;
- reference page exists and lists migration/rollback semantics.

#### Rollout

Start as sidecar and export helpers. Turn on packet summaries in staging after
legacy readers are tested. Fail closed only for new high-risk publication paths
after Phase 2.6 reissue semantics exist.

#### Kill rules

Do not promote if:

- lifecycle events can be reordered or overwritten silently;
- blocked claims disappear from reviewer or machine exports;
- old `ClaimLedger` artifacts stop loading;
- diff loses counterevidence, reviewer attribution or source refs.

---

## Фаза 2.2 - Research DAG replay and comparison

**Длительность:** 4-5 недель.  
**Тезис:** Research DAG is not only stored; it can be replayed, compared and
used to diagnose why decisions changed.

**Статус:** closed - replay planning, trajectory comparison, source
invalidation, public replay redaction, reference docs and Phase 2.2 gate
accepted.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_2.py
policy-engine/tests/scientist/research_dag/test_replay_plan.py
policy-engine/tests/scientist/research_dag/test_comparison.py
policy-engine/tests/scientist/research_dag/test_invalidation.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_2.py
```

### Acceptance criteria

- Replay can use CAS-pinned inputs without live web.
- Diff reports changed queries, changed sources, changed snippets, changed
  claims, changed governance outcomes.
- Source invalidation can mark dependent claims stale.
- Replay output is safe for audit without exposing hidden benchmark answers.

### Execution details

#### Goal

Move from "DAG exists" to "DAG explains and compares runs." Replay in this
phase means audit reconstruction from pinned artifacts and summarized tool
nodes, not deterministic regeneration of LLM tokens or live web results.

#### Current-code correction

`research_dag/replay.py` and `research_dag/diff.py` already exist from Phase
1.2. This phase extends them with replay planning, deeper comparison and source
invalidation; it should not duplicate the existing models.

#### Proposed contracts

```python
class ReplayMode(str, Enum):
    AUDIT_RECONSTRUCTION = "audit_reconstruction"
    PINNED_INPUT_REPLAY = "pinned_input_replay"
    VARIANCE_ENVELOPE = "variance_envelope"


class ResearchReplayPlan(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    workflow_id: str
    mode: ReplayMode
    dag_ref: ArtifactRef
    required_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    live_fetch_required: bool = False
    unsupported_steps: list[str] = Field(default_factory=list)


class SourceInvalidationEvent(BaseModel):
    event_id: str
    source_ref: ArtifactRef
    invalidation_type: Literal["stale", "withdrawn", "contradicted", "unavailable"]
    affected_claim_ids: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)
    reason: str
```

#### Preconditions

- Phase 2.1 claim ids and lifecycle events are stable enough to mark claims
  stale.
- Phase 1.2 DAG models and persistence tests are green.
- Phase 1.3 evidence snippets have stable source ids and spans.

Baseline:

```bash
uv run pytest tests/scientist/research_dag tests/scientist/evidence -q
uv run pytest tests/tools/test_scientist_best_in_class_phase1_2.py -q
```

#### Non-goals

- Do not call live web during replay.
- Do not promise deterministic LLM output replay.
- Do not expose hidden benchmark answers in replay/diff exports.
- Do not replace engine checkpoints or workflow specs.

#### Existing surfaces

```text
src/polisyos/scientist/research_dag/models.py
src/polisyos/scientist/research_dag/replay.py
src/polisyos/scientist/research_dag/diff.py
src/polisyos/scientist/research_dag/projections.py
src/polisyos/scientist/evidence/**
src/polisyos/scientist/claims/**
src/polisyos/scientist/provenance/run_dag.py
src/polisyos/scientist/engine/checkpoint.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.2A | Replay plan | `research_dag/replay.py` | Plan pinned/audit replay and unsupported steps | `test_replay_plan.py` |
| 2.2B | Deep comparison | `research_dag/comparison.py`, `diff.py` | Queries/sources/snippets/claims/governance diff | `test_comparison.py` |
| 2.2C | Invalidation | `research_dag/invalidation.py` | Source invalidation propagation to claims and nodes | `test_invalidation.py` |
| 2.2D | Claim integration | `claims/lifecycle.py` | Mark affected claims stale/invalidated | lifecycle integration test |
| 2.2E | Redaction audit | replay export helpers | Hidden/private refs removed from public replay | negative tests |
| 2.2F | Reference docs | `research-dag-replay.md` | Replay semantics and limits | docs gate |
| 2.2G | CI gate | `check_scientist_best_in_class_phase2_2.py` | Phase readiness report | tools test |

#### Migration plan

1. Add replay plans without changing workflow execution.
2. Add comparison report as optional sidecar.
3. Wire invalidation into Claim Ledger lifecycle only after Phase 2.1 lands.
4. Show `replay_status = "legacy_minimal"` for Phase 1.2 DAGs without enough
   node metadata.
5. Require replay plans for high-risk reissue workflows only after Phase 2.6.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_2.replay_plan
scientist.best_in_class.wave2.phase2_2.source_invalidation
```

#### Required negative tests

- Replay plan requiring live web is rejected for audit mode.
- Hidden benchmark/private refs do not appear in public replay export.
- Invalidation event with missing source ref fails validation.
- Orphaned invalidation target claim/node fails validation.
- Legacy DAG renders `legacy_minimal`, not success.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_2.py
tests/tools/test_scientist_best_in_class_phase2_2.py
```

Gate checks:

- replay/comparison/invalidation modules import;
- pinned replay fixture validates without live web;
- diff fixture includes changed sources, claims and governance outcomes;
- public replay fixture contains no hidden refs;
- reference page exists.

#### Rollout

Shadow replay reports for representative runs. Enable source invalidation as a
warning first, then let Phase 2.6 use it for review/reissue triggers.

#### Kill rules

Do not promote if:

- replay attempts live fetches in audit mode;
- hidden benchmark data leaks through diff or replay exports;
- invalidation can mark claims stale without evidence/ref lineage;
- comparison cannot identify changed claim ids.

---

## Фаза 2.3 - VOI scheduler

**Длительность:** 4-6 недель.
**Тезис:** Scientist compute should be allocated by expected value of
information, not static pipeline habit.

**Статус:** closed - VOI decision/report contracts, candidate scheduler report
emission, source verification VOI, human escalation VOI, calibration/regret
guards, CAS persistence, `voi_run_report_ref` sidecars, decision packet
projection, reference docs and Phase 2.3 gate accepted.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_3.py
policy-engine/tests/scientist/search/test_voi_models.py
policy-engine/tests/scientist/search/test_voi_reports.py
policy-engine/tests/scientist/search/test_voi_calibration.py
policy-engine/tests/scientist/evidence/test_claim_support_voi.py
policy-engine/tests/scientist/human_review/test_voi_escalation.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_3.py
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

### Execution details

#### Goal

Make VOI the explanation layer for expensive evaluation/search/review choices.
The scheduler can prioritize work, but cannot waive mandatory evidence,
benchmark authority, governance or human-review gates.

#### Current-code correction

`src/polisyos/scientist/search/voi_scheduler.py` already contains candidate
VOI scheduling primitives. This phase extends that surface instead of creating
a separate scheduler stack.

#### Proposed contracts

```python
class VOIDecisionType(str, Enum):
    CANDIDATE_EVALUATION = "candidate_evaluation"
    SOURCE_VERIFICATION = "source_verification"
    HUMAN_ESCALATION = "human_escalation"
    ADVERSARIAL_CHALLENGE = "adversarial_challenge"
    STOP_SEARCH = "stop_search"


class VOIDecisionRecord(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    decision_id: str
    run_id: str
    decision_type: VOIDecisionType
    recommended_action: str
    expected_value: float
    expected_cost: float = Field(ge=0.0)
    expected_risk_reduction: float = Field(ge=0.0)
    mandatory_gate_overrides: list[str] = Field(default_factory=list)
    explanation: str
    input_refs: list[ArtifactRef] = Field(default_factory=list)


class VOIRunReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    decisions: list[VOIDecisionRecord] = Field(default_factory=list)
    total_expected_cost: float = Field(ge=0.0)
    calibration_status: str
    shadow_baseline_ref: ArtifactRef | None = None
```

#### Preconditions

- Phase 1.5 benchmark authority and Phase 1.6 human-review gates remain
  fail-closed where required.
- Current search/funnel/autotune tests are green.
- Phase 2.1 Claim Ledger exposes blocked/contested claims for source/review VOI.

Baseline:

```bash
uv run pytest tests/scientist/search tests/scientist/autotune -q
uv run pytest tests/scientist/human_review tests/scientist/evals -q
```

#### Non-goals

- Do not let VOI skip required benchmark authority evidence.
- Do not make learned VOI default-on.
- Do not require probabilistic optimality proof in v1.
- Do not use provider/LLM calls to estimate VOI in unit tests.

#### Existing surfaces

```text
src/polisyos/scientist/search/voi_scheduler.py
src/polisyos/scientist/search/stopping.py
src/polisyos/scientist/search/strategies/**
src/polisyos/scientist/search/funnel/**
src/polisyos/scientist/human_review/oversight_policy.py
src/polisyos/scientist/evidence/**
src/polisyos/scientist/evals/authority.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.3A | VOI contracts | `search/voi_models.py` | Decision/report models | `test_voi_models.py` |
| 2.3B | Candidate adapter | `search/voi_scheduler.py` | Existing candidate scheduler emits `VOIDecisionRecord` | scheduler tests |
| 2.3C | Source verification VOI | `evidence/claim_support.py`, `search/voi_models.py` | Prioritize contested/unsupported claim evidence | source VOI tests |
| 2.3D | Human escalation VOI | `human_review/voi_escalation.py` | Auditable review escalation recommendation | human-review tests |
| 2.3E | Calibration/regret | `search/voi_calibration.py` | Shadow baseline comparison and regret report | calibration tests |
| 2.3F | Persistence | `search/voi_scheduler.py` or `voi_reports.py` | CAS-persisted `VOIRunReport` | persistence tests |
| 2.3G | Reference docs | `voi-scheduler.md` | Compute law and mandatory-gate rule | docs gate |
| 2.3H | CI gate | `check_scientist_best_in_class_phase2_3.py` | Phase readiness report | tools test |

#### Migration plan

1. Preserve existing `SimpleVOIScheduler` APIs.
2. Add report emission in shadow mode.
3. Wire candidate evaluation first; source verification and human escalation
   remain advisory.
4. Compare against static scheduling for 20 representative offline runs.
5. Only allow default use when safety is non-worse and cost targeting improves.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_3.voi_reports
scientist.best_in_class.wave2.phase2_3.voi_scheduler_shadow
scientist.best_in_class.wave2.phase2_3.voi_scheduler_default
```

#### Required negative tests

- VOI cannot waive missing benchmark authority evidence.
- VOI cannot suppress required human review for high-risk publication.
- Negative expected value must produce `defer`, `reject` or `stop_search`.
- Report with no explanation fails validation.
- Learned/shadow VOI cannot become default without calibration and regret refs.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_3.py
tests/tools/test_scientist_best_in_class_phase2_3.py
```

Gate checks:

- VOI models import and fixture validates;
- existing scheduler emits report-compatible records;
- mandatory-gate override fixture is blocked;
- calibration fixture reports baseline comparison;
- docs list mandatory gates that VOI cannot waive.

#### Rollout

Start with report-only shadow mode. Enable advisory scheduling for offline
candidate search. Keep human escalation advisory until review false-pass and
false-block rates are measured.

#### Kill rules

Do not promote if:

- VOI reduces required evidence coverage;
- human-review escalation becomes less auditable;
- shadow regret is worse than static scheduling without explanation;
- cost savings come from skipping mandatory gates.

---

## Фаза 2.4 - Reflexive memory and failure intelligence

**Длительность:** 4-5 недель.
**Тезис:** Best-in-class Scientist learns from failures without contaminating
future evaluations.

**Статус:** closed - governed memory facade over existing failure cards and
lesson registry, scoped applicability, hidden-eval/canary contamination
guards, warning-only retrieval, consolidation/revocation, Research DAG memory
projection, reference docs and Phase 2.4 gate accepted.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_4.py
policy-engine/tests/scientist/memory/test_failure_lessons.py
policy-engine/tests/scientist/memory/test_applicability.py
policy-engine/tests/scientist/memory/test_contamination.py
policy-engine/tests/scientist/memory/test_retrieval.py
policy-engine/tests/scientist/memory/test_consolidation.py
policy-engine/tests/scientist/memory/test_research_dag_projection.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_4.py
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

### Execution details

#### Goal

Turn existing failure cards, lesson cards and agent memory into a governed
memory surface that helps future runs recover from failures without leaking
hidden eval content or silently steering decisions.

#### Current-code correction

The repo already has `search/failure_cards.py`, `search/lessons.py`,
`agent/memory.py`, `agent/persistent_memory.py` and `agent/vector_memory.py`.
This phase should wrap and harden those surfaces; it should not create an
unrelated memory subsystem that bypasses existing lesson registries.

#### Proposed contracts

```python
class MemoryVisibility(str, Enum):
    LOCAL_RUN = "local_run"
    TENANT = "tenant"
    DOMAIN = "domain"
    GLOBAL_PUBLIC = "global_public"


class LessonApplicability(BaseModel):
    lesson_id: str
    applies: bool
    reasons: list[str] = Field(default_factory=list)
    scope: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime | None = None


class ReflexiveMemoryEvent(BaseModel):
    event_id: str
    run_id: str
    lesson_id: str
    action: Literal["retrieved", "applied", "rejected", "revoked"]
    applicability: LessonApplicability
    research_dag_node_id: str | None = None
```

#### Preconditions

- Phase 1.5 hidden eval leakage controls remain in place.
- Phase 2.2 DAG replay can show memory influence as nodes/metadata.
- Current search lesson and agent memory tests are green.

Baseline:

```bash
uv run pytest tests/scientist/search tests/scientist/agent -q
uv run pytest tests/scientist/evals/test_leakage.py -q
```

#### Non-goals

- Do not store hidden benchmark answers in reusable memory.
- Do not use memory as evidence for public claims.
- Do not make vector similarity the only applicability criterion.
- Do not default-enable memory influence on high-risk workflows.

#### Existing surfaces

```text
src/polisyos/scientist/search/failure_cards.py
src/polisyos/scientist/search/lessons.py
src/polisyos/scientist/agent/memory.py
src/polisyos/scientist/agent/persistent_memory.py
src/polisyos/scientist/agent/vector_memory.py
src/polisyos/scientist/research_dag/projections.py
src/polisyos/scientist/evals/leakage.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.4A | Memory facade | `scientist/memory/__init__.py`, `failure_lessons.py` | Canonical wrapper around existing lesson/failure surfaces | model tests |
| 2.4B | Applicability | `memory/applicability.py` | Scope, expiry and reasoned applicability checks | applicability tests |
| 2.4C | Contamination guards | `memory/contamination.py` | Hidden eval and canary leakage checks | negative tests |
| 2.4D | Retrieval | `memory/retrieval.py` | Deterministic retrieval result with lesson ids/reasons | retrieval tests |
| 2.4E | Consolidation/revocation | `memory/consolidation.py` | Merge lessons, revoke invalidated lessons | consolidation tests |
| 2.4F | DAG projection | `research_dag/projections.py` | Memory influence node or metadata | DAG tests |
| 2.4G | Reference docs | `reflexive-memory.md` | Operational rules and contamination posture | docs gate |
| 2.4H | CI gate | `check_scientist_best_in_class_phase2_4.py` | Phase readiness report | tools test |

#### Migration plan

1. Keep existing search lesson registry as the storage substrate.
2. Add contamination and applicability wrappers.
3. Emit memory retrieval events into Research DAG in shadow mode.
4. Use memory only for warnings/anti-patterns until recovery evals pass.
5. Allow revocation to mark lessons unusable without deleting audit history.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_4.reflexive_memory
scientist.best_in_class.wave2.phase2_4.memory_influence_shadow
scientist.best_in_class.wave2.phase2_4.memory_influence_default
```

#### Required negative tests

- Hidden holdout ids, hidden suite ids and canaries are rejected from reusable
  memory.
- Expired or out-of-scope lesson is retrieved as non-applicable.
- Revoked lesson cannot influence scheduling or prompting.
- Memory retrieval without applicability reasons fails validation.
- Memory influence missing from Research DAG is reported.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_4.py
tests/tools/test_scientist_best_in_class_phase2_4.py
```

Gate checks:

- memory package imports;
- hidden leakage fixture blocks reusable memory;
- applicability fixture explains include/exclude decisions;
- revocation fixture prevents reuse;
- docs list hidden-eval and DAG-influence rules.

#### Rollout

Start read-only: retrieve lessons and render warnings without changing
decisions. Enable advisory influence only after held-out failure recovery
improves and contamination tests stay green.

#### Kill rules

Do not promote if:

- hidden eval content can enter reusable memory;
- memory can affect high-risk decisions without visible DAG attribution;
- revoked lessons remain retrievable as applicable;
- recovery improvement is not measured on held-out scenarios.

---

## Фаза 2.5 - Adversarial challenge factory

**Длительность:** 4-6 недель.
**Тезис:** Scientist should continuously generate and rotate adversarial
challenges, not wait for hand-written evals.

**Статус:** closed - challenge factory contracts, failure-card/near-miss/
policy-risk generation, challenge mutation, review-before-hidden admission,
sentinel metadata, red-team registry, rotating pack lineage/freshness,
benchmark authority lineage projection, reference docs and Phase 2.5 gate
accepted.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_5.py
policy-engine/tests/scientist/evals/test_challenge_factory.py
policy-engine/tests/scientist/evals/test_sentinels.py
policy-engine/tests/scientist/evals/test_red_team.py
policy-engine/tests/scientist/evals/test_rotation.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_5.py
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

### Execution details

#### Goal

Create a controlled challenge factory that turns observed failures and
near-misses into candidate challenge packs, then promotes only reviewed packs
into benchmark authority. Generation is not the same as hidden-eval admission.

#### Current-code correction

`evals/challenge_packs.py` already defines rotating/sentinel/adversarial pack
metadata. This phase adds generation, review, red-team and rotation lifecycle
around that metadata.

#### Proposed contracts

```python
class ChallengeStatus(str, Enum):
    GENERATED = "generated"
    REVIEW_REQUIRED = "review_required"
    APPROVED_FOR_PUBLIC = "approved_for_public"
    APPROVED_FOR_PRIVATE = "approved_for_private"
    APPROVED_FOR_HIDDEN = "approved_for_hidden"
    REJECTED = "rejected"
    RETIRED = "retired"


class GeneratedChallenge(BaseModel):
    challenge_id: str
    challenge_class: str
    source_failure_refs: list[ArtifactRef] = Field(default_factory=list)
    prompt_or_case_ref: ArtifactRef
    expected_failure_mode: str
    status: ChallengeStatus = ChallengeStatus.GENERATED
    leakage_risk: Literal["low", "medium", "high"] = "medium"
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)


class ChallengeFactoryReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    generated: list[GeneratedChallenge] = Field(default_factory=list)
    promoted_pack_refs: list[ArtifactRef] = Field(default_factory=list)
    rejected_reasons: list[str] = Field(default_factory=list)
```

#### Preconditions

- Phase 1.5 benchmark authority is the only promotion authority.
- Phase 2.4 memory contamination guards are available for generated cases.
- Current challenge pack and leakage tests are green.

Baseline:

```bash
uv run pytest tests/scientist/evals tests/scientist/search -q
uv run pytest tests/tools/test_scientist_benchmark_authority.py -q
```

#### Non-goals

- Do not create real hidden datasets in this phase.
- Do not let generated challenges become hidden without human/reviewer gate.
- Do not use generated challenge success as proof of scientific validity.
- Do not expose hidden challenge answers in public reports or memory.

#### Existing surfaces

```text
src/polisyos/scientist/evals/challenge_packs.py
src/polisyos/scientist/evals/authority.py
src/polisyos/scientist/evals/leakage.py
src/polisyos/scientist/search/failure_cards.py
src/polisyos/scientist/search/adversarial.py
src/polisyos/scientist/search/sentinels.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.5A | Challenge model | `evals/challenge_factory.py` | Generated challenge/report contracts | model tests |
| 2.5B | Failure-card generator | `challenge_factory.py` | Convert failure cards into candidate challenges | generator tests |
| 2.5C | Sentinels | `evals/sentinels.py` | Sentinel case metadata and admission rules | sentinel tests |
| 2.5D | Red-team scenarios | `evals/red_team.py` | Red-team class registry and risk tags | red-team tests |
| 2.5E | Rotation lifecycle | `evals/rotation.py`, `challenge_packs.py` | Expiry, refresh, lineage and dedupe | rotation tests |
| 2.5F | Authority integration | `evals/authority.py` | Challenge pack lineage in verdicts | authority tests |
| 2.5G | Reference docs | `adversarial-challenge-factory.md` | Review/promotion policy | docs gate |
| 2.5H | CI gate | `check_scientist_best_in_class_phase2_5.py` | Phase readiness report | tools test |

#### Migration plan

1. Generate candidate challenge reports only.
2. Add reviewed public/private packs before hidden packs.
3. Register approved packs with `BenchmarkRegistry`.
4. Require fresh rotating challenge evidence for near-frontier promotion only
   after authority integration is stable.
5. Keep generated-but-unreviewed cases out of reusable memory.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_5.challenge_factory
scientist.best_in_class.wave2.phase2_5.require_fresh_rotating_challenge
```

#### Required negative tests

- Generated challenge cannot be registered as hidden without review refs.
- Challenge containing hidden answer/canary is rejected from public export.
- Expired rotating pack blocks near-frontier promotion.
- Duplicate challenge lineage is deduped, not double-counted.
- Failure card with private data cannot generate public challenge content.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_5.py
tests/tools/test_scientist_best_in_class_phase2_5.py
```

Gate checks:

- challenge factory modules import;
- failure-card fixture generates candidate challenges;
- unreviewed hidden promotion fixture fails;
- rotation expiry fixture blocks promotion;
- reference page exists and documents review-before-hidden.

#### Rollout

Run generation in shadow mode from failure cards. Promote only reviewed public
packs first. Hidden/adversarial packs remain internal and redacted from public
outputs.

#### Kill rules

Do not promote if:

- generated challenges can enter hidden evals without review;
- hidden answers leak into docs, public reports or memory;
- benchmark authority cannot trace pack lineage;
- fresh rotating challenge requirements block unrelated low-risk workflows.

---

## Фаза 2.6 - Continuous governance and reissue loop

**Статус:** closed - implemented as an additive continuous-governance package
with monitor events, source invalidation bridge, reissue packets, incidents,
withdrawal records, validity reports, governance/decision-packet links and a
Phase 2.6 CI gate. Runtime effects remain shadow/governance-controlled.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_6.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_6.py
policy-engine/tests/scientist/continuous_governance/
```

### Acceptance criteria

- A source invalidation can mark dependent claims stale.
- Drift monitor can trigger review/reissue.
- Reissue packet links old and new claim ledgers.
- Withdrawal status is explicit and auditable.

### Execution details

#### Goal

Make decision artifacts living objects: they can remain valid, become stale,
require review, be reissued, or be withdrawn. This phase connects source
invalidation, drift signals, Claim Ledger lifecycle and human review.

#### Proposed contracts

```python
class DecisionValidityStatus(str, Enum):
    VALID = "valid"
    MONITORING = "monitoring"
    STALE = "stale"
    REVIEW_REQUIRED = "review_required"
    REISSUED = "reissued"
    WITHDRAWN = "withdrawn"


class GovernanceMonitorEvent(BaseModel):
    event_id: str
    decision_packet_ref: ArtifactRef
    event_type: Literal[
        "source_invalidation",
        "calibration_drift",
        "fairness_drift",
        "policy_context_drift",
        "incident",
    ]
    severity: Literal["info", "warning", "block"]
    affected_claim_ids: list[str] = Field(default_factory=list)
    reason: str


class ReissuePacket(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    original_decision_packet_ref: ArtifactRef
    new_decision_packet_ref: ArtifactRef | None = None
    original_claim_ledger_ref: ArtifactRef | None = None
    new_claim_ledger_ref: ArtifactRef | None = None
    status: DecisionValidityStatus
    monitor_event_refs: list[ArtifactRef] = Field(default_factory=list)
    human_review_ref: ArtifactRef | None = None
```

#### Preconditions

- Phase 2.1 Claim Ledger lifecycle can mark claims stale/invalidated.
- Phase 2.2 source invalidation identifies affected claims and DAG nodes.
- Phase 1.6 human review packets and decisions remain CAS-persisted.

Baseline:

```bash
uv run pytest tests/scientist/claims tests/scientist/research_dag tests/scientist/human_review -q
uv run pytest tests/scientist/governance -q
```

#### Non-goals

- Do not build production monitoring infrastructure.
- Do not claim legal compliance or post-market certification.
- Do not automatically withdraw public artifacts without governance policy.
- Do not make drift thresholds universal across domains.

#### Existing surfaces

```text
src/polisyos/scientist/frontier_runtime.py
src/polisyos/scientist/governance/**
src/polisyos/scientist/human_review/**
src/polisyos/scientist/claims/**
src/polisyos/scientist/research_dag/invalidation.py
src/polisyos/scientist/validation/fairness_audit.py
src/polisyos/scientist/validation/phase5_preflight.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.6A | Monitor contracts | `continuous_governance/monitors.py` | Event models and severity policy | model tests |
| 2.6B | Invalidation bridge | `continuous_governance/invalidation.py` | Source/drift to claim status bridge | invalidation tests |
| 2.6C | Reissue workflow | `continuous_governance/reissue.py` | Reissue packet and old/new links | reissue tests |
| 2.6D | Incident posture | `continuous_governance/incident.py` | Incident report and withdrawal triggers | incident tests |
| 2.6E | Reports | `continuous_governance/reports.py` | Public/internal validity reports | report tests |
| 2.6F | Governance integration | governance report/decision packet | validity status links | integration tests |
| 2.6G | Reference docs | `continuous-governance.md` | Reissue/withdrawal semantics | docs gate |
| 2.6H | CI gate | `check_scientist_best_in_class_phase2_6.py` | Phase readiness report | tools test |

#### Migration plan

1. Emit validity reports as shadow sidecars.
2. Let invalidation mark claims stale without changing public artifacts.
3. Add reviewer-visible reissue packets.
4. Add withdrawal status only as explicit governance action.
5. Wire continuous governance into decision-grade compiler in Phase 2.7.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_6.continuous_governance
scientist.best_in_class.wave2.phase2_6.enable_reissue_workflow
scientist.best_in_class.wave2.phase2_6.enable_withdrawal_status
```

#### Required negative tests

- Source invalidation with no affected claim/DAG lineage cannot silently pass.
- Drift monitor trigger must create review or reissue recommendation.
- Reissue packet without original decision and claim ledger refs fails.
- Withdrawal status must include actor, reason and audit event.
- Public report cannot expose hidden benchmark/internal monitor refs.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_6.py
tests/tools/test_scientist_best_in_class_phase2_6.py
```

Gate checks:

- continuous governance package imports;
- invalidation fixture marks dependent claim stale;
- reissue fixture links old/new ledgers;
- withdrawal fixture includes audit metadata;
- reference page exists.

#### Rollout

Start with shadow validity reports. Enable review/reissue recommendations in
staging. Require human approval before any withdrawal status can affect public
exports.

#### Kill rules

Do not promote if:

- stale/withdrawn status can be set without audit trail;
- old and new claim ledgers are not linked;
- false alarms overwhelm human-review queues in shadow data;
- public reports leak hidden/internal monitor refs.

---

## Фаза 2.7 - Decision-grade research compiler

**Status:** `closed` - implemented in
`src/polisyos/scientist/publisher.py`, `src/polisyos/scientist/orchestrator/decision_card.py`,
`src/polisyos/scientist/claims/export.py`,
`docs/reference/scientist/decision-grade-compiler.md`, and
`tools/ci/check_scientist_best_in_class_phase2_7.py`.

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
policy-engine/tools/ci/check_scientist_best_in_class_phase2_7.py
policy-engine/tests/scientist/test_decision_grade_compiler.py
policy-engine/tests/tools/test_scientist_best_in_class_phase2_7.py
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

### Execution details

#### Goal

Compile audience-specific outputs from the same governed source artifacts:
Claim Ledger, Research DAG, evidence bundle, benchmark authority and human
review. The compiler should reduce duplication between packet, decision card,
reviewer packet, public summary and machine export.

#### Current-code correction

`publisher.py`, `orchestrator/decision_card.py` and `claims/export.py` already
exist or are planned by earlier phases. Phase 2.7 should refactor/extend these
surfaces rather than creating a second publishing path.

#### Proposed contracts

```python
class OutputAudience(str, Enum):
    PUBLIC = "public"
    REVIEWER = "reviewer"
    EXPERT = "expert"
    MACHINE = "machine"


class OutputOmissionRecord(BaseModel):
    field_path: str
    audience: OutputAudience
    reason: str
    hidden_ref: ArtifactRef | None = None


class DecisionGradeExport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    audience: OutputAudience
    claims_ref: ArtifactRef
    research_dag_ref: ArtifactRef
    payload: dict[str, object]
    omissions: list[OutputOmissionRecord] = Field(default_factory=list)
```

#### Preconditions

- Phase 2.1 Claim Ledger export helpers exist.
- Phase 2.2 replay/diff status is available for audit fields.
- Phase 2.6 continuous governance status can be included when present.

Baseline:

```bash
uv run pytest tests/scientist/test_decision_packet_node_v3.py tests/scientist/orchestrator -q
uv run pytest tests/scientist/claims tests/scientist/human_review -q
```

#### Non-goals

- Do not build frontend UI in this phase.
- Do not remove existing packet/card APIs abruptly.
- Do not publish hidden benchmark/private refs in public tier.
- Do not rewrite every legacy report format.

#### Existing surfaces

```text
src/polisyos/scientist/publisher.py
src/polisyos/scientist/orchestrator/decision_card.py
src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py
src/polisyos/scientist/claims/export.py
src/polisyos/scientist/human_review/packets.py
src/polisyos/scientist/evals/reports.py
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.7A | Export contracts | `publisher.py`, `claims/export.py` | `DecisionGradeExport` and omissions | model tests |
| 2.7B | Public summary | `publisher.py` | Approved claims, limits, no hidden refs | public export tests |
| 2.7C | Reviewer packet | `human_review/packets.py`, `publisher.py` | Claim/evidence/blocker controls | reviewer tests |
| 2.7D | Expert appendix | `publisher.py` | Methods, assumptions, uncertainty, eval scope | expert tests |
| 2.7E | Machine export | `publisher.py` | Trust/provenance payload for UI/API/audit | machine tests |
| 2.7F | Decision card bridge | `orchestrator/decision_card.py` | Card derives from compiler output | card regressions |
| 2.7G | Reference docs | `decision-grade-compiler.md` | Tier contracts and omission rules | docs gate |
| 2.7H | CI gate | `check_scientist_best_in_class_phase2_7.py` | Phase readiness report | tools test |

#### Migration plan

1. Add compiler outputs without deleting existing packet/card code.
2. Make decision card consume compiler output where possible.
3. Add `omissions` to every audience tier.
4. Publish machine export for frontend Trust View.
5. Deprecate duplicated packet fields only after compatibility fixtures pass.

#### Feature flags

```text
scientist.best_in_class.wave2.phase2_7.decision_grade_compiler
scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card
```

#### Required negative tests

- Public export containing hidden benchmark/private refs fails.
- Any omitted blocker without omission reason fails.
- Reviewer export missing blocked claims fails.
- Machine export missing `claims_ref` or `research_dag_ref` fails.
- Legacy decision card remains loadable.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_phase2_7.py
tests/tools/test_scientist_best_in_class_phase2_7.py
```

Gate checks:

- compiler models import;
- four audience fixtures validate;
- omission rules block silent blocker removal;
- public fixture contains no hidden refs;
- reference page exists.

#### Rollout

Start compiler in parallel with existing packet/card generation. Compare payload
coverage. Move frontend/API consumers to machine export only after parity and
redaction tests pass.

#### Kill rules

Do not promote if:

- output tiers disagree about claim status or blockers;
- hidden/internal refs leak in public output;
- frontend trust fields cannot be rendered from machine export;
- legacy packet/card consumers break.

---

## Фаза 2.8 - System closeout

**Статус:** closed - `docs/reference/scientist/best-in-class-wave2-acceptance.md`,
`docs/reference/scientist/best-in-class-maturity.md`,
`docs/reference/scientist/wave2-migration-notes.md`,
`tools/ci/check_scientist_best_in_class_wave2.py`, and
`tests/tools/test_scientist_best_in_class_wave2.py`.

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

### Execution details

#### Goal

Close Wave 2 only when the primitives work together: Claim Ledger lifecycle,
Research DAG replay, VOI, reflexive memory, challenge factory, continuous
governance and decision-grade compiler agree on refs, status and rollout
evidence.

#### Preconditions

- Phase 2.0 through 2.7 gates are green.
- Wave 1 closeout remains green.
- At least one representative offline/shadow evidence bundle exists.

Baseline:

```bash
uv run python tools/ci/check_scientist_best_in_class_wave1.py --repo-root . --output-format json --require-passing
uv run pytest tests/tools/test_scientist_best_in_class_phase2_*.py -q
```

#### Deliverable expansion

```text
policy-engine/tools/ci/check_scientist_best_in_class_wave2.py
policy-engine/tests/tools/test_scientist_best_in_class_wave2.py
policy-engine/docs/reference/scientist/best-in-class-wave2-acceptance.md
policy-engine/docs/reference/scientist/best-in-class-maturity.md
policy-engine/docs/reference/scientist/wave2-migration-notes.md
```

#### Work packages

| WP | Name | Files | Output | Gate |
| --- | --- | --- | --- | --- |
| 2.8A | Phase gate aggregator | `check_scientist_best_in_class_wave2.py` | Runs phase gates 2.0-2.7 | tools test |
| 2.8B | Cross-phase invariants | wave2 gate | Claim/DAG/VOI/memory/governance/compiler agreement | negative tests |
| 2.8C | Shadow evidence summary | `best-in-class-wave2-acceptance.md` | Cost/safety/quality measurements | docs gate |
| 2.8D | Migration notes | `wave2-migration-notes.md` | Legacy fields, feature flags, rollback | docs gate |
| 2.8E | Maturity model | `best-in-class-maturity.md` | Best-in-class maturity levels | docs gate |

#### Cross-phase invariants

- No decision-bearing claim lacks lifecycle state and current export status.
- Replay/diff can explain changed claims and changed governance outcome.
- VOI decisions cannot waive benchmark authority or human-review gates.
- Memory influence is visible in Research DAG and contamination-clean.
- Challenge packs used for promotion are reviewed and registered.
- Reissued/withdrawn decisions link old and new claim ledgers.
- Public/reviewer/expert/machine outputs derive from the same refs.

#### Required negative tests

- Wave 2 gate fails if any phase gate fails.
- A compiler output with hidden benchmark refs in public tier fails.
- A VOI report that skips mandatory human review fails.
- A memory event with hidden eval canary fails.
- A reissue packet without old/new ledger linkage fails.
- A claim changed between runs but absent from replay diff fails.

#### CI gate

Create:

```text
tools/ci/check_scientist_best_in_class_wave2.py
tests/tools/test_scientist_best_in_class_wave2.py
```

Gate checks:

- all phase gates 2.0-2.7 green;
- Wave 1 gate still green;
- required reference pages exist;
- selected fixtures validate all cross-phase invariants;
- migration notes list every public field or flag introduced in Wave 2;
- shadow evidence includes either measurable quality lift or cost/safety
  improvement, with residual risks listed.

#### Rollout

Wave 2 remains read-only/shadow until this closeout gate is green. After closeout,
production promotion is still per-feature and can be rolled back via flags.

#### Kill rules

Do not close Wave 2 if:

- any phase has no CI gate;
- shadow evidence is absent or only anecdotal;
- old artifacts stop loading;
- public exports leak hidden/private refs;
- migration notes cannot explain rollback for each new primitive.

---

## 8. Wave R - Research-first companion agenda

Wave 1 and Wave 2 closed the runtime substrate: Claim Ledger, Research DAG,
benchmark authority, VOI reports, reflexive memory, challenge factory,
continuous governance and decision-grade compiler now exist as governed,
additive primitives. The remaining hard questions are no longer "can we store
this artifact?" but "what scientific rule makes this artifact trustworthy
enough to promote?".

Wave R is therefore not a third engineering wave. It is the research program
that decides which claims, gates, metrics and promotion rules are scientifically
defensible enough to move selected workflows from maturity level 2 toward
maturity level 3+.

### 8.0. Current research surface after Wave 2

| Primitive | Current repo state | Remaining research question |
| --- | --- | --- |
| Claim Ledger | Claim records, lifecycle, append-only audit, diff, export and blocked-claim summaries exist. | What is a sufficient and computable support relation for each claim family? |
| Research DAG | DAG sidecar, replay planning, trajectory comparison and source invalidation exist. | Which replay differences are decision-relevant rather than incidental? |
| Deep evidence stack | Safe fetch, source quality signals, snippets and claim-support mapping exist. | When is paraphrased or synthesized evidence faithful enough for promotion? |
| Benchmark authority | Public/private/hidden/rotating/sentinel/adversarial split semantics exist. | How do we detect contamination and leakage across memory, web and prior traces? |
| VOI scheduler | VOI decision/report contracts, source VOI, human-review VOI and calibration reports exist. | How should value of information be estimated under mandatory gates and multi-objective policy risk? |
| Reflexive memory | Scoped lessons, applicability, contamination guards, warning-only retrieval and DAG attribution exist. | When does memory improve recovery without contaminating future evaluations? |
| Challenge factory | Generated challenges, sentinels, red-team scenarios, rotation and review-before-hidden admission exist. | Which generated challenges predict real failures and deserve benchmark authority? |
| Continuous governance | Monitor events, source invalidation bridge, reissue packets, incidents, withdrawals and reports exist. | When exactly does drift invalidate, stale, supersede, reissue or withdraw a decision? |
| Decision-grade compiler | Public, reviewer, expert and machine tiers share Claim Ledger and Research DAG refs. | Which explanations improve trust calibration without overclaiming certainty? |

### 8.1. Wave R operating rules

A Wave R track can unlock implementation or promotion only if it produces at
least one of:

- theorem or formal rule with machine-checkable conditions;
- calibrated benchmark or frozen fixture with documented target metric;
- impossibility result with counterexample class;
- validated empirical protocol with uncertainty and residual risks;
- reduction to known solvable problem with explicit assumptions.

Heuristics alone do not unlock default production readiness.

Research artifacts enter Scientist as research-only artifacts:

- `max_readiness = proof_only` or equivalent research-only readiness;
- no public decision artifact may cite them as production evidence;
- hidden benchmark answers and canaries may not enter reusable memory;
- research results must name the Claim Ledger, Research DAG, benchmark pack,
  human-review or compiler fields they would eventually affect;
- every track needs a benchmark proxy before it can receive implementation
  budget beyond prototypes.

Unit tests and CI gates for Wave R must not require live LLM calls. LLM-based
experiments may be run later as quarantined offline evals with pinned inputs,
stored traces or Research DAG summaries, provider/version metadata, leakage
controls and no hidden-answer exposure in public exports or reusable memory.

### 8.2. Phase map

The tracks below can be researched in parallel inside phases, but phase gates
are sequential because later research depends on vocabulary and benchmark
proxies created earlier.

| Phase | Name | Duration | Output |
| --- | --- | --- | --- |
| R0 | Research substrate alignment | 1-2 weeks | Track cards, fixtures, baseline metrics, current-state acceptance and kill rules. |
| R1 | Claim support and citation semantics | 4-6 weeks | Support relation taxonomy, paraphrase-faithfulness benchmark and claim-family thresholds. |
| R2 | Evidence quality, leakage and benchmark validity | 4-6 weeks | Source-quality calibration, leakage tests, contamination bounds and frozen-web protocol. |
| R3 | VOI, human oversight and review economics | 4-6 weeks | VOI estimators, human escalation thresholds, reviewer-burden model and calibration protocol. |
| R4 | Memory, challenge generation and adversarial validity | 4-6 weeks | Reflexive-memory recovery eval, challenge predictive-validity study and rotation policy. |
| R5 | Continuous governance and reissue science | 4-6 weeks | Drift/invalidation semantics, stale/reissue/withdrawal thresholds and audit protocol. |
| R6 | Multi-agent research and explanation quality | 4-6 weeks | Fan-out compression study, context-budget law and trust/explanation calibration metrics. |
| R7 | Research closeout and promotion handoff | 1-2 weeks | Accepted/refuted/deferred track outcomes and engineering handoff list. |

### 8.3. Track catalog

#### R0 - Research substrate alignment

**Question:** What exactly must a Scientist research track produce before it can
affect readiness, default-enable, governance, human review or public export?

**Current implementation surface:** Wave 2 acceptance, maturity model, runtime
contracts and `tools/ci/check_scientist_best_in_class_wave2.py`.

**Research tasks:**

1. Define a research-track card template with hypothesis, benchmark proxy,
   integration target, readiness cap, contamination posture and kill rule.
2. Freeze representative offline/shadow fixtures for claim support, citation,
   VOI, memory, challenge, reissue and compiler tests.
3. Define minimum statistical reporting: effect size, uncertainty, confidence
   interval or posterior interval, sample definition and residual risks.
4. Map each Wave R track to a concrete package owner and reference page.

**Deliverables:** research handoff template, Wave R fixture index, research
substrate CI gate.

**Graduation gate:** every track has a benchmark proxy and non-production
readiness cap before research starts.

**Kill rule:** if a track cannot state a benchmark proxy or falsification case,
it is downgraded to recorded open problem.

#### R1 - Claim support semantics

**Question:** What is a sufficient computable support relation between evidence
snippets, model outputs, counterevidence and typed policy claims?

**Why research-first:** Wave 2 can store support and counterevidence, but
storage is not semantics. Factual, causal, legal, normative, forecast,
distributional, welfare, implementation and source-quality claims need
different support relations.

**Current implementation surface:** `claims/models.py`, `claims/readiness.py`,
`claims/lifecycle.py`, `claims/export.py`, `evidence/claim_support.py`,
[claims.md](../../reference/scientist/claims.md) and
[claim-ledger.md](../../reference/scientist/claim-ledger.md).

**Research tasks:**

1. Define support predicates by claim family.
2. Separate support strength from publishability.
3. Define counterevidence aggregation rules: contradiction, scope mismatch,
   outdated source, missing assumption, legal exception and distributional
   reversal.
4. Define lifecycle transitions that raise, lower, block, supersede or
   invalidate readiness.
5. Produce a minimal formal language that maps to `ClaimRecord`,
   `ClaimSupportLink`, `ClaimLifecycleEvent` and `DecisionReadiness`.

**Benchmark proxy:** hand-labeled claim-support fixture with factual, legal,
policy, causal, contested and invalid-support cases.

**Deliverables:** support taxonomy, claim-family support matrix, counterexample
catalog, fixture grader spec and integration spec for claim readiness.

**Graduation gate:** support rules meet target agreement while preserving zero
false-publish for blocked counterexamples.

**Kill rule:** if support cannot be defined better than lexical overlap for a
claim family, that family remains `review_required` or `research_first`.

#### R2 - Citation faithfulness under paraphrase

**Question:** How can Scientist detect that a cited source supports a
paraphrased or synthesized policy claim rather than only sharing words with it?

**Why research-first:** Exact quote checks are necessary but not sufficient.
Semantic entailment can fail under legal exceptions, temporal scope,
jurisdiction, population or policy-context constraints.

**Current implementation surface:** `evidence/snippet_ledger.py`,
`evidence/verifier.py`, `evidence/source_quality.py`,
`src/polisyos/scholar/search/models.py` and
[deep-research-evidence.md](../../reference/scientist/deep-research-evidence.md).

**Research tasks:**

1. Define faithfulness labels: supports, partially supports, scope-limited,
   contradicts, irrelevant, fabricated and unverifiable.
2. Create paraphrase stress cases for legal provisions, fiscal numbers,
   eligibility rules, causal assumptions, forecasts and welfare claims.
3. Study whether entailment must be claim-family-specific.
4. Define span-level requirements: character spans, table cells or full-document
   context.
5. Define public export language for partial support and unavailable sources.

**Benchmark proxy:** frozen citation-faithfulness pack with snippets, claim
paraphrases, expected labels and hidden adversarial variants.

**Deliverables:** citation-faithfulness rubric, paraphrase fixture,
legal/policy scope mismatch catalog, offline grader interface and public-export
blocking thresholds.

**Graduation gate:** public factual/legal claims hit the configured
faithfulness target with zero hidden-canary leakage.

**Kill rule:** if automated paraphrase faithfulness has high false-pass rates,
public citation verification remains human-reviewed for affected claim classes.

#### R3 - Source quality, freshness and evidence conflict

**Question:** How should Scientist combine source authority, recency,
primary-source status, anti-SEO signals, duplicates and conflict into a
decision-relevant evidence quality score?

**Why research-first:** Wave 1.3 introduced deterministic source-quality
signals, but their weights are heuristic. Treating them as truth would
overclaim.

**Current implementation surface:** `evidence/source_quality.py`,
`evidence/cache.py`, `research_dag/invalidation.py` and
`continuous_governance/invalidation.py`.

**Research tasks:**

1. Calibrate authority/freshness scores against source-type labels.
2. Define conflict resolution: newer source vs primary source, primary law vs
   commentary, empirical paper vs meta-analysis and jurisdiction conflicts.
3. Define freshness TTL by claim family and source class.
4. Define when source invalidation marks claims stale, review-required or
   withdrawn.
5. Produce uncertainty categories for quality scores.

**Benchmark proxy:** source-quality calibration pack with dated, conflicting,
stale and hidden withdrawn-source cases.

**Deliverables:** calibrated source-quality model or rulebook, TTL matrix,
conflict taxonomy and invalidation-to-claim-status mapping.

**Graduation gate:** freshness and conflict decisions meet target agreement and
never mark withdrawn primary sources as publishable.

**Kill rule:** if quality signals cannot be calibrated, they remain advisory
and may not drive readiness without human review.

#### R4 - VOI for governed policy research

**Question:** How should Scientist estimate the value of more evidence,
additional evaluation, adversarial challenge, causal computation or human
review when mandatory gates cannot be waived?

**Why research-first:** A VOI scheduler exists, but estimating expected value
and risk reduction is the real hard part. Cost savings must not come from
skipping required evidence.

**Current implementation surface:** `search/voi_models.py`,
`search/voi_scheduler.py`, `search/voi_calibration.py`,
`human_review/voi_escalation.py` and `evals/authority.py`.

**Research tasks:**

1. Define a multi-objective VOI objective: quality lift, uncertainty reduction,
   risk reduction, review cost, compute cost, delay and fairness/legal harm.
2. Separate advisory VOI from mandatory gates: benchmark authority, human
   review, governance blockers and hidden eval evidence are constraints.
3. Define regret metrics for stopping too early or escalating too often.
4. Calibrate VOI against static scheduling on representative offline runs.
5. Define when learned VOI can be considered for default scheduling.

**Benchmark proxy:** offline scheduling traces with late-discovered evidence,
near-frontier candidates, high-risk review cases and false-save traps.

**Deliverables:** VOI objective definition, calibration protocol, regret report
schema and default-enable evidence checklist.

**Graduation gate:** VOI is non-worse on safety and governance false-pass rate,
while improving cost targeting.

**Kill rule:** any VOI policy that saves cost by reducing mandatory evidence
coverage is rejected.

#### R5 - Human oversight thresholds and automation bias

**Question:** When should human review be required, what should reviewers see
and how should Scientist measure whether review improves decisions rather than
rubber-stamping them?

**Why research-first:** Human oversight is implemented as a control plane, but
thresholds and reviewer workload are policy and behavioral research questions.

**Current implementation surface:** `human_review/**`, governance passes,
`continuous_governance/reissue.py` and
[human-oversight.md](../../reference/scientist/human-oversight.md).

**Research tasks:**

1. Define review-required thresholds by risk tier, claim type, public-sector
   posture, legal uncertainty, distributional impact and reissue/withdrawal
   stakes.
2. Define automation-bias mitigations: counterevidence-first ordering,
   uncertainty prominence, dissent prompts, reviewer action taxonomy and
   override friction.
3. Measure reviewer burden and false-pass/false-block tradeoffs.
4. Define two-person verification triggers.
5. Define "explanation insufficient" criteria.

**Benchmark proxy:** human-review simulation pack with reviewer packets, known
blockers, ambiguous cases, automation-bias traps and expected actions.

**Deliverables:** risk-tier threshold matrix, reviewer-packet ordering rules,
false-pass/false-block protocol and escalation policy spec.

**Graduation gate:** thresholds reduce false-pass without unacceptable
false-block or reviewer-burden growth.

**Kill rule:** if review actions cannot be audited or reviewer burden dominates
benefit, the affected workflow remains blocked or internal-only.

#### R6 - Benchmark leakage, memory contamination and evaluation hygiene

**Question:** How can Scientist prove that hidden eval content, canaries,
previous traces and generated challenge answers do not contaminate reusable
memory or public artifacts?

**Why research-first:** Wave 2 has contamination guards, but memory, web cache,
generated challenges, hidden holdouts and public exports interact over time.

**Current implementation surface:** `evals/leakage.py`,
`memory/contamination.py`, `evidence/cache.py`, `evals/challenge_factory.py`
and [benchmark-authority.md](../../reference/scientist/benchmark-authority.md).

**Research tasks:**

1. Define contamination classes: direct hidden answer, canary token, paraphrased
   answer, challenge lineage, memorized grader feedback and public-export
   leakage.
2. Define redaction guarantees for public, reviewer, expert and machine tiers.
3. Define whether memory retrieval can be used in eval contexts at all.
4. Define rotating holdout refresh policy under possible contamination.
5. Design sentinel and canary strategies that catch exact and paraphrased
   leakage.

**Benchmark proxy:** leakage stress suite with canaries, paraphrased hidden
facts, memory events, challenge cases and public export attempts.

**Deliverables:** contamination taxonomy, canary strategy, leakage detector
evaluation and public/export redaction checklist.

**Graduation gate:** hidden and paraphrased canary leakage is blocked in
memory, cache, challenge and public export fixtures.

**Kill rule:** if hidden content can reach reusable memory or public exports,
memory influence and challenge generation stay shadow-only.

#### R7 - Adversarial challenge validity

**Question:** Which generated challenges are valid, non-leaky and predictive of
real failures rather than synthetic noise?

**Why research-first:** Challenge generation exists, but benchmark authority
should admit only reviewed challenges whose failure modes are meaningful and
whose lineage is clean.

**Current implementation surface:** `evals/challenge_factory.py`,
`evals/rotation.py`, `evals/sentinels.py`, `evals/red_team.py` and
`search/failure_cards.py`.

**Research tasks:**

1. Define challenge validity criteria: realistic failure mode, clear expected
   behavior, non-leaky prompt/case, reviewer-admissible, not duplicate and tied
   to risk taxonomy.
2. Measure predictive power against held-out real-world or frozen-web tasks.
3. Define mutation limits and when mutation preserves the same failure mode.
4. Define challenge retirement and rotation economics.
5. Define public/private/hidden admission thresholds.

**Benchmark proxy:** challenge lineage pack with generated, mutated, reviewed,
rejected, duplicate and expired examples.

**Deliverables:** challenge validity rubric, mutation-preservation test,
predictive-validity report and rotation/retirement policy.

**Graduation gate:** reviewed challenge packs improve detection of known
failure modes without increasing leakage or duplicate-counting.

**Kill rule:** generated challenges cannot enter hidden evals if predictive
validity or review-before-hidden cannot be demonstrated.

#### R8 - Decision reissue and drift semantics

**Question:** When does a changed source, model calibration shift, fairness
drift, law/policy-context change or incident make an existing decision stale,
review-required, superseded, reissued or withdrawn?

**Why research-first:** Reissue and continuous governance packages can
represent status changes, but deciding thresholds is domain-specific and
high-stakes.

**Current implementation surface:** `continuous_governance/**`,
`research_dag/invalidation.py`, `claims/lifecycle.py`, `governance/report.py`
and [continuous-governance.md](../../reference/scientist/continuous-governance.md).

**Research tasks:**

1. Define validity status semantics: valid, monitoring, stale,
   review_required, reissued and withdrawn.
2. Define source invalidation propagation by claim family.
3. Define drift thresholds for calibration, fairness, legal context, policy
   context and incident severity.
4. Define old/new ledger linkage and public explanation language.
5. Define false-alarm budget for review queues.

**Benchmark proxy:** reissue simulation pack with changed sources, withdrawn
sources, drift events, new counterevidence, incidents and expected validity
outcomes.

**Deliverables:** decision-validity semantics, drift threshold matrix,
reissue/withdrawal explanation rubric and false-alarm budget model.

**Graduation gate:** reissue recommendations match expected outcomes and do
not overload review queues beyond the stated budget.

**Kill rule:** if stale/withdrawn status cannot be justified by audit lineage,
continuous governance remains advisory only.

#### R9 - Multi-agent research compression and fan-out quality

**Question:** When does subagent fan-out improve evidence coverage and synthesis
quality rather than amplify noise, duplicated work or citation errors?

**Why research-first:** Agent capabilities are gated. Multi-agent research is a
cost, context and evidence-compression problem, not a default architecture
choice.

**Current implementation surface:** `agent/**`, `agent/promotion.py`,
`agent/supervisor_eval.py`, `research_dag/projections.py` and
[agent-capability-promotion.md](../../reference/scientist/agent-capability-promotion.md).

**Research tasks:**

1. Define evidence coverage metrics: unique relevant sources, contradiction
   discovery, snippet faithfulness and claim support improvement.
2. Define compression loss when subagents summarize source reads.
3. Compare single-agent, routed-worker and supervisor-worker patterns on
   frozen tasks without live web.
4. Define cost envelopes and stop conditions for same-model fan-out.
5. Define how subagent outputs appear in Research DAG without raw transcript
   exposure.

**Benchmark proxy:** multi-hop policy research pack with known relevant
sources, distractors, contradictions and hidden synthesis traps.

**Deliverables:** fan-out evaluation protocol, compression-loss metric,
cost/coverage frontier and supervisor-worker default-eligibility checklist.

**Graduation gate:** fan-out shows meaningful lift in evidence coverage or
contradiction discovery without higher citation false-pass or unacceptable cost.

**Kill rule:** if fan-out lift is explained only by extra cost or duplicated
search, the capability remains non-default.

#### R10 - Decision-grade explanation and trust calibration

**Question:** Which public, reviewer, expert and machine exports help users
understand the decision boundary without overtrusting the system?

**Why research-first:** The compiler can produce audience-specific exports, but
presentation choices affect trust, reviewer behavior and misinterpretation.

**Current implementation surface:** `publisher.py`,
`orchestrator/decision_card.py`, `claims/export.py`,
[decision-grade-compiler.md](../../reference/scientist/decision-grade-compiler.md)
and `docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md`.

**Research tasks:**

1. Define trust calibration metrics: correct acceptance, correct skepticism,
   uncertainty comprehension, blocked-claim visibility and counterevidence
   recall.
2. Define omission semantics for hidden/private/internal material.
3. Compare public summary, reviewer packet and expert appendix layouts using
   static fixtures.
4. Define UI/API machine export requirements for future Trust View.
5. Define explanation-insufficient criteria for human review.

**Benchmark proxy:** explanation comprehension pack with public/reviewer/expert
export variants, known blockers, uncertainty and hidden omissions.

**Deliverables:** trust-calibration metric spec, export comprehension benchmark,
omission-reason taxonomy and Trust View research requirements.

**Graduation gate:** target users identify blockers, uncertainty and evidence
limits better than baseline without increased overtrust.

**Kill rule:** if explanation variants increase overtrust or hide blockers,
compiler-backed UI promotion is blocked.

### 8.4. Dependency map

| Track | Depends on | Feeds |
| --- | --- | --- |
| R0 | Wave 2 closeout | all Wave R tracks |
| R1 | Claim Ledger, evidence support links | R2, R3, R4, R8, R10 |
| R2 | R1 support taxonomy, snippet ledger | R3, R6, R9, R10 |
| R3 | R1, R2 | R8 continuous governance |
| R4 | R1, benchmark authority, human review | scheduler default eligibility |
| R5 | human-review packets, R1 support taxonomy | high-risk publication gates, R10 |
| R6 | benchmark authority, memory guards | R7 challenge admission, all eval tracks |
| R7 | R6 leakage rules, failure cards | benchmark authority, near-frontier promotion |
| R8 | R1, R3, continuous governance | reissue/withdrawal workflows |
| R9 | R2, R4, Research DAG | agent promotion, deep research subgraph |
| R10 | R1, R5, compiler exports | frontend Trust View and publication posture |

Minimum viable research sequence:

1. R0, R1 and R2 first.
2. R3, R4 and R6 in parallel.
3. R5, R7, R8 and R9 after the first benchmark proxies exist.
4. R10 when claim/export semantics are stable enough to test with users.

### 8.5. Promotion handoff format

Every completed track must produce:

```text
track_id:
status: accepted | narrow_accepted | refuted | deferred
claim_family_or_capability:
research_result_ref:
benchmark_proxy_ref:
counterexample_refs:
integration_targets:
required_code_changes:
required_docs:
required_tests:
readiness_cap_before_implementation:
promotion_gate:
rollback_or_kill_rule:
contamination_posture:
```

Interpretation:

- `accepted` means the result can unlock an implementation phase.
- `narrow_accepted` means the result unlocks only a scoped slice with explicit
  blockers outside that slice.
- `refuted` means the counterexample becomes a permanent guardrail.
- `deferred` means the problem remains recorded but receives no implementation
  budget.

### 8.6. Anti-swamp rules

1. A track without a benchmark proxy after two research cycles is downgraded to
   recorded open problem.
2. A track cannot request implementation work until its promotion handoff names
   exact files, docs and tests.
3. A track that exposes hidden eval content to reusable memory is paused until
   contamination is resolved.
4. A result that is valid only for a narrow class must be surfaced as
   `narrow_accepted`, not marketed as a broad solution.
5. Counterexamples are first-class deliverables and should be added to gates.
6. Live LLM experiments are optional evidence, not CI requirements.
7. Research cannot lower mandatory governance, benchmark or human-review gates.

### 8.7. Success criteria for Wave R

Wave R is successful when:

- every active track has a benchmark proxy or is intentionally deferred;
- at least three tracks produce accepted or narrow-accepted handoffs;
- claim support and citation faithfulness have calibrated evaluation packs;
- VOI and human-review thresholds show non-worse safety on offline fixtures;
- contamination and leakage tests cover memory, challenge packs and public
  exports;
- reissue semantics can classify stale/review/reissue/withdrawal examples;
- multi-agent fan-out has a cost/coverage frontier rather than anecdotes;
- explanation exports are evaluated for trust calibration, not only aesthetics.

Wave R does not need to turn every primitive production-default. Its purpose is
to decide honestly which primitives are scientifically ready, which are only
engineering-ready, and which should remain blocked.

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
