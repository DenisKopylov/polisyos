# Independent red-team: integration architecture, round 2

## Evidence

Reviewed brief `policy-engine/_build/g-architecture-20261023/brief.md` (SHA-256 `a0e3ccddddb9c3277b4e8c1b71289d4c437aff267421c420b2c1a19c59ef6d68`), R1 note (`0cb98f70b285852865635d90c3f31339bc6a3f56847fa2884bddc724ebe8a5c4`), and revised docs read from `policy-engine/docs/research/e02-cloud-test-plan/integration/architecture-decisions-2026-10-23/`:

- `03-pag-scope-and-legal-relation.md` — `51dbf9c81f2e7aeaf41e5547d731ccc68ff764b8a89d5c67bcdf9fa209b1fbdd`
- `04-conditional-transport-diagnostic.md` — `555984e7b3c6b943468f93c0705295bf288919ecddfef815a455aa64290e8233`
- `05-implementation-and-inputs.md` — `82c90408c94baf9073703d76f258147809484ce5dba66ecfa3634640b6da3312`
- `06-validated-partial-graph-profile.md` — `1df69a0085c2b3a09f83d12bd64db870ea36b209e7c6535505b72108698e5036`

No code/tests run; no source files changed.

## R1 disposition

- **R1-01 candidate bridge/trigger: closed at architecture level.** R4 §Execution explicitly distinguishes absent request (no attempt) from explicit null/malformed/unknown request (typed refusal), rejects injected probabilistic defaults as intent, and requires a second candidate branch after preserving the exact Lex refusal. Access/resource admission is independent. This matches the actual early return described in R1: implementation must split that route; merely calling today’s loop remains insufficient. The positive candidate bridge is still `producer_missing`/`bridge_missing`/`verification_missing` until implemented, as §06 says.
- **R1-02 scalar confidence: closed.** New output uses `selected_family_success_fraction`, persists its numerator/denominator and non-success accounting, forbids a zero-denominator fraction and disclaims probability/confidence/whole-class meaning. New refused results do not mirror legacy scalar fields. Old sampler remains inadmissible; PAG candidates require validated MAG membership, not relabelled orientations.
- **No blanket refusal:** PAG/R4 requires a substantive positive; §06 separately requires a DAG/ADMG end-to-end positive. Missing optional PAG backend may leave that PAG profile `UNRUN`, while other lanes continue.

## Remaining finding

**R2-01 — R4 routes CPDAG to a PAG-only profile (medium, same graph-semantics class one seam deeper; P02/P10/P40).** R4 §Execution step 4 (04:45) says PAG/CPDAG inputs invoke the registered validated-family producer. The selected profile in 06:17–26 accepts a complete observational PAG, enumerates circle endpoints, and certifies MAG members by reconstructing its PAG; it defines no CPDAG input, CPDAG-to-family semantics, or CPDAG-specific registered profile. A CPDAG cannot be silently reinterpreted as this PAG. Specify either (a) CPDAG is typed `unsupported` under this profile until its own registered producer/profile exists, while the existing PAG and DAG/ADMG positives remain required, or (b) define and validate a CPDAG family profile with its own membership contract. Do not call this an external blocker or revert to the invalid orientation sampler.

## Cross-document / rollout assessment

The package is free-grow: 05 uses generic owner declarations and existing IR reflection/catalog, keeps domain resources out of schema-version menus, requires unseen-resource and compatible-representation probes, and separates generic JSON custody from typed admission. No extra historical-corpus, positive-legal-evidence, six-Welfare-producer, or unrelated-family dependency blocks a completed independent mechanism. The necessary serial edges are the shared descriptor/DTO interface and reader-before-writer rollout; non-overlapping families and algorithm research may proceed in parallel. At implementation freeze, the stated direct/indirect consumer reconciliation is necessary; seed counts are not closure caps.

The PAG profile is finite and explicit: no-selection observational PAG, latent confounding retained, unsupported profile boundaries, bounded proposals, exact member validation, and no claim of random sampling or whole-class coverage. It reuses the existing optional `causal-discovery` extra (`causal-learn>=0.1.3.8`, lock 0.1.4.4 at the question pin; `policy-engine/pyproject.toml`, `uv.lock`) and existing supervised resource owners. §06 correctly treats the oracle as a candidate, binds actual backend revision, calls for independent conformance, and adds no platform or mandatory R runtime. Its explicit backend unavailability state is more honest than installing/upgrading one or refusing every candidate operation.

One low-cost wording clarification: R4 §Execution step 3’s “admitted resource-budget selection” should resolve through the existing compute permit/policy, not introduce a per-resource human approval or a new user-supplied cap. Sections 03 §11–19 and 06 §32–38 otherwise preserve existing purpose/access controls and truthful limits; those controls are operation admission, not a new approval workflow.

The external/legal inputs table in 05 is appropriately narrow: an authenticated operative source, competent issuer, scope/time and applicability are genuine missing evidence; source search/admission remains existing-owner work. Contract definitions, resolver/consumer wiring, selected-profile binding, migrations, access rechecks and the independent candidate positive are implementer work. Manual/synthetic authorized inputs can prove the conditional path without fabricating a live grant. No blanket legal-approval request or per-resource approval is justified.

Pattern pass: R1-01/R1-02 are closed in the design; R2-01 is a concrete profile/dispatcher mismatch, not a new authority class. Relevant IDs P02/P05/P10/P13/P27/P29/P31/P32/P37/P38/P40. Runtime capability and finding closure remain unclaimed.

## Final delta review — latest 04/06 bytes

Reviewed the revised 04 (`8c844ace614e437566c0725228bad857a00b7b1e71d3bb9bbb6a40e35878ca6b`) and 06 (`66c257c9ed7fb5b549c8381af6fdaae92d47c36984c60bce3ce42ec1778ab625`) only. This supersedes R2-01 above: **CPDAG mismatch closed.** R4 now marks CPDAG unsupported for this PAG profile and retains direct refusal until a separately registered DAG-equivalence profile; the text says that extension does not block the PAG or resolved-DAG/ADMG positives. Profile 06 independently says CPDAG is outside scope and requires its own validator.

Other requested deltas are explicit and coherent: R4 resolves budget choice through the existing compute permit/policy, with no new human approval or caller cap; defines `identified_member_fraction` as valid completed `IDENTIFIED` outcomes divided by all valid completed outcomes, counting the other completed statuses separately and excluding errors/interrupted/unstarted (zero denominator has no fraction); 06 constructs a resolved `SelectionDiagram` per member with that member as `base_graph`, preserving transport S-nodes, contexts, and query; and the causal-learn 0.1.4.4 adapter records the documentation/source mismatch (latent Node objects vs documented indexes), requires the exact graph Node objects, and binds the tagged API/version. The finite PAG profile remains bounded and optional; it adds no platform.

Final disposition: no remaining R2 finding in the reviewed delta. This is documentation review only; implementation capability and semantic verification remain unclaimed.
