"Recompute the additive source4 receipt without rewriting reviewed all54 bytes."

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree

if TYPE_CHECKING:
    from types import ModuleType

OUT = Path(__file__).resolve().parent
SOURCE = "8d8e7b319e7eb6b57bc4ab3c4db5ca3070393f8c"
TREE = "192e584c646ee6df303b8793e7b92aa741dcaebb"
PREVIOUS_RUNTIME = "e4b97c15196d8e276745f55a4367da83586511d9"
ROOT_OUTPUT = Path("/workspace").parent / "tmp" / "e02-E-pr38-thirteenth-continuation-20261007"
WAVE = ROOT_OUTPUT / "final-wave-v4"
FILES = {
    "v2": OUT / "all54-delta-associations-v2-source11082.json",
    "prewave": OUT / "source4-association-prewave.json",
    "coverage": OUT / "coverage-reconciliation.json",
    "v2_review": Path("/workspace").parent
    / (
        "tmp/e02-E-fit-packet-thirteenth-20261007/independent-full54-revie"
        "w/review-v2-source11082.json"
    ),
    "source4_review": Path("/workspace").parent
    / ("tmp/e02-E-ingress-oracle-thirteenth-20261007/review-final-source4-test-companion.json"),
    "wave": WAVE / "wave-receipt.json",
    "defining": WAVE / "affected-defining.receipt.json",
    "architecture_controls": WAVE / "architecture-maintained-controls.receipt.json",
    "type": Path("/workspace").parent
    / ("tmp/e02-E-api-companions-thirteenth-20261007/final-v3-frozen-typecheck.receipt.json"),
    "lint": ROOT_OUTPUT / "source4-final-owned-lint/receipt.json",
    "FRC_unique": Path("/workspace").parent
    / ("tmp/e02-E-forecast-packet-thirteenth-20261007/all-eight-failure-identities.json"),
    "FRC_83": Path("/workspace").parent
    / ("tmp/e02-E-forecast-packet-thirteenth-20261007/full83-FRC-case-association.json"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": sha(data)}


def inputs() -> dict:
    return {key: json.loads(path.read_text()) for key, path in FILES.items()}


def source_tools() -> ModuleType:
    spec = importlib.util.spec_from_file_location("e02_full54", OUT / "build_delta_packet.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def xml_cases(path: Path) -> list[dict]:
    result = []
    for case in ElementTree.fromstring(path.read_bytes()).iter("testcase"):
        outcome = "PASS"
        for kind, label in (
            ("failure", "FAIL"),
            ("error", "ERROR"),
            ("skipped", "SKIP"),
        ):
            if case.find(kind) is not None:
                outcome = label
                break
        result.append(
            {
                "classname": case.get("classname", ""),
                "name": case.get("name", ""),
                "outcome": outcome,
            }
        )
    return result


def validate(packet: dict) -> None:
    reference = inputs()
    tools = source_tools()
    if packet["source"]["candidate"] != SOURCE or packet["source"]["tree"] != TREE:
        raise ValueError("final immutable source/tree identity")
    if tools.source_tree(SOURCE) != TREE:
        raise ValueError("recomputed Git tree")
    footprint = (
        tools.git("diff", "--name-status", tools.OLD_HEAD, SOURCE, "--").decode().splitlines()
    )
    if packet["source"]["complete_footprint"] != footprint or len(footprint) != 7:
        raise ValueError("complete seven-path footprint")
    if tools.git("diff", "--name-only", PREVIOUS_RUNTIME, SOURCE, "--", "policy-engine/src/"):
        raise ValueError("source4 runtime differs from measured source3")
    if packet["status_layers"] != reference["v2"]["status_layers"]:
        raise ValueError("historical/E proposal/G-intake layers unchanged")
    if packet["original_scope"] != reference["v2"]["denominator"]:
        raise ValueError("original22/54/55 denominator")
    for name, path in FILES.items():
        if packet["inputs"][name] != identity(path):
            raise ValueError(f"recomputed immutable input identity {name}")
    for key, count in (("defining", 195), ("architecture_controls", 3)):
        receipt = reference[key]
        if receipt["source"] != SOURCE or receipt["tree"] != TREE or receipt["exit_code"] != 0:
            raise ValueError(f"actual command source/exit {key}")
        for record in receipt["complete_outputs"]:
            if identity(Path(record["path"])) != record:
                raise ValueError(f"complete stdout/stderr/JUnit bytes {key}")
        junit = next(r for r in receipt["complete_outputs"] if r["path"].endswith(".xml"))
        cases = xml_cases(Path(junit["path"]))
        if cases != receipt["cases"] or Counter(c["outcome"] for c in cases) != {"PASS": count}:
            raise ValueError(f"actual full XML case denominator {key}")
        if packet["checks"][key]["outcomes"] != receipt["outcomes"]:
            raise ValueError(f"summary cannot invent/drop case outcomes {key}")
    if reference["source4_review"]["source_acceptance"] != (
        "GO_bounded_test_companion_corrective_delta"
    ):
        raise ValueError("non-author source4 bounded review")
    if reference["v2_review"]["disposition"] != "GO":
        raise ValueError("independent original54 association review")
    type_receipt = reference["type"]
    if type_receipt["source"] != PREVIOUS_RUNTIME or type_receipt["exit_code"] != 0:
        raise ValueError("actual scoped type execution retains measured e4 source")
    if type_receipt["summary"]["errorCount"] or type_receipt["summary"]["filesAnalyzed"] != 3:
        raise ValueError("actual selected three-file type result")
    for record in type_receipt["source_inputs"]:
        data = tools.body(SOURCE, record["repository_path"])
        if len(data) != record["bytes"] or sha(data) != record["sha256"]:
            raise ValueError("exact scoped type source reuse into source4")
    if packet["checks"]["type_reuse"]["executed_source"] != PREVIOUS_RUNTIME:
        raise ValueError("unchanged type inputs do not become a source4 rerun")
    if packet["checks"]["type_reuse"]["whole_type_gate"] != "UNRUN":
        raise ValueError("scoped type check is not whole typing gate")
    if (
        packet["historical_provenance"]["scoped_type_diagnostics"]
        != (type_receipt["preceding_current_runs"])
    ):
        raise ValueError("type diagnostic errors/warnings are not passed/failed tests")
    if packet["checks"]["whole_architecture"]["outcome"] != "UNRUN":
        raise ValueError("maintained architecture controls do not become whole gate")
    if packet["checks"]["current_A_native"]["outcome"] != "UNRUN":
        raise ValueError("A source review is not current-A native behavior")
    for name in ("ruff", "format", "diff"):
        run = next(r for r in reference["lint"]["runs"] if r["label"] == name)
        if run["exit_code"] != 0:
            raise ValueError("current source4 E-owned lint/format/diff result")
    if packet["mechanism"]["gate_eligible"] is not False:
        raise ValueError("bounded law receipt grants no gate authority")
    if packet["mechanism"]["production_or_institutional_authority"] != "not_established":
        raise ValueError("native finite corpus is not factual scientific authority")
    if packet["original_findings"]["B194_B197"] != "held":
        raise ValueError("actual served/source/fit inputs remain missing")
    if packet["original_findings"]["B32_LA051"] != "limited":
        raise ValueError("existing A consumer reason-carry gap is still limited")
    if packet["FRC_association"]["unique_observations"] != 8:
        raise ValueError("two FRC findings share eight unique observations")
    if packet["FRC_association"]["per_ID_case_count"] != 83:
        raise ValueError("corrected83-case historical FRC selector")
    deps = reference["prewave"]["all117_original_dependency_bodies"]
    recomputed = tools.unchanged_paths(tools.OLD_SOURCE, SOURCE, [r["path"] for r in deps])
    if deps != recomputed or packet["dependency_count"] != len(deps):
        raise ValueError("all117 original source dependency reconciliation")


def build() -> dict:
    data = inputs()
    tools = source_tools()
    healthy = [
        c
        for c in data["defining"]["cases"]
        if c["name"].startswith(
            "test_real_configured_backend_corpus_persists_and_fresh_node_consumes["
        )
    ]
    if len(healthy) != 2 or any(c["outcome"] != "PASS" for c in healthy):
        raise ValueError("actual HMC/NUTS fresh configured Node cases")
    return {
        "schema": "e02.E.original54.source4-final-verification-binding.v1",
        "scope": (
            "Additive receipt resolves v2/prewave pending public-boundary "
            "checks only. Immutable original54 decisions, historical checks "
            "and full G intake remain separate."
        ),
        "source": {
            "base": tools.OLD_HEAD,
            "candidate": SOURCE,
            "tree": TREE,
            "complete_footprint": tools.git("diff", "--name-status", tools.OLD_HEAD, SOURCE, "--")
            .decode()
            .splitlines(),
            "runtime_source_equal_to": PREVIOUS_RUNTIME,
        },
        "inputs": {key: identity(path) for key, path in FILES.items()},
        "status_layers": data["v2"]["status_layers"],
        "original_scope": data["v2"]["denominator"],
        "dependency_count": len(data["prewave"]["all117_original_dependency_bodies"]),
        "complete_dependency_record": {
            "input": "prewave",
            "fragment": "#/all117_original_dependency_bodies",
        },
        "checks": {
            "defining": {
                "outcome": "PASS",
                "outcomes": data["defining"]["outcomes"],
                "input": "defining",
            },
            "architecture_controls": {
                "outcome": "PASS",
                "outcomes": data["architecture_controls"]["outcomes"],
                "input": "architecture_controls",
            },
            "configured_HMC_NUTS_fresh_Node": healthy,
            "type_reuse": {
                "executed_source": PREVIOUS_RUNTIME,
                "outcome": "PASS",
                "summary": data["type"]["summary"],
                "source4_rerun": False,
                "basis": (
                    "All three selected source bodies equal source4 by exact Git/content hashes."
                ),
                "input": "type",
                "whole_type_gate": "UNRUN",
            },
            "owned_changed_file_lint": {"outcome": "PASS", "paths": 5, "input": "lint"},
            "whole_architecture": {
                "outcome": "UNRUN",
                "qualification": (
                    "Parent running separately; subsequent exact receipt cannot be "
                    "inferred from three maintained controls."
                ),
            },
            "current_A_native": {
                "outcome": "UNRUN",
                "qualification": (
                    "Existing A consumer source review/typed packet only; no current "
                    "A runtime result asserted."
                ),
            },
        },
        "mechanism": {
            "public_Profile2_raw_ingress_and_multi_join_completed": True,
            "property": (
                "Raw declared Profile2 is admitted before "
                "coercion/callback/publication on legacy/model push, compress and "
                "pull routes; unsupported multi-envelope Profile2 join refuses "
                "before generic lowering."
            ),
            "deciding_basis": (
                "Non-author source3/raw-ingress/removal/join review, source4 "
                "corrective test review, frozen actual affected195 cases and "
                "complete outputs."
            ),
            "compatibility": (
                "Single identity, generic joins, literal Profile1 and unprofiled "
                "Envelope1.1 remain supported; combine is diagnostic/non-gating "
                "loss."
            ),
            "gate_eligible": False,
            "production_or_institutional_authority": "not_established",
            "release_readiness": (
                "surface_missing; G canonical ABI/public-surface generation and "
                "owners remain separate"
            ),
        },
        "original_findings": {
            "all54_rows": {"input": "v2", "fragment": "#/rows"},
            "affected_B201_B202": (
                "E technical bounded closed proposals retained; new boundary "
                "repair verified; G formal closure is not promoted."
            ),
            "B188_B192_B199": (
                "Original mathematics/criteria unchanged; affected native "
                "public-reader and generic aggregation controls now have source4 "
                "receipts."
            ),
            "B194_B197": "held",
            "B32_LA051": "limited",
            "other_nine_limited_and_two_held_owner_inputs": {
                "input": "v2",
                "fragment": "#/external_owner_inputs",
            },
        },
        "FRC_association": {
            "unique_observations": 8,
            "cross_ID_links": 16,
            "per_ID_case_count": 83,
            "per_ID_historical_outcomes": {"PASS": 75, "FAIL": 8},
            "source": tools.OLD_SOURCE,
            "qualification": (
                "Shared b2 observations only; not additional tests or current A "
                "failures. Existing consumer/reason carry is verification_missing."
            ),
            "inputs": ["FRC_unique", "FRC_83"],
        },
        "historical_provenance": {
            "source": "v2/prewave immutable refs",
            "retained": (
                "b2 1457P/8F; b305 type7errors/1warning child1 FAIL; "
                "11082 type4errors/0warnings child1 FAIL; e4 first "
                "affected193P/2F; observer/parse ERROR attempts remain "
                "candidate-specific records."
            ),
            "scoped_type_diagnostics": data["type"]["preceding_current_runs"],
            "metadata_correction": {
                "superseded_binding": identity(
                    OUT / "all54-final-source4-verification-binding.json"
                ),
                "scope": (
                    "Correct historical type counts only: prior binding and "
                    "prewave caption wrote7PASS/1FAIL tests instead of7errors/ "
                    "1warning, child1 FAIL. Earlier bytes stay unchanged. "
                    "Original findings and source/wave outcomes do not change."
                ),
            },
            "P41_introducing_cause": "not_established",
            "rule": (
                "Source4 test-only correction observes the earlier raw refusal; "
                "no historical output or required method was weakened to get PASS."
            ),
        },
        "external_owners": {
            "G": (
                "Formal code/finding intake; composed-source "
                "ABI/inventory/generator and full seven-gate workflow/successors."
            ),
            "A": (
                "Current configured resolver/reason recomputation -> persist -> "
                "fresh grade/S6/default/HTTP; distinct missing/unresolved reasons "
                "versus resolved floor failure."
            ),
            "D": ("Default Search analysis_ref/reopen/ranking, independent of original B100."),
            "C_F": ("Actual typed law/profile consumer adoption and own fresh consumer evidence."),
            "Scientist_compute": (
                "Protected finite-float materializer inlet and actual run_job "
                "witness; separate from model/quantity binding and production "
                "authority."
            ),
            "remaining_institutional_source_inputs": (
                "Exact eleven original54 owner-input entries remain at v2; no "
                "unrelated production prerequisite is imposed on independent "
                "generic criteria."
            ),
        },
        "future_self_SHA": False,
        "scientific_or_global_reexecution_by_this_helper": False,
    }


def controls(packet: dict) -> list[dict]:
    mutations = [
        (
            "wrong_final_source",
            lambda p: p["source"].__setitem__("candidate", PREVIOUS_RUNTIME),
        ),
        ("omit_companion_footprint", lambda p: p["source"]["complete_footprint"].pop()),
        (
            "forge_input_receipt_digest",
            lambda p: p["inputs"]["defining"].__setitem__("sha256", "0" * 64),
        ),
        (
            "hide_native_failure",
            lambda p: p["checks"]["defining"]["outcomes"].__setitem__("FAIL", 2),
        ),
        (
            "inflate_native_PASS_count",
            lambda p: p["checks"]["defining"]["outcomes"].__setitem__("PASS", 1465),
        ),
        (
            "claim_source4_type_rerun",
            lambda p: p["checks"]["type_reuse"].__setitem__("executed_source", SOURCE),
        ),
        (
            "promote_scoped_type_to_whole_gate",
            lambda p: p["checks"]["type_reuse"].__setitem__("whole_type_gate", "PASS"),
        ),
        (
            "promote_controls_to_whole_architecture",
            lambda p: p["checks"]["whole_architecture"].__setitem__("outcome", "PASS"),
        ),
        (
            "A_source_review_as_native_PASS",
            lambda p: p["checks"]["current_A_native"].__setitem__("outcome", "PASS"),
        ),
        (
            "native_mean_as_gate_authority",
            lambda p: p["mechanism"].__setitem__("gate_eligible", True),
        ),
        (
            "fixture_as_actual_served_input",
            lambda p: p["original_findings"].__setitem__("B194_B197", "closed"),
        ),
        (
            "drop_missing_A_reason_gap",
            lambda p: p["original_findings"].__setitem__("B32_LA051", "closed"),
        ),
        (
            "double_count_FRC_observations",
            lambda p: p["FRC_association"].__setitem__("unique_observations", 16),
        ),
        (
            "promote_formal_G_acceptance",
            lambda p: p["status_layers"].__setitem__("formal_G_acceptance", 43),
        ),
        ("omit_original_dependency", lambda p: p.__setitem__("dependency_count", 116)),
        (
            "type_errors_relabelled_as_test_PASS",
            lambda p: p["historical_provenance"]["scoped_type_diagnostics"][0].__setitem__(
                "errors", 0
            ),
        ),
    ]
    result = []
    for label, mutate in mutations:
        bad = copy.deepcopy(packet)
        mutate(bad)
        try:
            validate(bad)
        except ValueError as exc:
            result.append({"control": label, "result": "refused", "reason": str(exc)})
        else:
            raise ValueError(f"corrupt binding admitted: {label}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--receipt-stem", required=True)
    args = parser.parse_args()
    if Path(args.receipt_stem).name != args.receipt_stem:
        raise ValueError("receipt output must stay inside packet directory")
    target = OUT / "all54-final-source4-verification-binding-v2.json"
    if args.verify:
        target = args.verify
        packet = json.loads(target.read_text())
    else:
        if target.exists():
            raise ValueError("final binding immutable; do not overwrite")
        packet = build()
    validate(packet)
    if not args.verify:
        target.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
    receipt = {
        "schema": "e02.E.original54.final-binding-validation.v1",
        "scope": (
            "Author receipt/source/XML association recomputation, not "
            "independent scientific review."
        ),
        "packet": identity(target),
        "active_builder": identity(Path(__file__)),
        "executed_python": sys.version,
        "executable": sys.executable,
        "source": SOURCE,
        "tree": TREE,
        "positive_control": (
            "Exact source, footprint, immutable reviews, all XML195+3 cases, "
            "three type source bodies and117 dependencies reconciled."
        ),
        "corrupt_field_controls": controls(packet),
        "result": "PASS",
    }
    (OUT / f"{args.receipt_stem}.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    sys.stdout.write(
        json.dumps({"packet": receipt["packet"], "controls": 16, "result": "PASS"}) + "\n"
    )


if __name__ == "__main__":
    main()
