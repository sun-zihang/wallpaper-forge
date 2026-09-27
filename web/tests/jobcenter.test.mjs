// web/tests/jobcenter.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { reportJob, getJobs, onJobChange, clearFinished, removeJob, moveJob } from "../lib/jobcenter.js";

test("reportJob creates and updates jobs", () => {
  reportJob({ id: "image:0", name: "a.png", page: "图片", status: "pending" });
  reportJob({ id: "image:0", status: "running", progress: 50 });
  reportJob({ id: "image:0", status: "done", progress: 100 });
  const job = getJobs().find((j) => j.id === "image:0");
  assert.equal(job.name, "a.png");
  assert.equal(job.page, "图片");
  assert.equal(job.status, "done");
  assert.equal(job.progress, 100);
});

test("reportJob treats different pages as distinct jobs", () => {
  reportJob({ id: "图片:0", name: "x", page: "图片" });
  reportJob({ id: "GIF:0", name: "y", page: "GIF" });
  const jobs = getJobs().filter((j) => j.id === "图片:0" || j.id === "GIF:0");
  assert.equal(jobs.length, 2);
  assert.equal(jobs[0].page, "图片");
  assert.equal(jobs[1].page, "GIF");
});

test("onJobChange notifies subscribers", () => {
  const seen = [];
  const off = onJobChange((jobs) => seen.push(jobs.length));
  reportJob({ id: "video:1", name: "v.mp4", page: "视频" });
  assert.equal(seen.length, 1);
  off();
  reportJob({ id: "video:2", name: "v2.mp4", page: "视频" });
  assert.equal(seen.length, 1, "unsubscribed listener must not fire");
});

test("clearFinished removes done/failed/cancelled only", () => {
  reportJob({ id: "c:1", status: "done" });
  reportJob({ id: "c:2", status: "running" });
  reportJob({ id: "c:3", status: "failed" });
  reportJob({ id: "c:4", status: "pending" });
  clearFinished();
  const jobs = getJobs().filter((j) => j.id.startsWith("c:"));
  assert.deepEqual(
    jobs.map((j) => j.id).sort(),
    ["c:2", "c:4"],
  );
});

test("removeJob and moveJob reorder the queue", () => {
  reportJob({ id: "m:1", status: "pending" });
  reportJob({ id: "m:2", status: "pending" });
  reportJob({ id: "m:3", status: "pending" });
  moveJob("m:1", 1);
  let ids = getJobs().filter((j) => j.id.startsWith("m:")).map((j) => j.id);
  assert.deepEqual(ids, ["m:2", "m:1", "m:3"]);
  removeJob("m:2");
  ids = getJobs().filter((j) => j.id.startsWith("m:")).map((j) => j.id);
  assert.deepEqual(ids, ["m:1", "m:3"]);
});
