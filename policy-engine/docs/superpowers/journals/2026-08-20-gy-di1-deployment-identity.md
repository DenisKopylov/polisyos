# GY-DI1 — deployment identity narrowed to the authority import closure

Date: 2026-08-20

Branch: codex/gy-di1-deployment-identity

Slice base: c054752637a9589fb99808bcdac5a97ae83f2906

Source freeze: 59e4b7c7b51a647b0c53255d6d257b93c0d0a299

Declared-transition commit: 015a062a81ba4e3e4ba06667ac6996230d0f0d1b

Accepted artifact commit: f4e4522e47760698fc2d05e293c7d355564c04ec

## 1. Entry, scope, and defect direction

GY-DI1 repairs the deployment identity used by the confidence-ledger authority path. The old
mechanism hashed every Python file under src/polisyos plus pyproject.toml and uv.lock. The repaired
mechanism derives the transitive repository-local import closure of the authority entry point and
adds only those two deployment-metadata files. It contains no enumerated Python-module list.

The defect direction remains the one registered by the plan: over-binding is conservative. It can
withdraw authority and force replay after an unrelated edit; it cannot falsely grant authority.
This slice closes false withdrawal and replay/governance cost. It does not claim a security repair.

The mechanism budget contains only:

- src/polisyos/runtime/quality/confidence_ledger.py
- tests/unit/runtime/quality/test_confidence_ledger.py
- architecture/production_quality/ci_tiers.toml

The transition declaration, this journal, the three reissued artifacts, and the required plan
standing are P39 record companions, not mechanism paths. No other owner or lane was repaired. The
plan's line 7 was not edited.

## 2. Isolation and toolchain baseline

Before the first repository command, the worktree path, branch, base HEAD, attachment, and empty
short status were checked. All repository mutations stayed inside
/Users/deniskopylov/polisyos/.worktrees/gy-di1-deployment-identity. The canonical dependency
environment in the parent checkout was read only. No sibling worktree was switched, stashed,
cleaned, or written.

The fresh worktree initially lacked a receipt-equivalent dependency/data profile. Bootstrap and
validator results from that state were classified as tooling non-receipts, never product findings.
In particular, the apparent N8 catalog drift under the provisional environment was a dependency
profile mismatch; its package-level cause was not retained as an admitted receipt and was not
promoted as upstream debt.

The admitted profile used a worktree-local clone of the canonical dependency runtime, with local
source first and Python started with -S:

- HOME=/Users/deniskopylov
- LANG=C.UTF-8 and LC_ALL=C.UTF-8
- JAX_PLATFORMS=cpu
- PYTHONHASHSEED=0
- PYTHONNOUSERSITE=1
- PYTHONDONTWRITEBYTECODE=1
- PATH begins with the worktree's policy-engine/.venv/bin
- PYTHONPATH is worktree src, worktree product root, then the matching Python 3.14 site-packages

The production_data dependency was linked read-only. Under that admitted profile, the canonical
short N8 preflight passed in 17.2 s and N10a passed in 21.5 s (7.604 s internal). A final N8
catalog-provenance replay under the worktree-local clone also returned status=pass,
ambient_findings=[] in 10.902 s. The parent checkout was not modified.

## 3. Red first and the P40 ledger

The first semantic target was the missing negative control. Against the legacy all-Python
denominator, adding or changing an unrelated repository module changed deployment identity and
invalidated the canonical session. The paired test was then made green by derivation, not by adding
or removing hand-picked filenames.

Mechanism review rounds ended at 2 / 2. Each item below was an Important finding against the
mechanism and consumed one round; the shared-class classification controls the widening response:

1. Round 1 / 2, Important, SAME CLASS ONE LEVEL DEEPER. Runtime-mode resolution walked
   TYPE_CHECKING arms and therefore still bound type-only providers. The repair made both runtime
   and owner walks use the executable-node traversal and added a nested type-only falsifier.
2. Round 2 / 2, Important, SAME CLASS ONE LEVEL DEEPER. Literal dynamic-import strings in dormant
   functions were still a proxy for imports the authority path executes. The mechanism widened to
   two derived modes: runtime identity follows executable static edges and literal PEP 562
   re-exports; owner/tool closure additionally follows literal dynamic targets and tools. A real
   session-path trace falsifies invocation of unadmitted dormant targets.

