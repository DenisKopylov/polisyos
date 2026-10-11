# Ukraine Demography Artifacts

This package owns typed readers for Ukraine static-aging demographic artifacts.
It is a concrete Data Forge domain package, not an extension placeholder.

## Read one snapshot

The composite `load_demography_artifacts` reader selects one complete snapshot: either
the hierarchical `new` layout (`demography/targets.json` and
`demography/transition_priors.json`) or the flat `legacy` layout. If both complete
layouts exist, callers must select one explicitly. The optional donor file belongs to
that selected layout and may be absent.

The scalar readers `load_reconciled_targets`, `load_transition_priors`, and
`load_donor_pool` accept the same optional keyword-only `layout="new"` or
`layout="legacy"`. Without a selection, each reader can auto-select one complete layout or preserve
its historical isolated single-member read. Supplying `layout="new"` or
`layout="legacy"` requires that snapshot's targets and priors even when the caller
requests one scalar member or only the optional donor. Partial or mixed inputs and
ambiguous complete layouts are refused.

`load_donor_pool` returns `{}` only when no layout is selected and no known demographic
member exists, or when the selected complete layout omits its optional donor. Missing
selected layouts, malformed present members, and mixed inputs raise instead of being
interpreted as absence. When reading multiple scalar members, pass the same `layout`
to each call; use `load_demography_artifacts` when one typed aggregate is preferable.

## Evidence boundary

These readers validate one file layout and the array shapes needed by static aging.
They do not establish an authoritative source inventory, producer identity, custody,
profile, law, currentness, or external approval. The `UkraineDemographyArtifacts`
value is a validated candidate input, not an authority receipt.
