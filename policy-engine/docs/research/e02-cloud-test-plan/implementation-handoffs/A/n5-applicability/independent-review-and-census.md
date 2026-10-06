# Independent preflight reviews and complete typed-request census

This companion preserves the two read-only source reviews, the earlier Decimal failure diagnostic, and request-leaf census counts. Full census output is retained in ignored local evidence at its cited path/SHA. The two derived leaf-path/type lists are omitted here because the reader can recompute them from the pinned fixture; other source excerpts preserve their original text. The census and Decimal diagnostic predate the final `afc25de` codec fix and are retained as evidence of the input shape that caused the prior failures, not as final-candidate test results.

| Section | Source | SHA-256 | Bytes |
|---|---|---|---:|
| Independent review b656 | `_build/A_build/e02-A-full-queue/b10-preflight-review-b6569078.md` | `bc5f237b60ca7163e35800d4377bcd10f055909f7d491459f8a08404b7a94b82` | 5326 |
| Independent review f30 | `_build/A_build/e02-A-full-queue/b10-preflight-review-f30fbec3.md` | `68afa2cd9a4337fc207c749fdd1164f84ccdd879054d17075838998174b2471c` | 1771 |
| Decimal diagnostic stdout | `policy-engine/_build/e02-A-full-queue/b10-diagnostic-bf465/stdout.txt` | `c8f5635a8dd153d0f4b1e056977dc79318238e98095fc28cc4258b35f4905259` | 2524 |
| Decimal diagnostic stderr | `policy-engine/_build/e02-A-full-queue/b10-diagnostic-bf465/stderr.txt` | `0d3d961bdaef57a7ffa254841f7d4ed3fff3894a9f15965740290ebd10a23f1a` | 3790 |
| Complete typed request leaf census | `policy-engine/_build/e02-A-full-queue/b10-leaf-census-bf465-r2/leaf-census.md` | `fcfb746138937a8fb8b5043942df6590907932c45109046a7f850cbdc6933673` | 55128 |

---

## Independent review b656

Source: `_build/A_build/e02-A-full-queue/b10-preflight-review-b6569078.md`; SHA-256 `bc5f237b60ca7163e35800d4377bcd10f055909f7d491459f8a08404b7a94b82`; 5326 bytes.

# B10 preflight revision review

**Verdict: GO for the bounded mechanical preflight delta, with B10 still open.** This read-only review does not establish the full B10 property or any test result.

## Reviewed artifact

- Patch: `_build/e02-A-full-queue/budget_feasibility/b10-preflight.patch`
- SHA-256: `b6569078cc098c189a946490c7546788ade98367a8bfecf5c3bc92fe039341a4`
- Patch mtime: `2026-10-06T20:04:18+0300`
- Patch base: `f5fbc9e6ab504e941439ed9fdabbbdcaf880f407`, tree `f2946514ce28e11dc05aafe9ba54b99370992382`

## Delta findings

The five previously reported source blockers are addressed for the scope this patch now admits:

1. **Request digest covers typed execution input or refuses.** `_typed_execution_payload` walks declared and computed Pydantic fields, mappings, and sequences; it refuses non-null excluded fields, non-null private values, unsupported opaque values, non-string mapping keys, and non-finite floats. `_joint_simulation_request_digest` returns no digest on any such failure. Consequently a live excluded Foundry handle cannot silently disappear from the applicability hash; for a request containing such a handle, preflight remains `not_established`. This closes the former lossy-JSON false pass for expected-applicability checks.

2. **The full problem is content-bound.** `_problem_content_hash_for_n5_preflight` hashes the typed `DesignProblem` content, including runtime hints, and declines preflight if that content cannot be bound. Preparation and execution both compare this content hash.

3. **Canonical multi-atom candidates receive a tuple content hash.** When `intervention_atoms` is present and contains validated `InterventionAtomBinding` values, `_candidate_content_hash` hashes the complete ordered tuple of atom content hashes (or uses the sole atom’s content hash). The prepared candidate check repeats this discriminator before consuming the prepared request.

4. **Absent multi-atom coupling evidence is no longer called eligible.** After the actual N5 owner assessment, an otherwise eligible multi-atom request with `coupling_graph is None` is downgraded to `not_established`. A real direct-assignment conflict is classified `ineligible` by `_validate_atom_assignment_compatibility`; the later “missing coupling” branch only downgrades `eligible`, so it does not erase that refusal.

