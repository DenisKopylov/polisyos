# GY-GAP1 + GY-DEF5 obligation-instance identity journal

Date: 2026-08-19
Branch: `codex/gy-gap1-obligation-instance-identity`
Base: `068aab9df41f2aeebf7b83a80c7939b02d196a5d`

## Entry contract

This lane closes GY-DEF5 first as a claim-only correction, then enters GY-GAP1 directly under the
ratified remove-one acceptance test. It changes no other GY row, writes no revision-frontmatter
entry, and leaves line 7 of the GY plan byte-identical. The base line-7 SHA-256, including its
newline, is `f88d113f34f339f14d333cdd3fe6459cf0e73d449ec3bb5f026567276a14aa37`.

### P39 mechanism / companion split

- GY-DEF5 mechanism: `src/polisyos/pdc/_impl/gy_waist.py` only.
- GY-DEF5 companions: this journal, the GY-DEF5 standing paragraph, the complete repository-text
  census, and the confidence-deployment identity measurement.
- GY-GAP1 mechanism: `src/polisyos/pdc/_impl/gy_waist.py`,
  `src/polisyos/pdc/_impl/layer2_design_search.py`,
  `src/polisyos/runtime/quality/generation_cycle.py`,
  `src/polisyos/runtime/quality/promotion_sequence.py`, and
  `tools/quality/validation/check_layer3_gy_promotion_contract.py`.
- GY-GAP1 companions: focused tests, this journal, the GY-GAP1 standing paragraph, the exact-delta
  declaration, all induced hash receipts, and exactly these six permitted generated artifacts:
  `layer3_gy_promotion_contract.json`, `layer3_gy_generation_cycle_contract.json`,
  `layer3_gy_second_domain_cycle_entry_trace.json`, `layer3_gy_second_domain_pack.json`,
  `layer3_gy_second_domain_free_grow_gaps.json`, and
  `layer3_gy_depth_n_universality_contract.json`, all under
  `architecture/policy_design_case/`. The confidence artifact is a deliberately deferred companion:
  it must remain stale for one later joint-lane reissue and is not written in this lane. The N10a
  census and smoke-problem outputs are explicit byte-identity controls, not permitted deltas.

## GY-DEF5 entry and census

P37 provenance: internal enum/receipt totality is `recomputed`; world-level completeness is
`not_established`. P40 entry: implementation round 0/2. The mechanism is the docstring only; opening,
dissolving, or making the enum discoverable is explicitly out of scope.

Two independent complete scans at the base agreed:

- denominator: 9,873 tracked paths and 9,766 tracked text paths;
- `PromotionObligationClass`: 23 files and 214 literal occurrences;
- enum cardinality: 15 by both AST and lexical declaration scans;
- targeted universal/world-closure assertions: 16 lines in 11 files, with exactly one live
  violating claim—the `Universal N9 obligation-class denominator` docstring. All other matches are
  historical findings or explicit negative controls.

Closure witness: after the edit the live overclaim count is zero, while the enum declaration and
every behavioral producer/consumer remain byte-identical outside the docstring.

## Reconciled obligation population before GY-GAP1

At the pre-declaration source census, two independent structural walkers over all 1,170 tracked JSON
files (zero parse failures) agreed on 26 receipt-shaped objects, 390 obligation records, distribution
`{15: 26}`, maximum `(class, gate)` multiplicity 1, and zero repeated pairs. Committing the later
transition-declaration companion raises the current tracked-JSON denominator to 1,171 without adding
an obligation receipt, so the current population remains 26/390. The earlier 19/285 census
intentionally selected only current v2 owner-bound receipts. The remaining seven receipts / 105
records are v1 historical recordings preserved under the depth-N universality artifact; the full
blast-radius population is therefore 26/390.

Distribution by persisted artifact:

- depth-N universality: 17 receipts / 255 records (10 current v2, 7 historical v1);
- generation cycle: 2 / 30;
- promotion contract: 3 / 45;
- second-domain cycle trace: 4 / 60.

