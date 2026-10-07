#!/usr/bin/env python3
(
    "Reconcile existing tracked E closeout an"  # Exact value.
    "d exact component cuts without edits."  # Exact value.
)

import collections
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path

from defusedxml.ElementTree import fromstring as _safe_xml_fromstring


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


REPO = pathlib.Path("/workspace/e02-E-continuation-20261006")
OUT = pathlib.Path(__file__).resolve().parent
SNAPSHOT = "f445cbc3439b1539937e8e3f6df492bbd6c2e4a3"
SOURCE = SNAPSHOT
E02 = "policy-engine/docs/research/e02-cloud-test-plan/"
E = E02 + "implementation-handoffs/E/"
CONT = E + "continuation-20261006/"
R2 = CONT + "pr38-r2/"
inputs = {}


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
    return subprocess.check_output([_resolve_executable("git"), "-C", str(REPO), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def read(path: object, ref: object = SNAPSHOT) -> object:
    data = git("show", f"{ref}:{path}")
    key = f"{ref}:{path}"
    inputs[key] = {
        "source_sha": ref,
        "path": path,
        "git_blob": git("rev-parse", key).decode().strip(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return data


def obj(path: object, ref: object = SNAPSHOT) -> object:
    return json.loads(read(path, ref))


def dump(name: str, data: object) -> None:
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


coverage = obj(E02 + "closure-decisions/coverage.json")
bundles = {x["id"]: x for x in coverage["bundles"] if x["unit"] == "E"}
covered = {x["id"]: x for x in coverage["findings"] if x["unit"] == "E"}
prior = obj(CONT + "closure-frozen/all-54-closeout.json")
recipes = obj(CONT + "closure-frozen/local-G-closeout-recipes.json")
assembly = obj(R2 + "reviewed-five-slice-assembly.json")
semantic = obj(R2 + "ir-semantic-owner-decision.json")
trace = obj(CONT + "consumer-frozen/source-trace.json")
for path in [
    "AGENTS.md",
    "policy-engine/CONTRIBUTING.md",
    "policy-engine/docs/reference/ownership.md",
    "policy-engine/architecture/public_surface/contract.toml",
    E02 + "execution-prompts/HANDOFF.md",
    E02 + "execution-prompts/continuation-2026-10-06/E-resume-after-pr38.md",
    E02 + "execution-organization/README.md",
    E02 + "execution-organization/bundle-owners.tsv",
    E02 + "execution-organization/finding-owners.tsv",
    E02 + "closure-decisions/README.md",
    E02 + "closure-decisions/E.md",
    E02 + "closure-decisions/method-decisions.md",
    E02 + "closure-decisions/semantic-decisions.md",
    E02 + "closure-decisions/cross-unit-contracts.md",
    E02 + "closure-decisions/verification-and-closeout.md",
    E02 + "closure-decisions/runtime-profiles.md",
    E02 + "closure-decisions/execution-sequence.md",
    E02 + "integration/reviews/E-pr38-continuation-audit-2026-10-06.md",
    "policy-engine/docs/reference/policy-design-case-failure-patterns.md",
    E02 + "results/verification.json",
]:
    read(path)
for b in bundles.values():
    read(b["criterion_card"])

component = {x["family"]: x for x in assembly["components"]}
new_receipts = {
    "MC": (
        "finite-sampling-law-20261006-r2.json",
        component["mc"]["published_receipt_head"],
        component["mc"]["implementation_sha"],
    ),
    "CAL": (
        "calibration-gaussian-noise-preflight-r2-20261006.json",
        component["cal"]["published_receipt_head"],
        component["cal"]["implementation_sha"],
    ),
    "DOE": (
        "doe-block-replay-20261006.json",
        component["doe"]["published_receipt_head"],
        component["doe"]["implementation_sha"],
    ),
    "DDM": (
        "ddm-registry-version-20261006.json",
        component["ddm"]["published_receipt_head"],
        component["ddm"]["implementation_sha"],
    ),
    "PCL": (
        "pcl-configured-consumer-20261006.json",
        component["pcl"]["published_receipt_head"],
        component["pcl"]["implementation_sha"],
    ),
    "BKT": (
        "backtest-native-chain-admission-r2.json",
        SNAPSHOT,
        "0983d064df3c3e21f8b1accff4ee90484d78973b",
    ),
    "FRC": (
        "frc-source-measurement-r2.json",
        "f73e554bfe567aec29aff957a2c026f1537e4834",
        "8486baad6fdef8063cfaad80b15f6b6d8532460a",
    ),
}
receipts = {family: obj(E + path, ref) for family, (path, ref, _) in new_receipts.items()}
reviews = {family.upper(): obj(R2 + c["review"]) for family, c in component.items()}
reviews["FRC"] = obj(R2 + "independent-reviews/frc/frc-independent-review-8486.json")
reviews["BKT"] = obj(
    E + "backtest-native-chain-admission-r2-checks/independent-review-go-0983.json"
)
component_reconciliation = []
for c in assembly["components"]:
    entries = []
    for old in c["matching_objects"]:
        current = git("rev-parse", SOURCE + ":" + old["path"]).decode().strip()
        entries.append(
            {
                "path": old["path"],
                "reviewed_blob": old["source_blob"],
                "assembled_blob": current,
                "identical": current == old["source_blob"],
                "delta_owner": (
                    "FRC8486 forecast_owner companion; native PCL six-owned-paths"
                    " remain exact; full root consumer wave pending"
                )
                if current != old["source_blob"]
                else None,
            }
        )
    component_reconciliation.append(
        {
            "family": c["family"],
            "implementation_sha": c["implementation_sha"],
            "assembled_source_sha": SOURCE,
            "entries": entries,
        }
    )
for row in prior["rows"]:
    for cr in row["criterion_refs"]:
        read(cr["path"])
    ref = row["receipt_ref"]
    path, commit = ref.rsplit("@", 1)
    read(path, commit)
    for ref in row.get("independent_review_refs", []) or []:
        if isinstance(ref, str) and "@" in ref:
            p, commit = ref.rsplit("@", 1)
            if len(commit) == 40:
                read(p, commit)

# Evidence remains at its exact authored/reviewed cut. Root component byte
# equality is checked here, without converting component tests into root tests.
for c in assembly["components"]:
    for entry in c["matching_objects"]:
        read(entry["path"], c["implementation_sha"])
        read(entry["path"], SOURCE)
for key, (_unused_name, _unused_ref, impl) in new_receipts.items():
    d = receipts[key]
    for path in d.get("mechanism_paths", []):
        if isinstance(path, str):
            read(path, impl)

family_meta = {
    "CAL": {
        "bundles": ["CAL-01", "CAL-02", "CAL-03", "CAL-04", "CAL-05", "CAL-06"],
        "producer": (
            "Foundry measurement/compiler/preflight -> CalibratorInputs -"
            "> actual JAX Calibrator scalar/batch optimizer/final forward"
            "/Hessian"
        ),
        "artifact": (
            "CalibrationReport v2 with exact objective/cache/config ident"
            "ity; report-owned coordinate covariance and CAS refs"
        ),
        "bridge": (
            "Configured producer/report persistence and strict welfare pr"
            "ojection; legacy IR sample reader enforcement is a separate "
            "owner seam"
        ),
        "consumer": (
            "Calibrator selection/finalization; configured fresh welfare "
            "reader; actual default served model authority not establishe"
            "d"
        ),
        "surface": (
            "Typed report/native Calibrator and welfare artifacts, withou"
            "t production or causal authority"
        ),
        "new_property": receipts["CAL"]["runtime_property"],
        "oracle": (
            "Known-sigma Gaussian NLL: MLE(1,2), Hessian diag(.25,1/9), i"
            "nverse diag(4,9), SE(2,3). Pure scalar admission uses actual"
            " Calibrator loader/emitter counters: Python/NumPy bool ->0 c"
            "alls; finite positive real float -> actual execution."
        ),
        "negative": (
            "Old exact58e boolean scales reach loader; new bool/np.bool_,"
            " zero, nonfinite, wrong type refuse before loader/emitter. R"
            "aw saddle/flat/negative/singular/ill-conditioned curvature n"
            "ever becomes valid covariance."
        ),
        "P37": {
            "recomputed": (
                "Support, axes, target weights, JAX grad/"
                "Hessian, finite scalar preflight, exact "
                "objective/cache and tie-map projection"
            ),
            "consumer_asserted": (
                "Synthetic known noise/input mathematical"  # Exact value.
                " profile, target/source declarations"  # Exact value.
            ),
            "not_established": (
                "Actual source fit/noise law, Calibrator/"
                "served authority and legacy enforcement "
                "adapter"
            ),
        },
    },
    "BKT": {
        "bundles": ["BKT-01", "BKT-02", "BKT-03", "BKT-04"],
        "producer": (
            "Scientist BacktestOrchestrator -> immutable replay snapshot/"
            "Trinity/materializer -> actual DefaultFoundry/native executi"
            "on"
        ),
        "artifact": (
            "Typed target trajectory and execution re"
            "quest/output/binding refs -> BacktestRep"
            "ort CAS"
        ),
        "bridge": (
            "Native snapshot/model/seed/output replay bridge; new chronol"
            "ogical/initial-anchor/Trinity mismatch falsifiers are active"
            " blockers"
        ),
        "consumer": (
            "Fresh BacktestReport and independently resolved source/forec"
            "ast refs; grade scorer withholds trust without purpose/profi"
            "le"
        ),
        "surface": (
            "Native report diagnostics/library consum"
            "er; production-history claim remains loc"
            "al-only"
        ),
        "new_property": (
            "Prior native K1/K7 author witness exists, but independent ne"
            "w review blocks approval pending chronological ordering, ini"
            "tial-anchor and actual Trinity/plan binding class repair."
        ),
        "oracle": (
            "Fresh exact masked row IDs/refs, requested=attempted=complet"
            "ed=K, failed=0; actual seeds/run IDs/typed forecast target/u"
            "nit/time/horizon. Micro residual oracle[0,10,10]:sqrt(200/3)"
            "; Student t fixtures t0/df2/p1 and t2.59807621135/df2/p.1216"
            "899343."
        ),
        "negative": (
            "Missing/mismatched Trinity, future/leaky rows, wrong target/"
            "horizon, counter-only fake producer, chronological loader/in"
            "itial-anchor and actual plan-binding mismatch; unavailable S"
            "ciPy degraded, not neutrality."
        ),
        "P37": {
            "recomputed": (
                "Diagnostic denominators, residuals, executed seeds/ref joins"
                ", split/horizon/row binding and actual trajectory"
            ),
            "consumer_asserted": (
                "Exploratory synthetic profile; distinct "
                "seeds do not establish source-law indepe"
                "ndence"
            ),
            "not_established": "Owner trust-grade purpose/equivalence rule and production history",
        },
    },
    "DOE": {
        "bundles": ["DOE-01", "DOE-02", "DOE-03"],
        "producer": "Canonical capped/adaptive DoE and SALib1.5.2 seeded sampler/analyzer",
        "artifact": (
            "Ordered complete plan/X/Y/analysis receipt in configured CAS"
            ", distribution/seed/scale/trajectory/counts/analyzer bound"
        ),
        "bridge": (
            "SensitivityBridge -> fresh artifact reader -> SensitivityAwa"
            "reCandidateGenerator.from_artifact; D default Search integra"
            "tion remains bridge_missing"
        ),
        "consumer": (
            "Fresh-process recomputing analyzer/typed candidate generator"
            "; D owns actual SearchLoopRunner execution/ranking"
        ),
        "surface": (
            "DoE/Sensitivity library artifact and typed _sensitivity refs"
            "; no separate search runtime"
        ),
        "new_property": receipts["DOE"]["property"]["statement"],
        "oracle": (
            "Independent ANOVA: x,z iidU[0,1], y=x+z+2xz -> S1(.48,.48),S"
            "2=.04,ST(.52,.52), abs tolerance.01. Complete valid Saltelli"
            " block+pairedY reorder preserves point estimates(1e-12) whil"
            "e changing content/order; Morris physical(2,3), normalized(2"
            "0,3)."
        ),
        "negative": (
            "Zero indices with preserved shape, invalid/duplicate/missing"
            "/interior-mutated blocks, integrity-valid stale/forged S2 af"
            "ter fresh rebind, removed analyzer numerical recomputation; "
            "old exact58e shape-only proxy divergence."
        ),
        "P37": {
            "recomputed": (
                "Plan/X/Y/full block membership/order/denominator/distributio"
                "n mapping and canonical analyzer fresh readback"
            ),
            "independently_reconciled": "ANOVA interaction indices and linear Morris unit oracle",
            "consumer_asserted": "Admitted experimental iid law/profile",
            "not_established": "Population/evaluator authority; D actual default Search consumer",
        },
    },
    "DDM": {
        "bundles": ["DDM-01", "DDM-02"],
        "producer": (
            "Detector calibration -> calibration audit -> monitor.evaluat"
            "e_window -> versioned model registry producer"
        ),
        "artifact": (
            "Neutral ShiftEvent/budget contracts; distinct registry v2 re"
            "cord/schema with exact report/model/rule/quantity/time/inval"
            "idation refs"
        ),
        "bridge": (
            "Fresh JSON schema reader/migration -> rebind original inputs"
            " -> independent veto/readiness gate"
        ),
        "consumer": (
            "DDMWindowResult.registry_record library; served deployment/p"
            "rofile reader promotion remains owner action"
        ),
        "surface": (
            "Internal polisyos.ddm lazy facade and actual registry record"
            "; no institutional signoff inferred"
        ),
        "new_property": receipts["DDM"]["property"]["statement"],
        "oracle": (
            "Original strict closed v1 reader rejects actual v2 producer;"
            " current reader preserves actual old v1 bytes as nongating; "
            "native v2 fresh rebind/veto. DDM01 no-orchestration MetaPath"
            ",14 classes/enums,12 JSON/pickle models and LK35 differentia"
            "l preserved."
        ),
        "negative": (
            "Old same$id+four optional fields actual producer fails old s"
            "trict reader; unknown/untyped/unversioned enriched record, f"
            "orged source digest, R4/R3 veto after reopen/signoff, remove"
            "d version guard/schema reader control. [] synthetic events i"
            "s not a complete current feed."
        ),
        "P37": {
            "recomputed": (
                "Wire version/schema, exact source/input rebind, validity TTL"
                "/time roles and veto precedence"
            ),
            "consumer_asserted": (
                "Synthetic bounded calibration/feed decla"  # Exact value.
                "ration and boolean signoff"  # Exact value.
            ),
            "not_established": (
                "Actual feed completeness/freshness, depl"
                "oyment purpose/institutional R2 human au"
                "thority"
            ),
        },
    },
    "PCL": {
        "bundles": ["PCL-01"],
        "producer": (
            "Configured execute_program_graph -> MethodDispatcher -> Nump"
            "yRunner -> actual Advanced segment/overall/scenario interval"
            " diagnostics"
        ),
        "artifact": (
            "Source PanelData plus ordered requested/eligible/observed pa"
            "irs, diagnostics/report/receipt in same configured CAS"
        ),
        "bridge": (
            "Local params service override trusted graph store, scientifi"
            "c/state payloads exclude CAS service; existing native result"
            " refs"
        ),
        "consumer": (
            "Fresh FileSystemCAS load_continuous_evaluation independently"
            " joins source entity/time/index rows to persisted intervals;"
            " existing execute derived-ref surface"
        ),
        "surface": (
            "Native method results/ExecuteResult derived refs; source aut"
            "hority not_established and gate_eligible=false"
        ),
        "new_property": receipts["PCL"]["property"]["statement"],
        "oracle": (
            "Actual native arch fit reopened100 paired source rows:82/100"
            " coverage, nominal.95, ECE.13. Separate95/100,0/100,zero/inc"
            "omplete pairs arithmetic; fresh store12 diagnostics artifact"
            "s*100source joins."
        ),
        "negative": (
            "Missing configured store nongating, fake client store cannot"
            " redirect trusted graph CAS; corrupted/missing/reordered per"
            "sisted pairs, hash-valid forged count/receipt and property r"
            "emoval fail. Old58 exact inlet fails artifact_store paramete"
            "r; historical helper-only pass did not prove native bridge."
        ),
        "P37": {
            "recomputed": (
                "Persisted report/receipt/pair counts and source row/time joi"
                "ns, configured CAS refs, arbitrary client store denied"
            ),
            "consumer_asserted": "Synthetic target/unit/split profile from typed PanelData",
            "not_established": (
                "Production source/history authority; app"  # Exact value.
                "roved joint API compatibility sunset"  # Exact value.
            ),
        },
    },
    "FRC": {
        "bundles": ["FRC-01", "FRC-02"],
        "producer": (
            "Admitted ForecastOwnerRequest v2 -> canonical source schema/"
            "unit/scale preflight -> real MethodDispatcher NumPy ETS"
        ),
        "artifact": (
            "Training+forecast bundle+BacktestReport; separate content-bo"
            "und candidate receipt and empirical evidence in configured C"
            "AS"
        ),
        "bridge": (
            "Fresh E candidate loader/to_s10_input_fields typed adapter; "
            "A default producer/verifier/generation-cycle/HTTP pending ca"
            "nonical writer"
        ),
        "consumer": (
            "E independent source rows->persisted interval readback; A mu"
            "st resolve/recompute all profile/source/metric/unit/split/ho"
            "rizon/pairs/counts/threshold/purpose/six roles and verifier "
            "provenance on fresh served read"
        ),
        "surface": (
            "E native predictive evidence; A S10/grade/S6/HTTP surface pe"
            "nding; terminal causal/treatment/policy refusal retained"
        ),
        "new_property": receipts["FRC"]["property"]["statement"],
        "oracle": receipts["FRC"]["property"]["independent_oracle"],
        "negative": receipts["FRC"]["property"]["negative_controls"],
        "P37": {
            "recomputed": (
                "Resolved schema/unit/scale/split/pairs/time/ref integrity an"
                "d independently source-bound observed interval coverage"
            ),
            "consumer_asserted": (
                "Synthetic declared predictive purpose/profile; producer cred"
                "ible=True is not trusted verifier"
            ),
            "not_established": (
                "A own configured verifier provenance/def"  # Exact value.
                "ault HTTP read and production history"  # Exact value.
            ),
        },
    },
    "MC": {
        "bundles": ["UQP-01", "UQP-02", "UQP-03"],
        "producer": (
            "Common input-law/numeric admission -> analytical/delta/rando"
            "m/Sobol/Halton transform -> actual callback"
        ),
        "artifact": (
            "Per-output envelopes, full addressed draw-outcome provenance"
            " and propagation config/report in CAS; exact finite joint ca"
            "rrier"
        ),
        "bridge": (
            "Dispatcher common supported law admission pre-nominal callba"
            "ck; Scientist node/welfare strict fresh report adapter"
        ),
        "consumer": (
            "Fresh CAS law/certificate/outcome reconciliation; generic se"
            "rved evaluator/domain authority unavailable"
        ),
        "surface": (
            "Native propagation/welfare envelope refs remain nongating wh"
            "ere assumptions/source unknown"
        ),
        "new_property": (
            "One canonical exact finite-machine paired law; all positive "
            "CDF buckets retained or typed refusal before callbacks; supp"
            "orted covariance Gaussian/nullspace and empirical pairing co"
            "ntrols retained."
        ),
        "oracle": (
            "Paired rows(0,0),(1,2),(4,5),mass1:1:2: ymean5.25,var15.1875"
            ",complete256net64/64/128callback rows. TiedGaussian differen"
            "ce variance0 vs independent.005. Independent256pilot fixed40"
            "8main(mean certificate) excludes pilot; RQMC independent ful"
            "l nets replicate estimates."
        ),
        "negative": (
            "Tiny first/interior/last atoms, zero weights/U0/U1/adjacent "
            "CDF boundaries, near-but-distinct normalized weights, CDF co"
            "llapse, reordered paired rows/stale digest; unsupported Unif"
            "orm covariance before callback0; float32 range escape pre-dr"
            "aw; per-draw failure conditional≠unconditional."
        ),
        "P37": receipts["MC"]["predicate_basis"],
    },
    "UQS": {
        "bundles": ["UQS-01"],
        "producer": (
            "Existing uncertainty aggregation over admitted envelopes; ne"
            "w v2 exact-law producer awaits semantic ratification"
        ),
        "artifact": (
            "v1.1 replay envelopes/provenance; future distinct v2 linked "
            "uncertainty/identification artifacts with exact joint-law CA"
            "S"
        ),
        "bridge": (
            "Existing typed summary aggregation; cannot reconstruct a law"
            " from moments or inline summary"
        ),
        "consumer": (
            "Existing nongating aggregator; actual new C/F law consumers "
            "must be appointed by ratified IR semantic owner"
        ),
        "surface": "v1.1 retained; v2 not implemented or silently ratified",
        "new_property": (
            "Duplicate identity/level/type regression retained. B200 real"
            " information relationships unknown; B201/B202 four decisions"
            " unratified."
        ),
        "oracle": (
            "Same source copies preserve std1; precision combination is o"
            "nly conditional declared independent arithmetic, never verif"
            "ied information count.99zeros+100:mean1,q05/q95[0,0].Equal s"
            "ummaries/different laws and pairedcorrelation+1/-1 require d"
            "istinct serialize/reopen law identities."
        ),
        "negative": (
            "Duplicate ref/content, conflicting same origin, missing inde"
            "pendence, summary-only law queries and falsely widened equal"
            "-tail interval. B201/B202 oracle is reviewable discriminator"
            ", not a v2 implementation PASS."
        ),
        "P37": {
            "recomputed": "Existing content/ref equality and fixed summary types/levels",
            "consumer_asserted": "Caller origins/independence flags; hypothetical v2 alternatives",
            "not_established": (
                "Information-unit prior/likelihood/shared-data lineage and ap"
                "pointed semantic authority/new law consumers"
            ),
        },
    },
}
for family, d in family_meta.items():
    if family in new_receipts:
        name, head, impl = new_receipts[family]
        d["new_receipt"] = f"{E}{name}@{head}"
        d["implementation_sha"] = impl
        d["implementation_tree"] = git("rev-parse", impl + "^{tree}").decode().strip()
    if family.lower() in component:
        c = component[family.lower()]
        d["independent_review_ref"] = f"{R2}{c['review']}@{SNAPSHOT}"
        d["code_review_state"] = (
            "E independently reviewed bounded code GO; G code acceptance separate"
        )
        d["assembled_source_sha"] = SOURCE
        d["assembled_state"] = (
            "present, exact owned mechanism Git blobs equal reviewed leaf"
            " cut; no root numeric wave yet"
        )
    elif family == "FRC":
        d["independent_review_ref"] = (
            f"{R2}independent-reviews/frc/frc-independent-review-8486.json@{SNAPSHOT}"
        )
        d["code_review_state"] = (
            "E independently reviewed bounded8486GO; exact trackedCAL rev"
            "iew, G acceptance/finding closure separate"
        )
        d["assembled_source_sha"] = SOURCE
        d["assembled_state"] = (
            "source-present after ordinary merge of publishedf73 receipt/"
            "source8486 into902d9f6 and successor5d4e010; no combined num"
            "eric wave"
        )
    elif family == "BKT":
        d["independent_review_ref"] = (
            f"{E}"  # Exact value.
            "backtest-native-chain-admission-r2-check"  # Exact value.
            "s/independent-review-go-0983.json@"  # Exact value.
            f"{SNAPSHOT}"  # Exact value.
        )
        d["code_review_state"] = (
            "E independent bounded0983GO after concrete9cHOLD and correct"
            "ive5ad; actual current source present; finding/G acceptance "
            "separate"
        )
        d["assembled_source_sha"] = SOURCE
        d["assembled_state"] = (
            "source-present by ordinaryappendmerge into5d4e010 and succes"
            "sorinventoryf445; native chronology/initialanchor/compiledTr"
            "inity joins repaired; no common numeric wave"
        )
        d["new_property"] = receipts["BKT"]["defining_property"]
        d["corrective_negative"] = receipts["BKT"]["negative_controls"]
        d["corrective_oracle"] = receipts["BKT"]["independent_oracle"]
    else:
        d["code_review_state"] = (
            (
                "pending fix+fresh independent review; prior author positive "
                "does not overrule new blocker"
            )
            if family == "BKT"
            else "pending independent source/delta review"
            if family == "FRC"
            else "unchanged bounded mechanisms; no new own review claim"
        )
        d["assembled_source_sha"] = SOURCE
        d["assembled_state"] = (
            "new component NOT merged at this snapshot"
            if family == "BKT"
            else "existing v1.1 source, v2 unimplemented"
        )

# Exact moderate deciding output locators supplement, rather than duplicate,
# the full original author receipts. ExpectedFAIL removal controls are labeled.
output_paths = {
    "MC": [
        ("finite-sampling-law-20261006-r2/native-run.json", "author native274PASS"),
        (
            "finite-sampling-law-20261006-r2/frozen58.stdout.txt",
            "exactold58 law falsifiers",
        ),
        (
            "finite-sampling-law-20261006-r2/candidate-d69.stdout.txt",
            "same candidate law falsifiers",
        ),
        ("finite-sampling-law-20261006-r2/environment.json", "actual environment"),
    ],
    "CAL": [
        (
            (
                "calibration-gaussian-noise-preflight-r2-"  # Exact value.
                "20261006.frozen58-gaussian-scale.txt"  # Exact value.
            ),
            "exactold58 actualloader bool falsifier",
        ),
        (
            (
                "calibration-gaussian-noise-preflight-r2-"  # Exact value.
                "20261006.candidate45b-gaussian-scale.txt"  # Exact value.
            ),
            "candidate actualloader scalar witness",
        ),
        (
            "calibration-gaussian-noise-preflight-r2-20261006.candidate45b-pytest.txt",
            "author native37PASS",
        ),
    ],
    "DOE": [
        (
            "doe-block-replay-20261006/frozen-native.execution.json",
            "author native123PASS",
        ),
        (
            "doe-block-replay-20261006/interaction-removal-final.stdout.txt",
            "expectedFAIL numerical interaction removal",
        ),
        (
            "doe-block-replay-20261006/block-admission-removal-final.stdout.txt",
            "expectedFAIL block membership removal",
        ),
        (
            "doe-block-replay-20261006/recompute-readback-removal-final.stdout.txt",
            "expectedFAIL receipt numeric recomputation removal",
        ),
        (
            "doe-block-replay-20261006/fresh-process.stdout.txt",
            "fresh consumer/formal stale receipt controls",
        ),
        ("doe-block-replay-20261006/environment.json", "actual environment"),
    ],
    "DDM": [
        ("ddm-registry-version-20261006/native-candidate.json", "author native82PASS"),
        (
            "ddm-registry-version-20261006/old_source_probe.stdout",
            "sameID original strict reader falsifier",
        ),
        (
            "ddm-registry-version-20261006/legacy_source_probe.stdout",
            "actual old producer->new reader",
        ),
        (
            "ddm-registry-version-20261006/schema-removal-candidate.stdout",
            "expectedFAIL strict schema property removal",
        ),
        ("ddm-registry-version-20261006/environment.json", "actual environment"),
    ],
    "PCL": [
        (
            (
                "pcl-configured-consumer-20261006-logs/pc"  # Exact value.
                "l-74b26eb067de/native-witness-output.jso"  # Exact value.
                "n"  # Exact value.
            ),
            "actual native source/pairs/results ref oracle",
        ),
        (
            "pcl-configured-consumer-20261006-logs/pcl-exact58e-red3.stdout.txt",
            "exactold58 native inlet overlay",
        ),
        (
            "pcl-configured-consumer-20261006-logs/archive-readback.json",
            "fresh portableCAS12artifact*100sourcepairs",
        ),
        (
            "pcl-configured-consumer-20261006-logs/environment.json",
            "actual environment",
        ),
    ],
    "BKT": [
        (
            (
                "backtest-native-chain-admission-r2-check"  # Exact value.
                "s/independent-order-falsifiers-final.jso"  # Exact value.
                "n"  # Exact value.
            ),
            (
                "independent genuineK3 positive plus five hash-valid chronolo"
                "gy/anchor/Trinity forgeries reject"
            ),
        ),
        (
            (
                "backtest-native-chain-admission-r2-check"  # Exact value.
                "s/independent-order-falsifiers-removal.j"  # Exact value.
                "son"  # Exact value.
            ),
            (
                "removing actual compiledTrinity join accepts unexecutedtax50"
                " with genuine tax25 outcomes; property-removal divergence"
            ),
        ),
    ],
    "FRC": [
        (
            "frc-source-measurement-r2/checks/affected-native.resource.json",
            "author native affectedfamily",
        ),
        (
            "frc-source-measurement-r2/checks/positive-artifact.stdout",
            "fresh source rows31..34 positive4/4 vs0/4",
        ),
        (
            "frc-source-measurement-r2/checks/measurement-probe.stdout",
            "actual callback0 preflight",
        ),
        (
            "frc-source-measurement-r2/checks/property-removal.stdout",
            "expectedFAIL unit guard removal",
        ),
        (
            (
                "frc-source-measurement-r2/checks/histori"  # Exact value.
                "cal-base-measurement-configured.stdout"  # Exact value.
            ),
            "old58 configured callback divergence",
        ),
    ],
}
for family, paths in output_paths.items():
    head = new_receipts[family][1]
    evidence = []
    for path, meaning in paths:
        fullpath = E + path
        read(fullpath, head)
        record = inputs[f"{head}:{fullpath}"]
        evidence.append({**record, "meaning": meaning})
    family_meta[family]["deciding_output_refs"] = evidence

active = {
    "B32",
    "B100",
    "B166",
    "B169",
    "B170",
    "B172",
    "B173",
    "B188",
    "B190",
    "B192",
    "B193",
    "B200",
    "LA-051",
    "LA-052",
    "LA-053",
    "LA-054",
    "LA-055",
}
held = {"B194", "B197", "B201", "B202"}
bounded = set(prior["bounded_property_complete_candidate_ids"])
external = {
    "B32": (
        (
            "A generation-cycle/S10/default HTTP writ"  # Exact value.
            "er; @runtime-owners and @scientist-owner"  # Exact value.
            "s"  # Exact value.
        ),
        (
            "E8486 configured CAS positive refs, correct request/profile/"
            "unit/source/split/horizon/rule/six actual times and A test/s"
            "tatus patch packet"
        ),
        (
            "A applies typed fields/default producer and separately recom"
            "putes evidence/provenance; fresh grade/S6/HTTP read agrees; "
            "missing_ref differs from resolved limited; causal refusal st"
            "ays"
        ),
        (
            "A bridge/verifier/default surface code remains implementable"
            "; E source/unit/adapter packet8486 merged902 and successor5d"
            " with exact trackedCAL independentGO"
        ),
    ),
    "LA-051": (
        (
            "A generation-cycle/S10/default HTTP writer; E ForecastOwner/"
            "calibration writer (@scientist-owners)"
        ),
        (
            "Exact separate E candidate/empirical refs, configured source"
            "/metric/unit/profile/split/horizon/pairs/counts/threshold/pu"
            "rpose/six roles and native packet"
        ),
        (
            "A own verifier resolves/recomputes then fresh default+HTTP r"
            "ead; accepts predictive calibration only and retains termina"
            "l causal/treatment/policy refusal"
        ),
        (
            "A trusted verifier/default bridge remains code; E8486 source"
            " preflight/adapter independentlyGO with tracked review and s"
            "ource-present5d"
        ),
    ),
    "B100": (
        (
            "D default Search/autotune writer; @scientist-owners; E-W06 o"
            "wns canonical numeric producer"
        ),
        (
            "Tracked D-consumer-packet.md, configured CAS analysis ref, a"
            "dmitted plan/X/Y and declared experimental input law/evaluat"
            "or purpose"
        ),
        (
            "Actual SearchLoopRunner invokes canonical seeded producer/re"
            "ader and consumes typed sensitivity refs in ranking; fresh p"
            "ersisted result+negative stale law/order"
        ),
        "D default Search bridge remains code; no second E search runtime",
    ),
    "B166": (
        (
            "E-W01 BKT writer; @scientist-owners workflow/materializer wi"
            "th @foundry-owners execution input boundary"
        ),
        (
            "Native immutable source/mask/Trinity/ModelSpec/plan refs and"
            " chronological source rows/valid initial anchor; exact candi"
            "date identity"
        ),
        (
            "Accountable owner adjudicates native0983 exactmasked row/anc"
            "hor/clock/model-plan joins using independent genuineK3+five "
            "hash-validforgeries; factual production history only if clai"
            "med"
        ),
        (
            "Native source chronology/initialanchor/actualTrinity-plan cl"
            "ass defects repaired5ad+0983 and independentlyGO; owner find"
            "ing acceptance remains"
        ),
    ),
    "B169": (
        (
            "E-W01 BKT writer; @scientist-owners typed forecast profile/m"
            "aterializer with @foundry-owners native producer"
        ),
        (
            "Native typed target/unit/time/horizon trajectory refs with c"
            "onsistent model/Trinity execution binding"
        ),
        (
            "Accountable owner adjudicates actual typed native trajectory"
            " on independentK3 and priorK7 witness; counters/scalar/wrong"
            "target/horizon and forgedTrinity refuse fresh"
        ),
        (
            "Actual native replay bridge independentlyGO0983 and source-p"
            "resent; no counter/scalar/ETS substitution for this native b"
            "oundary"
        ),
    ),
    "B170": (
        (
            "E-W01 BKT writer; @scientist-owners work"  # Exact value.
            "flow and @foundry-owners execution-confi"  # Exact value.
            "g owner"  # Exact value.
        ),
        (
            "Actual per-run ExecuteRequest ExecConfig seeds/run IDs, full"
            "K attempted/failed/success output refs and admitted matching"
            " plan"
        ),
        (
            "Accountable owner uses independent genuineK3 and preserved a"
            "uthorK7 count/seed/runID refs; fresh9883 reader rejects alte"
            "red modelplan/chronology/anchor with no fallback"
        ),
        (
            "Actual effective ExecConfig seeds/nativeK bridge independent"
            "lyGO0983; original owner acceptance pending, distinct seeds "
            "not stochastic-law evidence"
        ),
    ),
    "B172": (
        (
            "@scientist-owners backtest trust-purpose/profile accountable"
            " owner; E-W01 implementation"
        ),
        (
            "Versioned trust-grade purpose, admissible sampling assumptio"
            "ns and where equivalence required meaningful-bias margin+equ"
            "ivalence interval rule"
        ),
        (
            "Profile-bound independent tests distinguish constant nonzero"
            ",zero,unavailable/degenerate inference and equivalence; Grad"
            "eA remains denied until admission"
        ),
        (
            "No new math fix identified; institutional/profile decision r"
            "equired, p>alpha not neutrality"
        ),
    ),
    "B173": (
        (
            "@scientist-owners backtest trust-purpose/profile accountable"
            " owner; E-W01 implementation"
        ),
        (
            "Same versioned purpose/sampling/equivalence profile plus dec"
            "lared allowed degraded inference behavior"
        ),
        (
            "Actual SciPy t/df/p and unavailable-SciPy controls retain de"
            "scriptive magnitude; owner-approved profile independently de"
            "cides eligibility"
        ),
        (
            "SciPy degraded guard exists; no normal f"  # Exact value.
            "allback; external profile unresolved"  # Exact value.
        ),
    ),
    "B188": (
        "E-W03 law admission and @foundry-owners calibration/source-law producer",
        (
            "Supported canonical joint/product law with parameter axis/or"
            "der, ordered shared draws/weights/units, exact content+sourc"
            "e/model/fit provenance; actual CAL posterior carrier only if"
            " emitted"
        ),
        (
            "Source-owner input→configured producer/CAS→fresh all-backend"
            " sampler yields same law/nullspace, with reordered rows/weig"
            "hts/stale digest refusal before callbacks"
        ),
        (
            "Finite-machine mathematical inlet repairedd69/independentGO;"
            " actual producer law authority remains not_established"
        ),
    ),
    "B190": (
        (
            "@scientist-owners served simulation/Jacobian/execution produ"
            "cer; E-W03 propagation adapter"
        ),
        (
            "Declared real configured model execution seam, evaluator/res"
            "ponse or source-bound Jacobian, input/output parameter/unit "
            "mapping and exact source/fit/law refs"
        ),
        (
            "Real native producer→persisted sensitivity→configured propag"
            "ation consumer reproduces zero-baseline and actual JAX deriv"
            "atives; present-but-fake map refuses"
        ),
        (
            "Real producer bridge absent; cannot invent served evaluator/"
            "authoritative sensitivity map from current affine proxy"
        ),
    ),
    "B192": (
        (
            "@foundry-owners configured CAL exact-law carrier producer; E"
            "-W03 MC/QMC consumer; IR owner for future v2"
        ),
        (
            "If multivariate posterior emitted: joint_law_sha256,joint_pa"
            "rameter_order,ordered joint_draw_ids,canonical weights/units"
            " and content-bound CAS lineage"
        ),
        (
            "Actual supported producer→CAS→fresh sampler preserves empiri"
            "cal atoms and pairing; stale digest/order/weights refuses; n"
            "ew v2 output only after B202 ratification"
        ),
        (
            "Existing finite-law inlet repaired; CAL source carrier input"
            " missing and B202 new-wire choice held"
        ),
    ),
    "B193": (
        (
            "E-W03 estimator-method owner; @scientist-owners configured e"
            "valuator/source-law producer"
        ),
        (
            "Actual evaluator functional/recipe, one admitted IID[0,1]pil"
            "ot+main law and bounded response; alternate statistic requir"
            "es named theorem/stopping/scramble profile"
        ),
        (
            "Configured actual mean certificate fresh readback recomputes"
            " independent pilot/frozenN/pilot exclusion; RQMC uses full i"
            "ndependent scrambles and replicate statistic error"
        ),
        (
            "Current canonical indicator certificate exists; opaque serve"
            "d laws/quantile/CDF/interval/anytime stopping not establishe"
            "d"
        ),
    ),
    "B194": (
        (
            "@scientist-owners served simulation/domain/retry producer an"
            "d @foundry-owners source-law owner; G exact local read-only "
            "checker"
        ),
        (
            "Named actual evaluator/serving seam, per-input admissible do"
            "main and same-input transient-vs-structural classifier/retry"
            "/completion contract with source law"
        ),
        (
            "Actual configured evaluator preserves all requested terminal"
            " IDs/outcomes/missing mass; fresh consumer refuses unconditi"
            "onal mean without completion; negative-support fixture stays"
            " conditional"
        ),
        (
            "Held technical producer boundary: existing strict generic su"
            "pport mechanism does not identify real served evaluator/doma"
            "in law"
        ),
    ),
    "B197": (
        (
            "E FRC writer now owns narrow legacy PropagateUncertaintyNode"
            " calibration-reader repair; @foundry-owners configured Calib"
            "rator/model/source-fit; @scientist-owners welfare/served wor"
            "kflow; @ir-owners enforcement contract"
        ),
        (
            "For codefix: actual native Calibratorv2→configuredCAS→Propag"
            "ateUncertaintyNode with wrongkind/schema/hash-valid forged p"
            "ayload refusals. For authority: real source/noise/model/fit/"
            "objective/row joins and named served consumer profile"
        ),
        (
            "Strict legacy calibration reader verifies kind/schema/canoni"
            "cal payload before admitting any envelope; actual native pos"
            "itive+forged negatives reviewed on exactnewSHA. Sourcefit au"
            "thority separately staysheld until owner input; independentl"
            "yGO1e942 reader fix awaits receipt/appendmerge"
        ),
        (
            "Legacy loader bypass still exists in rootf445; FRC source1e9"
            "42 repairs actual native CAS reader and root reports indepen"
            "dentGO, receipt+appendmergepending. Strictwelfare report rea"
            "der alreadycorrect. Real source/noise law remains separatehe"
            "ld boundary"
        ),
    ),
    "B200": (
        (
            "@foundry-owners/@scientist-owners evidence/source informatio"
            "n relationship producer; E-W03 aggregator; @ir-owners contra"
            "ct review"
        ),
        (
            "Content-bound information-unit refs, likelihood vs prior/pos"
            "terior roles, shared data/model lineage and independently ad"
            "mitted relationships/units"
        ),
        (
            "Source producer→relationship artifact→fresh aggregator count"
            "s independent information units; four copies stay std1, trul"
            "y independent measurements differ; forged origin/flags deny "
            "authority"
        ),
        (
            "No information relationship producer/input authority; consum"
            "er_asserted arithmetic remains nongating"
        ),
    ),
    "B201": (
        (
            "Human-appointed canonical IR uncertainty semantic owner; @ir"
            "-owners/@architecture-owners appoint, current enforced revie"
            "wer@DenisKopylov"
        ),
        (
            "Named accountable semantic owner and ratification/amendment "
            "of four finite decisions in tracked IR decision packet; func"
            "tionals/quantile conventions/units/invalid refusals"
        ),
        (
            "Owner-signed tracked decision selects distinctv2$id+independ"
            "ent point/interval functionals; E later proves99zeros+100 me"
            "an1,equal-tail[0,0] without widening and retainsv1.1replay"
        ),
        (
            "Held unratified wire semantics; team-polisyos library owners"
            "hip is not semantic appointment"
        ),
    ),
    "B202": (
        (
            "Human-appointed canonical IR semantic owner; then E producer"
            " and C/F appointed consumers"
        ),
        (
            "Same four ratifications; CAS-onlyv2(recommended)or inline+pe"
            "rsistedref, exact axes/order/shareddrawIDs/weights/units/sou"
            "rce/model/fit/rule/time/purpose and real consumer appointmen"
            "ts"
        ),
        (
            "Ratified producer→configuredCAS→fresh sampler distinguishes "
            "same summaries/different laws and paired+1/-1 after reopen; "
            "unresolved law computations refuse"
        ),
        (
            "Held semantic carrier/functionals decisi"  # Exact value.
            "on; E/G code cannot ratify new wire cont"  # Exact value.
            "ract"  # Exact value.
        ),
    ),
    "LA-052": (
        (
            "PCL-01 E-W08 and @scientist-owners calibration API; @foundry"
            "-owners actual default diagnostics caller"
        ),
        (
            "Reviewedffd native graph→runner configured CAS source/pairs/"
            "report/receipt refs; exact target/unit/entity/time/source ro"
            "ws for application claim"
        ),
        (
            "Accountable owner individually adjudicates generic criterion"
            " from native graph+freshstore independent100pairreadback and"
            "95/100,0/100,empty/missing/reordered/forged negatives"
        ),
        (
            "Former E default-store defect repaired and independently rev"
            "iewed; no extra production corpus intrinsic to generic repor"
            "t/pairs criterion; full productionauthority remains limited"
        ),
    ),
    "LA-053": (
        (
            "polisyos.calibration owner and Scientist backtesting alias m"
            "igration/test owner; @scientist-owners with @architecture-ow"
            "ners"
        ),
        (
            "Explicit jointly approved compatibility/deprecation window, "
            "supported old/new APIs and actual external caller inventory"
        ),
        (
            "Tracked joint owner decision/inventory plus actual alias ide"
            "ntity/runtime/numerical replay; alias remains until approved"
            " window"
        ),
        (
            "Mechanism/class/test migration implemented; external API win"
            "dow/input decision missing, no unapproved sunset"
        ),
    ),
    "LA-054": (
        (
            "DDM-02 E-W05; @scientist-owners current-"  # Exact value.
            "feed/applicability/registry deployment o"  # Exact value.
            "wners"  # Exact value.
        ),
        (
            "Actual report/model/rule/source/window/invalidation orderedr"
            "efs and currentfeed delivery/completeness+delayed-event fres"
            "hness profile; exact served reader version/routing"
        ),
        (
            "Read-only actual source→registryv2→fresh rebind/veto→served "
            "deployment consumer; delayed/missing event/feed/schema sourc"
            "e negative cannot inherit historicalpass"
        ),
        (
            "Directional reader defect repaired4c5; actual currentfeed/fr"
            "eshness and served consumer inputs remain absent"
        ),
    ),
    "LA-055": (
        (
            "DDM-02 E-W05; @scientist-owners deployment-purpose owner and"
            " named institutional R2 signoff authority"
        ),
        (
            "Versioned deployment purpose/R-state policy, identity-bound "
            "institutional R2 approval and observed-empty vs unavailable "
            "complete feed provenance"
        ),
        (
            "Actual consumer verifies independent baseline/veto/R2 signof"
            "f ordering and fresh valid source; R1/R0/failure/R4R3veto ca"
            "nnot be overridden after reopen"
        ),
        (
            "Library gate consistency implemented; boolean signoff/empty "
            "synthetic triggers not institutional authority"
        ),
    ),
}

rows = []
for old in prior["rows"]:
    fid = old["finding_id"]
    cov = covered[fid]
    bids = list(old["bundle_ids"])
    first = bids[0]
    family = (
        "MC"
        if first.startswith("UQP")
        else "UQS"
        if first.startswith("UQS")
        else first.split("-")[0]
    )
    card_refs = [f"{bundles[b]['criterion_card']}@{SNAPSHOT}" for b in bids]
    status = old["ledger_status_preserved"]
    next_owner, minimal, next_result, residual = external.get(
        fid,
        (
            old["next_owner"],
            (
                "Exact original card, existing bounded/na"
                "tive receipt and fresh combined candidat"
                "e dependency review; no production corpu"
                "s required for the generic arithmetic/co"
                "ntrol-flow/import property"
            ),
            (
                "Accountable original finding owner indiv"
                "idually accepts or rejects the preserved"
                " bounded proposal using defining-propert"
                "y oracle/negative and exact candidate ev"
                "idence; G admits code separately"
            ),
            old["remaining_condition"],
        ),
    )
    row = {
        "id": fid,
        "bundle_ids": bids,
        "source_closure_owner_literal": cov["source_closure_owner_literal"],
        "bundle_writers": {b: bundles[b]["writer"] for b in bids},
        "criterion": old["criterion"],
        "original_card_refs": card_refs,
        "original_source_criterion_refs": old["criterion_refs"],
        "ledger_status_preserved": status,
        "historical_bounded_proposal": fid in bounded,
        "historical_bucket": "held"
        if fid in held
        else "closed_regression"
        if fid == "B198"
        else "partial_active_residual"
        if fid in active
        else "partial_bounded_proposal_pending_owner",
        "proposed_verdict": "held" if fid in held else "closed" if fid == "B198" else "limited",
        "finding_owner_acceptance": "existing closed regression retained"
        if fid == "B198"
        else "not decided; historical status unchanged",
        "formal_ledger_change": False,
        "family_evidence": family,
        "prior_exact_scoped_evidence": {
            "statement": old["deciding_scoped_evidence"],
            "receipt": old["receipt_ref"],
            "source_sha": old["accepted_source_sha"],
            "oracle_negative_detail_location": (
                "Original card + exact referenced receipt; historical frozen "
                "wave is not a new assembled-candidate PASS"
            ),
        },
        "current_property_status": (
            "new0983 native class repair independentlyGO/source-present; "
            "original finding owner acceptance pending"
        )
        if fid in {"B166", "B169", "B170"}
        else (
            "Available source1e942 readerrepair independentlyGO by root; "
            "not yet mergedf445/receiptpublished; historicalheld/sourceau"
            "thority remains"
        )
        if fid == "B197"
        else "new bounded defining-property evidence ready for individual owner"
        if fid == "LA-052"
        else "preserved bounded evidence with explicit remaining boundary",
        "implementation_residual_or_external_boundary": residual,
        "next_owner": next_owner,
        "minimal_inputs": minimal,
        "next_verifiable_result": next_result,
        "gate_predicate_basis": family_meta[family]["P37"],
        "new_code_present": family in {"MC", "CAL", "DOE", "DDM", "PCL", "FRC"},
        "root_wave_outcome": (
            "UNRUN on assemblingf445; one combined wave after all source/"
            "dependency reviews and freeze"
        ),
    }
    if fid in {"B185"}:
        row["additional_exact_source"] = (
            "2643672263971584dcdcf347c6a93c3122d7e7ae real Calibrator lax"
            ".map batch; unchanged property retained, not repeated by CAL"
            " scalar delta"
        )
    if fid == "B198":
        row["regression_rule"] = (
            "Closed stays closed unless a new defining-property falsifier"
            " disproves it; no new falsifier established"
        )
        row["minimal_inputs"] = (
            "Existing closed regression source/report/native replay and e"
            "xact display levels.8/.95; no new closure decision or produc"
            "tion input required"
        )
        row["next_verifiable_result"] = (
            "Retain closed and rerun exact typed sigma/display-level regr"
            "ession in final common wave; only a new defining-property fa"
            "lsifier may reopen it"
        )
        row["implementation_residual_or_external_boundary"] = (
            "No new defining-property falsifier established; closed regre"
            "ssion retained, never treated as a pending closure proposal"
        )
    if fid in {"B201", "B202"}:
        row["semantic_decision_packet"] = f"{R2}ir-semantic-owner-decision.json@{SNAPSHOT}"
    rows.append(row)

# Name the historical controls and denominator per original bundle, retaining
# their exact old source. These are not current-candidate test outcomes.
for row in rows:
    checks = []
    wanted = {
        "tests.unit.remediation.test_" + b.lower().replace("-", "_") for b in row["bundle_ids"]
    }
    for evidence in next(r for r in prior["rows"] if r["finding_id"] == row["id"])[
        "common_wave_check_evidence"
    ]:
        job = obj(evidence["job_ref"])
        xml_bytes = read(evidence["junit_ref"])
        selected = [
            case
            for case in _safe_xml_fromstring(xml_bytes).iter("testcase")
            if case.attrib.get("classname") in wanted
        ]
        if row["id"] == "B183":
            selected = [
                case
                for case in selected
                if "fresh" in case.attrib["name"]
                and ("otel" in case.attrib["name"] or "noop" in case.attrib["name"])
            ]
        if row["id"] == "B198":
            selected = [case for case in selected if "typed_normal_scale" in case.attrib["name"]]
        for case in selected:
            state = (
                "FAIL"
                if case.find("failure") is not None
                else "ERROR"
                if case.find("error") is not None
                else "SKIP"
                if case.find("skipped") is not None
                else "PASS"
            )
            classname = case.attrib["classname"]
            selector = classname.replace(".", "/") + ".py::" + case.attrib["name"]
            checks.append(
                {
                    "selector": selector,
                    "historical_state": state,
                    "source_sha": job["candidate_sha"],
                    "published_junit_ref": f"{evidence['junit_ref']}@{SNAPSHOT}",
                    "published_job_ref": f"{evidence['job_ref']}@{SNAPSHOT}",
                    "group_denominator": evidence["test_counts"],
                    "scope": (
                        "Named original-bundle controls only; his"
                        "torical source58e, not new assembled-can"
                        "didatePASS or automatic individual crite"
                        "rionclosure"
                    ),
                }
            )
    row["named_historical_control_evidence"] = {
        "exact_example_selectors": [
            {k: c[k] for k in ("selector", "historical_state")} for c in checks[:8]
        ],
        "complete_named_bundle_denominator": len(checks),
        "source_sha": prior["review_source_sha"],
        "full_selector_location": (
            "Original frozenXML and preserved per-finding criterion-speci"
            "fic fields; examples are bounded navigation, not a complete "
            "finding verdict"
        ),
    }
    oldrow = next(r for r in prior["rows"] if r["finding_id"] == row["id"])
    row["preserved_per_finding_extended_evidence"] = {
        k: v
        for k, v in oldrow.items()
        if (
            k.startswith("latest_author_")
            or k
            in (
                "criterion_specific_actual_xml_checks",
                "independent_extra_evidence",
                "independent_review_refs",
                "common_wave_check_evidence",
            )
        )
        and v is not None
    }
    row["defining_property_predicate"] = {
        "property": row["criterion"],
        "basis": (
            "recomputed actual runtime property in exact referenced nativ"
            "e controls; declared source/noise/profile/semantic authority"
            " is separately consumer_asserted or not_established"
        ),
        "oracle": row["prior_exact_scoped_evidence"]["statement"],
        "negative_and_oracle_detail_ref": row["prior_exact_scoped_evidence"]["receipt"],
        (
            "current_component_output_refs"  # Exact value.
        ): (
            "family_evidence/"  # Exact value.
            f"{row['family_evidence']}"  # Exact value.
            "/deciding_output_refs"  # Exact value.
        ),
    }
    if row["id"] == "B183":
        row["defining_property_predicate"].update(
            {
                "property": (
                    "Every optimizer restart enters a newly c"
                    "reated OTel or noop context manager; no "
                    "exhausted span reuse on secondstart"
                ),
                "oracle": (
                    "Two actual starts enter distinct reusabl"
                    "e context lifetimes and complete; enabli"
                    "ng OTel does not change candidate behavi"
                    "or"
                ),
                "negative": (
                    "Reuse a one-shot context across starts makes second entry fa"
                    "il; named freshOTel/noop controls detect it"
                ),
                "basis": (
                    "recomputed actual context creation/entry count perrestart; n"
                    "o Hessian or scientific-authority implication"
                ),
            }
        )

for row in rows:
    if row["id"] in {"B188", "B192", "B194"}:
        row["implementation_residual_or_external_boundary"] = (
            "Additional current E-owned welfare sibling law defect: real "
            "empirical carrier is replaced by Normal; root-confirmed nati"
            "ve witness100/100draws outside atoms and failed supportmass."
            "5 hidden. BKT writer repairing common welfare law/sampler/su"
            "pport class; new native artifact/oracle/removal review requi"
            "red. "
        ) + row["implementation_residual_or_external_boundary"]
        row["current_property_status"] = (
            "CommonMCd69 finite law mechanismGO; real welfare consumer si"
            "bling has active implementablelaw/support blocker; closure n"
            "ot hidden by sourceauthorityhold"
        )
        row["next_owner"] = (
            "E BKT writer owns welfare empirical sampler/support classfix"
            " and independentreviewer; then "
        ) + row["next_owner"]
        row["next_verifiable_result"] = (
            "Real configured empirical welfare->actualnative GE evaluator"
            " preserves atoms/pairedlaw/requestedoutcomes and mass.5faile"
            "d support through freshCAS; off-supportdraw/failurehidden ne"
            "gatives reject on exactrepairSHA; then "
        ) + row["next_verifiable_result"]
    if row["id"] == "B197":
        row["available_component_fix"] = {
            "source_sha": "1e942ff624ae7cb6c71227d48eef760687e17d2b",
            "tree": git("rev-parse", "1e942ff624ae7cb6c71227d48eef760687e17d2b^{tree}")
            .decode()
            .strip(),
            "state": (
                "Root reports independentGO for nativeCal"
                "ibratorv2->CAS->legacyNode kind/schema/c"
                "anonicalpayload repair; publicationrecei"
                "pt/appendmerge not yet available at f445"
                " snapshot"
            ),
            "finding": "held remains; source/noiselaw authority separate",
        }
        for path in (
            git(
                "diff",
                "--name-only",
                "1e942ff624ae7cb6c71227d48eef760687e17d2b^",
                "1e942ff624ae7cb6c71227d48eef760687e17d2b",
            )
            .decode()
            .splitlines()
        ):
            read(path, "1e942ff624ae7cb6c71227d48eef760687e17d2b")

current_recipes = []
for historic in recipes["recipes"]:
    current = json.loads(json.dumps(historic))
    current["implementation_sha_for_this_recipe"] = SOURCE
    current["implementation_tree"] = git("rev-parse", SOURCE + "^{tree}").decode().strip()
    current["topic"] = "codex/e02-E-continuation-20261006"
    current["historical_recipe_preserved_ref"] = (
        f"{CONT}closure-frozen/local-G-closeout-recipes.json@{SNAPSHOT}"
    )
    current["tracked_receipt_ref"] = family_meta[
        {"backtest": "BKT", "mc": "MC", "cal": "CAL", "frc": "FRC", "ddm": "DDM"}[current["family"]]
    ].get("new_receipt")
    current["execution_state"] = (
        "owner input required for factual authority; generic math/mec"
        "hanism witness is available separately; no production data m"
        "oves tocloud"
    )
    if current["family"] == "backtest":
        current["why_local"] = (
            "Generic native default replay is independently positive on09"
            "83 and present5d. Local read-only history is needed only for"
            " an actual historical/source claim, not to defer the generic"
            " native bridge."
        )
        current["minimal_inputs"][1] = (
            "Actual source,Trinity,registry refs admitted by the existing"
            " default workflow, with canonical NativeForecastProfile targ"
            "et/unit/time/horizon; the generic native binding now exists "
            "and is not missing."
        )
        current["actual_api_sequence"] = [
            (
                "prepare_native_replay(configuredCAS,Hist"
                "oricalValidationPlan,historical_data) va"
                "lidates original source/Trinity/registry"
                " and derives immutable masked snapshot/m"
                "atchingTrinity/materializer."
            ),
            (
                "BacktestOrchestrator.run uses default Sc"
                "ientist run_experiment/RunSimulationNode"
                " -> execute_native_forecast(ctx,ExecuteR"
                "equest,native_request_ref), effective Ex"
                "ecConfig.seed and actual native perstep "
                "execution."
            ),
            (
                "Freshload_native_forecast configuredCAS "
                "resolves actual initialanchor,clock prog"
                "ression,binding/poststate lineage,Simula"
                "tionResult.ExecPlan->ProgramGraph/Lowere"
                "dIR->Trinity and source/registry joins; "
                "independently compare local source row I"
                "Ds,target/unit/time/horizon/counts/actua"
                "lseeds."
            ),
        ]
        current["deciding_controls"] = receipts["BKT"]["negative_controls"]
        current["bounded_mechanism_commands"] = [
            (
                "(cd policy-engine && uv run --no-sync py"
                "thon -m pytest -o addopts= -q tests/unit"
                "/scientist/methods/backtesting/test_nati"
                "ve_replay.py)"
            ),
            (
                "(cd policy-engine && uv run --no-sync py"
                "thon -m pytest -o addopts= -q tests/unit"
                "/scientist/methods/backtesting/test_nati"
                "ve_replay.py -k refuses_unadmitted)"
            ),
        ]
        current["code_review_ref"] = family_meta["BKT"]["independent_review_ref"]
        current["implementation_commits"] = receipts["BKT"]["implementation_commits"]
    elif current["family"] == "frc":
        current["minimal_inputs"].append(
            "ForecastOwnerRequestv2 explicit unit/numeric_scale and resol"
            "vable canonical sourceDataSchema; current8486 preflight reje"
            "cts missing/mismatched schema/unit beforeETS callbacks. Use "
            "separately persisted empirical_evidence_ref/candidate_receip"
            "t_ref and to_s10_input_fields adapter."
        )
        current["implementation_commits"] = ["8486baad6fdef8063cfaad80b15f6b6d8532460a"]
        current["code_review_ref"] = family_meta["FRC"]["independent_review_ref"]
    elif current["family"] == "ddm":
        current["actual_api_sequence"] = [
            (
                "calibrate_detector -> build_calibration_"
                "audit -> DriftAndDegradationMonitor.eval"
                "uate_window -> build_model_registry_reco"
                "rd(schema_version=2)."
            ),
            (
                "Persist/reopen distinctv2 with ModelRegi"
                "stryReadinessRecord.model_validate_json;"
                " preserveoldv1wire/reader semantics and "
                "no implicit enriched-record downgrade."
            ),
            (
                "rebind_calibration_validity with exact o"
                "riginal report/audit/metric/readiness/or"
                "dered observations, then evaluate_regist"
                "ry_gate; [] must be genuine observedcomp"
                "lete feed,not unavailable."
            ),
            (
                "Institutional R2 signoff identity and deployment-purpose pol"
                "icy stay separate from synthetic bool/readiness/pass."
            ),
        ]
        current["implementation_commits"] = ["4c5afb1dc10b4e3f4dbc10b50ca6066de9b08ccb"]
        current["code_review_ref"] = family_meta["DDM"]["independent_review_ref"]
    elif current["family"] == "cal":
        current["code_blocker"] = (
            "Currentf445 root still has legacy genericCalibrationReport l"
            "oader bypass; available source1e942 repairs it and root repo"
            "rts independentGO. Receipt/appendmerge not yet in this snaps"
            "hot; use strictwelfare report reader for already established"
            " bounded projection. Rebind actual nativeCalibratorv2->CAS->"
            "Node positive and forgedkind/schema/payload to finalmergedSH"
            "A before defaultconsumerGO; source/noiselaw authority staysh"
            "eld."
        )
        current["implementation_commits"] = ["45b834534958c262a8146e6c4d847cf8d53846bc"]
    elif current["family"] == "mc":
        current["implementation_commits"] = ["d69d2fad34de9923209fde3e20439e46f36f6750"]
        current["current_numeric_boundary"] = (
            "Common exact finite-machine paired weight/CDF admission; tin"
            "ypositivecategory survives or pre-callbacktypedrefusal; unsu"
            "pportedUniformcovariance refusesbeforecallback0; Gaussian/nu"
            "llspace/empiricalcontrols remain."
        )
        if set(current["finding_ids"]) & {"B188", "B192", "B194"}:
            current["current_consumer_code_blocker"] = (
                "Welfare sibling empirical->Normal approx"
                "imation loses atom law and hides faileds"
                "upportmass.5; BKT writer repairing actua"
                "l native law/sampler/outcomes class. Fre"
                "sh actual GE evaluator, atoms/pairedrows"
                "/weights/support outcomes and negative r"
                "eceipts required on exactrepairSHA. Math"
                "ematical supportedMC inletGO is not this"
                " sibling consumerGO."
            )
    current_recipes.append(current)
recipe_packet = {
    "schema": "policyos.e02.E.local_recipes.current.v1",
    "implementation_sha": SOURCE,
    "implementation_tree": git("rev-parse", SOURCE + "^{tree}").decode().strip(),
    "historical_source": "58e2d97965c0826c44843a78dcb2f8698d9950a3",
    "historical_document_ref": f"{CONT}closure-frozen/local-G-closeout-recipes.json@{SNAPSHOT}",
    "production_data_rule": (
        "G executes localread-only onlywithminimum owner-issued immut"
        "able inputs; unavailableinput/backend=UNRUN/SKIP for check,n"
        "ever syntheticproductionPASS. No data copiedcloud."
    ),
    "common_protocol": recipes["common_G_protocol"],
    "recipes": current_recipes,
    "final_candidate_rebind": (
        "This wrapper is source-bound onf445; no local production che"
        "ck has yet executed, not a finalfreeze claim. After pending "
        "B197/dependency fixes root regenerates wrapper on exact fina"
        "lsourceSHA, fetch/readback verifiesit, then G checks that im"
        "mutable implementation."
    ),
}
dump("current-local-G-recipes.json", recipe_packet)

packet = {
    "schema": "policyos.e02.E.all54.reconciliation.v1",
    "unit": "E",
    "review_role": (
        "Read-only criterion/evidence reconciliation by pcl_r2. Autho"
        "r of PCL implementation; PCL code GO is quoted exclusively f"
        "rom independentddm_r2 review, not self-review."
    ),
    "input_snapshot_sha": SNAPSHOT,
    "input_snapshot_tree": git("rev-parse", SNAPSHOT + "^{tree}").decode().strip(),
    "assembled_source_sha": SOURCE,
    "assembled_source_tree": git("rev-parse", SOURCE + "^{tree}").decode().strip(),
    "G_audit_sha": "0346fc656a45ff2cd43d37126992d8ddbb739d10",
    "denominator": {
        "bundles": len(bundles),
        "findings": len(rows),
        "ID_to_bundle_links": sum(len(r["bundle_ids"]) for r in rows),
    },
    "ledger_status_counts_preserved": dict(
        collections.Counter(r["ledger_status_preserved"] for r in rows)
    ),
    "historical_buckets": {
        "partial_bounded_owner_proposals": 32,
        "partial_active_residuals": 17,
        "held": 4,
        "closed_regression": 1,
    },
    "decision_counts": dict(collections.Counter(r["proposed_verdict"] for r in rows)),
    "history_rule": (
        "32partial bounded proposals are preserved as individual owne"
        "r proposals, not accepted decisions;17historical partial act"
        "ive residuals stay identifiable even after a new bounded cod"
        "e repair. LA052 has a new native closure proposal, separatel"
        "y not automatic acceptance."
    ),
    "authority_rule": (
        "Code E bounded GO/G integration acceptance, check PASSFAILER"
        "RORSKIPUNRUN, original criterion owner acceptance and produc"
        "tion/semantic authority remain separate."
    ),
    "bundles": [
        {
            "id": b["id"],
            "writer": b["writer"],
            "finding_ids": b["finding_ids"],
            "original_card": b["criterion_card"],
        }
        for b in bundles.values()
    ],
    "family_evidence": family_meta,
    "rows": rows,
    "component_cut_reconciliation": component_reconciliation,
    "remaining_source_blocks": [
        {
            "owner": "E BKT writer and separate native law/support reviewer",
            "IDs": ["B188", "B192", "B194"],
            "state": (
                "Confirmed actual welfare empirical->Norm"
                "al/success-only support escape: native d"
                "raws100/100offatoms and failedmass.5hidd"
                "en. Implementable classfix underway; no "
                "sourceauthorityinput may defer it."
            ),
        },
        {
            "owner": "E FRC writer + independent reviewer",
            "IDs": ["B197"],
            "state": (
                "Rootf445 legacy calibration reader bypas"
                "s has available source1e942 repair with "
                "reported independentGO; authorreceipt/ap"
                "pendmerge pending. Source/noiseauthority"
                " remainsheld separately."
            ),
        },
        {
            "owner": "A generation-cycle/S10/default HTTP writer",
            "IDs": ["B32", "LA-051"],
            "state": (
                "E8486 source/schema/unit/adapter indepen"
                "dentlyGO and merged; A default verifier/"
                "status/HTTP code remains separatelyowned"
            ),
        },
        {
            "owner": "E facade/Core/IR/Foundry public-contract owners",
            "state": (
                "root14d narrow owned exports plus invent"
                "ory/architecture dependency review; cann"
                "ot broaden baseline/exceptions or public"
                " contract without owner admission"
            ),
        },
    ],
    "additional_E_residual_search": {
        "state": (
            "Rootconfirmed E code defects: B197 legacy CASreader bypass h"
            "as available1e942 independentlyGO source/receiptappendmergep"
            "ending; welfare empirical->Normal/failedmass hiding is activ"
            "eBKT writer classfix. Neither is hidden behind externalsourc"
            "eauthorityhold."
        ),
        "inspected_boundaries": [
            "UQP190 actual affine sensitivity vs real configured evaluator",
            (
                "UQP193 canonical bounded mean certificate and unsupported fu"
                "nctional/stopping law boundary"
            ),
            (
                "UQS200 duplicate origin/content and cons"  # Exact value.
                "umer_asserted independence nongating"  # Exact value.
            ),
            "CAL197 strict configured welfare/source-fit and legacy reader boundary",
            "PCL052 actual native graph/CAS default bridge",
            "DDM054055 fresh rebind/veto vs current feed/institutional signoff",
        ],
        "limit": (
            "This is criterion/source tracing, not a new full independent"
            " code review or numeric common wave; newly found downstream "
            "counterexamples must update the packet."
        ),
    },
    "owner_ready_packets": [
        f"{R2}core-ir-facade-owner-packet.json@{SNAPSHOT}",
        f"{R2}ir-semantic-owner-decision.json@{SNAPSHOT}",
        (
            f"{E}"  # Exact value.
            "doe-block-replay-20261006/D-consumer-pac"  # Exact value.
            "ket.md@"  # Exact value.
            f"{component['doe']['published_receipt_head']}"  # Exact value.
        ),
        f"{E}frc-source-measurement-r2/README.md@{new_receipts['FRC'][1]}",
    ],
    "local_G_recipe_ref": "current-local-G-recipes.json",
    (
        "historical_local_G_recipe_ref"  # Exact value.
    ): (
        f"{CONT}"  # Exact value.
        "closure-frozen/local-G-closeout-recipes."  # Exact value.
        "json@"  # Exact value.
        f"{SNAPSHOT}"  # Exact value.
    ),
    "local_G_rule": (
        "Full production law/history stays localread-only. Current ex"
        "plicit wrapper bindsf445 source/nativeAPI/controlIDs and pre"
        "serves old58 recipes separately; finalsource rebind is requi"
        "red after pending B197/dependency fixes. Generic BKT native "
        "bridge is positive and not a missing production dataset."
    ),
    "global_remaining_checks": [
        (
            "Rootsourcefreeze after welfare law/support classfix+independ"
            "entreview,1e942 strict reader receiptappendmerge/dependency "
            "checks, and facade review; BKT0983/FRC8486 reviews trackedGO"
        ),
        "One common numerical/gate wave on frozen assembled source",
        (
            "Architecture/import facade/contract inventory on exact denom"
            "inator; old reds need P41 fullbasecommandinputs replay"
        ),
        (
            "Repeat earlier fail-fast UNRUN workspace/CI-parity/Atlas umb"
            "rella stages after actual prerequisite repair"
        ),
        (
            "A/G generator owners confidence OpenAPI/FeedbackSolveResult "
            "schema manifest/trust-posture packets"
        ),
        (
            "Individual accountable owner acceptance of32historical parti"
            "al proposals plus newLA052 and B166/B169/B170 native proposa"
            "ls"
        ),
    ],
    "cleanup": {
        "policy": (
            "No checkout/environment/production data deleted. No native T"
            "rash established in cloud; exact repeatable receipts directo"
            "ry is a later cleanup candidate only after root copied track"
            "ed deciding packet and no active users."
        )
    },
    "P37_basis": prior["predicate_basis"],
    "P41_basis": (
        "Results navigation is source-reported compact baseline only;"
        " preserved historical frozen wave1123PASS2FAIL belongs to58e"
        ", notf445. New component oracles/removals are bound to their"
        " exact leaf cuts. BKT9c priorGO superseded by concrete count"
        "erexamples, then5ad/0983 corrective source independentlyGO; "
        "generic A ownership alone does not establish causal attribut"
        "ion of old FRC red. B197 extra source defect is explicitly r"
        "ecorded, not hidden by held."
    ),
}
for ref in packet["owner_ready_packets"]:
    path, commit = ref.rsplit("@", 1)
    read(path, commit)
dump("all-54-update.json", packet)
dump(
    "input-index.json",
    {
        "schema": "policyos.e02.git_inputs.v1",
        "input_snapshot_sha": SNAPSHOT,
        "inputs": list(inputs.values()),
    },
)
summary = [
    "# E all54 criterion/evidence reconciliation",
    "",
    f"Pinned tracked receipt snapshot `{SNAPSHOT}`; assembled reviewed-seven source `{SOURCE}`.",
    "",
    (
        "22bundles /54findings /55links. Historical ledger remains49p"
        "artial /4held /1closed.32partial bounded proposals need indi"
        "vidual owner acceptance;17historical partial active residual"
        "s are separately preserved. B198 closed regression retained;"
        " B194/B197/B201/B202 held."
    ),
    "",
    (
        "MCd69/CAL45b/DOEf07/DDM4c5/PCLffd/FRC8486/BKT0983 are source"
        "-present inf445 with tracked independent boundedGO reviews. "
        "G accepts code separately. No common numeric wave has run on"
        "f445. B197 strict readerrepair1e942 is available/reportedind"
        "ependentlyGO but not yet merged at this snapshot. Welfare em"
        "pirical->Normal/hidden failedmass classfix is activeBKT work"
        ". BKT9cHOLD remains historical; corrective0983 is GO."
    ),
    "",
    (
        "LA052 now has a real configured graph→runner→Advanced→CAS→fr"
        "eshreader witness; its generic original criterion needs no p"
        "roduction corpus. Its new finding proposal is not automatica"
        "lly accepted. LA053 requires a joint API compatibility windo"
        "w and caller inventory. D owns actual default Search; A owns"
        " default FRC trusted verifier/status/fresh HTTP surface; Cor"
        "e/IR/Foundry own cross-root facade/contract admission."
    ),
    "",
    (
        "The remaining free source work is explicit in remaining_sour"
        "ce_blocks; external inputs and the next verifiable result ar"
        "e per finding in all-54-update.json. Additional confirmed B1"
        "97 reader codefix is recorded separately from source/noise a"
        "uthority. This source/criterion trace is not a substitute fo"
        "r final numeric/architecture/consumer reviews."
    ),
    "",
    (
        "B172/B173 need trust purpose/profile/equivalence inputs; B19"
        "0 real response/Jacobian; B193 evaluator/law/functional/stop"
        "ping assumptions; B200 information-unit relationships; B197 "
        "actual source fit and named legacy enforcement seam; DDM act"
        "ual feed/freshness/R2 institutional input. Human-appointed I"
        "R semantic authority must ratify four finite decisions befor"
        "e E implements distinctv2; team-polisyos library owner is no"
        "t semantic appointment."
    ),
    "",
    (
        "Run `python3 validate.py --repo /workspace/e02-E-continuatio"
        "n-20261006 --negative` from this directory. It verifies exac"
        "t tracked Git input blobs and all54 ownership/status/denomin"
        "ators/component/root bindings; negatives mutate only in-memo"
        "ry packet copies. Numeric outputs remain referenced at their"
        " tracked exact authored/reviewed cuts."
    ),
    "",
    (
        "Production/history stays local read-only; G recipes require "
        "finalcandidate rebind. Nothing deleted; this external receip"
        "t directory is a later cleanup candidate only after root pub"
        "lication and no active users."
    ),
    "",
]
(OUT / "summary.md").write_text("\n".join(summary))
_write_stdout(
    json.dumps(
        {
            "state": "packet_written",
            "rows": len(rows),
            "bundles": len(bundles),
            "links": packet["denominator"]["ID_to_bundle_links"],
            "inputs": len(inputs),
            "bytes": (OUT / "all-54-update.json").stat().st_size,
        }
    )
)
