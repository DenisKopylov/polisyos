# Stage 1 deciding evidence

Input base `28b8a1a420e746b54fbd0b87f73fad1fc4821ba5`. Raw outputs are gitignored
beside this record. The admission command was repeated with complete output capture
immediately before `git worktree add -b codex/promotion-conjunction ... 28b8a1a42`.
It returned admitted/0; the readback returned `## codex/promotion-conjunction` and
the exact base. The earlier uncaptured/truncated admission was not used as a reservation.

- `uv run polisyos-tools workspace doctor --worktree-admission create --branch codex/promotion-conjunction --path /Users/deniskopylov/polisyos/.worktrees/promotion-conjunction` — process exit `0`; `raw/admission.json` SHA-256 `5292859cd73549fab6689bb7d5f711ace406d3f254346543f338cfe2d7a3681e`.

- `python3 docs/superpowers/journals/promotion-conjunction/census.py` — process exit `0`; `raw/census.json` SHA-256 `34d6881dfc5eb588f977af68a2c6a6c5bd9ab9db334327875715af85ca56ef6b`.

- `.venv/bin/python -m pytest tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py::test_separate_signed_authorization_produces_persists_resolves_and_projects tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py::test_invalid_authority_keeps_frontier_and_persists_typed_request tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers tests/unit/runtime/quality/test_promotion_sequence.py::test_scope_insufficient_obligation_does_not_vacuously_pass tests/unit/runtime/quality/test_promotion_sequence.py::test_scope_insufficient_cannot_mint_production_authority -q` — process exit `1`; `raw/stage1-targeted.txt` SHA-256 `69afcfd9b03022ca50c7326fd1c698847d79bcd706d6ee58ccd2e31b642bf401`.

The combined targeted run failed in the two scope tests' obsolete CG2 fixture at
`grounding_admission_strangle_drift`, before the scope guards. This is not scope
verification. No source/test had been edited. Exact slice-base replay and input
intersection proof are still required before assigning the failure as inherited.

Environment: offline frozen sync attempted and returned 1 because jaxlib 0.8.2
was absent from the cache. Local Python 3.14.3 venv uses local `src` first and a
read-only dependency path to integration's Python 3.14 site-packages. Import readback
confirmed `polisyos.__file__` is inside this lane. No dependency artifact was changed
or committed. This environment limitation is tooling, routed to this record.
