# Proxmox plan for `tazlab`: reuse, don't wipe

Based on your Proxmox VE 9.2.18 datacenter view (`pve01` and `pve02`).

## Verdict: reuse it

Wiping would cost you weeks and gain nothing. What you've already built is exactly the foundation
an agent platform needs:

- a **2-node Proxmox cluster**, so the workload can be split across both Micros
- a working **K3s cluster** (`k3s-cp01` + `k3s-worker01`) with namespaces, RBAC, NetworkPolicies, and Traefik ingress
- **Wazuh** for security monitoring, which matters once agents read untrusted web content
- **pfSense** and VLAN test containers, for network segmentation later

You need cleanup, one urgent fix, more RAM, and better resilience. You don't need a rebuild.

## What I see, and what to do with each item

| ID | Name | Host | State | Decision |
|---|---|---|---|---|
| 101 | `k3s-cp01` (VM) | pve01 | running, **disk 89.1%** | **Fix now** (below). Move its disk to `nvme-lvm`, grow it, give it 4 vCPU / 8 GB. It becomes the **data** node (Postgres, Redis, console). |
| 102 | `k3s-worker01` (VM) | pve02 | running, disk 44.2% | **Grow**: 6-8 vCPU / 12-16 GB. pve02 has 12 threads and is only ~20% used on memory, so it becomes the **compute** node (agent workers, n8n, optional Ollama). |
| 106 | `wazuh-mgr01` (LXC) | pve01 | running, disk 60.8% | **Keep.** Enroll both K3s VMs as Wazuh agents, set index retention (30 days) so the disk doesn't fill, and forward alerts to `security-auditor` through n8n. |
| 100 | `jellyfin` (LXC) | pve01 | running, light | **Keep** (personal). If pve01 RAM gets tight, it's the first thing to move to pve02. |
| 105 | `pfsense-fw01` (VM) | pve02 | stopped | **Keep, optional.** Fine for an isolated lab VLAN. Don't route the cluster's internet through it while it runs on one of only two hosts: a pve02 reboot would cut every agent off. |
| 107 | `splunk01` (VM) | pve02 | stopped | **Your call.** It overlaps with Wazuh, and Splunk Enterprise needs a lot of RAM. Delete it to free space on pve02's `local-lvm` (46.8% used), unless you're studying for Splunk certs. |
| 103 / 104 | `vlan40-test01/02` (LXC) | both | stopped | **Delete** once you've confirmed they were only VLAN tests (`pct destroy 103`, `pct destroy 104`). |
| — | `nvme-lvm` | pve01 | **3.8% used** | Your fastest storage, sitting almost empty. Put cp01's disk here (so Postgres lives on NVMe). |

## Step 0: back up before touching anything

```bash
# On pve01 / pve02. "local" is a stopgap; a USB disk, NAS, or Proxmox Backup Server is better.
vzdump 101 106 --storage local --mode snapshot --compress zstd   # on pve01
vzdump 102 --storage local --mode snapshot --compress zstd       # on pve02
```

## Step 1 (urgent): free and grow `k3s-cp01`'s disk

At about 89% used, the node is already past the kubelet's default image garbage-collection threshold
(85%) and close to its disk-pressure eviction thresholds. Pods will start getting evicted, and image
pulls will fail.

Inside `k3s-cp01`, find the space and reclaim the easy wins:

```bash
df -h /
sudo du -xh / --max-depth=2 2>/dev/null | sort -h | tail -15
sudo k3s crictl rmi --prune            # unused container images
sudo journalctl --vacuum-size=200M     # old logs
```

On **pve01**, move the disk to NVMe and grow it. Both work while the VM is running:

```bash
qm config 101 | grep -E '^(scsi|virtio|sata)[0-9]'   # find the disk name, e.g. scsi0
qm disk move 101 scsi0 nvme-lvm --delete 1
qm disk resize 101 scsi0 +40G
```

Inside `k3s-cp01`, grow the filesystem. These are Ubuntu Server defaults with LVM; check `lsblk` first,
because yours may use `vda` instead of `sda`:

```bash
lsblk
sudo growpart /dev/sda 3
sudo pvresize /dev/sda3
sudo lvextend -r -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
df -h /
```

## Step 2: RAM, CPU, and node roles

Find out how much RAM each host has (`free -h` on pve01 and pve02). Most 8th-gen-and-newer OptiPlex
Micros have two SODIMM slots; check your model's maximum before buying.

| Host RAM | pve01 (6 threads) | pve02 (12 threads) |
|---|---|---|
| 16 GB each (tight) | cp01 6 GB · wazuh 6 GB · jellyfin 1 GB | worker01 10 GB · Ollama off |
| **32 GB each (recommended)** | cp01 8 GB · wazuh 8 GB · jellyfin 2 GB · ~10 GB spare | worker01 16 GB · ~12 GB spare |
| 64 GB on pve02 | same as above | worker01 24-32 GB · Ollama on |

Apply the sizes (each VM needs a reboot afterwards, so do one at a time):

```bash
qm set 101 --cores 4 --memory 8192     # pve01
qm set 102 --cores 8 --memory 16384    # pve02
```

Then tell Kubernetes which node does what. The manifests prefer these labels but still run without them:

```bash
kubectl label node k3s-cp01     homelab.tazlab/tier=data
kubectl label node k3s-worker01 homelab.tazlab/tier=compute
```

## Step 3: fix two-node quorum (important)

A 2-node Proxmox cluster loses quorum when either node is down. The surviving node then can't start or
change guests. Add a tiny third vote with a **QDevice** on any always-on Debian box, such as a
Raspberry Pi:

```bash
# On the Pi / small box
sudo apt install corosync-qnetd
# On BOTH pve01 and pve02
apt install corosync-qdevice
# On pve01
pvecm qdevice setup <PI_IP>
pvecm status   # expect "Expected votes: 3"
```

## Step 4: scheduled backups

In **Datacenter → Backup**, add a nightly job for 101, 102, and 106 to storage that is *not* on the same
disk. Keep 7 daily and 4 weekly. The `postgres-backup` CronJob adds nightly logical dumps of the agent
database inside the cluster. Copy both offsite (Backblaze B2 through rclone) once there's client data.

## Target layout

```
pve01 (6 threads)                         pve02 (12 threads)
├─ 101 k3s-cp01   [tier=data, NVMe]       ├─ 102 k3s-worker01 [tier=compute]
│   K3s control plane                     │   agentos-worker ×2, n8n, (Ollama)
│   Postgres, Redis, console, scheduler   ├─ 105 pfsense-fw01 (stopped, lab only)
├─ 106 wazuh-mgr01  (monitors both VMs)   └─ (107 splunk01 removed, or kept stopped)
└─ 100 jellyfin
QDevice on a Pi → 3 votes, so either host can reboot safely
```
