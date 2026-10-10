# Linux capacity refinement — 2026-10-10

Read-only measurement of the existing `e02-local` Colima worker before frozen-source transport. No VM, disk, container limit, environment, checkout, or mount was changed; no source was copied and no test ran.

Root later authorized the bounded data-disk increase; see [`capacity-growth-receipt-20261010.md`](capacity-growth-receipt-20261010.md). This file remains the pre-change baseline.

## Disk budget and safe grow path

The dedicated Colima profile is Colima 0.10.3 / Lima 2.2.1, Virtualization.framework (`vz`), aarch64, 2 CPUs, 3 GiB guest memory. The Lima instance is named `colima-e02-local`; its system disk is 20 GiB. Separately, the Colima `disk: 8` setting is the 8 GiB Docker data disk `colima-e02-local` (`raw`, ext4). It is backed by `.../_lima/_disks/colima-e02-local/datadisk` (8,589,934,592 logical bytes; about 4.5 GiB currently allocated on the host). Do not confuse it with the 20 GiB system disk.

The worker `/scratch` volume and Docker storage are on that 8 GiB data disk. Current guest view: 8,152,540 KiB total, 4,664,316 KiB used, 3,052,512 KiB free = 2.911102 GiB, 61% used. The current host data-volume check reports 20,214,052 KiB free = 19.2776 GiB. A source bare store plus one attached checkout (555,792,112 bytes each), Q2 output (~1.5 GiB), and known sdist/wheel outputs (121,945,591 bytes plus two 15,146,001-byte wheels) total about 2.677 GiB. That leaves only ~0.234 GiB against present guest free space. These are pre-freeze estimates, not a capacity receipt for the final source.

An increase from 8 to 12 GiB adds 4 GiB virtual capacity. At the measured host free space, the sparse backing can grow by up to 4 GiB and still leaves about 15.28 GiB host free before the workload writes. After the estimated 2.677 GiB workload, a 12 GiB data disk would leave roughly 4.234 GiB guest free, before any unestimated temp/cache growth. This is the sensible bounded target if root wants disk headroom before the heavy slot; it does not change the 20 GiB system disk.

The supported Colima route is to increase the profile's `disk` setting and let Colima apply it on startup (official [Colima FAQ](https://github.com/abiosoft/colima/blob/main/docs/FAQ.md#how-can-disk-size-be-increased)). Local `colima start --help` supports `--disk`; the existing profile config says that disk may be increased after creation. The generated Lima config also provisions `resize2fs` at startup. For this particular profile, the exact no-action-yet sequence is:

```sh
export COLIMA_HOME=/Users/deniskopylov/.colima-e02-local
export DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local

/opt/homebrew/bin/colima stop --profile e02-local
/opt/homebrew/bin/colima start --profile e02-local --edit --activate=false
# In the editor, change only `disk: 8` to `disk: 12`; preserve CPU=2,
# memory=3, arch=aarch64, runtime=docker, vmType=vz, autoActivate=false.
```

The check must follow startup before any source transfer: `colima status -p e02-local -j`, `limactl disk ls`, `lsblk -b -o NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS`, `sfdisk --dump /dev/vdb`, and `df -k /scratch /mnt/lima-colima-e02-local`. The current guest has `/dev/vdb` (8,589,934,592 bytes) and `/dev/vdb1` (8,587,837,440 bytes), ext4 label `lima-colima-e02-`, mounted as `/mnt/lima-colima-e02-local` and bind-backed Docker directories. `growpart` is installed. Its read-only `growpart --dry-run /dev/vdb 1` at the current 8 GiB size reports `NOCHANGE` (only 2,015 bytes available below the 2,048-byte fudge threshold). Therefore, do not assume Colima's configured `resize2fs` alone expands the current GPT partition. If the post-start checks show the disk grew but partition 1 did not, the available guest-side sequence for root to review is `sudo growpart /dev/vdb 1`, then `sudo resize2fs /dev/vdb1`, followed by `lsblk` and `df` verification. Reconfirm that `/dev/vdb1` is still the `lima-colima-e02-` data partition before applying those commands. No partition or filesystem command was run here. Avoid direct raw-file edits or unreviewed `limactl disk resize`; let the profile's supported Colima startup path handle the virtual disk first.

## Memory and host pressure snapshot

At the capture, the worker cgroup used 1,632,464,896 bytes (1.5204 GiB) of a 2,306,867,200-byte (2.1484 GiB) memory limit, leaving 643.160 MiB hard-limit headroom. `memory.events` high/max/OOM/OOM-kill counters were all zero. `memory.stat` showed 1,456,812,032 bytes file cache (1.3568 GiB), including 1,236,533,248 bytes inactive file (1.1516 GiB), 174,234,136 bytes reclaimable slab (166.163 MiB), 175,390,720 bytes kernel (167.266 MiB), and 425,984 bytes anon. PSI `avg10/avg60/avg300` was 0.00 for both `some` and `full`; guest `MemAvailable` was 2,578,456 KiB (2.459 GiB), with no swap. Docker's configured memory limit is 2,200 MiB; memory-swap is configured as 4,400 MiB, but the guest reports zero swap. No limit increase is justified by this idle/readiness snapshot; recheck under the actual heavy slot rather than infer peak demand.

Host snapshot: 16 GiB RAM, 8 CPUs, page size 16 KiB; `vm_stat` reported 78,243 free pages (1.1939 GiB), 214,135 inactive pages, 194,882 wired pages, and 305,809 compressor-occupied pages. `uptime` at capture reported load averages 2.22 / 2.56 / 2.51 and 8 days 3:46 uptime. These are point-in-time host counters, not a guarantee of future headroom.

## Receipt

Full stdout, stderr, and exit status for each bounded read-only check are in [`raw/capacity-refinement-20261010/`](raw/capacity-refinement-20261010/). `SHA256SUMS` covers those captures; its SHA-256 is `db3c84a011b680f48a0f6b7541b40f0986878c760d39e4250f4435375503e042`. The source and test status remains as in [`final-wave-readiness.md`](final-wave-readiness.md): freeze identity and root's heavy-slot release are still prerequisites.
