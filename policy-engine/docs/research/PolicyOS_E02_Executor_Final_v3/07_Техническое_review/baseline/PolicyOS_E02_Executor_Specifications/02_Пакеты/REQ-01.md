# REQ-01 — Сохранность явной потребности и domain-нормализация DataRequirement

**LANE-01 · LA-045, LA-046 · CP1 · исполнительское ТЗ; не исполнено.**
Основание: `20d9009be21097bfbdc38a546a15cc60213b8ace`; исходный план, строки 303–507; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/REQ-01.md). Все новые TEST — **NOT_RUN**. Это ТЗ, не сообщение об исполнении.
**Тип работы:** Локальный behavior fix нормализации домена; qualify/preserve выполненную private-чистку, scope/discovery и historical readers; LA-046 этап1/2.
**Практический результат:** Одинаковый запрос об образовании не превращается в fiscal из-за написания domain; явные потребности и неизвестные остаются видимыми и поступают действительному resolver. Новый совместимый construct/resource подключается общим путём без возврата hardcoded family authority.

## 1. Что сохраняется

- LK24: compiler, construct extractor, resolver guards, reports и исторические readers живы; bounded helper cleanup не разрешает удалить весь compiler.
- LK31: actual N7/compiler/planner/reentry не legacy целиком; typed source gap и explicit semantic constructs не заменяются family labels.
- Исходный preserve family-heuristic пересмотрен: retirement сохраняется; полезность replacement проверяется положительно.
- Canonical domains и названный pilot profile, raw input, versioned report bytes; missing/unknown/explicit-empty различаются.
- LA-046 accountable closure ACQ-01; compiler unit PASS не закрывает весь acquisition.

## 2. Полный disposition исходных обязанностей и остатков

| Основание | Disposition | REQ | Решение / владелец |
|---|---|---|---|
| LA-045 | qualify | REQ-REQ-01-06, REQ-REQ-01-09 | Точная private-группа уже отсутствует; не заказывать повторное удаление. |
| AM03 | preserve | REQ-REQ-01-06 | _digest включён в семь функций; hashlib/json остаются живыми. |
| LA-046 original generic/pilot obligations | preserve | REQ-REQ-01-03, REQ-REQ-01-04 | Большинство исходных scope/ID/text потерь уже изменены; regression по полному query. |
| REQ-01 §2 domain alias | fix | REQ-REQ-01-01, REQ-REQ-01-02, REQ-REQ-01-09 | Реальный source-класс education_policy→fiscal; один общий нормализатор. |
| C03_C04 R03 | fix | REQ-REQ-01-01, REQ-REQ-01-02, REQ-REQ-01-09 | Единый shared domain-дефект; другие пакеты не создают свой resolver alias fix. Owner: **REQ-01**. |
| REQ-01 §3 retirement reinterpretation | preserve | REQ-REQ-01-07 | Исходный preserve эвристики заменён явным решением и проверкой полезности replacement. |
| REQ-01 §3 replacement usefulness | capability | REQ-REQ-01-04, REQ-REQ-01-07 | Положительный новый совместимый ресурс и реальный consumer, не один removal flag. |
| REQ-01 §4 finite compatibility census | lifecycle | REQ-REQ-01-06, REQ-REQ-01-09 | Закрытая область first-party/distribution вместо неограниченного поиска внешних users. |
| REQ-01 §5 top-level construct characterization | qualify | REQ-REQ-01-08 | Поддержка top-level shape не установлена; bounded DEC до расширения API. |
| AM04 original handoff, reinterpreted | shared | REQ-REQ-01-05 | Старое raw explicit-spec precedence не восстанавливать: текущий source отмечает такие поля unbound; сохранять semantic declarations и owner-bound source gap. Owner: **ACQ-01**. |
| C03_C04 R02 | shared | REQ-REQ-01-04, REQ-REQ-01-05 | Реальные compiler/planner missing-byte controls и конечный acquisition consumer — ACQ-01. Owner: **ACQ-01**. |
| LA-046 closure | shared | REQ-REQ-01-04, REQ-REQ-01-05, REQ-REQ-01-07 | Нативный compiler результат не является полной LA-046 приёмкой. Owner: **ACQ-01**. |

