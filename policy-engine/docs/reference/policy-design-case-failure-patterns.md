# Policy Design Case Failure And Repair Patterns

Owner: `team-policyos-runtime`
Source of truth: the root `AGENTS.md` and this register.

This is the on-demand register behind the root `AGENTS.md` failure lens. Use it when changing Policy Design Case, governance, evidence, runtime quality, producer, API, dashboard, export, or research-plan behavior.

## How To Use

- Before design: identify which pattern IDs the change could create or close.
- During exploration: record existing anti-patterns found in touched code instead of treating them as background noise.
- During implementation: prefer the correct pattern in the register over new contract vocabulary.
- Before closeout: mention any relevant pattern IDs in the PR or final summary when the change is governance-significant.
- Keep this register compact. Add a new row only for recurring or systemic failures; move long examples to ADRs, plans, or backlog docs.

## Capability Reality Check

Capability = `typed contract/artifact + producer + persisted artifact/event + orchestration bridge + consumer + verification + external/audit/API/dashboard surface or explicit out_of_scope + negative/e2e semantic test`.

If any part is missing, do not call the capability implemented. Mark it precisely as `absent/unallocated`, `contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`, `surface_out_of_scope`, or `semantic_test_missing`.

| Label | Meaning |
| --- | --- |
| `absent/unallocated` | **Weaker than every label below.** No admitted prerequisite chain exists at all: no typed contract, no owner, no producer, no consumer — and no canonical owner has been appointed. Use it when the stronger labels would *overstate* what is present, and say which prerequisite is missing. Prose, a research contract, or a plan section is an input, not a chain: a substantive Markdown procedure is still `absent/unallocated`, never `contract_only`. |
| `contract_only` | Type/schema/status exists, but no producer, consumer, or workflow uses it. |
| `producer_missing` | A consumer expects an event/artifact, but no deployed producer emits it. |
| `artifact_missing` | Producer logic exists, but the artifact/event is not persisted, queryable, or replayable. |
| `bridge_missing` | Producer and consumer both exist, but orchestration does not connect them. |
| `consumer_missing` | Artifact/event is produced and persisted, but no downstream reader acts on it. |
| `verification_missing` | The chain is wired, but no automated check proves the end-to-end behavior. |
| `implemented_but_not_orchestrated` | A component works in isolation but is not integrated into the runtime workflow. |
| `surface_missing` | Internal capability exists, but API, dashboard, audit, export, or public surface cannot inspect it. |
| `surface_out_of_scope` | No external surface is intentionally provided; the rationale and owner are documented. |
| `semantic_test_missing` | Structural tests pass, but no test proves content-level adequacy or correct authority semantics. |

`semantic_test_missing` capabilities cannot graduate to `implemented`.
Semantic tests should live next to the relevant unit/integration suite, or in a
dedicated semantic/regression fixture when the behavior spans producers. They
must verify content-level adequacy, not only constructor validity, field
presence, checksum integrity, or schema compatibility.

## Register

