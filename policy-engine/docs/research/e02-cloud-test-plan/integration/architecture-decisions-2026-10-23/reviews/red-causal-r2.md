# Red-team R2 disposition — revised PAG/R4 profile

## Reviewed bytes

Read the exact current draft bytes; SHA-256:

- `03-pag-scope-and-legal-relation.md`: `51dbf9c81f2e7aeaf41e5547d731ccc68ff764b8a89d5c67bcdf9fa209b1fbdd`
- `04-conditional-transport-diagnostic.md`: `555984e7b3c6b943468f93c0705295bf288919ecddfef815a455aa64290e8233`
- `06-validated-partial-graph-profile.md`: `1df69a0085c2b3a09f83d12bd64db870ea36b209e7c6535505b72108698e5036`

Code/source pin remains F12 `f12fb9895a4009ce77828554f4c5c18d83e6ec15`. No tests ran; no tracked files changed. This is an architecture disposition, not code acceptance or evidence the selected producer exists.

## Disposition

**Conditional GO for the design and actual producer/validator extension; NO runtime or finding closure.** The revised design now has a credible useful-positive path without relaxing direct scalar PAG refusal: explicitly request a named finite profile; generate PAG-compatible candidate MAGs; establish membership by reconstructing and semantically comparing the complete observational PAG; evaluate only validated members through the existing resolved DAG/ADMG method; report sensitivity only over that finite selected family. It correctly does not require proof that the selected family covers every PAG completion. The Lex relation refusal is kept separate from operation access, and its absent positive producer is stated honestly.

The membership argument is mathematically sound **if** the member is a valid no-selection MAG, its bidirected expansion is a faithful latent-DAG representation, and the pinned DAG-to-PAG oracle is semantically conformant for the supported domain. None of those runtime conditions has yet been demonstrated. `DAG2PAG` is a candidate oracle, not self-authenticating proof; the proposed independent small-graph/separation conformance and removal control are appropriate. No recursive verifier of future validators is required.

## Concrete blockers / minimal repairs

1. **CPDAG route exceeds the new profile’s domain (spec blocker; P02).** R4 §Execution step 4 says PAG **and CPDAG** invoke a registered validated-family producer; 06 defines only a finite no-selection PAG profile. Direct scalar CPDAG admission also remains refused. Make dispatch profile-specific: the PAG profile handles PAG; an explicit CPDAG request is typed unsupported until a separately registered DAG-equivalence profile exists (or define/test that profile using DAG-to-CPDAG equality). This must not suppress the PAG positive or the separately required resolved DAG/ADMG positive. Do not imply one profile validates both graph types.

2. **Define what “family success” means (semantic blocker; P10/P38).** F12 `TransportabilityStatus` includes `IDENTIFIED`, `PARTIALLY_IDENTIFIED`, `BOUNDED_NON_IDENTIFIED`, and `UNSUPPORTED` (`ir/analytics/transportability.py:425-436`). R4 names `selected_family_success_fraction` but says only “documented completed outcome.” A partial/bounded result is completed without being an identified transport result; treating all non-unsupported outcomes as success would repeat the old sampler’s proxy (`transport_check.py:385-395`). Prefer a per-status/mode count vector. If keeping a fraction, state the exact numerator (e.g. exact `IDENTIFIED` outcomes only) and denominator, separately expose partial/bounded/unsupported/error/unevaluated outcomes, and ensure this remains descriptive candidate output.

