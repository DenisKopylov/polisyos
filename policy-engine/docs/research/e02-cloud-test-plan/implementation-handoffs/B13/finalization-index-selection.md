# B13 terminal workflow selection

The run index formerly picked the first `scientist.experiment_state` and
`scientist.workflow_report` among manifest outputs. The synchronous workflow
executor records a prior state before its final state, so kind and output order do
not identify the terminal finalizer's selection. That prior state also omits the
finalizer's Research DAG/report bindings. The terminal event's exact selected
`WorkflowStateFinalization` ref is the existing owner coordinate.

For an owner-bound modern terminal workflow, the adapter now reopens the strict
terminal Core source, then bounded-reads its selected finalization, workflow spec,
prior state, final state and report. It reconciles run/workflow identity, expected
schemas and selected artifact profiles, exact owner input/output membership,
unique permitted output paths, and the final state's actual bound refs. It returns
both final state and bound report together. An unavailable or inconsistent modern
selection yields neither ref and a `core_run_workflow_finalization_unavailable`
warning; it never falls back to an earlier same-kind output. A distinct unselected
finalization or earlier report remains historical, not the selected value.

Legacy terminal records with neither terminal input nor finalization output keep
their historical index projection with
`core_run_workflow_finalization_not_established`; the SimulationResult debug
candidate also carries that limitation. Nonterminal history remains unpromoted.
The exact selected views are read under the existing store's access checks. A
conflicting tenant manifest is refused; if a scoped run's selected artifact
manifest omits tenant metadata, a separate limitation is returned rather than
claiming independent manifest-level tenant attestation. The candidate reader
still performs its own tenant/CAS/schema admission.

The bounded reader spends a shared aggregate 8 MiB across at most five selected
JSON reads, each with 64 KiB manifest, depth 64 and 200,000-element limits. Budget,
backend or permission refusal is an unavailable selection, not a product PASS. No
fallback to an unbounded reader is made. This is a bounded output-selection bridge;
it is not an independent proof of the entire prior→final transition and does not
establish a complete actual consumed source basis, durable source event head or
currentness. Those remain separate G27-02 work; prior source/history is preserved.

The `test_terminal_workflow_index.py` owner tests build real RunContext traces,
including prior/final permutations, an earlier same-kind report and two distinct
finalization outputs. The real WorkflowExecutor/DAG witness additionally checks
the index against its actual owner finalization. The RES-03 served ref-removal
negative uses a verified replacement state and an explicitly substituted index
selection; it does not itself prove that such a state was committed by the run
owner. All are authored tests until their native outputs are retained. Neither a
source review nor a test patch grants G acceptance or formal B13 closure.

Pattern pass: P29 checks a real selection and a prior-state substitution, not
markers; P31 moves selection to the shared run-index adapter; P32/P37 content-bind
selected artifacts and disclose limits; P38 distinguishes first-by-kind from the
owner's selected state; P40 retains source-event/readset completeness as the same
separate declared residual.
