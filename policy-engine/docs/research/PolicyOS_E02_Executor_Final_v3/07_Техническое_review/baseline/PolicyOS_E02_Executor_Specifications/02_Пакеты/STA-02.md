# STA-02 — Точная версия входа и пригодность готового bundle

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B60, B61, B62. Тип: исправление stale derived payload + квалификация source/consumer.

Переиспользовать пригодный parameter bundle без дорогого повторного выбора, но выдать текущему numerical consumer именно payload для его backend/draws/seed.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/STA-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C62_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/STA-02_исходные_строки.txt), исходный объединённый план §STA-02 (исторические строки 7366–7479).

## 2. Уже работает — сохранить

- Общий _bundle_matches_request: context/domain/required/graph/profile/source binding, не exists→ok.
- PreparedSKGRead связывает digest, query/version и фактическую connection до cache key; WAL/смена generation отказываются.
- Key v2 сохраняет missing/null/0/false/[]; default нормализуется только по реальному consumer contract.
- Typed bundles V1.0–1.2 и ParameterTransfer уже существуют; никаких новых S-обязательств.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C62-R01 | fix: Материализовать outputs через текущий ParameterTransfer даже при reuse source-unbound bundle. | REQ-STA-02-01, REQ-STA-02-02 |
| C62-G01 | qualify: Real CAS/DuckDB/prepared-reader lifecycle, не row stub. | REQ-STA-02-02, REQ-STA-02-03 |
| C62-G02 | capability: Проверить/довести explicit state→supported prior consumer mapping; научная применимость и measured I/O остаются отдельными, G не закрывается одним fixture test. | REQ-STA-02-04 |

### Исходные обязанности, не только новые R

- B60: REQ-STA-02-01/-02 — пригодность и полные текущие derived outputs; partial coverage разрешать только при composable component contracts, иначе existing resolver.
- B61: REQ-STA-02-03/-04 — та же фактическая версия до key/read, stable reuse и measured I/O без mtime shortcut.
- B62: REQ-STA-02-03 — presence-aware key и безопасная historical miss policy.

## 4. Нормативный контракт

### REQ-STA-02-01
При accepted existing source-unbound bundle ResolveParametersNode должен заполнить объявленные literature_priors, uncertainty multipliers, runtime intervals/backend_used/ready для текущих effective backend/draws/seed. Изменение draws32→128 и seed1→9 не возвращает прежние intervals; imported bundle без derived fields не даёт пустой ok.

Источник: B60; аудит: C62-R01; проверки: TEST-STA-02-01.

### REQ-STA-02-02
Reuse допустим только после общего matcher/load/admission. Неизменный selected bundle не вызывает повторный expensive selector; изменённые context/domain/graph/profile/required/source bindings вызывают нужное разрешение или явный отказ, не stale ok. Derived failure не публикует state с ready=true или смешанными старыми полями.

Источник: B60; аудит: C62-R01, C62-G01; проверки: TEST-STA-02-01, TEST-STA-02-02.

### REQ-STA-02-03
Key и фактический SKG read используют одну prepared source identity/connection. Same-path bytes change меняет key и значение; unchanged snapshot даёт reuse; unrelated database не инвалидирует запрос. Missing/null/false/zero/list различаются, кроме явно consumer-equivalent defaults. Prepared reader закрывается ровно один раз на success/error/rebind.

Источник: B61, B62; аудит: C62-G01; проверки: TEST-STA-02-03.

### REQ-STA-02-04
В одном заявленном supported prior consumer результат bridge доходит до actual fit/request с сохранением mean/uncertainty/applicability/source binding; неподдерживающий literature-prior GCM профиль явно отказывает, не молча игнорирует prior. Отдельно измерены digest/materialization calls/bytes/time на выбранном source; эти измерения не доказывают scientific relevance.

Источник: B60, B61; аудит: C62-G02; проверки: TEST-STA-02-04.

## 5. Техническое решение и producer → consumer

В ResolveParametersNode.execute ранний source-unbound return заменить общей процедурой derivation: после matcher загрузить тот же admitted typed bundle, передать в ParameterTransfer.pure_step с effective текущими runtime params, затем записать все derived fields в branch_state с _SPEC.state_writes. Вынести существующий block после persist_context_adaptive_parameter_bundle_v1_2 в небольшой private helper materialize-runtime-from-bundle и вызвать его из fresh и reuse paths. Сохранить existing bundle ref при reuse; не переписывать его как будто сменился source. Для частичного покрытия применять только уже объявленную composability: недостающие параметры разрешает текущий selector; не склеивать профили самовольно.

SKG owner→prepared snapshot→key→resolver→typed bundle→ParameterTransfer→state→supported manual/hybrid causal consumer. Ограниченное исследование G02: выбрать один фактический caller SCMFitData, проследить mapping каждого поля; если adapter отсутствует, расширить existing caller, не GCM и не новый registry. Выход — executed mapped request/result либо точный unsupported contract и перечень отсутствующего общего adapter.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/nodes/builtins/causal/resolve_parameters.py: ResolveParametersNode.execute, _bundle_matches_request
- policy-engine/src/polisyos/foundry/methods/catalog/causal/parameter_transfer.py: ParameterTransfer.pure_step
- policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_query.py: PreparedSKGRead, prepare_read
- policy-engine/src/polisyos/scientist/orchestration/engine/idempotency.py: extract_state_slice/key contract
- policy-engine/src/polisyos/scientist/orchestration/engine/skg_snapshot.py: retained source materializer

Расширять только key недостаточно: pinned key уже различает draws, дефект внутри reuse. Пересчитывать selector при каждом seed change избыточно; глобальный cache запрет теряет полезный путь.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-STA-02-01
- Уровень: unit + targeted native integration.
- Setup: Actual V1.1 beta=2,std=.2 bundle без current SKG; NumPy bridge; request32/seed1, затем128/seed9; imported no-derived case.
- Действие: Выполнить resolver reuse и direct bridge как numeric oracle.
- Точный oracle: 128 draws/current seed result точно равен direct bridge; missing outputs восстановлены; selector calls=0; unchanged request не меняет selected bundle ref. Искусственный bridge failure не публикует ready=true.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-02-02
- Уровень: unit + targeted native integration.
- Setup: Actual typed bundle + scoped real CAS manifest; положительный same request, changed context/domain/required/graph/profile, unavailable ref.
- Действие: Run internal reuse и external cache validation.
- Точный oracle: Оба используют один matcher; invalid/unavailable binding не ok; valid result достигает следующего node и retains original provenance.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-02-03
- Уровень: native integration P-CORE/P-DATA.
- Setup: Real temporary DuckDB with value1.25; replace same-path bytes на value9.75; retained snapshot, unrelated DB; five presence variants.
- Действие: Key→read→close через actual executor; fault во время preparation; reopen.
- Точный oracle: Changed key/value9.75, stable selected snapshot hit, unrelated no change; actual same connection ID and exactly-one close; five distinct keys, declared gate default exception only. WAL/race refusal не stale read.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-STA-02-04
- Уровень: cross-lane causal + performance qualification.
- Setup: Один actual manual/hybrid prior-capable consumer, source-bound bundle; отдельно GCM; representative available source.
- Действие: Проследить state fields до SCMFitData и numerical fit; измерить digest/materialization.
- Точный oracle: Consumer использовал exact parameters/uncertainty/scope; GCM unsupported explicit; empirical applicability не повышена synthetic prior. Таблица actual bytes/calls/time с данными источника; нет выдуманного SLA.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: малый synthetic beta для numeric mapping; controlled file fault/unit store для узкого matcher. Запрещено: DuckDB row stub для transaction acceptance, success-shaped fit, отсутствующий manifest как доказательство custody.

## 7. Общая интеграция и порядок

Согласовать cache identity с STA-01/RES-01. Downstream prior mapping принимается с владельцем LANE-05 (SCM/FIT) как consumer контракт, без копирования их numerical suite; E02-I06-A проверяет доступность current derived output.

Точные общие сценарии: E02-I06-A из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: STA-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Historical bundle остаётся историческим и typed; key v2 не переименовывать. Новые derived values отражают новый runtime request. Отказ неподдержанному backend scoped; корректный candidate/prior payload не требует эмпирического сертификата. Rollback допускает отключение affected shortcut, не stale ready=true.

## 9. Free-grow и design direction

- design_direction.md §2.3, §4.1–3: discovery/custody/численный transfer/научная применимость различны.
- policy-design-causal-grounding-firewall.md §5: scalar mapping и applicability не устанавливают переносимость эффекта; полезный conditional путь разрешён.
- universal-policy-design-system-vision-and-organizing-rules.md §5 Rule12: общий derivation helper обслуживает новые совместимые bundles без if-case.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- DEC-STA-02-01: владелец causal consumer выбирает один поддержанный manual/hybrid route по текущим API. Выход — field-by-field mapping + executable positive/unsupported controls; отсутствие native backend блокирует этот witness, не R01 repair.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

