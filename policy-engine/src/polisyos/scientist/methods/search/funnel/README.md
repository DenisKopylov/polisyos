# Funnel resource accounting

A configured `BudgetMiddleware` is the resource owner. Provider events count
only after their exact typed spend receipts resolve from that owner's canonical
ledger. Trace cost, status fields and result estimates do not establish debit.

Cache reuse also requires the existing cache receiver's runtime issuer proof,
exact request/content/model/provider binding and the original paid receipts.
`LLMBudgetEnforcer` forwards reuse to the funnel while that receiver context is
live. The native returned-response observer then accepts only the same verified
stage event with unchanged content; a `reuse` kind, cache flag, guessed origin ID
or freely constructed committed ACK cannot create free accounting.

New reuse without the live receiver proof refuses. Existing native callers still
observe returned responses before payload parsing. Receipts and the current
producer IDs are operational evidence, not external invoice or promotion
permission authority. This uses the B1.1 ledger profile on the exact D source;
B1.2 adoption and an ordinary production blueprint resource producer remain
separate owner contracts.

Checks: `tests/integration/scientist/methods/search/funnel/test_cache_settlement_binding.py`
uses the real env-backed gateway factory, native response-text decoder, cache and
traced completion, enforcer, funnel and fresh file-ledger readback. Controls retain
typed markers while removing receiver observation or paid-origin readback, and
mutate returned content after issuance. The provider HTTP exchange is controlled;
no production billing, native draws or promotion authority is claimed.
