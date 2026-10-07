"""Bind the finite inspected consumer window and explicit missing owner inputs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/e02-F-tmle-20261006")
scratch = Path(__file__).resolve().parent
native = "0c81614f5aa737a4b26c6c74044955a842b26cf4"
candidate = "8d94a937ca6e3f886ada9ad5c1f76dadb049da84"
root = "8236d9c368336a5ea20c1586f29aea7321db6536"
dependency = "072d45a56d1119fe3e7665cec2cbbdca015d2934"
g = "9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7"
def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo)
def bound(ref, path):
    raw = git("show", ref + ":" + path)
    return {"git_ref": ref, "path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "git_blob": git("rev-parse", ref + ":" + path).decode().strip()}
spec = json.loads((scratch / "native-spec.json").read_bytes())
providers = spec["guard_paths"][:9]
provider_bindings = []
for path in providers:
    bindings = [bound(ref, path) for ref in (root, native, candidate)]
    assert len({item["git_blob"] for item in bindings}) == 1, path
    provider_bindings.append(bindings)
runtime_paths = [
    "policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py",
    "policy-engine/src/polisyos/runtime/http/services/control/evaluation_safety.py",
    "policy-engine/src/polisyos/pdc/_impl/evaluation_safety.py",
]
runtime_bindings = []
for path in runtime_paths:
    bindings = [bound(ref, path) for ref in (g, dependency, native, candidate)]
    assert len({item["git_blob"] for item in bindings}) == 1, path
    runtime_bindings.append(bindings)
delta = git("diff", "--name-only", native, candidate).decode().splitlines()
assert delta == ["policy-engine/release-fragments/unreleased/2026-10-07-tmle-persisted-consumers.toml"]
common_path = "policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/continuation-2026-10-07/COMMON.md"
card = "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FIT-01.md"
packet = {
    "schema": "policyos.e02.consumer_source_and_owner_packet.v1",
    "candidate_sha": candidate, "candidate_tree": git("rev-parse", candidate + "^{tree}").decode().strip(),
    "native_test_source": native,
    "root_product_source": root,
    "dependency_carrier": dependency,
    "fetched_G_input": g,
    "provider_denominator": 9, "provider_byte_equivalence": provider_bindings,
    "runtime_inspected_denominator": 3, "runtime_byte_equivalence": runtime_bindings,
    "metadata_only_delta": delta,
    "new_source_paths": [bound(candidate, path) for path in spec["guard_paths"][9:]],
    "original_card": bound(g, card), "continuation_instructions": bound(g, common_path),
    "scope": "These named maintained consumers/default suppliers are inspected; no repository-wide absence or external-client census is inferred.",
    "missing_owner_packets": [
        {"plane": "statistical_identification", "outcome": "UNRUN", "owner": "existing causal identification/IR semantic owner coordinated by ROOT/C", "producer": "existing ProofBundle and proof_bundle_from_identification_result project identification results; they are not the accepted gate admission input", "consumer": "CausalEffectReport.to_uncertainty_envelope and ConfidencePass.validate", "source_boundary": "IR report converter has no accepted identification verifier input; current Confidence causal-purpose role remains blocked", "required_input": ["accepted existing issuer/verifier API and exact artifact/input contract", "content-bound observation source, graph, estimand type, treatment contrast, target/population and current revision", "actual producer-issued positive receipt and fresh consumer challenge"], "negative_falsifier": "Missing, fake, stale and swapped source/graph/estimand/target proof must retain candidate/BLOCKER with numerical SUCCESS and CI unchanged", "reason_unavailable": "No accepted statistical admission bridge is supplied for this maintained consumer window; operational safety is a different plane"},
        {"plane": "operational_evaluation_admission", "outcome": "UNRUN", "owner": "Runtime/A and canonical institutional authority suppliers", "producer": "EvaluationSafetyPersistenceService.compose_and_persist_attempt", "consumer": "EvaluationSafetyAdmissionVerifier.require_admission, EvalSafetyVerifierPort and evaluation_safety_consumer_admission_is_verified", "source_boundary": "run_lifecycle default authority resolver blocked/not_established; appointment resolver blocked/unappointed; registry None; attempt basis/pack/facet denominator absent, evidence empty", "required_input": ["real appointed authority/verification suppliers and current CAS basis/pack/facet/evidence/revision material", "actual resolved passed intake and Runtime-produced complete EvaluationExecutionContext", "fresh EvalSafetyAdmissionChallenge matching owner/intake/certificate/current revision"], "negative_falsifier": "Present-but-fake seal, stale revision, mismatched full context or replay evidence must refuse", "reason_unavailable": "Maintained defaults do not supply this institutional packet; injected unit suppliers are not admitted production inputs"},
        {"plane": "native_value_projection", "outcome": "UNRUN", "owner": "canonical output-contract/value owner coordinated by C/ROOT", "producer": "TMLEEstimator.signature report SlotSpec and CausalEffectReport", "consumer": "project_method_value_evidence", "source_boundary": "Actual consumer returns method_output_contract_unresolved before downstream gate predicate", "required_input": ["declared SlotSpec contract_id, native canonical contract owner and VALUE_UNCERTAINTY_PROJECTION capability", "matching native owner declaration, supported projection and content-bound NativeValueEstimandBinding"], "negative_falsifier": "Wrong native contract/owner/estimand binding refuses; an operational safety receipt cannot replace this contract", "reason_unavailable": "Current real TMLE report slot lacks the native value contract; no parallel projection is invented"},
        {"plane": "B56_actual_admitted_study_budget", "outcome": "UNRUN", "owner": "Runtime/B/C actual study/workload suppliers and G local runner", "producer": "actual admitted common study and configured MethodJobs/repeats/seeds/models/competing jobs", "consumer": "existing LocalRunnerPool.wait admission and common CausalEvaluation consumer", "source_boundary": "This fixture is one MethodJob, not an admitted common-study workload", "required_input": ["actual owner study/workload refs and full jobs/models/seeds/repeats denominator", "existing execution context and concrete budget/admission inputs", "exact candidate run receipt over competing admitted studies"], "negative_falsifier": "Without canonical context preserve execution_context_missing before fit; with genuine supplied context execute every configured fold and enforce existing outer-job permits", "reason_unavailable": "No actual admitted workload/context packet was supplied; no new global scheduler/quota is created"},
    ],
    "G_acceptance": "UNRUN; ordinary topic delivery and code review do not imply integration or finding closure",
}
(scratch / "source-and-owner-packet.json").write_text(json.dumps(packet, indent=2) + "\n")
print(json.dumps({"provider_byte_equivalence": 9, "runtime_byte_equivalence": 3, "metadata_only_delta": delta, "missing_positive_packets": len(packet["missing_owner_packets"])}))
