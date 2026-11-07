# CYC-01 — Штатный вход и сохранённая постановка реального N5

**LANE-01 · B01, B02, B03 · CP1 · исполнительское ТЗ; не исполнено.**
Основание: `20d9009be21097bfbdc38a546a15cc60213b8ace`; исходный план, строки 174–302; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CYC-01.md). Все новые TEST — **NOT_RUN**. Это ТЗ, не сообщение об исполнении.
**Тип работы:** Квалификация уже связанного пути; адресный ремонт только при обнаруженном разрыве; отдельно ограниченный опыт переносимости.
**Практический результат:** Пользователь задаёт вопрос обычным HTTP-входом, не конструируя внутренний Python-context; получает повторно читаемый численный условный результат с точным смыслом модели и ограничениями.

## 1. Что сохраняется

- LK02: Foundry input binding и Fabric data plane сохраняют разные роли; не вводить второй world store.
- LK17: публичный OPA facade и действующая авторизация не удаляются ради сокращения aliases.
- Явный None для допустимого режима не равен непереданному решению; protected intent сохраняет preconditions.
- Post-compile context owners, leaf-specific capsules, N4 source membership, WMR/catalog/profile identity и доступный selected input.
- K_sim/кандидатный результат не становится K_world, N9 или разрешением действия; N4 сохраняется при недоступном profile.
- S02/S08: общий механизм и проверяемый второй случай; это отдельная характеристика роста, не бесконечное расширение B01–B03.

## 2. Полный disposition исходных обязанностей и остатков

| Основание | Disposition | REQ | Решение / владелец |
|---|---|---|---|
| B01 | qualify | REQ-CYC-01-01, REQ-CYC-01-05 | Исходный ранний безусловный барьер уже изменён; новый product rewrite не назначается без несоответствия. |
| B02 | qualify | REQ-CYC-01-02, REQ-CYC-01-06 | Post-compile/recursive контекст уже связан; нужен actual consumption и подмена связей. |
| B03 | qualify | REQ-CYC-01-03, REQ-CYC-01-04 | Builder/controller/persistence существуют; проверяется доступный точный input и действительное число. |
| CYC-01 §11 runtime qualification | qualify | REQ-CYC-01-01, REQ-CYC-01-03, REQ-CYC-01-04 | Нативный прогон исходного отчёта UNRUN; наличие теста не PASS. |
| CYC-01 §11 portability | capability | REQ-CYC-01-07 | Отдельный ограниченный прирост переносимости, не утверждение отсутствия всего discovery. |
| CYC-01 §11 request provenance | qualify | REQ-CYC-01-03, REQ-CYC-01-06 | Проверить конкретный candidate V5/generic reader; не создавать новый receipt format заранее. |
| CYC-01 §11 foreign-context controls | qualify | REQ-CYC-01-02 | Рабочий positive и changed-binding negatives обязательны вместе. |
| CYC-01 §11 numerical oracle | preserve | REQ-CYC-01-04 | В текущем полном served-файле обнаружен oracle 0.5 в строках1587–1614, вне старого прочитанного окна; использовать его, не дублировать harness. |
| CYC-01 §11 positive N8 | shared | REQ-CYC-01-04, REQ-CYC-01-05 | Configured candidate-N5 тест намеренно ловит вызов N8; положительный N8 принимает другой owner. Owner: **CYC-02**. |
| CYC-01 §10 authored composition | shared | REQ-CYC-01-05, REQ-CYC-01-07 | Alternatives/гипотетический joint не доказывают authored compound; здесь сохранить ограничения. Owner: **CYC-05**. |
| CYC-01 §12 temporal stability | shared | REQ-CYC-01-06 | Историческое чтение здесь; обновление и current continuation принимает CYC-03. Owner: **CYC-03**. |

## 3. Атомарный нормативный контракт

### REQ-CYC-01-01
При разрешённом ordinary simulate-only запросе actual HTTP/job owner должен явно выбрать режим и передать отсутствие EvalSafety-context как None; клиенту не требуется внутренний Python-context. Непереданный выбор и защищённый intent без своего допуска должны отклоняться до защищённого использования. Actor/tenant/cell, lease и producer budget продолжают проверяться до соответствующих операций; разрешённое отсутствие EvalSafety-context не снимает эти проверки.
Источник: B01; остаток: B01; CYC-01 §11 runtime qualification. Проверка: TEST-CYC-01-01, TEST-CYC-01-02.

