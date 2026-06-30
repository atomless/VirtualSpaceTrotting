import assert from 'node:assert/strict';
import test from 'node:test';

let instrumentation = {};
try {
  instrumentation = await import('../src/lib/boomerang-instrumentation.js');
} catch (error) {
  if (error?.code !== 'ERR_MODULE_NOT_FOUND') throw error;
}

const {
  buildUnloadBeacon,
  createErrorReporter,
  createFirstInputSender,
  createRequestBatcher,
  hasPlugin,
  installBoomerangInstrumentation,
  normalizeError,
  shouldExcludeRequest
} = instrumentation;

test('exports the instrumentation helpers', () => {
  assert.equal(typeof buildUnloadBeacon, 'function');
  assert.equal(typeof createErrorReporter, 'function');
  assert.equal(typeof createFirstInputSender, 'function');
  assert.equal(typeof createRequestBatcher, 'function');
  assert.equal(typeof hasPlugin, 'function');
  assert.equal(typeof installBoomerangInstrumentation, 'function');
  assert.equal(typeof normalizeError, 'function');
  assert.equal(typeof shouldExcludeRequest, 'function');
});

test('detects only initialized official plugins', () => {
  assert.equal(hasPlugin({ plugins: { AutoXHR: {} } }, 'AutoXHR'), true);
  assert.equal(hasPlugin({ plugins: {} }, 'AutoXHR'), false);
  assert.equal(hasPlugin(undefined, 'AutoXHR'), false);
});

test('excludes mPulse traffic and configured URL fragments', () => {
  const boomr = { xhr_excludes: { 'fast-stats.io': true, '/quiet/': true } };

  assert.equal(shouldExcludeRequest('https://collector.akstat.io/', boomr), true);
  assert.equal(shouldExcludeRequest('https://rum.example.soasta.com/api/config.json', boomr), true);
  assert.equal(shouldExcludeRequest('https://fast-stats.io/collect', boomr), true);
  assert.equal(shouldExcludeRequest('https://example.com/quiet/poll', boomr), true);
  assert.equal(shouldExcludeRequest('https://example.com/api/maps', boomr), false);
});

test('groups concurrent consequential requests into one response beacon', () => {
  const reports = [];
  let scheduled;
  const batcher = createRequestBatcher({
    now: (() => {
      let now = 1000;
      return () => (now += 10);
    })(),
    report: (report) => reports.push(report),
    schedule: (callback) => {
      scheduled = callback;
      return 1;
    },
    cancel: () => {},
    excluded: () => false
  });

  const first = batcher.begin('https://example.com/api/maps', 'fetch');
  const second = batcher.begin('https://example.com/api/places', 'xhr');
  batcher.markMutation();
  batcher.finish(first, { status: 200 });
  batcher.finish(second, { status: 200 });
  scheduled();

  assert.equal(reports.length, 1);
  assert.equal(reports[0].url, 'https://example.com/api/maps');
  assert.equal(reports[0].requestCount, 2);
  assert.equal(reports[0].initiator, 'xhr');
});

test('does not report background or excluded requests', () => {
  const reports = [];
  let scheduled;
  const batcher = createRequestBatcher({
    now: () => 1000,
    report: (report) => reports.push(report),
    schedule: (callback) => {
      scheduled = callback;
      return 1;
    },
    cancel: () => {},
    excluded: (url) => url.includes('excluded')
  });

  const background = batcher.begin('https://example.com/api/background', 'fetch');
  batcher.finish(background, { status: 200 });
  scheduled();
  const excluded = batcher.begin('https://example.com/excluded', 'xhr');
  batcher.finish(excluded, { status: 200 });

  assert.deepEqual(reports, []);
});

test('normalizes errors without serializing arbitrary objects', () => {
  assert.equal(normalizeError(new Error('broken')), 'broken');
  assert.equal(normalizeError({ private: 'value' }), '[object Object]');
  assert.equal(normalizeError('x'.repeat(600)).length, 500);
});

test('deduplicates, caps, and batches fallback errors', () => {
  const added = [];
  let sends = 0;
  let scheduled;
  const reporter = createErrorReporter({
    boomr: {
      addError: (message, source) => added.push([message, source]),
      sendBeacon: () => {
        sends += 1;
      }
    },
    limit: 2,
    schedule: (callback) => {
      scheduled = callback;
      return 1;
    },
    cancel: () => {}
  });

  reporter.report('one', 'window.error');
  reporter.report('one', 'window.error');
  reporter.report('two', 'promise');
  reporter.report('three', 'console');
  scheduled();

  assert.deepEqual(added, [
    ['one', 'window.error'],
    ['two', 'promise']
  ]);
  assert.equal(sends, 1);
});

