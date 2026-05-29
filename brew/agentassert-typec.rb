class AgentassertTypec < Formula
  desc "Formal behavioral contracts for AI agents — Type-C universal middleware"
  homepage "https://agentassert.com/typec"
  license "MIT"
  version "0.4.0"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/qualixar/agentassert-typec/releases/download/v0.4.0/agentassert-proxy-macos-arm64"
      sha256 "PLACEHOLDER_SHA256_ARM64"
    else
      url "https://github.com/qualixar/agentassert-typec/releases/download/v0.4.0/agentassert-proxy-macos-x86_64"
      sha256 "PLACEHOLDER_SHA256_X86_64"
    end
  end

  on_linux do
    url "https://github.com/qualixar/agentassert-typec/releases/download/v0.4.0/agentassert-proxy-linux-x86_64"
    sha256 "PLACEHOLDER_SHA256_LINUX"
  end

  def install
    if Hardware::CPU.arm?
      bin.install "agentassert-proxy-macos-arm64" => "agentassert-proxy"
    else
      bin.install "agentassert-proxy-macos-x86_64" => "agentassert-proxy" if OS.mac? && !Hardware::CPU.arm?
      bin.install "agentassert-proxy-linux-x86_64" => "agentassert-proxy" if OS.linux?
    end
    bin.install_symlink "agentassert-proxy" => "agentassert"
  end

  test do
    system "#{bin}/agentassert-proxy", "--help"
  end
end
