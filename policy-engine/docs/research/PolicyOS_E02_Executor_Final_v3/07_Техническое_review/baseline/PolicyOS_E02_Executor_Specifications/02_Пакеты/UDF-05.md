# UDF-05 — Целостный demographic bundle без смены роли и идентичности

**Лейн:** LANE-07 · **Окно:** CP2 · **Основания:** LA-032, LK12, LK20 · **Тип:** fix + native qualification; historical migration preserve.

**Практический результат.** Выбранные demographic inputs достигают реального aging/Foundry consumer с теми же totals, ordered states, donor IDs и честной candidate/source evidence; корректные old snapshots не теряются.

**Статус:** исполнительское ТЗ. Это не выполненный ремонт; все новые TEST ниже — **NOT_RUN**. Исходный аудит выполнен на `20d9009be21097bfbdc38a546a15cc60213b8ace`; его полнота не означает закрытия остатков.

## 1. Основание и границы
[Аудит UDF-05](../05_Основания/Аудит/02_Пакеты/UDF-05.md), [C88 residual](../05_Основания/Аудит/01_Реестры/C88_остатки.json), [исходная карточка LA-032, LK12/LK20](../05_Основания/Аудит/05_Источники/UDF-05_исходные_строки.txt). Исходный migration M уже дал whole-layout selection; возвращать прежнюю per-file fallback архитектуру запрещено. Full probes и исторические command logs находятся в отдельно доставленном phase1 ZIP; они не подменяют новую native приёмку.

R01 — доказанный aggregate role overwrite после разрешения coherent source, **не** доказанный обход native CAS. R02 — доказанное молчаливое усечение индексов. G01 — граница неисполненной native квалификации; существующую producer/read-api цепь не строить заново без воспроизведённого разрыва. G02 — граница source/scientific утверждения, а не поручение создать новую provenance-платформу.

## 2. Уже работает — сохранить
Whole-layout new/legacy selection, explicit old snapshots, optional donor, standalone historical scalar читатели, captured bytes и immutable projections. `load_verified_stage_artifacts`/`load_verified_stage_output_bytes` остаются единственными выбранными IO/CAS owners; `build_static_aging_state` остаётся чистой проекцией. Source evidence не становится D5/научным сертификатом. Candidate missing entrants не получает silent zeros; историческая zero projection имеет существующую явную qualification. Не менять dtype/shape/domain сверх исправления потери дискретной идентичности без отдельного обоснования.

## 3. Полная disposition остатков

- **C88-R01 — fix** → REQ-UDF-05-01, REQ-UDF-05-06. Устранить молчаливую смену owner computational поля внутри выбранного bundle, сохранить metadata и valid composition.
- **C88-R02 — fix** → REQ-UDF-05-02. Валидировать дискретную identity до преобразования; исправить оба index поля, не только state range.
- **C88-G01 — qualify** → REQ-UDF-05-03, REQ-UDF-05-04, REQ-UDF-05-06. Исполнить реальную native producer/read chain; product change только при установленном несоответствии, без новой CAS платформы.
- **C88-G02 — qualify** → REQ-UDF-05-05. Доказать truthful propagation и полезный candidate path; scientific suitability конкретного source остаётся отдельной явно ограниченной областью.

Исходные обязанности и сохранения lossless inventory связаны отдельно в companion JSON (`obligation_dispositions`, `preservation_bindings`); номера residual не заменяют исходные обязанности.

## 4. Нормативные требования

### REQ-UDF-05-01
При сборке одного resolved demographic snapshot ни priors, ни donor не должны изменять вычислительные поля targets. Повтор чужого поля с отличающимся значением должен завершиться явным конфликтом роли до возврата aggregate; равный повтор допустим только как проверенное совместимое дублирование. Scalar и aggregate читатели того же source должны возвращать одинаковые target totals и порядок state_ids.

Основание: LA-032; аудит: C88-R01. Проверка: TEST-UDF-05-01, TEST-UDF-05-05.

### REQ-UDF-05-02
До любого int64 cast каждый donor_state_index и присутствующий donor_record_index должен быть конечным точным целым, представимым в int64. Дробь любого знака, NaN/Inf и выход за int64 должны отклоняться без усечения или wraparound. После этого donor_state_index должен принадлежать [0,n_states); прежние допустимые signed record IDs не ограничивать новой положительностью.

