# C owner actions — immutable candidates and closure boundaries

Prepared from the read-only G reviews at integration HEAD `9c989f7877bd25fea38416cbd10d4c8b2511d10e`. The three C implementation candidates documented below are **not accepted into G at this HEAD**; this statement makes no claim about the count or disposition of other C work. Source review/code acceptance and formal finding closure remain separate. This is an owner-action draft, not a new review or test receipt.

## BERL — candidate `87999f69c5f99d69ee2622ef00cd7f4e04d7d572`

**Return to canonical BERL owner; block exact conditional-Gaussian claim.** Both direct runtime falsifiers reproduce on the exact frozen source:

- Decimal-scale witness: `Sigma=[[1e-20,0,1e-10],[0,1,0],[1e-10,0,1]]`, observe `x1=1e-11,x2=0`; exact `x3` mean/variance = `0.1/0`, runtime = `0/1`.
- Binary-exact witness: with `s=2^-35`, `Sigma=[[s²,0,s],[0,1,0],[s,0,1]]`, observe `x1=s/8,x2=0`; exact = `0.125/0`, runtime = `0/1`. The observed block is full-rank SPD and all nonzero inputs are binary-exact.

**Fix once at the property level:** make rank selection and support acceptance use one coherent scale-aware policy. Prefer existing stable linear algebra or scale-whitening; reject unresolved conditioning. Do not add numeric jitter, a one-input threshold patch, or a proxy correction that merely makes these witnesses pass. The defect is one rank/support class; the second witness is `SAME_CLASS_DEEPER`, not another repair round.

**Acceptance:** on a repaired immutable SHA, add scale-varied direct-moment and exact affine-adapter behavioral cases; preserve ordinary full-rank/singular and unsupported-observation controls. Then use a fresh reader on the normal package path and actual Runtime/FileSystemCAS and Phase 5 consumers, proving exact persisted value/readback and refusal controls. Existing probes use three exact Git implementation modules but three empty namespace stubs: they do **not** establish normal package initialization, registered public adapter behavior, Runtime/CAS, or Phase 5 behavior. Do not claim those consumers passed until freshly exercised.

Keep `LA-036 held`: the missing admitted law/model/bound producer and independent content-binding verifier/consumer authority chain are not supplied by numerical repair. Keep `LA-034 limited` pending an explicit decision on the shipped schema's external interoperability contract and supported-reader evidence. Preserve the `public_experimental` boundary.

## OBS/UDF — candidate `5a75b004e0d17c80f1d156df84db7a12a9274c9e`

**B147 / OBS-02 (P38 oracle gap; no demonstrated runtime bug):** bounded snapshot/resume implementation has source-review GO and recorded focused tests, but the ID oracle proves only uniqueness/cardinality plus metric/value multisets. It can accept a wrong `(observation_id, metric_id, observed_value, period)` assignment after a row-offset shift. Strengthen the existing test with an independently enumerated exact mapping (or interrupted-vs-uninterrupted equality plus explicit expected IDs); retain current cardinality and Parquet-consumer controls. Treat as the same continuity class one level deeper. A runtime fix is warranted only if this stronger discriminator exposes one. Keep copy-during-write atomicity, scratch-capacity, and remote-storage behavior as explicit limitations.

**LA-029 / UDF-04:** server lifecycle is **UNRUN**, not a code failure and not closed. Existing entrypoint/fake-`uv`, unavailable-workspace and Darwin-marker refusals do not prove server start/stop/restart/cleanup. Obtain a Linux C7 process receipt for create/start/stop/restart/cleanup, or keep LA-029 partial/held.

**LA-032 / UDF-05:** authoritative producer/bridge is **absent** (`producer_missing + bridge_missing + verification_missing`), not a proven selector defect. Add a source-authorized producer persisting one versioned inventory/ArtifactRecord for required targets and priors plus explicit donor presence/absence, provenance and time semantics. Wire all four reader forms and a real consumer to resolve and verify that same record. Do not elevate the current ephemeral `GenerationBasis` to authority. Keep LA-032 held until that end-to-end route exists.

## B87 / NET-01 — C streaming writer, B finding/evidence owner

The [B actions](B-delta-owner-actions-2026-10-06.md) record 7 PASS / 1 FAIL
on product `48e1f7170b04f1362e9b7e1d9b74eb9763151830`, with test
`a6ddddc114e195c7f1686042cf7c63ad99b9d5af` transferred at
`67c4a6f6f4e396c61d26846c51127cc4724978e1`. B87 remains open.
C owns `fabric/data_plane/streaming.py`: retain or transfer the failed handle
to a live production cleanup owner, or complete the required disconnect before
exit while preserving primary error/cancellation. A free permit and a new
connector session do not establish cleanup of the old handle. Reuse B's actual
process-stream consumer oracle and replay it on the frozen G source after the
owner repair; current-G verification is UNRUN. Do not create another pool or
give B authorship of C's shared writer. Committed locators:
`implementation-handoffs/B/current-stream-cleanup-consumer-oracle.json@67c4a6f`
and `current-stream-cleanup-consumer-evidence/native.txt@67c4a6f`.

