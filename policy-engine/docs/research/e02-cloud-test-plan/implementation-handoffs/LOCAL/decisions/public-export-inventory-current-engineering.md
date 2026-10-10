# Current public-export inventory: source-engineering assessment

**Disposition:** research only; no runtime/source, generated artifact, or public-contract edits. The current inventory remains fail-closed and incomplete. This note does not certify any package or close the public-surface gate.

## Question and finding

The current static resolver is not overlooking one harmless grammar token. It walks the entire declared set of 20 package policies and 38 supported entrypoints. Its present result and the checked-in generated inventory agree: all 38 are unresolved, with `export_count = null`, `known_export_count = 0`, and scope text explicitly saying this does not mean an empty runtime namespace. The bounded resolver preserves declared candidate names separately from proven exports.

A read-only prototype admitted only an unaliased `from __future__ import <known feature>` as a no-effect compiler directive, using `__future__.all_feature_names`. The positive directive control was admitted; controls for external `import pathlib`, computed `__all__ = build_exports()`, and an unknown future feature remained refused. Across the complete set, that extension moved the first refusal deeper but changed **0 of 38** entrypoints to complete. Prototype refusal classes were: 27 import effects, 3 external `ImportFrom` effects, 5 class-body effects, 1 unsupported export expression, 1 conditional/mutated `__all__`, and 1 subscript effect. The next blockers are real owner-resolution and runtime-dispatch semantics, not simply syntax spelling.

This is the **same export-closure class, one level deeper** under P40. The first observed blocker is effect auditing (including a harmless compiler directive); after the bounded extension, the second finding is transitive/lazy source behavior. Do not repair these as a sequence of one-module exceptions. The bounded residual is explicit: the static inventory does not establish the runtime exports of these 38 entrypoints.

## Complete declared denominator

Path denominator: `architecture/public_surface/contract.toml`'s complete `[[package]]` set and each policy's complete `supported_entrypoints` list. File-type denominator: TOML package-policy records and Python facade/source inputs; all source paths read by the probe have SHA-256s in the raw report. The contract contains **20 package policies / 38 supported entrypoints**. The report's current-builder result contains **20 packages / 38 rows / 0 complete / 38 unresolved**; the prototype contains the same denominator and outcome. The checked-in JSON inventory contains **20 packages / 38 entrypoints / 38 unresolved**. A read-only equality probe found no per-entrypoint differences in status, counts, or first unresolved reason between the current builder snapshot and the checked-in JSON.

| Declared package policy | Complete supported-entrypoint list | Classification | Facade mode |
|---|---|---|---|
| `polisyos.common` | `polisyos.common`, `polisyos.common.config` | public_stable | lazy_facade |
| `polisyos.core` | `polisyos.core`, `polisyos.core.contracts`, `polisyos.core.observability`, `polisyos.core.security`, `polisyos.core.trace` | public_stable | lazy_facade |
| `polisyos.ir` | `polisyos.ir`, `polisyos.ir.analytics`, `polisyos.ir.api` | public_stable | lazy_facade |
| `polisyos.obligation_rules` | `polisyos.obligation_rules` | internal | eager_exports |
| `polisyos.obligation_graph` | `polisyos.obligation_graph` | internal | eager_exports |
| `polisyos.method_requirement` | `polisyos.method_requirement` | internal | eager_exports |
| `polisyos.participation_requirement` | `polisyos.participation_requirement` | internal | eager_exports |
| `polisyos.fabric` | `polisyos.fabric`, `polisyos.fabric.api`, `polisyos.fabric.world` | public_stable | lazy_facade |
| `polisyos.foundry` | `polisyos.foundry`, `polisyos.foundry.api`, `polisyos.foundry.compile`, `polisyos.foundry.execute`, `polisyos.foundry.uncertainty` | public_stable | lazy_facade |
| `polisyos.scientist` | `polisyos.scientist`, `polisyos.scientist.governance.continuous`, `polisyos.scientist.methods.research_dag`, `polisyos.scientist.replay` | public_stable | lazy_facade |
| `polisyos.evidence` | `polisyos.evidence` | internal | eager_exports |
| `polisyos.runtime` | `polisyos.runtime` | public_stable | lazy_facade |
| `polisyos.runtime.quality` | `polisyos.runtime.quality` | public_experimental | eager_exports |
| `polisyos.lex` | `polisyos.lex`, `polisyos.lex.knowledge` | public_stable | lazy_facade |
| `polisyos.scholar` | `polisyos.scholar` | public_experimental | lazy_facade |
| `polisyos.data_forge` | `polisyos.data_forge`, `polisyos.data_forge.read_api` | public_experimental | lazy_facade |
| `polisyos.berl` | `polisyos.berl` | public_experimental | eager_exports |
| `polisyos.calibration` | `polisyos.calibration` | public_experimental | eager_exports |
| `polisyos.ddm` | `polisyos.ddm` | internal | lazy_facade |
| `polisyos.foundry.agent_sim.world` | `polisyos.foundry.agent_sim.world` | public_experimental | eager_exports |

