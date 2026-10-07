#!/usr/bin/env python3
"""Check the sole stale-caption repair, without repeating original35/material tests."""
import argparse
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
import time

BASE='46cc03546f2572986962555ddf04d858163c1cf6'
TARGET='cdf61b4500e355a27db14260e80ce673ddf8869e'
PATH='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-transfer-20261007/REPORT.md'
OLD='Final installed affected-wave output and complete dependency/source-order records are published separately and referenced in this index once available.'
NEW='Final source519 installed affected-wave output and complete dependency/source-order records are published at de197/c4 and bound by exact refs in this index.'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();start=time.monotonic()
    def git(*args):return subprocess.check_output(['git',*args],cwd=a.repo,stderr=subprocess.PIPE)
    before=git('show',BASE+':'+PATH);after=git('show',TARGET+':'+PATH);patch=git('diff','--no-ext-diff',BASE,TARGET)
    changed=git('diff','--name-only',BASE,TARGET).decode().splitlines()
    assert git('rev-parse',TARGET+'^').decode().strip()==BASE
    assert changed==[PATH]
    assert before.count(OLD.encode())==1 and OLD.encode() not in after
    assert before.replace(OLD.encode(),NEW.encode())==after
    assert NEW.encode() in after
    assert git('diff','--numstat',BASE,TARGET).decode().strip()=='1\t1\t'+PATH
    result={'schema':'F-final-ledger-caption-independent-addendum/v1','check':'PASS',
            'target':{'sha':TARGET,'tree':git('rev-parse',TARGET+'^{tree}').decode().strip()},
            'previous_complete_metadata_review':{'sha':BASE,'tree':git('rev-parse',BASE+'^{tree}').decode().strip(),'check':'PASS','negative_controls':'six actualFAIL/exit1; harnessPASS; remain bound to46cc, not relabeled as cdf executions'},
            'changed_paths':changed,'complete_diff':{'bytes':len(patch),'sha256':sha(patch),'reconstruction':['git','diff','--no-ext-diff',BASE,TARGET]},
            'report_before':{'git_ref':BASE,'path':PATH,'bytes':len(before),'sha256':sha(before)},
            'report_after':{'git_ref':TARGET,'path':PATH,'bytes':len(after),'sha256':sha(after)},
            'old_sentence':OLD,'new_sentence':NEW,
            'byte_identity_by_exact_one_path_diff':'All35perIDs/index/audit/10registry/source-order/3currentcaptions/scientific provider/test/schema/build bytes unchanged46cc; only one REPORT sentence changes. No repeat old1659/480 material or numerical suites.',
            'rationale':'Removes observed stale future wording after actualde197/c4 publication; source519 installed91/profile and separatewheel-child remain finite observed properties, original34PASS/33closed and G0 separate.',
            'environment':{'python':platform.python_version(),'executable':sys.executable,'purpose':'stdlib immutable Git doc delta only'},
            'replayer':{'path':__file__,'bytes':pathlib.Path(__file__).stat().st_size,'sha256':sha(pathlib.Path(__file__).read_bytes())},
            'elapsed_s':time.monotonic()-start}
    pathlib.Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
