# Host-Side mPulse Profile Switching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Install a secure host-side registry and CLI that lets authorised Linode operators edit, switch, verify, and roll back named mPulse endpoint/API-key profiles without rebuilding or restarting the site.

**Architecture:** The public repository provides validation, operator tooling, a narrow privileged helper, host installation, and an inert browser placeholder, but no real profiles. The Linode stores configuration under /etc/opt and state under /var/opt; Caddy serves an atomically generated no-cache JavaScript file before proxying all other traffic to Spin.

**Tech Stack:** Python 3 standard library, unittest, SvelteKit static output, Caddy 2, systemd-tmpfiles, sudo, journald, Spin, Make.

**Execution constraint:** Work directly on main and do not create a feature branch or worktree, preserving the user's no-dangling-branches requirement.

---

### Task 1: Define And Validate The Registry

**Files:**
- Create: scripts/mpulse_profiles.py
- Create: scripts/tests/test_mpulse_profiles.py
- Create: deploy/mpulse/profiles.schema.json
- Create: deploy/mpulse/profiles.example.json
- Modify: Makefile

**Step 1: Write failing registry tests**

Cover:

- one valid profile;
- multiple valid profiles;
- unknown schema;
- empty profiles;
- invalid names;
- duplicate names after normalization;
- non-HTTPS URLs;
- user-info, query, and fragment rejection;
- paths not ending in /boomerang/;
- malformed keys;
- unknown fields;
- overlong descriptions;
- deterministic rendering of mpulse-config.js;
- rendered JavaScript escaping profile-controlled text.

Expose the intended API in the test:

~~~python
registry = parse_registry_text(text)
profile = registry.profile("dev-alma")
script = render_browser_config(profile)
~~~

**Step 2: Run the focused tests and confirm failure**

Run:

~~~bash
python3 -m unittest scripts.tests.test_mpulse_profiles -v
~~~

Expected: FAIL because scripts.mpulse_profiles does not exist.

**Step 3: Implement the minimal registry module**

Use:

- dataclasses for immutable Registry and Profile values;
- json.loads for parsing;
- urllib.parse.urlsplit for URL validation;
- re.fullmatch for profile names and keys;
- json.dumps for browser configuration serialization;
- a custom RegistryError with concise operator-facing messages.

Do not add third-party dependencies.

**Step 4: Add public schema and placeholder example**

The example contains only collector.example.com and an XXXXX placeholder key. Add a Make target:

~~~make
test-mpulse-profiles:
	$(PYTHON) -m unittest scripts.tests.test_mpulse_profiles -v
~~~

**Step 5: Run focused and umbrella tests**

Run:

~~~bash
make test-mpulse-profiles
make test
~~~

Expected: PASS.

**Step 6: Commit**

~~~bash
git add Makefile deploy/mpulse scripts/mpulse_profiles.py scripts/tests/test_mpulse_profiles.py
git commit -m "Add mPulse profile registry validation"
~~~

### Task 2: Build The Privileged State Engine

**Files:**
- Create: scripts/deploy/vst_mpulse_admin.py
- Create: scripts/tests/test_vst_mpulse_admin.py
- Modify: Makefile

**Step 1: Write failing state-transition tests**

Use temporary directories and injected probe/verification functions. Cover:

- install-registry reads JSON from standard input;
- independent privileged revalidation;
- registry backup before replacement;
- bounded backup rotation;
- active-profile removal rejection;
- successful initial activation;
- successful switch;
- idempotent switch;
- endpoint probe failure before mutation;
- public verification failure after mutation;
- automatic restoration of both prior files;
- rollback;
- no previous state for rollback;
- exclusive non-blocking file lock;
- atomic replacement through same-directory temporary files and os.replace;
- generated file mode and ownership hooks;
- structured journald and history-file audit fields without API keys.

**Step 2: Run the focused tests and confirm failure**

~~~bash
python3 -m unittest scripts.tests.test_vst_mpulse_admin -v
~~~

Expected: FAIL because the privileged module does not exist.

**Step 3: Implement the closed privileged command set**

Implement only:

~~~text
install-registry
switch PROFILE
rollback
~~~

Use fcntl.flock, tempfile.NamedTemporaryFile in the destination directory, os.fsync, os.replace, hashlib.sha256, urllib.request, and subprocess.run with fixed argv for systemd-cat. Never invoke a shell.

