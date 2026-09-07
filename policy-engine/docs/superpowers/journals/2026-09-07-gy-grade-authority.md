# GY grade authority — investigation and local handback

Date: 2026-09-07. Worktree: `/Users/deniskopylov/polisyos/.worktrees/gy`.
Branch: `codex/gy-grade-authority`. Slice base: `f4815387063`.
No push, GitHub tools, stash, history rewrite, or stale-branch mutation is authorized.

## Investigation (recorded before behavioral measurements)

The four requested debt rows were read as specifications, including their closure
signals. Neither the debt register nor LEDGER is a verification oracle; their
checker is excluded. The task's invariant is: **a grade is not issued by the party
whose claim it grades**. Findings beyond that invariant are proposals, not repairs.

### gy-census-decisive-property-unmeasured

The actual debt concerns evidence for task completion, not whether an artifact has
a field named standing. GY §8.5 and Task Q's investigation distinguish a selected
Done-when predicate from all conjuncts of completion. The historical population
must be recovered from the complete plan change, independently cross-checked,
and joined to current task rows by identity. No search-match total proves it.

Hypothesis before testing: a source-bound measurement can refute a task's
completion claim even when its self-written status remains `executed`; conversely,
one passing delegation test cannot establish the independently correct judgments
required by GY-C2. A runtime receipt verifier cannot by itself establish this
Markdown census. The CR5 routing may therefore need narrowing instead of a shared
wrapper. Cheapest honest close: enumerate the exact population, preserve per-
predicate scope and every unmeasured conjunct, and make the owning plan explicit
about which status is and is not established. Test this reading before deciding.

### GY-PA1

The closure asks for the S8 authorization/request and schedule production,
persistence, resolution and ranked-consumer chain, with the no-schedule and
wrong-authority negatives. GY §8.5 subsequently moves its engineering half to
GY-PR1a; the old PA1 scheduling verdict and missing capability are different facts.

Hypothesis before testing: the current S8 factory admits caller-declared
mandate/status/role references while archive creation always rejects a ranked
case with `p20_value_schedule_resolver_absent`. A green unauthorized-schedule
negative behind that unconditional refusal would measure the wrong property.
Cheapest honest close must wire an independent evidence resolver to the existing
ranking boundary and persist an explicit refusal request, without minting a
mandate or manufacturing an N8 receipt. The investigation must locate the exact
engineering/appointment/data boundary before sizing that repair.

### GY-DEF22

The current closure leaves the appointed Foundry catalog/discovery owner's
acceptance of six bounded claims outstanding. It expressly says no engineering
work is owed. The previous review-subagent ACCEPT is not such an appointment.

Hypothesis before testing: the existing non-decisive diagnostic changes its own
result on environment drift while governing N8/N10a/chronology bytes remain
equivalent to diagnostic removal. Removing the actual generic discriminator,
while keeping its DTOs and marker strings, should make its CB-I02 witness fail.
Cheapest honest close: remeasure that property, retain a typed-empty acceptance
slot, and hand the six claims back for an appointed signature. No self-countersign.

The alleged CR5 witness at `dependency_authority.py:3085` is a private success
payload behind a fieldless token. The visible result union also has rejected and
unestablished arms. This is a counter-hypothesis to the register's isolated-Literal
reading, not yet a behavioral verdict. Follow complete issuance/consumption paths.

### adjudication-and-champion-chain-is-forgeable

The row requires an independently appointed evaluator receipt, a non-producing
authenticator, recomputation from bound observations and champion replay before
any publication projection. Shape and matching manifest labels do not meet it.

Hypothesis before testing: `ClaimAdjudicationRuntime.admit_champion` checks
self-written evaluation metrics, guardrails and provenance strings without an
authenticated observation receipt. A coherently fabricated evaluation passes.
Separately, DataForge's `load_admitted_claim_adjudication_batch` admits a fabricated
batch from matching labels and lineage; `materialize_claim_adjudication_result`
can call it without the Scientist runtime. Thus repairing only Scientist's entry
point leaves a sibling emission path. The single intake must be closed at that
loader too. This path lies outside the allowed edit set, which must be verified
as a real row blocker rather than used to justify a symptom-only fix.

## Execution plan and pattern pass

1. Independently investigate PA1, DEF22 and the stale branch while the coordinator
   investigates census membership and the adjudication chain. No concurrent writer
   shares a source or governed artifact.
