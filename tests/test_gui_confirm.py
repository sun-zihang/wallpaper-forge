from pathlib import Path

from core.tasks import would_overwrite_sources


def test_confirm_logic_count_only_sources(tmp_path: Path):
    # _confirm_overwrite 的核心是 would_overwrite_sources；
    # 文案拼接 n = len(pairs)（与 base.py 实现一致）
    a = tmp_path / "a.png"
    a.write_bytes(b"x")
    existing = tmp_path / "converted" / "a.jpg"
    pairs = would_overwrite_sources([a], [a])
    assert len(pairs) == 1
    pairs2 = would_overwrite_sources([a], [existing])
    assert pairs2 == []