## Every current unresolved entrypoint

The `__all__` source locator, candidate count, source-expression AST hash, exact first refusal reason, and SHA-256 of every facade/refusal source are preserved in the raw report. Candidate counts below are the resolver's source-declaration candidates before effect audit; they are **not** runtime export counts.

| Policy | Entrypoint | Facade `__all__` source declaration | Declared candidate count | Current first refusal |
|---|---|---|---:|---|
| `polisyos.common` | `polisyos.common` | `src/polisyos/common/__init__.py:29`; AST `7b9fc431078e…` | 7 | `from __future__ import annotations` at `src/polisyos/common/__init__.py` |
| `polisyos.common` | `polisyos.common.config` | `src/polisyos/common/config.py:408`; AST `ae8dfc44b8a9…` | 8 | `from __future__ import annotations` at `src/polisyos/common/__init__.py` |
| `polisyos.core` | `polisyos.core` | `src/polisyos/core/__init__.py:180`; AST `ac7a9f4a8a49…` | 134 | `from __future__ import annotations` at `src/polisyos/core/__init__.py` |
| `polisyos.core` | `polisyos.core.contracts` | `src/polisyos/core/contracts/__init__.py:1421`; AST `61f2169b55c8…` | 0 | unsupported `__all__` expression; facade declaration line 1421, AST SHA `61f2169b55c8615d4d77ab860fe55d2f2deac447bd1cc9456c0e76a3f1434604` (full expression in source-hash-bound raw report) |
| `polisyos.core` | `polisyos.core.observability` | `src/polisyos/core/observability/__init__.py:675`; AST `c1953b41737d…` | 25 | `from __future__ import annotations` at `src/polisyos/core/__init__.py` |
| `polisyos.core` | `polisyos.core.security` | `src/polisyos/core/security/__init__.py:409`; AST `0cf9340ff9ec…` | 106 | `from __future__ import annotations` at `src/polisyos/core/__init__.py` |
| `polisyos.core` | `polisyos.core.trace` | `src/polisyos/core/trace/__init__.py:6`; AST `17ce862f298c…` | 5 | `from __future__ import annotations` at `src/polisyos/core/__init__.py` |
| `polisyos.ir` | `polisyos.ir` | `src/polisyos/ir/__init__.py:23`; AST `8b16eb23fa71…` | 292 | `from __future__ import annotations` at `src/polisyos/ir/__init__.py` |
| `polisyos.ir` | `polisyos.ir.analytics` | `src/polisyos/ir/analytics/__init__.py:17`; AST `c5209dc447ba…` | 284 | `from __future__ import annotations` at `src/polisyos/ir/__init__.py` |
| `polisyos.ir` | `polisyos.ir.api` | `src/polisyos/ir/api.py:1306`; AST `a8cf7a7c2494…` | 11 | `from __future__ import annotations` at `src/polisyos/ir/__init__.py` |
| `polisyos.obligation_rules` | `polisyos.obligation_rules` | `src/polisyos/obligation_rules/__init__.py:28`; AST `1b90fa356c92…` | 22 | ClassDef ObligationRule at `src/polisyos/obligation_rules/catalog.py:143` |
| `polisyos.obligation_graph` | `polisyos.obligation_graph` | `src/polisyos/obligation_graph/__init__.py:37`; AST `94b9d17c54d6…` | 20 | `from __future__ import annotations` at `src/polisyos/obligation_graph/__init__.py` |
| `polisyos.method_requirement` | `polisyos.method_requirement` | `src/polisyos/method_requirement/__init__.py:22`; AST `0b537320c2de…` | 14 | ClassDef MethodValidityRequirementCompiler at `src/polisyos/method_requirement/_impl/compiler.py:26` |
| `polisyos.participation_requirement` | `polisyos.participation_requirement` | `src/polisyos/participation_requirement/__init__.py:1302`; AST `a7e09ddb69a1…` | 23 | `from __future__ import annotations` at `src/polisyos/participation_requirement/__init__.py` |
| `polisyos.fabric` | `polisyos.fabric` | `src/polisyos/fabric/__init__.py:18`; AST `0d4a22243448…` | 41 | `from __future__ import annotations` at `src/polisyos/fabric/__init__.py` |
| `polisyos.fabric` | `polisyos.fabric.api` | `src/polisyos/fabric/api.py` (no direct `__all__` declaration) | 41 | `from __future__ import annotations` at `src/polisyos/fabric/__init__.py` |
| `polisyos.fabric` | `polisyos.fabric.world` | `src/polisyos/fabric/world/__init__.py:101`; AST `3d5fd2d7feaa…` | 41 | conditional or mutated `__all__`; exact source locator in raw report |
| `polisyos.foundry` | `polisyos.foundry` | `src/polisyos/foundry/__init__.py:55`; AST `dda4b8aa3eca…` | 31 | `from __future__ import annotations` at `src/polisyos/foundry/__init__.py` |
| `polisyos.foundry` | `polisyos.foundry.api` | `src/polisyos/foundry/api.py:10`; AST `41b406ffdb70…` | 3 | `from __future__ import annotations` at `src/polisyos/foundry/__init__.py` |
| `polisyos.foundry` | `polisyos.foundry.compile` | `src/polisyos/foundry/compile/__init__.py:15`; AST `18a13573323f…` | 1 | `from __future__ import annotations` at `src/polisyos/foundry/__init__.py` |
| `polisyos.foundry` | `polisyos.foundry.execute` | `src/polisyos/foundry/execute/__init__.py:10`; AST `09f25546e33a…` | 4 | `from __future__ import annotations` at `src/polisyos/foundry/__init__.py` |
| `polisyos.foundry` | `polisyos.foundry.uncertainty` | `src/polisyos/foundry/uncertainty/__init__.py:43`; AST `2b35ddff51bd…` | 18 | `from __future__ import annotations` at `src/polisyos/foundry/__init__.py` |
| `polisyos.scientist` | `polisyos.scientist` | `src/polisyos/scientist/__init__.py:16`; AST `46d014c87af2…` | 39 | `from __future__ import annotations` at `src/polisyos/scientist/__init__.py` |
| `polisyos.scientist` | `polisyos.scientist.governance.continuous` | `src/polisyos/scientist/governance/continuous/__init__.py:7`; AST `e5c91f763c2c…` | 87 | `from __future__ import annotations` at `src/polisyos/scientist/__init__.py` |
| `polisyos.scientist` | `polisyos.scientist.methods.research_dag` | `src/polisyos/scientist/methods/research_dag/__init__.py:61`; AST `08f831f8c001…` | 44 | `from __future__ import annotations` at `src/polisyos/scientist/__init__.py` |
| `polisyos.scientist` | `polisyos.scientist.replay` | `src/polisyos/scientist/replay/__init__.py:8`; AST `96865295b19b…` | 25 | `from __future__ import annotations` at `src/polisyos/scientist/__init__.py` |
| `polisyos.evidence` | `polisyos.evidence` | `src/polisyos/evidence/__init__.py:31`; AST `9ccc8c0fd8b4…` | 19 | `from __future__ import annotations` at `src/polisyos/evidence/__init__.py` |
| `polisyos.runtime` | `polisyos.runtime` | `src/polisyos/runtime/__init__.py:30`; AST `ad505e969c25…` | 10 | `from __future__ import annotations` at `src/polisyos/runtime/__init__.py` |
| `polisyos.runtime.quality` | `polisyos.runtime.quality` | `src/polisyos/runtime/quality/__init__.py:1115`; AST `15e986f34760…` | 966 | `from __future__ import annotations` at `src/polisyos/runtime/__init__.py` |
| `polisyos.lex` | `polisyos.lex` | `src/polisyos/lex/__init__.py:13`; AST `c0ed32215e05…` | 51 | `from __future__ import annotations` at `src/polisyos/lex/__init__.py` |
| `polisyos.lex` | `polisyos.lex.knowledge` | `src/polisyos/lex/knowledge/__init__.py:8`; AST `b385cbf6ef45…` | 14 | `from __future__ import annotations` at `src/polisyos/lex/__init__.py` |
| `polisyos.scholar` | `polisyos.scholar` | `src/polisyos/scholar/__init__.py:15`; AST `9156110d17b6…` | 25 | `from __future__ import annotations` at `src/polisyos/scholar/__init__.py` |
| `polisyos.data_forge` | `polisyos.data_forge` | `src/polisyos/data_forge/__init__.py:146`; AST `a6e86a75645d…` | 49 | `from __future__ import annotations` at `src/polisyos/data_forge/__init__.py` |
| `polisyos.data_forge` | `polisyos.data_forge.read_api` | `src/polisyos/data_forge/read_api/__init__.py:54`; AST `7de8983c25c1…` | 16 | `from __future__ import annotations` at `src/polisyos/data_forge/__init__.py` |
| `polisyos.berl` | `polisyos.berl` | `src/polisyos/berl/__init__.py:20`; AST `6bda231536ad…` | 11 | `from __future__ import annotations` at `src/polisyos/berl/__init__.py` |
| `polisyos.calibration` | `polisyos.calibration` | `src/polisyos/calibration/__init__.py:20`; AST `4c9a4cf744d4…` | 10 | `from __future__ import annotations` at `src/polisyos/calibration/__init__.py` |
| `polisyos.ddm` | `polisyos.ddm` | `src/polisyos/ddm/__init__.py:67`; AST `9d745e76f17f…` | 17 | `from __future__ import annotations` at `src/polisyos/ddm/__init__.py` |
| `polisyos.foundry.agent_sim.world` | `polisyos.foundry.agent_sim.world` | `src/polisyos/foundry/agent_sim/world/__init__.py:27`; AST `34574af3ac6b…` | 23 | `from __future__ import annotations` at `src/polisyos/foundry/__init__.py` |

