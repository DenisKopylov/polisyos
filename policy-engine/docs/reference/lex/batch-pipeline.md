# Data Forge Legal Batch Pipeline

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Freshness: 2026-10-14
Owner: `@data-forge-owners` for offline legal corpus preparation and publication; `@lex-owners` consumes the published runtime surfaces.
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `src/polisyos/data_forge/domains/legal/batch/**`, `src/polisyos/data_forge/domains/legal/corpus/**`, `src/polisyos/data_forge/read_api/legal.py`, and the named tests below.
Evidence level: source and named test behavior were inspected at the source pin; tests were inspected, not run for this documentation refresh. Test fixtures establish only the exercised transformations and publication checks, not the completeness or official status of an external corpus.

The legal batch pipeline is an offline Data Forge producer. It parses source material, extracts structural provisions and candidate facts, resolves references and amendment signals, attaches grounding, quality, and temporal outcomes, and publishes graph/search assets with manifests and quality reports. Extraction output remains candidate data: a found pattern or a populated graph row does not by itself establish issuer authenticity, legal competence, or that the institution's official source set is complete.

Runtime Lex reads published corpus and graph artifacts through `polisyos.data_forge.read_api.legal` and `polisyos.lex.knowledge`. Lex owns runtime version-aware NormPack assembly and claim-scoped legal assessment; it does not own batch preprocessing or the external institution's legal act.

## Key stages

| Stage | Producer output | Boundary |
| --- | --- | --- |
| Parse and structure | Parsed source documents and stable provision anchors | Structure and quote offsets bind an extracted span to processed document bytes; they do not authenticate the publisher. |
| Candidate extraction | Deterministic and gated LLM-assisted SPO/fact candidates | Candidates are subject to downstream grounding and quality classification; an LLM result is not authority. |
| References and amendment signals | Reference edges, amendment candidates, target-resolution signals | Target resolution and amendment metrics report extraction outcomes; unresolved or multi-target cases remain visible. |
| Quote grounding and quality | Quote spans, grounding/trust labels, filter and QC outcomes | Grounding tests the match to the processed text. It does not verify the source institution or legal effect. |
| Temporal resolution | Document/fact `effective_from`, `effective_to`, `temporal_state`, resolution status, and provenance | Missing anchors, incomplete historical windows, and conflicting constraints can remain `partial`, `unknown`, or `conflict`; these values are not issuer confirmations. |
| Graph, embeddings, and publish | DuckDB graph tables, optional content-bound vector generation, QC outputs, and publish manifest | Publication makes a local generation available to consumers subject to their admission checks; it does not elevate candidate facts into institutional authority. |

The staged runner is owned by `data_forge.domains.legal.batch.pipeline`; extraction/grounding and publication behavior is implemented across `postprocess.py`, `graph_builder.py`, `quality_report.py`, and `publish.py`. The canonical runtime is `polisyos.data_forge.domains.legal.batch`, following the Data Forge migration; the prior Lex batch location is not the owner.

## Time and quality interpretation

The batch temporal parser and resolver use source metadata and legal text to propose document and fact temporal envelopes. Relative-date language needs a usable publication/adoption anchor; missing anchors, a historical status without a bounded end, or contradictory constraints stay partial or unresolved. These resolver outputs are extraction evidence consumed downstream, not a substitute for external legal verification.

Do not conflate batch temporal states with Lex's active-version date selection or the amendment-window receipt. Corpus version selection is inclusive at both ends and requires a resolved `effective_from`; the amendment-window receipt uses a half-open effective interval and separately applies visibility-knowledge and purpose-admission cutoffs. See [NormPack](normpack.md#time-identity-and-replay) and [Lex Knowledge](knowledge.md#amendment-window-receipt).

The quality filters and deterministic patterns are tuned for Ukrainian legal materials. Amendment QC distinguishes extraction-row coverage from single-target resolution rates; those figures measure different outcomes and neither proves source-set completeness. Retain missing, unresolved, or low-quality classifications instead of describing them as successful legal authority decisions.

## Reference

::: polisyos.data_forge.domains.legal.batch.amendment_detector

::: polisyos.data_forge.domains.legal.batch.hallucination_detector

::: polisyos.data_forge.domains.legal.batch.quality_filters

::: polisyos.data_forge.domains.legal.batch.temporal_resolver

::: polisyos.data_forge.domains.legal.batch.amendment_metrics

## Code-inspected evidence

- Data Forge migration and ownership: `src/polisyos/data_forge/domains/legal/batch/README.md`, `src/polisyos/data_forge/domains/legal/corpus/README.md`, and `src/polisyos/lex/README.md`.
- Quote grounding and publication readiness: `src/polisyos/data_forge/domains/legal/batch/postprocess.py`, `src/polisyos/data_forge/domains/legal/batch/publish.py`, `tests/unit/data_forge/legal_batch/test_postprocess_grounding.py`, and `tests/unit/data_forge/legal_batch/test_publish_bundle.py::test_run_publish_writes_consumer_readiness_manifest`.
- Temporal limitations: `src/polisyos/data_forge/domains/legal/batch/temporal_resolver.py`, `tests/unit/data_forge/legal_batch/test_temporal_resolver.py::test_resolve_document_temporal_marks_status_only_historical_as_partial`, `tests/unit/data_forge/legal_batch/test_temporal_resolver.py::test_resolve_fact_temporal_prefers_statement_override_over_doc_envelope`, and `tests/unit/data_forge/legal_batch/test_temporal_resolver.py::test_resolve_fact_temporal_does_not_inherit_resolved_historical_start_only_doc_window`.
- Runtime reader boundary: `src/polisyos/data_forge/read_api/legal.py`, `src/polisyos/lex/knowledge/store.py`, and `src/polisyos/lex/normpack/select_sources.py`.
