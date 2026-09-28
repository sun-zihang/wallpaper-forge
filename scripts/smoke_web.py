# End-to-end browser smoke for the web version (local server or live Pages).
#
# Local:
#   python -m http.server 8791 --directory web
#   python scripts/smoke_web.py
# Live / CI:
#   SMOKE_BASE=https://sun-zihang.github.io/wallpaper-forge python scripts/smoke_web.py
#
# Fixtures are written to %TEMP%/wc_smoke_fixtures (override with SMOKE_FIX).
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

FIX = Path(os.environ.get("SMOKE_FIX") or Path(tempfile.gettempdir()) / "wc_smoke_fixtures")
FIX.mkdir(parents=True, exist_ok=True)
BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8791").rstrip("/")

png_path = FIX / "wall.png"
img = Image.new("RGB", (320, 200))
px = img.load()
assert px is not None
for y in range(200):
    for x in range(320):
        px[x, y] = ((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
img.save(png_path)

img2_path = FIX / "second.png"
Image.new("RGB", (64, 64), (255, 0, 0)).save(img2_path)

gif_path = FIX / "anim.gif"
frames = [Image.new("RGB", (64, 64), (i * 60 % 256, 100, 255 - i * 60)) for i in range(4)]
frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=80, loop=0)

png_bytes = png_path.read_bytes()
tex_path = FIX / "sample.tex"
tex_path.write_bytes(b"\x00" * 16 + struct.pack("<I", len(png_bytes)) + png_bytes + b"\x00" * 8)

big_path = FIX / "big.mp4"
need = 100 * 1024 * 1024 + 1
if not big_path.exists() or big_path.stat().st_size < need:
    with big_path.open("wb") as f:
        f.seek(need - 1)
        f.write(b"\x00")

tiny_path = FIX / "tiny.mp4"


def _make_tiny_mp4() -> bool:
    try:
        import cv2
        import numpy as np

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        w = cv2.VideoWriter(str(tiny_path), fourcc, 10, (64, 48))
        if w.isOpened():
            for i in range(15):
                w.write(np.full((48, 64, 3), i * 10 % 255, dtype=np.uint8))
            w.release()
            if tiny_path.exists() and tiny_path.stat().st_size > 1000:
                return True
    except Exception as e:
        print("tiny mp4 cv2 skip:", e)
    try:
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=1:size=64x48:rate=10",
                "-pix_fmt",
                "yuv420p",
                str(tiny_path),
            ],
            capture_output=True,
            timeout=60,
        )
        if r.returncode == 0 and tiny_path.exists() and tiny_path.stat().st_size > 1000:
            return True
        print("tiny mp4 ffmpeg rc:", r.returncode, (r.stderr or b"")[-200:])
    except Exception as e:
        print("tiny mp4 ffmpeg skip:", e)
    return False


if not (tiny_path.exists() and tiny_path.stat().st_size > 1000):
    _make_tiny_mp4()

failures: list[str] = []
console_errors = []
warns = []


