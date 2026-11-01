"""MkDocs hook: point links that leave `docs/` at the repository, not at the site.

The documents in `docs/` are written for the repository, where `../AGENTS.md` resolves to the
file next door. A rendered site has no parent directory, so the same link would 404. GitHub is
the canonical place for those files, so the hook rewrites every relative link that escapes
`docs_dir` into `https://github.com/<owner>/<repo>/blob/<branch>/<path>`.

Everything that stays inside `docs/` is left alone: MkDocs itself rewrites those to pages.

Loaded from `mkdocs.yml` (`hooks:`), Python standard library only.
"""

from __future__ import annotations

import posixpath
import re

# `href="../AGENTS.md"` and `src="../assets/x.png"` — relative targets that leave docs/.
ESCAPING_LINK_RE = re.compile(r'(?P<attribute>\b(?:href|src)=")(?P<target>\.\./[^"#?]*)(?P<rest>[^"]*)"')


def on_page_content(html: str, page, config, files) -> str:
    repo_url = (config.get("repo_url") or "").rstrip("/")
    if not repo_url:
        return html
    branch = (config.get("extra") or {}).get("repo_branch", "main")
    base = posixpath.dirname(page.file.src_uri) or ""

    def rewrite(match: re.Match) -> str:
        target = match.group("target")
        rest = match.group("rest")
        # Resolve as if the tree were rooted at `docs/`: the page lives at `docs/<src_uri>`,
        # so `../AGENTS.md` means the repository root, not the parent of the site.
        resolved = posixpath.normpath(posixpath.join("docs", base, target))
        if resolved == ".." or resolved.startswith("../"):
            return match.group(0)          # escapes the repository as well: leave it
        repo_path = resolved.removeprefix("docs/")
        url = f"{repo_url}/blob/{branch}/{repo_path}"
        return f'{match.group("attribute")}{url}{rest}"'

    return ESCAPING_LINK_RE.sub(rewrite, html)
