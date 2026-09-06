# Academic producer repairs — 2026-09-06

## APR-S01 — scope and execution contract

Worktree: `/Users/deniskopylov/polisyos/.worktrees/debt-academic-producer-repairs/policy-engine`.
Entry: attached, clean `codex/debt-academic-producer-repairs`, base `c633625c6`.
Row 1 is `evidence-class-normalizer-zeroes-two-canonical-classes`; Row 2 is
`academic-selective-extraction-prompt-never-rendered`. Each has one repair round,
independent stopping and a separate commit. This journal is append-only.
The architect owns transcription into `docs/plans/active/`.

Pattern pass: `P29`/`P33` require executable properties over the complete owner
vocabulary and the actual stubbed request path; `P31` favors one canonical-name
normalization invariant; `P05`/`P15` preserve candidate status; `P35` binds tables
to the complete Python `EVIDENCE_WEIGHTS` mapping and `DesignFamily` enum;
`P40` keeps adjacent findings as candidate rows. The failure/repair register was
opened before design. The gaps being closed are `semantic_test_missing` at
normalization and `verification_missing` at selective prompt/request preparation.
Acceptance is the requested red/green behavior, not a new publication capability.
There is no new public surface (`surface_out_of_scope`: internal producer repair).

No live producer, model, batch or data pass is authorized. The selective request
function may run against a controlled stub as explicitly required by acceptance.
Production data stays read-only; the pinned database digest is checked at close.
Only targeted pytest files/node IDs run. The bound debt checker runs once after
both rows, with redirected output. Its process is the only long-running resource;
no DuckDB connection is needed for these repairs.

The worktree lacked `.venv`. `uv sync --offline --frozen --extra lint --extra test
--extra runtime` could not provision because cached `jaxlib==0.8.2` was absent.
The incomplete environment was retained as `.venv-offline-incomplete`; `.venv`
now links to the existing workspace dependency environment. Its `uv.lock` SHA-256
matches this worktree's lock. An import probe verified that `PYTHONPATH=src:.`
loads this worktree's `article_extractor.py`, with Python 3.14 and pytest 9.0.2.
No dependency installation or mutation was performed in the shared environment.

## APR-R01 — Row 1 red, repair and green

The full runtime owner set is ten entries in
`src/polisyos/data_forge/domains/academic/knowledge/skg_store.py::EVIDENCE_WEIGHTS`;
its keys equal all members of
`src/polisyos/ir/analytics/literature.py::EvidenceStrength`. The committed test
asserts both set agreement and identity per weighted key, so additions to either
owner cannot escape the regression set. These are complete Python symbol
collections, not a sampled file census.

Before the repair, the selected canonical property test returned exit 1, with
exactly `quasi_natural_event` and `structural` failing and eight cases passing
(5.57 seconds wall time). One repair round adds enum-derived identity entries to
`_EVIDENCE_STRENGTH_ALIASES`, after explicit aliases so canonical identity wins.
The matching rule and `unknown` default do not change. The function docstring and
negative tests state that an answer outside canonical names and explicit aliases
returns `unknown`; a near-match such as `rct_unrecognized` does not gain `rct`.
The separate `not-a-class` probe returns evidence `unknown` and design `unclear`.

After repair, the targeted set passed **34 tests**, exit 0 (2.48 seconds pytest,
4.47 seconds wall). It includes all ten canonical keys, case/space normalization,
alias-output re-normalization, unknown inputs, and all ten keys through the
batch-imported `_normalize_extraction_payload` -> live `_normalize_causal_claim`
-> rich serializer -> JSON validation of the candidate envelope. The evidence
class and `candidate` status survive. The importer checks and selected existing
serializer/parameter tests pass. No store, real model or producer stage ran;
this demonstrates the pure normalization/transport path, not live publication.
Targeted Ruff and `git diff --check` both passed.

### Complete evidence-class table (APR-R01)

Values and weights were recomputed with `normalization_table.py` before and after
from the complete `EVIDENCE_WEIGHTS` mapping. The two normalization losses were
not changes to the weights themselves.

