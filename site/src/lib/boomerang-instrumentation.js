const DEFAULT_ERROR_LIMIT = 10;
const ERROR_MESSAGE_LIMIT = 500;
const REQUEST_IDLE_MS = 50;
const ERROR_SEND_INTERVAL_MS = 1000;

export function hasPlugin(boomr, name) {
  return Boolean(boomr?.plugins?.[name]);
}

export function normalizeError(value) {
  let message;
  if (value && typeof value.message === 'string') {
    message = value.message;
  } else {
    message = String(value ?? 'Unknown error');
  }
  return message.slice(0, ERROR_MESSAGE_LIMIT);
}

export function shouldExcludeRequest(url, boomr) {
  const requestUrl = String(url ?? '');
  if (!requestUrl) return true;

  const builtInExcludes = [
    'go-mpulse.net',
    'akstat.io',
    'soasta.com',
    'trial-eum-clientnsv4-s.akamaihd.net',
    'trial-eum-clienttons-s.akamaihd.net'
  ];
  if (builtInExcludes.some((fragment) => requestUrl.includes(fragment))) return true;

  return Object.entries(boomr?.xhr_excludes || {}).some(
    ([fragment, enabled]) => enabled && requestUrl.includes(fragment)
  );
}

export function createRequestBatcher({
  now,
  report,
  schedule,
  cancel,
  excluded,
  idleMs = REQUEST_IDLE_MS
}) {
  let batch = null;
  let flushTimer = null;
  let tokenId = 0;

  function clearFlushTimer() {
    if (flushTimer !== null) {
      cancel(flushTimer);
      flushTimer = null;
    }
  }

  function reset() {
    clearFlushTimer();
    batch = null;
  }

  function flush() {
    if (!batch || batch.active > 0) return false;

    const completed = batch;
    reset();
    if (!completed.mutated) return false;

    report({
      initiator: 'xhr',
      requestType: completed.requestType,
      requestCount: completed.requestCount,
      status: completed.status,
      tStart: completed.tStart,
      tEnd: completed.tEnd,
      url: completed.url
    });
    return true;
  }

  return {
    begin(url, requestType = 'xhr') {
      if (excluded(url)) return { excluded: true };
      clearFlushTimer();

      if (!batch) {
        batch = {
          active: 0,
          mutated: false,
          requestCount: 0,
          requestType,
          status: 0,
          tEnd: 0,
          tStart: now(),
          url: String(url)
        };
      }

      batch.active += 1;
      batch.requestCount += 1;
      return { batch, excluded: false, id: ++tokenId };
    },

    finish(token, { status = 0 } = {}) {
      if (!token || token.excluded || !batch || token.batch !== batch) return false;
      batch.active = Math.max(0, batch.active - 1);
      batch.status = batch.status || status;
      batch.tEnd = now();
      if (batch.active === 0) {
        flushTimer = schedule(flush, idleMs);
      }
      return true;
    },

    markMutation() {
      if (batch) batch.mutated = true;
    },

    flush,

    dispose() {
      reset();
    }
  };
}

export function createErrorReporter({
  boomr,
  schedule,
  cancel,
  limit = DEFAULT_ERROR_LIMIT,
  intervalMs = ERROR_SEND_INTERVAL_MS
}) {
  const seen = new Set();
  let pending = [];
  let timer = null;

  function flush() {
    if (timer !== null) {
      cancel(timer);
      timer = null;
    }
    if (pending.length === 0) return false;

    for (const entry of pending) {
      boomr.addError(entry.message, entry.source);
    }
    pending = [];
    boomr.sendBeacon();
    return true;
  }

  return {
    report(value, source = 'vst') {
      if (seen.size >= limit) return false;
      const message = normalizeError(value);
      const key = `${source}:${message}`;
      if (seen.has(key)) return false;

      seen.add(key);
      pending.push({ message, source });
      if (timer === null) timer = schedule(flush, intervalMs);
      return true;
    },

    flush,

    dispose() {
      if (timer !== null) cancel(timer);
      timer = null;
      pending = [];
    }
  };
}

