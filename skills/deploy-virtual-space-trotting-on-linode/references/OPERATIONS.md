# VirtualSpaceTrotting Linode Operations

## Local State

- `.env.local`: local secrets and active remote selection.
- `.vst/linode-host-setup.json`: host setup receipt.
- `.vst/remotes/<name>.json`: normalized day-2 remote receipt.

Never commit `.env.local` or `.vst/`.

## Remote Defaults

- SSH user: `vst`
- App dir: `/opt/virtual-space-trotting`
- Service name: `virtual-space-trotting`
- Health path: `/health`

## Setup

```bash
make prepare-linode-host PREPARE_LINODE_ARGS="--remote-name prod --region us-east --profile small"
```

## Day-2 Commands

```bash
make remote-use REMOTE=prod
make remote-status
make remote-logs
make remote-start
make remote-stop
make remote-open-site
make remote-update
```

## Common Failure Modes

### Missing Token

Add `LINODE_TOKEN` to `.env.local` or rerun the setup helper interactively.

### No Active Remote

Run:

```bash
make remote-use REMOTE=<name>
```

### Dirty Worktree Surprise

Release bundles are built from committed `HEAD`. Commit intended changes before `make remote-update`.

### Health Check Fails After Update

The helper attempts rollback when health fails. Inspect:

```bash
make remote-logs
make remote-status
```
