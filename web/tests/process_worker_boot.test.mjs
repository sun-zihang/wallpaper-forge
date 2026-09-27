// Boots process_worker.js in a simulated worker global scope to cover the
// auto-install branch; kept in its own file because the module is cached after
// the first import in a process.
import test from "node:test";
import assert from "node:assert/strict";

test("process_worker installs handlers when loaded inside a worker-like scope", async () => {
  const fakeSelf = { posted: [] };
  fakeSelf.postMessage = (data) => fakeSelf.posted.push(data);
  const origScope = globalThis.WorkerGlobalScope;
  const origSelf = globalThis.self;
  globalThis.WorkerGlobalScope = class WorkerGlobalScope {};
  globalThis.self = fakeSelf;
  try {
    const mod = await import("../lib/process_worker.js");
    assert.equal(typeof fakeSelf.onmessage, "function");
    // malformed and unknown messages are ignored, nothing is posted
    fakeSelf.onmessage(null);
    fakeSelf.onmessage({ data: { id: 1 } });
    fakeSelf.onmessage({ data: { id: 1, kind: "no_such_kind" } });
    assert.equal(fakeSelf.posted.length, 0);
    assert.ok(mod.handlers.convert_image);
  } finally {
    if (origScope === undefined) delete globalThis.WorkerGlobalScope;
    else globalThis.WorkerGlobalScope = origScope;
    if (origSelf === undefined) delete globalThis.self;
    else globalThis.self = origSelf;
  }
});
