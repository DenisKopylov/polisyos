# Debt A Promotion Gate — Execution Journal

## Standing

- Worktree: `.worktrees/debt-a-promotion-gate`
- Attached branch: `refs/heads/codex/debt-a-promotion-gate`
- Slice base and initial HEAD:
  `784d020148c56e9bfb3a3631909ba11232210a9f`
- Scope denominator: the five rows named in the task brief and implementation
  plan; protected register/ledger/task-plan files remain read-only.
- EFFECT ruling: `_effect_obligation` is excluded byte-for-byte.
- EvalSafety ruling: safety core/hash and attempted-evaluation authority are
  excluded.

## Initial read-through findings

The source walk corrected two premises without turning them into authority:

1. Attempted-evaluation safety is already implemented and orchestrated through
   the control service, generation/Scientist execution contexts, and evaluator
   chokepoints. Its certificate expressly forbids use for promotion. The N9
   positive predicate is therefore not a missing import; it is a distinct
   `producer_missing` authority chain.
2. N5 already emits real unsupported-coupling blockers, but N9 drops the typed
   `SimulationPortObservation` and checks different strings on
   `CandidateSummary.value_blockers`. This is `bridge_missing`, not absence of
   all producer behavior.

The remaining measured classifications before source edits are:

| Predicate | Classification |
| --- | --- |
| admissibility | real CG2 producer/consumer exists; production assembly bridge missing; caller Boolean is redundant |
| effective independence | N9-purpose producer missing |
| coupling | N5 producer exists; N5→N9 bridge missing |
| measurement | measurement-root producer exists; N8→N9 bridge missing |
| promotion-grade EvalSafety | producer missing; attempted-evaluation certificate is denied for promotion |

## Pattern and P40 bucket

Current side of the line: **narrow patch**. The scoped caller-assertion finding
and scoped absent-token finding teach different properties. No additional
spelling of either property has yet been found outside the named rows. If one
appears, stop enumerating and record the triggering source location before
generalising.

Relevant patterns: `P01`, `P02`, `P04`, `P05`, `P07`, `P10`, `P14`, `P17`,
`P29`, `P31`, `P32`, `P33`, `P37`, `P38`, `P40`, `P41`.

## Command ledger

| Stage | Command/predicate | Direct exit | Decisive output |
| --- | --- | ---: | --- |
| branch preflight | `git status -sb && git symbolic-ref -q HEAD && git rev-parse HEAD && git merge-base main HEAD` | 0 | clean attached `codex/debt-a-promotion-gate`; HEAD and merge-base both `784d02014…` |
| environment bind | `uv sync --frozen --extra test` and `uv run python -c 'import sys, pytest; ...'` | 0 / 0 | bound `.venv/bin/python3`; pytest `9.0.2` |
| red DTO predicates | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_current_input_rejects_legacy_caller_gate_predicates' -q --tb=short` | 1 | both `admissibility=True` and `effective_independence=True` failed with `DID NOT RAISE` |
| red context predicates | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_context_cannot_supply_legacy_gate_predicate' -q --tb=short` | 1 | both legacy context keys failed with `DID NOT RAISE` |
| red coupling | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_coupling_without_bound_n5_projection_is_scope_insufficient' -q --tb=short` | 1 | both no blocker and actual `unsupported_coupling_class:feedback` emitted `satisfied`, not `scope_insufficient` |
| red independence | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_effective_independence_missing_is_explicit_decisive_nonreceipt' -q --tb=short` | 1 | no `#effective_independence` decisive row was emitted (`len(rows) == 0`) |
| red receipt epoch/scope | `uv run python -m pytest '...::test_v4_v1_history_is_readable_but_cannot_be_current_authority' '...::test_v1_scope_rows_cannot_be_restamped_as_current_authority' -q --tb=short` | 1 | current receipt remained v4; a self-consistent v1 scope restamp returned no validation issue |
| real admissibility owner control | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_cg2_open_admissibility_obligation_keeps_promotion_red' -q --tb=short` | 0 | a content-bound CG2 certificate with open `admissibility_closed` produced `not_bind_decision`; IDENTIFICATION refused |
| one-time broader targeted wave | 24 exact changed/blast-radius nodes; diagnostic, not a verdict command | 1 | 26 of 27 parametrized cases passed; the sole failure was the synthetic v2 fixture omitting the two fields required by its frozen v1 owner shape |
| delta-only fixture replay | `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_comparison_refuses_v2_without_open_world_owner_fact' -q --tb=short` | 0 | corrected historical fixture passed; no product source changed after the 26 green cases |
| final high-value selector | exact nine-node selector in the next section | 0 | 12 parametrized cases passed; both caller seams, real CG2 refusal, coupling, independence, anti-vacuity vehicle, receipt epoch, restamp, and EvalSafety owner truth are green |
| runtime obligation census | exact Python predicate in the next section | 0 | data-only and pilot receipts remain non-promotable; COUPLING, EFFECT, MEASUREMENT, independence, and pilot EvalSafety are all fail-closed; owner refs distinguish dotted producers from `absent/unallocated` |
| Ruff | `uv run python -m ruff check src/polisyos/runtime/quality/promotion_sequence.py tests/unit/runtime/quality/test_promotion_sequence.py` | 0 | `All checks passed!` |
| format | `uv run python -m ruff format --check src/polisyos/runtime/quality/promotion_sequence.py tests/unit/runtime/quality/test_promotion_sequence.py` | 0 | both files already formatted |
| EFFECT integrity | AST source-byte extraction and SHA-256 predicate recorded below | 0 | 948 bytes; `2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38`, identical to pre-edit receipt |
| EvalSafety/shared-container integrity | `git diff --exit-code 784d020148c56e9bfb3a3631909ba11232210a9f HEAD -- src/polisyos/runtime/quality/evaluation_safety.py` and the same predicate for `src/polisyos/runtime/http/dependencies.py` | 0 / 0 | neither file differs from the slice base; no shared-container lines were edited |
| governed N9 generated companion | `JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers --extra test python tools/quality/validation/check_layer3_gy_promotion_contract.py --check --output-format json` | 1 | fail-closed `promotion_comparison_admission_manifest_drift`; v4 history rule is not registered in the four generated-owner consumers |
| architecture guardrails after `corepack pnpm install --frozen-lockfile` | `uv run polisyos-tools architecture guardrails check` | 1 | JS generators clean; trust-claim posture receipt fails because its complete `src/**/*.py` denominator includes the changed promotion source |
| debt ledger, fully bound | `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` | 1 | 18 blocking `closure_signal_identity_unresolvable` findings; none names a changed path, but exact slice-base replay was not established, so P41 forbids calling them inherited |
| debt ledger preflight | `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` before installing the test extra | 0, non-receipt | checker reported pytest unavailable and degraded runtime findings; this result is not closure evidence |
| docs lifecycle baseline | `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` | 1 | exactly six known findings: two `LEDGER.md` front-matter findings and four stale dashboard-path references |

## Final deciding predicates

### High-value behavior selector

```bash
uv run python -m pytest \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_current_input_rejects_legacy_caller_gate_predicates' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_context_cannot_supply_legacy_gate_predicate' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_cg2_open_admissibility_obligation_keeps_promotion_red' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_coupling_without_bound_n5_projection_is_scope_insufficient' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_effective_independence_missing_is_explicit_decisive_nonreceipt' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_scope_insufficient_obligation_does_not_vacuously_pass' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_v4_v1_history_is_readable_but_cannot_be_current_authority' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_v1_scope_rows_cannot_be_restamped_as_current_authority' \
  'tests/unit/runtime/quality/test_promotion_sequence.py::test_eval_safety_names_the_missing_promotion_authority_without_reusing_o0' \
  -q --tb=short
```

Direct exit `0`; output: `12 passed` (the quiet reporter emitted twelve dots and
`[100%]`).

### Production-lane obligation census

```bash
uv run python - <<'PY'
from tests.unit.runtime.quality.test_promotion_sequence import (
    _promotion_input,
    _run,
    _value_receipt,
)
import polisyos.runtime.quality.promotion_sequence as p

standard = _run(_promotion_input())
pilot = _run(
    _promotion_input(
        value_receipt=_value_receipt().model_copy(
            update={"evaluation_mode": "field_pilot"}
        )
    )
)
for label, receipt in (("standard", standard), ("pilot", pilot)):
    selected = {
        row.obligation_class.value: (row.status.value, row.owner_ref)
        for row in receipt.obligations
        if row.obligation_class.value
        in {"coupling", "effect", "measurement", "eval_safety"}
    }
    independence = [
        (row.status.value, row.owner_ref)
        for row in receipt.obligations
        if row.source_obligation_ref.endswith("#effective_independence")
    ]
    refusals = p._refusal_reasons(
        receipt.obligations,
        risk_spend=receipt.risk_spend,
    )
    print(
        label,
        "promoted=",
        receipt.promoted,
        "consumer_promotable=",
        receipt.consumer_promotable,
    )
    print(label, "selected=", selected)
    print(label, "independence=", independence)
    print(label, "refusals=", ",".join(refusals))
PY
```

