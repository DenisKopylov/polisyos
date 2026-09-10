# GY builders C journal

Lane base `07c89304d`, attached branch `codex/gy-builders`, 2026-09-10.
Decision: `../specs/2026-09-10-gy-builders-c-decision.md`.
Source changes remain prohibited until the parent freezes all workstream decisions.

## Stage 1 — research and owner execution

Read GY-CB1/GY-ML1 task definitions and §3.5.5/3.5.6; ratified W5-K02/W5-K06;
WP-09/WP-11/WP-12; INT-R3 benchmark, operational addendum and controlling amendment;
INT-R6 protocol, FX-001–003 and W5 routing map; CONTRIBUTING and failure register.
No institutional owner has been appointed; no withheld proposition is decided.

`gy-builders/c/owner_research.py` executed the complete tracked `src/` census at the lane base:
2,851 tracked source files, of which 2,640 are Python. A second method, an OS tree walk,
reconciled the complete Python identity set against `git ls-files`. The AST census parsed
172 Python files under `src/polisyos/runtime/quality/`, 43 under `src/polisyos/lex/`, and
28 under `src/polisyos/scholar/`; no unreadable member was omitted. Exact text searches
across all 2,851 tracked `src/` files found no `human_comprehension_established`, `MAEP`,
`operator comprehension`, `behavioural_contract` or `behavioral_contract`. These are bounded
text observations, not proof that no differently named owner exists. Owner placement comes from
the complete topical definition census plus inspected canonical implementations.

Full output is preserved at
`gy-builders/c/raw/stage1-owner-census.txt@d0676d0fff58ef388cb97b08cdb67a791b526a0e087030beacfd30f04e4cdc97`.
It is gitignored because it contains a large source-derived definition inventory. Read owner bytes
are bound inside that receipt; their tracked source is cited instead of embedded.

C-OWNER-01: CB1 composes `RuntimeDiagnosticEventLog` and `DiagnosticEvent` through the existing
producer-execution event and diagnostic CAS payload family. No new event storage/authority owner.
C-OWNER-02: ML1 extends Lex semantic evaluation, adjacent to `knowledge/benchmark.py` and
`normpack/legal_authority.py`. Scholar source acquisition stays upstream; imported source bytes
remain candidate evidence. No second status lattice or legal competence owner.
C-OWNER-03: root and C are independently allocated census parsers; only domain and output interface
were shared before implementation. Reconciliation compares full maps and byte identities, never
counts alone. Corrupt-field negative is required after allocation.

Existing-owner gate: only
`tests/unit/runtime/quality/test_runtime_event_log.py` and
`tests/unit/runtime/quality/test_diagnostic_event_contract.py`.
Complete output: `gy-builders/c/stage1-existing-owners.txt`.
Command uses venv first in PATH and `python -m pytest`; first invocation failed during collection
with `AcquisitionActionHeadRecord` circular import when ControlPlaneStore is imported before the
runtime control API. No product path was changed. The failure is a measured collection result, not
an inherited-debt claim; a canonical-startup-order replay will be recorded separately.

No predecessor is replaced/subordinated; no StrangleReceipt is currently applicable.
No governed epoch transition is planned. A later need would declare the transition from the immutable
merge base `07c89304d` before changing governed bytes.

Default architecture gate: `not_completed` because its compiler chain invokes prohibited
`check_debt_ledger.py`. Neither debt/ledger file was edited. No full/directory-wide suite was run.

## Claims that stay refused

GY-CB1's claim that humans comprehend PolicyOS stays refused: the emitted result has a non-settable
false property and all trial/conformance evidence in this lane remains candidate-only; WP-09
per-cell numerical claims stay typed empty.

GY-ML1's claim of legal equivalence stays refused: no signer, qualified holder or trust root can be
filled by this lane, and every candidate result reader enforces the complete declared
proposition/purpose/holder/context denominator before returning a bounded diagnostic.

## Routed findings outside this owner

- W5-R3-Q06 retains item adjudication and governance-loss appointment; no appointed study authority.
- W5-R6-Q05 retains per-jurisdiction co-authentic reconciliation.
- W5-R6-Q07 retains institutional security owner, trust roots and key-custody appointment for any
  future signed certificate; this lane builds a form with those slots empty.
