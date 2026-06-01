# Contributing To VirtualSpaceTrotting

## Ground Rules

- Follow `docs/project-principles.md`.
- Keep changes small, reviewable, and test-backed.
- Avoid new dependencies unless clearly justified.
- Use SvelteKit for the static frontend and Rust/Spin for serving/runtime behavior.
- Keep Python and shell scripts limited to setup, tests, content generation, deployment, and maintenance.
- Treat the product as pre-launch unless the user says otherwise.

## Required For Every Change

1. Add or update tests where behavior changes.
2. Run verification through `Makefile` targets:
   - `make test-code-quality` for non-doc helper/code changes.
   - `make test` for the current umbrella suite.
   - `make build` after the application scaffold exists.
   - `make setup`, `make prepare-linode-host`, or `make remote-*` when setup/deploy behavior changes.
3. Update docs for behavior, configuration, content generation, or operations changes.
4. Note security, provenance, performance, accessibility, and operational implications.
5. Keep generated-location content transparent: fictional places, fictional imagery, no copied real-world map tiles.

## Acceptance Criteria And Definition Of Done

For any non-trivial change, define success before implementation begins.

- Acceptance criteria must be pass/fail outcomes.
- Each criterion should name the proof surface: tests, rendered page, generated asset manifest, deployment receipt, or documentation contract.
- Completion notes must cite the verification actually run.
- Planning-only or documentation-only work must be described as such.
- If required proof is missing, keep the item open.

## Commit And Push Discipline

- Prefer atomic commits: one logical change per commit.
- Do not mix unrelated refactors with feature work.
- Run relevant `make` verification before each commit.
- Push after each validated atomic commit unless batching is explicitly requested.

## Content Corpus Discipline

- Plan the launch corpus size before bulk generation.
- Keep a data manifest for each generated location and image.
- Prefer reusable prompt families over one-off prompts.
- Record generation date, prompt family, category, fictional-region tags, and any manual curation notes.
- Do not represent AI-generated imagery as real satellite data.

## Deployment Helpers

- Local deployment state is stored in `.vst/`.
- Local secrets are stored in `.env.local`.
- Use `make prepare-linode-host` to create or attach a Linode host receipt.
- Use `make remote-use`, `make remote-status`, `make remote-logs`, `make remote-start`, `make remote-stop`, `make remote-open-site`, and `make remote-update` for day-2 operations.
- `make remote-update` deploys committed `HEAD`, not uncommitted local edits.

## When An ADR Is Required

Create or update an ADR in `docs/adr/` when a change affects:

- route architecture or data schema,
- content-generation pipeline,
- generated asset storage,
- deployment model,
- runtime trust boundaries,
- major dependencies,
- significant performance, accessibility, or SEO trade-offs.
