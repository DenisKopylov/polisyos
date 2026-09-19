# Индекс совместной очереди E02

127 рабочих пакетов; 225 B и57 LA учтены раздельно. 12 lanes — не обязательные глобальные фазы.

## LANE-01 — Пользовательский цикл и явное N7 требование

REQ-01 → ACQ-01; CYC-03 → ACQ-01. Остальной цикл идёт по собственным prerequisites, не ждёт общего завершения legacy.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [CYC-01](bundles/CYC-01.md) | Штатный вход и связанные контексты N4/N5 | B01, B02, B03 | — | нет | CP1/L |
| [REQ-01](bundles/REQ-01.md) | DataRequirement: явный контекст и ограниченная private-очистка | — | LA-045, LA-046 | нет | CP1/L |
| [CYC-03](bundles/CYC-03.md) | Идентичность содержательной второй итерации | B09, B27, B28 | — | CYC-01 | CP1/L |
| [ACQ-01](bundles/ACQ-01.md) | N7: типизированное требование → acquisition → re-entry | B12 | LA-046 | REQ-01, CYC-03 | CP1/L |
| [CYC-04](bundles/CYC-04.md) | Пригодные альтернативы и исследовательский бюджет | B10, B11 | — | CYC-03 | CP1/L |
| [CYC-02](bundles/CYC-02.md) | Читаемый численный результат и положительный условный N8 | B04, B05, B08 | — | CYC-01, SIM-01, SIM-02, SIM-03 | CP1/N |
| [CYC-05](bundles/CYC-05.md) | Правдивые лимиты, завершение и структурная проверка | B15, B29, B30 | — | CYC-02, CYC-03 | CP1/L |
| [SIM-01](bundles/SIM-01.md) | Полный выбор движка и верная история fallback | B06, B07 | — | нет | CP1/L |
| [SIM-02](bundles/SIM-02.md) | Выходы, конфликты атомов и покрытие траекторий | B18, B20, B22 | — | нет | CP1/L |
| [SIM-03](bundles/SIM-03.md) | Контрасты, реплики, SMM и экономия одинаковых расчётов | B19, B21, B23, B25, B26 | — | SIM-02 | CP1/N |
| [SEL-01](bundles/SEL-01.md) | Singleton, eligibility и неизменные требования выбора | B34, B35, B36 | — | нет | CP1/L |

## LANE-02 — Search state → adapters → actual autotune consumer

CTL-01 → CTL-03 → SRV-01 → SRV-03. OPT/RNG/funnel пакеты поставляют исправленные contracts; совместная приёмка не требует одинакового старого ошибочного результата.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [CTL-01](bundles/CTL-01.md) | Search run-state: исправление fresh/empty и извлечение владельца состояния | B118, B119 | LA-015 | OPT-01 | CP3/L |
| [CTL-03](bundles/CTL-03.md) | Search transition: стоимость, счётчики и typed eligibility | B120, B121, B123 | — | CTL-01 | CP3/L |
| [SRV-01](bundles/SRV-01.md) | SearchService: чистые contracts и один ask/tell state transition | — | LA-014 | CTL-03 | CP3/L |
| [SRV-03](bundles/SRV-03.md) | Autotune: native SearchService driver и ограниченный cutover | — | LA-015 | SRV-01, CTL-02, STP-01 | CP3/N |
| [CTL-02](bundles/CTL-02.md) | Содержательные даты и воспроизводимый RNG/checkpoint | B124, B125, B126 | — | OPT-02 | CP3/L |
| [STP-01](bundles/STP-01.md) | Актуальный convergence-сигнал и плато около нуля | B41, B122 | — | нет | CP3/L |
| [OPT-01](bundles/OPT-01.md) | Метрика, полная координата и строгий Pareto | B108, B109, B110, B111 | — | нет | CP3/L |
| [OPT-02](bundles/OPT-02.md) | Настоящий SearchSpace и координаты фактического исполнения | B112, B113, B127 | — | OPT-01 | CP3/L |
| [OPT-03](bundles/OPT-03.md) | Рабочий warm-start и сохранённое GP-состояние | B114, B115 | — | OPT-02 | CP3/N |
| [OPT-04](bundles/OPT-04.md) | Привязанный champion и compare-and-publish | B116, B117 | — | OPT-01, OPT-02 | CP3/L |
| [FUN-01](bundles/FUN-01.md) | Версионный ticket и одинаковое full/split продолжение | B156, B158, B159 | — | CTL-03 | CP3/L |
| [FUN-02](bundles/FUN-02.md) | Изоляция reduced-config и правдивый результат воронки | B157, B160, B162, B165 | — | FUN-01 | CP3/L |
| [FUN-03](bundles/FUN-03.md) | Текущее знание, calibration routing и pre-commit ограничение | B161, B163, B164 | — | FUN-02 | CP3/L |
| [TRN-01](bundles/TRN-01.md) | Численный transfer без фиктивного benchmark | B128, B130, B131, B132 | — | OPT-02 | CP3/L |
| [TRN-02](bundles/TRN-02.md) | Точные snapshot-refs и атомарное поколение vector memory | B129, B133, B134 | — | нет | CP3/N |
| [TRN-03](bundles/TRN-03.md) | Контекст переноса, фильтры lessons и время подтверждения | B135, B136, B137 | — | нет | CP3/L |

