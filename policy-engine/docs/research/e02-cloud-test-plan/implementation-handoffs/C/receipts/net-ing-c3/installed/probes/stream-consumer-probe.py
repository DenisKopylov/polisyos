from __future__ import annotations
import asyncio, hashlib, importlib, json, os, sys, tempfile, zipfile
from pathlib import Path
from typing import Any
import polisyos
import polisyos.fabric.connectors.registry as registry_module
import polisyos.fabric.connectors.sources.event_stream as event_stream_module
import polisyos.fabric.data_plane.cursor_store as cursor_store_module
import polisyos.fabric.data_plane.streaming as streaming
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.cursor import StreamLifecycleState, WindowStrategy
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import CursorStore, CursorStoreError
from polisyos.fabric.data_plane.streaming import StreamingSourceSession, StreamRuntimeOptions, process_stream_dataset
from polisyos.fabric.data_plane.watermark import WindowPolicy

ROOT=Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C3/raw/installed-net-ing/c694daaf")
SOURCE_ROOT=(ROOT/"source/policy-engine").resolve()
WHEEL=ROOT/"dist/policy_engine-0.1.0-py3-none-any.whl"
assert os.environ.get("PYTHONPATH") is None
assert bool(sys.flags.isolated) and bool(sys.flags.safe_path)
assert str(SOURCE_ROOT) not in [str(Path(p).resolve()) for p in sys.path if p]
modules={
 "polisyos":polisyos,
 "streaming":streaming,
 "registry":registry_module,
 "event_stream":event_stream_module,
 "cursor_store":cursor_store_module,
}
wheel_map={
 "polisyos":"polisyos/__init__.py",
 "streaming":"polisyos/fabric/data_plane/streaming.py",
 "registry":"polisyos/fabric/connectors/registry.py",
 "event_stream":"polisyos/fabric/connectors/sources/event_stream.py",
 "cursor_store":"polisyos/fabric/data_plane/cursor_store.py",
}
modules.update({
 "artifact_store":importlib.import_module("polisyos.core.artifacts.store"),
 "connector_base":importlib.import_module("polisyos.fabric.connectors.base"),
 "connector_pool":importlib.import_module("polisyos.fabric.connectors.pool"),
 "canon":importlib.import_module("polisyos.core.canon"),
 "cursor_contract":importlib.import_module("polisyos.core.contracts.cursor"),
 "watermark":importlib.import_module("polisyos.fabric.data_plane.watermark"),
})
wheel_map.update({
 "artifact_store":"polisyos/core/artifacts/store.py",
 "connector_base":"polisyos/fabric/connectors/base.py",
 "connector_pool":"polisyos/fabric/connectors/pool.py",
 "canon":"polisyos/core/canon/__init__.py",
 "cursor_contract":"polisyos/core/contracts/cursor.py",
 "watermark":"polisyos/fabric/data_plane/watermark.py",
})
module_identity={}
with zipfile.ZipFile(WHEEL) as z:
 for name,module in modules.items():
  path=Path(module.__file__).resolve()
  assert "site-packages" in path.parts and SOURCE_ROOT not in path.parents, (name,str(path))
  member=wheel_map[name]
  wheel_sha=hashlib.sha256(z.read(member)).hexdigest()
  installed_sha=hashlib.sha256(path.read_bytes()).hexdigest()
  assert installed_sha==wheel_sha,(name,installed_sha,wheel_sha)
  module_identity[name]={"origin":str(path),"wheel_member":member,"sha256":installed_sha,"byte_match":True}
assert "pytest" not in sys.modules and "hnswlib" not in sys.modules

class DisconnectFaultEventStream(EventStreamConnector):
 def __init__(self, failures:int):
  self.disconnect_failures=failures
  self.connect_handles:list[ConnectionHandle]=[]
  self.disconnect_handles:list[ConnectionHandle]=[]
  self.stream_reads=0
 async def connect(self,config:ConnectionConfig)->ConnectionHandle:
  handle=await super().connect(config)
  self.connect_handles.append(handle)
  return handle
 async def disconnect(self,handle:ConnectionHandle)->None:
  self.disconnect_handles.append(handle)
  if self.disconnect_failures:
   self.disconnect_failures-=1
   raise RuntimeError("controlled physical disconnect failure")
  await super().disconnect(handle)
 async def fetch_stream(self,handle:ConnectionHandle,request:Any):
  self.stream_reads+=1
  async for chunk in super().fetch_stream(handle,request):
   yield chunk

