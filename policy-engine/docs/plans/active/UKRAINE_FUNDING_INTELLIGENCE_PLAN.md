# Ukraine Funding Intelligence Plan

> Детерминированный план построения funding-intelligence слоя для PolicyOS с
> фокусом только на Украину.
> Created: 2026-04-15

---

## Scope and Assumptions

Этот план описывает, как собрать в PolicyOS слой
`funding intelligence` для украинских политик так, чтобы каждая policy option
сразу сопровождалась реалистичными путями финансирования.

Базовые предпосылки:

- география первого контура: только Украина;
- обработка: только детерминированный код, без LLM, OCR-эвристик и
  "black-box" matching;

- приоритет: не "все источники мира", а максимальная полнота именно тех
  источников, которые реально описывают финансирование украинских политик;

- первый target: `datasets + fabric + ukraine_data`, а не новый большой
  top-level subsystem;

- funding слой должен отвечать на вопрос "как это профинансировать", а не
  смешивать его с вопросом "кто влияет на политику".

Не-цели первого этапа:

- campaign finance, lobbying и foreign influence как primary use case;
- LLM-based extraction из PDF/сканов;
- построение полноценных ownership chains "до физлица" для всего графа;
- попытка сразу покрыть все private/philanthropic грантовые базы.

---

## Core Diagnosis

Для Украины максимальную практическую ценность дают не абстрактные donor-базы,
а связка:

`бюджет/бюджетная программа -> казначейское исполнение -> закупка -> проект восстановления -> внешнее софинансирование`

Именно эта связка даёт decision-grade answer:

- есть ли уже бюджетный канал;
- есть ли исторический прецедент финансирования;
- дошли ли деньги до исполнения;
- есть ли procurement/project evidence;
- есть ли внешний donor/IFI channel для co-financing;
- насколько этот путь реалистичен по срокам, ограничениям и юридическим
  участникам.

Поэтому главный объект системы должен быть не `donor`, а
`financing path`.

---

## Architectural Principle

Нужно разделить два графа:

### 1. Financing graph

Описывает реальные каналы финансирования политики:

- госбюджет;
- местные бюджеты;
- целевые бюджетные программы;
- международная техническая помощь;
- гранты;
- кредиты и гарантии IFI;
- recovery/reconstruction programs;
- co-financing patterns.

### 2. Risk / integrity graph

Описывает контрагента и риски:

- юридическая идентичность;
- санкции;
- ownership / corporate links;
- PEP / compliance signals;
- риск концентрации поставщиков или доноров.

Эти графы должны быть связаны, но не смешаны. Иначе runtime начнёт путать
`возможный источник финансирования` и `источник влияния/риска`.

---

## What The System Must Produce

Для каждой policy option система должна уметь собирать `financing bundle`:

- `domestic_channels`: существующие бюджетные и programmatic каналы в Украине;
- `execution_precedents`: подтверждения, что похожие расходы реально
  исполнялись;

- `procurement_precedents`: подтверждения через закупки и контракты;
- `recovery_channels`: применимые каналы DREAM / reconstruction pipeline;
- `external_channels`: доноры, IFI и international technical assistance;
- `eligibility_constraints`: география, сектор, тип бенефициара,
  стадия проекта, co-financing rules;

- `evidence_chain`: provenance до конкретного источника и записи;
- `confidence_breakdown`: объяснимый confidence без ML/LLM;
- `risk_flags`: санкции, слабая entity linkage, high concentration,
  stale source, conflicting amounts.

---

## Coverage Model

Полнота должна измеряться не по числу источников, а по покрытию жизненного
цикла финансирования.

| Coverage layer            | Ключевой вопрос                                         | Основные источники                                      |
| ------------------------- | ------------------------------------------------------- | ------------------------------------------------------- |
| Fiscal space              | Есть ли бюджетный канал и лимит?                        | Open Budget, бюджетные документы Минфина, data.gov.ua   |
| Budget execution          | Были ли реальные платежи / кассовое исполнение?         | Spending / E-data                                       |
| Procurement execution     | Есть ли контракты и закупочные прецеденты?              | Prozorro, Spending contracts proxy                      |
| Recovery pipeline         | Есть ли готовые или подготавливаемые recovery projects? | DREAM                                                   |
| External public financing | Есть ли committed / disbursed donor flows для Украины?  | IATI, Минэкономики МТД, Минфин / Ukraine Donor Platform |
| IFI project finance       | Есть ли проектные линии WB/EIB/EBRD/CEB/IFC?            | MoF IFI registers, official IFI project data            |
| Macro financing context   | Каков общий фискальный контекст и внешний ресурс?       | Минфин, НБУ, donor platform bulletins                   |
| Integrity / counterparty  | Кто именно получает / проводит / исполняет деньги?      | ЕДР, OpenCorporates, GLEIF, OpenSanctions               |

