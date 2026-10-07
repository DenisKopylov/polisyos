"Read-only immutable assembly/source join audit. No numerical invocation."

import ast
import hashlib
import json
import shutil
import subprocess
import sys
import time
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


LANE = Path("/workspace/e02-E-continuation-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/assembly")
BASE = "028829629a9c30454e44d25e7bea7be3ea05b561"
CANDIDATE = "c79de1a8779482cf485317039fe12e3570ae2273"
HAND = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/"
R2 = HAND + "continuation-20261006/pr38-r2/"
START = time.monotonic()


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


def blob(sha: str, path: object) -> object:
    return git("show", sha + ":" + path)


def digest(data: object) -> str:
    return hashlib.sha256(data).hexdigest()


def doc(rel: object) -> object:
    return json.loads(blob(CANDIDATE, R2 + rel))


def ancestor(sha: str) -> bool:
    return (
        subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [
                _resolve_executable("git"),
                "-C",
                str(LANE),
                "merge-base",
                "--is-ancestor",
                sha,
                CANDIDATE,
            ]
        ).returncode
        == 0
    )


def obj(sha: str, path: object) -> object:
    return txt("rev-parse", sha + ":" + path)


def changed(sha: str, path: object) -> bool:
    return bool(git("diff", "--name-only", sha, CANDIDATE, "--", path).strip())


start_head = txt("rev-parse", "HEAD")
start_working = txt("status", "--porcelain")
tracked_src = txt("ls-tree", "-r", "--name-only", CANDIDATE, "policy-engine/src").splitlines()
source_before = {p: digest((LANE / p).read_bytes()) for p in tracked_src}
if not (all((LANE / p).read_bytes() == blob(CANDIDATE, p) for p in tracked_src)):
    raise AssertionError
full = txt("diff", "--name-status", BASE, CANDIDATE).splitlines()
(OUT / "full-committed-footprint.tsv").write_text("status\tpath\n" + "\n".join(full) + "\n")
changed_paths = [row.split("\t")[-1] for row in full]
changed_src = [p for p in changed_paths if p.startswith("policy-engine/src/")]
operational = [
    p
    for p in changed_paths
    if p.startswith(
        (
            "policy-engine/src/",
            "policy-engine/tests/",
            "policy-engine/release-fragments/",
            "policy-engine/architecture/",
        )
    )
    or p == "policy-engine/docs/reference/public-surface.md"
]
review_refs = {
    "CAL/DDM": R2 + "independent-reviews/cal-ddm/review.json",
    "DoE": R2 + "independent-reviews/doe/doe-independent-review-f07.json",
    "MC": R2 + "independent-reviews/mc/review.json",
    "PCL": R2 + "independent-reviews/pcl/review.json",
    "BKT": HAND + "backtest-native-chain-admission-r2-checks/independent-review-go-0983.json",
    "FRC": R2 + "independent-reviews/frc/frc-independent-review-8486.json",
    "Welfare": R2 + "independent-welfare/welfare-independent-review-884681.json",
    "Legacy B197": HAND
    + (
        "calibration-legacy-consumer-r2/independent-review/legacy-con"
        "sumer-independent-review-1e942.json"
    ),
    "Common law guard": R2 + "public-surface-r3/review.json",
    "Canonical routing/metadata": R2 + "public-surface-r5/review-r5.json",
}
family_rows = []
coverage = {}


def family(
    label: str,
    sha: str,
    paths: object,
    review: object,
    scope: str = "byte-identical accepted mechanism and companions",
) -> None:
    if not (ancestor(sha)):
        raise AssertionError((label, "source checkpoint is not ancestor"))
    checks = []
    for p in paths:
        a, b = blob(sha, p), blob(CANDIDATE, p)
        checks.append(
            {
                "path": p,
                "reviewed_blob": obj(sha, p),
                "assembled_blob": obj(CANDIDATE, p),
                "sha256": digest(b),
                "bytes": len(b),
                "equal": a == b,
            }
        )
        if not (a == b):
            raise AssertionError((label, p, "unexpected source delta"))
        coverage[p] = label
    family_rows.append(
        {
            "family": label,
            "source": sha,
            "tree": txt("rev-parse", sha + "^{tree}"),
            "review": review,
            "review_sha256": digest(blob(CANDIDATE, review)),
            "reuse_basis": scope,
            "checks": checks,
        }
    )


