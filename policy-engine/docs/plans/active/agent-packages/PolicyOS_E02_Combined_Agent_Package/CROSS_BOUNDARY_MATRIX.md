# Межконтрактная проверка I2

X-группы — адреса совместной приёмки, не15 глобальных locks и не новые предметные authority-контракты. Обычный local patch не обязан ждать всех участников группы; изменение общего carrier/API требует согласования его читателей.

## X01 — Effective plan и occurrence

**Пакеты:** CMP-01 CMP-02 CMP-03 JIT-01 RES-04. **Сценарии:** T4/T6. **Окно:** CP1/CP2.

Одинаковые static/dynamic/override, requires и bindings в sequential/async/resume; смена UUID не меняет предмет.

## X02 — Идентичность предмета, версии и наблюдения

**Пакеты:** CYC-01 CYC-03 CTL-02 OPT-02 TRN-01. **Сценарии:** T2/T10/T11/T12. **Окно:** CP1/CP3.

Предметные даты и полные candidate/evaluation IDs сохраняются; occurrence отдельно от содержимого. Не навязывать один hash всем разным объектам.

## X03 — State writes, replay и retry

**Пакеты:** STA-01 STA-02 RUN-03 EXE-01 RES-02. **Сценарии:** T5/T6/T8. **Окно:** CP2.

Warm/cold применяют только разрешённые фактические эффекты; no-write/null/delete раздельны; failed retry не загрязняет следующий baseline.

## X04 — Один durable frontier и актуальная попытка

**Пакеты:** RES-01 RES-02 RES-03 RES-04 DUR-02 CAS-01. **Сценарии:** T3/T6. **Окно:** CP2.

State, complete-set, original workflow и attempt/fencing согласованы; сохранённый blob не равен актуальному commit.

## X05 — Режим источника и непрерывность окна

**Пакеты:** ING-01 ING-02 ING-03 NET-01 OBS-01 OBS-02. **Сценарии:** T7/T8/T13. **Окно:** CP2.

Cursor-передача включается вместе с правильным advancement; restart/batch/spill не меняют строки и windows; replay не переходит в live.

## X06 — Уровень, функционал точки и partial output

**Пакеты:** EMP-01 UQS-01 UQP-01 CAU-04 BKT-02. **Сценарии:** T16/T18/T19/T20. **Окно:** CP4/CP5.

Point-only не получает epsilon-CI; point-identification не стирает statistical uncertainty; credible/CI/heuristic сохраняют смысл.

## X07 — Совместный закон и единицы информации

**Пакеты:** SIM-03 CAL-06 UQP-02 UQS-01 SCM-01 SCM-02. **Сценарии:** T18/T19/T20/T21. **Окно:** CP4/CP5.

Tied fields, correlated inputs, empirical draw rows и repeated evidence не становятся независимыми по технической форме.

## X08 — Предмет сравнения и историческая выборка

**Пакеты:** OPT-01 OPT-02 OPT-04 TRN-01 TRN-02 BKT-01 BKT-02. **Сценарии:** T10/T12/T16. **Окно:** CP3.

Split, scope, units, direction и source snapshot одинаковы между producer, training и comparison/promotion.

## X09 — Историческая стоимость и новое потребление

**Пакеты:** LLM-01 LLM-02 CTL-03 DUR-01 EXE-01. **Сценарии:** T8/T11. **Окно:** CP2/CP3.

Local reuse не повторно списывает original usage; compute/read бюджеты и реальные новые sentinels отражены раздельно.

## X10 — Funnel outcome и фактическое действие

**Пакеты:** FUN-01 FUN-02 FUN-03 OPT-04 DUR-02. **Сценарии:** T15/T10. **Окно:** CP3.

Stage APPROVE не отменяет aggregate defer; preflight до callback, действительное право перед commit, predecessor/attempt актуальны.

## X11 — Графовый carrier и смысл causal query

**Пакеты:** GRF-01 GRF-02 GRF-03 SCM-01 SCM-02 SCM-03 CAU-04. **Сценарии:** T20/T21. **Окно:** CP5.

m-separation и surgery читают правильные marks/lag/version; fit/query/twin используют тот же law/contrast; статический успех не аттестует PAG.

## X12 — Одна калибровочная цель и выбранная точка

**Пакеты:** CAL-01 CAL-02 CAL-03 CAL-04 CAL-05 CAL-06. **Сценарии:** T17/T19. **Окно:** CP4.

Mask, axes, scale и target priority совпадают в loss/gradient/report/Hessian; final forward и curvature принадлежат выбранной точке.

## X13 — Измерительная опора от источника до модели

**Пакеты:** OBS-01 OBS-02 UDF-01 UDF-02 FED-01 FED-02 CAL-01 CAL-02 BKT-01. **Сценарии:** T13/T16/T17. **Окно:** CP2/CP4.

Calendar, row grain, missingness и provenance не меняются при JOIN, padding или historical masking.

## X14 — Artifact bytes, profile и проверка

**Пакеты:** CAS-01 CAS-02 CAS-03 RES-04 WIRE-01. **Сценарии:** T6/T14. **Окно:** CP2.