## LANE-03 — Empirical scope, calibration и S10 — без смешения ролей

B32+LA-051 в FRC-01; затем FRC-02 после PCL-01/EMP-01. LA-052/053 в одном test/owner пакете; backtesting не переносится целиком.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [EMP-01](bundles/EMP-01.md) | Область эмпирических данных, ValueOuterSet и selection diagram | B16, B31, B33 | — | CYC-01 | CP1/L |
| [FRC-01](bundles/FRC-01.md) | S10: реальные времена и запрет выдуманного calibration pass | B32 | LA-051 | CYC-01 | CP1/L |
| [PCL-01](bundles/PCL-01.md) | Предиктивная калибровка: знаменатель, receipt и canonical tests | — | LA-052, LA-053 | нет | CP3/N |
| [FRC-02](bundles/FRC-02.md) | S10: один действительный calibration producer и связанный forecast | — | LA-051 | FRC-01, PCL-01, EMP-01 | CP4/N |
| [BKT-01](bundles/BKT-01.md) | Фактический historical view, тип прогноза и реплики | B166, B169, B170 | — | нет | CP3/L |
| [BKT-02](bundles/BKT-02.md) | Полнота сравнения, nominal coverage и micro/macro | B167, B168, B171 | — | BKT-01 | CP3/L |
| [BKT-03](bundles/BKT-03.md) | Описательное смещение и честный статистический backend | B172, B173 | — | BKT-02 | CP3/L |
| [BKT-04](bundles/BKT-04.md) | Только выбранные CV-разбиения и разрешённая bootstrap-статистика | B174, B175 | — | нет | CP3/L |

## LANE-04 — Compile/runtime владельцы, baseline-модели и executable plans

FRY-01 → FRY-03 → ECO-01; PLG-02 → PLG-03. CMP/JIT правятся независимо, но после принятого move читают актуальный path map.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [FRY-01](bundles/FRY-01.md) | Foundry compile/catalog: randomization, families и прямой IR layout | — | LA-001, LA-002, LA-037 | нет | CP1/N |
| [FRY-03](bundles/FRY-03.md) | Fiscal/labor: эквивалентный перенос живых PatchMap kernels | — | LA-003 | FRY-01 | CP4/N |
| [ECO-01](bundles/ECO-01.md) | Два economic профиля и предметный baseline objective | — | LA-004, LA-035 | FRY-03 | CP4/N |
| [PLG-01](bundles/PLG-01.md) | DomainPlugin: общая discovery-механика без смены ABI | — | LA-022 | нет | CP4/L |
| [PLG-02](bundles/PLG-02.md) | PolisySimulator: честный rollout result вместо псевдообучения | — | LA-023 | нет | CP4/L |
| [PLG-03](bundles/PLG-03.md) | Один DomainPlugin → существующий trainer: реальный learning bridge | — | LA-023 | PLG-02 | CP4/N |
| [CMP-01](bundles/CMP-01.md) | Импорт, effective DAG и единый payload исполнителей | B42, B43, B44 | — | нет | CP1/L |
| [CMP-02](bundles/CMP-02.md) | Однозначные slots и ordering по occurrence | B45, B46 | — | CMP-01 | CP1/L |
| [CMP-03](bundles/CMP-03.md) | Полное и семантически одинаковое ручное/автоматическое связывание | B47, B48 | — | CMP-02 | CP1/L |
| [JIT-01](bundles/JIT-01.md) | Правильный warm kernel, single-flight и дешёвая подготовка | B49, B50, B53 | — | нет | CP1/N |
| [RES-04](bundles/RES-04.md) | Точный Foundry checkpoint и неизменяемые sidecars | B74, B75, B76 | — | CMP-02 | CP2/N |
| [CAL-05](bundles/CAL-05.md) | Неактивный механизм не вычисляется как активный | B185 | — | нет | CP4/N |

