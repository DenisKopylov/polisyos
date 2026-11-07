# OPT-04 — привязанный champion и compare-and-publish
## C21 · 31 октября 2026 года

**Исходные IDs:** B116, B117. **Порядок:** 21/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; source/tests/config/dependencies не изменены. Далее — FUN-01.

## Решение

**Частичная оценка.** Исходный B117 отремонтирован на уровне рассмотренного локального filesystem-owner: настоящий `fcntl.flock` охватывает чтение текущего pointer, сравнение и публикацию. Управляемый опыт с **двумя процессами** сохранил score=3; удаление только lock в памяти восстановило старый overwrite до 2. Atomic replace больше не служит единственной защитой сравнения.

B116 тоже существенно изменён: несовпадающие candidate, loop, policy loop, split и suite/basis отвергаются; selected manifest profile входит в идентичность. Но **C21-R01**: действующий comparison profile incumbent не сверяется с новой policy. Та же suite допускает сравнение holdout-метрики прежнего champion с selection-метрикой нового либо смену metric/direction/unit без отдельного перехода.

**19 ограниченных observations MATCH, 0 ERROR.** Исполнены полный AST registry, настоящие определения ArtifactID/ArtifactRef/InputRef и выбранные Pydantic DTO, настоящий локальный файловый ввод-вывод и межпроцессный flock. CAS/store/loaders — явные фикстуры. Native PolicyOS/CAS/pytest, HTTP/LLM, trusted-executor и специализированная claim authority — **UNRUN**. Ни техническое улучшение, ни наша фикстура не дают права внешней публикации.

## 1. Требование и содержательная способность

[Исходный OPT-04](../05_Источники/OPT-04_исходные_строки.txt) требует, чтобы лучшее число относилось именно к выбранному кандидату и испытанию и чтобы оно сравнивалось с действительно актуальным predecessor. Это два независимых вопроса: предметная сопоставимость и атомарность перехода. Lock не делает разные единицы сопоставимыми; верная метрика не устраняет гонку.

LLM может предложить новое пространство или критерий. Слой выбора должен сохранить этот смысл и отдельно установить допустимый переход comparison basis. Не требуется запретить развитие suite или цели; нельзя молча считать старое число измерением на новой базе. Technical champion остаётся внутренним результатом, не институциональным полномочием исполнения политики.

| ID | Уже сделано — сохранить | Конкретный остаток |
|---|---|---|
| B116 | Candidate/evaluation/policy loop binding; typed split; suite ID/version и selected lineage edges; чужая profile не принимается за ту же ref; отдельный MethodJob source/provenance guard | C21-R01: сравнить полный активный comparison profile incumbent с новой policy или сделать явный переход с переоценкой. Native evaluator→CAS→registry→loader qualification |
| B117 | Cross-process lock на loop; актуальный predecessor читается под lock; запись fsync+replace; claim pointer+basis в одном envelope | Квалифицировать настоящие consumers, specialised claim admission, deployment filesystem и аварийную долговечность; локальная гонка в проверенном профиле не воспроизводится |

## 2. B116: нынешний registry не доверяет отдельно переданным refs вслепую

`consider_promotion` сначала загружает evaluation, а под `_promotion_lock` читает current и выполняет `_promotion_binding_failure`. Проверяются policy loop, evaluation loop, полный candidate identity, наличие suite, runtime split, suite ID/version и единственные точные candidate/suite input edges. [S01:588–722]

`artifact_ref_identity_key` использует content ID, kind, media type и selected manifest profile. P08 с одинаковыми bytes и другой выбранной profile получил `evaluation_candidate_mismatch`. Это настоящее тело core identity helper и настоящие Pydantic refs, хотя manifest/store не являются настоящим CAS. [S03:219–320]

Исполненные отрицательные случаи:

| Вход | Наблюдаемая причина | Pointer |
|---|---|---|
| Evaluation A передана с candidate B | evaluation_candidate_mismatch | Не появился |
| Чужой evaluation loop | evaluation_loop_mismatch | Не появился |
| Чужой policy loop | policy_loop_mismatch | Не появился |
| Несовпадающий runtime split | runtime_split_mismatch | Не появился |
| Другая suite ID | suite_mismatch | Не появился |
| Та же suite ID/version, иной content basis | suite_basis_mismatch | Не появился |
| Те же candidate bytes, иной selected profile | evaluation_candidate_mismatch | Не появился |

Это P02–P08, не доказательство tenant/authentication/CAS bypass или независимой верификации источника. P19 сохранил существующий `evaluation_not_promotable`. P01 показал полезный положительный путь: 1→3 проходит, последующий 2 получает `not_better_than_champion`; новый reader читает score=3 из настоящего pointer-файла.

