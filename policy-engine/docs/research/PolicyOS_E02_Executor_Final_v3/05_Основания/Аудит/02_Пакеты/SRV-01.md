# SRV-01 — чистые contracts и единый переход ask/tell
## C14 · выпуск v012 · 31 октября 2026 года

**Исходная задача:** LA-014 (M), целиком в области SRV-01. **Очередь:** LANE-02; предшественник CTL-03; следующий по исходному порядку SRV-03. **Исследованный commit:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Проверка read-only; код продукта, тесты, конфигурация и зависимости не менялись.

## Решение по пакету

**Частичная оценка, не полная приёмка.** Основной перенос уже сделан: DTO/protocols находятся в `contracts.py`, concrete bridges — в `adapters.py`; `LegacySearchServiceAdapter` наследует существующий driver и использует тот же `_SearchLifecycleOwner`. Adapter не редактирует собственными присваиваниями history/best. Исторические импорты разрешаются лениво, а у сериализуемых record-types явно сохраняются прежние Python-адреса. Повторять extraction или создавать второй SearchService не нужно.

**Новый подтверждённый локальный дефект C14-R01:** проверка duplicate/pending и применение `tell` не являются одной защищённой операцией. Два одновременных ответа одного предложения записываются дважды; один caller после этого получает `KeyError`. То же воспроизведено при однопоточном callback-reentry. Строго последовательный duplicate правильно отвергается. Это нарушение единичности принятия ответа, не свидетельство двух реальных физических расчётов, денежного двойного списания или защищённой публикации.

**Отдельные границы, не приравненные к production-багам:** `ask` молча отбрасывает `goal/search_space`; отдельно вызываемые `ask/tell` не наследуют orchestration-контроль лимитов и стоимости полного `run_search`. Внешний caller может владеть этими правилами, однако договор такой композиции в проверенном наборе не установлен. Их нужно явно связать или ограничить до поддержанного профиля; нельзя выдавать наличие общего state-owner за полную эквивалентность API.

## 1. Исходный критерий и содержательная цель

[E02](../05_Источники/SRV-01_исходные_строки.txt) требует убрать concrete runtime из contracts, сохранить стабильные DTO и совместимые адреса, делегировать `tell` владельцу состояния, проверить unknown/duplicate IDs, typed evaluation, frontier и продолжение. Появление protocol не считается готовым native driver; перенос файлов без устранения второго редактора состояния не завершает LA-014.

Рабочая установка о LLM сохранена. LLM может выдвигать гипотезы, выбирать постановку и следующий исследовательский шаг. Эта миграция должна обеспечить точную передачу предложения и результата, а также согласованное принятие ответа. Она не требует универсального алгоритмического генератора гипотез и не оправдывает дополнительный общий запрет исследовательских вычислений.

## 2. Матрица состояния

| Критерий LA-014 | Реализация, которую сохранять | Граница доказательства / остаток |
|---|---|---|
| Contracts без eager controller/funnel | Прямые runtime imports отсутствуют в прочитанных sections; adapters разрешаются `__getattr__` | Полный cold package import с транзитивными зависимостями здесь UNRUN |
| Concrete adapters отдельно | Полный `adapters.py`, blob совпал; собственная history/best отсутствует | Funnel-owner заменён интерфейсной фикстурой в опытах |
| Один state transition | `tell → owner._accept_tell → SearchRunState.apply_tell_transition` | C14-R01: единый owner ещё не обеспечивает атомарность admission/commit |
| Unknown/duplicate IDs | Неизвестный ID и последовательный повтор отвергаются; pending и completed различаются | Пересекающийся повтор проходит обе проверки до изменения completed |
| Сохранение предмета | Снимки предложения отделены от caller/generator; out-of-order ответы хранят исходный payload | Полные policy source/strategy/candidate bindings не исполнялись |
| Typed-invalid не становится best | Общий resolver/consumer сохраняет invalid; корректный scalar без typed остаётся возможен | Настоящий PolicyEvaluationVector/ObjectiveStack и protected consumers UNRUN |
| Продолжение и limits | `run_search` использует текущие stopping/budget механизмы | Manual `ask/tell` требует отдельного явного lifecycle/admission-договора |
| Compatibility | Lazy alias identity; у record types сохранены исторические `__module__` | Нативные pickle/installed imports и конечный внешний consumer census не выполнены |

