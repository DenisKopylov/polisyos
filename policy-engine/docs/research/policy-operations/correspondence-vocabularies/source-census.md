# Reproducing the vocabulary mentions

## CV-C01 — predicate and two source epochs

The predicate is **Git-tracked files below repository-root `policy-engine/src/`,
suffix exactly `.py`, including `__init__.py`, with no content exclusions**.
Matching means a literal substring anywhere in strictly decoded UTF-8 text,
including comments and docstrings; the unit is **files containing the substring**,
not occurrences, definitions, owners, or demand. Case-sensitive and `str.casefold`
modes are both reported. Package is the first component after `src/polisyos/`.
Untracked files, other suffixes and other roots are excluded. Unreadable selected
members are ambiguous and the command returns `2 / UNRUN`, never a complete zero.

At survey source `fc823071a7b6f2c9a573172aec3499ad6d138c0f` the denominator is
**2,653 `.py` files**. At this lane's base
`28b8a1a420e746b54fbd0b87f73fad1fc4821ba5` it is **2,663 `.py` files** under that
same predicate. `git ls-files --cached --full-name -z` and a separate
`git ls-tree -r --name-only -z HEAD` enumeration agree on the complete selected
path set at both checkouts. Every selected file was successfully read and hashed.
Neither checkout had a source delta from its HEAD at measurement.

The historical read used the existing `codex/debt-nature-survey` checkout at
`ae4befeddf9645cccef2dec0d1254a18e2242e9b`; a separate
`git diff --exit-code fc823071a7b6f2c9a573172aec3499ad6d138c0f
ae4befeddf9645cccef2dec0d1254a18e2242e9b -- policy-engine/src` returned 0. This
establishes the source equivalence, not an assumption that the survey branch
itself equals its source base.

## CV-C02 — case sensitivity and the complete distribution

Both source epochs above return this same table; all counts retain CV-C01's
root/suffix/inclusion/substring predicate. The matched path sets were also checked
independently using case-insensitive Git grep against each pinned source commit,
with exact path-set equality, not merely equal totals.

| Literal substring | Case-sensitive matching files | Case-insensitive matching files |
| --- | ---: | ---: |
| `estimand` | 169 | 176 |
| `normative` | 132 | 141 |
| `write_operation` | 0 | 0 |
| `assurance_level` | 0 | 0 |

The last two zeros mean only that those **spellings** are absent in the admitted
`.py` text. They do not mean there is no operation contract, assurance consumer,
planned demand, or semantic owner. The existing `engagement.level` discriminator
is a concrete counterexample; see [R2-SEM-03](int-r2-semantics.md).

| Package | `estimand`, sensitive | `estimand`, insensitive | `normative`, sensitive | `normative`, insensitive |
| --- | ---: | ---: | ---: | ---: |
| core | 0 | 0 | 6 | 6 |
| data_forge | 2 | 2 | 34 | 36 |
| data_requirement | 0 | 0 | 1 | 1 |
| evidence | 0 | 0 | 2 | 2 |
| fabric | 2 | 2 | 2 | 2 |
| foundry | 101 | 105 | 2 | 2 |
| ir | 33 | 36 | 5 | 6 |
| legal_requirement | 0 | 0 | 1 | 1 |
| lex | 0 | 0 | 9 | 9 |
| pdc | 0 | 0 | 2 | 2 |
| policy_grammar | 0 | 0 | 0 | 1 |
| runtime | 19 | 19 | 37 | 38 |
| scientist | 12 | 12 | 31 | 35 |
| **sum over complete selected source** | **169** | **176** | **132** | **141** |

Thus case-insensitive `estimand` matches span six packages, with Foundry
`105 / 176 ≈ 59.7%`; case-insensitive `normative` spans thirteen packages with
Runtime 38, DataForge 36 and Scientist 35. These are file distributions within
CV-C01, not owner distributions. Reading actual definitions establishes the
Foundry estimand owner and the distinct normative owners; concentration alone
does not establish exact semantics, and spread cannot disprove ownership.

The capitalised-only counterexample was stated before measuring and the
insensitive mode can return it. Its normative difference includes
`src/polisyos/ir/analytics/normative_arbitration.py`, whose
`NormativeModelCompleteness` and `NormativeAuditStatus` refute the “only an
adjective” interpretation. Neither type is therefore presumed to implement the
INT-R2 consent/waiver ceiling. That comparison is [R2](int-r2-semantics.md).

## CV-C03 — denominator growth, not a new predicate

The complete selected-set difference is ten additions, no deletions:
`2,653 + 10 = 2,663`. The newly selected paths, relative to `policy-engine/src/`,
are `polisyos/common/markdown.py`; Runtime quality's `epoch_certificate_issuance.py`,
`epoch_deployment.py`, `epoch_evidence_exchange.py`, `epoch_transition_inputs.py`,
`epoch_transition_origin.py`, `epoch_transition_verification.py`; Scientist
governance continuous's `governed_public_record.py`,
`governed_public_record_contracts.py`; and Scientist validation's
`epoch_certificate_issuance.py`. This enumeration comes from the complete
selected-set difference, independently reconciled with the pinned Git delta.
The raw receipts retain path identities and content hashes; no duplicate source
dump is committed.

## Replay and boundaries

From the repository root, run:

```sh
python3 policy-engine/docs/research/policy-operations/correspondence-vocabularies/source_census.py
```

Use `--repo /absolute/path/to/checkout` for the historical checkout. The output
reports its actual HEAD, read paths/hashes, Git operations and selector
reconciliation. A changed working tree is printed explicitly; HEAD is not
silently asserted to describe changed bytes. Reproducing historical content
requires that source state, not today's checkout with yesterday's denominator.

Independent matching-set commands (replace `<source-commit>` with either pinned
source commit above; preserve the quoted pathspec):

```sh
git grep -l -i -z -e estimand <source-commit> -- ':(glob)policy-engine/src/**/*.py'
git grep -l -i -z -e normative <source-commit> -- ':(glob)policy-engine/src/**/*.py'
```

This is an **internal research instrument** directly invoked by the researcher;
it has no production caller, no gate consumer and no ownership/admissibility
verdict. It uses explicit byte-read receipts because it is standalone and must
also replay in a minimal fixture Git repository; it does not add a second runtime
measurement service. The author contract is
[`author-measurement-instruments.md`](../../../how-to/author-measurement-instruments.md).

`unresolved_by_construction`: nonliteral synonyms, semantic equivalence, unselected
authority documents, other roots/suffixes, untracked evidence, other revisions,
and sequential rather than atomic worktree observation. In particular this
census is unable to decide a universal no-owner or no-demand proposition.

The targeted command in `tests/repo_quality/tools/test_vocabulary_source_census.py`
exercises capitalised presence, outside-only evidence, a missing selected member,
undecodable selected bytes, changed content and an untracked Python member.
Removing case-insensitive matching while retaining all receipt markers fails
the capitalisation and changed-content assertions. Removing read-completeness
from the completion predicate fails the missing/undecodable-member assertions.
Complete output and mutant sources are retained in the lane's ignored `raw/`
directory and cited by SHA-256 in the [evidence record](../../../superpowers/journals/correspondence/vocabularies/evidence.md).

Named transcription destination: `team-architecture`, the existing
`int-r2-ceiling-vocabulary-owners` and
`estimand-binding-strength-terms-unregistered` rows. The latter still carries
169 and “one genuinely owed”; this lane records the correction here under its
no-register-edit constraint. `singleton-literal-census-predicate-unstated` is a
separate census and is neither remeasured nor closed by CV-C01–03.