Direct exit `0`. Decisive output:

```text
standard promoted= False consumer_promotable= False
standard selected= {'coupling': ('scope_insufficient', 'polisyos.runtime.quality.generation_cycle.SimulationPortObservation.authority_blockers'), 'effect': ('scope_insufficient', 'GY-K entailment witness owner'), 'measurement': ('scope_insufficient', 'polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer.produce_from_catalog'), 'eval_safety': ('not_applicable_data_only', 'polisyos.runtime.quality.promotion_sequence._eval_safety_obligation')}
standard independence= [('scope_insufficient', 'absent/unallocated')]
standard refusals= coupling:scope_insufficient,effect:scope_insufficient,calibration:single_obligation_fail,measurement:scope_insufficient,data:single_obligation_fail,data:scope_insufficient
pilot promoted= False consumer_promotable= False
pilot selected= {'coupling': ('scope_insufficient', 'polisyos.runtime.quality.generation_cycle.SimulationPortObservation.authority_blockers'), 'effect': ('scope_insufficient', 'GY-K entailment witness owner'), 'measurement': ('scope_insufficient', 'polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer.produce_from_catalog'), 'eval_safety': ('scope_insufficient', 'absent/unallocated')}
pilot independence= [('scope_insufficient', 'absent/unallocated')]
pilot refusals= coupling:scope_insufficient,effect:scope_insufficient,calibration:single_obligation_fail,measurement:scope_insufficient,data:single_obligation_fail,eval_safety:scope_insufficient,data:scope_insufficient
```

This predicate is also the reason the requested “EFFECT is the single remaining
conjunct” sentence cannot be admitted for this branch. The owned source repair
eliminates minting, but the typed N5→N9 coupling bridge, the candidate-bound
effective-independence producer, and the authority-grade N8→N9 measurement
bridge are not present. The attempted-evaluation certificate cannot fill the
last role: its owner expressly lists `promotion` under `may_not_use_for`.

### EFFECT byte identity

An AST extraction of `_effect_obligation` from the slice base and current file,
followed by byte equality and SHA-256 comparison, exited `0`:

```text
base_bytes= 948
current_bytes= 948
base_sha256= 2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38
current_sha256= 2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38
identical= True
```

## Decision log

### 2026-08-30 — governed receipt epoch

`n9_obligation_scope.v2` advances current promotion authority to v5. V4/v1 is
retained as history rather than accepted through the current model. Removing
the two Boolean owner fields advances the owner projection to v3 and retains
the exact v2 owner shape for v4 history.

### 2026-08-30 — no marker widening

The coupling consumer will not add `unsupported_coupling_class:feedback` to an
ever-growing string list. Until a typed N5/S5 result is carried and verified,
absence is `scope_insufficient`. The real spelling is a falsifier for the old
proxy, not a fabricated bridge.

### 2026-08-30 — EvalSafety non-transfer

The existing EvalSafety certificate is deliberately non-authoritative for
promotion. Reusing it would violate its `may_not_use_for` envelope and the task
stop rule protecting the safety core. N9 must name a distinct positive producer
if that predicate is retained.

### 2026-08-31 — governed companion boundary

Current v5 receipts and v4 history parse/refuse correctly inside the owned
runtime module. Full generated-owner compatibility is not delivered: the
promotion artifact is stale and the promotion, generation-cycle, second-domain,
and depth-N checker registries do not register the new v4-history owner rule.
Those files are outside this lane's declared ownership. The capability state is
`consumer_missing`/`surface_missing`, not "fully backward compatible".

### 2026-08-31 — review disposition

Independent review found no remaining caller/coupling minting path. Its one
in-scope test finding was accepted: COUPLING and independence tests now call the
production refusal compositor and assert their nonreceipts become refusal
reasons. The generated-companion findings above are recorded rather than
patched across unowned files.

## Commit ledger

| Commit | Boundary | Receipt |
| --- | --- | --- |
| `6828a8666` | plan/spec/initial journal | committed before the first source change |
| `81b8ceed6` | red-first fixtures | caller, context, coupling, independence, v4 epoch, and restamp paths red |
| `d2bbe314a` | governed fail-closed source repair | current v5/v3/v2, history v4/v2/v1, minting repair, owner truthfulness |
| `ca535d3cd` | review test closure | production refusal composition and exact v2 historical fixture |

## Register closure dossier

The final execution commit appends five complete blocks here. Each block will
contain verdict, exact command or predicate, direct exit, decisive output, and
the exact prose the architect can append beneath the protected row.

### `gy-promotion-obligations-scope-insufficient`

- Verdict: `open`
- Deciding command/predicate: the exact production-lane obligation census above.
- Direct exit and decisive output: exit `0`; the standard receipt contains
  `measurement:scope_insufficient` and `effect:scope_insufficient`, while the
  pilot receipt additionally contains `eval_safety:scope_insufficient`; both
  print `promoted=False consumer_promotable=False`.
- Exact append-only register prose: **Supersession 2026-08-31 — governed v2
  scope receipt, row remains open.** `MEASUREMENT` now names the existing dotted
  `MeasurementRootProducer.produce_from_catalog` owner, but the
  candidate/current-problem N8→N9 resolution is `bridge_missing`; pilot
  `EVAL_SAFETY` names `absent/unallocated` because the existing
  attempted-evaluation certificate expressly forbids promotion use; `EFFECT`
  is byte-identical by the 2026-08-30 ruling. The production census exits 0 and
  still reports `promoted=False consumer_promotable=False`; no real positive
  receipt or reconciled cross-gate counter exists, so the registered closure
  signal is unmet.

### `gy-n9-caller-asserted-gate-predicates`

- Verdict: `open`
- Deciding command/predicate: the exact high-value behavior selector above,
  especially the two caller-seam tests, the CG2 owner control, and the
  effective-independence nonreceipt test.
- Direct exit and decisive output: exit `0`, 12 parametrized cases passed.
  Both direct DTO and context injection reject the legacy Boolean fields; an
  actual open CG2 admissibility owner turns IDENTIFICATION red; missing
  effective independence emits a decisive `scope_insufficient` record owned by
  `absent/unallocated`, and the production refusal compositor consumes it.
- Exact append-only register prose: **Supersession 2026-08-31 — caller minting
  closed, positive capability still open.** Current v5 removes
  `admissibility` and `effective_independence` from the caller DTO and v3 owner
  projection, and both direct and context-supplied legacy `True` values are
  rejected. Admissibility reuses the content-bound CG2 resolver and an open CG2
  certificate turns IDENTIFICATION red. Effective independence now emits an
  explicit decisive `scope_insufficient` nonreceipt with
  `owner_ref=absent/unallocated`; because no candidate-bound persisted
  verifier-provenance producer exists, the row's two-producer acceptance signal
  remains unmet.

### `gy-n9-coupling-obligation-cannot-fail`

- Verdict: `open`
- Deciding command/predicate:
  `uv run python -m pytest 'tests/unit/runtime/quality/test_promotion_sequence.py::test_coupling_without_bound_n5_projection_is_scope_insufficient' -q --tb=short`.
- Direct exit and decisive output: exit `0`; both no blocker and the real N5
  spelling `unsupported_coupling_class:feedback` produce
  `COUPLING=scope_insufficient`, and the test asserts the production refusal
  compositor contains `coupling:scope_insufficient`.
- Exact append-only register prose: **Supersession 2026-08-31 — vacuous pass
  removed, typed bridge still open.** `_coupling_obligation` no longer grants on
  absence of the invented `n5_coupling_blocked` /
  `joint_obligation_inconsistency` strings. Until a verified typed
  `SimulationPortObservation.authority_blockers` projection reaches N9,
  COUPLING is `scope_insufficient`; both absence and the actual N5 blocker
  spelling production-refuse. The row remains `bridge_missing`: no fabricated
  token substitutes for its registered producer→consumer acceptance signal.

### `gy-n9-unmet-check-absence-kind-conflated`

- Verdict: `blocked`
- Deciding command/predicate: the exact production census plus the AST EFFECT
  byte-identity predicate above.
- Direct exit and decisive output: both exit `0`. MEASUREMENT now names a real
  dotted producer with `bridge_missing`; pilot EvalSafety names
  `absent/unallocated` with `producer_missing`; EFFECT remains exactly 948
  bytes at SHA-256
  `2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38`
  and therefore retains its prose owner.
