"""Install this pack into an agent's skill directory and verify the installation.

Three consumers are supported by name, because their skill roots are measured, not guessed:

  autoclaw  %USERPROFILE%\\.pi\\agent\\skills      (AutoClaw / AutoClaw2)
  harness   %USERPROFILE%\\.dsh\\skills            (HARNESS)
  saga      no fixed root — pass --target explicitly

`install` copies the pack and writes `.install.json` with a sha256 for every file, so
`verify` answers the only question that matters later: is the installed copy still the
one that was tested, or has it drifted?
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .util import PACK_NAME, PACK_VERSION, Report, read_text, rel, write_text

PROFILE_ROOTS = {
    "autoclaw": Path(".pi") / "agent" / "skills",
    "harness": Path(".dsh") / "skills",
}
PACK_CONTENT = ("AGENTS.md", "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
                "SUPPORT.md", "CODE_OF_CONDUCT.md", "LICENSE", "CITATION.cff",
                "skills", "tools", "tests", "reference", "docs", ".github", "wiki")
INSTALL_MANIFEST = ".install.json"
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ghagent"}


def user_home() -> Path:
    for variable in ("USERPROFILE", "HOME"):
        value = os.environ.get(variable)
        if value:
            return Path(value)
    return Path.home()


def resolve_target(profile: str, target: str | None) -> tuple[Path | None, str]:
    if target:
        return Path(target).expanduser(), ""
    if profile in PROFILE_ROOTS:
        return user_home() / PROFILE_ROOTS[profile], ""
    return None, f"profile '{profile}' has no fixed skill root; pass --target <dir>"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def collect_files(source: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in PACK_CONTENT:
        path = source / name
        if not path.exists():
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and not (set(child.parts) & SKIP_DIRS):
                    files[rel(child, source)] = _hash(child)
        else:
            files[name] = _hash(path)
    return files


def install(source: Path, target: Path, *, write: bool = False, report: Report | None = None) -> Report:
    source = Path(source)
    target = Path(target)
    report = report or Report(title=f"ghagent install -> {target}")
    if not (source / "tools" / "ghagent.py").exists():
        report.error("install.source", f"{source} does not look like the {PACK_NAME} pack")
        return report
    files = collect_files(source)
    if not files:
        report.error("install.empty", "no files collected from the source pack")
        return report

    destination = target / PACK_NAME
    report.data.update({"destination": str(destination), "files": len(files), "written": False})
    if not write:
        report.info("install.dry-run", f"would copy {len(files)} file(s) to {destination}",
                    hint="pass --write to install")
        return report

    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name, digest in files.items():
        origin = source / name
        if not origin.exists():
            continue
        aim = destination / name
        aim.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, aim)
        copied += 1
    manifest = {
        "pack": PACK_NAME,
        "version": PACK_VERSION,
        "installed_to": str(destination),
        "files": files,
    }
    write_text(destination / INSTALL_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    report.data.update({"written": True, "copied": copied})
    report.info("install.done", f"{copied} file(s) installed; run `ghagent selftest` from {destination}")
    return report


def verify(installed: Path, *, report: Report | None = None) -> Report:
    installed = Path(installed)
    report = report or Report(title=f"ghagent verify {installed}")
    if installed.name == PACK_NAME:
        root = installed
    else:
        root = installed / PACK_NAME
    manifest_path = root / INSTALL_MANIFEST
    if not manifest_path.exists():
        report.error("verify.manifest", f"{manifest_path} is absent: this copy was not installed by ghagent",
                     hint="run `ghagent install --write`")
        return report
    manifest = json.loads(read_text(manifest_path)[0])
    expected: dict[str, str] = manifest.get("files", {})
    if not expected:
        report.error("verify.empty", "the install manifest lists no files")
        return report
    missing: list[str] = []
    changed: list[str] = []
    for name, digest in expected.items():
        path = root / name
        if not path.exists():
            missing.append(name)
            continue
        if _hash(path) != digest:
            changed.append(name)
    present = {rel(p, root) for p in root.rglob("*") if p.is_file() and not (set(p.parts) & SKIP_DIRS)}
    extra = sorted(present - set(expected) - {INSTALL_MANIFEST})
    for name in missing:
        report.error("verify.missing", f"file is absent: {name}")
    for name in changed:
        report.error("verify.changed", f"file differs from the installed copy: {name}")
    for name in extra:
        report.info("verify.extra", f"file not in the manifest: {name}")
    report.data.update({
        "version": manifest.get("version"),
        "expected": len(expected),
        "missing": missing,
        "changed": changed,
        "extra": len(extra),
    })
    if not missing and not changed:
        report.info("verify.ok", f"{len(expected)} file(s) match version {manifest.get('version')}")
    return report


def snippet(target: Path | None = None) -> str:
    root = (Path(target) if target else Path("<skill-root>")) / PACK_NAME
    return "\n".join([
        "## Agent pack: github-agent",
        "",
        f"Skill root: `{root}`",
        "",
        "1. Read `AGENTS.md` in that directory before any repository or wiki work.",
        f"2. Verify the installation: `python \"{root / 'tools' / 'ghagent.py'}\" selftest`",
        "3. Use one command per job instead of reading files by hand:",
        "   `ghagent.py audit`, `doc`, `wiki build|publish`, `changelog check|release`, `meta apply`.",
        "4. Never publish a wiki without `wiki verify` passing and `--push` given explicitly.",
        "",
    ])


def remove(installed: Path, *, write: bool = False, report: Report | None = None) -> Report:
    """Remove an installed pack. Refuses unless the directory carries our manifest."""
    installed = Path(installed)
    report = report or Report(title=f"ghagent uninstall {installed}")
    root = installed if installed.name == PACK_NAME else installed / PACK_NAME
    manifest_path = root / INSTALL_MANIFEST
    if not manifest_path.exists():
        report.error("uninstall.refused", f"{root} has no {INSTALL_MANIFEST}; refusing to delete an unknown directory")
        return report
    if not write:
        report.info("uninstall.dry-run", f"would delete {root}", hint="pass --write to remove")
        return report
    shutil.rmtree(root)
    report.info("uninstall.done", f"removed {root}")
    return report
