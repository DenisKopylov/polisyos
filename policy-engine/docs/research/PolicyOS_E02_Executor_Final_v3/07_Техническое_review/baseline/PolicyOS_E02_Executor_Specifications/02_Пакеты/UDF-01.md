# UDF-01 — Ленивый builder facade и точный D4 handoff

**LANE-07 · CP2 · LA-030, LA-031 · fix + migration preserve + native qualification.**

**Практическая цель:** Малый typed contract доступен без всей pipeline; реальный D4 запрос сохраняет смысл и достигает существующего Scientist consumer.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/UDF-01.md) · [остатки C83](../05_Основания/Аудит/01_Реестры/C83_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/UDF-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 low import topology; время/RSS не измерены. G не означает неисправность supported runtime.

## 2. Сохранить работающий смысл
- D4 bytes/schema/filename/required stages/4 denials
- Canonical owner и bounded alias
- Current inputs extension/revalidation
- Real read API guards
- Материализационные contracts/planner

Защищённые различения: LK10, LK12. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C83-R01: fix** → REQ-UDF-01-01. Сделать facade lazy на existing pattern; контракт import не активирует все siblings.
- **C83-G01: qualify** → REQ-UDF-01-02. Real native producer→selected CAS→Scientist request consumer, не fixture storage.
- **C83-G02: lifecycle** → REQ-UDF-01-03, REQ-UDF-01-04. Сохранить inputs delta/old aliases и квалифицировать подтверждённых callers; остальные phases отдельно.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-UDF-01-01
Contract-only import builders.contracts не должен активировать unrelated builder siblings. Explicit facade/registry доступ должен затем активировать правильные canonical functions и сохранить aliases; не требуется исключить собственные необходимые DTO dependencies.

**TEST-UDF-01-01 — native unit / integration; NOT_RUN.**
- Setup: Fresh supported Python subprocess, empty relevant sys.modules; отдельно import contracts, затем facade STAGE_BUILDERS/aliases.
- Действие: Снять module import trace и сравнить function identities.
- Точный oracle: До explicit facade access отсутствуют sources/demography/bindings_validation/common из eager parent; после access полный registry верен, calibration alias is canonical build_d4_stage. Old eager parent нарушает первый oracle.
- Doubles/границы: Настоящий Python loader; no package shells/import interception, меняющего разрешение модулей.

### REQ-UDF-01-02
D4 producer должен сохранять exact output bytes/path/schema/required-stage mapping и все четыре may_not_use_for; actual selected-profile reader передаёт только producer handoff request Scientist consumer, не governance verdict.

**TEST-UDF-01-02 — native unit / integration; NOT_RUN.**
- Setup: Tiny valid config/manifest, build_d4_stage и actual FileSystemCAS/read API; independent legacy JSON byte fixture.
- Действие: Пройти facade/orchestrator в разрешённом profile→completed manifest→load_verified_stage_json_output.value_for_candidate→request consumer; corrupt/missing/wrong stage controls.
- Точный oracle: Bytes/hash/size/filename прежние, producer_handoff_ready=True и 4denials. Valid request принят parser; bad receipt отказан до consumer, old captured bytes неизменны после producer mutation.
- Doubles/границы: Не fake CAS или Scientist parser; admitted server orchestration только в подходящей среде, иначе scope честно ограничен.

### REQ-UDF-01-03
StageBuildResult сохраняет первые пять positional fields и полезный inputs/validate_inputs delta; после builder return orchestrator повторно проверяет content-bound уникальные inputs disjoint outputs. Aliases не удаляются до actual caller qualification.

**TEST-UDF-01-03 — native unit / integration; NOT_RUN.**
- Setup: Old constructor формы и current inputs, mutated list after construction; dataclass serialization/introspection consumers из подтверждённого census.
- Действие: Конструировать/сериализовать и передать actual orchestrator; проверить badtype/hash/duplicate/overlap.
- Точный oracle: Legacy positional ABI работает, defaults независимы; invalid returned inputs отвергаются. Alias identity сохраняется; census unknown не разрешает retirement.
- Doubles/границы: Не требовать буквально старый DTO без inputs; новые fields — intentional supported extension.

### REQ-UDF-01-04
LA-031 phase closure должна учитывать OBS-01 календарный owner и UDF-02 IO/bindings, сохраняя реальные materialize contracts/planner и read API; UDF-01 не закрывает эти части одним relocation.

**TEST-UDF-01-04 — native unit / integration; NOT_RUN.**
- Setup: Shared LANE07 fixture и actual materialize AssetDefinition/decorator/planner: dependency DAG,missing,cycle.
- Действие: Проверить producer routing и exact identity aliases; собрать phase obligations/review evidence.
- Точный oracle: DAG correct order, missing/cycle отказ; read API не bypassed. Phase status ссылается на завершённые собственные требования OBS/UDF02, не blanket LA031 PASS.
- Doubles/границы: Можно tiny specifications; не подменять planner и не выдавать его за distributed executor.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/ukraine/builders/__init__.py` сейчас eager импортирует bindings/common/sources и формирует STAGE_BUILDERS. Применить существующий `_LAZY_EXPORTS`/`__getattr__` pattern из `src/polisyos/data_forge/domains/ukraine/__init__.py`: явная name→canonical module map для public и сохранённых compatibility aliases; STAGE_BUILDERS конструировать один раз при явном запросе registry в composition owner. Не применять wildcard/lazy-global framework. contracts.StageBuildResult экспортировать прямо из contracts, не через common.

`src/polisyos/data_forge/domains/ukraine/builders/governance_handoff.py::build_d4_stage`, `src/polisyos/data_forge/domains/ukraine/builders/contracts.py::StageBuildResult`, calibration alias и `src/polisyos/data_forge/domains/ukraine/builders/io.py::_write_json` уже реализованы: менять только если characterization не проходит. `src/polisyos/data_forge/read_api/ukraine.py::load_verified_stage_json_output` и `src/polisyos/scientist/governance/blueprint_release.py::run_verified_ukraine_d4_governance` — actual downstream, включая request parsing и отдельно D0/D2/D3 receipts. Handoff не выполняет Foundry calibration. Native test обязателен для выбранного допустимого scope, а не фиктивный bypass server gates. Сохранить 4 запрета literally.

## 6. Общая интеграция и порядок
**E02-I07-A**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- UDF-01 sole shared facade/import writer; OBS-01/UDF-02 потребляют C83-R01
- LA-031 accountable owner UDF-02; общий E02-I07-A

Owners/callers: `src/polisyos/data_forge/domains/ukraine/builders/__init__.py`; `src/polisyos/data_forge/domains/ukraine/builders/contracts.py::StageBuildResult`; `src/polisyos/data_forge/domains/ukraine/builders/governance_handoff.py::build_d4_stage`; `src/polisyos/data_forge/read_api/ukraine.py`; `src/polisyos/scientist/governance/blueprint_release.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Historical CAS/filename/schema не мигрировать ради Python адреса. Lazy activation меняет только import topology; current DTO inputs — отдельный already-supported delta. Aliases retain; rollback loader не восстанавливает широкую namespace утечку и не удаляет real input validation.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

Малое import исправление не оправдывает удаление common/scheduler или создание meta-loader. D4 producer readiness полезна до governance authority; отделять ограничение claims от запрета работы.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_udf_01.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
