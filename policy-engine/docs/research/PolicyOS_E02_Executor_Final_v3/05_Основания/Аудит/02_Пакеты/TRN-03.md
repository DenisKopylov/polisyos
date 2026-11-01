# TRN-03 — предметный контекст, фильтры уроков и часы evidence
## C27 · 31 октября 2026 года

**Исходные IDs:** B135, B136, B137. **Порядок:** 27/127, последний пакет LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; далее LANE-03, EMP-01.

## Решение

**Основные исходные дефекты устранены.** Resolver сохраняет explicit task_family/domain/run, различает отсутствие и malformed declaration, не позволяет caller label стать authenticated tenant. Local и transfer используют общие source predicates и повторно проверяют effective trust/confidence до записи результата. Обычное чтение и transfer не обновляют evidence time: 100-дневный урок остаётся 0.5/low_confidence после повторения и fresh registry; usage сохраняется отдельным daily-throttled sidecar без перезаписи полного CAS index.

Подтверждены два узких остатка: **C27-R01** — sibling pattern/report projection выдаёт историческую 0.9/local там, где query того же старого урока уже возвращает 0.5/low_confidence; **C27-R02** — typed context допускает naive datetime, несовместимый с aware age calculation. Отдельная **C27-G01:** freshness anchor объединённой source entry не переносится в target result, поэтому немедленный transfer может иметь 0.9, а его fresh read — 0.5. Это намеренно консервативное readback в существующем тесте; снимать демotion ради одинакового числа нельзя.

**23 MATCH, 0 ERROR**, exit 0 в финальном запуске. Исполнены complete resolver/lesson registry definitions, actual Pydantic DTO, реальные index/access files, actual lifecycle hint method и calibration lesson projection. CAS/profile/security owner — **явные фикстуры**; native product/authorization/scientific validation **UNRUN**.

## 1. Матрица исходного ремонта и содержательной способности

[Исходный TRN-03 целиком](../05_Источники/TRN-03_исходные_строки.txt).

| ID | Сохранённый ремонт | Реальный остаток |
|---|---|---|
| B135 | Typed и serialized explicit subject context равны; fields_set отличает default; конфликт не скрывается; actual tenant owner имеет приоритет | Конфликтующие declarations теперь отказывают, а не разрешают arbitrary override. C27-R02: единый контракт timezone; native security boundary не проверен |
| B136 | Предикаты source-run/stage/domain/tags/threshold едины; materialized trust проверен после projection; final quota после eligibility | Native source/store/access квалификация; content source domain и target namespace не следует смешивать |
| B137 | Access не evidence; cold/warm/reopened одинаковая old-age demotion; transfer сохраняет created_at; отдельный throttled sidecar | C27-R01 sibling historical grade не обозначен как отдельный clock; C27-G01 source-anchor handoff; настоящая empirical revalidation не доказывается новым timestamp |

LLM здесь получает **подсказки для предложения**, а не научно доказанные причинные эффекты. Confidence урока и provenance_weight — внутренние оценки/правила маршрута, не измеренная вероятность истинности. Устаревшая идея не объявляется ложной и не удаляется только из-за календаря.

## 2. B135: все присутствующие declarations сверяются до fallback

`resolve_transfer_context` использует `model_fields_set` typed contexts; mappings считаются явными по наличию keys. Проверяются outer aliases, nested policy_search_context, nested TransferContext и explicit keyword declarations. Противоречие даёт typed `TransferScopeRefusedError`, а не выбор удобного truthy значения. Fallback run ID применяется только при отсутствии declaration. [S01:349–619]

* **P01:** object и JSON `discovery / education / r` разрешаются одинаково, timestamp сохранён.
* **P02:** не заданные typed defaults можно заполнить explicit discovery/education; действительно неизвестная область получает `isolated::fallback`.
* **P03/P04:** конфликт domain, пустой mapping context, invalid wrapper, пустой domain и текстовый bool не становятся defaults.
* **P05:** через declared live-owner fixture tenant hash берётся у owner, чужой hash отвергнут. Это не настоящий security authentication test.
* **P06:** serialized `authenticated` без live owner становится UNKNOWN, а не полномочием.

Sourceplan допускает «разрешённый override», но нынешний resolver не является API произвольной смены области: конфликт explicit значений намеренно fail-closed. Чтобы изменить предметную задачу, caller должен предъявить согласованный новый context у действительного owner. Восстанавливать старую silent precedence ради sourceplan wording не требуется.

