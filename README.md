# VirtualSpaceTrotting

VirtualSpaceTrotting is a pre-launch static site for touring imaginary, AI-generated places that resemble satellite imagery but do not exist.

The public browsing structure is inspired by [Virtual Globetrotting](https://virtualglobetrotting.com/): map/category browsing, popular and latest lists, location detail pages, and lightweight editorial context. The crucial difference is that every location, image, and place description in this project must be fictional and clearly treated as generated content.

## Current Status

The repository has been initialized with:

- project governance copied and adapted from Shuma Gorath,
- lean Linode setup and remote-update helper patterns,
- test coverage for the helper layer,
- Makefile targets for setup, verification, and remote operations.

The SvelteKit, Spin, Rust runtime, and generated imagery corpus are intentionally not scaffolded in this initial slice.

## Canonical Commands

```bash
make setup
make test
make test-code-quality
```

Linode host setup and day-2 operations:

```bash
make prepare-linode-host PREPARE_LINODE_ARGS="--remote-name prod --region us-east"
make remote-use REMOTE=prod
make remote-status
make remote-update
```

`make remote-update` ships committed `HEAD`; uncommitted changes are not included in the release bundle.

## Next Planning Questions

Before building the public site, capture a short design plan covering:

- route map and component boundaries,
- launch content target and category distribution,
- generated image style and provenance metadata,
- static SvelteKit output served by Spin/Rust,
- Linode first deploy flow.
