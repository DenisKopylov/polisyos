# Task C — DS10 capability discovery closure journal

Date: 2026-08-30  
Branch: `codex/debt-c-ds10-capability-discovery`  
Entry commit: `784d020148c56e9bfb3a3631909ba11232210a9f`

## Entry and governing evidence

- Worktree attachment: `git status -sb`, `git symbolic-ref -q HEAD`, and `git rev-parse HEAD` all completed exit 0. The tree was clean and attached to the requested branch.
- Read in full before planning: all twelve `DEBT-REGISTER.md` rows at lines 235–243, 269, 274, and 374; `CONTRIBUTING.md`; the P01–P41 failure/repair table including P38; `wave5-evidence-substitution-ratification.md` including ratified `W5-K01`; and the DS10 active plan's explicit non-closures.
- `uv sync --frozen` completed exit 0 and created the worktree-local environment.

## Anchor control — disagreement reported before row work

The requested 2,579-file denominator does not hold at this branch tip. A complete AST walk over the tracked set and two independent tracked-path counts agree on **2,611 unique `src/**/*.py` paths**:

```text
git ls-files -- 'src/**/*.py' | wc -l                                      -> 2611
git ls-tree -r --name-only HEAD -- src | awk '/\.py$/ {count++} END ...'  -> 2611
git ls-files -- 'src/**/*.py' | sort -u | wc -l                            -> 2611
```

The AST walk completed exit 0 after about 64 seconds and found:

```text
tracked_src_python_files=2611
production_implementations=0
protocol_declarations=2
protocol_declaration=src/polisyos/runtime/quality/capability_resolver.py:162:CapabilityLiveOperationRegistry.resolve_operation
protocol_declaration=src/polisyos/runtime/quality/capability_resolver.py:170:CapabilityConformanceVerifier.verify_conformance
admission_rows=61
admission_states={'admitted': 8, 'blocked': 1, 'candidate_shadow_only': 52}
admission_prohibited_key_counts={
  'resource_kind': 0,
  'capability_purpose': 0,
  'passport_receipt': 0,
  'evidence_receipt': 0,
  'currentness_receipt': 0,
  'capability_discovery_provider': 0,
}
```

Control disposition: the path denominator is **2,611, not 2,579 (+32)**. The substantive anchor agrees: **0 concrete implementations / 2,611 tracked Python paths**, plus two Protocol declarations; **61 admission rows**; zero occurrences of each named DS10 capability key/provider in those 61 rows.

## Baselines

- `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` completed exit 0 but reported `closure_signal_collection_host_unknown=32` and `pytest is unavailable`; this is an explicit non-receipt and will not be used as evidence.
- `PYTHONPATH=. uv run --extra test python tools/quality/validation/check_debt_ledger.py --check` completed exit 1 after roughly six minutes. It reported `closure_signal_identity_unresolvable=18`, `closure_signal_collection_host_unknown=0`, and the matching 18 informational count/exit disagreements. Eight unresolved identities are this task's DS10 pytest nodes; the other ten are the registered DS11/decision-validity peers. This is the known `debt-closure-signals-name-unwritten-tests` checker defect and is baseline evidence only, not a verdict for any row.
- `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` completed exit 1 with exactly six findings: two `active_plan_metadata` findings for architect-owned `LEDGER.md`, and four `removed_stub_reference` findings. This is the required before-state.

## Pattern stance

- P38 property: a capability-discovery row is produced by its named owner index with content-bound receipt/provenance; execution availability, an admitted adapter identity, world-model lookup, or review posture is not that property.
- Current implementation predicate: DS10 composes installed finite-kind providers and reports `producer_missing` for absent kinds; the adapter operation/conformance ports have only Protocol declarations.
- Divergent cases held fixed: execution may be available while no method row exists; a bridge adapter may be admitted while no DS10 kind/purpose/receipt/provider exists; L4 lookup may return world data while no Scientist agent/tool index exists; an internal reviewer result may exist while public custody authority is absent.
- `W5-K01` consequence: more same-stream rows do not establish a missing object. Those four divergent cases cannot close their rows.

