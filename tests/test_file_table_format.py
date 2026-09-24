from gui.widgets.file_table import _format_size


def test_format_size_kb_boundaries():
    assert _format_size(0) == "0 KB"
    assert _format_size(1023) == "1 KB"
    assert _format_size(1024) == "1 KB"
    assert _format_size(1024 * 1024 - 1) == "1024 KB"


def test_format_size_mb_and_negative_clamped():
    assert _format_size(1024 * 1024) == "1.0 MB"
    assert _format_size(1024 * 1024 * 5) == "5.0 MB"
    assert _format_size(-10) == "0 KB"
