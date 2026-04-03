# Observability (`polisyos.core.observability`)

`core.observability` is the telemetry layer shared by the rest of PolicyOS. It bundles tracing,
metrics, structured logging, context propagation, determinism helpers, and LLM pricing support.

The package is designed to degrade gracefully: if the OTel SDK is unavailable, the public API
still works through noop implementations.

## Role in System

- **Depends on:** the standard runtime stack plus optional OTel packages.
- **Used by:** `core.llm`, `core.security`, `foundry`, `scientist`, `runtime`, and any code that needs shared telemetry.
- **Boundary function:** gives the rest of the codebase one telemetry model instead of many small wrappers.

## Key Concepts

- **Tracer facade** - `tracer.py` centralizes span creation and sampling helpers.
- **Decorators** - `traced` and `traced_method` make instrumentation easy to apply.
- **Metrics registry** - `metrics_parts.py` carries the real registry and domain recording helpers.
- **Structured logging** - `logs.py` keeps trace correlation in log output.
- **Propagation** - `propagation.py` handles header/thread/async context transfer.
- **Pricing and determinism** - `pricing.py` and `determinism.py` keep execution metadata consistent.

## Public API

- `get_metrics`
- `traced`
- `traced_method`
- `OTelConfig`
- `DeterminismTier`
- `estimate_llm_cost_usd`

## Current State

- Last updated: 2026-04-03
- The tree now includes `_metrics_helpers.py` and `_metrics_registry_base.py` alongside the main metrics facade.
- Core callers still get graceful degradation when optional tracing dependencies are absent.