export function createFirstInputSender(boomr) {
  let sent = false;

  return function sendFirstInput(input) {
    if (sent || !input || !boomr.hasSentPageLoadBeacon()) return false;

    boomr.sendAll({
      timers: { FirstInputAll: Math.max(0, Math.ceil(input.delay || 0)) },
      vars: { 'c.ttfi': boomr.hrNow() }
    });
    sent = true;
    return true;
  };
}

function addFiniteMetric(beacon, name, value) {
  if (Number.isFinite(value)) beacon[name] = value;
}

export function buildUnloadBeacon(boomr, metrics) {
  const timestamp = boomr.now();
  const beacon = {
    'api.l': 'boomr',
    'api.v': 2,
    api: 1,
    d: boomr.session.domain,
    'h.cr': boomr.getVar('h.cr'),
    'h.d': boomr.getVar('h.d'),
    'h.key': boomr.getVar('h.key'),
    'h.t': boomr.getVar('h.t'),
    'http.initiator': 'api_custom_unload',
    n: ++boomr.beaconsSent,
    pid: boomr.pageId,
    'rt.end': timestamp,
    'rt.sl': boomr.session.length,
    'rt.ss': boomr.session.start,
    'rt.si': `${boomr.session.ID}-${Math.round(boomr.session.start / 1000).toString(36)}`,
    'rt.start': 'manual',
    'rt.tstart': timestamp,
    v: boomr.version
  };

  addFiniteMetric(beacon, 'c.cls', metrics?.cls);
  addFiniteMetric(beacon, 'et.fid', metrics?.fid);
  addFiniteMetric(beacon, 'et.inp', metrics?.inp);
  return beacon;
}

function getRequestUrl(input) {
  if (typeof input === 'string') return input;
  if (input && typeof input.url === 'string') return input.url;
  return String(input ?? '');
}

function readEventTimingMetrics(boomr) {
  const metrics = boomr?.plugins?.EventTiming?.metrics;
  const read = (name) => {
    try {
      return typeof metrics?.[name] === 'function' ? metrics[name]() : undefined;
    } catch {
      return undefined;
    }
  };
  return {
    fid: read('firstInputDelay'),
    inp: read('interactionToNextPaint')
  };
}

function installLayoutShiftObserver(browserWindow, metrics, cleanups) {
  if (typeof browserWindow.PerformanceObserver !== 'function') return;

  try {
    const observer = new browserWindow.PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput && Number.isFinite(entry.value)) metrics.cls += entry.value;
      }
    });
    observer.observe({ buffered: true, type: 'layout-shift' });
    cleanups.push(() => observer.disconnect());
  } catch {
    // LayoutShift observation is optional and browser-dependent.
  }
}

