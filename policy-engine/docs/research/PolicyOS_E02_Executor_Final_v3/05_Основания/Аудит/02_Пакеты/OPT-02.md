# OPT-02 — настоящий SearchSpace и координаты фактического исполнения
## C19 · продолжение v016 · 31 октября 2026 года

**Исходные IDs:** B112, B113, B127. **Порядок:** 19/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Исходный код, проектные тесты, настройки и зависимости не изменены. Далее — OPT-03.

## Решение

**Частичная оценка, без полного закрытия.** Настоящий SearchSpace уже подключён; история не превращается целиком в центр пространства, метрики отделены от параметров, полные artifact IDs и причины недопуска оценки сохраняются. Проверка эквивалентного дискретного действия также существует. Эти изменения полезны и не требуют нового оптимизатора.

Однако **C19-R01**: локальная защита от повторного действия не применяется ко всем ветвям — cold-start игнорирует переданный pending, несколько batch-ветвей не накапливают pending, а исчерпанное конечное пространство возвращает ещё один дубликат. **C19-R02**: внешний fallback по-прежнему возвращает current_best/history/context без типизированной причины и обозначения повторного представления. Это не доказательство успешного Bayesian-поиска.

Выполнены **19 ограниченных механических наблюдений и одна проверка наличия зависимости**; все ожидаемые наблюдения совпали. MATCH включает воспроизведение дефекта, не означает PASS продукта. Исполнялись точные AST-тела исходных определений с раскрытыми заменами инфраструктуры и corpus-header; не импортировался полный PolicyOS. Настоящие GP, CAS, HTTP, LLM, существующие pytest и поддержанный Python 3.14 — **UNRUN/BLOCKED**. Текущая среда Python 3.12.14 отличается от среды исторического C18; старый результат не переаттестован.

## 1. Требование и содержательная способность

[Полная исходная карточка](../05_Источники/OPT-02_исходные_строки.txt) требует связать предложенные параметры, реально выполненное действие и наблюдённый loss. Две непрерывные точки, округлённые до одного действия, не становятся двумя разными политиками. Отдельная стохастическая реплика остаётся самостоятельным наблюдением при явной идентичности.

LLM может предложить параметры, семейство модели, пространство и следующий эксперимент. Данный пакет не требует второго универсального алгоритма, изобретающего такие постановки. Техническая обязанность существующих владельцев — исполнить выбранную постановку, сохранить её идентичность, не выдумать результат и не назвать повтор старого результата новым поиском. Корректная синтетическая механика не даёт эмпирического обоснования политики.

| ID | Что уже сделано — сохранить | Конкретный остаток |
|---|---|---|
| B112 | Autotune SearchSpace делегирует canonical space; optimizer получает `search_space._native`; доступны normalize, denormalize, Sobol и BoTorch bounds | R02: явная причина и статус внешнего fallback. Настоящий native GP запуск не выполнен; наличие optimizer object не равно доступности backend |
| B113 | Проверка обязательных имён в history; нормализация фактических params; полные IDs; конфликт identity исключается; недоказанный score не становится успешным нулём; выбранный источник перечитывается через CAS | Квалификация полного native producer→history→training пути; параметры standalone benchmark-конвертера и самостоятельность реплик требуют отдельных контролей |
| B127 | Integer/category aliases сравниваются по effective execution; continuous значения не округляются; явные seed/replicate сохраняют различие | R01: распространить защиту на cold, batch и exhaustion. Согласовать relaxed proposal и canonical execution в прямом низкоуровневом Evaluation-пути |

## 2. B112: исходный разрыв интерфейса действительно изменён

