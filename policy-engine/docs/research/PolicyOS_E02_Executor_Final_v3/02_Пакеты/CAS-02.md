# CAS-02 — Сначала проверенный transfer, затем публикация inventory

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B148, B149. Тип: remediation publication/cleanup + native qualification.

Directory и tar export публикуют только законченный точный пакет, не удаляют поздний пользовательский файл и сохраняют прежний valid архив при сбое. Import использует уже действующий pre-publication verification/custody.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/CAS-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C75_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/CAS-02_исходные_строки.txt), исходный объединённый план §CAS-02 (исторические строки 8688–8780).

## 2. Уже работает — сохранить

- Закрытый inventory и измеренные hash/size bindings: экспорт B не включает остатки A; manifests=False не оставляет старую sidecar.
- Import проверяет private staging, ownership/admission/conflicts до публикации; staged/received не равно published/verified.
- Immutable profile views, nofollow/path containment и раздельные counts received/published/reused/verified остаются.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C75-R01 | fix: Убрать recursive delete старого output после swap: поздняя foreign запись не входит в доказанный export ownership. | REQ-CAS-02-01 |
| C75-R02 | fix: Tar строится во временном sibling файле и заменяет destination только после полного close/verification; fail не уничтожает A. | REQ-CAS-02-02 |
| C75-G01 | qualify: Проверить importer/exporter с initialized CAS, реальными owners/signatures/recovery. | REQ-CAS-02-03 |
| C75-G02 | lifecycle: Fault/concurrency/fs profile проверяют требуемую замкнутую группу и сохранность старого результата; не объявлять универсальную транзакционность. | REQ-CAS-02-01, REQ-CAS-02-02, REQ-CAS-02-03 |

### Исходные обязанности, не только новые R

- B148: corrupt/read-interrupted/conflicting import не повреждает ранее доступный объект; минимальная замкнутая группа атомарности, а не обязательная giant archive transaction.
- B149: A→B replacement выдаёт только B; foreign data не принадлежит exporter даже если появилась после preflight. Старое поколение может жить отдельно, но не в новом inventory.

## 4. Нормативный контракт

### REQ-CAS-02-01
Publication directory-generation не удаляет recursively previous_root, который мог получить foreign data после preflight. Минимальное безопасное решение: после swap сохранить прежнее поколение под отдельным sibling именем и явно сообщить его location/cleanup disposition; автоматический cleanup допускает только ранее доказанные export-owned entries с проверкой identity/bindings и не удаляет неизвестные/replaced entries. При невозможности доказать ownership сохранить, а не удалять. Новый target содержит ровно B.

Источник: B149; аудит: C75-R01, C75-G02; проверки: TEST-CAS-02-01.

### REQ-CAS-02-02
Compressed export создаёт уникальный private temp file на filesystem destination, полностью записывает tar и закрывает gzip/tar, фиксирует exact inventory и выполняет flush/fsync согласно принятому durability profile, затем atomic replace. При ошибке source/read/archive/finalization до replace старый архив A byte-identical и импортируем; temp удаляется только собственный. Ошибка после replace не называется rollback A и получает честный visibility/durability outcome.

Источник: B149; аудит: C75-R02, C75-G02; проверки: TEST-CAS-02-02.

### REQ-CAS-02-03
На native FileSystemCAS и durable owner index import directory/tar публикует только проверенные closed groups и exact profile bindings. Tampered bytes, symlink, unknown member, manifest conflict, wrong tenant, revoked signature при обязательной signature policy или pending recovery не дают успешной публикации; previously valid artifact остаётся читаем. Counts и ошибки описывают фактически received/verified/reused/published, а не число copied files.

Источник: B148, B149; аудит: C75-G01, C75-G02; проверки: TEST-CAS-02-03.

## 5. Техническое решение и producer → consumer

В _transfer_ops._publish_directory_generation отделить publication от garbage collection: текущий swap target→previous_root→target можно сохранить с rollback, но shutil.rmtree(previous_root) недопустим. По умолчанию удерживать старое поколение безопаснее, чем пытаться устранить race одним повторным rglob. Возвращать/логировать retained generation через существующий transfer result/diagnostic owner; изменение DTO согласовать с consumers. Tar branch перенести с tarfile.open(final,'w:gz') на private sibling temp и финальный replace, не буферизуя архив целиком. Import staging, open_member stream receipts и existing publication callback оставить едиными owners.

