from __future__ import annotations
import asyncio, hashlib, importlib, json, os, sys, zipfile
from collections import Counter
from pathlib import Path
from typing import Any
import polisyos
import polisyos.fabric.connectors.registry as registry_module
import polisyos.fabric.connectors.sources.event_stream as event_stream_module
import polisyos.fabric.connectors.pool as pool_module
import polisyos.fabric.data_plane.streaming as streaming
import polisyos.fabric.data_plane.cursor_store as cursor_store_module
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.pool import ConnectionPool
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions, process_stream_dataset
from polisyos.fabric.data_plane.watermark import WindowPolicy

ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C3/raw/installed-net-ing/c694daaf')
FIXTURE_ROOT=ROOT/'multiprocess-fixtures-v2'
SOURCE=FIXTURE_ROOT/'events.jsonl'
CAS_ROOT=FIXTURE_ROOT/'cas'
SOURCE_ROOT=(ROOT/'source/policy-engine').resolve()
WHEEL=ROOT/'dist/policy_engine-0.1.0-py3-none-any.whl'
assert os.environ.get('PYTHONPATH') is None
assert sys.flags.isolated and sys.flags.safe_path
assert str(SOURCE_ROOT) not in [str(Path(p).resolve()) for p in sys.path if p]
assert '/Users/deniskopylov/.codex/worktrees/e02-c-net-ing-20261007/polisyos' not in [str(Path(p).resolve()) for p in sys.path if p]
modules={
 'polisyos':polisyos,
 'streaming':streaming,
 'registry':registry_module,
 'event_stream':event_stream_module,
 'cursor_store':cursor_store_module,
 'connector_pool':pool_module,
 'artifact_store':importlib.import_module('polisyos.core.artifacts.store'),
 'connector_base':importlib.import_module('polisyos.fabric.connectors.base'),
 'canon':importlib.import_module('polisyos.core.canon'),
 'cursor_contract':importlib.import_module('polisyos.core.contracts.cursor'),
 'watermark':importlib.import_module('polisyos.fabric.data_plane.watermark'),
}
wheel_map={
 'polisyos':'polisyos/__init__.py','streaming':'polisyos/fabric/data_plane/streaming.py',
 'registry':'polisyos/fabric/connectors/registry.py','event_stream':'polisyos/fabric/connectors/sources/event_stream.py',
 'cursor_store':'polisyos/fabric/data_plane/cursor_store.py','connector_pool':'polisyos/fabric/connectors/pool.py',
 'artifact_store':'polisyos/core/artifacts/store.py','connector_base':'polisyos/fabric/connectors/base.py',
 'canon':'polisyos/core/canon/__init__.py','cursor_contract':'polisyos/core/contracts/cursor.py',
 'watermark':'polisyos/fabric/data_plane/watermark.py',
}
module_identity={}
with zipfile.ZipFile(WHEEL) as z:
 for name,module in modules.items():
  path=Path(module.__file__).resolve()
  assert 'site-packages' in path.parts and SOURCE_ROOT not in path.parents,(name,str(path))
  member=wheel_map[name]; installed_sha=hashlib.sha256(path.read_bytes()).hexdigest()
  assert installed_sha==hashlib.sha256(z.read(member)).hexdigest(),name
  module_identity[name]={'origin':str(path),'wheel_member':member,'sha256':installed_sha,'byte_match':True}
assert 'pytest' not in sys.modules and 'hnswlib' not in sys.modules

class CountingEventStreamConnector(EventStreamConnector):
 def __init__(self): self.stream_reads=0; self.connect_handles=[]; self.disconnect_handles=[]
 async def connect(self,config:ConnectionConfig)->ConnectionHandle:
  handle=await super().connect(config); self.connect_handles.append(handle); return handle
 async def disconnect(self,handle:ConnectionHandle)->None:
  self.disconnect_handles.append(handle); await super().disconnect(handle)
 async def fetch_stream(self,handle:ConnectionHandle,request:Any):
  self.stream_reads+=1
  async for chunk in super().fetch_stream(handle,request): yield chunk

