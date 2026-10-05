from datetime import UTC, datetime, timedelta
import importlib

registry_module = importlib.import_module('polisyos.fabric.connectors.resilience._bounded_registry')
circuit_module = importlib.import_module('polisyos.fabric.connectors.resilience.circuit_breaker')
clock = [0.0]
registry_module._monotonic = lambda: clock[0]
circuit_module._monotonic = lambda: clock[0]
circuit_module._utc_now = lambda: datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=clock[0])
Registry = registry_module.BoundedResourceRegistry
CapacityError = registry_module.BoundedResourceRegistryCapacityError
Circuit = circuit_module.CircuitBreaker
Config = circuit_module.CircuitBreakerConfig
State = circuit_module.CircuitState

def breaker(key):
    return Circuit(circuit_id=key, config=Config(failure_threshold=1, min_throughput=1,
                   timeout_seconds=1.0, half_open_max_calls=1, success_threshold=1,
                   window_size_seconds=1.0))

def active_breaker(key):
    value = breaker(key)
    value.record_failure()
    return value

registry = Registry(max_items=1, ttl_seconds=0.5)
first = registry.get_or_create('active', lambda: active_breaker('active'))
clock[0] = 1.0
lease = first.acquire_attempt()
assert lease is not None and lease.owns_half_open_slot and first.state is State.HALF_OPEN
clock[0] = 10.0
for i in range(24):
    registry.get_or_create(f'pressure-{i}', lambda: breaker(f'pressure-{i}'))
    current = registry.get_or_create('active', lambda: breaker('active'))
    assert current is first and current.acquire_attempt() is None
    assert len(registry.snapshot()) <= 2
try:
    registry.get_or_create('another-protected', lambda: active_breaker('another-protected'))
except CapacityError:
    pass
else:
    raise AssertionError('protected-capacity overflow admitted a second regulator')
first.record_success(lease)
assert first.state is State.CLOSED
clock[0] = 12.0
replacement = registry.get_or_create('active', lambda: breaker('active'))
assert replacement is not first and replacement.state is State.CLOSED
fresh_lease = replacement.acquire_attempt()
assert fresh_lease is not None
replacement.record_success(fresh_lease)
print('PASS B93 active HALF_OPEN lease survives TTL and 24-key pressure; extra protected key receives typed refusal; same-key second lease denied; quiescent state is reclaimed and real replacement acquires')
print('runtime modules:', registry_module.__file__, circuit_module.__file__)