## 3. Атомарный нормативный контракт

### REQ-REQ-01-01
Явный canonical domain или документированный spelling alias должен нормализоваться в тот же ProblemDomain; образование/education_policy/Education Policy не должны заменяться fiscal. Поддержанные fiscal/social/healthcare и остальные canonical enum значения сохраняются.
Источник: LA-046; остаток: C03_C04 R03; REQ-01 §2 domain alias. Проверка: TEST-REQ-01-01, TEST-REQ-01-02.

### REQ-REQ-01-02
Неподдержанный явный domain должен сохраняться как исходная строка и давать явно ограниченное CUSTOM/unresolved представление либо адресный input refusal; он не должен становиться другой предметной областью по fallback. Доступные explicit constructs и candidate работа не должны теряться только из-за незнакомого label.
Источник: LA-046; остаток: REQ-01 §2 unsupported-domain contract; S08. Проверка: TEST-REQ-01-01, TEST-REQ-01-08.

### REQ-REQ-01-03
Compiler adapter должен сохранить text/request и объявленные jurisdiction/interval/constructs; opaque scenario ID, generic geography/time и lexical topic proposal не должны создавать обязательный construct, UA/2022 или source authority.
Источник: LA-046; остаток: LA-046 original generic/pilot obligations; REQ-01 §§1,4. Проверка: TEST-REQ-01-02, TEST-REQ-01-03.

### REQ-REQ-01-04
Поддержанные explicit semantic constructs должны доходить до actual capability resolver с согласованным scope; обязательный отсутствующий resolver и неизвестная basis должны иметь точный исход, отличный от доказанного отсутствия потребности.
Источник: LA-046; остаток: REQ-01 §3 replacement usefulness; LK24; LK31. Проверка: TEST-REQ-01-02, TEST-REQ-01-03, TEST-REQ-01-04.

### REQ-REQ-01-05
REQ-01 и ACQ-01 должны передать один versioned compiler-owned denominator и report в N7; caller-supplied raw specs не должны подменять его. Owner-bound typed gap может выбрать только действительно скомпилированную потребность без изменения её смысла.
Источник: LA-046; остаток: AM04 original handoff, reinterpreted; C03_C04 R02; LK31. Проверка: TEST-REQ-01-02, TEST-REQ-01-05.

### REQ-REQ-01-06
Семь retired private функций и _DATA_FAMILY_ORDER не должны возвращаться; действующие compiler/facade/hash/report/reader exports и конечный поддержанный набор consumers должны сохраняться. Изменение AST сентября не является критерием эквивалентности сегодняшнего behavior fix. Не требовать AST-равенства текущих функций историческому relocation commit: проверять нынешний контракт и конечный caller scope.
Источник: LA-045; остаток: LA-045; AM03; REQ-01 §4. Проверка: TEST-REQ-01-06.

### REQ-REQ-01-07
Старый feature flag не должен восстанавливать retired family-authority эвристику; при добавлении совместимого нового construct/resource положительная потребность должна проходить existing governed resolver без новой ветки по кейсу. Candidate proposals остаются proposals.
Источник: LA-045, LA-046; остаток: REQ-01 §3 retirement reinterpretation; LK24; S08. Проверка: TEST-REQ-01-04, TEST-REQ-01-06.

### REQ-REQ-01-08
Поддержанный producer shape required_constructs должен быть определён конечным source/caller census: значение в supported shape не теряется при _claim_record_like. Неподдержанный shape должен иметь явный договор/отказ, а не обещанную совместимость private helper.
Источник: LA-046; остаток: REQ-01 §5 top-level construct characterization. Проверка: TEST-REQ-01-07.

### REQ-REQ-01-09
Новая domain/input interpretation должна быть отражена в versioned rule/provenance текущего report; original raw domain/text/scope и historical v1/v2 bytes сохраняются без повышения их evidence basis задним числом.
Источник: LA-045, LA-046; остаток: REQ-01 §§2–4 compatibility; LK24. Проверка: TEST-REQ-01-08.

## 4. Конкретное техническое решение