Если хотя бы один из этих слоёв отсутствует, итоговый financing bundle будет
неполным независимо от числа donor APIs.

---

## Existing Processed Data We Already Have

Перед новым сбором важно зафиксировать, что часть полезного украинского слоя
уже существует в репозитории в обработанном виде.

### A. `data/ukraine_server_support_20260410`

Это самый полезный уже подготовленный input для `domestic funding MVP`.

Содержимое:

- `normalized_corpus`: полный нормализованный украинский корпус без raw-layer;
- `runtime_calibration_internals`: selected runtime/calibration internals, нужные
  для bridge/QC/runtime reuse.

Наиболее ценные funding-related артефакты:

| Repo path                                                                                                                                      | Что это                                 | Практическая ценность для funding layer                                     | Статус             |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | --------------------------------------------------------------------------- | ------------------ |
| `data/ukraine_server_support_20260410/normalized_corpus/normalized/spending_full/budget_flows_monthly_sparse.parquet`                          | Нормализованные бюджетные потоки        | Основной seed для Spending-layer; закрывает факт движения публичных средств | Reuse now          |
| `data/ukraine_server_support_20260410/normalized_corpus/normalized/spending_contracts_procurement_proxy/procurement_contracts_monthly.parquet` | Procurement proxy из Spending contracts | Полезно как временный procurement evidence до полного Prozorro hydration    | Reuse now          |
| `data/ukraine_server_support_20260410/normalized_corpus/normalized/prozorro_full/procurement_contracts_monthly.parquet`                        | Нормализованный Prozorro слой           | Использовать только как слабый seed; слой явно неполный                     | Reuse with caution |
| `data/ukraine_server_support_20260410/normalized_corpus/normalized/edr_current/agent_registry_full.parquet`                                    | ЕДР registry dump                       | Главный deterministic entity-resolution backbone                            | Reuse now          |
| `data/ukraine_server_support_20260410/normalized_corpus/normalized/budget_managers/public_budget_manager_registry.parquet`                     | Реестр бюджетных менеджеров             | Полезен для связывания flows с program managers                             | Reuse now          |
| `data/ukraine_server_support_20260410/normalized_corpus/normalized/macro_nbu_derzhstat/macro_panel_monthly.parquet`                            | Макропанель                             | Вторичный контекст для fiscal backdrop, не primary funding truth            | Reuse as context   |
| `data/ukraine_server_support_20260410/runtime_calibration_internals/runtime/d0_p0/edr_identity_bridge_manifest.json`                           | Coverage/QC по ID bridge                | Полезно как baseline для качества linkage                                   | Reuse now          |

Что уже видно по этим данным:

- `spending_full` уже очень большой и полезный слой: `54,777,722` строк;
- `spending_contracts_procurement_proxy` уже даёт `1,358,759` строк;
- `edr_current` даёт `8,868,524` entity rows;
- `budget_managers` пока очень маленький, но полезный reference layer;
- `prozorro_full` в текущем пакете слишком мал, чтобы считать его полным
  procurement truth.

Вывод:

- этот пакет позволяет резко сократить time-to-MVP;
- его надо использовать как `trusted normalized seed import`;
- но он не заменяет новый raw/provenance-complete funding ingestion.

### B. `production_data/ukraine_agent_simulation_baseline_20260410`

Это не funding corpus, а компактный production handoff для agent-simulation /
runtime слоя.

Что в нём полезно:

- `production_bundle/bundles/runtime_bundle_v1`
  показывает, какой компактный runtime bundle реально нужен downstream;

- `heavy_graph_addon/*.npz`
  показывает размер тяжёлых sparse-graph артефактов;

- `production_bundle/manifests/build_run_d0_p0.json`
  фиксирует реальные coverage limits текущего D0 blueprint.

Ключевой caveat:

- этот baseline не является final funding truth;
- в D0 manifest зафиксированы ошибки по coverage:
  spending coverage около `0.880`, procurement coverage около `0.890`;

- procurement source в baseline идёт через
  `spending_contracts_procurement_proxy`, а не через полноценный
  hydrated `prozorro_full`.