Round 2 was the second finding of the same class, so the P40 breaker widened the mechanism and
declared the bounded residual below. Only later findings already covered by that residual consume no
additional round.

The repository has no general interprocedural call-graph capability that can prove every possible
future dynamic call. That is the declared bounded residual. On the complete current source census,
seven literal repository dynamic targets sit outside the runtime closure; the real authority
session trace observed zero of them across 279 imports. Loaded-code evidence is independently
reconciled at admission, so an actually loaded provider cannot be replaced by a narrowed manifest.
After round 2, same-class examples fold into this limitation and do not trigger another patch.

Artifact-custody reviews found separate companion issues after source freeze: a declaration-trusted
artifact denominator, receipt persistence outside the rollback envelope, and writer-HEAD binding
through a proxy. They were classified under P32/P35/P38 as artifact-custody classes, not GY-DI1
mechanism rounds. The final harness independently re-derived the registry-plus-PDC denominator,
persisted armed/final/fallback receipts atomically, and proved the writer HEAD descended from the
source freeze with zero source/tool or allowed-artifact commit drift.

## 4. Mechanism

The authority module now has one derivation chain:

1. _resolve_authority_import_closure parses repository source from the ledger entry point.
2. Runtime traversal follows executable static imports, nested imports, and literal PEP 562
   re-export providers while excluding TYPE_CHECKING arms and dormant literal dynamic calls.
3. _derived_authority_import_closure recomputes the closure and requires exact equality with the
   import-time closure.
4. _deployment_relative_paths_from_closure turns that admitted closure into paths and adds
   pyproject.toml and uv.lock.
5. The deployment baseline and quick fence consume those paths.
6. Session admission also recomputes the loaded-code manifest and compares its local-code evidence
   projection to import-time evidence.

The fixed metadata pair is not a Python authority list. All source modules enter through derivation.
The quick fence uses the already admitted import-time closure so steady-state admission does not
rescan the full source tree.

## 5. Five done-when clauses

| Clause | Behavioral evidence |
| --- | --- |
| Derived transitive closure, never an enumerated module list | test_deployment_identity_manifest_is_complete_and_import_order_independent; test_authority_import_closure_tracks_nested_runtime_but_not_type_only_imports |
| Inside-closure change turns the receipt red | test_deployment_identity_changes_for_closure_member_but_ignores_unrelated_module; test_canonical_session_rejects_closure_drift_but_ignores_unrelated_source; test_canonical_session_fails_closed_when_loaded_deployment_bytes_change |
| Outside-closure change does not | The paired identity/session tests assert an unchanged identity, usable session, and no extra ledger events after an unrelated edit |
| Forged or rehashed closure manifest fails closed | test_loaded_code_manifest_fails_closed_on_missing_declared_member; test_rehashed_closure_manifest_cannot_narrow_authority_admission; test_rehashed_loaded_code_manifest_cannot_replace_runtime_evidence |
| Closure includes every module the authority path imports | test_authority_import_closure_includes_every_live_repository_import_binding; nested/type-only, owner dynamic-boundary, and real dormant-dynamic session tests |

The new tests are registered in architecture/production_quality/ci_tiers.toml as fast-pr,
team-runtime-quality coverage.

## 6. Complete binding-breadth census

The complete source and path census at the source freeze was:

| Quantity | Count |
| --- | ---: |
| Python files under src/polisyos | 2,560 |
| Legacy deployment paths including pyproject.toml and uv.lock | 2,562 |
| Derived executable authority modules | 94 |
| Final deployment paths including the two metadata files | 96 |
| Legacy-bound paths now outside deployment identity | 2,466 |
| Reduction | 26.6875x |

The registered 120-module / 21.4x figure described the pre-review resolver proxy. The complete
reviewed census corrected that proxy by excluding type-only and dormant-dynamic edges. The final
identity is 2,562 to 96, not a longer hand-picked list. The independently derived owner/tool closure
contains 2,001 modules and is not substituted for runtime deployment identity. There are 595 Python
paths outside both closures.

The real outside witness was selected generically as the first POSIX-sorted Python path outside both
derived closures:

src/polisyos/berl/benchmarks/__init__.py

Before, during, and after mutating that witness in an isolated source copy, the live runtime identity
was exactly:

policy-engine-deployment:sha256:53618d6b3dba9590997d9bea42713f878dc6bcbca777f26d6db65fe8d9e3db03

## 7. Source freeze and reviews before replay