### Один нормализатор, точные spelling aliases
Исправлять _problem_domain_for_scenario через _scenario_adapter_input, не дублировать mapping в N7. Сначала различить absent, present non-string, empty и supplied string/enum. Нормализовать case/разделители как spelling; построить canonical aliases из ProblemDomain.name/value и общего suffix «policy» для того же canonical token. Существующие обоснованные health→healthcare aliases сохранить отдельным небольшим vocabulary mapping. Не выбирать domain по случайной подстроке или ID.

### Unknown не fiscal и не запрет исследования
Предпочтительный путь — уже существующий ProblemDomain.CUSTOM как transport escape hatch, с сохранением raw domain, статусом unresolved и причиной в compiler report metadata. Это не утверждение, что CUSTOM методологически поддерживает любую задачу: resolver получает explicit constructs/scope и ограничения. Malformed value или несовместимые одновременно supplied domain/domain_hint получают typed input error до grammar. Сначала использовать подходящий existing typed input error; только если его код/поле не выражает новый domain contract, небольшой новый ScenarioDomainInputError внутри compiler должен иметь code/reason/field по образцу соседних input errors; N7 переводит его в адресный GenerationCycleError, не generic success. Имена новых code — предлагаемый contract, зафиксировать вместе с tests.

### Provenance и отсутствие поля
_bind_scenario_compilation_inputs уже хэширует полный raw scenario и связывает rule refs; использовать его и versioned metadata, не создавать отдельный store. Для отсутствующего domain сохранить raw absence; выбор CUSTOM/явно ограниченного semantic proposal определить DEC-REQ-01-01, не молча назначать factual fiscal. Явный pilot обязан передать свой domain/profile. Новая interpretation version не меняет старые bytes.

### Compiler-owned denominator, важное уточнение старого плана
Текущий _n7_data_requirement_basis_with_report:9946–9962 помечает raw specs inputs unbound;10109–10118 разрешает routing только без отказа. Поэтому исходное «explicit specs precedence» сохранить как precedence явного semantic requirement и owner-bound source gap, а не вернуть произвольную инъекцию specs. DataRequirementCompiler и capability_resolutions остаются единственным производителем denominator. ACQ-01 владеет изменениями N7 composition; REQ-01 передаёт domain error/provenance contract и совместный тест.

### Сохранить активную пользу после retirement
Не возвращать _required_data_families_from_heuristic. Explicit constructs → _construct_resolution_inputs → _resolve_capability_requirements → injected resolver → compilation report остаются основным путём. Lexical proposals могут расширять поиск, но не входят в required authority без явного основания. TEST-04 требует положительный новый compatible resource/consumer; если общий adapter действительно отсутствует, расширить его один раз, а не завести новый case switch.

### Private cleanup и claim shape
LA-045 здесь qualify-only: семь функций/constant уже удалены. Проверить actual public/installed callers, не требовать искусственный cleanup diff. _claim_record_like теряет top-level required_constructs, но public поддержка неизвестна: DEC-REQ-01-02 ограничивает census и выбор. Если producer поддержан — нормализовать его декларацию в существующую canonical metadata форму до создания claim, проверить конфликт aliases; иначе явно документировать неподдержанный shape без присвоения новой capability.

### Альтернативы
Отвергнуть regex только для education_policy, немой fiscal fallback, глобальный NLP framework и blanket отказ всем неизвестным доменам. Governed domain vocabulary допустим как маршрутизирующий язык; он не должен стать закрытым списком доступных политических вопросов. Принципиально новая семантика может требовать нового общего кода, но не скрытой ручной авторизации.

## 5. Локальные тесты и точные oracle

Идентификаторы ниже — **предлагаемые проверки**, не имена уже существующих функций. Указанные file/selectors действительно найдены; их прежний source read не PASS. Любая дополненная проверка должна различать старый дефект/контролируемое удаление нужного механизма и исправленный positive.

