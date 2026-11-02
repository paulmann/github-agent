"""Repository imagery: the designed social preview, rendered locally and then checked.

Why this exists. A repository with no picture reads as abandoned, and the reference
project's README opens with a 1280x640 banner. The image is easy to forget and easy to
break, so it is generated from the repository's own metadata and then verified:

  * the social preview must be PNG/JPG/GIF under 1 MB, at least 640x320, 1280x640 for
    best display (GitHub documentation, "Customizing your repository's social media preview");
  * an SVG is a fine README banner but cannot be uploaded as a social preview;
  * a reference to a missing file renders as a broken box, so every referenced image is
    resolved against the tree.

One layout description, two renderers. `build_card` turns a `BannerSpec` into a `Card` — a flat
list of drawing instructions on a 1280x640 canvas — and the PNG (Pillow) and the SVG (standard
library) draw exactly that list. The pair cannot drift, because there is nothing to drift: the
coordinates are computed once. The layout follows the reference card the user chose: a dark
vertical gradient, an accent rule, an eyebrow, a monospace wordmark whose first letter carries
the accent colour, a bold summary and a muted tagline, a row of fact pills, a terminal panel with
traffic-light dots and real command output, and a footer that puts the repository on the left and
the homepage on the right.

Nothing is invented. Auto facts come only from what the tree proves — a manifest, a LICENSE, a
wiki manifest, the test suite, file extensions — and a fact that cannot be measured is omitted,
not guessed. Terminal output comes only from `--output`/`--output-line`; the command may be
derived from a manifest's declared console script, and the report names the source when it is.

Rendering uses Pillow when it is installed (PNG), and always writes an SVG, which needs
nothing at all. A missing Pillow lowers the output format, never the honesty of the report.
"""

from __future__ import annotations

import json
import os
import re
import struct
import zlib
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from . import config as cfg
from . import meta as meta_module
from .util import (
    IMAGE_RE,
    Report,
    git,
    guess_repo_slug,
    read_text,
    rel,
    scan_structure,
    visible_dirs,
)

SOCIAL_SIZE = (1280, 640)
SOCIAL_MIN = (640, 320)
SOCIAL_MAX_BYTES = 1_000_000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif"}
SOCIAL_ACCEPTED = {".png", ".jpg", ".jpeg", ".gif"}
# An emoji in an H1 is fine on GitHub and unreadable on a rendered card: the font set has
# no colour glyphs, so it lands as a box or disappears. The banner strips it.
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2b00-\u2bff\uFE0F]"
)

# The design palette. One source for both renderers; the accent is per-card.
PALETTE = {
    "bg_top": "#0b1220",
    "panel": "#0a1018",
    "panel_edge": "#22303f",
    "pill": "#141d29",
    "pill_edge": "#2a3848",
    "text": "#e6edf3",
    "muted": "#96a4b2",
    "accent": "#4f9cf9",
    "green": "#3fb950",
    "amber": "#d29922",
    "red": "#f85149",
}
TRAFFIC_LIGHTS = ((255, 95, 86), (255, 189, 46), (39, 201, 63))
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_FACTS = 6
BASE_WIDTH = SOCIAL_SIZE[0]
BASE_MARGIN = 48
TRANSLATION_RE = re.compile(r"\.(ru|de|es|hi|zh|fr|pt|ja|ko|it)\.md$", re.IGNORECASE)

# Layout, in base 1280x640 pixels. `build_card` scales the horizontal axis when `--size` asks
# for another width, and anchors the panel and the footer to the bottom edge.
EYEBROW_BASELINE = 84
WORDMARK_BASELINE = 172
SUMMARY_BASELINE = 242
SUMMARY_LEADING = 38
SUMMARY_MAX_LINES = 2
TAGLINE_LEADING = 30
TAGLINE_MAX_LINES = 2
PILL_HEIGHT = 36
PILL_GAP = 12
PILL_PADDING = 18
# A monospace space cell is a full em: at display size it reads as a double space, which is why
# a multi-word wordmark is laid out word by word with this designed gap instead of the font's
# space glyph. The glyphs stay monospace; only the gap between words is tightened.
WORD_GAP_RATIO = 0.35
PANEL_HEADER_RULE = 44
PANEL_FIRST_LINE = 70
PANEL_LINE_HEIGHT = 27
PANEL_BOTTOM_OFFSET = 70
FOOTER_BASELINE_OFFSET = 34


# --------------------------------------------------------------------------
# colour and font helpers
# --------------------------------------------------------------------------

def _hex_to_rgb(value: str, fallback: str = PALETTE["accent"]) -> tuple[int, int, int]:
    text = value if HEX_RE.match(value or "") else fallback
    return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)