3. **Pin the backend API actually consumed (implementation blocker before enabling profile; P38).** F12 lock pins causal-learn `0.1.4.4` (`uv.lock:584-602`) while `pyproject.toml:101` allows `>=0.1.3.8` in optional extra `causal-discovery`. The [official 0.1.4.4 `DAG2PAG.py`](https://github.com/py-why/causal-learn/blob/0.1.4.4/causallearn/utils/DAG2PAG.py) defines `dag2pag(dag, islatent: List[Node], isselection: List[Node] = [])`; it uses Node objects in set operations, though [the docs describe `islatent` as indexes](https://causal-learn.readthedocs.io/en/latest/utilities_index/Graph%20operations/DAG2PAG.html). The adapter must pass exact Node objects, use no selection nodes for this profile, bind the resolved installed package/source version, and refuse this profile when the optional extra or validated version is unavailable. Do not silently use the local R1–R3 checker or an arbitrary minimum-compatible release as the membership oracle. The draft already says lock/source must be bound; this precise API mismatch should be included in that acceptance check.

4. **Build the resolved transport diagram per member (bridge clarity; P02).** F12 `resolve_transport.py:404-444` builds a context `SelectionDiagram`, then the Lex verifier exception returns immediately. Splitting that catch to retain the outer refusal and invoke the explicit candidate branch is feasible at this loop seam. But the existing diagram’s `base_graph` is the source PAG; the solver cannot receive it unchanged after validation. For each admitted member, construct the resolved diagram with that member as `base_graph`, preserving the same frozen population-transport S-nodes, source/target contexts, and query. Keep observational sample-selection variables (excluded by the profile) distinct from transport S-nodes and from unverified policy-law S-nodes. This is an implementation-ready detail, not a reason to move or remove the direct scalar gate.

5. **Keep the profile acceptance bounded and operational (P29/P32/P37).** The exact graph should be translated to/from the pinned causal-learn representation by observed node identity and endpoint-at-node, not array/list position. The profile already excludes tail-tail, selection-encoded, background-knowledge-refined and incomplete RFCI cases and says to compare semantic graph structure; keep those refusals explicit. Ensure generated latent identifiers cannot collide with observed IDs. A time-out/incomplete `DAG2PAG` call is `validation_incomplete`, never membership. The proposed independent discriminating-path and latent cases plus remove-membership-oracle control are sufficient for this bounded profile’s present acceptance; do not expand them into a recursive verifier of hypothetical future graph rules.

## Preservation and remaining evidence

The explicit candidate request (absence means no new computation) and removal of the old heuristic sampler fix the R1 laundering/implicit-work risks. Separate proposal and evaluation accounting is now structurally adequate if each proposal and member has one mutually exclusive final disposition. `DAG2PAG` itself can be exponential in observed variables and has an orientation loop; the draft correctly requires measured graph-size preflight, existing resource admission, supervised deadline, bounded streaming/dedup, and truthful partial/timeout status. If no existing permit/supervisor can enforce that profile, the particular PAG run stays unavailable pending that bridge, while DAG/ADMG candidate positives remain possible; do not turn that into a universal all-candidate refusal.

F12 `resolve_transport.py` confirms the Lex early return occurs after the context diagram is built but before solver execution. The revised catch split is therefore a real extension point if access/resource admission precedes materialization as required. F12 `source_relation.py` still has only `verification_missing` and an always-raising verifier; no legal-positive chain should be emitted by this work. Draft03 now identifies runtime access anchors but correctly treats presence as not proof of a graph-route admission. Candidate synthetic/manual success remains distinct from actual data-use authorization and from legal claim authority.

Version tuple compatibility, external reader coverage, producer persistence and late-evidence invalidation remain owner-dependent or UNRUN as R4 says. New writer emission stays gated on owner-established exact tuples and reader-first migration. The finite PAG design is selected architecture only; the DAG/ADMG persistence positive, PAG member oracle, consumer migration, and every adversarial/removal signal remain runtime UNRUN.

## Final delta readback

Narrow reread of the four corrected clauses only; no new full review and no tests. Current SHA-256:

- `03-pag-scope-and-legal-relation.md`: `51dbf9c81f2e7aeaf41e5547d731ccc68ff764b8a89d5c67bcdf9fa209b1fbdd` (unchanged)
- `04-conditional-transport-diagnostic.md`: `8c844ace614e437566c0725228bad857a00b7b1e71d3bb9bbb6a40e35878ca6b`
- `06-validated-partial-graph-profile.md`: `66c257c9ed7fb5b549c8381af6fdaae92d47c36984c60bce3ce42ec1778ab625`

All four R2 blockers are addressed in the readback: CPDAG is explicitly outside this PAG profile; the status/mode vector is primary and the optional fraction counts `IDENTIFIED` over all valid completed outcomes while failed/interrupted/unstarted work stays separate; the tagged `0.1.4.4` adapter uses Node objects, no selection nodes, and collision-free latent identities; each member receives a resolved SelectionDiagram with its own `base_graph` and the frozen transport S-nodes, contexts, and query. **Disposition: conditional GO for the selected PAG design; no residual spec blocker in this delta. Runtime, persistence, consumer migration, and semantic probes remain UNRUN; no code acceptance or finding closure.**
