// Small concurrency limiter for batch pages: runs count tasks with at most
// `limit` in flight (matching the worker pool size) instead of one giant
// serial await loop, so both pool workers actually get work.
//
// Semantics:
// - startTask(i) is called for i in 0..count-1, at most `limit` running at
//   once; each lane pulls the next index only when its previous task settles.
// - shouldStop() is polled before every dispatch. When it turns true no NEW
//   task starts; in-flight tasks run to completion (the pool has no
//   per-job cancel — terminate would kill the shared pool for other pages).
// - allSettled semantics: startTask's rejections are captured per index, the
//   run always resolves. Indexes never dispatched stay `undefined` in the
//   result array — callers treat that as "not run / cancelled".

/** Run count tasks with bounded concurrency. Returns per-index
 *  { status, value | reason } like Promise.allSettled. */
export async function runLimited(count, startTask, { limit = 2, shouldStop } = {}) {
  const results = new Array(count);
  let next = 0;
  let stopped = false;
  async function lane() {
    while (true) {
      if (stopped || (shouldStop && shouldStop())) {
        stopped = true;
        return;
      }
      const i = next;
      if (i >= count) return;
      next += 1;
      try {
        results[i] = { status: "fulfilled", value: await startTask(i) };
      } catch (reason) {
        results[i] = { status: "rejected", reason };
      }
    }
  }
  const lanes = [];
  const laneCount = Math.min(Math.max(1, limit | 0), count);
  for (let k = 0; k < laneCount; k++) lanes.push(lane());
  await Promise.all(lanes);
  return results;
}
