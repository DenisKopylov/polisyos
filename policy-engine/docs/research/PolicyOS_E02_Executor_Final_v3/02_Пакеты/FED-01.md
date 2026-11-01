# FED-01 — Численно допустимая композиция с настоящим cell lineage

**LANE-07 · CP2 · B138, B140, B141, B145 · fix + preserve + native/use qualification.**

**Практическая цель:** Три и более источника объединяются без потери роли каждой ячейки, ошибочного увеличения grain или превращения конечного среднего в inf.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/FED-01.md) · [остатки C89](../05_Основания/Аудит/01_Реестры/C89_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/FED-01_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 не доказан как bypass downstream finite ObservationRecord. Numerical mini-calculator не native product acceptance.

## 2. Сохранить работающий смысл
- Owned cell basis и selected-parent replay
- Bounded explicit join cardinality/null semantics
- Collision-free internal aliases
- Participant/exclusion/absence evidence
- Candidate limits и finite helper

Защищённые различения: LK04. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C89-R01: fix** → REQ-FED-01-01. Stable numeric point calculation и final finite admission.
- **C89-R02: fix** → REQ-FED-01-02. Policy validity перед singleton shortcut.
- **C89-G01: qualify** → REQ-FED-01-03, REQ-FED-01-04. Native selected artifact и actual opt-in acquisition/consumer.
- **C89-G02: qualify** → REQ-FED-01-05. Concrete-use facts отдельно от программной lineage; conditional path полезен.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-FED-01-01
Numeric CONSENSUS mean/even median должен вернуть конечный representable point result без intermediate overflow и без потери representable subnormal/cancellation результата; проверка finite результата выполняется до publication. Participants/exclusions/absence и categorical mode сохраняются.

**TEST-FED-01-01 — native unit / integration; NOT_RUN.**
- Setup: Finite [1e308,1e308], [10,14], mixed signs, minsubnormal pairs и [1e308,-1e308,3*ulp(0)]; partial [10,14,inf,bad,null].
- Действие: Actual consensus→selected artifact persist→fresh replay; independent exact binary-rational oracle. Квалифицировать narrow wrapper со statistics.mean на supported CPython3.14 и сопоставить с независимым Fraction oracle; добавить перестановки и representative group-size cost/allocation profile. Expected не вычислять тем же statistics.mean.
- Точный oracle: Mean/median первых двух 1e308, ordinary12; cancellation mean=ulp(0), midpoint(minsub,2minsub)=2minsub при round-to-even. Partial12 с participants2/excluded2; invalid point не published. Old pandas aggregation inf различается.
- Doubles/границы: Exact rational calculator только независимый oracle, не product test. Настоящие composer/artifact/reader обязательны.

### REQ-FED-01-02
Strict scalar MEDIAN должен проверить numeric validity до single-effective-candidate shortcut: inf/bad не проходят как single_source, null остаётся absence. Resolver выбирает существующего producer, CONSENSUS создаёт aggregate; FIRST_AVAILABLE/TRUST не меняются этой проверкой. Scalar even median обязательно использует common finite_binary64_midpoint; current np.median overflow не должен менять выбранного producer. Preserve stable tie/closest-source policy, не aggregate.

**TEST-FED-01-02 — native unit / integration; NOT_RUN.**
- Setup: [inf,None], [bad,None], [10,None], two finite candidates; strict/non-strict и разные policies. Phase2 source-backed additional case [2,1e308,1e308,1e308] and permutations with fixed source identities.
- Действие: Actual ConflictResolver.resolve и numeric CONSENSUS.
- Точный oracle: Strict MEDIAN invalid отказ; valid10 выбран с настоящим source; обычные policies сохраняют объявленный смысл. Numeric consistency не превращает aggregate12 в одного producer10/14. Finite scalar target1e308 selects a genuine1e308 producer, not2; existing tie policy retained. Not a retroactive phase1 R or claimed native run.
- Doubles/границы: Нельзя глобально запретить categorical values или менять trust policy для прохождения теста.

### REQ-FED-01-03
Owned cell lineage, cardinality/null/row-budget admission и collision-free names должны сохраняться через вторую композицию и selected-parent persistence/reopen. Declared bounded many-to-many остаётся доступным.

**TEST-FED-01-03 — native unit / integration; NOT_RUN.**
- Setup: Ahigh[10,null], Blow[null,20], Cmedium[100,200], настоящий __source_id/x_left; repeated/null keys и explicit row budget.
- Действие: JOIN/OVERLAY→persist→independent fresh parent registry→второй JOIN; все 4 strategies имён.
- Точный oracle: Итог[10,200], origin20=B до сравнения; forged/mutated attrs не заменяют owner basis. Default duplicate-right refused before merge; explicit bounded m:m valid; nulls не совпадают без flag; реальные имена/значения сохранены.
- Doubles/границы: Нельзя fake lineage/replay или dedupe реальные occurrences; equal-priority order semantics не менять.

### REQ-FED-01-04
Native opt-in acquisition должен передать frozen request/captured sources в actual federation artifact owner, получить typed receipt и независимо открыть его; candidate limits сохраняются при useful composition.

**TEST-FED-01-04 — native unit / integration; NOT_RUN.**
- Setup: Controlled connector, real service/facade/native Python3.14, Parquet и selected artifact filesystem.
- Действие: fetch_federated→persist→fresh intake→second composition/SQL where declared.
- Точный oracle: Valid combined data доходит до actual consumer; real parent hashes/ref/profile связаны. Service result не становится verified/current/source-independent по одному replay; corrupt/foreign parent refused.
- Doubles/границы: Нет production network; controlled connector allowed, fake artifact/CAS/native format запрещён.

### REQ-FED-01-05
Для конкретного stronger use declared grain/unit/source scope/version/independence должны иметь предметное основание либо явное unknown. Недоказанные issuer/currentness факты не запрещают software_derivation_candidate, но ограничивают соответствующий claim.

**TEST-FED-01-05 — native unit / integration; NOT_RUN.**
- Setup: Candidate fixture и фактически доступные concrete-use source declarations.
- Действие: Сопоставить contract facts с evidence; выполнить valid conditional composition.
- Точный oracle: Каждый stronger claim имеет witness либо withheld; identity/replay не выдаётся issuer truth. Erased copy лишь новый limited candidate, не восстановленная history.
- Doubles/границы: Не invent source corpus, universal provenance platform или deterministic semantic model inventor.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/fabric/connectors/federation/composer.py` numeric consensus сейчас вызывает pd.Series.mean/median после finite input classification. Согласованный owner — **новый предлагаемый** `src/polisyos/common/numeric_reductions.py`: `finite_binary64_mean` и `finite_binary64_midpoint`; FED-01 sole writer, UQS-01 consumer, без Fabric→Scientist import. Предпочтительный первый production candidate — узкий finite Python-binary64 wrapper над stdlib `statistics.mean`; midpoint двух sorted central values через тот же mean, odd median — actual central value. CPython3.14 `mean` использует exact integer-ratio accumulation и final total/n conversion; квалифицировать это на locked runtime независимым rational oracle, не полагаться только на имя функции. НЕ использовать `statistics.fmean` или `statistics.median` как автоматическую замену: их sum/even-midpoint semantics не закрывают этот extreme/subnormal contract. Собственный scaled-integer accumulator остаётся допустим только при документированной correctness/performance причине; Fraction — прозрачный независимый reference, не обязательный объект на каждой production строке. Нет новой dependency. Finite guard до point publication обязателен; all-invalid остаётся absence, categorical mode и actual-cell scalar MEDIAN не меняются.

Допустим оптимизированный scaled/compensated путь после численной квалификации и измерения. Формула только `m*(fsum(x/m)/n)`, не `m*fsum/n`; однако scaling может уничтожить крошечный остаток после cancellation. Independent calculator автора (не product run) показал [1e308,-1e308,3*ulp(0)] →0 при scaling и exact mean=ulp(0). Не объявлять такую формулу универсальной. Не заменять even median на `(a+b)/2` или безусловное `a/2+b/2` — соответственно overflow/underflow. Scope helper — float64 point aggregation после existing admissibility, не universal real arithmetic engine.

`src/polisyos/fabric/connectors/federation/resolver.py::ConflictResolver.resolve` должен dispatch MEDIAN validation до singleton shortcut, используя `_resolve_by_median`/общую classification. Сохранить non-strict fallback и source-selection semantics. В `_resolve_by_median` использование common `finite_binary64_midpoint` для двух sorted central finite values **обязательно**, а не опционально: current np.median может дать inf на [2,1e308,1e308,1e308] и последующий closest/min выбирает 2. Odd median — actual central value; перед nearest-source selection проверить finite target. Сохранить existing stable tie/closest-source policy и result producer identity, не превращать scalar resolver в aggregate. Это source-backed дополнительная проверка phase2, не новый ретроактивный phase1 R. Независимый NumPy calculator подтвердил арифметический контрпример, но не объявляется полным product execution.

`src/polisyos/fabric/connectors/federation/composer.py::_join/_overlay`, owned cell basis и `src/polisyos/fabric/connectors/federation/artifact.py` selected-parent replay уже исправлены: preserve plus native tests. `fetch_federated` consumer bridge проверяется actual вызовом, не только прямым composer. Shared composer changes согласовать FED-02 одним writer.

Библиотечное основание выбора: [CPython v3.14.0 statistics.py](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py), `mean`/`_sum` и отличие `fmean`/even `median`, проверено2026-11-01. Source inspection не native product PASS; actual target qualification остаётся NOT_RUN.

## 6. Общая интеграция и порядок
**E02-I07-B**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- FED-02 shares composer/resolver mutex; UDF-05 общий E02-I07-B
- Не переносить numeric requirements в новый общий provenance owner

Owners/callers: `src/polisyos/fabric/connectors/federation/composer.py`; `src/polisyos/fabric/connectors/federation/resolver.py`; `src/polisyos/fabric/connectors/federation/artifact.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Old persisted inf derivations не переписываются. Новая numerical rule получает фактическую version/derivation binding; old replay поддерживается как historical qualified rule либо явно unavailable, не молча recompute с новым правилом под старым hash. Fix не изменяет categorical mode/FIRST_AVAILABLE. Rollback не разрешает invalid point publication; affected numeric claim ограничивается, valid composition сохраняется.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

[North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md): алгоритмическая воспроизводимость не scientific admissibility. Существующая declared source semantics достаточна для полезной candidate композиции; отсутствие независимости измерений не превращает весь composer в бесполезный helper.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/fabric/connectors/test_federation.py`, `tests/unit/fabric/connectors/test_federation_artifact.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.

## 10. Shared numeric owner и стоимость
С UQS-01 согласован один lower-level owner: **новый предложенный**, ещё не существующий `src/polisyos/common/numeric_reductions.py` (`finite_binary64_mean`, `finite_binary64_midpoint`). FED-01 один writer, UQS-01 consumer. Existing `src/polisyos/fabric/numerics/finite.py` остаётся validation owner (LK04). Сначала квалифицировать stdlib CPython3.14 `statistics.mean` и measured representative group cost; custom exact accumulator либо optimized fast path допускается по явной correctness/performance причине и с correctness-preserving fallback. Одного finite-result check недостаточно: он пропускает zero после cancellation. Не требовать Fraction на каждой production строке, не импортировать Fabric в Scientist и не менять law/provenance semantics. Independent reference и target runtime measurement обязательны, выдуманного SLO нет.