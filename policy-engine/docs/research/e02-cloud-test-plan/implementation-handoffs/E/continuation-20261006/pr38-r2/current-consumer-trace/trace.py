"Read-only exact source/evidence joins. No product execution or new code verdict."

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-continuation-20261006")
OUT = Path(__file__).parent
CURRENT = "a9f78817c873be5b35a08155f2593b229d9fdbb6"
TREE = "c02e043c3e1c8222c28aa71187fa8db4e2fdeea7"
E = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/"
P = E + "continuation-20261006/pr38-r2/"


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*argv: object) -> object:
    _admit_git_object_arguments(argv)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(ROOT), *argv])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def blob(sha: str, path: object) -> object:
    return git("show", sha + ":" + path)


def sha256(data: object) -> str:
    return hashlib.sha256(data).hexdigest()


if not (git("rev-parse", CURRENT + "^{tree}").decode().strip() == TREE):
    raise AssertionError
source_groups = {
    "BKT": (
        "0983d064df3c3e21f8b1accff4ee90484d78973b",
        [
            "scientist/methods/backtesting/native_replay.py",
            "scientist/methods/backtesting/orchestrator.py",
            "scientist/nodes/builtins/simulate/run_simulation.py",
            "scientist/methods/backtesting/plan.py",
            "scientist/methods/backtesting/evaluator.py",
            "ir/analytics/backtest.py",
        ],
    ),
    "PCL": (
        "74b26eb067dea76d90b134641e66537759e4dc0f",
        [
            "foundry/execute/_internal/graph/__init__.py",
            "foundry/methods/backends/numpy_runner.py",
            "foundry/methods/catalog/econometrics/advanced.py",
            "calibration/continuous.py",
        ],
    ),
    "FRC": (
        "8486baad6fdef8063cfaad80b15f6b6d8532460a",
        [
            "scientist/methods/backtesting/forecast_owner.py",
            "calibration/forecast_bridge.py",
            "foundry/methods/catalog/forecasting/advanced.py",
            "runtime/quality/generation_cycle.py",
        ],
    ),
}
joins = []
for family, (review_source, paths) in source_groups.items():
    for path in paths:
        path = "policy-engine/src/polisyos/" + path
        old = blob(review_source, path)
        now = blob(CURRENT, path)
        if not (old == now):
            raise AssertionError(path)
        joins.append(
            {
                "family": family,
                "path": path,
                "review_source": review_source,
                "current_source": CURRENT,
                "review_blob": git("rev-parse", review_source + ":" + path).decode().strip(),
                "current_blob": git("rev-parse", CURRENT + ":" + path).decode().strip(),
                "sha256": sha256(now),
                "bytes": len(now),
                "exact_bytes_unchanged": True,
            }
        )
(OUT / "mechanism-blob-joins.json").write_text(json.dumps(joins, indent=2) + "\n")
reviews = {
    "BKT": E + "backtest-native-chain-admission-r2-checks/independent-review-go-0983.json",
    "PCL": P + "independent-reviews/pcl/review.json",
    "FRC": P + "independent-reviews/frc/frc-independent-review-8486.json",
}
review_data = {}
review_inputs = []
dest = OUT / "authoritative-reviews"
dest.mkdir(exist_ok=True)
for family, path in reviews.items():
    raw = blob(CURRENT, path)
    review_data[family] = json.loads(raw)
    local = dest / (family.lower() + ".json")
    local.write_bytes(raw)
    review_inputs.append(
        {
            "family": family,
            "tracked_path": path,
            "current_git_blob": git("rev-parse", CURRENT + ":" + path).decode().strip(),
            "sha256": sha256(raw),
            "bytes": len(raw),
            "packet_copy": str(local.relative_to(OUT)),
            "authority": (
                "Existing independent review owns its ori"
                "ginal bounded judgment; this trace autho"
                "r does not re-review own BKT/facade code"
                "."
            ),
        }
    )
# Original committed receipts carry native witnesses; this task does no CAS producer/backend replay.
bkt_path = E + ("backtest-native-default-replay-r2-checks/backtest-native-deciding-evidence.json")
bkt_raw = blob(CURRENT, bkt_path)
bkt = json.loads(bkt_raw)
seven = bkt["generic_native_reports"][1]
report = seven["report_payload"]
scenarios = report["scenarios"]
counts = report["metadata"]["replay_denominators"][0]
if not (
    counts["requested"] == counts["attempted"] == counts["completed"] == 7 and counts["failed"] == 0
):
    raise AssertionError