### TEST-REQ-01-01 — native compiler unit · NOT_RUN
- **REQ:** REQ-REQ-01-01, REQ-REQ-01-02.
- **Setup:** Настоящий _scenario_adapter_input/compile_for_scenario; параметризовать все canonical ProblemDomain values и поддержанные spellings, включая education/education_policy/Education Policy и fiscal/social/healthcare controls.
- **Действие:** Подать одинаковый meaningful text с каждым spelling; затем unsupported label с тем же текстом, malformed value и конфликт domain/domain_hint.
- **Oracle:** Canonical/alias пары дают один canonical domain; unsupported не FISCAL по умолчанию, raw строка сохранена; malformed/conflict дают адресный input outcome. Изменение opaque ID не меняет domain.
- **Ожидаемо:** education_policy воспроизводит старый дефект до fix; отрицательный контроль намеренного возврата старого fallback ломает тест.
- **Evidence:** Параметры и full normalized input/grammar call; exact error code и raw-domain trace.
- **Doubles:** Recording grammar разрешена только для boundary assertion; компилятор/adapter не подменяются. Это не downstream admission PASS.

### TEST-REQ-01-02 — native N7→compiler→resolver integration · NOT_RUN
- **REQ:** REQ-REQ-01-01, REQ-REQ-01-03, REQ-REQ-01-04, REQ-REQ-01-05.
- **Setup:** Actual GenerationCycleController._n7_data_requirement_basis_with_report и actual DataRequirementCompiler; два разных explicit statements/scopes, действительный finite release-backed resolver fixture через существующий owner.
- **Действие:** Пройти canonical education и alias education_policy до grammar, report и resolver; прочитать report/basis в N7 consumer.
- **Oracle:** Сохраняются text/domain/jurisdiction/interval/required constructs; эквивалентный alias не меняет subject/domain query; разные meaningful requests дают различимое основание. Report denominator потреблён, не captured dict подставного compiler.
- **Ожидаемо:** Рабочая compatible requirement доходит до actual resolver result; exact missing resolver/basis не представляется no-need; raw specs не расширяют denominator.
- **Evidence:** Current source/backend, реальные report/query/selected source refs, negative mutation raw specs и domain.
- **Doubles:** Контролируемый finite external data source разрешён; запрещены _RecordingCompiler и resolver, который всегда выдаёт готовую authority по любому запросу. Actual resolver owners обязательны для integration claim.

### TEST-REQ-01-03 — native compiler contract regression · NOT_RUN
- **REQ:** REQ-REQ-01-03, REQ-REQ-01-04.
- **Setup:** Существующие test_compiler.py tests opaque_scenario_id, negated_topic, generic_scope, explicit_constructs и named profiles; actual DTO.
- **Действие:** Тот же вопрос с case-alpha/parent-support; отрицание rent; national/annual без profile; два explicit jurisdiction/interval; required/proposed/empty/unknown constructs.
- **Oracle:** ID/отрицание не создают required housing_rent_burden; generic labels не подставляют UA/2022; explicit scope сохранён; unknown basis и explicit empty различаются; proposals не выдаются за required или authority.
- **Ожидаемо:** Есть положительный explicit construct resolver path и все отрицательные controls.
- **Evidence:** Полные query/basis/reason fields, а не число specs; diff ключевых semantic полей.
- **Doubles:** Для unit допустим recording resolver как наблюдатель; его output не считать реальным admission и не использовать вместо TEST-02.

### TEST-REQ-01-04 — capability growth, native resolver + shared scenario · NOT_RUN
- **REQ:** REQ-REQ-01-04, REQ-REQ-01-07.
- **Setup:** Действительный supported construct/resource profile вне одного пилота, с owner-scoped данными и declared mapping; заранее записать обязательную потребность и available resource.
- **Действие:** Добавить совместимую запись через existing corpus/index/mapping owner без case-code branch; получить compiled requirement и actual resolver binding; передать его ACQ-01 в E02-I01-B.
- **Oracle:** Потребность обнаружена и потреблена по общему contract; unknown/incompatible resource не подавляет explicit requirement и не получает authority. Старый family flag не влияет на required output.
- **Ожидаемо:** Положительная пригодная потребность не потеряна после retirement; нет обещания полноты arbitrary semantic parsing.
- **Evidence:** Before/after catalog rows, code delta (если общий adapter понадобился — DEC), query/report/consumer refs и useful result либо scoped unresolved.
- **Doubles:** Допустим declared finite controlled source; нельзя выдавать hash/index-hit за consumed capability или скрыть per-case rule в JSON как якобы универсальный алгоритм.

