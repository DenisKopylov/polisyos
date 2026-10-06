"""Reproduce the pinned read-only C/F closure/handoff census for B09."""
from collections import Counter, defaultdict
from pathlib import PurePosixPath
import hashlib
import re
import subprocess

PINNED_REFS = (('refs/heads/codex/e02-C-berl', '942206505d1681ea1d4d46e93e21d0c566450acb'), ('refs/heads/codex/e02-C-berl-20261006', '95ea3780f1101ba1ad1a3087923c65c8aac53b7d'), ('refs/heads/codex/e02-C-canon', 'b98bc432e3afc0f17d992fc034029b68b0952169'), ('refs/heads/codex/e02-C-canon-20261006', '9f84276408fc6b776e35050afece5c4e74ed413d'), ('refs/heads/codex/e02-C-catalog', 'dfaadaac01f21b7b3994109c3cc76d522a2a3cb3'), ('refs/heads/codex/e02-C-catalog-20261006', '8590de631f0e5c4e6af75357e8d404931786ad62'), ('refs/heads/codex/e02-C-client', '13a723d8b6cb203583f856d949717427db858e37'), ('refs/heads/codex/e02-C-client-20261006', '5f812a3487d8f1fe0779f67bfcf3f9b73babeaf1'), ('refs/heads/codex/e02-C-continuation-20261006', '68eed6d56f48e9a676edeb3251902300a64d5fad'), ('refs/heads/codex/e02-C-coordinator', 'c40d4acae1ce58b597267255026d9356565828fd'), ('refs/heads/codex/e02-C-dfi-emb', 'cd02697111861bbcbb8442287101decaaf3239fb'), ('refs/heads/codex/e02-C-dfi-emb-20261006', 'ab27db6d940c7a34ba2dd3837803f0b6ec4f464c'), ('refs/heads/codex/e02-C-federation', 'ca9caf3d3cc26a57fc3cf225e9b17db981afff3f'), ('refs/heads/codex/e02-C-federation-20261006', '26ba51d571a5ccb5da26502d4d097d801cdc5b04'), ('refs/heads/codex/e02-C-handoff', '172e791ca9335954907ebfd789e95715a55963c8'), ('refs/heads/codex/e02-C-hygiene', 'b56ec6b1f802ab10d2927492bbc082f90c390139'), ('refs/heads/codex/e02-C-hygiene-20261006', 'd2da9ce760aa696431d727d3c3b29d03542faa64'), ('refs/heads/codex/e02-C-ing-oracle-20261006', '78ee80bf1016c979f8ff5ac0a63c23ab43fdf5ab'), ('refs/heads/codex/e02-C-ing-support', 'a5bf3d536a9f1773b7110f64ac0d3b3f1230abdf'), ('refs/heads/codex/e02-C-migrations', '1164718054d3a409269a724c832706b524f78864'), ('refs/heads/codex/e02-C-migrations-20261006', '696c9d0fc1e9d758014225c91dee80a048adb28b'), ('refs/heads/codex/e02-C-obs-udf', '6e24cbaf5fb1d78830fd918ab17e6495095250ed'), ('refs/heads/codex/e02-C-obs-udf-20261006', '05dd5193116c1916733ae3e7a6240e86f16f1659'), ('refs/heads/codex/e02-C-plugin-discovery', 'e30956352cd73e11c1c453e95859589cdd2e86c6'), ('refs/heads/codex/e02-C-plugin-training', '5ee7dbc2d66fbb647ddc617fbfe19454737916b5'), ('refs/heads/codex/e02-C-plugins-20261006', '0ccdd226744a936d09cc85b5596783b0b037262d'), ('refs/heads/codex/e02-C-schema-20261006', 'cf751b1b4bec5f7ef97d965370e8562f3b4c5b49'), ('refs/heads/codex/e02-C-scholar', 'cafeeffa1577d45c02e1ff22f0db9f9f698f9046'), ('refs/heads/codex/e02-C-scholar-20261006', '9a9dc96307dcb8d1e912d56386eef6f5779f956d'), ('refs/heads/codex/e02-C-streaming', '1013ae0d2292f732a2f0518b25a5a682dc156e81'), ('refs/heads/codex/e02-C-ukraine-ops', '62a9140aaf28630d24688d5c850e752048dbbe9a'), ('refs/remotes/origin/codex/e02-C-berl', '942206505d1681ea1d4d46e93e21d0c566450acb'), ('refs/remotes/origin/codex/e02-C-canon', 'b98bc432e3afc0f17d992fc034029b68b0952169'), ('refs/remotes/origin/codex/e02-C-canon-20261006', '9f84276408fc6b776e35050afece5c4e74ed413d'), ('refs/remotes/origin/codex/e02-C-catalog', 'dfaadaac01f21b7b3994109c3cc76d522a2a3cb3'), ('refs/remotes/origin/codex/e02-C-client', '13a723d8b6cb203583f856d949717427db858e37'), ('refs/remotes/origin/codex/e02-C-client-20261006', '5f812a3487d8f1fe0779f67bfcf3f9b73babeaf1'), ('refs/remotes/origin/codex/e02-C-dfi-emb', 'cd02697111861bbcbb8442287101decaaf3239fb'), ('refs/remotes/origin/codex/e02-C-federation', 'ca9caf3d3cc26a57fc3cf225e9b17db981afff3f'), ('refs/remotes/origin/codex/e02-C-federation-20261006', '26ba51d571a5ccb5da26502d4d097d801cdc5b04'), ('refs/remotes/origin/codex/e02-C-handoff', '172e791ca9335954907ebfd789e95715a55963c8'), ('refs/remotes/origin/codex/e02-C-hygiene', 'b56ec6b1f802ab10d2927492bbc082f90c390139'), ('refs/remotes/origin/codex/e02-C-ing-support', 'a5bf3d536a9f1773b7110f64ac0d3b3f1230abdf'), ('refs/remotes/origin/codex/e02-C-migrations', '1164718054d3a409269a724c832706b524f78864'), ('refs/remotes/origin/codex/e02-C-obs-udf', '6e24cbaf5fb1d78830fd918ab17e6495095250ed'), ('refs/remotes/origin/codex/e02-C-plugin-discovery', 'e30956352cd73e11c1c453e95859589cdd2e86c6'), ('refs/remotes/origin/codex/e02-C-plugin-training', '5ee7dbc2d66fbb647ddc617fbfe19454737916b5'), ('refs/remotes/origin/codex/e02-C-scholar', 'cafeeffa1577d45c02e1ff22f0db9f9f698f9046'), ('refs/remotes/origin/codex/e02-C-streaming', '1013ae0d2292f732a2f0518b25a5a682dc156e81'), ('refs/remotes/origin/codex/e02-C-ukraine-ops', '62a9140aaf28630d24688d5c850e752048dbbe9a'), ('refs/remotes/origin/codex/e02-F-api-20261006', '449d32909928caf39382f4ff02ac74b0adf277eb'), ('refs/remotes/origin/codex/e02-F-cau', '08aaccebfce37aa652ff243fce8037ff48020807'), ('refs/remotes/origin/codex/e02-F-cau-20261006', '4c5a11ff8050c6108f6753177b96e6714cef401f'), ('refs/remotes/origin/codex/e02-F-causal-api', '0b6d872d8a681b1725abb5e2e3f57f9668e31c69'), ('refs/remotes/origin/codex/e02-F-causal-output', '9a952415bb988e6ff79983fa9ef782ac28f2e672'), ('refs/remotes/origin/codex/e02-F-closeout-20261006', '92148340601ac6ea69f0dbd4764aae7428ad83d7'), ('refs/remotes/origin/codex/e02-F-dowhy-20261006', 'c8c2319d6c48f23f90103322da8cd63bc959da6f'), ('refs/remotes/origin/codex/e02-F-economic-dtype', 'bfc5d0fb8195c2246db72dfb5d46e29a8eec9e42'), ('refs/remotes/origin/codex/e02-F-economics', 'e642bb9025a67739c201393acca5712603cb064d'), ('refs/remotes/origin/codex/e02-F-economics-20261006', 'fb51511fef60c5123875e99ab2f19a9a0bd5d16f'), ('refs/remotes/origin/codex/e02-F-fit-tmle', 'ef3f208db031671d9f0d5cefe1ffa68af0650f0a'), ('refs/remotes/origin/codex/e02-F-foundry', 'ea577ac3185829e066a39f51a8a2eae8f1bb5d43'), ('refs/remotes/origin/codex/e02-F-fry-20261006', 'f4fa51e6dd247cfd967450263579d67233a743d6'), ('refs/remotes/origin/codex/e02-F-graph-20261006', '2137961b0d3a2b39b85c5a57bf774777d2a4204e'), ('refs/remotes/origin/codex/e02-F-graph-intake-20261006', '2044260c39dc4988b37d5a1568b65a1cdb1e3d31'), ('refs/remotes/origin/codex/e02-F-graph-scm', '85c16de9f16a4e21c05c516271b6c81e08b7a39f'), ('refs/remotes/origin/codex/e02-F-handoff-index', 'f72e8fa6b7be831f8fda6f106c9d4f04572c4b69'), ('refs/remotes/origin/codex/e02-F-installed-worker-20261006', 'e9bd25f05f063dd823d27a44b3c1c740e940751c'), ('refs/remotes/origin/codex/e02-F-lex', '3fab28d98997527b2a26d46fe4e16220e42383b7'), ('refs/remotes/origin/codex/e02-F-lex-20261006', '77166daa0ff8b9659e3978447f9016c691694266'), ('refs/remotes/origin/codex/e02-F-rdd-20261006', '15a04c4400497374416e167a5f61ebc12f61b8e4'), ('refs/remotes/origin/codex/e02-F-tmle-20261006', 'f460bd81b8124be58f890f59a53e2aba9e7ceb76'), ('refs/remotes/origin/codex/e02-integration', '0346fc656a45ff2cd43d37126992d8ddbb739d10'))
# Explicit late 2026-10-06 ref refreshes observed after the initial census.
PINNED_REF_OVERRIDES = {
    "refs/heads/codex/e02-C-catalog-20261006": "42a8b499860acdb67b73ea9c5c7f53a874d71f08",
    "refs/heads/codex/e02-C-continuation-20261006": "9f35e19ff8f39895d66cbce78644470e52f8ec09",
    "refs/heads/codex/e02-C-hygiene-20261006": "5ad2dc84420ff61caf02929d196a55fe1ea972cf",
    "refs/heads/codex/e02-C-ing-oracle-20261006": "5231cf93a399fcc2944870c8a590b8770f3ba931",
    "refs/heads/codex/e02-C-migrations-20261006": "c62f5f27c5a165316a5428806993e3f524caae85",
    "refs/heads/codex/e02-C-schema-20261006": "8b92203b52d0363d912635b773e432e795d3512f",
    "refs/heads/codex/e02-C-scholar-20261006": "597811a78a430bc8fff9c24b002c8d3dad5059a0",
    "refs/remotes/origin/codex/e02-C-continuation-20261006": "9f35e19ff8f39895d66cbce78644470e52f8ec09",
    "refs/remotes/origin/codex/e02-F-closeout-20261006": "421f1dd977b237307394c68820caab4156716eb2",
    "refs/remotes/origin/codex/e02-F-graph-20261006": "bf335dd687c313fda9001fa3bb1365df6bc5ae1f",
    "refs/remotes/origin/codex/e02-F-installed-worker-20261006": "3dde887e22592cdd7c1fe8865707afdfd72dc6fb",
    "refs/remotes/origin/codex/e02-integration": "6f869f39d04deaff7eda9b9047848912605beca5"
}
PINNED_REFS = tuple(
    (ref, PINNED_REF_OVERRIDES.get(ref, commit))
    for ref, commit in PINNED_REFS
) + (("refs/remotes/origin/codex/e02-C-continuation-20261006",
      "9f35e19ff8f39895d66cbce78644470e52f8ec09"),
     ("refs/heads/codex/e02-integration",
      "6f869f39d04deaff7eda9b9047848912605beca5"),)

