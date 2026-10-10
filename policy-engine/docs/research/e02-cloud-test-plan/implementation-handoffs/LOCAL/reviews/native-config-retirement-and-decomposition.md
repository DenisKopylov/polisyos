# Independent review: native config retirement and Scientist decompositions

## Verdict and boundary

**Partial.** The evidence supports retiring exactly the three named test-ratchet mirror-exception tuples and the zero-current-debt `errors` name-backlog row. It does not support clearing the remaining ratchet regressions. The seven Scientist source decompositions are structurally bounded in the current source snapshot, and a fresh scoped C901 run passes across all 32 implementation modules. However, the current complexity registry still contains seven expired exceptions whose source predicates are now below the declared cap. Those exact rows are eligible for retirement but have not been retired in the inspected workspace.

Target: the supplied candidate workspace at `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`; review is of the file bytes listed below, not an independently Git-confirmed HEAD. I did not run Git or tests and did not edit source, tests, configuration, generated artifacts, or source history. The no-test/no-Git restriction prevents a bytewise comparison to the named `4699` base for `name_registry.toml`; the exact limit is recorded below. This is not G code acceptance, integration publication, or formal finding adjudication.

## Ratchet exception retirement

Current `policy-engine/architecture/tests/ratchets.toml` is SHA-256 `88a9a3595f82e7456fd483140aadcc1ef051dfc05b4375dfef1db87381f27792`. The deciding full report is `LOCAL/raw/retired-zero-debt-rows/ratchets-current-retired.stdout` (113,069 bytes; SHA-256 `131818b95dd10a00dcbb30711744b28f48be23e74cf7eda8df5f03573deab43c`). I parsed the output directly: 13 package rows sum to 2,400 current source modules. Its summary remains 5 loose-floor regressions, 2 strict-mirror regressions, 0 property-count regressions, and 3 helper-topology count regressions; the report exits 1.

The observed current predicates justify only these three removed exception tuples:

| Removed tuple | Current measure | Unrelated status retained |
|---|---:|---|
| `fabric.strict_mirror_regression_exception` | 0.0734 vs 0.0717 strict baseline | Fabric loose mirror still regresses: 0.5019 vs 0.5020 and its loose exception remains. |
| `ir.mirror_regression_exception` | 0.6092 vs 0.6012 loose floor | IR remains `below_first_target_tracking` against its separate 0.70 first target. |
| `lex.strict_mirror_regression_exception` | 0.2750 vs 0.2059 strict baseline | Lex's package-level `explicit_exception` remains unchanged. |

The Scientist strict exception remains correctly present: 0.4004 is below its 0.4120 baseline. Scientist's loose ratio is 0.6762 vs 0.7099 and remains an unexcepted floor regression. Foundry's loose and strict rows and Runtime's loose row remain because their measured predicates still require them.

I independently parsed the three retained one-tuple counterfactual TOMLs. Relative to the current contract, each control adds exactly that package's five-field exception tuple; there are no root/header differences, other package differences, or changed fields. The restored tuple expiries remain their old `2026-06-15` values. `current-source-control-manifest.json` (SHA-256 `6285f7a4e381af1c8cbcc8a41639b309c15d07c565528e8b134093c93f8e5f2b`) records that each restored-tuple report has the same full report payload after excluding only contract path and timestamp. The current contract hash matches the positive report's pinned hash. This supports removing those tuples, not renewing or shifting any expiry.

The current reporter test is not green: `retired-zero-debt-rows.md` records 3 passed / 1 failed because `test_phase_6_2_reporter_renders_package_mirror_and_property_summary` expects zero floor regressions while the full current report has five. The author explicitly leaves that failure unclassified; this review also does not call it inherited or resolved. Historical and current counts differ, so no old baseline is used to erase it.

## `errors` name-backlog retirement

Current `policy-engine/architecture/name_registry.toml` is SHA-256 `ea985c079e393ca7fb98a89464dc3bbacff17ac453124e0ef18c89408707d842`. It retains version 1 and fail-closed unregistered-collision defaults. There is no `errors` `rename_backlog` row; the separate `shared_name` entry remains limited to `core` and says fixture directories named `errors` require backlog coverage rather than becoming package namespaces.