- Exact append-only register prose: **Supersession 2026-08-31 — two absence
  kinds corrected, EFFECT portion remains blocked.** MEASUREMENT now identifies
  the existing dotted `MeasurementRootProducer.produce_from_catalog` and calls
  the missing link `bridge_missing`; pilot EvalSafety now records
  `absent/unallocated` / `producer_missing` because attempted-evaluation
  authority may not be reused for promotion. EFFECT is byte-identical under the
  principal's ruling, so its prose owner and the receipt-status distinction
  needed for an unallocated obligation cannot move here. Full row closure stays
  blocked on `gy-n9-effect-class-has-no-referent` and any resulting governed
  status/class decision.

### `GY-O0-NC-01`

- Verdict: `open`
- Deciding command/predicate: the exact production-lane obligation census
  above, composed with
  `git diff --exit-code 784d020148c56e9bfb3a3631909ba11232210a9f HEAD -- src/polisyos/runtime/quality/evaluation_safety.py`.
- Direct exit and decisive output: exit `0` / `0`; both standard and pilot
  receipts print `promoted=False consumer_promotable=False`; the standard
  refusal set still includes COUPLING, EFFECT, MEASUREMENT, and independence,
  while the pilot set adds EvalSafety. The safety-core file is unchanged.
- Exact append-only register prose: **Supersession 2026-08-31 — open; empirical
  receipt remains unavailable and the proposed single-EFFECT basis is not yet
  established.** The safety core is unchanged, but a real canonical production
  receipt remains `promoted=False consumer_promotable=False`. EFFECT remains a
  ruled, byte-identical conjunct; independently, the delivered census still
  finds the authority-grade N8→N9 measurement bridge missing, and the typed
  coupling/effective-independence inputs are fail-closed nonreceipts. No
  constructed or forged receipt was used. Re-run the registered cross-gate
  disagreement only after those bridge/producer states close and the EFFECT
  investigation terminates.

### Arithmetic

For the complete five-row task denominator:

`5 = 0 closed + 4 open + 1 blocked + 0 ambiguous`.

The four open rows are the scope-insufficient blocker, caller-asserted
predicates, coupling, and the empirical cross-gate receipt. The one blocked row
is absence-kind conflation, whose remaining EFFECT portion was explicitly
removed from this task by ruling.

## Patch/generalise line at hand-back

The lane ends on the **narrow-patch** side. Caller assertion and invented-token
coupling were two different properties, and the repository walk found no
second spelling of either property outside the scoped rows. Within each
property the repair is structural: both caller seams reject the removed fields,
and COUPLING cannot infer success from blocker-string absence. The newly found
generated-history registry gap is a receipt-consumer compatibility class, not
another owner-prose or token spelling; it is recorded open rather than used to
widen this lane across unowned generated companions.

## Named out-of-scope findings

- The governed N9 generated artifact is stale after the v5/v3/v2 bump, and the
  promotion, generation-cycle, second-domain, and depth-N checker registries do
  not admit the new v4-history comparison owner. Parser readability exists;
  generated-owner compatibility is `consumer_missing`/`surface_missing`.
- Architecture guardrails now reach clean JS generated checks after the frozen
  dependency install, but the trust-claim posture receipt is red because its
  complete `src/**/*.py` denominator includes the changed promotion source.
- The fully bound protected debt checker reports 18 blocking
  `closure_signal_identity_unresolvable` findings. Exact slice-base replay was
  not established, so P41 classifies their provenance `not_established`; the
  protected checker/register files were not edited.
- `evaluation_safety.py` and the shared HTTP dependency container are both
  byte-unchanged relative to the slice base; there are no shared-container
  lines to hand back.

## Round 2 — approved execution (2026-08-31)

Round 1's dossier above is retained as historical evidence and is superseded,
not rewritten. The architect approved resolve-and-bind orchestration through
the existing `producer_root_refs` and `value_blockers` fields, granted an
additive-only expansion to `generation_cycle.py`, and required every scoped row
to finish `closed` or concretely `blocked`.

### Initial branch and source freeze

```text
$ git status -sb
## codex/debt-a-promotion-gate
$ git rev-parse HEAD
002da58cf5981bc6db5c029bc66c0f17e5c79b1e
$ git merge-base HEAD main
784d020148c56e9bfb3a3631909ba11232210a9f
```

The tree was clean and attached. No Round-2 source change preceded this plan,
spec, and journal addendum.

### Complete producer/caller census

Command:

```bash
rg --files src -g '*.py' | wc -l
rg -n --glob '*.py' \
  'build_effective_independence_graph|annotate_pdc_graph_with_effective_independence|validate_effective_independence_graph_record' src
rg -n --glob '*.py' 'build_evidence_independence_map\(' src
rg -n --glob '*.py' 'MeasurementRootProducer\(' src
rg -n --glob '*.py' 'class MeasurementRootProducer|MeasurementRootProducer\.produce_from_catalog' src
rg -n --glob '*.py' 'n5_coupling_blocked' src
```

Direct exit: `0` for the positive searches; the final zero-match search exits
`1`. Decisive output over **2,611 Python files**:

- the independence graph symbols occur in their 1,668-line producer, two
  facade re-exports, and one feature-flagged call at
  `runtime/quality/evidence_independence.py:1054`;
- the enclosing `build_evidence_independence_map` has one non-definition source
  caller, a verification rebuild in `prompt_tool_ledger.py:1217`, and zero N9
  or production design-orchestration callers;
- `MeasurementRootProducer(` has one production caller at
  `runtime/quality/workspace/loop.py:1983`; its class is at
  `data_forge_binding.py:187`, and N9 already names its method;
- `n5_coupling_blocked` has zero source occurrences before the repair.

Finding labels: measurement is `bridge_missing`; independence is
`bridge_missing + implemented_but_not_orchestrated`. The graph implementation
is real, but a feature-flagged report construction and a verification rebuild
are not production N9 orchestration.

### Receipt-version ruling before code

Round 2 keeps `n9_promotion.v5 / n9_owner_projection.v3 /
n9_obligation_scope.v2`. The v2 epoch is provisional and was created for the
owner-truthfulness repair now being completed. Owner resolution is hashed and
will correctly rekey row, gate, and receipt identities; it does not change the
scope algorithm or current DTO shape.

The complete governed-artifact census found zero durable v5 receipts in 656
JSON/TOML/Markdown files; four files still contain v3 receipts. No published v5
authority is being silently changed. Before implementation, tests will pin
authentic Round-1 v5 bytes, require exact structural readback, and require
current owner replay to reject the stale receipt.

### Pattern bucket and generalisation line

Independence and measurement are two spellings of one newly measured property:
producer output is not promotion evidence until it is resolved, content-bound,
candidate/problem-bound, and verifier-provenance checked. P40 therefore moves
this round to the **generalise** side and one typed CAS bridge repository will
serve both. Coupling is a separate property—a typed negative classification
lost during projection—and remains an additive narrow bridge.

The absence-of-evidence residual is predeclared: a missing independence bridge
will refuse until a production design orchestrator invokes the graph producer;
a missing measurement bridge will refuse until the running workspace producer's
envelope is bound and carried to N9. Those are honest permanent refusals in any
path that omits orchestration, not a recurrence of caller minting.

### Pre-change refusal census

The executable four-cell output is appended immediately after the bound command
finishes. It reports both the full refusal set and the scope-insufficient subset
for data-only and field-pilot inputs under production and contract-testing
composition. The after-census uses the same fixture with only real producer
bridge refs added; together they decide whether GY-PR1's premise is restored or
disproved.

### Round 2 command ledger

| Evidence | Command | Exit | Decisive output |
| --- | --- | ---: | --- |
| attached starting point | `git status -sb && git rev-parse HEAD && git merge-base HEAD main` | 0 | attached clean branch; HEAD and merge base above |
| Python producer denominator | `rg --files src -g '*.py' \| wc -l` | 0 | 2,611 |
| independence caller census | exact `rg` commands above | 0 | producer plus feature-flagged report call; zero N9/production design orchestrators |
| measurement caller census | exact `rg` commands above | 0 | one production constructor in workspace loop |
| coupling-token preimage | `rg -n --glob '*.py' 'n5_coupling_blocked' src` | 1 | zero matches |

### Round 2 dossier staging

The final append supplies five superseding blocks, `5 = closed + blocked`, the
before/after refusal table, the two differently labelled bridges, the
absence-of-evidence finding, exact touched-field consumers and E/D adjacent
tests, the v5 history proof, EFFECT bytes/hash, and both carried-red states.

### Pre-change four-cell result

Command: a bound `.venv/bin/python` predicate loaded the committed Round-1
promotion fixtures, ran data-only and field-pilot receipts once each, and
composed the same obligations with
`allow_non_authoritative_contract_scope_gaps=False/True`. Direct exit: `0`.

| Design class | Production: full / scope refusals | Contract testing: full / scope refusals |
| --- | --- | --- |
| data-only | `6 / 4` — COUPLING, EFFECT, MEASUREMENT, and independence are the four scope gaps; CALIBRATION and DATA are separate ledger refusals | `2 / 0` — CALIBRATION and DATA only |
| field-pilot | `7 / 5` — the data-only set plus EVAL_SAFETY | `2 / 0` — CALIBRATION and DATA only |

