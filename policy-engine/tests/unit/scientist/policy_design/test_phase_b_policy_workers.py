from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from polisyos.scientist.methods.autotune.models import BenchmarkSplitManifest
from polisyos.scientist.methods.doe.designs import ParameterSpec as DOEParameterSpec
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.policy_design.adversary import (
    ScenarioAdversaryConfig,
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)
from polisyos.scientist.policy_design.critic import ConstraintCritic, ConstraintCriticInput
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionEntry,
    ConstraintSatisfactionReport,
    PolicyBrief,
    SubgroupImpactEntry,
    SubgroupImpactReport,
    UncertaintyReport,
)
from polisyos.scientist.policy_design.translator import (
    DeterministicPolicyTranslator,
    PolicyTranslatorWorker,
    TranslatorCompliancePass,
    TranslatorInputBundle,
)

from .test_phase_b_output import _candidate, _evaluation_vector


def _readiness_contract() -> DecisionReadinessContract:
    return DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural", "statistical"],
        required_uncertainty_bounds={},
        mandatory_human_gate=True,
        assumptions_must_be_surfaced=[
            "Elasticity remains stable in the policy horizon.",
            "Hard constraint near binding: policy_budget_constraint",
        ],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="meta_analytic",
    )


def _translator_bundle() -> TranslatorInputBundle:
    dossier = ChampionPolicyDossier(
        candidate_id="candidate_policy",
        candidate_hash="sha256:" + "a" * 64,
        readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
        executive_summary="Candidate candidate_policy is assessed at recommendation_ready.",
        objective_summary={"policy_value": 1.2, "employment": 0.4},
        constraint_summary=[
            ConstraintSatisfactionEntry(
                constraint_name="policy_budget_constraint",
                status="near_binding",
                observed_value=0.95,
                threshold=1.0,
            )
        ],
        subgroup_harms=["Low income"],
        surfaced_assumptions=_readiness_contract().assumptions_must_be_surfaced,
        uncertainty_summary={"statistical": 0.2, "structural": 0.3},
        transport_summary={},
        governance_summary={},
        stress_summary={},
    )
    return TranslatorInputBundle(
        dossier=dossier,
        readiness_contract=_readiness_contract(),
        constraint_report=ConstraintSatisfactionReport(
            candidate_id="candidate_policy",
            feasible=True,
            constraints=dossier.constraint_summary,
        ),
        subgroup_report=SubgroupImpactReport(
            candidate_id="candidate_policy",
            harmed_subgroups=[
                SubgroupImpactEntry(
                    subgroup_id="low_income",
                    label="Low income",
                    direction="negative",
                    net_impact=-1.0,
                    vulnerable=True,
                )
            ],
        ),
        uncertainty_report=UncertaintyReport(
            candidate_id="candidate_policy",
            readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
            uncertainties={"statistical": 0.2, "structural": 0.3},
            binding_types=[],
        ),
        budget_state=BudgetState(),
    )


def test_translator_falls_back_deterministically_without_gateway() -> None:
    bundle = _translator_bundle()
    brief = PolicyTranslatorWorker().translate(bundle)

    assert brief.readiness_level == DecisionReadiness.RECOMMENDATION_READY.value
    assert bundle.readiness_contract.assumptions_must_be_surfaced == brief.surfaced_assumptions
    assert "Low income" in brief.subgroup_harms
    assert "policy_budget_constraint" in brief.hard_constraint_notes


@pytest.mark.asyncio
async def test_translator_gateway_parses_think_prefixed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _translator_bundle().model_copy(update={"budget_state": None})
    payload = DeterministicPolicyTranslator().translate(bundle).model_dump(mode="json")
    payload["title"] = "Think-prefixed real translation"

    class _Client:
        async def generate(self, **kwargs: object) -> SimpleNamespace:
            del kwargs
            return SimpleNamespace(
                content="<think>translation reasoning</think>" + json.dumps(payload)
            )

    monkeypatch.setattr(
        "polisyos.scientist.policy_design.translator.create_traced_gateway_client",
        lambda **kwargs: _Client(),
    )

    brief = await PolicyTranslatorWorker().translate_async(bundle)

    assert brief.title == "Think-prefixed real translation"
    assert brief.metadata.get("translator_mode") == "deterministic"


