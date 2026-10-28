# LA-017: bounded observable Lex control repair

This is a test-and-evidence change for `LA-017@LEX-01`, canonical pointer
`#/findings/241/criterion_refs/0`, originally specified in
`docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md:540-570`
at `d9397c7c0458ec2980fa58115c5ee597eb58dbc8`. It tests norm-difference
persistence, report readers, impact-topic descriptions and comparison boundaries;
it makes no claim of measured policy effects, law, issuer, production currentness,
or G acceptance. The historical ledger says `partial`; Appendix C separately
records a `closed_bounded` boundary. Current formal closure is not adjudicated.

## Repaired property and actual observations

The earlier C95 wrapper accepted any `AssertionError` as a successful removal,
including an unrelated setup or regex assertion. Its nine wrapper passes and six
selected test passes are observed XML results, not qualified current-source semantic
controls: the required per-phase process, source, plugin and deciding-output bytes
were not delivered. The historical receipt also names one implementation file but
its managed snapshot contains seven paths; its `closure_ids` field is not a G
closure. Preserve the original bytes and append a separate qualification with
`closure_ids: []`. Its install log names the unavailable `psutil==7.2.1` tunnel,
which must not be relabelled as a product failure.

The replacement test shares one semantic predicate across before/removal/restored
phases and separately requires an exact, mode-specific observation that explains
why removal caused the red. Each parameter uses its own pytest process; its three
phases use the same PID, equal synthetic inputs, separate CAS roots and restored
patch contexts. It records source and callable/code identities, active invocations,
phase inputs and errors before the final assertions. Four scenarios exercise the
same `_reconcile_selected_report` owner; they are distinct properties of one
mechanism, not four independent mechanisms.

The scope guard first persists and reopens a valid same-jurisdiction legacy 1.0
report. It then calls the selected 1.1 producer across jurisdictions. Before and
after removal, the target call must refuse with exactly
`selected_report_jurisdiction_mismatch` and reach no `FileSystemCAS.put_json`.
With the unique guard predicate removed, the observer requires actual calls to
`put_json` for both `lex.norm_diff` and `lex.norm_impact_report` in that process.
A wrong exception, a failed legacy setup, an empty write trace or a marker-only
mutation cannot qualify the removal. The writer spy patches the class method only
inside the call and verifies restoration of the actual unbound method.

The forged reports used for manifest and reconciliation controls are based on the
freshly reopened persisted report, whose payload contains no CAS self-reference;
otherwise the reader rejects before reaching the intended property. The removed
bridge is expected to cause `report_norm_diff_input_mismatch`, because the selected
diff remains present while its manifest edge is absent.

A narrow local RAW-path `scope_guard` smoke was run at source commit
`5e75fa8a543a08acddec6664066daeaaaf32969e`, tree
`cb339cf976d4bbb35978e5aefe4715e6aa60c3f9`, using test postimage SHA-256
`ad52d8b2a83b4cf3185b298a75fdefaf322cdac358cefe1c2d28bb70c4dccfaa`.
One process (PID 21175) completed in 7.24 s with sampled peak tree RSS
314,605,568 bytes and no resource abort. The real before/removal/restored trace
showed legacy reopen, two refusals before any write and, in the removal phase,
both real write calls. The retained finite project Python readset had 286 paths;
all 286 matched that commit. The isolated sandbox denied network and production
reads. The RAW test was outside the canonical test tree, so the product
`tests/conftest.py` was supplied explicitly as a plugin. This supports only the
named RAW-path smoke; it is not a canonical-composed test PASS or G acceptance.
The other eight removal scenarios and the six selectors are UNRUN in this repair.
The seven compressed deciding outputs are retained beside this document under
`evidence/c95-scope-smoke-20261028/`: full stdout/stderr, JUnit, source freeze,
resource result, Git readback and actual readset. The uncompressed stdout SHA-256
is `90d8342f937fb543840cf314826f0065b495762f829f7155970b1a5769c3a8ab`;
Git readback SHA-256 is
`86505d168459663bcaa428d9497ed639087c97cc7da74455679ebe337f5b4f10`.
They must be delivered and checked as bytes with this change; a local ignored
path and hash alone would not be delivered evidence.

## Execution after source composition

The tracked `tests/unit/remediation/e02_lex_triplet_runner.py` is the exact
launcher input. First verify the actual immutable admitted source commit/tree,
its complete changed footprint and the target test and runner bytes. `work`, a
detached HEAD and no `origin` are acceptable when identities agree. A mismatch
is an ERROR/UNRUN; record actual identities and stop without checkout repair.

Inspect and reuse the existing supported Python environment. For a fresh Cloud
checkout only, if the required locked dependencies are missing, use the documented
supported bootstrap or `uv sync --frozen --extra test`, retain setup output, and
report unavailable packages/network as ERROR/UNRUN. Never transfer production
payloads, credentials, private RAW, CAS or databases to Cloud.

Measure VM total and free disk, available RAM and CPU separately. The runner
admits at least 4 GiB free disk, chooses one-process RSS cap no larger than 2 GiB
or half reported `MemAvailable` unless an explicitly measured
`C95_RSS_CAP_BYTES` is supplied, and stops later cases after a resource abort. Its
2 GiB disk floor, 600 s per command and one numerical thread are initial guards,
not assumptions about a 32 GB VM's free disk or RAM. Where RSS/available RAM
cannot be observed, report that limitation; a measured explicit cap is required.

From `policy-engine/`, set `C95_EXPECTED_COMMIT` and `C95_EXPECTED_TREE` to the
actual published task base, and `C95_OUTPUT_DIR` to a new absolute output path:

```sh
C95_EXPECTED_COMMIT=<full-admitted-commit> \
C95_EXPECTED_TREE=<full-admitted-tree> \
C95_OUTPUT_DIR=<new-absolute-output-directory> \
.venv/bin/python -B tests/unit/remediation/e02_lex_triplet_runner.py
```

The runner executes the six explicit F17 selectors followed by nine individually
selected triplets, each in a fresh process. A failure in one property does not
make another property disappear; an actual resource abort stops the remaining
commands and marks them UNRUN. Default pytest plugin autoload and repository
configuration remain in effect. The launcher records exact argv, profiles,
backend versions, resources, process PID, selected test/owner/conftest/config
pins, finite imported project Python readset, JUnit and full stdout/stderr; it
checks those source bytes against the actual admitted Git tree. This readset does
not cover all parser inputs, dynamically executed code, external/compiled
modules or descendants. Reconcile reported phase records, callable observations,
source readbacks and command outcomes independently; exit status alone does not
establish a semantic property or distinguish a setup failure from a product defect.

Deliver the product/test changes, necessary companions and small receipt first.
Retain full deciding command outputs and removal traces in lossless compressed
form with the JUnit, source/profile and environment bindings. A local or Cloud
ignored path and hash are not delivered bytes. Use the available managed diff or
another real transfer channel for required bytes; if unavailable, state exactly
which evidence is unavailable and the smallest property-specific replay required.
Do not deliver checkout copies, environments, dependencies or transient CAS.

## Pattern and remaining boundaries

P29/P32/P33/P38: check the actual property, not merely a marker, exit code or
exception category; an early unexpected refusal and a missing write are explicit
falsifiers. P07: retain report/schema/profile and input identities. P14: four
reconciliation controls share an owner. The current bounded state remains
`verification_missing` and `semantic_test_missing` for the full canonical
cohort. Caller/corpus tracing over the compatibility window and a complete
identical-policy-versus-changed-policy downstream comparison are separate and
UNRUN. Author result, independent review, composed-source checks and eventual G
acceptance are separate steps.