def _rgb_to_hex(colour: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % colour


def _mix(first: tuple[int, int, int], second: tuple[int, int, int],
         ratio: float) -> tuple[int, int, int]:
    ratio = max(0.0, min(1.0, ratio))
    return (
        round(first[0] + (second[0] - first[0]) * ratio),
        round(first[1] + (second[1] - first[1]) * ratio),
        round(first[2] + (second[2] - first[2]) * ratio),
    )


FONT_DIRS = ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu")
FONT_CANDIDATES = {
    "mono": ("consola.ttf", "DejaVuSansMono.ttf"),
    "mono-bold": ("consolab.ttf", "DejaVuSansMono-Bold.ttf"),
    "sans": ("segoeui.ttf", "DejaVuSans.ttf"),
    "sans-bold": ("segoeuib.ttf", "DejaVuSans-Bold.ttf"),
}
FONT_FAMILIES = {
    "mono": "Consolas, 'DejaVu Sans Mono', monospace",
    "mono-bold": "Consolas, 'DejaVu Sans Mono', monospace",
    "sans": "'Segoe UI', 'DejaVu Sans', sans-serif",
    "sans-bold": "'Segoe UI', 'DejaVu Sans', sans-serif",
}
# Average advance as a fraction of the font size, used only when no TrueType font is present.
WIDTH_ESTIMATE = {"mono": 0.60, "mono-bold": 0.60, "sans": 0.52, "sans-bold": 0.54}


def _font_path(kind: str) -> str:
    for directory in FONT_DIRS:
        for name in FONT_CANDIDATES.get(kind, FONT_CANDIDATES["sans"]):
            candidate = Path(directory) / name
            if candidate.exists():
                return str(candidate)
    return ""


@lru_cache(maxsize=128)
def _pil_font(kind: str, size: int) -> Any:
    """A Pillow font, or None when Pillow is unavailable. Cached per (kind, size)."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    path = _font_path(kind)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except (OSError, TypeError):
        return None


def text_width(kind: str, size: int, text: str) -> float:
    """Advance width of `text`, measured with the real font when Pillow is present."""
    font = _pil_font(kind, size)
    if font is not None:
        try:
            return float(font.getlength(text))
        except AttributeError:  # pragma: no cover - a bitmap fallback font without getlength
            pass
    return len(text) * size * WIDTH_ESTIMATE.get(kind, 0.55)


# --------------------------------------------------------------------------
# image metadata without dependencies
# --------------------------------------------------------------------------

def image_size(path: Path) -> tuple[int, int] | None:
    """Read width/height from the file header. Pure stdlib, no decoding."""
    try:
        raw = Path(path).read_bytes()[:64]
    except OSError:
        return None
    if raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR":
        width, height = struct.unpack(">II", raw[16:24])
        return int(width), int(height)
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        width, height = struct.unpack("<HH", raw[6:10])
        return int(width), int(height)
    if raw[:2] == b"\xff\xd8":                     # JPEG: walk the marker chain
        try:
            data = Path(path).read_bytes()
        except OSError:
            return None
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return int(width), int(height)
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = struct.unpack(">H", data[index + 2:index + 4])[0]
            index += 2 + length
        return None
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return None                                # not needed for the rules below
    return None


def make_header_png(width: int, height: int) -> bytes:
    """A structurally valid PNG with an IHDR of the given size (used by the self-tests)."""
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# --------------------------------------------------------------------------
# one layout description, two renderers
# --------------------------------------------------------------------------

@dataclass
class Element:
    """One drawing instruction, understood by both renderers."""

    kind: str                     # rect | line | circle | dots | text | duo | wordmark
    box: tuple = ()               # rect: (x, y, w, h, radius)
    points: tuple = ()            # line: (x1, y1, x2, y2, width)
    at: tuple = ()                # text/duo: (x, y); circle: (cx, cy); dots: (x, y)
    text: str = ""
    size: int = 16
    colour: tuple = (0, 0, 0)
    font: str = "mono"            # mono | mono-bold | sans | sans-bold
    anchor: str = "start"         # start | end
    fill: tuple | None = None     # None means no fill
    split: int = 1                # duo: characters drawn in `prefix_colour`
    prefix_colour: tuple = (0, 0, 0)


@dataclass
class Card:
    elements: list[Element] = field(default_factory=list)
    width: int = SOCIAL_SIZE[0]
    height: int = SOCIAL_SIZE[1]
    top_colour: tuple = (11, 18, 32)
    bottom_colour: tuple = (24, 46, 75)
    accent: tuple = (79, 156, 249)
    aria: str = ""
    facts: list[str] = field(default_factory=list)
    omitted_facts: list[str] = field(default_factory=list)
    terminal_rows: int = 0
    omitted_lines: int = 0
    truncated: list[str] = field(default_factory=list)


@dataclass
class BannerSpec:
    title: str
    eyebrow: str = ""
    summary: str = ""
    tagline: str = ""
    command: str = ""
    outputs: list[str] = field(default_factory=list)
    facts: list[tuple[str, str]] = field(default_factory=list)   # (label, value) -> "Value Label"
    chips: list[str] = field(default_factory=list)               # legacy textual pills
    footer_left: str = ""
    footer_right: str = ""
    footer: str = ""               # legacy single footer, used as the right slot
    license: str = ""
    accent: str = PALETTE["accent"]
    command_source: str = ""
    fact_sources: dict[str, str] = field(default_factory=dict)
    width: int = SOCIAL_SIZE[0]
    height: int = SOCIAL_SIZE[1]

    def normalised(self) -> "BannerSpec":
        self.title = self.title.strip()
        self.eyebrow = self.eyebrow.strip()
        self.summary = self.summary.strip()
        self.tagline = self.tagline.strip()
        self.command = self.command.strip()
        self.footer_left = self.footer_left.strip()
        self.footer_right = self.footer_right.strip()
        self.footer = self.footer.strip()
        self.outputs = [line.strip() for line in self.outputs if line and line.strip()]
        self.facts = [(str(label).strip(), str(value).strip())
                      for label, value in self.facts if str(label).strip() or str(value).strip()]
        self.chips = [chip.strip() for chip in self.chips if chip and chip.strip()]
        self.accent = self.accent if HEX_RE.match(self.accent or "") else PALETTE["accent"]
        return self


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _cut_to_width(text: str, kind: str, size: int, limit: float, suffix: str = "…") -> str:
    """Shorten `text` until it fits `limit`, keeping the caller able to report the cut."""
    if text_width(kind, size, text) <= limit:
        return text
    trimmed = text
    while trimmed and text_width(kind, size, trimmed + suffix) > limit:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip(" .,;:-") + suffix) if trimmed else suffix


def _wrap(text: str, kind: str, size: int, limit: float, max_lines: int) -> tuple[list[str], bool]:
    """Wrap into at most `max_lines` lines; a cut is marked with an ellipsis and reported."""
    words = text.split()
    if not words:
        return [], False
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or text_width(kind, size, candidate) <= limit:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    cut = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        cut = True
    if lines and text_width(kind, size, lines[-1]) > limit:
        lines[-1] = _cut_to_width(lines[-1], kind, size, limit)
        cut = True
    if cut and lines:
        lines[-1] = lines[-1].rstrip(" .,;:-") + "…"
    return lines, cut


def fact_text(label: str, value: str) -> str:
    """How a `Label=Value` fact reads on the card: the value first, like `40 tools`."""
    label, value = label.strip(), value.strip()
    if label and value:
        return f"{value} {label}"
    return value or label


def _terminal_style(line: str) -> str:
    lowered = line.strip().lower()
    if lowered.startswith(("fail", "error", "traceback", "exception")):
        return "error"
    if lowered.startswith(("pass", "ok", "→", "written", "built", "done")):
        return "success"
    return "output"


def _display_url(value: str) -> str:
    text = re.sub(r"^https?://", "", (value or "").strip(), flags=re.IGNORECASE)
    return text.rstrip("/")


def wordmark_layout(text: str, kind: str, size: int) -> list[tuple[str, int]]:
    """Words of a wordmark and their x offset from the wordmark origin.

    The remainder of a word starts at the measured width of everything before it plus exactly one
    designed gap, so the space between words can never be counted twice. Both renderers read this
    one layout, so the PNG and the SVG place the same word on the same pixel.
    """
    words = [word for word in text.split(" ") if word]
    gap = size * WORD_GAP_RATIO
    layout: list[tuple[str, int]] = []
    cursor = 0.0
    for word in words:
        layout.append((word, int(round(cursor))))
        cursor += text_width(kind, size, word) + gap
    return layout


def wordmark_width(text: str, kind: str, size: int) -> float:
    layout = wordmark_layout(text, kind, size)
    if not layout:
        return 0.0
    word, offset = layout[-1]
    return offset + text_width(kind, size, word)


def _cut_wordmark_to_width(text: str, kind: str, size: int, limit: float, suffix: str = "…") -> str:
    """Shorten a wordmark until its designed layout fits, keeping the caller able to report it."""
    if wordmark_width(text, kind, size) <= limit:
        return text
    trimmed = text
    while trimmed and wordmark_width(trimmed + suffix, kind, size) > limit:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip(" .,;:-") + suffix) if trimmed else suffix


def _shift_elements_down(elements: list[Element], delta: int) -> None:
    """Move a finished block down the canvas, used to centre a card that has no terminal panel."""
    if delta <= 0:
        return
    for element in elements:
        if element.kind == "rect":
            x, y, width, height, radius = element.box
            element.box = (x, y + delta, width, height, radius)
        else:
            x, y = element.at
            element.at = (x, y + delta)


def build_card(spec: BannerSpec) -> Card:
    """Turn a spec into drawing instructions. PNG and SVG read only this list."""
    spec = spec.normalised()
    width, height = spec.width, spec.height
    scale = width / BASE_WIDTH if width != BASE_WIDTH else 1.0

    def s(value: float) -> int:
        return max(1, round(value * scale))

    margin = s(BASE_MARGIN)
    available = width - 2 * margin
    accent = _hex_to_rgb(spec.accent)
    top_colour = _hex_to_rgb(PALETTE["bg_top"])
    bottom_colour = _mix(top_colour, accent, 0.24)
    text_colour = _hex_to_rgb(PALETTE["text"])
    muted = _hex_to_rgb(PALETTE["muted"])
    green = _hex_to_rgb(PALETTE["green"])
    red = _hex_to_rgb(PALETTE["red"])

    card = Card(width=width, height=height, top_colour=top_colour, bottom_colour=bottom_colour,
                accent=accent)
    add = card.elements.append
    upper: list[Element] = []          # identity block; centred when the card has no panel
    add_upper = upper.append
    aria = spec.title if not (spec.summary or spec.tagline) else f"{spec.title} — {spec.summary or spec.tagline}"
    card.aria = _escape(aria[:300])

    title = spec.title or "project"
    add(Element("rect", box=(0, 0, width, s(5), 0), colour=accent, fill=accent))

    # Eyebrow: the small accent line above the wordmark.
    cursor = s(EYEBROW_BASELINE)
    if spec.eyebrow:
        lines, cut = _wrap(spec.eyebrow, "mono", s(17), available, 1)
        add_upper(Element("text", at=(margin, cursor), text=lines[0], size=s(17), colour=accent,
                          font="mono"))
        if cut:
            card.truncated.append("eyebrow")

    # Wordmark: monospace, the first letter in the accent colour, words laid out by one layout.
    wordmark_size = s(76)
    while wordmark_size > s(34) and wordmark_width(title, "mono-bold", wordmark_size) > available:
        wordmark_size = max(s(34), round(wordmark_size * 0.9))
    if wordmark_width(title, "mono-bold", wordmark_size) > available:
        title = _cut_wordmark_to_width(title, "mono-bold", wordmark_size, available)
        card.truncated.append("title")
    add_upper(Element("wordmark", at=(margin, s(WORDMARK_BASELINE)), text=title,
                      size=wordmark_size, colour=text_colour, font="mono-bold",
                      prefix_colour=accent))
    cursor = s(WORDMARK_BASELINE)

    # Bold summary, then the muted tagline.
    if spec.summary:
        lines, cut = _wrap(spec.summary, "sans-bold", s(30), available, SUMMARY_MAX_LINES)
        for index, line in enumerate(lines):
            add_upper(Element("text", at=(margin, s(SUMMARY_BASELINE) + index * s(SUMMARY_LEADING)),
                              text=line, size=s(30), colour=text_colour, font="sans-bold"))
        cursor = s(SUMMARY_BASELINE) + (len(lines) - 1) * s(SUMMARY_LEADING)
        if cut:
            card.truncated.append("summary")

    if spec.tagline:
        tagline_base = cursor + s(62)
        lines, cut = _wrap(spec.tagline, "sans", s(20), available, TAGLINE_MAX_LINES)
        for index, line in enumerate(lines):
            add_upper(Element("text", at=(margin, tagline_base + index * s(TAGLINE_LEADING)),
                              text=line, size=s(20), colour=muted, font="sans"))
        cursor = tagline_base + (len(lines) - 1) * s(TAGLINE_LEADING)
        if cut:
            card.truncated.append("tagline")

    # Fact pills: one row, value-first, capped at MAX_FACTS and at the row width.
    entries = [fact_text(label, value) for label, value in spec.facts] + list(spec.chips)
    pill_top = cursor + s(26)
    pill_font = s(18)
    pill_x = margin
    pill_kept = 0
    for text in entries:
        text = text.strip()
        if not text:
            continue
        if pill_kept >= MAX_FACTS:
            card.omitted_facts.append(text)
            continue
        display = _cut_to_width(text, "sans", pill_font, available, suffix="…")
        pill_width = int(text_width("sans", pill_font, display)) + 2 * s(PILL_PADDING)
        if pill_x + pill_width > margin + available:
            card.omitted_facts.append(text)
            continue
        add_upper(Element("rect", box=(pill_x, pill_top, pill_width, s(PILL_HEIGHT),
                                       s(PILL_HEIGHT) // 2),
                          colour=_hex_to_rgb(PALETTE["pill_edge"]), fill=_hex_to_rgb(PALETTE["pill"])))
        add_upper(Element("text", at=(pill_x + s(PILL_PADDING),
                                      pill_top + s(PILL_HEIGHT) // 2 + s(6)),
                          text=display, size=pill_font, colour=_hex_to_rgb(PALETTE["muted"]),
                          font="sans"))
        card.facts.append(display)
        pill_x += pill_width + s(PILL_GAP)
        pill_kept += 1
    pills_bottom = pill_top + s(PILL_HEIGHT) if pill_kept else pill_top

    # Terminal content: only the command and the output lines the caller supplied.
    raw_lines: list[str] = []
    if spec.command:
        raw_lines.append("$ " + spec.command.lstrip("$ ").strip())
    raw_lines.extend(spec.outputs)
    line_size = s(17)
    text_area = available - s(56)
    rows: list[tuple[str, str]] = []
    for line in raw_lines:
        prompt = line.startswith("$ ")
        body = line[2:].strip() if prompt else line.strip()
        wrapped, cut = _wrap(body, "mono", line_size, text_area - (s(20) if prompt else 0), 40)
        if not wrapped:
            continue
        if prompt:
            rows.append(("prompt", "$ " + wrapped[0]))
            rows.extend(("output", "  " + part) for part in wrapped[1:])
        else:
            style = _terminal_style(body)
            rows.append((style, wrapped[0]))
            rows.extend(("output", "  " + part) for part in wrapped[1:])
        if cut:
            card.truncated.append("terminal")

    if rows:
        # A full-width terminal panel: header with the traffic lights, then the real lines.
        panel_bottom = height - s(PANEL_BOTTOM_OFFSET)
        panel_top = pills_bottom + s(12) if pill_kept else cursor + s(28)
        panel_top = max(panel_top, s(300))
        panel_left = margin
        card.elements.extend(upper)
        add(Element("rect", box=(panel_left, panel_top, available, panel_bottom - panel_top, s(16)),
                    colour=_hex_to_rgb(PALETTE["panel_edge"]), fill=_hex_to_rgb(PALETTE["panel"])))
        add(Element("dots", at=(panel_left + s(20), panel_top + s(22))))
        add(Element("line", points=(panel_left, panel_top + s(PANEL_HEADER_RULE),
                                    panel_left + available, panel_top + s(PANEL_HEADER_RULE), 1),
                    colour=_hex_to_rgb(PALETTE["panel_edge"])))
        header_right = _display_url(spec.footer_right) or _display_url(spec.footer_left) or "local"
        header = _cut_to_width(f"{title} · {header_right}", "mono", s(15), available - s(120))
        add(Element("text", at=(panel_left + s(96), panel_top + s(27)), text=header, size=s(15),
                    colour=muted, font="mono"))
        first_line = panel_top + s(PANEL_FIRST_LINE)
        line_height = s(PANEL_LINE_HEIGHT)
        max_rows = max(0, int((panel_bottom - s(10) - first_line) // line_height) + 1)
        if len(rows) > max_rows:
            card.omitted_lines = len(rows) - max_rows
            rows = rows[:max_rows]
        card.terminal_rows = len(rows)
        line_colours = {"success": green, "error": red}
        for index, (style, line) in enumerate(rows):
            at = (panel_left + s(28), first_line + index * line_height)
            if style == "prompt":
                add(Element("duo", at=at, text=line, size=line_size, colour=text_colour,
                            font="mono", split=2, prefix_colour=accent))
            else:
                add(Element("text", at=at, text=line, size=line_size,
                            colour=line_colours.get(style, muted), font="mono"))
    else:
        # No command and no output: an empty terminal box looks unfinished, so the panel is
        # omitted and the identity block is centred between the top rule and the footer.
        block_top = (s(EYEBROW_BASELINE) - s(18)) if spec.eyebrow else (s(WORDMARK_BASELINE) - wordmark_size)
        block_bottom = pills_bottom if pill_kept else cursor + s(14)
        region_top = s(44)
        region_bottom = height - s(FOOTER_BASELINE_OFFSET) - s(26)
        delta = round(max(0.0, region_top
                          + (region_bottom - region_top - (block_bottom - block_top)) / 2
                          - block_top))
        _shift_elements_down(upper, delta)
        card.elements.extend(upper)

    # Footer: the repository on the left, the homepage with a status dot on the right.
    footer_y = height - s(FOOTER_BASELINE_OFFSET)
    footer_left = spec.footer_left
    footer_right = spec.footer_right or spec.footer
    footer_font = s(19)
    if footer_left:
        add(Element("text", at=(margin, footer_y), text=footer_left, size=footer_font,
                    colour=text_colour, font="sans-bold"))
    if footer_right:
        right_width = text_width("sans-bold", footer_font, footer_right)
        add(Element("text", at=(width - margin, footer_y), text=footer_right, size=footer_font,
                    colour=text_colour, font="sans-bold", anchor="end"))
        add(Element("circle", at=(width - margin - right_width - s(18), footer_y - s(7)),
                    size=s(5), colour=green, fill=green))
    return card


def render_card_png(card: Card) -> bytes | None:
    """PNG bytes, or None when Pillow is not installed."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    def s(value: float) -> int:
        return max(1, round(value * card.width / BASE_WIDTH))

    # The gradient is built at 1x32 and upscaled: a per-pixel Python loop over 1280x640
    # pixels is far slower for a result no eye can tell apart from the interpolated one.
    small = Image.new("RGB", (1, 32))
    small_pixels = small.load()
    assert small_pixels is not None
    for row in range(32):
        ratio = row / 31
        small_pixels[0, row] = _mix(card.top_colour, card.bottom_colour, ratio)
    image = small.resize((card.width, card.height), Image.Resampling.BILINEAR)
    draw = ImageDraw.Draw(image)

    for element in card.elements:
        if element.kind == "rect":
            x, y, w, h, radius = element.box
            if radius:
                draw.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                                       fill=element.fill, outline=element.colour, width=1)
            else:
                draw.rectangle([x, y, x + w, y + h], fill=element.fill, outline=element.colour)
        elif element.kind == "line":
            x1, y1, x2, y2, thickness = element.points
            draw.line([(x1, y1), (x2, y2)], fill=element.colour, width=thickness)
        elif element.kind == "circle":
            cx, cy = element.at
            radius = element.size
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                         fill=element.fill or element.colour, outline=element.colour)
        elif element.kind == "dots":
            cx, cy = element.at
            radius = max(3, s(6))
            spacing = max(8, s(22))
            for index, colour in enumerate(TRAFFIC_LIGHTS):
                left = cx + index * spacing
                draw.ellipse([left - radius, cy - radius, left + radius, cy + radius], fill=colour)
        elif element.kind in ("text", "duo", "wordmark"):
            font = _pil_font(element.font, element.size)
            if font is None:  # pragma: no cover - Pillow is present whenever this runs
                continue
            x, y = element.at
            if element.kind == "text":
                if element.anchor == "end":
                    x -= font.getlength(element.text)
                draw.text((x, y), element.text, font=font, fill=element.colour, anchor="ls")
            elif element.kind == "duo":
                split = max(0, min(len(element.text), element.split))
                prefix, rest = element.text[:split], element.text[split:]
                draw.text((x, y), prefix, font=font, fill=element.prefix_colour, anchor="ls")
                draw.text((x + font.getlength(prefix), y), rest, font=font, fill=element.colour,
                          anchor="ls")
            else:
                # One layout for the PNG and the SVG: each word starts where the measured width
                # of everything before it ends, plus exactly one designed gap.
                for index, (word, offset) in enumerate(
                        wordmark_layout(element.text, element.font, element.size)):
                    word_x = x + offset
                    if index == 0:
                        split = min(1, len(word))
                        draw.text((word_x, y), word[:split], font=font, fill=element.prefix_colour,
                                  anchor="ls")
                        draw.text((word_x + font.getlength(word[:split]), y), word[split:],
                                  font=font, fill=element.colour, anchor="ls")
                    else:
                        draw.text((word_x, y), word, font=font, fill=element.colour, anchor="ls")

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_card_svg(card: Card) -> str:
    """The vector twin: same instructions, same coordinates, standard library only."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{card.width}" height="{card.height}" '
        f'viewBox="0 0 {card.width} {card.height}" role="img" aria-label="{_escape(card.aria)}">',
        "  <defs>",
        '    <linearGradient id="background" x1="0" y1="0" x2="0" y2="1">',
        f'      <stop offset="0" stop-color="{_rgb_to_hex(card.top_colour)}"/>',
        f'      <stop offset="1" stop-color="{_rgb_to_hex(card.bottom_colour)}"/>',
        "    </linearGradient>",
        "  </defs>",
        f'  <rect width="{card.width}" height="{card.height}" fill="url(#background)"/>',
    ]
    for element in card.elements:
        if element.kind == "rect":
            x, y, w, h, radius = element.box
            fill = _rgb_to_hex(element.fill) if element.fill else "none"
            parts.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                         f'fill="{fill}" stroke="{_rgb_to_hex(element.colour)}" stroke-width="1"/>')
        elif element.kind == "line":
            x1, y1, x2, y2, thickness = element.points
            parts.append(f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                         f'stroke="{_rgb_to_hex(element.colour)}" stroke-width="{thickness}"/>')
        elif element.kind == "circle":
            cx, cy = element.at
            parts.append(f'  <circle cx="{cx}" cy="{cy}" r="{element.size}" '
                         f'fill="{_rgb_to_hex(element.fill or element.colour)}"/>')
        elif element.kind == "dots":
            cx, cy = element.at
            scale = card.width / BASE_WIDTH
            radius = max(3, round(6 * scale))
            spacing = max(8, round(22 * scale))
            for index, colour in enumerate(TRAFFIC_LIGHTS):
                parts.append(f'  <circle cx="{cx + index * spacing}" cy="{cy}" r="{radius}" '
                             f'fill="{_rgb_to_hex(colour)}"/>')
        elif element.kind in ("text", "duo", "wordmark"):
            x, y = element.at
            anchor = "end" if element.anchor == "end" else "start"
            family = FONT_FAMILIES.get(element.font, FONT_FAMILIES["sans"])
            weight = ' font-weight="700"' if element.font.endswith("-bold") else ""
            if element.kind == "text":
                parts.append(
                    f'  <text x="{x}" y="{y}" font-family="{family}" font-size="{element.size}"'
                    f'{weight} fill="{_rgb_to_hex(element.colour)}" text-anchor="{anchor}">'
                    f'{_escape(element.text)}</text>')
            elif element.kind == "duo":
                split = max(0, min(len(element.text), element.split))
                parts.append(
                    f'  <text x="{x}" y="{y}" font-family="{family}" font-size="{element.size}"'
                    f'{weight} fill="{_rgb_to_hex(element.colour)}" text-anchor="{anchor}">'
                    f'<tspan fill="{_rgb_to_hex(element.prefix_colour)}">'
                    f'{_escape(element.text[:split])}</tspan>'
                    f'{_escape(element.text[split:])}</text>')
            else:
                # One text run, one wordmark layout: each word carries the absolute x the PNG
                # draws it at, so the twin cannot drift and a word gap cannot be counted twice.
                spans: list[str] = []
                for index, (word, offset) in enumerate(
                        wordmark_layout(element.text, element.font, element.size)):
                    if index == 0:
                        split = min(1, len(word))
                        spans.append(
                            f'<tspan x="{x + offset}"><tspan '
                            f'fill="{_rgb_to_hex(element.prefix_colour)}">'
                            f'{_escape(word[:split])}</tspan>{_escape(word[split:])}</tspan>')
                    else:
                        spans.append(f'<tspan x="{x + offset}">{_escape(word)}</tspan>')
                parts.append(
                    f'  <text x="{x}" y="{y}" font-family="{family}" font-size="{element.size}"'
                    f'{weight} fill="{_rgb_to_hex(element.colour)}" text-anchor="{anchor}">'
                    f'{"".join(spans)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_svg(spec: BannerSpec) -> str:
    """Kept for callers of the first renderer; the card is the layout authority now."""
    return render_card_svg(build_card(spec))


def render_png(spec: BannerSpec) -> bytes | None:
    """Kept for callers of the first renderer; the card is the layout authority now."""
    return render_card_png(build_card(spec))


# --------------------------------------------------------------------------
# measurable facts
# --------------------------------------------------------------------------

LANGUAGE_BY_SUFFIX = dict(meta_module.LANGUAGE_BY_SUFFIX)


def _walk_files(root: Path) -> list[Path]:
    """Every file the documentation walk may enter, build output and tool state excluded."""
    excluded = cfg.load(Path(root)).exclude_dirs
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = visible_dirs(dirnames, excluded)
        for name in sorted(filenames):
            files.append(Path(dirpath) / name)
    return files


def _toml_block(text: str, table: str) -> str:
    match = re.search(rf"(?ms)^\[{re.escape(table)}\]\s*(.*?)(?=^\[|\Z)", text)
    return match.group(1) if match else ""


def _toml_string(block: str, key: str) -> str:
    match = re.search(rf'(?m)^{re.escape(key)}\s*=\s*"([^"]*)"', block)
    return match.group(1).strip() if match else ""


def _first_table_key(block: str) -> str:
    match = re.search(r"(?m)^([A-Za-z0-9_.-]+)\s*=", block)
    return match.group(1).strip() if match else ""


def _same_url(first: str, second: str) -> bool:
    return bool(first) and bool(second) and _display_url(first).lower() == _display_url(second).lower()


def _manifest_info(root: Path) -> dict[str, str]:
    """What the manifests declare: description, homepage, repository, console script."""
    info = {"title": "", "description": "", "homepage": "", "repo_url": "", "script": "",
            "script_source": ""}
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text, _ = read_text(pyproject)
        project = _toml_block(text, "project")
        info["description"] = _toml_string(project, "description")
        urls = _toml_block(text, "project.urls")
        info["homepage"] = _toml_string(urls, "Homepage")
        info["repo_url"] = _toml_string(urls, "Repository") or _toml_string(urls, "Source")
        script = _first_table_key(_toml_block(text, "project.scripts"))
        if script:
            info["script"] = script
            info["script_source"] = "pyproject.toml [project.scripts]"
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(read_text(package)[0])
        except json.JSONDecodeError:
            data = {}
        info["description"] = info["description"] or str(data.get("description") or "")
        info["homepage"] = info["homepage"] or str(data.get("homepage") or "")
        repository = data.get("repository")
        if isinstance(repository, dict):
            repository = repository.get("url")
        info["repo_url"] = info["repo_url"] or (str(repository) if repository else "")
        binaries = data.get("bin")
        if isinstance(binaries, dict) and binaries and not info["script"]:
            info["script"] = str(next(iter(binaries)))
            info["script_source"] = "package.json bin"
    composer = root / "composer.json"
    if composer.exists():
        try:
            data = json.loads(read_text(composer)[0])
        except json.JSONDecodeError:
            data = {}
        info["description"] = info["description"] or str(data.get("description") or "")
        info["homepage"] = info["homepage"] or str(data.get("homepage") or "")
        if not info["script"] and data.get("bin"):
            binaries = data["bin"]
            if isinstance(binaries, dict) and binaries:
                info["script"] = str(next(iter(binaries)))
                info["script_source"] = "composer.json bin"
    citation = root / "CITATION.cff"
    if citation.exists():
        text, _ = read_text(citation)
        title = re.search(r'(?m)^title:\s*"?([^"\n]+)"?', text)
        if title:
            info["title"] = title.group(1).strip()
        code = re.search(r'(?m)^repository-code:\s*"?([^"\n]+)"?', text)
        if code:
            info["repo_url"] = info["repo_url"] or code.group(1).strip()
    return info


def _readme_summary(text: str) -> str:
    """The first paragraph after the H1: the sentence the project uses to describe itself."""
    headings, _, _, lines = scan_structure(text)
    h1 = [heading for heading in headings if heading.level == 1]
    start = h1[0].line if h1 else 0
    paragraph: list[str] = []
    for raw in lines[start:]:
        stripped = raw.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", "<!--", "<", "![", "|", "```", ">", "[![", "**Read this in")):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
        if len(paragraph) >= 4:
            break
    return " ".join(paragraph).strip()


def _repository_metadata(root: Path) -> dict[str, str]:
    root = Path(root)
    config = cfg.load(root)
    facts = meta_module.derive(root)
    manifest = _manifest_info(root)
    summary = ""
    readme = config.path(config.readme)
    if readme.exists():
        summary = _readme_summary(read_text(readme)[0])
    title = str(facts.get("title") or "") or manifest["title"]
    description = manifest["description"]
    resolved_summary = summary or description or str(facts.get("summary") or "")
    tagline = description if description and not _same_url(description, resolved_summary) \
        and description.strip() != resolved_summary.strip() else ""
    repo_url = manifest["repo_url"]
    if not repo_url:
        slug = guess_repo_slug(root)
        if slug:
            repo_url = f"https://github.com/{slug[0]}/{slug[1]}"
    homepage = manifest["homepage"]
    if _same_url(homepage, repo_url):
        homepage = ""   # the right footer slot repeats the left one unless it is another site
    command = f"{manifest['script']} --help" if manifest["script"] else ""
    return {
        "title": title,
        "summary": resolved_summary,
        "tagline": tagline,
        "repo_url": repo_url,
        "homepage": homepage,
        "command": command,
        "command_source": manifest["script_source"] if command else "",
    }


def _detect_version(root: Path) -> tuple[str, str] | None:
    """The version the tree declares. Manifests first, a local tag last; nothing is guessed."""
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text, _ = read_text(pyproject)
        project = _toml_block(text, "project")
        version = _toml_string(project, "version")
        if version:
            return version, "pyproject.toml [project].version"
        hatch = _toml_block(text, "tool.hatch.version")
        path = _toml_string(hatch, "path")
        pattern_match = re.search(r"(?m)^pattern\s*=\s*(['\"])(.+)\1\s*$", hatch)
        if path and pattern_match:
            pattern = pattern_match.group(2)
            source = root / path
            if source.exists():
                found = re.search(pattern, read_text(source)[0], re.MULTILINE)
                if found:
                    value = ""
                    if "version" in found.groupdict():
                        value = found.group("version")
                    elif found.groups():
                        value = found.group(1)
                    if value:
                        return value, f"{path} (declared by pyproject.toml [tool.hatch.version])"
        poetry = _toml_block(text, "tool.poetry")
        version = _toml_string(poetry, "version")
        if version:
            return version, "pyproject.toml [tool.poetry].version"
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(read_text(package)[0])
        except json.JSONDecodeError:
            data = {}
        if data.get("version"):
            return str(data["version"]), "package.json version"
    citation = root / "CITATION.cff"
    if citation.exists():
        match = re.search(r'(?m)^version:\s*"?([^"\n]+)"?', read_text(citation)[0])
        if match:
            return match.group(1).strip(), "CITATION.cff version"
    version_file = root / "VERSION"
    if version_file.exists():
        first = read_text(version_file)[0].splitlines()
        if first and first[0].strip():
            return first[0].strip(), "VERSION first line"
    rc, out, _ = git(["describe", "--tags", "--abbrev=0"], root)
    if rc == 0 and out.strip():
        tag = out.strip().lstrip("v")
        if re.match(r"^\d+\.\d+", tag):
            return tag, "git tag on HEAD"
    return None


SPDX_PATTERNS = (
    (r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", None),
    (r"MIT License", "MIT"),
    (r"Apache License", "Apache-2.0"),
    (r"GNU General Public License\s+Version 3", "GPL-3.0"),
    (r"GNU General Public License\s+Version 2", "GPL-2.0"),
    (r"GNU Lesser General Public License", "LGPL-3.0"),
    (r"BSD 3-Clause", "BSD-3-Clause"),
    (r"BSD 2-Clause", "BSD-2-Clause"),
    (r"Mozilla Public License", "MPL-2.0"),
    (r"\bISC License\b", "ISC"),
    (r"The Unlicense", "Unlicense"),
    (r"CC0", "CC0-1.0"),
)


def _normalise_license(value: str) -> str:
    text = value.strip().strip('"')
    if not text:
        return ""
    match = re.match(r"(?i)^(MIT|ISC|Unlicense|BSD-[23]-Clause|Apache-2\.0|MPL-2\.0|"
                     r"GPL-[23]\.0|LGPL-[23]\.0|CC0-1\.0|AGPL-3\.0)$", text)
    if match:
        return match.group(1)
    if text.lower().startswith("mit"):
        return "MIT"
    return text


def _detect_license(root: Path) -> tuple[str, str] | None:
    """SPDX id from the manifest, else the LICENSE text; nothing is assumed."""
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text, _ = read_text(pyproject)
        project = _toml_block(text, "project")
        quoted = _toml_string(project, "license")
        if quoted:
            return _normalise_license(quoted), "pyproject.toml [project].license"
        table = re.search(r'(?m)^license\s*=\s*\{\s*text\s*=\s*"([^"]+)"', project)
        if table:
            return _normalise_license(table.group(1)), "pyproject.toml [project].license"
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(read_text(package)[0])
        except json.JSONDecodeError:
            data = {}
        if isinstance(data.get("license"), str) and data["license"].strip():
            return _normalise_license(str(data["license"])), "package.json license"
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"):
        candidate = root / name
        if not candidate.exists():
            continue
        try:
            head = "\n".join(read_text(candidate)[0].splitlines()[:40])
        except ValueError:
            continue
        for pattern, spdx in SPDX_PATTERNS:
            match = re.search(pattern, head, re.IGNORECASE)
            if match:
                value = match.group(1) if spdx is None else spdx
                return _normalise_license(value), f"{name} text"
    return None


def _detect_dependencies(root: Path) -> tuple[int, str] | None:
    """Runtime dependency count, only when a manifest actually declares the field."""
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        project = _toml_block(read_text(pyproject)[0], "project")
        match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", project)
        if match:
            body = match.group(1)
            names = re.findall(r'"([^"]+)"', body) + re.findall(r"'([^']+)'", body)
            return len([name for name in names if name.strip()]), "pyproject.toml [project].dependencies"
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(read_text(package)[0])
        except json.JSONDecodeError:
            data = {}
        dependencies = data.get("dependencies")
        if isinstance(dependencies, dict):
            return len(dependencies), "package.json dependencies"
    return None


def _detect_docs_pages(root: Path) -> tuple[int, str] | None:
    docs_dir = root / cfg.load(root).docs_dir
    if not docs_dir.is_dir():
        return None
    pages = [path for path in docs_dir.rglob("*.md") if not TRANSLATION_RE.search(path.name)]
    if not pages:
        return None
    return len(pages), f"{cfg.load(root).docs_dir}/**/*.md (translations excluded)"


def _detect_wiki_pages(root: Path) -> tuple[int, str] | None:
    config = cfg.load(root)
    manifest = config.path(config.wiki_manifest)
    if manifest.exists():
        try:
            data = json.loads(read_text(manifest)[0])
        except json.JSONDecodeError:
            data = {}
        pages = sum(len(group.get("pages", [])) for group in data.get("groups", [])
                    if isinstance(group, dict))
        if pages:
            return pages, f"{config.wiki_manifest} entries"
    wiki_dir = config.path(config.wiki_dir)
    if wiki_dir.is_dir():
        page_files = [path for path in wiki_dir.glob("*.md") if not path.name.startswith("_")]
        if page_files:
            return len(page_files), f"{config.wiki_dir}/*.md"
    return None


def _detect_tests(root: Path) -> tuple[int, str] | None:
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return None
    count = 0
    for path in tests_dir.rglob("*.py"):
        try:
            text = read_text(path)[0]
        except ValueError:
            continue
        count += len(re.findall(r"(?m)^\s*def (test_\w+)", text))
    if not count:
        return None
    return count, "tests/**/*.py test functions"


def derive_facts(root: Path) -> list[tuple[str, str, str]]:
    """Facts the tree proves: (label, value, source). An unmeasurable fact is omitted."""
    root = Path(root)
    facts: list[tuple[str, str, str]] = []
    files = _walk_files(root) if root.is_dir() else []
    suffixes = Counter(path.suffix.lower() for path in files)

    version = _detect_version(root)
    if version:
        facts.append(("version", version[0], version[1]))
    license_info = _detect_license(root)
    if license_info:
        facts.append(("license", license_info[0], license_info[1]))
    dependencies = _detect_dependencies(root)
    if dependencies:
        label = "runtime dep" if dependencies[0] == 1 else "runtime deps"
        facts.append((label, str(dependencies[0]), dependencies[1]))
    tests = _detect_tests(root)
    if tests:
        facts.append(("test function" if tests[0] == 1 else "test functions", str(tests[0]), tests[1]))
    wiki = _detect_wiki_pages(root)
    if wiki:
        facts.append(("wiki page" if wiki[0] == 1 else "wiki pages", str(wiki[0]), wiki[1]))
    docs = _detect_docs_pages(root)
    if docs:
        facts.append(("doc page" if docs[0] == 1 else "doc pages", str(docs[0]), docs[1]))
    languages = sorted({LANGUAGE_BY_SUFFIX[suffix] for suffix in suffixes
                        if suffix in LANGUAGE_BY_SUFFIX})
    if len(languages) >= 2:
        facts.append(("language" if len(languages) == 1 else "languages", str(len(languages)),
                      "source file extensions: " + ", ".join(languages)))
    source_files = sum(count for suffix, count in suffixes.items() if suffix in LANGUAGE_BY_SUFFIX)
    if source_files:
        label = "source file" if source_files == 1 else "source files"
        facts.append((label, str(source_files), "source file extensions"))
    return facts


# --------------------------------------------------------------------------
# spec from the repository
# --------------------------------------------------------------------------

def spec_from_repository(root: Path, *, title: str = "", eyebrow: str = "", summary: str = "",
                         tagline: str = "", command: str = "", outputs: list[str] | None = None,
                         chips: list[str] | None = None, facts: list[tuple[str, str]] | None = None,
                         facts_mode: str = "auto", footer_left: str = "", footer_right: str = "",
                         homepage: str = "", url: str = "", accent: str = "",
                         license: str = "") -> BannerSpec:
    """Build a spec from the tree plus the explicit flags; flags always win over derivation."""
    root = Path(root)
    metadata = _repository_metadata(root)
    # Explicit facts come first: a user who types --facts auto next to --fact wants the typed
    # ones on the card, and the derived ones only fill the remaining pill slots.
    fact_rows: list[tuple[str, str]] = [(label.strip(), value.strip()) for label, value in facts or []]
    fact_sources: dict[str, str] = {fact_text(label, value).lower(): "command line --fact"
                                    for label, value in fact_rows}
    if facts_mode != "none":
        # Auto facts are generated in priority order: only the ones that still fit the pill
        # row are taken, so an ordinary `assets render` never warns about pills it chose to
        # leave out. A warning is for facts the caller asked for explicitly — --fact or --chips.
        remaining = max(0, MAX_FACTS - len(fact_rows) - len(chips or []))
        for label, value, source in derive_facts(root)[:remaining]:
            fact_rows.append((label, value))
            fact_sources[fact_text(label, value).lower()] = source
    if license.strip():
        fact_rows = [(label, value) for label, value in fact_rows
                     if label.strip().lower() != "license"]
        fact_rows.insert(0, ("license", license.strip()))
        fact_sources[fact_text("license", license.strip()).lower()] = "--license"
    resolved_title = EMOJI_RE.sub("", title or metadata["title"]).strip() or root.name
    resolved_url = url or metadata["repo_url"]
    resolved_homepage = homepage or metadata["homepage"]
    spec = BannerSpec(
        title=resolved_title,
        eyebrow=eyebrow,
        summary=summary or metadata["summary"],
        tagline=tagline or metadata["tagline"],
        command=command or metadata["command"],
        outputs=list(outputs or []),
        facts=fact_rows,
        chips=list(chips or []),
        footer_left=footer_left or _display_url(resolved_url),
        footer_right=footer_right or _display_url(resolved_homepage),
        license=license,
        accent=accent or PALETTE["accent"],
        command_source=(metadata["command_source"] if not command else ""),
        fact_sources=fact_sources,
    )
    return spec


# --------------------------------------------------------------------------
# writing, checking, suggesting
# --------------------------------------------------------------------------

TRUNCATION_HINTS = {
    "eyebrow": "shorten --eyebrow",
    "title": "shorten --title: it renders as one monospace line",
    "summary": "shorten --summary: it renders as at most two bold lines",
    "tagline": "shorten --tagline: it renders as at most two muted lines",
    "terminal": "shorten the terminal lines, or pass fewer --output-line values",
}


def write_assets(root: Path, *, out_dir: str = "assets", spec: BannerSpec | None = None,
                 write: bool = False, report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title="ghagent assets render", root=str(root))
    spec = spec or spec_from_repository(root)
    card = build_card(spec)
    svg = render_card_svg(card)
    png = render_card_png(card)
    sources = getattr(spec, "fact_sources", {})
    report.data.update({
        "svg": rel(root / out_dir / "social-preview.svg", root),
        "png": rel(root / out_dir / "social-preview.png", root) if png else "",
        "size": f"{card.width}x{card.height}",
        "written": [],
        "png_unavailable": "" if png else "Pillow is not installed: only the SVG was produced",
        "facts": list(card.facts),
        "fact_sources": {text.lower(): sources.get(text.lower(), "command line") for text in card.facts},
        "omitted_facts": list(card.omitted_facts),
        "terminal_rows": card.terminal_rows,
        "omitted_terminal_lines": card.omitted_lines,
        "footer_left": spec.footer_left,
        "footer_right": spec.footer_right,
        "accent": spec.accent,
    })
    for label in card.truncated:
        report.warn("assets.truncated", f"the {label} does not fit the card and was cut",
                    hint=TRUNCATION_HINTS.get(label, "shorten the value"))
    if card.omitted_facts:
        report.warn("assets.facts-overflow",
                    f"{len(card.omitted_facts)} fact(s) dropped from the pill row: "
                    + ", ".join(card.omitted_facts),
                    hint="the card shows at most six pills; pass fewer --fact values or shorten them")
    if card.omitted_lines:
        report.warn("assets.terminal-overflow",
                    f"the terminal panel shows {card.terminal_rows} of "
                    f"{card.terminal_rows + card.omitted_lines} lines",
                    hint="the panel has room for a few lines; pass fewer --output-line values")
    if spec.command_source:
        report.info("assets.derived-command",
                    f"the terminal shows a command declared by {spec.command_source}",
                    hint="pass --command to show another one")
    if not spec.command and not spec.outputs:
        report.info("assets.no-command", "the card has no terminal panel: no command and no output",
                    hint="pass --command 'ghagent audit .' (and --output for its lines) to draw one")
    if not png:
        report.warn("assets.no-pillow", "Pillow is not available, so no PNG was rendered",
                    hint="a social preview must be PNG/JPG/GIF; install Pillow or supply your own image")
    svg_path = root / out_dir / "social-preview.svg"
    png_path = root / out_dir / "social-preview.png"
    if not write:
        report.info("assets.dry-run", f"would write {rel(svg_path, root)} and {rel(png_path, root)}",
                    hint="pass --write to create the files")
        return report

    target = root / out_dir
    target.mkdir(parents=True, exist_ok=True)
    svg_path.write_bytes(svg.replace("\r\n", "\n").encode("utf-8"))
    written = [rel(svg_path, root)]
    if png:
        png_path.write_bytes(png)
        written.append(rel(png_path, root))
    report.data["written"] = written
    report.info("assets.written", f"{len(written)} file(s) under {out_dir}/")
    return report


HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
HTML_ATTR_RE = re.compile(r"\b(src|alt)\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)


def readme_references(readme: Path) -> list[tuple[str, str, int]]:
    """(alt, target, line) for every image in a markdown file, markdown or HTML."""
    if not Path(readme).exists():
        return []
    text, _ = read_text(readme)
    found: list[tuple[str, str, int]] = []
    for number, line in enumerate(text.split("\n"), start=1):
        for match in IMAGE_RE.finditer(line):
            found.append((match.group(1), match.group(2), number))
        for match in HTML_IMG_RE.finditer(line):
            attributes = {name.lower(): value for name, value in HTML_ATTR_RE.findall(match.group(0))}
            if attributes.get("src"):
                found.append((attributes.get("alt", ""), attributes["src"], number))
    return found


def check(root: Path, *, report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title="ghagent assets check", root=str(root))
    readme = root / "README.md"
    if not readme.exists():
        report.error("assets.no-readme", "README.md is absent, so no image reference can be examined")
        return report

    references = readme_references(readme)
    if not references:
        report.error("assets.readme-banner", "README references no image",
                     hint="render one with `ghagent assets render --write` and put it above the first section")
    relative_targets: list[str] = []
    for alt, target, line in references:
        if not alt.strip():
            report.warn("assets.alt", f"image without alt text: {target}", path="README.md", line=line)
        if target.startswith(("http://", "//")):
            report.warn("assets.insecure-url", f"image over a plain-http URL: {target}",
                        path="README.md", line=line)
            continue
        if target.startswith("https://"):
            continue
        relative_targets.append(target)
        resolved = (root / target.split("?")[0].split("#")[0]).resolve()
        if not resolved.exists():
            report.error("assets.missing-file", f"README references an image that does not exist: {target}",
                         path="README.md", line=line,
                         hint="commit the file or fix the path; a missing image renders as a broken box")
            continue
        suffix = resolved.suffix.lower()
        size = image_size(resolved)
        if suffix in SOCIAL_ACCEPTED and size:
            report.info("assets.dimensions", f"{target}: {size[0]}x{size[1]}", path="README.md")

    assets_dir = root / "assets"
    candidates = sorted(p for p in assets_dir.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES) if assets_dir.is_dir() else []
    if not candidates:
        report.warn("assets.no-directory", "no assets/ directory with an image",
                    hint="`ghagent assets render --write` creates assets/social-preview.png and .svg")
        report.data["social_preview_ready"] = False
        return report

    preview = next((p for p in candidates if p.stem.lower() in {"social-preview", "social_preview", "preview"}), None)
    if preview is None:
        report.warn("assets.social-preview", "no file named social-preview.* under assets/",
                    hint="the social preview is what link cards show; name it social-preview")
        report.data["social_preview_ready"] = False
        return report

    size_bytes = preview.stat().st_size
    if preview.suffix.lower() not in SOCIAL_ACCEPTED:
        report.warn("assets.svg-social", f"{rel(preview, root)} cannot be uploaded as a social preview",
                    hint="GitHub accepts PNG, JPG or GIF; keep the SVG for the README and add a PNG")
    if size_bytes > SOCIAL_MAX_BYTES:
        report.error("assets.social-size", f"{rel(preview, root)} is {size_bytes} bytes, over the 1 MB limit",
                     hint="compress the image; the platform rejects anything larger")
    dimensions = image_size(preview)
    if dimensions is None:
        report.warn("assets.social-dimensions", f"cannot read the size of {rel(preview, root)}",
                    hint="PNG, JPEG and GIF headers are readable; other formats are not")
    else:
        width, height = dimensions
        if width < SOCIAL_MIN[0] or height < SOCIAL_MIN[1]:
            report.error("assets.social-dimensions",
                         f"{rel(preview, root)} is {width}x{height}, below the 640x320 minimum")
        elif (width, height) != SOCIAL_SIZE:
            report.warn("assets.social-dimensions",
                        f"{rel(preview, root)} is {width}x{height}; 1280x640 renders best")
        else:
            report.info("assets.social-dimensions", f"{rel(preview, root)} is 1280x640")

    ready = (preview.suffix.lower() in SOCIAL_ACCEPTED and size_bytes <= SOCIAL_MAX_BYTES
             and dimensions is not None and dimensions[0] >= SOCIAL_MIN[0] and dimensions[1] >= SOCIAL_MIN[1])
    report.data.update({
        "social_preview_ready": ready,
        "social_preview_file": rel(preview, root),
        "social_preview_bytes": size_bytes,
        "social_preview_dimensions": list(dimensions) if dimensions else None,
        "images_in_assets": len(candidates),
        "readme_references": len(references),
    })
    if ready:
        report.info("assets.upload-hint",
                    "upload this file in Settings → Social preview; the file in the repository is not used automatically")
    return report


RECOMMENDATIONS = {
    "banner": "1280x640 social preview: it is what link cards in chat and search show",
    "diagram": "one architecture diagram; prefer a Mermaid block over a picture, because it stays editable",
    "screenshot": "one screenshot of the main screen at 1440 px wide, with personal data removed",
    "terminal": "one terminal capture of the primary command, as a code block rather than an image",
}


def suggest(root: Path, *, report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title="ghagent assets suggest", root=str(root))
    facts = meta_module.derive(root)
    languages = [language for language, _count in facts.get("languages", [])]
    wanted: list[dict] = [{"kind": "banner", "why": RECOMMENDATIONS["banner"]}]
    if any(language in {"php", "python", "javascript", "typescript", "csharp", "go", "rust"} for language in languages):
        wanted.append({"kind": "diagram", "why": RECOMMENDATIONS["diagram"]})
    readme = root / "README.md"
    has_ui = False
    if readme.exists():
        text, _ = read_text(readme)
        has_ui = any(word in text.lower() for word in ("интерфейс", "ui", "screenshot", "панель", "screen"))
    if has_ui:
        wanted.append({"kind": "screenshot", "why": RECOMMENDATIONS["screenshot"]})
    wanted.append({"kind": "terminal", "why": RECOMMENDATIONS["terminal"]})
    present = set()
    assets_dir = root / "assets"
    if assets_dir.is_dir():
        present = {p.stem.lower() for p in assets_dir.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES}
    for entry in wanted:
        entry["present"] = entry["kind"] in present or (entry["kind"] == "banner" and "social-preview" in present)
    report.data.update({"recommended": wanted, "present_in_assets": sorted(present)})
    missing = [entry["kind"] for entry in wanted if not entry["present"]]
    if missing:
        report.info("assets.missing", "no image for: " + ", ".join(missing),
                    hint="render the banner with `assets render --write`; the rest needs a human decision")
    else:
        report.info("assets.complete", "every recommended image kind is present")
    return report
