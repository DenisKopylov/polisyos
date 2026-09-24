# E02-R2 Held Findings Review

Review base: merge commit `73c656744f051d9f40667da7f8bc91c61d8b4ebf` on `codex/e02-r2-held-review`.

Scope: the 14 Appendix C held findings B31, B61, B194, B197, B201, B202, B219, LA-005, LA-010, LA-026, LA-027, LA-031, LA-032, and LA-049. This is a bounded audit, not a closure claim. `held` means no finding-level behavioral closure; `partial` means a bounded behavior is present but one named residual remains. Every proposed behavioral witness below is **UNRUN** in this audit because four-base baseline jobs are active. No test command was run. Code and test citations use Git blob IDs from the review base; line references are within those blobs.

## Read-only records consulted

The E02 records are git-excluded and remain untouched. Their SHA-256 values identify the copies read from `/Users/deniskopylov/.codex/worktrees/safe-workspace/polisyos/.superpowers/sdd/bundle_manifest.json/`:

- `I1-CURRENT-RECONCILIATION-DELTA-20260921.md` — `b4d502df4c9a086e085d155f44528903eaad708ad7af68bc48a9fdfcbe3c051c`. Relevant lines: MIG-01 484–495; DFK-01 546–552; UDF-02 728–739; UDF-05 755–765; UQP-03 884–889; EMP-01 1044–1059; CAL-06 1319–1325; UQS-01 1522–1539; STA-02 1541–1578.
- `progress.md` — `148a2ff9b3c456916afd13969484ccb5769dc3fdca11b69b9234449bc6ce9a6e`. Relevant lines: 482–495 (MIG-01 bounded run / hold); 136–143 (STA-02 B61 receipt rejected, no integration).
- `GRF-02-test-first-review.md` — `fffb83a6251528c68f02c3d68e3235887616f1f93edeb866586e8a856660e247` (B219 exact selector and NetworkX `environment_not_established` rule).
- `I1-ROLLING-WORK-CYCLE-20260922-DFK-01-CURRENT-R1/reviews/DFK-01-J0696-independent-bounded-verdict.md` — `70e9fb9b452933c1e1295cd5abdfcfc9be5488eb72f74d9b75da38824b298950` (LA-005/026/027 remain compatibility-pending; J0696 is LA-006 only).
- `I1-ROLLING-WORK-CYCLE-20260922-MIG-01-CURRENT-R1/reviews/MIG-01-J0678-independent-bounded-review.md` — `0c721c4a19ebbf54e8722fcc206cd813ed38be839d12669e2717096e5e5cb8bc` (MIG-01 bounded review).

The original cards are tracked at the review base: `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@d800082eebfc12eaf647b0c0257c4f06e135d25a` and `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@4bdf76e99f0c26e40bc2a71e76d4940c23712260` under `PolicyOS_E02_Combined_Agent_Package/`.

## Findings

### B31 — `held`

**Original card criterion** (`B_r19_original.md:593–605`): “Ненулевой статистический интервал не теряется; асимметричный интервал не сужается без основания; смена единиц согласована; два метода одного estimand не становятся разными предметными координатами только по имени метода.”

**Evidence and blocker — `smallest missing capability`:** the projection maps point identification to `lower == upper == point` and builds proxy bounds symmetrically from a half-width; the typed `ValueOuterSet` has no separate statistical bounds. The public DTO cannot preserve both meanings yet. Evidence: `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:8163–8210`; `policy-engine/src/polisyos/core/contracts/value_outer_set.py@e73454e6b50624acc69627f48172a7612c9ccd9c:154–171`; candidate controls `policy-engine/tests/unit/remediation/test_emp_01.py@14d0a6bf93c00376483dc0d887a625b27e87167e:400–425`. **Absence denominator:** 1/1 `ValueOuterSet` owner-model file scanned for `statistical_lower`, `statistical_upper`, and `statistical_interval` (zero matches); the projection implementation is separately scoped to its one cited file. This is not a whole-repository semantic census. E02 still records B31 HOLD after EMP-01's bounded B16/B33 evidence (reconciliation delta 1044–1059).

