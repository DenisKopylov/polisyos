# Independent review: generic handoff `DesignProblem` runtime binding

**Verdict: GO for this one-line candidate fix; no formal closure proposed.**

Scope is limited to `policy-engine/src/polisyos/runtime/http/services/control/job_nl_admission.py`. The exact preimage/postimage pair recorded in `LOCAL/raw/root-canonical-import-fixes-v2-20261011/readback.json` is SHA-256 `5ec43db02a16518fc3276f12ae669c525a5bfcde29f01fc6f776f8c6f715a94a` → `5f916a063b1a306c0b81625bc1be9265fc8941ead387ae2a13cfe7ea80f37ff8`. I verified that the saved `before/` source has the preimage hash and that its complete diff to the current file is exactly one addition: a local import of `DesignProblem` in the configured generic-owner branch, before the nested handoff/currentness closures.

The module-level `DesignProblem` import is guarded by `TYPE_CHECKING`, so it does not bind the name at runtime. The currentness closure uses `type(problem) is DesignProblem`; without the new enclosing-function local import that lookup has no runtime binding and can raise `NameError` when the callback is invoked. The new import executes before either closure is defined, only in the branch that also establishes the typed configured owner, issued worker scope, root profile, and context owner. It keeps the import lazy and avoids adding a module-level dependency.

The closure binding is consistent with the existing consumer contract: the handoff resolver stores the exact typed handoff and problem; currentness rejects absent or wrong-typed entries, resolves the persisted handoff under the same verified scope/context owner, compares the replayed handoff, and re-resolves the optional child family. The lifecycle passes this callback into `GenerationCycle`; the generic path checks it before and after N5 work and treats false currentness as refusal/limitation. This review does not establish the broader N5 route or its authority claims.

**Evidence:** exact before/current source diff and hashes; source inspection of the closure and `GenerationCycle` consumers; canonical Ruff command from `policy-engine/`, `.venv/bin/python -m ruff check --config ruff.toml src/polisyos/runtime/http/services/control/job_nl_admission.py` → exit 0, `All checks passed!`.

**Limit:** no runtime integration test was run in this review. A composed consumer replay remains necessary to demonstrate that the callback is invoked on the actual route and no longer fails at runtime; this note is not that receipt and does not inherit the broader source's status.