5. **Profile-handoff and custom-port paths remain on their existing routes.** Enforcement is limited to production composition with the default simulation/controller, no candidate handoff, and the owner-built NCM data-only request path. When that discriminator is false, the summary records `None` (excluded from its wire form), selection uses the prior grounding behavior, and N7 invokes the configured simulation port as before. I found no remaining unconditional profile/custom-port block in this revision.

The assess-to-run binding is coherent in the admitted lane: pre-VOI execution calls `prepared_applicability_is_current` on the prepared request; `JointSimulationPort.__call__` consumes that same prepared request; and `run(expected_applicability=...)` recomputes the typed digest and the shared owner assessment before comparing the expected record. The default controller’s engine-runner map includes the NCM runner. I found no stale JSON-projection acceptance or missing-runner path for this default NCM composition. The shared-assessment refactor preserves the earlier world-record consumption and selected-plan inputs; the extra NCM intervention check is also repeated by the actual NCM run path.

## Remaining boundary and acceptance status

This is a bounded **mechanical N5 applicability preflight**, not the owner-complete B10 feasibility capability. Its eligible result establishes the particular checks in this admitted NCM lane: bound world/atom request, a selected registered NCM plan, acyclic NCM spec, and supported intervention assignments. It does not establish all canonical-owner hard constraints, nor does it prove persisted rejection/result readback or an independent direct-engine recomputation. Missing coupling evidence keeps multi-atom requests unestablished rather than filling those gaps.

The patch’s test-file hunk only changes the frozen-history model/field counts; it adds no N5 behavioral test. B10 therefore remains `verification_missing` pending the separate paired fixture and registered negative, persistence/readback, and direct-engine oracle. The new status must not be reported as B10 closure.

One narrow shape consistency caveat remains: `_candidate_content_hash` takes the tuple-hash branch only when `type(item) is InterventionAtomBinding`, whereas `_build_joint_simulation_request` accepts `isinstance(item, InterventionAtomBinding)`. The ordinary default N4 source emits the canonical base type; if subclass atom instances are intended to be supported by this builder, align those predicates or keep that shape unestablished so it cannot fall back to a weaker candidate discriminator.

## Scope

Reviewed the new patch against its pinned base and the relevant production source paths. No source or test files were edited. No tests, numeric runs, or commits were made. The independent prior-revision review remains at `_build/A_build/e02-A-full-queue/b10-preflight-review.md` and applies only to its recorded older patch SHA.

---

## Independent review f30

Source: `_build/A_build/e02-A-full-queue/b10-preflight-review-f30fbec3.md`; SHA-256 `68afa2cd9a4337fc207c749fdd1164f84ccdd879054d17075838998174b2471c`; 1771 bytes.

# B10 preflight delta review

**Verdict: GO for applying this revision relative to the prior scoped GO.** This is not B10 closure and not a test receipt.

- Patch SHA-256: `f30fbec3577dec92251f344e14ac9386e4c65dde18172d847b15cb7281655f42`
- Patch base: `e5796dd1c45a6c82bc0d425e6c3a11bb16fdd097`, tree `714893e485f02e13541247d45a4ed8ed21e3c475`
- Patch mtime: `2026-10-06T20:18:55+0300`

Reviewed only the two requested delta classes:

1. `prepare_candidate` detects an `InterventionAtomBinding` subclass and returns `not_established` before request preparation. `_candidate_content_hash` now records subclass identity by walking all typed fields (including inherited/computed fields); if that walk encounters opaque content, it falls back only for record identity. The preflight refusal prevents that fallback from conferring eligibility.

2. The unprepared path remains compatible with prior custom controllers: `JointSimulationPort.__call__` calls `self._controller.run(request)` when `prepared_candidate is None`, and supplies `expected_applicability` only for a prepared request. The default NCM runner remains in the controller’s runner map.

The reported real conflict case follows the intended source path: the shared assessment returns `ineligible` for conflicting assignments; the candidate selector admits only candidates with `status == "eligible"`, leaving the lower eligible candidate selectable. This is static inspection only; I did not run the test or numeric work.