The real promotion-contract writer independently produced three current verification receipts, each
with 15 records, 15 distinct class/gate pairs, and maximum multiplicity 1. No canonical production
authority receipt is persisted; that population is `not_established`.

## Timing regime before source

All samples below were taken while the Atlas lane was active and are labelled `contended`; none is
promoted into a clean budget. The executor-declared ceiling was 600 seconds.

- Base promotion contract `--check`: validator 30.354552 s, process 47.15 s, success.
- Direct three-run census: 34.27 s, success.
- Fresh-worktree offline setup: tooling non-receipt after 0.99 s because the Python 3.14 `jaxlib`
  wheel was absent from the offline cache; zero tracked bytes changed. The worktree uses the already
  provisioned locked venv by symlink.
- Three-suite focused baseline: terminated at the 600 s ceiling after missing-worktree-data failures;
  non-receipt and not a budget sample.
- Root cause falsifier: after linking the canonical production data read-only, the first formerly
  failing N8 boundary test passed. Its duration remains contended.

## GY-GAP1 mechanism entry

The identity is producer-derived, not minted. `generation_cycle.ValueGateReceipt` owns two exact
receipt-consistency predicates and emits content-bound descriptors for them. N9 hashes a versioned
run scope over promotion rule version, design-problem id and content hash, candidate id and content
hash, and operation invocation id. After every N11 class-row mutation is complete, one finalizer
derives each canonical id from role, class, gate, source obligation ref, source obligation content
hash, and that run-scope hash. Status, detail, evidence refs, risk spend, and the id itself are absent
from the identity preimage. Class rows derive their source content from the versioned class-gate
projection; decisive rows bind the generation-owner descriptor content hash. P37: both internal
equalities and every id are `recomputed`.

The mechanism is additive. Fifteen owner-produced `class_gate` drafts remain the complete declared
class denominator and receive N11 bindings before identity finalization. With a value receipt, two
`decisive_predicate` rows are appended under `slot` / `n8_transport`. Class totality and N11 consume
only the class partition; authority completeness, refusal evaluation, semantic projection, and the
gate hash retain the full ordered projection. This adds a second row kind carrying instance identity;
it does not make the fifteen singleton class-gate obligations instance-granular.

### P40 implementation rounds

- Round 1/2, **new class — live verifier-session provenance**: independent review found that the
  existing behavioral mutation table ran only after the isolated N11 session had closed. The repair
  widens the live-session helper so OM-01 is validated before return and its exact red report is then
  persisted. A marker-only frozen replay is not the witness.
- Round 2/2, **new class — legacy comparison isolation**: required identity fields make frozen v2
  receipts non-canonical. A strict private v2 custody model and one bounded comparison migrator now
  compare every pre-identity governing field, then replace only that admitted block with the live v3
  receipt. The v2 model is unavailable to the decision path. The certificate-refusal reconstruction
  seam was the identity-propagation class one level deeper, not a new round; the mechanism widened by
  finalizing only after every class mutation.

The first non-persisting artifact candidate then exposed the second finding of that same legacy
comparison-isolation class, one level deeper: the private v2 type inherited a current-v3 risk-scope
rule check. It stopped after 35.28 s with all governed bytes unchanged. P40 therefore permits no
local patch or third round; it requires widening the existing boundary to the quantity the property
needs. Raw v2 and v3 receipts now each validate under their own literal schema/risk-scope rule before
one private comparison projector normalizes only the finite typed v2/v3 aliases. Certificate,
semantic-ledger, owner-projection, and trace hashes remain raw and validated; no normalized copy is
persisted or admitted to a decision path. The permanent witness rejects a content-valid hybrid v2
receipt carrying a v3 risk scope and an unknown v4 boundary alias. The authentic frozen-v2 candidate
derivation then succeeded in 29.23 s under the recorded 2.40→2.76 load regime, again without moving a
governed byte. This is the mandated same-class widening, not implementation round 3.

### Declared source-authenticity residual and falsifier