Scope locator v3 является digest полного typed source body; чтение сверяет path/body/index/card. Locator не декодируется обратно в tenant authority. **P20** действительно меняет body domain в локальном index file: subsequent query отказывает с path-body mismatch. [S01:210–290; S02:953–998,1538–1627]

## 3. B136: source selection и effective result filter больше не расходятся

`_entry_matches` использует общий `_matches_query`, но не доверяет index trust/source-run: effective card ещё будет прочитана. `_revalidate_transfer` проверяет исходный card, включая source_run_id и content selectors. `materialize_transfer` заново разрешает persisted source binding, applies current age, не повышает уже пониженный caller grade, вычисляет transfer weight и проверяет final trust/confidence **до `record_local`**. [S02:638–870,1138–1315,1362–1371]

Final query сохраняет весь набор source candidates до projected quality filter; direct `find_transfer_candidates` остаётся bounded inspection. Source domain выбирает исходную карточку, target context — namespace назначения. После сохранения обычный local query правильно проверяет target domain; origin_domain остаётся происхождением, не скрытым override запроса.

**P07–P09:** weak confidence, запрещённый resulting trust и wrong source_run возвращают []; дополнительных CAS writes нет. **P10:** разрешённый .9 source переносится в labor как TRANSFERRED, weight .65, source_run_id=source и origin_domain=fiscal сохраняются после fresh registry. **P11:** raw top candidate не подходит по effective trust; final limit=1 заполняется следующим подходящим old/low_confidence кандидатом, а не пустеет. **P15:** caller-demoted .3/LOW_CONFIDENCE не повышается. **P16:** после invalidation сохранённый ранее candidate больше не materializes; source binding missing, новых writes нет. **P22:** другой tenant не допускается из-за local miss.

Всё это исполняет реальные complete functions, включая real local namespace/index files, но содержимое CAS и live owner seam — fixtures. Нельзя выводить из label equality действительное межтенантное право либо подтверждённую causal переносимость.

## 4. B137: чтение перестало омолаживать основание

`_evidence_anchor` использует max(entry.last_seen, card.created_at), **никогда last_accessed_at**. `_materialize_query_card` вычисляет возраст, понижает trust и caps confidence до .5. `_record_access` пишет отдельный opaque file не чаще раза в сутки; `_load_index_file` восстанавливает его только как retention clock. [S02:1210–1252,1373–1417,1569–1590]

* **P12:** 100-дневная .9/local карточка → .5/low_confidence при cold, повторном и fresh registry query; строгий .8/local запрос остаётся пустым.
* **P13:** три fresh-reader запроса — **0 новых CAS writes**, исходные index bytes неизменны, один access sidecar write. Настоящие временные файлы/fsync/replace исполнены; crash durability целиком не проверялась.
* **P14:** transfer старой карточки сохраняет created_at, .5 и low_confidence при fresh target read; weight .325 отдельно показывает scope/age discount.
* **P19:** новый producer record создаёт другой card ref и сохраняет обе версии в card_refs. Это проверка versioning, **не подтверждение, что producer выполнил эмпирическую ревалидацию**.

### C27-R01 — sibling pattern/report projection обходится без effective age

**Важность:** низкая диагностическая; это не право promotion.

`top_patterns` проецирует raw `entry.confidence/trust_level`, не вызывая effective-age materialization. `_resolve_top_lessons` для registry вызывает этот метод; для persisted snapshot делает аналогичную raw projection. [S02:872–907; S05:252–281]

**P17:** для одного 100-дневного основания actual query возвращает **.5/low_confidence**, `top_patterns` и actual calibration snapshot projection — **.9/local**. Ref одинаков. `build_calibration_report` сохраняет эти patterns в `top_lessons`; это sibling visible DTO surface, а не новое измерение. [S05:79–183]

Историческая .9 может быть полезна как исходная оценка, её нельзя стирать. Остаток — явно отделить historical grade от current effective grade либо использовать общий existing effective projection. Last_seen в pattern помогает увидеть возраст, но не объясняет, что одно и то же поле `confidence` имеет другой clock, чем в query. Основной lifecycle consumer с настоящим LessonRegistry выбирает `query_with_transfer`, **не** fallback `top_patterns`: **P21** подтверждает limited trust в actual hint payload. Поэтому весь search не объявлен потребителем завышенного report grade.

### C27-G01 — source aggregate anchor не связан с target readback

Existing dedup сохраняет max last_seen по source entry, даже когда последним выбран более старый card. При transfer effective freshness может основываться на более новом source occurrence, но materialized card сохраняет старый created_at, а target entry получает этот старый timestamp.