class ProcessDeath(BaseException):
 pass

def _registry(source:Path,connector:EventStreamConnector)->tuple[ConnectorRegistry,ConnectionConfig]:
 config=ConnectionConfig(url=source.as_uri(),headers={"X-Stream-ChunkSize":"1"},max_connections=1)
 registry=ConnectorRegistry()
 registry.register(EventStreamConnector,config=config,factory=lambda:connector)
 return registry,config

def _pending_owner(registry:ConnectorRegistry,handle:ConnectionHandle):
 owners=tuple(registry._pending_startup_cleanup.values())
 assert len(owners)==1, f"expected one registry-held cleanup owner, found {len(owners)}"
 connector_id,pool=owners[0]
 assert connector_id==registry.get_entry("stream.jsonl").fqid
 assert pool._pending_cleanup[handle.session_id].handle is handle
 assert pool._pending_cleanup[handle.session_id].pending_permit is False
 assert pool._semaphore._value==1
 return pool

async def sanitizer_failure_retry(root:Path)->dict[str,Any]:
 name="cleanup-recovery"
 source=root/f"{name}.jsonl"
 source.write_text('{"_message_id":"event-a","value":1}\n',encoding="utf-8")
 connector=DisconnectFaultEventStream(2)
 registry,config=_registry(source,connector)
 store=FileSystemCAS(root/f"{name}-cas")
 primary=RuntimeError("primary sanitizer failure")
 def fail(_batch:Any,**kwargs:Any):
  del kwargs
  raise primary
 try:
  try:
   await process_stream_dataset(connector_id="stream.jsonl",dataset_id=name,store=store,cursor_store=CursorStore(store),sanitize_rows=fail,runtime_options=StreamRuntimeOptions(batch_size=1),registry=registry)
  except RuntimeError as caught:
   assert caught is primary
   assert "stream session final cleanup failed" in " ".join(getattr(caught,"__notes__",()))
  else:
   raise AssertionError("primary sanitizer failure was not raised")
  assert connector.stream_reads==1 and len(connector.connect_handles)==1
  handle=connector.connect_handles[0]
  assert connector.disconnect_handles==[handle]
  pool=_pending_owner(registry,handle)
  try:
   await registry.shutdown_async()
  except RuntimeError as retry_error:
   assert "Connection cleanup remains pending" in str(retry_error)
  else:
   raise AssertionError("registry cleanup retry did not preserve the controlled failure")
  assert tuple(registry._pending_startup_cleanup.values())==((registry.get_entry("stream.jsonl").fqid,pool),)
  assert pool._pending_cleanup[handle.session_id].handle is handle
  connector.disconnect_failures=0
  await registry.shutdown_async()
  assert connector.disconnect_handles==[handle,handle,handle]
  assert all(item is handle for item in connector.disconnect_handles)
  assert registry._pending_startup_cleanup=={} and pool._pending_cleanup=={} and pool._semaphore._value==1
  return {"status":"pass","primary_error_identity_preserved":True,"source_reads":connector.stream_reads,"disconnect_attempts":len(connector.disconnect_handles),"same_physical_handle_all_attempts":True,"registry_retry_owner_cleared":True,"cas_root":str(root/f"{name}-cas")}
 finally:
  connector.disconnect_failures=0
  await registry.shutdown_async()

