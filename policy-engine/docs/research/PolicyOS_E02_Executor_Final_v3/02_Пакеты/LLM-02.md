# LLM-02 — Разрешённый frozen reuse и общий single-flight без лишней генерации

**Лейн:** LANE-09 · **Окно:** CP2 · **Основания:** B67, B68 · **Тип:** fix + positive capability + shared native qualification.

**Практический результат.** Повторное потребление реально зафиксированного evidence-rich plain-completion input экономит physical calls, не теряя current authorization, отдельного учёта, LLM proposal semantics или полезного первого ответа.

**Статус:** исполнительское ТЗ. Это не выполненный ремонт; все новые TEST ниже — **NOT_RUN**. Исходный аудит выполнен на `20d9009be21097bfbdc38a546a15cc60213b8ace`; его полнота не означает закрытия остатков.

## 1. Основание и границы
[Аудит LLM-02](../05_Основания/Аудит/02_Пакеты/LLM-02.md), [C107 residual](../05_Основания/Аудит/01_Реестры/C107_остатки.json), [исходные B67/B68](../05_Основания/Аудит/05_Источники/LLM-02_исходные_строки.txt). Исходный predecessor/write mutex — **LLM-01**. B67/B68 — экономия уже допустимых вычислений, не новый обязательный gate первого полезного ответа. S01/S06 здесь сохраняются как ограничения стоимости/границ reuse, не как обещание нового финансового результата.

C107-R01 — лишняя физическая работа в publication race, **не** ложное разрешение. C107-G01 — недостающая положительная strict frozen-input способность: current binder доказывает один data snapshot, но не закрытие остальных materialized inputs; нельзя свести G01 к повторному запуску уже консервативного теста. C107-G02 — native qualification + fallback API/test-maintenance. Full probes — в отдельно доставленном phase1 ZIP, не новый PASS.

## 2. Уже работает — сохранить
Exact actor/tenant/scope/issuer epoch/purpose/model/request identity, Core projection proof, shared cache flight и cross-loop Future, isolated follower cancellation, bounded cleanup, scoped factory closure, original producer attribution, separate reuse receipts. Live freshness/tool/stream/seed guards не снимаются глобально. `temperature=0` не означает право объединить намеренные независимые реплики. Opaque Python calls сохраняют исходные объекты и physical-only semantics; provider-specific JSON semantics принадлежат Gateway.

## 3. Полная disposition остатков

- **C107-R01 — fix** → REQ-LLM-02-01. Одна fresh re-admission устраняет redundant physical dispatch при стабильном разрешённом опубликованном entry; stale owner не обходится.
- **C107-G01 — capability** → REQ-LLM-02-02, REQ-LLM-02-03. Реализовать узкий materialization-bound strict reuse и actual positive consumer, сохранив live/unknown guards. Это отсутствующая способность, не только квалификационный запуск.
- **C107-G02 — qualify** → REQ-LLM-02-06, REQ-LLM-02-07. LLM-01 владеет no-OTel fallback repair; LLM-02 обновляет stale contract assertions и исполняет native factory/cache/CAS coverage без shims. Shared owner: **LLM-01**.

Исходные обязанности и сохранения lossless inventory связаны отдельно в companion JSON (`obligation_dispositions`, `preservation_bindings`); номера residual не заменяют исходные обязанности.

## 4. Нормативные требования

### REQ-LLM-02-01
Если publication revision изменился между разрешённым miss admission и claim shared flight, CachingLLMClient должен выполнить одну новую owner-guarded authorization+lookup, прежде чем выбирать physical fallback. Найденный действительный entry возвращается как reuse с отдельным consumer receipt, без второй physical генерации. Повторная гонка не создаёт бесконечный retry; используется существующий разрешённый physical путь с deadline/producer admission.

Основание: B68; аудит: C107-R01. Проверка: TEST-LLM-02-01, TEST-LLM-02-02.

### REQ-LLM-02-02
Strict reuse должен поддерживать конечный объявленный класс полностью materialized plain-completion inputs: реальные selected artifact bytes/версии, точный prepared request, provider route/model/settings, purpose и current principal/epoch связываются существующим owner. URL и uncertainty_notes внутри зафиксированного текста не являются сами по себе запретом или разрешением. Live/unresolved input role и неполная materialization остаются physical-only; tools/stream/intentional seed repeats не получают разрешение этим расширением.

