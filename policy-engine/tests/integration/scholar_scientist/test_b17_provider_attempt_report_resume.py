from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef, FileSystemCAS
from polisyos.scholar.search.jobs import DeepResearchJobManager
from polisyos.scholar.search.models import (
    FetchResult,
    ProviderAttemptTrace,
    SearchBudgetControls,
    SearchConstraints,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService

_PRIVATE_PROVIDER_DETAIL = (
    "https://provider.invalid/search?token=private-provider-token&email=private@example.test"
)


class _PrivacyFailureProvider:
    name = "privacy-failure"

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        del query, constraints, max_results, timeout_s
        raise RuntimeError(f"request failed: {_PRIVATE_PROVIDER_DETAIL}")


class _SuccessfulProvider:
    name = "fixture-success"

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        del constraints, timeout_s
        return [
            WebSearchHit(
                url="https://agency.gov/minimum-wage",
                title="Agency minimum wage report",
                snippet="The policy increased earnings for low-wage workers.",
                provider=self.name,
                query=query,
                rank=1,
                source_type="government",
            )
        ][:max_results]


class _FailOnceAfterProgress:
    """Exercise the real job checkpoint path before a normal resume."""

    def __init__(self, delegate: ScholarDeepSearchService) -> None:
        self._delegate = delegate
        self._calls = 0

    async def deep_search(self, **kwargs: Any) -> WebEvidenceBundle:
        self._calls += 1
        if self._calls != 1:
            return await self._delegate.deep_search(**kwargs)

        original_callback = kwargs.get("progress_callback")
        if original_callback is None:
            raise AssertionError("job manager must provide its checkpoint callback")

        async def _checkpoint_progress(event: Any, bundle: WebEvidenceBundle) -> None:
            outcome = original_callback(event, bundle)
            if hasattr(outcome, "__await__"):
                await outcome

        await self._delegate.deep_search(**{**kwargs, "progress_callback": _checkpoint_progress})
        raise RuntimeError("controlled interruption after persisted progress")


async def _fixture_fetch_open_page(
    url: str,
    *,
    constraints: SearchConstraints,
    cache: object,
    timeout_s: float,
    user_agent: str,
    max_bytes: int,
    source_type_hint: str,
) -> FetchResult:
    del constraints, cache, timeout_s, user_agent, max_bytes
    return FetchResult(
        url=url,
        final_url=url,
        title="Agency minimum wage report",
        text="The policy increased earnings for low-wage workers.",
        content_type="text/html",
        status="ok",
        content_sha256="sha256:fixture-minimum-wage-page",
        source_type=source_type_hint,
    )


def _private_provider_fragments() -> tuple[str, ...]:
    parsed = urlsplit(_PRIVATE_PROVIDER_DETAIL)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    return tuple(
        dict.fromkeys(
            (
                _PRIVATE_PROVIDER_DETAIL,
                parsed.netloc,
                *(part for pair in query_pairs for part in pair),
            )
        )
    )


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)


def _assert_no_private_provider_details(
    persisted_payloads: Mapping[str, bytes],
) -> None:
    needles = _private_provider_fragments()
    assert persisted_payloads
    for sink, payload in persisted_payloads.items():
        for needle in needles:
            assert needle.encode() not in payload, f"private bytes found in {sink}"
        parsed_payload = json.loads(payload)
        for value in _iter_strings(parsed_payload):
            for needle in needles:
                assert needle not in value, f"private string found in {sink}"


