"""GitHub wiki pipeline: manifest -> built wiki tree -> validated -> published.

Design constraints that came out of the platform:
  * the wiki is a flat namespace stored in a separate git repository (`<repo>.wiki.git`);
  * pages are addressed by filename without the `.md` suffix;
  * `_Sidebar.md` and `_Footer.md` are the only navigation files;
  * a relative image path cannot work, because the wiki repository has no access to the
    main repository tree — images must be referenced by an absolute URL.

Therefore `wiki build` rewrites every link and refuses to build silently-wrong pages:
a page that is missing from the manifest, a link to a non-existent page, or an image
that only exists inside the wiki source is an error, not a warning.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .util import (
    FENCE_RE,
    IMAGE_RE,
    INLINE_LINK_RE,
    MARKDOWN_SUFFIXES,
    Report,
    git,
    map_outside_code,
    read_text,
    rel,
    scan_structure,
    write_text,
)

WIKI_URL_TEMPLATE = "https://github.com/{slug}/wiki"
REPO_BLOB_TEMPLATE = "https://github.com/{slug}/blob/{branch}/{path}"
REPO_RAW_TEMPLATE = "https://github.com/{slug}/raw/{branch}/{path}"


@dataclass
class WikiManifest:
    slug: str
    branch: str = "main"
    title: str = ""
    footer: str = ""
    groups: list[dict] = field(default_factory=list)

    @property
    def pages(self) -> list[str]:
        ordered: list[str] = []
        for group in self.groups:
            for page in group.get("pages", []):
                if page not in ordered:
                    ordered.append(page)
        return ordered

    def group_of(self, page: str) -> str:
        for group in self.groups:
            if page in group.get("pages", []):
                return group.get("title", "")
        return ""


def load_manifest(path: Path) -> WikiManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return WikiManifest(
        slug=data.get("repo", ""),
        branch=data.get("branch", "main"),
        title=data.get("title", ""),
        footer=data.get("footer", ""),
        groups=data.get("groups", []),
    )


def page_id(filename: str) -> str:
    return filename[:-3] if filename.lower().endswith(".md") else filename


def _resolve_inside(candidate: Path, root: Path) -> str | None:
    """Resolve a link target relative to the page, but only inside the repository."""
    try:
        resolved = candidate.resolve()
        return resolved.relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return None


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build(root: Path, *, wiki_dir: str = "wiki", manifest_path: str = "wiki/wiki.json",
          out_dir: Path | None = None, report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title="ghagent wiki build", root=str(root))
    source = root / wiki_dir
    manifest_file = root / manifest_path

    if not source.is_dir():
        report.error("wiki.source", f"wiki source directory is missing: {wiki_dir}")
        return report
    if not manifest_file.exists():
        report.error("wiki.manifest", f"manifest is missing: {manifest_path}",
                     hint="copy reference/wiki-manifest-template.json and list every page")
        return report

    manifest = load_manifest(manifest_file)
    if not manifest.slug:
        report.warn("wiki.slug", "manifest has no `repo` field; absolute links will not be generated")
    if not manifest.title:
        report.warn("wiki.title", "manifest has no `title`; the sidebar header will be empty")

    on_disk = sorted(p.name for p in source.glob("*.md")
                     if not p.name.startswith("_") and p.suffix.lower() in MARKDOWN_SUFFIXES)
    listed = manifest.pages
    for page in listed:
        if page not in on_disk:
            report.error("wiki.page-missing", f"manifest lists {page}, which is not in {wiki_dir}/")
    for page in on_disk:
        if page not in listed:
            report.error("wiki.page-unlisted", f"{page} exists but is not listed in the manifest",
                         hint="an unlisted page is invisible in the sidebar; list it or delete it")
    if "Home.md" not in on_disk:
        report.error("wiki.home", "Home.md is missing", hint="the wiki landing page must be Home.md")
    if listed and listed[0] != "Home.md" and "Home.md" in listed:
        report.info("wiki.order", "Home.md is not the first manifest page (it is linked explicitly anyway)")

    out = Path(out_dir) if out_dir else root / ".ghagent" / "wiki"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    built: list[str] = []
    for filename in on_disk:
        text, _ = read_text(source / filename)
        rewritten = rewrite_page(text, source / filename, root, manifest, report)
        write_text(out / filename, rewritten)
        built.append(filename)

    sidebar = render_sidebar(manifest, on_disk)
    footer = render_footer(manifest, report)
    write_text(out / "_Sidebar.md", sidebar)
    write_text(out / "_Footer.md", footer)

    report.data.update({
        "pages": len(built),
        "out": str(out),
        "slug": manifest.slug,
        "branch": manifest.branch,
        "groups": len(manifest.groups),
    })
    if not built:
        report.error("wiki.empty", "no pages were built")
    return report


def rewrite_page(text: str, page_path: Path, root: Path, manifest: WikiManifest, report: Report) -> str:
    """Rewrite links and images for the wiki namespace, line by line, outside code fences."""
    page_name = page_path.name
    pages = set(manifest.pages)
    lines = text.split("\n")
    output: list[str] = []
    in_fence = False

    for index, raw in enumerate(lines, start=1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            output.append(raw)
            continue
        if in_fence:
            output.append(raw)
            continue

        def replace_image(match: re.Match) -> str:
            alt, target = match.group(1), match.group(2)
            if re.match(r"^(https?:)?//", target) or target.startswith("data:"):
                return match.group(0)
            report.error("wiki.image-relative", f"relative image in {page_name}: {target}",
                         path=page_name, line=index,
                         hint="the wiki cannot read the main repository tree: commit the image and use an absolute raw URL")
            return match.group(0)

        def replace_link(match: re.Match) -> str:
            label, target = match.group(1), match.group(2)
            if re.match(r"^(https?://|mailto:|tel:|#)", target):
                if re.match(r"^https?://github\.com/[^/]+/[^/]+/(blob|tree)/", target):
                    report.info("wiki.repo-link", f"link goes to the repository tree: {target}",
                                path=page_name, line=index)
                return match.group(0)
            path_part, _, anchor = target.partition("#")
            suffix = f"#{anchor}" if anchor else ""
            if path_part.lower().endswith(".md"):
                candidate = (page_path.parent / path_part).name
                if candidate in pages and (page_path.parent / path_part).exists():
                    return f"[{label}]({page_id(candidate)}{suffix})"
                resolved = _resolve_inside(page_path.parent / path_part, root)
                if resolved is not None and (root / resolved).exists():
                    return f"[{label}]({REPO_BLOB_TEMPLATE.format(slug=manifest.slug, branch=manifest.branch, path=resolved)}{suffix})"
                if resolved is None:
                    report.error("wiki.link-outside", f"link leaves the repository: {target}",
                                 path=page_name, line=index)
                else:
                    report.error("wiki.link-broken", f"link target does not exist: {target}",
                                 path=page_name, line=index)
                return match.group(0)
            if path_part and not path_part.startswith("#"):
                resolved = _resolve_inside(page_path.parent / path_part, root)
                if resolved is not None and (root / resolved).exists():
                    report.info("wiki.repo-relative", f"link to a repository path stays relative: {target}",
                                path=page_name, line=index,
                                hint="use an absolute GitHub URL, or leave it if the wiki should not link there")
            return match.group(0)

        line = map_outside_code(raw, lambda part: IMAGE_RE.sub(replace_image, part))
        # INLINE_LINK_RE carries a negative lookbehind for '!', so image syntax is not touched here
        if "[" in line:
            line = map_outside_code(line, lambda part: INLINE_LINK_RE.sub(replace_link, part))
        output.append(line)

    return "\n".join(output)


def render_sidebar(manifest: WikiManifest, on_disk: list[str]) -> str:
    lines: list[str] = []
    if manifest.title:
        lines.append(f"# {manifest.title}")
        lines.append("")
    lines.append("**[Home](Home)**")
    for group in manifest.groups:
        title = group.get("title", "").strip()
        pages = [p for p in group.get("pages", []) if p in on_disk]
        if not title or not pages:
            continue
        lines.append("")
        lines.append(f"### {title}")
        lines.append("")
        for page in pages:
            label = group.get("labels", {}).get(page) if isinstance(group.get("labels"), dict) else None
            if not label:
                label = page_id(page)
                label = re.sub(r"^(\d+)-", r"\1 · ", label).replace("-", " ")
            lines.append(f"- [{label}]({page_id(page)})")
    if manifest.slug:
        lines.append("")
        lines.append("### Ссылки")
        lines.append("")
        lines.append(f"- [Репозиторий](https://github.com/{manifest.slug})")
        lines.append(f"- [Релизы](https://github.com/{manifest.slug}/releases)")
        lines.append(f"- [Issues](https://github.com/{manifest.slug}/issues)")
    return "\n".join(lines).strip() + "\n"


def render_footer(manifest: WikiManifest, report: Report) -> str:
    if not manifest.slug:
        report.warn("wiki.footer", "footer is generated without repository links because `repo` is empty")
        return "---\n*Published by ghagent.*\n"
    parts = [f"[репозиторий](https://github.com/{manifest.slug})",
             f"[релизы](https://github.com/{manifest.slug}/releases)"]
    if manifest.footer:
        parts.append(manifest.footer)
    return "---\n*" + " · ".join(parts) + "*\n"


# --------------------------------------------------------------------------
# verify (built tree)
# --------------------------------------------------------------------------

def verify(build_dir: Path, *, report: Report | None = None) -> Report:
    build_dir = Path(build_dir)
    report = report or Report(title="ghagent wiki verify", root=str(build_dir))
    if not build_dir.is_dir():
        report.error("wiki.build-missing", f"no built wiki at {build_dir}", hint="run `ghagent wiki build` first")
        return report

    pages = {p.stem for p in build_dir.glob("*.md") if not p.name.startswith("_")}
    if not pages:
        report.error("wiki.pages", "no pages in the built wiki; nothing was examined")
        return report
    for required in ("Home", "_Sidebar", "_Footer"):
        if not (build_dir / f"{required}.md").exists():
            report.error("wiki.required", f"{required}.md is missing from the built wiki")

    internal_links: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(build_dir.glob("*.md")):
        text, meta = read_text(path)
        if meta.has_bom:
            report.error("doc.bom", "BOM in a wiki page", path=path.name)
        if meta.has_crlf:
            report.error("doc.crlf", "CRLF in a wiki page", path=path.name)
        headings, fences, links, _ = scan_structure(text)
        h1 = [h for h in headings if h.level == 1]
        if not h1 and path.name not in {"_Sidebar.md", "_Footer.md"}:
            report.warn("wiki.no-h1", "page has no H1", path=path.name)
        for fence in fences:
            if fence.closed_at is None:
                report.error("md.fence", "unclosed code fence", path=path.name, line=fence.line)
        for link in links:
            target = link.target
            if link.is_image and not target.startswith(("http://", "https://", "data:")):
                report.error("wiki.image-relative", f"relative image {target}", path=path.name, line=link.line)
            if re.match(r"^(https?:|mailto:|tel:)", target):
                continue
            path_part = target.split("#", 1)[0]
            if path_part.endswith(".md"):
                report.error("wiki.md-suffix", f"internal link keeps the .md suffix: {target}",
                             path=path.name, line=link.line, hint="wiki pages are addressed without .md")
                path_part = path_part[:-3]
            if path_part and path_part not in pages:
                report.error("wiki.link-target", f"link points to a non-existent page: {target}",
                             path=path.name, line=link.line)
            if path_part:
                internal_links.setdefault(path_part, []).append((link.line, path.name))

    sidebar = build_dir / "_Sidebar.md"
    if sidebar.exists():
        text, _ = read_text(sidebar)
        _, _, links, _ = scan_structure(text)
        linked = {link.target.split("#", 1)[0] for link in links if not link.target.startswith(("http", "mailto", "#"))}
        listed = {target[:-3] if target.endswith(".md") else target for target in linked}
        for page in sorted(pages - listed - {"Home"}):
            report.warn("wiki.page-orphan", f"page {page} is not reachable from the sidebar")
        for target in sorted(linked):
            clean = target[:-3] if target.endswith(".md") else target
            if clean and clean not in pages and not target.startswith("http"):
                report.error("wiki.sidebar-target", f"sidebar links to a non-existent page: {target}")

    footer = build_dir / "_Footer.md"
    if footer.exists():
        text, _ = read_text(footer)
        _, _, links, _ = scan_structure(text)
        for link in links:
            if not link.target.startswith(("http://", "https://")):
                report.warn("wiki.footer-relative", f"footer has a relative link: {link.target}",
                            hint="the footer is rendered on every page; absolute links only")

    report.data.update({"pages": len(pages), "links_internal": sum(len(v) for v in internal_links.values())})
    return report


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------

def wiki_remote(slug: str) -> str:
    return f"https://github.com/{slug}.wiki.git"


def publish(
    slug: str,
    build_dir: Path,
    *,
    push: bool = False,
    prune: bool = False,
    message: str = "",
    author_name: str = "",
    author_email: str = "",
    work_dir: Path | None = None,
    remote: str = "",
    report: Report | None = None,
) -> Report:
    """Publish a built wiki tree. Dry-run unless `push=True`; never deletes unless `prune=True`."""
    build_dir = Path(build_dir)
    report = report or Report(title=f"ghagent wiki publish {slug}", root=str(build_dir))
    if not build_dir.is_dir():
        report.error("wiki.build-missing", f"no built wiki at {build_dir}")
        return report
    files = sorted(p.name for p in build_dir.glob("*.md"))
    if not files:
        report.error("wiki.empty", "nothing to publish: the build directory has no markdown files")
        return report
    if "Home.md" not in files:
        report.error("wiki.home", "refusing to publish without Home.md")
        return report

    temp_created = work_dir is None
    work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="ghagent-wiki-"))
    clone_dir = work_dir / "wiki"
    remote = remote or wiki_remote(slug)

    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    rc, _, err = git(["clone", "--quiet", remote, str(clone_dir)], work_dir)
    if rc != 0:
        probe_rc, _, _ = git(["ls-remote", "--quiet", remote], work_dir)
        if probe_rc != 0:
            report.error(
                "wiki.remote-missing",
                f"the wiki repository does not exist: {remote}",
                hint=("GitHub creates <repo>.wiki.git only when the first page is saved in the web "
                      "interface (Wiki → New page); a push cannot create it. Create one page, then publish."),
            )
            return report
        clone_dir.mkdir(parents=True, exist_ok=True)
        git(["init", "--quiet"], clone_dir)
        git(["remote", "add", "origin", remote], clone_dir)
        report.info("wiki.remote-empty", f"remote {remote} is initialised but has no commits yet")
        if err.strip():
            report.info("wiki.clone-note", err.strip().splitlines()[0])

    changed_added: list[str] = []
    changed_modified: list[str] = []
    unchanged: list[str] = []
    for name in files:
        source = build_dir / name
        target = clone_dir / name
        payload, _ = read_text(source)
        if target.exists():
            current, _ = read_text(target)
            if current == payload:
                unchanged.append(name)
                continue
            changed_modified.append(name)
        else:
            changed_added.append(name)
        write_text(target, payload)

    existing = sorted(p.name for p in clone_dir.glob("*.md"))
    removed = [name for name in existing if name not in files]
    if removed and not prune:
        report.info("wiki.kept", f"{len(removed)} page(s) exist on the remote and are kept: {', '.join(removed[:6])}",
                    hint="pass --prune to delete pages that are no longer in the manifest")
    if removed and prune:
        for name in removed:
            (clone_dir / name).unlink()

    report.data.update({
        "added": changed_added,
        "modified": changed_modified,
        "unchanged": len(unchanged),
        "deleted": removed if prune else [],
        "kept": removed if not prune else [],
        "pushed": False,
        "remote": remote,
    })

    if not changed_added and not changed_modified and not (removed and prune):
        report.info("wiki.no-change", "the remote already matches the built tree; nothing to commit")
        return report

    git(["add", "-A"], clone_dir)
    identity: list[str] = []
    if author_name:
        identity += ["-c", f"user.name={author_name}"]
    if author_email:
        identity += ["-c", f"user.email={author_email}"]
    summary = message or f"docs(wiki): publish {len(changed_added)} new and {len(changed_modified)} updated page(s)"
    rc, out, err = git([*identity, "commit", "--quiet", "-m", summary], clone_dir)
    if rc != 0:
        report.error("wiki.commit", f"commit failed: {err.strip() or out.strip()}")
        return report
    rc, out, _ = git(["rev-parse", "--short", "HEAD"], clone_dir)
    commit = out.strip()
    report.data["commit"] = commit

    if not push:
        report.info("wiki.dry-run", f"would push commit {commit} to {remote}", hint="pass --push to publish")
        report.data["pushed"] = False
        return report

    rc, out, err = git(["push", "--quiet", "origin", "HEAD"], clone_dir)
    if rc != 0:
        report.error("wiki.push", f"push failed: {err.strip() or out.strip()}")
        return report
    report.data["pushed"] = True
    report.data["wiki_url"] = WIKI_URL_TEMPLATE.format(slug=slug)
    if temp_created:
        report.info("wiki.tempdir", f"work tree left at {clone_dir} for inspection")
    return report


# --------------------------------------------------------------------------
# scaffold
# --------------------------------------------------------------------------

def scaffold(root: Path, *, slug: str, title: str, wiki_dir: str = "wiki", from_docs: bool = True,
             report: Report | None = None) -> Report:
    root = Path(root)
    report = report or Report(title="ghagent wiki init", root=str(root))
    target = root / wiki_dir
    target.mkdir(parents=True, exist_ok=True)
    manifest_file = target / "wiki.json"
    if manifest_file.exists():
        report.error("wiki.manifest-exists", f"{manifest_file} already exists; refusing to overwrite")
        return report

    groups: list[dict] = []
    if from_docs and (root / "docs").is_dir():
        pages = sorted(p.name for p in (root / "docs").glob("*.md"))
        for index, page in enumerate(pages, start=1):
            new_name = f"{index:02d}-{page}"
            source = root / "docs" / page
            text, _ = read_text(source)
            write_text(target / new_name, text)
            groups.append({"title": "Документация", "pages": [new_name]})
        report.info("wiki.scaffold-docs", f"copied {len(pages)} page(s) from docs/")
    if not (target / "Home.md").exists():
        write_text(target / "Home.md", f"# {title}\n\nКраткое описание проекта и навигация по вики.\n\n"
                                       "Начните с [первой страницы](01-Getting-Started).\n")
    manifest = {
        "repo": slug,
        "branch": "main",
        "title": title,
        "footer": f"{title} · MIT",
        "groups": [{"title": "Начало", "pages": ["Home.md"]}, *groups],
    }
    write_text(manifest_file, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    report.data["created"] = rel(manifest_file, root)
    return report
