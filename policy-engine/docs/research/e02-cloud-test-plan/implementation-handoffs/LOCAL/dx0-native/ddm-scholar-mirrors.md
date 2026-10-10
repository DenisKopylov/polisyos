# DDM incident and Scholar scoring mirrors

## Scope and source binding

This packet covers exactly the two section-3 test paths named by
`LOCAL/dx0-native/ratchet-repair-routing-current.md` (SHA-256
`a54c4e42702850227a0d3d95ceca04e36e922b67b37833fd1bc485eeae0112c1`):

| Source owner | Direct test | SHA-256 at review checkpoint |
|---|---|---|
| `src/polisyos/ddm/integration/incident.py` | `tests/unit/ddm/integration/test_incident.py` | `92561c5097bd0e82eb28220fdb9620164fd99236053b7fb0ba8a06183b871348` |
| `src/polisyos/scholar/search/scoring.py` | `tests/unit/scholar/search/test_scoring.py` | original checkpoint: `73ece3ad82d743776cdef9749efcfdb7531305bff96fa754f3edad584da73bfc`; repaired working file: `34a60559aebd228a849952ee1fe8e42f6824ebdf56172df1b27e88096739a7d9` |

The candidate was WIP at HEAD `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`,
tree `741784521d909f775d50863a29deec63cde300cd`. These test files and this
packet are local changes; the production sources were read-only. The DDM
readiness composer is `src/polisyos/ddm/readiness/readiness_mapper.py`
(SHA-256 `040c993e244c868c897456429738e5140c9607eae4157cca33b70c849f9ca7d0`),
and Scholar's typed inputs are `src/polisyos/scholar/search/models.py`
(SHA-256 `8ffd9f8223bcc416b1c1dcacb68f730703cd365be92bccef757683f7b062a784`).

## DDM route and acceptance boundary

The new test calls the canonical `map_readiness` producer, passes its real
`ReadinessStateEvent` into `build_incident_payload`, and for hard data-quality
failure supplies the real `build_root_cause_bundle` result. This checks the
readiness-to-incident consumer boundary, not only event constructors or the
upstream mapping. Existing `tests/unit/ddm/test_readiness_mapping.py` exercises
upstream state mapping but does not call the incident consumer; the new path
fills that direct-route gap.

The exact expected values are copied from the current source-owned
`_actions_for_state` and `_severity_for_state` behavior. Hook order below is
`create_ticket / notify_owner / page_owner / trigger_shadow_retrain /
freeze_rollout / rollback_or_fallback`.

| State | Severity | Required actions | Incident hooks |
|---|---|---|---|
| R4 | `none` | `continue_monitoring` | false / false / false / false / false / false |
| R3 | `watch` | `annotate_dashboard`, `increase_label_sampling` | false / true / false / false / false / false |
| R2 | `investigate` | `open_investigation_ticket`, `increase_label_sampling`, `run_shadow_retrain` | true / true / false / true / false / false |
| R1 | `retrain` | `freeze_rollout`, `trigger_shadow_retrain`, `require_owner_signoff` | true / true / false / true / true / false |
| R0 | `rollback` | `rollback_or_route_to_fallback`, `page_model_owner`, `block_registry_promotion` | true / true / true / false / false / true |

The inputs are explicitly synthetic and deterministic: no input for R4; a
`risk_score=0.5` watch shift for R3; critical-slice budget 0.25 for R2 and 0.50
for R1; and a hard-failure `DataQualitySignal` for R0. This matches the
current readiness thresholds. The R0 case also requires the incident's root
cause bundle ID and attached event ID to equal the bundle emitted from that
same failure signal. No action policy was added or inferred.

## Scholar route and acceptance boundary

`test_scoring.py` imports `scoring.py` directly. The production consumers
include `scholar/search/fetcher.py` (snippet extraction),
`scholar/search/service.py` (ranking, snippets, and conflict score), and
`scientist/evidence/claim_support.py` (conflict score). Those consumer routes
do not currently provide a direct FQN test for this owner. The new cases test
the three named source-owned boundaries:

* Two directionally consistent snippets yield no conflict note; adding an
  opposite-direction snippet yields the mixed-polarity score and note. This
  is a lexical uncertainty signal, not a factual contradiction verifier.
