# Independent A foundation review

Reviewed the committed A foundation at `2ad1e8b47b5ba2bccc6cbba96fb206112c6fbd06` against A1/A2/A3 in the correction plan. Read-only source review; no generator, shared world-model rebuild, or review test was executed. The reviewed working files were independently hash-checked against the commit before review:

- `src/polisyos/runtime/quality/grounding_risk.py@288e5d9c12302eb4777c613355fe50ac525d7ac2`
- `src/polisyos/runtime/quality/grounding_bind.py@c864cc722dcb353b083db9d72a5e0dc39ce64102`
- `src/polisyos/runtime/quality/grounding_calibration.py@c8f9d1bdf07a0a6a7e44db63d74993c694490295`

## Finding A-RV-B01 — frame intake trusts a stale nested payload

**Same P37/content-binding class one level deeper. Blocking until exercised and resolved.** `grounding_calibration.py:349` accepts a `CalibrationFrame` without revalidating its complete content hash. `run_refusal_suite` at line 413 revalidates the suite but likewise does not revalidate the frame. It compares the frame's claimed hash and then re-derives a suite using only each frame row's operator family, target identities, and ambiguity. A frame's nested `signature` dictionary remains mutable even though the enclosing Pydantic model is frozen.

The divergent case is changing a non-selector deciding input such as a nested signature parameter while retaining the original `frame.content_hash`. The suite declaration can remain identical because its case source hash comes from the reference atom, not that changed frame payload. The execution therefore does not establish the promised complete binding to the declared frame. This is a static code inference, not an executed exploit receipt.

The smallest closure is to replay the existing `CalibrationFrame` validation at the shared declaration/execution intake. Keep a genuinely valid frame positive and mutate a nested non-selector field with the original hash for the negative. Test declaration and execution, so a caller cannot bypass one by supplying an already-built suite. Removing that intake replay while leaving the hash fields intact must make the unchanged negative test red. Root was notified before any source edits.

## Other reviewed properties

| Requirement | Source mechanism inspected | Review conclusion and limit |
| --- | --- | --- |
| A3 charges only owner-approved binding | `GroundingBindGate.certificate_for` replays CG1, checks relation, obligations, robustness and owned calibration before `_decision` invokes `_admit`. | No additional concrete escape found in the reviewed source. This is not execution credit. |
| A3 durable shared cap and idempotent replay | `GroundingRunBudget._admit` locks the canonical run, replays the complete immutable event chain, checks an integer admission count before append, and reuses the existing event for an identical binding key. `_read_chain` reconciles event paths, validates content and chain linkage, and treats corrupt state as unavailable. | Source supports the intended owner shape. Crash/concurrency/cap evidence remains the owning A verification responsibility. |
| A3 candidate continuation | Failed admission becomes abstention while retaining the safe set/candidate custody. Candidate requests do not consume a binding admission. | No additional source finding. Actual negative-to-candidate and cap controls remain required. |
| Synthetic authority ceiling | Bind creation and promotability resolution examine synthetic reference provenance; contract-testing calibration is separate from the empty current production calibration store. | Synthetic mechanics do not supply a correctness bound or current production calibration. The root-owned CG2-v2 to CG3 consumer migration is a separate known handoff, not repaired by this review. |
| A2 complete input frame and source dependence | `build_owner_frame_inputs` reads the actual owner dictionary and independently enumerates raw identities; unresolved rows remain in the frame. `source_clusters` computes transitive shared-source components. Difficulty uses input structure, and epoch scope is separate. | No additional concrete source finding. The official declared frame and complete execution identities still decide acceptance. |
| A1 honest refusal sensitivity | Suite execution invokes actual CG1 and CG2 and requires the constructed mismatch's specific contradiction/refusal, with a matched mechanical positive. Its output retains the synthetic/no-correctness limitation. | The permanent absence of production calibration is not used as the decisive mismatch property. Frame binding remains blocked by A-RV-B01 above. |

This bounded review does not approve final A completion. It identifies one actionable intake gap; hypothetical future producers and already-declared scientific limitations were not treated as new repair rounds.
