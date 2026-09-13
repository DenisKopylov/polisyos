# Correspondence vocabularies evidence

Stage 1 checkpoint. Commands ran in this lane’s `policy-engine/` unless noted.
Raw evidence is local and gitignored; absence at another checkout is a non-receipt, not a passing result.

## Commands and process results

| Command / operation | Own exit | Result |
| --- | --- | --- |
| Worktree doctor create and resume preflights from integration checkout, exact requested branch/path | 0 / 0 | Admitted before lane creation; complete JSON and stderr retained. |
| `corepack pnpm install --frozen-lockfile` | 0 | Workspace dependencies linked, 44.7 seconds. |
| `python3 docs/research/policy-operations/correspondence-vocabularies/source_census.py --repo ..` | 0 | Complete current tracked Python census; exact invocation arguments are recorded in JSON. |
| Historical census with same script and debt-nature-survey worktree repo | 0 | Complete historical tracked Python census; source equality to historical census base separately checked. |
| Independent case-insensitive `git grep -l -i -z` at both pinned commits, each estimand/normative literal | 0 each | Complete path sets reconcile to Python reader; predicate and commands in source-census report. |
| `python3 -m unittest discover -s tests/repo_quality/tools -p test_vocabulary_source_census.py -v` | 0 | 6 behavioral tests, 7.532 seconds, final output. Initial invalid-UTF8 Git-diff failure retained and fixed. |
| Same suite with casefold removed, then with unreadable-member completion condition removed | 1 each | Each removal leaves markers but causes 2 assertion failures. |
| Shared root `.venv/bin/python -m ruff check` on research script and mirrored test | 0 | Bounded lint; complete output retained. |
| `env PYTHONPATH=src:tests:. /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/fabric/test_non_data_acquisition.py tests/unit/fabric/test_ceiling_relations.py tests/unit/foundry/validation/test_legal_correspondence.py tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py -o addopts= -q` | 0 | 140 passed, 6 warnings, 449.90 seconds. Source resolves from this lane; environment is shared, not a provisioned lane venv. |
| Independent integrated R1/R2 reviews | review findings | DS15 negative projection is independent; commissioned consent scope retained; stale lane destinations corrected. |

No production-source changes precede the Stage 1 commit. Stage 2 results and final standalone ledger/guardrail checks will be appended after execution; no pass is implied here.

## Raw receipt references

This table covers existing immediate raw files except mutant `.py` implementations, plus the explicitly named integrated reviews and row-denominator receipt. Per-scenario probe directories are retained beside their deciding suite outputs; no derived data copies are committed.

| Raw path (relative to this journal) | SHA-256 |
| --- | --- |
| `raw/acquisition-commission.json` | `0a95afd58a66c4c4ddf408c2c05771ee8abb403f064730023baf7a00b3cbcb09` |
| `raw/admission-create.json` | `73bf681ae5e419d86f16f3405af258d56dcc6000aa14d13673d0466c1f026a32` |
| `raw/admission-create.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/admission-resume.json` | `67ce73a6dc41656ae5a699515802a3a7212179c1b1598396f1f4dab7fb6c2c74` |
| `raw/admission-resume.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/case-removal-tests.txt` | `492ffed11502b4cdd843a6dd7badf436dfecc5c68d816ad339ef8e1f51e5a845` |
| `raw/census-reconciliation.json` | `1050ffc03931ea9fc5b914981b5005f87a4ff0acb15b85beccef73035b3dc091` |
| `raw/census-tests-final.txt` | `d76484ad4211f4bb895929797f4796b471717efd5d11cdb034550c31ad29f7ba` |
| `raw/census-tests-fixed.txt` | `d7af2d84dc6b921f03560c342047f63a23d0a7d80d8a073dd209a51fc78d367a` |
| `raw/census-tests.txt` | `090b1bd9088dc5c15812b6fd6761865df30337568cfebf104d4c213e2b999a92` |
| `raw/existing-owner-tests.txt` | `8526b30570dbc7da91229fce3bc0fa5f3818afb1239bf2706c042a4e25941f3e` |
| `raw/git-estimand-current.bin` | `10896796fb2b07df37d56b92f87677a29bd3f01bc241d67c4834549161838007` |
| `raw/git-estimand-historical.bin` | `0f0cb13db9a2f2e496a2d3aa224f2e817ef334388ad1da3016cd68ad3ca4ddcf` |
| `raw/git-normative-current.bin` | `847862ddb707a59157d9e24fd2caf6d2be027ac1a535d361729a0794b48307ad` |
| `raw/git-normative-historical.bin` | `b25ed127e0b7addfe6f0167e11b85fc54c47dec8664bd924dcdc01e81a6ee4e2` |
| `raw/historical-source-census.json` | `b194ae95a9c2999a264cdffb9118174207ce474727b99ce52a24f2a35ab47b9c` |
| `raw/historical-source-census.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/historical-source-delta.txt` | `8106f19a36c0e828b169f1d3c6402123878a0c0497d54ec35bea363a2cb194a3` |
| `raw/local-links-before-evidence.json` | `ef637b9175771a8fac1e4062a624e44d42ad8d1c85d9bcf844d6575273f6b0e1` |
| `raw/pnpm-install.txt` | `53d579ccc49052df960c089fb95cca392b89249e44b4fb321d27fa5844f9b3f7` |
| `raw/r1/integrated-review.md` | `d95c5452f683f3ceb96b3643b7182e5173dcec001d8cefc01478101ec0f1d3a6` |
| `raw/r2/integrated-review.md` | `205d089158823c4802e8d8cb046a7bbe5c7db8e88e0c8f34672ad3e2e60ac9cf` |
| `raw/r3-r4/row-denominator.json` | `518bb3a8bf5b512048bbef4c6c1e9458bffd6559599713cee5a4e3dc74b633a9` |
| `raw/ruff.txt` | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `raw/source-census.json` | `4df0ca42247becbb557b4c725be09e2759cf895dc0f75f5d7cf425b05978f4f5` |
| `raw/source-census.stderr` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw/unreadable-removal-tests.txt` | `ad9c9f11a4ae3041da33e4c94f30ede0f0b5ac9321f999583e9133919924ff21` |
