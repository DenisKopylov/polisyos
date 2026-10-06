from __future__ import annotations
import asyncio
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
import sys
import time
import zipfile
from email.message import Message
from pathlib import Path
from unittest.mock import patch

WHEEL = Path(sys.argv[1]).resolve()
SOURCE_ROOT = Path(sys.argv[2]).resolve()
DATA_ROOT = Path(sys.argv[3]).resolve()
MODULE_SOURCE = {
    'polisyos.scholar.fetch_contracts': 'src/polisyos/scholar/fetch_contracts.py',
    'polisyos.scholar.discover.transport': 'src/polisyos/scholar/discover/transport.py',
    'polisyos.scholar.discover.http_fetch': 'src/polisyos/scholar/discover/http_fetch.py',
    'polisyos.scholar.search.models': 'src/polisyos/scholar/search/models.py',
    'polisyos.scholar.search.cache': 'src/polisyos/scholar/search/cache.py',
    'polisyos.scholar.search.fetcher': 'src/polisyos/scholar/search/fetcher.py',
    'polisyos.scholar.search.providers': 'src/polisyos/scholar/search/providers.py',
    'polisyos.scholar.search.service': 'src/polisyos/scholar/search/service.py',
    'polisyos.scholar.search.security': 'src/polisyos/scholar/search/security.py',
    'polisyos.core.artifacts.store': 'src/polisyos/core/artifacts/store.py',
    'polisyos.core.artifacts.manifest': 'src/polisyos/core/artifacts/manifest.py',
    'polisyos.core.artifacts.write_contract': 'src/polisyos/core/artifacts/write_contract.py',
    'polisyos.core.canon': 'src/polisyos/core/canon/__init__.py',
    'polisyos.core.contracts.scholar': 'src/polisyos/core/contracts/scholar.py',
    'polisyos.scholar.types': 'src/polisyos/scholar/types.py',
    'polisyos.fabric.docs': 'src/polisyos/fabric/docs/__init__.py',
}
import polisyos.scholar.fetch_contracts as fetch_contracts
import polisyos.scholar.discover.transport as transport
import polisyos.scholar.discover.http_fetch as http_fetch
import polisyos.scholar.search.models as models
import polisyos.scholar.search.cache as cache_module
import polisyos.scholar.search.fetcher as fetcher
import polisyos.scholar.search.providers as providers
import polisyos.scholar.search.service as service_module
import polisyos.scholar.search.security as security
import polisyos.core.artifacts.store as artifact_store
import polisyos.core.artifacts.manifest as artifact_manifest
import polisyos.core.artifacts.write_contract as write_contract
import polisyos.core.canon as canon
import polisyos.core.contracts.scholar as scholar_contracts
import polisyos.scholar.types as scholar_types
import polisyos.fabric.docs as fabric_docs
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.scholar import SourceSpec
from polisyos.scholar.discover.http_fetch import fetch_url
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.fetcher import fetch_open_page
from polisyos.scholar.search.models import (
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SearchBudgetControls,
    SearchConstraints,
    WebEvidenceBundle,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def module_inventory() -> tuple[dict[str, dict[str, str]], Path]:
    modules = {name: sys.modules[name] for name in MODULE_SOURCE}
    site = next(Path(p).resolve() for p in sys.path if p.endswith('site-packages'))
    inventory: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(WHEEL) as wheel:
        for name, module in modules.items():
            installed = Path(module.__file__).resolve()
            require(installed.is_relative_to(site), f'{name} not from site-packages: {installed}')
            source_rel = MODULE_SOURCE[name]
            wheel_rel = 'polisyos/' + source_rel.removeprefix('src/polisyos/')
            installed_bytes = installed.read_bytes()
            source_bytes = (SOURCE_ROOT / source_rel).read_bytes()
            wheel_bytes = wheel.read(wheel_rel)
            require(installed_bytes == source_bytes == wheel_bytes, f'{name} byte identity mismatch')
            inventory[name] = {
                'origin': str(installed),
                'source': source_rel,
                'wheel': wheel_rel,
                'sha256': sha(installed_bytes),
            }
    return inventory, site


class FixtureResponse:
    def __init__(self, body: bytes, final_url: str, headers: dict[str, str]) -> None:
        self._body = body
        self.url = final_url
        self.headers = Message()
        for key, value in headers.items():
            self.headers[key] = value

    def __enter__(self) -> FixtureResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]


