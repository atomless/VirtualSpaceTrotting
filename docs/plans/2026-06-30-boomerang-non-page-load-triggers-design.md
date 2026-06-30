# Boomerang Non-Page-Load Triggers Design

## Scope

Replicate the active non-page-load instrumentation observed on VirtualGlobetrotting while continuing to use the Boomerang build selected by the configured mPulse API key. Official Boomerang plugins take precedence; VirtualSpaceTrotting supplies focused fallbacks only when the tenant-served build omits the corresponding plugin.

## Assumptions

- The tenant-served plugin set is controlled by mPulse and may change independently of this repository.
- Fallbacks must detect official plugins and avoid duplicate instrumentation across tenant configurations.
- The mPulse API key remains optional. No key means no instrumentation, listeners, wrappers, or beacon attempts.
- This is testing instrumentation, not application functionality. It must not alter navigation, request results, error propagation, or rendering.

## Architecture

Add one browser-only instrumentation module initialized from the root Svelte layout. A small head bootstrap captures the first input and early errors before hydration, then the module takes ownership once Boomerang loads.

The module uses public Boomerang APIs rather than posting directly to a collector:

- `BOOMR.sendAll()` for the first-input custom beacon.
- `BOOMR.responseEnd()` for fallback XHR, Fetch, and BFCache beacons.
- `BOOMR.addError()` plus `BOOMR.sendBeacon()` for fallback error reporting.
- `BOOMR.sendBeaconData()` for the unload beacon, matching the reference site's unload-safe pattern.

Concurrent XHR and Fetch requests form one batch. A batch is reported only when it causes a meaningful DOM mutation, preserving AutoXHR's distinction between user-visible work and background traffic. mPulse loader, configuration, collector, and Akamai mapping endpoints are always excluded.

## Trigger Behaviour

1. First input after the page-load beacon sends one custom beacon containing first-input delay and time-to-first-interaction data.
2. Consequential XHR or Fetch batches send one `xhr` response beacon. Background requests without DOM changes do not.
3. When the official Errors plugin is absent, runtime errors, rejected promises, failed requests, `console.error`, and Reporting API warnings are batched at most once per second, with ten distinct errors retained.
4. Page unload sends accumulated CLS, FID, and INP when available. BFCache suspension does not count as unload.
5. When the official BFCache plugin is absent, a persisted `pageshow` event sends a `bfcache` response beacon.

## Safety And Performance

- Error text is converted to a string and truncated; arbitrary objects and page data are not serialized.
- Wrapped Fetch and XHR methods preserve return values, callbacks, exceptions, and promise rejection.
- Fallbacks are installed once and expose cleanup that restores wrapped browser APIs.
- Performance observers and request mutation observers are disconnected after use.
- No dependency is added.

## Acceptance Criteria

1. Without a valid host-provided mPulse profile, the generated page remains inert.
2. First input emits at most one custom beacon and never duplicates pre-page-load FID collection.
3. Concurrent consequential requests emit one XHR beacon; background and excluded requests emit none.
4. Errors are deduplicated, capped at ten, throttled to one send per second, and still propagate normally.
5. Unload sends available CLS/FID/INP exactly once and ignores BFCache suspension.
6. BFCache fallback runs only when the official plugin is absent.
7. Official `AutoXHR`, `Errors`, and `BFCache` plugins disable their corresponding fallbacks.
8. `make test-code-quality`, `make test`, and `make build` pass.

## Rollback

Remove the root-layout initializer, the instrumentation module, and the head bootstrap. The existing non-blocking Boomerang loader remains independently functional.