Основание: B67; аудит: C107-G01. Проверка: TEST-LLM-02-03, TEST-LLM-02-04.

### REQ-LLM-02-03
Trusted closure контекст создаёт producer/binder для конкретного вызова из конечных известных input roles и фактически прочитанных artifacts, а не LLM/caller cacheable flag. Авторизатор сверяет exact evidence и prepared call binding при каждом reuse; иной content/version/model/settings/route/purpose/tenant/epoch либо утраченное право исключают hit/join по старому grant. Неизвестные роли обозначаются явно и не считаются закрытыми.

Основание: B67, B68; аудит: C107-G01. Проверка: TEST-LLM-02-03, TEST-LLM-02-04, TEST-LLM-02-05.

### REQ-LLM-02-04
Две wrapper instances с одним cache и совпадающими разрешёнными identities, в том числе на разных event loops, должны разделять один physical producer для четырёх одновременных miss. Каждый consumer получает detached response и собственный reuse/settlement receipt, сохраняя original producer attribution и Core response-projection proof; mutation одного response не меняет остальные.

Основание: B68. Проверка: TEST-LLM-02-01, TEST-LLM-02-05, TEST-LLM-02-06.

### REQ-LLM-02-05
Отмена одного follower не отменяет нужный остальным producer. Deadline/error/closed scope освобождают соответствующие flight registrations и bounded Core bookkeeping без вечной записи; новый разрешённый запрос после завершённого error может выполнить новую работу. Ошибка owner guard не превращается в обход admission через uncached transport.

Основание: B68. Проверка: TEST-LLM-02-02, TEST-LLM-02-05, TEST-LLM-02-06.

### REQ-LLM-02-06
Native cache/factory/owner-admission suite должна пройти на поддержанном runtime без test shims, скрывающих отсутствующий observability API. No-OTel tracer repair выполняется единственным owner LLM-01; LLM-02 подтверждает свой actual factory/cache путь с ним. Устаревшие expectations менять по текущему публичному контракту, а не ослаблением assertions.

Основание: B67, B68; аудит: C107-G02. Проверка: TEST-LLM-02-07, TEST-LLM-02-08.

### REQ-LLM-02-07
Opaque Python inputs, не допускающие exact reusable snapshot, остаются physical-only с исходными объектами; они не нормализуются ради cache. Non-finite Gateway JSON отклоняется Gateway до transport. TEST cleanup проверяет lifecycle/resource outcomes, а не историческую приватную форму shield(flight.task).

Основание: B67, B68; аудит: C107-G02. Проверка: TEST-LLM-02-06, TEST-LLM-02-08.

## 5. Конкретное техническое решение
Все пути от `policy-engine/`, проверены на pinned commit.

### 5.1 Bounded re-admission, не новая система блокировок
В `src/polisyos/scientist/orchestration/llm/prompt_cache.py::CachingLLMClient.generate` current `admit_lookup` возвращает `_CacheAdmission` с `publication_revision`. При mismatch под `_SharedCacheState.lock` код сейчас бросает `cache_head_changed_during_admission` и broad catch выбирает uncached.

Выделить локальный admission/claim результат с различением **revision conflict** и настоящей ошибки. Только revision conflict запускает **одну** новую полную `reuse_guard(admit_lookup)` с `_authorize_reuse`, actual cache lookup и Core proof. Повторный valid hit возвращается по обычному verified reuse path. Если опять conflict — существующий физический путь с его producer admission/deadline/settlement. Guard exception не проглатывать как cache miss. Не переиспользовать первый grant после ожидания; не держать lock вокруг async provider/owner IO; не вводить distributed lock и не поднимать retry до общего бесконечного policy engine. Глобальный revision допустим как нынешний invalidation сигнал; per-key optimization не обязательна для исправления.

