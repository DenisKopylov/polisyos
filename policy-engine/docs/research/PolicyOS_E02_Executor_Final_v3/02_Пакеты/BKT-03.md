# BKT-03 — Устойчивое descriptive mean и честная identity статистической диагностики

**Исполнительская спецификация; финальная QA комплекта ещё ожидается.**
**LANE-03 · CP3 · B172, B173.** Основание `20d9009be21097bfbdc38a546a15cc60213b8ace`. Реализация документом не выполнена; все будущие проверки **NOT_RUN**. Именных исполнителя/reviewer назначает проект.

## 1. Практическая цель и область

Согласовать signed-residual reduction producer/reader без ослабления строгой проверки. Сохранить уже правильное разделение полезного описательного смещения, фактического t-test и неустановленных предметных предпосылок; довести результат через настоящий CAS/C5b/packet.

**Тип работы:** C34-R01 numerical cancellation repair; native qualification; scoped statistical-method decision, без нового общего сервиса диагностики.

[Аудит](../05_Основания/Аудит/02_Пакеты/BKT-03.md) · [остатки](../05_Основания/Аудит/01_Реестры/C34_остатки.json) · [исходная карточка](../05_Основания/Аудит/05_Источники/BKT-03_исходные_строки.txt) · [источники](../05_Основания/Аудит/05_Источники/C34_источники.json) · [трассировка](../04_Трассировка/BKT-03.json). Полные диагностические scripts/logs остаются в отдельно доставленном ZIP фазы 1. Действуют [общие правила](../00_Общее/Правила_исполнения_и_приёмки.md).

## 2. Исходные обязанности и сохранение

B172 constant nonzero residual уже сохраняется отдельно от p, знак не превращается в optimistic/pessimistic без ориентации. B173 normal approximation под именем t-test уже удалён: actual SciPy либо explicit unavailable. Требуется не повторный ремонт старой ветви, а устойчивый mean и native/full-consumer доказательство. BKT-02 overflow distinct from C34 cancellation; общий numeric contract согласовать, ID не сливать.

- `preserve:0434`: Magnitude/sign → REQ-BKT-03-01, REQ-BKT-03-03; TEST-BKT-03-01, TEST-BKT-03-03.
- `preserve:0435`: Unknown orientation → REQ-BKT-03-03, REQ-BKT-03-06; TEST-BKT-03-03, TEST-BKT-03-07.
- `preserve:0436`: Exact-zero control → REQ-BKT-03-03; TEST-BKT-03-03, TEST-BKT-03-06.
- `preserve:0437`: Strict source reconciliation → REQ-BKT-03-01, REQ-BKT-03-05; TEST-BKT-03-01, TEST-BKT-03-05.
- `preserve:0438`: Method/backend/version → REQ-BKT-03-02, REQ-BKT-03-04; TEST-BKT-03-04, TEST-BKT-03-05.
- `preserve:0439`: No hidden normal approximation → REQ-BKT-03-04; TEST-BKT-03-04.
- `preserve:0440`: Residual-only degradation → REQ-BKT-03-02, REQ-BKT-03-04, REQ-BKT-03-05; TEST-BKT-03-02, TEST-BKT-03-04, TEST-BKT-03-05.
- `preserve:0441`: Actual packet-section verifier → REQ-BKT-03-05; TEST-BKT-03-05, TEST-BKT-03-06.

## 3. Disposition полного остатка

| ID | Действие / причина | REQ / общий владелец |
|---|---|---|
| `C34-R01` | fix: Согласовать compensated signed mean и честную statistical-range деградацию. | REQ-BKT-03-01, REQ-BKT-03-02 |
| `C34-G01` | qualify: Native complete CAS/C5b/packet path вместо isolated section fixture. | REQ-BKT-03-03, REQ-BKT-03-04, REQ-BKT-03-05 |
| `C34-G02` | qualify: Фактические scientific assumptions и scale policy, без automatic trust. | REQ-BKT-03-02, REQ-BKT-03-06, REQ-BKT-03-07 |

Все source-registry remaining также связаны: `remaining:0291`, `remaining:0292`, `remaining:0293`. Подробная причина и REQ для каждой строки — в companion JSON; повторная запись не считается новым независимым дефектом.