### TEST-REQ-01-05 — native boundary negative + positive · NOT_RUN
- **REQ:** REQ-REQ-01-05.
- **Setup:** Реальный скомпилированный denominator и owner-bound typed gap; отдельно caller supplies raw data_requirement_specs/compiled_requirement_specs/runtime hint.
- **Действие:** Попытаться заменить/добавить raw spec и подменить source gap; затем выполнить легальный выбор существующего compiled requirement.
- **Oracle:** Unbound fields не маршрутизируют новый gap; конкретная routing limitation сохраняется; легальный source gap выбирает только compiler-owned requirement без изменения denominator.
- **Ожидаемо:** Нет регрессии к historical raw-spec precedence; положительный typed gap продолжает действительный acquisition.
- **Evidence:** N7 report/denominator/binding and routing reason; ACQ shared evidence для конца цепи.
- **Doubles:** Нельзя подменять _n7_route_compiler_gaps или вручную выдавать gap owner receipt.

### TEST-REQ-01-06 — static finite census + native installed import · NOT_RUN
- **REQ:** REQ-REQ-01-06, REQ-REQ-01-07.
- **Setup:** Точная группа LA-045: _data_families_from_obligation_graph,_data_family_token_from_frontier_item,_nested,_normalised_family,_slug_family,_ordered_data_families,_digest,_DATA_FAMILY_ORDER; first-party maintained source/tests/generated export inventories и поставляемый wheel.
- **Действие:** Проверить отсутствие retired definitions/необходимых callers, actual public imports и existing test_req_01_installed.py; поднять legacy flag в существующем removed-family test.
- **Oracle:** Живые compiler/facade/resolver/hash/report функции доступны; retired группа и family heuristic не воскресают; найденный реальный supported consumer получает явную миграцию, не массовое удаление.
- **Ожидаемо:** Cleanup-квалификация без искусственного нового source edit; никаких требований AST равенства сентябрю.
- **Evidence:** Именованный denominator scan, команды/результаты cold import/installed test, caller disposition.
- **Doubles:** Не считать простой grep-zero полным external census; no installed interpreter — UNRUN, не PASS.

### TEST-REQ-01-07 — bounded contract census + native normalization · NOT_RUN
- **REQ:** REQ-REQ-01-08.
- **Setup:** Прочитать все first-party producers, передающие Mapping claim с required_constructs в compiler; current _claim_record_like и supported metadata form.
- **Действие:** Для найденного supported producer прогнать actual public compile path, сравнив top-level и metadata форму; если support не установлен, закрепить допустимый shape и отказ/diagnostic неподдержанного.
- **Oracle:** Поддержанное declared requirement сохраняется до resolver; unknown shape не получает вымышленную публичную поддержку. Решение DEC-REQ-01-02 имеет конечный evidence и owner.
- **Ожидаемо:** Либо bounded adapter fix с двумя representations, либо ограниченный documented contract с negative test; не новый неподтверждённый bug.
- **Evidence:** Список producers/schema и конкретный native reproduction; selected decision.
- **Doubles:** Private helper-only test недостаточен для public support.

### TEST-REQ-01-08 — native persistence compatibility · NOT_RUN
- **REQ:** REQ-REQ-01-02, REQ-REQ-01-09.
- **Setup:** Tracked historical v1/v2 report bytes и новый domain-resolution report; actual parse/write/audit_surface readers.
- **Действие:** Прочитать/сохранить заново исторические bytes и новый report, открыть fresh reader; сравнить raw/canonical domain и rule_version binding.
- **Oracle:** Historical bytes и их прежняя basis не изменены; новый input interpretation даёт новое честное rule/provenance поле; unknown/CUSTOM не promoted. Старые consumers либо читают supported metadata, либо имеют явный versioned отказ.
- **Ожидаемо:** Нет silent reinterpretation/rename старого report как нового proof; данные доступны следующему consumer.
- **Evidence:** Byte hashes, version/metadata/result fields, roundtrip и tamper negative.
- **Doubles:** Реальные serializers/readers; forbidden preassembled new report masquerading as old bytes.

## 6. Общая интеграция и ownership