Direct current-tree checks found both `data_forge/domains/catalog/fixtures/academic/errors` and the proposed `academic_error_cases` path absent. A scoped search over `policy-engine/src` and `policy-engine/tests` for the old module/path and replacement forms had no matches. I parsed the complete saved Phase 0 inventory: 52 repeated-directory-name rows and zero `errors` rows. Its full output remains 55,101 bytes at SHA-256 `55328377d8cfed33c5e5af0dc35c6d01460958a24c397f24d955711a360d6558`; the post-change manifest says it is byte-identical to the pre-change inventory. The actual fail-closed name gate output is `{"findings": [], "mode": "fail-closed"}` (46 bytes; SHA-256 `e26fdcc8bf34499fef3a20dd662a02eb3fd886e66a6495477df2353de00ef426`). The recorded five-test name-registry suite includes a negative unregistered-collision fixture for a new repeated directory name and passed.

These controls support retirement of the `errors` backlog row. They do not establish the whole-file byte delta from `4699`: I found no saved pre-retirement `name_registry.toml` bytes or hash in the supplied controls, and this review was prohibited from using Git. Thus the current row-level property is supported, but the requested exact base-to-current delta remains **not_established** for this file. The same limitation applies to an exact whole-file comparison of `ratchets.toml` against `4699`; the current-vs-one-row-restored controls establish the authorized retirement shape, not every intervening base delta.

## Scientist structural decomposition review

The six independent decision packets describe seven original canonical Scientist modules: Blueprint, Distributional, Normative Arbitration, Governance, Policy Runtime Support, Transportability, and Welfare. The Governance packet covers its two original nodes. The full current helper footprint inspected here contains 32 Python implementation/bridge modules, listed with exact current line count and SHA-256 below. Counts use the repository's stated logical rule: nonblank lines excluding comment-only lines. All 32 are below `complexity_exceptions.default_max_module_lines = 1000`; the largest is `welfare_covariance.py` at 990 logical lines.

