# Migration Guide: Ukraine Part B Ops Composition

Date: 2026-10-15
Owner: `team-data-forge`
Migration owner: `team-data-forge`
Status: candidate implementation; independent Linux/C7 verification remains open.

This note records the existing `ukraine-data` console script's Ops composition
and its caller boundary. It does not certify deployment, a live server, or
formal E02 finding closure.

## Entry point and ownership

The `ukraine-data` console script is declared in `pyproject.toml` and resolves
to `tools.ops_runners.ukraine_data_cli:main`. That wrapper calls the canonical
domain CLI with the Ops-owned `build_orchestrator` factory from
`tools.ops_runners.ukraine_data.server_bootstrap`.

The domain package owns the typed pipeline, stage, and manifest contracts. Ops
owns server provisioning, capability probing, and repository-test process
execution. The domain CLI does not discover Ops modules, infer a checkout from
`__file__`, or launch subprocesses itself. Code that calls
`polisyos.data_forge.domains.ukraine.cli.main` directly must pass its typed
`orchestrator_factory`; omitting it raises `RuntimeError`. The installed
`ukraine-data` entry point already supplies the factory.

`polisyos-tools ukraine_data ...` remains a separate registered Ops-tool group
for the existing commands in `tools/ops_runners/ukraine_data/`, including its
own bootstrap and gate commands. It is not the Part B domain CLI's composition
factory.

## Filesystem inputs

The CLI's `--root` argument is an artifact/build root override. If omitted, the
default is the relative `production_data/ukraine_part_b` root from
`BuildRootConfig`; an explicit `--config` may supply a different build root,
which `--root` overrides when both are present.

`--workspace-root` separately identifies the repository checkout needed for
repository-only server gates. The Ops composition resolves an omitted value to
the process working directory, then passes the resolved path into the domain
orchestrator. It does not use the artifact root as a checkout or infer a
checkout from package parents. If the selected working directory is not a
usable checkout, the gate returns a typed `unavailable` result rather than
searching elsewhere.

## Server-only boundary and verification

The Part B pipeline keeps its server-only policy. Ops owns bootstrap and the
subprocess callback for the repository C7 integration gate. A positive result
requires a same-child receipt binding the complete pre-filter C7 node set to
pytest's real lifecycle: passed setup requires call and teardown, while a setup
skip may omit call but must retain teardown and its reason. The receipt also
binds the test/configuration bytes and the sanitized plugin/conftest profile.
Ambient plugin loading is disabled, non-core collectors are refused, and the
pre-filter node sequence is compared with the final execution sequence. A zero
exit code, console summary, collect-only run, or narrowed selection is not
evidence that the gate passed.

The candidate's focused macOS suite exercises the CLI-to-Ops composition and
workspace/build-root separation. Its installed-wheel test is explicitly
Linux-only and was skipped on macOS. A native Linux installed-wheel run and the
real C7 server lifecycle run remain unverified, so neither this note nor the
candidate's test results close LA-029. Independent acceptance must inspect the
candidate source and obtain those platform-specific receipts or retain the
corresponding limitation.

## Rollout checklist

- Confirm the installed `ukraine-data` script resolves to the Ops wrapper and
  supplies the typed factory.
- Keep `--root` for pipeline artifacts and `--workspace-root` for the repository
  checkout; when the latter is omitted, verify that the process working
  directory is the intended checkout.
- On the supported Linux worker, verify the installed-wheel unavailable path
  and the real C7 server lifecycle with retained process receipts.
- Preserve the server-only guard and leave LA-029 open or limited until the
  independent source and platform-specific receipts are accepted.