class FixtureOpener:
    def __init__(self, response: FixtureResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def open(self, request: object, timeout: float) -> FixtureResponse:
        self.calls.append({'request_url': getattr(request, 'full_url', None), 'timeout_s': timeout})
        return self.response


class ScriptedProvider:
    def __init__(self, name: str, response: list[WebSearchHit] | Exception) -> None:
        self.name = name
        self.response = response
        self.calls: list[str] = []

    async def search(self, query: str, *, constraints: SearchConstraints, max_results: int, timeout_s: float) -> list[WebSearchHit]:
        del constraints, max_results, timeout_s
        self.calls.append(query)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class DelayedProvider:
    def __init__(self, name: str, delay_s: float) -> None:
        self.name = name
        self.delay_s = delay_s
        self.timeouts: list[float] = []
        self.cancelled = False

    async def search(self, query: str, *, constraints: SearchConstraints, max_results: int, timeout_s: float) -> list[WebSearchHit]:
        del query, constraints, max_results
        self.timeouts.append(timeout_s)
        try:
            await asyncio.sleep(self.delay_s)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return []


async def exercise_fetch_cache_and_seed() -> dict[str, object]:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    body = b"Official employment law source.\n"
    digest = sha(body)
    url = 'https://example.gov/start'
    final_url = 'https://example.gov/final'
    headers = {'Content-Type': 'text/plain; charset=utf-8', 'ETag': '"scl-01-v1"', 'X-PolicyOS-Test': 'installed'}
    constraints = SearchConstraints(
        allowed_domains=['example.gov'],
        allow_private_networks=True,
        allowed_content_types=['text/plain'],
    )
    cas = FileSystemCAS(DATA_ROOT / 'fetch-cas')
    index = DATA_ROOT / 'fetch-cache.json'
    cache = UrlFetchCache(index_path=index, cas=cas)
    opener = FixtureOpener(FixtureResponse(body, final_url, headers))
    with patch('polisyos.scholar.discover.transport.urllib.request.build_opener', lambda *args, **kwargs: opener):
        fetched = await fetch_open_page(
            url,
            constraints=constraints,
            cache=cache,
            timeout_s=2,
            user_agent='installed-scl-audit/1',
            max_bytes=1024,
        )
    require(fetched.status == 'ok', f'first fetch status: {fetched.status}/{fetched.failure_reason}')
    require(fetched.content_sha256 == digest and fetched.artifact_id == f'sha256:{digest}', 'fetch digest/CAS identity mismatch')
    record = cache.get(url)
    require(record is not None, 'cache record missing after producer fetch')
    assert record is not None
    raw = cache.get_raw_bytes(record)
    require(raw == body, 'cache producer CAS bytes differ from response')
    raw_manifest = cas.get_manifest(record.artifact_id)
    require(raw_manifest.artifact_schema is not None, 'raw CAS schema missing')
    require(raw_manifest.artifact_schema.version == '1.0', 'raw CAS schema version mismatch')
    require(Path(index).is_file(), 'cache JSON index not persisted')

    reopened_cache = UrlFetchCache(index_path=index, cas=FileSystemCAS(DATA_ROOT / 'fetch-cas'))
    with patch('polisyos.scholar.discover.transport.urllib.request.build_opener', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('cache hit attempted network fetch'))):
        cached = await fetch_open_page(
            url,
            constraints=constraints,
            cache=reopened_cache,
            timeout_s=2,
            user_agent='installed-scl-audit/1',
            max_bytes=1024,
        )
    require(cached.status == 'cached' and cached.content_sha256 == digest, 'persisted cache readback failed')
    require(cached.headers.get('X-PolicyOS-Test') == 'installed', 'header metadata did not survive cache readback')
    require(cached.final_url == final_url and cached.byte_size == len(body), 'cached URL/size readback mismatch')

    blocked_url = 'https://example.gov/cached-blocked-final'
    blocked_final = 'https://blocked.example/final'
    blocked_body = b'blocked final response\n'
    blocked_digest = sha(blocked_body)
    blocked_cache = UrlFetchCache(index_path=DATA_ROOT / 'blocked-cache.json', cas=FileSystemCAS(DATA_ROOT / 'blocked-cas'))
    from polisyos.scholar.search.models import FetchResult
    blocked_cache.put(
        FetchResult(
            url=blocked_url,
            final_url=blocked_final,
            content_type='text/plain',
            content_sha256=blocked_digest,
            headers={'X-Cache-Test': 'preserved'},
            redirect_chain=[blocked_final],
            byte_size=len(blocked_body),
            license='fixture-license',
            fetch_profile={'recorded': 'original'},
        ),
        raw_bytes=blocked_body,
    )
    blocked_constraints = SearchConstraints(
        allowed_domains=['example.gov'],
        blocked_domains=['blocked.example'],
        allow_private_networks=True,
        allowed_content_types=['text/plain'],
    )
    with patch('polisyos.scholar.discover.transport.urllib.request.build_opener', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('blocked cache tried network fetch'))):
        blocked = await fetch_open_page(
            blocked_url,
            constraints=blocked_constraints,
            cache=blocked_cache,
            max_bytes=1024,
        )
    require(blocked.status == 'error' and blocked.failure_reason == 'blocked_domain', 'current policy did not refuse blocked cached final URL')
    require(blocked.headers.get('X-Cache-Test') == 'preserved' and blocked.final_url == blocked_final, 'typed refusal discarded cached metadata')

    seed_opener = FixtureOpener(FixtureResponse(body, final_url, headers))
    source = SourceSpec(kind='url', canonical_url=url, url=url, license='CC-BY-4.0', mime_hint='text/plain')
    with patch('polisyos.scholar.discover.transport.urllib.request.build_opener', lambda *args, **kwargs: seed_opener):
        seeded = http_fetch.fetch_url(source, constraints=constraints, timeout_s=2, user_agent='installed-scl-audit/1', max_bytes=1024)
    require(seeded.raw_bytes == body and seeded.content_sha256 == digest, 'seed adapter raw byte identity mismatch')
    require(seeded.final_url == final_url and seeded.headers.get('X-PolicyOS-Test') == 'installed', 'seed adapter lost transport metadata')
    require(seeded.doc_source.license == 'CC-BY-4.0', 'seed license identity lost')
    return {
        'fetch_producer': {'status': fetched.status, 'artifact_id': fetched.artifact_id, 'content_sha256': digest, 'byte_size': len(body), 'transport_calls': opener.calls},
        'cache_artifact': {'index_path': str(index), 'index_sha256': sha(index.read_bytes()), 'raw_cas_id': str(record.artifact_id), 'raw_cas_sha256': sha(raw), 'raw_schema_version': raw_manifest.artifact_schema.version, 'cache_readback_status': cached.status, 'cache_readback_headers': cached.headers, 'cache_readback_final_url': cached.final_url},
        'cached_policy_refusal': {'status': blocked.status, 'failure_reason': blocked.failure_reason, 'final_url': blocked.final_url, 'preserved_headers': blocked.headers},
        'seed_adapter': {'content_sha256': seeded.content_sha256, 'byte_size': seeded.byte_size, 'final_url': seeded.final_url, 'mime': seeded.mime, 'license': seeded.doc_source.license, 'transport_calls': seed_opener.calls},
        'policy': {'cache_network_fetch_forbidden_by_probe': True, 'blocked_cached_final_refused_before_network': True},
    }


