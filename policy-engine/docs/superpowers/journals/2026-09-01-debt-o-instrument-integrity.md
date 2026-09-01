# Task O — instrument integrity journal

Date: 2026-09-01
Branch: `codex/debt-o-instrument-integrity`
Base: `d1680bd0d`
Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-o-instrument-integrity/policy-engine`

## Outcome and delivery shape

All eight allocated rows are closed. The repair is five ordered source/test commits plus this
append-only record:

1. `59ca637aa` — `test: declare corridor prerequisites`
2. `e2fd0a9f8` — `fix: type debt ledger findings and nonclosures`
3. `85dba9372` — `fix: distinguish quoted lifecycle evidence`
4. `92a9a34ac` — `fix: bind trust posture to invalidating sources`
5. `a61b99631` — `fix: bind atlas timing to live workload`

The fifth commit includes delta-only P29 hardening for Group 1: the original declaration tests were
form-based, so two behavioral tests now select real corridor nodes under simulated prerequisite
absence. This does not change the prerequisite mechanism; it closes the semantic-test gap discovered
during review.

The required interpreter binding was checked once before any measurement:

```sh
uv run --frozen --extra test python -c "import polisyos, sys; print(sys.prefix)"
```

Exact output, exit 0:

```text
/Users/deniskopylov/polisyos/.worktrees/debt-o-instrument-integrity/policy-engine/.venv
```

No branch-changing command or stash was used. `DEBT-REGISTER.md` was not edited. The only edits under
`docs/plans/active/` are the two explicitly authorised `## Explicit non-closure` tables in DS10 and
DS17; generated `LEDGER.md` was not hand-edited.

## Pattern pass

- `P04` / `P09`: debt status is a lattice with terminal and nonterminal consequences; a future
  closure test is not itself evidence that an open or blocked row is malformed.
- `P29`: prerequisite and CI guards execute the real selected node or parse the real workflow. A
  marker-only declaration is insufficient.
- `P31` / `P40`: the repair is generic over the class. The Group 1 behavioral probe and Group 5
  same-child receipt widened the mechanism after deeper examples of the same class; they were not
  patched per instance.
- `P32`: a timing receipt admits execution only when exact argv/cwd, ToolRunRecord bytes, workload
  identity, and the same child session agree. A plausible JSON shape is not evidence.
- `P33`: adversaries include missing prerequisites, nonterminal and terminal rows, invented debt-like
  labels, unclosed evidence markers, comment-only CI commands, disabled steps/jobs, source-set
  substitutions, same-cardinality node swaps, mixed path kinds, deselection, and plugin nonreceipt.
- `P35`: every set claim below carries its complete path/type denominator. Historical Task M failures
  and current declared dependencies are deliberately reported as two different sets.
- `P37`: prerequisite presence, source-set completeness, non-debt typing, and workload identity are
  `recomputed`; they are not consumer assertions. Anything else fails closed.
- `P38`: the old proxies were ambient workstation state, a row's lifecycle-independent missing test,
  the absence of a verbatim path, all-source byte drift, scalar test counts, and workflow text. Each
  repair states the actual property and a case where the proxy diverged.
- `P41`: the architecture test and architecture guardrail reds reproduced from the Task O slice base
  with zero intersection between Task O paths and their complete input denominators. They remain
  inherited, named below, and do not change any Task O row verdict.

Capability closeout: every Task O row now has a producer, typed result or receipt, consumer/gate,
verification, and a negative or integration-style semantic test. No Task O row remains
`contract_only`, `verification_missing`, or `implemented_but_not_orchestrated`. The Atlas timing
catalog correctly remains *unmeasured* because the captured semantic workload ended red; that is an
honest measurement state, not an open workload-identity capability.

## Group 1 — corridor prerequisites

### `corridor-tests-depend-on-undeclared-ambient-prerequisites`

Verdict: `open` -> `closed`.

#### Complete denominator and cause of movement

The historical Task M raw-failure denominator was re-derived, not inherited:

```text
TASK_M_OWNER_CATALOG_FAILURE_NODES=12
TASK_M_CP_SAT_FAILURE_NODES=4
```

The current declaration denominator is:

```text
CURRENT_OWNER_CATALOG_DEPENDENT_TESTS=14
CURRENT_CP_SAT_DEPENDENT_FUNCTIONS=3
CURRENT_CP_SAT_COLLECTED_NODES=4
```

