(
    "Freeze moderate author outputs and appli"  # Exact value.
    "cable source packet; no root writes."  # Exact value.
)

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from defusedxml.ElementTree import parse as _safe_xml_parse


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


OUT = Path(__file__).parent
ROOT = Path("/workspace/e02-E-continuation-20261006")
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
WAVE = Path("/workspace/e02-E-pr38-r2-receipts/common-wave-5e3e37276/checks")
manifest = json.loads((OUT / "postimage-manifest.json").read_text())
for row in manifest["paths"]:
    if not (
        hashlib.sha256((OUT / "postimage" / row["path"]).read_bytes()).hexdigest()
        == row["after_sha256"]
    ):
        raise AssertionError
base_dest = OUT / "original-5e-red"
base_dest.mkdir(exist_ok=True)
base_inputs = []
for stage in ("architecture", "workspace-verify"):
    for ext in ("stdout.txt", "json"):
        origin = WAVE / stage / (stage + "." + ext)
        destination = base_dest / (stage + "." + ext)
        raw = origin.read_bytes()
        destination.write_bytes(raw)
        base_inputs.append(
            {
                "original": str(origin),
                "packet_copy": str(destination.relative_to(OUT)),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
xml = _safe_xml_parse(OUT / "native-combined.xml")
suite = xml.getroot().find("testsuite")
if not (
    suite is not None
    and int(suite.attrib["tests"]) == 17
    and int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
):
    raise AssertionError
origins = json.loads((OUT / "native-origins-combined.json").read_text())
if origins["mismatches"]:
    raise AssertionError
collect = json.loads((OUT / "collector-generator.json").read_text())
native = json.loads((OUT / "native-combined-receipt.json").read_text())
fresh = json.loads((OUT / "fresh-cas-readback.json").read_text())
receipt = {
    "schema": "policyos.e02.implementation_handoff.owned_facade_route.v1",
    "unit": "E",
    "slice": "owned-welfare-covariance-and-calibration-reader-facade-route",
    "authorization": (
        "Root scratch-only writer lease: Foundry uncertainty and Cali"
        "bration owned facades, exact two Node import routes, mirrore"
        "d tests/docs/release/canonical inventory. No root/source wri"
        "tes, new worktrees/environments or foreign facade/shared sch"
        "ema edits."
    ),
    "base": {"sha": BASE, "tree": "3b63e778d5b6d17b2e9edc3b4bf91af079b32eb0"},
    "candidate": {
        "state": "frozen_applicable_scratch_patch",
        "implementation_sha": None,
        "implementation_tree": None,
        "root_framing_sha": native["framing_HEAD"],
        "root_framing_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [
                _resolve_executable("git"),
                "-C",
                str(ROOT),
                "rev-parse",
                native["framing_HEAD"] + "^{tree}",
            ],
            text=True,
        ).strip(),
        "patch": "owned-facade-route.patch",
        "patch_sha256": manifest["patch_sha256"],
        "postimage_manifest": "postimage-manifest.json",
        "source_postimage_count": 12,
        "checkpoint_owner": (
            "E root applies reviewed patch and commits original source, t"
            "hen appends exact Git implementation SHA/tree binding before"
            " handoff/publish. This receipt does not invent an implementa"
            "tion Git SHA."
        ),
    },
    "diff_paths": [row["path"] for row in manifest["paths"]],
    "problem_and_behavior": [
        {
            "trigger": (
                "Actual Welfare Node imported five canonical covariance symbo"
                "ls from private Foundry covariance module."
            ),
            "before": "Canonical deep-import scanner records the new cross-root private edge.",
            "after": (
                "Five identity-preserving lazy typed expo"
                "rts in already-admitted Foundry uncertai"
                "nty root; actual Welfare caller imports "
                "that root. Available math/objects retain"
                " identity; optional JAX absence preserve"
                "s root import and requesting covariance "
                "raises real dependency error."
            ),
        },
        {
            "trigger": (
                "Calibration experimental root re-exporte"
                "d strict Foundry reader and actual legac"
                "y uncertainty Node imported that alias."
            ),
            "before": "Actual workspace lint rule ARCH001 reports Calibration→Foundry at root41.",
            "after": (
                "Remove unreleased E-topic alias and rout"
                "e actual Node directly through admitted "
                "Foundry uncertainty. Identical strict re"
                "ader, other28 Cal exports, unchanged num"
                "erical/CAS schema/consumer bodies."
            ),
        },
    ],
    "property_path": {
        "actual_callers": [
            (
                "PropagateWelfareNode.execute → canonical"  # Exact value.
                " covariance/projection/null-space consum"  # Exact value.
                "ers"  # Exact value.
            ),
            (
                "PropagateUncertaintyNode.execute → _coll"
                "ect_input_envelopes → canonical configur"
                "ed CAS load_calibration_report before di"
                "spatch"
            ),
        ],
        "defining_properties": [
            (
                "Five canonical owner objects exported wi"  # Exact value.
                "th identity and typed TYPE_CHECKING impo"  # Exact value.
                "rts"  # Exact value.
            ),
            (
                "Exact admitted consumer routes remove the two real owned vio"
                "lations, no newly introduced private edges"
            ),
            "Both Node non-import ASTs and covariance source bytes unchanged",
            (
                "True empirical-law native GE failed supp"
                "ort and fresh sample/outcome readback pr"
                "eserved"
            ),
            (
                "Actual tied Calibrator v2 covariance reaches fresh legacy No"
                "de; malformed kind/schema/version refuse callback0"
            ),
        ],
        "source_origin_evidence": (
            "native-origins-combined.json actual830 loaded modules, four "
            "frozen postimages plus exact5e Git bytes; zero mismatches"
        ),
    },
    "oracles_and_negatives": {
        "actual_native_oracles": {
            "pytest_xml": "native-combined.xml",
            "tests": 17,
            "failures": 0,
            "errors": 0,
            "scope": native["scope"],
            "welfare_fresh_readback": "fresh-cas-readback.json",
            "requested": 128,
            "attempted": 128,
            "success": 92,
            "failed": 36,
            "conditional_welfare": 2.0,
            "unconditional_welfare": None,
            "credible_and_outer_intervals": None,
            "seed": 31415,
            "atom_rows_and_weights": (
                "Input carrier0/1 weights3/1 → independent NumPy inverse-CDF "
                "row indices, exact persisted rows/outcomes/ref metadata"
            ),
        },
        "route_removal_controls": {
            (
                "exports_present_old_private_route"  # Exact value.
            ): (
                "Canonical actual collector retains covar"  # Exact value.
                "iance violation despite25 exports"  # Exact value.
            ),
            "Cal___all___28_old_runtime_alias_import": (
                "Actual lint_imports.main still ARCH001 even removing alias e"
                "xport name while retaining forbidden import"
            ),
        },
        "CAS_adversarial_controls": (
            "Actual legacy Node samebytes wrongkind, schema/name and vers"
            "ion plus invalid explicit input hiding behind valid snapshot"
            " refuse before dispatcher/evaluator callback. Native tests b"
            "ind canonical strict reader identity."
        ),
        "metadata_negatives": (
            "Present fake owner E passes generic nonempty parser but fail"
            "s actual contract owner/classification/version predicate; in"
            "ventory_review field removal and version_owner removal refus"
            "ed by native structured parser."
        ),
        "optional_dependency_control": (
            "Fresh child blocks JAX before package import; uncertainty ro"
            "ot import succeeds, canonical covariance request raises genu"
            "ine ImportError. NumPy already required by base sampling_adm"
            "ission; no absentNumPy survival claim."
        ),
    },
    "collector_and_publication_evidence": {
        "primary": "collector-generator.json",
        "old_owned_covariance_red": collect["removed_owned_covariance_edge"],
        "old_Cal_ARCH001_red": "import-policy-old5e.json",
        "new_import_policy_zero": "import-policy-postimage.json",
        "actual_deep_selected_remainder": collect["selected_new_deep_edges"],
        "new_private_edges": [],
        "canonical_generator": (
            "Native guardrails.build_public_surface_inventory/render_publ"
            "ic_surface_json/render_public_surface_markdown, full unchang"
            "ed contract; exact original5e generated bytes verified, surg"
            "ical owned postimages generated"
        ),
        "counts": {"Calibration": 28, "Foundry uncertainty": 25, "DDM": 17},
        "source_denominator": collect["selected_full_source_denominator"],
        (
            "complete_current_reader_reference_denomi"  # Exact value.
            "nator"  # Exact value.
        ): (
            "tracked-reader-refs.json plus original21"  # Exact value.
            "matches/9paths stdout"  # Exact value.
        ),
        "release_companions": (
            "release-parser.json exact2 rows team-scientist/public_experi"
            "mental Cal, team-polisyos/public_stable uncertainty, version"
            "team-architecture per canonicalG53"
        ),
    },
    "commands_outputs_environment": {
        "actual_pytest_receipt": "native-combined-receipt.json",
        "actual_loaded_origins": "native-origins-combined.json",
        "environment": "environment-probe-receipt.json",
        "style": (
            "style-receipt.json 6Python files/12 actu"  # Exact value.
            "al product-context Ruff+format PASS"  # Exact value.
        ),
        "apply_readonly_check": "apply-check.json",
        "generator_script": "generate_and_collect.py",
        "generator_outputs": [
            "collector-generator-expanded.stdout",
            "collector-generator-expanded.stderr",
        ],
        "release_and_reference_script": "release_and_refs.py",
        "fresh_readback_script": "fresh_readback.py",
        "no_artificial_CPU_process_limits": True,
        "native_test_conftest_backend": (
            "Runner removes inherited caps and JAX_PLATFORMS; repository "
            "pytest fixture subsequently sets JAX_PLATFORMS=cpu, recorded"
            " actual origin environment/backend. CPU is observed backend,"
            " no worker cap."
        ),
    },
    "predicate_basis": {
        "P37_frozen": (
            "Two actual-owned route predicates, canonical object identity"
            ", unchanged math/covariance/supported optional boundary, nat"
            "ive caller freshCAS property, exact generator/owner metadata"
            " and effective route-removal controls. No pass-count substit"
            "ution for defining property."
        ),
        "P40_class_fix": (
            "Same facade-consumer class applied to both actual owned rout"
            "es and allfive covariance symbols; literal exports/name abse"
            "nce cannot substitute for actual consumer/import-policy beha"
            "vior."
        ),
        "P41": (
            "Original full5e guard and workspaceverify FAIL stdout/comple"
            "te stage receipts retained. Exact selected collectors reprod"
            "uce old owned rows. Their bounded GO does not imply full glo"
            "bal architecture/import-policy PASS or classify all other re"
            "d as inherited."
        ),
        "original_red_inputs": base_inputs,
        "introducing_commits": {
            "private_covariance_import": "28ea3bb56bc4e751bf1303615d79219b56d7a24c",
            "Cal_Foundry_alias": "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33",
        },
        "Welfare_final884_math_reuse": (
            "Current covariance/Welfare blobs and unchanged non-importAST"
            " checked, prior independent CAL review mathematical judgment"
            " reused only within exact unchanged defining property. Final"
            "884 did not introduce the private import."
        ),
    },
    "capability_state": {
        "bounded_author_code_checks": "PASS",
        "independent_review": (
            "pending DDM exact source/receipt decisio"  # Exact value.
            "n; author does not self-review"  # Exact value.
        ),
        "real_backend": (
            "Existing NumPy/SciPy/JAX shared venv, real CPU JAX operation"
            "s and native GE/Calibrator executed"
        ),
        "served_evaluator_profile_source_authority": "not_established",
        (
            "foreign_API_owner_admission"  # Exact value.
        ): (
            "pending distinct owner packets; no Core/"  # Exact value.
            "IR/public-contract edit or waiver"  # Exact value.
        ),
    },
    "status_and_limits": {
        "code_acceptance": (
            "Separate bounded reviewed route compatibility task; root/G a"
            "cceptance independent of findings"
        ),
        "finding_ledger_changes": None,
        "B194": (
            "held source/evaluator/profile authority "  # Exact value.
            "despite generic native law witness"  # Exact value.
        ),
        "B197": (
            "held source/Calibrator/served evaluator authority despite te"
            "chnical producer/readback/covariance route"
        ),
        "B198": "closed regression status preserved; this slice does not reclassify it",
        "B201_B202": (
            "held semantic-owner decisions unchanged;"  # Exact value.
            " v1.1 wire replay/schema bytes untouched"  # Exact value.
        ),
        "other_historical_partial_open": "Preserved, no automatic finding closure",
        "production_evidence": (
            "No production history/source-law bytes in cloud; exact nativ"
            "e fixture inputs and moderate deciding CAS artifacts remain "
            "labeled generic. Existing localG reproduce recipe remains se"
            "parate; no new invented production dataset/evaluator/admissi"
            "on input."
        ),
        "remaining_owners": {
            "E_root": (
                "Apply/commit reviewed source then receipt Git binding; one f"
                "inal planned wave after all bounded reviews"
            ),
            "DDM_reviewer": (
                "Independent object/route/optional/native artifact review on "
                "frozen patch and/or applied Git bytes"
            ),
            "G": (
                "Fetch exact E topic implementation check"
                "point for integration/acceptance; formal"
                " finding closure remains owner adjudicat"
                "ion"
            ),
            "Core_IR_API_owners": (
                "Remaining foreign supported-entrypoint/h"
                "elper admissions are separate packets an"
                "d cannot be granted by E route exports"
            ),
        },
    },
    "preserved_historical_harness_outputs": {
        "historical_covariance_only": (
            "historical-covariance-only/ contains initial7PASS source sub"
            "set before added Cal-alias route fix; never substitute for f"
            "inal17 source. Full old output/origins retained."
        ),
        "harness_errors": (
            "harness-errors/ preserves initialwrong Ruff cwd/config conte"
            "xt, missing actual package-boundaries filename and exporter "
            "typed-store reference adaptation errors. These are harness f"
            "ailures, not product numerical evidence; corrected final dec"
            "iding outputs separately retained."
        ),
    },
    "cleanup": {
        "policy": (
            "No permanent deletion; no system Trash used/emptied. Candida"
            "tes only after root/G deciding outputs and unique data prese"
            "rvation. Shared active venv/code/docs/production/unique CAS "
            "never discarded as repeatable scratch."
        ),
        "exact_repeatable_candidates": [
            str(OUT / name)
            for name in (
                "native-basetemp",
                "native-cache",
                "native-benchmark",
                "native-final-basetemp",
                "native-final-cache",
                "native-final-benchmark",
                "native-combined-basetemp",
                "native-combined-cache",
                "native-combined-benchmark",
                "import-policy-old5e-cache",
                "import-policy-postimage-cache",
                "import-policy-present-old-alias-cache",
            )
        ],
        "retained": (
            "Frozen postimages/patch/receipts/original outputs/deciding g"
            "enericCAS exports and active shared environment. Owner root "
            "coordinates later cleanup after review; no Trash available i"
            "n this cloud task."
        ),
    },
}
(OUT / "author-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
# Include exact12 postimages despite generated sizes: required applicable-source audit.
paths = [
    OUT / "author-receipt.json",
    OUT / "postimage-manifest.json",
    OUT / "owned-facade-route.patch",
    OUT / "apply-check.json",
    OUT / "overlay.json",
]
paths += [OUT / "postimage" / row["path"] for row in manifest["paths"]]
for name in (
    "generate_and_collect.py",
    "freeze_source.py",
    "style_checks.py",
    "release_and_refs.py",
    "fresh_readback.py",
    "run_native.py",
    "finalize_packet.py",
    "collector-generator.json",
    "collector-generator-expanded.stdout",
    "collector-generator-expanded.stderr",
    "import-policy-old5e.json",
    "import-policy-postimage.json",
    "import-policy-present-old-alias.json",
    "release-parser.json",
    "tracked-reader-refs.json",
    "tracked-reader-refs-base.stdout",
    "release-and-refs.stdout",
    "release-and-refs.stderr",
    "native-combined-receipt.json",
    "native-combined.stdout",
    "native-combined.stderr",
    "native-combined.xml",
    "native-origins-combined.json",
    "environment-probe-receipt.json",
    "environment-probe.stdout",
    "environment-probe.stderr",
    "fresh-cas-readback.json",
    "fresh-readback.stdout",
    "fresh-readback.stderr",
    "style-receipt.json",
    "style-summary.stdout",
    "style-summary.stderr",
    "freeze-source.stdout",
    "freeze-source.stderr",
):
    paths.append(OUT / name)
for folder in (
    "hooks",
    "fresh-cas-readback",
    "historical-covariance-only",
    "harness-errors",
    "original-5e-red",
):
    paths += [p for p in (OUT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
paths += list(OUT.glob("style-*.stdout")) + list(OUT.glob("style-*.stderr"))
paths = sorted(set(paths))
rows = []
for path in paths:
    if not (path.exists()):
        raise AssertionError(path)
    raw = path.read_bytes()
    rows.append(
        {
            "path": str(path.relative_to(OUT)),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
index = {
    "schema": "policyos.e02.moderate_immutable_author_packet_index.v1",
    "base": BASE,
    "state": "READY_frozen_source_and_author_outputs_independent_decision_pending",
    "source_patch_sha256": manifest["patch_sha256"],
    "primary_receipt": "author-receipt.json",
    "file_count": len(rows),
    "bytes": sum(row["bytes"] for row in rows),
    "files": rows,
    "excluded": (
        "Entire repeatable pytest/CAS/cache dirs and broad sourcearch"
        "ive excluded. Exact12 postimages, moderate deciding generic "
        "artifact bytes, original red outputs and historical harness "
        "failures included."
    ),
}
(OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
ready = {
    "state": "READY",
    "packet_root": str(OUT),
    "index_sha256": hashlib.sha256((OUT / "index.json").read_bytes()).hexdigest(),
    "author_receipt_sha256": hashlib.sha256((OUT / "author-receipt.json").read_bytes()).hexdigest(),
    "patch_sha256": manifest["patch_sha256"],
    "files": len(rows),
    "bytes": index["bytes"],
    "root_mutations": 0,
    "implementation_sha": None,
    "independent_review": (
        "Pending DDM; this is author packet readi"  # Exact value.
        "ness, not independent GO/global pass."  # Exact value.
    ),
}
(OUT / "READY.json").write_text(json.dumps(ready, indent=2) + "\n")
_write_stdout(json.dumps(ready, indent=2))
