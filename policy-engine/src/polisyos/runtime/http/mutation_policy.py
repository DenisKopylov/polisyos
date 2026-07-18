"""Shared write-path hardening for runtime mutations and live streams."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.serialization import fast_json_dumps
from polisyos.runtime.http.errors import problem_response

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
else:  # pragma: no cover - optional runtime dependency
    try:
        from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response
    except ModuleNotFoundError:  # pragma: no cover
        _BaseHTTPMiddleware = cast("type[Any]", object)
        Request = cast("Any", None)
        Response = cast("Any", None)
        JSONResponse = cast("Any", None)


def _as_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _now_seconds() -> float:
    return time.monotonic()


def _normalize_tenant_id(request: Request) -> str:
    access_scope = getattr(request.state, "access_scope", None)
    if access_scope is not None and getattr(access_scope, "tenant_id", None):
        return str(access_scope.tenant_id)
    if getattr(request.state, "tenant_id", None):
        return str(request.state.tenant_id)
    header_tenant = request.headers.get("X-Tenant-ID")
    if header_tenant:
        return header_tenant
    return "anonymous"


def _request_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _cache_key(*, tenant_id: str, method: str, path: str, idempotency_key: str) -> str:
    material = f"{tenant_id}:{method}:{path}:{idempotency_key}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _resource_ids_from_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    resource_ids: list[str] = []
    for key in (
        "run_id",
        "job_id",
        "reissued_run_id",
        "promotion_id",
        "pipeline_id",
        "data_snapshot_ref",
        "evidence_bundle_ref",
        "record_ref",
        "cursor_ref",
        "decision_packet_ref",
        "event_id",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            resource_ids.append(value)
    for key in ("monitoring_report_ref", "compare_report_ref", "reissue_plan_ref"):
        value = payload.get(key)
        if isinstance(value, dict):
            artifact_id = value.get("artifact_id")
            if isinstance(artifact_id, str) and artifact_id:
                resource_ids.append(artifact_id)
    return sorted(set(resource_ids))


def _is_live_stream_path(path: str) -> bool:
    if path == "/api/v1/runs/live":
        return True
    if path.startswith("/api/v1/runs/") and path.endswith("/live"):
        return True
    return path == "/api/v1/review/live"


def _is_mutation_path(method: str, path: str) -> bool:
    return method.upper() == "POST" and path.startswith("/api/v1/control")


def _is_managed_request(method: str, path: str) -> bool:
    return _is_mutation_path(method, path) or (
        method.upper() == "GET" and _is_live_stream_path(path)
    )


@dataclass(frozen=True, slots=True)
class IdempotencyReplay:
    status_code: int
    body: Any
    media_type: str


class RuntimeRateLimiter:
    """Fixed-window rate limits for mutations plus concurrent live-stream budgets."""

    def __init__(
        self,
        *,
        write_limit: int = 24,
        write_window_seconds: int = 60,
        live_limit: int = 8,
        live_window_seconds: int = 60,
        live_concurrency_limit: int = 4,
        metrics: Any | None = None,
    ) -> None:
        self._write_limit = max(write_limit, 1)
        self._write_window_seconds = max(write_window_seconds, 1)
        self._live_limit = max(live_limit, 1)
        self._live_window_seconds = max(live_window_seconds, 1)
        self._live_concurrency_limit = max(live_concurrency_limit, 1)
        self._metrics = metrics
        self._lock = threading.Lock()
        self._request_windows: dict[tuple[str, str], list[float]] = {}
        self._active_live_streams: dict[tuple[str, str], int] = {}

    def check_request(self, *, tenant_id: str, method: str, path: str) -> tuple[bool, int | None]:
        endpoint_key = self._endpoint_bucket(method=method, path=path)
        now = _now_seconds()
        window = (
            self._live_window_seconds
            if endpoint_key.startswith("live:")
            else self._write_window_seconds
        )
        limit = self._live_limit if endpoint_key.startswith("live:") else self._write_limit
        bucket_key = (tenant_id, endpoint_key)
        with self._lock:
            timestamps = [
                stamp for stamp in self._request_windows.get(bucket_key, []) if now - stamp < window
            ]
            if len(timestamps) >= limit:
                retry_after = max(1, int(window - (now - timestamps[0])))
                self._request_windows[bucket_key] = timestamps
                self._record_rate_limit_event(
                    endpoint=endpoint_key, mode="request", outcome="throttled"
                )
                return False, retry_after
            timestamps.append(now)
            self._request_windows[bucket_key] = timestamps
        self._record_rate_limit_event(endpoint=endpoint_key, mode="request", outcome="allowed")
        return True, None

    def acquire_live_stream(self, *, tenant_id: str, path: str) -> tuple[bool, str]:
        endpoint_key = self._endpoint_bucket(method="GET", path=path)
        stream_key = (tenant_id, endpoint_key)
        with self._lock:
            active = self._active_live_streams.get(stream_key, 0)
            if active >= self._live_concurrency_limit:
                self._record_rate_limit_event(
                    endpoint=endpoint_key, mode="concurrency", outcome="throttled"
                )
                return False, ""
            active += 1
            self._active_live_streams[stream_key] = active
        self._record_rate_limit_event(endpoint=endpoint_key, mode="concurrency", outcome="acquired")
        self._set_live_streams(endpoint=endpoint_key, active_streams=active)
        return True, f"{tenant_id}:{path}"

    def release_live_stream(self, *, tenant_id: str, path: str) -> None:
        endpoint_key = self._endpoint_bucket(method="GET", path=path)
        stream_key = (tenant_id, endpoint_key)
        with self._lock:
            active = self._active_live_streams.get(stream_key, 0)
            if active <= 1:
                self._active_live_streams.pop(stream_key, None)
                active = 0
            else:
                active -= 1
                self._active_live_streams[stream_key] = active
        self._set_live_streams(endpoint=endpoint_key, active_streams=active)

    @staticmethod
    def _endpoint_bucket(*, method: str, path: str) -> str:
        if _is_live_stream_path(path):
            if path == "/api/v1/review/live" or path == "/api/v1/runs/live":
                normalized_path = path
            else:
                normalized_path = "/api/v1/runs/{run_id}/live"
            return f"live:{normalized_path}"
        return f"{method.upper()}:{path}"

    def _record_rate_limit_event(self, *, endpoint: str, mode: str, outcome: str) -> None:
        recorder = getattr(self._metrics, "record_runtime_rate_limit_event", None)
        if callable(recorder):
            recorder(endpoint=endpoint, mode=mode, outcome=outcome)

    def _set_live_streams(self, *, endpoint: str, active_streams: int) -> None:
        setter = getattr(self._metrics, "set_runtime_live_streams", None)
        if callable(setter):
            setter(endpoint=endpoint, active_streams=active_streams)


class RuntimeIdempotencyStore:
    """Persist completed idempotent mutation responses for replay-safe retries."""

    def __init__(self, *, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._pending: set[str] = set()

    def begin(
        self,
        *,
        tenant_id: str,
        method: str,
        path: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[str, IdempotencyReplay | None]:
        key = _cache_key(
            tenant_id=tenant_id,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
        )
        path_on_disk = self._root / f"{key}.json"
        with self._lock:
            if path_on_disk.exists():
                record = json.loads(path_on_disk.read_text(encoding="utf-8"))
                if record.get("request_hash") != request_hash:
                    return "mismatch", None
                return (
                    "replay",
                    IdempotencyReplay(
                        status_code=int(record["status_code"]),
                        body=record.get("body"),
                        media_type=str(record.get("media_type") or "application/json"),
                    ),
                )
            if key in self._pending:
                return "pending", None
            self._pending.add(key)
        return "started", None

    def complete(
        self,
        *,
        tenant_id: str,
        method: str,
        path: str,
        idempotency_key: str,
        request_hash: str,
        status_code: int,
        media_type: str,
        body: Any,
    ) -> None:
        key = _cache_key(
            tenant_id=tenant_id,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
        )
        record = {
            "tenant_id": tenant_id,
            "method": method,
            "path": path,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "status_code": status_code,
            "media_type": media_type,
            "body": body,
            "completed_at": time.time(),
        }
        target = self._root / f"{key}.json"
        self._atomic_write_json(target, record)
        with self._lock:
            self._pending.discard(key)

    def fail(
        self,
        *,
        tenant_id: str,
        method: str,
        path: str,
        idempotency_key: str,
    ) -> None:
        key = _cache_key(
            tenant_id=tenant_id,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
        )
        with self._lock:
            self._pending.discard(key)

    @staticmethod
    def _atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=target.stem, suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(fast_json_dumps(payload, sort_keys=True))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


class RuntimeMutationAuditTrail:
    """Append-only mutation audit log for compliance review and incident analysis."""

    def __init__(self, *, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> None:
        line = fast_json_dumps(entry, sort_keys=False) + "\n"
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


class MutationProtectionMiddleware(_BaseHTTPMiddleware):
    """Apply rate limiting, idempotency replay, and mutation audit logging."""

    def __init__(
        self,
        app: Any,
        *,
        rate_limiter: RuntimeRateLimiter,
        idempotency_store: RuntimeIdempotencyStore,
        audit_trail: RuntimeMutationAuditTrail,
    ) -> None:
        if JSONResponse is None:
            raise RuntimeError(
                "MutationProtectionMiddleware requires starlette/fastapi dependencies"
            )
        super().__init__(app)
        self._rate_limiter = rate_limiter
        self._idempotency_store = idempotency_store
        self._audit_trail = audit_trail
        self._json_response_cls = cast("Any", JSONResponse)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        method = request.method.upper()
        path = str(getattr(request.url, "path", ""))
        if not _is_managed_request(method, path):
            return await call_next(request)

        tenant_id = _normalize_tenant_id(request)
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        live_stream_acquired = False
        idempotency_key = (
            request.headers.get("X-Idempotency-Key") if _is_mutation_path(method, path) else None
        )
        request_hash_value: str | None = None
        if idempotency_key:
            raw_body = await request.body()
            request_hash_value = _request_hash(raw_body)
            state, replay = self._idempotency_store.begin(
                tenant_id=tenant_id,
                method=method,
                path=path,
                idempotency_key=idempotency_key,
                request_hash=request_hash_value,
            )
            if state == "replay" and replay is not None:
                response = self._json_response_cls(
                    status_code=replay.status_code,
                    content=replay.body,
                    media_type=replay.media_type,
                )
                response.headers["X-Idempotent-Replay"] = "true"
                if live_stream_acquired:
                    self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)
                return response
            if state == "mismatch":
                if live_stream_acquired:
                    self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)
                return problem_response(
                    status_code=409,
                    code="idempotency_key_reused",
                    detail="X-Idempotency-Key cannot be reused with a different request payload",
                    request_id=request_id,
                    instance=path,
                    error="idempotency_key_reused",
                )
            if state == "pending":
                if live_stream_acquired:
                    self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)
                return problem_response(
                    status_code=409,
                    code="idempotency_request_in_progress",
                    detail="A matching idempotent request is still in progress",
                    request_id=request_id,
                    instance=path,
                    error="idempotency_request_in_progress",
                )

        allowed, retry_after = self._rate_limiter.check_request(
            tenant_id=tenant_id,
            method=method,
            path=path,
        )
        if not allowed:
            if idempotency_key and request_hash_value is not None:
                self._idempotency_store.fail(
                    tenant_id=tenant_id,
                    method=method,
                    path=path,
                    idempotency_key=idempotency_key,
                )
            return problem_response(
                status_code=429,
                code="rate_limit_exceeded",
                detail="Runtime request rate limit exceeded",
                request_id=request_id,
                instance=path,
                error="rate_limit_exceeded",
                extensions={"retry_after_seconds": retry_after},
            )

        if _is_live_stream_path(path):
            live_stream_acquired, _ = self._rate_limiter.acquire_live_stream(
                tenant_id=tenant_id,
                path=path,
            )
            if not live_stream_acquired:
                if idempotency_key and request_hash_value is not None:
                    self._idempotency_store.fail(
                        tenant_id=tenant_id,
                        method=method,
                        path=path,
                        idempotency_key=idempotency_key,
                    )
                return problem_response(
                    status_code=429,
                    code="live_stream_limit_exceeded",
                    detail="Too many concurrent live streams for this tenant and endpoint",
                    request_id=request_id,
                    instance=path,
                    error="live_stream_limit_exceeded",
                )

        try:
            response = await call_next(request)
        except Exception:
            self._append_audit_entry(
                request=request,
                tenant_id=tenant_id,
                path=path,
                outcome="error",
                status_code=500,
                resource_ids=[],
                request_hash_value=request_hash_value,
                response_hash=None,
            )
            if idempotency_key and request_hash_value is not None:
                self._idempotency_store.fail(
                    tenant_id=tenant_id,
                    method=method,
                    path=path,
                    idempotency_key=idempotency_key,
                )
            if live_stream_acquired:
                self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)
            raise

        if _is_live_stream_path(path):
            return self._wrap_live_stream_response(
                request=request,
                response=response,
                tenant_id=tenant_id,
                path=path,
            )

        payload = None
        response_hash = None
        media_type = getattr(response, "media_type", None) or response.headers.get(
            "content-type", "application/json"
        )
        body_bytes = await self._capture_response_body(response)
        if isinstance(body_bytes, bytes) and body_bytes:
            decoded_bytes = body_bytes
            if str(response.headers.get("content-encoding", "")).lower() == "gzip":
                decoded_bytes = gzip.decompress(body_bytes)
            if "json" in str(media_type):
                payload = json.loads(decoded_bytes.decode("utf-8"))
            else:
                payload = decoded_bytes.decode("utf-8")
            response_hash = hashlib.sha256(body_bytes).hexdigest()

        if idempotency_key and request_hash_value is not None:
            if int(getattr(response, "status_code", 500)) < 500:
                self._idempotency_store.complete(
                    tenant_id=tenant_id,
                    method=method,
                    path=path,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash_value,
                    status_code=int(getattr(response, "status_code", 500)),
                    media_type=str(media_type),
                    body=payload,
                )
            else:
                self._idempotency_store.fail(
                    tenant_id=tenant_id,
                    method=method,
                    path=path,
                    idempotency_key=idempotency_key,
                )

        self._append_audit_entry(
            request=request,
            tenant_id=tenant_id,
            path=path,
            outcome="success" if int(getattr(response, "status_code", 500)) < 400 else "rejected",
            status_code=int(getattr(response, "status_code", 500)),
            resource_ids=_resource_ids_from_payload(payload),
            request_hash_value=request_hash_value,
            response_hash=response_hash,
        )
        if live_stream_acquired:
            self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)
        return response

    async def _capture_response_body(self, response: Response) -> bytes:
        response_any = cast("Any", response)
        body_iterator = getattr(response_any, "body_iterator", None)
        if body_iterator is not None:
            chunks: list[bytes] = []
            async for chunk in body_iterator:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
                else:
                    chunks.append(str(chunk).encode("utf-8"))
            body = b"".join(chunks)

            async def _replay_body() -> AsyncIterator[bytes]:
                if body:
                    yield body

            response_any.body_iterator = _replay_body()
            if body:
                response.headers["content-length"] = str(len(body))
            return body

        body = getattr(response, "body", b"")
        return body if isinstance(body, bytes) else bytes(body)

    def _wrap_live_stream_response(
        self,
        *,
        request: Request,
        response: Response,
        tenant_id: str,
        path: str,
    ) -> Response:
        response_any = cast("Any", response)
        original_iterator = getattr(response_any, "body_iterator", None)
        if original_iterator is None:
            self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)
            return response

        async def _managed_iterator() -> AsyncIterator[Any]:
            try:
                async for chunk in original_iterator:
                    yield chunk
            finally:
                self._rate_limiter.release_live_stream(tenant_id=tenant_id, path=path)

        response_any.body_iterator = _managed_iterator()
        self._append_audit_entry(
            request=request,
            tenant_id=tenant_id,
            path=path,
            outcome="stream_opened",
            status_code=int(getattr(response, "status_code", 200)),
            resource_ids=[],
            request_hash_value=None,
            response_hash=None,
        )
        return response

    def _append_audit_entry(
        self,
        *,
        request: Request,
        tenant_id: str,
        path: str,
        outcome: str,
        status_code: int,
        resource_ids: list[str],
        request_hash_value: str | None,
        response_hash: str | None,
    ) -> None:
        claims = getattr(request.state, "user_claims", None)
        effective_scope = getattr(request.state, "authz_effective_scope", None)
        actor = (
            getattr(effective_scope, "user_sub", None)
            or getattr(effective_scope, "spiffe_id", None)
            or getattr(claims, "sub", None)
            or getattr(request.state, "authenticated_tenant_id", None)
            or "anonymous"
        )
        request_id = getattr(getattr(request, "state", object()), "request_id", None)
        self._audit_trail.append(
            {
                "timestamp": time.time(),
                "request_id": request_id,
                "tenant_id": tenant_id,
                "actor": actor,
                "method": request.method.upper(),
                "endpoint": path,
                "operation": f"{request.method.upper()} {path}",
                "outcome": outcome,
                "status_code": status_code,
                "resource_ids": resource_ids,
                "before_hash": getattr(request.state, "mutation_before_hash", None),
                "after_hash": response_hash,
                "request_hash": request_hash_value,
                "idempotency_key": request.headers.get("X-Idempotency-Key"),
            }
        )


def build_runtime_mutation_services(
    *, cas_root: Path, metrics: Any | None = None
) -> tuple[
    RuntimeRateLimiter,
    RuntimeIdempotencyStore,
    RuntimeMutationAuditTrail,
]:
    runtime_root = cas_root / "runtime"
    rate_limiter = RuntimeRateLimiter(
        write_limit=int(os.getenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "24")),
        write_window_seconds=int(os.getenv("POLISYOS_RUNTIME_WRITE_RATE_WINDOW_SECONDS", "60")),
        live_limit=int(os.getenv("POLISYOS_RUNTIME_LIVE_RATE_LIMIT", "8")),
        live_window_seconds=int(os.getenv("POLISYOS_RUNTIME_LIVE_RATE_WINDOW_SECONDS", "60")),
        live_concurrency_limit=int(os.getenv("POLISYOS_RUNTIME_LIVE_CONCURRENCY_LIMIT", "4")),
        metrics=metrics,
    )
    idempotency_store = RuntimeIdempotencyStore(root=runtime_root / "idempotency")
    audit_trail = RuntimeMutationAuditTrail(path=runtime_root / "audit" / "mutations.jsonl")
    return rate_limiter, idempotency_store, audit_trail


__all__ = [
    "MutationProtectionMiddleware",
    "RuntimeIdempotencyStore",
    "RuntimeMutationAuditTrail",
    "RuntimeRateLimiter",
    "build_runtime_mutation_services",
]
