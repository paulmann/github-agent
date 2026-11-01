# Homebrew formula for the PyPI distribution github-agent-cli.
#
# Canonical location for `brew install paulmann/homebrew-github-agent-cli/github-agent-cli`
# is the tap repository; this copy is the reviewable source of truth and the CI job
# `manifests` verifies that its url and sha256 match what PyPI actually serves.
class GithubAgentCli < Formula
  include Language::Python::Virtualenv

  desc "Repository and wiki steward: one command per documentation job"
  homepage "https://github.com/paulmann/github-agent"
  url "https://files.pythonhosted.org/packages/source/g/github-agent-cli/github_agent_cli-1.3.0.tar.gz"
  sha256 "763595eb57df20b7e12711946680e528d100794d3fc0addf8fb4c9b06d33cf26"
  license "MIT"

  depends_on "python@3.13"

  livecheck do
    url "https://pypi.org/pypi/github-agent-cli/json"
    regex(/"version"\s*:\s*"([^"]+)"/i)
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/ghagent --version")
    assert_match "usage: ghagent", shell_output("#{bin}/ghagent --help")
  end
end