Exact decisive output:

```text
CLASS=data_only
  LANE=production COUNT=6 SCOPE_COUNT=4 REASONS=coupling:scope_insufficient|effect:scope_insufficient|calibration:single_obligation_fail|measurement:scope_insufficient|data:single_obligation_fail|data:scope_insufficient
  LANE=contract_testing COUNT=2 SCOPE_COUNT=0 REASONS=calibration:single_obligation_fail|data:single_obligation_fail
CLASS=field_pilot
  LANE=production COUNT=7 SCOPE_COUNT=5 REASONS=coupling:scope_insufficient|effect:scope_insufficient|calibration:single_obligation_fail|measurement:scope_insufficient|data:single_obligation_fail|eval_safety:scope_insufficient|data:scope_insufficient
  LANE=contract_testing COUNT=2 SCOPE_COUNT=0 REASONS=calibration:single_obligation_fail|data:single_obligation_fail
```

The after table will preserve both measures. The scope subset decides the
plan correction; the full set prevents unrelated N11 fixture refusals from
being silently laundered out of the measurement.

### Round 2 red-first receipt

Exact selector:

```bash
uv run python -m pytest -q --tb=short \
  tests/unit/runtime/quality/test_generation_cycle.py::test_real_unsupported_n5_result_is_serialized_as_simulation_blocked \
  tests/unit/runtime/quality/test_generation_cycle.py::test_n5_coupling_blocker_survives_selected_summary_projection \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_real_dependent_independence_graph_refuses_legacy_true \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9 \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_n5_coupling_blocker_refuses_coupling \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_supported_n5_coupling_path_satisfies_coupling
```

Direct exit: `1`; decisive output: `6 failed`. Each failed on its intended
missing property:

- the real unsupported N5 result lacked `n5_coupling_blocked`;
- `_summary_with_value_observation` rejected the new `simulation` bridge input;
- the independence and measurement tests found no
  `N9PromotionEvidenceBridgeRepository`;
- N9 returned `scope_insufficient` instead of FAILED for the blocker and
  instead of SATISFIED for the adjacent supported path.

The history fixture separately pins authentic Round-1 v5/v3/v2 bytes: 48,568
UTF-8 bytes, SHA-256
`dba4a1ab7f374ea04044b171b0e163c6b0b1390089197fc64f96c2f0e86983c9`,
compressed only for embedding in the owned unit test. Its red condition is
exact structural round-trip followed by a non-empty live-owner validation
issue set; before owner outcomes change, that final assertion is false.

## Round 2 — final execution and superseding findings

Round 2 terminates the five-row denominator as:

`5 = 3 closed + 2 blocked`.

No row is `open`. The three closures are measured producer/bridge properties;
neither blocked row is being used as a difficulty or budget label.

### Before/after refusal table and the GY-PR1 correction

The same fixture was measured with full refusal reasons and with only
`scope_insufficient` reasons. Counts are written `full / scope`; CALIBRATION
and DATA are the two N11 fixture controls in every full set and are not counted
as scope gaps.

| Design class | Lane semantics | Before bridges: full / scope | After bridges: full / scope |
| --- | --- | ---: | ---: |
| data-only | production | `6 / 4` | `3 / 1` |
| data-only | contract testing | `2 / 0` | `2 / 0` |
| field-pilot | production | `7 / 5` | `4 / 2` |
| field-pilot | contract testing | `2 / 0` | `2 / 0` |

The exact after output was:

```text
AFTER CLASS=data_only PRODUCTION=3/1 CONTRACT=2/0 PRODUCTION_REASONS=effect:scope_insufficient|calibration:single_obligation_fail|data:single_obligation_fail CONTRACT_REASONS=calibration:single_obligation_fail|data:single_obligation_fail
AFTER CLASS=field_pilot PRODUCTION=4/2 CONTRACT=2/0 PRODUCTION_REASONS=effect:scope_insufficient|calibration:single_obligation_fail|data:single_obligation_fail|eval_safety:scope_insufficient CONTRACT_REASONS=calibration:single_obligation_fail|data:single_obligation_fail
```

Named plan finding — **GY-PR1's Done-when is mis-specified**. Before the
Round-1 minting repair, the data-only production scope count was two: EFFECT
and MEASUREMENT. Removing the vacuous independence and coupling passes made the
pre-Round-2 count four. That `2 -> 4` delta is the repair working: two lies
became honest absence-of-evidence refusals. The text “repair the vacuous passes
and only EFFECT remains” incorrectly combines minting repair with three
separate producer handshakes. After those handshakes, data-only really does
have only EFFECT left; field-pilot separately retains the promotion-authority
EvalSafety nonreceipt. In the data-only denominator, EFFECT is the only one of
the four pre-bridge gaps with no producer semantics at all.

### Resolve-and-bind bridge results

The shared bridge is a strict CAS record carried by existing
`producer_root_refs`; the resolver is an orchestration dependency and never a
serialized caller predicate. It verifies exact bridge bytes and manifest,
fixed verifier provenance, candidate id and content hash, design-problem id,
hash and rule version, and then source-specifically recomputes the producer
result. Missing, duplicate, malformed, foreign-candidate, foreign-problem,
wrong-provenance, or drifted evidence returns
`evidence_not_established`. The adversarial test also proves an empty
independence graph refuses as `no_support_evidence`.

The two producer labels remain deliberately asymmetric:

- Effective independence is `bridge_missing +
  implemented_but_not_orchestrated`. The existing report caller is guarded by
  `policy_design_case.graded_independence_weights`; its other caller is a
  verification rebuild. Neither invokes the N9 bridge writer on the production
  design path. The new bridge calls the public evidence facade, persists exact
  graph inputs/output, reruns `build_effective_independence_graph`, and reruns
  `validate_effective_independence_graph_record` before N9 can consume it.
- Measurement is `bridge_missing`. `MeasurementRootProducer` is already
  constructed by `workspace/loop.py`; the bridge resolves that producer's
  authority-linked CAS payload, reconstructs its MeasurementRoot projection,
  and candidate/problem-binds it. Production still must pass the running
  producer's envelope through `persist_measurement_root` and carry the returned
  ref.

Absence-of-evidence finding: a normal production path that invokes neither
bridge writer now refuses independence and measurement for lack of resolved
evidence, not for lack of semantics. Independence needs the production design
orchestrator to invoke its graph bridge; measurement needs the workspace loop's
existing envelope passed to its binding bridge. This can keep production
non-promotable, but it cannot mint. Field-pilot also refuses until a distinct
promotion-authoritative EvalSafety producer exists; the attempted-evaluation
certificate expressly cannot be reused for promotion.

### Additive generation-cycle diff and exact consumers

The Round-2 diff against `002da58cf` is additive in the approved sense:

- lines 261-262 append `n5_coupling_blocked` only when the real N5
  `feedback_classification.support_status` is `unsupported`; existing specific
  blockers and control flow remain;
- line 3457 passes the already-produced `SimulationPortObservation` to the
  selected-summary projection; lines 5673-5682 union only that typed token into
  existing `value_blockers` without changing the return shape;
- lines 2463-2467 and 2591 carry the N9 owner-store resolver already exposed by
  the promotion port into decision-front replay; lines 6046-6099 only thread
  that dependency.

A complete AST/text census over **2,611 `src/**/*.py` files** found:

```text
_joint_simulation_port_outcome: 1 definition + 1 production call
_summary_with_value_observation: 1 definition + 1 production call
_apply_promotion_to_summaries: 1 definition + 1 production call
_promotion_receipt_allows_decision_front: 1 definition + 1 production call
n5_coupling_blocked: 3 source occurrences (emit, carry, consume)
```

The exact consumers are therefore: `JointSimulationPort` reads the real N5
classification and creates `SimulationPortObservation.authority_blockers`;
`GenerationCycleController._revise_node` reads that observation and carries the
one typed token into `CandidateSummary.value_blockers`; `_coupling_obligation`
reads the token and refuses; controller decision-front replay reads the
promotion port's owner-store resolver. There is no sibling source consumer of
the token.

The E- and D-adjacent blast command selected one behavioral node for each
named consumer boundary:

```bash
uv run pytest -q --tb=short \
  tests/unit/runtime/quality/test_acquisition_planner.py::test_generation_cycle_bootstrap_authority_is_strangled \
  tests/unit/runtime/quality/test_acquisition_route_loop.py::test_route_closure_rejects_complete_before_terminal_then_ignores_newer_job \
  tests/unit/runtime/http/test_governed_projection_service.py::test_acquisition_growth_is_one_content_bound_composite_projection \
  tests/unit/runtime/http/test_workspace_loop_transition.py::test_workflow_transition_uses_injected_catalog_and_persists_measurement_payload
```