The source history was appended in four boundaries:

- c52bdfb09 — derive deployment identity from the authority closure
- da0c17079 — exclude type-only authority edges
- 69aaa1b76 — add the dormant-dynamic falsifier
- 59e4b7c7b — compose owner and runtime closure modes

At 59e4b7c7b, all tracked source was frozen. Three independent read-only reviews returned GO with no
new Blocking or Important class. The accepted bounded residual was recorded before any cold replay.
The transition declaration then received its own full and delta reviews. Its final review at
015a062a8 was GO. No post-wave source review re-priced the artifacts.

## 8. Non-persisting measurement

The real writers were first run through non-persisting candidate paths. All three deployment-bound
artifacts moved, so the wave could not be skipped:

| Artifact | Before bytes / SHA-256 | Candidate bytes / SHA-256 | Changed leaves |
| --- | --- | --- | ---: |
| N9 promotion | 183,066 / ba71198ef9b9227d6ba8094e68d15a3a68721709f4ff87ceb1f94304ce78a484 | 183,066 / 08877f171fb08424896d177dac5aa7f7801dcce4bdc2ce77f9faa3690cc2cd1e | 67 |
| Generation cycle | 183,254 / 695fd482dc525ec11a15921c93cebbc9349a2b38af1789c87cb24828bfc4f59e | 183,254 / 2e931ccfcd07141178eb622ec03348a7db3d1f437cc396b5f909eba41ae7136a | 43 |
| N11 confidence ledger | 977,814 / 4a0fdf065b0d1a3c283f2f0f8bef55b5d8e485d59634646d165d7ea663f3adc9 | 980,647 / dd8f4be3afc8deefade824cb4bb4de0cce0d051fa262abb0c427c157ea770391 | 5,277 |

Total declared changed leaves: 5,387.

The outside-witness mutation produced byte-identical N9 and generation candidates. The real N11
candidate's recursively embedded deployment-identity fields matched the unchanged live admission
identity, and the witness was outside both runtime and owner closures. This is the deployment-identity
negative on each real artifact at the level this slice changes. A second full cold N11 derivation
under the outside mutation was deliberately not run, so full N11 byte equality is not claimed.

The active N9/generation measurement was bracketed by load averages 3.90/5.13/4.71 and
3.16/3.73/4.16. The N11 run was bracketed by 2.52/2.79/2.94 and 3.72/3.67/3.64. Both are contended
regime receipts and are not promoted into a clean budget.

N11 completed a cold owner derivation in 1,220.234 s, a cache-hit derivation in 224.767 s, and
1,467.517 s observer wall time. The two candidate passes were byte-identical, all 50 corrupt-field
cases went red, the worker reported profiling_stop=false, and its process group was clean. No killed
or unbootstrapped run was used as a duration sample.

## 9. Declared transition and rollback contract

The durable declaration is:

docs/superpowers/journals/2026-08-20-gy-di1-artifact-transition-declaration.json

Its raw-file SHA-256 is
241761a9859e536cab78bae8e1140ae5b7b4d15d8f2d17ad260a60c588fa0a0a and its canonical manifest
content hash is
sha256:aee981251d9dfb9282ee410db827e87e35279cb815b5b7d10f438602f91a8768.

The declaration binds 3,286 source/tool files under
sha256:31845637caccc9598e50e34d87c1c9e182ee19580f3c78646a0365d0d356e0a8.
It independently expands 437 generated-artifact registry specs to 713 tracked files, unions those
with 509 tracked policy-design-case files, accounts for their 308-file intersection, and obtains the
complete 914-file / 47,532,401-byte artifact denominator. Exactly three outputs are allowed and 911
preimages are protected.

The declared artifact-scope transition is:

- before:
  sha256:3f5508d734d90345c21e40396ab1595fe7d4582597b810fa91fc144667d6c1a4
- after:
  sha256:5f9b8b4375fc34fb8240836d43a01a194557caec26bb5c08874c2a2843477f04

Before the first governed replacement, the writer snapshots all 914 preimages. It then checks exact
branch and HEAD before and after each temporary write and immediately before and after each atomic
replacement. Any path, byte, leaf, source-scope, protected-preimage, or attachment mismatch restores
the three allowed files by the same guarded atomic path.

## 10. Guarded replay receipts

