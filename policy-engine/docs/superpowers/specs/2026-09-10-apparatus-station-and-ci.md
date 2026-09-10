# Apparatus station and original CI inventory: research decision

Status: stage 1 decision; execution starts after the root's stage-1 commit/readback.
Owner: apparatus station workstream; root owns shared configuration and commits.
Source under inspection: `c49449343`, attached worktree `codex/measuring-apparatus`.
Historical CI source: `20082e545ba89cefc2fd913e1723f6ef7c63df39`.

## Scope and evidence discipline

This document addresses `odfpy-core-dependency-is-sourced-from-a-non-canonical-index`
and individually triages the contents of `ci-red-inventory-on-20082e545`. It also
separately adjudicates the fresh observations about missing pytest prerequisites
and an offline JAX provisioning failure. Neither register nor ledger is edited.
Historical CI failures are historical observations, not a claim that today's tree
has the same failures. Current-source inspections below are labelled as such;
only executed current commands can become current verdicts.

Read before design: root `AGENTS.md`, `CONTRIBUTING.md`, and
`docs/reference/policy-design-case-failure-patterns.md`. Pattern pass:

| Pattern | Existing problem | Smallest correct pattern / acceptance |
| --- | --- | --- |
| P27/P31 | CI canary bypasses the existing Python provisioning owner; mutation workflow and canonical runner both use obsolete CLI flags. | Compose the existing setup action / mutation runner. A sibling caller must not retain the defect. |
| P29/P32/P38 | Installed package names, a successful process exit, and marker-based mutation configuration are weaker than an executed test or mutation. | Run a real import and bounded test; mutation must create and kill a real mutant with the declared scope. |
| P35/P36 | The CI inventory prose understates the original failures and conflates their causes. | Parse complete job/log/artifact sets, preserve finding identities, cite this document's CI IDs and raw receipts. |
| P37 | A warmed interpreter or borrowed site-packages tree can supply undeclared prerequisites. | Cold local environment, pinned interpreter/toolchain, explicit source selection; fail or report UNRUN before claiming product quality. |
| P40/P41 | A second station workaround can hide the same prerequisite class; old CI red is not evidence of present inheritance. | Widen provisioning at its owner; no automatic product fixes, no inherited label without exact-base replay and input intersection. |

Apparatus chains have existing producers and consumers. The missing property is
`verification_missing` for a cold default pytest station and mutation scope; this
document itself is not an implemented capability. External product surface is
`surface_out_of_scope`: output belongs in CLI/CI receipts, not a policy authority API.
Serialized resources: shared `.venv`, uv lock generation and governed artifacts.
Root provisions those; this lane only downloads read-only CI/public package evidence
under its ignored raw directory and writes this decision document.

## C-ODF: the registered remote-host problem is already repaired in source

The named row describes a piwheels URL, but commit `70da48c23` already selected the
row's **vendor** alternative. At the slice base, `pyproject.toml` and `uv.lock`
both point at `vendor/wheels/odfpy-1.4.1-py2.py3-none-any.whl`.
`vendor/wheels/README.md` records the custody/reachability rationale and removal
condition. The wheel remains a core dependency because the real ODS consumer is
`CKANResourceConnector._parse_resource` through pandas' `odf` engine. Moving the
dependency out of core would change a working ingestion capability unnecessarily.

Research repeated the byte comparison against the canonical PyPI 1.4.1 sdist,
downloaded from the URL in its release metadata. Complete denominator: every regular
file under `odf/` in each archive, all file types. The two sets each contain 34 files;
missing in either direction and changed content are empty. The sdist SHA256 equals
PyPI's metadata (`db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec`)
and the vendored wheel equals the lock's
`1d1c3ea36a422d3c5cd4c2457ea0e0be59841d6c26d28bd3d5e43f060565d11b`.
This is source-subtree equivalence, not an assertion that wheel metadata equals
sdist metadata. The complete 1.4.1 release-file list has an egg and sdist, no wheel.

Disposition: **retain the existing vendor decision**; no pyproject or lock change
is needed for this debt. Validate the real consumer with exactly
`tests/repo_quality/test_dependency_runtime_witnesses.py::DependencyRuntimeTests::test_ckan_reads_real_ods_and_enforces_limits`.
It reads a generated multilingual/multisheet ODS and rejects malformed input and a
row-limit violation. Final cold check must install the locked local wheel, with
piwheels unreachable, then run this test. Corrupting the wheel with its locked hash
unchanged must fail installation; mere path presence is insufficient.

**That local-wheel hash behavior was executed, not assumed.** A tiny isolated
project depends only on the vendored ODF copy. Pinned uv 0.9.21 generated its lock,
then `uv sync --frozen --project <probe-project>` using a fresh environment and
empty cache installed the original wheel (exit 0). The probe appended one benign
comment to `odf/__init__.py`, updated that member's wheel RECORD hash/size, rebuilt
a valid ZIP and left uv.lock byte-identical. The same frozen sync with a second
fresh environment and empty cache exited 1 explicitly on the wheel hash mismatch:
expected `1d1c3ea3…565d11b`, computed `52814eb4…96aebbd`. This verifies archive
content binding, including a valid internally consistent replacement; failure
was not merely invalid ZIP or stale internal RECORD. The real repository wheel,
pyproject and lock were untouched. This narrow probe does not substitute for the
full-repository cold ODS consumer witness.