## Row ledger (initial state, not verdicts)

| row | exact probe or deciding predicate |
| --- | --- |
| `ds10-adapter-admission-capability-discovery-bridge` | exact named pytest node through real admission builder; reject admitted-flag/tuple substitutes |
| `ds10-lex-pipeline-mutation-boundary` | backend file plus complete read-only frontend call-graph/title measurement; zero-selected title is not evidence |
| `ds10-causal-method-index-provider-bridge` | exact named node requires default owner-index method rows and content-bound receipt |
| `ds10-owner-signed-capability-purpose-binding` | exact named node requires independent signed ref/digest/purpose joined to DS9 currentness |
| `ds10-connector-acquisition-content` | exact named control-API node requires real connector/source-profile producer snapshots |
| `ds10-public-decision-rendering` | exact named public-export node requires custody-bound public decision, not internal posture |
| `ds10-global-case-index-producer-allocation` | exact named API node requires appointed canonical global index; run-bound case strings are negative |
| `ds10-world-agent-capability-discovery-boundary` | exact named integration node requires Scientist registry snapshots; L4 lookup is negative |
| `ds10-layer3-owner-ledger-rejection-richness` | exact named node walks complete G2/G3/GL owners and forbids synthesized rejections |
| `three-unavailable-governed-producers` | investigate all three sources and recompute the complete 13-projection availability/reason census |
| `ds10-adapter-registry-data-only-free-growth` | exact named node mutates governed contract data and runs real post-G0 admission |
| `ds10-c13-print-receipt-reissue` | complete current 11-binding hash census plus two distinct zero-retry/no-writer outputs; no frontend source writes |

## C13 currentness investigation

The complete receipt-defined set is eleven paths. Its current-byte census completed exit 0 with **5/11 current and 6/11 stale**:

```text
stale  AmbientTelemetryHud.tsx    232392b0... -> a06e6a98...
stale  OperatorCraftPanel.tsx     687a831d... -> 8d94ade6...
stale  RunDetailLayout.tsx        514ddff6... -> f4533fee...
stale  RunReportPage.tsx          4bb0bea6... -> 5f51a10e...
stale  RunReportPage.test.tsx     d3b5819e... -> 30023d27...
stale  runtime-dashboard.visual.spec.ts
                                  c472f411... -> 3a69dd55...
```

The other five bindings match. `apps/runtime-dashboard/src/app/routes/routes.tsx` is not a member of the receipt's declared `source_bindings`. The supplied two-binding premise therefore disagrees both with the register's existing 6/11 subject sweep and with this fresh 6/11 census.

The exact admission test:

```text
uv run --extra test pytest architecture/atlas_surfaces/test_frontend_disposition_register.py::DS6C13PrintTransitionTests::test_independent_receipt_binds_the_full_conjunction_and_current_bytes -q
```

completed exit 1 at the first stale whole-file binding. The authorized run-one browser command then used `CI=1`, `PLAYWRIGHT_RETRIES=0`, `--workers=1`, `--retries=0`, `--update-snapshots=none`, the exact `DS8 governed run paper` grep, and scratch-only JSON/output paths. It completed exit 1 before selecting a test:

```text
expected=0 skipped=0 unexpected=0 flaky=0
TypeError: Module ".../src/shared/i18n/locales/en.json" needs an import attribute of "type: json"
Error: No tests found
```

Before and after that no-writer attempt, the environment tuple digest was identically `867883c4c6ab6fb16d7b6c2a5e06599c0772df05593b08d4da1d549a9f998c23`; the governed snapshot remained SHA-256 `26cca8a75e61cfcf8873cfc7417b6bb0c7f2cacdd8490bfa45d256422513041a`, 19,197 bytes; and `git diff --exit-code -- apps/runtime-dashboard` completed exit 0. A second expensive run cannot create an independent passing receipt after the first run selected zero tests, so the row stops as `blocked` under the frontend-corridor rule.

## Register closure dossier

The final section will contain twelve append-only blocks after all measured adjudications. No architect-owned register file is edited in this branch.
