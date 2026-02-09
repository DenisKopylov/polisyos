"""
APISimulator -- record / replay / synthetic HTTP mocking engine.

Three modes control how the simulator serves responses to connector code:

    REPLAY      (default, CI-safe)
        Intercepts every outbound HTTP request and serves the response
        from a JSON fixture file on disk. If the fixture is missing,
        the test FAILS immediately -- it never falls through to the network.

    RECORD
        Proxies the real request to the network, captures the full
        response (status, headers, body), and writes it to a fixture
        file. Activate with pytest --record-mode or by explicitly
        constructing APISimulator(mode=SimulatorMode.RECORD).

    SYNTHETIC
        Generates random response payloads that conform to a given
        DataSchema. Useful for load / property-based tests where
        fixture diversity matters more than realism.

Architecture
------------
The simulator patches aiohttp.ClientSession (the transport layer used by
BaseConnector) via a context manager. All connector code under
"async with simulator:" sees the patched session transparently.

Fixture layout on disk::

    tests/fabric/connectors/fixtures/
    +-- <connector_id>/
        +-- <dataset_id>/
            +-- <request_content_hash>.json

If dataset_id is not provided, it defaults to "unknown" so the layout
remains consistent with the documented structure.
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import MISSING, dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from unittest.mock import patch

from polisyos.core.canon import content_hash

# ---------------------------------------------------------------------------
# Enums & data objects
# ---------------------------------------------------------------------------


class SimulatorMode(Enum):
    """Operating mode for APISimulator."""

    REPLAY = auto()      # Serve from fixture; fail if missing
    RECORD = auto()      # Proxy to network, save fixture
    SYNTHETIC = auto()   # Generate schema-conformant random data


@dataclass(frozen=True)
class SimulatorFixture:
    """
    On-disk representation of a single captured API response.

    Attributes:
        status_code:      HTTP status that was returned.
        headers:          Response headers (string -> string).
        body:             Base64-encoded response body.
        captured_at:      ISO-8601 timestamp when the fixture was recorded.
        request_url:      The URL that was originally requested.
        request_method:   HTTP method (GET, POST, ...).
        request_hash:     SHA-256 of the canonical request for lookup.
        connector_id:     Which connector produced this fixture.
        dataset_id:       Logical dataset identifier.
    """

    status_code: int
    headers: dict[str, str]
    body: str  # base64
    captured_at: str
    request_url: str
    request_method: str
    request_hash: str
    connector_id: str = ""
    dataset_id: str = ""

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "captured_at": self.captured_at,
            "request_url": self.request_url,
            "request_method": self.request_method,
            "request_hash": self.request_hash,
            "connector_id": self.connector_id,
            "dataset_id": self.dataset_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulatorFixture":
        kwargs: dict[str, Any] = {}
        for name, field in cls.__dataclass_fields__.items():
            if name in data:
                kwargs[name] = data[name]
            elif field.default is not MISSING:
                kwargs[name] = field.default
            elif field.default_factory is not MISSING:  # type: ignore[comparison-overlap]
                kwargs[name] = field.default_factory()  # type: ignore[misc]
            else:
                raise KeyError(name)
        return cls(**kwargs)

    def write(self, path: Path) -> None:
        """Persist fixture to path (creates parent dirs)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "SimulatorFixture":
        """Load fixture from path."""
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------
    # Decoded accessors
    # ------------------------------------------------------------------

    @property
    def body_bytes(self) -> bytes:
        """Decode the base64 body back to raw bytes."""
        return base64.b64decode(self.body)

    @property
    def body_text(self) -> str:
        """Decode the body as UTF-8 text."""
        return self.body_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# Request hashing (deterministic fixture lookup key)
# ---------------------------------------------------------------------------


def _normalize_params(params: Any) -> list[tuple[str, str]]:
    """Normalize query params into a sorted list of (key, value) tuples."""
    if params is None:
        return []

    items: list[tuple[str, str]] = []

    if isinstance(params, dict):
        iterable: Iterable[tuple[Any, Any]] = params.items()
    elif isinstance(params, (list, tuple)):
        iterable = params  # type: ignore[assignment]
    else:
        # Fallback: treat as a single opaque value
        return [(str(params), "")]

    for key, value in iterable:
        if isinstance(value, (list, tuple, set)):
            for v in value:
                items.append((str(key), "" if v is None else str(v)))
        else:
            items.append((str(key), "" if value is None else str(value)))

    return sorted(items)


def _canonicalize_url(url: str, params: Any | None = None) -> str:
    """Return a canonical URL with sorted query params."""
    parsed = urlparse(url)
    query_items = list(parse_qsl(parsed.query, keep_blank_values=True))
    query_items.extend(_normalize_params(params))

    query = urlencode(sorted((str(k), str(v)) for k, v in query_items), doseq=True)
    return urlunparse(parsed._replace(query=query))


