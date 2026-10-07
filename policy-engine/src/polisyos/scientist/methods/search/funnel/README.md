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
permission authority. The durable profile consumes canonical B1.2 intent,
settlement and completion receipts. An appointed production blueprint resource
producer remains a separate deployment input.

Checks: `tests/integration/scientist/methods/search/funnel/test_cache_settlement_binding.py`
uses the real env-backed gateway factory, native response-text decoder, cache and
traced completion, enforcer, funnel and fresh file-ledger readback. Controls retain
typed markers while removing receiver observation or paid-origin readback, and
mutate returned content after issuance. The provider HTTP exchange is controlled;
no production billing, native draws or promotion authority is claimed.

A supplied `CorrelationTracker` also persists its existing `1.0` snapshot in the
calibration report metadata consumed by the native runtime resolver. Report/CAS
readback keeps the original paired observations, record metadata, thresholds and
routing state. An absent tracker keeps the legacy read-only projection; an
explicit empty tracker remains `not_established` with no measured drift. Removing
the snapshot while retaining normal/sample-count labels cannot reconstruct it.
Empty report rate/correlation values and corresponding acceptance criteria remain
null and unassessed in JSON/CAS and display `n/a`/`GAP` in Markdown. An observed
zero correlation remains a numerical zero and keeps its actual verdict. This
transports supplied state; it does not appoint evidence, tenant scope or promotion
authority.


The native configured policy worker factory composes the supplied initialized B
middleware and actual run identity before calling the provider. Intersecting
unresolved completion refuses next work through the existing owner admission API.
A response obtained with invalid or nonrepresentable monetary evidence retains
`amount=None`; funnel feedback serializes that amount as JSON null with unknown
reported-input status. It cannot become a settled zero or an estimated charge.
Unknown settlement ACK with a known amount stays distinct; exact fresh receipt
readback confirms local debit without completing any pending owner obligation.

The ordinary enforcer supplies the same read-only exact receipt resolver for
standalone native cache consumption. A missing paid-origin receipt refuses reuse;
no cache marker grants a charge or permission. The gateway's configured factory
supports `generate`; a supplied invoke SDK adapter can use the enforcer's existing
invoke port, without implying native gateway cache support for that port.

Response-text tests retain actual tiny numeric tokens until the B-owned decoder,
then check canonical pending obligations and fresh ledger/CAS readers. Explicit
provider null is invalid-present; omitted cost can be priced only from supported
validated observed usage. Real literal zero keeps its known zero receipt. The
native configured caller tests control HTTP bytes, not an invoice, native raw
sample law, authorized estimate refinement or promotion permit authority.


The paid-origin predicate runs in the durable enforcer before any reuse zero ACK
or release, and again at the funnel's first financial observation. Generic cache
receiver evidence is operational; D money intake additionally requires current
canonical receipts. The guard-removal control retains the genuine issuer, paid
content/DTO/ledger bytes and raw cache markers while removing only current
receipt readback, then shows that removing financial admission would admit the
forbidden zero ACK. Actual physically executed unknown-cost controls retain
pending/reserved state. A physically unentered cache-only refusal can abort its
own intent, preserving the original paid receipt and issuing no new charge ACK.


A failed settlement keeps reported and usage-priced estimated inputs as distinct
feedback components. `resource_reported_input_usd` is null unless an actual
reported row exists; a genuine reported zero remains a measured zero. The
additive `resource_estimated_input_usd` and corresponding status preserve known
estimates without presenting them as provider reports. Unknown amount remains
unknown; an observed known subset alongside unknown input is partial. Pending
producer event payloads retain each amount, origin and stable identity. The
ordinary runtime outcome serializer and fresh JSON/CAS reader retain both
components. These input amounts do not establish settled debit or invoice truth.