Поэтому этот baseline нужно использовать:

- как ориентир по target bundle shape;
- как ориентир по размеру runtime/release bundle;
- как источник уже готовых runtime manifests;
- но не как источник истины для funding extraction.

### C. `production_data/datasets_full_phase3full_20260327_183054/`

В `production_data/datasets_full_phase3full_20260327_183054/` уже есть
большой `datasets` catalog layer:

- `dataset_catalog.duckdb`;
- `all_records.jsonl`;
- embeddings/index artifacts;
- publish/QC manifests.

Полезность для funding плана:

- это сильный `source discovery` и `dataset inventory` слой;
- там уже каталогизированы десятки тысяч украинских CKAN datasets;
- в частности, по `data_gov_ua` уже есть большой inventory footprint.

Но важно:

- текущий datasets publish не consumer-ready;
- `consumer_readiness` и `manifest` фиксируют, что этот слой полезен как
  catalog/discovery surface, а не как готовый production funding runtime.

Вывод:

- `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`
  использовать как discovery index;
- не использовать как финальный funding bundle без нового украинского
  domain-specific publish layer.

---

## Reuse Strategy for Existing Assets

### Reuse as-is

- `spending_full`
- `spending_contracts_procurement_proxy`
- `edr_current`
- `budget_managers`
- `edr_identity_bridge_manifest`
- `public_entity_registry` и related runtime reference outputs

### Reuse after remapping / re-wrapping

- `macro_nbu_derzhstat`
- compact `runtime_bundle_v1` and `release_manifest_v1` from
  `ukraine_agent_simulation_baseline_20260410`

- `dataset_catalog.duckdb` and `all_records.jsonl` from
  `production_data/datasets_full_phase3full_20260327_183054`

### Do not treat as final truth

- `prozorro_full` from the support package in its current shape;
- heavy graph addons as source evidence;
- calibration artifacts as financing evidence;
- generic `datasets` publish artifacts without funding-specific reconciliation.

---

## Gaps That Still Require New Collection and Processing

Даже с уже имеющимися артефактами остаются критические пробелы:

| Missing layer                           | Почему нельзя закрыть текущими артефактами                                      | Что нужно сделать                          |
| --------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------ |
| Open Budget                             | В текущем локальном пакете нет явного budget-program / local-budget truth layer | Новый harvest + normalization              |
| DREAM                                   | Нет reconstruction project layer                                                | Новый connector / deterministic API ingest |
| Минэкономики МТД                        | Нет official ITA registry layer в текущем processed corpus                      | Новый harvest + structured extraction      |
| Минфин donor platform / IFI registers   | Нет полного official external-financing coordination layer                      | Новый harvest + registry normalization     |
| IATI                                    | Нет donor transaction graph for Ukraine                                         | Новый external donor ingest                |
| WB / EIB / EBRD project layer           | Нет полноценного IFI project/instrument surface                                 | Новый harvest + entity/topic mapping       |
| Full Prozorro hydration                 | Текущий local `prozorro_full` недостаточен                                      | Новый procurement ingest / hydration       |
| Open Budget <-> Spending reconciliation | Пока нет funding-specific reconciliation contract                               | Новый deterministic merge/QC stage         |
| Policy-theme crosswalk                  | Нет funding-specific crosswalk to canonical policy ontology                     | Новый rules-based mapping layer            |

---

## Source Portfolio for Ukraine

### Tier A0: обязательное украинское ядро

Это must-have источники. Без них система не сможет давать полезные ответы по
украинским политикам.

| Source                                             | Почему критичен для Украины                                             | Что покрывает                                                        | Формат / доступ                                     | Приоритет |
| -------------------------------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------- | --------- |
| Open Budget                                        | Даёт структуру гос- и местных бюджетов, планы и исполнение              | Budget programs, local/state allocations, execution aggregates       | web portal + structured responses / exports         | P0        |
| Spending / E-data                                  | Даёт факт использования публичных средств                               | Treasury-like spending evidence, contracts, payments, counterparties | official portal / machine-readable portal artifacts | P0        |
| Prozorro / OpenProcurement API                     | Даёт procurement proof и контрагенты                                    | Tenders, awards, contracts, buyers, suppliers, amounts               | official API docs + feed endpoints                  | P0        |
| DREAM                                              | Даёт reconstruction/recovery pipeline, особенно для капитальных политик | Projects, financing programs, stages, recovery status                | public portal + open API/docs                       | P0        |
| data.gov.ua                                        | Даёт каталог открытых наборов и fallback-реестры                        | budget docs, registries, sector datasets, local open data links      | CKAN API                                            | P0        |
| Минэкономики: International Technical Assistance   | Даёт официальный контур МТД и активных проектов                         | donors, recipients, project titles, sectors, periods                 | official ministry pages / docs / tables             | P0        |
| Минфин: Ukraine Donor Platform + IFI/ITA registers | Даёт официальный coordination layer и регистры IFI projects             | IFI pipeline, external financing context, donor coordination         | official ministry pages / registers / bulletins     | P0        |

