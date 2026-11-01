# SCL-01 — Текущий допуск cached страницы и бюджет каждой попытки

**Лейн:** LANE-09 · **Окно:** CP2 · **Основания:** B17, LA-024 · **Тип:** fix + preserve + native qualification.

**Практический результат.** Доступный поиск продолжает полезные разрешённые попытки, но не отдаёт запрещённый snapshot и не начинает работу после hard deadline.

**Статус:** исполнительское ТЗ. Это не выполненный ремонт; все новые TEST ниже — **NOT_RUN**. Исходный аудит выполнен на `20d9009be21097bfbdc38a546a15cc60213b8ace`; его полнота не означает закрытия остатков.

## 1. Основание и границы
[Аудит SCL-01](../05_Основания/Аудит/02_Пакеты/SCL-01.md), [остатки C104](../05_Основания/Аудит/01_Реестры/C104_остатки.json), [полная исходная карточка](../05_Основания/Аудит/05_Источники/SCL-01_исходные_строки.txt). B17/LA-024; LK09 — защищённое различение, не дополнительная migration. R01 — допуск saved content, не установленный SSRF/network-access exploit. Full probes доступны в отдельно доставленном phase1 ZIP; historical bounded counts не являются свежей native приёмкой.

## 2. Сохранить
Existing []/exception failover, ordered diagnostic attempts, typed seed/search adapters, raw transport, local files/bytes, peer/DNS/SNI/proxy refusal и prebatch deadline.

## 3. Полная disposition остатков

- **C104-R01 — fix** → REQ-SCL-01-01. Current admission перед cached result и snippets с сохранением legal reuse.
- **C104-R02 — fix** → REQ-SCL-01-02, REQ-SCL-01-03. Единый deadline ограничивает каждый provider attempt и честный terminal outcome.
- **C104-G01 — qualify** → REQ-SCL-01-04, REQ-SCL-01-05. Native transport/profile compatibility и явное решение candidate schema; fixture не права на источник.

Исходные обязанности и сохранения lossless inventory связаны отдельно в companion JSON (`obligation_dispositions`, `preservation_bindings`); номера residual не заменяют исходные обязанности.

## 4. Нормативные требования

### REQ-SCL-01-01
Перед возвратом cached страницы fetch_open_page должен проверить текущую применимую policy по initial/final URL и каждому redirect, MIME, известному raw byte_size и пригодности saved profile. Неизвестный требуемый факт не считается доказательством допуска; unchanged разрешённый snapshot должен переиспользоваться без нового raw fetch. При достаточных saved facts offline reuse не зависит от нового DNS/socket access. Pure URL/domain/literal-IP и saved-content policy проверяются до выдачи; live destination resolution выполняется только при отдельно разрешённом fresh fetch.

Основание: LA-024; аудит: C104-R01. Проверка: TEST-SCL-01-01, TEST-SCL-01-02.

### REQ-SCL-01-02
deep_search должен передать единый monotonic deadline в provider failover; перед каждой следующей попыткой вычисляется remaining. При remaining<=0 новый provider не запускается; timeout попытки не превышает min(per-search timeout,remaining). Итог сохраняет partial и точную wall-budget причину, включая истечение в последнем batch.

Основание: B17; аудит: C104-R02. Проверка: TEST-SCL-01-03.

### REQ-SCL-01-03
При доступном бюджете []/exception/unusable candidates должны позволять следующий разрешённый provider; trace различает empty/error/filter/normalization и legacy unknown, не заявляя исчерпания знаний по одному ответу.

Основание: B17. Проверка: TEST-SCL-01-03, TEST-SCL-01-04.

### REQ-SCL-01-04
Search и seed должны продолжать использовать один redirect-aware raw transport, сохраняя полный документ/bytes/hash/license/source identity, numeric destination/peer проверки и hostname SNI. Local-file/bytes adapters и search extraction остаются отдельными; snippets не заменяют raw.

Основание: LA-024. Проверка: TEST-SCL-01-04, TEST-SCL-01-05.

### REQ-SCL-01-05
Native HTTP/TLS/redirect-cycle/proxy и supported runtime квалифицируются на контролируемом разрешённом стенде; candidate schema1.1 не объявляется принятой автоматически. До stronger deployment claim оформить конечное решение совместимости actual producer/consumer contract, сохраняя рабочий текущий supported профиль.

Основание: B17, LA-024; аудит: C104-G01. Проверка: TEST-SCL-01-05, TEST-SCL-01-06.

## 5. Решение на текущих owners
Все code paths ниже repo-relative от `policy-engine/` на pinned commit.

