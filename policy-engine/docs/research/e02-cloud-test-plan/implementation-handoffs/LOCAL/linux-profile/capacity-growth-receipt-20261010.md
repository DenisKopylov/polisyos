# Dedicated Linux worker data-disk growth — 2026-10-10

Root-authorized, bounded provisioning change to the existing isolated `e02-local` Colima profile. No second VM, source checkout/copy, production mount, cleanup, memory-limit adjustment, or test run. The current worker is healthy and ready for the later frozen-source transfer.

## Pre-change gate and command

Before stopping the profile, the dedicated Docker context showed exactly one running container: the existing `e02-local-worker-provision` (`88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`). The four Prometheus containers were only Exited/Created; they were left untouched. The worker had restart policy `no`, so it was explicitly restarted after VM startup. It used only the existing named volumes for uv Pythons, `/scratch`, and uv cache.

The Colima profile had `disk: 8`; `colima status` reported 8 GiB and `limactl disk ls` identified the same 8 GiB `colima-e02-local` raw data disk. Its separate system disk remained 20 GiB. The dedicated profile config before the operation is preserved as `raw/capacity-growth-20261010/colima.yaml.before`, SHA-256 `48e3c0f0c575fb295e144b42375ceb22beee71c2436b31a33f7a5c8514abb4b7`.

The local CLI exposes `--disk` as the container-data disk size. With `COLIMA_HOME` and `DOCKER_CONFIG` scoped to this profile, `colima stop --profile e02-local` succeeded, then this supported command completed with exit 0:

```sh
COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
/opt/homebrew/bin/colima start --profile e02-local --disk 12 --activate=false
```

Colima logged `resizing disk to 12GiB`, reused the existing VZ instance, and reached `READY`. One nonfatal port-53 forwarding warning said `address already in use`; the startup completed, Docker was reachable on the explicit `colima-e02-local` context, and no context activation was requested. The dedicated `DOCKER_CONFIG` still reports its own current context as `default`; no host-default Docker configuration was targeted.

The saved profile now reports disk 12 GiB, CPU 2, memory 3 GiB, aarch64, Docker, VZ, virtiofs, and `autoActivate: false`. The only config diff is `disk: 8` → `disk: 12` and empty hostname → the profile-derived `colima-e02-local` hostname. The before and after config files are both retained in the raw receipt; after SHA-256 is `c08f5009de157d2011e96485f6609ea8c03a8ef77e84448399ad0bc77ce34a96`.

## Guest and worker verification

After startup, both `colima status` and `limactl disk ls` report 12 GiB. Guest `/dev/vdb` is 12,884,901,888 bytes and `/dev/vdb1` is 12,883,836,416 bytes. Its GPT disk label ID stayed `C79FAB5F-72CE-49F7-8873-0C409EBD9B47`; the partition UUID stayed `398750A2-D4C7-4EAF-B7A7-A66DE81E8243`; ext4 filesystem label `lima-colima-e02-` and UUID `e490c417-d79a-40d4-a5a9-4746bd52f572` stayed the same. The filesystem expanded to 12,277,956 KiB, with 7,010,204 KiB free (6.685 GiB, 40% used). `growpart --dry-run /dev/vdb 1` reports `NOCHANGE: partition 1 is size 25163743. it cannot be grown`, confirming the partition now fills the disk; the earlier conditional manual `growpart`/`resize2fs` sequence was not needed or run.

The same worker container ID, image digest, and three named-volume mounts are present and it is `Up`. No source or production directory is mounted. Its memory limit remains 2,306,867,200 bytes (2,200 MiB); cgroup current was 5,582,848 bytes after startup, with all memory event counters zero and PSI averages zero. No memory limit was changed.

The existing environments remain at uv 0.9.21, root Python 3.14.0 and DoWhy Python 3.12.12. `uv pip check` passed again: 161 root distributions and 52 DoWhy distributions. These are package consistency checks only; no tests or worker runs were started. The pre/post outputs confirm the source remains unmounted and the existing other containers remain Exited/Created.

## Receipt files

All command stdout, stderr, and exit statuses, plus the pre-change config and before/after config hashes, are under [`raw/capacity-growth-20261010/`](raw/capacity-growth-20261010/). `SHA256SUMS` covers all 140 raw receipt files and verifies cleanly with `shasum -a 256 -c SHA256SUMS`; the manifest SHA-256 is `d7ec1f6529f2e5e5f66d7cc596cd9dd9e8abb7236ec4c877eb4b1b6b01e87675`.