2. Record hypotheses first; run focused behavioral stations. Enumerate full path
   sets, compare identities in both directions, classify unreadable cases ambiguous.
3. Implement only an established mechanism within the approved paths. Preserve
   negative and unavailable outcomes, leaving institutional signature slots empty.
4. Freeze changes, review the delta, run blast-radius tests and appropriate
   recomputing validators once. Commit clean boundaries after checking attachment;
   read committed files back from the branch. Stop before push.

Relevant patterns: P05/P15 (authority), P29/P32 (behavior/content versus markers),
P31 (single intake/emission), P35/P36 (whole-set and finding-bound evidence),
P37/P38 (predicate provenance/proxy), P40 (same-class finding bucket), P41 (no
unproved inherited-red claims). A second finding of the same class widens the
mechanism or yields a measured bounded residual; it does not start a patch ladder.
Acceptance: actual consumer refusal of self-issued labels, favorable/unfavorable
results through real paths, and at least one property-removal red per measured row.
Missing capability labels are assigned after tracing, not inferred from prose.

## Stations and environment

- Auxiliary worktrees: none created.
- `git status -sb` after setup: `## codex/gy-grade-authority`.
- `uv sync --offline --frozen --extra lint --extra test --extra runtime` failed
  because the pinned odfpy wheel is not cached. Minimal offline install also lacked
  cached pytest metadata. These are tooling non-receipts, not product findings.
- A local CPython 3.14.3 venv reads the existing main venv's dependency directory
  through local `gy_reused_dependencies.pth`; no sibling file is modified. Tests
  use `PYTHONPATH=src` and local `python -m pytest`, with import origin verified.
- Scratch is under this worktree's `policy-engine/_build/gy-grade-authority/`.
  No shared production data writes or fixed-port/browser stations are planned.

## Measurements, changes, probes and remaining work

### GGA-CENSUS-01 — population and limits

The first whole-commit subtraction found **35**, not 24, new task rows. My first
query was wider than the debt: that commit also added **11 `not_started` future
tasks**. Filtering the complete addition by its recorded standing yields the
original census population, and independently walking the complete original
contiguous census block yields exactly the same identities. This correction was
made before reporting any population as measured. No unreadable row was dropped.

Denominator: one Markdown GY plan, its complete §8.5 table at historical
`73d930f8284682fafc283c2b78c54d64bbecf1dd` and that commit's first parent, and
the complete current table. Original census: **24 = 21
presence-only + three ambiguous** (`GY-D1`, `GY-M2`, `GY-K`). Current table:
**74 = 42 executed + one not_executable + 22 not_started + nine ambiguous**.
The current 21-row subset is **14 executed + seven ambiguous**. Two current-table
parsers agree on the entire identity set, not just its size. The 73-row count in
the task's historical input is not used as today's denominator.

The table below is the complete 21-row set. The Task Q column is a **historical
selected-predicate receipt** from its §3 investigation, not a fresh green claimed
here. All other Done-when conjuncts remain explicitly `not_measured`. That note is
now on **every corresponding row of the owning GY plan**. A favorable author-
written task status does not upgrade the measurement's scope.

| Task | Task Q selected predicate | Full Done when at this station |
| --- | --- | --- |
| GY-M1 | lifecycle scan: fail | not_measured |
| GY-B | non-active operation refusal: pass | not_measured |
| GY-H | terminal precedence: pass | not_measured |
| GY-D2 | connector/source admission: pass | not_measured |
| GY-D3 | adequacy negative and recall, slice0_gate_only: pass | not_measured |
| GY-E | costed acquisition terminal: pass | not_measured |
| GY-C1 | playbook deviation: fail | not_measured |
| GY-C2 | independent real-input judgments: not_measured | not_measured; self-grade falsifier below fails |
| GY-C3 | real Foundry estimate consumption: fail | not_measured |
| GY-I | tool-loop event persistence: pass | not_measured |
| GY-F1 | workflow failure authority recomputation: fail | not_measured |
| GY-F2 | artifact surface safety: pass | not_measured |
| GY-F3 | time/source authority recomputation: pass | not_measured |
| GY-G | feedback without joint grounding: pass | not_measured |
| GY-J | useful-design graded routing: fail | not_measured |
| GY-L | HTTP-triggered outcome run: fail | not_measured |
| GY-S0 | novel registration/versioning: pass | not_measured |
| GY-S1 | L4 world model/simulation: pass | not_measured |
| GY-N-V | timeout yields unknown: pass | not_measured |
| GY-S2 | transported/contested non-point sets: pass | not_measured |
| GY-S3 | every method route covered: fail | not_measured |

