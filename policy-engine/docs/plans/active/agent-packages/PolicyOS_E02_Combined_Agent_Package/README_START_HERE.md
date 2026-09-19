# Начать здесь — PolicyOS E02

**127 рабочих пакетов:225B +57LA;84 прежних packet IDs сохранены,43 новых добавлены.** Связанные bugfix и migration идут одной ready-очередью, не двумя этапами «сначалаB, потомlegacy».

Главный документ: [PolicyOS_Combined_Remediation_E02_Agent_Bundles.md](PolicyOS_Combined_Remediation_E02_Agent_Bundles.md). Полные B/LA карточки,4 поздних уточнения и36 LK ограничений включены в нужные задания. Два непрерывных оригинала сохранены в `source/`; E01 — в `parent/` как история. Исторические audit evidence ZIP/probes отдельно не переданы и не выданы за включённые.

Для Sol: [SOL_ORCHESTRATOR](SOL_ORCHESTRATOR.md), [EXECUTION_GUIDE](EXECUTION_GUIDE.md), [BUNDLE_INDEX](BUNDLE_INDEX.md), `bundle_manifest.json`. Для I1/I2: [MIGRATION_LANES](MIGRATION_LANES.md), [LEGACY_CROSSWALK](LEGACY_CROSSWALK.md), [WRITE_OWNERSHIP](WRITE_OWNERSHIP.md), [CROSS_BOUNDARY_MATRIX](CROSS_BOUNDARY_MATRIX.md), [CHECKPOINTS](CHECKPOINTS.md), `relocation_map.json`. Исполнителю — [TEAM_RULES](TEAM_RULES.md) и **один** файл `bundles/`, exact base/worktree/lease. Проверяющему — тот же packet/patch и [REVIEWER_PROMPT](REVIEWER_PROMPT.md).

По умолчанию Sol +14Luna:9writers+3reviewers+2integrators; варианты12/16 сохранены. **Mac budget не увеличен:** максимум2L или1exclusiveN/C. Никто постоянно не мониторит железо; чтение/код/review идут при занятой test queue. Native tests, generated-client build и package validation запускаются малыми адресными проверками/6окнами CP, не отдельными full CI на57LA.

Первый ready-набор: CYC-01, SEL-01, STA-01, ING-01, OPT-01, FRY-01, DDM-01, GRF-01, UDF-01. После него динамическая выдача по actual contracts/leases. Path map не позволяет последующим B-тестам проверять старую копию после перемещения. DDM R2, handwritten schema, historical readers, разные calibration роли защищены.

[Изменения E01→E02](CHANGES_FROM_E01.md); `E01_TO_E02.json` помогает перенести actual progress без обнуления. **Это план, не config Codex и не доказательство исправности проекта.** Current HEAD и native PolicyOS/Mac tests здесь не запускались.

Проверка файлов комплекта без third-party dependencies:

```bash
python3 verify_plan.py
```

Скрипт проверяет source preservation, полное распределение, DAG, mutex, amendments, ссылки и checksums; не запускает PolicyOS. QA результаты относятся только к launch kit. Не запускайте parent/E01 как второй параллельный план.
