# 2026-06-01 Init Sequence Plan

## Scope

Initialize the empty `atomless/VirtualSpaceTrotting` repository with reusable project governance and lean helper patterns from Shuma Gorath, stripped of bot-defence, gateway, telemetry, and adversary-simulation specifics.

## Assumptions

- The product is pre-launch.
- The first slice should not scaffold the SvelteKit/Spin app yet.
- Linode setup/update helpers should establish reusable receipts and day-2 operation patterns, not pretend a deployable app exists before the runtime scaffold lands.

## Acceptance Criteria

1. Repository is attached to `atomless/VirtualSpaceTrotting`.
   - Proof: `git remote -v`.
2. Project guidance exists and is specific to imaginary generated locations.
   - Proof: `AGENTS.md`, `CONTRIBUTING.md`, and `docs/project-principles.md`.
3. Linode helper patterns are renamed and stripped of Shuma-specific gateway/bot-defence behavior.
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
