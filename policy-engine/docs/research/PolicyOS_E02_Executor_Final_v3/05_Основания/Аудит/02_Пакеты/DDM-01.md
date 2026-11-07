# DDM-01 — один contract owner и lazy parents

**C121 · LANE-11 · LA-056 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Canonical event и metric-budget классы действительно вынесены к contracts; прежние адреса возвращают те же class objects. Root и integration facade загружают monitor/registry/incident только по запросу. Четыре холодных contract imports не достигают orchestration trap; прямой monitor import тем же trap перехватывается.

**6 MATCH; 10 unchanged test bodies / 19 cases:18 PASS,1 environment FAIL. Новых подтверждённых defects нет.** Missing optional date-time checker не скрыт: malformed-date schema case остаётся FAIL, а runtime Pydantic отдельно отвергает дату. Полного закрытия LA-056 и native supported profile не заявлено.

## 2. Матрица исходного основания

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| LA-056 | Один neutral event/budget owner, lazy parent boundary, forwarding совместимости. | Реальные imports без copied packages;14 event/enum exports тождественны canonical owner, budget legacy alias тот же. Root API разрешает настоящий monitor. Existing DTO guards/wire aliases и fresh old-FQN pickle controls работают. | G01: supported runtime/pytest/format extras/full suites/packaging. G02: actual historical corpus и applicability не аттестованы relocation controls. |

## 3. Producer → consumer

[Root lazy facade](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/__init__.py) импортирует только canonical event contracts eager; [integration facade](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/__init__.py) откладывает executable exports. [Legacy events](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/events.py) — forwarding, не копия classes.

[MetricBudgetPolicy](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/contracts/metric_budget.py) нейтрален; ReadinessPolicy и executable mapping остаются в readiness_mapper. Некоторые consumers по-прежнему импортируют compatibility path, но получают один объект, не второй тип. Это не само по себе незавершённый repair.

[Actual monitor](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/monitor.py#L63-L154) принимает ShiftDetectedEvent → adapter строит ShiftRiskEvent → readiness → root-cause/incident DTO. Этот путь выполнен на synthetic shift без registry authority; данные инцидента не означают состоявшийся deployment/retrain.

## 4. Проверки

| Проверка | Результат |
|---|---|
| P01 | Холодные root/events/budget/legacy-events imports не загружают orchestration; тот же live finder ловит actual monitor import. |
| P02 | Все4 facade bodies PASS; compatibility6 bodies/15cases дают14PASS и1 environment FAIL (bad-date-time schema). Всего10 bodies/19cases,18PASS. |
| P03 | Все14 legacy event/enum exports — canonical class objects; old budget FQN сохраняет identity. Behavioral ReadinessPolicy не перенесён. |
| P04 | No-channel: manual schema/runtime reject, plain generated schema accepts. Reversed window: manual shape accepts, runtime rejects. Это защищённое различие LK35. |
| P05 | Реальный monitor с shift0.95: R2; тот же diagnostic-only input: R4. Typed risk/incident остаются, registry_record=None. |
| P06 | Два новых холодных readers загружают trusted synthetic old-FQN event и budget pickle; payload/type совпадают. Исторический corpus не подменяется fixture. |

[Probe](../04_Проверки/C121_DDM01/probe_ddm01.py) · [наблюдения](../04_Проверки/C121_DDM01/run02/observations.json) · [команды](../04_Проверки/C121_DDM01/commands.json) · [границы](../04_Проверки/C121_DDM01/Чтение_и_границы.md).

## 5. Остаток и сохраняемое поведение

**C121-G01 — native tooling.** Product imports и monitor здесь настоящие, без product AST/stubs. Но pytest отсутствует, Python3.12/Pydantic2.13.4 не supported3.14 pinned environment. `FormatChecker()` не гарантирует наличие date-time checker: optional RFC3339 dependency отсутствует. [Test extra](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/pyproject.toml#L169-L179) его требует, поэтому локальный FAIL не новый product schema defect. Полные fresh-consumer/mirror suites, typing, wheel/sdist, import-time/memory qualification остаются UNRUN; installs не делались.

**C121-G02 — historical/applicability.** Current extensions CalibrationValidityProjection и optional model identity в CalibrationAudit сохраняют legacy reading, но один current HEAD не доказывает byte-equivalent migration commit. Синтетический old-FQN replay полезен, не заменяет реальный historical/plugin corpus. Актуальность calibration, observation window, R2 signoff exception и non-overridable failures будут разобраны отдельно в следующем DDM-02; class relocation не объявляется их ремонтом.

Сохранить ручную [channel schema](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ddm/integration/shift_event.schema.json#L69-L73), runtime reversed-window guard, pass/pass_ alias, event_type literals, strict extras и разные drift/degradation/quality/readiness состояния. DDM остаётся monitoring support, не замена N11 accounting или parameter calibration. Отсутствие универсального нового detector не препятствует подтверждённому contract repair.

[Карточка](../05_Источники/DDM-01_исходные_строки.txt) · [pinned sources](../05_Источники/C121_источники.json) · [остатки](../01_Реестры/C121_остатки.json).

**121/127. Следующий DDM-02; осталось6 пакетов. Фаза заданий исполнителю ещё не начата.**
