# AD-E02-B09-01: admission occurrence и semantic continuation

Версия архитектурного решения 1, 26 октября 2026. Это локальное расширение existing acquisition/candidate owners; identity PolicyOS и system-design-decisions не меняются. B09 требует переоценки при существенном изменении исследовательского основания и запрещает повторение только из-за имени/UUID/time; он сохраняет возможность явно разрешённых проверок устойчивости. Canonical criterion: `bundles/CYC-03.md`, блок `SOURCE_BEGIN B:B09`, B_r19:301–312. V3 здесь — контекст verification work, не номер нового DTO или прежнего reentry receipt.

## 1. Три identity, которые нельзя отождествлять

| Плоскость | Что сохраняется | Кто определяет |
| --- | --- | --- |
| Acquisition occurrence | Конкретные attempt, source artifact, epoch/passport, action generation, native admission и времена получения/допуска | Existing Data Forge/Fabric acquisition owners + `AcquisitionWorldGrowthBridge` |
| Semantic evaluation basis | Все эффективные inputs выбранной оценки и всех стадий, которые собираемся пропустить; смысл правил и purpose | Existing materialization/context/candidate/N5 owners, композиция у Runtime |
| Evaluation occurrence | Реально исполненные N5/cycle, входы, output, candidate identity и ограничения | Existing generation/source/simulation owners |

Несколько acquisition occurrences могут поддерживать одну evaluation occurrence. Это не делает их независимыми наблюдениями, не увеличивает sample size, не добавляет прошлому вычислению новый input и не обновляет автоматически его authority. В append-only history сохраняются новые события и факты admission; существующая оценка остаётся с исходной lineage.

**Выбор:** сохранить `AcquisitionWorldGrowthReceipt@1.1` как положительный факт native growth; добавить semantic decision **после** его durable selection, но **до** создания новых WMR/context/N4/N5/cycle. Admission layer не должен знать все правила N5. Его `world_committed` означает положительный native commit, а не обещание обязательного N5. Поэтому двухвариантный `AcquisitionOwnerExecutionResult@1.0` может остаться без изменения смысла: application service перестаёт считать всякий positive admission командой unconditional reentry.

Отклонены: (a) reinterpret no-growth; (b) drop new source; (c) always run N5 on every epoch; (d) глобальное переопределение hash WMR так, чтобы убрать provenance; (e) generic cache service. Все варианты либо теряют факт/семантику, либо дублируют owners. Новая branch — отдельное завершение acquisition action, **не** новый статус научной/публикационной authority.

## 2. Что означает «основание не изменилось»

Пусть `Eprev` — последняя **выбранная и проверенная** evaluation данного candidate/task, а `Pnew` — owner-prepared semantic plan для нового admitted source. `Bprev` и `Bnew` — их typed effective bases. Retain допустим только если:

1. Новая occurrence действительно допущена existing native owner; scoped delta положителен, source/profile/epoch/task binding перепроверен.
2. `Eprev` разрешается через реальный persisted source/input/output и проверенную историю; это не произвольный старый равный результат из cache.
3. Один поддерживаемый versioned projection contract полностью покрывает обе стороны: `Bprev == Bnew` по canonical семантике; все required facets разрешены и content-bound. Hash — индекс после проверки содержания, не самостоятельный verdict.
4. Current owner guards разрешают **сохранение candidate-grade результата** на выбранном frontier. Не отозвано требуемое admission, нет неподтверждённого изменения зависимости, pending revision или явного нового evaluation intent.
5. Conditional terminal commit связан с тем же action head и evaluation frontier, которые проверялись при сравнении.

`semantic_epoch.no_change` покрывает только семантику epoch manifest. Он не заменяет 2–5. Existing WMR/context hashes включают refs, transaction time и материализацию; их различие не доказывает существенное изменение, а их выборочное сравнение не доказывает полноту. Не ослаблять существующие content hashes/ArtifactRef identities.

