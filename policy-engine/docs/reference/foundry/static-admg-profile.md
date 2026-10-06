# Static ADMG inference profile

Static graph separation, graph surgery and symbolic causal rewrites accept
resolved, contemporaneous directed and bidirected relations. A directed arrow
may be stored as either `TAIL, ARROW` or the reverse `ARROW, TAIL`; both represent
the same parent-to-child relation. `ARROW, ARROW` represents a bidirected relation.

An edge with two tails, any circle endpoint, or a positive compact lag is outside
this profile. The shared adjacency admission raises `ValueError` with the stable
prefix `Unsupported static ADMG profile: ` and identifies the offending edge and
its endpoints or lag. It checks the original graph before surgery, projection,
counterfactual or selection graph construction, PAG identification policy, AST
rewriting and no-op requests. Removing the offending relation during a later
transformation cannot make the original input admitted.

The endpoint-inspection and orientation utilities retain their structural use.
Reading undirected edges, testing adjacency, inspecting resolved directed paths,
or applying PAG orientation rules does not establish causal identification for
an unresolved graph. A completed graph must satisfy the static profile before
entering these causal consumers. Static primitives do not choose a completion or
treat a compact temporal relation as a contemporaneous arrow.

## Consumer migration

Callers that previously received an empty rewrite, an independence result, or
an identified expression after uncertain relations were ignored must handle the
profile refusal. Report the unsupported input or retain a limited result until
an appropriately supported graph is supplied. Do not catch the exception and
retry after deleting relations. A temporal consumer or an explicitly specified
time-expanded graph must supply the temporal interpretation.

Known reverse-stored arrows are normalized consistently in adjacency, incoming
and outgoing surgery, condensed graphs and counterfactual world construction.
The published source graph remains unchanged. Existing immutable graph row
preparation and detached tuple/plain-dictionary consumer values retain their
own contract; this change does not introduce an IR schema or public facade.

## Evidence and limits

`test_admg_profile_consumers.py` exercises the actual graph, Rule 1–3, sigma,
ID/IDC, ID*/IDC*, transport, CTF and AMN entry points, including no-op requests.
The known fork, collider and conditioned-descendant examples distinguish open
and blocked paths at the Rule consumers. Ordinary IDC invokes two ID calls and
forms their ratio; it is not described as a direct separator caller. IDC* uses
the actual separator, whose finite returned queries are compared with an
independent latent-DAG ancestral moralization oracle.

The independent complete three-node ADMG oracle remains a separate finite
synthetic property check. Real two-node bow controls retain non-identification
through SID and conditional-ID. Disjoint AMN queries compare the actual derived
graph against independent moralization. These checks do not establish universal
ID, PAG-completion, counterfactual or transport completeness, a real-data effect,
or scientific authority for production admission.
