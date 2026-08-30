---
title: "INT-R5 — Commendation preservation and survey-manifest verification"
amendment_head_verified: 70f2db6d3a4330664c981721a9305f16bffe369b
commendations_preserved: 9
manifest_finding: partially_closed
---

# INT-R5 Commendation and Manifest Ledger

## 1. Scope

Repository observations are GitHub connector reads pinned to
`70f2db6d3a4330664c981721a9305f16bffe369b`. External survey observations use the Files connector
against the exact `file_…`, version `1` identities recorded in
`int-r5/survey-source-manifest.md`. This ledger does not re-research the surveys.

## 2. Commendation preservation

| Commendation | Property demanded by audit §3 | Package evidence | Result |
|---|---|---|---|
| `C01` | Honest delivery and evidence-class reporting. | main `1-45`; manifest `1-17` | **preserved**. Branch limitations are explicit. The separate conversational hand-back was inaccurate and is not used as package evidence. |
| `C02` | Named measurement holder; index zeroes settle neither absence nor presence. | main `153-179`; baseline `1-31,273-284` | **preserved**. |
| `C03` | 34/34 permission parity; historical 33 is documentation drift. | main `194-203`; baseline `120-139` | **preserved**. |
| `C04` | No assertion that hidden/off-system conflicts are absent. | main `365-380`; specification `400-451`; external ledger `161-188` | **preserved**. |
| `C05` | Jurisdiction/profile-relative forum, quorum, presence, vote and cure. | main `351-365`; fixtures `220-282`; external ledger `124-160` | **preserved**. |
| `C06` | Red-first fixtures with near-pass and mutation structure. | main `435-461`; fixtures `1-534` | **preserved**. |
| `C07` | Missing holder is typed without borrowed institutional authority or loss of demo lane. | main `405-420`; specification `533-558`; fixtures `466-475` | **preserved**. |
| `C08` | PAO-R4 remains a separate owner and cannot substitute for INT-R5. | main `130-150`; specification `16-75`; fixtures `404-432` | **preserved**. |
| `C09` | Historical certificates remain immutable; no fictional rollback after effect. | main `421-434`; specification `446-463,559-594`; fixtures `283-356,480-490` | **preserved**. |

Result: **9/9 preserved.**

## 3. Manifest inventory and anchor resolution

The manifest records five source objects. Direct Files-connector resolution of each exact identity
succeeded. Materializing the version-1 Markdown bytes produced the following independent checks:

| ID | Recorded external identity | Lines | Bytes | SHA-256 check |
|---|---|---:|---:|---|
| `S1` | `file_000000001e10820aa329804b1bf1dfe1` | 617 | 86,930 | matched `4d6c9e49db74d08c7f2d56590ec9480e3702a908b58cc38139e75b0a2a4b40be` |
| `S2` | `file_000000007d548243b06f8f47c1ca8a21` | 375 | 90,722 | matched `5c046877c6bbbb1fccd0c30709136ffd55c451b71ac34984ed2d24a937a2606a` |
| `S3` | `file_00000000eb3482469ae708351aa9e291` | 424 | 88,604 | matched `9436cfdfa6f67bd7a79ffe5826ce7862f78ea1bd51856f1e3fad2b009ff82de7` |
| `S4` | `file_000000005e8c81f4b4dd2913ffc49aa9` | 829 | 88,763 | matched `160cfd65d14e79a6cd05b22976ea0a83f0a9cd7ba1a132ce18d5c8a002265845` |
| `S5` | `file_000000003ce8820aa2796bf8f4f71f68` | 485 | 78,489 | matched `c5ea9693fb63fcd827e09367f92fc655dfa323ee497268b0643813d18605f92b` |

Consequences:

1. The hashes are genuine content bindings, not invented values.
2. The package-local URNs identify those digests but are not retrieval mechanisms.
3. The `file_…` identities are resolvable inside the authenticated Files environment; the branch does
   not establish that an independent third party possesses that connector or permission.

## 4. Passage-coverage test

Manifest §3 lists load-bearing source ranges; §4 claims to admit the branch-local evidence. Comparing
the two yields:

| Survey | Branch-local coverage | Residue |
|---|---|---|
| `S1` | Core scope, amount, attenuation and cure summaries are present. | `CL-E12` cites `328-409`, but §4 stops at `328-381`; lines `382-409` contain cure outcome tables and failure cases. |
| `S2` | Forum/quorum/co-signature claims are materially represented. | No material omission found for the listed S2 families. |
| `S3` | Structural SoD and detectability summaries are present. | `CL-E08` cites `136-178`; §4 omits it. That range contains transaction-level SoD and the USAID self-review failure. |
| `S4` | Non-inferability, proof and path-reduction summaries are present. | The freshness claim cites `377-550`; §4 omits it. That range contains revocation propagation, snapshot and checkpoint semantics. |
| `S5` | Recognition and base act taxonomy are present. | `CL-E11` cites `172-236`; §4 omits it. That range contains degradation mechanisms and counterfactual authority tests. |

The §4 text is also a bounded paraphrase, not a verbatim passage copy. It supports semantic review but
does not let a branch-only reader inspect each source passage.

## 5. A-005 adjudication

```yaml
claimed_disposition: accepted_with_variation
verification_result: partially_closed
content_identity: independently_verified
branch_only_source_replay: not_established
full_external_byte_custody: explicitly_not_claimed
```

The amendment's `accepted_with_variation` label and explicit source-custody residual are defensible.
The stronger main-report statement that every transferred claim can be replayed from package-local
extracts is not fully earned. Audit §4.5 requires the branch-only reader to verify bytes or a durable
archive identity and locate every load-bearing passage. A private connector identity plus a digest
does not satisfy branch-only retrieval, and the extract set is incomplete.

This is a gap, not a `NO_GO` trigger: the amendment preserves exact identities, honestly denies that
the full bytes are committed, and does not use the manifest to upgrade capability or gate standing.

## 6. Residual band

- Primary-source citations embedded in the surveys were not independently revalidated; Stage 4 tested
  transfer custody and claim coverage, not the underlying legal research.
- The Files connector proves present accessibility to the verifier, not durable public availability.
- No conclusion is drawn about future retention guarantees for `file_…` objects.
