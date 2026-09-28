// web/tests/sw_core.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import "../lib/sw_core.js";

const core = globalThis.__wcCore;
const req = (over = {}) => ({
  method: "GET",
  url: "https://site.test/app.js",
  headers: { has: () => false },
  ...over,
});
const res = (over = {}) => ({
  ok: true,
  status: 200,
  type: "basic",
  url: "https://site.test/app.js",
  ...over,
});

test("cacheName namespaces versions under one prefix", () => {
  assert.equal(core.cacheName("7"), "wc-shell-7");
  assert.equal(core.CACHE_PREFIX, "wc-shell-");
});

test("isNavigationRequest detects navigations", () => {
  assert.equal(core.isNavigationRequest(req({ mode: "navigate" })), true);
  assert.equal(core.isNavigationRequest(req({ destination: "document" })), true);
  assert.equal(core.isNavigationRequest(req({ mode: "cors", destination: "script" })), false);
});

test("isCacheableResponse accepts plain successful GETs", () => {
  assert.equal(core.isCacheableResponse(req(), res()), true);
});

test("isCacheableResponse rejects non-GET and missing responses", () => {
  assert.equal(core.isCacheableResponse(req({ method: "POST" }), res()), false);
  assert.equal(core.isCacheableResponse(null, res()), false);
  assert.equal(core.isCacheableResponse(req(), undefined), false);
});

test("isCacheableResponse rejects error, partial, and opaque responses", () => {
  assert.equal(core.isCacheableResponse(req(), res({ ok: false, status: 404 })), false);
  assert.equal(core.isCacheableResponse(req(), res({ status: 206 })), false);
  assert.equal(core.isCacheableResponse(req(), res({ type: "opaque" })), false);
  assert.equal(core.isCacheableResponse(req(), res({ type: "opaqueredirect" })), false);
});

test("isCacheableResponse rejects non-http schemes and range requests", () => {
  assert.equal(
    core.isCacheableResponse(req(), res({ url: "file:///C:/app.js" })),
    false,
  );
  assert.equal(
    core.isCacheableResponse(req(), res({ url: "not a url" })),
    false,
  );
  assert.equal(
    core.isCacheableResponse(req({ headers: { has: (h) => h === "range" } }), res()),
    false,
  );
  assert.equal(
    core.isCacheableResponse(req({ headers: undefined }), res()),
    true,
    "missing headers fall through safely",
  );
});