def runtime_options(cap:int)->StreamRuntimeOptions:
 return StreamRuntimeOptions(max_buffered_rows=cap,checkpoint_every_chunks=1,window_policy=WindowPolicy(strategy=WindowStrategy.SESSION,size=60,session_gap_seconds=2,timestamp_field='event_time'))
def clean_rows(batch:list[dict[str,Any]],**kwargs:Any):
 del kwargs
 return [dict(row) for row in batch],[],0
def make_registry(connector:EventStreamConnector):
 config=ConnectionConfig(url=SOURCE.as_uri(),headers={'X-Stream-ChunkSize':'2'},max_connections=1)
 registry=ConnectorRegistry(); registry.register(EventStreamConnector,config=config,factory=lambda:connector); return registry
def data_artifacts(store:FileSystemCAS,kind:str,dataset_id:str):
 found=[]
 for artifact_id in store.iter_artifact_ids():
  ref=str(artifact_id); manifest=store.get_manifest(ref)
  if manifest.kind!=kind: continue
  payload=from_canonical_bytes(store.get_bytes(ref))
  if payload.get('dataset_id')==dataset_id: found.append((ref,payload,manifest))
 return found
def optional_bytes(path:Path): return path.read_bytes() if path.exists() else None
def flatten_diff(a:Any,b:Any,path:str=''):
 if isinstance(a,dict) and isinstance(b,dict):
  out=[]
  for key in sorted(set(a)|set(b)):
   child=f'{path}.{key}' if path else str(key)
   if key not in a or key not in b: out.append(child)
   else: out.extend(flatten_diff(a[key],b[key],child))
  return out
 if isinstance(a,list) and isinstance(b,list):
  if len(a)!=len(b): return [path+'[length]']
  out=[]
  for i,(x,y) in enumerate(zip(a,b,strict=True)): out.extend(flatten_diff(x,y,f'{path}[{i}]'))
  return out
 return [] if a==b else [path]

def source_fixture():
 rows=[{'_message_id':f'event-{value}','value':value,'event_time':f'2024-01-01T00:00:0{second}+00:00'} for value,second in ((1,0),(2,1),(3,5))]
 lines=[json.dumps(row).encode('utf-8')+b'\n' for row in rows]
 return b''.join(lines),rows,lines

async def phase_prepare()->dict[str,Any]:
 FIXTURE_ROOT.mkdir(parents=True,exist_ok=True)
 source_bytes,rows,_lines=source_fixture(); SOURCE.write_bytes(source_bytes)
 connector=CountingEventStreamConnector(); registry=make_registry(connector)
 store=FileSystemCAS(CAS_ROOT); cursors=CursorStore(store)
 real_poll=streaming.StreamingSourceSession.poll; returned=0
 async def stop_after_first(session:streaming.StreamingSourceSession):
  nonlocal returned
  if returned==1: raise RuntimeError('controlled stop after two-row checkpoint')
  chunk=await real_poll(session)
  if chunk is not None: returned+=1
  return chunk
 streaming.StreamingSourceSession.poll=stop_after_first
 try:
  try:
   await process_stream_dataset(connector_id='stream.jsonl',dataset_id='net-ing-frontier',store=store,cursor_store=cursors,sanitize_rows=clean_rows,runtime_options=runtime_options(3),registry=registry)
  except RuntimeError as caught:
   assert str(caught)=='controlled stop after two-row checkpoint',repr(caught)
  else: raise AssertionError('fixture did not stop after the two-row checkpoint')
 finally:
  streaming.StreamingSourceSession.poll=real_poll
  await registry.shutdown_async()
 reopened=FileSystemCAS(CAS_ROOT); reopened_cursors=CursorStore(reopened)
 checkpoint=reopened_cursors.find_latest_stream_checkpoint('stream.jsonl','net-ing-frontier')
 assert checkpoint is not None
 decoded=tuple(tuple((str(pair[0]),pair[1]) for pair in json.loads(encoded)) for encoded in checkpoint.dedupe_keys)
 assert decoded==((('_message_id','event-1'),),(('_message_id','event-2'),)),decoded
 accumulator=streaming.StreamWindowAccumulator(runtime_options(3).window_policy)
 streaming._restore_stream_operator_state(checkpoint.metadata['operator_state'],accumulator=accumulator,ordering_state=streaming._StreamOrderingState())
 assert accumulator.buffered_rows()==2
 cursor=reopened_cursors.find_latest_cursor('stream.jsonl','net-ing-frontier'); assert cursor is not None
 return {'phase':'prepare','pid':os.getpid(),'process_interrupted_after_first_two_rows':True,'source_sha256':hashlib.sha256(source_bytes).hexdigest(),'source_bytes':len(source_bytes),'expected_rows':rows,'checkpoint_lifecycle':checkpoint.lifecycle_state.value,'checkpoint_offset':checkpoint.offset,'checkpoint_frontier_state':checkpoint.metadata.get('frontier_intent',{}).get('state'),'decoded_dedupe_keys':decoded,'restored_pending_rows':accumulator.buffered_rows(),'cursor_watermark':cursor.watermark_value,'cas_root':str(CAS_ROOT)}

