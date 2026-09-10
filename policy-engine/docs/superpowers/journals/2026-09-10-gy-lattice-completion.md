# GY lattice and custody — execution and completion journal

Date: 2026-09-10. Immutable lane merge base: `992aa493f`.
Local branch: `codex/gy-lattice-and-custody`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/gy-lattice`.
No push, history rewrite, stash storage, or other branch modification.

This is the lane's single completion journal. **GY-VC1, GY-CR2, GY-CR3 and GY-CR5
are executed. GY-AS1 is blocked on architecture acceptance.** Its semantic battery
passes, but the final architecture gate reports a new deep import. The user's
explicit stop condition applies: no source repair, baseline sync, or further
product gate followed that result. Remaining work after the stop was bookkeeping,
preservation and this handback.

**GL-ARCH-FINAL-01 — required architect decision, not an impossible mechanism.**
The full gate ran against the delivered source at `c817314b4`, exit **1**. It
reports new deep-import creep from `polisyos.fabric.evidence.acquisition_assurance`
to `polisyos.core.artifacts`, with corresponding baseline drift. Source:
`src/polisyos/fabric/evidence/acquisition_assurance.py@1b76ac477`.
Accepting the baseline or authorizing an alternative boundary composition belongs
to the architect. This lane does neither. Complete output:
`gy-lattice/root/raw/architecture-final.txt`; command/exit/output digest are in
`gy-lattice/root/verification.json`.

The same gate's generated freshness stage is **unrun**: its environment interpreter
aborts with SIGABRT while loading `libpython3.14.dylib`. This is not a passed or
skipped check. No claim of a green full architecture gate is made. The four other
tasks' scoped deciding evidence is retained below; the new import belongs to AS1.

## Stage boundaries and scope

`f51b85b0a` is the first commit. Its only change adds
`policy-engine/docs/superpowers/journals/gy-lattice/**/raw/` to `.gitignore`.
The initial commit attempt failed because the fresh checkout lacked lefthook;
`corepack pnpm install --frozen-lockfile` supplied the workspace dependencies,
and the ordinary hook then completed. No hook was bypassed.

`950c6a57f` commits the complete Stage-1 decision set before any source or test
change. All five files were read back from the attached branch and compared
byte-for-byte to the worktree. The user's prompt supplied execution authorization;
there was no intermediate approval pause.

| Task | Decision at Stage-1 commit | Current evidence status |
| --- | --- | --- |
| GY-VC1 | `docs/superpowers/specs/2026-09-10-gy-vc1-decision.md@950c6a57f` | executed; `gy-lattice/vc1/verification.json@d71f407df` |
| GY-AS1 | `docs/superpowers/specs/2026-09-10-gy-as1-decision.md@950c6a57f` | blocked on GL-ARCH-FINAL-01; semantic receipts `gy-lattice/as1/verification.json@d71f407df` |
| GY-CR2 | `docs/superpowers/specs/2026-09-10-gy-cr2-decision.md@950c6a57f` | executed; `gy-lattice/cr3/verification.json@c817314b4` |
| GY-CR3 | `docs/superpowers/specs/2026-09-10-gy-cr3-decision.md@950c6a57f` | executed; `gy-lattice/cr3/verification.json@c817314b4` |
| GY-CR5 | `docs/superpowers/specs/2026-09-10-gy-cr5-decision.md@950c6a57f` | executed by reuse and fresh verification; `gy-lattice/cr5/verification.json@c817314b4` |

Concurrency is bounded to three workstreams: VC1; CR2/CR3; AS1. Root completed
CR5's architectural investigation before starting the third agent and coordinates
shared work and separately authors AS1's oracle. After AS1's semantic work closed,
that stream performed CR5 verification. The closed VC1 stream later prepared only
the final runner. At most three workstreams ran concurrently. Root serializes commits,
README/initializer changes, the plan table and this journal. Source and fixtures
are exclusively assigned by path. No shared DuckDB, fixed port or browser station
is used. Reviewers classify new versus repeated classes before proposing repair.

## Findings that determine execution

**GL-CR5-01 — the historical defect was already repaired in the supplied base.**
The initial `GGA-ADJ-01` witness is followed in its own journal by `GGA-ADJ-02`,
`GGA-GATE-02` and `GGA-PA1-05`. Those findings and commit `d421575d3` deliver the
shared non-producing verifier, both production intakes, retained predecessor
replay and complete consumer-subject binding. Reading only the beginning of that
journal would have rebuilt a closed mechanism. The CR5 decision therefore chooses
fresh behavioral and removal verification. No CR5 production source edit is
planned. The source owner is
`src/polisyos/data_forge/domains/academic/batch/claim_adjudication_verifier.py@992aa493f`.

The five explicitly selected baseline test functions collected 17 parameterized
cases and passed in 29.62 seconds, exit 0. Full output:
`gy-lattice/root/raw/cr5-baseline.txt`. This preliminary count is not a claim about
all grade consumers or complete CR5 acceptance.

**GL-TABLE-01 — the complete initial standing table matches the prompt.**
Two separately written parsers (anchored regex over the entire section and a
line-state/cell parser) agree on all identities and statuses in the single
Markdown file's complete §8.5: 74 = 50 executed + 17 not_started + 5 blocked +
2 not_executed. Every commissioned row starts `not_started`. Initial parser
attempts exposed the heading level and bold-wrapped status cells and refused;
neither was counted as a census. The final delivery checker must compare full
rows against the lane base and permit movement only in the five commissioned IDs.

**GL-ARCH-BASE-01 — full architecture gate ran; freshness could not run.**
The sole gate command was:

```sh
PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.:src .venv/bin/python -m tools.cli architecture guardrails check > docs/superpowers/journals/gy-lattice/root/raw/architecture-base.txt 2>&1
```

Exit 1. The emitted finding is `required_freshness_environment` /
`probe_environment_preparation_failed`: the gate-created interpreter aborts with
SIGABRT because `@rpath/libpython3.14.dylib` cannot be found. Required generated
freshness is **unrun**, neither passed nor skipped. The complete output is retained
at `gy-lattice/root/raw/architecture-base.txt`. This lane does not repair or sync
the gate, conceal the failure, or invoke the debt-ledger checker. The final gate inspected the frozen integrated source and triggered the explicit
new-deep-import stop recorded in GL-ARCH-FINAL-01.

The local offline `uv sync --frozen --extra lint --extra test --extra runtime`
could not find cached jaxlib. The isolation-local CPython 3.14 environment instead
reads the existing dependency directory through a local `.pth`, as prior lanes
did. Import-origin verification resolves `polisyos` to this worktree, with pytest
9.0.2 and Pydantic 2.12.5. This dependency reuse does not establish that the gate's
separately created environment can build.

## Independent oracle and review record

**GL-AS1-ORACLE-01 — independent expectation seal, before subject execution.**
Root authored the complete 63-row TSV from research and reviewed stimulus inputs,
without reading the new subject source or observing its answers. Two independent
input-ID walks (JSON structure and lexical case keys) reconcile with the separately
expanded expected family set. The expectation SHA-256 is
`ed74752c6e965bc5aabc4c0f8cd6d111ccf4f227646d46433223307bc001a3e0`;
the input corpus SHA-256 is
`84de2b1384f0a6262398620491113bf4d55449667b847b4dbbd9e84120d00f99`.
The checker must appoint these literal identities rather than compute a trusted
identity from whichever file it happens to read. These seals freeze the synthetic
assurance manifest, not a governed institutional epoch or authority artifact.

The isolated oracle shares no decoder, fixture loader or comparator with the
subject. An actual readable subject-source probe and forbidden JSON import prove
the process boundary. Removing that boundary yields
`oracle_isolation_not_enforced:subject_read`; decoder, loader and comparator
dependency attempts each refuse before grading. All ten targeted oracle tests
passed, exit 0, and ruff passed. Complete deciding outputs are
`gy-lattice/root/raw/as1-oracle-tests.txt`, `as1-oracle-ruff.txt`, the four
`oracle-{decoder,loader,comparator,unconfined}.txt` probes, and
`as1-oracle-seal.txt`. These checks do not yet establish that the subject passes.

Two stimulus-review findings were the same P32/P37 witness-binding class. The
first required substantive finite terminal witnesses; the second widened binding
to the complete demand, actual assessed objects and actual finite alternative set.
The bounded residual is explicit: finite synthetic proof is not completeness of
the real world's causal models, institutions or providers. Further examples of
that residual do not trigger an open-ended institutional subsystem build.

**GL-AS1-INPUT-02 — the independent oracle caught a malformed adversary.**
The first live subject run failed with 24 field differences over all eight form
cases. The fixture generator had aliased candidate facts and owner requirements;
removing a candidate fact also removed the corresponding demand. This is a new
fixture-construction class, distinct from the bounded terminal-proof residual.
The correction restores the eight complete owner requirements while preserving
the missing candidate fact and plausible signature. Root checked every restored
key set against the eight distinct substantive obligations. The expectation file
and all case IDs remain unchanged. The corrected input SHA-256 is
`5ba11a2f0d80dca0fca8ff30f6544d01b79e7e0be412e0eb8d0c5498ea22ad13`;
the failed deciding output is `gy-lattice/as1/raw/baseline-first.txt`.

Commit `30dd80249` contains the oracle program/tests and the initial seal record;
the TSV itself was omitted because the existing broad `*.tsv` ignore matched it.
An append-only correction adds a narrow tracked-artifact exception and the sealed
TSV. Branch readback identified the omission before any delivery claim.

**GL-CR2-01 — expansion is a state property, not an event label.**
Root independently adjudicated the restart review against OPS-R5 `AUD-F06`,
`amendment-state-invariants.md`: `protected_restart_or_expansion_has_fresh_restart_evidence`
applies to actual exposure expansion even when an event is named `observe`.
The oracle revision is authorized by that explicit conjunct, not by agreement
with the implementation. Same-class deeper P37/P38 correction widens the gate;
no competent external restart authority is inferred.

## Final deciding evidence and binding falsifiers

**GY-VC1 — executed, with declared candidate scope.**
`docs/reference/canonical-vocabulary-crosswalk.v1.json@d71f407df` contains 98
entries in 13 declared source vocabularies. Complete independently extracted
source sets reconcile with the emitted entry set. Fifteen explicit test functions,
final recomputation and ruff pass. Corrupting one semantic loss field fails the
checker; removing registry independence, blocking-loss refusal or the actual
consumer's namespace admission produces its own checker failure. The existing
Atlas status is preserved. FM-OPS-17's second movement vocabulary is unreachable
through this admitted channel: an arbitrarily named second namespace is refused.
This does not claim a proof over arbitrary future bypass code or a second physical
causal ontology. Binding falsifiers and complete output are in
`gy-lattice/vc1/verification.json@d71f407df`.

The relation-claim-strength mapping onto `maximum_claim_strength` and capacity-stage
mapping onto `maximum_commitment_stage` are explicit conditional rulings with
reasons; capacity load remains separate. Estimand binding strength, legal/normative/
write operations and assurance levels remain **absent/unallocated**, with precise
owner-supply requirements. No research term or institutional appointment was invented.
Predicted institutional families are reconciled against delivered AQ1/CR1/CB1/ML1
contracts; `AssurancePacket`, `CandidateAssuranceResult` and `AssuranceReceipt` are
recognized, while `RTLSourcePack` is not promoted to co-authentic legal authority.

**GY-AS1 — semantic conjunction passes; architecture acceptance blocked.**
`docs/reference/gy-acquisition-assurance-corpus.json@1b76ac477` seals 63 cases;
`docs/reference/gy-acquisition-assurance-oracle.tsv@8012dc035` is independently
owned and unchanged after the first subject result. The baseline passes. Seven
mutants each fail with their own witness and reason. Decoder, fixture-loader and
comparison-helper sharing each fails at the isolated oracle boundary; removing
isolation permits an actual forbidden source read and therefore refuses grading.
The battery executes AQ1's real acquisition, receipt verifier and demanding-owner
seams with one bound requested-use/evaluation-time context. Negative tests prove
consumption rather than constructor shape. Exact nodes, own-reason results and
full logs: `gy-lattice/as1/verification.json@d71f407df` and the root receipt.
These passing semantics do not waive GL-ARCH-FINAL-01. The unresolved conjunct is
architectural acceptance of its new `fabric.evidence → core.artifacts` import.

**GY-CR2 — executed through CR1's durable store, not a second machine.**
`src/polisyos/runtime/quality/constrained_response.py@c817314b4` recomputes the
factor history from CR1 records, using aggregate/sequence identity and the existing
submit/process/snapshot path. No independent durable head or replacement lifecycle
is introduced. The complete 500-member E/X/V/C product and origin predicates are
exercised, including pairwise and three-way forbidden tuples. Direct CR1 intake
cannot bypass the predecessor/genesis rule when history is read. Duplicate,
conflicting, stale-head and late events are checked; a late event produces
correction or supersession while prior bytes remain unchanged. Actual exposure
expansion requires restart evidence even under an `observe` label. The Atlas
projection adds zero statuses. Binding falsifier: remove the substantive tuple,
predecessor or expansion property while retaining its markers; the relevant
behavioral assertion fails. Evidence: `gy-lattice/cr3/verification.json@c817314b4`.

**GY-CR3 — executed for candidate custody, with external execution refused.**
`docs/reference/response-corpus/packets.json@c817314b4` contains 20 packets across
seven response families and 42 event occurrences. The final sealed transition
oracle is `docs/reference/response-corpus/oracle.toml@c817314b4`; its independent
stdlib interpretation shares no subject decoder or semantic comparison closure.
All twelve exact OPS-R5 §6.3 guardrail counters read zero on the corpus, and all
8 predeclared high-harm custody-containment demands remain preserved. This is not
proof that an external institution executed containment. Each of the 20 proxy
pairs has equal headline movement but a distinct decisive local reason; removing
each pair's discriminator fails locally rather than through a shared failure.

The final frozen-source wave ran 21 explicit test functions (19 new functions and
two unchanged CR1 importer functions, including the actual kill/duplicate test),
exit 0 in 51.000 seconds. The final corpus checker exits 0; corrupting the oracle
exits 1 with `oracle_seal_mismatch` and `oracle_recompute_mismatch`; ruff passes.
Complete commands, actual outputs, durations and source digests are retained in
`gy-lattice/cr3/verification.json@c817314b4`. Earlier 40-event output is superseded
by the reviewed 42-event corpus, whose additional redesign suffix exercises the
actual withdrawal/observation history.

**GY-CR5 — executed by composition and fresh verification of the existing repair.**
The two live intakes already share substantive evaluator authentication and batch
observation recomputation at the supplied base (GL-CR5-01). Twenty-five explicit
test functions expand to 46 cases, independently reconciled against collection;
all pass. Three process-local removals, without file edits, turn the battery red:
removing only signature verification fails four intake negatives; removing only
observation equality fails two; removing current-subject binding fails six
consumer negatives for cause variable, direction and scope. Authenticated unfavorable
grades are retained as false and yield zero graph/conflict publications.
Institutional appointments remain typed-empty. The complete 15-path selected
source/test/fixture set is byte-identical to `992aa493f` before and after the runs.
Evidence: `gy-lattice/cr5/verification.json@c817314b4`; reproducible removal helper:
`gy-lattice/cr5/verify.py@c817314b4`. No closed production owner was repaired again.

## Actual callers and deferred surfaces

| Mechanism | Non-test caller and bounded delivery |
| --- | --- |
| VC1 movement admission | `src/polisyos/runtime/quality/constrained_response.py@c817314b4` calls the canonical admission owner. |
| VC1 total projector/checker | `tools/quality/validation/check_canonical_vocabulary_crosswalk.py@d71f407df` recomputes all entries and executes refusal probes. Atlas UI is deferred to DS12; live monitoring/learning to GY-O1/GY-O3, posterior assertion to GY-AS3. |
| AS1 assurance adapter and independent oracle | `tools/quality/validation/check_gy_acquisition_assurance.py@1b76ac477` invokes the adapter, actual AQ1 lifecycle/consumer and isolated oracle. This operational checker is a real non-test caller; its adapter's architecture acceptance is blocked. Open-world institutional completeness remains refused. |
| CR2 persisted factor machine | `src/polisyos/runtime/quality/response_corpus_evaluator.py@c817314b4` replays through CR2 into CR1. Live operational dispatch is deferred to GY-O1/GY-O3 because these corpus tasks do not own a scheduler or external executor. |
| CR3 evaluator and sealed oracle | `tools/check_response_corpus.py@c817314b4` invokes the evaluator and independent oracle. Runtime API/dashboard publication is deferred to DS12; no test-only importer is counted as that surface. |
| CR5 authentication/recomputation | Existing Scientist `admit_champion`/`adjudicate` and DataForge `load_admitted_batch` call the shared verifier; graph/conflict consumers replay current subject binding. Exact owner paths and immutable source digests are in the CR5 receipt; all remain at `992aa493f`. |

No new sovereign institutional executor, appointment issuer, legal-equivalence
oracle, causal-truth verifier or notification channel is claimed. Candidate
identity transport does not authenticate institutional provenance. A finite set
of terminal acquisition witnesses does not establish the completeness of every
real-world model, provider or institution. A signature's authenticity does not
establish the real world's causal calibration. These are declared limitations,
not silently favorable defaults.

## Census, preservation and final runner

The VC1 census walks every tracked `policy-engine` `.py` member at the lane base:
6,136 overall, 5,207 under source plus tests, 2,647 under source. A second method
reconciles the complete path set and exact symbol results. **5/12 exact predicted
names is a source-only result**, not a claim that seven capabilities are absent.
Unreadable members refuse the census. The delivered vocabulary is inspected before
adjudication. Likewise, the route list contains twelve unique explicitly named
routes by two independent parses and the complete routing table; the inherited
narrative's “thirteen” is not reproduced as arithmetic. Full output is cited by
the VC1 receipt. Digit-bearing omissions discovered during review were the same
P35 class one level deeper and were closed with general qualified-identity parsing.

`gy-lattice/check_delivery.py` uses two independently written parsers over all
74 authoritative §8.5 rows and reconstructs the entire base plan by restoring only
the five authorized rows. Both agree on the final distribution:
**54 executed + 12 not_started + 6 blocked + 2 not_executed = 74**.
Exactly GY-VC1, GY-AS1, GY-CR2, GY-CR3 and GY-CR5 moved. Corrupting a sixth row
fails with `uncommissioned_or_missing_row_movement:GY-AQ1`. Registers and pre-existing
production source remain unchanged; no other plan bytes changed.

`gy-lattice/run_targeted_verification.py` is the final runner. Its default is a
read-only listing of exact commands and literal file/test-node selectors; execution
requires explicit groups. It preserves each sole subprocess's exit, full output
and duration, and requires expected failures to exhibit their own reason. No
broad or directory-wide test selector is used. Actual workstream receipts remain
the evidence of the completed waves; the runner was not used to repeat them after
the architecture stop. Metadata-only ruff, listing and delivery checks passed.

Source was frozen after all substantive reviews and before each final expensive
wave; no product change or product gate followed GL-ARCH-FINAL-01. Decisions,
mechanisms and evidence were committed at clean boundaries and read back from the
attached branch. CR2/CR3's first-delivery v1 seals and the documented pre-delivery
oracle revision are measured from `992aa493f`; no governed epoch bump or previously
published artifact reissue occurred. The revision receipt cites old/new seals and
the delta, without embedding either tracked artifact. Raw outputs are ignored
beside their receipts and identified by SHA-256. No push or baseline sync occurred.

## Incidental findings routed to their owners

| Finding | Destination and disposition |
| --- | --- |
| GL-ARCH-FINAL-01: AS1 introduces a deep import | Architect / GY-AS1 boundary acceptance. Blocked pending an explicit architectural ruling or authorized alternative composition; no sync or source repair attempted. |
| Required freshness environment SIGABRT / missing libpython | Team DevEx architecture freshness owner. Check remains unrun; the final full gate is failed, never green or skipped. |
| Three absent semantic vocabulary owners and two conditional mapping rulings | `int-r2-ceiling-vocabulary-owners`. Exact prerequisites and rulings are in the versioned crosswalk; architect owns register updates. |
| Predicted institutional names differ from delivered contracts | `w5-institutional-authority-slots`. Use the delivered-family reconciliation, with its explicit source-file denominator. |
| Twelve explicit routes versus inherited thirteen | GY plan / wave-5 routing-map owner. Only VC1's commissioned standing row is corrected here; surrounding inherited prose is untouched. |
| Builder caller standing | `gy-builder-mechanisms-have-no-production-caller`: CR1 now has the CR2 path; AQ1 has the AS1 checker path with architecture blocked. CB1/ML1's closed-task callers are not modified. |
| Deferred live dispatch, learning, posterior assertion and UI | GY-O1 / GY-O3 / GY-AS3 / DS12 respectively. No standing movement for those tasks. |
| Client-computed public verification badge | `public-decision-verified-badge-is-client-computed`, Atlas owner; already registered and outside CR5's scoped repair. |
| Stale aggregate prose immediately below the authoritative task table | GY plan owner. The unchanged prose still carries a historical distribution; the complete two-parser result above governs this handback. Only the five commissioned rows may be edited here. |
| Inherited prose claiming guardrails invokes the debt ledger | GY plan / architecture owner. The actual runnable gate was executed; prose outside the five authorized rows was preserved. |
| Closed review classes: marker-only proof, incomplete binding, sampled identifiers, proxy predicates | Existing P29/P31/P32/P35/P37/P38 register rules. Fixes and bounded residuals are recorded above; no duplicate narrative rule added. Register reread before closeout. |
| Private success Literal and transitive-runner-closure-unbound | Explicit nowhere in this lane: settled exclusions, no reopen or incidental repair. |

Neither `docs/plans/active/DEBT-REGISTER.md` nor `docs/plans/active/LEDGER.md` was
edited. This journal routes findings; the architect writes those registers.