async def task_cancellation_retry(root:Path)->dict[str,Any]:
 name="actual-task-cancel"
 source=root/f"{name}.jsonl"
 source.write_text('{"_message_id":"event-a","value":1}\n',encoding="utf-8")
 connector=DisconnectFaultEventStream(1)
 registry,config=_registry(source,connector)
 store=FileSystemCAS(root/f"{name}-cas")
 first_source_yield=asyncio.Event()
 release_poll=asyncio.Event()
 original_poll=StreamingSourceSession.poll
 async def pause_after_real_yield(session:StreamingSourceSession):
  chunk=await original_poll(session)
  if chunk is not None and not first_source_yield.is_set():
   first_source_yield.set()
   await release_poll.wait()
  return chunk
 StreamingSourceSession.poll=pause_after_real_yield
 task=asyncio.create_task(process_stream_dataset(connector_id="stream.jsonl",dataset_id=name,store=store,cursor_store=CursorStore(store),sanitize_rows=lambda rows,**kwargs:([dict(row) for row in rows],[],0),runtime_options=StreamRuntimeOptions(batch_size=1),registry=registry))
 try:
  await asyncio.wait_for(first_source_yield.wait(),timeout=5)
  assert connector.stream_reads==1 and len(connector.connect_handles)==1
  handle=connector.connect_handles[0]
  assert task.cancel()
  try:
   await task
  except asyncio.CancelledError as caught:
   assert any("stream session final cleanup failed" in note for note in getattr(caught,"__notes__",()))
  else:
   raise AssertionError("cancelled stream task did not propagate cancellation")
  assert task.cancelled() and connector.disconnect_handles==[handle]
  pool=_pending_owner(registry,handle)
  connector.disconnect_failures=0
  await registry.shutdown_async()
  assert connector.disconnect_handles==[handle,handle] and connector.disconnect_handles[1] is handle
  assert registry._pending_startup_cleanup=={} and pool._pending_cleanup=={} and pool._semaphore._value==1
  return {"status":"pass","cancel_after_actual_source_yield":True,"source_reads":connector.stream_reads,"disconnect_attempts":len(connector.disconnect_handles),"same_physical_handle_retry":True,"registry_retry_owner_cleared":True,"cas_root":str(root/f"{name}-cas")}
 finally:
  StreamingSourceSession.poll=original_poll
  if not task.done():
   task.cancel()
   await asyncio.gather(task,return_exceptions=True)
  connector.disconnect_failures=0
  await registry.shutdown_async()

def dataset_artifacts(store:FileSystemCAS,kind:str,dataset_id:str):
 result=[]
 for artifact_id in store.iter_artifact_ids():
  manifest=store.get_manifest(artifact_id)
  if manifest.kind!=kind:
   continue
  payload=from_canonical_bytes(store.get_bytes(str(artifact_id)))
  if payload.get("dataset_id")==dataset_id:
   result.append((str(artifact_id),payload,manifest))
 return result

