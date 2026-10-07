# Static graph consumer fixtures

These tests exercise finite supported static graphs through the maintained
SID, conditional-ID, AMN and estimand compiler consumers. They do not change
the graph algorithms, IR versions or public exports.

## A latent bow and an observed collider are different graphs

The bow has two observed nodes and both relations `X→Y` and `X↔Y`. Its latent
expansion adds a hidden parent of X and Y. SID and conditional-ID must return
a hedge for this example, with the native hedge certificate and proof step.

The former fixture instead encoded `X↔U↔Y` and `X→Y`, making U an observed
collider. After removing the outgoing effect of X, that path is closed without
conditions and open when U is conditioned. This graph remains a separate
identified positive control; it is not renamed into a hidden common cause.

An independent nonidentification example uses independent standard Gaussian
U and E, `X=U`, and `Y=βX+γU+E`. The pairs `(β,γ)=(1/2,1/2)` and
`(3/2,−1/2)` have identical, nonsingular observed covariance
`[[1,1],[1,2]]`, while `E[Y|do(X=1)]` equals 1/2 and 3/2 respectively.
Both structural coefficients are nonzero. Observational data cannot determine
which intervention law holds in this bow.

## AMN separation uses disjoint query sets

The cross-world fixture uses a shared `U→X→Y` chain with no direct `U→Y`
edge. The maintained AMN builder also adds the bidirected X bridge between
worlds. `X__w0` and `Y__w1` are dependent without conditions and separated
given `X__w1`. That condition is distinct from both queried endpoints.

The reference expands the bridge into its own latent common cause and uses
ancestral moralization. A separate Gaussian realization gives
`Cov(X0,Y1|X1)=2−2·3/3=0`. This checks the derived graph's separation law;
it does not identify the builder's numeric counterfactual or intervention SEM.
Fork, collider and conditioned-descendant cases supply opposite controls.
The former query conditioned on its own Y endpoint and remains an explicit
false result outside the supported disjoint-query domain.

## Compiler fixtures must execute the pre-pass

The compiler fixture constructs typed `CausalEdge` objects directly. The graph
is `T→Y` with isolated Z, and the adjustment AST is
`Σ_Z P(Y|T,Z)P(Z)`. Rule 1 therefore removes Z from the outcome factor before
compilation. The tests observe the real rewriter, its changed AST and the exact
proof transferred into the ExecutorGraph, including the ordering before an
existing manual proof. Constructor errors fail the test rather than turning
into backend-unavailable skips.

The pre-pass removal control keeps the callable and graph/AST markers but
returns the unchanged AST and no steps. The consumer test must fail. The
historical three failed fixtures and two constructor-induced skips remain in
the receipt as original observations, not passing results or an inherited-red
claim. These checks do not establish general ID completeness, arbitrary
PAG/CPDAG support or causal authority on admitted real data.
