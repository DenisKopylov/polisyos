# LANE-05: общий интеграционный контракт

**Цель:** Получить правильный условный causal estimate/query на заявленном графе и модели; отдельно идентификация, uncertainty и право дальнейшего использования.

Состояние проверок: **NOT_RUN**. Это обязательные критерии будущей связанной приёмки, а не свидетельство текущего PASS. Семейство запускается один раз для согласованного изменения; локальные packet tests не дублируют его инфраструктуру.

## Область и зависимости

Пакеты: GRF-01, GRF-02, GRF-03, API-01, CAU-01, CAU-02, CAU-03, CAU-04, CAU-05, SCM-01, SCM-02, SCM-03, FIT-01

- Reuse persistence LANE-06, actual Scientist consumers и generation bindings.
- FIT-01 исторически CP4; остальные lane packets CP5. Не добавлять FIT как global CP5 барьер без affected route.

## Профиль и допустимые подмены

- **P-CORE:** policy-engine Python >=3.14,<3.15; actual project lock/extras, supported existing environment; imports bind tested checkout/artifact (основание: policy-engine/pyproject.toml:8)
- **P-ANALYTICS:** P-CORE + applicable analytics/causal-core extras and exact selected numeric backend; no fixture substitution for native numeric claim (основание: policy-engine/pyproject.toml [project.optional-dependencies])
- **P-DOWHY:** Parent Python>=3.14,<3.15 + isolated Linux worker workers/dowhy-014 Python>=3.12,<3.13, dowhy==0.14 with its own lock; actual worker OS/arch/interpreter/inventory. Parent conditional DoWhy extra is not this native profile; native_hybrid is not a substitute. Missing Linux worker is profile NOT_QUALIFIED, not a defect on every platform. (основание: policy-engine/workers/dowhy-014/pyproject.toml; worker uv.lock; C57-G01)
- **P-GRAPH:** P-CORE + locked NetworkX3.6.1 canonical graph backend; Kuzu0.11.3 only when selected with kuzu extra and scoped compatibility repair. Record actual OS/arch/interpreter/lock/extras/backend inventory. No native rustworkx claim without a separately declared authorized dependency; unavailable optional backend is profile NOT_QUALIFIED. (основание: policy-engine/pyproject.toml [project.optional-dependencies].kuzu; uv.lock; GRF-02 backend owner)

- Известный синтетический SCM/panel служит oracle, не доказательством эмпирического causal graph.
- Внешние запросы/clock контролируются; selected fit worker, registered dispatcher, whole report и CAS validators для native acceptance реальные.

Подмена запрещена для принимаемого свойства: если проверяется запись/чтение, actual store и fresh reader обязательны; если численный метод — actual backend; если physical cleanup — actual OS resource. Внешний provider/encoder может быть лёгким и контролируемым, когда качество модели/сети не входит в claim.

## Подготовка и порядок

1. На выбранном поддерживаемом профиле связать checkout/build SHA и входные fixtures. Использовать существующие test owners ниже, прочитать их реальные seams перед расширением
2. Выполнить локальные REQ/TEST затронутых пакетов, затем каждый применимый вариант этого семейства. Независимые варианты допускают раздельный запуск
3. Положительный прогон должен пройти actual producer→передача/хранение→fresh consumer. При отсутствии хранения в конкретном алгоритме проверить непосредственный downstream consumer, не придумывая CAS ради отчётности
4. Повторить адресный негативный/граничный контроль. Изменение одного deciding input или отключение исправленного механизма должно менять наблюдаемый исход; unrelated пригодный результат остаётся доступным
5. Сохранить входы, события/значения/ошибки, ref identities, численные tolerances и команды. Итог связывает покрытые REQ, а не только список пакетных имён

## E02-I05-A — Graph → native representations → rule consumer

Покрываемая область: GRF-01, GRF-02, GRF-03, API-01

**Положительный oracle:** 3–5 node DAG/ADMG: chain/fork/collider/descendant и perfect-do совпадают с независимым latent-DAG oracle; graph copy/version/export/cache согласованы; registry пользуется canonical owner. Native backend qualification указывает OS/arch/interpreter/lock/extras и фактический backend: NetworkX3.6.1 canonical; Kuzu0.11.3 только выбранный optional профиль с узким compatibility repair.

**Различающий негативный oracle:** Wrong endpoint/multikey identity и stale cache различаются; temporal/PAG вне declared static profile получает адресную несовместимость, не выдуманный DAG. Статический успех не доказывает все PAG. Нет native rustworkx claim без отдельно объявленной разрешённой зависимости; missing backend/platform остаётся NOT_QUALIFIED для соответствующего профиля, не defect всех платформ.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I05-B — Registered estimator → persisted whole report

