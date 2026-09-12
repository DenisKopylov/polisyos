---
title: Absence requires a declared measurement boundary
status: decision-pending-population-readback
owner: team-devx / team-architecture
may_not_use_for:
  - capability closure outside the measured source boundary
  - runtime execution or institutional ownership proof
---

# Instruments must show what they read

Row: `instruments-report-absence-without-declaring-what-they-read`.
Base: `307dabcb4`. Decision becomes executable only after the full five-document
Stage 1 commit is read back from attached `codex/measurement-plane`.

## Findings already reproduced

**MP1-01 — static invocation is the reference.**
`src/polisyos/runtime/quality/production_invocation.py@307dabcb4`,
`audit_sources`, `audit_repository`, and `main` separate static direct paths,
`unresolved_by_construction`, and static `uninvoked`. `_read_tree` enumerates tracked
`src/**/*.py`, `tools/**/*.py`, `tests/**/*.py` plus project scripts at current and
base revisions. Its receipt gives counts and content identities; its summary names
HTTP, callbacks, deferred execution, reflection and runtime evidence as unmeasured.
Do not infer framework non-invocation or change the call-graph algorithm.

**MP1-02 — a status projection is not an interpretation of completion clauses.**
`tools/quality/validation/check_debt_ledger.py@307dabcb4`, `_GY_TASK_ROW`,
`_parse_gy_tasks`, `_snapshot`, and `main` match the task-standing row grammar and
project non-terminal tasks. The same file reads the GY document bytes, but does not
interpret its section 8.6 rulings. The owner document's operational boundary is
section 8.6 through the start of section 9 in
`docs/plans/active/layer3-slices/GY-engine-subordination.md@307dabcb4`: rulings govern
how tasks are read and change no statuses. No `may_not_use_for` frontmatter field
is present. In particular a selected trajectory does not count as attempted
execution, and a fixture cannot enter a production-catalog rate numerator.
No status/ledger rewrite is authorized by that discovery.

**MP1-03 — acknowledgement validation is not ownership allocation.**
`architecture/atlas_surfaces/check_atlas_enforcement.py@307dabcb4`,
`_tracked_atlas_plan_paths`, `_yaml_frontmatter`, and
`validate_slice_scope_obligations` enumerate tracked Markdown under `docs/plans`,
retain `type: slice-plan`, and validate the exact unique manifest input set.
Documents rejected by that selector do not establish absence of an owner.
`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@307dabcb4`
contains dated 2026-09-01 ownership acts under per-slice detail; its frontmatter has
no `may_not_use_for`. Those acts explicitly allow assignment without a separate
slice plan. The acknowledgement checker must name this unmeasured ownership plane,
not create a rival ownership parser. Malformed/unreadable candidate documents must
remain ambiguous rather than silently disappearing.

## Architecture and protected seams

Compose existing producers and projections: ledger `audit_repository` → `main`;
Atlas `validate_slice_scope_obligations` → `validate_enforcement` → `main`; existing
production-invocation receipt. Keep GY/Atlas status authorities, generated ledger
bytes, register bytes (including its deliberate pipes), schema meanings and
architecture baselines intact. Reuse the existing report dictionaries for additive
coverage. Any source-read helper must report successful reads separately from
failed attempts and declare child-process reads outside its boundary.

Production caller of new source-read bookkeeping: the existing ledger audit and
Atlas obligation validator. It is internal tooling composition, not a standalone
command. Discoverability comes from those existing command/architecture entrypoints
and their README links. Preserve Atlas's list-of-errors interface; its production
caller receives the additional scope receipt. No new runtime/public API.

Shared-instrument effects for other lanes: ledger stdout/report gains an input and
limitation receipt, but original finding codes, denominator pins, generated text
and blocking thresholds remain. Atlas gains an acknowledgement-scope receipt on
success and failure; duplicate and malformed obligations still fail. The invocation
instrument and repository structure gate are reference owners, not repair targets
for this row. Root alone edits shared instruments and performs git mutations.

## Standing rule and falsifiers

Put the standing rule where new instrument authors enter: scoped `tools/AGENTS.md`
and `architecture/AGENTS.md`, linked from their READMEs to an author guide. Extend
the existing P35/P38 maintenance guidance rather than inventing a new pattern.
Every absence-capable instrument must expose its actual read set, semantic selector,
nonselected/unreadable members and named `unresolved_by_construction` boundaries.
A documented domain or a source file opened is not proof every statement in it was
interpreted. A clean exit is no verdict after incomplete execution.

Red-first tests exercise the real report path: (1) a fact solely in GY section 8.6
must remain explicitly outside the task-status measurement; (2) a master-plan
ownership act alongside no slice frontmatter must not be called measured absence;
(3) unreadable/malformed input cannot yield an empty successful measurement;
(4) a dropped ledger row and an invalid/duplicate acknowledgement still fail;
(5) the existing framework witness remains unresolved while removing a real direct
caller still produces the original invocation failure. Remove the read-recording
or boundary emission while keeping its documentation and these tests must fail.

Pattern pass: P31 structural rule, P35 complete denominators, P37 recomputed read
facts versus declared interpretation limits, P38 proxy versus property. Existing
defect: file-open/status/acknowledgement knowledge was overstated as interpretation
or allocation. Target: bounded diagnostic plus explicit nonmeasurement. Before
execution, report enrichment is `surface_missing` / `semantic_test_missing`.
The population survey and its exact follow-up routing are required before repair.

## Implementation contract for the committed decision

Reuse `tools/lib/fs.py` for a context-local read receipt. The two production
callers above enter a measurement context; their direct file reads and presence
probes record path, operation and success/result as they occur. Failed attempts
are distinct from successful reads. The context is not a filesystem audit of
Python imports, Git, pytest children or external services, and says so explicitly.
The same path can be read more than once; operation records are not a claim of
unique business evidence. This extends the existing tooling helper owner rather
than adding a new module or runtime dependency.

Ledger `AuditReport.measurement` is additive with a default for existing tuple
constructors. CLI stdout prints its JSON before findings; a read failure prints
`UNRUN` with partial read coverage and exits 2 instead of producing a complete
absence verdict. Original complete audits retain their 0/1 exits and all existing
status, collection and render predicates. An unavailable optional file is recorded
as a presence probe, not as a file whose bytes were read.

Atlas keeps `list[str]` for callers and accepts an optional measurement destination.
Its production caller publishes that receipt on both successful and failed checks.
The receipt separately enumerates selected slice plans, excluded documents and
unreadable/invalid candidates. Schema/manifest loading and tracked-plan enumeration
are declared inputs; supplied in-memory manifest values are labelled as such.
A malformed tracked candidate is no longer silently dropped: the run fails with
an explicit input-unresolved finding. No absence of a slice-plan acknowledgement
is allowed to settle the master plan's institutional ownership acts.

The standing rule governs authoring and review across the surveyed population.
This change does not claim to retrofit every historical instrument from one generic
tracer: imports, child processes and semantic interpretation cannot be recovered by
recording `Path.read_text` calls. The population handback must distinguish compliant,
partial and undisclosed members and route the remaining migration by owner.