# Own CAL authorship is excluded from mechanism judgment; only byte identity to independent
# DoE review is audited.
five = doc("reviewed-five-slice-assembly.json")
for c in five["components"]:
    label = c["family"].upper()
    if label == "CAL":
        review = review_refs["CAL/DDM"]
        paths = [
            x["path"]
            for x in c["matching_objects"]
            if x["path"].startswith(
                (
                    "policy-engine/src/polisyos/foundry/calibration/",
                    "policy-engine/tests/unit/foundry/calibration/",
                    "policy-engine/release-fragments/",
                )
            )
        ]
    elif label == "DDM":
        review = review_refs["CAL/DDM"]
        paths = [x["path"] for x in c["matching_objects"]]
    elif label == "DOE":
        review = review_refs["DoE"]
        paths = [x["path"] for x in c["matching_objects"]]
    elif label == "MC":
        review = review_refs["MC"]
        paths = [
            x["path"]
            for x in c["matching_objects"]
            if not x["path"].endswith("sampling_admission.py")
        ]
    elif label == "PCL":
        review = review_refs["PCL"]
        paths = json.loads(blob(CANDIDATE, review))["target"]["full_footprint"]
    else:
        raise AssertionError(label)
    family(label, c["implementation_sha"], paths, review)
bkt = doc("reviewed-backtest-assembly.json")
bkt_readme = "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/README.md"
if not (blob(CANDIDATE, bkt_readme).startswith(blob(bkt["source_sha"], bkt_readme))):
    raise AssertionError
