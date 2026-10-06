from __future__ import annotations
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import pathlib
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

root = pathlib.Path(__file__).resolve().parent
site = next(pathlib.Path(p).resolve() for p in sys.path if p.endswith('site-packages'))

import polisyos
import polisyos.core.artifacts.store as cas_module
import polisyos.fabric.connectors.contracts as contracts_module
import polisyos.fabric.data_plane.cursor_store as cursor_store_module
import polisyos.fabric.data_plane.modes as modes_module
import polisyos.fabric.data_plane.quarantine as quarantine_module
import polisyos.fabric.data_plane.schema_rows as schema_rows_module
import polisyos.fabric.data_plane.streaming as streaming_module
import polisyos.fabric.data_plane.watermark as watermark_module
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.types import DataChunk
from polisyos.fabric.data_plane.cursor_store import CursorStore, CursorStoreError
from polisyos.fabric.data_plane.modes import _sanitize_stream_rows
from polisyos.fabric.data_plane.quarantine import list_quarantine_records, load_quarantine_payload
from polisyos.fabric.data_plane.streaming import (
    StreamCapacityError,
    StreamRuntimeOptions,
    StreamSchemaBinding,
    process_stream_dataset,
)
from polisyos.fabric.data_plane.watermark import WindowPolicy


def inside_site(module: object) -> bool:
    path = getattr(module, '__file__', None)
    return bool(path) and pathlib.Path(path).resolve().is_relative_to(site)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

modules = {
    'polisyos': polisyos,
    'polisyos.core.artifacts.store': cas_module,
    'polisyos.fabric.connectors.contracts': contracts_module,
    'polisyos.fabric.data_plane.cursor_store': cursor_store_module,
    'polisyos.fabric.data_plane.modes': modes_module,
    'polisyos.fabric.data_plane.quarantine': quarantine_module,
    'polisyos.fabric.data_plane.schema_rows': schema_rows_module,
    'polisyos.fabric.data_plane.streaming': streaming_module,
    'polisyos.fabric.data_plane.watermark': watermark_module,
}
module_origins = {name: str(pathlib.Path(module.__file__).resolve()) for name, module in modules.items()}
assert all(inside_site(module) for module in modules.values()), module_origins
assert importlib.util.find_spec('pytest') is None, 'test dependencies unexpectedly present'
assert not any(name.startswith('tests.') or name.startswith('test_') for name in sys.modules)
assert not any('/e02-c-ing-oracle-20261006/polisyos' in str(path) or '/raw/installed/ing/source/policy-engine' in str(path) or '/raw/installed/ing-successor-68eed/source/policy-engine' in str(path) for path in sys.path)
dist = metadata.distribution('policy-engine')
metadata_text = dist.read_text('METADATA') or ''
base_jsonschema = [line for line in metadata_text.splitlines() if line.lower().startswith('requires-dist: jsonschema')]
assert base_jsonschema == ['Requires-Dist: jsonschema[format-nongpl]>=4.25.1'], base_jsonschema

class FixtureStreamConnector:
    """Small deterministic source fixture used only to exercise installed production code."""
    connector_id = 'fixture.stream'

    def __init__(self, events: list[Any]) -> None:
        self.events = list(events)
        self.poll_calls = 0
        self.rewind_calls = 0
        self.commit_calls = 0
        self.close_calls = 0
        self.disconnect_calls = 0

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle
        self.disconnect_calls += 1

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        del handle
        return HealthStatus(healthy=True, message='fixture is local and deterministic')

    async def subscribe_stream(self, handle: ConnectionHandle, request: Any) -> object:
        del handle, request
        return object()

    async def poll_stream(self, handle: ConnectionHandle, subscription: object) -> Any:
        del handle, subscription
        self.poll_calls += 1
        if not self.events:
            return None
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        return event

    async def rewind_stream(self, handle: ConnectionHandle, checkpoint: Any) -> None:
        del handle, checkpoint
        self.rewind_calls += 1

    async def commit_stream(self, handle: ConnectionHandle, checkpoint: Any) -> None:
        del handle, checkpoint
        self.commit_calls += 1

    async def close_stream(self, handle: ConnectionHandle) -> None:
        del handle
        self.close_calls += 1


def make_schema() -> DataSchema:
    return DataSchema(
        schema_id='installed.stream.fixture',
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name='message_id', data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name='event_time', data_type=SchemaType.TIMESTAMP_TZ, nullable=False),
            FieldSpec(name='value', data_type=SchemaType.FLOAT64, nullable=False, bounds=(0.0, 10.0)),
        ),
        primary_key=('message_id',),
        required_completeness=0.0,
    )