Boundary: `[tool.hatch.build.targets.sdist].include` does not explicitly include
`vendor/`. The repository-checkout installation covered by this row has the wheel;
a released sdist/package distribution is a distinct packaging seam and no closure
claim is made for it without a build/extract/install witness. Likewise plain pip
does not honor `tool.uv.sources`; core-wheel acceptance must use the pinned uv
source/export path. Do not change ODS semantics, add a new index, or reopen a source
build to make this row appear fresh.

## C-STATION: two fresh observations, two distinct causes

### C-STATION-1: fresh plain pytest prerequisites

At `c49449343`, `project.optional-dependencies.test` already owns pytest,
pytest-asyncio, pytest-benchmark, pytest-xdist, hypothesis, jsonschema, rdflib and
`policy-engine[runtime-http]`. `pytest.ini` unconditionally uses
`--benchmark-storage`; repository test setup uses hypothesis. The default uv
development group owns only libcst. Plain `uv run pytest` in a fresh project
environment therefore does not request the test extra. A pre-existing pytest on
PATH may make this look like a pytest/plugin or hypothesis error instead of a
missing executable. Root independently replayed the prerequisite import in stage 1
using pinned uv 0.9.21, a separate new environment and an empty uv cache, with
`PYTHONNOUSERSITE=1`. Frozen default selection installed 115 packages and then
exited 1 with `ModuleNotFoundError: No module named 'pytest'`. This is a measured
fresh omission, not a hypothesis or an in-place repair of the shared dashboard
environment. Complete output: `raw/baseline-default-prerequisites.log`.

The second executed command, ordinary `uv run --frozen pytest` selecting only the
ODS node, exits 1 before running a product test. Its traceback resolves pytest to
`/opt/homebrew/lib/python3.14/site-packages/_pytest` and fails loading
`_helpers.artifacts` because that ambient interpreter lacks cryptography. Complete
output: `raw/baseline-default-pytest.log`. Thus fresh omission has a measured
**wrong-station fallback** consequence. The current symptom differs from the
original hypothesis/benchmark report and is not retroactively relabelled as that
same error string; both expose absence of the default test-installation edge.

This is **distinct** from the registered frontend child using the wrong interpreter:
one is absent default prerequisites; the other is a provisioned prerequisite not
reaching the child process. Do not combine their finding counts. It is also not a
pytest configuration defect: removing the benchmark option merely conceals the
unmet installation contract.

The original frontend job's complete setup log explicitly installs
`jsonschema==4.25.1` and `jsonschema-specifications==2025.9.1` under `extras: dev test`
before its child reports missing jsonschema. This rules out an absent declared
dependency as that historical child's explanation; interpreter selection is the
dashboard lane's seam. Today's ambient Python may already have the package, so
ordinary green alone cannot falsify a PATH-dependent child.

Proposed root edit: append `"policy-engine[test]"` to `[dependency-groups].dev`,
reusing the existing extra rather than duplicating package names/version constraints.
Regenerate the lock without upgrades and inspect the complete package/version delta.
The optional `dev` extra and the dependency group named `dev` are different owners;
adding test to the optional extra alone does not fix default uv execution.

Consequences for every other lane:

* Architecture/default uv checks gain test+runtime-http dependencies; their input
  semantics must still be checked from the selected repository, not the new site.
* Schema export/default execution gains these imports. Cold equality remains
  required; availability is not proof that optional-import-dependent output is stable.
* Dashboard Python-child provisioning can reuse the same owner, but interpreter
  identity/provenance still needs the dashboard lane's repair.
* Explicit core export/install with `--no-default-groups --no-dev` is unchanged.
  Plain/default sync and the docs profile become larger; docs-only installations
  can explicitly opt out if they intend that narrower station.
* Contributor runtime/research profiles already request test, so their intended
  package union does not grow. The canary must still declare its actual profile;
  obtaining FastAPI accidentally through test is not a durable canary contract.

