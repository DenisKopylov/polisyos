from __future__ import annotations
import asyncio, json, os, sys
from pathlib import Path
from typing import Any
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.streaming import StreamingSourceSession, StreamRuntimeOptions, process_stream_dataset

ROOT=Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C3/raw/installed-current/07bbb61/stream-fixtures/mutant")
class DisconnectFaultEventStream(EventStreamConnector):
 def __init__(self):
  self.disconnect_failures=1
  self.disconnect_handles:list[ConnectionHandle]=[]
 async def disconnect(self,handle:ConnectionHandle)->None:
  self.disconnect_handles.append(handle)
  if self.disconnect_failures:
   self.disconnect_failures-=1
   raise RuntimeError("controlled physical disconnect failure")
  await super().disconnect(handle)

async def main()->dict[str,Any]:
 ROOT.mkdir(parents=True,exist_ok=True)
 source=ROOT/"mutant.jsonl"
 source.write_text('{"_message_id":"mutant-event","value":1}\n',encoding="utf-8")
 config=ConnectionConfig(url=source.as_uri(),headers={"X-Stream-ChunkSize":"1"},max_connections=1)
 connector=DisconnectFaultEventStream()
 registry=ConnectorRegistry()
 registry.register(EventStreamConnector,config=config,factory=lambda:connector)
 sessions=[]
 original_create=StreamingSourceSession.create
 async def capture(cls:type[StreamingSourceSession],**kwargs:Any):
  session=await original_create(**kwargs)
  sessions.append(session)
  return session
 StreamingSourceSession.create=classmethod(capture)
 original_retain=ConnectorRegistry._retain_pending_startup_cleanup
 def remove_owner(self:ConnectorRegistry,connector_id:str,pool:Any)->None:
  del self,connector_id,pool
 ConnectorRegistry._retain_pending_startup_cleanup=remove_owner
 primary=RuntimeError("mutant primary sanitizer failure")
 def fail(_rows:Any,**kwargs:Any):
  del kwargs
  raise primary
 store=FileSystemCAS(ROOT/"cas")
 try:
  try:
   await process_stream_dataset(connector_id="stream.jsonl",dataset_id="mutant",store=store,cursor_store=CursorStore(store),sanitize_rows=fail,runtime_options=StreamRuntimeOptions(batch_size=1),registry=registry)
  except RuntimeError as caught:
   assert caught is primary
   notes=" ".join(getattr(caught,"__notes__",()))
  else:
   raise AssertionError("mutant primary failure missing")
  assert "stream session final cleanup failed" in notes
  assert len(sessions)==1
  session=sessions[0]
  handle=connector.disconnect_handles[0]
  assert session.pool._pending_cleanup[handle.session_id].handle is handle
  registry_owner_count=len(registry._pending_startup_cleanup)
  assert registry_owner_count==0
  try:
   owners=tuple(registry._pending_startup_cleanup.values())
   assert len(owners)==1 and owners[0][1] is session.pool
  except AssertionError:
   caught_property_failure=True
  else:
   caught_property_failure=False
  assert caught_property_failure and "stream session final cleanup failed" in notes
  return {"status":"pass","mutant":"replaced ConnectorRegistry._retain_pending_startup_cleanup with no-op for this process only","cleanup_marker_still_present":True,"same_pool_still_has_pending_handle":True,"registry_owner_count_after_mutation":registry_owner_count,"owner_property_assertion_failed_as_expected":caught_property_failure,"pytest_imported":"pytest" in sys.modules,"PYTHONPATH":os.environ.get("PYTHONPATH")}
 finally:
  ConnectorRegistry._retain_pending_startup_cleanup=original_retain
  StreamingSourceSession.create=original_create
  connector.disconnect_failures=0
  if sessions:
   await sessions[0].pool.close_all()
  await registry.shutdown_async()

print(json.dumps(asyncio.run(main()),sort_keys=True,separators=(",",":")))
