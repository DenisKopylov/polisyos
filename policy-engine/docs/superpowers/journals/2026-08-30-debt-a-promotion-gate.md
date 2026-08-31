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
