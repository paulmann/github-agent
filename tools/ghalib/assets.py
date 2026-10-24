"""Repository imagery: banner and social preview, rendered locally and then checked.

Why this exists. A repository with no picture reads as abandoned, and the reference
project's README opens with a 1280x640 banner. The image is easy to forget and easy to
break, so it is generated from the repository's own metadata and then verified:

  * the social preview must be PNG/JPG/GIF under 1 MB, at least 640x320, 1280x640 for
    best display (GitHub documentation, "Customizing your repository's social media preview");
  * an SVG is a fine README banner but cannot be uploaded as a social preview;
  * a reference to a missing file renders as a broken box, so every referenced image is
    resolved against the tree.

Rendering uses Pillow when it is installed (PNG), and always writes an SVG, which needs
nothing at all. A missing Pillow lowers the output format, never the honesty of the report.
"""

from __future__ import annotations

import base64
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .util import IMAGE_RE, Report, iter_text_files, read_text, rel

SOCIAL_SIZE = (1280, 640)
SOCIAL_MIN = (640, 320)
SOCIAL_MAX_BYTES = 1_000_000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif"}
SOCIAL_ACCEPTED = {".png", ".jpg", ".jpeg", ".gif"}

PALETTE = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "line": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#58a6ff",
    "accent2": "#3fb950",
    "warn": "#d29922",
}


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
# rendering
# --------------------------------------------------------------------------