Direct exit `0`; decisive output: `4 passed`. The first two exercise E's
generation/acquisition model consumers, the third exercises E's governed
projection consumer, and the fourth exercises D-adjacent `run_lifecycle`
through the real workspace measurement transition.

Both producer modules are byte-unchanged relative to the slice base.
`evaluation_safety.py` and `runtime/http/dependencies.py` are also unchanged;
there are zero shared-container lines to hand back.

### Receipt-version ruling and history proof

The epoch remains `n9_promotion.v5 / n9_owner_projection.v3 /
n9_obligation_scope.v2`. Owner resolution is exactly the semantic repair v2
introduced on this still-unmerged branch; it rekeys hashed obligation rows and
the gate receipt without changing owner-projection shape or the scope-hash
algorithm. A `.v3` bump would incorrectly freeze a provisional intermediate
state.

The complete governed-artifact denominator is the 656 JSON/TOML/Markdown files
under `architecture/`: zero contain a durable v5 receipt and four contain v3.
The history test embeds authentic pre-Round-2 v5/v3/v2 bytes, requires exact
48,568-byte readback and SHA-256
`dba4a1ab7f374ea04044b171b0e163c6b0b1390089197fc64f96c2f0e86983c9`,
round-trips the parsed model to identical bytes, and then proves current owner
authority rejects it with exactly:

```text
decisive_obligation_omitted
unexpected_decisive_obligation_instance
```

The targeted history/replay selector exited `0` with `7 passed`. This is
structural history readability plus current-authority rejection, not a silent
restamp.

### Final command ledger

| Evidence | Exact command/predicate | Exit | Decisive output |
| --- | --- | ---: | --- |
| closure selector | `uv run pytest -q --tb=short` over the current-input legacy predicate, CG2-open, real dependent independence, two real N5 transport, N9 coupling refusal, and supported coupling nodes | 0 | 8 parametrized cases passed |
| post-bridge table | `uv run pytest -q -s --tb=short tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9` | 0 | data-only `3/1`, `2/0`; field-pilot `4/2`, `2/0` |
| resolver adversaries | exact dependent, empty, and foreign-candidate/wrong-verifier nodes | 0 | 3 passed; producer negative refuses and malformed authority never establishes |
| N9 replay/port blast | exact seven-node history, deterministic obligation, adaptive-port, comparison, and decision-front selector | 0 | 7 passed |
| E/D adjacency | exact four-node command above | 0 | 4 passed |
| Ruff | `uv run python -m ruff check` on the two owned source and two owned test files | 0 | `All checks passed!` |
| EFFECT integrity | AST extracts `_effect_obligation` from slice base and current source, then compares bytes and SHA-256 | 0 | 948 / 948 bytes; both `2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38`; identical |
| excluded files | base-to-HEAD `git diff --exit-code` for EvalSafety, dependencies, and both read-only producer modules | 0 | no diff |
| promotion generated companion | `JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers --extra test python tools/quality/validation/check_layer3_gy_promotion_contract.py --check --output-format json` | 1 | carried `promotion_comparison_admission_manifest_drift`; not regenerated or silenced |
| architecture guardrails | `uv run polisyos-tools architecture guardrails check` | 1 | API generated outputs clean; only the carried stale trust-claim posture receipt remains after the temporary deep-import finding was fixed through the public evidence facade |
| debt checker | `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` | 1 | exactly 18 blocking `closure_signal_identity_unresolvable` findings |
| docs lifecycle | `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` | 1 | exactly 6 baseline findings |

### Patch/generalise ruling

Round 2 ends on the **generalise** side for producer evidence. Independence and
measurement were the second spelling of one property, so one resolve,
content-bind, candidate/problem-bind, verifier-provenance mechanism serves
both. Coupling stays a narrow typed-negative patch because it is a different
property and has exactly one emitter, carrier, and consumer. No further owner
string or token spelling was enumerated.

## Register closure dossier — Round 2 supersession

The prose below is append-only. It supersedes the retained Round-1 blocks and
does not authorize edits to the protected register in this lane.

### `gy-n9-caller-asserted-gate-predicates`

- Verdict: `closed`.
- Deciding command: the final closure selector in the command ledger, including
  `test_current_input_rejects_legacy_caller_gate_predicates`,
  `test_cg2_open_admissibility_obligation_keeps_promotion_red`, and
  `test_real_dependent_independence_graph_refuses_legacy_true`.
- Direct exit and decisive output: exit `0`; `8 passed` across the selector.
  Direct legacy `True` is rejected, real open CG2 evidence refuses, and a real
  dependent graph refuses through the resolved dotted producer despite the
  former caller assertion.
- Exact append-only register prose: **Supersession 2026-08-31 — closed by
  resolved owner evidence.** Current v5 has no caller Boolean for admissibility
  or effective independence. Admissibility is recomputed through the
  content-bound CG2 resolver, and an open CG2 obligation refuses.
  `N9PromotionEvidenceBridgeRepository` invokes the real effective-independence
  graph producer, persists and exactly replays its inputs/output, binds
  candidate and design problem plus fixed verifier provenance, and makes a
  hard-collapse dependency fail N9 even against the rejected legacy
  `effective_independence=True` shape. Missing or unresolvable bridge evidence
  remains an honest `evidence_not_established` refusal.

### `gy-n9-coupling-obligation-cannot-fail`

- Verdict: `closed`.
- Deciding command: the final closure selector's two N5 transport nodes plus
  `test_n5_coupling_blocker_refuses_coupling` and
  `test_supported_n5_coupling_path_satisfies_coupling`.
- Direct exit and decisive output: exit `0`; the same `8 passed` selector proves
  the real unsupported result emits `n5_coupling_blocked`, the selected summary
  retains it, COUPLING is `failed`, and the adjacent real supported path is
  `satisfied`.
- Exact append-only register prose: **Supersession 2026-08-31 — closed by the
  additive N5-to-N9 bridge.** The existing joint-simulation producer now
  appends typed `n5_coupling_blocked` only when its content-bound support
  classification is `unsupported`; it preserves all specific blockers and
  existing control flow. The selected-summary projection carries only that
  token into `value_blockers`, and N9 COUPLING refuses it. A red-first real N5
  fixture and adjacent supported control both pass after the bridge; no token
  was fabricated by a test or inferred from string absence—the bridge derives
  it from the real producer classification.

### `gy-promotion-obligations-scope-insufficient`

- Verdict: `closed`.
- Deciding command:
  `uv run pytest -q -s --tb=short tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9`.
- Direct exit and decisive output: exit `0`; the real authority-linked
  MeasurementRoot is independently replayed and MEASUREMENT is `satisfied`.
  After both producer bridges, data-only production is `3 / 1` full/scope and
  contract testing is `2 / 0`; the one data-only scope refusal is EFFECT, which
  is governed by the separately deferred investigation.
- Exact append-only register prose: **Supersession 2026-08-31 — closed for the
  executable scope; only the separately ruled EFFECT investigation remains.**
  N9 now reads the exact CAS payload and authority links emitted by the running
  `MeasurementRootProducer`, verifies its manifest, applicable source contract,
  connector fallback, MeasurementRoot projection, candidate/problem binding,
  and fixed verifier provenance before satisfying MEASUREMENT. Independence
  and coupling likewise have real refusal paths. The production data-only
  scope set falls from four honest pre-bridge gaps to EFFECT alone; no marker
  or caller assertion passes. Field-pilot separately exposes the existing
  promotion-authority EvalSafety nonreceipt.

### `GY-O0-NC-01`

- Verdict: `blocked`.
- `blocked_by: gy-n9-effect-class-has-no-referent` under the principal's
  ruling dated 2026-08-30.
- Deciding command/predicate: the post-bridge four-cell test composed with the
  EFFECT AST byte/hash predicate.
- Direct exit and decisive output: both exit `0`; data-only has only
  `effect:scope_insufficient`, field-pilot has EFFECT plus
  `eval_safety:scope_insufficient`, and EFFECT remains exactly 948 bytes at
  SHA-256
  `2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38`.
  No `consumer_promotable=True` receipt exists.
- Exact append-only register prose: **Supersession 2026-08-31 — blocked by
  `gy-n9-effect-class-has-no-referent`, principal ruling 2026-08-30.** The
  engineering bridges now reduce the data-only production scope set to the
  byte-identical EFFECT conjunct, so a first governed promotable receipt cannot
  execute until that scoped investigation terminates. The registered
  field-pilot disagreement signal additionally requires an appointed,
  candidate/problem-bound promotion-authority EvalSafety producer; the existing
  attempted-evaluation certificate forbids promotion use. No forged or
  contract-testing receipt is admissible closure evidence.

### `gy-n9-unmet-check-absence-kind-conflated`

- Verdict: `blocked`.
- `blocked_by: gy-n9-effect-class-has-no-referent` and the governed
  status/class decision that investigation may require.
