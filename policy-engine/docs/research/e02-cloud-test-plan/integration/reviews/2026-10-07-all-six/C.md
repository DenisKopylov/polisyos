# C: независимая сверка перед продолжением

Снимок: G checkout /Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos, branch codex/e02-integration, HEAD ff277db7798fc312654704fa51c52e00f53f10f4. Уже существующий untracked execution-prompts/continuation-2026-10-07 не менял. Эти заметки находятся в игнорируемом policy-engine/_build/.

## Что проверено

Обязательная целостность результатов: results/import_results.py --check вернул ok:true. verification.json ограничивает это проверкой целостности и навигации inputs, не продуктовой приёмкой. query.py --unit C --failures-only --limit 30 — навигация по baseline, не доказательство PASS/closure для новых кандидатов.

Новый C root — commit c158689d692d47b6300609ac2ba5e7dac28650dc, tree 573063f560533e73518ef87d29acc1a46959cf33. Полный handoff: implementation-handoffs/C/C-root-final-20261006.json; verdict table: C54-final-20261006-v10.json и .md. Его source snapshot — codex/e02-C-continuation-20261006, head 48af851db5c0e802c92d9b30226acbc4436c69ba, tree 84b6416c9cc84a975ceb2d5d4cd5a8a4f6b3d9e2; analysis source 97c85fae2d4505ec8248540d98b9556296244208. Записанный published base — 198076863e143dea9f89f02734b13d50dae3eed5, tree 2b754a92c27959e2e747738d47ed0b419f3b6dd8. Anchor 1c0a87b385d65aa17f63b26157295976c4029ea — только ancestor evidence, не substitute за фактически fetched origin/main tip.

Воспроизведены 33 bundles / 54 уникальных finding IDs / 59 hash-bound criterion occurrences: 31 closed, 9 limited, 14 held. Все 59 criterion byte spans/source hashes сверены с двумя исходными документами; 282 RFC pointers разрешились. C source-DAG ACCEPT относится к Git identity/ownership, не к runtime или semantic closure. Исторические statuses не подменяют root verdicts.

## Полный знаменатель: все 33 bundle и 54 IDs

| Семейство | Bundles | Finding IDs |
|---|---|---|
| FED | FED-01, FED-02 | B138–B145 |
| OBS | OBS-01, OBS-02, UDF-01, UDF-02 | B146, B147, LA-030, LA-031 |
| SCL | SCL-01, SCL-03 | B17, LA-024, LA-025 |
| ING | ING-01, ING-02, ING-03 | B79–B86, B88 |
| DFK | DFK-01 | LA-005, LA-006, LA-026, LA-027 |
| HYG | HYG-02, HYG-04 | LA-008, LA-009, LA-011, LA-012, LA-013, LA-018 |
| MIG | MIG-01, MIG-02, MIG-04, MIG-05 | LA-010, LA-047, LA-048, LA-049, LA-050 |
| CAN | CAN-01 | LA-021 |
| PLG | PLG-01, PLG-02, PLG-03 | LA-022, LA-023 |
| CAT | DFK-02 | LA-028 |
| UDF | UDF-04, UDF-05 | LA-029, LA-032 |
| BER | BER-01 | LA-034, LA-036 |
| DFI | DFI-01, DFI-02, DFI-03, EMB-01, EMB-02, EMB-03 | LA-038–LA-042 |
| CLI | CLI-01 | LA-043, LA-044 |

Closed (31): B138–B147, B17, B81, B82, B84–B86, B88, LA-008–LA-013, LA-022, LA-030, LA-031, LA-043, LA-044, LA-047–LA-049. Это рекомендация C по finite/hash-bound критерию; formal closure и integration admission G — отдельно.

## Все 23 limited/held решения и ближайшие действия

