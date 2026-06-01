---
name: deploy-virtual-space-trotting-on-linode
description: Use when updating, inspecting, starting, stopping, or opening a prepared Linode-hosted VirtualSpaceTrotting systemd service.
---

# Deploy Or Update VirtualSpaceTrotting On Linode

## Overview

Use the one-shot path for the first live install:

```bash
make deploy-linode-one-shot DEPLOY_LINODE_ARGS="--remote-name prod --region us-east --profile small"
```

Then use the normalized remote receipt layer for day-2 work:

```bash
make remote-use REMOTE=prod
make remote-status
make remote-logs
make remote-update
make remote-open-site
```

`make deploy-linode-one-shot` creates or attaches a Linode, waits for SSH, uploads a release bundle from committed `HEAD`, installs Spin on the host if needed, writes a `virtual-space-trotting` systemd service, checks `http://127.0.0.1:3000/health`, and writes the day-2 remote receipt.

`make remote-update` builds a release bundle from committed `HEAD`, uploads it to the selected remote, swaps `/opt/virtual-space-trotting`, restarts the `virtual-space-trotting` systemd service, checks `http://127.0.0.1:3000/health`, and refreshes the local remote receipt metadata.

## Preconditions

- The app scaffold exists and `make build` succeeds.
- First deploy requires `LINODE_TOKEN` in `.env.local`, the environment, or `DEPLOY_LINODE_ARGS`.
- Day-2 deploy requires `.vst/remotes/<name>.json` and a compatible `virtual-space-trotting` systemd service.
- Current intended changes are committed; dirty worktree changes are not included in release bundles.

## Canonical Commands

```bash
make test
make test-code-quality
make build
make deploy-linode-one-shot DEPLOY_LINODE_ARGS="--remote-name prod --region us-east --profile small"
make remote-update
```

For inspection:

```bash
make remote-status
make remote-logs
make remote-open-site
```

## Operations Reference

See `references/OPERATIONS.md`.