| ID | Anti-pattern | Correct pattern | Diagnostic question | Closure move |
| --- | --- | --- | --- | --- |
| P01 | Contract-only capability | Demonstrated capability chain | Does the typed event/status/packet flow from real input through producer, persisted artifact/event, bridge, consumer, visible effect, and negative test? | Prove the full chain before claiming capability. |
| P02 | Component sophistication with thin orchestration | Bridge-first orchestration | Do mature components exchange binding artifacts, or only coexist? | Add explicit workflow bridges, especially evidence -> `ClaimRecord` -> lifecycle. |
| P03 | Internal richness with poor external surface | Multi-audience projection | Can PUBLIC/REVIEWER/EXPERT/MACHINE surfaces inspect what the internals know? | Expose typed projections for assurance, invariants, uncertainty, status, and contestability. |
| P04 | Status enum proliferation | Composed status lattice | How does the new status combine with support, publishability, readiness, faithfulness, freshness, admissibility, validity, overridability, and review action? | Keep local statuses, but define cross-status composition rules and mixed-status tests. |
| P05 | Authority dilution | Purpose-scoped authority boundary | Can downstream code confuse projection/diagnostic/package/export with authority? | Boundary/public/closeout artifacts must declare `authoritative_for` and `may_not_use_for`, with consumer-side enforcement. |
| P06 | Shim drift / canonical ownership ambiguity | Sunset-enforced canonical ownership | Are anchors or tests using deprecated compatibility paths or accepted legacy behavior? | Use canonical owners; preserve shim sunset dates, behavioral legacy retirement criteria, and deprecation warnings. |
| P07 | Schema versioning without rule evolution | Rule-versioned semantic replay | Can old closed cases replay under the exact schemas, taxonomies, and rules that closed them? | Store rule/taxonomy version refs and add replay, migration, grandfathering, and reissue behavior for tightened rules. |
| P08 | Time semantics fragmentation | Time-role algebra | Are legal, policy, data, observation, valid, transaction, ingestion, publication, detection, forecast, freshness, retention, and replay times distinct? | Model time roles explicitly and block, transform, project, or limit mismatches. |
| P09 | Implicit soft gates | Owned warning lifecycle | Do warnings have owners, aging rules, accepted-deficit policy, escalation rules, and closeout/publication impact? | Convert soft gates into owned warning lifecycles; test warning aggregation and aging. |
| P10 | Structural-only validation | Semantic adequacy validation | Does "pass" mean semantic adequacy, or only required fields/checksums exist? | Add semantic probes, expert-disagreement fixtures, negative controls, or adversarial cases. |
| P11 | Failure-only memory | Balanced learning memory | Does cross-run learning capture successes as well as failures? | Add success-pattern retrieval/reuse where failure lessons are used. |
| P12 | Producer fragmentation | Producer handshake protocol | Do Lex/Fabric/Scholar/Foundry/Scientist coordinate before post-hoc conflict detection? | Use shared concept/scope handshakes before producer emission where meaning must align. |
| P13 | Contract gravity well | Proportional governance | Does a required gate/artifact justify its marginal cost for producing a valid PDC? | Make requirements authority-level-gated or optional unless their value is load-bearing. |
| P14 | Raw evidence count inflation | Effective independence accounting | Do multiple sources collapse through shared data, authors, methods, lineage, prompts, institutions, or assumptions? | Report effective independent evidence count and collapse reasons before claiming strong support. |
| P15 | LLM speculation laundering | Candidate-to-authority firewall | Can LLM-generated risks, claims, legal readings, participation claims, or method choices become authoritative without producer evidence? | Keep LLM output as `candidate_unverified`, `rejected_speculation`, `typed_blocker`, or `limitation` until producer authority validates it. |
| P16 | Epistemic-regime laundering | Gate-owned regime declaration | Can a design claim risk-regime precision without evidence, or hide available evidence behind precaution/robustness language? | Classify epistemic regime on the A-side, per claim, with asymmetric false-precision penalties and downgrade/upgrade firewalls. |
| P17 | Decomposition / partial-equilibrium laundering | Coupling-gated composition | Is whole-design authority assembled from parts before decomposition validity and cross-effects are grounded? | Prove modular or near-decomposable boundaries before composing authority; entangled cases need system-level evidence or downgrade. |
| P18 | Streetlight measurability laundering | Measurability adequacy declaration | Are measurable proxies optimized and projected as if they exhausted the policy value? | Represent unmeasured/qualitative constructs as limitations or ignorance, with proxy validity and value-loss disclosure. |
| P19 | Aggregation laundering | Subject-granularity and aggregation validity | Does evidence at one aggregation level close claims at another level without ecological-error checks? | Emit aggregation-validity records and block or limit individual/group/jurisdiction scope drift. |
| P20 | Normative choice laundering | Authorized value-choice provenance | Does the system or LLM silently choose objectives, social weights, or value tradeoffs? | Require authorized value inputs, show alternative schedules, and expose multi-principal incompatibilities rather than resolving them silently. |
| P21 | Capacity-feasibility laundering | State-capacity grounded feasibility | Does a design assume administrative, fiscal, enforcement, or delivery capacity that the actor lacks? | Ground capacity assumptions and make absent capacity a blocker, limitation, or design-to-build-capacity obligation. |
| P22 | Mandate-legitimacy laundering | Mandate and legitimacy authority | Are goals or social weights treated as authorized without participation, legal mandate, or governance provenance? | Emit mandate/legitimacy records before objectives and value weights can close. |
| P23 | Stakes and commitment laundering | Stakes/reversibility-gated floors | Are low-stakes or reversible evidence floors applied to irreversible, high-stakes, or catastrophic commitments? | Classify stakes, reversibility, and option value; raise floors or require adaptive/precautionary design when needed. |
| P24 | Strategic-response laundering | Response-model validity | Are pre-policy effects transported into a post-policy world whose incentives and behavior change? | Model Goodhart/Lucas/performativity/capture response or limit claims and route response back into system dynamics. |
| P25 | Search-control laundering | Replayable search frontier boundary | Is a search frontier, best-so-far candidate, or control-plane summary projected as exhaustive, replayable, or authoritative? | Persist `SearchLedger`, search incompleteness, budget cutoffs, and frontier provenance; keep frontier support separate from producer evidence. |
| P26 | Responsibility-integrity laundering | Mandate-bounded human decision integrity | Does the system shift responsibility to a human who was not informed enough to approve, or does the human shift responsibility back to "the AI"? | Require mandate-bounded `HumanDecisionRecord`, active choice for high-stakes/value-laden decisions, disconfirming evidence, and responsibility-integrity checks. |
| P27 | Parallel re-implementation / canonical-owner bypass | Owner-first placement | Does an existing module already own this concept, or is new logic (a type, engine, gate, planner, or fixture) being created beside it — often named by slice/plan (`gy_*`, `slice0_*`) instead of by domain? | Locate the canonical owner by concept (grep the concept root across the owning packages) and extend it; route slice work into the owner and delete the parallel copy. Watch the dual symptom: orchestration over-concentrated in one slice god-file while thin wrappers proliferate — both are placement-by-slice-identity, not by owner. |
| P28 | Additive migration / un-strangled legacy | Strangle-fig replacement | After adding the better approach, can the superseded path still be reached by default (a fix gated behind a default-off flag, legacy left callable, zero deletions on a "replace/subordinate" change)? | Fence or delete the predecessor in the same change, flip the default to the corrected path, and record the sunset/guard so the two cannot coexist. A replacement that only adds a layer over the legacy default has not migrated anything. |
| P29 | Authorial proof / self-attested artifact | Recompute-from-live evidence | If the committed proof/benchmark/closure artifact were deleted, would the validator reproduce it from a real run — or does it only check shape/refs over a hand-authored payload (placeholder ids, round `…T00:00:00Z` times) or a strawman fixture corpus where the metric is vacuous, or only confirm that marker strings / field names are present while the runtime property it guards is broken? | Emit proofs from the real path; validators must re-derive the claim from live code/artifacts and fail on drift; benchmark substrates must be representative (real corpus or a declared `surface_out_of_scope` rationale), not trivially separable fixtures; the drift-check/self-check itself must FAIL on a corrupted artifact (verify the verifier) — a `--corrupt-field-drift-check` that returns success on a corrupted input is decorative. A gate/contract for a semantic property (a runtime cap, a round-trip, a strangle, a promotion rule) must **exercise the real runtime** (import + run the real path and assert the property holds/fails), not confirm that marker strings or field names are present; prove it with the *remove-the-property-keep-the-markers* probe — if the gate stays green when the runtime semantic property is deleted but its marker strings remain, the gate is form-based and must be rewritten to behavioral. **Stopping point (do not regress infinitely):** a verifier is *complete-by-construction* when it is GENERIC over the actual source of truth — it derives its check set from the runtime's own rejection reasons / the artifact's own schema fields / the actual objects (no hand-enumerated list), walks them recursively (including list elements and nested objects on a fully-non-default sample), and its exemptions are GENUINE constraints (a "justified default-only" field must be truly type-constrained, e.g. a `Literal`/discriminator, not a `str` loophole). Once it is generic with genuine exemptions, coverage of FUTURE additions is governed by THIS rule + review — not by recursively verifying the verifier. An audit that can only construct a HYPOTHETICAL future field/root that would escape a GENERIC mechanism (rather than an actual present gap or a non-generic enumerated set) is a GO, not a NO-GO; do not add another meta-level. |
| P30 | Provenance-named modules (plan/slice/wave-scoped file names) | Domain-function naming with discovery breadcrumbs | Does the module/file/symbol name describe the capability it owns, or only the plan/slice/wave that created it (`gy_*`, `slice0_*`, `wave5_*`)? Would an implementer grepping by concept find it and its relatives, or re-create them? | Name modules by the function they own, not their birth plan (`workspace_loop.py`, not `gy_loop.py`). If a provenance prefix is truly unavoidable, the module docstring must name the canonical owner(s) it extends and link related modules so the next implementer reads them before writing a parallel file. Provenance naming is the upstream enabler of P27. |
| P31 | Instance-patching over structural invariant (enumerate-and-route) | One chokepoint/invariant for the whole class | Is the fix closing the one named site while a sibling consumer/intake/surface of the SAME class stays open — so a synonym, another consumer, or another producer reopens it next round? | When a defect is an instance of a class (e.g. "authority emitted from unverified evidence", "bytes leave a surface without the admission gate"), close the class with ONE structural chokepoint/invariant — single intake AND single emission — not a per-site patch. Prove no sibling bypass by enumerating every write/read/intake of the class and grepping that each routes through the chokepoint. |
| P32 | Trust-by-form (presence/shape/string/keyword/self-attestation = permission; absence = permission) | Resolve-bind-verify evidence intake, fail closed on absence | Does an authority/promotion/Ring-2 decision admit evidence because a ref/field is PRESENT, well-SHAPED, name/keyword-matched, or self-stamped with a verifier role — or because it RESOLVES to a committed artifact, CONTENT-BINDS by hash to THIS claim/graph/program/port, and carries VERIFIER (non-producer) provenance? Does absence grant, or fail closed? | Admit evidence for an authority decision only via resolve + content-bind + verifier-provenance; presence/shape/keyword/string/inline/self-attestation is not evidence; unresolved/mismatched/missing → cap/block, never grant. This operationalizes P05/P10/P15 for reference-based evidence and is the unifying root behind `model_construct` bypass, synthetic-as-measurement, `no_authority->allowed`, keyword-feedback, and presence-of-ref laundering. |
| P33 | Witness-as-spec / teaching-to-the-test | Property fix + adversarial-variant self-generation | Does the fix make the EXACT acceptance/audit probe pass while a near-variant (synonym, malformed input, present-but-fake ref, cross-bound id, another consumer) re-breaks it? Is the probe being treated as the specification? | Fix the general property the probe samples, not the probe. Before claiming done, self-generate and pass adversarial variants of every probe (synonym, malformed, present-but-fake, partial-bind, sibling consumer). An audit probe is a witness, never the spec. |
| P34 | Premature-green via uncompleted exclusion | Completed isolation before exclusion | Is a failing test/lane excluded by calling it "honest-empty" or "unrelated / pre-existing dirty worktree" WITHOUT a completed revert/stash isolation proof? Could the change itself have caused it, or is a broken downstream state (inconsistent manifest, blocked-used-as-conversion) being asserted honest? | Complete the isolation — revert/stash only the change and confirm the failure is independent — before excluding it. Prove an "honest" downstream state is actually honest (consistent top==summary status, no laundering), not merely relabeled from a fail. |
| P35 | Sampled-denominator generalization | Full-set enumeration by script | Is a SET-LEVEL fact (a count, a distribution, "all of them are X", "the field is always null") derived from opening one member, a truncated `grep -A N`, a frontmatter summary, or a **search index / connector / ranked query** — rather than from walking the whole set? Would the claim change if the set had one more member than you looked at? Can you name the **path denominator** and the **file-type denominator** the number was measured over? | Produce every set-level fact with a script that walks the complete set and prints the denominator, then quote the denominator with the fact. Never generalize from a sampled member, and never let a truncated context window define a set boundary. **An index is not a denominator in either direction:** a ranked/indexed result cannot establish an absence (it may not have looked), and it cannot establish a positive count either (it may omit a member the tree contains) — settle every literal census by a complete walk at the pinned ref (`git grep` over the ref), and state both denominators beside the number. Applies to enums, registries, manifests, pools, finding registers, and file censuses alike. |
| P36 | Authority by adjacency | Cite the finding by ID, not the prose around it | Is a downstream document relying on a sentence from an authoritative source that was NOT the source's finding — an aside, a motivating example, an explanatory paraphrase — and treating it as carrying the source's authority? Can you name the finding ID that the relied-upon statement IS? | Cite the finding by its ID and reproduce set-level and arithmetic claims from the pinned owner rather than from the citing document. A document is authoritative only for what it establishes; the prose around a finding carries the document's tone, not its warrant. When correcting such a chain, follow every dependent BINDING (grep the key/ID), not only the narrative that reads wrong. |
| P37 | Declared gate predicate | Predicate-provenance classification, fail closed on a declared premise | The contract names a gate. For each predicate that gate DEPENDS ON — completeness of a declared basis or denied-use set, neutrality of a shared artifact, a consumer's "would the action have changed?", the arrival of an expiry/correction event, adequacy of a named discriminator, membership of a frozen set — is it RECOMPUTED by the procedure, or SUPPLIED by the party the gate is meant to constrain? Would the gate still return green if the declaration were false? Is the deciding predicate itself frozen at admission, or can it still be chosen after the transaction begins? | Label every load-bearing predicate as exactly one of `recomputed` (derived from a controlled artifact/history), `independently_reconciled` (observed against a second, non-producing source), `consumer_asserted`, `institutionally_supplied`, or `not_established` — and freeze the label at admission. A gate whose decisive predicate is `consumer_asserted`, `institutionally_supplied`, or `not_established` must fail closed or degrade its claim; it may not return a positive. This is `S0-K06` applied to the gate's own predicate rather than to the statement it guards: the authority band forbids a declared unknown INSIDE a gate exactly as it forbids one inside a published claim, and a candidate-grade predicate cannot carry an authority-grade gate. Prove it with the *falsify-the-declaration* probe — make the declared premise false while leaving its declaration intact; if the gate stays green it is testing the declaration, not the property. |
| P38 | Proxy gate — the implementation stands in for the property | Property-constructed gate with a named divergent case | A gate is built to decide some property, but it turns on a cheap adjacent stand-in — an exit code, a field's *name*, a `file:line`, a byte diff, a program root, a prefix. The stand-in agrees with the property nearly everywhere and diverges **precisely at the boundary the gate exists to police**, so the gate is confidently wrong exactly when it matters. Can you name one case where the property holds and the implementation says no, or the property fails and the implementation says yes? | Before writing or accepting a gate, state the property in one sentence, state what the implementation actually tests, and **name one divergent case**. If none can be constructed, the implementation *is* the property. If one can, either the gate consults the context that distinguishes them, or the divergence is recorded as a declared, bounded limitation — never left implicit. Falsifier: replace the proxy while holding the property fixed, then change the property while holding the proxy fixed; a gate that tracks the proxy rather than the property is a P38 instance. This applies to a procedural rule in a plan exactly as it applies to code. |
| P39 | Budget that counts the record it mandates | Cap over mechanism paths, with the mandatory record set named and excluded | A task declares a path or size cap, and the same governing instructions force it to write artifacts the cap counts — the plan that must record each new terminal duration, the journal, the register/report/inventory family, the test that pins the very constant being changed. The cap is therefore short by the number of its own mandatory companions, and the task stops on ARITHMETIC rather than on its property. Does the declared budget reserve a slot for every artifact this task's own binding instructions force it to write? | Count **mechanism** paths only; name the record companions explicitly and hold them outside the count. A path that exists only because another path changed — a test pinning a constant the change moves, a generated report, a plan line the binding instruction demands — is not an independent path. Falsifier: subtract the mandatory companions from a stopped cluster's measured cut; if the remainder fits the declared cap, the stop was arithmetic, not scope. Never resolve it by splitting one mechanism across commits to fit the number — that buys three reviews of one thing and proves nothing extra. |