test('sends first input once and only after the page-load beacon', () => {
  const payloads = [];
  let pageLoadSent = false;
  const boomr = {
    hasSentPageLoadBeacon: () => pageLoadSent,
    hrNow: () => 321,
    sendAll: (payload) => payloads.push(payload)
  };
  const sendFirstInput = createFirstInputSender(boomr);

  assert.equal(sendFirstInput({ delay: 12 }), false);
  pageLoadSent = true;
  assert.equal(sendFirstInput({ delay: 14 }), true);
  assert.equal(sendFirstInput({ delay: 18 }), false);
  assert.deepEqual(payloads, [
    { timers: { FirstInputAll: 14 }, vars: { 'c.ttfi': 321 } }
  ]);
});

test('builds an unload beacon with session and interaction data', () => {
  const boomr = {
    version: '1.2.3',
    pageId: 'page1234',
    beaconsSent: 2,
    now: () => 5000,
    getVar: (name) => ({ 'h.key': 'key', 'h.d': 'example.com', 'h.cr': 'crumb', 'h.t': 100 }[name]),
    session: { ID: 'session', start: 4000, length: 2, domain: 'example.com' }
  };

  const beacon = buildUnloadBeacon(boomr, { cls: 0.12, fid: 7, inp: 55 });

  assert.equal(beacon['http.initiator'], 'api_custom_unload');
  assert.equal(beacon['c.cls'], 0.12);
  assert.equal(beacon['et.fid'], 7);
  assert.equal(beacon['et.inp'], 55);
  assert.equal(beacon['h.key'], 'key');
  assert.equal(beacon['rt.si'].startsWith('session-'), true);
  assert.equal(beacon.n, 3);
});

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, callback) {
    const callbacks = this.listeners.get(name) || new Set();
    callbacks.add(callback);
    this.listeners.set(name, callbacks);
  }

  removeEventListener(name, callback) {
    this.listeners.get(name)?.delete(callback);
  }

  dispatch(name, event = {}) {
    for (const callback of this.listeners.get(name) || []) callback(event);
  }
}

function createFakeWindow({ plugins = {} } = {}) {
  const events = new FakeEventTarget();
  const boomrEvents = new FakeEventTarget();
  const responses = [];
  const customBeacons = [];
  const errors = [];
  const originalFetch = async () => ({ status: 200 });
  const consoleErrors = [];
  const documentElement = {};

  class FakeMutationObserver {
    static instances = [];

    constructor(callback) {
      this.callback = callback;
      this.disconnected = false;
      FakeMutationObserver.instances.push(this);
    }

    observe() {}

    disconnect() {
      this.disconnected = true;
    }

    trigger(records = [{ type: 'childList' }]) {
      this.callback(records);
    }
  }

  class FakePerformanceObserver {
    constructor(callback) {
      this.callback = callback;
    }

    observe() {}
    disconnect() {}
  }

  class FakeXMLHttpRequest extends FakeEventTarget {
    constructor() {
      super();
      this.status = 200;
    }

    open(method, url) {
      this.method = method;
      this.url = url;
    }

    send() {}
  }

  const boomr = {
    version: '1.2.3',
    plugins,
    pageId: 'page1234',
    beaconsSent: 1,
    session: { ID: 'session', start: 4000, length: 1, domain: 'example.com' },
    xhr_excludes: {},
    now: (() => {
      let now = 5000;
      return () => ++now;
    })(),
    hrNow: () => 300,
    hasSentPageLoadBeacon: () => true,
    getVar: (name) => ({ 'h.key': 'key', 'h.d': 'example.com', 'h.cr': 'crumb', 'h.t': 100 }[name]),
    responseEnd: (...args) => responses.push(args),
    subscribe: (...args) => boomrEvents.addEventListener(...args),
    unsubscribe: (...args) => boomrEvents.removeEventListener(...args),
    sendAll: (payload) => customBeacons.push(payload),
    sendBeaconData: (payload) => customBeacons.push(payload),
    addError: (message, source) => errors.push([message, source]),
    sendBeacon: () => customBeacons.push({ error: true })
  };

  const window = {
    BOOMR: boomr,
    BOOMR_API_key: 'key',
    BOOMR_EARLY_STATE: { errors: [], firstInput: null },
    MutationObserver: FakeMutationObserver,
    PerformanceObserver: FakePerformanceObserver,
    XMLHttpRequest: FakeXMLHttpRequest,
    addEventListener: (...args) => events.addEventListener(...args),
    removeEventListener: (...args) => events.removeEventListener(...args),
    console: { error: (...args) => consoleErrors.push(args) },
    document: { documentElement, location: { href: 'https://example.com/maps/' } },
    fetch: originalFetch,
    location: { href: 'https://example.com/maps/' },
    performance: { now: () => 10 }
  };

  return {
    FakeMutationObserver,
    boomr,
    boomrEvents,
    consoleErrors,
    customBeacons,
    errors,
    events,
    originalFetch,
    responses,
    window
  };
}