Current first-refusal distribution over these 38 rows: 34 `ImportFrom` effects (all `from __future__ import annotations`), 2 `ClassDef` effects, 1 unsupported `__all__` expression, and 1 conditional/mutated `__all__`. The raw report also contains the complete post-prototype 38-row table, not a sampled subset.

## Engineering options

1. **Reuse the current bounded static resolver.** Keep unknowns unknown, preserve candidates separately, and keep the gate red/incomplete. This is the current honest behavior; it does not supply a complete runtime inventory.
2. **Broaden the passive AST proof.** A real closure would need a generic source proof for lazy maps, `__getattr__` dispatch, importlib/module-name resolution, transitive owner bindings, conditional optional-dependency facades, and all resulting export names. Recognizing only `__future__` or allowing selected imports cannot prove that contract. A static-proof implementation would need to cover and adversarially falsify the entire current 38-entrypoint set, not gain green by package-name allowlist or runtime import.
3. **Profile-qualified runtime witness after source freeze.** The narrower available engineering route is to freeze the exact source tree/profile, build or install from it, then in a fresh isolated process resolve the complete `__all__` of all 38 declared entrypoints and every listed name, recording source/build identity, Python/runtime and optional-dependency profile, complete per-entrypoint names, and failure status. Reconcile those full sets with the source declarations and installed artifact. Such a result is explicitly a profile-qualified runtime witness, not a universal static proof. This avoids new global static-inventory semantics while making the actual executable surface observable.
4. **Inventory declarations only.** A separate declared-name inventory might aid review, but relabeling declaration candidates as complete runtime exports would change the property and would be unsound where maps, conditions, or dispatch affect actual exports. No such contract change is recommended here.