Основание: LA-032; аудит: C88-R02. Проверка: TEST-UDF-05-02, TEST-UDF-05-05.

### REQ-UDF-05-03
Выбор historical new/legacy layout выполняется целиком до чтения членов; mixed/ambiguous/present-invalid не подменяется fallback. Явный old snapshot, scalar historical-only чтение и законное отсутствие donor сохраняются. Candidate aggregate требует materialized entrants и установленной disposition donor; unknown donor не блокирует только уже разрешённые scalar targets/priors.

Основание: LA-032, LK12, LK20. Проверка: TEST-UDF-05-03, TEST-UDF-05-05.

### REQ-UDF-05-04
Native candidate путь должен получить inventory через существующий builder из явно выбранного producer manifest, проверить exact member set/hash/size/profile, затем прочитать captured CAS receipt новым reader и передать те же значения и evidence в pure aging/Foundry. Изменение producer files после capture не меняет старый receipt; потеря или порча выбранного CAS blob даёт отказ, а не filesystem/default fallback.

Основание: LA-032, LK12, LK20; аудит: C88-G01. Проверка: TEST-UDF-05-04, TEST-UDF-05-05.

### REQ-UDF-05-05
Читатели и pure aging должны сохранять provenance source facts и различать consumer_asserted, not_established и проверенные content/basis facts. Отсутствие scientific/currentness authority не запрещает законную candidate/conditional работу и не превращается в verified scientific input; legacy zero-entrant projection остаётся явно не измеренным нулём.

Основание: LA-032, LK12, LK20; аудит: C88-G02. Проверка: TEST-UDF-05-03, TEST-UDF-05-05, TEST-UDF-05-06.

### REQ-UDF-05-06
Role assembly должна сохранить полезные metadata выбранных членов без выдачи их за computational authority; source_status/identity/evidence задаются только resolved source. Экспорт payload/evidence не должен позволять внешней мутации изменить последующее чтение captured source или результат другого consumer.

Основание: LA-032, LK12; аудит: C88-R01, C88-G01. Проверка: TEST-UDF-05-01, TEST-UDF-05-04, TEST-UDF-05-05.

## 5. Конкретное техническое решение
Все пути ниже — repo-relative от `policy-engine/`, проверены на pinned commit.

1. **Role assembly owner:** `src/polisyos/data_forge/domains/ukraine/demography/__init__.py::_artifacts_from_resolved_source`. Заменить `{**targets, **priors}`/`payload.update(donor)` на один локальный role-aware assembler. Ownership: targets → `state_ids`, `target_state_totals`, `entrant_state_totals`; priors → `transition_prior_matrix`, `allowed_transition_mask`; donor → `donor_weights`, `donor_state_index`, `donor_record_index`. Для computational fields чужое значение не используется: идентичное допустимо как legacy duplication только после точного equality (с сохранением порядка/shape), отличающееся — явный `SourceResolutionRefusalError` с кодом role conflict до DTO. Unknown fields сохраняют существующую extra-forbid семантику, а не тихо отбрасываются. Полный запрет любых равных повторов отвергнут как ненужное повреждение совместимости; right-biased merge отвергнут как потеря смысла.
2. **Metadata:** existing top-level metadata API оставить совместимым, добавить при необходимости namespaced per-role projection внутри metadata для lossless collisions. Reserved `demography_source_status/identity/evidence` назначаются resolved owner последними. Если same-key metadata различаются, сохранить обе role projections; не делать metadata источником вычислительных arrays. Это небольшой reader contract delta, не новая inventory версия без надобности.
3. **Discrete validation owner:** `UkraineDemographyArtifacts._validate_shapes`, до `_to_numpy(...dtype=np.int64)`. Вынести общую локальную проверку exact finite integral + int64 representability для обоих index arrays. Не переводить большие Python ints сначала в float: int64 max и 2**63 иначе неразличимы. Проверять и присутствующий record index без paired donor, не создавая новый обход. После проверки выполнять существующие shape/pair/range проверки. Integer-valued floats сохраняются, fractions/overflow отказывают. Reader candidate сохраняет existing error translation `demography_bundle_invalid`; прямой DTO — ValidationError. Ошибка не возвращает частичный «исправленный» donor.
4. **Не новый IO:** `src/polisyos/data_forge/domains/ukraine/demography/source_inventory.py::_resolve_inventory`, `src/polisyos/data_forge/domains/ukraine/builders/demography_inventory.py::build_demography_source_inventory_stage`, `src/polisyos/data_forge/read_api/ukraine.py::load_verified_stage_artifacts` и `load_verified_stage_output_bytes` уже осуществляют выбранные reads/basis. Использовать их в тесте, не реконструировать manifest по имени файлов. Producer → inventory → profile-aware receipt → fresh public reader → `src/polisyos/data_forge/domains/ukraine/static_aging.py::build_static_aging_state` → `src/polisyos/foundry/methods/catalog/simulation/demography.py::StaticAgingSimulationEstimator.pure_step`.
5. **Native gap:** расширить `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py`; его `_make_candidate` использует настоящие bytes/CAS/orchestrator, но патчит server/Part-A/prior-stage gates. Поэтому existing helper пригоден для изолированного data-chain scope, не для утверждения admitted full pipeline. Для stronger claim выполнить route в реально разрешённом profile, либо предъявить отдельно gate execution и честно оставить admission outside data-chain scope. Не запускать server-only workflow в неподходящей среде.
6. **Source suitability:** использовать уже существующие `SourceFact` provenance/unknown fields, не новый универсальный validator модели. В delivery указать фактические materialized inputs и основания concrete-use claims. Это не блокирует полезный conditional aging, но ограничивает научную интерпретацию.

