# Guidelines For Academic Causal Claim Annotation

## Назначение разметки

Вы размечаете не "истинность экономических законов", а качество и статус причинных утверждений в академических работах для построения `policy-oriented causal knowledge graph`.

Контекст задачи такой. Система `PolisyOS` собирает академические статьи по policy-relevant темам, извлекает из них кандидатные причинные утверждения и затем решает, какие из них можно публиковать в граф как достаточно надежные causal edges. На первом этапе модель `Qwen` уже умеет находить кандидатные claims, но пока склонна смешивать три разных вещи:

1. в статье есть язык причинности;
2. статья действительно идентифицирует причинный эффект;
3. это утверждение достаточно надежно, чтобы попасть в production-grade граф.

Именно это смешение и нужно исправить с помощью `gold set`.

Ваша разметка нужна не для того, чтобы "согласиться или не согласиться" с выводами статьи по существу, а чтобы задать строгий эталон того, как система должна интерпретировать научный текст. Главный вопрос: что именно утверждает paper, насколько это утверждение каузально по формулировке, насколько оно поддержано дизайном исследования и должно ли оно попадать в граф как `credible causal edge`.

Система работает в режиме `precision-first`. Это значит, что для нас лучше потерять часть слабых или неоднозначных claims, чем включить в граф много ложноположительных причинных связей. Поэтому при сомнении разметка должна быть консервативной. Если paper показывает `association`, `correlation`, `panel relationship` или `regression coefficient` без убедительного `identification design`, это не должно автоматически трактоваться как сильное причинное утверждение.

## Три уровня оценки

Очень важно разделять три уровня оценки.

1. `paper relevance`:
   статья вообще релевантна для `policy-causal extraction` или нет.
2. `claim presence`:
   paper формулирует claim, который можно выделить как отдельное утверждение.
3. `causal validity`:
   этот claim является действительно `causal assertion` с достаточной доказательной базой, а не просто ассоциацией, механизмом, обзорным выводом или нормативной репликой.

Ошибки модели чаще всего происходят именно на переходе от второго уровня к третьему.

Единица разметки на `claim-level` это не статья целиком, а конкретное утверждение. Одна статья может не дать ни одного годного claim, а может дать несколько claims с разным статусом. Например, paper может содержать один основной causal claim, один механизм и один слабый observational side-result. Это должны быть разные annotation outcomes, а не одна общая оценка статьи.

## Правило источника

При разметке нельзя полагаться на внешние знания о paper, авторе, журнале или теме. Нужно судить только по тому тексту, который дан в пакете кандидата:

- `title`
- `paper_abstract`
- `claim_text`
- `supporting_spans`
- `supporting_text`
- при наличии `method_spans`
- `source_basis`
- `design_family_hint`

Если в пакете недостаточно evidence, это не повод "догадываться", что paper, вероятно, сильный. В этом случае нужно понижать уверенность, `causal_credibility` или ставить `insufficient_evidence` / `unclear`.

## Causal language vs causal evidence

Особенно критично различать:

- `paper uses causal language`
- `paper has causally credible evidence`
- `claim should be published to the graph`

Это три разные вещи.

В экономике и `policy-literature` это не одно и то же. Формулировки вроде `affects`, `impacts`, `drives`, `improves`, `reduces` часто встречаются и в observational papers. Сильный causal статус обычно требует явного `design signal`: `RCT`, `IV`, `DiD`, `RDD`, `synthetic control` или очень сильного `meta-analysis`. `Panel FE`, `OLS`, `cross-sectional regressions` и `ML prediction` сами по себе не должны маркироваться как `strong causal evidence`.

## Source Basis

Поле `source_basis` критично и интерпретируется так:

- `fulltext`:
  claim заземлен в полном тексте статьи. Это предпочтительный режим для production-grade gold set.
- `abstract_only`:
  claim заземлен только в abstract. Такие claims полезны для exploratory recall и early annotation rounds, но почти никогда не должны попадать в production causal graph как `strong publishable edges`.

Если вы размечаете `abstract-only` пакет, будьте еще более консервативны. Даже если paper выглядит сильным по abstract, без full text не следует автоматически повышать claim до `publish_to_graph = yes`.

## Supporting Spans

`Supporting spans` имеют центральное значение. Мы строим систему, где claim должен быть заземлен в конкретном текстовом свидетельстве. Поэтому наличие хорошего supporting span важнее, чем красивое перефразирование claim-а.

Если supporting span:

- не подтверждает именно тот `cause -> effect relation`, который выделен в claim;
- описывает фон, мотивацию или общий контекст, но не результат;
- говорит только о методе, но не о выводе;

то такой claim должен считаться слабым, недостаточно поддержанным или вовсе `not_causal` / `insufficient_evidence` для графа.

## Два режима экспертной разметки

Разметка теперь проводится в двух отдельных пакетах:

1. `fulltext-only bundle`
   - более сильный источник для gold set;
   - здесь можно строже судить о `design_family`, `causal_credibility` и `publish_to_graph`;
   - это основной кандидат на production-grade gold ядро.