* Returned span offsets must select exactly the returned citation text:
  `text[start_char:end_char] == snippet.text`, with the range inside the source
  text. ASCII, Unicode whitespace/characters, punctuation, and a Unicode-prefix
  metamorphic case exercise the same coordinate invariant. A whitespace-only
  fallback window emits no empty citation. The initial source
  selected `[9:25]` (`" bbbbbbbtarget  "`) but emitted the stripped string
  `"bbbbbbbtarget"` with the original offsets. The narrow fix retains trimmed
  output and adjusts the start/end positions in Python character coordinates;
  it skips an empty trimmed window instead of emitting an unbindable citation.
* A clean source and an SEO-marked source use the same synthetic `.invalid`
  host, source type, query, and search rank. The anti-SEO score, pre-fetch
  search score, and consumer `source_rank_key` must all keep the clean source
  first. The fixtures make no claim about real issuers or external sources.

The citation-span divergence is classified under P40 as a **new class** for
this packet: exact citation text-to-offset binding. No repeated same-class
escape was established here. The fix widens the boundary adjustment over all
trimmed window edges, not one whitespace example. The new test and existing
fetcher test now assert exact source slicing; existing Scientist claim-support
and snippet-ledger tests exercise downstream consumers. The other two Scholar
assertions remain separate scoring properties. This applies P29/P38: the
falsifier calls the real compressor and names the source/display divergence.

## Verification and limits

The focused checks used synthetic text and `.invalid` URLs only; the existing
fetcher case replaces network resolution and transport with local stubs. The
focused red/green outputs are retained under ignored `LOCAL/raw` paths:

| Run | Command/result | Complete output reference |
|---|---|---|
| Red before source edit | `policy-engine/.venv/bin/python -m pytest -q policy-engine/tests/unit/scholar/search/test_scoring.py -k snippet_offsets` — exit 1, four failing span cases | `LOCAL/raw/dx0-native-scholar-span/pytest-red.txt` @ SHA-256 `e1121d4ca96ba352a66762203d1efc75b58f7848d975d784e80a7df4e9bdb412` |
| Green after source edit | same command — exit 0, four passed | `LOCAL/raw/dx0-native-scholar-span/pytest-green.txt` @ SHA-256 `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830` |
| Direct and downstream slice | `policy-engine/.venv/bin/python -m pytest -q policy-engine/tests/unit/scholar/search/test_scoring.py policy-engine/tests/unit/scholar/search/test_fetcher_security_cache.py::test_find_in_page_returns_stable_spans policy-engine/tests/unit/scientist/evidence/test_claim_support.py policy-engine/tests/unit/scientist/evidence/test_snippet_ledger.py` — exit 0, 14 passed | `LOCAL/raw/dx0-native-scholar-span/consumer-green.txt` @ SHA-256 `98967da847c1b2cb69c4a206d58c16711070f173d6a41a0dde3f36db2fab9257` |

Then run the configured root Ruff and in-memory compilation checks:

```text
policy-engine/.venv/bin/python -m ruff check --config policy-engine/architecture/tooling/ruff/workspace_root.toml policy-engine/src/polisyos/scholar/search/scoring.py policy-engine/tests/unit/scholar/search/test_scoring.py policy-engine/tests/unit/scholar/search/test_fetcher_security_cache.py
All checks passed!

policy-engine/.venv/bin/python -c 'from pathlib import Path; paths=[Path("policy-engine/src/polisyos/scholar/search/scoring.py"), Path("policy-engine/tests/unit/scholar/search/test_scoring.py"), Path("policy-engine/tests/unit/scholar/search/test_fetcher_security_cache.py")]; [compile(path.read_text(), str(path), "exec") for path in paths]; print("compiled", len(paths), "files in memory")'
compiled 3 files in memory
```

Final reviewed file hashes: `test_scoring.py` `8c89be104e52799e7abbd8633ba634716d1cef4ecb08445fa74c9076ee43f5ad`;
`test_fetcher_security_cache.py`
`556505127e2ef6f7e171529224baef6daea99bd7a66e1737cfe1c9058c8b2b08`;
Scholar README `bfde34c3929d1abf949d922c0e1b1e1c4c28b9fd74cc7345ef8f7d531d6c68c3`;
release fragment `1accd77fe42295827b90f2d991c0a9b901cb82fcb12528a43efe1861af1d76a4`.

The DDM matrix's runtime outcome remains unverified pending the parent-owned
combined test run. The Scholar correction was locally tested at the compressor,
fetcher, claim-support, and snippet-ledger seams; this is not a final source
freeze or whole-repository acceptance claim.