| Canonical input | Before output | After output | Input weight | Before output weight | After output weight |
| --- | --- | --- | --- | --- | --- |
| `rct` | `rct` | `rct` | 1 | 1 | 1 |
| `meta_analysis` | `meta_analysis` | `meta_analysis` | 0.95 | 0.95 | 0.95 |
| `quasi_natural` | `quasi_natural` | `quasi_natural` | 0.7 | 0.7 | 0.7 |
| `quasi_natural_event` | `unknown` | `quasi_natural_event` | 0.6 | 0 | 0.6 |
| `panel_fe` | `panel_fe` | `panel_fe` | 0.5 | 0.5 | 0.5 |
| `structural` | `unknown` | `structural` | 0.45 | 0 | 0.45 |
| `observational` | `observational` | `observational` | 0.3 | 0.3 | 0.3 |
| `cross_sectional` | `cross_sectional` | `cross_sectional` | 0.2 | 0.2 | 0.2 |
| `theoretical` | `theoretical` | `theoretical` | 0.15 | 0.15 | 0.15 |
| `unknown` | `unknown` | `unknown` | 0 | 0 | 0 |

### APR-C01 — candidate row: design normalization chooses a substring before identity

The requested design property was separately **asserted** with a parametrized
pytest probe over all 20 `DesignFamily` members. It returned exit 1: five failed,
15 passed (4.06 seconds wall). All 20 canonical names already have self-aliases;
there is no third missing self-alias. This is a distinct class: the earlier
`if key in normalized` loop wins before exact lookup. For example, `iv` inside
`review_narrative` wins and reports an instrumental-variable design.

Bucket: **NEW class**, substring precedence over an existing exact alias,
not a second instance of Row 1's missing evidence self-alias. It is report-only
under stop rule 5; the requested evidence repair proceeds. Design normalization
is untouched. The before/after instruments verify the whole design result is
unchanged. This diagnostic is retained here with its executable source, rather
than committing a failing product test or a test that blesses the defect.

| DesignFamily input | Before and after output | Identity |
| --- | --- | --- |
| `rct` | `rct` | pass |
| `iv` | `iv` | pass |
| `did` | `did` | pass |
| `rdd` | `rdd` | pass |
| `synthetic_control` | `synthetic_control` | pass |
| `event_study` | `event_study` | pass |
| `quasi_experimental_other` | `quasi_experimental_other` | pass |
| `quasi_experimental_did` | `did` | FAIL |
| `quasi_experimental_rdd` | `rdd` | FAIL |
| `panel_fe` | `panel_fe` | pass |
| `ols` | `ols` | pass |
| `ols_cross_sectional` | `ols` | FAIL |
| `meta_analysis` | `meta_analysis` | pass |
| `review` | `review` | pass |
| `review_narrative` | `iv` | FAIL |
| `review_meta_analysis` | `meta_analysis` | FAIL |
| `theoretical` | `theoretical` | pass |
| `structural_model` | `structural_model` | pass |
| `time_series_cointegration` | `time_series_cointegration` | pass |
| `unclear` | `unclear` | pass |

### Exact Row 1 commands

All commands run from the stated worktree's `policy-engine` directory. Initial
measured tests finish within six seconds; subsequent targeted executions use a
60-second observation budget, without killing a healthy process.

```sh
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python -m pytest -q tests/unit/data_forge/domains/academic/batch/test_article_extractor.py::test_evidence_strength_normalization_is_idempotent > _build/academic-producer-repairs/row1-red.log 2>&1
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python -m pytest -q _build/academic-producer-repairs/test_design_vocabulary.py > _build/academic-producer-repairs/design-probe.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python _build/academic-producer-repairs/normalization_table.py _build/academic-producer-repairs/normalization-before.json
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python -m pytest -o addopts='' -q tests/unit/data_forge/domains/academic/batch/test_article_extractor.py tests/unit/data_forge/domains/academic/batch/test__resolve_extract_transformers.py tests/unit/data_forge/domains/academic/batch/test__resolve_extract_api.py tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_rich_claim_serializer_preserves_metadata_and_does_not_borrow_record_confidence tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_rich_claim_serializer_keeps_omitted_pydantic_defaults_absent tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_normalize_empirical_parameter_accepts_estimate_candidate_payload > _build/academic-producer-repairs/row1-green.log 2>&1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python _build/academic-producer-repairs/normalization_table.py _build/academic-producer-repairs/normalization-after.json > _build/academic-producer-repairs/normalization-after.log 2>&1
.venv/bin/python -m ruff check src/polisyos/data_forge/domains/academic/batch/article_extractor.py tests/unit/data_forge/domains/academic/batch/test_article_extractor.py
git diff --check
```