### 5.2 Конечная materialization closure на существующих owners
Расширить `CacheReuseRequest`/`CacheReuseEvidence` и trusted binder contract только необходимой versioned materialization привязкой; не строить второй authorizer. Существующие owners: `src/polisyos/runtime/http/services/control/nl_pipeline.py::_nl_snapshot_cache_reuse_binding`, `src/polisyos/runtime/http/services/control/job_nl_execution.py` scoped owner/guard, `src/polisyos/scientist/orchestration/llm/factory.py::_gateway_cache_reuse_scope`/`create_traced_gateway_client`, `src/polisyos/scientist/orchestration/llm/prompt_cache.py::prepare_cached_request`/`PreparedCacheRequest`/`_authorize_reuse`.

**Предлагаемый первый поддержанный профиль — frozen plain completion для materialized policy-translation payload.** Его finite input roles уже видны в `src/polisyos/scientist/policy_design/translator.py::PolicyTranslatorWorker.translate_async`: dossier, readiness_contract, constraint_report, subgroup_report, uncertainty_report, optional implementation_plan, плюс literal system/user prompt и model/settings. `TranslatorInputBundle` сам по себе mutable и не доказательство закрытия: owner фиксирует фактически сериализованные bytes до dispatch, selected artifact references/manifest profiles и nullable optional role. BudgetState/доступ/epoch остаются current controls, не «замороженным правом».

Binder для этого объявленного профиля получает actual prepared provider request и owner-captured role descriptors, читает selected CAS bytes/profile существующим API, проверяет совпадение материализованного payload с фактическим prompt, формирует trusted closure: profile/version, exact request digest, ordered role→selected ref/version/hash либо explicit absence, и remaining_unknown/live roles. `CacheReuseRequest.evidence` связывает весь реально использованный frozen набор; authorizer проверяет current actor/purpose/epoch и эту точную привязку. Нельзя авторизовать unrelated data snapshot рядом с произвольным prompt. Private closure metadata отделить от wire metadata, не меняя caller-selected wire arguments; избежать самоссылочного digest — сначала exact prepared provider call identity, затем отдельный closure binding к ней. Использовать существующий canonical identity owner, не второй JSON hash алгоритм.

`_cache_skip_reason` сохраняет остальные независимые guards. Лексические URL/uncertainty markers допускаются для **проверенного finite closure profile**, а не `cacheable=True`. Literal URL в документе не есть запрос на live fetch. Если producer действительно включает live retrieval/unresolved role или профиль не знает, откуда сформировалось соответствующее поле, closure неполна и reuse запрещён. Это контракт известного materializer, **не доказательство всей семантики произвольного естественного языка**. Unknown сохраняется явно; никаких regex «commit выглядит immutable», удаления ссылок или TTL обхода.

Положительный route подключает existing translator consumer через current scoped factory и frozen materialization binder; configuration для проверки temperature=0/fallback_on_error=False, **не** изменение default temperature=0.1. Два разных compatible bundles проходят тот же профиль. Если binding placement требует общего helper вместо import runtime из scientist, вынести узкую часть в existing llm owner, а runtime оставить thin adapter; правило dependency direction сохраняется. Новый общий код здесь оправдан отсутствующей closure способностью, новый branch для каждого текста — нет.

Важно: `build_design_problem_from_nl_request` использует tool-calling; он **не** становится reusable от этой работы. Не объявлять весь NL pipeline covered и не распространять finite translator proof на retrieval/другие stages. Нужен working narrow capability, не «исследовать universal model inputs».

### 5.3 Native/test ownership
Shared fallback `src/polisyos/core/observability/__init__.py::PolicyOSTracer.start_as_current_span` сейчас не принимает `kind`, тогда как normal tracer принимает keyword attributes/kind/record_exception/set_status_on_exception. Repair и общий compatibility test — **LLM-01**, LLM-02 только consumption qualifier. Existing opaque NaN и private task cleanup assertions обновить по настоящему contract, не спрятать исключения. Existing test owners: `tests/unit/scientist/orchestration/llm/test_prompt_cache.py`, `tests/unit/scientist/orchestration/llm/test_cache_owner_admission.py`, `tests/unit/scientist/orchestration/llm/test_prompt_cache_scope_admission.py`, `tests/unit/scientist/orchestration/llm/test_factory_cache_composition.py`; translator consumer fixtures — `tests/unit/scientist/policy_design/test_phase_b_policy_workers.py`. Native CAS/runtime qualification обязана использовать поддержанный Python 3.14, не AST shims.

## 6. Локальные различающие проверки