**Distinguishing witness — UNRUN:** on the real public projection, point identification with native CI `(1,10)` retains `(4,4)` as identification bounds and `(1,10)` as statistical bounds; an asymmetric proxy CI remains asymmetric. Change units as a control and verify the serialized consumer preserves the same estimand.

### B61 — `held`

**Original card criterion** (`B_r19_original.md:1601–1613`): “Изменённая фактически используемая версия меняет ключ и результат; новая непотребляемая база не инвалидирует всё исследование; сохранённый снимок остаётся воспроизводимым.”

Current behavioral status: `not_established` in this audit; no behavioral test was run.

**Evidence and blocker — `smallest missing capability`:** the SKG owner exposes `latest_skg_version_id()` and formats `skg_snapshot_ref` as `duckdb://<path>#v<id>`; the recorded residual is that no owner-issued immutable read handle binds the cache identity to the bytes the consumer actually reads. Evidence: `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_query.py@bc4226fce34ea9f4bd08646cc16089dc06a6f1ee:1885–1909` and resolver reads at `:2393–2407`. **Absence denominator:** 14/14 tracked Python source paths in `data_forge/domains/academic/knowledge/` scanned for `skg_snapshot_ref`, `latest_skg_version_id`, `SnapshotReadHandle`, `SKGSnapshotHandle`, and `snapshot_handle`; the version/path functions occur in `skg_query.py`, with no read-handle symbol. This exact-name scan is corroboration only; the missing owner bridge is the E02-recorded blocker, not an inference that a differently named capability cannot exist. E02 progress 136–143 records the rejected/unintegrated bridge receipt; reconciliation delta 1541–1578 says the handle/bridge remains HOLD.

**Distinguishing witness — UNRUN:** run the actual consumer with a mutable DB path. Change the consumed SKG version between key formation and read; require one pinned snapshot for both and a changed result/key on a real consumed update. An unrelated, unconsumed database change must preserve reuse; unchanged pinned bytes are the control.

### B194 — `held`

**Original card criterion** (`B_r19_original.md:4792–4800`): “Не заменять NaN нулями и не удалять полезные 50 результатов.”

**Evidence and blocker — `smallest missing capability`:** `_build_results` filters to finite values and carries only that successful-value sample array plus aggregate valid/failed counts; it does not carry per-draw outcome identity/reason into the resulting law. The current path marks missing-output scope non-gate-eligible, but that does not identify the missing mass. Evidence: `policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py@38f409e574dc2a97badc694499f534734123006a:658–828`; adjacent test file `policy-engine/tests/unit/remediation/test_uqp_03.py@65ec0a2ae53ea5e7d1868c596b67a103c972a3b9:48–76` covers adaptive stopping, not this witness. **Absence denominator:** 12/12 tracked `foundry/uncertainty/*.py` source files scanned for `draw_id`, `draw_outcome`, `failed_draw`, `failure_reason`, `sample_identity`, and `mc_n_failed`; the relevant result-building terms occur in `monte_carlo.py`. The claim is limited to outcome detail carried by this builder. E02 UQP-03 records B194 failed-draw provenance and sequential stopping as open (reconciliation delta 884–889).

**Distinguishing witness — UNRUN:** for fixed symmetric draws `x ∈ [-1,1]`, `y=x`, force input-dependent refusal for `x<0`. The produced result must not present the successful-only mean near `0.505` as an unconditional push-forward. Separately prove transient retry reuses the same draw and domain refusal yields a typed conditional limitation.

### B197 — `held`

**Original card criterion** (`B_r19_original.md:4922–4934`): “Tied и untied конфигурации сохраняют точные адреса параметров, размерность и зависимость. Изменение технического имени группы не убирает результат. Несовместимые bounds и неразрешённая проекция отвергаются адресно.”

