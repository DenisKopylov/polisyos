# Manage Generated Artifacts

Use this procedure for committed outputs registered in
`architecture/generated_artifacts.toml`. For transient build or runtime outputs,
follow the owning subsystem's procedure.

Owner: @platform-owners for this procedure; each family names its owner and
approval owner.
Source of truth: architecture/generated_artifacts.toml
Generated lookup: docs/reference/generated-artifacts.md

Source review at `47e1e59b569a5b922611f71a7f53fb6320abea4c` on 2026-10-14
inspected the registry, listed generator/check entrypoints, contributor
environment, and evidence-retention workflows. No generator, check, test, CI
workflow, or GitHub artifact was run or queried. This historical review is not
a current execution receipt.

## One-family workflow

1. Find the output path in [Generated Artifacts](../reference/generated-artifacts.md),
   then open its family record in `architecture/generated_artifacts.toml`.
2. Read that record's `source_of_truth`, `outputs`, `check_cwd`,
   `check_command`, `regenerate_commands`, `commit_policy`, `owner`, and
   `approval_owner`. The registry is the only command and output-set authority;
   this guide does not maintain another family command list.
3. From the registered `check_cwd`, run the exact `check_command` before
   changing anything. It checks only that family's declared contract. A
   registry-wide guardrail check does not replace the family check.
4. If the source should change, edit the source of truth and run only the
   registered `regenerate_commands` for the affected family. Do not edit
   generated outputs directly or regenerate unrelated families.
5. Rerun the registered check, run `git diff --check`, and compare changed
   paths with the family's declared outputs. Follow `commit_policy` and
   involve the recorded `approval_owner` where required.
6. In the change summary, state the source change, generated paths, exact check
   outcome, whether regeneration occurred, and any `UNRUN` dependency. A
   missing result is not a pass.

If no family matches the output, ask its owner where the contract belongs. Do
not invent a local command table or treat an unregistered output as covered by
this registry.

## Evidence and storage

Committed outputs are available for review from the branch. Files under ignored
`_build/` paths are local unless a supported workflow explicitly uploads them.
For workflow evidence, confirm the actual run, commit, step, and downloadable
artifact; an upload declaration in source does not prove that the artifact
exists. Do not present a new local run as evidence from an earlier CI run.

When a result depends on measured input coverage, follow the [measurement
author contract](author-measurement-instruments.md): report the actual
denominator, read outcomes, and unresolved boundaries. A local path and digest
identify retained evidence but do not make it available in another checkout.

## When the registry changes

When adding or changing a family, update `architecture/generated_artifacts.toml`,
then regenerate `docs/reference/generated-artifacts.md` with
`uv run polisyos-tools architecture guardrails sync` and verify it with
`uv run polisyos-tools architecture guardrails check`. Run the affected family's
registered check separately. The guardrail commands validate the
registry/reference workflow; they do not replace the family check.

MkDocs navigation and configuration fragments use the separate
`architecture/tooling/tool_config_split.toml` workflow. See
[Documentation Verification](../reference/documentation-verification.md); do
not mix those source/output maps into the generated-artifact family registry.

## Family-specific procedures

Connector contract changes have additional compatibility and test requirements.
Follow [Connectors: Contributing](../connectors/CONTRIBUTING.md) rather than
copying family commands into this general guide. Runtime API client generation
has its own [update procedure](update-runtime-dashboard-api-client.md).

## Rollback and troubleshooting

If regeneration was accidental, revert the generated diff, confirm the source
of truth, and rerun only that family's registered check.

If a check changes unrelated files, inspect its declared source and output set
before accepting the diff. If a check is unavailable, report `UNRUN` and the
missing dependency. Do not replace a failed family check with string search or
a different local command.
