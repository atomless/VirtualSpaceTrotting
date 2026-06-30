# ADR 0001: Host-Managed mPulse Profiles

## Status

Accepted on 2026-06-30.

## Context

VirtualSpaceTrotting previously selected one mPulse tenant during the static release build. The API key came from local environment state, while the paired Boomerang script endpoint was embedded in the page template. Switching tenants therefore depended on a particular engineering checkout and required a rebuild and deployment.

The shared Linode is the durable operational boundary. Engineers with access to that host need to inspect, update, switch, verify, and roll back named endpoint/key pairs without depending on Jenkins, a particular workstation, or a web administration surface.

An mPulse page key is necessarily delivered to browsers, but a registry of inactive tenants still reveals operational inventory and does not belong in a public repository.

## Decision

The authoritative registry is stored at `/etc/opt/virtual-space-trotting/mpulse-profiles.json`. Mutable selection, sanitized history, and bounded registry backups live under `/var/opt/virtual-space-trotting/mpulse/`.

Caddy serves only the generated `/mpulse-config.js` from host state with `Cache-Control: no-store`; all other requests continue to the localhost Spin service. Static release bundles contain an inert placeholder and no tenant profile.

Operators use `vst-mpulse`. Read-only commands run unprivileged. Registry installation, switching, and rollback cross a narrow sudo boundary implemented by a root-owned helper with a closed argument parser, independent validation, endpoint probing, an exclusive lock, atomic writes, public verification, and automatic rollback. Registry editing occurs in a user-owned temporary file, never in a root editor.

The real registry is initialized only from an explicitly supplied gitignored file and is never replaced by ordinary code deployment. Each engineer should use an individual limited account and SSH key in `vst-mpulse-operators`; a shared login cannot provide person-level audit attribution.

## Consequences

- Switching a profile no longer rebuilds or restarts the site; refreshed pages use the new pair.
- Code releases are tenant-neutral and can move between environments unchanged.
- Caddy, filesystem ownership, sudoers, journald, and deployment locking become part of the operational contract.
- The host is now the source of truth for profile inventory, so its protected registry and backups must be included in operational recovery planning.
- Individual Unix accounts are required for useful personal audit records.
- A missing or invalid host profile leaves instrumentation inert instead of silently using stale embedded credentials.

## Alternatives Considered

- Keep build-time environment selection:
  - Upside: minimal host tooling.
  - Downside: rebuilds for every switch and workstation-dependent administration.
- Store a named registry in Git:
  - Upside: familiar review and distribution workflow.
  - Downside: exposes inactive tenant inventory in a public repository.
- Use Jenkins as the registry and switching interface:
  - Upside: centralized access and job history.
  - Downside: adds an unnecessary availability dependency for a host-local operation.
- Add a web administration UI:
  - Upside: approachable interaction.
  - Downside: creates a new network-exposed privileged surface and authentication burden.

## Verification

- Registry parsing, rendering, locking, atomic switching, failed-verification rollback, CLI behavior, installer permissions, Caddy routing, and deployment preservation have automated tests.
- Candidate Caddy and sudoers configurations are validated before installation.
- `make remote-mpulse-verify` checks the endpoint, generated public configuration, cache policy, and public health path.
- `make remote-update` acquires the profile mutation lock and verifies the active profile after service health succeeds.
