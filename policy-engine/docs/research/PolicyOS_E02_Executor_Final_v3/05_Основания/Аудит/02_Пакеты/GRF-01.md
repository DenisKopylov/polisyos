# GRF-01 — static ADMG m-separation и perfect-do
## C48 · свежая проверка 31 октября — 1 ноября 2026 года

**Порядок:** 48/127, LANE-05. **Исходные IDs:** B216, B217, LA-007, LA-019. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит.

## Решение

Исходные ошибки fork/collider и сохранения confounding edge при perfect-do **не воспроизводятся в проверенной конечной области**. Найден общий endpoint-aware separator; perfect-do удаляет входящие directed и incident bidirected edges, сохраняя исходящие. Свежий запуск дал **20 bounded MATCH и 3 PASS неизменённых существующих test bodies**: 200 трёхузловых ADMGs, 2400 separation queries и 19200 surgery queries. Нового подтверждённого R-дефекта не установлено.

Это **не native pytest PASS и не полное закрытие**. Python 3.12 отличается от поддержанной проектом 3.14; pytest отсутствует. Полные imports, installed distributions, ID/IDC и persisted CausalEngine route не квалифицированы. LA-предписания проверены именно как точечное отсутствие пустых siblings при сохранении настоящих packages, а не как разрешение удалить семейство методов.

**Восстановление:** после потери рабочей среды сохранённый внешний checkpoint заканчивался C47. Этот C48 заново прочитан и исполнен; утраченные прежние C48–C75 не являются доказательством и не включены в текущий счёт.

## 1. Матрица исходных задач

| ID | Исходная проблема | Найденное решение и исполнение | Что остаётся |
|---|---|---|---|
| B216 | Старый traversal путал fork/noncollider и collider, в том числе bidirected; двусторонний AND не исправлял семантику | Traversal хранит endpoint mark на входе; collider определяется двумя arrowheads, активируется через предков Z. Common owner вызывается do-/σ-rules. Конечный независимый oracle совпал | C48-G01: native и полный ID/IDC; G03: профиль и научное основание |
| B217 | `do(X)` оставлял X↔Y и давал неверную action deletion | Удалены incoming directed и все incident bidirected edges; outgoing сохранены. Все 8 action sets на каждом из 200 ADMGs совпали с latent-DAG surgery | G01: native consumer/artifact path; G03: не переносить вывод на stochastic/fixing/temporal semantics |
| LA-007 | Пустой `id_engine.py` скрывал смысл настоящего package | Точный sibling отсутствует; `id_engine/__init__.py` и core/transport/counterfactual/api facade сохранены | C48-G02: installed imports, поддержанные filename loaders и distribution contents |
| LA-019 | Пустые `causal_engine.py` и `interference.py` рядом с рабочими packages | Оба точных siblings отсутствуют; настоящие facade implementations и exports сохранены | G02: wheel/sdist и actual native consumers; API-01 остаётся отдельной задачей |

Исходная карточка прочитана полностью, строки 5840–6034. LK05 защищает настоящий ID package; LK13 не даёт объявлять всё семейство BERL legacy. В этой проверке ничего не удалялось. A07-ограничение о factual ancestors/shared noise не превращено в утверждение о проверенном counterfactual runtime.

## 2. Producer → consumer