## 3. Что уже изменено: перенос имеет смысл, а не только новое имя файла

### 3.1. Contracts и lazy facade

В `contracts.py` определены `CandidateProposal`, `CandidateStrategyContext`, `EvaluationBundle`, `TellResult`, `SearchService`, `FunnelService`, records и внутренние ports. Concrete adapters импортируются лишь при обращении к двум историческим именам. Типы funnel в annotations находятся под `TYPE_CHECKING`. Это не утверждение, что весь импорт любого верхнеуровневого пакета лёгкий: contracts импортирует своих действительных DTO/objective владельцев, а parent package имеет собственную eager-поверхность. [S01, S06]

Перед сохранением прежних `__module__` annotations dataclass разрешаются в определяющем модуле и записываются также в dataclass fields. `SearchStatus`, `SearchIteration`, `SearchResult` сохраняют путь controller, transition-types — путь run_state. Это осознанная совместимость сериализации, а не второй экземпляр математического типа. Не следует менять исторические FQN только ради эстетики extraction. [S01]

P02 проверяет реальную ленивую функцию из source excerpt: до обращения concrete runtime не запрашивается; неизвестное имя даёт AttributeError; запрос alias разрешает объект и повторный запрос использует тот же объект. **Это не полный project cold-import**: target-module представлен загруженным точным adapters с fixture зависимостями. P29 проверяет отличие concrete alias access от contract-only доступа. [P02, P29]

Root search facade имеет свою явную поверхность. `OrchestratorFunnelService` доступен через ленивый contract путь; наличие supported alias в contracts не даёт основания дополнительно экспортировать `SearchController`/legacy shortcuts из root. Адресный search обнаружил положительных consumers прежнего адреса в tests; это не полный census внешних клиентов. Удаление compatibility-адреса этим проходом не разрешается. [S06–S08]

### 3.2. Состояние действительно делегировано

Полный `adapters.py` содержит маленький compatibility subclass: сохраняет controller и передаёт `controller._lifecycle_owner` native driver. Driver хранит pending/completed и счётчик запросов; mutation history/best выполняет `_accept_tell`, а запись history/counters — существующий `SearchRunState`. AST-проверка двух полных модулей не обнаружила прямых присваиваний `_history`, `_best_candidate`, `_best_objective`; это конечная проверка только этих двух файлов, не всего репозитория. [S02–S04; P03, P27]

Один владелец — нужное архитектурное достижение. Однако точность его публичных переходов нельзя вывести из самого факта делегирования. Основной остаток расположен на границе pending → applying → completed.

## 4. C14-R01: два ответа одного предложения меняют историю до отказа

### 4.1. Последовательный контроль работает

`tell` проверяет completed и pending, копирует исходное предложение, материализует его и передаёт `_accept_tell`. После возврата удаляет pending, помечает completed и строит `TellResult` по snapshot. При строго последовательном повторе completed уже установлен, поэтому второй `tell` отвергается до изменения состояния. [S03; P08]

### 4.2. Различающий конкурентный опыт

Оба потока допущены к одному pending ID, после чего удерживаются настоящим `threading.Barrier` в интерфейсном objective callback внутри исходного `_accept_tell`. Таким образом, оба прошли проверку ID до её изменения. После освобождения каждый проходит существующий transition. Один успевает удалить pending, другой получает `KeyError` на таком же удалении — **уже после применения собственного transition**.

| Показатель | Наблюдение P14 |
|---|---:|
| Исходных pending-предложений | 1 |
| Ответов `tell` | 2 |
| Обычных строк после обоих ответов | 2 |
| `evaluation_iterations` | 2 |
| Учтённых adapter Stage B | 2 |
| Нормальных возвращённых TellResult | 1 |
| Ошибок после изменения state | 1 × KeyError |
| Выбранный best | отсутствует |

Оценки оставлены неустановленными, перспективность ложной; никакое полезное численное преимущество для опыта не требовалось. Stage B здесь — **счётчик принятых внешних ответов**, не два исполнившихся численных производителя. Registry/CAS и публикация не исполнялись. Record/score/materializer/source boundaries — указанные fixtures. Реальны exact driver/state bodies, выбранный lifecycle body, потоки, barrier, mutable containers и порядок переходов. [P14]