def make_registry(connector: FixtureStreamConnector, schema: DataSchema, dataset_id: str) -> tuple[Any, StreamSchemaBinding]:
    contract = ConnectorSchemaContract(
        contract_id='installed.stream.fixture_contract',
        connector_id=FixtureStreamConnector.connector_id,
        dataset_id=dataset_id,
        schema=schema,
        created_by='installed-package-probe',
    )
    binding = StreamSchemaBinding.from_contract(contract, registry_revision=1)
    config = ConnectionConfig(url='fixture://local', max_connections=1)
    entry = SimpleNamespace(factory=lambda: connector, default_config=config)

    class Registry:
        def get_entry(self, connector_id: str) -> Any:
            assert connector_id == FixtureStreamConnector.connector_id
            return entry

        def resolve_schema_contract(self, *, connector_id: str, dataset_id: str) -> tuple[Any, int]:
            assert connector_id == FixtureStreamConnector.connector_id
            assert dataset_id == contract.dataset_id
            return contract, 1

    return Registry(), binding


def sanitizer_for(schema: DataSchema, binding: StreamSchemaBinding):
    def sanitize(rows: Any, *, connector_id: str, dataset_id: str, store: Any, chunk_index: int):
        return _sanitize_stream_rows(
            rows,
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=chunk_index,
            schema=schema,
            schema_binding=binding,
        )
    return sanitize


def utc_text(value: object) -> str:
    assert isinstance(value, str), value
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), value
    return value


def checkpoint_cas_record(store: FileSystemCAS, cursor_store: CursorStore, connector_id: str, dataset_id: str) -> dict[str, Any]:
    checkpoint = cursor_store.find_latest_stream_checkpoint(connector_id, dataset_id, partition_key='installed-probe')
    assert checkpoint is not None
    stream_id = f'{connector_id}:{dataset_id}:installed-probe'
    checkpoint_artifact_id = cursor_store._stream_index[stream_id]
    checkpoint_ref = ArtifactID.model_validate(checkpoint_artifact_id)
    raw = store.get_bytes(checkpoint_ref)
    payload = from_canonical_bytes(raw)
    assert isinstance(payload, dict)
    assert type(checkpoint).model_validate(payload).model_dump(mode='json') == checkpoint.model_dump(mode='json')
    assert utc_text(payload['created_at'])
    if payload.get('committed_at') is not None:
        assert utc_text(payload['committed_at'])
    return {
        'ref': str(checkpoint_ref),
        'sha256': sha(raw),
        'typed': checkpoint,
        'payload': payload,
        'payload_bytes': raw,
    }