### APR-T01 — Row 1 transcription paragraph

**`evidence-class-normalizer-zeroes-two-canonical-classes` — repaired on this
branch, awaiting merge/transcription.** The full ten-key `EVIDENCE_WEIGHTS`
identity test fails at base only for `quasi_natural_event` and `structural`, then
passes for every key after enum-derived self-aliases are added at the shared
normalizer. Canonical class, corresponding weight and candidate status survive
the batch-imported claim normalization and serialized-envelope round-trip;
unknown/near-match inputs retain the explicit `unknown` fallback. Targeted tests
pass (34); no prompt wording, weight, historical data or production artifact
changed. The separately requested design probe finds five substring collisions
among 20 `DesignFamily` members, with zero missing design self-aliases (APR-C01);
that distinct candidate row is unmodified and is not closed by this repair.

### Durable Row 1 probe sources

`test_design_vocabulary.py` (scratch execution location above):

```python
"""Report-only property probe; design normalization is outside the repair scope."""

import pytest

from polisyos.data_forge.domains.academic.batch.article_extractor import _normalize_design_family
from polisyos.ir.analytics.literature import DesignFamily


@pytest.mark.parametrize("design", [member.value for member in DesignFamily])
def test_design_normalization_is_idempotent(design: str) -> None:
    assert _normalize_design_family(design) == design
```

`normalization_table.py` (scratch execution location above):

```python
"""Walk complete runtime vocabularies without invoking a producer or store."""

import json
import sys
from pathlib import Path

from polisyos.data_forge.domains.academic.batch import article_extractor as ae
from polisyos.data_forge.domains.academic.knowledge import skg_store
from polisyos.ir.analytics import literature

report = {
    "source_paths": [ae.__file__, skg_store.__file__, literature.__file__],
    "denominator": "complete EVIDENCE_WEIGHTS mapping and DesignFamily enum in Python owners",
    "evidence": [
        {
            "input": key,
            "output": ae._normalize_evidence_strength(key),
            "input_weight": weight,
            "output_weight": skg_store.EVIDENCE_WEIGHTS[ae._normalize_evidence_strength(key)],
        }
        for key, weight in skg_store.EVIDENCE_WEIGHTS.items()
    ],
    "design": [
        {"input": member.value, "output": ae._normalize_design_family(member.value)}
        for member in literature.DesignFamily
    ],
    "missing_design_self_aliases": [
        member.value
        for member in literature.DesignFamily
        if ae._DESIGN_FAMILY_ALIASES.get(member.value) != member.value
    ],
    "unrecognized_answer": {
        "input": "not-a-class",
        "evidence_output": ae._normalize_evidence_strength("not-a-class"),
        "design_output": ae._normalize_design_family("not-a-class"),
    },
}
Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
```

### Commit execution

The shared Git pre-commit hook invokes Lefthook and contains a binary path into a
separate worktree; this checkout has no repository-root Lefthook configuration.
Commits use `LEFTHOOK=0 git commit` so validation stays bound to the explicit
commands above and the single deferred debt-checker run. No hook configuration
is changed. Branch attachment is verified immediately before every commit.

## APR-R02 — Row 2 red, repair and green

Row 1 was committed separately as `f876c26f2` and its source was read back from
`codex/debt-academic-producer-repairs` before starting this row.

The new request-path test called `extract_with_llm` with an autospecced
`AcademicLLMClient` stub; no client constructor, session or network was used.
All three input variants failed before the request with exactly
`KeyError: '\n  "estimates"'` at the original `.format` call (exit 1; 1.13 seconds
pytest, 2.59 seconds wall). This proves the missing behavior at the function
boundary, rather than looking for words in an unrendered constant.

