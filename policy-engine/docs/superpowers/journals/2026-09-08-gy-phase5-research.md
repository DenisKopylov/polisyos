# GY Phase 5 research — 2026-09-08

Stage 1 in progress; no production changes authorized before the research and architecture record.

## Station and source

Requested worktree `/Users/deniskopylov/polisyos/.worktrees/gy-phase5`, attached branch `codex/gy-phase5-execution`, immutable slice base `3d572c146`. Creation ran `git worktree add /Users/deniskopylov/polisyos/.worktrees/gy-phase5 -b codex/gy-phase5-execution 3d572c146`, exit 0. Readback `git status -sb` returned `## codex/gy-phase5-execution`, exit 0. No auxiliary worktrees created. Source checkout has user edits in LEDGER and its checker; neither is touched or executed.

`uv sync --offline --frozen --extra lint --extra test --extra runtime --extra ml` exited 1: missing cached jaxlib 0.8.2 CPython 3.14 macOS wheel. A lane-local venv was created by uv. Its site-packages uses a `.pth` to read the existing station installed dependencies; local source is explicitly first through PYTHONPATH. No other checkout is modified. The read-only station production_data is linked into the lane. Both paths are ignored local environment, not delivered source. Literal python3 children receive lane-local .venv/bin first in PATH.

Research evidence, executable probes and full transcripts are retained below `docs/superpowers/journals/gy-phase5-evidence/`. All terminal classifications remain not_established until measured.

## Shared SKG fork

Measurement pending.

### Station correction (research, no production delta)

The OR-Tools-dependent positive EFFECT controls initially skipped. Offline `uv pip install --offline --python .venv/bin/python ortools` returned 1 (no cached package); ordinary package installation then installed the locked OR-Tools 9.15.6755 but resolved newer transitive versions. The targeted re-execution exposed pandas 3 / DuckDB `Data type str not recognized` before the property. This is a measured station dependency conflict; exact locked transitive versions are restored (numpy 2.3.5, pandas 2.3.3, protobuf 6.33.2, absl-py 2.3.1, immutabledict 4.2.2, typing-extensions 4.15.0). The failed and subsequent successful exact gates are retained separately. No source behavior is repaired for this station error.

### P5-SKG-01 — shared fork, measured before execution planning

The certified SKG alternative is not blocked by a DataForge write boundary in this lane. Its source/reference producer and N7 bridge already exist and execute: `skg-real-replay.json` records full current-source CAS replay, `reference_population_recomputed`, persisted `completed_no_results`, CG2 `cold_start`, N8 `blocked`, zero world groundings and zero network calls. The exact acceptance slots `relation_gold_context`, `accepted_relation_adjudicator`, `outcome_sensitive_calibration_rule` remain typed `None`. Actual production CG2 returns `records=[]`, `source_id=none_wired_production_freezes`.

The remaining authority-positive bridge requires a scientific acceptance ruling and independently admitted relation-outcome evidence, not an owner appointment alone. Source publication admissibility is a different predicate from whether THIS proposal matches THIS reference atom/context. The existing wrong-atom test exercises that divergence; source/calibration/replay controls passed (29 cases). Building a new signed carrier or using publication labels would not fill that gap (P29/P32/P37/P38). Existing mechanism, CAS persistence, current request replay and typed empty slot are retained. Proposed home: `cg2-production-relation-gold-acceptance-unspecified` (existing GGA-PA1-06 finding); acceptance semantics `team-architecture`, relation source/verifier DataForge academic/knowledge, CG2 consumption runtime/quality. A ruling defining exact contextual gold, accepted independent adjudicator and outcome-sensitive acceptance, plus actual accepted observations, would falsify this blocked positive-bridge decision. No claim of global impossibility of semantic recovery is made.

The complete retained station path denominator is 6,562 regular files, Path.rglob and os.walk identity sets equal; eight database files are readable with native table identity sets independently equal. All 27 tables of the academic holder were inspected for native schema and count. The complete populations were compared row-by-row via Python Counter and SQL GROUP BY: 55,176 SKG variable names; 7,868 causal claim IDs; 7,607 edge IDs; 67,791 publication adjudication IDs; 62,248 native numerical estimate IDs; 5,124 simulation-reference IDs. These are distinct denominators, never promoted into calibrated observation counts. Full outputs and identity hashes are in `shared/skg-census-v2.json`. Initial census returned 1 because a git glob omitted root `src/polisyos/__init__.py`; the corrected whole-directory enumeration reconciles all 2,630 tracked production Python identities. The failed census credits no partial total.

`not_established`: semantic source coverage for a particular intervention and target; source snapshot institutional authenticity; relation gold/context/adjudicator/acceptance rule; a complete positive production N8/canonical promotion. Literal absence of avg_income is lexical evidence only.