**Evidence and blocker — `smallest missing capability`:** the optimizer retains group `handle_indices`, but the report stores Hessian parameter names and field-keyed `calibrated_params` without the group-to-field projection; the downstream adapter iterates field keys and requires exact matches in Hessian names. Evidence: `policy-engine/src/polisyos/foundry/calibration/calibrator.py@3567d8e57dc1a05f8653c164683cb515807de2f2:603–665,1177–1179,1525–1528`; `policy-engine/src/polisyos/foundry/calibration/report.py@e33eb19964273297d229760d8e5849f800a0760c:56–90`; `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py@d547b27f4f64091ea399c7bf7d8c6f557504c774:49–84,134–149`. The adjacent `policy-engine/tests/unit/remediation/test_cal_06.py@864751c50f337e8c94505379cbbce0b8ec43be46` is bounded B198 coverage, not B197 closure. **Absence denominator:** 16/16 tracked calibration Python sources scanned for exact `group_to_field`, `field_to_group`, and `group_projection` names; `handle_indices` occurs in `calibrator.py`. The absence claim is scoped to `CalibrationReport` and `envelopes_from_calibration`, whose fields and lookup are directly cited; no claim that the optimizer itself lacks group membership.

**Distinguishing witness — UNRUN:** two fields tied to one group produce two field envelopes whose covariance remains rank one with covariance `0.0025` for group STD `0.05`; rename the technical group without changing output. The downstream welfare `_extract_std` path must consume that dependence. Incompatible bounds and missing mappings must refuse specifically.

### B201 — `held`

**Original card criterion** (`B_r19_original.md:4978–4990`): “Асимметричная конечная выборка может быть представлена без новых прогонов; точка и интервал сохраняют заявленные смыслы.” The distinguishing card example is 99 zero draws plus one 100: mean 1, equal-tail interval `[0,0]`.

**Evidence and blocker — `owner decision`:** the Bayesian summarizer uses the mean as `point_estimate` and equal-tail quantiles as the interval; `UncertaintyEnvelope` universally requires the point to lie within the interval. This representation rejects the card’s valid skewed summary. Evidence: `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py@d547b27f4f64091ea399c7bf7d8c6f557504c774:152–201`; `policy-engine/src/polisyos/ir/analytics/uncertainty.py@0a2495855d707a6548da6983bdef9abed9c4b0c7:1357–1441`. E02 records B201/B202 and public IR versioning as HOLD (reconciliation delta 1522–1539). The owner must decide/version point-functional semantics and historical serialization; do not silently widen a credible interval or relabel a median as a mean.

**Distinguishing witness — UNRUN:** represent the 99/1 sample with its declared mean and equal-tail interval, then round-trip it; include symmetric, atomic, bounded-support, and non-finite controls. Preserve a distinct mean if a compatible consumer instead requires an explicitly typed median point.

### B202 — `held`

**Original card criterion** (`B_r19_original.md:4992–5004`): “Одинаковые mean/CI не сливают различные законы. Изменение batch, порядка сохранения или чтения не теряет совместные draw-идентичности. Компрессия явно ограничивает поддерживаемые запросы и не превращает маргинальные samples в независимые совместные draws.”

**Evidence and blocker — `owner decision`:** `PosteriorSamplesCarrier` already exists, but `summarize_bayesian_calibration_posterior` only stores summary metadata and does not attach the received draws as `distribution_payload` or a content-bound ref. The public IR owner must set schema-versioned sample/joint identity semantics with a historical serializer, shared with B201. Evidence: `policy-engine/src/polisyos/foundry/calibration/uncertainty_adapter.py@d547b27f4f64091ea399c7bf7d8c6f557504c774:152–201`; existing carrier and envelope `policy-engine/src/polisyos/ir/analytics/uncertainty.py@0a2495855d707a6548da6983bdef9abed9c4b0c7:557–580,1357–1382`; adjacent `policy-engine/tests/unit/remediation/test_uqs_01.py@a8332205e105b759d6e04ac6eefb25270f0dd050` covers B199/B200, not B202. **Absence denominator:** the Bayesian summary is one function in one adapter file; it does not set `distribution_payload`. This is scoped to this producer, not a claim that the carrier is absent from the IR (it is present).

