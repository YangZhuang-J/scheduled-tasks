"""跨平台中文字体探测，避免回测图表在 macOS/Linux 上出现方框。"""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

from matplotlib import font_manager


_WINDOWS_FONTS = ("Microsoft YaHei", "SimHei", "SimSun")
_MACOS_FONTS = ("PingFang SC", "Hiragino Sans GB", "Heiti SC", "Songti SC")
_LINUX_FONTS = (
    "Noto Sans CJK SC",
    "Noto Sans CJK CN",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
)
_FALLBACK_FONTS = ("Arial Unicode MS",) + _WINDOWS_FONTS + _MACOS_FONTS + _LINUX_FONTS


def _normalise(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _ordered_candidates() -> tuple[str, ...]:
    system = platform.system()
    if system == "Darwin":
        return _MACOS_FONTS + _LINUX_FONTS + _WINDOWS_FONTS + _FALLBACK_FONTS
    if system == "Windows":
        return _WINDOWS_FONTS + _MACOS_FONTS + _LINUX_FONTS + _FALLBACK_FONTS
    return _LINUX_FONTS + _MACOS_FONTS + _WINDOWS_FONTS + _FALLBACK_FONTS


def _set_font(plt_module: Any, name: str) -> str:
    plt_module.rcParams["font.sans-serif"] = [name]
    plt_module.rcParams["font.family"] = "sans-serif"
    plt_module.rcParams["axes.unicode_minus"] = False
    return name


def _macos_font_paths() -> Iterable[Path]:
    # PingFang/Hiragino are commonly installed as TTC collections and may not
    # be returned by findSystemFonts(fontext="ttf") on older Matplotlib builds.
    return (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/STHeiti Light.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/STSong.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path.home() / "Library/Fonts/Arial Unicode.ttf",
    )


def configure_chinese_font(plt_module: Any) -> Optional[str]:
    """选择当前机器可用的中文字体，并关闭负号乱码。"""

    candidates = _ordered_candidates()
    targets = {_normalise(name) for name in candidates}
    available = {
        _normalise(entry.name): entry.name
        for entry in font_manager.fontManager.ttflist
        if getattr(entry, "name", None)
    }
    for candidate in candidates:
        matched = available.get(_normalise(candidate))
        if matched:
            return _set_font(plt_module, matched)

    paths = []
    for ext in ("ttf", "otf"):
        try:
            paths.extend(font_manager.findSystemFonts(fontext=ext))
        except TypeError:
            paths.extend(font_manager.findSystemFonts())
    if platform.system() == "Darwin":
        paths.extend(str(path) for path in _macos_font_paths())

    seen = set()
    for raw_path in paths:
        path = str(raw_path)
        if path in seen or not Path(path).exists():
            continue
        seen.add(path)
        try:
            name = font_manager.FontProperties(fname=path).get_name()
        except Exception:
            continue
        if _normalise(name) not in targets:
            continue
        try:
            font_manager.fontManager.addfont(path)
        except Exception:
            continue
        return _set_font(plt_module, name)

    # Keep the chart usable when the host has no CJK font, while making the
    # missing dependency visible instead of silently claiming success.
    _set_font(plt_module, "DejaVu Sans")
    print(
        "警告：未检测到可用中文字体，回测图表中的中文可能显示为方框；"
        "请在系统中安装 Noto Sans CJK、思源黑体或苹方。",
        file=sys.stderr,
    )
    return None
