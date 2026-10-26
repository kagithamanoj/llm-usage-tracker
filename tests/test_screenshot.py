"""Tests pinning the README screenshot to a real image file."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_readme_links_screenshot():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    assert "docs/screenshot.png" in readme


def test_screenshot_is_a_real_png():
    path = os.path.join(ROOT, "docs", "screenshot.png")
    with open(path, "rb") as fh:
        header = fh.read(8)
        body = fh.read()
    assert header == b"\x89PNG\r\n\x1a\n"
    assert len(body) > 1000
