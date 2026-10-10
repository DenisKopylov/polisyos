# B59 producer admission delta review

Status: independent review completed on the r4 source hash recorded below. Actual builtin producer and consumer controls, poison negatives, and canonical-depth controls pass. A bounded private Enum-member mutation residual remains; this report does not claim the whole B59 mutation-custody property is closed. No product source or test files were changed by this reviewer.

Review environment: product root `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`; candidate HEAD `077a572ff5880b3f50a85d3e3db6a232d277659a`; Python invoked as `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python`; source origins resolve inside this worktree. B59 source baseline `src/polisyos/scientist/orchestration/engine/state_branching.py@490d05e758b8ab6cdca12dc37bddd9085dfd7987e86feb9fb4cc49db4db01666`. Relevant test baseline `tests/unit/scientist/orchestration/engine/test_state_branching.py@88f2f9a3e8802d2c4415ccc146be7105446c524293627044b5103bb8ef50fe73` (the B59 author was adding tests during this review); producer test `tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py@cd8e841805394e3cf6abc0dd0dcfb7b455bee4c561919352f29587a5a5338e66`.

## Material baseline regression

The existing maintained producer selector was run against the current shared candidate:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q -ra --tb=short --disable-warnings -p no:cacheprovider \
  tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_no_registry_hierarchy_persists_candidates_without_global_frontier_claim \
  tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py::test_hierarchical_stage_b_absent_or_mismatched_eval_safety_refuses_without_evaluation
