# Pre-call review corrections, 2026-09-09

The new model declarations were committed before calls at `0b998499f`.
These corrections append; neither the frozen six inputs nor either declaration
changes. No authenticated request preceded this review.

Three concrete properties were checked before execution. Parsed-response custody
is a new class: JSON Unicode escapes could materialize a credential after the
envelope scan. `sdk-decoded-secret-red.json` demonstrates the missed refusal.
The exact decoded object now passes the same credential guard before reaching any
owner or logger; `sdk-decoded-secret-green.json` records the repaired path.

Provider observation attribution is a separate class. The adapter now retains
both the requested and reported model. A reported mismatch refuses comparison
credit without losing observed usage. `sdk-reported-model-red.json` demonstrates
the previous attribution gap, and `sdk-reviewed-green.json` checks the repair.
A matching reported ID remains an observation, not backend identity attestation.

The contract probe also calls the existing structural validator before the
existing typed extraction owner. An empty object cannot gain contract credit
through normalization defaults. `contract-shape-red.json` and
`contract-shape-green.json` retain the refusal and valid-shape control. No
extraction DTO, normalizer, closed workstream, or governed receipt epoch changed.

The pilot reporter must use raw boolean screening judgments, treating non-booleans
as ambiguous. It must calculate cost from observed token usage and the live rate;
the legacy extractor's zero USD field is not a provider cost measurement.

`root-reviewed-ruff.json` is a diagnostic-test annotation/style nonreceipt;
`root-reviewed-ruff-final.json` is the corrected scoped lint gate.