- Limited (9): B79 — source-confirmed content binder от B до promotion; LA-006 — сохранить tombstone, получить FQN/public compatibility disposition; LA-024 — техническая snapshot continuity есть, нужна license-policy authority; LA-034 — tracked consumer census не равен внешнему; LA-038/039/041/042 — реальные installed fixture producer/readers/cache/compatibility пути доказаны только в их границах, для усиления claims нужны source/production membership и immutable encoder/model authority; LA-050 — ограничиваться текущим аудитом 19 manifest-named paths, DuckDB information_schema (129 columns/10 tables), четырьмя genuine current 1.0 manifests через установленный CLI. Исторический 0.9 файл не найден в проверенной области, что не доказывает отсутствие во внешней истории.
- Held (14): B80 — B должен content-bind dataset и ingestion_run_id перед cursor promotion; B83 — B source-owned event/version identity, offset _message_id не authority. Production backend/VM archives не запускались.
- LA-005/026/027 — public/schema/active-plan owners решают supported FQN, intended producer/consumer и alias window; удаление требует отдельного одобрения. LA-018 — фактический marker-kept-live negative всё ещё даёт Lex выбрать doc.source.hyg18unauth при source_auth:null. LA-021 — нужен B-owned Core byte-writer admission/profile contract; CAN candidate 3b2 потерял write_options, raw Core.put_bytes bypass сохраняет red. LA-023 — Product решает public .train / TrainingResult, C-W15 — typed cross-call checkpoint/resume. LA-025 — license text не permission, отсутствует авторитетный policy owner.
- LA-028 — A-owned serving profile/context отсутствует в реальном request; A владеет lifecycle/profile, C — typed consumer seam. Не вводить default и не редактировать A-файлы. LA-029 — нужен настоящий Linux/C7 create/start/stop/restart/cleanup process; LA-032 — C-W19 versioned authoritative inventory producer/artifact/bridge. LA-036 — отсутствуют E/F verified law/model/bounds producer и content-bound inputs; numeric fixture не authority.
- LA-040 — реальные Legal entity/fact/provision membership, withdrawals, immutable encoder/tokenizer/model provenance не исследованы; это не объявлено unavailable.

## Source candidates и ownership

Новые exact candidates, требующие delta review/admission:
- CAT handoff f428b114..., source 8dfa7f3c544461c0ff081861848fcc5d8523da5b, tree 3eac9b5c...; DFI/EMB source ab44166335130463178e65dfc29a252c96afe479, tree b1eaa06..., ancestor в CAT. CAT — 94 paths, DFI slice — отдельные 60, delta CAT поверх DFI — 36. Основные writer/readers: policy-engine/src/polisyos/data_forge/kernel/embeddings.py, policy-engine/src/polisyos/data_forge/kernel/io/generation_basis.py, policy-engine/src/polisyos/fabric/retrieval/service.py, policy-engine/src/polisyos/lex/knowledge/store.py, а также policy-engine/src/polisyos/data_forge/domains/catalog/batch/embedder.py, policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/store.py, policy-engine/src/polisyos/data_forge/domains/academic/batch/embedder.py, policy-engine/src/polisyos/data_forge/domains/academic/knowledge/store.py, policy-engine/src/polisyos/data_forge/domains/legal/batch/embedder.py и policy-engine/src/polisyos/data_forge/domains/legal/embedding_projection.py. Реальные API/NL/acquisition callsites пока не передают run_profile, а принадлежат A.
- ING handoff 48af851..., C source 81a4af184d72cd28e7ab4063140432e2af764547, tree c3423c94...; dependency 495043eb636275398ed729d9d01bec12059d8059. C writer — policy-engine/src/polisyos/fabric/data_plane/streaming.py и consumer tests policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py, test_pool_stream_budget_oracle.py, test_stream_pool_cleanup_oracle.py; B владеет policy-engine/src/polisyos/fabric/connectors/pool.py, policy-engine/src/polisyos/fabric/connectors/registry.py, policy-engine/src/polisyos/fabric/data_plane/cursor_store.py и CAS producer.
- CAN source 3b2ce9d6b8e37941a1061fa40fdc054cd3acb344, tree 37e4c01a...; прежний HOLD актуален: сохранять write_options и не обходить Core boundary. CAN paths: policy-engine/src/polisyos/core/artifacts/ir_adapter.py, policy-engine/src/polisyos/fabric/entity_resolution/store.py, policy-engine/src/polisyos/ir/analytics/ncm.py, policy-engine/src/polisyos/ir/artifacts/contracts.py, policy-engine/src/polisyos/ir/artifacts/io.py; policy-engine/src/polisyos/core/artifacts/store.py — B-owned.
- CLI source/test candidate c21584f390ae0e53602833df34571a0d9545f13e и FED candidate 575e7b16b59d374fc09e74563ba5dd2698877c64 имели bounded source-review GO, не closure и не G integration acceptance.
- MIG latest fe15a3604801f9a8c4fda51c73f51976f52d6c25 — docs/evidence-only delta после 552c7d9; LA050 не реконструирует 0.9 history.
- Остальные root source pins: SCL 01c303c2...; HYG 1e8aa374... и exact sdist 95407808...; PLG a452011d...; OBS/UDF 5a75b004...; DFK b8d9115c... (test-only change); BER 87999f69...; основные consumers BERL: policy-engine/src/polisyos/berl/service.py, policy-engine/src/polisyos/berl/adapters/shap_kernel.py, policy-engine/src/polisyos/berl/contracts/explanation_bundle.py, policy-engine/src/polisyos/runtime/quality/explanation_reliability.py, policy-engine/src/polisyos/scientist/validation/phase5_preflight.py. MIG writers: policy-engine/src/polisyos/common/migrations/README.md и policy-engine/src/polisyos/fabric/identity/migrations.py. Admission проверяет immutable Git candidate и полный footprint, не topic summary.

