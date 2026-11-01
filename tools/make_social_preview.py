#!/usr/bin/env python3
"""Render the repository's social preview: `assets/social-preview.png` and its SVG twin.

GitHub shows the social preview wherever the repository is linked, at roughly 400 pixels wide,
so the card carries one name, one sentence and three claims — anything else turns into grey
noise at that size. The terminal panel repeats output the tool actually prints, which is why it
can be believed.

    python tools/make_social_preview.py [--write]

One layout description, two renderers: the PNG is drawn with Pillow (the `png` extra), the SVG
carries the same coordinates so the pair cannot drift. Without Pillow the command exits 2 and
says why, like every other optional-dependency path in this pack.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 1280, 640

BG_TOP = (9, 13, 19)
BG_BOTTOM = (16, 23, 33)
PANEL = (17, 24, 35)
PANEL_EDGE = (38, 50, 66)
TEXT = (230, 237, 243)
MUTED = (139, 152, 165)
ACCENT = (79, 156, 249)
GREEN = (63, 185, 80)
AMBER = (210, 153, 34)

MONO = "C:/Windows/Fonts/consola.ttf"
MONO_LINUX = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SANS_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
SANS_BOLD_LINUX = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SANS = "C:/Windows/Fonts/segoeui.ttf"
SANS_LINUX = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@dataclass
class Element:
    """One drawing instruction, understood by both renderers."""

    kind: str                     # rect | line | text | dots
    box: tuple = ()               # rect: (x, y, w, h, radius)
    points: tuple = ()            # line: (x1, y1, x2, y2, width)
    text: str = ""
    at: tuple = ()                # text: (x, y)
    size: int = 16
    colour: tuple = TEXT
    font: str = "mono"            # mono | sans | sans-bold
    anchor: str = "start"
    fill: tuple | None = None     # rect fill; None means no fill


@dataclass
class Card:
    elements: list[Element] = field(default_factory=list)
    gradient: bool = True


def measure(font_path: str, size: int, text: str) -> float:
    from PIL import ImageFont
    for candidate in (font_path, SANS, SANS_LINUX):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size).getlength(text)
    return len(text) * size * 0.55


def wrap(text: str, font_path: str, size: int, limit: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or measure(font_path, size, candidate) <= limit:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def build() -> Card:
    card = Card()
    add = card.elements.append

    # Left column: identity, one sentence, three claims.
    x = 72
    add(Element("text", at=(x, 96), text="REPOSITORY & WIKI STEWARD", size=17,
                colour=ACCENT, font="mono"))
    add(Element("text", at=(x, 168), text="github-agent", size=74, colour=TEXT, font="mono"))
    add(Element("rect", box=(x, 196, 132, 6, 3), colour=ACCENT, fill=ACCENT))

    add(Element("text", at=(x, 248), text="One command per documentation job:", size=27,
                colour=TEXT, font="sans"))
    add(Element("text", at=(x, 288), text="audit  ·  lint  ·  changelog  ·  wiki  ·  images", size=22,
                colour=MUTED, font="mono"))

    bullets = [
        "README, CHANGELOG and community files — scored",
        "Markdown, links, anchors, tables, secrets — checked",
        "GitHub Wiki — built, verified, published",
    ]
    y = 356
    for bullet in bullets:
        add(Element("rect", box=(x, y - 10, 8, 8, 2), colour=GREEN, fill=GREEN))
        add(Element("text", at=(x + 24, y), text=bullet, size=20, colour=MUTED, font="sans"))
        y += 38

    # Right: a terminal panel with output the tool really prints.
    px, py, pw, ph = 672, 88, 536, 400
    add(Element("rect", box=(px, py, pw, ph, 16), colour=PANEL_EDGE, fill=PANEL))
    add(Element("dots", at=(px + 22, py + 20)))
    add(Element("line", points=(px, py + 46, px + pw, py + 46, 1), colour=PANEL_EDGE))

    lines = [
        ("$ ghagent audit . --min-score 85", ACCENT),
        ("* hygiene score: 100.0% (34 items scored)", MUTED),
        ("$ ghagent doc --root .", ACCENT),
        ("PASS: 0 error(s), 0 warning(s)", GREEN),
        ("$ ghagent changelog check", ACCENT),
        ("PASS: 0 error(s), 0 warning(s)", GREEN),
        ("$ ghagent wiki build && ghagent wiki verify", ACCENT),
        ("PASS: 0 error(s)", GREEN),
    ]
    y = py + 84
    for line, colour in lines:
        add(Element("text", at=(px + 28, y), text=line, size=17, colour=colour, font="mono"))
        y += 38

    # Bottom strip: what it costs to run, and where it lives.
    add(Element("line", points=(72, 548, 1208, 548, 1), colour=PANEL_EDGE))
    add(Element("text", at=(72, 596), text="Python 3.11+  ·  zero runtime dependencies  ·  MIT",
                size=19, colour=MUTED, font="mono"))
    add(Element("text", at=(1208, 596), text="github.com/paulmann/github-agent", size=19,
                colour=ACCENT, font="mono", anchor="end"))
    return card


# --------------------------------------------------------------------------
# renderers
# --------------------------------------------------------------------------

def _font_path(kind: str) -> str:
    if kind == "mono":
        return MONO if Path(MONO).exists() else MONO_LINUX
    if kind == "sans-bold":
        return SANS_BOLD if Path(SANS_BOLD).exists() else SANS_BOLD_LINUX
    return SANS if Path(SANS).exists() else SANS_LINUX


def render_png(card: Card) -> bytes:
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    draw = ImageDraw.Draw(image)
    for row in range(HEIGHT):
        ratio = row / (HEIGHT - 1)
        colour = tuple(round(a + (b - a) * ratio) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line([(0, row), (WIDTH, row)], fill=colour)

    for element in card.elements:
        if element.kind == "rect":
            x, y, w, h, radius = element.box
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                                   fill=element.fill, outline=element.colour, width=1)
        elif element.kind == "line":
            x1, y1, x2, y2, width = element.points
            draw.line([(x1, y1), (x2, y2)], fill=element.colour, width=width)
        elif element.kind == "dots":
            cx, cy = element.at
            for index, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
                draw.ellipse([cx + index * 22, cy - 6, cx + index * 22 + 12, cy + 6], fill=colour)
        elif element.kind == "text":
            font = ImageFont.truetype(_font_path(element.font), element.size)
            tx, ty = element.at
            if element.anchor == "end":
                tx -= font.getlength(element.text)
            draw.text((tx, ty), element.text, font=font, fill=element.colour, anchor="ls")

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _svg_colour(colour: tuple) -> str:
    return "#%02x%02x%02x" % colour


def render_svg(card: Card) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="github-agent — repository and wiki steward">',
        "  <defs>",
        '    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">',
        f'      <stop offset="0" stop-color="{_svg_colour(BG_TOP)}"/>',
        f'      <stop offset="1" stop-color="{_svg_colour(BG_BOTTOM)}"/>',
        "    </linearGradient>",
        "  </defs>",
        f'  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>',
        f'  <rect x="0" y="0" width="{WIDTH}" height="6" fill="{_svg_colour(ACCENT)}"/>',
    ]
    families = {"mono": "Consolas, 'DejaVu Sans Mono', monospace",
                "sans": "'Segoe UI', 'DejaVu Sans', sans-serif",
                "sans-bold": "'Segoe UI', 'DejaVu Sans', sans-serif"}
    for element in card.elements:
        if element.kind == "rect":
            x, y, w, h, radius = element.box
            fill = _svg_colour(element.fill) if element.fill else "none"
            parts.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                         f'fill="{fill}" stroke="{_svg_colour(element.colour)}" stroke-width="1"/>')
        elif element.kind == "line":
            x1, y1, x2, y2, width = element.points
            parts.append(f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                         f'stroke="{_svg_colour(element.colour)}" stroke-width="{width}"/>')
        elif element.kind == "dots":
            cx, cy = element.at
            for index, colour in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
                parts.append(f'  <circle cx="{cx + index * 22 + 6}" cy="{cy}" r="6" '
                             f'fill="{_svg_colour(colour)}"/>')
        elif element.kind == "text":
            x, y = element.at
            anchor = "end" if element.anchor == "end" else "start"
            parts.append(
                f'  <text x="{x}" y="{y}" font-family="{families[element.font]}" '
                f'font-size="{element.size}" fill="{_svg_colour(element.colour)}" '
                f'text-anchor="{anchor}">{_escape(element.text)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("*", ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the social preview")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    card = build()
    svg = render_svg(card)
    try:
        png = render_png(card)
    except ImportError:
        print('ghagent: Pillow is required to render the preview; install "github-agent-cli[png]"',
              file=sys.stderr)
        return 2

    png_path = ROOT / "assets" / "social-preview.png"
    svg_path = ROOT / "assets" / "social-preview.svg"
    print(f"png: {len(png)} bytes, svg: {len(svg)} bytes, {WIDTH}x{HEIGHT}")
    if not args.write:
        print("dry run; pass --write to replace the files under assets/")
        return 0
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(png)
    svg_path.write_text(svg, encoding="utf-8", newline="\n")
    print(f"written {png_path.relative_to(ROOT)} and {svg_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