async def exercise_installed() -> dict[str, Any]:
    schema = make_schema()
    connector_id = FixtureStreamConnector.connector_id
    cas_root = root / 'cas-final' / 'membership'
    store = FileSystemCAS(cas_root)
    cursor_store = CursorStore(store)
    rows = [
        {'message_id': 'ok-1', 'event_time': '2026-10-06T10:00:00Z', 'value': 1.5},
        {'message_id': 'bad-1', 'event_time': '2026-10-06T10:00:01Z', 'value': '2.5'},
    ]
    connector = FixtureStreamConnector([DataChunk(data=rows, chunk_index=1, row_count=2, bytes_size=80)])
    registry, binding = make_registry(connector, schema, 'membership')
    options = StreamRuntimeOptions(
        partition_key='installed-probe',
        batch_size=2,
        checkpoint_every_chunks=1,
        dedupe_key_fields=('message_id',),
        max_dedupe_keys=16,
        max_buffered_rows=8,
        max_buffered_bytes=1_000_000,
        max_input_rows=8,
        max_input_bytes=1_000_000,
        max_output_refs=32,
        pause_seconds=0.0,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
    )
    result = await process_stream_dataset(
        connector_id=connector_id,
        dataset_id='membership',
        store=store,
        cursor_store=cursor_store,
        sanitize_rows=sanitizer_for(schema, binding),
        runtime_options=options,
        registry=registry,
        schema_binding=binding,
    )
    assert result.rows_emitted == 1, result.rows_emitted
    assert result.quarantined_rows == 1, result.quarantined_rows
    assert len(result.chunk_refs) == len(result.window_refs) == 1
    chunk_ref = result.chunk_refs[0]
    window_ref = result.window_refs[0]
    chunk_raw = store.get_bytes(chunk_ref)
    window_raw = store.get_bytes(window_ref)
    chunk_payload = from_canonical_bytes(chunk_raw)
    window_payload = from_canonical_bytes(window_raw)
    assert chunk_payload['data'] == [rows[0]], chunk_payload
    assert chunk_payload['schema_binding'] == binding.snapshot()
    assert window_payload['data'] == [rows[0]], window_payload
    assert window_payload['row_count'] == 1
    assert window_payload['lineage']['contributor_chunk_refs'] == [str(chunk_ref.artifact_id)]
    assert store.get_manifest(window_ref).inputs[0].artifact_id == chunk_ref.artifact_id
    quarantine = list_quarantine_records(
        store,
        source=f'connector.stream:{connector_id}:membership',
        reason='poison_stream_message',
    )
    assert len(quarantine) == 1, len(quarantine)
    quarantine_id, quarantine_record = quarantine[0]
    assert quarantine_record.context['row_index'] == 1
    assert quarantine_record.context['field_violations'] == {'value': 'schema_type_mismatch'}
    raw_quarantine_row = load_quarantine_payload(store, quarantine_record.raw_payload_ref)
    assert raw_quarantine_row == rows[1]
    field_origin = str(pathlib.Path(schema_rows_module.__file__).resolve())
    assert pathlib.Path(field_origin).is_relative_to(site)

    checkpoint_ref = ArtifactID.model_validate(result.final_checkpoint_ref)
    cursor_ref = ArtifactID.model_validate(result.final_cursor_ref)
    checkpoint_raw = store.get_bytes(checkpoint_ref)
    checkpoint_payload = from_canonical_bytes(checkpoint_raw)
    checkpoint = cursor_store.find_latest_stream_checkpoint(connector_id, 'membership', partition_key='installed-probe')
    assert checkpoint is not None
    checkpoint_from_ref = type(checkpoint).model_validate(checkpoint_payload)
    assert checkpoint_from_ref.model_dump(mode='json') == checkpoint_payload
    cursor = cursor_store.find_latest_cursor(connector_id, 'membership', partition_key='installed-probe')
    assert cursor is not None
    cursor_raw = store.get_bytes(cursor_ref)
    cursor_payload = from_canonical_bytes(cursor_raw)
    cursor_from_ref = type(cursor).model_validate(cursor_payload)
    assert cursor_from_ref.model_dump(mode='json') == cursor_payload
    assert checkpoint_from_ref.metadata['schema_binding'] == binding.snapshot()
    assert checkpoint_from_ref.offset == 1 and cursor_from_ref.watermark_value == '1'
    assert utc_text(checkpoint_payload['created_at'])
    if checkpoint_payload.get('committed_at') is not None:
        utc_text(checkpoint_payload['committed_at'])
    assert utc_text(cursor_payload['created_at'])
    latest_stream_id = f'{connector_id}:membership:installed-probe'
    latest_checkpoint_ref_text = cursor_store._stream_index[latest_stream_id]
    assert result.final_checkpoint_ref == latest_checkpoint_ref_text, (
        'returned final checkpoint ref does not equal durable latest index ref'
    )
    latest_checkpoint_ref = ArtifactID.model_validate(latest_checkpoint_ref_text)
    latest_checkpoint_raw = store.get_bytes(latest_checkpoint_ref)
    latest_checkpoint_payload = from_canonical_bytes(latest_checkpoint_raw)
    assert isinstance(latest_checkpoint_payload, dict)
    result_checkpoint = result.final_checkpoint
    assert result_checkpoint is not None
    result_checkpoint_payload = result_checkpoint.model_dump(mode='json')
    returned_checkpoint = type(result_checkpoint).model_validate(checkpoint_payload)
    indexed_checkpoint = type(result_checkpoint).model_validate(latest_checkpoint_payload)
    assert returned_checkpoint.model_dump(mode='json') == result_checkpoint_payload
    assert indexed_checkpoint.model_dump(mode='json') == result_checkpoint_payload
    assert checkpoint_from_ref.model_dump(mode='json') == result_checkpoint_payload
    assert checkpoint_payload == latest_checkpoint_payload
    assert checkpoint_raw == latest_checkpoint_raw
    assert result_checkpoint.lifecycle_state.value == 'closed'
    assert result_checkpoint.committed_at is not None
    assert result_checkpoint.metadata['frontier_intent']['state'] == 'committed'
    assert utc_text(latest_checkpoint_payload['created_at'])
    assert utc_text(latest_checkpoint_payload['committed_at'])

    cursor_index = json.loads((cas_root / 'cursor_index.json').read_text())
    cursor_id = f'{connector_id}:membership:installed-probe'
    latest_cursor_ref_text = cursor_index[cursor_id]
    assert result.final_cursor_ref == latest_cursor_ref_text
    assert result.final_cursor is not None
    assert result.final_cursor.model_dump(mode='json') == cursor_payload
    latest_cursor_payload = from_canonical_bytes(
        store.get_bytes(ArtifactID.model_validate(latest_cursor_ref_text))
    )
    assert isinstance(latest_cursor_payload, dict)
    assert latest_cursor_payload == cursor_payload
    assert result.final_cursor.model_dump(mode='json') == latest_cursor_payload

    # Reopen the installed runtime's CAS and index; exact returned reference and
    # the full typed closed checkpoint must survive process/store reconstruction.
    reopened_store = FileSystemCAS(cas_root)
    reopened_cursor_store = CursorStore(reopened_store)
    reopened_stream_index = json.loads((cas_root / 'stream_checkpoint_index.json').read_text())
    reopened_cursor_index = json.loads((cas_root / 'cursor_index.json').read_text())
    assert result.final_checkpoint_ref == reopened_stream_index[latest_stream_id]
    assert result.final_cursor_ref == reopened_cursor_index[cursor_id]
    reopened_payload = from_canonical_bytes(
        reopened_store.get_bytes(ArtifactID.model_validate(result.final_checkpoint_ref))
    )
    assert isinstance(reopened_payload, dict)
    assert reopened_payload == result_checkpoint_payload
    reopened_latest = reopened_cursor_store.find_latest_stream_checkpoint(
        connector_id, 'membership', partition_key='installed-probe'
    )
    assert reopened_latest is not None
    assert reopened_latest.model_dump(mode='json') == result_checkpoint_payload

    # Prove the exact-index guard distinguishes a real prepared artifact from
    # the committed result reference, using only the runtime's persisted CAS.
    intent_id = result_checkpoint.metadata['frontier_intent']['intent_id']
    prepared_refs = []
    for artifact_id in reopened_store.iter_artifact_ids():
        if reopened_store.get_manifest(artifact_id).kind != 'fabric.stream_checkpoint':
            continue
        candidate = type(result_checkpoint).model_validate(
            from_canonical_bytes(reopened_store.get_bytes(artifact_id))
        )
        intent = candidate.metadata.get('frontier_intent', {})
        if candidate.stream_id == latest_stream_id and intent.get('state') == 'prepared' and intent.get('intent_id') == intent_id:
            prepared_refs.append(str(artifact_id))
    assert len(prepared_refs) == 1, prepared_refs

    def assert_ref_is_latest(ref_text: str, index: dict[str, str]) -> None:
        assert ref_text == index[latest_stream_id], (
            'returned final checkpoint ref does not equal durable latest index ref'
        )

    try:
        assert_ref_is_latest(prepared_refs[0], reopened_stream_index)
    except AssertionError as exc:
        prepared_canary_rejected = str(exc) == (
            'returned final checkpoint ref does not equal durable latest index ref'
        )
    else:
        raise AssertionError('prepared checkpoint canary unexpectedly matched the committed index')
    assert prepared_canary_rejected
    assert_ref_is_latest(result.final_checkpoint_ref, reopened_stream_index)
    return {
        'producer': 'installed polisyos.fabric.data_plane.streaming.process_stream_dataset',
        'module_origins': module_origins,
        'cas_root': str(cas_root),
        'schema_binding': binding.snapshot(),
        'source_input_rows': len(rows),
        'chunk_ref': str(chunk_ref.artifact_id),
        'chunk_sha256': sha(chunk_raw),
        'chunk_payload': chunk_payload,
        'window_ref': str(window_ref.artifact_id),
        'window_sha256': sha(window_raw),
        'window_payload': window_payload,
        'quarantine_ref': quarantine_id,
        'quarantine_record': {
            'reason': quarantine_record.reason,
            'context': quarantine_record.context,
            'raw_payload_ref': quarantine_record.raw_payload_ref,
            'readback_raw_payload': raw_quarantine_row,
        },
        'field_value_violation_module_origin': field_origin,
        'membership': {
            'valid_row_emitted': chunk_payload['data'][0]['message_id'] == 'ok-1',
            'invalid_row_not_emitted': all(row['message_id'] != 'bad-1' for row in chunk_payload['data']),
            'invalid_numeric_string_typed_as': quarantine_record.context['field_violations']['value'],
            'valid_count': result.rows_emitted,
            'quarantined_count': result.quarantined_rows,
        },
        'checkpoint': {
            'ref': str(checkpoint_ref),
            'sha256': sha(checkpoint_raw),
            'payload': checkpoint_payload,
            'typed_offset': checkpoint_from_ref.offset,
            'lifecycle_state': checkpoint_from_ref.lifecycle_state.value,
            'committed_at_present_on_result_ref': checkpoint_payload.get('committed_at') is not None,
            'utc_created_at': True,
            'latest_closed_ref': latest_checkpoint_ref_text,
            'latest_closed_sha256': sha(latest_checkpoint_raw),
            'returned_ref_equals_latest_index': True,
            'full_payload_equals_latest_closed_payload': checkpoint_payload == latest_checkpoint_payload,
            'full_typed_payload_equals_result_checkpoint': returned_checkpoint.model_dump(mode='json') == result_checkpoint_payload,
            'reopened_full_checkpoint_equals_result': reopened_payload == result_checkpoint_payload,
            'prepared_checkpoint_canary_rejected': prepared_canary_rejected,
            'prepared_checkpoint_canary_ref': prepared_refs[0],
            'latest_closed_utc_committed_at': True,
        },
        'cursor': {
            'ref': str(cursor_ref),
            'sha256': sha(cursor_raw),
            'payload': cursor_payload,
            'watermark_value': cursor_from_ref.watermark_value,
            'utc_created_at': True,
        },
        'window_lineage_matches_chunk': True,
        'module_test_imports_absent': True,
    }