## Scholar — candidate `01c303c2a94a1ff281e4fcc9804db60183e65d68` (includes shared transport)

**B17:** state the intended budget boundary. Current deadline/failover evidence supports provider/query work; `deep_search` page-fetch/rank (fixed fetch timeout) and later callback/finalization do not share its deadline. If B17 means whole-run wall time, carry one monotonic deadline through those stages and add a delayed-page falsifier plus persisted terminal-stop readback. Otherwise explicitly bound the claim to provider fallback and keep whole-run cap unestablished.

**LA-024:** keep **limited**. Shared transport has bounded redirect/timeout/bytes/MIME admission, CAS identity checks and negative controls, but permission/licensing authority is absent. The manual-seed path also drops response metadata (`final_url`, redirects, headers, fetch profile and digest) between `AcquireResult` and canonical document metadata. Decide with the canonical owner whether this provenance is required; if yes, bridge it in the canonical producer/artifact path and assert it at a consumer; if no, document the exact scope limit. Do not invent or imply license authority.

**LA-025:** keep **held**. Exact CAS snapshot continuity through enrichment and packet readback is technically supported, including no-fallback controls, but byte identity is not reuse permission. Closure requires an authoritative license/permission input and an admissibility rule consumed by the relevant path; until then, no reuse authorization claim.

## Transport, status and handoff

These three candidates are each pinned by a committed handoff at the fetched topic transport head. Transport/evidence heads below are not substitutes for implementation candidates; none of the candidates is accepted into G at `9c989…`.

| Slice | Candidate commit / tree | Fetched transport head / tree | Committed handoff locator |
|---|---|---|---|
| BERL | `87999f69c5f99d69ee2622ef00cd7f4e04d7d572` / `0280403e6837c5b220ac748a7674f4e5830ba0ab` | `8aecb0b6e08f8d37f09c70927761576583a89828` / `e31935df4f03f4c8c8bc028ca169261a26ffed76` (`origin/codex/e02-C-berl-20261006`) | [`ber-01-final-combined-c2-adjudication.json@8aecb0b6e08f8d37f09c70927761576583a89828`](policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/ber-01-final-combined-c2-adjudication.json); [`ber-01-consumer-census-c2-addendum.json@8aecb0b6e08f8d37f09c70927761576583a89828`](policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/ber-01-consumer-census-c2-addendum.json) |
| OBS/UDF | `5a75b004e0d17c80f1d156df84db7a12a9274c9e` / `3602443723a9a57b1a988ae3933b2d1d7c17f2bc` | `705575be73510d40d726c82c5a0af4bf8635a2a8` / `623a5ddd9e9512262f7944885a811930574733f0` (`origin/codex/e02-C-obs-udf-20261006`) | [`obs-udf.json@705575be73510d40d726c82c5a0af4bf8635a2a8`](policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/obs-udf.json) |
| Scholar | `01c303c2a94a1ff281e4fcc9804db60183e65d68` / `7bf3e8dda2bb1179b9960ffb3c5be5a5fb8e101f` | `f7af77f3373e4d22f703efa7208c19c6ffed1746` / `9d6c122811db158a7a84a43f534a1d1c1209b3a6` (`origin/codex/e02-C-scholar-20261006`) | [`scholar-scl-20261006.json@f7af77f3373e4d22f703efa7208c19c6ffed1746`](policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/scholar-scl-20261006.json) |

The source-candidate and transport/tree identities were read from Git, and each handoff path exists at the stated transport commit. BERL’s source freeze is an ancestor of its evidence tip; no PR is declared in these handoffs. The numeric falsifier receipts are being published with the G checkpoint at [full deciding outputs](../checks/2026-10-06-sixth-wave/README.md), with decimal-scale and binary-exact outputs separated. Send each correction to its canonical C owner; after a new commit, review only its delta plus dependencies and rerun affected defining consumers. Formal status changes require the finding owner’s closure evidence, not this action draft.

## Source reviews

`1548-C-berl.md`; `1548-C-berl-falsifier.md`; `1548-C-berl-falsifier-binary-exact.md`; `1548-C-obs-udf.md`; `1548-C-scholar.md`. These reviews inform the action items; the pinned handoffs above are the cloud-readable candidate/transport receipts. This draft adds no runtime evidence.

Local `R/1548-*` and `_build` references above are G-only navigation, not cloud dependencies. Read the committed owner receipts at the exact source/transport SHA; absent local bytes remain not_established. This owner-action record adds no product run or formal finding closure.
