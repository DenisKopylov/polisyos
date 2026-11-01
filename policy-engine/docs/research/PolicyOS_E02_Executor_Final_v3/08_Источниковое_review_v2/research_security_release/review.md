# Security, trust, release и operations: исследовательская основа review E02

## Полезный результат

Подготовлены **18 условных проверяемых критериев по 20 первичным источникам**. Главная опасность формулировок — подмена одного свойства другим: hash ≠ допустимость; подпись ≠ свежесть; authentication ≠ permission; проверка в начале ≠ разрешённый эффект в конце; valid schema ≠ единая parser-семантика; старый binary ≠ обратимые данные; backup ≠ восстановленный сервис.

**Это ещё не аудит E02.** Ни один критерий не объявляет найденный дефект. Спеки не оценивались, тесты и exploit-сценарии не исполнялись, продукт и исходные спецификации не менялись. Далее адресат проверки: текущий v2 baseline, pinned repository `20d9009be21097bfbdc38a546a15cc60213b8ace`, 127 packets, 12 lanes, 38 + 4 scenarios. Количество — ожидаемый объём следующей фазы, не проверенный здесь результат.

## Границы применения

- Все выводы для E02 ниже — **аналитические review-критерии**, а не перенос нормативного MUST из другого домена. Требуется сначала доказать applicability trigger.
- Нельзя требовать новую security platform, ASVS level, SLSA level, TUF adoption, SIEM, HSM, отдельную БД на tenant или canary только потому, что они встречаются в источниках.
- Исторический replay закреплённого baseline и новое operational разрешение — разные режимы. Старая версия может быть правильной для первого и запрещённой для второго.
- Evidence имеет минимум три слоя: (1) явный контракт, (2) реализация/статические свидетельства, (3) наблюдаемый эксперимент. Текст и fixture не доказывают исполнение.
- Для каждой применимой строки последующей матрицы нужны: точный packet/lane/path/section, цитата спорной формулировки, counterexample, positive/negative oracle, доступные evidence и остаточная неопределённость.
- Рекомендуемые статусы: NOT_APPLICABLE с причиной; SPEC_CONTRACT_PRESENT; SPEC_GAP/CONTRADICTION; IMPLEMENTATION_NOT_CHECKED; TEST_NOT_RUN; OBSERVED_PASS/FAIL только с реально полученным результатом. Отсутствие evidence не равно найденной уязвимости.

SSDF прямо предусматривает риск-ориентированную адаптацию вместо универсального checklist ([NIST SP 800-218, §2](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf)).

## Критерии для следующей фазы

### SR-01. Gate проверяет свойство, а не наличие файла или количество тестов

**Триггер:** Пакет или lane объявляет security/release gate, PASS, evidence или coverage.

**Неверная формулировка:** «Есть test_report.json и все обязательные ключи — релиз безопасен».
**Контрпример:** Набор содержит 127 syntactically valid отчётов, но каждый проверяет только собственный happy path; отсутствует запрещённый cross-packet переход.

**Критерий (аналитический вывод):** Выделить независимые уровни: полнота перечня, смысл oracle, связь с target revision, реально исполненный тест. Ни один уровень не заменяет следующий.

**Положительные свидетельства:**
- В спеке указаны проверяемый инвариант, scope, oracle и конкретные свидетельства PASS.
- Тест с разрешённым входом действительно достигает полезного эффекта; evidence указывает fixture, verifier и target.

**Отрицательные свидетельства / ожидаемые проверки:**
- Для каждого выбранного gate есть контрпример, нарушающий ровно соответствующее свойство и отвергаемый по ожидаемой причине.
- Пустой/неполный/устаревший/от другого target отчёт не становится PASS.

**Минимум контракта:** Property + trigger + expected allow/deny/effect + artifact identity + evidence source + missing-evidence outcome.
**Интеграция:** Нужны межпакетные цепочки для границ, которые не наблюдаемы локальным unit test.
**Пределы:** Требование review-методики; отсутствие runtime evidence означает NOT_TESTED, а не доказанную уязвимость. SSDF не требует 127 security suites или тотального pentest.
**Компромисс:** Дорогие проверки концентрируются на активных trust boundaries; общий тест допустим при явной трассировке применимости.

**Основание:** [SR-S01: NIST SP 800-218 — SSDF](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf), PO.4.1–PO.4.2; PW.8.1–PW.8.2; [SR-S18: OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), Create Unit and Integration Test Cases.

### SR-02. Целостность, ожидаемая идентичность и доверие к происхождению различаются

**Триггер:** Передача/release/исполнение артефактов, manifest, provenance, подписанных отчётов или derived assets.

**Неверная формулировка:** «SHA совпал / подпись валидна — использовать можно».
**Контрпример:** Правильно подписанный артефакт собран из неразрешённого fork; или digest относится к JSON summary, а исполняется другой blob по mutable URL.

**Критерий (аналитический вывод):** Проверять, какие именно bytes/семантический объект связаны с evidence, и отдельно — ожидаемые source, builder, параметры и authority. Trust policy не может быть произвольно выбрана самим объектом.

**Положительные свидетельства:**
- Разрешённый источник/процесс/параметры и точный consumable artifact проходят цепочку проверки.
- Записаны происхождение trust configuration и её версия.

**Отрицательные свидетельства / ожидаемые проверки:**
- Подмена subject digest, builder, repository или существенного parameter отклоняется независимо.
- Замена артефакта после publication-time verification выявляется у точки потребления или исключается доказанным immutable handoff.

**Минимум контракта:** Exact object identity; trust root/expectations; verifier decision; authorized use; binding до потребления.
**Интеграция:** Проверить producer → transport/store → consumer, а не только генератор manifest.
**Пределы:** SLSA adoption, конкретный level, подпись каждого внутреннего файла и новый registry не требуются. Проверенный provenance не доказывает корректность или отсутствие уязвимостей.
**Компромисс:** Полная provenance дороже простого authenticated immutable handoff; выбирается граница, соответствующая источнику риска.

**Основание:** [SR-S03: SLSA — Build: Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts), Steps 1–2; Forming Expectations; [SR-S01: NIST SP 800-218 — SSDF](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf), PS.2.1; PS.3.1.

### SR-03. Свежесть допуска отдельно от воспроизводимости старого snapshot

**Триггер:** Используются allowlists, release channels, policy/approval versions, expiry или обещание «актуально».

**Неверная формулировка:** «Любой ранее подписанный bundle допустим» либо «любой старый snapshot недействителен».
**Контрпример:** Сохранённый snapshot нужен для исторического replay, но его давно отозванный approval ошибочно разрешает новое production действие.