function installRequestFallback(browserWindow, boomr, reporter, options, cleanups) {
  if (hasPlugin(boomr, 'AutoXHR')) return;

  const schedule = options.schedule || globalThis.setTimeout;
  const cancel = options.cancel || globalThis.clearTimeout;
  const batcher = createRequestBatcher({
    now: () => boomr.now(),
    report: (request) => {
      boomr.responseEnd(
        { initiator: 'xhr', url: request.url },
        request.tStart,
        {
          requestCount: request.requestCount,
          requestType: request.requestType,
          status: request.status
        },
        request.tEnd
      );
    },
    schedule,
    cancel,
    excluded: (url) => shouldExcludeRequest(url, boomr),
    idleMs: options.requestIdleMs ?? REQUEST_IDLE_MS
  });
  cleanups.push(() => batcher.dispose());

  if (typeof browserWindow.MutationObserver === 'function' && browserWindow.document?.documentElement) {
    const observer = new browserWindow.MutationObserver((records) => {
      if (records.some((record) => record.type === 'childList' || record.type === 'attributes')) {
        batcher.markMutation();
      }
    });
    observer.observe(browserWindow.document.documentElement, {
      attributes: true,
      attributeFilter: ['href', 'src'],
      childList: true,
      subtree: true
    });
    cleanups.push(() => observer.disconnect());
  }

  if (typeof browserWindow.fetch === 'function') {
    const originalFetch = browserWindow.fetch;
    browserWindow.fetch = function instrumentedFetch(input, init) {
      const url = getRequestUrl(input);
      const token = batcher.begin(url, 'fetch');
      let request;
      try {
        request = originalFetch.call(this, input, init);
      } catch (error) {
        batcher.finish(token);
        reporter?.report(error, 'fetch');
        throw error;
      }

      return Promise.resolve(request).then(
        (response) => {
          batcher.finish(token, { status: response?.status || 0 });
          if (response?.status >= 400) reporter?.report(`HTTP ${response.status}: ${url}`, 'fetch');
          return response;
        },
        (error) => {
          batcher.finish(token);
          reporter?.report(error, 'fetch');
          throw error;
        }
      );
    };
    cleanups.push(() => {
      browserWindow.fetch = originalFetch;
    });
  }

  const xhrPrototype = browserWindow.XMLHttpRequest?.prototype;
  if (!xhrPrototype?.open || !xhrPrototype?.send) return;

  const originalOpen = xhrPrototype.open;
  const originalSend = xhrPrototype.send;
  const requestDetails = Symbol('vstBoomerangRequest');
  xhrPrototype.open = function instrumentedOpen(method, url, ...args) {
    this[requestDetails] = { method, url: getRequestUrl(url) };
    return originalOpen.call(this, method, url, ...args);
  };
  xhrPrototype.send = function instrumentedSend(...args) {
    const details = this[requestDetails] || { method: 'GET', url: '' };
    const token = batcher.begin(details.url, 'xhr');
    const finish = () => {
      batcher.finish(token, { status: this.status || 0 });
      if (this.status >= 400) reporter?.report(`HTTP ${this.status}: ${details.url}`, 'xhr');
    };
    this.addEventListener('loadend', finish, { once: true });
    try {
      return originalSend.apply(this, args);
    } catch (error) {
      batcher.finish(token);
      reporter?.report(error, 'xhr');
      throw error;
    }
  };
  cleanups.push(() => {
    xhrPrototype.open = originalOpen;
    xhrPrototype.send = originalSend;
  });
}

function installErrorFallback(browserWindow, boomr, options, cleanups) {
  const earlyErrors = browserWindow.BOOMR_EARLY_STATE?.errors || [];
  if (hasPlugin(boomr, 'Errors')) {
    if (earlyErrors.length > 0 && typeof boomr.addError === 'function') {
      for (const entry of earlyErrors) boomr.addError(entry.message, entry.source);
      boomr.sendBeacon();
    }
    earlyErrors.length = 0;
    return null;
  }

  const reporter = createErrorReporter({
    boomr,
    schedule: options.schedule || globalThis.setTimeout,
    cancel: options.cancel || globalThis.clearTimeout,
    intervalMs: options.errorIntervalMs ?? ERROR_SEND_INTERVAL_MS
  });
  cleanups.push(() => reporter.dispose());

  const reportWindowError = (event) => reporter.report(event?.error || event?.message, 'window.error');
  const reportRejection = (event) => reporter.report(event?.reason, 'unhandledrejection');
  browserWindow.addEventListener('error', reportWindowError);
  browserWindow.addEventListener('unhandledrejection', reportRejection);
  cleanups.push(() => browserWindow.removeEventListener('error', reportWindowError));
  cleanups.push(() => browserWindow.removeEventListener('unhandledrejection', reportRejection));

  for (const entry of earlyErrors) {
    reporter.report(entry.message, entry.source);
  }
  earlyErrors.length = 0;

  if (browserWindow.console?.error) {
    const originalConsoleError = browserWindow.console.error;
    browserWindow.console.error = function instrumentedConsoleError(...args) {
      reporter.report(args[0], 'console.error');
      return originalConsoleError.apply(this, args);
    };
    cleanups.push(() => {
      browserWindow.console.error = originalConsoleError;
    });
  }

  if (typeof browserWindow.ReportingObserver === 'function') {
    try {
      const observer = new browserWindow.ReportingObserver((reports) => {
        for (const report of reports) reporter.report(report?.body?.message || report?.type, 'reporting');
      });
      observer.observe();
      cleanups.push(() => observer.disconnect());
    } catch {
      // ReportingObserver is optional and implementations vary by browser.
    }
  }

  return reporter;
}