async def commit_reopen(root:Path)->dict[str,Any]:
 name="frontier-crash-after-commit"
 expected_rows=[{"_message_id":x,"event_id":x,"value":n} for x,n in (("a",1),("b",2),("c",3))]
 raw_lines=[b" \t"+json.dumps(row,sort_keys=True).encode("utf-8")+b" \t\r\n" for row in expected_rows]
 source_bytes=b"".join(raw_lines)
 parsed=[json.loads(line.strip().decode("utf-8")) for line in raw_lines]
 assert parsed==expected_rows
 source=root/f"{name}.jsonl"
 source.write_bytes(source_bytes)
 connector=DisconnectFaultEventStream(0)
 registry,_config=_registry(source,connector)
 cas_root=root/f"{name}-cas"
 source_reads=[]
 original_read=event_stream_module.read_location_bytes
 original_commit=streaming._commit_stream_frontier
 async def capture_source_read(*args:Any,**kwargs:Any):
  payload,headers=await original_read(*args,**kwargs)
  source_reads.append(bytes(payload))
  return payload,headers
 injected=False
 async def crash_after_commit(**kwargs:Any):
  nonlocal injected
  committed=await original_commit(**kwargs)
  if not injected:
   injected=True
   raise ProcessDeath("crash after committed frontier persistence")
  return committed
 event_stream_module.read_location_bytes=capture_source_read
 streaming._commit_stream_frontier=crash_after_commit
 options=StreamRuntimeOptions(checkpoint_every_chunks=1,window_policy=WindowPolicy(strategy=WindowStrategy.COUNT,size=2))
 first_store=FileSystemCAS(cas_root)
 try:
  try:
   await process_stream_dataset(connector_id="stream.jsonl",dataset_id=name,store=first_store,cursor_store=CursorStore(first_store),sanitize_rows=lambda rows,**kwargs:([dict(row) for row in rows],[],0),runtime_options=options,registry=registry)
  except ProcessDeath:
   pass
  else:
   raise AssertionError("after-commit process-death control did not interrupt the producer")
 finally:
  streaming._commit_stream_frontier=original_commit
  event_stream_module.read_location_bytes=original_read
 crash_store=FileSystemCAS(cas_root)
 crash_cursors=CursorStore(crash_store)
 crash_checkpoint=crash_cursors.find_latest_stream_checkpoint("stream.jsonl",name)
 assert crash_checkpoint is not None
 assert crash_checkpoint.metadata["frontier_intent"]["state"]=="committed"
 crash_cursor=crash_cursors.find_latest_cursor("stream.jsonl",name)
 assert crash_cursor is not None and crash_cursor.watermark_value=="0"
 pre_resume_chunks=dataset_artifacts(crash_store,"fabric.stream_chunk",name)
 assert len(pre_resume_chunks)==1 and pre_resume_chunks[0][1]["data"]==[expected_rows[0]]
 assert connector.stream_reads==1 and source_reads and all(hashlib.sha256(x).digest()==hashlib.sha256(source_bytes).digest() for x in source_reads)
 resumed_store=FileSystemCAS(cas_root)
 resumed_cursors=CursorStore(resumed_store)
 result=await process_stream_dataset(connector_id="stream.jsonl",dataset_id=name,store=resumed_store,cursor_store=resumed_cursors,sanitize_rows=lambda rows,**kwargs:([dict(row) for row in rows],[],0),runtime_options=options,registry=registry)
 assert connector.stream_reads==2 and len(source_reads)>=1
 assert result.final_checkpoint is not None
 assert result.final_checkpoint.lifecycle_state==StreamLifecycleState.CLOSED
 assert result.final_checkpoint.offset==2
 assert result.final_checkpoint.metadata["frontier_intent"]["state"]=="committed"
 chunks=dataset_artifacts(resumed_store,"fabric.stream_chunk",name)
 chunks.sort(key=lambda item:int(item[1]["chunk_index"]))
 assert [int(payload["chunk_index"]) for _ref,payload,_manifest in chunks]==[0,1,2]
 actual_rows=[row for _ref,payload,_manifest in chunks for row in payload["data"]]
 assert actual_rows==expected_rows,(actual_rows,expected_rows)
 chunk_by_message={str(row["_message_id"]):ref for ref,payload,_manifest in chunks for row in payload["data"]}
 windows=dataset_artifacts(resumed_store,"fabric.stream_window",name)
 windows.sort(key=lambda item:int(item[1]["ordinal"]))
 window_memberships=[[str(row["_message_id"]) for row in payload["data"]] for _ref,payload,_manifest in windows]
 assert window_memberships==[["a","b"],["c"]]
 for _ref,payload,manifest in windows:
  ids=[str(row["_message_id"]) for row in payload["data"]]
  expected_inputs=tuple(dict.fromkeys(chunk_by_message[item] for item in ids))
  assert tuple(str(item.artifact_id) for item in manifest.inputs)==expected_inputs
  assert tuple(payload["lineage"]["contributor_chunk_refs"])==expected_inputs
 reopened_store=FileSystemCAS(cas_root)
 reopened_cursors=CursorStore(reopened_store)
 latest_checkpoint=reopened_cursors.find_latest_stream_checkpoint("stream.jsonl",name)
 latest_cursor=reopened_cursors.find_latest_cursor("stream.jsonl",name)
 assert latest_checkpoint is not None and latest_checkpoint.model_dump(mode="json")==result.final_checkpoint.model_dump(mode="json")
 assert latest_cursor is not None and latest_cursor.watermark_value=="2"
 await registry.shutdown_async()
 return {"status":"pass","crash_state":"committed checkpoint and cursor persisted after first frontier","pre_resume_chunk_rows":pre_resume_chunks[0][1]["data"],"resumed_source_reads":connector.stream_reads,"raw_source_sha256":hashlib.sha256(source_bytes).hexdigest(),"expected_rows":expected_rows,"reopened_chunk_indexes":[int(payload["chunk_index"]) for _ref,payload,_manifest in chunks],"window_memberships":window_memberships,"chunk_refs":[ref for ref,_payload,_manifest in chunks],"window_refs":[ref for ref,_payload,_manifest in windows],"latest_checkpoint_equals_final_result":True,"reopened_cursor_watermark":latest_cursor.watermark_value,"cas_root":str(cas_root)}

async def main()->dict[str,Any]:
 root=ROOT/"stream-fixtures"
 root.mkdir(parents=True,exist_ok=True)
 return {"profile":{"python":sys.version,"executable":str(Path(sys.executable).resolve()),"isolated":bool(sys.flags.isolated),"PYTHONPATH":os.environ.get("PYTHONPATH"),"pytest_imported":"pytest" in sys.modules,"hnswlib_imported":"hnswlib" in sys.modules,"module_identity":module_identity,"sys_path":sys.path},"failure_cleanup_same_handle_retry":await sanitizer_failure_retry(root),"cancellation_cleanup_same_handle_retry":await task_cancellation_retry(root),"actual_commit_and_reopen_readback":await commit_reopen(root)}

print(json.dumps(asyncio.run(main()),sort_keys=True,separators=(",",":")))
