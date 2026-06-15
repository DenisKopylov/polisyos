# Privacy Compliance Evidence

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/quality/privacy_compliance.py`, `tools/ops_runners/runtime/canary_evidence.py`, and `tests/unit/runtime/quality/**`

`privacy_compliance_report_ref` is the runtime evidence handle for privacy,
licensing, and public-export compliance. It is intentionally separate from
source quality reports: governance reviewers can audit compliance status from a
canary evidence bundle without rerunning Fabric source selection.

The canary bundle writes:

- `quality_evidence/privacy_compliance_report.json`
- `quality_evidence.privacy_compliance_report` in `bundle.json`
- `privacy_compliance_report_ref` in the quality scorecard evidence refs

## Report Shape

The report schema is `policyos.privacy_compliance_report.v1`.

Top-level fields:

- `status`: `pass`, `warn`, or `fail`
- `summary`: counts for production data sources, public artifact families,
  PII-like fields, warnings, and blocking issues
- `production_data_sources`: sanitized source-level compliance summaries
- `public_artifact_families`: sanitized public-output summaries
- `issues`: blocking or warning findings
- `override_requirements`: required fields for exceptional overrides
- `override`: sanitized override validity summary

Raw records, row samples, and sensitive field values must not appear in this
report. Only field names, metadata, status, basis refs, and evidence refs belong
in the bundle.

## Inputs

Canary evidence accepts explicit compliance input under `privacy_compliance`:

```json
{
  "production_data_sources": [
    {
      "source_id": "production-msme-panel",
      "source_family": "production_msme_panel",
      "fields": [
        {"name": "firm_id", "retained": true},
        {
          "name": "owner_email",
          "retained": true,
          "basis": "public_authority",
          "basis_ref": "law://ua.statistics",
          "redaction_status": "redacted"
        }
      ],
      "minimization": {
        "purpose": "Estimate wartime credit policy outcomes.",
        "retained_fields": ["firm_id", "owner_email"],
        "excluded_fields": ["owner_phone"]
      },
      "retention_class": "warm",
      "jurisdiction": "UA",
      "license": "CC-BY-4.0",
      "public_export_allowed": true,
      "source_attribution": "State Statistics Service of Ukraine",
      "authority_basis": "statutory mandate"
    }
  ],
  "public_artifact_families": [
    {
      "artifact_family": "public_policy_brief",
      "jurisdiction": "UA",
      "license": "CC-BY-4.0",
      "public_export_allowed": true,
      "source_attribution": ["production-msme-panel"],
      "redaction_status": "redacted",
      "authority_basis": "public interest publication"
    }
  ]
}
```

If explicit compliance input is absent, the bundle still emits a report and
summarizes production sources discoverable from Fabric retrieval evidence.

## Blocking Rules

The compliance gate blocks production approval when:

- a PII/PHI-like field has no approved basis and no approved redaction status
- a production data source or public artifact family has restricted license
  terms, such as internal-only, no redistribution, proprietary, confidential, or
  non-commercial terms
- a source or artifact family is marked `public_export_allowed: false`
- an attempted compliance override omits reviewer identity, reason, scope,
  expiry, or evidence refs

Accepted PII/PHI controls include an explicit consent, authority, legal, or
processing basis, or a redaction status such as `redacted`, `masked`,
`tokenized`, `pseudonymized`, `anonymized`, `deidentified`, or `aggregated`.

## Override Requirements

Compliance override packets must be reviewer-attributed. Required fields:

- `reviewer_identity`
- `reason`
- `scope`
- `expires_at`
- `evidence_refs`

An incomplete override is itself a blocking compliance issue. A valid override
is recorded in the report but does not remove the underlying finding; production
approval still depends on the governance approval packet.