## 6. Локальные различающие проверки

Все TEST — будущие спецификации проверок, не заявления о существующих тестовых функциях. Сначала расширять перечисленные реальные test owners; новый файл — только при отсутствии подходящего owner.

### TEST-UDF-05-01 — native unit; historical и candidate reader / NOT_RUN
- **Setup:** Два state_ids, targets=[100,250], согласованные priors и donor; варианты с priors.target_state_totals=[900,800], чужим state_ids, donor override, равным повтором; реальный resolved source.
- **Действие:** Вызвать scalar targets и aggregate, затем повторить после изменения только metadata другого члена.
- **Oracle:** Чужое отличающееся computational поле вызывает role-specific refusal/ValidationError до aggregate; равный повтор не меняет [100,250]/axis. Metadata всех ролей сохраняются по выбранной совместимой схеме, reserved source evidence не подменяется.
- **Ожидаемый исход:** Конфликт — negative; обычные и равные повторения — positive. На старом dict merge контроль [900,800] ошибочно проходит, поэтому regression различающий.
- **Doubles / граница:** Разрешены tiny JSON fixtures. Нельзя заменить assembler/validator копией или считать candidate fixture доказательством CAS chain.
- **REQ:** REQ-UDF-05-01, REQ-UDF-05-06.

### TEST-UDF-05-02 — native unit DTO + public reader / NOT_RUN
- **Setup:** Полный валидный bundle; donor state [0,1], record [1001,1002]. Параметры .9/1.9, -.9/1, record1001.9, NaN/±Inf, int64 min/max и соседние integers, float2**63, state -1/n_states; integer float1.0.
- **Действие:** Построить DTO и прочитать bundle обоими public routes; проверить standalone record_index без paired donor отдельно, если current DTO принимает такое сочетание.
- **Oracle:** Ни один неверный индекс не попадает в downstream int64; exact integer float разрешён без смены значения; большие Python ints сравниваются до lossy float cast. Signed record domain сохранён; state range ограничен. Preserved standalone-record shape не даёт обхода integrality.
- **Ожидаемый исход:** Дробные/непредставимые — отказ; валидные границы record и допустимые state — тот же ID. Old fractional truncation reproducer обязан упасть на старой реализации.
- **Doubles / граница:** Настоящий NumPy/Pydantic; не имитировать dtype/validation. Допустимы входные массивы и временный filesystem.
- **REQ:** REQ-UDF-05-02.