The root reported independent runtime counts for some facades (Core 642, IR 292, Foundry uncertainty 18, Scholar 51). They are not independently re-run in this passive-AST assessment and are not the same measure as the raw `declared_export_candidate_count` (for example, the source candidate count across Core's five declared entrypoints is 270; across IR's three it is 587; root facades alone show different counts). Do not infer one measure from the other. A future runtime witness must state its exact path/profile and reconcile all names, rather than treating a count as proof.

## P38 property boundary and falsifier

**Intended property:** the public-surface inventory establishes the names actually exported by every declared runtime entrypoint, with exact scope and no silent empty-namespace interpretation. **Current implementation:** a bounded static declaration resolver, which audits source under a pure import-time grammar and deliberately never executes modules or runtime dispatch. **Divergent case:** a valid `from __future__ import annotations` directive is a compiler directive and does not add/change export names, but the current effect auditor marks its dependent facade unresolved; after the passive prototype admits that directive, a different import/class/conditional effect still keeps the row unresolved. Thus the current gate establishes static proof completeness, not the actual runtime export set. The honest result is unknown/fail-closed, not “no exports”; close the gap with a complete source proof or the explicit profile witness above.

P29/P32/P35/P38 apply: evidence is derived from the full source set, not names/markers or an importlib declaration alone. P40 classification is the second same-class deeper finding. The smallest next capability that closes the stated runtime-inventory limitation is a fresh-process, source/build-bound full-name resolver over all 38 entrypoints, with optional dependency/profile conditions observed and recorded. No such witness was run in this task.

