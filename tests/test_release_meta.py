"""Release metadata must stay in lockstep with core/version.py.

Guards against shipping an installer whose filename/AppVersion, or a README
whose download links, point at a different version than the app reports.
"""

import re
from pathlib import Path

from core.version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_installer_iss_version_matches_core():
    iss = (ROOT / "build" / "installer.iss").read_text(encoding="utf-8")
    m = re.search(r'#define MyAppVersion "([^"]+)"', iss)
    assert m, "installer.iss is missing the MyAppVersion define"
    assert m.group(1) == __version__


def test_readme_links_current_release():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"releases/tag/v{__version__}" in readme
    assert f"WallpaperConverter-Setup-{__version__}.exe" in readme


def test_installer_ships_vendored_chinese_language():
    iss_path = ROOT / "build" / "installer.iss"
    iss = iss_path.read_text(encoding="utf-8")
    assert 'MessagesFile: "languages\\ChineseSimplified.isl"' in iss
    isl = iss_path.parent / "languages" / "ChineseSimplified.isl"
    assert isl.is_file(), "vendored ChineseSimplified.isl is missing"
    # Inno reads this; a UTF-8 BOM would break codepage 936 parsing.
    raw = isl.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert "LanguageCodePage=936" in raw.decode("utf-8")


def test_release_workflow_generates_and_ships_sha256sums():
    wf = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "SHA256SUMS.txt" in wf
    assert "Get-FileHash" in wf and "SHA256" in wf
    assert "build/Output/SHA256SUMS.txt" in wf
    # Draft path must attach both installer and checksum file.
    assert "gh release create" in wf and "$sums" in wf


def test_web_version_is_independent_semver():
    # web/version.js tracks the static site independently of the desktop app;
    # both must stay valid semver so release tooling can parse them.
    web = (ROOT / "web" / "version.js").read_text(encoding="utf-8")
    m = re.search(r'WEB_VERSION\s*=\s*"([^"]+)"', web)
    assert m, "web/version.js is missing WEB_VERSION"
    assert re.fullmatch(r"\d+\.\d+\.\d+", m.group(1)), m.group(1)