test('stays inert without an API key', () => {
  const fixture = createFakeWindow();
  fixture.window.BOOMR_API_key = '';

  const cleanup = installBoomerangInstrumentation(fixture.window);

  assert.equal(fixture.window.fetch, fixture.originalFetch);
  assert.equal(typeof cleanup, 'function');
});

test('prefers official AutoXHR and Errors plugins', () => {
  const fixture = createFakeWindow({ plugins: { AutoXHR: {}, Errors: {}, BFCache: {} } });
  const originalConsoleError = fixture.window.console.error;
  let earlyCaptureStops = 0;
  fixture.window.BOOMR_EARLY_STATE.errors.push({
    message: 'early failure',
    source: 'window.error'
  });
  fixture.window.BOOMR_EARLY_STATE.stopErrorCapture = () => {
    earlyCaptureStops += 1;
  };

  const cleanup = installBoomerangInstrumentation(fixture.window);

  assert.equal(fixture.window.fetch, fixture.originalFetch);
  assert.equal(fixture.window.console.error, originalConsoleError);
  assert.equal(earlyCaptureStops, 1);
  assert.deepEqual(fixture.errors, [['early failure', 'window.error']]);
  assert.equal(fixture.customBeacons.some((beacon) => beacon.error), true);
  cleanup();
});

test('retries an early first input after the page-load beacon', () => {
  const fixture = createFakeWindow();
  let pageLoadSent = false;
  fixture.boomr.hasSentPageLoadBeacon = () => pageLoadSent;
  fixture.window.BOOMR_EARLY_STATE.firstInput = { delay: 11, type: 'click' };

  const cleanup = installBoomerangInstrumentation(fixture.window);
  assert.equal(fixture.customBeacons.length, 0);

  pageLoadSent = true;
  fixture.boomrEvents.dispatch('page_load_beacon');

  assert.deepEqual(fixture.customBeacons, [
    { timers: { FirstInputAll: 11 }, vars: { 'c.ttfi': 300 } }
  ]);
  cleanup();
});

test('fallback Fetch instrumentation reports consequential request batches', async () => {
  const fixture = createFakeWindow();
  const cleanup = installBoomerangInstrumentation(fixture.window, { requestIdleMs: 0 });

  const request = fixture.window.fetch('https://example.com/api/maps');
  fixture.FakeMutationObserver.instances.at(-1).trigger();
  await request;
  await new Promise((resolve) => setTimeout(resolve, 5));

  assert.equal(fixture.responses.length, 1);
  assert.equal(fixture.responses[0][0].initiator, 'xhr');
  assert.equal(fixture.responses[0][0].url, 'https://example.com/api/maps');
  cleanup();
  assert.equal(fixture.window.fetch, fixture.originalFetch);
});

test('fallback error reporting preserves console behavior and batches the report', async () => {
  const fixture = createFakeWindow();
  const cleanup = installBoomerangInstrumentation(fixture.window, { errorIntervalMs: 0 });

  fixture.window.console.error('broken');
  await new Promise((resolve) => setTimeout(resolve, 5));

  assert.deepEqual(fixture.consoleErrors, [['broken']]);
  assert.deepEqual(fixture.errors, [['broken', 'console.error']]);
  assert.equal(fixture.customBeacons.some((beacon) => beacon.error), true);
  cleanup();
});

test('sends unload metrics and ignores BFCache suspension', () => {
  const fixture = createFakeWindow({
    plugins: {
      EventTiming: {
        metrics: {
          firstInputDelay: () => 8,
          interactionToNextPaint: () => 60
        }
      }
    }
  });
  const cleanup = installBoomerangInstrumentation(fixture.window);

  fixture.events.dispatch('pagehide', { persisted: true });
  fixture.events.dispatch('pagehide', { persisted: false });

  const unloads = fixture.customBeacons.filter(
    (beacon) => beacon['http.initiator'] === 'api_custom_unload'
  );
  assert.equal(unloads.length, 1);
  assert.equal(unloads[0]['et.fid'], 8);
  assert.equal(unloads[0]['et.inp'], 60);
  cleanup();
});

test('sends a BFCache response only when the official plugin is absent', () => {
  const fallback = createFakeWindow();
  const official = createFakeWindow({ plugins: { BFCache: {} } });
  const cleanupFallback = installBoomerangInstrumentation(fallback.window);
  const cleanupOfficial = installBoomerangInstrumentation(official.window);

  fallback.events.dispatch('pageshow', { persisted: true, timeStamp: 20 });
  official.events.dispatch('pageshow', { persisted: true, timeStamp: 20 });

  assert.equal(fallback.responses.length, 1);
  assert.equal(fallback.responses[0][0].initiator, 'bfcache');
  assert.equal(official.responses.length, 0);
  cleanupFallback();
  cleanupOfficial();
});
