# CNT-08.basis-branches — Сохранить competing basis branches, ancestry и search frontier

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [CNT-08](../../parents/CNT-08.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Per generation, immutable common inputs and changed-premise branches/difference record preserve lineage/dependence/uncertainty; exploration/exposure stays distinct from eligible confirmation and verified absence.

**Предпочтительное решение.** Reuse Fabric/Scholar/Scientist lineage and claim-support graph. Persist input edges and shared study/cohort/participant/model ancestry, alternative metric/mandate/law/method/permission/calibration branches and bounded search state. Anomaly may open candidate/acquisition; only eligible confirmation or source-validated correction changes support.

**Граница владельца.** Existing Fabric lineage and Scientist support owners write their native records under canonical leases; no new independence/evidence service. External custodians supply studies, data and change facts. Exact path/lease intersections unresolved after E02; assume possible overlap.

**Входы.** CNT-05 metric/mandate outputs and CNT-06 ClaimRecord; conditional CNT-04/CAP-05 law and CNT-07 participation outputs only if selected. Custodians supply holdouts, outcomes and ancestry; logs are selection history.

**Выход и consumer.** Immutable basis manifest, changed-premise difference, ancestry/input-edge graph and bounded search frontier with unknown overlap/no-hit limits; consumed by event-recompute and claim support.

**Что можно готовить независимо.** Read-only lineage/query-bound census can prepare. No outside event or confirmation is synthesized; writes require E02 source, rights, owner, exact lease and permit.

**Где результат соединяется с другими.** Event-recompute consumes manifest/edge set; fresh Scientist claim reader applies claim-specific method profile. Selected legal/participation premises only; no blanket gate.

**Positive.** На двух поколениях с общим исследованием/когортой и изменившейся географией свежий reader показывает общее основание и изменённую premise, не считает публикации или hashes независимыми, сохраняет корректное сравнение разных моделей, а ограниченный поиск сообщает только «не найдено в маршрутах X к cutoff Y».

**Distinguishing negative.** Одинаковый кэш, новый DOI/hash, повторный адаптивный просмотр или неизвестное перекрытие не дают независимое подтверждение; бюджетный cutoff, устаревший индекс или непросмотренный источник не дают полного no-hit. Не переносить право, target, время или калибровку по похожему ID.

**Matched removal.** Оставь источники и ancestry refs доступными, отключи их consumption и подай два разных paper IDs с общей когортой. Неизменённая независимая семантическая проверка ожидает один dependent basis/unknown overlap; если без механизма reader допускает независимый count, именно эта проверка должна FAIL. Отдельное отсутствие ancestry/event даёт unknown/limited, но не доказывает removal property.

**Граница контекста.** Analytical basis state, not new evidence source or universal Bayesian/independent-confirmation rule.

## Первые действия и передача

1. После принятого E02/source rebind найди фактических Fabric lineage и Scientist claim-support owners, их поколения, readers и точные leases.
2. Для выбранной генерации зафиксируй immutable общие входы и difference по изменившейся premise (мера/мандат, право, источник, метод, testimony/permission или calibration); привяжи support, contradiction, ancestry, dependency и supersession к версиям.
3. Сохрани common ancestry и partial/unknown overlap; search/exposure оставь bounded selection history с frontier, query/version/time, rights, result denominator, cutoff и blind spots. Передай manifest event-recompute и claim-specific basis свежему Scientist reader; independent/holdout basis требуется лишь claim, который заявляет независимое подтверждение.

**Ответственность и handoff.** Fabric lineage owner пишет native ancestry/input edges; Scientist claim-support owner решает claim-specific support и method profile. Фактических владельцев и exact leases закрепляет source rebind; не вводить новый evidence/independence service. Потребители: event-recompute для manifest/dependencies и свежий Scientist claim-support reader для статуса конкретного claim.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-05](../../parents/CNT-05.md) | `direct:owner_readiness`: Selected measure and mandate branches/results.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-06](../../parents/CNT-06.md) | `direct:owner_readiness`: ClaimRecord target/estimand/method and conditional calibration relation to compare or recompute applicable claims.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-04](../../parents/CNT-04.md) | `conditional_acceptance_requirements:composition`: Only selected legal premise: qualified legal content/applicability and native verifier.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: legal premise selected by CNT-01 |
| Supplier [CAP-05](../../parents/CAP-05.md) | `conditional_acceptance_requirements:composition`: Only selected legal premise: native content-bound legal-source admission/verifier.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: legal premise selected by CNT-01 |
| Supplier [CNT-07](../../parents/CNT-07.md) | `conditional_acceptance_requirements:composition`: Only selected participation/value/testimony premise: permitted assertion and affected-use link.<br>Source: `task.conditional_acceptance_requirements[1]`.<br>Условия: participation/value/testimony premise selected by CNT-01 |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.deliverable`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.positive`; `task.adversarial`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.migration`
- **binding** — Legal and participation inputs are conditional on actual CNT-01 selection; they are qualified evidence inputs, not new blanket start gates.
  `task.conditional_inputs[0]`; `task.conditional_inputs[1]`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.r14_extension.requirement`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`
- **execute** — These clauses preserve immutable comparison, common-vs-changed premises, ancestry/dependence, bounded search/exploration and claim-specific confirmation; logs/hashes alone are not evidence.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Consume qualified CNT-04/CNT-07 refs; compare changed bases, ancestry and dependencies, preserving dissent and refreshing only affected claims. Positive discriminator: Verified legal or participation premise change updates linked support; common study/cohort is not independent evidence. Adversary: Citation/hash alone, false target/time edge or mirrored testimony cannot count as new or independent support. Removal: Remove dependency/ancestry binding but keep labels; fresh reader cannot claim affected refresh or independence.
  `task.r19_extension.question_slices[0]` (`R18-D01-Q02`); `task.r19_extension.question_ids[0]` (`R18-D01-Q02`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Use exact local refs or verified profile mappings to find related custody records; ancestry is not external continuity or independent support. Positive discriminator: With no external ID, a fresh reader retrieves records explicitly attached to one local ref across distinct case_ids, without claiming real-world continuity. Adversary: Similar questions or unqualified/reused aliases do not collapse cases or make evidence independent. Removal: Remove ref/mapping resolution but retain hashes: aggregation and independent-support claims become unknown; cases stay separate.
  `task.r19_extension.question_slices[1]` (`R18-D01-Q03`); `task.r19_extension.question_ids[1]` (`R18-D01-Q03`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Consume qualified CNT-03/04/07 refs; compare parent/child bases, target/method/time applicability and common ancestry, dedupe overlap, and refresh dependent uses. Do not re-decide law, delegation or permission. Positive discriminator: Child-specific qualified bases are reused only where applicable; merge retains conflict and counts common cohort once. Adversary: False target/time edge or shared cohort cannot pass as applicable or independent support. Removal: Remove child dependency/ancestry binding but retain parent IDs; fresh support reader limits the unsupported child basis.
  `task.r19_extension.question_slices[2]` (`R18-D01-Q04`); `task.r19_extension.question_ids[2]` (`R18-D01-Q04`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Compare changed premise and retain dependence between branches. Positive discriminator: Common source basis vs changed geography is explicit. Adversary: Count derived branches as independent confirmations. Removal: Remove alternate branch; sensitivity range disappears.
  `task.r19_extension.question_slices[3]` (`R18-D02-Q01`); `task.r19_extension.question_ids[3]` (`R18-D02-Q01`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Compare dependent bases under one target. Positive discriminator: Counts widen sensitivity without inflating independence. Adversary: Treat imputations sharing sources as independent. Removal: Remove branch; sensitivity range disappears.
  `task.r19_extension.question_slices[4]` (`R18-D02-Q02`); `task.r19_extension.question_ids[4]` (`R18-D02-Q02`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Compare alternative support/heterogeneity assumptions as dependent. Positive discriminator: Auxiliary relation changes bound width visibly. Adversary: Count allocations from same table as independent evidence. Removal: Remove premise branch; range narrows visibly.
  `task.r19_extension.question_slices[5]` (`R18-D02-Q04`); `task.r19_extension.question_ids[5]` (`R18-D02-Q04`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Consume search/exposure trace only as bounded selection history and keep frontier, cutoff and blind spots separate from the admitted empirical basis; apply the claim's stated scope when comparing bases. Positive discriminator: Completed bounded search supports only “not located in routes X as of cut Y.” Adversary: Truncated budget, stale index or unsearched source cannot become full no-hit. Removal: Drop selection-history dependency but keep count; broad conclusion loses its warrant.
  `task.r19_extension.question_slices[6]` (`R18-D03-Q01`); `task.r19_extension.question_ids[6]` (`R18-D03-Q01`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Link immutable study/cohort/control ancestry; retain partial and unknown overlap. Positive discriminator: Shared cohort does not add independent confirmation. Adversary: New DOI/hash over shared controls cannot tighten precision. Removal: Drop the dependence edge but keep count; fresh synthesis loses independence.
  `task.r19_extension.question_slices[7]` (`R18-D03-Q02`); `task.r19_extension.question_ids[7]` (`R18-D03-Q02`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Compare basis generations with target, quality premise and method changes explicit; retain prior generations and affected dependencies. Positive discriminator: Only claims depending on changed target support are affected. Adversary: Same bytes do not erase measured drift or downgrade unrelated claims. Removal: Remove the quality edge but keep snapshots; current comparison loses its basis.
  `task.r19_extension.question_slices[8]` (`R18-D03-Q03`); `task.r19_extension.question_ids[8]` (`R18-D03-Q03`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Keep interpretations as changed-basis branches with shared-source ancestry. Positive discriminator: Admitted correction updates dependent branch; historic basis remains. Adversary: Several paraphrases of one source count as independent authority. Removal: Remove dependency edge, keep branch labels: fresh comparison detects basis loss.
  `task.r19_extension.question_slices[9]` (`R18-D04-Q02`); `task.r19_extension.question_ids[9]` (`R18-D04-Q02`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Keep sources and ancestry distinct when comparing competing legal bases. Positive discriminator: Correction changes only branches that depend on it. Adversary: Several summaries of one resolution count as independent authority. Removal: Drop scope/ancestry edge, keep count: support comparison fails.
  `task.r19_extension.question_slices[10]` (`R18-D04-Q05`); `task.r19_extension.question_ids[10]` (`R18-D04-Q05`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Persist regime, schema/code version, coverage, bias and bridge source. Positive discriminator: Bridge applies only to matching versions and validated subgroup/time. Adversary: Change source version or target population while keeping bridge label; binding rejects. Removal: Remove calibration content; fresh consumer cannot support bridge.
  `task.r19_extension.question_slices[11]` (`R18-D06-Q04`); `task.r19_extension.question_ids[11]` (`R18-D06-Q04`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Extend search boundary to result-level denominator, protocol versions and missing reasons. Positive discriminator: Inception cohort reconciles each eligible result to report or explicit state. Adversary: Keep complete-search declaration but add eligible registry record without results. Removal: Remove a result but leave completeness declaration; reconciliation catches mismatch.
  `task.r19_extension.question_slices[12]` (`R18-D06-Q05`); `task.r19_extension.question_ids[12]` (`R18-D06-Q05`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Bind grounds for required branches; preserve alternatives; optimizer survivors are not the model universe. Positive discriminator: Claim stays limited to source-supported selected set. Adversary: Optimizer survivors are mislabeled as all plausible models. Removal: Remove basis binding, keep label; fresh reader limits claim.
  `task.r19_extension.question_slices[13]` (`R18-D07-Q01`); `task.r19_extension.question_ids[13]` (`R18-D07-Q01`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Bind shared cohort, assumptions and exposure. Positive discriminator: Shared cohort counted once under dependence profile. Adversary: Different paper/version treated independent. Removal: Drop ancestry, keep hashes; independence fails.
  `task.r19_extension.question_slices[14]` (`R18-D09-Q04`); `task.r19_extension.question_ids[14]` (`R18-D09-Q04`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Bind protocol/outcome/report and shared cohort. Positive discriminator: Same cohort retains reports but one ancestry. Adversary: Registry, preprint, article, correction counted as four studies. Removal: Drop lineage link; independence fails.
  `task.r19_extension.question_slices[15]` (`R18-D09-Q05`); `task.r19_extension.question_ids[15]` (`R18-D09-Q05`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Group source/evaluator ancestry for independence claims. Positive discriminator: Common outputs count once; narrow recomputation still stands. Adversary: Two models repeat the same supplied data/evaluator. Removal: Drop ancestry binding; independent-support claim fails although arithmetic may pass.
  `task.r19_extension.question_slices[16]` (`R18-D14-Q01`); `task.r19_extension.question_ids[16]` (`R18-D14-Q01`)
- **execute** — Basis-branches owns immutable changed-premise comparisons, ancestry/dependence, bounded search and uncertainty; it consumes qualified external sources without re-deciding their authority. Slice: Do not count common-ancestry releases as independent evidence. Positive discriminator: Shared source/evaluator reduces independence separately from release permission. Adversary: Different formats are presented as independent confirmation. Removal: Drop ancestry check; assurance is inflated.
  `task.r19_extension.question_slices[17]` (`R18-D14-Q03`); `task.r19_extension.question_ids[17]` (`R18-D14-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