### Current availability note

На старте у нас уже есть частично готовый processed domestic layer:

- `Spending` и procurement proxy уже присутствуют в нормализованном виде;
- `EDR` и `budget_managers` уже присутствуют как reference layer;
- `data.gov.ua` уже сильно покрыт discovery-каталогом в `production_data`.

Но пока отсутствуют или неполны:

- полноценный `Open Budget` слой;
- `DREAM`;
- official ITA / donor platform layers;
- полноценный hydrated `Prozorro`;
- внешний donor/IFI graph.

### Tier A1: международный public-finance слой, реально полезный для Украины

Эти источники не заменяют украинское ядро, а закрывают внешний financing layer.

| Source                                                     | Роль в украинском контуре                                        | Что брать                                                              | Формат / доступ                       | Приоритет |
| ---------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------- | --------- |
| IATI                                                       | Главный открытый междонорский слой по aid flows                  | activities, transactions, organizations, sectors, recipient-country=UA | official API / datastore / XML        | P1        |
| World Bank projects / operations                           | Важен для programmatic/project financing Украины                 | project pipeline, commitments, sectors, implementing agencies          | official project/operations data      | P1        |
| OECD finance / CRS-compatible flows                        | Нужен для исторических donor patterns, но не как real-time truth | long-run donor-sector-country flows                                    | SDMX / statistical access             | P2        |
| EIB open data                                              | Важен для EU-linked project finance                              | projects, regions, sectors, instruments                                | official open data                    | P1        |
| EBRD official project data                                 | Важен для infrastructure, municipal, private-sector support      | project metadata, country sector pipeline                              | official project pages / data exports | P2        |
| CEB / IFC / IMF official public project or financing pages | Полезны как supplementary registry layer                         | program / facility / operation metadata                                | official pages / tables / docs        | P3        |

### Tier B: entity and integrity enrichments

Это не первичный funding truth, а слой для deterministic entity resolution и
compliance.

| Source                              | Назначение                                            | Что использовать                                    | Приоритет |
| ----------------------------------- | ----------------------------------------------------- | --------------------------------------------------- | --------- |
| ЕДР / украинские registry dumps     | Украинский ground truth по юрлицам                    | EDRPOU, names, status, region, sector               | P1        |
| OpenCorporates API                  | Foreign legal entities и cross-border company linkage | jurisdiction, company number, names, provenance     | P2        |
| GLEIF / LEI data                    | Международный юридический идентификатор               | LEI, legal name, jurisdiction, parent relationships | P2        |
| OpenSanctions (`default`, не `all`) | Sanctions / PEP / risk flags                          | sanctions targets, identifiers, aliases             | P2        |

---

## Recommended Inclusion / Exclusion Logic

### Что включать сразу

- любые официальные украинские источники, которые описывают бюджет,
  исполнение, закупки, recovery projects или МТД/IFI;

- международные открытые источники, где Украина явно присутствует как
  страна-бенефициар, страна реализации или страна recipient;

- источники с устойчивым machine-readable surface:
  API, CKAN, CSV/XLSX, XML, SDMX, documented JSON feeds.

### Что включать позже

- ministry PDFs, если у них стабильная табличная структура и extractor можно
  жёстко тестировать;

- IFI pages без полноценного API, если HTML стабилен и не критичен для
  publish-blocking path;

- sector-specific vertical funds, если они реально часто участвуют в украинских
  policy bundles.

### Что не включать в первую волну

- FEC, OpenSecrets, FollowTheMoney и иные US political-finance источники:
  они не отвечают на вопрос финансирования украинских политик;

- коммерческие closed databases как core dependency;
- любые источники, требующие LLM extraction;
- free-form PDF parsing без строгого шаблона;
- sources with opaque provenance.

---

## Why These Sources Maximize Ukraine Coverage

### 1. Они покрывают весь путь денег, а не только donor commitment