| Current implementation path (relative to `policy-engine/`) | Logical lines | SHA-256 |
|---|---:|---|
| `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py` | 590 | `a737d7056956730665c6f7eedd258bb427e12b09a847746138d65d40d9173a81` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_engine.py` | 370 | `15f508608cbb931226d24efb111c2e325ed1a83d4cef1ae6cf492f74beea66ff` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_strategy.py` | 146 | `cd11f2fd0542c14821aee9ad41224f79618d04a3aef559d039c283647f6fc1c6` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_benchmarks.py` | 666 | `202fd486a09a610fcd681af45c2b24f43a511d9bdf5767e7256aa53899508ff2` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_reporting.py` | 688 | `68877a5dc66ddbf8a59644eb72377ea34091243dbdd708da64aff6298848c883` |
| `src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py` | 588 | `6a78396de9fbaaf152a998f3dcbfa528e8acf7a4f81f849069680166346c5598` |
| `src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_ordinal.py` | 296 | `89ca3fcd8368736e54f00ded2a1b454ad1bd5d0d34a913c86358a1c7502365c1` |
| `src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_justification.py` | 686 | `449970c269d7457fd13ef7ab85b9b32bf18848fecd5dfa871bec1a3ec4caa11d` |
| `src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_bounds.py` | 514 | `e19bab487de4bc1f1b2e10369997dc8498c1b7af9197c2634de584386d420c6d` |
| `src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_artifacts.py` | 335 | `20eba50c64248977e4e110e7faf6032544afadc4790db6ef8be062b7d8d1e4d7` |
| `src/polisyos/scientist/nodes/builtins/simulate/distributional_analysis_subgroups.py` | 129 | `fbb9b5423b3e3e38a195678e218de8d1dbb33d3ab59404429c504b03b44147c0` |
| `src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py` | 583 | `ec9cd1b370943f564875e91ea2c62058b06e88615699ad6533d1922039a7e9ea` |
| `src/polisyos/scientist/nodes/builtins/governance/normative_arbitration_calculations.py` | 618 | `d168ec331b803fc2ce01bc089e1ece4adfb9b9647c459accb3a6480fb021b623` |
| `src/polisyos/scientist/nodes/builtins/governance/run_governance.py` | 930 | `f0632804853a0c00747fec319b67021f635c21e5f485cea53eb2269be5efcfd9` |
| `src/polisyos/scientist/nodes/builtins/governance/governance_gate_requests.py` | 404 | `14fab09e4e63427db8a6a06032d44f00952fa32eda5e13200d2a1c9ce852fbc7` |
| `src/polisyos/scientist/governance/passes/_artifact_resolution.py` | 152 | `c7241dd0e6333c03aaa4d102e961e11ca586db5346670bc44e778a234be6941c` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py` | 946 | `c97671fbd57c8b410fb8a352b294db62265bf3fd513abf93abc8c5c5ffe4a992` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_artifacts.py` | 701 | `c0f2d7d85f171d6ff24158f6b9fc676e133c54093460e722ed3d36b8c319b113` |
| `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_metrics.py` | 400 | `0de6efcb9de46c2938b0bbe7d6e87274236c903285ff180440ea64b3e74bf164` |
| `src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py` | 982 | `4696f3c37f1edb287527776d1579fd98ae0d94b8d4d513c9571328bf1e0d51cc` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_inputs.py` | 356 | `0d9601de272f6067b2384111fb09d783d8cbfffa46500ed2bd0dba21ee717703` |
| `src/polisyos/scientist/nodes/builtins/causal/transport_resolution_results.py` | 537 | `c607b069be5fcd8d537e7ce53a92e3321ccaa1904007581a40276a81b8074cfa` |
| `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` | 64 | `993a434317e54b6db23626ba56e60e0973312fe960e57cc2c2cc76cdae981c7f` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_context.py` | 762 | `67b8d609fe101e9b13756b651af03bb0740940e7415a6913b3f30c11581b116a` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_covariance.py` | 990 | `c5cb907b8312b52f0504cbacf3e2a38e147909a0acf8db6d04ac741607bc2d65` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_draws.py` | 692 | `99d2adc8509354890a92de6380e23b973966f141f5a2b7a68f3fa2e8f2f09d38` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_ge.py` | 715 | `ad740b6579a91b76ff005b3c2bbecd7a1f84d4827298627ec08f5aae84f41cea` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_node.py` | 473 | `b321051e25133161b0d504366cbdc0cb55391778430b1a685e1a46329ef698bf` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_propagation.py` | 750 | `3633130f341dea915e1876ca1e148c7e26cd0ab34811d4fed870c240686a24bb` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_reports.py` | 644 | `5040ee6a1192a88551ff6efc83944cb8b5e2f44fe508e9368a85ed11ac8d3807` |
| `src/polisyos/scientist/nodes/builtins/simulate/welfare_types.py` | 319 | `80c7724be00d61bb2202d322b70d0bc2d525ce7d23328e9bf1bc0557af1a00a8` |
| `src/polisyos/foundry/uncertainty/evaluation_failures.py` | 114 | `a371c4e8ad6ca37d3d94bb69fefad541c442fcec233c2a7305ea689fffca9050` |

Current source inspection confirms the public node facades still define their canonical classes and `spec`/`execute` entry points in the original modules. Blueprint keeps `_PolicyRuntimeWorkflowEngine` there and re-exports the private helper names needed by current callers; Distributional keeps `RunDistributionalAnalysisNode` and re-exports its private helpers, including the canonical `StateSnapshotRef` resolution seam; Normative Arbitration and Governance keep their node classes and `RunGovernanceNode.bind`; Policy Runtime Support retains its typed backend/artifact classes, `__all__`, and promotion entry point; Transport retains `ResolutionState`, `TransportabilityResolutionLoop`, and `RunTransportabilityNode` with their facade signatures; Welfare retains `WelfareSampleDomainError` and `PropagateWelfareNode`. The independent packets record consumer/FQN/signature characterization and their focused behavioral receipts; this review did not rerun those tests.

Fresh focused static check, from `policy-engine/`, ran Ruff 0.14.10 over the complete 32-file implementation denominator with `--select C901` and `lint.mccabe.max-complexity=12` (no cache). Exact result: exit 0, stdout `All checks passed!`. The command uses `ruff.toml` and explicitly selects every path in the table above. This directly covers current WIP source, including the current Blueprint reporting helper.

### Stale complexity exceptions

