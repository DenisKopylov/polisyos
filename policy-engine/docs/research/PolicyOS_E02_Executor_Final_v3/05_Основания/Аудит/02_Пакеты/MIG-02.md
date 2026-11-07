# MIG-02 — RunManifest path normalization без подмены артефакта

## 1. Решение

**Ограниченно оценён, не закрыт. Новый подтверждённый product defect не установлен.** Старая inline basename-эвристика заменена настоящим Runtime owner. Converter сохраняет подкаталоги, использует заявленный root, проверяет существование и real-path containment каждого источника, отвергает конфликт двух адресов и external references. `--to` явно запрещён для path-only режима. Никакие файлы не копируются автоматически.

Свежий результат: **5 bounded MATCH, 11 unchanged bodies/cases PASS**, плюс отдельный native converter control. Actual Runtime writer → persisted manifest → actual converter/main → настоящий RunManifest/ArtifactRef → actual resolver прочёл прежние bytes. Whole native package/registered CLI не объявлен PASS.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/MIG-02_исходные_строки.txt) · [Pinned sources](../05_Источники/C80_источники.json).

## 2. Матрица исходных требований

| ID | Проверенный результат | Остаток |
|---|---|---|
| LA-048 | Runtime `manifest_migrations` реально подключён из CLI; no basename fallback; declared/default root, nested identity, existing source, conflict/escape/--to refusals; deepcopy/input preservation | Native/installed activation G01; profile/root limits G02; historical corpus G03 |
| LK15 | Использован настоящий persisted RunManifest1.0 и его writer/reader; import address теперь package, контракт сохранён | Не доказана эквивалентность с новыми Core DTO или всеми историческими runs |
| LK27 | Actual Runtime resolver сохраняет absolute/escape guards, operational binding остаётся в CLI | Containment и существующий contract directory не равны same-object/release authority |

Пакет не требует строить новый relocation engine только ради слова «миграция». Нынешний узкий normalization profile явно не обещает physical move или version conversion; unsupported external/target cases отказаны, а не молча переименованы.

## 3. Producer → converter → consumer

Runtime writer сохраняет `run_root=str(base_dir)`, root-relative ArtifactRef, audit trail и schema1.0 (`S03`, `S04`). Canonical CLI передаёт исходный manifest path и target converter owner, а output публикует только после его успешного возврата (`S02`).

Converter выбирает заявленный root; при отсутствии — `manifest_path.resolve().parent.parent`. Root должен существовать как directory. Для каждого `path`/`relative_path` он разрешает реальный путь, проверяет containment/existence и требует совпадения обоих адресов, если оба заданы. Возвращаемое имя получается относительно **этого же root**, а не через basename. Весь список preflight проверяется до публикации; data deep-copied, artifacts не перемещаются (`S01`).

Runtime consumer предпочитает relative_path и применяет `_ensure_path_within`; absolute path по умолчанию запрещён. В C80 producer и consumer — реальные whole modules с настоящими Pydantic DTO, но actual EnvironmentManifestRef передан через import bridge мимо тяжёлого Foundry graph. Converter сам импортируется native без подмены (`S03`, `S11`).

## 4. Свежие проверки

1. **P01:** все8 unchanged MIG-02 cases PASS. Nested `sub/data.json` при чужом `data.json` сохраняет original; внутренний absolute path использует declared root, а не папку input; missing source не получает substitute; symlink escape отказан; повтор byte-idempotent; явный target отказан; external files, в том числе одинаковые basenames, не копируются и не переадресуются. Отказ сохраняет old output.
2. **P02:**3 unchanged Runtime cases PASS — writer производит relative paths; audit ref/file действительно создаются; actual resolver читает relative path и отвергает absolute default. В writer case проверен доступ к ref после собственного переноса дерева через новый base; это не означает, что converter сам выполняет relocation.
3. **P03:** actual Runtime start/log/finalize создают собственный run с audit и payload. Canonical main пишет новый manifest в другой каталог. Actual DTO/resolver до и после даёт одинаковые абсолютные paths и bytes; SHA каждого собственного объекта сохранены. Source manifest не меняется, повтор converter равен первому результату, schema1.0/status ok сохранены. Output location не превращается в новый artifact root.
4. **P04:** conflicting path/relative_path; mixed set «первый valid, второй missing»; неправильный artifacts container/entry; отсутствие path; escape — все дают точный отказ до output. Source и old output неизменны, нет частичной публикации первого элемента.
5. **P05:** relative_path-only сохраняется; отсутствующий root получает documented default; внутренний symlink нормализуется к тому же внутреннему target; broken link отказан; Runtime absolute-default и escape guards работают. Relative declared root spelling сохраняется и остаётся CWD-bound — не объявлен переносимым relocation contract.

Отдельный свежий native subprocess вызвал converter без bridges, подтвердив same file bytes и отсутствие input mutation. Synthetic files и собственный Runtime run не называются пользовательским или production corpus.

## 5. Сохранить и доуточнить

**Сохранить:** существующий Runtime owner, чистый path-only profile, весь preflight до publication, exact source comparison, subdirectory identity, deepcopy, explicit refusals, historical DTO/reader, atomic output и operational binding. Не ослаблять containment и не искать substitute по basename.

**C80-G01 — native integration.** Выполнить registered/installed tools command и полный Runtime import/consumer на поддержанном runtime, включая JSON/YAML и общий output scope. Объединить с C79/MIG-01 в LANE-06/CP2, а не создавать несколько одинаковых больших tests. Общий **C79-R01 temp cleanup** остаётся открытым; успешные C80 writes его не закрывают и не порождают второй идентичный finding.

**C80-G02 — пределы profile/root.** Current normalization сохраняет root, не делает произвольный rebase, relocation или schema conversion. Relative root требует прежнего caller/CWD binding. Existence/real-path check действует в момент проверки, не даёт immutable snapshot или cryptographic custody при параллельной замене файлов. Не обещать более сильный контракт; если реальный consumer потребует relocation или snapshot guarantee, расширять существующего owner с соответствующей authority, не включать внешнее копирование неявно. Само отсутствие неподдержанного relocation режима сейчас не product defect.

**C80-G03 — historical и смысл evidence.** Сохранять RunManifest1.0 и исторические readers, пока не проверен corpus реальных поддержанных layouts/consumers. New own-run roundtrip не полная old-run compatibility и не journal/pickle recovery qualification. Same addressed bytes, containment, operational binding, release review и научная валидность — разные утверждения. Path converter не оценивает содержание политики и не создаёт empirical authority.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C80_MIG02/commands.json) · [Observations/cases](../04_Проверки/C80_MIG02/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C80_MIG02/native_verification.json) · [Остатки](../01_Реестры/C80_остатки.json).

Final run02 exit0:5 MATCH,11/11 cases PASS. Run01 сохранён: внешний tmp_path был relative, поэтому2 existing cases и2 diagnostics не соответствовали absolute pytest fixture; исправлен только audit harness (`resolve`), не product code. Pytest отсутствует. Whole Runtime import блокирован Python3.14 syntax в Core store при Python3.12; source-qualified EnvironmentManifestRef bridge позволяет bounded actual DTO/API execution, не native whole package claim. Canonical main использует C79 unchanged atomic function и unbound output seam; registered CLI/preflight/SecureOutputRoot UNRUN.

Собственные fixture symlinks после исполнения сохранены как target text без следования в архив; malformed/sentinel JSON bytes сохранены с картой переименования. Checkout чист, зависимости и product files не менялись. Никакие пользовательские runs не мигрировались.

**80/127 рассмотрены ограниченно. Следующий — MIG-04. Фаза 2 не начата.**