IATI и donor registries показывают commitment/disbursement, но не показывают:

- бюджетную привязку в Украине;
- факт казначейского исполнения;
- факт закупки;
- связь с локальными бенефициарами и закупочными агентами.

Open Budget + Spending + Prozorro + DREAM закрывают этот пробел.

### 2. Они дают украинские идентификаторы

Для deterministic linkage нам нужны:

- `EDRPOU`;
- budget program / budget classification codes;
- `UA-...` tender IDs;
- project IDs / registry IDs;
- периоды исполнения;
- геокоды украинских территорий.

Многие международные donor datasets этого не дают, поэтому должны выступать
внешним слоем обогащения, а не корневым truth layer.

### 3. Они позволяют ответить не только "кто финансирует", но и "через что"

Украинская policy relevance определяется каналом:

- госпрограмма;
- субвенция;
- местный бюджет;
- МТД;
- recovery project;
- IFI loan / guarantee;
- external budget support.

Именно этот канал должен стать основной единицей аналитики.

---

## Deterministic Data Model

Нужна не donor-centric, а channel-centric модель.

Базовые сущности:

- `FundingSource`
  donor / бюджет / IFI / facility / local budget / ministry program;

- `FundingInstrument`
  grant / budget appropriation / loan / guarantee / technical assistance /
  subvention / procurement-financed spending;

- `FundingCommitment`
  обещанное или утверждённое финансирование;

- `FundingDisbursement`
  фактическая выдача / disbursement / transfer;

- `BudgetAllocation`
  бюджетное назначение / программа / local allocation;

- `BudgetExecution`
  факт исполнения;

- `ProcurementArtifact`
  tender / award / contract / supplier evidence;

- `RecoveryProject`
  DREAM или другой проектный объект;

- `RecipientEntity`
  орган, громада, коммунальное учреждение, предприятие, НГО, private recipient;

- `ImplementingAgency`
  фактический исполнитель;

- `PolicyTheme`
  ссылка на существующую canonical ontology PolicyOS;

- `RiskFlag`
  sanctions / unresolved entity / stale source / inconsistent amounts.

Ключевой итоговый объект:

- `FinancingPath`
  упорядоченная цепочка вида
  `source -> instrument -> Ukrainian channel -> project/program -> execution evidence`

---

## Deterministic Matching Strategy

### Matching rules must be identifier-first

Приоритет идентификаторов:

1. `EDRPOU`
2. `UA-...` procurement IDs
3. DREAM project / program IDs
4. budget classification / program codes
5. IATI activity / organisation IDs
6. World Bank / EIB / EBRD project IDs
7. LEI
8. jurisdiction + company number

### Name matching must remain rule-based

Разрешённые deterministic passes:

- Unicode normalization;
- нормализация регистра и пунктуации;
- вычищение организационно-правовых суффиксов;
- фиксированные таблицы транслитерации `uk <-> en`;
- фиксированные dictionaries donor aliases:
  `EU`, `European Union`, `ЄС`, `European Commission`, `EC`, etc.;

- exact / prefix / token-set matching по правилам;
- explainable weighted score с фиксированными коэффициентами.

Запрещено:

- LLM arbitration;
- embedding-based semantic matching;
- auto-merge при слабом evidence.

### Ambiguity policy

Если deterministic rules не дают уверенного соответствия, запись остаётся:

- `unresolved`;
- `candidate_matches`;
- `manual_override_allowed`.

Лучше иметь меньше связей, но с высокой explainability, чем "красивый" граф с
непроверяемыми слияниями.

---

## Topic Mapping Without LLM

Финансирование должно привязываться не к свободному тексту, а к
существующей policy ontology.

Подход:

- использовать существующий canonical registry PolicyOS как target namespace;
- завести rules-based crosswalk:
  budget code / procurement CPV / donor sector / DREAM category ->
  canonical `policy_theme`;

- держать bilingual mapping tables:
  `uk`, `en`, сокращения, ведомственные названия;

- разрешать one-to-many mapping только если source явно содержит breakdown;
- каждый mapping снабжать `mapping_rule_id` и `mapping_confidence`.

Это позволит позднее включить funding evidence в `scientist` как новую
dimension без LLM-посредника.

---

## Source-Specific Implementation Notes

### Open Budget

Использовать как основной слой для:

- госбюджета;
- местных бюджетов;
- program structure;
- агрегированного исполнения.

