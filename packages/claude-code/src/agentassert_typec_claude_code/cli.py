from __future__ import annotations

import sys
from pathlib import Path

import click


@click.group()
def cli():
    pass


@cli.command()
@click.option("--contract", "-c", required=True, help="Path to contract YAML")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing hook")
def install_cmd(contract: str, force: bool) -> None:
    from agentassert_typec_claude_code.installer import install

    contract_path = Path(contract).resolve()
    if not contract_path.exists():
        click.echo(f"Error: Contract file not found: {contract_path}", err=True)
        sys.exit(1)

    install(str(contract_path), force=force)


@cli.command()
def uninstall_cmd() -> None:
    from agentassert_typec_claude_code.installer import uninstall

    uninstall()


@cli.command()
def status_cmd() -> None:
    from pathlib import Path

    hook_file = Path.home() / ".claude-hooks" / "00-agentassert-typec.py"
    if hook_file.exists():
        click.echo(f"✅ Hook installed: {hook_file}")
    else:
        click.echo("❌ Hook not installed")

    import os
    contract = os.environ.get("AGENTASSERT_CONTRACT", "")
    if contract:
        click.echo(f"   AGENTASSERT_CONTRACT={contract}")
    else:
        click.echo("   AGENTASSERT_CONTRACT not set")


if __name__ == "__main__":
    cli()