Fresh positive-control command (each gate is a sole invocation):

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/runtime/quality/test_workspace_spine_repair_gates.py::test_governance_tail_verifier_delegates_to_governance_node_owner -q --override-ini addopts=''
```

Result: **exit 0, one passed, 27.15 s**. The actual test calls the real owner but
supplies empty per-judge dictionaries. The owner at
`scientist/nodes/builtins/governance/run_governance.py:1136` checks the set of judge
names, `composite_decision`, warnings and declared completeness. It does not
authenticate or inspect each judgment's substance.

Removal/falsification station:

```sh
PYTHONPATH=src .venv/bin/python -m pytest _build/gy-grade-authority/test_census_judge_station.py -q --override-ini addopts=''
```

**Exit 1, three failed, 27.14 s.** For each judge in the runtime-derived
`_PHASE2_REQUIRED_SIX_JUDGES`, the probe substitutes `{}`, `{"verdict":"reject"}`
or `{"verified":false}` while keeping all judge names, completeness and promote
markers. Every cell returns `applicable`, contradicting the assertion
`status == "repair_required"`. This proves the green delegation receipt is
insufficient; it does not prove the positive real-input Done when. No judge is
silently omitted, and the source's required set supplies the denominator.

**Routing result:** the common principle survives; the proposed shared runtime
implementation does not discharge the documentary census. GY-CR5's witness is
also refuted independently in GGA-DEF22-02. The census therefore returns to its
measurement lane, as the user explicitly permits. The old note-or-measurement
obligation is now complete over its exact population; full task completion and
the broader CR5 all-consumer claim are **not** asserted. Capability grade for the
independent GY-C2 judgment producer remains `verification_missing` at this intake.

### GGA-ADJ-01 — a coherent fabricated chain really publishes

Source paths traced: Scientist `claim_adjudication_runtime.py`, evaluator
`claim_adjudication.py`, `models.py`, `registry.py`; DataForge
`claim_adjudicator.py` and `admitted_claim_adjudications.py`; neutral carrier
`ir/analytics/literature.py`. The input CAS bytes, ordered claim denominator and
manifest lineage were preserved in both negative stations.

The existing Scientist suite is **exit 0, nine passed, 18.38 s**:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/scientist/methods/autotune/test_claim_adjudication_runtime.py -q --override-ini addopts=''
```

Its `_promote_champion` helper constructs a self-stamped passing
`BenchmarkEvaluation` and asserts registry promotion. Reusing that complete
fixture, the new requirement-level negative is **red**: the outcome is
`completed`, with one published claim, where `blocked` is required. The batch
declares `independently_reconciled` despite no appointed evaluator receipt.

```sh
PYTHONPATH=src .venv/bin/python -m pytest _build/gy-grade-authority/test_forged_authority_station.py -q --override-ini addopts=''
```

Initial pair: **exit 1, two failed, 16.24 s**, identities
`test_self_stamped_evaluation_does_not_emit_publishability` and
`test_same_forged_chain_cannot_materialize_without_scientist`.

The second station was then made stronger: it constructs the typed batch and
self-labelled CAS manifest **without ever calling Scientist's runtime**, uses a
zero-valued pointer digest, and invokes DataForge materialization directly.
An authentic evaluator receipt, registry replay and observation recomputation are
all absent; every marker and lineage field stays present. Exact targeted rerun:

```sh
PYTHONPATH=src .venv/bin/python -m pytest _build/gy-grade-authority/test_forged_authority_station.py::test_same_forged_chain_cannot_materialize_without_scientist -q --override-ini addopts=''
```

**Exit 1, one failed, 17.69 s: `DID NOT RAISE ValueError`.** This is the same
authority-intake class at its sibling consumer, not a new repair round. Its
counterexample establishes the genuine file boundary: changing only Scientist
cannot close the row. `data_forge/**` and the neutral IR carrier are outside this
task's allowed source paths. No source repair or owner appointment is claimed.

