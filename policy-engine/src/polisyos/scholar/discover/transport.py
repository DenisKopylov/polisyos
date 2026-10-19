"""Shared redirect-aware raw HTTP transport for Scholar adapters."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl
    from collections.abc import Callable, Mapping
    from urllib.response import addinfourl

    from polisyos.scholar.search.models import SearchConstraints
    from polisyos.scholar.search.security import _ResolvedFetchTarget, _ResolvedSocketAddress


_TARGET_ATTRIBUTE = "_polisyos_resolved_fetch_target"


class RawFetchSizeError(ValueError):
    """Raised when a raw response exceeds the caller's byte budget."""

    def __init__(self, *, observed_bytes: int, max_bytes: int) -> None:
        super().__init__(f"raw payload exceeds max_bytes={max_bytes}")
        self.observed_bytes = observed_bytes
        self.max_bytes = max_bytes


class _UnsupportedProxyRouteError(ValueError):
    """Raised when the configured proxy route cannot prove its destination binding."""


@dataclass(frozen=True, slots=True)
class RawFetchResult:
    """Raw response bytes and the metadata needed by typed result adapters."""

    raw_bytes: bytes
    final_url: str
    content_type: str
    headers: dict[str, str]
    redirect_chain: list[str]


def fetch_raw(
    url: str,
    *,
    constraints: SearchConstraints,
    timeout_s: float,
    user_agent: str,
    max_bytes: int | None,
) -> RawFetchResult:
    """Fetch through one shared opener, binding each request hop to a numeric peer."""
    from polisyos.scholar.search.security import _resolve_fetch_target

    target = _resolve_fetch_target(url, constraints)
    return _fetch_raw_with_target(
        url,
        constraints=constraints,
        timeout_s=timeout_s,
        user_agent=user_agent,
        max_bytes=max_bytes,
        target=target,
    )


def _fetch_raw_with_target(
    url: str,
    *,
    constraints: SearchConstraints,
    timeout_s: float,
    user_agent: str,
    max_bytes: int | None,
    target: _ResolvedFetchTarget,
) -> RawFetchResult:
    """Fetch with a target already resolved by the calling adapter."""
    _assert_target_matches_request(target, url, constraints)
    _assert_direct_proxy_route(target)
    redirect_chain: list[str] = []
    current_target = [target]
    opener = urllib.request.build_opener(
        _ValidatingRedirectHandler(
            constraints=constraints,
            redirect_chain=redirect_chain,
            current_target=current_target,
        ),
        urllib.request.ProxyHandler({}),
        _PinnedHTTPHandler,
        _PinnedHTTPSHandler,
    )
    # The URL passed HTTP(S) and host-policy validation before Request creation.
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    setattr(request, _TARGET_ATTRIBUTE, target)
    with opener.open(request, timeout=timeout_s) as response:
        final_url = getattr(response, "url", url) or url
        if final_url != current_target[0].request_url:
            raise ValueError("final response URL did not match its validated request")
        raw_bytes = response.read(max_bytes + 1 if max_bytes is not None else -1)
        if max_bytes is not None and len(raw_bytes) > max_bytes:
            raise RawFetchSizeError(
                observed_bytes=len(raw_bytes),
                max_bytes=max_bytes,
            )
        headers = {str(key): str(value) for key, value in response.headers.items()}
        content_type = response.headers.get("Content-Type") or "application/octet-stream"
        return RawFetchResult(
            raw_bytes=raw_bytes,
            final_url=final_url,
            content_type=content_type,
            headers=headers,
            redirect_chain=list(redirect_chain),
        )


def _assert_target_matches_request(
    target: _ResolvedFetchTarget,
    url: str,
    constraints: SearchConstraints,
) -> None:
    signature = (
        tuple(constraints.allowed_domains),
        tuple(constraints.blocked_domains),
        constraints.allow_private_networks,
    )
    if target.request_url != url or target.constraints_signature != signature:
        raise ValueError("resolved fetch target does not match the request policy")


def _assert_direct_proxy_route(target: _ResolvedFetchTarget) -> None:
    proxies = urllib.request.getproxies()
    proxy = proxies.get(target.scheme) or proxies.get("all")
    if proxy is None:
        return
    proxy_host = (
        f"[{target.hostname}]:{target.port}"
        if ":" in target.hostname
        else f"{target.hostname}:{target.port}"
    )
    try:
        bypassed = urllib.request.proxy_bypass(proxy_host)
    except Exception as exc:
        raise _UnsupportedProxyRouteError(
            "proxy bypass could not be established for pinned fetch"
        ) from exc
    if not bypassed:
        raise _UnsupportedProxyRouteError(
            "configured proxy route is unsupported by the pinned direct transport"
        )


def _request_target(request: urllib.request.Request) -> _ResolvedFetchTarget:
    from polisyos.scholar.search.security import _ResolvedFetchTarget

    target = getattr(request, _TARGET_ATTRIBUTE, None)
    if not isinstance(target, _ResolvedFetchTarget) or target.request_url != request.full_url:
        raise urllib.error.URLError("request lacks a matching validated fetch target")
    return target


def _connection_factory(
    connection_type: type[http.client.HTTPConnection],
    request: urllib.request.Request,
) -> Callable[..., http.client.HTTPConnection]:
    target = _request_target(request)
    if connection_type is http.client.HTTPConnection:
        pinned_type: type[http.client.HTTPConnection] = _PinnedHTTPConnection
    else:
        pinned_type = _PinnedHTTPSConnection
    return partial(pinned_type, target=target)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, request: urllib.request.Request) -> addinfourl:
        return self.do_open(_connection_factory(http.client.HTTPConnection, request), request)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request: urllib.request.Request) -> addinfourl:
        return self.do_open(
            _connection_factory(http.client.HTTPSConnection, request),
            request,
            context=self._context,
        )