No additional blocker found in these two deltas. Prior scope remains unchanged: bounded default-production NCM mechanical preflight only; owner-complete hard-feasibility, persistence/fresh readback, and the independent direct-engine oracle remain outside this GO and B10 remains open.

---

## Decimal diagnostic stdout

Source: `policy-engine/_build/e02-A-full-queue/b10-diagnostic-bf465/stdout.txt`; SHA-256 `c8f5635a8dd153d0f4b1e056977dc79318238e98095fc28cc4258b35f4905259`; 2524 bytes.

```text
supports True
problem payload {'schema_version': 'policyos.runtime.design_problem.v1', 'design_problem_id': 'cyc_n5_owner_boundary_a205116017b94f80ad076b6d770fb7a1', 'problem_statement': 'Improve firm survival with grounded support under fiscal constraints.', 'domain': 'generic_policy', 'nl_provenance': {'raw_request': 'Improve firm survival with grounded support.', 'source_surface': 'test_generation_cycle', 'source_context': {}}, 'authority_profile': {'requester_authority': 'research_lab', 'requested_authority_level': 'research', 'mandate': 'test-only research mandate', 'authority_refs': []}, 'jurisdiction_time': {'region': 'UA', 'valid_time': '2026', 'as_of': '2026-06-29', 'policy_time': '2026', 'data_time': '2026', 'time_semantics': None}, 'objectives': [{'objective_id': 'firm_survival', 'description': 'Improve firm survival', 'metric_id': 'firm_survival', 'direction': 'maximize'}], 'constraints': [{'constraint_id': 'shadow_only', 'description': 'Generated candidates remain shadow until A/N9 certification.', 'hard': True, 'admissibility_basis': 'request_text', 'source_text': 'Do not promote generated candidates.', 'evidence_ref': None}], 'stakeholders': [{'stakeholder_id': 'firms', 'name': 'Firms', 'role': 'target_population'}], 'outcome_of_interest': {'target_variable': 'firm_survival', 'metric_id': 'firm_survival', 'estimand': 'average_treatment_effect', 'direction': 'maximize'}, 'candidate_lever_space': {'allowed_operator_kinds': ['grant', 'tax_relief'], 'candidate_levers': [{'lever_id': 'grant', 'operator_kind': 'grant', 'instrument': 'Targeted grant', 'target_slot': 'government_balance'}]}, 'evidence_acquisition_needs': {'needs': [{'need_id': 'supporting_data', 'question': 'Which data grounds this effect?', 'required_for': 'A-side grounding', 'status': 'required', 'source_hint': None, 'artifact_ref': None}]}, 'model_spec_ref': None, 'ir_problem_frame_ref': None, 'policy_request_frame_ref': None, 'runtime_hints': {'joint_simulation_budget_ref': 'budget://cyc-01/b917d3efad0f477c871623ab96cc6c17/n5', 'joint_simulation_horizon': {'start': 0, 'end': 0, 'step': 1}, 'joint_simulation_resource': 'ncm_parallel_worlds', 'joint_simulation_baseline_state': {'firm_survival': 0.0}}}
candidate_high_conflict {'status': 'not_established', 'request_digest': None, 'engine_decisions': [], 'blockers': ['n5_request_digest_not_established']}
candidate_feasible_single {'status': 'not_established', 'request_digest': None, 'engine_decisions': [], 'blockers': ['n5_request_digest_not_established']}
```

## Decimal diagnostic stderr

Source: `policy-engine/_build/e02-A-full-queue/b10-diagnostic-bf465/stderr.txt`; SHA-256 `0d3d961bdaef57a7ffa254841f7d4ed3fff3894a9f15965740290ebd10a23f1a`; 3790 bytes.

