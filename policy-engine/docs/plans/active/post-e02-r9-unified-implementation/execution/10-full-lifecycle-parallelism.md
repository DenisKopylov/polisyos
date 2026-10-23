# R19: параллельное исполнение без новых глобальных барьеров

Реализация начинается после фактической приёмки E02. До неё разрешены документация, исследование и source-bound подготовка. R19 не меняет исходный task DAG и не добавляет общий prerequisite «все84 вопроса закрыты».

## 1. Три стадии зависимости

1. **Подготовка:** source/owner census, исследование метода, proof sketch, ограниченные fixtures и contract draft. Независимые части можно готовить параллельно после E02 acceptance; ожидание внешнего акта не блокирует работу над механизмом.
2. **Выбранный interface:** writer и consumers фиксируют точные refs/schema/rule/profile и migration. Это локальный handshake для взаимодействующих задач, не общий freeze всех owners.
3. **Composition proof:** интегрированная проверка потребляет exact accepted producer output и реальные selected consumers. Только здесь соответствующий producer result — обязательная зависимость; declaration/placeholder не заменяет его.

Исходные `depends_on`/dependency_stage остаются. `composition_edges` карточек означают уточнение соответствующего handshake/proof, а не автоматическое добавление новых execution edges. Если actual source выявляет новый prerequisite, исполнитель обосновывает его property и стадию; document proximity не является зависимостью.

## 2. Разделение работы

| Параллельный поток | Native anchor | Что можно делать независимо | Где нужен supplier |
|---|---|---|---|
| Mandate/subject/values | CNT-01/05/07, DES-01 | Qualified refs, candidate branches, value comparisons | Protected selection/adoption с actual authority |
| Discovery/data semantics | CAP-01/02/03, CNT-06/08 | Coverage, crosswalk, missingness, provenance tests | Actual source/use/profile для composed claim |
| Law | CAP-05/CNT-04/DES-05 | Source selection, temporal/applicability method | Exact legal inputs/competent acts для конкретного use |
| Causal/model science | Native methods, CNT-06, GYD-30 | Identifiability, fidelity, exposure, uncertainty variants | Selected graph/data/unit contracts и consumer proof |
| Search/studies/learning | DES-03/04/08/12, GYD-09/10/12 | Bounded exploration, designs, transfer/restart validation | Real response/data/rights before empirical/admitted claims |
| LLM/human/documents | DES-06/07/09/10, UI | Profile eval, meaning oracle, renderer companions | Exact qualified basis/edition для public rendering |
| Rights/security/extensions | LIF-05, OPS-01/05, GYD-32 | Sink/adapter/qualification contracts and adversarial cases | Selected store/tenant/key/source policy для full route |
| Runtime/deployment | LIF-04/06, OPS-03/04/08/09/10/11/12 | Fairness, fencing, selected profile deployment | Actual process/store/remote closure для guarantees |
| Lifetimes/composition | LIF-02/07, GYD-30, DES-11 | Enrollment and scoped dependency fixtures | Actual producer events, public consumers и custody inputs |

Это логические потоки, не девять новых sovereign owners и не фиксированная квота агентов. При запуске число исполнителей выбирается по готовым независимым slices. Разрешённая глубина delegation определяется тогдашней инструкцией, а не этой таблицей. В текущей исследовательской работе использован только один уровень прямых помощников.

## 3. Writer lease и совместные изменения

Параллельны разные native owners/paths. Один exact shared DTO, registry, generated family, governed document или certificate имеет одного writer на выбранный период; остальные дают reviewed delta/companion proposals. Shared ownership не разрешается cherry-pick гонкой. Generated/OpenAPI/clients/browser companions поставляются вместе с реальным source contract, не после «почти готового» acceptance.

LIF-02 и GYD-30 будут получать много запросов из карточек. Их изменения следует объединять по одному механизму, а не сериализовать по84 questions. Shared schema согласуется один раз, consumers работают параллельно; integrator принимает coherent batch. Reviewer не автор reviewed code.

## 4. Внешние входы без искусственного stop

Каждый unavailable input записывается как exact owner/source/scope/time/needed predicate и минимальная форма. Прежде чем объявить stop, исполнитель проверяет: существует ли уже accepted supplier; можно ли recompute property из разрешённых inputs; остаётся ли полезный conditional result; нужен ли только инженерный adapter; требуется ли настоящий внешний акт/эмпирический результат. Он не назначает закон, политические веса, issuer/currentness или эмпирическую truth самостоятельно.

Неразрешённый SDD proposal о transfer authority блокирует только такое protected применение. Он не блокирует adapter-local refs, immutable provenance links, fresh claim evaluation и независимый candidate research. Неизвестная actual public capacity не мешает строить parameterized feasibility method, но не даёт actual feasibility PASS.

## 5. Итоговая интеграция

В каждой поставке: exact source/tree/input/profile, полный footprint/companions, native owner, выбранная альтернатива и причины deviation, full deciding outputs, независимый review и явные limitations. Code acceptance, actual capability и finding closure раздельны.

Обоснованно отклоняться от предложенного решения можно после source rebind или нового исследования. Записать counterexample прежнего решения, альтернативу, migration/free-grow effects и affected consumers; проверить обязательства вопроса. Нельзя отклонением скрыть вопрос или породить второго owner. Полный programme остаётся обязательным перед limited real use; scoped candidate progress не означает урезание launch scope.
