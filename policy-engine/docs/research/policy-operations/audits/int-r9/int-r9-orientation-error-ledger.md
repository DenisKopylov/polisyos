---
title: INT-R9 — Orientation Error Ledger
status: delivered
kind: independent-audit
research_task: INT-R9
audit_verdict: NO_GO
repository: https://github.com/DenisKopylov/polisyos
audited_branch: research/int-r9-first-promotion-protocol
audited_commit: f5ad922377e38ee3ddbecb33293300bca25a9ad7
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - exact baseline verification of the factual orientation supplied to INT-R9
  - complete 15-manifest calibration, topology, authority-level, and reviewer-standing ledger
  - correction record for prompt premises and INT-R9's response to those premises
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - inference that a manifest authority_level grants independent adjudication
  - inference that public calibration metadata proves reviewer competence or independence
research_only: true
---

# INT-R9 — Orientation Error Ledger

## 1. Enumeration method

The audit did not infer the directory from one sampled file. It enumerated the fifteen committed
manifest names from the baseline adjudication register and fetched every JSON object at exact SHA
`d152565dcc11cea457dacd61fadc6e15dc3ecc86`. The following fields were extracted from each
structured object:

```text
case_id
case_ref
authority_level
reviewer_topology.topology_mode
reviewer_topology.calibration_round_id
reviewer_topology.reviewers[*].reviewer_id
reviewer_topology.reviewers[*].conflict_disclosures
expected_claim_ids
adjudications[*].label
adjudications[*].reviewer_votes
adjudications[*].gold_card
```

This is a full-directory result, not a sample. The two synthetic manifests are identified by their
case paths and by the adjudication README's 13-real-plus-2-synthetic reconciliation.

## 2. Exact 15-manifest topology and calibration result

| # | Manifest | Population role | `topology_mode` | `calibration_round_id` | `authority_level` | Reviewer identity standing | Conflict values |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `housing-rent-stabilization-001.adjudication.json` | synthetic | `deep_pilot_overlap` | `deep-pilot-round-1` | `governed` | role-like IDs, not named natural persons | `none_declared` |
| 2 | `public-health-outreach-001.adjudication.json` | synthetic | `partial_disjoint` | `null` | `production` | role-like IDs, not named natural persons | `none_declared` |
| 3 | `ua-msme-affordable-loans-2022.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | role-like IDs, not named natural persons | `none_declared` |
| 4 | `w11a_berlin_rent_cap_2020.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `governed` | role-like IDs, not named natural persons | `none_declared` |
| 5 | `w11a_boston_operation_ceasefire_1996.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `research` | role-like IDs, not named natural persons | `none_declared` |
| 6 | `w11a_eu_temporary_protection_ukraine_2022.adjudication.json` | real | `deep_pilot_overlap` | `deep-pilot-round-1` | `production` | role-like IDs, not named natural persons | `none_declared` |
| 7 | `w11a_ghana_free_shs_2017.adjudication.json` | real | `partial_disjoint` | `null` | `research` | role-like IDs, not named natural persons | `none_declared` |
| 8 | `w11a_india_aadhaar_dbt_2016.adjudication.json` | real | `partial_disjoint` | `null` | `production` | role-like IDs, not named natural persons | `none_declared` |
| 9 | `w11a_mexico_ssb_tax_2014.adjudication.json` | real | `partial_disjoint` | `null` | `research` | role-like IDs, not named natural persons | `none_declared` |
| 10 | `w11a_netherlands_room_for_river_2007.adjudication.json` | real | `partial_disjoint` | `null` | `research` | role-like IDs, not named natural persons | `none_declared` |
| 11 | `w11a_pakistan_ehsaas_cash_2020.adjudication.json` | real | `partial_disjoint` | `null` | `production` | role-like IDs, not named natural persons | `none_declared` |
| 12 | `w11a_uk_levelling_up_fund_2021.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | role-like IDs, not named natural persons | `none_declared` |
| 13 | `w11a_uk_mtd_vat_2019.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | role-like IDs, not named natural persons | `none_declared` |
| 14 | `w11a_uk_work_programme_2011.adjudication.json` | real | `partial_disjoint` | `null` | `governed` | role-like IDs, not named natural persons | `none_declared` |
| 15 | `w11a_us_ppp_2020.adjudication.json` | real | `partial_disjoint` | `null` | `production` | role-like IDs, not named natural persons | `none_declared` |

### Exact sets

```text
calibration_round_id values:
  {null, "deep-pilot-round-1"}

