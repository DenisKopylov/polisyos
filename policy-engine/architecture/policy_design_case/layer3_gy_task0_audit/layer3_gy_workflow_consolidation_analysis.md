# GY Workflow Consolidation Analysis — Is `policy_design` the Right Target?

Date: 2026-06-14
Question (from review): `policy_design` seems written later and inherits a more progressive/universal policy-design vision; it can absorb the best traits of the three workflows; and it is a more universal *structure* with much more variability of actions and sequences than three sequential workflows. Is that right?
Mode: evidence-based analysis; input to the execution-topology design.

## Hypothesis scorecard

| Claim | Verdict | Evidence |
| --- | --- | --- |
| `policy_design` written later / more progressive | ✅ at capability level, ❌ at spec-file level | All 3 workflow spec files co-committed 2026-05-07 (a packaging refactor). But the design-search machinery is ~7 weeks newer than the evidence/legal substrate: `scientist/policy_design/{search,objectives,schema}.py` 2026-03-27, `lex/interventions.py` 2026-04-03 vs `ir/analytics` 2026-02-09 (transport/ensemble 2026-03-02), `lex/knowledge` 2026-02-04. The design layer is built **on top of** the earlier evidence + legal engines. |
| Can adopt the best traits of all three | ✅ structurally clean | `policy_verified` is a strict node subset of `policy_design` (0 unique nodes). `causal_full` adds only the evidence arm (transport/ensemble/abm/evaluator) + requires trinity. `policy_design + causal_full's evidence arm = superset`. |
| `policy_design` is a more universal structure with more variability of actions/sequences | ⚠️ half-right, refined | **Topology: no** — none of the 3 specs use the engine's `condition` gate; all are static DAGs (`depends_on` only); `policy_design` is just the largest fixed topology (37 nodes). **Capability: yes (and only it)** — `policy_design` is the only workflow wired to the variable/iterative machinery: `run_hierarchical_policy_search` → `policy_design/search.py:869` adaptive loop (`while iteration < max_iterations`: generate→stageA→stageB→rank→stopping→repeat) + `iteration_state_machine.py` (`replanning`). `causal_full`/`policy_verified` are flat pipelines with zero iteration. |

## The refined truth about "variability"

Two senses must be separated:

- The **DAG topology** of all three is static. `policy_design` is not a more flexible graph; it is a longer fixed one.
- The genuine variability lives **inside one node** (`run_hierarchical_policy_search`) and its search loop — which exists only in `policy_design`. That loop is a **seed** of the target the constitution/D-series actually want: **D3.2 "Design Search Control Plane"** — a blackboard loop `ConstraintStore → B proposes → A verifies → ParetoArchive / CounterexampleRecord → RefinementDecision → SearchLedger → loop` (CEGIS/CEGAR family). The seed is single-axis and currently broken (lex optional-bounds bug); D3.2 is 🔴 not built.

There is also a second, more flexible construction substrate already present: `ResearchDAGBuilder` (`scientist/methods/research_dag/builder.py`) builds a DAG programmatically (mutable `add_node`/`add_edge`), unlike the frozen `WorkflowSpec`.

## Strategic conclusion

`policy_design` **is** the right consolidation target — not because it is a flexible DAG (it is not yet), but because it (i) most completely covers the design-side of the operating model (intent → options → search → lowering → translation → decision packet), (ii) is a structural near-superset, (iii) is the only workflow already reaching toward the D3.2 variable-search vision, and (iv) sits on the later design stratum.

But the end-state is **not "one bigger static DAG."** Reframe the three not as competing pipelines but as **three layers of one designer**, expressed in D3.2 terms:

- `causal_full` → **evidence / transport producers** (knowledge sources writing into the ConstraintStore + A-firewalls). Its evidence arm is a source of constraints, not a separate mode.
- `policy_verified` → **legal-admissibility constraint producer + verifier**. It is a strict subset and should not remain a separate top-level mode.
- `policy_design` → **B: generative design search + lowering + decision packet** (the body of the blackboard loop).

Consolidation therefore means: near-term, absorb the evidence arm and legal arm as **conditional sub-graphs / constraint producers** around the shared 19-node spine; target, evolve the orchestration from a static DAG to the D3.2 blackboard control plane.

## Honesty caveats

- `policy_design` is simultaneously the only workflow **broken at its distinctive node** (lex bounds bug) and the **untriggered** one in production. Choosing it as canonical is the most ambitious path (repair the search seed + wire the trigger + absorb the arms), not a rename.
- Static→blackboard is a real engineering program (D3.2 = 🔴), not a one-week task. The near-term spine+conditional-arms gives honest consolidation cheaply; the blackboard is the direction.
- **Graded outcomes** (the fork-independent near-term `useful_design_rate` win) is orthogonal to this mode decision and should proceed regardless.

## Feeds

This analysis feeds the execution-topology design (next): the target topology must be the D3.2 blackboard control plane over a content-addressed artifact graph, scale-invariant from a single-cycle local policy to a dozens-of-cycle accession program, with the three current workflows demoted to default trajectories/presets over registered operations.