Все TEST — будущие спецификации проверок, не заявления о существующих тестовых функциях. Сначала расширять перечисленные реальные test owners; новый файл — только при отсутствии подходящего owner.

### TEST-LLM-02-01 — native deterministic race / two wrappers two loops / NOT_RUN
- **Setup:** Общий real cache, current exact owner grant, два wrappers/event loops. Barrier останавливает первый после фактического miss admission, не копируя generate. Второй публикует valid entry; затем первый продолжается.
- **Действие:** Сначала показать, что второй sequential lookup даёт hit; отпустить первый и собрать provider count, guard/authorize calls, receipts и ответы.
- **Oracle:** Всего один physical provider call; первый повторно вызывает live guard+authorizer и получает опубликованный response с отдельным receipt/original producer. Old code делает второй call, что обязано нарушить oracle.
- **Ожидаемый исход:** Positive race repair; без вмешательства оба результата равны immutable saved projection, а учёт consumer различен.
- **Doubles / граница:** Controlled provider и scheduling barriers разрешены. Real generate/cache/Core settlement/factory metadata identity обязательны; нельзя вручную подложить _CacheAdmission/подменить admission body.
- **REQ:** REQ-LLM-02-01, REQ-LLM-02-04.

### TEST-LLM-02-02 — native race boundaries / NOT_RUN
- **Setup:** Та же гонка; между admission и retry: epoch/owner closure, deadline, authorization revocation; отдельно два revision changes подряд.
- **Действие:** Возобновить pending caller и проверить точный дальнейший путь.
- **Oracle:** Старый grant не используется. Closed guard даёт existing typed ownership error и 0 новых unauthorized dispatch. При разрешённом owner и повторной churn ровно одна повторная admission попытка, затем bounded existing physical fallback, не spin/deadlock; deadline respected.
- **Ожидаемый исход:** Revoked/closed — refusal или current-authorized independent physical только по действующему producer rule, никогда stale hit. Churn не означает новый free provider call.
- **Doubles / граница:** Позволены deterministic fence callbacks/barriers; запрет заменить guard no-op в assertions про owner currentness.
- **REQ:** REQ-LLM-02-01, REQ-LLM-02-05.

### TEST-LLM-02-03 — native integration strict binder→factory→consumer / NOT_RUN
- **Setup:** Actual FileSystemCAS с двумя immutable materialized bundles; finite plain-completion profile, URL/uncertainty_notes как literal frozen input. Current execution scope, real binder/factory/cache/traced ledger и controlled provider. Для полезного consumer — PolicyTranslatorWorker.translate_async при explicit temperature=0, fallback_on_error=False; frozen typed six-role TranslatorInputBundle, без tools/retrieval.
- **Действие:** Сформировать closure из реально сериализованного bundle/prompt через owner, выполнить два identical calls в strict scope и повторить с совместимым вторым bundle без отдельной case branch.
- **Oracle:** На каждом bundle один provider miss затем authorized hit; authorizer вызывается, URL/text bytes не удалены, точный PolicyBrief получен actual consumer, current scope и separate consumer receipt присутствуют. Default translator temperature0.1 не изменён. Existing lexical strict guard должен провалить provider-count oracle.
- **Ожидаемый исход:** Два positive closed-input examples; cached response остаётся proposal/text и не повышает readiness/authority.
- **Doubles / граница:** Provider response контролируемый допустим; реальны CAS/profile read, materialization, prepared request identity, scoped factory/cache/ledger и consumer parse. Не stub translator/factory/CAS и не выдавать это за качество живой модели или full NL tool-calling route.
- **REQ:** REQ-LLM-02-02, REQ-LLM-02-03.

### TEST-LLM-02-04 — native closure rejection and non-lexical boundary / NOT_RUN
- **Setup:** Valid closed TEST-03 плюс: uncovered/live input role, mismatch artifact hash/profile/version, changed prepared text/settings/route, caller forged cacheable/closure, literal URL not fetched, trusted live retrieval descriptor.
- **Действие:** Повторить вызов; сравнить actual provider args и reuse/skip cause.
- **Oracle:** Pure literal URL не автоматически live access request и не портится; complete closed case reusable. Uncovered/live/tampered roles не дают cache hit; exact current call может физически выполниться только с обычным producer admission. Tools/stream/seed и explicit retrieval freshness guards не снимаются для unsupported profile.
- **Ожидаемый исход:** Positive literal frozen text плюс negative coverage/identity matrix; инъекция arbitrary closure flag не проходит.
- **Doubles / граница:** Можно fixtures ролей и transport counter; нельзя доказывать closure LLM заявлением, regex commit или произвольным snapshot unrelated prompt.
- **REQ:** REQ-LLM-02-02, REQ-LLM-02-03.

