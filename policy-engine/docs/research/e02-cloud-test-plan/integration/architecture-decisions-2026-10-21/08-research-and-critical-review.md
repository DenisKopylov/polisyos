# Research and critical review record

Date: 2026-10-21. Deliverable: three architecture selections and implementation obligations, not code acceptance or formal closure. This record explains the reasoning that changed the design. The normative selections are AD04–06; illustrative names/versions in preliminary researcher proposals do not override those documents.

## Inputs and scope

The complete five-document input set is enumerated in [inputs.json](inputs.json), with lengths, SHA-256 and the Git snapshot against which the bytes were checked. The changing implementer checkout was read only. Source analysis used immutable objects, not a claim that every observation describes its latest working tree:

| Question | Source frame used | Qualification |
|---|---|---|
| HTE | `80f7c18f1295e3d2ecbee7625e52cdcbacca97f2` | Shared adapter/serial ForestDR runtime receipt is newer than the early failed-adapter proposal; bounded runtime success does not establish inference law or the complete consumer chain |
| CAN | `ee2a5d9e508060c6348ce3e1a02511a99a5cf177` | The supplied scoped witness belongs to this source; its preparation comparison is separate |
| B161 | `566d194402dec721d162cff83b4bf2d16442d52e` | Current/history composition, uncertainty persistence and CI-width routing inspected at this frame; no assumption that later code remains identical |
| Previously selected AD01–03 | `b7adafe89423bc6906a5fb86c38e579a381ad2ee` | Reused intent/output/profile boundaries; not reopened |

The original B161 criterion was checked separately from the current author's interpretation: the first assessment of an unknown component, preservation of history, and preservation of another active risk are the relevant property. It does not supply a general ordering of scientific estimates. The CAN manifest projection, contextual tag readers and HTE actual extraction/serialization invariants were inspected rather than inferred from summary labels.

## Research and review sequence

Five direct helpers were used, with no nested delegation: three independent research slices (HTE, CAN, B161), one statistical red-team reviewer, and one protocol/migration red-team reviewer. They were restricted to small source reads, primary-source research and documentation; no tests, backend imports, installations, data scans or numerical workloads were authorized. G reconciled the research, drafted the common contracts, submitted the draft to the two critics, incorporated their delta findings, and performed a final direct critical review. Final editorial/mathematical clarifications are G's own review; they are not mislabeled as another independent runtime or source-acceptance verdict.

| Attack / divergent case | Decision after criticism |
|---|---|
| Finite CATE-derived bounds appear to be a justified ATE interval | Separate computed point, supported native conditional inference and stronger population claim; remove local fallback/widening on the new ABI |
| Blanket refusal of all intervals until an outside statistical authority arrives | Admit a specifically qualified internal native protocol with explicit conditional premises; execution predicates are recomputed, empirical application claims remain separate |
| Callable inference API, method-family name or conservative SE automatically implies valid coverage | Concrete estimator/inference/configuration entries; native route and target law documented; no family-wide acceptance, no coverage theorem from an SE bound |
| Stored mean of predictions is mistaken for the inferential estimand | Bind estimator functional and underlying conditional-effect target separately; no uncertainty claim about arithmetic on already stored bytes |
| Strong population request is silently answered with a selected-row interval | Distinct requested/computed target and guarantee; explicit unsatisfied requested claim |
| Post-selection interval is treated like a fixed-method interval | Same-outcome method/subgroup selection requires a supported selection-valid procedure; otherwise primary output is point-only |
| Self-consistent forged result/basis passes every hash check | Reconcile actual owned attempt/fence and capture; content integrity does not establish execution origin |
| Outcome and verification anchor refer to each other's content hash | Stable pre-output anchor, later output association/receipt; one-way artifact dependencies |
| Old required slots or default aliases bypass the new point-only semantics | Breaking method ABI, one discriminated output, readers-first migration, all current defaults migrated; explicit old replay retains its source qualification |
| Common CAN name implies universal Core/IR semantic compatibility | Share mechanics; select strict expected reader policy from the consumer contract; IR rejection remains meaningful |
| Profile digest proves raw declaration, creation date or producer law | Resolve actual raw manifest and provenance separately; preserve excluded time fields and raw absence/null distinctions |
| Core cache grants IR acceptance, or old selected view grants currentness | Cache/admission binds actual selected association, semantic reader, purpose and relevant authority/time context; reconcile before reuse |
| A true assessed risk 1.0 is treated like an unknown placeholder | Typed numeric-free unassessed state; first-assessment relation cannot lower an assessed value |
| A declared dependency list omits an inconvenient source | Inventory from the actual selected plan/config/source graph, or independent reconciliation; complete supplied subset is not completeness |
| CI-width score becomes confidence, a stop rule or cross-quantity ordering | Explicit relative-imprecision convention, restricted candidate ordering and comparable profiles; never authority, completeness or pruning by itself |
| Zero estimate, additive origin shift or malformed width fabricates a favorable score | Native assessment survives separately; score unavailable where reference scale is unestablished; no epsilon/NaN/default confidence |
| First CAS arrival becomes scientific superiority | Preserve competing successors, mark contested current component, advance revision and invalidate stale current projections |
| History/current conflation or one failed intake wipes unrelated evidence | Separate immutable history, per-obligation current view and active constraints; scope each failure; as-of and live meanings differ |