- Deciding command/predicate: the producer/caller census, post-bridge table, and
  byte-identical EFFECT predicate.
- Direct exit and decisive output: exits `0`; measurement is
  `bridge_missing` against one running production constructor; independence is
  `bridge_missing + implemented_but_not_orchestrated` under
  `policy_design_case.graded_independence_weights`; both now use resolved dotted
  owners and `evidence_not_established`. EFFECT alone retains its ruled prose
  owner and unchanged bytes.
- Exact append-only register prose: **Supersession 2026-08-31 — blocked only on
  the ruled EFFECT absence-kind decision.** The shared resolver now
  distinguishes the running MeasurementRoot producer's missing promotion
  binding from the feature-flagged independence calculus that is implemented
  but not production-orchestrated. Both resolve to dotted producer owners when
  evidence exists and otherwise emit `evidence_not_established`; COUPLING now
  resolves through its real N5 classification. EFFECT remains byte-identical
  by ruling, so deciding its referent and any required status/class vocabulary
  must land through `gy-n9-effect-class-has-no-referent` before this row can
  close.

## Round 3 — Phase 1: EFFECT specification archaeology (2026-08-31)

Phase 1 is a reading-only boundary. At entry the branch was
`codex/debt-a-promotion-gate` at `b53da2192`, clean and 12 commits ahead. No
source file changed during the investigation. Phase 2 did not begin before
this ruling, plan, specification, and journal were written.

### Intake discrepancy and architect ownership question

The prompt identifies a Wave-2 Group-A row named `GY-N9-EFFECT-REFERENT`.
Against the exact entry revision, this complete census is decisive:

```bash
base=b53da21925c38d644d414a2419bff89a8162c05e
git ls-tree -r --name-only "$base" | wc -l
git ls-tree -r --name-only "$base" | awk '/^docs\/.*\.md$/ {n++} END {print n+0}'
git grep -n 'GY-N9-EFFECT-REFERENT' "$base" -- .
git grep -n 'gy-n9-effect-class-has-no-referent' "$base" -- \
  docs/plans/active/DEBT-REGISTER.md
```

The denominator is 10,371 tracked files below `policy-engine/`, including
1,133 tracked Markdown files below `policy-engine/docs/`. The exact alias
search exits `1` with zero;
the existing row search exits `0` at register line 314. The visible row carries
the same question, evidence exclusions, and three outcomes, so it is the Phase
1 authority available to this lane.

**Ownership question to the architect:** land or identify the promised
`GY-N9-EFFECT-REFERENT` Wave-2 Group-A alias in
`docs/research/policy-operations-and-real-world-runtime-backlog.md`, binding it
to the existing `gy-n9-effect-class-has-no-referent` investigation. This lane
cannot create that architect-owned research row. The absent alias does not
block the archaeology because the existing register row supplies the complete
execution contract.

### Historical separating evidence

The first-revision search found one common introduction:

```bash
git log --all --reverse --format='%H %cs' \
  -S'entailment / grounding (GY-K)' -- \
  docs/plans/active/layer3-slices/GY-engine-subordination.md
git grep -n -F 'entailment / grounding (GY-K)' 584bd7b72^ -- \
  docs/plans/active/layer3-slices/GY-engine-subordination.md
git grep -n -F 'Effect obligations:' 584bd7b72^ -- \
  docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md
git grep -n -F 'entailment / grounding (GY-K)' 584bd7b72 -- \
  docs/plans/active/layer3-slices/GY-engine-subordination.md
git grep -n -F 'Effect obligations:' 584bd7b72 -- \
  docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md
```

Decisive output is commit
`584bd7b72deb74694db87f4612176be0cb78724f`, dated 2026-06-28, with exits
`parent_phrase=1`, `parent_effect=1`, `introduced_phrase=0`, and
`introduced_effect=0`. That commit introduced all of the following together:

- GY-N9 requires “producer roots, entailment / grounding (GY-K), calibration +
  transport, effective independence, admissibility” and immediately defines
  its full obligations compiler as including separate `effect` and
  `identification` members.
- RACE §12.2 enumerates distinct `O_effect(x)` and `O_id(x)`. Section 12.3 makes
  EFFECT map the declared epsilon to the estimand, require a causal path or
  mechanism, and require the effect claim to be entailed, bounded, or marked
  ungrounded. IDENTIFICATION instead specifies point/partial/proxy/blocked
  status, explicit assumptions, stored proof, and risk spend.
- The PolicyOS adoption decision §4 binds GY-N9 to the full `O(x)` taxonomy.

The status-vector counter-reading fails against the same specification. RACE
§6.1 has `z_adm`, `z_ground`, and per-objective `z_id`, but §6.2 says
`grounded` means every active grounding obligation is satisfied; §12.4 defines
that state as the intersection over `O_ground(x)`; and §12.5 separately
requires grounding obligations and identification certificates. The vector is
an aggregate status projection, not the obligation denominator. Using the
missing `z_effect` as the class test was a P38 proxy error.

The CGF history sharpens, rather than collapses, this distinction:

```bash
git log --all --reverse --format='%H %cs %s' -- \
  docs/system-design-decisions/policy-design-causal-grounding-firewall.md
```

Its first revision is `115536dbaa04470dcccdbb7badb2d0d532e5a65c`, dated
2026-07-05—after the obligations taxonomy. The binding decision calls CGF the
typed grounding/linker layer, says GY-K is a per-axis entailment witness “never
the decider,” and defines CG0-CG6 as reference audit, typed relation/joint
solver, conservative bind, free-grow admission, phrasing defense, active
grounding, and benchmark. Crediting current IDENTIFICATION with CGF/CG2 thus
does not consume the already-separate `O_effect` predicate.

Current code history only corroborates the ruling: the first N9 implementation
created distinct EFFECT and IDENTIFICATION rows, then the marker-only GY-K pass
was removed while CG2 remained in IDENTIFICATION. Code shape did not decide the
spec question.

### Phase-1 ruling

**Outcome 3: EFFECT was specified as a distinct seventh check.** It remains a
class, and a later governed slice must give it the RACE `O_effect` referent and
evaluator. It is not an early name absorbed by IDENTIFICATION and is not the
missing ADMISSIBILITY enum slot.

The evaluator must resolve and content-bind a fixed-provenance producer
artifact to the candidate, problem, estimand, and rule epoch, then independently
recompute: declared effect claim/epsilon maps to the estimand; the applicable
causal path or mechanism is grounded; and the effect is entailed or bounded.
Explicitly ungrounded is a decisive negative. Missing, malformed, foreign,
stale, or self-attested evidence is `evidence_not_established`. GY-K is a
witness input, never sufficient evidence on its own. No producer or evaluator
is invented in this phase.

### Governed version consequence

The v2 design explicitly deferred EFFECT interpretation. Landing this new
semantic evaluator therefore requires:

- `n9_obligation_scope.v2 -> .v3`;
- `n9_promotion.v5 -> .v6`, retaining v5/v3/v2 receipt bytes as readable,
  non-current history;
- `n9_evidence_bridge.v1 -> .v2` if its strict union gains an effect-evidence
  kind, retaining v1 readback;
- no owner-projection bump when using existing `producer_root_refs`, so
  `n9_owner_projection.v3` remains the selected shape.

Phase 2's two existing writer calls remain within v5/v3/v2 and do not enact
this future version change.

### Phase-1 integrity receipts

```text
EFFECT AST bytes: 948
EFFECT SHA-256: 2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38
base-to-working-tree source diff: exit 0
```

The diff predicate covered `promotion_sequence.py`, `evaluation_safety.py`,
`generation_cycle.py`, and `runtime/http/dependencies.py`. All were unchanged
in Phase 1.

The bound documentation lifecycle guard was also replayed before the Phase-1
commit:

```bash
PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py
```

It exits `1` with exactly the six inherited findings: two `LEDGER.md`
front-matter findings and four removed-stub-reference findings. The Phase-1
documents add no seventh finding.

## Register closure dossier — Round 3 Phase-1 supersession

These three blocks supersede the retained Round-2 verdict text. The exact row
signals—not partial mechanism completion—decide the verdicts.

### `gy-promotion-obligations-scope-insufficient`

- Verdict: `blocked`.
- `blocked_by:` the governed RACE `O_effect` producer, evaluator, and
  `n9_obligation_scope.v3` / `n9_promotion.v6` rule epoch specified by the
  outcome-3 ruling. The field-pilot half additionally retains the separately
  measured promotion-authority EvalSafety producer gap.
- Deciding predicate: the accepted Round-2 four-cell production measurement
  plus the Phase-1 historical ruling and EFFECT byte predicate.
- Direct exits and decisive output: four-cell test exit `0`, with both real
  production receipts `promoted=False`; history searches exit
  `1,1,0,0` parent/introduced and prove separate `O_effect`/`O_id`; integrity
  exit `0`, 948 bytes at the frozen hash. MEASUREMENT is built and resolves,
  but the row's exact `consumer_promotable=True` signal is not met.