Для existing champion дополнительно сверяются suite ID/version/ref. Unknown seeded basis не принимается за совместимую; changed suite не запрещена навсегда, но требует явного способа перехода. [S01:750–805]

## 3. C21-R01 — stored comparison policy не связывает следующее сравнение

**Тип:** подтверждённый локальный дефект полноты comparison binding; **важность:** средняя, условная; **уверенность:** высокая для generic registry-пути.

Новый pointer сохраняет `promoted_by_policy` и `compare_split`. Однако при следующем вызове incumbent проверяется по suite, затем `current.metrics.get(policy.primary_metric)` читается уже через **новую** policy. Сохранённые split/direction/unit/metric в этом сравнении не используются. [S01:750–805,859–901]

### Различающие наблюдения

* **P09, split:** первый champion — holdout score=10; тот же suite ref, новая evaluation имеет selection score=20 и новая policy selection. Новый кандидат promoted; сравнение прошло против старого holdout=10, без переоценки incumbent на selection.
* **P10, metric:** у incumbent сохранён только score=10. Новая policy выбирает other, новый other=−999. `current.metrics.get('other')` даёт None; проверка улучшения пропущена и кандидат promoted. Это не утверждение, что −999 всегда хуже: предыдущего сравнимого измерения вообще нет.
* **P11, direction:** при том же suite maximize сменён на minimize, новый score=1 заменяет старый 10 без отдельного comparison transition. Само новое предпочтение может быть допустимо; не установлена история перехода базы.
* **P12, unit:** generic policy USD сменена на EUR, число 20 заменяет 10. Реальный валютный источник, преобразование или MethodJob authority не моделировались; это точная проверка отсутствия policy-binding guard, не доказательство финансового вреда.

Последствие — цепочка champion становится неоднородной: «лучше» больше не имеет одного установленного смысла. Существенен уже finite split-контрпример, не зависящий от NaN, corrupted files либо GP backend.

**Минимальное направление:** сопоставить incumbent с эффективной metric/split/direction/unit basis до численного сравнения. Новая обоснованная постановка должна иметь явный переход: переоценка incumbent на новой базе либо отдельная начальная точка сравнения. Не возвращать неизвестное прежнее значение как 0, не запрещать все изменения policy и не строить второй registry. Использовать уже сохранённую policy и реальные evaluator/suite owners. Нужен distinguishing test именно последовательности двух разных policies, а не ещё один неверный split только у одной evaluation.

Specialised claim policy имеет отдельное точное сравнение с canonical policy и не объявлена уязвимой тем же способом. [S01:736–747]

## 4. B117: compare и publish теперь действительно в одной критической секции

