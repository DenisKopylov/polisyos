# Local Runtime State

Owner: `team-platform` for the schema reference; `team-ops` owns the layout contract version
Source of truth: `architecture/local_runtime_state.toml`@`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, `architecture/runtime_state_layout.toml`@`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, and `tools/ops_runners/runtime/runtime_state_cleanup.py`@`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Review evidence: source inspection at that repository revision on 2026-10-14; cleanup commands and local state were not exercised.

## Purpose

This page describes the repository contract for the ignored `.polisyos/` local
runtime-state root. It is a schema reference, not an inventory of files present
on a machine and not evidence that a runtime, cloud resource, or state store is
available. Raw local payloads stay ignored; promote only reviewed summaries or
registered release evidence.

The similarly named `production_data/` tree used by production-debug procedures
is a separate product-root input tree. This contract's `.polisyos/production_data`
slot is local runtime state; do not treat the paths as interchangeable.

## Owner And Contact

`team-platform` owns this human-readable schema reference. `team-ops` owns the
versioned layout contract and its migration rules. Individual state slots have
their own owners in `architecture/local_runtime_state.toml` and
`architecture/runtime_state_layout.toml`. The logical owner-group mapping and
fallback are in [Ownership](ownership.md); repository support scope and channels
are defined by `policy-engine/SUPPORT.md`.

## Allowed Directory Layout

The complete registered and legacy first-level entry sets, canonical paths,
slot IDs, and migration targets live in the two source-of-truth TOML files above.
The layout contract marks unknown `.polisyos/<name>` entries fail-closed: do not
invent a slot or use this page as authorization to create one.

The list below is the first-level layout declared by
`architecture/local_runtime_state.toml` and `architecture/runtime_state_layout.toml`
at the pinned source revision above. A script parsed both TOML files: each has
32 registered entries, the registered sets match, and the layout file declares
4 legacy entries. The path denominator is those two TOML files; the file-type
denominator is 2 TOML files. This is the declared layout, not a census of a
machine's physical `.polisyos/` directory.

| Registered entry | Registered entry | Legacy alias |
| --- | --- | --- |
| `.polisyos/.polisyos` | `.polisyos/audits` | `.polisyos/artifacts` |
| `.polisyos/canary_evidence` | `.polisyos/canary_evidence_debug` | `.polisyos/cas-readme-check` |
| `.polisyos/canary_matrix_runs` | `.polisyos/canary_replay_cas` | `.polisyos/cas_cache` |
| `.polisyos/cas` | `.polisyos/control.sqlite3` | `.polisyos/live_gonka_smoke.json` |
| `.polisyos/control_plane.sqlite3` | `.polisyos/control_plane_real_canary_8031.sqlite3` | — |
| `.polisyos/decision_validity` | `.polisyos/evicted` | — |
| `.polisyos/facts` | `.polisyos/idempotency` | — |
| `.polisyos/keys` | `.polisyos/local-prod-debug` | — |
| `.polisyos/local_production_canary` | `.polisyos/production_data` | — |
| `.polisyos/provider_verification` | `.polisyos/real_production_profile_attempt_state` | — |
| `.polisyos/real_production_quality_run` | `.polisyos/real_production_quality_run_state` | — |
| `.polisyos/reports` | `.polisyos/runs` | — |
| `.polisyos/runtime` | `.polisyos/scholar_cache` | — |
| `.polisyos/scholar_jobs` | `.polisyos/scientist` | — |
| `.polisyos/search_registry` | `.polisyos/security` | — |
| `.polisyos/state` | `.polisyos/wave35A_runs` | — |

CAS is canonical under `.polisyos/cas`; content-addressed blobs and manifests
belong under `.polisyos/cas/artifacts/sha256`, while recomputable cache and
README/check output use `.polisyos/cas/_cache` and
`.polisyos/cas/_readme_check`. The contract maps legacy cache and validation
paths to those canonical locations. Runtime runs,
reports, audit evidence, control-plane state, and other component state each
have registered slots; consult the TOML for their exact paths and per-slot
policy. For artifact-store semantics and backend selection, see
[CAS and Storage](operations/cas-storage.md).

## File Naming

Use registered snake_case slot names for first-level directories, except for a
documented legacy alias. Run and evidence leaves use stable run IDs, ISO-8601
dates, provider IDs, or content-addressed hashes as appropriate. The layout
contract's `schema_md_contract.file_naming` and each slot's `naming` field are
authoritative for details.

## Formats

The contract assigns TOML to local manifests and migration metadata, JSON or
JSONL to machine evidence and event streams, Markdown to reviewed human
summaries, and SQLite only to local control-plane state slots. Binary blobs are
limited to the paths listed in `schema_md_contract.formats` in
`architecture/runtime_state_layout.toml`.

## Retention

Retention is declared per slot as a default duration plus a cleanup policy in
`architecture/local_runtime_state.toml` and `architecture/runtime_state_layout.toml`.
Use those records for exact slot values. The artifact-family classes in
[Retention and Recovery](operations/retention-and-recovery.md) describe a
separate policy and do not replace the local slot contract. A retention value
is policy metadata; it does not prove that a cleanup job is scheduled or has
run.

## Backup Policy

Recomputable state has no default backup. Before cleanup, audit evidence,
production snapshots, local keys, security evidence, and promoted release
evidence require an explicit backup or export as specified by the layout
contract. Check the slot's owner and backup policy before changing state.

## Safe Cleanup

The cleanup tool accepts registered slot IDs, confines cleanup targets beneath
`.polisyos/`, rejects wildcard paths, and defaults to a report without deletion
unless `--apply` is supplied. Start with a dry run from the product root:

```bash
cd policy-engine
uv run python tools/ops_runners/runtime/runtime_state_cleanup.py --slot runs --dry-run
```

The command requires `uv` and a Python environment provisioned for the checkout
according to `CONTRIBUTING.md`. It inspects only the selected local checkout;
it does not query remote services or establish cloud state. This command was
not run during the review recorded above.

Use one `--slot` per registered slot; repeat the flag to inspect more than one.
Applying cleanup to a protected non-production slot also requires
`--approve-protected`; `production_data` requires `--approve-production-snapshots`
with `--apply`. These flags satisfy tool guards only. They do not replace the
manual owner approval required by the slot's cleanup policy. The script does
not provide an `--apply` command here: consult the contract and the owning team
before any destructive action.

## Promotion Rules

Keep raw runtime state local. Promote a reviewed summary or manifest, not a raw
runtime directory. Redact secrets, credentials, tenant payloads, provider keys,
and large binaries. The contract requires promoted evidence to record its
source slot, run ID, owner, review date, and cleanup decision, and to use a
registered evidence location such as `docs/archive/reports/` or release
evidence.

## Migration Slots

The complete slot IDs, target paths, migration classes, compatibility rules,
and owners are defined by the `[[migration_slot]]` entries in
`architecture/runtime_state_layout.toml`. Runtime-state readers must preserve
N-1 compatibility or publish an export/cleanup procedure before promotion;
breaking state-format changes require the declared release fragment. The
runtime-state reader gate is linked from
`architecture/gates/compatibility_release.toml`.

For restore execution, use [Replay or Restore Workflow](../runbooks/replay-or-restore.md)
or [Retained Artifact Recovery](../runbooks/retained-artifact-recovery.md),
depending on the artifact family.