## 4. Нормативный контракт

### REQ-BKT-03-01
Для supported finite residual multiset signed mean/magnitude/sign одинаковы у producer, IR reconciliation и fresh consumer независимо от permutation. [1e16,1,-1e16] даёт mean1/3 и descriptive magnitude1/3, не false neutral/whole-report refusal. Использовать устойчивую reduction, не увеличивать tolerance чтобы скрыть потерянную единицу.
Источник: B172; C34-R01. Проверки: TEST-BKT-03-01, TEST-BKT-03-02.

### REQ-BKT-03-02
Если statistical backend не воспроизводит supported numerical-range contract, сохранить finite scenario rows/descriptive diagnostics и точную unavailable limitation; не приписывать ему вычисленный другим способом statistic/p. Any range change согласовать с BKT-02 и actual fresh recomputation. Numeric backend identity/statistic/p отражают действительно исполненный метод.
Источник: B172, B173; C34-R01, C34-G02. Проверки: TEST-BKT-03-01, TEST-BKT-03-02, TEST-BKT-03-04.

### REQ-BKT-03-03
Constant residual±10 сохраняет magnitude10 и signed direction при not_computable/zero_variance, без p0 и без NEUTRAL positive trust. Exact all-zero — отдельное point-fit состояние без фиктивного executed method. Balanced nonzero residual mean0 не называется exact_zero и сохраняет MAE/неустановленные assumptions.
Источник: B172; C34-G01, C34-G02. Проверки: TEST-BKT-03-03.

### REQ-BKT-03-04
Нормальный supported sample использует actual scipy.stats.ttest_1samp с method/backend/version/statistic/p. Import denial, отсутствующий метод, invalid p/statistic или backend error сохраняют rows/descriptive values и explicit unavailable без hidden normal approximation. При свежем чтении stale p/version/test identity не становятся доступными из сохранённого marker.
Источник: B173; C34-G01. Проверки: TEST-BKT-03-04, TEST-BKT-03-05.

### REQ-BKT-03-05
Native CAS→C5b/calibration summary→full decision packet и fresh reader сохраняют exact source/profile/scope и повторяют diagnostic projection. Изменение p, backend version, bias-card p, counts/mean/scope или exact-zero status выявляется; статистические claims снимаются адресно, validated descriptive values остаются доступными.
Источник: B172, B173; C34-G01. Проверки: TEST-BKT-03-05, TEST-BKT-03-06.

### REQ-BKT-03-06
Scientific interpretation явно задаёт units/metric orientation, residual dependence/effective n, multiplicity и population scope выбранного испытания. Пока эти сведения не установлены, sign остаётся descriptive и direction UNKNOWN; computed p и число rows не снимают unresolved assumptions. Предметный owner может предоставить обоснованную orientation через existing metric contract, но не через знак residual.
Источник: B172, B173; C34-G02. Проверки: TEST-BKT-03-07.

### REQ-BKT-03-07
Absolute std floor1e-12 считается numerical policy, а не математическим доказательством zero variance. До изменения выбрать и документировать supported unit/scale regime либо scale-aware computation; [-1e-14,0,1e-14] и его допустимая смена единиц получают согласованную интерпретацию. Смена policy/version не переаттестовывает старые reports.
Источник: B172, B173; C34-G02. Проверки: TEST-BKT-03-02, TEST-BKT-03-07.

## 5. Конкретное техническое решение

**Ремонт reduction:** `_detect_systematic_biases` использует `np.mean`, IR/fresh reader — `math.fsum/n`. Для текущего supported range заменить producer mean на ту же устойчивую математическую reduction, сохранив independent source recalculation у reader. Все ветки magnitude/sign/bias-presence используют этот mean; не исправлять только отображаемое поле. Для wider range согласовать с BKT-02 scaled summation/typed limitation, поскольку и fsum может переполниться. Не расширять `_close` чтобы принять0 вместо1/3.

