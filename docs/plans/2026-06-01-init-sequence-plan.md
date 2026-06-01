# 2026-06-01 Init Sequence Plan

## Scope

Initialize the empty `atomless/VirtualSpaceTrotting` repository with project governance and lean deployment helper patterns focused only on this static generated-location site.

## Assumptions

- The product is pre-launch.
- The first slice should not scaffold the SvelteKit/Spin app yet.
- Linode setup/update helpers should establish reusable receipts and day-2 operation patterns, not pretend a deployable app exists before the runtime scaffold lands.

## Acceptance Criteria

1. Repository is attached to `atomless/VirtualSpaceTrotting`.
   - Proof: `git remote -v`.
2. Project guidance exists and is specific to imaginary generated locations.
   - Proof: `AGENTS.md`, `CONTRIBUTING.md`, and `docs/project-principles.md`.
3. Linode helper patterns are focused on this static site and avoid unrelated source-project behavior.
   - Proof: `scripts/deploy/*`, `skills/*linode*/SKILL.md`.
4. Helper behavior has focused tests.
   - Proof: `make test`.
5. Helper code compiles.
   - Proof: `make test-code-quality`.

## Out Of Scope

- SvelteKit app scaffold.
- Spin/Rust runtime scaffold.
- Generated imagery.
- Launch corpus planning beyond noting it as the next required planning step.
