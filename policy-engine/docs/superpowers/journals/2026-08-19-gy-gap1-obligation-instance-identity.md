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

Two independent structural walkers over all 1,170 tracked JSON files (zero parse failures) agree on
26 receipt-shaped objects, 390 obligation records, distribution `{15: 26}`, maximum `(class, gate)`
multiplicity 1, and zero repeated pairs. The earlier 19/285 census intentionally selected only
current v2 owner-bound receipts. The remaining seven receipts / 105 records are v1 historical
recordings preserved under the depth-N universality artifact; the full blast-radius population is
therefore 26/390.

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
aggregated independently by `awk`—read all 1,170 tracked JSON files with no parse failure and agreed:
26 receipts / 390 rows; `{15: 26}`; maximum pair multiplicity one; zero repeated class/gate pairs;
19 v2 receipts / 285 rows plus seven historical v1 receipts / 105 rows. The 19 count was therefore
the current owner-bound scope, while 26 is the full persisted blast-radius scope. The reproducing
commands enumerate paths from `git ls-files -z -- '*.json'`, recursively select non-empty
`obligations` arrays whose rows carry `obligation_class` and `gate_id`, and aggregate receipt count,
row count, schema, artifact, and maximum pair multiplicity; neither command searches a sampled path.

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