1. `src/polisyos/scholar/search/fetcher.py::fetch_open_page`: existing initial `_resolve_fetch_target` выполняет live `getaddrinfo` до cache.get, поэтому одного cached check после этого guard недостаточно. В current `security.py` разделить pure URL syntax/domain/port/literal-private-IP policy и live destination resolution. Порядок: offline initial policy → cache.get → current saved initial/final/redirect URL, MIME, raw byte_size и necessary profile admission → eligible cached return. Только разрешённый miss/explicit refresh проходит live resolver и existing pinned transport/peer/SNI/redirect checks. Сохранённая страница не требует нового DNS; DNS today не historical peer proof. Text length не raw size. Unknown required fact даёт distinct cache-ineligible outcome и лишь existing permitted refresh либо gap, не cached text; не удалять весь index ради одного entry.
2. SCL-03 владеет фактическим `FetchResult.fetch_profile` producer wiring. Здесь определить с ним минимум current-admission полей (normalized constraints, max_bytes, transport/profile version, acquisition timeout/UA как provenance); совпадение всех полей не обязательно там, где текущую policy можно непосредственно доказать. Старый `{}` не означает permission. TTL остаётся freshness primitive, не access proof.
3. `src/polisyos/scholar/search/service.py::deep_search` вычисляет absolute monotonic deadline от существующего start_time/budget и передаёт его в `src/polisyos/scholar/search/providers.py::ProviderFailoverPolicy.search_with_attempts`. Добавить backwards-compatible optional deadline; legacy `search` сохраняет tuple ABI. Перед каждым adapter call проверить remaining и передать min timeout. Для hard bound использовать существующий async timeout/cancellation owner, не только advisory provider timeout. Cancellation не ловить как обычный provider error. Service получает отдельный terminal budget outcome (через existing trace/результат с совместимым adapter) и отмечает partial, даже когда очередь завершилась в этом batch. Не приравнивать query count к attempt count.
4. Не переписывать `src/polisyos/scholar/discover/transport.py`: он уже общий. Native квалификация использует оба adapters. Реальные test owners сверить по source inventory C104; verified `tests/unit/scholar/search/test_source_binding.py` относится к downstream, для policy/transport tests выбрать существующие files. Новый test_scl_01.py был исходным предложением, не найденным здесь файлом.

## 6. Локальные различающие проверки

Все TEST — будущие спецификации проверок, не заявления о существующих тестовых функциях. Сначала расширять перечисленные реальные test owners; новый файл — только при отсутствии подходящего owner.

### TEST-SCL-01-01 — native public cache roundtrip / NOT_RUN
- **Setup:** Разрешённый actual raw response с redirect, UrlFetchCache JSON put/reload, known MIME/size. После producer put/reload сделать DNS resolver/socket/transport raise-on-call; сохранённые facts достаточны для current offline admission.
- **Действие:** Повторить public fetch/find при unchanged policy; затем blocked final/redirect host, меньшем max_bytes, другом MIME. Повторить allowed cached fetch/find при недоступном DNS; запрещённые cached policy variants тоже проверить без network access. Fresh miss/refresh квалифицировать отдельно с прежними live guards.
- **Oracle:** Unchanged→cached и 0 новых raw calls; каждый запрещённый cached case не даёт text/snippets. Cold и cached policy outcomes согласованы; old cache bypass test падает на прежнем коде. Eligible persisted cache возвращает прежние text/ref при нуле новых DNS/socket/raw calls; current offline policy denial также не открывает сеть. Existing live resolver перед cache.get должен нарушить positive offline oracle.
- **Ожидаемый исход:** Positive reuse плюс различающие negatives.
- **Doubles / граница:** Контролируемый raw transport allowed; cache/index/fetch/find реальные, не fabricated cached record.
- **REQ:** REQ-SCL-01-01.

### TEST-SCL-01-02 — native historical cache profile / NOT_RUN
- **Setup:** Persisted legacy records с missing byte_size/profile/redirect metadata и известные valid records; no fabricated rights.
- **Действие:** Применить current constraints; выполнить явный permitted refresh отдельно.
- **Oracle:** Missing required facts → explicit unusable-cache/gap либо разрешённый refresh по existing call policy, не silent equivalence. Известные достаточные факты допускают reuse без требования полного identity совпадения всех несущественных полей.
- **Ожидаемый исход:** Безопасная совместимость, не blanket cache-disable.
- **Doubles / граница:** Не обращаться к запрещённому host ради проверки saved content; не считать DNS today историческим peer proof.
- **REQ:** REQ-SCL-01-01.

### TEST-SCL-01-03 — native deterministic deadline / NOT_RUN
- **Setup:** Actual service и ProviderFailoverPolicy, monotonic injected clock; budget1, first empty ends t2; boundary remaining0; success when second finishes within budget.
- **Действие:** Вызвать deep_search и legacy policy interface; inspect passed timeouts/attempts/partial/notes.
- **Oracle:** Expired→second count0, partial=True, stopped:max_wall_time_s ровно с реальной причиной; available→second called with bounded timeout и hits preserved; cancellation не превращается в continue-all. Prebatch guard сохраняется.
- **Ожидаемый исход:** Old t2 second-call reproducer различающий; положительный failover обязателен.
- **Doubles / граница:** Provider/clock doubles allowed; service/policy реальные, не sleep-based flaky race.
- **REQ:** REQ-SCL-01-02, REQ-SCL-01-03.

