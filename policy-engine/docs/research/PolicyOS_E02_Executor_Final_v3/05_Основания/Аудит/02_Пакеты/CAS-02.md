# CAS-02 — проверенный transfer и точный inventory

## 1. Решение

**Ограниченно оценён, не закрыт.** B148 больше не сводится к копированию в live CAS перед проверкой: intake snapshots, admission, private staging, повторная проверка и immutable owner publication действительно существуют. B149 directory A→B публикует точный новый inventory без хвоста A. Это полезную работу нужно сохранить.

Свежий C75 подтверждает два остатка export: **R01 — поздний чужой файл в reusable directory удаляется при cleanup старого поколения; R02 — ошибка повторного compressed export уничтожает прежний полный tar.** 12 MATCH включают воспроизведение этих дефектов, а не 12 product PASS.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`; исходная карточка [8688–8780](../05_Источники/CAS-02_исходные_строки.txt). [Pinned source index](../05_Источники/C75_источники.json) содержит SHA, Git blobs и read ranges. После утраты старой среды это **свежий replay**, не восстановленная задним числом аттестация.

## 2. Матрица исходных требований

| ID | Требование | Фактическое состояние |
|---|---|---|
| B148 | Проверить входящий связанный набор до публикации; не повредить старую пару | P01/P03: corrupt directory и tar, в том числе смешанный набор, дают ноль published files и сохраняют старый читаемый объект. P04: изменение bytes после intake отвергнуто, staging удалён. P05: `verify_integrity=False` не отключает actual manifest-size admission. Полный native owner/signature путь не исполнен. |
| B149 | A→B без A; смена опций без stale sidecars; безопасная замена поколения | P01/P02: exact B inventory и manifest-free export без старых sidecars. P08: directory source failure сохраняет прежний output. P10: заранее чужой файл приводит к отказу без удаления. P09/R01 и P11/R02 выявляют оставшиеся failure boundaries. |

Разделение equivalent move и исправления: transfer helpers действительно вынесены, но текущие measured bindings, staging/admission и exact generation — содержательные изменения поведения, не одна смена имени. Не требуется восстанавливать retired copy-then-verify путь или вводить гигантскую транзакцию на весь архив.

## 3. Реальная цепь producer → consumer

Public `FileSystemCAS.export_subgraph` проверяет владельца default/selected view и передаёт stream callbacks в transfer owner (`S02:5885–5926`). Native `open_member` удерживает read lease, проверяет pending transaction, owner, manifest/profile/ref, размер и digest; завершает stream до выдачи receipt (`S02:1287–1545`). **Этот stream owner прочитан, но не исполнен в C75:** fixture отдаёт реальные bytes/size/hash под actual lease.

Transfer producer записывает members с content bindings и точным inventory. Directory готовится отдельно и публикуется swap; tar пока пишет непосредственно final path (`S01:667–813`). Import consumer сначала держит no-follow handles и snapshots, сверяет закрытый набор и bindings, вызывает owner admission, копирует только pending members в private staging, снова сравнивает реальные bytes, выполняет requested verification и лишь затем вызывает publication (`S01:815–1158`).

Store admission различает exact no-op refs и pending artifact IDs; публикация имеет existing immutable bytes/profile checks, preflight storage, per-artifact intent/stage/claims и exact retry (`S02:4289–5323`). Мы исполнили эти selected methods с fixture index; **не доказали durable current ownership**. Report отдельно несёт received, published, reused и verified refs: P12 даёт `[1,1,0,1]`, повтор `[1,0,1,1]`. Имя `durable_owner_manifest_stage_intent` само по себе не повышает fixture до authority.

## 4. Проверки и полезное сохранённое поведение

- **P01:** 10 unchanged existing test bodies /11 cases PASS: corrupt directory/tar, exact A→B, failed directory write, foreign entries, unlisted members, invalid tar path, alternate selected profile, no-follow parent/member и canonical marker. Весь test file прочитан, но signing/tenant/recovery cases не запущены.
- **P02:** export без manifests не сохраняет старую sidecar.
- **P03–P05:** mixed corrupt group, intake-to-stage mutation и bad manifest size отказывают до live publication; старый объект не испорчен.
- **P06–P07:** strict inventory отсутствие и duplicate tar member отвергнуты. Legacy `verify_integrity=False` путь без inventory остаётся ограниченной совместимостью и не заявляет requested integrity verification.
- **P08/P10:** source failure в directory и foreign entry до preflight оставляют старое поколение нетронутым.
- **P09/P11:** различающие отрицательные controls ниже; P12 подтверждает раздельную disposition, не scientific/ownership authority.

Сохранять no-follow/path checks, exact inventory и bindings, immutable history и selected view вместо overwrite, bounded streaming в native owner, admission до publication, отдельные disposition fields и честный отказ. Synthetic payloads здесь тестируют filesystem/contract, не валидируют модель политики.

## 5. Подтверждённые остатки

### C75-R01 — чужой файл после preflight удаляется (medium, bounded confidence high)

`_validate_directory_export` один раз допускает только известные members. Между этой проверкой и `_publish_directory_generation` callback первого source read добавляет `user-note.txt` в **собственный fixture output**. Actual transfer успешно заменяет target, затем `shutil.rmtree(previous_root)` удаляет и поздний чужой файл (`S01:385–468,753–798`). P09 фиксирует SHA и исчезновение файла; P10 показывает, что такой же файл до проверки корректно сохраняется при отказе.

Нарушен прямой запрет B149 удалять пользовательское содержимое как export-owned. Это не внешняя exploit демонстрация и не удаление вне fixture root. Нужна минимальная корректировка existing ownership/generation cleanup: не считать весь destination собственным по устаревшему preflight; сохранить неизвестное/изменившееся или безопасно отказать. Простое ещё одно неполное scan не следует объявлять доказанной атомарностью.

### C75-R02 — failed tar replacement теряет старый archive (medium, bounded confidence high)

Compressed branch открывает final path через `tarfile.open(..., "w:gz")` до завершения source reads (`S01:718–752`). P11 сначала создаёт полный A, затем на export B вводит `OSError` при чтении manifest после blob. Exception честно выходит наружу, однако old bytes уже заменены; новый tar не содержит ни export marker, ни прежнего A. Before/after SHA и actual members сохранены. P08 — различающий directory control: прежний output сохраняется.

Это потеря предыдущего корректного transfer результата, **не ложный успешный import**. Сохранить старый archive при source failure через existing staging/atomic publication подход; не отключать source verifier и не считать partial tar завершённым пакетом.

## 6. Квалификационные остатки

**G01:** supported native FileSystemCAS → signed/default/selected-view transfer → durable index/current tenant/input owner → real consumer. Прочитанные signing, cross-tenant и pending-intent recovery bodies остаются UNRUN. Нельзя считать проверку структуры/binding signature проверкой доверия к подписанту. Generic CAS byte correctness не даёт права semantic reuse, закрытия attempt или научного вывода.

**G02:** поддерживаемые filesystem, crash/power-loss, concurrent publication и восстановление минимально необходимой группы. Process-local controlled failure не доказывает machine durability. Per-artifact transaction виден в исходнике; атомарность всего archive не заявлена и исходная B148 её безусловно не требует. Продолжать через существующие transfer/index/profile owners, не строить новый provenance subsystem.

## 7. Воспроизводимость и границы

[Команды](../04_Проверки/C75_CAS02/commands.json), [наблюдения](../04_Проверки/C75_CAS02/bounded_diagnostics.json), [native/seams](../04_Проверки/C75_CAS02/native_verification.json), [остатки](../01_Реестры/C75_остатки.json). Fresh main replay exit0: **12 MATCH; 10 bodies /11 cases PASS; native pytest bodies=0**. Existing тела не изменены, pytest helpers поставлены harness. Реальные transfer/file/hash/coordinator/selected methods, но fixture owner/index/stream и отключённые tenant/input/signing/storage admissions явно ограничивают вывод.

Native pytest отсутствует. Обычный import store блокирован Python3.14 syntax на Python3.12.14 (`store.py:2118`); Pydantic2.13.4 также вне baseline. Это environment BLOCKED/UNRUN, не product defects. Репозиторий чист, installs и source edits не выполнялись. Negative symlink fixtures переведены в текстовый inventory после проверки нахождения в собственном root; ZIP не следует наружу.

**75/127 рассмотрены ограниченно. Следующий — CAS-03. Полного закрытия нет; фаза 2 не начата.**
