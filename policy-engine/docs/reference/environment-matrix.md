# Environment Matrix

Related guides: [Installation](../how-to/install.md), [Dependency Platform](dependency-platform.md).

Owner: `@platform-owners`
Source of truth: `pyproject.toml`, `.python-version`, `.nvmrc`, and `.github/workflows/{abi,arch,docs,perf,foundry-release-gate,replay,signatures}.yml`

This document is the reference point for contributor setup, CI design, and bug
triage.

## Support Levels

| Level       | Meaning                                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------------------------- |
| Supported   | Covered by current contributor docs and expected to stay green in CI or the canonical local bootstrap path |
| Best effort | Known to work for some workflows, but not part of the primary CI contract or may require manual tuning     |
| Unsupported | Outside the maintained contract; bugs may be closed unless they reproduce on a supported surface           |

## Operating Systems

| OS                          | Level       | Notes                                                                                         |
| --------------------------- | ----------- | --------------------------------------------------------------------------------------------- |
| Ubuntu 24.04 / 22.04 x86_64 | Supported   | Canonical CI and devcontainer target                                                          |
| macOS 14+ on Apple Silicon  | Best effort | Verified contributor path exists; prefer CPU-first JAX defaults, with `apple-metal` as opt-in |
| macOS Intel                 | Best effort | No active CI, but should remain viable for non-accelerated contributor work                   |
| Windows native              | Unsupported | Use a Linux devcontainer or WSL2-equivalent instead of native Windows Python/Node installs    |

## Python

| Python | Level       | Notes                                                                                 |
| ------ | ----------- | ------------------------------------------------------------------------------------- |
| 3.14.x | Supported   | Canonical baseline in `pyproject.toml`, `.python-version`, docs, and CI               |
| < 3.14 | Unsupported | Outside `requires-python`; some compatibility extras also explicitly gate older paths |
| 3.15+  | Unsupported | Not yet verified for dependency resolution or runtime compatibility                   |

## Node

| Node  | Level       | Notes                                                                                |
| ----- | ----------- | ------------------------------------------------------------------------------------ |
| 22.x  | Supported   | Canonical dashboard/tooling baseline in `.nvmrc`, `package.json`, docs, and CI       |
| 23.x+ | Unsupported | Tooling drift risk; local success on newer Node versions is not part of the contract |
| < 22  | Unsupported | Outside the current dashboard engine range                                           |

## CPU / GPU Expectations

| Surface                                              | Level       | Notes                                                                                |
| ---------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------ |
| CPU-only backend / docs / frontend contributor flows | Supported   | Default path for bootstrap, verify, docs build, and CI                               |
| NVIDIA CUDA research hosts                           | Best effort | Useful for research workloads, but not part of the default contributor or CI surface |
| Apple Metal acceleration                             | Best effort | Use the opt-in `apple-metal` extra; CPU remains the support baseline                 |
| TPU / vendor-specific accelerators                   | Unsupported | No maintained bootstrap, CI, or runtime contract today                               |

Baseline expectations:

- 4+ CPU cores and 16 GB RAM are the practical floor for comfortable local contributor work.
- Browser suites need enough disk for Playwright browsers and artifacts.
- Large benchmarks or dataset pipelines may need substantially more memory and local storage than the default contributor path.

## Optional External Binaries And Services

| Surface                     | Level                    | Notes                                                                                                       |
| --------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `uv 0.9.21`, `git`, `npm`   | Supported prerequisite   | Required for canonical contributor workflows; `uv` is pinned to the same baseline in CI and local bootstrap |
| Playwright browsers         | Supported prerequisite   | Installed on demand for browser-backed frontend suites                                                      |
| Docker / dev containers     | Supported prerequisite   | Preferred route for hermetic local environments                                                             |
| PostgreSQL                  | Best effort prerequisite | Required for durable control-plane and tenant-aware runtime flows                                           |
| CUDA toolkit / `nvidia-smi` | Best effort prerequisite | Required only for GPU research hosts                                                                        |
| `libomp` on macOS           | Best effort prerequisite | Often needed for `causal-bcf` / `stochtree`                                                                 |

## Triage Rules

- Reproduce first on Python `3.14.x` and Node `22.x`.
- If a report only reproduces on native Windows or an unpinned Node/Python version, treat it as unsupported until reproduced on the supported matrix.
- If a failure only occurs with `apple-metal`, CUDA, or other accelerator-specific paths, classify it as best-effort unless the bug also affects the CPU baseline.