Cheapest correct mechanism: one independent evaluator-verification owner that
authenticates a deployment-trusted appointed key, resolves and content-binds the
complete observation set, recomputes metrics/guardrails/promotion, and replays the
champion before **both** admission and direct materialization. An independent
public key taken from the claimant's payload is not a trust root. Missing trust
leaves the typed appointment slot empty and the authority output blocked. Current
capability: `verification_missing`; runtime and materializer bridges are present
but admit unverified evidence. The claimant's batch shape is not a credential.

Exact minimal quarantine edit to hand to the DataForge owner, if immediate
containment is chosen before that capability lands (not applied here): at the
start of `load_admitted_claim_adjudication_batch`, before reading a ref or
materializing any output, add
`raise ValueError("claim_adjudication_independent_verifier_missing")`.
This closes that emission path only by an explicit missing-capability refusal;
it is **not** the row's positive closure and must not be reported as one. The full
replacement must route this same loader through the independent owner, and keep
the standalone fabricated-batch test above. A Scientist-only patch, a caller-
supplied verifier callback, or a differently named manifest producer is refused.

### GGA-PA1 — implementation and closure evidence

S8 mechanism and its removal controls are in progress. Its full PA1 closure is
not asserted: the separate N8 production chain remains missing.

**GGA-PA1-N8-01:** the complete tracked source Python set and an independent
filesystem walk (excluding caches) both contain 2,621 files; both directional
path differences and all AST parse failures are empty. Expanded name/attribute/
alias-aware inspection finds **zero production `ValueGateReceipt(...)`
constructors**. Two `ValueGateReceipt.model_validate` consumers do exist, at
`promotion_sequence.py:1530,1590`; calling those producers would be wrong.
The four `value_ready` literals are type/check positions, not emissions.

The live N8 port's successful selection path ends unconditionally at
`treatment_assignment_not_owner_derived`. The owner data profile only represents
`owner_assignment_unresolved`; the existing N7 gap represents unsatisfied routing
and cannot be reinterpreted as positive admission. The production CG2 calibration
store supplies `records=()` / `none_wired_production_freezes`. Neither the
transport solver nor N9's effect verifier produces that missing evidence.

The first targeted station failed because the worktree lacked its data symlink.
That was a setup error, **not a substantive missing-data finding**. The root then
linked the existing filesystem-read-only main `production_data` directory into
this worktree (directory `dr-xr-xr-x`, catalog `-r--r--r--`). No data was modified.
Fresh exact-node rerun:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -p no:cacheprovider tests/unit/runtime/quality/test_value_gate.py::test_value_port_selects_then_routes_missing_owner_assignment_to_acquisition tests/unit/runtime/quality/test_value_gate.py::test_shaped_owner_assignment_attestation_is_not_authority tests/unit/runtime/quality/test_value_gate.py::test_shaped_relation_certificate_cannot_open_missing_value_input_lane -q
```

**Exit 0, three passed**: actual owner data and selected method reach the honest
assignment refusal; fabricated rollout and SKG declarations do not change it;
no value receipt is emitted. The field boundary now rests on a meaningful live
path, rather than a missing local file.

The existing PR1a plan (`docs/superpowers/plans/2026-09-02-gy-pr1a-data-only-promotion.md`,
§ numbered source anchors 311/396/894/1161) places the independent non-institutional
certificate producer in
`src/polisyos/data_forge/domains/academic/knowledge/skg_identity_bridge.py`, which
is absent and outside this task's write set. That is engineering authority;
**no appointment is needed for this alternative**. Older PA1 prose treating every
route as institutional is not used to stop engineering. The source/effect
certificate, production calibration, scoped Foundry dispatch, S10 support and
persisted/read-back N8 receipt must precede a truthful positive observation.
Building a downstream adapter/store shell or signing a fabricated assignment
would preserve the missing producer while making the capability look finished.
N8 remains `producer_missing + artifact_missing + bridge_missing`; its negative
consumer route is real. S8 is built independently below without changing that
empirical standing.

### GGA-DEF22 — current measurement and appointment

**GGA-DEF22-01: the prior five-clause acceptance is not freshly re-attested.**
The initial wave on the slice's unchanged source returns **five failed, zero
skipped, 28.14 s**, before the intended diagnostic assertions. Exact node set:

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data -q --override-ini addopts=''
```