def _canonical_body(kwargs: dict[str, Any]) -> tuple[str, bytes]:
    """Return (body_kind, body_bytes) with deterministic encoding."""
    if "json" in kwargs and kwargs["json"] is not None:
        body_obj = kwargs["json"]
        body = json.dumps(body_obj, sort_keys=True, separators=(",", ":"), default=str)
        return "json", body.encode("utf-8")

    if "data" in kwargs and kwargs["data"] is not None:
        data = kwargs["data"]
        if isinstance(data, (bytes, bytearray)):
            return "data", bytes(data)
        if isinstance(data, str):
            return "data", data.encode("utf-8")
        if isinstance(data, dict):
            encoded = urlencode(_normalize_params(data), doseq=True)
            return "data", encoded.encode("utf-8")
        return "data", str(data).encode("utf-8")

    return "none", b""


def _request_hash(method: str, url: str, body_kind: str, body: bytes) -> str:
    """
    Produce a stable SHA-256 key for a given HTTP request.

    The hash covers method + canonical URL + body kind + body bytes so
    that two requests to the same endpoint with the same payload always
    map to the same fixture file, regardless of header ordering or timing.
    """
    payload = b"".join(
        (
            method.upper().encode("utf-8"),
            b"\0",
            url.encode("utf-8"),
            b"\0",
            body_kind.encode("utf-8"),
            b"\0",
            body,
        )
    )
    return content_hash(payload)


# ---------------------------------------------------------------------------
# APISimulator
# ---------------------------------------------------------------------------


class MissingFixtureError(Exception):
    """
    Raised in REPLAY mode when no fixture file exists for a request.

    This is a hard failure -- CI must never silently fall through to
    the network.
    """