Использовать **E02-I01-B, E02-X02** из [общего LANE-01](../03_Интеграция/LANE-01.md); не создавать ещё одну копию тяжёлого стенда. CP1 — окно связанной приёмки, не новый runtime реестр и не full CI на каждый пакет.

- ACQ-01: владелец полного LA-046 caller→compiler→resolver→admission→reentry; domain rule реализуется один раз REQ-01.
- CYC-03: current continuation и reuse; REQ-01 не повторяет dispatcher.
- LA-045 совместимость: first-party imports/loaders/exports/distribution scope; не бесконечный внешний census.

Порядок: установить существующий positive → воспроизвести адресный остаток → внести минимальное intentional изменение, если оно требуется → локальные различающие controls → affected shared scenario на стабильном общем наборе inputs. Один writer у фактически пересекающегося owner; чтение и непересекающиеся документы не сериализовать.

## 7. Совместимость, миграция и rollback

Не переписывать v1/v2 reports; учитывать rule interpretation version в новых outputs. Семантически одинаковый spelling разрешён как тот же canonical domain, raw input identity остаётся различимой для audit. Не удалять canonical domain enum/facade или historical readers. Смена unknown handling — intentional behavior fix, отдельно от cleanup. При rollback сохранить новые immutable outputs и их versioned reader/точный unsupported outcome; не присваивать им старую fiscal интерпретацию.

## 8. Free-grow и смысл design-decisions

- Vision Rule12: совместимый construct/resource через общий resolver; не буквальный запрет нового общего кода и не восстановление retired fallback.
- Stage0 §4.3 K06 и W5 K01/K08: unknown domain/context допускает candidate работу, не создаёт предметного/полномочного основания.
- S01/S03/S08: потребность доходит до реального ресурса/consumer; отсутствие match не доказывает отсутствие потребности.

Нормативными являются REQ этого пакета; design-ссылки объясняют цель и статус выбранного решения, но не создают скрытого требования реализовать все планы корпуса.

## 9. Ограниченные открытые решения

### DEC-REQ-01-01: Как текущий grammar/resolver потребляет CUSTOM и отсутствие domain без потери explicit requirement?
**Owner:** REQ-01; ACQ-01 подтверждает N7 error/continuation surface
Варианты: CUSTOM + raw/status metadata, explicit constructs/scope продолжаются — предпочтительный путь.; Typed adapter refusal только для отсутствующей indispensable semantics, с сохранённым candidate/report и точным запросом; не blanket unknown-domain refusal.
**Выбрать по:** Actual PolicyGrammarCompiler/compiled report для neutral unknown и явно заданного construct; existing ProblemDomain.CUSTOM escape hatch.
**Обязательный выход:** До merge domain fix закрепить один exact contract, rule version и TEST-01/02/08; explicit alias fix и finite cleanup проверки не ждут всемирного semantic решения.

### DEC-REQ-01-02: Входит ли top-level required_constructs у Mapping claim в фактически поддержанный producer contract?
**Owner:** REQ-01 compiler owner
Варианты: Да: перенести без потери в canonical record, reject conflicting aliases.; Нет: сохранить metadata contract и сделать unsupported top-level input явным.
**Выбрать по:** Конечные first-party producers + публичные DTO/schema + actual compile trace, не private helper поведение.
**Обязательный выход:** Именованный перечень producer scope и выбранный поддержанный shape с TEST-07; не оставлять «разобраться вообще».

## 10. Предъявление и запрет ложного PASS

Предъявить до/после domain counterexample и работающие canonical/unknown/explicit-construct контроли, actual N7→compiler→resolver report, finite LA-045 census и versioned readback. TEST-02/04 с shared E02-I01-B нужен для полезности replacement; source-only или RecordingCompiler не закрывает LA-046. Полное LA-046 закрытие только вместе с ACQ-01 actual acquisition/reentry. Native среда отсутствует — сохранить UNRUN, не объявлять недействительными все specs.

## 11. Проверенные текущие места

