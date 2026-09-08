# Final guardrail deep-import baseline audit

Recommendation: remove only the stale baseline identity
`polisyos.runtime.quality.acquisition_planner->polisyos.data_forge.domains.academic.knowledge`,
record that deliberate tightening, and run the unchanged normal guardrail with the separately repaired station environment. No production import, public-entrypoint policy, exception, receipt, or executed N7 capability needs repair. This observer changed no baseline or production source.

## Actual owner measurements

The focused harness imports the real `tools.devx.architecture.guardrails` from each requested root and asserts its `REPO_ROOT`. It executes the same `collect_deep_import_edges`, `render_deep_import_baseline_json`, exact frozen-byte equality, and `_check_deep_import_creep` owners used by normal `run_check`. It does not skip an input or alter a rejection rule. Both command records include exact argv, cwd, lane-venv path prefix, return code, wall time, and complete streams.

| Root | Focused baseline result | Evidence |
| --- | --- | --- |
| Current lane | RC1, 39.255s; exact stale identity below; creep findings empty | [command](deep-import-owner-current.json), [complete packet](deep-import-current-complete.json) |
| Existing lane-owned `gyphase5-lane-basecheck`, exact slice base `3d572c146f9d021cb6daad64ebb7b093121ed124` | RC1, 39.664s; identical stale identity; creep findings empty | [command](deep-import-owner-base.json), [complete packet](deep-import-base-complete.json) |

The denominator is every `src/**/*.py` file used by the owner and every static import in those files, together with the complete public-entrypoint contract. The owner's `Path.rglob`/`ast.walk` result is independently reconciled against `os.walk`/`ast.NodeVisitor`; complete file and finding identity sets agree, and unreadable/ambiguous cases are empty. Each packet retains all source-file identities and hashes, every actual expected edge, every independently derived edge, every frozen edge, and the whole expected and frozen artifacts. No count-only comparison is used.

[Complete base/current reconciliation](deep-import-complete-delta.json), produced by [this command](deep-import-delta-archive.json), returns RC0 in 12.363s. The entire current expected edge map equals the entire slice-base expected edge map, including values, and the entire frozen maps also agree. The complete set differences in each root are:

- Frozen absent from actual expected: `polisyos.runtime.quality.acquisition_planner->polisyos.data_forge.domains.academic.knowledge`.
- Actual expected absent from frozen: empty.
- Shared edge identities with different edge values: empty.

The exact source-removal provenance is retained as a complete `git show 68689784a -- src/polisyos/runtime/quality/acquisition_planner.py` command/result in the reconciliation packet. That commit, already in the slice base, replaced `_capture_skg`'s direct `domains.academic.knowledge` import and schema probe with the existing `polisyos.data_forge.read_api` academic surface and `ProductionCG2CalibrationSource.produce/replay`. The baseline retained the old import identity. The current supported-entrypoint contract still declares `polisyos.data_forge.read_api`; its existing `__init__.py` exposes `academic`, and `read_api/academic.py` resolves the actual source-identity owner. The declaration is not newly broadened by this lane.

## Why deletion tightens the gate

`guardrails.py:1952` detects creep by testing each complete current edge identity against the baseline. `run_check:2074` separately rejects a baseline that differs from the full current rendering. Removing an absent row shrinks the tolerated set while restoring exact snapshot freshness; it neither suppresses a live finding nor narrows the scanner denominator.

The reconciliation command also ran the actual creep owner against an ignored scratch baseline rendered from all real current edges. The genuine current edge set returned no creep findings. Reintroducing the old frozen edge as the adversarial input then produced the exact `New deep-import creep detected` finding for that identity. The reintroduced edge is explicitly a mutation witness, never a current-source denominator member. No checked-in baseline was written by the probe.

## Write boundary and finding classification

`CONTRIBUTING.md:94–113` names the baseline and the canonical governance sources. `tools/devx/architecture/README.md` identifies the guardrails engine as the source of truth for regenerating this inventory. `docs/reference/ratchet-policy.md` requires deliberate baseline changes and names `@platform-owners` with `@tools-owners` as backup. The exact deletion, evidence, and normal-gate replay meet that maintenance purpose without admitting a new dependency.

The plan's earlier closed `deep-import-baseline-stale` row required edge adjudication because blindly synchronizing would have accepted new creeps. Its closure is historical context, not authorization for another expansion and not a task reopened here. This measurement has no added creep to adjudicate. The proposed ADR-0053 is explicitly `Proposed`; its post-freeze contract-change approval language is not silently promoted to a ratified ruling. In any case, this recommendation changes no import rule or supported-entrypoint contract. No missing external semantic ruling or institutional appointment is identified for this exact tightening. Do not perform an unrestricted baseline sync or change another entry.

P40 classification: **NEW final-review class**, a stale import-ratchet snapshot companion under P07/P29. It is separate from the lane's already repaired manifest/authority intake classes. Its home is the continuous architecture guardrail baseline owner (`@platform-owners`, backup `@tools-owners`), with the source transition identified above. No executed N7 or closed stale-baseline task is reopened.

P41 scope remains explicit: the focused owner reproduces at the exact slice base, but the full normal architecture command was not replayed here. The complete current/base observed source-input intersection with this lane's changed paths is nonempty and is retained in the delta packet. Therefore a claim that the **full red guardrail is inherited** is **not_established**. The proposed closure rests on the actual complete edge maps and the tightening falsifier, not on an inherited-red exemption.

[Research harness Ruff](deep-import-harness-ruff-final-v2.json) passes RC0. Earlier local Ruff records remain as superseded harness-format findings. The station's separate copied-interpreter/dylib failure belongs to the parent's station evidence; no station workaround, source fix, baseline write, or full guardrail run was performed by this audit.
