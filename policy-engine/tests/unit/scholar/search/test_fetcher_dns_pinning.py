"""Behavioral controls for DNS-to-socket destination binding."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import ssl
import threading
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from polisyos.core.contracts.scholar import SourceSpec
from polisyos.scholar.discover import fetch_url as fetch_seed_url
from polisyos.scholar.discover import transport
from polisyos.scholar.orchestrator.errors import ScholarAcquireError
from polisyos.scholar.search import fetch_open_page, security
from polisyos.scholar.search.models import SearchConstraints


@pytest.fixture(autouse=True)
def _direct_test_environment(monkeypatch):
    """Keep route selection explicit in tests that exercise the direct transport."""
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})


def _addrinfo(address: str, port: int, family: int = socket.AF_INET):
    sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)]


def test_resolved_target_uses_scheme_default_ports_and_keeps_numeric_addresses(monkeypatch):
    calls: list[tuple[str, int]] = []

    def resolver(host, port, **kwargs):
        calls.append((host, port))
        assert kwargs["type"] == socket.SOCK_STREAM
        assert kwargs["proto"] == socket.IPPROTO_TCP
        return _addrinfo("93.184.216.34", port)

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)
    http_target = security._resolve_fetch_target("http://example.test/path", SearchConstraints())
    https_target = security._resolve_fetch_target("https://example.test/path", SearchConstraints())

    assert http_target.port == 80
    assert https_target.port == 443
    assert [item.address for item in http_target.addresses] == ["93.184.216.34"]
    assert [item.address for item in https_target.addresses] == ["93.184.216.34"]
    assert calls == [("example.test", 80), ("example.test", 443)]


def test_resolved_target_retains_private_address_only_under_explicit_policy(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("127.0.0.1", port),
    )

    target = security._resolve_fetch_target(
        "http://fixture.test/data",
        SearchConstraints(allowed_domains=["fixture.test"], allow_private_networks=True),
    )

    assert target.addresses[0].address == "127.0.0.1"
    assert target.port == 80


def test_resolved_target_refuses_mixed_public_and_private_answers(monkeypatch):
    def resolver(host, port, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port)),
        ]

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)

    with pytest.raises(ValueError, match="private network address blocked"):
        security._resolve_fetch_target("http://example.test/data", SearchConstraints())


def test_resolved_target_refuses_empty_or_malformed_address_set(monkeypatch):
    monkeypatch.setattr(security.socket, "getaddrinfo", lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="no TCP addresses"):
        security._resolve_fetch_target("http://example.test/data", SearchConstraints())

    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("not-an-ip", port))
        ],
    )
    with pytest.raises(ValueError, match="non-numeric address"):
        security._resolve_fetch_target("http://example.test/data", SearchConstraints())


def test_resolved_target_refuses_mismatched_resolver_port(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("93.184.216.34", port + 1),
    )

    with pytest.raises(ValueError, match="mismatched port"):
        security._resolve_fetch_target("http://example.test/data", SearchConstraints())


def test_resolved_target_refuses_address_family_mismatch(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("2001:4860:4860::8888", port),
            )
        ],
    )

    with pytest.raises(ValueError, match="address-family mismatch"):
        security._resolve_fetch_target("http://example.test/data", SearchConstraints())


def test_pinned_connection_dials_only_selected_numeric_address_and_checks_peer(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.35", port)),
        ],
    )
    target = security._resolve_fetch_target("http://example.test:8080/data", SearchConstraints())
    connects: list[tuple[str, int]] = []

    class FakeSocket:
        def __init__(self, family, socket_type, protocol):
            assert family == socket.AF_INET
            assert socket_type == socket.SOCK_STREAM
            assert protocol == socket.IPPROTO_TCP
            self.peer = None
            self.closed = False

        def settimeout(self, timeout):
            assert timeout is None or timeout >= 0

        def bind(self, address):
            assert address

        def connect(self, address):
            connects.append(address)
            self.peer = address

        def getpeername(self):
            return self.peer

        def setsockopt(self, *args):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(transport.socket, "socket", FakeSocket)
    connection = transport._PinnedHTTPConnection(
        "example.test:8080",
        target=target,
        timeout=2.0,
    )
    connection.connect()

    assert connects == [("93.184.216.34", 8080)]
    assert connection.sock is not None
    assert connection.sock.getpeername() == ("93.184.216.34", 8080)
    connection.close()


def test_pinned_connection_refuses_unexpected_peer_without_retry(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.35", port)),
        ],
    )
    target = security._resolve_fetch_target("http://example.test:8080/data", SearchConstraints())
    attempted: list[tuple[str, int]] = []

    class WrongPeerSocket:
        def __init__(self, family, socket_type, protocol):
            self.closed = False

        def settimeout(self, timeout):
            return None

        def connect(self, address):
            attempted.append(address)

        def getpeername(self):
            return ("93.184.216.35", 8080)

        def setsockopt(self, *args):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(transport.socket, "socket", WrongPeerSocket)
    connection = transport._PinnedHTTPConnection("example.test:8080", target=target, timeout=2.0)

    with pytest.raises(transport._PinnedPeerMismatchError, match="differs from the selected"):
        connection.connect()
    assert attempted == [("93.184.216.34", 8080)]


def test_pinned_connection_refuses_unexpected_peer_port(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("93.184.216.34", port),
    )
    target = security._resolve_fetch_target("http://example.test:8080/data", SearchConstraints())

    class WrongPortSocket:
        def __init__(self, family, socket_type, protocol):
            self.closed = False

        def settimeout(self, timeout):
            return None

        def connect(self, address):
            return None

        def getpeername(self):
            return ("93.184.216.34", 8081)

        def setsockopt(self, *args):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(transport.socket, "socket", WrongPortSocket)
    connection = transport._PinnedHTTPConnection("example.test:8080", target=target, timeout=2.0)

    with pytest.raises(transport._PinnedPeerMismatchError, match="peer port differs"):
        connection.connect()


def test_pinned_connection_refuses_unexpected_ipv6_scope(monkeypatch):
    address = "2001:4860:4860::8888"
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port, 0, 1))
        ],
    )
    target = security._resolve_fetch_target(f"http://[{address}]:8080/data", SearchConstraints())

    class WrongScopeSocket:
        def __init__(self, family, socket_type, protocol):
            self.closed = False

        def settimeout(self, timeout):
            return None

        def connect(self, sockaddr):
            return None

        def getpeername(self):
            return (address, 8080, 0, 2)

        def setsockopt(self, *args):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(transport.socket, "socket", WrongScopeSocket)
    connection = transport._PinnedHTTPConnection(
        f"[{address}]:8080",
        target=target,
        timeout=2.0,
    )

    with pytest.raises(transport._PinnedPeerMismatchError, match="peer scope differs"):
        connection.connect()


def test_https_connection_keeps_origin_hostname_for_sni(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("93.184.216.34", port),
    )
    target = security._resolve_fetch_target(
        "https://origin.example.test/report", SearchConstraints()
    )
    observed_server_names: list[str | None] = []

    class FakeSocket:
        def __init__(self, family, socket_type, protocol):
            self.peer = None

        def settimeout(self, timeout):
            return None

        def connect(self, address):
            self.peer = address

        def getpeername(self):
            return self.peer

        def setsockopt(self, *args):
            return None

        def close(self):
            return None

    class FakeSSLContext:
        check_hostname = True

        def wrap_socket(self, sock, *, server_hostname):
            observed_server_names.append(server_hostname)
            return sock

    monkeypatch.setattr(transport.socket, "socket", FakeSocket)
    connection = transport._PinnedHTTPSConnection(
        "origin.example.test",
        target=target,
        timeout=2.0,
        context=FakeSSLContext(),
    )
    connection.connect()

    assert connection.host == "origin.example.test"
    assert observed_server_names == ["origin.example.test"]
    connection.close()


@pytest.mark.integration
def test_real_local_tls_keeps_hostname_and_verifies_connected_peer(monkeypatch, tmp_path):
    host = "tls.example.test"
    body = b"verified local TLS"
    received: list[tuple[str | None, str, str]] = []
    server_names: list[str | None] = []
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(UTC).replace(tzinfo=None)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    certificate_path = Path(tmp_path) / "fixture-cert.pem"
    key_path = Path(tmp_path) / "fixture-key.pem"
    certificate_path.write_bytes(certificate_pem)
    key_path.write_bytes(key_pem)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.headers.get("Host"), self.path, self.client_address[0]))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            del fmt, args

    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(str(certificate_path), str(key_path))
    server_context.set_servername_callback(
        lambda _socket, server_name, _context: server_names.append(server_name)
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    client_context = ssl.create_default_context()
    client_context.load_verify_locations(cadata=certificate_pem.decode("ascii"))
    monkeypatch.setattr(
        ssl,
        "_create_default_https_context",
        lambda *args, **kwargs: client_context,
    )
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda resolver_host, port, **kwargs: _addrinfo("127.0.0.1", port)
        if resolver_host == host
        else [],
    )
    connected_peers: list[tuple[str, int]] = []
    original_connect = transport._PinnedHTTPSConnection.connect

    def record_connected_peer(connection):
        original_connect(connection)
        assert connection.sock is not None
        connected_peers.append(connection.sock.getpeername()[:2])

    monkeypatch.setattr(transport._PinnedHTTPSConnection, "connect", record_connected_peer)
    port = server.server_port
    url = f"https://{host}:{port}/verified"
    try:
        result = transport.fetch_raw(
            url,
            constraints=SearchConstraints(
                allowed_domains=[host],
                allow_private_networks=True,
            ),
            timeout_s=3,
            user_agent="la024-tls-test",
            max_bytes=1000,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.raw_bytes == body
    assert result.final_url == url
    assert received == [(f"{host}:{port}", "/verified", "127.0.0.1")]
    assert connected_peers == [("127.0.0.1", port)]
    assert server_names == [host]
    print(
        "OBSERVED_TLS "
        + json.dumps(
            {
                "sni": server_names,
                "origin_hostname": host,
                "host_header": received[0][0],
                "server_peer": received[0][2],
                "client_socket_peer": connected_peers[0],
                "certificate_san_hostname": host,
                "certificate_verification": "passed",
                "certificate_pem_sha256": hashlib.sha256(certificate_pem).hexdigest(),
                "final_url": result.final_url,
            },
            sort_keys=True,
        )
    )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("adapter", ["seed", "search"])
async def test_both_public_adapters_bind_each_redirect_hop_to_resolved_peer(monkeypatch, adapter):
    body = b"<html><head><title>Bound</title></head><body>Controlled fixture.</body></html>"
    received: list[tuple[str | None, str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.headers.get("Host"), self.path, self.client_address[0]))
            if self.path == "/start":
                self.send_response(302)
                self.send_header(
                    "Location", f"http://second.example:{self.server.server_port}/finish"
                )
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("ETag", "fixture-etag")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            del fmt, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    resolver_calls: list[tuple[str, int]] = []
    resolver_answers: list[tuple[str, int, str, int]] = []
    answers_per_host: dict[str, int] = defaultdict(int)

    def resolver(host, port, **kwargs):
        resolver_calls.append((host, port))
        answer_index = answers_per_host[host]
        answers_per_host[host] += 1
        address = "127.0.0.1" if answer_index == 0 else "127.0.0.2"
        resolver_answers.append((host, port, address, answer_index))
        return _addrinfo(address, port)

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)
    port = server.server_port
    first_url = f"http://first.example:{port}/start"
    constraints = SearchConstraints(
        allowed_domains=["first.example", "second.example"],
        allow_private_networks=True,
    )
    try:
        if adapter == "seed":
            source = SourceSpec(
                kind="url",
                canonical_url=first_url,
                license="public",
                url=first_url,
            )
            result = fetch_seed_url(
                source,
                timeout_s=3,
                user_agent="la024-test",
                max_bytes=10_000,
                constraints=constraints,
            )
            assert result.raw_bytes == body
            assert result.mime == "text/html"
        else:
            result = await fetch_open_page(
                first_url,
                constraints=constraints,
                timeout_s=3,
                max_bytes=10_000,
            )
            assert result.status == "ok"
            assert result.final_url == f"http://second.example:{port}/finish"
            assert result.redirect_chain == [f"http://second.example:{port}/finish"]
            assert result.content_sha256 == hashlib.sha256(body).hexdigest()
            assert result.etag == "fixture-etag"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert received == [
        (f"first.example:{port}", "/start", "127.0.0.1"),
        (f"second.example:{port}", "/finish", "127.0.0.1"),
    ]
    assert resolver_calls == [("first.example", port), ("second.example", port)]
    print(
        "OBSERVED_REDIRECT "
        + json.dumps(
            {
                "adapter": adapter,
                "server_requests": received,
                "resolver_answers": resolver_answers,
                "would_return_on_second_lookup": "127.0.0.2",
                "resolver_calls_per_hop": resolver_calls,
                "redirect_chain": [f"http://second.example:{port}/finish"],
                "removal_falsifier": "each hop would resolve to 127.0.0.2 on a second lookup; successful requests reached the captured 127.0.0.1 peer with one resolution per hop",
            },
            sort_keys=True,
        )
    )


def test_private_redirect_target_is_refused_before_a_second_connection(monkeypatch):
    def resolver(host, port, **kwargs):
        address = "93.184.216.34" if host == "first.example" else "127.0.0.1"
        return _addrinfo(address, port)

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)
    constraints = SearchConstraints(allowed_domains=["first.example", "second.example"])
    initial = security._resolve_fetch_target("http://first.example/path", constraints)
    redirect_chain: list[str] = []
    current_target = [initial]
    handler = transport._ValidatingRedirectHandler(
        constraints=constraints,
        redirect_chain=redirect_chain,
        current_target=current_target,
    )
    request = urllib.request.Request(initial.request_url)  # noqa: S310
    setattr(request, transport._TARGET_ATTRIBUTE, initial)

    with pytest.raises(ValueError, match="private network address blocked"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://second.example/private",
        )

    assert redirect_chain == []
    assert current_target == [initial]


def test_configured_proxy_route_fails_closed_before_opener_creation(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("93.184.216.34", port),
    )
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": "http://proxy.invalid"})
    proxy_bypass_hosts: list[str] = []

    def proxy_bypass(host):
        proxy_bypass_hosts.append(host)
        return False

    monkeypatch.setattr(urllib.request, "proxy_bypass", proxy_bypass)
    opener_created = False

    def build_opener(*handlers):
        nonlocal opener_created
        opener_created = True
        return None

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)

    with pytest.raises(transport._UnsupportedProxyRouteError, match="proxy route is unsupported"):
        transport.fetch_raw(
            "http://example.test/report",
            constraints=SearchConstraints(),
            timeout_s=2,
            user_agent="test",
            max_bytes=100,
        )
    assert opener_created is False
    assert proxy_bypass_hosts == ["example.test:80"]


def test_explicit_proxy_bypass_keeps_direct_route_available(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("93.184.216.34", port),
    )
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": "http://proxy.invalid"})
    proxy_bypass_hosts: list[str] = []

    def proxy_bypass(host):
        proxy_bypass_hosts.append(host)
        return True

    monkeypatch.setattr(urllib.request, "proxy_bypass", proxy_bypass)
    target = security._resolve_fetch_target("http://example.test/report", SearchConstraints())

    transport._assert_direct_proxy_route(target)

    assert proxy_bypass_hosts == ["example.test:80"]


def test_explicit_port_zero_is_preserved_in_resolved_target(monkeypatch):
    calls: list[tuple[str, int]] = []

    def resolver(host, port, **kwargs):
        calls.append((host, port))
        return _addrinfo("93.184.216.34", port)

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)
    target = security._resolve_fetch_target("http://example.test:0/path", SearchConstraints())

    assert target.port == 0
    assert target.addresses[0].sockaddr == ("93.184.216.34", 0)
    assert calls == [("example.test", 0)]


def test_resolver_oserror_refuses_before_opener_creation(monkeypatch):
    resolver_error = socket.gaierror(socket.EAI_NONAME, "controlled resolver failure")

    def resolver(*args, **kwargs):
        raise resolver_error

    def unexpected_opener(*handlers):
        pytest.fail("transport opener must not be created after resolver refusal")

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)
    monkeypatch.setattr(urllib.request, "build_opener", unexpected_opener)

    with pytest.raises(ValueError, match="fetch hostname could not be resolved") as exc_info:
        transport.fetch_raw(
            "https://unresolved.example.test/path",
            constraints=SearchConstraints(),
            timeout_s=2,
            user_agent="la024-test",
            max_bytes=100,
        )

    assert exc_info.value.__cause__ is resolver_error


@pytest.mark.parametrize(
    "address",
    [
        "100.64.0.1",
        "10.0.0.1",
        "127.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "240.0.0.1",
        str(ipaddress.IPv4Address(0)),
        "192.0.2.1",
        "255.255.255.255",
        "fd00::1",
        "::1",
        "fe80::1",
        "ff02::1",
        "::",
        "2001:db8::1",
    ],
)
def test_resolved_target_rejects_non_global_answers_without_explicit_policy(monkeypatch, address):
    """Reject shared, private, special-purpose, and non-global DNS answers by default."""
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo(address, port, family),
    )

    with pytest.raises(ValueError, match="private network address blocked"):
        security._resolve_fetch_target("http://fixture.test/data", SearchConstraints())


def test_resolved_target_refuses_mixed_global_and_shared_answers(monkeypatch):
    """A shared-space DNS answer cannot ride alongside an approved global answer."""
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            *_addrinfo("93.184.216.34", port),
            *_addrinfo("100.64.0.1", port),
        ],
    )

    with pytest.raises(ValueError, match="private network address blocked"):
        security._resolve_fetch_target("http://fixture.test/data", SearchConstraints())


@pytest.mark.parametrize(
    ("address", "family"),
    [
        ("93.184.216.34", socket.AF_INET),
        ("2606:4700:4700::1111", socket.AF_INET6),
    ],
)
def test_resolved_target_accepts_global_ipv4_and_ipv6(monkeypatch, address, family):
    """Keep globally routable IPv4 and IPv6 resolver answers available."""
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo(address, port, family),
    )

    target = security._resolve_fetch_target("https://fixture.test/data", SearchConstraints())

    assert [item.address for item in target.addresses] == [address]


def test_explicit_private_network_policy_still_allows_shared_space(monkeypatch):
    """The explicit network exception composes with default global-only validation."""
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda host, port, **kwargs: _addrinfo("100.64.0.1", port),
    )

    target = security._resolve_fetch_target(
        "http://fixture.test/data",
        SearchConstraints(allow_private_networks=True),
    )

    assert [item.address for item in target.addresses] == ["100.64.0.1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", ["seed", "search"])
async def test_both_public_adapters_refuse_mixed_non_global_redirect_answers(monkeypatch, adapter):
    """A mixed public/shared-space DNS set is refused at every public-adapter hop."""
    resolver_calls: list[tuple[str, int]] = []

    def resolver(host, port, **kwargs):
        del kwargs
        resolver_calls.append((host, port))
        if host == "first.example":
            return _addrinfo("93.184.216.34", port)
        return [
            *_addrinfo("93.184.216.35", port),
            *_addrinfo("100.64.0.1", port),
        ]

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)

    class RedirectOnlyOpener:
        def __init__(self, handlers):
            self._redirect_handler = next(
                handler
                for handler in handlers
                if isinstance(handler, transport._ValidatingRedirectHandler)
            )

        def open(self, request, timeout):
            del timeout
            self._redirect_handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "http://second.example/next",
            )
            pytest.fail("mixed non-global redirect answer must be refused")

    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *handlers: RedirectOnlyOpener(handlers),
    )
    constraints = SearchConstraints(allowed_domains=["first.example", "second.example"])
    first_url = "http://first.example/start"

    if adapter == "seed":
        source = SourceSpec(
            kind="url",
            canonical_url=first_url,
            license="public",
            url=first_url,
        )
        with pytest.raises(
            ScholarAcquireError,
            match="blocked URL fetch: private network address blocked",
        ):
            fetch_seed_url(
                source,
                timeout_s=2,
                user_agent="la024-test",
                max_bytes=100,
                constraints=constraints,
            )
    else:
        result = await fetch_open_page(
            first_url,
            constraints=constraints,
            timeout_s=2,
            max_bytes=100,
        )
        assert result.status == "error"
        assert "private network address blocked" in (result.error or "")

    assert resolver_calls == [("first.example", 80), ("second.example", 80)]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("adapter", ["transport", "seed", "search"])
async def test_redirect_cycle_is_bounded_through_shared_transport_and_adapters(
    monkeypatch, adapter
):
    """A controlled A-to-B-to-A cycle is refused by the shared redirect lifecycle."""
    requests: list[tuple[str | None, str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.headers.get("Host"), self.path, self.client_address[0]))
            next_path = "/b" if self.path == "/a" else "/a"
            self.send_response(302)
            self.send_header(
                "Location", f"http://cycle.example:{self.server.server_port}{next_path}"
            )
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, fmt, *args):
            del fmt, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    resolver_calls: list[tuple[str, int]] = []
    port = server.server_port

    def resolver(host, resolved_port, **kwargs):
        del kwargs
        resolver_calls.append((host, resolved_port))
        assert host == "cycle.example"
        assert resolved_port == port
        return _addrinfo("127.0.0.1", resolved_port)

    monkeypatch.setattr(security.socket, "getaddrinfo", resolver)
    first_url = f"http://cycle.example:{port}/a"
    constraints = SearchConstraints(
        allowed_domains=["cycle.example"],
        allow_private_networks=True,
    )
    caught: BaseException | None = None
    try:
        if adapter == "transport":
            try:
                transport.fetch_raw(
                    first_url,
                    constraints=constraints,
                    timeout_s=3,
                    user_agent="la024-loop-test",
                    max_bytes=1000,
                )
            except urllib.error.HTTPError as exc:
                caught = exc
            else:
                pytest.fail("shared transport must refuse a repeated redirect cycle")
        elif adapter == "seed":
            source = SourceSpec(
                kind="url",
                canonical_url=first_url,
                license="public",
                url=first_url,
            )
            with pytest.raises(ScholarAcquireError) as exc_info:
                fetch_seed_url(
                    source,
                    timeout_s=3,
                    user_agent="la024-loop-test",
                    max_bytes=1000,
                    constraints=constraints,
                )
            caught = exc_info.value.__cause__
        else:
            result = await fetch_open_page(
                first_url,
                constraints=constraints,
                timeout_s=3,
                max_bytes=1000,
            )
            assert result.status == "error"
            assert "infinite loop" in (result.error or "").lower()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    if adapter != "search":
        assert isinstance(caught, urllib.error.HTTPError)
        assert caught.code == 302
        assert "infinite loop" in str(caught).lower()
    max_redirects = transport._ValidatingRedirectHandler.max_redirections
    assert 1 < len(requests) <= max_redirects
    assert all(path in {"/a", "/b"} for _host, path, _peer in requests)
    assert [path for _host, path, _peer in requests][:2] == ["/a", "/b"]
    assert all(host == f"cycle.example:{port}" for host, _path, _peer in requests)
    assert all(peer == "127.0.0.1" for _host, _path, peer in requests)
    assert all(call == ("cycle.example", port) for call in resolver_calls)
    assert len(resolver_calls) <= max_redirects + 1
    print(
        "OBSERVED_REDIRECT_CYCLE "
        + json.dumps(
            {
                "entrypoint": adapter,
                "cycle": ["/a", "/b", "/a"],
                "request_count_before_refusal": len(requests),
                "resolver_call_count_including_refused_hop": len(resolver_calls),
                "request_paths": [path for _host, path, _peer in requests],
                "origin_host_headers": [host for host, _path, _peer in requests],
                "connected_peers": [peer for _host, _path, peer in requests],
                "stdlib_redirect_limit": max_redirects,
                "refusal": "urllib HTTP 302 infinite redirect loop",
                "removal_falsifier": "removing the inherited redirect-loop check would make this controlled A/B cycle continue beyond the configured bound",
            },
            sort_keys=True,
        ),
        flush=True,
    )