```text
2026-10-06 20:24:19.351 | INFO     | polisyos.common.logger:_call:120 - Circuit breaker initialized
Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1050, in _typed_execution_payload
    payload[name] = _typed_execution_payload(item)
                    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1062, in _typed_execution_payload
    return [_typed_execution_payload(item) for item in value]
            ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1050, in _typed_execution_payload
    payload[name] = _typed_execution_payload(item)
                    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1050, in _typed_execution_payload
    payload[name] = _typed_execution_payload(item)
                    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1060, in _typed_execution_payload
    return {key: _typed_execution_payload(item) for key, item in value.items()}
                 ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1069, in _typed_execution_payload
    raise TypeError(f"execution_input_not_json_bindable:{type(value).__name__}")
TypeError: execution_input_not_json_bindable:Decimal
Traceback (most recent call last):
  File "<stdin>", line 19, in <module>
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1050, in _typed_execution_payload
    payload[name] = _typed_execution_payload(item)
                    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1062, in _typed_execution_payload
    return [_typed_execution_payload(item) for item in value]
            ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1050, in _typed_execution_payload
    payload[name] = _typed_execution_payload(item)
                    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1050, in _typed_execution_payload
    payload[name] = _typed_execution_payload(item)
                    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1060, in _typed_execution_payload
    return {key: _typed_execution_payload(item) for key, item in value.items()}
                 ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "/Users/deniskopylov/.codex/worktrees/e02-a-full-queue/polisyos/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py", line 1069, in _typed_execution_payload
    raise TypeError(f"execution_input_not_json_bindable:{type(value).__name__}")
TypeError: execution_input_not_json_bindable:Decimal
```

## Complete typed request leaf census

Source: `policy-engine/_build/e02-A-full-queue/b10-leaf-census-bf465-r2/leaf-census.md`; SHA-256 `fcfb746138937a8fb8b5043942df6590907932c45109046a7f850cbdc6933673`; 55128 bytes.

# B10 typed request leaf census at bf465

Base `bf465f6d486816c1de8579f4c19faf1ec0772fbb` / tree `57d8dd8e6254a8f63e3b59074bd58902ce0247bf`.
Constructed the two actual owner-built requests (conflicting high candidate and feasible single-atom candidate) using guarded fixture CAS. Invoked only request construction, verified-WMR binding, and program-state binding; no N5 applicability selector and no numerical engine ran.

The walker recursively enumerated all model fields, computed fields, populated private state, mapping keys/values, and sequence members, continuing after unsupported values. It also recorded non-null excluded fields, private values, non-string mapping keys, and computed-field errors; leaf values were not printed.

## candidate_high_conflict

Nodes: models=41, mappings=39, sequences=78; leaf occurrences=380.

Leaf type counts:

- `builtins.NoneType`: 45
- `builtins.bool`: 18
- `builtins.float`: 8
- `builtins.int`: 14
- `builtins.str`: 283
- `decimal.Decimal`: 2
- `enum:polisyos.ir.analytics.interventions.ProofKernelInterventionType -> builtins.str`: 6
- `enum:polisyos.ir.analytics.interventions.QueryTargetKind -> builtins.str`: 2
- `enum:polisyos.pdc._impl.world_model_record.BranchMode -> builtins.str`: 1
- `enum:polisyos.pdc._impl.world_model_record.SubstrateLayer -> builtins.str`: 1

Non-null excluded=0; populated private=0; non-string keys=0; computed errors=0.

The complete derived leaf-path/type list remains in the ignored source census cited above; it is reproducible from the pinned fixture and is not duplicated here.

Unsupported by bf465 codec:

```text
decimal.Decimal	request.intervention_atoms[0].direct_effect_bundle.params['rate']
decimal.Decimal	request.intervention_atoms[1].direct_effect_bundle.params['rate']
```

Excluded/private/key/computed exceptions:

```text
```

## candidate_feasible_single

Nodes: models=33, mappings=30, sequences=58; leaf occurrences=286.

Leaf type counts:

- `builtins.NoneType`: 35
- `builtins.bool`: 15
- `builtins.float`: 7
- `builtins.int`: 10
- `builtins.str`: 212
- `decimal.Decimal`: 1
- `enum:polisyos.ir.analytics.interventions.ProofKernelInterventionType -> builtins.str`: 3
- `enum:polisyos.ir.analytics.interventions.QueryTargetKind -> builtins.str`: 1
- `enum:polisyos.pdc._impl.world_model_record.BranchMode -> builtins.str`: 1
- `enum:polisyos.pdc._impl.world_model_record.SubstrateLayer -> builtins.str`: 1

Non-null excluded=0; populated private=0; non-string keys=0; computed errors=0.

The complete derived leaf-path/type list remains in the ignored source census cited above; it is reproducible from the pinned fixture and is not duplicated here.

Unsupported by bf465 codec:

```text
decimal.Decimal	request.intervention_atoms[0].direct_effect_bundle.params['rate']
```

Excluded/private/key/computed exceptions:

```text
```

---

