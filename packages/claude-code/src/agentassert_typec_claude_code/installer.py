from __future__ import annotations

import shutil
import stat
from pathlib import Path


def install(contract_path: str, force: bool = False) -> None:
    hooks_dir = Path.home() / ".claude-hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_file = hooks_dir / "00-agentassert-typec.py"
    source_hook = Path(__file__).parent / "hook.py"

    if hook_file.exists() and not force:
        raise FileExistsError(
            f"Hook already installed at {hook_file}. Use --force to overwrite."
        )

    shutil.copy2(source_hook, hook_file)
    hook_file.chmod(hook_file.stat().st_mode | stat.S_IEXEC | stat.S_IXUSR | stat.S_IXGRP)

    print(f"✅ AgentAssert Type-C hook installed to {hook_file}")
    print()
    print("Add this to your shell config (~/.zshrc or ~/.bashrc):")
    print(f"  export AGENTASSERT_CONTRACT={contract_path}")
    print()
    import sys
    if sys.stdout.isatty():
        print("⭐  If AgentAssert Type-C is useful, please star the repo:")
        print("    https://github.com/qualixar/agentassert-typec")


def uninstall() -> None:
    hook_file = Path.home() / ".claude-hooks" / "00-agentassert-typec.py"
    if hook_file.exists():
        hook_file.unlink()
        print(f"✅ AgentAssert Type-C hook removed from {hook_file}")
    else:
        print("Hook not installed.")