## LANE-05 — Causal shared helpers, wrappers и model/query

GRF-01 включает только три пустых sibling .py вместе с примитивами B216/217. CAU-01 metadata-detachment → общие estimator fixes → CAU-05 dedicated cutover.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [GRF-01](bundles/GRF-01.md) | Правильные static ADMG m-separation и perfect-do | B216, B217 | LA-007, LA-019 | нет | CP5/L |
| [GRF-02](bundles/GRF-02.md) | Неизменяемый граф, mixed-edge export и версии кэша | B219, B220 | — | GRF-01 | CP5/L |
| [GRF-03](bundles/GRF-03.md) | Известные направления и явная временная/частичная семантика | B214, B218 | — | GRF-02 | CP5/L |
| [API-01](bundles/API-01.md) | Причинные фасады: explicit surface вместо отражающих globals | — | LA-020 | нет | CP5/L |
| [CAU-01](bundles/CAU-01.md) | Standard DiD: допустимый дизайн, covariance и уровни CI | B204, B205, B206 | LA-016 | нет | CP5/N |
| [CAU-02](bundles/CAU-02.md) | Staggered DiD: единицы, H0 и anticipation | B207, B208, B209 | — | CAU-01 | CP5/N |
| [CAU-03](bundles/CAU-03.md) | RDD: честная RBC capability и линейная память WLS | B210, B211 | — | CAU-01 | CP5/N |
| [CAU-04](bundles/CAU-04.md) | DoWhy: реальный estimand и point-only результат | B212, B213 | — | нет | CP5/L |
| [CAU-05](bundles/CAU-05.md) | DiD: dedicated planning, old-slot replay и retirement umbrella | — | LA-016 | CAU-01, CAU-02 | CP5/N |
| [SCM-01](bundles/SCM-01.md) | Наблюдаемые корни и выполняемый nonlinear payload | B221, B222 | — | GRF-02 | CP5/N |
| [SCM-02](bundles/SCM-02.md) | Factual abduction и две явные стороны attribution | B215, B223 | — | SCM-01 | CP5/N |
| [SCM-03](bundles/SCM-03.md) | Активный query-plan и сохранённый stochastic law | B224, B225 | — | SCM-02, GRF-01, GRF-02 | CP5/N |
| [FIT-01](bundles/FIT-01.md) | Nuisance fit-core, актуальная диагностика и ограниченные folds | B54, B56 | — | нет | CP4/N |

## LANE-06 — Состояние, deadlines, replay, канон и persisted migrations