The smallest missing capability is one generation-cycle owner/resolver that jointly receives the
candidate summary, value receipt, and resolved world-model record; content-binds the receipt to
`CandidateSummary.content_hash`; and independently recomputes the WMR content-hash and valid-time
binding. A complete static inspection found no such owner: `ValueGateReceipt` has candidate id and a
WMR hash but no candidate-content or valid-time binding, while N9 checks candidate-id equality only.
P37: receipt-internal equalities are `recomputed`; candidate-content and independently resolved WMR
valid-time authenticity are `not_established`.

The first behavioral launch was a non-receipt: Python-mode reserialization failed on an unrelated
legacy `ValueOuterSet.width` shape before the first subject operation, in 12.64 s with zero changed
bytes. The typed-object rerun succeeded in 17.20 s under contention: it held candidate id fixed,
changed candidate content, supplied no resolved WMR, and still produced two green decisive
receipt-consistency rows. Observed result:

```json
{"candidate_content_binding":"not_established","candidate_id_predicate":"recomputed","decisive_receipt_consistency_rows":2,"decisive_rows_green":true,"resolved_wmr_present":false,"resolved_wmr_valid_time_binding":"not_established"}
```

That is a worked example of the declared residual. It is not repaired or relabelled as world binding
in this lane.

### Reconciled census commands

Two independent complete walkers—one Python structural visitor and one `jq` recursive-object walk
aggregated independently by `awk`—read all 1,170 JSON files in the pre-declaration source census with
no parse failure and agreed: 26 receipts / 390 rows; `{15: 26}`; maximum pair multiplicity one; zero
repeated class/gate pairs; 19 v2 receipts / 285 rows plus seven historical v1 receipts / 105 rows. The
tracked transition-declaration companion makes the current file denominator 1,171, still with zero
parse failures and the same 26/390 obligation population. The 19 count was therefore the current
owner-bound scope, while 26 is the full persisted blast-radius scope. The reproducing commands
enumerate paths from `git ls-files -z -- '*.json'`, recursively select non-empty `obligations` arrays
whose rows carry `obligation_class` and `gate_id`, and aggregate receipt count, row count, schema,
artifact, and maximum pair multiplicity; neither command searches a sampled path.

The following first walker reproduces the complete population when run from the repository root;
the `cd policy-engine` is part of the denominator and excludes the repository-level Renovate JSON:

```bash
cd policy-engine
python3 - <<'PY'
import collections
import json
import subprocess
from pathlib import Path

paths = [
    Path(raw.decode())
    for raw in subprocess.check_output(
        ["git", "ls-files", "-z", "--", "*.json"]
    ).split(b"\0")
    if raw
]
receipts = []

def walk(node, artifact):
    if isinstance(node, dict):
        rows = node.get("obligations")
        if (
            isinstance(rows, list)
            and rows
            and all(
                isinstance(row, dict)
                and "obligation_class" in row
                and "gate_id" in row
                for row in rows
            )
        ):
            receipts.append((artifact, node))
        for value in node.values():
            walk(value, artifact)
    elif isinstance(node, list):
        for value in node:
            walk(value, artifact)

failures = []
for path in paths:
    try:
        walk(json.loads(path.read_text()), path.as_posix())
    except Exception as exc:
        failures.append((path.as_posix(), type(exc).__name__))

multiplicities = []
for _, receipt in receipts:
    pair_counts = collections.Counter(
        (row["obligation_class"], row["gate_id"])
        for row in receipt["obligations"]
    )
    multiplicities.append(max(pair_counts.values()))
print(
    {
        "tracked_json": len(paths),
        "parse_failures": len(failures),
        "receipts": len(receipts),
        "records": sum(len(receipt["obligations"]) for _, receipt in receipts),
        "distribution": dict(
            sorted(
                collections.Counter(
                    len(receipt["obligations"]) for _, receipt in receipts
                ).items()
            )
        ),
        "schema": dict(
            sorted(
                collections.Counter(
                    receipt.get("schema_version") for _, receipt in receipts
                ).items()
            )
        ),
        "max_pair_multiplicity": max(multiplicities),
        "receipts_with_repeated_pairs": sum(value > 1 for value in multiplicities),
    }
)
PY
```