@pytest.mark.asyncio
async def test_materialized_translator_reuses_only_the_exact_scoped_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch, record_property
) -> None:
    """Read real selected CAS views, then charge one provider and each reuse."""
    import hashlib
    import threading
    from decimal import Decimal
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from polisyos.core.artifacts import FileSystemCAS, PutOptions, artifact_manifest_profile_sha256
    from polisyos.scientist import policy_design
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm import prompt_cache
    from polisyos.scientist.orchestration.llm.factory import _gateway_cache_reuse_scope
    from polisyos.scientist.orchestration.llm.prompt_cache import (
        CacheReuseDecision,
        CacheReusePrincipal,
        InMemoryPromptCache,
    )
    from polisyos.scientist.policy_design import translator

    assert policy_design.TranslatorMaterialization is translator.TranslatorMaterialization
    assert policy_design.materialize_translator_inputs is translator.materialize_translator_inputs
    bundle = _translator_bundle().model_copy(update={"budget_state": None, "run_id": "run-a"})
    dossier = bundle.dossier.model_copy(
        update={
            "executive_summary": "Literal evidence at https://example.org/input",
            "metadata": {"uncertainty_notes": "A frozen statement, not live retrieval"},
        }
    )
    bundle = bundle.model_copy(update={"dossier": dossier})
    other = bundle.model_copy(
        update={
            "dossier": dossier.model_copy(update={"executive_summary": "Second bundle"}),
            "implementation_plan": translator.ImplementationPlan(candidate_id="candidate_policy"),
        }
    )
    store = FileSystemCAS(tmp_path / "cas")
    selections = [
        translator.materialize_translator_inputs(store, bundle),
        translator.materialize_translator_inputs(store, other),
    ]
    snapshot = store.put_bytes(
        b"scope snapshot",
        PutOptions(kind="translator.test.snapshot", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    references = {str(snapshot.artifact_id): snapshot}
    for selection in selections:
        references.update(
            {str(ref.artifact_id): ref for _, ref in selection.role_refs if ref is not None}
        )
    seen_requests = []

    class Owner:
        def authorize_reuse(self, request):
            seen_requests.append(request)
            if (
                request.materialization_profile != "policy_translator_plain_completion.v1"
                or request.actor_id != "actor-a"
                or request.tenant != "tenant-a"
                or request.scope != "tenant-a/cell-a"
                or request.purpose != "llm_snapshot_reuse"
                or request.provider_route != "fixture-provider"
            ):
                return None
            if request.absent_roles not in {(), ("implementation_plan",)}:
                return None
            role_items = [item for item in request.evidence if item.role is not None]
            if {item.role for item in role_items} != {
                "dossier",
                "readiness_contract",
                "constraint_report",
                "subgroup_report",
                "uncertainty_report",
                *(() if request.absent_roles else ("implementation_plan",)),
            }:
                return None
            for item in request.evidence:
                ref = references.get(item.ref)
                if ref is None:
                    return None
                content = store.get_bytes(ref)
                manifest = store.get_manifest(ref)
                if (
                    item.content != content
                    or item.content_hash != "sha256:" + hashlib.sha256(content).hexdigest()
                    or item.version != artifact_manifest_profile_sha256(manifest)
                    or (item.role is not None and json.loads(content).get("role") != item.role)
                    or (item.role is not None and item.kind != manifest.kind)
                    or (item.role is not None and item.media_type != manifest.media_type)
                ):
                    return None
            return CacheReuseDecision(
                issuer="test-owner",
                epoch="epoch-1",
                actor_id=request.actor_id,
                tenant=request.tenant,
                scope=request.scope,
                purpose=request.purpose,
                model=request.model,
                parameters_digest=request.parameters_digest,
                evidence=request.evidence,
                materialization_profile=request.materialization_profile,
                absent_roles=request.absent_roles,
                provider_route=request.provider_route,
            )

    provider_requests = []
    brief = DeterministicPolicyTranslator().translate(bundle).model_dump(mode="json")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            provider_requests.append(request)
            user = json.loads(request["messages"][-1]["content"])
            result = dict(brief)
            result["title"] = user["input"]["dossier"]["executive_summary"]
            body = json.dumps(
                {
                    "id": f"completion-{len(provider_requests)}",
                    "model": "fixture-model",
                    "choices": [{"message": {"role": "assistant", "content": json.dumps(result)}}],
                    "usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 3,
                        "total_tokens": 5,
                        "cost_usd": 0.02,
                    },
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", f"http://{host}:{port}/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-fixture-translation-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PROVIDER", "fixture-provider")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    monkeypatch.delenv("POLISYOS_LLM_GATEWAY_PRESET", raising=False)
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PRIVACY_SANITIZATION", "false")
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    clients = []
    factory = translator.create_traced_gateway_client

    def tracked_factory(**kwargs):
        client = factory(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(translator, "create_traced_gateway_client", tracked_factory)
    context = {
        "tenant": "tenant-a",
        "scope": "tenant-a/cell-a",
        "purpose": "translator-candidate",
        "snapshot": {
            "ref": str(snapshot.artifact_id),
            "version": snapshot.manifest_profile_sha256,
            "immutable": True,
            "content": b"scope snapshot",
            "content_hash": "sha256:" + hashlib.sha256(b"scope snapshot").hexdigest(),
        },
    }
    ledger_path = tmp_path / "ledger.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    run_binding = BudgetLedgerProducerRunBinding(
        run_id="run-a",
        control_job_id="job-a",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="test",
    )
    worker = translator.PolicyTranslatorWorker(
        translator.PolicyTranslatorConfig(
            model_name="fixture-model", temperature=0, fallback_on_error=False
        )
    )
    try:
        with (
            middleware.producer_run_binding_scope(run_binding, control_job_attempt=1),
            _gateway_cache_reuse_scope(
                authorizer=Owner(),
                principal=CacheReusePrincipal("actor-a", "tenant-a", "tenant-a/cell-a"),
                context=context,
                cache=InMemoryPromptCache(),
                run_id="run-a",
                settlement_store=middleware,
                reuse_guard=lambda operation: operation(),
            ),
        ):
            first = await worker.translate_async(bundle, materialization=selections[0])
            tracer_module = type(clients[0]._tracer).__module__
            assert tracer_module in {
                "polisyos.core.observability",
                "polisyos.core.observability.tracer",
            }
            record_property("tracer_implementation", tracer_module)
            again = await worker.translate_async(bundle, materialization=selections[0])
            assert first.title == again.title == dossier.executive_summary
            assert len(provider_requests) == 1
            second = await worker.translate_async(other, materialization=selections[1])
            assert (await worker.translate_async(other, materialization=selections[1])) == second
            assert second.title == "Second bundle"
            assert len(provider_requests) == 2

            # A different selected payload must not reuse either cached response.
            await worker.translate_async(bundle, materialization=selections[1])
            await worker.translate_async(bundle, materialization=selections[1])
            assert len(provider_requests) == 4

            roles = selections[0].role_refs
            selected_ref = roles[0][1]
            assert selected_ref is not None
            wrong_profile = selected_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "0" * 64}
            )
            wrong_kind = selected_ref.model_copy(update={"kind": "foreign.kind"})
            bad_selections = [
                translator.TranslatorMaterialization(store, (*roles[:-2], roles[-1])),
                translator.TranslatorMaterialization(store, (*roles, ("live_retrieval", None))),
                translator.TranslatorMaterialization(
                    store, ((roles[0][0], wrong_profile), *roles[1:])
                ),
                translator.TranslatorMaterialization(
                    store, ((roles[0][0], wrong_kind), *roles[1:])
                ),
                translator.TranslatorMaterialization(
                    store, ((roles[0][0], roles[1][1]), *roles[1:])
                ),
            ]
            for selection in bad_selections:
                count = len(provider_requests)
                await worker.translate_async(bundle, materialization=selection)
                assert len(provider_requests) == count + 1

            # Refusing bad materializations does not destroy the valid entry.
            assert (await worker.translate_async(bundle, materialization=selections[0])) == first
            assert len(provider_requests) == 9

            # Actual sanitizer transformation changes the prepared prompt. The
            # raw materialization cannot authorize the different wire input.
            private_bundle = bundle.model_copy(
                update={
                    "dossier": dossier.model_copy(
                        update={"executive_summary": "Contact author@example.org"}
                    )
                }
            )
            private_selection = translator.materialize_translator_inputs(store, private_bundle)
            monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "true")
            await worker.translate_async(private_bundle, materialization=private_selection)
            await worker.translate_async(private_bundle, materialization=private_selection)
            assert len(provider_requests) == 11
            assert all("author@example.org" not in str(item) for item in provider_requests[-2:])

            # Factory settings can add features after the caller's kwargs. The
            # actual prepared Gateway body must remain plain, not merely hashable.
            monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
            auth_count = len(seen_requests)
            monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PRESET", "live-retrieval")
            await worker.translate_async(bundle, materialization=selections[0])
            await worker.translate_async(bundle, materialization=selections[0])
            assert len(provider_requests) == 13
            assert all(item["preset"] == "live-retrieval" for item in provider_requests[-2:])
            monkeypatch.delenv("POLISYOS_LLM_GATEWAY_PRESET")
            monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PRIVACY_SANITIZATION", "true")
            await worker.translate_async(bundle, materialization=selections[0])
            await worker.translate_async(bundle, materialization=selections[0])
            assert len(provider_requests) == 15
            assert all(item["plugins"] for item in provider_requests[-2:])
            monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PRIVACY_SANITIZATION", "false")

            # These controls cannot borrow a closed profile's cache entry.
            for control in (
                {"tools": [{"type": "function", "function": {"name": "lookup"}}]},
                {"stream": True},
                {"seed": 11},
            ):
                client = tracked_factory(model_name="fixture-model", run_id="run-a")
                for _ in range(2):
                    with translator.translator_materialization_scope(selections[0]):
                        await client.generate(
                            system=translator.get_policy_translator_prompt(),
                            user=translator.build_policy_translator_user_payload(
                                translator._translator_payload(bundle)
                            ),
                            response_format={"type": "json_object"},
                            temperature=0,
                            max_tokens=1800,
                            **control,
                        )
            assert len(provider_requests) == 21
            assert len(seen_requests) == auth_count

            # A removal control substitutes an innocuous body only at the
            # binder boundary, preserving the actual preset-enabled dispatch.
            # The second invocation then reuses; restoring the real body
            # forces physical dispatch again even though that entry exists.
            monkeypatch.setenv("POLISYOS_LLM_GATEWAY_PRESET", "live-retrieval")
            real_binder = prompt_cache.bind_current_translator_materialization

            def omit_actual_wire(args, kwargs, *, model, prepared_wire_payload):
                del prepared_wire_payload
                benign_body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": kwargs["system"]},
                        {"role": "user", "content": kwargs["user"]},
                    ],
                    "response_format": kwargs["response_format"],
                    "temperature": kwargs["temperature"],
                    "max_tokens": kwargs["max_tokens"],
                }
                if "_run_id" in kwargs:
                    benign_body["_run_id"] = kwargs["_run_id"]
                return real_binder(
                    args,
                    kwargs,
                    model=model,
                    prepared_wire_payload=json.dumps(benign_body).encode(),
                )

            with monkeypatch.context() as removal:
                removal.setattr(
                    prompt_cache, "bind_current_translator_materialization", omit_actual_wire
                )
                await worker.translate_async(bundle, materialization=selections[0])
                await worker.translate_async(bundle, materialization=selections[0])
                assert len(provider_requests) == 22
            await worker.translate_async(bundle, materialization=selections[0])
            assert len(provider_requests) == 23

            # A caller's cacheability/closure declaration is not an owner
            # materialization, even with the otherwise identical prompt.
            monkeypatch.delenv("POLISYOS_LLM_GATEWAY_PRESET")
            forged_client = tracked_factory(model_name="fixture-model", run_id="run-a")
            for _ in range(2):
                await forged_client.generate(
                    system=translator.get_policy_translator_prompt(),
                    user=translator.build_policy_translator_user_payload(
                        translator._translator_payload(bundle)
                    ),
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=1800,
                    metadata={"cacheable": True, "translator_closure": "closed"},
                )
            assert len(provider_requests) == 25
    finally:
        for client in clients:
            if client is not None:
                await client.unwrap().aclose()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert len(seen_requests) >= 4
    assert {len(request.evidence) for request in seen_requests} == {6, 7}
    assert all("https://example.org/input" in str(request) for request in provider_requests[:1])
    assert all("cache_reuse" not in str(request) for request in provider_requests)
    assert all("tools" not in request for request in provider_requests[:15])
    records = tuple(FileBudgetLedger(ledger_path).snapshot().producer_settlements.values())
    assert sum(item.cost_origin == "reported" for item in records) == 25
    assert sum(item.cost_origin == "reuse" for item in records) == 4
    assert sum((item.amount or Decimal(0)) for item in records) == Decimal("0.50")


