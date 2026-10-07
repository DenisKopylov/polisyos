import pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).parent
for name in ['audit.py','audit_companions.py','consolidate.py']:
 result=subprocess.run([sys.executable,str(ROOT/name)],check=False)
 if result.returncode:raise SystemExit(result.returncode)