**Distinguishing witness — UNRUN:** compare two one- and two-parameter draw corpora with equal marginal means/intervals but different empirical probabilities or `+1` versus `−1` joint dependence. Round-trip and batch/order changes must preserve the source draws, weights, axes, and shared draw identity; the supported compression must declare which queries it cannot answer.

### B219 — `held`

**Original card criterion** (`B_r19_original.md:5375–5387`): “Приёмка — round-trip и неизменность результата при перестановке edges, отдельно для каждого реально используемого backend и класса графа.”

**Evidence and blocker — `smallest missing capability`:** `to_networkx()` constructs `nx.DiGraph()` and adds edges keyed by endpoint, so a same-endpoint directed/bidirected or different-lag edge overwrites another. The existing four-permutation test exercises this owner. Evidence: `policy-engine/src/polisyos/ir/analytics/causal_graph.py@f8758f86a0e78fb748e658fdc7d92addbb54df88:378–389`; `policy-engine/tests/unit/ir/test_causal_graph_contract.py@d4b495c0eb21807d8bd131ad1cbf87fb5f32be52:151–193`. **Absence denominator:** the claim is directly about the one `to_networkx` exporter method in the cited owner file; other backends are not claimed absent. The recorded exact selector is `test_causal_graph_networkx_preserves_mixed_edge_identity`; its required NetworkX execution remains UNRUN / `environment_not_established` per the GRF-02 review, lines 58–86 and 122–178.

**Distinguishing witness — UNRUN:** run the four insertion-order permutations through the real exporter and a consumer that resolves endpoints, edge marks, lag, and metadata. Ordinary single-edge DAG export is the property-preserving control.

### LA-005 — `held`

**Original card criterion** (`LA_r09_original.md:198–222`): “Поиск по полному дереву и сборке distribution, импортные и сценарные tests, round-trip обнаруженных старых inputs. Проверка одного символа не заменяет проверку всех трёх типов.”

**Evidence and blocker — `data record`:** the current DTOs remain importable and are identity-bound in the DFK tests; the E02 independent verdict accepts only LA-006 and explicitly keeps LA-005/026/027 compatibility-pending. Evidence: `policy-engine/src/polisyos/foundry/domain/schema.py@098c04de8a8fa4987b78fa0d7e3cb0af25ef5616`; `policy-engine/tests/unit/remediation/test_dfk_01.py@dc67765fe998e51f1b838ad28cba8222712e4cfc:136–173`; DFK review SHA above, lines 7–17, 59–91. **Search denominator:** 11,670/11,670 tracked text/code paths under `policy-engine/` scanned for `RegionProfile`, `GeneratedSchemaModule`, and `data_forge.kernel.pipeline.schemas`; eight files matched, including source definitions, test, baseline, and package documentation. This is not an external-consumer census; no absence of external callers is claimed. The card itself says indexed external search cannot establish zero.

**Distinguishing witness — UNRUN:** after a complete distribution, supported-input, and external-caller inventory, exercise every found DTO consumer and historical round-trip. Retire or adapt only the actual consumer path established by that record.

### LA-010 — `partial`

**Original card criterion** (`LA_r09_original.md:339–365`): “JSON/YAML, явно заданная и default версия, неправильный top-level input, exit codes, newline/encoding, ошибка записи, поддержанные historical fixtures. Прямое удаление root CLI — отдельная смена интерфейса.”

**Evidence and blocker — `owner decision`:** the root CLI delegates to the canonical runner, and the existing test asserts argv/status forwarding. Current-version Trinity validation is also explicit, but the E02 record keeps full MIG-01/LA-010/LA-049 HOLD because the no-op/self-edge postcondition is unresolved. Evidence: `policy-engine/migrate.py@4e402d2c11146f86dab86f0473ce2ad970b8cd8b:11–16`; `policy-engine/tools/ops_runners/migrations/migrate.py@a0c11ebbe6a5349461221f60f7a8b5161de68855:54–86`; `policy-engine/tests/unit/remediation/test_mig_01.py@48bb51735c406de067ade8a3c0d8cdc95dfb0dff:83–196,244–258`; reconciliation delta SHA above, lines 484–495. The remaining owner decision is whether same-version CLI input is “unchanged/no conversion” or “validated current Trinity,” and whether the identity self-edge should exist.

