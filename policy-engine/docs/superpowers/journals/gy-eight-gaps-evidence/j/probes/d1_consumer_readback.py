"""Record exact D1 native identities and a whole-source freeze without runtime imports."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path.cwd()
TEST = 'tests/repo_quality/tools/test_gy_d1_catalog_wiring.py'
BASE = ROOT / '_build/gy-gaps/j/companions/d1-current-consumer-before.json'
RECEIPT = ROOT / '_build/gy-gaps/j/companions/d1-current-consumer.json'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())

def capture():
    git = {p for p in subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard','--','src','tools','tests'],text=True).split('\0') if p.endswith('.py') and Path(p).is_file()}
    rg = {p for p in subprocess.check_output(['rg','--files','--hidden','src','tools','tests'],text=True).splitlines() if p.endswith('.py')}
    assert git == rg, {'git_only': sorted(git-rg), 'rg_only':sorted(rg-git)}
    values = {p:sha(Path(p).read_bytes()) for p in sorted(git)}
    text = Path(TEST).read_text()
    defs = [n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')]
    regex = re.findall(r'^def (test_[A-Za-z0-9_]+)\(',text,re.M)
    assert sorted(n.name for n in defs) == sorted(regex)
    assert not any(n.decorator_list for n in defs), 'parameter expansion must be independently derived'
    return {'source_hashes':values,'expected':sorted(TEST+'::'+n.name for n in defs), 'source_count_git':len(git),'source_count_rg':len(rg),'source_path_hash':digest(sorted(git)), 'source_content_hash':digest(values)}

def main():
    current = capture()
    if sys.argv[1] == 'before':
        assert not BASE.exists()
        BASE.write_text(json.dumps(current))
        print(json.dumps({k:v for k,v in current.items() if k!='source_hashes'},indent=2))
        return 0
    prior = json.loads(BASE.read_bytes())
    receipt_raw = RECEIPT.read_bytes()
    receipt = json.loads(receipt_raw)
    expected_command = ['.venv/bin/python','-m','pytest','-q','-s','-rA','--show-capture=no','--tb=short',TEST]
    assert receipt['command']==expected_command
    changed = [{'path':p,'before':prior['source_hashes'][p] if p in prior['source_hashes'] else '<absent>', 'after':current['source_hashes'][p] if p in current['source_hashes'] else '<absent>'} for p in sorted(prior['source_hashes'].keys() | current['source_hashes'].keys()) if prior['source_hashes'].get(p)!=current['source_hashes'].get(p)]
    summaries = re.findall(r'^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) ('+re.escape(TEST)+r'::\S+)',receipt['stdout'],re.M)
    identities = [identity for _,identity in summaries]
    assert len(identities)==len(set(identities))
    result = {'receipt':str(RECEIPT.relative_to(ROOT))+'@sha256:'+sha(receipt_raw), 'command_returncode':receipt['returncode'], 'timed_out':receipt['timed_out'], 'expected_complete_ast_and_regex_identities':current['expected'], 'actual_complete_rA_states':dict((i,s) for s,i in summaries), 'identity_delta':{'missing':sorted(set(current['expected'])-set(identities)), 'extra':sorted(set(identities)-set(current['expected']))}, 'source_denominator':{'scope':'complete Git-visible src/tools/tests .py; exact Git/ripgrep sets agree','before':prior['source_count_git'],'after_git':current['source_count_git'],'after_rg':current['source_count_rg']}, 'source_path_hash_before':prior['source_path_hash'],'source_path_hash_after':current['source_path_hash'],'source_content_hash_before':prior['source_content_hash'],'source_content_hash_after':current['source_content_hash'],'complete_source_delta':changed, 'source_frozen':not changed, 'runtime_scope':'actual isolated fixture Fabric/N9 constructor and persistence consumer checks; no J production population claim'}
    print(json.dumps(result,indent=2))
    assert prior['expected']==current['expected'] and not changed
    assert not result['identity_delta']['missing'] and not result['identity_delta']['extra']
    assert receipt['returncode']==0 and not receipt['timed_out'] and all(s=='PASSED' for s,_ in summaries)
    BASE.unlink()
    return 0

if __name__=='__main__': raise SystemExit(main())
