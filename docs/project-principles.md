# VirtualSpaceTrotting Project Principles

## Purpose

VirtualSpaceTrotting exists to make browsing imaginary locations feel as rich and curious as browsing real satellite curiosities, while being truthful that the places and imagery are generated fiction.

## Core Goals

1. Build a fast static SvelteKit site served by Spin with a small Rust runtime.
2. Preserve the broad browsing grammar of Virtual Globetrotting without copying its content or assets.
3. Populate launch with a planned, coherent corpus of generated locations.
4. Keep generated imagery provenance clear and auditable.
5. Keep setup, test, build, and deploy paths simple and Makefile-driven.
6. Keep architecture modular and data-driven.
7. Keep performance, accessibility, and maintainability first-class.
8. Keep deployment repeatable on Linode.

## Principles

### P1. Truthful Fiction

- Generated places must be presented as imaginary.
- Generated satellite-style images must not be described as real map tiles or real satellite data.
- Location descriptions must not imply real-world visitation, ownership, or sensitive-site discovery.

### P2. Data-Driven Static Site

- Location pages, category pages, popular/latest lists, and metadata should be generated from structured data.
- Repeated UI must live in reusable Svelte components.
- Content schema changes should be planned and tested.

### P3. Clean Runtime Boundary

- SvelteKit owns static page generation.
- Rust/Spin owns serving and any runtime HTTP behavior.
- Python and shell helpers are allowed for setup, deployment, tests, and asset/content generation only.

### P4. Content Corpus Quality

- Launch corpus size must be planned before bulk image generation.
- Categories should be broad enough to browse and dense enough not to feel empty.
- Each generated asset should have provenance metadata.
- Prompt families should be reusable and documented.

### P5. Verification

- Behavior changes require tests.
- Rendered UI changes require browser verification once the frontend exists.
- Deployment helper changes require focused helper tests.
- Completion claims require fresh verification evidence.

### P6. Operational Simplicity

- `Makefile` targets are the canonical setup/build/test/deploy interface.
- Linode host receipts live under `.vst/`.
- Secrets live in `.env.local`.
- Remote updates ship committed `HEAD`.

### P7. Pre-Launch Change Discipline

- Prefer clean designs over compatibility shims.
- Avoid technical debt and duplicate bootstrap paths.
- Record significant decisions in ADRs.

## Decision Rubric

For significant feature work, document:

1. User experience and route/component impact.
2. Content schema and generation impact.
3. Fiction/provenance implications.
4. Performance and accessibility impact.
5. Security and operational impact.
6. Verification path.
7. Rollback path for deployment changes.
