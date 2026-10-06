from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as metadata
import json
import sys
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.scholar.search.cache import UrlFetchCache
from polisyos.scholar.search.models import (
    ClaimSupportLink,
    FetchResult,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
)
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment import (
    _build_web_evidence_section,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_WEB_EVIDENCE_BUNDLE_REF

RAW = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed').resolve()
SCL = RAW / 'scl-01c'
WHEEL = SCL / 'dist/policy_engine-0.1.0-py3-none-any.whl'
ARCHIVE = SCL / 'candidate.tar'
DATA = RAW / 'scl-packet-consumer-data-v3'
SOURCE_URL = 'https://agency.gov/reports/employment'
FINAL_URL = 'https://agency.gov/reports/employment-2026'
SNAPSHOT_V1 = b'The minimum wage policy is 100 USD per hour.\n'
SNAPSHOT_V2 = b'The minimum wage policy is 999 USD per hour.\n'
FETCH_PROFILE = {
    'transport': 'scl-01',
    'timeout_s': '5',
    'max_bytes': '4096',
    'allowed_content_types': 'text/plain',
    'allow_private_networks': 'false',
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def store_fixture_snapshot(cache: UrlFetchCache, payload: bytes) -> object:
    return cache.put(
        FetchResult(
            url=SOURCE_URL,
            final_url=FINAL_URL,
            title='Employment policy report',
            text=payload.decode('utf-8'),
            content_type='text/plain',
            fetched_at=datetime.now(UTC),
            status='ok',
            content_sha256=sha(payload),
            etag='fixture-v1' if payload == SNAPSHOT_V1 else 'fixture-v2',
            last_modified='Wed, 01 Jan 2026 00:00:00 GMT',
            redirect_chain=[SOURCE_URL, FINAL_URL],
            source_type='government',
            license='CC-BY-4.0',
            fetch_profile=dict(FETCH_PROFILE),
        ),
        raw_bytes=payload,
    )

def make_bundle(source_ref: str, expected_sha: str) -> WebEvidenceBundle:
    source = SourceMetadata(
        source_id='src.employment.v1',
        url=SOURCE_URL,
        final_url=FINAL_URL,
        title='Employment policy report',
        domain='agency.gov',
        source_type='government',
        provider='fixture',
        search_query='employment policy',
        search_rank=1,
        fetched_at=datetime(2026, 10, 6, 13, 0, tzinfo=UTC),
        fetch_status='cached',
        content_type='text/plain',
        content_sha256=expected_sha,
        headers={'ETag': 'fixture-v1'},
        artifact_id=source_ref,
        byte_size=len(SNAPSHOT_V1),
        license='CC-BY-4.0',
        fetch_profile=dict(FETCH_PROFILE),
        etag='fixture-v1',
        last_modified='Wed, 01 Jan 2026 00:00:00 GMT',
        redirect_chain=[SOURCE_URL, FINAL_URL],
        paywalled=False,
    )
    brief = ResearchBrief(question='employment policy')
    node = QueryNode(node_id='q1', query='employment policy', perspective='overview', status='searched', hit_count=1)
    return WebEvidenceBundle(
        schema_version='1.2',
        bundle_id='webkb.scl03.fixture',
        brief=brief,
        query_graph=QueryGraph(brief=brief, nodes=[node], root_node_ids=['q1']),
        sources=[source],
        snippets=[
            SourceSnippet(
                snippet_id='snip.src.employment.v1.1',
                source_id='src.employment.v1',
                url=SOURCE_URL,
                query_node_id='q1',
                perspective='overview',
                text='employment increased',
                start_char=11,
                end_char=30,
            )
        ],
        claim_supports=[
            ClaimSupportLink(
                claim_id='claim.employment.v1',
                claim_text='employment increased',
                snippet_ids=['snip.src.employment.v1.1'],
                source_ids=['src.employment.v1'],
                support_score=0.8,
                metadata={'support_status': 'supported'},
            )
        ],
    )

def module_inventory(site: Path) -> list[dict[str, object]]:
    selected = [
        'polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment',
        'polisyos.scientist.nodes.builtins.decide.decision_packet.serialization',
        'polisyos.scientist.nodes.builtins.decide.decision_packet.validation',
        'polisyos.scientist.nodes.builtins.state_keys',
        'polisyos.scholar.search.models',
        'polisyos.scholar.search.cache',
        'polisyos.scholar.search.service',
        'polisyos.core.artifacts.store',
        'polisyos.core.artifacts.manifest',
        'polisyos.core.artifacts.write_contract',
        'polisyos.core.canon',
    ]
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(WHEEL) as wheel, tarfile.open(ARCHIVE, 'r:') as archive:
        names = set(archive.getnames())
        wheel_names = set(wheel.namelist())
        for name in selected:
            module = sys.modules.get(name)
            require(module is not None, f'{name}: module was not loaded')
            origin = Path(module.__file__).resolve()
            require(origin.is_relative_to(site) and origin.suffix == '.py', f'{name}: unexpected installed origin {origin}')
            wheel_member = origin.relative_to(site).as_posix()
            if wheel_member.startswith('polisyos/'):
                archive_member = f'policy-engine/src/{wheel_member}'
            else:
                archive_member = f'policy-engine/{wheel_member}'
            require(wheel_member in wheel_names, f'{name}: absent from wheel: {wheel_member}')
            require(archive_member in names, f'{name}: absent from frozen archive: {archive_member}')
            installed_bytes = origin.read_bytes()
            wheel_bytes = wheel.read(wheel_member)
            archive_bytes = archive.extractfile(archive_member).read()
            require(installed_bytes == wheel_bytes == archive_bytes, f'{name}: source/wheel/install byte mismatch')
            rows.append({
                'module': name,
                'origin': str(origin),
                'wheel_member': wheel_member,
                'source_archive_member': archive_member,
                'sha256': sha(installed_bytes),
                'byte_identity': True,
            })
    return rows

require(sys.flags.isolated == 1, 'probe must run with Python -I')
site_packages = Path(next(path for path in sys.path if path.endswith('site-packages'))).resolve()
dist = metadata.distribution('policy-engine')
require(dist.version == '0.1.0', f'unexpected installed distribution version: {dist.version}')
require(Path.cwd().resolve() == Path('/private/tmp'), f'probe must run outside checkout, got {Path.cwd()}')

DATA.mkdir(parents=True, exist_ok=True)
cas_root = DATA / 'cas'
cas = FileSystemCAS(cas_root)
cache = UrlFetchCache(index_path=DATA / 'cache.json', cas=cas, ttl_seconds=3600)
v1_record = store_fixture_snapshot(cache, SNAPSHOT_V1)
v2_record = store_fixture_snapshot(cache, SNAPSHOT_V2)
latest = cache.get(SOURCE_URL)
require(latest is not None, 'versioned cache entry missing')
assert latest is not None
v1_ref = str(v1_record.artifact_id)
v2_ref = str(v2_record.artifact_id)
require(v1_ref != v2_ref, 'different source snapshots did not receive distinct CAS ids')
require(str(latest.artifact_id) == v2_ref, 'URL cache did not advance to v2')
require(latest.lineage_parent_artifact_id == v1_ref, 'v2 cache record lost its v1 lineage')
require(cas.get_bytes(v1_ref) == SNAPSHOT_V1 and cas.get_bytes(v2_ref) == SNAPSHOT_V2, 'versioned raw CAS payloads differ from fixture bytes')

service = ScholarDeepSearchService(cas=cas)
bundle = make_bundle(v1_ref, sha(SNAPSHOT_V1))
bundle_ref = service.persist_bundle(bundle)
bundle_manifest = cas.get_manifest(bundle_ref.artifact_id)
require(bundle_manifest.artifact_schema is not None and bundle_manifest.artifact_schema.version == '1.2', 'bundle CAS schema mismatch')
reopened_bundle = WebEvidenceBundle.model_validate(from_canonical_bytes(cas.get_bytes(bundle_ref.artifact_id)))
require(reopened_bundle.model_dump(mode='json', exclude_none=True) == bundle.model_dump(mode='json', exclude_none=True), 'persisted bundle typed readback mismatch')

raw_reads: list[str] = []
get_bytes = cas.get_bytes
def record_get_bytes(artifact_id: object) -> bytes:
    if str(artifact_id) == v1_ref:
        raw_reads.append(str(artifact_id))
    return get_bytes(artifact_id)
cas.get_bytes = record_get_bytes
section = _build_web_evidence_section(
    SimpleNamespace(store=cas),
    {ARTIFACT_WEB_EVIDENCE_BUNDLE_REF: bundle_ref},
)
require(section is not None, 'packet consumer omitted web evidence section')
require(section['status'] == 'available', 'packet consumer did not load persisted bundle')
require(section['source_snapshots'][0]['artifact_id'] == v1_ref, 'packet consumer substituted latest URL snapshot for selected v1 CAS ref')
require(section['source_snapshots'][0]['status'] == 'verified', 'packet consumer did not verify selected v1 source')
require(section['source_snapshots'][0]['computed_sha256'] == sha(SNAPSHOT_V1), 'packet consumer digest mismatch')
require(section['snippets'][0]['raw_artifact_id'] == v1_ref and section['snippets'][0]['raw_snapshot_status'] == 'verified', 'packet snippet did not preserve verified source binding')
require(section['claim_supports'][0]['source_artifact_ids'] == [v1_ref], 'packet claim support did not retain only verified source id')
require(raw_reads == [v1_ref], f'packet consumer did not read selected v1 once: {raw_reads}')
positive_raw_reads = list(raw_reads)

wrong_bundle = make_bundle(v1_ref, sha(SNAPSHOT_V2))
wrong_ref = service.persist_bundle(wrong_bundle)
wrong_section = _build_web_evidence_section(
    SimpleNamespace(store=cas),
    {ARTIFACT_WEB_EVIDENCE_BUNDLE_REF: wrong_ref},
)
require(wrong_section is not None, 'negative packet consumer omitted web evidence section')
require(wrong_section['source_snapshots'][0]['status'] == 'mismatch', 'packet consumer failed to reject false digest binding')
require(wrong_section['claim_supports'][0]['source_artifact_ids'] == [], 'packet consumer admitted a source id with mismatched content')
negative_raw_reads = raw_reads[len(positive_raw_reads):]

modules = module_inventory(site_packages)
required_modules = {
    'polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment',
    'polisyos.scientist.nodes.builtins.state_keys',
    'polisyos.scholar.search.models',
    'polisyos.scholar.search.cache',
    'polisyos.scholar.search.service',
    'polisyos.core.artifacts.store',
    'polisyos.core.artifacts.manifest',
    'polisyos.core.canon',
}
module_names = {str(row['module']) for row in modules}
require(required_modules <= module_names, f'expected consumer modules absent from installed inventory: {sorted(required_modules - module_names)}')

print(json.dumps({
    'candidate': {
        'commit': '01c303c2a94a1ff281e4fcc9804db60183e65d68',
        'tree': '7bf3e8dda2bb1179b9960ffb3c5be5a5fb8e101f',
        'wheel_sha256': hashlib.sha256(WHEEL.read_bytes()).hexdigest(),
        'wheel_bytes': WHEEL.stat().st_size,
    },
    'execution': {
        'cwd': str(Path.cwd()),
        'python': sys.version.split()[0],
        'isolated': sys.flags.isolated,
        'site_packages': str(site_packages),
        'PYTHONPATH': None,
        'PYTHONHOME': None,
        'no_external_provider_or_network_called': True,
    },
    'fixture': {
        'source_url': SOURCE_URL,
        'final_url': FINAL_URL,
        'v1_sha256': sha(SNAPSHOT_V1),
        'v2_sha256': sha(SNAPSHOT_V2),
        'v1_artifact_id': v1_ref,
        'v2_artifact_id': v2_ref,
        'url_cache_latest_artifact_id': str(latest.artifact_id),
        'v2_parent_artifact_id': latest.lineage_parent_artifact_id,
        'bundle_artifact_id': str(bundle_ref.artifact_id),
        'bundle_manifest_schema_version': bundle_manifest.artifact_schema.version,
        'persisted_bundle_typed_readback_matches': True,
    },
    'installed_packet_consumer': {
        'module': 'polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment._build_web_evidence_section',
        'selected_ref': str(bundle_ref.artifact_id),
        'selected_source_ref': v1_ref,
        'cache_latest_was_v2': str(latest.artifact_id) == v2_ref,
        'source_snapshot_status': section['source_snapshots'][0]['status'],
        'source_snapshot_sha256': section['source_snapshots'][0]['computed_sha256'],
        'snippet_status': section['snippets'][0]['raw_snapshot_status'],
        'claim_source_refs': section['claim_supports'][0]['source_artifact_ids'],
        'selected_raw_source_reads': positive_raw_reads,
        'wrong_digest_raw_source_reads': negative_raw_reads,
        'wrong_digest_status': wrong_section['source_snapshots'][0]['status'],
        'wrong_digest_claim_source_refs': wrong_section['claim_supports'][0]['source_artifact_ids'],
    },
    'module_origins_and_frozen_byte_identity': {
        'selected_module_count': len(modules),
        'modules': modules,
    },
}, sort_keys=True))