## Новое downstream свидетельство B → C

На c683ab749f470249565ecaf377e5a24cd74e47bc handoff current-completed-crossunit-contracts.json указывает B source 1862c021df74a5c5815bc5cd21a20e61b30132b6. Полные native.txt/native.xml (SHA256 739f1f5905edb0ed3ef7e603ee35cc4a04072f0105b94d634ab03308f506a764 и b4b60fd6c986cbd3a2d454cbdfd5ac5d0a2294941b27583f4faec17cb0fc7958) на evidence commit 85f0f0afd7abd62114074311ec90e7387ac27a38: FileSystemCAS + CursorStore + настоящий process-stream consumer, 10 тестов, 8 PASS и 2 FAIL.

Не переносить их как текущий C red без повторной проверки: source streaming.py у B 1862 старее и отличается от C 81a4: blobs 0915a4e9bc52ed97048d7e9f135ab8d3dfccbff6 и 08b304cc85885e0a95348b4b2d69bf3459e11e21 соответственно. Первый FAIL: persisted frontier 2 rows при предыдущем cap 3, restart cap 1; тест видит poll/flush/commit до отказа. Второй: process disconnect failure оставляет физический handle open/pending, но production registry не хранит retry ownership; свободный semaphore и observer rescue не доказывают cleanup. На C 81a4 startup failure уже передаёт cleanup registry, но финальный process_stream_dataset cleanup теряет session, если disconnect завершается ошибкой.

Следующая C задача: exact-tree rerun NET→ING; реализовать typed refusal до poll/surface/commit или строго документированный supported contract; process cleanup должен передать тот же physical handle production retry owner, сохранив primary exception. B владеет pool/registry, C — streaming consumer; сверять B87 handoff и не писать в B owner. Deciding witness: pooled source → stream → CAS/frontier/cursor → restart, точный порядок и bytes без потери/дублей, реальные cleanup controls и полный output на exact candidate. B87 остаётся open.

## Итог аудита

Самые конкретные новые задачи: reconciliation CAT/DFI source и A profile seam; C-owned stream cap/final cleanup по свежему B edge; CAN options после появления B writer contract; typed law-bound BERL. Все remaining held/limited IDs имеют явного владельца или отсутствующий input. Root документы — качественная полная карта, не автоматический merge/closure. Здесь не запускались тесты и не изменялись product source files.