## Reproducibility and retained evidence

The full output is not duplicated here. It is retained under ignored `LOCAL/raw/` and cited by exact path and SHA-256:

- Probe command: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/public-export-inventory-current/current-prototype.command.json` — SHA-256 `91671f22d70cc3ee412a819ca6611d9f4758bb85f7ebcf2480ff3b02e2fcbe88`; argv is `.venv/bin/python docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/public-export-inventory-current/current_and_future_probe.py`; CWD is the product root; no environment overrides were recorded.
- Probe source: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/public-export-inventory-current/current_and_future_probe.py` — SHA-256 `61f0b5c0e657e2b55a4f6ae5abba3f66b7b9b301302c48700e68ce261a22d914`.
- Full JSON stdout (all 20 policies, 38 rows, exact refusal strings, prototype controls, and hashes for all 48 source/artifact inputs): `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/public-export-inventory-current/current-prototype.stdout.json` — SHA-256 `96047f230cd951b64fe0de047f618d975a2e7d52deec86f733560927155dc719`, 270,132 bytes.
- stderr: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/public-export-inventory-current/current-prototype.stderr.txt` — empty, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- exit status file: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/public-export-inventory-current/current-prototype.exit.txt` — `0`, SHA-256 `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Runtime recorded by probe: `3.14.3 (main, Feb 12 2026, 00:29:58) [Clang 21.1.4 ]`. The command fixture did not record elapsed time; no timing claim is made.

Pinned key inputs from the complete 48-path hash map:

| Input | SHA-256 |
|---|---|
| `architecture/public_surface/contract.toml` | `14ae5db4c9f137e2d5b434fd1cdf259151216e7952b50da04218754eef3bdce6` |
| `tools/devx/architecture/guardrails.py` | `5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6` |
| `architecture/public_surface/inventory.json` | `e630af14c07955b6607435749f881858f0c72d061318b89791de5b3153b829aa` |
| `docs/reference/public-surface.md` | `dd88b95930b185dee6021dd34f44feb2c09af167e66368fa04fcfa82fae5674a` |

The full output records hashes for every facade and refusal-source input; the rows above are an index, not a shortened input set. No imports of the target public facade modules, installs, generation, source modifications, or heavy tests were performed for this assessment.
