# Исследование, редтим и пределы решения

Архитектурный результат — [01](01-fabric-runtime-annotations.md), задания — [02](02-implementation-and-verification.md). Этот файл объясняет выбор и след review; не является runtime receipt.

## Что действительно проверено G

Пакет прочитан из immutable Git commit `8533003b91961cf9ba1305ec296dab7f3ed40e4b`. G пересчитал полный source-набор трёх разделов `source_hashes` (`affected_modules`, `ruff_config_12`, `support_sources`): **25 уникальных путей**, SHA256 всех совпали с blobs source `49dff9183c20be3877d47953e0142417cb854cd0`. Девять дополнительных точных source inputs связывают actual facade/README/runtime requirements; они отдельно перечислены в [inputs.json](inputs.json), без копирования исходников.

Полный сохранённый Ruff JSON прочитан и его hash проверен. В нём **182 diagnostics: 14 Fabric + 168 IR**, Fabric — TC001 11 + TC003 3. Все `.py` аргументы нормализованы относительно записанного cwd и сравнены с **полным tracked Python set этих двух packages на frame**: 502 = 306 Fabric + 196 IR, symmetric difference 0. Это проверка сохранённого результата и знаменателя, не новый запуск Ruff и не claim обо всём repository.

Прочитаны и проверены hashes шести exact-14 reflection artifacts: invocation, stdout, stderr, receipt, sandbox profile и per-binding result. Они сообщают 14 positives и 14 exact-removal NameError controls на Python 3.14.3. G **не повторял** исполнение. Invocation заменяет модули source copies через `spec_from_file_location`/`sys.modules`, использует существующие зависимости и проверяет непустые hints. Он не доказывает ordinary facade import, полные expected types или весь замороженный dependency closure. Source-rebind 25 входов не равен глобальному source/input/backend freeze.

Полный annotation-use обход пяти modules включал callable parameters/return и class `AnnAssign`, с последующей сверкой экспортов. Так найдены дополнительный constructor, query siblings, `WorldQueryRequest` и несогласованность mode-route. Raw files/production data/source snapshots в Git не копировались.

## Первичные технические основания

