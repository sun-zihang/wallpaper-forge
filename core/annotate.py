from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.image_ops import ImageOpError, _open_rgba
from core.safeio import staged_dst

_POSITIONS = {
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "center",
}


def _paste_pos(
    canvas_w: int,
    canvas_h: int,
    mark_w: int,
    mark_h: int,
    position: str,
    margin: int,
) -> tuple[int, int]:
    if position not in _POSITIONS:
        raise ImageOpError(f"未知水印位置: {position}")
    if position == "top_left":
        return margin, margin
    if position == "top_right":
        return canvas_w - mark_w - margin, margin
    if position == "bottom_left":
        return margin, canvas_h - mark_h - margin
    if position == "bottom_right":
        return canvas_w - mark_w - margin, canvas_h - mark_h - margin
    return (canvas_w - mark_w) // 2, (canvas_h - mark_h) // 2


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "msyh.ttc", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def crop_image(src: Path, dst: Path, box: tuple[int, int, int, int]) -> Path:
    im = _open_rgba(src)
    left, top, right, bottom = box
    if not (0 <= left < right <= im.width and 0 <= top < bottom <= im.height):
        raise ImageOpError(f"裁剪区域无效: 必须在 0..{im.width} × 0..{im.height} 范围内")
    out = im.crop((left, top, right, bottom))
    dst.parent.mkdir(parents=True, exist_ok=True)
    fmt = Image.registered_extensions().get(dst.suffix.lower())
    with staged_dst(src, dst) as target:
        out.save(target, format=fmt)
    return dst


def add_text_watermark(
    src: Path,
    dst: Path,
    *,
    text: str,
    font_size: int = 32,
    color: tuple[int, int, int, int] = (255, 255, 255, 180),
    position: str = "bottom_right",
    margin: int = 16,
) -> Path:
    if not text:
        raise ImageOpError("水印文字不能为空")
    base = _open_rgba(src).convert("RGBA")
    font = _load_font(font_size)
    bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    x, y = _paste_pos(base.width, base.height, tw, th, position, margin)
    draw = ImageDraw.Draw(layer)
    draw.text((x - bbox[0], y - bbox[1]), text, font=font, fill=color)
    out = Image.alpha_composite(base, layer)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fmt = Image.registered_extensions().get(dst.suffix.lower())
    with staged_dst(src, dst) as target:
        out.save(target, format=fmt)
    return dst


def add_image_watermark(
    src: Path,
    dst: Path,
    *,
    mark: Path,
    scale: float = 0.2,
    position: str = "bottom_right",
    margin: int = 16,
    opacity: float = 0.8,
) -> Path:
    if not 0.05 <= scale <= 1.0:
        raise ImageOpError("水印缩放比例需在 0.05–1.0 之间")
    if not 0.0 <= opacity <= 1.0:
        raise ImageOpError("透明度需在 0–1 之间")
    base = _open_rgba(src).convert("RGBA")
    mark_im = _open_rgba(mark).convert("RGBA")
    mw = max(1, round(base.width * scale))
    mh = max(1, round(mark_im.height * (mw / mark_im.width)))
    mark_im = mark_im.resize((mw, mh), Image.LANCZOS)
    if opacity < 1.0:
        alpha = mark_im.getchannel("A").point(lambda a: int(a * opacity))
        mark_im.putalpha(alpha)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    x, y = _paste_pos(base.width, base.height, mw, mh, position, margin)
    layer.paste(mark_im, (x, y), mark_im)
    out = Image.alpha_composite(base, layer)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fmt = Image.registered_extensions().get(dst.suffix.lower())
    with staged_dst(src, dst) as target:
        out.save(target, format=fmt)
    return dst
