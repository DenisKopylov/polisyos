from pathlib import Path
p=Path('/workspace/ORCH04-C10/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py');s=p.read_text()
s=s.replace('        N4CandidateProposalSource,\n','        N4CandidateProposalSource,\n        GenerationUnderAResult,\n')
s=s.replace('        RecursiveGenerationCycleController,\n','        RecursiveGenerationCycleController,\n        RecursiveLeafContextOwner,\n')
s=s.replace('    root_n4_generation_port: N4GenerationPort | None = None,\n','    root_n4_generation_port: N4GenerationPort | None = None,\n    n4_recursive_source: GenerationUnderAResult | None = None,\n    recursive_leaf_context_owner: RecursiveLeafContextOwner | None = None,\n')
s=s.replace('        not n4_proposal_only or execution_intent != "simulate_only"\n','        (not n4_proposal_only and n4_recursive_source is None)\n        or execution_intent != "simulate_only"\n')
anchor='    root_ref = f"design-problem://{problem_ref.removeprefix(\'sha256:\')}"\n'
addition='''    # The internal candidate-child route takes complete immutable actual N4
    # source. HTTP request dictionaries cannot allocate this source or owner.
    problems_by_node = None
    contexts_by_node = None
    handoffs_by_node = None
    generation_ports_by_node = None
    if n4_recursive_source is not None:
        from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextHandoff
        from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems
        from polisyos.runtime.quality.generation_cycle import N4GenerationPort
        from polisyos.runtime.quality.recursive_generation_cycle import RecursiveLeafContextOwner

        if execution_intent != "simulate_only" or root_evaluation_context is not None:
            raise DesignProblemAuthorityError("n4_recursive_child_intent_not_candidate")
        if type(recursive_leaf_context_owner) is not RecursiveLeafContextOwner:
            raise DesignProblemAuthorityError("n4_recursive_child_context_owner_missing")
        if cycle_substrate_context_resolver is None:
            raise DesignProblemAuthorityError("n4_recursive_child_context_resolver_missing")
        children = derive_n4_candidate_child_problems(problem, n4_recursive_source, model_id=model_name)
        if not children:
            raise DesignProblemAuthorityError("n4_recursive_child_source_empty")
        if recursive_budget.max_depth < 1 or recursive_budget.max_nodes < 1 + len(children):
            raise DesignProblemAuthorityError("n4_recursive_child_supported_budget_missing")
        problems_by_node = {}
        contexts_by_node = {}
        handoffs_by_node = {}
        generation_ports_by_node = {}
        root_scope = (
            (candidate_simulation_handoff.job_id, candidate_simulation_handoff.run_id,
             candidate_simulation_handoff.tenant_id, candidate_simulation_handoff.cell_id)
            if candidate_simulation_handoff is not None else None
        )
        for child in children:
            child_ref = "design-problem://" + gy_content_hash(child.problem.model_dump(mode="json")).removeprefix("sha256:")
            handoff = cycle_substrate_context_resolver(child.problem)
            if type(handoff) is not CandidateSimulationContextHandoff:
                raise DesignProblemAuthorityError("n4_recursive_child_configured_context_missing")
            scope = (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id)
            if root_scope is not None and scope != root_scope:
                raise DesignProblemAuthorityError("n4_recursive_child_job_scope_mismatch")
            problems_by_node[child_ref] = child.problem
            contexts_by_node[child_ref] = handoff.context
            handoffs_by_node[child_ref] = handoff
            generation_ports_by_node[child_ref] = N4GenerationPort(
                model_id=model_name, repo_root=repo_root,
                cycle_substrate_context=handoff.context,
                candidate_simulation_handoff=handoff,
            )

'''
assert anchor in s;s=s.replace(anchor,addition+anchor)
s=s.replace('        module_refs=(),\n        parent_child_edges=(),\n        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",','        module_refs=tuple(problems_by_node or ()),\n        parent_child_edges=tuple((root_ref, child_ref) for child_ref in problems_by_node or ()),\n        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",',1)
s=s.replace('            problems_by_node={root_ref: problem},','            problems_by_node={root_ref: problem, **(problems_by_node or {})},',1)
s=s.replace('            cycle_substrate_contexts_by_node=(\n                {root_ref:', '            cycle_substrate_contexts_by_node=contexts_by_node or (\n                {root_ref:',1)
s=s.replace('            candidate_simulation_handoffs_by_node=(\n                {root_ref:', '            candidate_simulation_handoffs_by_node=handoffs_by_node or (\n                {root_ref:',1)
s=s.replace('            candidate_simulation_currentness_resolvers_by_node=(\n                {root_ref:', '            candidate_simulation_currentness_resolvers_by_node={} if handoffs_by_node else (\n                {root_ref:',1)
s=s.replace('            n4_generation_ports_by_node=(\n                {root_ref:', '            n4_generation_ports_by_node=generation_ports_by_node or (\n                {root_ref:',1)
s=s.replace('            evaluation_contexts_by_node=(\n                {root_ref:', '            evaluation_contexts_by_node=None if handoffs_by_node else (\n                {root_ref:',1)
s=s.replace('            execution_intents_by_node={root_ref: execution_intent},','            execution_intents_by_node=dict.fromkeys(problems_by_node or (root_ref,), execution_intent),\n            leaf_context_owner=recursive_leaf_context_owner,',1)
p.write_text(s)