### REQ-CYC-01-02
После построения DesignProblem фактически используемый leaf N4/N5 должен получить owner-bound context именно этой задачи и выбранного WMR/catalog/profile; подмена любой существенной связи должна остановить зависимую операцию до использования, сохранив независимый кандидатный результат.
Источник: B02; остаток: B02; CYC-01 §11 foreign-context controls. Проверка: TEST-CYC-01-02, TEST-CYC-01-05.

### REQ-CYC-01-03
В поддержанном served-профиле запрос N5 должен быть восстановим из сохранённых typed input/selection refs без пользовательского callable; выбранный настоящий controller обязан потребить этот запрос, а не успех-shaped замену.
Источник: B03; остаток: B03; CYC-01 §11 request provenance. Проверка: TEST-CYC-01-01, TEST-CYC-01-04.

### REQ-CYC-01-04
Для фиксированного малого модельного примера сохранённый N5 должен содержать численный эффект, согласованный с независимым расчётом объявленного вмешательства и модели; свежий reader обязан вернуть те же значения, единицы, модель и существенные ограничения.
Источник: B03; остаток: CYC-01 §11 numerical oracle; B03. Проверка: TEST-CYC-01-01.

### REQ-CYC-01-05
При отсутствующем или неактуализируемом profile система должна сохранить доступное N4-предложение и различающую причину; она не должна объявлять N5/N8/N9 исполненными либо стирать K_sim/effect-basis/currentness ограничения ради положительного статуса.
Источник: B01, B02, B03; остаток: CYC-01 §§9–10 partial result and authority boundary. Проверка: TEST-CYC-01-03, TEST-CYC-01-05.

### REQ-CYC-01-06
После сохранения исторический input/result должен читаться в своей версии без переписывания байтов; новая значимая basis не должна заимствовать прежнюю currentness. Внутренняя совместимая callable API допускается вне сериализованного public пути.
Источник: B02, B03; остаток: CYC-01 §11 provenance; CYC-01 §12 temporal stability. Проверка: TEST-CYC-01-04.

### REQ-CYC-01-07
Для второго содержательно отличного поддержанного вопроса исполнитель должен предъявить прохождение тех же composition/binding owners и перечень специальной подготовки. Пригодный совместимый ресурс должен подключаться через существующий общий контракт, без ветки по имени кейса; если общей способности не хватает, должен быть предъявлен точный пробел и ограниченное повторно используемое решение, а не фиктивный success. Перечислить, что вводит пользователь и что выводит server owner: ресурс, горизонт, comparator и бюджет; пять допустимых engine labels не означают пять квалифицированных served маршрутов.
Источник: B01, B02, B03; остаток: CYC-01 §11 portability; S02; S08. Проверка: TEST-CYC-01-06.

## 4. Конкретное техническое решение

### Сначала квалифицировать, а не переписывать
Зафиксировать exact existing environment/import origin и прочитать полное тело выбранного served test вместе с его fixtures. Запустить TEST-01; окружение/skip не называть product defect. Внешний HTTP-input оставить data-only. Если positive работает, изменения source ради B01–B03 не нужны; расширять только недостающие assertions/совместимый профиль.

### Канонический producer→consumer путь
job_nl_execution.run_nl_pipeline_job передаёт server intent, producer binding и root_evaluation_context=None в compile_and_run_recursive_generation_cycle. После build_design_problem_from_nl_request existing resolver выдаёт context/handoff; recursive owner передаёт leaf-specific maps/capsules в GenerationCycleController. JointSimulationPort разрешает candidate/generic typed input либо поддержанный data-only builder, revalidates WMR/source и вызывает свой _controller.run(request); persist_joint_simulation_result сохраняет bytes; load_joint_simulation_result и свежий GET проверяют selected binding. Новые adapters не должны обходить любой из этих owners.

