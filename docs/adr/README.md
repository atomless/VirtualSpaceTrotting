# Architecture Decision Records

Use ADRs to capture significant architectural or cross-cutting decisions.

## Records

- [ADR 0001: Host-Managed mPulse Profiles](0001-host-managed-mpulse-profiles.md)

## When An ADR Is Required

Create an ADR when a change:

- Introduces or changes route architecture.
- Changes the content data schema or generated asset manifest.
- Changes the image/content generation pipeline.
- Adds or removes a significant dependency.
- Changes Spin/Rust deployment or hosting assumptions.
- Changes security posture or trust boundaries.
- Introduces a meaningful performance, accessibility, or SEO trade-off.

## Naming And Location

- Location: `docs/adr/`
- File format: `NNNN-short-title.md`
- Start from `docs/adr/0000-template.md`.

## Status Lifecycle

- `Proposed`
- `Accepted`
- `Superseded`
- `Deprecated`

If superseded, link the replacing ADR.
