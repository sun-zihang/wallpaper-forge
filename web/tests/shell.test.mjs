// web/tests/shell.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { WEB_VERSION } from "../version.js";

test("web version semver-ish", () => {
  assert.match(WEB_VERSION, /^\d+\.\d+\.\d+$/);
});

const html = await readFile(new URL("../index.html", import.meta.url), "utf8");

test("index.html ships icon, preconnect, description and og tags", () => {
  assert.match(html, /rel="icon"\s+href="\.\/favicon\.ico"/);
  assert.match(html, /rel="preconnect" href="https:\/\/cdn\.jsdelivr\.net"/);
  assert.match(html, /rel="preconnect" href="https:\/\/unpkg\.com"/);
  assert.match(html, /rel="preconnect" href="https:\/\/esm\.sh"/);
  assert.match(html, /name="description" content="[^"]{20,}"/);
  assert.match(html, /name="theme-color" content="#[0-9a-f]{6}"/i);
  assert.match(html, /property="og:title"/);
  assert.match(html, /property="og:image" content="https:\/\/sun-zihang\.github\.io\/wallpaper-forge\/og-image\.png"/);
  assert.match(html, /property="og:url" content="https:\/\/sun-zihang\.github\.io\/wallpaper-forge\/"/);
});

test("favicon.ico exists and looks like an ico", async () => {
  const bytes = await readFile(new URL("../favicon.ico", import.meta.url));
  assert.ok(bytes.length > 0, "favicon.ico is empty");
  // ICO magic: 00 00 01 00
  assert.deepEqual([...bytes.subarray(0, 4)], [0x00, 0x00, 0x01, 0x00]);
});

test("og-image.png exists and has png magic", async () => {
  const bytes = await readFile(new URL("../og-image.png", import.meta.url));
  assert.deepEqual([...bytes.subarray(0, 4)], [0x89, 0x50, 0x4e, 0x47]);
});

test("404.html redirects unknown paths back to the app", async () => {
  const notFound = await readFile(new URL("../404.html", import.meta.url), "utf8");
  assert.match(notFound, /location\.replace\("\/wallpaper-forge\/"\)/);
  assert.match(notFound, /rel="icon"/);
});
