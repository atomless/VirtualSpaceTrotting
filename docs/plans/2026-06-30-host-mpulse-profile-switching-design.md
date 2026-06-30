# Host-Side mPulse Profile Switching Design

## Status

Approved on 2026-06-30.

## Objective

Allow an authorised engineer with SSH access to the shared Linode to inspect, edit, validate, activate, verify, and roll back named mPulse endpoint/API-key profiles without rebuilding the site, restarting Spin, or relying on a particular workstation or Jenkins job.

## Current State

- The public site is served by Caddy at https://172.239.117.12.sslip.io.
- Caddy reverse-proxies to Spin on 127.0.0.1:3000.
- The Boomerang endpoint is hard-coded in site/src/app.html.
- BOOMERANG_API_KEY is substituted during the release build.
- Changing either value therefore requires a complete release build and remote deployment.
- The host is Ubuntu 24.04 with Caddy 2.6.2, systemd 255, and sudo 1.9.15p5.
- The host currently has one human-capable login, vst. Individual accounts are required before audit records can reliably identify individual engineers.

## Research Decisions

- Akamai recommends individual limited Linux users, SSH keys, and temporary privilege elevation with sudo instead of routine root access. See [Set up and secure a compute instance](https://techdocs.akamai.com/cloud-computing/docs/set-up-and-secure-a-compute-instance) and [Grant a developer access](https://techdocs.akamai.com/cloud-computing/docs/grant-a-developer-access).
- The Filesystem Hierarchy Standard places host-specific configuration for software under /opt in /etc/opt/<package> and mutable state in /var/opt/<package>. See [the /etc hierarchy](https://specifications.freedesktop.org/fhs/latest/etc.html) and [the /opt hierarchy](https://specifications.freedesktop.org/fhs/latest/opt.html).
- Caddy handle blocks can serve one exact path and use a fallback reverse proxy, while header can set Cache-Control. Candidate configurations should pass caddy validate and be applied with a graceful reload. See [handle](https://caddyserver.com/docs/caddyfile/directives/handle), [header](https://caddyserver.com/docs/caddyfile/directives/header), and [Caddy command line](https://caddyserver.com/docs/command-line).
- systemd-tmpfiles is suitable for creating persistent application directories with controlled ownership and modes. See [systemd-tmpfiles](https://www.freedesktop.org/software/systemd/man/systemd-tmpfiles.html).
- sudo warns that root-run editors remain hazardous and identifies sudoedit as the safer pattern. The design goes further: editing stays entirely unprivileged, and only validated content crosses a narrow privileged-helper boundary. See [sudoers(5)](https://www.sudo.ws/docs/man/1.9.14/sudoers.man.pdf).
- journald provides filterable structured operational records. See [journalctl](https://www.freedesktop.org/software/systemd/man/255/journalctl.html).

## Non-Goals

- Switching a profile inside an already-loaded browser document.
- Adding a web administration interface.
- Requiring Jenkins for profile maintenance or switching.
- Storing the real registry or inactive tenant inventory in the public repository.
- Enabling SPA instrumentation or creating artificial requests to generate beacons.
- Allowing arbitrary endpoint/key values on a privileged switch command.

## Filesystem Layout

| Path | Purpose | Ownership and mode |
| --- | --- | --- |
| /etc/opt/virtual-space-trotting/mpulse-profiles.json | Authoritative host registry | root:vst-mpulse-operators, 0640 |
| /var/opt/virtual-space-trotting/mpulse/state/active-profile | Selected profile name | root:vst-mpulse-operators, 0640 |
| /var/opt/virtual-space-trotting/mpulse/state/history.jsonl | Sanitized operator-readable history | root:vst-mpulse-operators, 0640 |
| /var/opt/virtual-space-trotting/mpulse/state/registry-backups/ | Bounded registry backup rotation | root:vst-mpulse-operators, 0750 |
| /var/opt/virtual-space-trotting/mpulse/public/mpulse-config.js | Browser-readable generated configuration | root:caddy, 0640 |
| /run/lock/vst-mpulse.lock | Concurrent mutation lock | root-managed |
| /usr/local/bin/vst-mpulse | Unprivileged operator CLI | root:root, 0755 |
| /usr/local/lib/virtual-space-trotting/vst-mpulse-admin | Privileged helper | root:root, 0755 |
| /usr/local/lib/virtual-space-trotting/mpulse_profiles.py | Shared validation and rendering module | root:root, 0644 |
| /etc/sudoers.d/vst-mpulse | Narrow helper permission for the operator group | root:root, 0440 |

systemd-tmpfiles creates and repairs the /var/opt state directories. The registry remains administrator-managed configuration under /etc/opt.

## Registry Format

The repository contains a schema and placeholder example, but never the real registry:

~~~json
{
  "schema": "virtual-space-trotting.mpulse-profiles.v1",
  "profiles": {
    "example": {
      "description": "Example profile only",
      "script_base_url": "https://collector.example.com/boomerang/",
      "api_key": "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
    }
  }
}
~~~

Validation requires:

- a known schema version;
- at least one profile;
- unique lowercase profile names using letters, numbers, and hyphens;
- an HTTPS endpoint with no user-info, query, or fragment;
- a path ending in /boomerang/;
- an mPulse key of five groups of five alphanumeric characters separated by hyphens;
- a bounded description string;
- no unknown fields.

## Operator Interface

~~~text
vst-mpulse list
vst-mpulse current
vst-mpulse verify
vst-mpulse history
vst-mpulse registry validate FILE
vst-mpulse registry edit
vst-mpulse switch PROFILE
vst-mpulse rollback
~~~

Read-only commands run without sudo. Mutation commands invoke the privileged helper internally, so engineers do not run an editor as root.

registry edit copies the registry into a user-owned temporary file, opens the operator's editor, validates the result, probes changed endpoint/key pairs, and pipes the validated JSON to sudo vst-mpulse-admin install-registry. The privileged helper reads standard input, revalidates independently, locks mutations, writes a backup, and atomically replaces the registry. API keys never appear in command arguments or shell history.

## Switching Flow

1. Resolve the selected name from the root-owned registry.
2. Acquire the exclusive mutation lock.
3. Validate the selected endpoint/key pair.
4. Fetch the composed Boomerang script URL with a bounded timeout.
5. Require an HTTPS success response and JavaScript-compatible content.
6. Generate mpulse-config.js with JSON serialization, never string interpolation.
7. Preserve the previous active state and generated file.
8. Atomically rename the new files into place.
9. Verify the public /mpulse-config.js, /health, selected script URL, and selected profile name.
10. Restore the previous files automatically if any post-activation check fails.
11. Emit a structured journald record and release the lock.

Switching does not modify Caddy configuration and does not restart or reload Caddy, Spin, or systemd services. Existing documents retain their loaded profile; new or refreshed documents use the new profile.

## Browser Configuration

The page synchronously loads this same-origin script before the Boomerang bootstrap:

~~~html
<script src="/mpulse-config.js"></script>
~~~

The generated script defines one frozen object:

~~~javascript
window.VST_MPULSE_PROFILE = Object.freeze({
  name: "example",
  scriptBaseUrl: "https://collector.example.com/boomerang/",
  apiKey: "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
});
~~~

The Boomerang bootstrap reads both values from this object. A committed static placeholder defines no profile, leaving instrumentation inert in builds that are not behind the configured Caddy route.

Caddy serves only /mpulse-config.js from /var/opt/virtual-space-trotting/mpulse/public and continues proxying every other path to Spin:

~~~caddyfile
handle /mpulse-config.js {
  root * /var/opt/virtual-space-trotting/mpulse/public
  header Cache-Control "no-store"
  header Content-Type "application/javascript; charset=utf-8"
  file_server
}

handle {
  reverse_proxy 127.0.0.1:3000
}
~~~

The Caddyfile keeps the existing compression, HTML cache, TLS, and security-header behavior.

## Permissions And Audit

- Each engineer should use an individual limited account and SSH key.
- Membership of vst-mpulse-operators grants registry read access and permission to invoke only the privileged helper.
- The helper exposes a closed command set: install-registry, switch, and rollback.
- The helper accepts no shell command and no arbitrary endpoint/key switch arguments.
- Registry content is accepted through standard input and independently validated.
- All mutable operations use atomic replacement and an exclusive file lock.
- Journald and the sanitized history file record timestamp, SUDO_USER, action, old/new profile, endpoint hostname, registry checksum, and outcome.
- Journald never receives full API keys or registry contents.
- Until individual accounts exist, actions performed through the shared vst login can only be attributed to vst.

## Failure And Recovery

- Invalid registry edits never reach /etc/opt.
- An unreachable or invalid candidate endpoint prevents activation.
- Failed public verification restores the previous generated file and active name.
- rollback reactivates the most recent valid previous profile through the same validation path.
- Registry installation retains a bounded rotation of timestamped backups.
- Concurrent edit, switch, rollback, deployment, or upgrade operations fail cleanly rather than interleave.
- If /mpulse-config.js is absent or malformed, the page remains uninstrumented rather than falling back to an old embedded tenant.

## Deployment Integration

Installation is an explicit, idempotent host operation:

1. Install or upgrade the CLI and privileged helper.
2. Create the operator group without changing unrelated sudo membership.
3. Install and validate tmpfiles and sudoers configuration.
4. Initialize the real registry only from an explicitly supplied local file or interactive host edit.
5. Activate an explicitly selected initial profile.
6. Generate and validate a candidate Caddyfile.
7. Back up the existing Caddyfile, install the candidate, validate it, and gracefully reload Caddy.
8. Deploy the application version that reads /mpulse-config.js.
9. Verify public HTTPS, health, active profile, script request, and service status.

Ordinary future make remote-update operations replace /opt/virtual-space-trotting only. They must preserve /etc/opt, /var/opt, the active profile, registry, backups, and audit history.

The initial migration names the currently deployed Alma pair dev-alma. The real key is read from existing gitignored deployment state or entered on the host; it is never written into a committed file.

## Acceptance Criteria

1. The public repository contains no real registry or inactive mPulse keys.
2. Authorised operators can list, inspect, edit, switch, verify, view history, and roll back profiles over SSH.
3. Root never launches the operator's editor.
4. Invalid profile data and failed probes leave the active configuration unchanged.
5. New page loads use the selected endpoint/key pair without a service restart.
6. Existing HTTPS, security headers, /health, Spin binding, firewall, and fail2ban behavior remain intact.
7. Concurrent mutations cannot corrupt configuration or state.
8. Logs identify the invoking Unix account and never include full keys.
9. A normal code deployment preserves registry and selection.
10. Caddy configuration passes caddy validate before installation and reloads gracefully.
11. Automated tests cover validation, atomicity, locking, rollback, permissions, rendering, migration, and deployment preservation.
12. Direct post-install checks confirm the active profile, generated script, composed Boomerang URL, JavaScript response, and system service health.

## Rollback

The feature rollout keeps a backup of the previous Caddyfile and application release. To remove the feature:

1. Restore the previous Caddyfile and validate it.
2. Gracefully reload Caddy.
3. Roll back the application release to the build-time Boomerang configuration.
4. Remove the sudoers and tmpfiles entries.
5. Remove installed CLI/helper files.
6. Preserve /etc/opt and /var/opt until the rollback is verified and operational data is intentionally retired.
