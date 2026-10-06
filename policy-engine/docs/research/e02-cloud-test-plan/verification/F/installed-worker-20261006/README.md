# Installed selected-worker profile verification

The standalone `workers/dowhy-014` directory remains the canonical owner of the
six selected production assets. Hatch projects those exact files into the
wheel's private `causal/_dowhy_profile` directory. The sdist retains their
canonical source paths so rebuilding the wheel uses the same mapping. This
adds no application dependency, Python marker exception or second worker
implementation. The configured absolute Python 3.12 interpreter supplies the
locked external dependencies; the executed script and protocol come from the
installed product.

`test_installed_worker_profile.py` runs under Python isolated mode in a neutral
consumer directory against an owned wheel install and a separate install rebuilt
from the sdist. Its environment explicitly supplies the frozen native fixture
paths, the six-asset source hash manifest and the selected worker interpreter.
These test carriers come from immutable Git blobs; product imports must come
from the owned installed site. Read-only third-party dependencies are reused,
so this proves product-installation isolation rather than an independent full
dependency rebuild.

The actual MethodJob resolves synthetic observational input through CAS, invokes
real DoWhy, persists its result and execution evidence, and reopens them in a
fresh installed Python 3.14 reader. The public pure report factory executes in
the real producer and reproduces the complete typed report, including absent
p-values. The existing dematerializer projects the actual typed report into its
declared slot. Raw dispatcher key warnings are retained as diagnostics; they
alone do not establish loss at the canonical slot consumer.

The GCM companion invokes the frozen owner's genuine GCM MethodJob, fitted
source/row oracle, fresh model reader and actual Scientist query consumer with
40 refits. All four governed Foundry helper exports retain canonical object
identity and pickle FQNs through the root and methods compatibility facades.
The actual helpers validate the reopened worker/model/interval inputs. Its
synthetic estimator interval remains non-gate-eligible.

A missing-profile red run retains the helper identities while both real method
consumers fail. After packaging, temporarily retiring `worker.py` in only the
owned installed environment makes the fresh persisted reader raise typed
unavailability while the original CAS reply bytes and version/hash declarations
remain unchanged. Restoration is checked by exact bytes and another fresh
reader. Archive/source and installed byte denominators are independently walked
and recorded in the handoff.

These are bounded engineering and known-DGP numerical witnesses. They do not
admit real-data causal assumptions, scientific authority or a production
Scientist evaluation. Primary CAU/SCM/API finding owners retain their decisions.
Application Python 3.14 DoWhy/EconML exclusions remain UNRUN; the selected Python
3.12 profile is a distinct explicitly authorized computation boundary.
