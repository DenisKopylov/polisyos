# SCM-02 — factual abduction и две стороны attribution
## C58 · 1 ноября 2026 года

**Порядок:** 58/127, LANE-05. **Исходные ID:** B215, B223. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит, свежий проход после внешнего сохранения C57.

## Решение

Основные исправления действуют: частичный linear-Gaussian factual input даёт условный закон noises, полный factual input сохраняет точную residual-инверсию; target и comparator представлены отдельно, observational baseline не смешан с do-zero. **Однако подтверждены два остатка:** C58-R01 уничтожает ненулевую posterior variance при малом масштабе; C58-R02 фиксирует observed empirical root, не condition-ируя общий root-row carrier, и помечает такой результат exact.

**10 bounded MATCH, 17 unchanged test bodies /17 cases PASS изолированно.** MATCH включает воспроизведение дефектов, не product PASS. Native registry/CAS/Scientist/ensemble и source-bound refit не исполнены; все общие envelopes в проверенных запросах остаются non-gating.

## 1. Матрица требований

| ID | Требование | Что реально подтверждено | Остаток |
|---|---|---|---|
| B215 | Не считать model-imputed parent observed; partial Gaussian posterior и full factual control | P01–P03: аналитический oracle, actual query/twin; unsupported profile получает limitation | R01 scale collapse; R02 joint empirical conditioning; G01/G02 |
| B223 | Target/comparator, no override vs observational; shared-U semantics и сохранённые arms | P01/P08–P10: explicit do-zero, natural, identical и stochastic arms; typed JSON и metadata conflict refusal | G01 native producer/reader/ensemble; G02 estimand/science |

Полная карточка SCM-02 прочитана. Ни исправленный интерфейс, ни synthetic examples не устанавливают эмпирическую причинную идентификацию.

## 2. Что исправлено в factual Gaussian chain

Owner строит affine map от independent noises к nodes, затем condition-ит Gaussian joint по действительно observed rows. Он не присваивает imputed parent статус наблюдения. Empirical residual samples, polynomial payload и неподдержанные families не принимаются за Gaussian. При невозможности exact fallback сохраняется явная limitation/non-gating metadata. [S01:788–990](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L788-L990)

**P02:** X=Ux,Y=X+Uy,Ux,Uy~N(0,1), evidence Y=2. Независимый closed-form oracle: posterior mean(U)=(1,1), covariance=[[0.5,−0.5],[−0.5,0.5]]. Actual helper совпадает; actual query do(X=0),4096 draws даёт mean=**0.9984346**, variance=**0.4925374**, а не исходные2/0. **P03:** полный X=1,Y=2 даёт Y(0)≈1 с roundoff-level std; impossible factual Y=2 в deterministic zero model отвергнут.

