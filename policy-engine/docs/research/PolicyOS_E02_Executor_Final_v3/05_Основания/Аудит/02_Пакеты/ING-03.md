# ING-03 — bounded stream без подмены состава данных
## C101 · LANE-08 · B83, B84, B86

**Решение: частично подтверждено, не закрыто.** Dedupe теперь имеет одного UTC-horizon owner и не вытесняет живые ключи ради cap. Input/operator/output admission реально отказывает до публикации неприемлемого перехода; окно не закрывается ради памяти. Sanitizer больше не голосует по большинству batch, а использует bound schema. Остались повторная сериализация всего buffer и пропущенный `CATEGORY.allowed_values` в stream membership.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. **5 MATCH; 13 неизменённых existing test bodies /65 cases PASS**. Финальные команды: run02, boundary_run01, category_run01; run01 не суммируется. Это bounded execution с actual streaming/session/registry/pool/JSONL/CursorStore/quarantine и fixture CAS, не native pytest. **101/127**, далее NET-01.

## 1. Две оси

**Исходный ремонт.** Старые deque/set asymmetry и игнорирование TTL/disabled ушли из selected loop. Ключ строится из конкретных source-owned event/version components, без payload-hash fallback. Cap не переобъявляет24-часовой horizon. Row/input/operator/output guards связаны с actual execution, optional absence больше не трактуется как removed field по случайной пачке.

**Содержательная способность.** Actual finite reader связывает весь physical source с admitted event/version scope; отказ от чужого/missing owner сохраняется. Настоящий local JSONL producer не выдумывает provider ID из row position. Actual schema classifier влияет на сохранённые строки и DLQ, но не все existing FieldSpec restrictions участвуют. Ни key membership, ни schema binding не удостоверяют научную истинность, legal rights, live currentness или внешнюю полноту. Отсутствие универсального deterministic inventor не объявлено дефектом; LLM остаётся semantic proposer.

## 2. Матрица исходных IDs

| ID | Actual результат | Остаток |
|---|---|---|
| B83 | `_DedupeHorizon` хранит first-accepted UTC timestamps, exact scope/fields/window; live и restore используют ту же структуру. При cap2 a,b,c,a отказывает на c без eviction; cap3 retry сохраняет c и подавляет redelivery a. UTC86399/86400 и disabled проверены. | Native separate-process worker прочитан, UNRUN. Реальный источник должен иметь admitted owner; finite scope не превращён в universal API authority. |
| B84 |48 cases по4 window ×4 backpressure strategies ×3 условия: restored over-cap/live over-cap/exact closing transition. Refusal сохраняет frontier и не публикует rejected input; at-cap closing transition допускается. Input/output cap gates имеют removal/negative controls. | C101-R01: full buffered-byte rescans остаются. Disk spill не установлен, но honest refusal допустим; peak RSS/CPU не измерены. |
| B86 | Bound required/optional/null/type/finite membership одинаков при batch1/2/8; actual quarantine сохраняет4 ошибочные строки. Optional coverage через physical chunks1/3 не создаёт CDC. Validator removal пропускает bad type и ломает semantic oracle. | C101-R02: declared CATEGORY allowlist не проверяется row-local validator. Остальные ограничения не объявлены exhaustively equivalent всем consumers. |

## 3. Полезная existing цепочка

1. Source reader допускает уникальный owner и exact physical JSONL/event-version universe; `resolve_dedupe_key` не принимает missing/bool/list или неизвестную source version как identity [S01:2334–2460,3244–3267; S10].
2. `_DedupeHorizon.remember/restore` сохраняют UTC first acceptance. Live-key cap вызывает `StreamDedupeUnsupported`, не превращается в незаметный count-horizon. Injected clock и finite source маркируются replay_only [S01:267–332,2490–2559; S03].
3. Input admission считает реальные rows/serialized bytes до sanitizer и сборки clean_rows. Accumulator preview исполняет тот же window transition на отдельных containers до raw/window publication. Refused capacity не затирает predecessor [S01:1029–1054,2202–2332,2608–2744,3049–3053]. Ни пауза сама по себе, ни название spill_to_disk не объявлены освобождением памяти.
4. Schema binding заморожен, declared schema объединяется с visible extras, поэтому missing optional key не означает schema removal. Row-local type/finite/bounds/pattern/length checks питают настоящий quarantine producer/index/reader [S02:1212–1355; S05–S06]. Whole modes/evidence consumer прочитан в C100, здесь не переисполнен.

## 4. Наблюдения

