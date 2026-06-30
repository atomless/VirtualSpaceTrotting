# Boomerang Instrumentation

## Purpose

This note records the mPulse Boomerang capabilities used by VirtualSpaceTrotting, the beacons the site can emit, and the extensions that remain possible. It is intentionally limited to measurements relevant to this static multi-page site.

The Boomerang build is selected by the active host-managed mPulse profile, which pairs a script base URL with its API key. Its plugin set can change independently of this repository. The site therefore prefers official plugins when present and installs only focused fallbacks for required behavior.

## Plugin Inventory

### Page-Load Enrichment

As verified on 2026-06-30, the current tenant-delivered build supplies these relevant plugins. Treat this as a deployment snapshot rather than a permanent application guarantee.

| Plugin | Data added to beacons |
| --- | --- |
| `RT` | Navigation start, end, session, and round-trip timing context. |
| `NavigationTiming` | DNS, connection, TLS, request, response, DOM, and load timings exposed by the browser. |
| `PaintTiming` | Paint metrics such as FP, FCP, and LCP when supported. |
| `ResourceTiming` | Resource timing data used to describe the page's asset waterfall. |
| `Memory` | Supported browser memory, storage, and DOM measurements. |
| `EventTiming` | First-input and interaction timing, including FID and INP when available. |
| `PageParams` | Custom variables, dimensions, metrics, timers, and custom-beacon APIs. |
| `Akamai` | Akamai-specific delivery and mPulse integration metadata. |
| `ConfigOverride` | Applies tenant-delivered Boomerang configuration. |
| `LOGN` | Records loader and configuration diagnostics. |

Plugin presence does not mean every optional field is populated. Browser support, tenant configuration, page activity, and any site-defined variables determine which values appear on a particular beacon.

### Additional-Beacon Plugins And Fallbacks

| Capability | Current tenant | Site handling |
| --- | --- | --- |
| `AutoXHR` | Present | The official plugin takes precedence. If absent, the site observes Fetch and XHR batches and calls `BOOMR.responseEnd()` only when the request causes a relevant DOM mutation. Collector and mPulse requests are excluded. |
| `Errors` | Present | The official plugin takes precedence. If absent, the site reports uncaught errors, unhandled rejections, failed requests, `console.error`, and browser reports through `BOOMR.addError()` and `BOOMR.sendBeacon()`. Distinct errors are capped at ten and batched at most once per second. |
| `BFCache` | Present | The official plugin takes precedence. If absent, a persisted `pageshow` event produces a `bfcache` response beacon. |
| `CWV`-style unload | No named plugin | Site code sends available CLS, FID, and INP data through `BOOMR.sendBeaconData()` on a non-persisted `pagehide`. |
| First input | No named plugin | Site code sends one custom beacon through `BOOMR.sendAll()` after the page-load beacon has completed. |

The head bootstrap captures the first input and up to ten errors before the main application initializes. This queue prevents early events from being lost, but it is not an implementation of Boomerang's `Early` plugin and does not send provisional pre-onload beacons.

## Beacon Inventory

| Beacon | Trigger | Principal contents |
| --- | --- | --- |
| Page load | A full document load | Standard mPulse page timing enriched by the available page-load plugins above. |
| First input | The first supported user input, after page-load beacon completion | `FirstInputAll` timer and `c.ttfi`. Emitted at most once per document. |
| XHR | A consequential Fetch or XHR batch | Request URL, request type, request count, status, and request timing. Background requests without a relevant DOM change do not emit this fallback beacon. |
| Error | Post-load browser, promise, request, console, or Reporting API error | Normalized error message and source. Arbitrary objects and page data are not serialized. |
| Custom unload | A non-BFCache page exit when at least one metric is available | `http.initiator=api_custom_unload` plus available `c.cls`, `et.fid`, and `et.inp`. |
| BFCache | Restoration from the browser's back-forward cache | `http.initiator=bfcache`, restored URL, timestamp, and persisted state. |

All site-added instrumentation remains inert when `/mpulse-config.js` contains no valid active profile.

## Relevant Extensions

These are possible extensions, not current behavior:

1. **Page taxonomy through `PageParams`.** Add stable page groups and dimensions for home, map index, map detail, category, pagination, and editorial pages. This is the clearest remaining enrichment because it would make existing beacons easier to compare without creating extra traffic.
2. **Explicit multi-page navigation.** Ensure internal links perform full document navigation so each route reliably produces a normal page-load beacon. Prerendering alone does not guarantee this when SvelteKit's client router is enabled.
3. **`Continuity`.** Enable only if the test programme needs continuity-specific measurements beyond the current EventTiming, FID, INP, and unload data. Configuration for a missing plugin does not load that plugin.
4. **`Early`.** Enable only when provisional pre-onload beacons are needed to diagnose pages that may fail or stall before normal page-load collection.
5. **Async interaction coverage.** Revisit AutoXHR settings and action-level verification if the site later gains genuine user-triggered Fetch or XHR workflows.

## Deliberate Exclusions

- `SPA`, `History`, and framework adapters are not part of the intended instrumentation model because VirtualSpaceTrotting is a static multi-page site.
- `TPAnalytics` is not relevant while the site has no third-party analytics provider whose identifiers need correlation.
- No artificial requests or interactions should be introduced solely to manufacture additional beacons.
- The site never posts directly to the collector; custom behavior uses public `BOOMR` APIs.

After switching a profile or changing tenant configuration, run `vst-mpulse verify`, verify the delivered plugin set, and inspect representative page-load, interaction, error, unload, and BFCache beacons. Do not assume that a plugin available to one tenant is available to another.