family(
    "BKT",
    bkt["source_sha"],
    [p for p in bkt["property_paths_exact_reviewed_blobs"] if p != bkt_readme],
    review_refs["BKT"],
)
family(
    "BKT publication README",
    bkt["published_receipt_head"],
    ["policy-engine/src/polisyos/scientist/methods/backtesting/README.md"],
    review_refs["BKT"],
    "documentation-only companion; technical source checked separately",
)
frc = doc("reviewed-frc-assembly.json")
frcpaths = [
    "policy-engine/src/polisyos/calibration/forecast_bridge.py",
    ("policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py"),
    "policy-engine/tests/unit/remediation/test_frc_02_owner.py",
    ("policy-engine/tests/unit/scientist/methods/backtesting/test_forecast_owner.py"),
    ("policy-engine/release-fragments/unreleased/2026-10-06-e02-forecast-source-measurement.toml"),
]
family(
    "FRC",
    frc["source_sha"],
    frcpaths,
    review_refs["FRC"],
    (
        "FRC producer/writer/loader/neutral adapter unchanged; overla"
        "pping root facade exports separately reviewed at bf3"
    ),
)
family(
    "Welfare",
    "884681db485b7466b183a206f83bbe0635f86ca3",
    [
        ("policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py"),
        (
            "policy-engine/tests/unit/scientist/nodes/builtins/simulate/t"
            "est_welfare_empirical_law.py"
        ),
        "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/README.md",
        ("policy-engine/release-fragments/unreleased/2026-10-06-e02-welfare-empirical-law.toml"),
    ],
    review_refs["Welfare"],
    (
        "own independent884 review reused only for identical Welfare "
        "body; common helpers upgraded via separate independent5cd na"
        "tive review"
    ),
)
family(
    "Legacy B197 immutable companions",
    "1e942ff624ae7cb6c71227d48eef760687e17d2b",
    [
        "policy-engine/src/polisyos/scientist/nodes/README.md",
        ("policy-engine/tests/unit/scientist/nodes/test_calibration_report_consumer.py"),
        (
            "policy-engine/release-fragments/unreleased/2026-10-06-e02-ca"
            "libration-legacy-consumer.toml"
        ),
    ],
    review_refs["Legacy B197"],
)
family(
    "Common law guard",
    "5cdfe613bf91fffbd578848c9e2f8275edc21ee7",
    [
        "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py",
        "policy-engine/tests/unit/foundry/uncertainty/test_sampling_real_domain.py",
    ],
    review_refs["Common law guard"],
    (
        "new real/nonzero float64 pre-cast quantity is separately rev"
        "iewed; old MC numeric PASS is not reused for changed helper "
        "body"
    ),
)
family(
    "Canonical routing",
    "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33",
    [
        "policy-engine/src/polisyos/calibration/__init__.py",
        "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
        ("policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py"),
        "policy-engine/tests/unit/calibration/test_evidence_facades.py",
    ],
    review_refs["Canonical routing/metadata"],
    (
        "DoE independent cold canonical identity/actual strict CAS co"
        "nsumer/collector review; own CAL author is not reviewed here"
    ),
)
family(
    "Canonical generated metadata",
    "7dc540d08d30bad8cf23744172c253c934dfc77e",
    [
        "policy-engine/architecture/public_surface/inventory.json",
        "policy-engine/docs/reference/public-surface.md",
        "policy-engine/src/polisyos/foundry/uncertainty/README.md",
    ],
    review_refs["Canonical routing/metadata"],
    (
        "exact canonical20 companion bytes and full generator output "
        "already independently reviewed; no new generator or global g"
        "uard run"
    ),
)
family(
    "Stable reader review flag",
    "7bc65f73d333bc4a526c55d8a959d2b7dea7e472",
    [("policy-engine/release-fragments/unreleased/2026-10-06-e02-foundry-calibration-reader.toml")],
    review_refs["Canonical routing/metadata"],
)
# Non-overlapping root documentation/release companions are bound to the independently
# reviewed root checkpoints.
for p in operational:
    if p in coverage:
        continue
    if (
        p.startswith("policy-engine/src/polisyos/runtime/http/")
        or p.startswith("policy-engine/tests/unit/runtime/http/")
        or p == "policy-engine/tests/unit/remediation/test_dur_02_process.py"
    ):
        family(
            "Foreign G-accepted B runtime",
            txt("rev-parse", "6f869"),
            [p],
            ("policy-engine/docs/research/e02-cloud-test-plan/integration/checkpoint-10.json"),
            (
                "foreign B/runtime checkpoint ancestry only; no E numerical d"
                "ependence or re-review of runtime transaction mechanism"
            ),
        )
    elif (
        p.startswith("policy-engine/release-fragments/")
        or p == "policy-engine/src/polisyos/calibration/README.md"
    ):
        sha = txt("log", "-1", "--format=%H", CANDIDATE, "--", p)
        coverage[p] = "root/family documentation companion"
        family_rows.append(
            {
                "family": "documentation/release companion",
                "source": sha,
                "path": p,
                "assembled_blob": obj(CANDIDATE, p),
                "sha256": digest(blob(CANDIDATE, p)),
                "no_product_python_change": True,
                "review_basis": (
                    "classification/purpose/limitations by existing independent f"
                    "amily/facade reviews; full footprint retained"
                ),
            }
        )
    else:
        raise AssertionError(("uncovered operational path", p))
# Existing canonical loader body remains exact; legacy Node changes only its public
# alias/import route.
report = "policy-engine/src/polisyos/foundry/calibration/report.py"
if not (blob("1e942ff624ae7cb6c71227d48eef760687e17d2b", report) == blob(CANDIDATE, report)):
    raise AssertionError
node_path = "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py"


class NormalizeLoader(ast.NodeTransformer):
    def visit_Name(self, n: int) -> object:
        if n.id == "load_foundry_calibration_report":
            n.id = "load_calibration_report"
        return n


def named_function(sha: str, name: str) -> object:
    return next(
        n
        for n in ast.parse(blob(sha, node_path)).body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )


old = named_function("1e942ff624ae7cb6c71227d48eef760687e17d2b", "_collect_input_envelopes")
new = NormalizeLoader().visit(named_function(CANDIDATE, "_collect_input_envelopes"))
if not (ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)):
    raise AssertionError


# Static canonical-helper routing proof: the actual Welfare consumer imports all three
# existing law helpers through the admitted facade.
def imports(path: object) -> list[object]:
    tree = ast.parse(blob(CANDIDATE, path))
    return [
        {
            "module": n.module,
            "level": n.level,
            "names": [{"name": a.name, "asname": a.asname} for a in n.names],
        }
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
    ]


def all_names(path: object) -> object:
    tree = ast.parse(blob(CANDIDATE, path))
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
    )


welfare = "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py"
unc = "policy-engine/src/polisyos/foundry/uncertainty/__init__.py"
cal = "policy-engine/src/polisyos/calibration/__init__.py"
helpers = {"admit_empirical_weights", "admit_unit_uniform", "empirical_cdf"}
if not (
    helpers
    <= {
        n["name"]
        for i in imports(welfare)
        if i["module"] == "polisyos.foundry.uncertainty"
        for n in i["names"]
    }
):
    raise AssertionError
if not (
    helpers
    <= {n["name"] for i in imports(unc) if i["module"] == "sampling_admission" for n in i["names"]}
):
    raise AssertionError
if not (helpers <= set(all_names(unc))):
    raise AssertionError
if not (len(all_names(unc)) == 20 and len(all_names(cal)) == 29):
    raise AssertionError
if not (
    any(
        i["module"] == "polisyos.foundry.uncertainty"
        and {"load_foundry_calibration_report"} <= {n["name"] for n in i["names"]}
        for i in imports(cal)
    )
):
    raise AssertionError
if not (
    any(
        i["module"] == "calibration.report"
        and i["level"] == 2
        and any(
            n["name"] == "load_calibration_report"
            and n["asname"] == "load_foundry_calibration_report"
            for n in i["names"]
        )
        for i in imports(unc)
    )
):
    raise AssertionError
if not (
    any(
        i["module"] == "polisyos.calibration"
        and any(n["name"] == "load_foundry_calibration_report" for n in i["names"])
        for i in imports(node_path)
    )
):
    raise AssertionError
# Explicit authority/shared-wire boundaries are unchanged in this continuation.
boundaries = [
    "policy-engine/src/polisyos/core",
    "policy-engine/src/polisyos/ir",
    "policy-engine/src/polisyos/scientist/methods/search",
    "policy-engine/src/polisyos/scientist/methods/generation_cycle.py",
    "policy-engine/architecture/guardrails",
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions",
    "policy-engine/docs/research/e02-cloud-test-plan/results",
]
if not (all(not changed(BASE, p) for p in boundaries)):
    raise AssertionError
if not (
    all(
        ancestor(s)
        for s in [
            BASE,
            "1ddcd7b3905e52c0d19db091823a64830139fa64",
            txt("rev-parse", "6f869"),
            "363e7ae0cb2929a92d9667334fdc0ac3087daf5e",
            "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33",
            "7dc540d08d30bad8cf23744172c253c934dfc77e",
            "7bc65f73d333bc4a526c55d8a959d2b7dea7e472",
        ]
    )
):
    raise AssertionError
source_after = {p: digest((LANE / p).read_bytes()) for p in tracked_src}
if not (source_before == source_after):
    raise AssertionError
# Read-only review-removal controls discriminate whole mechanism and companion identity.
checks = [x for family in family_rows for x in family.get("checks", [])]
if not (checks):
    raise AssertionError
for idx, property_name in [
    (0, "mechanism byte substitution"),
    (len(checks) - 1, "required companion removal"),
]:
    altered = [dict(x) for x in checks]
    if idx == 0:
        altered[idx]["assembled_blob"] = "0" * 40
    else:
        altered.pop(idx)
    accepted = len(altered) == len(checks) and all(
        x["assembled_blob"] == x["reviewed_blob"] for x in altered
    )
    if accepted:
        raise AssertionError(property_name)
