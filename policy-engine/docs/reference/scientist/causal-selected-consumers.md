# Selected causal method consumers

`RunCausalEvaluationNode` checks evaluation admission before starting its primary
causal job. A resolved numerical source and a successful backend call do not grant
evaluation permission or establish that real-world identification assumptions
hold. Synthetic backend receipts exercise the numerical bridge separately.

Before admission, the consumer resolves every actual top-level causal input
through the exact typed Core CAS view. It recomputes the byte digest and checks
manifest identity, kind, media type, integrity and size. The optional staged
contract, bundle and intake receipt form a complete three-reference set. Missing,
extra or duplicated offered input identities cannot reach the verifier or job.
This profile projects the verified byte digest into the PDC input hash; it does
not infer a semantic hash from an arbitrary payload field. A source owner using
a distinct semantic content hash must supply its supported resolver contract.

Binding tests are `test_causal_input_byte_binding.py` beside the node tests.
They use actual persisted CAS sources for input identity and untrusted contexts
only for refusal controls. They do not demonstrate a lawful positive admission.
That replay requires the source owner's typed manifest/bytes/projection and the
Runtime owner's current intake, revision lineage, appointed verifier and context;
the consumer creates its own fresh challenge.

The primary job includes the actual observational artifact in its input lineage.
The selected DoWhy profile runs the pinned Python 3.12 worker through the existing
method runner while the application remains Python 3.14. The parent resolves the
source, validates the primitive response, reads the persisted method artifact,
and reconciles its complete consumed report and uncertainty projection. A
consistent replacement of both the peer report and stored report must still
agree with the canonical producer projection of the validated worker result.
Point-only results retain their unavailable interval and cannot acquire an
eligible confidence envelope through this bridge.

The selected staggered DiD consumer recomputes the fixed participation target
using both its materialized input and the actual source artifact. It reconciles
the typed peer report and derived envelope against the persisted method result.
This establishes input and output identity; its scientific interval remains
limited to the declared independent-unit profile.

The defining numerical tests are
`tests/unit/scientist/nodes/builtins/simulate/test_causal_selected_consumers.py`.
They run genuine method jobs and CAS readers, compare the DoWhy interval against
independent OLS, and preserve real source/backend markers while changing consumed
quantities. The same file checks that a node lacking evaluation admission refuses
execution. A production-authority success requires the existing grounded inputs
and admission verifier; its local replay belongs to G.

For the target and scientific profile, see
[causal statistical validity](../foundry/causal-statistical-validity.md).