**t-test отдельно.** Actual SciPy может иметь собственную finite precision reduction. Не записывать стабилизированный hand-computed statistic под method_id SciPy, если он не был этим backend получен. Сравнить actual result с declared source reduction/variance в допустимом tolerance; при genuine unsupported range вернуть existing unavailable с точным scipy_ttest_1samp_numeric_range reason, сохраняющим compatibility с IR prefix checks, и повторять ту же policy при fresh verification. Если требуется новая эквивалентная реализация, это явно другой method/version с reference acceptance; не обязательное условие данного ремонта. Обычный sample сохраняет реальный SciPy result.

**Честные описания и downstream уже реализованы.** Constant nonzero magnitude, UNKNOWN orientation, exact-zero point-fit, real backend identity и residual-only degradation сохраняются. Existing full CAS/C5b/packet regression нужно выполнить/расширить cancellation case, а не писать новый parallel validator. Native report binding и source rows остаются доказательной базой; kept marker не заменяет fresh recomputation.

**Floor и scientific scope:** `std<=1e-12` — нынешняя absolute numerical policy. DEC-SCALE выбирает либо явно ограниченный unit/range contract с accurate below_resolution reason, либо scale-aware numerical variance predicate/normalization. Смена одновременно затрагивает producer и IR availability check; old reason/version остаётся читаемым исторически. Не принимать tiny exact variance как scientifically trustworthy только после снятия floor. Metric orientation, dependence/effective n и multiplicity предоставляет selected study/metric owner, а не общий helper, угадывающий по residual sign.

### Текущие owners и источники

