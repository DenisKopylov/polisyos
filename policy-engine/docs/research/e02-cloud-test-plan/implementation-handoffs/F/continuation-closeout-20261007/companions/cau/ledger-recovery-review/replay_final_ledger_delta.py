#!/usr/bin/env python3
"""Portable launcher for the immutable original35 review packet.

Supply the transferred reviewer input directory and reconstruct the authored
patch with git diff <target>^ <target> into a unique scratch file. This only
verifies immutable Git metadata; it executes no numerical or backend tests.
"""
import argparse
import importlib.util
import pathlib
import sys

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', required=True, type=pathlib.Path)
    p.add_argument('--authored-patch', required=True, type=pathlib.Path)
    p.add_argument('--repo', required=True)
    p.add_argument('--target', default='46cc03546f2572986962555ddf04d858163c1cf6')
    p.add_argument('--output', required=True)
    p.add_argument('--control')
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('reviewer_delta', a.input_dir/'validate_final_ledger_delta.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OLDER_VALIDATOR = a.input_dir/'validate_root_current35.py'
    module.EXPECTED = a.input_dir/'expected-original35-compact.json'
    module.PATCH = a.authored_patch
    sys.argv = [str(a.input_dir/'validate_final_ledger_delta.py'), '--repo', a.repo,
                '--target', a.target, '--output', a.output]
    if a.control:
        sys.argv += ['--control', a.control]
    return module.main()

if __name__ == '__main__':
    raise SystemExit(main())