**Distinguishing witness — UNRUN:** run the actual root CLI through the canonical executor for JSON/YAML, default/explicit version, malformed top-level/nested inputs, write failure, and historical fixtures; verify output bytes and validation call. Existing `test_root_entrypoint_delegates_to_the_canonical_executor` is a candidate control, not a fresh pass receipt.

### LA-026 — `held`

**Original card criterion** (`LA_r09_original.md:1372–1414`): “Для удаления в проекте нужны поиск по полному доступному дереву, сборка distribution и schema-tests. Проверка AST не доказывает отсутствие внешнего клиента.”

**Evidence and blocker — `data record`:** `GeneratedSchemaModule` remains a three-field placeholder and the DFK compatibility test intentionally keeps its FQN importable. DFK-01's independent review did not retire it; wheel/distribution, external-consumer, and historical-payload evidence remain required. Evidence: `policy-engine/src/polisyos/data_forge/kernel/schemas/codegen.py@ac44baf02ab49e496631617060f32bbfde3add0e`; `policy-engine/tests/unit/remediation/test_dfk_01.py@dc67765fe998e51f1b838ad28cba8222712e4cfc:136–173`; DFK review SHA above, lines 59–91. **Search denominator:** same 11,670 tracked text/code paths and eight exact-symbol hits listed for LA-005; this cannot establish external absence.

**Distinguishing witness — UNRUN:** build wheel/sdist and run schema/import/historical-payload tests after the complete caller/distribution record and owner disposition. Keep or remove the exact FQN according to the discovered supported contract.

### LA-027 — `held`

**Original card criterion** (`LA_r09_original.md:1418–1454`): “В проекте проверить реальные imports и schema-тесты, сборку wheel/sdist и чтение исторических fixture.”

**Evidence and blocker — `data record`:** the alias initializer re-exports canonical schema classes; current tests intentionally verify importability and class identity. The bounded DFK review leaves the alias compatibility-pending and requires distribution, external-consumer, and historical-import evidence. Evidence: `policy-engine/src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py@09439357496c6e30c16444d8a5e7c15d5a3c09f3`; `policy-engine/tests/unit/remediation/test_dfk_01.py@dc67765fe998e51f1b838ad28cba8222712e4cfc:136–173`; DFK review SHA above, lines 59–91. **Search denominator:** the 11,670 tracked text/code paths and eight exact-name hits listed for LA-005; external callers remain unknown.

**Distinguishing witness — UNRUN:** after the consumer inventory and compatibility-window decision, verify each migrated import resolves to the canonical owner and test the intended alias result in wheel/sdist and historical fixtures.

### LA-031 — `partial`

**Original card criterion** (`LA_r09_original.md:1616–1664`): “Нужны native import-budget/characterization tests, registry mappings и сравнение output bytes выбранных stages.”

**Evidence and blocker — `smallest missing capability`:** the bounded UDF-02 move covers I/O and binding helpers, but the shared namespace remains imported by production builder modules and the package facade. Evidence: `policy-engine/src/polisyos/data_forge/domains/ukraine/builders/common.py@97c1f1dca8db13dc6409919ca2cf81feea43d997`; `policy-engine/tests/unit/remediation/test_udf_02.py@27c4c09d13063138f4e8f18bb6593a0ca898413b:35–86`; reconciliation delta SHA above, lines 728–739. **Search denominator:** 11/11 tracked `builders/*.py` paths scanned; five still import `.common`: `__init__.py`, `bindings_validation.py`, `demography.py`, `release.py`, `sources.py`. This is the full directory import census at review base. The D5 CAS-kind failure recorded in the same delta is not attributed here; its P41 attribution belongs to R9.

**Distinguishing witness — UNRUN:** migrate/characterize the named production callers through their canonical modules, verify registry mappings and byte-identical outputs for selected stages, then demonstrate real builder execution without depending on the broad compatibility namespace.

### LA-032 — `partial`