async def exercise_provider_and_deadline_cas() -> dict[str, object]:
    constraints = SearchConstraints(allowed_domains=['allowed.example'], source_types=['government'])
    good = WebSearchHit(url='https://allowed.example/report', title='report', provider='useful', query='policy', rank=1, source_type='government')
    empty = ScriptedProvider('empty', [])
    useful = ScriptedProvider('useful', [good])
    uncalled = ScriptedProvider('uncalled', RuntimeError('must not run'))
    selection = await ProviderFailoverPolicy([empty, useful, uncalled]).search_detailed(
        'employment policy', constraints=constraints, max_results=5, timeout_s=1,
    )
    require([a.outcome for a in selection.attempts] == ['empty', 'useful'], 'provider failover attempt trace mismatch')
    require(len(selection.hits) == 1 and selection.stop_reason == 'useful', 'provider failover did not select first useful provider')
    require(not uncalled.calls, 'provider after useful result was called')

    first = DelayedProvider('first', 0.7)
    second = DelayedProvider('second', 0.7)
    never = ScriptedProvider('never', RuntimeError('must not run'))
    brief = ResearchBrief(question='employment policy')
    graph = QueryGraph(brief=brief, nodes=[QueryNode(node_id='q1', query='employment', perspective='overview')], root_node_ids=['q1'])
    cas = FileSystemCAS(DATA_ROOT / 'deadline-cas')
    service = ScholarDeepSearchService(provider_policy=ProviderFailoverPolicy([first, second, never]), cas=cas, search_timeout_s=2)
    started = time.monotonic()
    bundle = await service.deep_search(
        brief=brief,
        query_graph=graph,
        constraints=SearchConstraints(),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
            max_wall_time_s=1,
        ),
    )
    elapsed = time.monotonic() - started
    require(elapsed < 1.4, f'deadline exceeded bounded profile: {elapsed}')
    trace = bundle.query_traces[0]
    require([a.provider for a in trace.provider_attempts] == ['first', 'second'], 'deadline attempt sequence mismatch')
    require([a.outcome for a in trace.provider_attempts] == ['empty', 'error'], 'deadline outcome sequence mismatch')
    require(trace.terminal_reason == 'max_wall_time_s', 'deadline terminal reason missing')
    require(second.cancelled and second.timeouts and second.timeouts[0] < 0.5, 'remaining deadline did not bound and cancel second provider')
    require(not never.calls and not bundle.no_hit_frontier, 'deadline stop incorrectly continued providers or recorded a false exhausted frontier')
    require(bundle.partial is True and [item.reason for item in bundle.budget_stops] == ['max_wall_time_s'], 'deadline was not represented as partial typed budget stop')
    ref = service.persist_bundle(bundle)
    manifest = cas.get_manifest(ref.artifact_id)
    require(manifest.artifact_schema is not None and manifest.artifact_schema.version == '1.2', 'persisted web evidence bundle schema version mismatch')
    payload = cas.get_bytes(ref.artifact_id)
    readback = WebEvidenceBundle.model_validate(from_canonical_bytes(payload))
    require(readback.model_dump(mode='json', exclude_none=True) == bundle.model_dump(mode='json', exclude_none=True), 'CAS bundle readback differs from producer result')
    require(readback.query_traces[0].terminal_reason == 'max_wall_time_s' and readback.budget_stops[0].reason == 'max_wall_time_s', 'CAS consumer lost deadline semantics')
    return {
        'provider_selection': {'provider': selection.provider, 'attempts': [a.model_dump(mode='json') for a in selection.attempts], 'accepted_hits': len(selection.hits), 'uncalled_after_success': not uncalled.calls},
        'deadline_profile': {'elapsed_s': round(elapsed, 6), 'provider_timeouts_s': [first.timeouts[0], second.timeouts[0]], 'second_cancelled': second.cancelled, 'never_called': not never.calls, 'attempts': [a.model_dump(mode='json') for a in trace.provider_attempts], 'terminal_reason': trace.terminal_reason, 'partial': readback.partial, 'budget_stops': [item.model_dump(mode='json') for item in readback.budget_stops], 'no_hit_frontier_count': len(readback.no_hit_frontier)},
        'bundle_cas': {'artifact_id': str(ref.artifact_id), 'bytes': len(payload), 'sha256': sha(payload), 'schema_name': manifest.artifact_schema.name, 'schema_version': manifest.artifact_schema.version, 'readback_matches_result': True},
    }


