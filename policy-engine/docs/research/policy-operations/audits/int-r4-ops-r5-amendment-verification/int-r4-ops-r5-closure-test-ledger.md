# INT-R4 ‖ OPS-R5 — Closure-Test Ledger

Audit instrument: `audits/int-r4-ops-r5/int-r4-ops-r5-recommended-revision.md`, `CT-01`…`CT-12`.  
Package under test: `329edb60f77867f914581d380acfccf5882d607d`.

## Instrument Boundary

The user explicitly required GitHub Connector execution after local Git transport failed. The verifier therefore executed exact-ref branch, file, blob and compare reads through the connector. No shell process produced the requested Git receipts; each terminal value is `not_produced`. Connector observations below are labelled as such and are not terminal substitutes.

For `UNRUNNABLE`, this ledger uses the audit's required distinction. All six unrun tests are blocked by missing package artifacts and are therefore **a package defect**, not **an environmental limit of my verification**.

## Results

| CT | What was executed | Result | Basis |
|---|---|---|---|
| `CT-01` | Compared audit absorption standard with the seven-row OPS-R7 matrix, operation-level OPS-R6 charters, and corpus-gap records. | `FAIL` | Each question now has an argument, evidence and falsifier/divergent case, but no immutable question/operation fixture exists. The test requires answer, evidence, failure mode, fixture and residue. |
| `CT-02` | Read INT report §4.3, §4.8 and §5.1 at amendment head; then read INT amendment ledger §5 and amended rider register. | `FAIL` | The report still permits routine `expected_variation` assimilation and says “no contradiction”; ledger/register forbid effect-posterior mutation. Different package artifacts give different answers. |
| `CT-03` | Established diagnosis corpus and consumer availability from `amendment-diagnosis-corpus-gap.md`. | `UNRUNNABLE` | Missing artifact: instantiated self-produced-compatible packet, sealed oracle and actual effect-posterior consumer assertion. This is **a package defect**. |
| `CT-04` | Applied the amendment's mixed path: genuine behavioral response → changed inclusion/filtering → biased sample. | `PASS` | The amendment sets observation change as the effect-update disposition, retains behavioral response, blocks learning, and makes both measurement and behavior lanes mandatory. |
| `CT-05` | Established holdout/oracle/evaluator availability from INT ledger §3 and diagnosis gap record. | `UNRUNNABLE` | Missing artifacts: sealed domain-stratified holdout, independent oracle, evaluator and results against all-unresolved/simple-quarantine baselines. This is **a package defect**. |
| `CT-06` | Read `amendment-state-invariants.md`; checked for a state engine and mutation results. | `UNRUNNABLE` | Predicates and FCT-01…FCT-04 are specified, but the file explicitly says no executable state engine or mutation suite exists. This is **a package defect**. |
| `CT-07` | Established O3 mutation artifact availability from the diagnosis gap record. | `UNRUNNABLE` | O3-M1…M5 are described, but zero packets, sealed oracles and consumer assertions exist. This is **a package defect**. |
| `CT-08` | Established response packet/evaluator availability from `amendment-response-corpus-gap.md`. | `UNRUNNABLE` | Zero response packets, transition oracles and evaluator exist; paired proxy cases cannot execute. This is **a package defect**. |
| `CT-09` | Fetched both revised registers at the exact amendment SHA and scanned every finding-table capability cell for `contract_only`. | `PASS` | Denominator: 36 finding rows/capability cells, 18 INT + 18 OPS. Capability-cell hits: 0. Two prose hits remain, both explicitly negating prose-based `contract_only`; context recorded below. |
| `CT-10` | Read INT §4.7, INT amendment §8 and checked corpus/crosswalk artifacts. | `UNRUNNABLE` | No versioned total crosswalk artifact exists, and no fixture corpus exists to enumerate contributor combinations. This is **a package defect**. |
| `CT-11` | Traced sampled row `INT-F03`: row → `INT-RB16` → exact N8 source coordinates, plus kind/transfer and row falsifier. | `PASS` | The reviewer reaches evidence, evidence kind, bounded transfer and falsifier from the register without reconstructing the package. |
| `CT-12` | Connector compare `ea2eac557…` → `329edb60…`; classified every changed path and status. | `PASS` | Exactly 7 paths: 5 added, 2 modified; all `.md`, all under `policy-engine/docs/research/policy-operations/`; no audit artifact, source, workflow, binary, staging, `AGENTS.md` or pattern-register edit. |

Arithmetic:

```text
PASS        4  (CT-04, CT-09, CT-11, CT-12)
FAIL        2  (CT-01, CT-02)
UNRUNNABLE  6  (CT-03, CT-05, CT-06, CT-07, CT-08, CT-10)
           --
TOTAL      12
```

## CT-02 Package-Wide Reading

Observed in `int-r4-performative-effect-update-diagnosis.md` at amendment head:

```text
§4.3: expected_variation “May enter ... routine likelihood/calibration schedule.”
§4.8: expected_variation “may enter ... routine update/calibration schedule.”
§5.1: “Only prediction_error may update” must not ban that path;
      “This does not contradict the rider's safety direction.”
```

Observed in `int-r4/amendment-ledger.md:239-334` and the amended INT register:

```text
expected_variation → no effect-posterior mutation
only prediction_error may enter an effect-posterior update proposal
```

The top-level INT report has the same blob at research and amendment heads. CT-02 directs the verifier not to choose one artifact; the package is internally inconsistent under its declared interim posture. No judgment is made on the separately routed principal request.

## CT-09 Search Record

Connector operation, equivalent to an exact-ref two-file search:

```text
fetch_file(path=int-r4/evidence-register.md,
           ref=329edb60f77867f914581d380acfccf5882d607d)
fetch_file(path=ops-r5/evidence-register.md,
           ref=329edb60f77867f914581d380acfccf5882d607d)
scan column "Capability standing" across 36 finding rows for literal contract_only
```

Result:

```text
INT capability cells scanned: 18
OPS capability cells scanned: 18
capability-cell hits: 0
```

Surrounding prose contexts containing the token are non-hits for the test:

```text
INT: “A research sketch is not contract_only; that label presupposes a real admitted type.”
OPS: “Research sketches are not contract_only capabilities.”
```

## Connector Read Set

The closure ledger read at exact SHAs:

- both amendment ledgers;
- both amended evidence registers;
- both unchanged research reports;
- diagnosis-corpus gap, response-corpus gap and state-invariants documents;
- all seven audit artifacts, with the recommended-revision closure tests as primary instrument;
- pipeline §2 and §3.3;
- compare records for base/research/audit/amendment topology and delta shape;
- both research-report blobs at research and amendment heads.
