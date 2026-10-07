import ast
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact value.
        "e an unavailable program before invocati"  # Exact value.
        "on."  # Exact value.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact value.
        "y flush without logging side effects."  # Exact value.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


LANE = Path("/workspace/e02-E-doe-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/doe-budget")
BASE = "a2677935015e8a0e7f2dfd5412b671e13fb3175a"
SOURCE = "70c4a14fc872f5ef66437d958ba63884ecdda168"


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


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(LANE), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def txt(*args: object) -> object:
    return git(*args).decode().strip()


def blob(ref: object, path: object) -> object:
    return git("show", ref + ":" + path)


def sha(x: object) -> str:
    return hashlib.sha256(x).hexdigest()


roots = json.loads((OUT / "independent-native-origins-artifacts.json").read_text())
receipts = {
    label: json.loads((OUT / (label + "-receipt.json")).read_text())
    for label in ["independent-native", "style", "format"]
}
if not (all(x["exit_code"] == 0 and x["source_unchanged"] for x in receipts.values())):
    raise AssertionError
folder = "policy-engine/src/polisyos/scientist/methods/doe/"
unchanged = ["__init__.py", "morris_geometry.py", "uncertainty.py", "sensitivity_benchmark.py"]
if not (all(blob(BASE, folder + p) == blob(SOURCE, folder + p) for p in unchanged)):
    raise AssertionError


def named(ref: object, path: object, kind: str, name: str) -> object:
    return next(
        n for n in ast.parse(blob(ref, path)).body if isinstance(n, kind) and n.name == name
    )


for path, kind, names in [
    (folder + "designs.py", ast.ClassDef, ["SensitivityPlan", "ParameterSpec"]),
    (folder + "_receipt.py", ast.ClassDef, ["_AnalysisReceipt"]),
    (folder + "_receipt.py", ast.FunctionDef, ["_load_analysis"]),
    (folder + "analysis.py", ast.FunctionDef, ["_admit_sobol_sample_blocks"]),
]:
    for name in names:
        if not (
            ast.dump(named(BASE, path, kind, name), include_attributes=False)
            == ast.dump(named(SOURCE, path, kind, name), include_attributes=False)
        ):
            raise AssertionError
cas_case = next(x for x in roots["results"] if x.get("native_analysis"))
store = FileSystemCAS(cas_case["CAS"])
export = {
    "source": SOURCE,
    "oracle": "Morris Y=X+2Z; elementary effects exactly1,2, rankingZthenX",
    "artifacts": {},
}
for label in ["analysis_ref", "corrupt_receipt_ref"]:
    ref = cas_case[label]
    aid = ref["artifact_id"]
    raw = store.get_bytes(aid)
    if not (store.verify(aid).ok):
        raise AssertionError
    export["artifacts"][label] = {
        "ref": ref,
        "sha256": sha(raw),
        "manifest": store.get_manifest(aid).model_dump(mode="json"),
        "content": from_canonical_bytes(raw),
    }
(OUT / "fresh-cas-deciding-artifacts.json").write_text(json.dumps(export, indent=2) + "\n")
footprint = txt("diff", "--name-status", BASE, SOURCE).splitlines()
paths = [p.split("\t")[-1] for p in footprint]
if not (
    len(paths) == 10
    and all(
        p.startswith(
            (
                "policy-engine/src/polisyos/scientist/methods/doe/",
                "policy-engine/tests/unit/scientist/methods/doe/",
                "policy-engine/release-fragments/",
            )
        )
        for p in paths
    )
):
    raise AssertionError
if not (
    txt(
        "diff",
        SOURCE,
        "HEAD",
        "--",
        "policy-engine/src",
        "policy-engine/tests",
        "policy-engine/release-fragments",
    )
    == ""
):
    raise AssertionError