| Наблюдение | Фактическая проверка |
|---|---|
| P01 |12 unchanged bodies/64 cases PASS:48 capacity cases; output gate exact/removal;3 batch schema cases +type-validator removal; dedupe cap/retry, legacy UTC refusal,4 invalid event/version inputs, missing source identity,3 missing-owner cases и scope isolation. |
| P02 |Three fresh store/cursor instances: first acceptance0/10s, redelivery86399s→0 emitted/1 dropped,86400s→1/0. Owner removal не меняет index/artifacts. Disabled mode сохраняет все4 строки и at_least_once. **Один OS-процесс**, не native worker test. |
| P03 |Actual processor на session20/40 строк:590/2380 повторных serialized-row estimates в buffered_bytes; дополнительно80/160 текущих row admission estimates. Все строки сохранены в одном неизменённом логическом окне. |
| P04 |Optional present/absent/null при physical chunks1/3:3 accepted,0 quarantine,0 CDC. Chunk5 приinput cap2 не вызывает sanitizer/raw writer и не оставляет artifacts/checkpoint. Ещё1 unchanged DataFrame/partial-frame body PASS. |
| P05 |CATEGORY allowed_values={'allowed'}: actual stream приbatch1/3 сохраняет и allowed, и outside, quarantine0, binding marker intact. Actual sibling DataFrame validator отвергает outside, allowed-only positive проходит. |

[Диагностика](../04_Проверки/C101_ING03/bounded_diagnostics.json) · [команды](../04_Проверки/C101_ING03/commands.json) · [main probe](../04_Проверки/C101_ING03/probe_ing03.py) · [boundary probe](../04_Проверки/C101_ING03/probe_boundaries.py) · [category probe](../04_Проверки/C101_ING03/probe_category.py).

## 5. Подтверждённые остатки

### C101-R01 — стоимость bytes accounting не стала инкрементальной

`buffered_bytes()` каждый раз собирает текущие rows и вызывает JSON size estimator для каждого. Он вызывается в основном loop, затем при preview admission и при фактическом append. Для незакрываемой session20/40 строк зафиксированы590/2380 повторных сериализаций retained rows: `3*N*(N-1)/2+N`. Дополнительные current-row estimates80/160 учтены отдельно. Значения возвращаются неизменёнными; это actual call-count instrumentation, не модель вместо кода.

Источник: [buffered_bytes1254–1270](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/streaming.py#L1254-L1270), [append/preview1029–1054](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/streaming.py#L1029-L1054). Сохранить точные guards и window semantics; уменьшать стоимость через existing owned accounting, не ложный approximate RSS и не forced flush. Severity low: production latency/CPU доля не измерены, OOM не утверждается.

### C101-R02 — разрешённые категории остаются только декларацией для stream

`FieldSpec.allowed_values` — существующее ограничение CATEGORY. `field_value_violation` проверяет строковый тип, pattern и length, но allowlist не читает. В whole actual process → sanitizer → chunk writer сохраняется `outside` при allowlist только `allowed`; schema_binding остаётся правильным. Это воспроизводится приbatch1 и3, а не случайность одной технической пачки. Positive allowed-only и actual DataFrame sibling negative отделяют schema meaning от предположения аудитора.

Источники: [FieldSpec constraint](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/connectors/contracts/_schema_field.py#L235-L246), [actual row validator82–126](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/data_plane/schema_rows.py#L82-L126), [sibling existing check185–188](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/connectors/contracts/_inference_validation.py#L185-L188). Остаток — подключить existing restriction к row-local admission/quarantine, без нового schema engine и без возврата majority inference. Severity medium относится к declared membership, не к доказанному production ущербу.

## 6. Что сохранить и чего не заявлять

Сохранить UTC horizon/first acceptance, cap refusal без eviction, source/version scope, отсутствие positional/hash identity fallback, conservative guarantee labels, pre-publication guards, at-cap window transitions, full lineage/state, declared optional/null semantics и реальные quarantine artifacts. C100-R01 first-frontier recovery остаётся отдельным результатом, здесь не пересчитан как новый ID.

**C101-G01:** native CAS/tenant/profile/input closure, supported Python3.14/pytest, whole served consumers, native OS-process UTC worker и production performance не исполнены. Существующий `test_b83_first_accepted_key_expires_at_utc_86400_seconds_after_restart` и его142-line worker полностью прочитаны, а не объявлены отсутствующими; P02 не присваивает им PASS. Source allocation до возврата chunk не равна downstream retained-state cap. Честный отказ spill_to_disk без spill reader — допустимая ограниченность, не автоматически баг.

## 7. Границы и продолжение

Native streaming/modes imports BLOCKED из-за baseline graph подPython3.12; pytest отсутствует. Whole actual modules работают в bounded package-shell graph с одной dependency TypeVar import adaptation, не с переписанным streaming алгоритмом. CAS/profile/load — fixture; actual quarantine использует разрешающий nonfinite CanonSpec для сохранения rejected payload. Schema test data synthetic, не authority для реальных политик. Установок, source/test/config/dependency edits, live services или model calls не было; tracked git status чист.

[Исходная карточка](../05_Источники/ING-03_исходные_строки.txt) · [источники](../05_Источники/C101_источники.json) · [остатки](../01_Реестры/C101_остатки.json) · [точные границы](../04_Проверки/C101_ING03/Чтение_и_границы.md).

**101/127 — промежуточный аудит; следующий NET-01. Фаза заданий исполнителю только после всех127.**