Покрываемая область: CAU-01, CAU-02, CAU-03, CAU-04, CAU-05

**Положительный oracle:** Known ATT, declared cluster covariance, finite-B CI/p inversion, anticipation controls и bounded sharp RBC проверяются независимыми numerical oracles; dedicated DiD route передаёт whole report fresh consumer. Conventional RDD отдельно объявляет kernel-localization variance profile: known diagonal noise проверяется B XᵀWΣWX B, residual-HC0 — B Xᵀdiag(w²r²)X B, B=(XᵀWX)⁻¹; inverse-Gram legacy не oracle iid-kernel covariance. CAU-04 actual Linux/Python3.12 DoWhy0.14 worker сверяется и с независимым 8-row algebraic point/SE/t-CI oracle, и отдельно с Statsmodels adapter parity; DGP coverage — отдельное свидетельство.

**Различающий негативный oracle:** NaN cluster/unsupported t0, wrong estimand/diagnostic window, coherent report substitution не получают ложной роли. Point-only backend сохраняет число без придуманных CI/SUCCESS; legacy adapter не меняет method identity. Known-variance finite fixture не требует совпадения single-sample HC0 с истинной variance; HC0 не заявлен finite-unbiased. Historical covariance profile/bytes сохраняются под прежней меткой, новый estimator versioned. Общий underlying OLS не считается независимым numerical oracle.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## E02-I05-C — Selected fit → CAS → fresh SCM query/twin

Покрываемая область: SCM-01, SCM-02, SCM-03, FIT-01

**Положительный oracle:** Наблюдаемый root law, polynomial prediction, partial/full factual evidence и explicit target/comparator работают через actual selected producer/worker и reader. Hard-do не выполняет заменённый механизм; irrelevant missing root не блокирует outcome. Reuse fit сохраняет current diagnostics. SCM iid-observation-row refit qualification сопоставляет каждый фактический bootstrap row corpus с независимыми scalar OLS target/contrast и явной linear-quantile convention, затем actual persisted validator. Continuous TMLE standardized nuisance preprocessing/hyperselection принадлежит fit fold: изменение только Y[test_idx] при fixed X,T/splits/train Y не меняет nuisance predictions этого fold; train-Y positive control меняет actual fit.

**Различающий негативный oracle:** Source/row/mechanism tampering отвергается; tiny positive covariance не исчезает; malformed stochastic law не превращается в atomic success. Actual selected worker нельзя заменить native_hybrid и объявить эквивалентным. Offset/scale target, shuffled row-index pairing и wrong quantile mutants должны различаться. Итоговый ATE/EIF вправе измениться от heldout Y; нельзя требовать его invariance или выдавать width shrink за coverage theorem.

**Приёмка:** предъявить оба исхода на одной объявленной модели/профиле с изменением только deciding условия. Точные локальные counterexamples и expected values берутся из связанных TEST соответствующих пакетов; совпадение summary без фактического потребления не принимается. Если метод стохастический, заранее указать seed/replica/ошибку сравнения, не подбирать tolerance после результата.

## Существующие места расширения tests

Список означает проверенные пути, не доказательство полноты или запуска всего содержимого. Новые проверки добавлять к ближайшему владельцу; отдельный harness создавать только при реальном разрыве.

- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py) — SHA256 `4ea4c07555000dee55d3b1b4d7ed15b07862899b3776c8362485322a9e64a253`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_did_diagnostic_consumer.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_did_diagnostic_consumer.py) — SHA256 `a5011ff94c676ac0daf94dee1f6367f6d9e399b50cb4452f5389d202df0bfb56`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_rdd_rbc_independent_oracle.py) — SHA256 `4c8398b42efa15eeba4b28c9900a18541269931322edb8122412443d081f1585`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py) — SHA256 `716a15e0a93e0063a112effec1acb6f4578db2906da95f427011687bb170e761`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.
- [policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_fit_contract.py) — SHA256 `0dd02251c4d7476761e5475fb6eea67a4c412e87c315b2087682291c57f71bf1`. Existing owner is a reuse location, not proof that the full proposed scenario exists or passes.

## Выход приёмки

- Один manifest исполнения семейства: base/head SHA, scenario-ID, связанные REQ/TEST, профиль, входы и их hash, actual commands/exit, фактические positive/negative oracles, ограничения
- Перечень doubles с объяснением, какое свойство ими не проверяется
- Для failure/unknown: точная стадия и сохранённый полезный результат. Не перекрашивать BLOCKED/UNRUN в PASS
- Ремонт механизма и предметная валидность имеют разные решения. Синтетический механизм может пройти, не подтверждая прогноз/каузальную идентификацию/мандат реального кейса