- WP-09, WP-11 and WP-12 retain their withheld statements; no local constant closes them.
- Arbitrary natural-language semantic extraction/verification is not established by candidate frame
  equality. Its authority-grade producer is explicitly nowhere in this new mechanism; qualified
  adjudication remains the prerequisite, and the refusal is structural.

Design review amendment: internal per-cell exact-binomial estimator requires explicit candidate alpha,
while public bounds remain withheld; MAEP implements resolved-byte integrity and append-only
revocation/use-time checking now even though signer/trust roots remain empty.

Stage-1 startup-order replay completed RC0: all 22 cases in the two named files pass after importing
`polisyos.runtime.http.services.control.api` before the direct store import. Full deciding output is
`gy-builders/c/stage1-existing-owners-startup-order.txt`; executable replay is
`gy-builders/c/owner_test_replay.py`. B independently confirmed the facade-first startup order and a
real SQLite reopen/duplicate/checkpoint execution. The earlier collection error remains recorded and
unrepaired. This establishes the existing event/CAS bridge under the supported startup order.

C-OWNER-04: readback located the existing detached-signature/Ed25519 verifier owner under
`core/artifacts/store.py` and `core/artifacts/signing.py`. MAEP will call its unsigned strict
verification with empty trust roots; no second crypto engine and no signing call.

## Stage 2 — red-first build

Parent released execution after decision checkpoint `c628361c5` was read back from the attached
branch. New tests were written before the three new owners. Separate W5-K02 and W5-K06 tests
exercise comprehension refusal and out-of-denominator read refusal; FX-001–003 are separate
parameterized negatives. No real participant, translation approval or legal source authority is
represented by the synthetic corpus. Source and target text/frame pairs are explicitly candidate
fixtures; text-to-frame semantics remain unverified.

### Execution receipts and review closure

| Gate | Outcome | Complete output |
| --- | --- | --- |
| Initial missing-mechanism negatives, three named test files | RC1, before source existed | `gy-builders/c/raw/red-first.txt@d85726f2894e2f92f1c19495d5936da718a6ac5d1ed5b8b6d172a0eefd3ea8f9` |
| First implementation, same named files | RC1, canonical tagged-float readback exposed | `gy-builders/c/raw/green-first.txt@cea40db5a96d356bf762481d6f159691ed5ec26bd2296233fb0be1e457cc9285` |
| Clock/population/fixed-stop falsifiers | RC1, actual property failures | `gy-builders/c/raw/red-clock-population-stop-replay.txt@4ccbe1bf911cec228239a5f0015cf8866e0294defac30516cb70cc38b7a9be33` |
| Batched CB1+ML1+parser A cases | RC0, 31 passed | `gy-builders/c/green-batched.txt` |
| Ruff on the three source and mirrored test files | RC0 | `gy-builders/c/ruff-batched.txt` |
| Review C-R01 source-content/check-plane/deep-input negatives | RC1 before repair | `gy-builders/c/raw/red-rtl-surface.txt@f2cc3886e2fa6e60dcc24af05edf82b1be1a7bf57855293a58af983661bb8b0a` |
| ML1 and parser A delta after C-R01 | RC0, 22 passed | `gy-builders/c/green-rtl-surface.txt` |
| Remove W5-K02 invariant in memory, keep markers | RC1, unchanged W5-K02 test fails | `gy-builders/c/raw/removal-comprehension.txt@84a9ea9377986fc843fc0344ee6256f552b080a1c750278d25fa1e095f1920f6` |
| Remove non-result consequence in memory, keep markers | RC1, unchanged no-eligible test fails | `gy-builders/c/raw/removal-eligible.txt@f91d39e5aa7a28fa1bd44a34519f6a1440cef62fa36c5530714db8efefc1fa84` |
| Remove W5-K06 scope guard effect in memory, keep markers | RC1, unchanged out-of-denominator consumer fails | `gy-builders/c/raw/removal-scope.txt@3eb1169615112014c94b5c4a15d1e736a3313d76dc0ab83a98141c5733688977` |
| Remove semantic refusal consequence in memory, keep markers | RC1, all FX-001–003 consumer cases fail | `gy-builders/c/raw/removal-semantic.txt@e8632408903f6c56e4b7dd41b48ea63c3f72ecdd866a32e26fcf1f611b173252` |
| Standalone real event/CAS demonstration and readback | RC0 | `gy-builders/c/raw/demonstration.txt@cc83a953681f8146ec6da03218fd1a2392c6049f12f16fbeef1085db6c8dbc5c` |