@dataclass
class BannerSpec:
    title: str
    tagline: str = ""
    command: str = ""
    chips: list[str] = field(default_factory=list)
    footer: str = ""
    width: int = SOCIAL_SIZE[0]
    height: int = SOCIAL_SIZE[1]

    def normalised(self) -> "BannerSpec":
        self.chips = [chip for chip in self.chips if chip][:6]
        return self


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _wrap(text: str, limit: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        return []
    remainder = " ".join(words)[len(" ".join(lines)):].strip()
    if remainder and lines:
        lines[-1] = lines[-1].rstrip(" .,;") + "…"
    return lines


def render_svg(spec: BannerSpec) -> str:
    spec = spec.normalised()
    width, height = spec.width, spec.height
    pad = 72
    title_lines = _wrap(spec.title, 26, 2)
    tagline_lines = _wrap(spec.tagline, 62, 3)
    title_size = 64 if len(title_lines) <= 1 else 52
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{_escape(spec.title)}">',
        f'  <rect width="{width}" height="{height}" fill="{PALETTE["bg"]}"/>',
        f'  <rect x="0" y="0" width="{width}" height="6" fill="{PALETTE["accent"]}"/>',
        f'  <rect x="{pad}" y="{pad}" width="{width - 2 * pad}" height="{height - 2 * pad}" '
        f'rx="18" fill="{PALETTE["panel"]}" stroke="{PALETTE["line"]}"/>',
    ]
    y = pad + 96
    for line in title_lines:
        parts.append(
            f'  <text x="{pad + 48}" y="{y}" fill="{PALETTE["text"]}" font-size="{title_size}" '
            f'font-weight="700" font-family="Segoe UI, Helvetica, Arial, sans-serif">{_escape(line)}</text>')
        y += int(title_size * 1.18)
    y += 10
    for line in tagline_lines:
        parts.append(
            f'  <text x="{pad + 48}" y="{y}" fill="{PALETTE["muted"]}" font-size="26" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{_escape(line)}</text>')
        y += 36
    if spec.command:
        box_y = height - pad - 128
        parts.append(
            f'  <rect x="{pad + 48}" y="{box_y}" width="{width - 2 * pad - 96}" height="56" rx="10" '
            f'fill="{PALETTE["bg"]}" stroke="{PALETTE["line"]}"/>')
        parts.append(
            f'  <text x="{pad + 72}" y="{box_y + 36}" fill="{PALETTE["accent2"]}" font-size="22" '
            f'font-family="Consolas, Menlo, monospace">{_escape(spec.command)}</text>')
    chip_x = pad + 48
    chip_y = height - pad - 56
    for chip in spec.chips:
        chip_w = 14 + len(chip) * 12
        parts.append(
            f'  <rect x="{chip_x}" y="{chip_y}" width="{chip_w}" height="32" rx="16" '
            f'fill="none" stroke="{PALETTE["line"]}"/>')
        parts.append(
            f'  <text x="{chip_x + 12}" y="{chip_y + 22}" fill="{PALETTE["muted"]}" font-size="16" '
            f'font-family="Consolas, Menlo, monospace">{_escape(chip)}</text>')
        chip_x += chip_w + 10
    if spec.footer:
        parts.append(
            f'  <text x="{width - pad - 48}" y="{height - 26}" text-anchor="end" fill="{PALETTE["muted"]}" '
            f'font-size="18" font-family="Consolas, Menlo, monospace">{_escape(spec.footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _font(size: int, bold: bool = False, mono: bool = False):
    from PIL import ImageFont
    candidates = []
    if mono:
        candidates += ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
    if bold:
        candidates += ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    candidates += ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render_png(spec: BannerSpec) -> bytes | None:
    """PNG bytes, or None when Pillow is not installed."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    spec = spec.normalised()
    width, height = spec.width, spec.height
    pad = 72
    image = Image.new("RGB", (width, height), PALETTE["bg"])
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, 7], fill=PALETTE["accent"])
    draw.rounded_rectangle([pad, pad, width - pad, height - pad], radius=18,
                           fill=PALETTE["panel"], outline=PALETTE["line"], width=2)

    title_lines = _wrap(spec.title, 26, 2)
    title_font = _font(64 if len(title_lines) <= 1 else 52, bold=True)
    y = pad + 58
    for line in title_lines:
        draw.text((pad + 48, y), line, font=title_font, fill=PALETTE["text"])
        y += title_font.size + 12
    y += 6
    tagline_font = _font(26)
    for line in _wrap(spec.tagline, 62, 3):
        draw.text((pad + 48, y), line, font=tagline_font, fill=PALETTE["muted"])
        y += tagline_font.size + 10
    if spec.command:
        box_y = height - pad - 128
        draw.rounded_rectangle([pad + 48, box_y, width - pad - 48, box_y + 56], radius=10,
                               fill=PALETTE["bg"], outline=PALETTE["line"], width=2)
        draw.text((pad + 72, box_y + 15), spec.command, font=_font(22, mono=True), fill=PALETTE["accent2"])
    chip_font = _font(16, mono=True)
    chip_x = pad + 48
    chip_y = height - pad - 56
    for chip in spec.chips:
        chip_w = 14 + int(chip_font.getlength(chip))
        draw.rounded_rectangle([chip_x, chip_y, chip_x + chip_w, chip_y + 32], radius=16,
                               outline=PALETTE["line"], width=2)
        draw.text((chip_x + 12, chip_y + 7), chip, font=chip_font, fill=PALETTE["muted"])
        chip_x += chip_w + 10
    if spec.footer:
        footer_font = _font(18, mono=True)
        draw.text((width - pad - 48 - footer_font.getlength(spec.footer), height - 44),
                  spec.footer, font=footer_font, fill=PALETTE["muted"])
    from io import BytesIO
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def spec_from_repository(root: Path, *, title: str = "", tagline: str = "", command: str = "",
                         chips: list[str] | None = None) -> BannerSpec:
    from . import meta as meta_module
    facts = meta_module.derive(root)
    readme = Path(root) / "README.md"
    summary = ""
    if readme.exists():
        text, _ = read_text(readme)
        for block in text.split("\n\n"):
            stripped = block.strip()
            if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 20:
                summary = stripped.strip("*").strip()
                break
        if not summary:
            summary = facts.get("summary", "")
    languages = [language for language, _count in facts.get("languages", [])[:3]]
    return BannerSpec(
        title=title or facts.get("title") or Path(root).name,
        tagline=tagline or summary[:180],
        command=command,
        chips=(chips if chips is not None else languages + ["mit"])[:6],
        footer=" · ".join(filter(None, ["MIT", ", ".join(languages)])),
    )


# --------------------------------------------------------------------------
# writing, checking, suggesting
# --------------------------------------------------------------------------

def write_assets(root: Path, *, out_dir: str = "assets", spec: BannerSpec | None = None,
                 write: bool = False, report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title="ghagent assets render", root=str(root))
    spec = (spec or spec_from_repository(root)).normalised()
    target = root / out_dir
    svg_path = target / "social-preview.svg"
    png_path = target / "social-preview.png"
    svg = render_svg(spec)
    png = render_png(spec)

    report.data.update({
        "svg": rel(svg_path, root),
        "png": rel(png_path, root) if png else "",
        "size": f"{spec.width}x{spec.height}",
        "written": [],
        "png_unavailable": "" if png else "Pillow is not installed: only the SVG was produced",
    })
    if not png:
        report.warn("assets.no-pillow", "Pillow is not available, so no PNG was rendered",
                    hint="a social preview must be PNG/JPG/GIF; install Pillow or supply your own image")
    if not write:
        report.info("assets.dry-run", f"would write {rel(svg_path, root)} and {rel(png_path, root)}",
                    hint="pass --write to create the files")
        return report

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
    from . import meta as meta_module
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