### Red-first and focused receipts

- The three new value-receipt witnesses first failed on the absent descriptor method and distinct
  error codes; the focused four-test owner slice then passed. Its 68.44 s duration is labelled
  contended but is not an admissible timing sample because the unexpectedly long run lacked the
  required pre-run uptime observation; the post-run load average was 11.28 / 11.44 / 11.12.
- The N9 additive-identity and remove-one witnesses first failed because records had no
  `obligation_role`; after implementation both passed in 74.25 s under the recorded 10.48→8.74 load
  regime. A later v3 rerun passed in 46.51 s under 4.16→4.12.
- The live artifact OM-01 test first failed on the missing persisted witness in 54.15 s, then passed
  in 32.11 s after the mutation moved inside the verification-session lifetime.

### Source freeze review and authority-identity radius

Three independent read-only reviews preceded the source freeze. Runtime returned GO with no
material finding. Artifact custody returned GO for a controlled reissue and no Blocking/Important
mechanism finding. Boundary returned GO for the mechanism and confirmed plan line 7 at its base
SHA-256. Its Important label names the deliberately unfinished artifact hand-back: under P39 this is
a companion/custody class, not a mechanism class, so it consumes no implementation round and is
closed only by the declared-versus-observed reissue below. Both reviewers' missing-path-list and
missing-census-working-directory observations are the same companion/P35 class one level deeper;
the enumerated allowlist and executable command above close them before any accepted writer.

One mixed focused slice has a single inherited RED:
`test_rederived_n9_contract_accounts_fixed_time_refusal_through_n11` expects one projection row but
the current owner returns the two governed calibration/data rows. The same isolated test fails on
untouched base `068aab9df` with the same assertion, so it is a P34-complete exclusion and is not
changed in this lane.

The runtime E12 authority import closure has 120 members. Of the four changed runtime/PDC source
files, `gy_waist.py` and `layer2_design_search.py` are members; `generation_cycle.py` and
`promotion_sequence.py` are not. The deployment baseline independently enumerates 2,562 files and
includes all four changed `src/polisyos/**/*.py` files, so each still moves the confidence ledger's
deployment identity. The five-file mechanism's tool writer is outside that deployment set. The
broader generated-owner source closure has 1,992 members and contains the four source files but not
the tool writer. P37: each membership and denominator is `recomputed`; the source-freeze reviewers
independently reconciled the changed-path classification. The confidence artifact therefore remains
deliberately byte-identical and stale for the later joint-lane reissue.

## Pre-writer artifact transition declaration

The source-phase 600 s executor ceiling above was never the Depth writer's governing budget. The
committed timing catalog already carries the lane-owned Depth `--write` recommendation
`7,320.872024` s, derived before this lane from three serialized Depth samples. Two early contended
shadow attempts used the wrong 600 s harness cap and produced no candidate; both are non-receipts and
neither changes the catalog or supplies a duration. A noncanonical Lane-0 run then produced an 8,951
byte pending payload, and one canonical launch omitted the required synchronous provenance preflight;
both terminated before the governed candidate operation and are excluded.

With the synchronous preflight ordered correctly and all five upstream candidate artifacts staged in
a disposable branch-attached shadow clone, the governed Depth writer returned a 2,268,318 byte
candidate in 1,100.709022 s under contention. That launch recorded kernel load averages but omitted the
literal pre-run `uptime` string, so its duration is regime evidence only. A second canonical write used
the catalog ceiling and a literal `uptime` pair (`6.84/6.56/5.51` to `3.81/5.45/5.41`), completed in
1,048.502441 s, and reproduced the first candidate byte-for-byte at
`sha256:280986fc48977b948bd95068e3554958fb6112470fe1d9de82eb9cce795edf64`.
Promotion and generation independently reproduced their candidates byte-for-byte in 10.331204 s and
19.779163 s. The earlier same-byte N10a "repeat" is not an independent reproducibility receipt: the
producer owns a module-level cycle-trace cache, and a later fresh-process falsifier produced different
live identities from the same source and governed inputs. Its two contended durations, 396.011913 s and
364.30 s, remain regime observations only. None of these contended durations is promoted into a clean
p95.

