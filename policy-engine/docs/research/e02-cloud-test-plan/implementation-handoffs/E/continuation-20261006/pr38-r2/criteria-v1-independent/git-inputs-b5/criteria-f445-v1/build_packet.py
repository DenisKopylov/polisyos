#!/usr/bin/env python3
"""Reconcile existing tracked E closeout and exact component cuts without edits."""

import collections
import hashlib
import json
import pathlib
import subprocess
import xml.etree.ElementTree as ET

REPO = pathlib.Path("/workspace/e02-E-continuation-20261006")
OUT = pathlib.Path(__file__).resolve().parent
SNAPSHOT = "f445cbc3439b1539937e8e3f6df492bbd6c2e4a3"
SOURCE = SNAPSHOT
E02 = "policy-engine/docs/research/e02-cloud-test-plan/"
E = E02 + "implementation-handoffs/E/"
CONT = E + "continuation-20261006/"
R2 = CONT + "pr38-r2/"
inputs = {}


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def read(path, ref=SNAPSHOT):
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


def obj(path, ref=SNAPSHOT):
    return json.loads(read(path, ref))


def dump(name, data):
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
receipts = {
    family: obj(E + path, ref) for family, (path, ref, _) in new_receipts.items()
}
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
                "delta_owner": "FRC8486 forecast_owner companion; native PCL six-owned-paths remain exact; full root consumer wave pending"
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
for key, (name, ref, impl) in new_receipts.items():
    d = receipts[key]
    for path in d.get("mechanism_paths", []):
        if isinstance(path, str):
            read(path, impl)