The first writer attempt rejected its own post-write status because Git returned worktree-root paths
while the harness expected product-root paths. This was a P38 harness-coordinate non-receipt, not an
artifact or mechanism finding. It atomically restored all three original bytes, verified all 911
protected preimages, and left the tracked tree clean. Its append-only receipt is:

/private/tmp/polisyos-gy-di1-candidates.Iobu7X/writer.receipt.json

That receipt records status=rolled_back, rollback_error=null, the snapshot
/private/tmp/polisyos-gy-di1-914-preimage.75okrb0p, and 25 exact branch/HEAD checks spanning promotion
and rollback. Its raw receipt SHA-256 is
5444ecacbe320c6a714a0288fadd02ccadc87a74b5fbc2f92711ed275f1074b6. A read-only delta review of
the coordinate normalization returned GO before retry.

The accepted one-batch receipt is:

/private/tmp/polisyos-gy-di1-candidates.Iobu7X/writer.receipt.2.json

It records status=accepted, 13 exact branch/HEAD checks, 5,387 observed declared leaves, all 911
protected preimages exact, rollback_armed=true, rollback_performed=false, and snapshot
/private/tmp/polisyos-gy-di1-914-preimage.izuw9cyp. Immediate raw-byte readback reproduced the three
declared candidate hashes. Its raw receipt SHA-256 is
e4d1100b4ee646071700411d88525394977cae5a53bbd099a924cd2e695403b4. The exact three artifacts were
committed together at f4e4522e4.

The failed receipt was never overwritten, and an armed or completed receipt path cannot be silently
reused. The first attempt is not counted as an accepted replay wave; it is retained as the rollback
receipt for the refused harness operation.

## 11. Verification before closeout

At the source freeze, the exact 21-test deployment/closure slice was green after its red-first
pollution repair. An 11-variant loaded-callable matrix and the synthetic owner/runtime-closure
falsifiers were green. The N11 two-pass and 50-case corruption receipts described above were also
green. No full pytest run was launched.

A fresh post-write acceptance receipt then ran the ten property-defining nodes from the table above:
10 / 10 were green, exit 0, in 114.65 s observer time. Its uptime pair was
2.18/2.69/2.62 to 2.72/2.76/2.66, so the duration is contended-regime evidence only. An earlier
post-write invocation of the full 21-node slice completed after its terminal session identifier was
not retained and lacked a start uptime sample; it is explicitly a harness/timing non-receipt and is
not counted.

Committed-artifact readback used the admitted source-first -S profile:

- N9 recomputed exactly and passed in 26.041859 s.
- Generation-cycle recomputed exactly and passed in 23.092681 s.
- The committed N11 payload validated against itself with status=pass and issues=[]; the already
  admitted two-pass cold candidate is the recomputation receipt, so no second cold wave was run.

The combined readback took 75.65 s with load 2.61/2.72/2.65 to 3.10/2.86/2.71. It is also a
contended-regime receipt, not a clean budget.

Changed-path Ruff and git diff whitespace validation are green. The architecture guardrail
reproduced the same six deep-import additions seen at the slice base:

1. runtime.http.services.channel_contracts to core.artifacts.manifest
2. runtime.http.services.channel_contracts to core.contracts.decision_validity
3. runtime.http.services.control.lex_pipeline to lex.knowledge.store
4. runtime.http.services.control.lex_search_projection to core.contracts.runtime
5. runtime.http.services.control.lex_search_projection to lex.knowledge.types
6. scientist.orchestration.engine.checkpoint to core.security.tenant_context

None of those reported source files is a GY-DI1 mechanism path, and no baseline sync or unrelated
repair was attempted. Because the aggregate scanner's complete input denominator still includes all
source, including the changed confidence-ledger module, P41 classifies the aggregate gate
not_established rather than inherited-green. The command took 16.72 s with load
3.00/2.85/2.70 to 3.17/2.89/2.72.

## 12. Outcome and boundary

The deployment identity now binds 96 derived deployment paths rather than 2,562 generic paths.
Inside drift withdraws authority; outside drift does not. A forged or rehashed closure or loaded-code
manifest fails closed. Runtime import coverage is checked against the live repository bindings and
the loaded-code evidence projection.

This closes semantic_test_missing for GY-DI1. It does not change GY-N11's legitimate replay for
polisyos/fabric/__init__.py, does not claim a security vulnerability, and does not absorb work owned
by GY-PA2, DS7, GY-PA1, N8, or N10a.
