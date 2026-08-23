# GY-N12 Clusters 1–4 Implementation Plan

> **For Codex:** use `superpowers:executing-plans` to execute this plan task by
> task, `superpowers:test-driven-development` before every production change,
> and `superpowers:verification-before-completion` before each cluster handoff.

**Status:** Cycle 6 planning deliverable. Execution requires the user's explicit
approval. Until then the research toolchain gate remains closed: do not create a
runtime, bootstrap, run tests or validators, write generated/governed artifacts,
or replay deployment-bound outputs.

**Goal:** deliver the fixed full-prefix chronology-proof protocol and the epoch
family through Clusters 1–4, including owner-preserving GY-DEF22 execution,
honest no-holder acceptance machinery, epoch derivation, Decision Validity
staleness, Claim Ledger lifecycle consumption and public fail-closed behavior.

**Architecture:** one policy-free proof protocol serves opaque family-native
records. It owns exact framing, commitments, consistency and verification only.
Family owners retain denominator, acceptance, native identity, currentness and
authority. The epoch adapter derives semantic-version coordinates from all
owner-admitted L5 regimes and L3 amendments. Decision Validity owns certificate
currentness; Claim Ledger owns claim history. No universal envelope, shared log,
parent scope, chronology authority head or holder appointment is introduced.

**Proof profile:** `full_prefix_canon_json_0_2_0_sha256_256_v1`; streaming
SHA-256, full native prefix, no Merkle tree and no selective proof. The frozen
caps and revisit conditions in the design are implementation requirements, not
tunables: 2,500,000 members, 4 GiB complete bundle and 1,024-byte canonical
member frame fail with `proof_profile_capacity_exceeded`; profile review occurs
only on a cap crossing, an admitted consumer unable to hold full history, or an
appointed consumer SLO that measured full-prefix replay cannot meet. There is
no algorithm fallback.

**Provenance:** Cycle 6 was prepared on merge commit
`7445bd48cc58bca24f8531660303176f651f632e`, whose parents are accepted Cycle 5
commit `787a41e26beaede4efbfa23ac94f14df355341ff` and the authorized `main` tip
`0dda8be515c588b326bb5253ca40eb825f0d46f2`. The historical slice base remains
`1360b1cb592be6a19c162a3ec3ddb5a2e87986c7`. The implementation base is **not**
the merge commit: after the Cycle-6 documents are committed and the user
approves this plan, the executor captures the then-current clean attached HEAD
as `GY_N12_IMPLEMENTATION_START`. Every source delta, P41 replay, deployment
intersection and transition declaration binds that immutable hash; none binds
moving `main`.

---

## Execution protocol

Run every command from the exact worktree and keep the branch attached:

```zsh
cd /Users/deniskopylov/polisyos/.worktrees/gy-n12-epoch-chronology/policy-engine
test "$(git rev-parse --show-toplevel)" = \
  /Users/deniskopylov/polisyos/.worktrees/gy-n12-epoch-chronology
test "$(git symbolic-ref --short HEAD)" = codex/gy-n12-epoch-chronology
```

After approval, reconstruct only the accepted N8/GY-DI1 package surface: base
dependencies plus `analytics`, `bayesian`, `ml`, `optimization-advanced` and
`solvers`; add `lint`, `test` and `runtime` only as implementation tooling.
`research` is forbidden because it admits `torch==2.10.0`. The contributor
baseline is uv 0.9.21, Python 3.14 and Node 22. Run this exact admission
sequence once, but first read
`docs/superpowers/journals/2026-08-20-gy-di1-deployment-identity.md` completely;
its admitted-profile reconstruction and E11 custody relation are inputs to the
commands below, not facts to rediscover after bootstrap.
`GY_N12_BOOTSTRAP_PY` must be an already-authorized local 3.14
interpreter; uv may not download another one:

The operator-supplied hashes in this first tooling bootstrap are local
preconditions only; they are never serialized into or cited by the Foundry/N8
product predicate. The post-freeze receipt producer accepts executable paths
but resolves their expected platform-qualified identities exclusively from the
Foundry authority registry and independently hashes the bytes.

```zsh
GY_N12_ROOT=/Users/deniskopylov/polisyos/.worktrees/gy-n12-epoch-chronology
GY_N12_PRODUCT="$GY_N12_ROOT/policy-engine"
cd "$GY_N12_PRODUCT"
test "$(git rev-parse --show-toplevel)" = "$GY_N12_ROOT"
test "$(git symbolic-ref --short HEAD)" = codex/gy-n12-epoch-chronology
test -z "$(git status --porcelain)"
test "$(git rev-parse --show-prefix)" = policy-engine/
GY_N12_IMPLEMENTATION_START="$(git rev-parse HEAD)"
test -n "$GY_N12_IMPLEMENTATION_START"
: "${GY_N12_UV_BIN:?operator must supply the authorized uv executable}"
: "${GY_N12_UV_BIN_SHA256:?operator must supply its sha256 digest}"
: "${GY_N12_UV_CACHE_DIR:?operator must supply the explicit offline cache root}"
test "${GY_N12_UV_BIN#/}" != "$GY_N12_UV_BIN"
test -x "$GY_N12_UV_BIN"
test "$("$GY_N12_UV_BIN" --version | awk '{print $2}')" = 0.9.21
test "sha256:$(shasum -a 256 "$GY_N12_UV_BIN" | awk '{print $1}')" = \
  "$GY_N12_UV_BIN_SHA256"
test "${GY_N12_UV_CACHE_DIR#/}" != "$GY_N12_UV_CACHE_DIR"
test -d "$GY_N12_UV_CACHE_DIR"
test -r "$GY_N12_UV_CACHE_DIR"
: "${GY_N12_BOOTSTRAP_PY:?operator must supply the authorized Python 3.14 interpreter}"
: "${GY_N12_BOOTSTRAP_PY_SHA256:?operator must supply its sha256 digest}"
test "${GY_N12_BOOTSTRAP_PY#/}" != "$GY_N12_BOOTSTRAP_PY"
test -x "$GY_N12_BOOTSTRAP_PY"
test "sha256:$(shasum -a 256 "$GY_N12_BOOTSTRAP_PY" | awk '{print $1}')" = \
  "$GY_N12_BOOTSTRAP_PY_SHA256"
test "$($GY_N12_BOOTSTRAP_PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" = 3.14
UV_PYTHON="$GY_N12_BOOTSTRAP_PY" UV_PYTHON_DOWNLOADS=never \
UV_CACHE_DIR="$GY_N12_UV_CACHE_DIR" "$GY_N12_UV_BIN" sync \
  --frozen --offline \
  --extra lint --extra test --extra runtime \
  --extra analytics --extra bayesian --extra ml \
  --extra optimization-advanced --extra solvers
GY_N12_PY="$GY_N12_PRODUCT/.venv/bin/python"
GY_N12_SITE="$GY_N12_PRODUCT/.venv/lib/python3.14/site-packages"
test -x "$GY_N12_PY"
test -d "$GY_N12_SITE"
: "${GY_N12_AUTHORIZED_DATA_ROOT:?operator must supply the appointed read-only data root}"
: "${GY_N12_DATA_APPOINTMENT_RECEIPT:?operator must supply its custody receipt}"
test "${GY_N12_AUTHORIZED_DATA_ROOT#/}" != "$GY_N12_AUTHORIZED_DATA_ROOT"
test -d "$GY_N12_AUTHORIZED_DATA_ROOT"
test "${GY_N12_DATA_APPOINTMENT_RECEIPT#/}" != \
  "$GY_N12_DATA_APPOINTMENT_RECEIPT"
test -f "$GY_N12_DATA_APPOINTMENT_RECEIPT"
test -L "$GY_N12_PRODUCT/production_data"
GY_N12_DATA_REAL="$(cd "$GY_N12_PRODUCT/production_data" && pwd -P)"
GY_N12_APPOINTED_DATA_REAL="$(cd "$GY_N12_AUTHORIZED_DATA_ROOT" && pwd -P)"
test "$GY_N12_DATA_REAL" = "$GY_N12_APPOINTED_DATA_REAL"
test -f "$GY_N12_PRODUCT/production_data/manifest.json" || \
  { print -u2 production_data_manifest_missing; exit 1; }
test ! -w "$GY_N12_DATA_REAL"
GY_N12_RUN=(
  /usr/bin/env -i
  LANG=C.UTF-8 LC_ALL=C.UTF-8
  JAX_PLATFORMS=cpu PYTHONHASHSEED=0 PYTHONNOUSERSITE=1
  PYTHONDONTWRITEBYTECODE=1
  PATH="$GY_N12_PRODUCT/.venv/bin:/usr/bin:/bin"
  PYTHONPATH="$GY_N12_PRODUCT/src:$GY_N12_PRODUCT:$GY_N12_SITE"
  "$GY_N12_PY" -S
)
"${GY_N12_RUN[@]}" - "$GY_N12_ROOT" <<'PY'
import importlib.metadata as metadata
from pathlib import Path
import sys

import polisyos

root = Path(sys.argv[1]).resolve()
assert Path(polisyos.__file__).resolve().is_relative_to(root)
try:
    metadata.distribution("torch")
except metadata.PackageNotFoundError:
    pass
else:
    raise SystemExit("forbidden_distribution_present:torch")
PY
test "$(node --version | sed 's/^v//' | cut -d. -f1)" = 22
corepack pnpm install --frozen-lockfile --ignore-scripts
```

The executor may create the worktree-local `production_data` link only from an
explicitly authorized read-only source; this plan does not nominate the parent
checkout or a sibling as that source. The operator supplies both the appointed
root and its content-bound custody receipt before admission; the worktree link
must resolve exactly to that root. The later Foundry resolver verifies the
receipt, root identity, manifest bytes and source-freeze binding and rejects a
writable, moved, sibling/unappointed or changed target. These shell checks are
toolchain preconditions, not product evidence. Current tracked source supplies
no such manifest. No authorized source, unreadable manifest, absent/mismatched
uv binary, uv cache miss, wrong Python/uv/Node, installed
torch or identity disagreement is a tooling/typed-
input non-receipt. It is never repaired with `research`, a writable data copy, a
backend ignore, a machine pin or a package allowlist.

For every task below:

1. write the named failing test and run only that test to record red;
2. implement the smallest owner-respecting behavior;
3. run the named green command plus the negative/corruption case;
4. run changed-path Ruff and architecture guards;
5. review the exact delta under the P40 bucket rule; and
6. commit only after attached-branch/status readback.

Status/record review packets are derived from a complete Markdown-owner walk,
not hand-selected narrative ranges or anchor-adjacent lines. The normative
profile is `policyos.gy-n12.c1-status-markdown-owner.v2`, with a 28,000-byte
packet cap and these exact repository-root-relative paths, in this order:

1. `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md`;
2. `policy-engine/docs/superpowers/journals/2026-08-20-gy-n12-cycle-6-implementation-planning.md`;
3. `policy-engine/docs/superpowers/plans/2026-08-20-gy-n12-epoch-chronology-implementation.md`; and
4. `policy-engine/docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-design.md`.

The derivation has no caller-supplied path, root or anchor argument. Its private
snapshot reducer requires exactly that key tuple: missing, duplicate,
reordered, product-relative or extra same-type paths fail before selection.
Repository-root and product-root invocation both derive the Git top level and
serialize POSIX UTF-8 paths beginning `policy-engine/`.

The subject anchors remain exactly `GY-DEF22`, `C1-CURRENT`,
`owner_enforced_runtime_subtree_cutoff`,
`owner-enforced runtime-subtree cutoff`, `runtime-cutoff authority`,
`runtime cutoff`, `production runtime candidate`,
`candidate_runtime_evidence`, `not_requested`, `test/reference`, and
`owner_resolved_resolution_receipt_store`. Adding a literal is not a closure
move. Instead, enumerate every case-sensitive occurrence, including repeated
or overlapping occurrences, and expand it to exactly one complete Markdown
owner using this precedence:

1. enclosing zero-indent outer list item;
2. enclosing fenced block;
3. one physical outer-pipe GFM table row in a delimiter-established table;
4. the complete ATX heading section, but only when the hit is on its heading;
5. the maximal paragraph (frontmatter is one paragraph owner).

An outer list item ends before its next zero-indent sibling, an equal-or-outer
heading, or a post-blank non-indented block; nested indented content and blank
lines stay inside it. A heading section ends before the next equal-or-higher
heading. A fence closes only on the same character at least as long as its
opener. Setext headings, structural tabs, lazy ambiguous continuations,
unterminated fences, directly hit ambiguous indented code and crossing
non-nested owners fail `status_manifest_markdown_ambiguous`. Exact bytes split
only after LF; LF, CRLF and an unterminated final line are preserved, while a
bare CR fails.

Owner identity is `(path, kind, start_line, end_line_exclusive)`. Owners
deduplicate by that identity; every occurrence maps to exactly one owner and
every owner has at least one occurrence. Nested selected owners may overlap,
but source bytes emit once. Each selected line records its complete sorted
owner-ID set. Lines sort by UTF-8 path bytes then one-based line number.

The manifest serializer is exhaustive and versioned. It emits LF-terminated
UTF-8 TSV with no escaping; tabs/newlines in an input field fail before
serialization. The five row grammars are exact:

- `M`: profile, cap, packet base `1`, compact exact-path JSON, compact
  exact-anchor JSON;
- `C`: owner ID, path, kind, start line, exclusive end line, container
  SHA-256—there is no auxiliary field;
- `O`: occurrence ID, owner ID, path, line, start byte, end byte and one-based
  anchor-tuple ordinal;
- `S`: packet, sequence-within-packet, path, line, segment start/end, ending
  token, sorted owner-ID JSON, whole-line SHA-256 and segment SHA-256; and
- `R`: packet, size and packet SHA-256.

Kinds are exactly `outer_list_item`, `fence`, `table_row`, `heading_section`
and `paragraph`, in that ordinal order. Owner IDs are one-based after sorting
`(path UTF-8 bytes, start line, exclusive end line, kind ordinal)`.
Occurrence IDs are one-based after sorting `(path bytes, line, start byte, end
byte, anchor ordinal, owner ID)`. Rows serialize strictly as one `M`, all `C`
by owner ID, all `O` by occurrence ID, all `S` by packet and sequence, then all
`R` by packet. `container_sha256` hashes exact concatenated source-line bytes
in the owner span, including tracked endings. Whole-line and segment hashes
cover their exact indicated bytes. Ending tokens are exactly `LF`, `CRLF` and
`NONE`. Compact JSON uses `ensure_ascii=False`, sorted keys and separators
`(",", ":")`; integer arrays therefore contain no spaces and digests are
lowercase. Packet bytes are `S` segments in manifest order with no separator.
For each packet, `sequence-within-packet` is exactly one plus the number of
earlier `S` segments assigned to that packet: it starts at one, is contiguous
through `N`, and resets to one at every new packet. It is never global or
caller-selected.
Greedy packetization fills every non-final packet to exactly 28,000 bytes and
splits only at remaining capacity; the final packet is nonempty and at most
28,000. Manifest-transfer packets are independently greedy-split to the same
ceiling. Their external receipt is not part of the manifest: one
`T\tprofile\tmanifest_size\tmanifest_sha256\tpacket_count` row followed by one
`P\tindex\tsize\tsha256` row per contiguous one-based transfer packet. That
exact receipt bytestring is reported by size and SHA-256, never recursively
embedded.

The checker reconciles occurrence-to-owner, owner-to-occurrence,
selected-line-to-covering-owner, exact `[0, len(line_bytes))` segment coverage,
contiguous one-based packet indices, exact `1..N` segment sequences independently
for every packet, and reconstructed packet bytes. These
mutations are mandatory method falsifiers: the plan's `Standing: open` changed
to `closed`; refusal persistence `not_established` changed to `established`;
receipt-store `absent/unallocated` changed to `implemented`; a missing path;
an extra same-type path or anchor; product-relative serialization; zero-based
indices; LF removal or LF/CRLF change; early packet close; a non-anchor byte
change in each of the five owner kinds; fence-looking structure inside a fence;
collapsed repeated occurrences; and global, duplicate, skipped or non-reset
segment sequences with all selected bytes fixed. A terminal review receipt is a separate
blank-delimited paragraph containing no subject anchor; if it enters the
selected union or changes the receipt, fail `self_referential_receipt` rather
than seeking a hash fixed point.

The stdlib serializer has a frozen row-level golden independent of the
four-path derivation. With one paragraph owner over exact line `b"A\n"`, path
`policy-engine/a.md` and anchor `A`, line/container/segment hash is
`06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0`.
The literal five-row manifest is 457 bytes with SHA-256
`bcf8fc1885643cbe8958f84ae304e56d9edfed9290d4e7ae09d203a5f13e6ea6`;
its literal two-row transfer receipt is 190 bytes with SHA-256
`728d26ab22b6e07601ba90d91256fd9fcf0a17dbb1019e00d048da9bfd13b02e`.
The canonical escaped rendering follows: each visible two-character `\t` is
replaced by exactly one ASCII TAB byte and each displayed row has exactly one
trailing LF byte; no other unescaping occurs.

```text
M\tpolicyos.gy-n12.c1-status-markdown-owner.v2\t28000\t1\t["policy-engine/a.md"]\t["A"]
C\t1\tpolicy-engine/a.md\tparagraph\t1\t2\t06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0
O\t1\t1\tpolicy-engine/a.md\t1\t0\t1\t1
S\t1\t1\tpolicy-engine/a.md\t1\t0\t2\tLF\t[1]\t06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0\t06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0
R\t1\t2\t06f961b802bc46ee168555f066d28f4f0e9afdf3f88174c1ee6f9de004fc30a0
```

```text
T\tpolicyos.gy-n12.c1-status-markdown-owner.v2\t457\tbcf8fc1885643cbe8958f84ae304e56d9edfed9290d4e7ae09d203a5f13e6ea6\t1
P\t1\t457\tbcf8fc1885643cbe8958f84ae304e56d9edfed9290d4e7ae09d203a5f13e6ea6
```

The fixture asserts every literal row byte, not only the hashes. The earlier
kind-metadata and `{}` auxiliary variants both fail because `C` has exactly
seven fields.

```python
def derive_status_manifest() -> Receipt:
    repo = resolve_git_toplevel()
    require_invocation_coordinate(Path.cwd(), {repo, repo / "policy-engine"})
    snapshot = read_exact_constant_paths(repo, STATUS_PATHS)
    require_exact_keys(snapshot, STATUS_PATHS)
    documents = parse_exact_lines(snapshot)
    structures = classify_markdown_structures(documents)
    occurrences = enumerate_all_occurrences(documents, STATUS_ANCHORS)
    owners = deduplicate(owner_for(item, structures) for item in occurrences)
    reconcile_occurrence_owner_bijections(occurrences, owners)
    selected = union_owner_lines(owners)
    cover = reconcile_exact_owner_cover(selected, owners)
    segments, packets = greedy_packetize(selected, cover, 28_000, base=1)
    reconcile_interval_and_packet_bijections(selected, segments, packets)
    return freeze_receipt(serialize_M_C_O_S_R(...), packets)
```

The `GY_N12_RUN` zsh array is the source-first **tooling** wrapper. Python,
pytest, Ruff, epoch-validator, transition-controller and writer commands expand
it as `"${GY_N12_RUN[@]}"`; architecture guardrails run as
`"${GY_N12_RUN[@]}" -m tools.cli architecture guardrails check`. Terminal
N8/N10a modes use the separately defined, receipt-bound `GY_N12_N8_RUN`; the
two site-package roots may never be combined. Bare
`.venv/bin/python`, `uv run`, console entry points, `eval`, `zsh -c` and a
shell-inherited Python are non-receipts.
The shell-level torch absence check protects this local toolchain only. It is
never cited as the GY-DEF22 closure predicate; the Foundry purpose/profile and
environment receipts below carry that predicate.
Never treat an exit code, field name, hash marker or generated diff as the
property: each gate below includes a keep-the-marker/remove-the-property
mutation.

The frozen 128-property basis remains byte-for-byte unchanged. The following
sets assign review responsibility; they are not scores and must never be
reported as `91/91` or `128/128`. A review finding is on-basis only when it maps
to one of the cluster's exact IDs.

### Cluster-scoped execution contract

GY-N12 executes cluster by cluster, not as one fifteen-task run. Cluster 1,
then Cluster 2, then Cluster 3 and then Cluster 4 each use an attached cluster
branch in this already-provisioned worktree and finish with their own frozen
basis subset, closure receipt and handoff. Changing branch must not replace the
worktree: the admitted `.venv`, appointed read-only `production_data` link and
operator appointment files remain part of the lane environment. Cluster 1 is
Foundry-owned and independent of the chronology chain; its correctness
adjudication remains owed to Foundry.

The task sections are the execution source of truth. Their complete `Add` and
`Modify` lists declare the only candidate paths for a boundary, and their argv
rows are commands to run directly. `Modify` paths must exist at task entry;
their absence is an error. `Add` paths need not exist until their candidate is
present. Immediately before a task suite and again before attachment, derive
the complete Git-visible working-tree delta and require exact set equality with
the sorted union of the task's declared `Add` and `Modify` paths. Equality,
not containment, is the drift guard. A missing declared candidate, an
undeclared path, an Add/Modify overlap or a narrowed command denominator blocks
the boundary.

The six-wave bootstrap harness is retired from the execution path. Its three
files are not task inputs, suite members, boundary paths or authority
artifacts. Their exact historical bytes remain recoverable from the non-branch
preservation refs `refs/gy-n12-preservation/bootstrap-wave6`,
`refs/gy-n12-preservation/bootstrap-wave6-declared-residuals` and
`refs/gy-n12-preservation/bootstrap-wave6-evidence`; no cluster consumes those
refs.

Every declared suite row runs in full through the canonical `GY_N12_RUN`
wrapper (or the separately admitted N8 wrapper where the row explicitly says
so). No selector may omit a named file or node. The journal records the
attached branch, expected parent, declared and observed path sets, direct argv,
process outcome and attachment readback. An ordinary non-zero exit is a
completed failure receipt; a killed or signalled run is a non-receipt.

For every run measured or expected to exceed 60 seconds, declare the ceiling
before launch from a prior comparable measurement, record `/usr/bin/uptime`
immediately before and after, and write wall time, command, environment,
process exit/signal and receipt/non-receipt disposition into the cluster
journal. `GY-DI2` and `GY-DI4` are satisfied by those receipts, not by a
timing machine or catalog-review state machine.

Appendix C supplies the only reusable shell procedures: one plain
task-boundary executor that enforces the prefix, branch, clean-index,
exact-delta and complete-suite predicates, and one atomic attachment function.
The attachment transaction performs symbolic-HEAD verification, expected-old
verification and branch update in one `git update-ref --stdin` transaction.
If the installed Git cannot execute `symref-verify`, the boundary blocks; no
non-atomic fallback exists.

---

## Cluster 1 — execute GY-DEF22 at the Foundry owner boundary

**Delivers:** the Foundry-owned candidate profile/root/distribution
reconstruction and its fail-closed admission machinery; typed absence of the
production-data manifest; the six fixed falsifiers; and generated-artifact
registration. A positive admitted environment additionally needs a competent
runtime-subtree cutoff authority. None is evidenced today, so the implemented
production path returns
`owner_enforced_runtime_subtree_cutoff_not_established` and N8/N10a cannot
promote the candidate. GY-N12 executes the work, but Foundry owns correctness
and its adjudication receipt is owed before GY-DEF22 closure.

**Retains:** N8 as producer, N10a as consumer, and ambient plugin discovery as a
recorded non-decisive posture. No N12-local identity, machine pin, package
allowlist, backend ignore or prose-only environment description is permitted.
Until the Foundry review is accepted, GY-DEF22 remains `producer_missing` with
`artifact_missing + semantic_test_missing + surface_missing` deficits.
An owner-enforced immutable runtime snapshot or mandatory writer-exclusion
lease is `absent/unallocated`. Two equal complete walks are candidate
observations, not an authority-grade common cutoff: a file can change after its
last observation while the second walk continues. Cluster 1 records that exact
residual and cannot issue an admitted environment receipt around it. The exact
preflight refusal is returned in process; its persistence is
`not_established` because an owner-resolved request-bound receipt store is also
`absent/unallocated`. Cluster 1 neither invents that store nor writes a local
substitute.

**Frozen basis subset (9):** `CB-H09`, `CB-I01`, `CB-I02`, `CB-I02A`,
`CB-I03`, `CB-I03A`, `CB-I04`, `CB-I05`, `CB-I06`.

### Task 1.1 — make the discriminating input a Foundry-owned contract

**Add:**

- `architecture/production_quality/method_catalog_dependency_profiles.toml`
- `architecture/production_quality/method_catalog_dependency_authority.toml`
- `architecture/production_quality/method_catalog_dependency_digest_domains.toml`
- `release-fragments/unreleased/2026-08-20-gy-n12-epoch-chronology.toml`
- `src/polisyos/foundry/methods/catalog/dependency_profile.py`
- `src/polisyos/foundry/methods/catalog/dependency_authority.py`
- `src/polisyos/foundry/methods/catalog/dependency_evidence.py`
- `tools/devx/foundry/sync_dependency_profile.py`
- `tests/unit/foundry/methods/test_dependency_profile.py`
- `tests/typecheck/foundry/dependency_authority_covariance.py`

**Modify:**

- `src/polisyos/foundry/methods/catalog/snapshot.py`
- `src/polisyos/foundry/methods/catalog/README.md`
- `tests/unit/foundry/methods/test_catalog_snapshot.py`

The three TOMLs are Foundry-owned data. A profile-registry row names the accepted root
distribution `policy-engine` and the exact extras `analytics`, `bayesian`,
`ml`, `optimization-advanced`, `solvers`; it binds `pyproject.toml`, `uv.lock`,
Python 3.14 and uv 0.9.21 by content/ref, not by machine. A novel row is enough
to define another profile. It contains no package list: the resolver derives
the full locked distribution closure from root + extras + markers. The
authority registry binds purpose-to-profile, platform-qualified Python/uv
artifact source identities and the production-data appointment issuer/trust
profile. A novel platform artifact is a data row, not a path/machine pin.
Its predicate rows carry discriminated rejected/not-established evidence
requirements. `canonical_source_freeze` binds the request commit/tree to a
fresh owner observation of the same module Git root;
`owner_enforced_runtime_subtree_cutoff` is a one-sided not-established
predicate naming the absent capability independently of candidate runtime
evidence. The negative stage map references those predicate IDs and cannot
repeat or override their codes/evidence grammar.

Implement one strict/frozen authority ABI. Every authority DTO below inherits
`FoundryAuthorityModel`; no plain `BaseModel` is admitted at this boundary.
Every decisive digest is tagged with its semantic domain, so two hashes from
different preimages cannot be compared merely because both serialize as
`sha256:...`:

```python
from __future__ import annotations
import ast
import hashlib
import inspect
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass
from functools import wraps
from threading import RLock
from types import MappingProxyType
from typing import ContextManager, ParamSpec, TypeVar, cast, get_args, get_origin, get_type_hints
from weakref import WeakKeyDictionary, finalize

class AuthorityScalarRole(StrEnum):
    DIGEST_WIRE = "digest-wire"
    HEX_BYTES_WIRE = "hex-bytes-wire"
    IDENTITY = "identity"
    VERSION = "version"
    PLATFORM_TAG = "platform-tag"
    ABI_TAG = "abi-tag"
    PYTHON_CONSTRAINT = "python-constraint"
    ENTRYPOINT = "entrypoint"
    ARGUMENT = "argument"
    MARKER_EXPRESSION = "marker-expression"
    BUILD_BACKEND = "build-backend"
    ENVIRONMENT_KEY = "environment-key"
    ENVIRONMENT_VALUE = "environment-value"
    SCHEMA_VERSION = "schema-version"
    EXACT_BYTES = "exact-bytes"
    BYTE_LENGTH = "byte-length"
    REQUEST_PATH = "request-path"
    FILESYSTEM_IDENTITY = "filesystem-identity"

Sha256 = Annotated[
    StrictStr, AuthorityScalarRole.DIGEST_WIRE,
    Field(pattern=r"^sha256:[0-9a-f]{64}$"),
]
# Exact live ArtifactID wire ABI; no bare-hash compatibility form exists.
ArtifactIdWire = Annotated[
    StrictStr, AuthorityScalarRole.DIGEST_WIRE,
    Field(pattern=r"^sha256:[0-9a-f]{64}$"),
]
HexBytes = Annotated[
    StrictStr, AuthorityScalarRole.HEX_BYTES_WIRE,
    Field(pattern=r"^(?:[0-9a-f]{2})*00$"),
]
IdentityText = Annotated[
    StrictStr, AuthorityScalarRole.IDENTITY, Field(min_length=1)
]
VersionText = Annotated[
    StrictStr, AuthorityScalarRole.VERSION, Field(min_length=1)
]
PlatformTagText = Annotated[
    StrictStr, AuthorityScalarRole.PLATFORM_TAG, Field(min_length=1)
]
AbiTagText = Annotated[
    StrictStr, AuthorityScalarRole.ABI_TAG, Field(min_length=1)
]
PythonConstraintText = Annotated[
    StrictStr, AuthorityScalarRole.PYTHON_CONSTRAINT, Field(min_length=1)
]
EntrypointText = Annotated[
    StrictStr, AuthorityScalarRole.ENTRYPOINT, Field(min_length=1)
]
ArgumentText = Annotated[StrictStr, AuthorityScalarRole.ARGUMENT]
MarkerExpressionText = Annotated[
    StrictStr, AuthorityScalarRole.MARKER_EXPRESSION, Field(min_length=1)
]
BuildBackendText = Annotated[
    StrictStr, AuthorityScalarRole.BUILD_BACKEND, Field(min_length=1)
]
EnvironmentKeyText = Annotated[
    StrictStr, AuthorityScalarRole.ENVIRONMENT_KEY, Field(min_length=1)
]
EnvironmentValueText = Annotated[StrictStr, AuthorityScalarRole.ENVIRONMENT_VALUE]
SchemaVersionText = Annotated[
    StrictStr, AuthorityScalarRole.SCHEMA_VERSION, Field(min_length=1)
]
ExactBytes = Annotated[bytes, AuthorityScalarRole.EXACT_BYTES]
ByteLength = Annotated[int, AuthorityScalarRole.BYTE_LENGTH, Field(ge=0)]
FilesystemIdentityNumber = Annotated[
    int, AuthorityScalarRole.FILESYSTEM_IDENTITY, Field(ge=0)
]
NonEmptyIdentity = IdentityText
GitCommitId = Annotated[
    StrictStr, AuthorityScalarRole.IDENTITY, Field(pattern=r"^[0-9a-f]{40}$")
]
GitTreeId = Annotated[
    StrictStr, AuthorityScalarRole.IDENTITY, Field(pattern=r"^[0-9a-f]{40}$")
]

class DigestDomain(StrEnum):
    RAW_BLOB = "raw-blob"
    CANONICAL_SOURCE = "canonical-source-authority"
    PROFILE_REGISTRY = "dependency-profile-registry"
    AUTHORITY_REGISTRY = "dependency-authority-registry"
    DIGEST_REGISTRY = "digest-domain-registry"
    PROFILE_DECLARATION = "dependency-profile-declaration"
    PROFILE_ADMISSION = "profile-admission"
    PYPROJECT = "pyproject-blob"
    UV_LOCK = "uv-lock-blob"
    TOOLCHAIN_SELECTED = "toolchain-selected-artifact"
    TOOLCHAIN_EXECUTABLE = "toolchain-executable-blob"
    TOOLCHAIN_RUNTIME = "toolchain-runtime-installation"
    TOOLCHAIN_RUNTIME_OBSERVED = "toolchain-runtime-observed"
    TOOLCHAIN_RUNTIME_ROOT = "toolchain-runtime-root-resolution"
    TOOLCHAIN_RUNTIME_ROOT_TOKEN = "toolchain-runtime-root-token"
    TOOLCHAIN_RUNTIME_ROOT_PATH = "toolchain-runtime-root-path"
    TOOLCHAIN_RUNTIME_BINDING = "toolchain-runtime-source-binding"
    TOOLCHAIN_RUNTIME_INSTALLATION = "toolchain-runtime-root-installation-receipt"
    TOOLCHAIN_RUNTIME_VERIFICATION = "toolchain-runtime-verification"
    TRUST_MATERIAL = "trust-material"
    TRUST_REVOCATION = "trust-revocation"
    TRUST_RESOLUTION = "trust-resolution-receipt"
    TRUST_POLICY = "production-data-trust-policy"
    VERIFIER_PROVENANCE = "verifier-provenance"
    PRODUCTION_MANIFEST = "production-data-manifest"
    PRODUCTION_APPOINTMENT = "production-data-appointment"
    PRODUCTION_CUSTODY = "production-data-custody"
    ROOT_NONCE = "root-access-nonce"
    ROOT_CHALLENGE = "root-access-challenge"
    ROOT_MOUNT_REQUEST = "root-mount-request"
    ROOT_MOUNT_RESOLUTION = "root-mount-resolution"
    ROOT_ACCESS = "production-data-root-access"
    LOCKED_SOURCE = "locked-source"
    SELECTED_DISTRIBUTION = "selected-distribution-artifact"
    SELECTED_WHEEL = "selected-wheel-blob"
    SELECTED_SOURCE = "selected-source-artifact"
    WHEEL_RECORD = "wheel-record-manifest"
    SOURCE_TREE = "source-tree-manifest"
    BUILD_PROFILE = "build-profile"
    BUILD_ARGV = "build-argv"
    BUILD_ENVIRONMENT = "build-environment"
    BUILD_LINEAGE = "build-lineage-receipt"
    INSTALLED_STABLE = "installed-tree-stable"
    INSTALLED_INSTANCE = "installed-tree-instance"
    INSTALLED_BINDING = "installed-source-binding"
    DISTRIBUTION_SET = "distribution-set"
    CONTENT_SET_STABLE = "required-content-set-stable"
    CONTENT_SET_INSTANCE = "required-content-set-instance"
    DEPENDENCY_CLOSURE = "dependency-closure"
    DERIVED_UV_ARGV = "derived-uv-argv"
    ENVIRONMENT_INSTANCE = "environment-instance"
    ENVIRONMENT_MARKER = "dependency-environment-marker"
    ENVIRONMENT_RECEIPT = "dependency-environment-receipt"
    CAPSULE = "dependency-authority-capsule"
    RESOLUTION_REQUEST = "dependency-resolution-request"
    SIGNED_EVIDENCE = "detached-signature-evidence"
    SIGNED_RECORD_BINDING = "signed-record-binding"
    SIGNED_BINDING_INDEX = "signed-binding-index"
    VERIFIER_APPOINTMENT = "verifier-appointment"

class ExternalAuthorityKind(StrEnum):
    INSTITUTIONAL_ROOT = "institutional-root-object"
    PRODUCTION_DATA_CUSTODIAN = "production-data-custodian"

D_co = TypeVar("D_co", bound=DigestDomain, covariant=True)
E_co = TypeVar("E_co", bound=ExternalAuthorityKind, covariant=True)

class DigestPreimageKind(StrEnum):
    CANONICAL_STATEMENT = "canonical_statement"
    RAW_BLOB = "raw_blob"
    TRACKED_TOML = "tracked_toml"
    ORDERED_ROWS = "ordered_rows"
    RELATION = "relation"

class DigestOrderingRule(StrEnum):
    CANON_JSON_V1 = "canon_json_v1"
    RAW_BYTES_IDENTITY = "raw_bytes_identity"
    TOML_UTF8_CANON_V1 = "toml_utf8_canon_v1"
    LEXICOGRAPHIC_FRAMED_ROWS_V1 = "lexicographic_framed_rows_v1"
    ORDERED_FRAMED_RELATION_V1 = "ordered_framed_relation_v1"

class DigestProducerId(StrEnum):
    CANONICAL_STATEMENT_V1 = "canonical_statement_v1"
    RAW_BLOB_V1 = "raw_blob_v1"
    TRACKED_TOML_V1 = "tracked_toml_v1"
    ORDERED_ROWS_V1 = "ordered_rows_v1"
    RELATION_V1 = "relation_v1"

class DigestVerifierId(StrEnum):
    RECOMPUTE_CANONICAL_STATEMENT_V1 = "recompute_canonical_statement_v1"
    REHASH_RAW_BLOB_V1 = "rehash_raw_blob_v1"
    REPARSE_TRACKED_TOML_V1 = "reparse_tracked_toml_v1"
    RECOMPUTE_ORDERED_ROWS_V1 = "recompute_ordered_rows_v1"
    RECOMPUTE_RELATION_V1 = "recompute_relation_v1"

class DigestAlgebraId(StrEnum):
    CANONICAL_STATEMENT_V1 = "canonical_statement_v1"
    RAW_BLOB_V1 = "raw_blob_v1"
    TRACKED_TOML_V1 = "tracked_toml_v1"
    ORDERED_ROWS_V1 = "ordered_rows_v1"
    RELATION_V1 = "relation_v1"

class DigestPhase(StrEnum):
    STABLE = "stable"
    INSTANCE = "instance"
    RESOLUTION = "resolution"

class LauncherNormalizationProfile(StrEnum):
    POSIX_CONSOLE_SCRIPT_V1 = "posix_console_script_v1"

class LauncherExpectedProducerId(StrEnum):
    DISTLIB_POSIX_CONSOLE_V1 = "distlib_posix_console_v1"

class LauncherObservedVerifierId(StrEnum):
    PARSE_DISTLIB_POSIX_CONSOLE_V1 = "parse_distlib_posix_console_v1"

class TrustRole(StrEnum):
    FOUNDRY_TRUST_ROOT = "foundry_trust_root"
    APPOINTMENT_ISSUER = "appointment_issuer"
    CUSTODY_VERIFIER = "custody_verifier"
    ROOT_ACCESS_ATTESTOR = "root_access_attestor"
    BUILD_VERIFIER = "build_verifier"

class AuthorityPredicateId(StrEnum):
    SOURCE_FREEZE = "canonical_source_freeze"
    RUNTIME_SUBTREE_CUTOFF = "owner_enforced_runtime_subtree_cutoff"
    AUTHORITY_REGISTRY = "authority_registry"
    PURPOSE_PROFILE = "purpose_profile_admission"
    TRUST_SIGNATURE = "trust_signature"
    PRODUCTION_APPOINTMENT = "production_data_appointment"
    ROOT_ACCESS = "fresh_root_access"
    PRODUCTION_MANIFEST = "production_data_manifest"
    SELECTED_ARTIFACT = "selected_distribution_artifact"
    BUILD_LINEAGE = "build_lineage"
    PYTHON_RUNTIME = "python_runtime"
    UV_EXECUTABLE = "uv_executable"
    INSTALLED_SOURCE = "installed_source_binding"
    INSTALLED_CONTENT = "installed_content"
    ENVIRONMENT_RECEIPT = "environment_receipt"

class AuthorityFailureCode(StrEnum):
    SOURCE_FREEZE_MISMATCH = "source_freeze_mismatch"
    SOURCE_NOT_ESTABLISHED = "canonical_foundry_source_not_established"
    RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED = (
        "owner_enforced_runtime_subtree_cutoff_not_established"
    )
    REGISTRY_INVALID = "dependency_authority_registry_invalid"
    REGISTRY_NOT_ESTABLISHED = "dependency_authority_registry_not_established"
    PROFILE_MISMATCH = "dependency_profile_input_mismatch"
    PROFILE_NOT_ADMITTED = "dependency_profile_not_admitted_for_purpose"
    SIGNATURE_INVALID = "dependency_trust_signature_invalid"
    TRUST_NOT_ESTABLISHED = "dependency_trust_material_not_established"
    APPOINTMENT_MISMATCH = "production_data_appointment_mismatch"
    APPOINTMENT_NOT_ESTABLISHED = "production_data_appointment_not_established"
    ROOT_ACCESS_MISMATCH = "production_data_root_access_mismatch"
    ROOT_ACCESS_NOT_ESTABLISHED = "production_data_root_access_not_established"
    MANIFEST_MISMATCH = "production_data_manifest_content_mismatch"
    MANIFEST_MISSING = "production_data_manifest_missing"
    ARTIFACT_MISMATCH = "selected_distribution_artifact_mismatch"
    ARTIFACT_NOT_ESTABLISHED = "selected_distribution_artifact_not_established"
    BUILD_LINEAGE_MISMATCH = "build_lineage_mismatch"
    BUILD_LINEAGE_NOT_ESTABLISHED = "build_lineage_not_established"
    PYTHON_RUNTIME_MISMATCH = "python_runtime_manifest_mismatch"
    PYTHON_RUNTIME_NOT_ESTABLISHED = "python_runtime_not_established"
    UV_MISMATCH = "resolver_executable_mismatch"
    UV_NOT_ESTABLISHED = "resolver_executable_not_established"
    SOURCE_BINDING_MISMATCH = "required_distribution_source_mismatch"
    SOURCE_BINDING_NOT_ESTABLISHED = "installed_source_binding_not_established"
    CONTENT_MISMATCH = "required_distribution_content_mismatch"
    CONTENT_NOT_ESTABLISHED = "installed_content_not_established"
    ENVIRONMENT_MISMATCH = "dependency_environment_receipt_mismatch"
    ENVIRONMENT_NOT_ESTABLISHED = "dependency_environment_receipt_not_established"

class ScalarDomain(StrEnum):
    PROFILE_ID = "profile-id"
    GIT_COMMIT = "git-commit"
    VERSION = "version"
    PLATFORM_TAG = "platform-tag"
    PATH_IDENTITY = "path-identity"

class OwnerCapabilityKind(StrEnum):
    CANONICAL_SOURCE = "canonical-source"
    RUNTIME_INSTALLATION = "runtime-installation"
    VERIFIED_RUNTIME = "verified-runtime"
    TRUST_BOOTSTRAP = "trust-bootstrap"
    RESOLVED_TRUST = "resolved-trust"
    PRODUCTION_APPOINTMENT = "production-appointment"
    PRODUCTION_MOUNT = "production-mount"
    ROOT_ACCESS = "root-access"
    SIGNED_RECORD = "signed-record"
    SIGNED_GRAPH = "signed-graph"
    RESOLVED_COMPONENTS = "resolved-components"

class FoundryAuthorityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

C = TypeVar("C")
P = TypeVar("P")
R = TypeVar("R")
PS = ParamSpec("PS")

class OwnerCapabilityFaultDisposition(StrEnum):
    REJECTED = "rejected"
    NOT_ESTABLISHED = "not_established"

class OwnerCapabilityFaultCode(StrEnum):
    WRONG_TOKEN_TYPE = "wrong_token_type"
    UNMINTED_TOKEN = "unminted_token"
    WRONG_CAPABILITY_FAMILY = "wrong_capability_family"
    RESOURCE_ALREADY_OWNED = "resource_already_owned"
    RESOURCE_IN_USE = "resource_in_use"
    WRONG_RECORD_DOMAIN = "wrong_record_domain"
    INVALID_NESTED_CAPABILITY = "invalid_nested_capability"
    FORKED_PROCESS = "forked_process"
    CHILD_RESOURCE_DISPOSAL_FAILED = "child_resource_disposal_failed"

class OwnerCapabilityFault(RuntimeError):
    def __init__(
        self, *, code: OwnerCapabilityFaultCode,
        disposition: OwnerCapabilityFaultDisposition,
        capability_kind: OwnerCapabilityKind | None,
        payload_path: tuple[str, ...] = (),
        expected_record_domain: DigestDomain | None = None,
        actual_record_domain: DigestDomain | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.disposition = disposition
        self.capability_kind = capability_kind
        self.payload_path = payload_path
        self.expected_record_domain = expected_record_domain
        self.actual_record_domain = actual_record_domain

_OwnerResourceKey = tuple[Literal["posix_open_generation"], int, int]

class _OwnerChildDisposable(Protocol):
    def require_current_process_descriptor(self) -> int: ...
    def owner_resource_lease_key(self) -> _OwnerResourceKey: ...
    def close_owner_resource(self) -> None: ...

@dataclass(frozen=True, slots=True)
class _OwnerResourceClaim:
    lease: object
    resources: tuple[tuple[_OwnerResourceKey, _OwnerChildDisposable], ...]

class _ClaimOwnerResources(Protocol):
    def __call__(
        self, *, capability_kind: OwnerCapabilityKind,
        resources: tuple[_OwnerChildDisposable, ...],
    ) -> _OwnerResourceClaim: ...

class _ReleaseOwnerResources(Protocol):
    def __call__(self, claim: _OwnerResourceClaim, /) -> None: ...

class _RegisterOwnerForkParticipant(Protocol):
    def __call__(self, participant: Callable[[bool], None], /) -> None: ...

class _OwnerLifecycleSection(Protocol):
    def __call__(self) -> ContextManager[None]: ...

@dataclass(frozen=True, slots=True)
class _OwnerPayloadLeafSpec:
    field_path: tuple[str, ...]
    exact_concrete_type: type[object]

class _OwnerNestedCardinality(StrEnum):
    SINGLE = "single"
    MANY = "many"

@dataclass(frozen=True, slots=True)
class _OwnerNestedTokenSpec:
    payload_path: tuple[str, ...]
    cardinality: _OwnerNestedCardinality
    token_path: tuple[str, ...]
    expected_domain_path: tuple[str, ...] | None
    nested_kind: OwnerCapabilityKind

@dataclass(frozen=True, slots=True)
class _OwnerPayloadSpec(Generic[C, P]):
    """Closed token/payload relation; never accepted from a request."""
    kind: OwnerCapabilityKind
    token_type: type[C]
    payload_type: type[P]
    exact_concrete_leaves: tuple[_OwnerPayloadLeafSpec, ...]
    dynamic_record_domain_path: tuple[str, ...] | None
    dynamic_record_ref_domain_path: tuple[str, ...] | None
    child_resource_paths: tuple[tuple[str, ...], ...]
    nested_tokens: tuple[_OwnerNestedTokenSpec, ...]

@dataclass(frozen=True, slots=True)
class _OwnerCapabilityEntry(Generic[C, P]):
    spec: _OwnerPayloadSpec[C, P]
    creator_pid: int
    process_instance: object
    payload: P
    resource_finalizer: finalize

class _OwnerMint(Protocol):
    def __call__(self, spec: _OwnerPayloadSpec[C, P], payload: P, /) -> C: ...

class _OwnerUnwrap(Protocol):
    def __call__(
        self, value: object, spec: _OwnerPayloadSpec[C, P], /, *,
        expected_record_domain: DigestDomain | None = None,
    ) -> ContextManager[P]: ...

class _OwnerRelease(Protocol):
    def __call__(self, value: object, spec: _OwnerPayloadSpec[C, P], /) -> None: ...

class OwnerEntrypointFailureAdapterId(StrEnum):
    AUTHORITY_PREDICATE = "authority_predicate"
    MANIFEST_INPUT = "manifest_input"
    GIT_RELATION = "git_relation"
    METHOD_CATALOG_RESULT = "method_catalog_result"

class OwnerEntrypointTargetKind(StrEnum):
    METHOD = "method"
    MODULE_FUNCTION = "module_function"

@dataclass(frozen=True, slots=True)
class OwnerMethodTarget:
    target_kind: Literal[OwnerEntrypointTargetKind.METHOD]
    concrete_owner_type: type[object]
    protocol_type: type[object]
    method_name: str

@dataclass(frozen=True, slots=True)
class OwnerFunctionTarget:
    target_kind: Literal[OwnerEntrypointTargetKind.MODULE_FUNCTION]
    module_qualname: str
    function_name: str

OwnerEntrypointTarget = OwnerMethodTarget | OwnerFunctionTarget

@dataclass(frozen=True, slots=True)
class OwnerFaultPolicy:
    capability_parameter_name: str
    capability_kind: OwnerCapabilityKind
    predicate_id: AuthorityPredicateId
    rejected_code: AuthorityFailureCode
    not_established_code: AuthorityFailureCode
    evidence_argument_names: tuple[str, ...]
    missing_evidence_domains: tuple[DigestDomain, ...]

@dataclass(frozen=True, slots=True)
class OwnerEntrypointSpec:
    target: OwnerEntrypointTarget
    fault_policies: tuple[OwnerFaultPolicy, ...]
    failure_adapter_id: OwnerEntrypointFailureAdapterId

@dataclass(frozen=True, slots=True)
class OwnerBorrowTerminalEdge:
    evaluation_kind: Literal[
        "call", "attribute", "iteration", "context", "comparison",
        "truth", "hash", "index", "format", "repr", "binary", "unary",
    ]
    callable_qualified_name: str | None
    operand_exact_types: tuple[type[object], ...]
    implicit_method_names: tuple[str, ...]
    disposition: Literal["traversed", "no_user_dispatch"]
    traversed_qualified_functions: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class AstOccurrenceStep:
    field_name: str
    child_index: int | None

@dataclass(frozen=True, slots=True)
class AstOccurrenceId:
    ancestry: tuple[AstOccurrenceStep, ...]

@dataclass(frozen=True, slots=True)
class OwnerBorrowEvaluationNode:
    ast_node_type: type[ast.AST]
    occurrence_id: AstOccurrenceId
    source_span: tuple[int, int, int, int] | None
    disposition: Literal["lowered", "syntactic_container"]
    terminal_edges: tuple[OwnerBorrowTerminalEdge, ...]

@dataclass(frozen=True, slots=True)
class OwnerBorrowReachability:
    entrypoint: OwnerEntrypointTarget
    borrowed_name: str
    reachable_qualified_functions: tuple[str, ...]
    evaluated_nodes: tuple[OwnerBorrowEvaluationNode, ...]

class _OwnerBoundaryBase:
    """Marker for class-level guards installed from the independent census."""
    pass

_OWNER_TOKEN_CLASS_MARKER = object()

def _fieldless_owner_token(cls: type[C]) -> type[C]:
    """Create one fieldless token type; this decorator mints no authority."""
    if cls.__bases__ != (object,) or tuple(getattr(cls, "__annotations__", ())):
        raise TypeError("owner capability token classes must be fieldless")
    token_type = dataclass(
        frozen=True, init=False, slots=True, weakref_slot=True, eq=False
    )(cls)
    setattr(token_type, "__owner_token_class_marker__", _OWNER_TOKEN_CLASS_MARKER)
    return token_type

def _validate_fieldless_owner_token_type(token_type: type[object]) -> None:
    """Check behavior, not only the decorator marker."""
    parameters = getattr(token_type, "__dataclass_params__", None)
    if (
        vars(token_type).get("__owner_token_class_marker__")
        is not _OWNER_TOKEN_CLASS_MARKER
        or not is_dataclass(token_type)
        or token_type.__mro__ != (token_type, object)
        or fields(token_type) != ()
        or parameters is None
        or parameters.init
        or parameters.eq
        or not parameters.frozen
        or tuple(getattr(token_type, "__slots__", ())) != ("__weakref__",)
        or "__dict__" in vars(token_type)
        or token_type.__hash__ is not object.__hash__
        or token_type.__eq__ is not object.__eq__
    ):
        raise TypeError("owner capability token class is not fieldless/frozen/identity-only")
    probe = object.__new__(token_type)
    weak_probe: WeakKeyDictionary[object, bool] = WeakKeyDictionary()
    weak_probe[probe] = True
    try:
        setattr(probe, "state", object())
    except (AttributeError, TypeError):
        pass
    else:
        raise TypeError("owner capability token admits instance state")

def _build_owner_capability_kernel(
    specs: tuple[_OwnerPayloadSpec[object, object], ...],
    *, claim_owner_resources: _ClaimOwnerResources,
    release_owner_resources: _ReleaseOwnerResources,
    register_fork_participant: _RegisterOwnerForkParticipant,
    lifecycle_section: _OwnerLifecycleSection,
) -> tuple[_OwnerMint, _OwnerUnwrap, _OwnerRelease]:
    """Return closures; live payload entries are not module-visible state."""
    def exact_path(value: object, *, allow_empty: bool = False) -> bool:
        return (
            type(value) is tuple
            and (allow_empty or bool(value))
            and all(type(member) is str and member for member in value)
        )

    if type(specs) is not tuple or len(specs) != len(OwnerCapabilityKind):
        raise TypeError("owner payload specs must exactly cover every capability kind")
    for spec in specs:
        if (
            type(spec) is not _OwnerPayloadSpec
            or type(spec.kind) is not OwnerCapabilityKind
            or not isinstance(spec.token_type, type)
            or not isinstance(spec.payload_type, type)
            or type(spec.exact_concrete_leaves) is not tuple
            or type(spec.child_resource_paths) is not tuple
            or type(spec.nested_tokens) is not tuple
        ):
            raise TypeError("owner payload spec has an invalid type/kind/token relation")
        _validate_fieldless_owner_token_type(spec.token_type)
        leaf_paths: list[tuple[str, ...]] = []
        for leaf in spec.exact_concrete_leaves:
            if (
                type(leaf) is not _OwnerPayloadLeafSpec
                or not exact_path(leaf.field_path)
                or not isinstance(leaf.exact_concrete_type, type)
            ):
                raise TypeError("owner payload leaf spec is not exact")
            leaf_paths.append(leaf.field_path)
        if len(leaf_paths) != len(set(leaf_paths)):
            raise TypeError("owner payload leaf paths must be unique")
        for field_path in spec.child_resource_paths:
            if not exact_path(field_path) or field_path not in leaf_paths:
                raise TypeError("child resource must name an exact registered leaf")
        if len(spec.child_resource_paths) != len(set(spec.child_resource_paths)):
            raise TypeError("child resource paths must be unique")
        if (spec.dynamic_record_domain_path is None) != (
            spec.dynamic_record_ref_domain_path is None
        ):
            raise TypeError("dynamic record and ref domains must be paired")
        for field_path in (
            spec.dynamic_record_domain_path, spec.dynamic_record_ref_domain_path,
        ):
            if field_path is not None and not exact_path(field_path):
                raise TypeError("dynamic record domain paths must be exact")
        nested_paths: list[tuple[str, ...]] = []
        for nested in spec.nested_tokens:
            if (
                type(nested) is not _OwnerNestedTokenSpec
                or type(nested.cardinality) is not _OwnerNestedCardinality
                or type(nested.nested_kind) is not OwnerCapabilityKind
                or not exact_path(nested.payload_path)
                or not exact_path(nested.token_path, allow_empty=True)
                or (
                    nested.expected_domain_path is not None
                    and not exact_path(nested.expected_domain_path)
                )
            ):
                raise TypeError("nested owner-token spec is not exact")
            nested_paths.append(nested.payload_path)
        if len(nested_paths) != len(set(nested_paths)):
            raise TypeError("nested owner-token paths must be unique")

    spec_by_token = MappingProxyType({spec.token_type: spec for spec in specs})
    spec_by_kind = MappingProxyType({spec.kind: spec for spec in specs})
    if not (
        len(spec_by_token) == len(spec_by_kind) == len(specs)
        == len(OwnerCapabilityKind)
        and set(spec_by_kind) == set(OwnerCapabilityKind)
    ):
        raise TypeError("owner payload specs must be a kind-complete bijection")
    for spec in specs:
        if (
            spec_by_token.get(spec.token_type) is not spec
            or spec_by_kind.get(spec.kind) is not spec
            or any(nested.nested_kind not in spec_by_kind for nested in spec.nested_tokens)
        ):
            raise TypeError("owner payload spec has an incomplete domain/resource relation")
        validate_owner_payload_spec_annotation_graph(
            spec=spec, spec_by_kind=spec_by_kind,
        )
    instances: WeakKeyDictionary[object, _OwnerCapabilityEntry[object, object]] = (
        WeakKeyDictionary()
    )
    released_tokens: WeakKeyDictionary[
        object, _OwnerPayloadSpec[object, object]
    ] = WeakKeyDictionary()
    forked_tokens: WeakKeyDictionary[
        object, _OwnerPayloadSpec[object, object]
    ] = WeakKeyDictionary()
    active_borrows: WeakKeyDictionary[object, int] = WeakKeyDictionary()
    process_instance = object()
    child_disposal_failed = False

    def resolve_registered_spec(
        candidate: object,
    ) -> _OwnerPayloadSpec[object, object]:
        capability_kind = (
            candidate.kind
            if type(candidate) is _OwnerPayloadSpec
            and type(candidate.kind) is OwnerCapabilityKind
            else None
        )
        if (
            type(candidate) is not _OwnerPayloadSpec
            or type(candidate.kind) is not OwnerCapabilityKind
        ):
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=capability_kind,
            )
        registered_by_kind = spec_by_kind.get(candidate.kind)
        if registered_by_kind is not candidate:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=capability_kind,
            )
        registered_by_token = spec_by_token.get(registered_by_kind.token_type)
        if registered_by_token is not registered_by_kind:
            raise TypeError("registered owner capability maps disagree")
        return cast(_OwnerPayloadSpec[object, object], candidate)

    def follow(value: object, field_path: tuple[str, ...]) -> object:
        for name in field_path:
            value = getattr(value, name)
        return value

    def validate_payload(
        spec: _OwnerPayloadSpec[object, object], payload: object, *,
        expected_record_domain: DigestDomain | None,
        bind_dynamic_domain_to_payload: bool = False,
    ) -> None:
        # This exact-type test is the first payload operation. In particular,
        # no dynamic-domain path/property may be read before it.
        if type(payload) is not spec.payload_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=spec.kind,
            )
        # Generic implementation reconstructs every frozen Pydantic leaf from
        # its strict dump and rejects Protocol, object, Any or unregistered
        # capability annotations anywhere in the payload graph.
        validate_owner_payload_annotation_graph(payload, spec_by_token=spec_by_token)
        for leaf in spec.exact_concrete_leaves:
            if type(follow(payload, leaf.field_path)) is not leaf.exact_concrete_type:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=spec.kind, payload_path=leaf.field_path,
                )
        if spec.dynamic_record_domain_path is not None:
            actual = follow(payload, spec.dynamic_record_domain_path)
            bound_ref_domain = follow(
                payload, cast(tuple[str, ...], spec.dynamic_record_ref_domain_path)
            )
            required = actual if bind_dynamic_domain_to_payload else expected_record_domain
            if (
                required is None
                or actual is not required
                or bound_ref_domain is not required
            ):
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.WRONG_RECORD_DOMAIN,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=spec.kind,
                    payload_path=spec.dynamic_record_domain_path,
                    expected_record_domain=required,
                    actual_record_domain=cast(DigestDomain, actual),
                )

    def validate_nested(
        payload: object, spec: _OwnerPayloadSpec[object, object], *,
        seen_token_ids: set[int],
    ) -> None:
        for nested in spec.nested_tokens:
            raw = follow(payload, nested.payload_path)
            members = (
                cast(tuple[object, ...], raw)
                if nested.cardinality is _OwnerNestedCardinality.MANY
                else (raw,)
            )
            nested_spec = spec_by_kind[nested.nested_kind]
            for member in members:
                token = follow(member, nested.token_path) if nested.token_path else member
                expected_domain = (
                    cast(DigestDomain, follow(member, nested.expected_domain_path))
                    if nested.expected_domain_path is not None else None
                )
                unwrap_impl(
                    token, nested_spec,
                    expected_record_domain=expected_domain,
                    seen_token_ids=seen_token_ids,
                    payload_path=nested.payload_path,
                )

    def unwrap_impl(
        value: object, spec: _OwnerPayloadSpec[C, P], /, *,
        expected_record_domain: DigestDomain | None = None,
        seen_token_ids: set[int],
        payload_path: tuple[str, ...] = (),
    ) -> P:
        nonlocal child_disposal_failed
        registered_spec = cast(
            _OwnerPayloadSpec[C, P], resolve_registered_spec(spec)
        )
        # Exact type precedes WeakKeyDictionary access: mappings, lists, strings
        # and every other novel non-hashable/non-weakrefable input become faults.
        if type(value) is not registered_spec.token_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_TOKEN_TYPE,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        if child_disposal_failed:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.CHILD_RESOURCE_DISPOSAL_FAILED,
                disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        if id(value) in seen_token_ids:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.INVALID_NESTED_CAPABILITY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        seen_token_ids.add(id(value))
        with lifecycle_section():
            forked_spec = forked_tokens.get(value)
            entry = instances.get(value)
        if forked_spec is registered_spec:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        if entry is None:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.UNMINTED_TOKEN,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        if (
            entry.spec is not registered_spec
        ):
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        if entry.creator_pid != os.getpid() or entry.process_instance is not process_instance:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                capability_kind=registered_spec.kind, payload_path=payload_path,
            )
        validate_payload(
            cast(_OwnerPayloadSpec[object, object], registered_spec), entry.payload,
            expected_record_domain=expected_record_domain,
        )
        validate_nested(
            entry.payload, cast(_OwnerPayloadSpec[object, object], registered_spec),
            seen_token_ids=seen_token_ids,
        )
        return cast(P, entry.payload)

    def unwrap(
        value: object, spec: _OwnerPayloadSpec[C, P], /, *,
        expected_record_domain: DigestDomain | None = None,
    ) -> ContextManager[P]:
        @contextmanager
        def borrow() -> Iterator[P]:
            # Hold the coordinator's sole transition lock for the entire use,
            # not only lookup. Release/fork cannot close a resource while the
            # caller holds the unwrapped payload.
            with lifecycle_section():
                payload = unwrap_impl(
                    value, spec, expected_record_domain=expected_record_domain,
                    seen_token_ids=set(),
                )
                active_borrows[value] = active_borrows.get(value, 0) + 1
                try:
                    yield payload
                finally:
                    remaining = active_borrows[value] - 1
                    if remaining:
                        active_borrows[value] = remaining
                    else:
                        active_borrows.pop(value, None)
        return borrow()

    def prepare_payload_resources(
        spec: _OwnerPayloadSpec[object, object], payload: object,
    ) -> tuple[_OwnerChildDisposable, ...]:
        """Phase A: exact type/path extraction only; never call a child method."""
        if type(payload) is not spec.payload_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=spec.kind,
            )
        exact_types = {
            leaf.field_path: leaf.exact_concrete_type
            for leaf in spec.exact_concrete_leaves
        }
        resources: list[_OwnerChildDisposable] = []
        for field_path in spec.child_resource_paths:
            raw_resource = follow(payload, field_path)
            if type(raw_resource) is not exact_types[field_path]:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=spec.kind, payload_path=field_path,
                )
            resources.append(cast(_OwnerChildDisposable, raw_resource))
        return tuple(resources)

    def mint(spec: _OwnerPayloadSpec[C, P], payload: P, /) -> C:
        nonlocal child_disposal_failed
        registered_spec = cast(
            _OwnerPayloadSpec[C, P], resolve_registered_spec(spec)
        )
        with lifecycle_section():
            if child_disposal_failed:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.CHILD_RESOURCE_DISPOSAL_FAILED,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered_spec.kind,
                )
            # Phase A is side-effect-free: exact payload type, declared child
            # extraction and exact concrete child types only. It never follows
            # a dynamic-domain path and never invokes a child method.
            resources = prepare_payload_resources(
                cast(_OwnerPayloadSpec[object, object], registered_spec), payload
            )
            claim: _OwnerResourceClaim | None = None
            try:
                # Phase B begins by taking provisional ownership. Claim is
                # internally transactional; every later recursive/domain/
                # nested failure rolls it back synchronously.
                claim = claim_owner_resources(
                    capability_kind=registered_spec.kind, resources=resources,
                )
                validate_payload(
                    cast(_OwnerPayloadSpec[object, object], registered_spec), payload,
                    expected_record_domain=None,
                    bind_dynamic_domain_to_payload=(
                        registered_spec.dynamic_record_domain_path is not None
                    ),
                )
                validate_nested(
                    payload, cast(_OwnerPayloadSpec[object, object], registered_spec),
                    seen_token_ids=set(),
                )
                token = object.__new__(registered_spec.token_type)
                resource_finalizer = finalize(
                    token, release_owner_resources, claim
                )
                instances[token] = _OwnerCapabilityEntry(
                    spec=cast(_OwnerPayloadSpec[object, object], registered_spec),
                    creator_pid=os.getpid(), process_instance=process_instance,
                    payload=payload, resource_finalizer=resource_finalizer,
                )
                return cast(C, token)
            except BaseException:
                if claim is not None:
                    release_owner_resources(claim)
                raise

    def release(value: object, spec: _OwnerPayloadSpec[C, P], /) -> None:
        registered_spec = cast(
            _OwnerPayloadSpec[C, P], resolve_registered_spec(spec)
        )
        if type(value) is not registered_spec.token_type:
            raise OwnerCapabilityFault(
                code=OwnerCapabilityFaultCode.WRONG_TOKEN_TYPE,
                disposition=OwnerCapabilityFaultDisposition.REJECTED,
                capability_kind=registered_spec.kind,
            )
        with lifecycle_section():
            forked_spec = forked_tokens.get(value)
            entry = instances.get(value)
            if forked_spec is registered_spec:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.FORKED_PROCESS,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered_spec.kind,
                )
            if entry is None:
                if released_tokens.get(value) is registered_spec:
                    return
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.UNMINTED_TOKEN,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=registered_spec.kind,
                )
            if entry.spec is not registered_spec:
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.WRONG_CAPABILITY_FAMILY,
                    disposition=OwnerCapabilityFaultDisposition.REJECTED,
                    capability_kind=registered_spec.kind,
                )
            if active_borrows.get(value, 0):
                raise OwnerCapabilityFault(
                    code=OwnerCapabilityFaultCode.RESOURCE_IN_USE,
                    disposition=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
                    capability_kind=registered_spec.kind,
                )
            # Close and state transition share the same coordinator lock.
            entry.resource_finalizer()
            instances.pop(value, None)
            released_tokens[value] = cast(
                _OwnerPayloadSpec[object, object], registered_spec
            )

    def after_fork_token_sweep(resource_disposal_failed: bool) -> None:
        """Retain token provenance, but no payload or child resource, in child."""
        nonlocal process_instance, child_disposal_failed
        with lifecycle_section():
            inherited = tuple(instances.items())
            for token, entry in inherited:
                entry.resource_finalizer.detach()
                forked_tokens[token] = entry.spec
            instances.clear()
            released_tokens.clear()
            active_borrows.clear()
            process_instance = object()
            child_disposal_failed = (
                child_disposal_failed or resource_disposal_failed
            )
        # The coordinator invokes this participant inside its sole serialized
        # transition, then replaces the inherited coordinator lock.

    register_fork_participant(after_fork_token_sweep)
    return mint, unwrap, release

def _guard_owner_entrypoint(
    function: Callable[PS, R], *, spec: OwnerEntrypointSpec,
    failure_factory: Callable[
        [OwnerCapabilityFault, inspect.BoundArguments, OwnerEntrypointSpec], R
    ],
) -> Callable[PS, R]:
    """Bind call context, return one exact typed failure and preserve signature."""
    call_signature = inspect.signature(function)
    @wraps(function)
    def guarded(*args: PS.args, **kwargs: PS.kwargs) -> R:
        bound = call_signature.bind(*args, **kwargs)
        try:
            return function(*args, **kwargs)
        except OwnerCapabilityFault as error:
            return failure_factory(error, bound, spec)
    return guarded

def _require_sorted_unique(keys: tuple[str, ...], *, label: str) -> None:
    if not keys or len(keys) != len(set(keys)) or keys != tuple(sorted(keys)):
        raise ValueError(f"{label} must be non-empty, unique and canonically sorted")

class RootedRelativePath(FoundryAuthorityModel):
    value: Annotated[StrictStr, AuthorityScalarRole.REQUEST_PATH]

    @field_validator("value")
    @classmethod
    def validate_rooted_relative_path(cls, value: str) -> str:
        candidate = PurePosixPath(value)
        if (
            not value or "\x00" in value or not candidate.parts
            or candidate == PurePosixPath(".")
            or candidate.is_absolute() or value != candidate.as_posix()
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise ValueError("path must be canonical, relative and root-contained")
        return value

class AbsoluteRequestPath(FoundryAuthorityModel):
    value: Annotated[Path, AuthorityScalarRole.REQUEST_PATH]

    @field_validator("value")
    @classmethod
    def validate_absolute_request_path(cls, value: Path) -> Path:
        if not value.is_absolute() or "\x00" in str(value):
            raise ValueError("request path must be absolute and NUL-free")
        return value

class LauncherProfileSpec(FoundryAuthorityModel):
    profile_id: Literal[LauncherNormalizationProfile.POSIX_CONSOLE_SCRIPT_V1]
    supported_platform_family: tuple[Literal["darwin", "linux"], ...]
    python_abi: Literal["cp314"]
    line_ending: Literal["lf"]
    interpreter_occurrences: Literal[1]
    normalized_interpreter_token: Literal["@PYTHON@"]
    expected_producer_id: Literal[LauncherExpectedProducerId.DISTLIB_POSIX_CONSOLE_V1]
    observed_verifier_id: Literal[LauncherObservedVerifierId.PARSE_DISTLIB_POSIX_CONSOLE_V1]

class LauncherNormalizationVerified(FoundryAuthorityModel):
    status: Literal["verified"]
    normalized_wrapper_bytes: ExactBytes

class LauncherNormalizationRejected(FoundryAuthorityModel):
    status: Literal["rejected"]
    code: Literal[
        "launcher_grammar_mismatch", "launcher_interpreter_count_mismatch",
        "launcher_entrypoint_mismatch", "launcher_flags_mismatch",
        "launcher_line_ending_mismatch",
    ]

LauncherNormalizationResult = Annotated[
    LauncherNormalizationVerified | LauncherNormalizationRejected,
    Field(discriminator="status"),
]

class LauncherNormalizationABI(Protocol):
    def build_expected(
        self, *, spec: LauncherProfileSpec, entrypoint_target: EntrypointText,
        interpreter_bytes: ExactBytes, normalized_flags: tuple[ArgumentText, ...],
    ) -> bytes: ...
    def verify_and_normalize(
        self, *, spec: LauncherProfileSpec, entrypoint_target: EntrypointText,
        observed_wrapper_bytes: ExactBytes, admitted_interpreter_bytes: ExactBytes,
        normalized_flags: tuple[ArgumentText, ...],
    ) -> LauncherNormalizationResult: ...

class DomainDigest(FoundryAuthorityModel, Generic[D_co]):
    domain: D_co
    value: Sha256

class FoundryRecordRef(FoundryAuthorityModel, Generic[D_co]):
    artifact_id: ArtifactIdWire
    semantic_hash: DomainDigest[D_co]
    schema_version: SchemaVersionText

class ExternalAuthorityRef(FoundryAuthorityModel, Generic[E_co]):
    authority_kind: E_co
    value: IdentityText
    resolver_appointment_ref: DomainDigest[Literal[DigestDomain.VERIFIER_APPOINTMENT]]

class CanonicalStatementDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.CANONICAL_STATEMENT_V1]
    preimage_kind: Literal[DigestPreimageKind.CANONICAL_STATEMENT]
    producer_id: Literal[DigestProducerId.CANONICAL_STATEMENT_V1]
    verifier_id: Literal[DigestVerifierId.RECOMPUTE_CANONICAL_STATEMENT_V1]
    ordering_rule: Literal[DigestOrderingRule.CANON_JSON_V1]

class RawBlobDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.RAW_BLOB_V1]
    preimage_kind: Literal[DigestPreimageKind.RAW_BLOB]
    producer_id: Literal[DigestProducerId.RAW_BLOB_V1]
    verifier_id: Literal[DigestVerifierId.REHASH_RAW_BLOB_V1]
    ordering_rule: Literal[DigestOrderingRule.RAW_BYTES_IDENTITY]

class TrackedTomlDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.TRACKED_TOML_V1]
    preimage_kind: Literal[DigestPreimageKind.TRACKED_TOML]
    producer_id: Literal[DigestProducerId.TRACKED_TOML_V1]
    verifier_id: Literal[DigestVerifierId.REPARSE_TRACKED_TOML_V1]
    ordering_rule: Literal[DigestOrderingRule.TOML_UTF8_CANON_V1]

class OrderedRowsDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.ORDERED_ROWS_V1]
    preimage_kind: Literal[DigestPreimageKind.ORDERED_ROWS]
    producer_id: Literal[DigestProducerId.ORDERED_ROWS_V1]
    verifier_id: Literal[DigestVerifierId.RECOMPUTE_ORDERED_ROWS_V1]
    ordering_rule: Literal[DigestOrderingRule.LEXICOGRAPHIC_FRAMED_ROWS_V1]

class RelationDigestAlgebra(FoundryAuthorityModel):
    algebra_id: Literal[DigestAlgebraId.RELATION_V1]
    preimage_kind: Literal[DigestPreimageKind.RELATION]
    producer_id: Literal[DigestProducerId.RELATION_V1]
    verifier_id: Literal[DigestVerifierId.RECOMPUTE_RELATION_V1]
    ordering_rule: Literal[DigestOrderingRule.ORDERED_FRAMED_RELATION_V1]

DigestAlgebraSpec = Annotated[
    CanonicalStatementDigestAlgebra | RawBlobDigestAlgebra
    | TrackedTomlDigestAlgebra | OrderedRowsDigestAlgebra
    | RelationDigestAlgebra,
    Field(discriminator="algebra_id"),
]

class DigestDomainSpec(FoundryAuthorityModel):
    domain_id: DigestDomain
    # TOML stores lowercase even-length hex; decoding is exactly bytes.fromhex().
    # The decoded prefix is non-empty and NUL-terminated.
    prefix_hex: HexBytes
    algebra: DigestAlgebraSpec
    phase: DigestPhase
    signature_requirement: Literal["unsigned", "signed"]
    required_signer_role: TrustRole | None

    @model_validator(mode="after")
    def validate_executable_row(self) -> DigestDomainSpec:
        prefix = bytes.fromhex(self.prefix_hex)
        expected = f"polisyos.foundry.{self.domain_id.value}.v1\0".encode("ascii")
        if prefix != expected:
            raise ValueError("digest prefix does not equal its domain-derived Foundry prefix")
        if (self.signature_requirement == "signed") != (self.required_signer_role is not None):
            raise ValueError("signature requirement and signer role must be paired")
        return self

class DomainEvidenceRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["domain_evidence"]
    evidence_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]

class MissingEvidenceDomainsRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["missing_evidence_domains"]
    missing_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]

class SourceFreezeRelationEvidenceRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["source_freeze_relation"]
    request_commit_path: Literal[
        "result.request.pre_source_request.expected_source_freeze_commit"
    ]
    request_tree_path: Literal["result.request.expected_source_tree_id"]
    observed_commit_path: Literal["result.failure.owner_observed_head_commit"]
    observed_tree_path: Literal["result.failure.owner_observed_tree_id"]
    observation_producer: Literal["canonical_module_git_recompute_v1"]
    require_same_owner_root: Literal[True]
    require_commit_or_tree_inequality: Literal[True]

class MissingGateCapabilityEvidenceRequirement(FoundryAuthorityModel):
    requirement_kind: Literal["missing_gate_capability"]
    capability_id: Literal["owner_enforced_runtime_subtree_cutoff"]
    capability_state: Literal["absent/unallocated"]
    candidate_evidence_rule: Literal["orthogonal_present_or_not_requested"]

AuthorityEvidenceRequirement = Annotated[
    DomainEvidenceRequirement | MissingEvidenceDomainsRequirement
    | SourceFreezeRelationEvidenceRequirement
    | MissingGateCapabilityEvidenceRequirement,
    Field(discriminator="requirement_kind"),
]

class BidirectionalAuthorityPredicateSpec(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    predicate_id: AuthorityPredicateId
    admitted_classes: Annotated[
        tuple[Literal["recomputed", "independently_reconciled"], ...],
        Field(min_length=1),
    ]
    satisfied_requirement: DomainEvidenceRequirement
    rejected_code: AuthorityFailureCode
    rejected_requirement: AuthorityEvidenceRequirement
    not_established_code: AuthorityFailureCode
    not_established_requirement: AuthorityEvidenceRequirement

class NotEstablishedOnlyAuthorityPredicateSpec(FoundryAuthorityModel):
    branch_shape: Literal["not_established_only"]
    predicate_id: AuthorityPredicateId
    not_established_code: AuthorityFailureCode
    not_established_requirement: AuthorityEvidenceRequirement

AuthorityPredicateSpec = Annotated[
    BidirectionalAuthorityPredicateSpec
    | NotEstablishedOnlyAuthorityPredicateSpec,
    Field(discriminator="branch_shape"),
]

class SatisfiedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    status: Literal["satisfied"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: BidirectionalAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["recomputed", "independently_reconciled"]
    evidence_refs: Annotated[tuple[FoundryRecordRef[DigestDomain], ...], Field(min_length=1)]
    @model_validator(mode="after")
    def validate_bound_branch(self) -> SatisfiedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self

class RejectedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    status: Literal["rejected"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: BidirectionalAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["recomputed", "independently_reconciled"]
    failure_code: AuthorityFailureCode
    evidence_refs: Annotated[tuple[FoundryRecordRef[DigestDomain], ...], Field(min_length=1)]
    @model_validator(mode="after")
    def validate_bound_branch(self) -> RejectedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self

class BidirectionalUnestablishedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["bidirectional"]
    status: Literal["not_established"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: BidirectionalAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["not_established"]
    failure_code: AuthorityFailureCode
    missing_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]
    @model_validator(mode="after")
    def validate_bound_branch(self) -> BidirectionalUnestablishedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self

class OneSidedUnestablishedAuthorityPredicate(FoundryAuthorityModel):
    branch_shape: Literal["not_established_only"]
    status: Literal["not_established"]
    predicate_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    predicate_spec: NotEstablishedOnlyAuthorityPredicateSpec
    predicate_id: AuthorityPredicateId
    predicate_class: Literal["not_established"]
    failure_code: AuthorityFailureCode
    missing_capability: IdentityText
    missing_capability_state: Literal["absent/unallocated"]
    @model_validator(mode="after")
    def validate_bound_branch(self) -> OneSidedUnestablishedAuthorityPredicate:
        validate_bound_predicate_disposition(self)
        return self

UnestablishedAuthorityPredicate = Annotated[
    BidirectionalUnestablishedAuthorityPredicate
    | OneSidedUnestablishedAuthorityPredicate,
    Field(discriminator="branch_shape"),
]

BidirectionalAuthorityPredicateDisposition = Annotated[
    SatisfiedAuthorityPredicate | RejectedAuthorityPredicate
    | BidirectionalUnestablishedAuthorityPredicate,
    Field(discriminator="status"),
]
AuthorityPredicateDisposition = Annotated[
    BidirectionalAuthorityPredicateDisposition
    | OneSidedUnestablishedAuthorityPredicate,
    Field(discriminator="branch_shape"),
]

def validate_bound_predicate_disposition(
    disposition: AuthorityPredicateDisposition,
) -> None:
    """Bind branch, ID, class, code and evidence to the embedded exact spec.

    The owner additionally resolves ``predicate_registry_ref`` through the
    already-minted canonical-source payload and requires byte-for-byte equality
    with that registry row. A shaped alternate spec/ref is never authority.
    """
    ...

class MethodCatalogDependencyProfileDeclaration(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-profile.v1"]
    profile_id: IdentityText
    root_distribution: IdentityText
    extras: tuple[IdentityText, ...]
    python_constraint: PythonConstraintText
    resolver_name: Literal["uv"]
    resolver_version: Literal["0.9.21"]
    pyproject_ref: DomainDigest[Literal[DigestDomain.PYPROJECT]]
    lockfile_ref: DomainDigest[Literal[DigestDomain.UV_LOCK]]

class MethodCatalogProfileAdmission(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.profile-admission.v1"]
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    profile_id: IdentityText
    declaration_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_DECLARATION]]
    python_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    uv_executable_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]]
    production_data_trust_policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]
    predicate_class: Literal["recomputed"]

class DependencyProfileRegistryStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-profile-registry.v1"]
    declarations: tuple[MethodCatalogDependencyProfileDeclaration, ...]

class DigestDomainRegistryStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.digest-domain-registry.v1"]
    domains: tuple[DigestDomainSpec, ...]
    predicates: tuple[AuthorityPredicateSpec, ...]

class FoundryTomlWireModel(BaseModel):
    """Strict transport shape; it carries no semantic enum authority."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

class DigestAlgebraTomlWire(FoundryTomlWireModel):
    algebra_id: StrictStr
    preimage_kind: StrictStr
    producer_id: StrictStr
    verifier_id: StrictStr
    ordering_rule: StrictStr

class DigestDomainTomlWire(FoundryTomlWireModel):
    domain_id: StrictStr
    prefix_hex: StrictStr
    algebra: DigestAlgebraTomlWire
    phase: StrictStr
    signature_requirement: StrictStr
    required_signer_role: StrictStr | None = None

class DomainEvidenceRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["domain_evidence"]
    evidence_domains: list[StrictStr]

class MissingEvidenceDomainsRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["missing_evidence_domains"]
    missing_domains: list[StrictStr]

class SourceFreezeRelationRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["source_freeze_relation"]
    request_commit_path: StrictStr
    request_tree_path: StrictStr
    observed_commit_path: StrictStr
    observed_tree_path: StrictStr
    observation_producer: StrictStr
    require_same_owner_root: bool
    require_commit_or_tree_inequality: bool

class MissingGateCapabilityRequirementTomlWire(FoundryTomlWireModel):
    requirement_kind: Literal["missing_gate_capability"]
    capability_id: StrictStr
    capability_state: StrictStr
    candidate_evidence_rule: StrictStr

AuthorityEvidenceRequirementTomlWire = Annotated[
    DomainEvidenceRequirementTomlWire | MissingEvidenceDomainsRequirementTomlWire
    | SourceFreezeRelationRequirementTomlWire
    | MissingGateCapabilityRequirementTomlWire,
    Field(discriminator="requirement_kind"),
]

class BidirectionalAuthorityPredicateTomlWire(FoundryTomlWireModel):
    branch_shape: Literal["bidirectional"]
    predicate_id: StrictStr
    admitted_classes: list[StrictStr]
    satisfied_requirement: DomainEvidenceRequirementTomlWire
    rejected_code: StrictStr
    rejected_requirement: AuthorityEvidenceRequirementTomlWire
    not_established_code: StrictStr
    not_established_requirement: AuthorityEvidenceRequirementTomlWire

class NotEstablishedOnlyAuthorityPredicateTomlWire(FoundryTomlWireModel):
    branch_shape: Literal["not_established_only"]
    predicate_id: StrictStr
    not_established_code: StrictStr
    not_established_requirement: AuthorityEvidenceRequirementTomlWire

AuthorityPredicateTomlWire = Annotated[
    BidirectionalAuthorityPredicateTomlWire
    | NotEstablishedOnlyAuthorityPredicateTomlWire,
    Field(discriminator="branch_shape"),
]

class DigestDomainRegistryTomlWire(FoundryTomlWireModel):
    schema_version: Literal["polisyos.foundry.digest-domain-registry.v1"]
    domains: list[DigestDomainTomlWire]
    predicates: list[AuthorityPredicateTomlWire]

class DecodedDigestDomainRegistry(FoundryAuthorityModel):
    registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]
    statement: DigestDomainRegistryStatement
    canonical_statement_bytes: ExactBytes
    semantic_hash: DomainDigest[Literal[DigestDomain.DIGEST_REGISTRY]]

EnumT = TypeVar("EnumT", bound=StrEnum)

def _exact_enum(enum_type: type[EnumT], value: object) -> EnumT:
    if type(value) is not str:
        raise ValueError("enum wire value must be an exact string")
    matches = tuple(
        member for _name, member in enum_type.__members__.items()
        if value == member.value
    )
    if len(matches) != 1:
        raise ValueError("unknown, aliased or non-exact enum wire value")
    return matches[0]

def _decode_digest_algebra(wire: DigestAlgebraTomlWire) -> DigestAlgebraSpec:
    algebra_id = _exact_enum(DigestAlgebraId, wire.algebra_id)
    variant = {
        DigestAlgebraId.CANONICAL_STATEMENT_V1: CanonicalStatementDigestAlgebra,
        DigestAlgebraId.RAW_BLOB_V1: RawBlobDigestAlgebra,
        DigestAlgebraId.TRACKED_TOML_V1: TrackedTomlDigestAlgebra,
        DigestAlgebraId.ORDERED_ROWS_V1: OrderedRowsDigestAlgebra,
        DigestAlgebraId.RELATION_V1: RelationDigestAlgebra,
    }[algebra_id]
    return variant(
        algebra_id=algebra_id,
        preimage_kind=_exact_enum(DigestPreimageKind, wire.preimage_kind),
        producer_id=_exact_enum(DigestProducerId, wire.producer_id),
        verifier_id=_exact_enum(DigestVerifierId, wire.verifier_id),
        ordering_rule=_exact_enum(DigestOrderingRule, wire.ordering_rule),
    )

def decode_digest_domain_registry_toml(
    raw_toml_bytes: ExactBytes, *,
    expected_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]],
) -> DecodedDigestDomainRegistry:
    """Parse, exact-map and require the recomputed registry ref/hash."""
    # The implementation explicitly constructs every DigestDomainSpec and
    # AuthorityPredicateSpec/evidence-requirement variant with _exact_enum();
    # model_validate on the semantic DTO is forbidden. tomllib output first
    # passes DigestDomainRegistryTomlWire. Unknown or cross-branch requirement
    # fields fail before the semantic registry is hashed.
    ...

class VerifierProvenanceStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.verifier-provenance.v1"]
    verifier_id: IdentityText
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    configuration_ref: FoundryRecordRef[Literal[DigestDomain.RAW_BLOB]]

class LockedDistributionIdentity(FoundryAuthorityModel):
    normalized_name: IdentityText
    version: VersionText
    source_kind: Literal["registry", "url", "git", "path"]
    selected_artifact_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]]
    expected_stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    expected_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]
    marker_expression: MarkerExpressionText | None

class StablePayloadFileRow(FoundryAuthorityModel):
    row_kind: Literal["payload"]
    logical_root: Literal["purelib", "platlib", "scripts", "data", "headers"]
    relative_path: RootedRelativePath
    byte_length: ByteLength
    raw_content_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]

class StableEntrypointFileRow(FoundryAuthorityModel):
    row_kind: Literal["generated_entrypoint"]
    logical_root: Literal["scripts"]
    relative_path: RootedRelativePath
    entrypoint_target: EntrypointText
    launcher_profile: LauncherNormalizationProfile
    python_abi: AbiTagText
    normalized_flags: tuple[ArgumentText, ...]

StableInstalledFileRow = Annotated[
    StablePayloadFileRow | StableEntrypointFileRow,
    Field(discriminator="row_kind"),
]

class InstalledInstanceFileRow(FoundryAuthorityModel):
    environment_relative_path: RootedRelativePath
    byte_length: ByteLength
    raw_content_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]

class StableInstalledDistributionManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.installed-tree-stable.v1"]
    normalized_name: IdentityText
    version: VersionText
    transform_profile: Literal["wheel_install_tree_v1", "source_first_tree_v1"]
    rows: tuple[StableInstalledFileRow, ...]

class InstalledDistributionInstanceManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.installed-tree-instance.v1"]
    environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]
    normalized_name: IdentityText
    version: VersionText
    rows: tuple[InstalledInstanceFileRow, ...]
    recomputed_stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]

class WheelInstalledSourceBindingStatement(FoundryAuthorityModel):
    binding_kind: Literal["wheel"]
    schema_version: Literal["polisyos.foundry.installed-source-binding.v1"]
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    selected_evidence_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]]
    stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    transform_profile: Literal["wheel_install_tree_v1"]

class BuiltInstalledSourceBindingStatement(WheelInstalledSourceBindingStatement):
    binding_kind: Literal["built_source"]
    build_lineage_ref: FoundryRecordRef[Literal[DigestDomain.BUILD_LINEAGE]]

class SourceFirstInstalledSourceBindingStatement(FoundryAuthorityModel):
    binding_kind: Literal["source_first"]
    schema_version: Literal["polisyos.foundry.installed-source-binding.v1"]
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    selected_evidence_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]]
    stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    transform_profile: Literal["source_first_tree_v1"]
    source_tree_ref: FoundryRecordRef[Literal[DigestDomain.SOURCE_TREE]]

InstalledSourceBindingStatement = Annotated[
    WheelInstalledSourceBindingStatement | BuiltInstalledSourceBindingStatement
    | SourceFirstInstalledSourceBindingStatement,
    Field(discriminator="binding_kind"),
]

class WheelRecordManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.wheel-record-manifest.v1"]
    wheel_blob_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    stable_rows: tuple[StableInstalledFileRow, ...]

class SourceTreeManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.source-tree-manifest.v1"]
    source_freeze_commit: GitCommitId
    rows: tuple[StableInstalledFileRow, ...]

class BuildProfileStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.build-profile.v1"]
    build_backend: BuildBackendText
    python_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    build_requirement_refs: tuple[FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]], ...]
    normalized_environment: tuple[tuple[EnvironmentKeyText, EnvironmentValueText], ...]

class InstalledDistributionIdentity(FoundryAuthorityModel):
    normalized_name: IdentityText
    version: VersionText
    selected_artifact_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]]
    observed_stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    observed_instance_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_INSTANCE]]
    observed_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]

class BuildLineageStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.build-lineage.v1"]
    source_artifact_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_SOURCE]]
    builder_toolchain_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    build_profile_ref: FoundryRecordRef[Literal[DigestDomain.BUILD_PROFILE]]
    normalized_argv_hash: DomainDigest[Literal[DigestDomain.BUILD_ARGV]]
    build_environment_hash: DomainDigest[Literal[DigestDomain.BUILD_ENVIRONMENT]]
    output_wheel_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    verifier_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]
    trust_resolution_receipt_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_RESOLUTION]]

class PersistedBuildLineageEvidence(FoundryAuthorityModel):
    record_ref: FoundryRecordRef[Literal[DigestDomain.BUILD_LINEAGE]]
    statement: BuildLineageStatement
    signed_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]

class SelectedWheelArtifactEvidence(FoundryAuthorityModel):
    artifact_kind: Literal["wheel"]
    schema_version: Literal["polisyos.foundry.selected-wheel.v1"]
    normalized_name: IdentityText
    version: VersionText
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    wheel_blob_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    wheel_record_manifest_ref: FoundryRecordRef[Literal[DigestDomain.WHEEL_RECORD]]
    expected_stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    expected_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]

class SelectedBuiltArtifactEvidence(FoundryAuthorityModel):
    artifact_kind: Literal["built_source"]
    schema_version: Literal["polisyos.foundry.selected-built-wheel.v1"]
    normalized_name: IdentityText
    version: VersionText
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    source_blob_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_SOURCE]]
    build_lineage: PersistedBuildLineageEvidence
    output_wheel_ref: FoundryRecordRef[Literal[DigestDomain.SELECTED_WHEEL]]
    expected_stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    expected_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]

class SelectedSourceTreeEvidence(FoundryAuthorityModel):
    artifact_kind: Literal["source_tree"]
    schema_version: Literal["polisyos.foundry.selected-source-tree.v1"]
    normalized_name: IdentityText
    version: VersionText
    locked_source_ref: DomainDigest[Literal[DigestDomain.LOCKED_SOURCE]]
    tracked_source_commit: GitCommitId
    source_tree_manifest_ref: FoundryRecordRef[Literal[DigestDomain.SOURCE_TREE]]
    expected_stable_manifest_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_STABLE]]
    expected_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.INSTALLED_BINDING]]

SelectedDistributionArtifactEvidence = Annotated[
    SelectedWheelArtifactEvidence | SelectedBuiltArtifactEvidence | SelectedSourceTreeEvidence,
    Field(discriminator="artifact_kind"),
]

class PythonRuntimeRegularFileRow(FoundryAuthorityModel):
    row_kind: Literal["regular_file"]
    relative_path: RootedRelativePath
    role: Literal["launcher", "stdlib", "libpython", "runtime_library"]
    byte_length: ByteLength
    content_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]

class PythonRuntimeSymlinkRow(FoundryAuthorityModel):
    row_kind: Literal["symlink"]
    relative_path: RootedRelativePath
    role: Literal["launcher", "stdlib", "libpython", "runtime_library"]
    symlink_target: RootedRelativePath

PythonRuntimeFileRow = Annotated[
    PythonRuntimeRegularFileRow | PythonRuntimeSymlinkRow,
    Field(discriminator="row_kind"),
]

class PythonRuntimeManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime.v1"]
    implementation: Literal["cpython"]
    version: VersionText
    platform_tag: PlatformTagText
    abi_tag: AbiTagText
    executable_relative_path: RootedRelativePath
    files: Annotated[tuple[PythonRuntimeFileRow, ...], Field(min_length=1)]

class PythonRuntimeSourceBindingStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-source-binding.v1"]
    selected_artifact_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_SELECTED]]
    runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    installation_transform: Literal["python_runtime_installation_v1"]

class PosixRuntimeFilesystemKind(StrEnum):
    APFS = "apfs"
    EXT4 = "ext4"

class PosixRuntimeRootObservation(FoundryAuthorityModel):
    device_id: FilesystemIdentityNumber
    inode: FilesystemIdentityNumber
    mode_type: Literal["directory"]
    ctime_ns: FilesystemIdentityNumber

class PosixRuntimeRootIdentityStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.posix-runtime-root-identity.v1"]
    predicate_class: Literal["candidate_observation"]
    identity_profile: Literal["posix-open-directory-apfs-ext4-v1"]
    platform_family: Literal["darwin", "linux"]
    filesystem_kind: PosixRuntimeFilesystemKind
    environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]
    environment_root_path_hash: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH]]
    runtime_root_path_hash: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_PATH]]
    opened_before: PosixRuntimeRootObservation
    opened_after_enumeration: PosixRuntimeRootObservation
    reopened_by_path: PosixRuntimeRootObservation
    first_walk_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    second_walk_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]

    @model_validator(mode="after")
    def require_equal_two_pass_observations(self) -> PosixRuntimeRootIdentityStatement:
        if not (
            self.opened_before == self.opened_after_enumeration
            == self.reopened_by_path
        ):
            raise ValueError("runtime root identity changed during the two-pass walk")
        if self.first_walk_manifest_ref != self.second_walk_manifest_ref:
            raise ValueError("runtime subtree changed between complete walks")
        return self

class RuntimeSubtreeCutoffAuthority(Protocol):
    def preflight(self) -> RuntimeCutoffUnestablishedPredicate: ...

class _NoRuntimeSubtreeCutoffAuthority(
    _OwnerBoundaryBase, RuntimeSubtreeCutoffAuthority
):
    """Production v1: no appointed snapshot/writer-exclusion owner exists."""
    def preflight(self) -> RuntimeCutoffUnestablishedPredicate: ...

@dataclass(frozen=True, slots=True)
class _OpenedDescriptorIdentity:
    device_id: int
    inode: int
    mode_type: Literal["directory"]

class _OpenOwnerDirectory(Protocol):
    def __call__(
        self, *, directory: Path, owner_kind: OwnerCapabilityKind,
        handle_type: type[P],
    ) -> P: ...

class _RequireOwnerDescriptor(Protocol):
    def __call__(self, handle: object, /) -> int: ...

class _CloseOwnerDescriptor(Protocol):
    def __call__(self, handle: object, /) -> None: ...

class _OwnerDescriptorLeaseKey(Protocol):
    def __call__(self, handle: object, /) -> _OwnerResourceKey: ...

def _build_owner_resource_coordinator(
    *, specs: tuple[_OwnerPayloadSpec[object, object], ...],
) -> tuple[
    _OpenOwnerDirectory, _RequireOwnerDescriptor,
    _CloseOwnerDescriptor, _OwnerDescriptorLeaseKey,
    _ClaimOwnerResources, _ReleaseOwnerResources,
    _RegisterOwnerForkParticipant, _OwnerLifecycleSection,
    Callable[[], None], Callable[[], None], Callable[[], None],
]:
    """Own open, claim, release, GC and fork in one synchronized closure.

    One private ``RLock`` guards the complete open-generation table, lease
    table and fork-participant list. ``open`` alone constructs handle objects
    (all handle dataclasses have
    ``init=False``), uses ``O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC``, records a
    monotonic generation and frozen fstat identity, installs an idempotent
    handle finalizer immediately, and keeps the entry for the process lifetime.
    Construction derives every exact ``_OwnerChildDisposable`` concrete from
    the payload specs and proves it is slotted, identity-equality and
    weak-referenceable by installing/detaching a probe finalizer; a newly added
    non-weakrefable child type fails before any descriptor opens.
    Thus an exception or fork between open and token mint still has an owner.
    ``require`` checks exact handle type, PID, generation, live state, FD number
    and current fstat identity; raw OSError becomes
    ``OwnerCapabilityFault(FORKED_PROCESS, not_established)``. ``close`` is
    idempotent, closes once and permanently tombstones the generation. Reusing
    the numeric FD creates a new generation and cannot revive a stale wrapper.
    ``lease_key`` returns
    ("posix_open_generation", creator_pid, generation).

    ``claim`` validates and deduplicates every resource, then performs the
    absent-check plus lease installation as one locked transition. Two threads
    claiming one generation therefore yield exactly one claim and one typed
    ``RESOURCE_ALREADY_OWNED``. ``release`` is idempotent and atomically drops
    the lease, closes/tombstones each generation and detaches its handle
    finalizer. A failed token mint calls this same rollback before returning.

    The three fork callbacks are registered together. ``before`` acquires the
    coordinator lock, excluding open/claim/release and waiting for every active
    payload borrow; the parent callback releases it. The source-derived
    transitive borrow-call graph forbids direct, helper, alias, callback and
    unresolved process-creation edges and forbids payload escape from inside an
    owner borrow, avoiding same-thread reentrant fork. The child callback closes
    **every** live generation, including unclaimed
    open-before-mint handles, records whether disposal failed, invokes every
    registered token participant while no transition can race, clears leases,
    and replaces the inherited lock before return. Participant order is frozen:
    descriptors close first, then token finalizers detach and payload entries
    become provenance-only fork tombstones. No independent descriptor child hook
    or token-only sweep exists.
    """
    ...

@dataclass(slots=True, weakref_slot=True, eq=False, init=False)
class _PosixOpenedDirectoryHandle:
    descriptor: int
    creator_pid: int
    owner_kind: OwnerCapabilityKind
    open_generation: int
    opened_identity: _OpenedDescriptorIdentity

    def require_current_process_descriptor(self) -> int:
        return _require_owner_descriptor(self)

    def owner_resource_lease_key(self) -> _OwnerResourceKey:
        return _owner_descriptor_lease_key(self)

    def close_owner_resource(self) -> None:
        _close_owner_descriptor(self)

class PythonRuntimeResolutionHop(FoundryAuthorityModel):
    source_root_instance: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]]
    source_relative_path: RootedRelativePath
    target_root_instance: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]]
    target_relative_path: RootedRelativePath
    raw_link_hash: DomainDigest[Literal[DigestDomain.RAW_BLOB]]

class PythonRuntimeRootResolutionStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-root-resolution.v1"]
    environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]
    installation_receipt_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]]
    environment_python_relative_path: RootedRelativePath
    resolved_executable_relative_path: RootedRelativePath
    resolution_chain: tuple[PythonRuntimeResolutionHop, ...]
    runtime_root_identity: PosixRuntimeRootIdentityStatement
    runtime_root_instance: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]]
    recomputed_runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    recomputed_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]]

class PythonRuntimeInstallationStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-installation.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    selected_artifact_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_SELECTED]]
    runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    runtime_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]]
    environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]
    runtime_root_identity: PosixRuntimeRootIdentityStatement
    runtime_root_instance: DomainDigest[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT_TOKEN]]
    installer_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]

class PersistedPythonRuntimeInstallation(FoundryAuthorityModel):
    receipt_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]]
    statement: PythonRuntimeInstallationStatement

@dataclass(frozen=True, slots=True)
class _ResolvedPythonRuntimeInstallationPayload:
    persisted: PersistedPythonRuntimeInstallation
    opened_runtime_root: _PosixOpenedDirectoryHandle

@_fieldless_owner_token
class ResolvedPythonRuntimeInstallation:
    pass

PythonRuntimeInstallationResult = (
    ResolvedPythonRuntimeInstallation
    | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class PythonRuntimeInstallationAuthority(Protocol):
    def attest_after_install(
        self, *, environment_root: Path, admission: PythonRuntimeAdmission,
        environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]],
    ) -> PythonRuntimeInstallationResult: ...
    def resolve_installed_root(
        self, *, environment_root: Path,
        receipt_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]],
        admission: PythonRuntimeAdmission,
    ) -> PythonRuntimeInstallationResult: ...

class ObservedPythonRuntimeStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-observed.v1"]
    environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]
    expected_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    installation_receipt_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]]
    root_resolution_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT]]
    recomputed_runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    observed_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]]
    implementation: Literal["cpython"]
    version: VersionText
    platform_tag: PlatformTagText
    abi_tag: AbiTagText
    files: Annotated[tuple[PythonRuntimeFileRow, ...], Field(min_length=1)]

class PythonRuntimeVerificationReceiptStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.python-runtime-verification.v1"]
    expected_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    installation_receipt_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]]
    recomputed_runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    expected_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]]
    observed_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]]
    root_resolution_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_ROOT]]
    observed_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]]
    verifier_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]
    predicate_class: Literal["independently_reconciled"]

@dataclass(frozen=True, slots=True)
class _VerifiedPythonRuntimePayload:
    observed_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]]
    verification_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]]

@_fieldless_owner_token
class VerifiedPythonRuntime:
    pass

PythonRuntimeObservationResult = (
    VerifiedPythonRuntime | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class PythonRuntimeObserver(Protocol):
    def observe_and_verify(
        self, *, environment_root: Path,
        installation: ResolvedPythonRuntimeInstallation,
        admission: PythonRuntimeAdmission,
    ) -> PythonRuntimeObservationResult: ...

class PythonRuntimeAdmission(FoundryAuthorityModel):
    artifact_role: Literal["python_runtime"]
    version: Literal["3.14"]
    platform_tag: PlatformTagText
    selected_artifact_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_SELECTED]]
    executable_blob_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]]
    expected_runtime_manifest_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    expected_runtime_source_binding_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_BINDING]]
    verifier_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]

class UvExecutableAdmission(FoundryAuthorityModel):
    artifact_role: Literal["uv_executable"]
    version: Literal["0.9.21"]
    platform_tag: PlatformTagText
    selected_artifact_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_SELECTED]]
    executable_blob_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]]
    verifier_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]

ToolchainArtifactAdmission = Annotated[
    PythonRuntimeAdmission | UvExecutableAdmission,
    Field(discriminator="artifact_role"),
]

class TrustPublicKey(FoundryAuthorityModel):
    key_id: Sha256
    algorithm: Literal["ed25519"]
    public_key_encoding: Literal["raw-ed25519-32"]
    public_key_bytes: Annotated[
        bytes, AuthorityScalarRole.EXACT_BYTES, Field(min_length=32, max_length=32)
    ]
    signer_identity: NonEmptyIdentity
    roles: Annotated[tuple[TrustRole, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_identity_and_roles(self) -> TrustPublicKey:
        expected = f"sha256:{hashlib.sha256(self.public_key_bytes).hexdigest()}"
        if self.key_id != expected:
            raise ValueError("key_id must be recomputed from exact raw Ed25519 bytes")
        _require_sorted_unique(tuple(role.value for role in self.roles), label="trust roles")
        return self

class TrustRevocationStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.trust-revocation.v1"]
    key_id: Sha256
    signer_identity: NonEmptyIdentity
    revoked_roles: Annotated[tuple[TrustRole, ...], Field(min_length=1)]
    effective_source_freeze_commit: GitCommitId

    @model_validator(mode="after")
    def validate_revoked_roles(self) -> TrustRevocationStatement:
        _require_sorted_unique(
            tuple(role.value for role in self.revoked_roles), label="revoked roles"
        )
        return self

class PersistedTrustRevocation(FoundryAuthorityModel):
    revocation_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_REVOCATION]]
    statement: TrustRevocationStatement
    signed_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]

class TrustMaterialStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.trust-material.v1"]
    signature_profile: Literal["polisyos.ed25519.detached.v1"]
    keys: Annotated[tuple[TrustPublicKey, ...], Field(min_length=1)]
    revocation_refs: tuple[FoundryRecordRef[Literal[DigestDomain.TRUST_REVOCATION]], ...]
    effective_admission_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_ADMISSION]]

    @model_validator(mode="after")
    def validate_trust_denominator(self) -> TrustMaterialStatement:
        _require_sorted_unique(tuple(key.key_id for key in self.keys), label="trust keys")
        if self.revocation_refs:
            _require_sorted_unique(
                tuple(ref.artifact_id for ref in self.revocation_refs),
                label="revocation refs",
            )
        return self

class PersistedTrustMaterial(FoundryAuthorityModel):
    material_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    statement: TrustMaterialStatement
    signed_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]

class FoundryTrustBootstrapSnapshot(FoundryAuthorityModel):
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    source_freeze_commit: GitCommitId
    binding_index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]]
    trust_materials: Annotated[tuple[PersistedTrustMaterial, ...], Field(min_length=1)]
    revocations: tuple[PersistedTrustRevocation, ...]

    @model_validator(mode="after")
    def validate_bootstrap_denominators(self) -> FoundryTrustBootstrapSnapshot:
        if self.trust_materials:
            _require_sorted_unique(
                tuple(row.material_ref.artifact_id for row in self.trust_materials),
                label="bootstrap trust materials",
            )
        if self.revocations:
            _require_sorted_unique(
                tuple(row.revocation_ref.artifact_id for row in self.revocations),
                label="bootstrap revocations",
            )
        return self

@dataclass(frozen=True, slots=True)
class _VerifiedFoundryTrustBootstrapPayload:
    snapshot: FoundryTrustBootstrapSnapshot

@_fieldless_owner_token
class VerifiedFoundryTrustBootstrap:
    pass

class ProductionDataTrustPolicyStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-trust-policy.v1"]
    appointment_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    custody_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    root_access_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    build_verifier_keys_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    root_identity_profile: Literal["institutional_root_object_v1"]

class PersistedProductionDataTrustPolicy(FoundryAuthorityModel):
    policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]
    statement: ProductionDataTrustPolicyStatement

class DependencyAuthorityRegistryStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-authority-registry.v1"]
    purpose_admissions: tuple[MethodCatalogProfileAdmission, ...]
    toolchain_admissions: tuple[ToolchainArtifactAdmission, ...]
    launcher_profiles: tuple[LauncherProfileSpec, ...]
    foundry_trust_root_keys: Annotated[tuple[TrustPublicKey, ...], Field(min_length=1)]
    production_data_trust_policies: tuple[ProductionDataTrustPolicyStatement, ...]

    @model_validator(mode="after")
    def validate_root_key_denominator(self) -> DependencyAuthorityRegistryStatement:
        _require_sorted_unique(
            tuple(key.key_id for key in self.foundry_trust_root_keys),
            label="Foundry root keys",
        )
        return self

class ResolvedTrustKey(FoundryAuthorityModel):
    key_id: Sha256
    signer_identity: NonEmptyIdentity
    selected_role: TrustRole

class GitCommitRelation(StrEnum):
    ANCESTOR = "ancestor"
    EQUAL = "equal"
    DESCENDANT = "descendant"
    INCOMPARABLE = "incomparable"

class RevocationCutoffDisposition(FoundryAuthorityModel):
    revocation_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_REVOCATION]]
    relation_to_source_cutoff: GitCommitRelation
    status: Literal["effective", "future", "not_established"]

    @model_validator(mode="after")
    def validate_relation_status(self) -> RevocationCutoffDisposition:
        expected = {
            GitCommitRelation.ANCESTOR: "effective",
            GitCommitRelation.EQUAL: "effective",
            GitCommitRelation.DESCENDANT: "future",
            GitCommitRelation.INCOMPARABLE: "not_established",
        }[self.relation_to_source_cutoff]
        if self.status != expected:
            raise ValueError("revocation status does not match Git ancestry")
        return self

class GitCommitAncestryAuthority(Protocol):
    def compare(
        self, *, candidate: GitCommitId, source_cutoff: GitCommitId,
    ) -> GitCommitRelation | MissingPredicateEvidence: ...

class TrustResolutionReceiptStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.trust-resolution.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    source_freeze_commit: GitCommitId
    trust_policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]
    required_role: TrustRole
    trust_material_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]]
    eligible_keys: Annotated[tuple[ResolvedTrustKey, ...], Field(min_length=1)]
    revocation_dispositions: tuple[RevocationCutoffDisposition, ...]
    verifier_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]

    @model_validator(mode="after")
    def require_comparable_cutoff(self) -> TrustResolutionReceiptStatement:
        if any(row.status == "not_established" for row in self.revocation_dispositions):
            raise ValueError("a positive trust receipt cannot contain incomparable revocation")
        _require_sorted_unique(
            tuple(row.key_id for row in self.eligible_keys), label="eligible trust keys"
        )
        if any(row.selected_role != self.required_role for row in self.eligible_keys):
            raise ValueError("eligible key role must equal the requested trust role")
        if self.revocation_dispositions:
            _require_sorted_unique(
                tuple(row.revocation_ref.artifact_id for row in self.revocation_dispositions),
                label="revocation dispositions",
            )
        return self

class PersistedTrustResolutionReceipt(FoundryAuthorityModel):
    receipt_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_RESOLUTION]]
    statement: TrustResolutionReceiptStatement

@dataclass(frozen=True, slots=True)
class _ResolvedFoundryTrustPayload:
    receipt: PersistedTrustResolutionReceipt
    verifier: Ed25519Verifier

@_fieldless_owner_token
class ResolvedFoundryTrust:
    pass

TrustResolutionResult = (
    ResolvedFoundryTrust | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class FoundryTrustResolver(Protocol):
    def resolve(
        self, *, policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]],
        required_role: TrustRole,
    ) -> TrustResolutionResult: ...

def _build_sealed_foundry_trust_resolver(
    *, bootstrap: _VerifiedFoundryTrustBootstrapPayload,
    ancestry: GitCommitAncestryAuthority,
) -> _ProductionFoundryTrustResolver: ...

class ProductionDataInputAppointmentStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-appointment.v1"]
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    appointed_root: ExternalAuthorityRef[Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]]
    manifest_relative_path: Literal["manifest.json"]
    expected_manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]
    appointed_custodian: ExternalAuthorityRef[Literal[ExternalAuthorityKind.PRODUCTION_DATA_CUSTODIAN]]
    custody_statement_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_CUSTODY]]
    trust_policy_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_POLICY]]

class ProductionDataCustodyStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-custody.v1"]
    institutional_root: ExternalAuthorityRef[Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]]
    appointed_custodian: ExternalAuthorityRef[Literal[ExternalAuthorityKind.PRODUCTION_DATA_CUSTODIAN]]
    manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]
    access_mode: Literal["read_only"]
    writer_access_disposition: Literal["denied"]

@dataclass(frozen=True, slots=True)
class _VerifiedProductionDataAppointmentPayload:
    appointment_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    custody_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    appointment_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_APPOINTMENT]]
    custody_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_CUSTODY]]
    appointment_statement: ProductionDataInputAppointmentStatement
    custody_statement: ProductionDataCustodyStatement

@_fieldless_owner_token
class VerifiedProductionDataAppointment:
    pass

ProductionDataAppointmentResolutionResult = (
    VerifiedProductionDataAppointment
    | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class ProductionDataAppointmentAuthority(Protocol):
    def resolve(
        self, *, source_authority: CanonicalFoundrySourceAuthority,
        capsule: PersistedFoundryDependencyAuthorityCapsule,
        signed_graph: VerifiedCapsuleSignedGraph,
    ) -> ProductionDataAppointmentResolutionResult: ...

class ProductionDataMountResolutionStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-mount.v1"]
    appointment_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_APPOINTMENT]]
    institutional_root: ExternalAuthorityRef[Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]]
    requested_root_token: DomainDigest[Literal[DigestDomain.ROOT_MOUNT_REQUEST]]
    access_mode: Literal["read_only"]

@dataclass(slots=True, weakref_slot=True, eq=False, init=False)
class _InstitutionalRootHandle:
    descriptor: int
    creator_pid: int
    owner_kind: Literal[OwnerCapabilityKind.PRODUCTION_MOUNT]
    open_generation: int
    opened_identity: _OpenedDescriptorIdentity

    def require_current_process_descriptor(self) -> int:
        return _require_owner_descriptor(self)

    def owner_resource_lease_key(self) -> _OwnerResourceKey:
        return _owner_descriptor_lease_key(self)

    def close_owner_resource(self) -> None:
        _close_owner_descriptor(self)

@dataclass(frozen=True, slots=True)
class _ResolvedProductionDataMountPayload:
    receipt_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]]
    statement: ProductionDataMountResolutionStatement
    opened_root_handle: _InstitutionalRootHandle

@_fieldless_owner_token
class ResolvedProductionDataMount:
    pass

ProductionDataMountResolutionResult = (
    ResolvedProductionDataMount | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class ProductionDataMountResolver(Protocol):
    def resolve(
        self, *, requested_root: Path,
        appointment: VerifiedProductionDataAppointment,
    ) -> ProductionDataMountResolutionResult: ...

    def read_manifest(
        self, *, mount: ResolvedProductionDataMount,
    ) -> (
        ProductionDataManifestInput
        | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
    ): ...

class ProductionDataRootAccessChallenge(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.root-access-challenge.v1"]
    request_ref: FoundryRecordRef[Literal[DigestDomain.RESOLUTION_REQUEST]]
    challenge_nonce: DomainDigest[Literal[DigestDomain.ROOT_NONCE]]
    expected_root: ExternalAuthorityRef[Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]]
    expected_manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]
    mount_resolution_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]]

class RootAccessAttestationStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.root-access-attestation.v1"]
    challenge_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_CHALLENGE]]
    request_ref: FoundryRecordRef[Literal[DigestDomain.RESOLUTION_REQUEST]]
    challenge_nonce: DomainDigest[Literal[DigestDomain.ROOT_NONCE]]
    institutional_root: ExternalAuthorityRef[Literal[ExternalAuthorityKind.INSTITUTIONAL_ROOT]]
    observed_manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]
    mount_resolution_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_MOUNT_RESOLUTION]]
    access_mode: Literal["read_only"]
    writer_access_disposition: Literal["denied"]

@dataclass(frozen=True, slots=True)
class _VerifiedProductionDataRootAccessPayload:
    statement: RootAccessAttestationStatement
    attestation_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]]
    signed_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    predicate_class: Literal["independently_reconciled"]

@_fieldless_owner_token
class VerifiedProductionDataRootAccess:
    pass

RootAccessAttestationResult = (
    VerifiedProductionDataRootAccess
    | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class ProductionDataRootAccessAttestor(Protocol):
    def attest(
        self, *, mount: ResolvedProductionDataMount,
        challenge: ProductionDataRootAccessChallenge,
    ) -> RootAccessAttestationResult: ...

class ExactSignedArtifactEvidenceStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.signed-artifact-evidence.v1"]
    signed_blob_bytes: ExactBytes
    exact_manifest_bytes: ExactBytes
    detached_signature_bytes: ExactBytes
    # Key id, signer identity and profile are parsed from the detached-signature
    # bytes; this statement carries no caller-supplied duplicate authority field.

class SourceAuthorityVerificationBasis(FoundryAuthorityModel):
    kind: Literal["source_authority"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]

class ResolvedTrustVerificationBasis(FoundryAuthorityModel):
    kind: Literal["resolved_trust"]
    trust_resolution_receipt_ref: FoundryRecordRef[Literal[DigestDomain.TRUST_RESOLUTION]]

SignedRecordVerificationBasis = Annotated[
    SourceAuthorityVerificationBasis | ResolvedTrustVerificationBasis,
    Field(discriminator="kind"),
]

class SignedFoundryRecordBindingStatement(FoundryAuthorityModel, Generic[D_co]):
    schema_version: Literal["polisyos.foundry.signed-record-binding.v1"]
    record_ref: FoundryRecordRef[D_co]
    signed_evidence_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_EVIDENCE]]
    required_role: TrustRole
    verification_basis: SignedRecordVerificationBasis
    verifier_provenance_ref: FoundryRecordRef[Literal[DigestDomain.VERIFIER_PROVENANCE]]

    @model_validator(mode="after")
    def validate_bootstrap_direction(self) -> SignedFoundryRecordBindingStatement[D_co]:
        source_basis = self.verification_basis.kind == "source_authority"
        if (self.required_role == TrustRole.FOUNDRY_TRUST_ROOT) != source_basis:
            raise ValueError("only Foundry trust-root records use source-authority verification")
        return self

class PersistedSignedFoundryRecordBinding(FoundryAuthorityModel, Generic[D_co]):
    binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    statement: SignedFoundryRecordBindingStatement[D_co]

class SignedRecordBindingIndexStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.signed-binding-index.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    binding_refs: Annotated[
        tuple[FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]], ...],
        Field(min_length=1),
    ]

class PersistedSignedRecordBindingIndex(FoundryAuthorityModel):
    index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]]
    statement: SignedRecordBindingIndexStatement

@dataclass(frozen=True, slots=True)
class _VerifiedSignedFoundryRecordPayload:
    record_domain: DigestDomain
    binding: PersistedSignedFoundryRecordBinding[DigestDomain]
    exact_record_bytes: ExactBytes

@_fieldless_owner_token
class VerifiedSignedFoundryRecord:
    pass

@dataclass(frozen=True, slots=True)
class _VerifiedSignedGraphRecord:
    record_domain: DigestDomain
    binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    record: VerifiedSignedFoundryRecord

@dataclass(frozen=True, slots=True)
class _VerifiedCapsuleSignedGraphPayload:
    index: PersistedSignedRecordBindingIndex
    verified_records: tuple[_VerifiedSignedGraphRecord, ...]

@_fieldless_owner_token
class VerifiedCapsuleSignedGraph:
    pass

SignedRecordVerificationResult = (
    VerifiedSignedFoundryRecord
    | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

TrustBootstrapResult = (
    VerifiedFoundryTrustBootstrap
    | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

class FoundryBootstrapEvidencePort(Protocol):
    """Read-only CAS transport; it carries no trust or positive predicate."""
    def load_capsule_raw(self) -> PersistedFoundryDependencyAuthorityCapsule: ...
    def load_binding_index_raw(
        self, *, index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]],
    ) -> PersistedSignedRecordBindingIndex: ...
    def load_binding_raw(
        self, *, binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]],
    ) -> PersistedSignedFoundryRecordBinding[DigestDomain]: ...
    def load_exact_evidence_raw(
        self, *, evidence_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_EVIDENCE]],
    ) -> ExactSignedArtifactEvidenceStatement: ...

class FoundrySourceTrustBootstrapper(Protocol):
    def bootstrap(
        self, *, source_authority: CanonicalFoundrySourceAuthority,
        evidence: FoundryBootstrapEvidencePort,
    ) -> TrustBootstrapResult: ...

class _ProductionFoundrySourceTrustBootstrapper(
    _OwnerBoundaryBase, FoundrySourceTrustBootstrapper
): ...

class FileSystemCASFoundryBootstrapEvidencePort(FoundryBootstrapEvidencePort):
    def __init__(self, *, store: FileSystemCAS, capsule_index_path: Path) -> None: ...

def _open_source_trust_bootstrapper() -> _ProductionFoundrySourceTrustBootstrapper: ...
class _ProductionGitCommitAncestryAuthority(
    _OwnerBoundaryBase, GitCommitAncestryAuthority
): ...
def _open_git_commit_ancestry_authority(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
) -> _ProductionGitCommitAncestryAuthority: ...

class CanonicalSignedRecordRepository(Protocol):
    """Exact signed triples plus the complete content-bound binding graph."""
    def import_and_bind(
        self, *, record_ref: FoundryRecordRef[DigestDomain],
        evidence: ExactSignedArtifactEvidenceStatement,
        required_role: TrustRole,
        verification_basis: SignedRecordVerificationBasis,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> SignedRecordVerificationResult: ...

    def persist_binding_index(
        self, *, source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]],
        bindings: Sequence[PersistedSignedFoundryRecordBinding[DigestDomain]],
    ) -> PersistedSignedRecordBindingIndex: ...

    def load_and_verify_binding(
        self, *, binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]],
        expected_record_domain: DigestDomain,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> SignedRecordVerificationResult: ...

    def verify_capsule_signed_graph(
        self, *, capsule: PersistedFoundryDependencyAuthorityCapsule,
        source_authority: CanonicalFoundrySourceAuthority,
    ) -> VerifiedCapsuleSignedGraph | AuthorityPredicateFailure: ...

class FileSystemCASSignedRecordRepository(
    _OwnerBoundaryBase, CanonicalSignedRecordRepository
):
    # The sole ArtifactVerifier is sealed inside ResolvedFoundryTrust by the
    # canonical trust resolver; it is never a constructor argument here.
    def __init__(self, *, store: FileSystemCAS, trust_resolver: FoundryTrustResolver) -> None: ...

class FoundryDependencyAuthorityCapsuleStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-capsule.v1"]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    profile_admission_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_ADMISSION]]
    appointment_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_APPOINTMENT]]
    signed_binding_index_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_BINDING_INDEX]]
    environment_receipt_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]
    selected_artifact_refs: tuple[FoundryRecordRef[Literal[DigestDomain.SELECTED_DISTRIBUTION]], ...]
    build_lineage_refs: tuple[FoundryRecordRef[Literal[DigestDomain.BUILD_LINEAGE]], ...]
    trust_material_refs: tuple[FoundryRecordRef[Literal[DigestDomain.TRUST_MATERIAL]], ...]

    @model_validator(mode="after")
    def validate_graph_denominators(self) -> FoundryDependencyAuthorityCapsuleStatement:
        for label, refs in (
            ("selected artifacts", self.selected_artifact_refs),
            ("build lineages", self.build_lineage_refs),
            ("capsule trust materials", self.trust_material_refs),
        ):
            if refs:
                _require_sorted_unique(tuple(ref.artifact_id for ref in refs), label=label)
        return self

class PersistedFoundryDependencyAuthorityCapsule(FoundryAuthorityModel):
    capsule_ref: FoundryRecordRef[Literal[DigestDomain.CAPSULE]]
    statement: FoundryDependencyAuthorityCapsuleStatement

class FoundryDependencyAuthorityEvidenceRepository(Protocol):
    def load_capsule(self) -> PersistedFoundryDependencyAuthorityCapsule: ...
    def signed_records(self) -> CanonicalSignedRecordRepository: ...
    def read_blob(self, *, record_ref: FoundryRecordRef[DigestDomain]) -> bytes: ...

class ArtifactStoreFoundryDependencyAuthorityRepository(
    FoundryDependencyAuthorityEvidenceRepository
):
    def __init__(
        self, *, store: ArtifactStore,
        signed_records: CanonicalSignedRecordRepository,
        capsule_index_path: Path,
    ) -> None: ...

def _open_production_dependency_authority_repository(
    *, environment_root: Path,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
    trust_resolver: FoundryTrustResolver,
) -> ArtifactStoreFoundryDependencyAuthorityRepository: ...

class CanonicalFoundrySourceAuthorityStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.canonical-source-authority.v1"]
    source_freeze_commit: GitCommitId
    source_tree_id: GitTreeId
    profile_registry_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_REGISTRY]]
    authority_registry_ref: FoundryRecordRef[Literal[DigestDomain.AUTHORITY_REGISTRY]]
    digest_registry_ref: FoundryRecordRef[Literal[DigestDomain.DIGEST_REGISTRY]]

@dataclass(frozen=True, slots=True)
class _CanonicalFoundrySourceAuthorityPayload:
    source_root: _PosixOpenedDirectoryHandle
    authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    statement: CanonicalFoundrySourceAuthorityStatement
    digest_registry: DecodedDigestDomainRegistry

    def __post_init__(self) -> None:
        if self.statement.digest_registry_ref != self.digest_registry.registry_ref:
            raise ValueError("source authority and decoded digest registry disagree")

@_fieldless_owner_token
class CanonicalFoundrySourceAuthority:
    pass

class DependencyEnvironmentMarkerStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-environment-marker.v1"]
    environment_creation_nonce: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    python_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]
    python_runtime_installation_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]]
    observed_python_runtime_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_OBSERVED]]
    python_runtime_verification_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]]
    uv_executable_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_EXECUTABLE]]
    derived_uv_argv: DomainDigest[Literal[DigestDomain.DERIVED_UV_ARGV]]
    instance_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_INSTANCE]]

class DependencyProfileEnvironmentStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.dependency-environment.v1"]
    admission_ref: FoundryRecordRef[Literal[DigestDomain.PROFILE_ADMISSION]]
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    appointment_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_APPOINTMENT]]
    sync_root_access_ref: FoundryRecordRef[Literal[DigestDomain.ROOT_ACCESS]]
    sync_root_access_binding_ref: FoundryRecordRef[Literal[DigestDomain.SIGNED_RECORD_BINDING]]
    python_runtime_installation_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_INSTALLATION]]
    python_runtime_verification_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME_VERIFICATION]]
    observed_distributions: tuple[InstalledDistributionIdentity, ...]
    stable_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_STABLE]]
    instance_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_INSTANCE]]
    marker_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_MARKER]]

class DependencyProfileEnvironmentReceipt(FoundryAuthorityModel):
    receipt_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]
    statement: DependencyProfileEnvironmentStatement
    predicate_class: Literal["recomputed"]

class ResolvedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    status: Literal["resolved"]
    admission: MethodCatalogProfileAdmission
    declaration: MethodCatalogDependencyProfileDeclaration
    marker_environment: tuple[tuple[EnvironmentKeyText, EnvironmentValueText], ...]
    distributions: tuple[LockedDistributionIdentity, ...]
    distribution_set: DomainDigest[Literal[DigestDomain.DISTRIBUTION_SET]]
    stable_content_set: DomainDigest[Literal[DigestDomain.CONTENT_SET_STABLE]]
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    production_data_manifest_ref: FoundryRecordRef[Literal[DigestDomain.PRODUCTION_MANIFEST]]

class ProductionDataManifestPresent(FoundryAuthorityModel):
    kind: Literal["present"]
    exact_bytes: ExactBytes

class ProductionDataManifestStatement(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.production-data-manifest.v1"]
    exact_manifest_bytes: ExactBytes

class ProductionDataManifestUnavailable(FoundryAuthorityModel):
    kind: Literal["unavailable"]
    cause: Literal["missing", "unreadable"]

ProductionDataManifestInput = Annotated[
    ProductionDataManifestPresent | ProductionDataManifestUnavailable,
    Field(discriminator="kind"),
]

class DomainScalar(FoundryAuthorityModel):
    domain: ScalarDomain
    value: IdentityText

class MissingPredicateEvidence(FoundryAuthorityModel):
    kind: Literal["not_established"]
    predicate_id: AuthorityPredicateId
    code: AuthorityFailureCode
    missing_domains: Annotated[tuple[DigestDomain, ...], Field(min_length=1)]
    predicate_class: Literal["not_established"]

class ProductionDataManifestMissingFailure(FoundryAuthorityModel):
    kind: Literal["production_data_manifest_missing"]
    predicate_id: Literal[AuthorityPredicateId.PRODUCTION_MANIFEST]
    code: Literal[AuthorityFailureCode.MANIFEST_MISSING]
    cause: Literal["missing", "unreadable"]
    predicate_class: Literal["not_established"]

class DigestPredicateMismatch(FoundryAuthorityModel):
    kind: Literal["digest_mismatch"]
    predicate_id: AuthorityPredicateId
    code: AuthorityFailureCode
    expected: DomainDigest[DigestDomain]
    observed: DomainDigest[DigestDomain]
    predicate_class: Literal["recomputed", "independently_reconciled"]

class ScalarPredicateMismatch(FoundryAuthorityModel):
    kind: Literal["scalar_mismatch"]
    predicate_id: AuthorityPredicateId
    code: AuthorityFailureCode
    expected: DomainScalar
    observed: DomainScalar
    predicate_class: Literal["recomputed", "independently_reconciled"]

AuthorityPredicateFailure = Annotated[
    MissingPredicateEvidence | ProductionDataManifestMissingFailure
    | DigestPredicateMismatch | ScalarPredicateMismatch,
    Field(discriminator="kind"),
]

class DependencyProfileReconciliationPass(FoundryAuthorityModel):
    status: Literal["pass"]
    profile_id: IdentityText
    stable_closure: DomainDigest[Literal[DigestDomain.DEPENDENCY_CLOSURE]]
    environment_receipt_ref: FoundryRecordRef[Literal[DigestDomain.ENVIRONMENT_RECEIPT]]
    predicate_class: Literal["independently_reconciled"]

class DependencyProfileReconciliationFail(FoundryAuthorityModel):
    status: Literal["fail"]
    profile_id: IdentityText
    failures: Annotated[tuple[AuthorityPredicateFailure, ...], Field(min_length=1)]

DependencyProfileReconciliation = Annotated[
    DependencyProfileReconciliationPass | DependencyProfileReconciliationFail,
    Field(discriminator="status"),
]

class MethodCatalogDependencyAuthorityRequest(FoundryAuthorityModel):
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    expected_source_freeze_commit: GitCommitId
    production_data_root: AbsoluteRequestPath
    environment_root: AbsoluteRequestPath

class DependencyAuthorityPreSourceRequestStatement(FoundryAuthorityModel):
    schema_version: Literal[
        "polisyos.foundry.dependency-pre-source-request.v1"
    ]
    authority_purpose: Literal["n8_method_catalog_reconstruction"]
    expected_source_freeze_commit: GitCommitId
    production_data_request_token: DomainDigest[Literal[DigestDomain.ROOT_MOUNT_REQUEST]]
    environment_request_token: DomainDigest[Literal[DigestDomain.ENVIRONMENT_INSTANCE]]

class DependencyAuthorityResolvedSourceRequestStatement(FoundryAuthorityModel):
    schema_version: Literal[
        "polisyos.foundry.dependency-resolved-source-request.v1"
    ]
    pre_source_request: DependencyAuthorityPreSourceRequestStatement
    expected_source_tree_id: GitTreeId

class NegativeDependencyAuthorityResultKind(StrEnum):
    SOURCE_REJECTED = "source_rejected"
    SOURCE_NOT_ESTABLISHED = "source_not_established"
    RUNTIME_CUTOFF_NOT_ESTABLISHED = "runtime_cutoff_not_established"

@dataclass(frozen=True, slots=True)
class SourceBootstrapFailureStageSpec:
    result_kind: NegativeDependencyAuthorityResultKind
    status: OwnerCapabilityFaultDisposition
    predicate_id: Literal[AuthorityPredicateId.SOURCE_FREEZE]
    failure_code: AuthorityFailureCode
    request_shape: Literal["pre_source", "resolved_source"]
    source_ref_rule: Literal["forbidden"]
    persistence: Literal["not_established"]
    persistence_capability: Literal[
        "owner_resolved_resolution_receipt_store"
    ]
    persistence_capability_state: Literal["absent/unallocated"]

SOURCE_BOOTSTRAP_FAILURE_STAGES = MappingProxyType({
    NegativeDependencyAuthorityResultKind.SOURCE_REJECTED:
        SourceBootstrapFailureStageSpec(
            result_kind=NegativeDependencyAuthorityResultKind.SOURCE_REJECTED,
            status=OwnerCapabilityFaultDisposition.REJECTED,
            predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
            failure_code=AuthorityFailureCode.SOURCE_FREEZE_MISMATCH,
            request_shape="resolved_source",
            source_ref_rule="forbidden",
            persistence="not_established",
            persistence_capability="owner_resolved_resolution_receipt_store",
            persistence_capability_state="absent/unallocated",
        ),
    NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED:
        SourceBootstrapFailureStageSpec(
            result_kind=NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED,
            status=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
            predicate_id=AuthorityPredicateId.SOURCE_FREEZE,
            failure_code=AuthorityFailureCode.SOURCE_NOT_ESTABLISHED,
            request_shape="pre_source",
            source_ref_rule="forbidden",
            persistence="not_established",
            persistence_capability="owner_resolved_resolution_receipt_store",
            persistence_capability_state="absent/unallocated",
        ),
})

@dataclass(frozen=True, slots=True)
class PostSourceNegativeAuthorityStageSpec:
    result_kind: Literal[
        NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED
    ]
    status: Literal[OwnerCapabilityFaultDisposition.NOT_ESTABLISHED]
    predicate_id: AuthorityPredicateId
    required_branch_shape: Literal["not_established_only"]
    source_ref_rule: Literal["required"]
    persistence: Literal["not_established"]
    persistence_capability: Literal[
        "owner_resolved_resolution_receipt_store"
    ]
    persistence_capability_state: Literal["absent/unallocated"]

POST_SOURCE_NEGATIVE_AUTHORITY_STAGES = MappingProxyType({
    NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED:
        PostSourceNegativeAuthorityStageSpec(
            result_kind=NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED,
            status=OwnerCapabilityFaultDisposition.NOT_ESTABLISHED,
            predicate_id=AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF,
            required_branch_shape="not_established_only",
            source_ref_rule="required", persistence="not_established",
            persistence_capability="owner_resolved_resolution_receipt_store",
            persistence_capability_state="absent/unallocated",
        ),
})

class NegativeResultPersistenceDisposition(FoundryAuthorityModel):
    status: Literal["not_established"]
    missing_capability: Literal["owner_resolved_resolution_receipt_store"]
    missing_capability_state: Literal["absent/unallocated"]

class CandidateRuntimeEvidenceNotRequested(FoundryAuthorityModel):
    status: Literal["not_requested"]
    reason: Literal["owner_enforced_runtime_subtree_cutoff_absent"]

class CandidateRuntimeEvidencePresent(FoundryAuthorityModel):
    status: Literal["present"]
    evidence_ref: FoundryRecordRef[Literal[DigestDomain.TOOLCHAIN_RUNTIME]]

RuntimeCandidateEvidenceDisposition = Annotated[
    CandidateRuntimeEvidenceNotRequested | CandidateRuntimeEvidencePresent,
    Field(discriminator="status"),
]

class SourceFreezeRejectedPredicate(FoundryAuthorityModel):
    status: Literal["rejected"]
    predicate_id: Literal[AuthorityPredicateId.SOURCE_FREEZE]
    predicate_class: Literal["recomputed"]
    failure_code: Literal[AuthorityFailureCode.SOURCE_FREEZE_MISMATCH]
    expected_source_freeze_commit: GitCommitId
    expected_source_tree_id: GitTreeId
    owner_observed_head_commit: GitCommitId
    owner_observed_tree_id: GitTreeId
    observation_producer: Literal["canonical_module_git_recompute_v1"]

    @model_validator(mode="after")
    def require_actual_source_difference(self) -> SourceFreezeRejectedPredicate:
        if (
            self.expected_source_freeze_commit == self.owner_observed_head_commit
            and self.expected_source_tree_id == self.owner_observed_tree_id
        ):
            raise ValueError("source rejection requires a commit or tree mismatch")
        return self

class SourceFreezeUnestablishedPredicate(FoundryAuthorityModel):
    status: Literal["not_established"]
    predicate_id: Literal[AuthorityPredicateId.SOURCE_FREEZE]
    predicate_class: Literal["not_established"]
    failure_code: Literal[AuthorityFailureCode.SOURCE_NOT_ESTABLISHED]
    missing_domains: tuple[Literal[DigestDomain.CANONICAL_SOURCE]]

class RuntimeCutoffUnestablishedPredicate(FoundryAuthorityModel):
    status: Literal["not_established"]
    predicate_id: Literal[AuthorityPredicateId.RUNTIME_SUBTREE_CUTOFF]
    predicate_class: Literal["not_established"]
    failure_code: Literal[
        AuthorityFailureCode.RUNTIME_SUBTREE_CUTOFF_NOT_ESTABLISHED
    ]
    missing_capability: Literal["owner_enforced_runtime_subtree_cutoff"]
    missing_capability_state: Literal["absent/unallocated"]
    candidate_runtime_evidence: RuntimeCandidateEvidenceDisposition

class SourceRejectedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    result_kind: Literal[NegativeDependencyAuthorityResultKind.SOURCE_REJECTED]
    status: Literal["rejected"]
    persistence: NegativeResultPersistenceDisposition
    request: DependencyAuthorityResolvedSourceRequestStatement
    failure: SourceFreezeRejectedPredicate
    @model_validator(mode="after")
    def validate_stage(self) -> SourceRejectedMethodCatalogDependencyProfile:
        validate_source_bootstrap_failure(self)
        return self

class SourceUnestablishedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    result_kind: Literal[NegativeDependencyAuthorityResultKind.SOURCE_NOT_ESTABLISHED]
    status: Literal["not_established"]
    persistence: NegativeResultPersistenceDisposition
    request: DependencyAuthorityPreSourceRequestStatement
    failure: SourceFreezeUnestablishedPredicate
    @model_validator(mode="after")
    def validate_stage(self) -> SourceUnestablishedMethodCatalogDependencyProfile:
        validate_source_bootstrap_failure(self)
        return self

CanonicalFoundrySourceResolution = (
    CanonicalFoundrySourceAuthority
    | SourceRejectedMethodCatalogDependencyProfile
    | SourceUnestablishedMethodCatalogDependencyProfile
)

class RuntimeCutoffPreflightRefusal(FoundryAuthorityModel):
    schema_version: Literal["polisyos.foundry.runtime-cutoff-preflight-refusal.v1"]
    persistence: NegativeResultPersistenceDisposition
    source_authority_ref: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]]
    request: DependencyAuthorityResolvedSourceRequestStatement
    failure: RuntimeCutoffUnestablishedPredicate

class UnestablishedMethodCatalogDependencyProfile(FoundryAuthorityModel):
    result_kind: Literal[
        NegativeDependencyAuthorityResultKind.RUNTIME_CUTOFF_NOT_ESTABLISHED
    ]
    status: Literal["not_established"]
    preflight_refusal: RuntimeCutoffPreflightRefusal

MethodCatalogDependencyAuthorityResult = Annotated[
    SourceRejectedMethodCatalogDependencyProfile
    | SourceUnestablishedMethodCatalogDependencyProfile
    | UnestablishedMethodCatalogDependencyProfile,
    Field(discriminator="result_kind"),
]
DependencyProfileResolutionFailure = MethodCatalogDependencyAuthorityResult

SourceBootstrapFailureResult = (
    SourceRejectedMethodCatalogDependencyProfile
    | SourceUnestablishedMethodCatalogDependencyProfile
)

def validate_source_bootstrap_failure(
    result: SourceBootstrapFailureResult,
) -> None:
    """Validate the pre-registry grammar without consulting failed source.

    The two frozen bootstrap variants bind the canonical-module Git observer,
    exact source predicate/code and common persistence gap. The rejected
    variant requires a resolved-source request with the owner-derived expected
    tree; the not-established variant accepts only the pre-source request and
    therefore cannot fabricate a tree when the Git root/commit is unavailable.
    No registry ref or ambient registry bytes are legal here; missing,
    unreadable or corrupt registry data is represented by the typed
    source-not-established variant instead of trying to decode that registry.
    """
    ...

def validate_negative_dependency_authority_stage(
    result: UnestablishedMethodCatalogDependencyProfile, *,
    source_authority: _CanonicalFoundrySourceAuthorityPayload,
) -> None:
    """Recompute the post-source stage from the owner-bound decoded registry.

    Use only ``source_authority.digest_registry``, whose canonical bytes/hash
    and ref were verified before the source capability was minted. Resolve the
    exact ``NotEstablishedOnlyAuthorityPredicateSpec`` selected by the stage
    row and its not-established requirement. Ambient files and an opaque
    source ref are not registry inputs; changing them after capability mint
    cannot alter this classification.

    Require the failure DTO's code and evidence to satisfy that discriminated
    requirement, predicate-spec ref, source-ref and common persistence rules.
    The registry row must have branch shape ``not_established_only``; a
    bidirectional/satisfied/rejected cutoff row is structurally inadmissible.
    Candidate runtime evidence is preserved but never changes the result.
    """
    ...

def build_runtime_cutoff_refusal(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
    request: DependencyAuthorityResolvedSourceRequestStatement,
    candidate_runtime_evidence: RuntimeCandidateEvidenceDisposition,
) -> UnestablishedMethodCatalogDependencyProfile:
    """Build, owner-validate and return the only post-source v1 result."""
    # Construct the strict result, then call
    # validate_negative_dependency_authority_stage(result,
    #     source_authority=source_authority) before it may leave the owner.
    ...

class CanonicalFoundrySourceAuthorityResolver(Protocol):
    def resolve(
        self, *, request: MethodCatalogDependencyAuthorityRequest,
    ) -> CanonicalFoundrySourceResolution: ...

class _ProductionCanonicalFoundrySourceAuthorityResolver(
    _OwnerBoundaryBase, CanonicalFoundrySourceAuthorityResolver
):
    def __init__(
        self, *, bootstrapper: FoundrySourceTrustBootstrapper,
        ancestry: GitCommitAncestryAuthority,
    ) -> None: ...
    def resolve(
        self, *, request: MethodCatalogDependencyAuthorityRequest,
    ) -> CanonicalFoundrySourceResolution: ...

class MethodCatalogDependencyAuthority(Protocol):
    def resolve(
        self, request: MethodCatalogDependencyAuthorityRequest
    ) -> MethodCatalogDependencyAuthorityResult: ...

class _ProductionMethodCatalogDependencyAuthority(
    _OwnerBoundaryBase, MethodCatalogDependencyAuthority
):
    def __init__(
        self, *, source_resolver: _ProductionCanonicalFoundrySourceAuthorityResolver,
        cutoff_authority: _NoRuntimeSubtreeCutoffAuthority,
    ) -> None: ...
    def resolve(
        self, request: MethodCatalogDependencyAuthorityRequest,
    ) -> MethodCatalogDependencyAuthorityResult: ...

class _ProductionFoundryTrustResolver(_OwnerBoundaryBase, FoundryTrustResolver): ...
class _ProductionDataAppointmentAuthority(
    _OwnerBoundaryBase, ProductionDataAppointmentAuthority
): ...
class _ProductionDataMountResolver(
    _OwnerBoundaryBase, ProductionDataMountResolver
): ...
class _ProductionDataRootAccessAttestor(
    _OwnerBoundaryBase, ProductionDataRootAccessAttestor
): ...
class _ProductionPythonRuntimeInstallationAuthority(
    _OwnerBoundaryBase, PythonRuntimeInstallationAuthority
):
    def __init__(
        self, *, cutoff_authority: _NoRuntimeSubtreeCutoffAuthority,
    ) -> None: ...
class _ProductionPythonRuntimeObserver(_OwnerBoundaryBase, PythonRuntimeObserver): ...

@dataclass(frozen=True, slots=True)
class _ResolvedDependencyAuthorityComponentsPayload:
    capsule: PersistedFoundryDependencyAuthorityCapsule
    signed_graph: VerifiedCapsuleSignedGraph
    trust_resolver: _ProductionFoundryTrustResolver
    signed_records: FileSystemCASSignedRecordRepository
    appointments: _ProductionDataAppointmentAuthority
    mounts: _ProductionDataMountResolver
    root_attestor: _ProductionDataRootAccessAttestor
    python_installations: _ProductionPythonRuntimeInstallationAuthority
    python_observer: _ProductionPythonRuntimeObserver

@_fieldless_owner_token
class ResolvedDependencyAuthorityComponents:
    pass

def derive_owner_protocol_concrete_pairs_from_source(
    *, module_file: Path, namespace: Mapping[str, object],
) -> tuple[tuple[type[object], type[object]], ...]:
    """Derive owner pairs without a hand-maintained pair registry.

    A complete AST class graph finds every concrete transitive subclass of
    ``_OwnerBoundaryBase``. Each must have exactly one transitive owner
    ``Protocol`` base implemented in this module, every Protocol method must be
    present with an exactly compatible typed result union, and no Protocol may
    have two production concretes unless its result composition explicitly
    declares that plurality. The live objects are resolved from ``namespace``
    only after the AST denominator is frozen. Missing/extra classes, an owner
    boundary without a Protocol, a Protocol concrete lacking the owner marker,
    or a namespace/source mismatch fails. Sorting is by source-qualified class
    name. Thus deleting a pair declaration is impossible, while adding one
    `_OwnerBoundaryBase` subclass automatically enlarges the denominator.
    """
    ...

_OWNER_PROTOCOL_CONCRETE_PAIRS = derive_owner_protocol_concrete_pairs_from_source(
    module_file=Path(__file__).resolve(), namespace=MappingProxyType(globals()),
)

def validate_owner_payload_annotation_graph(
    payload: object, *,
    spec_by_token: Mapping[type[object], _OwnerPayloadSpec[object, object]],
) -> None:
    """Reject Protocol/object/Any leaves and reconstruct every strict DTO leaf."""
    # Walk dataclass/Pydantic/tuple annotations transitively. Every live leaf
    # must be named in the active OwnerPayloadSpec and have exact concrete type;
    # every persisted leaf must reconstruct under its strict model. Tokens are
    # allowed only where the complete token/spec relation names them.
    ...

def validate_owner_payload_spec_annotation_graph(
    *, spec: _OwnerPayloadSpec[object, object],
    spec_by_kind: Mapping[OwnerCapabilityKind, _OwnerPayloadSpec[object, object]],
) -> None:
    """Resolve every declared path against the real annotated payload graph.

    The implementation uses ``get_type_hints(..., include_extras=True)`` and a
    total TypeVar/Annotated/tuple resolver. Every leaf path must terminate at
    its exact concrete type. Each child-resource leaf must expose the three
    exact owner-resource methods. A dynamic domain path and its bound-ref path
    must both resolve to the same ``DigestDomain`` parameter. For a nested row,
    MANY requires exactly ``tuple[T, ...]`` while SINGLE rejects a sequence;
    token_path must resolve to the registered nested token type and an optional
    expected-domain path to ``DigestDomain``. Missing attributes, ambiguous
    unions, unresolved TypeVars, wrong cardinality and an extra/unused path all
    raise ``TypeError`` at kernel construction, before any token is minted.
    """
    ...

def derive_owner_entrypoint_denominator_from_source(
    *, module_file: Path,
    protocol_concrete_pairs: tuple[tuple[type[object], type[object]], ...],
) -> tuple[OwnerEntrypointSpec, ...]:
    """Derive the denominator independently of wrapping or registration.

    The independent denominator is the union of every method on every declared
    owner Protocol/concrete pair and every additional concrete/module function
    that accepts a token type or calls kernel unwrap. Each joins to an exact
    result union and method-specific fault policy. Missing concrete methods,
    extra consumers, bare exceptions and ambiguous failure unions fail
    derivation. Every unwrap call must be the context expression of a `with`
    statement; a bare call or stored context manager fails. Borrow escape and
    process creation are checked by the separate transitive graph below, not by
    a direct-target keyword scan. In particular the sole runtime-cutoff
    preflight is included even though it accepts no token.
    """
    ...

def derive_owner_borrow_reachability_from_source(
    *, module_file: Path,
    owner_entrypoints: tuple[OwnerEntrypointSpec, ...],
) -> tuple[OwnerBorrowReachability, ...]:
    """Close every call and escape edge reachable while a payload is borrowed.

    Start from each lexical ``with _unwrap_owner_capability(...) as payload``
    body found by the independent AST denominator. Resolve every direct helper,
    method and import alias recursively to a source-qualified callable. Derive
    one row for **every AST node occurrence** reachable in that lexical body,
    including statement, expression, pattern, comprehension, target, context
    and operator nodes. Each row is keyed by an ``AstOccurrenceId`` derived
    from the full ``ast.iter_fields`` ancestry from the synthetic borrow-body
    root: every step records the exact field name and, for sequence-valued
    fields, the child index. Object identity is never a key because operator,
    comparison and context nodes may be spanless singletons reused at multiple
    positions. Source span is optional diagnostic metadata only. Reconstructing
    the AST path from an occurrence ID must select exactly that occurrence.

    Each row is either lowered to every Python evaluation edge it can invoke or
    proved to be a purely syntactic container whose child rows carry all
    evaluation. A deny-by-default evaluator-rule registry covers
    the complete concrete AST node types present in the source; occurrence-row
    and source-AST denominators must be an exact bijection. An unclassified
    node, context or child-evaluation rule fails.

    Lower attribute descriptors, iteration/context, comparison/truth/hash/
    index, formatting, representation and unary/binary protocols through the
    same terminal-edge algebra. Each terminal edge records its exact invocation
    form and operand types. An implicit data-model method is
    either traversed like an explicit call or admitted as ``no_user_dispatch``
    only when the exact built-in operand types are source/type-proven to have no
    Python-level override or callback edge. Exact builtin identity alone is not
    evidence: ``len(x)`` and ``tuple(x)`` remain non-terminal until ``x`` is
    proven, while ``len(exact_builtin_tuple)`` is the control admitted edge.

    This includes dispatch introduced without an expression call: ``if``/
    ``while`` truth, ``for``/async iteration, ``with``/async context, sequence/
    mapping/class patterns, comprehensions, descriptor targets and guards all
    lower through their applicable data-model methods. A callable parameter,
    Protocol/dynamic dispatch, ``getattr``/reflection,
    unresolved import, lambda/closure invocation, unknown descriptor/dunder or
    callback edge is rejected rather than presumed non-forking. The enumerator
    is generic over the complete AST occurrence set, not a hand-maintained list
    of expressions or statements. Adding an ``if``, ``match``, comprehension,
    helper, operator or descriptor therefore enlarges the denominator
    automatically.

    Every reachable callable is rejected if it can invoke ``fork``/``forkpty``
    or a process-spawning subprocess/multiprocessing primitive directly,
    through an alias or through another reachable helper. The borrowed payload
    (or any transitive object obtained from it) may not be returned, yielded,
    captured, assigned to global/nonlocal/attribute/subscript/container state,
    passed to an unresolved callable or kept beyond the lexical ``with``. The
    graph is reconciled to live qualified objects before guards are installed.
    Thus helper→fork, callback→fork, helper-return and callback-store mutations
    fail at import/test time before a capability can be used; a direct-target
    marker is not the gate.
    """
    ...

def install_owner_entrypoint_guards(
    specs: tuple[OwnerEntrypointSpec, ...],
) -> None:
    """Wrap every independently derived method/function with its exact adapter."""
    # The adapter registry is a closed mapping from failure_adapter_id to a
    # builder that receives OwnerCapabilityFault + BoundArguments + the frozen
    # per-parameter OwnerFaultPolicy. It resolves predicate/evidence refs from
    # the bound call and returns only a variant admitted by that target's exact
    # result union. The generic guard never invents persistence; a target may
    # write only through an independently appointed writer in its own ABI.
    # ParamSpec is preserved by _guard_owner_entrypoint.
    ...

_CANONICAL_SOURCE_SPEC: _OwnerPayloadSpec[
    CanonicalFoundrySourceAuthority, _CanonicalFoundrySourceAuthorityPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.CANONICAL_SOURCE,
    token_type=CanonicalFoundrySourceAuthority,
    payload_type=_CanonicalFoundrySourceAuthorityPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("source_root",), _PosixOpenedDirectoryHandle),
    ),
    dynamic_record_domain_path=None, dynamic_record_ref_domain_path=None,
    child_resource_paths=(("source_root",),),
    nested_tokens=(),
)
_RUNTIME_INSTALLATION_SPEC: _OwnerPayloadSpec[
    ResolvedPythonRuntimeInstallation, _ResolvedPythonRuntimeInstallationPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.RUNTIME_INSTALLATION,
    token_type=ResolvedPythonRuntimeInstallation,
    payload_type=_ResolvedPythonRuntimeInstallationPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("opened_runtime_root",), _PosixOpenedDirectoryHandle),
    ),
    dynamic_record_domain_path=None, dynamic_record_ref_domain_path=None,
    child_resource_paths=(("opened_runtime_root",),),
    nested_tokens=(),
)
_VERIFIED_RUNTIME_SPEC: _OwnerPayloadSpec[
    VerifiedPythonRuntime, _VerifiedPythonRuntimePayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.VERIFIED_RUNTIME,
    token_type=VerifiedPythonRuntime, payload_type=_VerifiedPythonRuntimePayload,
    exact_concrete_leaves=(), dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None, child_resource_paths=(),
    nested_tokens=(),
)
_TRUST_BOOTSTRAP_SPEC: _OwnerPayloadSpec[
    VerifiedFoundryTrustBootstrap, _VerifiedFoundryTrustBootstrapPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.TRUST_BOOTSTRAP,
    token_type=VerifiedFoundryTrustBootstrap,
    payload_type=_VerifiedFoundryTrustBootstrapPayload,
    exact_concrete_leaves=(), dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None, child_resource_paths=(),
    nested_tokens=(),
)
_RESOLVED_TRUST_SPEC: _OwnerPayloadSpec[
    ResolvedFoundryTrust, _ResolvedFoundryTrustPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.RESOLVED_TRUST,
    token_type=ResolvedFoundryTrust, payload_type=_ResolvedFoundryTrustPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("verifier",), Ed25519Verifier),
    ),
    dynamic_record_domain_path=None, dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(),
)
_PRODUCTION_APPOINTMENT_SPEC: _OwnerPayloadSpec[
    VerifiedProductionDataAppointment, _VerifiedProductionDataAppointmentPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.PRODUCTION_APPOINTMENT,
    token_type=VerifiedProductionDataAppointment,
    payload_type=_VerifiedProductionDataAppointmentPayload,
    exact_concrete_leaves=(), dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None, child_resource_paths=(),
    nested_tokens=(),
)
_PRODUCTION_MOUNT_SPEC: _OwnerPayloadSpec[
    ResolvedProductionDataMount, _ResolvedProductionDataMountPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.PRODUCTION_MOUNT,
    token_type=ResolvedProductionDataMount,
    payload_type=_ResolvedProductionDataMountPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("opened_root_handle",), _InstitutionalRootHandle),
    ),
    dynamic_record_domain_path=None, dynamic_record_ref_domain_path=None,
    child_resource_paths=(("opened_root_handle",),),
    nested_tokens=(),
)
_ROOT_ACCESS_SPEC: _OwnerPayloadSpec[
    VerifiedProductionDataRootAccess, _VerifiedProductionDataRootAccessPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.ROOT_ACCESS,
    token_type=VerifiedProductionDataRootAccess,
    payload_type=_VerifiedProductionDataRootAccessPayload,
    exact_concrete_leaves=(), dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None, child_resource_paths=(),
    nested_tokens=(),
)
_SIGNED_RECORD_SPEC: _OwnerPayloadSpec[
    VerifiedSignedFoundryRecord, _VerifiedSignedFoundryRecordPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.SIGNED_RECORD,
    token_type=VerifiedSignedFoundryRecord,
    payload_type=_VerifiedSignedFoundryRecordPayload,
    exact_concrete_leaves=(),
    dynamic_record_domain_path=("record_domain",),
    dynamic_record_ref_domain_path=(
        "binding", "statement", "record_ref", "semantic_hash", "domain",
    ),
    child_resource_paths=(),
    nested_tokens=(),
)
_SIGNED_GRAPH_SPEC: _OwnerPayloadSpec[
    VerifiedCapsuleSignedGraph, _VerifiedCapsuleSignedGraphPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.SIGNED_GRAPH,
    token_type=VerifiedCapsuleSignedGraph,
    payload_type=_VerifiedCapsuleSignedGraphPayload,
    exact_concrete_leaves=(), dynamic_record_domain_path=None,
    dynamic_record_ref_domain_path=None, child_resource_paths=(),
    nested_tokens=(
        _OwnerNestedTokenSpec(
            payload_path=("verified_records",),
            cardinality=_OwnerNestedCardinality.MANY,
            token_path=("record",), expected_domain_path=("record_domain",),
            nested_kind=OwnerCapabilityKind.SIGNED_RECORD,
        ),
    ),
)
_RESOLVED_COMPONENTS_SPEC: _OwnerPayloadSpec[
    ResolvedDependencyAuthorityComponents, _ResolvedDependencyAuthorityComponentsPayload
] = _OwnerPayloadSpec(
    kind=OwnerCapabilityKind.RESOLVED_COMPONENTS,
    token_type=ResolvedDependencyAuthorityComponents,
    payload_type=_ResolvedDependencyAuthorityComponentsPayload,
    exact_concrete_leaves=(
        _OwnerPayloadLeafSpec(("trust_resolver",), _ProductionFoundryTrustResolver),
        _OwnerPayloadLeafSpec(("signed_records",), FileSystemCASSignedRecordRepository),
        _OwnerPayloadLeafSpec(("appointments",), _ProductionDataAppointmentAuthority),
        _OwnerPayloadLeafSpec(("mounts",), _ProductionDataMountResolver),
        _OwnerPayloadLeafSpec(("root_attestor",), _ProductionDataRootAccessAttestor),
        _OwnerPayloadLeafSpec(
            ("python_installations",), _ProductionPythonRuntimeInstallationAuthority,
        ),
        _OwnerPayloadLeafSpec(("python_observer",), _ProductionPythonRuntimeObserver),
    ),
    dynamic_record_domain_path=None, dynamic_record_ref_domain_path=None,
    child_resource_paths=(),
    nested_tokens=(
        _OwnerNestedTokenSpec(
            payload_path=("signed_graph",),
            cardinality=_OwnerNestedCardinality.SINGLE,
            token_path=(), expected_domain_path=None,
            nested_kind=OwnerCapabilityKind.SIGNED_GRAPH,
        ),
    ),
)

_OWNER_CAPABILITY_SPECS = (
    _CANONICAL_SOURCE_SPEC, _RUNTIME_INSTALLATION_SPEC, _VERIFIED_RUNTIME_SPEC,
    _TRUST_BOOTSTRAP_SPEC, _RESOLVED_TRUST_SPEC, _PRODUCTION_APPOINTMENT_SPEC,
    _PRODUCTION_MOUNT_SPEC, _ROOT_ACCESS_SPEC, _SIGNED_RECORD_SPEC,
    _SIGNED_GRAPH_SPEC, _RESOLVED_COMPONENTS_SPEC,
)
(
    _open_owner_directory, _require_owner_descriptor,
    _close_owner_descriptor, _owner_descriptor_lease_key,
    _claim_owner_resources, _release_owner_resources,
    _register_owner_fork_participant, _owner_lifecycle_section,
    _before_owner_fork, _after_owner_fork_parent, _after_owner_fork_child,
) = _build_owner_resource_coordinator(
    specs=cast(tuple[_OwnerPayloadSpec[object, object], ...], _OWNER_CAPABILITY_SPECS)
)
(
    _mint_owner_capability, _unwrap_owner_capability, _release_owner_capability,
) = _build_owner_capability_kernel(
    cast(tuple[_OwnerPayloadSpec[object, object], ...], _OWNER_CAPABILITY_SPECS),
    claim_owner_resources=_claim_owner_resources,
    release_owner_resources=_release_owner_resources,
    register_fork_participant=_register_owner_fork_participant,
    lifecycle_section=_owner_lifecycle_section,
)
os.register_at_fork(
    before=_before_owner_fork,
    after_in_parent=_after_owner_fork_parent,
    after_in_child=_after_owner_fork_child,
)

DependencyAuthorityComponentResolution = (
    ResolvedDependencyAuthorityComponents
    | RejectedAuthorityPredicate | UnestablishedAuthorityPredicate
)

def _resolve_owner_components_for_request(
    *, request: MethodCatalogDependencyAuthorityRequest,
    source_authority: CanonicalFoundrySourceAuthority,
    bootstrapper: FoundrySourceTrustBootstrapper,
    ancestry: GitCommitAncestryAuthority,
) -> DependencyAuthorityComponentResolution: ...
def _open_owner_production_data_appointment_authority(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
    signed_records: CanonicalSignedRecordRepository,
) -> _ProductionDataAppointmentAuthority: ...
def _open_owner_production_data_mount_resolver(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
) -> _ProductionDataMountResolver: ...
def _open_owner_root_access_attestor(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
    trust_resolver: FoundryTrustResolver,
    signed_records: CanonicalSignedRecordRepository,
) -> _ProductionDataRootAccessAttestor: ...
def _open_owner_python_runtime_installation_authority(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
    cutoff_authority: _NoRuntimeSubtreeCutoffAuthority,
) -> _ProductionPythonRuntimeInstallationAuthority: ...
def _open_owner_python_runtime_observer(
    *, source_authority: _CanonicalFoundrySourceAuthorityPayload,
    installations: PythonRuntimeInstallationAuthority,
) -> _ProductionPythonRuntimeObserver: ...

def _build_production_canonical_source_resolver(
) -> _ProductionCanonicalFoundrySourceAuthorityResolver: ...
def build_production_method_catalog_dependency_authority() -> MethodCatalogDependencyAuthority: ...

def resolve_dependency_profile(
    declaration: MethodCatalogDependencyProfileDeclaration, *,
    pyproject_bytes: bytes, lockfile_bytes: bytes,
    marker_environment: Mapping[str, str],
    production_data_manifest: ProductionDataManifestInput,
    admission: MethodCatalogProfileAdmission,
) -> ResolvedMethodCatalogDependencyProfile | AuthorityPredicateFailure: ...

def reconcile_bound_installed_environment(
    profile: ResolvedMethodCatalogDependencyProfile, *,
    environment_root: Path,
    environment_receipt: DependencyProfileEnvironmentReceipt,
    evidence: FoundryDependencyAuthorityEvidenceRepository,
) -> DependencyProfileReconciliation: ...

def validate_decisive_domain_coverage() -> None: ...
def validate_authority_predicate_coverage() -> None: ...
def validate_authority_scalar_role_coverage() -> None: ...
def validate_no_owner_capability_in_persisted_schemas() -> None: ...
def validate_owner_entrypoint_failure_mapping() -> None: ...
def validate_negative_only_dependency_authority_abi() -> None:
    """Freeze the complete current result/schema/codec/domain/writer denominator.

    Derive every variant of ``MethodCatalogDependencyAuthorityResult`` and
    require exactly source-rejected, source-not-established and
    runtime-cutoff-not-established, then require an identity-bijection with the
    disjoint union of ``SOURCE_BOOTSTRAP_FAILURE_STAGES`` and
    ``POST_SOURCE_NEGATIVE_AUTHORITY_STAGES``. Source-bootstrap rows use the
    frozen pre-registry grammar and cannot consult registry bytes that failed
    establishment. The post-source row fixes only result, status, predicate,
    required branch shape and source-ref/persistence rules; code and evidence
    shape are resolved from the owner-bound decoded registry in the source
    capability, never duplicated in the stage map or loaded from ambient data.
    Source rejection binds the request's expected commit/tree to the owner
    resolver's observation of the same canonical module Git root and requires
    commit or tree inequality. Missing/unreadable/corrupt registry bytes return
    source-not-established rather than entering post-source validation.
    Runtime refusal names
    ``owner_enforced_runtime_subtree_cutoff: absent/unallocated`` whether
    candidate runtime evidence is present or deliberately not requested. Every
    result separately names
    ``owner_resolved_resolution_receipt_store: absent/unallocated`` as the sole
    reason its refusal is not persisted. A positive/admitted status is invalid.

    The independent AST/type walk covers every ``FoundryAuthorityModel``, every
    ``FOUNDRY_STATEMENT_CODECS`` row, every ``DigestDomain`` row, every method
    on every authority-module Protocol/concrete, every ArtifactStore/FileSystemCAS
    mutation and every filesystem-writing call in the complete canonical
    authority module **and both exact public catalog builder symbols plus the
    complete source-AST caller closure of those builders**. Its only
    persisted-evidence roots are the explicit
    existing capsule, environment, signed-evidence, trust and build-lineage
    types; each must already be reachable from its own codec/domain. A new
    sibling DTO/codec/domain/writer is either a reachable declared evidence root
    or an orphan and fails the same complete walk. No writer/effect edge may
    accept or be reached from a negative dependency-authority result. The
    production call graph is reconciled independently against that denominator.
    Under v1 every public builder/caller returns one of the three negative
    results before any legacy ``platform``/``safe_version`` identity, ambient
    package projection or private candidate reducer edge. Restoring any such
    edge enlarges the cross-file graph and fails. A future positive authority
    requires a new reviewed ABI.
    """
    ...
def validate_runtime_cutoff_constructor_bijection() -> None:
    """Make the owner-bound builder the sole cutoff-result constructor.

    Derive from the complete module AST every call constructing
    ``RuntimeCutoffPreflightRefusal`` or
    ``UnestablishedMethodCatalogDependencyProfile`` and every function/method
    whose return union contains either type. The only constructor is
    ``build_runtime_cutoff_refusal``; every returner must delegate to it with
    the live ``_CanonicalFoundrySourceAuthorityPayload``. That function alone
    calls ``validate_negative_dependency_authority_stage`` before return.
    Missing delegation, a shaped predicate helper or a sibling constructor
    enlarges the denominator and fails.
    """
    ...
def validate_production_owner_composition_bijection() -> None:
    """Derive the no-argument factory graph and reject injectable substitutions.

    The source/AST graph must show one exact source resolver followed by one
    build_production_method_catalog_dependency_authority ->
    one exact _ProductionCanonicalFoundrySourceAuthorityResolver ->
    one exact _NoRuntimeSubtreeCutoffAuthority constructed inside the factory
    and passed only to _ProductionMethodCatalogDependencyAuthority.
    Source rejection/not-established returns before cutoff. Source success then
    reaches cutoff, whose current refusal returns before repository, component,
    sync, candidate, runtime-installation owner or artifact construction. A
    frozen source payload, request/
    constructor parameter, Protocol-typed edge, alternate positive
    implementation, persistence edge or missing preflight edge fails.
    """
    ...

# Install only after every Protocol, concrete method, module function, kernel
# operation and failure-receipt adapter above exists. Source derivation is
# independent of this tuple and installation; exact equality is asserted first.
_OWNER_ENTRYPOINT_SPECS = derive_owner_entrypoint_denominator_from_source(
    module_file=Path(__file__).resolve(),
    protocol_concrete_pairs=_OWNER_PROTOCOL_CONCRETE_PAIRS,
)
_OWNER_BORROW_REACHABILITY = derive_owner_borrow_reachability_from_source(
    module_file=Path(__file__).resolve(),
    owner_entrypoints=_OWNER_ENTRYPOINT_SPECS,
)
validate_owner_entrypoint_failure_mapping()
validate_negative_only_dependency_authority_abi()
validate_runtime_cutoff_constructor_bijection()
validate_production_owner_composition_bijection()
install_owner_entrypoint_guards(_OWNER_ENTRYPOINT_SPECS)
```

After canonical source establishment, the predicate registry is the exhaustive
result decoder. ``BidirectionalAuthorityPredicateSpec`` necessarily carries a
non-empty admitted-class set plus satisfied, rejected and not-established
requirements. ``NotEstablishedOnlyAuthorityPredicateSpec`` has none of the
admitted/rejected fields, so strict TOML decoding rejects them as extras. The
current cutoff row uses that one-sided shape; a satisfied cutoff disposition
cannot be built by the owner because its source capability resolves that exact
row, whereas an ordinary bidirectional predicate remains supported:

| predicate | rejected code | not-established code |
| --- | --- | --- |
| canonical source/freeze | `source_freeze_mismatch` | `canonical_foundry_source_not_established` |
| owner-enforced runtime-subtree cutoff | — | `owner_enforced_runtime_subtree_cutoff_not_established` |
| profile/authority/digest registry | `dependency_authority_registry_invalid` | `dependency_authority_registry_not_established` |
| admitted purpose/profile | `dependency_profile_input_mismatch` | `dependency_profile_not_admitted_for_purpose` |
| trust material/signature | `dependency_trust_signature_invalid` | `dependency_trust_material_not_established` |
| production-data appointment/custody | `production_data_appointment_mismatch` | `production_data_appointment_not_established` |
| fresh root access | `production_data_root_access_mismatch` | `production_data_root_access_not_established` |
| production manifest | `production_data_manifest_content_mismatch` | `production_data_manifest_missing` |
| selected distribution artifact | `selected_distribution_artifact_mismatch` | `selected_distribution_artifact_not_established` |
| build lineage | `build_lineage_mismatch` | `build_lineage_not_established` |
| Python runtime closure | `python_runtime_manifest_mismatch` | `python_runtime_not_established` |
| uv executable | `resolver_executable_mismatch` | `resolver_executable_not_established` |
| installed source binding | `required_distribution_source_mismatch` | `installed_source_binding_not_established` |
| installed stable/instance content | `required_distribution_content_mismatch` | `installed_content_not_established` |
| marker/environment receipt | `dependency_environment_receipt_mismatch` | `dependency_environment_receipt_not_established` |

`production_data_manifest_missing` alone carries
`cause: Literal["missing", "unreadable"]`; it is never translated into catalog
identity or generation-contract drift. Every mismatch carries same-domain
expected/observed values and validates inequality. A not-established row
carries its registered discriminated requirement: missing evidence domains for
evidence predicates, or the exact absent owner capability for the one-sided
runtime-cutoff predicate. `status=pass` has no failures;
`status=fail` has at least one. A generic mutation adds one predicate without a
result row and must fail model construction, which prevents a prose-only status
from becoming the gate.

The loaded digest table admits one discriminated `DigestAlgebraSpec` per row;
the algebra ID and its exact preimage/order/producer/verifier literals are one
constructible variant, never independently selectable fields. Replacing any
one with another otherwise-valid enum member fails strict model construction
before hashing. Tracked TOML first enters the separate strict wire DTO, whose
fields remain exact strings. `decode_digest_domain_registry_toml()` maps every
enum through `_exact_enum` and explicitly constructs the semantic DTO; it never
asks Pydantic to coerce TOML strings into enums. Whitespace, aliases, integers,
booleans and unknown strings reject. Canonical semantic reserialization is
domain-hashed and must reproduce the same statement/hash on a second decode.
The loaded predicate table is a frozen mapping keyed by
`AuthorityPredicateId`; model validators require the exact paired
`AuthorityFailureCode`, P37 class, evidence domains and scalar domain. The
negative-stage table is the sole binding statement for the current resolution
union. It fixes each result kind to one status, predicate/code pair,
evidence/missing-domain shape, source-ref rule and `not_established`
persistence state. Unknown predicate/code strings, wrong stage pairs,
cross-domain scalar or digest comparisons, a positive/admitted variant, or any
resolution-outcome writer/codec/domain are unconstructible.

The authority-schema walker classifies by annotation, never field name. Every
non-`Literal` scalar leaf in every `FoundryAuthorityModel` must be a closed enum,
a nested authority DTO, `DomainDigest`/record ref, `RootedRelativePath`, or carry
exactly one `AuthorityScalarRole` metadata tag. Bare `str`, `StrictStr`, `Path`,
`bytes` and `int` leaves fail regardless of whether their field is called
`relative_path`, `destination`, `install_member` or something novel. TOML wire
DTOs are transport-only and are admitted only through the exact decoder above.
Adding a synonym-named raw path field is the required generic mutation.

All in-process positive owner capabilities use one closure-built kernel.
Tokens are fieldless, slotted, object-only in their complete MRO and carry no
state. Eleven typed
`_OwnerPayloadSpec[C, P]` constants form an exact capability-kind bijection;
mint/unwrap take the spec, so the token/payload relation is not erased to
`object`. Separate token→spec and kind→spec maps must both have exactly eleven
entries and point to the identical spec objects; a rogue twelfth token or a
duplicate kind fails construction. Before either a supplied value or the weak
map is touched, one shared resolver requires the candidate to be the identical
registered spec, its kind to be the exact enum type and its token class to carry
the fieldless-token constructor marker. Kernel construction also validates the
complete leaf/path/nested-cardinality/domain schema. Mint, unwrap and release
all call that resolver first, so a rogue list token, raw-string kind or ordinary
undecorated token class cannot escape through mapping behavior.
Every live leaf is an exact named concrete class—never `Protocol`,
`object` or `Any`—and every persisted leaf is reconstructed under its strict
model. The signed-record spec additionally compares the caller's expected
domain with both the payload domain and bound record-ref domain. A signed graph
stores private `(record_domain, binding_ref, token)` rows; its spec tells the
kernel to recursively unwrap each row with that exact domain. It never asks an
external recursive helper to guess. A structural
lookalike, wrong-domain record, novel mapping/list value, mutated nested token
or wrong-family token becomes a typed fault before registry access.

Live entries exist only inside the kernel closure; the module exposes mint and
unwrap/release operations, not its map or payload entries. Architecture tests allow
those operations only inside the canonical authority module. This is an API
authority boundary, not protection from arbitrary code execution or process-
memory compromise: either condition invalidates the source/process trust basis
and produces no authority receipt.

Entrypoint coverage is independent of wrapping and of a pair registry. A source
AST first finds every transitive `_OwnerBoundaryBase` concrete and its exact
owner `Protocol`; a new concrete automatically enters, while a missing/extra
marker, Protocol or namespace object fails. A second resolved-type walk derives
every concrete method or module function that accepts a token or calls unwrap,
joins it to that independently derived owner method and exact result union, and
then class-wraps the complete denominator. No hand-maintained pair list or
per-method decorator exists. The frozen method/function target carries one
`OwnerFaultPolicy` per capability argument: kind, predicate, rejected and
not-established codes and evidence argument/domain denominator.
The guard binds `self` and all call arguments before invoking the method; a
fault carries kind, payload path and expected/actual domain. The adapter uses
that complete context to return the exact typed negative admitted by that
method's result union, while `ParamSpec` preserves its signature. It does not
mint a persistence authority. Two forged parameters to one multi-token method
must therefore produce distinct predicate-specific outcomes. Removing a guard, adding an unregistered
consumer, or omitting a concrete protocol method fails the bijection before
execution.

PID plus a per-process object bind every live entry. One private synchronized
resource coordinator owns a directory descriptor from the instant `open`
returns, before any token mint. It issues a monotonic open generation, records
the original fstat identity, proves every registered child handle is
weak-referenceable, installs an immediate handle finalizer and
permanently tombstones the generation when it closes. Numeric FD reuse cannot
revive a stale alias. Its single locked claim transition combines
absent-check+lease installation, so two concurrent mints over one generation
yield exactly one token and one typed `RESOURCE_ALREADY_OWNED`. A failed mint
rolls back through the same idempotent release before returning. Exact payload,
leaf and domain validation is side-effect free and precedes child lookup or
claim; fake/missing child attributes cannot invoke a method or mutate the
coordinator. Each admitted
resource token adds its own `weakref.finalize`; explicit release and GC converge
on that coordinator, while a weak released-token tombstone distinguishes
repeat release from a never-minted value.

Unwrap returns a context-managed payload borrow, never a naked payload. The
borrow holds the same coordinator transition lock for its complete use and
increments a token-local borrow count. Release either sees zero borrows and
atomically closes resources+removes the entry+adds the tombstone, or returns
`RESOURCE_IN_USE/not_established` without changing state. A barrier after close
can therefore never expose a still-live token. The source census rejects any
bare unwrap and any fork/forking-subprocess call inside a borrow.

The coordinator owns all three fork callbacks. `before` excludes open, claim,
release and active borrows; the child closes every live generation, including a descriptor
opened just before mint, then invokes the token participant and replaces the
inherited lock. The participant detaches resource finalizers, removes every
payload and retains only a weak token→spec fork tombstone. An inherited genuine
token therefore returns `FORKED_PROCESS/not_established`; a freshly forged
fieldless object still returns `UNMINTED_TOKEN/rejected`. A disposal failure
poisons both unwrap **and mint**, so no new positive token can be created in
that child. Tests prove the descriptor is closed before `exec`, not merely that
its token rejects, and barrier both open-before-mint/fork and two-thread mint.
A copied stale wrapper followed by close, FD-number reuse and another directory
open still fails its generation/current-fstat check before token registration.
Capabilities have no codec and a transitive
schema walk forbids every token beneath a Pydantic/wire/persisted DTO.
Persisted results carry only receipt/binding refs; a fresh process re-resolves
them through the owner.

The Foundry registry owns an explicit `authority_purpose -> profile_id`
admission relation. N8 supplies only the literal fixed purpose; it cannot
select a profile ID. The pure reducer accepts a discriminated manifest input—
exact raw bytes or one unavailable cause—and returns a typed success/failure
union; it never accepts a caller-constructed positive evidence DTO.
The authority-registry validator requires exactly one row for the purpose,
exactly one matching platform row for each of Python and uv, unique row keys,
and exact declaration/trust-policy content hashes. Zero, duplicate, unknown or
cross-platform matches fail before any executable runs; file order is never a
selection predicate.

The only authority path is the no-argument production composition root
`build_production_method_catalog_dependency_authority()`. It constructs the
private `_ProductionMethodCatalogDependencyAuthority` with exactly one
`_ProductionCanonicalFoundrySourceAuthorityResolver` and one
`_NoRuntimeSubtreeCutoffAuthority`; neither is a request or public builder
parameter. Every `resolve()` invokes that resolver afresh. Source mismatch
returns `SourceRejectedMethodCatalogDependencyProfile`; unavailable source
returns `SourceUnestablishedMethodCatalogDependencyProfile`. Neither variant
requires or may carry a source-authority ref. Only a fresh source token proceeds
to cutoff preflight, which binds the strict request, canonical source ref and
negative predicate in a `RuntimeCutoffPreflightRefusal`. It performs no write.
The gate failure names
`owner_enforced_runtime_subtree_cutoff: absent/unallocated`; it never reports
missing `TOOLCHAIN_RUNTIME` evidence as a proxy for that absent owner. Candidate
runtime evidence is an orthogonal discriminated disposition: current
production reports `not_requested`, while a test/reference path may preserve a
content-bound candidate ref and must still return the same gate failure. Every
one of the three negative results separately binds
`persistence=not_established` to
`owner_resolved_resolution_receipt_store: absent/unallocated`; a local CAS
path, environment configuration, caller store or self-attested adjacent copy
is not that capability. The smallest closure is
an appointed owner-opened, request-bound,
no-follow, explicitly signed audit store with independently resolvable
readback. No such component exists in live source, so this plan does not invent
its ABI or writer. The derived production graph rejects a frozen source token,
Protocol/request injection, any positive result, and every repository,
component, sync, candidate or artifact edge before the typed refusal. The
source resolver derives the product root
from the imported Foundry module's resolved `__file__`, proves its enclosing
Git root/attached HEAD, and loads the three fixed registry paths beneath that
root. It rejects any tracked worktree byte differing from HEAD and every
untracked path beneath Python import roots, the Foundry tool root or authority
registry root. Registry, `pyproject.toml`, lock and imported authority bytes
are read from the bound Git tree and compared byte-for-byte to the worktree,
so an unchanged HEAD plus a dirty authority TOML/lock/module is a non-receipt.
The public request contains no source-root, appointment, capsule or receipt
location; its expected commit must equal this independently derived HEAD. A
CLI `--tracked-source-root` is only an equality guard against the derived root.
It cannot redirect lookup.

The candidate reconstruction library, which production v1 cannot reach while
cutoff is absent, is deliberately two phase. Phase B0 opens the fixed
`<environment>/.polisyos-foundry-authority-v1/` evidence capsule read-only and
uses a transport-only CAS reader to load the raw capsule, binding index, exact
signed triples and records. Root keys come only from the canonical tracked
authority registry, use exactly 32 raw Ed25519 bytes (`raw-ed25519-32`), and
verify every source-basis trust-material/revocation binding. No resolver exists
yet. A complete successful B0 result seals the verified material and
revocations together with the exact source authority ref and freeze commit.
Every key ID, key role, trust-material ref, revocation ref, eligible-key row and
revocation disposition is unique and canonically sorted before the live
dictionary/set verifier is constructed; duplicate conflicting rows reject in
either input order. Phase B1 applies the bound Git graph: ancestor/equal revocations
are effective, descendants are retained as future, and an incomparable or
missing commit is `not_established`, never timestamp-ordered. B1 then constructs
the sole role resolver bound immutably to that source ref and cutoff; its
`resolve()` method accepts only policy ref and role. A different source or
cutoff requires an independently bootstrapped resolver. This order
has no resolver/repository cycle and a fresh process can reproduce it from
source authority plus capsule/CAS. The repository then resolves appointment,
selected-artifact and environment-receipt records. The
sync process creates that capsule only after all evidence verifies, atomically
fsyncs it, and a fresh N8 process reopens it from the environment root. Neither
raw registry/appointment/receipt bytes nor a
positive dependency-profile authority result crosses the public owner ABI.
The capsule is only a read-only index over records in the existing
`ArtifactStore`/`FileSystemCAS`, never another CAS. Its
`signed_binding_index_ref` is the complete, sorted, content-bound relation from
every capsule-reachable domain whose digest row says `signed` to that record's
`SignedFoundryRecordBindingStatement`. The denominator comes from signed-domain
rows plus graph reachability, not an appointment case list; missing, duplicate,
orphan, wrong-role and cyclic bindings fail. Trust material uses the source-
authority basis and cannot introduce the trust root that verifies itself;
appointment, custody, root access and build lineage use resolved trust. A fresh
process needs only the capsule index path and CAS—there is no reverse scan,
filename convention or retained process map.

The production `CanonicalSignedRecordRepository` stores one content-bound
evidence record containing the **exact** signed blob, exact original manifest
and detached signature, then a separate non-self-referential binding from the
semantic record ref to that evidence ref, trust-resolution basis, signer role
and verifier provenance. It never regenerates a signed manifest. Loading CAS-
verifies index, binding and evidence; reconstructs the canonical live
`ArtifactID` without changing its `sha256:` wire bytes; requires the retained
blob to reproduce the binding's semantic domain/schema/ref; parses the original
manifest and signature; rejects absent/empty signer identity; resolves the
binding's owner trust snapshot; and only then invokes `ArtifactVerifier`.
Semantic parsing happens last. Deleting or swapping only a binding/evidence
record, regenerating the manifest, adding an extra eligible key or corrupting
any triple member fails in a fresh process.
The separately appointed production-data root may be outside the worktree,
but its statement must bind the Foundry registry, authorized issuer, custody
evidence, verifier provenance, exact root identity and manifest hash. A
missing, fake or unverified appointment returns
`production_data_appointment_not_established`; the production default is this
non-receipt until an appointment is installed. A writable, unappointed, moved
or changed target also fails. Once an appointment is established, the
authority reads the manifest bytes itself. Missing **or unreadable** manifest
then returns the single public code `production_data_manifest_missing`;
the strict failure leaf carries `cause: Literal["missing", "unreadable"]` and
neither cause can construct a resolved profile. Fake appointment bytes plus a valid read-only
root remain a non-receipt because no caller can install an issuer/trust row.
The owner-only `ProductionDataAppointmentAuthority` is the sole positive mint:
it selects the capsule appointment and canonical policy, follows that
appointment's exact `custody_statement_ref`, verifies both signed bindings, and
requires equal root, custodian, manifest, purpose and policy relations. It never
accepts an appointment/custody pair. Cross-pairing two individually authentic
pairs therefore rejects while their signatures and graph membership remain
valid. The authority then recomputes statement refs and manifests,
resolves exact public-key plus revocation bytes through the owner trust policy,
verifies both detached signatures under that material, checks verifier
provenance, and uses its container-owned root-access
attestor to issue a fresh nonce challenge. First the container-owned
`ProductionDataMountResolver` turns the requested path plus verified
appointment into one opaque mount capability. The sealed appointment retains
the exact already-verified appointment and custody statements, not just their
refs; mount resolution compares the requested root with the statement's
`appointed_root` before opening anything. An authentic pair for root A cannot
be applied to requested root B. That same capability is the only
input to both manifest reading and attestation; neither operation can reopen a
path or accept a caller token. Its three-way reducer is frozen: absent
institutional resolver/evidence is `not_established`; a present but wrong,
writable, copied, moved or post-resolution-changed object is `rejected`; only
an owner-opened identity-bound read-only handle is resolved. The missing or
unreadable manifest then remains the separately typed
`production_data_manifest_missing` result. The
attestor must sign the challenge ref and nonce, institutional object ref, live
manifest hash and read-only access mode under an owner-admitted key; there is
no bare-key-ID, filesystem-path, inode or caller-self-attestation fallback.
The trust resolver selects the policy by ref from the canonical source
registry, uses only its bootstrap-bound source authority and cutoff, recomputes
each key ID as SHA-256 over exact 32-byte raw Ed25519 key bytes (PEM is rejected
at this boundary), requires a non-empty signer identity
and requested role, and resolves every content-bound revocation record. It
persists a receipt binding source authority/commit, policy, role, exact eligible
keys, revocations and verifier provenance, then seals the **only**
`ArtifactVerifier` the signed-record repository may use. No caller or repository
constructor supplies a second verifier. The wrapper explicitly rejects an
absent detached-signature identity before calling the live verifier, whose
lower-level compatibility behavior is not an authority predicate.
`build_verifier` resolves its distinct policy material through this same path.
The candidate root-access reducer returns
`production_data_root_access_not_established` when no such attestor is
appointed, but production v1 does not reach that reducer while cutoff is
absent. The current ABI has only the two source-failure variants and the exact
strict `RuntimeCutoffPreflightRefusal`; no persisted resolution-outcome DTO,
domain, codec, repository writer or positive result exists. The refusal's
persistence is explicitly `not_established`.
Consequently no dependency-authority resolution artifact is issued in v1 and
the overall GY-DEF22 capability remains `producer_missing` with an
`artifact_missing` refusal-receipt residual. Public builders return the typed
source failure or preflight refusal, never a positive profile or a bare
exception. An authentic
old attestation or copied
capsule without the current attestor fails. The environment receipt binds only
its own sync-time access evidence and is never treated as fresh N8 evidence.
The institutional-root registry row alone defines the canonical preimage over
root object, appointed custodian, custody record and manifest; no handwritten
formula is a second hash authority.
It contains no machine path. A byte-identical copied directory cannot answer
the fresh institutional root-object challenge and fails; remounting the same genuine
institutional object does not fabricate a new identity.

`tools/devx/foundry/sync_dependency_profile.py` is the only environment-receipt
producer. Given the fixed authority purpose, it resolves the owner admission,
derives uv argv from root/extras/lock, requires a new empty task-local
environment destination, fixes the root install to uv `--no-editable`, and
accepts only absolute Python/uv executables plus
an explicit offline-cache root. Expected tool identities come only from the
Foundry authority registry; caller hashes and versions are not accepted. It never
searches `PATH` or a default uv cache. Cache location/content is transport-
availability only and is deliberately non-decisive: lock/source identities
plus the independently rehashed installed-file closure carry the product gate.
An arbitrary “cache receipt” is neither accepted nor recorded. Before sync it
selects the exact platform artifact for every lock row, verifies its bytes
against `uv.lock`, and retains canonical-store refs plus their evidence records
in the environment capsule. Wheel rows retain the exact wheel. Sdist/git rows
retain source, built wheel and a strict signed `BuildLineageStatement` binding
source, admitted builder runtime, build profile, normalized argv/environment,
output wheel and verifier provenance; no opaque lineage bytes/ref can satisfy
that relation. The local root row retains the complete tracked source-tree
manifest/commit used by the source-first runner. The admitted Python artifact
likewise carries a complete runtime-installation denominator—launcher, stdlib,
libpython and linked runtime libraries—not merely `bin/python`—plus the
expected selected-artifact-to-runtime source binding. The container-owned
installation authority issues a content-bound installation receipt only after
the sync: it binds selected artifact, rooted transform, runtime manifest/source
binding, fresh environment nonce, owner-opened actual-root identity and
installer provenance. During sync, the producer passes the sealed installation
result returned directly by `attest_after_install()` into
`PythonRuntimeObserver.observe_and_verify()`. After the marker exists, a fresh
N8 process resolves the marker's installation-receipt ref through
`resolve_installed_root()` and passes that sealed result into the same observer;
neither path reverse-scans CAS or uses a process-local receipt map. The
installation owner freezes the root-token preimage and requires the requested
environment root to reproduce it before returning the capability. V1 is
deliberately POSIX-local only: Darwin APFS and Linux ext4. The owner opens each
resolved root with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, obtains filesystem kind
from the platform `statfs` identity, and records `fstat` device, inode,
directory mode and `ctime_ns` before enumeration, after enumeration, and after
reopening the same path. All three observations must be equal. It also performs
two independently enumerated, canonically ordered complete file walks. Each
file is opened relative to the retained root descriptor and is `fstat`-checked
before and after its content hash; the two complete runtime-manifest refs must
be equal. Thus mutating an already-hashed nested stdlib file during the first
walk returns `python_runtime_not_established` even when the directory inode is
unchanged. Absolute
environment/root paths contribute only their length-framed
`os.fsencode(realpath)` bytes under `TOOLCHAIN_RUNTIME_ROOT_PATH`; raw paths are
not persisted. The token is the domain-prefixed canonical
`PosixRuntimeRootIdentityStatement`, including path hashes and environment
nonce. The observer independently reopens, remeasures and rehashes the same
statement; producer and verifier do not share an observation function. A path
replacement, move or byte-identical copy changes or loses this relation. Any
other OS, filesystem, unavailable `statfs`, unstable object identity, failed
race recheck or symlink escape returns `python_runtime_not_established`; v1
makes no portable or network-filesystem copy-detection claim. The two complete
walks establish only that both ordered observations match. They do not
establish one simultaneous cutoff: write-and-restore between walks, or a write
to an already-final-observed file while the remainder of pass two continues,
can escape. The smallest closing capability is an owner-enforced immutable
filesystem snapshot or mandatory writer-exclusion lease over the entire
runtime subtree; its state is `absent/unallocated`.

The escape test is deterministically scheduled, not an always-negative proxy.
A test-only observer hook raises a barrier immediately after the chosen early
file's second-pass post-hash `fstat` and before the next row. The adversary
changes that file, releases the observer, and the test independently proves
that both recorded candidate manifest refs and all root observations still
compare equal while a fresh read of the file differs. It then proves the
production preflight alone prevents construction of the installation/
environment authority result. Moving the write before the post-`fstat` is the
control and must make the candidate observations disagree.

`_NoRuntimeSubtreeCutoffAuthority` is therefore the only production v1
composition. Its observation-free `preflight()` is pure and returns only the
typed `not_established` predicate; it neither knows a request nor writes a
receipt. `_ProductionMethodCatalogDependencyAuthority.resolve()` is the outer
owner boundary: it binds the exact request and canonical source evidence,
unwraps the source capability to its immutable decoded digest registry, calls
preflight, and passes the refusal plus that owner payload to
`build_runtime_cutoff_refusal()`. That helper constructs the source-stage
`RuntimeCutoffPreflightRefusal`, validates the one-sided registry branch and
returns
`UnestablishedMethodCatalogDependencyProfile` carrying that exact refusal.
This happens before sync or candidate generation, and no receipt store,
capsule, environment marker or admitted environment receipt exists. The
behavioral test changes CWD and all CAS/signing environment variables and
supplies fake store-shaped inputs; because the production preflight opens no
store and accepts none, none can create or redirect an artifact. It proves the
request root is unchanged and sync, capsule, environment-marker, candidate and
resolution-receipt outputs are absent. Receipt persistence remains
`not_established`; that is the bounded P40 residual, not a hidden writer.
Immediate re-verification is not promoted to a
cutoff predicate. This plan deliberately defines no future positive receipt or
verifier: a later institutional appointment must first receive its own
design/review and replace the no-owner composition.
Substituting a writer-owned lock or adjacent copy remains forbidden. The
reference observer
opens the target child executable, resolves the complete symlink chain and
actual runtime root, and requires the recomputed root token to equal the
receipt before it enumerates rows through the sealed capability. One shared
`RootedRelativePath` validator rejects empty, absolute, non-canonical, `.` and
`..` and NUL-bearing paths in every stable payload, generated-entrypoint,
instance, executable, file, symlink and resolution-hop row. The semantic-scalar
annotation census above rejects any novel raw path regardless of its name.
Cross-root hops carry two root
tokens plus contained relative paths, never an absolute stable path. The
observer recomputes the expected-domain runtime manifest and source binding and
persists a separate instance root-resolution statement. The
verification receipt compares expected and recomputed refs in their respective
**same domains** before binding the observed instance. A byte-identical launcher
or complete runtime tree redirected to a root not named by the installation
receipt, copied expected rows, a self-consistently rewritten observation, or a parent
`PYTHONPATH` cannot mint that capability. Absolute paths enter only the instance
root token's owner preimage, never a persisted stable field. Missing/unreplayable artifact, build lineage
or Python runtime evidence maps through the predicate registry to its exact
`not_established` leaf and no admitted receipt exists.
Fixture/reference tests may compute the stable profile, exercise the frozen
offline-sync command derivation, independently read a scratch installed closure
and write a candidate marker. The production authority calls `preflight()`
first and, under the current no-owner composition, stops with the typed
non-receipt before any sync, marker or N8 candidate. It accepts no profile ID or
extras. N8 requires an
admitted receipt and calls only the bound resolver/reconciler, which reads
the marker and installed metadata from the bound environment itself; a caller
sequence of shaped distribution DTOs is reference-test input only and cannot
carry the gate. The pure reducer is a non-authority reference function and no
gate consumes its result without the source-freeze, data-appointment and
environment receipts.
The CLI's appointment-file argument is candidate transport: it imports the
exact appointment/signature/custody bundle, obtains its content ref, and asks
the canonical verifier to verify it before the capsule is created. It cannot
turn arbitrary bytes into an installed appointment or supply a verifier/trust
configuration.

The N8 identity environment never uses the lock's default editable root shape.
The fixed non-editable argv makes checkout-address-bearing `direct_url.json`
and `.pth` files invalid rather than candidates for normalization. A test builds
the same source commit from two sibling checkout paths and requires identical
stable root rows; switching either install to editable fails. The separate
tooling `.venv` may remain editable because it is not the receipted N8 identity.

Distribution names use one PEP-503 lowercase/dash normalization function in
the Foundry module. Hashes are lowercase `sha256:<64 hex>`. Canonical JSON uses
the repository CanonSpec with raw mappings. Distribution-set and closure
preimages/order are generated only from their executable digest-registry rows;
handwritten formulas are forbidden and the contract test compares every
generated builder against that row. The stable closure contains the exact
source-tree ref/commit for a source-first distribution, but no environment
nonce, receipt ref, cache location or install-instance field.
Two independent installs from identical decisive inputs therefore reproduce
the same closure discriminant while issuing distinct instance receipts.

Installed content has separate **stable** and **instance** complete
denominators. The stable expected denominator is derived independently from the
retained wheel/build/source-tree artifact, never from installed `RECORD`.
`wheel_install_tree_v1` applies the standard purelib/platlib/data relocation;
rows use logical roots `{purelib}`, `{platlib}`, `{scripts}`, `{data}` and
`{headers}` and therefore contain no absolute environment path. Payload rows
bind logical root, normalized relative path, byte length and raw content hash.
Generated entry-point rows instead bind the exact entry-point target, admitted
launcher profile, Python ABI and normalized flags. V1 admits exactly one
authority-registry profile: POSIX distlib console script, `cp314`, LF endings,
one interpreter occurrence and token `@PYTHON@`; Windows is deliberately not
claimed. Its closed expected-wrapper producer and **different** observed-byte
parser/verifier are resolved through immutable enum maps. The producer derives
the complete expected wrapper from entry-point target, admitted interpreter and
flags. The verifier parses the whole observed UTF-8 wrapper, requires exact
line ending, stub/import/call/body/flags, exactly one admitted interpreter
prefix and no trailing/extra bytes, then replaces only that prefix. Mutating the
body while keeping markers, CRLF, a second interpreter occurrence, changed
flags or stub shape rejects. It never normalizes a path-like byte sequence in
package payload. Freeze expected/observed/rejected byte vectors for every
admitted platform family. The six live project scripts are in this denominator.
RECORD/INSTALLER/REQUESTED and structurally generated bytecode are the only
exclusions.

The instance denominator independently enumerates every
`importlib.metadata.Distribution.files` row, resolves it within the bound
environment, rejects escaping/duplicate/ambiguous ownership, and hashes exact
raw file bytes including generated launchers. It builds a complete ownership
map from distribution records and retained artifact paths; an unrecorded or
ambiguously owned regular file under a required artifact's import roots fails.
Stable rows hash under `installed-tree-stable`; raw instance rows hash under
`installed-tree-instance`. The source relation hashes the selected evidence,
transform profile, stable manifest, optional typed build-lineage record and
optional source freeze under `installed-source-binding`. Expected and observed
source mismatches compare this same domain only; comparing a locked-artifact
identity to a relation digest is schema-invalid.

The closure uses ordered expected stable manifests/bindings. The environment
marker/receipt use independently observed stable manifests/bindings plus the
raw instance content set and instance nonce. Two installs at different
absolute roots therefore have equal stable closure and distinct instance
receipts. Mutating any non-instance payload byte, `pathlib.py`, libpython,
required runtime library, build output or source relation fails even when
dist-info/RECORD and shaped receipts are rewritten. A missing RECORD/file,
unowned editable origin without retained source lineage or file outside the
bound source/environment roots fails closed. A same-name/version substituted
wheel with rewritten RECORD cannot match the retained lock-selected artifact.

All decisive refs/hashes use one non-self-referential grammar. For strict
statement `S`, construct a raw mapping, compute `statement_bytes=C(S)` under the
complete `CanonSpec`, use canonical CAS identity `sha256(statement_bytes)`, and
compute semantic identity as
`sha256(domain_prefix || uint64_be(len(preimage)) || preimage)`. Tracked TOML
raw refs hash exact source bytes while semantic hashes frame the canonical
parsed statement. Ordered-row and relation domains define their complete sort
key/preimage in the digest registry. No statement contains its own ref/hash.

`method_catalog_dependency_digest_domains.toml` is the exhaustive owner table,
not a suggestive prefix list. TOML encodes every distinct
`polisyos.foundry.*.v1\\0` prefix as validated lowercase `prefix_hex`, including
the terminal `00`; `bytes.fromhex` is the only decoder. Each row chooses closed
`DigestPreimageKind`, `DigestOrderingRule`, **separate** `DigestProducerId` and
`DigestVerifierId`, and `DigestPhase` members. The decoded prefix must equal
`polisyos.foundry.{domain.value}.v1\\0` byte-for-byte; a sibling-owner prefix is
invalid even when lowercase and NUL-terminated. Independent immutable producer-
and verifier-to-callable maps use different functions/provenance; corrupting a
producer while retaining the verifier must turn the golden-vector test red.
Unknown/unused handlers or rules and an incompatible preimage/order pair fail
registry construction. A signed row also names its
exact `TrustRole`, while an unsigned row structurally cannot. The table covers:
canonical source authority; profile, authority and digest registries; profile
declaration/admission; Python/uv artifact admission, executable, expected/
observed runtime, runtime-root installation/resolution/token/source binding and runtime-
verification receipt;
pyproject/lock raw blobs; trust material, trust resolution and
content-bound revocation plus verifier provenance; production manifest,
appointment, custody, institutional root, mount resolution, root nonce,
challenge/access, signed-record binding and complete binding index; selected
wheel/source/built artifact, source-tree
and wheel-RECORD manifests, build argv/environment/profile/lineage; stable and
instance installed trees, installed-source binding, distribution and
stable/instance content sets, closure and derived uv argv; marker, environment
receipt, capsule and resolution request. External
institutional refs and Git commits are separate typed values with appointed
resolvers, never content proof.

`FOUNDRY_STATEMENT_CODECS` is the sole schema-version/domain decoder. Every
registry row with `preimage_kind=canonical_statement` maps to exactly one strict
statement class (a discriminated union counts as one codec); rows of every other
`DigestPreimageKind` — `raw_blob`, `relation`, `tracked_toml` and `ordered_rows`
— map to their one builder of that kind instead, and each row's `preimage_kind`
is **derived from how this plan uses the domain**, never chosen by the
implementation: a domain that names its own statement class is
`canonical_statement`; a domain carried as a digest, ref, token or nonce field
inside another statement is `raw_blob`; a domain computed from other domains is
`relation`. A domain whose kind cannot be derived from this plan's text is a
specification stop. The mapping is a bijection across the complete
`DigestDomain` enum. This includes the
profile/authority/digest registries, canonical source, verifier provenance,
trust/revocation/resolution, manifest/appointment/custody/mount/challenge,
selected-evidence union, wheel/source/build records, stable/instance/source-
binding records, Python expected/observed/root/source-binding/verification
records, signed binding/index records, marker,
environment, capsule, request and outcome. A ref whose schema version does not
match its domain cannot be loaded.

`validate_decisive_domain_coverage()` recursively inspects every strict C1 DTO
by its `DomainDigest`, `FoundryRecordRef`, `DomainScalar` or external-ref type
annotation—not by field-name suffix. `FoundryRecordRef` pairs an immutable
domain-specialized ref with the **exact** live `ArtifactID` wire ABI
`sha256:<64-lowercase-hex>` and its semantic domain. The canonical store adapter
calls `ArtifactID.model_validate`, requires byte-identical string round-trip and
never constructs a mutable `ArtifactRef` or strips/adds a prefix. Every domain
has exactly one producer and one independent recomputing verifier;
prefixes are unique; and the phase DAG forbids instance/resolution inputs from
stable hashes. `validate_authority_predicate_coverage()` requires every gate
predicate to instantiate exactly one allowed branch shape: bidirectional rows
carry admitted P37 classes and all three requirements, while one-sided rows
carry only their not-established requirement. It also reconciles every emitted
disposition to the exact owner-bound registry ref/spec; a branch absent from the
row cannot be constructed by an authority path.
Adding an unregistered decisive field, unmapped predicate, duplicate prefix or
cross-domain `DigestPredicateMismatch` fails a generic contract test. Freeze
0/1 golden vectors for **every registry row**, not a hand-picked subset. Missing
artifact/build/Python/root evidence therefore maps generically to its exact
not-established leaf; contradictory evidence maps to the paired rejection.

The marker retained under the environment root binds a fresh instance nonce
and the same stable inputs. Reconciliation reloads it and requires byte/hash
equality with the receipt; copying only a receipt fails. A bit-for-bit clone
including the marker retains the same instance identity and is not promoted to
writer-independent custody. The selected marker environment contains exactly
the marker variables traversed during closure resolution, sorted by key; unused
ambient variables and distributions outside the derived closure are
non-decisive.

`resolve_dependency_profile` returns a missing production manifest with the
single typed code `production_data_manifest_missing`; it never reports catalog
identity or generation-hash drift for that cause. `reconcile...` compares only
the derived closure, so an out-of-closure package cannot fail the gate. A
changed influential marker/root/extras/lock edge changes the discriminant.
Holding the admitted label constant while substituting a receipt produced for
another selected profile fails the admission/argv/receipt hashes. Thus the
documented `research` **selection** fails even when its required package subset
overlaps, while an unrelated out-of-closure package added to a genuinely
admitted environment remains non-decisive. The shell torch check is not used
as product evidence.

`DependencyProfileEnvironmentReceipt` is deliberately an instance receipt,
not an input to `closure_discriminant`. It binds that stable discriminant and
the independently read installed set. Required tests build two fresh
environments with identical inputs and require equal closure discriminants but
different marker/receipt refs; changing one in-closure distribution changes
the stable identity or rejects reconciliation. A same-shaped receipt copied
without its marker, a changed marker under the same child interpreter, and a
parent `PYTHONPATH` pointed at the tooling site all fail.

Change the existing owner rather than adding a parallel identity:

```python
def build_method_catalog_runtime_identity(
    snapshot: MethodCatalogSnapshot,
    *, dependency_authority_request: MethodCatalogDependencyAuthorityRequest,
) -> DependencyProfileResolutionFailure: ...

def build_method_catalog_provenance_manifest(
    snapshot: MethodCatalogSnapshot,
    *,
    registry_report: FoundryExtensionRegistryReport,
    ambient_manifest: ComponentDiscoveryManifest,
    dependency_authority_request: MethodCatalogDependencyAuthorityRequest,
    additional_predicate_provenance: Sequence[Mapping[str, object]] = (),
    predicate_bindings: Mapping[str, Sequence[str]] | None = None,
) -> DependencyProfileResolutionFailure: ...
```

Each public builder calls the canonical no-argument authority factory and
returns its exact negative result before evaluating any legacy ambient identity
or private positive projection helper. There is no successful public variant in
v1 and therefore no `dict` arm in either signature. Positive DTOs and pure
candidate reducers remain package-internal test/reference evidence and are
unreachable from both builders and every caller under the complete cross-file
call-graph strangle. Model validators still independently recompute equality of
profile/admission declaration hashes, purpose/profile relation, stable
discriminant, environment receipt/marker refs, installed set/content-set hashes
and candidate reconciliation, but those candidate values cannot enter a public
result until a separately reviewed positive authority ABI exists. A fail
reconciliation requires at least one failure; a pass has no failure field.
`AuthorityPredicateSpec` fixes every code/class/evidence-domain combination,
and the generic validator rejects a missing mapping, equal mismatch values,
cross-domain expected/observed values, or a not-established row with invented
observed evidence. Constructing shape-valid but cross-object-inconsistent
positives is therefore schema-invalid and cannot bypass the absent cutoff.

There is no default dependency profile. A complete AST census over both changed
builders currently finds **12 call expressions** (nine provenance-manifest and
three runtime-identity calls). Record the exact `file:line:function` census in
the Cluster-1 red receipt and update all 12 in the same atomic signature-
migration commit; the post-change AST census must have zero call missing the
request keyword and zero source call passing an admitted-profile object. A
missed or novel caller fails by signature, never by fallback to
`platform`/`safe_version` ambient observation. The same complete source walk
starts from both public symbols and follows all callers; restoring the current
ambient dictionary branch or an edge to a pure candidate reducer fails even
when the authority module remains perfectly negative-only.

Task 1.1 direct suite argv (no selector may omit the novel-profile test):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/foundry/methods/test_dependency_profile.py \
  tests/unit/foundry/methods/test_catalog_snapshot.py
"${GY_N12_RUN[@]}" -m basedpyright --project basedpyright.toml \
  tests/typecheck/foundry/dependency_authority_covariance.py
```

The checked fixture assigns a
`FoundryRecordRef[Literal[DigestDomain.RAW_BLOB]]` to the exact generic
repository parameter `FoundryRecordRef[DigestDomain]` without a cast, and also
contains `assert_type` witnesses for the domain tag. Making `D_co` invariant or
passing a raw string domain must fail this command; a runtime pytest cannot
stand in for that static property.

Required nodes are
`test_purpose_resolves_profile_without_caller_profile_id`,
`test_research_receipt_cannot_relabel_itself_as_n8_profile`,
`test_authorized_external_read_only_data_root_passes_appointment`,
`test_read_only_root_without_appointed_access_attestor_is_not_established`,
`test_writable_moved_or_unappointed_data_root_fails`,
`test_fake_appointment_and_valid_read_only_root_is_not_established`,
`test_two_authentic_appointment_custody_pairs_cannot_be_cross_swapped`,
`test_random_signature_custody_and_verifier_refs_fail_after_resolution`,
`test_trust_key_id_role_identity_and_revocation_are_recomputed`,
`test_duplicate_or_unsorted_trust_key_role_and_revocation_sets_reject_before_verifier`,
`test_trust_policy_statement_has_no_self_reference`,
`test_trust_receipt_changes_with_policy_cutoff_or_role`,
`test_source_a_bootstrap_cannot_resolve_source_b_or_another_cutoff`,
`test_trust_resolution_rejects_absent_identity_or_extra_eligible_key`,
`test_source_trust_bootstrap_precedes_role_resolver_without_repository_cycle`,
`test_source_trust_bootstrap_rejects_pem_or_wrong_length_root_key`,
`test_revocation_cutoff_uses_ancestor_equal_future_and_incomparable_git_relations`,
`test_signed_record_repository_has_no_verifier_injection_surface`,
`test_build_lineage_requires_owner_resolved_build_verifier_trust`,
`test_old_signed_root_attestation_cannot_relabel_fresh_nonce`,
`test_candidate_evidence_binds_fresh_challenge_and_current_manifest`,
`test_current_production_authority_returns_only_unpersisted_cutoff_refusal`,
`test_manifest_missing_candidate_preserves_exact_missing_or_unreadable_cause`,
`test_genuine_attestor_for_root_a_cannot_attest_requested_copy_b`,
`test_authentic_appointment_for_root_a_rejects_requested_root_b_before_mount`,
`test_identical_copied_tree_without_institutional_root_evidence_fails`,
`test_alternate_git_root_with_self_consistent_registries_cannot_redirect_authority`,
`test_dirty_authority_registry_under_unchanged_head_fails_before_admission`,
`test_fresh_n8_process_reopens_exact_environment_authority_capsule`,
`test_capsule_signed_binding_index_is_exact_graph_bijection`,
`test_fresh_process_reopens_appointment_custody_trust_and_lineage_bindings`,
`test_missing_swapped_or_cyclic_signed_binding_fails_closed`,
`test_canonical_store_blob_manifest_or_signature_corruption_fails_before_parse`,
`test_imported_signed_evidence_rejects_regenerated_manifest_or_swapped_ref`,
`test_authority_record_pointer_round_trips_exact_live_artifact_id_wire`,
`test_bare_uppercase_or_unprefixed_artifact_id_fails_strict_parse`,
`test_profile_closure_names_root_extras_and_distribution_discriminant`,
`test_in_closure_substitution_changes_discriminant_without_name_rule`,
`test_required_file_mutation_with_unchanged_dist_info_fails_reconciliation`,
`test_substituted_wheel_with_consistently_rewritten_record_fails_lineage`,
`test_source_first_runtime_files_bind_to_tracked_tree_not_tooling_environment`,
`test_noneditable_root_install_is_stable_across_sibling_checkout_paths`,
`test_editable_root_install_is_rejected_from_n8_identity`,
`test_python_stdlib_mutation_with_unchanged_launcher_fails`,
`test_observed_python_runtime_cannot_copy_expected_runtime_ref`,
`test_runtime_observer_derives_child_executable_root_and_source_binding`,
`test_runtime_observer_requires_owner_sealed_installation_capability`,
`test_fresh_n8_resolves_marker_installation_before_runtime_observation`,
`test_owner_capability_rejects_empty_object_new_mutated_token_and_wrong_family`,
`test_owner_payload_protocol_lookalike_wrong_domain_or_nested_token_rejects_before_mint`,
`test_raw_string_kind_undecorated_token_and_list_spec_fail_before_mapping_access`,
`test_copying_token_marker_onto_stateful_class_fails_behavioral_token_check`,
`test_token_with_inherited_writable_slot_fails_object_only_mro_check`,
`test_unhashable_metaclass_in_rogue_spec_fails_before_token_map_access`,
`test_nonexistent_or_wrong_typed_leaf_nested_and_domain_paths_fail_construction`,
`test_signed_record_token_rejects_a_different_expected_record_domain`,
`test_signed_graph_recursively_binds_each_record_token_to_its_row_domain`,
`test_swapped_signed_graph_record_domain_fails_private_recursive_unwrap`,
`test_rogue_twelfth_token_or_duplicate_capability_kind_fails_bijection`,
`test_owner_kernel_exposes_no_live_entry_or_payload_registry`,
`test_fork_closes_inherited_source_runtime_and_institutional_root_descriptors`,
`test_every_registered_child_resource_is_weakrefable_before_open`,
`test_drop_open_handle_before_mint_closes_generation_by_finalizer`,
`test_fork_after_descriptor_open_before_mint_closes_unclaimed_generation`,
`test_failed_mint_rolls_back_and_closes_every_provisional_resource`,
`test_wrong_payload_or_fake_child_fails_before_any_coordinator_or_child_call`,
`test_wrong_signed_record_lookalike_property_is_never_accessed_before_type_fault`,
`test_corrupt_sibling_after_valid_open_handle_closes_generation_on_mint_failure`,
`test_claim_internal_failure_leaves_no_partial_lease_or_open_provisional`,
`test_concurrent_same_generation_mint_admits_exactly_one_resource_lease`,
`test_release_and_token_tombstone_are_atomic_against_payload_borrow`,
`test_bare_unwrap_or_fork_inside_owner_borrow_fails_source_denominator`,
`test_owner_borrow_helper_to_fork_fails_transitive_call_graph`,
`test_owner_borrow_callback_or_helper_cannot_store_or_return_payload`,
`test_owner_borrow_custom_len_to_fork_fails_implicit_dispatch_graph`,
`test_owner_borrow_custom_iter_to_aliased_spawn_fails_implicit_dispatch_graph`,
`test_owner_borrow_descriptor_getter_to_callback_fails_implicit_dispatch_graph`,
`test_owner_borrow_if_custom_bool_to_fork_fails_statement_dispatch_graph`,
`test_owner_borrow_sequence_match_to_spawn_fails_pattern_dispatch_graph`,
`test_owner_borrow_repeated_operator_occurrences_are_indexed_and_reconciled`,
`test_owner_borrow_len_of_exact_builtin_tuple_is_admitted_control`,
`test_inherited_live_token_is_forked_not_unminted_but_forgery_is_unminted`,
`test_drop_and_collect_token_closes_descriptor_before_later_fork`,
`test_two_tokens_cannot_share_one_resource_handle`,
`test_closed_wrapper_cannot_revive_after_fd_number_reuse`,
`test_raw_oserror_from_stale_descriptor_becomes_typed_not_established`,
`test_explicit_release_closes_descriptor_and_invalidates_token_idempotently`,
`test_forked_handle_operation_rechecks_creator_process`,
`test_disposal_failure_poison_rejects_fresh_mint_without_registering_token`,
`test_source_derived_owner_entrypoint_denominator_equals_wrapped_methods`,
`test_source_derived_owner_boundary_classes_exactly_determine_protocol_pairs`,
`test_new_owner_boundary_or_removed_protocol_base_fails_pair_derivation`,
`test_removing_one_derived_method_or_function_guard_fails_independent_bijection`,
`test_every_owner_entrypoint_maps_mapping_or_nested_fake_to_its_exact_result_union`,
`test_two_fake_parameters_map_to_distinct_predicates_and_typed_outcomes`,
`test_runtime_cutoff_composition_rejects_protocol_or_positive_fake_substitution`,
`test_factory_holds_source_resolver_not_source_snapshot_and_resolves_each_call`,
`test_dirty_or_missing_source_returns_typed_variant_without_source_ref`,
`test_source_failure_and_cutoff_refusal_precede_repository_sync_and_candidate_edges`,
`test_negative_only_abi_rejects_positive_result_or_resolution_writer_codec_domain`,
`test_negative_stage_map_fixes_status_predicate_code_domains_source_ref_and_persistence`,
`test_post_source_negative_stage_map_derives_code_and_evidence_from_canonical_predicate_registry`,
`test_runtime_cutoff_predicate_is_one_sided_and_cutoff_specific`,
`test_missing_unreadable_or_corrupt_digest_registry_returns_source_not_established`,
`test_unusable_git_root_or_unresolvable_commit_returns_source_not_established_without_tree`,
`test_ambient_registry_mutation_after_source_capability_cannot_change_cutoff`,
`test_cutoff_row_rejects_admitted_class_or_satisfied_disposition`,
`test_bidirectional_predicate_branch_remains_constructible`,
`test_sibling_cutoff_result_constructor_enlarges_constructor_denominator`,
`test_source_stage_cannot_carry_appointment_failure_with_valid_result_kind`,
`test_source_rejection_binds_request_commit_tree_to_owner_observed_head_tree`,
`test_unrelated_unequal_source_hashes_cannot_satisfy_source_freeze_rejection`,
`test_candidate_runtime_evidence_does_not_substitute_for_missing_cutoff_owner`,
`test_cutoff_absence_uses_cutoff_predicate_not_python_runtime_evidence_predicate`,
`test_every_negative_variant_names_the_same_absent_receipt_store`,
`test_sibling_resolution_dto_codec_domain_or_writer_enlarges_complete_denominator`,
`test_negative_production_graph_rejects_runtime_installation_owner_edge`,
`test_public_catalog_builders_and_all_callers_are_inside_negative_graph`,
`test_restoring_legacy_ambient_or_candidate_projection_fails_cross_file_strangle`,
`test_every_missing_capability_literal_has_one_exact_incomplete_state_label`,
`test_cutoff_outer_owner_returns_exact_unpersisted_refusal_before_any_write`,
`test_cutoff_refusal_names_absent_owner_resolved_receipt_store`,
`test_cwd_cas_and_signing_environment_do_not_create_or_redirect_refusal_artifact`,
`test_owner_capabilities_have_no_wire_codec_and_fresh_process_reresolves`,
`test_no_persisted_schema_transitively_contains_owner_capability`,
`test_admitted_profile_round_trip_carries_root_access_refs_not_live_token`,
`test_byte_identical_child_redirected_to_unbound_runtime_root_fails`,
`test_copied_runtime_tree_cannot_rewrite_owner_installation_receipt`,
`test_posix_runtime_root_token_recomputes_open_handle_path_and_race_relation`,
`test_moved_replaced_or_byte_identical_copied_runtime_root_changes_token`,
`test_nested_stdlib_mutation_during_first_walk_is_runtime_not_established`,
`test_barriered_write_after_second_post_fstat_preserves_equal_candidate_manifests`,
`test_control_write_before_second_post_fstat_changes_candidate_manifest`,
`test_no_runtime_cutoff_preflight_blocks_before_sync_or_candidate_generation`,
`test_candidate_two_pass_observation_has_no_positive_production_intake`,
`test_runtime_receipt_does_not_claim_writer_independent_continuous_immutability`,
`test_unsupported_or_unstable_filesystem_is_runtime_not_established`,
`test_runtime_paths_reject_empty_dot_absolute_dotdot_noncanonical_and_nul_variants`,
`test_every_authority_scalar_has_semantic_role_without_name_heuristic`,
`test_synonym_named_raw_path_field_fails_generic_schema_coverage`,
`test_fresh_runtime_root_resolution_changes_instance_not_stable_identity`,
`test_missing_build_lineage_is_exact_source_binding_not_established`,
`test_every_persisted_digest_domain_has_one_strict_statement_codec`,
`test_unknown_digest_producer_verifier_ordering_or_launcher_profile_fails_before_execution`,
`test_digest_algebra_rejects_single_known_enum_member_substitution`,
`test_digest_registry_toml_rejects_synthetic_enum_alias_whitespace_number_and_bool`,
`test_digest_registry_toml_semantic_round_trip_reproduces_hash`,
`test_digest_prefix_hex_is_lowercase_nul_terminated_and_round_trips`,
`test_sibling_owner_prefix_fails_exact_domain_derived_equality`,
`test_corrupted_digest_producer_is_rejected_by_independent_verifier`,
`test_specific_domain_ref_satisfies_generic_repository_without_cast`,
`test_out_of_closure_distribution_is_non_decisive`,
`test_novel_profile_resolves_from_toml_without_code_change`,
`test_influential_marker_or_lock_edge_cannot_be_omitted`,
`test_two_fresh_installs_share_closure_but_not_instance_receipt`,
`test_generated_launchers_normalize_only_admitted_interpreter_across_roots`,
`test_launcher_body_crlf_flags_stub_or_second_interpreter_mutation_rejects`,
`test_path_like_payload_bytes_are_never_launcher_normalized`,
`test_root_nonce_and_challenge_statement_domains_are_not_substitutable`,
`test_missing_mount_is_not_established_but_wrong_writable_or_moved_is_rejected`,
`test_manifest_and_attestor_consume_same_mount_and_detect_later_identity_change`,
`test_receipt_copy_without_target_marker_fails`,
`test_substituted_uv_bytes_fail_against_unchanged_owner_admission`,
`test_arbitrary_cache_receipt_is_not_an_authority_input`,
`test_public_builders_reject_caller_constructed_positive_profile`,
`test_unknown_authority_dto_field_fails_strict_parse`,
`test_unregistered_decisive_digest_or_predicate_fails_generic_coverage`,
`test_every_explicit_digest_builder_is_generated_from_registry_algebra`,
`test_source_mismatch_requires_same_domain_expected_and_observed`,
`test_scalar_mismatch_rejects_cross_domain_strings`,
`test_cross_object_admission_or_reconciliation_mismatch_is_schema_invalid`,
`test_every_mismatch_code_rejects_equal_or_incompatible_field_shapes`,
`test_tooling_pythonpath_cannot_supply_n8_distribution_origin`, and
`test_missing_and_unreadable_manifest_share_public_typed_cause`.

The tool's tests use fixture source-freeze commits and scratch destinations;
they issue candidate receipts only. No admitted environment receipt can be
issued while its implementing source is uncommitted, while Clusters 2–4 can
still move the source freeze, or while runtime-cutoff authority is
`not_established`. The post-review source-freeze protocol therefore calls the
observation-free production `preflight()` immediately before any environment
sync, terminal N8/N10a validation or candidate generation and
records the current expected non-receipt. It must not enter candidate generation
or a governed transition. If a separately reviewed owner appointment later
changes that predicate, a new contract and plan must define the positive
observation/verification boundary; this plan contains no dormant positive path.
A pre-existing destination, direct
`uv sync` substitution, caller-supplied profile/extras or receipt copied from a
different environment is a non-receipt. The terminal N8/N10a commands use this
environment and receipt, never the tooling `.venv` as identity evidence.

### Task 1.2 — carry the identity through N8 and N10a without relabeling it

**Modify:**

- `tools/quality/validation/check_layer3_gy_value_gate_contract.py`
- `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- `tests/unit/runtime/quality/test_value_gate.py`
- `tests/unit/runtime/quality/test_second_domain_pack.py`
- `tests/repo_quality/tools/test_local_prod_debug_probe.py`

N8 constructs `MethodCatalogDependencyAuthorityRequest` with only the fixed
authority purpose, expected source freeze, production-data root and environment
root, then passes that request to both catalog builders. The canonical source
registry and environment marker—not N8—resolve appointment, capsule and receipt
refs. Each builder resolves
through the canonical Foundry authority in the same call; under current v1 N8
can record only the returned typed non-receipt and must stop before an ambient
or candidate projection. It cannot pass or mint a positive profile wrapper.
The authority hashes the exact production manifest bytes.
Extend
N8 `validate_payload_result`, `check_catalog_provenance_result` and
`check_result` to rederive the discriminant from the recorded declaration and
lock inputs before considering backend/package fingerprints. Extend N10a
`_n8_transport_gap_closure()` to preserve the exact typed cause instead of
collapsing it to `n8_value_contract_invalid` or downstream triage drift.
Foundry reads the bound source itself; it must not import the runtime HTTP
production-data service and N8 cannot supply a positive evidence object.
Both validators require `--expected-source-freeze COMMIT`; they reject a
receipt bound to another commit even when profile/distribution bytes match.

Add exact negatives:

- an environment receipt issued by the documented `research` selection (which
  admits `torch==2.10.0`) cannot be relabelled under the fixed N8 purpose and
  fails with the named profile/root/distribution mismatch;
- changed in-closure distribution under unchanged shaped fields -> rejection;
- changed out-of-closure package -> pass;
- missing or unreadable `production_data/manifest.json` -> exactly
  `production_data_manifest_missing`, never catalog/hash/N10a drift; and
- corrupt the discriminant while retaining every profile marker -> rejection by
  recomputation.

The red/green full-file argv is manifest data, not an executable bypass:

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/runtime/quality/test_value_gate.py \
  tests/unit/runtime/quality/test_second_domain_pack.py \
  tests/repo_quality/tools/test_local_prod_debug_probe.py
```

The complete N8/N10a validator and mutation command ledger is frozen in
Appendix B. In particular, N8 `--corrupt-field-drift-check` and N10a's same mode
have intentional non-standard success statuses; their wrapper asserts both the
documented process status and semantic PASS/status payload.

### Task 1.3 — register the owner boundary; defer every writer

**Modify in the same atomic signature boundary as Tasks 1.1–1.2:**

- `src/polisyos/foundry/methods/catalog/__init__.py`
- `src/polisyos/foundry/__init__.py`
- `architecture/public_surface/inventory.json`
- `docs/reference/public-surface.md`

Only `MethodCatalogDependencyAuthorityRequest`, the discriminated public
failure union, and the two authority-calling catalog builders are re-exported
through the already admitted `polisyos.foundry` root facade. Positive
declaration/admission/environment/reconciliation DTOs, the authority protocol,
evidence repository, verifier and pure reducers remain package-internal. The
package-local catalog module remains internal; a README or local `__init__`
does not mint authority.
Regenerate and review `architecture/public_surface/inventory.json`, add the
required `python-public-api` release fragment, and prove import/identity parity
through the root facade. This classification is not conditional. Registering
generated N8/N10a source dependencies in
`architecture/generated_artifacts.toml` and
`docs/reference/generated-artifacts.md` is deferred to the terminal declared
artifact transaction, where registry, reference and payload bytes move
together. Do not touch N8/N10a governed JSON here. Foundry adjudicates the
exact resolver/falsifier packet; until that receipt is recorded, GY-DEF22
retains `producer_missing` even if lane tests are green.

Regenerate the admitted public inventory/reference through the canonical
source-first writer, then check the result; never edit generated rows by hand
or rewrite the deep-import baseline:

```text
"${GY_N12_RUN[@]}" - <<'PY'
from tools.devx.architecture import guardrails

policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
families = guardrails._parse_public_generated_artifact_families(
    guardrails.DEFAULT_PUBLIC_MANIFEST
)
inventory = guardrails.build_public_surface_inventory(policies)
guardrails._write_if_changed(
    guardrails.DEFAULT_PUBLIC_JSON,
    guardrails.render_public_surface_json(
        inventory, generated_artifact_families=families
    ),
)
guardrails._write_if_changed(
    guardrails.DEFAULT_PUBLIC_MD,
    guardrails.render_public_surface_markdown(inventory),
)
PY
"${GY_N12_RUN[@]}" -m tools.cli architecture guardrails check
```

These are the exact direct suite argv rows for the public-surface boundary.

**Commit boundaries:**

1. `feat(foundry): bind and carry admitted dependency profile identity` — one
   atomic 12-caller signature migration containing DTO/resolver, both builders,
   N8/N10a transport, root facade/README/public-surface inventory/release
   fragment and all red/green tests. No
   intermediate commit may have a required signature with old callers.
2. Terminal artifact/registry/reference commit only if the frozen declaration
   says candidate bytes differ; it is shared with Cluster 4.

---

## Cluster 2 — exact policy-free full-prefix protocol

**Delivers:** strict proof DTOs, byte-exact canonical frames, full-prefix
builder/verifier, profile/domain isolation, persistence of supplied proof
bundles/results, and two conformance shapes using the real verifier. One shape
is epoch-like; the second is materially non-epoch and test-only.

**Retains:** native denominator completeness, acceptance, purpose-specific
authority, native heads/currentness and writer-independent custody remain
family-owned. The exact terminal matrix is part of the J05 witness: contracts,
builder, verifier and persistence-adapter components are delivered, while the
aggregate common protocol primitive and generic qualification consumer are
`implemented_but_not_orchestrated`; the epoch
producer remains `producer_missing` until Cluster 4; release, run, movement and
confidence producers remain `absent/unallocated`; the accepted-anchor consumer
and writer-independent holder remain `absent/unallocated`; family audit/API/
dashboard projection remains `surface_missing`; and whole-history authenticity
is `not_established` as a property result. This cluster does not satisfy
`CB-J00`. A source-derived test reconciles the complete production call-site,
export and file denominators to that matrix; prose is not its oracle.

**Frozen basis subset (34):** `CB-A01`, `CB-A02`, `CB-A03`, `CB-A04`,
`CB-A05`, `CB-A06`, `CB-A07`, `CB-B01`, `CB-B02`, `CB-B03`, `CB-B05`,
`CB-B06`, `CB-B07`, `CB-B08`, `CB-B10`, `CB-B11`, `CB-B12`, `CB-B13`,
`CB-B14`, `CB-B15`, `CB-B15A`, `CB-B16`, `CB-B17`, `CB-H01`, `CB-H02`,
`CB-H04`, `CB-H05`, `CB-H06`, `CB-H10`, `CB-H11`, `CB-H14`, `CB-H16`,
`CB-H17`, `CB-J05`.

### Task 2.1 — freeze the exact contract and golden vectors

**Add:**

- `src/polisyos/core/contracts/chronology.py`
- `tests/unit/core/contracts/test_chronology.py`
- `tests/repo_quality/test_gy_n12_cluster2_plan_paths.py`

**Modify:**

- `src/polisyos/core/contracts/__init__.py`
- `src/polisyos/core/__init__.py`
- `src/polisyos/core/contracts/README.md`
- `architecture/public_surface/inventory.json`
- `release-fragments/unreleased/2026-08-20-gy-n12-epoch-chronology.toml`
- `docs/reference/public-surface.md`

Chronology wire DTOs are re-exported from the already admitted
`polisyos.core` root facade. `core.contracts` remains an internal implementation
module under the canonical public-surface contract; a package README cannot
promote it. Regenerate/review the public-surface inventory and add the required
`python-public-api` release fragment in the same commit. This is not left to
the executor.

Define strict (`extra="forbid"`, frozen) DTOs. These are the complete public
inputs; implementations may add private helpers but not another wire shape:

```python
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
PredicateClass = Literal[
    "recomputed", "independently_reconciled", "consumer_asserted",
    "institutionally_supplied", "not_established",
]

class PredicateDisposition(BaseModel):
    predicate_id: str
    predicate_class: PredicateClass
    status: Literal["satisfied", "rejected", "not_established"]
    evidence_ref: ArtifactRef | None
    failure_code: str | None

class PredicateAdmissionRule(BaseModel):
    predicate_id: str
    subject_kind: Literal["member", "query"]
    admitted_classes: tuple[
        Literal["recomputed", "independently_reconciled"], ...
    ]
    require_evidence_ref: Literal[True] = True

class PredicatePolicySelectionKey(BaseModel):
    family: str
    proof_domain: str
    scope_ref: Digest
    authority_purpose: str
    requested_cutoff_ref: Digest

class PredicateAdmissionPolicyStatement(BaseModel):
    schema_version: Literal["polisyos.chronology.predicate-policy.v1"]
    key: PredicatePolicySelectionKey
    native_schema_profile: str
    rules: tuple[PredicateAdmissionRule, ...]
    owner_provenance_ref: ArtifactRef
    owner_provenance_content_hash: Digest

class PersistedPredicateAdmissionPolicy(BaseModel):
    policy_ref: ArtifactRef
    policy_content_hash: Digest
    statement: PredicateAdmissionPolicyStatement

class ApplicablePredicateDenominatorStatement(BaseModel):
    schema_version: Literal["polisyos.chronology.applicable-predicate-denominator.v1"]
    policy_ref: ArtifactRef
    policy_content_hash: Digest
    member_subject_refs: tuple[Digest, ...]
    required_member_predicate_pairs: tuple[tuple[Digest, str], ...]
    required_query_predicate_ids: tuple[str, ...]

class PersistedApplicablePredicateDenominator(BaseModel):
    artifact_ref: ArtifactRef
    cas_raw_bytes_hash: Digest
    denominator_content_hash: Digest
    statement: ApplicablePredicateDenominatorStatement

class PredicatePolicyAdmissionStatement(BaseModel):
    schema_version: Literal["polisyos.chronology.predicate-policy-admission.v1"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    native_schema_profile: str
    policy_ref: ArtifactRef
    policy_content_hash: Digest
    owner_relation_ref: ArtifactRef
    owner_relation_content_hash: Digest

class PersistedPredicatePolicyAdmission(BaseModel):
    admission_ref: ArtifactRef
    admission_content_hash: Digest
    statement: PredicatePolicyAdmissionStatement

class ResolvedPredicatePolicyAdmission(BaseModel):
    admission: PersistedPredicatePolicyAdmission
    policy: PersistedPredicateAdmissionPolicy
    owner_relation_verification: VerifiedPredicatePolicyOwnerRelation

class PredicatePolicyResolutionContext(BaseModel):
    query: NativeChronologyQuery
    key: PredicatePolicySelectionKey

class PolicyAdmissionMissingFailure(BaseModel):
    code: Literal["policy_admission_missing"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest

class PolicyAdmissionAmbiguousFailure(BaseModel):
    code: Literal["policy_admission_ambiguous"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest

class PolicyBytesMissingFailure(BaseModel):
    code: Literal["policy_bytes_missing"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    artifact_role: Literal[
        "admission", "policy", "policy_owner_provenance", "owner_relation"
    ]
    missing_ref: ArtifactRef | None

class PolicyBindingMismatchFailure(BaseModel):
    code: Literal["policy_binding_mismatch"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    evidence_ref: ArtifactRef

class PolicyQueryBindingMismatchFailure(BaseModel):
    code: Literal["policy_query_binding_mismatch"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    admitted_query_context_ref: Digest

PredicatePolicyResolutionFailure = Annotated[
    PolicyAdmissionMissingFailure | PolicyAdmissionAmbiguousFailure
    | PolicyBytesMissingFailure | PolicyBindingMismatchFailure
    | PolicyQueryBindingMismatchFailure,
    Field(discriminator="code"),
]

class VerifiedOwnerPredicateEvidence(BaseModel):
    subject_kind: Literal["member", "query"]
    subject_ref: Digest
    predicate_id: str
    predicate_class: PredicateClass
    status: Literal["satisfied", "rejected", "not_established"]
    evidence_ref: ArtifactRef | None
    evidence_content_hash: Digest | None
    evidence_verifier_provenance_ref: ArtifactRef | None

class VerifiedNativeMemberIdentity(BaseModel):
    member_ref: Digest
    native_artifact_ref: ArtifactRef
    native_content_hash: Digest
    native_schema_profile: str
    member_admission_basis_ref: Digest
    member_admission_context_ref: Digest

class VerifiedNativeSubjectIdentity(BaseModel):
    subject_kind: Literal["denominator", "query_context"]
    subject_ref: Digest
    artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_content_hash: Digest
    verifier_provenance_ref: ArtifactRef

class VerifiedPolicyOwnerProvenance(BaseModel):
    policy_ref: ArtifactRef
    policy_content_hash: Digest
    owner_provenance_ref: ArtifactRef
    owner_provenance_content_hash: Digest
    trust_snapshot_ref: ArtifactRef
    trust_snapshot_content_hash: Digest
    verification_receipt_ref: ArtifactRef
    verification_receipt_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class VerifiedPredicatePolicyOwnerRelation(BaseModel):
    query: NativeChronologyQuery
    owner_relation_ref: ArtifactRef
    owner_relation_content_hash: Digest
    owner_verifier_provenance_ref: ArtifactRef
    verification_receipt_ref: ArtifactRef
    verification_receipt_content_hash: Digest
    candidate_content_hash: Digest
    owner_declared_denominator_ref: Digest
    candidate_declared_denominator_ref: Digest
    owner_ordered_member_refs: tuple[Digest, ...]
    candidate_ordered_member_refs: tuple[Digest, ...]
    denominator_identity: VerifiedNativeSubjectIdentity
    query_context_identity: VerifiedNativeSubjectIdentity
    member_identities: tuple[VerifiedNativeMemberIdentity, ...]
    predicate_evidence: tuple[VerifiedOwnerPredicateEvidence, ...]
    policy_owner_provenance: VerifiedPolicyOwnerProvenance
    predicate_class: Literal["independently_reconciled"]

class PolicyOwnerRelationRejected(BaseModel):
    code: Literal["policy_owner_relation_rejected"]
    status: Literal["rejected"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    owner_relation_ref: ArtifactRef
    evidence_ref: ArtifactRef

class PolicyOwnerRelationNotEstablished(BaseModel):
    code: Literal["policy_owner_relation_not_established"]
    status: Literal["not_established"]
    key: PredicatePolicySelectionKey
    requested_query_context_ref: Digest
    owner_relation_ref: ArtifactRef | None

PredicatePolicyOwnerRelationFailure = Annotated[
    PolicyOwnerRelationRejected | PolicyOwnerRelationNotEstablished,
    Field(discriminator="code"),
]

class PredicatePolicyAdmissionIndex(Protocol):
    def enumerate_admission_refs(
        self, *, key: PredicatePolicySelectionKey
    ) -> tuple[ArtifactRef, ...]: ...

class PredicatePolicyOwnerProvenanceVerifier(Protocol):
    def verify_owner_relation(
        self, *, query: NativeChronologyQuery,
        admission: PredicatePolicyAdmissionStatement,
        policy: PersistedPredicateAdmissionPolicy,
        policy_owner_provenance_bytes: bytes,
        owner_relation_bytes: bytes,
        candidate: NativeChronologyCandidate,
    ) -> VerifiedPredicatePolicyOwnerRelation | PredicatePolicyOwnerRelationFailure: ...

class ChronologyPredicatePolicyArtifacts:
    def __init__(self, *, store: ArtifactStore) -> None: ...

    def load_admission(
        self, *, context: PredicatePolicyResolutionContext,
        admission_ref: ArtifactRef,
    ) -> PersistedPredicatePolicyAdmission | PredicatePolicyResolutionFailure: ...

    def load_policy(
        self, *, context: PredicatePolicyResolutionContext,
        policy_ref: ArtifactRef, expected_content_hash: Digest,
    ) -> PersistedPredicateAdmissionPolicy | PredicatePolicyResolutionFailure: ...

    def load_owner_relation_bytes(
        self, *, context: PredicatePolicyResolutionContext,
        relation_ref: ArtifactRef, expected_content_hash: Digest,
    ) -> bytes | PredicatePolicyResolutionFailure: ...

    def load_policy_owner_provenance_bytes(
        self, *, context: PredicatePolicyResolutionContext,
        provenance_ref: ArtifactRef, expected_content_hash: Digest,
    ) -> bytes | PredicatePolicyResolutionFailure: ...

class ApplicablePredicateDenominatorArtifactFailure(BaseModel):
    code: Literal["applicable_predicate_denominator_artifact_not_established"]
    status: Literal["not_established"]
    query: NativeChronologyQuery
    denominator_content_hash: Digest
    evidence_ref: ArtifactRef | None

class ChronologyApplicablePredicateDenominatorArtifacts:
    def __init__(self, *, store: ArtifactStore) -> None: ...

    def persist_and_verify(
        self, *, query: NativeChronologyQuery,
        statement: ApplicablePredicateDenominatorStatement,
        owner_qualified_candidate: OwnerQualifiedNativeCandidate,
    ) -> PersistedApplicablePredicateDenominator \
        | ApplicablePredicateDenominatorArtifactFailure: ...

class MemberPredicateDisposition(BaseModel):
    member_ref: Digest
    disposition: PredicateDisposition

class QueryPredicateDisposition(BaseModel):
    requested_query_context_ref: Digest
    disposition: PredicateDisposition

class ChronologyProofDomain(BaseModel):
    format: Literal["polisyos.chronology.full-prefix.v1"]
    profile: Literal["full_prefix_canon_json_0_2_0_sha256_256_v1"]
    proof_domain: str
    family: str
    scope_ref: Digest
    authority_purpose: str

class ChronologyMemberInput(BaseModel):
    member_ref: Digest
    native_artifact_ref: ArtifactRef
    native_content_hash: Digest
    native_schema_profile: str
    native_bytes: bytes
    member_admission_basis_ref: Digest
    member_admission_context_ref: Digest

class ChronologyBundleRequest(BaseModel):
    domain: ChronologyProofDomain
    native_schema_profile: str
    declared_denominator_ref: Digest
    requested_cutoff_ref: Digest
    requested_query_context_ref: Digest
    members: tuple[ChronologyMemberInput, ...]

class ChronologyBundleHeader(BaseModel):
    format: Literal["polisyos.chronology.full-prefix.v1"]
    profile: Literal["full_prefix_canon_json_0_2_0_sha256_256_v1"]
    proof_domain: str
    family: str
    scope_ref: Digest
    authority_purpose: str
    native_schema_profile: str
    declared_denominator_ref: Digest
    requested_cutoff_ref: Digest
    requested_query_context_ref: Digest
    member_count: int
    native_bytes_total: int
    first_commitment: Digest | None
    commitment_head: Digest

class ExpectedCommitmentPrefix(BaseModel):
    domain: ChronologyProofDomain
    member_count: int
    commitment_head: Digest

class FullPrefixBuildFailureCode(StrEnum):
    PROOF_PROFILE_CAPACITY_EXCEEDED = "proof_profile_capacity_exceeded"

class FullPrefixInvocationFailureCode(StrEnum):
    BUNDLE_CONTENT_HASH_MISMATCH = "bundle_content_hash_mismatch"

class FullPrefixEnvelopeFailureCode(StrEnum):
    BUNDLE_MALFORMED = "bundle_malformed"
    NON_CANONICAL_HEADER = "non_canonical_header"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNKNOWN_PROFILE = "unknown_profile"
    PROOF_DOMAIN_MISMATCH = "proof_domain_mismatch"
    PROOF_PROFILE_CAPACITY_EXCEEDED = "proof_profile_capacity_exceeded"

class FullPrefixMemberFailureCode(StrEnum):
    NON_CANONICAL_MEMBER_FRAME = "non_canonical_member_frame"
    PROOF_PROFILE_CAPACITY_EXCEEDED = "proof_profile_capacity_exceeded"
    NATIVE_CONTENT_HASH_MISMATCH = "native_content_hash_mismatch"
    PREDECESSOR_MISMATCH = "predecessor_mismatch"
    ORDINAL_MISMATCH = "ordinal_mismatch"

class FullPrefixInternalConsistencyFailureCode(StrEnum):
    MEMBER_COUNT_MISMATCH = "member_count_mismatch"
    NATIVE_BYTES_TOTAL_MISMATCH = "native_bytes_total_mismatch"
    FIRST_COMMITMENT_MISMATCH = "first_commitment_mismatch"
    COMMITMENT_HEAD_MISMATCH = "commitment_head_mismatch"

class FullPrefixExpectedPrefixFailureCode(StrEnum):
    DOMAIN_MISMATCH = "expected_prefix_domain_mismatch"
    OUT_OF_RANGE = "expected_prefix_out_of_range"
    HEAD_MISMATCH = "expected_prefix_head_mismatch"

FullPrefixCheckState = Literal[
    "not_requested", "not_evaluated", "satisfied", "rejected"
]

class FullPrefixEvaluationState(BaseModel):
    bundle_content_hash: FullPrefixCheckState
    envelope: FullPrefixCheckState
    members: FullPrefixCheckState
    internal_consistency: FullPrefixCheckState
    expected_prefix: FullPrefixCheckState

class FullPrefixTerminalCheck(StrEnum):
    VERIFIED = "verified"
    BUNDLE_CONTENT_HASH = "bundle_content_hash"
    ENVELOPE = "envelope"
    MEMBERS = "members"
    INTERNAL_CONSISTENCY = "internal_consistency"
    EXPECTED_PREFIX = "expected_prefix"

class FullPrefixInputMode(StrEnum):
    ABSENT = "absent"
    PRESENT = "present"

@dataclass(frozen=True, slots=True)
class FullPrefixFailureDescriptor:
    operation: Literal["verify"]
    phase: Literal[
        "invocation", "envelope", "member", "consistency", "expected_prefix",
    ]
    code: FullPrefixInvocationFailureCode | FullPrefixEnvelopeFailureCode \
        | FullPrefixMemberFailureCode | FullPrefixInternalConsistencyFailureCode \
        | FullPrefixExpectedPrefixFailureCode
    terminal_check: FullPrefixTerminalCheck

@dataclass(frozen=True, slots=True)
class FullPrefixEvaluationKey:
    result_kind: Literal[
        "verified", "invocation_rejected", "envelope_rejected",
        "member_rejected", "internal_consistency_rejected",
        "expected_prefix_rejected",
    ]
    expected_bundle_hash: FullPrefixInputMode
    expected_prefix: FullPrefixInputMode

class EncodedChronologyBundle(BaseModel):
    result_kind: Literal["encoded"]
    bundle_bytes: bytes
    bundle_content_hash: Digest
    header: ChronologyBundleHeader
    member_commitments: tuple[Digest, ...]

class FullPrefixBuildRejected(BaseModel):
    result_kind: Literal["build_rejected"]
    domain: ChronologyProofDomain
    requested_member_count: int = Field(ge=0)
    failure_code: FullPrefixBuildFailureCode

FullPrefixBuildResult = Annotated[
    EncodedChronologyBundle | FullPrefixBuildRejected,
    Field(discriminator="result_kind"),
]

class FullPrefixVerified(BaseModel):
    result_kind: Literal["verified"]
    status: Literal["verified"]
    terminal_check: Literal[FullPrefixTerminalCheck.VERIFIED]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    evaluation_state: FullPrefixEvaluationState

class FullPrefixInvocationRejected(BaseModel):
    result_kind: Literal["invocation_rejected"]
    status: Literal["rejected"]
    phase: Literal["invocation"]
    terminal_check: Literal[FullPrefixTerminalCheck.BUNDLE_CONTENT_HASH]
    bundle_content_hash: Digest
    parsed_header: None = None
    verified_member_count: Literal[0] = 0
    commitment_head: None = None
    failure_codes: Annotated[
        tuple[FullPrefixInvocationFailureCode, ...], Field(min_length=1)
    ]
    evaluation_state: FullPrefixEvaluationState

class FullPrefixEnvelopeRejected(BaseModel):
    result_kind: Literal["envelope_rejected"]
    status: Literal["rejected"]
    phase: Literal["envelope"]
    terminal_check: Literal[FullPrefixTerminalCheck.ENVELOPE]
    bundle_content_hash: Digest
    parsed_header: None = None
    verified_member_count: Literal[0] = 0
    commitment_head: None = None
    failure_codes: Annotated[
        tuple[FullPrefixEnvelopeFailureCode, ...], Field(min_length=1)
    ]
    evaluation_state: FullPrefixEvaluationState

class FullPrefixMemberRejected(BaseModel):
    result_kind: Literal["member_rejected"]
    status: Literal["rejected"]
    phase: Literal["member"]
    terminal_check: Literal[FullPrefixTerminalCheck.MEMBERS]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    failure_codes: Annotated[
        tuple[FullPrefixMemberFailureCode, ...], Field(min_length=1)
    ]
    evaluation_state: FullPrefixEvaluationState

class FullPrefixInternalConsistencyRejected(BaseModel):
    result_kind: Literal["internal_consistency_rejected"]
    status: Literal["rejected"]
    phase: Literal["consistency"]
    terminal_check: Literal[FullPrefixTerminalCheck.INTERNAL_CONSISTENCY]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    failure_codes: Annotated[
        tuple[FullPrefixInternalConsistencyFailureCode, ...], Field(min_length=1)
    ]
    evaluation_state: FullPrefixEvaluationState

class FullPrefixExpectedPrefixRejected(BaseModel):
    result_kind: Literal["expected_prefix_rejected"]
    status: Literal["rejected"]
    phase: Literal["expected_prefix"]
    terminal_check: Literal[FullPrefixTerminalCheck.EXPECTED_PREFIX]
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verified_member_count: int = Field(ge=0)
    commitment_head: Digest
    failure_codes: Annotated[
        tuple[FullPrefixExpectedPrefixFailureCode, ...], Field(min_length=1)
    ]
    evaluation_state: FullPrefixEvaluationState

FullPrefixRejected = Annotated[
    FullPrefixInvocationRejected | FullPrefixEnvelopeRejected
    | FullPrefixMemberRejected
    | FullPrefixInternalConsistencyRejected | FullPrefixExpectedPrefixRejected,
    Field(discriminator="result_kind"),
]

FullPrefixVerificationResult = Annotated[
    FullPrefixVerified | FullPrefixInvocationRejected
    | FullPrefixEnvelopeRejected
    | FullPrefixMemberRejected | FullPrefixInternalConsistencyRejected
    | FullPrefixExpectedPrefixRejected,
    Field(discriminator="result_kind"),
]

class FullPrefixVerificationStatement(BaseModel):
    schema_version: Literal[
        "polisyos.chronology.full-prefix-verification-result.v1"
    ]
    bundle_ref: ArtifactRef
    expected_domain: ChronologyProofDomain
    expected_prefix: ExpectedCommitmentPrefix | None
    expected_bundle_content_hash: Digest | None
    result: FullPrefixVerificationResult

class PersistedChronologyProof(BaseModel):
    result_kind: Literal["persisted"]
    artifact_ref: ArtifactRef
    cas_raw_bytes_hash: Digest
    protocol_bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    verifier_result_ref: ArtifactRef
    verifier_result_content_hash: Digest
    verification_statement: FullPrefixVerificationStatement

class ChronologyPersistenceManifestMismatch(BaseModel):
    failure_kind: Literal["manifest_mismatch"]
    disposition: Literal["rejected"]
    query: NativeChronologyQuery
    artifact_role: Literal["bundle", "verification_result"]
    artifact_ref: ArtifactRef
    expected_manifest_content_hash: Digest
    observed_manifest_content_hash: Digest

class ChronologyPersistenceVerificationMismatch(BaseModel):
    failure_kind: Literal["verification_mismatch"]
    disposition: Literal["rejected"]
    query: NativeChronologyQuery
    proof_result: FullPrefixRejected

class ChronologyPersistenceStoreIntegrityMismatch(BaseModel):
    failure_kind: Literal["store_integrity_mismatch"]
    disposition: Literal["rejected"]
    query: NativeChronologyQuery
    artifact_role: Literal["bundle", "verification_result"]
    artifact_ref: ArtifactRef
    expected_raw_cas_hash: Digest
    observed_raw_cas_hash: Digest
    verification_report_content_hash: Digest

class ChronologyPersistenceNotEstablished(BaseModel):
    failure_kind: Literal["not_established"]
    disposition: Literal["not_established"]
    query: NativeChronologyQuery
    code: Literal[
        "artifact_store_not_established", "bundle_write_not_established",
        "verification_result_write_not_established",
        "persistence_process_generation_not_established",
    ]
    evidence_ref: ArtifactRef | None

ChronologyPersistenceFailure = Annotated[
    ChronologyPersistenceManifestMismatch
    | ChronologyPersistenceVerificationMismatch
    | ChronologyPersistenceStoreIntegrityMismatch
    | ChronologyPersistenceNotEstablished,
    Field(discriminator="failure_kind"),
]

class ChronologyProofPersistenceFailed(BaseModel):
    result_kind: Literal["persistence_failed"]
    failure: ChronologyPersistenceFailure

ChronologyProofPersistenceResult = Annotated[
    PersistedChronologyProof | ChronologyProofPersistenceFailed,
    Field(discriminator="result_kind"),
]

class NativeChronologyQuery(BaseModel):
    domain: ChronologyProofDomain
    requested_cutoff_ref: Digest
    requested_query_context_ref: Digest

class NativeChronologyCandidate(BaseModel):
    query: NativeChronologyQuery
    declared_denominator_ref: Digest
    native_denominator_artifact_ref: ArtifactRef
    native_denominator_content_hash: Digest
    query_context_artifact_ref: ArtifactRef
    query_context_content_hash: Digest
    ordered_members: tuple[ChronologyMemberInput, ...]
    member_predicates: tuple[MemberPredicateDisposition, ...]
    query_predicates: tuple[QueryPredicateDisposition, ...]
    exterior_limitation_code: str | None
    native_authority_head_refs: tuple[Digest, ...]

class OwnerQualifiedNativeCandidate(BaseModel):
    candidate: NativeChronologyCandidate
    candidate_content_hash: Digest
    owner_relation_verification: VerifiedPredicatePolicyOwnerRelation

class NativeChronologyOwnerContext(BaseModel):
    query: NativeChronologyQuery
    owner_qualified_candidate: OwnerQualifiedNativeCandidate
    policy_admission_ref: ArtifactRef
    policy_admission_content_hash: Digest
    predicate_admission_policy_ref: ArtifactRef
    predicate_admission_policy_content_hash: Digest

class NativeChronologyReconciliation(BaseModel):
    owner_context: NativeChronologyOwnerContext
    authoritative_native_schema_profile: str
    applicable_predicate_denominator: PersistedApplicablePredicateDenominator

class NativeChronologyQualified(BaseModel):
    result_kind: Literal["qualified"]
    reconciliation: NativeChronologyReconciliation
    proof_result: FullPrefixVerified
    persisted_proof: PersistedChronologyProof

class NativeFullPrefixBuildRejected(BaseModel):
    result_kind: Literal["build_rejected"]
    reconciliation: NativeChronologyReconciliation
    build_result: FullPrefixBuildRejected

class NativeSchemaProfileRejected(BaseModel):
    result_kind: Literal["profile_rejected"]
    code: Literal["native_schema_profile_mismatch"]
    owner_context: NativeChronologyOwnerContext
    expected_profile: str
    observed_profiles: tuple[str, ...]

class NativeDenominatorRejected(BaseModel):
    result_kind: Literal["denominator_rejected"]
    code: Literal["native_denominator_mismatch"]
    owner_context: NativeChronologyOwnerContext
    expected_denominator_ref: Digest
    observed_denominator_ref: Digest

class NativePredicateRejected(BaseModel):
    result_kind: Literal["predicate_rejected"]
    code: Literal["native_predicate_inadmissible"]
    owner_context: NativeChronologyOwnerContext
    evidence_refs: tuple[ArtifactRef, ...]

class NativeFullPrefixProofRejected(BaseModel):
    result_kind: Literal["proof_rejected"]
    code: Literal["full_prefix_proof_rejected"]
    reconciliation: NativeChronologyReconciliation
    proof_result: FullPrefixRejected

NativeChronologyCandidateRejected = (
    NativeSchemaProfileRejected | NativeDenominatorRejected
    | NativePredicateRejected | NativeFullPrefixProofRejected
)

class NativeExteriorNotEstablished(BaseModel):
    result_kind: Literal["native_exterior_not_established"]
    code: Literal["native_exterior_not_established"]
    reconciliation: NativeChronologyReconciliation
    exterior_limitation_code: str
    proof_result: FullPrefixVerified

class NativeAuthorityHeadNotEstablished(BaseModel):
    result_kind: Literal["native_authority_head_not_established"]
    code: Literal["native_authority_head_not_established"]
    reconciliation: NativeChronologyReconciliation
    required_native_head_role: str
    proof_result: FullPrefixVerified

class NativeExteriorAndAuthorityHeadNotEstablished(BaseModel):
    result_kind: Literal[
        "native_exterior_and_authority_head_not_established"
    ]
    reconciliation: NativeChronologyReconciliation
    exterior_limitation_code: Annotated[str, Field(min_length=1)]
    required_native_head_role: Annotated[str, Field(min_length=1)]
    proof_result: FullPrefixVerified

class NativeProjectionCustodyGap(BaseModel):
    result_kind: Literal["projection_custody_gap"]
    status: Literal["native_not_established"]
    code: Literal["native_projection_custody_gap"]
    reconciliation: NativeChronologyReconciliation
    proof_result: FullPrefixVerified
    missing_projection_receipt_role: Literal["native_projection_receipt"]

class NativeChronologyPolicyResolutionFailed(BaseModel):
    result_kind: Literal["policy_resolution_failed"]
    query: NativeChronologyQuery
    failure: PredicatePolicyResolutionFailure | PredicatePolicyOwnerRelationFailure

class NativeApplicablePredicateDenominatorPersistenceFailed(BaseModel):
    result_kind: Literal["predicate_denominator_persistence_failed"]
    owner_context: NativeChronologyOwnerContext
    failure: ApplicablePredicateDenominatorArtifactFailure

class NativeChronologyPersistenceFailed(BaseModel):
    result_kind: Literal["persistence_failed"]
    reconciliation: NativeChronologyReconciliation
    failure: ChronologyPersistenceFailure

NativeChronologyQualificationResult = Annotated[
    NativeChronologyQualified | NativeFullPrefixBuildRejected
    | NativeSchemaProfileRejected
    | NativeDenominatorRejected | NativePredicateRejected
    | NativeFullPrefixProofRejected
    | NativeExteriorNotEstablished | NativeAuthorityHeadNotEstablished
    | NativeExteriorAndAuthorityHeadNotEstablished
    | NativeProjectionCustodyGap
    | NativeChronologyPolicyResolutionFailed
    | NativeApplicablePredicateDenominatorPersistenceFailed
    | NativeChronologyPersistenceFailed,
    Field(discriminator="result_kind"),
]
```

The module uses `from __future__ import annotations`; every forward-referenced
DTO is rebuilt once after definition and its generated schema is contract
tested. All DTOs are strict/frozen. Digests share one lowercase normalization; counts
are non-negative and cap-checked; `failure_code` is required exactly when the
status is not satisfied. Every member predicate is keyed by the exact
`member_ref`; every query predicate is keyed by the requested query context;
and `(subject, predicate_id)` is unique. The native authority—not the adapter—
persists a unique admission relation keyed only by
family/proof-domain/scope/purpose/cutoff. That relation selects both the native
schema profile and exact policy; neither the query nor adapter proposes either.
`NativeChronologyQuery` therefore remains profile-, policy-ref- and
policy-version-free. `PredicatePolicyAdmissionIndex` enumerates the exact owner
key and zero or multiple rows fail closed, including at zero members.
The consumer constructs one immutable `PredicatePolicyResolutionContext` from
the full query and derived key and passes it to every byte loader; unreadable
bytes therefore cannot erase or reconstruct their query coordinate.
`ChronologyPredicatePolicyArtifacts` calls live `ArtifactStore.verify`,
requires its positive report, reloads exact admission, policy, policy-owner-
provenance and opaque owner-relation bytes, reparses the fixed
prefix/frame/CanonSpec representation and recomputes both CAS and semantic
hashes. It has no injectable decoder or hash callback. A shaped inline policy,
an arbitrary valid CAS blob standing in for owner provenance, missing/swapped
bytes or an ambiguous index cannot reach the adapter. The exact sequence is:
load and verify the unique admission, policy, policy-provenance and relation
bytes; obtain the native candidate; invoke
`PredicatePolicyOwnerProvenanceVerifier` with all four verified inputs and that
candidate; and only then qualify it. The verifier owns the family-native
canonical-denominator resolver, native subject-artifact resolver, policy
trust-snapshot resolver and disposition-evidence resolver; none is supplied on
the request. It re-enumerates the owner's complete denominator from the query,
then reloads, content-verifies and provenance-verifies the denominator,
query-context artifact, policy-owner provenance and every non-null disposition
evidence ref. Its positive receipt binds one independently verified policy-
provenance receipt, the full query, owner and candidate denominator refs, both
ordered-member sequences, exact denominator/query subject identities and an
exact subject/predicate/evidence row for every candidate disposition. It also binds
`candidate_content_hash = sha256("polisyos.chronology.owner-qualified-native-candidate.v1\\0"
|| frame(C(candidate raw mapping)))`; that mapping contains every candidate
field, including exact native bytes/content hashes/artifact refs, schema and
admission refs, query/cutoff/context, exterior limitation and native heads.
Each `member_ref` is reconciled to one `VerifiedNativeMemberIdentity`, and the
owner verifier reloads its artifact and requires the exact native bytes/hash.
The denominator and query context are separately reconciled to one
`VerifiedNativeSubjectIdentity` each; those rows bind semantic subject ref,
raw artifact ref/hash, semantic content hash and verifier provenance. Candidate
fields and persistence-manifest inputs must equal those receipt-owned rows,
never merely another caller-selected role-correct artifact.
The three optional evidence fields are all present or all absent;
for an authority-positive row they are all present and the evidence class is
`recomputed` or `independently_reconciled`. A caller-shaped evidence ref, an
unknown artifact, a narrowed candidate denominator, unequal owner/candidate
member sequences or relation bytes binding a different member set cannot
produce the only admissible
`independently_reconciled` receipt.

`OwnerQualifiedNativeCandidate` has a model validator that recomputes that
canonical hash, requires it to equal the persisted owner-verification receipt,
and requires every direct owner/candidate denominator/member comparison in the
receipt to agree. Final reconciliation embeds this one qualified object instead
of copying its fields beside the receipt. `PredicateAdmissionPolicyStatement`
itself binds the policy owner's provenance ref; no positive provenance exists
only on an unverified wrapper.

The consumer requires every member profile, the eventual bundle/header profile
and policy profile to equal the owner-selected value. It recomputes the cross-product of every
ordered member with every member rule plus every query rule.
The concrete `ChronologyApplicablePredicateDenominatorArtifacts` owns the
fixed codec/write options and canonical `ArtifactStore`, persists the
statement, reloads/verifies exact bytes and returns a typed failure on missing
or mismatched storage; the consumer has no implicit writer or Protocol-only
test-double positive path. Its unit test writes, reloads and corrupts the exact
denominator bytes through the live store contract. An authority-positive reconciliation requires a
four-way bijection across that denominator, resolved policy rules, candidate
dispositions and verified owner-evidence rows, with a `satisfied` disposition
in one of each rule's admitted classes and a non-null content-bound artifact
ref/hash/verifier-provenance triple. Missing,
duplicate, cross-subject, `consumer_asserted`, `institutionally_supplied` or
`not_established` rows fail closed. `native_authority_head_refs=()` means the
family has no native head and is not a fabricated null head.
Every policy-resolution negative carries the full query. Every post-policy
leaf carries either `NativeChronologyOwnerContext` or the completed
`NativeChronologyReconciliation`; both bind the query, policy admission bytes,
owner-qualified candidate and policy bytes. Denominator persistence is its own
post-owner leaf and cannot be laundered back into query-only policy failure.

The native-limitation decision is a frozen two-bit mask derived after a
verified prefix: bit 1 is a non-null exterior limitation and bit 2 is an
owner-policy-required authority head with an empty candidate head tuple. Mask
0 alone proceeds to projection; mask 1 emits `NativeExteriorNotEstablished`;
mask 2 emits `NativeAuthorityHeadNotEstablished`; mask 3 emits
`NativeExteriorAndAuthorityHeadNotEstablished` and preserves both facts.
Projection custody is evaluated only for mask 0, so it never erases or competes
with a native limitation. Persistence is evaluated only after mask 0 and a
positive projection receipt. Model validators derive the mask rather than
accepting it, reject every inverse combination, and require the combined leaf
at mask 3.

A single ordered native transition table covers policy resolution, owner
relation, schema profile, native denominator, predicate reconciliation,
denominator persistence, bundle build, proof verification, all four limitation
masks, projection, persistence and qualified. A generated source/schema walk
bijects its terminals to `NativeChronologyQualificationResult`, so an off-union
or stale symbol cannot be emitted. Every nested failure carries the exact requested-query-context
ref, and a query-binding mismatch carries both admitted and requested refs.
Validators require all copies to agree, so two same-key failures at different
native query coordinates cannot serialize as the same result.
Admission, policy and denominator bytes use the same raw-mapping CanonSpec and
exact framing as the proof profile, under
`polisyos.chronology.predicate-policy-admission.v1\0`,
`polisyos.chronology.predicate-policy.v1\0` and
`polisyos.chronology.applicable-predicate-denominator.v1\0`; the policy
statement's owner-provenance field is inside the second preimage. Freeze 0/1
golden vectors and reject duplicate relations/rules/subjects before hashing.
The denominator digest is
`sha256(prefix || frame(C(ApplicablePredicateDenominatorStatement)))`; only the
persisted wrapper contains raw CAS identity and semantic digest, so the
preimage is non-self-referential and independently reproducible.
Installing two valid profiles and having the adapter nominate the lax one must
still select the strict owner row or reject; deleting all members cannot make
profile selection impossible or caller-defined.

Full-prefix failures are one closed ordered operation/phase/check algebra, not
independent per-case validators. Builder input is already strict/canonical, so
its sole runtime failure is the profile-capacity leaf; it cannot emit a
verifier-only prefix or parsing code. The verifier evaluates raw expected-
bundle hash, envelope, members, internal consistency and expected prefix in
that order.

The frozen `FULL_PREFIX_FAILURE_DESCRIPTORS` bijects every member of the five
verifier failure enums to `(operation, phase, code, terminal_check)`. A
separate `FULL_PREFIX_TERMINAL_BY_RESULT_KIND` maps every discriminated result
kind to its one terminal; callers cannot select it. The independently derived
`FULL_PREFIX_EVALUATION_TABLE` has exactly twenty rows: invocation rejection
2, envelope rejection 4, member rejection 4, internal-consistency rejection
4, expected-prefix rejection 2 and verified 4. Its key is only result kind
plus expected-bundle-hash and expected-prefix presence. All construction goes
through one `_build_full_prefix_result(...)` factory, and the concrete ordered
check graph must lower to the same twenty rows.

`FullPrefixEvaluationState` records `not_requested`, `not_evaluated`,
`satisfied` or `rejected` for every stage. An absent optional input remains
`not_requested` even after an earlier rejection; only a present later input
becomes `not_evaluated`. Thus a wrong expected hash with
`expected_prefix=None` has one state: hash rejected, required later checks not
evaluated, prefix not requested. A wrong supplied hash rejects at invocation
even when the bytes are malformed. Envelope rejection has no parsed header or
head and count zero; member rejection carries the exactly processed prefix;
internal-consistency rejection has processed every declared member; and
expected-prefix rejection is its own discriminated leaf. No shape can mix an
internal-consistency code with an expected-prefix code while naming one
terminal.

`bundle_content_hash_mismatch` is reachable only when the caller supplies the
expected digest. Code text such as `proof_profile_capacity_exceeded` may recur
in build/envelope/member contexts; its unique identity is
`(operation, phase, code)`. Each result's codes are unique and enum-ordered.
A verified leaf has no failure field; every rejected leaf has a nonempty tuple
from exactly its own enum. Header/count/aggregate capacity rejects at envelope,
an oversized member frame rejects at member, and no cap falls through.
Computed commitments are absent from the frozen member frame, so there is no
unreachable `member_commitment_mismatch` leaf.

`FullPrefixVerificationStatement` derives its table key from optional-input
presence and the discriminated result and requires exact state equality. A
present prefix after an earlier failure is not evaluated; an absent prefix is
not requested. Verified results satisfy every requested predicate. Falsifiers
cover all twenty rows, remove/duplicate a descriptor or table row, attempt a
mixed internal/prefix tuple, substitute a synonym code, and combine malformed
bytes with wrong expected hash and absent/present prefix. Enums, constructors,
ordered graph, table and behavioral denominator reconcile exactly.

The qualification transition graph is total across owner qualification,
denominator persistence, build, verification, native limitations, projection
and persistence. A build-cap failure becomes exactly
`NativeFullPrefixBuildRejected`; a verifier rejection becomes exactly
`NativeFullPrefixProofRejected`; a first-writer manifest mismatch,
post-write verification mismatch or unavailable store/write becomes exactly
`NativeChronologyPersistenceFailed`; and only a verified, reloaded persistence
result becomes `NativeChronologyQualified`. Every post-policy leaf binds the
full query and policy-admission ref. Present-but-wrong evidence is `rejected`;
missing/unreadable institutional or store evidence is `not_established`.
For `ArtifactStore.verify`, `ok=True` continues, `ok=False` with no observed
digest becomes query-bound `not_established`, and `ok=False` with an observed
digest becomes `ChronologyPersistenceStoreIntegrityMismatch`; free-form report
text is content-bound but never selects disposition. The artifact reader uses
that same exhaustive mapping and has no third interpretation of a negative
verification report.
There is no persistence-authority leaf reachable from a public capability
argument. A generated transition table reconciles every
builder/verifier/persistence result kind to exactly one final qualification
leaf; invalid authority state plus malformed bytes cannot escape or select two
leaves.

Required attacks include simultaneous exterior/required-head limitations,
projection absence beside each mask, denominator persistence failure after a
positive owner receipt, missing versus present-corrupt store evidence, deleting
one transition while retaining its result marker, and the exact transition-
table/result-union bijection.

The member frame and header contain exactly the fields frozen in Cycle 5. Use
the complete `CanonSpec` from the design—not only name/version—over freshly
constructed raw mappings, never BaseModel/dataclass input. Define all four
domain prefixes, `uint64_be(length) || bytes` framing, lowercase digests,
1,024-byte member-frame / 4,096-byte header / 2,500,000-member / 4-GiB caps,
zero-member genesis/null head, and independent 0/1/2 golden vectors.

Tests must prove BaseModel/dataclass/mapping inputs cannot choose different
null encodings, an inapplicable CTM role may be absent, member context at C1 is
not rebound by query context C2, and every unknown field/profile fails closed.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/core/contracts/test_chronology.py \
  tests/repo_quality/test_gy_n12_cluster2_plan_paths.py
```

### Task 2.2 — implement one real streaming verifier

**Add:**

- `src/polisyos/core/security/full_prefix.py`
- `tests/unit/core/security/test_full_prefix.py`

**Modify:**

- `src/polisyos/core/security/__init__.py`
- `src/polisyos/core/__init__.py`
- `src/polisyos/core/security/README.md`
- `architecture/public_surface/inventory.json`
- `release-fragments/unreleased/2026-08-20-gy-n12-epoch-chronology.toml`
- `docs/reference/public-surface.md`

`FullPrefixVerifier`, the builder and result are re-exported through the
already admitted `polisyos.core` root facade; `core.security` stays internal.
Regenerate/review the public inventory and public-API release fragment with the
same atomic public-surface commit.

Implement only these proof operations:

```python
def build_full_prefix_bundle(
    request: ChronologyBundleRequest,
) -> FullPrefixBuildResult: ...

class FullPrefixVerifier:
    def verify_bundle(
        self,
        bundle_bytes: bytes,
        *,
        expected_domain: ChronologyProofDomain,
        expected_prefix: ExpectedCommitmentPrefix | None = None,
        expected_bundle_content_hash: Digest | None = None,
    ) -> FullPrefixVerificationResult: ...
```

The verifier streams exact native bytes and recomputes native hashes, member
commitments, genesis, canonical header, first/head, ordinals, counts/caps and
full-bundle digest. When `expected_prefix` is present, it checks only that the
same domain's commitment at `member_count - 1` equals the supplied prefix head
(or genesis at zero). It never accepts parameters or result fields named
`accepted`, `authority_head`, `current`, `complete` or `lineage`: consumer
acceptance is Cluster 3 and denominator/native-head authority is an adapter.
It may reuse canonical/hash primitives, but must not promote
`core.security.ChainVerifier`, which verifies only interior continuity of a
supplied audit segment.

When `expected_bundle_content_hash` is non-null, the verifier recomputes and
compares that same-domain protocol digest; when it is null no mismatch code is
issuable. This optional expected value is distinct from the raw CAS identity
and makes the consistency code reachable without making persistence metadata a
proof predicate.

Proof status has exactly two meanings. `verified` means the supplied bytes are
well-formed under the declared proof domain and internally reproduce their
full prefix; when `expected_prefix` is supplied it also matches that prefix.
`rejected` covers malformed bytes, unknown profile/domain, cap breach, digest/
chain disagreement, or expected-prefix mismatch. No expected prefix is a valid
bytes-only verification relative to the bundle's supplied head, not a
limitation or completeness claim. Exterior/native incompleteness belongs only
to `NativeChronologyReconciliation`; acceptance/custody absence belongs only to
Cluster 3. The verifier has no `limited` status with which those owners could
be recombined.

Write red tests for 0/1/2, extension, deletion including tail/prefix narrowing,
substitution with markers preserved, reorder, proof-domain/profile/scope replay,
unknown profile, cap crossing, changed native bytes with unchanged declared
hash, expected bundle-hash mismatch, malformed bytes plus wrong expected hash
rejecting at invocation with later predicates not evaluated, and removal of actual consistency code
while markers remain. Constructor tests require each build/invocation/envelope/
member/consistency code to be accepted only by its own `(operation, phase)` result,
reject every cross-phase code/evaluation-state pair, and reject contradictory
header/count/head combinations.

This task tests bytes only. The two authority-adapter shapes belong to Task 2.4
so the verifier cannot acquire policy while satisfying B10/B11/B16.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q tests/unit/core/security/test_full_prefix.py
"${GY_N12_RUN[@]}" - <<'PY'
from tools.devx.architecture import guardrails

policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
families = guardrails._parse_public_generated_artifact_families(
    guardrails.DEFAULT_PUBLIC_MANIFEST
)
inventory = guardrails.build_public_surface_inventory(policies)
guardrails._write_if_changed(
    guardrails.DEFAULT_PUBLIC_JSON,
    guardrails.render_public_surface_json(
        inventory, generated_artifact_families=families
    ),
)
guardrails._write_if_changed(
    guardrails.DEFAULT_PUBLIC_MD,
    guardrails.render_public_surface_markdown(inventory),
)
PY
"${GY_N12_RUN[@]}" -m tools.cli architecture guardrails check
```

The narrow writer and check run after both root-facade edits and before the Tasks
2.1–2.2 atomic commit. The generated inventory/reference and release fragment
must be in that exact boundary; Cluster 1's earlier sync is not evidence for
these bytes.

### Task 2.3 — persist protocol artifacts without owning native history

**Add:**

- `src/polisyos/runtime/quality/chronology_proof.py`
- `tests/unit/runtime/quality/test_chronology_proof.py`

**Modify:**

- `src/polisyos/runtime/quality/README.md`

Do **not** introduce `ChronologyProofStore`. Adapt the existing
`core.artifacts.ArtifactStore` protocol (`put_bytes`, `get_bytes`,
`get_manifest`, `verify`):

```python
class ChronologyProofArtifactNotEstablished(BaseModel):
    status: Literal["not_established"]
    code: Literal["chronology_proof_artifact_not_established"]
    query: NativeChronologyQuery
    bundle_ref: ArtifactRef

class ChronologyProofArtifactReader:
    def __init__(self, *, store: ArtifactStore) -> None: ...
    def load_and_verify(
        self,
        *,
        query: NativeChronologyQuery,
        bundle_ref: ArtifactRef,
        expected_domain: ChronologyProofDomain,
        expected_prefix: ExpectedCommitmentPrefix | None,
        expected_bundle_content_hash: Digest,
    ) -> FullPrefixVerificationResult | ChronologyProofArtifactNotEstablished \
        | ChronologyPersistenceManifestMismatch \
        | ChronologyPersistenceStoreIntegrityMismatch: ...

@dataclass(frozen=True, slots=True)
class _ChronologyProcessGeneration:
    creator_pid: int
    nonce: object

@dataclass(frozen=True, init=False, eq=False, slots=True, weakref_slot=True)
class _QualificationPersistenceContinuation:
    """Fieldless process-local continuation; never importable or serialized."""

    def __reduce_ex__(self, protocol: int) -> NoReturn: ...
```

There is no module-level persistence factory, writer or callable that accepts a
store, verifier, positive reconciliation or token. The no-argument
`QualificationConsumer.from_current_owner_container()` resolves the canonical
owner-held dependency factories from a private process composition registry;
that registry never retains a live inherited `ArtifactStore` or verifier.
Registry appointment, each consumer and each continuation bind one opaque
`_ChronologyProcessGeneration`. The owner registry constructs fresh live
dependencies for that generation and the consumer records their exact identity;
an absent appointment is retained inside the consumer so the first `qualify`
returns a query-bound typed policy-resolution non-receipt. Its
`qualify` method defines the persistence closure locally, mints the private
continuation only after constructing the reconciliation, and consumes it in
the same stack frame.  Test stores/verifiers are installed only by a
test-package fixture through a test-only owner appointment; no production
constructor accepts them. Each hidden entry binds the exact query,
reconciliation, owner receipt, persisted denominator, bundle and verified
proof; creator PID; an opaque process-generation object; and
`issued -> borrowed -> spent` under one `RLock`. The one owner-registry fork
participant acquires before fork, releases in the parent, and in the child
replaces every registry lock, rotates the process generation, clears live
stores/verifiers and appointments, and tombstones inherited consumers and
continuations. PID/generation is checked before adapter, payload or store
access. An inherited consumer returns query-bound
`qualification_process_generation_not_established`; a fresh child consumer
remains unavailable until a child-local appointment constructs a demonstrably
fresh store/verifier instance. Copy, pickle,
forgery, reuse, concurrent borrow, fork after issue, fork while borrowed and
bundle/query/hash disagreement perform zero `ArtifactStore` calls. A fresh
post-fork process may construct fresh dependencies only through that child-local
appointment; inherited dependencies are poisoned even when no continuation was
minted before the fork. Release and GC are idempotent. Tests fork immediately
after consumer construction and while a live store lock is held, require zero
child store calls, and prove that child reappointment uses a different live
store identity.

Neither the lease nor hidden payload is a BaseModel field, return DTO,
manifest, sidecar or serialized byte. The positive result carries only the
persisted proof. A complete schema/type-hint/export and production-call census
requires zero exposed token/kernel/writer surfaces, one factory call and one
consumer. A paired rogue coordinator/store cannot be injected because the
production composition root exposes only the already-built
`QualificationConsumer`.

The coordinator accepts no `ArtifactWriteOptions`. It constructs fixed internal
write contracts: bundle kind `core.chronology.full_prefix.bundle`, media type
`application/octet-stream`, schema
`polisyos.chronology.FullPrefixBundle@1`; result kind
`core.chronology.full_prefix.verification_result`, the same media type, and
schema `polisyos.chronology.FullPrefixVerificationResult@1`. Result bytes are
`frame(C(FullPrefixVerificationStatement raw mapping))`; that statement binds
the bundle ref, expected proof domain, nullable expected prefix, expected
protocol bundle-content hash and exact discriminated result. Its semantic hash uses
`polisyos.chronology.full-prefix-verification-result.v1\0`; and the result
manifest has exactly one `InputRef` to the bundle with role `verified_bundle`.
The bundle manifest's inputs are derived—not supplied—from the exact hidden
owner-qualified payload: one owner-qualification receipt, one native
denominator, one query-context artifact and one native artifact per ordered
member, under those four closed role strings. Policy admission/provenance is
bound inside the verified owner receipt and is not duplicated as caller-shaped
common lineage. Caller code supplies no input list, kind, schema, canon,
governance or authority metadata.

Before constructing that manifest the coordinator borrows its private lease,
then reloads and verifies the owner receipt, denominator, query-context and
every member artifact. It reparses the
bundle and requires its domain/profile, denominator ref, query-context ref,
ordered member refs and recomputed native-content hashes to equal the qualified
candidate byte for byte. Denominator and query artifacts must equal the
receipt-owned `VerifiedNativeSubjectIdentity` rows; each member must equal its
`VerifiedNativeMemberIdentity`. Each derived `InputRef.artifact_id` therefore
comes from an independently verified subject row, not merely a candidate field
or caller role. A caller cannot attach an unrelated existing artifact under a
plausible role. A valid bundle with one swapped member/denominator/query
artifact, a semantic-subject/artifact mismatch or a forged qualification
receipt fails before `put_bytes`.

For both writes the coordinator constructs the complete deterministic manifest
template before calling `put_bytes`. After every put—and on every load—it calls
`get_manifest`, copies only the store-minted `created_at` instance coordinate
into that template, and requires full typed equality. No other observed field
is copied. The comparison therefore covers kind, schema, media type, byte size,
integrity, producer, ordered inputs, CanonSpec, authority, closure and every
optional field while correctly treating creation time as non-decisive store
instance metadata. It also recomputes the canonical full-manifest content hash,
including that timestamp. A pre-existing raw blob deduplicated under a
different first-writer manifest yields `ChronologyPersistenceManifestMismatch`; CAS
byte integrity alone is never accepted as lineage or authority.

The private persistence call invokes the real verifier before `put_bytes`. It carries
two deliberately distinct identities: `ArtifactRef.artifact_id`/
`cas_raw_bytes_hash` is the canonical CAS SHA-256 of the raw bundle bytes,
while `protocol_bundle_content_hash` is SHA-256 over
`polisyos.chronology.bundle.v1\0 || bundle_bytes`. They are never compared for
equality. After `put_bytes`, reload exact CAS bytes, recompute both identities,
reparse header and commitments, rerun the verifier with all three expected
inputs, and persist the exact verifier-result statement sidecar. A verification
or manifest rejection writes no result sidecar. Only raw bundle bytes
cross this API; fields from an `EncodedChronologyBundle` are never authority.
`ChronologyProofArtifactReader.load_and_verify` also receives the full query,
requires `store.verify(...)` success, recomputes the raw CAS
identity from loaded bytes, separately recomputes the protocol bundle hash and
runs the real verifier with the expected domain, prefix and protocol digest.
Every not-established reader result carries the input query. A persisted verification result is audit data only and
is never a green input. The adapter stores only common bundle/result bytes;
family-native payload/history remains in its owner store. Tests include the
divergent-domain case where both correct digests differ, caller-controlled
write metadata, valid bytes paired with forged wrapper fields, pre-seeded
identical bytes under wrong first-writer kind/schema/lineage, wrong sidecar
input lineage, changed expected-prefix statement, role-correct but subject-
wrong member/denominator/query artifacts and sidecar substitution. Additional
falsifiers prove a serialized `OwnerQualifiedNativeCandidate` cannot cross
the persistence seam, a second/sibling factory is found by the complete
census, a paired rogue owner container cannot construct the consumer, and
forged/copied/spent/fork-inherited continuations perform zero store calls.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/runtime/quality/test_chronology_proof.py \
  tests/unit/core/contracts/test_chronology.py \
  tests/unit/core/security/test_full_prefix.py
"${GY_N12_RUN[@]}" -m ruff check \
  src/polisyos/core/contracts/chronology.py \
  src/polisyos/core/security/full_prefix.py \
  src/polisyos/runtime/quality/chronology_proof.py \
  tests/unit/core/contracts/test_chronology.py \
  tests/unit/core/security/test_full_prefix.py \
  tests/unit/runtime/quality/test_chronology_proof.py
```

### Task 2.4 — prove policy separation with two authority shapes

**Add:**

- `architecture/production_quality/chronology_capability_allocation.toml`
- `src/polisyos/runtime/quality/chronology_qualification.py`
- `tests/_helpers/chronology_qualification.py`
- `tests/unit/runtime/quality/test_chronology_qualification.py`
- `tests/integration/runtime_quality/test_chronology_protocol_conformance.py`
- `tests/repo_quality/test_chronology_terminal_state.py`

**Modify:**

- `src/polisyos/runtime/quality/README.md`

The production-internal qualification consumer owns policy resolution; the
helper contains only the two native adapters and test owner doubles. Cluster
4's epoch adapter implements the exact authority seam:

```python
class NativeChronologyAuthorityAdapter(Protocol):
    def reconcile_candidate(
        self, request: NativeChronologyQuery
    ) -> NativeChronologyCandidate: ...

class QualificationConsumer:
    @classmethod
    def from_current_owner_container(
        cls,
    ) -> QualificationConsumer: ...

    def qualify(
        self, *, adapter: NativeChronologyAuthorityAdapter,
        request: NativeChronologyQuery,
    ) -> NativeChronologyQualificationResult: ...
```

`NativeChronologyReconciliation` carries the immutable complete denominator
ref, ordered native members, the opaque requested-query-context ref, predicate
classes/results, typed exterior limitation and optional **native** authority
heads. It never enters the common header except through opaque refs.

Implement two helpers using the production builder, sealed persistence
coordinator and verifier:

1. `EpochLikeQualificationAdapter`: valid/effect + visibility/knowledge roles,
   semantic `epoch_ref`, two incomparable native branches and a native
   authority head.
2. `OpaqueInventoryQualificationAdapter`: immutable inventory records with no
   epoch, fork, native clock or authority head. It is not named release/run/
   movement/confidence and creates no production producer.

`QualificationConsumer.qualify(...)` is a production-internal common consumer
with no production family call site yet, so it is
`implemented_but_not_orchestrated`. The adapter cannot supply a policy/
admission ref or select a profile. The consumer first derives one immutable
resolution context, enumerates the unique owner admission and reloads exact
persisted admission/policy/policy-provenance/relation bytes. It then obtains the
candidate and passes that exact candidate plus the verified bytes to the owner
provenance verifier. Only a receipt that independently reconciles policy-owner
provenance, native denominator/query-context subjects, ordered members, every
candidate field/hash and every content-resolved disposition evidence row
proceeds. The consumer constructs and validates the
single `OwnerQualifiedNativeCandidate`; no copied candidate field can diverge
beside its receipt.
The consumer recomputes the complete applicable-predicate denominator,
persists/reloads it through
`ChronologyApplicablePredicateDenominatorArtifacts`,
reconciles its four-way bijection, constructs the bundle profile from the owner
admission, and mints the private continuation in the same owner-held consumer
frame.  The locally closed persistence path owns verification, one-shot
process-local custody and persistence. No caller can pass a proof adapter,
store, verifier, kernel, continuation or positive reconciliation. The consumer
alone constructs the final `NativeChronologyReconciliation`. This proves
B10/B11/B16/H01/H02/H10/H14 without putting those predicates inside
`FullPrefixVerifier`. The full integration file covers 0/1/2 members,
valid-prefix omission, annotation-only commitment movement, authority-only head
movement, exterior unknown, terminal/historical opaque members and a sibling
consumer forced through the same verifier. A falsifier removes one required
policy rule and its matching disposition while holding members/context/bundle
fixed; the owner-resolved profile still requires it and admission fails. Other
required falsifiers install strict and lax policies for one owner, make the
adapter nominate the lax profile, repeat at zero members, replay the admission
across scope/purpose/cutoff/query context, and add a novel owner admission via
data alone. Wrong/mixed member profiles reject before bundle construction.
An owner-plane falsifier supplies a self-consistent narrowed candidate plus an
arbitrary non-stored evidence `ArtifactRef`; canonical owner re-enumeration and
content resolution must reject it before bundle building.
Every policy failure, post-policy candidate rejection and native limitation has
its own discriminated result; no exception, fabricated reconciliation or
mislabelled policy failure is an admitted return path. Contradictory
status/code construction is schema-invalid. Qualified and native-limited leaves
require a `verified` proof result; the proof-rejected leaf requires `rejected`;
profile/denominator mismatch leaves validate inequality and exact evidence.

B08 is an opaque-owner projection negative: terminal/member bytes and the
verified common proof stay fixed while a missing projection receipt yields a
`NativeProjectionCustodyGap` with exact
`code="native_projection_custody_gap"` and
`status="native_not_established"`; it never
rewrites the terminal. H05 is the opposite of the positive data-only
admission case: valid novel member bytes with an unknown or missing required
owner relation/provenance fail the applicable-predicate denominator without an
engine code-list edit. J05 has two independently read inputs rather than a
source-topology proxy for allocation. Before the Task-2.4 commit, the Git-side
candidate-tree walk is `git ls-files -z --cached --others --exclude-standard
-- '*.py' '*.pyi'`; it therefore includes every cached/tracked and every new
non-ignored Python or stub file that the boundary is about to commit. The
independent filesystem walk enumerates every `*.py`/`*.pyi`, applies Git's
ignore decision per path, and parses/type-classifies the complete candidate
set without consuming the first walk's output. After the guarded commit, rerun
against committed `HEAD` with `git ls-files -z -- '*.py' '*.pyi'` and require
exact equality to both the recorded candidate set and the fresh filesystem
walk. Every path is classified exactly once as `production_capable`,
`test_only`, `benchmark_only` or `example_only`. All Python/stubs under `src`,
`tools`, `apps`, `ops` and `architecture` are production-capable; `tests`,
`benchmarks` and `examples` have only their named exemption, and a novel top-
level or ambiguous path fails closed. Constructor, call and export analysis for
the common consumer and every named family producer runs over the entire
production-capable partition; an app/dashboard script, stub export or the
Task-2.4 consumer itself cannot escape by living outside `src`/`tools` or being
untracked before commit.

The precommit/postcommit equality is recorded as a cluster-journal receipt,
not as a product contract or a lane execution-manifest DTO. Before the
Task-2.4 suite, record each complete candidate path with its role, SHA-256 and
one classifier from `production_capable`, `test_only`,
`benchmark_only` or `example_only`. The two independent walks above must
agree with that exact candidate set.

Appendix C's plain boundary function repeats exact set equality after the
suite, stages exactly those declared paths, writes the captured tree, creates
one commit object over that tree and attaches it with the reusable atomic
transaction. The post-attachment readback requires the expected branch, commit
and tree, an empty index/worktree, and a fresh committed-tree walk equal to the
recorded candidate set. A missing path, path/content/classifier drift,
undeclared source, later mutation or narrowed suite fails the boundary. These
journal receipts guard this lane only; they do not establish chronology,
holder, authority or whole-history properties.

The allocation oracle is the separately added, strict append-only history
`architecture/production_quality/chronology_capability_allocation.toml`, not
this test or an absent prose row. Its decoder is defined beside the J05 test:

```python
ChronologyCapabilityRealityLabel: TypeAlias = (
    Literal["absent/unallocated"] | UniversalPolicyCapabilityRealityLabel
)
ChronologyPropertyResult = Literal["not_established", "established"]
ChronologyCapabilitySubject = Literal[
    "common_protocol_primitive", "generic_qualification_consumer",
    "epoch_family_producer", "release_family_producer",
    "run_family_producer", "movement_family_producer",
    "confidence_family_producer", "accepted_anchor_consumer",
    "writer_independent_holder", "family_audit_api_dashboard",
]
ChronologyActivationSignal = Literal[
    "cluster_2_common_protocol", "cluster_2_generic_consumer",
    "cluster_4_epoch_composition", "cluster_4_epoch_producer",
    "deferred_gy_gap3", "deferred_gy_gap5",
    "deferred_gy_gap6", "blocked_gy_gap2", "epoch_anchor_unappointed",
    "epoch_holder_unappointed", "family_surface_deferred",
    "whole_history_holder_not_established",
]

class ChronologyCapabilityStateChange(BaseModel):
    row_kind: Literal["capability"]
    subject_key: ChronologyCapabilitySubject
    effective_after_cluster: Literal["cluster_2", "cluster_3", "cluster_4"]
    status: ChronologyCapabilityRealityLabel
    canonical_owner_ref: str
    routing_ref: str
    activation_signal: ChronologyActivationSignal

class ChronologyPropertyStateChange(BaseModel):
    row_kind: Literal["property"]
    subject_key: Literal["whole_history_authenticity"]
    effective_after_cluster: Literal["cluster_2", "cluster_3", "cluster_4"]
    status: ChronologyPropertyResult
    canonical_owner_ref: str
    routing_ref: str
    activation_signal: ChronologyActivationSignal

ChronologyCapabilityHistoryPayload = Annotated[
    ChronologyCapabilityStateChange | ChronologyPropertyStateChange,
    Field(discriminator="row_kind"),
]

class ChronologyCapabilityHistoryEntry(BaseModel):
    ordinal: int = Field(ge=0)
    predecessor_kind: Literal["genesis", "entry"]
    previous_entry_hash: Digest | None
    payload: ChronologyCapabilityHistoryPayload
    entry_hash: Digest

class ChronologyCapabilityHistory(BaseModel):
    schema_version: Literal[
        "polisyos.chronology.capability-allocation-history.v2"
    ]
    history_id: Literal["gy-n12-clusters-2-4"]
    entries: tuple[ChronologyCapabilityHistoryEntry, ...]
```

Each TOML row is one physical `[[entries]]` table. `entry_hash` excludes
itself and is exactly
`sha256("polisyos.chronology.capability-allocation-entry.v2\\0" ||
uint64_be(len(C(mapping))) || C(mapping))`, where `mapping` is the fresh raw
mapping `{ordinal, predecessor_kind, previous_entry_hash, payload}` under the
record CanonSpec above. Genesis is ordinal zero with an explicit canonical
null predecessor; every later ordinal is contiguous and binds
the previous entry hash. There is no mutable stored count or head; both are
derived. The writer appends complete tables at EOF and fsyncs, never reopens a
prior table. The decoder uses strict/frozen models, rejects duplicate
`(subject_key,effective_after_cluster)` payloads, non-monotone cluster order,
owner/routing mutation, an invalid predecessor/hash, unknown
subjects/owners/routes/signals and a property status in a capability row (or
vice versa). `absent/unallocated` is the programme's explicit weaker
state added by this record; it is not falsely attributed to the narrower live
`UniversalPolicyCapabilityRealityLabel`. Exact owner/routing values are
`core.chronology/GY-N12-C2` for the common primitive,
`runtime.quality.chronology_qualification/GY-N12-C2` for the generic consumer,
`runtime.quality.semantic_epoch/GY-N12-C4` for the epoch producer,
`release_family/GY-GAP3`, `recursive_run/GY-GAP5`, `movement/GY-GAP6`,
`confidence_composition/GY-GAP2`, `epoch_anchor_acceptance/GY-N12-C3`,
`epoch_anchor_holder/GY-N12-C3`, `family_projection/GY-N12-C4`, and
`epoch_history/GY-N12-C3` for whole-history authenticity. Activation signals
are the exact closed literals above; free prose is rejected.

The approved Cycle-6 routing decision freezes the same eleven post-Cluster-2
payloads listed by the terminal matrix above: common primitive and generic
consumer `implemented_but_not_orchestrated`; epoch producer
`producer_missing`; release/run/movement/confidence and both anchor roles
`absent/unallocated`; family surface `surface_missing`; whole-history
authenticity `not_established`. Their exact owner, routing and activation
values are the closed mappings above. A 0/1 golden vector freezes the
`[[entries]]` grammar; a complete eleven-entry golden vector freezes ordering,
predecessor linkage and projected state. The chain establishes deterministic
retained-record continuity only; without the appointed holder it does not
upgrade whole-history authenticity.

Cluster 4 appends—never edits—three transitions: common protocol primitive,
generic qualification consumer and epoch-family producer each become
`implemented` after the production epoch adapter is invoked by
`SemanticEpochService`; every deferred family/anchor/holder/surface/property
row retains its earlier state and needs no duplicate transition. The appended
rows are three complete EOF `[[entries]]` tables with contiguous ordinals and
predecessor hashes. Common primitive and generic consumer use
`activation_signal="cluster_4_epoch_composition"`; epoch producer uses
`activation_signal="cluster_4_epoch_producer"`. The first two retain their
Cluster-2 owner/routing identities, and the third retains
`runtime.quality.semantic_epoch/GY-N12-C4`. This split records the Cluster-4
production composition that actually changes their state rather than reusing
the earlier creation signal.

J05 evaluates
the prefix as of Cluster 2; the final validator evaluates the latest state as
of Cluster 4. `whole_history_authenticity` is explicitly a property result,
not laundered into a capability label. The two complete source walks must agree
with each other, while code topology must agree with the independent TOML
history at the requested cluster boundary. Source absence alone never
distinguishes `producer_missing` from `absent/unallocated`. Adding a production
call/export, changing an owner row, omitting a candidate/committed Python or
stub path, or failing to append the Cluster-4 transition turns the test red.

`tests/repo_quality/test_gy_n12_cluster2_plan_paths.py` remains the C2 semantic
projection test. Appendix C derives the complete task `Add`/`Modify` union and
requires exact equality with the Git-visible delta before suites and before
attachment. A shared path may recur in sequential boundaries only when both
tasks declare it. Each public-surface boundary runs its canonical inventory
writer/check. Adding a path to a task or command alone fails independently of
the executor's selection.

**Exact 34-ID test map:**

```text
CB-A01 test_two_native_shapes_preserve_scope_and_reject_parent_scope
CB-A02 test_sparse_native_time_roles_are_not_fabricated
CB-A03 test_common_bundle_requires_no_universal_event_envelope
CB-A04 test_owner_disposition_changes_without_changing_verified_proof
CB-A05 test_withdrawn_historical_member_remains_membership_verifiable
CB-A06 test_common_surface_cannot_mutate_decision_or_claim_heads
CB-A07 test_adapter_cannot_admit_source_or_accept_anchor
CB-B01 test_owner_denominator_is_complete_before_qualification
CB-B02 test_native_byte_substitution_changes_commitment
CB-B03 test_delete_insert_reorder_and_fork_fail_proof_order
CB-B05 test_native_multi_head_is_preserved_and_never_time_selected
CB-B06 test_unknown_exterior_returns_native_not_established
CB-B07 test_offline_replay_uses_only_frozen_inputs
CB-B08 test_projection_suppression_reports_custody_gap_without_rewriting_terminal
CB-B10 test_valid_prefix_omitting_owner_member_fails_qualification
CB-B11 test_commitment_and_native_authority_heads_are_distinct
CB-B12 test_common_verifier_never_inspects_native_policy_fields
CB-B13 test_both_native_adapters_share_the_real_verifier_rejection
CB-B14 test_chronology_never_uses_confidence_ledger_scope_or_head
CB-B15 test_fixed_full_prefix_profile_behaviors_and_caps
CB-B15A test_unknown_profile_and_cross_domain_replay_reject
CB-B16 test_authority_only_and_annotation_only_heads_move_orthogonally
CB-B17 test_inventory_without_native_head_uses_empty_head_tuple
CB-H01 test_predicate_class_comes_from_owner_verifier_receipt
CB-H02 test_non_authority_predicate_classes_fail_qualification
CB-H04 test_remove_content_check_keep_markers_fails
CB-H05 test_novel_member_unknown_relation_or_provenance_fails
CB-H06 test_sibling_consumer_cannot_bypass_verifier_or_lift_limitation
CB-H10 test_owner_policy_change_moves_authority_not_proof
CB-H11 test_remove_predecessor_check_keep_markers_fails
CB-H14 test_valid_prefix_denominator_omission_fails
CB-H16 test_valid_shaped_unknown_profile_has_no_fallback
CB-H17 test_cross_family_scope_domain_replay_fails
CB-J05 test_cluster2_terminal_labels_match_source_derived_chain
```

Run the complete C2 witness denominator directly, with no selector:

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/runtime/quality/test_chronology_qualification.py \
  tests/integration/runtime_quality/test_chronology_protocol_conformance.py \
  tests/repo_quality/test_chronology_terminal_state.py \
  tests/repo_quality/test_gy_n12_cluster2_plan_paths.py
```

Appendix C stages exactly the declared candidate, atomically attaches the
captured tree and reads branch/commit/tree and the committed path set back.
No later boundary may use the C2 journal receipt as a current-state proxy.

**Commit boundaries:**

1. `feat(chronology): add exact full-prefix contract and verifier` — Tasks
   2.1–2.2.
2. `feat(chronology): persist bundles through the canonical artifact store` —
   Task 2.3 and its nearest runtime-quality README update.
3. `feat(chronology): add owner-qualified conformance consumer and two native
   witnesses` — Task 2.4, its README/status validator update and no production
   family adapter or owner state.

---

## Cluster 3 — epoch acceptance with an honest absent holder

**Delivers:** consumer-side acceptance, exact receipt/non-receipt contracts,
accepted-anchor lineage and query-bound rollback verification; a holder
capability port; and a production default that returns `not_established` when
no appointed holder exists.

**Retains:** the epoch-only holder is `absent/unallocated`; deployment and
credential independence are `not_established`. Generic audit cold tier remains
an implemented/conditionally-orchestrated reuse candidate only. No S3 writer,
bucket appointment, credential assumption, self-attested witness or positive
whole-history claim is delivered.

**Frozen basis subset (8):** `CB-B04`, `CB-B09`, `CB-B09A`, `CB-H08`,
`CB-H12`, `CB-H15`, `CB-J01`, `CB-J06`.

### Task 3.1 — define and verify the acceptance boundary

**Add:**

- `src/polisyos/core/artifacts/signed_evidence.py`
- `src/polisyos/core/security/anchor_lineage.py`
- `src/polisyos/core/security/chronology_anchor.py`
- `src/polisyos/runtime/quality/chronology_custody.py`
- `tests/unit/core/artifacts/test_signed_evidence.py`
- `tests/unit/core/security/test_anchor_lineage.py`
- `tests/unit/core/security/test_chronology_anchor.py`
- `tests/unit/runtime/http/test_epoch_custody_container.py`
- `tests/unit/runtime/quality/test_chronology_custody.py`

**Modify:**

- `src/polisyos/core/contracts/chronology.py`
- `src/polisyos/core/__init__.py`
- `src/polisyos/core/security/__init__.py`
- `src/polisyos/core/security/README.md`
- `src/polisyos/runtime/http/container.py`
- `src/polisyos/runtime/quality/README.md`
- `tests/_helpers/chronology_qualification.py`
- `architecture/public_surface/inventory.json`
- `release-fragments/unreleased/2026-08-20-gy-n12-epoch-chronology.toml`
- `docs/reference/public-surface.md`

Separate the two P37 predicates. A competent consumer accepts a native prefix;
an independent holder proves retention/readback. Neither predicate implies the
other and neither is inferred from storage location.

```python
from __future__ import annotations

class AnchorAcceptanceRequest(BaseModel):
    bundle_ref: ArtifactRef
    expected_domain: ChronologyProofDomain
    native_reconciliation_ref: ArtifactRef
    authority_purpose: str
    requested_query_context_ref: Digest
    asserted_prior_acceptance_record_refs: tuple[ArtifactRef, ...]

class OwnerDerivedAcceptedPrefix(BaseModel):
    acceptance_record_ref: ArtifactRef
    acceptance_record_content_hash: Digest
    statement_evidence_ref: ArtifactRef
    expected_prefix: ExpectedCommitmentPrefix

class AnchorAcceptanceStatement(BaseModel):
    accepting_owner_ref: str
    bundle_ref: ArtifactRef
    bundle_content_hash: Digest
    parsed_header: ChronologyBundleHeader
    native_reconciliation_ref: ArtifactRef
    authority_purpose: str
    requested_query_context_ref: Digest
    admission_cutoff_ref: Digest
    predicate_dispositions: tuple[PredicateDisposition, ...]
    prior_acceptance_record_refs: tuple[ArtifactRef, ...]
    derived_prior_prefixes: tuple[OwnerDerivedAcceptedPrefix, ...]
    owner_lineage_state_content_hash: Digest
    acceptance_appointment_ref: ArtifactRef
    acceptance_appointment_content_hash: Digest
    appointment_verification_receipt_ref: ArtifactRef
    appointment_verification_receipt_content_hash: Digest
    trust_snapshot_content_hash: Digest
    verifier_provenance_ref: Digest

class AnchorAcceptanceReceiptStatement(BaseModel):
    acceptance_digest: Digest
    acceptance_record_ref: ArtifactRef
    acceptance_record_content_hash: Digest
    signed_statement_evidence_ref: ArtifactRef
    lineage_append_receipt_ref: ArtifactRef
    lineage_append_receipt_content_hash: Digest
    lineage_key_ref: Digest
    requested_query_context_ref: Digest
    admission_cutoff_ref: Digest

class AnchorAcceptanceReceipt(BaseModel):
    receipt_record_ref: ArtifactRef
    receipt_record_content_hash: Digest
    statement_bytes: bytes
    receipt_record_bytes: bytes
    signed_receipt_evidence: SignedArtifactEvidence

class SignedArtifactEvidenceRecord(BaseModel):
    artifact_ref: ArtifactRef
    raw_blob_bytes_hash: Digest
    exact_manifest_raw_bytes_hash: Digest
    signature_artifact_ref: ArtifactRef
    signature_raw_bytes_hash: Digest
    signing_profile_ref: ArtifactRef
    signer_provenance_ref: ArtifactRef

class PersistedSignedArtifactEvidence(BaseModel):
    evidence_record_ref: ArtifactRef
    evidence_record_content_hash: Digest
    record_bytes: bytes

class SignedArtifactEvidence(BaseModel):
    persisted: PersistedSignedArtifactEvidence
    blob_bytes: bytes
    exact_manifest_bytes: bytes
    detached_signature_bytes: bytes

class SignedArtifactEvidenceRepository(Protocol):
    def persist_signed(
        self,
        *,
        blob_bytes: bytes,
        write_options: ArtifactWriteOptions,
        signer: ArtifactSigner,
        signing_profile_ref: ArtifactRef,
        signer_provenance_ref: ArtifactRef,
    ) -> PersistedSignedArtifactEvidence: ...

    def read_exact(
        self, *, evidence_record_ref: ArtifactRef
    ) -> SignedArtifactEvidence: ...

class AnchorAcceptanceRecord(BaseModel):
    acceptance_digest: Digest
    statement_artifact_ref: ArtifactRef
    statement_content_hash: Digest
    signed_statement_evidence_ref: ArtifactRef
    prior_acceptance_record_refs: tuple[ArtifactRef, ...]

class AcceptanceVerifierAppointmentStatement(BaseModel):
    schema_version: Literal["polisyos.chronology.acceptance-appointment.v1"]
    family: Literal["epoch"]
    proof_domain: str
    authority_purpose: str
    accepting_owner_ref: str
    trust_config_ref: ArtifactRef
    trust_config_content_hash: Digest
    appointment_basis_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef

class HolderVerifierAppointmentStatement(BaseModel):
    schema_version: Literal["polisyos.chronology.holder-appointment.v1"]
    family: Literal["epoch"]
    proof_domain: str
    authority_purpose: str
    holder_ref: str
    trust_config_ref: ArtifactRef
    trust_config_content_hash: Digest
    custody_boundary_evidence_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef

class AcceptanceAppointmentVerificationStatement(BaseModel):
    schema_version: Literal[
        "polisyos.chronology.acceptance-appointment-verification.v1"
    ]
    appointment_ref: ArtifactRef
    appointment_content_hash: Digest
    trust_config_ref: ArtifactRef
    trust_config_content_hash: Digest
    appointment_evidence_record_ref: ArtifactRef
    appointment_evidence_record_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class HolderAppointmentVerificationStatement(BaseModel):
    schema_version: Literal[
        "polisyos.chronology.holder-appointment-verification.v1"
    ]
    appointment_ref: ArtifactRef
    appointment_content_hash: Digest
    trust_config_ref: ArtifactRef
    trust_config_content_hash: Digest
    appointment_evidence_record_ref: ArtifactRef
    appointment_evidence_record_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class VerifiedAcceptanceVerifierAppointment(BaseModel):
    appointment_ref: ArtifactRef
    appointment_content_hash: Digest
    statement_bytes: bytes
    signed_appointment_evidence: SignedArtifactEvidence
    trust_config_bytes: bytes
    verification_statement_bytes: bytes
    verification_receipt_ref: ArtifactRef
    verification_receipt_content_hash: Digest
    signed_verification_evidence: SignedArtifactEvidence

class VerifiedHolderVerifierAppointment(BaseModel):
    appointment_ref: ArtifactRef
    appointment_content_hash: Digest
    statement_bytes: bytes
    signed_appointment_evidence: SignedArtifactEvidence
    trust_config_bytes: bytes
    verification_statement_bytes: bytes
    verification_receipt_ref: ArtifactRef
    verification_receipt_content_hash: Digest
    signed_verification_evidence: SignedArtifactEvidence

class AnchorRetentionStatement(BaseModel):
    family: str
    proof_domain: str
    authority_purpose: str
    requested_query_context_ref: Digest
    admission_cutoff_ref: Digest
    bundle_ref: ArtifactRef
    bundle_content_hash: Digest
    native_reconciliation_ref: ArtifactRef
    acceptance_receipt_ref: ArtifactRef
    acceptance_receipt_content_hash: Digest
    prior_acceptance_record_refs: tuple[ArtifactRef, ...]
    acceptance_appointment_ref: ArtifactRef
    acceptance_appointment_content_hash: Digest
    holder_appointment_ref: ArtifactRef
    holder_appointment_content_hash: Digest

class AnchorRetentionPackage(BaseModel):
    package_ref: Digest
    package_content_hash: Digest
    package_bytes: bytes

class AnchorAcceptanceEvidenceBundle(BaseModel):
    acceptance_statement_evidence: SignedArtifactEvidence
    acceptance_record_bytes: bytes
    acceptance_receipt_bytes: bytes
    acceptance_receipt_signed_evidence: SignedArtifactEvidence
    lineage_append_receipt_bytes: bytes

class AnchorRetentionObjectGraph(BaseModel):
    retention_statement_bytes: bytes
    bundle_bytes: bytes
    native_reconciliation_bytes: bytes
    acceptance_evidence: AnchorAcceptanceEvidenceBundle
    acceptance_appointment: VerifiedAcceptanceVerifierAppointment
    holder_appointment: VerifiedHolderVerifierAppointment

class AnchorCustodyReceiptStatement(BaseModel):
    family: Literal["epoch"]
    proof_domain: str
    authority_purpose: str
    holder_appointment_ref: ArtifactRef
    holder_ref: str
    package_ref: Digest
    package_content_hash: Digest
    object_version_ref: str
    retention_policy_ref: ArtifactRef
    requested_query_context_ref: Digest

class AnchorCustodyReceiptRecord(BaseModel):
    statement_artifact_ref: ArtifactRef
    statement_content_hash: Digest
    signed_statement_evidence_ref: ArtifactRef
    signed_statement_evidence_content_hash: Digest

class AnchorCustodyReceipt(BaseModel):
    receipt_record_ref: ArtifactRef
    receipt_record_content_hash: Digest
    receipt_record_bytes: bytes
    statement_bytes: bytes
    signed_statement_evidence: SignedArtifactEvidence

class AnchorReadbackChallengeStatement(BaseModel):
    family: Literal["epoch"]
    proof_domain: str
    authority_purpose: str
    lineage_key: AnchorAcceptanceLineageKey
    holder_appointment_ref: ArtifactRef
    package_ref: Digest
    expected_package_content_hash: Digest
    custody_receipt_record_ref: ArtifactRef
    custody_receipt_record_content_hash: Digest
    expected_object_version_ref: str
    requested_query_context_ref: Digest

class PersistedAnchorReadbackChallenge(BaseModel):
    challenge_record_ref: ArtifactRef
    challenge_record_content_hash: Digest
    statement_bytes: bytes

class AnchorReadbackReceiptStatement(BaseModel):
    family: Literal["epoch"]
    proof_domain: str
    authority_purpose: str
    holder_ref: str
    holder_appointment_ref: ArtifactRef
    challenge_record_ref: ArtifactRef
    challenge_record_content_hash: Digest
    custody_receipt_record_ref: ArtifactRef
    custody_receipt_record_content_hash: Digest
    package_ref: Digest
    package_content_hash: Digest
    object_version_ref: str
    retention_policy_ref: ArtifactRef
    requested_query_context_ref: Digest

class AnchorReadbackReceiptRecord(BaseModel):
    statement_artifact_ref: ArtifactRef
    statement_content_hash: Digest
    signed_statement_evidence_ref: ArtifactRef
    signed_statement_evidence_content_hash: Digest

class AnchorReadbackReceipt(BaseModel):
    receipt_record_ref: ArtifactRef
    receipt_record_content_hash: Digest
    receipt_record_bytes: bytes
    statement_bytes: bytes
    package_bytes: bytes
    retention_receipt: AnchorCustodyReceipt
    signed_statement_evidence: SignedArtifactEvidence

class AcceptanceUnavailableNonReceipt(BaseModel):
    status: Literal["not_established"]
    component: Literal["acceptance"]
    code: Literal[
        "anchor_acceptance_owner_not_established",
        "anchor_acceptance_trust_not_established",
    ]
    subject_artifact_ref: ArtifactRef
    requested_query_context_ref: Digest
    appointment_key_ref: Digest
    resolved_appointment_ref: ArtifactRef | None
    appointment_evidence_ref: ArtifactRef | None
    resolver_provenance_ref: ArtifactRef
    predicate_class: Literal["not_established"]

class RetentionUnavailableNonReceipt(BaseModel):
    status: Literal["not_established"]
    component: Literal["retention"]
    code: Literal[
        "anchor_holder_not_established",
        "anchor_holder_trust_not_established",
        "anchor_retention_not_established",
    ]
    subject_artifact_ref: ArtifactRef
    requested_query_context_ref: Digest
    appointment_key_ref: Digest
    resolved_appointment_ref: ArtifactRef | None
    appointment_evidence_ref: ArtifactRef | None
    resolver_provenance_ref: ArtifactRef
    predicate_class: Literal["not_established"]

class AcceptanceRejectedNonReceipt(BaseModel):
    status: Literal["rejected"]
    component: Literal["acceptance"]
    code: Literal[
        "anchor_signature_unverified",
        "anchor_query_or_lineage_mismatch",
        "accepted_anchor_lineage_conflict",
    ]
    subject_artifact_ref: ArtifactRef
    requested_query_context_ref: Digest
    appointment_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef
    decisive_evidence_refs: Annotated[
        tuple[ArtifactRef, ...], Field(min_length=1)
    ]
    predicate_class: Literal["independently_reconciled"]

class RetentionRejectedNonReceipt(BaseModel):
    status: Literal["rejected"]
    component: Literal["retention"]
    code: Literal[
        "anchor_package_mismatch",
        "anchor_signature_unverified",
        "anchor_readback_mismatch",
        "anchor_query_or_lineage_mismatch",
    ]
    subject_artifact_ref: ArtifactRef
    requested_query_context_ref: Digest
    appointment_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef
    decisive_evidence_refs: Annotated[
        tuple[ArtifactRef, ...], Field(min_length=1)
    ]
    predicate_class: Literal["independently_reconciled"]

AcceptanceNonReceipt = Annotated[
    AcceptanceUnavailableNonReceipt | AcceptanceRejectedNonReceipt,
    Field(discriminator="status"),
]
RetentionNonReceipt = Annotated[
    RetentionUnavailableNonReceipt | RetentionRejectedNonReceipt,
    Field(discriminator="status"),
]

class VerifiedAnchorAcceptance(BaseModel):
    acceptance_digest: Digest
    acceptance_record_ref: ArtifactRef
    acceptance_record_content_hash: Digest
    acceptance_receipt_record_ref: ArtifactRef
    acceptance_receipt_record_content_hash: Digest
    lineage_append_receipt_ref: ArtifactRef
    lineage_append_receipt_content_hash: Digest
    lineage_state_content_hash: Digest
    lineage_position: Literal["current", "historical_for_exact_query"]
    accepting_owner_ref: str
    statement_content_hash: Digest
    signed_statement_evidence_ref: ArtifactRef
    acceptance_appointment_ref: ArtifactRef
    acceptance_appointment_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    requested_query_context_ref: Digest
    admission_cutoff_ref: Digest
    prior_acceptance_record_refs: tuple[ArtifactRef, ...]
    predicate_class: Literal["independently_reconciled"]

class VerifiedAnchorRetention(BaseModel):
    holder_ref: str
    custody_receipt_record_ref: ArtifactRef
    custody_receipt_record_content_hash: Digest
    readback_receipt_record_ref: ArtifactRef
    readback_receipt_record_content_hash: Digest
    challenge_record_ref: ArtifactRef
    challenge_record_content_hash: Digest
    package_ref: Digest
    package_content_hash: Digest
    object_version_ref: str
    retention_policy_ref: ArtifactRef
    holder_appointment_ref: ArtifactRef
    holder_appointment_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    signed_evidence_record_refs: Annotated[
        tuple[ArtifactRef, ...], Field(min_length=2, max_length=2)
    ]
    requested_query_context_ref: Digest
    predicate_class: Literal["independently_reconciled"]

class VerifiedAcceptanceOutcome(BaseModel):
    status: Literal["verified"]
    value: VerifiedAnchorAcceptance

class UnavailableAcceptanceOutcome(BaseModel):
    status: Literal["not_established"]
    non_receipts: Annotated[
        tuple[AcceptanceUnavailableNonReceipt, ...], Field(min_length=1)
    ]

class RejectedAcceptanceOutcome(BaseModel):
    status: Literal["rejected"]
    rejections: Annotated[
        tuple[AcceptanceRejectedNonReceipt, ...], Field(min_length=1)
    ]

class VerifiedRetentionOutcome(BaseModel):
    status: Literal["verified"]
    value: VerifiedAnchorRetention

class UnavailableRetentionOutcome(BaseModel):
    status: Literal["not_established"]
    non_receipts: Annotated[
        tuple[RetentionUnavailableNonReceipt, ...], Field(min_length=1)
    ]

class RejectedRetentionOutcome(BaseModel):
    status: Literal["rejected"]
    rejections: Annotated[
        tuple[RetentionRejectedNonReceipt, ...], Field(min_length=1)
    ]

AcceptanceOutcome = Annotated[
    VerifiedAcceptanceOutcome | UnavailableAcceptanceOutcome
    | RejectedAcceptanceOutcome,
    Field(discriminator="status"),
]
RetentionOutcome = Annotated[
    VerifiedRetentionOutcome | UnavailableRetentionOutcome
    | RejectedRetentionOutcome,
    Field(discriminator="status"),
]

class AnchorCustodyVerification(BaseModel):
    status: Literal["verified", "limited", "rejected"]
    acceptance: AcceptanceOutcome
    retention: RetentionOutcome

class AnchorAcceptanceLineageKey(BaseModel):
    family: Literal["epoch"]
    proof_domain: str
    scope_ref: Digest
    authority_purpose: str

class AcceptedAnchorRecordEntry(BaseModel):
    acceptance_record_ref: ArtifactRef
    acceptance_record_content_hash: Digest
    acceptance_digest: Digest
    signed_statement_evidence_ref: ArtifactRef
    requested_query_context_ref: Digest
    admission_cutoff_ref: Digest
    predecessor_record_refs: tuple[ArtifactRef, ...]

class AnchorAcceptanceLineageStateStatement(BaseModel):
    key: AnchorAcceptanceLineageKey
    current_record_refs: tuple[ArtifactRef, ...]
    records: tuple[AcceptedAnchorRecordEntry, ...]

class AnchorAcceptanceLineageState(BaseModel):
    statement_bytes: bytes
    state_content_hash: Digest

class AnchorAcceptanceAppendSuccessStatement(BaseModel):
    status: Literal["appended", "idempotent"]
    key: AnchorAcceptanceLineageKey
    expected_head_refs: tuple[ArtifactRef, ...]
    previous_head_refs: tuple[ArtifactRef, ...]
    resulting_head_refs: tuple[ArtifactRef, ...]
    acceptance_record_ref: ArtifactRef
    resulting_state_content_hash: Digest

class PersistedAnchorAcceptanceAppendSuccess(BaseModel):
    result_kind: Literal["append_success"]
    append_receipt_ref: ArtifactRef
    append_receipt_content_hash: Digest
    statement_bytes: bytes

class AnchorAcceptanceAppendConflict(BaseModel):
    result_kind: Literal["append_conflict"]
    status: Literal["head_conflict"]
    key: AnchorAcceptanceLineageKey
    expected_head_refs: tuple[ArtifactRef, ...]
    observed_head_refs: tuple[ArtifactRef, ...]
    candidate_record_ref: ArtifactRef
    failure_code: Literal["accepted_anchor_lineage_conflict"]

AnchorAcceptanceAppendResult = Annotated[
    PersistedAnchorAcceptanceAppendSuccess | AnchorAcceptanceAppendConflict,
    Field(discriminator="result_kind"),
]

class AnchorAcceptanceLineageRepository(Protocol):
    def resolve_lineage(
        self, *, key: AnchorAcceptanceLineageKey
    ) -> AnchorAcceptanceLineageState: ...

    def append_if_current(
        self, *, key: AnchorAcceptanceLineageKey,
        expected_head_refs: tuple[ArtifactRef, ...],
        record: AcceptedAnchorRecordEntry,
    ) -> AnchorAcceptanceAppendResult: ...

class AnchorReadbackChallengeRepository(Protocol):
    def persist(
        self, statement: AnchorReadbackChallengeStatement
    ) -> PersistedAnchorReadbackChallenge: ...

    def resolve(
        self, *, challenge_record_ref: ArtifactRef
    ) -> PersistedAnchorReadbackChallenge: ...

class ChronologyAcceptanceAuthority(Protocol):
    def recompute_and_accept(
        self, request: AnchorAcceptanceRequest
    ) -> AnchorAcceptanceReceipt | AcceptanceNonReceipt: ...

class AnchorHolder(Protocol):
    def retain(
        self, package: AnchorRetentionPackage
    ) -> AnchorCustodyReceipt | RetentionNonReceipt: ...

    def readback(
        self, challenge: PersistedAnchorReadbackChallenge
    ) -> AnchorReadbackReceipt | RetentionNonReceipt: ...

class AnchorAcceptanceReceiptVerifier(Protocol):
    def verify(
        self,
        *,
        receipt: AnchorAcceptanceReceipt,
        appointment: VerifiedAcceptanceVerifierAppointment,
        evidence: AnchorAcceptanceEvidenceBundle,
        lineage: AnchorAcceptanceLineageRepository,
        requested_query_context_ref: Digest,
    ) -> VerifiedAnchorAcceptance | AcceptanceNonReceipt: ...

class AnchorHolderReceiptVerifier(Protocol):
    def verify_retention_and_readback(
        self,
        *,
        retention: AnchorCustodyReceipt,
        readback: AnchorReadbackReceipt,
        challenge: PersistedAnchorReadbackChallenge,
        appointment: VerifiedHolderVerifierAppointment,
    ) -> VerifiedAnchorRetention | RetentionNonReceipt: ...

class EstablishedAcceptanceAppointment(BaseModel):
    status: Literal["established"]
    appointment: VerifiedAcceptanceVerifierAppointment

class UnavailableAcceptanceAppointment(BaseModel):
    status: Literal["not_established"]
    non_receipt: AcceptanceUnavailableNonReceipt

AcceptanceAppointmentResult = Annotated[
    EstablishedAcceptanceAppointment | UnavailableAcceptanceAppointment,
    Field(discriminator="status"),
]

class EstablishedHolderAppointment(BaseModel):
    status: Literal["established"]
    appointment: VerifiedHolderVerifierAppointment

class UnavailableHolderAppointment(BaseModel):
    status: Literal["not_established"]
    non_receipt: RetentionUnavailableNonReceipt

HolderAppointmentResult = Annotated[
    EstablishedHolderAppointment | UnavailableHolderAppointment,
    Field(discriminator="status"),
]

class EpochAnchorAppointmentResolution(BaseModel):
    acceptance: AcceptanceAppointmentResult
    holder: HolderAppointmentResult

class EpochAnchorAppointmentResolver(Protocol):
    def resolve_epoch_appointments(
        self, *, family: Literal["epoch"], proof_domain: str,
        authority_purpose: str,
    ) -> EpochAnchorAppointmentResolution: ...

class EpochAnchorAuthorityRegistry(Protocol):
    def resolve_acceptance_authority(
        self, *, appointment: VerifiedAcceptanceVerifierAppointment
    ) -> ChronologyAcceptanceAuthority | AcceptanceNonReceipt: ...

    def resolve_holder(
        self, *, appointment: VerifiedHolderVerifierAppointment
    ) -> AnchorHolder | RetentionNonReceipt: ...

    def resolve_acceptance_verifier(
        self, *, appointment: VerifiedAcceptanceVerifierAppointment
    ) -> AnchorAcceptanceReceiptVerifier | AcceptanceNonReceipt: ...

    def resolve_acceptance_lineage(
        self, *, appointment: VerifiedAcceptanceVerifierAppointment
    ) -> AnchorAcceptanceLineageRepository | AcceptanceNonReceipt: ...

    def resolve_holder_verifier(
        self, *, appointment: VerifiedHolderVerifierAppointment
    ) -> AnchorHolderReceiptVerifier | RetentionNonReceipt: ...

class EpochAnchorCustodyService:
    def __init__(
        self,
        *,
        appointment_resolver: EpochAnchorAppointmentResolver,
        authority_registry: EpochAnchorAuthorityRegistry,
        issuance_evidence: SignedArtifactEvidenceRepository,
        challenge_repository: AnchorReadbackChallengeRepository,
    ) -> None: ...

    def accept_retain_and_verify(
        self, *, request: AnchorAcceptanceRequest
    ) -> AnchorCustodyVerification: ...

    def verify_retained_challenge(
        self, *, challenge_record_ref: ArtifactRef
    ) -> AnchorCustodyVerification: ...

class EpochAnchorCustodyProvider(Protocol):
    def evaluate_acceptance_and_custody(
        self, *, request: AnchorAcceptanceRequest
    ) -> AnchorCustodyVerification: ...

    def evaluate_retained_challenge(
        self, *, challenge_record_ref: ArtifactRef
    ) -> AnchorCustodyVerification: ...

def build_production_epoch_anchor_custody_provider(
) -> EpochAnchorCustodyProvider: ...
```

`SignedArtifactEvidenceRepository` is a narrow exact-byte port, not
`ArtifactStore`. Its concrete filesystem adapter owns
`FileSystemCAS.get_manifest_bytes`; it writes the detached-signature canonical
bytes as a separate ordinary CAS artifact and persists an evidence record that
binds blob, exact manifest and signature artifacts. A generic `ArtifactStore`
does not conform, is never cast to this port, and cannot issue a signed receipt.
`SignedArtifactEvidenceRecord` contains no `evidence_record_ref`; only the
persisted wrapper carries the raw-CAS ref/hash of those canonical record bytes.
The existing signer signs the raw-CAS artifact ID exactly as required; the
domain-separated acceptance digest is a separate semantic identity and is
never passed as `ArtifactID`.

No persisted/verified Cluster-3 wrapper carries a parsed statement or record
beside its exact bytes. Statement/record DTOs define codecs only. Every owner
consumer first verifies the signed evidence and ref/hash graph, reparses the
verified bytes with the named strict DTO, canonically reserializes that parsed
value and requires byte equality; authority fields and verifier provenance are
read only from that local reparsed value. The local value is not stored on or
accepted from the wrapper. This one rule covers appointments, appointment-
verification receipts, acceptance/custody/readback receipts, lineage state and
append receipts, and signed-evidence records. A generic mutation replaces each
codec field in turn while keeping the authentic bytes/evidence fixed and proves
that no parallel object field exists; changing exact bytes still fails
signature/content verification.

`AnchorAcceptanceStatement` is serialized canonically **without** signature or
self-reference and persisted first. `acceptance_digest` is the domain-separated
hash of those exact statement bytes. The canonical `AnchorAcceptanceRecord`
then binds that digest, raw statement ref/hash, signed-evidence ref and prior
record but contains no ref to itself. At that point it is an authentic
**candidate**, not an accepted anchor. Only a successful owner-held
compare-and-append produces a persisted append-success statement. The final
`AnchorAcceptanceReceiptStatement` binds both the candidate record and that
append receipt; its signed persisted wrapper is the only positive acceptance
receipt. A conflict leaves the signed candidate historically authentic but
returns `accepted_anchor_lineage_conflict`, never an acceptance receipt.
Custody, readback and challenge use the same no-self-reference pattern:
canonical unsigned statement, exact signed evidence, canonical receipt record,
then persisted wrapper carrying the record ref/hash. No object signs bytes
containing its own ref.

Every Cluster-3 statement/record uses the Cluster-2 raw-mapping `CanonSpec` and
`frame(x)=uint64_be(len(x))||x`. The complete **module** denominator is derived
first from every production `.py` in Task 3.1's `Add`/`Modify` lists and then
independently from the exact candidate delta recorded by Appendix C; those two
sets must match exactly. Tests/helpers are a separate test-only partition. Every
production module is classified exactly once as `model_owner` or
`verified_no_cluster3_model`; the latter is admissible only when a full AST
walk finds no concrete `BaseModel` definition, canonical codec, Cluster-3
domain registration or persisted-result wrapper in that module. Thus
`core/contracts/chronology.py`, `core/__init__.py`, security package exports and
`runtime/http/container.py` remain inside the denominator even when their
current classification is no-model/export-only.

The complete **model** denominator is then derived twice over that full module
set: one AST walk resolves every concrete model definition and import-owned
module, while one runtime walk imports every declared production module and
enumerates every concrete strict `BaseModel` whose `__module__` is in the set.
The AST/runtime sets and the model-owner/no-model classification must match
exactly. A third whole-Cluster-3 source guard rejects a concrete/canonical/
transport/result model in any declared production module that neither walk
classifies. Adding a canonical DTO with a decisive digest to
`core/contracts/chronology.py`, `runtime/http/container.py` or any other
formerly no-model declared path therefore fails before registry/golden edits;
the two walks cannot share a hand-maintained four-module blind spot. Every
model has exactly one registry class:
`canonical_codec`, `persisted_transport`, or `failure_or_result`. A canonical
codec has exactly one domain, CanonSpec and 0/1 fixture factory; the other two
classes carry an explicit no-domain reason. An unclassified, multiply
classified, abstract-looking concrete or source/runtime-mismatched model fails.

`C3_HASH_FIELD_RULES` is generated over that complete model set from resolved
type annotations: every field whose annotation contains `Digest`, plus every
nested `ArtifactRef.artifact_id`, enters the denominator regardless of its
spelling. Each rule supplies model, field path, role, raw/semantic/
institutional class, exact preimage, ordering, domain, persisting owner and
self-field exclusion. The model-derived field denominator must equal the
registry exactly, and the set of canonical-codec models must equal the domain
and golden-vector key sets. Raw CAS identity is `sha256(exact_bytes)` with
no domain; semantic identity is `sha256(domain||frame(exact_bytes))`; imported
bundle identity uses the Cluster-2 bundle domain; institutional refs resolve
only through the exact verified appointment snapshot and are never recomputed
locally as authority. Raw blob, exact manifest and signature fields are named
`*_raw_bytes_hash`; raw and semantic identities cannot share a suffix.

The initial canonical-codec registry—and therefore the generated 0/1 golden
denominator—is exactly `anchor-acceptance-statement.v1`,
`anchor-acceptance-candidate.v1`, `anchor-lineage-append.v1`,
`anchor-acceptance-receipt.v1`, `anchor-retention-statement.v1`,
`anchor-custody-receipt.v1`, `anchor-readback-challenge.v1`,
`anchor-readback-receipt.v1`, `signed-artifact-evidence-record.v1`,
`anchor-acceptance-appointment.v1`,
`anchor-acceptance-appointment-verification.v1`,
`anchor-holder-appointment.v1`,
`anchor-holder-appointment-verification.v1`,
`anchor-acceptance-trust-snapshot.v1`, `anchor-holder-trust-snapshot.v1`,
`anchor-acceptance-lineage-state.v1` and `anchor-retention-package.v1`, each
under `polisyos.chronology.` plus a trailing NUL except the explicitly frozen
`polisyos.signed-artifact-evidence-record.v1\0` domain.
`AnchorAcceptanceLineageState.state_content_hash` hashes only the canonical
`AnchorAcceptanceLineageStateStatement`; `package_ref` is raw
`sha256(package_bytes)` and `package_content_hash` is the domain-separated
retention-package hash; signed-evidence record content uses its own domain.
Persisted wrapper refs/hashes always describe already constructed unsigned
bytes and exclude themselves. A generic schema test reconciles every model,
domain, golden and field to the complete censuses. Adding a new concrete DTO
with a decisive digest—or a new canonical DTO/domain—fails before any manual
registry or golden update; removing `package_ref`, any raw evidence hash or
`lineage_key_ref` also fails. All raw/semantic and cross-domain swaps plus a
keep-self-reference/remove-exclusion mutation fail.

Each appointment-verification receipt is the semantic hash/ref of its exact
canonical unsigned verification statement under its named domain. The verified
appointment wrapper carries only appointment/verification statement bytes,
trust bytes, refs/hashes and their independently signed exact evidence; it has
no parallel parsed authority object. A bare receipt ref/hash is insufficient.
Deleting or mutating verification-statement bytes while appointment, signature
and trust bytes remain fixed must fail fresh verification; an attempted
object-only substitution has no input field and cannot reach a gate.

The appointed acceptance authority owns the
bundle/native readers, real `FullPrefixVerifier`, native admission policy and
signed-evidence issuer. `recompute_and_accept` accepts only refs/query context,
reloads exact bytes and recomputes proof plus member-bound P37 predicates. It
first resolves the owner-held lineage and requires the caller's asserted prior
refs to equal its exact current set. It reloads every current record and signed
acceptance statement, derives one `OwnerDerivedAcceptedPrefix` per unique
current commitment prefix, and runs the real verifier against every derived
prefix. An empty derived-prefix tuple is legal only when both records and heads
are empty; a nonempty lineage can never request genesis/`None`. Same-chain
ancestors may all verify, while divergent prefixes reject without list or time
ordering. A caller-supplied `expected_prefix` does not exist.

The verified acceptance-appointment statement, exact trust-config bytes,
signed appointment evidence, appointment-verification receipt and trust
snapshot are bound into the unsigned acceptance statement before signing. The
owner lineage-state hash and every derived prior prefix are bound there too.
The authority then creates/signs a candidate, calls the owner-held
`AnchorAcceptanceLineageRepository.append_if_current`, and issues the final
receipt only from a persisted `appended`/`idempotent` result. The
repository keys family/proof-domain/scope/purpose, preserves every historical
record and explicit current multi-head set, and compare-and-appends against
owner-resolved heads. A genuine old record remains verifiable at its stored query/cutoff
but cannot be appended or presented as a current head for a later query. It
never list-orders or timestamps incomparable heads.
`anchor_lineage.py` supplies the append-only file implementation: immutable
canonical candidate and transaction records plus one atomic compare-and-replace
head index. A write-ahead transaction record makes index movement and the
append-success receipt idempotently recoverable; a crash exposes either the old
head or the recoverable committed new head, never a positive receipt without a
matching lineage state. Conflict receipts never move the index. It is exercised by the qualification
acceptance authority but is not installed in production while that authority
is unappointed. The authority never accepts a caller-created
`FullPrefixVerificationResult`, reconciliation bytes, verifier, signer, trust
root or appointment.

`AnchorRetentionStatement` is a second canonical,
domain-separated frame over the accepted bundle/reconciliation/receipt/query/
lineage identities and contains no `package_ref`; `package_ref` is computed
from the canonical `AnchorRetentionObjectGraph`. That graph embeds the exact
bundle and native-reconciliation bytes, the complete signed acceptance
statement evidence, persisted candidate and final acceptance-receipt bytes,
the successful lineage-append receipt, the exact verified acceptance and
holder appointment statements/evidence/trust/verification-receipt bytes, and the retention statement
bytes. Both appointment refs/content hashes also sit in the retention
statement. The final acceptance receipt transitively binds the acceptance
appointment through its signed statement; the retained graph freezes both
appointments so fresh verification cannot substitute a live mutable
appointment. The
independent holder retains these bytes, not writer-store
refs. Readback returns the exact retained package bytes plus the holder's signed
custody receipt, exact custody-statement/signature evidence bytes and exact
readback-statement/signature evidence bytes—not evidence refs requiring the
writer store. The holder verifier takes no writer `ArtifactStore` or
`SignedArtifactEvidenceRepository`; it parses/recomputes entirely from those
holder-returned bytes. The writer-side repository is used only during initial
acceptance issuance. A fresh readback verifier with an empty/deleted writer CAS
must still verify the package and both holder signatures; deleting holder bytes
must fail. Thus deleting every writer-side copy cannot turn a failure into a pass. The
acceptance statement binds the exact full-bundle digest and parsed header,
native reconciliation, purpose/query/cutoff, frozen P37 dispositions, verifier
provenance and the exact prior acceptance-record head set.

The content-bound `AnchorReadbackChallengeStatement` carries the epoch family,
proof domain, authority purpose, full lineage key, holder-appointment ref,
custody-receipt record ref/hash, package/version and requested query context.
The service persists it and exposes only `challenge_record_ref`; a fresh service
reloads that record before resolving the appointment and holder. The holder's
readback statement binds the exact challenge and custody-receipt record
identities. Reusing one package/holder across purposes, substituting another
valid custody receipt, or changing a caller-supplied holder label therefore
cannot redirect verification.

The result is a closed acceptance-by-retention product: each half is exactly
one role-specific `verified`, `not_established` or `rejected` outcome and is
never `None`. `verified` means verified × verified. `limited` means verified ×
not-established, not-established × verified, or not-established ×
not-established. `rejected` is exactly the five combinations containing at
least one rejected half. An initial acceptance rejection gives retention an
exact prerequisite rejection or independently resolved unavailable result; it
cannot leave the second predicate unaccounted. Model validators exercise all
nine combinations, reject role-wrong codes, empty non-receipt/rejection tuples,
a verified half without every receipt/challenge/appointment/evidence/verifier
ref, and any code/component/provenance pairing outside its exact map.
`VerifiedAnchorAcceptance` always binds final receipt, append receipt, verified
appointment/trust snapshot, verifier and reconciled lineage state;
`VerifiedAnchorRetention` always binds persisted challenge, custody/readback
receipts, both exact signed-evidence records, verified appointment/trust
snapshot and verifier.

The acceptance verifier adapts the existing `ArtifactVerifier` with the exact
`AnchorAcceptanceEvidenceBundle` bytes, the appointment's trust
configuration and the owner lineage repository; signature authenticity without
the bound successful append is rejected. The holder verifier adapts the same
cryptographic primitive over the exact evidence bytes embedded in holder
readback and takes no writer repository. Acceptance and holder appointments resolve independently under
the same family/domain/purpose key; absence of one never erases evidence for
the other. `EpochAnchorCustodyService` is an internal mechanism, not a public
production constructor;
its methods take no authority, holder, verifier, signer, trust-root or
appointment parameters. It resolves an appointment scoped jointly to epoch
family, proof domain and authority purpose, obtains the matching implementations
from its container-owned registry, resolves the persisted challenge by ref,
checks the query against prior lineage, challenges the appointed holder and verifies exact object/version/retention/readback
evidence. It never accepts a separately invented header hash or field-shaped
fake.

`runtime.quality.chronology_custody.build_production_epoch_anchor_custody_provider`
is the single no-argument composition root. It installs the no-appointment
resolver/empty registry and is wired into `RuntimeServiceContainer`; downstream
production code receives only `EpochAnchorCustodyProvider`. The service class,
ports and test factory are not re-exported from `polisyos.core`. A complete AST
guard requires every source constructor call to occur in that one composition
module and forbids request/method parameters typed as the internal service,
resolver or registry. Arbitrary test resolvers therefore cannot be passed to
the authority gate. Today the production resolver independently returns no
acceptance appointment and no holder appointment. It returns
`anchor_acceptance_owner_not_established`,
`anchor_acceptance_trust_not_established` and
`anchor_holder_not_established` as applicable. Test-only appointed
consumer/holder/verifiers live in `tests/_helpers/chronology_qualification.py`;
they cannot enter a production registry or change the production claim.

Write red tests for:

- self-signed writer and writer-adjacent copy;
- authentic old anchor presented for a later query;
- nonempty owner lineage plus a rewritten origin and caller assertion of the
  exact current refs cannot use `None`/genesis; same-chain multiple prefixes
  verify and divergent current prefixes reject;
- cross-purpose and wrong/missing requested query context;
- whole-history substitution of every writer-mutable anchor;
- absent holder and missing exact readback/retention receipt;
- correct historical query against its own old anchor;
- a fake holder implementing only field shape.
- a valid signature under an unappointed key/trust configuration;
- an acceptance receipt issued under appointment A cannot verify under B even
  with a shared valid key; deleted or mutated appointment/trust/appointment-
  verification-receipt bytes reject;
- statement-byte substitution with an unchanged signature sidecar;
- writer CAS deletion after holder retention while exact holder readback still
  verifies in a fresh service with no writer evidence repository, and
  holder-byte deletion/mutation rejects;
- a valid custody receipt substituted under an unchanged challenge rejects by
  receipt-record identity;
- one package/holder reused across two purposes cannot redirect a persisted
  challenge or appointment lookup;
- a generic `ArtifactStore` with no exact-manifest port cannot issue a receipt;
- a caller-supplied fake appointment/resolver cannot enter the production
  custody service;
- an authentic acceptance receipt with no independent holder; and
- a holder receipt with no competent accepting consumer;
- `verified` with either evidence half missing is schema-invalid;
- a verified half missing any receipt/challenge/appointment/verifier binding,
  and a limitation contradicting that verified half, are schema-invalid;
- acceptance-only and holder-only return distinct `limited` results preserving
  the established half;
- all nine acceptance × retention outcomes produce the exact aggregate status,
  and every role-wrong non-receipt is schema-invalid;
- the DTO-derived decisive ref/hash denominator equals `C3_HASH_FIELD_RULES`,
  every added domain reproduces its golden vectors and all raw/semantic or
  cross-role swaps reject;
- the Task-3 production-Python denominator equals both plan/commit declarations,
  every module is model-owning or AST-proven no-model, and adding a canonical
  digest-bearing DTO to a formerly no-model declared module turns both census
  reconciliation and the golden/domain gate red;
- accepted-head compare-and-append rejects a genuine old record for a later
  query while retaining historical lookup; and
- two concurrent candidates from the same expected heads leave exactly one
  accepted receipt; the loser's authentic signed candidate never verifies as
  accepted/current;
- the production constructor census has exactly one source call and no
  injectable service parameter.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/core/artifacts/test_signed_evidence.py \
  tests/unit/core/security/test_anchor_lineage.py \
  tests/unit/core/security/test_chronology_anchor.py \
  tests/unit/core/security/test_full_prefix.py \
  tests/unit/runtime/quality/test_chronology_custody.py \
  tests/unit/runtime/http/test_epoch_custody_container.py
GY_N12_C3_MODIFY_PATHS=(
  src/polisyos/core/contracts/chronology.py
  src/polisyos/core/__init__.py
  src/polisyos/core/security/__init__.py
  src/polisyos/core/security/README.md
  src/polisyos/runtime/http/container.py
  src/polisyos/runtime/quality/README.md
  tests/_helpers/chronology_qualification.py
  architecture/public_surface/inventory.json
  release-fragments/unreleased/2026-08-20-gy-n12-epoch-chronology.toml
  docs/reference/public-surface.md
)
for GY_N12_C3_MODIFY in "${GY_N12_C3_MODIFY_PATHS[@]}"; do
  test -e "$GY_N12_C3_MODIFY"
done
GY_N12_C3_ADD_PATHS=(
  src/polisyos/core/artifacts/signed_evidence.py
  src/polisyos/core/security/anchor_lineage.py
  src/polisyos/core/security/chronology_anchor.py
  src/polisyos/runtime/quality/chronology_custody.py
  tests/unit/core/artifacts/test_signed_evidence.py
  tests/unit/core/security/test_anchor_lineage.py
  tests/unit/core/security/test_chronology_anchor.py
  tests/unit/runtime/http/test_epoch_custody_container.py
  tests/unit/runtime/quality/test_chronology_custody.py
)
GY_N12_C3_RUFF_PATHS=()
for GY_N12_C3_CANDIDATE in \
  "${GY_N12_C3_MODIFY_PATHS[@]}" "${GY_N12_C3_ADD_PATHS[@]}"; do
  [[ "$GY_N12_C3_CANDIDATE" == *.py ]] || continue
  [[ ! -e "$GY_N12_C3_CANDIDATE" ]] ||
    GY_N12_C3_RUFF_PATHS+=("$GY_N12_C3_CANDIDATE")
done
test "${#GY_N12_C3_RUFF_PATHS[@]}" -gt 0
"${GY_N12_RUN[@]}" -m ruff check "${GY_N12_C3_RUFF_PATHS[@]}"
```

Explicitly leave `src/polisyos/core/security/audit_sink.py` and
`src/polisyos/core/run/context.py` unchanged: their cold tier has no chronology
intake, object-version receipt, readback/challenge, deployed principal or
appointment. If implementation discovers such a live appointment, stop and
return to the user; that is institutional scope, not a code repair.

**Commit boundary:** `feat(chronology): separate anchor acceptance from custody
without appointing either owner`.

---

## Cluster 4 — epoch family, validity cascade and owner bridges

**Delivers:** data-derived fixed-semantics epochs with complete native-
denominator receipts; honest unresolved/contested resolution; an independently
checked N13b semantic stamp; certificate staleness and owner-adjudicated
perturbation; a separate authority-verified Decision Validity batch route with
pending freeze; completed-batch Claim Ledger persistence/export; and
OpenWorldRisk `not_established` propagated through the actual N9/generation/
public path. It adds one generated epoch contract only after source freeze.

**Retains:** Decision Validity, Claim Ledger, L5, Lex, N13b and N9 as canonical
owners; overlay `epoch_id` as its native operational ordinal; historical
authenticity; automatic derivation-recipe execution globally
`absent/unallocated` (or `producer_missing` for a known uninvoked producer);
competent deployment-scope evidence `producer_missing`; its institutional owner
`absent/unallocated`; epoch holder/whole-history authenticity
`absent/unallocated`; and release/run/movement/GAP2 adapters outside this task.
No `40/40` implementation claim is permitted.

**Frozen basis subset (40):** `CB-C00`, `CB-C01`, `CB-C02`, `CB-C03`,
`CB-C03A`, `CB-C04`, `CB-C05`, `CB-C06`, `CB-C07`, `CB-C08`, `CB-C09`,
`CB-C10`, `CB-C10A`, `CB-D01`, `CB-D02`, `CB-D03`, `CB-D04`, `CB-D05`,
`CB-D06`, `CB-D06A`, `CB-D06B`, `CB-D06C`, `CB-D06D`, `CB-D07`,
`CB-D08`, `CB-D08A`, `CB-D09`, `CB-D10`, `CB-D11`, `CB-D12`, `CB-D13`,
`CB-D13A`, `CB-H03`, `CB-H07`, `CB-H18`, `CB-H19`, `CB-H20`, `CB-H21`,
`CB-H22`, `CB-J01A`.

### Task 4.1 — enumerate complete owner boundary sources and derive epochs

**Add:**

- `architecture/policy_design_case/layer3_gy_epoch_boundary_source_registry.json`
- `architecture/policy_design_case/layer3_gy_l5_schema_regime_registry.json`
- `architecture/policy_design_case/layer3_gy_l5_schema_regime_scope_registry.json`
- `architecture/policy_design_case/layer3_gy_semantic_facet_registry.json`
- `src/polisyos/core/contracts/epoch.py`
- `src/polisyos/runtime/quality/semantic_epoch.py`
- `src/polisyos/runtime/quality/semantic_epoch_store.py`
- `tests/unit/runtime/quality/test_semantic_epoch.py`
- `tests/unit/runtime/quality/test_semantic_epoch_store.py`

**Modify:**

- `architecture/production_quality/chronology_capability_allocation.toml`
- `src/polisyos/core/contracts/__init__.py`
- `src/polisyos/runtime/quality/substrate_registry.py`
- `src/polisyos/runtime/quality/data_state_substrate.py`
- `src/polisyos/lex/knowledge/store.py`
- `src/polisyos/lex/knowledge/types.py`
- `src/polisyos/data_forge/domains/catalog/knowledge/overlay.py`
- `src/polisyos/data_forge/domains/ukraine/builders/sources.py`
- `src/polisyos/runtime/quality/README.md`
- `src/polisyos/lex/knowledge/README.md`
- `src/polisyos/data_forge/domains/catalog/knowledge/README.md`
- `docs/reference/public-surface.md`
- `tests/unit/runtime/quality/test_substrate_registry.py`
- `tests/integration/runtime_quality/test_data_state_substrate.py`
- `tests/unit/lex/test_knowledge_store_filters.py`
- `tests/unit/data_forge/domains/ukraine/test_builders.py`

The boundary registry's initial opaque registrations name the all-L5-regime,
all-L3-amendment-window and N13b-acquisition owner batches. Each row carries
one finite native `owner_kind` (`l5_schema_regime`, `lex_amendment_window`, or
`catalog_acquisition`) plus opaque scope/source bindings; registration IDs and
domains are never engine enums. The facet registry contains all eleven
ratified facets as data, never an engine enum. A novel domain, source
registration or facet row using one of the three ratified native owner kinds
must work without engine code. A genuinely new native owner kind is a new
authority integration and deliberately requires a new adapter/review; that is
not disguised as data-only growth. Add these native owner APIs; the epoch
module may not query their stores directly:

```python
class L5SchemaRegimeResolutionQuery(BaseModel):
    scope_identity_ref: Digest
    authority_purpose: str
    valid_effect_value: date
    valid_effect_coordinate_schema_profile: str
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_schema_profile: str
    visibility_knowledge_cutoff_bytes: bytes
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_schema_profile: str
    purpose_admission_cutoff_bytes: bytes
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

class L5SchemaRegimeScopeRelation(BaseModel):
    schema_regime_id: str
    scope_identity_refs: tuple[Digest, ...]
    relation_provenance_ref: ArtifactRef

class L5SchemaRegimeAssessment(BaseModel):
    schema_regime_id: str
    regime_source_ref: ArtifactRef
    regime_content_hash: Digest
    scope_relation: L5SchemaRegimeScopeRelation | None
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: Literal[
        "schema_regime_scope_missing", "schema_regime_scope_ambiguous"
    ] | None

class L5SchemaRegimeDenominatorReceipt(BaseModel):
    query: L5SchemaRegimeResolutionQuery
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    regime_registry_ref: ArtifactRef
    regime_registry_content_hash: Digest
    scope_registry_ref: ArtifactRef
    scope_registry_content_hash: Digest
    declared_regime_count: int
    assessments: tuple[L5SchemaRegimeAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

class LegalAmendmentWindowResolutionQuery(BaseModel):
    jurisdiction: str
    domain: str
    authority_purpose: str
    valid_effect_value: date
    valid_effect_coordinate_schema_profile: str
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_schema_profile: str
    visibility_knowledge_cutoff_bytes: bytes
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_schema_profile: str
    purpose_admission_cutoff_bytes: bytes
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

class LegalAmendmentWindowAssessment(BaseModel):
    amendment_ref: ArtifactRef
    amendment_content_hash: Digest
    amended_doc_ref: ArtifactRef
    resolved_scope_ref: Digest | None
    effective_from: date
    effective_to: date | None
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: Literal[
        "amendment_scope_unresolved", "amendment_scope_ambiguous",
        "amendment_knowledge_cutoff_unresolved",
    ] | None

class LegalAmendmentWindowDenominatorReceipt(BaseModel):
    query: LegalAmendmentWindowResolutionQuery
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    declared_amendment_count: int
    assessments: tuple[LegalAmendmentWindowAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

class AcquisitionBoundaryResolutionQuery(BaseModel):
    scope_identity_ref: Digest
    authority_purpose: str
    valid_effect_coordinate_schema_profile: str
    valid_effect_coordinate_bytes: bytes
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_schema_profile: str
    visibility_knowledge_cutoff_bytes: bytes
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_schema_profile: str
    purpose_admission_cutoff_bytes: bytes
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

class AcquisitionNativeMemberAssessment(BaseModel):
    native_member_ref: ArtifactRef
    native_member_content_hash: Digest
    operational_epoch_id: int
    passport_ref: ArtifactRef | None
    passport_content_hash: Digest | None
    semantic_candidate_ref: ArtifactRef | None
    semantic_candidate_content_hash: Digest | None
    binding_status: Literal["bound", "legacy_unresolved", "invalid"]
    query_disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: Literal[
        "legacy_acquisition_candidate_identity_not_established",
        "acquisition_candidate_binding_mismatch",
        "acquisition_query_context_mismatch",
    ] | None

class AcquisitionNativeMembershipReceipt(BaseModel):
    query: AcquisitionBoundaryResolutionQuery
    owner_source_snapshot_ref: ArtifactRef
    owner_source_snapshot_content_hash: Digest
    declared_native_member_count: int
    assessments: tuple[AcquisitionNativeMemberAssessment, ...]
    native_membership_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

class AcquisitionSemanticCandidateAssessment(BaseModel):
    semantic_candidate_ref: ArtifactRef
    semantic_candidate_content_hash: Digest
    disposition: Literal["applicable", "not_applicable", "unresolved"]
    failure_code: Literal[
        "acquisition_member_unresolved", "acquisition_visibility_unresolved",
        "acquisition_query_context_mismatch",
    ] | None

class AcquisitionSemanticCandidateDenominatorReceipt(BaseModel):
    query: AcquisitionBoundaryResolutionQuery
    semantic_candidate_set_hash: Digest
    declared_unique_candidate_count: int
    assessments: tuple[AcquisitionSemanticCandidateAssessment, ...]
    denominator_hash: Digest
    status: Literal["resolved", "unresolved"]
    failure_codes: tuple[str, ...]
    predicate_class: Literal["independently_reconciled"]

class AcquisitionSemanticProjectionVerificationReceipt(BaseModel):
    native_membership_receipt_ref: ArtifactRef
    native_membership_receipt_content_hash: Digest
    semantic_denominator_receipt_ref: ArtifactRef
    semantic_denominator_receipt_content_hash: Digest
    prospective_candidate_ref: ArtifactRef | None
    prospective_candidate_content_hash: Digest | None
    status: Literal["verified", "not_established"]

class AdmittedAcquisitionBoundaryEvidence(BaseModel):
    semantic_candidate_ref: ArtifactRef
    semantic_candidate_content_hash: Digest
    epoch_id: int
    native_member_ref: ArtifactRef
    native_member_content_hash: Digest
    prepared_epoch_ref: ArtifactRef
    prepared_epoch_content_hash: Digest
    passport_ref: ArtifactRef
    passport_content_hash: Digest
    pending_overlay_receipt_ref: ArtifactRef
    pending_overlay_receipt_content_hash: Digest
    native_membership_receipt_ref: ArtifactRef
    native_membership_receipt_content_hash: Digest
    semantic_denominator_receipt_ref: ArtifactRef
    semantic_denominator_receipt_content_hash: Digest
    semantic_projection_verification_receipt_ref: ArtifactRef
    semantic_projection_verification_receipt_content_hash: Digest
    semantic_epoch_stamp: SemanticEpochStamp
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class ScopedSchemaRegimeProjection(BaseModel):
    scope_identity_ref: Digest
    valid_effect_coordinate_ref: Digest
    requested_query_context_ref: Digest
    owner_source_snapshot_ref: ArtifactRef
    denominator_receipt_ref: ArtifactRef
    applicable_regime_ids: tuple[str, ...]
    applicable_regime_content_hashes: tuple[Digest, ...]
    changepoint_refs: tuple[Digest, ...]
    status: Literal["resolved", "unresolved", "contested"]
    projection_content_hash: Digest

class L5CatalogAuthority:
    def resolve_schema_regime_denominator(
        self, *, query: L5SchemaRegimeResolutionQuery
    ) -> L5SchemaRegimeDenominatorReceipt: ...

    def project_scoped_schema_regimes(
        self, *, receipt: L5SchemaRegimeDenominatorReceipt
    ) -> ScopedSchemaRegimeProjection: ...

class LegalKnowledgeStore:
    def resolve_amendment_window_denominator(
        self, *, query: LegalAmendmentWindowResolutionQuery
    ) -> LegalAmendmentWindowDenominatorReceipt: ...

class CatalogAcquisitionOverlay:
    def resolve_native_membership(
        self, *, query: AcquisitionBoundaryResolutionQuery,
        candidate: AcquisitionSemanticBoundaryCandidate | None = None,
    ) -> AcquisitionNativeMembershipReceipt: ...

    def resolve_semantic_candidate_denominator(
        self, *, query: AcquisitionBoundaryResolutionQuery,
        native_membership: AcquisitionNativeMembershipReceipt,
        candidate: AcquisitionSemanticBoundaryCandidate | None = None,
    ) -> AcquisitionSemanticCandidateDenominatorReceipt: ...

    def verify_semantic_projection(
        self, *, native_membership_ref: ArtifactRef,
        semantic_denominator_ref: ArtifactRef,
        prospective_candidate: AcquisitionSemanticBoundaryCandidate | None,
    ) -> AcquisitionSemanticProjectionVerificationReceipt: ...
```

These are three family-native sparse queries, not one temporal envelope. Each
owner receives the values it must actually interpret plus refs it must
recompute: L5/Lex receive an owner-readable valid date; all three receive exact
visibility/knowledge and purpose-admission cutoff bytes; N13b receives its
native valid/effect bytes. Every coordinate ref is
`sha256("polisyos.native-coordinate.v1\\0" || frame(family) || frame(role) ||
frame(schema_profile) || frame(coordinate_bytes))`. The query-context ref is
the domain-separated hash of the ordered applicable role refs, scope and
purpose. Value/ref disagreement rejects. An inapplicable role is absent from
that family's typed query rather than represented by a null common field.

Each receipt identifies exact frozen owner-source bytes, binds the complete
ordered assessment tuple, recomputed declared count, all query-coordinate refs,
denominator hash and typed failures. The adapter reloads that snapshot and
recomputes count/hash before converting it to `EpochBoundaryOwnerBatch`; a
self-consistent subset with a reduced declared count therefore fails against
unchanged owner bytes. The same scope/valid date at visibility cutoffs just
before and after a retroactively admitted owner row must produce two
reproducible denominators. Missing knowledge/admission history yields
`unresolved`, never present-day substitution.

L5 walks every `schema_regimes.values()` entry, never `_entries_from_l5()` or
`latest_schema_regime()`. Its new scope registry is owned and loaded by
`L5CatalogAuthority`, not by N12. It gives each regime an explicit set of
opaque scope-identity refs plus a content-bound relation-provenance ref. The
receipt binds both regime/scope registries and the composite owner snapshot;
it contains every static and dynamic regime, every joined scope relation and an
`applicable/not_applicable/unresolved` result. A missing relation is unresolved,
multiple conflicting relations are ambiguous, and the N12 boundary registry
cannot override either result. Changing only an N12/projection mapping while
the L5 relation stays fixed therefore cannot change applicability. The first
Ukraine relations are data fixtures; a new L5 regime/domain is completed by a
new L5 data relation with zero epoch-engine code.
Move the existing hard-coded Ukraine v1/v2 regime/changepoint declarations into
the new L5-owned regime registry. In particular,
`data_forge/domains/ukraine/builders/sources.py` ceases constructing the two
`SubstrateSchemaRegime` rows or their 2022 changepoint and becomes a projection
reader of that same L5 registry for its Ukraine bundle. Dynamic DCAT/manifest
regimes keep their owner-produced rows, and the complete denominator joins both
sources. A repository-quality AST/call census derives every producer and reader
of `SubstrateSchemaRegime`, `schema_regimes`, changepoint rows and the two
registry loaders across the complete candidate Python tree. The only static
declaration producer is the L5 registry loader; dynamic owner producers are
separately classified and must emit into that owner relation. A sibling
hard-coded constructor, a second changepoint literal or a reader bypassing the
scoped projection fails the census. Engine and Data Forge modules contain no
Ukraine-specific regime ID/date branch.

This projection also strangles the two live sibling shortcuts. Change
`substrate_registry._entries_from_l5` to require the exact
`ScopedSchemaRegimeProjection`; it may no longer call global
`latest_schema_regime()`. Change
`data_state_substrate._schema_regime_decision` into a generic builder over the
same projection's complete applicable regimes/changepoint refs; remove the
Ukraine v1/v2 and 2022 branch. Generation substrate entries, L4 binding/value
state and the epoch adapter all persist the same denominator/projection refs
and fail unresolved/contested together. No projection can select a different
regime from identical owner bytes.

Lex reads the complete ordered `lex_amendments`
table, then derives each amendment's scope only through its
`amended_doc_id -> lex_facts.doc_id` owner relation: the unique non-empty
`(UPPER(jurisdiction), top_domain)` pair is the scope; zero pairs is
`amendment_scope_unresolved`; multiple distinct pairs is
`amendment_scope_ambiguous`. `effective_to` is derived as the next
`effective_from` over the complete same-`amended_doc_id`/`target_anchor`
partition, exactly as the existing temporal-competence helper does. No caller
jurisdiction/domain filter is applied before that complete assessment. N13b
walks every persisted epoch/passport plus the candidate. Visibility/knowledge
cutoff is applied only after the full ordered native row assessment, so a
retroactively learned amendment/acquisition is excluded from an earlier
knowledge query without disappearing from the denominator receipt. A missing
owner table or coordinate history produces a blocked receipt, not an empty
denominator.

N13b emits two independently verified denominators. The native-membership
receipt has exactly one row for every owner-native row, including legacy rows,
passport identity and operational ordinal; deletion or post-hoc narrowing is
therefore detectable. The semantic denominator is the sorted unique set of
bound `AcquisitionSemanticBoundaryCandidate` identities plus an optional
prospective candidate. Duplicate ordinals collapse only in that projection.
A legacy/invalid native row remains recorded and makes the semantic projection
unresolved; it is never silently omitted or given a fabricated candidate.
`epoch_ref`, `SemanticEpochManifest` and `SemanticEpochStamp` bind only the
semantic-candidate denominator. Prepared/final production receipts bind their
native-membership and projection-verification receipts outside semantic
identity. Changing only `epoch_id`, native row address or retry receipt
changes native evidence but cannot change `epoch_ref`.

`core.contracts.epoch.SemanticEpochStamp` and
`AcquisitionSemanticBoundaryCandidate` are the import-safe boundary for Data
Forge. The candidate is a persisted wrapper around a separately canonical
statement, so its ref/hash never enter their own preimage; the statement binds
native scope/query refs but deliberately contains no stamp. Data Forge never
imports runtime `AdmissionPassport`:

```python
class SemanticEpochStamp(BaseModel):
    epoch_ref: Digest
    semantic_manifest_ref: ArtifactRef
    semantic_manifest_hash: Digest
    boundary_denominator_receipt_ref: ArtifactRef
    boundary_denominator_receipt_hash: Digest
    facet_denominator_receipt_ref: ArtifactRef
    facet_denominator_receipt_hash: Digest
    requested_query_context_ref: Digest
    authority_purpose: str
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_ref: Digest
    predicate_provenance_class: Literal["independently_reconciled"]

class AcquisitionSemanticBoundaryCandidateStatement(BaseModel):
    source_record_ref: ArtifactRef
    source_record_content_hash: Digest
    scope_identity_ref: Digest
    authority_purpose: str
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

class AcquisitionSemanticBoundaryCandidate(BaseModel):
    candidate_ref: ArtifactRef
    candidate_content_hash: Digest
    statement: AcquisitionSemanticBoundaryCandidateStatement
```

Candidate bytes are exactly
`frame(C(AcquisitionSemanticBoundaryCandidateStatement raw mapping))`; the
semantic digest uses
`polisyos.epoch.acquisition-semantic-boundary-candidate.v1\0`. The persisted
wrapper requires the CAS bytes, semantic digest and embedded reparsed statement
to agree. A ref/hash over the wrapper itself is forbidden.

In `semantic_epoch.py`, add strict `EpochScopeIdentity`,
`EpochResolutionQuery`, `EpochBoundarySourceRegistration/Registry`,
`EpochBoundaryAssessment`, `EpochBoundaryOwnerBatch`,
`EpochBoundaryDenominatorReceipt`, `SemanticFacetRegistration/Registry`,
`SemanticFacetValue`, `SemanticFacetDenominatorReceipt`,
`SemanticEpochManifest`, `EpochBranchAdjudication`, `EpochInputReconciliation`
and `EpochResolutionResult`. Also define the production receipts exactly:

```python
class EpochResolutionQuery(BaseModel):
    scope_identity: EpochScopeIdentity
    authority_purpose: str
    valid_effect_coordinate_evidence_ref: ArtifactRef
    valid_effect_coordinate_ref: Digest
    visibility_knowledge_cutoff_evidence_ref: ArtifactRef
    visibility_knowledge_cutoff_ref: Digest
    purpose_admission_cutoff_evidence_ref: ArtifactRef
    purpose_admission_cutoff_ref: Digest
    requested_query_context_ref: Digest

BoundaryOwnerKind = Literal[
    "l5_schema_regime", "lex_amendment_window", "catalog_acquisition"
]

class EpochBoundarySourceRegistration(BaseModel):
    registration_id: str
    owner_kind: BoundaryOwnerKind
    owner_source_ref: Digest
    opaque_scope_binding_ref: Digest

class EpochBoundaryOwnerAdapter(Protocol):
    owner_kind: BoundaryOwnerKind

    def resolve_complete_batch(
        self, *, registration: EpochBoundarySourceRegistration,
        owner_query: L5SchemaRegimeResolutionQuery
        | LegalAmendmentWindowResolutionQuery
        | AcquisitionBoundaryResolutionQuery,
        candidate_refs: tuple[ArtifactRef, ...] = (),
    ) -> EpochBoundaryOwnerBatch: ...

class SemanticFacetProvider(Protocol):
    def resolve_all(
        self, *, registry: SemanticFacetRegistry,
        owner_batches: tuple[EpochBoundaryOwnerBatch, ...],
        query: EpochResolutionQuery,
    ) -> tuple[SemanticFacetValue, ...]: ...
```

```python
class PreparedSemanticEpoch(BaseModel):
    prepared_epoch_ref: ArtifactRef
    prepared_content_hash: Digest
    query: EpochResolutionQuery
    stamp: SemanticEpochStamp
    boundary_candidate_refs: tuple[ArtifactRef, ...]
    owner_denominator_receipt_refs: tuple[ArtifactRef, ...]
    status: Literal["prepared"]

class SemanticEpochProductionReceipt(BaseModel):
    production_mode: Literal["ordinary", "acquisition_finalization"]
    status: Literal["appended", "no_change", "not_established", "contested"]
    prepared_epoch_ref: ArtifactRef | None
    admitted_boundary_evidence_ref: ArtifactRef | None
    epoch_ref: Digest | None
    semantic_manifest_ref: ArtifactRef | None
    owner_denominator_receipt_refs: tuple[ArtifactRef, ...]
    history_append_receipt_ref: ArtifactRef | None
    chronology_bundle_ref: ArtifactRef | None
    chronology_verification_ref: ArtifactRef | None
    requested_query_context_ref: Digest
    failure_codes: tuple[str, ...]
```

The positive fields are required for `appended`/`no_change` and forbidden for
the two negative statuses; negative statuses require at least one exact code.
`ordinary` forbids both prepared/admitted-evidence refs;
`acquisition_finalization` requires both, and their verified bytes bind one
stable candidate/stamp pair.
Use these exact calls:

```python
def reconcile_epoch_inputs(
    *,
    query: EpochResolutionQuery,
    boundary_registry: EpochBoundarySourceRegistry,
    owner_batches: Sequence[EpochBoundaryOwnerBatch],
    facet_registry: SemanticFacetRegistry,
    facet_values: Sequence[SemanticFacetValue],
) -> EpochInputReconciliation: ...

def resolve_semantic_epoch(
    *,
    query: EpochResolutionQuery,
    boundary_registry: EpochBoundarySourceRegistry,
    owner_batches: Sequence[EpochBoundaryOwnerBatch],
    facet_registry: SemanticFacetRegistry,
    facet_values: Sequence[SemanticFacetValue],
    prior_manifests: Sequence[SemanticEpochManifest],
    owner_branch_adjudications: Sequence[EpochBranchAdjudication] = (),
) -> EpochResolutionResult: ...

class SemanticEpochHistoryRepository(Protocol):
    def append_if_current(
        self,
        *,
        expected_head_refs: tuple[Digest, ...],
        manifest_ref: ArtifactRef,
        native_member_ref: ArtifactRef,
        predecessor_refs: tuple[Digest, ...],
    ) -> EpochHistoryAppendReceipt: ...

    def resolve_scope_history(
        self, *, scope: EpochScopeIdentity, authority_purpose: str
    ) -> EpochScopeHistory: ...

class SemanticEpochQualificationAdapter(NativeChronologyAuthorityAdapter):
    def __init__(
        self, *, history: SemanticEpochHistoryRepository,
        artifacts: ArtifactStore,
        policy_owner: EpochChronologyPolicyOwner,
    ) -> None: ...

    def reconcile_candidate(
        self, request: NativeChronologyQuery
    ) -> NativeChronologyCandidate: ...

class SemanticEpochService:
    def __init__(
        self,
        *,
        boundary_registry: EpochBoundarySourceRegistry,
        boundary_adapters: Mapping[BoundaryOwnerKind, EpochBoundaryOwnerAdapter],
        facet_registry: SemanticFacetRegistry,
        facet_provider: SemanticFacetProvider,
        history: SemanticEpochHistoryRepository,
        artifact_store: ArtifactStore,
        qualification_consumer: QualificationConsumer,
        chronology_adapter: SemanticEpochQualificationAdapter,
    ) -> None: ...

    def resolve_and_persist_epoch(
        self, *, query: EpochResolutionQuery
    ) -> SemanticEpochProductionReceipt: ...

    def prepare_epoch_candidate(
        self,
        *,
        query: EpochResolutionQuery,
        boundary_candidate_refs: Mapping[str, tuple[ArtifactRef, ...]],
    ) -> PreparedSemanticEpoch: ...

    def finalize_admitted_epoch(
        self,
        *,
        prepared_epoch_ref: ArtifactRef,
        admitted_boundary_evidence_ref: ArtifactRef,
    ) -> SemanticEpochProductionReceipt: ...
```

The sparse query binds scope identity, authority purpose, three exact
coordinate-evidence artifact refs plus their semantic refs, and requested query
context. `SemanticEpochService` loads/recomputes those evidence bytes and
constructs the applicable family-native query type; neither a caller nor the
N12 registration row supplies decoded dates/cutoffs. Every owner batch assesses every native member as applicable,
not-applicable or unresolved and hashes ordered rows; registry reconciliation
proves the exact expected registration IDs and every receipt. Each facet value
binds source-record and semantic-value hashes, so a rename with unchanged
semantic hash is generically annotation-only. Missing, unknown, unregistered,
malformed or incomplete input -> `epoch_scope_unresolved`; incomparable
branches -> `contested/not_established`, never transaction-time ordering.

`resolve_semantic_epoch` is the pure internal reducer; callers cannot supply
its `owner_batches` or facets to an authority path. `SemanticEpochService` is
the production producer. It requires exactly one adapter for every native
`owner_kind` present in the boundary registry, rejects extra/missing/duplicate
kind adapters, dispatches every registration row through its declared kind,
and calls one generic facet provider over every facet row and complete owner
batches. It never maps provider objects by registration or facet ID. Ordinary
L3/L5 resolution uses
`resolve_and_persist_epoch`: persist exact context/manifest/native member,
compare-and-append the family-native history/head set, rebuild the complete
native prefix and run the production epoch adapter through Cluster 2's
`QualificationConsumer` and sealed persistence coordinator. The same atomic producer commit
appends the three exact Cluster-4 transitions to
`chronology_capability_allocation.toml`; a source producer/call-site census and
the allocation history must change together.

An acquisition cannot append an epoch before the acquisition is admitted, and
its passport cannot bind an epoch that has not yet been resolved. Close that
cycle with a typed two-phase handshake, not a default or a future-ref cycle.
`AcquisitionNativeMembershipReceipt` is complete over every native row.
`AcquisitionSemanticCandidateDenominatorReceipt` is the stable deduplicated
projection and never contains an operational ordinal, native-row identity,
passport or admission-receipt ref. Their independently persisted
`AcquisitionSemanticProjectionVerificationReceipt` proves the projection
under the exact query. A historical row lacking a candidate identity remains
in the native receipt under its exact artifact/hash and unresolved code; it
cannot be dropped, upgraded or assigned a fabricated candidate.
`prepare_epoch_candidate` accepts only opaque
content-bound candidate refs keyed by registered owner source; each provider
resolves/recomputes them. It persists a prepared candidate artifact and
deterministic stamp over that stable projection but moves no epoch/native head.

After Data Forge durably admits the passported row in hidden
`pending_epoch_activation`, it emits a separate
`AdmittedAcquisitionBoundaryEvidence`. That evidence is not part of the epoch
preimage: it binds the already-computed candidate and prepared stamp to the now
existing passport and pending-overlay receipt. `finalize_admitted_epoch`
resolves the exact admission evidence, re-enumerates complete native
membership, regenerates the semantic projection and requires the semantic
denominator plus prepared manifest/stamp to remain byte-identical. The native
receipt is expected to change when the pending row appears; its new row must
bind the same semantic candidate, and the projection-verification receipt
links both versions outside semantic identity. It separately verifies that
passport bytes bind that candidate and stamp and never asks a pre-passport
stamp to contain its future passport ref. Only then does it compare-and-append native history, run the
production `EpochQualificationAdapter` through Cluster 2's
`QualificationConsumer`, and persist the common proof. The returned production
receipt binds both native/semantic denominators, projection verification,
admitted evidence, manifest, history append, common bundle and verifier refs.
Any missing provider, unresolved result,
post-admission binding mismatch or future-ref attempt persists only a typed
non-receipt; no partial member/head is appended. The acquisition orchestrator
is the first production caller and activates visibility only after this receipt
is independently verified by the overlay.

`semantic_epoch_store.py` is the epoch family's native owner, not a common
chronology store. Its file-backed implementation uses append-only manifest
refs plus an atomic compare-and-append scope-head index; it never stores
release/run/movement records. Tests cover concurrent expected-head conflict,
idempotent identical append, branch preservation, crash before head movement
and full-prefix rebuild from every native member.

Required red nodes include
`test_every_registered_boundary_source_reconciles_a_complete_native_receipt`,
`test_missing_native_table_is_blocked_not_empty`,
`test_native_receipt_subset_with_self_consistent_count_fails_source_snapshot`,
`test_native_coordinate_bytes_ref_mismatch_rejects`,
`test_retroactive_row_differs_before_and_after_knowledge_cutoff`,
`test_novel_domain_and_facet_rows_require_no_engine_change`,
`test_novel_registration_reuses_owner_kind_without_provider_map_change`,
`test_missing_or_novel_owner_kind_fails_closed`,
`test_l5_scope_relation_not_projection_mapping_decides_applicability`,
`test_l5_regime_without_owner_scope_relation_is_epoch_scope_unresolved`,
`test_third_regime_and_novel_domain_agree_across_epoch_generation_and_l4`,
`test_ukraine_builder_reads_canonical_l5_registry_without_regime_literals`,
`test_complete_regime_producer_reader_census_rejects_sibling_declaration`,
`test_generation_and_data_state_cannot_call_global_latest_schema_regime`,
`test_scope_without_regime_or_amendment_is_epoch_scope_unresolved`,
`test_retroactive_reissue_at_same_bitemporal_coordinates_changes_epoch_ref`,
`test_incomparable_branches_fail_closed`, and
`test_unchanged_semantic_hash_rename_is_annotation_only`,
`test_service_collects_every_registered_provider_without_caller_batches`,
`test_service_persists_native_history_and_common_proof_before_return`,
`test_same_candidate_two_ordinals_change_native_not_semantic_denominator`,
`test_deleting_either_native_row_fails_membership_completeness`,
`test_new_semantic_candidate_changes_epoch`, and
`test_legacy_native_row_is_recorded_and_blocks_positive_epoch`. Ukraine is only the
first data fixture; a source scan rejects `ukraine|prewar|wartime` in engine
code.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/runtime/quality/test_semantic_epoch.py \
  tests/unit/runtime/quality/test_semantic_epoch_store.py \
  tests/unit/runtime/quality/test_substrate_registry.py \
  tests/integration/runtime_quality/test_data_state_substrate.py \
  tests/unit/lex/test_knowledge_store_filters.py \
  tests/unit/data_forge/domains/ukraine/test_builders.py \
  tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py
! rg -n -i 'prewar|wartime|ukraine_schema_v[12]|2022-02-24' \
  src/polisyos/runtime/quality/semantic_epoch.py \
  src/polisyos/runtime/quality/substrate_registry.py \
  src/polisyos/runtime/quality/data_state_substrate.py \
  src/polisyos/data_forge/domains/ukraine/builders/sources.py
```

### Task 4.2 — bind N13b to the semantic stamp

**Modify:**

- `src/polisyos/runtime/quality/acquisition_executor.py`
- `src/polisyos/data_forge/domains/catalog/knowledge/overlay.py`
- `tests/unit/runtime/quality/test_acquisition_executor.py`
- `tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py`
- `tests/unit/data_forge/domains/catalog/knowledge/test_acquisition_authority.py`
- `tests/unit/runtime/quality/test_acquisition_overlay_visibility.py`

Preserve `epoch_id` as N13b's operational ordinal. Add the full
`SemanticEpochStamp` JSON/hash/ref to `AdmissionPassport`,
its private persisted `_Passport`, `OverlayAdmissionReceipt` and the overlay
table. This is an explicit v1-to-v2 schema migration, not a constructor default:

- bump the passport, receipt and overlay schema profiles to v2 while retaining
  a private v1 decoder used only for historical readback;
- migrate `acquisition_epochs` transactionally by inspecting
  `information_schema.columns`, adding nullable `semantic_epoch_ref`,
  `semantic_epoch_stamp_sha256`, `semantic_epoch_stamp_json`,
  `prepared_semantic_epoch_ref`, `semantic_epoch_production_receipt_ref` and
  non-null `epoch_activation_state` (`legacy_not_established`,
  `pending_epoch_activation`, `active`), and advancing the table metadata
  version only after the complete column/check-constraint set exists;
- add an owner-native `acquisition_epoch_members` relation with
  `(table_name, canonical_primary_key_bytes, canonical_primary_key_hash,
  epoch_id, passport_id)` and a uniqueness constraint over table/key/epoch;
  populate it transactionally for every overlay row **referenced by the
  admission** in every table in `_BASELINE_UNION_TABLES`, including an existing
  metadata row reused by an idempotent registration;
- decode a legacy null triple as `not_established`; a partial triple is corrupt
  and fails closed; and
- never synthesize a positive stamp for a v1 row or make resolver/query
  arguments optional to preserve an old caller.

The stamp binds epoch/manifest, boundary and
facet denominator receipt refs+hashes, requested query context, purpose,
valid/effect, visibility/knowledge, purpose cutoff and frozen predicate class.
The admission orchestrator constructs and CAS-binds the pre-passport
`AcquisitionSemanticBoundaryCandidate`, calls `prepare_epoch_candidate`, then
passes that prepared receipt—not a supplied positive ref—to the passport
builder. `admit_epoch` first reconstructs the candidate/complete native
evidence, compares the prepared stamp and commits the row/passport hidden as
`pending_epoch_activation`. The orchestrator then calls
`finalize_admitted_epoch` with the separately persisted
`AdmittedAcquisitionBoundaryEvidence`; finally the overlay
reloads/verifies the semantic production receipt and atomically changes only
that epoch to `active`.

Visibility is one owner-native generated strangle, not a flag check on the
`acquisition_epochs` row. At migration/startup, derive the complete overlay
member-key specification by reading DuckDB primary-key metadata for **every**
table in `_BASELINE_UNION_TABLES`; reject a table with no unique native key or
a table missing from the relation. Each pending-admission receipt carries the
complete six-table referenced-member denominator, and commit fails if any
native key used by that admission lacks its epoch/passport binding. This
includes `_insert_registration`'s pre-existing rows; returning early cannot
skip membership.

`open_catalog_read_session` keeps all baseline rows, but each overlay arm uses
an `EXISTS`/semi-join from its canonical primary-key bytes through
`acquisition_epoch_members` to at least one `active` acquisition epoch. It
never raw-joins (which would duplicate a row reused by two active epochs) and
never unconditionally unions an overlay table. The generated denominator must equal
the exact live six-table set and the read-session builder has one code path for
all members, so adding a seventh baseline-union table without a generated key
and membership relation fails closed. All visibility queries therefore exclude
pending/legacy rows. Each
phase is content-idempotent: crash before admission moves nothing; crash after
pending commit exposes no row; crash after epoch finalization resumes activation
without appending a second epoch. A failed finalization retains a visible audit
gap and quarantined row, never a fabricated epoch.

The exact new owner bridge is:

```python
class ActivatedSemanticEpochAdmissionReceipt(BaseModel):
    passport_ref: ArtifactRef
    prepared_epoch_ref: ArtifactRef
    pending_overlay_receipt_ref: ArtifactRef
    semantic_epoch_production_receipt_ref: ArtifactRef
    overlay_admission_receipt_ref: ArtifactRef
    native_membership_receipt_ref: ArtifactRef
    semantic_denominator_receipt_ref: ArtifactRef
    semantic_projection_verification_receipt_ref: ArtifactRef
    semantic_epoch_stamp: SemanticEpochStamp
    activation_state: Literal["active"]

def admit_acquisition_with_semantic_epoch(
    *,
    epoch_id: int,
    raw_evidence_ref: JournalEventRef,
    artifact_store: _ArtifactStore,
    authority: _CanonicalAuthority,
    overlay: CatalogAcquisitionOverlay,
    epoch_service: SemanticEpochService,
    epoch_query: EpochResolutionQuery,
    live_source_execution: LiveSourceExecutionEvidence | None = None,
) -> ActivatedSemanticEpochAdmissionReceipt: ...

class CatalogAcquisitionOverlay:
    def admit_epoch(
        self,
        *,
        passport: _Passport,
        prepared_epoch: _PreparedSemanticEpoch,
        boundary_candidate: AcquisitionSemanticBoundaryCandidate,
        artifact_store: _ArtifactStore,
        authority: _CanonicalAuthority,
    ) -> PendingOverlayAdmissionReceipt: ...

    def activate_semantic_epoch(
        self,
        *,
        pending_receipt: PendingOverlayAdmissionReceipt,
        production_receipt: _SemanticEpochProductionReceipt,
        artifact_store: _ArtifactStore,
    ) -> OverlayAdmissionReceipt: ...
```

The Data Forge annotations are its own structural protocols/core DTOs, never a
runtime import. The final receipt binds every phase ref plus the complete
native-membership, deduplicated semantic-denominator and projection-
verification receipts; only it is returned as an admitted/visible result. The
stamp binds the semantic denominator, while deletion detection binds the native
receipt outside it.

Migrate the complete static call denominator
atomically with the signature change: six `build_admission_passport(...)` and
eighteen `admit_epoch(...)` call expressions were measured at planning time.
Re-run an AST census immediately before editing and fail the task if its set
diff is non-empty; no intermediate commit may leave any caller on the old
signature.

Exact failure dispositions are `resolver_unavailable`, `scope_unresolved`,
`basis_mismatch`, `query_context_mismatch`, `epoch_ref_mismatch` and
`predicate_not_authority_grade`. Required nodes include
`test_passport_uses_resolved_semantic_stamp_not_supplied_epoch_ref`,
`test_overlay_reconciles_stamp_against_complete_owner_denominator`,
`test_overlay_ordinal_never_substitutes_for_semantic_epoch_ref`, and
`test_legacy_row_has_not_established_semantic_epoch`,
`test_v1_table_migrates_transactionally_to_nullable_v2_columns`,
`test_partial_semantic_stamp_columns_fail_closed`,
`test_acquisition_authority_supplies_epoch_service_and_query`, and
`test_overlay_visibility_never_promotes_a_legacy_null_stamp`,
`test_pending_epoch_activation_is_hidden_after_crash`,
`test_pending_epoch_is_hidden_from_all_six_baseline_union_views`,
`test_every_baseline_union_table_has_generated_member_key_and_epoch_relation`,
`test_active_reuser_exposes_complete_metadata_when_creator_is_pending`,
`test_two_active_epochs_reusing_registration_emit_each_row_once`,
`test_novel_union_table_without_native_key_relation_fails_closed`,
`test_finalization_reenumerates_admitted_owner_denominator`, and
`test_activation_retry_cannot_append_a_second_semantic_epoch`,
`test_prepared_epoch_identity_excludes_future_passport_ref`, and
`test_finalization_binds_passport_to_stable_candidate_without_rehashing_epoch`,
`test_same_semantic_candidate_under_two_ordinals_keeps_one_epoch_ref`,
`test_duplicate_ordinal_projection_binds_every_native_row`,
`test_deleting_reused_native_row_fails_complete_membership_receipt`,
`test_candidate_a_with_native_row_or_passport_b_refuses`, and
`test_preparation_succeeds_before_operational_ordinal_exists`.

The combined 4.1+4.2 `c4-epoch` boundary is executed only by the same single
manifest transition, with the C2 committed receipt supplied through its
Task-4.1 declared predecessor relation. Its private history phase requires the C2
allocation byte/entry-hash prefix unchanged, exactly three new EOF history
entries with the Cluster-4 activation split, a fresh J05/topology result and
the exact candidate-path set at the new HEAD. Any later C4 boundary changes
source topology; closeout therefore reruns the Cluster-4 history/topology
predicate rather than reusing this receipt.

### Task 4.3 — bind certificates, perturbations and OpenWorldRisk

**Add:**

- `src/polisyos/runtime/quality/epoch_validity_cascade.py`
- `src/polisyos/runtime/quality/open_world_risk.py`
- `tests/unit/runtime/quality/test_epoch_validity_cascade.py`
- `tests/unit/runtime/quality/test_open_world_risk.py`

**Modify:**

- `src/polisyos/runtime/quality/promotion_sequence.py`
- `src/polisyos/runtime/quality/generation_cycle.py`
- `src/polisyos/runtime/quality/recursive_generation_cycle.py`
- `src/polisyos/runtime/quality/public_export.py`
- `src/polisyos/runtime/quality/README.md`
- `src/polisyos/runtime/http/container.py`
- `src/polisyos/runtime/http/services/control/generation_cycle.py`
- `tests/unit/runtime/quality/test_promotion_sequence.py`
- `tests/unit/runtime/quality/test_generation_cycle.py`
- `tests/unit/runtime/http/test_control_service_di.py`
- `tests/unit/runtime/quality/test_public_export.py`

Add `EpochCertificateBinding`, `DerivationRecipeBinding`,
`EpochDependencyEdge/Graph`, `AdvisoryPerturbationEvent`,
`OwnerAdjudicatedTargetDisposition`, `TargetDispositionVector` and
`EpochValidityTransitionArtifact`:

```python
def bind_certificate_to_epoch(
    *, certificate_ref: ArtifactRef, certificate_content_hash: Digest,
    epoch: SemanticEpochManifest, input_certificate_refs: Sequence[ArtifactRef],
    recipe: DerivationRecipeBinding, canonical_producer_ref: str,
    authority_purpose: str, native_coordinate_refs: Sequence[Digest],
    rule_schema_profile_refs: Sequence[Digest],
) -> EpochCertificateBinding: ...

def resolve_owner_target_dispositions(
    *, advisory_events: Sequence[AdvisoryPerturbationEvent],
    owner_dispositions: Sequence[OwnerAdjudicatedTargetDisposition],
    dependency_graph: EpochDependencyGraph,
) -> TargetDispositionVector: ...

def build_epoch_validity_transition(
    *, previous_epoch: SemanticEpochManifest,
    current_epoch: SemanticEpochManifest,
    certificates: Sequence[EpochCertificateBinding],
    dependency_graph: EpochDependencyGraph,
    target_vector: TargetDispositionVector,
    requested_query_context_ref: Digest,
) -> EpochValidityTransitionArtifact: ...

class EpochDependencyDenominatorReceipt(BaseModel):
    denominator_ref: Digest
    certificate_bindings: tuple[EpochCertificateBinding, ...]
    dependency_graph: EpochDependencyGraph
    target_refs: tuple[ArtifactRef, ...]
    predicate_class: Literal["independently_reconciled"]

class EpochDependencyDenominatorProvider(Protocol):
    def resolve_complete_epoch_dependencies(
        self,
        *,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> EpochDependencyDenominatorReceipt: ...

class EpochPerturbationAdjudicationReceipt(BaseModel):
    denominator_ref: Digest
    advisory_events: tuple[AdvisoryPerturbationEvent, ...]
    owner_dispositions: tuple[OwnerAdjudicatedTargetDisposition, ...]
    predicate_class: Literal["independently_reconciled"]

class EpochPerturbationAdjudicationProvider(Protocol):
    def resolve_complete_owner_adjudications(
        self,
        *,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> EpochPerturbationAdjudicationReceipt: ...

class PersistedEpochValidityTransition(BaseModel):
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest
    dependency_denominator_ref: Digest
    signed_artifact_evidence_ref: ArtifactRef
    signing_profile_ref: ArtifactRef
    producer_identity_ref: ArtifactRef
    signer_provenance_ref: ArtifactRef
    requested_query_context_ref: Digest
    authority_purpose: str

class EpochValidityTransitionProducer:
    def __init__(
        self,
        *,
        dependency_inventory: EpochDependencyDenominatorProvider,
        adjudications: EpochPerturbationAdjudicationProvider,
        epoch_history: SemanticEpochHistoryRepository,
        signed_artifacts: SignedArtifactEvidenceRepository,
        signing_authority: EpochTransitionSigningAuthority,
    ) -> None: ...

    def produce_and_persist(
        self,
        *,
        previous_epoch_ref: ArtifactRef,
        current_epoch_receipt_ref: ArtifactRef,
        requested_query_context_ref: Digest,
        authority_purpose: str,
    ) -> PersistedEpochValidityTransition: ...

class EpochTransitionSigningAuthority(Protocol):
    def sign_transition(
        self, *, transition_bytes: bytes, authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> PersistedSignedArtifactEvidence | EpochTransitionSigningNonReceipt: ...

class EpochTransitionSigningNonReceipt(BaseModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "epoch_transition_signer_not_established",
        "epoch_transition_signing_profile_mismatch",
        "epoch_transition_exact_evidence_unavailable",
    ]
    predicate_class: Literal["not_established", "independently_reconciled"]
```

Transport order/action is never authority. Exact owner/target/purpose conflicts
become contested/review; annotation-only, invalidate, reissue, supersede and
withdraw preserve historical bytes. Bind the executable recipe, but do **not**
add a recipe executor: global automatic recompute remains
`absent/unallocated`; a known canonical producer not invoked here remains
`producer_missing`. The missed-obligation automatic chain also remains
`absent/unallocated`; this slice delivers challenge/invalidation and requires a
new widened epoch.

`EpochValidityTransitionProducer` is the missing authority-grade epoch
producer, not a caller-shaped artifact constructor. It resolves the current and
prior epoch bytes from the epoch-native history, asks the injected canonical
Decision Validity inventory adapter for its complete certificate/dependency
denominator, asks the canonical target owners' adjudication provider for the
complete owner-result denominator, independently recomputes the target vector,
persists canonical bytes through the Cluster-3
`SignedArtifactEvidenceRepository` and a container-owned
`EpochTransitionSigningAuthority`, binds signing-profile/producer provenance,
reloads the exact blob/manifest/signature evidence, and returns
only content-bound refs/hashes/provenance. A caller cannot supply certificates,
targets, status, signer, signing profile or producer identity. A generic
`ArtifactStore` cannot issue a transition because it lacks the exact manifest/
signature evidence port; `signature_sidecar_ref` is not invented as an
`ArtifactRef`. Decision Validity independently
reconciles the same native target denominator at intake; producer agreement is
necessary, never sufficient. A container with no admitted signing/trust profile
returns `epoch_transition_signer_not_established` and retains the producer's
incomplete label; it never falls back to an ambient/self-signed key.
The epoch owner can adjudicate the direct old-manifest/new-manifest transition;
incident/appeal/correction/retraction owners remain external inputs to the
adjudication provider. Missing or conflicting owner results freeze as
`review_required`/`contested`; chronology never guesses their action.

In the same module add `DeploymentScopeQuery`,
`DeploymentScopeRoleResolution`, `CompetentDeploymentScopeEvidence`,
`VerifiedDeploymentScopeEvidence`, `DeclaredScopeComponent/Manifest`,
`OpenWorldRiskComponent/Vector/PublicLimitation`,
`DeploymentLifecycleQueryOwner`, `CompetentDeploymentScopeEvidenceVerifier`
and `resolve_open_world_risk(...)`. The caller cannot supply role, status or
severity; missing owner/evidence or a novel component produces a persisted,
round-tripped `not_established` vector. The competent lifecycle owner remains
unappointed and positive evidence producer remains missing.

First add the shared owner query artifact consumed by both OWR and the
Decision Validity pre-N9 gate:

```python
class PromotionCandidateOccurrenceStatement(BaseModel):
    ordinal: int = Field(ge=0)
    design_problem_binding_ref: ArtifactRef
    design_problem_binding_content_hash: Digest
    candidate_id: str
    candidate_content_hash: Digest
    candidate_summary: CandidateSummary
    candidate_summary_content_hash: Digest
    cycle_index: int = Field(ge=0)

class PromotionCandidateIdentity(BaseModel):
    ordinal: int = Field(ge=0)
    occurrence_ref: ArtifactRef
    occurrence_content_hash: Digest
    candidate_id: str
    candidate_content_hash: Digest
    candidate_summary_content_hash: Digest

class PromotionCandidateDenominatorStatement(BaseModel):
    owner_snapshot_ref: ArtifactRef
    owner_snapshot_content_hash: Digest
    design_problem_binding_ref: ArtifactRef
    declared_candidate_count: int = Field(ge=0)
    ordered_occurrence_refs: tuple[ArtifactRef, ...]
    ordered_occurrence_content_hashes: tuple[Digest, ...]
    predicate_class: Literal["recomputed"]

class PersistedPromotionCandidateDenominator(BaseModel):
    denominator_ref: ArtifactRef
    denominator_content_hash: Digest
    statement: PromotionCandidateDenominatorStatement

class EpochPromotionQueryEvidence(BaseModel):
    family: Literal["semantic_epoch"]
    candidate: PromotionCandidateIdentity
    query_artifact_ref: ArtifactRef
    query_artifact_content_hash: Digest
    native_requested_query_context_ref: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class DeploymentPromotionQueryEvidence(BaseModel):
    family: Literal["deployment_scope"]
    candidate: PromotionCandidateIdentity
    query_artifact_ref: ArtifactRef
    query_artifact_content_hash: Digest
    native_requested_query_context_ref: Digest
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class PromotionCandidateOwnerContext(BaseModel):
    candidate: PromotionCandidateIdentity
    epoch_query: EpochPromotionQueryEvidence
    deployment_query: DeploymentPromotionQueryEvidence
    member_query_context_ref: Digest

class PromotionCandidateContextMemberStatement(BaseModel):
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    epoch_query_evidence_ref: ArtifactRef
    epoch_query_evidence_content_hash: Digest
    epoch_native_query_context_ref: Digest
    deployment_query_evidence_ref: ArtifactRef
    deployment_query_evidence_content_hash: Digest
    deployment_native_query_context_ref: Digest
    authority_purpose: str

class PromotionOwnerQueryContextStatement(BaseModel):
    design_problem_binding_ref: ArtifactRef
    design_problem_binding_content_hash: Digest
    authority_purpose: str
    candidate_denominator_ref: ArtifactRef
    candidate_denominator_content_hash: Digest
    ordered_candidate_contexts: tuple[PromotionCandidateOwnerContext, ...]
    requested_query_context_ref: Digest
    owner_resolution_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class PersistedPromotionOwnerQueryContext(BaseModel):
    context_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    statement: PromotionOwnerQueryContextStatement
    verifier_provenance_ref: ArtifactRef

class BoundPromotionCandidateContextStatement(BaseModel):
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    member_context_ref: ArtifactRef
    member_context_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    ordinal: int = Field(ge=0)

class PersistedBoundPromotionCandidateContext(BaseModel):
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    statement: BoundPromotionCandidateContextStatement

class PersistedPromotionContextBatch(BaseModel):
    aggregate_context: PersistedPromotionOwnerQueryContext
    ordered_bound_members: tuple[PersistedBoundPromotionCandidateContext, ...]

class PromotionOwnerQueryContextNonReceipt(BaseModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "promotion_query_context_owner_unavailable",
        "epoch_query_unresolved", "deployment_query_unresolved",
        "promotion_query_context_binding_mismatch",
        "promotion_candidate_denominator_mismatch",
        "promotion_query_family_substitution",
    ]

class _CompletedGenerationCandidateBatch(Protocol):
    """Private post-loop batch; no public constructor or partial snapshot."""

class PromotionCandidateDenominatorOwner(Protocol):
    def freeze_completed_generation(
        self, *, completed_batch: _CompletedGenerationCandidateBatch,
    ) -> PersistedPromotionCandidateDenominator \
        | PromotionOwnerQueryContextNonReceipt: ...

class EpochResolutionQueryOwner(Protocol):
    def resolve_for_promotion(
        self, *, design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
    ) -> EpochPromotionQueryEvidence | PromotionOwnerQueryContextNonReceipt: ...

class DeploymentScopeQueryOwner(Protocol):
    def resolve_for_promotion(
        self, *, design_problem_binding_ref: ArtifactRef,
        candidate: PromotionCandidateIdentity,
    ) -> DeploymentPromotionQueryEvidence \
        | PromotionOwnerQueryContextNonReceipt: ...

class PromotionOwnerQueryContextVerifier(Protocol):
    def verify_exact(
        self, *, context_ref: ArtifactRef,
        context_bytes: bytes,
    ) -> (
        PersistedPromotionOwnerQueryContext
        | PromotionOwnerQueryContextNonReceipt
    ): ...

class PromotionOwnerQueryContextRepository(Protocol):
    def resolve_verified(
        self, *, context_ref: ArtifactRef,
    ) -> (
        PersistedPromotionOwnerQueryContext
        | PromotionOwnerQueryContextNonReceipt
    ): ...

class ArtifactPromotionOwnerQueryContextRepository(
    PromotionOwnerQueryContextRepository
):
    def __init__(
        self, *, artifacts: ArtifactStore,
        verifier: PromotionOwnerQueryContextVerifier,
    ) -> None: ...

class PromotionOwnerQueryContextAuthority:
    def __init__(
        self, *, candidates: PromotionCandidateDenominatorOwner,
        epoch_queries: EpochResolutionQueryOwner,
        deployment_queries: DeploymentScopeQueryOwner,
        artifacts: ArtifactStore,
        verifier_provenance_ref: ArtifactRef,
    ) -> None: ...

    def persist_for_promotion(
        self, *, denominator_ref: ArtifactRef,
    ) -> (
        PersistedPromotionContextBatch
        | PromotionOwnerQueryContextNonReceipt
    ): ...
```

The generation owner exposes one post-loop/pre-N9 freezer. The live controller
passes its completed local summary tuple only by converting it to private
`_CompletedGenerationCandidateBatch` after loop termination; no provisional
snapshot or public `Sequence` is accepted. The freezer persists one occurrence
artifact per summary and then one complete denominator artifact, returning its
sealed ref. A late append, a second unequal freeze or any N9 input before that
receipt fails. The context authority accepts only the sealed denominator ref,
reloads the owner snapshot and every occurrence, and requires contiguous unique
ordinals, exact count/order and exact candidate/summary bytes.
For every row it asks each family-native owner for one typed query artifact.
Epoch and deployment evidence have distinct fixed kinds/schemas and digest
domains (`polisyos.promotion-query.semantic-epoch.v1\0` and
`polisyos.promotion-query.deployment-scope.v1\0`); each native verifier checks
its own scope, purpose, candidate binding, sparse coordinates and native query-
context ref. A family tag, kind or verifier substitution is rejected before
aggregation.

Each `PromotionCandidateContextMemberStatement` is persisted before the
aggregate and binds exactly one occurrence plus its separately typed epoch and
deployment evidence. `member_query_context_ref` is exactly the domain-separated canonical hash of
the design binding, authority purpose, candidate identity and the two ordered
typed query-evidence refs/content hashes/native context refs. The outer
`requested_query_context_ref` is exactly
`sha256("polisyos.promotion-owner-query-context.v2\0" || frame(C(mapping)))`,
where `mapping` contains the design binding/hash, purpose, complete candidate-
denominator ref/hash and the ordered `(candidate identity,
member_query_context_ref)` rows. After the aggregate exists, the authority
persists one `BoundPromotionCandidateContextStatement` per ordered member; this
binds the aggregate and member without a reference cycle. The aggregate verifier independently reloads
the candidate denominator and both native query artifacts, recomputes every
member ref and the aggregate, and requires an exact row/denominator bijection.
It does not interpret or merge either family's sparse temporal roles: those
remain inside the two typed opaque evidence records.

The persisted aggregate plus its sealed bound-member ref/hash is the only
query-context input accepted by OWR, DV, N9, projection, receipt and replay.
Each candidate gate resolves the bound member, proves its unique membership in
that aggregate and then uses that row's typed native refs; a caller cannot
nominate a row or independently supply `CandidateSummary`. Dropped, duplicated, reordered or cross-promotion
rows, an authentic epoch artifact placed in the deployment slot, reuse of one
authentic member under another aggregate, reuse of candidate A's OWR vector or
DV subject for candidate B within one authentic aggregate, and mutation of only the outer
aggregate ref all fail. No `runtime_hints`, DTO digest, candidate `Sequence` or
controller-selected context can substitute.

Define the read path independently of the live producer:

```python
class OpenWorldRiskArtifactResolver(Protocol):
    def resolve_verified(
        self, *, vector_artifact_ref: ArtifactRef,
        expected_raw_cas_hash: Digest, expected_semantic_hash: Digest,
        requested_query_context_ref: Digest,
        expected_aggregate_context_ref: ArtifactRef,
        expected_bound_member_ref: ArtifactRef,
        expected_candidate_occurrence_ref: ArtifactRef,
        expected_verifier_provenance_ref: ArtifactRef,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt: ...

class VerifiedOpenWorldRiskVector(BaseModel):
    vector: OpenWorldRiskVector
    vector_artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    requested_query_context_ref: Digest
    aggregate_context_ref: ArtifactRef
    bound_member_ref: ArtifactRef
    candidate_occurrence_ref: ArtifactRef
    verifier_provenance_ref: ArtifactRef
    predicate_class: Literal["independently_reconciled"]

class OpenWorldRiskResolutionNonReceipt(BaseModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "open_world_vector_unresolved", "open_world_vector_content_mismatch",
        "open_world_vector_query_mismatch", "open_world_verifier_untrusted",
    ]

class PersistedOpenWorldRiskVector(BaseModel):
    vector_artifact_ref: ArtifactRef
    raw_cas_hash: Digest
    semantic_hash: Digest
    declared_component_denominator_ref: Digest
    lifecycle_role_denominator_ref: Digest
    verifier_provenance_ref: ArtifactRef
    requested_query_context_ref: Digest
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest

class OpenWorldRiskProductionNonReceipt(BaseModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "declared_scope_manifest_unresolved",
        "declared_scope_component_denominator_mismatch",
        "open_world_vector_persistence_failed",
    ]
    requested_query_context_ref: Digest

class PromotionDeclaredScopeManifestProvider(Protocol):
    def resolve_complete_manifest(
        self, *, member: PersistedBoundPromotionCandidateContext,
    ) -> DeclaredScopeManifest | OpenWorldRiskProductionNonReceipt: ...

class OpenWorldRiskVectorArtifactRepository(OpenWorldRiskArtifactResolver):
    def __init__(self, *, store: ArtifactStore) -> None: ...

    def persist_and_verify(
        self, *, vector: OpenWorldRiskVector,
        declared_manifest: DeclaredScopeManifest,
        lifecycle_role_denominator_ref: Digest,
        verifier_provenance_ref: ArtifactRef,
        requested_query_context_ref: Digest,
    ) -> PersistedOpenWorldRiskVector | OpenWorldRiskProductionNonReceipt: ...

    def resolve_verified(
        self, *, vector_artifact_ref: ArtifactRef,
        expected_raw_cas_hash: Digest, expected_semantic_hash: Digest,
        requested_query_context_ref: Digest,
        expected_aggregate_context_ref: ArtifactRef,
        expected_bound_member_ref: ArtifactRef,
        expected_candidate_occurrence_ref: ArtifactRef,
        expected_verifier_provenance_ref: ArtifactRef,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt: ...

class OpenWorldRiskVectorProducer:
    def __init__(
        self, *, owner_contexts: PromotionOwnerQueryContextRepository,
        manifests: PromotionDeclaredScopeManifestProvider,
        lifecycle_owner: DeploymentLifecycleQueryOwner,
        evidence_verifier: CompetentDeploymentScopeEvidenceVerifier,
        artifacts: OpenWorldRiskVectorArtifactRepository,
        verifier_provenance_ref: ArtifactRef,
    ) -> None: ...

    def produce_for_candidate(
        self, *, bound_member_ref: ArtifactRef,
    ) -> PersistedOpenWorldRiskVector | OpenWorldRiskProductionNonReceipt: ...

class OpenWorldRiskPromotionAuthority:
    def __init__(
        self, *, producer: OpenWorldRiskVectorProducer,
        resolver: OpenWorldRiskArtifactResolver,
    ) -> None: ...

    def prepare_verified_projection(
        self, *, bound_member_ref: ArtifactRef,
    ) -> VerifiedOpenWorldRiskVector | OpenWorldRiskResolutionNonReceipt \
        | OpenWorldRiskProductionNonReceipt: ...
```

`open_world_risk.py` supplies the missing producer and persistence chain.
`PromotionDeclaredScopeManifestProvider` derives the complete declared
component denominator only after reloading the bound member, aggregate,
occurrence and its design problem/candidate summary; it neither accepts a caller
component list nor treats an unknown component as empty.
`OpenWorldRiskVectorProducer` resolves every denominator
row through the lifecycle owner and competent-evidence verifier, runs the pure
reducer, and persists canonical vector bytes with fixed kind/schema/CanonSpec,
declared-component and lifecycle-role denominator refs and verifier provenance.
`OpenWorldRiskVectorArtifactRepository` reloads the exact manifest and bytes,
recomputes raw and semantic hashes, rejects first-writer metadata/lineage drift,
and is the concrete implementation of the independent read port. Missing
institutional owner/evidence is a valid **negative input** to the reducer: the
container-installed `NoDeploymentLifecycleOwner` produces a content-bound
`not_established` component row for every declared component, and that vector
is still persisted and independently replayed. It never becomes a positive
deployment-scope claim. The competent positive evidence producer remains
`producer_missing` and the institutional owner `absent/unallocated`.

Every vector `verifier_provenance_ref` and
`expected_verifier_provenance_ref` is exactly `ArtifactRef`; no digest-string
overload or conversion exists. `OpenWorldRiskPromotionAuthority` passes the ref
returned by `PersistedOpenWorldRiskVector`; neither N9 nor a caller supplies
it. The repository reloads that provenance artifact and requires exact kind,
media type, bytes and owner lineage. The same ref is carried through production
result, canonical input, owner projection, receipt and replay. Protocol
conformance assigns the concrete repository to `OpenWorldRiskArtifactResolver`;
a raw digest, right ID under wrong artifact kind, or matching-looking different
provenance artifact is rejected.

The no-argument runtime composition root installs one
`PromotionOwnerQueryContextAuthority`, one
`OpenWorldRiskPromotionAuthority` with the concrete producer and an
independently constructed read resolver. After the generation loop and before
the first promotion-input build it freezes and persists every occurrence plus
one complete denominator, then persists one aggregate owner query context and
its sealed bound-member handles. Before every candidate input it
re-resolves that aggregate and bound member, proves the candidate's unique ordered member row,
then produces, persists, reloads and verifies one vector from that exact
aggregate/member pair;
failure to persist the context or to produce a
negative or positive artifact freezes N9. Thus `not_established` has a real
producer/artifact/bridge while a positive competent-evidence chain retains its
exact incomplete labels.

Wire the vector and the shared owner-query-context ref into the canonical N9 owner, not caller
`PromotionContextProvider`: inject
`OpenWorldRiskPromotionAuthority.prepare_verified_projection(bound_member_ref=...)` into
`CanonicalN9PromotionPort`, add a content-bound `OpenWorldRiskPromotionGate` to
the gate hash/refusal/trace/receipt, and thread it through generation,
recursive generation and the control service. The replay contract is explicit:
`CanonicalPromotionInput` carries the aggregate owner-query-context ref/hash,
candidate member-context ref/hash, vector artifact ref, raw-CAS hash, semantic
vector hash, requested aggregate-query-context ref and verifier-provenance ref;
`CanonicalPromotionOwnerProjection` carries the same content-bound projection;
and the receipt semantic projection plus gate hash commits them. Inject the
same owner-configured read-only `OpenWorldRiskArtifactResolver` into the live
port, standalone receipt verifier, offline replay wrapper and decision-front
consumer; DTO fields never act as a resolver. Extend
`_owner_projection_from_input`, `_input_from_owner_projection`,
`_validate_promotion_receipt_with_bound_session` and
`_promotion_receipt_allows_decision_front` so offline replay resolves the
artifact, recomputes both hashes and verifier provenance, and reconstructs the
decision solely from the bound owner projection. A receipt-shaped gate field is
never trusted and a missing projection cannot be silently dropped.

Do not add an obligation enum; the existing `_compile_obligations` denominator
stays exact. An absent provider or `not_established` vector freezes promotion.
Public output exposes only the limitation code/status/vector ref, never raw
evidence or a numeric delta.

Required nodes include `test_recipe_binding_cannot_project_execution`,
`test_owner_dispositions_preserve_mixed_append_only_history`,
`test_novel_or_missing_scope_component_is_not_established`,
`test_supplied_low_false_cannot_override_vector`,
`test_no_owner_still_persists_one_not_established_row_per_declared_component`,
`test_every_promotion_input_is_preceded_by_produce_persist_and_fresh_resolve`,
`test_arbitrary_vector_bytes_or_first_writer_lineage_cannot_enter_n9`,
`test_open_world_vector_persists_and_round_trips`,
`test_canonical_promotion_freezes_on_open_world_risk`,
`test_canonical_promotion_freezes_on_scope_not_established`,
`test_promotion_context_cannot_supply_open_world_gate`, and
`test_public_export_carries_scope_limitation_without_numeric_risk`,
`test_owner_projection_round_trips_exact_open_world_vector_identity`,
`test_offline_replay_recomputes_open_world_vector_and_verifier_provenance`,
`test_fresh_process_replay_rejects_deleted_or_mutated_open_world_vector`,
`test_remove_vector_keep_gate_markers_fails_replay`, and
`test_decision_front_rejects_unbound_open_world_receipt`.
`test_owner_context_varies_while_problem_and_candidate_bytes_stay_fixed`,
`test_wrong_kind_or_mutated_promotion_owner_context_rejects`, and
`test_direct_recursive_http_and_replay_share_one_owner_context_ref`,
`test_owner_context_rejects_dropped_duplicate_reordered_or_cross_promotion_member`,
`test_owner_context_is_derived_from_canonical_candidate_denominator`, and
`test_authentic_member_context_under_another_aggregate_freezes_n9`.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/runtime/quality/test_epoch_validity_cascade.py \
  tests/unit/runtime/quality/test_open_world_risk.py \
  tests/unit/runtime/quality/test_acquisition_executor.py \
  tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py \
  tests/unit/runtime/quality/test_promotion_sequence.py \
  tests/unit/runtime/quality/test_generation_cycle.py \
  tests/unit/runtime/quality/test_public_export.py \
  tests/unit/runtime/http/test_control_service_di.py
```

### Task 4.4 — close GY-DEF23 through a non-bypassable owner intake

**Add:**

- `tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py`

**Modify:**

- `src/polisyos/core/contracts/decision_validity.py`
- `src/polisyos/core/contracts/control.py`
- `src/polisyos/scientist/validation/decision_validity.py`
- `src/polisyos/runtime/http/container.py`
- `src/polisyos/runtime/http/routes/control.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/control/generation_cycle.py`
- `src/polisyos/runtime/http/services/run_index.py`
- `src/polisyos/runtime/quality/generation_cycle.py`
- `src/polisyos/runtime/quality/promotion_sequence.py`
- `src/polisyos/runtime/quality/recursive_generation_cycle.py`
- `src/polisyos/core/contracts/README.md`
- `src/polisyos/scientist/validation/README.md`
- `src/polisyos/runtime/http/README.md`
- `src/polisyos/runtime/http/routes/README.md`
- `src/polisyos/runtime/http/services/README.md`
- `docs/reference/public-surface.md`
- `tests/unit/scientist/validation/test_decision_validity_service.py`
- `tests/unit/runtime/http/test_decision_validity_api.py`
- `tests/unit/runtime/http/test_runtime_api_authz.py`
- `tests/unit/runtime/http/test_runtime_step_up_authz.py`
- `tests/unit/runtime/http/test_runs_api.py`
- `tests/unit/runtime/quality/test_generation_cycle.py`
- `tests/unit/runtime/quality/test_promotion_sequence.py`
- `tests/unit/runtime/http/test_control_service_di.py`

Add strict `EpochTransitionVerificationReceipt`, `EpochValidityBatchTarget`,
`EpochValidityPendingBatch` and `EpochValidityBatchReceipt`. The only HTTP
request fields are `transition_artifact_ref` and
`requested_query_context_ref`; the response returns batch/state/transition,
completion receipt, affected packet refs and claim-bridge result refs. It has no
status, reason, dependency keys, dedupe or verifier fields.

```python
class EpochTransitionVerifier(Protocol):
    def verify(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: Digest,
        expected_authority_purpose: str,
    ) -> EpochTransitionVerificationReceipt: ...

class DecisionValidityService:
    def admit_epoch_validity_batch(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: Digest,
    ) -> EpochValidityBatchReceipt: ...

class PreN9EpochValiditySubjectStatement(BaseModel):
    owner_query_context_ref: ArtifactRef
    owner_query_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    decision_packet_lineage_key_ref: Digest
    current_decision_packet_ref: ArtifactRef | None
    packet_epoch_refs: tuple[Digest, ...]

class PersistedPreN9EpochValiditySubject(BaseModel):
    subject_ref: ArtifactRef
    subject_content_hash: Digest

class PersistedEpochValidityGateEvidence(BaseModel):
    gate_evidence_ref: ArtifactRef
    gate_evidence_content_hash: Digest
    subject_ref: ArtifactRef
    subject_content_hash: Digest

class EpochValidityPreN9SubjectAuthority(Protocol):
    def persist_for_n9(
        self, *, bound_member_ref: ArtifactRef,
    ) -> PersistedPreN9EpochValiditySubject: ...

class ControlPlaneService:
    def reconcile_epoch_validity_for_subject(
        self,
        *,
        subject_ref: ArtifactRef,
    ) -> PersistedEpochValidityGateEvidence | EpochValidityGateNonReceipt: ...

class EpochValidityGateReceipt(BaseModel):
    status: Literal["current", "batch_completed", "pending", "not_established"]
    subject_ref: ArtifactRef
    subject_content_hash: Digest
    current_decision_packet_ref: ArtifactRef | None
    packet_epoch_refs: tuple[Digest, ...]
    current_epoch_head_refs: tuple[Digest, ...]
    dependency_denominator_ref: Digest
    adjudication_denominator_ref: Digest
    prior_completed_binding_ref: ArtifactRef | None
    completed_batch_receipt_ref: ArtifactRef | None
    requested_query_context_ref: Digest
    failure_codes: tuple[str, ...]

class EpochValidityAuthorityGate(Protocol):
    def reconcile_before_n9(
        self, *, subject_ref: ArtifactRef,
    ) -> PersistedEpochValidityGateEvidence | EpochValidityGateNonReceipt: ...

class PreN9AdmittedCandidate(BaseModel):
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    subject_ref: ArtifactRef
    subject_content_hash: Digest
    gate_evidence_ref: ArtifactRef
    gate_evidence_content_hash: Digest

class PersistedPreN9AdmittedCandidateBatch(BaseModel):
    aggregate_context_ref: ArtifactRef
    aggregate_context_content_hash: Digest
    candidate_denominator_ref: ArtifactRef
    candidate_denominator_content_hash: Digest
    ordered_admissions: tuple[PreN9AdmittedCandidate, ...]
    batch_content_hash: Digest

class EpochValidityN9Projection(BaseModel):
    owner_query_context_ref: ArtifactRef
    owner_query_context_content_hash: Digest
    bound_member_ref: ArtifactRef
    bound_member_content_hash: Digest
    candidate_occurrence_ref: ArtifactRef
    candidate_occurrence_content_hash: Digest
    subject_ref: ArtifactRef
    subject_content_hash: Digest
    gate_receipt_ref: ArtifactRef
    gate_receipt_content_hash: Digest
    requested_query_context_ref: Digest
    current_decision_packet_ref: ArtifactRef | None
    completed_batch_receipt_ref: ArtifactRef | None
    verifier_provenance_ref: ArtifactRef
    status: Literal["current", "batch_completed"]
    predicate_class: Literal["independently_reconciled"]

class EpochValidityN9EvidenceResolver(Protocol):
    def resolve_verified(
        self, *, admission: PreN9AdmittedCandidate,
        expected_design_problem_ref: ArtifactRef,
    ) -> EpochValidityN9Projection | EpochValidityGateNonReceipt: ...

class PromotionPort(Protocol):
    def __call__(
        self, *, admitted_batch: PersistedPreN9AdmittedCandidateBatch,
        problem: DesignProblem,
    ) -> PromotionPortObservation: ...
```

Inject the verifier at service construction through the runtime container and
`ControlPlaneService`, never through the request or method call. Add POST
`/api/v1/control/decision-validity/epoch-batches`, authorized only over the
artifact ref and query context. Resolve exact bytes/hash/signature/purpose/
query/verifier provenance, reconcile the complete target denominator from the
owner index, derive status/reason, and freeze every decisive P37 class.

The production pipeline uses an explicit completed-batch-to-candidate split. Inject
`PromotionOwnerQueryContextAuthority`,
`EpochValidityPreN9SubjectAuthority` and `EpochValidityAuthorityGate` into the
canonical core `GenerationCycleController`. After the generation loop closes,
the denominator owner persists every candidate occurrence and freezes the
complete batch. The context authority consumes that sealed denominator and
persists one aggregate plus one bound-member handle per occurrence. OWR
produces from the bound member; the subject authority then accepts only that
same bound member and persists canonical
`PreN9EpochValiditySubjectStatement` bytes. It resolves the member, aggregate and
derives the decision-packet lineage key, optional current packet and packet
epoch refs from owner indexes; none is a controller/caller field. This is
usable for the first decision where no prior packet exists. Only the persisted
subject ref crosses into the gate. The controller never parses subject/context
bytes or supplies query coordinates; the gate reloads both and persists one
gate-evidence artifact. Only the
aggregate/member/occurrence and subject/gate handles cross as
`PreN9AdmittedCandidate`; after every denominator member has exactly one
admission, the owner seals the ordered batch against that same aggregate and
denominator. Only the sealed batch enters the promotion port—no caller
sequence. `CanonicalN9PromotionPort` receives the owner-configured
`EpochValidityN9EvidenceResolver`, resolves every paired admission, checks
candidate/problem identity by reloading the occurrence (not a supplied
`CandidateSummary`) and builds `EpochValidityN9Projection`. Add that
projection to both `CanonicalPromotionInput` and
`CanonicalPromotionOwnerProjection`; the canonical receipt and gate hash bind
it together with the identical owner-query-context ref/hash used by OWR.
Missing, duplicate, reordered or mismatched candidate admission fails the
exact batch/complete-candidate-denominator bijection. The HTTP control service delegates to
that same controller; it is not the exclusive strangle. A missing subject
authority, missing gate or non-positive receipt freezes the core path, so a
direct non-HTTP invocation cannot bypass epoch validity.

The order is fixed: finish the loop; persist occurrences and freeze the complete
denominator; persist one aggregate and all bound members; for each bound member
produce OWR; persist the DV subject from that same member; reconcile the
gate; build N9 input; then bind the context ref/hash into owner projection,
receipt, decision-front check and offline replay. Every direct, recursive and
HTTP composition root uses that sequence. Holding problem/candidate bytes
fixed while substituting a second authentic context must change the receipt or
fail; missing/wrong-kind/mutated context freezes N9.

Subject and gate persistence use fixed kind/schema/CanonSpec and return only
content-bound refs/hashes; no parsed statement travels beside those handles.
The gate and N9 resolver reload, verify, strictly reparse and canonically
reserialize before using any field.

The constructor denominator is complete, not a direct-controller sample. An
AST plus runtime-container census covers `GenerationCycleController`,
`RecursiveGenerationCycle`, its default factory in
`recursive_generation_cycle.py`, the HTTP generation service and every
production constructor/call of `PromotionPort`/`CanonicalN9PromotionPort`.
Every row must receive the same container-owned subject authority, gate and N9
evidence resolver; optional/default `None`, test-double defaults and an
unwrapped N9 call are forbidden. Direct, recursive, HTTP, standalone receipt
verification and offline replay resolve the same gate evidence; DTO fields are
never trusted as the projection. Removing any dependency from the default recursive factory while
leaving the direct controller wired must fail the census and an end-to-end
non-HTTP recursive test.

`reconcile_epoch_validity_for_subject` implements the gate. It reloads and
content-verifies the subject and owner-query-context artifact, resolves the
optional current packet from its owner lineage and derives scope, authority
purpose, packet/candidate-bound epoch refs and sparse native coordinates from
those owner artifacts; invokes
`SemanticEpochService`; and independently resolves the complete dependency and
owner-adjudication denominators on **every** N9 attempt. It compares four owner
facts: subject/packet-bound epoch refs, current native head refs, both current
denominator refs, and the last completed binding for that subject lineage/query/
purpose. `current` is legal only when refs equal the current head, both
denominator refs equal those in the last completed binding, and no unresolved/
contested result exists. For an initial subject with no prior packet, a new
content-bound completed binding is required; absence never becomes current. It
is never inferred merely because the head did not move during this function
call.

Any old subject/current-head mismatch or changed dependency/adjudication
denominator invokes the appointed `EpochValidityTransitionProducer` (including
a same-epoch perturbation), stores the signed transition and passes only its ref
plus requested-query context to `admit_epoch_validity_batch`. The external
caller supplies neither subject, packet, epochs, targets, status nor
producer/verifier. A
content-bound no-transition/current receipt is therefore an exact replay of a
previously completed owner binding, not a shortcut. Generation/N9 cannot
proceed while this call is a non-receipt or pending batch. This closes the
producer-orchestration link rather than leaving the new HTTP intake waiting for
an imaginary caller.

The generic caller-controlled event route remains for non-epoch dependencies,
but it cannot admit, complete or clear an epoch batch. Its owner index stores
`DecisionDependencyKind.SEMANTIC_EPOCH`; any generic request targeting such an
owner-known dependency fails regardless of string prefix. An ACTIVE generic
event cannot clear a pending freeze.

Before any packet mutation persist one atomic complete-target pending batch.
Every owner read composes that pending limitation orthogonally with the terminal
status—withdrawn/revoked/stale remain terminal, but none becomes current. Apply
idempotent transitions, persist completion, then clear pending. A crash after
phase one or mid-batch leaves every target non-current; resume uses the frozen
denominator. Verification failure writes no state. Exact failure codes include
`verifier_not_configured`, `ref_unresolved`, `content_hash_mismatch`,
`signature_unverified`, `authority_purpose_mismatch`,
`query_context_mismatch`, `dependency_denominator_unresolved`,
`target_denominator_mismatch` and `batch_pending`.

`RunIndexService` is an owner read and therefore part of the strangle. Add the
Decision Validity repository generation/ref to its cache identity (or overlay
the repository's current projection on every read); the run-directory
fingerprint alone is forbidden because a validity batch does not change it.
Cached `/runs` and detail responses after phase-one persistence, after a
mid-batch process crash and after restart must all expose the pending freeze
while preserving any stronger terminal status. No cached `ACTIVE` value can
outlive a Decision Validity generation change.

Required nodes include
`test_epoch_batch_request_has_no_status_reason_dependency_keys_or_verifier`,
`test_generic_event_endpoint_cannot_admit_or_clear_epoch_batch`,
`test_epoch_batch_rejects_fake_verifier_provenance_without_state`,
`test_epoch_batch_reconciles_complete_dependency_denominator`,
`test_epoch_batch_omitted_target_fails_closed`,
`test_epoch_batch_persists_complete_pending_freeze_before_first_packet_write`,
`test_epoch_batch_crash_mid_batch_keeps_all_targets_non_current`,
`test_epoch_batch_pending_preserves_withdrawn_or_revoked_terminal`, and
`test_epoch_batch_resume_is_idempotent`,
`test_run_index_generation_invalidates_cached_active_status`, and
`test_runs_api_crash_restart_keeps_complete_pending_denominator_non_current`,
`test_generation_control_derives_and_admits_signed_epoch_transition`, and
`test_generation_control_caller_cannot_supply_epoch_targets_or_status`,
`test_core_generation_controller_cannot_bypass_epoch_gate`,
`test_default_recursive_generation_factory_binds_subject_authority_and_gate`,
`test_http_and_direct_recursive_paths_share_the_pre_n9_subject_strangle`,
`test_first_decision_uses_candidate_subject_without_fabricated_prior_packet`,
`test_post_n9_packet_binds_exact_subject_and_gate_receipt`,
`test_gate_derives_query_context_from_owner_context_not_controller`,
`test_owr_and_epoch_gate_bind_identical_owner_context_ref`,
`test_missing_or_mutated_owner_context_freezes_n9`,
`test_canonical_n9_resolves_sealed_epoch_gate_evidence`,
`test_offline_replay_rejects_missing_or_mutated_epoch_gate_evidence`,
`test_old_packet_after_prior_head_advance_requires_validity_batch`,
`test_unchanged_epoch_with_new_owner_adjudication_requires_batch`, and
`test_current_receipt_requires_matching_prior_completed_denominators`;
route authz and step-up tests exercise the typed path.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/scientist/validation/test_decision_validity_service.py \
  tests/unit/runtime/http/test_decision_validity_api.py \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_runtime_step_up_authz.py \
  tests/unit/runtime/http/test_runs_api.py \
  tests/unit/runtime/http/test_control_service_di.py \
  tests/unit/runtime/quality/test_promotion_sequence.py \
  tests/unit/runtime/quality/test_generation_cycle.py \
  tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py
```

### Task 4.5 — orchestrate GY-GAP8 and fail public claims closed

**Add:**

- `architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json`
- `src/polisyos/scientist/evidence/claims/head_index.py`
- `tests/unit/scientist/evidence/claims/test_head_index.py`
- `tests/repo_quality/test_claim_ledger_export_callers.py`

**Modify:**

- `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py`
- `src/polisyos/scientist/evidence/claims/__init__.py`
- `src/polisyos/scientist/evidence/claims/export.py`
- `src/polisyos/scientist/evidence/claims/audit.py`
- `src/polisyos/scientist/evidence/claims/ledger.py`
- `src/polisyos/scientist/evidence/claims/models.py`
- `src/polisyos/scientist/methods/causal/validity.py`
- `src/polisyos/scientist/nodes/builtins/governance/run_governance.py`
- `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`
- `src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`
- `src/polisyos/scientist/nodes/builtins/decide/decision_packet/builder.py`
- `src/polisyos/scientist/policy_design/output.py`
- `src/polisyos/scientist/orchestration/engine/context.py`
- `src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py`
- `src/polisyos/scientist/orchestration/workflows/builder.py`
- `src/polisyos/scientist/methods/backtesting/composition_bridge.py`
- `src/polisyos/scientist/publishing/publisher.py`
- `src/polisyos/runtime/http/container.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/quality/workspace/loop.py`
- `src/polisyos/runtime/quality/projection_semantics.py`
- `src/polisyos/runtime/quality/status_deficits.py`
- `src/polisyos/scientist/governance/README.md`
- `src/polisyos/scientist/evidence/README.md`
- `src/polisyos/scientist/publishing/README.md`
- `docs/reference/public-surface.md`
- `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py`
- `tests/unit/scientist/evidence/claims/test_export.py`
- `tests/unit/scientist/evidence/claims/test_audit.py`
- `tests/unit/scientist/evidence/claims/test_ledger.py`
- `tests/unit/scientist/methods/causal/test_causal_validity.py`
- `tests/unit/scientist/nodes/builtins/governance/test_run_governance_claims.py`
- `tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py`
- `tests/unit/scientist/nodes/test_decision_packet_node_v3.py`
- `tests/unit/scientist/policy_design/test_phase_b_output.py`
- `tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py`
- `tests/unit/scientist/orchestration/workflows/test_builder_pinning.py`
- `tests/unit/scientist/methods/backtesting/test_composition_bridge.py`
- `tests/unit/runtime/quality/test_workspace_loop.py`
- `tests/unit/scientist/policy_design/test_baseline_compiler.py`
- `tests/unit/scientist/policy_design/test_claim_decomposition.py`
- `tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py`
- `tests/unit/runtime/http/test_decision_validity_api.py`
- `tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py`
- `tests/unit/runtime/quality/test_status_deficits.py`
- `tests/unit/runtime/http/test_control_service_di.py`
- `tools/ci/check_scientist_best_in_class_phase2_1.py`
- `tools/ci/check_scientist_best_in_class_wave2.py`

Add the only authority-bearing bridge service. Its public method accepts refs
and query coordinates only; the pure reducer is private:

```python
class CompletedEpochValidityBatchEvidence(BaseModel):
    batch_receipt_ref: ArtifactRef
    batch_receipt_content_hash: Digest
    receipt_bytes: bytes
    verifier_provenance_ref: ArtifactRef
    requested_query_context_ref: Digest

@dataclass(frozen=True, slots=True)
class _VerifiedCompletedEpochValidityBatch:
    evidence: CompletedEpochValidityBatchEvidence
    parsed_receipt: EpochValidityBatchReceipt

class DecisionValidityCompletedBatchResolver:
    def __init__(
        self, *, repository: DecisionValidityRepository,
        artifacts: ArtifactStore,
        verifier: CompletedBatchReceiptVerifier,
    ) -> None: ...

    def resolve_completed(
        self, *, batch_receipt_ref: ArtifactRef,
        decision_packet_ref: ArtifactRef,
        requested_query_context_ref: Digest,
    ) -> _VerifiedCompletedEpochValidityBatch \
        | EpochValidityBatchResolutionNonReceipt: ...

class ClaimLedgerOwnerKey(BaseModel):
    scope_ref: Digest
    claim_owner_ref: str
    authority_purpose: str

class PreparedClaimLedgerInitialization(BaseModel):
    preparation_ref: ArtifactRef
    preparation_content_hash: Digest
    owner_key: ClaimLedgerOwnerKey
    initial_ledger_ref: ArtifactRef
    initial_ledger_content_hash: Digest

class ClaimLedgerRootBasisStatement(BaseModel):
    owner_key: ClaimLedgerOwnerKey
    preparation_ref: ArtifactRef
    preparation_content_hash: Digest
    decision_packet_ref: ArtifactRef
    decision_packet_content_hash: Digest
    initial_ledger_ref: ArtifactRef
    initial_ledger_content_hash: Digest
    denominator_receipt_ref: ArtifactRef
    denominator_receipt_content_hash: Digest

class ClaimLedgerRootStatement(BaseModel):
    schema_version: Literal["polisyos.claim-ledger.root.v1"]
    root_identity: Digest
    basis_ref: ArtifactRef
    basis_content_hash: Digest
    issuance_evidence_ref: ArtifactRef
    issuance_evidence_content_hash: Digest
    issuance_verifier_provenance_ref: ArtifactRef

class PersistedClaimLedgerRoot(BaseModel):
    root_receipt_ref: ArtifactRef
    root_receipt_content_hash: Digest
    statement: ClaimLedgerRootStatement

class VerifiedClaimLedgerIssuance(BaseModel):
    root: PersistedClaimLedgerRoot
    verifier_receipt_ref: ArtifactRef
    verifier_receipt_content_hash: Digest
    predicate_class: Literal["independently_reconciled"]

class ClaimLedgerRootVerificationReceipt(BaseModel):
    root_ref: ArtifactRef
    root_content_hash: Digest
    verifier_provenance_ref: ArtifactRef
    disposition: Literal["verified"]

class ClaimLedgerIssuanceNonReceipt(BaseModel):
    status: Literal["not_established", "rejected"]
    code: Literal[
        "claim_root_issuance_not_established",
        "claim_root_issuance_content_mismatch",
        "claim_root_denominator_mismatch",
        "claim_root_provenance_untrusted",
    ]

class ClaimLedgerIssuanceVerifier(Protocol):
    def verify_exact(
        self, *, root_receipt_ref: ArtifactRef,
        expected_owner_key: ClaimLedgerOwnerKey | None = None,
    ) -> VerifiedClaimLedgerIssuance | ClaimLedgerIssuanceNonReceipt: ...

class ClaimLedgerHeadStatement(BaseModel):
    schema_version: Literal["polisyos.claim-ledger.head.v1"]
    root_identity: Digest
    root_receipt_ref: ArtifactRef
    root_receipt_content_hash: Digest
    owner_key: ClaimLedgerOwnerKey
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest
    generation: int
    predecessor_head_ref: ArtifactRef | None
    bridge_result_refs: tuple[ArtifactRef, ...]
    issuance_verifier_receipt_ref: ArtifactRef
    issuance_verifier_receipt_content_hash: Digest

class PersistedClaimLedgerHead(BaseModel):
    head_ref: ArtifactRef
    head_content_hash: Digest
    statement: ClaimLedgerHeadStatement

class ClaimLedgerHeadResolutionNonReceipt(BaseModel):
    result_kind: Literal["non_receipt"]
    status: Literal["not_established", "rejected"]
    code: Literal[
        "claim_head_absent", "claim_head_issuance_unverified",
        "claim_head_content_mismatch", "claim_head_conflict",
    ]

class ClaimLedgerHeadAdvanced(BaseModel):
    result_kind: Literal["advanced"]
    owner_key: ClaimLedgerOwnerKey
    root_identity: Digest
    prior_head_ref: ArtifactRef | None
    new_head: PersistedClaimLedgerHead
    durable_pointer_content_hash: Digest
    readback_receipt_ref: ArtifactRef

class ClaimLedgerHeadAdvanceConflict(BaseModel):
    result_kind: Literal["conflict"]
    owner_key: ClaimLedgerOwnerKey
    expected_head_ref: ArtifactRef | None
    observed_head_ref: ArtifactRef | None

ClaimLedgerHeadAdvanceReceipt = Annotated[
    ClaimLedgerHeadAdvanced | ClaimLedgerHeadAdvanceConflict
    | ClaimLedgerHeadResolutionNonReceipt,
    Field(discriminator="result_kind"),
]

class ClaimLedgerRootAssessment(BaseModel):
    decision_packet_ref: ArtifactRef | None
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest
    root_identity: Digest | None
    root_receipt_ref: ArtifactRef | None
    root_receipt_content_hash: Digest | None
    root_issuance_evidence_ref: ArtifactRef | None
    owner_key: ClaimLedgerOwnerKey | None
    disposition: Literal[
        "registered", "migration_required", "not_established",
    ]
    failure_code: str | None

class ClaimLedgerRootDenominatorReceipt(BaseModel):
    owner_snapshot_ref: ArtifactRef
    owner_snapshot_content_hash: Digest
    independent_walk_content_hash: Digest
    owner_snapshot_row_count: int = Field(ge=0)
    independent_walk_row_count: int = Field(ge=0)
    declared_root_count: int
    assessments: tuple[ClaimLedgerRootAssessment, ...]
    denominator_hash: Digest
    predicate_class: Literal["independently_reconciled"]

class ClaimLedgerRootInventory(Protocol):
    def resolve_complete_roots(
        self,
    ) -> ClaimLedgerRootDenominatorReceipt: ...

class DecisionPacketRootRow(BaseModel):
    decision_packet_ref: ArtifactRef | None
    decision_packet_content_hash: Digest | None
    ledger_artifact_ref: ArtifactRef
    ledger_raw_cas_hash: Digest

class DecisionPacketRootSnapshot(BaseModel):
    snapshot_ref: ArtifactRef
    snapshot_content_hash: Digest
    row_count: int = Field(ge=0)
    ordered_rows: tuple[DecisionPacketRootRow, ...]
    verifier_provenance_ref: ArtifactRef

class DecisionPacketRootRepository(Protocol):
    def resolve_owner_snapshot(self) -> DecisionPacketRootSnapshot: ...

class ArtifactStoreClaimRootWalk(Protocol):
    def enumerate_independently(
        self,
    ) -> tuple[DecisionPacketRootRow, ...]: ...

class ClaimLedgerIssuanceEvidenceIndex(Protocol):
    def resolve_for_ledger(
        self, *, ledger_artifact_ref: ArtifactRef,
    ) -> ArtifactRef | ClaimLedgerHeadResolutionNonReceipt: ...

class RepositoryClaimLedgerRootInventory(ClaimLedgerRootInventory):
    def __init__(
        self, *, decision_packets: DecisionPacketRootRepository,
        independent_walk: ArtifactStoreClaimRootWalk,
        artifacts: ArtifactStore,
        issuance_evidence: ClaimLedgerIssuanceEvidenceIndex,
    ) -> None: ...

class ClaimLedgerOwnerPort(Protocol):
    def prepare_initial_ledger(
        self, *, base_claims_ref: ArtifactRef,
        source_artifact_refs: tuple[ArtifactRef, ...],
        initialization_policy_ref: ArtifactRef,
    ) -> PreparedClaimLedgerInitialization | ClaimLedgerIssuanceNonReceipt: ...

    def finalize_initial_root(
        self, *, preparation_ref: ArtifactRef,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt | ClaimLedgerIssuanceNonReceipt: ...

    def resolve_current(
        self, *, owner_key: ClaimLedgerOwnerKey,
    ) -> PersistedClaimLedgerHead | ClaimLedgerHeadResolutionNonReceipt: ...

    def advance_verified_batch(
        self, *, verified_batch: _VerifiedCompletedEpochValidityBatch,
        decision_packet_ref: ArtifactRef,
    ) -> ClaimLifecycleBridgeAuthorityResult: ...

    def append_verified_owner_event(
        self, *, owner_key: ClaimLedgerOwnerKey,
        owner_event_ref: ArtifactRef,
    ) -> ClaimLedgerHeadAdvanceReceipt: ...

    def export_current(
        self, *, owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerExport: ...

    def migrate_legacy_roots(
        self,
    ) -> tuple[
        ClaimLedgerHeadAdvanceReceipt | ClaimLedgerHeadResolutionNonReceipt,
        ...,
    ]: ...

@dataclass(frozen=True, kw_only=True)
class ClaimCapableExecutionContext(ExecutionContext):
    claim_ledger_owner: ClaimLedgerOwnerPort

class EpochClaimLifecycleBridgeService:
    def __init__(
        self, *, completed_batches: DecisionValidityCompletedBatchResolver,
        claim_owner: ClaimLedgerOwnerPort,
    ) -> None: ...

    def bridge_completed_batch(
        self, *, batch_receipt_ref: ArtifactRef,
        decision_packet_ref: ArtifactRef,
        requested_query_context_ref: Digest,
    ) -> ClaimLifecycleBridgeAuthorityResult: ...

def _apply_verified_epoch_batch_to_claim_lifecycle(
    *, ledger: AppendOnlyClaimLedger,
    verified_batch: _VerifiedCompletedEpochValidityBatch,
    target: EpochValidityBatchTarget,
    dependency_denominator: ClaimDependencyDenominatorReceipt,
    actor_id: Literal["decision_validity_epoch_bridge"],
) -> LifecycleBridgeResult: ...

class ClaimLedgerExportService:
    def __init__(
        self, *, claim_owner: ClaimLedgerOwnerPort,
    ) -> None: ...

    def export(
        self, *, owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerExport: ...

def _format_resolved_claim_ledger(
    *, ledger: AppendOnlyClaimLedger, audience: ClaimExportAudience,
    pending_projection: ClaimBridgePendingProjection,
) -> ClaimLedgerExport: ...
```

`DecisionValidityCompletedBatchResolver` loads exact persisted receipt bytes,
recomputes content/signature/verifier provenance and rejects non-completed,
wrong-target/query/purpose batches. A shaped `EpochValidityBatchReceipt` plus a
matching-looking ref is not an input to the service. After the Decision
Validity batch completes, the control service supplies only its persisted ref,
packet ref and query coordinate. The bridge service loads the packet itself,
resolves its initial `claim_ledger_v2_ref`/`claims_ref` only to derive the Claim
Ledger owner key, then passes the verified batch and packet ref to the one
container-owned `ClaimLedgerOwnerPort`. The owner resolves the current head,
root receipt, issuance-verifier receipt and ledger itself. The private reducer
receives only those sealed values.

Initial root issuance is one owner-controlled two-phase transaction. First,
enrichment calls `prepare_initial_ledger`: the owner derives and persists an
unadvertised immutable ledger plus preparation statement and returns only that
sealed preparation handle. Enrichment places its ledger ref in the packet;
`decision_packet/builder.py` persists the packet. Only then does the same owner
call `finalize_initial_root`, reload both bytes, prove the packet binds that
exact prepared ledger, reconcile the prospective row against the owner snapshot
and independent ArtifactStore walk, persist a separate
`ClaimLedgerRootBasisStatement`, issue/verify the root, create the generation-0
head, and register packet-to-root. Failure exposes neither packet nor ledger as
current; unreferenced immutable CAS bytes carry no authority.

Root issuance is explicit and non-self-referential. The Claim owner producer
constructs canonical `ClaimLedgerRootStatement` bytes only from the verified
basis and owner issuance evidence. `root_identity` is the domain-separated hash
of the exact basis projection; it never contains a current ledger or head. Root artifacts have fixed kind
`scientist.claims.ledger_root`, schema `polisyos.claim-ledger.root.v1`, media
type and raw-mapping CanonSpec. `ClaimLedgerIssuanceVerifier` independently
reloads root, packet, ledger, denominator, issuance evidence and verifier-
provenance bytes and returns the only positive receipt. A shaped root statement
or valid CAS blob under the wrong kind/schema/provenance is rejected.

Every `ClaimLedgerHeadStatement` binds that immutable root identity, exact root
receipt/hash and issuance-verifier receipt/hash in addition to owner key,
current ledger, predecessor, bridge results and generation. Head artifacts use
fixed kind `scientist.claims.ledger_head` and schema
`polisyos.claim-ledger.head.v1`. Resolve-current always reloads and verifies the
root and issuance receipts, fixed manifest profile and immutable root identity;
an advance cannot change any root field. Initial statements require generation
zero and no predecessor; advances require prior generation + 1 and the exact
verified predecessor. The head ref stays outside its statement preimage.

One exhaustive `C4_PERSISTED_PROFILE_SPECS` registry freezes every new
persisted statement before implementation. Each row fixes kind, schema, media
type `application/octet-stream`, semantic prefix, exact raw-mapping field list,
self-field exclusions and the one common CanonSpec:
`polisyos.canon.json@0.2.0`, `forbid_floats=True`,
`forbid_nan_inf=True`, `exclude_none=False`, `max_depth=128`,
`sort_keys=True`, separators `(',', ':')`, `ensure_ascii=False`. The rows are:

| record | kind | schema | semantic prefix |
| --- | --- | --- | --- |
| candidate occurrence | `runtime.promotion.candidate_occurrence` | `polisyos.promotion.candidate-occurrence.v1` | `polisyos.promotion.candidate-occurrence.v1\0` |
| candidate denominator | `runtime.promotion.candidate_denominator` | `polisyos.promotion.candidate-denominator.v1` | `polisyos.promotion.candidate-denominator.v1\0` |
| epoch query evidence | `runtime.promotion.semantic_epoch_query` | `polisyos.promotion.semantic-epoch-query.v1` | `polisyos.promotion-query.semantic-epoch.v1\0` |
| deployment query evidence | `runtime.promotion.deployment_scope_query` | `polisyos.promotion.deployment-scope-query.v1` | `polisyos.promotion-query.deployment-scope.v1\0` |
| member context | `runtime.promotion.candidate_context_member` | `polisyos.promotion.candidate-context-member.v1` | `polisyos.promotion-candidate-context-member.v1\0` |
| aggregate context | `runtime.promotion.owner_query_context` | `polisyos.promotion.owner-query-context.v2` | `polisyos.promotion-owner-query-context.v2\0` |
| bound member | `runtime.promotion.bound_candidate_context` | `polisyos.promotion.bound-candidate-context.v1` | `polisyos.promotion-bound-candidate-context.v1\0` |
| Claim preparation | `scientist.claims.ledger_preparation` | `polisyos.claim-ledger.preparation.v1` | `polisyos.claim-ledger-preparation.v1\0` |
| Claim root basis | `scientist.claims.ledger_root_basis` | `polisyos.claim-ledger.root-basis.v1` | `polisyos.claim-ledger-root-basis.v1\0` |
| Claim root | `scientist.claims.ledger_root` | `polisyos.claim-ledger.root.v1` | `polisyos.claim-ledger-root-root.v1\0` |
| root verification | `scientist.claims.ledger_root_verification` | `polisyos.claim-ledger.root-verification.v1` | `polisyos.claim-ledger-root-verification.v1\0` |
| Claim head | `scientist.claims.ledger_head` | `polisyos.claim-ledger.head.v1` | `polisyos.claim-ledger-head-statement.v1\0` |
| head readback | `scientist.claims.ledger_head_readback` | `polisyos.claim-ledger.head-readback.v1` | `polisyos.claim-ledger-head-readback.v1\0` |

Every semantic digest is `sha256(prefix || uint64_be(len(C(mapping))) ||
C(mapping))`; the persisted wrapper's ref/hash is never in its statement
preimage. The registry includes the exact root-identity projection—owner key,
preparation, packet, initial ledger and denominator identities in that order—
so two encoders cannot choose fields or ordering. Independent encoders that do
not import production projection helpers reproduce 0/1-candidate, initial-root
and one-advance golden vectors. Wrong kind/media/schema/CanonSpec, omitted or
extra field, same bytes under a sibling profile, and a changed self-exclusion
all fail.

`head_index.py` contains one private `_LockedClaimLedgerHeadCAS`; no exported
store exposes compare/create/advance. A fieldless module-local mutation permit
is available only to the concrete Claim owner. For each owner-key hash the CAS
opens one `O_CLOEXEC` lock file and takes an interprocess exclusive lock before
reading or comparing the pointer. Under that same lock it verifies the
expected head/root, writes and verifies immutable ledger/result/head CAS bytes,
writes the new pointer to a same-directory temporary file, fsyncs the file,
atomically replaces the pointer, fsyncs the parent directory, reloads the
pointer and all referenced bytes, and only then emits
`ClaimLedgerHeadAdvanced`. Every error releases the lock and returns a typed
non-receipt. Two distinct processes racing from one predecessor yield exactly
one `advanced` and one conflict; byte-identical initial registration/retry is
idempotent. Kill tests at prewrite, post-file-fsync, post-replace and post-dir-
fsync recover either the complete old or complete new pointer—never two heads
or a success without durable readback. Unreferenced immutable CAS bytes are
not current and are safe to collect later.

The root denominator is independently reconciled. The canonical packet/root
repository produces a content-bound owner snapshot with every root row,
count/order/hash and verifier provenance. A second adapter walks the complete
ArtifactStore manifest and packet-index denominator without consuming that
snapshot. `RepositoryClaimLedgerRootInventory` requires canonical unique order,
exact count and row-for-row equality, then emits one assessment for every row;
only that bijection earns `predicate_class="independently_reconciled"`.
Deleting a row from either walk, while retaining it in the other, fails.
`migrate_legacy_roots()` accepts no root list and may register only receipt
rows with verified issuance evidence; missing evidence is `not_established`
and freezes public output.

Ordinary `ExecutionContext` remains valid for non-Claim unit work. A frozen,
keyword-only `ClaimCapableExecutionContext(ExecutionContext)` adds one required,
non-optional `claim_ledger_owner` port. The workflow builder, activity worker,
workspace loop and backtesting bridge are the complete production constructor
denominator and all return this subtype with the same canonical port. Claim
producer/mutator/export entry points require that subtype or a narrow service
derived from it; a base context yields `claim_ledger_owner_not_established`.
The source/type-hint census requires zero production construction of the base
context while leaving the 116 unrelated test constructions valid. Positive
Claim tests explicitly construct the subtype. HTTP,
publisher, enrichment, audit, causal validity, governance, simulation and
policy-output code receive only that port or the narrow bridge/export services.
Canonical enrichment prepares the ledger, the packet builder persists it, and
the owner finalizes/registers the root before the packet or state is advertised.
Every subsequent append calls `advance_verified_batch` (or an
owner-internal append equivalent); every audience and decision-grade compiler
calls `export_current`. Raw ledger persistence/formatters are module-private,
and an AST/import/call census requires zero production calls outside
`head_index.py`. No PUBLIC caller can supply a ledger, ledger ref, store,
pending reader, issuance statement or expected head. Test doubles remain
confined to tests.

Affected-claim membership is data-owned, not hard-coded to six fields. The
strict dependency-field registry declares every current dependency-bearing
`ClaimRecord` path and its extraction rule: evidence, counterevidence,
uncertainty, provenance, facet, obligation, concept-spine, authority-profile,
baseline, alternative, comparison, reviewer and source-attribution refs, plus
nested method-precondition facet/obligation refs. The extractor generically
walks that complete registry, reconciles it against the model schema and emits
a content-bound denominator receipt. An unregistered model dependency field,
missing registered path, malformed nested path or target absent from the
receipt emits `claim_target_denominator_unresolved`—never an all-claims guess.
Adding a registry row whose model path already exists requires no bridge code.
The completed DV stale result remains intact. Raw `GovernanceMonitorEvent`
remains an advisory path and cannot establish epoch truth.

DV completion and Claim Ledger append are separate owner transactions, so the
control owner persists `claim_bridge_pending` over the exact completed-batch
target denominator before attempting the bridge. Decision/public reads compose
that limitation after DV completion: affected claims or an unresolved mapping
cannot appear current while the ledger head is old. Successful atomic head
advance records the bridge result and clears only its exact pending target.
Crash after DV completion or after CAS writes resumes from the same completed
batch and current ledger head. If dependency-field reconciliation is
`claim_target_denominator_unresolved`, no ledger transition is guessed and the
packet/public claim projection remains explicitly limited until an owner-grade
mapping arrives.

The private formatter used by `ClaimLedgerExportService` suppresses lifecycle stale for PUBLIC,
blocked, invalidated, superseded, review-required, withdrawn and revalidation
members; REVIEWER/MACHINE preserve history and limitations. Projection/status
helpers and `compile_decision_grade_export` consume the same current-head read,
so a sibling route cannot bypass pending or stale state.

The complete candidate-tree denominator is every call/export/import and every
`ExecutionContext(...)` construction across all nonignored `.py`/`.pyi` files.
One AST walk starts from definitions and follows aliases/imports; an independent
text/type walk begins at all tracked/untracked candidate files and classifies
every call. They reconcile the complete set rather than sharing a sampled root.
Every production caller is migrated to the container-owned port; tests/tools
either seed a verified head through that port or exercise the private formatter
locally. The old public ledger-taking persistence/export functions have zero
production call/import sites. The repository-quality test fails on a novel
caller, fake store injection, unregistered initial head, skipped legacy
migration or an `ExecutionContext` without the exact owner port. Its explicit
producer denominator includes audit, decision-packet enrichment, causal
validity, governance, causal simulation and policy output; its composition
denominator includes workflow builder, activity worker, workspace loop and
backtesting bridge. Every packet/root producer must appear in both the owner
snapshot and independent ArtifactStore walk.

The end-to-end API test seeds two claims, POSTs only transition ref/query,
asserts persisted receipt/ledger/bridge refs, then compares actual PUBLIC and
REVIEWER exports. Other required nodes are
`test_completed_epoch_batch_is_only_authority_input_to_claim_bridge`,
`test_fabricated_completed_batch_dto_and_matching_ref_cannot_bridge`,
`test_raw_detector_event_cannot_establish_epoch_claim_transition`,
`test_control_epoch_batch_resolves_ledger_from_packet_not_request`,
`test_partial_or_pending_epoch_batch_cannot_bridge_claims`,
`test_unmapped_dependency_emits_claim_target_denominator_unresolved`, and
`test_mixed_target_outcomes_stay_distinct_append_only`,
`test_two_sequential_batches_advance_one_claim_ledger_head_without_fork`,
`test_crash_after_cas_write_before_head_advance_keeps_old_head_current`,
`test_crash_after_dv_completion_keeps_claim_bridge_pending_public_freeze`,
`test_stale_caller_ledger_cannot_bypass_current_head_public_export`,
`test_public_export_api_accepts_owner_key_not_ledger_bytes_or_ref`,
`test_empty_store_first_batch_requires_verified_initial_head`,
`test_concurrent_initial_head_creation_accepts_only_identical_bytes`,
`test_two_distinct_process_advances_from_one_predecessor_yield_one_conflict`,
`test_kill_at_each_pointer_durability_boundary_recovers_one_complete_head`,
`test_head_statement_round_trips_without_prefilled_self_ref`,
`test_mutated_head_statement_under_old_pointer_fails`,
`test_head_advance_cannot_change_root_identity_or_issuance_verifier`,
`test_well_shaped_fake_root_issuance_cannot_be_registered_or_exported`,
`test_root_inventory_omission_fails_against_independent_owner_snapshot`,
`test_new_initial_producer_or_unenumerated_legacy_root_fails_denominator`,
`test_raw_claim_persistence_has_zero_production_callers_outside_authority`,
`test_all_execution_context_constructors_require_same_claim_owner_port`,
`test_fake_head_or_artifact_store_cannot_enter_export_method`,
`test_complete_old_export_caller_denominator_is_zero`,
`test_every_registered_claim_dependency_path_participates_in_denominator`, and
`test_novel_registered_dependency_path_requires_no_bridge_code`.

Direct task suite argv (run exactly as written):

```text
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py \
  tests/unit/scientist/evidence/claims/test_head_index.py \
  tests/unit/scientist/evidence/claims/test_audit.py \
  tests/unit/scientist/evidence/claims/test_ledger.py \
  tests/unit/scientist/evidence/claims/test_export.py \
  tests/unit/scientist/methods/causal/test_causal_validity.py \
  tests/unit/scientist/nodes/builtins/governance/test_run_governance_claims.py \
  tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py \
  tests/unit/scientist/nodes/test_decision_packet_node_v3.py \
  tests/unit/scientist/policy_design/test_phase_b_output.py \
  tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py \
  tests/unit/scientist/orchestration/workflows/test_builder_pinning.py \
  tests/unit/scientist/methods/backtesting/test_composition_bridge.py \
  tests/unit/runtime/quality/test_workspace_loop.py \
  tests/repo_quality/test_claim_ledger_export_callers.py \
  tests/unit/scientist/policy_design/test_baseline_compiler.py \
  tests/unit/scientist/policy_design/test_claim_decomposition.py \
  tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py \
  tests/unit/runtime/http/test_decision_validity_api.py \
  tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py \
  tests/unit/runtime/quality/test_status_deficits.py
"${GY_N12_RUN[@]}" -m pytest -q \
  tests/unit/runtime/http/test_control_service_di.py
```

### Task 4.6 — add behavioral validators and a guarded transition tool

**Add:**

- `tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py`
- `tools/quality/validation/execute_gy_n12_artifact_transition.py`
- `tests/repo_quality/tools/test_layer3_gy_epoch_chronology_contract.py`
- `tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py`

**Modify before source freeze:**

- `tools/quality/validation/check_layer3_gy_value_gate_contract.py`
- `tools/quality/validation/check_layer3_gy_second_domain_pack.py`

**Candidate targets, never edited in the source commit:**

- `architecture/generated_artifacts.toml`
- `docs/reference/generated-artifacts.md`

The validator imports and runs the real epoch resolver, full-prefix verifier,
Decision Validity typed path, Claim bridge and actual N9/public OpenWorldRisk
consumer. Its modes are `--check`, `--rederive-audit`,
`--source-flip-mutations`, `--corrupt-field-drift-check` and
`--output-format json`. Every mode emits a top-level semantic status; normalize
N8's rederive and corrupt modes to the same rule while preserving their
documented process statuses. Source flips keep markers while removing the real
resolution, prefix check, pending freeze, bridge call or N9 gate.

N8 gains `--candidate-reissue-catalog-provenance PATH`; N10a gains
`--candidate-dir DIR`; the epoch validator gains `--candidate-output PATH`.
The transition tool requires the exact N8 interpreter plus admitted environment
receipt and reconstructs the same sanitized N8 child environment; it rejects a
tooling-site path or distribution origin before invoking either N8 or N10a.
Each writes only to a declared scratch candidate and never its governed target.
The transition tool implements only `measure`, `build-deployment-candidates`,
`declare`, `apply` and `readback`. It imports the existing GY-DI1 owner's
`confidence_ledger._deployment_relative_paths` directly for this bounded
transition instead of minting a second 96-path owner. It snapshots the complete
protected denominator and implements the durable armed/final/fallback protocol
in Deployment Intersection below. Timing is lane procedure, not another
machine. For each complete suite expected or measured to exceed 60 seconds,
the journal declares a ceiling before launch from a prior comparable
measurement, records `/usr/bin/uptime` immediately before and after, and binds
the exact argv, runner, wall time and ordinary exit or signal. An ordinary
non-zero exit is a completed failure receipt; a killed or signalled run is a
non-receipt. No timing index, catalog mutation, admission state machine
or rerun around a failed receipt exists. Tests prove wrong branch/HEAD, changed
candidate, omitted protected path, intervening source/tool drift, kill after
the first replacement and readback mismatch never advertise a partial
governed state.

### Task 4.7 — freeze source, then execute one declared artifact transaction

After every source and validator review is clean, add the candidate output:

- `architecture/policy_design_case/layer3_gy_epoch_chronology_contract.json`

The registry/reference modifications from Task 4.6 and this payload form one
generated family. Do not write it directly. The guarded transition builds,
declares, applies and reads it back together with any changed N8/N10a or
deployment-bound candidates. A missing Foundry adjudication, production-data
manifest, declaration receipt, writer authority or clean source freeze yields
a typed non-receipt and omits the artifact commit.

**Commit boundaries:**

1. `feat(epochs): derive and bind fixed semantics to N13b` — Tasks 4.1–4.2
   form one atomic producer/signature/schema migration; no intermediate commit
   may expose a service without its first production caller or a required
   argument without every caller.
2. `feat(epochs): bind validity cascade and OpenWorldRisk to N9` — Task 4.3.
3. `feat(decision-validity): admit verified epoch batches fail closed` — Task
   4.4; closes GY-DEF23 only when typed route, generic-route strangle and crash
   negatives pass.
4. `feat(claims): consume completed epoch validity batches` — Task 4.5; closes
   GY-GAP8 only when ledger persistence and real public export pass.
5. `test(gy-n12): freeze epoch and artifact-transition validators` — Task 4.6,
   with no governed payload.
6. `docs(gy-n12): bind artifact transition declaration` — only the exact
   declaration journal path; it changes no source, tool or governed target.
7. `chore(artifacts): issue declared GY-N12 artifact transaction` — Task 4.7
   only if every prerequisite is green; otherwise omit and retain the exact
   incomplete label.

---

## Deployment intersection and the one-replay rule

No existing tracked command can safely execute this transition: N8 has no
candidate path, N10a currently writes five files sequentially, and the 96-path
closure is a private GY-DI1 owner helper. Task 4.6 closes that prerequisite
before any writer. After all source commits and blocking reviews are clean,
enter one self-contained fail-closed shell block:

```zsh
set -euo pipefail
cd "$GY_N12_PRODUCT"
: "${GY_N12_CLUSTER_BRANCH:?capture the attached Cluster-4 branch at entry}"
test "$(git symbolic-ref --short HEAD)" = "$GY_N12_CLUSTER_BRANCH"
test -z "$(git status --porcelain)"
GY_N12_SOURCE_FREEZE="$(git rev-parse HEAD)"
test "$(git merge-base "$GY_N12_IMPLEMENTATION_START" HEAD)" = \
  "$GY_N12_IMPLEMENTATION_START"
GY_N12_TRANSITION_SCRATCH="$(mktemp -d /private/tmp/gy-n12-transition.XXXXXX)"
GY_N12_N8_ENV="$GY_N12_PRODUCT/.venv-gy-n12-n8-$GY_N12_SOURCE_FREEZE"
GY_N12_N8_ENV_RECEIPT="$GY_N12_TRANSITION_SCRATCH/n8-environment-$GY_N12_SOURCE_FREEZE.json"
test ! -e "$GY_N12_N8_ENV"
"${GY_N12_RUN[@]}" tools/devx/foundry/sync_dependency_profile.py \
  --authority-purpose n8_method_catalog_reconstruction \
  --tracked-source-root "$GY_N12_PRODUCT" \
  --source-freeze "$GY_N12_SOURCE_FREEZE" \
  --production-data-root "$GY_N12_DATA_REAL" \
  --production-data-appointment "$GY_N12_DATA_APPOINTMENT_RECEIPT" \
  --environment-root "$GY_N12_N8_ENV" \
  --python-bin "$GY_N12_BOOTSTRAP_PY" \
  --uv-bin "$GY_N12_UV_BIN" \
  --uv-cache-dir "$GY_N12_UV_CACHE_DIR" \
  --offline --receipt "$GY_N12_N8_ENV_RECEIPT"
GY_N12_N8_PY="$GY_N12_N8_ENV/bin/python"
GY_N12_N8_SITE="$GY_N12_N8_ENV/lib/python3.14/site-packages"
test -x "$GY_N12_N8_PY"
test -d "$GY_N12_N8_SITE"
test -s "$GY_N12_N8_ENV_RECEIPT"
GY_N12_N8_RUN=(
  /usr/bin/env -i
  LANG=C.UTF-8 LC_ALL=C.UTF-8
  JAX_PLATFORMS=cpu PYTHONHASHSEED=0 PYTHONNOUSERSITE=1
  PYTHONDONTWRITEBYTECODE=1
  PATH="$GY_N12_N8_ENV/bin:/usr/bin:/bin"
  PYTHONPATH="$GY_N12_PRODUCT/src:$GY_N12_PRODUCT:$GY_N12_N8_SITE"
  "$GY_N12_N8_PY" -S
)
"${GY_N12_N8_RUN[@]}" - "$GY_N12_N8_ENV" "$GY_N12_SITE" <<'PY'
import importlib.metadata as metadata
from pathlib import Path
import sys

environment = Path(sys.argv[1]).resolve()
tooling_site = Path(sys.argv[2]).resolve()
assert tooling_site not in map(Path, map(str, sys.path))
for distribution in metadata.distributions(path=[str(environment / "lib/python3.14/site-packages")]):
    assert Path(distribution.locate_file("")).resolve().is_relative_to(environment)
PY
```

Execute Appendix B's complete **Validator semantics** ledger at this point and
bind every N8/N10a receipt to `GY_N12_SOURCE_FREEZE` and
`GY_N12_N8_ENV_RECEIPT`. Any non-receipt stops before pricing or candidate
generation. Return here only after that wave and its source-flip/corrupt
negatives are reviewed clean:

```zsh
set -euo pipefail
"${GY_N12_RUN[@]}" \
  tools/quality/validation/execute_gy_n12_artifact_transition.py measure \
  --implementation-base "$GY_N12_IMPLEMENTATION_START" \
  --source-freeze "$GY_N12_SOURCE_FREEZE" \
  --output "$GY_N12_TRANSITION_SCRATCH/measurement.json"
```

`measure` imports the canonical GY-DI1 `_deployment_relative_paths`, derives its
complete identity, and intersects it with every changed mechanism path since
the immutable implementation base. Its receipt contains the complete changed
set, 96-path closure identity, exact intersection, affected generated families,
owner predicates, the source-freeze tree, exact transition-tool/source hashes,
every target preimage and current price inputs. The inherited figures—5,387
leaves, 911 protected preimages, 47,532,401 bytes and 1,220.234 seconds cold—are
only inputs; recomputation may replace them.

- Intersection zero means **zero deployment-bound candidate and zero reissue**.
  N8/N10a/epoch families still get candidates only when their declared source
  dependencies moved.
- A non-zero intersection gets exactly one deployment candidate batch. The
  transition tool obtains the N11 write ceiling from
  `tools/quality/timing_budgets.json` (currently 2,346,559.3 ms), captures
  `/usr/bin/uptime` before/after and invokes the existing N9/generation candidate
  builders plus N11's scratch `--write --output` once. A timeout/kill is a
  non-receipt; a completed fail is a receipt. No second cold N11 run occurs.

Build candidates without touching governed targets:

```zsh
set -euo pipefail
"${GY_N12_RUN[@]}" \
  tools/quality/validation/execute_gy_n12_artifact_transition.py \
  build-deployment-candidates \
  --measurement "$GY_N12_TRANSITION_SCRATCH/measurement.json" \
  --candidate-dir "$GY_N12_TRANSITION_SCRATCH/candidates" \
  --n8-python "$GY_N12_N8_PY" \
  --n8-environment-receipt "$GY_N12_N8_ENV_RECEIPT" \
  --n8-candidate-mode candidate-reissue-catalog-provenance \
  --n10a-candidate-mode candidate-dir \
  --epoch-candidate-mode candidate-output \
  --output "$GY_N12_TRANSITION_SCRATCH/candidate-receipt.json"
"${GY_N12_RUN[@]}" \
  tools/quality/validation/execute_gy_n12_artifact_transition.py declare \
  --measurement "$GY_N12_TRANSITION_SCRATCH/measurement.json" \
  --candidate-receipt "$GY_N12_TRANSITION_SCRATCH/candidate-receipt.json" \
  --expected-branch "$GY_N12_CLUSTER_BRANCH" \
  --expected-source-freeze "$GY_N12_SOURCE_FREEZE" \
  --allowed-post-freeze-record \
    docs/superpowers/journals/2026-08-20-gy-n12-cluster-4-artifact-transition.md \
  --output "$GY_N12_TRANSITION_SCRATCH/declaration.json"
```

Root reads and reviews the exact declaration and copies its canonical content
into
`docs/superpowers/journals/2026-08-20-gy-n12-cluster-4-artifact-transition.md`
using `apply_patch`; no tool edits the journal. Commit only that declared
record path, then bind apply to the new attached HEAD:

```zsh
set -euo pipefail
test "$(git symbolic-ref --short HEAD)" = "$GY_N12_CLUSTER_BRANCH"
test -z "$(git status --porcelain)"
GY_N12_DECLARATION_HEAD="$(git rev-parse HEAD)"
"${GY_N12_RUN[@]}" \
  tools/quality/validation/execute_gy_n12_artifact_transition.py apply \
  --declaration "$GY_N12_TRANSITION_SCRATCH/declaration.json" \
  --candidate-dir "$GY_N12_TRANSITION_SCRATCH/candidates" \
  --expected-branch "$GY_N12_CLUSTER_BRANCH" \
  --expected-source-freeze "$GY_N12_SOURCE_FREEZE" \
  --expected-declaration-head "$GY_N12_DECLARATION_HEAD" \
  --state-dir "$GY_N12_TRANSITION_SCRATCH/apply-state"
```

`apply` does not accept the declaration HEAD as a proxy for source custody. It
re-derives the exact relationship
`source_freeze -> declaration_head`: the only intervening paths must equal the
declared record-path set, and there must be zero source, transition-tool,
candidate-dependency or governed-target drift. It re-hashes every candidate and
target, copies and fsyncs every protected preimage, then exclusively creates and
fsyncs `apply-state/armed.json` plus its parent directory **before** the first
replacement. Each target replacement is atomic. Success creates a distinct
fsynced `final.json`; an ordinary failure restores and verifies every preimage
before creating a distinct `fallback.json`. Receipt files are append-only and
never overwritten. On restart, an armed state without final/fallback forces
recovery from the durable preimages before any new candidate can be applied,
then records `fallback.json`. Wrong branch/relationship, changed candidate,
undeclared target or missing protected path performs no governed write.

Root verifies `final.json` and the exact diff, then commits one indivisible
artifact batch. `readback` binds the actual artifact commit and re-runs every
cheap consumer against those exact bytes without rebuilding N11:

```zsh
set -euo pipefail
test "$(git symbolic-ref --short HEAD)" = "$GY_N12_CLUSTER_BRANCH"
test -z "$(git status --porcelain)"
GY_N12_ARTIFACT_HEAD="$(git rev-parse HEAD)"
"${GY_N12_RUN[@]}" \
  tools/quality/validation/execute_gy_n12_artifact_transition.py readback \
  --declaration "$GY_N12_TRANSITION_SCRATCH/declaration.json" \
  --apply-receipt "$GY_N12_TRANSITION_SCRATCH/apply-state/final.json" \
  --expected-branch "$GY_N12_CLUSTER_BRANCH" \
  --expected-head "$GY_N12_ARTIFACT_HEAD" \
  --output "$GY_N12_TRANSITION_SCRATCH/readback-receipt.json"
```

Any blocking post-freeze review invalidates the declaration and re-prices the
wave. Cosmetic findings become recorded debt. Missing authorized
`production_data/manifest.json`, Foundry adjudication, writer authority or
candidate receipt stops before `apply` with its exact non-receipt. The guarded
tool tests an intervening source commit with an otherwise authentic declaration
HEAD and a process kill immediately after the first replacement; both must
leave or recover the complete protected denominator and may never mint a final
receipt.

---

## Final verification and handoff

Close each cluster on its own attached branch and hand it off before beginning
the next cluster. Run every direct task and closeout argv row in Appendix B;
no manifest command, receipt index or selector stands between the plan and
those commands. Independent read-only suites may run in parallel. Serialize
only the guarded artifact transition and any other explicitly shared writer.

Before each launch expected or previously measured above 60 seconds, declare
its ceiling from the prior comparable measurement in the cluster journal.
Capture `/usr/bin/uptime` immediately before and after, wall time, exact argv
and runner, and the ordinary exit or signal. A completed non-zero result is a
failure receipt; a killed or signalled run is a non-receipt. Execute the
complete denominator once after source freeze. A blocking post-freeze source
change invalidates the freeze and re-prices that run.

At closeout, repeat Appendix C's exact declared-set equality and attachment
readbacks, then compare each changed-input gate with its
`GY_N12_IMPLEMENTATION_START` receipt under `P41`. Judge every gate by
its own predicate, never by a composite exit code. The user reviews the
attached cluster branch before merge; no additional reviewer wave or timing
appointment is part of this execution contract.

The final implementation handoff reports, per cluster, delivered chain links
and every retained incomplete label. It reports neither a basis score nor
whole-history authenticity. GY-GAP3, GY-GAP5 and GY-GAP6 remain separate
owner-bound tasks. GY-GAP2 remains `contract_missing` and
`blocked_on_product_decision`, a candidate consumer only. The epoch holder
remains `absent/unallocated` unless the user later makes and evidences the
institutional appointment.

---

## Appendix A — exact basis responsibility and completion ceiling

These 91 IDs are an exhaustive partition of the narrow slice, not a score.
“Delivered” below always means the named behavioral witness passes. A retained
label is part of the planned result and cannot be promoted by a green test.

### Cluster 1 (9)

`C1-CURRENT` is the single source for every row below: overall
`producer_missing`; positive runtime-cutoff authority
`absent/unallocated`; production runtime candidate-evidence disposition
`not_requested` (test/reference `present` remains non-decisive); deficits
`artifact_missing + semantic_test_missing + surface_missing`; blockers Foundry
correctness adjudication owed, authorized
production-data appointment/root/manifest `not_established`, and no admitted
runtime cutoff. The exact preflight refusal is in-process only; refusal-receipt
persistence is `not_established` because the owner-resolved request-bound
receipt-store capability is `absent/unallocated`. No row may abbreviate or
promote that state.

| ID | Executable witness | Current state | Planned terminal disposition |
| --- | --- | --- | --- |
| CB-H09 — omitted recipe dependency | keep the shaped recipe fixed, mutate one influential omitted tool/environment input, require reuse failure | `C1-CURRENT` | negative witness may close; overall identity remains `producer_missing` until all three blockers clear |
| CB-I01 — admitted profile identity | owner purpose relation plus fresh-environment receipt makes N8 and N10a independently reconstruct identical profile/root/distribution discriminants | `C1-CURRENT` | retained `not_established`: Foundry adjudication, authorized data root/manifest and runtime cutoff all required |
| CB-I02 — research-profile regression | a receipt actually issued for `research`/`torch==2.10.0` cannot be relabelled under the fixed N8 purpose; failure names the discriminant, not a package rule | `C1-CURRENT` | negative witness may close; overall remains `producer_missing` with the exact `C1-CURRENT` blockers/deficits |
| CB-I02A — name-invariant incompatibility | keep profile label/shape fixed, substitute an incompatible in-closure distribution, require failure | `C1-CURRENT` | negative witness may close; overall remains `producer_missing` with the exact `C1-CURRENT` blockers/deficits |
| CB-I03 — irrelevant difference | mutate only a distribution outside the resolved deployment closure, require replay unchanged | `C1-CURRENT` | non-decisive negative branch may close without promoting positive identity |
| CB-I03A — novel admitted profile | add a valid TOML profile/distribution and resolve it with zero engine/code allowlist change | `C1-CURRENT` | data-only candidate derivation may close; admission remains `not_established` under `C1-CURRENT` |
| CB-I04 — admitted reconstruction | rebuild GY-DI1's recorded profile using the separately appointed read-only data root and reproduce the accepted deployment identity | `C1-CURRENT` | retained `not_established`: Foundry adjudication, authorized data root/manifest and runtime cutoff all required |
| CB-I05 — exact transition price | transition `measure` recomputes complete 96-path identity and exact changed-path intersection | `C1-CURRENT` | measurement mechanism may close; zero means zero reissue, but no artifact is issuable under `C1-CURRENT` |
| CB-I06 — single replay | source-freeze/declaration relation, timed single candidate wave, durable armed/final/fallback and all-consumer readback | `C1-CURRENT` | retained `artifact_missing`; no candidate wave, governed transaction or replay while the admitted environment is `not_established` |

The fail-closed
`owner_enforced_runtime_subtree_cutoff_not_established` preflight is the
current complete Cluster-1 outcome, not permission to substitute a two-pass
observation.

### Cluster 2 (34)

| ID | Executable witness | Planned disposition |
| --- | --- | --- |
| CB-A01 — native scope | two adapters preserve their native root/scope IDs and reject a minted parent/family scope | test-only boundary witness |
| CB-A02 — native time | inventory adapter omits inapplicable temporal roles while epoch adapter binds only its applicable sparse coordinates | test-only CTM witness |
| CB-A03 — no universal envelope | common DTO/schema accepts two materially different native shapes without event fields or native payload persistence | delivered structural negative |
| CB-A04 — no authority by chronology | identical proof result plus changed owner disposition leaves integrity fixed and changes only owner authority | test-only separation witness |
| CB-A05 — historical authenticity | stale/withdrawn native member remains membership-verifiable while currentness is independently false | test-only protocol/owner composition witness |
| CB-A06 — canonical currentness owners | common surface exposes no Decision Validity or Claim Ledger status/head mutator; attempted projection fails | delivered boundary negative |
| CB-A07 — delivery is not authority | adapter result cannot admit source, accept anchor or assign currentness without the appointed native owner | delivered authority ceiling |
| CB-B01 — complete declared basis | adapter independently reconciles supplied admitted members to a content-bound native denominator; omitted required ref fails | test-only owner witness |
| CB-B02 — membership | valid-shaped native-byte substitution changes recomputed member hash/commitment and fails | delivered |
| CB-B03 — two orders | deletion/insertion/reorder/fork mutations fail predecessor integrity while changed semantic applicability alone does not alter it | delivered integrity-order witness |
| CB-B05 — scoped heads | owner supplies zero/one/multiple opaque native heads under scope rules; verifier never selects one by time or list position | test-only adapter witness |
| CB-B06 — unknown exterior | declared unobservable exterior returns typed `limited`, never universal completeness | delivered limitation |
| CB-B07 — offline replay | verifier succeeds/fails from frozen bytes+basis+proof with network and wall clock unavailable | delivered |
| CB-B08 — recorder non-interference | suppress persisted projection of a completed native result; custody gap appears without changing its disposition | test-only adapter witness |
| CB-B10 — admission is not completeness | keep every presented member/proof valid but omit one native-denominator member; owner reconciliation fails | test-only denominator witness |
| CB-B11 — two head predicates | move authority only, then append annotation only; commitment and authority heads move independently | test-only orthogonality witness |
| CB-B12 — policy-free protocol | source scan plus owner-mutation test proves common verifier never inspects native eligibility/currentness fields | delivered protocol boundary |
| CB-B13 — adapters do not fork proof semantics | epoch and inventory adapters call the same real verifier; neither can accept its rejection | test-only genericity witness |
| CB-B14 — no N11 owner reuse | persistence keys/native roots never use confidence-ledger scope/head; only isolated primitives may be reused | delivered structural negative |
| CB-B15 — algorithm-profiled property | fixed v1 passes membership/substitution/narrowing/complexity behaviors; marker-only algorithm mutation fails | delivered fixed full-prefix profile |
| CB-B15A — profile isolation | cross-family/scope replay and unknown canonical/hash/schema profile fail with all hashes otherwise retained | delivered |
| CB-B16 — head orthogonality | authority-only transition and annotation-only append exercise both independent directions | test-only owner witness |
| CB-B17 — no mandatory native head | inventory witness verifies a commitment head with exact `native_authority_head_refs=()` | delivered genericity witness |
| CB-H01 — predicate provenance | adapter admission receipt freezes each decisive P37 class | test-only owner witness |
| CB-H02 — authority classes | `consumer_asserted`, `institutionally_supplied` and `not_established` inputs fail authority admission | test-only owner witness |
| CB-H04 — form falsifier | keep fields/markers, remove native-byte or consistency recomputation, require real-path failure | delivered behavioral gate |
| CB-H05 — novel member | novel valid-shaped member with unknown relation/provenance fails without code-list update | delivered generic negative |
| CB-H06 — sibling consumer | second conformance consumer cannot bypass canonical verifier or reinterpret `limited` as pass | test-only strangle witness |
| CB-H10 — policy leak | hold bundle/head fixed, change owner admission/currentness, require proof fixed and owner result changed | test-only separation witness |
| CB-H11 — algorithm mutation | keep profile/root markers, remove predecessor/consistency check, require deletion/substitution negatives to fail | delivered source-flip witness |
| CB-H14 — denominator omission | valid prefix with one required native member omitted fails independent reconciliation | test-only owner witness |
| CB-H16 — unknown profile | valid-shaped unknown profile rejects without fallback | delivered |
| CB-H17 — cross-domain replay | retain member/proof hashes, replay under another family/scope/root, require domain-bound failure | delivered |
| CB-J05 — incomplete labels | complete tracked-Python topology plus the frozen allocation record reconcile the Cluster-2 terminal matrix | common primitive/consumer `implemented_but_not_orchestrated`; epoch `producer_missing`; deferred family/anchor/holder `absent/unallocated`; family surface `surface_missing`; authenticity `not_established` |

### Cluster 3 (8)

| ID | Executable witness | Planned disposition |
| --- | --- | --- |
| CB-B04 — consistency | accepting authority derives every prior prefix from owner-loaded accepted lineage, rejects `None` on nonempty lineage and verifies append-only extension before receipt | mechanism delivered; production acceptance `not_established` |
| CB-B09 — retained accepted anchor | appointed acceptance and holder verifiers reject writer-rewritable substitutes and prove independent readback in the test double | test-only holder witness; production holder `absent/unallocated` |
| CB-B09A — anti-rollback | an authentic old anchor passes its historical context and fails a later requested query/lineage | delivered verifier negative |
| CB-H08 — whole-history substitution | rewrite all writer-controlled history/anchors; independent holder rejects, absent holder returns `not_established` | mechanism/test-double witness only |
| CB-H12 — writer-self-anchor | valid writer signature plus self-consistent history without independent retention cannot establish authenticity | delivered independence negative |
| CB-H15 — authentic-anchor rollback | present genuine old anchor and original denominator for later query, require fail/`not_established` without erasing old validity | delivered |
| CB-J01 — epoch chain | no-holder production path demonstrates native epoch proof/acceptance limitation and must not claim the full recompute/bridge/public chain complete | retained incomplete chain; later Cluster 4 links cannot lift anchor gap |
| CB-J06 — appointment gate | acceptance-only, holder-only and neither-appointed cases all remain limited; projection is never a substitute | delivered claim ceiling |

### Cluster 4 (40)

| ID | Executable witness | Planned disposition |
| --- | --- | --- |
| CB-C00 — boundary-source denominator | add one admitted registry/provider row and require service collection; missing/malformed provider blocks append | delivered data-owned registration |
| CB-C01 — L5 denominator | reconcile every applicable `schema_regimes.values()` member; omit one and fail | delivered |
| CB-C02 — L3 denominator | unfiltered amendment rows join uniquely to legal scope, derive every validity window; omit/ambiguous join fails | delivered |
| CB-C03 — fixed semantics | mutate each of the eleven minimum facet values and require a different complete semantic manifest/epoch | delivered |
| CB-C03A — facet free-grow | add valid registered facet with zero resolver conditional, require identity/staleness participation | delivered by registry |
| CB-C04 — explicit coordinate | same records at different native valid/effect query resolve by that coordinate; observation/transaction substitute fails | delivered |
| CB-C05 — unresolved honesty | missing regime/amendment/facet/provider and incomparable branch each return typed unresolved/contested with no head | delivered |
| CB-C06 — data-only free-grow | add new domain regime/amendment/source registration in data only and change resolution | delivered |
| CB-C07 — Ukraine case only | fixture resolves prewar/wartime while engine source scan contains no Ukraine/domain conditional | delivered first case, never enum |
| CB-C08 — append-only revision | new semantic manifest compare-and-appends; prior bytes/head lineage remain readable and mutation fails | delivered epoch-native store behavior |
| CB-C09 — annotation-only rename | changed rule label with identical logic hash appends annotation relation without semantic invalidation | delivered |
| CB-C10 — epoch not clock | retroactive reissue at identical bitemporal coordinates changes `epoch_ref`; incomparable branches never timestamp-order | delivered semantic-coordinate inference |
| CB-C10A — N13b relation | overlay ordinal remains separate; prepare -> hidden pending admission -> owner re-enumeration/finalize -> verified activation reconciles one identical stamp | delivered N13b composition |
| CB-D01 — issuance binding | certificate hash recomputation covers epoch manifest, inputs, purpose, provenance, profiles and sparse native coordinates | delivered binding |
| CB-D02 — stale transition | relevant verified transition enters canonical DV stale/revalidation batch; irrelevant target leaves status unchanged | delivered owner transition |
| CB-D03 — public fail closed | phase-one/mid-crash/cache-restart PUBLIC and `/runs` reads exclude currentness while REVIEWER preserves history | delivered through DV/public strangle |
| CB-D04 — recipe is certificate | exact recipe/input/canonical-producer binding verifies; chronology cannot execute/project recompute | binding/negative delivered; global executor `absent/unallocated` and known producer `producer_missing` |
| CB-D05 — transitive invalidation | exact dependency graph propagates through affected descendants, stops at sibling branch and rejects proximity lineage | delivered |
| CB-D06 — cascade vocabulary | permutation of advisory inputs yields same exact owner/target/purpose disposition vector | delivered |
| CB-D06A — event advisory | keep event/action fixed and vary owner result; pre-adjudication ceiling stays review/contested | delivered |
| CB-D06B — adjudicated reaction | only verified owner disposition selects annotation/invalidate/reissue/supersede/withdraw | delivered |
| CB-D06C — Claim lifecycle bridge | only completed verified DV batch atomically advances canonical Claim Ledger head and public projection | delivered GY-GAP8 path |
| CB-D06D — mixed outcomes | disjoint targets stay distinct, annotation cannot cancel, same-key conflict freezes, order permutation invariant | delivered |
| CB-D07 — historical query | now-invalid certificate remains authentic at issuance coordinate with linked later invalidation | delivered |
| CB-D08 — OpenWorldRisk relation | owner role/evidence/vector bytes and provenance are resolved/recomputed; caller role/severity cannot carry gate | no-evidence branch delivered; lifecycle owner `absent/unallocated`, positive evidence `producer_missing` |
| CB-D08A — OWR composition | any proven-outside => risk; all proven-inside => within; any missing/unknown => `not_established` | delivered composition/no-numeric-risk |
| CB-D09 — promotion freeze | actual N9 replay freezes on risk and `not_established`; supplied low/deadline/projection cannot bypass | delivered real consumer |
| CB-D10 — current-valid front | stale/revalidation/pending packets are removed from decision-front eligibility; only owner-current remains | delivered DV/N9 decision-front strangle |
| CB-D11 — freshness non-receipt | absent/unknown/expired proof cannot reuse cached green; historical issuance query stays separate | delivered, including run-index generation invalidation |
| CB-D12 — executable recipe | remove influential tool/environment input while retaining recipe shape, require reuse failure | negative delivered; recompute producer remains `producer_missing` |
| CB-D13 — missed obligation reissue | challenge/invalidate and widened-epoch requirement delivered; same-epoch mutation fails | automatic widened-epoch/recompute chain `absent/unallocated` |
| CB-D13A — delta honesty | old arithmetic remains historical and widened-basis delta cannot be published as improvement | delivered |
| CB-H03 — supplied epoch falsifier | keep positive overlay ordinal, falsify native regime/stamp coordinate, require admission failure | delivered |
| CB-H07 — adjudication falsifier | hold perturbation/action fixed, change canonical owner disposition, require authority to follow owner | delivered |
| CB-H18 — N13b disagreement | valid passport/ordinal plus stamp mismatch fails; restored match enters same stale cascade | delivered |
| CB-H19 — facet mutation | mutate every registered minimum facet and add one novel facet; each participates, unknown fails | delivered complete denominator |
| CB-H20 — OWR premise | advance lifecycle from intended to actual and vary/remove actual component evidence; require risk/unknown and N9 freeze | delivered falsifier; positive institutional chain incomplete |
| CB-H21 — missed-obligation cascade | old-certificate mutation/same-epoch recompute fails; plan retains missing full reissue chain label | `absent/unallocated`; no synthetic pass |
| CB-H22 — cascade mixed outcomes | transport permutation/disjoint outcomes/conflict attack preserves owner-vector rules and freezes conflict | delivered |
| CB-J01A — OWR chain | no-owner/evidence -> persisted `not_established` vector -> owner projection/replay -> N9 freeze -> public limitation | fail-closed branch delivered; appointed owner/positive evidence chain remains incomplete |

---

## Appendix B — executable command ledger

All commands assume the tooling `GY_N12_RUN` array and scratch directory from
the execution protocol; terminal N8/N10a commands additionally require the
post-source-freeze `GY_N12_N8_RUN` and its receipt. Test full files, never
selectors that can drop a required node.

### Cluster test waves

Each task section's direct argv rows are the complete, non-narrowable
denominator for that task. Define one zsh callback containing those commands
verbatim and pass that callback to Appendix C's boundary executor. Test full
files; do not use selectors that can drop a required node. A task or cluster
handoff lists every command, expected semantic/process result and actual
receipt separately; a bundled exit code never decides another predicate.

For any row expected or measured above 60 seconds, declare its ceiling before
launch from a prior comparable measurement and capture an `uptime` pair, wall
time and ordinary exit or signal in the journal. Run the complete denominator
once after source freeze. An ordinary non-zero exit is a completed failure
receipt. A kill, signal or enforced timeout is a non-receipt. There is no
timing index, catalog mutation, timing admission or hidden rerun.

### Validator semantics

Standard check/rederive/source-flip modes exit zero only with top-level JSON
`status="pass"`. Epoch corrupt mode does the same. Legacy N8/N10a corrupt modes
retain exit 1 when every corruption is rejected; N8 emits semantic pass, while
N10a's frozen inverted contract emits semantic `status="fail"` plus only
`corrupt_field_drift_detected` and no `corrupt_field_drift_not_detected`.
Every validator output implements the common envelope `validator`, `mode`,
`status`, `issues` and `receipt_sha256`; no process status is inferred from the
payload and no payload status is inferred from the process.

Every validator mode is a distinct direct command in the task denominator;
there is no validator subset loop. The boundary callback checks the declared
mode/status/required/forbidden issue-code contract and the process result
independently. Removing the semantic assertion while retaining an exit code,
or removing the exit assertion while retaining JSON markers, fails its own
contract mutation.

### Lint, imports and architecture

Static and closeout checks are likewise direct rows in that same one-pass
denominator; no second loop exists. The changed-path Ruff row filters existing
Python/stub paths from the complete declared/Git candidate delta; corepack
installation, the narrow public-surface writer, architecture check, backend
verify, CI parity, runtime contract and `git diff --check` each retain their
own predicate. Never run `guardrails sync`.

---

## Appendix C — commits, cluster closure and pattern pass

The commit boundaries named under each cluster are indivisible mechanism
boundaries. Registry plus reference documentation that names the same source
belongs in that source commit; generated bytes belong only in the terminal
artifact commit. N12 executes Cluster 1, then 2, then 3, then 4 on separate
attached cluster branches in this same provisioned worktree. At cluster entry,
capture the actual branch and parent in the cluster journal; no function below
binds a moving `main` tip or invents a branch name.

The retired bootstrap's exact historical bytes remain under
`refs/gy-n12-preservation/bootstrap-wave6`,
`refs/gy-n12-preservation/bootstrap-wave6-declared-residuals` and
`refs/gy-n12-preservation/bootstrap-wave6-evidence`. They are recovery
evidence only. No bootstrap boundary, scalar appointment, disposition,
reviewer receipt or self-authorization step remains in the execution path.

Before the first edit for a task, assert every declared `Modify` path exists.
Do not assert that an `Add` path exists until its candidate is present:

```zsh
gy_n12_assert_task_entry() {
  emulate -L zsh
  setopt LOCAL_OPTIONS ERR_EXIT NO_UNSET PIPE_FAIL
  test "$(git rev-parse --show-prefix)" = policy-engine/
  local gy_n12_modify
  for gy_n12_modify in "$@"; do
    test -e "$gy_n12_modify"
  done
}
```

Use the following attachment function at every commit boundary. The symbolic
HEAD check, expected-old check and branch update are one transaction. If this
Git cannot execute `symref-verify`, the boundary blocks; no non-atomic
fallback exists.

```zsh
gy_n12_attach_commit() {
  emulate -L zsh
  setopt LOCAL_OPTIONS ERR_EXIT NO_UNSET PIPE_FAIL
  local gy_n12_branch="$1"
  local gy_n12_old="$2"
  local gy_n12_new="$3"
  local gy_n12_tree="$4"
  local gy_n12_ref="refs/heads/$gy_n12_branch"

  test "$(git rev-parse --show-prefix)" = policy-engine/
  test "$(git symbolic-ref -q HEAD)" = "$gy_n12_ref"
  test "$(git rev-parse HEAD)" = "$gy_n12_old"
  {
    print -r -- start
    print -r -- 'option no-deref'
    print -r -- "symref-verify HEAD $gy_n12_ref"
    print -r -- "verify $gy_n12_ref $gy_n12_old"
    print -r -- "update $gy_n12_ref $gy_n12_new $gy_n12_old"
    print -r -- prepare
    print -r -- commit
  } | git update-ref --stdin

  test "$(git symbolic-ref -q HEAD)" = "$gy_n12_ref"
  test "$(git rev-parse HEAD)" = "$gy_n12_new"
  test "$(git rev-parse 'HEAD^{tree}')" = "$gy_n12_tree"
}
```

A boundary suite is a named zsh callback containing that task's direct argv
rows verbatim. The plain executor below accepts the captured branch, expected
parent, commit message, callback name and the complete declared `Add` plus
`Modify` path union. It rejects duplicate declarations, a dirty index, a
missing candidate, any undeclared drift and any suite-created drift. It stages
only the exact set, commits the captured tree and reads attachment and
cleanliness back.

```zsh
gy_n12_execute_task_boundary() {
  emulate -L zsh
  setopt LOCAL_OPTIONS ERR_EXIT NO_UNSET PIPE_FAIL
  local gy_n12_branch="$1"
  local gy_n12_old="$2"
  local gy_n12_message="$3"
  local gy_n12_suite_fn="$4"
  shift 4
  local -a gy_n12_paths=("$@")
  local gy_n12_expected gy_n12_unique gy_n12_observed
  local gy_n12_staged gy_n12_tree gy_n12_commit gy_n12_candidate

  gy_n12_expected="$(printf '%s\n' "${gy_n12_paths[@]}" | LC_ALL=C sort)"
  gy_n12_unique="$(printf '%s\n' "${gy_n12_paths[@]}" | LC_ALL=C sort -u)"
  test -n "$gy_n12_expected"
  test "$gy_n12_expected" = "$gy_n12_unique"
  test "$(git rev-parse --show-prefix)" = policy-engine/
  test "$(git symbolic-ref --short HEAD)" = "$gy_n12_branch"
  test "$(git rev-parse HEAD)" = "$gy_n12_old"
  test -z "$(git diff --cached --name-only)"

  for gy_n12_candidate in "${gy_n12_paths[@]}"; do
    test -e "$gy_n12_candidate"
  done
  gy_n12_observed="$({
    git diff --name-only --relative "$gy_n12_old" -- .
    git ls-files --others --exclude-standard -- .
  } | sed '/^$/d' | LC_ALL=C sort -u)"
  test "$gy_n12_observed" = "$gy_n12_expected"

  "$gy_n12_suite_fn"

  test "$(git symbolic-ref --short HEAD)" = "$gy_n12_branch"
  test "$(git rev-parse HEAD)" = "$gy_n12_old"
  test -z "$(git diff --cached --name-only)"
  for gy_n12_candidate in "${gy_n12_paths[@]}"; do
    test -e "$gy_n12_candidate"
  done
  gy_n12_observed="$({
    git diff --name-only --relative "$gy_n12_old" -- .
    git ls-files --others --exclude-standard -- .
  } | sed '/^$/d' | LC_ALL=C sort -u)"
  test "$gy_n12_observed" = "$gy_n12_expected"

  test "$(git symbolic-ref --short HEAD)" = "$gy_n12_branch" &&
    git add -- "${gy_n12_paths[@]}"
  gy_n12_staged="$(
    git diff --cached --name-only --relative "$gy_n12_old" -- . |
      LC_ALL=C sort -u
  )"
  test "$gy_n12_staged" = "$gy_n12_expected"
  git diff --cached --check
  gy_n12_tree="$(git write-tree)"
  test "$(git symbolic-ref --short HEAD)" = "$gy_n12_branch"
  test "$(git rev-parse HEAD)" = "$gy_n12_old"
  gy_n12_commit="$(
    printf '%s\n' "$gy_n12_message" |
      git commit-tree "$gy_n12_tree" -p "$gy_n12_old"
  )"
  gy_n12_attach_commit \
    "$gy_n12_branch" "$gy_n12_old" "$gy_n12_commit" "$gy_n12_tree"
  test -z "$(git status --porcelain=v1 --untracked-files=all)"
}
```

Record the declared and observed sets, callback argv, suite receipts, commit
and tree IDs, and both attachment readbacks in the cluster journal. For the
terminal artifact boundary, derive the exact target array from the reviewed
declaration's `targets[*].path`, require the epoch payload, generated-artifact
registry and reference paths, compare that array with the exact post-apply
delta, and pass it to this same executor. No wildcard or hand-entered extra
path is admissible.

Root alone edits and commits. A blocking source finding lands before
`GY_N12_SOURCE_FREEZE`; after freeze it invalidates the declaration and
re-prices the full run. The user reviews each attached cluster branch before
merge. No harness review wave, timing appointment or scalar appointment is
part of this contract.

Pattern pass:

- `P01/P02`: every delivered family link has producer, artifact, bridge,
  consumer and negative test; missing producers retain their labels.
- `P05/P37/P38`: native owner reconciliation, typed DV verifier injection,
  generic-route strangle and real N9/Claim consumers prevent caller/projection
  authority and proxy gates.
- `P07/P08`: recipes and sparse native coordinates are content-bound; an
  `epoch_ref` is a semantic coordinate, never a third clock.
- `P27/P28`: no parent scope, universal envelope, second native ledger or
  unstrangled generic epoch path survives.
- `P29/P32`: real source flips and byte/provenance recomputation defeat marker
  and shape proofs.
- `P35/P39`: owner denominators and deployment paths are fully enumerated;
  records/tests do not consume mechanism budgets.
- `P40`: second findings widen the structure (registries, typed route,
  persisted bridge, real N9 consumer), never patch another instance.
- `P41`: inherited reds are replayed at `GY_N12_IMPLEMENTATION_START` and are
  inherited only when the complete changed-path/input intersection is zero.
