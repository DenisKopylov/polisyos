# INT-R4 ‖ OPS-R5 — Amendment Verification Orientation Ledger

Measurement head: `329edb60f77867f914581d380acfccf5882d607d`.  
Instrument: fresh GitHub Connector reads at exact SHAs. Terminal receipts are separately recorded as `not_produced`.

## G1–G7 Re-Measurement

| Item | Architect-supplied value | Independently measured value | Agreement |
|---|---|---|---|
| `G1` containment/counts | audit→amendment 13; research→amendment 27; base→amendment 39; all behind 0; three ancestor exits 0 | Connector compare: `13/0`, `27/0`, `39/0`; merge bases respectively audit, research and base. Verification branch initially resolved exactly to amendment SHA. Terminal ancestor exit codes: `not_produced`. | Agree on counts and ancestry relation; terminal-code values not produced by this instrument. |
| `G2` delta shape | 7 paths; 5 added, 2 modified; 0 non-Markdown; 0 audit touched; common policy-operations prefix | Compare independently returned 7 paths, statuses `5 added + 2 modified`; every suffix `.md`; every path under `policy-engine/docs/research/policy-operations/`; no audit path. | Agree. |
| `G3` audit population | 18 unique IDs; 0 blocking, 9 material, 2 minor, 7 commendation | Parsed the audit finding table: `AUD-F01`…`AUD-F18` exactly once; split `0/9/2/7`. | Agree. |
| `G4` disposition rows | INT 10, OPS 8; F09 row only INT, F11 row only OPS | Parsed table rows, not token occurrences: INT 10, OPS 8; unique union 18; F09 owned by INT, F11 by OPS. | Agree. |
| `G5` disposition tokens | accepted 14; accepted_with_variation 3; routed_pending_principal 1; declined 0 | Row values independently total `14/3/1/0 = 18`. | Agree numerically; the routed token is outside pipeline §3.3. |
| `G6` report blobs | INT `5c302ae38eb365b8048b50259d96143650ee35b4`; OPS `475afba75ea3698619b2b2b4f89742bac0000b7e` at both heads | Fresh fetches at research and amendment heads returned those exact two SHAs at both refs. | Agree. |
| `G7` amended-location classification | no supplied four-way count | All 18 disposition rows point to their own amendment ledger: `(a)=18, (b)=0, (c)=0, (d)=0`. | New measured result. |

## G7 Row-Level Classification

Categories: `(a)` amendment ledger itself; `(b)` evidence register; `(c)` research report; `(d)` elsewhere.

| Finding | Amended-location cell | Category |
|---|---|---|
| `AUD-F01` | `int-r4/amendment-ledger.md:30-57` | a |
| `AUD-F02` | `ops-r5/amendment-ledger.md:28-276` | a |
| `AUD-F03` | `int-r4/amendment-ledger.md:58-153` | a |
| `AUD-F04` | `int-r4/amendment-ledger.md:154-238` | a |
| `AUD-F05` | `int-r4/amendment-ledger.md:239-334` | a |
| `AUD-F06` | `ops-r5/amendment-ledger.md:277-304` | a |
| `AUD-F07` | `int-r4/amendment-ledger.md:335-357` | a |
| `AUD-F08` | `ops-r5/amendment-ledger.md:305-328` | a |
| `AUD-F09` | `int-r4/amendment-ledger.md:358-408` | a |
| `AUD-F10` | `int-r4/amendment-ledger.md:409-447` | a |
| `AUD-F11` | `ops-r5/amendment-ledger.md:329-350` | a |
| `AUD-F12` | `int-r4/amendment-ledger.md:448-456` | a |
| `AUD-F13` | `int-r4/amendment-ledger.md:457-464` | a |
| `AUD-F14` | `int-r4/amendment-ledger.md:465-472` | a |
| `AUD-F15` | `ops-r5/amendment-ledger.md:351-358` | a |
| `AUD-F16` | `ops-r5/amendment-ledger.md:359-367` | a |
| `AUD-F17` | `ops-r5/amendment-ledger.md:368-376` | a |
| `AUD-F18` | `ops-r5/amendment-ledger.md:377-386` | a |

```text
(a) amendment ledger itself  18
(b) evidence register         0
(c) research report           0
(d) elsewhere                 0
                              --
total                        18
```

The table is descriptive only. Closure consequences are reported in the conformance artifact.

## Significance Of G6

Unchanged research-report blobs are not automatically a defect because the pipeline is append-only and an amendment ledger may expressly supersede historical propositions. G6 matters where the audit's own test requires package-wide consistency or where the object demanded by the audit remains absent.

Measured consequences:

- material for `AUD-F05`/`CT-02`: the unchanged INT report still permits `expected_variation` effect assimilation and says “no contradiction,” while amended artifacts forbid it;
- not a generic failure for `AUD-F04` or `AUD-F10`: their ledgers explicitly supersede the old precedence/representation statements at research-contract level;
- evidentiary for `AUD-F07`/`AUD-F08`: top reports still describe fixed corpora, while gap records admit that no fixture artifacts exist; those findings remain not closed rather than being silently treated as closed.

## Stage-Contract Orientation

Pipeline §2 requires each stage head to contain the stage it answers. Connector compare returned amendment over audit, audit over research, and research over base with the corresponding merge base and zero behind. The verification branch was created from the exact amendment SHA before its first write.

Pipeline §3.3 limits disposition to:

```text
accepted
accepted_with_variation
declined_with_reason
```

The supplied G5 arithmetic is correct, but `routed_pending_principal` is a vocabulary deviation. The row's substantive routing remains separately assessable and was found defensible under the conservative interim posture.

## Verifier Orientation Corrections

### `VER-OR-01` — unchanged blobs are not a universal amendment failure

Initial risk: treat G6 as proof that every finding answered in a ledger was merely described rather than amended. Correction: pipeline history is append-only and the ledgers are prescribed amendment records. Unchanged blobs become decisive only when a closure test demands one package-wide answer (`CT-02`) or when the demanded artifact itself is absent.

### `VER-OR-02` — connector ancestry is not a terminal exit code

Initial risk: transcribe exact-ref identity or compare merge-base as `git merge-base ...; echo 0`. Correction: connector observations and terminal receipts remain separate. All five initial and final shell values are `not_produced`; no synthetic `0` is reported.

## Orientation Conclusion

No architect-supplied G1–G6 numeric or identity value was contradicted. G7 was newly measured as `18/0/0/0`. The architect orientation is accurate on repository topology and populations; it intentionally left the meaning of G6 open, and the verification found that it matters principally to the unresolved GY-O1 package inconsistency.
