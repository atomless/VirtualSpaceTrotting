# Completed TODO History

## 2026-06-01 - Source-Project Residue Cleanup

Type: cleanup and review.

Removed unused deployment network-filter scaffolding and source-project vocabulary from the initialized helper/docs layer so the repository is focused on the static generated-location site.

Evidence:

- `make test`
- `make test-code-quality`
- residue scan with `rg` for source-project-specific terms

## 2026-06-01 - Initial Governance And Helper Migration

Type: setup and policy.

Delivered the adapted AGENTS/CONTRIBUTING guidance, project principles, ADR scaffolding, Make targets, Linode host receipt helper, generic remote receipt/update helper, and focused tests for the helper layer.

Evidence:

- `make test`
- `make test-code-quality`