### Если обнаружится точный разрыв
В исправлении переносить отсутствующее semantic поле/selected ref через существующий handoff и его validator; не расширять подставными defaults. Если branch выполняет N5 без exact input provenance, сначала использовать его существующий CandidateSimulationN5InputV5/GenericCycleN5Input owner и reader; новый формат допустим лишь после доказательства, что текущий не выражает нужное поле. Ошибка должна сохранять адресный код и уже готовую независимую работу.

### Контекст и child identity
Сравнивать содержательный problem/model/catalog/profile basis, не требовать один object identity для всех узлов. На каждом leaf проверять свой problem ref, WMR и source membership; для изменившейся basis использовать existing reissue owner (CYC-03), не принимать старый context и не убирать hash guard.

### Oracle уже найден
Старый отчёт честно не читал test после1240. Новый read выявил persisted numerical oracle1587–1614, заданную slope/base/materialization и effect0.5; перенести эту связь в evidence матрицу, а не писать второй numerical framework. Candidate-профиль имеет N8/N9 traps; positive N8 остаётся REQ CYC-02 и общим E02-I01-A.

### Отвергнутые альтернативы
Не создавать второй world store/context DTO; не снимать EvalSafety/actor/resource guards; не удалить все internal callable API; не считать все пять engine-kind значений пятью квалифицированными routes. GenericCycleN5RequestProfileV1 остаётся NCM-scoped до отдельного подтверждения.

## 5. Локальные тесты и точные oracle

Идентификаторы ниже — **предлагаемые проверки**, не имена уже существующих функций. Указанные file/selectors действительно найдены; их прежний source read не PASS. Любая дополненная проверка должна различать старый дефект/контролируемое удаление нужного механизма и исправленный positive.

### TEST-CYC-01-01 — native integration, P-CORE + выбранный P-JAX · NOT_RUN
- **REQ:** REQ-CYC-01-01, REQ-CYC-01-03, REQ-CYC-01-04.
- **Setup:** Использовать существующий test_configured_candidate_simulation_served.py::test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift; test tenant, temporary SQLite/CAS, его declared procurement/model fixture.
- **Действие:** Запустить actual POST→worker→N4/context→JointSimulationPort→controller, затем разрешить сохранённый CandidateSimulationN5InputV5 и N5 result.
- **Oracle:** Существующие строки1600–1614: expected_effect = outcome_per_target_unit*(materialization.value-target_baseline), равно0.5±1e-12; все profile.replications эффектов согласованы с ним в уже заявленной численной погрешности0.02. Этот допуск относится только к данному тестовому NCM, не новым доменам.
- **Ожидаемо:** Есть фактический numerical call и сохранённый result; ordinary клиент не передаёт внутренний context; K_sim и not_established comparator не повышаются.
- **Evidence:** Команда, exit/skip, source/backend binding, входной profile/model/input/result refs и assertions numeric/readback.
- **Doubles:** Допустим deterministic traced LLM protocol fixture и тестовая identity. Запрещено заменять JointSimulationPort/controller/store reader успешной записью; наблюдающая обёртка должна делегировать оригиналу.

### TEST-CYC-01-02 — native boundary/integration · NOT_RUN
- **REQ:** REQ-CYC-01-01, REQ-CYC-01-02.
- **Setup:** Тот же рабочий profile и leaf; по одному заменить problem hash, WMR, selected registry/profile или source member при сохранённых прочих входах. Отдельные контроли: чужие actor/tenant/cell, отсутствующая lease либо исчерпанный producer budget; не смешивать с domain/model отказами.
- **Действие:** Пройти actual owner admission/reader и попытку зависимого N5.
- **Oracle:** Каждая несогласованная связь даёт адресный existing refusal до физического расчёта; неизменный positive снова работает; чужой child context не принимается как родительский. Auth/resource controls не допускают соответствующую операцию; исправление не создаёт новые credentials.
- **Ожидаемо:** Ноль вызовов запрещённого numerical/protected действия на invalid inputs; N4/исторический результат не уничтожены.
- **Evidence:** Полный deciding output и наблюдаемые call counts; identify exact validation owner, не только HTTP status.
- **Doubles:** Можно менять только атакуемый payload/ref либо снабжать согласованно перевыпущенный чужой artifact; нельзя подменять verifier на функцию, всегда возвращающую False.