The complete declared transition is committed separately as
`2026-08-19-gy-gap1-artifact-transition-declaration.json`. It is bound to mechanism head
`1de11b8bdd486556f05f3347988e0e1e6dcbf5d8`, 3,286 source/tool files at
`sha256:f37a518b34668cad3063a0e4cb1e9094e41e70f1903e7d91033398406741e516`, and a
914-file / 47,112,213-byte governed-output preimage at
`sha256:66c51f365c3d8f4284cfca33f00059f05f3a7c959d4b4ab45b0d87d7e4e29d68`. The denominator is
the union of all tracked files reached by the 437 generated-artifact registry specs and all 509
tracked Policy Design Case files: 713 and 509 members respectively, 308 in their intersection. Two
independent implementations agree on all four counts and the byte total. This widens the byte audit
past the generation-cycle artifact's measured registry omission and covers all 46 statically declared
validator outputs plus all 50 outputs returned by the one dynamic GX validator.

The declaration pins 908 protected files byte-for-byte, including the deferred confidence ledger,
the N10a census, and the N10a smoke problem. Its six permitted movements are:

| Governed output | Leaves | Candidate bytes | Candidate SHA-256 |
| --- | ---: | ---: | --- |
| promotion contract | 525 | 183,066 | `27277bf5eb6db1c09154eff58b6b8a302d46625fc551cd3c2d679abdb4ef19e8` |
| generation-cycle contract | 304 | 183,254 | `80527a78bbbcefeef6b2eabaac965ec7fac392d6425ca1e2f33622d796166d14` |
| second-domain cycle trace | 770 | 603,649 | `8a2337e1b481a0afc129dd5a97e60ce4632687b81213f83c4b6d7c5d50c6aa3f` |
| second-domain pack | 3 | 252,598 | `74bb27a236edadc53d6522fcd2c28562d2e2bf79090a7516edb9a18ced39dea4` |
| second-domain free-grow gaps | 5 | 21,053 | `237873f8989f405bff266b7a87a33e6602f7f5813fa555cd111eeff316a7143c` |
| depth-N universality contract | 1,837 | 2,268,318 | `280986fc48977b948bd95068e3554958fb6112470fe1d9de82eb9cce795edf64` |

The declared total is exactly 3,444 canonical JSON leaves. Manifest content identity is
`sha256:1d3193bb0161f4f930edd6f415b6ecd77e5cf5fbde76875135ed6aa2afb7a67e`; the
746,866-byte manifest file is
`sha256:e00726953716e4d474b3f150912b8079b161b52806196f72a2682f0964db5a44`.
Acceptance remains `not_established` until each canonical writer returns and a raw-byte readback proves
all six candidate hashes, every declared leaf set, and all 908 protected preimages exactly.

The candidate-overlay population remains 26 receipts. Nineteen current receipts validate as v3 and
seven historical Depth recordings remain raw v1 custody. Exactly three current promotion-writer
receipts carry the two additive decisive rows: the final distribution is 23 receipts of 15 rows and
three of 17, 396 rows total, with 285 `class_gate`, six `decisive_predicate`, and 105 historical rows
whose pre-identity shape is retained. P37: every count is `recomputed`; an independent recursive
object walk is required again after accepted writes.

P40 companion classification: the missing machine-readable six-output declaration was the same P39
artifact-custody class one level deeper, so the companion widened to the complete transition rather
than adding six local prose patches. The generation artifact's absence from the registry was the
second registry/validator-denominator finding; ladder repair stops, the registry is not patched in
this lane, and the byte mechanism widens to registry expansion union the complete tracked PDC set.
An intermediate claim of 51 dynamic GX outputs was a worked example of that declared denominator
class: the live owner and an independent reconstruction both return 50 (`2 × (5 inputs + 20
reports)`). These are companion findings and consume no GY-GAP1 mechanism round.