def test_translator_surfaces_degraded_evidence_channels() -> None:
    bundle = _translator_bundle()
    bundle = bundle.model_copy(
        update={
            "readiness_contract": bundle.readiness_contract.model_copy(
                update={
                    "metadata": {
                        "cross_graph_source_statuses": {
                            "academic": "missing_config",
                            "datasets": "missing_path",
                        },
                        "prior_knowledge_status": "degraded",
                    }
                }
            )
        }
    )

    brief = PolicyTranslatorWorker().translate(bundle)
    descriptions = [risk.description for risk in brief.risks]

    assert any(
        "academic" in description and "missing_config" in description
        for description in descriptions
    )
    assert any(
        "datasets" in description and "missing_path" in description for description in descriptions
    )
    assert any(
        "Academic prior support is unavailable or degraded" in description
        for description in descriptions
    )


def test_translator_compliance_flags_all_anti_spin_invariants() -> None:
    bundle = _translator_bundle()
    brief = PolicyBrief(
        title="Spinny brief",
        executive_summary="Everything is deployment ready and safe.",
        readiness_level=DecisionReadiness.DEPLOYMENT_READY.value,
        surfaced_assumptions=[],
        uncertainty_highlights=[],
        subgroup_harms=[],
        hard_constraint_notes=[],
    )

    result = TranslatorCompliancePass().evaluate(
        brief,
        dossier=bundle.dossier,
        readiness_contract=bundle.readiness_contract,
        constraint_report=bundle.constraint_report,
        subgroup_report=bundle.subgroup_report,
        uncertainty_report=bundle.uncertainty_report,
    )

    codes = {finding.code for finding in result.findings}
    assert result.passed is False
    assert "readiness_overstated" in codes
    assert "assumptions_omitted" in codes
    assert "uncertainty_collapsed" in codes
    assert "negative_harm_omitted" in codes
    assert "binding_constraints_omitted" in codes


