# Q2 owned bare-origin patch preparation

Prepared 2026-10-10 only; no source helper or worker file was changed.

The unapplied diff in raw/q2-owned-bare-origin.patch (SHA-256 a6423ad48b484bd99e096749815676d99804612feaac17fdc90f1e08992854be) targets only the frozen local helper raw/final-source-linux-wave.sh at SHA-256 cc17a395e38fee53d67fe3c4fb6c69ac56bcaed63c91abca705cd462cc589ffb. It replaces the Q2 worker heredoc's freeze-derived bare path with the attached checkout's origin, then requires that origin to equal the exact worker bare path in the append-only transport receipt (/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git). Before creating a run directory, it validates that store's root ownership/mode, bare configuration, requested branch/SHA/tree, retained 7574 shallow boundary, and absence of an external alternates file. The transport-size measurement then uses the verified origin. Thus an arbitrary /scratch/*.git, network origin, symlink, non-bare repo, or mismatched freeze fails closed.

The patch preserves the existing worker checkout, bare object store, volumes, Python environments, lock pins, and source inputs. It does not alter Q2 selection or invoke a wave. The frozen helper and its source-bound inputs remain untouched.

The hook is a separate native-capture prerequisite: only /scratch/e02-child-capture/7574c864a605c50efc033b966807790cbd8d1781/sitecustomize.py currently exists, with SHA-256 4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2. Q2's timeout driver captures its own process output and does not consume this hook. A later native lane for the 13e411 freeze needs a separately authorized absent-or-exact copy to its new freeze-scoped path.

Read-only git apply --check passed against the stated helper hash; git apply --numstat reports 15 insertions and one deletion. No worker probes, product tests, or builds were run for this preparation. Before applying, review the negative cases listed above; they must fail before any run directory or build is created.