async def exercise_restore_refusal() -> dict[str, Any]:
    schema = make_schema()
    connector_id = FixtureStreamConnector.connector_id
    dataset_id = 'restore-lower-cap'
    store = FileSystemCAS(root / 'cas-final' / 'restore')
    cursor_store = CursorStore(store)
    rows = [
        {'message_id': 'restore-1', 'event_time': '2026-10-06T11:00:00Z', 'value': 1},
        {'message_id': 'restore-2', 'event_time': '2026-10-06T11:00:01Z', 'value': 2},
    ]
    connector_before = FixtureStreamConnector([
        DataChunk(data=rows, chunk_index=5, row_count=2, bytes_size=90),
        RuntimeError('controlled fixture interruption after checkpoint'),
    ])
    registry_before, binding = make_registry(connector_before, schema, dataset_id)
    initial_options = StreamRuntimeOptions(
        partition_key='installed-probe',
        batch_size=2,
        checkpoint_every_chunks=1,
        dedupe_key_fields=('message_id',),
        max_dedupe_keys=16,
        max_buffered_rows=4,
        max_buffered_bytes=1_000_000,
        max_input_rows=8,
        max_input_bytes=1_000_000,
        max_output_refs=32,
        pause_seconds=0.0,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=4),
    )
    interruption = None
    try:
        await process_stream_dataset(
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=sanitizer_for(schema, binding),
            runtime_options=initial_options,
            registry=registry_before,
            schema_binding=binding,
        )
    except RuntimeError as exc:
        if 'controlled fixture interruption' not in str(exc):
            raise
        interruption = str(exc)
    assert interruption is not None
    before = checkpoint_cas_record(store, cursor_store, connector_id, dataset_id)
    state = before['payload']['metadata']['operator_state']
    assert before['payload']['lifecycle_state'] == 'paused'
    buffered = state['accumulator']['count_buffer']
    assert len(buffered) == 2, state
    assert state['max_event_time'].endswith('+00:00') or state['max_event_time'].endswith('Z')
    assert all(entry['refs'] for entry in buffered)
    assert len(set(ref for entry in buffered for ref in entry['refs'])) == 1
    assert before['payload']['metadata']['operator_state_required'] is True
    prior_cursor = cursor_store.find_latest_cursor(connector_id, dataset_id, partition_key='installed-probe')
    assert prior_cursor is not None
    prior_cursor_payload = prior_cursor.model_dump(mode='json')
    prior_artifact_count = len(store.iter_artifact_ids())

    connector_after = FixtureStreamConnector([])
    registry_after, same_binding = make_registry(connector_after, schema, dataset_id)
    assert same_binding.snapshot() == binding.snapshot()
    lower_options = StreamRuntimeOptions(
        partition_key='installed-probe',
        batch_size=2,
        checkpoint_every_chunks=1,
        dedupe_key_fields=('message_id',),
        max_dedupe_keys=16,
        max_buffered_rows=1,
        max_buffered_bytes=1_000_000,
        max_input_rows=8,
        max_input_bytes=1_000_000,
        max_output_refs=32,
        pause_seconds=0.0,
        window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=4),
    )
    try:
        await process_stream_dataset(
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            cursor_store=cursor_store,
            sanitize_rows=sanitizer_for(schema, same_binding),
            runtime_options=lower_options,
            registry=registry_after,
            schema_binding=same_binding,
        )
    except StreamCapacityError as exc:
        refusal = exc
    else:
        raise AssertionError('lower-cap restore unexpectedly advanced')
    after = checkpoint_cas_record(store, cursor_store, connector_id, dataset_id)
    post_cursor = cursor_store.find_latest_cursor(connector_id, dataset_id, partition_key='installed-probe')
    assert post_cursor is not None
    assert refusal.stage == 'restore'
    assert refusal.rows == 2 and refusal.max_rows == 1
    assert connector_after.poll_calls == 0
    assert connector_after.rewind_calls == 0
    assert after['ref'] == before['ref'] and after['sha256'] == before['sha256']
    assert post_cursor.model_dump(mode='json') == prior_cursor_payload
    assert len(store.iter_artifact_ids()) == prior_artifact_count
    return {
        'producer': 'installed polisyos.fabric.data_plane.streaming.process_stream_dataset',
        'controlled_interruption': interruption,
        'committed_predecessor_checkpoint': {
            'ref': before['ref'],
            'sha256': before['sha256'],
            'lifecycle_state': before['payload']['lifecycle_state'],
            'offset': before['payload']['offset'],
            'buffered_rows': len(buffered),
            'buffered_rows_carry_chunk_refs': True,
            'operator_state_required': True,
            'operator_max_event_time_utc': state['max_event_time'],
        },
        'restore_refusal': {
            'typed_error': f'{type(refusal).__module__}.{type(refusal).__qualname__}',
            'stage': refusal.stage,
            'rows': refusal.rows,
            'max_rows': refusal.max_rows,
            'poll_calls_after_resume_start': connector_after.poll_calls,
            'source_rewind_calls_after_resume_start': connector_after.rewind_calls,
        },
        'before_after': {
            'checkpoint_ref_unchanged': after['ref'] == before['ref'],
            'checkpoint_sha256_unchanged': after['sha256'] == before['sha256'],
            'cursor_payload_unchanged': post_cursor.model_dump(mode='json') == prior_cursor_payload,
            'cas_artifact_count_unchanged': len(store.iter_artifact_ids()) == prior_artifact_count,
        },
    }


