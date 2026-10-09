from pathlib import Path
p=Path('/workspace/ORCH04-C10/policy-engine/src/polisyos/runtime/quality/design_generation.py')
s=p.read_text()
anchor='class RecordingLLMClient:'
addition='''@dataclass(frozen=True)
class N4CandidateChildProblem:
    """A complete candidate subproblem restricted by an actual N4 atom.

    This is a candidate exploration boundary, not a modularity certificate.
    Source atom identities remain attached to their parent problem; the child
    must obtain a new context and generate its own child-bound atoms.
    """

    problem: DesignProblem
    source_result_ref: str
    source_atom_refs: tuple[str, ...]
    semantic_ref: str


def derive_n4_candidate_child_problems(
    problem: DesignProblem,
    result: GenerationUnderAResult,
    *,
    model_id: str,
) -> tuple[N4CandidateChildProblem, ...]:
    """Restrict the declared lever space using content-verified real N4 output.

    Different candidate names or provenance do not manufacture another child.
    Only distinct declared operator/target subsets are supported here; varying
    parameters of the same declared lever remain one exploration child. All
    subject, mandate, constraints, outcome, evidence, model and time fields are
    preserved exactly. No root execution grant is an input to this producer.
    """

    from polisyos.runtime.quality.design_problem import DesignProblem as ProblemModel

    if type(problem) is not ProblemModel or type(result) is not GenerationUnderAResult:
        raise DesignGenerationError("n4_recursive_child_source_untyped")
    problem = ProblemModel.model_validate(problem.model_dump(mode="python"))
    result = GenerationUnderAResult.model_validate(result.model_dump(mode="python"))
    root_ref = gy_content_hash(problem.model_dump(mode="json"))
    if result.design_problem_ref != root_ref:
        raise DesignGenerationError("n4_recursive_child_parent_mismatch")
    if result.model_id != model_id:
        raise DesignGenerationError("n4_recursive_child_model_mismatch")
    if result.status != "generated":
        return ()
    source_ref = gy_content_hash(result.model_dump(mode="json"))
    by_semantics: dict[str, tuple[list[object], list[str]]] = {}
    for candidate in result.candidates:
        atom = candidate.atom
        estimand = atom.intended_downstream_estimand
        if (
            atom.problem_frame_ref != root_ref
            or candidate.provenance.model_id != model_id
            or estimand.outcome_variables != (problem.outcome_of_interest.target_variable,)
            or estimand.target_population != problem.jurisdiction_time.region
            or (estimand.metric_id is not None and estimand.metric_id != problem.outcome_of_interest.metric_id)
        ):
            raise DesignGenerationError("n4_recursive_child_subject_mismatch")
        levers = [
            lever for lever in problem.candidate_lever_space.candidate_levers
            if lever.operator_kind == atom.operator_kind.trinity_kind
            and lever.target_slot in atom.target_world_slots
        ]
        if not levers or {lever.target_slot for lever in levers} != set(atom.target_world_slots):
            raise DesignGenerationError("n4_recursive_child_declared_lever_semantics_missing")
        # Semantic identity excludes candidate/atom names, timestamps and prose.
        semantic_ref = gy_content_hash({
            "operator_kind": atom.operator_kind.trinity_kind,
            "target_world_slots": sorted(atom.target_world_slots),
            "declared_levers": sorted(
                (lever.model_dump(mode="json") for lever in levers),
                key=lambda row: (row["operator_kind"], row["target_slot"], row["instrument"], row["lever_id"]),
            ),
        })
        if semantic_ref not in by_semantics:
            by_semantics[semantic_ref] = (levers, [])
        by_semantics[semantic_ref][1].append(atom.content_hash)
    children: list[N4CandidateChildProblem] = []
    for semantic_ref, (levers, atom_refs) in sorted(by_semantics.items()):
        payload = problem.model_dump(mode="python")
        payload["design_problem_id"] = "n4_candidate_child_" + semantic_ref.removeprefix("sha256:")[:24]
        payload["candidate_lever_space"] = {
            "allowed_operator_kinds": sorted({lever.operator_kind for lever in levers}),
            "candidate_levers": [lever.model_dump(mode="python") for lever in levers],
        }
        # These are source lineage facts, never interpreted as admission grants.
        payload["runtime_hints"] = {
            **problem.runtime_hints,
            "n4_candidate_child_source": {
                "purpose": "candidate_lever_exploration_only",
                "parent_design_problem_ref": root_ref,
                "source_result_ref": source_ref,
                "source_atom_refs": sorted(set(atom_refs)),
                "semantic_ref": semantic_ref,
            },
        }
        child = ProblemModel.model_validate(payload)
        children.append(N4CandidateChildProblem(
            problem=child,
            source_result_ref=source_ref,
            source_atom_refs=tuple(sorted(set(atom_refs))),
            semantic_ref=semantic_ref,
        ))
    return tuple(children)


'''
assert anchor in s;s=s.replace(anchor,addition+anchor)
s=s.replace('    "N4CandidateProposalSource",','    "N4CandidateChildProblem",\n    "N4CandidateProposalSource",')
s=s.replace('    "default_firewall_evidence",','    "default_firewall_evidence",\n    "derive_n4_candidate_child_problems",')
p.write_text(s)
