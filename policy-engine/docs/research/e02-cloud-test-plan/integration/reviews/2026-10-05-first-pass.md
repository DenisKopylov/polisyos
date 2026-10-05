# G: независимая приёмка первых slices

Это review по immutable Git objects, не назначение G владельцем bundles и
не closure findings. Base — `c40d4acae1ce58b597267255026d9356565828fd`.
Новые upstream commits принимаются после delta/dependency/evidence review.
Owners получают этот record через fetch `codex/e02-integration`.

## Решения, требующие canonical owner

| Slice / inspected head | Решение и distinguishing case | Следующее доказательство |
| --- | --- | --- |
| B RUN / `6e9be8959d7ff26efa9f2b4db81d308a506d04db` | **HOLD new executor delta.** `submit` удерживает admission lock до `super().submit`, который берёт shutdown lock. Concurrent `shutdown(cancel_futures=True)` удерживает shutdown lock и через inline cancellation callback берёт admission lock. Отдельный escape: future завершён и counter уменьшен, но worker ещё выполняет user callback; все workers могут принять nested jobs и ждать друг друга. | Убрать lock inversion; измерять фактическую доступность workers либо определить поддерживаемую границу. Детерминированные submit/shutdown, callback saturation и spare-worker positive controls. Reviews: consumer_a, edge_cycle_forecast; эти counterexamples пока static, локальные probes pending. |
| B CAS / `36bc2f72f8cc8dab5c1aa2a51740f5945b1143f6` | **HOLD path-boundary acceptance.** Для regular destination publication ordering и reopened archive consumer поддержаны. `stat` читает mode symlink referent, а `replace` заменяет сам alias. Archive path не имеет directory-path symlink refusal. Source formatter также FAIL; четыре CAS02 failures сохранены, не названы inherited. | Canonical CAS owner определяет symlink/special-mode boundary и добавляет probe с реальным alias. Сохранить старый package и честный replaced status при отказе. Reviews: consumer_d, edge_connector_ingest. |
| D RL / `84b786676894f677ace14ed74183e0156245f5d0` | **HOLD strict checkpoint admission.** `checkpoint_version != 1` принимает `True` и `1.0`. Локальные реальные RL/random/Sobol tests: 27 PASS на SciPy path; это не falsifier malformed version. Changing decay/history replay и production persisted caller не установлены. | Один typed version decoder; missing/boolean/fractional/unsupported controls без mutation. Меняющийся schedule с восстановленной evaluation history и repeated restart. Reviews: consumer_d, edge_connector_ingest. |
| D transfer / `91f45ad8024554656238b67f6d32719a953d01e7` | **HOLD complete reader-generation claim.** `dim` читает поле вне generation lock, load публикует `_dim` до index swap. Текущий query barrier допускает descheduled reader и не доказывает попытку lock acquisition. Snapshot-copy/CAS/cache repair поддержан отдельно. | Consistent public generation boundary и deterministic overlap; либо owner объявляет bounded scope и исполняет его falsifier. Native local probe pending. Distributed atomicity и live provenance остаются отдельными held/input residuals. Reviews: consumer_f, consumer_e. |
| D GP witness / `9b1a319a48fd5739065d5d0114dadfa62deef5b9` | **HOLD ordinary-unit-test integration.** Candidate `052e763…` меняет только tests; baseline 4 FAIL / 3 PASS — полезный witness. Новые 7/7 logs используют другой source snapshot, который не связан delivered Git ancestry/tree/diff. Future refit clock mutation остаётся admitted. | Передать canonical implementation SHA/tree и complete diff, затем повторить прежний witness и admission controls. Не превращать red unit tests в green через ослабление checks. B114 provenance/replicas и B115 continuation — раздельные predicates. Reviews: edge_cycle_forecast, surface_audit. |
| E DDM facade / `25f92860db509525f8e7d829ff060bed675ae154` | **HOLD ABI coverage change.** Условие `if name in ddm.__all__` позволяет удалить прежний root export вместе с declaration и оставить test green. Реальный consumer `scientist/governance/continuous/detectors/fairness.py` импортирует root events; receipt говорит, что non-test consumers не найдены. | Сохранить независимый prior/public root surface oracle и run affected drift-detector consumer; исправить caller census claim. Neutral import trap и pickle-class checks полезны отдельно. Review: consumer_b. |