| Источник | Что использовано | Чего из этого не следует |
| --- | --- | --- |
| [Python 3.14 typing](https://docs.python.org/3.14/library/typing.html#typing.get_type_hints) | Runtime type evaluation и static typing различаются; обычные namespaces и `include_extras` имеют определённую семантику | Само слово public не обещает reflection всех members |
| [PEP 649](https://peps.python.org/pep-0649/) и [PEP 749](https://peps.python.org/pep-0749/#the-future-of-from-__future__-import-annotations) | Deferred evaluation, cache и продолжающий работать future-import требуют version-qualified probes | Отложенное вычисление не восстанавливает отсутствующий type binding; не требуется менять annotation representation в этом slice |
| [annotationlib](https://docs.python.org/3.14/library/annotationlib.html) | Разные режимы inspection полезны для разных consumers | Полученная строка/ForwardRef не заменяет обещанное resolved type |
| [Ruff TC001](https://docs.astral.sh/ruff/rules/typing-only-first-party-import/) / [TC003](https://docs.astral.sh/ruff/rules/typing-only-standard-library-import/) | Правила сокращают стоимость imports, но перенос меняет runtime behavior; fixes обозначены unsafe | Линтер не выбирает public compatibility contract вместо owner |
| [Ruff suppression semantics](https://docs.astral.sh/ruff/linter/#error-suppression) и [RUF100](https://docs.astral.sh/ruff/rules/unused-noqa/) | Нужна точность фактического suppression scope и согласованность active profile | Групповой import не означает автоматически точное alias-level исключение |

Online docs — основания семантики, не команда обновлять toolchain. Pinned project использует Python 3.14; решения не зависят от будущего Python 3.15 lazy-import syntax или новых форм Ruff suppression. Нет доказанной необходимости внедрять Pydantic/FastAPI-style namespace machinery: существующий Python resolver и imports уже выполняют требуемую работу. Современный качественный выбор здесь — сохранить небольшой корректный механизм и сделать его границу проверяемой.

## Раунды критики и исправления

Четыре прямых независимых направления: public-surface/source closure; Python annotations; Ruff/config ownership; исходный adversarial review. Затем отдельный reviewer атакует готовый draft, исследователь Python повторно проверяет семантику, а G делает собственное source-bound review. Никто не создавал детей, окружений, checkout или product processes.

| Атака | Что изменено в решении | Остаточная граница |
| --- | --- | --- |
| «11 imports = 11 signatures» | Исправлен знаменатель; diagnostic ledger отделён от callable/field closure | Новые uses на actual candidate пересчитываются, не блокируются сегодняшним числом |
| «Parent public package делает `.modes` public» | 10 proven facade bindings + отдельная bounded mode compatibility; сохранить четыре функции, уточнить README, не добавлять exports | Не принят новый public-stable contract для всех descendants |
| «Проверим только callable из diagnostic row» | Включены оба cache constructors, query siblings и поля `WorldQueryRequest` | Не требуется бесконечный обход внутренних типов/генерируемых методов |
| «Непустые hints + NameError доказывают типы» | Полные annotation keys, независимые expected types, nominal/union/generic checks; неправильный одноимённый тип и Any substitution — negatives | Не обещается полная semantics произвольного plugin schema generator |
| «Deep copy даёт facade receipt» | Fresh supported route и alias identity — отдельные обязательные checks | Исторический source-copy positive остаётся только тем, что он реально проверил |
| «Удалим global после чтения annotations» | Fresh annotation state и mutation до introspection, без CPython cache hacking | После эквивалентного refactor negative следует новому механизму |
| «Добавим локальные noqa поверх общего ignore» | Одновременно убрать только TC001/TC003 из production glob и обновить generated companions | Не отменяются unrelated policy или test-scoped ignores |
| «Новый alias спрячется на разрешённой import line» | Explicit actual-layout negative плюс production-path fresh-line sentinel | Не вводится новая waiver platform или brittle keyword scanner |
| «Нет production/freeze — работа стоит» | Точные engineering inputs и affected wave; нет внешнего law/production prerequisite | G acceptance и formal closure остаются отдельными |
| «Любой resolved hint обязан быть class» | Учтён generic `SourceConnectorValue` alias; canonical alias/origin/arguments сохраняются без forced expansion | Не требуется новый type normalizer |
| «Dataclass fields равны всем class annotations» | Разделены class-annotation и dataclass-field множества, включая будущие ClassVar/InitVar | Никакого нового требования проверять произвольные class internals |
| «Alias identity подразумевается, тест сам догадается» | Добавлен точный `is`-oracle для root/data_plane query function | Identity внутри одного процесса, не адреса между subprocesses |

Это несколько проявлений класса P35/P36/P38, а не несколько новых архитектурных систем. По P40 исправлен способ определения scope: bindings → все relevant uses → actual routes → consumer property. Не вводится очередная ручная таблица API, независимая от существующих владельцев.

## Самостоятельное review G и условия передачи

G дополнительно прочитал actual signatures, runtime/TYPE_CHECKING blocks, `WorldQueryRequest` fields, фасады и Data Plane README. Подтверждён version-bound source, а не актуальность moving branch исполнителя. Проверены отсутствие namespace-repair требования, разграничение internal/private conversion и публичной reflection, сохранение mode behavior без молчаливой promotion/demotion, полноценный facade/semantic oracle и конфигурационные companions. Финальный независимый review дал bounded GO с уточнением alias-identity oracle; Python review добавил type-alias/dataclass различия и явную привязку примеров к source вопроса. Все три уточнения внесены. Ложное замечание про «11 supported» было отозвано reviewer: оно цитировало immutable исходный вопрос, а не новый draft.

Существующий `scientist/agent/tools/knowledge_tools_adapter.py` вызывает `get_type_hints` и при ошибке может переходить к raw annotations. Конкретный вызов этих Fabric APIs из него **не установлен**. Поэтому решение не заявляет уже реализованную автоматическую генерацию tools, исправление agent bridge или расширение learning capability. Это сохранение нужного interface primitive, совместимое с будущими расширениями, без выдуманной интеграции.

**Pattern pass:** P01/P02 — contract не подменяет исполнение; P03 — actual Python facade; P05/P15 — annotation/LLM output не authority; P07/P08 — source/runtime versions, без выдуманного global freeze; P14 — evidence прочитано, но не перепроиграно G; P27/P31 — один type/config owner; P29/P32/P33 — behavioral resolution + independent types + removal; P35/P36/P38 — полный declared denominator и подтверждённый route; P39 — обязательные companions вне произвольных path caps; P40 — закрыт класс set-construction; P41 — нет утверждения inherited red без replay.

Приёмочный сигнал остаётся будущим: reviewed exact candidate → обычный facade import → resolved real types → потребление полной сигнатуры → mutation различается → config visibility/companions согласованы. Сейчас `verification_missing`/`semantic_test_missing` обозначают недостающие новые acceptance receipts, а не отсутствие всех существующих функций. Product implementation, tests, lint, builds и global replay в этой работе не запускались.
