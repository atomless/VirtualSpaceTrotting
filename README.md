# VirtualSpaceTrotting

VirtualSpaceTrotting is a pre-launch static site for touring imaginary, AI-generated places that resemble satellite imagery but do not exist.

The public browsing structure is inspired by [Virtual Globetrotting](https://virtualglobetrotting.com/): map/category browsing, popular and latest lists, location detail pages, and lightweight editorial context. The crucial difference is that every location, image, and place description in this project must be fictional and clearly treated as generated content.

## Setup And Deploy

The intended setup path is deliberately small:

1. Clone the repository.

   ```bash
   git clone https://github.com/atomless/VirtualSpaceTrotting.git
   cd VirtualSpaceTrotting
   ```

2. Add a Linode access token to the local environment file.

   ```bash
   printf 'LINODE_TOKEN=%s\n' 'paste-your-linode-token-here' > .env.local
   chmod 600 .env.local
   ```

   `.env.local` is gitignored. Do not commit the token.

3. Tell your coding agent to set up the remote and deploy the site.

   Use this exact instruction:

   > Run the project setup, create or update the Linode remote named `prod`, deploy the current committed `main` branch, and verify the public `/health` endpoint and a paginated maps page.

   The agent should run the project helper:

   ```bash
   make deploy-linode-one-shot DEPLOY_LINODE_ARGS="--remote-name prod --region gb-lon --profile small"
   ```

   After the first deploy, updates use:

   ```bash
   make remote-update
   ```

Release bundles are built from committed `HEAD`. Commit and push the work you want deployed before asking the agent to deploy or update the remote.

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

The first-run Linode helper needs `LINODE_TOKEN` in `.env.local` or via `DEPLOY_LINODE_ARGS="--linode-token ..."` and creates or attaches a host. By default it serves the Spin app publicly on port `3000`; pass `--public-base-url` when pointing a domain or reverse proxy at the service.
