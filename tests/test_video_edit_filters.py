from gui.video_edit.filters import build_clip_filter, needs_processing
from gui.video_edit.model import Clip, create_default_params


def make_clip_dict(**overrides):
    clip = Clip(
        id=overrides.pop("id", "c1"),
        source_file=overrides.pop("source_file", "a.mp4"),
        timeline_in=overrides.pop("timeline_in", 0),
        source_in=overrides.pop("source_in", 0),
        source_out=overrides.pop("source_out", 10),
        speed=overrides.pop("speed", 1.0),
        params=create_default_params(),
    )
    for key, value in overrides.items():
        setattr(clip, key, value)
    return clip.to_dict()


def make_overlay(text="ab"):
    return {
        "type": "text",
        "text": text,
        "position": {"x": 0, "y": 0},
        "fontSize": 12,
        "fontColor": "#000000",
        "opacity": 1.0,
    }


def test_identity_filter():
    d = make_clip_dict()
    assert build_clip_filter(d, 0, 0) == "[0:v]copy[v0];[0:v]format=yuv420p[0:v]"


def test_crop_filter():
    d = make_clip_dict()
    d["params"]["transform"]["crop"] = {"x": 1, "y": 2, "width": 100, "height": 50}
    assert build_clip_filter(d, 0, 0) == (
        "[0:v]crop=100:50:1:2[c0];[c0]copy[v0];[c0]format=yuv420p[0:v]"
    )


def test_scale_filter():
    d = make_clip_dict()
    d["params"]["transform"]["scale"] = 1.5
    assert build_clip_filter(d, 0, 0) == (
        "[0:v]scale=iw*1.5:ih*1.5[s0];[s0]copy[v0];[s0]format=yuv420p[0:v]"
    )


def test_rotation_filters():
    d = make_clip_dict()
    d["params"]["transform"]["rotation"] = 90
    assert "transpose=1[r0]" in build_clip_filter(d, 0, 0)
    d["params"]["transform"]["rotation"] = 180
    assert "transpose=2,transpose=2[r0]" in build_clip_filter(d, 0, 0)
    d["params"]["transform"]["rotation"] = 270
    assert "transpose=2[r0]" in build_clip_filter(d, 0, 0)


def test_flip_filters():
    d = make_clip_dict()
    d["params"]["transform"]["flip_h"] = True
    d["params"]["transform"]["flip_v"] = True
    assert "hflip,vflip[r0]" in build_clip_filter(d, 0, 0)


def test_color_filters():
    d = make_clip_dict()
    d["params"]["filters"].update(brightness=0.2, contrast=0.1, saturation=0.3, hue=10)
    assert "brightness=0.2,contrast=1.1,saturation=1.3,hue=10[col0]" in build_clip_filter(d, 0, 0)


def test_grayscale_filter():
    d = make_clip_dict()
    d["params"]["filters"]["grayscale"] = True
    assert "format=gray[col0]" in build_clip_filter(d, 0, 0)


def test_sepia_filter():
    d = make_clip_dict()
    d["params"]["filters"]["sepia"] = True
    assert (
        "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131[col0]"
        in build_clip_filter(d, 0, 0)
    )


def test_blur_sharpen_filters():
    d = make_clip_dict()
    d["params"]["filters"]["blur"] = 2
    assert "gblur=sigma=2[b0]" in build_clip_filter(d, 0, 0)
    d = make_clip_dict()
    d["params"]["filters"]["sharpen"] = 1.5
    assert "unsharp=5:5:1.5:5:5:0[sh0]" in build_clip_filter(d, 0, 0)


def test_speed_filter():
    d = make_clip_dict(speed=2.0)
    assert "setpts=PTS/2.0[v0]" in build_clip_filter(d, 0, 0)


def test_overlay_text_filter_escapes_quotes():
    d = make_clip_dict()
    d["params"]["overlay"] = make_overlay("你好 '世界'")
    f = build_clip_filter(d, 0, 0)
    assert "drawtext=text=你好 '\\''世界'\\''" in f
    assert "fontsize=12:fontcolor=#000000@1.0:x=(w-text_w)*0.0:y=(h-text_h)*0.0[ov0]" in f


def test_full_pipeline_order():
    d = make_clip_dict(speed=2.0)
    d["params"]["transform"]["crop"] = {"x": 0, "y": 0, "width": 640, "height": 360}
    d["params"]["transform"]["rotation"] = 90
    d["params"]["transform"]["flip_h"] = True
    d["params"]["transform"]["scale"] = 0.5
    d["params"]["filters"].update(brightness=0.1, blur=1.5)
    d["params"]["overlay"] = make_overlay()
    assert build_clip_filter(d, 0, 0) == (
        "[0:v]crop=640:360:0:0[c0];"
        "[c0]scale=iw*0.5:ih*0.5[s0];"
        "[s0]transpose=1,hflip[r0];"
        "[r0]brightness=0.1[col0];"
        "[col0]gblur=sigma=1.5[b0];"
        "[b0]setpts=PTS/2.0[v0];"
        "[v0]drawtext=text=ab:fontsize=12:fontcolor=#000000@1.0:x=(w-text_w)*0.0:y=(h-text_h)*0.0[ov0];"
        "[ov0]format=yuv420p[0:v]"
    )


def test_needs_processing_default_false():
    assert needs_processing(make_clip_dict()) is False


def test_needs_processing_speed():
    assert needs_processing(make_clip_dict(speed=2.0)) is True


def test_needs_processing_transform():
    for key, value in [("rotation", 90), ("flip_h", True), ("flip_v", True), ("scale", 2.0)]:
        d = make_clip_dict()
        d["params"]["transform"][key] = value
        assert needs_processing(d) is True
    d = make_clip_dict()
    d["params"]["transform"]["crop"] = {"x": 0, "y": 0, "width": 10, "height": 10}
    assert needs_processing(d) is True


def test_needs_processing_filters():
    for key, value in [
        ("brightness", 0.1),
        ("contrast", 0.1),
        ("saturation", 0.1),
        ("hue", 10),
        ("blur", 1),
        ("sharpen", 1),
    ]:
        d = make_clip_dict()
        d["params"]["filters"][key] = value
        assert needs_processing(d) is True
    d = make_clip_dict()
    d["params"]["filters"]["grayscale"] = True
    assert needs_processing(d) is True
    d = make_clip_dict()
    d["params"]["filters"]["sepia"] = True
    assert needs_processing(d) is True


def test_needs_processing_overlay():
    d = make_clip_dict()
    d["params"]["overlay"] = make_overlay()
    assert needs_processing(d) is True