- [policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py:1542–1726](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/backtesting/orchestrator.py#L1542-L1726)
- [policy-engine/src/polisyos/ir/analytics/backtest.py:153–204](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L153-L204)
- [policy-engine/src/polisyos/ir/analytics/backtest.py:583–736](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/backtest.py#L583-L736)
- [policy-engine/src/polisyos/scientist/governance/backtest_matrix.py:172–322](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/backtest_matrix.py#L172-L322)
- [policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py:255–350](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/outcome_sections.py#L255-L350)
- [policy-engine/tests/unit/scientist/nodes/test_decision_packet_node_v3.py:4066–4622](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/nodes/test_decision_packet_node_v3.py#L4066-L4622)

## 6. Проверки: setup → действие → oracle

TEST-ID обозначает требуемую проверку, не существующий одноимённый pytest test. Расширять указанные действительные места, не дублировать suites.

### TEST-BKT-03-01 · native cancellation/permutation regression
**NOT_RUN. REQ:** REQ-BKT-03-01, REQ-BKT-03-02.
**Setup:** Actual evaluator rows для residuals[1e16,1,-1e16] и всех6 permutations, plus [1e16,-1e16,1]; Decimal exact oracle.
**Действие:** _detect_systematic_biases→BacktestReport→CAS→fresh verified projection.
**Oracle:** Mean/magnitude1/3, positive residual sign, nonzero descriptive card сохраняются при всех порядках; no metric diagnostic count/mean rejection. Statistical fields либо genuine reconciled SciPy result, либо explicit range-unavailable; false neutral и tolerance-based hiding запрещены.
**Место:** `tests/unit/remediation/test_bkt_03.py; ir/analytics/backtest.py::_assert_metric_diagnostics_match_scenarios`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-03-02 · native reduction/range consistency
**NOT_RUN. REQ:** REQ-BKT-03-01, REQ-BKT-03-02, REQ-BKT-03-07.
**Setup:** Cancellation corpus, constant huge finite residuals, tiny variance [-1e-14,0,1e-14], ordinary sample; BKT-02 range fixtures.
**Действие:** Producer numeric policy и independent IR/fresh recomputation; snapshot method/policy identity.
**Oracle:** Для supported range одинаковые counts/mean/sign/status. Overflow/underflow policy даёт typed limitation с useful rows, не exception/inf/fictional p. Tiny variance limitation не выдается за истинное отсутствие variability; chosen unit/scale domain указан.
**Место:** `tests/unit/remediation/test_bkt_03.py; shared numeric policy BKT-02`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-03-03 · native descriptive versus inferential matrix
**NOT_RUN. REQ:** REQ-BKT-03-03.
**Setup:** Residuals[10,10,10],[-10,-10,-10],[0,0,0],[0],[-1,0,1],[-1,3,3] и n2 sample.
**Действие:** Actual evaluator/aggregate/report roundtrip.
**Oracle:** Constant magnitude10, sign±, pNone/zero_variance, directionUNKNOWN; exact-zero отдельный status без backend identity. Balanced mean0 с MAE>0 не exact-zero; [-1,3,3] magnitude5/3, MAE7/3, не взаимозаменяемы. n2 insufficient_observations с сохранённым descriptive value.
**Место:** `tests/unit/remediation/test_bkt_03.py`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-03-04 · native SciPy reference + controlled faults
**NOT_RUN. REQ:** REQ-BKT-03-02, REQ-BKT-03-04.
**Setup:** [.5,1.5,2.5] и настоящий installed SciPy; отдельные controlled import denial/missing ttest/NaN p/out-of-range p/nonfinite statistic.
**Действие:** Actual _two_sided_ttest и независимый direct scipy.stats.ttest_1samp; serialize/validate result.
**Oracle:** Positive p≈.121690 и actual method/backend/version/statistic совпадают с direct reference. Fault branches pNone и точный reason, никаких normal-like .009375 под именем t-test. Rows/MAE1.5 и mean1.5 сохранены. Фикстурный fault не считается native отсутствием dependency.
**Место:** `tests/unit/remediation/test_bkt_03.py::test_small_sample_ttest_matches_scipy_reference; orchestrator.py::_two_sided_ttest`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-03-05 · native CAS/fresh statistical tamper controls
**NOT_RUN. REQ:** REQ-BKT-03-04, REQ-BKT-03-05.
**Setup:** Genuine saved report; по одному p=.009375, backend_version, bias-card p, diagnostic scope, mean/n, forged exact_zero; backend unavailable после записи.
**Действие:** Canonical load и actual fresh verifier, затем C5b summary.
**Oracle:** Forged source shape/scope/exact-zero rejected; stale statistical provenance снимает p/method и оставляет validated mean/magnitude. Unchanged ordinary control сохраняет вычисленный p с версией. Backend disappearance не теряет source rows и не возвращает positive trust.
**Место:** `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_c5b_fresh_backtest_binding_reaches_packet_and_rejects_kept_markers`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### TEST-BKT-03-06 · native full packet E02-I03-C
**NOT_RUN. REQ:** REQ-BKT-03-05.
**Setup:** Actual native selected report ref/manifest, C5b source, full BuildDecisionPacketNode; unchanged and stale diagnostic branches из TEST05.
**Действие:** Build/persist full packet и fresh read; inspect actual nested backtest section.
**Oracle:** Section имеет тот же recomputed mean/p/status/scope, stale pNone with explicit unavailable и mean1.5. Exact-zero trusted point-fit control проходит только при собственных verified bindings. Isolated section fixture не заменяет это свидетельство.
**Место:** `tests/unit/scientist/nodes/test_decision_packet_node_v3.py::test_s1_exact_zero_trust_recomputes_through_cas_c5b_and_packet`.
**Doubles:** Test tenant/inputs допустимы; selected loader, CAS/C5b, actual packet node и verifier не подменяются.

### TEST-BKT-03-07 · scoped numerical/scientific qualification
**NOT_RUN. REQ:** REQ-BKT-03-06, REQ-BKT-03-07.
**Setup:** Одна metric с documented units и orientation, тот же residual corpus в эквивалентных units; dependent repeated copies vs независимый declared design, multiple metrics; protocol before result inspection.
**Действие:** Методовый reviewer задаёт bounded assumptions/policy; actual diagnostic transport/readback проверяет labels и unresolved fields.
**Oracle:** Unit conversion не превращает tiny nonzero variance в доказанную zero variance. Без sufficient independence/effective-n/multiplicity/population basis остаются unresolved; sign costs не называется автоматически optimism. Поддержанная orientation имеет явный source/definition, unknown case сохраняет UNKNOWN и useful descriptive result. Научный вывод ограничен конкретным protocol, не synthetic software fixture.
**Место:** `MetricBiasDiagnostic / existing metric definition owner; DEC-SCALE/DEC-SCOPE`.
**Doubles:** Допустимы контролируемые входы и наблюдающая обёртка вокруг actual owner. Запрещена подмена принимаемого producer/consumer заранее готовым ответом.

### Запуск: адаптируемый шаблон, не выполненная команда

Из `policy-engine/` в поддержанной Python3.14 среде с закреплёнными зависимостями. Этот документ не разрешает автоматические installs; отсутствующая dependency означает BLOCKED конкретной проверки.

```bash
python -V
python -m pytest -q tests/unit/remediation/test_bkt_03.py
python -m pytest -q tests/unit/scientist/nodes/test_decision_packet_node_v3.py -k "s1_c5b_fresh_backtest_binding or s1_exact_zero_trust"
# Cancellation/scaled-domain cases добавить к действительному suite; native supported environment обязателен.
```

Фиксировать профиль/backend, inputs/seed/hash, deciding output и exit. Ruff и затронутые architecture/import checks выбирать по фактическому patch; native slot согласовать, полный suite на каждый пакет не копировать.

## 7. Общая интеграция и ownership

Переиспользовать **E02-I03-C**: [канонический контракт LANE-03](../03_Интеграция/LANE-03.md). Одно свидетельство связывается с конкретными вариантами и REQ; не считается многими независимыми подтверждениями.

BKT-03 владеет descriptive reduction и statistical backend result transport; IR/governance reviewers сохраняют independent reconciliation. BKT-02 координирует numerical-range changes общих файлов. Один E02-I03-C witness с full packet variants, без повторения тяжёлой CAS инфраструктуры.

- **BKT-02:** Один coordinated numerical-range/IR reconciliation contract; cancellation distinct from SSE overflow.
- **BKT-01:** Actual historical input и forecast/replica semantics до residual science.

## 8. Совместимость, миграция и возврат

Normal finite-range method outputs сохраняются. Cancellation исправление меняет ранее ошибочно neutral/нечитаемый result намеренно; старые persisted diagnostics не переписывать. Новый numerical-floor contract требует explicit version/profile handling и current recalculation; historical p не становится current по одному marker. Rollback сохраняет rows и делает только неподдержанный diagnostic unavailable; запрещено вернуть hidden normal approximation или loosen source verification.

## 9. Free-grow и обоснованные границы

- [universal-policy-design-target-architecture-and-gap.md — D0: typed meanings and reusable computation](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md): Общая numerical/diagnostic policy повторно используется для новой metric, но предметная orientation/dependence не придумывается helper.
- [wave5-evidence-substitution-ratification.md — K01, K07–K08](../05_Основания/Архитектура/wave5-evidence-substitution-ratification.md): Доступность вычисленного p не является evidence scientific assumptions или decision authority; useful descriptive work сохраняется отдельно.

## 10. Конечные решения и сдача

### DEC-BKT-03-SCALE
**Вопрос:** Сохранить ограниченный unit-domain floor или перейти к scale-aware predicate?
**Кто решает:** Numerical/statistical method owner.
**Конечное действие/выход:** Исполнить ordinary/tiny/unit-converted/cancellation matrix, выбрать policy по заявленному supported domain. Сдать exact predicate, reason semantics, version/read compatibility и зеркальную independent IR проверку. Не ослаблять floor без численной/научной аргументации.
**До решения:** Current floor остаётся явной numerical limitation, не доказанной zero variance; cancellation fix сдаётся независимо.

### DEC-BKT-03-SCOPE
**Вопрос:** Какие assumptions и orientation доступны для конкретного backtest?
**Кто решает:** Selected study/domain owner.
**Конечное действие/выход:** Зафиксировать metric definition/units, repeated-unit/time dependence, effective-n basis, multiplicity и population scope для одного intended claim. Недостающие поля перечислить конкретно; не требовать универсальной методологии всех будущих задач.
**До решения:** Descriptive magnitude/sign доступны, inferential/directional claims ограничены неизвестными основаниями.

Сдать base/head и patch, exact REQ→TEST→shared variant, исходные входы и их идентичности, actual команды/exit/log, независимые численные/семантические oracles, positive/negative/removal controls, сохранённые инварианты и открытые решения. Source-only, fixture, native и scientific qualification отражать отдельно. Не повышать partial/NOT_RUN до PASS; квалифицированный локальный механизм не является автоматической готовностью всей политики.