The two owner-catalog numbers describe different repository states. The movement from 12 historical
raw failures to 14 current dependent tests is explained by Task M review-hardening commit
`b6de70859`: it added `test_default_value_port_binds_the_actual_n5_context` and routed
`test_active_overlay_reentry_is_exact_direct_and_read_only` through the canonical strict-world owner
catalog path. The solver denominator is three functions but four collected nodes because one function
is parametrized. No scalar is pinned as a proxy for future growth; every dependent function carries
the shared declaration at collection time.

When the ignored owner tree is absent, the skip reason names the unavailable production owner catalog
and tells the operator to link the worktree's provisioned `production_data` owner tree read-only.
When CP-SAT is absent, the reason names the missing `solvers` extra and the provisioning command
`uv sync --frozen --extra test --extra solvers`.

#### Red-first and deciding evidence

The declaration tests were first observed red against unmarked dependent tests. The later P29 probes
were also observed red before the shared collection hooks were made observable to a real selected
node: under simulated absence, the selected semantic node executed instead of reporting the missing
prerequisite.

Final behavioral command:

```sh
uv run --frozen --extra test python -m pytest -q \
  tests/unit/runtime/quality/test_generation_cycle.py::test_owner_catalog_prerequisite_skips_an_actual_node_when_catalog_is_absent \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_solver_prerequisite_skips_an_actual_node_when_extra_is_absent
```

Exact output, exit 0:

```text
..                                                                       [100%]
```

The provisioned positive controls — one actual owner-catalog node and one actual solver node — also
exit 0, proving the declarations do not convert an available semantic test into a permanent skip.

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`; historical and current denominators are both preserved.** A complete replay of Task M's classification re-derives **12** generation nodes whose raw failures came from the absent ignored owner catalog and **4** promotion nodes whose raw failures came from absent CP-SAT. The current declared dependency set is **14 owner-catalog tests plus 4 CP-SAT nodes**: Task M's review-hardening added `test_default_value_port_binds_the_actual_n5_context` and made `test_active_overlay_reentry_is_exact_direct_and_read_only` execute the same canonical strict-world/catalog path. Every current dependent test now carries the shared prerequisite declaration. Missing owner data reports that the `production_data` owner catalog is unavailable and names the read-only worktree link; missing CP-SAT names `--extra solvers`. Under the provisioned profile the semantic tests continue to execute. The declaration and real absent-prerequisite collection tests pass.

## Group 2 — debt-ledger checker

### `debt-closure-signals-name-unwritten-tests`

Verdict: `open` -> `closed` by a status-lattice decision.

Decision: `closure_signal_identity_unresolvable` is informational for every nonterminal source status
(`open`, `blocked`, `open_unmerged`, `ambiguous`, `foreign`) and blocking for terminal `closed` or
`folded` rows. The globally informational alternative was rejected because a published terminal
closure receipt whose test disappears must make `--check` red. The literal alternative “block for
every status other than `open`” was rejected because blocked work legitimately names the test its
eventual closure will write.

Red first: the new status-pair test initially showed the same missing identity blocking both an open
and a closed row. After the rule, the exact status test pair exits 0:

```sh
uv run --frozen --extra test python -m pytest -q \
  tests/repo_quality/tools/test_debt_ledger_checker.py::test_unwritten_closure_identity_is_informational_until_terminal \
  tests/repo_quality/tools/test_debt_ledger_checker.py::test_falsifier_missing_pytest_identity_is_blocking
```

Exact output:

```text
..                                                                       [100%]
```

The final bound collector found 43 pytest selections and exactly 10 missing identities. Their full
status partition is six `blocked` plus four `open`; therefore all ten are visible informational
findings and none can falsely block correct nonterminal standing:

```text
blocked  DS11-EXTERNAL-A11Y-COUNTERSIGN
blocked  DS11-FULL-TRUST-CENTER-AND-DOCS-IA
blocked  DS11-GROUNDED-PERFORMANCE
blocked  DS11-PUBLIC-SIGNATURE-POPULATION
blocked  DS11-SCOPE-ADJUDICATION-RECORD
blocked  global-case-index-producer-missing
open     ds10-connector-acquisition-content
open     ds10-global-case-index-producer-allocation
open     ds10-public-decision-rendering
open     epoch-dependency-denominator-defined-twice-incompatibly
```

The row's old prose count of 18 was not re-pinned. The current number is source-derived. Its movement
is fully accounted for: the branch registered three Task O selectors, Groups 1 and 2 wrote two of
them, and Group 3 wrote the third; at the final source freeze ten future identities remained. The
coincidental old/final scalar of ten masks changed membership, which is why the rule no longer treats
the scalar as the authority.

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`, with a status-lattice decision.** `closure_signal_identity_unresolvable` is informational while its source row is nonterminal and blocking once the row is `closed` or `folded`. The globally-informational alternative was rejected because a terminal row whose published closure identity disappears must fail the checker; the literal “anything except open blocks” alternative was rejected because `blocked` work also correctly names the test its eventual closure will write. A complete bound walk finds **43 pytest selections and 10 missing identities**, all on nonterminal rows — six blocked and four open — so the ten remain visible without making correct debt standing fail the gate. The prior prose count of 18 is superseded.