В [adapter, S01:146–217](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py#L146-L217) нет второй реализации нормализации: создаётся настоящий `strategies.space.SearchSpace`, ему делегируются операции. Конструктор генератора передаёт optimizer именно `_native`, а не урезанную обёртку. [S01:266–282]

Исполненные P01–P04 проверили категориальное раскрытие, integer, лог-шкалу и различимость физических параметров. Для `{x:5,n:0,c:B,scale:10}` при x∈[0,10], scale∈[1,100] получен `(0.5,0,0,1,0.5)`. Настоящее тело `_sobol_candidate` прошло через полный native-space класс; в этом профиле сработал **SciPy Sobol**, не Torch. Это реальная узкая механика sampling/denormalization, но не полный вызов `BayesianCandidateGenerator.generate` и не обучение GP.

Найденный `test_first_sobol_candidate_uses_native_search_space_protocol` связывает именно autotune wrapper с первым suggest на смешанном пространстве. Он прочитан, но не выполнен. `to_botorch_bounds` делегирован правильно по исходному коду; Torch отсутствует, поэтому этот путь не приписан исполненному результату. [S04:87–131]

## 3. B113: действительный producer→consumer путь и его границы

`SearchLoopRunner.run` устанавливает source store, неизменный run context и MethodJob profile, затем создаёт существующие lifecycle owner и native service driver. `_evaluate_candidate` декодирует payload через codec, сохраняет candidate, вызывает evaluator, сохраняет evaluation и возвращает в историю полные evaluation/candidate refs, split и provenance. Генератор proposal metadata отделён от mutation payload. [S06:1840–2040,2290–2369]

`_history_to_evaluations` сначала требует все bound names, затем вызывает настоящий normalize. `_history_identity` согласует candidate, entry и StageB claims вместо молчаливого выбора одной версии. Scalar выводится из assessment источника; отсутствующий либо неподтверждённый score остаётся diagnostic/unavailable, а не `SUCCESS,0`. [S01:947–1276]

Это не один DTO: `_resolve_search_history_source` открывает selected evaluation и её manifest, проверяет candidate/suite edges и сверяет реальные параметры. MethodJob claims идут через отдельный verifier и не могут притвориться обычным generic benchmark только из-за отсутствующей удобной metadata. Generic источник сохраняет более слабую квалификацию `candidate_only`. [S10:154–350]

`benchmark_to_evaluation` сохраняет полный candidate artifact ID, использует metadata params, проверяет runtime split, единицу и finite metric; MethodJob claim без source-store verifier отклоняется. В `Evaluation.is_valid` наличие SUCCESS недостаточно: нужен пересчитываемый score basis. [S01:1279–1412; S03:112–162]

**Что не установлено исполнением:** native score admission, реальный selected CAS readback, изоляция закрытого holdout, фактический GP tensor и независимость измерений. Наличие этих ветвей и найденных tests не превращено в PASS. Важный найденный native test `test_native_methodjob_unitless_ate_explores_without_gp_admission` предусматривает четыре реально разные координаты, actual MethodJob work и fresh reader, но намеренно оставляет unitless ATE вне GP corpus. Это полезное исследование, а не ложный нулевой успех. Сам test имеет opt-in gate и здесь не запускался. [S11:1006–1245]

## 4. C19-R01 — защита от повторного дискретного действия не охватывает все предложения

**Тип:** подтверждённый локальный дефект; **важность:** средняя, зависит от использования batch/pending и конечного пространства; **уверенность:** высокая для показанных ветвей.

В [S05:1613–1647](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L1613-L1647) `_is_duplicate` уже сравнивает результат denormalize, а не расстояние между relaxed vectors. P05–P08 подтвердили integer/category equivalence, различие seeds и сохранение близких continuous значений. Найденные штатные tests проверяют эти свойства; их следует сохранить. [S07:385–452]

Но caller coverage неполон:

| Различающий вход | Наблюдение | Основание |
|---|---|---|
| Cold-start; pending уже содержит именно первый Sobol action | Возвращается тот же effective action, без replica metadata | P10; `suggest`: ранний return до duplicate guard, S05:896–918 |
| Бинарное пространство; no-backend batch размера 3 | Повторяющиеся 0/1, у всех пустая replica metadata; каждый вызов получает новый пустой pending | P11; S05:962–997 |
| Pending содержит оба действия бинарного пространства | После 20 попыток возвращается заведомо уже pending действие, без exhaustion-состояния | P12; S05:1601–1611 |

P10 исполнял настоящий Sobol sampling и точное тело suggest, но допуск training corpus был явной пустой фикстурой. P11 использовал явный непустой corpus-header и backend-disabled branch; оценка качества corpus не проверялась. P12 не требовал GP. Поэтому здесь доказана ошибка выбора/дедупликации в названных ветвях, а не production-частота, расход денег или вред опубликованной политике.

`_NativeSearchServiceDriver` защищает pending/completed **candidate IDs**, но создаёт новые IDs для обычных словарных payload. Это другое свойство: оно не устанавливает уникальность effective parameter set. У `BayesianCandidateGenerator` в рассмотренном пути вообще нет generate_batch; потому нельзя переносить наблюдение native optimizer batch на каждый autotune запуск. [S08:40–126; S09:900–944]

**Минимальное направление:** использовать существующий effective-action guard на фактических ветвях предложения и накапливать pending внутри batch; явно возвращать exhaustion либо заявленную независимую реплику вместо случайного дубликата. Не запрещать повторные стохастические измерения и не округлять continuous без принятого допуска. Не нужен второй optimizer/registry. Для приёмки добавить случаи cold pending, полный конечный набор и batch, а не только ещё один прямой тест `_is_duplicate`.

## 5. C19-R02 — внешний fallback теряет происхождение результата

**Тип:** подтверждённое локальное несоответствие исходному B112; **важность:** средняя, условная; **уверенность:** высокая для returned payload, не для внешнего UI.

`generate` при недоступности wrapper optimizer либо исключении suggest вызывает `_fallback_generate`. Тот возвращает shallow copy current_best, последнего dict history либо самого context. В payload нет нового поля, различающего прежний результат, недоступную зависимость и wiring error. [S01:318–385,858–869]

P14 получил ровно `{"x":7}`; P15 получил `{"task":"question"}` как кандидатоподобный словарь. Штатные tests прямо закрепляют эти возвращаемые значения, но не проверяют требуемую причину и reuse-семантику. [S04:51–84]

Нижележащий optimizer уже умеет возвращать `source_strategy="random_no_botorch"`, `random_fallback` и иные действительные стратегии. Этот полезный источник не надо заменять общим «нет Bayesian — ничего нельзя». Замечание относится именно к внешнему catch/absent-optimizer fallback. Поле `botorch_available` генератора означает успешное создание wrapper optimizer и не тождественно `native_gp_ready`.

**Минимальное направление:** сохранить возможность показать старый best, но провести явные причина/режим reuse через существующий контракт генерации; контекст не принимать за новое действие без candidate contract. Не требовать нового научного результата от fallback. Внешний service/UI и фактическая повторная оценка такого payload здесь не исполнялись.

## 6. Дополнительные границы, не смешиваемые с дефектами выше

**C19-G01 — canonical training coordinate зависит от входного пути.** Base random/Sobol и `_tensor_to_candidate` сохраняют relaxed vector; это нормально как proposal diagnostic, если loss затем привязывается к effective params. Autotune history выполняет normalize(params), что защищает рассмотренный путь. Однако `_has_compatible_params` проверяет размерность, finite и [0,1], не равенство `normalize(evaluation.params)`. P09 увидел relaxed vector, отличный от effective canonical; P13 принял `params={n:0}, vector=(0.9,)`, хотя эта координата denormalize даёт n=1. Прямой caller обязан иметь различающий контроль producer→Evaluation→training; прохождение такой строки через настоящий score/source verifier здесь не установлено. [S02; S05:1242–1250,1350–1373,1649–1679]

**C19-G02 — standalone benchmark converter слабее history на обязательных параметрах.** История проверяет required names, но benchmark converter при `search_space` сразу вызывает normalize. P18 установил, что canonical normalize({}) для continuous x∈[0,1] возвращает 0, а не отказ. Конвертер и его настоящий score/source admission здесь не исполнялись целиком, поэтому это конкретный адрес для регрессии, а не объявленный доказанным проход к GP. Аналогично проверить out-of-range и typed integer, не заменяя нормализацию новым framework. [S01:1299–1329; S02:65–91]

**C19-G03 — отдельный evaluation ID не равен replica identity.** P19 показал: `_evaluation_identity` использует provenance либо candidate ID плюс replicate/replica/seed; два различных metadata evaluation_id сами по себе не разделяют наблюдения. В настоящем runtime provenance обычно отдельный MethodJob result/evaluation ref. Нужно проверить именно желаемую модель повторов и реальную выдачу этих refs; не объявлять каждый повтор одного action дубликатом и не считать два списка независимыми данными. [S05:1328–1348; S06:2321–2358]

Неполный scalar, неправильный split и недостоверный source не обходить ради green GP. Недопуск к GP не означает запрет полезной candidate-grade exploration.

## 7. Исполнение, доказательства и следующий шаг

`probe_opt02.py` читает pinned checkout и перед исполнением сверяет Git blob каждого использованного файла. AST сохраняет тела выбранных определений; project imports исключены, `Evaluation`, corpus selection/header и optional Torch boundary явно заменены. Настоящий `ParameterBounds`, `PolicyCandidate`, полный `SearchSpace`, base helpers и указанные методы Bayes выполнялись. Это **не native import**, не запуск существующих tests и не доказательство научной оптимальности.

Команда: `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 probe_opt02.py`. Exit 0, 20 MATCH, 0 ERROR; P20 — только availability probe. Проектный pytest не установлен; отдельно сохранён фактический неуспешный вызов `python3 -m pytest --version`. Зависимости не устанавливались. Репозиторий после проверки чист и остаётся на указанном SHA.

[Протокол](../04_Проверки/C19_OPT02/bounded_diagnostics.json) · [команды](../04_Проверки/C19_OPT02/commands.json) · [границы](../04_Проверки/C19_OPT02/Чтение_и_границы.md) · [источники](../05_Источники/C19_источники.json) · [остатки](../01_Реестры/C19_остатки.json).

**19/127 пакетов рассмотрены ограниченно; 49 уникальных B/LA частично оценены; полного закрытия нет.** Все 18 предыдущих отчётов и их evidence сохранены без переаттестации. Далее — **OPT-03 / B114, B115**.