class APISimulator:
    """
    Transparent HTTP interceptor for connector testing.

    Usage as a context manager::

        simulator = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=Path("tests/fabric/connectors/fixtures"),
            connector_id="worldbank.wdi",
            dataset_id="gdp",
        )
        async with simulator:
            result = await connector.fetch(handle, request)
            # ^^^ all HTTP calls served from fixtures

    Parameters
    ----------
    mode : SimulatorMode
        Operating mode (REPLAY / RECORD / SYNTHETIC).
    fixture_root : Path
        Root directory where fixture JSON files live.
    connector_id : str
        Logical connector identifier (used to namespace fixtures).
    dataset_id : str | None
        Logical dataset identifier for fixture namespacing.
    schema : DataSchema | None
        Required only in SYNTHETIC mode -- the schema used to generate
        random payloads.
    """

    def __init__(
        self,
        mode: SimulatorMode = SimulatorMode.REPLAY,
        fixture_root: Path | None = None,
        connector_id: str = "unknown",
        dataset_id: str | None = None,
        schema: Any | None = None,
    ) -> None:
        self.mode = mode
        self.fixture_root = fixture_root or Path("tests/fabric/connectors/fixtures")
        self.connector_id = connector_id
        self.dataset_id = dataset_id or "unknown"
        self.schema = schema

        # Internal call log for assertion helpers
        self._call_log: list[dict[str, Any]] = []
        # Patch handle -- assigned in __aenter__
        self._patch: Any = None
        # Original aiohttp request method (set in __aenter__)
        self._orig_request: Any = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "APISimulator":
        """
        Monkey-patch aiohttp.ClientSession to route through the simulator.

        We replace the _request method on the session class so that
        every session.get(), session.post() etc. hits our handler
        instead of the real network stack.
        """
        import aiohttp  # local import to avoid hard dependency at module import

        # Preserve the original method to avoid recursion in RECORD mode
        self._orig_request = aiohttp.ClientSession._request

        self._patch = patch(
            "aiohttp.ClientSession._request",
            new=self._handle_request,
        )
        self._patch.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Remove the patch and restore normal aiohttp behaviour."""
        if self._patch:
            self._patch.stop()
            self._patch = None

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    async def _handle_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        """
        Central dispatcher -- routes to the appropriate mode handler.

        Logs every call for later assertion in tests.
        """
        body_kind, body_bytes = _canonical_body(kwargs)
        canonical_url = _canonicalize_url(str(url), kwargs.get("params"))
        req_hash = _request_hash(method, canonical_url, body_kind, body_bytes)

        self._call_log.append({
            "method": method,
            "url": canonical_url,
            "hash": req_hash,
            "timestamp": time.monotonic(),
        })

        match self.mode:
            case SimulatorMode.REPLAY:
                return await self._replay(method, canonical_url, req_hash)
            case SimulatorMode.RECORD:
                return await self._record(method, canonical_url, req_hash, **kwargs)
            case SimulatorMode.SYNTHETIC:
                return self._synthetic(method, canonical_url, req_hash)
            case _:  # pragma: no cover
                raise ValueError(f"Unknown simulator mode: {self.mode}")

    # ------------------------------------------------------------------
    # REPLAY mode
    # ------------------------------------------------------------------

    def _fixture_path(self, req_hash: str) -> Path:
        """Resolve the fixture file path for a given request hash."""
        return self.fixture_root / self.connector_id / self.dataset_id / f"{req_hash}.json"

    async def _replay(self, method: str, url: str, req_hash: str) -> Any:
        """
        Serve a response from a pre-recorded fixture.

        Raises MissingFixtureError if the fixture does not exist --
        this is the CI safety net that prevents live network access.
        """
        path = self._fixture_path(req_hash)
        if not path.exists():
            raise MissingFixtureError(
                f"No fixture found for {method} {url}\n"
                f"  Expected at: {path}\n"
                f"  Request hash: {req_hash}\n"
                f"  Run with --record-mode to capture this response."
            )

        fixture = SimulatorFixture.read(path)
        return _MockResponse(
            status=fixture.status_code,
            headers=fixture.headers,
            body=fixture.body_bytes,
        )

    # ------------------------------------------------------------------
    # RECORD mode
    # ------------------------------------------------------------------

    async def _record(self, method: str, url: str, req_hash: str, **kwargs: Any) -> Any:
        """
        Proxy the real request, capture the response, and write a fixture.

        This intentionally makes a real network call. It should only
        be activated via --record-mode or explicit construction.
        """
        import aiohttp  # real import -- only hit in RECORD mode

        if self._orig_request is None:
            raise RuntimeError("APISimulator missing original _request; did you enter context?")

        async with aiohttp.ClientSession() as session:
            async with self._orig_request(session, method, url, **kwargs) as resp:
                body_bytes = await resp.read()
                headers = dict(resp.headers)
                status = resp.status

        # Persist fixture
        fixture = SimulatorFixture(
            status_code=status,
            headers=headers,
            body=base64.b64encode(body_bytes).decode(),
            captured_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            request_url=url,
            request_method=method,
            request_hash=req_hash,
            connector_id=self.connector_id,
            dataset_id=self.dataset_id,
        )
        fixture.write(self._fixture_path(req_hash))

        return _MockResponse(status=status, headers=headers, body=body_bytes)

    # ------------------------------------------------------------------
    # SYNTHETIC mode
    # ------------------------------------------------------------------

    def _synthetic(self, method: str, url: str, req_hash: str) -> Any:
        """
        Generate a random response body that conforms to self.schema.

        Delegates to generate_dataframe_for_schema() from the contracts
        module, then serialises to JSON.
        """
        if self.schema is None:
            raise ValueError(
                "SYNTHETIC mode requires a DataSchema. "
                "Pass schema= to APISimulator()."
            )

        from polisyos.fabric.connectors.testing.contracts import (
            generate_dataframe_for_schema,
        )

        df = generate_dataframe_for_schema(self.schema, num_rows=100)
        body = df.to_json(orient="records").encode()

        return _MockResponse(
            status=200,
            headers={"Content-Type": "application/json"},
            body=body,
        )

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Number of HTTP requests intercepted since entering context."""
        return len(self._call_log)

    @property
    def call_log(self) -> list[dict[str, Any]]:
        """Ordered log of every intercepted request."""
        return list(self._call_log)

    def assert_called_with(self, url: str, method: str = "GET") -> None:
        """Assert that at least one call matches the given URL and method."""
        matches = [
            c for c in self._call_log
            if c["url"] == url and c["method"].upper() == method.upper()
        ]
        assert matches, (
            f"APISimulator: no call to {method} {url} was recorded.\n"
            f"Actual calls: {[f'{c["method"]} {c["url"]}' for c in self._call_log]}"
        )


# ---------------------------------------------------------------------------
# Lightweight mock response (duck-types aiohttp.ClientResponse)
# ---------------------------------------------------------------------------


class _MockResponse:
    """
    Minimal response object that satisfies aiohttp.ClientResponse duck-typing.

    Connector code typically calls .status, .headers, .read(), and .json()
    on the response. We implement all four.
    """

    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self._body = body

    async def read(self) -> bytes:
        return self._body

    async def json(self, **kwargs: Any) -> Any:
        return json.loads(self._body.decode("utf-8"))

    async def text(self, **kwargs: Any) -> str:
        return self._body.decode("utf-8")

    async def __aenter__(self) -> "_MockResponse":
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass
