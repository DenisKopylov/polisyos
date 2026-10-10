# Decision-packet complexity repair — DX0 research packet

**State:** read-only research complete; no product source, tests, budgets, or Git state changed by this task. The only new artifacts are under this packet's `raw/` directory. **Candidate:** `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`, HEAD `077a572ff5880b3f50a85d3e3db6a232d277659a`, tree `2895b6c7597215b714275cb4ba83a504724dc89c`.

## Finding and decision

The old complexity exception describes a 4,704-line implementation at `build_decision_packet.py`, which is now a six-physical-line compatibility shim. Its expiry is 2026-08-15. The live implementation is the `decision_packet/` package: **5,150 physical lines** across six Python files, plus the shim. The exception is therefore both expired and attached to the wrong source unit. It does not measure package size, and it is not a Ruff C901 exemption.

The existing implementation can be reorganized without changing packet meaning. Keep the legacy API and producer identity, split the mixed projection module by responsibility, and factor the six over-cap functions around their existing branches. Reuse the typed IR loaders, existing `decision_packet_support.py`, and existing validation/serialization modules. Do not add gates, alter the C901 cap, widen a size budget, change packet fields/schema, or change authority or selected-reference handling.

The reuse-first scan found no existing causal, strategic, evidence, or uncertainty *decision-packet projection* owner to receive the large section families. Existing causal/simulation modules produce or validate those artifacts; moving output projections into them would invert the current producer-to-consumer boundary. `decision_packet_support.py` is a fitting existing home for the optional source-report loading block removed from `builder.py`; it is currently 211 physical / 181 logical lines. Keep the remaining packet projection modules package-owned and split them by section family.

## Pattern pass

- **P13, proportional governance:** relevant. A stale exception and one 2,891-logical-line section module impose cost without identifying the live owner. The repair removes the one stale exception and splits the module; it adds no policy or quality gate.
- **P31, fix the class:** relevant. One coherent section-family split plus shared control-flow helpers addresses the oversized module and all six C901 findings; do not suppress individual functions or keep extending the facade.
- **P38, name the measured property:** the requested property is “all decision-packet functions remain at or below C901 12, and no implementation module exceeds the existing per-module line limits.” The current exception row measures the old shim path; current Ruff configuration does not select C901 or set `max-complexity`, so the cap-12 result is currently an explicit native Ruff invocation, not a configured repository gate. Keep that invocation as the package acceptance check; wiring a new global lint gate is outside this no-threshold-change task.
- **Capability state:** this is an internal refactor of an already wired node, not a new capability. The node, persisted artifact, orchestration, consumers, authority checks, and semantic tests already exist.

## Measured baseline

The module-size validator's source of truth counts nonblank, noncomment lines. Current physical / logical counts are:

| Path | Physical | Logical |
| --- | ---: | ---: |
| `decision_packet/__init__.py` | 7 | 4 |
| `decision_packet/api.py` | 31 | 23 |
| `decision_packet/builder.py` | 981 | 954 |
| `decision_packet/enrichment.py` | 3,053 | 2,891 |
| `decision_packet/serialization.py` | 506 | 471 |
| `decision_packet/validation.py` | 572 | 512 |
| `decision_packet/` package total | **5,150** | **4,855** |
| legacy `build_decision_packet.py` shim | 6 | 4 |

Native Ruff C901, with the requested cap 12 passed explicitly on the whole package, reports six functions:

| Path and function | Complexity |
| --- | ---: |
| `builder.py:219` `BuildDecisionPacketNode.execute` | 34 |
| `enrichment.py:597` `_build_causal_section` | 16 |
| `enrichment.py:853` `_build_strategic_section` | 24 |
| `enrichment.py:2790` `_build_uncertainty_bounds` | 16 |
| `validation.py:185` `_build_analysis_limits` | 13 |
| `validation.py:485` `_collect_contract_warnings` | 14 |