### TEST-LLM-02-05 — native singleflight identity and currentness / NOT_RUN
- **Setup:** Четыре одновременных same-key callers; отдельные variants tenant/scope/issuer epoch/purpose/model/route/seed/snapshot/parameters. Current owner revocation после ожидания producer. Real Core attestation.
- **Действие:** Собрать calls/events, изменить один returned payload и повторно читать другой; повреждённую projection proof попробовать использовать.
- **Oracle:** Same allowed key →1 physical,4 correct consumer accounting outcomes. Разные identities/intentional seeds не сливаются; follower после revoke не получает stale authorized reuse. Projection proof mismatch не выдаёт cached response. Detached copies неизменны, original producer event сохраняется.
- **Ожидаемый исход:** Полезная coalesced работа сохраняется; boundary cases дают separate physical/typed refusal по actual admission, не ошибочный shared hit.
- **Doubles / граница:** Controlled provider разрешён; Core proof/ledger и final current guard реальные, не handmade success receipt.
- **REQ:** REQ-LLM-02-03, REQ-LLM-02-04, REQ-LLM-02-05.

### TEST-LLM-02-06 — native lifecycle / NOT_RUN
- **Setup:** Shared cross-loop flight; один canceled follower, два live consumers; затем provider error и deadline variants; наблюдаемые Core registration/flight counters и повторная permitted попытка.
- **Действие:** Cancel follower, завершить producer; дождаться остальных. Повторить error/deadline; после cleanup запустить новый разрешённый запрос.
- **Oracle:** Другие получают результат; canceled consumer не получает выдуманный receipt success; inflight registrations возвращаются к baseline после окончания/waiter release; новые permitted calls не зависают на tombstone. Проверка не требует await shield(flight.task), допустим текущий wrap_future result.
- **Ожидаемый исход:** Positive isolation/recovery плюс bounded cleanup; provider error не кэшируется как successful reusable answer.
- **Doubles / граница:** Scheduling/barriers allowed; нельзя проверять только private task shape, удалять registry вручную или заменить реальные cleanup hooks.
- **REQ:** REQ-LLM-02-04, REQ-LLM-02-05, REQ-LLM-02-07.

### TEST-LLM-02-07 — native factory with optional observability profiles / NOT_RUN
- **Setup:** Существующий supported no-OTel profile и обычный tracer profile; LLM-01 shared repair опубликован. No injected shim добавляющего start_as_current_span(kind=...).
- **Действие:** Исполнить actual factory→traced client→cache miss/hit/failure path, затем existing unit suite owners.
- **Oracle:** Оба поддержанных profiles соблюдают public start_as_current_span call contract; проверки доходят до cache/receipt assertions, не только import. Ошибки не скрыты blanket catching. Native results содержат точный runtime/profile и trace outcome.
- **Ожидаемый исход:** No-OTel compatibility не требует OTel install. Это shared fix consumption, не дублированный repair.
- **Doubles / граница:** Можно детерминированный transport; no-op tracer разрешён только штатный fallback, не test replacement. Unsupported profile явно N/A с основанием, не PASS.
- **REQ:** REQ-LLM-02-06.

### TEST-LLM-02-08 — native regression contract maintenance / NOT_RUN
- **Setup:** Opaque custom Python object и float NaN в opaque provider path; отдельно настоящий Gateway JSON request с non-finite numeric field. Current cache Core lifecycle test.
- **Действие:** Вызвать opaque twice; Gateway once; выполнить обновлённые cleanup tests.
- **Oracle:** Opaque:2 physical,0 entries, исходный object/value сохранён, не превращён в None/string. Gateway: отказ до transport,0 dispatch. Cleanup oracle из TEST-06, не old implementation coupling.
- **Ожидаемый исход:** NaN expectation исправлена по actual provider boundary; ни blanket reject всех Python inputs, ни permissive nonfinite wire.
- **Doubles / граница:** Opaque provider double допустим как этот контракт; настоящий Gateway preparation/JSON validation обязателен для pretransport assertion.
- **REQ:** REQ-LLM-02-06, REQ-LLM-02-07.

