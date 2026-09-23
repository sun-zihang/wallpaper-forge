from __future__ import annotations

from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_QUALITY_EXTS = {".jpg", ".jpeg", ".webp"}


class ImageOpError(Exception):
    pass


def _open_rgba(src: Path) -> Image.Image:
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        raise ImageOpError(f"无法读取图片: {src.name}（{e}）") from e
    return im


def convert_image(
    src: Path,
    dst: Path,
    *,
    max_width: int | None = None,
    quality: int = 90,
) -> Path:
    ext = dst.suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    if ext not in IMAGE_EXTS:
        raise ImageOpError(f"不支持的输出格式: {dst.suffix}")
    im = _open_rgba(src)
    if max_width and max_width > 0 and im.width > max_width:
        ratio = max_width / im.width
        im = im.resize((max_width, max(1, round(im.height * ratio))), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    save_kw: dict = {}
    if ext in _QUALITY_EXTS:
        save_kw["quality"] = max(1, min(100, quality))
        save_kw["optimize"] = True
    if ext in {".jpg", ".jpeg"} and im.mode in {"RGBA", "P", "LA"}:
        im = im.convert("RGB")
    try:
        im.save(dst, **save_kw)
    except Exception as e:
        raise ImageOpError(f"保存失败: {dst.name}（{e}）") from e
    return dst