P15 даёт те же две записи без потоков: callback обработки первой оценки повторно вызывает `tell` того же ID; внутренняя операция завершается, внешняя затем меняет state и падает при удалении уже удалённого pending. Это тот же класс незащищённого reentry, не вторая независимая находка.

Положительный конкурентный контроль с двумя **разными** pending IDs сохранил оба соответствующих предмета без исключений. Он не доказывает полную безопасность всех параллельных ветвей, но исключает ошибочный вывод «любые два результата — недопустимый дубль». [P16]

### 4.3. Материальность и минимальный ремонт

**Severity: medium, conditional on overlapping/reentrant tell; confidence: high for local mechanism.** Ложная дополнительная запись и счётчик могут искажать исследовательскую историю; caller видит отказ после изменения состояния и не может трактовать его как отсутствие принятия. Возможное дальнейшее переобучение/двойное расходование квоты — риск, конкретный downstream эффект не исполнен.

Направление: атомарно закрепить обработку pending-предложения за одной попыткой и согласовать commit с поколением существующего state-owner. Допустимы явный non-reentrant профиль либо сериализация/claim-response у нынешнего владельца; для already-applied ответа нужен стабильный исход, а не случайный KeyError. Дорогой внешний evaluator не нужно помещать под общий долгий lock: исследуется принятие уже готового ответа.

P17 — только direction-control: ограниченный внешний guard отвергает второе пересекающееся принятие до mutation, и остаётся одна строка. Он **не является production-патчем** и не решает все несколько-adapter/run-epoch случаи.

Ранее C12 установил старый pending-ответ после нового run. P22 ограниченно повторяет его для связи границ; новой B-карточкой или новым независимым дефектом он не считается. Ремонт должен охватывать принадлежность run и единичность commit вместе, а не ставить отдельные несогласованные locks в каждый wrapper.

## 5. Два существенных ограничения split-профиля

### 5.1. C14-G01: `goal/search_space` не доходят до генератора

В начале `ask` стоит `del goal, search_space`; генератор получает только context и текущее состояние. В P18 две разные цели (снижение аренды / увеличение занятости) и непересекающиеся границы x переданы при одном context. В обоих случаях callback получил строго один и тот же context; отдельные аргументы не сохранены и не валидированы. P19 подтверждает: уже включённые в context поля передаются. [S03]

Это **установленная потеря входных параметров конкретного API**, но не утверждение, что реальный активный caller использует ненулевые значения или что LLM в продукте уже игнорирует цель пользователя. Прочитанные тесты adapter вызывают `goal=None, search_space=None`; их положительный исход этот случай не покрывает. [S07, S08]

Не следует создавать второй goal/search-space owner. Нужно либо адаптировать эти поля к действительной постановке с явным правилом конфликтов с context/config, либо явно ограничить compatibility профиль значениями None и отказать неподдержанному явному запросу. Простое безусловное `context.update(...)` тоже не решает, какая цель и область являются действительными. Возможность LLM выбирать гипотезы не разрешает инфраструктуре молча терять её постановку.

### 5.2. C14-G02: common state не означает общую stop/admission-политику

`run_search` выполняет refresh/check до и после генерации, ограничивает пустые попытки и обычные итерации. Одиночный `ask` вызывает `_prepare_service_run` и генератор, затем увеличивает только собственный `_ask_iteration`. Он не проводит через тот же `_prepare_batch` учёт попыток и stopping. `tell` принимает факт внешнего оценивания, но не читает бюджет. [S03, S04]

В P20 full-run при лимите 1 сделал одну обычную оценку. Три последовательных ask/tell с той же настройкой записали три оценки, `generation_attempts` остался 0. В P21 context-cost 10 при лимите 1 остановил full-run до callback; manual ask вызвал callback один раз. Это **fixture-cost и fixture-producer**, не обход настоящего защищённого LLM-ledger.

Здесь важно не перепутать обязанности: внешний orchestrator может намеренно владеть лимитами и бюджетом split-API, а `tell` должен уметь сохранить уже выполненную работу даже после истечения ресурса. Поэтому blanket-запрет принимать поздние результаты неверен. Но существование такого внешнего владельца должно быть установлено для заявленного профиля; иначе перенос `run_search → ask/tell` меняет управление ресурсом без видимой границы. Следующая SRV-03-приёмка должна отдельно квалифицировать действительного consumer. Создание нового scheduler или второго ledger не предлагается.

