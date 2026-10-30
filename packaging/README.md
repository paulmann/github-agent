# Packaging manifests

Native installers for the `github-agent-cli` distribution. The canonical copies live in their
package-manager repositories; the files here are the reviewable source of truth and the CI job
`manifests` proves that every URL resolves and every hash matches the file it names.

| File | Package manager | Canonical repository | Install command |
|---|---|---|---|
| [homebrew/github-agent-cli.rb](homebrew/github-agent-cli.rb) | Homebrew (macOS, Linux) | `paulmann/homebrew-github-agent-cli` | `brew install paulmann/homebrew-github-agent-cli/github-agent-cli` |
| [scoop/github-agent-cli.json](scoop/github-agent-cli.json) | Scoop (Windows) | `paulmann/scoop-github-agent-cli` | `scoop bucket add github-agent-cli https://github.com/paulmann/scoop-github-agent-cli` then `scoop install github-agent-cli` |

The Homebrew formula installs the PyPI sdist; the Scoop manifest installs the Windows bundle from
the GitHub release (`ghagent.cmd` plus the wheel contents) and declares `python` as a dependency.

## Bumping a manifest

1. Publish the release (the `Publish` workflow uploads it to PyPI and the release carries the
   Windows bundle and `SHA256SUMS.txt`).
2. Homebrew: take `sha256` from `https://pypi.org/pypi/github-agent-cli/json`
   (`.urls[].digests.sha256` for the `.tar.gz`), update `url` and `sha256`, copy the file into the
   tap repository.
3. Scoop: take the hash of `github-agent-cli-X.Y.Z-windows-x64.zip` from `SHA256SUMS.txt`, update
   `version`, `url`, `hash` and `extract_dir`, copy the file into the bucket repository.
4. Run `python tools/ghagent.py audit .` and let the `manifests` CI job check the download.

There is no placeholder hash anywhere: a wrong hash fails the job instead of installing the wrong
bytes.