**Original card criterion** (`LA_r09_original.md:1668–1712`): “В интеграции нужны идентичность inventory, конфликт версий, недоступный blob, чтение прежнего bundle и сохранность численных полей.”

**Evidence and blocker — `smallest missing capability`:** the current demographic loader selects one complete layout and records `demography_layout`, and its tests cover mixed/incomplete/corrupt layouts. E02's J0681 acceptance is bounded to that snapshot-selection slice; persisted demographic inventory/path/digest/version binding and independent sibling loaders remain held. A general verified-stage/release manifest owner already exists in the Ukraine read API, but the demographic loader is not wired to it. Evidence: `policy-engine/src/polisyos/data_forge/domains/ukraine/demography/__init__.py@32d925f0d443ea61c08b16986b87ed053dd8c9a8:285–317`; existing receipt owner `policy-engine/src/polisyos/data_forge/read_api/ukraine.py@061441cccf7f52e8fdea33a4c63b47dd95372dad:73–134,223–338`; `policy-engine/src/polisyos/data_forge/domains/ukraine/manifests.py@b112bcd9f0d553d1194ee99599dc73e976fb01f5`; `policy-engine/tests/unit/remediation/test_udf_05.py@e7d2a6ee74913664d363242d53ea1d0c387c5a2e:97–235`; reconciliation delta SHA above, lines 755–765. **Search denominator:** 2/2 tracked relevant source paths (`demography/__init__.py`, `read_api/ukraine.py`) inspected. The first emits only the demographic layout marker; the second has generic stage/release manifest verification but no demographic inventory bridge. No claim is made that a generic manifest capability is absent.

**Distinguishing witness — UNRUN:** create a demographic receipt for the selected layout through the existing Data Forge artifact owner; mutate one selected file and require digest-bound refusal. Independent sibling readers must resolve the same receipt and preserve its exact numerical fields; the complete legacy bundle is the control.

### LA-049 — `partial`

**Original card criterion** (`LA_r09_original.md:3358–3395`): “Native валидный Trinity, неполный current-version mapping, неправильный вложенный объект, готовая модель, JSON/YAML/UTF-8, старые markers, major bump, прямой helper и настоящий operator CLI. Проверить validation call, exception identity, model dump mode/defaults и no-op identity.”

**Evidence and blocker — `owner decision`:** the current-version public migration path explicitly calls the real `TrinityBundle.model_validate`; a test observes the validator call and another rejects an incomplete mapping. The `1.0→1.0` identity edge remains registered but is unreachable under generic same-version no-op. E02's bounded J0678 review does not settle whether same-version means untouched or validated-current-Trinity. Evidence: `policy-engine/src/polisyos/ir/migrations/__init__.py@ccf40f02867599f06d60f12b5d7900147a1814d7:62–87`; `policy-engine/src/polisyos/ir/migrations/policy_ir.py@14f1c0319522800ebd7c9023be6177b40ffd16fd:18–30`; `policy-engine/tests/unit/remediation/test_mig_01.py@48bb51735c406de067ade8a3c0d8cdc95dfb0dff:83–147`; reconciliation delta SHA above, lines 484–495.

**Distinguishing witness — UNRUN:** invoke the real operator CLI on a complete native Trinity and an incomplete current-version mapping; assert validation call, exception identity, output/model defaults, and no-op identity. Once the owner binds the postcondition, remove or justify the unreachable self-edge and verify the registry path.

## Plan and pattern alignment

These blockers follow the existing north star and custody direction: represent downstream distributions without conflating functionals, preserve replay, and bind data to its consumed snapshot. Relevant main-plan rows are GY-D1 and GY-N13b for acquisition/world growth, GY-PR1 for promotion, Atlas DS15 for acquisition surfaces, and DS16 for value/uncertainty grammar (`GY-engine-subordination.md:1756,1778–1800`; `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:657–658`). This review does not take those plan tasks on as scope. Relevant failure patterns include P07 (historical replay), P10 (semantic adequacy), P27/P31 (canonical owner and structural repair), and P35 (complete-set evidence) (`policy-design-case-failure-patterns.md:52,55,72,76,80`).
