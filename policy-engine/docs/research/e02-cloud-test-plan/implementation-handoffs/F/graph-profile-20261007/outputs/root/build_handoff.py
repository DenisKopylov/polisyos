from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
E02 = Path('policy-engine/docs/research/e02-cloud-test-plan')
OUT = E02 / 'implementation-handoffs/F/graph-profile-20261007.json'
PACK = E02 / 'implementation-handoffs/F/graph-profile-20261007'
SCRATCH = Path('/tmp/e02-F-graph-profile-20261007')
SOURCE = '4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
TREE = '551d4e760dc1168f6ad8182c9b176f00e94a2281'
BASE = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
G = '6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79'
affected = ['B204', 'B212', 'B213', 'B214', 'B218', 'LA-037']
manifest_path = ROOT / PACK / 'artifact-transports.json'
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)

def evidence(rel):
    path = SCRATCH / rel
    matches = [r for r in manifest['files'] if r['original_path'] == str(path)]
    assert len(matches) == 1, rel
    r = matches[0]
    return {k: r[k] for k in ['path', 'encoding', 'stored_bytes', 'stored_sha256', 'decoded_bytes', 'decoded_sha256']}

ledger = ROOT / E02 / 'implementation-handoffs/F/continuation-transfer-20261007'
cards = {fid: json.loads((ledger / 'per-ID' / (fid + '.json')).read_text())['original_card_refs'] for fid in affected}
footprint = json.loads((SCRATCH / 'root/source-footprint.json').read_text())
checks = json.loads((SCRATCH / 'root/final-wave/checks.json').read_text())
handoff = {
    'schema': 'e02.F.property_slice_handoff.v1', 'unit': 'F',
    'role': 'One canonical graph-profile repair after25c, narrow B204/backend/LA-037 companions and B218 supersession; source-ready F recommendation only',
    'canonical_writer': {'graph_mechanism': 'F root', 'B204_checker': 'F cau', 'LA-037_docs': 'F foundry', 'ledger': 'F root'},
    'branch': 'codex/e02-F-closeout-20261006', 'PR': 'https://github.com/DenisKopylov/polisyos/pull/65',
    'slice_base': {'sha': BASE, 'tree': 'ed4a4fd6864e8b60cb45124fb8e6fa9b7c503b66'},
    'candidate': {'sha': SOURCE, 'tree': TREE, 'parents': subprocess.check_output(['git', 'show', '-s', '--format=%P', SOURCE], cwd=ROOT, text=True).strip().split(), 'fetchable': True},
    'implementation_commits': [
        {'sha': '36b18cc142aff77a5825126b4f07bafec09a5180', 'tree': '28a104214fe96f1ccf572aeb64a7866c41776344', 'role': 'canonical reconciliation profile guard and real consumer tests'},
        {'sha': 'e1c4bb28c9d5ff936ae1c047619c56cf12ba5347', 'tree': '7ae6991cb8424e93b22dee4234914a6c99c88141', 'role': 'honest two-preperiod benchmark checker'},
        {'sha': '6beacc8b42dacabff214901919203323f07d1fef', 'tree': '64dc785b6bf29659e94acdd7cf3100c02179e2c0', 'role': 'IR direct facade/same-object alias lifecycle docs'},
    ],
    'history': {'append_only': True, 'reset_rebase_force_main_integration_write': False, 'previous_measured_source': {'sha': '519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82', 'tree': '750d28da94f372848fe6b2db5f88db95b94cb57d', 'role': 'Recovered historical actual91wheel/91sdist source, not new whole-head proof'}},
    'G_dependency': {'sha': G, 'tree': 'f79fc5304324b92aeed741d7abdd6fc6f54a130a', 'read_only_ref': 'origin/codex/e02-integration', 'newer_than_previous_83e': '106 documentation/review/prompt paths, zero product paths', 'decision': 'integration/reviews/2026-10-07-F35-decision/README.md', 'bounded_original_recommendations_supported': 33, 'new_F_runtime_source_accepted': 0, 'formal_findings_closed': 0, 'prior_Lex_accepted_source_preserved': '00a6eda114b903bc5abe86902cd8372426f739a1'},
    'original_criterion_bindings': cards, 'affected_IDs': affected, 'unchanged_ID_count': 29,
    'full_source_footprint': footprint, 'complete_diff': evidence('root/combined-implementation.full.patch'),
    'property': {
        'invariant': 'Only declared static DAG/ADMG may enter canonical reconciliation, before confidence filtering, endpoint rewrites or persistence. Other semantic graph families refuse rather than acquire DAG/ADMG identity.',
        'chain': 'schema-valid scored build_mgraph → actual MethodRegistry/run_job → ReconcileCausalGraphNode → no reconciled publication; original MGraph CAS → distinct-process extractor. Same-form ADMG → registered job/Node → CAS → distinct-process fresh reader.',
        'surfaces': ['direct Node intake', 'supplied method-result intake', 'selected current-CAS/cache intake', 'fragment composition defensive admission'],
        'oracle': 'Actual extract_mgraph_metadata plus declared graph-type identity and complete relation/metadata readback; known reverse normalization; lag/unresolved refusal. This synthetic DATA confidence0.9 only passes cutoff, not empirical confidence or authority.',
        'negative': 'Keep enum, strings, diagnostic messages, endpoints, status and module bytes; disable only runtime semantic-family predicate. Real MGraph producer/direct and supplied/cache negatives fail; ordinary ADMG/DAG/reverse positives remain green.',
        'class_P40': 'Widened endpoint/static-profile class to semantic graph family at its canonical reconciliation owner; no metadata-name allowlist and no per-caller graph-type patch.',
        'scope_limit': 'Reconciliation/Node/defensive Compose boundary only. Shared ADMG inference helper, all other identification consumers, PAG/CPDAG/MGraph support and temporal identification are not newly claimed. Ordinary FragmentCompositionData already refuses unsupported families; unsafe model_copy test is defensive, not a newly discovered normal constructor escape.',
        'no_new_finding_ID': True,
    },
    'independent_reviews': [
        {'role': 'full10-path immutable source and specification review, independent of writers', 'outcome': 'GO', 'output': evidence('api-review/combined4ee/review.json')},
        {'role': 'graph source, scored native discriminator and different-PID reader', 'outcome': 'GO', 'output': evidence('graph-review-prep/independent-review.json')},
        {'role': 'original35/36 criterion custody and independent scoped source review', 'outcome': 'GO', 'output': evidence('economics-review/review.json')},
        {'role': 'new exact-source wheel archive/site/source and complete installed packet independent audit', 'outcome': 'GO', 'output': evidence('api-review/installed4ee/review.json')},
    ],
    'checks': [
        {'name': 'affected graph defining/consumer wave', 'check': 'PASS', 'passed': 62, 'failures': 0, 'errors': 0, 'skipped': 0, 'output': evidence('root/final-wave/graph-consumers.junit.xml')},
        {'name': 'natural-experiment smoke, full affected3-case denominator', 'check': 'PASS', 'passed': 3, 'failures': 0, 'errors': 0, 'skipped': 0, 'output': evidence('root/final-wave/natural-experiments.json'), 'execution': evidence('root/final-wave/natural-experiments.execution.json')},
        {'name': 'actual configured Python3.12/DoWhy0.14 changed-body selected backend tests', 'check': 'PASS', 'passed': 3, 'failures': 0, 'errors': 0, 'skipped': 0, 'output': evidence('worker/focused-real-worker-review.json'), 'qualifier': 'Point-only case executes a genuine estimator, then deliberately removes interval/SE accessor responses in the test child; controlled real-backend post-fit negative, not a naturally point-only backend positive. Parent3.14/fresh reader non-gating without admitted identification basis.'},
        {'name': 'independent untouched graph controls', 'check': 'PASS', 'passed': 7, 'output': evidence('api-review/combined4ee/graph-untouched.xml')},
        {'name': 'independent semantic-family property removal', 'check': 'FAIL', 'expected_control_failure': True, 'behavioral_failures': 2, 'positive_controls_passed': 5, 'output': evidence('api-review/combined4ee/graph-removed.xml')},
        {'name': 'new exact4ee source wheel affected consumers', 'check': 'PASS', 'passed': 16, 'failures': 0, 'errors': 0, 'skipped': 0, 'warning_count': 1, 'warning_kind': 'unchanged unit-mark instrumentation', 'output': evidence('foundry/installed-4ee/native-junit.xml'), 'fresh_reader': evidence('foundry/installed-4ee/fresh-admg-corrected.stdout.txt'), 'archive_sha256': '1c912ce057fcdd3f91201979025867f9df1f2dc9041020877e2476cd7d396159', 'archive_bytes': 15147133, 'byte_origin_denominator': '3464 package files =3453 tracked source +11 Hatch resources;3147 Python; parent970/reader83 exact origins'},
        {'name': 'new installed semantic-family property removal', 'check': 'FAIL', 'expected_control_failure': True, 'behavioral_failures': 1, 'output': evidence('foundry/installed-4ee/removal-junit.xml')},
        {'name': 'independent B204 four-means oracle and10 retained-report falsifiers', 'check': 'PASS', 'actual_ATT': 1.997217038863679, 'oracle_ATT': 1.9972170388636759, 'tamper_controls_refused': 10, 'output': evidence('api-review/combined4ee/b204.stdout.json')},
        {'name': 'new rebuilt-sdist affected consumers', 'check': 'UNRUN', 'reason': 'No new rebuilt-sdist wave commissioned; historical519 qualification stays source-bound. New wheel does not prove new sdist.'},
        {'name': 'in-process Python3.14 DoWhy/EconML optional profiles', 'check': 'UNRUN', 'reason': 'Application markers exclude these backends; actual selected3.12 worker is separate.'},
    ],
    'exact_root_commands': checks,
    'baseline_and_harness_outcomes': {'real_pre_guard_MGraph_negative': {'check': 'FAIL', 'role': 'Actual property regression witness on unchanged25c runtime', 'stdout': evidence('root/baseline-mgraph.stdout')}, 'development_ordinary_compose_DTO_constructor': '3 development harness FAIL before corrected explicit unsafe-copy setup; original DTO already rejects unsupported family', 'worker_first_launch': 'ERROR before0tests because /usr/bin/time absent; corrected os.wait4 harness, no backend substitution', 'installed_first_collection': 'ERROR: overbroad dependency pth origin exclusion; exact read-only dependency exception fixed, Polisyos own-origin guard preserved', 'installed_first_child': 'ERROR StopIteration in evidence harness; original and corrected complete outputs retained', 'no_harness_error_relabelled_product_failure': True},
    'companions': {'B204': 'Only benchmark checker changes: two preperiods require not_testable/insufficient_pre_periods, passedFalse, statistic/pNone, identification_authorityFalse; ATT2DGP/time_treatment2/seed11 unchanged. No estimator/diagnostic admission weakening.', 'B212_B213': 'Focused exact-source changed test body3PASS on genuine configured3.12/DoWhy0.14 worker; old implementation receipts remain at their original sources.', 'B218': 'Explicit append supersession: historical limited→bounded original lag/export/static-refusal closed recommendation. Full protected temporal readiness stays separate limited/UNRUN; serialization is not identification.', 'LA037': 'Three docs align IR canonical owner, direct Foundry facade, same-object compatibility alias and finite lifecycle; both paths retained, no runtime/layout/API change.'},
    'published_companion_receipts': [
        {'branch': 'codex/e02-F-cau-20261006', 'git_ref': 'a7204961ac1028965c58224fe40e6bb3a397d8a8', 'tree': '936d0e79ae4fea92dfb082a98296037bdc965452', 'path': str(E02 / 'implementation-handoffs/F/did-clean-rollout-companion-20261007.json'), 'role': 'Separate implementatione1/handoff; exactGitREST upload after ordinarypush500, forcefalse/refreadback verified'},
        {'branch': 'codex/e02-F-fry-20261006', 'git_ref': 'b634d8a17ed43cad6f7e1558a9c927feb3d2e8ba', 'tree': 'c04125bf993487876f64a7b1abb176a3acbd07e4', 'path': str(E02 / 'implementation-handoffs/F/layout-compatibility-docs-20261007.json'), 'role': 'Separate source6be/docs identity/MkDocs native6PASS receipt, ordinary remote readback'},
        {'branch': 'codex/e02-F-fry-20261006', 'git_ref': 'defa506dfbe226fbbdbdf7722ae84c03828e181b', 'tree': '5e6aa2bd1fa5a47eef1fd76198a2fde916346325', 'path': str(E02 / 'implementation-handoffs/F/installed-graph-profile-20261007.json'), 'bytes': 33160, 'sha256': 'c9c1b717ac2b2fa60b2fad8508abbc1276d32ab963a067727b1ae6a7d5160f68', 'role': 'External exact4ee installed qualification,89 newreceipt paths/zero runtime delta; final defa forward-adds mandatory ignored trace plus complete Git transport audit, ordinary remote readback'},
    ],
    'source_carry': {'rule': 'Unchanged input/blob/origin-qualified old evidence only. None of historical numerical160-DGP/4000RDD/91wheel/91sdist results reassigned to new whole-head candidate.', 'catalog': '11 packaged resource/build contracts unchanged, exact byte/origin rows guarded in new wheel; no full old catalog wave repeated', 'worker': 'Seven implementation/profile/lock blobs unchanged; newbody selected tests actually rerun3PASS', 'unaffected_finding_rows': '29 per-ID bytes retained; six appended focused evidence only; original35/36 bindings unchanged'},
    'quality': {'historical_source519_scanner': 'ERROR/incomplete, two returncode-9 attempts, complete configured5957 denominator; no retry in narrow continuation', 'historical_Ruff': 'FAIL103 on exact maintained loader denominator', 'historical_public_surface': 'FAIL38', 'new_changed_graph_Ruff': 'PASS4files', 'new_changed_Python_format': 'PASS5files', 'new_benchmark_Ruff': 'FAIL2T201 full changed benchmark file; base also red is not P41 inherited proof', 'P41': 'not_established; no complete zero-overlap slice-base witness', 'new_full_scanner': 'UNRUN'},
    'owner_triggers': {'B214': {'outcome': 'limited', 'owners': ['A', 'C', 'F graph'], 'minimal_packet': 'Tracked family/identified-vs-conditional/partial output and authority-projection contract; query with distinct effects across admissible completions. No arbitrary DAG completion/new general ID engine.'}, 'B56': {'check': 'UNRUN', 'outcome': 'limited', 'owners': ['Runtime', 'Scientist', 'G local measurement'], 'minimal_packet': 'Canonical shared admission/cap and complete workload/input roster. Local active/wait/wall/RSS/all-fold/provenance/readback on exact candidate; serial folds retained, no second TMLE scheduler.'}},
    'acceptance': {'F_code_ready': True, 'F_technical_original_recommendations': {'closed': 33, 'limited': 2}, 'F_finding_recommendations': {'closed': 33, 'limited': 2}, 'finding_check_states': {'PASS': 34, 'UNRUN': 1}, 'G_new_source_acceptance': 'not_issued', 'G_formal_finding_closure': 'not_issued', 'no_main_publication': True},
    'evidence_transport': {'path': str(PACK / 'artifact-transports.json'), 'bytes': len(manifest_bytes), 'sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'files': manifest['file_count'], 'stored_bytes': manifest['stored_bytes'], 'decoded_bytes': manifest['decoded_bytes'], 'complete_outputs_retained': True},
    'cleanup': {'action': 'none', 'preserve': 'Git objects, source, docs, all deciding outputs/unique input artifacts and active environments', 'candidates_for_later_inactive_review_only': [str(SCRATCH / 'foundry/installed-4ee/uv-cache'), str(SCRATCH / 'foundry/installed-4ee/wheel-env')], 'no_native_Trash': True, 'permanent_delete_or_Trash_empty': False},
}
(ROOT / OUT).write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'receipt': str(OUT), 'bytes': (ROOT / OUT).stat().st_size, 'files': manifest['file_count']}))