### Проверенные owners на срезе
- policy-engine/src/polisyos/core/artifacts/_transfer_ops.py: _validate_directory_export, _publish_directory_generation, export_subgraph, import_subgraph
- policy-engine/src/polisyos/core/artifacts/store.py: FileSystemCAS.export_subgraph, import_subgraph
- policy-engine/src/polisyos/core/artifacts/_atomic_write.py: fsync_directory, AtomicFileDurabilityError

Повторный scan перед rmtree не закрывает поздний race; глобальный lock exporter не контролирует произвольного пользователя. Поэтому сохранение old generation — дешёвое достаточное решение, отдельный garbage collector не обязателен.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-CAS-02-01
- Уровень: unit + targeted native integration.
- Setup: Экспорт A в reusable directory; callback после _validate_directory_export, но до generation swap, создаёт user-note.txt и отдельно заменяет старый member пользовательскими bytes.
- Действие: Экспорт B; затем import нового target. Также существующая foreign file до preflight и fault второго os.replace.
- Точный oracle: Новый inventory ровно B без A; note/replaced bytes сохранены в old generation либо операция отказана до потери данных. Нет recursive deletion foreign entries. При swap failure A restored либо явный restore failure с сохранёнными путями; ни ложного B success, ни silent loss.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-02-02
- Уровень: unit + targeted native integration.
- Setup: Valid archive A; экспорт B открывает blob, а чтение manifest выбрасывает OSError. Отдельные faults write, close/gzip footer, fsync, replace.
- Действие: Повторить failed export; сравнить SHA256 всего archive A; import A fresh reader. Затем successful B и absence stale A.
- Точный oracle: Любой pre-replace отказ сохраняет A byte-for-byte и пригодным к import; successful archive closed и inventory B; собственный temp очищен, пользовательские sibling files не затронуты. Post-replace fsync refusal явно не обещает старый A.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-CAS-02-03
- Уровень: native CAS → transfer → fresh CAS.
- Setup: Реальный source CAS профили A/B из CAS-01, отдельный destination root/index, configured trust/tenant; малый directory и tar.
- Действие: Valid transfer, corrupt payload, altered manifest, extra member, symlink, tenant mismatch; fault на verified group publication и restart/retry.
- Точный oracle: Точные selected refs/manifest bytes сохраняются; отрицательный набор не портит старый valid destination; partial disposition честен по каждому объекту. Нет опубликованного объекта без admission, обязательного для выбранного профиля и configured policy; допустимый unsigned профиль остаётся пригодным и проверяется положительным control. Отсутствие подписи само по себе не invalid; recovery читает действующие intents, не перескакивает проверку.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_cas_02.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: faulting source member и barriers для точного race; fsync failures в локальных test roots. Запрещено: фиктивный ownership/signature admission для итоговой native проверки, массовая копия production CAS.

## 7. Общая интеграция и порядок

Использовать те же A/B selected refs CAS-01; после импорта новый CAS-03 читает и подписывает точные imported views. Publication/fresh read свидетельство общее, error injection остаётся локальным.

Точные общие сценарии: E02-I06-D из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: CAS-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Closed inventory и partial missing-artifact report сохраняются. Retained old generation не объявляется частью нового пакета. DTO добавление только additive/с совместимым default; если existing report не допускает field, стабильно документированный diagnostic location обязателен. Повтор не меняет input CAS. Rollback только до подтверждённой новой visibility, не после успешного replace.

## 9. Free-grow и design direction

- Custody требует проверенный producer→transfer→consumer, а не успешный copy.
- Безопасное удержание предыдущего поколения предпочтительнее дорогостоящего универсального transactional storage.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Согласовать канал передачи retained generation path и bounded retention policy; отсутствие автоматического cleanup допустимо, потеря чужих данных — нет.
- Для fsync после replace зафиксировать существующий error/report surface и поддержанный filesystem; не изобретать гарантированный rollback.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

