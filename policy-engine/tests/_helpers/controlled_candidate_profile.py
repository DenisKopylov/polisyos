"""Shared controlled candidate-scenario inputs for served N4→N5 tests.

The fixture remains candidate-only: the replay changes one integer parameter and
records its exact target/outcome path; the configured model is a declared synthetic
SCM and does not establish empirical grounding, source time, S8, or N9 authority.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.llm.response import _recorded_usage_payload, _usage_quantity
from polisyos.ir.artifacts import ArtifactStore
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import CandidateGroundingObservation
from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

if TYPE_CHECKING:
    from polisyos.ir.kernel import SlotSpec


from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SyntheticCandidateProviderProfile:
    """Explicit candidate-only provider inputs, never a historical billing replay.

    Each row is an immutable JSON string carrying its exact parent response key,
    controlled output identity, source model and synthetic usage declaration.
    Existing agent validators and cost settlement remain the actual consumers.
    """

    model_id: str
    profile_selection_ref: str
    source_recording_id: str
    source_recording_content_hash: str
    controlled_recording_content_hash: str
    response_rows: tuple[tuple[str, str], ...]
    evidence_root: Path

    def __post_init__(self) -> None:
        from polisyos.scientist.orchestration.llm._n4_request import _STAGES

        if {stage for stage, _ in self.response_rows} != _STAGES or len(self.response_rows) != len(
            _STAGES
        ):
            raise ValueError("synthetic_provider_stage_set_incomplete")
        for _stage, encoded in self.response_rows:
            row = json.loads(encoded)
            if row.get("status") != "success" or row.get("source_model_id") != self.model_id:
                raise ValueError("synthetic_provider_response_source_incompatible")
            if gy_content_hash(row.get("raw_response")) != row.get("raw_response_hash"):
                raise ValueError("synthetic_provider_response_content_mismatch")
            usage = row.get("usage")
            if (
                not isinstance(usage, dict)
                or usage.get("usage_status") != "known"
                or _usage_quantity(usage).status != "known"
                or row.get("usage_declaration")
                != "new_synthetic_test_input_not_provider_measurement"
                or row.get("legacy_counter_availability") != "not_established"
            ):
                raise ValueError("synthetic_provider_usage_not_established")
            if not row.get("parent_response_hash") or not row.get("parent_role"):
                raise ValueError("synthetic_provider_response_lineage_missing")

    def descriptor(self) -> dict[str, Any]:
        """Return the declared input identity without copying source payloads."""
        rows = [
            {"stage": stage, "response_sha256": hashlib.sha256(encoded.encode()).hexdigest()}
            for stage, encoded in self.response_rows
        ]
        return {
            "schema_version": "test.synthetic_candidate_provider.v1",
            "source_recording_id": self.source_recording_id,
            "source_recording_content_hash": self.source_recording_content_hash,
            "controlled_recording_content_hash": self.controlled_recording_content_hash,
            "configured_model": self.model_id,
            "profile_selection_ref": self.profile_selection_ref,
            "usage_basis": "explicit_new_synthetic_values_from_source_counters_not_measured_usage",
            "cost_scope": "current_configured_model_estimate_not_historical_billing",
            "authority": "candidate_only_not_external_evidence",
            "stages": rows,
        }

    def completion(
        self,
        request: dict[str, Any],
        *,
        raw_request: bytes,
        compiled_problem_ref: str | None,
    ) -> dict[str, Any]:
        """Validate a source-issued complete request and select its declared response."""
        from polisyos.scientist.orchestration.llm._n4_request import _read_payload

        context = _read_payload(request)
        if compiled_problem_ref is None or context["subject_ref"] != compiled_problem_ref:
            raise ValueError("synthetic_provider_compiled_problem_not_bound")
        if request.get("model") != self.model_id:
            raise ValueError("synthetic_provider_model_mismatch")
        encoded = dict(self.response_rows).get(context["stage"])
        if encoded is None:
            raise ValueError("synthetic_provider_stage_unavailable")
        row = json.loads(encoded)
        completion = {
            "id": "synthetic-n4-" + context["context_id"],
            "object": "chat.completion",
            "model": self.model_id,
            "provider": "controlled_synthetic_stage_provider",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": row["raw_response"]},
                    "finish_reason": "stop",
                }
            ],
            "usage": dict(row["usage"]),
        }
        exchange = self.evidence_root / uuid4().hex
        exchange.mkdir(parents=True, exist_ok=False)
        response_bytes = json.dumps(completion, sort_keys=True).encode()
        for name, data in (("request.json.gz", raw_request), ("response.json.gz", response_bytes)):
            with (
                (exchange / name).open("xb") as stream,
                gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed,
            ):
                compressed.write(data)
        receipt = {
            "profile": self.descriptor(),
            "source_response": {
                "parent_role": row["parent_role"],
                "parent_response_hash": row["parent_response_hash"],
                "controlled_response_hash": row["raw_response_hash"],
                "source_model_id": row["source_model_id"],
            },
            "producer_context": context,
            "request_bytes_sha256": hashlib.sha256(raw_request).hexdigest(),
            "serialized_response_bytes_sha256": hashlib.sha256(response_bytes).hexdigest(),
            "delivery": "serialized before send; actual receipt/settlement is a separate consumer",
        }
        with (exchange / "receipt.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
        return completion


class ControlledCandidateGateway:
    """Small OpenAI-compatible local gateway for the real traced-client factory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recording: dict[str, object] | None = None
        self._problem: dict[str, object] | None = None
        self._n4_cursor = 0
        self._provider_profile: SyntheticCandidateProviderProfile | None = None
        self._compiled_problem_ref: str | None = None

        class Handler(BaseHTTPRequestHandler):
            owner: ControlledCandidateGateway

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/v1/models":
                    self._send_json(404, {"error": "not_found"})
                    return
                with self.owner._lock:
                    recording = self.owner._recording
                if recording is None:
                    self._send_json(503, {"error": "fixture_not_selected"})
                    return
                with self.owner._lock:
                    self.owner._n4_cursor = 0
                self._send_json(
                    200,
                    {"data": [{"id": recording["model_id"], "object": "model"}]},
                )

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/v1/chat/completions":
                    self._send_json(404, {"error": "not_found"})
                    return
                try:
                    raw_request = self.rfile.read(int(self.headers["Content-Length"]))
                    request = json.loads(raw_request)
                except KeyError, TypeError, ValueError, json.JSONDecodeError:
                    self._send_json(400, {"error": "malformed_request"})
                    return
                if not isinstance(request, dict):
                    self._send_json(400, {"error": "malformed_request"})
                    return
                compiler_name = self._compiler_tool_name(request)
                if compiler_name is not None:
                    with self.owner._lock:
                        problem = self.owner._problem
                        self.owner._n4_cursor = 0
                    if problem is None:
                        self._send_json(503, {"error": "fixture_not_selected"})
                        return
                    completion = {
                        "id": "synthetic-design-problem-completion",
                        "object": "chat.completion",
                        "model": request.get("model"),
                        "provider": "controlled_local_gateway",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "synthetic-design-problem-tool-call",
                                            "type": "function",
                                            "function": {
                                                "name": compiler_name,
                                                "arguments": json.dumps(
                                                    problem,
                                                    sort_keys=True,
                                                    separators=(",", ":"),
                                                ),
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }
                    self._send_json(200, completion)
                    return

                with self.owner._lock:
                    profile = self.owner._provider_profile
                    compiled_problem_ref = self.owner._compiled_problem_ref
                if profile is not None:
                    try:
                        completion = profile.completion(
                            request,
                            raw_request=raw_request,
                            compiled_problem_ref=compiled_problem_ref,
                        )
                    except (TypeError, ValueError) as exc:
                        self._send_json(
                            409, {"error": {"type": type(exc).__name__, "message": str(exc)}}
                        )
                        return
                    self._send_json(200, completion)
                    return

                with self.owner._lock:
                    recording = self.owner._recording
                    if recording is None:
                        response = None
                    else:
                        responses = recording.get("responses")
                        if not isinstance(responses, list) or self.owner._n4_cursor >= len(
                            responses
                        ):
                            response = None
                        else:
                            response = responses[self.owner._n4_cursor]
                            self.owner._n4_cursor += 1
                if not isinstance(response, dict):
                    self._send_json(502, {"error": "synthetic_response_exhausted"})
                    return
                if response.get("status") == "error":
                    error = response.get("error")
                    error_payload = error if isinstance(error, dict) else {}
                    self._send_json(
                        502,
                        {
                            "error": {
                                "type": error_payload.get("type") or "synthetic_gateway_error",
                                "code": error_payload.get("code"),
                                "message": error_payload.get("message")
                                or "controlled fixture provider error",
                            }
                        },
                    )
                    return
                content = response.get("raw_response")
                if not isinstance(content, str):
                    self._send_json(502, {"error": "synthetic_response_malformed"})
                    return
                completion = {
                    "id": "synthetic-candidate-completion",
                    "object": "chat.completion",
                    "model": request.get("model"),
                    "provider": "controlled_recorded_response",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                }
                if "usage" in response:
                    completion["usage"] = _recorded_usage_payload(response["usage"])
                self._send_json(200, completion)

            @staticmethod
            def _compiler_tool_name(request: dict[str, object]) -> str | None:
                tools = request.get("tools")
                if not isinstance(tools, list):
                    return None
                for tool in tools:
                    if not isinstance(tool, dict):
                        continue
                    function = tool.get("function")
                    if not isinstance(function, dict):
                        continue
                    name = function.get("name")
                    if name == "emit_design_problem":
                        return name
                return None

            def _send_json(self, status: int, payload: object) -> None:
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *args: object) -> None:
                del args

        Handler.owner = self
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """Return this test server's ephemeral OpenAI-compatible API root."""
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    def environment(self) -> dict[str, str]:
        """Return explicit local-only fixture configuration, never real credentials."""
        return {
            "POLISYOS_LLM_SIMULATION_MODE": "0",
            "POLISYOS_LLM_GATEWAY_BASE_URL": self.base_url,
            "POLISYOS_LLM_GATEWAY_API_KEY": "sk-synthetic-local-fixture-key",
            "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "0",
            "POLISYOS_LLM_FALLBACK_URLS": "",
        }

    def __enter__(self) -> ControlledCandidateGateway:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def set_fixture(
        self,
        recording: dict[str, object],
        *,
        problem: object,
        provider_profile: SyntheticCandidateProviderProfile | None = None,
    ) -> None:
        """Select a historical replay or explicit synthetic provider profile."""
        self._validate_recording(recording)
        if (
            provider_profile is not None
            and type(provider_profile) is not SyntheticCandidateProviderProfile
        ):
            raise TypeError("synthetic_provider_profile_untyped")
        model_dump = getattr(problem, "model_dump", None)
        if not callable(model_dump):
            raise TypeError("controlled_gateway_problem_untyped")
        problem_payload = model_dump(mode="json")
        if not isinstance(problem_payload, dict):
            raise TypeError("controlled_gateway_problem_untyped")
        with self._lock:
            self._recording = copy.deepcopy(recording)
            self._problem = copy.deepcopy(problem_payload)
            self._n4_cursor = 0
            self._provider_profile = provider_profile
            self._compiled_problem_ref = None

    def admit_compiled_problem(self, problem: object) -> None:
        """Bind the actual validated compiler product before profiled N4 calls."""
        from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

        with self._lock:
            profile = self._provider_profile
            if profile is None:
                return
            if type(problem) is not DesignProblem:
                raise TypeError("synthetic_provider_compiler_product_untyped")
            if cycle_job_profile_selection_ref(problem) != profile.profile_selection_ref:
                raise ValueError("synthetic_provider_compiler_semantic_scope_mismatch")
            if self._problem is None or (
                problem.nl_provenance.raw_request != self._problem["nl_provenance"]["raw_request"]
            ):
                raise ValueError("synthetic_provider_compiler_request_mismatch")
            self._compiled_problem_ref = gy_content_hash(problem.model_dump(mode="json"))

    @staticmethod
    def _validate_recording(recording: dict[str, object]) -> None:
        n4_contract._validate_recording_fixture(recording)  # type: ignore[arg-type]


