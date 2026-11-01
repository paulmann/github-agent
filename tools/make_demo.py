#!/usr/bin/env python3
"""Render `assets/demo.gif` from real command output.

The README opens with an animation, and an animation that is drawn by hand goes stale the first
time a command changes. This script runs three commands against this checkout, takes their real
summary lines and renders them as a terminal window, one line per frame, so the picture cannot
say anything the tool did not print.

    python tools/make_demo.py [--write]

Needs Pillow (the `png` extra). Without it the script explains itself and exits 2.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "demo.gif"

WIDTH = 1000
PAD = 28
LINE_HEIGHT = 30
FONT_SIZE = 18
TOP = 58          # the traffic-light row
BOTTOM = 44

BG = (13, 17, 23)
PANEL = (22, 27, 34)
LINE = (48, 54, 61)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT = (88, 166, 255)
GOOD = (63, 185, 80)
WARN = (210, 153, 34)

COMMANDS = [
    ["audit", ".", "--min-score", "80"],
    ["doc", "--root", "."],
    ["changelog", "check"],
]

# Only lines the tool actually printed, and only the ones a reader can check: the verdict and
# the two counts behind it. A wall of table rows proves nothing in a 1280-pixel card.
KEEP_PREFIXES = ("* hygiene score", "* findings", "PASS:", "WARN:", "FAIL:")


def run_lines(command: list[str]) -> list[str]:
    """Run one ghagent command and return the lines worth showing."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ghagent.py"), *command],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    body = [line.rstrip() for line in proc.stdout.splitlines() if line.strip()]
    kept = [line for line in body if line.startswith(KEEP_PREFIXES)][-3:]
    return [f"$ ghagent {' '.join(command)}", *kept]


def readme_banner_lines() -> list[str]:
    return ["github-agent — repository and wiki steward", ""]


def colour_for(line: str) -> tuple[int, int, int]:
    if line.startswith("$"):
        return ACCENT
    if line.startswith(("PASS", "score: 100", "PASS:")):
        return GOOD
    if line.startswith(("FAIL", "WARN")):
        return WARN
    return TEXT


def font(size: int):
    from PIL import ImageFont
    for candidate in ("C:/Windows/Fonts/consola.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def frame(lines: list[str], shown: int, height: int):
    """One animation frame: the first `shown` lines of the transcript."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([PAD, PAD, WIDTH - PAD, height - PAD], radius=14, fill=PANEL, outline=LINE)
    for index, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        draw.ellipse([PAD + 20 + index * 22, PAD + 18, PAD + 32 + index * 22, PAD + 30], fill=colour)
    mono = font(FONT_SIZE)
    y = PAD + TOP
    for line in lines[:shown]:
        draw.text((PAD + 26, y), line[:88], font=mono, fill=colour_for(line))
        y += LINE_HEIGHT
    return image


def build(write: bool) -> int:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("ghagent: Pillow is required to render the demo; install \"github-agent-cli[png]\"",
              file=sys.stderr)
        return 2

    lines = readme_banner_lines()
    for command in COMMANDS:
        lines.extend(run_lines(command))
        lines.append("")
    height = PAD + TOP + len(lines) * LINE_HEIGHT + BOTTOM

    frames = [frame(lines, shown, height) for shown in range(1, len(lines) + 1)]
    frames.append(frame(lines, len(lines), height))     # a beat on the finished output

    buffer = io.BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:],
                   duration=[110] * (len(frames) - 1) + [2600], loop=0, optimize=True)
    data = buffer.getvalue()
    print(f"frames: {len(frames)}, size: {len(data)} bytes, lines: {len(lines)}, {WIDTH}x{height}")
    if not write:
        print("ghagent: dry run; pass --write to replace assets/demo.gif")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    print(f"written {OUT.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the README demo animation")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if not shutil.which(sys.executable):        # pragma: no cover - defensive
        print("ghagent: no interpreter", file=sys.stderr)
        return 2
    return build(args.write)


if __name__ == "__main__":
    sys.exit(main())