Не использовать как единственный execution truth для контрагентов и контрактов;
для этого нужен Spending / Prozorro.

### Spending / E-data

Использовать как основной слой фактического использования публичных средств.

Уже имеющийся `spending_full` нужно рассматривать как первый import-ready seed,
а не пересобирать с нуля в первой итерации.

Нужно собирать:

- отправителя / получателя;
- сумму;
- дату / период;
- документ / договор / назначение платежа;
- EDRPOU, где доступен;
- мосты к Prozorro, если контракт содержит procurement identifiers.

### Prozorro

Использовать как основной procurement-evidence layer.

Текущий локальный `prozorro_full` нельзя считать production-complete; до
полноценного deterministic hydration нужно опираться на
`spending_contracts_procurement_proxy` как временный bridge layer.

Нужно брать:

- tenders;
- awards;
- contracts;
- buyers;
- suppliers;
- CPV / classification;
- milestone dates;
- budget/project references, если присутствуют.

### DREAM

Использовать как основной reconstruction/recovery layer.

Особенно важно для политик, связанных с:

- инфраструктурой;
- образованием;
- здравоохранением;
- энергетикой;
- housing / community recovery;
- municipal capital investment.

### data.gov.ua

Использовать как:

- discovery layer для украинских открытых data packages;
- fallback registry layer;
- источник budget/program/sector datasets;
- канал для периодической проверки, появились ли новые релевантные наборы.

Это уже органично ложится на текущий `ckan` stack в `datasets`.

Практически:

- `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`
  уже можно использовать как первичный discovery index;

- funding lane должен выбирать из него релевантные budget/procurement/finance
  datasets и только потом промотировать их в funding-specific publish path.

### Минэкономики: МТД

Использовать как официальный реестр/список международной технической помощи,
а не как raw truth по disbursement.

Главная ценность:

- donor-recipient-project linkage;
- сектор;
- сроки;
- официальный статус проекта.

### Минфин / Ukraine Donor Platform / IFI registers

Использовать как coordination + registry layer:

- register of joint IFI projects;
- monitoring pages;
- donor platform summaries;
- bulletins по внешнему бюджетному финансированию.

Это особенно важно для budget support и IFI financing, где IATI не всегда даёт
достаточно полный operational picture.

### IATI

Использовать как главный внешний donor graph для Украины.

Но важно:

- IATI не должен считаться единственным source of truth;
- это слой donor commitments / transactions / org metadata;
- украинская execution verification должна идти через украинские источники.

### OECD

Использовать ограниченно:

- для исторических donor-sector-country patterns;
- для baseline concentration analysis;
- для long-run cross-country comparison.

Не использовать как основной оперативный слой по финансированию Украины.

### World Bank / EIB / EBRD / other IFIs

Использовать как project/instrument registries по operations в Украине.

Ключевая логика:

- WB WDI и обычные макроиндикаторы полезны, но это не funding source;
- нужен project-level / operation-level layer;
- IFI pages можно держать publish-non-blocking, пока не появится стабильный
  API или tabular export.

---

## Recommended Repo Strategy

### Do not start with a brand-new top-level subsystem

Сейчас лучший путь:

- использовать `datasets.batch.source_registry` как discovery / harvest surface;
- переиспользовать `fabric.connectors` (`ckan`, `rest_json`, `sdmx`,
  `file_tabular`);

- переиспользовать существующий `fabric.entity_resolution` и manual override
  store;

- переиспользовать и расширять `ukraine_data`, где уже есть Spending/Prozorro
  нормализация и runtime budget/procurement graph assets.

### Why

Потому что в текущем состоянии репозитория:

- `data.gov.ua` уже естественно укладывается в `datasets + ckan`;
- `oecd_sdmx` и `worldbank_wdi` уже существуют, но funding-layer требует
  уточнённых source specs;

- `ukraine_data` уже понимает `spending_full` и `prozorro_full`;
- уже существует локальный `normalized_corpus` с полезным domestic funding seed;
- уже существует compact `ukraine_agent_simulation_baseline` как ориентир по
  runtime/release bundle shape;

- отдельный новый subsystem слишком рано потянет изменения в snapshot,
  docs/site nav, import policy и runtime surface.

### Practical rule

Первый этап делать как `funding lane` поверх текущих слоёв.

Отдельный пакет `polisyos.funding` имеет смысл только если появятся:

- собственный CLI lifecycle;
- отдельный publish bundle;
- отдельные runtime API endpoints;
- самостоятельные governance contracts.

