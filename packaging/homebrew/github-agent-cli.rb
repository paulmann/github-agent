# Homebrew formula for the PyPI distribution github-agent-cli.
#
# Canonical location for `brew install paulmann/homebrew-github-agent-cli/github-agent-cli`
# is the tap repository; this copy is the reviewable source of truth and the CI job
# `manifests` verifies that its url and sha256 match what PyPI actually serves.
class GithubAgentCli < Formula
  include Language::Python::Virtualenv

  desc "Repository and wiki steward: one command per documentation job"
  homepage "https://github.com/paulmann/github-agent"
  url "https://files.pythonhosted.org/packages/source/g/github-agent-cli/github_agent_cli-1.2.2.tar.gz"
  sha256 "f60d17b10a25fe6c9b307509fa7f0e58a571d1e39f802191dc1d6828b8ee14ae"
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