async def phase_reject()->dict[str,Any]:
 source_bytes,rows,_lines=source_fixture(); assert SOURCE.read_bytes()==source_bytes
 store=FileSystemCAS(CAS_ROOT); cursors=CursorStore(store)
 checkpoint=cursors.find_latest_stream_checkpoint('stream.jsonl','net-ing-frontier'); assert checkpoint is not None
 cursor=cursors.find_latest_cursor('stream.jsonl','net-ing-frontier'); assert cursor is not None
 pending_refs=tuple(dict.fromkeys(str(ref) for entry in checkpoint.metadata['operator_state']['accumulator']['session_rows'] for ref in entry['refs']))
 predecessor_ids={str(ref) for ref in store.iter_artifact_ids()}
 predecessor_bytes={ref:store.get_bytes(ref) for ref in pending_refs}
 predecessor_manifests={ref:store.get_manifest(ref).model_dump(mode='json') for ref in pending_refs}
 stream_path=cursors._stream_index_path; cursor_path=cursors._index_path
 stream_before=optional_bytes(stream_path); cursor_before=optional_bytes(cursor_path)
 connector=CountingEventStreamConnector(); registry=make_registry(connector)
 poll_events=[]; flush_events=[]; commit_events=[]; writes=[]; acquisitions=[]; releases=[]
 real_poll=streaming.StreamingSourceSession.poll; real_flush=streaming.StreamWindowAccumulator.flush_with_refs
 real_commit=streaming._commit_stream_frontier; real_acquire=ConnectionPool.acquire_with_connector
 real_release=ConnectionPool.release; real_put_json=store.put_json; real_put_bytes=store.put_bytes
 async def poll(session:streaming.StreamingSourceSession): poll_events.append('poll'); return await real_poll(session)
 def flush(accumulator:streaming.StreamWindowAccumulator): flush_events.append('flush'); return real_flush(accumulator)
 async def commit(**kwargs:Any): commit_events.append('commit'); return await real_commit(**kwargs)
 async def acquire(pool:ConnectionPool[Any]):
  value=await real_acquire(pool); acquisitions.append((id(pool),value[1].session_id)); return value
 async def release(pool:ConnectionPool[Any],handle:Any):
  value=await real_release(pool,handle); releases.append((id(pool),handle.session_id)); return value
 def put_json(*args:Any,**kwargs:Any): writes.append('put_json'); return real_put_json(*args,**kwargs)
 def put_bytes(*args:Any,**kwargs:Any): writes.append('put_bytes'); return real_put_bytes(*args,**kwargs)
 streaming.StreamingSourceSession.poll=poll; streaming.StreamWindowAccumulator.flush_with_refs=flush
 streaming._commit_stream_frontier=commit; ConnectionPool.acquire_with_connector=acquire; ConnectionPool.release=release
 store.put_json=put_json; store.put_bytes=put_bytes
 try:
  try:
   await process_stream_dataset(connector_id='stream.jsonl',dataset_id='net-ing-frontier',store=store,cursor_store=cursors,sanitize_rows=clean_rows,runtime_options=runtime_options(1),registry=registry)
  except streaming.StreamCapacityError as caught:
   assert (caught.stage,caught.rows,caught.max_rows)==('restore',2,1),(caught.stage,caught.rows,caught.max_rows)
   refusal={'error':'StreamCapacityError','stage':caught.stage,'rows':caught.rows,'max_rows':caught.max_rows}
  else: raise AssertionError('lower restored cap did not refuse')
  after_checkpoint=cursors.find_latest_stream_checkpoint('stream.jsonl','net-ing-frontier')
  after_cursor=cursors.find_latest_cursor('stream.jsonl','net-ing-frontier')
  assert after_checkpoint is not None and after_checkpoint.model_dump(mode='json')==checkpoint.model_dump(mode='json')
  assert after_cursor is not None and after_cursor.model_dump(mode='json')==cursor.model_dump(mode='json')
  assert optional_bytes(stream_path)==stream_before and optional_bytes(cursor_path)==cursor_before
  assert {str(ref) for ref in store.iter_artifact_ids()}==predecessor_ids
  assert {ref:store.get_bytes(ref) for ref in pending_refs}==predecessor_bytes
  assert {ref:store.get_manifest(ref).model_dump(mode='json') for ref in pending_refs}==predecessor_manifests
  assert poll_events==[] and flush_events==[] and commit_events==[] and writes==[]
  assert Counter(acquisitions)==Counter(releases)
  assert connector.stream_reads==0
  assert SOURCE.read_bytes()==source_bytes
 finally:
  streaming.StreamingSourceSession.poll=real_poll; streaming.StreamWindowAccumulator.flush_with_refs=real_flush
  streaming._commit_stream_frontier=real_commit; ConnectionPool.acquire_with_connector=real_acquire; ConnectionPool.release=real_release
  store.put_json=real_put_json; store.put_bytes=real_put_bytes
  await registry.shutdown_async()
 return {'phase':'reject-lower-cap','pid':os.getpid(),'typed_refusal':refusal,'source_reads':connector.stream_reads,'poll':poll_events,'flush':flush_events,'frontier_commit':commit_events,'cas_writes':writes,'pool_handles_balanced':Counter(acquisitions)==Counter(releases),'checkpoint_unchanged':True,'cursor_unchanged':True,'stream_index_unchanged':True,'cursor_index_unchanged':True,'predecessor_ids_unchanged':True,'pending_chunk_bytes_unchanged':True,'pending_chunk_manifests_unchanged':True,'input_bytes_unchanged':True}

