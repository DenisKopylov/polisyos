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

## First live contracts and append-only codec correction

The first DeepSeek response passes the unchanged typed DTO. The first MiniMax
response fails the adapter's raw JSON decode. Their complete deciding captures
and verdicts retain separate original declaration hashes. The precise cause of
MiniMax's malformed text is `not_established`: that failed raw response was not
retained, and its byte hash does not identify its syntax.

Inspection then found a P27 mismatch introduced by this adapter: the existing
extraction owner already has a text codec accepting a JSON object surrounded by
text. `sdk-owner-codec-red.json` proves the adapter rejected an input that the
existing codec supports. The v2 adapter now delegates to that owner, preserving
the structural check and unchanged extraction DTO; its complete transport tests
pass in `sdk-owner-codec-green.json`. Attempt observations advance from v1 to v2;
the original v1 observations remain readable, with their original hashes.

`declare_contract_retry --declare` appends one dated MiniMax contract retry and
two revised six-input pilot declarations. The previous declarations remain.
There is no outcome-based input replacement. The newly observed live rate differs
from the first metadata read; both observations are retained and every pilot
binds the rate its own declaration names. This is calculated cost at an observed
rate, not an account billing assertion.