All paths use production defaults but can be overridden by explicit test-only constructor arguments. Endpoint and public checks have bounded timeouts.

**Step 4: Add a Make test target and run verification**

~~~bash
make test-mpulse-admin
make test
make test-code-quality
~~~

Expected: PASS.

**Step 5: Commit**

~~~bash
git add Makefile scripts/deploy/vst_mpulse_admin.py scripts/tests/test_vst_mpulse_admin.py
git commit -m "Add privileged mPulse profile state engine"
~~~

### Task 3: Build The Operator CLI

**Files:**
- Create: scripts/deploy/vst_mpulse.py
- Create: scripts/tests/test_vst_mpulse.py
- Modify: Makefile

**Step 1: Write failing CLI tests**

Cover:

- list marks the active profile;
- current prints name, endpoint host, and masked key fingerprint;
- verify checks registry, generated file, public config, health, and script response;
- history reads the sanitized group-readable history file;
- registry validate works on an arbitrary user file;
- registry edit runs the editor as the invoking user;
- cancelled or unchanged edits perform no privileged operation;
- invalid edits never invoke sudo;
- valid edits pipe canonical JSON to the fixed helper command;
- switch accepts only a profile name;
- rollback invokes the fixed helper command;
- full keys never appear in standard output or subprocess argv.

**Step 2: Run the focused tests and confirm failure**

~~~bash
python3 -m unittest scripts.tests.test_vst_mpulse -v
~~~

Expected: FAIL because the CLI does not exist.

**Step 3: Implement the unprivileged CLI**

Use argparse and the shared registry module. Use the user's VISUAL or EDITOR only for the user-owned temporary file. Pipe validated canonical JSON through standard input to:

~~~text
sudo /usr/local/lib/virtual-space-trotting/vst-mpulse-admin install-registry
~~~

Never run the editor through sudo.

**Step 4: Run focused and umbrella verification**

~~~bash
make test-mpulse-cli
make test
make test-code-quality
~~~

Expected: PASS.

**Step 5: Commit**

~~~bash
git add Makefile scripts/deploy/vst_mpulse.py scripts/tests/test_vst_mpulse.py
git commit -m "Add mPulse operator CLI"
~~~

### Task 4: Load Runtime mPulse Configuration In The Site

**Files:**
- Create: site/static/mpulse-config.js
- Modify: site/src/app.html
- Modify: site/svelte.config.js
- Modify: scripts/tests/test_static_output_contract.py
- Modify: site/tests/boomerang-instrumentation.test.mjs
- Modify: scripts/deploy/build_release_bundle.py
- Modify: scripts/tests/test_build_release_bundle.py

**Step 1: Write failing browser and output-contract tests**

Require:

- /mpulse-config.js loads before every Boomerang bootstrap block;
- the template reads only window.VST_MPULSE_PROFILE;
- missing or malformed runtime configuration leaves instrumentation inert;
- the script URL is composed from scriptBaseUrl plus apiKey;
- no real key or collector endpoint is committed;
- a release bundle no longer depends on BOOMERANG_API_KEY;
- release metadata no longer claims to select an mPulse tenant.

**Step 2: Run focused tests and confirm failure**

~~~bash
python3 -m unittest scripts.tests.test_static_output_contract scripts.tests.test_build_release_bundle -v
make test-site
~~~

Expected: FAIL on the new runtime-configuration assertions.

**Step 3: Implement the runtime configuration contract**

The committed placeholder must contain:

~~~javascript
window.VST_MPULSE_PROFILE = null;
~~~

Load it synchronously in head. Validate the object defensively before assigning window.BOOMR_API_key and window.BOOMR.url. Remove build-time endpoint/key substitution and the Svelte public environment-prefix dependency.

**Step 4: Update release bundling**

Remove BOOMERANG_API_KEY lookup and propagation from build_release_bundle.py. A production release must be tenant-neutral; the host configuration selects the tenant.

**Step 5: Run tests and build**

~~~bash
make test
make test-code-quality
make build
~~~

Expected: PASS, and dist/site/mpulse-config.js contains only the inert placeholder.

**Step 6: Commit**

~~~bash
git add site scripts/deploy/build_release_bundle.py scripts/tests
git commit -m "Load mPulse profile from host runtime configuration"
~~~

### Task 5: Install Host Files, Permissions, And Caddy Routing

