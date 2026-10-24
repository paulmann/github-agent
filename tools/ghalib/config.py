"""Repository-local configuration: `.ghagent.json` at the repository root.

Defaults are deliberately conservative: nothing is published and nothing is deleted
unless a human passes the flag that says so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = ".ghagent.json"


@dataclass
class Config:
    root: Path
    owner_repo: str = ""
    default_branch: str = "main"
    readme: str = "README.md"
    agents: str = "AGENTS.md"
    changelog: str = "CHANGELOG.md"
    docs_dir: str = "docs"
    wiki_dir: str = "wiki"
    wiki_manifest: str = "wiki/wiki.json"
    ci_workflow: str = ".github/workflows/ci.yml"
    require_files: list[str] = field(default_factory=list)
    ignore_rules: list[str] = field(default_factory=list)
    topic_min: int = 8
    topic_max: int = 20
    description_max: int = 200
    changelog_style: str = "keepachangelog"
    language: str = "ru"

    def path(self, relative: str) -> Path:
        return self.root / relative


def load(root: Path) -> Config:
    root = Path(root)
    config = Config(root=root)
    candidate = root / CONFIG_NAME
    if not candidate.exists():
        return config
    data = json.loads(candidate.read_text(encoding="utf-8"))
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if hasattr(config, key):
            setattr(config, key, value)
    return config
