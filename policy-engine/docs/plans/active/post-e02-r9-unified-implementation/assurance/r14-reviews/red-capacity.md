# R14 capability red-team

**Pin:** baseline `c8986d035f12c1c3d9e5d0d57e369fe8257bccbc`, branch `codex/e02-integration`.
**Scope:** architecture/04, solutions/13, assurance/08, and the added DES tasks / `r14_extension` fields in `tasks.json`. Review was read-only; no product implementation or runtime verification was performed.

## R14-C01 — The productive-search pass can lack a meaningful positive

**Severity:** Blocker for closing or claiming the DES-10 productive-capability obligation; not a blocker to preparation or plumbing work.

**Location:** `solutions/13-productive-design.md` §DES-02 acceptance and §DES-10 acceptance/alternatives; `assurance/08-productive-search-and-document-quality.md` §§Case classes and endpoints, Sequencing and closure; `tasks.json` DES-02 `positive` (line 9989) and DES-10 `positive` (line 10670).

**Property vs. gate:** The stated capability is decision-relevant search. The plan measures incremental support against no-op, but its hard positive check is a typed non-no-op candidate meeting a structural/case witness, and DES-10 may pass with “material alternatives” while comparisons merely report useful and harmful/null outcomes. The run-level target is not explicitly bound to the incremental-support endpoint. A feasible, structurally distinct candidate that independent reviewers find adds no response to the decision need and no useful evidence path is a divergent case: the measured endpoint is null, while the current positive fields can still read as satisfied. This is P10/P38. Treat the DES-02 and DES-10 instances as the same class under P40; do not patch them as separate ladders.

**Smallest closure:** Make the positive-control witness explicitly answer a pre-registered decision need or identify an evidence/acquisition path that resolves it, with independent labels. Bind DES-10’s predeclared success criterion to that endpoint. This need not impose a universal rate, require success on every case, optimize `useful_design_rate`, or choose a scalar winner. If evidence is insufficient or all positive-control outcomes are null, retain engineering/readiness results but keep the productive-capability claim `not_established` until an explicit competent scope disposition.

**Falsifier:** On the known-solvable controls, supply only feasible and structurally distinct candidates that blinded reviewers judge to add no decision support over no-op. If DES-10/FINAL-USE can still close the productive-capability obligation as positive, this finding holds. If it reports the null outcome and leaves that claim `not_established`, the gap is closed.

## Bounded checks — no other blocker found

- **Rule 5:** Quality is diagnostic; `useful_design_rate` is excluded as objective, stopping rule, promotion evidence, and scalar substitute (`architecture/04` §What to count; `assurance/08` §Case classes and endpoints; `solutions/13` §DES-10). This is consistent with the original target spec’s Rule 5.
- **G6 / publication:** G6 stays bounded to intake/framing/tool routing; the public raw prompt/recommendation boundary and UI-02 data-only route remain. Private reviewer/expert drafting is permitted through the named document owner (`architecture/04` §§Open candidate work, Document package; `solutions/13` §§DES-06/07; `tasks.json` DES-06 surface).
- **GYD-23 / EVSI:** Slice0 keeps its BIND/ESTIMATE/VERIFY route and Estimate terminal. Richer N4/N6 work is separately routed; no blanket numeric-EVSI prerequisite is introduced (`architecture/04` §Open candidate work; `solutions/13` GYD-23 extension; `tasks.json` GYD-23 `r14_extension`).
- **WP-01/02:** R14 explicitly excludes operative O1 posterior mutation and LLM weight training; DES-08 bars candidate memory from mutating O1/O3, while genuine search learning remains possible without waiting for update activation (`architecture/04` §Learning three kinds; `solutions/13` §DES-08; `tasks.json` DES-08).
- **Numeric vs. structural search:** Outer structural proposals and inner native parameter/constraint trials are separate; set-valued/Pareto outcomes remain where weights are absent (`architecture/04` §What to count; `solutions/13` §DES-03; `tasks.json` DES-03).
- **Learning and free growth:** DES-08 requires actual outcomes, compatible retrieval, influence on a later choice, fresh-process persistence, stale/revoked/contamination checks, and balanced successes/failures/opportunities. New operators, methods, formats, and cases can flow through existing registries/adapters; unrepresentable content survives as an unbound hypothesis, and search limits remain explicit (`architecture/04` §§Open candidate work, Learning; `solutions/13` §§DES-02/03/04/06/08/10). No overrestriction or fake-learning blocker found.

Task records consistently label the work planning-only and product verification `UNRUN`; that is an appropriate pre-E02 boundary, not a product PASS.

## Narrow rereview — R14-C01

**Result:** CLOSED as a documentation acceptance gap. Reviewed the current working tree at HEAD `c8986d035f12c1c3d9e5d0d57e369fe8257bccbc`, branch `codex/e02-integration`. The productive positive is now tied to a predeclared substantive decision need or resolving evidence/acquisition path, with independent labels; feasible but irrelevant alternatives fail, and an all-null result leaves productive capability `not_established` while plumbing may pass. The candidate-producing system is distinguished from no-op and removal comparator arms, and reviewer panels are evaluation inputs rather than per-run authority gates. This closes the original divergent-case falsifier without imposing a universal rate, per-case diversity floor, or `useful_design_rate` objective.

The refinement is aligned across architecture/04; the DES-02 and DES-10 root-review refinements in solutions/13; assurance/08's positive endpoint, distinguishing probe, and composed closure; `tasks.json` and `preferred-solutions.json` DES-02/DES-10 fields; and matching `R14-DES-02` / `R14-DES-10` obligation records. No remaining C01 blocker found. Product/runtime verification remains `UNRUN` and was outside this rereview.

**Reviewed-content SHA-256 scope:**

- `architecture/04-generative-search-learning-and-documents.md` — `270cee02de6c3f7b88501b9b9851fef8f906f2af5c06a6a17d6dcbabea3ba795`
- `solutions/13-productive-design.md` — `cc3d7c40f9d8434b4bd463939d1af3a3879627519464e40edfdaf0983284e851`
- `assurance/08-productive-search-and-document-quality.md` — `b3e1c2971ce84c89d714f0feda59c17a495544669af480bf457be261941d5fa7`
- `tasks.json` — `fcc0807206908301644ea5f2e66c23cbb2ca2012400e66b0de5a4619df54a206`
- `solutions/preferred-solutions.json` — `69a51a6af2f1399d86467308375215175a866f1d3b62e8835176de0578874192`
- `assurance/r14-capability-obligations.json` — `7114df44c54bfce8ea2609ece11e06b3171b51a18e946075356a64e9a07dc1a5`