**Files:**
- Create: scripts/deploy/mpulse_host_setup.py
- Create: scripts/deploy/templates/vst-mpulse-tmpfiles.conf
- Create: scripts/deploy/templates/vst-mpulse-sudoers
- Create: scripts/tests/test_mpulse_host_setup.py
- Modify: Makefile

**Step 1: Write failing installer tests**

Cover:

- production paths and modes;
- operator group creation without granting general sudo;
- installation of root-owned CLI and helper;
- installation of the root-owned shared validation module;
- sudoers syntax check through visudo -cf before installation;
- tmpfiles syntax and directory creation;
- explicit registry-file requirement for initialization;
- refusal to overwrite an existing registry;
- explicit initial profile requirement;
- candidate Caddyfile preserving redirect, compression, HTML cache, and security headers;
- exact /mpulse-config.js handle before fallback proxy;
- caddy validate before installation;
- backup and restoration on failed validation or reload;
- graceful reload command;
- idempotent upgrades;
- no key in command arguments or logs.

**Step 2: Run the focused tests and confirm failure**

~~~bash
python3 -m unittest scripts.tests.test_mpulse_host_setup -v
~~~

Expected: FAIL because the installer does not exist.

**Step 3: Implement installation assets**

The tmpfiles template creates:

~~~text
/var/opt/virtual-space-trotting/mpulse/public
/var/opt/virtual-space-trotting/mpulse/state
/var/opt/virtual-space-trotting/mpulse/state/registry-backups
~~~

The sudoers template grants vst-mpulse-operators permission to run only the fixed privileged-helper path. The helper's own parser remains the primary safety boundary.

Generate a complete candidate Caddyfile from the selected remote receipt and the existing hardened policy. Validate with:

~~~bash
caddy validate --config Caddyfile
~~~

Install and reload only after validation. Restore the previous file if reload or public verification fails.

**Step 4: Add contributor targets**

Add:

~~~text
make remote-install-mpulse-admin MPULSE_REGISTRY_FILE=.vst/mpulse-profiles.json MPULSE_PROFILE=dev-alma
make remote-mpulse-list
make remote-mpulse-current
make remote-mpulse-verify
~~~

The installed host CLI remains the normal team interface after setup.

**Step 5: Run verification**

~~~bash
make test
make test-code-quality
~~~

Expected: PASS.

**Step 6: Commit**

~~~bash
git add Makefile scripts/deploy/mpulse_host_setup.py scripts/deploy/templates scripts/tests/test_mpulse_host_setup.py
git commit -m "Add secure host mPulse profile installation"
~~~

### Task 6: Preserve Host Profile State Across Deployments

**Files:**
- Modify: scripts/deploy/remote_target.py
- Modify: scripts/deploy/linode_one_shot.py
- Modify: scripts/tests/test_remote_target.py
- Modify: scripts/tests/test_linode_one_shot.py
- Modify: .env.example
- Modify: README.md
- Modify: docs/boomerang-instrumentation.md

**Step 1: Write failing deployment-preservation tests**

Require:

- ordinary remote-update never reads or writes /etc/opt or /var/opt;
- remote-update acquires the shared mutation lock before swapping /opt;
- deployment verification checks /mpulse-config.js and the selected script URL when host administration is installed;
- one-shot provisioning can install the host tooling only from an explicit registry file and initial profile;
- BOOMERANG_API_KEY is removed from .env.example and deployment instructions;
- documentation explains host-side registry maintenance.

**Step 2: Run focused tests and confirm failure**

~~~bash
python3 -m unittest scripts.tests.test_remote_target scripts.tests.test_linode_one_shot -v
~~~

Expected: FAIL on lock, verification, and obsolete environment-key assertions.

**Step 3: Implement deployment integration**

Coordinate the /opt swap with /run/lock/vst-mpulse.lock when present. Never copy registry data into a release directory. Verify external runtime configuration after the service health check.

**Step 4: Update operational documentation**

Document:

- individual operator accounts and group membership;
- registry edit/list/switch/current/verify/history/rollback;
- real registry exclusion from Git;
- profile backup behavior;
- initial setup and ordinary deployment behavior;
- emergency rollback.

**Step 5: Run full verification**

~~~bash
make test-code-quality
make test
make build
git diff --check
~~~

Expected: PASS.

**Step 6: Commit**

~~~bash
git add .env.example README.md docs scripts/deploy scripts/tests
git commit -m "Preserve host mPulse profiles across deployments"
~~~