```

Both tests fail at the actual assignment to `state.params["policy_candidate_schema"]` (`run_hierarchical_policy_search.py:712`, and the Stage B assignment at `:805`). `_validate_mutation_attachment` rejects nested Enum values with `TypeError: state mutation journaling requires a finite JSON container graph`. These callers construct/use a genuine typed `PolicyCandidateSchema`; the normal consumer `_resolve_search_candidate` reads that same state slot at `:758`. This is not merely a canonical JSON compatibility concern: converting the candidate to a dict/string would change the supported typed handoff. Other real consumers include simulation and policy output-bundle construction.

A runtime walk constructed the actual `_bundle()` from the maintained producer test and `PolicyCandidateSchema.from_trinity_bundle(bundle)`, yielding five Enum leaves in a real candidate instance: `ProblemDomain.fiscal`, `OptimizationDirection.maximize`, `SelectorOperator.EQUALS`, `AssumptionType.PARAMETRIC`, and `FidelityLevel.HYBRID`. Full paths and module origins are in `b59-delta-actual-candidate-enums.log@b4264f0a76997ee0a54c62c825900b890fe723341f47084ac42b6fcd2bc6fbc1`. The recursive field type census, including additional production schema Enum annotations and dynamic `Any` fields, is `b59-delta-runtime-types.log@458bf155e241a448a233d274b4a04589710786ee0fe2d2bd879383b5a56500e6`.

The two-test full failure output is `b59-delta-hierarchical-consumers.log@5e859beb8561ab10ffb70d65861fce181ba841d52f8e924c92fde2873c724015`.

## Enum custody boundary

A blanket `Enum` leaf exemption is not safe under the existing deep-copy/journal mechanism: `deepcopy(str_enum_member) is member`; standard `str, Enum`, `StrEnum`, and `IntEnum` instances also accept both `member._value_ = ...` and arbitrary attribute assignment. The direct probe, which shows source/copy alias mutation, is retained in `b59-delta-enum-census.log@0653b4695573464951af2aa09a22e0d0645dadddb9ca15d6e50a8a414701c05f`. Therefore an implementation that admits scalar Enum values must justify how it preserves typed policy semantics and controls the still-mutable singleton/member alias. No model-to-string conversion was used or proposed as a workaround.

## Depth boundary

The existing recursive admission starts at depth zero for each `ExperimentState` member, while canonical serialization measures the enclosing `ExperimentState` envelope. A `params.probe` list graph with 124–127 layers was accepted by field admission although full-state canonical serialization with `max_depth=128` refuses. With 126 layers, both sync and async real `WorkflowExecutor` controls fail canonicalization before the counted producer runs (`calls=0`; events only `RUN_STARTED`, `RUN_INPUT_ADDED`; no cache/completion events). Full output: `b59-delta-depth-workflow.log@55373de7be09bcf9c6234e2b91ff480854423992a3a9fde8985d1aeda63af275`. This proves a depth-accounting mismatch, not a producer-side-effect regression.

## Controls already run

The pre-r4 focused selectors for state branching, producer-scope reconciliation, producer validation GraphOracle/importer, and `BuildExecutionPlanNode` built-in tests passed. Full output: `b59-delta-unit.log@ff986e6190180b379c5ef74b3e32894d2754068555d84a4bc1d60cef83fea260`. Separate sync and async two-node workflows using actual `BuildExecutionPlanNode` output succeeded; a downstream consumer verified three typed `ExecutionPlanRef` locations and read/decoded the CAS object. Full output: `b59-delta-tests.log@cf88c93c682b1a0f38b67a38770df03816607ffa881b0bfc05b03d07d113df42`. The final r4 poison-control replay is recorded below.

## P40 and closeout

The actual PolicyCandidateSchema regression is a same-class deeper finding against generic producer-state admission: a current registered producer writes a supported typed result that the admission contract rejects. The corrected mechanism must preserve the `PolicyCandidateSchema`/Enum types and pass the actual downstream candidate consumer, while existing hostile/custom-leaf negatives stay red. The depth probe is another measured boundary mismatch in the same finite-graph admission mechanism; it did not run the producer before refusal. Review is not complete until r4 reports a new source hash and the real producer/consumer plus poison-negative controls are replayed against that exact hash.

## r4 compatibility replay (source SHA `f38a82a6d61c37a0c2d94799ec5a16272d8acf1040334dfe7c80c0328cb45798`)

The exact source hash was unchanged before and after the replay. The final combined tests passed: `test_state_branching.py@0919a7fd58885d25f0c2b0dd5b6b55efae68fd8806b2aebada3900a2b8ed8c28`, `test_producer_scope_reconciliation.py`, and both previously failing hierarchy selectors. Full output: `b59-delta-enum-candidate-focused-final.log@075301b636ae00652938cadb3575cae6d8bd4c7fff48f33f7dc52582d5f62ce3`. This replays poison controls for custom copy/attribute/reduction hooks, hostile containers, custom scalar subclasses, mutable-backed enums, nonfinite values, malformed keys, cycles, and depth.

A separate live harness drove `RunHierarchicalPolicySearchNode.execute()` with a genuine `PolicyCandidateSchema` from the maintained test fixture, then passed the produced state through the real `_resolve_search_candidate` consumer. The producer returned `ok`; the state retained `PolicyCandidateSchema` through its journaled wrapper, `ProblemDomain` as its runtime enum type, and the original candidate hash; the consumer resolved the same typed candidate and matching hash. Full output: `b59-delta-producer-consumer.log@cc38ed3d51433bee40ce584b24ce5ac9c82a0725046bb9a2accf25569d30b130` (an initial harness setup error is retained in `b59-delta-producer-consumer-attempt1.log`).

The widened canonical depth accounting passed both the finite boundary test and an actual producer refusal control. A 125-layer nested params graph is refused by the synchronous and asynchronous `WorkflowExecutor` before `_ScopeProducer.execute` (`calls=0`); the traces contain `RUN_STARTED` only, with no node cache or completion event. Full output: `b59-delta-depth-current-workflow.log@6032915b09f935a3d6b29078bc3de2e83773e8dc18b54c610c04ce97fa1a4257`. The 124-layer positive side is accepted and serializes canonically in the state-branching test.

## Bounded enum residual and decision boundary

The approved compatibility mechanism admits audited primitive-valued Enum members and preserves the live built-in candidate path. The separate private-member falsifier remains true even after this update: for an admitted typed model, the original and branch contain the exact same Enum singleton; changing `Domain.fiscal._value_` changes both typed fields, while mutation journal operations remain empty. Full output: `b59-delta-enum-alias-typed-model.log@a7c57ffd46ab16b49eada4952412998e76de0d700a64ecc57148440aac40205f`. This is a `P40 SAME_CLASS_DEEPER` escape in the finite graph's alias/mutation custody boundary. It is recorded as the declared unenforced private-member mutation residual, not as proof that Enum values are immutable, and it does not trigger another instance patch round. Where private Enum mutation affects the admitted-state immutability claim, the gate's predicate is `consumer_asserted` / `not_established`: callback/value-shape checks do not recompute read-only member behavior. The divergent case is an externally retained standard enum member whose `_value_` changes after admission. This report therefore confirms the registered producer/consumer and poison-control behavior but does not claim the whole B59 immutability property closed.
