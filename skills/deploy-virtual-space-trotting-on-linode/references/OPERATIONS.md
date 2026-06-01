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
make deploy-linode-one-shot DEPLOY_LINODE_ARGS="--remote-name prod --region us-east --profile small"
```

Use `make prepare-linode-host` only when you want to create or record a Linode receipt without installing the application service.

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

### First Deploy Not Publicly Reachable

The default first deploy serves Spin on port `3000` and records `http://<server-ip>:3000`. If you want a domain/TLS front door, point your reverse proxy or DNS at the host and rerun the deploy with `--public-base-url <url>` so local receipts open the canonical URL.
