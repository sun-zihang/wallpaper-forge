// pipeline.js 测试:并发上限、shouldStop 停止派发、allSettled 语义、索引有序
import test from "node:test";
import assert from "node:assert/strict";
import { runLimited } from "../lib/pipeline.js";

const tick = () => new Promise((r) => setTimeout(r, 0));

test("runLimited: 全部完成,结果按索引有序(allSettled 语义)", async () => {
  const r = await runLimited(4, async (i) => {
    await tick();
    return i * 10;
  });
  assert.deepEqual(
    r.map((x) => x.status),
    ["fulfilled", "fulfilled", "fulfilled", "fulfilled"],
  );
  assert.deepEqual(r.map((x) => x.value), [0, 10, 20, 30]);
});

test("runLimited: 并发不超过 limit(用最大在飞数验证)", async () => {
  let inFlight = 0;
  let peak = 0;
  const r = await runLimited(
    6,
    async (i) => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await tick();
      await tick();
      inFlight -= 1;
      return i;
    },
    { limit: 2 },
  );
  assert.equal(r.length, 6);
  assert.equal(peak, 2, "最多 2 个在飞(与池大小一致)");
});

test("runLimited: 任务抛错被捕获为 rejected,不阻塞后续", async () => {
  const r = await runLimited(3, async (i) => {
    if (i === 1) throw new Error("boom");
    return i;
  });
  assert.equal(r[0].status, "fulfilled");
  assert.equal(r[1].status, "rejected");
  assert.match(String(r[1].reason), /boom/);
  assert.equal(r[2].status, "fulfilled");
});

test("runLimited: shouldStop 翻转后不再派发新任务", async () => {
  let stop = false;
  const started = [];
  const r = await runLimited(
    10,
    async (i) => {
      started.push(i);
      await tick();
      if (started.length >= 3) stop = true;
      return i;
    },
    { limit: 1, shouldStop: () => stop },
  );
  assert.ok(started.length < 10, `只跑了 ${started.length} 个,不是全部 10 个`);
  // 未派发的索引保持 undefined
  for (let i = started.length; i < 10; i++) assert.equal(r[i], undefined);
});

test("runLimited: count=0 与 limit=0 的边界", async () => {
  assert.deepEqual(await runLimited(0, async () => 1), []);
  const r = await runLimited(2, async (i) => i, { limit: 0 });
  // limit 钳到 1:仍要全部完成
  assert.deepEqual(r.map((x) => x.value), [0, 1]);
});