Notes:

- P15 extends P05 for LLM-generated content. Both require consumer-side
  `authoritative_for` / `may_not_use_for` enforcement, but P15 also needs
  source classification such as `deterministic_producer`, `llm_candidate`,
  `llm_critic`, and `llm_drafter`.
- Build-time validity without runtime enforcement is a P01/P10 variant. A
  proof, benchmark, or offline validator is not runtime authority until the
  runtime path consumes it and fails closed when it is absent or failing.
- P27 is the net-new sibling of P06 and P12. P06 covers drift toward a
  deprecated compatibility path; P12 covers producers that do not coordinate;
  P27 covers building a *fresh* type/engine/gate beside a live canonical owner
  instead of extending it. Slice/plan identity (`gy_*`) is not a module
  boundary.
- P28 extends P06's sunset discipline from compatibility shims to whole-approach
  replacement: when the new path lands, the predecessor must be deleted or
  guarded and the default flipped, not left as the reachable default.
- P29 is the evidence-artifact dual of the build-time note. A proof is authority
  only when it is *emitted by* the run it claims and the validator *recomputes*
  it from live code/artifacts. A hand-authored proof packet, or a closure metric
  computed on a strawman fixture corpus, reproduces the very `authorial-refs`
  laundering it is meant to prevent.