First-writer profile и exact inventory соответствуют доступным bytes; оптимизация hash/reuse не отрывает проверку от потреблённого снимка.

## X15 — Научный дизайн и расчёт inference

**Пакеты:** DOE-01 DOE-02 DOE-03 CAU-01 CAU-02 CAU-03 BKT-04. **Сценарии:** T9/T16/T20. **Окно:** CP3/CP5.

Техническая batch/parallelism настройка не меняет replications, trajectory geometry, control set или independent unit.


# Дополнения E02

**X16 — migration identity.** Source→target/consumer map, old formats и exception identities: CAN/MIG/REP/FRY/SRV/UDF. Старый исправленный код не возвращается отдельной копией.

**X17 — measured calibration.** FRC-01/02, PCL-01 и EMP/BKT сохраняют subject/denominator/times. DDM-02 не является тем же calibration producer.

**X18 — generation publication.** EMB-01/02/03, DFI-03 и UDF-05: одна membership/basis/output identity; сравнение с B stores — только по их собственным contracts.

**X19 — DDM decision.** DDM-01/02: expiry/identity, R2 precedence, observed-window completeness и handwritten schema channel guard.

**X20 — generated/retired surfaces.** CLI-01/HYG/DFK/API: actual supported outputs, users, package forms и negative resurrection tests.

## Условия activation

**A01 · CYC-02, SIM-02, SIM-03.** Не выдавать положительный численный N8 без проверенных missing/zero, comparator, replications и trajectory semantics реально выбранного N5 runner.

**A02 · EMP-01, CYC-02, FRC-01.** Эмпирические helpers открываются после scope/uncertainty/graph-binding EMP-01; S10 временная и calibration-семантика — FRC-01/FRC-02. Условный simulation-only путь не ждёт неиспользуемых empirical/calibration функций.

**A03 · ING-01.** B79 и B80 принимаются совместно; cursor advancement и пригодность legacy cursors проверены до включения incremental read.

**A04 · UQP-01.** B189 не считать готовым fast-delta ремонтом без реальной карты отклика B190 и проверки output presence B191.

**A05 · TRN-01, TRN-02, OPT-02, OPT-03.** Исправление конструктора B128 не включает неподтверждённые исторические числа; numerical warm-start получает только compatible, origin-bound observations.

**A06 · CMP-01, CMP-02, CMP-03, RES-04.** Новый async/autolink/resume профиль объявляется эквивалентным только после своей согласованной effective-plan проверки. Явный исправный sequential профиль не блокируется неготовым optional режимом.

**A07 · SCM-03, GRF-01, GRF-02, SCM-02.** Active-query pruning сохраняет правильную surgery, immutable topology, factual ancestors и shared-noise/replica semantics. Частичный temporal/PAG профиль не присваивается статическому успеху.

**A08 · CAS-01, CAS-02, CAS-03.** Сокращение hash/I/O проверок не допускает чтение неподтверждённого нового bytes-view или публикацию transfer до complete inventory verification.

**A09 · FUN-03, OPT-04, DUR-02.** Техническая перспективность/APPROVE не разрешает внешнюю запись; callback preflight, права владельца, attempt и predecessor подтверждаются отдельно.

**A10 · CAU-02, CAU-03, CAU-04, UQS-01.** Исправленный point/label не означает статистическую аттестацию CI/RBC/bootstrap. Невыполненные процедуры и coverage checks остаются отдельными остатками.

**A11 · CTL-01, CTL-03, SRV-01, SRV-03.** Native search cutover не копирует private mutation и сохраняет все принятые B fresh/empty/cost/typed controls. LA-015 закрывается после проверки реального consumer, не появления protocol.

**A12 · CAU-01, CAU-02, CAU-05.** Metadata-detachment и dedicated cutover не заменяют numerical/inferential fixes; supported old plans и corrected common helpers проверяются вместе.

**A13 · FRC-01, FRC-02, PCL-01, EMP-01.** No fake pass может быть принято раньше реального bridge. Наличие report с finite CI не calibration evidence; полного завершения LA-051 нет при bridge_pending.

**A14 · EMB-01, EMB-02, EMB-03, DFI-03.** Общий encode не готовый atomic publisher; input identity не output integrity. Resume по новому generation принимается только с нужным inventory и reader.

**A15 · DDM-01, DDM-02.** Relocation не исправляет applicability/gate. Нельзя потерять LK35 channel guard, R2 signoff exception, non-overridable failures и actual observation-window precondition.

**A16 · CLI-01, HYG-04.** Удаление committed raw client после scratch handoff и всех retaining consumers. Generated checks пользуются одним input/output family; build/caller/lifecycle обязательства не исчезают по истёкшей дате.

**A17 · PLG-02, PLG-03.** Honest rollout/unsupported принят отдельно; он не означает реализованное обучение. Требуется настоящий policy→actions→gradient/update bridge для заявленного train capability.

**A18 · CAN-01, MIG-01, MIG-02, MIG-04, MIG-05, REP-01.** Изменение import-пути не меняет historical bytes/format/ошибки автоматически. Relocation, исправление поведения и прекращение поддержки получают раздельные результаты.