### `nonclosure-tables-name-no-debt-ids`

Verdict: `open` -> `closed`.

Decision: every populated explicit-nonclosure entry must either start with an exact backticked debt ID
that exists in the register or carry the explicit `not-a-debt` type. Label-derived IDs and fuzzy
matching are forbidden. A terminal ID-bound entry can additionally be typed as resolved history; a
non-debt cannot borrow that lifecycle.

Red first: the named closure test observed the supplied 29/7/22 denominator before the tables and
typing rule were repaired. Final command:

```sh
uv run --frozen --extra test python -m pytest -q \
  tests/repo_quality/tools/test_debt_ledger_checker.py::test_every_nonclosure_entry_is_identified_or_typed_not_a_debt
```

Exact output, exit 0:

```text
.                                                                        [100%]
```

Complete final census:

```text
explicit_nonclosure_entries=29
explicit_nonclosure_identified=18
explicit_nonclosure_typed_not_a_debt=11
explicit_nonclosure_resolved_history=7
explicit_nonclosure_unidentified=0
path:DS10-capability-discovery.md=12
path:DS11-trust-docs-posture.md=7
path:DS17-confidence-ledger-risk-spend.md=10
```

The 7 -> 18 identified movement is the eleven DS10 entries that already had real register debts. The
new eleven `not-a-debt` entries are the standing DS10 P38 denominator-label note plus all ten DS17
entries for which no exact register debt exists. The 22 -> 0 unidentified movement is therefore
11 exact IDs plus 11 explicit non-debts, not 22 invented IDs. The seven ID-bound resolved-history
entries remain part of the 18 identified entries.

Other moved checker pins are explained, not merely refreshed:

- register IDs 175 -> 178: Task O registered the corridor prerequisite, nonclosure identity, and
  quoted-evidence rows;
- open remains 27 while closed moves 100 -> 103: three new Task O open rows offset two Task N closures
  and one Task M closure;