The pre-writer artifact review then found the second occurrence of that P39 custody/denominator
class one level deeper: allowed paths were product-root-relative while protected paths were
workspace-root-relative, and the aggregate hash recipe was implicit. P40 forbids another local
patch. The declaration therefore widened as one schema: every one of the 914 paths is now a POSIX
path relative to the declared Policy Engine product root, absolute and `..` paths are forbidden,
and the exact canonical-JSON, raw-file, source-scope length-prefix, artifact-scope, and manifest
preimages are part of the declaration. The earlier manifest identities are superseded before any
writer ran. This companion widening consumes no mechanism round.

## Artifact-writer refusal and stopped hand-back

The guarded accepted-writer wave began clean and branch-attached at
`f332387bb8aea29020b81014c2f6003c6e9c334f`. Its literal pre-run `uptime` recorded load averages
`2.77 / 2.98 / 3.96`, so every duration is `regime=contended`. Promotion completed in 10.149752 s and
matched its declared 183,066-byte candidate at
`sha256:27277bf5eb6db1c09154eff58b6b8a302d46625fc551cd3c2d679abdb4ef19e8`.
Generation completed in 17.807984 s and matched its declared 183,254-byte candidate at
`sha256:80527a78bbbcefeef6b2eabaac965ec7fac392d6425ca1e2f33622d796166d14`.
N10a reached its transition-manifest comparison and refused with
`n10a_expected_transition_manifest_mismatch`; because the exception did not return the owner's own
duration, it supplies no N10a timing sample. The guard restored all seven possible writer targets,
and a readback showed a clean tree at the same attached branch and head. No candidate from that wave
was accepted.

A fresh-process, non-persisting falsifier then staged only the exact promotion and generation
candidates in a disposable branch-attached clone. It completed in 224.437990 s under the literal
contended `uptime` pair `3.68 / 3.54 / 3.86` to `4.84 / 4.41 / 4.16`. The approved and fresh manifests
had the same source head, the same 3,286-file source-scope identity
`sha256:f37a518b34668cad3063a0e4cb1e9094e41e70f1903e7d91033398406741e516`,
the same five legacy content hashes, the same changed-leaf counts, and the same changed-leaf sets.
Their live identities nevertheless diverged:

| Output | Approved live content hash | Fresh-process live content hash |
| --- | --- | --- |
| N10a cycle trace | `sha256:a452f1e7c55eeacd1eac602f756accc92048f9c4a01060120cd45529bb9871dd` | `sha256:38db953fc810c59626eeaaed2e53464ca2c54e7727fbe24170116456b2fe3278` |
| N10a pack | `sha256:6746e54a33a6c0325752af1c9964d64330b72b48dc8bd58a41241934d1750d49` | `sha256:aeae5c8d4a1eb276f8dfae8d0a2f2ec9fa7cfd12fc584a3ce35470da73dae9b3` |
| N10a gap report | `sha256:83672e47d3b7dbcd0490ef54c808e9da367c709d6506935057d1bab47dca83db` | `sha256:33a4f74180ed132a4f82d2ff569ec972056a7a83d156a4575b2c4c4c46b9c594` |

The approved N10a transition-manifest identity was
`sha256:d6f2c6e79e2b5e10b2f4eb95e0d8b8c39810abb38634eae12615a21ec6d61729`;
the fresh identity was
`sha256:967fb1b868183468036316149aaa970a5156fa9a59a545c8a40f1c202818b396`.
P37 provenance for every comparison above is `recomputed`.