import asyncio

results = asyncio.run(exercise_installed())
restore = asyncio.run(exercise_restore_refusal())
receipt = {
    'candidate_commit': '68eed6d56f48e9a676edeb3251902300a64d5fad',
    'candidate_tree': '0d0163f817c7b697e18f96c0056076a7360b8e8f',
    'wheel_sha256': '85095b7bb283b79d16367565deea21a9b9256a1b890ab2a6a5e2c5e14233e51b',
    'sdist_sha256': 'e8ebfa2963e23b14f562cf33f47e1bf82a95ffe584fa564c2e1a1cfda0e8a9b2',
    'runtime_environment': {
        'python': sys.version,
        'site_packages': str(site),
        'project_version': metadata.version('policy-engine'),
        'project_wheel_requires_dist_jsonschema': base_jsonschema,
        'jsonschema_version': metadata.version('jsonschema'),
        'test_package_installed': importlib.util.find_spec('pytest') is not None,
        'module_origins': module_origins,
        'test_source_imports': False,
        'python_path': list(sys.path),
        'jax_imported': 'jax' in sys.modules or 'jaxlib' in sys.modules,
        'numerical_model_or_causal_backend_run': False,
        'installed_streaming_module_sha256': hashlib.sha256(pathlib.Path(streaming_module.__file__).read_bytes()).hexdigest(),
    },
    'installed_stream_producer_and_cas_consumer': results,
    'installed_checkpoint_restore_lower_cap': restore,
}
path = root / 'installed-ing-runtime.json'
path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
print(json.dumps(receipt, indent=2, sort_keys=True))
