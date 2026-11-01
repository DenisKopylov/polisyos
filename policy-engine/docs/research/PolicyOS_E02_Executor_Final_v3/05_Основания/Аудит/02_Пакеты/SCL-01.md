# SCL-01 — пустой ответ, общий raw transport и границы повторного допуска
## C104 · LANE-09 · B17, LA-024 · сохранить LK09

**Решение: частично подтверждено, не закрыто.** Поиск продолжает работу после пустого результата и исключения. Seed и search действительно используют общий redirect-aware raw transport, не подменяя полный документ поисковым сниппетом. Остаются две недосвязки: повторный допуск cached страницы по текущим ограничениям и передача оставшегося wall-time бюджета следующему provider.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **6 MATCH; 44 неизменённых test bodies / 60 cases PASS** в ограниченном исполнении. MATCH включает воспроизведение двух дефектов, а не означает product PASS. **104/127**, далее SCL-03.

## 1. Две независимые оси

**Исходный ремонт.** `ProviderFailoverPolicy` не возвращает первый пустой ответ как окончательный успех: следующий provider вызывается. Для конкретных adapters различены пустой ответ, отбраковка при нормализации и фильтрация ограничениями; для legacy list-only provider неизвестные исходные количества честно остаются неизвестными. Общий transport сохраняет bytes, headers, final URL и redirects, а оба adapters сохраняют свою роль.

**Содержательная способность.** Прослежена цепочка provider → ordered attempts → service trace; raw transport → actual JSON cache → public fetch/find → точные текстовые spans. Она полезна для получения и трассировки материала, но не доказывает исчерпание знаний, истинность источника или причинную валидность. Возврат cached результата без текущего допуска и продолжение после исчерпания бюджета уменьшают реальную управляемость этой цепочки. LLM остаётся semantic proposer; отсутствие универсального детерминированного автора моделей здесь не объявлено дефектом.

## 2. Матрица исходных IDs

| ID | Что подтверждено | Что остаётся |
|---|---|---|
| B17 | Переход после `[]`, после exception и после непригодных конкретному adapter кандидатов. Причины и неизвестность legacy diagnostics различены. | C104-R02: уже начатый batch не проверяет remaining wall budget перед следующим provider; global search exhaustion не доказан. |
| LA-024 | Один общий raw transport; seed получает полный документ, search извлекает текст отдельно. Проверки initial/redirect, size/MIME и сохранения raw hash реально исполнены на fake responses. | C104-R01: cache-hit не применяет текущие ограничения final/redirect host, MIME и размера. Native transport и принятие candidate контракта открыты. |
| LK09 — защита, не дополнительный B/LA | Discover URL/files/bytes, search и orchestrator не слиты. Actual local-file read и bytes normalization сохранены. | Snapshot handoff принадлежит следующему SCL-03; полный docs/claims pipeline в C104 не аттестован. |

## 3. Фактические владельцы и потребители

1. Provider policy последовательно собирает `ProviderAttemptTrace`, продолжает после пустоты и завершает при hits. Конкретные adapters сообщают наблюдаемые raw/candidate/rejection counts; legacy provider не получает выдуманных причин. Public legacy search сохраняет свой result ABI и error text, тогда как persisted trace использует безопасные категории [S01:99–221; S07:240–452].
2. `discover.transport` один раз разрешает адрес каждого hop, связывает numeric destination с проверяемым peer и оставляет hostname для Host/SNI. Redirect handler повторяет политику для нового target; непроверенный proxy route отказывает. Search и seed вызывают этот raw owner, но сохраняют разные типизированные outputs [S02; S03; S04].
3. Search cache хранит text, final URL, redirects, MIME и byte_size. Public service повторно использует тот же cache в fetch и find; find допускает status `cached` и извлекает spans из возвращённого текста [S05; S06:134–215]. Это реальная downstream ветвь R01, а не искусственный вызов внутренней функции без потребителя.
4. `deep_search` владеет общим бюджетом, но передаёт provider policy неизменный per-search timeout. Проверка wall deadline находится перед batch, а не между попытками внутри policy [S06:280–330; S01:118–221].
5. Local-file и bytes normalization остаются отдельными. Соседний prior miner извлекает уже существующие graph priors, а не является третьей реализацией HTTP поиска [S10–S16].

## 4. Фактические наблюдения