The repository module-size report currently returns `status=contract_errors`, `contract_error_count=77`, and six report-only findings. Its relevant findings are `builder.py` at 954 logical lines versus the registered current budget 926 and report-only limit 926. It does not report `enrichment.py`: its logical count 2,891 is under that entry's existing 3,022 report-only limit, though above the default 1,000 warning. Keep these existing budget thresholds; shrink the builder below its existing 926-line ceiling and the section module below the 1,000-line default. The report's other findings/errors are repository-wide and are not evidence that this slice passes.

The full `src/polisyos` C901 cap-12 run reports 1,190 findings in 615 files. That existing repository-wide state is not a useful slice acceptance gate. The final native check for this task should cover **every file in `decision_packet/`** and any existing support module changed by the repair.

## Source graph, API, and behavior to preserve

The complete AST record is `raw/decision-packet-source-map.json`. It contains imports, module edges, function/class spans, arguments, intra-package call names, and all direct Python import consumers found under `src/` and `tests/`. The module DAG is:

```text
decision_packet.__init__ -> api
api -> builder, enrichment, serialization, validation
builder -> enrichment, serialization, validation, decision_packet_support
enrichment -> serialization, validation, decision_packet_support
serialization -> validation
validation -> decision_packet_support
```

There is no package cycle. `api.py` derives `__all__` dynamically from `dir()` on the four modules and currently exposes 296 names, including incidental imported names. `__init__.py` exposes `BuildDecisionPacketNode`; the legacy shim star-imports `api`. Keep `api.py` and `__init__.py` unchanged, preserve the existing compatibility globals in `enrichment.py`, and verify its `api.__all__` set against `raw/decision-packet-api-surface.json` after splitting. Do not silently contract the current exported surface as part of a complexity repair.

The function ownership split below follows the current AST spans, keeps the public import owner intact, and places each complex function with its private branch helpers:

| Proposed owner | Current functions / source spans | Approximate existing code span |
| --- | --- | ---: |
| Keep in `enrichment.py` | Human-review and claim attachment, runtime/web/VOI/continuous-governance projections, `_build_policy_summary` (201–595); metric projections and labels (2885–3006) | ~520 physical lines, plus facade imports/exports |
| `causal_sections.py` | `_build_causal_section`, `_normalize_dp_summary`, `_merge_dp_summary_into_causal_payload`, `_build_transportability_summary` (597–850, 1219–1255) | ~290 lines |
| `strategic_sections.py` | `_build_strategic_section`, `_performative_loop_payload` (853–1216) | ~365 lines |
| `outcome_sections.py` | ABM, abstraction, HTE, targeting, backtest, calibration, feedback, distributional, welfare, Phase 3, tradeoff, econometrics builders (1258–2041) | ~785 lines |
| `basis_sections.py` | Normative arbitration, auxiliary artifacts, sensitivity, diagnostics, normative/data/knowledge/transportability bases, watched triggers, normative-frame loader (2044–2704) | ~660 lines |
| `uncertainty_sections.py` | `_build_uncertainty_section` and `_build_uncertainty_bounds` (2707–2882) | ~180 lines |

These are code-span estimates, not final module LOC; new imports and reexports need to be counted by the same logical-line source after implementation. The largest proposed implementation module starts with fewer than 800 current physical lines, leaving room for its typed imports under the existing 1,000 logical-line warning. Keep cross-module calls directed to validation, serialization, support, or domain loaders, never back to the `enrichment.py` barrel.

The direct production import paths are the builtin registry through the legacy shim and Runtime epoch issuance through `decision_packet.builder.BuildDecisionPacketNode`. Epoch issuance pins the canonical producer string `polisyos.scientist.nodes.builtins.decide.decision_packet.builder.BuildDecisionPacketNode.execute`; keep that class and method at that path. `execute` captures the invocation before packet work and passes the method code plus `builder.py` source bytes to the existing issuance port.