2. `abstract-only bundle`
   - вспомогательный набор;
   - нужен для калибровки поведения системы в режиме ограниченного текста;
   - решения здесь должны быть особенно консервативными.

При сравнении двух пакетов ориентир такой:
- если один и тот же тип claim в `fulltext` и `abstract_only` размечается по-разному, приоритет имеет `fulltext`.

## Screen Gold

Поле `paper_relevant_for_policy_causal_extraction` относится к screen-level решению: должна ли статья вообще идти дальше в causal extraction pipeline.

Ставьте `yes`, если текст:

- изучает эффект, impact или consequence policy, institutional change, regulation, program, tax, subsidy, spending intervention или governance reform;
- сообщает empirical estimates, quasi-experimental evidence, experiments, `meta-analysis` или явные causal findings;
- полезен для построения policy causal graph, даже если результат `null` или `mixed`.

Ставьте `no`, если текст:

- чисто descriptive и не содержит policy-evaluation угла;
- purely theoretical без empirical evidence и без review/meta synthesis;
- является editorial / commentary / normative text;
- является bibliographic stub / redirect / технической заглушкой;
- находится вне policy-relevant social science scope.

Ставьте `unclear`, если по предоставленному тексту недостаточно evidence, чтобы уверенно принять `yes` или `no`.

## Claim Gold Fields

Обязательные поля для claim-level:

- `paper_relevant_for_policy_causal_extraction`
- `claim_present`
- `claim_text`
- `claim_type`
- `explicitness`
- `cause_text`
- `effect_text`
- `direction`
- `supporting_spans`
- `source_basis`
- `design_family`
- `causal_credibility`
- `risk_of_bias`
- `support_status`
- `publish_to_graph`

### Claim Type

- `causal_claim`: paper утверждает или явно имплицирует, что `X causes Y`
- `associative`: paper сообщает association/correlation without enough design support
- `mechanism`: текст о том, как работает связь, а не о главном causal edge
- `review_summary`: synthesis/review/meta claim
- `unclear`: нельзя надежно определить тип
- `not_applicable`: claim-level аннотация неприменима

### Explicitness

- `explicit`: текст прямо использует effect/impact/causes/leads to
- `implicit`: causal meaning strongly implied
- `unclear`: textual evidence недостаточна

### Design Family

Допустимые значения:

- `rct`
- `iv`
- `did`
- `rdd`
- `synthetic_control`
- `panel_fe`
- `ols_cross_sectional`
- `structural_model`
- `review_narrative`
- `review_meta_analysis`
- `time_series_cointegration`
- `quasi_experimental_iv`
- `quasi_experimental_did`
- `quasi_experimental_rdd`
- `quasi_experimental_other`
- `theoretical`
- `unclear`
- `not_applicable`

Если дизайн не виден из текста пакета, ставьте `unclear`, а не предполагайте его по репутации paper.

### Causal Credibility

- `strong`: explicit causal claim backed by strong identification or meta evidence
- `moderate`: plausible causal claim with decent design support but material caveats
- `weak`: likely association or weak design support
- `insufficient`: недостаточно текстовой опоры, чтобы признать claim causally credible
- `not_causal`: не должен представляться как causal edge
- `unclear`: evidence не позволяет решить
- `not_applicable`: поле неприменимо

### Risk Of Bias

- `low`
- `moderate`
- `serious`
- `critical`
- `unclear`
- `not_applicable`

### Support Status

- `supported`: текст поддерживает extracted claim
- `mixed`: текст поддерживает claim, но с явными caveats или mixed findings
- `counterevidence`: paper содержит явное contra-evidence
- `insufficient_evidence`: недостаточно текста для подтверждения claim
- `not_applicable`: статус неприменим

### Publish To Graph

Ставьте `yes` только когда одновременно выполняются все условия:

- `claim_type = causal_claim` или оправданный `review_summary`
- `causal_credibility in {strong, moderate}`
- `support_status in {supported, mixed}`
- `supporting_spans` действительно подтверждают claim
- `source_basis = fulltext`, кроме очень редких исключений уровня `meta-analysis`

По умолчанию ставьте `no` для:

- `abstract_only` claims
- claims без убедительного supporting span
- `panel_fe` / `ols_cross_sectional` claims без stronger identification evidence
- descriptive, normative или unclear statements

## Практический приоритет

Поля `design_family`, `causal_credibility`, `risk_of_bias` и `support_status` нужны не для академической красоты, а для downstream-фильтрации. На их основе строятся:

- QC gates
- prompt calibration
- regression tests
- publish rules

Поэтому ваша задача не просто "рассортировать примеры", а дать системе правильную эпистемическую дисциплину: что считать причинным утверждением, что считать только ассоциацией, а что вообще нельзя публиковать как causal edge.

Итоговая цель gold set: научить систему быть строгой, grounded и воспроизводимой. После разметки этот набор будет использоваться для оценки `precision`, `calibration`, `overcall-rate` по `quasi-natural` claims, а также для настройки adjudication prompts и acceptance criteria.

Приоритет такой:

- меньше догадок
- больше текстовой опоры
- меньше generosity к causality
- больше консервативной точности
