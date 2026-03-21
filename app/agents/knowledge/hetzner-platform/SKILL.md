---
name: hetzner-platform
description: Hetzner Cloud infrastructure managed by Pulumi, including platform-infra and nexus-infra
version: 1.0.0
tags:
  - hetzner
  - pulumi
  - infrastructure
  - cloud
---

# Hetzner Cloud Platform

## Provider
- Hetzner Cloud, location hel1 (Helsinki), datacenter hel1-dc2
- Managed by Pulumi (TypeScript runtime, npm package manager)
- Secrets in Pulumi ESC (environment: nexus/secrets, platform-infra/secrets)

## NEXUS Infrastructure (nexus-infra repo)
- **Server**: CX43 (8 vCPU, 16GB RAM, 160GB disk) ~$10/mo
- **Network**: 10.1.0.0/16, subnet 10.1.1.0/24
- **Server IP**: 10.1.1.10 (private), public IPv4
- **Firewall**: SSH + ICMP only
- **OS**: Ubuntu 24.04
- **Provisioning**: cloud-init (Docker CE, swap, sysctl tuning)
- **Protection**: deleteProtection, rebuildProtection, ignoreChanges on userData

### Pulumi Resources (10)
```
hcloud:Server          nexus-server
hcloud:Network         nexus-network
hcloud:NetworkSubnet   nexus-subnet
hcloud:ServerNetwork   nexus-server-net
hcloud:SshKey          nexus-ssh-key
hcloud:Firewall        fw-nexus-dev
command:local:Command  generate-ssh-key
```

## Platform Infrastructure (platform-infra repo)
- **Control Plane**: cx23 (3 vCPU, 4GB) — Coolify, Traefik, Grafana, Uptime Kuma
- **Data Plane**: cx33 (4 vCPU, 8GB) — PostgreSQL 16+pgvector, PgBouncer, Redis 7, MinIO
- **App Plane A**: cx33 (4 vCPU, 8GB) — Application containers via Coolify
- **Network**: 10.0.0.0/16, subnet 10.0.1.0/24
- **Access**: Tailscale VPN only

### Projects Hosted
| Project | Stack | DB | Redis | MinIO |
|---------|-------|-----|-------|-------|
| Whabi | WhatsApp CRM | whabi | DB 0 | whabi-media, whabi-documents |
| Docflow | EHR system | docflow | DB 1 | docflow-documents |
| Aurora | Voice PWA (Nuxt 3) | aurora | DB 2 | aurora-assets |

## Pulumi Conventions
- TypeScript runtime with npm
- Stack config in Pulumi.<stack>.yaml
- ESC environments for secrets (never hardcode)
- Tags: project, environment, role labels on all resources
- ignoreChanges on userData (cloud-init only runs on first boot)
- protect: true on critical servers

## Do NOT
- Modify cloud-init after server creation (use ignoreChanges)
- Remove deleteProtection without explicit approval
- Create resources without labels
- Hardcode Hetzner tokens (use ESC)