CB-I01 stops at `DigestPredicateMismatch`: N8's owner declaration expects
pyproject digest `803cbfb79c7727807db1c98d07413e8ef2f1b2a08929bd99bc2f8e638ee5142d`,
while the currently resolved frozen owner bytes yield
`a25bc559fb92ba39e357babc2961f4e8981b39bb51e599632a8224dcfed52484`.
The other four stop at `selected_lock_graph`; the real inner error is
`uv lock contains an ambiguous package name`. The current complete uv.lock TOML
has 418 package rows, including Pillow 10.4.0/12.3.0 and regex
2024.11.6/2026.9.3. The resolver rejects repeated names before following the
selected dependency closure. The named source property was never reached.

These are recorded station failures, **not a claim of inherited-red exclusion**:
no exact-command isolated P41 replay with a disjoint full input denominator was
produced. The earlier merge's five greens are historical receipts, not substituted
for this failed current wave. Changing toolchain owner artifacts or repairing a
lock-identity resolver is outside the grade invariant and is proposed separately.

A new removal station instead supplies novel two-package owner data directly to
the actual Foundry resolver and diagnostic. Removing only
`_calculate_dependency_distribution_cases` preserves types, rules, schema and
discriminant content identity. It removes the substantive discrimination.

```sh
GY_DEF22_REMOVE_CASES=1 PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_runtime_removal_probe
```

**Exit 1**: `dependency disagreement was not detected`; actual status
`not_established`, expected diagnostic `fail`. Restored fresh process:

```sh
PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_runtime_removal_probe
```

**Exit 0**, actual diagnostic `fail`. Both runs retain discriminant hash
`d383aba601fd2edb159bc557b55be744b25a8e5b0d5e566889ea3304a823bace`.
This demonstrates substance beyond marker presence. It does **not** re-establish
all five CB clauses, and it correctly does not turn missing discrimination into
a favorable grade. Scratch is local at `_build/gy_grade_authority/`; the earlier
file-form exploratory invocation is superseded by these module-form gates.

**GGA-DEF22-02: the registered Literal is not a self-grading escape.**
`_VerifiedProductionDataRootAccessPayload.predicate_class` is a private success
payload. `RootAccessAttestationResult` also has `RejectedAuthorityPredicate` and
`UnestablishedAuthorityPredicate` arms. Production `attest` returns unestablished.
The complete module assignment census finds three keyword assignments: line 4712
belongs to a negative mismatch, 5173 to the candidate root observer, 5423 to the
candidate runtime observer. The fourth textual occurrence is the annotation,
not a fourth payload-producing assignment. Those paths cannot be inferred from
adjacency in the file.

The actual public-token intake was exercised:

```sh
PYTHONPATH=.:src .venv/bin/python -m _build.gy_grade_authority.def22_grade_boundary_probe
```

**Exit 0**. A self-written `predicate_class="independently_reconciled"` mapping
and an empty object both fail with `wrong_token_type`; an
`object.__new__(VerifiedProductionDataRootAccess)` forgery fails with
`unminted_token`. Negative and unavailable result arms remain representable.
No success-Literal widening is warranted. This is where the motivating reading
was wrong: it treated one successful branch as the whole result vocabulary.

**GGA-DEF22-03: appointment stays empty.** Required acceptance is still by the
appointed Foundry catalog/discovery owner for exactly these bounded claims:

1. Foundry controls the purpose/profile relation.
2. Identity is dependency-only and excludes machine and production data.
3. Closure and first-case ordering are generic.
4. N8 is the sole producer and consumers share verified bytes.
5. Diagnostics cannot decide admission, gap closure, chronology, publication or promotion.
6. The missing positive authority chain remains missing.

The previous subagent ACCEPT supplies none of that institutional appointment.
This lane leaves the acceptance slot empty and makes no new authority claim.
Cheapest honest disposition: preserve the existing grade boundary, hand back the
appointment and report the current verification prerequisites. No tracked
Foundry implementation was changed.

## Proposed rows and boundary handbacks

- `gy-foundry-profile-pins-drift-after-toolchain-update` — proposed owner Foundry
  catalog/discovery + GY artifact owner. Reconcile the frozen pyproject/owner pin
  and reissue its governed artifacts before reusing the five-CB receipt. Required
  architecture/tools writes are excluded here.