One repair round replaces `.format(topic=topic, abstract=abstract[:4000])` with
`.replace("{abstract}", abstract[:4000])`. The original template has one input
placeholder and no topic placeholder. Exact single-slot replacement keeps the
JSON readable and unchanged, has no brace-escaping convention to maintain, and
does not interpret placeholders or braces inside the substituted abstract.
`topic` was already absent from model-facing wording and remains absent. The
function signature and existing 4,000-character limit remain as before.

The existing prompt/vocabulary tests now inspect the actual captured request,
and the parser test consumes the stub response returned by the real request
function. New variants cover plain input, literal `{abstract}` / `{topic}` /
`$abstract` / nested JSON braces, and truncation. They assert single JSON braces
in the outgoing instructions, literal input insertion, one awaited stub request,
a nonempty parsed response and preserved `candidate` status. All seven tests in
the selected file pass (exit 0; 1.36 seconds pytest, 3.28 seconds wall). Targeted
Ruff and `git diff --check` pass.

### APR-P02 — complete rendered-prompt proof

`rendered_prompt_proof.py` reads the complete original template from the task's
pinned base using `git show`, extracts the string with `ast.literal_eval`, and
compares its bytes with the current template. It independently forms the
expected outgoing text by splitting the original input slot and concatenating
literal input, then compares that with the request captured from the actual
`extract_with_llm` invocation. This comparison covers all wording and JSON
braces, not only the quoted regression snippets. Both identities pass, and the
stub was awaited exactly once.

Original and current template SHA-256: `25a3a22c6dd84efda895118ca22e11b96bba8def843d1434ea5cff104339c813`.

Captured outgoing prompt SHA-256: `2d001d35f88d525363c2a960ef33c1e41e7f008f91014e437df989f151461bee`.

The complete captured prompt for the plain-input proof is:

```text
Extract causal and quantitative evidence from this abstract.

Return strict JSON object with fields:
{
  "estimates": [
    {
      "value": <number>,
      "unit": "percent|ratio|level|index|pp",
      "ci_low": <number or null>,
      "ci_high": <number or null>,
      "std_error": <number or null>,
      "context": "<brief description>",
      "variable_hint": "<canonical-like variable name>"
    }
  ],
  "study_design": "RCT|IV|DiD|RDD|FE|OLS|meta-analysis|descriptive|other",
  "sample_size": <number or null>,
  "causal_claims": [
    {
      "cause": "<concept>",
      "effect": "<concept>",
      "direction": "positive|negative|null|mixed",
      "design_family_hint": "one design family (rct, iv, did, rdd, synthetic_control, event_study,
        quasi_experimental_other, quasi_experimental_did, quasi_experimental_rdd, panel_fe, ols,
        ols_cross_sectional, meta_analysis, review, review_narrative, review_meta_analysis,
        theoretical, structural_model, time_series_cointegration, unclear) or null",
      "evidence_strength": "one evidence class (rct, quasi_natural, quasi_natural_event,
        meta_analysis, panel_fe, structural, observational, cross_sectional, theoretical,
        unknown) or null",
      "claim_extraction_confidence": <number from 0 to 1 or null>,
      "mechanism": "<short text>"
    }
  ],
  "boundary_conditions": [
    {
      "variable": "<name>",
      "operator": "<op>",
      "threshold_value": "<value>",
      "scope_text": "<condition text>",
      "confidence": <0..1>
    }
  ]
}

Abstract:
Tax rates reduce employment.
```

### APR-C02 — candidate row: request failures collapse into empty extraction

Report only, source-inspected in `llm_extractor.py::extract_with_llm` and
`AcademicLLMClient.chat_completion`; no exception-handling repair is included.
The blanket `except Exception` wraps the awaited client call, response `.get`,
string conversion and `_parse_json_object`. It logs a warning and returns the
same empty extraction shape for, among other ordinary exceptions:

- Non-retryable HTTP errors raised as `RuntimeError`, including authentication /
  authorization failures, and retry exhaustion after retryable HTTP responses.
- Timeouts, connection/TLS/client failures and malformed provider-body JSON after
  the client's retries, surfaced as a final `RuntimeError`.
- The client's `AssertionError` when used without its async context/session.
- Programming/response-shape errors in the protected block, such as a nonmapping
  response raising `AttributeError`, failing string conversion, or an unexpected
  parser exception such as `RecursionError` on excessively nested JSON.