### TEST-UDF-05-03 — native unit historical compatibility / NOT_RUN
- **Setup:** Матрица new only / legacy only / оба complete / mixed partial / present-invalid / standalone scalar / absent donor / legacy entrants absent / candidate entrants absent / unknown donor.
- **Действие:** Вызвать существующие public readers с explicit layout и без него; сохранить прежний snapshot отдельно.
- **Oracle:** Whole-layout semantics не смешивают sources; explicit old остаётся доступным; standalone scalar и lawful donor absence работают; legacy omitted entrants дают zeros только вместе с compatibility note и not_established; candidate omitted entrants — отказ.
- **Ожидаемый исход:** Положительные legacy/scalar paths обязательны; отказ не является единственной реализацией защиты.
- **Doubles / граница:** Использовать реальный tempfile filesystem, не mock existence/read. Это bounded historical compatibility, не native pipeline evidence.
- **REQ:** REQ-UDF-05-03, REQ-UDF-05-05.

### TEST-UDF-05-04 — native integration producer→inventory→profile-aware CAS→fresh reader / NOT_RUN
- **Setup:** Tiny реальный producer manifest с targets/priors/donor и ArtifactRecord; build_demography_source_inventory_stage, FileSystemCAS и load_verified_stage_artifacts. Отдельные generations, explicit donor absence; выбранные profile receipts.
- **Действие:** Создать inventory stage/receipt; закрыть объекты и открыть fresh reader. Изменить producer files; прочитать старый receipt. Затем по одному удалить/испортить CAS member, изменить manifest membership/hash/size/profile basis.
- **Oracle:** Receipt имеет exact selected manifest/member IDs/hash/size/profile и сохранённый generation basis; captured чтение не зависит от producer mutation; fresh reader выдаёт прежние arrays/evidence, integrity failures не дают filesystem fallback/смешение поколений.
- **Ожидаемый исход:** Valid route и old receipt работают; corrupt/missing/inexact basis отказывают с причиной и без частичного aggregate.
- **Doubles / граница:** Нельзя fake CAS, read API или hashes. Синтетический producer manifest — допустимый source fixture, не реальное ведомственное происхождение. Патчи server/Part-A gate в existing helper требуют отдельной маркировки и не доказывают admitted orchestrator run.
- **REQ:** REQ-UDF-05-04, REQ-UDF-05-06.

### TEST-UDF-05-05 — native integration public readers→pure aging→Foundry / NOT_RUN
- **Setup:** Валидный inventory receipt из TEST-04, source facts partly consumer_asserted/partly not_established. Native JAX/Foundry environment. Реальный build_static_aging_state и StaticAgingSimulationEstimator.
- **Действие:** Прочитать все четыре public readers, построить aging state и выполнить pure_step; вторым compatible fixture изменить state names/count и значения без case-specific code. Попытаться изменить exported arrays/evidence и прочитать повторно.
- **Oracle:** В pure state/result diagnostics поступают тот же ordered axis, totals, discrete donor IDs, source_identity, candidate evidence; повторное чтение неизменно; actual estimator производит предусмотренный конечный результат. Условный fixture calibration report не становится empirical calibration.
- **Ожидаемый исход:** Два полезных candidate consumers работают; роль/ID corruption не доходит до compute. Сравнить конкретные ожидаемые arrays/diagnostics, не только exit0.
- **Doubles / граница:** Нельзя подменять JAX/Foundry/pure_step. Малый calibration report допустим только явно synthetic prerequisite; не выдавать его за scientific validation. Проверять чистоту aging отдельно: никаких новых IO внутри.
- **REQ:** REQ-UDF-05-01, REQ-UDF-05-02, REQ-UDF-05-03, REQ-UDF-05-04, REQ-UDF-05-05, REQ-UDF-05-06.

