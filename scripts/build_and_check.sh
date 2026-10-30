#!/usr/bin/env bash
# Build github-agent and verify the artefact end to end.
#
#   PYTHON=python3 bash scripts/build_and_check.sh
#
# What it proves, in order:
#   1. the sdist and the wheel build from this tree with the declared backend;
#   2. `twine check` accepts both;
#   3. the artefact version equals PACK_VERSION in tools/ghalib/util.py (the only source);
#   4. the wheel installs `ghagent.py` and `ghalib/` flat in site-packages, with no `tools`
#      package;
#   5. the wheel has no runtime dependency except the optional `png` extra;
#   6. a clean virtual environment can install the wheel, `ghagent --version` answers, and
#      the installed CLI lints and audits this checkout.
#
# Requirements: Python 3.11+ with venv support, network access to PyPI (build backend and
# twine only). Everything happens under a temporary directory; the repository tree is not
# modified.
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ghagent-check.XXXXXX")
BUILD_VENV="$WORK/build-venv"
TEST_VENV="$WORK/test-venv"
DIST="$WORK/dist"

cleanup() {
    rm -rf "$WORK"
}
trap cleanup EXIT

step() {
    printf '\n== %s ==\n' "$1"
}

step "build environment"
"$PYTHON" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip build twine

step "build sdist and wheel"
"$BUILD_VENV/bin/python" -m build --outdir "$DIST" "$ROOT"

step "twine check"
"$BUILD_VENV/bin/python" -m twine check "$DIST"/*

step "version from the single source"
VERSION=$("$BUILD_VENV/bin/python" - "$ROOT" <<'PY'
import pathlib
import re
import sys

text = (pathlib.Path(sys.argv[1]) / "tools" / "ghalib" / "util.py").read_text(encoding="utf-8")
match = re.search(r'^PACK_VERSION = "([^"]+)"', text, re.M)
if not match:
    raise SystemExit("PACK_VERSION is missing from tools/ghalib/util.py")
print(match.group(1))
PY
)
echo "PACK_VERSION: $VERSION"

WHEEL="$DIST/github_agent_cli-$VERSION-py3-none-any.whl"
SDIST="$DIST/github_agent_cli-$VERSION.tar.gz"
test -f "$WHEEL"
test -f "$SDIST"

step "wheel layout"
"$BUILD_VENV/bin/python" -m zipfile -l "$WHEEL" | tee "$WORK/wheel.txt"
grep -q '^ghagent.py' "$WORK/wheel.txt"
grep -q '^ghalib/' "$WORK/wheel.txt"
if grep -q '^tools/' "$WORK/wheel.txt"; then
    echo "FAIL: the wheel installs a top-level tools package" >&2
    exit 1
fi

step "no third-party runtime dependency"
"$BUILD_VENV/bin/python" - "$WHEEL" <<'PY'
import email
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as archive:
    name = next(item for item in archive.namelist() if item.endswith(".dist-info/METADATA"))
    metadata = email.message_from_bytes(archive.read(name))
requires = metadata.get_all("Requires-Dist") or []
print("Requires-Dist:", requires or "none")
unexpected = [item for item in requires if "extra ==" not in item]
if unexpected:
    raise SystemExit(f"runtime dependencies found: {unexpected}")
PY

step "clean installation"
"$PYTHON" -m venv "$TEST_VENV"
"$TEST_VENV/bin/python" -m pip install --quiet --disable-pip-version-check "$WHEEL"
ACTUAL=$("$TEST_VENV/bin/ghagent" --version)
echo "ghagent --version: $ACTUAL"
test "$ACTUAL" = "github-agent $VERSION"
"$TEST_VENV/bin/python" -m pip list

step "smoke test on the repository checkout"
(
    cd "$ROOT"
    "$TEST_VENV/bin/ghagent" doc --root .
    "$TEST_VENV/bin/ghagent" audit . --min-score 80
)

printf '\nPASS: github-agent %s built, checked and installed with no runtime dependency\n' "$VERSION"