- pytest closure selections 41 -> 43: three Task O selectors were added and one closed table-parser
  selector was removed.

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`.** Every populated explicit-nonclosure entry now starts with either its exact backticked debt ID or the explicit `not-a-debt` type; no label-derived ID was invented. Resolved history remains ID-bound and is accepted only when the register status is terminal. The complete denominator is **29 entries = 18 identified + 11 typed not-a-debt**, with **7 resolved-history** entries inside the identified set and **0 unidentified**. Its source split is DS10 12, DS11 7, DS17 10. The named behavioral closure test and the bound checker pass.

### Final bound debt-ledger receipt

This was run once, after all source commits, on a clean quiescent tree:

```sh
uv run --frozen --extra test python tools/quality/validation/check_debt_ledger.py --check
```

Exit 0. Exact metric block:

```text
register_ids=178
gy_ids=38
atlas_debt_rows=22
frontend_disposition_entries=261
frontend_ds8_assignment_rows=217
gy_history_blocks=6
gy_absent_from_register=15
gy_absent_from_register_closed=15
ds5_nonclosure_rows=27
ds5_planless_routes=4
irregular_section_e_branch_rows=1
explicit_nonclosure_entries=29
explicit_nonclosure_identified=18
explicit_nonclosure_typed_not_a_debt=11
explicit_nonclosure_resolved_history=7
explicit_nonclosure_unidentified=0
closure_signal_pytest_selections=43
closure_signal_unsupported_runners=1
closure_signal_identities_without_commands=4
closure_signal_identity_unresolvable=10
closure_signal_input_unresolvable=0
closure_signal_selects_nothing=0
closure_signal_collection_failed=0
closure_signal_collection_host_unknown=0
closure_signal_ast_collection_disagreements=0
closure_signal_count_exit_disagreements=10
Informational findings (do not block):
```

The following emitted detail is the complete unresolved-identity set; the same ten also carry the
expected `count_exit_disagreement` detail because pytest exits 4 with zero selections:

```text
DS11-EXTERNAL-A11Y-COUNTERSIGN: tests/repo_quality/docs/test_accessibility_evidence.py::test_external_countersign_is_content_bound_current_and_scope_exact
DS11-FULL-TRUST-CENTER-AND-DOCS-IA: tests/repo_quality/frontend/test_public_surface_claim_ownership.py::test_every_retained_trust_docs_route_has_an_approved_owner_and_evidence_contract
DS11-GROUNDED-PERFORMANCE: tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence
DS11-PUBLIC-SIGNATURE-POPULATION: tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound
DS11-SCOPE-ADJUDICATION-RECORD: tests/unit/core/contracts/test_scope_adjudication.py::test_four_way_ruling_is_produced_consumed_and_plane_specific
ds10-connector-acquisition-content: tests/unit/runtime/http/test_control_api.py::test_list_connectors_and_profiles_are_producer_backed
ds10-global-case-index-producer-allocation: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index
ds10-public-decision-rendering: tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound
epoch-dependency-denominator-defined-twice-incompatibly: tests/unit/scientist/validation/test_decision_validity_service.py::test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions
global-case-index-producer-missing: tests/unit/runtime/http/test_capability_discovery_api.py::test_case_provider_is_backed_by_canonical_global_index
```

## Group 3 — quoted docs-lifecycle evidence

### `docs-lifecycle-flags-quoted-paths-in-journal-evidence`

Verdict: `open` -> `closed`.

Decision: use a paired, explicit lifecycle-evidence marker, recognised only in Markdown closeout
journals. The scanner removes the enclosed bytes from the live-reference domain only when both
markers are present. An ordinary fenced block and an unclosed marker remain scannable. This was
chosen over treating every fence as evidence because ordinary documentation often places live paths
in fences. The alternative “remove four references” was rejected: the four are genuinely live stale
references, not quoted checker output, and must continue to fire.

Red first: the behavioral test initially got seven findings after adding a journal that quoted the
carried six verbatim. Final acceptance command:

```sh
uv run --frozen --extra test python -m pytest -q \
  tests/repo_quality/docs/test_docs_lifecycle_checker.py::test_quoted_evidence_is_not_a_live_reference
```

Exact output, exit 0:

```text
.                                                                        [100%]
```

Fresh deciding command:

```sh
uv run --frozen --extra test python tools/quality/validation/check_docs_lifecycle.py
```

Exit 1 with exactly the carried six findings. The output is intentionally preserved verbatim inside
the rule's explicit evidence scope:

<!-- docs-lifecycle-evidence:start -->
```text
Docs lifecycle gate FAILED:
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `status` front matter.
- [active_plan_metadata] docs/plans/active/LEDGER.md: active plan missing `owner` front matter.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-adoption-ledger.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] architecture/atlas_surfaces/atlas-v15-archive-map.json: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/reference/frontend/atlas-v15-adjudication.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
- [removed_stub_reference] docs/research/policy-operations/audits/pao-r0/pao-r0-test-and-fixture-verification.md: stale direct reference `frontend/runtime-dashboard`; use `apps/runtime-dashboard`.
```
<!-- docs-lifecycle-evidence:end -->

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`.** The lifecycle scanner now recognises a paired explicit evidence block only inside Markdown closeout journals. A properly closed block can quote the checker's output verbatim without becoming a live reference; an unclosed marker and an ordinary fenced block remain scannable, so the rule cannot hide arbitrary stale documentation. The four genuinely stale references remain live findings. The acceptance test passes, and a fresh lifecycle run remains at exactly the carried six findings rather than creating a seventh.

## Group 4 — trust posture

### Shared pre-repair replay and moved-pin causes

The complete pre-repair test-file replay collected 53 nodes and produced exactly:

```text
35 passed
18 failed
```

The eighteen failures partitioned completely:

```text
1 failing node containing 2 all-src scalar assertions: pinned 2603, live tracked src/**/*.py 2617
1 failing literal-census node: pinned (69, 31, 34), live (70, 32, 34)
1 failing identity-paragraph navigation node: pinned <= 88, live start 89
15 failing custody-appointment derivation nodes
TOTAL_FAILING_NODES=18
```