Direct helper consumers also exist: `test_decision_packet_web_evidence.py` imports `_build_web_evidence_section` from the legacy facade, and the real welfare propagation/readback test imports `_build_welfare_section` from `decision_packet.enrichment`. The alias characterization test requires `_build_policy_summary.__module__ == enrichment.__name__`; leave that helper in `enrichment.py`. It also pins the current aliases for the node, manifest builder, and degraded-path helper. Keep the existing explicit `enrichment.__all__` names available from the same path after moving implementation functions.

The authority-sensitive execution order is:

1. Capture the exact invocation and input references before packet work.
2. Build the existing v3.4 payload and enrich sections / report projections; preserve typed refs passed to the existing loaders.
3. Build validity and epoch preparation before publication gates.
4. Apply serious-profile requirements, claim-spine, human-review, research-DAG, then opted-in Phase-5 gates.
5. Persist the canonical packet only after those gates pass.
6. Finalize claim-root and epoch issuance, register decision validity, and then update branch state.

Do not move, weaken, or reorder these gates. Keep `CanonSpec(forbid_floats=False)`, the `scientist.decision_packet` kind, schema name/version `polisyos.scientist.DecisionPacket` / `3.4`, packet field names, status values, diagnostics, degradation handling, authority states, and current selected-view semantics unchanged. Existing test vectors deliberately preserve distinct selected manifest profiles for identical artifact IDs.

## Narrow author footprint proposed for root approval

Product mechanism paths:

- Modify `src/polisyos/scientist/nodes/builtins/decide/decision_packet/builder.py` and existing `decision_packet_support.py` to extract optional report reads and split `execute` into small private stage/gate helpers while preserving call order and the public method path.
- Keep `src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py` as the compatibility barrel and retain `_build_policy_summary` there. Add five package-private implementation modules, each with one clear responsibility: `causal_sections.py`, `strategic_sections.py`, `outcome_sections.py`, `basis_sections.py`, and `uncertainty_sections.py`. Re-export the moved functions from `enrichment.py`; new implementation modules must not import `enrichment.py` back.
- Factor `_build_analysis_limits` and `_collect_contract_warnings` in existing `decision_packet/validation.py`. Factor the causal, strategic, and uncertainty branch logic in their new section owners without changing loader order, warning order, degraded-path records, fallback values, or output keys.
- Delete only the stale decision-packet exception row in `architecture/exceptions/complexity.toml`. Keep `default_max_module_lines=1000`, `default_max_complexity=12`, all other exception rows, and every threshold/target in `architecture/module_size_budget.toml` unchanged. The current builder budget should be satisfied by the code moving below 926 logical lines; the split sections should fall below the existing 1,000-line warning without adding new waivers.

Mandatory mirrored contract test: extend `tests/unit/scientist/nodes/builtins/decide/test__decision_packet_contracts.py` to assert that representative moved helper names remain identical through the new owner module, `enrichment`, `api`, and the legacy facade. Update the nearest existing README, `src/polisyos/scientist/nodes/README.md`, to describe the internal package split and stop describing the old shim as the implementation owner. Update the source-of-truth paths in `docs/reference/scientist/claim-ledger.md`, `docs/reference/scientist/continuous-governance.md`, and `docs/reference/scientist/human-oversight.md` from the shim to the live package owner; the stable workflow/API name in `docs/reference/scientist/claims.md` may remain the compatibility node name.

No release fragment is needed for a behavior-preserving internal refactor unless the public export set changes; if it changes, stop and treat that as an API scope change.

## Authoring order and falsifiers

1. Extend the alias contract test first. Red signal: a moved helper is absent from `enrichment`, `api`, or the legacy facade, or `_build_policy_summary` changes owner.
2. Move section implementations by the five family groups, keeping their typed loaders and branch behavior, and re-export each legacy function from `enrichment.py`.
3. Factor the three high-branch section functions and two validation functions with private helpers. Keep call order and fallback/degraded-path writes identical.
4. Move the optional report-loading block into existing `decision_packet_support.py`; split the remaining builder flow into small stage/gate helpers, retaining the `execute` producer identity and persist-after-gates order.
5. Remove the one stale exception row and correct the nearest/source-of-truth docs. Do not modify module-size thresholds or add `noqa` exceptions.
6. Run the focused semantic tests below, Ruff on the touched files, native C901 cap 12 on the whole package, and the module-size report. Preserve complete outputs. Compare only changed-path findings in the repository-wide report because it currently has unrelated contract errors.

