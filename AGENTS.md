# AGENTS.md

This file provides instructions for coding agents working in this repository.

## Scope And Precedence

1. Follow explicit user instructions first.
2. Follow this file next.
3. Follow canonical project policy docs:
   - `docs/project-principles.md`
   - `CONTRIBUTING.md`
   - `docs/adr/README.md`
4. If instructions conflict, preserve correctness, maintainability, security, and clear project intent.

## Product Direction

VirtualSpaceTrotting is a pre-launch static site inspired by the layout and browsing structure of `virtualglobetrotting.com`, but all locations and imagery are imaginary. The site must never present generated places as real-world discoveries.

Core goals:

- Build a static SvelteKit experience served by Spin with a small Rust runtime.
- Keep the site modular: content data, generated imagery metadata, route rendering, and deployment helpers should stay separate.
- Populate launch with enough generated locations to make browsing feel alive; decide the launch content target in a documented plan before bulk generation.
- Preserve the browsing feel of map/location/category/timeline pages while avoiding copied content, copied source assets, or user-confusing claims.
- Keep deployment simple for a Linode-hosted systemd service.

## Required Workflow

Planning-first workflow is mandatory for non-trivial work unless the user explicitly asks for a different sequence.

1. Read relevant docs and touched modules before editing.
2. For feature work, ask whether to research current best practice and state of the art before implementation.
3. Define assumptions and acceptance criteria before implementation begins.
4. Keep implementation in small, reviewable slices.
5. Add or update tests where behavior changes.
6. Update docs for behavior, content-generation, setup, deployment, or operational changes.
7. Use `Makefile` targets as the contributor interface:
   - `make setup` for local gitignored state.
   - `make test-code-quality` as the static helper-code gate for non-doc changes.
   - `make test` for the current umbrella verification target.
   - `make build` once the app scaffold exists.
   - `make prepare-linode-host` and `make remote-*` for Linode host receipts and day-2 operations.
8. Treat direct tool invocations as implementation details behind `make` unless no Make target exists yet.
9. If a needed workflow is missing from `Makefile`, add or update the Make target first.
10. Before reporting completion, run fresh verification and state what was run.
11. Commit and push atomic validated slices when the user has asked for repo setup or delivery into GitHub.

Documentation-only changes do not require runtime tests, but the response must say verification was intentionally limited.

## Architecture And Boundaries

- Runtime request-path logic belongs in Rust once the Spin scaffold exists.
- SvelteKit should statically prerender the public site; avoid dynamic server features unless a plan justifies them.
- Content should be data-driven. Avoid hard-coding repeated location cards into page components.
- Generated media must carry provenance metadata: prompt family, generator/tool, date, intended category, and fictional status.
- Keep image assets inspectable and versionable until the corpus becomes too large; document any later asset-storage change.
- Use ADRs for deployment model changes, content-generation pipeline choices, data schema changes, or major route architecture decisions.
- Treat this project as pre-launch by default; do not add backward-compatibility shims unless the user explicitly asks for them.

## Content And Safety

- Never imply generated satellite imagery depicts a real location.
- Do not use real private homes, sensitive facilities, or copied map tiles as source material for fictional entries.
- Avoid claims that could confuse a visitor into searching for or visiting a non-existent place.
- Keep fictional coordinates clearly synthetic or internally scoped unless a plan explicitly defines public fake-coordinate semantics.
- Make generated categories broad enough for browsing but not so many that the launch corpus feels thin.

## UI And Frontend

- Follow the existing site structure closely enough for recognisable browsing: header navigation, map/category browsing, popular/latest lists, location detail pages, blog/news-style entries if needed, and sidebar metadata.
- Do not clone visual assets or copyrighted text.
- Keep pages fast, accessible, and responsive.
- Use reusable Svelte components for repeated cards, lists, nav, and metadata.
- Validate rendered pages with browser screenshots once the app exists.

## Deployment And Operations

- Durable local operator state belongs in `.vst/`.
- Local secrets belong in `.env.local`, which must stay gitignored.
- Linode host setup writes `.vst/linode-host-setup.json` and `.vst/remotes/<name>.json`.
- `make remote-update` ships committed `HEAD`; a dirty worktree is not deployed.
- Remote service defaults:
  - user: `vst`
  - app dir: `/opt/virtual-space-trotting`
  - systemd service: `virtual-space-trotting`
  - health path: `/health`

## Pull Request Expectations

PR descriptions should include:

- what changed,
- why it changed,
- verification run,
- content/provenance implications,
- security or operational implications,
- rollback notes for deployment changes.

## Question Handling

If a question pertains to this codebase, read the code before answering. If a question pertains to broader software engineering principles, best practices, or technical specifics, research authoritative sources and cite them.