old = json.loads((OUT / "baseline-a267-falsifier.json").read_text())
review = {
    "schema": "e02.E.independent.mutable_plan_budget_review.v1",
    "reviewer": "root/cal_uq_r3; independent from DoE author; read-only; no children",
    "source": SOURCE,
    "tree": txt("rev-parse", SOURCE + "^{tree}"),
    "base": BASE,
    "base_tree": old["tree"],
    "lane": str(LANE),
    "observed_documentation_head": txt("rev-parse", "HEAD"),
    "verdict": "GO_bounded_runtime_plan_admission",
    "blocking_findings": [],
    "immutable_footprint": [
        {
            "status": line.split("\t")[0],
            "path": p,
            "git_blob": txt("rev-parse", SOURCE + ":" + p),
            "sha256": sha(blob(SOURCE, p)),
            "bytes": len(blob(SOURCE, p)),
        }
        for line, p in zip(footprint, paths, strict=False)
    ],
    "property": (
        "Construction admission is not admission of a later mutable o"
        "r model-copy state. Every native/materialization caller re-a"
        "dmits a canonical deep snapshot using existing constructor s"
        "tructural/cap predicate, then uses the captured plan."
    ),
    "common_mechanism": (
        "designs._admit_sensitivity_plan = SensitivityPlan.model_vali"
        "date(plan.model_dump(mode=python)); no copied validator and "
        "no public helper/facade added"
    ),
    "caller_denominator": [
        "generate_sensitivity_samples",
        "_build_salib_problem",
        "_analysis_identity",
        "_prepare_analysis_inputs",
        "analyze_sensitivity",
        "_persist_analysis",
        "AdaptiveSampler.run",
        "MultiOutputAnalyzer.analyze",
        "RankingStabilityChecker.check",
    ],
    "independent_checks": {
        "pytest": "66PASS,9warnings",
        "warnings": (
            "Only deliberate model_construct nested dict serializer warni"
            "ngs; all mutated objects re-admitted and refused before nati"
            "ve work"
        ),
        "mutations": [
            "N",
            "nested dimension list append",
            "method",
            "cap lowering",
            "model_copy(update)",
            "model_construct",
        ],
        "nine_boundaries_each": True,
        "refusal_count": 54,
        "refusal_counts": {"SALib": 0, "evaluator": 0, "CAS_write": 0},
        "three_method_overcap_inlets": "Morris/Sobol/FAST each refuses before sample call",
        "native_sampler_positives": [
            "MorrisN2,k2,6rows",
            "SobolN2,k2,12rows",
            "FASTN65,k2,130rows",
        ],
        "native_denominator_oracle": (
            "Morris N(k+1); Sobol N(2k+2); FAST Nk, i"  # Exact value.
            "ndependently derived from design definit"  # Exact value.
            "ions"  # Exact value.
        ),
        "declared_override": (
            "allow_large_run=true N3Morris cap6 retai"  # Exact value.
            "ns9rows and unchangeddeclaredcap"  # Exact value.
        ),
        "callback_mutation": (
            "original N/nested specs/seed/units changes during sampler an"
            "d identity regeneration do not change captured effective pro"
            "file/design identity"
        ),
        "adaptive": (
            "Late original allow_large_run=true/cap100/N99/bounds100 is i"
            "gnored; one6-row evaluator call then max_estimated_runs_exce"
            "eded at capturedcap6"
        ),
        "analytic_native_CAS": (
            "Morris y=x+2z gives μstar1,2/rankingz,x;12rows requested=suc"
            "cessful; actualpersist→freshFileSystemCAS→reproduced result "
            "exact"
        ),
        "forged_CAS_profile": (
            "Same valid kind/schema/content integrity, n4→5 overcap12; fr"
            "eshreader refuses with0SALib calls"
        ),
        "marker_preserving_removal": (
            "All public names/constructor/schema retained. Remove only sh"
            "ared snapshot/re-admission at actual callers; mutatedN3 cap6"
            " again reachesrealSALib sample inlet once."
        ),
    },
    "fresh_old_falsifier": {
        "source": BASE,
        "tree": old["tree"],
        "all_sources_exact_Git": old["all_module_origins_exact_Git_blobs"],
        "tracked_source_count": old["tracked_source_count"],
        "source_before_after_equal": old["before_after_equal"],
        "cases": old["cases"],
        "backend_scope": (
            "Actual current generate/identity caller reaches counted real"
            " SALib function inlet; old sampler body replaced by spy to a"
            "void allocation. No old numerical-estimator result or inheri"
            "ted PASS claimed."
        ),
    },
    "source_identity": {
        "all_module_origins_exact": roots["all_module_origins_exact"],
        "imported_module_count": roots["module_count"],
        "module_hashes": roots["module_hashes"],
        "tracked_count": receipts["independent-native"]["before"]["source_count"],
        "aggregate_before": receipts["independent-native"]["before"]["source_digest"],
        "aggregate_after": receipts["independent-native"]["after"]["source_digest"],
        "all_runs_source_unchanged": True,
    },
    "environment": roots["environment"],
    "style": {"configuredRuff": "PASS8files", "configuredformat": "PASS8files"},
    "unchanged_properties_proof": {
        "SensitivityPlan_fields_config_and_constructor_AST": True,
        "ParameterSpec_AST": True,
        "persisted_AnalysisReceipt_format_AST": True,
        "fresh_load_implementation_AST": True,
        "Sobol_complete_block_validator_AST": True,
        "Morris_geometry_bytes": True,
        "uncertainty_methods_bytes": True,
        "DOE_facade_bytes": True,
        "benchmark_bytes": True,
        "compatibility": (
            "Existing mutable public object/API preserved; construction f"
            "ields and persisted wire unchanged. Explicit per-design over"
            "ride remains supported. This is not an inferred global cumul"
            "ative budget."
        ),
    },
    "independent_evidence_reuse": (
        "Earlier f07 analytic interaction/Saltelli whole-block/recomp"
        "utedS2/20×3Morris geometry review is retained only for uncha"
        "nged mechanism portions; this new70c4 runtime admission delt"
        "a is separately executed. No new collective B97-B105 closure"
        " or old123 suite relabeling."
    ),
    "P37": {
        "budget": (
            "Caller-declared max_estimated_runs and explicit allow_large_"
            "run, evaluated on canonical current plan at each materializa"
            "tion; no automatic authority"
        ),
        "boundary": (
            "Unsupported/overcap before SALib/evaluator/CAS; structural s"
            "erializer itself may process existing input fields"
        ),
        "snapshot": (
            "Native result/identity uses captured admissible operands eve"
            "n when original object changes during callback"
        ),
        "authority": (
            "population_law_status/evaluator_provenance remainnot_establi"
            "shed; experimental independentinput law is consumer_asserted"
        ),
    },
    "P40": (
        "Same-class deeper post-construction escape widened to the sh"
        "ared constructor predicate through every materialization inl"
        "et, including nested/copy bypass and callback mutation; one "
        "canonical mechanism rather than only visible generator wrapp"
        "er."
    ),
    "P41": (
        "Exact olda267 source/root loaded modules and new70c4 source/"
        "module origins/fullstdout saved; only measured bounded prope"
        "rty outcomes reported. No global guard or unchanged full num"
        "ericalwave run."
    ),
    "remaining_owners": {
        "D": (
            "DefaultSearch typed_sensitivity carrier/codec→analysis_ref→r"
            "anking packet stillconsumer_missing/bridge_missing; no D sou"
            "rce changed"
        ),
        "G": (
            "Exactaggregatefreeze/commonwave and criterion-specific produ"
            "ction history/source-law checks remain separate/localread-on"
            "ly where required"
        ),
        "IR": (
            "Semantic/carrier/source-law ratification"  # Exact value.
            " not part of cap guard;B201/B202held"  # Exact value.
        ),
        "E_root": (
            "Merge reviewedsource+10companions, update exactsourceassembl"
            "y delta thenfreeze; never transfer currentPASS to changedcod"
            "e"
        ),
    },
    "finding_status": (
        "Ledger unchanged; codeGO distinct from finding closure. B97-"
        "B105 not collectively closed, B194/B197/B201/B202held and B1"
        "98 regression retained by existingledger."
    ),
    "run_receipts": {k: k + "-receipt.json" for k in receipts},
    "deciding_artifacts": "fresh-cas-deciding-artifacts.json",
    "cleanup": {
        "performed": "none; nativeTrash unavailable",
        "preserve": "all code/documentation/deciding receipts/stdout/exportedCASpayloads",
        (
            "exact_repeatable_candidates"  # Exact value.
        ): [
            (
                "/tmp/pytest-of-agent/pytest-217"  # noqa: S108 - reported cleanup path only
            )
        ],
        "instruction": (
            "onlyTrash after decidingoutputs/noactiveusers; no permanentd"
            "eletion; shared interpreter remainsactive"
        ),
    },
    "numeric_global_wave": "UNRUN, rootfreeze pending",
    "new_environment_or_worktree": False,
    "source_writes": False,
    "reviewed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
(OUT / "doe-budget-independent-review-70c4.json").write_text(json.dumps(review, indent=2) + "\n")
files = []
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name != "copy-index.json":
        files.append(
            {
                "source": str(p),
                "destination_name": p.name,
                "bytes": p.stat().st_size,
                "sha256": sha(p.read_bytes()),
            }
        )
index = {
    "schema": "e02.E.independent_Doe_budget_copy_index.v1",
    "source": SOURCE,
    "tree": review["tree"],
    "exact_bytes_required": True,
    "files": files,
    "file_count": len(files),
    "total_bytes": sum(x["bytes"] for x in files),
}
(OUT / "copy-index.json").write_text(json.dumps(index, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "review": str(OUT / "doe-budget-independent-review-70c4.json"),
            "verdict": review["verdict"],
            "source": SOURCE,
            "tree": review["tree"],
            "native_independent": 66,
            "file_count": index["file_count"],
            "bytes": index["total_bytes"],
            "blockers": [],
        },
        indent=2,
    )
)