PREFIX = "policy-engine/docs/research/e02-cloud-test-plan/"
ROOTS = (
    "closure-decisions/",
    "implementation-handoffs/C/",
    "implementation-handoffs/F/",
    "execution-prompts/handoffs/",
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def tree_of(commit: str) -> str:
    return git("show", "-s", "--format=%T", commit).decode().strip()


PINNED_REF_MAP = dict(PINNED_REFS)
CURRENT_REF_MAP = {}
for line in git("for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines():
    ref, commit = line.split()
    is_local_or_remote = ref.startswith("refs/heads/") or ref.startswith("refs/remotes/")
    is_c_or_f_or_integration = "e02-C-" in ref or "e02-F-" in ref or ref.endswith("/codex/e02-integration")
    if is_local_or_remote and is_c_or_f_or_integration:
        CURRENT_REF_MAP[ref] = commit
if set(CURRENT_REF_MAP) != set(PINNED_REF_MAP):
    missing = sorted(set(CURRENT_REF_MAP) - set(PINNED_REF_MAP))
    stale = sorted(set(PINNED_REF_MAP) - set(CURRENT_REF_MAP))
    raise SystemExit(f"pinned ref name set is stale: unpinned={missing}; no-longer-present={stale}")
changed = sorted((ref, PINNED_REF_MAP[ref], commit)
                 for ref, commit in CURRENT_REF_MAP.items()
                 if PINNED_REF_MAP[ref] != commit)
if changed:
    raise SystemExit(f"pinned refs are stale; refresh explicitly: {changed}")

snapshots = defaultdict(list)
for ref, commit in PINNED_REFS:
    snapshots[tree_of(commit)].append((ref, commit))

path_blobs = {}
for tree in snapshots:
    for entry in git("ls-tree", "-r", "-z", tree).split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        path = raw_path.decode()
        relative = path[len(PREFIX):] if path.startswith(PREFIX) else ""
        if kind == "blob" and any(relative.startswith(root) for root in ROOTS):
            path_blobs[(tree, path)] = blob

entry_types = Counter()
root_entries = Counter()
for _, path in path_blobs:
    rel = path[len(PREFIX):]
    root = next(root for root in ROOTS if rel.startswith(root))
    ext = PurePosixPath(path).suffix.lower() or "[none]"
    entry_types[ext] += 1
    root_entries[root] += 1

manifest = hashlib.sha256()
for (tree, path), blob in sorted(path_blobs.items()):
    manifest.update((tree + "\0" + path + "\0" + blob + "\n").encode())

unique_path_blobs = sorted({(path, blob) for (_, path), blob in path_blobs.items()})
text_path_blobs = [
    (path, blob) for path, blob in unique_path_blobs
    if PurePosixPath(path).suffix.lower() != ".gz"
]
patterns = {
    "finding B09": re.compile(rb"\bB09\b"),
    "finding LA-046": re.compile(rb"LA-046"),
    "ObservationToWMRRule": re.compile(rb"ObservationToWMRRule"),
    "typedObservationToWMRRule": re.compile(rb"typedObservationToWMRRule"),
    "observation-to-WMR phrase": re.compile(rb"observation[- ]to[- ]WMR", re.I),
}
term_hits = defaultdict(list)
for path, blob in text_path_blobs:
    content = git("cat-file", "blob", blob)
    for label, pattern in patterns.items():
        if pattern.search(content):
            line_numbers = [i for i, line in enumerate(content.decode("utf-8", "ignore").splitlines(), 1)
                            if pattern.search(line.encode())]
            term_hits[label].append((path, line_numbers))

cf_roots = ("implementation-handoffs/C/", "implementation-handoffs/F/")
cf_handoff_blobs = [
    (path, blob) for path, blob in text_path_blobs
    if path.startswith(PREFIX + cf_roots[0]) or path.startswith(PREFIX + cf_roots[1])
]
cf_contract_patterns = {
    "WMR token": re.compile(rb"\bWMR\b", re.I),
    "canonical C observation projection type": re.compile(rb"CanonicalAcquisitionObservation|ActivatedAcquisitionObservationProjection"),
    "C activated semantic-epoch readback": re.compile(rb"read_activated_semantic_epoch_observations"),
    "C passport-derived observation class": re.compile(rb"observation_class|source_watermark|dataset_version"),
    "selected rows": re.compile(rb"selected[- ]rows?", re.I),
    "valid-time field": re.compile(rb"valid[-_ ]time", re.I),
    "source as-of role": re.compile(rb"source[- ]as[- ]of|source/as[- ]of", re.I),
    "observation profile/scope/unit mapping": re.compile(rb"observation.{0,40}(?:profile|denominator|unit|transform|slot)|(?:profile|denominator|unit|transform|slot).{0,40}observation", re.I),
}
cf_contract_hits = defaultdict(list)
for path, blob in cf_handoff_blobs:
    content = git("cat-file", "blob", blob)
    for label, pattern in cf_contract_patterns.items():
        if pattern.search(content):
            lines = [i for i, line in enumerate(content.decode("utf-8", "ignore").splitlines(), 1)
                     if pattern.search(line.encode())]
            cf_contract_hits[label].append((path, lines))

print(f"REFS={len(PINNED_REFS)} UNIQUE_TREE_SNAPSHOTS={len(snapshots)}")
print("PINNED_REFS:")
for ref, commit in PINNED_REFS:
    print(f"  {ref} {commit} tree={tree_of(commit)}")
print(f"TRACKED_PATH_TREE_ENTRIES={len(path_blobs)} DISTINCT_PATHS={len({p for _, p in path_blobs})} DISTINCT_BLOBS={len({b for b in path_blobs.values()})}")
print("PATH_ROOT_ENTRIES=" + ", ".join(f"{root}{root_entries[root]}" for root in ROOTS))
print("FILE_TYPE_DENOMINATOR=" + ", ".join(f"{ext}:{entry_types[ext]}" for ext in sorted(entry_types)))
print(f"PATH_TREE_BLOB_MANIFEST_SHA256={manifest.hexdigest()}")
print(f"TEXT_SCAN_SCOPE=distinct tracked path/blob entries excluding compressed .gz payloads ({len(text_path_blobs)} scanned; .gz remains in denominator/manifest)")
for label in patterns:
    hits = term_hits[label]
    cf = [(p, lines) for p, lines in hits if any(p.startswith(PREFIX + root) for root in cf_roots)]
    print(f"TEXT_SCAN {label!r}: distinct_path_blob_hits={len(hits)} C_or_F_handoff_hits={len(cf)}")
    for path, lines in hits:
        print(f"  {path}:{','.join(map(str, lines))}")
print(f"CF_HANDOFF_TEXT_DENOMINATOR={len(cf_handoff_blobs)} distinct path/blob entries")
for label in cf_contract_patterns:
    hits = cf_contract_hits[label]
    print(f"CF_HANDOFF_SCAN {label!r}: distinct_path_blob_hits={len(hits)}")
    for path, lines in hits:
        print(f"  {path}:{','.join(map(str, lines))}")
