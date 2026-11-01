# CAS-01 — first-writer, честная ref и ограниченный реестр блокировок

## 1. Решение

**C74, порядок 74/127, LANE-06. B150, B151, B153; защита LK20. Ограниченная оценка, не полное закрытие.** Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`, полная карточка 8562–8687. Выполнен свежий проход после внешнего сохранения C73. Реконструированное происхождение внешнего harness указано явно; утраченные прежние результаты не используются как доказательство.

Три исходных механизма существенно исправлены. **B150:** разные metadata profiles имеют собственные immutable selected views одного blob; ref указывает на реально сохранённый profile, а ID-only view сохраняет первый manifest. **B151:** retry проверяет существующий blob digest и manifest size/binding, не подтверждает повреждение успешной ref. **B153:** actual coordinator имеет фиксированные 64 stripes, shared root registry и межпроцессный flock вместо бесконечного per-ID lock dictionary.

В этом bounded проходе **новый подтверждённый product defect не установлен**. Остаются G01 native custody/authority, G02 две реально падающие observer assertions и G03 эксплуатационное восстановление/storage qualification. Честный отказ на повреждении является допустимым repair outcome, а не обязательством построить автоматический ремонт.

## 2. Исходная матрица и две оси

| ID | Исходное требование | Actual producer → consumer | Итог |
|---|---|---|---|
| B150 | RefB не обещает profileB при единственном manifestA | Write options → v3 manifest/profile → immutable selected sidecar → ref selector → selected read validation | P01–P03/P06 подтверждают profile fidelity на actual methods/files; authority owner fixture, G01 |
| B151 | Повреждённый existing blob/byte_size не подтверждается retry | Current bytes/hash → exclusive lease → existing digest/manifest check → publication либо explicit refusal → read/verify | P04/P14 отказывают до успешной ref; G03 crash/repair qualification |
| B153 | Ограничить registry без вытеснения holders/waiters | Canonical root coordinator → fixed stripe + root/shared flock → opaque current lease → publication/read | P01/P07–P13/P15 подтверждают bounded real primitives; G02 native test observer drift |
| LK20 | Content/hash/current marker не равны полномочию reuse/closeout | Exact bytes/profile проверяются отдельно от tenant/input/attempt admission | Сохранено; authority не приписана fixture index |

## 3. Владельцы и намеренные изменения поведения

В actual `_put_blob_and_manifest_once` exclusive artifact lease охватывает повторную input-owner проверку, existing blob hash, default/selected manifest validation, создание staged members и publication. Existing hash вычисляется по файлу; default и выбранный view сверяются с content identity и byte_size. Разные profiles не переписывают первый manifest: создаётся view с отдельным selector. `put_bytes` возвращает selector, вычисленный внутри этой операции; explicit `return_selected_profile=True` может вернуть exact selector даже для первой записи [S01:3358–3814].

`ManifestLifecycle` строит current v3 manifest. Profile projection сохраняет historical v1/v2 правила и добавляет в v3 consumer-visible optional integrity metadata, исключая content-derived SHA. Повтор того же профиля стабилен; время создания не делает каждый retry новым событием [S02; S11:185–225]. Это намеренное расширение selected-view ABI, не equivalent relocation и не лицензия переписать provenance.

Actual read wrapper держит shared artifact lease; `get_manifest` проверяет selected-profile hash и соответствие kind/media_type offered ref. `get_bytes` сохраняет mandatory blob/manifest integrity; `verify` проверяет выбранный view, а не только default [S01:840–952, 2162–2225, 2349–2392, 3876–3914, 6167–6193; S05].

Coordinator фиксирует lock order: root shared → in-process RLock stripe → file flock. Активный same-ID nested lease переиспользуется; upgrade shared→exclusive и вложенный чужой ID отвергаются. После выхода opaque lease недействителен. Weak root registry не удерживает заброшенные coordinators навечно. Read-only path имеет отдельный `create_lock_files=False` и не вправе создать отсутствующий lock [S04:256–566].

Полные пути, Git blobs, SHA256 и прочитанные диапазоны: [источники C74](../05_Источники/C74_источники.json). Store и ownership index велики: проверены relevant полные methods/consumers, не заявлен полный обзор каждого файла. C4 frozen exact manifest helper прочитан как соседний строгий контракт, не как доказательство всех C4 owners [S12].

## 4. Что действительно исполнено

**15 MATCH**, включая сохранённые отрицательные результаты. Это не product PASS. Whole real AtomicFileWriter/ManifestLifecycle/DTO/layout/integrity/coordinator импортированы за одним artifact package shell. Selected store methods извлечены без изменения тел. **Receiver/index/owner/signing/storage admission — fixtures**, поэтому generic publication proof не выдан за native custody.

| Probe | Наблюдение |
|---|---|
| P01 | 14 unchanged regression bodies: 12 PASS, 2 TypeError FAIL сохранены. Actual lock pressure: 3000 acquisitions, pool64, 63 использованных stripes; активный holder/waiter не вытеснен |
| P02 | Пять вариантов kind/media/schema/producer/inputs имеют разные selected views одного blob; исходный default manifest побайтно неизменен |
| P03 | Explicit selected first-write и историческая profileless ref разрешают один и тот же manifest |
| P04 | Corrupt blob, неверный default byte_size и неверный selected byte_size отвергают retry; снимок файлов после отказа неизменен |
| P05 | При удалённом default новый manifest отражает нынешние options; старый exact view остаётся доступным, несовместимая старая profileless ref отвергается |
| P06 | Неверный kind в offered ref отвергается manifest/bytes reader; verify не даёт успех |
| P07 | Same-ID nested lease допустим; upgrade, nested чужой ID и просроченное после выхода proof отвергаются |
| P08 | Coordinator одного root разделяется, затем освобождается из weak registry после потери ссылок |
| P09 | Два собственных процесса реально разделяют exclusive flock; waiter входит только после release |
| P10 | Actual immutable publication принимает уже совпадающие bytes; неверный staged digest не заменяет existing blob |
| P11 | Четыре потока публикуют/читают свои honest profiles одного blob; ровно один default selector; все joined |
| P12 | Два собственных процесса публикуют разные profiles; fresh receiver читает оба; durable owner generation остаётся fixture, не подтверждена |
| P13 | Исключение holder освобождает same-ID waiter; оба потока завершены |
| P14 | Повреждённый selected manifest отвергнут, intact default продолжает читаться |
| P15 | Actual coordinator при missing stripe и no-create отказывает без файловых изменений; existing stripe shared read тоже ничего не создаёт |

Pressure не создаёт 3000 blob/manifest files: это 3000 lease keys при фиксированном числе lock files. Наблюдение не измеряет RSS, throughput или multi-host fairness. Реальные child процессы принадлежат probe и завершены; production artifacts не затронуты.

## 5. Две failed existing проверки не скрыты

`_observe_artifact_lease_attempts` принимает только `(artifact_id, exclusive=...)`. Current public read wrapper передаёт ещё `create_lock_files`. Поэтому unchanged tests о concurrent profiles и colliding stripes достигают readback и падают `unexpected keyword argument 'create_lock_files'` [S06:147–166, 452–594, 928–1072; S01:917–921].

Это **C74-G02**, test qualification drift, не установленный defect реального coordinator. Actual `artifact_lease` принимает keyword, P15 отдельно проверяет его no-create смысл. Нужно обновить observer по действующему контракту и повторить native набор; нельзя удалить readonly guard ради старого теста. Отдельные P09/P11/P12/P13 не превращают эти два FAIL в PASS задним числом.

Прочитанные signing-history, guarded tenant, pending-intent recovery и transfer tests **не исполнены**. Внешний fixture index не содержит полного durable поколения, поэтому такие bodies намеренно не запускались под ложным видом native acceptance.

## 6. Сохраняемая работа и реальные остатки

**Сохранить:** first/default manifest bytes и profileless compatibility; exact selected views и их lineage; один физический blob; corruption refusal до successful put; mandatory read integrity; immutable link/create-once и strict directory sync publication; root/stripe lock order; opaque lease validation; current readonly no-create policy. Не восстанавливать неизвестное происхождение по одному blob hash и не вводить run_id salt ради разных metadata.

**G01 — native цепочка.** Выполнить actual FileSystemCAS constructor → durable intent/owner generations → exact tenant/input admission → current selected readback/signature на supported runtime. В LANE-06 связать это с actual attempt, а не отдельным generic fixture. Здесь реальные files, hash, profiles и flock доказаны, но owner/index admission специально не подменяются их успешностью.

**G03 — эксплуатационная квалификация.** Проверить поддерживаемый filesystem при crash/power-loss и политику разрешённого repair/quarantine. Current refusal B151 корректен: автоматическое восстановление не требуется для честного отказа. P05 демонстрирует создание текущего профиля при отсутствующем default, **не восстановление утраченной прежней provenance**; старый exact view сохранён. Multi-host locking, storage-controller durability и большие throughput/RSS не измерены.

**LK20:** правильный content digest, верный manifest profile, актуальное поколение, эквивалентный request, целые outputs и разрешённый reuse/closeout — разные факты. Ни один generic CAS primitive не становится научным или юридическим authority только по имени `current`. Расширять следует существующие owners/profile contracts; новый lock-service или параллельный provenance журнал для первого результата не нужны.

## 7. Среда и воспроизводимость

Main fresh replay: exit0, 14 MATCH. Supplemental readonly: exit0, P15 MATCH. **14 existing bodies /14 cases:12 PASS,2 FAIL; native pytest bodies=0.** External helper реконструирован ранее по контексту, но перед этим run исходные методы и полный regression прочитаны заново, и все наблюдения получены на новых файлах. Пометки `reconstructed_script` относятся к происхождению harness, не к фиктивному переносу старого исполнения.

Native pytest отсутствует; обычный FileSystemCAS import блокирован Python-3.14 syntax `store.py:2118` на Python3.12.14. Pydantic2.13.4 также вне project baseline. Это ограничения среды, не дефекты продукта. Никаких installs/checkout edits или сетевых сервисов. В shared helper есть неактивный transfer support и его inventory hash; transfer не запускался и не аттестован C74.

[Команды](../04_Проверки/C74_CAS01/commands.json) · [Все наблюдения/failed cases](../04_Проверки/C74_CAS01/bounded_diagnostics.json) · [Явные seams](../04_Проверки/C74_CAS01/native_verification.json) · [Остатки](../01_Реестры/C74_остатки.json).

**74/127 рассмотрены ограниченно. Следующий — CAS-02. Полного закрытия нет; фаза 2 не начата.**
