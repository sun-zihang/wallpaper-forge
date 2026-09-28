from __future__ import annotations


def build_clip_filter(clip: dict, input_index: int, output_index: int) -> str:
    filters: list[str] = []
    current = f"[{input_index}:v]"

    transform = clip["params"]["transform"]
    if transform.get("crop"):
        crop = transform["crop"]
        filters.append(
            f"{current}crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']}[c{output_index}]"
        )
        current = f"[c{output_index}]"

    if transform.get("scale") != 1.0:
        filters.append(
            f"{current}scale=iw*{transform['scale']}:ih*{transform['scale']}[s{output_index}]"
        )
        current = f"[s{output_index}]"

    rotation = transform.get("rotation", 0)
    flip_h = transform.get("flip_h", False)
    flip_v = transform.get("flip_v", False)
    if rotation or flip_h or flip_v:
        parts = []
        if rotation == 90:
            parts.append("transpose=1")
        elif rotation == 180:
            parts.append("transpose=2,transpose=2")
        elif rotation == 270:
            parts.append("transpose=2")
        if flip_h:
            parts.append("hflip")
        if flip_v:
            parts.append("vflip")
        filters.append(f"{current}{','.join(parts)}[r{output_index}]")
        current = f"[r{output_index}]"

    f = clip["params"]["filters"]
    color_parts = []
    if f.get("brightness", 0) != 0:
        color_parts.append(f"brightness={f['brightness']}")
    if f.get("contrast", 0) != 0:
        color_parts.append(f"contrast={1 + f['contrast']}")
    if f.get("saturation", 0) != 0:
        color_parts.append(f"saturation={1 + f['saturation']}")
    if f.get("hue", 0) != 0:
        color_parts.append(f"hue={f['hue']}")
    if f.get("grayscale"):
        color_parts.append("format=gray")
    if f.get("sepia"):
        color_parts.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
    if color_parts:
        filters.append(f"{current}{','.join(color_parts)}[col{output_index}]")
        current = f"[col{output_index}]"

    if f.get("blur", 0) > 0:
        filters.append(f"{current}gblur=sigma={f['blur']}[b{output_index}]")
        current = f"[b{output_index}]"
    if f.get("sharpen", 0) > 0:
        filters.append(f"{current}unsharp=5:5:{f['sharpen']}:5:5:0[sh{output_index}]")
        current = f"[sh{output_index}]"

    if clip["speed"] != 1.0:
        filters.append(f"{current}setpts=PTS/{clip['speed']}[v{output_index}]")
    else:
        filters.append(f"{current}copy[v{output_index}]")

    overlay = clip["params"].get("overlay")
    if overlay and overlay.get("type") == "text":
        text = overlay["text"].replace("'", "'\\''")
        x = f"(w-text_w)*{overlay['position']['x'] / 100}"
        y = f"(h-text_h)*{overlay['position']['y'] / 100}"
        filters.append(
            f"[v{output_index}]drawtext=text={text}:fontsize={overlay['fontSize']}"
            f":fontcolor={overlay['fontColor']}@{overlay['opacity']}:x={x}:y={y}[ov{output_index}]"
        )
        current = f"[ov{output_index}]"

    filters.append(f"{current}format=yuv420p[{output_index}:v]")
    return ";".join(filters)


def needs_processing(clip: dict) -> bool:
    p = clip["params"]
    t = p["transform"]
    f = p["filters"]
    return (
        clip["speed"] != 1.0
        or t["rotation"] != 0
        or t["flip_h"]
        or t["flip_v"]
        or t["scale"] != 1.0
        or t["crop"] is not None
        or f["brightness"] != 0
        or f["contrast"] != 0
        or f["saturation"] != 0
        or f["hue"] != 0
        or f["grayscale"]
        or f["sepia"]
        or f["blur"] > 0
        or f["sharpen"] > 0
        or p["overlay"] is not None
    )