## 6. Сохраняемые детали поведения

P04–P13 проверяют с disclosed fixtures: generated ID только при отсутствии поля; `0`, пустой ID, bool и None не переименовываются автоматически; допустимая строка `-1` сохраняется. Duplicate в одном batch не публикует частично собранный pending-набор. Повтор pending ID не заменяет предмет. Снимок не зависит от последующей мутации генератора/выданного proposal. Два разных предмета могут завершаться в обратном порядке. Неизвестный ID и последовательный повтор не дописывают историю.

Ошибка формы `simulation_results` возникает до перехода и оставляет pending для допустимого исправления. Контрольное identity-несоответствие на fixture-hash boundary также не испортило state. Это не новая аттестация полных native candidate/source guards.

Malformed typed-результат сохраняет invalid и не становится best через adapter. Отдельная scalar-диагностика допустима при сохранённом invalid — это различие из CTL-03, не повторная находка. Native Vector/ObjectiveStack отсутствуют в среде опыта. Уже заданный feedback verdict не переписывается удобным boolean; входной evaluation-словарь не мутируется. [P12, P23]

P24 отдельно характеризует nullable convenience-поле `EvaluationBundle.policy_evaluation`: top-level None не вносится в stage_b_result, но явно заданный nested `policy_evaluation=None` сохраняется. Не установлен единый договор presence для этих двух форм, поэтому это **не объявлено новым B123-обходом**.

Funnel adapter передаёт материализованный предмет и сам proposal существующему orchestrator. При отсутствии результата может вызвать advance; уже имеющийся partial output возвращается с `completed=False`, не объявляясь полным. Здесь исполнялся adapter с записывающим funnel, не реальная многослойная воронка. Называть такой контроль доказательством FUN-01/02/03 нельзя. [P25, P26]

## 7. Что проверяют существующие тесты и чего ещё не хватает

`test_srv_01.py` содержит настоящий fresh-subprocess import trap для controller/funnel, ленивую загрузку autotune на первом обращении, identity alias, sequential ask/tell, Stage A rejection без Stage B, disabled Stage A, unknown/duplicate IDs и malformed typed feedback. Это содержательные проверки, не повод создавать дублирующий suite. [S07]

`test_contracts.py` сохраняет DTO/alias identity и исторические pickle lookup paths, тестирует adapter и funnel bridge. Его funnel-stage — MagicMock; численная корректность воронки этим тестом не устанавливается. Показанные pickle round-trips локально создают DTO и читают их в том же тестовом процессе; старый installed distribution и независимый процесс чтения здесь не выполнялись. [S08]

У этих положительных случаев `goal/search_space=None`. Sequential duplicate test не пересекает два tell между проверкой pending и mutation. В следующей native-приёмке нужен один детерминированный overlap-control на настоящем state/DTO и нормальные контроли для разных IDs; дополнительно проверить сериализацию и cold-import через действительную поставку, не только excerpt.

**Точные существующие команды для следующего штатного запуска (UNRUN):**

```bash
cd policy-engine
uv run pytest -q tests/unit/remediation/test_srv_01.py tests/unit/scientist/search/test_contracts.py
```

Полный SRV-03 требует другой, действительный autotune consumer trace. Его implementation-зависимости CTL-02/STP-01 не отменены последовательным read-only разбором.

## 8. Проверки, среда и итоговый остаток

29 ограниченных наблюдений; финальный вывод — 29 MATCH, 0 ERROR. В это число входят два воспроизведения одного дефекта, наблюдения interface-boundary, один direction-control, два removal/negative controls, cross-reference старой находки и проверки сохранения. Это **не 29 PASS продукта**. Начальных ошибок harness в данном проходе не было. [Протокол](../04_Проверки/C14_SRV01/bounded_diagnostics.json)

