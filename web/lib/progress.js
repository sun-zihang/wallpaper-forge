export function batchPct(done, currentPct, total) {
  const t = Math.max(1, total | 0);
  const span = 100 / t;
  const pct = Math.max(0, Math.min(100, Number(currentPct) || 0));
  return Math.max(0, Math.min(100, Math.round(Math.max(0, done | 0) * span + (span * pct) / 100)));
}