---

## Proposed Pipeline Shape

Рекомендуемые стадии:

1. `source_discovery`
2. `harvest_domestic`
3. `harvest_external`
4. `normalize`
5. `identifier_bridge`
6. `rule_based_entity_resolution`
7. `topic_crosswalk`
8. `flow_build`
9. `execution_reconciliation`
10. `risk_enrichment`
11. `qc`
12. `publish`

### Stage semantics

- `source_discovery`
  обнаруживает новые CKAN packages, registry pages и relevant feeds;

- `harvest_domestic`
  забирает Open Budget / Spending / Prozorro / DREAM / Ukrainian registries;

- `harvest_external`
  забирает IATI / IFI / OECD / international layers;

- `normalize`
  переводит всё в единые canonical records;

- `identifier_bridge`
  строит exact ID bridges;

- `rule_based_entity_resolution`
  обрабатывает случаи без exact ID, но только explainable rules;

- `topic_crosswalk`
  связывает funding records с canonical policy themes;

- `flow_build`
  строит `FinancingPath` и derived edges;

- `execution_reconciliation`
  проверяет, что budget / donor / procurement layers не противоречат друг другу;

- `risk_enrichment`
  накладывает sanctions / company / LEI enrichments;

- `qc`
  валидирует coverage, freshness, reconciliation, unresolved rate;

- `publish`
  публикует bundle для runtime и аналитики.

---

## Prioritized Delivery Plan

### Phase 0. Ontology and identifiers

Сначала нужно зафиксировать:

- канонический список funding entity types;
- список идентификаторов и их приоритет;
- украинские геокоды и territorial crosswalk;
- rules для bilingual normalization;
- source provenance contract.

Без этого следующий этап даст много несогласованных записей.

### Phase 1. Domestic funding truth

Первая production wave:

- import already processed domestic seeds from
  `data/ukraine_server_support_20260410`;

- Open Budget;
- Spending;
- Prozorro;
- DREAM;
- `data.gov.ua` как catalog/fallback;
- link к существующим `ukraine_data` активам.

Цель фазы:

- доказать связку `budget -> execution -> procurement -> project`.
- при этом не тратить первую итерацию на повторную переработку того, что уже
  нормализовано и лежит локально.

### Phase 2. External donor truth for Ukraine

Вторая wave:

- IATI;
- Минэкономики МТД;
- Минфин donor platform / IFI registers;
- World Bank / EIB project layers.

Цель фазы:

- собирать `external_channels` и `co-financing` без потери украинского
  execution context.

### Phase 3. Historical and comparative layer

Третья wave:

- OECD finance / CRS-compatible flows;
- EBRD / CEB / IFC supplement;
- MoF/NBU macro financing context.

Цель фазы:

- дать системе historical precedent и concentration view, но не ломать
  оперативную полезность.

### Phase 4. Integrity and counterparty layer

Четвёртая wave:

- EDR bridge hardening;
- OpenCorporates;
- GLEIF;
- OpenSanctions;
- deterministic risk flags.

Цель фазы:

- сделать financing bundle пригодным для governance/compliance review.

### Phase 5. Runtime integration

Пятая wave:

- добавить `funding feasibility` в decision surfaces;
- включить financing evidence в cross-graph reasoning;
- добавить search / inspect / explain endpoints;
- вынести only-if-needed в отдельный `funding` subsystem.

---

## Quality Gates

Funding layer должен проходить отдельные QC-gates:

- `coverage.domestic_budget`
  доля policy themes, для которых найден хотя бы один domestic channel;

- `coverage.execution`
  доля записей, подтверждённых Spending или Open Budget execution;

- `coverage.procurement`
  доля channels, имеющих procurement evidence, где это ожидаемо;

- `coverage.external`
  доля external channels с donor/instrument/amount/time metadata;

- `resolution.identifier_exact_rate`
  доля entity links, закрытых exact IDs;

- `resolution.unresolved_rate`
  доля unresolved entities после rules-based pass;

- `reconciliation.amount_conflict_rate`
  конфликтные суммы между источниками;

- `freshness.days_since_last_source_sync`
  свежесть по каждому publish-blocking source;

- `provenance.missing_rate`
  записи без source URL / source ID / ingest timestamp;

- `policy_binding.unmapped_theme_rate`
  доля funding records без canonical policy theme.

Publish-blocking должны быть только те источники, без которых bundle теряет
украинскую практическую полезность.

На старте это:

