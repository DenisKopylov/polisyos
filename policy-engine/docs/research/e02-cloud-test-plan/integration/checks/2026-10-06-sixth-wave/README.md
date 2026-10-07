# Deciding G outputs, 2026-10-06 sixth intake

The accepted A source is `577521c6651bba048d6bdfdc13f36a383c8146c6`, tree
`1e8820533c48ec88355f2a2fccba486f279c2a4b`, ordinary merge
`9c989f7877bd25fea38416cbd10d4c8b2511d10e`. This is one installed-wheel test
and fourteen handoff/evidence companions, with no production-source changes.
All fifteen candidate blobs were read back unchanged after merge; the three
original commits remain in ancestry. Code acceptance does not close REQ-01.

`A-compiler/replay-4/` retains the complete exact-selector stdout/stderr,
JUnit, command/environment, persisted compiler report and execution receipt.
Result: 1 PASS, 0 FAIL/ERROR/SKIP; 3.175 seconds JUnit, 4.662 seconds wall.
The real installed compiler uses a RecordingResolver fixture and persists its
report; an unknown family refuses without resolver queries or emitted specs.
The child runs outside the checkout, from a freshly built wheel and fresh venv.
All 3143 `.py` ZIP entries match exact candidate Git bytes. The separate 2698
count is installed `polisyos` package files, not loaded modules or test cases.
The wheel hash is `c1d20a264ced1691f0cdfdf89c5727bc152269a989be40ba352357d9abab8f27`.
Production resolver/source admission, external dynamic callers and a composed
G wheel remain unestablished; LA-045 limited/partial and LA-046 partial are unchanged.

Earlier attempts are preserved. Attempt 1 stdout/JUnit are retained byte-exact
in `attempt-1/lossless-output-capture.json` because their unescaped whitespace
failed the Git whitespace gate; decoding its strings restores both hashes.
Attempt 1 could not resolve Hatchling in the
active offline cache and never reached the property. Replays 2/3 were interrupted
by harness storage caps after a healthy build, before the child property.
They are prerequisite/harness UNRUN, not product FAIL. Replay 4 used the same
selector with a hash-pinned local build index, `UV_OFFLINE=1`, `UV_NO_CACHE=1`,
a separate 100 MiB source cap and 500 MiB generated cap. Generated allocation
peaked at 293347328 bytes. Build packages were reconstructed from locally
content-verified RECORD files: their archive hashes differ from upstream wheel
containers, as `build-inputs.json` explicitly records. There was no network
dependency installation or global cache/environment write. Initial Ruff on an
ignored copy had wrong test-profile discovery; the actual canonical test path
and configuration subsequently passed Ruff, with the exact same Git blob.
The JUnit `record_property`/xunit2 warning is retained and is nonfailing.

`C-BERL/` records two independent numerical falsifiers of source
`87999f69c5f99d69ee2622ef00cd7f4e04d7d572`, tree
`0280403e6837c5b220ac748a7674f4e5830ba0ab`. Decimal-scale conditioning
should yield mean/variance `0.1/0`, but yields `0/1`. Ordinary full-rank and
singular positives and off-support refusal controls pass. The second witness
uses exact binary powers: `s=2^-35`, `x1=s*x3`, independent `x2`, observation
`x1=s/8`; its observed block `diag(s²,1)` is SPD. Expected `0.125/0`, actual
`0/1`. This is the same rank/support class, with a distinguishing scale variant.
The runner exit 0 means the falsifier reproduced; the product property FAILs.

These C probes import three verified Git implementation modules through three
empty namespace stubs. They establish the numerical primitive failure, not
normal package initialization, public adapter, Runtime/CAS or Phase 5 behavior.
They used existing Python 3.14.3 / NumPy 2.3.5, about 35 MiB RSS and under
0.15 seconds each. Scripts are retained as `.py.txt` evidence, not maintained
production tools. Execution records omit their redundant embedded stdout copy;
the full stdout bytes are retained once and rehashed. Literal newline suffixes
from receipt writers were repaired/parsing-qualified without product reruns.

No production payload, source archive, wheel, virtual environment or full
derived source census is committed here. Source closures are cited by Git SHA;
unique deciding reports and complete moderate outputs are retained. No broad
regression or data-dependent closeout was run. `main` remains outside scope.
