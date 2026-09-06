# K3s Kubernetes Homelab

A hands-on Kubernetes homelab built on Proxmox VE using K3s, Ubuntu Server, and declarative Kubernetes manifests.

## Architecture

Physical Host:
- Proxmox VE 9
- Dell OptiPlex
- Intel-based virtualization host

Kubernetes Cluster:
- k3s-cp01
  - Role: Control Plane
  - IP: 192.168.1.30
  - Ubuntu Server
  - K3s

- k3s-worker01
  - Role: Worker
  - IP: 192.168.1.31
  - Ubuntu Server
  - K3s Agent

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

## Repository Structure

homelab-k8s/
├── apps/
│   └── homelab-web/
│       ├── deployment.yaml
│       └── service.yaml
└── README.md

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

- Kubernetes namespaces
- RBAC and least privilege
- NetworkPolicies
- Persistent storage
- Ingress routing
- TLS
- Monitoring and metrics
- Centralized logging
- Kubernetes security monitoring
- GitOps
- Additional Proxmox nodes
