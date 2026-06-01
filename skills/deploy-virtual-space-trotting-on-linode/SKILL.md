---
name: deploy-virtual-space-trotting-on-linode
description: Use when updating, inspecting, starting, stopping, or opening a prepared Linode-hosted VirtualSpaceTrotting systemd service.
---

# Deploy Or Update VirtualSpaceTrotting On Linode

## Overview

Use the normalized remote receipt layer:

```bash
make remote-use REMOTE=prod
make remote-status
make remote-logs
make remote-update
make remote-open-site
```

`make remote-update` builds a release bundle from committed `HEAD`, uploads it to the selected remote, swaps `/opt/virtual-space-trotting`, restarts the `virtual-space-trotting` systemd service, checks `http://127.0.0.1:3000/health`, and refreshes the local remote receipt metadata.

## Preconditions

- `.vst/remotes/<name>.json` exists.
- The remote host already has a compatible `virtual-space-trotting` systemd service.
- The app scaffold exists and `make build` succeeds.
- Current intended changes are committed; dirty worktree changes are not included in the bundle.

## Canonical Commands

```bash
make test
make test-code-quality
make build
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