def synthetic_controlled_candidate_provider_profile(
    recording: dict[str, Any],
    controlled: dict[str, Any],
    *,
    problem: DesignProblem,
    evidence_root: Path,
) -> SyntheticCandidateProviderProfile:
    """Declare new stage inputs from the exact controlled capture's parent rows.

    The selected successful bodies remain candidate software fixtures. Token
    magnitudes are explicitly new synthetic quantities, not recovered historical
    usage or billing; the normal traced client computes the current estimate.
    """
    n4_contract._validate_recording_fixture(recording)
    n4_contract._validate_recording_fixture(controlled)
    if (
        controlled.get("derived_from_recording_id") != recording["recording_id"]
        or controlled.get("derived_from_content_hash") != recording["recording_content_hash"]
        or len(controlled["responses"]) != len(recording["responses"])
    ):
        raise ValueError("synthetic_provider_controlled_parent_mismatch")
    # Exact row occurrences in the retained decisive capture, including the
    # successful final formalizer. Consolidation deliberately reuses draft as a
    # declared stage function; this is not a historical call-order replay.
    stage_rows = (
        ("draft", 0, "draft"),
        ("drafter_multipass", 1, "drafter_multipass"),
        ("drafter_consolidation", 0, "draft"),
        ("formalizer", 8, "formalizer"),
        ("critic", 9, "critic"),
    )
    rows = []
    for stage, index, parent_role in stage_rows:
        source = recording["responses"][index]
        selected = controlled["responses"][index]
        if (
            source.get("role") != parent_role
            or selected.get("role") != parent_role
            or source.get("status") != "success"
            or selected.get("status") != "success"
            or source.get("model_id") != recording["model_id"]
            or selected.get("model_id") != recording["model_id"]
        ):
            raise ValueError("synthetic_provider_parent_response_identity_unresolved")
        quantity = _usage_quantity(source.get("usage"))
        if quantity.status != "known":
            raise ValueError("synthetic_provider_explicit_usage_values_invalid")
        row = {
            "status": "success",
            "source_model_id": recording["model_id"],
            "raw_response": selected["raw_response"],
            "raw_response_hash": selected["raw_response_hash"],
            "usage": {
                "prompt_tokens": quantity.prompt_tokens,
                "completion_tokens": quantity.completion_tokens,
                "total_tokens": quantity.total_tokens,
                "usage_status": "known",
            },
            "legacy_counter_availability": "not_established",
            "usage_declaration": "new_synthetic_test_input_not_provider_measurement",
            "parent_role": parent_role,
            "parent_response_hash": source["raw_response_hash"],
        }
        rows.append((stage, json.dumps(row, sort_keys=True, separators=(",", ":"))))
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

    return SyntheticCandidateProviderProfile(
        model_id=str(recording["model_id"]),
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_recording_id=str(recording["recording_id"]),
        source_recording_content_hash=str(recording["recording_content_hash"]),
        controlled_recording_content_hash=str(controlled["recording_content_hash"]),
        response_rows=tuple(rows),
        evidence_root=evidence_root,
    )


def _resolve_controlled_parent_slot(slot_id: str) -> str:
    """Resolve a test-parent alias using the existing controlled slot map."""

    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY

    canonical_id = _CONTROLLED_SLOT_ALIASES.get(slot_id, slot_id)
    if canonical_id not in DEFAULT_SLOT_REGISTRY.slots:
        raise ValueError("controlled_n4_parent_slot_alias_not_established:" + slot_id)
    return canonical_id


def _current_compiler_problem(recording: dict[str, object]):
    """Build a controlled current-schema parent without rewriting replay bytes.

    The selected recording supplies response bytes only; its historical problem
    scope remains unestablished and is never reused as the controlled parent identity.
    All callers receive this test fixture parent rather than an implied historical
    parent scope.
    """

    reconstructed = n4_contract._design_problem(recording)
    source_text = "all proposals remain candidate-only"
    assert source_text in reconstructed.nl_provenance.raw_request
    constraints = [
        constraint.model_copy(
            update={
                "description": "All proposals remain candidate-only.",
                "source_text": source_text,
            }
        )
        if constraint.constraint_id == "no_authority_without_a"
        else constraint
        for constraint in reconstructed.constraints
    ]
    problem = reconstructed.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
            "constraints": constraints,
        }
    )
    # Controlled current-schema parents pass the complete owner validator;
    # fixture adapters must not rely on model_copy to establish validity.
    problem = DesignProblem.model_validate(problem.model_dump(mode="python"))
    recording_id = recording.get("recording_id")
    content_hash = recording.get("recording_content_hash")
    if not isinstance(recording_id, str) or not recording_id:
        raise ValueError("controlled_n4_parent_source_recording_id_missing")
    if not isinstance(content_hash, str) or not content_hash:
        raise ValueError("controlled_n4_parent_source_recording_hash_missing")

    source_levers = tuple(problem.candidate_lever_space.candidate_levers)
    resolved_levers = []
    lever_slot_resolutions: list[dict[str, str]] = []
    for lever in source_levers:
        canonical_slot = _resolve_controlled_parent_slot(lever.target_slot)
        resolved_levers.append(lever.model_copy(update={"target_slot": canonical_slot}))
        lever_slot_resolutions.append(
            {
                "lever_id": lever.lever_id,
                "operator_kind": lever.operator_kind,
                "instrument": lever.instrument,
                "source_target_slot": lever.target_slot,
                "resolved_target_slot": canonical_slot,
            }
        )
    if len(resolved_levers) != len(source_levers) or not resolved_levers:
        raise ValueError("controlled_n4_parent_lever_set_incomplete")

    scope_ref = gy_content_hash(
        {
            "schema_version": "controlled_n4_parent_scope_v1",
            "source_recording_id": recording_id,
            "source_recording_content_hash": content_hash,
            "reconstructed_problem": problem.model_dump(mode="json"),
            "allowed_operator_kinds": list(problem.candidate_lever_space.allowed_operator_kinds),
            "resolved_candidate_levers": [
                lever.model_dump(mode="json") for lever in resolved_levers
            ],
            "lever_slot_resolutions": lever_slot_resolutions,
        }
    )
    controlled_problem_id = "controlled_n4_parent_" + scope_ref.removeprefix("sha256:")[:24]
    scope_declaration = {
        "purpose": "controlled_test_fixture_only",
        "scope_status": "declared_controlled_fixture",
        "historical_scope_status": "not_established",
        "source_recording_id": recording_id,
        "source_recording_content_hash": content_hash,
        "reconstructed_problem_id": problem.design_problem_id,
        "parent_problem_id": controlled_problem_id,
        "parent_scope_ref": scope_ref,
        "lever_slot_resolutions": lever_slot_resolutions,
    }
    return problem.model_copy(
        update={
            "design_problem_id": controlled_problem_id,
            "candidate_lever_space": problem.candidate_lever_space.model_copy(
                update={"candidate_levers": resolved_levers}
            ),
            "runtime_hints": {
                **problem.runtime_hints,
                "n4_controlled_parent_scope": scope_declaration,
            },
        }
    )