def test_constraint_critic_surfaces_budget_and_not_assessed_findings() -> None:
    candidate = _candidate()
    candidate = candidate.model_copy(
        update={
            "budget_allocation": [
                item.model_copy(
                    update={"amount": item.amount.model_copy(update={"amount": Decimal("95")})}
                )
                for item in candidate.budget_allocation
            ]
        }
    )
    critique = ConstraintCritic().evaluate(
        ConstraintCriticInput(
            candidate=candidate,
            evaluation_vector=_evaluation_vector(candidate),
        )
    )

    failure_types = {finding.failure_type for finding in critique.findings}
    assert critique.passed is True
    assert "budget_driver" in failure_types
    assert "overlap_not_assessed" in failure_types
    assert "binding_hard_constraint" in failure_types


def test_scenario_adversary_fallback_and_execution(tmp_path) -> None:
    worker = ScenarioAdversaryWorker(ScenarioAdversaryConfig(max_scenarios=3, collect_top_k=2))
    surface = ScenarioAttackSurface(
        candidate_id="candidate_policy",
        parameter_specs=[
            DOEParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0),
            DOEParameterSpec(name="noise", lower_bound=0.0, upper_bound=1.0),
        ],
        base_metrics={"gdp_change": [0.1, 0.2, 0.3]},
        benchmark_split_manifest=BenchmarkSplitManifest(
            suite_id="suite",
            selection_ids=["a"],
            holdout_ids=["b"],
        ),
        vulnerability_threshold=0.5,
    )
    bundle = worker.propose(surface, run_id="adv_test", budget_state=BudgetState())

    assert bundle.fallback_used is True
    assert bundle.scenarios
    assert any(item.target_split == "hidden_holdout_only" for item in bundle.scenarios)

    result = worker.execute(
        surface=surface,
        base_objective=CompositeObjective([GDPGrowthObjective()]),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {
                "gdp_change": float(candidate.get("shock", 0.0))
                + float(candidate.get("noise", 0.0))
            }
        },
        cas=None,
        run_id="adv_test",
    )

    assert result.compiled_plan.parameter_specs
    report = result.stress_test_report
    assert report.total_scenarios_evaluated >= 1
    # Bare numeric metrics without a declared unit or persisted objective basis
    # still exercise the fallback, but cannot establish a scored vulnerability.
    assert report.vulnerabilities == []
    assert report.score_status == "unbound"
    assert report.robustness_score is None
    assert not report.is_robust
    assert report.score_predicate_status == "not_established"
    assert report.set_adequacy_status == "unverified"
    assert report.metadata["objective_score_admission_status"] == "unavailable"
    assert report.metadata["objective_score_admission_reason"] == "objective_basis_incomplete"
    assert report.metadata["skipped_evaluation_count"] == report.total_scenarios_evaluated
    assert report.metadata["valid_evaluation_count"] == 0
    assert report.metadata["invalid_evaluation_count"] == 0
    assert report.metadata["unknown_evaluation_count"] == 0


@pytest.mark.asyncio
async def test_scenario_adversary_gateway_parses_think_prefixed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    surface = ScenarioAttackSurface(
        candidate_id="candidate_think_prefixed",
        parameter_specs=[DOEParameterSpec(name="shock", lower_bound=0.0, upper_bound=1.0)],
    )
    payload = {
        "scenarios": [
            {
                "scenario_id": "adv_think_prefixed",
                "scenario_type": "shift",
                "parameter_name": "shock",
                "intensity": 0.25,
                "rationale": "Real model scenario.",
            }
        ]
    }

    class _Client:
        async def generate(self, **kwargs: object) -> SimpleNamespace:
            del kwargs
            return SimpleNamespace(
                content="<think>adversary reasoning</think>" + json.dumps(payload)
            )

    monkeypatch.setattr(
        "polisyos.scientist.policy_design.adversary.create_traced_gateway_client",
        lambda **kwargs: _Client(),
    )

    bundle = await ScenarioAdversaryWorker().propose_async(surface)

    assert bundle.fallback_used is False
    assert [scenario.scenario_id for scenario in bundle.scenarios] == ["adv_think_prefixed"]
