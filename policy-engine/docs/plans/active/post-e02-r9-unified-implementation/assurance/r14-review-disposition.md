# R14: review и решения по найденным пробелам

Дата: 23 октября 2026. Baseline `c8986d035f12c1c3d9e5d0d57e369fe8257bccbc`; статический code pin `dccea950845cda5b38f026e7770c07819d31f4d9` не является принятой базой E02. Документарная работа; implementation, tests, builds, installs, product imports и production reads не выполнялись.

Шесть прямых исследовательских помощников разобрали search, hybrid/numerics, legal, documents, learning и quality. Три других прямых reviewer атаковали capability/ограничения, legal/document и execution/allocation. Дочерней делегации не было. Root самостоятельно прочитал результаты, сверил ключевые static divergences (LLM client без invocation; запрет active LLM-memory; фактический HTML-backed DOCX helper), правила G6/GYD-23/Rule5/WP, исходные задачи и каждую новую карточку. Research — вход, не автоматически принятое решение. Ошибочный anchor `search/space.py` исправлен на существующий `search/strategies/space.py` по immutable tree.

## Findings и dispositions

| Finding / класс | Принятое исправление | Различающий будущий сигнал |
|---|---|---|
| R14-C01, P10/P38: структурно разные, но бесполезные варианты могли закрыть productive claim | DES-02/10, machine obligations, architecture и quality protocol требуют заранее определённый meaningful positive; all-null сохраняет not_established. Это одна исправленная class, не два независимых дефекта | Подставить feasible/distinct, но decision-irrelevant альтернативы: productive claim не закрывается при зелёной plumbing |
| Execution medium, P27: общий formulator/ledger имел несовпадающие writer keys | DES-01 sole formulator; DES-02 sole hypothesis ledger; DES-09 prompt/tool receipt + context. Write candidates/read-only roles, conflict registry и cards согласованы | Полный map этих путей даёт по одному writer; N4 fresh reader разрешает actual invocation ref |
| Legal refinement 1, P32 | Current-law conclusion потребляет actual CAP-05 relation artifact; interface agreement/URL недостаточны | Удалить relation output при сохранённых citations: permission limited/refused, amendment candidate сохраняется |
| Legal refinement 2, P08 | Разделены legal-valid, observation/receipt/verification и knowledge/as-of | Поздняя correction раннего effective date не переписывает historical knowledge replay |
| Document refinement 3, P05/rights | Нормальное хранение human edits подчинено LIF-05 retention/use, не только rollback | Истёкшее право при прежнем revision ID прекращает запрещённый use/export/copy |
| Document refinement 4, P38 | Actual DOCX text/table сверяется с semantic sidecar, а не только с форматом | Изменить body/cell при прежних IDs/sidecar: старое основание не наследуется |
| Evaluation refinement 5, P13 | Два независимых labelers — benchmark protocol, не per-document approval office | Отсутствие панели не блокирует native machine-checkable relation; только affected evaluation claim открыт |

Независимые узкие повторные review подтвердили исправление перечисленных вопросов: [capacity](r14-reviews/red-capacity.md), [legal/documents](r14-reviews/red-legal-documents.md), [execution](r14-reviews/red-execution.md). Это GO для документарного delta, не product PASS.

## Самостоятельное review и полнота

[Машинная запись root review](r14-root-review.json) связывает полные task/solution hashes десяти новых и 24 дополненных строк с индивидуальным выводом. Остальные 85 task rows не изменены; исходные поля прежних 109 сохраняются, кроме двух явных execution joins и additive extensions. Исторические GY/Atlas/debt/R9 inventory files остаются byte-identical. Новые десять obligations имеют собственный [реестр](r14-capability-obligations.json), а не новые старые finding IDs.

Root отдельно исключил лишние зависимости: numeric EVSI не обязательна для любой acquisition; O1/O3 activation не блокирует candidate search-memory; DES-07 может готовиться по interface DES-06; DES-10 не требует собственного финального результата до freeze. Производительные positive controls относятся к system-under-test, а no-op/removal arms ожидаемо служат контрконтролями. Документация не обещает абсолютную семантическую эквивалентность произвольного текста и не заставляет все идеи сразу стать executable programs.

Проверка полного текущего документационного набора: [r14-validation.json](r14-validation.json). Product quality/effect, authentic case, live provider и audience evidence остаются будущими отдельными результатами. Новых SDD решений не требуется для выбранных reuse/extend путей; прежние AS2/WP вопросы остаются в своём процессе. Любое будущее изменение ratified boundary требует отдельного согласования.