async def main() -> None:
    require(sys.flags.isolated == 1, 'Python was not launched in isolated mode')
    module_map, site_packages = module_inventory()
    distributions = {d.metadata['Name'].lower().replace('_', '-'): d.version for d in metadata.distributions() if d.metadata.get('Name')}
    with zipfile.ZipFile(WHEEL) as z:
        metadata_text = next(z.read(n).decode('utf-8', errors='replace') for n in z.namelist() if n.endswith('.dist-info/METADATA'))
        entries = next(z.read(n).decode('utf-8', errors='replace') for n in z.namelist() if n.endswith('.dist-info/entry_points.txt'))
    require('pytest' not in distributions, 'fresh no-extra env unexpectedly contains pytest')
    fetched = await exercise_fetch_cache_and_seed()
    deadline = await exercise_provider_and_deadline_cas()
    print(json.dumps({
        'candidate': {'commit': '01c303c2a94a1ff281e4fcc9804db60183e65d68', 'tree': '7bf3e8dda2bb1179b9960ffb3c5be5a5fb8e101f'},
        'execution': {'cwd': os.getcwd(), 'isolated': sys.flags.isolated, 'python': sys.version.split()[0], 'site_packages': str(site_packages), 'PYTHONPATH': os.environ.get('PYTHONPATH'), 'PYTHONHOME': os.environ.get('PYTHONHOME')},
        'installed_modules': module_map,
        'environment': {'policy_engine': metadata.version('policy-engine'), 'pytest_present': importlib.util.find_spec('pytest') is not None, 'jsonschema_present': importlib.util.find_spec('jsonschema') is not None, 'hnswlib_present': importlib.util.find_spec('hnswlib') is not None, 'faiss_present': importlib.util.find_spec('faiss') is not None, 'optional_extras_selected': [], 'base_pyproject_sha256': 'b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267', 'base_uv_lock_sha256': 'e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463', 'installed_distribution_count': len(distributions), 'installed_distributions': distributions, 'wheel_metadata_requires_dist_sha256': sha(metadata_text.encode()), 'entry_points_sha256': sha(entries.encode())},
        'fetch_cache_seed': fetched,
        'provider_deadline_cas': deadline,
        'predicate_witnesses': {
            'wheel_module_origin_and_byte_identity': 'recomputed',
            'raw_response_to_CAS_to_reopened_cache_bytes_digest': 'recomputed',
            'cached_final_URL_policy_refusal': 'recomputed',
            'provider_attempt_trace_vs_scripted_provider_calls': 'independently_reconciled',
            'deadline_stop_vs_persisted_bundle_CAS_readback': 'recomputed',
            'live_external_search_provider_quality': 'not_established',
            'optional_vector_search_extra_profile': 'not_established',
        },
    }, sort_keys=True))

asyncio.run(main())
