# C4 installed-package proof preflight — UNRUN

## Source identity check

Current CAN HEAD at check: `992ad5da2928a25aada15db5cfb9c74d011b6bc6`, tree `605b56c45c7d168ab5b6178613f22d0de987377a`. It includes later docs/receipt changes. The current branch is clean. The two relevant source/test blobs are unchanged from pinned Mapping candidate e3:

- `io.py`: e3 and current both `00a9b82ae827cae69acc2420ac887ae82802f5c5`.
- `test_ir_adapter.py`: e3 and current both `eadf0f52778561418dd77e64945f084d855d4beb`.
- Readback: `git diff --exit-code e3cb3fafc847b94a5d4b3adc03b814b4c711920c -- policy-engine/src/polisyos/ir/artifacts/io.py policy-engine/tests/unit/core/artifacts/test_ir_adapter.py` returned exit 0.

The command `git diff --exit-code e3cb3fafc847b94a5d4b3adc03b814b4c711920c -- policy-engine/src/polisyos/ir/artifacts/io.py policy-engine/tests/unit/core/artifacts/test_ir_adapter.py` returned exit 0.

## Offline build input check

Observed global interpreter: `/opt/homebrew/opt/python@3.14/bin/python3.14`, CPython 3.14.0. Global Pydantic is 2.12.5 and pytest is 9.0.2.

- `/opt/homebrew/opt/python@3.14/bin/python3.14 -I -m pip show hatchling pydantic pytest` returned exit 0 with `WARNING: Package(s) not found: hatchling`; it showed Pydantic 2.12.5 and pytest 9.0.2.
- `/opt/homebrew/opt/python@3.14/bin/python3.14 -I -m pip cache list hatchling` returned `No locally built wheels cached.`
- `uv cache dir && uv cache size` returned `/Users/deniskopylov/.cache/uv` and `12288` bytes.
- The prior C3 interpreter path `/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/policy-engine/.venv/bin/python` no longer exists (shell exit 127); it was not restored.
- Global `pip show policy-engine` identifies an editable install whose project location is `/Users/deniskopylov/polisyos/policy-engine`; that install cannot prove an e3 wheel.

The project build-system requires `hatchling>=1.27.0`. No approved local Hatchling backend/wheel was available in the inspected interpreter or caches. I therefore did not attempt a wheel build, install, alternate-backend packaging, environment creation, network access, or default-environment write.

## Disposition

Installed-wheel runtime proof is **UNRUN** because the required offline build backend input is unavailable. The missing input is an approved local Hatchling >=1.27 build backend or wheel. The earlier source-level independent Mapping review and focused runtime tests remain as previously reported; they do not substitute for this installed-package layer.
