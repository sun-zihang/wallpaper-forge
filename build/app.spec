# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH provided by PyInstaller

datas = []
ffmpeg = ROOT / "vendor" / "ffmpeg" / "ffmpeg.exe"
if ffmpeg.is_file():
    datas.append((str(ffmpeg), "."))

hidden = collect_submodules("PIL")

# Drop Qt Quick/Qml/Pdf/OpenGL software backend and duplicate ffmpeg DLLs
# pulled in by opencv/imageio (we ship vendor/ffmpeg ourselves).
_DROP_SUBSTR = (
    "imageio_ffmpeg",
    "opencv_videoio_ffmpeg",
    "opengl32sw",
    "Qt6Quick",
    "Qt6Qml",
    "Qt6Pdf",
    "Qt6OpenGL",
    "Qt63D",
    "d3dcompiler",
)


def _keep(name: str) -> bool:
    n = name.lower()
    return not any(s.lower() in n for s in _DROP_SUBSTR)


a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.QtPdf",
        "PySide6.QtQuickWidgets",
        "PySide6.Qt3DCore",
        "imageio_ffmpeg",
        "imageio",
    ],
    noarchive=False,
)

# Post-filter collected binaries/datas before PYZ/COLLECT.
a.binaries = [(n, p, f) for n, p, f in a.binaries if _keep(n)]
a.datas = [(n, p, f) for n, p, f in a.datas if _keep(n)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WallpaperConverter",
    icon=str(ROOT / "assets" / "app.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WallpaperConverter",
)