RUN-01 сначала exact TypeVar cleanup, затем deadline/context fix отдельным commit. MIG-01 единый CLI/Trinity; MIG-02/MIG-04 исправляют его разные режимы. CAN/WIRE не сливаются.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [STA-01](bundles/STA-01.md) | Изоляция ветвей и точные эффекты replay | B57, B58, B59 | — | нет | CP2/L |
| [STA-02](bundles/STA-02.md) | Точная версия входа и пригодность готового bundle | B60, B61, B62 | — | STA-01 | CP2/L |
| [EXE-01](bundles/EXE-01.md) | Допуск cache read, неблокирующий I/O и fail-fast | B51, B52, B55 | — | STA-01, RUN-01 | CP2/L |
| [EXE-02](bundles/EXE-02.md) | Готовность зависимостей вместо лишнего tier-ожидания | B77 | — | RES-02, RES-01 | CP2/L |
| [RES-01](bundles/RES-01.md) | Повторный resume, достаточный state и дешёвый индекс | B63, B70, B71 | — | STA-02, RES-02 | CP2/L |
| [RES-02](bundles/RES-02.md) | Единый завершённый frontier и атомарный tier checkpoint | B72, B73 | — | STA-01 | CP2/L |
| [RES-03](bundles/RES-03.md) | Сохранение частичного результата через последующий отказ | B13 | — | CYC-02, CMP-01 | CP2/L |
| [RUN-01](bundles/RUN-01.md) | Deadline, contextvars и безопасные sync/async-мосты | B14, B40, B69, B95 | LA-057 | нет | CP2/L |
| [RUN-02](bundles/RUN-02.md) | Доставка результата через процессную границу | B24 | — | RUN-01 | CP2/N |
| [RUN-03](bundles/RUN-03.md) | Одна retry-политика и чистый baseline каждой попытки | B39, B96 | — | STA-01, RUN-01 | CP2/L |
| [DUR-01](bundles/DUR-01.md) | Аварийно-устойчивый бюджетный snapshot | B37 | — | нет | CP2/L |
| [DUR-02](bundles/DUR-02.md) | Поколение worker и безопасный backend handover | B38, B78 | — | RUN-03, RES-02 | CP2/L |
| [WIRE-01](bundles/WIRE-01.md) | Версионированный transport допустимых типов state | B94 | — | нет | CP2/L |
| [CAS-01](bundles/CAS-01.md) | First-writer, честная ref и bounded lock ownership | B150, B151, B153 | — | нет | CP2/L |
| [CAS-02](bundles/CAS-02.md) | Сначала проверенный transfer, затем публикация inventory | B148, B149 | — | CAS-01 | CP2/L |
| [CAS-03](bundles/CAS-03.md) | Одна проверка bytes и bounded batch verification | B152, B154, B155 | — | CAS-01 | CP2/L |
| [REP-01](bundles/REP-01.md) | Runtime replay: прямой Scientist owner без лишнего compatibility hop | — | LA-033 | нет | CP2/N |
| [CAN-01](bundles/CAN-01.md) | Strict canon: один primitive, явные Core/IR профили | — | LA-021 | нет | CP2/L |
| [MIG-01](bundles/MIG-01.md) | Один migration CLI: делегирование и явная Trinity validation | — | LA-010, LA-049 | нет | CP2/N |
| [MIG-02](bundles/MIG-02.md) | RunManifest: сохраняющее identity преобразование paths | — | LA-048 | MIG-01 | CP2/L |
| [MIG-04](bundles/MIG-04.md) | DatasetManifest: converter у schema owner, явная registration | — | LA-050 | MIG-01 | CP2/L |
| [MIG-05](bundles/MIG-05.md) | Common/IR: общая линейная механика, разные migration profiles | — | LA-047 | нет | CP2/L |

## LANE-07 — Ukraine builders: перенос helpers сразу с ремонтом наблюдений

