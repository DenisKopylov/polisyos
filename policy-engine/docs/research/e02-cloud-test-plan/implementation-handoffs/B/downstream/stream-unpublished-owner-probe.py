"""Read-only consumer discriminator: pool pending cleanup before stream handle publication."""
import asyncio, json, sys
from unittest.mock import patch
from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.data_plane import streaming

class Connector:
    def __init__(self):
        self.fail_disconnect = "--disconnect-ok" not in sys.argv
        self.disconnect_calls = 0
    async def connect(self, config):
        return ConnectionHandle(connector_id="stream.jsonl", config=config)
    async def health_check(self, handle):
        await asyncio.Event().wait()
        return HealthStatus(healthy=True)
    async def disconnect(self, handle):
        self.disconnect_calls += 1
        if self.fail_disconnect:
            raise OSError("persistent physical disconnect failure")

async def main():
    connector = Connector()
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    registry.register(EventStreamConnector, config=ConnectionConfig(url="https://stream.invalid",max_connections=1), factory=lambda: connector)
    pools=[]
    def pool_factory(**kwargs):
        obj=ConnectionPool(**kwargs); pools.append(obj); return obj
    def config_factory(**kwargs):
        return PoolConfig(**kwargs,acquire_timeout_seconds=0.03,connection_timeout_seconds=0.5)
    try:
        with patch.object(streaming,"PoolConfig",side_effect=config_factory), patch.object(streaming,"ConnectionPool",side_effect=pool_factory):
            try:
                await asyncio.wait_for(streaming.StreamingSourceSession.create(connector_id="stream.jsonl",dataset_id="unpublished-health",registry=registry),timeout=0.5)
            except BaseException as exc:
                failure={"type":type(exc).__name__,"message":str(exc),"notes":getattr(exc,"__notes__",[])}
            else:
                raise AssertionError("health-gated acquisition unexpectedly succeeded")
        pool=pools[0]
        retained=len(registry._pending_startup_cleanup)
        pending=[{"pending_permit":p.pending_permit,"closed":p.closed} for p in pool._pending_cleanup.values()]
        calls_before_retry=connector.disconnect_calls
        connector.fail_disconnect=False
        await registry.shutdown_async()
        retry_disconnects=connector.disconnect_calls-calls_before_retry
        consumer_completed=not pool._pending_cleanup and pool._semaphore._value==1
        print(json.dumps({"pool_source":__import__("polisyos.fabric.connectors.pool",fromlist=["__file__"]).__file__,"streaming_source":streaming.__file__,"failure":failure,"pending_pool_owners":pending,"registry_pending_pool_count":retained,"active_acquires":pool._active_acquires,"semaphore_value":pool._semaphore._value,"disconnect_calls":connector.disconnect_calls,"registry_retry_disconnects":retry_disconnects,"pool_pending_after_registry_retry":len(pool._pending_cleanup),"property_actual_registry_cleanup_completes":consumer_completed},indent=2))
        return not consumer_completed
    finally:
        connector.fail_disconnect=False
        for pool in pools: await pool.close_all()
        await registry.shutdown_async()
        ConnectorRegistry.reset_instance()

raise SystemExit(asyncio.run(main()))