P40 buckets: B callback case — существующий capacity-proxy class глубже;
B shutdown — новый lock-order class; CAS alias — path identity class;
D RL — checkpoint corruption; D transfer — generation reader exclusion;
DDM — consumer-facing facade coverage. G не пишет исправления в эти owners.

После static review выполнены изолированные runtime probes на прежних exact
candidates, без изменения mechanism. [B shutdown output](../checks/b-executor-shutdown.txt)
доказывает конкретный wait cycle и успешный non-inverted probe-only control.
[B callback receipt](../checks/b-executor-callback.json) фиксирует четыре занятых
callback workers при counter=0, accepted nested jobs без исполнения; контроль
с одним свободным worker и accounting/cancellation controls проходят. Этот
probe не устанавливает существующего PolicyOS callback consumer.
[D native receipt](../checks/d-transfer-native.json) содержит реальный hnswlib
0.8.0: 14 transfer/vector/TRN-02 и 10 warm-start tests проходят, а `dim`
возвращает новую размерность до публикации keys; query ждёт завершения swap.
[D RL observations](../checks/d-rl-admission.json) подтверждают приём `True`
и `1.0`; missing/unsupported version и malformed outer/Python RNG отвергнуты
без mutation. В текущем decoder нет `metadata.wrapped_rng_state`: отдельный ранний AttributeError относится к nested `metadata.base_state`, а не к Python RNG codec. Эти probes проверяют outer/Python RNG; nested-base delta рассматривается на source `4030275…` со старым, не обновлённым handoff.
Все четыре HOLD сохраняются. Full moderate deciding outputs находятся в Git;
probe scripts остаются локально ignored и связаны hashes, remote bytes не
переданы.

## Bounded code/evidence acceptance candidates

D baseline map принят как navigation/census artifact в checkpoint-01, без
product closure. B TypeVar cleanup `418b1f0…` рассмотрен отдельно от нового
executor delta: 10 local tests, Ruff check/format и exact-base negative control
прошли. Cleanup принят в checkpoint-02 с [полным receipt](../checks/b-typevar.json).
Новая LA-057 closure не заявляется; external/dynamic callers и
packaging/typecheck broader scope остаются ограничениями.

E bootstrap, E FRC, F CAU, F API ABI, F FRY и F Lex имеют положительные
bounded reviews; финальная code admission ещё требует G readback/receipts и
обязательных checks. Bootstrap interval discriminator пока совпадает для
mean/median; seed-changing oracle нужен для interval criterion. FRC producer
binding не устанавливает source time/context или A-owned served bridge.
CAU scalar anticipation/missing-baseline repair не валидирует весь timing
array и не закрывает multi-cohort inferential calibration. F API preserves
its bounded source facade; ranking red и installed-package applicability
остаются открыты. FRY salt/layout artifacts не доказывают salt consumption.
Lex synthetic input-binding не доказывает admitted law, valid time или
authority-grade public projection. F economic mixed-profile run остаётся
FAIL, candidate attribution пока не установлена.

## Входы и closeout

Results importer/corruption controls принимают transferred text/index binding.
VM raw archives отсутствуют. Большие invocation receipts не переданы и имеют
`runtime_invocation_established=false`; они не являются доказательством
отсутствия production caller. Source PASS и route candidates не закрывают
findings. Все новые finding closure decisions пока пусты.

Production остаётся локально read-only и используется только по criterion.
DoWhy/EconML/Temporal и real GP backend в текущих G snapshots недоступны.
Локальный общий heavy slot не запущен; cloud B/D/E/F этим не ограничен.
Freeze не объявлен, broad regression/data-dependent closeout остаются UNRUN.
Push в main не разрешён.