### TEST-UDF-05-06 — contract qualification / concrete-use boundary / NOT_RUN
- **Setup:** Один валидный candidate receipt с полным перечнем source fact keys и intentional unknowns; отдельно переданный документированный concrete-use источник, только если он реально имеется.
- **Действие:** Сформировать evidence mapping фактических measure/unit/period/state mapping/owner/currentness и вывод consumer на selected fixture.
- **Oracle:** Каждому claimed fact соответствует существующий witness или явное not_established; hash/author assertion не поднимает уровень до scientific/owner currentness. Без внешнего witness candidate computation остаётся доступным, а concrete empirical claim остаётся withheld.
- **Ожидаемый исход:** Механическая приёмка LA-032 возможна с честным candidate scope; эмпирическая пригодность не объявляется PASS без конкретного источника.
- **Doubles / граница:** Нельзя выдумывать corpus/owner signature или требовать универсального автоматического изобретателя demographic модели. Source fixture доказывает лишь contract propagation.
- **REQ:** REQ-UDF-05-05.

## 7. Общий сценарий, зависимости и ownership
Общий [LANE-07 сценарий](../03_Интеграция/LANE-07.md) **E02-I07-B** объединяет UDF-05/FED-01/FED-02: selected artifact и second read, role/lineage/precedence. UDF-05 предоставляет role-owned demographic fixture и fractional-index negative; не копировать federation infrastructure и не утверждать federation correct по одному demographic test.

Нет обязательного predecessor из исходной карточки. Согласовать generation/CAS API с их существующими owners LANE-06/08, не менять их одновременно отдельным writer. UDF-05 владеет demographic assembler/DTO и тестами в `tests/unit/remediation/test_udf_05.py`, `tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py`, `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py`. Foundry consumer только читается/проверяется; изменение общего Foundry выполняется его owner лишь при отдельном воспроизведении. CP2 — окно связанной приёмки, не новый runtime registry.

## 8. Совместимость, история, rollback
Historical arrays и source bytes не переписываются. В change note отдельно equivalent ownership refactor и intentional rejection fractional/conflicting inputs. Старые конфликтные bundle теперь явно невалидны, не «мигрируются» выбором последнего поля. Equal duplicates и допустимые integral arrays не требуют миграции. Legacy zero entrant qualification сохраняется. Новое role metadata namespacing, если нужно, — additive; old top-level keys и source identity не меняются без contract test.

Rollback не означает повторное разрешение silently truncated IDs: затронутые inputs оставить refused/qualified, сохранить независимые корректные sources/old receipts. Не удалять CAS/history ради чистого прогона.

## 9. Free-grow и разумные отступления
[Vision §3–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): reuse существующего IO и typed boundary, переносимый механизм вместо path-per-case. [North Star §2, §5, §7](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md): model structure и происхождение не равны bytes; при этом working conditional simulation ценна. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): epistemic regime должен остаться явным.

Узкая role-specific schema здесь оправдана реальным demographic domain; не обобщать локальный баг до платформы всех источников. Второй совместимый dataset проходит тем же assembler/inventory без отдельного orchestration branch. Новая демографическая семантика может потребовать нового общего кода; не требовать детерминированного «изобретателя модели». Historical ratification не даёт текущему fixture эмпирическую authority и не запрещает полезную кандидатную работу.

## 10. Приёмка и запрещённые утверждения
Предъявить patch/base, actual write map, before/after R01/R02, complete native logs supported Python 3.14 и фактических NumPy/JAX/Pydantic/CAS versions; exact selected receipt/source hashes, gate/doubles scope, results TEST-01–06 и общий E02-I07-B evidence locator. Реальные existing targets: `tests/unit/remediation/test_udf_05.py`, `tests/unit/data_forge/domains/ukraine/test_demography_artifacts.py`, `tests/unit/data_forge/domains/ukraine/test_demography_source_inventory.py`. Адаптируемый шаблон после проверки runner: `<supported-python> -m pytest <эти paths>`, из `policy-engine/`; наличие pytest/3.14 здесь не объявлено установленным.

Нельзя объявлять native pipeline PASS по copied-function probe, stubbed gate или только filesystem тесту; immutable receipt — научной пригодностью; fixture calibration — настоящей калибровкой; отказ всех inputs — исправлением; перечень TEST — их исполнением. G02 закрывается как честно ограниченная contract/use qualification, а не фиктивный empirical PASS. Если реально выбран конкретный scientific use, его source-owner/currentness/measurement witness предъявляется отдельно; без него остаётся только соответствующий stronger claim withheld.