### TEST-SCL-01-04 — native provider/adapters preservation / NOT_RUN
- **Setup:** First [], first exception, normalized-invalid, all-filtered и legacy list-only provider; raw HTML/bytes/local file.
- **Действие:** Actual policy/search/discover adapters; inspect ordered trace и full byte input downstream.
- **Oracle:** Причины/counts только наблюдаемые; legacy raw counts None; provider ABI/error text сохраняется. Full document не snippets; local path/bytes живы.
- **Ожидаемый исход:** Полезный second result и исходные adapters.
- **Doubles / граница:** Fake provider/response allowed; не fake policy/normalizer/adapter outputs.
- **REQ:** REQ-SCL-01-03, REQ-SCL-01-04.

### TEST-SCL-01-05 — native controlled transport integration / NOT_RUN
- **Setup:** Supported Python3.14, локальный разрешённый HTTP/TLS fixture и explicit private-network opt-in; valid numeric peer, redirects/loop/oversize/timeout/MIME, отказ proxy where current contract disallows.
- **Действие:** Пройти обоими actual adapters через discover/transport; inspect raw hashes и hostname SNI/peer binding.
- **Oracle:** Valid bytes одинаковы; invalid hop/peer/MIME/size не выдаётся; loop bounded. Opt-in не отключает остальные проверки. Ни internet access, ни current source rights не выводятся из fixture.
- **Ожидаемый исход:** Positive real native stack и targeted refusals.
- **Doubles / граница:** Local server/transport endpoints allowed; no external production fault injection. Не подменять CAS/Python imports shims.
- **REQ:** REQ-SCL-01-04, REQ-SCL-01-05.

### TEST-SCL-01-06 — finite compatibility decision / NOT_RUN
- **Setup:** Actual current schema/consumer requirements и candidate1.1 docs, supported platform/proxy policy.
- **Действие:** Составить таблицу field/producer/reader/version и выполнить выбранные supported combinations.
- **Oracle:** Решение: оставить текущий supported schema либо явно forward-migrate candidate при подтверждённых consumers; нет скрытого принятия ratification. Unsupported profile marked, не фиктивный PASS.
- **Ожидаемый исход:** Bounded qualification output, не новая архитектура.
- **Doubles / граница:** Source rights проверяются только по имеющимся конкретным источникам; не выдумывать universal public-web grant.
- **REQ:** REQ-SCL-01-05.

## 7. Общий сценарий, зависимости и ownership
**E02-I09-A**: Scholar→raw snapshot→snippet→docs ingest. SCL-01 владеет shared transport/cache admission/deadline; SCL-03 — effective profile producer wiring и selected-ref handoff. `src/polisyos/scholar/search/fetcher.py` общий: один writer, согласованная последовательность, не два несовместимых cache predicates. SCL-03 интегрировать после SCL-01. Native CAS и docs-ingest контракты читаются у существующих owners, не создаётся второй store. [Канонический сценарий LANE-09](../03_Интеграция/LANE-09.md). CP2 — окно связанной приёмки, не новый runtime gate.

## 8. Совместимость, история и rollback
Старые JSON cache records остаются читаемыми и unknown там, где фактов не было. Не достраивать исторический fetch profile вымышленными defaults. Current constraints строже — affected cache ineligible, остальные entries полезны. Deadline новый optional keyword с legacy ABI. Rollback ограничивает affected reuse, не снимает current admission и не выключает весь Scholar.

## 9. Free-grow/design alignment
[Vision §3,§7,§11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): один owner транспорта и новый совместимый provider через protocol. [North Star §5,§7](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md): содержательная acquisition работа и честная неопределённость важнее ложного «нет знаний». Не требовать universal deterministic semantic search solver; новый source-specific adapter допустим при общем contract.

## 10. Приёмка и пределы PASS
Предъявить actual miss→JSON reload→public find и deadline schedule; native controlled HTTP/TLS scope; candidate schema decision. Нет live платных providers. Не называть unchanged fixture permission, source license/currentness проверенными автоматически, root lazy import — search native PASS, правильный failover — исчерпанием мировых знаний.

Для каждого TEST: actual command/runtime/commit, exit/log, input hashes, assertions и список doubles. Новые tests NOT_RUN до исполнения. Адаптируемый шаблон `<supported-python> -m pytest <verified test paths>` из `policy-engine/`; runner/dependencies здесь не объявлены доступными. Не устанавливать зависимости как часть этого задания на документы.

