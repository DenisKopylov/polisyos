# tools/ops_runners/ukraine_data

Ukraine public-data ingestion and corpus-preparation helpers.

Canonical domain logic lives in `src/polisyos/data_forge/domains/ukraine/`.
This directory is the Ops-facing executable surface for harvest, sharding, and
publication workflows around that domain.

Use the unified entry point:

```bash
polisyos-tools ukraine_data --help
polisyos-tools ukraine_data pre-shard-lex-corpus --help
```

## Part B server workflow

The existing `ukraine-data` project console script is the Part B server-workflow
entry point. Its `pyproject.toml` target is
`tools.ops_runners.ukraine_data_cli:main`, which composes the domain CLI with
the Ops-owned orchestrator factory in `server_bootstrap.py`. The separate
`polisyos-tools ukraine_data ...` command group above remains the separate
registered Ops-tool surface, including its own bootstrap and gate commands.

The `ukraine-data` CLI keeps the domain parser's existing `--config`, `--root`,
and `--workspace-root` options and subcommands. `--root` overrides the
artifact/build root; when omitted, the pipeline configuration uses its
`production_data/ukraine_part_b` default. `--workspace-root` selects the
repository checkout used by repository-only server gates. The Ops composition
resolves an omitted workspace root to the process working directory. It is
distinct from the artifact root and is not inferred from the module path. If no
usable checkout is available, the gate records a typed `unavailable` result.

Server provisioning and subprocess execution stay in this Ops directory. The
domain CLI requires an explicit typed `orchestrator_factory` when called
directly; the installed `ukraine-data` console script supplies that factory.
The workflow retains its server-only policy. The C7 gate records the complete
pre-filter collected test-node set and every same-process setup, call, and
teardown result. A real setup skip has no call report but still requires a
teardown report and a retained skip reason;
it passes only when the exact source/config identity is reconciled and every
phase succeeds. A zero exit code, console summary, collect-only run, or narrowed
selection cannot substitute for that evidence. A macOS focused test run does
not verify the Linux installed-wheel path or the actual C7 server lifecycle. Each C7 child also gets
a unique system-temporary attempt directory outside the supplied checkout; explicit pytest `cache_dir`
and `--basetemp` options keep its cache and per-test temporary files in that directory. The directory
is removed after the typed receipts are read. An approved caller-provided JUnit report remains at its
requested path.

Operational rules:

- Preserve source null/missing semantics in generated manifests and contract
  payloads.

- Stream large inputs and use atomic publication for summary files.
- New harvesters must make timeout, response-size, and retry policies explicit.
