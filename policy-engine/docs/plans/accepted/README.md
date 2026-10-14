# Accepted plan routing

This directory contains approved work programs and their phase records. The
directory name describes program routing; it does not say that a plan's work is
implemented, verified, or closed. Read each plan's own status and evidence.
`accepted` means the program was approved, not that implementation is complete.

Plan status is not a capability status: `proposed` records intent, `accepted`
records approval, and `completed` is a plan/document lifecycle claim; none
proves an end-to-end product capability. For a capability claim, use the
[capability check](../../reference/policy-design-case-failure-patterns.md#capability-reality-check);
a plan or procedure alone remains `absent/unallocated`. For claims about
current behavior, follow the source snapshot and verification rules in the
[documentation style guide](../../style-guide.md) and preserve their source,
method, and scope.

The nine plan documents below were enumerated from the complete accepted
directory at branch snapshot `8dd933600dd7a5a8a5b48432c6089d63b81ca641`:
9 Markdown plan files plus the non-plan `.gitkeep` placeholder. The complete
plans-and-backlog walk was performed by
`policy-engine/_build/docs-maintenance/plans_audit.py`; its ignored receipt is
`policy-engine/_build/docs-maintenance/raw/plans-audit.json` (417 paths total:
411 under `docs/plans/`, including 10 accepted entries, and 6 under
`docs/backlog/`). This new README is a routing aid added after that snapshot.

| Plan | Front matter status at the snapshot | Current repository consumer or binding |
| --- | --- | --- |
| [`REPOSITORY_SOTA_PLAN.md`](REPOSITORY_SOTA_PLAN.md) | `accepted` | `tests/repo_quality/architecture/test_repository_public_polish.py` checks its accepted path; `tools/devx/workspace/repository_sota_closeout.py` requires the plan and its Phase 5 link; phase 4/5 tests and `tests/repo_quality/tools/test_docs_lifecycle.py` also reference it. `architecture/conservative_overlay.toml` and the 2026-04-03 release fragment carry path references. |
| [`REPOSITORY_SOTA_PHASE_0_CONTRACTS.md`](REPOSITORY_SOTA_PHASE_0_CONTRACTS.md) | `active` | `architecture/shims.toml` binds three shim records to this plan as their issue; `test_repository_public_polish.py` checks its accepted path. |
| [`REPOSITORY_SOTA_PHASE_1_DATA_FORGE_FOUNDATION.md`](REPOSITORY_SOTA_PHASE_1_DATA_FORGE_FOUNDATION.md) | no status field | `test_repository_public_polish.py` checks its accepted path; the SOTA parent plan and the phase 0–7 decision brief link to it. |
| [`REPOSITORY_SOTA_PHASE_2_DOMAIN_MIGRATION.md`](REPOSITORY_SOTA_PHASE_2_DOMAIN_MIGRATION.md) | no status field | `test_repository_public_polish.py` checks its accepted path; the SOTA parent plan and the phase 0–7 decision brief link to it. |
| [`REPOSITORY_SOTA_PHASE_3_TOPOLOGY_CLEANUP.md`](REPOSITORY_SOTA_PHASE_3_TOPOLOGY_CLEANUP.md) | `report` | `test_repository_public_polish.py` checks its accepted path; the SOTA parent plan and the phase 0–7 decision brief link to it. |
| [`REPOSITORY_SOTA_PHASE_4_GENERATED_FRONTEND_DATA_OPS.md`](REPOSITORY_SOTA_PHASE_4_GENERATED_FRONTEND_DATA_OPS.md) | no status field | `test_repository_public_polish.py` checks its accepted path; `test_repository_sota_phase4_discipline.py::test_phase4_plan_and_reference_docs_link_the_contracts` checks both this file and its link from the SOTA parent plan. |
| [`REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md`](REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md) | no status field | `architecture/gates/repository_sota.toml` names it as `closeout_report`; `tools/devx/workspace/repository_sota_closeout.py::_check_closeout_docs` requires it and its link from the SOTA parent plan; `test_repository_sota_phase5_closeout.py` covers the closeout references. |
| [`REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md`](REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md) | `accepted` | `test_repository_structure_phase7_closeout.py::test_phase7_closeout_evidence_is_recorded` checks the plan and closeout paths; the active concurrency plan and accepted closeout document also reference this plan. |
| [`REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md`](REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md) | `accepted` | `test_repository_structure_phase7_closeout.py::test_phase7_closeout_evidence_is_recorded` checks the file and specific recorded test evidence. |

The path-existence assertions above preserve repository topology and navigation;
they are not proof that the described program is fully implemented or that a
runtime gate is green. Likewise, a plan with no front matter has no status to
infer from its directory. For current work and remaining obligations, follow
the named owner and evidence in the plan or its linked closeout, then route to
the [active-plan index](../active/README.md) or
[historical plan archive](../archive/README.md) as appropriate.

`.gitkeep` is only a directory placeholder and is not a plan.