seeds = [row["metadata"]["actual_foundry_seed"] for row in scenarios]
run_ids = [row["metadata"]["backend_run_id"] for row in scenarios]
if not (len(set(seeds)) == len(set(run_ids)) == 7):
    raise AssertionError
if not (
    report["metadata"]["comparison_denominator"]
    == {
        "basis": "recomputed",
        "eligible": 14,
        "observed": 14,
        "requested": 14,
        "unit": "metric_time_cell_per_replay",
    }
):
    raise AssertionError
k7 = {
    "original_tracked_evidence": bkt_path,
    "original_git_blob": git("rev-parse", CURRENT + ":" + bkt_path).decode().strip(),
    "original_sha256": sha256(bkt_raw),
    "original_numerical_candidate": bkt["numerical_candidate_sha"],
    "original_import_only_readback": bkt["readback_after_import_only_sha"],
    "report_artifact_id": seven["report_artifact_id"],
    "replay_counts": counts,
    "comparison_counts": report["metadata"]["comparison_denominator"],
    "actual_foundry_seeds": seeds,
    "actual_run_ids": run_ids,
    "scenarios": [
        {
            "scenario_id": row["scenario_id"],
            "predictions": row["outcome_comparisons"],
            "metadata": row["metadata"],
            "compared_count": row["compared_count"],
            "requested_count": row["requested_count"],
            "source": row["data_source"],
        }
        for row in scenarios
    ],
    "evidence_scope": (
        "Previously executed generic native K7 witness, original repo"
        "rt reopened fresh; not a new execution or production history"
        ". Exact current producer/native reader/report source blobs j"
        "oin reviewed0983; independent fixed-reader K3 evidence is se"
        "parate review input."
    ),
}
(OUT / "native-k7-carried-witness.json").write_text(json.dumps(k7, indent=2) + "\n")
pcl = review_data["PCL"]["runtime_property"]
frc = review_data["FRC"]
(OUT / "pcl-carried-witness.json").write_text(
    json.dumps(
        {
            "review_input": reviews["PCL"],
            "runtime_property": pcl,
            "distinct_sites": 3,
            "actual_calls": 5,
            "distinct_diagnostics_refs": 5,
            "derived_roles": 6,
            "alias_note": (
                "proposed_profile_break_garch aliases overall; never count it"
                " as a separate independent computation."
            ),
            "scope": (
                "Existing independent actual configured g"
                "raph/arch/NumPy execution and fresh pair"
                "s reader; no native rerun in this trace."
            ),
        },
        indent=2,
    )
    + "\n"
)
(OUT / "frc-carried-witness.json").write_text(
    json.dumps(
        {
            "review_input": reviews["FRC"],
            "original_source": frc["reviewed_source"],
            "scope": frc["scope"],
            "verification": frc["verification"],
            "negative_controls": frc["negative_controls"],
            "residuals": frc["residuals"],
            "finding_closure_claim": frc["finding_closure_claim"],
            "scope_note": (
                "Current producer/bridge/ETS method/A con"
                "sumer blobs identical to independent8486"
                " source; retain original20+32+5bounded P"
                "ASS and two A status-reason failures as "
                "historical deciding evidence. No new cur"
                "rent numerical/backend/served run."
            ),
        },
        indent=2,
    )
    + "\n"
)
# Actual Git semantics plus frozen expected-candidate predicate for a present, valid, stale
# recipe SHA.
recipe = {
    "schema": "policyos.e02.local_readonly_recipe_binding.v1",
    "implementation_sha": CURRENT,
    "implementation_tree": TREE,
    "source_packet_sha256": sha256((OUT / "mechanism-blob-joins.json").read_bytes()),
    "unit": "E",
    "mode": "local_read_only_exact_candidate",
}


def admit_recipe(value: object) -> dict[str, object]:
    resolved = git("rev-parse", value["implementation_sha"] + "^{commit}").decode().strip()
    if resolved != CURRENT:
        raise ValueError("recipe implementation SHA differs from exact frozen consumer source")
    tree = git("rev-parse", resolved + "^{tree}").decode().strip()
    if value["implementation_tree"] != tree:
        raise ValueError("recipe tree differs from exact implementation tree")
    if value["source_packet_sha256"] != sha256((OUT / "mechanism-blob-joins.json").read_bytes()):
        raise ValueError("recipe source-packet digest mismatch")
    return {"resolved_sha": resolved, "tree": tree, "admission": "PASS_exact_source_binding_only"}