- `gy-foundry-lock-graph-name-uniqueness-proxy` — proposed owner Foundry
  dependency-profile resolver. Select the applicable uv package identity before
  diagnosing closure; global name uniqueness is the wrong predicate. Keep repeated
  names whose graph coordinates discriminate them as a red/green pair.
- `gy-governance-tail-admits-names-without-verdicts` — proposed owner Scientist
  governance, within GY-C2/CR5 engineering if accepted. The three requirement-level
  reds in GGA-CENSUS-01 are one class. No instance patch for empty dictionaries was
  made; verification must authenticate and consume actual judgments.
- `gy-n8-dormant-proxy-interval-certification` — proposed owner runtime/quality
  value producer. `_value_outer_set_from_foundry_result` invents 10%/0.01 proxy
  interval floors and labels the result certified. It has no source callers;
  activating it unchanged would turn a dormant helper into an authority leak.
- Adjudication DataForge intake edit: GGA-ADJ-01 above. This is a blocker of that
  row's structural repair, not a request to appoint an evaluator and not a reason
  to stop S8 work.

## Census reproducer and readback contract

Run from the worktree root. This walks the complete GY table at each pin, derives
membership from the whole historical addition, reconciles independently with the
original census block, and compares full current identity sets. It reads neither
DEBT-REGISTER nor LEDGER. Unknown status or a malformed row fails rather than
counting as absent. The script emits only recomputed documentary facts.

```python
from collections import Counter
from pathlib import Path
import re
import subprocess

path = "policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md"
historical = "73d930f8284682fafc283c2b78c54d64bbecf1dd"
def git_text(ref):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
def table(text):
    section = text.split("## 8.5 Task standing (authoritative)", 1)[1].split("## 9.", 1)[0]
    expected_cells = len(next(line for line in section.splitlines()
                              if line.startswith("| id | phase | status |")).split("|"))
    rows = {}
    for line in section.splitlines():
        if not line.startswith("| `GY-"):
            continue
        cells = line.split("|")
        assert len(cells) == expected_cells, line
        key, status = cells[1].strip().strip("`"), cells[3].strip().strip("`*")
        assert key not in rows
        assert status in {"executed", "in_flight", "not_executable", "not_started", "ambiguous"}
        rows[key] = (status, line)
    return rows

before = table(git_text(historical + "^"))
after_text = git_text(historical)
after = table(after_text)
added = set(after) - set(before)
census = {key for key in added if after[key][0] != "not_started"}
block = after_text[after_text.index("| `GY-M1` "):]
block = block[:block.index("| `GY-S3` ")] + block[block.index("| `GY-S3` "):].splitlines()[0]
independent_census = set(re.findall(r"^\| `(GY-[^`]+)`", block, re.M))
assert census == independent_census
presence_only = {key for key in census if after[key][0] == "executed"}
current_text = Path(path).read_text()
current = table(current_text)
independent_current = set(re.findall(
    r"^\| `(GY-[^`]+)` \| [^|]+ \| (?:\*\*)?`?(?:executed|not_executable|not_started|ambiguous|in_flight)",
    current_text, re.M))