UDF-01 contracts/D4 → OBS-01 observation-time+B146 → UDF-02 IO/bindings → OBS-02 B147. UDF-04/05 независимы при свободных write leases.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [UDF-01](bundles/UDF-01.md) | Ukraine builders: D4 handoff и малые явные contracts | — | LA-030, LA-031 | нет | CP2/L |
| [OBS-01](bundles/OBS-01.md) | Календарные observation helpers: перенос и корректные периоды | B146 | LA-031 | UDF-01 | CP2/L |
| [UDF-02](bundles/UDF-02.md) | Ukraine common: доменный I/O, binding diagnostics и явные exports | — | LA-031 | UDF-01, OBS-01 | CP2/N |
| [OBS-02](bundles/OBS-02.md) | Observation reader: непрерывность после partial yield | B147 | — | UDF-02 | CP2/N |
| [UDF-04](bundles/UDF-04.md) | Ukraine ops: явный workspace root и перенос server gate | — | LA-029 | нет | CP2/L |
| [UDF-05](bundles/UDF-05.md) | Демография: единый snapshot вместо per-file legacy fallback | — | LA-032 | нет | CP2/N |
| [FED-01](bundles/FED-01.md) | Grain, cell lineage, внутренние имена и CONSENSUS | B138, B140, B141, B145 | — | нет | CP2/L |
| [FED-02](bundles/FED-02.md) | Устойчивый bounded audit, typed-empty и один indexing | B139, B142, B143, B144 | — | FED-01 | CP2/L |
| [CAL-01](bundles/CAL-01.md) | Наблюдения, календарная ось и заполнение без фиктивной опоры | B176, B177, B178 | — | нет | CP4/N |

## LANE-08 — Catalog ingestion, generation-bound embeddings и resume

DFI-01 → DFI-02 для broadcast; EMB-01 → EMB-02 → EMB-03/DFI-03 для index generation/reuse. Соседние B ingestion/network сохраняют свои owners.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [DFK-02](bundles/DFK-02.md) | Source catalog: одно определение и единая seed-selection policy | — | LA-028 | нет | CP2/L |
| [DFI-01](bundles/DFI-01.md) | Core sources: самостоятельные writer/validator/loader dependencies | — | LA-038 | нет | CP2/L |
| [DFI-02](bundles/DFI-02.md) | Core sources: API cutover без обратной синхронизации globals | — | LA-038 | DFI-01 | CP2/N |
| [EMB-01](bundles/EMB-01.md) | Academic/Catalog: общий encode/index primitive, разные text profiles | — | LA-039 | нет | CP2/N |
| [EMB-02](bundles/EMB-02.md) | Индексное поколение: NPZ/HNSW/basis публикуются согласованно | — | LA-039 | EMB-01 | CP2/N |
| [EMB-03](bundles/EMB-03.md) | Legal embeddings: content-bound incremental и честный старый backend API | — | LA-040, LA-042 | EMB-02 | CP2/N |
| [DFI-03](bundles/DFI-03.md) | Batch resume: input basis и обязательный output inventory | — | LA-041 | EMB-02 | CP2/L |
| [ING-01](bundles/ING-01.md) | Инкрементальный запрос, committed cursor и replay | B79, B80, B88 | — | нет | CP2/L |
| [ING-02](bundles/ING-02.md) | Непрерывное окно, позиция и полная lineage | B81, B82, B85 | — | ING-01, NET-01 | CP2/L |
| [ING-03](bundles/ING-03.md) | Ограниченный stream-state без смены выборки | B83, B84, B86 | — | ING-02 | CP2/L |
| [NET-01](bundles/NET-01.md) | Владение соединением от acquire до cleanup | B87, B89, B90 | — | нет | CP2/L |
| [NET-02](bundles/NET-02.md) | Редкий rate, поколения circuit и невыбрасываемая защита | B91, B92, B93 | — | нет | CP2/L |

## LANE-09 — Scholar raw acquisition и snapshot handoff

SCL-01 B17+LA-024 → SCL-03 LA-025. LLM cache/planning остаётся отдельным контрактом с общей snapshot приёмкой.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [SCL-01](bundles/SCL-01.md) | Scholar: пустой ответ, общий raw transport и точные причины отказа | B17 | LA-024 | нет | CP2/L |
| [SCL-03](bundles/SCL-03.md) | Search→enrich: точный raw snapshot, не повторный URL-fetch | — | LA-025 | SCL-01 | CP2/N |
| [LLM-01](bundles/LLM-01.md) | Корректная обёртка, необязательная телеметрия и цена reuse | B64, B65, B66 | — | нет | CP2/L |
| [LLM-02](bundles/LLM-02.md) | Разрешённый immutable reuse и single-flight | B67, B68 | — | LLM-01 | CP2/L |

## LANE-10 — Калибровка модели и закон неопределённости