The removal recipes are `gy-builders/c/removal_probes.py`; they compile the real module with one
property removed in memory, leaving fields and marker names present, and call unchanged tests.
Production files are untouched by probes. `raw/red-clock-population-stop.txt` records a tooling
non-receipt: disabling pytest plugin autoload while retaining the repository benchmark option was
rejected; its replay explicitly overrides addopts. No product failure is inferred from that attempt.
The initial Ruff output is retained at
`gy-builders/c/raw/ruff-first.txt@5ee0f57a24fba680be5887ac20607b6d7412930fcb8f04b57d60b3c218d0b215`.
Oversized raw outputs remain gitignored and were not force-added.

NEW C-R01 (P01/P02), found by root review: the initial RTL pack had no source-content chain.
Closed by candidate Hebrew/mixed-direction text production→CAS→exact scope/content readback;
wrong/missing scopes and content drift fail. The same owner now publishes the broader protocol's
`not_established` check plane. Root's delta review accepted this closure. No RTL source authority,
rendering/accessibility adequacy, jurisdiction admission or UI capability is claimed.

Clock/order conflation, missing participant aggregation and the fixed safety-failure consequence
were caught before freeze by separate red tests. `elapsed_seconds` is optional measured time;
sequence only orders events, and absent time yields no time-to-correct. Distinct pseudonyms contribute
to each safety-cell opportunity denominator. Per-cell candidate exact-binomial estimates use the
explicit design alpha; public upper bounds and any high-confidence threshold remain withheld.
Raw confidence/correctness information is retained without inventing a confidence cutoff.
The canonical persistence failure was fixed by reusing `core.canon.from_canonical_obj/bytes`, not by
creating another float serializer. Parser A's unreadable recursive shape now returns `ambiguous`
through the generic exception boundary; no depth limit is presented as semantic acceptance.

C independently reviewed root's complete parser B/reconciler and their two exact test files only
AFTER both independent implementations were complete. No parser code/helpers were shared during
construction. NEW C-REVIEW-01 (P35/P38): an alternate directory was described by the default path
in its receipt. Root first produced the failing alternate-directory test and corrected the emitted
path to the actual resolved input; C read back the one-line delta and accepted it. The byte
before/between/after check establishes repeated-checkpoint stability for quiescent local source;
it is not an atomic filesystem snapshot under adversarial ABA writes. That bounded concurrent-edit
residual is disclosed, not silently called atomic custody. Root owns the frozen final census and
its independently corrupted-A, corrupted-B and receipt-drift receipts.

### Initial durable demonstration and exact denominators (schema 1 history)

The standalone runner consumes the entire tracked corpus JSON files, crosschecks raw item identity
against validated identities and the declared factorial, then produces real runtime timestamps,
event IDs and CAS references. Under
`tests/fixtures/runtime_quality/operator_comprehension.json` (one JSON file), the complete
40-item synthetic corpus has 32 sealed items = 8 declared constructs × 4 declared modalities, plus
8 training items. The initial decorated-identity split was later falsified by C-PARTITION-01;
these schema-1 receipts are historical, superseded by the schema-2 run below. The run records
128 raw events, produces
`comprehension:a21a942a95c046a29ff8a71596dcfdb0`, persists payload
`sha256:264e70160fef3e61ff0a8838d033c1155d7c8a76d2c07096760460cf97f9b931`, and independently
reads its candidate result back through the diagnostic-event/CAS consumer.
Corpus source is
`tests/fixtures/runtime_quality/operator_comprehension.json@646172cfe30418249032999f929f15ae6abfc910e90d6e2fc85308694cf54f37`.
No observed real-operator result is implied by the synthetic event count.