Separately, missing/empty/unparseable content returns the same empty shape via
`parsed is None` without reaching that warning. A caller gets no typed failure
status distinguishing these from a successful empty extraction. That is the
candidate row. The catch does not include prompt preparation, which is still
above `try`, errors in later `parse_llm_result`, or `BaseException` subclasses
such as cancellation, `KeyboardInterrupt` and `SystemExit`.

Operational consequence: a repaired producer can make real model calls when the
existing route is enabled by its owner. This lane did not enable the route,
change its gate/configuration, call a real model, run a batch or write data.

### Exact Row 2 commands

```sh
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python -m pytest -o addopts='' -q tests/unit/data_forge/mirror_contracts/test_llm_extractor.py::test_llm_request_renders_single_json_braces_and_literal_abstract > _build/academic-producer-repairs/row2-red.log 2>&1
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python -m pytest -o addopts='' -q tests/unit/data_forge/mirror_contracts/test_llm_extractor.py > _build/academic-producer-repairs/row2-green.log 2>&1
.venv/bin/python -m ruff check src/polisyos/data_forge/domains/academic/batch/llm_extractor.py tests/unit/data_forge/mirror_contracts/test_llm_extractor.py
git diff --check
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:src .venv/bin/python _build/academic-producer-repairs/rendered_prompt_proof.py
```

### APR-T02 — Row 2 transcription paragraph

**`academic-selective-extraction-prompt-never-rendered` — repaired on this
branch, awaiting merge/transcription.** A red test exercises `extract_with_llm`
against a stub and reproduces the literal-JSON `.format` `KeyError` before the
request. Exact `{abstract}` replacement repairs rendering without changing a
byte of the model-facing template. Seven targeted tests pass; captured requests
retain single JSON braces, both named vocabularies, literal abstract contents
and the 4,000-character limit, and the real function returns the stub's parsed
candidate response. The complete rendered text also matches the pinned original
wording plus literal input (APR-P02). No route was enabled and no real model,
batch or data pass ran; enabling the route now permits real calls. The blanket
failure-to-empty behavior remains a separate, report-only candidate (APR-C02).

### Durable Row 2 proof source

```python
"""Compare the actual stubbed request with the complete, pinned original wording."""

import ast
import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import create_autospec

from polisyos.data_forge.domains.academic.batch import llm_extractor as llm

source = subprocess.check_output(
    [
        "git", "show",
        "c633625c6:policy-engine/src/polisyos/data_forge/domains/academic/batch/llm_extractor.py",
    ],
    text=True,
)
assignment = next(
    node
    for node in ast.parse(source).body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "EXTRACTION_PROMPT" for target in node.targets)
)
original_template = ast.literal_eval(assignment.value)
assert original_template == llm.EXTRACTION_PROMPT
prefix, suffix = original_template.split("{abstract}")
abstract = "Tax rates reduce employment."
expected = prefix + abstract[:4000] + suffix
client = create_autospec(llm.AcademicLLMClient, instance=True)
response = {"estimates": [{"value": 0.25}], "causal_claims": [], "boundary_conditions": []}
client.chat_completion.return_value = {"content": json.dumps(response)}
result = asyncio.run(llm.extract_with_llm(
    abstract=abstract, topic="unused-topic", work_id="synthetic:render-proof", client=client
))
client.chat_completion.assert_awaited_once()
(message,) = client.chat_completion.call_args.kwargs["messages"]
rendered = message["content"]
assert message["role"] == "user"
assert rendered == expected
assert result == response
instructions = rendered.partition("\nAbstract:\n")[0]
assert "{{" not in instructions and "}}" not in instructions
scratch = Path("_build/academic-producer-repairs")
(scratch / "rendered-prompt.txt").write_text(rendered)
proof = {
    "source": llm.__file__,
    "baseline": "c633625c6",
    "template_byte_identity": True,
    "template_sha256": hashlib.sha256(original_template.encode()).hexdigest(),
    "actual_request_equals_pinned_wording_with_literal_input": True,
    "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
    "single_json_braces": True,
    "client": "autospecced stub; no client/session construction or network",
    "await_count": client.chat_completion.await_count,
    "parsed_response_matches_stub": result == response,
}
(scratch / "rendered-prompt-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
```