**Equality domain отделён от evidence envelope.** В `AcquisitionEvaluationBasis` exact source refs, scope и времена derivation нужны для custody; они не сравниваются целиком как `model_dump()` или digest всего нового receipt. Сравнивается typed semantic projection под одним поддерживаемым rule/codec contract. Для различающихся refs owner сначала resolves/content-binds обе стороны и обосновывает их допустимую relation. Простое исключение refs из hash не является таким обоснованием. Неизвестная dependency role запрещает retain; разные serialization/provenance envelopes при доказанно одинаковой projection не запрещают его. Версии projection можно сопоставить только через explicit existing-owner compatibility relation; иначе неизвестность.

### Основание формируется там же, где реальное исполнение получает inputs

Extend/refactor существующие owners в **prepare → compare → commit/execute**: общий typed preparation вычисляет prospective effective state и request-shaping values, reentry потребляет именно этот prepared plan или повторно сверяет его digest перед исполнением. Retain branch потребляет тот же plan. Запрещён отдельный «дешёвый» список полей, который не связан с N5/cycle preparation.

`data_state_substrate` отвечает за canonical selected observations и bindings, `cycle_substrate` — admission/selected context и profile, `candidate_simulation` — rule/materialization/N5 semantics. `acquisition_world_growth` собирает relation и receipt. Existing schema owners предоставляют projection из своих typed inputs; не вводить service/registry рядом с ними. Pure preparation не должна создавать новый WMR/NCM declaration/candidate или произвольный scratch snapshot лишь ради последующего сравнения. Persisted basis/decision artifacts и source receipts допустимы: это evidence решения, не новый выполненный расчёт.

Минимальные facets для текущего controlled profile:

| Facet | Что обязательно учитывать | Что нельзя считать достаточным |
| --- | --- | --- |
| Candidate/task | Исходная и revised DesignProblem basis, candidate content/atom/occurrence selection, цель продолжения | Только candidate_id или route_id |
| Data/evidence | Все реально читаемые строки/slots, schema, units, missingness, multiplicity/weights, population, relevant time coordinates, effective observation selection; неизменённая остальная state basis | Только value или одинаковый count |
| Mapping/profile | Exact selected configured profile, `AcquisitionCandidateWorldRefresh`, variable→slot mapping, rule version, transforms и bounds; derived profile объясним owner relation | Совпадение label/name или итогового значения |
| World/model | Все потребляемые model/state/registry/SKG/intervention/transport inputs, model declaration/NCM/graph semantics, assumptions/calibration и ограничения | Только world_model_record_id или digest выбранного slot |
| N5 execution intent | Engine/semantic implementation identity, N5 config, horizon, comparators, seed/replications, baseline, outcome/estimand и relevant backend/numerical policy | ABI, один model_id или прошлый численный output |
| Skipped continuation | Предпосылки acquisition requirement/VOI/revision/grounding/value/promotion, которые иначе потребляются или меняют эффект в `_run_cycle`/post-loop | «N5 одинаковый — весь N6 можно пропустить» |
| Eligibility | Candidate-purpose admission, restrictions/limitations, profile validity/revocation и selection/frontier на момент решения | Старый PASS или caller `equivalent=true` |

Дешёвые обязательные последствия admission (audit, spend, source bookkeeping, проверка current eligibility и фактического состояния acquisition requirement) исполняются и для retained branch. Их изменение само по себе не заставляет заново считать N5. В skip basis входят только реально пропускаемые эффекты; «все N6 inputs должны побитово совпасть» было бы лишним ограничением. Остаток budget/номер action/новая provenance запись не являются новым numerical intent, пока не меняют actual selected computation или допускаемую цель. Если изменённая стадия может быть корректно выполнена отдельно existing owner без нового N5, выполнить её и сохранить старый numerical result с честной новой projection; не выдумывать новый cycle/evaluation receipt. Если такого композиционного пути нет, не выдавать source-only за его реализацию: existing reentry либо явный bounded residual.

Это обязательства существующих owners, не новая закрытая ontology. Current implementation начинается с существующего controlled candidate profile; будущий engine/schema подключается через тот же versioned preparation/reuse relation. Unsupported schema/required facet → `not_established`, не permissive fallback. Новый consumer field должен автоматически попадать в prepared typed basis либо иметь явно проверенную owner classification как occurrence-only. Использовать существующие typed schemas и semantic tests; не бесконечную метапроверку проверяющего.

