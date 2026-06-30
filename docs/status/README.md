# VirtualSpaceTrotting Project Status

Last updated: 2026-06-30.

## Product Status

VirtualSpaceTrotting is a pre-launch static site for exercising Akamai mPulse Boomerang real user monitoring across a deep, realistic browsing experience. All locations, descriptions, coordinates, and satellite-style images are fictional generated content.

The current launch seed contains 64 locations across 11 categories. The map index displays 12 locations per page, and category pages paginate when they contain enough entries.

## Application Status

- SvelteKit statically prerenders the public site.
- The browsing structure includes the home page, map index, paginated map listings, location details, category listings, and editorial content.
- Reusable components provide navigation, location lists, pagination, metadata, and sidebars.
- Deterministic generated preview imagery includes provenance metadata and can be rebuilt without additional API credentials.
- A Rust Spin component serves the static output and provides `/health`.

## mPulse Status

- The document head contains Akamai's non-blocking Boomerang loader snippet version 14.
- The active endpoint and API-key pair come from a host-managed named profile registry rather than the release build.
- Operators can list, switch, verify, edit, and roll back profiles over SSH with `vst-mpulse`.
- Page-load instrumentation is enriched by the plugins supplied by the active tenant.
- Site instrumentation covers consequential Fetch/XHR activity, post-load errors, first input, unload metrics, and back-forward cache restoration where the tenant build does not already provide the corresponding behavior.
- SPA instrumentation is deliberately excluded because the intended instrumentation model is a static multi-page site.

See [Boomerang instrumentation](../boomerang-instrumentation.md) for the plugin and beacon inventory.

## Deployment Status

- The production site runs on Linode as a systemd-managed Spin service behind Caddy.
- Spin listens only on `127.0.0.1:3000`; Caddy provides public HTTP-to-HTTPS redirection and TLS termination.
- UFW, the Linode cloud firewall, SSH restrictions, and Fail2ban protect the host.
- Release bundles are built from committed `HEAD` and remain independent of the selected mPulse tenant.
- Profile configuration and state live under `/etc/opt/virtual-space-trotting` and `/var/opt/virtual-space-trotting`, so ordinary application deployments preserve them.
- Deployment and profile mutations share an exclusive lock and automatically roll back on failed verification.

The live site is [https://172.239.117.12.sslip.io](https://172.239.117.12.sslip.io).

## Remaining Work

- Add individual limited Linux accounts and SSH keys for team members so profile audit history identifies each operator rather than the shared `vst` account.
- Add further authorised mPulse endpoint/key profiles as testing requires them.
- Reassess the launch content target and generated image corpus before public launch.
- Complete representative browser-level beacon checks whenever the active tenant's delivered plugin set changes.