- Open Budget;
- Spending;
- Prozorro;
- DREAM;
- IATI или официальный украинский external-financing substitute.

---

## Hard Rules for "No LLM"

Чтобы ограничение не размылось, его нужно формализовать.

Запрещено:

- извлекать donor / recipient / sector из свободного текста через LLM;
- использовать embeddings для similarity;
- использовать LLM для entity arbitration;
- использовать LLM для topic mapping.

Разрешено:

- regex / XPath / CSS selectors;
- deterministic JSON/XML parsers;
- tabular parsers для CSV/XLSX/ODS;
- fixed transliteration tables;
- fixed dictionaries;
- explainable weighted rules;
- manual override store с audit trail.

Если источник нельзя обработать этими способами, он не должен быть
publish-blocking.

---

## Sources to Prefer Immediately

Если нужен жёсткий short list для старта, он такой:

1. Open Budget
2. Spending / E-data
3. Prozorro / OpenProcurement API
4. DREAM
5. data.gov.ua
6. Минэкономики: International Technical Assistance
7. Минфин: Ukraine Donor Platform + IFI registers
8. IATI
9. World Bank project/operations layer
10. EIB open data

Именно этот набор даёт лучший баланс:

- украинская практическая применимость;
- полнота канала финансирования;
- детерминированность обработки;
- разумная стоимость внедрения в текущую архитектуру.

### Immediate acceleration rule

Чтобы сократить время первой реализации, стартовать нужно так:

1. импортировать и переупаковать уже существующие processed domestic artifacts;
2. добрать отсутствующие domestic layers (`Open Budget`, `DREAM`,
   полноценный `Prozorro`);
3. затем добавлять официальный external donor / IFI layer.

---

## Official Source References

Украинское ядро:

- Open Budget: [openbudget.gov.ua](https://openbudget.gov.ua/local-budget/info/info)
- Spending / E-data: [spending.gov.ua](https://spending.gov.ua/)
- Prozorro API docs: [prozorro-api-docs.readthedocs.io](https://prozorro-api-docs.readthedocs.io/en/latest/)
- DREAM public portal: [dream.gov.ua](https://dream.gov.ua/)
- DREAM API docs: [open-contracting.github.io/dream-api-docs](https://open-contracting.github.io/dream-api-docs/)
- data.gov.ua CKAN API: [data.gov.ua/api/3/action/package_search](https://data.gov.ua/api/3/action/package_search)
- Минэкономики, International Technical Assistance:
  [me.gov.ua](https://me.gov.ua/Documents/MoreDetails?id=b01d5d7e-6804-4a21-82cc-12139e8d3529&lang=en-GB&title=InternationalTechnicalAssistance)

- Минфин, Ukraine Donor Platform:
  [mof.gov.ua](https://www.mof.gov.ua/en/ukraine_donor_platform-897)

Международный слой:

- IATI developer portal: [developer.iatistandard.org/apis](https://developer.iatistandard.org/apis)
- IATI datastore docs:
  [iatistandard.org](https://iatistandard.org/en/iati-tools-and-resources/iati-datastore/how-to-use-the-datastore-api/)

- OECD SDMX REST base: [sdmx.oecd.org/public/rest](https://sdmx.oecd.org/public/rest)
- World Bank API base: [api.worldbank.org/v2](https://api.worldbank.org/v2)
- EIB open data: [eib.org](https://www.eib.org/en/publications-research/eib-open-data)

Entity / integrity:

- OpenCorporates API reference:
  [api.opencorporates.com](https://api.opencorporates.com/documentation/API-Reference)

- GLEIF LEI data access:
  [gleif.org](https://www.gleif.org/en/lei-data/access-and-use-lei-data)

- OpenSanctions notice on dataset choice:
  [discuss.opensanctions.org](https://discuss.opensanctions.org/t/notice-do-not-use-the-all-dataset/60)

---

## Bottom Line

Для украинского policy engine SOTA-подход заключается не в том, чтобы
"подключить побольше donor APIs", а в том, чтобы собрать
детерминированный graph, который:

- начинается с украинского бюджетно-исполнительного truth layer;
- подтверждается закупками и recovery-project evidence;
- обогащается внешними donor/IFI flows;
- остаётся explainable, provenance-first и без LLM;
- возвращает не просто список доноров, а реальный `financing path`.

Именно такой слой кратно повышает практическую полезность системы, потому что
переводит policy analysis из "что стоит сделать" в
"через какой канал это реально профинансировать в Украине".
