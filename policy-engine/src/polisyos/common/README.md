# Common (`polisyos.common`)

`polisyos.common` is the low-level utility layer for PolicyOS. It contains shared bootstrap,
logging, serialization, time, async, and local migration helpers with no domain logic.

## Role in System

- **Depends on:** the standard library and a few optional runtime packages.
- **Used by:** nearly every higher layer, especially `core`, `fabric`, `foundry`, `scientist`, `runtime`, `lex`, and `scholar`.
- **Boundary function:** stays at the bottom of the dependency graph and must remain stable.

## Key Concepts

- **Bootstrap** - `config.py` and `jax_env.py` handle early runtime setup.
- **Logging** - `logger.py` provides the shared logging facade.
- **Async bridge** - `async_tools.py` runs coroutines from synchronous code.
- **Serialization** - `serialization.py` canonicalizes Python objects into JSON-friendly data.
- **Time utilities** - `timestamps.py` keeps UTC parsing/formatting consistent.
- **Environment parsing** - `env_parsing.py` supports bootstrap configuration parsing, even though it is not part of the top-level facade.
- **Local migrations** - `migrations/` owns only the artifacts this package is responsible for.

## Public API

- `async_tools`
- `config`
- `jax_env`
- `logger`
- `serialization`
- `timestamps`
- `migrations`

## Current State

- Last updated: 2026-04-03
- The tree now includes `env_parsing.py` alongside the legacy bootstrap and utility helpers.
- `common.migrations` remains intentionally separate from `polisyos.ir.migrations`.