Полные adapters/service/run_state сверены с Git blob. Выбранные lifecycle bodies взяты из сохранённых материалов того же SHA после свежего чтения; полный lifecycle import не исполнялся. Реальны Python threads/events/locks/deepcopy, AST и Pydantic CandidateProposal; record/evaluation DTO, objective/source/materializer/registry/funnel — обозначенные fixtures. Native package cold-import, полные ObjectiveStack/DTO, provider/ledger/CAS/HTTP и pytest — **UNRUN**. Прямое получение raw source в контейнере завершилось DNS error; актуальный код прочитан GitHub connector. Web-view был старым и не использован как текущий source baseline. Dependency install не выполнялся.

13 прежних отчётов и evidence сохраняются побайтово без переаттестации. Прикладной вывод: сохранять разделение contracts/runtime и общего владельца; довести единичность и принадлежность ответа, затем определить поддержанный split-профиль. Не путать отсутствие реализации на новом адресе с уже исправленным историческим диагнозом, не расширять LA-014 до безусловного удаления controller.

## Источники

Индекс [C14_источники.json](../05_Источники/C14_источники.json) содержит закреплённые URL, Git blob SHA, диапазоны и границы исполнения. S01 contracts; S02 adapters; S03 service; S04 lifecycle; S05 run_state; S06 root facade; S07 test_srv_01; S08 test_contracts; S09 README; S10 AGENTS; S11 CONTRIBUTING. Все относятся к одному закреплённому commit, не к произвольному текущему main.

[Остатки C14](../01_Реестры/C14_остатки.json) · [Матрица критериев](../04_Проверки/C14_SRV01/verification_matrix.json) · [Границы](../04_Проверки/C14_SRV01/Чтение_и_границы.md).

### Закреплённые ссылки

- **S01** — [policy-engine/src/polisyos/scientist/methods/search/contracts.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/contracts.py), blob `93768dd16c915f96488bfde09cae606be3e0b658`. Fresh sections read; only lazy export tail and CandidateProposal class excerpt executed; native full module import UNRUN.
- **S02** — [policy-engine/src/polisyos/scientist/methods/search/adapters.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/adapters.py), blob `781e14fd5e50bc4cd2d000eb99fadeb876ef1dfd`. Complete source recreated exactly and Git blob matched, executed with declared external dependencies.
- **S03** — [policy-engine/src/polisyos/scientist/methods/search/service.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py), blob `bcc87e32cc1903888845a557a729f6dcf6b182b2`. Fresh boundary read; preserved complete C12 file Git blob matched, entire module executed with fixtures.
- **S04** — [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py), blob `754e942a21b3198c3989ac9175c54342b6c67ab3`. Fresh accept_tell/prepare/snapshot source; same-SHA prior excerpt bodies executed; no full native owner imports.
- **S05** — [policy-engine/src/polisyos/scientist/methods/search/run_state.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/run_state.py), blob `b4f980de235263513c7ad7e5771e1ccfbb3d8b3d`. Fresh blob identity; preserved complete source hash matched and entire state body executed.
- **S06** — [policy-engine/src/polisyos/scientist/methods/search/__init__.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/__init__.py), blob `dfd0f9057db3666bce512d654a69fc9057cbad5d`. Read only: eager dependencies and lazy supported surface. Native cold import UNRUN.
- **S07** — [policy-engine/tests/unit/remediation/test_srv_01.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_srv_01.py), blob `5a52ea0584e7844d1dea31afacc9cfebaf3db4ce`. Full read, no execution of project pytest or child cold import.
- **S08** — [policy-engine/tests/unit/scientist/search/test_contracts.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/test_contracts.py), blob `b2e5b84d0179af0221c71752536446fcc69b9501`. Read adapter/identity/pickle tests; real funnel method not executed; test stage mocked.
- **S09** — [policy-engine/src/polisyos/scientist/methods/search/README.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/README.md), blob `не зафиксирован в сохранённом ответе`. Context read, only relevant received sections used; documentation claims not substitutes for execution.
- **S10** — [AGENTS.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/AGENTS.md), blob `5f144a27e35130b60e2c3537d97f0c7bbcda57f5`. Repository rules read; read-only audit not implementation.
- **S11** — [policy-engine/CONTRIBUTING.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/CONTRIBUTING.md), blob `8ff414198e306e671abff1f76f31330a1f29d765`. Python 3.14 supported baseline; cloud diagnostic Python 3.13.5.