**Критерий (аналитический вывод):** Развести историческую проверку as-of фиксированного времени/версии и текущий operational admit. Для второго определить источник свежести и правила устаревания/отзыва.

**Положительные свидетельства:**
- Исторический snapshot воспроизводится в заявленном read-only режиме без выданного права на новое действие.
- Current admit использует ожидаемую policy/version и авторизованный rollback при необходимости.

**Отрицательные свидетельства / ожидаемые проверки:**
- Просроченный или отозванный approval не даёт новый admit даже с корректным hash/signature.
- Смешанные версии policy/metadata и потеря freshness source дают явно заданный исход, не скрытый PASS.

**Минимум контракта:** As-of vs current mode; version/time authority; allowed staleness; revocation; authorized rollback path.
**Интеграция:** Связать approval producer, очередь, consumer и release gate на одной проверяемой временной шкале.
**Пределы:** TUF защищает update metadata, не любую бизнес-авторизацию. Нельзя автоматически запрещать исторические данные; обычный rollback релиза не равен атаке rollback metadata.
**Компромисс:** Offline availability конфликтует с мгновенным отзывом: нужен явно ограниченный stale window или отказ, а не обещание обоих без механизма.

**Основание:** [SR-S04: The Update Framework Specification](https://theupdateframework.github.io/specification/v1.0.36/), §5.1; §5.3–5.5; §5.7; [SR-S03: SLSA — Build: Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts), Forming Expectations.

### SR-04. TOCTOU: решение связано с фактически использованным объектом и действующими правами

**Триггер:** Между validate/approve и read/execute/commit возможны задержка, конкурентная запись, alias swap или отзыв прав.

**Неверная формулировка:** «Проверить права и hash в начале, затем исполнить; быстрый retry закрывает race».
**Контрпример:** В t0 разрешены revision A и роль редактора; до t1 alias указывает на B или роль отозвана; эффект всё равно совершается.

**Критерий (аналитический вывод):** Спека должна назвать точку, в которой связываются решение, resource identity/version и эффект, и механизм против инвалидирующего interleaving.

**Положительные свидетельства:**
- Без изменений разрешённая операция завершается с тем target, который проверялся.
- При допустимом concurrent update оговорён retry/revalidation или version conflict.

**Отрицательные свидетельства / ожидаемые проверки:**
- Контролируемая пауза между check/use, затем resource replacement или revocation: новый запрещённый эффект/раскрытие не происходит.
- Проверка «после» не объявлена достаточной защитой от уже выданного секрета.

**Минимум контракта:** Decision binding + validity window + invalidation + conflict behavior + effect boundary.
**Интеграция:** Негативный interleaving важен через очередь/adapter/consumer, не только внутри функции проверки.
**Пределы:** Не каждое immutable local read требует распределённой транзакции. Конкретная реализация atomic/CAS/lock/lease выбирается отдельно; уменьшение окна не доказательство отсутствия race.
**Компромисс:** Сильный fencing стоит latency/availability; при bounded stale праве размер окна должен соответствовать риску.

**Основание:** [SR-S12: MITRE CWE-367 — Time-of-check Time-of-use Race Condition](https://cwe.mitre.org/data/definitions/367.html), Description; Potential Mitigations; [SR-S02: OWASP ASVS — V8 Authorization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x17-V8-Authorization.md), 8.3.2.

### SR-05. Authorization покрывает функцию, существующий чужой объект и защищённые поля

**Триггер:** Есть разные субъекты, roles, ownership или частично доступные поля/операции.

**Неверная формулировка:** «Пользователь аутентифицирован; неизвестный ID возвращает 404; UI скрывает кнопку».
**Контрпример:** Два пользователя имеют одну роль; оба знают существующие object IDs. Второй может экспортировать чужой объект или записать закрытое поле через альтернативный endpoint.

**Критерий (аналитический вывод):** Проверять authority в доверенной точке для точной операции/объекта/поля; тест чужого объекта должен использовать существующий объект и заведомо различимые разрешения.

**Положительные свидетельства:**
- Разрешённый субъект читает/меняет ровно допустимые объект и поля.
- Публичный ресурс остаётся доступным согласно контракту.

**Отрицательные свидетельства / ожидаемые проверки:**
- Анонимный, logged-out, другой owner той же роли и недостаточная роль не достигают запретного результата.
- Отказ проверяется по состоянию/раскрытию данных, а не только HTTP status.

**Минимум контракта:** Subject × operation × resource × fields × context; trusted enforcement; observable allow/deny outcome.
**Интеграция:** Одинаковая политика для direct API, export/import, batch и adapter путей, если они присутствуют.
**Пределы:** Не требуются RBAC, ABAC, UI или web endpoints, если их нет. Не каждый 404 означает security defect; oracle учитывает сознательное сокрытие существования.
**Компромисс:** Подробные ошибки удобнее диагностики, но раскрывают ownership/existence; внутренний audit и внешний ответ могут различаться.

**Основание:** [SR-S02: OWASP ASVS — V8 Authorization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x17-V8-Authorization.md), 8.1.1–8.2.3; 8.3.1; [SR-S10: OWASP WSTG — Testing for Bypassing Authorization Schema](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/05-Authorization_Testing/02-Testing_for_Bypassing_Authorization_Schema/), Summary; Horizontal testing; [SR-S11: OWASP WSTG — Testing for Insecure Direct Object References](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References/), How to Test.

### SR-06. Делегирование не подменяет права пользователя привилегиями посредника

**Триггер:** Сервис, worker, агент или adapter действует от имени субъекта либо выполняет явно системную операцию.

**Неверная формулировка:** «Внутренний сервис доверенный; его machine token разрешает всё downstream».
**Контрпример:** Непривилегированный пользователь вызывает экспорт; посредник с широкими полномочиями выгружает ресурс, недоступный исходному пользователю.

**Критерий (аналитический вывод):** Контракт различает originating principal, intermediary и system authority; явно задаёт, чьи права ограничивают эффект и какую scope можно делегировать.

**Положительные свидетельства:**
- Разрешённый delegated request сохраняет достаточный проверенный контекст до конечного ресурса.
- Независимая системная задача имеет собственное явно разрешённое назначение и scope.

**Отрицательные свидетельства / ожидаемые проверки:**
- Недостаточное исходное право не становится достаточным из-за широкого service account.
- Подмена subject/delegation или отсутствие обязательного контекста не создаёт default superuser.

**Минимум контракта:** Principal origin; authority basis; delegation scope/audience; downstream enforcement; missing-context outcome.
**Интеграция:** Нужен тест полного пути caller → intermediary → final resource.
**Пределы:** Не требуется передавать пользовательский bearer token повсюду; возможны ограниченные capabilities/проверенная delegation. Глобальные system jobs не нужно искусственно изображать пользователем.
**Компромисс:** Передача end-user credentials расширяет поверхность утечки; суженный проверяемый контекст сложнее, но уменьшает полномочия.

**Основание:** [SR-S02: OWASP ASVS — V8 Authorization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x17-V8-Authorization.md), 8.3.3; [SR-S18: OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), Enforce Least Privileges.

### SR-07. Tenant isolation распространяется на cache, jobs, blobs и дедупликацию

**Триггер:** Данные/права/эффекты различаются по tenant или namespace в разделяемой инфраструктуре.

**Неверная формулировка:** «tenant_id есть в JSON и SQL; следовательно все пути изолированы».
**Контрпример:** Два tenant используют одинаковый local ID или idempotency key; кэш, retry/DLQ или экспорт возвращает результат соседа.

**Критерий (аналитический вывод):** Определить verified context и его scope во всех tenant-sensitive shared state; client selector не заменяет permission. Явные global/cross-tenant данные допустимы только по отдельной модели.

**Положительные свидетельства:**
- Одинаковые локальные IDs в двух tenants дают независимые результаты и effects.
- Разрешённый global asset остаётся осознанно общим.

**Отрицательные свидетельства / ожидаемые проверки:**
- Подмена tenant selector, потеря context при dequeue, общий cache key или чужой blob не дают утечку/эффект.
- Delayed job учитывает изменение time-sensitive membership согласно контракту.

**Минимум контракта:** Scope classification + verified context + key namespaces + storage/async enforcement + explicit global exceptions.
**Интеграция:** Проверить crossing request → queue/cache/store → export/consumer.
**Пределы:** Не требуются отдельная DB, очередь или криптоключ для каждого tenant. Применять только к реально tenant-scoped state.
**Компромисс:** Физическая изоляция дороже; общая инфраструктура допустима, но границы и шумный сосед нуждаются в проверке.

**Основание:** [SR-S19: OWASP Multi-Tenant Application Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html), §1; §4; §5 asynchronous work; §6; [SR-S02: OWASP ASVS — V8 Authorization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x17-V8-Authorization.md), 8.4.1.

### SR-08. Один payload имеет одну security-семантику на всех parser/interpreter границах

**Триггер:** Входные JSON/XML/URI/path/manifest проходят несколько decoders, validators или interpreters.

**Неверная формулировка:** «Payload прошёл JSON schema; любые дальнейшие parse/normalization безопасны».
**Контрпример:** Validator видит первое одноимённое поле allow=false, consumer — последнее allow=true; либо percent-decoding после проверки меняет значение пути.

**Критерий (аналитический вывод):** Зафиксировать grammar/version/encoding, decode order, неоднозначности и limits. Raw ambiguity не исчезает от schema validation уже потерявшего дубликаты объекта.

**Положительные свидетельства:**
- Допустимый encoding и representative boundary values дают одинаковое canonical meaning у verifier и consumer.

**Отрицательные свидетельства / ожидаемые проверки:**
- Duplicate security-relevant fields, unsupported forms, malformed encoding и divergent parsing либо явно отвергаются, либо имеют доказанно одинаковую безопасную семантику.
- Контекстно опасное значение остаётся данными в используемом sink.

**Минимум контракта:** Accepted bytes/types + normalization order + ambiguity policy + parser agreement + resource bounds.
**Интеграция:** Тестировать те же bytes на input validator, signer/verifier и фактическом consumer.
**Пределы:** RFC 8259 не делает reject-duplicates универсальным MUST; это рекомендуемое разрешение ambiguity для security-sensitive контракта. Никакие malicious payloads не исполнялись.
**Компромисс:** Строгий parser снижает ambiguity, но может ломать legacy producers; tolerant intake допустим только с единым нормализованным представлением.

**Основание:** [SR-S05: OWASP ASVS — V1 Encoding and Sanitization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x10-V1-Encoding-and-Sanitization.md), 1.1.1–1.1.2; 1.5.1–1.5.3; [SR-S13: IETF RFC 8259 — JSON Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259), §4; §6; §8.1; §9.

### SR-09. Валидные поля не означают допустимую комбинацию и ограниченную работу

**Триггер:** Есть связанных input fields, workflow state, batch/fan-out, лимитируемые ресурсы или внешние зависимости.

**Неверная формулировка:** «Проверить типы; retry до успеха; batch_size — положительное число».
**Контрпример:** Каждый параметр допустим, но вместе depth×fan-out×retries создаёт неограниченную работу; action и target state противоречат друг другу.

**Критерий (аналитический вывод):** Указать cross-field invariants и бюджет на весь operation, не только отдельный запрос. Порядок шагов и частичный эффект должны иметь oracle.

**Положительные свидетельства:**
- Граничный допустимый объём и согласованная комбинация завершаются с нужным результатом.
- Задержка зависимости укладывается в обещанный общий deadline/resource bound.

**Отрицательные свидетельства / ожидаемые проверки:**
- Несогласованные поля, skipped state, превышение aggregate limit или exhaustion дают определённый отказ/partial outcome без запрещённого эффекта.

**Минимум контракта:** Cross-field rules; allowed state transitions; aggregate timeout/resource budget; partial-result contract.
**Интеграция:** Локальный лимит должен композиционно ограничивать fan-out и повторения всего lane.
**Пределы:** Не вводятся произвольные числа, CAPTCHAs или квоты для offline pure function. Пределы выводятся из заявленной нагрузки/риска.
**Компромисс:** Низкие лимиты снижают доступность для легитимного bulk; high limits увеличивают стоимость и blast radius.

**Основание:** [SR-S06: OWASP ASVS — V2 Validation and Business Logic](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x11-V2-Validation-and-Business-Logic.md), 2.1.1–2.2.3; 2.3.1–2.3.4; 2.4.1; [SR-S07: OWASP ASVS — V13 Configuration](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x22-V13-Configuration.md), 13.1.2–13.1.3.

### SR-10. Диагностика и evidence не становятся каналом секретов

**Триггер:** Обрабатываются secrets, session credentials, sensitive tenant data; создаются logs, exports, test artifacts или release bundles.

**Неверная формулировка:** «Для воспроизводимости приложить полный request/env; Base64 безопасно; секрет вырезан из UI».
**Контрпример:** Секрет отсутствует в UI, но присутствует в generated manifest, exception trace, cache snapshot или приложенном fixture.

**Критерий (аналитический вывод):** Классификация данных должна действовать на весь жизненный цикл derived artifacts, включая failure paths; воспроизводимость не оправдывает раскрытие.

**Положительные свидетельства:**
- Минимальные синтетические/редактированные evidence воспроизводят диагноз без реальных секретов.
- Авторизованная операция получает нужный секрет по предусмотренной границе.

**Отрицательные свидетельства / ожидаемые проверки:**
- Canary marker вместо секрета не обнаруживается в запрещённых output/log/build/export каналах после success и failure.
- Недостаточно привилегированный reader не видит чувствительные evidence.

**Минимум контракта:** Data classes; allowed sinks/readers; redaction; retention; secret lifecycle; negative-path assertions.
**Интеграция:** Проверка должна охватывать упаковку и выдачу итогового артефакта, не только runtime response.
**Пределы:** Нет требования нового secrets platform или HSM. Проверять лишь реально секретные классы, а не скрывать полезные несекретные IDs/diagnostics.
**Компромисс:** Редакция снижает диагностическую полноту; correlation IDs и controlled restricted evidence сохраняют полезность без массового раскрытия.

**Основание:** [SR-S07: OWASP ASVS — V13 Configuration](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x22-V13-Configuration.md), 13.1.4; 13.3.1; [SR-S08: OWASP ASVS — V14 Data Protection](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x23-V14-Data-Protection.md), 14.1.1–14.2.4; [SR-S09: OWASP ASVS — V16 Security Logging and Error Handling](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md), 16.2.5; 16.5.1.

### SR-11. Отказ зависимости не превращается в разрешение; отсутствие результата не равно запрету

**Триггер:** Внешний policy service/verifier/storage/connector влияет на разрешение или завершение операции.

**Неверная формулировка:** «При недоступности проверки продолжить по умолчанию» или «любой timeout означает rejected/no effect».
**Контрпример:** Policy lookup timeout интерпретирован как отсутствующее deny правило; effect выполняется. В другом случае effect произошёл, но потерянный ответ ошибочно отмечен как гарантированно неисполненный.

**Критерий (аналитический вывод):** Разделять security decision и execution outcome. Degraded mode заранее ограничен разрешёнными безопасными действиями; unknown evidence не превращается в PASS.

**Положительные свидетельства:**
- При доступной зависимости разрешённое действие выполняется.
- Документированный degraded read-only или иной допустимый режим сохраняет свои границы.

**Отрицательные свидетельства / ожидаемые проверки:**
- Ошибка/exception обязательной проверки не даёт allow.
- Timeout после отправки даёт UNKNOWN/PENDING и предусмотренный reconciliation, не автоматический новый effect.

**Минимум контракта:** Dependency failure taxonomy; admissible degraded actions; evidence absence handling; execution outcome states.
**Интеграция:** Интеграционный отказ нужен в adapter/check/commit точках, не только mock возвращающий false.
**Пределы:** Fail-closed не означает остановку всего продукта при любой ошибке. Конкретные retry и outcome semantics зависят от API, а не от общего лозунга безопасности.
**Компромисс:** Строгая проверка снижает availability; разрешённый cache/stale режим требует отдельной риск-модели.

**Основание:** [SR-S09: OWASP ASVS — V16 Security Logging and Error Handling](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md), 16.5.2–16.5.3; [SR-S07: OWASP ASVS — V13 Configuration](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x22-V13-Configuration.md), 13.1.2–13.1.3; 13.2.6.

### SR-12. Совместимость old/new readers и writers проверяется во время rollout

**Триггер:** Меняются persistent/wire formats, schema, defaults, heartbeat/timeout protocol; версии могут сосуществовать или выполняться rollback.

**Неверная формулировка:** «Новая версия читает старые данные; миграция обратно совместима».
**Контрпример:** Новый writer сохраняет формат N+1; старый reader ещё работает или возвращается после rollback и не может прочесть новые записи.

**Критерий (аналитический вывод):** Зафиксировать направленную матрицу чтения/записи/протокола для реальных mixed states, а не один happy-path upgrade.

**Положительные свидетельства:**
- Доказаны поддерживаемые комбинации old writer→new reader, new writer→old reader/bridge и работа mixed fleet.
- Readiness всех нужных readers подтверждена перед activation нового writer.

**Отрицательные свидетельства / ожидаемые проверки:**
- Ранняя activation при одном старом reader, rollback после новой записи и delayed old worker выявляют несовместимость или безопасно блокируются.

**Минимум контракта:** Version matrix; writer activation barrier; supported downgrade floor; delayed clients; completion proof.
**Интеграция:** Нужен mixed-version lane scenario со state, произведённым обеими версиями.
**Пределы:** Полная all-to-all совместимость не обязательна: допустим coordinated downtime, read-only migration или bridge, если это явно согласовано. AWS two-phase — вариант, не mandate.
**Компромисс:** Prepare/activate требует дополнительных этапов; downtime проще, но уменьшает доступность. Продолжительность rollback window влияет на хранение совместимости.

**Основание:** [SR-S14: AWS Builders’ Library — Ensuring rollback safety during deployments](https://builder.aws.com/content/3F04j2yRAAMBuPSPs50xwXZqg01/ensuring-rollback-safety-during-deployments), Standalone vs distributed; Problems with protocol changes; Two-phase deployment.

### SR-13. Rollback описывает данные и внешние эффекты, а не только старый binary

**Триггер:** Релиз обещает rollback/reversibility после migration, deletion, export или другого внешнего эффекта.

**Неверная формулировка:** «Откат: вернуть предыдущий контейнер/commit».
**Контрпример:** Старый binary стартовал, но column удалён, записи преобразованы необратимо или внешний получатель уже получил данные.

**Критерий (аналитический вывод):** Разделить code rollback, data recovery, compensation и forward-fix. Назвать last reversible point, доступные состояния и последствия после пересечения границы.

**Положительные свидетельства:**
- После реальной новой записи возврат в разрешённую версию сохраняет нужные данные и инварианты.
- Операционная инструкция проверяет восстановление сервиса, а не лишь exit code deployment.

**Отрицательные свидетельства / ожидаемые проверки:**
- Сбой до/после irreversible step, прерванная backfill и частичное восстановление имеют определённый stop/recovery path.
- Невозможная компенсация disclosure/deletion не маскируется фразой «полностью обратимо».

**Минимум контракта:** Reversible boundary; code/data/effect separation; loss budget; stop conditions; owner; recovery acceptance.
**Интеграция:** Проверить rollback после каждого реально важного промежуточного состояния lane.
**Пределы:** Не все изменения должны быть обратимыми. Допустимый необратимый шаг требует честного ограничения и отдельного согласования, а не автоматического запрета.
**Компромисс:** Хранение старых форматов/данных облегчает rollback, но увеличивает стоимость и может конфликтовать с retention; forward recovery иногда безопаснее downgrade.

**Основание:** [SR-S14: AWS Builders’ Library — Ensuring rollback safety during deployments](https://builder.aws.com/content/3F04j2yRAAMBuPSPs50xwXZqg01/ensuring-rollback-safety-during-deployments), Problems with protocol changes; Two-phase deployment; [SR-S16: Google SRE Book — Data Integrity: What You Read Is What You Wrote](https://sre.google/sre-book/data-integrity/), Backups Versus Archives; Third Layer.

### SR-14. Canary/rollout gate имеет наблюдаемую когорту и не считает тишину успехом

**Триггер:** Спека обещает canary, gradual rollout или автоматическую promotion по telemetry.

**Неверная формулировка:** «За пять минут общий error rate не вырос — продолжать».
**Контрпример:** Canary получает мало запросов; её 50% ошибок растворяются в общем metric; failed telemetry возвращает пустой набор, трактуемый как 0 errors.

**Критерий (аналитический вывод):** Определить cohort/control, релевантные signals, достаточность наблюдения и отдельный inconclusive исход. Решение должно реально менять progression.

**Положительные свидетельства:**
- Здоровый candidate с представительной нагрузкой проходит заявленный oracle.
- Candidate/control различимы, и проверено влияние gate на promotion.

**Отрицательные свидетельства / ожидаемые проверки:**
- Управляемый bad candidate на малой когорте останавливает progression.
- Нет трафика/telemetry, contaminated control или явно недостаточная выборка не дают автоматический PASS.

**Минимум контракта:** Cohort; control; signals; observation adequacy; pass/fail/inconclusive; pause/rollback authority.
**Интеграция:** Интеграционная проверка касается telemetry → evaluator → rollout actuator, а не одного dashboard.
**Пределы:** Canary не обязателен offline артефакту и не заменяет security/data-migration tests. Фиксированные минуты/проценты из примеров не копируются.
**Компромисс:** Длинная репрезентативная оценка замедляет releases; короткая увеличивает false negatives. Цена ошибки определяет допустимый объём эксперимента.

**Основание:** [SR-S15: Google SRE Workbook — Canarying Releases](https://sre.google/workbook/canarying-releases/), Requirements; per-version comparison; Choosing population/duration.

### SR-15. Восстановление заканчивается доступными согласованными данными в RTO/RPO

**Триггер:** Есть persistent state и обещанные backup/recovery/SLO/continuity свойства.

**Неверная формулировка:** «Backup создан, checksum совпал, restore command завершился — recovery PASS».
**Контрпример:** Файлы восстановлены, но индексы, metadata или ключи недоступны; пользователи не могут прочесть данные. Snapshot нескольких stores относится к несовместимым моментам.

**Критерий (аналитический вывод):** Определить what recovered означает для пользователя и бизнес-инвариантов, отдельно допустимые downtime и data-loss point; проверить зависимости и post-restore validation.

**Положительные свидетельства:**
- Репетиция на репрезентативном объёме восстанавливает чтение/запись и связи в пределах принятых целей.
- Проверены доступность ключей, конфигурации и необходимых зависимостей.

**Отрицательные свидетельства / ожидаемые проверки:**
- Повреждённый/неполный backup, отсутствующая зависимость или несовместимые snapshots не получают recovery PASS.
- Измерен ожидаемый проигрыш при неполном восстановлении; потерянный диапазон данных явно сообщён.

**Минимум контракта:** Recovery scope; data dependencies; RTO/RPO; accessible keys; validation oracle; accepted partial recovery.
**Интеграция:** Проверять consumer-visible восстановление всего нужного набора stores, не только одного storage adapter.
**Пределы:** Никакие RTO/RPO, георегионы или федеральные процедуры не навязаны. Для полностью пересоздаваемого состояния достаточно доказанного rebuild, не обязательного backup.
**Компромисс:** Частые независимые backups дороже; recovery validation и объём определяют реальный RTO, который не следует из расписания копирования.

**Основание:** [SR-S17: NIST SP 800-34 Rev. 1 — Contingency Planning Guide](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-34r1.pdf), §3.2.1; §3.5; §4.4; [SR-S16: Google SRE Book — Data Integrity: What You Read Is What You Wrote](https://sre.google/sre-book/data-integrity/), Delivering Recovery System; 1T vs 1E; recovery case studies.

### SR-16. Restore не воскресит отозванный доступ и не смешает tenant data

**Триггер:** Backup содержит ACL/membership/secrets/approvals либо совместные данные нескольких tenants.

**Неверная формулировка:** «Вернуть backup целиком в live и считать restored state доверенным».
**Контрпример:** Участник удалён после backup; восстановление старой membership возвращает доступ. Tenant-specific recovery случайно копирует соседние записи.

**Критерий (аналитический вывод):** Разделить восстановление содержимого и текущую authority/retention policy; восстановленные данные проходят сегодняшние разрешения перед доступностью.

**Положительные свидетельства:**
- Авторизованный operator восстанавливает именно нужный scope; необходимые данные доступны тем, кому разрешены сейчас.

**Отрицательные свидетельства / ожидаемые проверки:**
- Отозванный user/approval/secret не оживает; чужие tenant rows не копируются в целевой live scope.
- Restore из устаревшего backup не отменяет предусмотренные удаления/retention без отдельного разрешённого решения.

**Минимум контракта:** Restore data scope vs current security state; ownership validation; revocation/retention reapplication; isolated staging.
**Интеграция:** Нужен путь backup → staging → revalidation → live exposure.
**Пределы:** Не каждая система multi-tenant и не каждый backup содержит authority. Для исторической экспертизы старые ACL могут храниться как данные, не как действующие права.
**Компромисс:** Точная историческая реконструкция конфликтует с текущим доступом; безопасное решение — отдельный ограниченный forensic режим, а не silent overwrite.

**Основание:** [SR-S19: OWASP Multi-Tenant Application Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html), §7 Tenant Backup Restore; [SR-S02: OWASP ASVS — V8 Authorization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x17-V8-Authorization.md), 8.3.2; 8.4.1.

### SR-17. Audit/evidence защищены от подмены и достаточно точны для решения

**Триггер:** Audit log, approval/evidence record или test result используются для допуска, расследования или доказательства результата.

**Неверная формулировка:** «Логировать JSON» либо «есть event=success, значит эффект завершён».
**Контрпример:** Непроверенный input содержит перевод строки/поддельный event; record от другого target/revision принят за доказательство; denial и unknown записаны как одинаковый generic failure.

**Критерий (аналитический вывод):** Задать meaning, binding и доверенный producer каждого security/release event, а также защиту от неавторизованной записи/чтения. Лог намерения не равен свидетельству эффекта.

**Положительные свидетельства:**
- Событие привязано к actor, target, operation, revision/correlation и фактическому outcome; investigator различает этапы.

**Отрицательные свидетельства / ожидаемые проверки:**
- Forged/untrusted event, изменённый/неполный record, неправильный target или log injection не становятся валидным evidence.
- Проверка failure path не записывает секреты.

**Минимум контракта:** Event semantics; identity/revision binding; trust/permissions; integrity; retention; incomplete-evidence handling.
**Интеграция:** Трассировка должна соединять решение, adapter attempt и конечный эффект без смешения этих стадий.
**Пределы:** Не обязательны блокчейн, WORM, SIEM или отдельная audit platform. Не гарантируется абсолютная неотказуемость при полном компромиссе trusted producer.
**Компромисс:** Больше логов повышает стоимость/риск утечки; минимальный набор определяется реальными решениями и расследованием.

**Основание:** [SR-S09: OWASP ASVS — V16 Security Logging and Error Handling](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md), 16.1.1; 16.2.1–16.2.5; 16.3; 16.4; [SR-S01: NIST SP 800-218 — SSDF](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf), PO.4.2; PS.3.1.

### SR-18. Неизвестный результат внешнего действия не лечится новым намерением

**Триггер:** Deploy/release/migration/connector операция мутирует внешнее состояние и допускает timeout/retry/resume.

**Неверная формулировка:** «Любая ошибка — повторить с новым request ID»; «тот же payload всегда тот же запрос».
**Контрпример:** Commit выполнен, ответ потерян; повтор создаёт второй объект. Или поздний retry воскрешает уже отменённый ресурс после истечения dedup window.

**Критерий (аналитический вывод):** Разделить намерение и попытки, проверить сервисный idempotency contract и окно его действия; при неопределённости использовать предусмотренную сверку результата, не изобретать новый effect.

**Положительные свидетельства:**
- Одна разрешённая операция и её безопасный повтор приводят к одному ожидаемому эффекту и понятному результату.

**Отрицательные свидетельства / ожидаемые проверки:**
- Потерянный response после commit, concurrent retry, поздний retry и тот же key с другим intent не дают дубликат/ложный success.
- Отозванная/отклонённая авторизация не превращается в transient retry.

**Минимум контракта:** Intent identity/scope; attempt identity; durable effect binding; retry window; parameter mismatch; reconciliation; terminal outcomes.
**Интеграция:** Сбой моделируется на границе effect committed / response lost у конечного adapter.
**Пределы:** Оговорённый серверный контракт важнее названия header. Idempotency не равно exactly-once всех побочных эффектов и не расширяет authority; запрещённые действия не повторяются по этому критерию.
**Компромисс:** Долгое хранение dedup state дорого; после его expiry нужен явный безопасный outcome. Read-only операции обычно проще.

**Основание:** [SR-S20: AWS Builders’ Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/), Retrying and side effects; semantic equivalence; late requests; different intent.

## Как не получить ложный PASS при проверке 127 packets и lanes

1. Сначала составить перечень точек authority, parser, store/transport, side effect и recovery из самой спек-системы; не предполагать, что в ней есть все перечисленные технологии.
2. Для каждого packet заполнить applicability по этим критериям; shared control может ссылаться на один владеющий контракт, но consumer должен явно полагаться на его гарантию.
3. На уровне lane искать composition gaps: проверил producer — исполнил consumer; tenant ушёл в cache/job; версия сменилась в пути; rollback пересёк новую запись; backup восстановил старые права.
4. Положительный тест нужен против тривиального «всё запрещать». Отрицательный — против тривиального «формат корректен, значит разрешить». Отдельно проверять действительный запрещённый target, не только отсутствующий.
5. При later execution сохранять exact target/version, fixture, oracle, наблюдаемый outcome и среду. Не принимать log intended success, выход генератора или число сценариев за результат проверки.
6. При недостаточных правах/данных остановить зависимую проверку, назвать точное действие/цель/причину и outcome: denied, pending либо uncertain. Timeout уже отправленного действия не доказывает отсутствие эффекта.

## Реестр прочитанных источников

Дата доступа ко всем источникам: **2026-11-01 UTC**. `null` в JSON означает, что календарная дата источника не установлена, а не что её нет. Для living documents закреплён только момент чтения, не commit.

### SR-S01. NIST SP 800-218 — SSDF
- URL: [NIST SP 800-218 — SSDF](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf)
- Версия: 1.1, Final; дата: 2022-02; доступ: 2026-11-01.
- Прочитано: §2, печ. с. 3 (PDF page 12): risk-based tailoring; PO.4.1–PO.4.2, печ. с. 8 (PDF page 17); PS.2.1, PS.3.1–PS.3.2, печ. с. 10 (PDF page 19); PW.8.1–PW.8.2, печ. с. 15 (PDF page 24).
- Вывод источника: Критерии security checks и их свидетельства задаются заранее; тесты имеют scope и результаты; целостность и архив релиза — отдельные задачи. SSDF прямо не является универсальным checklist.
- Ограничения: Прочитаны релевантные страницы через извлечение PDF-текста; документ целиком не проверялся. Notional examples не превращены в обязательные способы реализации.

### SR-S02. OWASP ASVS — V8 Authorization
- URL: [OWASP ASVS — V8 Authorization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x17-V8-Authorization.md)
- Версия: 5.0.0, tag v5.0.0; дата: 2025-05; доступ: 2026-11-01.
- Прочитано: 8.1.1–8.1.4; 8.2.1–8.2.4; 8.3.1–8.3.3; 8.4.1.
- Вывод источника: Функция, объект, поле, исходный субъект и tenant являются разными границами доступа. Компенсация после отзыва прав не устраняет уже совершённое раскрытие данных.
- Ограничения: Версия закреплена tag; месяц выпуска подтверждён страницей проекта. Конкретный ASVS level для E02 не установлен; требования L2/L3 не объявляются глобально обязательными.

### SR-S03. SLSA — Build: Verifying artifacts
- URL: [SLSA — Build: Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts)
- Версия: 1.2, Approved; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: How to verify; Step 1: Check SLSA Build level; Step 2: Check expectations; Forming Expectations; Architecture options.
- Вывод источника: Подпись provenance, digest subject и заранее доверенные builder/repository/build parameters проверяются раздельно. Проверка только в registry не покрывает последующую подмену у потребителя.
- Ограничения: Страница versioned и Approved; календарная дата публикации на прочитанной странице не указана. Build L3 не гарантирует честность самой build platform и не доказывает отсутствие дефектов.

### SR-S04. The Update Framework Specification
- URL: [The Update Framework Specification](https://theupdateframework.github.io/specification/v1.0.36/)
- Версия: 1.0.36; дата: 2026-08-05; доступ: 2026-11-01.
- Прочитано: §1.1 Scope; §1.4 Non-goals; §5.1 fixed update start time; §5.3 root rotation; §5.4 timestamp rollback/freeze checks; §5.5 snapshot binding; §5.7 Fetch target; §6.1 key management.
- Вывод источника: Действительная подпись сама по себе не исключает replay старых metadata или mix-and-match; target связан с проверенными metadata и digest.
- Ограничения: Стандарт именно для update systems; перенос на approvals/policies — ограниченная аналогия, не требование внедрить TUF. Freshness зависит от модели доверенного времени и доступности metadata.

### SR-S05. OWASP ASVS — V1 Encoding and Sanitization
- URL: [OWASP ASVS — V1 Encoding and Sanitization](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x10-V1-Encoding-and-Sanitization.md)
- Версия: 5.0.0; дата: 2025-05; доступ: 2026-11-01.
- Прочитано: 1.1.1–1.1.2; 1.2.1–1.2.5; 1.3.6; 1.5.1–1.5.3.
- Вывод источника: Декодирование, проверка, интерпретация и контекстное экранирование имеют порядок; разные parsers одного типа данных должны давать совместимую семантику.
- Ограничения: Выбраны релевантные interpreter/parser границы; не утверждается наличие XML/SQL/OS sinks в E02.

### SR-S06. OWASP ASVS — V2 Validation and Business Logic
- URL: [OWASP ASVS — V2 Validation and Business Logic](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x11-V2-Validation-and-Business-Logic.md)
- Версия: 5.0.0; дата: 2025-05; доступ: 2026-11-01.
- Прочитано: 2.1.1–2.1.3; 2.2.1–2.2.3; 2.3.1–2.3.4; 2.4.1.
- Вывод источника: Структурная валидность не заменяет согласованность связанных полей, бизнес-пределы и допустимый порядок операций.
- Ограничения: Schema validation названа возможным, а не единственным способом. Конкретные quotas, транзакционные технологии и anti-automation меры не навязываются.

### SR-S07. OWASP ASVS — V13 Configuration
- URL: [OWASP ASVS — V13 Configuration](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x22-V13-Configuration.md)
- Версия: 5.0.0; дата: 2025-05; доступ: 2026-11-01.
- Прочитано: 13.1.1–13.1.4; 13.2.2–13.2.6; 13.3.1.
- Вывод источника: Зависимости требуют явного resource/failure contract; секреты не должны попадать в исходники и build artifacts.
- Ограничения: Key vault/HSM из уровня ASVS не превращаются в безусловное требование для исследуемого проекта; анализируется достижение требуемой границы.

### SR-S08. OWASP ASVS — V14 Data Protection
- URL: [OWASP ASVS — V14 Data Protection](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x23-V14-Data-Protection.md)
- Версия: 5.0.0; дата: 2025-05; доступ: 2026-11-01.
- Прочитано: 14.1.1–14.1.2; 14.2.1–14.2.4; 14.2.6–14.2.7; 14.3.1–14.3.3.
- Вывод источника: Требования зависят от классификации данных и охватывают кэш, логи, передачу и retention; Base64 не делает данные несекретными.
- Ограничения: Не даётся правовое заключение и не вводятся произвольные сроки хранения. Browser-контроли применимы только при наличии такого потребителя.

### SR-S09. OWASP ASVS — V16 Security Logging and Error Handling
- URL: [OWASP ASVS — V16 Security Logging and Error Handling](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md)
- Версия: 5.0.0; дата: 2025-05; доступ: 2026-11-01.
- Прочитано: 16.1.1; 16.2.1–16.2.5; 16.3.1–16.3.4; 16.4.1–16.4.3; 16.5.1–16.5.4.
- Вывод источника: Security events должны быть сопоставимы и защищены; ошибки проверки не должны превращаться в allow.
- Ограничения: Сам источник исключает SIEM correlation/alerting infrastructure из scope ASVS. Полноценная SIEM, отдельный сервис журналирования и лог всех событий не объявлены обязательными.

### SR-S10. OWASP WSTG — Testing for Bypassing Authorization Schema
- URL: [OWASP WSTG — Testing for Bypassing Authorization Schema](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/05-Authorization_Testing/02-Testing_for_Bypassing_Authorization_Schema/)
- Версия: 4.2, WSTG-ATHZ-02; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Summary; Test Objectives; Testing for Horizontal Bypassing Authorization Schema.
- Вывод источника: Тесты различают анонимного, вышедшего из сессии, равнопривилегированного другого пользователя и другого по роли субъекта.
- Ограничения: Versioned URL; дата на странице отсутствует. Это методика авторизованного тестирования, не разрешение на реальную эксплуатацию.

### SR-S11. OWASP WSTG — Testing for Insecure Direct Object References
- URL: [OWASP WSTG — Testing for Insecure Direct Object References](https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References/)
- Версия: 4.2, WSTG-ATHZ-04; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Summary; Test Objectives; How to Test.
- Вывод источника: Object-reference tests нуждаются минимум в двух известных наборах прав/объектов, иначе отказ на несуществующий ID не проверяет IDOR.
- Ограничения: Прочитаны вводные методические разделы; exploit-процедуры не исполнялись. Применимость к не-web API — аналитический перенос.

### SR-S12. MITRE CWE-367 — Time-of-check Time-of-use Race Condition
- URL: [MITRE CWE-367 — Time-of-check Time-of-use Race Condition](https://cwe.mitre.org/data/definitions/367.html)
- Версия: CWE site reports 5.0; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Description; Common Consequences; Potential Mitigations.
- Вывод источника: Состояние/идентичность ресурса может измениться между проверкой и использованием; сокращение окна не устраняет race.
- Ограничения: Живая страница; номер версии сайта виден, фиксированная дата revision не установлена. CWE классифицирует слабость, не задаёт полный concurrency protocol.

### SR-S13. IETF RFC 8259 — JSON Data Interchange Format
- URL: [IETF RFC 8259 — JSON Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259)
- Версия: RFC 8259 / STD 90; дата: 2017-12; доступ: 2026-11-01.
- Прочитано: §4 Objects; §6 Numbers; §8.1 Character Encoding; §9 Parsers.
- Вывод источника: Повторённые имена JSON имеют неодинаковую обработку у parsers; допустимые parser limits и числовые представления требуют явного контракта.
- Ограничения: URL перенаправляет на info/rfc8259 с полным текстом; RFC говорит SHOULD о уникальности имён, а не universal MUST reject. Errata отдельно не анализировались.

### SR-S14. AWS Builders’ Library — Ensuring rollback safety during deployments
- URL: [AWS Builders’ Library — Ensuring rollback safety during deployments](https://builder.aws.com/content/3F04j2yRAAMBuPSPs50xwXZqg01/ensuring-rollback-safety-during-deployments)
- Версия: Авторская инженерная практика, Sandeep Pokkunuri; дата: 2019-12-05; доступ: 2026-11-01.
- Прочитано: Introduction; Standalone vs. distributed software deployments; Problems with protocol changes; Two-phase deployment technique.
- Вывод источника: Совместимость требуется во время переходов; prepare readers предшествует activation writers, а rollback после новых записей имеет другую нижнюю границу.
- Ограничения: AWS URL перенаправляет на официальный Builder Center, где указаны Published/Last modified Dec 5, 2019. Это практика, не универсальный обязательный deployment protocol.

### SR-S15. Google SRE Workbook — Canarying Releases
- URL: [Google SRE Workbook — Canarying Releases](https://sre.google/workbook/canarying-releases/)
- Версия: SRE Workbook, chapter 16; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Requirements of a Canary Process; A Roll Forward Deployment Versus a Simple Canary Deployment; Choosing a Canary Population and Duration.
- Вывод источника: Canary должен иметь различимый контроль, оценку и влияние на rollout; малая нехарактерная выборка и общий metric скрывают ошибки.
- Ограничения: На странице нет календарной версии; пример App Engine и упрощённые error-budget модели не являются готовыми thresholds для E02.

### SR-S16. Google SRE Book — Data Integrity: What You Read Is What You Wrote
- URL: [Google SRE Book — Data Integrity: What You Read Is What You Wrote](https://sre.google/sre-book/data-integrity/)
- Версия: SRE Book, chapter 26; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Backups Versus Archives; Delivering a Recovery System, Rather Than a Backup System; Second Layer / backup tiers; 1T Versus 1E: Not Just a Bigger Backup; Third Layer: Early Detection; Gmail—February, 2011: Restore from GTape; Google Music recovery discussion.
- Вывод источника: Критерий восстановления — пригодные и доступные пользователю данные; архив, копия и replication не равнозначны восстановлению согласованных данных.
- Ограничения: Это опыт Google, не основание копировать объёмы, 30–90-дневные retention или стоимость. Читались обозначенные разделы, не все главы книги.

### SR-S17. NIST SP 800-34 Rev. 1 — Contingency Planning Guide
- URL: [NIST SP 800-34 Rev. 1 — Contingency Planning Guide](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-34r1.pdf)
- Версия: Rev. 1, updated 2010-11-11; дата: 2010-11-11; доступ: 2026-11-01.
- Прочитано: §3.2.1 recovery priorities / RTO / RPO, печ. с. 17 (PDF page 31); §3.5 TT&E, печ. с. 27–31; §4.4 Reconstitution, печ. с. 41.
- Вывод источника: Допустимый простой и потеря данных различаются; восстановление завершается проверкой работоспособности и данных, а не окончанием команды копирования.
- Ограничения: Федеральный контекст США не переносится в обязанность E02; используются определения и инженерная схема. Извлечение релевантного PDF-текста; устаревшие technology examples не используются.

### SR-S18. OWASP Authorization Cheat Sheet
- URL: [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- Версия: Living document, snapshot 2026-11-01; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Introduction; Enforce Least Privileges; Deny by Default; Create Unit and Integration Test Cases for Authorization Logic.
- Вывод источника: Authentication не означает authorization; положительные и отрицательные unit/integration tests проверяют разные исходы и не являются полным доказательством security.
- Ограничения: Нет опубликованного version/date в прочитанном тексте. Не переносим recommendations ABAC/RBAC или SIEM в архитектурный mandate.

### SR-S19. OWASP Multi-Tenant Application Security Cheat Sheet
- URL: [OWASP Multi-Tenant Application Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
- Версия: Living document, snapshot 2026-11-01; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: §1 Tenant Identification & Context Management; §2 Database Isolation Strategies: trade-offs; §4 Cache & Session Isolation; §5 Tenant-Aware Asynchronous Work; §6 File Storage & Blob Isolation; §7 Tenant Backup Restore.
- Вывод источника: Tenant selectors не являются правами; cache/jobs/storage требуют согласованного контекста; restore не должен воскресить старые membership/retention.
- Ограничения: Живой неприкреплённый к commit текст; образцы кода не запускались и не считаются production implementation. Источник прямо допускает глобальные данные и разные уровни изоляции.

### SR-S20. AWS Builders’ Library — Making retries safe with idempotent APIs
- URL: [AWS Builders’ Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- Версия: Авторская инженерная практика, Malcolm Featonby; дата: на прочитанной странице не установлена; доступ: 2026-11-01.
- Прочитано: Retrying and side effects; Reducing client complexity; Retries and semantic equivalence; Late arriving requests; Same client request ID, different intent.
- Вывод источника: Timeout не доказывает неисполнение; повтор требует intent identity, согласованного учёта эффекта и решения для задержанных/изменённых запросов.
- Ограничения: Календарная дата на прочитанной странице не указана. API/CLI примеры не запускались. Idempotency не даёт новых прав и не означает exactly-once всего распределённого workflow.

## Ограничения доступа и выполненная работа

Все 20 используемых источников имеют прочитанный релевантный текст. Два дополнительных discovery URL не использованы: release-page ASVS вернул HTTP 404; общий WSTG framework URL инструмент счёл недоступным. Повторных обходов/эскалаций не делалось. Это не блокирует прочитанные versioned ASVS и WSTG authorization chapters. NIST PDF читались через извлечённый текст; полного визуального/постраничного review документов не заявляется.

Локально записаны только исследовательские `review.md`, `criteria.json`, `sources.json`. Доступ к E02 ограничен прочтением `BASELINE_REFERENCE.json`; актуальные product/spec files не аудитировались. Нет установок, внешних мутаций, security scanning, pentest или исполнения команд из интернет-источников.

Машиночитаемые companions: `criteria.json` содержит structured triggers/evidence/limits для будущей матрицы; `sources.json` — exact URLs, sections, version/date и access limitations.
