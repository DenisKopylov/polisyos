from __future__ import annotations

import argparse
import hashlib
import importlib.abc
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


class MutationFinder(importlib.abc.MetaPathFinder):
    def __init__(self, name: str, path: Path):
        self.name, self.path = name, path

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.name:
            return importlib.util.spec_from_file_location(fullname, self.path)
        return None


class OriginPlugin:
    def __init__(self, args):
        self.args = args

    def pytest_collection_modifyitems(self, session, config, items):
        if self.args.census_script:
            for item in items:
                if hasattr(item.module, 'CENSUS_SCRIPT'):
                    item.module.CENSUS_SCRIPT = self.args.census_script

    def pytest_sessionfinish(self, session, exitstatus):
        origins = []
        bad = []
        for name,module in sorted(sys.modules.items()):
            if not (name == 'polisyos' or name.startswith('polisyos.') or name == 'tools' or name.startswith('tools.')):
                continue
            filename = getattr(module, '__file__', None)
            if not filename:
                continue
            path = Path(filename).resolve()
            entry = {'module':name,'origin':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            origins.append(entry)
            allowed = self.args.target.resolve() if self.args.target else self.args.installed_prefix.resolve()
            if not path.is_relative_to(allowed):
                if not self.args.mutant_path or path != self.args.mutant_path.resolve():
                    bad.append(entry)
        self.args.origins.parent.mkdir(parents=True,exist_ok=True)
        distributions = sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda d:d['name'].lower())
        receipt = {'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'sys_path':sys.path,'origins':origins,'foreign_origins':bad,'pytest_exitstatus':int(exitstatus),'installed_distributions':distributions}
        self.args.origins.write_text(json.dumps(receipt,indent=2)+'\n')
        if bad:
            print('FOREIGN TARGET ORIGIN: '+json.dumps(bad))
            session.exitstatus = 1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',type=Path)
    parser.add_argument('--expected-sha')
    parser.add_argument('--installed-prefix',type=Path)
    parser.add_argument('--origins',type=Path,required=True)
    parser.add_argument('--mutant-module')
    parser.add_argument('--mutant-path',type=Path)
    parser.add_argument('--census-script',type=Path)
    parser.add_argument('pytest_args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    sys.dont_write_bytecode=True
    if args.target:
        if args.expected_sha:
            actual=subprocess.run(['git','rev-parse','HEAD'],cwd=args.target,capture_output=True,text=True,check=True).stdout.strip()
            assert actual == args.expected_sha,(actual,args.expected_sha)
        product=args.target/'policy-engine'
        sys.path[:0]=[str(product/'src'),str(product)]
    if args.mutant_module:
        sys.meta_path.insert(0,MutationFinder(args.mutant_module,args.mutant_path))
    import pytest
    pytest_args=args.pytest_args
    if pytest_args and pytest_args[0]=='--':pytest_args=pytest_args[1:]
    return pytest.main(pytest_args,plugins=[OriginPlugin(args)])


if __name__=='__main__':
    raise SystemExit(main())