Under `tests/fixtures/lex/multilingual_assurance.json` (one JSON file), all three declared
proposition IDs are traversed and independently checked for unique identity. Corrected EN–UA
candidate pairs produce unsigned bounded results; their defective siblings are separately falsified
by the exact FX-001–003 tests. The actual CAS receipts and unestablished check plane are in the full
run output cited above, not recopied here. Source is
`tests/fixtures/lex/multilingual_assurance.json@859c18a512f8d3eee71bbc63d05bd5f72cb59ef378ef7ac37d7032864f7ece68`.
The RTL producer persists the actual mixed-direction text as
`sha256:b41b79691b6925752f0467be536d2134cc9eb76c2acd1f5d6ebe9bad79f355d2` and the exact scoped
reader returns it with all WP-12 evidence slots empty. The untracked CAS and SQLite records remain
under `gy-builders/c/raw/demonstration/`; the receipt binds their local location.

### Task standing for lane closeout

| Task | State | Deciding evidence and falsifier |
| --- | --- | --- |
| GY-CB1 | `executed` (commissioned candidate instrument) | Synthetic producer→durable diagnostic event/CAS→recomputed consumer; exact sealed/training source and complete declared-family union disjointness checks; no eligible result stays `not_established`; W5-K02 and non-result property-removal probes fail unchanged tests. |
| GY-ML1 | `executed` (commissioned candidate assurance machinery) | Real scoped CAS reader rejects denominator escape; FX-001–003 each refuse and corrected siblings compare only as candidates; changed modality/text binding refuses; source-content chain and independent parser census are executed; W5-K06 and semantic-removal probes fail unchanged consumers. |

These states concern the commissioned mechanisms. The final lane journal supplies the frozen
cross-workstream gate and post-commit branch readback; this journal does not claim an uncommitted
working tree is a delivered branch. No predecessor was replaced or subordinated, so no
StrangleReceipt applies. New audit/readback surfaces are in scope; a product UI and new HTTP route
are `surface_out_of_scope` for these synthetic instruments, with Atlas as their future integration
consumer. Real studies, multilingual semantic/legal certification and institutional appointments
remain absent as explicitly required by the commission.

GY-CB1's human-comprehension claim remains refused by the non-settable false property,
sealed-input consumer recomputation and candidate-only projection; WP-09 keeps public confidence
bounds and thresholds withheld even though the internal estimator executes.

GY-ML1's legal-equivalence claim remains refused by exact proposition/purpose/context/holder
scope checks, an empty signer/holder plane and strict existing cryptographic verification with no
trusted signing root; WP-11/WP-12 and the institutional adjudication gaps remain explicit.

Failure register was reopened before closeout. The closure patterns are P01/P02/P03, P05/P15,
P27, P29/P32/P33, P35, P37/P38. No new recurring class required a register edit. Two Pydantic
warnings about the candidate `construct` field shadowing a deprecated BaseModel method are recorded
as cosmetic source debt, without a post-freeze rename. Default architecture gate remains
`not_completed` under the prohibited debt-compiler rule; no full suite, debt compiler, debt/ledger
write, push, rebase, stash or institutional appointment occurred in C.

Frozen current locale census completed after parser A's final change:
`gy-builders/root/raw/census-final.json@d4e969ea0ca2a4174d5665f26b8805ad229267c297a2337113b97f32e871e2ce`.
Path denominator is the actual resolved `apps/runtime-dashboard/src/shared/i18n/locales/*`;
file-type denominator is all direct members, exactly three JSON catalogues. Independently decoded
full maps agree: EN 2,879 string leaves; UK 2,879, all shared, 909 identical decoded strings; RU
2,456 leaves, 2,452 shared, 1,930 identical, 427 English paths missing and 4 extra RU paths.
The crosscheck is whole-map equality from independently allocated grammars, not equality of the
counts. These are structural/identity facts, never translation quality or legal equivalence.
Root's corrupted-A and corrupted-B invocations each returned RC1, healthy receipt replay RC0,
and a corrupted UK identity numerator receipt RC1. Complete outputs are retained in root's receipt
folder and bound by the final lane journal.


### C-PARTITION-01 — source identity closure and declared semantic residual

B independently found a NEW presentation-versus-source identity defect: every original training
stimulus reappeared under presentation wrappers in the sealed corpus. Its complete 256-pair scan
and independent inverse scan both found 32 matches over 40 items (8 training, 32 sealed):
`gy-builders/b/cb-partition-review.txt@fb7c978c0cc2a6abbe0de1f52c2ad2a8b057d0d666fb0e876cda21c31c36985e`.
The earlier schema-1 "disjoint" implication was a P38 proxy claim and is superseded here, not
preserved as evidence of independent item families.