def check(cond, msg):
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def grab(page, click_sel, timeout=20000):
    with page.expect_download(timeout=timeout) as dl:
        page.click(click_sel)
    return dl.value


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(accept_downloads=True)
    page = ctx.new_page()
    page.add_init_script("localStorage.setItem('wc.onboarded','1')")
    page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
    page.on(
        "console",
        lambda m: (
            console_errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None
        ),
    )

    # 1. home
    page.goto(BASE + "/index.html")
    page.wait_for_load_state("networkidle")
    check(page.locator(".card").count() == 7, "home has 7 cards")
    check("不会上传" in page.content(), "home privacy copy")
    check(page.locator('#app a[href="#/desktop"]').count() >= 1, "home desktop landing link")
    check(page.locator(".rail nav a").count() == 9, "rail has 9 nav items")
    check(
        page.locator("#footer .mono").first.inner_text().startswith("v"),
        "footer shows version",
    )
    check(
        "core" in page.locator("#footer").inner_text()
        and "gifuct" in page.locator("#footer").inner_text(),
        "footer lists dependency versions",
    )

    # 1b. home language toggle (zh <-> en)
    page.click("#langToggle")
    page.wait_for_function(
        "() => { const h = document.querySelector('#app h1'); return h && /browser/i.test(h.textContent); }",
        timeout=5000,
        polling=100,
    )
    check(True, "home switches to English")
    page.click("#langToggle")
    check("处理壁纸" in page.content(), "home switches back to Chinese")

    # 2. image — convert queues, ZIP button downloads
    page.click('nav a[href="#/image"]')
    page.wait_for_selector("#q")
    page.set_input_files("#files", str(png_path))
    page.select_option("#fmt", "JPG")
    page.click("#start")
    page.wait_for_selector("td.st-done", timeout=20000)
    check(True, "image convert reached done")
    check("wall.png" in page.locator(".jobs tbody").inner_text(), "job row shows source name")
    d = grab(page, "#zip")
    check(d.suggested_filename == "images.zip", f"image zip: {d.suggested_filename}")
    check(Path(d.path()).stat().st_size > 0, "image zip non-empty")

    # 2b. BMP encodes natively (was a guaranteed failure before 0.6.2)
    page.set_input_files("#files", str(png_path))
    page.select_option("#fmt", "BMP")
    page.click("#start")
    page.wait_for_selector("td.st-done, td.st-failed", timeout=20000)
    st = page.locator("td.st-done, td.st-failed").first.inner_text()
    check("完成" in st, f"BMP convert succeeded ({st})")
    with page.expect_download(timeout=20000) as dl:
        page.click("#zip")
    zip_path = Path(dl.value.path())
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        bmp_entries = [n for n in names if n.lower().endswith(".bmp")]
        sizes = {n: zf.getinfo(n).file_size for n in bmp_entries}
    check(len(bmp_entries) == 1, f"zip contains exactly one bmp ({names})")
    check(
        all(v > 0 for v in sizes.values()),
        f"bmp entry non-empty ({sizes})",
    )

    check(not console_errors, f"no console errors on home+image ({console_errors[:3]})")

    # 3. gif split — queues, ZIP button downloads frames.zip
    page.click('nav a[href="#/gif"]')
    page.wait_for_selector("#step")
    page.set_input_files("#files", str(gif_path))
    page.click("#start")
    try:
        page.wait_for_selector("td.st-done, td.st-failed", timeout=90000)
        split_status = page.locator("td.st-done, td.st-failed").first.inner_text()
    except Exception as e:
        split_status = f"TIMEOUT {str(e)[:80]}"
        print("GIF ROW:", page.locator(".jobs tbody").inner_html()[:400])
        print("GIF ERR:", page.locator("#err").inner_text()[:200])
        print("GIF CONSOLE:", console_errors[-6:])
    check("完成" in split_status, f"gif split done ({split_status})")
    check(page.locator("#zip").is_visible(), "gif split shows zip button")
    d = grab(page, "#zip", timeout=30000)
    check(d.suggested_filename == "frames.zip", f"gif split zip: {d.suggested_filename}")
    check(Path(d.path()).stat().st_size > 0, "frames zip non-empty")

    # 3a. gif retry — corrupt gif fails, #retry appears and re-runs only failures
    bad_gif = FIX / "bad.gif"
    bad_gif.write_bytes(b"GIF89a" + b"\x00" * 64)
    page.set_input_files("#files", str(bad_gif))
    page.click("#start")
    try:
        page.wait_for_function(
            "() => document.querySelector('#start').disabled", timeout=5000, polling=100
        )
    except Exception:
        print("GIF START STATE err:", page.locator("#err").inner_text()[:200])
        print("GIF START STATE rows:", page.locator(".jobs tbody").inner_text()[:200])
        print("GIF START STATE console:", console_errors[-8:])
        raise
    page.wait_for_function(
        "() => !document.querySelector('#start').disabled", timeout=90000, polling=100
    )
    check(page.locator("td.st-failed").count() >= 1, "gif corrupt file failed")
    check(page.locator("#retry").is_visible(), "gif retry button shows on failure")
    page.click("#retry")
    page.wait_for_function(
        "() => document.querySelector('#start').disabled", timeout=5000, polling=100
    )
    page.wait_for_function(
        "() => !document.querySelector('#start').disabled", timeout=90000, polling=100
    )
    check(page.locator("td.st-failed").count() >= 1, "gif retry re-ran failed job")
    check(page.locator("#retry").is_visible(), "gif retry stays visible after failed retry")

    # reset gif page state so the merge section starts with a clean file list
    page.click('nav a[href="#/unpack"]')
    page.click('nav a[href="#/gif"]')
    page.wait_for_selector("#step")

    # 3b. gif merge — auto download
    page.select_option("#mode", "merge")
    page.set_input_files("#files", [str(png_path), str(img2_path)])
    d = grab(page, "#start", timeout=60000)
    check(d.suggested_filename.endswith(".gif"), f"gif merge download: {d.suggested_filename}")
    page.wait_for_selector("td.st-done", timeout=60000)

    # 4. unpack .tex — queues, #dl downloads unpacked.zip
    page.click('nav a[href="#/unpack"]')
    page.wait_for_selector("#dl")
    page.set_input_files("#files", str(tex_path))
    page.click("#start")
    page.wait_for_selector("td.st-done", timeout=10000)
    d = grab(page, "#dl", timeout=20000)
    check(d.suggested_filename == "unpacked.zip", f"unpack zip: {d.suggested_filename}")
    check(Path(d.path()).stat().st_size > 0, "unpacked zip non-empty")

    # 4b. unpack retry — corrupt pkg fails, #retry appears and re-runs failures
    bad_pkg = FIX / "bad.pkg"
    bad_pkg.write_bytes(b"NOTAPKG" + b"\x00" * 64)
    page.set_input_files("#files", str(bad_pkg))
    page.click("#start")
    page.wait_for_function(
        "() => document.querySelector('#start').disabled", timeout=5000, polling=100
    )
    page.wait_for_function(
        "() => !document.querySelector('#start').disabled", timeout=30000, polling=100
    )
    check(page.locator("td.st-failed").count() >= 1, "unpack corrupt pkg failed")
    check(page.locator("#retry").is_visible(), "unpack retry button shows on failure")
    page.click("#retry")
    page.wait_for_function(
        "() => document.querySelector('#start').disabled", timeout=5000, polling=100
    )
    page.wait_for_function(
        "() => !document.querySelector('#start').disabled", timeout=30000, polling=100
    )
    check(page.locator("td.st-failed").count() >= 1, "unpack retry re-ran failed job")
    check(page.locator("#retry").is_visible(), "unpack retry stays visible after failed retry")

    # 5. video — oversize rejected at drop time, never queued for the engine
    page.click('nav a[href="#/video"]')
    page.wait_for_selector("#mode", state="attached")
    check(page.locator("#retry").count() == 1, "video retry button in DOM")
    page.set_input_files("#files", str(big_path))
    page.wait_for_timeout(300)
    err = page.locator("#err").inner_text()
    check(
        "100MB" in err or "上限" in err or "桌面版" in err,
        f"oversize rejected at drop: {err[:80]}",
    )
    page.click("#start")
    page.wait_for_timeout(300)
    err = page.locator("#err").inner_text()
    check(
        "请先添加视频文件" in err,
        f"oversize never queued for engine: {err[:80]}",
    )

    # 5b. video convert with tiny mp4 (wasm load is slow / may be network-blocked)
    if tiny_path.exists() and tiny_path.stat().st_size > 1000:
        page.set_input_files("#files", str(tiny_path))
        try:
            d = grab(page, "#start", timeout=180000)
            page.wait_for_selector("td.st-done, td.st-failed", timeout=180000)
            st = page.locator("td.st-done, td.st-failed").first.inner_text()
            check("完成" in st, f"video convert result: {st}")
            check(
                d.suggested_filename.endswith((".mp4", ".webm")),
                f"video download: {d.suggested_filename}",
            )
        except Exception as e:
            warns.append(f"video smoke (wasm/network): {str(e)[:200]}")
            print("VIDEO_SMOKE_WARN:", warns[-1])
    else:
        warns.append("tiny.mp4 unavailable; video convert check skipped")

    bad = [e for e in console_errors if "video:" not in e]
    check(not bad, f"clean console ({bad[:5]})")

    # static SEO landing pages + sitemap/robots
    for slug, kw in [
        ("gif-to-png", "GIF"),
        ("webm-to-mp4", "WebM"),
        ("pkg-extract", "PKG"),
        ("tex-to-png", "TEX"),
    ]:
        resp = page.goto(f"{BASE}/{slug}/", wait_until="domcontentloaded")
        check(resp is not None and resp.ok, f"landing /{slug}/ responds 200")
        title = page.title()
        check(kw in title, f"landing {slug} title has keyword ({title[:60]})")
        h1 = page.locator("h1").first.inner_text()
        check(kw in h1, f"landing {slug} h1 has keyword ({h1[:60]})")
        check(
            page.locator(".lp-faq details").count() >= 3,
            f"landing {slug} FAQ block present",
        )
        check(page.locator(".lp-foot a").count() >= 6, f"landing {slug} footer cross-links")
        check(f"/en/{slug}/" in page.content(), f"landing {slug} hreflang links to en")
        resp = page.goto(f"{BASE}/en/{slug}/", wait_until="domcontentloaded")
        check(resp is not None and resp.ok, f"landing en /en/{slug}/ responds 200")
        etitle = page.title()
        check(kw in etitle, f"landing en {slug} title has keyword ({etitle[:60]})")
        eh1 = page.locator("h1").first.inner_text()
        check(kw in eh1, f"landing en {slug} h1 has keyword ({eh1[:60]})")
        check(
            page.locator(".lp-faq details").count() >= 3,
            f"landing en {slug} FAQ block present",
        )
        check(
            page.locator(".lp-foot a").count() >= 6,
            f"landing en {slug} footer cross-links",
        )
        check(
            page.locator('link[rel="canonical"][href*="/en/"]').count() == 1,
            f"landing en {slug} canonical points at /en/",
        )
    sm = page.request.get(f"{BASE}/sitemap.xml")
    check(sm.ok, "sitemap.xml responds")
    smt = sm.text()
    for slug in ("gif-to-png", "webm-to-mp4", "pkg-extract", "tex-to-png"):
        check(slug in smt, f"sitemap lists {slug}")
        check(f"/en/{slug}/" in smt, f"sitemap lists en/{slug}")
    rb = page.request.get(f"{BASE}/robots.txt")
    check(rb.ok and "sitemap.xml" in rb.text(), "robots.txt points at sitemap")

    # 6. service worker: controls the page and serves the shell offline
    page.goto(BASE + "/", wait_until="domcontentloaded")
    try:
        page.wait_for_function(
            "() => navigator.serviceWorker && navigator.serviceWorker.controller",
            timeout=15000,
            polling=100,
        )
        check(True, "service worker controls the page")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".rail nav a", timeout=15000)
        page.context.set_offline(True)
        try:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector(".rail nav a", timeout=15000)
            check(True, "offline reload serves cached app shell")
        finally:
            page.context.set_offline(False)
    except Exception as e:
        check(False, f"service worker offline shell: {str(e)[:160]}")

    # 7. settings: telemetry opt-in defaults to off and reports endpoint state
    page.goto(BASE + "/index.html#/settings", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#telemetryOptIn", timeout=15000)
        check(not page.locator("#telemetryOptIn").is_checked(), "telemetry opt-in defaults off")
        page.locator("#telemetryOptIn").check()
        check(
            "端点未配置" in page.locator("#telemetryStatus").inner_text(),
            "telemetry status explains missing endpoint",
        )
        page.locator("#telemetryOptIn").uncheck()
        check(not page.locator("#telemetryOptIn").is_checked(), "telemetry opt-in toggles off")
    except Exception as e:
        check(False, f"settings telemetry panel: {str(e)[:160]}")
    browser.close()

print()
if warns:
    print(f"WARN ({len(warns)}):")
    for w in warns:
        print(" -", w)
if failures:
    print(f"SMOKE FAILED: {len(failures)}")
    for item in failures:
        print(" -", item)
    sys.exit(1)
print("SMOKE PASSED")