- [policy-engine/src/polisyos/data_requirement/compiler.py:122–196](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L122-L196) — `_ScenarioAdapterInput / typed input error conventions`.
- [policy-engine/src/polisyos/data_requirement/compiler.py:486–572](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L486-L572) — `compile_for_scenario`.
- [policy-engine/src/polisyos/data_requirement/compiler.py:797–812](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L797-L812) — `_claim_record_like`.
- [policy-engine/src/polisyos/data_requirement/compiler.py:1435–1478](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L1435-L1478) — `_bind_scenario_compilation_inputs`.
- [policy-engine/src/polisyos/data_requirement/compiler.py:2279–2300](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L2279-L2300) — `_problem_domain_for_scenario`.
- [policy-engine/src/polisyos/ir/governance/problem_frame.py:49–68](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/governance/problem_frame.py#L49-L68) — `ProblemDomain including CUSTOM`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:9937–9963](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9937-L9963) — `compiler-owned N7 basis/unbound overrides`.
- [policy-engine/src/polisyos/runtime/quality/generation_cycle.py:10090–10118](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L10090-L10118) — `actual compiler/resolver and routing refusal`.
- [policy-engine/tests/unit/data_requirement/test_compiler.py:725–799](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/data_requirement/test_compiler.py#L725-L799) — `scenario adapter unit doubles and retirement control`.

Трассировка: [`../04_Трассировка/REQ-01.json`](../04_Трассировка/REQ-01.json). Исторические количества «осталось/следующий пакет» из исходных отчётов не являются текущим статусом: этап1 охватил127/127, но это не product completion.

## 12. Точная трассировка исходных obligation IDs

Полная таблица, включая дословные основания, находится в companion JSON и сохранённом аудите. Probes и полные runtime logs остаются в отдельно доставленном phase1 ZIP; файл ТЗ не выдаёт их за новое исполнение.

| Inventory ID | REQ / TEST | Решение |
|---|---|---|
| remaining:0458 | REQ-REQ-01-06 | qualify: Конечный installed/public caller scope и существующие compiler tests. |
| remaining:0459 | REQ-REQ-01-06 | superseded: Историческое AST equality было ограничением отдельного cleanup, не нынешнего развившегося compiler; replacement — текущие contract/installed checks. |
| remaining:0460 | REQ-REQ-01-01, REQ-REQ-01-02, REQ-REQ-01-09 | fix: Общий domain-normalizer, unknown metadata и versioned input provenance. |
| remaining:0461 | REQ-REQ-01-03, REQ-REQ-01-04, REQ-REQ-01-07 | capability: Actual injected resolver/consumer и новый совместимый ресурс; family fallback не восстанавливать. |
| remaining:0462 | REQ-REQ-01-04, REQ-REQ-01-05 | shared: Фраза «ещё не рассмотрена полностью» исторически superseded завершённым ACQ-01 аудитом; обязанность acquisition→changed calculation остаётся у ACQ-01 и E02-I01-B. |
| preserve:0757 | REQ-REQ-01-04, REQ-REQ-01-06, REQ-REQ-01-09, TEST-REQ-01-02, TEST-REQ-01-06, TEST-REQ-01-08 | preserve: Действующий resolver/compiler, hash/version и публичные/history readers. |
| preserve:0758 | REQ-REQ-01-06, TEST-REQ-01-06 | preserve: Конечный caller check не восстанавливает удалённые private helpers. |
| preserve:0759 | REQ-REQ-01-03, REQ-REQ-01-05, TEST-REQ-01-03, TEST-REQ-01-05 | preserve: Declared constructs отдельно от proposals; arbitrary raw specs не authority. |
| preserve:0760 | REQ-REQ-01-03, TEST-REQ-01-03 | preserve: Explicit scope, no implicit UA/2022, opaque ID не semantic content. |
| preserve:0761 | REQ-REQ-01-01, REQ-REQ-01-02, REQ-REQ-01-03, REQ-REQ-01-04, TEST-REQ-01-01, TEST-REQ-01-02, TEST-REQ-01-03 | preserve: Text/domain/profile и real injected resolver; unknown basis сохраняется. |

Конкретное архитектурное основание: [System Vision §5 Rule12 и §6 Capability Reality Bar](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): explicit requirements и настоящий resolver/consumer вместо hardcoded family fallback; [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): unknown domain сохраняется как limitation candidate работы, а не молчаливый fiscal.
