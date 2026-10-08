# K3s Kubernetes Homelab

A hands-on Kubernetes homelab built on Proxmox VE using K3s, Ubuntu Server, and declarative Kubernetes manifests.

## Architecture

Physical Hosts (Proxmox VE 9 cluster `tazlab`):
- pve01: Dell OptiPlex Micro (6 threads, NVMe-backed `nvme-lvm`)
- pve02: Dell OptiPlex Micro (12 threads)

Kubernetes Cluster:
- k3s-cp01 (on pve01)
  - Role: Control Plane + data node (`homelab.tazlab/tier=data`)
  - IP: 192.168.1.30
  - Ubuntu Server
  - K3s

- k3s-worker01 (on pve02)
  - Role: Worker + compute node (`homelab.tazlab/tier=compute`)
  - IP: 192.168.1.31
  - Ubuntu Server
  - K3s Agent

Other guests: Wazuh manager, pfSense (lab), Jellyfin. See [docs/ai-agents/PROXMOX-PLAN.md](docs/ai-agents/PROXMOX-PLAN.md).

## Current Kubernetes Workload

### homelab-web

NGINX-based test application used to validate:

- Multi-node pod scheduling
- Kubernetes Deployments
- Replica scaling
- Service discovery
- NodePort networking
- Automatic pod recovery
- Declarative configuration with YAML

Current configuration:

- 4 replicas
- CPU requests and limits
- Memory requests and limits
- NodePort service
- Workloads distributed across both Kubernetes nodes

### agent-platform (AgentOS)

A 40-agent AI team (Claude API) that runs a one-person AI automation studio:
research, lead generation, outreach drafts, proposals, delivery, content, and finance.
Agents unlock in phases, run under per-agent and global budgets, and can't touch the
outside world without a human approval, which n8n then executes.

- 60-day sprint (start here): [docs/ai-agents/60-DAY-SPRINT.md](docs/ai-agents/60-DAY-SPRINT.md)
- Plan, team, costs, roadmap: [docs/ai-agents/BLUEPRINT.md](docs/ai-agents/BLUEPRINT.md)
- Hardware reuse plan: [docs/ai-agents/PROXMOX-PLAN.md](docs/ai-agents/PROXMOX-PLAN.md)
- Deployment runbook: [docs/ai-agents/DEPLOY.md](docs/ai-agents/DEPLOY.md)

Components: Postgres, Redis, n8n, optional Ollama, and the AgentOS runtime
(scheduler, worker pool, and the Mission Control console) in the `agents` namespace.

## Repository Structure

```
homelab-k8s/
├── apps/
│   ├── homelab-web/            # NGINX test workload
│   └── agent-platform/         # AgentOS: kustomize stack + roster.yaml + runtime/ (Python)
├── docs/ai-agents/             # Blueprint, Proxmox plan, deploy runbook
├── namespaces/                 # homelab, agents
├── networking/ingress/         # Traefik ingresses
├── security/
│   ├── network-policies/       # default-deny + egress-only for agents
│   └── rbac/
└── .github/workflows/          # AgentOS image build (GHCR)
```

## Skills Demonstrated

- Proxmox virtualization
- Linux server administration
- K3s / Kubernetes
- Multi-node cluster configuration
- containerd
- Kubernetes networking
- Deployments and Services
- Resource requests and limits
- Self-healing workloads
- Infrastructure as Code
- Git version control

## Security

Cluster credentials, tokens, private keys, kubeconfig files, and environment files are excluded from source control.

## Planned Improvements

- TLS (cert-manager) for ingress
- Encrypted secrets in Git (SOPS / Sealed Secrets)
- Monitoring and metrics
- Centralized logging
- Kubernetes security monitoring
- GitOps
- Additional Proxmox nodes