### TEST-CYC-01-03 — native served negative + recovery · NOT_RUN
- **REQ:** REQ-CYC-01-05.
- **Setup:** Существующие selectors test_served_unknown_candidate_profile_keeps_persisted_n4_candidate и test_served_unrefreshable_profile_evidence_keeps_n4_and_blocks_n5.
- **Действие:** Подать отсутствующий profile, затем отдельно profile с неактуализируемым evidence; прочитать run после worker.
- **Oracle:** В первом случае missing profile, во втором profile_refresh_unavailable; N4 ref доступен; N5/N8/N9 not_run, нет ложного numerical success.
- **Ожидаемо:** Полезное кандидатное предложение сохраняется с точной следующей потребностью; охранные ограничения не выключены.
- **Evidence:** Persisted N4 + fresh response, отрицательные call traps, сопоставление разных причин.
- **Doubles:** Контролируемый unavailable provider допустим; запрещена подмена самой логики fallback/сохранения.

### TEST-CYC-01-04 — native persistence/consumer · NOT_RUN
- **REQ:** REQ-CYC-01-03, REQ-CYC-01-06.
- **Setup:** Взять result/input TEST-CYC-01-01 и временное хранилище; новый reader/app без прежних Python objects.
- **Действие:** Разрешить текущие owner-selected refs, восстановить actual request; отдельно удалить только выбранные bytes или изменить meaningful parameter/model binding.
- **Oracle:** Сохранены request/outcome/horizon/model/selected source refs и численные значения; missing/tampered/foreign не превращаются в default input. Исторические bytes до/после неизменны.
- **Ожидаемо:** Корректный input повторно доступен; невозможность чтения видна как scoped refusal, не как утверждение неправильной мировой модели.
- **Evidence:** Hashes сохранённых bytes, exact selected refs и positive/negative readback. Отдельно отметить fresh app против fresh process; независимый process общий owner CYC-02.
- **Doubles:** Настоящий persistence protocol и reader; не возвращать заранее собранный request из fake store.

### TEST-CYC-01-05 — native authority-boundary · NOT_RUN
- **REQ:** REQ-CYC-01-02, REQ-CYC-01-05.
- **Setup:** Рабочий candidate/conditional пример и отдельный protected intent без допустимого scope.
- **Действие:** Выполнить candidate N5 и попытку защищённого действия; проверить N8/N9 traps текущего candidate-only сценария.
- **Oracle:** Candidate result существует; protected action не вызван; decision front пуст и publication authority отсутствует. Parent alternatives не становятся authored composition.
- **Ожидаемо:** Граница допустимости не уничтожает полезный условный/candidate output и не повышает его смысл.
- **Evidence:** Actual terminal/front/promotion fields, resource/tenant scopes, negative calls.
- **Doubles:** Тестовый identity issuer допустим только в declared test scope; нельзя вручную выставлять value_ready/certified.

### TEST-CYC-01-06 — capability witness, shared E02-X01 · NOT_RUN
- **REQ:** REQ-CYC-01-07.
- **Setup:** После малого positive выбрать иной смысловой вопрос с уже доступным совместимым ресурсом; заранее зафиксировать source/model/outcome/unit и независимый ожидаемый bounded результат. Не использовать только замену IDs.
- **Действие:** Зарегистрировать ресурс через его существующий owner; пропустить ordinary intent через тот же общий путь; учесть ручные input artifacts и новые общие изменения.
- **Oracle:** Результат отвечает на конкретную часть второго вопроса; нет if case/domain-name маршрута. Если ресурс найден, но не consumed, ошибка не считается честным отсутствием знания. Если семантики нет, предъявлено DEC-CYC-01-01 с конечным действием. Таблица user-supplied/server-derived для ресурса, горизонта, comparator и бюджета, отдельно qualified route и лишь допустимый engine label; неизвестный comparator не повышается.
- **Ожидаемо:** Отдельно limited repair PASS и portability outcome; не обещать универсальную пригодность/эмпирическую truth.
- **Evidence:** Сравнение первого/второго кейса: preparation, generic code delta, actual call/input/readback, domain judgment owner либо declared synthetic boundary.
- **Doubles:** LLM proposal может быть контролируемым; сам binding/discovery selected resource и N5 нельзя заменить post-hoc готовым result.

