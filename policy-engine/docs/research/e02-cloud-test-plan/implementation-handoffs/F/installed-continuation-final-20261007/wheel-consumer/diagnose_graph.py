import sys
sys.dont_write_bytecode=True
import pytest
from pathlib import Path
import json
c=json.loads(Path(sys.argv[1]).read_text());carrier=Path(c['scratch'])/'wheel-consumer'
assert Path.cwd()==carrier and sys.flags.isolated
raise SystemExit(pytest.main(['-q','-s','-o','addopts=','-p','no:cacheprovider','--import-mode=importlib',str(carrier/'tests/unit/scientist/methods/causal/test_graph_intake_current_content.py')+'::test_query_only_replay_recomputes_operational_cache']))