[Lock, S01:943–952](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/registry.py#L943-L952) использует стабильный `champion.lock` в каталоге loop. Evaluation загружается до lock; current read, binding checks и `_consider_promotion_locked` находятся под ним. `seed_baseline` и публичный generic `write_pointer` также пользуются этим lock. Дорогой evaluator в настоящем `SearchLoopRunner` выполняется до вызова registry. [S01:563–649,981–991; S06:1940–2040,2306–2320]

### P15: два процесса, а не только два объекта

Изначально score=1. Процесс slow со score=2 остановлен после чтения predecessor внутри lock. Fast со score=3 начинает вызов; до освобождения slow его predecessor read не происходит. После разрешения slow публикует 2, затем fast читает **2**, сравнивает и публикует 3. Оба child exit codes=0; fresh reader видит 3.

### P16: removal control

Тот же corpus и порядок событий, но в отдельном audit-профиле `_promotion_lock` заменён на no-op только в памяти дочерних процессов. Fast читает 1 и публикует 3 до освобождения slow; slow затем публикует 2, всё ещё считая predecessor=1. Fresh reader видит 2. Source checkout не изменялся. Контроль показывает, что опыт действительно различает исходный lost-update, а не всегда выдаёт удобный итог.

Это настоящее поведение POSIX flock и atomic file replacement в данной среде с fixture CAS. Оно не устанавливает семантику network filesystem, нескольких машин или всех deployment profiles. Новый распределённый registry ради этого не нужен.

## 5. Публикация, predecessor и специализированная authority

`_write_json` пишет временный файл в том же каталоге, flush+fsync, затем `os.replace`. P17 инъецировал ошибку непосредственно в replace: старые pointer bytes остались неизменны. Это тест отказа **до** замены, а не power-loss/crash-recovery эксперимент. fsync родительского каталога здесь не выполняется; durability конкретной deployment filesystem отдельно не установлена. [S01:993–1006]

Для claim path pointer и promotion_basis теперь сериализуются в один `claim-champion-envelope.v1`; predecessor reader понимает embedded basis и требует совпадения pointer. Это устраняет необходимость синхронно публиковать два отдельных файла для нового формата. Исторический отдельный basis читается как legacy путь. Проверка подписи/appointment/expiry и protected consumer находится у существующего claim verifier. Эти ветви прочитаны, но **не исполнялись в C21**. [S01:903–929; S08:481–577]

MethodJob guard намеренно не выдаёт self-consistent result graph за trusted execution provenance: `_methodjob_execution_provenance_failure` возвращает `methodjob_execution_provenance_not_established`. Source admission дополнительно пересчитывает dispatch, input/data basis, metric, units и summary. P14 только показал, что наличие неполного MethodJob claim не пролезает через generic branch. Полный MethodJob verifier не исполнялся и не объявлен проверенным этим опытом. [S01:143–529]

Не снимать эти guards ради promotion и не выводить право внешней записи из лучшего score. Audit не создаёт новый институциональный допуск.

## 6. Существующие tests и настоящий consumer

Найденные `test_registry_and_runner.py` содержат candidate/loop/policy/suite/profile/split negatives, bound promotion over unknown seed denial, controlled two-thread race и evaluator-from-foreign-suite отказ. `test_search_loop_runner_promotes_and_runtime_loader_reads_champion` проверяет actual runner/loader. Их assertions прочитаны; project pytest отсутствует, поэтому ни один test не объявлен выполненным. [S05]

Runtime producer сохраняет candidate/evaluation с source edges, вызывает registry, а в StageB возвращает точную promotion decision. `ChampionBackedRuntimeLoader` читает текущий pointer и разрешает выбранный candidate model. Это существующий путь поставки технического результата, не необходимость нового publisher. [S06:152–227,1940–2040,2306–2362]

## 7. Остальные границы

**C21-G01 — native/source/authority qualification.** Реальный CAS canonical profile, source signatures, MethodJob admission, claim evaluator appointment и HTTP authorization не выполнялись. Наш in-memory store знает только fixture payloads и lineage. Genuine DTO/ArtifactID execution не равен genuine evidence source.

**C21-G02 — seeded baseline и полезный следующий шаг.** `seed_loop_baseline` создаёт seeded baseline без suite ID/ref в pointer metadata, если caller отдельно их не передал. P13 подтвердил правильный отказ последующего сравнения `champion_suite_basis_unknown`. Для normal loader-first сценария нужен существующий путь связывания/переоценки baseline на активной suite. Это content-capability qualification, не предложение убрать защиту или объявить baseline измеренным. [S06:152–217]

**C21-G03 — finite guard локально не автономен.** P18 на fixture-store, разрешающем NaN source, получил promoted bootstrap и null в pointer JSON, после чего настоящий Pydantic reader отказал. Но штатные persist helpers используют `CanonSpec(forbid_floats=False)` с default `forbid_nan_inf=True`; настоящий CAS admission не проверялся. Поэтому это характеристика прямого registry API/producer assumptions, **не доказанный достижимый native дефект**. Не дублировать как ещё один баг B116 без source-bound replay. [S02:1015–1043; S03:40–51]

**C21-G04 — crash/durability и lifecycle.** Проверены процессы, локальный lock и replace failure, но не power loss, platform portability либо forced termination на всех границах. Аварийная согласованность специализированного envelope требует отдельного actual consumer test.

## 8. Доказательства и продолжение

Полный registry AST сверён с Git blob; целиком прочитан исходный registry. Actual ArtifactID, InputRef, ArtifactRef и identity helper взяты из source; actual выбранные Pydantic DTO исполняются на Pydantic 2.13.4 / Python 3.12.14. Project imports, artifact loaders/store и специализированный claim reader заменены явно. Никаких зависимостей не установлено; checkout остаётся чистым.

Команда: `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 probe_opt04.py`. Exit 0, 19 MATCH/0 ERROR. Все дочерние процессы завершены, временные fixture-файлы удалены самим harness. Исходные код/тесты не менялись; deciding outputs и source identities сохранены.

[Протокол](../04_Проверки/C21_OPT04/bounded_diagnostics.json) · [команды](../04_Проверки/C21_OPT04/commands.json) · [границы](../04_Проверки/C21_OPT04/Чтение_и_границы.md) · [источники](../05_Источники/C21_источники.json) · [остатки](../01_Реестры/C21_остатки.json).

**21/127 пакетов рассмотрены ограниченно; 53 уникальных B/LA частично оценены; полного закрытия нет.** 20 предыдущих packet reports/evidence сохранены. Следующий — **FUN-01 / B156, B158, B159**.