Unchanged tests дополнительно проверяют twin shared posterior noises, fully observed empirical-root residual fallback, limited partial unsupported model и отказ объявлять twin empirical factual root exact. Полезные limited candidates сохраняются; общий envelope всё равно не выдаёт scientific gate authority. [S06:175–391](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_scm_02.py#L175-L391)

## 3. C58-R01 — scale-dependent потеря posterior randomness

**Средняя серьёзность; высокая уверенность в bounded numerical profile.** `_draw_linear_gaussian_noises` считает covariance нулевой по `allclose(...,atol=1e-12,rtol=0)` и возвращает один posterior mean вместо random draw. Порог выражен в абсолютных единицах covariance. [S01:993–1015](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L993-L1015)

**P04:** тот же Gaussian control в масштабе s=10⁻⁷, evidence Y=2s. Actual conditioning корректно даёт Var(Uy|Y)=**≈5·10⁻¹⁵**, но все4096 draws имеют одно значение. Actual std≈**2.65·10⁻²³** — roundoff от повторения одной точки; аналитически требуется **7.071·10⁻⁸**. Нормализация единиц должна сохранять std≈0.707, как положительный s=1 control, а не давать0.

**P05:** тот же shared draw owner переносит collapse в twin potential-outcome marginal. ITE в этом linear same-noise control действительно deterministic; ошибка относится **не** к ITE std, а к ненулевой conditional variance отдельного counter-world. Envelope non-gating снижает authority-риск, но не исправляет неверную симуляцию.

Минимальное направление: различать доказанно deterministic/singular structure и numerically small-but-nonzero covariance, применять scale-aware admission/PSD handling на существующем shared owner. Сохранить exact full-factual и incompatible-evidence controls; проверить обе sibling consumers при unit rescaling.

## 4. C58-R02 — root pin нарушает условный joint empirical law

**Средняя серьёзность; высокая уверенность в finite declared-carrier profile.** Sampler выбирает общий observed-root row без conditioning, затем observed non-descendant root напрямую перезаписывает factual value. Exact-fallback classifier разрешает такой root и не проверяет conditional dependence с другими empirical roots. [S01:788–821](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L788-L821) [S01:1371–1464](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1371-L1464)

**P06:** actual SCM DTO содержит joint rows (W,Z)={(0,0),(10,1)}; Y=T+W, запрос do(T=0), factual Z=1. У заданного finite joint law единственный подходящий row имеет W=10, поэтому oracle Y=10,std0. Actual query даёт **mean4.990234375,std4.99999046** и создаёт невозможную пару **(W,Z)=(0,1)**. Metadata: `exact_residual_fallback`, `abduction_gate_eligible=True`, без warning; overall envelope по общему правилу остаётся False.

**P07** отделяет дефект от carrier storage: unconditional path правильно сохраняет только исходные пары. Ошибка появляется именно при factual conditioning, не из-за неверно изготовленного DTO и не из-за отсутствующих данных. Этот контроль использует явно объявленную joint empirical law; он не доказывает идентификацию такой модели в реальных социальных данных.

Минимальное направление: condition общий row selection по evidence в поддержанном finite profile либо явно признать unsupported limited posterior/отказать. Не подменять evidence интервенцией и не маркировать exact на основании известности одного root. Сохранить unconditional joint sampling и реально exact full-parent residual controls.

## 5. B223: явный контраст действительно проходит до результата

Canonical `CausalContrastSpec` хранит target InterventionSpec и tagged comparator regime. Legacy attribution нормализуется к явному observational comparator; missing atomic value/malformed stochastic law и противоречащие tags отвергаются. Sentinel различает отсутствие override от явного None=observation. [S03:110–316](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_queries.py#L110-L316) [S01:1020–1038](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1020-L1038) [S01:1315–1354](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/gcm_query.py#L1315-L1354)

**P08:** при natural root mean4 и Y=3X+Uy explicit target X=2 /do-zero comparator даёт **6**; natural comparator даёт≈**−5.947**; одинаковые explicit arms — ровно0. Structural noise переиспользуется для common-world ITE: в fixed linear do contrast std≈0, а не variance двух независимых arm means. Existing stochastic-policy test исполняет разные uniform arms и сохраняет обе typed laws.

**P09:** actual result JSON roundtrip сохраняет target/comparator; подмена metadata comparator при прежнем query отвергнута. `CausalQueryResult` и envelope bridge выводят arms из typed query, не доверяют произвольному тексту. **P10:** legacy raw DTO нормализуется к current1.2, но не получает manifest-bound source provenance. Это JSON validation, не native persisted replay. [S03:457–583](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_queries.py#L457-L583)

## 6. Producer/consumer, native и scientific пределы

Source-only tracing показывает actual query node: load/validate SCM → bound method job → whole canonical output/aliases/request reconciliation → typed result persistence → собственное построение envelope. Ensemble source сравнивает canonical arms до aggregation и переносит limitations участников. Эти owners прочитаны, но не выполнены с fake store ради PASS. Existing native tests используют настоящий CAS, но часть job producers в них специально mocked; и эти tests здесь UNRUN. [S07:153–200](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L153-L200) [S07:252–393](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_queries.py#L252-L393) [S08:657–680](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py#L657-L680) [S08:798–824](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py#L798-L824)

**C58-G01:** нужны supported Python3.14 native request/result/manifest/fresh-reader/Scientist/ensemble checks и actual worker/custody там, где это требуется. Pytest отсутствует; ordinary import под3.12 останавливается на Python3.14 syntax. Это ограничение среды, не product defect. Actual persistence owner имеет exact source tuple/current schema и отдельный legacy adapter, но local DTO roundtrip не подтверждает его весь. [S03:596–753](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/ir/analytics/causal_queries.py#L596-L753)

**C58-G02:** fixed-model outcome/ITE/conditional distributions не estimator sampling CI. **Refit bootstrap в C58 не запускался и не считается автоматически задачей SCM-03**: следующая карточка про active query-plan/stochastic law. Source-bound refit/coverage qualification остаётся открытой отдельно. General nonlinear posterior и causal graph/assumption admission также не установлены; не требуется универсальный deterministic inventor вместо LLM semantic proposer.

## 7. Сохранить и остаток

Сохранить ordinary Gaussian posterior, exact factual control, явные unsupported limitations, typed two-arm contrast, shared-U semantics и conservative envelopes. Исправлять конкретно shared draw threshold и conditional joint-root handling, расширяя существующие owners. Не возвращать исходное imputed-as-observed поведение и не запрещать все useful partial models.

17 unchanged bodies исполнены с минимальными approx/raises, не pytest runner. Первые два внешних probe failures вызваны bitwise float expectations; исходные probes/logs сохранены, скорректирована только диагностическая tolerance. Distinct-value control R01 остаётся точным; numerical error не скрыт. Финальный exit0; repo clean, installs/исходных edits/сервисов нет.

[Диагностика](../04_Проверки/C58_SCM02/bounded_diagnostics.json) · [Команды](../04_Проверки/C58_SCM02/commands.json) · [Границы](../04_Проверки/C58_SCM02/native_verification.json) · [Источники](../05_Источники/C58_источники.json) · [Остатки](../01_Реестры/C58_остатки.json).

**58/127 пакетов рассмотрены ограниченно; 136 уникальных B/LA частично оценены. Следующий — SCM-03. Полного закрытия нет.**
