---
name: prepare-virtual-space-trotting-on-linode
description: Use when preparing or attaching a Linode host for this repository and writing the local day-2 remote receipt.
---

# Prepare VirtualSpaceTrotting On Linode

## Overview

Use the repository-native helper instead of manual setup narration:

```bash
make prepare-linode-host PREPARE_LINODE_ARGS="--remote-name prod --region us-east --profile small"
```

The helper:

- validates or captures `LINODE_TOKEN`,
- stores local secrets in `.env.local`,
- creates or reuses a dedicated SSH keypair,
- creates a fresh Linode instance or inspects `--existing-instance-id`,
- writes `.vst/linode-host-setup.json`,
- writes `.vst/remotes/<name>.json`,
- selects the active remote by writing `VST_ACTIVE_REMOTE` to `.env.local`.

## Human Boundary

The operator must already have a Linode account. If `LINODE_TOKEN` is missing, ask them to create a Linode Personal Access Token in Cloud Manager and either paste it into the prompt or add it to `.env.local`.

## Useful Flags

- `--existing-instance-id <id>`
- `--remote-name <name>`
- `--region <slug>`
- `--profile small|medium|large`
- `--type <linode-plan>`
- `--image <linode-image>`
- `--operator-ip <cidr>`
- `--public-base-url <url>`
- `--yes`

## Handoff

Stop after setup if the application runtime has not been scaffolded and deployed yet. The receipt proves host orientation only; it does not prove the site is live.

Use `../deploy-virtual-space-trotting-on-linode/SKILL.md` for day-2 update/status/log operations after a service exists on the host.
