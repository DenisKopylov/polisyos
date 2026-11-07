# DFK-01 — точные schema-остатки и сохранение работающих владельцев

**C124 · LANE-12 · LA-005, LA-006, LA-026, LA-027 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Пустой `foundry.domain.mechanisms` действительно отсутствует, negative tests сохранены и исполняются. Остальные три surfaces **не удалены**: Foundry DTO, codegen descriptor и pipeline schema alias явно остаются compatibility_pending. Это не доказательство их активной вычислительной роли и не основание немедленно удалить их без отдельного lifecycle решения.

Canonical registry/evolution/graph migrations работают в доступном окружении. **6 MATCH; 9 unchanged bodies / 16 cases: 14 PASS, 2 environment FAIL. Новых подтверждённых R нет; G01–G03 остаются.** Два FAIL и начальные harness остановки сохранены, не скрыты повторным запуском.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual состояние | Остаток |
|---|---|---|---|
| LA-005 | Проверить3 DTO, FQN/config/persisted consumers; удаление только без необходимой роли. | AgentType/RegionProfile/SimulationConfig остаются; native models и synthetic roundtrip работают. | G01: конкретный compatibility/lifecycle decision, реальные historical/external inputs. Не переносить автоматически в общий Foundry contract. |
| LA-006 | Удалить empty tombstone, заменить import-success отрицательной архитектурной проверкой. | Package/files отсутствуют, root/submodule negative imports PASS; useful current owners не удалены. | G02: distribution membership и native JAX registry consumer не исполнены. |
| LA-026 | Удалить3-field descriptor лишь при отсутствии supported contract; не строить generator. | GeneratedSchemaModule остаётся ровно descriptor3fields, canonical export не делает его генератором. | G01: собственное compatibility_pending решение, не whole schemas deletion. |
| LA-027 | Canonical kernel/schemas, снять только alias после миграции адреса. | Alias ещё существует; exact initializer identity всех3 классов совпадает с actual owner. | G01/G02: lifecycle и native parent/package/archive qualification. |

## 3. Producer → consumer и защищённые различия

[Registry](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/registry.py#L25-L71) хранит actual typed versions; [evolution](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/evolution.py#L75-L129) требует matching explicit rule для своих breaking families. [Migration registry](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/schemas/migrations.py#L61-L132) — directed graph с deterministic shortest path, не два линейных runners. Shallow copy и отсутствие автоматического version stamping — объявленный contract, не новая ошибка.

[Pipeline alias](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py#L1-L11) не параллельный registry. [Materialize](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_forge/kernel/pipeline/materialize.py#L30-L105) сохраняет spec→callable и dependency planner. [ABI owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/schemas/abi_models/__init__.py#L29-L95) теперь package, а не старый файл; registry references не дублирующие DTO. LK03/LK10/LK25 не превращены в задачи удаления соседних владельцев.

[Actual census](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/quality/validation/schema_fqn_census.py#L1049-L1393) связывает Git-visible selected paths и прочитанные байты, отдельно показывает relative imports, strings/resources, dynamic loaders, исключения и unsupported inputs. Его verdict прямо не retirement authorization. V3 сохраняет unknown ignored counts как null, а не zero; release fragment явно различает смену receipt contract и миграцию внешних callers.

## 4. Проверки

| Проверка | Результат и предел |
|---|---|
| P01 |7 unchanged bodies/14cases:12PASS2environmentFAIL. Canonical identities/evolution/migration, codegen и Foundry native imports, negative retired FQNs. Pipeline parent blocked Core3.14 syntax. |
| P02 |Два порядка регистрации branching migration graph дают low→vialow; duplicate exact edge refused. Actual native owner. |
| P03 |Full current product-tree census: partial_unsupported_or_ambiguous, code2, selected/read 25336/25336, excluded 2899, unsupported 44, loader sites 1278 (nonliteral 477). Реальные Git/bytes, но dependency fs extracted; не native CLI. |
| P04 |Own finite Git fixture без commit: relative/literal/nonliteral loaders, ignored/binary exclusions; malformed source→partial, missing tracked file→partial. |
| P05 |Independent bare-symbol census всего tracked repository: 26633 UTF-8 files, 1631 non-UTF-8 excluded, 176 matching lines. Это lexical evidence, не external consumer proof. |
| P06 |Ещё2 unchanged schema bodies PASS; exact alias initializer identity и3 native synthetic DTO JSON roundtrips. Не historical corpus и не native pipeline parent. |

[Probe](../04_Проверки/C124_DFK01/probe_dfk01.py) · [все14 cases](../04_Проверки/C124_DFK01/run02/existing_cases.json) · [дополнительные2 cases](../04_Проверки/C124_DFK01/followup02/observations.json) · [полный census](../04_Проверки/C124_DFK01/run02/repository_census.json) · [bare symbols](../04_Проверки/C124_DFK01/run02/bare_symbol_census.json) · [команды](../04_Проверки/C124_DFK01/commands.json).

## 5. Остаток

**C124-G01:** отдельно решить три названные compatibility_pending surfaces. Конечный source census полезен, но binary/historical/installed/external/computed-name consumers не исключены. Неизвестность конкретного имени не отменяет отдельно проверенное tombstone retirement. Нужный внешний contract получает converter/window рядом с actual owner; ненужный DTO не переселяется «на всякий случай».

**C124-G02:** supported native census/public CLI и Q2 wheel→sdist→rebuilt-wheel/installed consumer. Текущий installed oracle в source требует конкретного artifact binding; пропущенный профиль не PASS. Package configuration прочитана, build/install не запускался. Python3.12 syntax limits и missing pytest/JAX не product defects. Сохранить current partial/read/exclusion semantics и не считать ACTIVE autodiscovery утверждением lifecycle.

**C124-G03:** сохранение canonical capability ограничено её реальным contract. Evolution не универсальный JSON Schema inclusion solver, миграции не заменяют Common/IR, materialize не распределённый executor. Bare-symbol hits включают другой SimulationConfig в plugins/api.py и другой AgentType в core/contracts/provenance.py: совпадение имени не связь с legacy DTO. Native JAX economics registry и реальный historical payload replay остаются UNRUN. Не придумывать новый generator или paperwork architecture ради удаления placeholder; расширять существующих owners лишь при подтверждённой необходимости.

[Карточка](../05_Источники/DFK-01_исходные_строки.txt) · [sources](../05_Источники/C124_источники.json) · [остатки](../01_Реестры/C124_остатки.json) · [границы](../04_Проверки/C124_DFK01/Чтение_и_границы.md).

**124/127. Следующий HYG-02; осталось3 пакета. Фаза заданий исполнителю не начата.**
