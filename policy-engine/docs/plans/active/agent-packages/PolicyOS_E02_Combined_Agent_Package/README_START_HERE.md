# Начать здесь — PolicyOS E02

**127 рабочих пакетов:225B +57LA;84 прежних packet IDs сохранены,43 новых добавлены.** Связанные bugfix и migration идут одной ready-очередью, не двумя этапами «сначалаB, потомlegacy».

Главный документ: [PolicyOS_Combined_Remediation_E02_Agent_Bundles.md](PolicyOS_Combined_Remediation_E02_Agent_Bundles.md). Полные B/LA карточки,4 поздних уточнения и36 LK ограничений включены в нужные задания. Два непрерывных оригинала сохранены в `source/`; E01 — в `parent/` как история. Исторические audit evidence ZIP/probes отдельно не переданы и не выданы за включённые.

Для Sol: [SOL_ORCHESTRATOR](SOL_ORCHESTRATOR.md), [EXECUTION_GUIDE](EXECUTION_GUIDE.md), [BUNDLE_INDEX](BUNDLE_INDEX.md), `bundle_manifest.json`. Для I1/I2: [MIGRATION_LANES](MIGRATION_LANES.md), [LEGACY_CROSSWALK](LEGACY_CROSSWALK.md), [WRITE_OWNERSHIP](WRITE_OWNERSHIP.md), [CROSS_BOUNDARY_MATRIX](CROSS_BOUNDARY_MATRIX.md), [CHECKPOINTS](CHECKPOINTS.md), `relocation_map.json`. Исполнителю — [TEAM_RULES](TEAM_RULES.md) и **один** файл `bundles/`, exact base/worktree/lease. Проверяющему — тот же packet/patch и [REVIEWER_PROMPT](REVIEWER_PROMPT.md).

Рабочая раскладка — Sol +15 прямых leaf workers: 8 исполнителей, 3 независимых reviewer, 2 preparer/I2, 1 I1 broker и 1 последовательный integration writer. Preparer может стать девятым исполнителем, а при четырёх кандидатах без первого review — четвёртым reviewer; это не создаёт новых руководящих слоёв. Если runtime даёт меньше worker seats, используется максимум доступных с сохранением независимости review и изоляции записи, а фактический предел фиксируется. **Общий Mac-бюджет — 7 resource-bearing process groups и 7 L-equivalent units:** micro=0.5, standard=1, неизвестный medium сначала измеряется (обычно 2–3); N/C занимает весь бюджет и запускается эксклюзивно. Compute permit не закрепляется за агентом и освобождается после cleanup/receipt, до review. I1 принимает immutable request с exact argv/cwd/worktree/SHA/output root; байты заявки атомарно копируются в уникальную ready-запись и получают SHA, прямые обходы очереди запрещены. Не держим permit из-за чтения/review и не мониторим железо постоянно; перед новым worktree/environment/install/build сохраняем минимум 20 GiB свободного диска. Native tests, generated-client build и package validation запускаются малыми адресными проверками/6 окнами CP, не отдельными full CI на57LA.

Сохранённый historical seed (не текущий dispatch и не barrier): CYC-01, SEL-01, STA-01, ING-01, OPT-01, FRY-01, DDM-01, GRF-01, UDF-01. Текущая работа выдаётся из live B+LA rolling queue: минимум пять полностью специфицированных ready-пакетов сверх active, с actual contracts/leases перед каждым claim. Path map не позволяет последующим B-тестам проверять старую копию после перемещения. DDM R2, handwritten schema, historical readers, разные calibration роли защищены.

[Изменения E01→E02](CHANGES_FROM_E01.md); `E01_TO_E02.json` помогает перенести actual progress без обнуления. **Это план, не config Codex и не доказательство исправности проекта.** Current HEAD и native PolicyOS/Mac tests здесь не запускались.

Проверка файлов комплекта без third-party dependencies:

```bash
python3 verify_plan.py
```

Скрипт проверяет source preservation, полное распределение, DAG, mutex, amendments, ссылки и checksums; не запускает PolicyOS. QA результаты относятся только к launch kit. Не запускайте parent/E01 как второй параллельный план.