calibration counts:
  "deep-pilot-round-1": 4
  null: 11

topology_mode values:
  {"deep_pilot_overlap", "partial_disjoint"}

topology counts:
  deep_pilot_overlap: 4
  partial_disjoint: 11

observed pairings:
  (deep_pilot_overlap, deep-pilot-round-1): 4
  (partial_disjoint, null): 11

authority_level values and counts:
  production: 5
  governed: 6
  research: 4
```

No manifest combined `deep_pilot_overlap` with a null calibration ID, and no
`partial_disjoint` manifest named a calibration round.

## 3. Calibration orientation error

### Supplied orientation

The research prompt said the current reviewer topology had `calibration_round_id: null`,
generalizing from a sampled file.

### Baseline truth

That statement is false as a directory-level claim. Four manifests carry
`deep-pilot-round-1`:

1. synthetic housing;
2. Berlin rent cap;
3. Boston Operation Ceasefire; and
4. EU temporary protection.

### INT-R9 correction

INT-R9 section 2.5 and the contamination census correctly found Berlin, Boston, and EU. It then
said “three deep-pilot manifests record `deep-pilot-round-1`,” which remains incomplete because the
synthetic housing manifest has the same topology and round.

### Consequence

The correction does **not** make an independent adjudicator exist. All four manifests still use
role-like IDs, public expected answers, and declarations rather than identified accountable human
signatures. The readiness conclusion is unchanged. The factual roster and any calibration analysis
must nevertheless use four, not three.

**Finding:** `INT-R9-J-001` / `INT-R9-A-003` — material factual correction, result-neutral for the
independence block.

## 4. Authority-level orientation error

### Supplied orientation

The prompt described reviewer topology as having `authority_level: research`, again as though the
sample generalized to all manifests.

### Baseline truth

Authority standing is heterogeneous:

- `production`: public-health synthetic, EU, India, Pakistan, US PPP;
- `governed`: housing synthetic, ua-msme, Berlin, UK Levelling Up Fund, UK MTD VAT, UK Work
  Programme; and
- `research`: Boston, Ghana, Mexico, Netherlands.

### Interpretation

These values are manifest metadata. They do not turn role strings into independent natural-person
adjudicators, and the audit found no reason to treat `production` as a first-promotion authority
grant. The supplied premise was still false and should not be silently repeated.

**Finding:** `INT-R9-J-002` — material orientation correction.

## 5. Answer-bearing-field orientation

### Supplied orientation

The prompt said each adjudication file carries `expected_claim_ids`, `gold_card`, `label`, and
`reviewer_votes`, making the corpus unusable as a sealed holdout.

### Baseline truth

The conclusion is correct, with one field-value qualification:

- all manifests expose expected IDs;
- all expose labels;
- all expose reviewer votes;
- all expose enough case/evidence/context/reviewer structure to reveal intended semantics; but
- not every adjudication has a non-null gold card.

Confirmed null examples include:

- EU temporary protection;
- India Aadhaar DBT;
- Pakistan Ehsaas cash; and
- one semantic-pass adjudication inside synthetic housing.

The field key may be committed while its value is null. A null card does not restore secrecy
because labels, expected IDs, votes, rationales, evidence refs, and context refs remain visible.

**Finding:** `INT-R9-J-003` — minor wording correction; sealed-holdout conclusion verified.

## 6. Full supplied-orientation ledger

| Orientation assertion | Verification evidence | Verdict | Effect on INT-R9 |
| --- | --- | --- | --- |
| `proving_ground_case_count: 13` | outcome-corpus README enumerates 13 real cases | verified | denominator correct |
| named thirteen cases and domains | README rows reconciled to human aliases | verified | no missing/extra real case found |
| 15 adjudication files = 13 real + 2 synthetic | adjudication README plus `case_ref` paths | verified | exact denominator correct |
| expected IDs/labels/votes are committed | all 15 JSON files | verified | current corpus cannot be sealed retroactively |
| every adjudication has a non-null gold card | all 15 JSON files | false/imprecise | no change to contamination conclusion |
| reviewers are role placeholders | all reviewer IDs and absence of natural-person signature records | verified | current decisive independence unmet |
| all conflict disclosures say `none_declared` | all reviewer records | verified | self-declaration remains weak evidence |
| all calibration round IDs are null | all topology records | false | four deep-pilot records exist |
| all authority levels are research | all top-level values | false | 5 production / 6 governed / 4 research |
| ua-msme alone runs full composed loop | constitution `:382-398` | verified | ua decisive use contaminated |
| other twelve are per-slice, not integrated | same block | verified | no current integrated alternative |
| ua-msme appears in universality development | S14 `:170-255` | verified | strengthens exclusion |
| N9 input names ua-msme by default | promotion sequence `:130-180` | verified | strengthens exclusion |
| 0 of 13 converted | constitution `:382-398` | verified | current positive capability absent |
| `useful_design_rate = 0` | same block | verified | no positive-existence inference |
| every case remains a typed blocker | same block | verified | current state honest-negative |
| B output is shadow-only | same block and organizing rules | verified | no authority transition demonstrated |
| D3.8 is unbuilt | same block | verified | first-promotion gate absent |
| confidence registry is 232 lines | complete TOML inspection | verified | orientation count correct |
| two `ineligible_v1` profiles | proof-profile enumeration | verified | exact |
| one `owner_theorem_unavailable_v1` | proof-profile enumeration | verified | exact |
| one `deterministic_owner_v1` | proof-profile enumeration | verified | exact |
| one `closed_constant_unit_e_process_v1` | proof-profile enumeration | verified | exact |
| two `basel_square_v1` schedules | schedule-profile enumeration | verified | exact, but scope-local only |
| GY plan requires INT-R9 before candidate inspection | GY verification-phase text | verified | protocol must be settled prospectively |
| GY plan frontmatter does not safely parse | unquoted colon-rich `revised:` scalar | verified | separate owner must fix |
| Atlas plan frontmatter does not safely parse | same defect | verified | separate owner must fix |
| Wave-2 backlog frontmatter does not safely parse | same defect | verified | separate owner must fix |

## 7. Reviewer identity and conflict conclusion

The exact calibration and authority corrections do not cure independence. Across all fifteen
manifests:

- IDs describe functions or numbered roles, not accountable natural-person identities;
- expertise is asserted in short strings;
- conflicts are represented by `none_declared`;
- no signed employment/funding/reporting-line record is attached;
- no first-promotion-specific access log exists; and
- all answers are public.

INT-R9's named-human block is therefore still correct and should be preserved.

## 8. Findings

### `INT-R9-J-001` — material

The prompt's null-calibration premise is false, and INT-R9's correction is incomplete by one
synthetic manifest. Correct exact count: four non-null, eleven null.

### `INT-R9-J-002` — material

The prompt's uniform research-authority premise is false. Correct exact count: five production,
six governed, four research.

### `INT-R9-J-003` — minor

Distinguish a committed `gold_card` key from a non-null card. The holdout conclusion remains.

### `INT-R9-J-004` — commendation

Every other load-bearing orientation assertion in the audit brief was verified, including the
13/15 denominator, ua integrated depth, zero-conversion state, registry profile counts, GY
prospectivity gate, and malformed frontmatter warning.

## 9. Orientation conclusion

The supplied orientation was useful but not authoritative. Its two incorrect generalizations show
why INT-R9 was right to demand pinned verification. INT-R9 caught the central calibration error
but stopped one manifest short of a complete correction. No conclusion should henceforth cite
“all null,” “three manifests,” or “authority research” without this exact ledger.