The two stale all-source pins were two assertions in one failing test node, not two nodes. The
complete node partition is therefore 1 scalar-count node + 1 literal-census node + 1 paragraph node
+ 15 appointment nodes = 18.

Every movement has a named cause:

- tracked source paths 2603 -> 2617 are +21 additions and -7 removals across intervening merged
  source growth; the all-src scalar is removed rather than re-pinned;
- the semantic invalidation set is now the complete recomputed 138-file authority/denial candidate
  set, seven candidate paths larger than the former semantic set, and is bound by its own digest;
- wrapper census `(69, 31, 34)` -> `(70, 32, 34)` is exactly the new
  `scope_adjudication.Field` wrapper from merge `55f7e553dc`;
- paragraph start 88 -> 89 is the identity-document frontmatter/informs addition in `62405090d`;
- the identity constants were reissued because ratified amendments `62405090d` and `708028756`
  changed their owned content/basis, not because a line number moved;
- the default register date moves 2026-08-26 -> 2026-09-01 because the ratified amendment was last
  reviewed on 2026-08-31.

Final recomputed posture facts:

```text
semantic_source_files=138
predicate_provenance=recomputed
ast_raw_occurrences=122
ast_exact_invocations=121
ast_declaring_files=109
ast_consuming_files=39
role_partition=76,6,6,33,1,0
direct_partition=45,20,27,10
wrapper_partition=70,32,34
denied_partition=135,43,28,50
ast_row_digest=sha256:7a123021e26de6a002309bf1cd0950ab77e98f420fe9832e032824042fc8ce26
token_row_digest=sha256:a8ca0fbb8ba42368665be3abbe8a16a04b2caf403ccc54d19586fe5ff612e408
payload_digest=sha256:581514c156fcec9528bdd485a588ccb03ca1df4df08c3a874c8286689df4ea53
source_set_digest=sha256:30658cbeedfe7d85acc168b15d3046c48e21c1d705b5f968020a2154442ab2b1
```

The final complete trust-posture test file exits 0:

```text
.......................................................                  [100%]
55 passed
```

The production checker command is:

```sh
uv run --frozen --extra test python tools/quality/validation/check_trust_claim_posture.py \
  --repo-root . --check --corruption-probes --json
```

Its exact decisive output fields are:

```text
issue_codes=["DS11-SOURCE-COLLISION","DS11-SOURCE-RUNTIME-BOUND"]
corruption_probes.probe_count=15
corruption_probes.rejected_count=15
corruption_probes.scratch_escape_count=0
write_set=[]
```

The two issue codes are the posture's governed findings, not checker failures; exit 0 and 15/15
rejected corruptions are the admission result.

### `ds11-trust-posture-guardrail-unwired-and-red`

Verdict: `open` -> `closed`.

The exact trust-posture test file is now a required command in the architecture CI `import-gate`.
The guardrail test parses the workflow YAML and matches argv tokens; a comment-only mention, step- or
job-level `if: false`, and step- or job-level `continue-on-error: true` all fail. The five adversarial
workflow cases pass, so textual presence cannot satisfy wiring.

The architecture test file's only remaining red is
`test_checkpoint_scope_uses_candidate_security_route`; it reproduces unchanged on the pinned Task O
base. The architecture guardrail command likewise reproduces its deep-import acquisition-admission
bundle on that base. Task O's changed paths have zero intersection with both complete input
denominators, so P41 classifies both as inherited. The deciding rule for changing that classification
is exact: either the same command must stop reproducing at the slice base, or a Task O path must enter
the gate's complete input denominator. A future named prerequisite landing without either fact does
not transfer ownership to Task O.

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`.** The pre-repair 53-node posture file was 35 green / 18 red: one duplicated stale all-source scalar node, one wrapper-census pin, one identity-paragraph navigation pin, and fifteen custody-appointment projections. The generator now derives a complete recomputed 138-file semantic authority/denial source set instead of pinning all `src`; every moved authored value has a named merge or ratified-document cause. The exact 55-node posture file is wired into the architecture CI import gate. Parsed-workflow tests reject comment-only, disabled, and allowed-to-fail substitutes. The final checker exits 0, rejects 15/15 corruption probes, escapes no scratch path, and writes nothing in check mode.

### `trust-claim-posture-receipt-stale-on-any-src-change`

Verdict: `open` -> `closed`.

The receipt is now bound to the complete recomputed set of Python files that can contribute an
authority/denial posture fact, not every file below `src`. Its source-set digest and per-source bytes
are load-bearing. Adding or changing a contributing file invalidates the receipt; changing an
unrelated source file does not. The source-set classifier and its adversarial additions are part of
the generator, so no growing scalar total is the property.

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`.** Trust-posture invalidation is now bound to a `recomputed` semantic source predicate and the exact 138-file authority/denial candidate set, with source-set and content digests. An unrelated `src` edit no longer makes the receipt stale; adding, removing, or changing a contributing source does. The old 2603/2617 all-source scalar is removed rather than re-pinned, and adversarial source-set substitutions fail closed.