function installFirstInput(browserWindow, boomr, cleanups) {
  const sendFirstInput = createFirstInputSender(boomr);
  const earlyState = browserWindow.BOOMR_EARLY_STATE;
  let pendingInput = earlyState?.firstInput || null;

  const sendPendingInput = () => {
    if (!pendingInput || !sendFirstInput(pendingInput)) return false;
    pendingInput = null;
    return true;
  };

  const onFirstInput = (event) => {
    const detail = event?.detail || event;
    pendingInput = {
      delay: Number.isFinite(detail?.delay)
        ? detail.delay
        : Math.max(0, (browserWindow.performance?.now?.() || 0) - (detail?.timeStamp || 0)),
      type: detail?.type
    };
    sendPendingInput();
  };
  browserWindow.addEventListener('vst:boomerang-first-input', onFirstInput);
  cleanups.push(() => browserWindow.removeEventListener('vst:boomerang-first-input', onFirstInput));

  if (typeof boomr.subscribe === 'function') {
    boomr.subscribe('page_load_beacon', sendPendingInput, null, null, true);
    cleanups.push(() => boomr.unsubscribe?.('page_load_beacon', sendPendingInput));
  }
  sendPendingInput();
}

function installUnloadAndBFCache(browserWindow, boomr, metrics, cleanups) {
  let unloadSent = false;
  const onPageHide = (event) => {
    if (event?.persisted || unloadSent) return;

    const eventMetrics = readEventTimingMetrics(boomr);
    const unloadMetrics = {
      cls: metrics.cls || undefined,
      fid: eventMetrics.fid ?? browserWindow.BOOMR_EARLY_STATE?.firstInput?.delay,
      inp: eventMetrics.inp
    };
    if (!Object.values(unloadMetrics).some(Number.isFinite)) return;

    if (Number.isFinite(unloadMetrics.inp) && typeof boomr.sendTimer === 'function') {
      boomr.sendTimer('INPatUnload', unloadMetrics.inp);
    }
    boomr.sendBeaconData(buildUnloadBeacon(boomr, unloadMetrics));
    unloadSent = true;
  };
  browserWindow.addEventListener('pagehide', onPageHide);
  cleanups.push(() => browserWindow.removeEventListener('pagehide', onPageHide));

  if (hasPlugin(boomr, 'BFCache')) return;
  const onPageShow = (event) => {
    if (!event?.persisted) return;
    const timestamp = boomr.now();
    boomr.responseEnd(
      { initiator: 'bfcache', url: browserWindow.location?.href || '' },
      timestamp,
      { persisted: true },
      timestamp
    );
  };
  browserWindow.addEventListener('pageshow', onPageShow);
  cleanups.push(() => browserWindow.removeEventListener('pageshow', onPageShow));
}

function setupInstrumentation(browserWindow, options) {
  const boomr = browserWindow.BOOMR;
  const cleanups = [];
  const metrics = { cls: 0 };

  installLayoutShiftObserver(browserWindow, metrics, cleanups);
  installFirstInput(browserWindow, boomr, cleanups);
  const reporter = installErrorFallback(browserWindow, boomr, options, cleanups);
  browserWindow.BOOMR_EARLY_STATE?.stopErrorCapture?.();
  installRequestFallback(browserWindow, boomr, reporter, options, cleanups);
  installUnloadAndBFCache(browserWindow, boomr, metrics, cleanups);

  return () => {
    for (const cleanup of cleanups.reverse()) cleanup();
  };
}

export function installBoomerangInstrumentation(browserWindow, options = {}) {
  if (!browserWindow?.BOOMR_API_key) return () => {};
  if (browserWindow.__VST_BOOMR_INSTRUMENTATION__) return () => {};

  browserWindow.__VST_BOOMR_INSTRUMENTATION__ = true;
  let teardown = () => {};
  let ready = false;

  const onReady = () => {
    if (ready || !browserWindow.BOOMR?.version) return;
    ready = true;
    browserWindow.removeEventListener('vst:boomerang-ready', onReady);
    teardown = setupInstrumentation(browserWindow, options);
  };

  browserWindow.addEventListener('vst:boomerang-ready', onReady);
  onReady();

  return () => {
    browserWindow.removeEventListener('vst:boomerang-ready', onReady);
    teardown();
    browserWindow.__VST_BOOMR_INSTRUMENTATION__ = false;
  };
}