Current `policy-engine/architecture/exceptions/complexity.toml` is SHA-256 `497475749708681b72f94c4d72e6539fb845778d94865628407f91e8b8e7b7bb`. It still contains these seven rows, all with expiry `2026-08-15`, owner `team-scientist`, and old remediation text claiming extraction remains pending:

| Registered path | Registered `lines` | Current logical lines |
|---|---:|---:|
| `simulate/propagate_welfare.py` | 2,733 | 64 |
| `simulate/run_distributional_analysis.py` | 2,367 | 588 |
| `decide/run_policy_blueprint_runtime.py` | 2,173 | 590 |
| `causal/resolve_transport.py` | 1,531 | 982 |
| `decide/policy_runtime_support.py` | 1,478 | 946 |
| `governance/run_normative_arbitration.py` | 1,075 | 583 |
| `governance/run_governance.py` | 1,068 | 930 |

**MEDIUM finding — stale exception ledger.** These are not justified default-only cases now: the current measured module-size predicate is under 1,000 for every registered path, and a fresh C901-12 run passes the complete extracted helper/bridge denominator. Keep the cap and threshold unchanged; retire exactly these seven stale rows, without changing expiry dates, creating new exceptions for helpers, or treating the source-size result as a behavior/capability closure. This is the same zero-current-debt exception class addressed in the ratchet cleanup, widened here to the complete seven-row Scientist decomposition set (P40). The old `dx0-native/native-row-disposition-2026-10-09.md` statement that these seven remain real current size debt is historical to its earlier source snapshot and must not be presented as current after this source composition.

### Current-source delta that needs a later freeze review

The Blueprint decomposition note reports `policy_blueprint_runtime_reporting.py` at 537 lines. Current bytes are 729 physical / 688 logical lines, SHA-256 `68877a5dc66ddbf8a59644eb72377ea34091243dbdd708da64aff6298848c883`, and include additional projection/refusal helpers. This remains below the 1,000 logical-line cap and the current full C901 check passes. The six original decision packets do not bind this current file hash or establish the semantics of this later addition; I have not reviewed those active semantic changes. The current source README now describes the projection validation/refusal behavior. The complete source freeze therefore needs a separate review and current behavioral receipt for that delta before treating the old Blueprint packet as acceptance of these bytes.

## Evidence paths and limits

- Retired-row report: `LOCAL/dx0-native/retired-zero-debt-rows.md` @ `c5e39d3db84bc9596fbacc4d5e16cc69bcd9b5bee88400fd31760ccf044b6929`.
- Ratchet counterfactual manifest: `LOCAL/raw/retired-zero-debt-rows/current-source-control-manifest.json` @ `6285f7a4e381af1c8cbcc8a41639b309c15d07c565528e8b134093c93f8e5f2b`.
- Name/Phase 0 post-change manifest: `LOCAL/raw/retired-zero-debt-rows/postchange-manifest.json` @ `8cbb0f381aa2b2ed35b886a9281719e1e19a8c4bec80fcac8bfb88ad9e2ab1f7`.
- Current configuration hashes are given above; the current package reports and full directory inventory are retained under `LOCAL/raw/retired-zero-debt-rows/`.
- The six independent decomposition notes are `LOCAL/decisions/{blueprint,distributional,governance,policy-support,transport,welfare}-native-decomposition-9e02.md`; their current hashes respectively are `e8dd9371fd7ce457f005940ad8125e16d899a89f66a1df5a015a7d8da5bfc54c`, `8bd4c3d54c914498f8e7fed6a7e1022547ec562a818f9a44606d3188c6102f47`, `ab767b047d76f5712e8f9359919bfb9a7c9eae2024d4635266eee69e347b14c1`, `9f8ffa06798c1a514423b6cf71008a6448bbf57e25cba00716fc4fc0b54cd506`, `cde64369f3f749271d410ff12e73be500ea5106b37487226072c0a7d780d728f`, and `8731a47bed9ca3104331d01f4efeb2c33ac345a1224d806b93782617b0f28f10`.

No formal G closure, source freeze, installed/native runtime result, or full native SOTA green is claimed. The complete ratchet report still has active regressions, the ratchet contract test has a documented failure, and the exact whole-file `name_registry.toml` diff against `4699` remains unestablished under this read-only/no-Git review.
