# B09/V3: новый источник при сохранении прежней оценки

26 октября 2026. Ответ G на [пакет 123eb4c2](https://github.com/DenisKopylov/polisyos/blob/123eb4c215a76736deaa7018688e0aeace8efa90/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/g-questions/acquisition-source-only-20261026/README.md). `architecture_selection=selected_by_G`, `code_acceptance=false`, `closure_ids=[]`. Самостоятельное исследование, без субагентов, product imports/tests и тяжёлых процессов.

**Выбран вариант 1 с уточнением архитектуры:** новую source occurrence сохранять через существующий положительный admission receipt; отдельный owner decision определяет необходимость semantic continuation. При доказанной эквивалентности и допустимости сохранения оценки выпускать новый terminal **`source_admitted_evaluation_retained`**. Старые WMR/N5/candidate остаются прежними объектами с прежними источниками. Новый источник получает проверяемую связь с ними, но не становится задним числом входом старого расчёта.

Ключевые ограничения решения:

- `admitted_observation_delta > 0` и unchanged evaluation — совместимые факты. `quarantined_no_growth` по-прежнему требует literal zero и одинаковые membership snapshots.
- Equality — owner-recomputed relation для **полного основания всех пропускаемых стадий**, а не равенство scalar, epoch receipt, UUID или полного WMR artifact hash. `not_established` никогда не разрешает retained terminal.
- Fresh GET показывает отдельно новый acquisition source и сохранённый evaluation source. Оно не присваивает currentness, новую эмпирическую независимость или publication authority.
- Один существующий route/action owner, один typed decision и существующие CAS/event/head механизмы. Новый scheduler, глобальный cache или provenance subsystem не нужны.

Читать:

1. [01 — контракт, equality, состояния и выбранные версии](01-decision.md).
2. [02 — реализация, recovery, migration и проверки](02-implementation-and-checks.md).
3. [03 — самостоятельный редтим, первичные источники и границы](03-critical-review.md).
4. [inputs.json](inputs.json) — exact Git/RAW inputs и выполненные лёгкие проверки.

Source анализа — committed `6ad021abaaec967ce48122e5f94985112dc19e59`; пять WIP postimages отдельно восстановлены в памяти из pinned RAW patch и проверены по SHA256. Это не принятие WIP и не global source/input/backend freeze. Controlled fixture из пакета остаётся **UNRUN** и не доказывает последовательное поступление второго источника. Исполнителю разрешён описанный engineering выбор без нового общего вопроса G; full B09 closure требует actual producer-to-history evidence и отдельной adjudication.