- Exact append-only register prose: **Supersession 2026-08-31 — blocked with
  the engineering mechanism built.** The measurement-rooted producer now
  resolves through exact CAS evidence and can reach a decisive N9 outcome, but
  this row's recorded closure signal is the exact real production
  `consumer_promotable=True` GY-O0 receipt, not repair of one conjunct.
  Specification history rules EFFECT a distinct RACE `O_effect` obligation:
  declared effect-to-estimand binding, grounded causal path or mechanism, and
  entailed/bounded/explicitly-ungrounded disposition. That producer/evaluator
  and the governed v3/v6 epoch must land before the signal is executable; the
  field-pilot witness also retains the promotion-authority EvalSafety producer
  nonreceipt.

### `GY-O0-NC-01`

- Verdict: `blocked`.
- `blocked_by:` the governed RACE `O_effect` producer/evaluator and v3/v6 rule
  epoch established by this ruling; the field-pilot signal also requires the
  already-named candidate/problem-bound promotion-authority EvalSafety
  producer.
- Deciding predicate: the accepted four-cell table shows no real production
  promotable receipt; the historical parent/introduced comparison proves
  EFFECT is an unimplemented distinct conjunct rather than an alias; EFFECT
  remains byte-identical.
- Direct exits and decisive output: four-cell test `0` with
  `promoted=False` for data-only and field-pilot production; history comparison
  `1,1,0,0`; integrity `0`, 948 bytes and the frozen SHA-256.
- Exact append-only register prose: **Supersession 2026-08-31 — blocked by the
  distinct RACE `O_effect` capability ruled from specification history.** The
  first GY-N9/RACE adoption revision introduced separate effect and
  identification obligations; the later CGF decision makes GY-K a per-axis
  witness, never the decider. A real `O_effect` producer/evaluator and governed
  v3/v6 rule epoch must land before any production `consumer_promotable=True`
  receipt can exist. The field-pilot disagreement witness additionally retains
  the promotion-authority EvalSafety producer nonreceipt. GY-O0's closed safety
  core and hash remain untouched.

### `gy-n9-unmet-check-absence-kind-conflated`

- Verdict: `blocked`.
- `blocked_by:` the same governed RACE `O_effect` producer/evaluator artifact
  and v3/v6 rule epoch.
- Deciding predicate: specification history now assigns EFFECT exact semantics
  but the complete admitted chain remains absent; the byte-identical current
  function still has no design-discriminating evidence input.
- Direct exits and decisive output: history comparison `1,1,0,0` and visible
  row search `0`; source-integrity predicate `0`, with unchanged 948-byte
  EFFECT. The ruling terminates semantic ambiguity but does not fabricate a
  producer.
- Exact append-only register prose: **Supersession 2026-08-31 — the semantic
  ambiguity is closed; execution remains blocked on the distinct `O_effect`
  capability.** Specification history proves EFFECT and IDENTIFICATION were
  separately adopted, and proves GY-K is only a grounding witness. EFFECT is
  therefore `producer_missing + artifact_missing + bridge_missing +
  consumer_evaluator_missing`, not `scope_insufficient` and not
  absent/unallocated semantics. A content-bound, candidate/problem/estimand/
  epoch-bound evaluator under `n9_obligation_scope.v3` must land before this
  row's absence kinds are truthfully represented end to end.

## Round 3 — Phase 2: production writer orchestration

Phase 2 began only after commit `e0239f3c9` recorded and froze the Phase-1
ruling. The two source capabilities remained deliberately distinct:

- effective independence entered as `bridge_missing +
  implemented_but_not_orchestrated`. Its only non-N9 report-builder route is
  guarded by `policy_design_case.graded_independence_weights`; the N9 writer
  itself invokes the complete producer and does not treat that report route as
  promotion evidence;
- measurement entered as `bridge_missing` only. The real
  `MeasurementRootProducer` is already constructed and invoked by
  `workspace/loop.py`; N9 needed to bind its returned envelope, not build a
  second producer.

### Red-first boundary

The two integration witnesses exercise `CanonicalN9PromotionPort` with a real
container-owned `PromotionRuntime`, a sealed positive epoch admission, and the
real producer inputs. Each validates the emitted receipt again through the
owner resolvers. Before source changed, this exact command exited `1`:

```bash
uv run pytest -q --tb=short \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_production_n9_port_persists_and_consumes_dependent_independence_evidence \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_production_n9_port_persists_and_consumes_measurement_root_evidence
```

Decisive red output was two assertion failures: independence was
`scope_insufficient` instead of `failed`, and MEASUREMENT was
`scope_insufficient` instead of `satisfied`. These are the two absent writer
calls, not fixture or collection errors.

The minimal production repair is `_bind_production_promotion_evidence` inside
the canonical N9 batch. It runs only after the exact candidate/problem input
exists, strict-validates producer-specific context, invokes the existing
repository writers, and carries only returned CAS refs. Invalid or absent
source input is caught at that boundary and produces no ref, so the existing
reader returns `evidence_not_established`; no exception or caller predicate can
become a positive.

The same two-node command was then rerun with an explicit exit capture. It
exited `0` and printed two passing dots plus `writer_witness_exit=0`.
Independence reached `failed` with `dependent_evidence_collapsed`; measurement
reached `satisfied` and carried the real producer payload ref. Both complete
receipts passed current owner replay with the same resolver.

### Source caller census

```bash
git grep -n '\.persist_effective_independence(' -- src/
git grep -n '\.persist_measurement_root(' -- src/
```

Both commands exit `0`. Each returns exactly one non-test caller, in
`promotion_sequence.py` inside `_bind_production_promotion_evidence`. The
repository method definitions are not counted by this call-pattern census.
`generation_cycle.py`, both read-only producer modules, `evaluation_safety.py`,
and `runtime/http/dependencies.py` have zero Round-3 Phase-2 lines changed.

Ruff over the owned source and test files exits `0` with `All checks passed!`.

## Register closure dossier — Round 3 Phase-2 writer rows

### `gy-n9-independence-evidence-writer-unorchestrated`

- Verdict: `closed`.
- Deciding command: the two-node writer witness above plus
  `git grep -n '\.persist_effective_independence(' -- src/`.
- Direct exits and decisive output: pytest red `1` with
  `scope_insufficient != failed`, then green `0`; the final receipt contains
  one `N9EffectiveIndependenceBridge`, the independently recomputed obligation
  is `failed` with `dependent_evidence_collapsed`, and full owner replay has no
  issues. Grep exits `0` with the production caller in
  `_bind_production_promotion_evidence`.
- Exact append-only register prose: **Supersession 2026-08-31 — closed by the
  production N9 writer path.** Effective independence remains distinct from
  the feature-flagged report-builder route
  `policy_design_case.graded_independence_weights`. The canonical production
  batch now strict-validates producer inputs after candidate/problem binding,
  invokes `persist_effective_independence`, carries only its CAS bridge ref,
  and immediately resolves and recomputes the real graph under fixed verifier
  provenance. A red-first dependent graph moved from
  `evidence_not_established` to decisive `dependent_evidence_collapsed`; the
  complete receipt replays cleanly, while absent or malformed evidence still
  refuses.

### `gy-n9-measurement-evidence-writer-unorchestrated`

- Verdict: `closed`.
- Deciding command: the two-node writer witness above plus
  `git grep -n '\.persist_measurement_root(' -- src/`.
- Direct exits and decisive output: pytest red `1` with
  `scope_insufficient != satisfied`, then green `0`; the final receipt
  contains one `N9MeasurementRootBridge`, MEASUREMENT is `satisfied`, the real
  producer payload ref is evidence, and full owner replay has no issues. Grep
  exits `0` with the production caller in
  `_bind_production_promotion_evidence`.
- Exact append-only register prose: **Supersession 2026-08-31 — closed by the
  running MeasurementRoot-to-N9 writer path.** The production batch accepts
  only the full real `MeasurementRootProducer` envelope, validates its source
  and authority CAS chain through `persist_measurement_root`, binds it to the
  exact candidate and design problem, carries only the returned bridge ref,
  and independently replays it before MEASUREMENT can satisfy. The red-first
  integration witness moved from `evidence_not_established` to a decisive
  satisfied outcome and the current receipt replays cleanly. Missing,
  malformed, or foreign evidence remains an honest refusal.

## Round 3 final freeze and consolidated dossier

The source freeze is commit `a11a91a7e9972933063354e84cf1e665ae9abba8`.
Relative to the Round-3 entry `b53da2192`, only
`promotion_sequence.py`, its owned unit test, and the three lane documents
change. `generation_cycle.py` has zero Round-3 lines: the accepted Round-2
additive emit/carry/consume path remains untouched. `evaluation_safety.py`,
`runtime/http/dependencies.py`, and all three read-only producer modules also
have zero Round-3 lines.