def _provider_trace_with_attempts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [row for row in rows if row.get("provider_attempts")]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.asyncio
async def test_provider_attempts_survive_checkpoint_resume_and_reach_fresh_cas_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fixture_fetch_open_page,
    )
    cas = FileSystemCAS(tmp_path / "cas")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_PrivacyFailureProvider(), _SuccessfulProvider()]),
        cas=cas,
    )
    manager = DeepResearchJobManager(
        service=_FailOnceAfterProgress(service),
        cas=cas,
    )

    job_id = manager.submit(
        question="minimum wage earnings",
        claim_texts=["minimum wage increased earnings for low-wage workers"],
        constraints=SearchConstraints(allowed_domains=["agency.gov"]),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
        ),
    )
    failed_status = await manager.wait(job_id)

    assert failed_status.status == "failed"
    assert failed_status.checkpoint_artifact_id is not None
    checkpoint_artifact_id = failed_status.checkpoint_artifact_id
    checkpoint_bytes = cas.get_bytes(checkpoint_artifact_id)
    checkpoint = json.loads(checkpoint_bytes)
    assert checkpoint["bundle"]["schema_version"] == "1.1"
    checkpoint_trace = _provider_trace_with_attempts(checkpoint["bundle"]["query_traces"])
    assert checkpoint_trace["provider_attempts"][0]["error_type"] == "provider_exception"

    resumed_job_id = await manager.resume(
        checkpoint_artifact_id=failed_status.checkpoint_artifact_id
    )
    completed_status = await manager.wait(resumed_job_id)

    assert completed_status.status == "completed"
    assert completed_status.scholar_academic_evidence_artifact_id is not None
    assert completed_status.result_bundle is not None
    assert completed_status.result_bundle.schema_version == "1.1"
    assert completed_status.result_bundle.query_traces[0].provider_attempts is not None

    status_path = tmp_path / "cas" / "scholar_web_jobs" / "status_index.json"
    status_bytes = status_path.read_bytes()
    checkpoint_id = ArtifactID.model_validate(checkpoint_artifact_id)
    report_id = ArtifactID.model_validate(completed_status.scholar_academic_evidence_artifact_id)
    default_view_ids = {str(artifact_id) for artifact_id in cas.iter_artifact_ids()}
    assert str(checkpoint_id) in default_view_ids
    assert str(report_id) in default_view_ids

    inventory = cas.inventory_snapshot()
    assert inventory.verdict == "pass", inventory.reason
    persisted_payloads: dict[str, bytes] = {}
    inventory_default_view_ids: set[str] = set()
    checkpoint_blob_keys: list[str] = []
    checkpoint_default_blob_keys: list[str] = []
    checkpoint_profile_keys: list[str] = []
    report_blob_keys: list[str] = []
    report_default_blob_keys: list[str] = []
    for entry in inventory.entries:
        ref = entry.artifact_ref
        if isinstance(ref, ArtifactRef):
            artifact_id = ref.artifact_id
            profile = ref.manifest_profile_sha256
            assert profile is not None
            assert ref.kind == entry.manifest.kind
            assert ref.media_type == entry.manifest.media_type
        else:
            artifact_id = ref
            profile = None
            inventory_default_view_ids.add(str(artifact_id))

        identity = (
            str(artifact_id),
            entry.manifest.kind,
            entry.manifest.media_type,
            profile,
        )
        identity_key = json.dumps(identity, separators=(",", ":"))
        blob_key = f"cas-blob-view:{identity_key}"
        manifest_key = f"cas-manifest-view:{identity_key}"
        assert blob_key not in persisted_payloads
        assert manifest_key not in persisted_payloads

        blob_bytes = cas.get_bytes(ref)
        assert len(blob_bytes) == entry.blob_byte_size
        assert hashlib.sha256(blob_bytes).hexdigest() == entry.blob_sha256.removeprefix("sha256:")
        persisted_payloads[blob_key] = blob_bytes

        manifest_bytes = cas.get_manifest_bytes(ref)
        assert len(manifest_bytes) == entry.manifest_byte_size
        assert hashlib.sha256(manifest_bytes).hexdigest() == entry.manifest_sha256.removeprefix(
            "sha256:"
        )
        persisted_payloads[manifest_key] = manifest_bytes

        try:
            signature_bytes = cas.get_signature_bytes(ref)
        except FileNotFoundError:
            pass
        else:
            signature_key = f"cas-signature-view:{identity_key}"
            assert signature_key not in persisted_payloads
            persisted_payloads[signature_key] = signature_bytes

        if (
            str(artifact_id) == str(checkpoint_id)
            and entry.manifest.kind == "scholar.web_research_checkpoint"
        ):
            checkpoint_blob_keys.append(blob_key)
            if isinstance(ref, ArtifactRef):
                checkpoint_profile_keys.append(blob_key)
            else:
                checkpoint_default_blob_keys.append(blob_key)
        if (
            str(artifact_id) == str(report_id)
            and entry.manifest.kind == "scholar.academic_evidence"
        ):
            report_blob_keys.append(blob_key)
            if not isinstance(ref, ArtifactRef):
                report_default_blob_keys.append(blob_key)

    assert inventory_default_view_ids == default_view_ids
    assert str(checkpoint_id) in inventory_default_view_ids
    assert str(report_id) in inventory_default_view_ids
    assert checkpoint_blob_keys
    assert checkpoint_default_blob_keys
    assert checkpoint_profile_keys
    assert report_blob_keys
    assert report_default_blob_keys
    assert all(persisted_payloads[key] == checkpoint_bytes for key in checkpoint_blob_keys)
    assert len({persisted_payloads[key] for key in report_blob_keys}) == 1
    assert persisted_payloads[report_default_blob_keys[0]] == cas.get_bytes(report_id)
    persisted_payloads["job-status-index"] = status_bytes
    _assert_no_private_provider_details(persisted_payloads)

    report_bytes = persisted_payloads[report_default_blob_keys[0]]
    report = json.loads(report_bytes)
    report_trace = _provider_trace_with_attempts(report["provider_traces"])
    attempts = report_trace["provider_attempts"]
    typed_attempts = [ProviderAttemptTrace.model_validate(item) for item in attempts]
    assert [item.attempt_index for item in typed_attempts] == [0, 1]
    assert [item["provider"] for item in attempts] == [
        "privacy-failure",
        "fixture-success",
    ]
    assert [item["outcome"] for item in attempts] == ["error", "returned_hits"]
    assert attempts[0]["error"] == "provider_error"
    assert attempts[0]["error_type"] == "provider_exception"
    assert attempts[1]["returned_hit_count"] == report_trace["hit_count"] > 0
    assert report_trace.get("error") is None

    persisted_status = json.loads(status_bytes)[job_id]
    assert persisted_status["status"] == "completed"
    status_trace = _provider_trace_with_attempts(persisted_status["result_bundle"]["query_traces"])
    assert status_trace["provider_attempts"] == attempts