Four source-identity falsifiers were first observed failing through the real owner:
`gy-builders/c/raw/red-source-partition.txt@31a7f9974b3237490945be04a7b9f78102f321a3a449b9b24ed2e5d2eb1611d4`.
The owner now generates displayed content from undecorated `stimulus_text`, requires that stimulus
in its declared `stimulus_family`, and derives identities from source bytes. Actual training
examples were replaced. Source metadata now distinguishes artifact `authority_level=candidate_only`
from declared synthetic `target_authority_level`; neither creates an appointment. Candidate corpus
schema and new producer version move from 1 to 2; no pre-existing governed epoch is changed.

Root and B then found the SAME structural class one level deeper: a whole-family hash misses a
shared member when an extra member changes the hash. The own sibling first failed with
DID NOT RAISE, and B independently reproduced admission before the widening:
`gy-builders/c/raw/red-family-union.txt@b60bba25e5bdf17487b4f18d93b087312c2ae0cd107e5fcd592437c52f837f1e`;
`gy-builders/b/cb-partition-delta-review.txt@5e96fd5556109d98a16eee89372d1b6db00f01c6ab86a90d9231aca3d4972985`.
Per P40 the predicate was widened to the quantity the property needs: disjoint complete UNIONs
of all actual declared-family member bytes across partitions. It does not compare whole-family
hashes. This single generic member-set rule covers added, removed and reordered family members.
B read back the widened source and its unchanged actual-owner probe rejected the overlapping member.

Final CB targeted file: RC0, 17 passed in 33.66 seconds,
`gy-builders/c/green-partition-union.txt@65f6e2f0da61a99abf0ba3282cf2f9bb3bb0c11840de5ea318f328d8b260a622`;
Ruff RC0 at `gy-builders/c/ruff-partition-union.txt`.
The standalone complete fixture witness compares all 256 training/sealed pairs and independently
inverts every family member: both methods find zero overlapping pairs. It then deliberately submits
a different-byte paraphrase of the sealed missing-observation example, observes structural
admission, and records `semantic_independence=not_established` and human comprehension false:
`gy-builders/c/raw/partition-demonstration.txt@5da9c3adca387c6f2664f966bfab7feb5d3de7463ce2247ad16b26638e004988`.
This is the executed bounded residual, not a semantic-independence claim. The smallest missing
capability is independently appointed item/family adjudication at W5-R3-Q06, confirmed absent by
the stage-1 source-owner census and institutional row. No paraphrase normalizer or new adjudicator
was invented; further examples of that declared class consume no repair round.

Schema-2 durable replay RC0:
`gy-builders/c/raw/demonstration-v2.txt@9bbc633a194a658c9f34a4806bd28d3b4fb0ab73a93b8236027f83b5171edc00`.
The one current corpus JSON is
`tests/fixtures/runtime_quality/operator_comprehension.json@6dd22d7585ea1ef3c3ae10e27e49bf3e1fa36cb01dc39cd25bae0569ebbfa828`.
Its complete 40 items remain 32 sealed (8 constructs × 4 modalities) plus 8 training. The 128-event
synthetic run emits `comprehension:2cb3b3cb6b13428e8da36668097b846f`, persists
`sha256:2d48938b8656b923f6d6fc1f660c700a842efed6874b96f14a26153d541dc76e`, and reads back through
the existing event/CAS consumer with public upper bounds withheld, semantic independence
unestablished and human comprehension false. ML1's fixture and current-census denominator are
unchanged; the same standalone run replays its three candidate comparisons and actual RTL text.

Complete failure/removal outputs with trailing whitespace were moved intact under ignored `raw/`
and their references updated; no evidence bytes were trimmed and no oversized output force-added.
B final delta acceptance output: `gy-builders/b/cb-partition-union-review.txt@4c46f85884aa8998aadf0770f70998812e9750154fef3161737aef4dd96bc533`.
Actual union-property removal also returned RC1, with the unchanged family-overlap consumer test failing: `gy-builders/c/raw/removal-partition-union.txt@bf9193528da8e75e6daefaba980c2c8f5f6fb93eac7abd37e6166585a0eb3bc3`.