## 6. Общая интеграция и ownership

Использовать **E02-I01-A, E02-X01** из [общего LANE-01](../03_Интеграция/LANE-01.md); не создавать ещё одну копию тяжёлого стенда. CP1 — окно связанной приёмки, не новый runtime реестр и не full CI на каждый пакет.

- CYC-02: положительный conditional N8 и свежий независимый reader; не приписывать это candidate-N5 тесту.
- SIM-01/SIM-02/SIM-03/SEL-01: numerical/selection falsifiers принимаются у своих owners; CYC-01 проверяет их штатное соединение.
- CYC-03/ACQ-01: новая basis и continuation отдельно; CYC-05: действительная child/composition способность отдельно.
- CP1: составная приёмка нужного пути; интерфейсы LANE-04 и LANE-06 только по фактическому выбранному маршруту.

Порядок: установить существующий positive → воспроизвести адресный остаток → внести минимальное intentional изменение, если оно требуется → локальные различающие controls → affected shared scenario на стабильном общем наборе inputs. Один writer у фактически пересекающегося owner; чтение и непересекающиеся документы не сериализовать.

## 7. Совместимость, миграция и rollback

Сохранить публичные/internal API, если конечный caller census не доказал их retirement; typed served путь не обязан удалять внутреннюю factory. Historical artifacts читаются прежним reader/profile без mutation. Forward fix меняет новые records и binding; rollback продукта не переписывает старые evidence bytes. При регрессии вернуть предыдущую рабочую composition через обычный forward/revert change, не отключать guards.

## 8. Free-grow и смысл design-decisions

- [universal-policy-design-target-architecture-and-gap.md](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) § «D0 — Decision: B-on-A, Shadow-First»: генерация/поиск не блокируются отсутствием всей authority-архитектуры.
- [universal-policy-design-system-vision-and-organizing-rules.md](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) §6 «The Capability Reality Bar» и §5 Rule12: producer→artifact→consumer; zero-new-code трактуется для совместимого ресурса, не для принципиально новой семантики.
- [stage0-custody-kernel-ratification.md](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md) §4.3 K06: declared unknown допустим в candidate band; защищённое действие требует своего основания.

Нормативными являются REQ этого пакета; design-ссылки объясняют цель и статус выбранного решения, но не создают скрытого требования реализовать все планы корпуса.

## 9. Ограниченные открытые решения

### DEC-CYC-01-01: Какой второй содержательно отличный случай доступен через имеющийся ресурсный/модельный контракт?
**Owner:** Исполнитель CYC-01 с предметным reviewer; назначенный проектом координатор сквозного сценария E02-X03 «второй содержательно иной случай»
Варианты: Совместимый существующий profile/resource: только данные/регистрация.; Нужна отсутствующая общая семантика: минимально расширить существующий owner и предъявить повторное использование.; Доступного основания нет: сохранить полезный candidate/план получения, не заявлять portability PASS.
**Выбрать по:** Реальный catalog/resource manifest, exact model/outcome/unit, независимый oracle, список case-specific подготовки.
**Обязательный выход:** До TEST-06 выбрать один вариант и вход; результат/ограничение/конкретный следующий общий механизм. Не блокирует TEST-01–05 и bounded repair acceptance.

## 10. Предъявление и запрет ложного PASS

Предъявить REQ↔TEST↔shared-scenario trace, exact command/exit/UNRUN/SKIP, pinned inputs/backend и доступные решающие bytes. B01–B03 accepted только при положительном actual served пути плюс falsifiers; conditional/public numerical readback совместно с CYC-02. Отдельно portability outcome. Один зелёный marker, источник без исполнения, отсутствующий источник или authority refusal сами по себе не PASS способности. Свежий CI canary на том же HEAD остановился до основного canary из-за отсутствующего POLISYOS_RUNTIME_CANARY_BEARER_TOKEN; live-job success с пропуском credential-dependent lane не квалифицирует этот путь. Для исполнения нужен разрешённый test principal; это предусловие проверки, не новый дефект модели и не повод ослабить auth.

## 11. Проверенные текущие места