### Targeted source verification

The post-implementation blast selector was:

```bash
uv run pytest -q --tb=short \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_production_n9_port_persists_and_consumes_dependent_independence_evidence \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_production_n9_port_persists_and_consumes_measurement_root_evidence \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_real_dependent_independence_graph_refuses_legacy_true \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_empty_independence_graph_cannot_establish_promotion_evidence \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_foreign_candidate_and_wrong_verifier_provenance_fail_closed \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9 \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_effective_independence_missing_is_explicit_decisive_nonreceipt \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_invented_measurement_marker_does_not_supply_authority \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_n9_port_rebinds_every_adaptive_receipt_to_one_final_ledger_head \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_context_cannot_supply_open_world_gate \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_promotion_context_cannot_supply_legacy_gate_predicate \
  tests/unit/runtime/quality/test_promotion_sequence.py::test_round1_v5_v2_receipt_round_trips_but_cannot_regain_current_authority \
  tests/unit/runtime/quality/test_generation_cycle.py::test_every_promotion_input_is_preceded_by_produce_persist_and_fresh_resolve
```

It exits `0`: fourteen cases pass, including the two parametrizations of the
legacy-predicate test. This one selector covers both real producer outcomes,
missing/malformed/foreign evidence, caller-predicate rejection, adaptive
receipt replay, the generation-cycle ordering witness, and authentic v5
history readback/current-authority rejection. The history case preserves the
48,568-byte v5 receipt and its SHA-256
`dba4a1ab7f374ea04044b171b0e163c6b0b1390089197fc64f96c2f0e86983c9`,
then rejects current authority with exactly
`decisive_obligation_omitted` and
`unexpected_decisive_obligation_instance`. Round 3 therefore retains the
v5/v3/v2 epoch; only the future EFFECT capability requires v6/v3 and possibly
evidence-bridge v2.

The complete source denominator is 2,611 Python files. The two required caller
searches now each exit `0` with exactly one non-test call:

```text
src/polisyos/runtime/quality/promotion_sequence.py:917: repository.persist_effective_independence(
src/polisyos/runtime/quality/promotion_sequence.py:939: repository.persist_measurement_root(
```

Independence closes the former `bridge_missing +
implemented_but_not_orchestrated` state while retaining the distinct
feature-flagged report route
`policy_design_case.graded_independence_weights`. Measurement closes
`bridge_missing` alone because `MeasurementRootProducer` already runs in the
workspace loop. Neither absence kind is substituted for the other.

Ruff over the owned source and test files exits `0` with
`All checks passed!`. The base-to-HEAD exclusion predicate exits `0` for
EvalSafety, generation-cycle, the shared HTTP container, and all three
read-only producer modules.

The final AST-byte predicate exits `0`:

```text
base_bytes=948
current_bytes=948
base_sha256=2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38
current_sha256=2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38
identical=True
```

### Governed and carried-red verification

| Evidence | Exact command | Exit | Decisive output |
| --- | --- | ---: | --- |
| promotion contract | `JAX_PLATFORMS=cpu uv run --extra analytics --extra solvers --extra test python tools/quality/validation/check_layer3_gy_promotion_contract.py --check --output-format json` | 1 | uncaught `ValueError: promotion_comparison_admission_manifest_drift`; artifact not regenerated and check not silenced |
| architecture guardrails | `uv run polisyos-tools architecture guardrails check` | 1 | both API generated-artifact probes clean; only the carried trust-claim posture receipt fails because its ratified identity basis differs from the admitted closed receipt |
| debt ledger | `PYTHONPATH=. uv run python tools/quality/validation/check_debt_ledger.py --check` | 1 | exactly 18 blocking `closure_signal_identity_unresolvable` findings: nine `ds10-*`, eight `DS11-*`, and `decision-validity-fixed-temp-concurrency`; no growth |
| documentation lifecycle | `PYTHONPATH=. uv run python tools/quality/validation/check_docs_lifecycle.py` | pending final replay | recorded append-only immediately below |

The two known reds remain measured failures. No governed admission manifest or
trust-claim posture receipt was regenerated, rewritten, or waived.

### Final five-row dossier

#### `gy-promotion-obligations-scope-insufficient`

- Verdict: `blocked`.
- `blocked_by:` the content-bound RACE `O_effect` producer/evaluator and its
  governed `n9_obligation_scope.v3` / `n9_promotion.v6` epoch; the field-pilot
  signal additionally requires the already-named promotion-authority
  EvalSafety producer.
- Deciding evidence: accepted four-cell witness exits `0` but both production
  receipts remain `promoted=False`; Phase-1 history exits `1,1,0,0` and proves
  EFFECT is a distinct obligation; the final EFFECT integrity predicate exits
  `0`. The MEASUREMENT mechanism is built, but the row's exact real production
  `consumer_promotable=True` closure signal is unmet.
- Append-only prose: use the exact supersession under the Phase-1 block above;
  it records the built measurement mechanism and the unlanded governed
  `O_effect` capability without claiming partial closure.

#### `GY-O0-NC-01`

- Verdict: `blocked`.
- `blocked_by:` the same RACE `O_effect` producer/evaluator and v3/v6 epoch;
  the field-pilot disagreement witness also requires the candidate/problem-
  bound promotion-authority EvalSafety producer.
- Deciding evidence: the accepted four-cell test exits `0` with
  `promoted=False` in both production classes, Phase-1 history proves separate
  `O_effect` and `O_id`, and the safety core plus EFFECT bytes remain
  unchanged.
- Append-only prose: use the exact Phase-1 supersession above. It names both
  artifacts that must land and preserves GY-O0's closed structural core.

#### `gy-n9-unmet-check-absence-kind-conflated`

- Verdict: `blocked`.
- `blocked_by:` the RACE `O_effect` producer, persisted artifact,
  content-bound evaluator/consumer, and governed v3/v6 epoch.
- Deciding evidence: the historical comparison exits `1,1,0,0` and settles
  the semantics, while the byte predicate exits `0` and proves the current
  function still has no design evidence. The honest state is now
  `producer_missing + artifact_missing + bridge_missing +
  consumer_evaluator_missing`, not an unowned semantic class.
- Append-only prose: use the exact Phase-1 supersession above; it closes the
  semantic ambiguity but blocks execution on the named chain that must land.

#### `gy-n9-independence-evidence-writer-unorchestrated`

- Verdict: `closed`.
- Deciding command: the red-first two-writer selector moves independence from
  `scope_insufficient` to `failed`, then the final fourteen-case selector and
  `git grep -n '\.persist_effective_independence(' -- src/` both exit `0`.
- Decisive output: one production caller; a real dependent graph resolves to
  `dependent_evidence_collapsed`; the complete receipt replays with zero
  issues. Missing evidence remains `evidence_not_established`.
- Append-only prose: use the exact Phase-2 supersession above, including the
  named graded-independence feature flag and fixed verifier provenance.

#### `gy-n9-measurement-evidence-writer-unorchestrated`

- Verdict: `closed`.
- Deciding command: the red-first two-writer selector moves MEASUREMENT from
  `scope_insufficient` to `satisfied`, then the final fourteen-case selector
  and `git grep -n '\.persist_measurement_root(' -- src/` both exit `0`.
- Decisive output: one production caller; the real producer envelope and its
  authority CAS chain bind to the candidate/problem, and the complete receipt
  replays with zero issues. Missing or foreign evidence remains fail-closed.
- Append-only prose: use the exact Phase-2 supersession above; it records the
  already-running producer and the newly orchestrated N9 writer separately.

**Arithmetic: `5 = 2 closed + 3 blocked`; zero rows are open.** The two closed
rows each have one source caller in the 2,611-file Python denominator and a
red-first integration witness reaching a decisive producer-derived outcome.
The three blocked rows all name the same future `O_effect` capability/epoch
that must land; the two field-pilot signals additionally retain the separately
named EvalSafety producer requirement.

### Post-dossier documentation replay

`PYTHONPATH=. uv run python
tools/quality/validation/check_docs_lifecycle.py` exits `1` with exactly six
findings: the two inherited active-ledger front-matter findings and the four
inherited removed-stub-reference findings. The Round-3 documents add no
seventh finding.

### Mechanical-format supersession

The final formatter pass changed layout only in the two owned Python files.
The production caller coordinates above are therefore superseded by line 915
for `persist_effective_independence` and line 935 for
`persist_measurement_root`; the 2,611-file denominator and one-call count for
each are unchanged. After that formatting, the exact fourteen-case selector
was rerun and exited `0` with fourteen passing dots. Ruff check and Ruff format
check both exit `0` (`All checks passed!`; `2 files already formatted`), and
`git diff --check` exits `0`. The final EFFECT predicate still exits `0` with
948 identical bytes and SHA-256
`2aa090d9694d8599d07f07df46476894a4a39287c324c08beeb8a90d7fd44a38`.