The independent freeze audit localized the divergence. `_build_cycle_trace` constructs
`GenerationCycleController` without a governed `generated_at`; the acquisition planner therefore
resolves `_utc(None)` from the live clock. The resulting
`generation_cycle_run.cycles[0].acquisition_routing_report.generated_at` is inside the trace content
identity, while only `runtime_metrics` is operationally excluded. The saved candidate carries
`2026-08-19T16:02:51Z`; the frozen artifact carries `2026-08-13T10:03:43Z`. The module-level
`_CYCLE_TRACE_CACHE` explains why a same-process second call can repeat the first bytes without
re-deriving time. The falsifier is the fresh process above: keep source, governed inputs, legacy
preimages, and leaf denominator fixed; the live manifest changes. Supplying a governed deterministic
operation time, or defining an owner-level operational reconciliation for this field, is the
smallest mechanism that would close this new class; neither is wired into the N10a writer here.

P40 classification: **new mechanism class — uncontrolled runtime time is content-bound by the writer
manifest**. This is not the source-authenticity residual and not another P39 declaration-denominator
example. It arrived after the two permitted GY-GAP1 mechanism rounds were consumed, so the lane stops
without repairing, rebaselining, or running another writer. The declared transition was six files /
3,444 leaves; the observed **accepted** transition is zero files / zero leaves. All 908 protected
preimages, including the deliberately stale confidence ledger, the N10a census, and the N10a smoke
problem, remain byte-identical.

GY-DEF5 is closed at mechanism round 0/2. GY-GAP1 is stopped at artifact freeze after mechanism round
2/2 on the new uncontrolled-runtime-time finding and remains open as a governed capability. Its
source-level acceptance witness does pass: one decisive obligation instance removed, class
denominator total and green, authority-band result red. That source witness does not override the
failed governed-artifact freeze. Plan line 7 remains byte-identical at
`f88d113f34f339f14d333cdd3fe6459cf0e73d449ec3bb5f026567276a14aa37`.

## P41 exact-base ownership replay

Before any further source or artifact mutation, two isolated branch-attached clones were checked out
at exact base `068aab9df41f2aeebf7b83a80c7939b02d196a5d`. Each clone had zero tracked delta from that base,
zero status entry under `src/polisyos` or `tools`, and zero `GY-GAP1` source/tool match. Each invoked
the canonical measurement entry point in a distinct fresh process, with the exact-base `src` and
product root forced to the front of `PYTHONPATH`:

```text
.venv/bin/python tools/quality/validation/check_layer3_gy_second_domain_pack.py \
  --repo-root <exact-base-product-root> --measure-write-transition --output-format json
```

Both processes completed below the existing N10a writer ceiling of `852.699146` s. Their samples are
contended regime evidence only and do not enter a clean p95:

| Replay | Duration | `uptime` load averages, before -> after | Transition manifest |
| --- | ---: | --- | --- |
| A | `381.213158` s | `4.47 / 4.83 / 4.39` -> `8.62 / 8.45 / 6.33` | `sha256:86ca60383705ef20151186d4d505af2fe0ae4506f18058332b1d969763a176a7` |
| B | `369.202892` s | `7.97 / 6.05 / 4.98` -> `8.67 / 8.45 / 6.70` | `sha256:86ca60383705ef20151186d4d505af2fe0ae4506f18058332b1d969763a176a7` |

The two parsed manifest objects and their canonical bytes are identical; the latter have SHA-256
`1e3712a98b605c94c7591c3c1e5d56d21b8d8791f657c84e9ee2562a429cc02f`. Both bind source scope
`sha256:98449d8d2f74f1461b1a5c821438f27794453339d73d363b048a80697313545f`; all five artifact rows
have equal frozen/live identities and zero changed leaves. P37: checkout identity, source absence,
status, manifests, canonical bytes, row counts, durations, and `uptime` pairs are `recomputed`.

P41 therefore returns **stable at the exact base**, not inherited. The introducing change is
`7ca24cda0` (`feat(gy): bind decisive obligation instances`): its v3 identity fields and additive
`decisive_predicate` rows create the legitimate semantic transition in the promotion receipts
embedded by the N10a trace. That non-equality bypasses the writer's existing operational-leaf
reconciliation guard, which only runs when the frozen and live top-level content identities already
match, and exposes the live-clock `acquisition_routing_report.generated_at` during the transition.
Commit `1de11b8bd` only admits historical v2 custody for comparison and is not the semantic trigger.