Existing behavioral tests are the falsifiers; they are not constructor-only checks:

- If claim-spine validation is bypassed, `test_build_decision_packet_blocks_naked_recommendation_when_claim_gate_enabled` must fail.
- If Phase-5 gating moves after persistence, `test_decision_packet_is_not_persisted_when_phase5_blocks` must fail.
- If strategic runtime projection or fallback changes, `test_build_decision_packet_surfaces_strategic_runtime_artifacts` or `test_build_decision_packet_falls_back_to_blocked_strategic_summary_without_bundle` must fail.
- If uncertainty degradation or metric projection changes, their named node-v3 and metric-validation tests must fail.
- If the public helper aliases disappear, the alias test and direct web/welfare helper consumers must fail.
- If selected inputs are collapsed to bare artifact IDs, `test_invocation_input_refs_keep_distinct_selected_views_for_one_artifact`, the malformed-selector cases, and `test_epoch_basis_persistence_keeps_distinct_selected_input_views` must fail.

## Baseline receipts

All tests ran with the candidate `.venv`, `PYTHONPATH=src:.`, and a preflight that resolved `polisyos`, `decision_packet.api`, `.builder`, and `.enrichment` under this candidate checkout.

- Focused compatibility, authority, section, and producer-consumer tests: 15 passed, 2 upstream Torch deprecation warnings, 6.46s. Complete output: `raw/baseline-focused-tests.log`.
- Epoch invocation / selected-profile tests: 11 passed, 2 upstream Torch deprecation warnings, 12.58s. Complete output: `raw/baseline-profile-tests.log`.
- C901 package cap-12 baseline: exactly the six findings above, exit 1. Complete output: `raw/c901-decision-packet-cap12.stdout`.
- `src/polisyos` C901 cap-12 background count: 1,190 findings / 615 files, exit 1. Complete output: `raw/c901-polysios-cap12.stdout`.
- Module-size report: complete JSON in `raw/module-size-report.json`; the overall report is not green (`contract_errors`, 77 errors), so use it only for its changed-path observations.
- The full package/source/test AST and dependency census is `raw/decision-packet-source-map.json`; dynamic API baseline is `raw/decision-packet-api-surface.json`; high-complexity function outline is `raw/complex-function-outline.txt`.

Raw receipts (all local-only): `decision-packet-source-map.json@sha256:0e103357724bd98cec0aa20a04a0068e8a21184cdc434fd646c90ba3bbb0a91b` (242,384 bytes); `decision-packet-api-surface.json@sha256:0af1f0b879882e721fc7086c7899dcf0281dc17fce49daa40eab3d5c5bf15fcb` (13,019); `module-size-report.json@sha256:67b0e8fa024a1b3643c5c4edf9315b2f8a34903c50a7a3fcd1a085e7ca7eae96` (24,136); package C901 output `@sha256:f1402757d63f64b957c9c24973525ab94ae53bee4449a7ce0ea0dc48d56b2f65` (829); full-source C901 output `@sha256:82e1b33aac04078674856c67081155de19fc9a5b6fbe7e453ddd76651521c279` (140,685); focused tests `@sha256:8ef461ef13070e4979beeb64aeaf205d0b12b1cc3c434f09a11b1812280c1a5a` (3,062); selected-profile tests `@sha256:ccf081bbea9d6a87f99c7538288910340a5161c24a263f0dfda290634916f496` (2,757); function outline `@sha256:3317198f2413e5a323463744d1c545ef7bae7d2f84afdd7b3daf3e7c13f8ec4e` (15,875). No source prototype was applied because this stage was explicitly research-only. Root can grant the proposed bounded author footprint after review.
