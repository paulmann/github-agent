#!/usr/bin/env python3
"""Render github-agent's own social preview: `assets/social-preview.png` and its SVG twin.

GitHub shows the social preview wherever the repository is linked, at roughly 400 pixels wide,
so the card carries one name, one sentence, a few measured facts and a terminal panel — anything
else turns into grey noise at that size.

    python tools/make_social_preview.py [--write]

This is a thin preset over the user-facing renderer in `tools/ghalib/assets.py`: the same
`BannerSpec` -> `Card` -> PNG/SVG path that `ghagent assets render` uses, so the generic card and
this one cannot drift into two designs. The preset supplies only what the generic renderer cannot
know — the eyebrow, the summary, the homepage footer and the terminal panel.

The terminal panel is not decoration. Before the card is drawn, the three commands below are
executed and the card repeats their last line; a command that fails stops the render instead of
printing a green line it did not see.

One layout description, two renderers: the PNG is drawn with Pillow (the `png` extra), the SVG
carries the same coordinates. Without Pillow the command exits 2 and says why, like every other
optional-dependency path in this pack.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from ghalib import assets  # noqa: E402

# The exact commands the terminal panel shows. They are run for real; the picture repeats what
# the tool printed at render time, so a stale claim is impossible.
AUDIT = [sys.executable, str(ROOT / "tools" / "ghagent.py"), "audit", ".", "--min-score", "85"]
DOC = [sys.executable, str(ROOT / "tools" / "ghagent.py"), "doc", "--root", "."]
CHANGELOG = [sys.executable, str(ROOT / "tools" / "ghagent.py"), "changelog", "check"]

SHOWN_AUDIT = "python tools/ghagent.py audit . --min-score 85"
SHOWN_DOC = "python tools/ghagent.py doc --root . && python tools/ghagent.py changelog check"


def _run(command: list[str]) -> str:
    """Run one gate command and return its last non-empty output line."""
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode != 0 or not lines:
        raise SystemExit(f"ghagent: {' '.join(command)} failed ({proc.returncode}); "
                         f"the card would have shown a line the tool did not print\n"
                         f"{proc.stderr.strip() or proc.stdout.strip()}")
    return lines[-1]


def terminal_lines() -> list[str]:
    """Command output the card is allowed to repeat: it was measured seconds ago."""
    return [
        _run(AUDIT),
        "$ " + SHOWN_DOC,
        _run(DOC),
        _run(CHANGELOG),
    ]


def build_spec() -> assets.BannerSpec:
    return assets.spec_from_repository(
        ROOT,
        title="github-agent",
        eyebrow="REPOSITORY & WIKI STEWARD",
        summary="One command per documentation job.",
        tagline="README, CHANGELOG, documents, links, images and the wiki — measured, not guessed.",
        command=SHOWN_AUDIT,
        outputs=terminal_lines(),
        footer_left="github.com/paulmann/github-agent",
        homepage="https://paulmann.github.io/github-agent/",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render github-agent's own social preview")
    parser.add_argument("--write", action="store_true",
                        help="replace assets/social-preview.png and assets/social-preview.svg")
    args = parser.parse_args(argv)

    card = assets.build_card(build_spec())
    svg = assets.render_card_svg(card)
    png = assets.render_card_png(card)
    if png is None:
        print('ghagent: Pillow is required to render the preview; install "github-agent-cli[png]"',
              file=sys.stderr)
        return 2

    print(f"png: {len(png)} bytes, svg: {len(svg)} bytes, {card.width}x{card.height}")
    print("facts on the card: " + ", ".join(card.facts))
    if not args.write:
        print("dry run; pass --write to replace the files under assets/")
        return 0
    png_path = ROOT / "assets" / "social-preview.png"
    svg_path = ROOT / "assets" / "social-preview.svg"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(png)
    svg_path.write_text(svg, encoding="utf-8", newline="\n")
    print(f"written {png_path.relative_to(ROOT)} and {svg_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