Реальный `CausalGraphModel` несёт graph type, nodes, edge endpoint marks, lag и metadata. Canonical admission восстанавливает содержимое DTO, а не доверяет только внешнему имени класса; static scalar-query owner отказывает partial completion/temporal профилям. Cache получает canonical validated graph, и immutable adjacency не отменяет повторную проверку входа. [S04:156–255](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_graph.py#L156-L255) [S01:184–307](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L184-L307)

`apply_rule1/2/3` получают этот graph и настоящий `DistributionRef`, делают соответствующую surgery и вызывают общий separator. Успех возвращает **новый DistributionRef + IR ProofStep**, а не просто boolean. Recursive rewrite consumer читает эти результаты, переносит proof steps и изменяет AST leaves. В этой проверке реально исполнены отдельные rules; весь recursive rewrite/counterfactual post-pass не запускался. [S02:80–267](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/do_calculus.py#L80-L267) [S02:280–436](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/do_calculus.py#L280-L436)

IDC route прочитан отдельно: он валидирует query/profile, строит ID numerator для Y∪Z и denominator для Z, переносит неидентифицируемый результат, либо создаёт ratio и positivity step. Это реальный соседний consumer, **но его прочтение не означает исполнения полного ID/IDC**. Artifact persistence, последующее чтение доказательства и пользовательский CausalEngine report здесь не получены. [S06:1081–1253](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/core.py#L1081-L1253)

## 3. Что устанавливает исправленный separator

Внутренний путь хранит `(node, incoming_mark)`. На внутреннем узле collider — это ARROW на входе и на выходном endpoint; такой переход разрешён, только если узел в An(Z). Noncollider закрывается при conditioning на самом узле. Это устраняет семантическую ошибку, а не скрывает её проверкой обратного направления. [S01:699–801](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L699-L801)

- **P01–P05:** fork и chain открыты без Z и закрываются через middle node; collider и bidirected collider ведут себя наоборот; conditioning на descendant открывает collider.
- **P06/P07:** направления запроса симметричны в четырёх контролях; reverse-stored directed edges дают ту же fork-семантику.
- **P13:** настоящий Rule 1 отказывает удалить X из conditioning при fork, но удаляет при collider, возвращая настоящий typed proof.
- **P16:** σ-Rule 1 на selection-augmented graph различает тот же fork/collider. Сохраняющийся у σ-rules двусторонний AND здесь избыточен относительно исправленного symmetric primitive; он не является самостоятельным доказательством правильности.
- **P18/P19:** PAG и lag>0 явно отклонены; прогретый cache не пропускает затем поданный invalid endpoint profile. Это положительный admission control, не обещание PAG/temporal inference.

Три существующих test bodies из `test_admg_latent_oracle.py` прочитаны целиком и исполнены неизменёнными. Reference algorithm **другой**: каждый bidirected edge разворачивается в latent common cause, затем выполняются ancestor restriction, moralization и connectivity после удаления conditioned nodes. Runtime использует endpoint-state traversal. Полный конечный denominator — 25 directed DAGs × 8 bidirected subsets = 200, 6 ordered pairs × 2 conditioning sets = 2400. [S05:1–164](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py#L1-L164)

Это сильнее нескольких одинаково устроенных helper assertions, но не доказательство произвольного числа узлов, всех mixed graph families или корректности supplied causal structure. NetworkX не устанавливался и не запускался.

## 4. Perfect-do, не observation/fixing

Owner проверяет реальное направление даже при reverse storage. Для intervention target удаляется входящий directed edge; bidirected edge удаляется, если любой конец вмешиваемый. Исходящий causal effect не отрезается. Новый graph сохраняет типизированные поля и metadata, исходный объект не изменяется. [S01:368–390](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L368-L390) [S01:485–584](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py#L485-L584)

**P08–P12:** чистый X↔Y исчезает после do(X); в P→X→Y и X↔Z остаётся X→Y; исходные bytes-эквивалентные DTO data и metadata сохраняются; multi-action и reverse-storage controls совпали. **P14/P17:** actual Rule 3 и σ-Rule 3 удаляют действие X в pure confounding case. **P15:** Rule 2 использует другую, outgoing surgery и переводит действие в conditioning.

Finite surgery oracle рассматривает 8 action sets × 12 queries × 200 ADMGs = **19200**. В latent reference удаляются только incoming edges в observed action target; влияние latent cause на другого ребёнка не удаляется. Это соответствует perfect intervention в заявленном профиле, но не является реализацией conditioning, fixing, stochastic intervention или произвольной counterfactual abduction.

## 5. Что именно сохранено при retirement

Все три точных `.py` siblings отсутствуют; package directories и substantive facades существуют и прочитаны. `id_engine` собирает core/transport/counterfactual/api; `causal_engine` сохраняет CausalEngine и readiness error; `interference` — estimators, identification functions и contract aliases. [S07](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/id_engine/__init__.py) [S08](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/causal_engine/__init__.py) [S09](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/interference/__init__.py)

Скан всех **8936 Git-tracked `.py`/`.toml` файлов** дал 23 substring hits: среди них исторические handoffs, docstrings и другие filenames. Никакое из этих чисел не выдано за отсутствие всех динамических loader consumers. Bounded `find_spec` разрешает три package `__init__.py`, но использует parent namespace shells. Попытки package import отдельно сохранены: id_engine и causal_engine остановлены Python 3.14 exception syntax; interference — отсутствующим export в нашем analytics shell. Последнее — **ограничение harness**, не обнаруженный product regression.

## 6. Среда, честные остатки и сохранённые ограничения

**C48-G01:** запустить native tests/ID/IDC/actual artifacts в поддержанной среде. Здесь используются пять parent namespace shells и `typing_extensions.get_protocol_members` для Python 3.12; product graph DTO и function bodies не подменены. Pytest остановлен до collection, обычный graph import — на отсутствующем `typing.get_protocol_members`. Установленный Pydantic 2.13.4 также вне project `<2.13`. Поэтому isolated PASS не закрывает supported dependency profile.

**C48-G02:** wheel/sdist, public imports и поддержанные filename loaders не проверены. Сохранять полезные packages и существующие consumers; не возвращать пустые файлы ради буквального соответствия старым путям и не удалять пакет под предлогом legacy cleanup.

**C48-G03:** математическая finite graph-correctness не создаёт эмпирическое основание модели мира. Нужна честная связь graph basis → estimand/proof → сохранённый результат → admissible consumer. Синтетический graph oracle не становится observed data. LLM может оставаться semantic proposer; отсутствие универсального deterministic model inventor не является дефектом B216/B217.

Первый probe завершился assertion из-за слишком узкого **ожидания имени exception в harness**: PAG корректно вернул более специфический PartialGraphCompletionSemanticsError. Исходный harness и failure log сохранены; изменено только это ожидание. Ни продуктовый код, ни существующие tests не менялись.

[Результаты](../04_Проверки/C48_GRF01/bounded_diagnostics.json) · [Команды](../04_Проверки/C48_GRF01/commands.json) · [Native-границы](../04_Проверки/C48_GRF01/native_verification.json) · [Источники](../05_Источники/C48_источники.json) · [Остатки](../01_Реестры/C48_остатки.json).

**48/127 пакетов рассмотрены ограниченно; 116 уникальных B/LA частично оценены. Следующий — GRF-02. Полного закрытия нет.**
