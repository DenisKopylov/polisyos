# Exact public Q2 build-backend input carrier

This carrier contains exactly five locked universal wheels and five corresponding public PyPI release JSON records. It solves one demonstrated input-availability gap: C107's canonical official urllib fetch failed with proxy403 before backend provisioning. It does not fix a product defect or certify a backend, artifact, installed consumer, C104 psutil closure, whole I2/Q2 or E02.

The payload is the existing canonical CPython3.14/Hatchling1.27 closure: hatchling1.27.0, packaging25.0, pathspec0.12.1, pluggy1.6.0, trove-classifiers2026.9.21.13. Five wheel archives total208,224bytes; all ten original inputs total255,220bytes. The source-owned wheel lock/helper/profile remain the authority; no lock, version or dependency is changed. These exact public inputs are classA, not a copy of an installed environment or general dependency tree. All wheel bytes and upstream licenses/notices remain unchanged. Whole wheels preserve Hatchling/pluggy MIT, packaging Apache/BSD, pathspec MPL2 and trove-classifiers Apache2 license material. Required sources/notices are retained inside the complete unmodified wheel archives; retained Root provenance is cited by precise locator/hash, with no private RAW receipt copied.

Each payload is a single losslessly compressed `.whl.gz` or `.json.gz` regular file. No tar, filesystem tree, symlink, executable upload automation or `.github` workflow exists. `manifest.json` gives both compressed and exact original hashes/sizes, upstream public URLs and the complete ten-file denominator. The compression suffix permits ordinary explicitly enumerated Git add under repository ignore rules; never force-add an opaque archive or broad directory. This is a small justified source input, not a cleanup/reinstall request.

After ordinary author publication and exact source/tree readback, use the existing admitted Python and the decoder's explicit source arguments:

```text
<python> <published-carrier>/decode_backend_inputs.py
 --source-root <actual-checkout>
 --source-commit <actual-full-published-SHA>
 --source-tree <actual-full-published-tree>
 --destination <fresh-task-scratch-outside-checkout>/backend-quarantine
```

The decoder first binds its own/carrier/canonical helper/profile/lock bytes to the actual selected Git source, materializes exactly ten flat basenames with bounded gzip reads and hash/readback checks, then calls the EXISTING canonical `validate_quarantine`. It does not fetch, install, build, run pytest or import PolicyOS runtime. Do not treat transport checks as replacement wheel verification. A failed input leaves the exact partial scratch for diagnosis; no cleanup is performed. Run outputs and decoded files must stay outside every Hatch include root; this tracked source carrier may be in docs, but generated outputs must never be placed beside it.

Next use the existing Q2 `configure_build_env` with this exact admitted flat quarantine, not another fetch or an app-Hatchling import. Reuse existing appropriate environments; no Root reinstall or environment copy. uv0.9.21 is not pinned by canonical pyproject/Q2 profile: record actual supported command/profile identity without falsely relabelling it. Backend -> real source wheel/native sdist/rebuilt wheel -> actual installed28positive/M1/restored and original bounded companions remain UNRUN until executed on a frozen source/harness with actual process/readset evidence. No source-only32PASS substitutes for that chain.