assert set(current) == independent_current
assert presence_only <= set(current)
assert all("not_measured" in current[key][1] for key in presence_only)
print("historical additions", len(added), Counter(after[k][0] for k in added))
print("census", len(census), "presence-only", len(presence_only))
print("current", len(current), Counter(status for status, _ in current.values()))
print("subset", sorted((key, current[key][0]) for key in presence_only))
```

The staging hook initially refused the investigation commit because the new
worktree lacked Lefthook. `corepack pnpm install --frozen-lockfile` provisioned
its local dependencies (5.2 s); no lockfile or tracked frontend path changed.
Normal hooks then passed/skipped their scoped checks and created investigation
commit `4082cd490`. Its journal was read back with `git show` from the named
branch immediately after commit. No hook bypass or ledger checker was used.

## codex/gy-def6-e11 analysis

### Intent, population and later incorporation

Recommendation: **do not recover this as an implementation lane; preserve the
existing branch ref as history**. No unique production mechanism was identified
as a prerequisite of the four grade rows. No stale branch, worktree or history was
mutated, and no test was run from that branch.

At investigation entry, main and the task's slice base were the same full commit
`f481538706316b0d94722fd2a3891b2067779a38`. Merge base with the stale branch:
`e708e8f77dbac35e3f8c164341cc19eed7695998`. The entire commit and changed-path sets
were walked. **82 ahead / 1,666 behind; 22 paths = 14 Python + seven JSON + one
ledger**. Python paths comprise five source, six test and three validator files.
The complete commit classification is **63 ledger-only + ten code/test + nine
artifact reissues = 82**. Author and committer dates run August 8–9, 2026; first
commit `44e01b523`, final `ba5946ebc`. All 21 non-ledger paths exist at the slice
base and have subsequent main history. This is a complete set, not a sampled log.

The work sought content-bound N8 provenance, independent N10a rederivation,
controlled catalog loading, non-consumer Depth-N verification, replay clocks,
complete import closure, and loader-owned callable-slot admission. The decisive
later incorporation is `431bcd7981b571c8c3943bfee55be8ce0bc0aa1f`, “bind cold
closeout inputs and projections”. Normalized ASTs were compared over every
top-level definition in all 14 Python paths and differing hunks were inspected.
At that successor, Depth-N tests match 99/99 definitions, N8 validator 85/85,
N8 tests 75/75, and catalog snapshot 27/27. All 11 production definitions changed
by final WIP `ba5946ebc` match the successor; at the task base ten still match
and the remaining function has gained qualified `.contextmanager` support.
These are code-equivalence findings, **not fresh behavioral test receipts**.

### Commit-specific recovery disposition

| Commit | Intended contribution | Disposition against current base |
| --- | --- | --- |
| d5a3495d0 | N8 provenance identity/recomputation and corruption controls | Incorporated by 431bcd798 and extended later |
| 50412092c | N8 artifact reissue | Historical receipt superseded; recompute, do not transplant |
| c88593cc1 | N10a writer-normalized rederive, no invented routing time | Incorporated and replaced by canonical operational-leaf reconciliation |
| 6d0ac2c18 | N10a trace/gaps/pack reissue | Superseded historical artifact wave |
| 537d8927d | Promotion reissue | Superseded identity-only wave |
| 691ae33f0 | Generation-cycle reissue | Superseded identity-only wave |
| b45911d49 | Controlled builtin Foundry registry and consumers | Incorporated; consumers further bound to module-owned lookup |
| 35279d30c | Delete ambient POLISYOS_PACKS_PATHS in registry test | Unique one-line test isolation choice; present necessity not_established |
| f6b24b0df | Controlled N10a trace reissue | Superseded within branch and on main |
| 16ca22088 | Depth-N/N10a isolated-verification promotion and migration | Incorporated and refined by a75543d2f, 431bcd798 and later admissions |
| a75543d2f | Source admission, predecessor/migration lineage, live-receipt checks | Incorporated and hardened later |
| 821df3115 | Independent N10a corrupt witnesses reaching consumers | Incorporated; successor adds controlled live-bundle input |
| 5b031e262 | N10a dependent artifact wave | Superseded by later main reissues |
| 062cb3f36 | Controlled Depth-N replay clocks | Incorporated and moved to canonical reconciliation |
| f12454c17 | Depth-N authority migration artifact | Authority posture retained; physical receipts superseded |
| b2fb6e52d | Promotion artifact wave | Superseded; current contract has v3 obligations/comparison proofs |
| bcbcf7d79 | Generation artifact wave | Superseded by current comparison projection |
| cfbf863b6 | Complete import closure before capture; missing-member/import-order controls | Production incorporated; old credal_first test variant may be retained as additional coverage |
| ba5946ebc | Loader-owned descriptor/property/contextmanager/cache callable slots | Incorporated despite WIP label; current implementation is further extended |

The **only identified unique recoverable choices** are test details in
`35279d30c` (`monkeypatch.delenv("POLISYOS_PACKS_PATHS", raising=False)`) and
`cfbf863b6` (an additional `credal_first` ordering instead of the successor's
`depth_first`). Neither warrants recovery without a current falsifier. The 63
ledger-only commits retain historical process evidence, not absent production
work; none should be replayed into the current lane.

### Collision with the three named contracts

This task does **not** change any `layer3_gy_*_contract.json`. Those architecture
paths are outside its allowed write set, so its diff has no direct collision.
If the later artifact owner recomputes them after S8, recovery must start from
current main; old stale-branch receipts cannot be merged as current evidence.

Complete recursive JSON walks count scalar leaves and empty containers by
key/index identity (one complete JSON document per row):

| Contract | Fork / stale / base leaves | Stale changed leaf identities | Current disposition |
| --- | --- | --- | --- |
| depth_n_universality | 16,586 / 36,083 / 43,032 | 22,960 | 22,600 changed values retained; real migration posture incorporated |
| generation_cycle | 1,695 / 1,695 / 2,620 | 43 | All changes are sha256 identity strings, all subsequently replaced |
| promotion | 1,873 / 1,873 / 2,915 | 67 | All changes are sha256 identity strings, all subsequently replaced |

The Depth-N changed set partitions into one contract hash, 27 domain-run leaves
and 22,932 proof-recording leaves. Every one of its three domain promotion rows
has the same authority projection in stale and base: `contract_testing`,
`authority_provenance=["verification"]`, all receipts non-consumer,
`verification_n9_sequence_non_consumer`, `not_promoted`, no certified candidates.
Receipt counts are education four, first_vertical three, unseen three.
Current contracts additionally carry comparison projection v2/rule v3; promotion
schema moved from stale v2 to base v3. Transplant would remove later semantics.

### Why it stopped, and what cannot be inferred

The final commit explicitly records: “Unreviewed successor-task work; no E11
admission, replay, or closure claim.” It records focused import-order/rebound
tests as green, but says the full confidence-ledger/importer/artifact wave was
intentionally not run under the GY-DEF6 stop rule. The **exact triggering rule
threshold is `not_established`** from the requested commit messages and ledger;
no procedural cause is invented.

The complete `.e11/gy-def6.ledger` contains **64 records**: one open, ten freezes,
ten review packages, 20 review results, 13 admitted findings and ten resolutions.
All 64 mark `research_only=true`. Its final frozen source is `cfbf863b6`, before
the WIP. Unresolved admitted identities are
`N11-IMPORT-ORDER-IDENTITY-1`, `ARCH-REBOUND-CALLABLE-ADMISSION-1`, and
`QUALITY-REBOUND-CALLABLE-ADMISSION-1`; the latter two are recorded blocking/batch.
There is no close, replay or terminal event in the complete record set.

The 64 records refer to **62 distinct** review/package/checklist/result/resolution
files under `tmp/e11/`; **zero are tracked on the stale branch**. Thus the ledger
establishes recorded declarations and events, not the absent reviews' full
semantic evidence. This limitation survives even where main incorporated code.

### Options, costs and losses

- **Recover the entire branch onto fresh main:** reconcile 82 commits/22 paths
  against 1,666 later commits, revisit superseded authority changes, then review
  and rerun the dependent receipt cascade. No production gain identified.
- **Extract specific choices:** the two named test variants only, after a present
  falsifier establishes value. Small code cost plus focused validation; no JSON
  transplant or historical E11 protocol replay.
- **Register debt:** only a demonstrated current missing behavior. Registering
  this whole branch as implementation debt would double-count incorporated work.
  Historical incomplete review is a provenance limitation, not missing code.
- **Abandon implementation recovery while preserving the ref (recommended):**
  lowest cost, no identified production capability loss, history remains usable.
  Deleting the ref would lose convenient historical evidence and is not authorized.

Readback during work found the external `main` ref advanced once to
`8a0d996fe53d9f689fd28b84fe649ce494030820`: its live distance became 1,667 behind.
Our branch/HEAD remained attached and unchanged by that event. All incorporation
claims and the 1,666 denominator above are deliberately bound to the original
slice base; the stale ref remains `ba5946ebc70bb63f30e4776d0426e19f37dffd31`.
No branch was moved to follow main.

Reproducible read-only starting commands (each invoked separately; use the pinned
base in distance/diff commands to reproduce the numbers above):

```sh
git rev-parse main f48153870 codex/gy-def6-e11
git merge-base f48153870 codex/gy-def6-e11
git rev-list --left-right --count f48153870...codex/gy-def6-e11
git log --reverse --format='%H|%aI|%cI|%s' f48153870..codex/gy-def6-e11
git diff --name-status f48153870...codex/gy-def6-e11
git show codex/gy-def6-e11:.e11/gy-def6.ledger
```

For every enumerated commit, `git diff-tree --no-commit-id --name-only -r COMMIT`
supplies its complete path denominator. Ledger-referenced path availability is
checked with `git cat-file -e REF:PATH`. No GitHub plugin or remote operation was
used, and no decision recorded on that branch is a prerequisite for these rows.