**P18:** новый и затем 100-дневный card одной signature → немедленный transfer **.9/transferred**, fresh target read **.5/low_confidence**, тот же lesson ID и created_at. Существующий `test_transfer_older_selected_card_keeps_conservative_restart_age` прямо ожидает это консервативное readback. [S02:510–565,804–870; S03:1698–1748]

Это не разрешение вернуть .9 после restart и не утверждение, что новое occurrence является достаточным новым доказательством. До полного закрытия нужен согласованный owner-bound evidence anchor: либо уже первоначально выдать консервативный grade выбранной карточки, либо переносить и разрешать настоящее основание более нового assessment через существующие refs. Простая передача last_seen=now повторила бы исходный дефект. Текущий safe limitation сохранён, но требование одинаковой содержательной степени актуальности при handoff/readback пока не выполнено полностью.

### C27-R02 — naive timestamp проходит typed boundary и ломает age computation

**Важность:** низкая доступность для некорректного внешнего времени; не security bypass.

`TransferContext.timestamp` — обычный datetime без timezone constraint; resolver принимает `2020-01-01T00:00:00`. При иначе совместимой scope `compute_provenance_weight` вычитает его из aware target time и получает `TypeError: can't subtract offset-naive and offset-aware datetimes`. **P23**, actual DTO/resolver/weight function. [S01:55–71,310–346,414–419]

Нормальные producers используют UTC-aware now и этот случай не создают. Внешний JSON/typed caller может его передать без refusal. Нужен единый контракт: отказ с адресной причиной либо документированная нормализация, но не угадывание timezone в научном evidence time. Аналогичные datetime поля LessonCard/IndexEntry также требуют согласованной qualification; весь их набор не объявлен исчерпывающе протестированным.

## 5. Настоящие producers и потребитель, не только registry API

Orchestrator `_maybe_record_lessons` вызывается для terminal ticket и не повторяется после lessons_finalized. Failure route сохраняет typed failure/remediation/evidence refs и trace; success route требует complete, L4 promising и admitted AVAILABLE score перед созданием lesson. Producers используют эвристический confidence (severity-based 1/.75 либо success .8); это не empirical posterior. [S02:313–430; S04:2221–2290]

SearchController теперь facade единственного `_SearchLifecycleOwner`; реальный `_build_lesson_hints` находится в lifecycle.py. Он вызывает transfer-aware query с threshold .5 и передаёт compact trust/provenance/domain/task fields в generation context. **P21** исполняет этот actual method с actual registry. LLM/whole search loop не запускались. [S06:1451–1485; S07:1241–1288]

**C27-G02:** native Core schema/profile custody, live authenticated scope и полный funnel→persisted lesson→fresh native search consumer должны быть проверены в supported profile. Отдельно квалифицировать фактическую producer/evidence ревалидацию и смысл TTL для класса знания. Новый ref/created_at или internal confidence сам по себе не доказывает empirical applicability. Существующие owners и links пригодны; новый универсальный lesson approval subsystem не требуется.

## 6. Tests, execution history и завершение очереди LANE-02

Complete lessons.py (1656 строк) и transfer_context.py (731 строк) прочитаны. Existing `test_lesson_transfer.py` прочитан в указанных source-index диапазонах: typed/malformed/auth context, filters, quota, age/read/restart/transfer, invalidation и source-run/target separation. Все 1961 строки целиком не заявлены прочитанными. `test_trn_03.py` не найден; sourceplan предлагал имя, а не доказал его существование.

Первый audit run: **22 MATCH, 1 ERROR**. P23 ошибочно сравнивал разные tenant scopes, поэтому функция правильно вернула zero weight до subtraction; ожидаемая ветвь не была достигнута. Исправлена только fixture scope на одинаковую, без ослабления проверки; второй полный запуск **23 MATCH, 0 ERROR**. Оба logs сохранены. pytest, native CAS/auth и эмпирическая валидность не исполнялись. MATCH включает подтверждённые дефекты и не равен product PASS.

[Диагностика](../04_Проверки/C27_TRN03/bounded_diagnostics.json) · [команды](../04_Проверки/C27_TRN03/commands.json) · [границы](../04_Проверки/C27_TRN03/Чтение_и_границы.md) · [источники](../05_Источники/C27_источники.json) · [остатки](../01_Реестры/C27_остатки.json).

**27/127 пакетов рассмотрены ограниченно; 73 уникальных B/LA частично оценены; полного закрытия нет.** LANE-02 пройдена по порядку; аудит продолжается с **EMP-01 / B16, B31, B33**, не останавливается на границе очереди.
