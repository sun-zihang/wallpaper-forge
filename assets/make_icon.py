from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT_ICO = ROOT / "assets" / "app.ico"
OUT_PNG = ROOT / "assets" / "app_preview.png"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient_bg(size: int) -> Image.Image:
    # Diagonal brand gradient: indigo -> sky -> cyan
    c0 = (67, 56, 202)   # indigo-700
    c1 = (37, 99, 235)   # blue-600
    c2 = (8, 145, 178)   # cyan-700
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / max(1, 2 * (size - 1))
            if t < 0.55:
                col = _lerp(c0, c1, t / 0.55)
            else:
                col = _lerp(c1, c2, (t - 0.55) / 0.45)
            # soft corner vignette-ish highlight top-left
            hl = max(0.0, 1.0 - ((x + y) / max(1.0, float(size) * 1.4)))
            col = _lerp(col, (255, 255, 255), hl * 0.08)
            px[x, y] = (*col, 255)
    return img


def _rounded_mask(size: int, radius_frac: float = 0.22) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    r = int(size * radius_frac)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=255)
    return mask


def _draw_landscape(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], scale: float) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 3:
        return
    # sky already white-ish frame; draw hills
    hill_c = (16, 185, 129) if scale > 0.35 else (5, 150, 105)
    hill2 = (5, 110, 80)
    # back hill
    d.polygon(
        [
            (x0, y1),
            (x0 + int(w * 0.15), y0 + int(h * 0.45)),
            (x0 + int(w * 0.45), y0 + int(h * 0.2)),
            (x0 + int(w * 0.75), y0 + int(h * 0.55)),
            (x1, y0 + int(h * 0.35)),
            (x1, y1),
        ],
        fill=hill_c,
    )
    # front hill
    d.polygon(
        [
            (x0, y1),
            (x0 + int(w * 0.25), y0 + int(h * 0.65)),
            (x0 + int(w * 0.55), y0 + int(h * 0.4)),
            (x0 + int(w * 0.9), y0 + int(h * 0.7)),
            (x1, y1),
        ],
        fill=hill2,
    )
    # sun
    sr = max(1, int(h * 0.12))
    sx = x0 + int(w * 0.72)
    sy = y0 + int(h * 0.28)
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(253, 224, 71))


def _draw_card(
    img: Image.Image,
    box: tuple[int, int, int, int],
    *,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    radius: int,
    landscape: bool,
    scale: float,
) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=max(1, int(radius * 0.12)))
    if landscape:
        pad = max(1, int((x1 - x0) * 0.12))
        _draw_landscape(d, (x0 + pad, y0 + pad, x1 - pad, y1 - pad), scale)
    img.alpha_composite(layer)


def _arc_arrow(
    d: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    r: int,
    width: int,
    start: float,
    end: float,
    color: tuple[int, int, int, int],
) -> None:
    d.arc((cx - r, cy - r, cx + r, cy + r), start=start, end=end, fill=color, width=width)


def _arrow_head(
    d: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    r: int,
    angle_deg: float,
    size: int,
    color: tuple[int, int, int, int],
) -> None:
    import math

    a = math.radians(angle_deg)
    tip_x = cx + int(r * math.cos(a))
    tip_y = cy + int(r * math.sin(a))
    # tangent direction
    tx, ty = -math.sin(a), math.cos(a)
    # outward normal
    nx, ny = math.cos(a), math.sin(a)
    left = (tip_x - int(size * tx) + int(size * 0.35 * nx), tip_y - int(size * ty) + int(size * 0.35 * ny))
    right = (tip_x - int(size * tx) - int(size * 0.35 * nx), tip_y - int(size * ty) - int(size * 0.35 * ny))
    d.polygon([ (tip_x, tip_y), left, right ], fill=color)