async def phase_resume()->dict[str,Any]:
 source_bytes,expected_rows,lines=source_fixture(); assert SOURCE.read_bytes()==source_bytes
 store=FileSystemCAS(CAS_ROOT); cursors=CursorStore(store)
 connector=CountingEventStreamConnector(); registry=make_registry(connector)
 try:
  result=await process_stream_dataset(connector_id='stream.jsonl',dataset_id='net-ing-frontier',store=store,cursor_store=cursors,sanitize_rows=clean_rows,runtime_options=runtime_options(3),registry=registry)
 finally: await registry.shutdown_async()
 chunks=data_artifacts(FileSystemCAS(CAS_ROOT),'fabric.stream_chunk','net-ing-frontier'); chunks.sort(key=lambda x:int(x[1]['chunk_index']))
 rows=[row for _ref,payload,_manifest in chunks for row in payload['data']]
 assert [json.loads(line.decode('utf-8')) for line in lines]==expected_rows
 assert rows==expected_rows,rows
 assert Counter(str(row['_message_id']) for row in rows)==Counter({'event-1':1,'event-2':1,'event-3':1})
 assert all(FileSystemCAS(CAS_ROOT).verify(ref).ok for ref,_payload,_manifest in chunks)
 by_message={str(row['_message_id']):ref for ref,payload,_manifest in chunks for row in payload['data']}
 windows=data_artifacts(FileSystemCAS(CAS_ROOT),'fabric.stream_window','net-ing-frontier'); windows.sort(key=lambda x:int(x[1]['ordinal']))
 memberships=[[str(row['_message_id']) for row in payload['data']] for _ref,payload,_manifest in windows]
 assert memberships==[['event-1','event-2'],['event-3']],memberships
 for _ref,payload,manifest in windows:
  message_ids=[str(row['_message_id']) for row in payload['data']]
  expected_inputs=tuple(dict.fromkeys(by_message[item] for item in message_ids))
  assert tuple(str(item.artifact_id) for item in manifest.inputs)==expected_inputs
  assert tuple(str(item) for item in payload['lineage']['contributor_chunk_refs'])==expected_inputs
  assert all(FileSystemCAS(CAS_ROOT).verify(ref).ok for ref in expected_inputs)
 reopened=FileSystemCAS(CAS_ROOT); reopened_cursors=CursorStore(reopened)
 checkpoint=reopened_cursors.find_latest_stream_checkpoint('stream.jsonl','net-ing-frontier')
 cursor=reopened_cursors.find_latest_cursor('stream.jsonl','net-ing-frontier')
 assert result.final_checkpoint is not None and checkpoint is not None and checkpoint.model_dump(mode='json')==result.final_checkpoint.model_dump(mode='json')
 assert checkpoint.lifecycle_state==StreamLifecycleState.CLOSED and checkpoint.metadata['frontier_intent']['state']=='committed'
 assert cursor is not None and cursor.watermark_value==str(checkpoint.offset)
 return {'phase':'compatible-resume','pid':os.getpid(),'source_sha256':hashlib.sha256(source_bytes).hexdigest(),'source_reads':connector.stream_reads,'persisted_rows':rows,'message_ids':[str(row['_message_id']) for row in rows],'chunk_refs':[ref for ref,_payload,_manifest in chunks],'window_memberships':memberships,'window_refs':[ref for ref,_payload,_manifest in windows],'all_chunks_verified':True,'final_checkpoint_state':checkpoint.lifecycle_state.value,'final_checkpoint_offset':checkpoint.offset,'final_frontier_state':checkpoint.metadata['frontier_intent']['state'],'final_checkpoint_rows_emitted':checkpoint.metadata.get('rows_emitted'),'final_checkpoint_window_count':checkpoint.metadata.get('window_count'),'cursor_watermark':cursor.watermark_value,'cas_root':str(CAS_ROOT)}