### `trust-posture-custody-appointment-requires-open-row`

Verdict: `open` -> `closed` by design decision.

Decision: “appointed, and its work is blocked” is now an admitted source vocabulary. Appointment
identity and owner remain intact, while the projected public claim becomes `blocked`. The alternative
digest re-pin was rejected because the old predicate rejects a blocked source at every digest and
would preserve a false standing commitment. A terminal appointment is different: `closed` is admitted
only with its closure receipt, and the dashboard recomputes the projection rather than trusting a
consumer-authored status.

The mixed real source state is exercised: lifecycle orchestration is blocked, signature population is
open, and the watcher is closed. The producer returns a blocked posture instead of raising. The ten
targeted posture-domain unit tests pass:

```text
..........                                                               [100%]
10 passed
```

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed`, with an appointment-vocabulary decision.** A custody source may now be truthfully `appointed` while its work is `blocked`; the appointment remains owned and the derived public claim projects `blocked` instead of raising. Digest re-pinning was rejected because it cannot change the old exact-open predicate and would keep a public commitment standing on work the register says is blocked. Closed appointments remain fail-closed unless their admitted closure receipt is present. The real blocked/open/closed source mixture is produced, consumed by the dashboard projection, and covered by negative tests.

## Group 5 — Atlas timing workload identity

### `atlas-python-governance-workload-identity-drift`

Verdict: `open` -> `closed` for workload identity. The performance sample remains honestly
unavailable because the complete semantic run ended red.

The old 67-test receipt and later 181/190 observations were scalar snapshots of a growing set. The
replacement identity is structural and recomputed:

```text
schema_version=policyos.timing.pytest_workload.v1
predicate_provenance=recomputed
pytest_version=9.0.2
test_paths=2
frontend_disposition_nodes=194
status_retirement_nodes=41
diagnostic_total_nodes=235
node_map_digest=sha256:3023346d42a16fa2f21ab2a0dc161f840b122747c47cec75c491ccdde0be1ac7
frontend_disposition_source_digest=sha256:9873eeff8e5b81a722762e8a9663129616548957470acf7750b9ac060b038bbb
status_retirement_source_digest=sha256:e54e92d8ffc9856dda1e896894cbf869496b9d3d63f05a713bd5b2c98a1bd0ba
pytest_ini_digest=sha256:61270205a9f573a090b3c051a4b78351e67308a49e21660dbf33e76186d799eb
```

The total 235 is diagnostic output, not a pinned gate. Admission compares the exact ordered node map,
the exact two source digests, pytest version, and configuration digest. Growth changes the structural
identity automatically.

#### Red-first widening and correct mechanism

The first closure test was observed red against the stale scalar receipt. During delta review, a
same-cardinality node substitution passed the initial direct verifier: that is the same P32/P40 class
one level deeper, not a new row. The mechanism was widened once to the quantity the property needs.
The timed runner now launches one child session whose plugin emits the complete selected workload and
the ToolRunRecord; the receipt binds exact argv, cwd, attempt ID, raw ToolRunRecord bytes/digest,
source/config digests, and the same-child ordered node map.

The generic producer rejects:

- a session item outside the selected path set;
- a recorded map that omits any session item;
- post-collection deselection such as `-k` relative to the complete pre-deselection set;
- mixed file and directory selections;
- disabled or missing receipt plugin, with dedicated exit 74;
- stale output from an earlier attempt;
- same-cardinality node substitution and surplus source paths.

Signals and ordinary uncaptured child exits remain preserved. The direct verifier rejects unsupported
schema and `consumer_asserted` predicate provenance. These are behavioral child-process tests, not
JSON marker tests.

The whole timing test file's first final replay exposed a stale `max(empty)` test assumption. Its exact
node was observed red and repaired to assert the new honest unmeasured state. Final whole-file output,
exit 0:

```text
........................................................................ [ 71%]
.............................                                            [100%]
```

The row's named identity test also exits 0:

```text
.                                                                        [100%]
```

#### Final same-child receipt

Command:

```sh
POLISYOS_TOOLS_TIMING_LOG=/Users/deniskopylov/polisyos/.worktrees/debt-o-instrument-integrity/policy-engine/_build/task-o/atlas-python-governance-final.jsonl \
POLISYOS_TOOLS_TIMING_REGIME=serialized \
uv run --frozen --extra test --with 'jsonschema>=4.25' \
  python tools/quality/testing/run_timed_suite.py \
  --lane atlas.python-governance:default \
  --capture-pytest-workload \
  --receipt-output docs/superpowers/timing-evidence/2026-09-01-atlas-python-governance.jsonl \
  -- uv run --frozen --extra test --with 'jsonschema>=4.25' python -m pytest \
  architecture/atlas_surfaces/test_frontend_disposition_register.py \
  architecture/atlas_surfaces/test_status_retirement_inventory.py -q