The final solo pass added explicit fixed-frame covariance reasoning, pinned the initial native protocol to the receipt's EconML 0.17.0 instead of floating public documentation, clarified estimator versus estimand, bound the routing score's zero/reference meaning, and made conflict-driven projection invalidation explicit. These are architectural clarifications; none is a runtime PASS.

## Primary-source basis

Sources below were consulted as protocol/method precedents. They do not establish that PolicyOS implements the pattern or that an application dataset meets its assumptions.

- [EconML 0.17.0 inference implementation](https://raw.githubusercontent.com/py-why/EconML/v0.17.0/econml/inference/_inference.py): native mean-point/SE/interval protocol and explicit point-only absence. Its native conservative procedure is distinct from PolicyOS's local CATE-dispersion fallback.
- [EconML 0.17.0 effect/ATE implementation](https://raw.githubusercontent.com/py-why/EconML/v0.17.0/econml/_cate_estimator.py): effect aggregation over supplied X and inference availability. [Public PopulationSummaryResults documentation](https://www.pywhy.org/EconML/_autosummary/econml.inference.PopulationSummaryResults.html) served a 0.16.0 label at access, so it is explanatory rather than the selected version identity.
- [Wager and Athey, causal forest inference](https://doi.org/10.1080/01621459.2017.1319839), [Chernozhukov et al., double/debiased ML](https://academic.oup.com/ectj/article/21/1/C1/5056401), and [Foster and Syrgkanis, orthogonal statistical learning](https://arxiv.org/abs/1901.09036): method-specific conditions must accompany an inference claim; a method family does not prove those conditions for a concrete run. These were considered in the research, not imported as universal eligibility rules.
- [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785): repeatable canonical representation has a defined input domain. PolicyOS's tagged format remains its own protocol; no claim of JCS compatibility.
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/): distinguish an entity, its generating activity and responsible agent; lineage and revision do not automatically prove truth or authority.
- [Microsoft event-sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing): immutable events and materialized views can coexist, with concurrency and complexity costs. Reuse PolicyOS's owner/persistence instead of introducing another event store.

The covariance inequality in AD04 is direct mathematical reasoning for fixed prediction errors, not an empirical validation or proof of estimated-SE calibration. The relative-width rule in AD06 is an explicitly chosen internal convention, not a discovery of a universal risk measure. This distinction is essential to avoiding authority by citation.

## What remains deliberately outside the selected contracts

Population sampling/transport, causal identification for actual data, empirical calibration, lawful permissions and live custody/currentness need actual applicable evidence. No source citation or new field creates it. A supported future assessed-to-assessed scientific updating law may be added as a separate relation profile; this packet selects only first assessment. Unknown-legal-admission PAG remains pending its own verified packet. Historical closures, including B198, are unchanged.

There is no unresolved architectural requirement to obtain external permission to write typed outcome branches, implement the selected conditional protocol, keep CAN reader policies distinct, produce a real first assessment or migrate consumers. Missing internal bridges must be implemented, not renamed external inputs.

## Verification of this delivery

Only lightweight documentation checks are appropriate here: complete output-file inventory, local link resolution, JSON parsing, exact input-blob hash readback, whitespace/diff checks, attached branch and ordinary commit/publication readback. Product tests, numerical inference, imports/builds, package installation, production reads and integrated replay remain **UNRUN in this architecture session**. The acceptance/removal matrices in AD04–06 are instructions for the implementation lane, not evidence already obtained.

Before publication, the complete package-directory inventory was checked: six Markdown documents and one JSON manifest. All relative document links resolved, the manifest parsed, all five named input files matched their immutable Git blobs by length/SHA-256, and all four source-frame commit references resolved. These checks establish document integrity, not product behavior. Ordinary Git hook selection and publication readback are recorded in the task's tool outputs; no hook bypass is authorized by this packet.

Pattern pass: P04/P05/P07/P08/P10/P14/P27/P28/P29/P31/P32/P35/P37/P38/P40/P41. Keep source facts, selected design, conditional methodological premises and future verification distinct. Architecture selection changes no finding outcome and grants no code acceptance.
