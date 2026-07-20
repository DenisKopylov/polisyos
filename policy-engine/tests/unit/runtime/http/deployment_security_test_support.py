"""Loopback trust endpoints for deployment-security integration tests."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any, cast

from jwt.algorithms import RSAAlgorithm

if TYPE_CHECKING:
    from collections.abc import Callable


class LocalJWKSStub:
    """Serve one RSA public key through a real JWKS retrieval path."""

    def __init__(
        self,
        private_key: Any,
        *,
        key_id: str = "identity-2026-07",
        on_request: Callable[[], None] | None = None,
    ) -> None:
        public_jwk = RSAAlgorithm.to_jwk(
            private_key.public_key(),
            as_dict=True,
        )
        public_jwk.update({"alg": "RS256", "kid": key_id, "use": "sig"})
        self._payload = {"keys": [public_jwk]}
        self._on_request = on_request
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self) -> str:
        """Start the loopback JWKS endpoint and return its document URI."""
        payload = self._payload
        on_request = self._on_request

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
                if self.path != "/.well-known/jwks.json":
                    self.send_error(404)
                    return
                if on_request is not None:
                    on_request()
                response = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = Thread(
            target=server.serve_forever,
            name="ds20-local-jwks",
            daemon=True,
        )
        thread.start()
        self._server = server
        self._thread = thread
        host, port = cast("tuple[str, int]", server.server_address)
        return f"http://{host}:{port}/.well-known/jwks.json"

    def close(self) -> None:
        """Stop the endpoint and release its listening socket."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


__all__ = ["LocalJWKSStub"]