- [policy-engine/src/polisyos/runtime/http/services/control/job_nl_execution.py:290–350](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/job_nl_execution.py#L290-L350) — `_compile_control_nl_job: explicit mode/context`.
- [policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py:1639–1779](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1639-L1779) — `compile_and_run_recursive_generation_cycle`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:4020–4475](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4020-L4475) — `JointSimulationPort and _build_joint_simulation_request`.
- [policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py:1568–1633](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py#L1568-L1633) — `persisted numerical oracle and N8/N9 negatives`.

Трассировка: [`../04_Трассировка/CYC-01.json`](../04_Трассировка/CYC-01.json). Исторические количества «осталось/следующий пакет» из исходных отчётов не являются текущим статусом: этап1 охватил127/127, но это не product completion.

## 12. Точная трассировка исходных obligation IDs

Полная таблица, включая дословные основания, находится в companion JSON и сохранённом аудите. Probes и полные runtime logs остаются в отдельно доставленном phase1 ZIP; файл ТЗ не выдаёт их за новое исполнение.

| Inventory ID | REQ / TEST | Решение |
|---|---|---|
| remaining:0001 | REQ-CYC-01-01, REQ-CYC-01-03, REQ-CYC-01-04 | qualify: Actual HTTP/worker/controller и независимое число, не source-only green. |
| remaining:0002 | REQ-CYC-01-01, REQ-CYC-01-07 | qualify: Отдельный user/server-input census включён в переносимость; скрытая ручная подготовка видима. |
| remaining:0003 | REQ-CYC-01-02 | qualify: Точные post-compile/leaf bindings и changed-binding controls. |
| remaining:0004 | REQ-CYC-01-07 | capability: Второй содержательно иной case и общий resource mechanism. |
| remaining:0005 | REQ-CYC-01-06 | shared: CYC-03 владеет изменением basis/continuation; здесь только историческая неизменность. |
| remaining:0006 | REQ-CYC-01-03, REQ-CYC-01-07 | qualify: Выбор ресурса/горизонта/comparator/budget и owner предъявляются через actual persisted request, не fixtures без disclosure. |
| remaining:0007 | REQ-CYC-01-07 | qualify: В отчёте опыта явно разделены allowed engine labels и выполненные served routes. |
| remaining:0008 | REQ-CYC-01-04, REQ-CYC-01-05 | shared: Численный oracle уже существует; positive N8 у CYC-02, comparator/replications у SIM-03; не считать отсутствие старого read-window отсутствием oracle. |
| preserve:0001 | REQ-CYC-01-01, REQ-CYC-01-05, TEST-CYC-01-01, TEST-CYC-01-02, TEST-CYC-01-05 | preserve: Раздельные ordinary/protected режимы и границы candidate authority. |
| preserve:0002 | REQ-CYC-01-01, TEST-CYC-01-01, TEST-CYC-01-02 | preserve: Explicit None на actual job owner; auth controls остаются. |
| preserve:0003 | REQ-CYC-01-01, TEST-CYC-01-02 | preserve: Actor/tenant/cell, lease/budget controls до использования, не удаление admission. |
| preserve:0004 | REQ-CYC-01-02, TEST-CYC-01-02, TEST-CYC-01-05 | preserve: Точный typed context и problem/WMR/registry/source refs. |
| preserve:0005 | REQ-CYC-01-02, TEST-CYC-01-02, TEST-CYC-01-05 | preserve: Leaf-specific maps/capsules и real consuming owner. |
| preserve:0006 | REQ-CYC-01-05, TEST-CYC-01-03, TEST-CYC-01-05 | preserve: Полезный N4/candidate остаётся при отсутствующей authority. |
| preserve:0007 | REQ-CYC-01-03, TEST-CYC-01-01, TEST-CYC-01-04 | preserve: Existing builder/controller; не новый параллельный request builder. |
| preserve:0008 | REQ-CYC-01-02, REQ-CYC-01-03, TEST-CYC-01-01, TEST-CYC-01-02, TEST-CYC-01-04 | preserve: Настоящие WMR/CAS owners; missing не default zero. |
| preserve:0009 | REQ-CYC-01-03, REQ-CYC-01-04, REQ-CYC-01-06, TEST-CYC-01-01, TEST-CYC-01-04 | preserve: Persisted input/result и fresh reader, immutable history. |