| ID | Исполнение и результат |
|---|---|
| P01 | 11 existing bodies / 11 cases PASS: пустой первый provider, exception failover, конкретные normalization/filter причины, legacy unknown и прежний error text. |
| P02 | 12 existing bodies / 12 cases PASS: raw bytes/hash, seed metadata, общий executor bridge, initial/redirect refusal, MIME/size/timeout, cache и точные spans. |
| P03 | 21 existing fake-only bodies / 37 cases PASS: numeric address, peer IP/port/IPv6 scope, hostname SNI, proxy refusal/bypass, non-global DNS и обе adapter ветви redirect refusal. |
| P04 | Actual miss → JSON write → reload → public find возвращает cached страницу запрещённого final host и snippets при max_bytes=4. Отдельный MIME-only запрос также получает прежний text/html. Cold controls отказывают; unchanged profile переиспользуется; initial host guard работает. |
| P05 | При hard wall budget 1 первый пустой provider завершает в controlled t=2, следующий начинается в t=2 с timeout 10. Итог partial=False без wall-budget note. Positive pre-batch expiry вызывает 0 providers и partial=True. |
| P06 | Actual local-file raw bytes/license и bytes source normalization сохранены; полного document pipeline в этом опыте нет. |

[Диагностика](../04_Проверки/C104_SCL01/bounded_diagnostics.json) · [команды](../04_Проверки/C104_SCL01/commands.json) · [existing bodies runner](../04_Проверки/C104_SCL01/probe_scl01.py) · [границы и контроли](../04_Проверки/C104_SCL01/probe_boundaries.py).

## 5. Подтверждённые остатки

### C104-R01 — текущие ограничения не доходят до cache-hit admission

После initial URL validation функция немедленно возвращает `cached.to_fetch_result()` [S04:40–44](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/search/fetcher.py#L40-L44). Cache проверяет URL key и TTL, но не текущие constraints [S05:103–111](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/search/cache.py#L103-L111).

P04 не вставляет fabricated cache record: actual raw response проходит разрешённый redirect, actual cache пишет JSON и новый экземпляр его перечитывает. Затем public consumer выдаёт сохранённый текст и snippets при новом blocked final host и меньшем max_bytes; MIME constraint также обходится именно на cache hit. Cold path по каждому условию отказывает, а initial-host запрет остаётся действующим.

**Оставшаяся работа:** связать повторное использование существующего snapshot с применимыми текущими ограничениями и известностью его профиля до выдачи результата потребителю. Сохранить допустимое reuse и общий transport; неизвестные metadata не превращать в доказательство эквивалентности. Это не новый запрос к запрещённому host, не установленная SSRF эксплуатация и не вывод о separate orchestrator handoff SCL-03.

### C104-R02 — следующая failover попытка начинается после hard deadline

DTO называет wall-time budget жёстким ограничением, но service проверяет его лишь перед batch, затем вызывает policy с постоянным timeout [S07:21–32](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/search/models.py#L21-L32), [S06:296–330](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scholar/search/service.py#L296-L330). Policy не получает remaining deadline.

P05 использует actual service и policy, меняя только service-local clock и ответы двух разрешённых fake providers. Второй вызов начинается после исчерпания лимита; последний batch заканчивается без partial/budget note. Positive control показывает, что existing pre-batch guard работает: это конкретная потеря ограничения между попытками, не отсутствие всех бюджетов. Logical query count не приравнивается к числу provider attempts и отдельным дефектом не объявлен.

**Оставшаяся работа:** довести remaining deadline до существующей failover boundary, согласовать timeout/cancellation и честную terminal причину. Не выключать полезный переход после пустого ответа при доступном бюджете и не создавать второго search owner. Реальная задержка и job-manager cancellation этим controlled опытом не измерены.

## 6. Сохранить и доквалифицировать

Сохранить общий raw transport, исходные bytes, разные typed adapters, license metadata, explicit private-network opt-in, numeric destination/peer и hostname identity, точные spans и разделение error/empty/filter/unknown. Не заменять полный документ snippets и не стирать local-file/bytes маршрут.

**C104-G01.** Native lazy root import PASS не означает работоспособность search graph: тот BLOCKED на Python3.14 syntax в CAS при Python3.12.14. Pytest и opentelemetry отсутствуют; Pydantic2.13.4 вне целевого ограничения. Bounded setup использует package shells, actual class aliases, один TypeVar import adaptation и явно no-op tracing. Ранние setup failures сохранены, итоговые 60 cases не суммируются с предыдущими попытками.

Реальные HTTP/TLS и redirect-cycle integration tests не исполнялись. Proxy/macOS compatibility и candidate schema1.1 pending G остаются явными ограничениями документации, не принятым нами новым контрактом. Cache здесь работает без CAS; snapshot custody и handoff переходят к SCL-03. Лицензионные права, полнота корпуса, достоверность публикаций и научная валидность не следуют из технических PASS.

[Исходная карточка](../05_Источники/SCL-01_исходные_строки.txt) · [pinned источники](../05_Источники/C104_источники.json) · [остатки](../01_Реестры/C104_остатки.json) · [точные границы](../04_Проверки/C104_SCL01/Чтение_и_границы.md).

**104/127 — промежуточный аудит. Следующий SCL-03. Фаза заданий исполнителю не начата.**
