# MIG-04 — Fabric DatasetManifest converter и явная регистрация

## 1. Решение

**Ограниченно оценён, не закрыт. Новый подтверждённый product defect не установлен.** Canonical rename converter уже расположен рядом с Fabric schema owner, CLI явно регистрирует его, operational binding указывает настоящее callable. Generic Common не импортирует Fabric. Узкий старый Common adapter остаётся намеренно: он сохраняет прежний explicit-import registration side effect, не объявлен вторым schema owner.

Свежий результат: **5 bounded MATCH, 12 unchanged bodies / 14 cases PASS**. Три native child import/registration checks входят в эти14 cases. Настоящие Fabric DTO, clock и ManifestRegistry исполнялись без подмены; native отдельный persisted consumer control PASS. Full registered tools CLI ещё не квалифицирован.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/MIG-04_исходные_строки.txt) · [Pinned sources](../05_Источники/C81_источники.json).

## 2. Исходные требования и фактический смысл

| ID | Проверенный результат | Остаток |
|---|---|---|
| LA-050 | Fabric owner callback; explicit CLI registration; Common-neutral imports; legacy/current/equal/conflicting/unknown/missing shapes сохранены; caller isolation; JSON/YAML и default/explicit target | Historical profile/target disposition G01; adapter retirement G02; native CLI/evidence boundaries G03 |
| LK28 | Полезный rename не удалён; actual преобразование ключей и engine version stamp проверены | Не заменять converter удалением legacy API или всех readers |

Current docs прямо описывают **format-only conversion**, а не target DTO admission (`S13`). Поэтому version1.0 после rename не обещает, что любой неполный historical payload стал пригодным Fabric manifest. Не следует ослаблять extra-key guard или заполнять отсутствующие сведения только ради успешного parse.

## 3. Producer → converter → persisted output → consumer

Fabric callback переименовывает `datasetName`/`rawHash`, только если соответствующий snake_case alias отсутствует. Он возвращает тот же изменённый object и сам не stamp-ит version. Common engine копирует input, вызывает callback на копии, stamp-ит registered target и сохраняет isolation (`S01`, `S07`, `S08`).

CLI в dataset branch импортирует Fabric version/registration, регистрирует callback и вызывает neutral Common runner. `_dump` сохраняет выбранный JSON/YAML формат через общий atomic writer. Operational binding теперь ведёт в `polisyos.fabric.identity.migrations.migrate_manifest_0_9_to_1_0` (`S09`, `S10`).

Реальный `ManifestRegistry` читает `*_manifest.json`, вызывает настоящий `DatasetManifest.model_validate_json` **до регистрации**, а `require` отдельно проверяет reconciliation status (`S02`, `S03`). В C81 этот consumer действительно исполнен над собственными persisted outputs; это не проверка по имени файла или mocked validation.

Common initializer больше не импортирует предметный callback автоматически. Старый explicit `common.migrations.manifest` содержит маленькую намеренно продублированную rename функцию и прежний registration side effect, не импортируя Fabric обратно. Пока это поддержанная compatibility поверхность, наличие этого duplicate само по себе не незавершённый обязательный delete (`S05`, `S14`).

## 4. Свежие проверки

1. **P01:** все12 unchanged bodies/14 cases PASS: legacy-only/missing fields, equal/conflicting aliases, actual DTO positive/negative, Common no-op/schema errors, adapter equality, JSON/YAML CLI, actual binding. Три свежих native subprocess отдельно доказали отсутствие implicit registration до явного вызова, отсутствие Fabric после generic Common import и отсутствие Fabric при explicit legacy adapter import. Их command/exit/stdout/stderr сохранены.
2. **P02:** actual CLI → persisted manifest → native ManifestRegistry. Полный synthetic legacy fixture преобразуется и принимается настоящей DTO с сохранённым provided created_at/raw_hash. Equal aliases, conflicting aliases, unknown field и missing raw_hash остаются наблюдаемыми; conversion возвращает0 и version1.0, но native registry каждый из этих outputs отвергает. **Conversion success не назван admission PASS.** Source files неизменны.
3. **P03:** raw callback намеренно изменяет/возвращает input и оставляет version0.9. Public Common runner глубоко изолирует nested input; current no-op возвращает новую глубокую копию. Эти два API не механически одинаковы, их contracts не смешаны.
4. **P04:** default и explicit1.0 CLI outputs побайтово одинаковы. Unsupported2.0 отказывает, сохраняя old output/source. Missing raw_hash и created_at не появляются от stamp1.0. Отдельный DatasetManifest constructor может добавить clock default created_at, но поле отсутствует в `model_fields_set` и не является исходной provenance или действием converter.
5. **P05:** bounded old/new callback table совпадает для legacy, current, equal/conflict, missing и unknown shapes. Это narrow compatibility witness, не доказательство полного исторического corpus.

Отдельный native subprocess без tools seams прочитал собственный converted output через actual ManifestRegistry и вернул настоящую DTO. `sha256:abc` сохранён как synthetic string; ни этот hash, ни source/license не проверялись относительно реальных raw data.

## 5. Что сохранить и что осталось

**Сохранить:** Fabric owner, explicit composition registration, neutral Common, работающий rename и copy/stamp distinction, unknown/missing/conflicting данные без замалчивания, separate DTO validation, bounded legacy adapter и default target. Не подменять historical DatasetManifest StageManifest/DataForge snapshot по сходству названия.

**C81-G01 — historical mapping/target disposition.** Реальный historical corpus по-прежнему не получен. Определить поддержанные profiles и отдельные исходы conversion-only/target validation; equal aliases, conflicts и incomplete data требуют явного решения, не случайного выбора поля. Existing Fabric consumer уже отвергает invalid DTO. Добавлять новый параллельный validator не требуется. Нынешний честно ограниченный format-only output не классифицируется как новый product defect.

**C81-G02 — lifecycle.** До removal старого адреса проверить supported external callers/import order и окно совместимости. Native tests подтверждают нейтральность Common и narrow side effects, но не отсутствие downstream usage. Не импортировать весь Fabric из Common ради устранения временной duplicate функции и не удалять generic migration API.

**C81-G03 — native pipeline и evidence.** Supported-runtime registered/installed JSON/YAML/atomic output checks объединить с MIG-01/MIG-02 в LANE-06/CP2. Общий C79-R01 cleanup residual остаётся открытым. Raw content integrity, полнота набора, source/license authority, provenance и reuse eligibility не следуют из rename, версии1.0 или успешной DTO shape validation. Семантический owner этих проверок не заменяется converter.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C81_MIG04/commands.json) · [Cases/observations](../04_Проверки/C81_MIG04/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C81_MIG04/native_verification.json) · [Остатки](../01_Реестры/C81_остатки.json).

Final run02 exit0:5 MATCH,14/14 cases PASS. Run01 также успешен; final уточняет унаследованную helper metadata/import inventory, без product changes. Pytest runner отсутствует; existing bodies обслуживает внешний helper. Fabric converter/DTO/registry/clock native, без model/clock stubs. Canonical main whole source работает за C79 tools.lib/fs seam с unchanged atomic function и unbound-output selector. Registered outer CLI, preflight и SecureOutputRoot UNRUN; Python/Pydantic вне project baseline. Три native child checks не считаются вторично.

Два sentinel JSON outputs после проверки сохранены losslessly под .invalid-snapshot.bin с картой SHA. Checkout чист, зависимости/source/tests не менялись; реальные пользовательские datasets не читались и не мигрировались.

**81/127 рассмотрены ограниченно. Следующий — MIG-05. Фаза 2 не начата.**