def make_icon(size: int) -> Image.Image:
    base = _gradient_bg(size)
    mask = _rounded_mask(size, 0.22)
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg.paste(base, (0, 0), mask)

    # Geometry
    margin = max(2, int(size * 0.14))
    # back card (offset up-left)
    s = size
    back = (
        margin + int(s * 0.06),
        margin,
        s - margin - int(s * 0.18),
        s - margin - int(s * 0.22),
    )
    front = (
        margin + int(s * 0.22),
        margin + int(s * 0.16),
        s - margin,
        s - margin - int(s * 0.08),
    )

    _draw_card(
        bg,
        back,
        fill=(255, 255, 255, 70),
        outline=(255, 255, 255, 160),
        radius=max(2, int(s * 0.06)),
        landscape=False,
        scale=size / 256,
    )
    _draw_card(
        bg,
        front,
        fill=(255, 255, 255, 245),
        outline=(255, 255, 255, 255),
        radius=max(2, int(s * 0.07)),
        landscape=True,
        scale=size / 256,
    )

    # Convert cycle arrows at bottom-right badge
    d = ImageDraw.Draw(bg)
    badge_r = max(int(s * 0.16), 6)
    bcx = s - margin - badge_r // 2 - max(1, int(s * 0.02))
    bcy = s - margin - badge_r // 2 - max(1, int(s * 0.02))
    # clamp inside
    bcx = min(bcx, s - badge_r - 1)
    bcy = min(bcy, s - badge_r - 1)

    # badge plate
    plate = int(badge_r * 1.85)
    d.rounded_rectangle(
        (bcx - plate // 2, bcy - plate // 2, bcx + plate // 2, bcy + plate // 2),
        radius=max(2, plate // 4),
        fill=(15, 23, 42, 235),
    )

    white = (255, 255, 255, 255)
    lw = max(2, int(s * 0.035))
    ar = max(3, int(badge_r * 0.55))
    if size >= 24:
        _arc_arrow(d, bcx, bcy, ar, lw, start=200, end=340, color=white)
        _arc_arrow(d, bcx, bcy, ar, lw, start=20, end=160, color=white)
        import math

        # arrow heads at arc ends
        # end of first arc at 200 deg screen coords: angle from +x, PIL y down so use degrees
        def head(angle: float) -> None:
            a = math.radians(angle)
            tipx = bcx + int(ar * math.cos(a))
            tipy = bcy + int(ar * math.sin(a))
            # direction of arc motion (increasing angle): tangent (-sin, cos) but y-down
            tx, ty = -math.sin(a), math.cos(a)
            hs = max(3, int(s * 0.05))
            p1 = (tipx + int(hs * math.cos(a)), tipy + int(hs * math.sin(a)))
            p2 = (tipx - int(hs * ty * 0.7) + int(hs * tx * 0.5), tipy - int(hs * (-tx) * 0.7) + int(hs * ty * 0.5))
            # simpler perpendicular base
            px, py = -ty, tx
            b1 = (tipx + int(hs * tx) + int(hs * 0.55 * px), tipy + int(hs * ty) + int(hs * 0.55 * py))
            b2 = (tipx + int(hs * tx) - int(hs * 0.55 * px), tipy + int(hs * ty) - int(hs * 0.55 * py))
            d.polygon([(tipx, tipy), b1, b2], fill=white)

        # heads where arcs end (angle 340 and 160 in PIL arc coords)
        a_end1 = 20  # actually put head at end of drawn arc going cw
        # Arc from 200 to 340: ends at 340
        head(340)
        # Arc 20 to 160: ends at 160
        head(160)
    else:
        # tiny: single chevron pair
        d.line((bcx - ar, bcy, bcx + ar, bcy), fill=white, width=max(1, lw // 2))
        d.polygon(
            [(bcx + ar, bcy), (bcx + ar - lw, bcy - lw), (bcx + ar - lw, bcy + lw)],
            fill=white,
        )

    return bg


def main() -> None:
    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)
    # Pillow embeds multiple sizes by resizing the primary image.
    # Feed it the largest render so quality stays high at 256.
    big = make_icon(max(SIZES))
    big.save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
    )
    make_icon(256).save(OUT_PNG)
    print("wrote", OUT_ICO, "and", OUT_PNG)
    check = Image.open(OUT_ICO)
    print("ico sizes", sorted(check.info.get("sizes") or []))


if __name__ == "__main__":
    main()
