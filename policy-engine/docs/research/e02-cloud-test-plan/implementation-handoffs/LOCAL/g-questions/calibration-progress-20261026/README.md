# N2.calibration.foundry: смысл CalibrationStuck

26 октября 2026. Author proposal для G; `architecture_selection=proposed_for_G`, `code_acceptance=false`, `closure_ids=[]`. Это один новый вопрос о progress alert. Решение G25 по availability и dependent operational coverage исполняется независимо.

## Что требуется выбрать

Сохранить ли CalibrationStuck только как диагностический сигнал до появления настоящего lifecycle consumer, либо требуется alert о прогрессе **той же активной калибровки**? Если alert требуется, выбрать смысл «loss не уменьшается»: изменение между концами окна (`delta`) или линейный тренд по всем наблюдениям (`deriv`).

Рекомендация исполнителя — диагностический статус до появления связанного execution consumer. Это не предложение закрыть expiry, убрать обязательство или назвать текущую ошибочную query корректной. Если G выбирает progress alert, исполнителю остаются реализация identity/cleanup, ограничение cardinality, orchestration bridge и проверка producer → metrics → native alert engine → consumer; выбор B/C способов хранения состояния не нужен от G.

| Выбор G | Наблюдаемая семантика | Последствие |
| --- | --- | --- |
| Диагностика | Latest loss/история конкретного расчёта не обещают обнаруживать stuck execution | Согласовать alert/runbook/dashboard и отразить неполноту progress capability; availability работа продолжается |
| Alert: endpoint | Активная калибровка не улучшила loss между концами 30-минутного окна | Проверить `delta >= 0` только на её собственной истории, с существующим 30-минутным hold |
| Alert: trend | Активная калибровка имеет неотрицательный линейный тренд loss за окно | Проверить `deriv >= 0` на её собственной истории, с тем же hold |

Эти два смысла различаются: четыре наблюдения через 10 минут `1.0, 1.0, 10.0, 0.9` дают endpoint change `-0.1`, но положительный least-squares slope. Это арифметический discriminator, не новый native Prometheus receipt. Порог, окно и hold этим пакетом не меняются.

## Доказанная граница текущего source

`Calibrator.run()` создаёт collector с `optimizer=adam` до multi-start цикла. GaugeProxy хранит последнее значение по optimizer; `finalize()` не удаляет его. Две калибровки с тем же optimizer разделяют ключ. `polisyos_active_runs` — unlabeled счётчик активных Scientist workflows, который не устанавливает принадлежность к калибровке. Нынешний alert применяет `increase()` к loss gauge и default vector matching к этому счётчику.

Per-start `calibration.run` span и `calibration.start_index` уже существуют. Декларация `calibration.run_id` в component observability не является runtime producer: source census по всем 2 815 tracked `.py` файлам в `policy-engine/src/polisyos` на pinned commit не нашёл Python emission `calibration.run_id` или `calibration_run_id`. Не создавать authority из декларации.

Native Prometheus 2.50.0 проверил actual source rule и RAW counterfactual (`delta` + `and on()`) на 61 минутном sample loss=2.0 с optimizer=adam и active_runs=1 без labels. Canonical rule не firing; counterfactual firing после сохранённого hold. Полный deciding stdout:

```text
Unit Testing:  /tests/calibration-lifecycle-promtool.test.yml
  SUCCESS

```

Точный argv, image/daemon/mount/input hashes, полный stderr и source readback находятся в [inputs.json](inputs.json) и указанных там RAW outputs. Все product pins совпадают с опубликованным source `8f975da9c484f42bb2ef7c851ea3d5081e9124d4`; tooling WIP этой семантики не меняет. Контейнер: Linux/aarch64, 1 CPU, 512 MiB, network none, RO root/binds, tmpfs 64 MiB. Full Calibrator/JAX producer и deployed exporter этим запуском не проверены.

Одни и те же наблюдения совместимы с двумя мирами: активная flat калибровка, либо уже завершённая калибровка с retained loss плюс другой активный Scientist workflow. Actual GaugeProxy + OTel helper witness подтвердил retention, last-writer replacement и remove_matching. Он не доказывает deployed concurrent Calibrator execution. Поэтому исправление одного PromQL operator/join не устанавливает необходимое current-execution predicate.

## Binding, companions и независимая очередь

Вопрос относится к `N2.calibration.foundry`, состояние `consumer_missing`: определить Foundry run owner и смысл progress/stuck. Canonical Ops row — `ops/components/index.toml`, component `calibration`, owner `team-foundry`, expiry `2026-08-01`. Component observability и runbook coverage — зеркала; package exception `calibration-standalone-slo-deferred` принадлежит `team-scientist`. Exact selectors и file hashes приведены в inputs. Уже настроены alert, runbook и dashboard: отсутствует честная lifecycle/consumer связь, а не configured surface.

`N2.calibration.runtime` — отдельная открытая route/objective binding. Общий выбранный G25 путь computation → instrumentation host → objective выполняется параллельно. Этот вопрос не запрашивает повторного решения по availability, G528, научной достаточности calibration или продления срока. Все текущие N2 records остаются открыты до действительного evidence.

Если нужен alert, обязательны source-owned execution scope, одинаковая область для loss/activity, cleanup в finally на success/error и изоляция concurrent same-optimizer starts. Cardinality должна измеряться/ограничиваться; GaugeProxy cleanup не удаляет исторические Prometheus series. Reuse-first: существующие span, collector, GaugeProxy, report, Ops index/checker и alert consumer; новый registry/platform не нужен.

Acceptance: actual Calibrator/collector emits scoped observations; fresh native consumer различает retained completed loss + unrelated workflow, два concurrent same-optimizer starts, success/error cleanup, настоящий active stuck positive и missing telemetry. Removal controls сохраняют markers, но удаляют scope equality/cleanup/eligible observations и должны ломать именно property. До этого нет progress authority или production attainment.

Pattern pass: P29 actual rule engine/helper witness; P37 current-execution predicate не установлен; P38 global active counter — неверный proxy; P40 одна lifecycle-identity class, expression-only repairs остановлены. Ни source-global freeze, ни G acceptance, ни finding closure этим пакетом не объявляются.
