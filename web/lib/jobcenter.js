// web/lib/jobcenter.js
// 全局作业注册表。各页面的作业表通过 joblist.js 上报，
// #/jobs 路由读取并管理（暂停/下载/清除/重排）。
const jobs = [];
const listeners = new Set();
let seq = 0;

function notify() {
  for (const fn of listeners) fn(jobs);
}

export function reportJob(update) {
  const id = update.id;
  let job = jobs.find((j) => j.id === id);
  if (!job) {
    job = {
      key: ++seq,
      id,
      name: update.name || id,
      page: update.page || "",
      status: "pending",
      detail: "",
      progress: 0,
      blob: null,
      filename: null,
      createdAt: Date.now(),
    };
    jobs.push(job);
  }
  if (update.name !== undefined) job.name = update.name;
  if (update.page !== undefined) job.page = update.page;
  if (update.status !== undefined) job.status = update.status;
  if (update.detail !== undefined) job.detail = update.detail;
  if (update.progress !== undefined) job.progress = update.progress;
  if (update.blob !== undefined) job.blob = update.blob;
  if (update.filename !== undefined) job.filename = update.filename;
  notify();
}

export function getJobs() {
  return [...jobs];
}

export function onJobChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function clearFinished() {
  for (let i = jobs.length - 1; i >= 0; i--) {
    if (["done", "failed", "cancelled"].includes(jobs[i].status)) jobs.splice(i, 1);
  }
  notify();
}

export function removeJob(id) {
  const i = jobs.findIndex((j) => j.id === id);
  if (i >= 0) {
    jobs.splice(i, 1);
    notify();
  }
}

export function moveJob(id, dir) {
  const i = jobs.findIndex((j) => j.id === id);
  if (i < 0) return;
  const j = i + dir;
  if (j < 0 || j >= jobs.length) return;
  [jobs[i], jobs[j]] = [jobs[j], jobs[i]];
  notify();
}
