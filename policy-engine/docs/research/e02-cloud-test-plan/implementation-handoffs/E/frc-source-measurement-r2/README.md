# FRC source measurement and A packet

B32 and LA-051 keep their committed `partial` ledger status. This slice repairs
E source/schema/unit binding and supplies a real predictive CAS witness for A;
code admission and accountable FRC-02 closure remain separate.

New configured ETS execution uses internal request schema `2.0`, explicit
`target_unit` and `target_scale="source_native"`, and a canonical
`fabric.data_schema` reference in the source `DataSnapshot`. The producer loads
and validates the complete Fabric `DataSchema` before ETS; the shared neutral
coordinate reader content-binds field identity, unit, numeric type and decimal
storage scale. It does not infer units from MetricKey or apply unit conversion.
The binding is retained in training, forecasting bundle, evidence role artifacts
and report lineage. The fresh candidate reader re-resolves this basis, ordered
source rows, persisted intervals, split/horizon, rule, seed and six times.
Historical v1 request/evidence read/replay is preserved, while new execution
refuses unresolved or absent measurement inputs. Public IR semantics do not change.

The independent oracle reads held-out source values and forecasting intervals
from separate reopened CAS refs. For the exact linear training fixture,
Holt predicts 31,32,33,34 and every rolling-origin residual is zero, hence
bounds are `[31,31]`, `[32,32]`, `[33,33]`, `[34,34]` independently of the
BacktestReport comparison loop. The all-hit and all-miss sources produce 4/4
and 0/4 empirical hits despite identical training and point forecasts.

`a-cas-contract-tests.py.txt` is an applicable test packet for A's existing
resolver/gateway/buildrecord path. Copy it to an A-owned test path and run from
`policy-engine`. It uses the real configured ETS producer, persisted refs and
fresh canonical loader with valid six-role ordering, preserving predictive
purpose denials. Its bounded positive is not an admitted issuer/profile or
production/default/HTTP witness. The missing/wrong-kind/bad-time/wrong-rule
variants remain refusals. The old FRC01 fake mapping/time fixture must become a
negative or be replaced by this positive, never made acceptable by a fallback.

`a-status-reason.patch.txt` is a small reviewable patch against the exact A
source at the slice base. `a-status-reason-tests.py.txt` reproduces two distinct
A residues: missing empirical ref must produce the named missing-ref reason
through both tier and S6; resolved limited evidence must preserve the actual
`calibration_floor_not_met` reason. It is not an unconditional
`insufficient-history` assertion. E does not apply this patch to A shared files.
A reviews/applies it and checks its existing FRC01 expectations at the same time.

`ForecastOwnerResult.to_s10_input_fields(store)` reopens the candidate and
adapts the producer refs to A's `empirical_calibration_evidence_ref`, candidate
ref, `expected_rule_version_ref` and typed temporal roles. Its result preserves
`verifier_provenance="not_established"`; A independently selects/verifies an
admitted profile and source in configured CAS. Next A result: default route
calls the strict producer before terminal causal refusal, its own verifier
recomputes source/metric/unit/split/horizon/rows/pairs/counts/threshold/purpose/
six roles, and fresh served/HTTP read binds the same refs and verifier origin.

G's remaining local recipe is read-only on the exact implementation SHA:
provide a minimal immutable issued-forecast/outcome history for a declared
compatible predictive estimand, resolved DataSchema/units, source/model/rule
versions, split/horizon and six distinct actual times; run the same producer
and reader, change only later outcome rows and check the measured result.
Full production history remains local. Synthetic inputs prove generic numerical
and wiring properties only; they do not establish source authority or history.

P37 basis: mathematical bounds and byte/coordinate/pair reconciliation are
`recomputed`; the known analytic oracle is independently derived. Institutional
source/profile admission and independent A verifier provenance are
`not_established`. The latter cannot make the E candidate gating. P40 widens
source binding to schema/units at the shared producer/readback boundary; it does
not add a sibling forecast or calibration engine. P41 attribution of the old
FRC01 reds stays `not_established`; the packet is bounded deciding evidence,
not a claim that both historical FAILs were A production regressions.

Cloud has no native Trash. After receipts and absence of active users, cleanup
candidates are the exact reusable CAS/test directories under the cited r2 FRC
scratch root. Keep code, this packet, unique outputs and history; do not delete
fixtures permanently or empty Trash.
