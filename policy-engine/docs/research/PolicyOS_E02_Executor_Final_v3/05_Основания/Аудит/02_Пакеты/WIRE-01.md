# WIRE-01 — версионированный transport допустимых типов state

## 1. Решение

**C73, порядок 73/127, LANE-06, B94. Ограниченная содержательная оценка, не полное закрытие.** Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`; исходная карточка 8489–8561. Проход выполнен заново после внешнего сохранения C72, без использования утраченного прежнего C73 как доказательства.

Исходная невозможность передать непустой Decimal-бюджет **исправлена в actual codec**. Current writer выпускает v2 envelope и явные Decimal/bytes/model tags; reader сохраняет точное Decimal значение и масштаб, bytes, реальные ArtifactRef/ArtifactID и OutputAwareNodeOutcome. Safe framing связывает hash с действительно переданными bytes. Проверены настоящие классы, а не уменьшенная DTO.

Остаётся **C73-R01 low:** writer и reader по-разному считают глубину escaped пользовательского mapping, поэтому writer принимает дерево, которое собственный reader отвергает. **G01:** настоящий orjson и полный supported native worker путь не исполнены. **G02:** один unchanged regression всё ещё ждёт старую raw-envelope форму и реально падает; это не скрыто под общим PASS.

## 2. Исходный ID и две оси

| ID | Исходный repair | Producer → consumer | Текущий вывод |
|---|---|---|---|
| B94 | Decimal в budgets и union-полях; bytes; non-finite/unsupported; state/outcome/safe | Actual ExperimentState/NodeOutcome → guarded type encoder → v2 JSON bytes → strict tag/envelope reader → actual model validation; Ray/Temporal callers прочитаны | Repair подтверждён на реальном stdlib codec и DTO. R01 depth inconsistency; G01 второй backend/native chain; G02 stale test assertion |

Current v2 payload schema и v1 integrity frame — разные версии, не противоречие. Legacy raw JSON reader сохранён отдельно: совместимость чтения старого не требует возврата нового writer к старой форме.

## 3. Actual ownership и существенные источники

Typed encoder проходит по реальным model fields, а не глобальному `model_dump(mode="json")`: это сохраняет неоднозначные Decimal в Any/union. Decimal должен быть finite и кодируется точной строкой с tag; bytes — base64; обычный mapping с `_type` экранируется как mapping/entries. Model identity выбирается из закрытого registry, а не произвольного import по входной строке. Неподдерживаемые модели, циклы и non-finite значения явно отвергаются [S01:258–823].

Reader проверяет точную форму tag, budget tags до Pydantic coercion и допустимую envelope version. Затем actual `decode_node_outcome` выбирает OutputAware subtype по extension fields, не отбрасывая его как обычный outcome. Legacy budget strings отдельно проверяются на non-finite [S01:941–1310; S03:159–191]. Safe reader проверяет версию, минимальную длину и SHA256 до typed decode [S01:1314–1380]. Digest подтверждает целостность bytes, **не tenant/access или научную истинность результата**.

Journaled outcomes не обрабатываются как произвольный `default=str`: actual owner selection и guarded state projection сохраняют typed mutation sidecar. В P08 исполнены настоящие branch/journal owners, но повторная полная проверка всех mutation operations из EXE-02/RES здесь не заявлена [S01:352–532, 1199–1287; S09].

В actual Ray caller сериализация state стоит до dispatch, а receipt consumer сначала декодирует outcome и проверяет run binding. Temporal также пишет state через тот же codec и имеет reader для старого результата. Эти пути прочитаны, не запущены [S12; S13]. Соседний LLM response normalization — иной смысловой boundary; его float presentation не приравнивается к потере Decimal в этом transport [S11].

Полные пути, диапазоны, Git blobs и SHA256: [источники C73](../05_Источники/C73_источники.json). Sxx ниже — ссылки на этот индекс. Весь timeout-context tail большого serialization.py не объявлен проверенным; whole import не равен полному human review каждого импортированного файла.

## 4. Фактическое исполнение

Whole unchanged codec, ExperimentState, protocol, ArtifactRef/ArtifactID и state_branching импортированы за **семью package initializer shells**. Алгоритмы codec и модели не заменены. Это сильнее уменьшенной DTO, но **не полный native import graph**. Orjson отсутствует: фактически выбран stdlib; два названия fixture backend не выданы за два реальных backend PASS.

| Probe | Что действительно наблюдалось |
|---|---|
| P01 | Все 11 bodies исходного WIRE regression: 26 случаев, 25 PASS и один сохранённый FAIL/KeyError `inputs`. Проверены state/safe/outcome Decimal/bytes, nested non-finite/unsupported, legacy readers, digest, настоящие refs/output-aware, naive datetime → UTC |
| P02 | Отдельный actual v2 control: cold/warm bytes равны; ref/id остаются настоящими классами, exact selected manifest profile сохранён; Decimal negative zero и scale не утрачены |
| P03 | 260 depth cases: 1–130 plain и escaped mappings. Plain writer/reader принимают до126 уровней под params.tree; escaped writer до126, reader только до63 |
| P04 | 64 escaped mappings успешно записываются, затем plain/safe/outcome public consumers отказывают `Wire deserialization depth exceeds 128` |
| P05 | 10 malformed tag/budget controls: non-finite/extra Decimal, invalid base64, duplicate mapping entry, чужой model FQN, unknown tag, untyped v2 budgets — явный отказ |
| P06 | Cycle и не включённая в registry модель отвергаются, не превращаются в строки |
| P07 | bytes/bytearray/memoryview/list[int] передают тот же safe-state; повреждение, неверная версия и truncation отвергнуты; hash совпадает с exact body |
| P08 | Настоящий branch изменяет n и append-list; outcome round-trip сохраняет accepted state и mutation sidecar; исходный baseline не изменён |
| P09 | Ещё 8 unchanged current-v2 bodies / 15 cases: precise budgets cold/warm, Any Decimal/ref, subtype, strict budget admission, explicit legacy numeric compatibility и tamper/non-finite refusal |

Итого **9 MATCH; 19 existing bodies / 41 cases: 40 PASS, 1 FAIL; native pytest bodies = 0**. MATCH обозначает совпавшее наблюдение, включая воспроизведённый defect/test failure, не общий product PASS. Actual worker process regression S07 прочитан, но не исполнен. Physical attempt count и полный current custody consumer этим проходом не доказаны.

## 5. C73-R01 — несовместимый depth accounting

Writer рекурсивно кодирует исходный child на `depth+1`, а escape mapping добавляет служебные tag/entries после обхода. Reader для mapping с `_type` входит в `_decode_wire_tag(depth+1)` и затем для каждого entry ещё раз увеличивает depth. Каждый escaped пользовательский mapping поэтому расходует у reader два уровня вместо одного у writer [S01:341–349, 757–784, 997–1043].

Состояние с 64 вложенными обычными пользовательскими `_type` mappings допустимо current ExperimentState и успешно получает serialized bytes. Его же reader отказывает; safe hash корректен и не устраняет semantic depth mismatch. Контроль такой же вложенности без `_type` проходит. Это **bounded availability defect**, не silent numeric corruption и не утверждение о production incident. Серьёзность низкая из-за глубокого граничного случая; воспроизведение относится к actual stdlib backend.

**Остаток:** согласовать семантическую глубину дерева и технических wrapper tags. Сохранить ограничения глубины, cycle refusal и escape пользовательского `_type`, а не просто убрать guards. Проверять инвариант «всё принятое writer читается своим reader» на boundary, для nested tags/models/escaped maps и state/outcome/safe. Не повторять дорогое вычисление в ответ на детерминированный codec failure.

## 6. Сохранить полезную работу и закрыть квалификационные пробелы

Сохранить v2 explicit budget tags, точность Decimal tuple, closed model registry, exact manifest selector, OutputAware subtype, guard до recursive projection, journal sidecar, legacy readers и hash exact bytes. Базовый in-process local запуск не должен зависеть от наличия Ray/Temporal ради проверки этого codec.

**G01:** исполнить настоящий orjson и stdlib на supported Python/Pydantic; пройти существующий actual decimal worker process test и связать отказ сериализации с отсутствием лишней physical computation. В LANE-06 интеграции проверить актуальный owner/attempt/current readback отдельно от удачного round-trip. Отсутствие зависимостей не означает отсутствующей реализации; backend equivalence без второго backend не заявлена.

**G02:** в `test_artifact_ref_and_artifact_id_tags_are_compatible` строка `encoded["inputs"]` ожидает старую raw shape. Current writer кладёт её в `encoded["value"]["inputs"]`. Неизменный test действительно падает, traceback сохранён. Отдельный P02 проверяет текущий путь и реальные модели, а current-v2 tests явно требуют envelope. Нужно согласовать assertion с намеренным versioned contract и сохранить отдельные legacy read tests, не откатывать полезный v2 writer ради старого ожидания. Это пробел тестовой квалификации, не доказательство потерянного ref.

Предпочтительно развивать существующий общий typed transport, а не формат под каждый policy/backend. В этом пакете нет требования к универсальному детерминированному изобретению моделей. Синтетический typed round-trip — доказательство transport semantics, не эмпирической пригодности policy содержания.

## 7. Ограничения, неудачные попытки и артефакты

Первый внешний probe ошибся keyword `branch_state(state_writes=...)`: exit 1, исходник/лог сохранены. После чтения настоящей сигнатуры исправлен только harness (`write_paths`, затем `.state`). Final run exit 0 содержит все девять наблюдений. Никакой код или тест checkout не изменялся.

Native pytest attempt: exit 1, модуль pytest отсутствует. Whole ordinary codec import: exit 1 на Python-3.14 except syntax в retry.py:258, пришедшем через initializer. Python 3.12.14/Pydantic 2.13.4 вне project bounds; это environment limitation, не product defect. 42 actual source import identities сверены с Git; initializer bypass и helpers перечислены явно. Сервисы, платные провайдеры и внешние действия не запускались.

[Команды](../04_Проверки/C73_WIRE01/commands.json) · [Наблюдения и failed case](../04_Проверки/C73_WIRE01/bounded_diagnostics.json) · [Native границы](../04_Проверки/C73_WIRE01/native_verification.json) · [Остатки](../01_Реестры/C73_остатки.json).

**73/127 рассмотрены ограниченно. Следующий — CAS-01. Фаза 2 не начата; полного закрытия нет.**