```

The child exits 1 with 33 semantic failures and 202 passes. That red is deliberately not admitted as
a performance sample. Exact persisted execution fields:

```text
schema_version=policyos.timing.pytest_execution_receipt.v1
attempt_id=fd891907eecc425ab9446fde28a9cf19
cwd=.
started_at=2026-09-01T15:46:43.516605+00:00
duration_ms=843151.379
exit_code=1
status=failed
preflight_status=ok
regime=serialized
tool=atlas.python-governance
category=external
mode=default
tool_run_record_digest=sha256:9f374589d2b00d870e2fdd5eeb2e22e400844a2b70b8bbbf4a2c2b5f1a2d2a7a
admission=terminal_not_declared_healthy
samples=[]
measured_p95_ms=None
timeout_ms=None
```

The deciding rule for the remaining unmeasured performance posture is explicit: only a complete
same-child run ending in a declared healthy terminal may add a sample, p95, or timeout. If new tests
land without a new healthy run, the source/node digest changes and the verifier marks the old receipt
stale; it never silently reuses the old total.

#### Architect transcription prose

> **TASK O 2026-09-01 — `open` -> `closed` for workload identity.** Atlas Python-governance timing is no longer bound to the stale scalar 67, 181, 190, or today's 235. The producer captures the complete ordered node map in the same child that executes it and binds exact argv/cwd, attempt ID, raw ToolRunRecord, pytest/config identity, and both source digests. The current diagnostic map is 194 + 41 nodes with digest `sha256:3023346d42a16fa2f21ab2a0dc161f840b122747c47cec75c491ccdde0be1ac7`; adversarial same-cardinality swaps, deselection, mixed selections, plugin nonreceipt, and stale output fail closed. The final complete run ended with 33 semantic failures, so it is preserved as evidence but contributes no sample, p95, or timeout. Only a complete healthy same-child run can change that declared unmeasured state; future workload growth changes the structural identity automatically.

## Verification closeout

The expensive debt-ledger collector was run once only, on the source-frozen quiescent tree; its exact
exit-0 metrics are recorded above. The two other complete files whose own behavior was changed were
run once at source freeze:

```text
tests/repo_quality/tools/test_trust_claim_posture.py: 55 passed
tests/repo_quality/tools/test_timing.py: 101 passed
```

Targeted runner-compatibility tests: 6 passed. Targeted timing-receipt adversarial test: 1 passed.
Dashboard posture tests: 35 passed; dashboard TypeScript typecheck exited 0. Ruff over every changed
Python file exited 0 with `All checks passed!`; mypy over the changed timing implementation exited 0;
`git diff --check` produced no output.

The carried architecture reds are not concealed:

- `tests/repo_quality/tools/test_architecture_phase3.py` has one red and 24 passes; the same named red
  reproduces at `d1680bd0d`;
- `uv run --frozen --extra test polisyos-tools architecture guardrails check` reports the same
  deep-import acquisition-admission bundle at head and `d1680bd0d`.

Under P41 they remain inherited and input-disjoint. No Task O register row is left open. If either red
stops reproducing at the slice base, or Task O's changed paths enter its complete input denominator,
this verdict must be reopened; landing a named prerequisite without that evidence does not silently
change ownership.
