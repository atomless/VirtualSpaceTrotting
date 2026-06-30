# Boomerang Non-Page-Load Triggers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add plugin-aware non-page-load Boomerang instrumentation matching the active reference-site triggers.

**Architecture:** A browser-only module owns fallback instrumentation and uses public Boomerang APIs. A minimal head bootstrap captures pre-hydration input and errors; the root Svelte layout initializes the module after hydration.

**Tech Stack:** SvelteKit 2, browser JavaScript, Node's built-in test runner, Python contract tests, Akamai mPulse Boomerang.

---

### Task 1: Add The Site JavaScript Test Gate

**Files:**
- Modify: `Makefile`
- Modify: `site/package.json`
- Create: `site/tests/boomerang-instrumentation.test.mjs`

**Steps:**

1. Add `test-site` to `make test` and map it to `pnpm --dir site test`.
2. Add a Node `--test` package script.
3. Write failing tests for request batching, exclusions, errors, first input, unload, and plugin detection.
4. Run `make test-site` and confirm the tests fail because the module is missing.

### Task 2: Implement Plugin-Aware Instrumentation

**Files:**
- Create: `site/src/lib/boomerang-instrumentation.js`
- Test: `site/tests/boomerang-instrumentation.test.mjs`

**Steps:**

1. Implement pure helpers for error normalization, URL exclusion, plugin detection, request batching, and unload data.
2. Implement `installBoomerangInstrumentation(window)` with cleanup.
3. Use `BOOMR.responseEnd`, `BOOMR.addError`, `BOOMR.sendBeacon`, `BOOMR.sendAll`, and `BOOMR.sendBeaconData` for their documented purposes.
4. Run `make test-site` until all focused tests pass.

### Task 3: Capture Early Events And Initialize The Module

**Files:**
- Modify: `site/src/app.html`
- Modify: `site/src/routes/+layout.svelte`
- Modify: `scripts/tests/test_static_output_contract.py`

**Steps:**

1. Add failing static-contract assertions for the head event queue, loader-ready event, and layout initializer.
2. Run the focused Python contract test and confirm the expected failure.
3. Add the minimal head bootstrap and loader-ready dispatch.
4. Initialize the module through Svelte's `onMount` lifecycle.
5. Run focused JavaScript and Python tests.

### Task 4: Document Operations And Verify

**Files:**
- Modify: `README.md`

**Steps:**

1. Document which triggers are supplied by source and which defer to official plugins.
2. Run `make test-code-quality`.
3. Run `make test`.
4. Run `make build`.
5. Inspect the generated HTML to confirm an empty key remains inert and a populated key installs instrumentation.
6. Review `git diff` for unrelated changes before reporting completion.