out = {
    "schema": "e02.E.independent.assembly_dependency_review.v1",
    "reviewer": ("root/cal_uq_r3; independent assembly joins, no own CAL mechanism self-review"),
    "mode": (
        "read-only Git/source/AST/document receipts; no numerical wav"
        "e/global guard/new environment/worktree"
    ),
    "base": BASE,
    "candidate": CANDIDATE,
    "tree": txt("rev-parse", CANDIDATE + "^{tree}"),
    "last_product_source": "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33",
    "metadata_companion": "7dc540d08d30bad8cf23744172c253c934dfc77e",
    "flag_companion": "7bc65f73d333bc4a526c55d8a959d2b7dea7e472",
    "observed_head_start": start_head,
    "observed_head_end": txt("rev-parse", "HEAD"),
    "working_tree_start": start_working,
    "working_tree_end": txt("status", "--porcelain"),
    "product_source_working_delta": "empty",
    "working_tree_limit": (
        "uncommitted wave-controls browser path/README and pending th"
        "ree harness Ruff changes excluded; separate independent DoE "
        "review required before freeze"
    ),
    "source_identity": {
        "tracked_source_count": len(source_before),
        "aggregate_sha256": digest(json.dumps(source_before, sort_keys=True).encode()),
        "actual_working_source_all_matches_pinned_Git": True,
        "before_after_equal": True,
    },
    "footprint": {
        "full_paths": len(full),
        "full_footprint": "full-committed-footprint.tsv",
        "full_footprint_sha256": digest((OUT / "full-committed-footprint.tsv").read_bytes()),
        "source_paths": len(changed_src),
        "operational_paths": len(operational),
        "operational_coverage_complete": set(operational) <= set(coverage),
        "no_omitted_mechanism_or_companions": True,
        "coverage": coverage,
    },
    "families": family_rows,
    "reviews": {
        k: {"path": p, "sha256": digest(blob(CANDIDATE, p)), "bytes": len(blob(CANDIDATE, p))}
        for k, p in review_refs.items()
    },
    "dependency_joins": {
        "Welfare_3_law_helpers": (
            "Welfare source884 imports existing admitted Foundry uncertai"
            "nty aliases from same sampling_admission owner; common body5"
            "cd has separate DoE independent native review and is exact"
        ),
        "BKT_README": (
            "Original BKT paragraph bytes preserved as exact prefix; Welf"
            "are independently reviewed append is recorded, not claimed o"
            "ld byte equality"
        ),
        "Legacy_reader": (
            "Actual Node→Calibration→admitted Foundry uncertainty→unchang"
            "ed Foundry calibration report strict reader; normalized _col"
            "lect_input_envelopes AST equals1e942"
        ),
        "canonical_counts": {"Calibration": 29, "Foundry_uncertainty": 20},
        "no_parallel_CAS_reader_or_sampler": "import/reexport route only",
        "G_Runtime": (
            "ControlPlaneStore/test/dur02 bytes exact6f ancestry; B-owned"
            " transaction mechanisms not an E numerical dependency or E-a"
            "uthored change"
        ),
        "IR_Core_A_D": (
            "all listed source/contract/guard/results/closure-decision boundaries unchanged"
        ),
    },
    "P37_basis": {
        "reuse": (
            "exact property source blobs and required companions, consume"
            "r delta gets own independent review; export names alone insu"
            "fficient"
        ),
        "numeric_scope": (
            "true native laws/Hessians/full covariance/null axes/failed s"
            "upport retained per mechanism review; input source law/serve"
            "d consumer/authority remain separately held"
        ),
        "Welfare_unknown_joint": (
            "one nominal, one gradient base, four existing deterministic "
            "sensitivity probes recorded; zero stochastic/unattempted sup"
            "port/noCI/non-gating; no count0 claim"
        ),
        "authority": (
            "predictive only; candidate/empirical evidence distinct, CAS "
            "content/hash/schema not institutional provenance; gatefalse "
            "and terminal causal refusal retained"
        ),
    },
    "P40_class_repairs": {
        "common_precast": (
            "real-domain and nonzero support loss fixed at common inlet5c"
            "d; changed helper body is not assigned old MC PASS"
        ),
        "failed_support": (
            "Welfare native GE law/support plus conditional moments at884"
            " independently checked including present-but-fake/source-row"
            "/readback/removal"
        ),
        "objective_and_covariance": (
            "no new adjudication of own CAL code; independent CAL review "
            "owns scalar preflight and previous guards; mathematical/infe"
            "rence authority distinct"
        ),
        "canonical_architecture_route": (
            "transient private Cal→Foundry report edge superseded by bf3 "
            "canonical existing facade; oldnew collector+object+actualCAS"
            " controls reviewed by DoE"
        ),
    },
    "P41": (
        "No numerical/global PASS on new c79 candidate is inferred. E"
        "xact family native sources reused by immutable byte joins on"
        "ly; root expensive wave UNRUN here and must run once after f"
        "inal freeze; historic old red without exact replay stays not"
        "_established."
    ),
    "initial_harness_scope_error": (
        "First static join required byte-equal shared simulation READ"
        "ME; actual delta only appends Welfare paragraph and preserve"
        "s full BKT prefix. Scope corrected to BKT original prefix pl"
        "us separately reviewed Welfare full file; original failed as"
        "sertion retained. No product or companion loss."
    ),
    "scope_decision": (
        "GO_source_assembly_and_dependency_joins; ready for freeze af"
        "ter separate pending harness review; no committed product-so"
        "urce blocker found"
    ),
    "blocking_product_findings": [],
    "unratified_held_boundaries": {
        "B194": "held; real served evaluator/consumer input owner required",
        "B197": (
            "held; technical configured producer/CAS/strict consumer cove"
            "red, source/authority decision separate"
        ),
        "B201/B202": (
            "held; appointed IR semantic owner and four finite carrier/fu"
            "nctionals decisions absent; no IRwire edits"
        ),
        "B198": "closed historical regression retained; no new falsifier",
        "Core_IR_execute": (
            "owner packets not_ratified/unapplied; API alternatives not silently admitted"
        ),
        "A_default": (
            "defaultFRC trusted verifier/statusreason/HTTP checks remain "
            "A packet, no E edits generation_cycle"
        ),
        "D_Search": (
            "typed sensitivity codec actual _sensitivity extra_forbidden "
            "owner-ready packet; default consumer remains D residual"
        ),
    },
    "remaining_checks": {
        "root": (
            "separate pending harness review then freeze exact aggregate "
            "and execute one common wave; no authorization question requi"
            "red for already owned work"
        ),
        "G": (
            "fetch exact E candidate and recipes, integration acceptance "
            "separate; strictly required production history/source law lo"
            "cal read-only"
        ),
        "owners": (
            "Core/IR/execute public admission, A served/default verifier,"
            " D Search codec, IR semantic appointment/ratification, DDM s"
            "erved validity/signoff profiles"
        ),
    },
    "ledger": (
        "unchanged source/results/closure decisions; no status reclas"
        "sification or finding closure by assembly GO"
    ),
    "negative_controls": [
        {"property": "mechanism byte substitution", "outcome": "REJECTED"},
        {"property": "required companion removal", "outcome": "REJECTED"},
    ],
    "cleanup": (
        "No environments or native numeric fixtures created by this a"
        "ssembly review. Preserve scripts/evidence. No permanent dele"
        "tion."
    ),
    "elapsed_seconds": time.monotonic() - START,
}
(OUT / "assembly-dependency-review-c79.json").write_text(json.dumps(out, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "candidate": CANDIDATE,
            "tree": out["tree"],
            "verdict": out["scope_decision"],
            "family_rows": len(family_rows),
            "reviewed_blobs": len(checks),
            "full_paths": len(full),
            "operational_paths": len(operational),
            "source_before_after_equal": True,
            "blocking_product_findings": [],
        },
        indent=2,
    )
)
