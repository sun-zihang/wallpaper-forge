// web/tests/telemetry.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

function installStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  return store;
}

async function importTelemetry() {
  return import("../lib/telemetry.js");
}

test("telemetry is disabled by default and toggles persist", async () => {
  const store = installStorage();
  const { isEnabled, setEnabled } = await importTelemetry();
  assert.equal(isEnabled(), false);
  assert.equal(setEnabled(true), true);
  assert.equal(store.get("wc.telemetry"), "1");
  assert.equal(isEnabled(), true);
  assert.equal(setEnabled(false), false);
  assert.equal(store.has("wc.telemetry"), false);
  assert.equal(isEnabled(), false);
});

test("endpoint falls back to the built-in default and can be overridden", async () => {
  const store = installStorage();
  const { getEndpoint, setEndpoint } = await importTelemetry();
  assert.equal(getEndpoint(), "");
  setEndpoint("https://example.test/telemetry");
  assert.equal(store.get("wc.telemetryEndpoint"), "https://example.test/telemetry");
  assert.equal(getEndpoint(), "https://example.test/telemetry");
  setEndpoint("");
  assert.equal(getEndpoint(), "");
});

test("storage failures do not throw", async () => {
  globalThis.localStorage = {
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("blocked");
    },
    removeItem() {
      throw new Error("blocked");
    },
  };
  const { isEnabled, setEnabled, getEndpoint, flush } = await importTelemetry();
  assert.equal(isEnabled(), false);
  assert.equal(setEnabled(true), false, "cannot enable without storage");
  assert.equal(setEnabled(false), false, "disable path survives throwing storage");
  assert.equal(getEndpoint(), "");
  assert.equal((await flush()).reason, "disabled");
});

test("flush does nothing while disabled or unconfigured", async () => {
  installStorage();
  const { flush, setEnabled, setEndpoint } = await importTelemetry();
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return { ok: true };
  };
  assert.deepEqual(await flush({ fetchImpl }), { sent: false, reason: "disabled" });
  setEnabled(true);
  assert.deepEqual(await flush({ fetchImpl }), { sent: false, reason: "no-endpoint" });
  setEndpoint("https://example.test/telemetry");
  assert.equal(calls, 0, "fetch never called before endpoint is configured");
});

test("flush posts aggregates only — no event details", async () => {
  const store = installStorage();
  const { setEnabled, setEndpoint, flush } = await importTelemetry();
  setEnabled(true);
  setEndpoint("https://example.test/telemetry");
  const seen = {};
  const fetchImpl = async (url, opts) => {
    seen.url = url;
    seen.opts = opts;
    return { ok: true, status: 200 };
  };
  const r = await flush({ fetchImpl, now: 1000 });
  assert.equal(r.sent, true);
  assert.equal(seen.url, "https://example.test/telemetry");
  assert.equal(seen.opts.method, "POST");
  assert.equal(seen.opts.keepalive, true);
  const body = JSON.parse(seen.opts.body);
  assert.equal(body.v, 1);
  assert.equal(body.ts, 1000);
  assert.equal(typeof body.counters, "object");
  assert.equal(body.recent, undefined, "raw events are never sent");
  assert.equal(body.events, undefined);
  assert.equal(store.get("wc.telemetrySentAt"), "1000");
});

test("flush throttles repeats unless forced", async () => {
  installStorage();
  const { setEnabled, setEndpoint, flush } = await importTelemetry();
  setEnabled(true);
  setEndpoint("https://example.test/telemetry");
  let calls = 0;
  const fetchImpl = async () => {
    calls += 1;
    return { ok: true };
  };
  const first = await flush({ fetchImpl, now: 5000 });
  assert.equal(first.sent, true);
  const second = await flush({ fetchImpl, now: 5000 + 60 * 1000 });
  assert.deepEqual(second, { sent: false, reason: "throttled" });
  assert.equal(calls, 1, "throttled call never reaches the network");
  const forced = await flush({ fetchImpl, now: 5000 + 60 * 1000, force: true });
  assert.equal(forced.sent, true);
  assert.equal(calls, 2);
});

test("flush reports http errors, thrown fetches, and missing fetch", async () => {
  installStorage();
  const { setEnabled, setEndpoint, flush } = await importTelemetry();
  setEnabled(true);
  setEndpoint("https://example.test/telemetry");

  const httpFail = await flush({
    fetchImpl: async () => ({ ok: false, status: 502 }),
    force: true,
  });
  assert.deepEqual(httpFail, { sent: false, reason: "http-502" });

  const thrown = await flush({
    fetchImpl: async () => {
      throw new Error("offline");
    },
    force: true,
  });
  assert.deepEqual(thrown, { sent: false, reason: "error" });

  const origFetch = globalThis.fetch;
  delete globalThis.fetch;
  try {
    const missing = await flush({ force: true });
    assert.deepEqual(missing, { sent: false, reason: "no-fetch" });
  } finally {
    globalThis.fetch = origFetch;
  }
});
