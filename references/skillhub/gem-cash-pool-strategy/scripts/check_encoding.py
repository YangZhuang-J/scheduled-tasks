"""Validate source text encoding before installing or packaging this skill."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RELATIVE_PATHS = [
    "SKILL.md",
    "CHANGELOG.md",
    "config/strategy.json",
    "references/backtest.md",
    "references/params.md",
    "references/rules.md",
    "references/signals.md",
    "scripts/cash_pool_backtest.py",
    "scripts/data_client.py",
    "scripts/params.py",
    "scripts/check_env.py",
    "scripts/check_encoding.py",
]
SOURCE_PATHS = [ROOT / path for path in EXPECTED_RELATIVE_PATHS]
FORBIDDEN_KEY_FILES = [ROOT / ".env", ROOT / ".env.example"]
SUSPICIOUS_TEXT = (
    chr(0xFFFD),
    "\u951f\u65a4\u62f7",
    "\u00ef\u00bf\u00bd",
    chr(0xFFFD) * 3,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    errors = []
    checked = 0
    for path in FORBIDDEN_KEY_FILES:
        if path.exists():
            errors.append("forbidden Key file: %s" % path.relative_to(ROOT))
    for path in SOURCE_PATHS:
        if not path.is_file():
            errors.append("missing: %s" % path.relative_to(ROOT))
            continue
        rel = path.relative_to(ROOT)
        if any(ord(ch) > 127 for ch in rel.as_posix()):
            errors.append("non-ASCII package path: %s" % rel)
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append("UTF-8 BOM is not allowed in source file: %s" % rel)
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            errors.append("invalid UTF-8: %s (%s)" % (rel, exc))
            continue
        for marker in SUSPICIOUS_TEXT:
            if marker in text:
                errors.append("suspicious mojibake marker %r in %s" % (marker, rel))
        checked += 1

    skill = ROOT / "SKILL.md"
    if skill.is_file() and not skill.read_bytes().startswith(b"---"):
        errors.append("SKILL.md must start with YAML frontmatter at byte 0")

    if errors:
        print("Encoding validation failed:")
        for error in errors:
            print("- " + error)
        return 1
    print("Encoding validation passed: %d UTF-8 source files." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