Существующие B цепочки; учесть upstream changes FRY/OBS и downstream PCL/FRC без объединения разных calibration APIs.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [CAL-02](bundles/CAL-02.md) | Один effective loss: оси, два уровня весов и masked scale | B179, B180, B181, B182 | — | CAL-01 | CP4/N |
| [CAL-03](bundles/CAL-03.md) | Несколько стартов: span lifecycle и пригодность выбора | B183, B195 | — | CAL-02 | CP4/N |
| [CAL-04](bundles/CAL-04.md) | Последний итерат, единый финальный forward и Hessian reuse | B184, B196, B203 | — | CAL-03 | CP4/N |
| [CAL-06](bundles/CAL-06.md) | Tied-параметры и неизменный масштаб условного закона | B197, B198 | — | CAL-04, UQP-02 | CP4/N |
| [UQS-01](bundles/UQS-01.md) | Summary, интервалы и независимые информационные единицы | B199, B200, B201, B202 | — | UQP-02, CAL-06 | CP4/N |
| [UQP-01](bundles/UQP-01.md) | Настоящая функция отклика и полный effective call | B186, B189, B190, B191 | — | нет | CP4/N |
| [UQP-02](bundles/UQP-02.md) | Оси covariance, совместный закон и эмпирический carrier | B187, B188, B192 | — | UQP-01 | CP4/N |
| [UQP-03](bundles/UQP-03.md) | Точность функционала, остановка MC и непокрытая область | B193, B194 | — | UQP-02 | CP4/N |
| [DOE-01](bundles/DOE-01.md) | Ограниченная генерация и только объявленные раунды | B97, B98, B99 | — | нет | CP3/L |
| [DOE-02](bundles/DOE-02.md) | Один дизайн распределений и локальные RNG | B100, B101 | — | DOE-01 | CP3/N |
| [DOE-03](bundles/DOE-03.md) | Целые блоки, failure-policy, PCA и шкала Morris | B102, B103, B104, B105 | — | DOE-02 | CP3/N |
| [STR-01](bundles/STR-01.md) | Направление stress-поиска и независимые от top-k счётчики | B106, B107 | — | нет | CP3/L |

## LANE-11 — Explainability и monitoring: явный profile и актуальный decision

DDM-01 → DDM-02; BERL и Lex независимы. Общая проверка ограничений, но нет общего нового authority engine.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [BER-01](bundles/BER-01.md) | BERL: schema profile и действительная identity объяснителя | — | LA-034, LA-036 | нет | CP3/N |
| [DDM-01](bundles/DDM-01.md) | DDM: один event/budget owner и lazy parent facade | — | LA-056 | нет | CP3/L |
| [DDM-02](bundles/DDM-02.md) | DDM: актуальное основание и единый gate с R2 override | — | LA-054, LA-055 | DDM-01 | CP3/N |
| [LEX-01](bundles/LEX-01.md) | Lex: norm/compliance comparison отдельно от impact-topic эвристики | — | LA-017 | нет | CP3/L |

## LANE-12 — Точные retirement и generated client поставка

Готовые небольшие cleanup задачи выдаются между связанными fixes. Generated-family build и distribution объединяются в CP6; нет обязательной cleanup-фазы после B.

| Пакет | Задача | B | LA | Предшественники | Окно/класс |
|---|---|---|---|---|---|
| [DFK-01](bundles/DFK-01.md) | Точные остатки Foundry/Data Forge schemas без удаления владельцев | — | LA-005, LA-006, LA-026, LA-027 | нет | CP2/L |
| [HYG-02](bundles/HYG-02.md) | Evidence/governance/factlog: точные адресные retirement | — | LA-008, LA-009, LA-018 | нет | CP2/L |
| [HYG-04](bundles/HYG-04.md) | Bootstrap/benchmark wrappers и frontend redirect: конечная миграция | — | LA-011, LA-012, LA-013 | нет | CP6/L |
| [CLI-01](bundles/CLI-01.md) | Runtime client: package-owned генерация и снятие raw committed surface | — | LA-043, LA-044 | нет | CP6/N |