- P30 is the upstream enabler of P27 (and so of P28). A module named for its plan
  (`gy_loop.py`) hides its function, so the owner-first grep misses it and the next
  plan re-implements `workspace_loop` again beside it. Naming by function is the
  cheapest structural defense against parallel re-implementation: it makes the
  existing owner self-evident, so reuse/extension becomes the path of least
  resistance. The fix is not cosmetic — it changes which file the next implementer
  opens first.
- P31/P32/P33 came from the GY-G composition saga (~7 NO-GO rounds). They are the
  meta-lessons: each round flipped the named probe (P33) but a sibling consumer of the
  same class reopened it (P31), because the gate trusted a ref by form rather than
  resolving it (P32). The break-the-cycle move is always the same: turn the instance fix
  into one structural invariant (single intake + single emission), admit evidence only by
  resolve+content-bind+verifier-provenance, and self-generate adversarial variants before
  declaring done. P34 is the partner: do not let an excluded "honest/unrelated" failure
  close the loop without a completed isolation.
- P35 and P36 are **research/review-process** patterns, added 2026-08-04 from the
  INT-R1/R9/R10 wave. They look similar and are not: they have different causes and
  different closure moves, which is why they are two rows.
  **P35 is about denominators.** Three orientation packs in that wave asserted set-level facts
  measured from one sampled member — an enum said to have 14 members had 15 (a truncated
  `grep -A 16` cut the last one), a field said to be uniformly null was null in 11 of 15
  manifests, and an authority label read off one file was three labels across fifteen.
  Every instance came from generalizing a sample. The fix is mechanical: walk the whole set
  with a script and print the denominator.
  **P36 is about warrant.** An independent audit correctly established that the ledger has no
  cross-scope composition. In explaining *why* that mattered, it wrote in passing that three
  scopes each open "with a fresh δ" — an aside, not a finding, and arithmetically wrong: it
  conflates a scope's root budget with what a check allocates under a telescoping schedule.
  Three downstream documents, including this project's own gap register, adopted the aside as
  established, and the chain reached four substantive documents before a later audit
  enumerated the live registry and refuted it. No enumeration would have caught this, because
  the failure was not a denominator — it was inherited warrant. The fix is to cite the finding
  by ID and recompute arithmetic from the pinned owner.
  **Corollary, learned when correcting that chain:** repairing the narrative is not repairing
  the binding. A correction that fixes the prose but leaves `bound_*` frontmatter keys, YAML
  headers, or ID references pointing at the superseded artifact has not landed. Follow the
  correction by grepping the KEY, not by reading for what sounds stale.
  **Index rider, added 2026-08-08 from the OPS-R14/PAO-R36/PAO-R4/S0-GAP-02 audit wave.** Two
  independent audits applied P35 correctly to their ZERO claims — refusing to convert a connector's
  empty result into a proved absence — and then converted that same connector's candidate set into a
  complete denominator for their POSITIVE counts. Both were wrong. A complete tree walk at the pin
  gives lowercase `supersede` = 48 files / 215 matching lines / 260 occurrences (reported 47/203/246,
  and the original commission's 48 was right) and `legal_hold` = 2 / 7 / 8 (reported 2/4/5). The
  connector had returned 49 candidates where the tree holds 50; the two uppercase-only exclusions the
  audit made were themselves correct, so the arithmetic was sound on an incomplete set. P35 is
  symmetric: an index establishes neither a zero nor a positive.
  **Holder rider, added 2026-08-17 from the wave-4 consolidation — P35 composed with P37.** A complete
  walk settles the number; it does not settle *who may cite it*. Four wave-4 packages carried census
  results their own environment could not execute, and two families of overclaim survived into terminal
  text ("settled true zeroes from a complete walk"; "settled because the architect supplied a walk").
  Beyond the two denominators, a set-level record must therefore also name **the party that executed
  the walk** and carry the P37 label **relative to the holder making the present claim**. The same
  numeric tuple is legitimately `recomputed` for the holder that ran it and `institutionally_supplied`
  for one that did not — and **an `institutionally_supplied` census cannot settle a zero**. The facts
  were never in doubt in that wave; the attribution was, so the repair is to name the executing party,
  never to strip the numbers. All thirteen wave-4 tokens reproduce exactly at the pin in both
  denominators, with positive and negative controls; a zero reported without a positive control is not
  a measurement, and two harness defects were caught that way before any figure was retained.
- P37 is the **OPS-R14/PAO-R36/PAO-R4/S0-GAP-02 wave's single cross-task result**, added 2026-08-08.
  Eleven blocking findings across four independent audits of four unrelated subjects reduced to one
  shape: the contract names a gate, and the predicate that gate turns on is supplied by declaration
  rather than constructed by the procedure. PAO-R4 made a firewall violation classifiable once the
  basis, denied-use set and material-contribution counterfactual are trusted, without making their
  completeness decidable. S0-GAP-02 permitted a shared substrate `N ∪ B` without proving
  answer-neutrality, and defined `Compatible(x,y)` over an unbounded predicate language where a
  syntactically valid bundle (`event_count >= 0` as the mandatory positive, an unsatisfiable
  mandatory negative) accepts every trace. PAO-R36 made `Complete(R)` a precondition for appending a
  record that `R` contains, and left the predicate deciding whether a member needs a synchronous
  receipt mutable after the transaction began. OPS-R14 checked the fail-closed consequence of an
  expired dependency without measuring that the expiry event was ever delivered. None is a defect of
  care; each package is strong. The common cause is that the band lens had been applied to
  statements and never to the predicates of gates.
  **Fixed-point corollary, added 2026-08-17 from the wave-4 consolidation — the wave's second result,
  and it came out of the repairs rather than the research.** *Every repair that preserves a positive by
  adding a condition creates a new gate predicate, which must itself be classified. There is no fixed
  point until the condition is constructed at the level of the property it names.* Two packages reached
  this independently. OPS-R14 split a falsifier so that a positive survived behind "an independently
  reconciled **non-producing** authoritative record", then established non-producing character by
  comparing instrument bytes and receipts — a successor-controlled record agrees perfectly and takes
  the positive. S0-GAP-02 added `machine_observed`, whose positive eligibility turns on a *declared*
  frozen scope and second observer. Both moved the unconstructed premise one level down and left the
  positive alive. The diagnostic is a class check, not a quality check: content agreement can never
  establish provenance, so no amount of strengthening the comparison closes it — when the added
  condition names a different **measurement class** than the evidence constructs, withdraw the positive
  rather than commissioning another round. This retro-explains the GY-G saga's ~7 NO-GO rounds
  (P31/P32/P33): each round satisfied the named condition and a sibling reopened the class.
  Closure signal for any added condition: assign one registered label, name the evidence source and the
  non-producing observer, construct the property rather than its marker, and falsify the condition while
  keeping its declaration intact.
  **The five labels are fixed; refinements are sub-annotations.** S0-GAP-02 proposed a six-way
  vocabulary (`machine_observed`, `attested`, `institutionally_accepted` beside the registered five) and
  its verifier correctly showed the refinement does not widen the non-positive set. It is still not
  adoptable as *labels*: `machine_observed` is positive-eligible only conditionally — a subtype of
  `recomputed`, **or** `independently_reconciled` when retained by a second non-producing observer, with
  bare producer telemetry mapping to `not_established` — and a gate must answer positive-eligibility by
  fixed lookup, never by evaluating a declared condition (which is this row, one level down). Record
  the three genuine distinctions as **required sub-annotations on the registered class**: they qualify
  the evidence, are carried beside the label, and never alter positive-eligibility.

- P38 is **P37 seen from the consumer's end rather than the producer's**, and the two are kept apart
  deliberately. P37 asks *who supplied the predicate* — a declared premise the gate cannot recompute.
  P38 asks *what the implementation actually turns on* — a stand-in the gate can compute perfectly and
  which is simply not the property. A P37 gate is green because someone said so; a P38 gate is green
  because it measured the wrong thing correctly. **Why it recurs:** the proxy is almost always what is
  already computable at the gate's call site — an exit code the harness already has, a field name
  already in hand, a line number the AST already emits, a diff the tooling already produces —
  while constructing the real predicate needs context the call site does not yet carry.
  Four measured instances are catalogued in `docs/plans/active/layer3-slices/GY-engine-subordination.md`
  §3.5.14, with two further applications at that plan's hash owner and its run-directory
  address-versus-identity class, and one in the Atlas plan's Execution Doctrine.
  **Corollary for architect and reviewer instructions.** A stop rule keyed to a number, a list, or a
  directory *the architect supplied* is a proxy gate by construction: key stop rules to the property
  ("stop if something changed that the named mechanism does not explain"), never to the architect's
  arithmetic. Five stops in the `GY-DEFC-3` family were caused this way. The wave-4 consolidation added
  four more, all architect-side and all caught by agents rather than by the architect: a 40-character
  commit SHA extended by hand from a 9-character prefix (a prefix is a proxy for an identity — resolve
  it, never complete it); disposition *occurrences* counted as ledger *rows*, where every summary
  exceeded that package's own finding total; a line-anchored `^field:` regex matching inside a fenced
  block where a document **quoted** a field rather than declaring it; and a frequency table stated
  without its measure, which moved materially once fenced blocks were excluded. The cheap general
  defence is the **denominator check**: before reporting a count, confirm it sums to a total the
  document already states.

**`P39` is an architect-side pattern, and its signature is a histogram, not an incident.** One
cluster overrunning its cap is an estimate; sixteen clusters overrunning by **exactly one** is a
systematic omission applied sixteen times. Before treating a cap overrun as scope creep, plot the
deltas across the whole set: a mode at `+1` means the budget forgot a mandatory companion, and
raising each cap by one, cluster by cluster, pays the same correction repeatedly instead of once.
The cost is not administrative. A `DS5-C18b-R1` candidate that had closed a `P33` variant — a
scoped provider key built by raw NUL concatenation, so two legal tenant/user tuples collide — plus
four hostile-boundary cases, at `32/32` focused green with typecheck, lint, build and architecture
checks green, was preserved and **forward-reverted** because closing it required updating two tests
that pinned a stale constant. A tenant-isolation repair was withdrawn to satisfy a number.

## Grounding Anchors

These are navigation hints, not complete examples. Keep long analysis in ADRs,
plans, or backlog docs.

| Pattern | Useful anchors |
| --- | --- |
| P01 | `src/polisyos/scientist/governance/continuous/monitors.py`, `src/polisyos/ddm/integration/monitor.py` |
| P02 | `src/polisyos/scientist/evidence/claims/models.py`, `src/polisyos/ir/analytics/*`, `src/polisyos/runtime/quality/semantic_binding.py` |
| P03 | `src/polisyos/core/contracts/runtime.py`, `src/polisyos/runtime/http/services/control/response_shapes.py`, `packages/runtime-api-client/` |
| P04 | `src/polisyos/runtime/quality/scorecard.py`, `approval.py`, `phase_barriers.py`, `src/polisyos/scientist/validation/claim_support.py` |
| P05 | `src/polisyos/runtime/quality/authority.py`, `projection_semantics.py`, `public_export.py`, `authority_reconciliation.py` |
| P06 | `architecture/shims.toml`, `src/polisyos/scientist/evidence/_shim.py`, `src/polisyos/scientist/methods/_compat.py` |
| P07 | `src/polisyos/runtime/quality/schema_compat.py`, `architecture/production_quality/schema_compatibility.toml`, `src/polisyos/scientist/methods/research_dag/replay.py` |
| P08 | `src/polisyos/runtime/http/services/temporal.py`, `src/polisyos/core/contracts/runtime.py`, `src/polisyos/ir/governance/temporal_logic.py` |
| P09 | `src/polisyos/scientist/validation/decision_validity.py`, `src/polisyos/runtime/quality/effective_mode.py`, `src/polisyos/runtime/quality/scorecard.py` |
| P10 | `src/polisyos/core/audit/verifier.py`, `src/polisyos/scientist/validation/citation_faithfulness.py`, `tests/fixtures/production_quality/` |
| P11 | `src/polisyos/scientist/orchestration/memory/failure_lessons.py`, `src/polisyos/scientist/methods/search/lessons.py` |
| P12 | `src/polisyos/runtime/quality/semantic_binding.py`, `src/polisyos/scientist/cross_graph/compiler.py`, `src/polisyos/scientist/cross_graph/conflict.py` |
| P13 | `src/polisyos/runtime/quality/formal_invariants.py`, `src/polisyos/runtime/quality/invariants.py`, `src/polisyos/runtime/quality/scorecard.py` |
| P14 | `src/polisyos/foundry/methods/consensus.py`, `src/polisyos/foundry/methods/equivalence/`, `src/polisyos/scholar/search/models.py` |
| P15 | `src/polisyos/scientist/policy_design/adversary.py`, `src/polisyos/runtime/quality/prompt_tool_ledger.py`, `src/polisyos/scientist/publishing/publisher.py` |
| P16 | `src/polisyos/runtime/quality/capability_white_space.py`, `src/polisyos/scholar/_impl/evidence.py`, `src/polisyos/calibration/` |
| P17 | `src/polisyos/foundry/coupling/des_kernel.py`, `src/polisyos/foundry/methods/catalog/causal/dynamic_graph_dscm.py`, `src/polisyos/pdc/` |
| P18 | `src/polisyos/runtime/quality/semantic_binding.py`, `src/polisyos/fabric/claims/`, `src/polisyos/data_forge/` |
| P19 | `src/polisyos/runtime/quality/concept_spine.py`, `src/polisyos/fabric/entity_resolution/`, `src/polisyos/ir/world/` |
| P20 | `src/polisyos/foundry/welfare/social_weight_provenance.py`, `src/polisyos/participation_requirement/` |
| P21 | `src/polisyos/participation_requirement/`, `src/polisyos/scientist/governance/`, `src/polisyos/runtime/quality/approval.py` |
| P22 | `src/polisyos/participation_requirement/`, `src/polisyos/lex/`, `src/polisyos/scientist/governance/` |
| P23 | `src/polisyos/runtime/quality/case_lifecycle.py`, `src/polisyos/runtime/quality/cost_gate.py`, `src/polisyos/scientist/policy_design/` |
| P24 | `src/polisyos/foundry/methods/catalog/causal/strategic.py`, `src/polisyos/foundry/methods/catalog/causal/policy_learning.py`, `src/polisyos/scientist/feedback/` |
| P25 | `src/polisyos/scientist/methods/search/`, `src/polisyos/scientist/agent/drafter_multipass.py`, `src/polisyos/runtime/quality/capability_ratchet.py` |
| P26 | `src/polisyos/runtime/quality/human_review.py`, `src/polisyos/runtime/quality/approval.py`, `src/polisyos/scientist/governance/` |
| P27 | `src/polisyos/runtime/quality/workspace/loop.py` remains too broad; guardrails now require `WorkspaceSearchLedger` to extend canonical `SearchLedger`, GY acquisition to call `runtime/quality/acquisition_planner.py`, the Slice-0 catalog to use `data_forge/read_api/catalog.py`, and `workspace/spine_repair_gates.py` lex checks to delegate to `scientist/policy_design/search.py` |
| P28 | `src/polisyos/scientist/policy_design/search.py` now defaults `require_explicit_parameter_bounds=True`; legacy inferred bounds must be explicit compatibility/test posture, with remaining strangle anchors in `architecture/shims.toml` and `architecture/policy_design_case/layer3_g1_hardcode_strangle_delta.json` |
| P29 | `architecture/policy_design_case/layer3_gy_production_loop_run_proofs.json` is recomputed by `tools/quality/validation/check_layer3_gy_loop_artifacts.py --check`; remaining representative-substrate risk lives in `architecture/policy_design_case/layer3_gy_semantic_benchmark.json` until F4/F7 run on a real corpus |
| P30 | `src/polisyos/runtime/quality/workspace/loop.py`, `workspace/foundry_consumption.py`, `workspace/agent_proposal_bridge.py`, `workspace/scientist_node_adapters.py`, `proving_ground/bounded_request_agent.py`, `adapter_contracts.py`, `semantic_binding.py`, `data_forge_binding.py`; the 124-file `src/polisyos/runtime/quality/` namespace |
| P31/P32/P33 | `src/polisyos/runtime/quality/design_axes/coupling_composition.py` (GY-G: `resolve_bind_verify` single intake, the `verified_evidence` collection, and the single authority-emission chokepoint + guard) vs the per-site patches that kept reopening on the next consumer (consistency -> P14 -> cert -> emergent grounding -> SubDesignContract port intake); `src/polisyos/pdc/_impl/gy_waist.py` `assert_ring2_verifier_provenance` (Phase-0 boundary check the composition gate must reuse) |
| P34 | the GY-G G5 exclusion (`layer3_proving_ground_conversion.py` no-governed-input terminal — asserted honest, was laundering blocked-as-conversion) and the canary/public-export exclusion (`runtime/quality/public_export.py` dirty worktree — only confirmed unrelated after a completed stash isolation) |
| P35 | `src/polisyos/pdc/_impl/gy_waist.py` `PromotionObligationClass` (15 members, reported as 14 from a truncated `grep -A 16`); the fifteen INT-R9 manifests (`calibration_round_id` null in 11 of 15, not all; `authority_level` = 5 production / 6 governed / 4 research, not one value); `architecture/production_quality/confidence_ledger.toml` (13 instruments vs 5 proof profiles, conflated in one orientation); the index rider — `supersede` 48/215/260 and `legal_hold` 2/7/8 over `policy-engine/src` at `1a7a2d05e`, against connector-derived 47/203/246 and 2/4/5 in two wave-4 audits, and `benchmark`/`evaluator`/`oracle` = 183/80/44 Python-only vs 197/85/44 all-source (a correct number with an unstated file-type denominator) |
| P37 | the wave-4 audit branches `research/{ops-r14,pao-r36,pao-r4,s0-gap-02}-independent-audit` (registers `PAO-R4-III-002`, `S0-GAP-02-III-001`/`-VI-001`, `PAO-R36-III-002`/`-III-003`, `OPS-R14-V-001`); the ratified band lens it instantiates at `docs/system-design-decisions/stage0-custody-kernel-ratification.md:46-88,164-176` (`S0-K06`); the runtime analogue is P32's resolve-bind-verify intake — P32 governs a REFERENCE offered as evidence, P37 governs the PREDICATE the gate itself turns on |
| P38 | `docs/plans/active/layer3-slices/GY-engine-subordination.md` §3.5.14 (the four-instance table: exit code as completion `GY-DI4`; field *name* as non-decisiveness `GY-DEF14`; `file:line` as construct identity `DS5-LINE-ADDRESS-01`; mechanism-byte rounds as proof of wrong design, the DS5 two-fix breaker), plus that plan's hash owner and run-directory address-versus-identity class, and the Atlas plan Execution Doctrine; the architect-side instances are recorded in the P38 note above |
| P39 | the DS5 audited writer set (25 rows; **16** miss their declared cap by exactly `+1`, 2 by `+2`, 1 by `+3`, 1 by `+7`, and only the three `C13a` variants sit at `0`), and the `DS5-C17b` stop record naming the mechanism outright — the binding instruction requires each new terminal duration and recomputed ceiling in the plan, "making it an unavoidable eleventh path" |
| P36 | the `3δ` chain: the INT-R9 independent audit's aside about "a fresh δ" propagated into `docs/plans/active/layer3-slices/GY-engine-subordination.md` (GY-GAP2, Rev 23), the original INT-R10 research and its fixture, and the INT-R9 amendment summary, before the INT-R10 audit enumerated `confidence_ledger.py`'s Basel-square allocation and refuted it (corrected in Rev 24); the incomplete-rebinding corollary is the `bound_int_r10_commit` key surviving in five INT-R9 frontmatters plus a YAML header after the narrative was corrected (closed in `65b0beb72`) |

## Repair Priority

1. Fix authority, status, and soft-gate ambiguity first: `P05`, `P04`, `P09`.
2. Prevent LLM or projection content from laundering into authority: `P15`, `P05`, `P10`.
3. Make capability real on its canonical owner — named by function so the owner is discoverable, with the predecessor strangled and a representative substrate: `P01`, `P02`, `P27`, `P28`, `P29`, `P30`.
3a. For any authority/promotion/Ring-2 decision: close the class with one structural invariant, admit evidence only by resolve+content-bind+verifier-provenance, test the property not the probe, and finish isolation before excluding a failure: `P31`, `P32`, `P33`, `P34`.
4. Expose what the system knows to external audiences: `P03`.
5. Protect replay and reproducibility with rule and time semantics: `P07`, `P08`.
6. Preserve evidence strength truthfulness: `P14`.
7. Protect universal-design axis declarations, composition, search, and delegation: `P16` through `P26`.
8. Run complexity audits continuously so repairs do not add ceremonial load: `P13`.
9. Before a gate, census, or research claim is accepted: measure the whole set and name both
   denominators and the executing party (`P35`), cite the finding by ID rather than the prose around it
   (`P36`), classify what the gate turns on and fail closed on a declared premise (`P37`), and name one
   case where the implementation and the property diverge (`P38`). `P35`–`P38` govern review and
   research artifacts as much as code; `P37`/`P38` are the producer-side and consumer-side halves of the
   same failure and are checked together.

## Maintenance Rules

- Do not add a new enum, gate, artifact family, or public projection without checking P01, P03, P04, P05, P09, P10, and P13.
- Do not create a new module, type, engine, gate, planner, or fixture under a slice/plan name without checking P27: confirm no canonical owner already holds the concept, and prefer extending the owner over a parallel file.
- Do not name a new module, file, or public symbol after the plan/slice/wave that created it (P30): name it by the capability it owns. If a provenance prefix is unavoidable, the module docstring must point to the canonical owner and related modules.
- Do not land a replacement, repair, or "subordinate the engine" change without checking P28: in the same change, delete or guard the superseded path and flip the default to the corrected one; a default-off fix or a zero-deletion replacement has not migrated.
- Do not commit a proof, benchmark, capability, or closure artifact without checking P29: it must be emitted by the real run, recomputed by its validator from live code/artifacts, and measured on a representative substrate (or marked `surface_out_of_scope`); confirm the drift/self-check itself fails on a corrupted artifact.
- Do not fix an authority/promotion/gate/admission defect site-by-site without checking P31/P32: close the whole class with one structural invariant (single intake + single emission), admit evidence only by resolve+content-bind+verifier-provenance (never presence/shape/keyword/self-attestation), and grep that every sibling consumer/intake routes through it.
- Do not declare a fix done by passing the named probe without checking P33/P34: fix the property and self-generate adversarial variants (synonym, malformed, present-but-fake, sibling consumer); do not exclude a failing test as "honest/unrelated" without a completed revert/stash isolation.
- Do not state a set-level fact — a count, a distribution, a "the field is always X" — in a context pack, orientation, audit, review, or plan annotation without checking P35: derive it from a script that walks the complete set, and quote both the path denominator and the file-type denominator alongside the fact. A search index, connector result, or ranked query settles nothing — not a zero, and not a positive count.
- Do not specify a gate, admission rule, completeness assertion, effective/authority boundary, falsifier, or firewall predicate without checking P37: classify every predicate it depends on as `recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, or `not_established`, freeze that label at admission, and make the gate fail closed or degrade its claim whenever the decisive predicate is one of the last three. Run the falsify-the-declaration probe before calling the gate designed.
- Do not write or accept a gate, breaker, admission rule, or stop rule — in code or in a plan — without
  checking P38: state the property, state what the implementation turns on, and name one case where
  they diverge. If the divergent case cannot be eliminated, record it as a declared bounded limitation;
  never leave it implicit. Check P38 together with P37: they are the consumer-side and producer-side
  halves of one failure.
- Do not label a capability chain that does not exist as `contract_only` merely because a contract,
  research package, or plan section describes it: if no admitted prerequisite chain and no appointed
  owner exist, the honest label is `absent/unallocated`, and the missing prerequisite is named.
- Do not rely on a statement from an authoritative document without checking P36: name the finding ID it is, or reproduce it from the pinned owner. When correcting an inherited claim, grep the binding key and fix every dependent reference, not only the prose that reads wrong.
- Do not touch compatibility roots or imports without checking P06.
- Do not change admissibility, taxonomy, claim-support, or closeout logic without checking P04, P07, P08, and P10.
- Do not change monitoring, DDM, invalidation, reissue, or calibration behavior without checking P01, P02, P07, P08, and P09.
- Do not change evidence producers or cross-graph compilation without checking P02, P08, P11, P12, and P14.
- Do not change LLM formulation, critic, drafting, summarization, or tool-repair behavior without checking P05, P10, P13, and P15.
- Do not change universal policy-design axes, regime classification, decomposition, value choices, capacity, mandate, stakes, strategic-response modeling, design search, or delegation without checking P16 through P26.

## Pattern Lifecycle

- Add a pattern only when it is recurring, systemic, and not already covered by
  an existing row.
- A pattern can graduate to a historical section only after no new instances
  have been recorded for at least six months and an active maintenance rule or
  automated guard prevents recurrence.
- Graduated patterns keep their IDs for archaeological references; new
  patterns use the next available ID.
- If a pattern starts creating ceremonial load, check P13 before expanding it.

## Capability Ratchet

Use the missing-state labels as a maturity metric in implementation plans,
backlogs, and PR summaries. A useful periodic snapshot is:

```text
capability_claims_total:
implemented:
contract_only:
producer_missing:
artifact_missing:
bridge_missing:
consumer_missing:
verification_missing:
implemented_but_not_orchestrated:
surface_missing:
surface_out_of_scope:
semantic_test_missing:
```

The ratchet is directional: over time, capability claims should move from
missing-state labels toward `implemented`, or be explicitly scoped out. New
work should not increase `contract_only`, `bridge_missing`, or
`semantic_test_missing` without a named follow-up owner.

W1.A makes this executable through
`architecture/policy_design_case/capability_reality_report.json` and
`tools/quality/validation/check_policy_design_case_capability_ratchet.py`. The
report includes debt points, purpose multipliers, readiness bands, and
burn-down templates; a red readiness band is acceptable when the report is
honest and owned, but the affected capability still cannot be called
implemented.