The freeze blocker is a defect in the separately owned N10a writer. Its transition-manifest gate is
the uncovered second consumer of the operational normalization whose first consumer, scoped
`--rederive-audit`, was closed by `GY-DEF7`. Under the ratified P41 conditional, however, exact-base
stability assigns this transition escape to GY-GAP1 for budget purposes because GY-GAP1 introduced
the semantic trigger: `GY-DEF7` remains closed, no `GY-DEF17` is registered, the N10a writer is not
repaired, and no further candidate verification or writer is run. The existing mechanism-round 2/2
stop and the declared six-file / 3,444-leaf versus accepted zero-file / zero-leaf artifact outcome
stand unchanged.

## Superseding P41 ownership correction and GY-DEF17 registration

The exact-base replay receipt above remains valid: two separate fresh processes at
`068aab9df41f2aeebf7b83a80c7939b02d196a5d` produced the same zero-transition manifest. Its former
budget consequence does not. P41 establishes whether a symptom reproduces at the slice base; it
does not identify the component whose predicate is defective once a legitimate later input reaches
it. Here both facts hold:

- `7ca24cda0` supplies a legitimate governed semantic transition by adding the v3 N9 identity and
  additive decisive-predicate rows;
- the N10a writer already carries the defective operational-preservation mechanism; its equality
  guard predates `8816df5f4`, and that commit added the measured-transition consumer without
  extending the inherited normalization to that consumer.

The current branch coordinate was independently read before registration:
`_preserve_frozen_operational_metrics` is at
`tools/quality/validation/check_layer3_gy_second_domain_pack.py:6914`. The governed record cites the
symbol, not that movable line number. Its guard skips whenever top-level frozen/live content hashes
differ, so the writer's normalization is unreachable on a declared semantic delta. Its local member
tuple contains two outputs although `_ARTIFACT_WRITE_SPECS` at the same branch declares five. The
previously unclassified `pack`, `smoke_problem`, and `gaps` members are therefore absent from the
consumer denominator. These are member A (the equality proxy) and member B (the partial
denominator), and both belong to the same `GY-DEF7` class one level deeper. `GY-DEF7` remains closed
for its scoped `--rederive-audit` consumer. P37: commit ancestry, live symbol coordinates, guard
predicate, and both member sets are `recomputed`.

`GY-DEF17` is registered before any source or test byte moves. Its mechanism is the canonical
operational-leaf owner/export plus the N10a writer consumer. Its companions are the plan, this
journal, mirrored behavioral witnesses, and any induced transition receipt. Per the architect's
ruling, the lane enters a fresh shared **0/2**: only a Blocking or Important new-class finding against
GY-GAP1's or GY-DEF17's mechanism consumes a round. Closure requires the full derived writer-output
denominator, unconditional (or operational-predicate) reconciliation that constructs the live shape,
a fresh-process stability witness holding the declared GAP1 semantic delta fixed while operational
time varies, and an opposite-direction second governing mutation that still changes the manifest. At
least one positive case must exercise `pack`, `smoke_problem`, or `gaps`.

### Reboot and timing-catalog survival receipt

At observation time `2026-08-19 21:48 +0300`, the host reports boot time
`2026-08-19 21:28:37 +0300`. The worktree's
`.polisyos-tools/timing.jsonl` predates that boot (`2026-08-19 18:51:47 +0300`) and survived it
byte-readable: one JSON line / `306` bytes, recording a successful `measure-write-transition`
sample started `2026-08-19T15:45:00.496792+00:00` with duration `407018.089` ms. The primary
workspace timing log is also readable and had `38` JSON lines / `10,831` bytes at this measurement,
including an append after the reboot. The retained worktree row's regime is explicitly `unknown`;
survival does not promote any sample from this timing window to budget-grade evidence. P37: boot
time, mtimes, byte counts, line counts, and retained row content are `recomputed`.