async def phase_replay()->dict[str,Any]:
 source_bytes,expected_rows,_lines=source_fixture(); assert SOURCE.read_bytes()==source_bytes
 store=FileSystemCAS(CAS_ROOT); cursors=CursorStore(store)
 chunks_before=data_artifacts(store,'fabric.stream_chunk','net-ing-frontier'); chunks_before.sort(key=lambda x:int(x[1]['chunk_index']))
 windows_before=data_artifacts(store,'fabric.stream_window','net-ing-frontier'); windows_before.sort(key=lambda x:int(x[1]['ordinal']))
 checkpoint_before=cursors.find_latest_stream_checkpoint('stream.jsonl','net-ing-frontier'); cursor_before=cursors.find_latest_cursor('stream.jsonl','net-ing-frontier')
 assert checkpoint_before is not None and cursor_before is not None
 checkpoint_dump_before=checkpoint_before.model_dump(mode='json'); cursor_dump_before=cursor_before.model_dump(mode='json')
 ids_before={str(ref) for ref in store.iter_artifact_ids()}; stream_before=optional_bytes(cursors._stream_index_path); cursor_index_before=optional_bytes(cursors._index_path)
 connector=CountingEventStreamConnector(); registry=make_registry(connector)
 try:
  result=await process_stream_dataset(connector_id='stream.jsonl',dataset_id='net-ing-frontier',store=store,cursor_store=cursors,sanitize_rows=clean_rows,runtime_options=runtime_options(3),registry=registry)
 finally: await registry.shutdown_async()
 after_store=FileSystemCAS(CAS_ROOT); after_cursors=CursorStore(after_store)
 chunks_after=data_artifacts(after_store,'fabric.stream_chunk','net-ing-frontier'); chunks_after.sort(key=lambda x:int(x[1]['chunk_index']))
 windows_after=data_artifacts(after_store,'fabric.stream_window','net-ing-frontier'); windows_after.sort(key=lambda x:int(x[1]['ordinal']))
 checkpoint_after=after_cursors.find_latest_stream_checkpoint('stream.jsonl','net-ing-frontier'); cursor_after=after_cursors.find_latest_cursor('stream.jsonl','net-ing-frontier')
 assert checkpoint_after is not None and cursor_after is not None
 checkpoint_dump_after=checkpoint_after.model_dump(mode='json'); cursor_dump_after=cursor_after.model_dump(mode='json')
 ids_after={str(ref) for ref in after_store.iter_artifact_ids()}
 assert result.chunk_refs==[] and result.window_refs==[] and result.rows_emitted==0
 assert {r for r,_,_ in chunks_before}=={r for r,_,_ in chunks_after}
 assert {r for r,_,_ in windows_before}=={r for r,_,_ in windows_after}
 all_rows=[row for _ref,payload,_manifest in chunks_after for row in payload['data']]
 assert all_rows==expected_rows
 assert checkpoint_after.lifecycle_state==checkpoint_before.lifecycle_state==StreamLifecycleState.CLOSED
 assert checkpoint_after.offset==checkpoint_before.offset
 assert cursor_after.watermark_value==cursor_before.watermark_value
 return {'phase':'replay-after-process-restart','pid':os.getpid(),'source_reads':connector.stream_reads,'replay_rows_emitted':result.rows_emitted,'replay_chunk_refs':result.chunk_refs,'replay_window_refs':result.window_refs,'chunk_refs_unchanged':True,'window_refs_unchanged':True,'persisted_rows_unchanged':True,'closed_state_unchanged':True,'offset_unchanged':True,'cursor_watermark_unchanged':True,'checkpoint_changed_paths':flatten_diff(checkpoint_dump_before,checkpoint_dump_after),'cursor_changed_paths':flatten_diff(cursor_dump_before,cursor_dump_after),'new_all_artifact_ids':sorted(ids_after-ids_before),'removed_all_artifact_ids':sorted(ids_before-ids_after),'stream_index_changed':stream_before!=optional_bytes(after_cursors._stream_index_path),'cursor_index_changed':cursor_index_before!=optional_bytes(after_cursors._index_path),'checkpoint_rows_emitted_before':checkpoint_dump_before['metadata'].get('rows_emitted'),'checkpoint_rows_emitted_after':checkpoint_dump_after['metadata'].get('rows_emitted'),'checkpoint_window_count_before':checkpoint_dump_before['metadata'].get('window_count'),'checkpoint_window_count_after':checkpoint_dump_after['metadata'].get('window_count'),'cursor_metadata_rows_before':cursor_dump_before['metadata'].get('rows_emitted'),'cursor_metadata_rows_after':cursor_dump_after['metadata'].get('rows_emitted'),'source_unchanged':SOURCE.read_bytes()==source_bytes}

phase=sys.argv[1]
if phase=='prepare': result=asyncio.run(phase_prepare())
elif phase=='reject': result=asyncio.run(phase_reject())
elif phase=='resume': result=asyncio.run(phase_resume())
elif phase=='replay': result=asyncio.run(phase_replay())
else: raise SystemExit(f'unknown phase: {phase}')
result['profile']={'python':sys.version,'executable':str(Path(sys.executable).resolve()),'pid':os.getpid(),'isolated':bool(sys.flags.isolated),'PYTHONPATH':os.environ.get('PYTHONPATH'),'pytest_imported':'pytest' in sys.modules,'hnswlib_imported':'hnswlib' in sys.modules,'module_identity':module_identity,'sys_path':sys.path}
print(json.dumps(result,sort_keys=True,separators=(',',':')))