## 7. Общий сценарий, зависимости и ownership
[LANE-09](../03_Интеграция/LANE-09.md), **E02-I09-B**: LLM-01/LLM-02 совместно предъявляют один factory→cache/singleflight→trace ledger evidence set. LLM-02 даёт revision-race schedule, finite frozen profile и one-miss/per-consumer receipt oracles. Это не отдельная тяжёлая infrastructure suite.

LLM-01 — predecessor и sole shared writer mutex для factory/cache integration и no-OTel fallback; LLM-02 владеет согласованным cache algorithm delta и finite closure contract после freeze shared base. Технически оба меняют `src/polisyos/scientist/orchestration/llm/prompt_cache.py`/factory, поэтому последовательные commits либо один writer с review второго, не конкурентные правки. Runtime binder/translator materialization hook согласовать с текущими caller owners до изменения: не переносить scientific authority в cache и не менять translator output semantics. CAS/owner ledger contracts читаются у LANE-06; не вводить параллельный ledger.

Порядок: R01 characterization → bounded retry; отдельно finite closure producer/binder→cache→consumer positive/negative; LLM-01 fallback consumption; единая E02-I09-B волна. R01 не зависит от разрешения всех чужих retrieval profiles.

## 8. Совместимость, история, rollback
Historical cache entries без нового trusted closure не считаются strict URL-eligible автоматически. Старый безопасный ordinary/nonstrict behavior и exact identity controls сохраняются; новый finite profile включается только при наличии current owner и фактической closure. Не переписывать history/ledger чтобы «достроить» provenance. При изменении reusable identity версия/namespace явно отделяет old/new entries, не ломая чтение исторических receipt records.

На ошибке нового closure adapter affected profile возвращается к существующему authorized physical-only path, не к безусловному отказу всех LLM calls и не к небезопасному URL reuse. Closed producer owner по-прежнему отказывает. Rollback отключает только новый reuse eligibility; original producer accounting и independent outputs сохраняются.

## 9. Free-grow, LLM и границы authority
[Vision §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): способность существует, когда настоящий consumer использует её; finite reusable materializer важнее нового реестра. [North Star §2 и §7](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md): LLM semantic proposal и проверяемое execution/evidence не смешиваются. [Identity/custody §5 и §7](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md): подпись/owner — граница сильного утверждения, а не запрет полезной conditional работы.

Отступление от буквального URL guard оправдано actual materialized bytes + exact call/current owner, не желанием повысить hit rate. Не требовать доказательства всей natural-language semantics или детерминированного universal model inventor. URL может быть просто цитируемой строкой. Новый supported input role требует описанного general materialization contract/test; новый dataset/text того же роли — только данные. Не считать reuse качеством/истинностью LLM ответа или authority policy brief.

## 10. Приёмка и запрещённые утверждения
Предъявить before/after publication-race reproducer; exact finite role contract и output closure fixture; prepared request/selected bytes hashes; provider counts + per-consumer trace/ledger events; current guard call evidence; TEST-01–08 native results; shared E02-I09-B locator; LLM-01 fallback consumption result. Runtime supported Python 3.14, dependencies/profile и commands зафиксировать. Existing verified targets перечислены §5.3; адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`, не обещание наличия runner здесь.

Нельзя считать отсутствие второго call доказанным только cache stats; обход guard — repair гонки; fixture authorizer — институциональным разрешением; default0.1 translator — deterministic cache case; fallback PolicyBrief — доказательством actual cache consumer; positive ordinary URL reuse — strict capability; одна data snapshot — closure всех inputs; two fixture answers — качество живой модели; native imports — native suite PASS. G01 закрывается только работающим положительным finite strict route и отрицательной incomplete/live boundary. G02 не закрыт до native выполнения без скрывающих tracer шима. Экономия денег/latency в реальном workload не заявляется по controlled provider count.

