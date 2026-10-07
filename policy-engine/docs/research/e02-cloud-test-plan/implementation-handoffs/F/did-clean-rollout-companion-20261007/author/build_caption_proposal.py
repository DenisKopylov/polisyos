"""Build a read-only proposal for the ROOT-owned current captions."""

import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path('/workspace/e02-F-cau-20261006')
SCRATCH = Path('/tmp/e02-F-graph-profile-20261007/cau')
BASE = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
CANDIDATE = 'e1c4bb28c9d5ff936ae1c047619c56cf12ba5347'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def reference(sha, path, pointer=None):
    raw = git('show', sha + ':' + path)
    result = {
        'git_ref': sha, 'path': path, 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'git_blob': git('rev-parse', sha + ':' + path).decode().strip(),
    }
    if pointer is not None:
        result['json_pointer'] = pointer
    return result


def main():
    per_id = PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/per-ID/'
    old_scm = reference(
        'bf335dd687c313fda9001fa3bb1365df6bc5ae1f',
        PREFIX + 'implementation-handoffs/F/scm-source-bound-20261006.json', '/per_id/4',
    )
    historical072 = reference(
        '072d45a56d1119fe3e7665cec2cbbdca015d2934',
        PREFIX + 'implementation-handoffs/F/continuation-transfer-20261006/per-ID/B218.json',
    )
    current218 = reference(BASE, per_id + 'B218.json')
    current204 = reference(BASE, per_id + 'B204.json')
    text218 = (
        'B218: ранняя рекомендация limited в SCM receipt bf335dd#/per_id/4 и ROOT072 '
        'сохраняется как историческая. Для исходной нормы B218 она superseded текущей '
        'bounded рекомендацией F closed/check PASS: actual lag1/lag2/self-lag '
        'NetworkX/CAS round-trip и точный отказ static GCM/ADMG/intake без temporal '
        'conversion удовлетворяют исходному export/consumer-boundary критерию. '
        'Исходный текст и bytes unchanged. Full temporal protected-readiness route '
        'остаётся отдельным UNRUN/limited capability; serialization не identification. '
        'Это supersession исходной F-рекомендации, не formal closure или code acceptance G.'
    )
    text204 = (
        'B204 original estimator GO/PASS и bounded F closed сохраняются: zero-pre '
        'refusal, hand ATT3 и honest pretrend dispositions имеют прежние exact source '
        'bindings. В clean_rollout прежний checker на двух preperiods ошибочно требовал '
        'passed=True; actual base25c run FAIL при ATT1.997217 и корректном '
        'not_testable/insufficient_pre_periods. Companion e1c4 исправляет только checker, '
        'сохраняет DGP/time_treatment=2/seed11/ATT2 и требует passed=False, no statistic '
        'or p-value, identification_authority=False. До independent source review и '
        'ROOT affected benchmark replay новая companion readiness UNRUN, без объявления '
        'green. После actual replay ROOT добавляет отдельные exact source/check/output '
        'refs, сохраняя прежний FAIL и P41 not_established. Non-testability/nonrejection '
        'не устанавливают untreated real parallel trends.'
    )
    report = {
        'schema': 'e02.F.root_caption_proposal.v1',
        'role': 'read-only proposal; ROOT is sole ledger/caption writer',
        'base_sha': BASE,
        'base_tree': git('rev-parse', BASE + '^{tree}').decode().strip(),
        'candidate_sha': CANDIDATE,
        'candidate_tree': git('rev-parse', CANDIDATE + '^{tree}').decode().strip(),
        'source_delta': 'one clean_rollout checker, no estimator/diagnostic implementation changes',
        'B218': {
            'original_card': json.loads(git('show', BASE + ':' + per_id + 'B218.json'))['original_card_refs'],
            'historical_limited_refs': [old_scm, historical072],
            'current_bounded_closed_ref': current218,
            'exact_status_transition': {'historical_F_outcome': 'limited', 'current_F_outcome': 'closed', 'current_check': 'PASS', 'G_formal_acceptance': 'not_issued'},
            'proposed_text': text218,
            'separate_residual': 'full temporal protected-readiness UNRUN/limited; no general temporal identification claim',
        },
        'B204': {
            'current_original_criterion_ref': current204,
            'proposed_text': text204,
            'reviewed_affected_benchmark_command': [
                '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python',
                '-m', 'benchmarks.natural_experiments.policy_natural_experiments',
                '--mode', 'smoke', '--quiet', '--json', '<ROOT-unique-output-path>',
            ],
            'cwd': '/workspace/e02-F-closeout-20261006/policy-engine',
            'environment': {'PYTHONPATH': 'src:.', 'PYTHONDONTWRITEBYTECODE': '1'},
            'run_owner': 'ROOT after independent frozen-source review',
            'current_new_benchmark_readiness': 'UNRUN',
            'independent_four_means_att': 1.9972170388636759,
            'native_standard_did_att': 1.997217038863679,
            'base_red_stdout': str(SCRATCH / 'source-clean-rollout-red.stdout'),
            'base_red_stderr': str(SCRATCH / 'source-clean-rollout-red.stderr'),
            'base_red_execution': str(SCRATCH / 'source-clean-rollout-red.execution.json'),
        },
        'ROOT_only_dependent_surfaces': [
            PREFIX + 'closure-decisions/F.md',
            PREFIX + 'closure-decisions/method-decisions.md#f-m3',
            PREFIX + 'closure-decisions/method-decisions.md#f-m9',
            PREFIX + 'closure-decisions/runtime-profiles.md',
            PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/per-ID/B204.json',
            PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/per-ID/B218.json',
            PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/index.json',
            PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/full-audit.json',
            PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/REPORT.md',
            PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/G-source-integration-order.json',
        ],
        'caption_constraints': [
            'Keep all35/17/36 source-card bindings; B204/B218 do not introduce IDs or change current33closed/2limited count.',
            'Keep actual check, F recommendation, assembled consumer readiness, and formal G acceptance distinct.',
            'Do not overwrite original historical limited/FAIL outputs or retarget old scientific checks to e1c4.',
            'Do not describe the two-pre diagnostic as passed or causal identification.',
            'P41 inherited-red remains not_established; no complete denominator disjointness proof.',
        ],
    }
    path = SCRATCH / 'root-dependent-caption-proposal.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'path': str(path), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