### Task 7: Record The Deployment Decision

**Files:**
- Create: docs/adr/0001-host-managed-mpulse-profiles.md
- Modify: docs/adr/README.md

**Step 1: Write the ADR**

Record:

- build-time profile selection being replaced;
- host registry and generated same-origin script;
- why the real registry is excluded from the public repository;
- why no web UI, Jenkins dependency, or root editor is used;
- Caddy, filesystem, sudo, audit, and rollback consequences;
- the requirement for individual accounts to obtain person-level audit attribution.

**Step 2: Verify documentation**

~~~bash
git diff --check
test -f docs/adr/0001-host-managed-mpulse-profiles.md
rg -n "host-managed mPulse|vst-mpulse|/etc/opt|/var/opt" docs README.md
~~~

Expected: all references exist and no whitespace errors are reported.

**Step 3: Commit**

~~~bash
git add docs/adr
git commit -m "Document host-managed mPulse profile decision"
~~~

### Task 8: Roll Out To The Existing Linode

**Files:**
- Create locally only: .vst/mpulse-profiles.json
- Modify remotely: /etc/opt/virtual-space-trotting/mpulse-profiles.json
- Modify remotely: /var/opt/virtual-space-trotting/mpulse/
- Modify remotely: /etc/caddy/Caddyfile
- Install remotely: /usr/local/bin/vst-mpulse
- Install remotely: /usr/local/lib/virtual-space-trotting/vst-mpulse-admin

**Step 1: Create the gitignored initial registry**

Create .vst/mpulse-profiles.json with mode 0600. Name the current endpoint/key pair dev-alma. Read the key from existing local deployment state; never print it and never stage the file.

**Step 2: Capture pre-change receipts**

Run:

~~~bash
make remote-status
curl -fsS https://172.239.117.12.sslip.io/health
curl -fsS https://172.239.117.12.sslip.io/ > /tmp/vst-before-profile-switching.html
~~~

Record the current commit, service state, Caddyfile backup checksum, public key marker, and Boomerang script response.

**Step 3: Install host administration before changing the application**

~~~bash
make remote-install-mpulse-admin \
  MPULSE_REGISTRY_FILE=.vst/mpulse-profiles.json \
  MPULSE_PROFILE=dev-alma
~~~

Expected: host CLI installed, dev-alma active, Caddy valid and reloaded, old application still healthy.

**Step 4: Verify host configuration independently**

~~~bash
make remote-mpulse-list
make remote-mpulse-current
make remote-mpulse-verify
curl -fsSI https://172.239.117.12.sslip.io/mpulse-config.js
~~~

Expected: dev-alma is active and Cache-Control is no-store.

**Step 5: Push main and deploy the tenant-neutral application**

~~~bash
git push origin main
make remote-update
~~~

Expected: the new application reads /mpulse-config.js while the active tenant remains dev-alma.

**Step 6: Exercise safe operations**

Run an idempotent switch to dev-alma, verify history, verify rollback reports no older distinct profile when appropriate, and confirm invalid-profile switching fails without changing the generated configuration checksum.

Do not add a fabricated second production profile. Full cross-profile switching remains covered by automated tests until an authorised real profile is supplied.

**Step 7: Run final live verification**

Verify:

- site and /health return 200 over HTTPS;
- Caddy, Spin, UFW, Fail2ban, and systemd state remain healthy;
- /mpulse-config.js is no-store and contains dev-alma;
- composed Boomerang script returns JavaScript;
- first-input and unload code remain in the served client bundle;
- repository and origin/main contain no real registry;
- make remote-update preserves the active state.

**Step 8: Commit any rollout documentation receipts**

Commit only non-sensitive documentation changes. Never stage .vst/mpulse-profiles.json or host registry content.

### Task 9: Final Verification

**Step 1: Run all local gates from a clean worktree**

~~~bash
make test-code-quality
make test
make build
git diff --check
git status --short --branch
~~~

Expected: all gates pass and main contains only intentional commits.

**Step 2: Confirm Git and deployment state**

~~~bash
git rev-parse HEAD
git rev-parse origin/main
make remote-status
make remote-mpulse-current
make remote-mpulse-verify
~~~

Expected: HEAD, origin/main, and the remote deployment receipt identify the intended release; dev-alma remains active unless the user explicitly selected another real profile.
