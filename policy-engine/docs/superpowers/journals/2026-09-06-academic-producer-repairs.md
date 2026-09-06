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
