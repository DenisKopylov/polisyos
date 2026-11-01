# OBS-01 — календарная проекция observation periods

## 1. Решение

**Ограниченно оценён, не закрыт. Новый подтверждённый product defect не установлен.** Исходный B146 исправлен в проверенном корпусе: leap February, invalid month, missing/malformed и недостаточная точность больше не превращаются в январь2025, clamp или выдуманный месяц. Canonical observation owner и явные callers присутствуют; consumer повторно вычисляет projection, а не доверяет marker.

Свежий результат: **5 bounded MATCH;14 unchanged bodies /22 cases PASS;720 дополнительных calendar inputs**. На500 repeated rows выполнено4 distinct parser calls. Whole period owner настоящий, callers и Scientist consumer — complete unchanged AST functions; native full Parquet/CAS/governance pipeline не заявлен.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/OBS-01_исходные_строки.txt) · [Pinned sources](../05_Источники/C84_источники.json).

## 2. Матрица исходных IDs

| ID | Проверенный результат | Остаток |
|---|---|---|
| B146 | Calendar-inclusive bounds; missing/invalid/limited distinctions; no2025 fallback/clamp; unique precompute; version marker; actual consumer recomputation/refusal | Native pipeline G01; actual historical reevaluation G02 |
| LA-031, observation phase | Один предметный owner, explicit source/demography imports, compatibility aliases source-traced | Full facade/import activation не проверена; shared C83-R01; IO/bindings остаток UDF-02/G03 |
| LK12 | Actual read API owner routing/verified Parquet bridge сохранены | JSON diagnostic не подменяет content-bound read API/native CAS |

Relocation и behavior repair не смешаны: изменение конца февраля2024 с28 на29 — намеренное исправление, не byte-equivalent перенос. Старый `MONTHLY_END_MONTH` остаётся compatibility constant, но actual parser использует calendar-aware calculation. Current-state аудит не доказывает, в каких отдельных исторических commits были выполнены move/fix.

## 3. Producer → projection → consumer

`observation.py` распознаёт объявленные year/quarter/month/date-shaped formats, проверяет calendar range и достаточность точности для M/Q/Y. Year/quarter не превращаются в month. Series boundary возвращает aligned start/end/disposition/reason; invalid и missing сохраняют typed absence, repeated keys вычисляются один раз. Positional reconstruction сохраняет duplicate index labels (`S01`).

Actual source frame producer переносит эти поля и `ukraine_observation_period_v1` в каждую observation row. Household cell/panel producer использует тот же owner, а для unresolved periods не проставляет regime. Graph helper исключает edges без пригодных periods вместо default-year substitution (`S02`–`S04`). Сами source/household frames являются промежуточными таблицами; missing bounds не объявлены готовыми `ObservationRecord`, чья actual DTO требует date и monotonic interval (`S08`).

Scientist получает admitted Parquet bytes через existing read API и вызывает `_reconcile_ukraine_period_projection`. Reconcile сохраняет original input, заново вычисляет source period IDs, сверяет declared projection fields/version и отказывает при mismatch. Старые строки без reconstructable period facts получают `not_established/legacy_unavailable`, а source version не переписывается. Actual family gate снижает unresolved families до diagnostic tier и не даёт exact signoff (`S09`).

**Выполнена selected mathematical/DTO/caller chain с собственной persisted JSON table; actual Parquet/CAS orchestration лишь прослежена по source.** Typed calendar validity не является подтверждением истинности измерения, representativeness, идентификации причинного эффекта или admission политического решения.

## 4. Свежие проверки

1. **P01:**10 selected OBS bodies/18 parameterized cases,1 existing builders format body и3 existing Scientist consumer bodies — всего14/22 PASS. Проверены leap/ordinary/month/quarter/year, invalid/missing, duplicate/reordered indices, actual source/household/graph callers, marker forgery, legacy/no-ID limits и repeated reconciliation.3 native facade/import-alias tests сознательно не выполнялись.
2. **P02:**720 calendar inputs по6 accepted формам и10 годам, включая1900/2000/2100 и крайние supported годы. Независимый oracle — первый день следующего месяца минус день, не тот же monthrange.8 invalid/out-of-range controls отвергнуты. Включительность end проверена как день перед началом следующего периода.
3. **P03:**500 rows с duplicate labels:100 valid,100 invalid,100 missing,200 limited. Actual parser вызван только для4 unique non-missing identifiers; только valid rows получили dates.
4. **P04:** actual frame producer → собственная pandas JSON table → actual selected reconcile/family gate. Mixed unresolved cohort имеет tierB и `exact_signoff_eligible=False`; tampered leap end и unknown projection version отвергнуты. Source version сохранена. Эта table не выдаётся за actual Parquet/CAS output.
5. **P05:** legacy без period ID не повышается до valid, старые bounds остаются явно unestablished. Когда исходный period ID есть, consumer строит derived corrected leap bound с provenance `recomputed_from_period_id`; original frame и source version неизменны. Это не переписывание происхождения старого artifact.

## 5. Что сохранить и что осталось

**Сохранить:** canonical calendar owner, explicit caller routing, unique cache, inclusive bounds, distinct missing/invalid/limited, positional row identity, version marker, consumer recomputation/negative controls и purpose-limited read API. Не менять fixed2025 на now, не clamp-ить malformed periods и не приписывать synthetic calendar tests empirical authority.

**C84-G01 — native pipeline.** В supported environment повторить real facade/source/household→Parquet→verified CAS snapshot→Scientist consumer, включая corruption/absence/reordering. Shared LANE-07 test может обслуживать UDF-01/OBS-01/UDF-02/OBS-02 без дублирования тяжёлой инфраструктуры. Import isolation C83-R01 остаётся тем же finding, не новым R. Full reader continuation B147 относится к OBS-02; текущий spy/cache test не доказывает Parquet reader.

**C84-G02 — historical reevaluation.** Current code поддерживает versioned derived projection и честную legacy limitation, но реальные затронутые outputs/dependent evaluations не инвентаризированы и не переоценены. Сохранять original bytes/source versions, адресно строить новые derived views/artifacts через existing owners. Доля invalid/missing данных и прохождение исторических normalizers неизвестны.

**C84-G03 — LA-031 lifecycle.** Observation phase не закрывает remaining I/O/bindings/facade. Сохранить compatibility symbols до actual caller qualification; не удалять весь common или fixed table только по наличию нового parser. Следующий пакет UDF-02 продолжает эти обязанности.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C84_OBS01/commands.json) · [Diagnostics](../04_Проверки/C84_OBS01/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C84_OBS01/native_verification.json) · [Остатки](../01_Реестры/C84_остатки.json).

Run01 exit0:5 MATCH,22/22 selected cases. Whole period module за builders shell; actual SourceConfig/IR enums native. Caller/consumer functions выбраны целиком unchanged AST, exact ranges сохранены. Native ordinary observation import BLOCKED в eager parent/Core syntax stack; native pytest и PyArrow отсутствуют, supported baseline не достигнут. Actual native Parquet/CAS/governance не запускались. Pandas FutureWarnings сохранены, не скрыты.

Checkout чист; source/tests/dependencies не менялись; реальные datasets/servers не использованы.720 calendar inputs — дополнительные diagnostics, не720 независимых product tests.

**84/127 рассмотрены ограниченно. Следующий — UDF-02. Фаза 2 не начата.**
