# C05 source and G proposal review

Read-only review on the existing G integration branch. No test, install, source edit, branch/ref update, or production-data access was performed.

## Exact inputs and verdict

- G base is `dee58973f7673299070b7c7374f419b0adb8175c`, tree `4caee698bd9a6c61277a1608bb38376b669f0372`; the local G checkout is clean at this base.
- Published C05 source is `5ccbfa15c5671623a4c1ff7a3145460c5ca5a857`, tree `9633ae3e5fdbdcc6a6a76af3d7ef29bdaa12fd09`; the normal topic head is `eee090e345d1121d3d53cdd93a7ab32f818d5ef7`.
- The exact G-port proposal is `42987be62c48356211e1ce4397ca67cd45249997`, tree `ab1aa6a9cfe98d4a613fe04f83cc4bd56124c628`. Its base is the exact current G base above.
- I read the complete coordinator handoff at `d9a4b671c99bf6a5435fde4fc873092e03b451b0`, plus the full C05 source and proposal handoffs, proposal/reconciliation records, source DAG, exact source diff, and relevant tests/facade companions.

**Verdict:** the own-base C05 implementation has bounded source/native GO and is ready for a local G composition attempt. G source acceptance remains **HELD** until the proposal is reconciled and its behavior is checked on the composed G candidate. The hold is a pathwise source-contract choice, not a missing Git object, unavailable VM, or missing owner response. Do not issue finding closure or production/currentness claims from these receipts.

## What the exact C05 evidence supports

The final native receipt is stored in the source topic as a 91,084-byte gzip blob; its decoded bytes are 1,212,361 bytes and SHA-256 `76dd1fa4f704d07e0c09550d181e856b8d795303031a48c1356766969839d5f5`, matching the independent review’s pinned receipt identity. The decoded receipt binds source SHA/tree exactly and records 119 selected affected cases: 119 PASS, 0 FAIL, 0 ERROR, 0 SKIP. It preserves the earlier 117 PASS / 2 FAIL on the initial source instead of transferring those results to the repair. The independent reviewer’s verdict is `GO_BOUNDED_EXACT_SOURCE_AFFECTED_NATIVE_CONSUMER_AND_MATCHED_PROPERTY_REMOVAL_EVIDENCE`.

The tests exercise the real content/currentness path: material inputs and source-profile changes alter the persisted producer basis and actual stage/resume behavior; selected warm readers refresh; loader dispatch preserves context/global/owner resolution; real session reuse and native SQL paths are exercised. Matched removals are discriminating for profile, seed, WVS forwarding, session reuse, and WVS policy reads. The receipt explicitly limits what these controls prove: it does not establish throughput, every lazy transport branch, all headers or credentials, remote-version freshness, concurrent atomic snapshots, or full LA-041 resume/output integrity.

The source change is coherent as a bounded repair: it introduces the material-input snapshot/basis helpers, binds covered producer settings into the run signature, forwards policy snapshots through the actual WVS and proxy readers, and restores the canonical resolver order at the three affected loader consumers. The final source quality handoff records scoped Ruff/format and strict six-source mypy PASS with pinned private YAML/pandas stubs. The shared environment’s two missing-stub errors remain separate tooling evidence, not a source failure.

## The “14 missing suppliers” are not 14 absent files

I checked the 14 held supplier paths against exact Git trees for G, CAT `8dfa7f3c544461c0ff081861848fcc5d8523da5b`, and C05 source. Thirteen paths exist in all three; their blob IDs differ between current G and the CAT/C05 lineage. The one exception, `data_forge/domains/catalog/_resources.py`, exists only in current G and is absent from CAT and the C05 candidate. Therefore the issue is selection and compatibility, not missing bytes:

- Preserve G’s `_resources.py` and its default resource locators.
- For the other 13 paths, compare the exact G and DFI→CAT versions by callable/contract and retain G-only behavior where it exists. Do not replace them wholesale with CAT bytes or apply the historical 139 KB predecessor reference patch as if it were a current composite.
- The relevant DFI→CAT commit ancestry and trees are present in Git; the proposal’s source DAG records 23 verified ancestors. No new agent, cloud supplier, or additional production input is needed to make this source decision.

There are also four public-facade companion patches. They are actual source dependencies, not optional documentation. The G-port loader uses the public `polisyos.ir.FetchRequest` import, which current G does not expose. Applying only the owned C05 patch would therefore leave that import unresolved. The companion adds lazy aliases to existing Fabric/Core/IR/read-API objects. The independent proposal review reconstructs all 14 owned and 4 companion postimages from the exact G base and records that existing exports are retained. The recorded owned-only and combined `git apply --check` results are both zero; this proves patch applicability, not runtime correctness.

## Composition route for the unified local agent

1. Keep `dee58973` as the immutable composition base and verify/fetch the exact source and proposal refs above. Use `owned-g-proposal.patch.gz` and `foreign-public-companions.patch.gz` only as path-level proposals; do not cherry-pick the CAT branch or apply the historical predecessor reference patch.
2. Resolve the 14 supplier paths in one written source-selection table: exact G/CAT/C05 blob IDs, symbols consumed by C05, G-only behavior, selected postimage, and why. Preserve `_resources.py`; preserve the existing canonical `CatalogSelectionError` binding and add the distinct run-profile alias only as proposed. Apply the four facade changes with the implementation that depends on them, preserving all old lazy exports and the C07 public IR boundary.
3. Build one immutable integrated candidate, then run the focused C05 119-case consumer set on that candidate, plus the public facade/import checks and the affected C06/G consumers. Add no redundant feature or duplicate DTO. Use removal controls where the composed source changes a guarded behavior. Reuse the exact source receipts only for unchanged source portions; the composed delta needs fresh evidence.
4. Have an independent reviewer inspect the final delta and its complete companions. Record source acceptance separately from the still-red global architecture gate, unresolved invocation gate, C10 served caller, and unavailable authentic production profile. Keep the all-header/credential/remote-version/concurrent-snapshot limitations explicit unless the implementation and falsifiers actually close them.

Do not make the source wait on an old group’s ownership label. If an actual contract ambiguity remains after comparing the exact suppliers and consumers, write the competing behaviors, affected callers, falsifier, recommended narrow option, and a concrete G decision packet; continue the independent bounded work meanwhile.

## Gates and limits that remain

The exact C05 full required architecture run is a real FAIL: 160 rows, including 6 owned import edges and two of four generated families failing; the OpenAPI/trust generated outputs differ from committed outputs. The invocation diagnostic exited 3 after 500 seconds / about 8.37 GiB RSS and is classified as partial static output with runtime invocation **not established**. Do not call either gate inherited or green; P41 remains `not_established`. These are separate from the 119 affected tests and do not erase their bounded evidence. The proposed C05/G patch is not a waiver for them.

The public service caller at C10 still needs an admitted `CatalogRunProfile` from its existing request context and must preserve selected output/refusal. Authentic configured source/profile positives remain `not_established`; production data should stay at its custodian. LA-032’s existing target/prior/donor producer identity is also not established by D3’s unrelated builder or by synthetic fixtures. These inputs limit those criteria, not the ability to compose and verify the portable C05 implementation.

Relevant pattern pass: P01/P02 (source implementation still needs the C10 bridge), P03 (four public companions), P07 (run-signature/replay basis), P08 (declared profile/currentness exclusions), P14 (bounded evidence only), P29/P32/P37/P38 (real behavior and removal controls rather than markers), P40/P41 (repair ladder and gate provenance).
