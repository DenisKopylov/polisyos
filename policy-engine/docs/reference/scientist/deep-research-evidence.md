# Scientist Deep Research Evidence Stack

Status: Phase 1.3 runtime contract; proposed deep-research schema 1.1 remains pending G.
Owner: `@scientist-owners`

Source of truth:

- `src/polisyos/scholar/search/models.py`
- `src/polisyos/scientist/evidence/**`
- `src/polisyos/scientist/agent/tools/scholar_search_tools.py`
- `src/polisyos/scientist/methods/research_dag/projections.py`
- `tests/unit/scientist/evidence/**`
- `tools/ci/check_scientist_best_in_class_phase1_3.py`

## Canonical Contract

Scientist does not define a duplicate web evidence bundle. The canonical
contract remains `polisyos.scholar.search.models.WebEvidenceBundle`.

Phase 1.3 adds only additive fields:

- `fetch_safety_events: list[FetchSafetyEvent]`
- `source_quality_signals: list[SourceQualitySignal]`

### Proposed provider-attempt trace (WebEvidenceBundle 1.1; pending G)

The candidate additive `SearchQueryTrace.provider_attempts` field stores one
`ProviderAttemptTrace` for each provider call actually observed by the existing
failover policy. The record retains call order, observed outcome, the cause the
adapter established, available response/normalization/constraint counts, and a
fixed error category plus a bounded exception type. It never persists exception
text, request URLs, credentials, search terms copied from an exception, or
response payloads. Legacy search APIs may still return their existing public
failure text; the persisted candidate trace does not. It does not add a provider,
request, retry, schedule, or source-quality rule.

The existing 1.0 reader remains valid: absent attempt detail stays absent and
unknown; existing CAS objects are not rewritten. When a 1.0 bundle is resumed or
re-emitted as a new 1.1 candidate, its historical free-text query/frontier errors
are projected to `legacy_error_not_established`; no attempt, provider cause, or
exhaustion fact is inferred. Every 1.1 query/frontier error is constrained to a
fixed category even when attempt detail is absent. The candidate producer changes
new writes to 1.1; that behavior is not accepted for publication until G selects
the wire-version change. A 1.0 payload containing attempt data is invalid. On a
1.1 trace, strict nonnegative integer counts and
cross-field validation reject impossible error/hit/empty states and reconcile
known raw, normalized, eligible, rejected, and returned counts. Unknown counts
remain nullable; legacy list-only providers and unobservable upstream populations
are not assigned fabricated rejection causes.

An attempt sequence records calls, not the configured provider roster. It cannot
establish that a provider list was complete, that no source exists, or that a
search is globally exhausted. A nonempty provider result followed by an
inaccessible page does not trigger a new search fallback. Attempt detail is
persisted in the canonical Scholar CAS artifact; this proposal adds no new
supported Python symbol or HTTP endpoint. Existing human-facing evidence
rendering and the summary-only SKG projection remain unchanged until G assigns
any additional surface requirement.

`ClaimSupportLink.claim_id` maps to Phase 1.1 claim ids when available.
Legacy/local projections keep `metadata.claim_id_namespace = "legacy_local"`.

## Evidence Boundary

External web/page text is untrusted evidence data. It must never be treated as
system, developer, policy, governance, or tool-control instructions.

The safe-fetch/tool layer enforces:

- HTTP/HTTPS-only URL policy.
- SSRF/private-network blocks for localhost, link-local and private addresses.
- domain allow/block lists.
- MIME/content-type policy.
- max bytes, max snippets and max extracted characters.
- script/style/noscript/template/svg stripping.
- instruction-like phrase neutralization.
- prompt-injection warning events that do not self-certify safety.

## Helpers

| Helper | Role |
| --- | --- |
| `safe_fetch.py` | URL/content policy checks, blocked fetch result creation, prompt-injection detection, text neutralization. |
| `source_quality.py` | Deterministic authority, freshness, primary-source, anti-SEO and duplicate heuristics. |
| `snippet_ledger.py` | Stable snippet ids, snippet ledger entries and span validation. |
| `claim_support.py` | Claim-to-snippet support projection with support status metadata. |
| `cache.py` | Scientist defaults for the CAS-backed Scholar URL/content cache. |
| `verifier.py` | Bundle integrity checks for snippets, sources, support links and safety warnings. |

## Rendering

`KnowledgeToolkit.format_web_evidence_context(...)` renders web evidence with an
explicit untrusted-data warning, safety events, support status and quality
signals. Snippet text is still citation data, not prompt authority.

Decision packets render persisted bundles from
`artifacts_index.web_evidence_bundle_ref` into a `web_evidence` section with
claim-support links, safety events, source-quality signals and capped untrusted
snippets. The raw Scholar bundle remains the exportable source artifact.

## Research DAG Projection

`project_web_evidence_bundle_to_research_dag(...)` projects evidence bundles as:

- `question` nodes for the research brief.
- `source_acquisition` nodes for query graph nodes.
- `source_read` nodes for fetched sources.
- `extraction` nodes for snippets, with raw snippet content redacted into
  fingerprints/safety labels.
- `verification` nodes for claim-support links.
- `governance` nodes for fetch safety events.

## Required Negative Cases

- `http://169.254.169.254/...` blocks by default.
- localhost/private network URLs block by default.
- blocked domains do not fetch.
- unsupported MIME types emit block events.
- malicious page text containing instruction-injection phrases is stored only as
  untrusted snippet text and emits a safety event.
- claim-support links with missing snippet ids fail validation.

## Rollout

Phase 1.3 is library/helper-first. It is safe to run in tests and local shadow
runs without live LLM use. Production fail-closed behavior is controlled by:

- `scientist.best_in_class.wave1.phase1_3.deep_research_evidence`
- `scientist.best_in_class.wave1.phase1_3.safe_fetch_fail_closed`
- `scientist.best_in_class.wave1.phase1_3.claim_support_required`

Source quality is a heuristic signal only. It is not a truth score and must not
be presented as proof that a source is correct.
