# Lex impact report selected-view migration

The version 1.1 `NormImpactReport` stores the complete issued `NormDiff` artifact
reference, including kind, media type, and selected manifest profile. Its report
manifest carries the same `norm_diff` input edge. A fresh
`load_norm_impact_report` call requires the selected report profile, resolves the
report and diff, reconciles the edge, and reconstructs the embedded rule
changes with `diff_norm_packs` before returning `exact_selected`. It reconciles
report counts, candidate topics, the coarse ID, declared scopes, and replays the
carried issue records through the existing delta producer. It also checks issue
pass membership, issue-total lower bounds and delta aggregates. These are
internal consistency checks:
they do not establish completeness or authenticity of the originating packs,
correctness of legal issue records, source-law, issuer, currentness, complete
comparison-context, or publication authority.

## Reader-first rollout and rollback

1. Upgrade all report readers to the versioned owner before enabling 1.1
   writers. Existing strict 1.0-only Pydantic readers reject the new field; they
   must not silently treat a 1.1 payload as 1.0. Preserve the issued report's
   `cas_artifact_ref` so a new reader receives its exact selected profile.
2. The omitted option continues to write 1.0. After verifying consumers, opt in
   with `report_schema_version="1.1"` on `NormImpactAnalyzer` or
   `--report-schema-version 1.1` on `lex impact`. The historical
   `norm_diff_ref` and `cas_artifact_id` strings remain available, while
   `norm_diff_artifact_ref` and the returned `cas_artifact_ref` preserve the
   issued views. The persisted report does not contain its own CAS reference.
3. To roll back, omit the option or explicitly choose `1.0`. Keep the new
   readers in place for already-issued 1.1 reports. A 1.0 report with a diff
   is `legacy_unbound`: its historical string identifies content but not the
   issued manifest profile. A report without a diff is `legacy_absent`.
4. Existing 1.0 bytes and logical report-ID formula are unchanged in storage.
   New reports have different content addresses when descriptions, metadata,
   schema, or selected refs differ. Logical `report_id` is not content-unique;
   use the issued CAS reference for the selected persisted view.

The report's jurisdiction field has historically represented the old pack.
New reports record both input-pack declarations in metadata. A 1.1 persisted
write refuses differing declared scopes before issuing artifacts; 1.0 retains
the comparison while exposing the mismatch. Prior reports may lack both
records and stay explicitly limited. Equal producer-declared values do not
prove source authenticity, actual applicability, or scope completeness.

The metadata describes the configured backend and explicitly leaves complete
comparison-context binding unestablished. Omitted `--legal-backend` retains the
historic stub and reports that no rules were evaluated. `expr_ast` executes only
assigned rules and does not prove source authenticity or complete coverage.
The current CLI does not accept arbitrary comparison-context data.
