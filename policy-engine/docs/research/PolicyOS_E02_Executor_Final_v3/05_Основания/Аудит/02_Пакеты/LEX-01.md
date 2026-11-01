# LEX-01 — норм-различия, compliance transitions и темы воздействия

**C123 · LANE-11 · LA-017 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Полезная функция сохранена под Lex: `normpack/diff.py` сравнивает нормы, `legal_evaluation/impact_diff.py` выполняет passes и строит transitions. Исторические simulator-модули — узкие aliases. `AffectedKPI` остаётся совместимым именем поля, но его описание и actual renderer прямо называют значения candidate topics, без измеренной величины/направления эффекта.

**6 MATCH; 1 unchanged test body PASS. C123-R01 (low):** grouping issue paths через slash может скрыть изменение структурного пути, даже когда fingerprints различаются. Остальные ограничения native persistence и содержательной authority остаются G, не мнимым полным закрытием.

## 2. Матрица исходного задания

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| LA-017 | Смысловой перенос без потери norm diff, issues, provenance/persistence; tags не измеренные KPI; aliases и historical schema явные. | Actual owners и aliases найдены, четыре класса norm change исполнены; actual selected AST backend/LegalPass/analyzer дают expected transition. Default1.0 и opt-in1.1 различены, CLI свежо читает сохранённый report; topics/limitations видимы. | R01: path identity collision в issue grouping. G01: full native CAS/selected refs/CLI/compatibility UNRUN. G02: legal source/context/coverage и effects не установлены, отчёт это не скрывает. |

## 3. Producer → consumer

[Norm diff](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/normpack/diff.py#L66-L184) строит deterministic изменения и отвергает duplicate norm IDs. [Analyzer](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py#L138-L365) фиксирует/deduplicates pass plan и подставляет именно сравниваемый NormPack поверх caller context. Default legal backend — честный stub, не rule evaluation. Actual AST backend в P02 введён объектом: metadata правильно остаётся custom/unestablished, а не присваивает authority по self-label.

[Selected reader](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py#L505-L645) связывает1.1 с selected diff/manifest, пересчитывает locally derivable counts/topics/issue multiset. Он не доказывает полноту всех правовых норм. Legacy1.0 остаётся явно unbound. [Actual CLI consumer](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/core/components/_cli_lex.py#L83-L117) после persistence выполняет свежий read перед display, а не доверяет только объекту producer. Эти persisted guards прочитаны, но не исполнены в текущем runtime.

[Renderer](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/simulator/cli.py#L54-L131) сохраняет jurisdiction/backend limitations и отделяет Candidate Impact Topics от measured effects/legal conclusions.

## 4. Фактические проверки

| Проверка | Результат и предел |
|---|---|
| P01 | 1 unchanged existing diff test PASS: unchanged/added/removed/modified. Native NormPack, selected actual diff. |
| P02 | 4 caller-context controls: подмена norm_pack не заменяет actual compared packs; income2 при old>=1/new>=3 даёт new blocker. Actual AST policy/evaluator/LegalPass/analyzer, не production law. |
| P03 | Empty/frozen/deduplicated pass plans;3 invalid plans refused; unchanged failing rule не создаёт false transition; stub честно помечен. |
| P04 | Три rule types дают только qualitative topics с direction unknown; actual Markdown явно not measured. |
| P05 | Direct reconciliation helper принимает consistent report и отвергает tampered norm count/topic/issue count. Не selected reader, не CAS, не issued1.1. |
| P06 | Разные typed paths с одинаковым slash join и разными fingerprints дают empty compliance_deltas. Это воспроизведение residual, не product PASS. |

[Probe](../04_Проверки/C123_LEX01/probe_lex01.py) · [наблюдения](../04_Проверки/C123_LEX01/run02/observations.json) · [команды/exit codes](../04_Проверки/C123_LEX01/commands.json). Run01 harness error сохранён; run02 исправляет external namespace, не checkout.

## 5. Остаток и сохраняемое поведение

**C123-R01 — потеря границ path (low).** [Grouping](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py#L647-L695) превращает `['norm_pack','n.income','a/b']` и `['norm_pack','n.income','a','b']` в один key. При одинаковых severity/message/code actual analyzer считает issues неизменёнными, хотя actual fingerprints различны. Сохранён [report](../04_Проверки/C123_LEX01/run02/path_collision_report.json). Расширить existing identity/grouping representation, сохранив multiset/severity semantics и explicit historical compatibility. Не установлено, что текущий expr_ast генерирует такие пути; persisted admission/security consequence не заявляется.

**C123-G01 — native compatibility.** Повторить на supported3.14 actual aliases, real CAS bytes/refs, self-reference omission, manifest/profile binding, reader-first CLI, historical1.0 и explicit opt-in1.1/rollback. Source tests содержат эти различия, но отсутствующий pytest и blocked imports не превращены в product defects. Coarse report_id намеренно не content identity; существующий CAS distinction не удалять.

**C123-G02 — authority и содержательный предел.** Default stub не оценивает нормы; expr_ast покрывает только assigned rules. Ни backend label, ни одинаковая jurisdiction string, ни корректный NormPack не подтверждают authenticity/applicability/coverage/context. Сохранить нынешнюю честность. Экономический/причинный эффект требует existing Scientist/Foundry evidence, не нового численного механизма по OBLIGATION tag. LLM может предложить смысл/структуру, но synthetic source не становится эмпирическим основанием. Отсутствие универсального детерминированного изобретателя правил не самостоятельная ошибка.

[Исходная карточка](../05_Источники/LEX-01_исходные_строки.txt) · [pinned sources](../05_Источники/C123_источники.json) · [остатки](../01_Реестры/C123_остатки.json) · [границы](../04_Проверки/C123_LEX01/Чтение_и_границы.md).

**123/127. LANE-11 рассмотрен ограниченно. Следующий DFK-01, начало LANE-12; осталось4 пакета. Фаза заданий исполнителю ещё не начата.**