def _controlled_registered_tax_recording(
    recording: dict[str, object], *, outcome_variable: str, rate: int = 0
) -> dict[str, object]:
    """Build a test-only tax action in the registered global slot and legal range.

    The source capture remains immutable and is retained as the overlay's parent.
    Integer zero is both inside the registered 0..0.5 action range and accepted by
    the existing exact-set-to candidate profile; this creates no real-world claim.
    """

    if type(rate) is not int or rate != 0:
        raise ValueError("controlled_registered_tax_rate_test_value_unsupported")
    controlled = copy.deepcopy(recording)
    base_recording_id = str(controlled.get("recording_id") or "recording")
    base_content_hash = str(controlled.get("recording_content_hash") or "")
    responses = controlled.get("responses")
    assert isinstance(responses, list)
    for index in (4, 8):
        response = responses[index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        trinity = json.loads(raw)
        interventions = trinity["policy_spec"]["interventions"]
        tax_action = next(item for item in interventions if item.get("kind") == "tax_relief_rate")
        tax_action["params"] = {"rate": rate}
        tax_action["notes"] = [
            "do.target=global.tax_rate sign=decrease "
            f"outcome={outcome_variable} "
            f"effect_path=global.tax_rate,{outcome_variable}"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)

    identity_seed = gy_content_hash(
        {
            "base_recording_id": base_recording_id,
            "base_content_hash": base_content_hash,
            "response_hashes": [
                item.get("raw_response_hash") for item in responses if isinstance(item, dict)
            ],
            "outcome_variable": outcome_variable,
            "rate": rate,
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_controlled_registered_tax_n4_{identity_seed}"
    controlled["fixture_id"] = fixture_id
    controlled["recording_id"] = fixture_id
    controlled["recording_source"] = "synthetic_controlled_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = base_recording_id
    controlled["derived_from_content_hash"] = base_content_hash
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)
    return controlled


def _controlled_procurement_recording(
    recording: dict[str, object], *, outcome_variable: str, intensity: int = 1
) -> dict[str, object]:
    """Return a new synthetic fixture identity for a controlled N4 replay overlay."""

    from polisyos.pdc import gy_content_hash

    controlled = copy.deepcopy(recording)
    base_recording_id = str(controlled.get("recording_id") or "recording")
    base_content_hash = str(controlled.get("recording_content_hash") or "")
    responses = controlled.get("responses")
    assert isinstance(responses, list)
    for index in (4, 8):
        response = responses[index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        trinity = json.loads(raw)
        interventions = trinity["policy_spec"]["interventions"]
        procurement = next(
            item for item in interventions if item.get("kind") == "procurement_shock_intensity"
        )
        procurement["params"] = {"intensity": intensity}
        procurement["notes"] = [
            "do.target=cells.distress_score sign=decrease "
            f"outcome={outcome_variable} "
            f"effect_path=cells.distress_score,{outcome_variable}"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)

    # Edited provider bytes are a synthetic test fixture, not the historical
    # provider capture. Give the overlay an identity derived from its changed
    # bytes and retain an explicit lineage pointer to the immutable source.
    identity_seed = gy_content_hash(
        {
            "base_recording_id": base_recording_id,
            "base_content_hash": base_content_hash,
            "response_hashes": [
                item.get("raw_response_hash") for item in responses if isinstance(item, dict)
            ],
            "outcome_variable": outcome_variable,
            "intensity": intensity,
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_controlled_n4_{identity_seed}"
    controlled["fixture_id"] = fixture_id
    controlled["recording_id"] = fixture_id
    controlled["recording_source"] = "synthetic_controlled_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = base_recording_id
    controlled["derived_from_content_hash"] = base_content_hash

    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)
    return controlled


_CONTROLLED_SLOT_ALIASES = {
    "agents_income": "agents.income",
    "agents_is_employed": "agents.is_employed",
    "cells_distress_score": "cells.distress_score",
    "employment_retention": "cells.employment",
    "employment_retention_rate": "cells.employment",
    "global_tax_rate": "global.tax_rate",
    "government_balance": "government.balance",
}


def _controlled_direct_ncm_outcome_state_paths(outcome_variable: str) -> dict[str, str]:
    """Name an explicit toy path only when the selected outcome has no registered path."""
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY

    canonical_id = _CONTROLLED_SLOT_ALIASES.get(outcome_variable, outcome_variable)
    if canonical_id in DEFAULT_SLOT_REGISTRY.slots:
        return {}
    return {outcome_variable: "market.total_supply"}


def _controlled_ncm_outcome_baseline_is_compatible(baseline: object, value_type: object) -> bool:
    """Check scalar baselines without conflating booleans and numbers."""
    value_type_name = getattr(value_type, "value", value_type)
    if value_type_name == "bool":
        return isinstance(baseline, bool)
    if value_type_name == "int":
        if isinstance(baseline, bool) or not isinstance(baseline, int):
            return False
    elif value_type_name == "decimal":
        if isinstance(baseline, bool) or not isinstance(baseline, (int, float, Decimal)):
            return False
    else:
        return False
    try:
        return math.isfinite(float(baseline))
    except (OverflowError, TypeError, ValueError):
        return False


def _controlled_ncm_outcome_payload_value(
    *,
    payload: Mapping[str, object],
    slot_spec: SlotSpec,
    baseline: object,
) -> object:
    """Materialize a scalar fixture baseline only on its registered state axis.

    The selected slot's owner-derived family must agree with its declared scope.
    Global outcomes remain scalar. A scoped outcome can use a scalar NCM
    baseline only when the exact registered state path already carries a
    singleton entity axis in the fixture seed. This is a candidate-only
    representation rule, not aggregation or broadcast semantics.
    """
    from polisyos.ir.kernel import SlotRegistry
    from polisyos.ir.kernel.slots import build_slot_family_manifest

    state_path = slot_spec.state_path
    if not isinstance(state_path, str) or not state_path.strip():
        raise ValueError("controlled_wmr_ncm_outcome_state_path_not_declared")
    parts = state_path.split(".")
    if any(not part for part in parts):
        raise ValueError("controlled_wmr_ncm_outcome_state_path_invalid")
    registry = SlotRegistry(slots={slot_spec.slot_id: slot_spec})
    family_manifest = build_slot_family_manifest(registry)
    (family,) = family_manifest.families.values()
    scope_name = getattr(slot_spec.scope, "value", slot_spec.scope)
    family_scope_name = getattr(family.scope, "value", family.scope)
    if family.scope != slot_spec.scope:
        raise ValueError(
            "controlled_wmr_ncm_outcome_scope_state_path_mismatch:"
            f"{scope_name}:{family_scope_name}:{state_path}"
        )

    current: object = payload
    missing = object()
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            current = missing
            break
        current = current[part]
    if scope_name == "global":
        if current is not missing and isinstance(current, (list, tuple)):
            raise ValueError(
                "controlled_wmr_ncm_outcome_global_scope_entity_axis_mismatch:" + state_path
            )
        return baseline
    if current is missing or not isinstance(current, (list, tuple)):
        raise ValueError("controlled_wmr_ncm_outcome_entity_axis_not_established:" + state_path)
    if len(current) != 1:
        raise ValueError(
            "controlled_wmr_ncm_outcome_entity_axis_cardinality_not_supported:"
            f"{state_path}:{len(current)}"
        )
    if isinstance(current, list):
        return [baseline]
    return (baseline,)


def _controlled_auto_binding_id(slot_id: str) -> str:
    """Mirror the data-plane auto-binding identifier for collision checks."""
    return f"auto.{slot_id.replace('.', '_')}"


def _controlled_resolve_policy_slot_ids(
    policy_slot_ids: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """Preserve each requested identity and reject ambiguous fixture aliases."""
    resolved: list[tuple[str, str]] = []
    by_binding_id: dict[str, str] = {}
    by_canonical_id: dict[str, str] = {}
    for slot_id in policy_slot_ids:
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ValueError("controlled_wmr_policy_slot_id_invalid")
        if any(selected_id == slot_id for selected_id, _ in resolved):
            continue
        canonical_id = _CONTROLLED_SLOT_ALIASES.get(slot_id, slot_id)
        binding_id = _controlled_auto_binding_id(slot_id)
        prior_binding_id = by_binding_id.get(binding_id)
        if prior_binding_id is not None and prior_binding_id != slot_id:
            raise ValueError(
                "controlled_wmr_auto_binding_identity_collision:"
                f"{prior_binding_id}:{slot_id}:{binding_id}"
            )
        prior_canonical_id = by_canonical_id.get(canonical_id)
        if prior_canonical_id is not None and prior_canonical_id != slot_id:
            raise ValueError(
                "controlled_wmr_selected_slot_alias_collision:"
                f"{prior_canonical_id}:{slot_id}:{canonical_id}"
            )
        by_binding_id[binding_id] = slot_id
        by_canonical_id[canonical_id] = slot_id
        resolved.append((slot_id, canonical_id))
    return tuple(resolved)


def _controlled_selected_slot_specs(
    *,
    policy_slot_ids: Sequence[str],
    declared_ncm_outcomes: frozenset[str],
    candidate_baseline_state: Mapping[str, object] | None,
    candidate_outcome_state_paths: Mapping[str, str] | None,
) -> dict[str, Any]:
    """Build a selected-only registry from requested slots and a persisted NCM."""
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY, SlotSpec, UnitRef

    resolved = _controlled_resolve_policy_slot_ids(policy_slot_ids)
    if not resolved:
        raise ValueError("controlled_wmr_policy_slots_missing")
    if candidate_baseline_state is not None and not isinstance(candidate_baseline_state, Mapping):
        raise ValueError("controlled_wmr_candidate_baseline_state_invalid")
    if candidate_outcome_state_paths is not None and not isinstance(
        candidate_outcome_state_paths, Mapping
    ):
        raise ValueError("controlled_wmr_candidate_outcome_state_paths_invalid")
    state_paths = dict(candidate_outcome_state_paths or {})
    requested_ids = {slot_id for slot_id, _ in resolved}
    if set(state_paths) - requested_ids:
        raise ValueError("controlled_wmr_unselected_candidate_outcome_state_path")

    specs: dict[str, Any] = {}
    selected_state_paths: dict[str, str] = {}
    for slot_id, canonical_id in resolved:
        if canonical_id in DEFAULT_SLOT_REGISTRY.slots:
            canonical_slot = DEFAULT_SLOT_REGISTRY.slots[canonical_id]
            slot_spec = canonical_slot.model_copy(update={"slot_id": slot_id})
            if slot_id in declared_ncm_outcomes:
                value_type_name = getattr(
                    canonical_slot.value_type, "value", canonical_slot.value_type
                )
                if value_type_name not in {"bool", "int", "decimal"}:
                    raise ValueError(
                        "controlled_wmr_ncm_outcome_value_type_not_supported:" + slot_id
                    )
                baseline = (candidate_baseline_state or {}).get(slot_id)
                if not _controlled_ncm_outcome_baseline_is_compatible(
                    baseline, canonical_slot.value_type
                ):
                    raise ValueError(
                        "controlled_wmr_ncm_outcome_baseline_not_established:" + slot_id
                    )
                if not isinstance(slot_spec.state_path, str) or not slot_spec.state_path.strip():
                    raise ValueError(
                        "controlled_wmr_ncm_outcome_state_path_not_declared:" + slot_id
                    )
                if slot_id in state_paths and state_paths[slot_id] != slot_spec.state_path:
                    raise ValueError(
                        "controlled_wmr_registered_ncm_outcome_state_path_mismatch:" + slot_id
                    )
            elif slot_id in state_paths:
                raise ValueError(
                    "controlled_wmr_candidate_outcome_state_path_not_ncm_output:" + slot_id
                )
        else:
            baseline = (candidate_baseline_state or {}).get(slot_id)
            state_path = state_paths.get(slot_id)
            if slot_id not in declared_ncm_outcomes:
                raise ValueError("controlled_wmr_ncm_outcome_not_declared:" + slot_id)
            if not _controlled_ncm_outcome_baseline_is_compatible(baseline, "decimal"):
                raise ValueError("controlled_wmr_ncm_outcome_baseline_not_established:" + slot_id)
            if not isinstance(state_path, str) or not state_path.strip():
                raise ValueError("controlled_wmr_ncm_outcome_state_path_not_declared:" + slot_id)
            template = DEFAULT_SLOT_REGISTRY.slots["global.tax_rate"]
            slot_spec = SlotSpec.model_validate(
                {
                    **template.model_dump(mode="python"),
                    "slot_id": slot_id,
                    "unit": UnitRef(unit_id="synthetic_score"),
                    "kind": "stock",
                    "state_path": state_path,
                    "description": (
                        "Explicit candidate-only toy outcome input from the selected persisted "
                        "NCM baseline; it carries no measurement or calibration claim."
                    ),
                    "reset_rule": "carry",
                }
            )
        if slot_spec.state_path is not None:
            prior_slot = selected_state_paths.get(slot_spec.state_path)
            if prior_slot is not None and prior_slot != slot_id:
                raise ValueError(
                    "controlled_wmr_selected_state_path_collision:"
                    f"{prior_slot}:{slot_id}:{slot_spec.state_path}"
                )
            selected_state_paths[slot_spec.state_path] = slot_id
        specs[slot_id] = slot_spec
    direct_outcome_ids = {
        slot_id
        for slot_id, canonical_id in resolved
        if canonical_id not in DEFAULT_SLOT_REGISTRY.slots
    }
    if not direct_outcome_ids.issubset(state_paths):
        raise ValueError("controlled_wmr_candidate_outcome_state_paths_mismatch")
    if set(specs) != requested_ids:
        raise ValueError("controlled_wmr_selected_slot_registry_incomplete")
    return specs


def _controlled_declared_ncm_outcomes(
    *,
    artifact_store: ArtifactStore,
    ncm_view_refs: Sequence[Any],
    tenant_id: str,
    cell_id: str,
) -> frozenset[str]:
    """Read selected NCM declarations from their exact owner-persisted CAS refs."""
    if not ncm_view_refs:
        return frozenset()
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import load_ncm_spec

    declared: set[str] = set()
    ir_store = _ensure_ir_artifact_store(artifact_store)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        for ref in ncm_view_refs:
            manifest = artifact_store.get_manifest(ref)
            if (
                getattr(manifest, "kind", None) != "ir.ncm_spec"
                or getattr(manifest, "media_type", None) != "application/json"
            ):
                raise ValueError("controlled_wmr_selected_ncm_ref_kind_mismatch")
            selected_ncm = load_ncm_spec(ir_store, ref)
            equation_variables = {
                equation.variable for equation in selected_ncm.structural_equations
            }
            declared.update(set(selected_ncm.endogenous_vars) & equation_variables)
    return frozenset(declared)


def _controlled_set_payload_path(
    payload: dict[str, Any], path: str, value: object, *, replace_existing: bool = False
) -> None:
    """Set one validated candidate path, optionally replacing its fixture baseline leaf."""
    parts = path.split(".")
    if any(not part for part in parts):
        raise ValueError("controlled_wmr_candidate_outcome_state_path_invalid")
    current = payload
    for part in parts[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise ValueError("controlled_wmr_candidate_outcome_state_path_conflict:" + path)
        current = child
    if parts[-1] in current and not replace_existing:
        raise ValueError("controlled_wmr_candidate_outcome_state_path_conflict:" + path)
    current[parts[-1]] = value


_CONTROLLED_SYNTHETIC_SKG_VERSION_ID = 1
_CONTROLLED_SYNTHETIC_SKG_VERSION_COUNT = 1


@dataclass(frozen=True)
class ControlledSKGSourceSelection:
    """Exact owner-resolved identity for one read-only controlled SKG source."""

    db_path: Path
    version_id: int
    snapshot_ref: str
    sha256: str
    schema_sha256: str


def _controlled_skg_source_observation(db_path: Path) -> tuple[int, str, str, str]:
    """Observe version, ref, bytes, and schema through read-only owner APIs."""
    import duckdb

    from polisyos.data_forge.read_api.academic import SKGQuery

    resolved_path = db_path.resolve()
    if not resolved_path.is_file():
        raise ValueError("controlled_selected_skg_source_missing")
    if resolved_path.with_name(resolved_path.name + ".wal").exists():
        raise ValueError("controlled_selected_skg_source_wal_unbound")
    before_stat = resolved_path.stat()
    before_identity = (
        before_stat.st_dev,
        before_stat.st_ino,
        before_stat.st_size,
        before_stat.st_mtime_ns,
    )
    before_sha256 = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    try:
        with duckdb.connect(str(resolved_path), read_only=True) as connection:
            schema_rows = tuple(
                (str(table), str(column), str(data_type))
                for table, column, data_type in connection.execute(
                    "SELECT table_name, column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_catalog=current_database() AND table_schema='main' "
                    "ORDER BY table_name, ordinal_position"
                ).fetchall()
            )
            versions = tuple(
                int(row[0])
                for row in connection.execute(
                    "SELECT version_id FROM main.ac_skg_versions ORDER BY version_id"
                ).fetchall()
            )
    except (duckdb.Error, OSError, TypeError, ValueError) as exc:
        raise ValueError("controlled_selected_skg_source_schema_unresolved") from exc
    required_columns = {
        ("ac_skg_edges", "edge_id"),
        ("ac_skg_edges", "src"),
        ("ac_skg_edges", "dst"),
        ("ac_skg_variables", "canonical_name"),
        ("ac_skg_versions", "version_id"),
    }
    if not required_columns.issubset({(table, column) for table, column, _ in schema_rows}):
        raise ValueError("controlled_selected_skg_source_schema_incomplete")
    if versions != (_CONTROLLED_SYNTHETIC_SKG_VERSION_ID,):
        raise ValueError("controlled_selected_skg_source_version_set_mismatch")
    query = SKGQuery(db_path=resolved_path, index_dir=resolved_path.parent / "index")
    try:
        version_id = query.latest_skg_version_id()
        if version_id is None or not query.has_skg_version_id(version_id=version_id):
            raise ValueError("controlled_selected_skg_source_version_unresolved")
        snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
    finally:
        query.close()
    if version_id != _CONTROLLED_SYNTHETIC_SKG_VERSION_ID or snapshot_ref is None:
        raise ValueError("controlled_selected_skg_source_version_unresolved")
    after_stat = resolved_path.stat()
    after_identity = (
        after_stat.st_dev,
        after_stat.st_ino,
        after_stat.st_size,
        after_stat.st_mtime_ns,
    )
    after_sha256 = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
    if before_identity != after_identity or before_sha256 != after_sha256:
        raise ValueError("controlled_selected_skg_source_changed_during_read")
    schema_sha256 = hashlib.sha256(
        json.dumps(schema_rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return version_id, snapshot_ref, before_sha256, schema_sha256


def _capture_controlled_skg_source(db_path: Path) -> ControlledSKGSourceSelection:
    """Bind the new controlled source only after its real reader resolves it."""
    version_id, snapshot_ref, sha256, schema_sha256 = _controlled_skg_source_observation(db_path)
    return ControlledSKGSourceSelection(
        db_path=db_path.resolve(),
        version_id=version_id,
        snapshot_ref=snapshot_ref,
        sha256=sha256,
        schema_sha256=schema_sha256,
    )


def _validate_controlled_skg_source(
    selected_source: ControlledSKGSourceSelection,
) -> ControlledSKGSourceSelection:
    """Refuse any changed, malformed, or differently versioned selected source."""
    from polisyos.runtime.quality.world_model_record import _parse_skg_snapshot_ref

    if type(selected_source) is not ControlledSKGSourceSelection:
        raise TypeError("controlled_selected_skg_source_untyped")
    parsed = _parse_skg_snapshot_ref(selected_source.snapshot_ref)
    if (
        parsed.db_path.resolve() != selected_source.db_path.resolve()
        or parsed.version_id != selected_source.version_id
    ):
        raise ValueError("controlled_selected_skg_source_ref_mismatch")
    version_id, snapshot_ref, sha256, schema_sha256 = _controlled_skg_source_observation(
        selected_source.db_path
    )
    if version_id != selected_source.version_id or snapshot_ref != selected_source.snapshot_ref:
        raise ValueError("controlled_selected_skg_source_version_mismatch")
    if schema_sha256 != selected_source.schema_sha256:
        raise ValueError("controlled_selected_skg_source_schema_mismatch")
    if sha256 != selected_source.sha256:
        raise ValueError("controlled_selected_skg_source_bytes_mismatch")
    return selected_source


def _persist_controlled_data_snapshot(
    *,
    artifact_store: ArtifactStore,
    payload_ref: Any,
    snapshot_id: str,
) -> Any:
    """Persist one controlled snapshot with its exact canonical source lineage."""
    from polisyos.core.artifacts import (
        CanonInfo,
        PutOptions,
        SchemaInfo,
        input_ref_from_artifact_ref,
    )
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts import DataSnapshot

    canon_spec = CanonSpec(forbid_floats=False)
    expected_canon = CanonInfo.from_spec(canon_spec)
    expected_schema = SchemaInfo(
        name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
    )
    payload_input = input_ref_from_artifact_ref(payload_ref, role="data_ref")
    payload_profile = getattr(payload_ref, "manifest_profile_sha256", None)
    if type(payload_profile) is not str or not payload_profile.startswith("sha256:"):
        raise ValueError("controlled_data_snapshot_payload_profile_missing")

    snapshot = DataSnapshot(
        data_ref=payload_ref,
        stats={"snapshot_id": snapshot_id},
        notes=["snapshot_id:" + snapshot_id, "controlled_candidate_only"],
    )
    selected_ref = artifact_store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=expected_schema,
            inputs=[payload_input],
            canon=expected_canon,
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    selected_profile = getattr(selected_ref, "manifest_profile_sha256", None)
    if type(selected_profile) is not str or not selected_profile.startswith("sha256:"):
        raise ValueError("controlled_data_snapshot_selected_profile_missing")
    _read_controlled_data_snapshot_source(
        artifact_store=artifact_store,
        snapshot_ref=selected_ref,
        payload_ref=payload_ref,
        expected_canon=expected_canon,
        expected_schema=expected_schema,
    )
    return selected_ref


def _read_controlled_data_snapshot_source(
    *,
    artifact_store: ArtifactStore,
    snapshot_ref: Any,
    payload_ref: Any,
    expected_canon: Any | None = None,
    expected_schema: Any | None = None,
) -> Any:
    """Read one exact typed snapshot view and verify its selected manifest inputs."""
    from polisyos.core.artifacts import (
        CanonInfo,
        SchemaInfo,
        input_ref_from_artifact_ref,
        load_core_json_artifact,
    )
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts import DataSnapshot

    selected_profile = getattr(snapshot_ref, "manifest_profile_sha256", None)
    if type(selected_profile) is not str or not selected_profile.startswith("sha256:"):
        raise ValueError("controlled_data_snapshot_selected_profile_missing")

    canon = expected_canon or CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    schema = expected_schema or SchemaInfo(
        name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
    )
    value = DataSnapshot.model_validate(load_core_json_artifact(artifact_store, snapshot_ref))
    manifest = artifact_store.get_manifest(snapshot_ref)
    if manifest.canon != canon:
        raise ValueError("controlled_data_snapshot_canon_profile_mismatch")
    if manifest.artifact_schema != schema:
        raise ValueError("controlled_data_snapshot_schema_mismatch")
    expected_input = input_ref_from_artifact_ref(payload_ref, role="data_ref")
    if manifest.inputs != [expected_input]:
        raise ValueError("controlled_data_snapshot_input_binding_mismatch")

    observed_payload_ref = (
        str(value.data_ref.artifact_id),
        value.data_ref.kind,
        value.data_ref.media_type,
        value.data_ref.manifest_profile_sha256,
    )
    expected_payload_ref = (
        str(payload_ref.artifact_id),
        payload_ref.kind,
        payload_ref.media_type,
        payload_ref.manifest_profile_sha256,
    )
    if observed_payload_ref != expected_payload_ref:
        raise ValueError("controlled_data_snapshot_payload_view_mismatch")
    return value


def _materialize_controlled_world_model_build(
    *,
    source_world_model_record: Any,
    artifact_store: ArtifactStore,
    tmp_path: Path,
    source_root: Path | None = None,
    substrate_registry: Any,
    selected_registry_entry_hashes: Sequence[str],
    substrate_registry_ref: Any,
    policy_slot_ids: Sequence[str],
    selected_skg_source: ControlledSKGSourceSelection,
    tenant_id: str,
    cell_id: str,
    ncm_view_refs: Sequence[Any] = (),
    candidate_baseline_state: Mapping[str, object] | None = None,
    candidate_outcome_state_paths: Mapping[str, str] | None = None,
) -> Any:
    """Build a source-bound, limited WMR from real local owner artifacts.

    The synthetic fixture aliases its explicit controlled variables onto existing
    canonical runtime paths. It never represents an empirical or live source.
    """
    admitted_source_root = (
        Path(source_root).resolve()
        if source_root is not None
        else tmp_path / "controlled-candidate-source"
    )
    expected_skg_path = admitted_source_root / "academic-skg.duckdb"
    if selected_skg_source.db_path.resolve() != expected_skg_path.resolve():
        raise ValueError("controlled_selected_skg_source_path_mismatch")
    _validate_controlled_skg_source(selected_skg_source)

    from polisyos.core.artifacts import ArtifactRef, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
    from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
    from polisyos.data_forge.kernel.snapshot import finalize_snapshot
    from polisyos.fabric.world import (
        WorldSnapshotFactWrite,
        WorldSnapshotNodeWrite,
        WorldSnapshotWriteRequest,
        write_world_snapshot,
    )
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_METRIC_REGISTRY,
        DEFAULT_SELECTOR_FIELD_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
        GenericUnit,
        SlotRegistry,
        UnitsRegistry,
    )
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.pdc import WorldModelLimitations
    from polisyos.runtime.quality.substrate_registry import SubstrateRegistry
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        FabricWorldRef,
        SkgCausalPriorRef,
        build_world_model_record,
        load_world_model_record,
    )

    if not selected_registry_entry_hashes:
        raise ValueError("controlled_wmr_selected_registry_entries_missing")
    registry = SubstrateRegistry.model_validate(substrate_registry.model_dump(mode="json"))
    selected_hashes = tuple(dict.fromkeys(str(item) for item in selected_registry_entry_hashes))
    selected_entries = tuple(
        entry for entry in registry.entries if entry.entry_content_hash in selected_hashes
    )
    if {entry.entry_content_hash for entry in selected_entries} != set(selected_hashes):
        raise ValueError("controlled_wmr_selected_registry_entry_unresolved")
    supplied_registry_ref = ArtifactRef.model_validate(
        substrate_registry_ref.model_dump(mode="python")
    )

    declared_ncm_outcomes = _controlled_declared_ncm_outcomes(
        artifact_store=artifact_store,
        ncm_view_refs=ncm_view_refs,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    controlled_slot_specs = _controlled_selected_slot_specs(
        policy_slot_ids=policy_slot_ids,
        declared_ncm_outcomes=declared_ncm_outcomes,
        candidate_baseline_state=candidate_baseline_state,
        candidate_outcome_state_paths=candidate_outcome_state_paths,
    )
    controlled_slot_registry = SlotRegistry.model_validate(
        {
            "schema_version": DEFAULT_SLOT_REGISTRY.schema_version,
            "slots": controlled_slot_specs,
            "notes": [
                "Selected fixture slots derive from the requested policy plus owner-read NCM refs; "
                "all are candidate-only and carry no empirical or authority claim.",
            ],
        }
    )
    controlled_unit_registry = UnitsRegistry.model_validate(
        {
            **DEFAULT_UNITS_REGISTRY.model_dump(mode="python"),
            "units": {
                **DEFAULT_UNITS_REGISTRY.units,
                "synthetic_score": GenericUnit(
                    label="controlled candidate-fixture value",
                    description=(
                        "Candidate-only fixture unit; physical measurement semantics "
                        "are not established."
                    ),
                ),
            },
            "notes": [
                *DEFAULT_UNITS_REGISTRY.notes,
                "synthetic_score is limited to controlled candidate fixtures.",
            ],
        }
    )

    # The admitted SKG is read-only input; generated artifacts retain their
    # independent fixture output owner, including when source_root is explicit.
    output_root = tmp_path / "controlled-candidate-source"
    snapshot_id = "controlled-candidate-source-v1"
    fabric_root = output_root / "fabric-world"
    fabric_db = output_root / "fabric-world.duckdb"
    data_forge_root = output_root / "data-forge" / snapshot_id
    academic_artifact = data_forge_root / "academic" / "academic.jsonl"
    academic_artifact.parent.mkdir(parents=True, exist_ok=True)
    academic_artifact.write_text(
        '{"snapshot_id":"' + snapshot_id + '"}\n',
        encoding="utf-8",
    )
    write_publish_manifest(
        manifest_path=data_forge_root / "academic" / "publish" / "manifest.json",
        pipeline="academic",
        artifacts=(academic_artifact,),
        published_at="2026-05-24T08:30:00+00:00",
        extra={
            "corpus_id": "controlled-candidate-source",
            "builder_revision": "fixture:controlled-candidate-source-v1",
            "lineage_refs": ["fixture://controlled-candidate-source"],
        },
    )
    finalize_snapshot(
        data_forge_root,
        update_latest_symlink=False,
        pipelines=("academic",),
    )

    visible_time = "2026-05-24T00:00:00+00:00"
    transaction_time = "2026-05-24T12:00:00+00:00"
    node_id = "world.controlled.candidate-fixture"
    write_world_snapshot(
        fabric_db,
        WorldSnapshotWriteRequest(
            snapshot_root=fabric_root,
            snapshot_id=snapshot_id,
            branch_name="main",
            as_of_valid_time=visible_time,
            as_of_tx_time=transaction_time,
            provenance={"source": "controlled_candidate_fixture"},
            nodes=(
                WorldSnapshotNodeWrite(
                    node_id=node_id,
                    kind="claim",
                    label="Controlled candidate fixture",
                    artifact_id=None,
                    props_ref=None,
                ),
            ),
            facts=(
                WorldSnapshotFactWrite(
                    fact_id=f"fact:{snapshot_id}:controlled-candidate",
                    schema_version="1.0",
                    subject_id=node_id,
                    predicate_id="world.kind",
                    object_value="claim",
                    target_id=None,
                    valid_time=visible_time,
                    tx_time=transaction_time,
                    provenance_json={"source": "controlled_candidate_fixture"},
                    trust_json=None,
                    legal_json=None,
                    segment_id=f"seg:{snapshot_id}:controlled-candidate",
                ),
            ),
        ),
    )

    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        canon_spec = CanonSpec(forbid_floats=False)
        payload = {
            "agents": {
                "income": [1200.0],
                "is_employed": [True],
            },
            "cells": {
                "distress_score": [0.0],
                "employment": [1.0],
            },
            "government_balance": 0.0,
            "tax_rate": 0.0,
        }
        for slot_id, slot_spec in controlled_slot_specs.items():
            if slot_id not in declared_ncm_outcomes:
                continue
            baseline = (candidate_baseline_state or {}).get(slot_id)
            if baseline is None:
                raise ValueError("controlled_wmr_candidate_outcome_input_unbound:" + slot_id)
            if not isinstance(slot_spec.state_path, str) or not slot_spec.state_path.strip():
                raise ValueError("controlled_wmr_candidate_outcome_input_unbound:" + slot_id)
            canonical_id = _CONTROLLED_SLOT_ALIASES.get(slot_id, slot_id)
            canonical_slot = DEFAULT_SLOT_REGISTRY.slots.get(canonical_id)
            registered_path = canonical_slot.state_path if canonical_slot is not None else None
            payload_baseline = _controlled_ncm_outcome_payload_value(
                payload=payload,
                slot_spec=slot_spec,
                baseline=baseline,
            )
            _controlled_set_payload_path(
                payload,
                slot_spec.state_path,
                payload_baseline,
                replace_existing=(registered_path == slot_spec.state_path),
            )
        payload_ref = artifact_store.put_json(
            payload,
            PutOptions(kind="fabric.world_payload", media_type="application/json"),
            canon_spec=canon_spec,
            return_selected_profile=True,
        )
        data_snapshot_ref = _persist_controlled_data_snapshot(
            artifact_store=artifact_store,
            payload_ref=payload_ref,
            snapshot_id=snapshot_id,
        )
        registry_bundle = build_registry_bundle(
            artifact_store,
            slot_registry=controlled_slot_registry,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
            selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
            metric_registry=DEFAULT_METRIC_REGISTRY,
            units_registry=controlled_unit_registry,
        )
        persisted_registry = load_registry_bundle_content(
            artifact_store,
            registry_bundle.bundle_ref,
        )
        if (
            persisted_registry.slot_registry != controlled_slot_registry
            or persisted_registry.units_registry != controlled_unit_registry
        ):
            raise ValueError("controlled_wmr_registry_readback_mismatch")

    model_spec = ModelSpec(
        model_id="model_controlled_candidate_source",
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        calibrated=False,
        notes=["controlled candidate-only source fixture"],
    )

    skg_version_id = selected_skg_source.version_id
    skg_snapshot_ref = selected_skg_source.snapshot_ref

    selected_sources = tuple(dict.fromkeys(entry.source_id for entry in selected_entries))
    selected_families = tuple(dict.fromkeys(entry.family_id for entry in selected_entries))
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        built = build_world_model_record(
            artifact_store,
            fabric_world_ref=FabricWorldRef(
                snapshot_root=str(fabric_root),
                snapshot_id=snapshot_id,
                branch="main",
                as_of_valid_time=visible_time,
                as_of_tx_time=transaction_time,
                world_query_policy="default_allow_public",
                provenance_manifest_ref="fixture://controlled-candidate-source-v1",
            ),
            data_forge_snapshot_binding_path=(data_forge_root / "data_forge_snapshot_binding.json"),
            data_snapshot_ref=ArtifactRef.model_validate(
                data_snapshot_ref.model_dump(mode="python")
            ),
            model_spec=model_spec,
            skg_causal_prior_ref=SkgCausalPriorRef(
                skg_snapshot_ref=skg_snapshot_ref,
                skg_version_id=str(skg_version_id),
                source_data_snapshot_id=snapshot_id,
            ),
            substrate_registry=registry,
            region_or_jurisdiction=source_world_model_record.region_or_jurisdiction,
            population_scope=source_world_model_record.population_scope,
            policy_domain=source_world_model_record.policy_domain,
            valid_time_scope=source_world_model_record.valid_time_scope,
            tx_time_scope=source_world_model_record.tx_time_scope,
            resolution=source_world_model_record.resolution,
            branch_mode=BranchMode.SCENARIO,
            policy_slot_ids=tuple(controlled_slot_specs),
            producer_ref=(
                "tests._helpers.controlled_candidate_profile."
                "materialize_controlled_world_model_record"
            ),
            required_substrate_sources=selected_sources,
            required_substrate_families=selected_families,
            substrate_registry_artifact_ref=supplied_registry_ref,
            registry_bundle_artifact_ref=registry_bundle.bundle_ref,
            ncm_refs=tuple(str(ref.artifact_id) for ref in ncm_view_refs),
            ncm_view_refs=tuple(ncm_view_refs),
            limitations=WorldModelLimitations(
                admissibility_blockers=(
                    "source_time_not_established",
                    "source_to_target_measurement_contract_not_established",
                    "causal_coupling_not_established",
                )
            ),
            candidate_only=True,
        )
        persisted_record = load_world_model_record(artifact_store, built.record_ref)
        if persisted_record != built.record:
            raise ValueError("controlled_wmr_source_reader_mismatch")

    return built


def _materialize_controlled_world_model_record(
    *,
    source_world_model_record: Any,
    artifact_store: ArtifactStore,
    tmp_path: Path,
    source_root: Path | None = None,
    substrate_registry: Any,
    selected_registry_entry_hashes: Sequence[str],
    substrate_registry_ref: Any,
    policy_slot_ids: Sequence[str],
    selected_skg_source: ControlledSKGSourceSelection,
    tenant_id: str,
    cell_id: str,
    ncm_view_refs: Sequence[Any] = (),
    candidate_baseline_state: Mapping[str, object] | None = None,
    candidate_outcome_state_paths: Mapping[str, str] | None = None,
) -> Any:
    """Return the exact WMR from its owner build result for existing callers."""

    built = _materialize_controlled_world_model_build(
        source_world_model_record=source_world_model_record,
        artifact_store=artifact_store,
        tmp_path=tmp_path,
        source_root=source_root,
        substrate_registry=substrate_registry,
        selected_registry_entry_hashes=selected_registry_entry_hashes,
        substrate_registry_ref=substrate_registry_ref,
        policy_slot_ids=policy_slot_ids,
        selected_skg_source=selected_skg_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
        ncm_view_refs=ncm_view_refs,
        candidate_baseline_state=candidate_baseline_state,
        candidate_outcome_state_paths=candidate_outcome_state_paths,
    )
    return built.record


def _seed_controlled_selected_skg_source(
    tmp_path: Path,
    *,
    recorded_problem: DesignProblem,
    source_root: Path | None = None,
) -> ControlledSKGSourceSelection:
    """Build a variable-identity-only SKG through its canonical owner.

    The synthetic estimates admit variable identities for a controlled fixture;
    they do not create causal claims or establish source authority.
    """
    from polisyos.data_forge.domains.academic.knowledge.types import (
        EstimateCandidate,
        WorkRecord,
    )
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    admitted_source_root = source_root or tmp_path / "controlled-candidate-source"
    admitted_source_root.mkdir(parents=True, exist_ok=True)
    db_path = admitted_source_root / "academic-skg.duckdb"
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    selected_slots = tuple(
        dict.fromkeys(
            [lever.target_slot for lever in recorded_problem.candidate_lever_space.candidate_levers]
            + ["global.tax_rate", "government.balance", "cells.distress_score", outcome_variable]
        )
    )
    variables = tuple(
        dict.fromkeys(_CONTROLLED_SLOT_ALIASES.get(slot_id, slot_id) for slot_id in selected_slots)
    )
    record = WorkRecord(
        id="controlled-candidate-source-v1",
        title="Synthetic candidate variable-identity fixture",
        abstract=(
            "Synthetic fixture identities only; no causal or production claim is established."
        ),
        year=2026,
        estimates=[
            EstimateCandidate(
                value=0.0,
                pattern_name="controlled_candidate_variable_identity",
                variable_hint=variable,
            )
            for variable in variables
        ],
        metadata={"synthetic": True, "fixture_scope": "candidate_only"},
    )
    build_stats = build_synthetic_academic_skg_source(records=(record,), db_path=db_path)
    if build_stats.skg_versions != _CONTROLLED_SYNTHETIC_SKG_VERSION_COUNT:
        raise ValueError("controlled_selected_skg_source_build_version_set_mismatch")
    return _capture_controlled_skg_source(db_path)


def _seed_controlled_candidate_l6_source(source_owner_root: Path) -> Path:
    """Create fresh, empty candidate L6 data without inventing a lever or law.

    Only source/WMR fixture consumers use this bounded input. The real L6 owner
    still reads its authority manifest from the code root, verifies all hashes,
    and refuses an operator absent from the empty knob dictionary. This fixture
    does not establish an intervention, legal permission, or empirical grounding.
    """
    from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths

    root = Path(source_owner_root)
    root.mkdir(parents=True, exist_ok=False)
    root = root.resolve(strict=True)
    paths = default_l6_bundle_paths(REPO_ROOT, source_owner_root=root)
    for name in (
        "intervention_knob_dictionary",
        "lex_intervention_map",
        "observation_to_contract_manifest",
    ):
        path = paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    return root


@dataclass(frozen=True)
class _ControlledCandidateNCMParameters:
    """Scalar candidate assumptions shared by the model and its declaration."""

    target_world_slot: str
    outcome_variable: str
    target_baseline: float
    outcome_baseline: float
    outcome_per_target_unit: float
    outcome_noise_stddev: float


def _build_configured_procurement_profile(
    *,
    recorded_problem: DesignProblem,
    artifact_store: ArtifactStore,
    tenant_id: str,
    cell_id: str,
    tmp_path: Path,
    source_root: Path | None = None,
    selected_skg_source: ControlledSKGSourceSelection | None = None,
    repo_root: Path | None = None,
    l6_source_owner_root: Path | None = None,
    rule_operator_kind: str = "procurement_shock_intensity",
    rule_parameter_id: str = "intensity",
    rule_target_world_slot: str = "cells.distress_score",
    rule_unit_id: str = "synthetic_score",
    rule_minimum: int = 0,
    rule_maximum: int = 1,
    target_baseline: float = 0.0,
    outcome_baseline: float = 0.0,
) -> tuple[Any, Any, Any]:
    """Build a candidate profile from its exact owner-persisted WMR source."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        candidate_ncm_spec_from_declaration,
        load_ncm_spec,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry

    product_root = repo_root or REPO_ROOT
    _, base_context = _controlled_profile_cycle_basis(
        recorded_problem,
        repo_root=product_root,
    )
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    rule = CandidateScenarioSetToRule(
        operator_kind=rule_operator_kind,
        parameter_id=rule_parameter_id,
        target_world_slot=rule_target_world_slot,
        unit_id=rule_unit_id,
        minimum=rule_minimum,
        maximum=rule_maximum,
    )
    model_parameters = _ControlledCandidateNCMParameters(
        target_world_slot=rule.target_world_slot,
        outcome_variable=outcome_variable,
        target_baseline=target_baseline,
        outcome_baseline=outcome_baseline,
        outcome_per_target_unit=0.5,
        outcome_noise_stddev=0.01,
    )
    ncm = candidate_ncm_spec_from_declaration(model_parameters)
    selected_source = selected_skg_source or _seed_controlled_selected_skg_source(
        tmp_path,
        source_root=source_root,
        recorded_problem=recorded_problem,
    )
    candidate_slots = tuple(
        dict.fromkeys(
            [lever.target_slot for lever in recorded_problem.candidate_lever_space.candidate_levers]
            + ["global.tax_rate", "cells.distress_score", rule.target_world_slot, outcome_variable]
        )
    )
    baseline_state = {
        model_parameters.target_world_slot: model_parameters.target_baseline,
        model_parameters.outcome_variable: model_parameters.outcome_baseline,
    }
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://r1/controlled-candidate-n5",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state=baseline_state,
        seed=11,
        replications=2,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ncm_ref = persist_ncm_spec(_ensure_ir_artifact_store(artifact_store), ncm)
        substrate_registry_ref = persist_substrate_registry(
            artifact_store,
            base_context.substrate_registry,
        )
    world_build = _materialize_controlled_world_model_build(
        source_world_model_record=base_context.world_model_record,
        artifact_store=artifact_store,
        tmp_path=tmp_path,
        source_root=source_root,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        substrate_registry_ref=substrate_registry_ref,
        policy_slot_ids=candidate_slots,
        selected_skg_source=selected_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
        ncm_view_refs=(ncm_ref,),
        candidate_baseline_state=n5.baseline_state,
        candidate_outcome_state_paths=_controlled_direct_ncm_outcome_state_paths(outcome_variable),
    )
    world = world_build.record
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=(
            load_l6_intervention_substrate(product_root)
            if l6_source_owner_root is None
            else load_l6_intervention_substrate(
                product_root,
                source_owner_root=l6_source_owner_root,
            )
        ),
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
    )
    fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "r1.controlled.synthetic.procurement",
        "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    draft_profile = CandidateSimulationScenarioProfile.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft_profile.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY

    outcome_slot_id = _CONTROLLED_SLOT_ALIASES.get(
        model_parameters.outcome_variable, model_parameters.outcome_variable
    )
    outcome_slot = DEFAULT_SLOT_REGISTRY.slots.get(outcome_slot_id)
    outcome_unit_id = (
        outcome_slot.unit.unit_id
        if outcome_slot is not None and outcome_slot.unit is not None
        else rule.unit_id
    )
    declaration_fields = {
        "schema_version": ("policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": model_parameters.target_world_slot,
        "outcome_variable": model_parameters.outcome_variable,
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": outcome_unit_id,
        "target_baseline": model_parameters.target_baseline,
        "outcome_baseline": model_parameters.outcome_baseline,
        "outcome_per_target_unit": model_parameters.outcome_per_target_unit,
        "outcome_noise_stddev": model_parameters.outcome_noise_stddev,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    if profile.context_inputs.world_model_record != world_build.record:
        raise ValueError("controlled_candidate_profile_wmr_binding_mismatch")
    if (
        rule.target_world_slot != model_parameters.target_world_slot
        or n5.baseline_state != baseline_state
        or declaration.target_world_slot != model_parameters.target_world_slot
        or declaration.outcome_variable != model_parameters.outcome_variable
        or declaration.target_baseline != model_parameters.target_baseline
        or declaration.outcome_baseline != model_parameters.outcome_baseline
        or declaration.outcome_per_target_unit != model_parameters.outcome_per_target_unit
        or declaration.outcome_noise_stddev != model_parameters.outcome_noise_stddev
    ):
        raise ValueError("controlled_candidate_profile_ncm_declaration_binding_mismatch")
    declared_ncm = candidate_ncm_spec_from_declaration(declaration)
    if declared_ncm != ncm:
        raise ValueError("controlled_candidate_profile_ncm_declaration_binding_mismatch")
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        persisted_ncm = load_ncm_spec(_ensure_ir_artifact_store(artifact_store), ncm_ref)
    if persisted_ncm != declared_ncm:
        raise ValueError("controlled_candidate_profile_persisted_ncm_binding_mismatch")
    return profile, declaration, world_build


def _configured_procurement_profile(
    *,
    recorded_problem: DesignProblem,
    artifact_store: ArtifactStore,
    tenant_id: str,
    cell_id: str,
    tmp_path: Path,
    source_root: Path | None = None,
    selected_skg_source: ControlledSKGSourceSelection | None = None,
    repo_root: Path | None = None,
    l6_source_owner_root: Path | None = None,
    rule_operator_kind: str = "procurement_shock_intensity",
    rule_parameter_id: str = "intensity",
    rule_target_world_slot: str = "cells.distress_score",
    rule_unit_id: str = "synthetic_score",
    rule_minimum: int = 0,
    rule_maximum: int = 1,
    target_baseline: float = 0.0,
    outcome_baseline: float = 0.0,
) -> tuple[Any, Any]:
    """Return the profile and declaration from the exact owner-built WMR."""

    profile, declaration, _ = _build_configured_procurement_profile(
        recorded_problem=recorded_problem,
        artifact_store=artifact_store,
        tenant_id=tenant_id,
        cell_id=cell_id,
        tmp_path=tmp_path,
        source_root=source_root,
        selected_skg_source=selected_skg_source,
        repo_root=repo_root,
        l6_source_owner_root=l6_source_owner_root,
        rule_operator_kind=rule_operator_kind,
        rule_parameter_id=rule_parameter_id,
        rule_target_world_slot=rule_target_world_slot,
        rule_unit_id=rule_unit_id,
        rule_minimum=rule_minimum,
        rule_maximum=rule_maximum,
        target_baseline=target_baseline,
        outcome_baseline=outcome_baseline,
    )
    return profile, declaration


@dataclass(frozen=True)
class _Atom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str | None = "world_model_record_test"
    target_world_slots: tuple[str, ...] = ("firm_survival",)
    problem_frame_ref: str | None = None


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    atom: _Atom | InterventionAtomBinding
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "search_guiding"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_Candidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]
    grounding_dispositions: tuple[Any, ...] = ()
    design_problem_ref: str | None = None


@dataclass(frozen=True)
class _CertificateChain:
    cg1_certificate_id: str = "cg1_cert_test"
    cg1_content_hash: str = "sha256:" + "a" * 64
    cg2_certificate_id: str = "cg2_cert_test"
    cg2_content_hash: str = "sha256:" + "b" * 64
    cg3_certificate_id: str = "cg3_cert_test"
    cg3_content_hash: str = "sha256:" + "c" * 64
    cg4_proxy_gap_risk_id: str | None = None
    cg4_proxy_gap_content_hash: str | None = None
    cg4_quarantine_handoff_id: str | None = None
    cg4_quarantine_handoff_hash: str | None = None
    cg5_action_certificate_id: str | None = None
    cg5_action_content_hash: str | None = None
    cg5_ticket_id: str | None = None
    cg5_ticket_hash: str | None = None


@dataclass(frozen=True)
class _GroundingDisposition:
    proposal_id: str
    candidate_id: str | None
    raw_candidate_hash: str
    disposition: str
    selected_relation: str
    shadow_atom_content_hash: str | None = None
    identified_atom_id: str | None = "atom_test"
    cg2_decision: str | None = "shadow_frozen"
    cg2_reason: str | None = "cg2_frozen_until_cg6"
    cg3_decision: str | None = "shadow"
    cg3_reason: str | None = "cg3_shadow_only"
    rejected_cause: dict[str, Any] | None = None
    certificate_chain: _CertificateChain = _CertificateChain()
    bridge_missing_records: tuple[dict[str, Any], ...] = ()


class _SameCandidateNewBasisGenerator:
    """Return one candidate identity with a distinct content occurrence per cycle."""

    def __init__(self) -> None:
        self.problems: list[DesignProblem] = []

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        self.problems.append(problem)
        candidate = _Candidate(
            candidate_id="candidate_same_subject",
            atom=_Atom(
                "candidate_same_subject",
                "sha256:" + ("1" if cycle_index == 0 else "2") * 64,
            ),
            diversity_key=("grant", "firms", "same_subject", f"cycle_{cycle_index}"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(
                    candidate_id=candidate.candidate_id,
                    score=0.93 if cycle_index == 0 else 0.31,
                    voi_estimate=0.82 if cycle_index == 0 else 0.41,
                ),
            ),
        )


class _AlwaysLowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.2 if cycle_index == 0 else 0.68,
            issue_codes=("missing_supporting_data",) if cycle_index == 0 else (),
            evidence_refs=() if cycle_index == 0 else ("evidence://supporting-data",),
            current_valid=False,
        )


class _StableShadowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounded_shadow",
            grounding_score=0.8,
            evidence_refs=("evidence://b29/stable-shadow",),
            current_valid=False,
            report_ref="grounding://b29/stable-shadow",
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
        )


class _CgfGenerationPort:
    def __init__(
        self,
        *,
        missing_owner_target: bool = False,
        proxy_gap: bool = False,
        target_world_slots: tuple[str, ...] = ("firm_survival",),
    ) -> None:
        self._missing_owner_target = missing_owner_target
        self._proxy_gap = proxy_gap
        self._target_world_slots = target_world_slots

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del cycle_index
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        candidate = _Candidate(
            candidate_id="candidate_cgf_shadow",
            atom=_Atom(
                "candidate_cgf_shadow",
                "sha256:" + "4" * 64,
                target_world_slots=() if self._missing_owner_target else self._target_world_slots,
                problem_frame_ref=problem_ref,
            ),
            diversity_key=("grant", "firms", "cgf_shadow", "baseline"),
        )
        chain = _CertificateChain(
            cg4_proxy_gap_risk_id="cg4_proxy_gap_deadbeefdeadbeef" if self._proxy_gap else None,
            cg4_proxy_gap_content_hash="sha256:" + "d" * 64 if self._proxy_gap else None,
            cg4_quarantine_handoff_id="cg4_quarantine_deadbeefdeadbeef"
            if self._proxy_gap
            else None,
            cg4_quarantine_handoff_hash="sha256:" + "e" * 64 if self._proxy_gap else None,
            cg5_action_certificate_id="cg5_action_deadbeefdeadbeef" if self._proxy_gap else None,
            cg5_action_content_hash="sha256:" + "f" * 64 if self._proxy_gap else None,
        )
        disposition = _GroundingDisposition(
            proposal_id="proposal.cgf_shadow",
            candidate_id=candidate.candidate_id,
            raw_candidate_hash="sha256:" + "5" * 64,
            disposition="shadow_bound",
            selected_relation="exact",
            shadow_atom_content_hash=candidate.atom.content_hash,
            certificate_chain=chain,
            bridge_missing_records=(
                {
                    "pattern": "bridge_missing",
                    "owner": "CG4",
                    "integration_status": "handoff_artifact_n6_direct_intake_not_wired",
                },
            )
            if self._proxy_gap
            else (),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate.candidate_id, score=0.91, voi_estimate=0.6),
            ),
            grounding_dispositions=(disposition,),
            design_problem_ref=problem_ref,
        )


def _problem(problem_id: str = "generic_cycle_problem") -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement="Improve firm survival with grounded support under fiscal constraints.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Improve firm survival with grounded support.",
            source_surface="test_generation_cycle",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only research mandate",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-06-29",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Generated candidates remain shadow until A/N9 certification.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote generated candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant", "tax_relief"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="supporting_data",
                    question="Which data grounds this effect?",
                    required_for="A-side grounding",
                )
            ]
        ),
    )


def _budget(max_usd: str = "5.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


def _controlled_profile_cycle_basis(
    problem_seed: DesignProblem,
    *,
    runtime_hints: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[DesignProblem, Any]:
    """Build only the owner-bound cycle context consumed by the profile fixture."""
    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.generation_cycle import _build_boundary_world_model_record
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateCoverage,
        SubstrateLayer,
        SubstrateRegistration,
        SubstrateSchemaRegime,
        SubstrateTrustTier,
        build_substrate_registry,
        build_substrate_registry_entry,
    )

    hints: dict[str, Any] = {
        "joint_simulation_budget_ref": f"budget://cyc-01/{uuid4().hex}/n5",
        "joint_simulation_horizon": {"start": 0, "end": 3, "step": 1},
        "joint_simulation_resource": "ncm_parallel_worlds",
    }
    if runtime_hints:
        hints.update(runtime_hints)
    problem = problem_seed.model_copy(update={"runtime_hints": hints})
    domain = problem.domain
    registration = SubstrateRegistration(
        source_id="l2_cyc:serializable_n5_builder.duckdb",
        family_id=f"{domain}_causal_priors",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.74,
            coverage_kind="lane0.causal_claim_coverage",
            coverage_rule_ref=f"lane0://{domain}/coverage",
            observation_count=7,
            metric_binding_count=3,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"lane0://{domain}/trust",
        ),
        identification_mode="causal_prior_candidate",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{domain}_schema_v1",
            authority_ref=f"lane0://{domain}/schema",
            source_version="1",
        ),
        data_version=f"{domain}-data-v1",
        snapshot_id=f"{domain}-snapshot-v1",
        source_snapshot_id=f"{domain}-snapshot-v1",
        provenance_refs=(f"lane0://{domain}/causal-claims",),
        authority_refs=(f"lane0://{domain}/registry-owner",),
    )
    registry = build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="tests.unit.runtime.quality.test_generation_cycle",
        source_catalog_refs=registration.authority_refs,
    )
    selected_hash = registry.entries[0].entry_content_hash
    world = _build_boundary_world_model_record(
        repo_root=repo_root or REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("agents.income", "government.balance", "firm_survival"),
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    substrate_input_hash = gy_content_hash(
        {"domain": problem.domain, "registry": registry.content_hash}
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("cyc-n5-builder-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )
    return problem, context
