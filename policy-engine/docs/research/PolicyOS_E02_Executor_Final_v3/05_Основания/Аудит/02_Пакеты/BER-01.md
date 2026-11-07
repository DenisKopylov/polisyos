# BER-01 — schema profiles и действительная identity объяснителя

**C120 · LANE-11 · LA-034, LA-036 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Persisted schema теперь воспроизводима из строгих DTO: полное содержимое совпадает с генератором, writer детерминирован, версия1.0.0 и обязательные wire fields отделены от удобного construction input. Actual orchestrator сохраняет requested names, вычисляет совместимые aliases один раз и не выдаёт их за независимые методы.

**6 MATCH; 22 unchanged test bodies:21 PASS,1 environment FAIL. C120-R01 (low):** отдельный public `validate_persisted_explanation_bundle_payload` всё ещё применяет permissive construction parse и может дать semantic pass для неизвестной wire version/omitted version/numeric string. Selected CAS loader защищён отдельно; обход нормативного admission не доказан.

## 2. Матрица исходных оснований

| ID | Исходный ремонт | Actual capability | Остаток |
|---|---|---|---|
| LA-034 | Устранить skeleton drift, разделить construction/persisted profiles и version policy. | Full equal-content и deterministic writer; empty nested/extra/unknown wire/default omissions различаются корректно. Selected loader проверяет manifest/version/required fields и strict JSON. | R01: public semantic persisted helper не применяет тот же wire intake. G01: native selected persistence/historical consumers UNRUN. |
| LA-036 | Requested/effective/fallback identity, один compatible raw calculation, честный unsupported и disagreement. | Actual kernel/marginal aliases имеют kernel_shap identity, call count не растёт; kernel-first tree alias раскрывает empirical fallback. Conditional request отвергнут до raw calculation. | Direct tree test падает на available3.12, supported3.14 не запущен. Alias-only display conservatism G02; confidence law сохранён. |

## 3. Producer → consumer

[DTO и generated persisted profile](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/contracts/schema.py#L16-L62) имеют одного структурного владельца. Schema pass не доказывает infidelity eligibility. [Selected persistence](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/persistence.py#L77-L199) сохраняет version/profile и применяет строгий JSON reader; эта цепочка прочитана, native не выполнена.

[Actual service](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/service/__init__.py) заменяет старый service.py. [Cache identity](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/service/cache_identity.py#L59-L109) включает model object/snapshot, input, background, typed params/constraints, law, confidence и evaluation setup. Cache локален одному explain. Custom adapters не получают automatic reuse без source-owned immutable identity. Bool/int/float key distinctions сохранены.

[Exact empirical kernel](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/adapters/shap_kernel.py) реально зависит от модели/background и сохраняет feature-count/empty-background guards. Conditional law не возникает из metadata; explicit refusal полезнее неверной conditional подписи. [Tree wrapper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/adapters/shap_tree.py) явно объявляет fallback, не новую TreeSHAP математику.

## 4. Проверки

| Проверка | Результат |
|---|---|
| P01 |22 unchanged selected bodies:21 PASS,1 direct TreeSHAP TypeError наPython3.12. Включены input/wire corpus, identity, guards, nonmutation, changed model/background/parameters/input, conditional refusal и confidence posture. |
| P02 | Kernel-only и kernel+ marginal+tree aliases дают одинаковое число real model calls. Requested names сохранены; effective kernel_shap один, disagreement=None, tree fallback раскрыт. Только kernel-first cache route. |
| P03 | Valid marginal control проходит semantic helper и wire schema.9.9.9, omitted schema_version и raw_score="8.0" helper принимает с passed=true, wire schema отказывает. |
| P04 | Unchanged Phase5 validation wrapper для9.9.9 возвращает passed/analyst_display. Это wrapper diagnostic, не native Phase5 или selected CAS admission. |
| P05 | При двух aliases и обоих bounds<.05 остаётся missing_disagreement_report; квалифицировано как консервативная policy boundary, не false acceptance. |
| P06 | Две actual writer outputs byte-identical; generated dict равен сохранённой1039-строчной schema. Tooling здесь Pydantic2.13.4. |

[Probe](../04_Проверки/C120_BER01/probe_ber01.py) · [наблюдения](../04_Проверки/C120_BER01/run02/observations.json) · [команды и обе попытки](../04_Проверки/C120_BER01/commands.json) · [границы](../04_Проверки/C120_BER01/Чтение_и_границы.md).

## 5. Остаток и что сохранить

**C120-R01 — разный intake persisted helper (low).** [Public helper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/contracts/validation_rules.py#L105-L130) использует `model_validate`, тогда как wire reader требует known version, explicit required fields и strict JSON. [Phase5 wrapper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/validation/phase5_preflight.py#L1222-L1247) проецирует semantic result. Согласовать существующий intake или явно разделить construction diagnostics/persisted API; не создавать третью schema. [Runtime reliability](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/explanation_reliability.py#L638-L687) сначала использует строгий selected loader, а inline значения остаются candidate diagnostics. Поэтому R01 не означает принятие неизвестного wire в защищённом CAS пути.

**C120-G01 — поддерживаемый runtime/consumer.** Public facade import блокируется Core3.14 syntax на3.12; pytest отсутствует. Leaf service действительно выполнен, но package shell обходит facade; native CAS/Phase5/UI/historical records не проверены. Direct tree failure соответствует известной границе [dataclasses3.12](https://docs.python.org/3.12/library/dataclasses.html); [CPython PR124455](https://github.com/python/cpython/pull/124455) меняет этот механизм. Это объяснение, не доказательство успешного3.14 run. Переписывать product backend ради unsupported interpreter не требуется.

**C120-G02 — alias-only display.** Actual gate требует disagreement при requested-count>1, хотя producer корректно не сравнивает один effective estimator с самим собой. Нужна явная policy qualification; не фальсифицировать comparison и не менять Bonferroni claim budget из-за dedup. Existing confidence test специально сохраняет более строгую posture двух claims.

Сохранить BERL kernels/benchmarks, synthetic labeling, strict nested DTO, historical requested IDs, explicit fallback, unsupported conditional refusal, selected profile guards и локальный bounded cache. Никакой эмпирической валидности реальной политики из линейного fixture не следует; универсальный deterministic inventor conditional laws не требуется.

[Карточка](../05_Источники/BER-01_исходные_строки.txt) · [pinned sources](../05_Источники/C120_источники.json) · [остатки](../01_Реестры/C120_остатки.json).

**120/127. Следующий DDM-01; осталось7 пакетов. Фаза заданий исполнителю ещё не начата.**
