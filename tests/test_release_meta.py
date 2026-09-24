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