family_meta = {
    "CAL": {
        "bundles": ["CAL-01", "CAL-02", "CAL-03", "CAL-04", "CAL-05", "CAL-06"],
        "producer": "Foundry measurement/compiler/preflight -> CalibratorInputs -> actual JAX Calibrator scalar/batch optimizer/final forward/Hessian",
        "artifact": "CalibrationReport v2 with exact objective/cache/config identity; report-owned coordinate covariance and CAS refs",
        "bridge": "Configured producer/report persistence and strict welfare projection; legacy IR sample reader enforcement is a separate owner seam",
        "consumer": "Calibrator selection/finalization; configured fresh welfare reader; actual default served model authority not established",
        "surface": "Typed report/native Calibrator and welfare artifacts, without production or causal authority",
        "new_property": receipts["CAL"]["runtime_property"],
        "oracle": "Known-sigma Gaussian NLL: MLE(1,2), Hessian diag(.25,1/9), inverse diag(4,9), SE(2,3). Pure scalar admission uses actual Calibrator loader/emitter counters: Python/NumPy bool ->0 calls; finite positive real float -> actual execution.",
        "negative": "Old exact58e boolean scales reach loader; new bool/np.bool_, zero, nonfinite, wrong type refuse before loader/emitter. Raw saddle/flat/negative/singular/ill-conditioned curvature never becomes valid covariance.",
        "P37": {
            "recomputed": "Support, axes, target weights, JAX grad/Hessian, finite scalar preflight, exact objective/cache and tie-map projection",
            "consumer_asserted": "Synthetic known noise/input mathematical profile, target/source declarations",
            "not_established": "Actual source fit/noise law, Calibrator/served authority and legacy enforcement adapter",
        },
    },
    "BKT": {
        "bundles": ["BKT-01", "BKT-02", "BKT-03", "BKT-04"],
        "producer": "Scientist BacktestOrchestrator -> immutable replay snapshot/Trinity/materializer -> actual DefaultFoundry/native execution",
        "artifact": "Typed target trajectory and execution request/output/binding refs -> BacktestReport CAS",
        "bridge": "Native snapshot/model/seed/output replay bridge; new chronological/initial-anchor/Trinity mismatch falsifiers are active blockers",
        "consumer": "Fresh BacktestReport and independently resolved source/forecast refs; grade scorer withholds trust without purpose/profile",
        "surface": "Native report diagnostics/library consumer; production-history claim remains local-only",
        "new_property": "Prior native K1/K7 author witness exists, but independent new review blocks approval pending chronological ordering, initial-anchor and actual Trinity/plan binding class repair.",
        "oracle": "Fresh exact masked row IDs/refs, requested=attempted=completed=K, failed=0; actual seeds/run IDs/typed forecast target/unit/time/horizon. Micro residual oracle[0,10,10]:sqrt(200/3); Student t fixtures t0/df2/p1 and t2.59807621135/df2/p.1216899343.",
        "negative": "Missing/mismatched Trinity, future/leaky rows, wrong target/horizon, counter-only fake producer, chronological loader/initial-anchor and actual plan-binding mismatch; unavailable SciPy degraded, not neutrality.",
        "P37": {
            "recomputed": "Diagnostic denominators, residuals, executed seeds/ref joins, split/horizon/row binding and actual trajectory",
            "consumer_asserted": "Exploratory synthetic profile; distinct seeds do not establish source-law independence",
            "not_established": "Owner trust-grade purpose/equivalence rule and production history",
        },
    },
    "DOE": {
        "bundles": ["DOE-01", "DOE-02", "DOE-03"],
        "producer": "Canonical capped/adaptive DoE and SALib1.5.2 seeded sampler/analyzer",
        "artifact": "Ordered complete plan/X/Y/analysis receipt in configured CAS, distribution/seed/scale/trajectory/counts/analyzer bound",
        "bridge": "SensitivityBridge -> fresh artifact reader -> SensitivityAwareCandidateGenerator.from_artifact; D default Search integration remains bridge_missing",
        "consumer": "Fresh-process recomputing analyzer/typed candidate generator; D owns actual SearchLoopRunner execution/ranking",
        "surface": "DoE/Sensitivity library artifact and typed _sensitivity refs; no separate search runtime",
        "new_property": receipts["DOE"]["property"]["statement"],
        "oracle": "Independent ANOVA: x,z iidU[0,1], y=x+z+2xz -> S1(.48,.48),S2=.04,ST(.52,.52), abs tolerance.01. Complete valid Saltelli block+pairedY reorder preserves point estimates(1e-12) while changing content/order; Morris physical(2,3), normalized(20,3).",
        "negative": "Zero indices with preserved shape, invalid/duplicate/missing/interior-mutated blocks, integrity-valid stale/forged S2 after fresh rebind, removed analyzer numerical recomputation; old exact58e shape-only proxy divergence.",
        "P37": {
            "recomputed": "Plan/X/Y/full block membership/order/denominator/distribution mapping and canonical analyzer fresh readback",
            "independently_reconciled": "ANOVA interaction indices and linear Morris unit oracle",
            "consumer_asserted": "Admitted experimental iid law/profile",
            "not_established": "Population/evaluator authority; D actual default Search consumer",
        },
    },
    "DDM": {
        "bundles": ["DDM-01", "DDM-02"],
        "producer": "Detector calibration -> calibration audit -> monitor.evaluate_window -> versioned model registry producer",
        "artifact": "Neutral ShiftEvent/budget contracts; distinct registry v2 record/schema with exact report/model/rule/quantity/time/invalidation refs",
        "bridge": "Fresh JSON schema reader/migration -> rebind original inputs -> independent veto/readiness gate",
        "consumer": "DDMWindowResult.registry_record library; served deployment/profile reader promotion remains owner action",
        "surface": "Internal polisyos.ddm lazy facade and actual registry record; no institutional signoff inferred",
        "new_property": receipts["DDM"]["property"]["statement"],
        "oracle": "Original strict closed v1 reader rejects actual v2 producer; current reader preserves actual old v1 bytes as nongating; native v2 fresh rebind/veto. DDM01 no-orchestration MetaPath,14 classes/enums,12 JSON/pickle models and LK35 differential preserved.",
        "negative": "Old same$id+four optional fields actual producer fails old strict reader; unknown/untyped/unversioned enriched record, forged source digest, R4/R3 veto after reopen/signoff, removed version guard/schema reader control. [] synthetic events is not a complete current feed.",
        "P37": {
            "recomputed": "Wire version/schema, exact source/input rebind, validity TTL/time roles and veto precedence",
            "consumer_asserted": "Synthetic bounded calibration/feed declaration and boolean signoff",
            "not_established": "Actual feed completeness/freshness, deployment purpose/institutional R2 human authority",
        },
    },
    "PCL": {
        "bundles": ["PCL-01"],
        "producer": "Configured execute_program_graph -> MethodDispatcher -> NumpyRunner -> actual Advanced segment/overall/scenario interval diagnostics",
        "artifact": "Source PanelData plus ordered requested/eligible/observed pairs, diagnostics/report/receipt in same configured CAS",
        "bridge": "Local params service override trusted graph store, scientific/state payloads exclude CAS service; existing native result refs",
        "consumer": "Fresh FileSystemCAS load_continuous_evaluation independently joins source entity/time/index rows to persisted intervals; existing execute derived-ref surface",
        "surface": "Native method results/ExecuteResult derived refs; source authority not_established and gate_eligible=false",
        "new_property": receipts["PCL"]["property"]["statement"],
        "oracle": "Actual native arch fit reopened100 paired source rows:82/100 coverage, nominal.95, ECE.13. Separate95/100,0/100,zero/incomplete pairs arithmetic; fresh store12 diagnostics artifacts*100source joins.",
        "negative": "Missing configured store nongating, fake client store cannot redirect trusted graph CAS; corrupted/missing/reordered persisted pairs, hash-valid forged count/receipt and property removal fail. Old58 exact inlet fails artifact_store parameter; historical helper-only pass did not prove native bridge.",
        "P37": {
            "recomputed": "Persisted report/receipt/pair counts and source row/time joins, configured CAS refs, arbitrary client store denied",
            "consumer_asserted": "Synthetic target/unit/split profile from typed PanelData",
            "not_established": "Production source/history authority; approved joint API compatibility sunset",
        },
    },
    "FRC": {
        "bundles": ["FRC-01", "FRC-02"],
        "producer": "Admitted ForecastOwnerRequest v2 -> canonical source schema/unit/scale preflight -> real MethodDispatcher NumPy ETS",
        "artifact": "Training+forecast bundle+BacktestReport; separate content-bound candidate receipt and empirical evidence in configured CAS",
        "bridge": "Fresh E candidate loader/to_s10_input_fields typed adapter; A default producer/verifier/generation-cycle/HTTP pending canonical writer",
        "consumer": "E independent source rows->persisted interval readback; A must resolve/recompute all profile/source/metric/unit/split/horizon/pairs/counts/threshold/purpose/six roles and verifier provenance on fresh served read",
        "surface": "E native predictive evidence; A S10/grade/S6/HTTP surface pending; terminal causal/treatment/policy refusal retained",
        "new_property": receipts["FRC"]["property"]["statement"],
        "oracle": receipts["FRC"]["property"]["independent_oracle"],
        "negative": receipts["FRC"]["property"]["negative_controls"],
        "P37": {
            "recomputed": "Resolved schema/unit/scale/split/pairs/time/ref integrity and independently source-bound observed interval coverage",
            "consumer_asserted": "Synthetic declared predictive purpose/profile; producer credible=True is not trusted verifier",
            "not_established": "A own configured verifier provenance/default HTTP read and production history",
        },
    },
    "MC": {
        "bundles": ["UQP-01", "UQP-02", "UQP-03"],
        "producer": "Common input-law/numeric admission -> analytical/delta/random/Sobol/Halton transform -> actual callback",
        "artifact": "Per-output envelopes, full addressed draw-outcome provenance and propagation config/report in CAS; exact finite joint carrier",
        "bridge": "Dispatcher common supported law admission pre-nominal callback; Scientist node/welfare strict fresh report adapter",
        "consumer": "Fresh CAS law/certificate/outcome reconciliation; generic served evaluator/domain authority unavailable",
        "surface": "Native propagation/welfare envelope refs remain nongating where assumptions/source unknown",
        "new_property": "One canonical exact finite-machine paired law; all positive CDF buckets retained or typed refusal before callbacks; supported covariance Gaussian/nullspace and empirical pairing controls retained.",
        "oracle": "Paired rows(0,0),(1,2),(4,5),mass1:1:2: ymean5.25,var15.1875,complete256net64/64/128callback rows. TiedGaussian difference variance0 vs independent.005. Independent256pilot fixed408main(mean certificate) excludes pilot; RQMC independent full nets replicate estimates.",
        "negative": "Tiny first/interior/last atoms, zero weights/U0/U1/adjacent CDF boundaries, near-but-distinct normalized weights, CDF collapse, reordered paired rows/stale digest; unsupported Uniform covariance before callback0; float32 range escape pre-draw; per-draw failure conditional≠unconditional.",
        "P37": receipts["MC"]["predicate_basis"],
    },
    "UQS": {
        "bundles": ["UQS-01"],
        "producer": "Existing uncertainty aggregation over admitted envelopes; new v2 exact-law producer awaits semantic ratification",
        "artifact": "v1.1 replay envelopes/provenance; future distinct v2 linked uncertainty/identification artifacts with exact joint-law CAS",
        "bridge": "Existing typed summary aggregation; cannot reconstruct a law from moments or inline summary",
        "consumer": "Existing nongating aggregator; actual new C/F law consumers must be appointed by ratified IR semantic owner",
        "surface": "v1.1 retained; v2 not implemented or silently ratified",
        "new_property": "Duplicate identity/level/type regression retained. B200 real information relationships unknown; B201/B202 four decisions unratified.",
        "oracle": "Same source copies preserve std1; precision combination is only conditional declared independent arithmetic, never verified information count.99zeros+100:mean1,q05/q95[0,0].Equal summaries/different laws and pairedcorrelation+1/-1 require distinct serialize/reopen law identities.",
        "negative": "Duplicate ref/content, conflicting same origin, missing independence, summary-only law queries and falsely widened equal-tail interval. B201/B202 oracle is reviewable discriminator, not a v2 implementation PASS.",
        "P37": {
            "recomputed": "Existing content/ref equality and fixed summary types/levels",
            "consumer_asserted": "Caller origins/independence flags; hypothetical v2 alternatives",
            "not_established": "Information-unit prior/likelihood/shared-data lineage and appointed semantic authority/new law consumers",
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
            "present, exact owned mechanism Git blobs equal reviewed leaf cut; no root numeric wave yet"
        )
    elif family == "FRC":
        d["independent_review_ref"] = (
            f"{R2}independent-reviews/frc/frc-independent-review-8486.json@{SNAPSHOT}"
        )
        d["code_review_state"] = (
            "E independently reviewed bounded8486GO; exact trackedCAL review, G acceptance/finding closure separate"
        )
        d["assembled_source_sha"] = SOURCE
        d["assembled_state"] = (
            "source-present after ordinary merge of publishedf73 receipt/source8486 into902d9f6 and successor5d4e010; no combined numeric wave"
        )
    elif family == "BKT":
        d["independent_review_ref"] = (
            f"{E}backtest-native-chain-admission-r2-checks/independent-review-go-0983.json@{SNAPSHOT}"
        )
        d["code_review_state"] = (
            "E independent bounded0983GO after concrete9cHOLD and corrective5ad; actual current source present; finding/G acceptance separate"
        )
        d["assembled_source_sha"] = SOURCE
        d["assembled_state"] = (
            "source-present by ordinaryappendmerge into5d4e010 and successorinventoryf445; native chronology/initialanchor/compiledTrinity joins repaired; no common numeric wave"
        )
        d["new_property"] = receipts["BKT"]["defining_property"]
        d["corrective_negative"] = receipts["BKT"]["negative_controls"]
        d["corrective_oracle"] = receipts["BKT"]["independent_oracle"]
    else:
        d["code_review_state"] = (
            "pending fix+fresh independent review; prior author positive does not overrule new blocker"
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
            "calibration-gaussian-noise-preflight-r2-20261006.frozen58-gaussian-scale.txt",
            "exactold58 actualloader bool falsifier",
        ),
        (
            "calibration-gaussian-noise-preflight-r2-20261006.candidate45b-gaussian-scale.txt",
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
            "pcl-configured-consumer-20261006-logs/pcl-74b26eb067de/native-witness-output.json",
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
            "backtest-native-chain-admission-r2-checks/independent-order-falsifiers-final.json",
            "independent genuineK3 positive plus five hash-valid chronology/anchor/Trinity forgeries reject",
        ),
        (
            "backtest-native-chain-admission-r2-checks/independent-order-falsifiers-removal.json",
            "removing actual compiledTrinity join accepts unexecutedtax50 with genuine tax25 outcomes; property-removal divergence",
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
            "frc-source-measurement-r2/checks/historical-base-measurement-configured.stdout",
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
        "A generation-cycle/S10/default HTTP writer; @runtime-owners and @scientist-owners",
        "E8486 configured CAS positive refs, correct request/profile/unit/source/split/horizon/rule/six actual times and A test/status patch packet",
        "A applies typed fields/default producer and separately recomputes evidence/provenance; fresh grade/S6/HTTP read agrees; missing_ref differs from resolved limited; causal refusal stays",
        "A bridge/verifier/default surface code remains implementable; E source/unit/adapter packet8486 merged902 and successor5d with exact trackedCAL independentGO",
    ),
    "LA-051": (
        "A generation-cycle/S10/default HTTP writer; E ForecastOwner/calibration writer (@scientist-owners)",
        "Exact separate E candidate/empirical refs, configured source/metric/unit/profile/split/horizon/pairs/counts/threshold/purpose/six roles and native packet",
        "A own verifier resolves/recomputes then fresh default+HTTP read; accepts predictive calibration only and retains terminal causal/treatment/policy refusal",
        "A trusted verifier/default bridge remains code; E8486 source preflight/adapter independentlyGO with tracked review and source-present5d",
    ),
    "B100": (
        "D default Search/autotune writer; @scientist-owners; E-W06 owns canonical numeric producer",
        "Tracked D-consumer-packet.md, configured CAS analysis ref, admitted plan/X/Y and declared experimental input law/evaluator purpose",
        "Actual SearchLoopRunner invokes canonical seeded producer/reader and consumes typed sensitivity refs in ranking; fresh persisted result+negative stale law/order",
        "D default Search bridge remains code; no second E search runtime",
    ),
    "B166": (
        "E-W01 BKT writer; @scientist-owners workflow/materializer with @foundry-owners execution input boundary",
        "Native immutable source/mask/Trinity/ModelSpec/plan refs and chronological source rows/valid initial anchor; exact candidate identity",
        "Accountable owner adjudicates native0983 exactmasked row/anchor/clock/model-plan joins using independent genuineK3+five hash-validforgeries; factual production history only if claimed",
        "Native source chronology/initialanchor/actualTrinity-plan class defects repaired5ad+0983 and independentlyGO; owner finding acceptance remains",
    ),
    "B169": (
        "E-W01 BKT writer; @scientist-owners typed forecast profile/materializer with @foundry-owners native producer",
        "Native typed target/unit/time/horizon trajectory refs with consistent model/Trinity execution binding",
        "Accountable owner adjudicates actual typed native trajectory on independentK3 and priorK7 witness; counters/scalar/wrongtarget/horizon and forgedTrinity refuse fresh",
        "Actual native replay bridge independentlyGO0983 and source-present; no counter/scalar/ETS substitution for this native boundary",
    ),
    "B170": (
        "E-W01 BKT writer; @scientist-owners workflow and @foundry-owners execution-config owner",
        "Actual per-run ExecuteRequest ExecConfig seeds/run IDs, fullK attempted/failed/success output refs and admitted matching plan",
        "Accountable owner uses independent genuineK3 and preserved authorK7 count/seed/runID refs; fresh9883 reader rejects altered modelplan/chronology/anchor with no fallback",
        "Actual effective ExecConfig seeds/nativeK bridge independentlyGO0983; original owner acceptance pending, distinct seeds not stochastic-law evidence",
    ),
    "B172": (
        "@scientist-owners backtest trust-purpose/profile accountable owner; E-W01 implementation",
        "Versioned trust-grade purpose, admissible sampling assumptions and where equivalence required meaningful-bias margin+equivalence interval rule",
        "Profile-bound independent tests distinguish constant nonzero,zero,unavailable/degenerate inference and equivalence; GradeA remains denied until admission",
        "No new math fix identified; institutional/profile decision required, p>alpha not neutrality",
    ),
    "B173": (
        "@scientist-owners backtest trust-purpose/profile accountable owner; E-W01 implementation",
        "Same versioned purpose/sampling/equivalence profile plus declared allowed degraded inference behavior",
        "Actual SciPy t/df/p and unavailable-SciPy controls retain descriptive magnitude; owner-approved profile independently decides eligibility",
        "SciPy degraded guard exists; no normal fallback; external profile unresolved",
    ),
    "B188": (
        "E-W03 law admission and @foundry-owners calibration/source-law producer",
        "Supported canonical joint/product law with parameter axis/order, ordered shared draws/weights/units, exact content+source/model/fit provenance; actual CAL posterior carrier only if emitted",
        "Source-owner input→configured producer/CAS→fresh all-backend sampler yields same law/nullspace, with reordered rows/weights/stale digest refusal before callbacks",
        "Finite-machine mathematical inlet repairedd69/independentGO; actual producer law authority remains not_established",
    ),
    "B190": (
        "@scientist-owners served simulation/Jacobian/execution producer; E-W03 propagation adapter",
        "Declared real configured model execution seam, evaluator/response or source-bound Jacobian, input/output parameter/unit mapping and exact source/fit/law refs",
        "Real native producer→persisted sensitivity→configured propagation consumer reproduces zero-baseline and actual JAX derivatives; present-but-fake map refuses",
        "Real producer bridge absent; cannot invent served evaluator/authoritative sensitivity map from current affine proxy",
    ),
    "B192": (
        "@foundry-owners configured CAL exact-law carrier producer; E-W03 MC/QMC consumer; IR owner for future v2",
        "If multivariate posterior emitted: joint_law_sha256,joint_parameter_order,ordered joint_draw_ids,canonical weights/units and content-bound CAS lineage",
        "Actual supported producer→CAS→fresh sampler preserves empirical atoms and pairing; stale digest/order/weights refuses; new v2 output only after B202 ratification",
        "Existing finite-law inlet repaired; CAL source carrier input missing and B202 new-wire choice held",
    ),
    "B193": (
        "E-W03 estimator-method owner; @scientist-owners configured evaluator/source-law producer",
        "Actual evaluator functional/recipe, one admitted IID[0,1]pilot+main law and bounded response; alternate statistic requires named theorem/stopping/scramble profile",
        "Configured actual mean certificate fresh readback recomputes independent pilot/frozenN/pilot exclusion; RQMC uses full independent scrambles and replicate statistic error",
        "Current canonical indicator certificate exists; opaque served laws/quantile/CDF/interval/anytime stopping not established",
    ),
    "B194": (
        "@scientist-owners served simulation/domain/retry producer and @foundry-owners source-law owner; G exact local read-only checker",
        "Named actual evaluator/serving seam, per-input admissible domain and same-input transient-vs-structural classifier/retry/completion contract with source law",
        "Actual configured evaluator preserves all requested terminal IDs/outcomes/missing mass; fresh consumer refuses unconditional mean without completion; negative-support fixture stays conditional",
        "Held technical producer boundary: existing strict generic support mechanism does not identify real served evaluator/domain law",
    ),
    "B197": (
        "E FRC writer now owns narrow legacy PropagateUncertaintyNode calibration-reader repair; @foundry-owners configured Calibrator/model/source-fit; @scientist-owners welfare/served workflow; @ir-owners enforcement contract",
        "For codefix: actual native Calibratorv2→configuredCAS→PropagateUncertaintyNode with wrongkind/schema/hash-valid forged payload refusals. For authority: real source/noise/model/fit/objective/row joins and named served consumer profile",
        "Strict legacy calibration reader verifies kind/schema/canonical payload before admitting any envelope; actual native positive+forged negatives reviewed on exactnewSHA. Sourcefit authority separately staysheld until owner input; independentlyGO1e942 reader fix awaits receipt/appendmerge",
        "Legacy loader bypass still exists in rootf445; FRC source1e942 repairs actual native CAS reader and root reports independentGO, receipt+appendmergepending. Strictwelfare report reader alreadycorrect. Real source/noise law remains separateheld boundary",
    ),
    "B200": (
        "@foundry-owners/@scientist-owners evidence/source information relationship producer; E-W03 aggregator; @ir-owners contract review",
        "Content-bound information-unit refs, likelihood vs prior/posterior roles, shared data/model lineage and independently admitted relationships/units",
        "Source producer→relationship artifact→fresh aggregator counts independent information units; four copies stay std1, truly independent measurements differ; forged origin/flags deny authority",
        "No information relationship producer/input authority; consumer_asserted arithmetic remains nongating",
    ),
    "B201": (
        "Human-appointed canonical IR uncertainty semantic owner; @ir-owners/@architecture-owners appoint, current enforced reviewer@DenisKopylov",
        "Named accountable semantic owner and ratification/amendment of four finite decisions in tracked IR decision packet; functionals/quantile conventions/units/invalid refusals",
        "Owner-signed tracked decision selects distinctv2$id+independent point/interval functionals; E later proves99zeros+100 mean1,equal-tail[0,0] without widening and retainsv1.1replay",
        "Held unratified wire semantics; team-polisyos library ownership is not semantic appointment",
    ),
    "B202": (
        "Human-appointed canonical IR semantic owner; then E producer and C/F appointed consumers",
        "Same four ratifications; CAS-onlyv2(recommended)or inline+persistedref, exact axes/order/shareddrawIDs/weights/units/source/model/fit/rule/time/purpose and real consumer appointments",
        "Ratified producer→configuredCAS→fresh sampler distinguishes same summaries/different laws and paired+1/-1 after reopen; unresolved law computations refuse",
        "Held semantic carrier/functionals decision; E/G code cannot ratify new wire contract",
    ),
    "LA-052": (
        "PCL-01 E-W08 and @scientist-owners calibration API; @foundry-owners actual default diagnostics caller",
        "Reviewedffd native graph→runner configured CAS source/pairs/report/receipt refs; exact target/unit/entity/time/source rows for application claim",
        "Accountable owner individually adjudicates generic criterion from native graph+freshstore independent100pairreadback and95/100,0/100,empty/missing/reordered/forged negatives",
        "Former E default-store defect repaired and independently reviewed; no extra production corpus intrinsic to generic report/pairs criterion; full productionauthority remains limited",
    ),
    "LA-053": (
        "polisyos.calibration owner and Scientist backtesting alias migration/test owner; @scientist-owners with @architecture-owners",
        "Explicit jointly approved compatibility/deprecation window, supported old/new APIs and actual external caller inventory",
        "Tracked joint owner decision/inventory plus actual alias identity/runtime/numerical replay; alias remains until approved window",
        "Mechanism/class/test migration implemented; external API window/input decision missing, no unapproved sunset",
    ),
    "LA-054": (
        "DDM-02 E-W05; @scientist-owners current-feed/applicability/registry deployment owners",
        "Actual report/model/rule/source/window/invalidation orderedrefs and currentfeed delivery/completeness+delayed-event freshness profile; exact served reader version/routing",
        "Read-only actual source→registryv2→fresh rebind/veto→served deployment consumer; delayed/missing event/feed/schema source negative cannot inherit historicalpass",
        "Directional reader defect repaired4c5; actual currentfeed/freshness and served consumer inputs remain absent",
    ),
    "LA-055": (
        "DDM-02 E-W05; @scientist-owners deployment-purpose owner and named institutional R2 signoff authority",
        "Versioned deployment purpose/R-state policy, identity-bound institutional R2 approval and observed-empty vs unavailable complete feed provenance",
        "Actual consumer verifies independent baseline/veto/R2 signoff ordering and fresh valid source; R1/R0/failure/R4R3veto cannot be overridden after reopen",
        "Library gate consistency implemented; boolean signoff/empty synthetic triggers not institutional authority",
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
            "Exact original card, existing bounded/native receipt and fresh combined candidate dependency review; no production corpus required for the generic arithmetic/control-flow/import property",
            "Accountable original finding owner individually accepts or rejects the preserved bounded proposal using defining-property oracle/negative and exact candidate evidence; G admits code separately",
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
        "proposed_verdict": "held"
        if fid in held
        else "closed"
        if fid == "B198"
        else "limited",
        "finding_owner_acceptance": "existing closed regression retained"
        if fid == "B198"
        else "not decided; historical status unchanged",
        "formal_ledger_change": False,
        "family_evidence": family,
        "prior_exact_scoped_evidence": {
            "statement": old["deciding_scoped_evidence"],
            "receipt": old["receipt_ref"],
            "source_sha": old["accepted_source_sha"],
            "oracle_negative_detail_location": "Original card + exact referenced receipt; historical frozen wave is not a new assembled-candidate PASS",
        },
        "current_property_status": "new0983 native class repair independentlyGO/source-present; original finding owner acceptance pending"
        if fid in {"B166", "B169", "B170"}
        else "Available source1e942 readerrepair independentlyGO by root; not yet mergedf445/receiptpublished; historicalheld/sourceauthority remains"
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
        "root_wave_outcome": "UNRUN on assemblingf445; one combined wave after all source/dependency reviews and freeze",
    }
    if fid in {"B185"}:
        row["additional_exact_source"] = (
            "2643672263971584dcdcf347c6a93c3122d7e7ae real Calibrator lax.map batch; unchanged property retained, not repeated by CAL scalar delta"
        )
    if fid == "B198":
        row["regression_rule"] = (
            "Closed stays closed unless a new defining-property falsifier disproves it; no new falsifier established"
        )
        row["minimal_inputs"] = (
            "Existing closed regression source/report/native replay and exact display levels.8/.95; no new closure decision or production input required"
        )
        row["next_verifiable_result"] = (
            "Retain closed and rerun exact typed sigma/display-level regression in final common wave; only a new defining-property falsifier may reopen it"
        )
        row["implementation_residual_or_external_boundary"] = (
            "No new defining-property falsifier established; closed regression retained, never treated as a pending closure proposal"
        )
    if fid in {"B201", "B202"}:
        row["semantic_decision_packet"] = (
            f"{R2}ir-semantic-owner-decision.json@{SNAPSHOT}"
        )
    rows.append(row)

# Name the historical controls and denominator per original bundle, retaining
# their exact old source. These are not current-candidate test outcomes.
for row in rows:
    checks = []
    wanted = {
        "tests.unit.remediation.test_" + b.lower().replace("-", "_")
        for b in row["bundle_ids"]
    }
    for evidence in next(r for r in prior["rows"] if r["finding_id"] == row["id"])[
        "common_wave_check_evidence"
    ]:
        job = obj(evidence["job_ref"])
        xml_bytes = read(evidence["junit_ref"])
        selected = [
            case
            for case in ET.fromstring(xml_bytes).iter("testcase")
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
            selected = [
                case for case in selected if "typed_normal_scale" in case.attrib["name"]
            ]
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
                    "scope": "Named original-bundle controls only; historical source58e, not new assembled-candidatePASS or automatic individual criterionclosure",
                }
            )
    row["named_historical_control_evidence"] = {
        "exact_example_selectors": [
            {k: c[k] for k in ("selector", "historical_state")} for c in checks[:8]
        ],
        "complete_named_bundle_denominator": len(checks),
        "source_sha": prior["review_source_sha"],
        "full_selector_location": "Original frozenXML and preserved per-finding criterion-specific fields; examples are bounded navigation, not a complete finding verdict",
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
        "basis": "recomputed actual runtime property in exact referenced native controls; declared source/noise/profile/semantic authority is separately consumer_asserted or not_established",
        "oracle": row["prior_exact_scoped_evidence"]["statement"],
        "negative_and_oracle_detail_ref": row["prior_exact_scoped_evidence"]["receipt"],
        "current_component_output_refs": f"family_evidence/{row['family_evidence']}/deciding_output_refs",
    }
    if row["id"] == "B183":
        row["defining_property_predicate"].update(
            {
                "property": "Every optimizer restart enters a newly created OTel or noop context manager; no exhausted span reuse on secondstart",
                "oracle": "Two actual starts enter distinct reusable context lifetimes and complete; enabling OTel does not change candidate behavior",
                "negative": "Reuse a one-shot context across starts makes second entry fail; named freshOTel/noop controls detect it",
                "basis": "recomputed actual context creation/entry count perrestart; no Hessian or scientific-authority implication",
            }
        )

for row in rows:
    if row["id"] in {"B188", "B192", "B194"}:
        row["implementation_residual_or_external_boundary"] = (
            "Additional current E-owned welfare sibling law defect: real empirical carrier is replaced by Normal; root-confirmed native witness100/100draws outside atoms and failed supportmass.5 hidden. BKT writer repairing common welfare law/sampler/support class; new native artifact/oracle/removal review required. "
            + row["implementation_residual_or_external_boundary"]
        )
        row["current_property_status"] = (
            "CommonMCd69 finite law mechanismGO; real welfare consumer sibling has active implementablelaw/support blocker; closure not hidden by sourceauthorityhold"
        )
        row["next_owner"] = (
            "E BKT writer owns welfare empirical sampler/support classfix and independentreviewer; then "
            + row["next_owner"]
        )
        row["next_verifiable_result"] = (
            "Real configured empirical welfare->actualnative GE evaluator preserves atoms/pairedlaw/requestedoutcomes and mass.5failed support through freshCAS; off-supportdraw/failurehidden negatives reject on exactrepairSHA; then "
            + row["next_verifiable_result"]
        )
    if row["id"] == "B197":
        row["available_component_fix"] = {
            "source_sha": "1e942ff624ae7cb6c71227d48eef760687e17d2b",
            "tree": git("rev-parse", "1e942ff624ae7cb6c71227d48eef760687e17d2b^{tree}")
            .decode()
            .strip(),
            "state": "Root reports independentGO for nativeCalibratorv2->CAS->legacyNode kind/schema/canonicalpayload repair; publicationreceipt/appendmerge not yet available at f445 snapshot",
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
    current["implementation_tree"] = (
        git("rev-parse", SOURCE + "^{tree}").decode().strip()
    )
    current["topic"] = "codex/e02-E-continuation-20261006"
    current["historical_recipe_preserved_ref"] = (
        f"{CONT}closure-frozen/local-G-closeout-recipes.json@{SNAPSHOT}"
    )
    current["tracked_receipt_ref"] = family_meta[
        {"backtest": "BKT", "mc": "MC", "cal": "CAL", "frc": "FRC", "ddm": "DDM"}[
            current["family"]
        ]
    ].get("new_receipt")
    current["execution_state"] = (
        "owner input required for factual authority; generic math/mechanism witness is available separately; no production data moves tocloud"
    )
    if current["family"] == "backtest":
        current["why_local"] = (
            "Generic native default replay is independently positive on0983 and present5d. Local read-only history is needed only for an actual historical/source claim, not to defer the generic native bridge."
        )
        current["minimal_inputs"][1] = (
            "Actual source,Trinity,registry refs admitted by the existing default workflow, with canonical NativeForecastProfile target/unit/time/horizon; the generic native binding now exists and is not missing."
        )
        current["actual_api_sequence"] = [
            "prepare_native_replay(configuredCAS,HistoricalValidationPlan,historical_data) validates original source/Trinity/registry and derives immutable masked snapshot/matchingTrinity/materializer.",
            "BacktestOrchestrator.run uses default Scientist run_experiment/RunSimulationNode -> execute_native_forecast(ctx,ExecuteRequest,native_request_ref), effective ExecConfig.seed and actual native perstep execution.",
            "Freshload_native_forecast configuredCAS resolves actual initialanchor,clock progression,binding/poststate lineage,SimulationResult.ExecPlan->ProgramGraph/LoweredIR->Trinity and source/registry joins; independently compare local source row IDs,target/unit/time/horizon/counts/actualseeds.",
        ]
        current["deciding_controls"] = receipts["BKT"]["negative_controls"]
        current["bounded_mechanism_commands"] = [
            "(cd policy-engine && uv run --no-sync python -m pytest -o addopts= -q tests/unit/scientist/methods/backtesting/test_native_replay.py)",
            "(cd policy-engine && uv run --no-sync python -m pytest -o addopts= -q tests/unit/scientist/methods/backtesting/test_native_replay.py -k refuses_unadmitted)",
        ]
        current["code_review_ref"] = family_meta["BKT"]["independent_review_ref"]
        current["implementation_commits"] = receipts["BKT"]["implementation_commits"]
    elif current["family"] == "frc":
        current["minimal_inputs"].append(
            "ForecastOwnerRequestv2 explicit unit/numeric_scale and resolvable canonical sourceDataSchema; current8486 preflight rejects missing/mismatched schema/unit beforeETS callbacks. Use separately persisted empirical_evidence_ref/candidate_receipt_ref and to_s10_input_fields adapter."
        )
        current["implementation_commits"] = ["8486baad6fdef8063cfaad80b15f6b6d8532460a"]
        current["code_review_ref"] = family_meta["FRC"]["independent_review_ref"]
    elif current["family"] == "ddm":
        current["actual_api_sequence"] = [
            "calibrate_detector -> build_calibration_audit -> DriftAndDegradationMonitor.evaluate_window -> build_model_registry_record(schema_version=2).",
            "Persist/reopen distinctv2 with ModelRegistryReadinessRecord.model_validate_json; preserveoldv1wire/reader semantics and no implicit enriched-record downgrade.",
            "rebind_calibration_validity with exact original report/audit/metric/readiness/ordered observations, then evaluate_registry_gate; [] must be genuine observedcomplete feed,not unavailable.",
            "Institutional R2 signoff identity and deployment-purpose policy stay separate from synthetic bool/readiness/pass.",
        ]
        current["implementation_commits"] = ["4c5afb1dc10b4e3f4dbc10b50ca6066de9b08ccb"]
        current["code_review_ref"] = family_meta["DDM"]["independent_review_ref"]
    elif current["family"] == "cal":
        current["code_blocker"] = (
            "Currentf445 root still has legacy genericCalibrationReport loader bypass; available source1e942 repairs it and root reports independentGO. Receipt/appendmerge not yet in this snapshot; use strictwelfare report reader for already established bounded projection. Rebind actual nativeCalibratorv2->CAS->Node positive and forgedkind/schema/payload to finalmergedSHA before defaultconsumerGO; source/noiselaw authority staysheld."
        )
        current["implementation_commits"] = ["45b834534958c262a8146e6c4d847cf8d53846bc"]
    elif current["family"] == "mc":
        current["implementation_commits"] = ["d69d2fad34de9923209fde3e20439e46f36f6750"]
        current["current_numeric_boundary"] = (
            "Common exact finite-machine paired weight/CDF admission; tinypositivecategory survives or pre-callbacktypedrefusal; unsupportedUniformcovariance refusesbeforecallback0; Gaussian/nullspace/empiricalcontrols remain."
        )
        if set(current["finding_ids"]) & {"B188", "B192", "B194"}:
            current["current_consumer_code_blocker"] = (
                "Welfare sibling empirical->Normal approximation loses atom law and hides failedsupportmass.5; BKT writer repairing actual native law/sampler/outcomes class. Fresh actual GE evaluator, atoms/pairedrows/weights/support outcomes and negative receipts required on exactrepairSHA. Mathematical supportedMC inletGO is not this sibling consumerGO."
            )
    current_recipes.append(current)
recipe_packet = {
    "schema": "policyos.e02.E.local_recipes.current.v1",
    "implementation_sha": SOURCE,
    "implementation_tree": git("rev-parse", SOURCE + "^{tree}").decode().strip(),
    "historical_source": "58e2d97965c0826c44843a78dcb2f8698d9950a3",
    "historical_document_ref": f"{CONT}closure-frozen/local-G-closeout-recipes.json@{SNAPSHOT}",
    "production_data_rule": "G executes localread-only onlywithminimum owner-issued immutable inputs; unavailableinput/backend=UNRUN/SKIP for check,never syntheticproductionPASS. No data copiedcloud.",
    "common_protocol": recipes["common_G_protocol"],
    "recipes": current_recipes,
    "final_candidate_rebind": "This wrapper is source-bound onf445; no local production check has yet executed, not a finalfreeze claim. After pending B197/dependency fixes root regenerates wrapper on exact finalsourceSHA, fetch/readback verifiesit, then G checks that immutable implementation.",
}
dump("current-local-G-recipes.json", recipe_packet)

packet = {
    "schema": "policyos.e02.E.all54.reconciliation.v1",
    "unit": "E",
    "review_role": "Read-only criterion/evidence reconciliation by pcl_r2. Author of PCL implementation; PCL code GO is quoted exclusively from independentddm_r2 review, not self-review.",
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
    "history_rule": "32partial bounded proposals are preserved as individual owner proposals, not accepted decisions;17historical partial active residuals stay identifiable even after a new bounded code repair. LA052 has a new native closure proposal, separately not automatic acceptance.",
    "authority_rule": "Code E bounded GO/G integration acceptance, check PASSFAILERRORSKIPUNRUN, original criterion owner acceptance and production/semantic authority remain separate.",
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
            "state": "Confirmed actual welfare empirical->Normal/success-only support escape: native draws100/100offatoms and failedmass.5hidden. Implementable classfix underway; no sourceauthorityinput may defer it.",
        },
        {
            "owner": "E FRC writer + independent reviewer",
            "IDs": ["B197"],
            "state": "Rootf445 legacy calibration reader bypass has available source1e942 repair with reported independentGO; authorreceipt/appendmerge pending. Source/noiseauthority remainsheld separately.",
        },
        {
            "owner": "A generation-cycle/S10/default HTTP writer",
            "IDs": ["B32", "LA-051"],
            "state": "E8486 source/schema/unit/adapter independentlyGO and merged; A default verifier/status/HTTP code remains separatelyowned",
        },
        {
            "owner": "E facade/Core/IR/Foundry public-contract owners",
            "state": "root14d narrow owned exports plus inventory/architecture dependency review; cannot broaden baseline/exceptions or public contract without owner admission",
        },
    ],
    "additional_E_residual_search": {
        "state": "Rootconfirmed E code defects: B197 legacy CASreader bypass has available1e942 independentlyGO source/receiptappendmergepending; welfare empirical->Normal/failedmass hiding is activeBKT writer classfix. Neither is hidden behind externalsourceauthorityhold.",
        "inspected_boundaries": [
            "UQP190 actual affine sensitivity vs real configured evaluator",
            "UQP193 canonical bounded mean certificate and unsupported functional/stopping law boundary",
            "UQS200 duplicate origin/content and consumer_asserted independence nongating",
            "CAL197 strict configured welfare/source-fit and legacy reader boundary",
            "PCL052 actual native graph/CAS default bridge",
            "DDM054055 fresh rebind/veto vs current feed/institutional signoff",
        ],
        "limit": "This is criterion/source tracing, not a new full independent code review or numeric common wave; newly found downstream counterexamples must update the packet.",
    },
    "owner_ready_packets": [
        f"{R2}core-ir-facade-owner-packet.json@{SNAPSHOT}",
        f"{R2}ir-semantic-owner-decision.json@{SNAPSHOT}",
        f"{E}doe-block-replay-20261006/D-consumer-packet.md@{component['doe']['published_receipt_head']}",
        f"{E}frc-source-measurement-r2/README.md@{new_receipts['FRC'][1]}",
    ],
    "local_G_recipe_ref": "current-local-G-recipes.json",
    "historical_local_G_recipe_ref": f"{CONT}closure-frozen/local-G-closeout-recipes.json@{SNAPSHOT}",
    "local_G_rule": "Full production law/history stays localread-only. Current explicit wrapper bindsf445 source/nativeAPI/controlIDs and preserves old58 recipes separately; finalsource rebind is required after pending B197/dependency fixes. Generic BKT native bridge is positive and not a missing production dataset.",
    "global_remaining_checks": [
        "Rootsourcefreeze after welfare law/support classfix+independentreview,1e942 strict reader receiptappendmerge/dependency checks, and facade review; BKT0983/FRC8486 reviews trackedGO",
        "One common numerical/gate wave on frozen assembled source",
        "Architecture/import facade/contract inventory on exact denominator; old reds need P41 fullbasecommandinputs replay",
        "Repeat earlier fail-fast UNRUN workspace/CI-parity/Atlas umbrella stages after actual prerequisite repair",
        "A/G generator owners confidence OpenAPI/FeedbackSolveResult schema manifest/trust-posture packets",
        "Individual accountable owner acceptance of32historical partial proposals plus newLA052 and B166/B169/B170 native proposals",
    ],
    "cleanup": {
        "policy": "No checkout/environment/production data deleted. No native Trash established in cloud; exact repeatable receipts directory is a later cleanup candidate only after root copied tracked deciding packet and no active users."
    },
    "P37_basis": prior["predicate_basis"],
    "P41_basis": "Results navigation is source-reported compact baseline only; preserved historical frozen wave1123PASS2FAIL belongs to58e, notf445. New component oracles/removals are bound to their exact leaf cuts. BKT9c priorGO superseded by concrete counterexamples, then5ad/0983 corrective source independentlyGO; generic A ownership alone does not establish causal attribution of old FRC red. B197 extra source defect is explicitly recorded, not hidden by held.",
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
    "22bundles /54findings /55links. Historical ledger remains49partial /4held /1closed.32partial bounded proposals need individual owner acceptance;17historical partial active residuals are separately preserved. B198 closed regression retained; B194/B197/B201/B202 held.",
    "",
    "MCd69/CAL45b/DOEf07/DDM4c5/PCLffd/FRC8486/BKT0983 are source-present inf445 with tracked independent boundedGO reviews. G accepts code separately. No common numeric wave has run onf445. B197 strict readerrepair1e942 is available/reportedindependentlyGO but not yet merged at this snapshot. Welfare empirical->Normal/hidden failedmass classfix is activeBKT work. BKT9cHOLD remains historical; corrective0983 is GO.",
    "",
    "LA052 now has a real configured graph→runner→Advanced→CAS→freshreader witness; its generic original criterion needs no production corpus. Its new finding proposal is not automatically accepted. LA053 requires a joint API compatibility window and caller inventory. D owns actual default Search; A owns default FRC trusted verifier/status/fresh HTTP surface; Core/IR/Foundry own cross-root facade/contract admission.",
    "",
    "The remaining free source work is explicit in remaining_source_blocks; external inputs and the next verifiable result are per finding in all-54-update.json. Additional confirmed B197 reader codefix is recorded separately from source/noise authority. This source/criterion trace is not a substitute for final numeric/architecture/consumer reviews.",
    "",
    "B172/B173 need trust purpose/profile/equivalence inputs; B190 real response/Jacobian; B193 evaluator/law/functional/stopping assumptions; B200 information-unit relationships; B197 actual source fit and named legacy enforcement seam; DDM actual feed/freshness/R2 institutional input. Human-appointed IR semantic authority must ratify four finite decisions before E implements distinctv2; team-polisyos library owner is not semantic appointment.",
    "",
    "Run `python3 validate.py --repo /workspace/e02-E-continuation-20261006 --negative` from this directory. It verifies exact tracked Git input blobs and all54 ownership/status/denominators/component/root bindings; negatives mutate only in-memory packet copies. Numeric outputs remain referenced at their tracked exact authored/reviewed cuts.",
    "",
    "Production/history stays local read-only; G recipes require finalcandidate rebind. Nothing deleted; this external receipt directory is a later cleanup candidate only after root publication and no active users.",
    "",
]
(OUT / "summary.md").write_text("\n".join(summary))
print(
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
