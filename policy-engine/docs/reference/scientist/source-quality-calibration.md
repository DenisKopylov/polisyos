# Source Quality Calibration

Related references: [Deep research evidence](deep-research-evidence.md), [Continuous governance](continuous-governance.md), [Claim Ledger](claim-ledger.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/evidence/source_quality.py` and `tests/unit/scientist/evidence/test_source_quality.py`

Source quality calibration turns raw `SourceMetadata` into a decision-facing
`SourceQualityAssessment`. The assessment is deterministic and auditable, but
the composite score is explicitly advisory until an empirical calibration set
is accepted. Publication gates must use the lifecycle fields, not the numeric
score alone.

## Score Status

`score_source_quality(...)` emits component scores for authority, freshness,
primary-source posture, anti-SEO risk, and duplicate status. Every signal
includes `score_calibration:advisory_v1` in its reasons. The advisory composite
uses transparent fixed weights:

| Component | Weight |
| --- | ---: |
| Authority | 0.32 |
| Freshness | 0.22 |
| Primary-source status | 0.22 |
| Anti-SEO posture | 0.16 |
| Independent evidence | 0.08 |

These values are decision-support signals, not truth estimates. A high score
cannot override stale, review, or withdrawn lifecycle states.

## Source Classes

`classify_source_class(...)` maps source metadata into TTL and authority classes:

| Class | Examples |
| --- | --- |
| `primary` | government, law, statute, regulation, official, `.gov` |
| `academic` | academic, journal, working paper, `.edu` |
| `institutional` | recognized multilateral or nonprofit/institutional domains |
| `news` | news, press, media |
| `web` | general web sources |

Duplicates are not independent evidence. A source with
`duplicate_of_source_id` may remain publishable only if no stale/review/withdraw
state applies, but it receives no independent-evidence credit.

## Freshness TTL

Freshness is calibrated by claim family and source class:

| Claim family | Primary | Academic | Institutional | News | Web |
| --- | ---: | ---: | ---: | ---: | ---: |
| recommendation | 730 | 1095 | 365 | 90 | 180 |
| empirical | 730 | 1095 | 365 | 90 | 180 |
| numerical | 365 | 730 | 180 | 30 | 90 |
| causal | 730 | 1825 | 365 | 60 | 90 |
| normative | 3650 | 1825 | 1095 | 90 | 180 |
| forecast | 180 | 365 | 90 | 30 | 45 |
| distributional | 365 | 1095 | 180 | 60 | 90 |
| implementation | 365 | 365 | 180 | 60 | 90 |
| caveat | 365 | 730 | 180 | 90 | 180 |

Unknown claim families use conservative defaults by source class:
`primary=365`, `academic=730`, `institutional=180`, `news=60`, `web=90`.

Claim-family aliases are normalized before TTL lookup so the source-quality
layer matches claim-support semantics: `factual`/`fact` map to `empirical`,
`legal`/`statutory` map to `normative`, and `welfare`/cost-benefit claims use
the causal TTL calibration.

## Runtime Report

`build_source_quality_report(...)` produces the deterministic
`policyos.scientist.source_quality_report.v1` artifact used by serious
runtime NL runs. The report records:

- `score_calibration = advisory`
- one `SourceQualityAssessment` per normalized source
- fail issues when stale, review, withdrawn, unavailable, or conflicted sources
  are not publishable
- warning issues when sources are duplicates or freshness cannot be assessed

The policy grounding matrix folds non-pass source-quality reports into final
policy quality status. This prevents withdrawn primary sources from remaining
publishable even when structural data/method/norm refs are present.

## Invalidation Mapping

`source_invalidation_state(...)` maps source events to decision states:

| Source invalidation | Decision state | Publication posture |
| --- | --- | --- |
| `none` | `publishable` | publishable if no other blocker applies |
| `stale` | `stale` | not publishable until refreshed or reviewed |
| `unavailable` | `review` | human/reissue review required |
| `contradicted` | `review` | human/reissue review required |
| `superseded` | `review` | human/reissue review required |
| `withdrawn` | `withdraw` | not publishable |

Withdrawn primary sources cannot remain publishable. The assessment records
`withdrawn_primary_source_blocks_publication` and sets `publishable=False`.
Continuous governance still owns explicit artifact withdrawal records; source
quality only declares that the source posture is no longer publishable.

## Conflict Behavior

Source conflicts are handled independently from freshness:

| Conflict level | Decision state |
| --- | --- |
| `none` | unchanged |
| `minor` | publishable advisory reason |
| `material` | `review` |
| `blocking` | `review` |

The most restrictive state wins across freshness, invalidation, and conflict.
For example, a fresh source with a material conflict enters `review`, while a
withdrawn source remains `withdraw` even if it is otherwise recent and
authoritative.

## Verification

```bash
uv run pytest tests/unit/scientist/evidence/test_source_quality.py -q
```
