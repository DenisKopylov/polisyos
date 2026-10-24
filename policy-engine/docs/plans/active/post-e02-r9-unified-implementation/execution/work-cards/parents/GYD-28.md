# GYD-28: родитель и соединение рабочих результатов

Canonical title: F2 secret/PII and CAS integrity surface. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/04-gy-core.md#GYD-28).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [GYD-28.secret-scan](../cards/GYD-28/secret-scan.md) | [G09](../groups/G09.md) | Complete source-derived raw/public and DAG/loop outputs are enumerated and scanned for nested secret/PII at actual emission boundary. |
| [GYD-28.cas-integrity](../cards/GYD-28/cas-integrity.md) | [G09](../groups/G09.md) | Canonical bytes/digest, dedup/ref, tamper, GC retention and dereference are recomputed at actual reader. |
| [GYD-28.manifest-authority](../cards/GYD-28/manifest-authority.md) | [G06](../groups/G06.md) | Actual consumer resolves authority purpose, scope, provenance, rule version, time/currentness and boundary for the exact artifact. |

## Реальный join

Root joins complete output inventory/scan, CAS integrity/dereference, and authority result at a fresh output consumer.

**Outputs:** [GYD-28.secret-scan](../cards/GYD-28/secret-scan.md), [GYD-28.cas-integrity](../cards/GYD-28/cas-integrity.md), [GYD-28.manifest-authority](../cards/GYD-28/manifest-authority.md).

**Fresh consumer / ответственный контур:** Fresh raw/public artifact consumer resolves canonical manifest and CAS bytes, then enforces purpose/scope/currentness.

**Review размера:** Three proofs share an artifact set but remain distinct. No digest authority shortcut, sample denominator or lost CAS history.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Task results span scan, CAS lifecycle and authority-at-consumer; positive/adversary/removal/surface/rollback are joined across the three actual properties.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **binding** — Common acceptance and native schema/consumer/migration/journal/review companions remain parent contract.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **binding** — R19 planned status, composition reference and exact question context stay attached.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **join** — R19 consumer asks resolve content/root/recompute while separating source truth/authority; preferred solution explicitly divides scan, CAS bytes/ref lifecycle and authority consumer.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`
- **join** — The bundled step names scan wiring, CAS owner and purpose/scope/provenance/version/time authority as three distinct responsibilities.
  `solution.implementation_steps[1]`
- **join** — Bundled probe clauses are nested secret; tamper; missing manifest; valid digest with wrong/stale authority; GC/deref; and marker-preserving removal. Scan, CAS and authority cards own only their probes.
  `solution.implementation_steps[3]`
- **join** — Bounded streaming scan and bounded dereference are separate scan/CAS subclauses; uncertainty blocks or downgrades use.
  `solution.free_grow.resource_behavior`
- **join** — CAS preservation, authority binding, digest/authority separation and P29/P32/P31 proofs combine three existing outputs.
  `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **join** — Tamper/GC/dereference map to CAS; secret scan maps to scan.
  `solution.acceptance_discriminators[1]`
- **binding** — Undiscovered consumer/authority leaves exact incompleteness; issuer/purpose, corpus, retention and source-input classification remain parent inputs.
  `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`
- **join** — This is a genuine composed consumer result: resolve content-bound inputs and recompute the declared property, then keep input truth and authority separate. No single child owns that whole claim, so the parent joins the content/integrity and authority proofs.
  `task.r19_extension.question_slices[0]` (`R18-D14-Q01`); `task.r19_extension.question_ids[0]` (`R18-D14-Q01`)

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
