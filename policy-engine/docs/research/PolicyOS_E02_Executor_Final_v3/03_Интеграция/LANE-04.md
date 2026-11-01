# LANE-04: общий интеграционный контракт

**Цель:** Скомпилированная программа исполняет именно заданную семантику; профили экономики/обучения не смешиваются и не имитируют обученную модель.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: FRY-01, FRY-03, ECO-01, PLG-01, PLG-02, PLG-03, CMP-01, CMP-02, CMP-03, JIT-01, RES-04, CAL-05

- Compile contract передаётся LANE-01; RES-04 проверяется совместно с persistence LANE-06.
- CAL-05 входит в CAL/uncertainty LANE-10; не требуется весь trainer перед обычным compile/run.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-JAX:** P-CORE + locked base JAX/jaxlib/optax; deterministic CPU tiny mechanism unless selected accelerator explicitly required; no invented XLA flags (основание: policy-engine/pyproject.toml; AGENTS.md)

- Малые реальные зарегистрированные методы/короткий rollout; controlled events вокруг cache publication.
- Registry/composer/executor/JAX update принимаемого пути не заменяются success-shaped stub; внешний episode input можно фиксировать.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I04-A — Compile/freeze → sequential/async execution

Покрываемая область: FRY-01, CMP-01, CMP-02, CMP-03

**Положительный oracle:** Нестандартные static/dynamic параметры, requires-only edge, повтор метода и sibling дают те же значения, bindings и provenance; explicit merge остаётся UUID-invariant.

**Различающий негативный oracle:** Cycle/неразрешённый duplicate producer отклоняется до execution; ambiguous link не объявляется однозначным. Диагностика указывает нынешний source, exact-name preference не теряется.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I04-B — Warm compilation и checkpoint не меняют запрос

Покрываемая область: JIT-01, RES-04

**Положительный oracle:** Cold/warm dynamic defaults совпадают с текущим запросом; управляемая гонка даёт одну сборку/публикацию. Fresh checkpoint reader сохраняет per-node outputs/seed/restricted invocation.

**Различающий негативный oracle:** Failure между sidecar/rename/cleanup не удаляет принятую историю; changed params/input не использует старый checkpoint, namespace collision не подменяет историю.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I04-C — Economics profiles и реальный tiny trainer

Покрываемая область: FRY-03, ECO-01, PLG-01, PLG-02, PLG-03

**Положительный oracle:** Сохранены tax base/debit/units/clock/RNG профили; supported one-domain train делает 1–2 настоящих updates и fresh artifact меняет policy относительно independent no-update oracle. Ordinary run продолжает работать. Независимый analytic PPO/GAE oracle проверяет знак/clipped branches для обоих advantage signs, value/entropy coefficients и fixed-target gradients до сохранённого native Optax update. Обещанный inactive-padding scope квалифицируется actual same-shape/same-key paired training, меняющим только допустимый inactive payload finite→NaN, без изменения stored state.

**Различающий негативный oracle:** Unsupported train отказывает до actor/store без выдуманного loss; malformed discovery factory не оставляет half-registration; Неподдержанный HARD training отказывает до rollout/work/output, сохраняя HARD evaluation и положительный fluid/relaxed training. Если отдельно выбран полноценный HARD training, shared action/likelihood contract должен хранить фактически выполненное действие и соответствующую behavior probability, не только sampled action. Это не тест универсального обучения. Nonzero gradient/action delta недостаточны: sign-flip/unclipped-target mutant не проходит analytic oracle. Inactive-padding concern — native qualification, не установленный runtime bug; active NaN/intermediate terminal violations остаются отказом, no monotonic welfare/convergence promise.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I04-D — Calibration conditional execution

Покрываемая область: CAL-05

**Положительный oracle:** Inactive eager branch не считает механизм; tracer-safe active ветвь и scalar batch сохраняют результат и число фактических forward.

**Различающий негативный oracle:** Mapped predicate неподдержанного профиля получает точный refusal, не тайное evaluation всех ветвей и не общий запрет differentiable расчёта.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/remediation/test_cmp_01.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cmp_01.py) — SHA256 `8ea2dd89bf8fe8a59544e2707e6a14b9b01659a6eecf543f2911963a91f788b7`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_cmp_02.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_cmp_02.py) — SHA256 `b1e68f206f13bc025523eddd84f4627da2a0de38b367239e8ac435c3003bac1e`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_jit_01.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_jit_01.py) — SHA256 `ee7158540e9fb686b295e71d7981f1476f3d1b66e868b0963fb4135c0f3d0a69`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_res_04.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_res_04.py) — SHA256 `ea387149b3b353032a6630caac036356f0ac1804cb9c9dbe1ad60b7e3238bd9c`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/remediation/test_plg_03.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_plg_03.py) — SHA256 `8cb458316a40efad54c1890ad229ea1ff8b959c620b816012ef0dbcc701c97a5`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/calibration/test_pure_executor_semantics.py) — SHA256 `39220fe5e8e1a1ed823a87d54f0b04b9ec96b12956c1976afc8e2b3ff3b263fe`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