class _PinnedConnectionMixin:
    _target: _ResolvedFetchTarget
    _selected_address: _ResolvedSocketAddress | None
    host: str
    port: int
    timeout: float | None | object
    source_address: tuple[str, int] | None
    sock: socket.socket | None

    def _bind_validated_target(self, target: _ResolvedFetchTarget) -> None:
        self._target = target
        self._selected_address = None
        if self.host.lower() != target.hostname or self.port != target.port:
            raise ValueError("HTTP connection origin differs from its validated target")
        self._create_connection = self._create_pinned_connection

    def _create_pinned_connection(
        self,
        address: tuple[str, int],
        timeout: float | None | object = socket._GLOBAL_DEFAULT_TIMEOUT,
        source_address: tuple[str, int] | None = None,
    ) -> socket.socket:
        if address != (self._target.hostname, self._target.port):
            raise OSError("HTTP connection requested an unvalidated origin")

        effective_timeout = (
            socket.getdefaulttimeout() if timeout is socket._GLOBAL_DEFAULT_TIMEOUT else timeout
        )
        deadline = (
            time.monotonic() + effective_timeout
            if isinstance(effective_timeout, (int, float))
            else None
        )
        last_error: OSError | None = None
        for resolved in self._target.addresses:
            sock: socket.socket | None = None
            try:
                sock = socket.socket(resolved.family, resolved.socket_type, resolved.protocol)
                if deadline is not None:
                    sock.settimeout(max(0.0, deadline - time.monotonic()))
                elif effective_timeout is None:
                    sock.settimeout(None)
                if source_address is not None:
                    sock.bind(source_address)
                sock.connect(resolved.sockaddr)  # type: ignore[arg-type]
                self._assert_socket_peer(sock, resolved)
                self._selected_address = resolved
                return sock
            except OSError as exc:
                if sock is not None:
                    sock.close()
                if isinstance(exc, _PinnedPeerMismatchError):
                    raise
                last_error = exc
        if last_error is not None:
            raise OSError("could not connect to any approved fetch address") from last_error
        raise OSError("validated fetch target has no usable address")

    def _assert_socket_peer(
        self,
        sock: socket.socket,
        selected: _ResolvedSocketAddress,
    ) -> None:
        try:
            peer = sock.getpeername()
            actual_ip = ipaddress.ip_address(peer[0])
            selected_ip = ipaddress.ip_address(selected.address)
            selected_port = selected.sockaddr[1]
        except (OSError, ValueError, IndexError, TypeError) as exc:
            raise _PinnedPeerMismatchError("connected peer address could not be verified") from exc
        if actual_ip.version != selected_ip.version or actual_ip.packed != selected_ip.packed:
            raise _PinnedPeerMismatchError("connected peer differs from the selected address")
        if peer[1] != selected_port:
            raise _PinnedPeerMismatchError(
                "connected peer port differs from the selected destination"
            )
        if selected.family == socket.AF_INET6:
            try:
                expected_scope = selected.sockaddr[3]
                actual_scope = peer[3]
            except (IndexError, TypeError) as exc:
                raise _PinnedPeerMismatchError(
                    "connected IPv6 peer scope could not be verified"
                ) from exc
            if actual_scope != expected_scope:
                raise _PinnedPeerMismatchError(
                    "connected IPv6 peer scope differs from the selected destination"
                )

    def connect(self) -> None:
        super().connect()
        if self.sock is None or self._selected_address is None:
            raise _PinnedPeerMismatchError("connected socket has no selected target address")
        try:
            self._assert_socket_peer(self.sock, self._selected_address)
        except OSError:
            self.sock.close()
            self.sock = None
            raise


class _PinnedPeerMismatchError(OSError):
    """Raised when a connected socket does not match its selected numeric address."""


class _PinnedHTTPConnection(_PinnedConnectionMixin, http.client.HTTPConnection):
    def __init__(
        self,
        host: str,
        *,
        target: _ResolvedFetchTarget,
        port: int | None = None,
        timeout: float | None | object = socket._GLOBAL_DEFAULT_TIMEOUT,
        source_address: tuple[str, int] | None = None,
        blocksize: int = 8192,
    ) -> None:
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            source_address=source_address,
            blocksize=blocksize,
        )
        self._bind_validated_target(target)


class _PinnedHTTPSConnection(_PinnedConnectionMixin, http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        *,
        target: _ResolvedFetchTarget,
        port: int | None = None,
        timeout: float | None | object = socket._GLOBAL_DEFAULT_TIMEOUT,
        source_address: tuple[str, int] | None = None,
        context: ssl.SSLContext | None = None,
        blocksize: int = 8192,
    ) -> None:
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            source_address=source_address,
            context=context,
            blocksize=blocksize,
        )
        self._bind_validated_target(target)


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(
        self,
        *,
        constraints: SearchConstraints,
        redirect_chain: list[str],
        current_target: list[_ResolvedFetchTarget],
    ) -> None:
        super().__init__()
        self._constraints = constraints
        self._redirect_chain = redirect_chain
        self._current_target = current_target

    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:  # type: ignore[override]
        from polisyos.scholar.search.security import _resolve_fetch_target

        target = _resolve_fetch_target(newurl, self._constraints)
        _assert_direct_proxy_route(target)
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if redirected is not None:
            setattr(redirected, _TARGET_ATTRIBUTE, target)
            self._current_target[0] = target
        self._redirect_chain.append(newurl)
        return redirected


__all__ = [
    "RawFetchResult",
    "RawFetchSizeError",
    "fetch_raw",
]