### Допустимые исключения из equality и недопустимые shortcut

Raw serialization/transport occurrence, ingestion transaction time, attempt/job/epoch identifiers могут различаться **в occurrence envelope**, если owner доказал, что это не меняет выбранную семантику/eligibility. Они остаются в provenance и admission checks. Нельзя глобально удалить из сравнения все поля `id/time/ref`. Dataset identity может определять population/measurement; epoch — valid scope; новый источник — независимость evidence; reported year — временной ряд. Тогда соответствующий facet меняется и retain запрещён. Exact selected profile не заменяется sibling profile даже с одинаковыми числами.

Не нормализовать вручную NaN/null/zero, `1`/`1.0`, units, порядок и duplicate rows. Разрешён только выбранный owner codec/canonicalization contract; raw JSON formatting может измениться при той же typed projection. Использовать existing Core selected-profile readers, не `json.loads` вместо tagged-value decoder. Отсутствующая required dependency — unknown, не empty/default.

В текущем `build_acquired_observation_candidate_world` время материализации попадает в transaction fields и при отсутствии base valid time — в `as_of_valid_time`. Это конкретная причина не объявлять все timestamps несущественными. Если actual consumer использует такой time для world query, equality не установлена, пока owner не устранит proxy или не докажет ограниченную допустимую relation. `source_time_not_established` сохраняется: synthetic transaction time не становится source time.

Никакая relation не утверждает, что повтор stochastic/LLM execution даст те же bytes. Retain означает **нет нового основания требовать ещё один execution этой цели**, а старый результат сохраняется с прежней uncertainty/coverage. Seed/replications, новый authorized robustness intent, новый mechanism/model или выбранная numerical policy меняют basis. Не блокировать исследование только потому, что данные прежние. Name/time/UUID без изменённого intent и допуска не создают новое исследование.

## 3. Выбранные контракты и версии

Все новые artifact refs: существующий CAS selected profile, exact kind/media/schema, producer provenance, tenant/cell/run/job/action binding и durable event reconciliation. Не копировать огромные raw payloads; refs + небольшие owner-derived facets и digests достаточно. Нижеследующие имена — выбранный контракт для реализации, не утверждение, что он уже существует. Если имя/version уже занято на advancing source, использовать следующий свободный version, сохраняя эти semantics и записав mapping в handoff.

| Contract | Выбранная форма |
| --- | --- |
| `AcquisitionEvaluationBasis@1.0` | CAS kind `runtime_quality.acquisition_evaluation_basis`, schema name `polisyos.runtime.AcquisitionEvaluationBasis`, manifest version `1.0`. Typed prepared basis: projection-rule identity, exact consumed input refs, semantic facets/digests и scope. Обе стороны выводятся owner из реальных inputs; не caller dictionary |
| `AcquisitionEvaluationDecision@1.0` | Kind `runtime_quality.acquisition_evaluation_decision`, schema name `polisyos.runtime.AcquisitionEvaluationDecision`, manifest `1.0`. Comparison `equivalent / different / not_established`; decision role `candidate_evaluation_retention_only`; positive requires оба basis refs, new growth ref, selected previous evaluation tuple, current frontier/predecessor refs, eligibility witness, comparison rule and reason codes |
| Route terminal | Новый **`AcquisitionRouteLoopReceipt@2.0`**, прежний kind/schema name, manifest `2.0`. Добавленный discriminant `source_admitted_evaluation_retained`; явный `evaluation_decision_ref`. Common action scope/predecessor сохраняются. `reentry_receipt_ref=None` в новой branch; новая branch обязательна только с positive admission и equivalent decision |
| Fresh GET history | Новый schema literal **`policyos.runtime.run_candidate_simulation_acquisition_history.v3`**; discriminated source-retained projection. Старые unversioned/v2 entries читаются с прежним смыслом. Для новой branch обязательны acquisition source/growth/decision refs и retained-evaluation tuple |

`AcquisitionEvaluationDecision` — один canonical owner decision, а не три несвязанных booleans. Его positive tuple содержит: baseline generation-run/cycle identity и actual evaluation job; existing candidate source/materialization/input/execution refs для поддержанного profile; WMR/context refs; candidate/task identity. Отсутствие реально выполненного prior evaluation запрещает выдать «retained evaluation». `not_established` может иметь отсутствующий prior basis с explicit reason; оно не проходит validator equivalent variant.

`comparison=equivalent` означает equality, а не автоматическое разрешение сохранить результат. Terminal verifier отдельно проверяет owner-issued current eligibility witness и его frontier; relation может быть equivalent при отказе eligibility, и тогда retained terminal запрещён. Решение фиксирует classification каждого deciding predicate: equality и lineage `recomputed`, external facts — только в допустимой проверенной scope. Непроверенная декларация guard не становится истинной от помещения в receipt. Операционный read/permission denial также не обходится историческим receipt.

У route v2 explicit exhaustive variants: legacy no-growth сохраняет zero-delta meaning; reentry — настоящий reentry ref; source-retained — decision ref, positive growth и отсутствие new-evaluation refs. Можно переиспользовать общую typed base и verified dispatch для v1/v2; не создавать второй orchestration path. Старый v1 type не расширяется silently новым enum и не получает default нового decision. `AcquisitionWorldGrowthReceipt@1.1`, strict `NoGrowthReceipt`, phase receipts, selector и legacy reentry v1/v2/v3 не требуют version bump только ради нового terminal. Менять их лишь при реальном изменении сериализованного контракта; не распространять версии механически.

## 4. Переходы и правдивый public surface

Таблица применяется после обязательных дешёвых admission-реакций. `different` относится к основанию действительно пропускаемой работы, а не просто к новому audit/spend record.

| Native fact / semantic decision | Terminal/дальнейший путь | Evaluation/source effects |
| --- | --- | --- |
| Verified same-epoch zero delta | Existing `quarantined_no_growth` | Без повторного fetch/reentry; не записывать новую admitted occurrence |
| Positive admission + equivalent + eligible/current frontier | `source_admitted_evaluation_retained` | Новый source occurrence и action history; прежние WMR/N5/candidate/cycle bytes и pointers сохраняются |
| Positive admission + different | Existing reentry pending → `reentry_completed`, только после actual execution | Same-candidate re-evaluation; новые input/output/cycle refs; прежние readable |
| Positive admission + unknown/ineligible | Durable selected admission + typed diagnostic/recovery; **не retained terminal** | При полных runnable inputs возможна консервативная reentry по обычным guards; при missing/invalid inputs — bounded unresolved. Никакого угадывания law/profile |

Fresh GET новой branch показывает **два разных источника**: `admitted_source_ref`/growth occurrence и `retained_evaluation_source_ref` в retained tuple. Старые `new_candidate_source_ref`, `new_candidate_id`, `reentry_receipt_ref`, `continuation` остаются null для этой branch. Existing candidate root/origin refs сохраняют свой смысл; не складывать acquisition RAW и N4 source в одно поле. Candidate identity можно показывать внутри `retained_evaluation`, не заполняя поля «new». `source_admission_status=admitted` и `evaluation_disposition=retained_prior` выводятся из verified variant; caller их не назначает.

История сообщает, что новое поступление не потребовало новой оценки **по проверенному relation/scope на момент решения**. Она не говорит, что прежний N5 «выполнен на новом источнике», что policy новая/опубликована или что source сейчас актуален. Сохраняются `currentness_status=not_established`, `authority_purpose=candidate_observation_only`, `publication_authority=false`. Unknown source time/law в допустимом limited candidate profile не блокирует само сохранение истории; unknown **predicate equality/retention** блокирует retain. Исторический verified decision остаётся историческим фактом после invalidation; он не выдаёт вечный текущий reuse permit.

Новый event проходит обычные source/audit consumers. Нельзя suppress весь source-event processing ради экономии N5: изменение доказательной независимости, retention, revocation или acquisition requirement имеет свои последствия и может сделать skipped-continuation facet different. Retrieval/learning может видеть новую occurrence, но не считать её независимым подтверждением без своего owner proof.
