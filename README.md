# VirtualSpaceTrotting

![VirtualSpaceTrotting paginated maps view](docs/assets/virtual-space-trotting-page-5.png)

VirtualSpaceTrotting exists first as a realistic test site for Akamai mPulse Boomerang real user monitoring. The fictional atlas gives Boomerang enough page depth, navigation variety, generated imagery, and static asset weight to exercise browse, category, detail, and content-heavy page views without relying on a production customer site.

The public browsing structure is a deep fictional atlas: map/category browsing, popular and latest lists, location detail pages, and lightweight editorial context. Every location, image, and place description in this project must be fictional and clearly treated as generated content.

The page template contains the origin-side Akamai mPulse Boomerang loader. Code deployments are tenant-neutral; the Linode selects a named endpoint and API-key pair from a host-managed registry.

References:

- [Akamai mPulse origin setup](https://techdocs.akamai.com/mpulse/docs/set-up-behavior-options)
- [Akamai Boomerang implementation guide](https://techdocs.akamai.com/mpulse-boomerang/docs/implementation)
- [Akamai mPulse key concepts](https://techdocs.akamai.com/mpulse/docs/key-concepts-terms)

## Setup And Deploy

The intended setup path is deliberately small:

1. Clone the repository.

   ```bash
   git clone https://github.com/atomless/VirtualSpaceTrotting.git
   cd VirtualSpaceTrotting
   ```

2. Add the local setup values.

   ```bash
   cp .env.example .env.local
   $EDITOR .env.local
   chmod 600 .env.local
   ```

   Fill in `LINODE_TOKEN`:

   ```bash
   LINODE_TOKEN=paste-your-linode-token-here
   ```

   `.env.local` is gitignored. Do not commit it.

3. Create the Akamai mPulse Boomerang app and get this site's API key when you are ready to collect mPulse data.

   - Make sure your Akamai account has mPulse App Administrator privileges.
   - Log in to mPulse.
   - Choose `New > App`.
   - Select `HTML5` for this static multi-page site.
   - Enter the deployed site domain or public URL.
   - Open the app's `General` tab and enable `Show JavaScript` next to the API key.
   - Record both the generated mPulse API key and the script base URL paired with it.

   Akamai's mPulse API key is a public page instrumentation key, not a REST API secret. It identifies this site's beacons and is necessarily delivered to the browser.

4. Set up the remote and deploy the site.

   Use this exact instruction:

   > Run the project setup, create or update the Linode remote named `prod`, deploy the current committed `main` branch, and verify the public `/health` endpoint and a paginated maps page.

   The agent should run the project helper:

   ```bash
   make deploy-linode-one-shot DEPLOY_LINODE_ARGS="--remote-name prod --region gb-lon --profile small"
   ```

5. Initialize host-side mPulse administration from an explicit gitignored registry.

   Create `.vst/mpulse-profiles.json` with one or more named profiles:

   ```json
   {
     "schema": "virtual-space-trotting.mpulse-profiles.v1",
     "profiles": {
       "dev-alma": {
         "description": "Development Alma tenant",
         "script_base_url": "https://collector.example.com/boomerang/",
         "api_key": "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
       }
     }
   }
   ```

   `.vst/` is gitignored. Never put the real profile registry in this public repository. Install it and choose the initial profile explicitly:

   ```bash
   chmod 600 .vst/mpulse-profiles.json
   make remote-install-mpulse-admin \
     MPULSE_REGISTRY_FILE=.vst/mpulse-profiles.json \
     MPULSE_PROFILE=dev-alma
   ```

   The setup creates the restricted `vst-mpulse-operators` group. Reconnect over SSH after first installation so the new group membership takes effect.

6. After the first deploy, ordinary code updates use:

   ```bash
   make remote-update
   ```

Release bundles are built from committed `HEAD`. Commit and push the work you want deployed before asking the agent to deploy or update the remote.

## Switch mPulse Profiles

Connect to the Linode over SSH, list the defined profiles, and switch to the required one:

```bash
vst-mpulse list
vst-mpulse current
vst-mpulse switch PROFILE
vst-mpulse current
vst-mpulse verify
```

`switch` accepts only a name already defined in the host registry. It validates and probes the paired endpoint and API key, atomically updates `/mpulse-config.js`, and verifies the public result. It does not rebuild the site or restart Spin. New page loads use the selected profile; pages already open retain the profile they originally loaded.

If an operator selects the wrong valid profile, restore the previous one and inspect the sanitized change history:

```bash
vst-mpulse rollback
vst-mpulse history
```

Read-only checks can also be run from a configured engineering checkout:

```bash
make remote-mpulse-list
make remote-mpulse-current
make remote-mpulse-verify
```

If activation or public verification fails, the helper automatically restores the previously active profile.

### Add or Edit Profiles

The authoritative profile registry lives on the Linode. To add a profile or change an existing endpoint/key pair, connect over SSH and run:

```bash
vst-mpulse registry edit
```

The command opens a user-owned temporary copy in `$VISUAL` or `$EDITOR`. When the editor closes, it validates the complete registry and probes every changed endpoint/key pair before the privileged helper atomically installs it. Root never runs the editor. Registry changes do not alter the active profile, so run `vst-mpulse switch PROFILE` afterwards when the new or edited profile should become active.

Previous registries are retained in a bounded backup rotation under `/var/opt/virtual-space-trotting/mpulse/state/registry-backups/`. The real registry must remain on the host or in gitignored local state; never commit it to this public repository.

Engineers should use individual limited Linux accounts with their own SSH keys and membership of `vst-mpulse-operators`. The shared `vst` account works, but its history entries can identify only that shared account.

## Boomerang Snippet

VirtualSpaceTrotting uses origin-side mPulse tagging because the current launch target is a Linode-hosted Spin site. The committed page template permanently contains Akamai's non-blocking loader in the document `<head>`, after position-sensitive metadata and before the app's main scripts. Profile switching does not edit this HTML or replace the loader.

The committed page template loads a same-origin host configuration before the non-blocking loader:

```html
<script src="/mpulse-config.js"></script>
<script>
  var profile = window.VST_MPULSE_PROFILE;
  // The loader validates the pair, then loads profile.scriptBaseUrl + profile.apiKey.
</script>
```

The page uses Akamai's documented non-blocking loader snippet version 14. Caddy serves the active pair from root-managed host state with `Cache-Control: no-store`. The committed placeholder contains no profile, so a standalone static build remains inert.

When an operator runs `vst-mpulse switch PROFILE`, the privileged helper validates and probes the selected registry entry, then atomically regenerates `/var/opt/virtual-space-trotting/mpulse/public/mpulse-config.js`. Caddy serves that file at `/mpulse-config.js`. On the next page load, the unchanged loader reads the new `scriptBaseUrl` and `apiKey`, composes the paired Boomerang script URL, and loads it. No site rebuild, Spin restart, or Caddy reload is involved; pages that were already open retain the profile they originally loaded.

### Non-Page-Load Beacons

When a valid host profile is active, the site also reproduces the consequential non-page-load triggers used by the reference site:

| Trigger | Beacon behavior |
| --- | --- |
| First click, pointer, touch, or key input | Sends one custom first-input beacon after the page-load beacon. |
| XHR or Fetch work that changes the rendered page | Groups concurrent requests and sends one `xhr` response beacon. Background requests with no relevant DOM mutation are ignored. |
| Uncaught errors, unhandled promise rejections, console errors, and browser reports | Deduplicates and batches up to ten fallback error reports. |
| Leaving a page | Sends one unload-safe beacon when CLS, FID, or INP data is available. A page entering the back-forward cache is not treated as an unload. |
| Restoring a page from the back-forward cache | Sends a `bfcache` response beacon when the tenant's Boomerang build does not already provide the BFCache plugin. |

The instrumentation checks the Boomerang build delivered for the active mPulse profile. Official `AutoXHR`, `Errors`, and `BFCache` plugins take precedence; the site's corresponding fallback is installed only when that plugin is absent. mPulse loader, configuration, collector, and Akamai mapping requests are always excluded from request instrumentation. A missing or malformed host profile leaves both the loader and these listeners inert.

See [Boomerang instrumentation](docs/boomerang-instrumentation.md) for the plugin inventory, emitted beacon catalogue, deliberate exclusions, and possible extensions.

## Current Status

The repository has been initialized with:

- project governance tailored to this repository,
- lean Linode setup and remote-update helper patterns,
- test coverage for the helper layer,
- Makefile targets for setup, verification, and remote operations.
- a SvelteKit static site with semantic browsing routes,
- deterministic fictional preview imagery and provenance metadata,
- a Rust Spin health component and static-file serving manifest,
- a first-run Linode deploy helper that installs Spin as a systemd service.

## Local Commands

```bash
make setup
make test
make test-code-quality
make build
```

Linode host setup and day-2 operations:

```bash
make deploy-linode-one-shot DEPLOY_LINODE_ARGS="--remote-name prod --region gb-lon --profile small"
make remote-use REMOTE=prod
make remote-status
make remote-update
```

`make deploy-linode-one-shot` and `make remote-update` ship committed `HEAD`; uncommitted changes are not included in the release bundle.

## Content Notes

The current launch seed is 64 fictional locations across 11 categories. The map index paginates at 12 locations per page, and category pages paginate once a category has enough depth. Images are procedural generated previews so the site can be built and reviewed without extra API credentials.

## Deployment Notes

The first-run Linode helper needs `LINODE_TOKEN` in `.env.local` and creates or attaches a host. Release bundles never contain an mPulse profile. Optional one-shot profile initialization requires both `--mpulse-registry-file` and `--mpulse-profile`, plus an explicit HTTPS `--public-base-url`; ordinary deployments preserve `/etc/opt/virtual-space-trotting` and `/var/opt/virtual-space-trotting`. By default the basic helper serves Spin on port `3000`; production hosts should retain the documented Caddy, firewall, SSH, and systemd hardening.