Official uv semantics and local `uv run --help` distinguish exact `sync` from
inexact `run`: the initial hypothesis that plain run necessarily removes earlier
extras is withdrawn. The supported explanation is **fresh omission**, not measured
removal. References: [uv dependency groups](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups),
[uv syncing](https://docs.astral.sh/uv/concepts/projects/sync/).

Exact cold acceptance protocol, executed by root after dependency authorization:

1. Use a fresh disposable checkout/environment and pinned uv 0.9.21; remove inherited
   `PYTHONPATH`, `VIRTUAL_ENV`, `PYTHONHOME` and user-site effects from the child.
   Do not pre-sync extras or borrow another `.venv`. Final receipt records interpreter,
   sys.path and import origins alongside the actual gate output.
2. Run ordinary `uv run --frozen python -c "import pytest, pytest_benchmark, hypothesis; print(pytest.__file__, pytest_benchmark.__file__, hypothesis.__file__)"`.
   Then run ordinary `uv run --frozen pytest <absolute ODS node above>` without
   disabling addopts/conftest or injecting plugins. Same argv from product root and
   a nested product directory must have the same verdict.
3. In a disposable copy remove only the dev-to-test edge, leaving test extra and
   pytest.ini intact, and start a new environment. The prerequisite import must
   fail, and ordinary pytest must not claim a test verdict. A warmed environment
   is not an omission falsifier. This probe tests dependency selection; the ODS
   positive tests a real configured consumer.

### C-STATION-2: offline JAX cache miss / borrowed site packages

The locked `jaxlib==0.8.2` has a cp314 macOS arm64 wheel explicitly recorded in
`uv.lock`; the issue is not absence of a platform wheel. Offline sync cannot
download a wheel missing from its chosen cache. A prior station account of this
same mechanism exists in `docs/superpowers/journals/2026-08-08-gy-infra-3-step0.md`
(setup table: offline `jaxlib==0.8.2` cache miss), but this is not the odfpy index
or hnswlib no-wheel class. The particular fresh `.pth` workaround's bytes/path
have not been supplied/read here: **not_established**, not inferred from a green test.

Root's current online provisioning receipt successfully downloads JAX/jaxlib,
hypothesis and pytest-benchmark. Thus no evidence currently warrants a JAX version
or dependency-boundary change. Correct action: provision from locked wheels using
the permitted network, or prepare a complete content-verified offline wheel/cache
set explicitly; if neither is available, report **UNRUN/setup**. Never add a `.pth`
pointing at the main worktree/system site-packages as a closure station.

Falsifier: an empty cache plus `--offline` must fail before tests with the exact
missing artifact; the same frozen dependency selection online must install and
import JAX from the new environment. This measures availability, not product logic.
A package import origin outside the cold environment fails station admission even
when tests happen to pass. Final cold witness must pin uv: local Homebrew uv is
0.10.6, while `uv tool run --from uv==0.9.21 uv --version` was executed and returned
0.9.21. Root may install that tool under ignored `_cache/apparatus-toolchain`
using explicit `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`, without altering the project env.

## C-CI: original run reread, by actual item

The full five push-run job lists, failed-job logs and available deciding artifacts
were fetched from GitHub for the exact historical SHA. This is historical runner
evidence (`independently_reconciled`), not today's local replay. The inventory row
is not a complete or numerically accurate transcription of those logs: Contracts
has **six** failed test nodes; Docs Contract has **seven** link violations; the
frontend's three red files have at least two distinct immediate causes. The original
package-import JSON's complete `findings` list contains **243** records, not only
the four oversized subjects. Do not call all historical red "almost no product".

Counts below come from parsing complete JSON lists or every final `FAILED` line
of the corresponding named job, not sampled excerpts. Python source denominators
inside validators retain their own scope; CI jobs, finding records and test nodes
are different units and are never added into one total. Root's architecture lane
owns the current complete package-input analysis.

### Fast PR (`34196405835`)

| ID / actual item | Historical result and cause | Current route / falsifier |
| --- | --- | --- |
| CI-F01 Workflow governance | Success. | No repair from this observation; workflow edits require its current validator. |
| CI-F02 import exception expiry | 21 `import-exceptions` records in complete package-gate JSON. | Architecture owner adjudicates actual import exception validity; do not extend dates mechanically. Falsifier: same real gate against an expired still-used exception must remain red. |
| CI-F03 hidden coupling | 2 `import-boundary` records, runtime→quality and quality→runtime unregistered increase. Zero forbidden edges does not erase these findings. | Architecture owner; compare full edge sets with owned boundaries; no station excuse for a real edge. |
| CI-F04 dynamic import registration | 185 `dynamic-imports` records. | Architecture owner; complete scanner/registration reconciliation, no sampled registration patch. |
| CI-F05 import cycles | 3 `import-cycle` records. | Architecture owner; classify actual reachable cycle vs scanner artifact, then exact gate. |
| CI-F06 shim expiry | 13 `shim-expiry` records. | Architecture owner and shim owners; preserve actual expiry/strangle semantics. |
| CI-F07 architecture root | `architecture` contains Python but lacks non-product-root policy. | Architecture lane; tracked-file root census versus legitimate non-product role. |
| CI-F08 docs root | `docs` contains Python but lacks non-product-root policy. | Same owner/class as F07; do not strip evidence files to quiet the instrument. |
| CI-F09 vendor root | `vendor` lacks directory contract. | Compose existing vendoring with directory/import root policy; no removal of wheel capability. |
| CI-F10 absent production_data | Non-product-root policy points at absent `production_data` in clean CI. | Root station/census classification; an intentionally untracked data mount is not a required tracked source directory. |
| CI-F11 absent runs | Same check for absent `runs`. | Root station/census classification; independently exercise this root rather than assuming F10 covers it. |
| CI-F12 package root file | `src/polisyos/common/llm_json.py` unregistered root implementation. | Architecture/common owner; canonical owner or justified contract, never a catch-all baseline increase. |
| CI-F13 single-file shells | 4 `single-file-shell-package` records. | Architecture owner; retain complete identities in original JSON and adjudicate source structure. |
| CI-F14 builder size | `decision_packet/builder.py`: current 899, budget and limit 885. | Actual subject-to-metric mapping is established by JSON. Root module-size owner; no raw-line inference. |
| CI-F15 lifecycle size | `run_lifecycle.py`: current 3737, budget and limit 2050. | Same gate, separate subject. |
| CI-F16 advisor size | `advisor.py`: current 3559, budget and limit 3114. | Same gate, separate subject. |
| CI-F17 OpenAPI owner size | `openapi_contract.py`: current 4081, budget 2883, report-only limit 2866. | Same gate, separate subject; two different limits must not be conflated. |
| CI-F18 deep imports | 1 `deep-import` record. | Architecture owner; enumerate and bind edge identity. |
| CI-F19 scientist_docs | Path-aware docs coverage missing. | Docs/Scientist owners: source change impact note or correct published reference update; rerun exact historical range only when proving historical disposition. |
| CI-F20 foundry_docs | Coverage missing; original gate names 173 touched source files. | Foundry/docs owner; no generated-tools refresh can discharge subject documentation. |
| CI-F21 security_docs | Security/compliance coverage missing. | Security/docs owner; adjudicate actual changed semantics before declaring coverage. |
| CI-F22 security_runbooks | Runbook/rehearsal evidence missing. | Security/operations owner; separate consumer from F21. |
| CI-F23 generated tools reference | `polisyos-tools docs --check --output docs/reference/tools.md` reports drift. | DevX owner; regenerate from CLI owner then check, with a corrupted output negative. |
| CI-F24 ABI drift job | Skipped after prerequisites. | **UNRUN**, not green. Root's schema observability work must ensure actual execution. |
| CI-F25 Dependency review | Skipped. | No dependency-review verdict; inspect event conditions (push versus PR) before calling a defect. |
| CI-F26 aggregate Gate | Fails because its dependencies failed. | Derived result, not another product failure. Preserve skip/cancel distinctions. |

The eight module-size finding records are two checks for each of four subjects.
They are not eight oversized modules. Distribution checksum:
21+2+185+3+13+5+1+4+8+1 = 243 complete package-gate records. This is not a claim
that every record has the same policy severity; consult each summary's mode and
the exact checker when deciding repair.

### Standard PR (`34196405796`)

| ID / actual item | Historical result and cause | Current route / falsifier |
| --- | --- | --- |
| CI-S01 automated evidence capture | `atlasAutomatedEvidenceCapture.test.ts`: child raises missing jsonschema before persistence. | Dashboard lane's interpreter/provisioning seam; real child persistence/corruption negative. |
| CI-S02 readiness reconciliation | `atlasSurfaceReadinessReconciliation.test.ts`: canonical check executable provenance mismatch. | Dashboard lane: distinct immediate cause from S01; prove selected executable identity and no forged evidence admission. |
| CI-S03 workflow vocabulary test | `workflow.test.ts`: Python child missing jsonschema. | Same prerequisite class as S01, separate test observation; execute its source-flip negative. |
| CI-S04 frontend contract drift | Runtime OpenAPI snapshot differs, including confidence-ledger source/worker hashes. | Root runtime/schema lane. Generate twice in independent stations; distinguish current snapshot drift from changing generation input. |
| CI-S05 directory vendor | No top-level directory contract, plus corresponding coverage regression. | Architecture lane, compose existing vendor role. |
| CI-S06 trust fixtures | `src/features/trust/components/__fixtures__` unregistered fixture directory. | Architecture/dashboard role registry, preserving fixture-only status. |
| CI-S07 test fixtures | `src/test/fixtures` unregistered. | Separate directory admission, same class as S06. |
| CI-S08 subtree documentation | High-volume documentation 85.38 versus baseline 100; undocumented frontend subtree count 1 versus 0. | Architecture/docs owner; complete tracked subtree denominator, do not alter thresholds merely to restore green. |
| CI-S09 fixture count regression | Unregistered fixture count 2 versus 0. | Derived aggregate of S06/S07, not a new cause. |
| CI-S10 Frontend quality | Cancelled, no completed verdict. | Future hosted closure must run the declared job; this task routes its broader scope as not_established, with no inference from S01–S03 fixes. |
| CI-S11 Runtime HTTP | Cancelled, no completed verdict. | Future hosted execution required; this task runs only authorized named nodes, which cannot substitute for this job's full contract. |
| CI-S12 Integration | Skipped. | No verdict; follow actual dependency/event conditions. |
| CI-S13 Frontend smoke | Skipped. | No verdict, separate from successful component smoke. |
| CI-S14 component smoke | Success. | No repair from historical observation. |
| CI-S15 Performance | Success. | No repair from historical observation. |
| CI-S16 aggregate Gate | Failed dependency enforcement. | Derived, not a new defect. |

Directory artifact independently contains 3 direct findings and 4 regressions:
top-level coverage, high-volume coverage, undocumented frontend count, unregistered
fixture count. The table distinguishes underlying subjects from those aggregates.

### Core Runtime Release Gate (`34196405891`)

| ID / actual item | Historical result and cause | Current route / falsifier |
| --- | --- | --- |
| CI-R01 concrete CAS boundaries | `test_architecture_boundaries.py::test_runtime_never_imports_concrete_cas_write_implementation` failed on runtime constructors/imports. | Runtime/architecture owner; product boundary work routed, not an apparatus baseline relaxation. Exact test node is the falsifier. |
| CI-R02 registry singleton | `test_architecture_boundaries.py::test_runtime_control_paths_do_not_resolve_registry_singletons_inline` sees SourceProfileRegistry singleton in acquisition_executor. | Runtime owner; use injected canonical registry provider, retain exact negative test. |
| CI-R03 epoch example | `test_runtime_api_contract_hardening.py::test_epoch_batch_success_example_is_owner_derived_and_strict`: actual `stale`, expected `review_required`. | Runtime epoch/OpenAPI owner. Determine clock/fixture versus intended lifecycle semantics; never change status to satisfy a snapshot by assertion alone. |
| CI-R04 generated TS | `test_runtime_api_contract_hardening.py::test_openapi_typescript_output_matches_committed_shared_types` differs. | Root schema/runtime-client lane; same generated-surface class as S04, distinct executed test. |
| CI-R05 metrics override | `test_api_maturity.py::test_runtime_container_accepts_typed_test_overrides`: `_MetricsStub` lacks artifact_operations_total. | Runtime test collaborator seam. Current stub still exposes only ensure_initialized; production store reads counter. Route actual protocol adequacy, no product getattr fallback. |
| CI-R06 middleware metrics | `test_api_maturity.py::test_runtime_security_middlewares_receive_injected_metrics_provider`: same absent counter. | Same cause as R05, separate test node/consumer; preserve injection identity assertions. |
| CI-R07 ADR topic link | `docs/adr/by-topic.md:166` links unpublished/excluded ADR-048. | Docs publishing owner; determine exclusion versus actual page, then accuracy check. |
| CI-R08 ADR index link | `docs/adr/index.md:121`, same ADR-048. | Same target, separate broken link; regenerate owner indices if appropriate. |
| CI-R09 Atlas design link | `docs/brand/ATLAS_DESIGN_SYSTEM.md:14` links excluded ATLAS_SOURCE_OF_TRUTH. | Brand/docs publishing owner. |
| CI-R10 Atlas adoption link | `docs/brand/ATLAS_V4_ADOPTION.md:16`, same target. | Same target, separate link. |
| CI-R11 brand README link one | `docs/brand/README.md:7`, same target. | Same target, separate link. |
| CI-R12 brand README link two | `docs/brand/README.md:19`, same target. | Same target, separate link. |
| CI-R13 pipeline link | `docs/reference/index.md:35` points at unpublished policy-operations-research-pipeline.md. | Docs publisher and pipeline owner; distinguish internal research from published reference. |
| CI-R14 mutation subset | Exit 2: mutmut rejects --paths-to-mutate before mutation. | Apparatus repair candidate below; tests and mutation never ran. |
| CI-R15 Phase 1 report | Gate artifact identifies only `deep_copy:src/polisyos/scientist/methods/doe/uncertainty.py:985`. Reliability and required-test categories pass. | Scientist/calibration + gate owner. Current apply_calibrated_multiplier deep-copies a bundle before modifying nested intervals/warnings. Do not remove isolation to appease a substring scanner. |
| CI-R16 Typing and Ratchets | Cancelled. | **UNRUN**. Future hosted closure must execute it; its broader scope stays not_established and routed in this bounded task. |
| CI-R17 Phase 0 | Success. | No repair from historical observation. |
| CI-R18 Link Check | Success. | Distinct from publication-aware Docs Contract; local file reachability does not prove page publication. |
| CI-R19 Performance Smoke | Success. | No repair from historical observation. |
| CI-R20 Release Review Evidence | Skipped. | No review artifact verdict; depends on prior jobs. |

For R15 the property says no live deep copies on hot paths, while the implementation
searches for the literal `model_copy(deep=True)` across Scientist. A whitespace or
alias change escapes without removing work; a required defensive clone outside a
measured hot path is rejected without a performance measurement. This is P38, not
permission to mark the check green. Route to owner to either prove and optimize
the real quantity or explicitly bound the gate claim. Current product semantics
stay untouched by apparatus triage.

### Fabric Remediation (`34196405795`)

| ID / actual item | Historical result and cause | Current route / falsifier |
| --- | --- | --- |
| CI-B01 scanner-preserving config | `test_http_connector_base.py::test_connection_config_redaction_uses_shared_secret_pii_scanner`: expected secret marker absent. | Fabric/Core scanner boundary; actual redacted payload drops credentials. Exact test plus immutable mapping return witness. |
| CI-B02 credentials redaction | `test_protocol_compliance.py::TestConnectionConfig::test_redacted_hides_credentials`: actual mappingproxy({}), expected {'api_key':'***'}. | Same redaction boundary, but expected vocabulary must also be reconciled with scanner owner. Do not reverse actual and expected as the register does. |
| CI-B03 segments handlers | Broad-exception baseline includes additions in world/store/segments.py. | Fabric storage owner; classify each error handling boundary and preservation/rethrow semantics, no numerical baseline refresh alone. |
| CI-B04 snapshots handler | Same baseline class in world/store/snapshots.py. | Separate subject, same exact hygiene command and behavioral exception tests. |
| CI-B05 repeated race/leak smoke | Success. | No repair from historical observation. |
| CI-B06 performance smoke | Success. | No repair from historical observation. |

Full-suite historical summary is 2 failed, 1,644 passed, 1 skipped; the errors are
the two exact nodes above, not an open-ended product sweep. Baseline artifact says
expected 199, actual 203 broad-handler matches over its scanner denominator.
Current source trace: `PromptSanitizer.sanitize_payload` delegates keyed values to
`_sanitize_keyed_value`; `_is_sensitive_key` includes the `_credentials` suffix.
`ConnectionConfig.redacted` then preserves credentials only when that returned
value is a Mapping. Replacing a whole sensitive map with a placeholder can therefore
become `{}` at this consumer. This is the sharper causal hypothesis than an outer
dict/Mapping asymmetry; execute the actual scanner plus consumer before deciding
the repair. It warrants Fabric/Core owner work, not a source edit by apparatus triage.

### Canary Matrix (`34196405782`)

| ID / actual item | Historical result and cause | Current route / falsifier |
| --- | --- | --- |
| CI-C01 deterministic lane | One selected/executed lane, exit 1 before scorecard: artifact traceback is `ModuleNotFoundError: fastapi` importing local_production_canary→runtime.http.app→response_policies. | Apparatus provisioning defect. Current workflow still bypasses canonical setup, installs unpinned uv and JPEG headers, then runs with no extras. Fix at setup seam, both deterministic and live siblings. |
| CI-C02 live provider lane | Skipped on this push. | Intended event/credential quarantine, no product verdict. Do not invoke live external providers as an apparatus probe. |

No policy workload or scorecard was measured by C01. Its `bundle=none` is an
effect of failed imports, not evidence that a policy failed admissibility.
The artifact also identifies the selected canonical-production lane as
`ci_safe=false`. Missing data/actual policy limitations after provisioning are
separate outcomes, not permission to synthesize production data or weaken gates.

## Authorized execution design and boundary

The root selected the following design. Execution is sequenced after stage-1
commit/readback; only the root edits shared dependency/lock manifests.

1. Root: default dev→test edge and lock update, then cold prerequisite/ODS witness.
2. Root or assigned station lane: compose `.github/actions/setup-policy-engine-python`
   in both canary jobs and declare runtime-capable profile/extras; remove obsolete
   source-header provisioning. Bounded proof imports the real canary module and
   exercises its existing controlled matrix tests, not a live provider or full
   canonical-production run. Extra selection must follow real imports; `runtime`
   is minimum demonstrated need, not a claim that full research workloads need no
   research extra.
3. Mutation repair uses a **widened result protocol on the existing canonical runner**.
   Locked mutmut is 3.5.0; its actual source reads `[tool.mutmut]` or `setup.cfg`,
   ignores `mutmut.cfg`, and accepts mutant names plus `--max-children` on `run`.
   Its pytest configuration uses `pytest_add_cli_args` and
   `pytest_add_cli_args_test_selection`. Both release workflow and
   `tools/quality/testing/mutation.py` still call obsolete options. Do not pin
   an obsolete mutmut merely to revive removed flags, or change only the workflow.
   Extend the canonical runner to own scope and current configuration in an
   isolated scratch work directory, preserving other suites' target definitions.
   The work directory carries explicit selected source paths and test node paths;
   no global pyproject mutation or ambient mutmut.cfg selection can widen it.
   Invoke the current supported CLI and consume its machine-readable outcome plus
   source-bound mutation metadata; reconcile the complete actual mutant set to the
   declared source set and reject absent, stale, malformed or inconsistent results.
   A successful subprocess is necessary, never sufficient. Distinguish PASS (0),
   measured mutation-quality failure (1), and UNRUN/incomplete apparatus (2).
   Missing/zero mutants, setup/collection failures, unknown result statuses and
   unavailable result export are UNRUN; no-tests/skipped/interrupted/crashed mutants
   cannot be counted as killed. Survived mutants lower the measured score under the
   target's existing threshold. Before claiming closure prove at least one
   real selected source mutant is killed; enumerate mutated paths and selected
   tests; deliberate omitted target/zero mutants must fail, not return a false
   100% or success. The runner currently returns success for zero mutants and
   treats a failed survived-results command as "all killed"; these are the same
   result-admission class exposed one level deeper. P40 disposition is to widen
   this one protocol now, not leave it behind another per-flag patch.

The narrow executable proof fixture is a temporary package `sample_math` with
`adjust(value): return value + 1`, a single selected test asserting `adjust(2)==3`,
and a sibling source/test containing a deliberate tripwire. Invoke the production
runner against only `sample_math.py` and `tests/test_sample_math.py`; require a
positive, nonzero killed set and no sibling mutation/test execution. Mutate the
fixture to a constant-only no-mutable-function module to prove zero is UNRUN;
make the selected test fail before mutation to prove clean-baseline failure is
UNRUN; corrupt/remove its result artifact while leaving the process success
marker to prove result admission fails closed. Test lives under
`tests/repo_quality/tools/test_mutation.py`; existing importer/dispatch regression
is `tests/repo_quality/tools/test_phase4_consolidation.py::test_mutation_tool_scientist_all_aggregates_failures`.
No whole Foundry/Scientist/runtime mutation target is run in this task. Existing
product target definitions stay selectable; targets that cannot satisfy their
declared source/test paths return explicit UNRUN and are routed to their owner.

Canary bounded verification uses
`tests/repo_quality/tools/test_canary_matrix.py::test_local_canary_runner_accepts_profile_specific_matrix_args`,
`::test_real_canary_matrix_runs_deterministic_subset_and_writes_lane_summaries`,
`::test_real_canary_matrix_fails_lane_when_scorecard_fails`, and
`::test_live_provider_lane_requires_credentials_and_explicit_flag`, plus a real
fresh-interpreter import of `tools.ops_runners.runtime.local_production_canary`.
The matrix tests stub actual policy execution and are explicitly orchestration
proofs; they do not prove canonical-production policy success. The existing
workflow marker test alone is insufficient provisioning evidence.

**Route, preserve red**: actual runtime boundaries/status behavior, Fabric
redaction/exception semantics, Scientist deep-copy quantity, and documentation
publication coverage. Their owners and falsifiers are individually named above.
Root owns architecture/freshness/schema repair and current complete gate census;
dashboard owner handles its interpreter, assertion and evidence rows. This lane
does not edit their mechanisms or refresh governed baselines.

Closeout of the aggregate registered row still additionally requires a later push
whose failing set is a subset of the original, and actual execution of the cancelled
jobs. No push is authorized here. A local apparatus repair can therefore be delivered
with this explicit residual; it cannot honestly close that aggregate CI row.
No full CI job, directory test suite or whole mutation target is authorized by this
task. References to subsequent execution of cancelled jobs are future hosted
closure requirements, not instructions to run their broad scopes locally now.

## Per-row apparatus classification

| Finding scope | Classification before repair | Classification and remaining evidence |
| --- | --- | --- |
| C-ODF original row | Wrong supply source / station trust posture: core install depended on a noncanonical host; the ingestion check itself could run. | Current source already repaired by vendoring; byte integrity reverified, cold install + ODS consumer still required. |
| C-STATION-1 fresh pytest | Check never ran: default dependency selection does not provide configured pytest prerequisites; ambient executable can make the wrong station appear involved too. | Default owner wiring plus new-environment import and ordinary pytest positive/removal negative. |
| C-STATION-2 offline JAX | Check never ran: cache availability failure; `.pth` borrowing, if used, changes it into wrong-station evidence. | Online locked provisioning or explicitly complete offline set; provenance of the particular reported workaround remains not_established. |
| C-CI parent | Mixed row, deliberately decomposed above; no single station verdict applies. | CI-F/S/R/B/C IDs retain separate measured, UNRUN and wrong-station causes. |
| CI-S01 / CI-S03 Python child | Wrong station: venv dependency installed, consuming child cannot import it. | Dashboard interpreter-selection repair and PATH poison. |
| CI-S02 Node provenance | Wrong station/fixture producer: child executable fails canonical provenance. | Dashboard canonical fixture producer, unchanged fail-closed admission. |
| CI-R14 mutation | Check never ran: CLI rejected selection; deeper old outcome parser could also claim green without a measured set. | Canonical 3.5 config plus source-bound complete results and explicit UNRUN. |
| CI-C01 canary | Check never ran: runtime import failed before workload/scorecard. | Canonical environment profile; real module import; later product outcome remains distinct. |
| CI-F24/F25, S10–S13, R16/R20, C02 | Check never completed or was not selected (skipped/cancelled), as individually recorded. | Actual subsequent execution or reasoned event exclusion; no green inferred. |
| Remaining measured CI-F/S/R/B items | Checks did run; actual source/contract/docs failures or successful checks, individually routed. | Neither omission nor wrong-station label is supported merely because the failure is inconvenient. Current verdict requires current replay. |

## Raw receipts and reproducibility

Raw prefix: `docs/superpowers/journals/apparatus/station/raw/`; files are ignored.
Each CI fetch used `gh run view <id> --json jobs,event,headSha,url` and
`gh run view <id> --log-failed`; all five log fetches returned 0. GitHub artifact
downloads use the named run and artifact. These are complete evidence outputs,
not source snapshots. Historical log prefix removal means splitting each line at
the first two tabs and stripping only its ISO timestamp; parse the package JSON
from its first complete object and every `findings` member. Job tables derive from
every `jobs` member, not only failed jobs.

| Receipt | SHA256 |
| --- | --- |
| run-34196405835-failed.log | 99dd7bc49d279360707078bda1b56687fbd03e5bdbe50effe698fddf59fafaf7 |
| run-34196405796-failed.log | 94862b105452a4e721505b10e28eb3e2abef51447b8971aecc9fbb5c351932f3 |
| run-34196405891-failed.log | c30af0cd63955a928592daf71e9c1be3a33f600a766ea9479d4fb92b9bc15643 |
| run-34196405795-failed.log | 35a2f498b14598b06a514c306edfc0c8d05a42e4060676eff794115c49940752 |
| run-34196405782-failed.log | 9ad3127204462742f8079d03ead5ace4b119703d5d39f6abdddada6d2a414163 |
| phase1-artifact/scientist-phase1-gate.json | f3f47bda010c281f91f257e09d5977f3b43992767e0b334aeeb12a74c21d5b28 |
| economics-artifact/last-mile/directory-health.json | b61abea4f6c841b2e62575909093e08a115e54cee1914f6af0e06505f7b3533d |
| canary-artifact/_build/.tmp/production-quality/canary_matrix_result.json | 84f8ba562f33e130670ca2be84b575d238297fe350c48215cbbc77bb8aa7224a |
| odf-provenance.json | b365b24bf3b312016d060d387ce602b371a73461106f1cfef9e71b41296cd43e |
| baseline-default-prerequisites.log | 1262b90bca6bfb8a6f835a0abf575bd9c70034f8eaf081ca07fad266807049db |
| odf-hash-probe/sync-original.log | ec982f933d3002fa84a396ac12502d6ee4eaed9815cfc00a03cb4300c5582504 |
| odf-hash-probe/sync-modified.log | 304273e6943c3019c7752bdc6cfda1d4d8bb9e7f8950c06a7d0e4f10c26fd139 |
| odf-hash-probe/modification.json | 4a3158567a1e3f29558e1e643942b349d28fb6b03ee890c72d9cd3c9396beab2 |

No broad directory tests, backend verification, CI-parity or production canary was
run by this lane. Current runtime/Fabric nodes remain **not yet replayed** here.
No source, test, config, dependency or lockfile changes were made by this lane.

## Stage 2 decision addendum: native mutation station limitation

CI-R14's obsolete CLI and unmeasured-result admission defects are repaired on the
existing canonical owner. Execution research exposed a **NEW native station class**:
mutmut 3.5.0 unconditionally calls `setproctitle` in the child immediately after
`os.fork()`. On the measured CPython 3.14.3 / Darwin 25.6.0 / arm64 station with
setproctitle 1.3.7, that call intermittently segfaults inside CoreFoundation /
LaunchServices before pytest executes the mutant. A parent initialization attempt
passed once and then failed again: **same class one level deeper**, so P40 stops
that repair ladder. The ineffective initialization is removed. Neither engine
monkeypatching nor accepting native crashes as killed mutants is admissible.

The supported-option investigation inspected the pinned engine's entire
`__main__.py` and `__init__.py`, and its `run --help`: there is no process-title
suppression option. The upstream [Darwin process-title implementation](https://github.com/dvarrazzo/py-setproctitle/blob/master/src/darwin_set_process_name.c)
reinitializes LaunchServices for every call; initializing it in the parent does
not remove that child operation. Docker CLI is present but its daemon is
unavailable. The smallest absent closure capability is a supported Linux execution
station (or an upstream fork-safe process-title implementation, which is absent
from the pinned engine environment).

**Decision:** before staging or launching mutmut, the canonical runner rejects
`sys.implementation.name == 'cpython'`, Python major/minor `3.14`,
`sys.platform == 'darwin'`, and `platform.machine() == 'arm64'` with a persisted
`unrun` receipt and exit 2. This is a conservative support boundary around the
measured patch-level station, not a claim that every patch has reproduced the
fault. The diagnostic names the unsupported station and requires a supported
Linux station. Other platforms retain complete outcome reconciliation, so an
unanticipated failed native run still cannot become green. The guard has no
bypass option. Native support may be reconsidered only after replaying the tiny
real-mutant fixture on the changed station.

This support decision affects all three canonical mutation target families on
that station, without changing their source selections, test selections or score
floors. Hosted Linux Foundry, Scientist and core-runtime lanes remain eligible for
actual measurement. It changes no dependency, lock, canary, freshness, schema,
dashboard or product semantics. CI-R14 remains `verification_missing` for real
repeatable mutation execution locally; CLI and admission repairs can be delivered
without claiming that the mutation row or parent CI aggregate is closed.

The native falsifier used the identical absolute tiny-positive pytest invocation
from repository and product CWDs. Before this decision, the first underlying
producer returned UNRUN (-11), while the second returned PASS (2/2 killed).
Both outer tests exited zero because they explicitly checked the declared native
residual; **that outer exit is not evidence of mutation completeness**. Final
verification replaces this probabilistic allowance with a strict preflight
UNRUN assertion and runs the same runner invocation from both CWDs, expecting
exit 2 and the same station verdict before any fork. Non-Darwin real-positive
verification continues to require actual killed mutants. Protocol-admission
unit fixtures are explicitly controlled outcomes, never reported as real mutation
execution; each corrupt-result probe first admits its uncorrupted controlled
fixture. The real baseline-failure and zero-mutant producer traces remain retained.

All following receipts are under `docs/superpowers/journals/apparatus/station/raw/`:

| Receipt | SHA256 | Meaning |
| --- | --- | --- |
| mutation-native-platform.log | f4c1aa6faa15576a197685f334feab487c022dd75e2dc1d13b8ccdd3fcbe023b | Exact measured platform and package versions |
| mutation-faulthandler.log | eab724f0c83cad80f0b006bf5e59537f5e80e759782cd3fae2b8101066164d1d | Native post-fork crash before pytest |
| mutation-run-help.log | 5c9c8de9deeac8a4162c594addd9cb379a09ce6c641c7cfac9a5c66d3661d383 | Supported CLI options |
| mutation-title-options.log | bceb4914e52c25eabfbb8edd177522fdd87317cd63d5b286d943245bb83a1623 | Pinned engine callsite and option search |
| mutation-root-cwd.log | 0c2f7aa9eab5d55680c5f16f1a199e8b19027561ffec5669b6db30f4e0a6717c | Underlying UNRUN, outer test exit 0, 1.66 s |
| mutation-product-cwd.log | e7abd94a3d0571445e323e409fd96f4852dbeea604f6382f1ac0fb3f1c8e4a60 | Underlying measured PASS, outer test exit 0, 1.53 s |