positive = admit_recipe(recipe)
fake = dict(recipe, implementation_sha="9c51a7f7e0a7fc901a681b2fba6240b8cbcf7cef")
error = None
try:
    admit_recipe(fake)
except ValueError as exc:
    error = str(exc)
if not (error == "recipe implementation SHA differs from exact frozen consumer source"):
    raise AssertionError
control = {
    "schema": "policyos.e02.local_recipe_present_stale_source_negative.v1",
    "positive": positive,
    "fake_recipe": fake,
    "fake_SHA_is_real_existing_commit": True,
    "fake_native_source_blob": git(
        "rev-parse",
        fake["implementation_sha"]
        + (":policy-engine/src/polisyos/scientist/methods/backtesting/native_replay.py"),
    )
    .decode()
    .strip(),
    "current_native_source_blob": git(
        "rev-parse",
        CURRENT + (":policy-engine/src/polisyos/scientist/methods/backtesting/native_replay.py"),
    )
    .decode()
    .strip(),
    "refusal": error,
    "outcome": "EXPECTED_REFUSE",
    "checker": (
        "Git rev-parse actual existing commit/tree plus frozen source"
        "-recipe equality predicate in trace.py"
    ),
    "scope": (
        "Receipt recipe source guard only; no new product/backend/pro"
        "venance authority test and no native callback invocation."
    ),
}
(OUT / "recipe-binding-control.json").write_text(json.dumps(control, indent=2) + "\n")
traces = {
    "BKT": {
        "path": [
            (
                "HistoricalValidationPlan SCI n_simulatio"
                "n_runs → scalar K plans with distinct Se"
                "edSequence-derived actual seeds/runIDs"
            ),
            (
                "prepare_native_replay: exact original Da"
                "taSnapshot/data rows/Trinity/registry → "
                "immutable admitted history prefix and ma"
                "tching masked Trinity child"
            ),
            (
                "scientist_default → BindFoundryInputsNod"
                "e → compile/link → RunSimulationNode act"
                "ual FoundryExecConfig.seed → DefaultFoun"
                "dryPort.execute at every horizon step"
            ),
            (
                "SimulationResult + consumed bindings/pos"
                "t-state snapshots → NativeForecastTrajec"
                "tory registered target slot/unit/reducti"
                "on observations"
            ),
            (
                "load_native_forecast: request + actual c"
                "onfig + initial binding anchor + chronol"
                "ogical native clock/previous-state chain"
                " + exec_plan→program/LoweredIR→Trinity j"
                "oin + observed values"
            ),
            (
                "BacktestOrchestrator consumes verified n"
                "ative values, evaluates held outcomes, p"
                "ersists BacktestReport in configured CAS"
            ),
            (
                "fresh public BacktestReport reader retai"
                "ns typed counts/seed/ref metadata; local"
                " G independently reopens each native ref"
                " and recomputes reported pairs/errors/co"
                "unts"
            ),
        ],
        "defining_quantity": (
            "Registered native state observable trajectory at declared fu"
            "ture time/horizon; counters/effects/scalars never substitute"
            " for forecasts. No native failure fallback: scientist_unavai"
            "lable + preserved attempt/failure counts."
        ),
        "denominators": {
            "backend_replays": "requested7/attempted7/completed7/failed0/unobserved0",
            "metric_time_cells": "requested14/eligible14/observed14",
            "per_replica": "two compared future target-time cells",
        },
        "law_limit": (
            "Distinct actual seeds and runs prove dispatch/config use; de"
            "terministic [1.5,1] repeated values do not establish IID dra"
            "ws, independence, covariance law, interval calibration or gr"
            "ade neutrality."
        ),
        "current_reader_limit": (
            "Public load_backtest_report is typed payload readback, not a"
            " fresh native provenance verifier. Strong native reader is c"
            "onsumed before aggregation and separately available for loca"
            "l independent replay."
        ),
        "minimum_local_production_inputs": [
            (
                "Exact immutable production DataSnapshot/"
                "data refs, row_ids/time_index and declar"
                "ed history columns; original source auth"
                "ority/version remains local"
            ),
            (
                "Original Trinity ModelSpec binding that "
                "same source snapshot and registry, no un"
                "scoped network/time-series refs; declare"
                "d model/feature/world/calibration assump"
                "tions"
            ),
            (
                "Prefix-only Foundry input-binding rules,"
                " registered target slot/unit/reduction; "
                "predictive_simulation purpose/origin/fut"
                "ure coordinates"
            ),
            (
                "Actual cutoff/horizon/ground_truth_outco"
                "mes kept separate from masked inputs; re"
                "quested K and seed and configured CAS id"
                "entity"
            ),
        ],
        "local_procedure": (
            "On exact published candidate source, derive prefix/Trinity v"
            "ia existing producer, execute existing scientist_default, fr"
            "esh-read report and every NativeForecastTrajectory/request/c"
            "onfig/bindings/state, independently join actual original his"
            "tory/model/rows/times/target values/seeds/counts. Reject cha"
            "nged recipe SHA, leaked future rows, substituted Trinity/tra"
            "jectory order, wrong target/unit/horizon. Keep source/histor"
            "y local."
        ),
        "owner_boundaries": [
            (
                "G + model/history/input-binding owner su"
                "pplies source-bound local inputs if prod"
                "uction criterion requires; generic nativ"
                "e dispatch/trajectory positivity already"
                " established"
            ),
            (
                "Scientist trust-profile owner must decla"
                "re versioned purpose/profile and meaning"
                "ful-bias margin/equivalence interval for"
                " B172/B173; p>alpha/zeroRMSE never impli"
                "es GradeA"
            ),
            (
                "Canonical Foundry execution/Core/IR API "
                "owners own remaining helper/entrypoint a"
                "dmission packets; this trace grants no A"
                "PI or global guard waiver"
            ),
        ],
        "status": (
            "B166/B169/B170 technical native mechanism bounded accepted i"
            "ndependently; historical partial and owner adjudication unch"
            "anged. B169 trajectory, B170 K seed/dispatch, B171 micro/mac"
            "ro, B174 standalone CV positivity not universally production"
            "-dependent."
        ),
    },
    "PCL": {
        "path": [
            (
                "Configured graph CAS injected as local artifact_store servic"
                "e into actual MethodDispatcher"
            ),
            ("NumpyRunner preserves explicit store across PanelData extraction/validated params"),
            (
                "NonstationaryGARCHEstimator.pure_step pe"
                "rsisted panel source → segment summary, "
                "overall summary, scenario summary sites"
            ),
            (
                "_summarize_interval_diagnostics → evalua"
                "te_continuous → persist_continuous_evalu"
                "ation exact ordered pairs + diagnostic/r"
                "eceipt → immediate load_continuous_evalu"
                "ation"
            ),
            (
                "MethodResult.artifact_refs → ExecuteArti"
                "facts.derived_artifacts standard refs → "
                "new configured FileSystemCAS → independe"
                "ntly recomputed pairs/report/Truthfulnes"
                "sReceipt"
            ),
        ],
        "counts": (
            "Three distinct source call sites, five actual invocations/fi"
            "ve diagnostics refs/six derived roles in independent native "
            "panel. Proposed-profile alias shares overall artifact and is"
            " not an extra independent estimate."
        ),
        "time_rows_units": (
            "Source PanelData entity/time mapping, evaluated_rows carry o"
            "riginal positions/entity/time/train/evaluation/horizon seman"
            "tics; target/unit caller declarations preserved in source_bi"
            "nding. Independent fixture entity7/12,160panel rows,30traini"
            "ng+50holdout per entity; backend seed688080168. Requested/el"
            "igible/observed defined per requested outcome-level pair, se"
            "parate from row count."
        ),
        "readback_properties": (
            "Persisted pair digest and full numeric report/TruthfulnessRe"
            "ceipt recompute; zero/missing pairs not_evaluated; missing l"
            "evel200requested/100eligible/200observed not perfect; raw re"
            "port cannot assert paired receipt; bootstrap requires explic"
            "it replay seed/defined statistic."
        ),
        "minimum_local_production_inputs": [
            (
                "Immutable admitted PanelData source + ta"
                "rget/unit/entity/time mapping and exact "
                "intervals/held outcomes/level semantics"
            ),
            (
                "Real production caller input materializa"
                "tion/binding and same configured CAS ide"
                "ntity; source/split/horizon/evaluated_ro"
                "w mapping"
            ),
            (
                "Owner-declared purpose/admission/profile"
                " for any calibration authority claim, ex"
                "plicit bootstrap seed/statistic if reque"
                "sted"
            ),
        ],
        "local_procedure": (
            "Same actual graph→NumPy method caller, retain original sourc"
            "e/derived refs; fresh pairs+diagnostics readback recomputes "
            "counts/hits/statistics and reconciles evaluated row/time bin"
            "dings. No production data transfer or invented authority."
        ),
        "owner_boundaries": [
            (
                "Foundry workflow/input materializer/source owner + G local c"
                "hecker for source-bound production claim"
            ),
            (
                "Calibration/Scientist alias migration ow"
                "ner retains actual compatibility invento"
                "ry/window decisions LA053; shim identity"
                " alone does not decide migration"
            ),
            (
                "A served/HTTP caller and real production"
                " GlobalState/Trinity materialization are"
                " not established by generic native panel"
                " fixture"
            ),
        ],
        "status": (
            "LA052/LA053 historical partial; bounded configured method/CA"
            "S consumer code GO reused, no formal finding closure."
        ),
    },
    "FRC": {
        "path": [
            (
                "Strict ForecastOwnerRequestv2: admitted "
                "observed DataSnapshot + canonical DataSc"
                "hema/target_unit/source_native coordinat"
                "e binding + explicit contiguous train/ho"
                "ldout/horizon/method/rule/report/seed/si"
                "x times"
            ),
            (
                "ForecastOwner.run resolves actual regist"
                "ered ETS method, dispatcher NumPy on tra"
                "ining series only with same configured a"
                "rtifact_store/seed"
            ),
            (
                "Typed uncertainty bundle/points and expl"
                "icit heldout rows persist training slice"
                "/observed outcomes/BacktestReport separa"
                "tely"
            ),
            (
                "forecast_bridge produce/persist separate EmpiricalCalibratio"
                "nEvidence + content-bound ForecastCandidateReceipt"
            ),
            (
                "fresh load_forecast_candidate_receipt re"
                "computes original source indices/rowIDs/"
                "pairs/split/horizon/schema units/thresho"
                "ld/profile/times/counts"
            ),
            (
                "ForecastOwnerResult.to_s10_input_fields "
                "fresh candidate adapter retains predicti"
                "ve-only denials; A resolver/default/HTTP"
                "/verifier remains external acceptance pa"
                "th"
            ),
        ],
        "native_method": (
            "forecasting.univariate.exponential_smoothing@1.0.0; declared"
            " NumPy backend; at least8training observations and holdout l"
            "ength exactlyhorizon. ETS sibling is separate from required "
            "BKT default native Scientist forecast; neither substitutes f"
            "or other."
        ),
        "denominator_time_profile": (
            "Exact requested heldout horizon/complete observed pairs/inte"
            "rval hits; six distinct timezone-aware roles data_valid_time"
            ", calibration_window_start,end, policy_effective_time,predic"
            "tion_time,observation_time; predictive_interval_coverage and"
            " explicit configured threshold/profile bind estimand and sco"
            "pe. Method labels/hash/role/credible flag do not prove issue"
            "r/verifier authority."
        ),
        "minimum_local_production_inputs": [
            (
                "Immutable issued numeric DataSnapshot/da"
                "ta + canonical DataSchema mapping target"
                " field/unit/decimal storage scale; decla"
                "red source-native values"
            ),
            (
                "Exact issuer/model/rule/profile versions"
                " + owner admitted predictive calibration"
                " threshold, method params/seed/report id"
                "entity"
            ),
            (
                "Contiguous >=8training prefix and distin"
                "ct actual holdout rows/time positions, e"
                "xplicit horizon, original forecast/outco"
                "me history and six actual temporal roles"
                "; optional model/policy refs only as com"
                "plete distinct pair"
            ),
            (
                "Trusted A runtime verifier composition/p"
                "rofile admission and configured CAS iden"
                "tity for any served/gating acceptance; E"
                " payload supplies no such authority"
            ),
        ],
        "local_procedure": (
            "G performs read-only exact candidate source/history joins on"
            " local original data, invokes same E producer/fresh candidat"
            "e reader, independently recomputes source/split/ordered pair"
            "s/hits/counts/threshold/time/units/purpose; corrupt late out"
            "comes/scope/ref as negatives. A default/HTTP branch must inv"
            "oke strict producer before retained terminal causal refusal "
            "and independently emit/replay verifier provenance on fresh s"
            "erved read."
        ),
        "owner_boundaries": [
            (
                "A actual default-generation/HTTP lifecyc"
                "le, trusted verifier and status/S6 reaso"
                "n projections; current generation_cycle "
                "blob unchanged from independent8486 two "
                "historical A-owned reason failures"
            ),
            (
                "D/source/input-materialization owners su"
                "pply production source/schema/unit/issue"
                "r/time context when required; this E tra"
                "ce does not measure their served integra"
                "tion or ratify source law"
            ),
            (
                "G + local source owner supplies original"
                " production history; generic ETS math/pr"
                "oducer positive is already established"
            ),
            (
                "Causal-effect/treatment-assignment/polic"
                "y purpose authority stays denied, and B2"
                "01/B202 IR semantics remain separate hel"
                "d decisions"
            ),
        ],
        "status": (
            "B32/LA051 accountable-owner closure separate from bounded ET"
            "S producer/reader code GO; no default/served or institutiona"
            "l authority claimed."
        ),
    },
}
(OUT / "consumer-traces-and-local-inputs.json").write_text(json.dumps(traces, indent=2) + "\n")
recipe["families"] = traces
(OUT / "local-G-exact-source-recipe-supplement.json").write_text(
    json.dumps(recipe, indent=2) + "\n"
)
summary = {
    "schema": "policyos.e02.current_consumer_source_trace.v1",
    "current_sha": CURRENT,
    "current_tree": TREE,
    "mode": (
        "Read-only Git source/evidence trace + recipe binding control"
        "; no native duplicate/backend/global tests or new code/findi"
        "ng judgment"
    ),
    "source_E_checkpoint": "cfd79255aab85544082fcf24f93db894202fbfa2",
    "mechanism_blob_join_count": len(joins),
    "all14_reviewed_mechanism_blobs_exact": True,
    "authoritative_review_inputs": review_inputs,
    "carried_source_paths": [
        "mechanism-blob-joins.json",
        "native-k7-carried-witness.json",
        "pcl-carried-witness.json",
        "frc-carried-witness.json",
    ],
    "consumer_and_recipe": "consumer-traces-and-local-inputs.json",
    "local_recipe": "local-G-exact-source-recipe-supplement.json",
    "corrupt_source_recipe_control": "recipe-binding-control.json",
    "author_is_not_reviewer_of_own_BKT_Welfare_facade": (
        "This task assembles source/caller/evidence joins; independen"
        "t reviewers retain their original bounded verdicts. No fresh"
        " self-review."
    ),
    "publication": (
        "Exact currenta9 object exists locally. E root supplies remot"
        "e branch/PR publication/readback; this packet does not assum"
        "e SHA fetchability before root push."
    ),
    "all54_use": (
        "Supplement only BKT/PCL/FRC final consumer/recipe boundaries"
        "; final all54 owner verdicts/ledger historical partial/held/"
        "closed/open preserved. Generic native mechanism positivity i"
        "s not deferred for missing production data. Production input"
        " needed only for source/history authority criterion."
    ),
    "remaining": (
        "A/D served/source-input custody and issuer/profile/verifier/"
        "trust law remain distinct owner tasks; foreign public API le"
        "ases/global guards and IR semantics never authorized by this"
        " trace."
    ),
}
(OUT / "trace-receipt.json").write_text(json.dumps(summary, indent=2) + "\n")
paths = [
    p
    for p in OUT.rglob("*")
    if p.is_file()
    and p.name not in ("copy-index.json", "READY.json", "trace.stdout", "trace.stderr")
]
rows = [
    {
        "path": str(p.relative_to(OUT)),
        "bytes": len(p.read_bytes()),
        "sha256": sha256(p.read_bytes()),
    }
    for p in sorted(paths)
]
index = {
    "schema": "policyos.e02.immutable_source_trace_copy_index.v1",
    "current_sha": CURRENT,
    "primary": "trace-receipt.json",
    "files": rows,
    "file_count": len(rows),
    "bytes": sum(row["bytes"] for row in rows),
    "state": "READY_readonly_trace",
}
(OUT / "copy-index.json").write_text(json.dumps(index, indent=2) + "\n")
ready = {
    "state": "READY",
    "current_sha": CURRENT,
    "current_tree": TREE,
    "source_joins": len(joins),
    "native_or_global_tests_run": 0,
    "file_count": len(rows),
    "bytes": index["bytes"],
    "index_sha256": sha256((OUT / "copy-index.json").read_bytes()),
    "receipt_sha256": sha256((OUT / "trace-receipt.json").read_bytes()),
}
(OUT / "READY.json").write_text(json.dumps(ready, indent=2) + "\n")
_write_stdout(json.dumps(ready, indent=2))
