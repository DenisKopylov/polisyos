# LA crosswalk и единичная ответственность закрытия

B-карточки и LA-карточки имеют разные смыслы и статусы. Multi-stage participation не повторный счёт одной находки.

| LA | Категория | Полное решение | Все этапы | Closure owner |
|---|---|---|---|---|
| LA-001 | R | Treasury: инфраструктура случайности под предметным названием | [FRY-01](bundles/FRY-01.md) | FRY-01 |
| LA-002 | R | Design: каталог семейств рядом с исполняемыми механизмами | [FRY-01](bundles/FRY-01.md) | FRY-01 |
| LA-003 | R | Fiscal/labor: живые kernels ранних базовых моделей | [FRY-03](bundles/FRY-03.md) | FRY-03 |
| LA-004 | M | Две экономические реализации: согласовать, но не подменять | [ECO-01](bundles/ECO-01.md) | ECO-01 |
| LA-005 | D | Foundry domain/schema: остаточная ранняя предметная схема | [DFK-01](bundles/DFK-01.md) | DFK-01 |
| LA-006 | C | Foundry domain/mechanisms: пустой tombstone с тестовым контрактом | [DFK-01](bundles/DFK-01.md) | DFK-01 |
| LA-007 | D | id_engine.py рядом с id_engine/: пустая тень, не адаптер | [GRF-01](bundles/GRF-01.md) | GRF-01 |
| LA-008 | D | Evidence _shim: helper для уже выведенных пространств имён | [HYG-02](bundles/HYG-02.md) | HYG-02 |
| LA-009 | C | Scientist governance aliases: завершить перенос к Core | [HYG-02](bundles/HYG-02.md) | HYG-02 |
| LA-010 | M | Корневой migrate.py: реальная вторая реализация команды | [MIG-01](bundles/MIG-01.md) | MIG-01 |
| LA-011 | C | Install и JAX bootstrap: разные виды переходных entrypoints | [HYG-04](bundles/HYG-04.md) | HYG-04 |
| LA-012 | C | Benchmark wrappers: снять второй адрес, не удалить рабочие benchmarks | [HYG-04](bundles/HYG-04.md) | HYG-04 |
| LA-013 | D | frontend/: истёкший указатель вместо второго приложения | [HYG-04](bundles/HYG-04.md) | HYG-04 |
| LA-014 | M | Search contracts импортируют и изменяют legacy runtime | [SRV-01](bundles/SRV-01.md) | SRV-01 |
| LA-015 | M | SearchController: живое legacy-ядро, требующее поэтапного замещения | [CTL-01](bundles/CTL-01.md), [SRV-03](bundles/SRV-03.md) | SRV-03 |
| LA-016 | M | DiD umbrella-wrapper удерживает метаданные новых методов | [CAU-01](bundles/CAU-01.md), [CAU-05](bundles/CAU-05.md) | CAU-05 |
| LA-017 | R | Lex simulator: норм-различия, проверки и эвристика воздействия смешаны | [LEX-01](bundles/LEX-01.md) | LEX-01 |
| LA-018 | C | Lex factlog: alias читателя фактов у другого владельца | [HYG-02](bundles/HYG-02.md) | HYG-02 |
| LA-019 | D | Ещё два пустых файла после выделения причинных пакетов | [GRF-01](bundles/GRF-01.md) | GRF-01 |
| LA-020 | C | Фасады причинных пакетов сохраняют устройство старого монолита | [API-01](bundles/API-01.md) | API-01 |
| LA-021 | M | Два канонических кодека с одной версией и разными возможностями | [CAN-01](bundles/CAN-01.md) | CAN-01 |
| LA-022 | M | Legacy DomainPlugin discovery дублирует общую инфраструктуру загрузки | [PLG-01](bundles/PLG-01.md) | PLG-01 |
| LA-023 | M | PolisySimulator.train: сбор rollout-наград под видом обучения | [PLG-02](bundles/PLG-02.md), [PLG-03](bundles/PLG-03.md) | PLG-03 |
| LA-024 | M | Scholar: два HTTP-транспорта с разными границами проверки | [SCL-01](bundles/SCL-01.md) | SCL-01 |
| LA-025 | M | Найденный snapshot снова превращается в URL для новой загрузки | [SCL-03](bundles/SCL-03.md) | SCL-03 |
| LA-026 | D | Schema codegen: остаточная декларация вместо генератора | [DFK-01](bundles/DFK-01.md) | DFK-01 |
| LA-027 | C | pipeline/schemas: законченный перенос, но остаётся второй адрес | [DFK-01](bundles/DFK-01.md) | DFK-01 |
| LA-028 | M | Каталог источников: миграционное зеркало стало второй поддерживаемой истиной | [DFK-02](bundles/DFK-02.md) | DFK-02 |
| LA-029 | R | Ukraine server: эксплуатация и repository gate внутри предметного builder | [UDF-04](bundles/UDF-04.md) | UDF-04 |
| LA-030 | R | calibration.py: имя прежней ответственности после правильного D4-разделения | [UDF-01](bundles/UDF-01.md) | UDF-01 |
| LA-031 | M | builders/common.py: разделённые файлы всё ещё живут в namespace старого монолита | [OBS-01](bundles/OBS-01.md), [UDF-01](bundles/UDF-01.md), [UDF-02](bundles/UDF-02.md) | UDF-02 |
| LA-032 | M | Демографический reader: совместимость по отдельным filename вместо целого снимка | [UDF-05](bundles/UDF-05.md) | UDF-05 |
| LA-033 | C | Runtime replay: реализация перенесена, но старый путь остаётся транзитным | [REP-01](bundles/REP-01.md) | REP-01 |
| LA-034 | M | BERL ExplanationBundle: схема-каркас и генерируемый контракт разошлись | [BER-01](bundles/BER-01.md) | BER-01 |
| LA-035 | R | policy_loss_fn: ранний экономический baseline у общего method-владельца | [ECO-01](bundles/ECO-01.md) | ECO-01 |
| LA-036 | M | BERL: разные method IDs всё ещё обозначают один fallback-вычислитель | [BER-01](bundles/BER-01.md) | BER-01 |
| LA-037 | C | Slot layout: две последовательные compatibility-обёртки после переноса в IR | [FRY-01](bundles/FRY-01.md) | FRY-01 |
| LA-038 | M | core_sources_ingest: после разделения файлов фасад остаётся владельцем общего изменяемого окружения | [DFI-01](bundles/DFI-01.md), [DFI-02](bundles/DFI-02.md) | DFI-02 |
| LA-039 | M | Academic/Catalog embeddings: повтор механики и незавершённая публикация поколения | [EMB-01](bundles/EMB-01.md), [EMB-02](bundles/EMB-02.md) | EMB-02 |
| LA-040 | M | Legal incremental embeddings: старый ID-cache не описывает эквивалентность вычисления | [EMB-03](bundles/EMB-03.md) | EMB-03 |
| LA-041 | M | Batch checkpoint: прежняя «стадия уже выполнена» живёт отдельно от content-bound результата | [DFI-03](bundles/DFI-03.md) | DFI-03 |
| LA-042 | C | Старый embedding entrypoint: исчезнувший backend-контракт остался в сигнатуре | [EMB-03](bundles/EMB-03.md) | EMB-03 |
| LA-043 | C | Runtime API client: публичный twin сменился, а старый generated-адрес остался обязательным | [CLI-01](bundles/CLI-01.md) | CLI-01 |
| LA-044 | R | Генератор клиента уже принадлежит package, но schema-tool по-прежнему разрешается через dashboard | [CLI-01](bundles/CLI-01.md) | CLI-01 |
| LA-045 | D | Старый extractor data families: замкнутая неиспользуемая ветка внутри действующего compiler | [REQ-01](bundles/REQ-01.md) | REQ-01 |
| LA-046 | M | DataRequirementCompiler: именованный construct-путь всё ещё наследует неявный сценарный профиль | [REQ-01](bundles/REQ-01.md), [ACQ-01](bundles/ACQ-01.md) | ACQ-01 |
| LA-047 | M | Common / IR migration engines: один линейный механизм с разошедшимися свойствами | [MIG-05](bundles/MIG-05.md) | MIG-05 |
| LA-048 | M | RunManifest: старое эвристическое переписывание путей внутри канонического migration CLI | [MIG-02](bundles/MIG-02.md) | MIG-02 |
| LA-049 | M | Trinity: validation продолжает жить под migration-контрактами, но self-edge не выполняется | [MIG-01](bundles/MIG-01.md) | MIG-01 |
| LA-050 | R | DatasetManifest migration: предметный converter остался в Common отдельно от schema owner | [MIG-04](bundles/MIG-04.md) | MIG-04 |
| LA-051 | M | N8 → S10: адаптер формы причинной оценки продолжает выполнять роль производителя калибровки | [FRC-01](bundles/FRC-01.md), [FRC-02](bundles/FRC-02.md) | FRC-02 |
| LA-052 | M | Calibration curve: старое правило «нет пригодных интервалов — хорошо» пережило перенос в общий пакет | [PCL-01](bundles/PCL-01.md) | PCL-01 |
| LA-053 | C | Scientist backtesting calibration_curve: перенесённая функция и невыведенный прежний адрес | [PCL-01](bundles/PCL-01.md) | PCL-01 |
| LA-054 | M | DDM: rich calibration/report context сужается до бессрочного pass и несвязанной registry-записи | [DDM-02](bundles/DDM-02.md) | DDM-02 |
| LA-055 | M | DDM promotion: состояние, базовое разрешение и окончательный gate конкурируют за один смысл | [DDM-02](bundles/DDM-02.md) | DDM-02 |
| LA-056 | R | DDM contracts: нейтральные типы всё ещё входят через integration orchestration | [DDM-01](bundles/DDM-01.md) | DDM-01 |
| LA-057 | D | Common async bridge: прежний модульный TypeVar больше не участвует в четырёх generic-функциях | [RUN-01](bundles/RUN-01.md) | RUN-01 |

## Поздние уточнения включены в задания

**AM01 · LA-010.** LA-010 — уточнение r02; source строки 1154–1157. Полный текст приложен ко всем связанным packet.

**AM02 · LA-004.** LA-004 — уточнение r02; source строки 1158–1161. Полный текст приложен ко всем связанным packet.

**AM03 · LA-045.** LA-045 — дополнительное private-определение, без новой карточки; source строки 3434–3447. Полный текст приложен ко всем связанным packet.

**AM04 · LA-046.** LA-046 — N7 handoff теперь прочитан до непосредственного downstream-вызова; source строки 3818–3842. Полный текст приложен ко всем связанным packet.

LA-045: семь private функций и одна constant, включая _digest; не удалять hashlib/json или active fallback. LA-046: actual N7 text/domain/resolver handoff из r08, не только первоначальная substring-гипотеза.
